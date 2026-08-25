# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Dead-letter replay organ — classification half (pure read).

A failed ENABLED write leaves its payload in a per-process dead-letter
sidecar (writer._dead_letter). Those bytes are life the ledger omitted.
This module answers the only question that may precede any replay:
**what actually happened to each record?** It writes nothing — no
SQLite open for write, no spool directory, no state file.

Dispositions, in decision order:

``refused_evidence``
    A deterministic writer refusal (bad provenance/payload). The
    admission door already judged these bytes; re-submitting them would
    invert the refusal. Evidence forever.
``already_committed``
    A live row carries this record's identity. Since 2026-08-24
    ``owner_write_turn`` persists its pre-attempt ``attempt_id`` as the
    row's ``submission_id``, so the timeout-after-commit case — the
    write landed, then the response was lost and the failure classified
    — is an EXACT lookup instead of byte archaeology.
``already_enqueued``
    A replay envelope for this identity is already in the spool. One
    identity, one envelope: overwriting a published filename would race
    an in-flight drain.
``possibly_committed``
    No identity match, but a byte-identical row of the same kind
    committed within ``WINDOW_S`` of the record. This is the shape a
    pre-identity (legacy) timeout-after-commit leaves behind. Withheld
    for owner review — never auto-replayed, never auto-discarded.
``replayable``
    Everything else.

Byte identity is a SIGNAL, not an identity. The owner saying "ok" twice
is two lives; withholding the second loses speech, which is an equal
crime to duplicating it with a different victim. So a byte twin outside
the window flags (``byte_twin_exists``) and stays replayable.

Torn final lines (a writer SIGKILLed mid-append) are counted and
reported, never guessed at.
"""
from __future__ import annotations

import glob
import json
import sqlite3
from pathlib import Path

__all__ = ["classify", "WINDOW_S"]

#: How close in time a byte-identical row must be for a record to be
#: treated as a possible pre-identity timeout-after-commit.
WINDOW_S = 300.0

_PRODUCER = "dead_letter_replay"


def _records(db_path: str) -> tuple[list[dict], int]:
    """Every dead-letter record across all pid sidecars, deduped by
    identity (a redrive that failed twice is ONE record), plus the torn
    line count."""
    from core.ledger.writer import dead_letter_glob

    seen: dict[str, dict] = {}
    torn = 0
    for path in sorted(glob.glob(dead_letter_glob(db_path))):
        try:
            text = Path(path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                event_id = record["event_id"]
                if not isinstance(event_id, str) or not event_id:
                    raise ValueError("missing event_id")
            except (ValueError, KeyError, TypeError):
                torn += 1
                continue
            record.setdefault("source_file", path)
            seen.setdefault(event_id, record)
    return list(seen.values()), torn


def _db_view(db_path: str, wanted_ids: set[str]) -> tuple[dict, list]:
    """(identity → turn_id, [(turn_kind, raw_text, timestamp)]).

    mode=ro: the classifier runs in ANY process and must never perform
    WAL recovery or an autocheckpoint as a stray writer.
    """
    committed: dict[str, str] = {}
    rows: list = []
    if not Path(db_path).exists() or Path(db_path).stat().st_size == 0:
        return committed, rows
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except sqlite3.Error:
        return committed, rows
    try:
        for turn_id, sid in conn.execute(
            "SELECT turn_id, submission_id FROM turns"
            " WHERE submission_id IS NOT NULL"
        ):
            if sid in wanted_ids:
                committed[sid] = turn_id
        rows = conn.execute(
            "SELECT turn_kind, raw_text, timestamp FROM turns"
            " WHERE chain_position > 0"
        ).fetchall()
    except sqlite3.Error:
        return committed, rows
    finally:
        conn.close()
    return committed, rows


def classify(db_path: str) -> dict:
    """Classify every dead-letter record. Pure read; never raises."""
    from core.ledger import spool

    records, torn = _records(db_path)
    wanted = {r["event_id"] for r in records}
    committed, rows = _db_view(db_path, wanted)

    by_payload: dict[tuple, list[float]] = {}
    for turn_kind, raw_text, ts in rows:
        by_payload.setdefault((turn_kind, raw_text), []).append(ts)

    spool_root = spool.default_spool_root(db_path)
    out: list[dict] = []
    for record in sorted(records, key=lambda r: r.get("ts") or 0):
        event_id = record["event_id"]
        entry = {
            "event_id": event_id,
            "ts": record.get("ts"),
            "turn_kind": record.get("turn_kind"),
            "category": record.get("category"),
            "source_file": record.get("source_file"),
        }
        twin_times = by_payload.get(
            (record.get("turn_kind"), record.get("raw_text")), []
        )
        entry["byte_twin_exists"] = bool(twin_times)

        if record.get("category") == "refused":
            entry["disposition"] = "refused_evidence"
            entry["reason"] = (
                "the admission door judged these bytes; re-submitting "
                "them would invert the refusal"
            )
        elif event_id in committed:
            entry["disposition"] = "already_committed"
            entry["turn_id"] = committed[event_id]
        elif spool._submission_exists(spool_root, _PRODUCER, event_id):
            entry["disposition"] = "already_enqueued"
            entry["spool_state"] = spool._submission_exists(
                spool_root, _PRODUCER, event_id
            )
        else:
            record_ts = record.get("ts")
            near = [
                t for t in twin_times
                if isinstance(t, (int, float))
                and isinstance(record_ts, (int, float))
                and abs(t - record_ts) <= WINDOW_S
            ]
            if near:
                entry["disposition"] = "possibly_committed"
                entry["reason"] = (
                    "a byte-identical row of this kind committed within "
                    f"{WINDOW_S:g}s — this may be a pre-identity "
                    "timeout-after-commit. Owner review: replaying could "
                    "duplicate a life, discarding could erase one."
                )
            else:
                entry["disposition"] = "replayable"
        out.append(entry)

    counts: dict[str, int] = {"torn": torn}
    for entry in out:
        counts[entry["disposition"]] = counts.get(entry["disposition"], 0) + 1
    return {"db_path": db_path, "records": out, "counts": counts}
