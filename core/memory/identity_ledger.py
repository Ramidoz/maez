# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
r"""
identity_ledger.py — A-core #5, Track A.

Durable append-only ledger of coarse structural events that affect
"am I still me?" for Maez. This is the answer to: if Maez shuts down
tonight, swaps brain model tomorrow, and comes back up, can the
post-swap Maez tell whether it is the same being as the pre-swap one,
or a descendant, or something broken? The ledger is how.

SCOPE (Track A)
---------------
- Two producers only:
    1. Mechanical startup detector in daemon/maez_daemon.py. Computes
       the current identity fingerprint, compares it to the fingerprint
       stored with the latest ledger event, and writes a new 'same'
       event if the fingerprint changed.
    2. Explicit `record_event()` API for Track A birth (future) and
       any deliberate identity-affecting transition.
- Track A producers only ever write `severity='same'`. The schema
  supports 'descendant' and 'broken' so later tracks can produce them
  without migration, but nothing in Track A writes those values.
- One reader: daemon startup. The daemon stores
  `self.continuity_id = ledger.current_continuity_id()` at init and
  uses it nowhere else in Track A. No Telegram commands, no perception
  integration, no temperament coupling. Those come later tracks.

FINGERPRINT (Track A narrow shape)
----------------------------------
Only three fields are load-bearing in Track A:

    {
        "base_model": <MAEZ_LLAMACPP_MODEL env or 'gemma-4-26b'>,
        "lora_hash":  <sha256 of current LoRA file, or None>,
        "soul_hash":  <sha256 of config/soul.md>,
    }

Code hashes are intentionally excluded during Track A — the codebase
is being edited on almost every commit and including code hashes
would turn every daemon restart into a 'code_change' identity event,
duplicating the builder-mode direct-edit log with worse filtering.
Code hashes can return to the fingerprint post-Track-A when the
codebase stabilizes and a code change actually means something
structural.

All three hashes use SHA-256 for consistency across the fingerprint
family. (This is not coupled to the existing `_soul_hash` MD5 in
daemon/maez_daemon.py — that's a hot-reload change-detector, not an
identity fingerprint, and we leave it alone.)

COMPOSITION WITH CONTINUITY CAPSULE
-----------------------------------
Adjacent, not nested. The continuity capsule (core/continuity.py)
answers "what was I doing when I shut down?" — ephemeral state that
archives after the orientation window. The identity ledger answers
"am I still me across that transition?" — durable, append-only,
never archived. The two cross-reference via the `current_continuity_id`
field that `build_capsule()` reads from this module.

SCHEMA
------
CREATE TABLE identity_ledger (
    event_id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ts                    REAL    NOT NULL,
    event_type            TEXT    NOT NULL,
    continuity_id         TEXT    NOT NULL,
    parent_continuity_id  TEXT,
    severity              TEXT    NOT NULL,
    reason                TEXT    NOT NULL DEFAULT '',
    evidence_json         TEXT    NOT NULL DEFAULT '{}',
    fingerprint_json      TEXT    NOT NULL DEFAULT '{}'
)

Allowed `event_type` values:
    'gestation_boot'  — pre-birth seeded first event. Explicit name
                        to avoid confusion with the later 'birth'
                        event that marks gestation→lived transition.
    'birth'           — the transition from gestation-phase to
                        lived-phase memory. Produced via explicit
                        record_event API in the future.
    'brain_swap'      — base_model change.
    'lora_swap'       — lora_hash change.
    'soul_change'     — soul_hash change.
    'code_change'     — reserved; NOT produced in Track A.
    'memory_change'   — reserved; future memory-layer events.
    'restore'         — reserved; future restore-from-backup events.
    'other'           — catch-all for explicit-API events that don't
                        fit the above.

Allowed `severity` values:
    'same'            — Track A producers only write this. The being
                        is in the same continuity lineage as the
                        previous event.
    'descendant'      — schema-supported, not produced in Track A.
                        For future: substantial change but lineage
                        is preserved (new continuity_id, parent set).
    'broken'          — schema-supported, not produced in Track A.
                        For future: lineage is broken (restore from
                        backup, etc). New continuity_id, parent None.

INVARIANTS
----------
- Append-only. No UPDATE or DELETE paths exist in this module.
- A fresh ledger is seeded with exactly one 'gestation_boot' row at
  first init. All subsequent events reference that lineage.
- `record_event()` is the ONLY write path. The daemon startup detector
  calls it internally.
- `current_continuity_id()` returns the continuity_id of the latest
  event. If the ledger is empty (shouldn't happen post-init), it
  returns None.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import secrets
import sqlite3
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger("maez")


# ══════════════════════════════════════════════════════════════════════
#  CONSTANTS
# ══════════════════════════════════════════════════════════════════════

def _default_identity_ledger_path() -> Path:
    override = os.environ.get("MAEZ_IDENTITY_LEDGER_PATH")
    if override:
        return Path(override)
    try:
        from core.paths import memory_dir as _memory_dir
        return _memory_dir() / "identity_ledger.db"
    except Exception:
        return Path(__file__).resolve().parent.parent.parent / "memory" / "identity_ledger.db"


DEFAULT_DB_PATH = _default_identity_ledger_path()


def _default_soul_path() -> Path:
    try:
        from core.paths import soul_combined_path as _soul
        return _soul()
    except Exception:
        return Path(__file__).resolve().parent.parent.parent / "config" / "soul.md"


_DEFAULT_SOUL_PATH = _default_soul_path()

# Allowed event_type values. Kept as a set for O(1) validation.
EVENT_TYPES = frozenset({
    "gestation_boot",
    "birth",
    "brain_swap",
    "lora_swap",
    "soul_change",
    "code_change",
    "memory_change",
    "restore",
    "other",
})

SEVERITIES = frozenset({"same", "descendant", "broken"})

# Track A discipline: producers in this module only ever write 'same'.
# Other severities are schema-supported for later tracks but rejected
# here as a safety rail during Track A. Post-Track-A this constant
# will be removed.
_TRACK_A_WRITABLE_SEVERITIES = frozenset({"same"})


# ══════════════════════════════════════════════════════════════════════
#  SCHEMA — migration-safe split (table, then indexes)
# ══════════════════════════════════════════════════════════════════════

_SCHEMA_TABLE = """
CREATE TABLE IF NOT EXISTS identity_ledger (
    event_id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ts                    REAL    NOT NULL,
    event_type            TEXT    NOT NULL,
    continuity_id         TEXT    NOT NULL,
    parent_continuity_id  TEXT,
    severity              TEXT    NOT NULL,
    reason                TEXT    NOT NULL DEFAULT '',
    evidence_json         TEXT    NOT NULL DEFAULT '{}',
    fingerprint_json      TEXT    NOT NULL DEFAULT '{}'
);
"""

_SCHEMA_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_identity_ts           ON identity_ledger(ts);
CREATE INDEX IF NOT EXISTS idx_identity_event_type   ON identity_ledger(event_type);
CREATE INDEX IF NOT EXISTS idx_identity_continuity   ON identity_ledger(continuity_id);
"""


# ══════════════════════════════════════════════════════════════════════
#  FINGERPRINT
# ══════════════════════════════════════════════════════════════════════

def _sha256_file(path: Path) -> str | None:
    """SHA-256 of a file's bytes. Returns None if the file is missing or
    unreadable. Never raises."""
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except (OSError, IOError):
        return None


def compute_identity_fingerprint(
    soul_path: Path | str | None = None,
    lora_path: Path | str | None = None,
) -> dict[str, Any]:
    """Compute the Track A identity fingerprint.

    Three fields:
      - base_model: from MAEZ_LLAMACPP_MODEL env (default 'gemma-4-26b')
      - lora_hash:  SHA-256 of the file at lora_path, or MAEZ_LORA_PATH
                    env, or None if neither is set / file missing.
      - soul_hash:  SHA-256 of config/soul.md (or provided path),
                    or None if missing.

    Returns a dict suitable for JSON serialization. Never raises.
    """
    base_model = os.environ.get("MAEZ_LLAMACPP_MODEL", "gemma-4-26b")

    soul = Path(soul_path) if soul_path else _DEFAULT_SOUL_PATH
    soul_hash = _sha256_file(soul)

    lora_p: Path | None = None
    if lora_path:
        lora_p = Path(lora_path)
    else:
        env_lora = os.environ.get("MAEZ_LORA_PATH")
        if env_lora:
            lora_p = Path(env_lora)
    lora_hash = _sha256_file(lora_p) if lora_p else None

    return {
        "base_model": base_model,
        "lora_hash":  lora_hash,
        "soul_hash":  soul_hash,
    }


def _fingerprint_diff_reason(old: dict, new: dict) -> tuple[str, str]:
    """Given two fingerprints, return (event_type, reason) describing
    what changed. Assumes the two dicts are different."""
    if old.get("base_model") != new.get("base_model"):
        return ("brain_swap",
                f"base_model {old.get('base_model')} -> {new.get('base_model')}")
    if old.get("lora_hash") != new.get("lora_hash"):
        a = (old.get("lora_hash") or "none")[:12]
        b = (new.get("lora_hash") or "none")[:12]
        return ("lora_swap", f"lora_hash {a} -> {b}")
    if old.get("soul_hash") != new.get("soul_hash"):
        a = (old.get("soul_hash") or "none")[:12]
        b = (new.get("soul_hash") or "none")[:12]
        return ("soul_change", f"soul_hash {a} -> {b}")
    return ("other", "fingerprint changed in an unrecognized field")


def _new_continuity_id() -> str:
    """Fresh 128-bit hex continuity identifier."""
    return secrets.token_hex(16)


# ══════════════════════════════════════════════════════════════════════
#  IdentityLedger
# ══════════════════════════════════════════════════════════════════════

class IdentityLedger:
    """Append-only ledger of identity-affecting events. Thread-safe
    enough for Maez's single-daemon shape (new SQLite connection per
    call, per-connection lock is the concurrency primitive)."""

    def __init__(self, db_path: Path | str | None = None):
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()
        self._seed_if_empty()

    # -------------------------------------------------------------- #
    #  Schema + seeding                                               #
    # -------------------------------------------------------------- #

    def _initialize(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(_SCHEMA_TABLE)
            conn.executescript(_SCHEMA_INDEXES)

    def _seed_if_empty(self) -> None:
        """On first init (empty ledger), write exactly one
        'gestation_boot' row so `latest()` always returns something
        post-init. This is bootstrap option (b)."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM identity_ledger"
            ).fetchone()
            if row and row[0] == 0:
                fp = compute_identity_fingerprint()
                cid = _new_continuity_id()
                conn.execute(
                    "INSERT INTO identity_ledger "
                    "(ts, event_type, continuity_id, parent_continuity_id, "
                    " severity, reason, evidence_json, fingerprint_json) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        time.time(),
                        "gestation_boot",
                        cid,
                        None,
                        "same",
                        "first identity ledger initialization",
                        json.dumps({"seeded_by": "IdentityLedger._seed_if_empty"}),
                        json.dumps(fp),
                    ),
                )
                conn.commit()
                logger.info(
                    "Identity ledger seeded with gestation_boot event "
                    "(continuity_id=%s)", cid[:12]
                )

    # -------------------------------------------------------------- #
    #  Writer                                                         #
    # -------------------------------------------------------------- #

    def record_event(
        self,
        *,
        event_type: str,
        severity: str = "same",
        reason: str = "",
        evidence: dict | None = None,
        continuity_id: str | None = None,
        parent_continuity_id: str | None = None,
        fingerprint: dict | None = None,
    ) -> str:
        """Append an event to the ledger. Returns the `continuity_id`
        that was written (useful when auto-generation was requested).

        Auto-generation semantics (as decided in A-core #5 design pass):

          - severity == "same" and continuity_id is None:
                continuity_id = previous event's continuity_id
                parent_continuity_id = previous event's parent (or None)
            That is: staying in the same lineage means inheriting the
            same ID, not forking a new one.

          - severity == "descendant" and continuity_id is None:
                continuity_id = freshly generated
                parent_continuity_id = previous event's continuity_id
                                       (if not explicitly provided)
            Track A does not write this severity, but the semantics
            are defined for later tracks to rely on.

          - severity == "broken" and continuity_id is None:
                continuity_id = freshly generated
                parent_continuity_id = previous event's continuity_id
                                       (if not explicitly provided;
                                       callers are expected to have
                                       explicit knowledge and usually
                                       supply both).

          - Explicit caller values always win over auto-derivation.
        """
        if event_type not in EVENT_TYPES:
            raise ValueError(
                f"unknown event_type {event_type!r} "
                f"(allowed: {sorted(EVENT_TYPES)})"
            )
        if severity not in SEVERITIES:
            raise ValueError(
                f"unknown severity {severity!r} "
                f"(allowed: {sorted(SEVERITIES)})"
            )
        if severity not in _TRACK_A_WRITABLE_SEVERITIES:
            raise ValueError(
                f"severity {severity!r} is schema-supported but Track A "
                f"producers are not allowed to write it. Track A only "
                f"writes 'same'."
            )

        prev = self.latest()

        # Auto-generation
        if continuity_id is None:
            if severity == "same":
                if prev is not None:
                    continuity_id = prev["continuity_id"]
                    if parent_continuity_id is None:
                        parent_continuity_id = prev.get("parent_continuity_id")
                else:
                    continuity_id = _new_continuity_id()
            else:
                # 'descendant' or 'broken' — unreachable in Track A
                # (blocked by _TRACK_A_WRITABLE_SEVERITIES), but the
                # auto-generation semantics are defined here for
                # when that rail comes down.
                continuity_id = _new_continuity_id()
                if parent_continuity_id is None and prev is not None:
                    parent_continuity_id = prev["continuity_id"]

        if fingerprint is None:
            fingerprint = compute_identity_fingerprint()

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO identity_ledger "
                "(ts, event_type, continuity_id, parent_continuity_id, "
                " severity, reason, evidence_json, fingerprint_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    time.time(),
                    event_type,
                    continuity_id,
                    parent_continuity_id,
                    severity,
                    reason or "",
                    json.dumps(evidence or {}),
                    json.dumps(fingerprint),
                ),
            )
            conn.commit()

        logger.info(
            "Identity ledger: %s event recorded (severity=%s, "
            "continuity_id=%s, reason=%s)",
            event_type, severity, continuity_id[:12], reason[:80],
        )
        return continuity_id

    # -------------------------------------------------------------- #
    #  Readers                                                        #
    # -------------------------------------------------------------- #

    def latest(self) -> dict | None:
        """Return the most recent event as a dict, or None if the
        ledger is empty. (Post-init the ledger should never be empty;
        returns None only as a defensive fallback.)"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM identity_ledger "
                "ORDER BY event_id DESC LIMIT 1"
            ).fetchone()
        if not row:
            return None
        return self._row_to_dict(row)

    def current_continuity_id(self) -> str | None:
        """Shortcut for `latest()['continuity_id']`. Returns None if
        the ledger is empty (defensive)."""
        last = self.latest()
        return last["continuity_id"] if last else None

    def recent(self, limit: int = 20) -> list[dict]:
        """Return up to `limit` most recent events, newest first."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM identity_ledger "
                "ORDER BY event_id DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    # -------------------------------------------------------------- #
    #  Helpers                                                        #
    # -------------------------------------------------------------- #

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict:
        d = dict(row)
        try:
            d["evidence"] = json.loads(d.pop("evidence_json") or "{}")
        except (json.JSONDecodeError, TypeError):
            d["evidence"] = {}
            d.pop("evidence_json", None)
        try:
            d["fingerprint"] = json.loads(d.pop("fingerprint_json") or "{}")
        except (json.JSONDecodeError, TypeError):
            d["fingerprint"] = {}
            d.pop("fingerprint_json", None)
        return d


# ══════════════════════════════════════════════════════════════════════
#  Daemon startup detector
# ══════════════════════════════════════════════════════════════════════

def detect_and_record_startup(
    ledger: IdentityLedger,
    soul_path: Path | str | None = None,
    lora_path: Path | str | None = None,
) -> tuple[str, bool]:
    """Daemon-side mechanical detector.

    Computes the current fingerprint, compares it to the fingerprint
    stored with the latest ledger event, and writes a new 'same' event
    if any field changed. Returns (current_continuity_id, wrote_event).

    This is the ONLY mechanical writer in Track A. It is called exactly
    once, from daemon/maez_daemon.py __init__.
    """
    current_fp = compute_identity_fingerprint(
        soul_path=soul_path, lora_path=lora_path
    )
    prev = ledger.latest()
    if prev is None:
        # Post-seed this shouldn't happen, but defensively: record a
        # gestation_boot-ish event under 'other' so there's always a
        # latest to return. We don't use 'gestation_boot' here because
        # that's reserved for the single seeded row.
        cid = ledger.record_event(
            event_type="other",
            severity="same",
            reason="startup detector found empty ledger (defensive)",
            evidence={"fingerprint": current_fp},
            fingerprint=current_fp,
        )
        return cid, True

    prev_fp = prev.get("fingerprint", {}) or {}
    if prev_fp == current_fp:
        return prev["continuity_id"], False

    event_type, reason = _fingerprint_diff_reason(prev_fp, current_fp)
    cid = ledger.record_event(
        event_type=event_type,
        severity="same",
        reason=reason,
        evidence={"previous_fingerprint": prev_fp, "current_fingerprint": current_fp},
        fingerprint=current_fp,
    )
    return cid, True


# ══════════════════════════════════════════════════════════════════════
#  Self-test (python -m core.identity_ledger)
# ══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import tempfile

    _counts = [0, 0]  # passed, failed

    def _assert(cond: bool, label: str) -> None:
        if cond:
            _counts[0] += 1
            print(f"  OK   {label}")
        else:
            _counts[1] += 1
            print(f"  FAIL {label}")

    print("identity_ledger self-test")
    print("-" * 60)

    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "identity_ledger_test.db"

        # -- fresh ledger seeds a gestation_boot row
        L = IdentityLedger(db_path=db)
        latest = L.latest()
        _assert(latest is not None, "fresh ledger has a latest event")
        _assert(latest["event_type"] == "gestation_boot",
                "seeded event is gestation_boot")
        _assert(latest["severity"] == "same",
                "seeded event severity is 'same'")
        _assert(latest["parent_continuity_id"] is None,
                "seeded event has no parent")
        _assert(len(latest["continuity_id"]) == 32,
                "seeded continuity_id is 32 hex chars")

        seed_cid = latest["continuity_id"]

        # -- re-opening the ledger does NOT re-seed
        L2 = IdentityLedger(db_path=db)
        latest2 = L2.latest()
        _assert(latest2["continuity_id"] == seed_cid,
                "reopening ledger preserves the seed continuity_id")
        _assert(len(L2.recent(limit=50)) == 1,
                "reopening ledger leaves exactly one row")

        # -- current_continuity_id matches latest
        _assert(L2.current_continuity_id() == seed_cid,
                "current_continuity_id matches latest event")

        # -- record_event with severity='same' inherits continuity_id
        cid = L2.record_event(
            event_type="soul_change",
            severity="same",
            reason="soul_hash aaa -> bbb",
            evidence={"old": "aaa", "new": "bbb"},
        )
        _assert(cid == seed_cid,
                "severity='same' inherits the previous continuity_id")

        # -- explicit continuity_id wins over auto
        explicit = "deadbeef" * 4  # 32 hex chars
        cid2 = L2.record_event(
            event_type="other",
            severity="same",
            continuity_id=explicit,
            reason="explicit override test",
        )
        _assert(cid2 == explicit,
                "explicit continuity_id beats auto-derivation")

        # -- invalid event_type is rejected
        try:
            L2.record_event(event_type="not_a_real_type", reason="x")
            _assert(False, "invalid event_type should raise")
        except ValueError:
            _assert(True, "invalid event_type raises ValueError")

        # -- invalid severity is rejected
        try:
            L2.record_event(event_type="other", severity="not_a_severity")
            _assert(False, "invalid severity should raise")
        except ValueError:
            _assert(True, "invalid severity raises ValueError")

        # -- Track A rail: 'descendant' is blocked
        try:
            L2.record_event(event_type="other", severity="descendant")
            _assert(False, "Track A should block severity='descendant'")
        except ValueError:
            _assert(True, "Track A blocks severity='descendant'")

        # -- Track A rail: 'broken' is blocked
        try:
            L2.record_event(event_type="other", severity="broken")
            _assert(False, "Track A should block severity='broken'")
        except ValueError:
            _assert(True, "Track A blocks severity='broken'")

        # -- recent() returns events newest-first
        recents = L2.recent(limit=10)
        _assert(len(recents) == 3, "recent() returns 3 rows (seed + 2)")
        _assert(recents[0]["continuity_id"] == explicit,
                "recent()[0] is the newest event")
        _assert(recents[-1]["event_type"] == "gestation_boot",
                "recent()[-1] is the oldest (seed) event")

        # -- fingerprint computation is stable for the same inputs
        fp1 = compute_identity_fingerprint()
        fp2 = compute_identity_fingerprint()
        _assert(fp1 == fp2, "compute_identity_fingerprint is stable")
        _assert(set(fp1.keys()) == {"base_model", "lora_hash", "soul_hash"},
                "fingerprint has exactly the 3 Track A fields")
        _assert("code_hash" not in fp1 and "daemon_hash" not in fp1,
                "fingerprint does not include code hashes (Track A)")

        # -- startup detector: no change means no new event
        db_a = Path(td) / "startup_a.db"
        La = IdentityLedger(db_path=db_a)
        before_count = len(La.recent(limit=100))
        cid_a, wrote_a = detect_and_record_startup(La)
        after_count = len(La.recent(limit=100))
        _assert(wrote_a is False,
                "startup detector writes no event when fingerprint matches")
        _assert(before_count == after_count,
                "startup detector leaves row count unchanged on no-op")
        _assert(cid_a == La.current_continuity_id(),
                "startup detector returns current continuity_id")

        # -- startup detector: soul change triggers a new event
        db_b = Path(td) / "startup_b.db"
        fake_soul = Path(td) / "fake_soul_v1.md"
        fake_soul.write_text("version one of a fake soul")
        Lb = IdentityLedger(db_path=db_b)
        # Prime the fingerprint with the v1 soul by recording an event
        # that carries that fingerprint explicitly.
        fp_v1 = compute_identity_fingerprint(soul_path=fake_soul)
        Lb.record_event(
            event_type="other",
            severity="same",
            reason="prime with v1 soul fingerprint",
            fingerprint=fp_v1,
        )
        primed_cid = Lb.current_continuity_id()
        # Now change the soul and run the detector against v2.
        fake_soul.write_text("version TWO of a fake soul, substantially different")
        cid_b, wrote_b = detect_and_record_startup(Lb, soul_path=fake_soul)
        _assert(wrote_b is True,
                "startup detector writes an event when soul_hash changes")
        _assert(cid_b == primed_cid,
                "severity='same' preserves continuity_id across soul change")
        last_b = Lb.latest()
        _assert(last_b["event_type"] == "soul_change",
                "detected soul change produces event_type='soul_change'")
        _assert("soul_hash" in last_b["reason"],
                "soul_change reason names the soul_hash delta")

        # -- startup detector: base_model change triggers brain_swap
        db_c = Path(td) / "startup_c.db"
        Lc = IdentityLedger(db_path=db_c)
        os.environ["MAEZ_LLAMACPP_MODEL"] = "gemma-4-26b"
        fp_base = compute_identity_fingerprint()
        Lc.record_event(
            event_type="other",
            severity="same",
            reason="prime with base_model=gemma-4-26b",
            fingerprint=fp_base,
        )
        os.environ["MAEZ_LLAMACPP_MODEL"] = "claude-opus-zzzz"
        cid_c, wrote_c = detect_and_record_startup(Lc)
        _assert(wrote_c is True,
                "startup detector writes event on base_model change")
        _assert(Lc.latest()["event_type"] == "brain_swap",
                "base_model change produces event_type='brain_swap'")
        # Restore env so we don't leak into subsequent tests
        os.environ["MAEZ_LLAMACPP_MODEL"] = "gemma-4-26b"

        # -- _row_to_dict unpacks JSON blobs into dicts
        any_event = Lc.latest()
        _assert(isinstance(any_event["fingerprint"], dict),
                "row_to_dict unpacks fingerprint_json into a dict")
        _assert(isinstance(any_event["evidence"], dict),
                "row_to_dict unpacks evidence_json into a dict")

    print("-" * 60)
    print(f"{_counts[0]} passed, {_counts[1]} failed")
    raise SystemExit(0 if _counts[1] == 0 else 1)
