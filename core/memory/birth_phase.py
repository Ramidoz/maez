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


class LatchBlocked(NotImplementedError):
    """resolve() reached a lived-answer branch while the latch is blocked.

    §12.13: raising is the fail-closed seam. Returning `lived` without latch
    creation, or `unknown` with a fabricated reason, would each be a quiet
    lie the witness machinery would then certify.
    """


class PhaseUnknownRefusal(RuntimeError):
    """A consumer was asked to stamp a phase the resolver cannot vouch for.

    §4's contract: on `unknown`, a census consumer refuses and writes
    nothing. Silent success, or a `gestation` stamp, is a kill.
    """


def s1_enabled() -> bool:
    """Read at call time, never cached — a flag flip must not need a restart."""
    import os
    return os.environ.get(ACTIVATION_FLAG) == "1"


# ── the structural fingerprint (protocol §9's frozen T6 inventory) ──────
#
# Gate round 20 executed the nine T6 mutation controls against the first
# version of this resolver, which checked only that seven table NAMES were
# present. Eight of nine mutations still read `gestation` — a dropped index,
# a phantom migration row, a renamed migration, a flipped genesis byte and a
# stale head all sailed through, and a counterfeit database containing
# nothing but the seven names could reach `lived,joined`. "Gestation must be
# proven as hard as lived" (design ND13) is the whole point of this slice;
# a name check proves nothing.
#
# S1 lands before S2, so everything below is the 0001–0005 shipped world and
# is re-frozen when S2's migrations land.

_FROZEN_TABLES = frozenset({
    "audit_trace_lineage", "claim_judgements", "claims", "meta",
    "model_swaps", "schema_migrations", "turns",
})
_FROZEN_TRIGGERS = frozenset({
    "claim_judgements_no_delete", "claim_judgements_no_update",
    "claims_no_delete", "claims_no_update",
    "turns_no_delete", "turns_no_update",
})
_FROZEN_INDEXES = frozenset({
    "idx_claims_extracted_ts", "idx_claims_tenant_turn",
    "idx_judgements_claim_ts", "idx_judgements_provenance",
    "idx_judgements_tenant_ts", "idx_swaps_tenant_ts",
    "idx_turns_audit_trace", "idx_turns_chain_position",
    "idx_turns_kind_ts", "idx_turns_lifecycle_ts", "idx_turns_model",
    "idx_turns_parent", "idx_turns_raw_surface_ts", "idx_turns_surface_ts",
    "idx_turns_tenant_ts",
})
_FROZEN_MIGRATIONS = frozenset({
    "0001_init", "0002_triggers", "0003_add_lifecycle_stage",
    "0004_add_audit_trace_metadata", "0005_add_taint_privacy_chain_position",
})
#: sha256 of the shipped migration FILES (protocol §0). schema_migrations
#: stores only (name, applied_at) pre-S2, so file integrity is checked on
#: disk: the rows must name exactly the shipped set AND the shipped files
#: must still hash to what the protocol froze.
_FROZEN_MIGRATION_FILE_DIGESTS = {
    "0001_init":
        "eb126df1dd8c6ff5e249dab0259582747e3352991468acc936052d728db7ca75",
    "0002_triggers":
        "7aa3876024f45778a67e3e744f4ed5624146e94603cd7dd1e188c56a740fdc38",
    "0003_add_lifecycle_stage":
        "5e0829a501408b5db940a15b47899bd2899eb551da3f5795babe215ea00d9185",
    "0004_add_audit_trace_metadata":
        "69e5f4bc78ac8a81f742c61da49bab022234dfb8647b9977ce3e1812ce77a659",
    "0005_add_taint_privacy_chain_position":
        "5b66deb643d346a7f0b1ff154618b83366b1c7816de7f1d1b7304102c78d7c86",
}
_GENESIS_RAW_TEXT = '{"event":"genesis","schema_version":1}'


def _structural_failure(conn) -> str | None:
    """Return a short description of the first fingerprint failure, or None.

    Every check here answers one question: is this EXACTLY the shipped
    0001–0005 structure with an intact, head-consistent chain? Anything less
    is `unknown` — a half-built or tampered ledger must never pass as a
    clean pre-birth one.
    """
    import hashlib

    def names(kind: str, like: str | None = None) -> set[str]:
        q = "SELECT name FROM sqlite_master WHERE type=?"
        rows = conn.execute(q, (kind,)).fetchall()
        got = {r[0] for r in rows if not r[0].startswith("sqlite_")}
        if like:
            got = {n for n in got if n.startswith(like)}
        return got

    tables = names("table")
    if tables != _FROZEN_TABLES:
        return f"table set {sorted(tables ^ _FROZEN_TABLES)}"
    triggers = names("trigger")
    if triggers != _FROZEN_TRIGGERS:
        return f"trigger set {sorted(triggers ^ _FROZEN_TRIGGERS)}"
    # The FULL index set, not an idx_-prefixed slice: T6 mutation 2 creates
    # `extra_idx`, which a prefix filter is blind to. sqlite_autoindex_* are
    # implementation artifacts of UNIQUE constraints and excluded by the
    # sqlite_ prefix rule already applied in names().
    indexes = names("index")
    if indexes != _FROZEN_INDEXES:
        return f"index set {sorted(indexes ^ _FROZEN_INDEXES)}"

    rows = conn.execute(
        "SELECT name FROM schema_migrations").fetchall()
    migrations = {r[0] for r in rows}
    if migrations != _FROZEN_MIGRATIONS:
        return f"migration rows {sorted(migrations ^ _FROZEN_MIGRATIONS)}"
    mig_dir = Path(__file__).resolve().parents[2] / "core/ledger/migrations"
    for name, want in _FROZEN_MIGRATION_FILE_DIGESTS.items():
        f = mig_dir / f"{name}.sql"
        try:
            got = hashlib.sha256(f.read_bytes()).hexdigest()
        except OSError:
            return f"shipped migration {name} unreadable"
        if got != want:
            return f"shipped migration {name} digest drift"

    g = conn.execute(
        "SELECT turn_id, raw_text FROM turns WHERE chain_position = 0"
    ).fetchone()
    if g is None or g[0] != "genesis" or g[1] != _GENESIS_RAW_TEXT:
        return "genesis projection"

    # Chain verification to head, and head == tip. This is what turns a
    # flipped genesis byte or a stale meta pointer into `unknown` instead of
    # a confident `gestation`.
    from core.ledger import chain as _chain
    cur = conn.execute("SELECT * FROM turns ORDER BY chain_position")
    cols = [d[0] for d in cur.description]
    turn_rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    if _chain.verify_chain(turn_rows):
        return "chain verification"
    tip = turn_rows[-1]["chain_hash"] if turn_rows else None
    meta_head = conn.execute(
        "SELECT value FROM meta WHERE key='last_chain_hash'").fetchone()
    if meta_head is None or tip is None or meta_head[0] != tip:
        return "meta.last_chain_hash != actual tip"
    return None


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
    def _orphan_sidecars() -> bool:
        # A -wal or -shm beside a missing/empty main file means a database
        # EXISTED here and something removed or truncated it mid-flight.
        # Calling that provably-pre-birth would swallow evidence of exactly
        # the rewind/omission story this theme exists to tell.
        return any(path.with_name(path.name + suf).exists()
                   for suf in ("-wal", "-shm"))

    if not path.exists():
        if _orphan_sidecars():
            return PhaseResult(PHASE_UNKNOWN, "io_error")
        return PhaseResult(PHASE_GESTATION, "absent")
    try:
        if path.stat().st_size == 0:
            if _orphan_sidecars():
                return PhaseResult(PHASE_UNKNOWN, "io_error")
            return PhaseResult(PHASE_GESTATION, "uninitialized_empty")
    except OSError:
        return PhaseResult(PHASE_UNKNOWN, "io_error")

    # 2. from here the file claims to be a database, so it must prove it.
    try:
        conn = _sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except _sqlite3.Error:
        return PhaseResult(PHASE_UNKNOWN, "io_error")
    try:
        # Page integrity FIRST. Counting rows is not enough (the F-D2
        # fixture corrupts bytes no COUNT(*) reads), and gate round 20 found
        # something worse in the first fix: quick_check was executed and its
        # RESULT DISCARDED. quick_check reports many corruptions as rows,
        # not exceptions — a database that answered ("page 2 is never used",)
        # still resolved `gestation`. Check the answer, not just survival.
        try:
            qc = conn.execute("PRAGMA quick_check").fetchall()
        except _sqlite3.DatabaseError:
            return PhaseResult(PHASE_UNKNOWN, "corrupt")
        if qc != [("ok",)]:
            return PhaseResult(PHASE_UNKNOWN, "corrupt")

        try:
            failure = _structural_failure(conn)
        except _sqlite3.DatabaseError:
            return PhaseResult(PHASE_UNKNOWN, "corrupt")
        if failure is not None:
            return PhaseResult(PHASE_UNKNOWN, "structural")

        # 3. the birth anchor.
        try:
            row = conn.execute(
                "SELECT value FROM meta WHERE key = 'birth_event_turn_id'"
            ).fetchone()
        except _sqlite3.DatabaseError:
            return PhaseResult(PHASE_UNKNOWN, "corrupt")

        # Coerce: an anchor column can hold an int (SQLite is dynamically
        # typed) and `.strip()` on it crashed the resolver — an unhandled
        # exception from resolve() is worse than any wrong cell.
        anchor = str(row[0]).strip() if row and row[0] is not None else ""
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

        # §12.13, restored after gate round 20: answering `lived` IS the
        # latch-dependent truth claim. T1 cell 13 requires the first lived
        # observation to CREATE the latch, and the latch subsystem is blocked
        # until the writer topology is ruled (S2 O-1) and T2 witnesses it. A
        # `lived` returned here without a latch would be witnessed as truth
        # and would encode the exact allocation assumptions O-1 may
        # invalidate. Fail closed: refuse loudly. Nothing in the unborn
        # world reaches this branch; the first thing that does will be the
        # latch build itself, with this seam as its anchor.
        raise LatchBlocked(LATCH_BLOCKED_REASON)
    finally:
        conn.close()


VALID_STAMPS = (PHASE_GESTATION, PHASE_LIVED)


def phase_for_stamp(db_path=None, *, supplied=None, consumer=None,
                    dormant_default=None) -> str:
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
        #
        # `dormant_default` exists because legacy defaults were NOT uniform
        # (gate round 20, item D): private_thoughts and memory_manager
        # defaulted to current_phase(), but audit_log defaulted to the
        # LITERAL 'gestation' (a Python constant on the direct-edit methods,
        # the SQL column default on record()). On a born ledger those
        # diverge — dormant parity means reproducing each consumer's own
        # legacy answer, not a tidied-up common one.
        if supplied is not None:
            return supplied
        if dormant_default is not None:
            return dormant_default
        return current_phase(db_path)

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
