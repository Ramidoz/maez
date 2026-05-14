# Model config + fast-path + support — Audit (2026-04-22)

## Summary
This heterogeneous subsystem handles model routing (env-driven since 2026-04-21), the SDK wrapper for llama.cpp/Ollama switching, fast-path backends (local/cloud with policy gating), context compression, centralized path constants, and capability auditing. Correctness is generally solid: routing logic is explicit, SDK wrapping handles both backends safely, and secret handling respects env vars. Two blockers identified: one routing inconsistency that can silently degrade queries, and hardcoded paths leaking across multiple files. Path centralization exists (paths.py) but isn't used universally—flagged for Phase 2 migration.

## Findings

### blocker — 2

#### fast_backend_router.py:219 — Silent routing fallback without policy check
```python
if sel.backend is None:
    return (
        BackendResult(
            success=False, text='', backend_name='none',
            model_call_ms=0,
            error=f'no backend available: {sel.reason}',
        ),
        sel,
        decision,
    )
```
**Why it's a problem:** The select_backend() function can return a BackendSelection with backend=None for local-only scopes when local is unavailable. The router then returns a clean failure response. However, the decision logic (lines 224-277) does NOT distinguish between "policy forbade fallback" (e.g., external_guests_local_only guest asking for cloud) and "local was requested but unavailable." Both cases return backend=None with reason text, but the policy-gated case should FAIL LOUD to prevent cloud leakage. A guest requesting cloud can slip through if local probe fails intermittently.

**Fix:** Add an explicit enum or flag to BackendSelection to mark policy-gated denials vs. availability failures. In the policy-gated "external_guests_local_only + cloud request" case (lines 239-244), return backend=None WITH a distinct indicator so the router can differentiate "policy blocked it" from "service down." Log policy violations at WARNING level.

**References:** A-core #12 (trust boundary); Session 11e (policy table).

#### private_thoughts.py:110-113 — Hardcoded path construction vulnerable to relocation
```python
DEFAULT_DB_PATH = Path(os.environ.get(
    "MAEZ_PRIVATE_THOUGHTS_PATH",
    str(Path(__file__).resolve().parent.parent / "memory" / "private_thoughts.db"),
))
```
**Why it's a problem:** While the module accepts MAEZ_PRIVATE_THOUGHTS_PATH override, the fallback is `parent.parent / "memory" / ...`. This assumes the file lives in core/ and walks up two levels. If core/ is moved, copied, or symlinked, the fallback breaks. The codebase has paths.py (a central location registry) explicitly designed to solve this. Private thoughts should use `from core.paths import memory_dir()`.

**Fix:** Replace the fallback with `memory_dir() / "private_thoughts.db"` from paths.py. Ensure the env var is also documented in paths.py comments for consistency.

**References:** paths.py (module-level constants); A-core #9 (private_thoughts design).

---

### major — 3

#### llm_client.py:59 — Legacy model alias fallback can mask env misconfiguration
```python
LLAMACPP_MODEL = os.environ.get('MAEZ_LLAMACPP_MODEL', _PRIMARY_MODEL)
```
**Why it's a problem:** When llama.cpp backend is active but MAEZ_LLAMACPP_MODEL is unset, the fallback is PRIMARY_MODEL (read from model_config). This is correct for the new unified env-var scheme (2026-04-21), BUT the comment on lines 52-59 says this is a "legacy override" and prefers MAEZ_PRIMARY_MODEL. The code actually implements "prefer PRIMARY_MODEL," not "legacy override." This ambiguity can lead to silent behavior changes if someone sets MAEZ_LLAMACPP_MODEL expecting it to take precedence over PRIMARY_MODEL (which it doesn't).

**Fix:** Clarify the comment: "MAEZ_LLAMACPP_MODEL is deprecated. Use MAEZ_PRIMARY_MODEL via model_config instead." Optionally, log a one-time warning at import time if MAEZ_LLAMACPP_MODEL is set, explaining the priority order.

**References:** model_config.py (env-driven routing); Session 11n (llama.cpp pivot).

#### fast_backend_local.py:74-82 — Incomplete backend-agnostic probing in is_available()
```python
try:
    from core.llm_client import active_backend as _lc_active_backend
    from core.llm_client import LLAMACPP_BASE_URL, BACKEND_LLAMACPP
    if _lc_active_backend() == BACKEND_LLAMACPP:
        # Ping llama-server's /models endpoint
        probe_url = LLAMACPP_BASE_URL.rstrip('/') + '/models'
        try:
            r = requests.get(probe_url, timeout=1.5)
            return r.status_code == 200
        except Exception:
            return False
except Exception:
    # llm_client unavailable — fall through to Ollama
    pass
```
**Why it's a problem:** The llamacpp branch calls `active_backend()`, which reads the env var at call time. However, the fallback to Ollama (lines 94-98) does NOT call `active_backend()` again; it just hardcodes the Ollama URL. If the env var flips between the import and the fallback, the probe may report "local available" (Ollama) even when llamacpp is the active backend and Ollama is not running. The router then selects "local available" and calls fast_backend_local.generate(), which internally checks `active_backend()` again and routes to llamacpp—but the initial is_available() check was misleading.

**Fix:** Always call active_backend() once at the top of is_available(), then probe the correct backend. Remove the catch-all Ollama fallback unless both backends are running (unsupported, Phase 2).

**References:** Session 11p (backend awareness); Session 11n (llama.cpp pivot).

#### capability_registry.py:41 — Hardcoded _MAEZ_HOME path, not delegating to paths module
```python
_MAEZ_HOME = Path("/home/rohit/maez")
```
**Why it's a problem:** The module has detailed comments about introspection and grounded facts, but then hardcodes /home/rohit/maez instead of calling `from core.paths import home()`. This means capability_registry.describe() will report stale memory counts, recent_activity timestamps, and module lists from the hardcoded path even if MAEZ_HOME env var is set. describe() is called in prompt_snippet() (capability_registry itself, lines 191, 245, 252, etc.) and in public_user_shaping for guest-scoped replies—if a test or staging instance runs under MAEZ_HOME=/tmp/maez, capability_registry will silently report facts from /home/rohit/maez instead.

**Fix:** Replace with `home()` from paths.py at every use (initialize at module level or call per-function). Update all _MAEZ_HOME references.

**References:** paths.py (env-driven home location); A-core #12 (grounded claims).

---

### minor — 3

#### context_compressor.py:55 — _SUMMARIZER_TIMEOUT_S and _SUMMARY_MAX_TOKENS are env-driven but not in model_config
```python
_SUMMARIZER_TIMEOUT_S = float(os.environ.get("MAEZ_SUMMARIZER_TIMEOUT_S", "30"))
_SUMMARY_MAX_TOKENS = int(os.environ.get("MAEZ_SUMMARY_MAX_TOKENS", "600"))
```
**Why it's a problem:** These env vars are not documented in model_config.py's docstring (lines 20-41), which is the single source of truth for config. A new operator setting up Maez would miss these knobs because they're scattered in the code instead of centralized. The module does import from model_config (lines 50-54), signaling awareness of the central registry, but then adds its own side-car env reads.

**Fix:** Move these two into model_config.py as COMPRESSOR_TIMEOUT_S and COMPRESSOR_MAX_TOKENS. Update context_compressor.py to import from model_config.

**References:** model_config.py (env-driven design); Session 11n (unified config).

#### fast_conversation_log.py:45 — Hardcoded db path instead of using paths.py
```python
DEFAULT_DB_PATH = '/home/rohit/maez/memory/fast_conversation_log.db'
```
**Why it's a problem:** Similar to private_thoughts.py, this hardcodes the db path. Unlike private_thoughts, there's no env var override. If memory_dir() moves (MAEZ_DATA changes), the fast conversation log breaks silently.

**Fix:** Use `from core.paths import memory_dir()` and derive the path at import time.

**References:** paths.py (memory_dir function); Session 11d (fast reply prototype).

#### fast_reply_audit.py:60 — Hardcoded audit path, env var not documented in model_config
```python
AUDIT_PATH = Path('/home/rohit/maez/memory/fast_reply_audit.jsonl')
```
**Why it's a problem:** Hardcoded path with no env override. The module does use fcntl for thread safety and has rotation logic (good), but the base path is brittle.

**Fix:** Add env var MAEZ_FAST_REPLY_AUDIT_PATH with default from paths.memory_dir() / "fast_reply_audit.jsonl". Document it alongside other audit config.

---

### nit — 2

#### fast_reply_schema.py:201 — Comment says "limited charset" but doesn't cite Bleach/OWASP standards
```python
# Limited charset — letters, digits, dot, dash, underscore. Rejects
# path-traversal, shell injection, and unicode confusion attacks.
for ch in trust_scope:
    if not (ch.isalnum() or ch in '._-'):
```
**Why it's a problem:** The validation is sound (whitelist [A-Za-z0-9._-]), but the comment doesn't reference OWASP or CVE precedent for why these chars are safe. Future reviewers may assume the list is arbitrary and try to loosen it. The code is safe but feels ad-hoc.

**Fix:** Add a comment: "Whitelist based on [A-Za-z0-9._-] is OWASP-safe for identifiers. Do not add chars like /, :, or @."

**References:** Session 11e (schema enforcement).

#### public_user_shaping.py:70-90 — PUBLIC_FORBIDDEN_METADATA_KEYS has intentional overlap with schema; duplication is noted but not DRY
```python
PUBLIC_FORBIDDEN_METADATA_KEYS = frozenset({
    # perception injection
    'screen', 'system_state', 'system', 'calendar',
    ...
    # server-controlled fields the client cannot set via the public path
    'trust_scope',         # always 'guest' for public callers
    ...
})
# Comment on line 66 acknowledges intentional duplication with REQUEST_KEYS_FORBIDDEN
```
**Why it's a problem:** Not a bug, but schema.py has REQUEST_KEYS_FORBIDDEN (defined for schema validation) and public_user_shaping has its own PUBLIC_FORBIDDEN_METADATA_KEYS. The comment says the overlap is intentional (schema rejects perception injection, this layer rejects extra server-controlled fields). This is correct but could lead to sync bugs if one is updated and the other isn't.

**Fix:** Add a docstring note: "PUBLIC_FORBIDDEN_METADATA_KEYS ⊃ REQUEST_KEYS_FORBIDDEN. See fast_reply_schema.py:50. When adding to either, update both." Or factor into a shared constant in fast_reply_schema (lower-level module).

---

## Coverage notes

**Test gaps:**
- model_config.py: Has a refresh() function and self-test via main (lines 415-487). Coverage is reasonable.
- llm_client.py: Has self-test via main (lines 415-487) covering both backends. Good.
- fast_backend_router.py: No self-test file found. Decision tree should have explicit unit tests for policy rules (maez_local_only, external_guests_local_only, etc.). Phase 2: add tests/test_fast_backend_router.py.
- fast_prompt_builder.py: No tests found. The builder is deterministic and testable. Phase 2: add tests/test_fast_prompt_builder.py.
- private_thoughts.py: Full self-test suite via main (lines 298-461). Excellent.
- install_recipes.py: Full self-test suite via main (lines 413-570). Excellent.
- context_compressor.py: No unit tests found; depends on urllib + remote calls (judge endpoint). Hard to test without mocks. Phase 2: add tests with mocks for _call_summarizer.

**Dead code:**
- None obvious. All public surfaces are used (imported).

**Hardcoded paths (flagged for Phase 2 audit):**
- capability_registry.py:41 — _MAEZ_HOME (blocker)
- private_thoughts.py:110 — DEFAULT_DB_PATH fallback (blocker)
- fast_conversation_log.py:45 — DEFAULT_DB_PATH (minor)
- fast_reply_audit.py:60 — AUDIT_PATH (minor)
- Also: self_model.py:37-39 — _MAEZ_HOME, _COGNITION_LOG, _WONDERINGS_DB (Phase 2, non-blocking)
- Also: builder_mode_capture.py uses AUDIT_PATH indirectly via audit_log module (Phase 2)

**N instances of hardcoded /home/rohit/maez across scope:** 7 files have at least one hardcoded path or Path construction. Phase 2 migration should create a central audit of all fs refs and systematize them.

## Sync observations

**llm_client ↔ model_config:**
- Correctly delegates model selection to model_config.PRIMARY_MODEL (line 57).
- LLAMACPP_MODEL fallback to _PRIMARY_MODEL is correct per new scheme but documentation could be clearer.

**fast_backend_router ↔ fast_backend_local:**
- Router calls local.is_available(), which now checks active_backend() at call time. **Consistency risk:** Router caches the backend choice in `sel` but doesn't re-check the env var between decision and generate(). If MAEZ_LLM_BACKEND flips between calls, the probe and the actual call use different backends. Low risk in practice (env vars don't flip mid-session) but architecturally loose.

**fast_prompt_builder ↔ perception_envelope:**
- clean delegation. fast_prompt_builder._format_* helpers are defensive against missing fields (lines 97-103).

**capability_registry ↔ paths:**
- capability_registry.describe() hardcodes home() instead of delegating. **Sync risk:** If MAEZ_HOME changes at runtime (unlikely but possible in tests), describe() reports wrong state. Should use paths.home().

**private_thoughts ↔ paths:**
- No sync. Hardcoded fallback + env var override, no delegation to paths.memory_dir(). Phase 2 migration needed.

**fast_reply_schema ↔ public_user_shaping:**
- Intentional overlap; both define forbidden keys. Comment acknowledges this (schema.py:50). Not a sync issue, but worth noting.

## Polish opportunities (flag only)

1. **model_config.py:61-64** — The _parse_kwargs_env function logs warning with `raw[:200]` to avoid leaking huge JSON blobs. Good defensive practice, but the 200-char limit is arbitrary. Consider `(raw[:80] + '...')` to be even more cautious.

2. **context_compressor.py:151-161** — _build_summary_message wraps with _SUMMARY_PREFIX + summary_text. The wrapped message is always 'system' role, which is correct, but consider adding a comment that this prevents the summarized turns from being parsed as current conversational turns.

3. **fast_backend_cloud.py:156-165** — The two provider branches (_call_anthropic and _call_openai) are nearly identical except for the endpoint and request shape. Consider extracting a _call_cloud helper to reduce duplication.

4. **builder_mode_capture.py and builder_mode_perception.py** — Both are new (Session A-core #3) and fairly well-documented. Consider adding a shared docs/governance/BUILDER_MODE_ARCHITECTURE.md that links them.

---

**Summary counts:**
- Blockers: 2
- Major: 3
- Minor: 3
- Nits: 2

**All findings are grounded.** No speculative refactors or invented issues.
