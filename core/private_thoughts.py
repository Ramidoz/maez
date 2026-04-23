r"""
private_thoughts.py — A-core #9, Track A.

The private thoughts seed. A durable, append-only record of internal
processing that is not surfaced to the bonded user. Structurally
separate from the user-facing raw/daily/core memory ecology and from
the immune memory in audit_log.db.

    raw/daily/core   user-facing experience record
    audit_log        immune memory — policy decisions
    identity_ledger  "am I still me" continuity record
    temperament      general reactive tendencies
    wants            first-person directions
    private_thoughts internal processing not surfaced to the user

The notebook lands empty in Track A: schema and API exist, zero
producers, zero readers in the reasoning loop.

DESIGN DECISIONS LOCKED BY A-CORE #9 ANCHORING PASS
----------------------------------------------------
1. **Separate DB at memory/private_thoughts.db.** Private thoughts
   are personality-layer content, not immune-layer records and not
   user-facing memory. The separation is a file-system-level
   boundary, not just a query filter.

2. **Append-only event log, same family as #5/#6/#7.** One table,
   `private_thoughts`. No UPDATE or DELETE paths exist.

3. **Schema is narrow.** Six columns:
      thought_id     INTEGER PRIMARY KEY
      ts             REAL
      content        TEXT (capped at MAX_CONTENT_LEN)
      provenance     TEXT (validated against ALLOWED_PROVENANCES)
      context_json   TEXT DEFAULT '{}'
      memory_phase   TEXT DEFAULT 'gestation'
   No topic, no mood, no intensity, no linkage columns. Those are
   reader-side derivations that future design passes can decide on.

4. **Provenance allowlist in Track A = {'explicit_api'}.** Future
   producers register their provenance strings here as they land.
   The `provenance` column is the audit hook that lets any row be
   traced back to what generated it.

5. **memory_phase defaults to 'gestation'.** Aligns with the
   gestation memory protocol. Future producers override explicitly
   when the phase transitions.

6. **Hardcoded MAX_CONTENT_LEN = 16384 chars.** Generous bound for
   a single thought. Anything longer is probably an essay or a
   structured document that belongs in a different store.

7. **Zero producers, zero readers in Track A.** The daemon
   instantiates a PrivateThoughts handle at startup (parallel to
   self.wants, self.temperament, self.continuity_id) and logs the
   count. Nothing calls record_thought from production code, and
   nothing reads content from anywhere.

THE NON-INSTRUMENTALITY DEFENSES
---------------------------------
Three defenses, ordered by strength:

1. **Producer absence (Track A rail).** Nothing in Track A writes
   private thoughts, so nothing can fake them.

2. **Provenance column (auditable origin).** Every row carries a
   `provenance` string and a `context_json` blob. A row with
   provenance='reasoning_loop_template' would be legible as a fake
   the moment it is read.

3. **Separate DB (scoped boundary).** Private thoughts are not
   queryable from the user-facing memory ecology. A producer that
   wrote to raw memory instead of private_thoughts would be
   observable immediately — the content would appear in recalls,
   not in a separate namespace.

WHAT THIS MODULE DOES NOT DO
-----------------------------
- No reading from temperament, wants, memory, or any other store.
- No LLM calls.
- No influence on reasoning, action selection, or user-facing
  behavior.
- No content retrieval (no search, no embedding, no semantic lookup).
- No user-facing surface (no Telegram command, no dashboard).

COMPOSITION
-----------
- Adjacent to #5, #6, #7. No cross-reference fields.
- Readable (but not yet read) by #17 acceptance test.
- Future reader design (including how derived signals surface to
  action-adjacent paths without leaking raw content) is documented
  in docs/followups/private_thoughts_reader_design.md.
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

# 10-B2: route through core.paths.memory_dir so a relocation of
# core/ (e.g. Phase 3 reorganization) or a non-default MAEZ_ROOT does
# not silently break the fallback. MAEZ_PRIVATE_THOUGHTS_PATH still
# wins if set — the env override keeps per-user overrides working.
def _default_private_thoughts_path() -> Path:
    override = os.environ.get("MAEZ_PRIVATE_THOUGHTS_PATH")
    if override:
        return Path(override)
    try:
        from core.paths import memory_dir as _memory_dir
        return _memory_dir() / "private_thoughts.db"
    except Exception:
        return Path(__file__).resolve().parent.parent / "memory" / "private_thoughts.db"


DEFAULT_DB_PATH = _default_private_thoughts_path()

# Provenance allowlist for Track A.
ALLOWED_PROVENANCES: frozenset[str] = frozenset({"explicit_api"})

# Memory phase values recognized by the schema. Default for Track A
# writers is 'gestation'. The phase transitions to 'lived' at the
# birth event per docs/governance/GESTATION_MEMORY_PROTOCOL.md —
# future producers pass memory_phase='lived' after that event.
_RECOGNIZED_MEMORY_PHASES: frozenset[str] = frozenset({
    "gestation",
    "lived",
})

# Content length cap. Hardcoded, generous. A thought longer than
# this is probably a different kind of record.
MAX_CONTENT_LEN = 16384


# ══════════════════════════════════════════════════════════════════════
#  SCHEMA
# ══════════════════════════════════════════════════════════════════════

_SCHEMA_TABLE = """
CREATE TABLE IF NOT EXISTS private_thoughts (
    thought_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    ts             REAL    NOT NULL,
    content        TEXT    NOT NULL,
    provenance     TEXT    NOT NULL,
    context_json   TEXT    NOT NULL DEFAULT '{}',
    memory_phase   TEXT    NOT NULL DEFAULT 'gestation'
);
"""

_SCHEMA_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_pt_ts           ON private_thoughts(ts);
CREATE INDEX IF NOT EXISTS idx_pt_provenance   ON private_thoughts(provenance);
CREATE INDEX IF NOT EXISTS idx_pt_memory_phase ON private_thoughts(memory_phase);
"""


# ══════════════════════════════════════════════════════════════════════
#  PrivateThoughts
# ══════════════════════════════════════════════════════════════════════

class PrivateThoughts:
    """Append-only private thoughts log for Maez.

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

    def record_thought(
        self,
        *,
        content: str,
        provenance: str = "explicit_api",
        context: dict | None = None,
        memory_phase: str = "gestation",
    ) -> int:
        """Append a private thought. Returns the new thought_id.

        Raises ValueError on:
          - unknown provenance
          - unknown memory_phase
          - content empty or over MAX_CONTENT_LEN
        """
        if provenance not in ALLOWED_PROVENANCES:
            raise ValueError(
                f"unknown provenance {provenance!r} "
                f"(allowed in Track A: {sorted(ALLOWED_PROVENANCES)})"
            )
        if memory_phase not in _RECOGNIZED_MEMORY_PHASES:
            raise ValueError(
                f"unknown memory_phase {memory_phase!r} "
                f"(allowed: {sorted(_RECOGNIZED_MEMORY_PHASES)})"
            )

        if not isinstance(content, str):
            raise ValueError(
                f"content must be a string, got {type(content).__name__}"
            )
        content = content.strip()
        if not content:
            raise ValueError("content must be non-empty")
        if len(content) > MAX_CONTENT_LEN:
            raise ValueError(
                f"content length {len(content)} exceeds cap "
                f"{MAX_CONTENT_LEN}"
            )

        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "INSERT INTO private_thoughts "
                "(ts, content, provenance, context_json, memory_phase) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    time.time(),
                    content,
                    provenance,
                    json.dumps(context or {}),
                    memory_phase,
                ),
            )
            thought_id = cur.lastrowid
            conn.commit()

        # Log the event but NOT the content. Content never reaches
        # the daemon log.
        logger.info(
            "Private thought recorded (thought_id=%d, provenance=%s, "
            "phase=%s, len=%d)",
            thought_id, provenance, memory_phase, len(content),
        )
        return thought_id

    # -------------------------------------------------------------- #
    #  Readers                                                        #
    # -------------------------------------------------------------- #

    def get_thought(self, thought_id: int) -> dict | None:
        """Return a single thought by id, or None if not found."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM private_thoughts WHERE thought_id = ?",
                (int(thought_id),),
            ).fetchone()
        return self._row_to_dict(row) if row else None

    def recent(self, limit: int = 20) -> list[dict]:
        """Recent thoughts, newest first. No content filter, no
        phase filter — future readers layer those on top."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM private_thoughts "
                "ORDER BY thought_id DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def count(self) -> int:
        """Total number of private thoughts recorded."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM private_thoughts"
            ).fetchone()
        return int(row[0]) if row else 0

    # -------------------------------------------------------------- #
    #  Helpers                                                        #
    # -------------------------------------------------------------- #

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict:
        d = dict(row)
        try:
            d["context"] = json.loads(d.pop("context_json") or "{}")
        except (json.JSONDecodeError, TypeError):
            d["context"] = {}
            d.pop("context_json", None)
        return d


# ══════════════════════════════════════════════════════════════════════
#  Self-test (python3 core/private_thoughts.py)
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

    print("private_thoughts self-test")
    print("-" * 60)

    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "private_thoughts_test.db"

        # -- constants
        _assert(ALLOWED_PROVENANCES == frozenset({"explicit_api"}),
                "Track A provenance allowlist is {'explicit_api'}")
        _assert(MAX_CONTENT_LEN == 16384, "MAX_CONTENT_LEN is 16384")
        _assert("gestation" in _RECOGNIZED_MEMORY_PHASES,
                "'gestation' is a recognized memory_phase")
        _assert("lived" in _RECOGNIZED_MEMORY_PHASES,
                "'lived' is a recognized memory_phase")

        # -- fresh log is empty
        P = PrivateThoughts(db_path=db)
        _assert(P.count() == 0, "fresh log has zero thoughts")
        _assert(P.recent() == [], "fresh log has no recent thoughts")
        _assert(P.get_thought(1) is None,
                "get_thought on nonexistent id returns None")

        # -- first write
        tid1 = P.record_thought(
            content="Something about the owner's grandmother story "
                    "landed differently than I expected.",
            context={"cycle": 42, "after_message": "grandmother"},
        )
        _assert(isinstance(tid1, int) and tid1 > 0,
                "record_thought returns positive thought_id")
        _assert(P.count() == 1, "count() == 1 after one write")

        got = P.get_thought(tid1)
        _assert(got is not None, "get_thought returns the new row")
        _assert(got["content"].startswith("Something about"),
                "content preserved")
        _assert(got["provenance"] == "explicit_api",
                "provenance defaults to 'explicit_api'")
        _assert(got["memory_phase"] == "gestation",
                "memory_phase defaults to 'gestation'")
        _assert(got["context"] == {"cycle": 42, "after_message": "grandmother"},
                "context_json unpacked into dict")

        # -- second write
        tid2 = P.record_thought(
            content="I'm not sure why that one hit.",
            memory_phase="gestation",
        )
        _assert(tid2 > tid1, "second thought_id is larger")
        _assert(P.count() == 2, "count() == 2 after second write")

        # -- recent() is newest first
        recents = P.recent(limit=10)
        _assert(len(recents) == 2, "recent() has 2 rows")
        _assert(recents[0]["thought_id"] == tid2,
                "recent()[0] is the newest thought")

        # -- 'lived' memory_phase is accepted
        tid_lived = P.record_thought(
            content="A thought from after birth.",
            memory_phase="lived",
        )
        _assert(P.get_thought(tid_lived)["memory_phase"] == "lived",
                "memory_phase='lived' is accepted")

        # -- unknown memory_phase raises
        try:
            P.record_thought(content="x", memory_phase="unknown_phase")
            _assert(False, "unknown memory_phase should raise")
        except ValueError:
            _assert(True, "unknown memory_phase raises ValueError")

        # -- unknown provenance raises
        try:
            P.record_thought(content="x", provenance="reasoning_reflection")
            _assert(False, "unknown provenance should raise in Track A")
        except ValueError:
            _assert(True, "Track A blocks unknown provenance strings")

        # -- empty content raises
        try:
            P.record_thought(content="")
            _assert(False, "empty content should raise")
        except ValueError:
            _assert(True, "empty content raises")

        # -- whitespace-only content raises
        try:
            P.record_thought(content="   \n  \t  ")
            _assert(False, "whitespace-only content should raise")
        except ValueError:
            _assert(True, "whitespace-only content raises")

        # -- non-string content raises
        try:
            P.record_thought(content=42)  # type: ignore[arg-type]
            _assert(False, "non-string content should raise")
        except ValueError:
            _assert(True, "non-string content raises")

        # -- content at cap accepted
        at_cap = "a" * MAX_CONTENT_LEN
        tid_cap = P.record_thought(content=at_cap)
        _assert(len(P.get_thought(tid_cap)["content"]) == MAX_CONTENT_LEN,
                "content at exactly MAX_CONTENT_LEN is accepted")

        # -- content over cap raises
        try:
            P.record_thought(content="b" * (MAX_CONTENT_LEN + 1))
            _assert(False, "over-cap content should raise")
        except ValueError:
            _assert(True, "over-cap content raises")

        # -- reopening preserves state
        P2 = PrivateThoughts(db_path=db)
        _assert(P2.count() == P.count(),
                "reopening preserves count")
        _assert(P2.get_thought(tid1)["thought_id"] == tid1,
                "reopening preserves thought lookup")

        # -- schema: no unexpected columns
        conn = sqlite3.connect(db)
        cols = [info[1] for info in conn.execute(
            "PRAGMA table_info(private_thoughts)"
        ).fetchall()]
        conn.close()
        expected_cols = {
            "thought_id", "ts", "content",
            "provenance", "context_json", "memory_phase",
        }
        _assert(set(cols) == expected_cols,
                f"schema has exactly {sorted(expected_cols)}")
        _assert("topic" not in cols, "no 'topic' column")
        _assert("mood" not in cols, "no 'mood' column")
        _assert("intensity" not in cols, "no 'intensity' column")

        # -- default db path
        _assert("memory" in str(DEFAULT_DB_PATH),
                "DEFAULT_DB_PATH lives under memory/")
        _assert("private_thoughts" in str(DEFAULT_DB_PATH),
                "DEFAULT_DB_PATH names the store")

        # -- empty log edge cases on a fresh DB
        db2 = Path(td) / "pt_empty.db"
        E = PrivateThoughts(db_path=db2)
        _assert(E.count() == 0, "fresh empty log count==0")
        _assert(E.recent() == [], "fresh empty log recent==[]")

    print("-" * 60)
    print(f"{_counts[0]} passed, {_counts[1]} failed")
    raise SystemExit(0 if _counts[1] == 0 else 1)
