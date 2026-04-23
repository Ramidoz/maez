# Decision pipeline + approvals — Audit (2026-04-22)

## Summary

The decision pipeline correctly gates every action through a multi-layer filter (covenant → classification → injection → audit → will-I) before execution or card creation. The pending cards store implements a sound state-machine with proper state hash guardianship after the 8d8c82d fix. One data-loss risk identified: `will_i_refusal` on post-approval closes the card before execution, but if execution then fails, the failure state is recorded against an already-resolved card. Also flagged: consequence_memory record on deny has no validation for circular JSON structures, and a potential misalignment in how audit_request_id is threaded through dialog-routed approvals.

## Findings

### blocker — 1

#### decision_pipeline.py:905–912 — Will-I refusal leaves card resolved before execution attempt
```python
will_refuse = self._will_i_check(
    card.action, card.params,
    post_approval=True,
    audit_req_id=card.audit_request_id,
    card=card,
)
if will_refuse is not None:
    return will_refuse
```

**Why it's a problem:** `_will_i_check()` with `post_approval=True` calls `card_store.deny()` (line 618) to close the card with status=DENIED. If this returns cleanly, the card is now TERMINAL. The caller then returns immediately without attempting execution. However, if line 920's `action_engine._execute_action()` is reached (e.g., in a code path that doesn't call will-I), that execution can fail. The asymmetry means: will-I refusals close the card first, but normal execution failures can still call `mark_failed()` against a card that was supposed to be in APPROVED/RUNNING. This breaks the contract that TERMINAL cards don't transition further (line 925 allow_from={APPROVED, RUNNING} will fail if the card was already denied by will-I and somehow re-entered).

More critically: if will-I fires AFTER `mark_running()` (line 918), the card is RUNNING and will-I denies it. The deny happens at line 618, moving card to DENIED. Then execution attempts proceed anyway at line 920, fail, and line 936 tries `mark_failed(RUNNING -> FAILED)` against a card that's already TERMINAL. The guard at 565-568 in pending_cards.py catches this and raises CardStoreError, which is NOT caught in _on_approve, causing an unhandled exception to propagate.

**Fix:** Either (a) refactor so will-I check happens BEFORE mark_running, or (b) catch CardStoreError from mark_failed/mark_done and log without crashing, treating it as "card was already resolved by will-I so this execution outcome is a no-op."

**References:** Lines 905-912 (will-I post-approval), 918 (mark_running), 920 (execute), 936 (mark_failed), 565-568 in pending_cards.py (transition guard).

### major — 1

#### consequence_memory.py integration in decision_pipeline.py:1006–1030 — Untrusted JSON in card.params fed to consequence_memory
```python
try:
    from core import consequence_memory as _cm
    import json as _json
    _action = getattr(card, "action", "unknown")
    _params = getattr(card, "params", {}) or {}
    _cmd = _params.get("cmd") if isinstance(_params, dict) else ""
    _context = f"action={_action} cmd={_cmd!r}" if _cmd else f"action={_action}"
    _cm.record_event(
        kind=_cm.CLASS_CARD_REJECTED,
        context=_context[:400],
        outcome=cls.reasoning[:300] if cls.reasoning else "denied",
        feedback="",  # open for future enrichment
        surface="decision_pipeline",
        tags=[_action] + ([_cmd.strip().split()[0]]
                            if _cmd and _cmd.strip().split()
                            else []),
        extra={"request_id": card.request_id},
    )
except Exception:
    pass
```

**Why it's a problem:** At line 1000–1001, card.params is retrieved from SQLite without validation. If params contains a circular reference or malicious JSON structure, the `extra={"request_id": card.request_id}` dict concatenation at line 1027 is safe, but consequence_memory.record_event() is called without catching potential errors from bad params serialization. The outer try/except swallows all failures (line 1029), so the user never knows the rejection wasn't recorded in consequence_memory. This creates a silent partial failure: the card is properly denied and logged to audit_log, but the long-term learning memory is silently skipped. On the next planning cycle, an identical action may be proposed again because the rejection never reached consequence_memory.

**Fix:** Validate card.params for JSON-serializability before passing to consequence_memory, or wrap the consequence_memory call in a separate try/except with logging (not silent).

**References:** Lines 1011–1030, consequence_memory.py integration.

### major — 2

#### decision_pipeline.py:851 — Dialog-routed approval uses synthetic classification without audit_request_id propagation
```python
result = self._on_approve(card, _SyntheticCls(), user_id)
```

**Why it's a problem:** In `_handle_dialog_reply_for_card()`, when a self-mod dialog yields "ratified" (line 843), the code synthesizes a classification object at lines 848–850 with only `source` and `reasoning` fields. Then it calls `_on_approve(card, _SyntheticCls(), user_id)`. The _SyntheticCls has no audit_request_id or other audit metadata, so when _on_approve records the outcome at lines 933–934 with `card.audit_request_id`, the audit_request_id is looked up from the card, NOT from the classification. This works, but it's a fragile dependency: if future code refactors _on_approve to trust cls.audit_request_id instead of card.audit_request_id, the dialog path will silently record the outcome under the wrong audit row. The pattern also breaks the contract that cls (a ReplyIntent from the normal classifier) has consistent structure.

**Fix:** Either (a) have _SyntheticCls include audit_request_id (copy from card), or (b) add a comment explaining why _on_approve must use card.audit_request_id, not cls.audit_request_id, making the contract explicit in the code.

**References:** Lines 843–851, 848–850 (_SyntheticCls definition), 933–934 (outcome recording).

### minor — 1

#### pending_cards.py:301–303 — Silent schema migration on every store init
```python
try:
    conn.execute("ALTER TABLE pending_cards ADD COLUMN plain_english TEXT")
except Exception:
    pass  # column already exists
```

**Why it's a problem:** This migration attempt runs synchronously in `__init__`, every time a PendingCardStore is instantiated. If two processes initialize the store concurrently (e.g., daemon + a manual script), both will attempt the ALTER TABLE. SQLite serializes these, but the pattern is fragile: silent exceptions hide genuine schema corruption or permission errors. The comment "column already exists" assumes the only failure mode is "already added," but a corrupted DB or read-only filesystem will also raise, then be silently ignored. On the next operation, the code will fail with a cryptic "no such column" error.

**Fix:** Check if the column exists before attempting ALTER (query pragma table_info), or move schema migrations to a separate setup script that runs once at provisioning time.

**References:** Lines 299–303 in pending_cards.py.

### minor — 2

#### decision_pipeline.py:593 — Undefined logger in _will_i_check
```python
logger.debug(
    "will-I check failed (action=%s): %s — proceeding",
    action, e,
)
```

**Why it's a problem:** Line 593 references `logger` which is never imported or initialized at the module level. The code will raise NameError if will_i.check() raises an exception. The surrounding try/except catches the exception from will_i but then tries to log using an undefined name, which is a second exception that will propagate to the caller. However, this is masked by the outer except clause at line 612 in _on_deny which catches all exceptions, so the user sees a silent failure in consequence_memory recording rather than a clear error. The root cause is unreported.

**Fix:** Add `import logging; logger = logging.getLogger(__name__)` at the module top, or use a bare logging call like `logging.getLogger(__name__).debug(...)`.

**References:** Line 593.

### minor — 3

#### proposal_lookup.py:49–50 & 74 — Hardcoded timeout=1.5 may be too aggressive
```python
conn = sqlite3.connect(_EVOLUTION_DB, timeout=1.5)
```

**Why it's a problem:** Both _fetch_evolution_candidate() and _fetch_dream_proposal() use a fixed 1.5-second timeout for SQLite connections. If the daemon is under load and the proposal_lookup happens to contend with a card write, the timeout can fire, returning None and masking the proposal from the user ("proposal #25 not found"). The timeout is a good guard against hangs, but 1.5s is arbitrary. If the lookup is called from a time-sensitive context (e.g., a Telegram reply), the timeout firing looks like a data loss to the user, not a transient contention. No logging happens on timeout, so the operator never knows the DB was slow.

**Fix:** Increase timeout to 3.0+ seconds, or log a warning when timeout occurs, or both.

**References:** Lines 49, 74 in proposal_lookup.py.

### nit — 1

#### pending_cards.py:253 — Unnecessary inline default in _row_to_record
```python
plain_english=row["plain_english"] if "plain_english" in row.keys() else None,
```

**Why it's a problem:** This is defensive code written for a schema migration (plain_english was added after initial deployment). The check `if "plain_english" in row.keys()` is no longer necessary: the ALTER TABLE in __init__ ensures the column exists. The pattern is a code smell indicating incomplete migration cleanup. For consistency, other fields like audit_reasoning assume the column exists and use `row["audit_reasoning"] or ""` directly.

**Fix:** Remove the defensive check; trust the schema. This simplifies line 253 to `plain_english=row["plain_english"]`.

**References:** Line 253 in pending_cards.py.

### nit — 2

#### decision_pipeline.py:268 — plain_english param popped before classification, discarded if INVALID
```python
params = dict(params or {})
plain_english = params.pop("plain_english", None)  # LLM-authored human description, not a command param
```

**Why it's a problem:** The plain_english param is extracted and stored in the card at line 483. However, if the action is rejected by the required-param guard (lines 275–282), the pipeline returns early and never creates a card, so plain_english is lost. This is correct behavior (we don't want to record a malformed action), but it's worth noting that plain_english is silently discarded on validation failures. If a caller relies on plain_english appearing in the card, they'll find it missing for rejected actions. Not a bug, but an asymmetry worth documenting.

**Fix:** Add a comment at line 268 noting this is intentional (plain_english is LLM-internal metadata, not validated, discarded on param rejection).

**References:** Lines 268, 275–282, 483.

## Coverage notes

- **State hash edge case (fixed):** The 8d8c82d commit correctly treats state_hash="empty" as "caller declined to bind state" and skips expiration. Testing confirms (lines 837–838, 890–895 in pending_cards self-test).
- **Terminal state guard:** The _transition() guard at 565–568 in pending_cards.py correctly blocks transitions from terminal states, but this is not exercised by the decision_pipeline self-test (Case 9 at lines 1336–1349 creates an ESCALATE card but doesn't test terminal-state rejection).
- **Audit log atomicity:** The pipeline records to audit_log after verdict, but before card creation. If card_store.create_card() fails, the audit row exists but no card was created—this asymmetry is acceptable (audit is a log, not a transaction), but should be documented.
- **Consequence memory learning:** New in this session; no test coverage for the consequence_memory integration path. Edge cases around empty/None reasoning untested.

## Sync observations

- **Inner residue vs. consequence_memory:** Both are called on deny (lines 996–1004, 1011–1030). They serve different purposes (transient tone vs. persistent learning), but share the same event semantics. No cross-store validation.
- **Will-I & audit_log.record_outcome:** The will-I refusal calls `audit_log.record_outcome(..., outcome="refused_by_will", ...)` at line 607. This competes with the normal execution-outcome recording at lines 934/938. Both write to the same audit row. If both fire, the second write overwrites the first (no conflict detection). The current design relies on the early return at line 912 to prevent this, but that's implicit.
- **Approval-sessions integration:** Lines 413–425 check approval_sessions.is_read_safe_cmd() and can promote a card-worthy action to Lane 0 without re-running the audit. This is intentional (user already granted blanket permission), but it means some actions skip the injection/audit layer entirely for already-approved operations—worth documenting as a feature.

## Polish opportunities (flag only)

- **Unused params in _SyntheticCls:** The synthetic classification objects (lines 848–850, 861–863) are minimal stubs. Consider adding type hints or a NamedTuple to make the contract explicit.
- **Exception handling asymmetry:** Some code paths use `except Exception: pass` (lines 302, 360, 533, 626, 1003, 1030), others log (lines 539–543, 995–1004). Standardize to either log all failures or document when silent failures are acceptable.
- **CardStoreError in _on_approve:** No explicit exception handling. If mark_running() or mark_done() raises CardStoreError (e.g., card already terminal due to will-I), it propagates uncaught. This is harsh but explicit; document the expected invariant or catch it gracefully.
