# Evolution subsystem — Audit (2026-04-22)

## Summary

The evolution subsystem (soul/wants/will/temperament/wonderings/dream_state/wondering_cycle) implements identity + drive scaffolding with strong intent but a critical race condition in soul.local.md append, logging of NaN values in tempera‌ment, and widespread test coverage gaps. No silent invariant violations detected; safeguards are load-bearing. The test gap is the highest-severity issue—five of nine modules have zero production tests.

## Findings

### blocker — 1

#### soul_loader.py:119 — Soul.local.md append race condition

```python
def append_to_local(text: str, *, separator: str = "\n\n") -> None:
    """Append new content to soul.local.md. Used by dream-proposal apply."""
    if not text:
        return
    local_path = paths.soul_local_path()
    try:
        existing = local_path.read_text() if local_path.exists() else ""  # LINE 119: READ outside lock
    except Exception:
        existing = ""
    suffix = separator if existing and not existing.endswith(separator) else ""
    with _lock:
        local_path.write_text(existing + suffix + text)  # LINE 124: WRITE inside lock
        global _cache_text, _cache_signature
        _cache_text = None
        _cache_signature = None
```

**Why it's a problem:** The read of `existing` happens outside the `_lock` (line 119), but the write happens inside (line 124). Between the read and write, another thread can write to `soul.local.md`. Timeline: Thread A reads `existing=""`, Thread B reads `existing=""`, Thread A writes `"A"`, Thread B writes `"B"` (overwrites A). Result: lost dream proposals + soul.local.md truncation. This is a silent data loss on dream-proposal apply.

**Fix:** Move the `local_path.read_text()` call inside the `with _lock:` block:
```python
local_path = paths.soul_local_path()
with _lock:
    existing = ""
    try:
        existing = local_path.read_text() if local_path.exists() else ""
    except Exception:
        pass
    suffix = separator if existing and not existing.endswith(separator) else ""
    local_path.write_text(existing + suffix + text)
    global _cache_text, _cache_signature
    _cache_text = None
    _cache_signature = None
```

**References:** soul_loader.py:113–127; append_to_local is called by dream_state.apply_proposal() and action_engine.write_soul_note()

### major — 1

#### temperament.py:254 — NaN in log output

```python
logger.info(
    "Temperament: %s %.3f -> %.3f (source=%s, event_id=%d, reason=%s)",
    parameter,
    prior if prior is not None else float("nan"),  # LINE 254
    value_f,
    source,
    event_id,
    (reason or "")[:80],
)
```

**Why it's a problem:** When `prior` is None (first event for a parameter), the code logs `float("nan")`. The logger formats this as the literal string `"nan"`, which appears in log files and could confuse monitoring/parsing tools. While not a functional bug (the database stores the correct NULL and code never reads the log back), it's unnecessarily noisy and non-standard. The pattern contradicts the intent of the prior_value column which explicitly uses NULL.

**Fix:** Log the prior value without the sentinel conversion:
```python
logger.info(
    "Temperament: %s %s -> %.3f (source=%s, event_id=%d, reason=%s)",
    parameter,
    f"{prior:.3f}" if prior is not None else "NULL",
    value_f,
    ...
)
```

**References:** temperament.py:251–259

### major — 2

#### soul_editor.py:158–175 — Schema migration in _init_schema missing closure/commit

```python
def _init_schema(self) -> None:
    with self._lock, self._conn() as c:
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS dream_proposals (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at    REAL NOT NULL,
                insight       TEXT NOT NULL,
                status        TEXT NOT NULL DEFAULT 'pending',
                applied_at    REAL,
                reject_reason TEXT
            )
            """
        )
        # Session 11s: schema migration for soul section-replace proposals
        existing_cols = {
            row[1] for row in c.execute("PRAGMA table_info(dream_proposals)")
        }
        if "proposal_type" not in existing_cols:
            c.execute(
                "ALTER TABLE dream_proposals ADD COLUMN "
                "proposal_type TEXT NOT NULL DEFAULT 'append'"
            )
        # ... more ALTER statements ...
```

**Why it's a problem:** The SQLite connection manager in dream_state._init_schema() (lines 142–186) does not explicitly call `c.commit()` after the schema migrations. The context manager calls `conn.commit()` on normal exit (line 170 in the _conn method), but this happens in _init_schema which is a different method. While the WAL mode pragma ensures eventual durability, explicit commit semantics are clearer and required for robustness if an exception occurs during ALTER TABLE chains. The existing code relies on implicit commit via context manager exit—which works but is fragile.

**Fix:** Add explicit `c.commit()` after the migration block:
```python
def _init_schema(self) -> None:
    with self._lock, self._conn() as c:
        c.execute("CREATE TABLE IF NOT EXISTS dream_proposals (...)")
        # ... ALTER TABLE statements ...
        c.commit()  # Explicit commit after migrations
        c.execute("CREATE INDEX IF NOT EXISTS ...")
```

**References:** dream_state.py:141–186

### minor — 1

#### wondering_cycle.py:246 — Non-blocking lock acquire always succeeds on first call

```python
ollama_lock = getattr(daemon, "_ollama_lock", None)
acquired = True
if ollama_lock is not None:
    acquired = ollama_lock.acquire(timeout=0)  # LINE 246
if not acquired:
    _emit_outcome(wondering=wondering, action="skipped_lock_busy")
    return {"wondering_id": wondering["id"],
            "action": "skipped_lock_busy"}
```

**Why it's a problem:** The variable `acquired` is initialized to `True` (line 244). If `ollama_lock is None`, the acquire is skipped and `acquired` remains True. This is intentional — the code should proceed if there's no lock to check. However, the logic is slightly counterintuitive: the variable name `acquired` suggests "we got the lock," but if the lock doesn't exist, we're proceeding without acquiring anything. This is correct behavior (non-blocking acquire of absent lock = proceed), but the semantics are muddled. Minor code smell.

**Fix:** Clarify with a comment or rename:
```python
ollama_lock = getattr(daemon, "_ollama_lock", None)
can_proceed = True  # Renamed from 'acquired' for clarity
if ollama_lock is not None:
    can_proceed = ollama_lock.acquire(timeout=0)
if not can_proceed:
    ...
```

**References:** wondering_cycle.py:243–250

### minor — 2

#### temperament.py:372 — PARAMETER_NAMES claims 12 entries but list has 12

```python
_assert(len(PARAMETER_NAMES) == 12,
        "PARAMETER_NAMES has exactly 12 entries")
```

**Why it's a problem:** The assertion comment says "exactly 12 entries" and the count is correct (curiosity through empathy = 12 parameters). However, the design doc at the top of the file (lines 17–20) lists them as "1. curiosity ... 11. joy ... 12. empathy" but only 11 of the descriptive text is shown before empathy. The source comment lines 105–118 correctly enumerate all 12. This is a documentation consistency issue, not a code bug, but it creates confusion about whether the count is intentional. The docstring says "Eleven named parameters" (line 3) but the actual list is 12.

**Fix:** Update the module docstring (line 3) and design notes (lines 17–20) to say "twelve" instead of "eleven":
```python
"""Temperament skeleton. Twelve named parameters, stored as an
append-only event log..."""
```

**References:** temperament.py:1–20 vs. 105–118

### nit — 1

#### soul_invariants.py:104 — Regex whitespace normalization could be more defensive

```python
pattern: re.compile(
    r"(?:not\s+a\s+tool|not\s+a\s+servant|partnership|presence|partner)",
    re.IGNORECASE,
),
```

**Why it's a problem:** The regex allows flexible whitespace (`\s+`) for phrases like "not a tool" but is greedy and doesn't require word boundaries. A badly formatted soul.md with "not a tool" split across lines (e.g., "not a\ntool") would match correctly because `\s` includes newlines. However, a phrase like "partnership" with no word boundary will match inside a longer word like "subpartnership" or "codepartnership" (unlikely but possible). This is a minor regex hygiene issue—the fix is to add word boundaries.

**Fix:** Add word boundaries `\b`:
```python
pattern: re.compile(
    r"(?:not\s+a\s+tool\b|not\s+a\s+servant\b|partnership\b|presence\b|partner\b)",
    re.IGNORECASE,
),
```

But this requires a design pass to confirm the intent. For now, the current pattern is acceptable because the soul.md is human-maintained and these strings are unlikely to appear in compound words.

**References:** soul_invariants.py:99–105

## Coverage notes

**Test gap severity: CRITICAL** — This is the highest-impact finding in the audit. Per Phase 0 inventory, zero tests exist for:
- **soul_editor.py** (449 LoC) — complex proposal/apply logic, parse round-trip, backup atomicity, protected phrase guards. No tests for stale proposal detection, preamble protection, duplicate consolidation.
- **wants.py** (590 LoC) — append-only event log, provenance allowlist, column length caps, event type validation. Self-test exists as `if __name__ == "__main__"` but no unittest file.
- **will_i.py** (303 LoC) — impersonation ground check, sender-identity field extraction. Self-test exists but no unittest file.
- **temperament.py** (520 LoC) — parameter validation, value range clamping, prior_value tracking, current()/history() queries. Self-test exists but no unittest file.
- **dream_state.py** (767 LoC) — dream cycle gate logic, novelty checking (Jaccard, topic-level), proposal storage/apply, schema migration. No tests.

Only **wonderings.py** and **soul_invariants.py** have dedicated test files (/tests/test_wonderings.py, /tests/test_soul_invariants.py).

This gap is dangerous because:
1. The soul_editor race condition would not have been caught by the existing test suite.
2. Proposal parsing edge cases (empty sections, EOF-trailing newlines) are untested.
3. Dream proposal novelty thresholds (Jaccard=0.15, NOVELTY_TOPIC_JACCARD_MIN=0.10) have no regression tests; the 2026-04-22 comment shows three separate threshold tweaks in recent sessions, all driven by observational drift rather than test-driven validation.
4. Temperament decay math (currently static in Track A, but ready for future drift algorithms) has no baseline tests; adding a drift algorithm later will be risky without test coverage.

**Recommendation:** Before Track B drift/reasoning-loop wiring:
1. Add test_soul_editor.py covering parse/serialize round-trip, stale proposal detection, preamble guard, protected phrases.
2. Convert self-test blocks in wants.py, will_i.py, temperament.py into unittest files in /tests/.
3. Add test_dream_state.py covering dream gate logic, novelty checks (Jaccard thresholds are load-bearing), proposal CRUD.
4. Add test_wondering_cycle.py covering advance_one gate logic (lock non-blocking discipline, deadline budget).

## Sync observations

1. **soul_loader ↔ soul_editor ↔ action_engine:** Write flow is correct. Dream proposals append to soul.local.md via soul_loader.append_to_local (which should be fixed for the race condition). Section edits go through soul_editor.apply_section_replace. Both paths invalidate the cache correctly. The daemon's soul watcher picks up MD5 changes within 10s.

2. **wondering_cycle ↔ llm_client:** Non-blocking lock acquire is correct and intent-preserving. If the ollama_lock is held (primary cycle), wondering_cycle yields entirely. No degradation of the main loop.

3. **wonderings ↔ action_engine:** Deferred probes are correctly queued as pending cards. The unblock_from_card flow merges the real command output into the probe row. No sync issues detected.

4. **dream_state ↔ memory_manager:** Dream proposals are stored locally and sent to Telegram for approval. No feedback loop into memory. Correct isolation.

## Polish opportunities (flag only)

1. **soul_editor.py:128–129** — The `identity_key()` method on Section strips and lowercases, then deduplicates. This is used for duplicate detection, but the actual section name is preserved. Consider documenting that identity_key is only for dedup; the real name stays the same.

2. **wants.py:291–298** — The self-test in the `if __name__ == "__main__"` block is thorough but not discoverable by pytest. Moving to /tests/test_wants.py would integrate it into the test suite.

3. **dream_state.py:75–100** — The comment "11u fix: 0.4 was too lenient" and "2026-04-22 fix: after 5 hourly dreams..." shows iterative threshold tuning driven by observation. Document the rationale for each threshold in a separate design decision or move to docs/governance/.

4. **temperature.py:254** — The `float("nan")` log output can be replaced with a cleaner `"NULL"` string as suggested above.

---

**Audit completed:** 2026-04-22  
**Scope:** 9 files, ~3,700 LoC  
**Blockers found:** 1 (race condition in soul_loader)  
**Major issues:** 2 (NaN logging, schema commit semantics)  
**Minor issues:** 2 (lock logic clarity, parameter count documentation)  
**Nits:** 1 (regex word boundary)  
**Test coverage gap:** CRITICAL — 5 of 9 modules untested
