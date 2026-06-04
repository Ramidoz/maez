# GitHub v1 Ingest Trigger — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** A minimal owner-gated, explicit, one-shot trigger that runs the merged GitHub v1 ingest live (repo count → staging → raw-memory taint), idempotent per `ingest_record_id`, content-free.

**Architecture:** Mirror the hardened-loopback handoff (`/internal/limb/github/session` + `core/information_limb/github_limb.py` `handoff_trusted`/`handle_handoff` + `scripts/github_connect.py`) for an ingest route + script with a **dedicated** `MAEZ_GITHUB_INGEST_TOKEN`. The orchestrator reuses the merged `github_v1.ingest_repo_count`/`admit_repo_count_to_body`; idempotency state lives **durably** in the staging store.

**Tech Stack:** Python 3, `unittest` (`.venv/bin/python -B -m unittest`, NOT pytest), the merged `core/information_limb/github_*`, `core/infra/secrets.py`.

**Spec:** `docs/superpowers/specs/2026-06-04-github-v1-ingest-trigger-design.md`.

**Reading list:** `core/information_limb/github_limb.py` (`fetch_identity`, `handoff_trusted`, `handle_handoff`, `GITHUB_HANDOFF_*`), `daemon/maez_daemon.py` ~9719 (`/internal/limb/github/session` route), `scripts/github_connect.py`, `core/information_limb/github_v1.py` (`ingest_repo_count`, `admit_repo_count_to_body`, `_ingest_record_id`), `core/information_limb/github_store.py`, `core/infra/secrets.py` (`SECRET_NAMES`), `tests/test_github_limb_handoff.py` (the auth-before-envelope shape).

---

### Task 1: Dedicated `MAEZ_GITHUB_INGEST_TOKEN` allowlisted

**Files:** Modify `core/infra/secrets.py`; Test `tests/test_github_v1_ingest_trigger.py` (create).

- [ ] **Step 1: Failing test**
```python
import unittest
class IngestTokenLoadableTests(unittest.TestCase):
    def test_ingest_token_is_classified_secret(self):
        from core.infra.secrets import is_secret_name
        self.assertTrue(is_secret_name("MAEZ_GITHUB_INGEST_TOKEN"))
    def test_ingest_token_allowlisted(self):
        from core.infra.secrets import SECRET_NAMES
        self.assertIn("MAEZ_GITHUB_INGEST_TOKEN", SECRET_NAMES)
```
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** — add `"MAEZ_GITHUB_INGEST_TOKEN"` to `SECRET_NAMES` in `core/infra/secrets.py` (next to `MAEZ_GITHUB_HANDOFF_TOKEN`).
- [ ] **Step 4: Run → PASS. Step 5: Commit.**

---

### Task 2: `github_limb.fetch_repo_count(session) -> int` (HTTP boundary, int only)

**Files:** Modify `core/information_limb/github_limb.py`; Test add to the trigger test file.

- [ ] **Step 1: Failing test**
```python
from unittest import mock
class FetchRepoCountTests(unittest.TestCase):
    def _session(self):
        from core.information_limb import github_limb
        now = 1000.0
        return github_limb.GithubSession("TOK", ["read:user"], now, now + 3600)
    def test_returns_only_public_repos(self):
        from core.information_limb import github_limb
        r = mock.Mock(); r.status_code = 200
        r.json.return_value = {"public_repos": 7, "login": "SECRET_LOGIN", "id": 1}
        with mock.patch.object(github_limb.requests, "get", return_value=r):
            n = github_limb.fetch_repo_count(self._session())
        self.assertEqual(n, 7)
        self.assertNotIn("SECRET_LOGIN", repr(n))
    def test_missing_field_raises(self):
        from core.information_limb import github_limb
        r = mock.Mock(); r.status_code = 200; r.json.return_value = {"login": "x"}
        with mock.patch.object(github_limb.requests, "get", return_value=r):
            with self.assertRaises(github_limb.GithubAuthError):
                github_limb.fetch_repo_count(self._session())
    def test_non_200_raises(self):
        from core.information_limb import github_limb
        r = mock.Mock(); r.status_code = 403
        with mock.patch.object(github_limb.requests, "get", return_value=r):
            with self.assertRaises(github_limb.GithubAuthError):
                github_limb.fetch_repo_count(self._session())
```
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** in `github_limb.py` (mirror `fetch_identity`'s request, but return the count):
```python
def fetch_repo_count(session: GithubSession) -> int:
    """GET /user; return ONLY public_repos (int). Discards login/id/everything
    else. Fail-closed: non-200 or missing field raises (never a fabricated count)."""
    try:
        resp = requests.get(_USER_URL, headers={
            "Authorization": f"Bearer {session.access_token}",
            "User-Agent": _USER_AGENT, "Accept": "application/vnd.github+json",
        }, timeout=_HTTP_TIMEOUT)
    except requests.RequestException as exc:
        raise GithubAuthError("GitHub /user unreachable") from exc
    if resp.status_code != 200:
        raise GithubAuthError(f"GitHub /user HTTP {resp.status_code}")
    count = resp.json().get("public_repos")
    if type(count) is not int or count < 0:
        raise GithubAuthError("GitHub /user missing integer public_repos")
    return count
```
- [ ] **Step 4: Run → PASS. Step 5: Commit.**

---

### Task 3: Durable admitted-state in the staging store (idempotency, crash-safe)

**Files:** Modify `core/information_limb/github_store.py`; Test add.

Context (owner note 1): the admission guard must key off **durable** staging state, so a restart between stage and admit resumes (finish or report partial), never double-writes.

- [ ] **Step 1: Failing test**
```python
import tempfile, unittest
from pathlib import Path
class DurablePromotionTests(unittest.TestCase):
    def test_promotion_state_persists_across_reinstantiation(self):
        from core.information_limb.github_store import GithubStore
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "github_v1.db"
            s = GithubStore(p); s.initialize()
            s.stage_repo_count(ingest_record_id="ir-1", fetch_batch_id="fb-1",
                               repo_count=7, count_field="public_repos")
            self.assertEqual(s.promotion_state("ir-1"), "pending")
            s.mark_admitted("ir-1", body_memory_id="mem-1")
            # re-open the DB: state is durable
            s2 = GithubStore(p); s2.initialize()
            self.assertEqual(s2.promotion_state("ir-1"), "admitted")
            self.assertEqual(s2.admitted_body_memory_id("ir-1"), "mem-1")
```
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** — add to `github_provider_mirror` (or a sibling table) durable columns `promotion_state` (default `"pending"`) and `body_memory_id` (nullable). `stage_repo_count` upserts keyed on `ingest_record_id` (idempotent; on conflict keep existing `promotion_state`/`body_memory_id`). Add `promotion_state(ingest_record_id) -> str` (returns `"pending"`/`"admitted"`/`"absent"`), `mark_admitted(ingest_record_id, body_memory_id)` (sets `admitted` + the id), `admitted_body_memory_id(ingest_record_id)`. Bump `github_store_schema_version`.
- [ ] **Step 4: Run → PASS. Step 5: Commit.**

---

### Task 4: `github_v1.run_ingest(...)` — orchestrator with durable idempotency

**Files:** Modify `core/information_limb/github_v1.py`; Test add.

- [ ] **Step 1: Failing test**
```python
from unittest import mock
class RunIngestTests(unittest.TestCase):
    def _real_store(self):
        import tempfile; from pathlib import Path
        from core.information_limb.github_store import GithubStore
        self._d = tempfile.TemporaryDirectory()
        s = GithubStore(Path(self._d.name) / "github_v1.db"); s.initialize(); return s
    def test_same_batch_admits_once_durably(self):
        from core.information_limb import github_v1
        store = self._real_store(); memory = mock.Mock(); memory.store.return_value = "mem-1"
        with mock.patch("core.information_limb.github_v1.github_limb.fetch_repo_count", return_value=7):
            r1 = github_v1.run_ingest(limb_session=object(), store=store, memory=memory, fetch_batch_id="fb-1")
            r2 = github_v1.run_ingest(limb_session=object(), store=store, memory=memory, fetch_batch_id="fb-1")
        self.assertTrue(r1["admitted"]); self.assertEqual(memory.store.call_count, 1)
        self.assertFalse(r2["admitted"])  # already admitted (durable)
        self.assertEqual(r1["ingest_record_id"], r2["ingest_record_id"])
        # content-free result
        for k in ("repo_count", "count_field", "login"):
            self.assertNotIn(k, r1)
    def test_different_batch_is_a_new_observation(self):
        from core.information_limb import github_v1
        store = self._real_store(); memory = mock.Mock(); memory.store.return_value = "mem"
        with mock.patch("core.information_limb.github_v1.github_limb.fetch_repo_count", return_value=7):
            github_v1.run_ingest(limb_session=object(), store=store, memory=memory, fetch_batch_id="fb-1")
            github_v1.run_ingest(limb_session=object(), store=store, memory=memory, fetch_batch_id="fb-2")
        self.assertEqual(memory.store.call_count, 2)
```
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** in `github_v1.py`:
```python
from core.information_limb import github_limb

def run_ingest(*, limb_session, store, memory, fetch_batch_id) -> dict:
    count = github_limb.fetch_repo_count(limb_session)
    count_field = "public_repos"
    staged = ingest_repo_count(           # policy → envelope → staging upsert
        user_response={"public_repos": count}, store=store, fetch_batch_id=fetch_batch_id)
    irid = staged["ingest_record_id"]
    state = store.promotion_state(irid)
    if state == "admitted":               # durable guard — crash-safe, no double-write
        return {"ok": True, "ingest_record_id": irid, "fetch_batch_id": fetch_batch_id,
                "staged": True, "admitted": False, "state": "admitted"}
    body_id = admit_repo_count_to_body(
        memory=memory, repo_count=count, count_field=count_field,
        ingest_record_id=irid, fetch_batch_id=fetch_batch_id)
    store.mark_admitted(irid, body_memory_id=body_id)
    return {"ok": True, "ingest_record_id": irid, "fetch_batch_id": fetch_batch_id,
            "staged": True, "admitted": True, "state": "admitted"}
```
> Content-free result (owner note 2): only `ok, ingest_record_id, fetch_batch_id, staged, admitted, state`. NEVER `repo_count`/`count_field`/login/url/token/raw status. Crash-resume: if staged-but-`pending` on a retry, this finishes the admission; if `admitted`, it's a no-op.
- [ ] **Step 4: Run → PASS. Step 5: Commit.**

---

### Task 5: Daemon ingest route (hardened loopback, dedicated token, gated)

**Files:** Modify `daemon/maez_daemon.py`; Test `tests/test_github_v1_ingest_route.py`.

- [ ] **Step 1: Failing test** — mirror `tests/test_github_limb_handoff.py`'s auth-before-envelope shape: a bad/absent `MAEZ_GITHUB_INGEST_TOKEN` → reject and `run_ingest` NOT called; an `Origin` header → reject; non-V1 mode / unauthed limb / no store → reject; good secret + V1 + available + store → calls `run_ingest`, returns the content-free allowlist (assert no `repo_count` in the response).
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** — add `GITHUB_INGEST_HEADER="X-Maez-Github-Ingest"`, `GITHUB_INGEST_TOKEN_ENV="MAEZ_GITHUB_INGEST_TOKEN"` and an `ingest_trusted(headers)` (mirror `handoff_trusted`: dedicated secret, constant-time, reject `Origin`) in `github_limb.py` or `github_v1.py`. Add the daemon route mirroring `/internal/limb/github/session`:
```python
@app.route("/internal/limb/github/ingest", methods=["POST"])
def github_limb_ingest():
    from core.information_limb import github_v1
    if not github_v1.ingest_trusted(request.headers):
        return {"ok": False, "error": "github_ingest_untrusted"}, 403
    if self._github_mode != GithubMode.V1:
        return {"ok": False, "error": "github_v1_not_enabled"}, 409
    if _GITHUB_LIMB.health().get("state") != "available":
        return {"ok": False, "error": "github_limb_unauthed"}, 409
    if self._github_store is None:
        return {"ok": False, "error": "github_store_unavailable"}, 409
    import uuid
    result = github_v1.run_ingest(
        limb_session=_GITHUB_LIMB._session, store=self._github_store,
        memory=self.memory, fetch_batch_id=f"fb-{uuid.uuid4().hex[:12]}")
    return result, 200
```
> `_record`/log lines for this route must be content-free (no count/login/token). Auth-before-action: the trust check runs before any limb read or store write.
- [ ] **Step 4: Run → PASS + daemon parse check. Step 5: Commit.**

---

### Task 6: `scripts/github_ingest.py` owner trigger

**Files:** Create `scripts/github_ingest.py` (mirror `scripts/github_connect.py`).

- [ ] **Step 1:** Implement — load `MAEZ_GITHUB_INGEST_TOKEN` via `load_secrets_for_process(required=set(), optional={"MAEZ_GITHUB_INGEST_TOKEN"})`, POST to `http://127.0.0.1:11435/internal/limb/github/ingest` with header `X-Maez-Github-Ingest`, print the content-free JSON result. No scheduler. `bash -n`-equivalent: `python -m py_compile`.
- [ ] **Step 2: Commit.**

---

### Task 7: Full-suite gate + inventory re-check

- [ ] **Step 1:** `.venv/bin/python -B -m unittest discover -s tests 2>&1 | tail -20` — no NEW failures vs a fresh `main` run (apples-to-apples in the asset-rich checkout, NOT the worktree — `feedback_worktree_floor_confound`).
- [ ] **Step 2: External-fetch inventory re-check.** The daemon edits (new route + `__init__`/import lines) may move the external-fetch call sites again. Run `.venv/bin/python -B -m unittest tests.test_egress_external_fetch_inventory`; if it fails, the daemon call-site line numbers drifted — update the `DIRECT_CALLER_INVENTORY` pins (only the daemon entries that actually moved). Do **not** skip this (it's the regression that hid in v1's floor).
- [ ] **Step 3: Commit** any inventory refresh.

---

## Self-Review

**Spec coverage:** §1 components → Tasks 2 (fetch_repo_count), 4 (run_ingest), 5 (route), 6 (script), 1 (token allowlist), 3 (store). §2 dedicated token → Tasks 1, 5. §3 idempotency → Tasks 3 (durable state) + 4 (guard) — folds owner note 1 (durable, crash-safe). §4 rails → Tasks 4/5 (content-free, scoped, fail-closed). §5 tests → each task. §6 acceptance → Tasks 1-6. ✓

**Owner notes folded:** (1) durable admitted-state in the store (Task 3) read by the guard (Task 4), crash-resume explicit — not in-process. (2) response allowlist pinned in Task 4 + asserted in Tasks 4/5 (no `repo_count`/`count_field`/login/url/token/raw status). ✓

**Type consistency:** `fetch_repo_count(session)->int` (T2) used in `run_ingest` (T4); `stage_repo_count`/`promotion_state`/`mark_admitted`/`admitted_body_memory_id` (T3) used in `run_ingest` (T4); `ingest_trusted(headers)` (T5) mirrors `handoff_trusted`; result keys `{ok, ingest_record_id, fetch_batch_id, staged, admitted, state}` consistent T4↔T5.

**Implementer must verify:** the live limb session accessor (`_GITHUB_LIMB._session` vs a public getter — prefer adding a `GithubLimb.session()` accessor if `_session` is private); that `ingest_repo_count` accepts the `{"public_repos": count}` shape (it does in v1); the daemon route's exact insertion point (search the `/internal/limb/github/session` route symbol, don't trust line numbers); re-run the inventory test (Task 7).
