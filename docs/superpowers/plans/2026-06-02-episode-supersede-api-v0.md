# EpisodeStore.supersede() API v0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Add a covenant-grade `EpisodeStore.supersede()` so retiring a memory is a labeled, provenance-recording operation instead of a raw SQL flip.

**Architecture:** Three nullable provenance columns via the existing `_MIGRATIONS` `ADD COLUMN` pattern, plus a fetch-first `supersede(episode_id, *, reason, superseded_by=None) -> bool` in `core/memory/episodes.py`. Never deletes (status flip only). Tests join the existing schema-story file.

**Tech Stack:** Python, SQLite, `unittest` (`.venv/bin/python -m unittest`, **NOT pytest**).

**Spec:** `docs/superpowers/specs/2026-06-02-episode-supersede-api-v0-design.md`

**Lane:** owner picks Codex vs inline. Cross-verify: fetch-first order, never-delete, all-three-provenance-fields preserved on no-op.

---

## Task 1: supersede() + provenance columns (TDD)

**Files:**
- Modify: `core/memory/episodes.py` (`_MIGRATIONS` tuple + new `supersede` method)
- Test: `tests/test_lived_memory_schema.py` (new `EpisodeStoreSupersede` class)

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_lived_memory_schema.py` (it already imports `tempfile`, `Path`, `unittest`):

```python
class EpisodeStoreSupersede(unittest.TestCase):
    """supersede() is the covenant-grade 'retire a memory' op: status flip +
    provenance, never delete. Mirrors RelationshipGraph.supersede semantics."""

    def setUp(self):
        from core.memory.episodes import EpisodeStore

        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self.store = EpisodeStore(self._tmp.name)
        self.ep_id = self.store.add(
            title="t", summary="s", participants=["Maez"],
            source_memory_ids=["raw-1"], source_kind="reflection",
        )

    def tearDown(self):
        Path(self._tmp.name).unlink(missing_ok=True)

    def test_supersede_unknown_id_raises_keyerror(self):
        with self.assertRaises(KeyError):
            self.store.supersede("ep-doesnotexist", reason="x")

    def test_supersede_active_stamps_provenance_and_excludes_from_active(self):
        ok = self.store.supersede(self.ep_id, reason="mislabeled provenance")
        self.assertTrue(ok)
        row = self.store.get(self.ep_id)
        self.assertIsNotNone(row, "superseded episode must NOT be deleted")
        self.assertEqual(row["status"], "superseded")
        self.assertEqual(row["superseded_reason"], "mislabeled provenance")
        self.assertIsNotNone(row["superseded_at"])
        self.assertIsNone(row["superseded_by"])
        active_ids = {e["id"] for e in self.store.list_active()}
        self.assertNotIn(self.ep_id, active_ids)

    def test_supersede_blank_reason_raises_valueerror_no_mutation(self):
        with self.assertRaises(ValueError):
            self.store.supersede(self.ep_id, reason="   ")
        self.assertEqual(self.store.get(self.ep_id)["status"], "active")

    def test_supersede_unknown_successor_raises_valueerror(self):
        with self.assertRaises(ValueError):
            self.store.supersede(self.ep_id, reason="r", superseded_by="ep-nope")
        self.assertEqual(self.store.get(self.ep_id)["status"], "active")

    def test_supersede_self_successor_raises_valueerror(self):
        with self.assertRaises(ValueError):
            self.store.supersede(self.ep_id, reason="r", superseded_by=self.ep_id)

    def test_supersede_with_valid_successor_stores_it(self):
        succ = self.store.add(
            title="t2", summary="s2", participants=["Maez"],
            source_memory_ids=["raw-2"], source_kind="reflection",
        )
        ok = self.store.supersede(self.ep_id, reason="replaced", superseded_by=succ)
        self.assertTrue(ok)
        self.assertEqual(self.store.get(self.ep_id)["superseded_by"], succ)

    def test_resupersede_returns_false_and_preserves_all_three_provenance_fields(self):
        succ = self.store.add(
            title="t2", summary="s2", participants=["Maez"],
            source_memory_ids=["raw-2"], source_kind="reflection",
        )
        self.assertTrue(self.store.supersede(self.ep_id, reason="first reason", superseded_by=succ))
        first = self.store.get(self.ep_id)

        # Second call with DIFFERENT reason/successor must be a no-op.
        self.assertFalse(self.store.supersede(self.ep_id, reason="SECOND reason", superseded_by=None))
        second = self.store.get(self.ep_id)

        # idempotent == no mutation: all three provenance fields unchanged.
        self.assertEqual(second["status"], "superseded")
        self.assertEqual(second["superseded_reason"], first["superseded_reason"])
        self.assertEqual(second["superseded_at"], first["superseded_at"])
        self.assertEqual(second["superseded_by"], first["superseded_by"])
```

- [ ] **Step 2: Run to verify FAIL**

Run: `.venv/bin/python -m unittest tests.test_lived_memory_schema.EpisodeStoreSupersede -v`
Expected: **FAIL** — `EpisodeStore` has no `supersede` method (`AttributeError`), and the `superseded_*` columns don't exist yet.

- [ ] **Step 3: Add the three migration columns**

In `core/memory/episodes.py`, extend `_MIGRATIONS` (currently authorship/memory_voice):

```python
_MIGRATIONS: tuple[str, ...] = (
    "ALTER TABLE episodes ADD COLUMN authorship TEXT",
    "ALTER TABLE episodes ADD COLUMN memory_voice TEXT",
    "ALTER TABLE episodes ADD COLUMN superseded_at TEXT",
    "ALTER TABLE episodes ADD COLUMN superseded_reason TEXT",
    "ALTER TABLE episodes ADD COLUMN superseded_by TEXT",
)
```

(Applied idempotently in `__init__` — the existing `try/except sqlite3.OperationalError` swallows "column already exists" on re-run / live db.)

- [ ] **Step 4: Implement supersede()**

Add the method to the `EpisodeStore` class (near `get`/`list_active`). `Optional` is already imported; `closing`, `_now_iso` are in scope:

```python
    def supersede(
        self,
        episode_id: str,
        *,
        reason: str,
        superseded_by: Optional[str] = None,
    ) -> bool:
        """Retire an episode: flip status to 'superseded' with provenance.
        Never deletes (get() still returns it; list_active() excludes it).

        Returns True if it superseded an active row, False if the row was
        already non-active (idempotent no-op, no mutation). Raises KeyError
        for an unknown episode_id, ValueError for a blank reason or an
        unverifiable/self successor.
        """
        row = self.get(episode_id)
        if row is None:
            raise KeyError(f"Cannot supersede unknown episode: {episode_id}")
        if row["status"] != "active":
            return False  # idempotent no-op — preserve existing provenance
        if not (reason or "").strip():
            raise ValueError("supersede requires a non-blank reason")
        if superseded_by is not None:
            if superseded_by == episode_id:
                raise ValueError("superseded_by must not be the episode itself")
            if self.get(superseded_by) is None:
                raise ValueError(
                    f"superseded_by must resolve to an existing episode: {superseded_by}"
                )
        with closing(self._connect()) as c:
            with c:
                c.execute(
                    "UPDATE episodes SET status='superseded', superseded_at=?, "
                    "superseded_reason=?, superseded_by=? WHERE id=?",
                    (_now_iso(), reason, superseded_by, episode_id),
                )
        return True
```

- [ ] **Step 5: Run to verify PASS**

Run: `.venv/bin/python -m unittest tests.test_lived_memory_schema.EpisodeStoreSupersede -v`
Expected: **all PASS** — unknown→KeyError; active→True+stamped+excluded+not-deleted; blank reason→ValueError (no mutation); unknown/self successor→ValueError; valid successor stored; re-supersede→False with all three provenance fields preserved.

- [ ] **Step 6: Commit**

```bash
git add core/memory/episodes.py tests/test_lived_memory_schema.py
git commit -m "feat(memory): EpisodeStore.supersede() — labeled covenant retirement

Retiring an episode is now a real provenance-recording operation, not a
raw SQL flip. supersede(episode_id, *, reason, superseded_by=None) does a
fetch-first check (unknown->KeyError; already-superseded->False no-op;
blank reason->ValueError; unverifiable/self successor->ValueError; active
->status='superseded' + superseded_at/reason/by). Never deletes: get()
still returns the row, list_active() excludes it. Three nullable columns
via the existing _MIGRATIONS pattern. No caller wiring; canary re-stamp
out of scope."
```

---

## Task 2: Regression

- [ ] **Step 1: Schema + episode tests green**

Run: `.venv/bin/python -m unittest tests.test_lived_memory_schema tests.test_reflection_synthesis tests.test_reflection_input_hygiene -v`
Expected: all PASS — the new columns/method don't disturb existing add/get/list_active/provenance behavior (existing rows keep `superseded_*` NULL).

- [ ] **Step 2: Floor both directions**

Run: `.venv/bin/python -m unittest discover -s tests 2>&1 | grep -E "^(Ran|FAILED|OK)"`
Expected: within ±2 of the `main` base (ambient judge-carveout family); name any branch-only header. No new deterministic failure.

- [ ] **Step 3: Confirm live-db forward-compat (manual note, no code)**

The migration adds 3 nullable columns to `memory/lived_episodes.db` on the next `EpisodeStore` init (daemon restart or any instantiation). Non-destructive; existing 11 active reflections + superseded canary keep `superseded_*` NULL. No action needed — documented for awareness.

---

## Self-Review

- **Spec coverage:** §2 method + fetch-first order → Task 1 Step 4 + tests (KeyError/False/ValueError×2/True); §2 never-delete → `test_supersede_active_*` (get returns, list_active excludes); §2 idempotent-no-mutation → `test_resupersede_*` (all three fields preserved — owner tightening); §3 three columns → Step 3; §4 tests → Step 1; §5 out-of-scope (no canary restamp, no caller wiring, no successor-creation) — respected.
- **Placeholder scan:** none — full method + 7 test methods are concrete.
- **Type consistency:** `supersede(episode_id, *, reason, superseded_by=None) -> bool`; columns `superseded_at`/`superseded_reason`/`superseded_by`; `get()` returns a `sqlite3.Row` (dict-like, `row["status"]`); `_now_iso()`/`closing`/`Optional` in scope (verified in episodes.py); `EpisodeStore(self._tmp.name)` + `add(...)` setUp mirrors `EpisodeStoreProvenanceColumns`.
- **One risk:** `get()` returns a `sqlite3.Row`; new rows expose `superseded_*` keys only after the migration runs — guaranteed because `__init__` applies `_MIGRATIONS` before any `get`. Existing dbs get the columns on next init (idempotent ADD COLUMN).
