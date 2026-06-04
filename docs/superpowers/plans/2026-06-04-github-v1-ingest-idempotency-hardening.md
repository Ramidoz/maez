# GitHub v1 Ingest Idempotency Hardening (B+) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Close the mid-admission crash window so a fact is admitted exactly once even across a daemon crash, by making `run_ingest` **resume the oldest pending staged record before creating any new observation** — contained to `github_store` + `github_v1` + one read-only MemoryManager lookup, no `MemoryManager.store` change.

**Spec:** `docs/superpowers/specs/2026-06-04-github-v1-ingest-idempotency-hardening-design.md`.

**Reading list:** `core/information_limb/github_store.py` (the merged staging store + `promotion_state`/`body_memory_id`/`stage_repo_count`/`mark_admitted`), `core/information_limb/github_v1.py` (`run_ingest`, `ingest_repo_count`, `admit_repo_count_to_body`, `_ingest_record_id`), `memory/memory_manager.py` (the raw chroma collection + how metadata is queried), the merged ingest-trigger tests.

---

### Task 1: `github_store` — stable `created_at` + `oldest_pending()`

**Files:** Modify `core/information_limb/github_store.py`; Test `tests/test_github_v1_ingest_hardening.py` (create).

- [ ] **Step 1: Failing test**
```python
import tempfile, unittest
from pathlib import Path
class OldestPendingTests(unittest.TestCase):
    def test_oldest_pending_by_created_at(self):
        from core.information_limb.github_store import GithubStore
        with tempfile.TemporaryDirectory() as d:
            s = GithubStore(Path(d) / "github_v1.db"); s.initialize()
            s.stage_repo_count(ingest_record_id="ir-A", fetch_batch_id="fb-A",
                               repo_count=7, count_field="public_repos")
            s.stage_repo_count(ingest_record_id="ir-B", fetch_batch_id="fb-B",
                               repo_count=8, count_field="public_repos")
            p = s.oldest_pending()
            self.assertEqual(p.ingest_record_id, "ir-A")       # oldest created first
            self.assertEqual(p.repo_count, 7)
            self.assertEqual(p.count_field, "public_repos")
            self.assertEqual(p.fetch_batch_id, "fb-A")
            s.mark_admitted("ir-A", body_memory_id="mem-A")
            self.assertEqual(s.oldest_pending().ingest_record_id, "ir-B")  # A no longer pending
            s.mark_admitted("ir-B", body_memory_id="mem-B")
            self.assertIsNone(s.oldest_pending())
    def test_created_at_migrates_for_existing_rows(self):
        # a pre-hardening row (no created_at) gets created_at = updated_at on migrate
        ...  # implement: open an old-schema db, run initialize(), assert created_at populated
```
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** — add a `created_at TEXT` column to `github_provider_mirror` (set on `stage_repo_count` insert; on the migration path `_migrate_schema`, `UPDATE … SET created_at = updated_at WHERE created_at IS NULL`); bump `github_store_schema_version`. Add a `PendingRecord` (dataclass/namedtuple: `ingest_record_id, fetch_batch_id, repo_count, count_field, created_at`) and:
```python
def oldest_pending(self):
    with self._connect() as conn:   # the store's existing closing-managed connection
        row = conn.execute(
            "SELECT ingest_record_id, fetch_batch_id, repo_count, count_field, created_at "
            "FROM github_provider_mirror WHERE promotion_state='pending' "
            "ORDER BY created_at ASC, ingest_record_id ASC LIMIT 1"
        ).fetchone()
    if row is None:
        return None
    return PendingRecord(*row)
```
- [ ] **Step 4: Run → PASS. Step 5: Commit.**

---

### Task 2: `MemoryManager.owner_account_row_id_by_source_ref` (read-only, strict)

**Files:** Modify `memory/memory_manager.py`; Test add.

- [ ] **Step 1: Failing test**
```python
class SourceRefLookupTests(unittest.TestCase):
    def test_returns_id_only_for_owner_account_row(self):
        mm = _memory_manager_with_temp_collections()
        owner_id = mm.store(content="GitHub reports 7 public repositories on the owner's profile",
            cycle=0, provenance_source=_TOOL_OBSERVATION,
            egress_origin_class="owner_account_context",
            metadata={"source_ref": "github.s2:ir-1"})
        # a generic row sharing the source_ref but NOT owner_account_context must NOT match
        mm.store(content="unrelated", cycle=0, metadata={"source_ref": "github.s2:ir-1"})
        self.assertEqual(mm.owner_account_row_id_by_source_ref("github.s2:ir-1"), owner_id)
        self.assertIsNone(mm.owner_account_row_id_by_source_ref("github.s2:absent"))
```
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** — a **read-only** query on the raw collection filtered by `source_ref` AND `egress_origin_class == "owner_account_context"`; return the matching row's id (`memory_id`) or `None`. Use the existing chroma `get(where={...})` read path; **do not** touch `store()`/the write path. If multiple match (shouldn't, post-hardening), return the first deterministically.
- [ ] **Step 4: Run → PASS. Step 5: Commit.**

---

### Task 3: `github_v1.run_ingest` — resume-first rewrite

**Files:** Modify `core/information_limb/github_v1.py`; Test add.

- [ ] **Step 1: Failing tests** (the crash-window witnesses)
```python
from unittest import mock
class ResumeTests(unittest.TestCase):
    def _store(self):
        import tempfile; from pathlib import Path
        from core.information_limb.github_store import GithubStore
        self._d = tempfile.TemporaryDirectory()
        s = GithubStore(Path(self._d.name) / "github_v1.db"); s.initialize(); return s
    def test_crash_after_admit_resumes_no_double_write(self):
        from core.information_limb import github_v1
        store = self._store(); memory = mock.Mock(); memory.store.return_value = "mem-1"
        memory.owner_account_row_id_by_source_ref.return_value = None
        # Run 1: admit succeeds but mark_admitted "crashes" (patched to raise) → record left pending
        with mock.patch("core.information_limb.github_v1.github_limb.fetch_repo_count", return_value=7), \
             mock.patch.object(store, "mark_admitted", side_effect=RuntimeError("crash")):
            with self.assertRaises(RuntimeError):
                github_v1.run_ingest(limb_session=object(), store=store, memory=memory, fetch_batch_id="fb-A")
        # the body row now "exists" with the source_ref (simulate the lookup finding it)
        memory.owner_account_row_id_by_source_ref.return_value = "mem-1"
        # Run 2: fresh batch id, but resume finds the pending record + existing body row → no 2nd write
        r2 = github_v1.run_ingest(limb_session=object(), store=store, memory=memory, fetch_batch_id="fb-B")
        self.assertTrue(r2["resumed"]); self.assertFalse(r2["admitted"])
        self.assertEqual(memory.store.call_count, 1)   # exactly one body row across both runs
    def test_crash_after_stage_resumes_from_staged_count_no_refetch(self):
        from core.information_limb import github_v1
        store = self._store(); memory = mock.Mock(); memory.store.return_value = "mem-1"
        memory.owner_account_row_id_by_source_ref.return_value = None
        # Run 1: stage succeeds, admit "crashes" → pending, no body row
        with mock.patch("core.information_limb.github_v1.github_limb.fetch_repo_count", return_value=7), \
             mock.patch("core.information_limb.github_v1.admit_repo_count_to_body", side_effect=RuntimeError):
            with self.assertRaises(RuntimeError):
                github_v1.run_ingest(limb_session=object(), store=store, memory=memory, fetch_batch_id="fb-A")
        # Run 2: resume admits from the STAGED count, must NOT call fetch_repo_count
        with mock.patch("core.information_limb.github_v1.github_limb.fetch_repo_count",
                        side_effect=AssertionError("must not re-fetch on resume")):
            r2 = github_v1.run_ingest(limb_session=object(), store=store, memory=memory, fetch_batch_id="fb-B")
        self.assertTrue(r2["resumed"]); self.assertTrue(r2["admitted"])
        self.assertEqual(memory.store.call_count, 1)
    def test_no_pending_is_a_new_observation(self):
        from core.information_limb import github_v1
        store = self._store(); memory = mock.Mock(); memory.store.return_value = "mem"
        memory.owner_account_row_id_by_source_ref.return_value = None
        with mock.patch("core.information_limb.github_v1.github_limb.fetch_repo_count", return_value=7):
            r = github_v1.run_ingest(limb_session=object(), store=store, memory=memory, fetch_batch_id="fb-A")
        self.assertFalse(r["resumed"]); self.assertTrue(r["admitted"])
        for k in ("repo_count", "count_field", "login"): self.assertNotIn(k, r)
```
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** the resume-first `run_ingest` per spec §1:
```python
def run_ingest(*, limb_session, store, memory, fetch_batch_id: str) -> dict:
    pending = store.oldest_pending()
    if pending is not None:                       # RESUME — no fetch, no new batch
        irid = pending.ingest_record_id
        existing_id = memory.owner_account_row_id_by_source_ref(f"github.s2:{irid}")
        if existing_id is not None:
            store.mark_admitted(irid, body_memory_id=str(existing_id))
            return _result(irid, pending.fetch_batch_id, admitted=False, resumed=True)
        body_id = admit_repo_count_to_body(memory=memory, repo_count=pending.repo_count,
            count_field=pending.count_field, ingest_record_id=irid, fetch_batch_id=pending.fetch_batch_id)
        store.mark_admitted(irid, body_memory_id=str(body_id))
        return _result(irid, pending.fetch_batch_id, admitted=True, resumed=True)
    repo_count = github_limb.fetch_repo_count(limb_session)
    staged = ingest_repo_count(user_response={"public_repos": repo_count}, store=store,
                               fetch_batch_id=fetch_batch_id)
    irid = staged["ingest_record_id"]
    body_id = admit_repo_count_to_body(memory=memory, repo_count=repo_count,
        count_field="public_repos", ingest_record_id=irid, fetch_batch_id=fetch_batch_id)
    store.mark_admitted(irid, body_memory_id=str(body_id))
    return _result(irid, fetch_batch_id, admitted=True, resumed=False)

def _result(ingest_record_id, fetch_batch_id, *, admitted, resumed):
    return {"ok": True, "ingest_record_id": ingest_record_id, "fetch_batch_id": fetch_batch_id,
            "staged": True, "admitted": admitted, "state": "admitted", "resumed": resumed}
```
> `handle_ingest` must add `"resumed"` to `_INGEST_RESPONSE_KEYS` so it survives the content-free filter. The script's `_content_free_result` allowlist likewise gains `resumed` (still no count/login/token).
- [ ] **Step 4: Run → PASS. Step 5: Commit.**

---

### Task 4: Wire the result key + full-suite gate

**Files:** Modify `core/information_limb/github_v1.py` (`_INGEST_RESPONSE_KEYS`), `scripts/github_ingest.py` (allowlist); verification.

- [ ] **Step 1:** Add `"resumed"` to `_INGEST_RESPONSE_KEYS` and the script's content-free allowlist; a test asserts a resumed result survives the daemon-route filter and still leaks nothing (`repo_count`/`login`/token absent).
- [ ] **Step 2:** `.venv/bin/python -B -m unittest discover -s tests 2>&1 | tail -20` — apples-to-apples vs a fresh `main` run in the **asset-rich** checkout, not the worktree (`feedback_worktree_floor_confound`).
- [ ] **Step 3: Inventory re-check** — `tests.test_egress_external_fetch_inventory`; if `run_ingest`/daemon line moves shifted the external-fetch call sites, refresh the `DIRECT_CALLER_INVENTORY` daemon pins (only those that moved).
- [ ] **Step 4: Commit** any fixes.

---

## Self-Review

**Spec coverage:** §1 B+ algorithm → Task 3 (resume-first) + Tasks 1/2 (its inputs). §2 components → Tasks 1 (`created_at`+`oldest_pending`), 2 (read-only lookup, strict on source_ref+owner_account_context), 3 (`run_ingest`). §3 rails → Task 3/4 (content-free + `resumed`). §4 acceptance → Task 3 tests (crash-after-admit, crash-after-stage-no-refetch, no-pending) + Task 1 (oldest ordering) + Task 4 (content-free, no-store-change). ✓

**Owner edits folded:** `created_at` column + `(created_at, ingest_record_id)` ordering (Task 1); lookup requires `source_ref` AND `owner_account_context` (Task 2); id-returning `owner_account_row_id_by_source_ref` name everywhere (Tasks 2/3). ✓

**No shared-store change:** Task 2 is read-only; `MemoryManager.store` is untouched (assert via a source-contract check if convenient). ✓

**Implementer must verify:** the store's connection-context helper name (`self._connect()`/`closing(...)` — match the merged store); how the raw chroma collection is queried by metadata `where` (the existing read path); that `admit_repo_count_to_body` is patchable at the module path used in the tests; the inventory re-check (Task 4).
