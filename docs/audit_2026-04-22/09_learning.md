# Learning subsystem (consequence + fabrication + residue + errors) — Audit (2026-04-22)

## Summary
Four modules implement Maez's mistake-memory pipeline: `consequence_memory` (persistent event store with token-overlap retrieval), `fabrication_memory` (self-claim audit log), `inner_residue` (transient emotional state with exponential decay), and `error_classifier` (backend error taxonomy). Audit found one blocker token-filtering bug in consequence_memory.relevant() and two major connection-lifetime defects in fabrication_memory and inner_residue where DB connections are never closed, risking resource exhaustion under high-frequency calling.

## Findings

### blocker — 1

#### consequence_memory.py:290 — Token filter inconsistency causes retrieval gaps
```python
query_tokens = {
    t.lower() for t in context_snippet.split()
    if len(t) > 2 and t.isalnum()        # ← FILTER 1: rejects "git-push", "my_script", "http://x"
}
...
for e in pool:
    haystack = " ".join([e.context, e.outcome, e.feedback,
                          " ".join(e.tags)]).lower()
    tokens = {t for t in haystack.split() if len(t) > 2}  # ← FILTER 2: accepts "git-push"
    overlap = len(query_tokens & tokens)
```

**Why it's a problem:** Query-side applies `.isalnum()` which filters out tokens with hyphens, underscores, dots (e.g., "git-push", "my_script.py", "http://example.com"). Haystack-side has no such filter, so stored events with these tokens will never match queries containing them. A user typing "python script failed" won't retrieve stored events about "my_script.py" failures because the tokens never overlap. This silently degrades retrieval quality without error.

**Fix:** Remove `and t.isalnum()` from line 290, or add the same filter to line 305. Consistency is the goal — token treatment should be identical on both sides. Recommend removing the isalnum check entirely since hyphenated/underscored tokens are meaningful (git-push, my_script) and the haystack side already accepts them.

**References:** Identical token filtering was added to the query side (concern #2 in self-dev review 261a8db) but the haystack filter wasn't updated to match.


### major — 2

#### fabrication_memory.py:98, 131, 188, 216 — Connections never closed, file descriptor leak
```python
def _ensure_db() -> Optional[sqlite3.Connection]:
    ...
    db = sqlite3.connect(_DB_PATH, timeout=2.0, check_same_thread=False)
    ...
    return db  # ← Connection handed back

def record(surface: str, flags: list, mode: str) -> None:
    ...
    db = _ensure_db()  # ← Assigned to local var
    if db is None:
        return
    db.executemany(...)
    db.commit()
    # ← END OF SCOPE: db is dropped, connection never closed
```

**Why it's a problem:** Every call to `record()`, `top_tokens()`, `few_shots_for()`, and `_diag_clear_for_test()` opens a connection via `_ensure_db()` and never closes it. In a long-running daemon (which this is), hundreds of calls per hour will leak file descriptors. SQLite will eventually hit `SQLITE_CANTOPEN` ("too many open files") or the OS will run out of file descriptors, causing silent failures or crashes.

**Fix:** Wrap the connection in `contextlib.closing()` — the pattern consequence_memory.py uses correctly on every call site. See consequence_memory.py:181, 212, 239, 327 for the correct pattern. Change `db = _ensure_db()` to `with contextlib.closing(_ensure_db()) as db:` and move the body inside the with block.

**References:** self-dev review 261a8db concern #1 explicitly identified sqlite3 context managers don't close connections. consequence_memory applied the fix; fabrication_memory and inner_residue did not.


#### inner_residue.py:102, 130, 155 — Connections never closed, file descriptor leak
```python
def _ensure_db() -> Optional[sqlite3.Connection]:
    ...
    db = sqlite3.connect(_DB_PATH, timeout=2.0, check_same_thread=False)
    ...
    return db  # ← Connection handed back

def record(kind: str, ...):
    ...
    db = _ensure_db()  # ← Assigned to local var
    if db is None:
        return
    db.execute(...)
    db.commit()
    # ← END OF SCOPE: db is dropped, connection never closed

def current_level(now: Optional[float] = None) -> float:
    ...
    db = _ensure_db()  # ← Same problem in reader path
    ...
    rows = db.execute(...).fetchall()
    # ← Connection leaked

def recent_events(...):
    ...
    db = _ensure_db()  # ← Same problem
    rows = db.execute(...).fetchall()
    # ← Connection leaked
```

**Why it's a problem:** Identical to fabrication_memory — every call to `record()`, `current_level()`, and `recent_events()` leaks a connection. inner_residue is called on every cycle turn (brain_loop, decision_pipeline) so the leak is systematic and frequent. Over hours, file descriptor exhaustion becomes certain.

**Fix:** Wrap all `_ensure_db()` calls in `contextlib.closing()`. See consequence_memory.py for the correct pattern. Apply to all five call sites: record() line 102, current_level() line 130, recent_events() line 155, _diag_total_rows() (not shown but likely affected), _diag_clear_for_test() (not shown but likely affected).

**References:** Same self-dev review 261a8db concern #1; same fix applied correctly in consequence_memory.py but missed in inner_residue.py.


### minor — 0


### nit — 2

#### consequence_memory.py:170–175 — Unknown kind warning logs sorted() but set is unordered
```python
logger.warning(
    "consequence_memory: unknown kind %r (known: %s) — "
    "recording anyway",
    kind, sorted(_KNOWN_CLASSES),
)
```

**Why it's a problem:** Minor polish: sorted() is called on a frozenset, but the output order is deterministic so the warning is readable. Not a bug, just unnecessary since _KNOWN_CLASSES is immutable. The log message will always be in the same sorted order, which is fine. Flag only; not a functional issue.

**Fix:** Optional. Keep as-is for consistency with similar warning patterns elsewhere, or simply remove sorted() since order doesn't matter. No urgency.


#### error_classifier.py:210 — isinstance() check redundant with error_type membership test
```python
if error_type in _TIMEOUT_ERROR_TYPES or isinstance(error, TimeoutError):
    ...
if error_type in _CONNECT_ERROR_TYPES or isinstance(error, ConnectionError):
```

**Why it's a problem:** Lines 210 and 217 check both type name membership and isinstance(). The isinstance() checks are redundant — if `type(error).__name__` is in the frozenset, the object IS an instance of that type. However, this is intentional defense-in-depth: the isinstance() guards against custom exception subclasses that might not match the name check. This is reasonable defensive coding, not a defect. Keeping it is safer than removing it.

**Fix:** None. This is intentional redundancy for robustness. Flag only as "defensive but mildly verbose."


## Coverage notes

- **Readers:** consequence_memory.relevant() (1 blocker), recent(), stats(), format_for_prompt(). Inner_residue current_level(), recent_events(), prompt_snippet(). Error_classifier classify(), emit_telemetry().
- **Writers:** consequence_memory.record_event(), mark_heeded(). Fabrication_memory.record(), record_event(). Inner_residue.record(). Error_classifier has no writers (observational only).
- **Connection pooling:** consequence_memory correctly uses contextlib.closing() on every access. fabrication_memory and inner_residue leak connections on every call. No connection pooling observed; each call opens and (should) close a fresh connection.
- **Test coverage:** consequence_memory has 214 LOC tests (7 test classes, 24 assertions). fabrication_memory has 280 LOC tests. error_classifier has 145 LOC tests. Tests pass but don't cover the connection-leak scenario (tests are short-lived, don't expose FD exhaustion).
- **Dead code:** None identified. All functions are called by producers (brain_loop, decision_pipeline, self_claim_audit, cognition_quality bootstrap).

## Sync observations

- **Concept duplication candidate:** fabrication_memory and consequence_memory store overlapping classes: consequence_memory::CLASS_CARD_REJECTED captures user rejections; fabrication_memory captures self-claim audit flags (grounding failures). These are orthogonal: fabrication is a specific audit event class; consequence is broader (tool failure, user correction, etc.). No action needed, but a future schema could unify them as kind=fabrication, kind=audit_flag, etc. Flag only.
- **mark_heeded() wiring:** brain_loop correctly calls mark_heeded() after surfacing consequences to the planner (line 927–933). Called consistently when events are rendered for the user-facing prompt. Good hygiene.
- **Consumer call patterns:** brain_loop calls relevant() with user_text as the query and window_hours=168. decision_pipeline records card rejections with action + cmd context. No observed misuse of window_hours or limit parameters.
- **inner_residue detection:** Rejection markers are conservative (lines 232–237): "that's wrong", "you're lying", "bullshit" are exact substrings. A bare "no" is not detected, which is correct (it's a common answer, not a rejection of Maez). Good conservatism.

## Polish opportunities (flag only)

- **error_classifier:** Module docstring (lines 3–46) mentions "Hermes's 830-line version" and copyright borrowing (MIT). Consider dropping the Hermes reference after the system stabilizes — it's historical context for maintainers, not load-bearing for operation.
- **fabrication_memory & inner_residue:** Both use global `_initialized` to guard schema creation. This pattern is thread-safe (sqlite3.connect is thread-safe) but the guard itself is not atomically checked-and-set. If two threads call _ensure_db() simultaneously, both might run executescript(). SQLite's CREATE TABLE IF NOT EXISTS is idempotent so no corruption occurs, but a double-init is wasteful. Upgrade to a Lock-guarded check if this becomes observable. Low priority.
- **consequence_memory.recent():** When window_hours is 0 (meaning "events from the last 0 hours" = none), the query correctly returns empty via `if window_hours is not None`. The fix from 261a8db is correct and defensive. No change needed.

