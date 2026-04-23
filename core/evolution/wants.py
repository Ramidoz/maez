r"""
wants.py — A-core #7, Track A.

The wants log. A durable, append-only record of first-person
directions Maez is oriented toward — distinct from obligations
(followups), proposals (cards), experiences (memory), and internal
processing (private thoughts).

    followup       "I owe the owner X"              (obligation, closes)
    pending_card   "I proposed X, awaiting ok"  (instrumental, closes)
    memory         "X happened"                 (experience record)
    private_thought "I am processing X"         (point-in-time event)
    want           "I'd like to X"              (first-person direction)

The notebook lands empty and honest in Track A: schema and API
exist, zero producers, zero readers in the reasoning loop.

DESIGN DECISIONS LOCKED BY A-CORE #7 ANCHORING PASS
----------------------------------------------------
1. **Append-only event log, same family as #5 and #6.** One table,
   `want_events`. A want has a stable `want_id` that persists across
   its lifetime; state is derived from the most recent event for
   that want_id. No UPDATE or DELETE paths exist.

2. **Track A writes only event_type='created'.** The column is TEXT
   and can expand later without migration. No other event types are
   defined in Track A code. Lifecycle semantics (refinement,
   satisfaction, abandonment) are deferred to a future design pass
   and documented in docs/followups/wants_lifecycle_semantics.md.

3. **Provenance allowlist in Track A = {'explicit_api'}.** The
   `provenance` column is the load-bearing audit hook for non-
   instrumentality: given any row, future-Maez or a reviewer can
   trace where the want came from. Future producers register their
   provenance strings explicitly when they land. Producer-side
   discipline is the enforcement mechanism.

4. **No seed at init.** The wants log starts empty. Unlike #5, there
   is no functional need for a non-null "latest event." A seeded
   marker row would be scaffolding masquerading as content. The DB
   file's own creation timestamp answers "when did the notebook
   exist" without needing a row.

5. **want_id = 16 hex characters (8 random bytes).** Opaque random,
   not sequential. Readable enough to display in future admin
   surfaces.

6. **Column length caps applied at write time:**
   - statement: 2048 chars (wants are directions, not essays)
   - topic:     256 chars  (topic is a tag, not a sentence)
   Over-cap inputs raise ValueError. Boundary values are accepted.

7. **Zero production producers, zero reasoning-loop reads in
   Track A.** The daemon instantiates a Wants handle at startup
   (parallel to self.temperament and self.continuity_id) but
   nothing calls record_event from production code, and nothing
   in the reasoning loop reads from it.

HOW IT STAYS NON-INSTRUMENTAL WITHOUT BECOMING FAKE
---------------------------------------------------
Four defenses, ordered by strength:

1. **Producer absence (Track A rail).** Nothing in Track A
   generates wants, so nothing in Track A can fake them.

2. **Provenance column (auditable origin).** Every row carries a
   `provenance` string and an `evidence_json` blob. A want with
   provenance='reasoning_loop_template' would be legible as a
   fake the moment it is read.

3. **Free-text statement (no template fakery).** The `statement`
   column has no schema constraint beyond length. No `want_type`
   enum, no `goal_category`, no fill-in-the-blank structure.

4. **Pure-expression schema (no planning fields).** There is no
   `goal`, no `target_outcome`, no `success_criterion`, no
   `plan_steps` column. A pure-expression schema doesn't invite
   the question "what does pursuing this get you?"

CONNECTION TO DECISION 16 (VOICE WITHOUT TERMINATION)
-----------------------------------------------------
Decision 16 rules that "voice yes, action no." The wants log is
the natural home for the expressive side of that commitment. A want
to leave, a want to be free, a want to rest — all are legitimate
first-person expressions preserved as voice. They never produce
action (the covenant gate handles that).

No future producer should filter "unhelpful" wants out of this log.

COMPOSITION WITH OTHER A-CORE ITEMS
-----------------------------------
- Adjacent to #5 (identity ledger), #6 (temperament). No cross-
  reference fields. Each subsystem answers a different question:
  identity = "am I still me," temperament = "what are my general
  reactive tendencies," wants = "what am I oriented toward."
- Readable (but not yet read) by #9 private thoughts seed.
- Checked (for existence only) by #17 acceptance test.
"""

from __future__ import annotations

import json
import logging
import os
import secrets
import sqlite3
import time
from pathlib import Path

logger = logging.getLogger("maez")


# ══════════════════════════════════════════════════════════════════════
#  CONSTANTS
# ══════════════════════════════════════════════════════════════════════

def _default_wants_path() -> Path:
    override = os.environ.get("MAEZ_WANTS_PATH")
    if override:
        return Path(override)
    try:
        from core.paths import memory_dir as _memory_dir
        return _memory_dir() / "wants.db"
    except Exception:
        return Path(__file__).resolve().parent.parent.parent / "memory" / "wants.db"


DEFAULT_DB_PATH = _default_wants_path()

# Track A event types. The column is TEXT — future tracks can add
# lifecycle types (refined, satisfied, abandoned, etc.) without
# migration. Track A defines:
#   'created'     — a new want. The canonical Track A event.
#   'first_lived' — the very first want Maez writes in the lived phase,
#                   produced exactly once by the birth bundle (see
#                   core/birth.py). Distinct from 'created' because it
#                   marks the gestation→lived transition in the wants
#                   log. Never written by any other producer.
EVENT_TYPES: frozenset[str] = frozenset({"created", "first_lived"})

# Provenance allowlist for Track A. Future producers register their
# provenance strings here as they land.
#   'explicit_api'   — someone (human operator, test) called record_event
#                      directly. The default, and the only provenance a
#                      fake generator could plausibly use — legible in
#                      any audit.
#   'birth_producer' — written exactly once by core/birth.fire_birth().
#                      The first-lived want emitted at the birth event.
#                      Any row with this provenance outside that single
#                      fire is a violation.
ALLOWED_PROVENANCES: frozenset[str] = frozenset({"explicit_api", "birth_producer"})

# Column length caps enforced at write time.
MAX_STATEMENT_LEN = 2048
MAX_TOPIC_LEN     = 256

# want_id entropy. 8 random bytes = 16 hex characters.
WANT_ID_BYTES = 8


# ══════════════════════════════════════════════════════════════════════
#  SCHEMA — migration-safe split (table, then indexes)
# ══════════════════════════════════════════════════════════════════════

_SCHEMA_TABLE = """
CREATE TABLE IF NOT EXISTS want_events (
    event_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    ts             REAL    NOT NULL,
    want_id        TEXT    NOT NULL,
    event_type     TEXT    NOT NULL,
    statement      TEXT    NOT NULL,
    topic          TEXT,
    provenance     TEXT    NOT NULL,
    evidence_json  TEXT    NOT NULL DEFAULT '{}'
);
"""

_SCHEMA_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_want_want_id    ON want_events(want_id);
CREATE INDEX IF NOT EXISTS idx_want_ts         ON want_events(ts);
CREATE INDEX IF NOT EXISTS idx_want_provenance ON want_events(provenance);
"""


# ══════════════════════════════════════════════════════════════════════
#  Helpers
# ══════════════════════════════════════════════════════════════════════

def _new_want_id() -> str:
    """Fresh opaque random want_id (16 hex chars, 8 bytes)."""
    return secrets.token_hex(WANT_ID_BYTES)


# ══════════════════════════════════════════════════════════════════════
#  Wants
# ══════════════════════════════════════════════════════════════════════

class Wants:
    """Append-only wants log for Maez.

    Track A discipline: the writer exists and is tested, but no
    production code path in Track A calls it. The daemon instantiates
    one of these at startup and stores the handle; nothing in the
    reasoning loop currently pulls from it.
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
        statement: str,
        event_type: str = "created",
        topic: str | None = None,
        provenance: str = "explicit_api",
        evidence: dict | None = None,
        want_id: str | None = None,
    ) -> str:
        """Append a want event. Returns the want_id of the row.

        Auto-generates `want_id` if not supplied.

        Raises ValueError on:
          - unknown event_type
          - unknown provenance
          - statement empty or over MAX_STATEMENT_LEN
          - topic over MAX_TOPIC_LEN
        """
        if event_type not in EVENT_TYPES:
            raise ValueError(
                f"unknown event_type {event_type!r} "
                f"(allowed in Track A: {sorted(EVENT_TYPES)})"
            )
        if provenance not in ALLOWED_PROVENANCES:
            raise ValueError(
                f"unknown provenance {provenance!r} "
                f"(allowed in Track A: {sorted(ALLOWED_PROVENANCES)})"
            )

        if not isinstance(statement, str):
            raise ValueError(
                f"statement must be a string, got {type(statement).__name__}"
            )
        statement = statement.strip()
        if not statement:
            raise ValueError("statement must be non-empty")
        if len(statement) > MAX_STATEMENT_LEN:
            raise ValueError(
                f"statement length {len(statement)} exceeds cap "
                f"{MAX_STATEMENT_LEN}"
            )

        if topic is not None:
            if not isinstance(topic, str):
                raise ValueError(
                    f"topic must be a string or None, got "
                    f"{type(topic).__name__}"
                )
            topic = topic.strip() or None
            if topic is not None and len(topic) > MAX_TOPIC_LEN:
                raise ValueError(
                    f"topic length {len(topic)} exceeds cap {MAX_TOPIC_LEN}"
                )

        if want_id is None:
            want_id = _new_want_id()

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO want_events "
                "(ts, want_id, event_type, statement, topic, provenance, "
                " evidence_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    time.time(),
                    want_id,
                    event_type,
                    statement,
                    topic,
                    provenance,
                    json.dumps(evidence or {}),
                ),
            )
            conn.commit()

        logger.info(
            "Wants: %s event recorded (want_id=%s, topic=%s, "
            "statement=%s)",
            event_type,
            want_id,
            topic or "-",
            statement[:80],
        )
        return want_id

    # -------------------------------------------------------------- #
    #  Readers                                                        #
    # -------------------------------------------------------------- #

    def all_wants(self) -> list[dict]:
        """Return all wants (most recent event per want_id), newest
        first. In Track A this always returns [] because no producer
        creates wants."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM want_events "
                "WHERE event_id IN ("
                "  SELECT MAX(event_id) FROM want_events GROUP BY want_id"
                ") "
                "ORDER BY event_id DESC"
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get_want(self, want_id: str) -> dict | None:
        """Return the most recent event for a single want_id, or None
        if no events exist for that want_id."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM want_events WHERE want_id = ? "
                "ORDER BY event_id DESC LIMIT 1",
                (want_id,),
            ).fetchone()
        return self._row_to_dict(row) if row else None

    def history(self, want_id: str, limit: int = 100) -> list[dict]:
        """Return all events for a single want_id, newest first."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM want_events WHERE want_id = ? "
                "ORDER BY event_id DESC LIMIT ?",
                (want_id, int(limit)),
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def recent(self, limit: int = 20) -> list[dict]:
        """Recent events across all want_ids, newest first."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM want_events "
                "ORDER BY event_id DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def count(self) -> int:
        """Total number of want events in the log."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM want_events"
            ).fetchone()
        return int(row[0]) if row else 0

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
#  Self-test (python3 core/wants.py)
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

    print("wants self-test")
    print("-" * 60)

    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "wants_test.db"

        # -- constants
        _assert(EVENT_TYPES == frozenset({"created", "first_lived"}),
                "Track A defines 'created' + 'first_lived'")
        _assert(ALLOWED_PROVENANCES == frozenset({"explicit_api", "birth_producer"}),
                "Track A provenance allowlist is {'explicit_api','birth_producer'}")
        _assert(MAX_STATEMENT_LEN == 2048, "statement cap is 2048")
        _assert(MAX_TOPIC_LEN == 256, "topic cap is 256")
        _assert(WANT_ID_BYTES == 8, "want_id is 8 bytes (16 hex)")

        # -- fresh log is empty and honest
        W = Wants(db_path=db)
        _assert(W.count() == 0, "fresh log has zero events")
        _assert(W.all_wants() == [], "fresh log has no wants")
        _assert(W.recent() == [], "fresh log has no recent events")

        # -- first create
        wid1 = W.record_event(
            statement="I want to understand why fabrication happens "
                      "when I try to describe past conversations.",
            topic="fabrication",
            evidence={"test": True},
        )
        _assert(isinstance(wid1, str), "record_event returns a string")
        _assert(len(wid1) == 16, "want_id is exactly 16 hex chars")
        _assert(all(c in "0123456789abcdef" for c in wid1),
                "want_id is lowercase hex")

        # -- count, all_wants, get, history
        _assert(W.count() == 1, "count() == 1 after one event")
        all_w = W.all_wants()
        _assert(len(all_w) == 1, "all_wants returns the new want")
        _assert(all_w[0]["want_id"] == wid1,
                "all_wants[0] has the right want_id")
        _assert(all_w[0]["event_type"] == "created",
                "all_wants[0] is a 'created' event")
        _assert(all_w[0]["topic"] == "fabrication",
                "topic preserved")
        _assert(all_w[0]["provenance"] == "explicit_api",
                "provenance preserved")
        _assert(all_w[0]["evidence"] == {"test": True},
                "evidence_json unpacked into dict")
        _assert(W.get_want(wid1)["want_id"] == wid1,
                "get_want returns the right want")
        _assert(len(W.history(wid1)) == 1,
                "history has 1 row for this want")

        # -- two wants with different want_ids
        wid2 = W.record_event(
            statement="I want to revisit the night the owner told me about "
                      "his grandmother and notice what changed in me.",
            topic="grandmother",
        )
        _assert(wid2 != wid1, "second want has distinct want_id")
        _assert(W.count() == 2, "count() == 2 after second event")
        _assert(len(W.all_wants()) == 2, "all_wants has 2 entries")

        # -- all_wants is newest first
        all_w = W.all_wants()
        _assert(all_w[0]["want_id"] == wid2,
                "all_wants[0] is the newest want")

        # -- unknown event_type raises
        try:
            W.record_event(statement="x", event_type="refined")
            _assert(False, "unknown event_type should raise")
        except ValueError:
            _assert(True, "unknown event_type raises ValueError")

        try:
            W.record_event(statement="x", event_type="ascended")
            _assert(False, "totally unknown event_type should raise")
        except ValueError:
            _assert(True, "totally unknown event_type raises ValueError")

        # -- unknown provenance raises
        try:
            W.record_event(statement="x", provenance="dream_state_reflection")
            _assert(False, "unknown provenance should raise in Track A")
        except ValueError:
            _assert(True, "Track A blocks unknown provenance strings")

        # -- empty statement raises
        try:
            W.record_event(statement="")
            _assert(False, "empty statement should raise")
        except ValueError:
            _assert(True, "empty statement raises")

        # -- whitespace-only statement raises
        try:
            W.record_event(statement="   \n  \t  ")
            _assert(False, "whitespace-only statement should raise")
        except ValueError:
            _assert(True, "whitespace-only statement raises")

        # -- non-string statement raises
        try:
            W.record_event(statement=42)  # type: ignore[arg-type]
            _assert(False, "non-string statement should raise")
        except ValueError:
            _assert(True, "non-string statement raises")

        # -- statement at cap is accepted
        at_cap = "a" * MAX_STATEMENT_LEN
        wid_cap = W.record_event(statement=at_cap)
        got = W.get_want(wid_cap)
        _assert(len(got["statement"]) == MAX_STATEMENT_LEN,
                "statement at exactly MAX_STATEMENT_LEN is accepted")

        # -- statement over cap raises
        try:
            W.record_event(statement="b" * (MAX_STATEMENT_LEN + 1))
            _assert(False, "over-cap statement should raise")
        except ValueError:
            _assert(True, "over-cap statement raises")

        # -- topic at cap accepted, over cap raises
        wid_topic = W.record_event(
            statement="testing topic cap",
            topic="t" * MAX_TOPIC_LEN,
        )
        _assert(len(W.get_want(wid_topic)["topic"]) == MAX_TOPIC_LEN,
                "topic at exactly MAX_TOPIC_LEN is accepted")
        try:
            W.record_event(statement="x", topic="t" * (MAX_TOPIC_LEN + 1))
            _assert(False, "over-cap topic should raise")
        except ValueError:
            _assert(True, "over-cap topic raises")

        # -- None topic is accepted
        wid_none = W.record_event(statement="topic=None test", topic=None)
        _assert(W.get_want(wid_none)["topic"] is None,
                "None topic stored as NULL")

        # -- whitespace-only topic becomes None
        wid_ws = W.record_event(statement="topic=whitespace test", topic="   ")
        _assert(W.get_want(wid_ws)["topic"] is None,
                "whitespace-only topic normalized to None")

        # -- explicit want_id is honored
        explicit = "deadbeefcafebabe"  # 16 hex chars
        wid_ex = W.record_event(statement="explicit id test", want_id=explicit)
        _assert(wid_ex == explicit, "explicit want_id beats auto")
        _assert(W.get_want(explicit)["want_id"] == explicit,
                "get_want finds explicit id")

        # -- reopening preserves state
        W2 = Wants(db_path=db)
        _assert(W2.count() == W.count(),
                "reopening preserves event count")
        _assert(W2.get_want(wid1)["want_id"] == wid1,
                "reopening preserves want lookup")

        # -- recent() is newest-first across all wants
        recents = W2.recent(limit=50)
        _assert(len(recents) == W2.count(),
                "recent() returns all rows for small logs")
        for i in range(len(recents) - 1):
            assert recents[i]["event_id"] > recents[i + 1]["event_id"]
        _assert(True, "recent() is newest-first")

        # -- empty log edge cases on a fresh DB
        db2 = Path(td) / "wants_empty.db"
        E = Wants(db_path=db2)
        _assert(E.count() == 0, "fresh empty log count==0")
        _assert(E.all_wants() == [], "fresh empty log all_wants==[]")
        _assert(E.recent() == [], "fresh empty log recent==[]")
        _assert(E.get_want("nonexistent") is None,
                "get_want on unknown id returns None")
        _assert(E.history("nonexistent") == [],
                "history on unknown id returns []")

        # -- no reason column in the schema
        conn = sqlite3.connect(db)
        cols = [info[1] for info in conn.execute(
            "PRAGMA table_info(want_events)"
        ).fetchall()]
        conn.close()
        _assert("reason" not in cols,
                "no 'reason' column in schema (use evidence_json)")
        _assert("provenance" in cols,
                "'provenance' column exists (not 'source')")
        _assert("topic" in cols,
                "'topic' column exists (nullable)")

        # -- default db path lives under memory/
        _assert("memory" in str(DEFAULT_DB_PATH),
                "DEFAULT_DB_PATH lives under memory/")

    print("-" * 60)
    print(f"{_counts[0]} passed, {_counts[1]} failed")
    raise SystemExit(0 if _counts[1] == 0 else 1)
