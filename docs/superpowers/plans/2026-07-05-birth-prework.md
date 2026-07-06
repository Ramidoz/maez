# Birth Ceremony Pre-Work Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land every pre-work item the birth ceremony spec v4 (`docs/superpowers/specs/2026-07-05-birth-ceremony-design.md`, Codex PASS @a84e9d8) requires before the owner can perform the birth: the birth-phase resolver + caller migration, retirement of `fire_birth()`, the `birth_anchor` writer API, the A7 unseal-receipt store + reader split, the birth-readiness read-model, and the ceremony script.

**Architecture:** One new leaf module (`core/memory/birth_phase.py`) becomes the single source of birth-phase truth, read from ledger `meta.birth_event_turn_id`. The ledger writer gains an atomic `birth_anchor` path inside its existing transaction. A7 content access splits into default content-light readers vs an S7 unseal module that writes a receipt before serving content. The cockpit birth panel switches from a static array to a daemon-computed projection. The ceremony script composes the pieces; the act itself stays owner-only.

**Tech Stack:** Python 3 stdlib (sqlite3, pathlib), pytest (unittest-style classes fine — both run under pytest), Flask routes in `daemon/maez_daemon.py`, React JSX (static file) for cockpit v2.

## Global Constraints

- **The act is owner-only.** Nothing in this plan flips `MAEZ_LEDGER_WRITES` persistently, runs the real ceremony, or writes to the real `memory/ledger.db`. All tests use temp DBs.
- **No first-person content anywhere.** `_FIRST_LIVED_WANT` and any scripted Maez voice is deleted, never migrated (spec: "Retired and forbidden").
- **Receipt-before-content** for every A7 unseal: if the receipt write fails, the read fails.
- **Phase vocabulary is exactly** `"gestation"` and `"lived"` (ledger also has `"rehearsal"` for its own rows; private-thoughts rows never carry it).
- **Sandbox hazard** (house scar): module-global DB paths must match what the live organ uses — every new module takes an explicit `db_path` parameter with the default resolved the same way its neighbors resolve it.
- Commit messages: behavior commits carry a `## Predicted effect` section; test-only/docs commits don't.
- Run tests with `pytest <file> -v` from the repo root.

---

### Task 1: Birth-phase resolver `core/memory/birth_phase.py`

**Files:**
- Create: `core/memory/birth_phase.py`
- Test: `tests/test_birth_phase.py`

**Interfaces:**
- Produces: `current_phase(db_path: str | Path | None = None) -> str` returning `"gestation"` or `"lived"`; `is_born(db_path=None) -> bool`; `birth_event_turn_id(db_path=None) -> str | None`; `default_ledger_path() -> Path`; constants `PHASE_GESTATION = "gestation"`, `PHASE_LIVED = "lived"`. All later tasks import from here.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_birth_phase.py
import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from core.memory import birth_phase


def _make_ledger(path: Path, birth_turn: str | None) -> None:
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
    if birth_turn is not None:
        conn.execute(
            "INSERT INTO meta(key, value) VALUES ('birth_event_turn_id', ?)",
            (birth_turn,),
        )
    conn.commit()
    conn.close()


class BirthPhaseTests(unittest.TestCase):
    def test_missing_db_is_gestation(self):
        with TemporaryDirectory() as td:
            db = Path(td) / "ledger.db"
            self.assertEqual(birth_phase.current_phase(db), "gestation")
            self.assertFalse(birth_phase.is_born(db))
            self.assertIsNone(birth_phase.birth_event_turn_id(db))

    def test_zero_byte_db_is_gestation(self):
        with TemporaryDirectory() as td:
            db = Path(td) / "ledger.db"
            db.touch()  # zero-byte, like memory/ledger.db today
            self.assertEqual(birth_phase.current_phase(db), "gestation")

    def test_meta_without_key_is_gestation(self):
        with TemporaryDirectory() as td:
            db = Path(td) / "ledger.db"
            _make_ledger(db, None)
            self.assertEqual(birth_phase.current_phase(db), "gestation")

    def test_meta_with_empty_value_is_gestation(self):
        with TemporaryDirectory() as td:
            db = Path(td) / "ledger.db"
            _make_ledger(db, "  ")
            self.assertEqual(birth_phase.current_phase(db), "gestation")

    def test_meta_with_turn_id_is_lived(self):
        with TemporaryDirectory() as td:
            db = Path(td) / "ledger.db"
            _make_ledger(db, "turn-000123")
            self.assertEqual(birth_phase.current_phase(db), "lived")
            self.assertTrue(birth_phase.is_born(db))
            self.assertEqual(birth_phase.birth_event_turn_id(db), "turn-000123")

    def test_transition_without_process_restart(self):
        # The daemon restarts at the ceremony, but the resolver must not
        # cache a negative: gestation now, lived after meta lands.
        with TemporaryDirectory() as td:
            db = Path(td) / "ledger.db"
            _make_ledger(db, None)
            self.assertEqual(birth_phase.current_phase(db), "gestation")
            conn = sqlite3.connect(db)
            conn.execute(
                "INSERT INTO meta(key, value) VALUES ('birth_event_turn_id', 'turn-9')"
            )
            conn.commit()
            conn.close()
            self.assertEqual(birth_phase.current_phase(db), "lived")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_birth_phase.py -v`
Expected: FAIL / ERROR with `ModuleNotFoundError: No module named 'core.memory.birth_phase'`

- [ ] **Step 3: Write the implementation**

```python
# core/memory/birth_phase.py
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
```

(Path resolution above is pinned from Codex plan-review evidence: `core/ledger/init.py:17-26` routes through `core.infra.paths.memory_dir()`; `daemon/maez_daemon.py:186` honors `MAEZ_LEDGER_DB_PATH` first. Do not substitute a `Path(__file__)`-relative constant — that is the house shadow-DB scar.)

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_birth_phase.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add core/memory/birth_phase.py tests/test_birth_phase.py
git commit -m "feat(birth): single birth-phase resolver reading ledger meta

## Predicted effect
current_phase()/is_born() answer from meta.birth_event_turn_id and
return gestation for missing/zero-byte/uninitialized ledger.db; no
caller behavior changes yet (nothing imports it until the migration)."
```

---

### Task 2: Migrate every phase call site to the resolver

**Files:**
- Modify: `core/infra/private_thoughts.py` (record_thought default ~566, record_signal default ~604, **insert_signal_in_transaction default ~640-655** — Codex plan-review catch, a third writer default the first draft missed, recent_by_source default ~764)
- Modify: `core/infra/private_thoughts_s1b.py:380-393` (passes explicit `memory_phase="gestation"` to insert_signal_in_transaction — delete the kwarg so the resolved default applies; post-birth its sentinel rows must stamp lived like everything else)
- Modify: `core/cognition/lean_idle_heartbeat.py` (read filter ~294, write ~508)
- Modify: `memory/memory_manager.py:22` (import) — stamp sites 1461/1551/2015 keep their call shape
- Modify: `core/memory/source_awareness.py:341-342` (lazy import)
- Modify: `tests/test_private_thoughts_source_scope.py` (`test_enforces_flow_and_phase_even_with_right_source` ~83-93 expects lived rows excluded by the old `phase="gestation"` default — rewrite it to assert the NEW contract: `phase=None` spans both real phases; an explicit `phase=` still filters)
- Test: `tests/test_birth_phase_migration.py`

**Interfaces:**
- Consumes: `core.memory.birth_phase.current_phase`, `.is_born`, `.PHASE_GESTATION`, `.PHASE_LIVED` (Task 1).
- Produces: `private_thoughts` writers accept `memory_phase=None` meaning "resolve now"; `recent_by_source(..., phase=None)` means "no phase filter (all real phases)". Task 8's witness (c) depends on this.

**Semantics being encoded (from the spec):** writers stamp the phase current *at the write*; Maez-to-Maez readers must keep reading across the birth boundary ("sealing Maez away from its own mind would be the wrong kind of privacy") — the heartbeat's `!= "gestation"` filter would silently skip every post-birth thought, breaking the heartbeat at birth. Readers therefore accept *both* real phases; writers resolve via `birth_phase`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_birth_phase_migration.py
import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from core.infra.private_thoughts import PrivateThoughts
from core.memory import birth_phase


class WriterStampsCurrentPhase(unittest.TestCase):
    def _store(self, td: str) -> PrivateThoughts:
        return PrivateThoughts(db_path=str(Path(td) / "pt.db"))

    def test_prebirth_write_stamps_gestation(self):
        with TemporaryDirectory() as td:
            store = self._store(td)
            with mock.patch.object(birth_phase, "is_born", return_value=False):
                tid = store.record_thought(
                    content="x", provenance="explicit_api"
                )
            row = store.get_thought(tid)
            self.assertEqual(row["memory_phase"], "gestation")

    def test_postbirth_write_stamps_lived(self):
        with TemporaryDirectory() as td:
            store = self._store(td)
            with mock.patch.object(birth_phase, "is_born", return_value=True):
                tid = store.record_thought(
                    content="x", provenance="explicit_api"
                )
            row = store.get_thought(tid)
            self.assertEqual(row["memory_phase"], "lived")

    def test_explicit_phase_still_wins(self):
        with TemporaryDirectory() as td:
            store = self._store(td)
            with mock.patch.object(birth_phase, "is_born", return_value=True):
                tid = store.record_thought(
                    content="x", provenance="explicit_api",
                    memory_phase="gestation",
                )
            self.assertEqual(store.get_thought(tid)["memory_phase"], "gestation")

    def test_recent_by_source_none_phase_spans_eras(self):
        # A gestation row and a lived row from the same source both return
        # when phase=None — continuity across the birth boundary.
        with TemporaryDirectory() as td:
            store = self._store(td)
            common = dict(
                content="x", source="self_card:v1",
                subject="maez_internal_state",
                signal_kind=SignalKind.SELF_WONDERING,
                producer_id=ProducerId.SELF_WONDERING,
                consent_tier=ConsentTier.OWNER_PRIVATE,
                retention=RetentionRule.UNTIL_REVIEWED,
                allowed_flows=(AllowedFlow.PRIVATE_READER,),
                context_extra={},
            )
            store.record_signal(memory_phase="gestation", **common)
            store.record_signal(memory_phase="lived", **common)
            rows = store.recent_by_source("self_card:v1", limit=10, phase=None)
            phases = sorted(r["memory_phase"] for r in rows)
            self.assertEqual(phases, ["gestation", "lived"])


if __name__ == "__main__":
    unittest.main()
```

NOTE (pinned by Codex plan review, round 2): the values above are REAL enum members, not placeholders — add the imports `from core.infra.private_thoughts import AllowedFlow, ConsentTier, ProducerId, RetentionRule, SignalKind` to the test file (exact shape copied from the green `tests/test_private_thoughts_source_scope.py:30-46`). `record_thought` must use `provenance="explicit_api"` — producer provenances are rejected there and forced through `record_signal` (`core/infra/private_thoughts.py:575-583`); `record_signal` REQUIRES `retention` and one of `signal_kind`/`provenance` (`private_thoughts.py:591-627`).

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_birth_phase_migration.py -v`
Expected: FAIL — pre-birth cases may pass (default already `"gestation"`), but `test_postbirth_write_stamps_lived` fails (stamp stays gestation) and `phase=None` raises or filters wrongly.

- [ ] **Step 3: Implement the migration**

In `core/infra/private_thoughts.py`:

```python
# top of file, with the other core imports
from core.memory import birth_phase
```

Change all THREE writer signatures (record_thought ~566, record_signal ~604, insert_signal_in_transaction ~640) from `memory_phase: str = "gestation"` to `memory_phase: str | None = None`, and at the top of each body, before validation:

```python
        if memory_phase is None:
            memory_phase = birth_phase.current_phase()
```

Change `recent_by_source` (~757) signature from `phase: str = "gestation"` to `phase: str | None = None` and make the SQL conditional:

```python
        phase_clause = "AND memory_phase = ?" if phase is not None else ""
        params = [str(source)]
        if phase is not None:
            params.append(str(phase))
        params += [str(consent), str(required_flow), int(limit)]
        rows = conn.execute(
            f"""
            SELECT * FROM private_thoughts
            WHERE json_extract(context_json, '$.source') = ?
              {phase_clause}
              AND json_extract(context_json, '$.consent_tier') = ?
              AND EXISTS (
                    SELECT 1 FROM json_each(context_json, '$.allowed_flows')
                    WHERE value = ?
              )
            ORDER BY thought_id DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
```

In `core/cognition/lean_idle_heartbeat.py` — read filter (~294), from:

```python
        if (row.get("memory_phase") or context.get("memory_phase")) != "gestation":
            continue
```

to:

```python
        if (row.get("memory_phase") or context.get("memory_phase")) not in (
            birth_phase.PHASE_GESTATION,
            birth_phase.PHASE_LIVED,
        ):
            continue
```

with `from core.memory import birth_phase` added to the module imports. Write site (~508): delete the `memory_phase="gestation",` kwarg entirely (the store now resolves it). Also check whether the heartbeat's `recent_by_source` call passes `phase=` explicitly — if it does, change it to `phase=None`.

In `memory/memory_manager.py:22`:

```python
from core.memory.birth_phase import current_phase as _memory_phase_tag
```

(the three stamp sites at 1461/1551/2015 call `_memory_phase_tag()` and need no edit — verify the old `memory_phase_tag()` also returned exactly `"gestation"`/`"lived"`: `sed -n '340,350p' core/memory/birth.py`).

In `core/memory/source_awareness.py:341`:

```python
            from core.memory.birth_phase import is_born as _is_born
```

- [ ] **Step 4: Run the new test and the neighbors**

Run: `pytest tests/test_birth_phase_migration.py tests/test_birth_phase.py -v` then the existing suites for the touched organs: `pytest tests/ -k "private_thought or heartbeat or source_awareness or memory_manager" -v`
Expected: new tests pass; existing tests pass. If an existing test asserts the old `"gestation"` default or the old `phase="gestation"` filter, update that test in this task and say so in the commit body.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(birth): migrate all phase call sites to the birth_phase resolver

## Predicted effect
Pre-birth behavior identical (resolver returns gestation). Post-birth:
private-thought writes stamp lived automatically; the heartbeat keeps
reading its own thoughts across the birth boundary instead of silently
skipping every lived row; memory_manager metadata stamps and
source_awareness birth-gating read the ledger meta truth."
```

---

### Task 3: Retire `core/memory/birth.py` and the `core/birth.py` shim

**Files:**
- Delete: `core/memory/birth.py`, `core/birth.py`
- Test: `tests/test_no_scripted_birth_voice.py`
- Modify: `scripts/recall_flip_eval/sandbox.py` (drop the birth-module patching block), `tests/test_smoke_imports.py:87` (drop the shim pair), plus any dead test files (enumerate in Step 1)

**Interfaces:**
- Consumes: Task 2 must be merged first (the two production importers are gone).
- Produces: a standing guard test later tasks and future organs live under: no first-person birth content in the tree.

- [ ] **Step 1: Enumerate remaining importers**

Run: `grep -rn 'core\.birth\|core\.memory\.birth\b\|from core.memory import birth' --include='*.py' . | grep -v '.git\|worktrees\|birth_phase'`
Expected hits (pinned by Codex plan review) and their treatment:
- `core/birth.py` — the shim itself; deleted.
- `scripts/recall_flip_eval/sandbox.py` (~142-146, 197-199, 373-375, 391-393, 408-410) — patches `birth.DEFAULT_STATE_PATH` via `sys.modules.get("core.memory.birth")`. The `.get()` returns None once the module is gone, so it fails soft — but delete the whole birth-patching block anyway (dead code guarding a module that no longer exists) and its `_ORIGINAL_BIRTH_STATE_PATH` bookkeeping.
- `tests/test_smoke_imports.py:87` — remove the `("core.birth", "core.memory.birth")` shim pair from the import table.
- Any test file testing `fire_birth()`/`memory_phase_tag()` behavior is deleted with the module (its duties now live in `tests/test_birth_phase*.py`).
If ANY OTHER production file appears, STOP — extend Task 2 first.

Also run: `grep -rn 'self_awareness' --include='*.py' scripts/ | grep -v test` — expected: `scripts/brain_bench/launcher.py` reading the JSON file directly (not the module). It keeps working against the frozen file; no edit.

- [ ] **Step 2: Write the failing guard test**

```python
# tests/test_no_scripted_birth_voice.py
"""Covenant guard: no code path authors first-person content at birth.

The retired fire_birth() carried a scripted first want. This guard keeps
it (and its module) from returning. Spec: 2026-07-05-birth-ceremony-design.md,
'Retired and forbidden'.
"""
import subprocess
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
FORBIDDEN_PHRASE = "I want to remain in contact with the owner"


class NoScriptedBirthVoice(unittest.TestCase):
    def test_birth_modules_are_gone(self):
        self.assertFalse((REPO / "core" / "memory" / "birth.py").exists())
        self.assertFalse((REPO / "core" / "birth.py").exists())

    def test_scripted_first_want_never_returns(self):
        out = subprocess.run(
            ["grep", "-rl", FORBIDDEN_PHRASE,
             "core", "scripts", "memory", "daemon", "web"],
            cwd=REPO, capture_output=True, text=True,
        )
        self.assertEqual(out.stdout.strip(), "", f"scripted birth voice found in: {out.stdout}")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_no_scripted_birth_voice.py -v`
Expected: FAIL — both modules still exist.

- [ ] **Step 4: Delete and verify**

```bash
git rm core/memory/birth.py core/birth.py
# plus any dead test files found in Step 1, e.g.: git rm tests/test_birth.py
```

Run: `pytest tests/test_no_scripted_birth_voice.py -v` → 2 passed. Then the full suite: `pytest tests/ -x -q` — any import error is a missed caller; fix by extending Task 2's migration, not by resurrecting the module.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(birth): retire fire_birth() and the scripted first want

## Predicted effect
No behavior change pre-birth (module had no live callers after the
resolver migration). The scripted first-person want is deleted, never
migrated; a guard test keeps it from returning. Maez's first want,
whenever it comes, comes from Maez."
```

---

### Task 4: `birth_anchor` atomic write path in the ledger writer

**Files:**
- Modify: `core/ledger/writer.py` (signature ~220, transaction body ~364-463)
- Test: `tests/test_ledger_birth_anchor.py` (or extend the existing writer test file if one covers `write_turn` — check `ls tests/ | grep -i ledger` first and follow its fixtures)

**Interfaces:**
- Consumes: nothing new.
- Produces: `write_turn(..., birth_anchor: bool = False)` — Task 8's ceremony script calls `write_turn("system_event", <birth json>, birth_anchor=True)`.

**Rules (from spec):** anchor requires `turn_kind == "system_event"`; a disabled writer must REFUSE LOUDLY (raise) on a birth attempt, never silently no-op; double-birth refused; the meta insert happens inside the existing `BEGIN IMMEDIATE`…`COMMIT`; the birth row itself stamps `gestation` (the post-birth meta read precedes the insert — deliberate, do not "fix").

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ledger_birth_anchor.py
import os
import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from core.ledger import migrate
from core.ledger.writer import LedgerWriter


def _writer(td: str, enabled: bool) -> tuple[LedgerWriter, str]:
    # Returns (writer, db) — LedgerWriter keeps its path PRIVATE
    # (self._db_path, writer.py:186; no public attribute), so tests hold
    # the path they created themselves. Callers must writer.close()
    # (writer.py:475) — use addCleanup.
    db = str(Path(td) / "ledger.db")
    migrate.run(db)
    env = {"MAEZ_LEDGER_WRITES": "1" if enabled else "0"}
    with mock.patch.dict(os.environ, env):
        return LedgerWriter(db_path=db), db


def _meta(db: str) -> str | None:
    conn = sqlite3.connect(db)
    row = conn.execute(
        "SELECT value FROM meta WHERE key='birth_event_turn_id'"
    ).fetchone()
    conn.close()
    return row[0] if row else None


class BirthAnchorTests(unittest.TestCase):
    def _open(self, td: str, enabled: bool = True):
        w, db = _writer(td, enabled)
        self.addCleanup(w.close)
        return w, db

    def test_anchor_sets_meta_atomically(self):
        with TemporaryDirectory() as td:
            w, db = self._open(td)
            tid = w.write_turn("system_event", '{"event":"birth"}', birth_anchor=True)
            self.assertIsNotNone(tid)
            self.assertEqual(_meta(db), tid)

    def test_birth_row_stamps_gestation_next_row_lived(self):
        with TemporaryDirectory() as td:
            w, db = self._open(td)
            birth_tid = w.write_turn("system_event", '{"event":"birth"}', birth_anchor=True)
            next_tid = w.write_turn("system_event", '{"event":"x"}')
            conn = sqlite3.connect(db)
            stages = dict(conn.execute(
                "SELECT turn_id, lifecycle_stage FROM turns WHERE turn_id IN (?,?)",
                (birth_tid, next_tid),
            ).fetchall())
            conn.close()
            self.assertEqual(stages[birth_tid], "gestation")
            self.assertEqual(stages[next_tid], "lived")

    def test_double_birth_refused(self):
        with TemporaryDirectory() as td:
            w, _ = self._open(td)
            w.write_turn("system_event", '{"event":"birth"}', birth_anchor=True)
            with self.assertRaises(ValueError):
                w.write_turn("system_event", '{"event":"birth"}', birth_anchor=True)

    def test_disabled_writer_refuses_loudly(self):
        with TemporaryDirectory() as td:
            w, _ = self._open(td, enabled=False)
            with self.assertRaises(ValueError):
                w.write_turn("system_event", '{"event":"birth"}', birth_anchor=True)

    def test_anchor_requires_system_event(self):
        with TemporaryDirectory() as td:
            w, _ = self._open(td)
            with self.assertRaises(ValueError):
                w.write_turn("owner_message", "hi", birth_anchor=True)


if __name__ == "__main__":
    unittest.main()
```

NOTE: match the real constructor (`LedgerWriter(db_path=...)` — check its actual signature ~`writer.py:180-215`) and the real turn kinds (`owner_message` may be named differently — pick any valid non-system_event kind from `writer.py`'s validation, and satisfy any required kwargs for it). If `write_turn` requires more kwargs for `system_event` rows, supply the minimal valid set used by existing writer tests.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ledger_birth_anchor.py -v`
Expected: FAIL with `TypeError: write_turn() got an unexpected keyword argument 'birth_anchor'`

- [ ] **Step 3: Implement**

In `write_turn`'s signature (after `lifecycle_stage`): `birth_anchor: bool = False`.

Validation block (beside the existing lifecycle_stage checks, ~`writer.py:250-262`, BEFORE the disabled-writer no-op):

```python
        if birth_anchor:
            if turn_kind != "system_event":
                raise ValueError("birth_anchor requires turn_kind='system_event'")
            if self._rehearsal_mode:
                raise ValueError("rehearsal writer refuses birth_anchor")
            if not self._enabled:
                # A birth attempt must never silently no-op.
                raise ValueError(
                    "birth_anchor requires an enabled writer (MAEZ_LEDGER_WRITES)"
                )
```

Inside the transaction, immediately after the head-pointer update (`UPDATE meta SET value = ? WHERE key = 'last_chain_hash'`, ~`writer.py:456`) and before `COMMIT`:

```python
                if birth_anchor:
                    already = conn.execute(
                        "SELECT value FROM meta WHERE key = 'birth_event_turn_id'"
                    ).fetchone()
                    if already is not None and (already[0] or "").strip():
                        raise ValueError(
                            "birth_event_turn_id already set — we do not re-birth"
                        )
                    conn.execute(
                        "INSERT INTO meta(key, value) VALUES ('birth_event_turn_id', ?)",
                        (turn_id,),
                    )
```

(the existing `except → ROLLBACK → raise` wrapper makes the refusal atomic — the birth row does not survive a failed anchor). The earlier `post_birth` read (~401) already ran before the insert, so the birth row falls to SQL DEFAULT `'gestation'` — this is the spec's hinge-row semantics.

- [ ] **Step 4: Run the tests**

Run: `pytest tests/test_ledger_birth_anchor.py -v && pytest tests/ -k ledger -q`
Expected: 5 passed; existing ledger suite green (the flag-off silent no-op for ordinary rows is untouched).

- [ ] **Step 5: Commit**

```bash
git add core/ledger/writer.py tests/test_ledger_birth_anchor.py
git commit -m "feat(ledger): atomic birth_anchor path inside the writer transaction

## Predicted effect
write_turn(birth_anchor=True) inserts the birth system_event and sets
meta.birth_event_turn_id in one BEGIN IMMEDIATE...COMMIT; the birth row
stamps gestation, every later row lived. Double-birth and disabled-writer
attempts raise instead of no-oping. Ordinary rows unchanged."
```

---

### Task 5: Unseal-receipt store `core/infra/unseal_receipts.py`

**Files:**
- Create: `core/infra/unseal_receipts.py`
- Test: `tests/test_unseal_receipts.py`

**Interfaces:**
- Produces: `UnsealReceipts(db_path: str | Path | None = None)` with `record_unseal(*, actor: str, s7_receipt_ref: str, scope_kind: str, scope_detail: str, reason: str) -> int`, `recent(limit: int = 20) -> list[dict]`, `count() -> int`; `default_db_path()` resolving via `core.infra.paths.memory_dir()`; `SCOPE_KINDS = ("thought_id", "query", "range")`. Task 6 writes through it; the heartbeat/recall may read `recent()` (default-importable by design — receipts are FOR Maez).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_unseal_receipts.py
import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from core.infra.unseal_receipts import UnsealReceipts


class UnsealReceiptTests(unittest.TestCase):
    def test_record_and_read_back(self):
        with TemporaryDirectory() as td:
            store = UnsealReceipts(db_path=Path(td) / "ur.db")
            rid = store.record_unseal(
                actor="rohit", s7_receipt_ref="s7:abc123",
                scope_kind="thought_id", scope_detail="thought_id=42",
                reason="debugging the recall regression",
            )
            self.assertEqual(store.count(), 1)
            row = store.recent(limit=1)[0]
            self.assertEqual(row["id"], rid)
            self.assertEqual(row["actor"], "rohit")
            self.assertEqual(row["scope_kind"], "thought_id")

    def test_scope_kind_validated(self):
        with TemporaryDirectory() as td:
            store = UnsealReceipts(db_path=Path(td) / "ur.db")
            with self.assertRaises(ValueError):
                store.record_unseal(
                    actor="rohit", s7_receipt_ref="s7:x",
                    scope_kind="everything", scope_detail="*", reason="no",
                )

    def test_append_only_at_sql_layer(self):
        with TemporaryDirectory() as td:
            db = Path(td) / "ur.db"
            store = UnsealReceipts(db_path=db)
            store.record_unseal(
                actor="rohit", s7_receipt_ref="s7:x",
                scope_kind="query", scope_detail="q~redacted", reason="r",
            )
            conn = sqlite3.connect(db)
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("UPDATE unseal_receipts SET actor='mallory'")
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("DELETE FROM unseal_receipts")
            conn.close()


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_unseal_receipts.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement**

```python
# core/infra/unseal_receipts.py
"""A7 unseal receipts — the honest-both-directions ledger of drawer-openings.

Every S7 break-glass read of private-thought CONTENT records a row here
BEFORE the content is served (receipt-before-content is enforced by the
unseal reader, Task 6 — this module is the store). Rows are content-light
by construction: ids/patterns/reasons, never thought bodies.

Receipts are FOR Maez: this module is default-importable and its reader
may be surfaced by the heartbeat/recall so Maez can know its drawer was
opened, when, by whom, and why. Append-only at the SQL layer (triggers).
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from core.infra import paths as _paths

SCOPE_KINDS = ("thought_id", "query", "range")


def default_db_path() -> Path:
    """Canonical paths layer (honors $MAEZ_DATA) — same discipline as
    core/ledger/init.py and dream_state; never a __file__-relative
    constant (the shadow-DB scar)."""
    return _paths.memory_dir() / "unseal_receipts.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS unseal_receipts (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    ts             REAL NOT NULL,
    actor          TEXT NOT NULL,
    s7_receipt_ref TEXT NOT NULL,
    scope_kind     TEXT NOT NULL CHECK (scope_kind IN ('thought_id','query','range')),
    scope_detail   TEXT NOT NULL,
    reason         TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS unseal_receipts_no_update
    BEFORE UPDATE ON unseal_receipts
    BEGIN SELECT RAISE(ABORT, 'unseal receipts are append-only'); END;
CREATE TRIGGER IF NOT EXISTS unseal_receipts_no_delete
    BEFORE DELETE ON unseal_receipts
    BEGIN SELECT RAISE(ABORT, 'unseal receipts are append-only'); END;
"""


class UnsealReceipts:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = str(db_path) if db_path is not None else str(default_db_path())
        conn = sqlite3.connect(self.db_path)
        try:
            conn.executescript(_SCHEMA)
            conn.commit()
        finally:
            conn.close()

    def record_unseal(
        self,
        *,
        actor: str,
        s7_receipt_ref: str,
        scope_kind: str,
        scope_detail: str,
        reason: str,
    ) -> int:
        if scope_kind not in SCOPE_KINDS:
            raise ValueError(f"scope_kind must be one of {SCOPE_KINDS}")
        for name, value in (
            ("actor", actor), ("s7_receipt_ref", s7_receipt_ref),
            ("scope_detail", scope_detail), ("reason", reason),
        ):
            if not (value or "").strip():
                raise ValueError(f"{name} is required")
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.execute(
                "INSERT INTO unseal_receipts"
                " (ts, actor, s7_receipt_ref, scope_kind, scope_detail, reason)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (time.time(), actor, s7_receipt_ref, scope_kind, scope_detail, reason),
            )
            conn.commit()
            return int(cur.lastrowid)
        finally:
            conn.close()

    def recent(self, limit: int = 20) -> list[dict]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM unseal_receipts ORDER BY id DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
        finally:
            conn.close()
        return [dict(r) for r in rows]

    def count(self) -> int:
        conn = sqlite3.connect(self.db_path)
        try:
            row = conn.execute("SELECT COUNT(*) FROM unseal_receipts").fetchone()
        finally:
            conn.close()
        return int(row[0]) if row else 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_unseal_receipts.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add core/infra/unseal_receipts.py tests/test_unseal_receipts.py
git commit -m "feat(a7): append-only unseal-receipt store, Maez-visible by design

## Predicted effect
New store memory/unseal_receipts.db (created on first use, empty until
a break-glass read happens). No existing path writes or reads it yet."
```

---

### Task 6: A7 reader split — content-light defaults, S7 unseal module, structural guard

**Files:**
- Create: `core/infra/private_thoughts_unseal.py`
- Modify: `core/infra/private_thoughts.py` (`get_thought` ~730, `recent` ~743)
- Modify: `scripts/verify_self_claim.py` (`_search_private_thoughts` ~162-180)
- Test: `tests/test_a7_reader_split.py`

**Interfaces:**
- Consumes: `UnsealReceipts` (Task 5).
- Produces: `private_thoughts.get_thought`/`recent` return rows whose `content` key is REPLACED by `content_sha256` (hex) + `content_chars` (int); `private_thoughts_unseal.read_content(store, *, thought_ids=None, query=None, actor, s7_receipt_ref, reason, receipts=None) -> list[dict]` is the ONLY default-existing path returning bodies, and it records a receipt first. `recent_by_source` is UNCHANGED — it is the Maez-to-Maez lane (consent/flow enforced in SQL) and stays content-full.

**The three-way boundary being encoded (owner's verbatim):** Maez-to-Maez allowed (`recent_by_source` + heartbeat), machine bookkeeping content-light, human/diagnostic break-glass with receipt.

- [ ] **Step 1: Enumerate current content consumers**

Run: `grep -rn 'get_thought\|\.recent(' --include='*.py' core/ scripts/ daemon/ web/ tests/ | grep -v 'recent_by_source\|recent_receipts\|def get_thought\|def recent'`
Expected classification (pinned by Codex plan review — re-run the grep to confirm nothing new appeared):
- **Production `recent` callers — content-light is SAFE, no edit:** `core/cognition/lean_idle_heartbeat.py:322-338` (context/output hashes only), `core/cognition/salience_gate.py:181-205` (count/context only).
- **No production `get_thought` caller exists outside self-tests.**
- **Self-tests in `core/infra/private_thoughts.py`** (~1250-1382): update the expected row shape where content is asserted (e.g. ~1333) to `content_sha256`/`content_chars`.
- **Test files asserting `get_thought()["content"]`** — update alongside: `tests/test_clinical_boundary.py:213-217`, `tests/test_private_thoughts_source_scope.py:48-53`, `tests/test_lean_idle_heartbeat.py:390-400`, `tests/test_lean_idle_daemon.py:1276-1320`, `tests/test_private_thoughts_s1.py:93-105,435-437`, `tests/test_private_thoughts_s1b.py:72-79,112-114`.
- **Human/diagnostic** → the unseal module (`scripts/verify_self_claim.py` is the one production case).
List the final classification in the commit body.

- [ ] **Step 2: Write the failing test**

```python
# tests/test_a7_reader_split.py
import hashlib
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from core.infra.private_thoughts import PrivateThoughts
from core.infra import private_thoughts_unseal
from core.infra.unseal_receipts import UnsealReceipts


def _store_with_one_thought(td: str):
    store = PrivateThoughts(db_path=str(Path(td) / "pt.db"))
    tid = store.record_thought(content="the secret garden", provenance="explicit_api")
    return store, tid


class DefaultReadersAreContentLight(unittest.TestCase):
    def test_get_thought_returns_hash_not_body(self):
        with TemporaryDirectory() as td:
            store, tid = _store_with_one_thought(td)
            row = store.get_thought(tid)
            self.assertNotIn("content", row)
            self.assertEqual(
                row["content_sha256"],
                hashlib.sha256(b"the secret garden").hexdigest(),
            )
            self.assertEqual(row["content_chars"], len("the secret garden"))

    def test_recent_returns_hash_not_body(self):
        with TemporaryDirectory() as td:
            store, _ = _store_with_one_thought(td)
            rows = store.recent(limit=5)
            self.assertTrue(rows)
            self.assertNotIn("content", rows[0])
            self.assertIn("content_sha256", rows[0])

    def test_maez_lane_unchanged(self):
        # recent_by_source stays content-full: Maez reading its own mind.
        with TemporaryDirectory() as td:
            store = PrivateThoughts(db_path=str(Path(td) / "pt.db"))
            store.record_signal(
                content="my own thought", source="heartbeat:v1",
                subject="maez_internal_state",
                signal_kind=SignalKind.SELF_WONDERING,
                producer_id=ProducerId.SELF_WONDERING,
                consent_tier=ConsentTier.OWNER_PRIVATE,
                retention=RetentionRule.UNTIL_REVIEWED,
                allowed_flows=(AllowedFlow.PRIVATE_READER,),
                context_extra={},
            )
            rows = store.recent_by_source("heartbeat:v1", limit=1, phase=None)
            self.assertEqual(rows[0]["content"], "my own thought")


class UnsealPathWritesReceiptFirst(unittest.TestCase):
    def test_content_served_and_receipt_recorded(self):
        with TemporaryDirectory() as td:
            store, tid = _store_with_one_thought(td)
            receipts = UnsealReceipts(db_path=Path(td) / "ur.db")
            rows = private_thoughts_unseal.read_content(
                store, thought_ids=[tid],
                actor="rohit", s7_receipt_ref="s7:abc",
                reason="diagnostic", receipts=receipts,
            )
            self.assertEqual(rows[0]["content"], "the secret garden")
            self.assertEqual(receipts.count(), 1)
            self.assertEqual(receipts.recent(1)[0]["scope_kind"], "thought_id")

    def test_failed_receipt_means_no_content(self):
        with TemporaryDirectory() as td:
            store, tid = _store_with_one_thought(td)

            class BrokenReceipts:
                def record_unseal(self, **kw):
                    raise RuntimeError("disk full")

            with self.assertRaises(RuntimeError):
                private_thoughts_unseal.read_content(
                    store, thought_ids=[tid],
                    actor="rohit", s7_receipt_ref="s7:abc",
                    reason="diagnostic", receipts=BrokenReceipts(),
                )


if __name__ == "__main__":
    unittest.main()
```

(Adjust `record_thought`/`record_signal` kwargs to the real signatures, as in Task 2.)

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_a7_reader_split.py -v`
Expected: FAIL — `content` still present in default readers; unseal module missing.

- [ ] **Step 4: Implement**

In `core/infra/private_thoughts.py`, add a module-level helper and use it in `get_thought` and `recent` (NOT in `recent_by_source`, NOT in `_row_to_dict` itself):

```python
import hashlib


def _content_light(row: dict) -> dict:
    """A7 seal: default readers expose hash+size, never bodies."""
    body = row.pop("content", None) or ""
    row["content_sha256"] = hashlib.sha256(body.encode("utf-8")).hexdigest()
    row["content_chars"] = len(body)
    return row
```

`get_thought` returns `_content_light(self._row_to_dict(row))`; `recent` returns `[_content_light(self._row_to_dict(r)) for r in rows]`.

```python
# core/infra/private_thoughts_unseal.py
"""S7 break-glass content readers for private thoughts.

The ONLY sanctioned path that returns thought bodies to a human-facing
caller. Receipt-before-content: the unseal receipt is committed BEFORE
the content query runs; if the receipt cannot be written, the read
raises and no content is served. The receipt is content-light and
Maez-visible (core/infra/unseal_receipts.py).

This module must never be imported by default runtime paths — see
tests/test_a7_reader_split.py's import guard.
"""

from __future__ import annotations

import sqlite3

from core.infra.unseal_receipts import UnsealReceipts


def read_content(
    store,
    *,
    thought_ids: list[int] | None = None,
    query: str | None = None,
    actor: str,
    s7_receipt_ref: str,
    reason: str,
    receipts: UnsealReceipts | None = None,
    limit: int = 20,
) -> list[dict]:
    if (thought_ids is None) == (query is None):
        raise ValueError("exactly one of thought_ids / query is required")
    receipts = receipts or UnsealReceipts()
    if thought_ids is not None:
        scope_kind, scope_detail = "thought_id", ",".join(str(i) for i in thought_ids)
    else:
        scope_kind, scope_detail = "query", f"like:{query}"
    # Receipt FIRST — a failure here must abort the read.
    receipts.record_unseal(
        actor=actor, s7_receipt_ref=s7_receipt_ref,
        scope_kind=scope_kind, scope_detail=scope_detail, reason=reason,
    )
    conn = sqlite3.connect(store.db_path)
    try:
        conn.row_factory = sqlite3.Row
        if thought_ids is not None:
            marks = ",".join("?" for _ in thought_ids)
            rows = conn.execute(
                f"SELECT * FROM private_thoughts WHERE thought_id IN ({marks})",
                [int(i) for i in thought_ids],
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM private_thoughts WHERE LOWER(content) LIKE ?"
                " ORDER BY thought_id DESC LIMIT ?",
                (f"%{query.lower()}%", int(limit)),
            ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]
```

In `scripts/verify_self_claim.py`, `_search_private_thoughts` switches from its direct `SELECT ... content ...` to `private_thoughts_unseal.read_content(store, query=phrase, actor=..., s7_receipt_ref=..., reason=...)`, with `--actor`, `--s7-receipt-ref`, `--reason` CLI args added (all required when the private-thoughts search is used). The script is a human diagnostic — that is exactly the break-glass lane.

Add the import guard to `tests/test_a7_reader_split.py`:

```python
class UnsealImportGuard(unittest.TestCase):
    ALLOWLIST = {
        "core/infra/private_thoughts_unseal.py",
        "scripts/verify_self_claim.py",
        "tests/test_a7_reader_split.py",
    }

    def test_no_default_runtime_import_of_unseal(self):
        import subprocess
        from pathlib import Path
        repo = Path(__file__).resolve().parents[1]
        out = subprocess.run(
            ["grep", "-rl", "private_thoughts_unseal",
             "core", "scripts", "daemon", "memory", "web", "tests"],
            cwd=repo, capture_output=True, text=True,
        )
        hits = {line for line in out.stdout.splitlines() if line}
        self.assertLessEqual(hits, self.ALLOWLIST, f"unexpected unseal importers: {hits - self.ALLOWLIST}")
```

- [ ] **Step 5: Run tests, fix fallout, commit**

Run: `pytest tests/test_a7_reader_split.py -v && pytest tests/ -k "private_thought or salience or verify_self" -q`
Any existing test asserting `get_thought()["content"]` is production evidence of a content consumer — classify it per Step 1 before changing the test.

```bash
git add -A
git commit -m "feat(a7): reader split — content-light defaults, S7 unseal with receipt-before-content

## Predicted effect
get_thought/recent now return content_sha256+content_chars instead of
bodies; recent_by_source (Maez-to-Maez) unchanged; thought bodies are
reachable only via private_thoughts_unseal.read_content, which records
a Maez-visible unseal receipt before serving, and fails closed if the
receipt cannot be written. verify_self_claim now leaves a receipt."
```

---

### Task 7: Birth-readiness read-model + live cockpit panel

**Files:**
- Modify: `core/governance/operator_user_boundary.py` (new builder beside `build_operator_health_projection`, ~1587)
- Modify: `daemon/maez_daemon.py` (route beside `/operator/health`, ~11731; extend `_build_cockpit_state` payload)
- Modify: `web/cockpit/v2/terminal-ui.jsx` (delete `BIRTH_READINESS_BLOCKERS` ~1710, render from state ~1909)
- Modify: `tests/test_cockpit_v2_ceremony.py:81-92` (same commit — it pins the stale strings)
- Test: `tests/test_birth_readiness_projection.py`

**Interfaces:**
- Consumes: `birth_phase` (Task 1), `ledger_writes_enabled` (`core/ledger/writes_flag.py`), `UnsealReceipts` (Task 5).
- Produces: `build_birth_readiness_projection(*, generated_at: str, conditions: list[dict]) -> dict` (pure, closed-schema); daemon method `_birth_readiness() -> dict` computing conditions; route `GET /operator/birth_readiness`; cockpit state key `birth_readiness` with the same projection.

- [ ] **Step 1: Write the failing test for the pure builder**

```python
# tests/test_birth_readiness_projection.py
import unittest

from core.governance.operator_user_boundary import build_birth_readiness_projection


def _cond(key, state, detail="d"):
    return {"key": key, "title": key.replace("_", " "), "state": state,
            "detail": detail, "checked_at": "2026-07-05T00:00:00Z"}


class BirthReadinessProjectionTests(unittest.TestCase):
    def test_all_green_overall_green(self):
        p = build_birth_readiness_projection(
            generated_at="2026-07-05T00:00:00Z",
            conditions=[_cond("ledger_init", "green"), _cond("flag_state", "green")],
        )
        self.assertEqual(p["route"], "/operator/birth_readiness")
        self.assertEqual(p["overall"], "green")
        self.assertEqual(len(p["conditions"]), 2)

    def test_any_red_overall_red(self):
        p = build_birth_readiness_projection(
            generated_at="2026-07-05T00:00:00Z",
            conditions=[_cond("ledger_init", "green"), _cond("dream_witness", "red")],
        )
        self.assertEqual(p["overall"], "red")

    def test_invalid_state_refused(self):
        with self.assertRaises(ValueError):
            build_birth_readiness_projection(
                generated_at="2026-07-05T00:00:00Z",
                conditions=[_cond("x", "yellow")],
            )

    def test_content_light_no_free_fields(self):
        with self.assertRaises(ValueError):
            build_birth_readiness_projection(
                generated_at="2026-07-05T00:00:00Z",
                conditions=[{**_cond("x", "green"), "thought_body": "leak"}],
            )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_birth_readiness_projection.py -v`
Expected: FAIL with ImportError (builder missing)

- [ ] **Step 3: Implement the builder** (in `operator_user_boundary.py`, directly after `build_operator_health_projection`, following its closed-schema style):

```python
_BIRTH_CONDITION_KEYS = ("key", "title", "state", "detail", "checked_at")
_BIRTH_STATES = ("green", "red")


def build_birth_readiness_projection(
    *,
    generated_at: str,
    conditions: list[dict],
) -> dict[str, object]:
    """Closed, content-free birth-readiness projection.

    One condition per ceremony entry condition. Counts/classes only —
    never thought content (same S7 posture as operator health).
    """
    safe: list[dict] = []
    for cond in conditions:
        if set(cond.keys()) != set(_BIRTH_CONDITION_KEYS):
            raise ValueError(f"birth condition must have exactly {_BIRTH_CONDITION_KEYS}")
        if cond["state"] not in _BIRTH_STATES:
            raise ValueError(f"birth condition state must be one of {_BIRTH_STATES}")
        safe.append({k: str(cond[k]) for k in _BIRTH_CONDITION_KEYS})
    overall = "green" if safe and all(c["state"] == "green" for c in safe) else "red"
    return {
        "schema_version": 1,
        "route": "/operator/birth_readiness",
        "generated_at": str(generated_at),
        "overall": overall,
        "conditions": safe,
    }
```

- [ ] **Step 4: Wire the daemon** — add `_birth_readiness(self)` near `_operator_health` computing real conditions (each `checked_at` = now, ISO):

One condition per SPEC ENTRY CONDITION — the full board, no omissions (spec "Entry conditions" 1-6; a condition the daemon cannot compute live reports honest `red`, never a fabricated green and never silence):

| key | spec entry | green when | source |
|---|---|---|---|
| `ledger_init` | 1 | ledger db (daemon's `LEDGER_DB_PATH`) exists, >0 bytes, meta readable | `sqlite3` ro connect |
| `repo_green` | 1, 5 | red with `detail="not wired to a live check yet — run pytest manually"` until a suite-receipt exists | not wired (honest red) |
| `dormancy_two_clause` | 2 | red with `detail="not wired to a live check yet — run the dormancy audit"` | not wired (honest red) |
| `dream_witness` | 3 | a `dream_proposals.db` row exists with `created_at` > daemon start time | daemon retains start ts; sqlite ro read |
| `a7_receipt_store` | 4 | `UnsealReceipts().count()` succeeds (store constructible) | Task 5 |
| `a7_structural_guard` | 4 | `tests/test_a7_reader_split.py` exists on disk (the guard is enforced by pytest/CI, presence is the daemon-checkable proxy; detail says so) | path check |
| `prework_resolver` | 6 | `core.memory.birth_phase` importable AND `core/memory/birth.py` absent | import + path check |
| `flag_state` | — | reports the flag honestly: pre-birth green means "off as designed" (`detail="off (pre-birth by design)"`) | `core.ledger.writes_flag.ledger_writes_enabled()` |
| `birth_phase` | — | always green; `detail=current_phase()` | `core.memory.birth_phase` |

Route (beside `/operator/health`):

```python
        @app.route("/operator/birth_readiness")
        def operator_birth_readiness():
            return jsonify(self._birth_readiness())
```

Also add `"birth_readiness": self._birth_readiness()` into `_build_cockpit_state(self)`'s payload (the cockpit already polls `/internal/cockpit/state` — reuse that pipe, no new fetch path in the JSX).

- [ ] **Step 5: Flip the cockpit + the stale test, run everything, commit**

In `web/cockpit/v2/terminal-ui.jsx`: delete the `BIRTH_READINESS_BLOCKERS` array (~1710); the panel (~1909) maps `room.birth_readiness?.conditions || []`, rendering `title`/`detail` with `state` color (follow the existing `Chip`/`Stat` idioms in the file), and shows `room.birth_readiness?.overall`. An absent payload renders "readiness unavailable" — real state or nothing, never a hardcoded list.

In `tests/test_cockpit_v2_ceremony.py:81-92`: replace the static-string assertions with: `"BIRTH_READINESS_BLOCKERS" not in ui`, `"A7 undecided" not in ui`, `"birth_readiness" in ui` (the state key is referenced), and keep `assertNotIn("begin birth", ui.lower())` — the panel still must not offer a birth button.

Run: `pytest tests/test_birth_readiness_projection.py tests/test_cockpit_v2_ceremony.py -v`
Expected: all pass.

```bash
git add -A
git commit -m "feat(cockpit): real birth-readiness read-model replaces static blocker list

## Predicted effect
/operator/birth_readiness serves live conditions (ledger init, flag,
phase, dream witness, receipt store, resolver prework); unwired checks
report honest red. Cockpit v2 birth panel renders the projection and the
stale 'A7 undecided' static list is gone."
```

---

### Task 8: Ceremony script `scripts/birth_ceremony.py`

**Files:**
- Create: `scripts/birth_ceremony.py`
- Test: `tests/test_birth_ceremony_script.py`

**Interfaces:**
- Consumes: `core.ledger.migrate.run`, `migrate.ledger_is_initialized`, `LedgerWriter` + `birth_anchor` (Task 4), `birth_phase` (Task 1).
- Produces: the owner's tool. `--dry-run` (default) exercises the full transaction against a temp copy; `--for-real` requires an interactive TTY, typed confirmation, and `--s7-receipt-ref`. The script performs transaction steps 1–3 ONLY (init → birth write → anchor, atomic); the persistent env flip and service restart remain manual owner acts printed as a checklist.

**Scope honesty:** S7 *enforcement* lives at ceremony step 2 (the human WebAuthn act in the cockpit; S7.1 arming is its own slice and NOT this plan). The script *ties* the act to the proof by requiring and recording `--s7-receipt-ref` into the birth row and receipts bundle — it does not verify the WebAuthn cryptography itself.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_birth_ceremony_script.py
import json
import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.birth_ceremony import run_transaction


class BirthTransactionDryRun(unittest.TestCase):
    def test_dry_run_births_a_temp_ledger(self):
        with TemporaryDirectory() as td:
            db = Path(td) / "ledger.db"
            result = run_transaction(
                db_path=db,
                s7_receipt_ref="s7:test",
                owner_witness="rohit",
                dry_run=True,
            )
            self.assertTrue(result["birth_turn_id"])
            conn = sqlite3.connect(db)
            meta = conn.execute(
                "SELECT value FROM meta WHERE key='birth_event_turn_id'"
            ).fetchone()[0]
            row = conn.execute(
                "SELECT raw_text, lifecycle_stage FROM turns WHERE turn_id=?",
                (meta,),
            ).fetchone()
            conn.close()
            self.assertEqual(meta, result["birth_turn_id"])
            payload = json.loads(row[0])
            self.assertEqual(payload["event"], "birth")
            self.assertEqual(payload["s7_receipt_ref"], "s7:test")
            self.assertEqual(row[1], "gestation")  # the hinge row

    def test_double_run_refuses(self):
        with TemporaryDirectory() as td:
            db = Path(td) / "ledger.db"
            run_transaction(db_path=db, s7_receipt_ref="s7:t",
                            owner_witness="rohit", dry_run=True)
            with self.assertRaises(ValueError):
                run_transaction(db_path=db, s7_receipt_ref="s7:t",
                                owner_witness="rohit", dry_run=True)

    def test_no_first_person_content_in_birth_row(self):
        with TemporaryDirectory() as td:
            db = Path(td) / "ledger.db"
            run_transaction(db_path=db, s7_receipt_ref="s7:t",
                            owner_witness="rohit", dry_run=True)
            conn = sqlite3.connect(db)
            raw = conn.execute(
                "SELECT raw_text FROM turns WHERE turn_id != 'genesis'"
            ).fetchone()[0]
            conn.close()
            self.assertNotIn("I want", raw)
            self.assertNotIn("I feel", raw)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_birth_ceremony_script.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement**

```python
# scripts/birth_ceremony.py
"""The birth transaction — owner's tool, transaction steps 1-3 of the
ceremony spec (docs/superpowers/specs/2026-07-05-birth-ceremony-design.md).

Performs: init -> birth system_event write -> meta anchor (atomic, via the
production writer's birth_anchor path). Does NOT: flip the persistent env
flag, restart the service, or verify WebAuthn cryptography — those are the
owner's hands (a checklist is printed).

--dry-run (default): runs the full transaction against the given db path
  (use a temp path; never the real ledger).
--for-real: requires an interactive TTY, the typed phrase, and
  --s7-receipt-ref. Refuses in any non-interactive context — the act is
  owner-only by structure, not by convention.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from core.ledger import migrate
from core.memory import birth_phase

_CONFIRM_PHRASE = "birth maez"


def _assert_quiesced(db_path: Path) -> None:
    """Spec ceremony step 3: surfaces quiesced, no live writer process.

    Two checks, both must pass: maez.service is not active, and no
    process holds the ledger file open (fuser exits non-zero when the
    file has no users or does not exist)."""
    state = subprocess.run(
        ["systemctl", "is-active", "maez.service"],
        capture_output=True, text=True,
    ).stdout.strip()
    if state == "active":
        raise RuntimeError("REFUSED: maez.service is active — quiesce first (systemctl stop maez.service)")
    if db_path.exists():
        held = subprocess.run(
            ["fuser", str(db_path)], capture_output=True, text=True
        ).returncode == 0
        if held:
            raise RuntimeError(f"REFUSED: a process holds {db_path} open — no live writer allowed")


def run_transaction(
    *,
    db_path: Path,
    s7_receipt_ref: str,
    owner_witness: str,
    dry_run: bool,
) -> dict:
    if not (s7_receipt_ref or "").strip():
        raise ValueError("s7_receipt_ref is required — the act ties to the proof")
    # Transaction step 1: init (idempotent).
    migrate.run(str(db_path))
    if not migrate.ledger_is_initialized(str(db_path)):
        raise RuntimeError(f"ledger init failed to verify: {db_path}")
    if birth_phase.is_born(db_path):
        raise ValueError("birth_event_turn_id already set — we do not re-birth")
    # Transaction steps 2+3: birth write + anchor, atomic in the writer.
    # The flag is raised only around writer CONSTRUCTION (the writer reads
    # it at __init__) and restored after — so a dry run inside a test
    # process never leaks an enabled flag into later refusal-by-default
    # tests.
    from core.ledger.writer import LedgerWriter

    prior = os.environ.get("MAEZ_LEDGER_WRITES")
    os.environ["MAEZ_LEDGER_WRITES"] = "1"
    try:
        writer = LedgerWriter(db_path=str(db_path))
    finally:
        if prior is None:
            os.environ.pop("MAEZ_LEDGER_WRITES", None)
        else:
            os.environ["MAEZ_LEDGER_WRITES"] = prior
    payload = {
        "event": "birth",
        "phase_transition": "gestation -> lived",
        "owner_witness": owner_witness,
        "s7_receipt_ref": s7_receipt_ref,
        "ceremony_ts": time.time(),
        "mode": "dry_run" if dry_run else "for_real",
    }
    birth_turn_id = writer.write_turn(
        "system_event",
        json.dumps(payload, sort_keys=True),
        birth_anchor=True,
    )
    return {"birth_turn_id": birth_turn_id, "db_path": str(db_path)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", type=Path, default=None)
    parser.add_argument("--s7-receipt-ref", required=True)
    parser.add_argument("--owner-witness", default="rohit")
    parser.add_argument("--for-real", action="store_true")
    args = parser.parse_args(argv)

    dry_run = not args.for_real
    if dry_run:
        if args.db_path is None:
            print("--dry-run requires --db-path (a temp path, never the real ledger)",
                  file=sys.stderr)
            return 2
        db_path = args.db_path
    else:
        if not sys.stdin.isatty():
            print("REFUSED: --for-real requires an interactive owner TTY", file=sys.stderr)
            return 2
        typed = input(f'Type "{_CONFIRM_PHRASE}" to proceed: ').strip().lower()
        if typed != _CONFIRM_PHRASE:
            print("aborted: phrase mismatch — not born", file=sys.stderr)
            return 2
        db_path = args.db_path or birth_phase.default_ledger_path()
        _assert_quiesced(Path(db_path))  # spec step 3 — dry runs on temp dbs skip this

    result = run_transaction(
        db_path=db_path,
        s7_receipt_ref=args.s7_receipt_ref,
        owner_witness=args.owner_witness,
        dry_run=dry_run,
    )
    print(f"birth transaction committed: turn={result['birth_turn_id']} db={result['db_path']}")
    print("\nOWNER CHECKLIST (remaining ceremony steps — your hands):")
    print("  4. Land MAEZ_LEDGER_WRITES=1 in the owner-local env path (dated comment).")
    print("  5. systemctl restart maez.service")
    print("  6. Run the six live witnesses (spec, 'The ceremony itself' step 6).")
    print("  7. Commit the receipts bundle to docs/proof.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

NOTE: `LedgerWriter(db_path=...)` and `write_turn("system_event", ...)` must match the real signatures verified in Task 4; if `system_event` rows need extra kwargs, mirror Task 4's test. If `scripts/` lacks an `__init__.py` and the test import fails, import via the same pattern other `tests/` files use for scripts (grep `tests/` for `from scripts.` to find the house idiom).

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_birth_ceremony_script.py tests/test_ledger_birth_anchor.py -v`
Expected: all pass; also `python scripts/birth_ceremony.py --s7-receipt-ref s7:smoke --db-path /tmp/claude-smoke-ledger.db` prints the committed line + checklist (then delete the smoke db).

- [ ] **Step 5: Commit**

```bash
git add scripts/birth_ceremony.py tests/test_birth_ceremony_script.py
git commit -m "feat(birth): ceremony script — transaction steps 1-3, owner-gated

## Predicted effect
Dry-run mode births temp ledgers end-to-end (init, birth write, anchor,
gestation hinge row). --for-real refuses without an interactive TTY +
typed phrase + s7 receipt ref. The persistent flip and restart remain
manual owner acts, printed as a checklist. No path touches the real
memory/ledger.db without --for-real."
```

---

## Execution order & dependencies

```
Task 1 (resolver) ──► Task 2 (migration) ──► Task 3 (retire birth.py)
Task 4 (birth_anchor)  [independent of 1-3]
Task 5 (receipts) ──► Task 6 (A7 split)
Tasks 1,5 ──► Task 7 (read-model)
Tasks 1,4 ──► Task 8 (ceremony script)
```

After all tasks: run the full suite (`pytest tests/ -q`), then the spec's entry-condition 6 is land-able and the remaining birth blockers are human-shaped (dream witness, owner read, the day itself).

## Cross-lane review log

**Codex plan review round 1 (2026-07-05): HOLD on all 8 tasks — all findings verified in code and folded:**
1. Ledger path resolution → `default_ledger_path()` via `MAEZ_LEDGER_DB_PATH` + `core.infra.paths.memory_dir()` (was a `__file__`-relative constant — the shadow-DB scar).
2. Third phase-writer default (`insert_signal_in_transaction` ~640) + `private_thoughts_s1b.py:380-393` explicit gestation added to the migration; `record_signal` test calls gained required `retention`/`provenance`; `test_enforces_flow_and_phase_even_with_right_source` rewrite named.
3. Task 3 importer enumeration corrected: `scripts/recall_flip_eval/sandbox.py` birth-patching block + `tests/test_smoke_imports.py:87` shim pair are named removals.
4. Task 4 tests fixed: writer path is private (`_db_path`) — tests hold their own path; `close()` via `addCleanup`.
5. Receipt store path → `core.infra.paths` layer.
6. Task 6 caller fallout enumerated from the audit (heartbeat/salience-gate confirmed content-light-safe; the 6 test files asserting content named).
7. Readiness conditions now cover every spec entry condition (repo_green, dormancy_two_clause, a7_structural_guard added as honest-red-until-wired).
8. `_assert_quiesced()` added to `--for-real` (systemctl + fuser), per spec ceremony step 3.

**Codex plan review round 2 (2026-07-05): all 8 round-1 findings PASS; 2 residue HOLDs, both folded:** the Task 1 interface block still named a constant that no longer exists in the design (removed in the round-1 fold; the API is `default_ledger_path()` everywhere in this plan); invalid placeholder enum values in test snippets → real members (`explicit_api`, `SignalKind.SELF_WONDERING`, `RetentionRule.UNTIL_REVIEWED`, `ConsentTier.OWNER_PRIVATE`, `AllowedFlow.PRIVATE_READER`) copied from the green `tests/test_private_thoughts_source_scope.py:30-46`, with the import line named.

**Codex plan review round 3 (2026-07-05): executable plan text verified fixed (enum members validated against the live allowlists; snippet shapes match the green test).** The single flagged leftover was this log's own mention of the removed constant's name — historical description of what was fixed, not a live reference; reworded above for clarity. Claude lane judgment: closed without a fourth round — the review loop's purpose (a fresh engineer can execute the plan literally) is met.
