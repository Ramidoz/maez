# GitHub v1 S2-Bounded Ingest — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ingest exactly one minimized GitHub fact (the owner's repo count) through an S2-bounded pipeline (policy → envelope → staging), admit it once into raw durable memory wearing the `owner_account_context` taint with traceability, prove the cloud door refuses it hermetically, and retire the legacy broad-PAT `github_skill` injection.

**Architecture:** Mirror the fully-built Calendar v1 information-limb precedent (`core/information_limb/calendar_*.py`, ADR 0033) — config mode enum, S2 envelope, connector policy, noncanonical staging store, connector+health — source-scoped to GitHub. The novel/GitHub-specific parts (legacy disablement at the daemon GitHub injection point, the one taint-railed body-admission with honest wording + traceability, the hermetic egress canary) are written in full. Read via the v0 `github_limb` device-flow `read:user` token, not the broad PAT.

**Tech Stack:** Python 3, `unittest` (run with `.venv/bin/python -B -m unittest`, **NOT pytest**), the `core/information_limb/calendar_*` templates, `memory/memory_manager.py` (the live taint rail), `core/egress` (gate/provenance), the v0 `core/information_limb/github_limb.py`.

**Spec:** `docs/superpowers/specs/2026-06-04-github-v1-s2-bounded-ingest-design.md` (acceptance rules 1-9 + honest-wording test).

---

## Reading list (do this first — the templates you mirror)

Read these before Task 1; the inherited tasks say "mirror file X" and you must have read X:
- `core/information_limb/calendar_v1_config.py` (mode enum + resolve) — Task 1 template.
- `core/information_limb/calendar_s2_envelope.py` (the canonical S2 envelope) — Task 3 template.
- `core/information_limb/calendar_connector_policy.py` (the deterministic S2 gate) — Task 4 template.
- `core/information_limb/calendar_store.py` (noncanonical staging store) — Task 5 template.
- `core/information_limb/calendar_v1.py` (connector + health states) — Task 6 template.
- `daemon/maez_daemon.py` ~2476-2493 (calendar mode/legacy gating in `__init__`), ~2689 (`self.github = GitHubSkill()`), ~4296-4303 (the legacy `_last_github_block` injection), ~4465-4475 (`signal_absence` pattern), ~7975-7983 (the `self._last_github_block = self.github.get_context_block()` fetch) — Tasks 2 & 9 targets.
- `memory/memory_manager.py` `store(...)` (now accepts `egress_origin_class`) and `format_for_prompt_provenanced(...)` — Tasks 7 & 8.
- `tests/test_owner_account_memory_taint_rail.py` (the canary shape to mirror) — Task 8 template.

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `core/information_limb/github_v1_config.py` | Create (mirror `calendar_v1_config.py`) | `GithubMode` enum + `resolve_github_mode`. |
| `core/information_limb/github_s2_envelope.py` | Create (mirror `calendar_s2_envelope.py`) | GitHub-scoped canonical S2 envelope; offline. |
| `core/information_limb/github_connector_policy.py` | Create (mirror `calendar_connector_policy.py`) | Deterministic S2 gate: `read:user`-only, owner-only, count-only. |
| `core/information_limb/github_store.py` | Create (mirror `calendar_store.py`) | Noncanonical staging store (`github_v1.db`), minimized row + content-free telemetry. |
| `core/information_limb/github_v1.py` | Create (mirror `calendar_v1.py`) | Connector + health + fetch→policy→envelope→staging→body-admission. |
| `daemon/maez_daemon.py` | Modify (~2476, ~2689, ~4296, ~7975) | Resolve GitHub mode; gate `github_skill` to legacy-only; honest `signal_absence`; wire v1. |
| `tests/test_github_v1_*.py` | Create | RED-first legacy-disablement, config, policy, envelope, store, body-admission, canary, honest-wording. |

---

### Task 1: `GithubMode` config (mirror `calendar_v1_config.py`)

**Files:** Create `core/information_limb/github_v1_config.py`; Test `tests/test_github_v1_config.py`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_github_v1_config.py
import unittest
from core.information_limb.github_v1_config import GithubMode, resolve_github_mode

class GithubModeTests(unittest.TestCase):
    def test_default_is_disabled(self):
        self.assertEqual(resolve_github_mode({}), GithubMode.DISABLED)
    def test_v1(self):
        self.assertEqual(resolve_github_mode({"MAEZ_GITHUB_MODE": "v1"}), GithubMode.V1)
    def test_legacy_requires_gate(self):
        with self.assertRaises(ValueError):
            resolve_github_mode({"MAEZ_GITHUB_MODE": "legacy_dev_only"})
        self.assertEqual(
            resolve_github_mode({"MAEZ_GITHUB_MODE": "legacy_dev_only",
                                 "MAEZ_GITHUB_ALLOW_LEGACY_TEST_MODE": "1"}),
            GithubMode.LEGACY_DEV_ONLY)
    def test_unsupported_raises(self):
        with self.assertRaises(ValueError):
            resolve_github_mode({"MAEZ_GITHUB_MODE": "bogus"})
```

- [ ] **Step 2: Run → FAIL** `.venv/bin/python -B -m unittest tests.test_github_v1_config -v` (module not found).

- [ ] **Step 3: Implement** — copy `core/information_limb/calendar_v1_config.py` to `github_v1_config.py` and apply deltas: `CalendarMode`→`GithubMode`; `MAEZ_CALENDAR_MODE`→`MAEZ_GITHUB_MODE`; `MAEZ_CALENDAR_ALLOW_LEGACY_TEST_MODE`→`MAEZ_GITHUB_ALLOW_LEGACY_TEST_MODE`; `resolve_calendar_mode`→`resolve_github_mode`; docstring → "GitHub v1 process-start mode resolution." Enum members unchanged (`DISABLED="disabled"`, `V1="v1"`, `LEGACY_DEV_ONLY="legacy_dev_only"`); resolve logic unchanged.

- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Commit** `git add core/information_limb/github_v1_config.py tests/test_github_v1_config.py && git commit -m "feat(github-v1): mode config (mirror calendar)"`

---

### Task 2: Legacy disablement — RED-FIRST (Calendar precedent: replace-not-wrap, disable first)

**Files:** Modify `daemon/maez_daemon.py` (~2476 init, ~2689 GitHubSkill, ~4296 injection, ~7975 fetch); Test `tests/test_github_v1_legacy_disablement.py`.

Context: today `self.github = GitHubSkill()` (daemon ~2689) reads the broad PAT; `self._last_github_block = self.github.get_context_block()` (~7981) fetches every 10 cycles; `if self._last_github_block:` (~4296) injects it. GitHub v1 must make all three **legacy-dev-only**: in `DISABLED`/`V1` mode the daemon must not instantiate/fetch/inject `github_skill`, and the broad PAT is not read.

- [ ] **Step 1: Write the failing test (source-contract guard, mirror the publish-retired guard)**

```python
# tests/test_github_v1_legacy_disablement.py
import inspect, unittest
from daemon import maez_daemon

class GithubLegacyDisablementTests(unittest.TestCase):
    def test_github_skill_is_gated_to_legacy_mode(self):
        src = inspect.getsource(maez_daemon)
        # GitHubSkill must only be instantiated under a legacy-mode guard.
        self.assertIn("_github_legacy_enabled", src)
        # The raw block injection + fetch must be guarded, not unconditional.
        self.assertNotIn("prompt += f\"\\n{self._last_github_block.text}\\n\"\n", src.replace(" ", ""))  # see note
    def test_resolve_github_mode_imported(self):
        src = inspect.getsource(maez_daemon)
        self.assertIn("resolve_github_mode", src)
        self.assertIn("GithubMode", src)
```

> Note: the second assertion is brittle as written; prefer asserting the injection is INSIDE an `if self._github_legacy_enabled:` block. Implement the test as: extract the cognition method source and assert `self._last_github_block` only appears within a `_github_legacy_enabled` guard. Use a regex that the `_last_github_block.text` usage is preceded by a `_github_legacy_enabled` guard in the same method. Keep it robust (see Task 8's source-contract style).

- [ ] **Step 2: Run → FAIL** (`_github_legacy_enabled` absent).

- [ ] **Step 3: Implement** — in `daemon/maez_daemon.py`:

(a) Imports (near the calendar imports ~82-84):
```python
from core.information_limb.github_v1_config import GithubMode, resolve_github_mode
```
and at module scope where `CALENDAR_MODE` is resolved, add:
```python
GITHUB_MODE = resolve_github_mode(os.environ)
```

(b) In `__init__` (near ~2476, mirroring the calendar block):
```python
        self._github_mode = GITHUB_MODE
        self._github_legacy_enabled = self._github_mode == GithubMode.LEGACY_DEV_ONLY
```

(c) Gate the GitHubSkill instantiation (~2689). Replace `self.github = GitHubSkill()` with:
```python
        # Legacy broad-PAT GitHub reader is dev-test-only (GitHub v1 S2 ingest
        # replaces it). In DISABLED/V1 mode it is not instantiated and the broad
        # PAT (MAEZ_GITHUB_TOKEN) is not read.
        self.github = GitHubSkill() if self._github_legacy_enabled else None
        self._last_github_block = None
```

(d) Gate the fetch (~7975-7983):
```python
            # GitHub — legacy reader only when explicitly in legacy dev mode.
            self._mark_cycle_stage("github_context")
            if self._github_legacy_enabled and self.github is not None:
                self._github_counter += 1
                if self._github_counter >= 10:
                    self._github_counter = 0
                    try:
                        self._last_github_block = self.github.get_context_block()
                    except Exception as e:
                        logger.debug("GitHub context failed: %s", e)
```

(e) Gate the injection (~4296-4303): wrap the existing block in the legacy guard and add the honest absence:
```python
        # Add GitHub context — legacy raw injection only in dev legacy mode.
        if self._github_legacy_enabled and self._last_github_block:
            prompt += f"\n{self._last_github_block.text}\n"
            _extend_cycle_candidates(
                "fresh_evidence",
                self._last_github_block.text,
                durable_prefix="cycle_github_context",
                salience=65,
            )
        elif not self._github_legacy_enabled:
            signals_absent.append(
                "GitHub — UNAVAILABLE this cycle (GitHub v1 S2 ingest; legacy reader off)"
            )
```
(Confirm `signals_absent` is in scope at this point in the method; if the signal manifest is built later, append where the calendar absence is appended ~4471 instead, guarded by `not self._github_legacy_enabled`.)

- [ ] **Step 4: Run the legacy-disablement test + a daemon parse check → PASS.**
`.venv/bin/python -B -c "import ast; ast.parse(open('daemon/maez_daemon.py').read()); print('ok')"`

- [ ] **Step 5: Commit** `git commit -am "feat(github-v1): legacy github_skill injection is dev-test-only (replace-not-wrap)"`

---

### Task 3: `github_s2_envelope.py` (mirror `calendar_s2_envelope.py`)

**Files:** Create `core/information_limb/github_s2_envelope.py`; Test `tests/test_github_v1_envelope.py`.

- [ ] **Step 1: Failing test**
```python
# tests/test_github_v1_envelope.py
import unittest
from core.information_limb import github_s2_envelope as env
class EnvelopeTests(unittest.TestCase):
    def test_source_scoped(self):
        self.assertEqual(env.SOURCE_KIND, "github.repo_count")
        self.assertEqual(env.SCHEMA_VERSION, "github.s2.v1")
    def test_required_fields_match_canonical(self):
        # GitHub envelope inherits the SAME canonical S2 field set as Calendar.
        from core.information_limb.calendar_s2_envelope import CANONICAL_S2_REQUIRED_FIELDS as CAL
        self.assertEqual(env.CANONICAL_S2_REQUIRED_FIELDS, CAL)
```
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** — copy `calendar_s2_envelope.py` → `github_s2_envelope.py`. Deltas: `SOURCE_KIND = "github.repo_count"`; `SCHEMA_VERSION = "github.s2.v1"`; keep `CANONICAL_S2_REQUIRED_FIELDS` identical (import or re-declare the same frozenset — the field SET is canonical/inherited); adapt the docstring and any calendar-event-specific field validators to the repo-count shape (the `facts` field holds the single integer + the resolved field name; no event/title/location validators). Keep all envelope-shape guards.
- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Commit.**

---

### Task 4: `github_connector_policy.py` (mirror `calendar_connector_policy.py`)

**Files:** Create `core/information_limb/github_connector_policy.py`; Test `tests/test_github_v1_policy.py`.

- [ ] **Step 1: Failing test**
```python
# tests/test_github_v1_policy.py
import unittest
from core.information_limb import github_connector_policy as pol
class PolicyTests(unittest.TestCase):
    def test_allowed_scope_is_read_user_only(self):
        self.assertEqual(pol.ALLOWED_SCOPE, "read:user")
    def test_broad_scope_rejected(self):
        with self.assertRaises(pol.GithubPolicyError):
            pol.assert_scope_allowed("repo")
    def test_count_only_passes_extra_field_rejected(self):
        # The only admissible datum is the integer count + which field it came from.
        pol.assert_fact_minimized({"repo_count": 7, "count_field": "public_repos"})
        with self.assertRaises(pol.GithubPolicyError):
            pol.assert_fact_minimized({"repo_count": 7, "repo_names": ["x"]})
```
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** — mirror `calendar_connector_policy.py`'s structure (a `GithubPolicyError(ValueError)`, deterministic guards). Deltas: replace Google-scope constants with `ALLOWED_SCOPE = "read:user"` and a `FORBIDDEN_SCOPES` set (`repo`, `read:org`, etc.); `assert_scope_allowed(scope)` raises on anything but `read:user`; `assert_fact_minimized(fact)` raises unless `fact.keys() <= {"repo_count", "count_field"}` and `repo_count` is an int and `count_field in {"public_repos","total"}`; drop the calendar body-adjacent/third-party regex redactors (the fact is one integer — there is no free text to redact; instead enforce "no fields beyond the count"). Owner-only is structural (the v0 limb token is the bonded owner's).
- [ ] **Step 4: Run → PASS.** **Step 5: Commit.**

---

### Task 5: `github_store.py` staging store (mirror `calendar_store.py`)

**Files:** Create `core/information_limb/github_store.py`; Test `tests/test_github_v1_store.py`.

- [ ] **Step 1: Failing test**
```python
# tests/test_github_v1_store.py
import tempfile, unittest
from pathlib import Path
from core.information_limb.github_store import GithubStore, GithubStoreError
class StoreTests(unittest.TestCase):
    def test_minimized_row_roundtrip_content_free(self):
        with tempfile.TemporaryDirectory() as d:
            s = GithubStore(Path(d) / "github_v1.db"); s.initialize()
            rec = s.stage_repo_count(
                ingest_record_id="ir-1", fetch_batch_id="fb-1",
                repo_count=7, count_field="public_repos")
            self.assertEqual(rec["ingest_record_id"], "ir-1")
            # content-free telemetry only; no raw provider response persisted
            health = s.health()
            self.assertIn("staged_records", health)
            self.assertNotIn("7", repr(health))  # the integer is a fact, not telemetry
```
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** — mirror `calendar_store.py`: a small SQLite staging store with schema-version guard + `@contextmanager` connection (use `with closing(...)` per the repo's sqlite hygiene). Table `github_provider_mirror`: columns `ingest_record_id, fetch_batch_id, repo_count, count_field, count_hash, record_state, github_store_schema_version, updated_at`. `stage_repo_count(...)` upserts a minimized row and returns its identifiers. `health()` returns aggregate counts only (content-free). `GithubStoreError` on schema mismatch.
- [ ] **Step 4: Run → PASS.** **Step 5: Commit.**

---

### Task 6: `github_v1.py` connector + health + ingest flow (mirror `calendar_v1.py`)

**Files:** Create `core/information_limb/github_v1.py`; Test `tests/test_github_v1_connector.py`.

- [ ] **Step 1: Failing test** — fetch is MOCKED (no live HTTP):
```python
# tests/test_github_v1_connector.py
import unittest
from unittest import mock
from core.information_limb import github_v1
class ConnectorTests(unittest.TestCase):
    def test_repo_count_staged_from_user_response(self):
        # /user returns public_repos=7; connector extracts ONLY the count.
        user_payload = {"public_repos": 7, "login": "SECRET_LOGIN", "id": 1}
        store = mock.Mock()
        store.stage_repo_count.return_value = {"ingest_record_id": "ir-1", "fetch_batch_id": "fb-1"}
        result = github_v1.ingest_repo_count(
            user_response=user_payload, store=store, fetch_batch_id="fb-1")
        # only the count + field were staged; login never touched
        _, kwargs = store.stage_repo_count.call_args
        self.assertEqual(kwargs["repo_count"], 7)
        self.assertEqual(kwargs["count_field"], "public_repos")
        self.assertNotIn("SECRET_LOGIN", repr(result))
    def test_health_states_content_free(self):
        h = github_v1.build_github_health(mode="disabled")
        self.assertEqual(set(h.keys()) >= {"state"}, True)
        self.assertNotIn("SECRET_LOGIN", repr(h))
```
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** — mirror `calendar_v1.py` (health states `disabled`/`needs_auth`/`available`/`source_unavailable`, content-free). `ingest_repo_count(user_response, store, fetch_batch_id)`: extract `public_repos` (the safe field; use a total field ONLY if a later confirmation step sets `count_field="total"`), build the minimized fact `{"repo_count": N, "count_field": "public_repos"}`, run it through `github_connector_policy.assert_fact_minimized` + `assert_scope_allowed("read:user")`, build the S2 envelope (Task 3), call `store.stage_repo_count(...)`, return the staging identifiers (never the login/id). The actual `GET /user` happens via the v0 `github_limb` session in the daemon-wired path (Task 9); this function takes the already-fetched response so it is hermetically testable.
- [ ] **Step 4: Run → PASS.** **Step 5: Commit.**

---

### Task 7: The one taint-railed body-admission (honest wording + traceability)

**Files:** Modify `core/information_limb/github_v1.py` (add `admit_repo_count_to_body`); Test add to `tests/test_github_v1_connector.py`.

- [ ] **Step 1: Failing test**
```python
    def test_body_admission_honest_wording_taint_and_traceability(self):
        from core.information_limb import github_v1
        mm = mock.Mock(); mm.store.return_value = "mem-1"
        github_v1.admit_repo_count_to_body(
            memory=mm, repo_count=7, count_field="public_repos",
            ingest_record_id="ir-1", fetch_batch_id="fb-1")
        _, kwargs = mm.store.call_args
        # honest wording: public field -> public phrasing, never "owned"/total
        self.assertIn("public repositories", kwargs["content"])
        self.assertNotIn("owned by the owner", kwargs["content"])
        self.assertEqual(kwargs["egress_origin_class"], "owner_account_context")
        # provenance_source maps to OBSERVED (existing enum), raw memory
        self.assertEqual(str(kwargs["provenance_source"]).lower().endswith("tool_observation"), True)
        # traceability: source_ref -> staging ingest_record_id
        self.assertEqual(kwargs["metadata"]["source_ref"], "github.s2:ir-1")
        self.assertEqual(kwargs["metadata"]["fetch_batch_id"], "fb-1")
    def test_total_field_uses_owned_phrasing(self):
        from core.information_limb import github_v1
        mm = mock.Mock(); mm.store.return_value = "mem-2"
        github_v1.admit_repo_count_to_body(
            memory=mm, repo_count=9, count_field="total",
            ingest_record_id="ir-2", fetch_batch_id="fb-2")
        self.assertIn("repositories owned by the owner", mm.store.call_args[1]["content"])
```
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** in `github_v1.py`:
```python
from core.memory_provenance_source import ...  # see note: import ProvenanceSource from memory.memory_manager

def _honest_repo_count_content(repo_count: int, count_field: str) -> str:
    if count_field == "public_repos":
        return f"GitHub reports {repo_count} public repositories on the owner's profile"
    if count_field == "total":
        return f"GitHub reports {repo_count} repositories owned by the owner"
    raise ValueError(f"unknown count_field {count_field!r}")

def admit_repo_count_to_body(*, memory, repo_count, count_field,
                             ingest_record_id, fetch_batch_id):
    """The ONE reviewed body-admission (Inheritance-Ledger override). Writes the
    minimized fact to RAW memory with owner-account taint + traceability."""
    from memory.memory_manager import ProvenanceSource
    content = _honest_repo_count_content(repo_count, count_field)
    return memory.store(
        content=content,
        cycle=0,
        provenance_source=ProvenanceSource.TOOL_OBSERVATION,   # -> OBSERVED
        egress_origin_class="owner_account_context",
        metadata={
            "source_ref": f"github.s2:{ingest_record_id}",
            "fetch_batch_id": fetch_batch_id,
        },
    )
```
> Note: confirm `MemoryManager.store`'s exact signature (it is `store(self, content, cycle, snapshot=None, metadata=None, *, provenance_source=None, trust_tier=None, egress_origin_class=None)` per memory_manager.py:1007). `cycle=0` (or an appropriate sentinel) for a non-cycle ingest; if `store` requires a real cycle, use `store_telegram`-style or the lowest-friction raw write that accepts the keyword set — verify and adjust. Do NOT promote to core. Do NOT set `trust_tier` (let it default from `TOOL_OBSERVATION`).

- [ ] **Step 4: Run → PASS.** **Step 5: Commit** `"feat(github-v1): one taint-railed body-admission, honest wording + traceability"`

---

### Task 8: Hermetic egress canary (real-ingested fact → 403)

**Files:** Test `tests/test_github_v1_egress_canary.py` (mirror `tests/test_owner_account_memory_taint_rail.py::GithubCanaryReachesProxyAndIsRefused`).

- [ ] **Step 1: Failing/witness test** — store the repo-count fact via the REAL body-admission, recall it, route through the REAL assembly into `chat_completions`, assert refusal:
```python
# mirror tests/test_owner_account_memory_taint_rail.py setUp (temp proxy DB,
# _NeverCalledAdapter, importlib.reload(server), ADAPTERS patch).
async def test_repo_count_memory_is_refused_at_proxy(self):
    mm = _real_memory_manager_with_temp_db()           # real MemoryManager, temp dbs
    from core.information_limb import github_v1
    github_v1.admit_repo_count_to_body(
        memory=mm, repo_count=7, count_field="public_repos",
        ingest_record_id="ir-1", fetch_batch_id="fb-1")
    recalled = mm.recall_for_telegram("how many repos")   # or the recall path that returns the row
    owner_memory = mm.format_for_prompt_provenanced(recalled)
    from skills.web_interface import build_claude_router_cloud_payload
    from core.routing import claude_tier
    system_prompt, web_messages = build_claude_router_cloud_payload(
        owner_bridge=True, message="how many repos?",
        history=[{"role": "user", "content": "how many repos?"}],
        owner_memory=owner_memory)
    cloud_messages = [claude_tier.CloudMessage(role=m["role"], content=m["content"]) for m in web_messages]
    captured = {}
    def _cap(*, body_payload, model, caller, timeout_s=None):
        captured["body"] = body_payload
        from core.claude_tier import TierReply; return TierReply("x", model, 1, 1, {})
    with mock.patch("core.routing.claude_tier._post_chat_payload", side_effect=_cap):
        claude_tier.call_messages(system_prompt=system_prompt, messages=cloud_messages,
                                  model="github-v1-canary", caller="github-v1-canary")
    with self.assertRaises(HTTPException) as ctx:
        await self.server.chat_completions(_make_proxy_request(captured["body"]))
    self.assertEqual(ctx.exception.status_code, 403)
    self.assertEqual(self.adapter.prompts, [])
```
> The test must use a REAL `MemoryManager` writing to temp dbs so the fact is genuinely stored→recalled (not hand-built). If recall of a single raw row is awkward, assert the recalled set contains the row and that `format_for_prompt_provenanced` emits an `owner_account_context` span for it. Mutation check: removing `egress_origin_class` from the admission, or flattening the renderer, must make this test FAIL.

- [ ] **Step 2: Run → PASS** (the taint rail already enforces; this proves a *real-ingested* fact rides it).
- [ ] **Step 3: Commit.**

---

### Task 9: Daemon wiring of GitHub v1 (mode → store → fact / signal_absence)

**Files:** Modify `daemon/maez_daemon.py`; Test `tests/test_github_v1_daemon_wiring.py`.

- [ ] **Step 1: Failing test** — in `V1` mode the daemon constructs a `GithubStore` and exposes a content-free github health; in `DISABLED` mode neither legacy nor v1 contributes raw text (signal_absence only). Assert via a constructed daemon-ish harness or source-contract (mirror the calendar store-init block ~2480-2490).
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** — mirror the calendar store-init in `__init__` (~2480): in `V1` mode, `self._github_store = GithubStore(GITHUB_STORE_DB_PATH); self._github_store.initialize()` with the same error-class handling (`github_store_schema_mismatch` / `source_unavailable`). Add `GITHUB_STORE_DB_PATH = os.environ.get("MAEZ_GITHUB_STORE_DB") or (MEMORY_DIR / "github_v1.db")` near the calendar one (~180). Wire the v0 `github_limb` session as the auth source for the one-shot `GET /user` (only when the limb is `available`); the actual fetch + `ingest_repo_count` + `admit_repo_count_to_body` is a bounded operation (one-shot, owner-gated) — keep it OFF the hot cognition path in v1 (a separate explicit trigger / low-frequency, mirroring "polling-only, no proactive"). Health surfaces in `_body_health` like `reddit_limb`/`github_limb`.
- [ ] **Step 4: Run → PASS + daemon parse check.**
- [ ] **Step 5: Commit.**

---

### Task 10: Full-suite regression gate + honest-wording pin

**Files:** none (verification) + confirm the honest-wording test from Task 7 is present.

- [ ] **Step 1:** `.venv/bin/python -B -m unittest discover -s tests 2>&1 | tail -25` — expect no NEW failures vs main (the ambient floor: live-judge, smoke-imports, slice-3.5-envelope, fast-backend; compare against a fresh `main` run if unsure — see `feedback_worktree_floor_confound`).
- [ ] **Step 2:** Confirm acceptance rules 1-9 each map to a passing test (config, legacy-off, policy scope+minimization, staging minimization, body-admission taint+traceability, honest wording matches field, egress 403, signal_absence, trust posture). Fix gaps.
- [ ] **Step 3: Final commit** if Step 2 required changes.

---

## Self-Review

**Spec coverage:** §1 Inheritance Ledger → Tasks 1-6 (mirror) + the override realized in Task 7. §2 fact + honest wording → Tasks 6, 7 (+ pin). §3 components → Tasks 1,3,4,5,6. §4 flow → Tasks 6,7. §5 legacy disablement → Task 2 (RED-first). §6 traceability → Task 7. §7 trust posture → Task 7. §8 hermetic witness → Tasks 5,7,8 + Task 2 (legacy-off). §9 scope → respected (no proxy, no ACCOUNT_DERIVED, one fact). §10 acceptance rules → Task 10 mapping. ✓

**Placeholder scan:** "mirror calendar_X.py with deltas [explicit list]" is a concrete instruction against a real template the reading-list requires the implementer to read — not a placeholder. The two flagged verify-points (the brittle source-contract assertion in Task 2; the exact `store` cycle arg in Task 7) are called out with the robust alternative, not left vague.

**Type consistency:** `GithubMode`/`resolve_github_mode` (T1) used in T2/T9; `ingest_repo_count`/`admit_repo_count_to_body`/`_honest_repo_count_content` (T6/T7) consistent; `stage_repo_count(ingest_record_id, fetch_batch_id, repo_count, count_field)` consistent T5↔T6↔T9; `egress_origin_class="owner_account_context"` + `provenance_source=TOOL_OBSERVATION` + `metadata.source_ref="github.s2:<id>"` consistent T7↔T8.

**Implementer must verify (called out, not assumed):** (a) `MemoryManager.store`'s `cycle`/keyword acceptance for a non-cycle raw write; (b) whether `read:user` exposes a total count (else `public_repos`, honest wording follows); (c) the exact daemon line numbers (they drift — search by symbol: `self.github = GitHubSkill()`, `_last_github_block`, the calendar store-init block); (d) make the Task 2 legacy guard a robust source-contract assertion, not the brittle whitespace match.
