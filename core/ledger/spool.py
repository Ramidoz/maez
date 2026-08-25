# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Durable admission spool — the ruled transport for NON-OWNER surfaces.

Council rulings 2026-08-24 (four seats): web and the CLI never open the
ledger. They publish one immutable envelope per submission into their
own spool directory; the daemon owner drains. Sockets, if they ever
exist, are a wake-up hint — never a state carrier. In-daemon producers
do NOT ride this (Grok overturn): they write through owner_write_turn.

Mechanics, each chosen against a named failure mode:
- publish = exclusive temp file IN the pending dir (never /tmp:
  PrivateTmp on the units makes a cross-tmpfs rename EXDEV) → file
  fsync → atomic rename to ``<submission_id>.json`` → directory fsync.
  A scanner can never observe a torn envelope.
- filename = client-minted submission_id = the schema UNIQUE key
  (migration 0006). Crash-window redrive resolves by DB membership.
- drain is dependency-aware: a child (parent_submission_id) commits
  only after its parent's turn_id exists — conversation edges are life,
  not drain artifacts. Unsatisfiable parents defer loudly, forever if
  need be; a fabricated parent is worse than a late one.
- ack = chain-bound receipt (turn_id, chain_position, chain_hash)
  written temp→rename, THEN the envelope moves to ``acked/``. Crash
  between the two → redrive → UNIQUE → same turn_id → ack completes.
- refusals (writer §4.2 validation, authority fields, unparseable
  bytes) quarantine to ``refused/`` with an error sidecar — terminal,
  never retried, never silently dropped. The envelope is DATA: the
  admission door validates; it never trusts the file.
- authority is structurally inexpressible: kwargs naming birth_anchor,
  meta_marker_keys, lifecycle stages or identity overrides refuse at
  the door. Birth goes through no transport, ever.

Dormancy: enqueue is pure filesystem (no flag check — an unborn Maez's
surfaces may not even be running); drain_once refuses to touch anything
while MAEZ_LEDGER_WRITES is unset.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import sqlite3
import time
import uuid
from pathlib import Path

from core.ledger.writer import _json_safe

__all__ = [
    "default_spool_root",
    "enqueue",
    "enqueue_reconstructed",
    "drain_once",
    "spool_status",
]

_LOGGER = logging.getLogger("core.ledger.spool")

#: Envelope kwargs a surface may never express. The writer would refuse
#: most of these anyway; refusing at the door keeps the quarantine
#: message honest ("authority") and the writer's own refusals scoped to
#: payload validity.
_AUTHORITY_KWARGS = frozenset(
    {
        "birth_anchor",
        "meta_marker_keys",
        "lifecycle_stage",
        "submission_id",
        "submitted_at",
        "parent_turn_id",
        # Codex validation round (2026-08-24): tenant selection is
        # identity authority — a surface envelope must never write as
        # another tenant.
        "tenant_id",
    }
)

_STATES = ("pending", "acked", "refused")


def default_spool_root(db_path: str) -> str:
    """The spool root beside its ledger: ``<memory>/ledger_spool``.

    The units' ReadWritePaths only cover memory/, and a rename across
    filesystems is EXDEV (trap #1) — the spool must live on the same
    subtree as the db it feeds. One derivation, shared by the daemon's
    drainer and every surface producer, so the two ends can never
    disagree about where the mailbox is.
    """
    return str(Path(os.path.abspath(db_path)).parent / "ledger_spool")


def _dir_fsync(path: Path) -> None:
    fd = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _producer_dirs(spool_root: str, producer: str) -> dict[str, Path]:
    if "/" in producer or producer.startswith("."):
        raise ValueError(f"invalid producer name {producer!r}")
    base = Path(spool_root) / producer
    dirs = {}
    for state in _STATES:
        d = base / state
        d.mkdir(parents=True, exist_ok=True)
        dirs[state] = d
    # Spool dirs are life-bytes (council ruling 1): 0o700, enforced —
    # mkdir alone inherits the ambient umask (usually 022 → 0755).
    for d in (Path(spool_root), base, *dirs.values()):
        os.chmod(d, 0o700)
    return dirs


def _envelope_digest(envelope: dict) -> str:
    """Digest over the WHOLE submission (identity, kwargs, parent — not
    just kind+text). The drainer recomputes and refuses a mismatch, so
    an envelope edited after publication cannot commit as published
    (Codex validation round, 2026-08-24)."""
    core = {
        key: envelope.get(key)
        for key in (
            "submission_id",
            "producer",
            "seq",
            "submitted_at",
            "turn_kind",
            "raw_text",
            "kwargs",
            "parent_submission_id",
        )
    }
    return hashlib.sha256(
        json.dumps(
            core, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        ).encode("utf-8")
    ).hexdigest()


def _atomic_publish(target_dir: Path, name: str, payload: bytes) -> Path:
    tmp = target_dir / f".tmp-{name}"
    # O_TRUNC, deliberately not O_EXCL: temp names are unique per
    # submission, so the only thing that can already exist here is a
    # stale leftover from a process SIGKILLed mid-publish — and O_EXCL
    # would then wedge every redrive of this submission forever (the
    # falsifier's F6 arm caught exactly that). Truncating a dead
    # process's garbage is always safe; no live writer shares this name.
    fd = os.open(str(tmp), os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600)
    try:
        view = memoryview(payload)
        while view:
            written = os.write(fd, view)
            view = view[written:]
        os.fsync(fd)
    finally:
        os.close(fd)
    final = target_dir / name
    os.replace(tmp, final)
    _dir_fsync(target_dir)
    return final


def enqueue(
    spool_root: str,
    *,
    producer: str,
    turn_kind: str,
    raw_text: str | None,
    kwargs: dict,
    parent_submission_id: str | None = None,
) -> str:
    """Durably publish one submission. Returns its submission_id.

    Pure filesystem: never opens the ledger, never checks the writes
    flag (the entry simply waits). Raises on I/O failure — the CALLER
    owns what to do when even durable custody is impossible; silence is
    not an option this layer may choose.
    """
    submission_id = uuid.uuid4().hex
    envelope = {
        "submission_id": submission_id,
        "producer": producer,
        "seq": time.time_ns(),
        "submitted_at": time.time(),
        "turn_kind": turn_kind,
        "raw_text": raw_text,
        "kwargs": _json_safe(kwargs),
        "parent_submission_id": parent_submission_id,
    }
    envelope["payload_digest"] = _envelope_digest(envelope)
    dirs = _producer_dirs(spool_root, producer)
    _atomic_publish(
        dirs["pending"],
        f"{submission_id}.json",
        (json.dumps(envelope, sort_keys=True, separators=(",", ":"),
                    ensure_ascii=True) + "\n").encode("utf-8"),
    )
    return submission_id


def _submission_exists(spool_root: str, producer: str,
                       submission_id: str) -> str | None:
    """Which state dir already holds this submission, if any."""
    for state in _STATES:
        d = Path(spool_root) / producer / state
        if (d / f"{submission_id}.json").exists():
            return state
    return None


def enqueue_reconstructed(
    spool_root: str,
    *,
    submission_id: str,
    submitted_at: float,
    producer: str,
    turn_kind: str,
    raw_text: str | None,
    kwargs: dict,
    parent_submission_id: str | None = None,
) -> bool:
    """Publish a RECONSTRUCTED submission carrying a pre-existing identity
    and its original lived time. Returns False if that identity is
    already published (never overwrite: a filename rewrite races an
    in-flight drain).

    Deliberately NOT optional parameters on :func:`enqueue` (Grok council
    seat, 2026-08-24): teaching the public door to accept a caller-chosen
    ``submission_id``/``submitted_at`` would hand every caller exactly
    the authority the admission door refuses by name, protected only by
    a docstring. Reconstruction is a distinct act with a distinct
    entry point, used by the dead-letter replay organ alone.

    The envelope is otherwise ordinary: the admission door still
    validates it, the digest still covers it, and authority kwargs are
    still refused at drain.
    """
    if not isinstance(submission_id, str) or not submission_id.strip():
        raise ValueError("reconstructed submission_id must be a non-empty string")
    if _submission_exists(spool_root, producer, submission_id):
        return False
    envelope = {
        "submission_id": submission_id,
        "producer": producer,
        "seq": time.time_ns(),
        "submitted_at": submitted_at,
        "turn_kind": turn_kind,
        "raw_text": raw_text,
        "kwargs": _json_safe(kwargs),
        "parent_submission_id": parent_submission_id,
    }
    envelope["payload_digest"] = _envelope_digest(envelope)
    dirs = _producer_dirs(spool_root, producer)
    _atomic_publish(
        dirs["pending"],
        f"{submission_id}.json",
        (json.dumps(envelope, sort_keys=True, separators=(",", ":"),
                    ensure_ascii=True) + "\n").encode("utf-8"),
    )
    return True


def _quarantine(dirs: dict[str, Path], path: Path, error: str) -> None:
    name = path.name
    _atomic_publish(
        dirs["refused"],
        f"{Path(name).stem}.error.json",
        (json.dumps({"error": error, "ts": time.time()}) + "\n").encode(),
    )
    os.replace(path, dirs["refused"] / name)
    _dir_fsync(dirs["refused"])


def _resolve_submission(db_path: str, submission_id: str):
    """(turn_id, chain_position, chain_hash) for a committed submission,
    or None. Read-only: the drainer's lookups must never be writers."""
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except sqlite3.OperationalError:
        return None
    try:
        return conn.execute(
            "SELECT turn_id, chain_position, chain_hash FROM turns"
            " WHERE submission_id = ?",
            (submission_id,),
        ).fetchone()
    finally:
        conn.close()


def _ack(dirs: dict[str, Path], path: Path, submission_id: str,
         db_path: str) -> None:
    resolved = _resolve_submission(db_path, submission_id)
    if resolved is None:
        # Codex validation round (2026-08-24): a receipt with null
        # turn/position/hash is a terminal ack that is NOT chain-bound.
        # Leave the envelope pending — the redrive path re-resolves by
        # identity (UNIQUE) and acks properly next pass.
        raise RuntimeError(
            f"cannot chain-bind ack for {submission_id}: committed turn "
            "not resolvable right now; envelope stays pending for redrive"
        )
    receipt = {
        "submission_id": submission_id,
        "turn_id": resolved[0],
        "chain_position": resolved[1],
        "chain_hash": resolved[2],
        "acked_at": time.time(),
    }
    # Receipt FIRST, then the envelope moves: a crash between the two
    # leaves the envelope pending and the redrive path re-resolves.
    _atomic_publish(
        dirs["acked"],
        f"{submission_id}.receipt.json",
        (json.dumps(receipt, sort_keys=True) + "\n").encode(),
    )
    os.replace(path, dirs["acked"] / path.name)
    _dir_fsync(dirs["acked"])


def drain_once(spool_root: str, db_path: str) -> dict:
    """One owner-side drain pass over every producer. Never raises.

    Runs in the OWNER process only (commits go through owner_commit's
    serialized writer). Returns {"acked", "refused", "deferred"} counts,
    or {"...0, "skipped_disabled": True} while writes are dormant.
    """
    from core.ledger import owner as _owner
    from core.ledger.writes_flag import ledger_writes_enabled

    if not ledger_writes_enabled():
        return {"acked": 0, "refused": 0, "deferred": 0,
                "skipped_disabled": True}

    root = Path(spool_root)
    acked = refused = failed = 0
    entries: list[tuple[dict, Path, dict[str, Path]]] = []
    if root.is_dir():
        for producer_dir in sorted(p for p in root.iterdir() if p.is_dir()):
            dirs = _producer_dirs(spool_root, producer_dir.name)
            for path in sorted(dirs["pending"].iterdir()):
                if path.name.startswith(".tmp-") or not path.name.endswith(".json"):
                    continue
                try:
                    env = json.loads(path.read_text(encoding="utf-8"))
                    sid = env["submission_id"]
                    if not isinstance(sid, str) or f"{sid}.json" != path.name:
                        raise ValueError("submission_id does not match filename")
                except Exception as e:
                    _quarantine(dirs, path, f"unparseable envelope: {e!r}")
                    refused += 1
                    continue
                if env.get("payload_digest") != _envelope_digest(env):
                    _quarantine(
                        dirs, path,
                        "envelope digest mismatch: the submission was "
                        "modified after publication — refusing to commit "
                        "bytes nobody published",
                    )
                    refused += 1
                    continue
                entries.append((env, path, dirs))

    # Dependency-aware order: parents first (submitted_at, then seq as
    # the tiebreak); children defer until their parent's turn_id exists.
    entries.sort(key=lambda t: (t[0].get("submitted_at") or 0,
                                t[0].get("seq") or 0))
    committed: dict[str, str] = {}
    progress = True
    while progress and entries:
        progress = False
        remaining = []
        for env, path, dirs in entries:
            kwargs = dict(env.get("kwargs") or {})
            bad_authority = _AUTHORITY_KWARGS.intersection(kwargs)
            if bad_authority:
                _quarantine(
                    dirs, path,
                    "authority fields are inexpressible through the spool: "
                    f"{sorted(bad_authority)}",
                )
                refused += 1
                progress = True
                continue
            parent_sid = env.get("parent_submission_id")
            if parent_sid:
                parent_tid = committed.get(parent_sid)
                if parent_tid is None:
                    resolved = _resolve_submission(db_path, parent_sid)
                    parent_tid = resolved[0] if resolved else None
                if parent_tid is None:
                    remaining.append((env, path, dirs))  # defer this pass
                    continue
                kwargs["parent_turn_id"] = parent_tid
            outcome, detail = _owner.owner_commit(
                db_path,
                env.get("turn_kind"),
                env.get("raw_text"),
                submission_id=env["submission_id"],
                submitted_at=env.get("submitted_at"),
                **kwargs,
            )
            if outcome == "acked":
                committed[env["submission_id"]] = detail
                try:
                    _ack(dirs, path, env["submission_id"], db_path)
                except Exception as e:
                    # Committed but unacked: the redrive path owns it.
                    _LOGGER.error(
                        "spool ack failed for %s (committed as %s): %r",
                        env["submission_id"], detail, e,
                    )
                acked += 1
                progress = True
            elif outcome == "refused":
                _quarantine(dirs, path, f"writer refused payload: {detail!r}")
                refused += 1
                progress = True
            else:
                _LOGGER.error(
                    "spool commit failed for %s (stays pending): %r",
                    env["submission_id"], detail,
                )
                failed += 1
                remaining.append((env, path, dirs))
        entries = remaining

    report = {"acked": acked, "refused": refused,
              "deferred": len(entries), "failed": failed}
    if report["deferred"]:
        _LOGGER.warning(
            "spool drain deferred %d entries (unsatisfied parents or "
            "transient failures); they stay pending", report["deferred"],
        )
    return report


def run_drainer(
    spool_root: str,
    db_path: str,
    stop_event,
    interval: float = 0.5,
) -> None:
    """Owner-side drain loop: scan at start, then poll on a cadence.

    Poll, never inotify (host inotify scar; a watch is at most a future
    hint). Runs until stop_event is set. Exceptions inside a pass are
    already contained by drain_once; this loop existing is itself part
    of the liveness contract — the daemon starts it whenever writes are
    enabled, and spool_status() is how its health stays visible.
    """
    while not stop_event.is_set():
        drain_once(spool_root, db_path)
        stop_event.wait(interval)


def spool_status(spool_root: str) -> dict:
    """Machine-readable spool state per producer: counts + oldest pending
    age. The liveness contract: a spool nobody drains is a
    silent-omission machine, so this must be surfaced, not logged."""
    root = Path(spool_root)
    out: dict = {"producers": {}, "pending_total": 0,
                 "oldest_pending_ts": None}
    if not root.is_dir():
        return out
    for producer_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        counts = {}
        for state in _STATES:
            d = producer_dir / state
            # Count SUBMISSIONS, not artifacts: receipts and error
            # sidecars live beside the envelopes they describe.
            files = [f for f in d.iterdir()
                     if f.name.endswith(".json")
                     and not f.name.startswith(".tmp-")
                     and not f.name.endswith(".receipt.json")
                     and not f.name.endswith(".error.json")] if d.is_dir() else []
            counts[state] = len(files)
            if state == "pending":
                out["pending_total"] += len(files)
                for f in files:
                    try:
                        ts = json.loads(f.read_text()).get("submitted_at")
                    except (ValueError, OSError):
                        continue
                    if isinstance(ts, (int, float)) and (
                        out["oldest_pending_ts"] is None
                        or ts < out["oldest_pending_ts"]
                    ):
                        out["oldest_pending_ts"] = ts
        out["producers"][producer_dir.name] = counts
    return out
