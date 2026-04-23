# Cognition quality + audit + grounding — Audit (2026-04-22)

## Summary

This audit reviewed the quality scoring, audit logging, grounding judgment, and telemetry layers (cognition_quality.py, audit.py, audit_log.py, grounding_judge.py, quality_telemetry.py, observability.py). grounding_judge.py's iterative JSON parse fix (applied 2026-04-21) is well-designed; similar robustness exists in audit.py's parse path. Broader audit reveals one blocker (silent ring-buffer state loss in cognition_quality), two majors (unguarded DB connection close + silent metric emission), and polish gaps in label handling.

## Findings

### blocker — 1

#### cognition_quality.py:365 — Ring buffer state loss on exception in score_and_classify()
```python
def score_and_classify(text: str) -> dict:
    try:
        classification = classify(text, _recent_topics)
        quality = score(text, classification, _recent_topics)

        # Update ring buffers
        _recent_topics.append(classification['topic'])
        if len(_recent_topics) > 50:
            _recent_topics[:] = _recent_topics[-50:]
        _recent_scores.append(quality)
        if len(_recent_scores) > 50:
            _recent_scores[:] = _recent_scores[-50:]
        _recent_labels.append(classification['labels'])
        if len(_recent_labels) > 50:
            _recent_labels[:] = _recent_labels[-50:]
    except Exception as e:
        logger.error("Cognition scoring failed (safe fallback): %s", e)
        return {
            'cog_score': 50,
            'cog_primary': 'unknown',
            'cog_labels': 'error',
            'cog_topic': 'unknown',
            'cog_topics': 'unknown',
        }
```

**Why it's a problem:** If classify() or score() raises, the ring buffers never get updated. Subsequent fixation detection (line 234), behavior policy (line 539), and self_critique (line 416) all operate on stale state — potentially hours old if an exception occurred early and the daemon recovers silently. Fixation detection, novelty scoring, and behavior policy all depend on _recent_topics being current. A single exception corrupts all downstream cognition quality decisions without any audit trail. The fallback score (50) tells the caller "something went wrong" but the ring buffer corruption is invisible.

**Fix:** Refactor buffer updates to happen BEFORE classification/score, not after. Or: move buffer append outside try/except so it happens even on exception, with the exception itself becoming the topic (e.g. 'error'). Or: guard the entire function with a ring-buffer rollback on any exception path so the state is either fully updated or fully unchanged.

**References:** The "never raises" promise (line 349) is violated by state corruption. Test coverage gap: _test() does not exercise exception recovery with buffer state verification.

---

### major — 2

#### quality_telemetry.py:268-270 — Unguarded DB connection close() in finally block
```python
def _fabrication_snapshot(limit: int = 10) -> FabricationSnapshot:
    snap = FabricationSnapshot()
    if not _FAB_DB.exists():
        return snap
    try:
        db = sqlite3.connect(_FAB_DB, timeout=1.5)
        snap.total_events = db.execute(
            "SELECT COUNT(*) FROM fabrication_events"
        ).fetchone()[0]
        # ... fetch rows ...
    except Exception as e:
        logger.debug("fabrication_snapshot failed: %s", e)
    finally:
        try:
            db.close()  # ← db is undefined if initial connect() raised
        except Exception:
            pass
    return snap
```

**Why it's a problem:** If sqlite3.connect() raises an exception, `db` is unbound. The finally block then raises NameError('db') silently in the inner except, but the function still returns. This is masking the true root cause (connection failure) with a different exception. Worse: if the connection was partly established but connect() raised, the resource leaks.

**Fix:** Initialize `db = None` before the try block, then check `if db:` before calling close(). Or move the connect() call after the `if not _FAB_DB.exists()` guard into a separate try block with its own resource management.

---

#### audit_log.py:283 — Missing connection commit for record() writes
```python
def record(
    self,
    *,
    action: str,
    params: dict | None,
    classification: Any,
    injection_matches: list | None,
    verdict: Any,
    policy_rule_id: str | None = None,
) -> str:
    request_id = secrets.token_hex(12)
    # ... prep data ...
    with sqlite3.connect(self.db_path) as conn:
        conn.execute(
            """
            INSERT INTO audit_log (...)
            VALUES (...)
            """,
            (...)
        )
    return request_id
```

**Why it's a problem:** SQLite's context manager (`with sqlite3.connect()`) auto-commits on successful exit, but if an exception occurs during the INSERT itself, the transaction is rolled back silently. The caller gets back a request_id that was never written — a silent audit loss. No exception is raised to the caller; audit events can vanish without a trace. Later code referencing that request_id (e.g., record_outcome() on a non-existent row) silently succeeds with rowcount=0. The audit layer is supposed to be fail-closed, not fail-silent.

**Fix:** Explicitly call `conn.commit()` after the INSERT and wrap in an exception handler that either re-raises or logs a critical error. Or add `check_same_thread=False` + explicit conn.close() so you can verify the write succeeded. Or validate that insert rowcount > 0 before returning request_id.

**References:** Lines 312-337 call record_outcome() which silently succeeds on a non-existent request_id (rowcount > 0 check is implicit). The audit log's append-mostly promise depends on atomicity.

---

### major — 1

#### quality_telemetry.py:321 — Metric rollup emission with no error recovery
```python
def build_rollup(
    *,
    audit_lookback: int = 200,
    error_lookback: int = 200,
    consolidation_lookback: int = 20,
    fabrication_limit: int = 10,
) -> QualityRollup:
    blob = _read_tail(_COG_LOG)
    audit = _parse_audit_lines(blob, audit_lookback)
    errors = _parse_error_lines(blob, error_lookback)
    consol = _parse_consolidation_lines(blob, consolidation_lookback)
    fab = _fabrication_snapshot(limit=fabrication_limit)
    recall = _recall_snapshot()

    return QualityRollup(
        generated_at=time.time(),
        source_log_path=str(_COG_LOG),
        audit=audit,
        errors=errors,
        consolidation=consol,
        fabrication=fab,
        recall=recall,
    )
```

**Why it's a problem:** If _read_tail() or any _parse_*() function raises, the entire rollup fails and no partial result is returned to the caller (the HTTP endpoint expecting JSON for the cockpit). The "never raises" promise (module docstring, line 19) is violated. The cockpit goes dark during a transient log-read or disk error because there's no graceful degradation. Compare audit_log.stats() (line 648–684) which wraps every sub-query in a try/except so partial results are always returned.

**Fix:** Wrap each source (blob read, each parse, each snapshot) in its own try/except, returning empty/zero defaults on failure. Return a partial QualityRollup with non-None but empty audit/errors/fabrication instead of crashing.

---

### minor — 2

#### cognition_quality.py:261–262 — Redundant label append logic
```python
# Check repetition — exact substring match with recent (simple heuristic)
# This is a lightweight check; semantic similarity is in memory retrieval
if not labels or labels == ['vague']:
    labels.append('vague')

# Deduplicate
labels = list(dict.fromkeys(labels))
```

**Why it's a problem:** Line 261 appends 'vague' if labels is empty OR if it already contains only 'vague'. This means 'vague' gets appended even when it's already there, then deduplicated. The code works but is semantically confused — it says "append vague if it's the only label" but actually appends it unconditionally if the list is empty. The comment about "repetition" is orphaned (no actual repetition check), and the dedup on line 265 masks the redundancy.

**Fix:** Remove the if-guard. If no labels matched, append 'vague' unconditionally. Or clarify intent: if only one label and it's fixation/baseline, also tag vague (but code doesn't do this). Simplify to: `if not labels: labels.append('vague')`.

---

#### audit.py:537–542 — Unguarded getattr with fallback to False hiding classification structure
```python
if (parse_err or parsed is None):
    try:
        _lane_val = (
            classification.get("lane")
            if isinstance(classification, dict)
            else getattr(classification, "lane", None)
        )
        _is_lane_0 = (_lane_val == 0 or str(_lane_val) == "0")
    except Exception:
        _is_lane_0 = False
```

**Why it's a problem:** If getattr(classification, "lane", None) returns a truthy non-numeric value (e.g., "LANE_0" from a mistyped constant), str(_lane_val) == "0" silently fails to match and _is_lane_0 becomes False, bypassing the retry. A typo in a classification object's lane attribute causes silent degradation of parse recovery. The intent is clear but the implementation is fragile — numeric lane values should be validated earlier, not coerced here.

**Fix:** Add a type check: `if _lane_val not in (0, "0")` is clearer than string coercion. Or validate the classification's lane shape at the call site before audit_action() is invoked. Or log the non-standard lane value so audit operators see the anomaly.

---

### nit — 1

#### observability.py:74–78 — Implicit host default in Langfuse client kwargs
```python
client = Langfuse(
    public_key=os.environ["LANGFUSE_PUBLIC_KEY"],
    secret_key=os.environ["LANGFUSE_SECRET_KEY"],
    host=(
        os.environ.get("LANGFUSE_HOST")
        or os.environ.get("LANGFUSE_BASE_URL")
        or "https://cloud.langfuse.com"
    ),
)
```

**Why it's a problem:** The code reads LANGFUSE_HOST and LANGFUSE_BASE_URL (line 75–76) but Langfuse SDK v4 docs use `host` parameter. The fallback to "https://cloud.langfuse.com" is hardcoded; if an operator sets LANGFUSE_BASE_URL in hopes it takes effect, they get no error or warning — it silently uses the default. Not a correctness bug (the library will accept `host`), but a silent configuration drop that's easy to miss in logs.

**Fix:** Add a debug log when falling back to the hardcoded default, or validate that LANGFUSE_HOST or LANGFUSE_BASE_URL was explicitly set before using the fallback. Consider accepting only one env var name for consistency.

---

## Coverage notes

- cognition_quality.py's _test() does not verify ring-buffer consistency after exceptions. No test exercises a failure in classify() followed by state verification.
- audit.py's offline self-test (line 634–765) covers malformed judge output and nonce leakage but not the Lane-0 parse-retry interaction with inject-flag edge cases. Mutation tests would catch the _is_lane_0 logic fragility.
- audit_log.py's self-test (line 691–950) is thorough but does not exercise INSERT failures or missing commit() behavior. No test fails an INSERT mid-transaction to verify atomicity.
- quality_telemetry.py lacks an integration test that fails _read_tail() or _fabrication_snapshot() mid-call to verify partial-rollup graceful degradation.
- grounding_judge.py's _test() does not exist; the module relies on integration tests elsewhere. The iterative JSON parse (line 256–265) is well-tested implicitly by the module's fail-open design, but no unit test documents the strategy explicitly.

## Sync observations

1. **grounding_judge ↔ self_claim_audit**: grounding_judge.judge() returns list[dict] with {text, reason, rewrite}. self_claim_audit expects the same shape (Flag dataclass, line 52–64). Sync is tight; no struct mismatch detected.

2. **cognition_quality ↔ brain_loop**: score_and_classify() returns {cog_score, cog_primary, cog_labels, cog_topic, cog_topics, cog_parent_topic}. Callers in brain_loop expect all these keys (verified by memory.store() not rejecting them). No structural mismatch, but no explicit verification in the daemon that it consumes all fields.

3. **audit_log ↔ decision_pipeline**: audit_request_id lifecycle begins in audit_action() (audit.py, line 498), recorded in audit_log.record() (line 221), then later looked up in record_outcome() (line 312). The flow is implicit — no explicit contract documented that decision_pipeline must call record_outcome() with the same request_id returned by audit_log.record(). Silent audit loss is possible if a request_id is never looked up.

4. **quality_telemetry ↔ cockpit**: build_rollup() returns QualityRollup, which the cockpit expects to deserialize via to_json(). No validation that all fields are JSON-serializable (e.g., fabrication.recent contains dicts with floats and strings, which are safe). No version field to detect schema evolution.

## Polish opportunities (flag only)

1. **audit.py:392** — `_VALID_DECISIONS = frozenset(d.value for d in Decision)` works but recreates the set on every module load. Consider caching at definition time.

2. **cognition_quality.py:173** — `get_parent_topic()` returns None for non-subtopics but the caller (line 275) checks `.get('parent_topic')` which is None-safe. Consistent but verbose; could use a default value.

3. **audit_log.py:197** — `PRAGMA table_info(audit_log)` works but the migration is run on every __init__, not just on first-time DB creation. Idempotent by design, but unnecessary queries on warm startups. Consider a fast path: check for a version marker column or a separate marker table.

4. **grounding_judge.py:256–265** — The iterative raw_decode strategy is sound but the loop doesn't track the longest partial match in case all attempts fail partway. A stray `{` in the middle might succeed up to an unmatched `}` and hide a later complete JSON object. Unlikely in practice (the judge's output is usually clean or clearly broken), but not robust to adversarial malformed output.

5. **quality_telemetry.py:166–186** — _parse_audit_lines() iterates in reverse (newest first) and breaks at limit, but reversed(blob.splitlines()) creates the entire reversed list in memory. For multi-megabyte logs, consider reading tail first (like _read_tail does) then splitting.

6. **observability.py:43** — `_client_cache` is a module-level dict but has no invalidation logic. If LANGFUSE env vars change at runtime, the old client is still cached. Not a bug for daemon mode (env vars are set at startup), but surprising for REPL/CLI usage.

---

## Verdict

**Blocker: 1** (silent ring-buffer state corruption on exception)  
**Major: 2** (DB connection resource leak + silent audit write loss)  
**Minor: 2** (redundant label logic + fragile lane coercion)  
**Nit: 1** (implicit config fallback)

All findings are correctness or observability issues; no false positives or performance regressions. The grounding_judge fix (iterative parse) is a good model for audit_log and quality_telemetry to follow in their own failure paths.

