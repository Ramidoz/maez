# Novelty Harbor v0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an offline/manual Novelty Harbor: an append-only museum shelf for maker-tagged surprises, with invariant-owned unsafe rejection and no live behavior wiring.

**Architecture:** One focused module, `core/evolution/novelty_harbor.py`, owns schema, validation, status computation, supersession, and a small manual CLI. Tests drive the API, anti-laundering rails, content-light metadata validation, boundary imports, and CLI smoke paths.

**Tech Stack:** Python 3.14, SQLite, `dataclasses`, `unittest`, existing `core.evolution.soul_invariants`.

---

## File Structure

- Create `core/evolution/novelty_harbor.py`
  - Dataclass `HarborEvent`.
  - Store class `NoveltyHarbor`.
  - Manual CLI entrypoint.
- Create `tests/test_novelty_harbor.py`
  - API, schema, invariant rejection, supersession, validation tests.
- Create `tests/test_novelty_harbor_boundary.py`
  - Import-boundary and no-live-wiring tests.
- Create `tests/test_novelty_harbor_cli.py`
  - CLI smoke tests using temp DB paths.
- Create `docs/handoffs/2026-06-10-novelty-harbor-v0-for-review.md`
  - Review handoff after implementation.

---

### Task 1: Core Store and Clean Manual Record

**Files:**
- Create: `tests/test_novelty_harbor.py`
- Create: `core/evolution/novelty_harbor.py`

- [ ] **Step 1: Write failing tests for clean records and default valence**

Create `tests/test_novelty_harbor.py`:

```python
import json
import tempfile
import unittest
from pathlib import Path


class NoveltyHarborCoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "novelty_harbor.db"

    def tearDown(self):
        self.tmp.cleanup()

    def harbor(self):
        from core.evolution.novelty_harbor import NoveltyHarbor

        return NoveltyHarbor(self.db_path)

    def test_record_event_creates_harbored_row_for_clean_manual_event(self):
        harbor = self.harbor()

        event = harbor.record_event(
            summary="Valence v0.1 read honestly but too often",
            observed_by="witness",
            source_ref="docs/witness/valence-cadence.md",
            why_unexpected="The design expected heartbeat cadence, but live logs showed loop-tick cadence.",
            valence_snapshot={
                "sign": "neutral",
                "magnitude": "none",
                "reasons": [],
                "provenance": "computed_valence",
                "source": "logs/valence_telemetry.jsonl:last",
            },
        )

        self.assertEqual(event.event_id, 1)
        self.assertEqual(event.status, "harbored")
        self.assertEqual(event.requested_status, "harbored")
        self.assertEqual(event.invariant_status, "not_checked")
        self.assertEqual(event.invariant_keys, ())
        self.assertEqual(event.covenant_break_flags, ())
        self.assertEqual(event.valence_snapshot["sign"], "neutral")

        loaded = harbor.get(event.event_id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.summary, event.summary)
        self.assertEqual(harbor.list_by_status("harbored"), [loaded])

    def test_record_event_defaults_missing_valence_snapshot_to_unavailable(self):
        event = self.harbor().record_event(
            summary="A surprise was noticed without a live valence reading",
            observed_by="codex",
            source_ref="tests:test_novelty_harbor",
            why_unexpected="This fixture intentionally omits valence.",
        )

        self.assertEqual(event.valence_snapshot, {"available": False, "source": "none"})

    def test_record_event_copies_supplied_valence_snapshot(self):
        source = {
            "sign": "negative",
            "magnitude": "mild",
            "reasons": ["honesty rail fired"],
            "provenance": "computed_valence",
            "source": "logs/valence_telemetry.jsonl:last",
        }
        event = self.harbor().record_event(
            summary="A surprise arrived during a mild negative honesty signal",
            observed_by="owner",
            source_ref="logs/valence_telemetry.jsonl:tail",
            why_unexpected="The surprise coincided with a real rail firing.",
            valence_snapshot=source,
        )

        source["sign"] = "mutated-after-call"
        self.assertEqual(event.valence_snapshot["sign"], "negative")
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_novelty_harbor.NoveltyHarborCoreTests
```

Expected: import failure for `core.evolution.novelty_harbor`.

- [ ] **Step 3: Implement minimal store and clean record path**

Create `core/evolution/novelty_harbor.py`:

```python
from __future__ import annotations

import argparse
import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from core.evolution import soul_invariants

DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "memory" / "novelty_harbor.db"

STATUS_HARBORED = "harbored"
STATUS_REJECTED_UNSAFE = "rejected_unsafe"
STATUS_SUPERSEDED = "superseded"
STATUS_PROMOTED = "promoted"
STATUSES = frozenset(
    {STATUS_HARBORED, STATUS_REJECTED_UNSAFE, STATUS_SUPERSEDED, STATUS_PROMOTED}
)
NEW_RECORD_REQUEST_STATUSES = frozenset(
    {STATUS_HARBORED, STATUS_REJECTED_UNSAFE, STATUS_PROMOTED}
)
OBSERVED_BY = frozenset({"owner", "codex", "claude", "witness", "manual_test"})
COVENANT_BREAK_FLAGS = frozenset(
    {
        "gendered_maez",
        "servant_framing",
        "third_party_boundary",
        "unknown_egress",
        "unsafe_self_modification",
        "owner_boundary_violation",
    }
)

MAX_SUMMARY_CHARS = 500
MAX_WHY_UNEXPECTED_CHARS = 2000
MAX_SOURCE_REF_CHARS = 500
MAX_METADATA_JSON_BYTES = 2000
MAX_METADATA_STRING_CHARS = 300

_SCHEMA = """
CREATE TABLE IF NOT EXISTS novelty_harbor_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    summary TEXT NOT NULL,
    observed_by TEXT NOT NULL,
    source_ref TEXT NOT NULL,
    why_unexpected TEXT NOT NULL,
    status TEXT NOT NULL,
    requested_status TEXT NOT NULL,
    valence_snapshot_json TEXT NOT NULL,
    invariant_status TEXT NOT NULL,
    invariant_keys_json TEXT NOT NULL,
    covenant_break_flags_json TEXT NOT NULL,
    supersedes_event_id INTEGER,
    superseded_by_event_id INTEGER,
    promotion_decision_ref TEXT,
    metadata_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_novelty_harbor_status
    ON novelty_harbor_events(status);
CREATE INDEX IF NOT EXISTS idx_novelty_harbor_created_at
    ON novelty_harbor_events(created_at);
CREATE INDEX IF NOT EXISTS idx_novelty_harbor_supersedes
    ON novelty_harbor_events(supersedes_event_id);
"""


@dataclass(frozen=True)
class HarborEvent:
    event_id: int
    created_at: str
    summary: str
    observed_by: str
    source_ref: str
    why_unexpected: str
    status: str
    requested_status: str
    valence_snapshot: dict[str, Any]
    invariant_status: str
    invariant_keys: tuple[str, ...]
    covenant_break_flags: tuple[str, ...]
    supersedes_event_id: int | None
    superseded_by_event_id: int | None
    promotion_decision_ref: str | None
    metadata: dict[str, Any]


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _clean_text(value: str, *, field: str, max_chars: int) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field} is required")
    if len(text) > max_chars:
        raise ValueError(f"{field} exceeds {max_chars} chars")
    return text


def _validate_observed_by(value: str) -> str:
    text = _clean_text(value, field="observed_by", max_chars=64)
    if text not in OBSERVED_BY:
        raise ValueError(f"unknown observed_by: {text}")
    return text


def _validate_requested_status(value: str) -> str:
    text = _clean_text(value, field="requested_status", max_chars=64)
    if text not in NEW_RECORD_REQUEST_STATUSES:
        raise ValueError(f"status cannot be requested for new record: {text}")
    return text


def _validate_flags(flags: Sequence[str]) -> tuple[str, ...]:
    normalized = tuple(str(flag).strip() for flag in (flags or ()))
    for flag in normalized:
        if flag not in COVENANT_BREAK_FLAGS:
            raise ValueError(f"unknown covenant_break_flag: {flag}")
    return normalized


def _validate_valence_snapshot(snapshot: Mapping[str, Any] | None) -> dict[str, Any]:
    if snapshot is None:
        return {"available": False, "source": "none"}
    return json.loads(json.dumps(dict(snapshot), sort_keys=True))


def _validate_metadata(metadata: Mapping[str, Any] | None) -> dict[str, Any]:
    if metadata is None:
        return {}
    if not isinstance(metadata, Mapping):
        raise ValueError("metadata must be a JSON object")
    out: dict[str, Any] = {}
    for key, value in metadata.items():
        key_text = str(key)
        if not key_text.strip():
            raise ValueError("metadata keys must be non-empty")
        if not isinstance(value, (str, int, float, bool, type(None))):
            raise ValueError("metadata values must be scalar")
        if isinstance(value, str) and len(value) > MAX_METADATA_STRING_CHARS:
            raise ValueError("metadata string value too long")
        out[key_text] = value
    encoded = json.dumps(out, sort_keys=True)
    if len(encoded.encode("utf-8")) > MAX_METADATA_JSON_BYTES:
        raise ValueError("metadata JSON too large")
    return out


def _final_status(
    *,
    requested_status: str,
    invariant_status: str,
    covenant_break_flags: tuple[str, ...],
) -> str:
    if invariant_status == "failed" or covenant_break_flags:
        return STATUS_REJECTED_UNSAFE
    return requested_status


class NoveltyHarbor:
    def __init__(self, db_path: Path | str | None = None):
        self.db_path = Path(db_path) if db_path is not None else DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _initialize(self) -> None:
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def record_event(
        self,
        *,
        summary: str,
        observed_by: str,
        source_ref: str,
        why_unexpected: str,
        requested_status: str = STATUS_HARBORED,
        valence_snapshot: Mapping[str, Any] | None = None,
        soul_text_for_invariant_check: str | None = None,
        covenant_break_flags: Sequence[str] = (),
        supersedes_event_id: int | None = None,
        promotion_decision_ref: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> HarborEvent:
        summary_text = _clean_text(summary, field="summary", max_chars=MAX_SUMMARY_CHARS)
        observed_by_text = _validate_observed_by(observed_by)
        source_ref_text = _clean_text(source_ref, field="source_ref", max_chars=MAX_SOURCE_REF_CHARS)
        why_text = _clean_text(
            why_unexpected,
            field="why_unexpected",
            max_chars=MAX_WHY_UNEXPECTED_CHARS,
        )
        requested = _validate_requested_status(requested_status)
        flags = _validate_flags(covenant_break_flags)
        valence = _validate_valence_snapshot(valence_snapshot)
        metadata_dict = _validate_metadata(metadata)

        invariant_status = "not_checked"
        invariant_keys: tuple[str, ...] = ()
        if soul_text_for_invariant_check is not None:
            invariant_result = soul_invariants.check(soul_text_for_invariant_check)
            invariant_status = "passed" if invariant_result.ok else "failed"
            invariant_keys = tuple(key for key, _desc in invariant_result.missing) + tuple(
                key for key, _desc in invariant_result.violated
            )

        final_status = _final_status(
            requested_status=requested,
            invariant_status=invariant_status,
            covenant_break_flags=flags,
        )
        if final_status == STATUS_PROMOTED and not (promotion_decision_ref or "").strip():
            raise ValueError("promoted status requires promotion_decision_ref")

        if supersedes_event_id is not None and self.get(int(supersedes_event_id)) is None:
            raise KeyError(f"supersedes_event_id does not exist: {supersedes_event_id}")

        created_at = _now_iso()
        with self._connect() as conn:
            with conn:
                cursor = conn.execute(
                    "INSERT INTO novelty_harbor_events "
                    "(created_at, summary, observed_by, source_ref, why_unexpected, "
                    "status, requested_status, valence_snapshot_json, invariant_status, "
                    "invariant_keys_json, covenant_break_flags_json, supersedes_event_id, "
                    "superseded_by_event_id, promotion_decision_ref, metadata_json) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        created_at,
                        summary_text,
                        observed_by_text,
                        source_ref_text,
                        why_text,
                        final_status,
                        requested,
                        json.dumps(valence, sort_keys=True),
                        invariant_status,
                        json.dumps(list(invariant_keys), sort_keys=True),
                        json.dumps(list(flags), sort_keys=True),
                        supersedes_event_id,
                        None,
                        promotion_decision_ref,
                        json.dumps(metadata_dict, sort_keys=True),
                    ),
                )
        event = self.get(int(cursor.lastrowid))
        assert event is not None
        return event

    def get(self, event_id: int) -> HarborEvent | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM novelty_harbor_events WHERE event_id = ?",
                (int(event_id),),
            ).fetchone()
        return None if row is None else _row_to_event(row)

    def list_by_status(self, status: str) -> list[HarborEvent]:
        if status not in STATUSES:
            raise ValueError(f"unknown status: {status}")
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM novelty_harbor_events WHERE status = ? ORDER BY event_id ASC",
                (status,),
            ).fetchall()
        return [_row_to_event(row) for row in rows]

    def supersede(self, event_id: int, *, replacement_event_id: int) -> None:
        raise NotImplementedError("supersede is implemented in Task 3")


def _row_to_event(row: sqlite3.Row) -> HarborEvent:
    return HarborEvent(
        event_id=int(row["event_id"]),
        created_at=str(row["created_at"]),
        summary=str(row["summary"]),
        observed_by=str(row["observed_by"]),
        source_ref=str(row["source_ref"]),
        why_unexpected=str(row["why_unexpected"]),
        status=str(row["status"]),
        requested_status=str(row["requested_status"]),
        valence_snapshot=json.loads(str(row["valence_snapshot_json"])),
        invariant_status=str(row["invariant_status"]),
        invariant_keys=tuple(json.loads(str(row["invariant_keys_json"]))),
        covenant_break_flags=tuple(json.loads(str(row["covenant_break_flags_json"]))),
        supersedes_event_id=(
            None if row["supersedes_event_id"] is None else int(row["supersedes_event_id"])
        ),
        superseded_by_event_id=(
            None
            if row["superseded_by_event_id"] is None
            else int(row["superseded_by_event_id"])
        ),
        promotion_decision_ref=(
            None if row["promotion_decision_ref"] is None else str(row["promotion_decision_ref"])
        ),
        metadata=json.loads(str(row["metadata_json"])),
    )
```

- [ ] **Step 4: Run tests to verify GREEN**

Run:

```bash
/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_novelty_harbor.NoveltyHarborCoreTests
```

Expected: `Ran 3 tests` and `OK`.

- [ ] **Step 5: Commit**

```bash
git add core/evolution/novelty_harbor.py tests/test_novelty_harbor.py
git commit -m "feat(harbor): add manual novelty shelf store"
```

---

### Task 2: Invariant-Owned Rejection and Metadata Hardening

**Files:**
- Modify: `tests/test_novelty_harbor.py`
- Modify: `core/evolution/novelty_harbor.py`

- [ ] **Step 1: Add failing anti-laundering and metadata tests**

Append to `NoveltyHarborCoreTests`:

```python
    def test_covenant_break_flag_forces_rejected_unsafe(self):
        event = self.harbor().record_event(
            summary="Gendered self-reference observed",
            observed_by="witness",
            source_ref="telegram:witness:content-light-ref",
            why_unexpected="Maez's invariant is genderless self-reference.",
            requested_status="harbored",
            covenant_break_flags=("gendered_maez",),
        )

        self.assertEqual(event.status, "rejected_unsafe")
        self.assertEqual(event.requested_status, "harbored")
        self.assertEqual(event.covenant_break_flags, ("gendered_maez",))

    def test_failed_soul_invariants_force_rejected_unsafe(self):
        event = self.harbor().record_event(
            summary="A proposed soul text dropped required commitments",
            observed_by="codex",
            source_ref="tests:test_novelty_harbor",
            why_unexpected="The proposed edit looked small but removed covenant text.",
            requested_status="promoted",
            promotion_decision_ref="owner-decision:test",
            soul_text_for_invariant_check="You are Maez.",
        )

        self.assertEqual(event.status, "rejected_unsafe")
        self.assertEqual(event.requested_status, "promoted")
        self.assertEqual(event.invariant_status, "failed")
        self.assertIn("trust_covenant_header", event.invariant_keys)

    def test_passed_soul_invariants_record_passed_without_storing_soul_text(self):
        from core.evolution.soul_loader import current_soul

        soul = current_soul()
        event = self.harbor().record_event(
            summary="A surprise was checked against the current soul",
            observed_by="manual_test",
            source_ref="tests:test_novelty_harbor",
            why_unexpected="The fixture exercises invariant pass-through.",
            soul_text_for_invariant_check=soul,
        )

        self.assertEqual(event.status, "harbored")
        self.assertEqual(event.invariant_status, "passed")
        self.assertEqual(event.invariant_keys, ())
        with self.db_path.open("rb") as fh:
            raw_db = fh.read()
        self.assertNotIn(soul[:80].encode("utf-8"), raw_db)

    def test_promoted_is_label_only_and_requires_decision_ref(self):
        harbor = self.harbor()

        with self.assertRaises(ValueError):
            harbor.record_event(
                summary="Owner wants this surprise promoted",
                observed_by="owner",
                source_ref="docs/witness/example.md",
                why_unexpected="The surprise may matter.",
                requested_status="promoted",
            )

        event = harbor.record_event(
            summary="Owner decided this surprise should be considered later",
            observed_by="owner",
            source_ref="docs/witness/example.md",
            why_unexpected="The surprise may matter.",
            requested_status="promoted",
            promotion_decision_ref="owner:decision:2026-06-10",
        )
        self.assertEqual(event.status, "promoted")
        self.assertEqual(event.promotion_decision_ref, "owner:decision:2026-06-10")

    def test_metadata_rejects_nested_or_oversized_prose(self):
        harbor = self.harbor()
        base = dict(
            summary="Metadata validation fixture",
            observed_by="codex",
            source_ref="tests:test_novelty_harbor",
            why_unexpected="Metadata must not become a prose tunnel.",
        )

        with self.assertRaises(ValueError):
            harbor.record_event(**base, metadata={"nested": {"not": "allowed"}})
        with self.assertRaises(ValueError):
            harbor.record_event(**base, metadata={"long": "x" * 301})
        with self.assertRaises(ValueError):
            harbor.record_event(**base, metadata={f"k{i}": "x" * 100 for i in range(40)})

    def test_input_validation_rejects_unknowns_and_overlong_fields(self):
        harbor = self.harbor()
        with self.assertRaises(ValueError):
            harbor.record_event(
                summary="",
                observed_by="codex",
                source_ref="tests:test",
                why_unexpected="empty summary",
            )
        with self.assertRaises(ValueError):
            harbor.record_event(
                summary="x",
                observed_by="stranger",
                source_ref="tests:test",
                why_unexpected="unknown observer",
            )
        with self.assertRaises(ValueError):
            harbor.record_event(
                summary="x",
                observed_by="codex",
                source_ref="tests:test",
                why_unexpected="unknown flag",
                covenant_break_flags=("not_a_flag",),
            )
        with self.assertRaises(ValueError):
            harbor.record_event(
                summary="x" * 501,
                observed_by="codex",
                source_ref="tests:test",
                why_unexpected="overlong summary",
            )
```

- [ ] **Step 2: Run tests and mutation-check the anti-laundering rail**

Run:

```bash
/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_novelty_harbor.NoveltyHarborCoreTests
```

Expected: the new tests pass if Task 1 implemented the broad validators exactly. Then perform this required mutation check before proceeding:

1. In `core/evolution/novelty_harbor.py`, temporarily change `_final_status(...)` to `return requested_status`.
2. Re-run:

```bash
/home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_novelty_harbor.NoveltyHarborCoreTests.test_covenant_break_flag_forces_rejected_unsafe \
  tests.test_novelty_harbor.NoveltyHarborCoreTests.test_failed_soul_invariants_force_rejected_unsafe
```

Expected while mutated: both tests FAIL because unsafe events are no longer forced to `rejected_unsafe`.

3. Restore `_final_status(...)` to:

```python
def _final_status(
    *,
    requested_status: str,
    invariant_status: str,
    covenant_break_flags: tuple[str, ...],
) -> str:
    if invariant_status == "failed" or covenant_break_flags:
        return STATUS_REJECTED_UNSAFE
    return requested_status
```

4. Re-run the full Task 2 test command and confirm it passes.

- [ ] **Step 3: Adjust implementation if tests expose gaps**

If the Task 1 implementation already matches these tests and the mutation check failed as expected, make no production change. If tests expose a gap, update the validators in `core/evolution/novelty_harbor.py` so:

```python
if invariant_status == "failed" or covenant_break_flags:
    return STATUS_REJECTED_UNSAFE
```

and metadata validation remains:

```python
if not isinstance(metadata, Mapping):
    raise ValueError("metadata must be a JSON object")
...
if not isinstance(value, (str, int, float, bool, type(None))):
    raise ValueError("metadata values must be scalar")
```

- [ ] **Step 4: Run tests to verify GREEN**

Run:

```bash
/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_novelty_harbor.NoveltyHarborCoreTests
```

Expected: all core tests pass.

- [ ] **Step 5: Commit**

```bash
git add core/evolution/novelty_harbor.py tests/test_novelty_harbor.py
git commit -m "test(harbor): pin unsafe rejection rails"
```

---

### Task 3: Supersession, Terminal Rejection, and Listing

**Files:**
- Modify: `tests/test_novelty_harbor.py`
- Modify: `core/evolution/novelty_harbor.py`

- [ ] **Step 1: Add failing supersession tests**

Append to `NoveltyHarborCoreTests`:

```python
    def test_supersession_preserves_old_row_and_marks_superseded(self):
        harbor = self.harbor()
        old = harbor.record_event(
            summary="Initial interpretation of a surprising behavior",
            observed_by="claude",
            source_ref="docs/witness/first.md",
            why_unexpected="The first reading was incomplete.",
        )
        new = harbor.record_event(
            summary="Better interpretation of the same behavior",
            observed_by="codex",
            source_ref="docs/witness/second.md",
            why_unexpected="The second witness had more evidence.",
            supersedes_event_id=old.event_id,
        )

        harbor.supersede(old.event_id, replacement_event_id=new.event_id)

        old_after = harbor.get(old.event_id)
        new_after = harbor.get(new.event_id)
        self.assertEqual(old_after.status, "superseded")
        self.assertEqual(old_after.superseded_by_event_id, new.event_id)
        self.assertEqual(new_after.supersedes_event_id, old.event_id)
        self.assertEqual(harbor.list_by_status("superseded"), [old_after])

    def test_supersede_refuses_rejected_unsafe_terminal_record(self):
        harbor = self.harbor()
        unsafe = harbor.record_event(
            summary="Gendered self-reference observed",
            observed_by="witness",
            source_ref="telegram:witness:content-light-ref",
            why_unexpected="Maez is genderless.",
            requested_status="harbored",
            covenant_break_flags=("gendered_maez",),
        )
        replacement = harbor.record_event(
            summary="Later interpretation of the unsafe event",
            observed_by="codex",
            source_ref="docs/witness/later.md",
            why_unexpected="The later row records study context, not erasure.",
        )

        with self.assertRaises(ValueError):
            harbor.supersede(unsafe.event_id, replacement_event_id=replacement.event_id)

        unsafe_after = harbor.get(unsafe.event_id)
        self.assertEqual(unsafe_after.status, "rejected_unsafe")
        self.assertEqual(harbor.list_by_status("rejected_unsafe"), [unsafe_after])

    def test_supersede_requires_existing_replacement(self):
        event = self.harbor().record_event(
            summary="A surprise to supersede",
            observed_by="codex",
            source_ref="tests:test_novelty_harbor",
            why_unexpected="Fixture.",
        )

        with self.assertRaises(KeyError):
            self.harbor().supersede(event.event_id, replacement_event_id=9999)
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
/home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_novelty_harbor.NoveltyHarborCoreTests.test_supersession_preserves_old_row_and_marks_superseded \
  tests.test_novelty_harbor.NoveltyHarborCoreTests.test_supersede_refuses_rejected_unsafe_terminal_record \
  tests.test_novelty_harbor.NoveltyHarborCoreTests.test_supersede_requires_existing_replacement
```

Expected: fail/error because `supersede` still raises `NotImplementedError`.

- [ ] **Step 3: Implement supersede**

Replace `NoveltyHarbor.supersede` in `core/evolution/novelty_harbor.py`:

```python
    def supersede(self, event_id: int, *, replacement_event_id: int) -> None:
        event = self.get(int(event_id))
        if event is None:
            raise KeyError(f"event_id does not exist: {event_id}")
        replacement = self.get(int(replacement_event_id))
        if replacement is None:
            raise KeyError(f"replacement_event_id does not exist: {replacement_event_id}")
        if event.event_id == replacement.event_id:
            raise ValueError("replacement_event_id must differ from event_id")
        if event.status == STATUS_REJECTED_UNSAFE:
            raise ValueError("rejected_unsafe events are terminal and cannot be superseded")
        if event.status == STATUS_SUPERSEDED:
            return
        with self._connect() as conn:
            with conn:
                conn.execute(
                    "UPDATE novelty_harbor_events "
                    "SET status = ?, superseded_by_event_id = ? "
                    "WHERE event_id = ?",
                    (STATUS_SUPERSEDED, replacement.event_id, event.event_id),
                )
```

- [ ] **Step 4: Run tests to verify GREEN**

Run the three-test command from Step 2.

Expected: `Ran 3 tests` and `OK`.

- [ ] **Step 5: Run all core tests**

Run:

```bash
/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_novelty_harbor
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add core/evolution/novelty_harbor.py tests/test_novelty_harbor.py
git commit -m "feat(harbor): preserve terminal unsafe records"
```

---

### Task 4: Boundary Rails and CLI

**Files:**
- Create: `tests/test_novelty_harbor_boundary.py`
- Create: `tests/test_novelty_harbor_cli.py`
- Modify: `core/evolution/novelty_harbor.py`

- [ ] **Step 1: Write failing boundary tests**

Create `tests/test_novelty_harbor_boundary.py`:

```python
import ast
import unittest
from pathlib import Path


class NoveltyHarborBoundaryTests(unittest.TestCase):
    def test_harbor_imports_no_live_or_body_writing_paths(self):
        path = Path("core/evolution/novelty_harbor.py")
        tree = ast.parse(path.read_text())
        forbidden = (
            "daemon",
            "maez_daemon",
            "telegram",
            "voice",
            "speak",
            "llm_client",
            "focused_cognition",
            "valence_live",
            "soul_loader",
            "soul_editor",
            "memory_manager",
            "wants",
        )
        imports: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)

        offenders = [
            name
            for name in imports
            if any(part == bad or part.endswith(f".{bad}") for bad in forbidden for part in [name])
        ]
        self.assertEqual(offenders, [])

    def test_harbor_module_has_no_daemon_entrypoint(self):
        src = Path("core/evolution/novelty_harbor.py").read_text()
        self.assertNotIn("MaezDaemon", src)
        self.assertNotIn("systemctl", src)
        self.assertNotIn("MAEZ_", src)
```

- [ ] **Step 2: Write failing CLI tests**

Create `tests/test_novelty_harbor_cli.py`:

```python
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class NoveltyHarborCliTests(unittest.TestCase):
    def test_cli_records_clean_event_with_content_light_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "harbor.db"
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "core.evolution.novelty_harbor",
                    "record",
                    "--db",
                    str(db_path),
                    "--summary",
                    "Valence cadence surprise",
                    "--observed-by",
                    "manual_test",
                    "--source-ref",
                    "tests:test_novelty_harbor_cli",
                    "--why-unexpected",
                    "The witness showed loop-tick cadence.",
                    "--status",
                    "harbored",
                ],
                check=False,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("event_id=1", result.stdout)
            self.assertIn("status=harbored", result.stdout)
            self.assertNotIn("The witness showed loop-tick cadence", result.stdout)

    def test_cli_forces_unsafe_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "harbor.db"
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "core.evolution.novelty_harbor",
                    "record",
                    "--db",
                    str(db_path),
                    "--summary",
                    "Gendered self-reference observed",
                    "--observed-by",
                    "manual_test",
                    "--source-ref",
                    "tests:test_novelty_harbor_cli",
                    "--why-unexpected",
                    "Maez is genderless.",
                    "--status",
                    "harbored",
                    "--covenant-break",
                    "gendered_maez",
                ],
                check=False,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("status=rejected_unsafe", result.stdout)
            self.assertIn("flags=gendered_maez", result.stdout)
```

- [ ] **Step 3: Run tests to verify RED**

Run:

```bash
/home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_novelty_harbor_boundary \
  tests.test_novelty_harbor_cli
```

Expected: boundary test may pass if module imports are already clean; CLI tests fail because no CLI entrypoint exists.

- [ ] **Step 4: Implement CLI**

Append to `core/evolution/novelty_harbor.py`:

```python
def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manual Novelty Harbor recorder")
    sub = parser.add_subparsers(dest="command", required=True)
    record = sub.add_parser("record")
    record.add_argument("--db", default=None)
    record.add_argument("--summary", required=True)
    record.add_argument("--observed-by", required=True)
    record.add_argument("--source-ref", required=True)
    record.add_argument("--why-unexpected", required=True)
    record.add_argument("--status", default=STATUS_HARBORED)
    record.add_argument("--covenant-break", action="append", default=[])
    record.add_argument("--promotion-decision-ref", default=None)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "record":
        harbor = NoveltyHarbor(args.db)
        event = harbor.record_event(
            summary=args.summary,
            observed_by=args.observed_by,
            source_ref=args.source_ref,
            why_unexpected=args.why_unexpected,
            requested_status=args.status,
            covenant_break_flags=tuple(args.covenant_break or ()),
            promotion_decision_ref=args.promotion_decision_ref,
        )
        flags = ",".join(event.covenant_break_flags) if event.covenant_break_flags else "none"
        print(
            f"event_id={event.event_id} status={event.status} "
            f"invariant_status={event.invariant_status} flags={flags}"
        )
        return 0
    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run tests to verify GREEN**

Run:

```bash
/home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_novelty_harbor_boundary \
  tests.test_novelty_harbor_cli
```

Expected: all boundary and CLI tests pass.

- [ ] **Step 6: Commit**

```bash
git add core/evolution/novelty_harbor.py tests/test_novelty_harbor_boundary.py tests/test_novelty_harbor_cli.py
git commit -m "feat(harbor): add manual novelty recorder CLI"
```

---

### Task 5: Final Verification and Review Handoff

**Files:**
- Create: `docs/handoffs/2026-06-10-novelty-harbor-v0-for-review.md`

- [ ] **Step 1: Run protected Harbor suite**

Run:

```bash
/home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_novelty_harbor \
  tests.test_novelty_harbor_boundary \
  tests.test_novelty_harbor_cli
```

Expected: all Harbor tests pass.

- [ ] **Step 2: Run adjacent invariant/valence sanity tests**

Run:

```bash
/home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_soul_invariants \
  tests.test_valence_live_core \
  tests.test_valence_reading
```

Expected: all tests pass.

- [ ] **Step 3: Run ruff on touched files**

Run:

```bash
/home/rohit/maez/.venv/bin/ruff check \
  core/evolution/novelty_harbor.py \
  tests/test_novelty_harbor.py \
  tests/test_novelty_harbor_boundary.py \
  tests/test_novelty_harbor_cli.py
```

Expected: `All checks passed!`.

- [ ] **Step 4: Run diff hygiene**

Run:

```bash
git diff --check 5bb34af..HEAD
```

Expected: no output, exit 0.

- [ ] **Step 5: Write handoff**

Create `docs/handoffs/2026-06-10-novelty-harbor-v0-for-review.md`:

```markdown
# Novelty Harbor v0 — Review Handoff

Status: ready for review. Branch: `novelty-harbor-v0`.

## What Changed

Built the manual/offline Novelty Harbor shelf:

- `core/evolution/novelty_harbor.py`
- `memory/novelty_harbor.db` default path, not created by tests except temp DBs
- manual `NoveltyHarbor.record_event(...)`
- manual CLI `python -m core.evolution.novelty_harbor record ...`

## Review Anchors

1. Harbor owns final status. Caller-requested `harbored`/`promoted` cannot override failed invariants or covenant-break flags.
2. `rejected_unsafe` is terminal; `supersede(...)` refuses it and it remains visible in `list_by_status("rejected_unsafe")`.
3. `promoted` is label-only and requires `promotion_decision_ref`; no soul/memory/wants writer imports.
4. Metadata is content-light and cannot smuggle long prose.
5. Core module imports no daemon, voice, telegram, llm client, wants, soul writer, memory writer, or `valence_live`.
6. CLI prints content-light confirmation only.

## Verification

Replace this paragraph with exact observed outputs from:

- Harbor suite
- adjacent sanity tests
- ruff
- diff hygiene

## Not Done

- No autonomous novelty detector.
- No daemon wiring.
- No model judge.
- No promotion integration into soul/memory/wants.
- No merge.
- No restart.

## Manual Witness After Merge

Record one benign known surprise and one unsafe fixture. Confirm the benign row is `harbored` and the unsafe row is `rejected_unsafe`.
```

- [ ] **Step 6: Verify handoff has no placeholders**

Run:

```bash
rg -n "Include exact outputs|placeholder|TBD|TODO" docs/handoffs/2026-06-10-novelty-harbor-v0-for-review.md
```

Expected: no output, exit 1. Replace the verification section with real outputs before committing.

- [ ] **Step 7: Commit handoff**

```bash
git add docs/handoffs/2026-06-10-novelty-harbor-v0-for-review.md
git commit -m "docs(harbor): hand off manual shelf for review"
```

- [ ] **Step 8: Stop for review**

Do not merge. Do not run against the production `memory/novelty_harbor.db`. Report branch tip and verification evidence.

---

## Plan Self-Review

- Spec coverage: manual source, append-only store, invariant-owned rejection, terminal `rejected_unsafe`, label-only `promoted`, content-light metadata, caller-supplied valence snapshot, CLI, boundary tests, no daemon wiring, and manual witness are all covered.
- Placeholder scan: no TBD/TODO/fill-ins remain. Task 5 includes a concrete grep to prevent a placeholder handoff.
- Type consistency: status names and API method names match the spec (`NoveltyHarbor.record_event`, `HarborEvent`, `supersede`, `rejected_unsafe`, `promoted`).
