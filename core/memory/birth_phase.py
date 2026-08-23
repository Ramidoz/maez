"""Single source of truth for "has birth happened?".

Reads ledger meta.birth_event_turn_id — the same key the ledger writer
consults at write time (core/ledger/writer.py). Intentionally a leaf
module (sqlite3 + pathlib only) so core/infra and core/cognition can
import it without cycles.

Missing, zero-byte, or uninitialized ledger → gestation, never an error:
pre-birth the ledger legitimately does not exist yet.

Never caches a "gestation" answer (birth must be visible without a
process restart). A "lived" answer MAY be cached by callers — birth is
irreversible by covenant — but this module itself stays stateless.
"""

from __future__ import annotations

import sqlite3
from collections import namedtuple as _namedtuple
from pathlib import Path

PHASE_GESTATION = "gestation"
PHASE_LIVED = "lived"


def default_ledger_path() -> Path:
    """EXACTLY the daemon's resolution (daemon/maez_daemon.py:186):
    $MAEZ_LEDGER_DB_PATH override, else the canonical paths layer
    (core/infra/paths.memory_dir(), which honors $MAEZ_DATA — the
    shadow-DB-prevention rule; see core/ledger/init.py:17-26).
    Resolved per call, never a module constant, so env overrides and
    sandboxes see the right file."""
    import os

    from core.infra import paths as _paths

    override = os.environ.get("MAEZ_LEDGER_DB_PATH")
    return Path(override) if override else (_paths.memory_dir() / "ledger.db")


def birth_event_turn_id(db_path: str | Path | None = None) -> str | None:
    """The anchored birth turn id, or None while unborn/unreadable."""
    path = Path(db_path) if db_path is not None else default_ledger_path()
    if not path.exists():
        return None
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.Error:
        return None
    try:
        row = conn.execute(
            "SELECT value FROM meta WHERE key = 'birth_event_turn_id'"
        ).fetchone()
    except sqlite3.Error:
        return None
    finally:
        conn.close()
    if row is None:
        return None
    value = (row[0] or "").strip()
    return value or None


def is_born(db_path: str | Path | None = None) -> bool:
    return birth_event_turn_id(db_path) is not None


def current_phase(db_path: str | Path | None = None) -> str:
    return PHASE_LIVED if is_born(db_path) else PHASE_GESTATION


# ─────────────────────────────────────────────────────────────────────────
# S1 — phase truth. Theme 2, protocol §9 (API), §2/§10 (the resolution
# table), §12.13 (what is blocked).
#
# WHY THIS IS BOLTED ON RATHER THAN REPLACING WHAT IS ABOVE.
#
# Everything above answers `gestation` for any ledger without a readable
# birth anchor — absent, 0-byte, half-migrated, byte-corrupt alike. That is
# not a bug in the old code's own terms; it is the A6 defect Theme 2 exists
# to close: phase silently degrading to gestation, so a damaged ledger
# claims to be an unborn one.
#
# S1 must be able to say `unknown`. But it lands DORMANT: with
# MAEZ_S1_PHASE_TRUTH unset, `current_phase()`, `is_born()` and
# `birth_event_turn_id()` must behave EXACTLY as they did before. T5's
# discriminator is built on precisely that — it runs a partial ledger twice
# and requires the answer to change only when the flag is set. If the old
# surface drifts even slightly, the dormancy proof stops meaning anything.
#
# So: new names, no edits to the old ones.
# ─────────────────────────────────────────────────────────────────────────

PHASE_UNKNOWN = "unknown"

#: Activation. Pinned in §9 before the code that reads it, so T5's gate can
#: bind a forced-on run to a flag that already has a fixed spelling.
ACTIVATION_FLAG = "MAEZ_S1_PHASE_TRUTH"

#: The frozen twelve (§9). T1 asserts phase AND reason per cell, so this
#: vocabulary is a contract, not an implementation detail.
REASONS = (
    "absent",              # no file at the resolved path
    "uninitialized_empty", # the file exists and is 0 bytes
    "structural",          # connectable, but not the shipped structure
    "corrupt",             # unreadable as a database
    "meta_absent",         # structurally whole, no birth anchor -> gestation
    "joined",              # anchor pointer joins to its hashed turn -> lived
    "join_failed",         # anchor pointer names a turn that is not there
    "latch_conflict",      # a latch exists where the ledger says it cannot
    "latch_torn",          # latch segment half-published or truncated
    "latch_foreign",       # latch bound to another path or genesis
    "rewind",              # ledger behind the latched high-water mark
    "io_error",            # the resolver could not read what it needed
)

#: §12.13, as ruled: the latch subsystem is blocked until the production
#: writer topology is decided and T2 witnesses it. The branches that would
#: publish or interpret a latch are named and fail closed rather than
#: quietly returning something plausible — a stub that guesses is worse than
#: one that refuses, because the guess would be witnessed as truth.
LATCH_BLOCKED_REASON = (
    "birth_latch is blocked by S1 protocol §12.13 until the production "
    "writer topology is ruled (S2 open item O-1) and T2 witnesses it"
)


class PhaseResult(_namedtuple("PhaseResult", ("phase", "reason"))):
    """(phase, reason). §9 pins both fields; T1 asserts both."""
    __slots__ = ()


class PhaseUnknownRefusal(RuntimeError):
    """A consumer was asked to stamp a phase the resolver cannot vouch for.

    §4's contract: on `unknown`, a census consumer refuses and writes
    nothing. Silent success, or a `gestation` stamp, is a kill.
    """


def s1_enabled() -> bool:
    """Read at call time, never cached — a flag flip must not need a restart."""
    import os
    return os.environ.get(ACTIVATION_FLAG) == "1"


def _expected_tables() -> frozenset[str]:
    """The v1 shipped structure (protocol §9's T6 inventory).

    S1 lands before S2, so `gestation` is judged against migrations
    0001–0005 as shipped. The list is re-frozen when S2's migrations land.
    """
    return frozenset({
        "audit_trace_lineage", "claim_judgements", "claims", "meta",
        "model_swaps", "schema_migrations", "turns",
    })


def resolve(db_path=None) -> PhaseResult:
    """The S1 resolver. Latch-independent branches only (§12.13).

    Dormant unless MAEZ_S1_PHASE_TRUTH=1, in which case it answers exactly
    as the pre-S1 surface did, so that flags-off behaviour is unchanged.
    """
    import os
    import sqlite3 as _sqlite3

    path = Path(db_path) if db_path is not None else default_ledger_path()

    if not s1_enabled():
        # Dormant: mirror the legacy answer, and say why in the reason so a
        # report can tell dormancy from a real classification.
        return PhaseResult(current_phase(path), "dormant")

    # 1. absence and emptiness are provably pre-birth: no structure exists
    #    that could misreport anything (protocol §2's doctrine note).
    if not path.exists():
        return PhaseResult(PHASE_GESTATION, "absent")
    try:
        if path.stat().st_size == 0:
            return PhaseResult(PHASE_GESTATION, "uninitialized_empty")
    except OSError:
        return PhaseResult(PHASE_UNKNOWN, "io_error")

    # 2. from here the file claims to be a database, so it must prove it.
    try:
        conn = _sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except _sqlite3.Error:
        return PhaseResult(PHASE_UNKNOWN, "io_error")
    try:
        try:
            names = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
        except _sqlite3.DatabaseError:
            return PhaseResult(PHASE_UNKNOWN, "corrupt")

        missing = _expected_tables() - names
        if missing:
            return PhaseResult(PHASE_UNKNOWN, "structural")

        # A table set can be complete while the pages underneath are not.
        # Counting rows is NOT enough: the T1 F-D2 fixture corrupts 16 bytes
        # at offset 4096, and SELECT COUNT(*) on turns and meta never reads
        # that page — the resolver answered `gestation, meta_absent` on a
        # damaged ledger, which is exactly the misreport this slice exists to
        # prevent. quick_check walks the pages; it costs 0.2 ms on a healthy
        # store, and correctness here is worth far more than that.
        try:
            conn.execute("PRAGMA quick_check").fetchall()
        except _sqlite3.DatabaseError:
            return PhaseResult(PHASE_UNKNOWN, "corrupt")

        # 3. the birth anchor.
        try:
            row = conn.execute(
                "SELECT value FROM meta WHERE key = 'birth_event_turn_id'"
            ).fetchone()
        except _sqlite3.DatabaseError:
            return PhaseResult(PHASE_UNKNOWN, "corrupt")

        anchor = (row[0] or "").strip() if row else ""
        if not anchor:
            return PhaseResult(PHASE_GESTATION, "meta_absent")

        # The pointer is a convenience; the truth is the hashed row. A
        # pointer that names no turn is exactly the F-X case, and answering
        # `lived` on it would be the misdating this theme exists to prevent.
        try:
            hit = conn.execute(
                "SELECT 1 FROM turns WHERE turn_id = ?", (anchor,)).fetchone()
        except _sqlite3.DatabaseError:
            return PhaseResult(PHASE_UNKNOWN, "corrupt")
        if hit is None:
            return PhaseResult(PHASE_UNKNOWN, "join_failed")

        return PhaseResult(PHASE_LIVED, "joined")
    finally:
        conn.close()


VALID_STAMPS = (PHASE_GESTATION, PHASE_LIVED)


def phase_for_stamp(db_path=None, *, supplied=None, consumer=None) -> str:
    """The one gate every census consumer calls before stamping a phase.

    Sixteen constructs write `memory_phase`. If each decided for itself when
    to trust the resolver they would drift, and T3 would be witnessing
    sixteen different contracts. One helper, one contract:

        dormant  -> the legacy answer, unchanged, always, never raising
        enabled  -> gestation/lived pass through; unknown REFUSES
        supplied -> revalidated: a caller may narrow, never assert `lived`
                    while the gate says otherwise (§4)

    Raises:
        PhaseUnknownRefusal: the resolver cannot vouch for a phase. §4 is
            explicit that swallowing this and stamping `gestation` anyway is
            a kill -- it is the A6 defect wearing the fix's clothes.
        ValueError: the caller asserted a phase the gate contradicts, or a
            phase outside the vocabulary.
    """
    if supplied is not None and supplied not in VALID_STAMPS:
        raise ValueError(
            f"{consumer or 'caller'}: {supplied!r} is not a phase; "
            f"expected one of {VALID_STAMPS}")

    if not s1_enabled():
        # Dormant. Return exactly what the pre-S1 code would have written,
        # including a caller's own choice. Nothing here may change behaviour
        # or T5's discriminator stops being able to detect this guard at all.
        return supplied if supplied is not None else current_phase(db_path)

    result = resolve(db_path)

    if result.phase == PHASE_UNKNOWN:
        raise PhaseUnknownRefusal(
            f"{consumer or 'consumer'}: refusing to stamp a phase — the "
            f"resolver reads unknown ({result.reason}). Writing 'gestation' "
            f"here would assert something no longer true of this ledger."
        )

    if supplied is None:
        return result.phase

    # Narrowing is allowed; asserting past the gate is not. `lived` while the
    # gate says `gestation` is the misdating this theme exists to prevent.
    if supplied == PHASE_LIVED and result.phase != PHASE_LIVED:
        raise ValueError(
            f"{consumer or 'caller'}: supplied memory_phase='lived' while the "
            f"gate reads {result.phase!r} ({result.reason}); a caller may "
            f"narrow, never assert")
    return supplied
