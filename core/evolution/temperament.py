r"""
temperament.py — A-core #6, Track A.

The temperament skeleton. Eleven named parameters, stored as an
append-only event log with history support, no automatic drift and
no reasoning-loop wiring during Track A. The skeleton exists so the
future drift algorithm (Track B) and future read surfaces (#9
private thoughts, acceptance test, later admin commands) can plug
in without migration.

DESIGN DECISIONS LOCKED BY A-CORE #6 DESIGN PASS
------------------------------------------------
1. **Eleven parameters, canonical order, frozen**. Names from
   docs/governance/BETA_ARCHITECTURE_DECISIONS.md Decision 14. Rename
   is a data migration, so the list is treated as load-bearing.

       1. curiosity      2. caution        3. proactiveness
       4. awareness      5. warmth         6. persistence
       7. directness     8. patience       9. humor
      10. confidence    11. joy           12. empathy

2. **Value range [0.0, 10.0]**. Readable d&d-stat range. NULL means
   "not yet observed" — there are no fixed floors, per Decision 14's
   "no pre-set baselines" rule.

3. **Initial state = NULL / observing**. On first init, no rows exist
   in the table, so current_value() returns None for all 11
   parameters. This is deliberate: the baseline is the user's own
   biography, emerging over lived interaction, NOT a designer-chosen
   midpoint.

4. **Zero automatic drift in Track A**. The only writer is the
   explicit `record_event()` API. No production code in Track A calls
   it; it is reserved for #9 (if #9 needs to write diagnostic state),
   for future drift modules, and for admin paths that don't exist yet.
   The writer is the same shape as IdentityLedger.record_event — a
   tested API contract waiting for its first real caller.

5. **Single append-only table, no current-state cache**. Current
   value for a parameter is the most recent row for that parameter.
   This supports Decision 13 (mourning drift via biography averaging)
   without schema changes — the biography average is a time-integral
   over the history rows.

6. **Only 'explicit_set' is a valid source in Track A**. The `source`
   column exists so future drift signals are auditable the moment
   they land, but the producer-side discipline in Track A is: only
   explicit set events, no shaping signals.

EXPLICITLY NOT IN SCOPE
-----------------------
- Automatic drift algorithm (what shapes which parameter, how much,
  how often). Own design pass when the time comes.
- Wiring into the reasoning loop (temperament biases downstream
  reasoning). Track B.
- Gut feeling fast-path (Decision 15 — post-Track-A).
- Telegram /temperament admin command.
- Biography averaging computation (supported by the schema; computed
  by a later caller when mourning drift becomes live).
- Parameter coupling rules (caution vs curiosity anti-correlation,
  etc.). Not modeled. If later tracks need it, it's policy on top.
- Database-level enforcement of "bonded user only" (Decision 14).
  Stays as producer-side discipline; the `source` column makes
  violations auditable.

COMPOSITION WITH OTHER A-CORE ITEMS
-----------------------------------
- Adjacent to the identity ledger (#5), not nested. Identity answers
  "am I still me across a restart"; temperament answers "what are
  my general reactive tendencies." Different questions, different
  storage, no cross-reference field.
- Readable (but not yet read) by #9 private thoughts seed. When #9
  journals, it may reference current temperament state as read-only
  context. NULL values are a legitimate "I haven't observed this yet"
  signal, not an error.
- Checked (for existence only) by #17 acceptance test.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
from pathlib import Path

logger = logging.getLogger("maez")


# ══════════════════════════════════════════════════════════════════════
#  CONSTANTS
# ══════════════════════════════════════════════════════════════════════

# Resolve via core.paths so the Phase-3 subpackage move (core/temperament.py
# → core/evolution/temperament.py) doesn't silently drop the db in the
# wrong place. MAEZ_TEMPERAMENT_PATH still wins when set.
def _default_temperament_path() -> Path:
    override = os.environ.get("MAEZ_TEMPERAMENT_PATH")
    if override:
        return Path(override)
    try:
        from core.paths import memory_dir as _memory_dir
        return _memory_dir() / "temperament.db"
    except Exception:
        return Path(__file__).resolve().parent.parent.parent / "memory" / "temperament.db"


DEFAULT_DB_PATH = _default_temperament_path()

# The 11 canonical parameter names in their canonical order. This
# tuple is frozen. Renaming any entry is a data migration. Adding a
# 12th parameter is possible without migration (it just becomes a new
# string value in the `parameter` column) but the names listed here
# are what the acceptance test and downstream readers can rely on.
PARAMETER_NAMES: tuple[str, ...] = (
    "curiosity",
    "caution",
    "proactiveness",
    "awareness",
    "warmth",
    "persistence",
    "directness",
    "patience",
    "humor",
    "confidence",
    "joy",
    "empathy",
)

PARAMETER_SET = frozenset(PARAMETER_NAMES)

# Value range. Clamped at write time — out-of-range inputs raise
# ValueError rather than being silently truncated. NULL (None) is the
# sentinel for "not yet observed" and is returned by current_value()
# when no events exist for a parameter.
VALUE_MIN = 0.0
VALUE_MAX = 10.0

# Allowed sources for record_event. Track A producers only use
# 'explicit_set'. Future shaping signals will add their own source
# names (e.g., 'drift:telegram_tone', 'drift:reply_latency') and
# those names will be registered here when the shaping module lands.
ALLOWED_SOURCES = frozenset({
    "explicit_set",
})


# ══════════════════════════════════════════════════════════════════════
#  SCHEMA — migration-safe split (table, then indexes)
# ══════════════════════════════════════════════════════════════════════

_SCHEMA_TABLE = """
CREATE TABLE IF NOT EXISTS temperament_events (
    event_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    ts             REAL    NOT NULL,
    parameter      TEXT    NOT NULL,
    value          REAL    NOT NULL,
    prior_value    REAL,
    source         TEXT    NOT NULL,
    reason         TEXT    NOT NULL DEFAULT '',
    evidence_json  TEXT    NOT NULL DEFAULT '{}'
);
"""

_SCHEMA_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_temp_parameter ON temperament_events(parameter);
CREATE INDEX IF NOT EXISTS idx_temp_ts        ON temperament_events(ts);
CREATE INDEX IF NOT EXISTS idx_temp_source    ON temperament_events(source);
"""


# ══════════════════════════════════════════════════════════════════════
#  Temperament
# ══════════════════════════════════════════════════════════════════════

class Temperament:
    """Append-only temperament event store for Maez.

    Track A discipline: the writer exists and is tested, but no
    production code path in Track A calls it. Readers are available
    for #9 (private thoughts) and #17 (acceptance test) but neither
    of them is wired yet. The daemon instantiates one of these at
    startup and stores the handle; nothing in the reasoning loop
    currently pulls from it.
    """

    def __init__(self, db_path: Path | str | None = None):
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _initialize(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(_SCHEMA_TABLE)
            conn.executescript(_SCHEMA_INDEXES)

    # -------------------------------------------------------------- #
    #  Writer                                                         #
    # -------------------------------------------------------------- #

    def record_event(
        self,
        *,
        parameter: str,
        value: float,
        source: str = "explicit_set",
        reason: str = "",
        evidence: dict | None = None,
    ) -> int:
        """Append a temperament event. Returns the new event_id.

        Raises ValueError if:
          - `parameter` is not one of the 11 canonical names
          - `value` is outside [0.0, 10.0]
          - `source` is not in ALLOWED_SOURCES

        The `prior_value` column is auto-populated from the most
        recent previous event for the same parameter, or NULL if this
        is the first event for that parameter.
        """
        if parameter not in PARAMETER_SET:
            raise ValueError(
                f"unknown parameter {parameter!r} "
                f"(allowed: {list(PARAMETER_NAMES)})"
            )
        try:
            value_f = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"value {value!r} is not a float")
        if not (VALUE_MIN <= value_f <= VALUE_MAX):
            raise ValueError(
                f"value {value_f} out of range "
                f"[{VALUE_MIN}, {VALUE_MAX}]"
            )
        if source not in ALLOWED_SOURCES:
            raise ValueError(
                f"unknown source {source!r} "
                f"(allowed in Track A: {sorted(ALLOWED_SOURCES)})"
            )

        prior = self.current_value(parameter)

        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "INSERT INTO temperament_events "
                "(ts, parameter, value, prior_value, source, reason, evidence_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    time.time(),
                    parameter,
                    value_f,
                    prior,
                    source,
                    reason or "",
                    json.dumps(evidence or {}),
                ),
            )
            event_id = cur.lastrowid
            conn.commit()

        logger.info(
            "Temperament: %s %s -> %.3f (source=%s, event_id=%d, reason=%s)",
            parameter,
            f"{prior:.3f}" if prior is not None else "NULL",
            value_f,
            source,
            event_id,
            (reason or "")[:80],
        )
        return event_id

    # -------------------------------------------------------------- #
    #  Readers                                                        #
    # -------------------------------------------------------------- #

    def current(self) -> dict[str, float | None]:
        """Return a dict mapping each of the 11 parameter names to its
        current value (most recent event), or None if no events exist
        for that parameter yet. All 11 keys are always present.

        This is the primary read surface for #9 (private thoughts) and
        the acceptance test. NULL values are legitimate — they mean
        "not yet observed" per the no-fixed-floors rule, not an error.
        """
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT parameter, value FROM temperament_events "
                "WHERE event_id IN ("
                "  SELECT MAX(event_id) FROM temperament_events GROUP BY parameter"
                ")"
            ).fetchall()
        latest = {p: v for p, v in rows}
        return {name: latest.get(name) for name in PARAMETER_NAMES}

    def current_value(self, parameter: str) -> float | None:
        """Latest value for a single parameter, or None if no events
        exist for that parameter. Raises ValueError on unknown name."""
        if parameter not in PARAMETER_SET:
            raise ValueError(
                f"unknown parameter {parameter!r} "
                f"(allowed: {list(PARAMETER_NAMES)})"
            )
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT value FROM temperament_events "
                "WHERE parameter = ? "
                "ORDER BY event_id DESC LIMIT 1",
                (parameter,),
            ).fetchone()
        return float(row[0]) if row else None

    def history(self, parameter: str, limit: int = 100) -> list[dict]:
        """History of events for a single parameter, newest first.
        Raises ValueError on unknown name. Used by the future
        biography-averaging computation (Decision 13 / mourning drift)
        and by any debugging surface that wants to trace drift."""
        if parameter not in PARAMETER_SET:
            raise ValueError(
                f"unknown parameter {parameter!r} "
                f"(allowed: {list(PARAMETER_NAMES)})"
            )
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM temperament_events "
                "WHERE parameter = ? "
                "ORDER BY event_id DESC LIMIT ?",
                (parameter, int(limit)),
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def recent(self, limit: int = 20) -> list[dict]:
        """Recent events across all parameters, newest first."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM temperament_events "
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
        return d


# ══════════════════════════════════════════════════════════════════════
#  Self-test (python3 -m core.temperament)
# ══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import tempfile

    _counts = [0, 0]

    def _assert(cond: bool, label: str) -> None:
        if cond:
            _counts[0] += 1
            print(f"  OK   {label}")
        else:
            _counts[1] += 1
            print(f"  FAIL {label}")

    print("temperament self-test")
    print("-" * 60)

    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "temperament_test.db"

        # -- canonical name set
        _assert(len(PARAMETER_NAMES) == 12,
                "PARAMETER_NAMES has exactly 12 entries")
        _assert(PARAMETER_NAMES[0] == "curiosity",
                "first parameter is curiosity")
        _assert(PARAMETER_NAMES[-1] == "empathy",
                "last parameter is empathy")
        expected_names = {
            "curiosity", "caution", "proactiveness", "awareness",
            "warmth", "persistence", "directness", "patience",
            "humor", "confidence", "joy", "empathy",
        }
        _assert(set(PARAMETER_NAMES) == expected_names,
                "PARAMETER_NAMES matches Decision 14 + empathy addendum")

        # -- fresh ledger has NULL for every parameter
        T = Temperament(db_path=db)
        cur = T.current()
        _assert(set(cur.keys()) == set(PARAMETER_NAMES),
                "current() returns all 11 parameter keys")
        _assert(all(v is None for v in cur.values()),
                "fresh ledger: all 11 parameters are None (observing)")
        _assert(T.current_value("curiosity") is None,
                "current_value returns None before any events")
        _assert(len(T.recent(limit=100)) == 0,
                "fresh ledger has zero events")

        # -- first write: prior_value should be NULL
        eid1 = T.record_event(
            parameter="warmth",
            value=6.2,
            source="explicit_set",
            reason="self-test seeding warmth",
            evidence={"test": True},
        )
        _assert(isinstance(eid1, int) and eid1 > 0,
                "record_event returns a positive event_id")
        _assert(T.current_value("warmth") == 6.2,
                "current_value reflects the new warmth")
        hist = T.history("warmth")
        _assert(len(hist) == 1, "warmth history has 1 row")
        _assert(hist[0]["prior_value"] is None,
                "first warmth event has prior_value=NULL")
        _assert(hist[0]["evidence"] == {"test": True},
                "evidence_json unpacked into dict")

        # -- second write: prior_value should be the first value
        T.record_event(
            parameter="warmth",
            value=7.5,
            source="explicit_set",
            reason="self-test bumping warmth",
        )
        _assert(T.current_value("warmth") == 7.5,
                "current_value reflects the newer warmth")
        hist = T.history("warmth")
        _assert(len(hist) == 2, "warmth history has 2 rows")
        _assert(hist[0]["value"] == 7.5 and hist[0]["prior_value"] == 6.2,
                "newest warmth row has prior_value=6.2")

        # -- current() returns the new value for warmth, None elsewhere
        cur = T.current()
        _assert(cur["warmth"] == 7.5, "current() returns new warmth")
        _assert(cur["curiosity"] is None,
                "current() still None for untouched curiosity")
        _assert(sum(1 for v in cur.values() if v is not None) == 1,
                "current() has exactly 1 non-None parameter")

        # -- invalid parameter raises
        try:
            T.record_event(parameter="bravery", value=5.0)
            _assert(False, "unknown parameter should raise")
        except ValueError:
            _assert(True, "unknown parameter raises ValueError")

        # -- value below min raises
        try:
            T.record_event(parameter="humor", value=-0.1)
            _assert(False, "value < VALUE_MIN should raise")
        except ValueError:
            _assert(True, "value below VALUE_MIN raises")

        # -- value above max raises
        try:
            T.record_event(parameter="humor", value=10.1)
            _assert(False, "value > VALUE_MAX should raise")
        except ValueError:
            _assert(True, "value above VALUE_MAX raises")

        # -- boundary values accepted
        T.record_event(parameter="humor", value=0.0)
        _assert(T.current_value("humor") == 0.0,
                "value == VALUE_MIN (0.0) is accepted")
        T.record_event(parameter="humor", value=10.0)
        _assert(T.current_value("humor") == 10.0,
                "value == VALUE_MAX (10.0) is accepted")

        # -- invalid source raises (Track A only allows 'explicit_set')
        try:
            T.record_event(
                parameter="warmth",
                value=5.0,
                source="drift:telegram_tone",
            )
            _assert(False, "unknown source should raise in Track A")
        except ValueError:
            _assert(True, "Track A blocks unknown source strings")

        # -- current_value on unknown parameter raises
        try:
            T.current_value("wisdom")
            _assert(False, "current_value on unknown parameter should raise")
        except ValueError:
            _assert(True, "current_value on unknown parameter raises")

        # -- history on unknown parameter raises
        try:
            T.history("wisdom")
            _assert(False, "history on unknown parameter should raise")
        except ValueError:
            _assert(True, "history on unknown parameter raises")

        # -- non-float value raises cleanly
        try:
            T.record_event(parameter="joy", value="seven")
            _assert(False, "non-float value should raise")
        except ValueError:
            _assert(True, "non-float value raises ValueError")

        # -- recent() across all parameters
        recents = T.recent(limit=50)
        _assert(len(recents) >= 4,
                "recent() returns at least 4 rows after writes")
        _assert(recents[0]["parameter"] == "humor",
                "recent()[0] is the newest event (humor=10.0)")

        # -- reopening preserves state
        T2 = Temperament(db_path=db)
        _assert(T2.current_value("warmth") == 7.5,
                "reopening ledger preserves warmth=7.5")
        _assert(T2.current_value("curiosity") is None,
                "reopening ledger preserves NULL for curiosity")

        # -- default DB path points somewhere inside memory/
        _assert("memory" in str(DEFAULT_DB_PATH),
                "DEFAULT_DB_PATH lives under memory/")

    print("-" * 60)
    print(f"{_counts[0]} passed, {_counts[1]} failed")
    raise SystemExit(0 if _counts[1] == 0 else 1)
