# Recovery Jarvis Passes Can Create Multiple Orphan Cards

**Status:** Deferred follow-up. Not blocking Track A. Observed on 2026-04-15 during Fix 6 v1 live test. Partially mitigated by Fix 6 v3 (expire orphans on cap hit), but the underlying bug is structural.

## The bug

During a recovery pass triggered by a failed card, the Jarvis loop iterates up to 4 times. Each iteration can emit a tool call that goes through `pipe.handle_action`. For Lane 2 actions (`run_shell`, `write_any_file`), `handle_action` creates a `PendingCard` in `status='open'` and returns `PipelineStatus.PENDING_APPROVAL`.

**The LoRA sometimes emits multiple Lane 2 tool calls in a single recovery pass** — proposing variant A, then variant B, then variant C — before hitting the STATE_A or STATE_B terminal state that was supposed to end the pass with a single concrete proposal.

**The result:** multiple cards created from one recovery pass, only the most recently rendered card is visible to the user in Telegram, the user's approval (*"Proceed"*, *"Yes"*, *"go ahead"*) fires on the most recent card only. Earlier cards stay `status='open'` indefinitely, orphaned. The user never sees them, never approves or denies them, and they're just sitting in the card store waiting to accidentally match a future reply classifier pattern.

Observed on 2026-04-15, depth=2 recovery pass for openrgb:
- 01:14:20 — card `1d6da157` created (software-properties-common + PPA + install)
- 01:14:26 — card `a58676c8` created (same shape, variant)
- 01:14:45 — the owner said *"Proceed"* → approved `a58676c8` (most recent)
- `1d6da157` stayed `status='open'`
- 01:15:12 — the owner said *"What happened"* → reply classifier matched `1d6da157` as RE_EXPLAIN → re-presented the orphan card in Telegram, confusing the user

## Why it happens

The recovery seed prompt instructs the LoRA to end in exactly one terminal state (STATE_A concrete proposal OR STATE_B `NO_RECOVERY_FOUND`). But the LoRA doesn't always obey the terminal-state discipline cleanly. It sometimes proposes A, realizes A has a flaw, proposes A' as a refinement, and only after the second proposal writes DONE. From the LoRA's perspective, the second proposal is the real answer. From the pipeline's perspective, BOTH proposals became cards.

The structural hole: `pipe.handle_action` is a one-way commit. Once a card is created, there's no "rollback" or "supersede" mechanism from within the same Jarvis loop. If the LoRA changes its mind and proposes a better variant, the earlier card is already live in the store.

## What Fix 6 v3 does (mitigation, not fix)

When the recovery cap hits (depth > 2), Fix 6 v3 walks the card store for open cards in this chat created within the 30-minute chain window and explicitly expires them with the reason *"chain abandoned after recovery cap hit"*. This prevents orphans from confusing reply classification **after** the chain has terminated.

But it does NOT prevent orphans from existing during an active chain. If the recovery pass at depth=1 creates two cards, one of them is orphaned the moment the user approves the other. That orphan persists through depth=2 and depth=3 recoveries. Fix 6 v3 only cleans it up at cap hit.

**If a user happens to send a follow-up message BETWEEN recovery passes (e.g., *"what's going on?"* while a recovery is mid-flight), the orphan can still confuse classification.** This is unlikely but possible.

## The real fix (not Track A)

Three architectural options, ordered by cleanness:

### Option 1: Single-card-per-pass discipline at the Jarvis loop level

Modify `_run_jarvis_loop` so that during recovery passes (`recovery_seed is not None`), the FIRST Lane 2 tool call dispatched creates a card and ends the pass. Subsequent tool calls in the same pass are refused with a feedback message to the LoRA: *"You already proposed a concrete action this pass. Emit DONE or NO_RECOVERY_FOUND."*

This is clean but brittle: if the LoRA makes a bad first proposal, there's no way to refine it in the same pass.

### Option 2: Supersession — later proposals expire earlier ones in the same pass

Track which cards were created within the current Jarvis loop iteration. When a new Lane 2 proposal is accepted and creates a new card, automatically expire any previously-created cards from the same loop with reason *"superseded by later proposal in same recovery pass"*.

This is more forgiving than Option 1 and matches how the LoRA actually thinks (*"no, not that, this"*). But it requires Jarvis-loop-level state tracking.

### Option 3: Mark all recovery-pass cards with a `recovery_pass_id` and expire all-but-most-recent on pass completion

Add a `recovery_pass_id` field to `PendingCard`. Every card created inside a single `_run_jarvis_loop(recovery_seed=...)` invocation gets the same `recovery_pass_id`. At the end of the pass, walk the store for cards with this pass ID, keep the most recent, expire the rest.

This is the least invasive option — no changes to handle_action, just a metadata tag and a cleanup step. It's what I'd pick if implementing.

## Where this fits in the sequence

- **Not Track A.** Fix 6 v3's mitigation is good enough for Track A floor — orphans are cleaned up at cap hit, which is when they're most visible.
- **Track A-plus candidate.** Should land before the self-mod dialog work (Partial #2 EXPANDED) because the self-mod dialog is going to exercise the same Jarvis-loop → card-creation path and needs single-card-per-pass discipline.
- **Definitely by Track B.** Multi-tenant rollout cannot tolerate orphan cards accumulating in tenant stores.

## Related

- `feedback_never_delete_maez_memory.md` — deletion is not allowed to solve retrieval pollution. This follow-up's solutions all use **expiration** (legitimate state transition) rather than deletion. Stays consistent with the rule.
- `memory_integrity_tagging.md` — the broader retrieval-quality follow-up. Integrity tagging could flag orphan cards with `integrity: orphan` rather than expiring them, but expiration is cleaner for cards because they have a lifecycle.

*Created 2026-04-15 during Fix 6 v3 work.*
