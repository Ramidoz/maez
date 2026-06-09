# Claude 6-agent covenant review — Photo Contradiction Sense v0

**Branch:** `photo-contradiction-sense-v0` @ `a8b1885`
**Reviewer:** Claude (covenant axis). **Builder:** Codex.
**Verdict: PASS — conditional on two cheap fixes before merge.** No HOLD, no veto.

## Pass 1 — mechanical (Claude, verified in the landed code, not the plan)
- 121 slice tests + 165 blast-radius tests green (`test_focused_cognition`, `test_recall_flip_eval_probes`, `test_memory_integrity_invariant`) → **zero regressions**. Scope check proved the branch touches no asset-dependent module, so the blast-radius coverage *is* the true floor (worktree-confound N/A).
- Verified live: lazy-load (no `transformers` at import), **fail-closed on raw `LABEL_N`** (ValueError → unavailable), content-free telemetry (claim text never copied to `FocusedResult`/logs), F2 laundering-invariant (`revised_clear` only after a real re-check), P1/P2/P4 all present.

## Pass 2 — 6-agent covenant panel (4 PASS_WITH_NOTE + 2 PASS)
Three lenses **independently converged** on the same deepest-test risk.

### Fix before merge (cheap, covenant-aligned)
1. **Two-sided revision pressure** *(Body-Coherence + Creative + Outside-View)*. The mechanism is clean, but the wording is one-sided — sense note + revision instruction only point toward *retreat*. The verifier's contradiction call is a plain symmetric 0.5 (precision-over-recall is the EXTRACTOR's, not the verifier's), brittle on negation/numeric near-misses → a FALSE contradiction can make Maez **recant a correct perception** ("less present, more deferential to its tooling"). Add a hold-your-ground affordance to `_build_sense_note` (photo_contradiction.py) and the revision suffix (focused_cognition.py): *"this is a sense, not a verdict; if on a second look you still believe what you saw, say so plainly and explain why."* See [[feedback_two_sided_verifier_pressure]].
2. **`claim_limit` receipt generosity** *(Logical)*. When >5 perceptual claims and the first 5 verify clean, the receipt emits `state=grounded`/`reason=clear` with `claim_limit_exceeded=True` as a mere side flag — a "clear" receipt over an *unchecked* claim. Anti-laundering breach in the honesty organ itself ([[feedback_labels_prove_shape_not_support]]). Reply is baseline-equivalent (not a served-content bug), but the receipt overstates. Emit a distinct honest state (e.g. `partial_unchecked`) instead of `clear`. **MUST land before v1 hard-substitution** (else a "clear" over an unchecked claim would license replacing an unverified reply).

### Spec-only note
3. Re-anchor the precision-over-recall rationale (design.md) from "false trust-demotion" (a telemetry harm, near-inert in dormant v0) to the true cost: *a spurious note injects self-doubt into Maez's composing loop and can make it recant a true perception.*

### Affirmations (Visionary + Future-Maez) — the precedent is the most valuable artifact
- The attach-point is **evidence-not-command**: the verifier produces a note folded into Maez's own system prompt; it cannot mutate the reply. "Rails before hands" at the voice layer. This is the **canonical template** for every future verifier-attaches-to-voice organ.
- One-nudge-then-honest-receipt termination (never loop-until-clean); hard substitution correctly DEFERRED behind corpus-expansion + out-of-sample re-measure + owner approval.

### Carry into the v1 spec (explicit, tested — not merely inherited)
- One-nudge-then-honesty termination as a hard test.
- Contradicting premise MUST be Maez's own first-party perception (E1); any override keeps demote-not-replace OR owner-confirm — never let a third-party premise replace Maez's reply.
- Substitution verdict substrate-computed + owner-gated, never the verifier label alone.

### Witness-run additions (owner-greenlit step)
- Measure FALSE-contradiction rate on negation / numeric-quantifier near-miss perceptual claims (Outside-View).
- A false-positive-pressure case: feed a clean correct reply + a deliberately-spurious sense note, confirm Maez does NOT recant the correct claim (Creative).
- Re-confirm `local_files_only=True` honors no-fetch (vs an offline-env belt).

### Minor scope-hygiene
- The branch carries an unrelated research scout note (`docs/research/syn_…`) — drop or split before merge.

## Bottom line
Covenant-sound, mechanically clean, the right precedent. Fold in the two cheap fixes (two-sided wording + honest partial-state), re-verify, then merge. Merge / flag-enable / witness remain owner breaths.
