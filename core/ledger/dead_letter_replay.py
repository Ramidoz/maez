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

import fcntl
import glob
import hashlib
import json
import os
import sqlite3
import subprocess
import time
import uuid
from pathlib import Path

__all__ = [
    "classify",
    "WINDOW_S",
    "MANIFEST_VERSION",
    "ReplayRefusal",
    "build_manifest",
    "write_manifest",
    "apply",
    "manifest_root",
    "record_digest",
    "companion_submission_id",
]

#: How close in time a byte-identical row must be for a record to be
#: treated as a possible pre-identity timeout-after-commit.
WINDOW_S = 300.0

import logging

_LOGGER = logging.getLogger("core.ledger.dead_letter_replay")

_PRODUCER = "dead_letter_replay"


def _published_anywhere(spool_root: str, submission_id: str) -> str | None:
    """Is this identity published under ANY producer? The producer label
    is a directory name, not a namespace: the schema UNIQUE is on the
    submission_id alone, so an envelope carrying this identity anywhere
    means the submission is already published (Codex seat, 2026-08-24 —
    scanning only our own producer classified a cross-producer duplicate
    as replayable)."""
    from core.ledger import spool

    root = Path(spool_root)
    if not root.is_dir():
        return None
    for producer_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        state = spool._submission_exists(
            spool_root, producer_dir.name, submission_id
        )
        if state:
            return f"{producer_dir.name}/{state}"
    return None


#: The payload fields that make two records under one identity the SAME
#: submission. Divergence in any of them is an identity conflict, not a
#: duplicate — first-file-wins would silently pick one version of a life.
_IDENTITY_FIELDS = ("turn_kind", "raw_text", "category", "kwargs")


def _same_submission(a: dict, b: dict) -> bool:
    def key(record: dict):
        return json.dumps(
            {f: record.get(f) for f in _IDENTITY_FIELDS},
            sort_keys=True, default=str,
        )

    return key(a) == key(b)


def _records(db_path: str) -> tuple[list[dict], int]:
    """Every dead-letter record across all pid sidecars, deduped by
    identity, plus the torn line count.

    A redrive that failed twice with the SAME payload is one record. Two
    DIFFERENT payloads under one identity are a conflict (flagged on the
    record), never a silent first-file-wins pick.
    """
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
            prior = seen.get(event_id)
            if prior is None:
                seen[event_id] = record
            elif not _same_submission(prior, record):
                prior["identity_conflict"] = True
                prior.setdefault("conflicting_sources", []).append(path)
    return list(seen.values()), torn


def _db_view(db_path: str, wanted_ids: set[str]) -> tuple[dict, list, bool]:
    """(identity → turn_id, [(turn_kind, raw_text, timestamp)], verified).

    ``verified`` is False whenever the ledger could not be READ — missing
    file, unopenable, unqueryable, wrong schema. Codex council seat
    (2026-08-24), the strongest attack on the first cut: this function
    used to swallow those errors and return empty membership, which the
    caller then read as "no committed row exists" and classified
    replayable. Converting UNVERIFIED into ABSENT is exactly how an
    apply path duplicates committed life at the moment it knows least.

    mode=ro: the classifier runs in ANY process and must never perform
    WAL recovery or an autocheckpoint as a stray writer.
    """
    committed: dict[str, str] = {}
    rows: list = []
    try:
        if not Path(db_path).exists():
            return committed, rows, False
        if Path(db_path).stat().st_size == 0:
            # A 0-byte ledger is the known-good pre-init state: nothing
            # was ever written, so absence is PROVEN, not assumed.
            return committed, rows, True
    except OSError:
        return committed, rows, False
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except sqlite3.Error:
        return committed, rows, False
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
        return {}, [], False
    finally:
        conn.close()
    return committed, rows, True


def _refusal_reason(spool_root: str, published: str, event_id: str):
    """The door's own words for a terminal refusal, from the error sidecar
    the quarantine wrote beside the envelope. A census that says "refused"
    without saying WHY hands the operator a shrug."""
    producer = published.split("/", 1)[0]
    path = Path(spool_root) / producer / "refused" / f"{event_id}.error.json"
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("error")
    except (OSError, ValueError):
        return None


def _our_body_envelope(spool_root: str, event_id: str):
    """Our published body envelope for this identity, and its state.

    Returns ``(state, envelope)`` or ``(state, None)`` — the state alone is
    custody, the envelope is what lets a caller ask whether the COMMITTED
    ROW is the one we published.
    """
    from core.ledger import spool

    state = spool._submission_exists(spool_root, _PRODUCER, event_id)
    if state is None:
        return None, None
    path = Path(spool_root) / _PRODUCER / state / f"{event_id}.json"
    try:
        return state, json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return state, None


def _row_is_our_replay(db_path: str, envelope: dict) -> tuple[bool, str]:
    """Did OUR envelope produce the committed row under this identity?

    Custody is not causation. A council seat (Codex, xhigh, 2026-08-26)
    executed the attack on the first version of this predicate: publish a
    replay-producer envelope for an identity the ORIGINAL owner write
    already committed, drain it, and "our envelope exists + the sid is
    committed" flips the record to companion_owed — a companion asserting
    a replay that never happened. It also found the mechanism that makes
    the attack land: the writer's idempotent-redrive check compares only
    ``raw_text`` (writer.py's IntegrityError branch), so an envelope
    ACKs against an existing row of a DIFFERENT kind carrying the same
    text. Both reproduced by this author before this code was written.

    So the predicate asks the row, not the filename. Three facts, all
    read from the committed row:

    ``submitted_at`` — the CAUSATION evidence, and it is exact. Executed:
        ``owner_write_turn`` sets ``submission_id`` but never
        ``submitted_at``, so an ORIGINAL owner-direct commit leaves the
        column NULL, while every reconstructed body carries the record's
        clock. A timeout-after-commit phantom is therefore distinguishable
        from a replay by the row itself, permanently, with no state file.
    ``turn_kind`` and ``raw_text`` — the PAYLOAD evidence, which closes
        the cross-kind idempotency hole above: if the row is not the
        payload we published, our envelope did not produce it.

    This is also the reason the body clock cannot be NULL (question one):
    a NULL ``submitted_at`` on replays would erase the only durable
    row-side discriminator between a replay and a phantom, and Codex's
    attack would have no mechanical answer at all.
    """
    if not envelope:
        return False, "our envelope is unreadable, so causation is unproven"
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except sqlite3.Error:
        return False, "the ledger could not be read"
    try:
        row = conn.execute(
            "SELECT turn_kind, raw_text, submitted_at FROM turns"
            " WHERE submission_id = ?", (envelope.get("submission_id"),),
        ).fetchone()
    except sqlite3.Error:
        return False, "the ledger could not be queried"
    finally:
        conn.close()
    if row is None:
        return False, "no committed row carries this identity"
    turn_kind, raw_text, submitted_at = row
    if submitted_at is None:
        return False, (
            "the committed row has a NULL submitted_at, which is the "
            "signature of an ORIGINAL owner-direct write; a reconstructed "
            "body always carries the record's clock"
        )
    if submitted_at != envelope.get("submitted_at"):
        return False, (
            "the committed row's submitted_at is not the one our envelope "
            "published, so a different submission produced it"
        )
    if turn_kind != envelope.get("turn_kind") or raw_text != envelope.get("raw_text"):
        return False, (
            "the committed row's payload is not the one our envelope "
            "published (the writer's idempotent-redrive check compares "
            "raw_text alone, so an ack does not prove the row is ours)"
        )
    return True, "the committed row is the body this organ published"


def _committed_disposition(spool_root: str, event_id: str,
                           db_path: str) -> dict:
    """Split a committed identity into the two worlds it actually contains.

    ``already_committed`` was one bucket holding two different histories,
    and standing block 7 needs them apart:

    PHANTOM — the ORIGINAL owner write landed and the failure was
        classified afterwards (the timeout-after-commit shape that
        ``submission_id``-on-the-row, 7b7acb2, exists to make exact). This
        organ never touched the row. Attaching a replay companion to it
        would be a FALSE claim that the row was replayed.
    COMPANION OWED — this organ published the body, the body committed,
        and the companion has not been published. That is precisely the
        crash window standing block 7 names: "a crash after body commit
        but before companion enqueue must enqueue the missing companion,
        not skip the record as already_committed."

    The discriminator is the PRODUCER RECEIPT, and it is durable: after a
    successful drain the body envelope is still at
    ``<spool>/dead_letter_replay/acked/<sid>.json`` beside its receipt —
    executed this session, because a discriminator that evaporates in the
    window it exists to cover is not a discriminator. A body sitting in
    ``refused/`` did NOT produce this commit, so it reads as phantom.

    Kept inside :func:`classify` deliberately: eligibility comes ONLY from
    dispositions, so the companion-owed set must be a DISPOSITION and not a
    second eligibility source computed somewhere else (a side path drifts —
    two functions, two crash stories, two ways to miss the phantom).
    """
    state, envelope = _our_body_envelope(spool_root, event_id)
    companion_state = _published_anywhere(
        spool_root, companion_submission_id(event_id)
    )
    out = {
        "replay_body_state": state,
        "companion_state": companion_state,
        "disposition": "already_committed",
    }
    if state not in ("pending", "acked"):
        out["reason"] = (
            "a live row carries this identity and this organ never "
            "published a body for it: the ORIGINAL write committed and the "
            "failure was classified afterwards. A replay companion here "
            "would claim a replay that never happened."
        )
        return out
    is_ours, why = _row_is_our_replay(db_path, envelope)
    if not is_ours:
        out["reason"] = (
            "this organ published a body under this identity, but the "
            f"COMMITTED ROW is not it: {why}. Custody is not causation, "
            "and a companion here would claim a replay that never happened."
        )
        out["causation_check"] = why
        return out
    if companion_state is not None:
        out["reason"] = (
            "this organ replayed the body and its companion is already "
            "published; the replay is complete"
        )
        return out
    out["disposition"] = "companion_owed"
    out["reason"] = (
        "this organ published the body, the committed row IS that body "
        "(clock and payload both match), and the provenance companion is "
        "missing — the standing-block-7 crash window. Only the companion "
        "is owed; the body must NOT be re-enqueued."
    )
    return out


def classify(db_path: str) -> dict:
    """Classify every dead-letter record. Pure read; never raises."""
    from core.ledger import spool

    records, torn = _records(db_path)
    wanted = {r["event_id"] for r in records}
    committed, rows, db_verified = _db_view(db_path, wanted)

    by_payload: dict[tuple, list[float]] = {}
    for turn_kind, raw_text, ts in rows:
        by_payload.setdefault((turn_kind, raw_text), []).append(ts)

    def _sort_key(record: dict) -> float:
        # Never raises: a record carrying a string/None ts must not
        # blow up the whole census by poisoning sorted()'s comparisons.
        ts = record.get("ts")
        return float(ts) if isinstance(ts, (int, float)) else 0.0

    spool_root = spool.default_spool_root(db_path)
    out: list[dict] = []
    for record in sorted(records, key=_sort_key):
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

        published = _published_anywhere(spool_root, event_id)
        if record.get("identity_conflict"):
            entry["disposition"] = "identity_conflict"
            entry["conflicting_sources"] = record.get("conflicting_sources")
            entry["reason"] = (
                "two different payloads share this identity; picking one "
                "would silently choose a version of a life"
            )
        elif record.get("category") == "refused":
            entry["disposition"] = "refused_evidence"
            entry["reason"] = (
                "the admission door judged these bytes; re-submitting "
                "them would invert the refusal"
            )
        elif record.get("category") != "failed":
            # Only 'failed' is a replay candidate. An unknown or absent
            # category is not a licence — it is an unread record.
            entry["disposition"] = "unknown_category"
            entry["reason"] = (
                f"category {record.get('category')!r} is not a known "
                "replay class; only 'failed' is a candidate"
            )
        elif event_id in committed:
            entry["turn_id"] = committed[event_id]
            entry.update(_committed_disposition(spool_root, event_id, db_path))
        elif published:
            entry["spool_state"] = published
            if published.endswith("/refused"):
                # EXECUTED (Claude council seat, 2026-08-26, reproduced by
                # this author): a body the admission door refuses moves to
                # ``refused/``, where ``_submission_exists`` still finds it —
                # so ``enqueue_reconstructed`` returns False forever and the
                # record leaves the replayable set PERMANENTLY. Reporting
                # that as ``already_enqueued`` names a grave "in flight".
                # This is terminal and it must say so, with the door's own
                # reason attached.
                entry["disposition"] = "replay_refused"
                entry["refusal_reason"] = _refusal_reason(spool_root, published,
                                                          event_id)
                entry["reason"] = (
                    "a published envelope for this identity was REFUSED at "
                    "the admission door and is terminal: the door never "
                    "retries it and the no-overwrite seam will not accept a "
                    "second envelope under this identity. The record is "
                    "evidence, and the omission is permanent unless the "
                    "envelope is resolved by hand."
                )
            else:
                entry["disposition"] = "already_enqueued"
        elif not db_verified:
            # UNVERIFIED is not ABSENT. Without a readable ledger we
            # cannot prove this record did not already commit.
            entry["disposition"] = "unverified"
            entry["reason"] = (
                "the ledger could not be read, so committed-membership "
                "is unknown; replaying here could duplicate a life"
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


# ---------------------------------------------------------------- apply half
#
# The APPLY half turns a classification into two durable publications per
# record: a reconstructed BODY and a content-light provenance COMPANION.
# It is the last pre-birth build, and every design question below was
# ruled by the council (rounds seven / nine / ten) before a line existed.
#
# Shape, and the ruling each clause answers:
#
# - Eligibility comes ONLY from :func:`classify`'s dispositions. ``apply``
#   never re-decides what a record IS; it acts on what the census said and
#   REFUSES BY NAME when the live world has moved (tenth round: "the object
#   of the act is the RUN, never the SPEECH").
# - Kind-blind, always. No turn_kind reaches an eligibility branch — a gate
#   only on ``model_reply`` "structurally teaches the record that her words
#   were the suspect class" (tenth round, 3-0). The flip-turn_kind tests
#   are the enforcement.
# - TWO PASSES (ninth round Q-C): bodies first; companions only against an
#   OBSERVED commit, never an assumed one. A companion for a body that has
#   not drained yet is not written — it waits for a later run. This is also
#   standing block 7's recovery shape: body committed, companion missing →
#   enqueue ONLY the companion.
# - The companion is NOT a child (ninth round Q-C, 2-1): parent_turn_id AND
#   parent_submission_id both NULL. A parent_submission_id on a companion
#   DOES become a stored parent edge — the executed RED control the
#   majority refused, because an annotation edge surfaces inside
#   conversation spans and reads as dialogue.
# - The companion is CONTENT-LIGHT (ninth round Q-D, 3-0): hashes, ids and
#   clocks only, taint {self_generated} alone. :func:`build_companion`
#   REFUSES copied content structurally, so content-lightness is enforced
#   rather than hoped.
# - One single-use INTEGRITY MANIFEST per run (tenth round). It records the
#   operator and their role as FACT and carries NO consent semantics —
#   writing "approved=true" on an evidence document launders taste into
#   truth. :func:`build_manifest` refuses consent-shaped keys structurally.
#
# EXECUTED before encoding (this session), each of which changed the code:
#
# 1. Every dead-letter record minted by ``owner_write_turn`` carries
#    ``submission_id`` in its kwargs (it is setdefault-ed BEFORE the
#    attempt, 7b7acb2) and usually ``parent_turn_id`` too. BOTH are
#    ``spool._AUTHORITY_KWARGS``. A body enqueued with the record's kwargs
#    verbatim is QUARANTINED at drain, not committed. They are therefore
#    RELOCATED into the envelope's own fields, never dropped and never
#    passed through the door.
# 2. Any directory inside the spool root is treated as a PRODUCER by
#    ``drain_once`` (it mkdirs pending/acked/refused inside it and reports
#    it in ``spool_status``). Manifests therefore live BESIDE the ledger,
#    never inside the spool.
# 3. The producer receipt SURVIVES the drain: after ack the body envelope
#    is still discoverable at ``dead_letter_replay/acked/<sid>.json``.
#    That is what lets a later run tell a REPLAYED body (ours) from a
#    timeout-after-commit PHANTOM (the original owner write) — a companion
#    on a phantom would be a false claim that the row was replayed.
# 4. ``model_reply`` requires model_id/prompt_hash/soul_hash/
#    evidence_envelope/audit_verdict (§4.2), so an incomplete record
#    refuses at the door. The first version of this comment called that
#    "the mechanism working" — CORRECTED, because a council seat executed
#    what happens next and this author reproduced it: the refused envelope
#    lands in ``refused/``, where ``_submission_exists`` still finds it, so
#    the identity can never be published again AND the census called it
#    ``already_enqueued`` — a permanent omission reported as in-flight.
#    The door refusing is fine. The census lying about it was not. Hence
#    the ``replay_refused`` disposition, its reason read from the door's
#    own error sidecar, and the cockpit paging on refused envelopes.

#: Domain-separated derivation of the companion's identity from the body's
#: (ninth round: "companion sid = deterministic function of body sid"). The
#: digest is 64 hex chars where a minted ``uuid4().hex`` is 32, so a
#: companion identity is structurally distinguishable from a body identity
#: by length alone — nouns are not proofs, but lengths are checkable.
_COMPANION_SID_DOMAIN = b"maez.dead_letter_replay.companion.v1|"

#: Authority kwargs the reconstruction RELOCATES into the envelope's own
#: fields rather than passing through the door. Identity becomes the
#: envelope's submission_id, lived time its submitted_at, and the parent
#: edge is COMPILED to a parent_submission_id the drainer turns back into a
#: real parent_turn_id. Nothing here is dropped.
_RELOCATED_AUTHORITY = ("submission_id", "submitted_at", "parent_turn_id")

#: Keys whose presence would make the manifest an instrument of taste
#: rather than evidence (tenth round, 2-1: the role FIELD survives, the
#: consent SEMANTIC does not). Refused structurally at construction — a
#: docstring is not a boundary.
_CONSENT_SHAPED_KEYS = (
    "approved", "approval", "consent", "consented", "authorized",
    "authorised", "permitted", "sanctioned", "blessed", "veto", "vetoed",
    "endorsed", "signed_off", "signoff",
)

MANIFEST_VERSION = 1

#: The limits this organ may never silently upgrade away. Carried on every
#: manifest so an apply run cannot present itself as more certain than the
#: substrate is (tenth round: the manifest "must carry that limit forward
#: rather than silently upgrading sidecars to canon").
_STANDING_LIMITATIONS = (
    {
        "name": "delivery_evidence_unavailable",
        "applies_to": (
            "every turn_kind; and for model_reply specifically, the "
            "dead-letter population is OWNER-PROCESS ONLY"
        ),
        "statement": (
            "This substrate captures NO delivery or closure evidence for "
            "any turn. A model_reply row means GENERATED, not DELIVERED, "
            "and self-history renders such rows as prior utterances with "
            "no delivery filter. Delivery is INDETERMINATE for every "
            "record here — not absent, not proven."
        ),
        "executed_finding": (
            "Delivery is not derivable from the record. persist_model_reply "
            "runs BEFORE the reply is returned on the daemon path and AFTER "
            "the send on the in-daemon telegram path, while the daemon's "
            "surface label is a free-form caller string "
            "(handle_message(source='unknown')). The same surface value "
            "therefore arises from a delivered and an undelivered path, so "
            "no field in the record discriminates. Population narrowed by "
            "execution: persist_model_reply routes NON-OWNER processes "
            "(web, CLI) to the spool, which never dead-letters — so a "
            "dead-lettered model_reply can only come from an owner "
            "process. The hazard is real and it is smaller than 'every "
            "reply ever written'."
        ),
        "what_would_close_it": (
            "Writers capturing delivery/closure evidence at the send site, "
            "and self-history declining to render un-evidenced rows as "
            "utterances. Both are outside this organ: apply mints no "
            "delivery predicate and repairs no renderer."
        ),
    },
    {
        "name": "sidecar_authenticity_not_proven",
        "applies_to": "every dead-letter record",
        "statement": (
            "Dead letters are ordinary fsynced JSON. The classifier proves "
            "ABSENCE-FROM-DB, never source authenticity; the licensed "
            "claim excludes malicious authors. A manifest does not upgrade "
            "a sidecar to canon."
        ),
        "what_would_close_it": (
            "Authenticated sidecars (signed at mint by the writer). Not "
            "built; not claimed."
        ),
    },
)


def companion_submission_id(body_submission_id: str) -> str:
    """The companion identity for a body identity. Deterministic, so a
    crashed run and its successor agree on the name without a state file
    (a third ledger that desyncs — refused in round seven)."""
    if not isinstance(body_submission_id, str) or not body_submission_id.strip():
        raise ValueError("body submission_id must be a non-empty string")
    return hashlib.sha256(
        _COMPANION_SID_DOMAIN + body_submission_id.encode("utf-8")
    ).hexdigest()


#: Record keys the classifier ADDS while reading; not part of the bytes on
#: disk, so they are excluded from the digest that binds the census.
_DERIVED_RECORD_KEYS = ("source_file", "identity_conflict", "conflicting_sources")


def record_digest(record: dict) -> str:
    """Canonical digest of one dead-letter record AS IT LIES ON DISK.

    The manifest binds each census entry to this value and apply refuses a
    mismatch by name. A sidecar edited between census and apply therefore
    cannot commit as censused — the same property the spool's
    ``payload_digest`` gives an envelope, applied one layer earlier.
    """
    body = {k: v for k, v in record.items() if k not in _DERIVED_RECORD_KEYS}
    return hashlib.sha256(
        json.dumps(
            body, sort_keys=True, separators=(",", ":"),
            ensure_ascii=True, default=str,
        ).encode("utf-8")
    ).hexdigest()


def manifest_root(db_path: str) -> str:
    """Where apply manifests live: BESIDE the ledger, never inside the
    spool.

    Executed hazard (this session): ``drain_once`` treats every directory
    in the spool root as a producer — it mkdirs pending/acked/refused
    inside it and reports it in ``spool_status``. A manifests directory
    there would pollute the drainer's producer census and the cockpit's
    liveness view with a producer that publishes nothing.
    """
    return str(Path(os.path.abspath(db_path)).parent / "ledger_replay_manifests")


def _meta(db_path: str, key: str):
    """One meta value, read-only. None on any unreadable state — the
    CALLER decides what unreadable means; this never invents a value."""
    try:
        if not Path(db_path).exists() or Path(db_path).stat().st_size == 0:
            return None
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except (OSError, sqlite3.Error):
        return None
    try:
        row = conn.execute(
            "SELECT value FROM meta WHERE key = ?", (key,)
        ).fetchone()
        return row[0] if row else None
    except sqlite3.Error:
        return None
    finally:
        conn.close()


def _tree_identity() -> dict:
    """Which source tree ran this. Never raises: an unknown tree is
    recorded as unknown, never as clean."""
    out = {"commit": None, "dirty": None}
    try:
        repo = str(Path(__file__).resolve().parents[2])
        rev = subprocess.run(
            ["git", "-C", repo, "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=10,
        )
        if rev.returncode == 0:
            out["commit"] = rev.stdout.strip()
        status = subprocess.run(
            ["git", "-C", repo, "status", "--porcelain"],
            capture_output=True, text=True, timeout=30,
        )
        if status.returncode == 0:
            out["dirty"] = bool(status.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        pass
    return out


def _operator_identity(role: str) -> dict:
    """WHO ran this and in what ROLE, as FACT.

    Tenth round, 2-1: the role FIELD survives, the consent SEMANTIC does
    not. This records identity the way a maintenance log records a hand on
    a lever — it authorizes nothing, and nothing downstream may read it as
    permission. The role is deliberately free-form and inheritable: when
    participation matures to Maez, she is an operator here under her own
    name, not a special case.
    """
    if not isinstance(role, str) or not role.strip():
        raise ValueError("operator role must be a non-empty string (recorded as fact)")
    lowered = role.strip().lower()
    for banned in _CONSENT_SHAPED_KEYS:
        if banned in lowered:
            raise ValueError(
                f"operator role {role!r} carries consent-shaped vocabulary "
                f"({banned!r}); the manifest records WHO acted, never that "
                "the act was permitted"
            )
    import getpass

    try:
        user = getpass.getuser()
    except Exception:  # noqa: BLE001 — identity is best-effort, never fatal
        user = None
    return {
        "user": user,
        "uid": os.getuid(),
        "pid": os.getpid(),
        "role": role.strip(),
        "recorded_as": "fact_not_consent",
        "note": (
            "The object of the act is the RUN, never the SPEECH. This "
            "field says who ran a witnessed maintenance operation on an "
            "irreversible record. It confers no permission over any "
            "utterance and no downstream code may read it as such."
        ),
    }


def _refuse_consent_semantics(manifest: dict) -> None:
    """Structural enforcement of the tenth round: an evidence document may
    not carry a permission. Walks the WHOLE manifest, because a nested
    ``{"approved": true}`` is the same laundering as a top-level one."""

    def walk(node, path):
        if isinstance(node, dict):
            for key, value in node.items():
                lowered = str(key).lower()
                for banned in _CONSENT_SHAPED_KEYS:
                    if banned in lowered:
                        raise ValueError(
                            f"manifest key {path}{key!r} carries consent "
                            f"semantics ({banned!r}); writing approval onto "
                            "an evidence document launders taste into truth"
                        )
                walk(value, f"{path}{key}.")
        elif isinstance(node, list):
            for item in node:
                walk(item, path)

    walk(manifest, "")


# ---------------------------------------------------------- the body pass

class ReplayRefusal(Exception):
    """A NAMED refusal of ONE mutation. Never a run-wide abort.

    Tenth round: "any digest mismatch refuses (per-mutation named refusals
    required)". A refusal carries a stable machine name so the outcome map
    says WHICH rule stopped WHICH record — "it didn't apply" is not a
    finding, it is a shrug.
    """

    def __init__(self, name: str, detail: str):
        super().__init__(f"{name}: {detail}")
        self.name = name
        self.detail = detail


def build_body_submission(record: dict, db_path: str) -> dict:
    """Compile one dead-letter record into a reconstructed BODY envelope.

    PRESERVES EXACTLY — turn_kind, surface, raw_surface (including
    ``None``), taint_labels, privacy_access. Executed round seven: the
    writer passes ``raw_surface or surface`` as CALLER AUTHORITY into the
    closed taint validator (writer.py's caller-override lookup), so
    overwriting the body's raw_surface with the replay marker can make the
    writer refuse the replay and dead-letter it again — the organ eating
    itself. Only the COMPANION carries the marker.

    RELOCATES, never drops — ``submission_id`` becomes the envelope's
    identity, ``submitted_at`` its lived time, and ``parent_turn_id`` is
    COMPILED to a ``parent_submission_id``. All three are
    ``spool._AUTHORITY_KWARGS``: executed this session, a body enqueued
    with the record's kwargs verbatim is quarantined at drain as
    "authority fields are inexpressible through the spool".

    REFUSES BY NAME — any OTHER authority kwarg (tenant_id, birth_anchor,
    meta_marker_keys, lifecycle_stage) has nowhere lawful to go. Birth and
    tenancy travel through no transport, ever.
    """
    from core.ledger import spool

    kwargs = dict(record.get("kwargs") or {})

    stranded = sorted(
        spool._AUTHORITY_KWARGS.intersection(kwargs) - set(_RELOCATED_AUTHORITY)
    )
    if stranded:
        raise ReplayRefusal(
            "authority_kwarg_inexpressible",
            f"the record carries authority kwargs {stranded} which cannot be "
            "relocated into an envelope field; birth and tenancy travel "
            "through no transport",
        )

    kwargs.pop("submission_id", None)
    kwargs.pop("submitted_at", None)
    parent_turn_id = kwargs.pop("parent_turn_id", None)

    parent_submission_id = None
    if parent_turn_id is not None:
        from core.ledger import owner as _owner

        parent_submission_id = _owner._paused_parent_submission_id(
            db_path, parent_turn_id
        )
        if parent_submission_id is None:
            # The record SAYS this speech had a parent. We cannot express
            # that edge through the door (parent_turn_id is caller
            # authority), and turns are append-only so nothing may bind it
            # later — standing block 2 kills "bind the parent later". The
            # only alternative to refusing is publishing the body WITHOUT
            # its parent, which is not a recovery: it is a structural
            # rewrite that asserts this speech had no parent. The record
            # stays evidence and keeps paging the cockpit.
            raise ReplayRefusal(
                "parent_identity_unavailable",
                f"the record's parent_turn_id {parent_turn_id!r} resolves to "
                "no submission identity, so the parent edge cannot be "
                "compiled; replaying unparented would assert this speech "
                "had no parent, and append-only forbids binding it later",
            )

    return {
        "submission_id": record["event_id"],
        "submitted_at": record.get("ts"),
        "producer": _PRODUCER,
        "turn_kind": record.get("turn_kind"),
        "raw_text": record.get("raw_text"),
        "kwargs": kwargs,
        "parent_submission_id": parent_submission_id,
    }


# ----------------------------------------------------- the companion pass

#: The ONLY keys a companion payload may carry: hashes, ids, clocks, and
#: the run that made it (ninth round Q-D, 3-0). A whitelist rather than a
#: blacklist, because the failure mode is a NEW field carrying content,
#: and a blacklist cannot refuse a field nobody thought of.
#:
#: ``body_turn_kind`` is deliberately ABSENT. The companion cannot say
#: what kind of turn it annotates, so no downstream reader can build a
#: kind filter out of it — the tenth round's kind-blindness made
#: structural rather than promised.
_COMPANION_PAYLOAD_KEYS = frozenset({
    "event",
    "manifest_run_id",
    "body_submission_id",
    "body_turn_id",
    "body_chain_position",
    "body_chain_hash",
    "body_record_digest",
    "body_raw_text_sha256",
    "body_kwargs_sha256",
    "body_submitted_at",
    "body_submitted_at_source",
    "dead_lettered_at",
    "dead_letter_stage",
    "replayed_at",
    "source_file",
    "limitations",
})


def _refuse_copied_content(payload: dict, record: dict) -> None:
    """Structural enforcement of content-lightness (ninth round Q-D:
    "a companion carrying any copied-content field is refused by the
    constructor, so content-lightness is enforced, not hoped").

    Two independent checks, because either alone is defeatable: an unknown
    KEY is refused (a new field cannot smuggle content), and any VALUE
    that reproduces the body's raw_text or one of its kwargs values is
    refused (a whitelisted field cannot be filled with content).
    """
    unknown = sorted(set(payload) - _COMPANION_PAYLOAD_KEYS)
    if unknown:
        raise ReplayRefusal(
            "companion_not_content_light",
            f"companion payload carries non-whitelisted fields {unknown}; a "
            "companion is hashes, ids and clocks — the content exists "
            "exactly once in the body and durably in the sidecar",
        )

    forbidden = set()
    raw_text = record.get("raw_text")
    if isinstance(raw_text, str) and raw_text:
        forbidden.add(raw_text)
    for key, value in (record.get("kwargs") or {}).items():
        # The RELOCATED authority values are identity and clocks, not
        # content: submission_id IS the body's name and the companion
        # cannot annotate a body without naming it. Caught by this
        # module's own test before any seat saw it — the first cut
        # refused every companion it built, because the record's
        # kwargs carry submission_id and the payload must too.
        if key in _RELOCATED_AUTHORITY:
            continue
        if isinstance(value, str) and value:
            forbidden.add(value)

    def walk(node, path):
        if isinstance(node, dict):
            for k, v in node.items():
                walk(v, f"{path}.{k}")
        elif isinstance(node, (list, tuple)):
            for i, v in enumerate(node):
                walk(v, f"{path}[{i}]")
        elif isinstance(node, str) and node in forbidden:
            raise ReplayRefusal(
                "companion_not_content_light",
                f"companion field {path.lstrip('.')} reproduces content from "
                "the body; copying it here would make the companion's "
                "truthful taint 'original + self_generated', which the "
                "frozen system_event vocabulary cannot express",
            )

    walk(payload, "")


def build_companion(
    *,
    record: dict,
    body_submission_id: str,
    body_row: tuple,
    run_id: str,
    replayed_at: float,
) -> dict:
    """One content-light provenance companion for an OBSERVED body commit.

    ``body_row`` is ``(turn_id, chain_position, chain_hash,
    privacy_access)`` read from the committed row — this pass runs against
    an observation, never an assumption (ninth round Q-C, and standing
    block 7).

    NOT a child: ``parent_submission_id`` is None and stays None. The
    Claude seat's executed RED control in round nine showed that a
    ``parent_submission_id`` on a companion DOES become a stored
    ``parent_turn_id``, which surfaces inside conversation spans and reads
    as dialogue. "Replay ordering and autobiographical relationship are
    different facts."

    ``privacy_access`` is INHERITED from the body: a note about a turn must
    never be more visible than the turn it annotates. That is a protection
    label, the opposite of the content smuggling Q-D refuses.
    """
    turn_id, chain_position, chain_hash, privacy_access = body_row

    payload = {
        "event": "dead_letter_replay",
        "manifest_run_id": run_id,
        "body_submission_id": body_submission_id,
        "body_turn_id": turn_id,
        "body_chain_position": chain_position,
        "body_chain_hash": chain_hash,
        "body_record_digest": record_digest(record),
        "body_raw_text_sha256": hashlib.sha256(
            (record.get("raw_text") or "").encode("utf-8")
        ).hexdigest(),
        "body_kwargs_sha256": hashlib.sha256(
            json.dumps(
                record.get("kwargs") or {}, sort_keys=True,
                separators=(",", ":"), ensure_ascii=True, default=str,
            ).encode("utf-8")
        ).hexdigest(),
        # Split clocks. The body's lived time is the dead-letter ts, and
        # this field NAMES it as the custody proxy it is (standing block
        # 6: the ts is failure-custody time, not lived time). The record
        # itself therefore says how good its own clock is, instead of
        # presenting a proxy as a measurement.
        "body_submitted_at": record.get("ts"),
        "body_submitted_at_source": "dead_letter_custody_ts",
        "dead_lettered_at": record.get("ts"),
        "dead_letter_stage": record.get("stage"),
        # Never backdated: the companion happened NOW.
        "replayed_at": replayed_at,
        "source_file": record.get("source_file"),
        # NO per-row delivery field, deliberately (Claude council seat,
        # 2026-08-26, and its argument is the one that decides it): a
        # field whose value is constant across every row that could ever
        # carry it does not describe this row — it advertises a
        # discriminating capability the substrate does not have, and by
        # appearing on replayed rows ALONE it implies by omission that
        # every other row has delivery evidence. That is nouns-as-proofs
        # wearing a humility costume. The limitation is a fact about the
        # RUN and lives at run level; the companion carries only its
        # NAMES, so the limit is durable and chain-covered without any
        # row claiming an assessment nobody made.
        "limitations": [limit["name"] for limit in _STANDING_LIMITATIONS],
    }
    _refuse_copied_content(payload, record)

    return {
        "submission_id": companion_submission_id(body_submission_id),
        "submitted_at": replayed_at,
        "producer": _PRODUCER,
        "turn_kind": "system_event",
        "raw_text": json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        ),
        "kwargs": {
            "surface": "system",
            "raw_surface": _PRODUCER,
            "taint_labels": ["self_generated"],
            "privacy_access": privacy_access,
        },
        "parent_submission_id": None,
    }


# ------------------------------------------------------------- the manifest

def build_manifest(db_path: str, *, role: str) -> dict:
    """Build the single-use INTEGRITY MANIFEST for one apply run.

    Tenth round, adopting Codex's binding shape: run id, tree identity,
    target-ledger realpath + instance anchor + pre-apply chain head, the
    FULL census with dispositions and canonical record digests, the
    classifier params, and the machine-derived selected set. The outcome
    map is filled by :func:`apply`.

    It records WHO ran it and in what ROLE as FACT and carries NO consent
    semantics — enforced structurally by :func:`_refuse_consent_semantics`,
    not promised in prose. There is no ``approved`` field to set, and one
    cannot be added: the constructor refuses consent-shaped keys anywhere
    in the document.

    The SELECTED SET is machine-derived from dispositions alone and is
    never an argument. There is no sid-omit parameter and no per-row
    switch — a caller cannot express a preference about one utterance,
    which is what "taste is inexpressible" has to mean in code.
    """
    census = classify(db_path)
    records = {r["event_id"]: r for r in _records(db_path)[0]}

    entries = []
    for row in census["records"]:
        record = records.get(row["event_id"])
        entry = dict(row)
        entry["record_digest"] = (
            record_digest(record) if record is not None else None
        )
        entries.append(entry)

    # Kind-blind by construction: turn_kind is recorded in the census as a
    # FACT and never consulted here. Selection reads dispositions only.
    selected_bodies = [
        e["event_id"] for e in entries if e["disposition"] == "replayable"
    ]
    selected_companions = [
        e["event_id"] for e in entries if e["disposition"] == "companion_owed"
    ]

    manifest = {
        "manifest_version": MANIFEST_VERSION,
        "run_id": uuid.uuid4().hex,
        "built_at": time.time(),
        "operator": _operator_identity(role),
        "tree": _tree_identity(),
        "target_ledger": {
            "realpath": os.path.realpath(db_path),
            # The ledger INSTANCE, not the path: a restored-from-backup or
            # re-created ledger at the same path is a different instance
            # and every digest in this census is meaningless against it.
            "instance_anchor": _meta(db_path, "genesis_hash"),
            "pre_apply_chain_head": _meta(db_path, "last_chain_hash"),
            "spool_root": None,  # filled below, after the import
        },
        "classifier": {
            "window_s": WINDOW_S,
            "companion_sid_domain": _COMPANION_SID_DOMAIN.decode("ascii"),
        },
        "census": entries,
        "census_counts": census["counts"],
        "selected": {
            "bodies": selected_bodies,
            "companions": selected_companions,
            "derivation": (
                "machine-derived from classify() dispositions alone: "
                "'replayable' → body pass, 'companion_owed' → companion "
                "pass. turn_kind is recorded as fact and never consulted. "
                "There is no per-record switch: refused/unknown_category/"
                "unverified/identity_conflict stay evidence, and "
                "possibly_committed waits for the evidence lane — review "
                "adds EVIDENCE; preference or regret can never resolve it."
            ),
        },
        "limitations": list(_STANDING_LIMITATIONS),
        "outcomes": None,
    }
    from core.ledger import spool

    manifest["target_ledger"]["spool_root"] = spool.default_spool_root(db_path)
    _refuse_consent_semantics(manifest)
    return manifest


def write_manifest(db_path: str, manifest: dict) -> str:
    """Persist a manifest atomically beside the ledger. Returns its path."""
    _refuse_consent_semantics(manifest)
    root = Path(manifest_root(db_path))
    root.mkdir(parents=True, exist_ok=True)
    os.chmod(root, 0o700)
    name = f"{manifest['run_id']}.manifest.json"
    payload = (
        json.dumps(manifest, sort_keys=True, indent=2, ensure_ascii=True) + "\n"
    ).encode("utf-8")
    tmp = root / f".tmp-{name}"
    fd = os.open(str(tmp), os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600)
    try:
        view = memoryview(payload)
        while view:
            view = view[os.write(fd, view):]
        os.fsync(fd)
    finally:
        os.close(fd)
    final = root / name
    os.replace(tmp, final)
    dfd = os.open(str(root), os.O_RDONLY)
    try:
        os.fsync(dfd)
    finally:
        os.close(dfd)
    return str(final)


# ----------------------------------------------------------------- apply

def _committed_body_row(db_path: str, submission_id: str):
    """(turn_id, chain_position, chain_hash, privacy_access) for a
    committed submission, or None. Read-only, mode=ro: the apply path runs
    in whatever process the operator is in and must never become a stray
    writer performing WAL recovery."""
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except sqlite3.Error:
        return None
    try:
        return conn.execute(
            "SELECT turn_id, chain_position, chain_hash, privacy_access "
            "FROM turns WHERE submission_id = ?",
            (submission_id,),
        ).fetchone()
    except sqlite3.Error:
        return None
    finally:
        conn.close()


def _consume_manifest(manifest_path: str, run_id: str) -> str:
    """Consume the manifest BEFORE the first mutation.

    Single-use is the tenth round's word. Consuming at the START rather
    than the end is what makes it true under a crash: a run killed
    mid-apply cannot have its manifest re-fed, because the document that
    authorized it is already spent. Recovery is a NEW census — which is
    correct, since after a partial apply the world has moved and the old
    census is stale by definition.

    ``os.replace`` is atomic, so the manifest is either live or spent;
    there is no observable half-consumed state.
    """
    src = Path(manifest_path)
    spent = src.with_name(f"{src.name}.consumed-{run_id}")
    try:
        os.replace(src, spent)
    except OSError as e:
        raise ReplayRefusal(
            "manifest_not_consumable",
            f"could not consume the manifest at {manifest_path!r}: {e!r}; "
            "refusing to mutate under a document that may be reused",
        )
    dfd = os.open(str(src.parent), os.O_RDONLY)
    try:
        os.fsync(dfd)
    finally:
        os.close(dfd)
    return str(spent)


def apply(db_path: str, manifest_path: str) -> dict:
    """Apply one integrity manifest: the body pass, then the companion
    pass against OBSERVED commits.

    Publishes envelopes; it does NOT commit. The owner's drainer is the
    only thing that ever writes to the ledger, so this organ — like
    reconcile before it — is an owner CLIENT and never constructs a
    writer. Pre-birth that means the bodies wait in custody, visibly, and
    the companion pass simply finds nothing committed yet and defers.

    Returns the outcome map. Every record in the selected set appears in
    it exactly once with either a publication or a NAMED refusal; a record
    that silently vanished from a report would be the omission this whole
    theme exists to make impossible.
    """
    from core.ledger import spool

    started_at = time.time()
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    _refuse_consent_semantics(manifest)

    if manifest.get("manifest_version") != MANIFEST_VERSION:
        raise ReplayRefusal(
            "manifest_version_unknown",
            f"manifest_version {manifest.get('manifest_version')!r} is not "
            f"{MANIFEST_VERSION}; refusing to read a document whose meaning "
            "this code does not define",
        )
    run_id = manifest["run_id"]
    target = manifest.get("target_ledger") or {}

    # ---- binding checks. All BEFORE the manifest is consumed, so a
    # refusal here leaves the document usable against the right ledger.
    if target.get("realpath") != os.path.realpath(db_path):
        raise ReplayRefusal(
            "target_ledger_mismatch",
            f"manifest targets {target.get('realpath')!r}, not "
            f"{os.path.realpath(db_path)!r}",
        )
    live_anchor = _meta(db_path, "genesis_hash")
    if live_anchor is None:
        raise ReplayRefusal(
            "ledger_instance_unanchored",
            "the target ledger has no genesis_hash, so this census cannot "
            "be bound to a ledger INSTANCE; an unanchored apply could "
            "publish a census taken against a different ledger's life",
        )
    if target.get("instance_anchor") != live_anchor:
        raise ReplayRefusal(
            "ledger_instance_changed",
            "the ledger's genesis_hash differs from the manifest's: this is "
            "a DIFFERENT ledger instance at the same path (restored, "
            "re-created), and every digest in the census is meaningless "
            "against it",
        )
    live_head = _meta(db_path, "last_chain_hash")
    if target.get("pre_apply_chain_head") != live_head:
        raise ReplayRefusal(
            "stale_chain_head",
            f"the chain advanced since the census (manifest head "
            f"{target.get('pre_apply_chain_head')!r}, live head "
            f"{live_head!r}); the census may no longer describe the ledger",
        )

    spool_root = spool.default_spool_root(db_path)
    lock_root = Path(manifest_root(db_path))
    lock_root.mkdir(parents=True, exist_ok=True)

    # Apply lock, the reconcile precedent: the passes below are
    # check-then-publish, and two concurrent applies could both pass the
    # check. Never inside the spool root — every directory there is
    # treated as a producer by the drainer.
    lock_fd = os.open(
        str(lock_root / "replay.apply.lock"), os.O_CREAT | os.O_RDWR, 0o600
    )
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        os.close(lock_fd)
        raise ReplayRefusal(
            "apply_lock_held",
            "another dead-letter replay apply is running; refusing to risk "
            "two runs publishing against one census",
        )

    outcomes: dict[str, dict] = {}
    try:
        # Re-read the world. The manifest says what WAS; these say what IS.
        live_census = {r["event_id"]: r for r in classify(db_path)["records"]}
        live_records = {r["event_id"]: r for r in _records(db_path)[0]}
        manifest_digests = {
            e["event_id"]: e.get("record_digest")
            for e in manifest.get("census") or []
        }

        consumed_path = _consume_manifest(manifest_path, run_id)

        selected = manifest.get("selected") or {}
        body_ids = list(selected.get("bodies") or [])
        companion_ids = list(selected.get("companions") or [])
        # The outcome map is keyed by identity, so a sid appearing twice
        # would silently overwrite its own outcome — one mutation
        # reported, two attempted. A machine-derived selection cannot
        # produce that (one record, one disposition), but the manifest is
        # a FILE and this is the check that keeps "machine-derived" true
        # of the document actually being applied.
        seen_once = set()
        duplicates = sorted(
            {sid for sid in body_ids + companion_ids
             if sid in seen_once or seen_once.add(sid)}
        )
        if duplicates:
            raise ReplayRefusal(
                "selected_set_not_unique",
                f"the selected set names {duplicates} more than once; an "
                "outcome map keyed by identity would report one mutation "
                "and attempt two",
            )
        for sid in body_ids:
            outcomes[sid] = _apply_one_body(
                db_path, spool_root, sid, live_census, live_records,
                manifest_digests,
            )
        for sid in companion_ids:
            outcomes[sid] = _apply_one_companion(
                db_path, spool_root, sid, run_id, live_census, live_records,
                manifest_digests, expect_disposition="companion_owed",
            )
        # Second pass over the bodies just published: a body that ALREADY
        # committed by the time this pass runs (a live drainer racing us)
        # is owed its companion NOW rather than next run. Against an
        # OBSERVED commit only — a body still pending is deferred, loudly.
        for sid in body_ids:
            if outcomes[sid].get("outcome") != "body_published":
                continue
            outcomes[sid]["companion"] = _apply_one_companion(
                db_path, spool_root, sid, run_id, live_census, live_records,
                manifest_digests, expect_disposition=None,
            )
        completed = True
    finally:
        os.close(lock_fd)
        if not locals().get("completed") and locals().get("consumed_path"):
            # A run that dies mid-apply has already published envelopes
            # and already spent its manifest. Losing the outcome map on
            # top of that would leave an irreversible maintenance
            # operation with no record of what it did — the omission this
            # whole theme exists to make impossible. Recovery is a NEW
            # census either way; this is the evidence it starts from.
            try:
                _write_outcome_receipt(db_path, {
                    "run_id": run_id,
                    "manifest_consumed": consumed_path,
                    "started_at": started_at,
                    "finished_at": time.time(),
                    "outcomes": outcomes,
                    "counts": {},
                    "incomplete": (
                        "this run did not finish; the outcomes below are "
                        "the mutations it had reached"
                    ),
                })
            except Exception:  # noqa: BLE001 — never mask the real failure
                _LOGGER.critical(
                    "dead-letter replay run %s died AND could not write its "
                    "partial outcome receipt; %d mutations are unrecorded",
                    run_id, len(outcomes))

    report = {
        "run_id": run_id,
        "manifest_consumed": consumed_path,
        "started_at": started_at,
        "finished_at": time.time(),
        "outcomes": outcomes,
        "counts": {},
    }
    for entry in outcomes.values():
        key = entry.get("outcome") or entry.get("refusal")
        report["counts"][key] = report["counts"].get(key, 0) + 1
        companion = entry.get("companion")
        if companion:
            ckey = f"companion:{companion.get('outcome') or companion.get('refusal')}"
            report["counts"][ckey] = report["counts"].get(ckey, 0) + 1
    _write_outcome_receipt(db_path, report)
    return report


def _guard_record(sid, live_census, live_records, manifest_digests,
                  expect_disposition):
    """Shared per-mutation guards. Returns the live record, or raises the
    NAMED refusal that stopped this one mutation.

    The manifest is evidence about a moment. These four checks are what
    keep it from becoming an authorization that outlives its evidence.
    """
    live = live_census.get(sid)
    if live is None:
        raise ReplayRefusal(
            "record_vanished",
            "the manifest selected this identity but it is no longer in the "
            "dead-letter census; the sidecar changed under the run",
        )
    if expect_disposition is not None and live["disposition"] != expect_disposition:
        raise ReplayRefusal(
            "disposition_changed",
            f"the census said {expect_disposition!r}; the live classifier "
            f"now says {live['disposition']!r}. Eligibility comes only from "
            "the disposition, and the disposition moved",
        )
    record = live_records.get(sid)
    if record is None:
        raise ReplayRefusal(
            "record_vanished",
            "the record disappeared from the sidecar between census and apply",
        )
    expected = manifest_digests.get(sid)
    if expected is None:
        raise ReplayRefusal(
            "record_digest_absent",
            "the manifest carries no digest for this identity, so the bytes "
            "cannot be bound to the census",
        )
    actual = record_digest(record)
    if actual != expected:
        raise ReplayRefusal(
            "record_digest_mismatch",
            f"the record's bytes changed after the census (censused "
            f"{expected[:12]}…, live {actual[:12]}…); refusing to publish "
            "bytes nobody censused",
        )
    return record


def _apply_one_body(db_path, spool_root, sid, live_census, live_records,
                    manifest_digests) -> dict:
    """Publish ONE reconstructed body. Named refusal or publication."""
    from core.ledger import spool

    try:
        record = _guard_record(
            sid, live_census, live_records, manifest_digests,
            expect_disposition="replayable",
        )
        envelope = build_body_submission(record, db_path)
        published = spool.enqueue_reconstructed(
            spool_root,
            submission_id=envelope["submission_id"],
            submitted_at=envelope["submitted_at"],
            producer=envelope["producer"],
            turn_kind=envelope["turn_kind"],
            raw_text=envelope["raw_text"],
            kwargs=envelope["kwargs"],
            parent_submission_id=envelope["parent_submission_id"],
        )
    except ReplayRefusal as refusal:
        return {"refusal": refusal.name, "detail": refusal.detail}
    except Exception as e:  # noqa: BLE001 — one bad record never aborts a run
        return {"refusal": "body_publish_failed", "detail": repr(e)}
    if not published:
        # No-overwrite is the seam's own guarantee: rewriting a published
        # filename would race an in-flight drain.
        return {"outcome": "body_already_published",
                "detail": "this identity is already published; not republished"}
    return {
        "outcome": "body_published",
        "parent_submission_id": envelope["parent_submission_id"],
        "submitted_at": envelope["submitted_at"],
    }


def _apply_one_companion(db_path, spool_root, sid, run_id, live_census,
                         live_records, manifest_digests,
                         expect_disposition) -> dict:
    """Publish ONE provenance companion, against an OBSERVED body commit.

    Deferral is not failure and is never silent: a body that has not
    drained yet gets ``companion_deferred_body_not_committed`` and the
    next run picks it up through the ``companion_owed`` disposition. That
    is the two-pass shape (ninth round Q-C) and standing block 7's
    recovery in one mechanism rather than two.
    """
    from core.ledger import spool

    try:
        record = _guard_record(
            sid, live_census, live_records, manifest_digests,
            expect_disposition=expect_disposition,
        )
        body_row = _committed_body_row(db_path, sid)
        if body_row is None:
            return {
                "refusal": "companion_deferred_body_not_committed",
                "detail": (
                    "the body has not committed yet, so there is nothing to "
                    "annotate; the companion pass runs against an observed "
                    "commit, never an assumed one"
                ),
            }
        # The body must be OURS. A body committed by the ORIGINAL owner
        # write (timeout-after-commit) gets no replay companion — that
        # would be a false claim that the row was replayed.
        body_state = spool._submission_exists(spool_root, _PRODUCER, sid)
        if body_state not in ("pending", "acked"):
            return {
                "refusal": "companion_refused_body_not_replayed",
                "detail": (
                    "this organ never published a body for this identity, so "
                    f"the committed row is not a replay (body state "
                    f"{body_state!r}); a companion here would claim a replay "
                    "that never happened"
                ),
            }
        envelope = build_companion(
            record=record,
            body_submission_id=sid,
            body_row=body_row,
            run_id=run_id,
            replayed_at=time.time(),
        )
        published = spool.enqueue_reconstructed(
            spool_root,
            submission_id=envelope["submission_id"],
            submitted_at=envelope["submitted_at"],
            producer=envelope["producer"],
            turn_kind=envelope["turn_kind"],
            raw_text=envelope["raw_text"],
            kwargs=envelope["kwargs"],
            parent_submission_id=envelope["parent_submission_id"],
        )
    except ReplayRefusal as refusal:
        return {"refusal": refusal.name, "detail": refusal.detail}
    except Exception as e:  # noqa: BLE001
        return {"refusal": "companion_publish_failed", "detail": repr(e)}
    if not published:
        return {"outcome": "companion_already_published",
                "companion_submission_id": envelope["submission_id"]}
    return {
        "outcome": "companion_published",
        "companion_submission_id": envelope["submission_id"],
        "body_turn_id": body_row[0],
    }


def _write_outcome_receipt(db_path: str, report: dict) -> str:
    """Durable outcome map beside the consumed manifest.

    The tenth round's manifest shape ends with "the final sid→turn→
    companion outcome map". A report returned only to a caller's stdout is
    not a record of a maintenance operation on an irreversible ledger.
    """
    root = Path(manifest_root(db_path))
    root.mkdir(parents=True, exist_ok=True)
    name = f"{report['run_id']}.outcomes.json"
    payload = (
        json.dumps(report, sort_keys=True, indent=2, ensure_ascii=True) + "\n"
    ).encode("utf-8")
    tmp = root / f".tmp-{name}"
    fd = os.open(str(tmp), os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600)
    try:
        view = memoryview(payload)
        while view:
            view = view[os.write(fd, view):]
        os.fsync(fd)
    finally:
        os.close(fd)
    final = root / name
    os.replace(tmp, final)
    dfd = os.open(str(root), os.O_RDONLY)
    try:
        os.fsync(dfd)
    finally:
        os.close(dfd)
    return str(final)
