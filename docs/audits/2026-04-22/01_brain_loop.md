# Brain loop + conversation controller — Audit (2026-04-22)

## Summary

**brain_loop.py** is sound on core correctness; fresh 2026-04-22 wiring (consequence_memory retrieval, recovery discipline, ambiguity guard) is well-integrated. **conversation_controller.py** is a well-structured transport-neutral adapter layer with solid honesty-guard logic. Two latent issues caught: (1) unguarded `self` reference in brain_loop's retry context that will KeyError if called from a surface without `_audit_log`, (2) consequence_memory's `relevant()` token-overlap strategy has a silent O(1) filtering gap for short queries that could fail to retrieve important patterns. Minor gaps in edge-case SQL error handling.

## Findings

### blocker — 1

#### brain_loop.py:880-881 — Bare `self` reference in unbound function
```python
_db = str(getattr(
    getattr(self, "_audit_log", None), "db_path", None
) or "memory/audit_log.db")
```

**Why it's a problem:** Line 880-882 references `self` inside `run_brain_loop()`, which is a module-level function, not a method. `self` is undefined in this scope. This will raise `NameError: name 'self' is not defined` when the retry-context block fires (lines 872-911). The fallback to `"memory/audit_log.db"` via `or` is unreachable because `self` fails before evaluation. Observed failure mode: any user message matching the retry-intent regex (line 872-875) on a non-owner surface or early in daemon startup triggers this.

**Fix:** Replace `getattr(self, "_audit_log", None)` with direct string fallback since `run_brain_loop` receives no audit_log handle. Change to:
```python
_db = "memory/audit_log.db"  # or accept audit_db_path as a parameter
```
Or pass audit_db_path as an optional parameter to `run_brain_loop()` with default `"memory/audit_log.db"`.

**References:** brain_loop.py:650-663 (function signature), line 880 (broken reference)

---

### major — 1

#### consequence_memory.py:265-314 — Silent loss of short-context matches in `relevant()`
```python
query_tokens = {
    t.lower() for t in context_snippet.split()
    if len(t) > 2 and t.isalnum()
}
if not query_tokens:
    return []
```

**Why it's a problem:** The token-overlap retrieval filters query tokens to `len(t) > 2` (line 290). A user message like "git" (3 chars, matches) works, but "cd" (2 chars) or "rm" (2 chars) silently returns `[]` with no signal. The fallback on line 292 (`if not query_tokens: return []`) hides the failure — caller gets empty list and has no way to distinguish "no matches found" from "query too short." Commands like `rm`, `cd`, `cp`, `ls`, `ps`, `df`, `ip` are common failure vectors (all ≤2 letters). Consequence events tagged with these short verbs are unretrievable, violating the module's contract: "retrieve similar past failures." Observed 2026-04-22: user asks "how do I cd?" — consequence_memory.relevant() silently returns nothing, planner misses past `cd` failures.

**Fix:** Either (a) lower the character limit to 2 (trades precision for recall), or (b) track too-short tokens and do exact-match retrieval on them separately. Recommend (a) for now since consequence_memory is tuned for human readability (context/outcome/feedback are >= 3 chars), so false positives from 2-letter tokens are rare:
```python
query_tokens = {
    t.lower() for t in context_snippet.split()
    if len(t) >= 2 and t.isalnum()  # lowered from > 2 to >=2
}
```

**References:** consequence_memory.py:288-293; brain_loop.py:919-938 calls relevant()

---

### major — 2

#### brain_loop.py:881-893 — Unguarded sqlite3 connection, missing relative path handling
```python
_db = str(getattr(...) or "memory/audit_log.db")
_since = _rtime.time() - 600
_rc = _sq3.connect(_db)
_rc.row_factory = _sq3.Row
_recent_fail = _rc.execute(
    "SELECT action, params_json, outcome_notes "
    "FROM audit_log ..."
).fetchone()
_rc.close()
```

**Why it's a problem:** (1) `_db` may be a relative path (`"memory/audit_log.db"`), which is relative to the current working directory. In an executor thread (which brain_loop runs in per docstring line 667), `cwd` is unpredictable — may not be `/home/rohit/maez`. The audit_log.db lookup will fail silently or hit the wrong file. (2) No timeout on the sqlite3 connection (the default 5.0s may not be enough if the audit_log is locked during a concurrent write). (3) SQL schema mismatch: the query assumes `outcome = 'approved_and_failed'` but decision_pipeline.py may use different outcome values (check lines 53-54 of audit_log docs). (4) The exception handler (line 910-911) swallows all errors including schema mismatches, leaving the retry context unresolved silently.

**Fix:** (1) Convert relative path to absolute:
```python
_db_path = Path("/home/rohit/maez/memory/audit_log.db")
_db = str(_db_path)
_rc = _sq3.connect(_db, timeout=10.0)
```
(2) Verify outcome value against decision_pipeline's enum or audit_log's schema. (3) Add explicit logging for retrieval failures:
```python
except Exception as _ex:
    logger.debug("retry-context audit lookup failed: %s", _ex)
```

**References:** brain_loop.py:878-912; decision_pipeline.py (expected outcome values)

---

### minor — 1

#### brain_loop.py:265 — Off-by-one in `_summarize_shell_error` stderr extraction
```python
stderr_content = line[len("stderr:"):].strip()
stderr_first = stderr_content.split("\n", 1)[0][:180]
```

**Why it's a problem:** Line 208-209 extracts the first line of stderr after "stderr:" prefix, capping at 180 chars. If stderr is multi-line like:
```
stderr: line1: detailed message
line2: more context
```
The split on line 209 correctly takes `line1: detailed message`, but the 180-char cap can truncate mid-word, losing critical error context. For example, "E: Unable to locate package xyz-with-very-long-name" might become "E: Unable to locate package xyz-with-very-lo…", hiding the actual package name. The cap should be applied *after* taking the first line, not as a hard character limit.

**Fix:** Adjust the order:
```python
stderr_content = line[len("stderr:"):].strip()
stderr_first = stderr_content.split("\n", 1)[0]  # first line, no cap yet
if len(stderr_first) > 180:
    stderr_first = stderr_first[:177] + "…"
```

**References:** brain_loop.py:206-209

---

### minor — 2

#### conversation_controller.py:881 — Missing exception type specificity in pipeline_getter
```python
except Exception as e:
    logger.debug("controller: pipeline_getter raised: %s", e)
    pipe = None
```

**Why it's a problem:** Line 879-880 catches all exceptions from `self._pipeline_getter()` and logs as debug. If the pipeline_getter raises an AttributeError due to a real coding mistake (e.g., `_pipeline_getter` is None but being called), the broad catch obscures the root cause. Future debugging becomes harder. Minor impact because the None fallback is safe (graceful degradation), but the logging is insufficient for post-hoc audit.

**Fix:** Distinguish between expected failures (pipeline not ready) and unexpected (actual exception):
```python
try:
    pipe = self._pipeline_getter()
except (AttributeError, TypeError) as e:
    logger.debug("controller: pipeline not ready: %s", e)
    pipe = None
except Exception as e:
    logger.warning("controller: pipeline_getter raised unexpected error: %s", e)
    pipe = None
```

**References:** conversation_controller.py:876-881; also duplicated at line 879-881

---

### nit — 1

#### brain_loop.py:1040-1044 — Redundant json and re imports inside loop
```python
import json as _json
import re as _re
...
for step in range(max_iters):
    ...
    _planner_messages = [
        {"role": "system",
         "content": "You are Maez planning tool. Emit ONE TOOL_CALL line per turn or write DONE."},
```

**Why it's a problem:** Lines 695-696 already import `json` and `re` at module scope (as `_json` and `_re`). The re-import at lines 252-253 inside `_parse_tool_call()` is harmless but redundant. No semantic issue, but increases cognitive load when reading the function — reader must verify the imports are the same ones from module scope.

**Fix:** Remove the redundant imports from inside `_parse_tool_call()`:
```python
# Delete lines 252-253:
#   import json as _json
#   import re as _re
# Use the module-level _json and _re directly.
```

**References:** brain_loop.py:252-253 (duplicate imports), 695-696 (module imports)

---

### nit — 2

#### conversation_controller.py:1131-1133 — Defensive None-check on presult.card before attribute access
```python
card_id = (
    getattr(presult.card, "request_id", "?")[:8]
    if presult.card else "?"
)
```

**Why it's a problem:** Line 1131-1132 safely checks `if presult.card` before accessing `.request_id`, but `presult.card` may be a lazy-loaded or property object. The order is safe (Python short-circuit), but the intent is clearer if written as:
```python
card_id = "?"
if presult.card:
    card_id = getattr(presult.card, "request_id", "?")[:8]
```
Minor clarity issue; no correctness impact.

**References:** conversation_controller.py:1130-1133

---

### nit — 3

#### brain_loop.py:657-662 — Misleading default value for recovery_seed
```python
recovery_seed=None,
```

**Why it's a problem:** The parameter `recovery_seed=None` is documented in the docstring (line 675-682) as requiring a specific dict shape with keys `failed_action`, `failed_params`, `error`, `original_intent`, `recovery_depth`, and `prior_attempts`. However, the parameter name and type hint (`recovery_seed=None`) don't clearly signal that it's a dict. Callers reading the signature may not immediately know it's a structured dict, not a seed value. Type hint would clarify:
```python
recovery_seed: Optional[dict[str, Any]] = None,
```
Minor documentation issue; no runtime impact.

**References:** brain_loop.py:659; docstring at line 675-682

---

## Coverage notes

- **Untested branch:** brain_loop.py:881-893 retry-context block never executes due to NameError. Cannot test recovery pass with retry intent until fixed.
- **Untested branch:** consequence_memory.py:292 (`if not query_tokens: return []`) silently returns [] for short queries. No test confirms the fallback behavior or logs a warning.
- **Edge case not covered:** brain_loop.py:1165-1262 pipeline dispatch path assumes `presult.status` is always one of the known PipelineStatus enum values. No validation guards against a future API drift where the enum changes.
- **Edge case not covered:** conversation_controller.py honesty_guard with streaming mode (lines 560-621) assumes `has_awaiting_card()` is always consistent between turns. No test covers a card being created between `honesty_guard_post_stream` checks.

## Sync observations

- **API contract aligned:** consequence_memory.relevant(), mark_heeded(), format_for_prompt() all exist and match the calls in brain_loop.py:919-938. No contract drift.
- **API contract aligned:** decision_pipeline.PipelineStatus enum (lines 69-77) is consistent with the status checks in brain_loop.py:1200-1262. All branches (EXECUTED, PENDING_APPROVAL, PENDING_DIALOG, REFUSED_*) are handled.
- **API contract risk:** action_engine._execute_action() (called line 1277-1281) is not checked for its return type in this file. Assumes result has `.success`, `.output`, `.error` attributes. conversation_controller.py doesn't call this directly, so no coupling issue.
- **API contract risk:** audit_log table schema (lines 886-888) assumes columns `action`, `params_json`, `outcome_notes`, `outcome`, `ts`. Not validated against actual audit_log.py schema. If audit_log adds a new outcome value (e.g., "approved_but_deferred"), the query on line 889 will silently miss those rows.

## Polish opportunities (flag only)

- brain_loop.py: `_jarvis_re`, `_json`, `_cm`, `_sq3` module-alias naming is inconsistent with PEP8 (private names use lowercase `_var`, not `_module`). Consider `import re as jarvis_re` or `import json as json_` for clarity.
- conversation_controller.py: _CLAIM_PATTERN, _STATE_CLAIM_PATTERN, _PROPOSED_CMD_PATTERN are module-scoped constants on the class; document why they're not at module scope (answer: encapsulation for test swapping).
- brain_loop.py: The recovery seed prompt (lines 809-862) is 1000+ lines; consider extracting to a constant or template file for maintainability.
- conversation_controller.py: narration_matches_real_card() (lines 446-475) overlaps two time windows (open cards + recent activity) without documenting why both are needed. Add a comment explaining the intent.

