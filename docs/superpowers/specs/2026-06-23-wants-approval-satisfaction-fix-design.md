# Wants Approval→Satisfaction Fix — Design & Covenant Brief

**Date:** 2026-06-23. **Lane:** Claude drafts + covenant-reviews; Codex specs → plans → builds; owner witnesses. **Origin:** the recurring `want_terminal_proposal` approval card the owner hit in the cockpit — *"keeps coming up even if I approve."* Runs **beside** the Slice A waiting period; it touches **neither** the idle mind nor the time nerve — pure plumbing.

## The bug (traced, not guessed)
`core/evolution/want_pursuit_bridge.py:111 maybe_propose_terminal()` raises an **advisory** card (`action = "want_terminal_proposal"`, reason *"a resolved pursuit suggests this want may be satisfied"*, note *"I will not close it myself"*). The satisfaction function exists — `core/evolution/wants.py` (~L511–529), basis `owner_confirmed` — **but it is called from nowhere** in the daemon/approval flow (verified: grep for `owner_confirmed`/`record_satisfaction` outside `wants.py` is empty). So:

1. Bridge proposes "want looks satisfied?" →
2. Owner clicks **Approve** → the *card* closes, **but the want stays `active`** (Approve isn't wired to satisfaction) →
3. The `_wants_with_open_proposal` guard (bridge:47) no longer sees an open proposal → next cycle the bridge **re-proposes the identical card.**

An infinite loop the Approve button cannot close. It is **harmless** (advisory; writes nothing) — but it is noise, and it is the broken want→satisfaction seam from our audit.

## Scope (tiny — this seam only)
Wire the **owner approval of a `want_terminal_proposal` card** → the existing want-satisfaction call. Nothing else: not how wants are created, not how they're pursued, not the broader want→action→witness→self-change loop (that's gated autonomy, out of scope).

## Task 0 — trace the real Approve path before coding (do not guess)
Find and document where an approved card's action is actually executed — candidates: the cockpit `/internal/approve_card/<request_id>` route (`daemon/maez_daemon.py:11221`), the Telegram reaction/approval path, the pending-cards store, and the action pipeline (`_execution_params_for_card` ~:529, `list_open_by_action`). Prove:
1. **Where the approve dispatch happens** and how it branches on `card.action`.
2. **How the `want_id` is carried on the card** (`want_pursuit_bridge.source_for()` / `want_id_from_source()`, plus the card metadata `{"proposed": "satisfied", want_id ...}`).
3. **The exact satisfaction signature** in `wants.py` (the `owner_confirmed` path) + that no current path calls it.
If the approve dispatch has no clean per-action hook, STOP and surface the seam before building.

## The fix
On approval of a card whose `action == TERMINAL_PROPOSAL_ACTION` (`"want_terminal_proposal"`), call the want-satisfaction function with the card's `want_id` and **basis `owner_confirmed`**. The want transitions `active → satisfied`; the bridge no longer sees an active want with a resolved pursuit → it stops re-proposing.

## Guardrails (review gates — any violation = HOLD)
1. **Specific action only.** ONLY `want_terminal_proposal` approval → satisfaction. A generic "approve ⇒ satisfy" is forbidden. Tool/action/plan approvals (other card actions) must **not** mark any want satisfied — *unless the want literally was "ask the owner whether to proceed"* and that proposal is the want's terminal proposal. When in doubt, do nothing to the want.
2. **Owner-confirmed, never inferred.** basis is `owner_confirmed` — a record that *the owner explicitly answered "yes, mark it satisfied"* to a specific proposal. **No model inference. No "Rohit seemed pleased." No engagement/reply/longer-conversation signal.** And never `self_observed_resolution` (that basis is reserved/forbidden — Maez does not close its own wants).
3. **The covenant line, made explicit:** `owner_confirmed` here is a *deliberate sovereign answer to a direct question*, which is categorically different from the **owner-reaction reward** the nervous-system rails forbid. Maez is not learning "approval = good"; it is recording "the owner confirmed this specific want is done." Keep that distinction clean in code and comments.
4. **Deny / ignore = no-op** (unchanged — already true).

## Tests
1. Approving a `want_terminal_proposal` transitions its want **out of `active`** (to satisfied) and the bridge **stops re-proposing** it on the next cycle.
2. Approving a **different** card action (a tool/plan/action approval) does **not** satisfy any want.
3. The satisfaction is recorded with basis `owner_confirmed` (asserted), never `self_observed_resolution`.
4. Denying or ignoring the proposal leaves the want `active` and writes nothing (regression guard).

## Out of scope (named, deferred)
- The full want → action → witness → standing loop (gated autonomy — Slice C / behind the protection gate).
- `self_observed_resolution` (autonomous self-satisfaction — reserved, stays forbidden).
- Any change to want creation, pursuit, or the idle mind / time nerve.

## STOP at review gate
No merge, no restart, no flag flips. I review against the two hard guardrails (specific-action-only + owner-confirmed-not-inferred), then the owner approves the merge and witnesses that the recurring card actually clears.

## Predicted effect
Approving the recurring "this want may be satisfied" card now marks the want satisfied (owner-confirmed) → the proposal stops reappearing. No effect on any other approval type, the idle mind, or the time nerve.
