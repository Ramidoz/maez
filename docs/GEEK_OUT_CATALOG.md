# Maez Geek-Out Catalog

Catalog of natural-conversation failures where Maez's user-facing behavior
became visibly mechanical, safety-rail-shaped, or otherwise unnatural.

Purpose: make "fix the geek-outs" checkable. Each entry records the natural
prompt, symptom, root cause, fix, and regression evidence.

This catalog is not a prompt-tuning wishlist. Entries should close through
root-cause fixes plus regression tests.

Reuse rule: extend this catalog when a future natural conversation exposes a
new mechanical or safety-rail-shaped failure. Do not replace the catalog with a
fresh synthesis unless the entry format itself becomes insufficient.

Observation distinction: S1b producer observation is scoped to daemon-cycle
reasoning-residue events. Telegram-surface audit rewrites can be real geek-out
events without producing S1b `reasoning_residue` rows. A zero S1b producer
count after a Telegram audit rewrite is therefore not evidence that the
Telegram rewrite did not happen; it is a scope boundary of S1b.

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

---

## Entry 3 - Morning-Memory Audit Rewrite

**Observed:** 2026-05-13, Telegram.

**Natural prompt:**

> Do you remember today morning?

**Geek-out symptom:**

Maez replied:

> No. I have a memory gap from this morning. I don't have a grounded answer
> for that part.

The answer exposed the audit fallback phrase inside a normal bonded
conversation. It sounded like a safety rail rather than Maez naturally saying
it could not remember the morning.

**Root cause:**

`self_claim_audit` flagged two sentences on `telegram_surface` and rewrote in
sentence mode:

```text
2026-05-13 18:02:13 self_claim_audit | surface=telegram_surface flagged=2 mode=sentence kinds=judge
```

The literal phrase comes from `core/safety/self_claim_audit.py`:

```python
_REWRITE_SENTENCE = "I don't have a grounded answer for that part."
```

This is not caused by Telegram draft presence. TDP only produced empty draft
presence telemetry before the reply; the grounded-answer phrase is the
audit-rail rewrite path.

**Fix landed:**

Not yet.

**Regression test:**

Not yet. Needs a natural-text test for the prompt above that verifies Maez can
answer memory uncertainty without exposing `_REWRITE_SENTENCE` verbatim.

**Status:** open. Candidate fix should preserve legitimate self-claim refusal
while replacing the visible sentinel with a natural Telegram-surface rewrite.

---

## Entry 4 - Telegram Draft Presence Mobile Blank Space

**Observed:** 2026-05-13, Telegram desktop/Chrome and mobile.

**Natural prompt:**

> Testing draft presence

**Geek-out symptom:**

TDP succeeded at the Bot API/log level, but the user-visible client behavior
was weird:

- Desktop/Chrome showed platform-owned `typing` chrome at the top.
- Mobile showed a large blank space below the conversation.

The mobile blank space made the empty-draft presence feel broken rather than
present.

**Root cause:**

Likely Telegram-client rendering of an empty bot draft. Maez sent no
Maez-authored draft text and the final audited reply still worked, but Telegram
clients rendered the empty draft affordance differently across surfaces.

Observed telemetry:

```text
2026-05-13 17:59:36 telegram_draft_presence.attempted
2026-05-13 17:59:36 telegram_draft_presence.succeeded
2026-05-13 18:01:51 telegram_draft_presence.attempted
2026-05-13 18:01:52 telegram_draft_presence.succeeded
```

**Fix landed:**

Not yet. Operator-local TDP config was disabled after observation.

**Regression test:**

Unit tests cannot prove client chrome behavior. Needs live-client observation
or a revised surface strategy.

**Status:** open / disabled. Do not re-enable TDP until TDP-FOLLOWUP-1 decides
whether empty draft presence is acceptable, replaced by another presence
affordance, or abandoned.
