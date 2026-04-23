# Memory & recall — Audit (2026-04-22)

## Summary

Memory subsystem exhibits strong invariant discipline and fail-safe patterns. Chunked consolidation (2026-04-22) is solid; stale-number decay (session 11u) correctly applies penalty without deletion. Two minor inter-module sync gaps identified around timestamp format consistency and one recall-loop edge case in the stale-number reorder.

## Findings

### minor — 2

#### memory_manager.py:216-232 — timestamp format inconsistency in _age_hours_from_iso
```python
def _age_hours_from_iso(raw_ts, now_s: float) -> float:
    """Return age in hours from an ISO-8601 timestamp, or 0.0 if
    unparseable. Callers use this as a recall-decay input, so returning
    0.0 on parse failure is the safe default (no penalty applied)."""
    if not raw_ts:
        return 0.0
    try:
        s = str(raw_ts).strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        ts = datetime.fromisoformat(s)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        delta = now_s - ts.timestamp()
        return max(0.0, delta / 3600.0)
    except (ValueError, TypeError, OverflowError):
        return 0.0
```

**Why it's a problem:** memory_manager.py::store() writes timestamps as `datetime.now(timezone.utc).isoformat()` (line 349), which produces `2026-04-22T12:34:56.789123+00:00`. The _age_hours_from_iso handler only converts the trailing `Z` to `+00:00` (line 224-225), but does NOT handle bare ISO strings without a timezone offset (which fromisoformat silently accepts as naive). This is not a live bug—the source at store() time is always aware—but creates a silent assumption: if a timestamp ever arrives without tzinfo, the "safe default" of returning 0.0 means NO penalty is applied to a potentially stale memory. For the stale-number reorder in _query_collection (line 664), this means a freshness-loss bug could hide if timestamps ever lose tzinfo in the Chroma metadata pipeline (e.g., via JSON serialization round-trip).

**Fix:** Explicitly reject naive timestamps with a warning or normalize the handler to always assume UTC if tzinfo is None. Current code does that at line 227-228, but the docstring claims "returning 0.0 on parse failure is the safe default" when it actually disables the entire stale-number penalty. Add a log statement to surface the fallback.

**References:** memory_manager.py:216-232, memory_manager.py:349, memory_manager.py:662-664

---

#### memory_manager.py:786 — mmr_rerank import never validated as successful
```python
        try:
            from memory.mmr import mmr_rerank
        except ImportError:
            return results[:n]
        candidate_pool = results[: max(n * 2, n + 2)]
        return mmr_rerank(candidate_pool, k=n, lambda_=0.7)
```

**Why it's a problem:** If the import succeeds but mmr_rerank is not callable (e.g., the function is deleted or module-level exception during import), the call at line 787 will raise AttributeError/TypeError and propagate to the caller, breaking the recall path. The try-except only guards the import statement, not the function call. The "fail-open" documented contract (retrieval failures return [] vs propagate) is violated here because the fallback path (return results[:n]) is unreachable if import succeeds but call fails.

**Fix:** Wrap the mmr_rerank call itself in a try-except that falls back to `return results[:n]`:
```python
try:
    from memory.mmr import mmr_rerank
    candidate_pool = results[: max(n * 2, n + 2)]
    return mmr_rerank(candidate_pool, k=n, lambda_=0.7)
except (ImportError, AttributeError, TypeError):
    return results[:n]
```

**References:** memory_manager.py:782-787

---

### nit — 2

#### continuity.py:76 — global variable without clear initialization order
```python
def _get_current_mode() -> str:
    """Derive current_mode from cognition policy and evolution state."""
    global _mode_override
    if _mode_override:
        mode = _mode_override
        _mode_override = None  # consume: one-shot
        return mode
```

**Why it's a problem:** The module declares `_mode_override: str | None = None` at line 608, but _get_current_mode() at line 76 reads it before that module-level assignment executes in normal Python order. This works because Python executes module code top-to-bottom and _mode_override is defined before functions are called, but the code is fragile to refactoring. More importantly, if an exception occurs during module load before line 608, a call to _get_current_mode() will raise NameError. Current practice in the file (set_mode_override at line 611) makes this safe in practice, but it's a code-smell.

**Fix:** Move the `_mode_override` declaration to the top of the module, or document the required load order with a comment at line 76.

---

#### memory_scoring.py:416 — _STALE_NUMBER_HALF_LIFE_HOURS choice lacks evidence trail
```python
_STALE_NUMBER_HALF_LIFE_HOURS = 24.0
```

**Why it's a problem:** The constant is set to 24 hours per the comment ("Chosen to match the observation-window cadence"), but no baseline or A/B result is cited. If a future revision of consolidation moves to 6h or 48h windows, this constant should move with it, but there's no diagnostic to verify the choice is still correct. Not a bug—the comment is clear—but Polish opportunity: add a sentence explaining why 24h was chosen and link to any related test/metric.

**References:** memory_scoring.py:416, memory_scoring.py:414-415

---

## Coverage notes

- **Consolidation chunking (memory_manager.py:74-197)**: Solid. Oversize-entry truncation happens before chunking; char budget is conservative; failures logged; sub-summary fallback chain is correct. One harmless observation: if ALL chunks fail, the function returns None and consolidation aborts gracefully. No data loss.

- **Identity continuity (continuity.py + identity_ledger.py)**: Append-only invariant enforced; schema version checked; seeding is idempotent. Capsule age check is 24h (line 57). Cross-reference with birth.py is correct: continuity_id passed from ledger to capsule (line 411).

- **Perception cache (perception_cache.py)**: Thread-safe with RLock; get() always returns a copy (line 117-124), so consumers cannot mutate state. Freshness recomputed at read time (line 116). State transitions are correct (ERROR sticky until next set_value, line 183-184).

- **Timestamp consistency**: Audit found a minor gap (see Finding #1). Most of the codebase uses ISO 8601 with UTC offset. perception.py uses strftime (line 205), which produces "2026-04-22 12:34:56 UTC" — different format. Not a bug because these are separate paths (perception in format_snapshot, memory timestamps in store()), but worth noting if timestamps ever need to cross-reference.

- **MMR integration (mmr.py)**: Tokenization is sound; Jaccard similarity is correct (line 85-93). Number normalization (line 48-49) is intentional for disk-metric deduplication. Selection loop at line 135-152 is O(k²), which is acceptable for k ≤ 20.

---

## Sync observations

1. **memory_scoring → memory_manager**: Concept tag derivation (line 368 in memory_manager) is observational. Tags are stored but not yet used to gate promotion. Wiring is loose by design; no correctness issue.

2. **stale-number penalty (memory_scoring) → recall reorder (memory_manager)**: Correctly applied at line 664 with age_hours computed fresh at query time. No skew between when a memory is scored and when it decays.

3. **consolidation scoring feedback loop (memory_manager:530-555)**: Calls mark_consolidated() after LLM succeeds. If mark_consolidated() fails (DB error), the log reports it but does NOT stop the consolidation from succeeding. Correct fail-open behavior.

4. **birth → memory tagging**: memory_phase_tag() at line 355 and 396 reads from birth.current_phase(). No caching; reads fresh on every store. Correct.

---

## Polish opportunities (flag only)

- memory_manager.py:416-418 — The _LAST_CONSOLIDATION_FILE read uses hardcoded path. Consider storing last timestamp in the sidecar recall_stats.db instead for centralized persistence.
- memory_scoring.py:423-449 — The stale-number patterns could benefit from a single comprehensive regex compiled once (module init) rather than iterating over a list of compiled regexes on every has_stale_number_claim call.
- perception_cache.py:192-195 — _compute_state() is called at read time for every get(), but freshness thresholds are static. Consider caching the computed state inline with the entry.
- continuity.py:292-344 — _generate_resume_instructions() tries LLM first, falls back to deterministic text. The fallback is never tested in the self-test block (line 336-446). Consider adding a mock LLM failure case.

