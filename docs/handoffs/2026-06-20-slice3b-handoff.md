# Handoff — Earned-Maturity Routing Slice 3b (Beta-Binomial belief, shadow-compared) — REVIEW GATE

**Date:** 2026-06-21. **Branch:** `earned-maturity-slice3b` (last code commit `eed0ba7`; this handoff on top; local-only, NOT pushed/merged).
**Status:** built (Task 0 + 2 code commits) + Claude two-stage reviewed (Task 0 light; Task 1 math controller-verified; Task 2 FULL spec+quality APPROVED). **STOPPED at the review gate** — awaiting Codex cross-lane, then owner breath. NOT live (both Beta flags default-off).
**Spec:** `docs/superpowers/specs/2026-06-20-earned-maturity-routing-design.md`. **Plan:** `docs/superpowers/plans/2026-06-20-earned-maturity-routing-slice3b.md`.

## What this slice does (one line)

Replaces the crude `n/8` confidence curve with a **Beta-Binomial belief** whose confidence *emerges* from evidence consistency — but **only in shadow**: logs `n/8` and Beta side by side and changes NO behavior. Graduation (flipping the veto to Beta) is an owner flag-flip AFTER the receipts prove Beta is better-calibrated.

## Commits

- `93078b6` docs(proof): Task 0 GO — consult-guard + scipy verdict anchors confirmed.
- `e4767df` **Task 1** — `beta_belief` (scipy.stats.beta.cdf) + `compare_beliefs` + `BeliefComparison` (pure; n/8 path UNCHANGED). 6/6 incl. the keystone.
- `eed0ba7` **Task 2 (behavior)** — consult-guard widened to the 4-flag `_routing_prior_consult_enabled()` (false-witness fix), shadow-log `routing_belief_compare`, default-off Beta veto-swap.

## THE CALIBRATION TABLE — the "provably saner" artifact (gate witness)

```
case          n  u  rate | n8_conf n8_veto | beta_p beta_veto | note
thin-2        2  0  0.00 |   0.000   False |  0.784     False | both abstain
3-streak      3  0  0.00 |   0.375   False |  0.870     False | both abstain
4-streak      4  0  0.00 |   0.500   False |  0.922      True | DIVERGE: beta eager (TUNING WARNING)
5-streak      5  0  0.00 |   0.625    True |  0.953      True | both veto (gate 4)
mixed-3of5    5  2  0.40 |   0.625    True |  0.456     False | KEYSTONE (gate 5): n8 overclaims, beta abstains
useful-5      5  5  1.00 |   0.625   False |  0.004     False | neither
```
- **Gate 5 (keystone) holds:** on MIXED evidence (3-bad-2-good) `n/8` vetoes (conf 0.625, rate 0.40) while Beta correctly stays uncertain (`beta_p 0.456 < 0.9`) — Beta is *less* confident than `n/8`, earning its keep. This is the graduation evidence, NOT "it also vetoes Barchart."
- **4-streak is a TUNING WARNING, not a win:** `Beta(1,1)+0.9` vetoes at 4 straight failures while `n/8` doesn't — eager for "one streak shouldn't over-confide." Surface it; consider a more skeptical prior (`Beta(1,2)`) or higher credence WITH the owner before any `BETA_ENABLED` flip.

## Hardcoded scaffolding — named honestly (3b fixes the *reading*, 3c earns the *caution*)

3b still hardcodes the caution settings: `prior_alpha=1, prior_beta=1`, `credence=0.9`, `max_success=0.4`, `min_observations=3` (+ `n/8`'s `0.6/0.4` for the comparison). This is acceptable ONLY because 3b is shadow and **3c makes them earned** (the prior moves with the global age + per-class re-ask outcomes from the 3a ledger). 3b is a better *belief* with still-ours *parameters* — NOT "Maez has learned caution."

## Codex cross-lane review anchors

1. **All four flags off = byte-identical** — consult never runs, no scipy import (verified `scipy not in sys.modules`), `_belief_cmp` None, `_veto_decision == _prior_vetoes_reflex(_prior)`. No reply-text change either state.
2. **False-witness fix** — the consult guard is `_routing_prior_consult_enabled()` (4-flag OR), so `MAEZ_ROUTING_BETA_SHADOW=1` ALONE reaches the consult (no "flag on, shadow asleep"). `_default_store` import retained (no NameError). `routing_prior_shadow` stays on its 2 priors-flags; the Beta block + scipy on the 2 Beta flags.
3. **Authority** — the veto application still LEADS with `MAEZ_ROUTING_PRIORS_ENABLED == "1" and _veto_decision`; Beta only ASSIGNS `_veto_decision`. `BETA_ENABLED=1` alone computes the comparison but cannot veto. (`test_beta_swap_inside_priors_enabled_authority` asserts the source-order.)
4. **n/8 + 3a untouched** — `learn_priors`/`_confidence`/`_prior_vetoes_reflex` byte-unchanged; the 3a veto-ledger record/override block unchanged. Beta is parallel + shadow.
5. **Graduation is an owner flag-flip, not a code change** — `MAEZ_ROUTING_BETA_ENABLED` shipped default-off; flip only AFTER reviewing the receipts (calibration table + live shadow agreement on the consistent Barchart class).

## Nice-to-have (for the graduation slice, NOT this one — Task-2 reviewer)

When Beta moves toward live, cache `_store = _default_store()` once in the consult and pass to both `learn_priors` + `compare_beliefs` (currently a double store-construction on the Beta-flag-on path; idempotent sqlite, fine for shadow, tip to Important when on the live path).

## Verification

`test_beta_belief` (6) + `test_beta_shadow_seam` (6) GREEN; regression `test_routing_priors`/`_veto_seam`/`test_veto_ledger`/`_seams` GREEN; ruff clean. Scope: 3 files (priors.py + daemon + 1 new test) + Task-0 proof.

## Owner-breath (after both-lanes PASS + merge — owner-sovereign)

Code only; restart `maez`. Set `MAEZ_ROUTING_BETA_SHADOW=1` in `/home/rohit/.config/maez/model.env` (PRIORS_ENABLED already live). Then:
1. Live some "today's signals" turns; `grep routing_belief_compare` in the logs — confirm Beta reproduces the Barchart veto LIVE (agreement on the consistent class: `n8_veto=True beta_veto=True`).
2. Review the calibration table above for the mixed-evidence sanity (gate 5) + the 4-streak tuning warning.
3. ONLY THEN, if the receipts satisfy you (and after deciding the prior/credence tuning), consider `MAEZ_ROUTING_BETA_ENABLED=1`. No autonomous check.
