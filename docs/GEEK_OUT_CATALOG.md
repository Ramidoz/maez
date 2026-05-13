# Maez Geek-Out Catalog

Catalog of natural-conversation failures where Maez's user-facing behavior
became visibly mechanical, safety-rail-shaped, or otherwise unnatural.

Purpose: make "fix the geek-outs" checkable. Each entry records the natural
prompt, symptom, root cause, fix, and regression evidence.

This catalog is not a prompt-tuning wishlist. Entries should close through
root-cause fixes plus regression tests.

---

## Entry 1 - Recursive Grounded-Answer Fallback

**Observed:** 2026-05-13, Telegram.

**Natural prompt:**

> How's the body feeling?

**Geek-out symptom:**

Maez answered with the audit fallback phrase:

> I don't have a grounded answer for that part.

Then, when asked "Grounded answer for what part?", the reply explained the
fallback but repeated the same fallback phrase again, making the conversation
look recursive and unnatural.

**Root cause:**

`self_claim_audit` sentence-mode rewrite could inject
`I don't have a grounded answer for that part.` into a response that was
already quoting or explaining that same audit sentinel. The audit rail made
the follow-up look like Maez was looping.

**Fix landed:**

`2bcd894 fix(audit): prevent recursive fallback rewrites`

**Regression test:**

`tests.test_self_claim_audit.ShortCircuitRewrite.test_existing_audit_sentinel_never_gets_duplicated`

**Status:** closed mechanically; deeper audit false-positive tuning remains a
separate catalog item if reproduced.

---

## Entry 2 - Uninitialized Ledger Self-History Noise

**Observed:** 2026-05-13, `logs/maez.log`.

**Natural prompt context:**

Same Telegram conversation as Entry 1.

**Geek-out symptom:**

Every evidence-envelope build attempted to populate `self_history` from
`memory/ledger.db`, then logged:

```text
self_history population skipped (ledger lookup failed for db_path='/home/rohit/maez/memory/ledger.db'): no such table: turns
```

This did not directly rewrite the reply, but it meant the audit path was
operating with missing self-history context and noisy diagnostics.

**Root cause:**

`memory/ledger.db` can exist as a zero-byte / uninitialized file before
production ledger writes are authorized. The envelope builder treated any
provided ledger path as queryable, so an intentionally-not-live ledger looked
like schema drift on every turn.

**Fix landed:**

`5d27530 fix(envelope): quiet uninitialized ledger self-history`

**Regression tests:**

- `tests.test_envelope_builder.MissingDBTests.test_uninitialized_ledger_returns_empty_self_history_without_noise`
- `tests.test_envelope_observability_hardening.SelfHistoryPopulationLoggingTests.test_lookup_failure_logs_debug`

**Status:** closed mechanically. Real lookup failures still log at DEBUG;
uninitialized ledger now means "self_history unavailable" without noise.
