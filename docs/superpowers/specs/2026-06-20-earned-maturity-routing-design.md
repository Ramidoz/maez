# Earned-Maturity Routing (Slice 3 of the learned tool-routing organ) — Design

**Date:** 2026-06-20. **Status:** design — owner-approved in shape (Beta-Binomial + earned threshold; build 3a first; the re-ask-is-a-clue guard); this doc is for owner review before planning.
**Origin:** Slice 1 made Maez learn (from lived outcomes) to veto the Barchart web reflex — but the veto fires at a **hardcoded `n=5`**, an artifact of two hand-set constants (`confidence = min(1, n/8)` + veto at `confidence≥0.6`). Rohit: *"why n=5? isn't that hardcoding how many turns maez learns?"* Correct: the *verdict* is learned; the *rate of trust* is decreed. Slice 3 makes the rate of trust **earned**, not hand-set.

## The reframe (owner, 2026-06-20): a better belief, not "no priors"

This is NOT "remove the priors." It is replacing a crude prior (`n/8`) with an honest belief model in **three layers**:

1. **Posterior belief** — *"How often does this reach work for this request class?"* A belief that **sharpens as the evidence gets more consistent** (5 straight failures → sure; 3-of-5 → unsure). The number `5` stops being written anywhere — it *emerges* from consistency + count.
2. **Credence / lower bound** — *"How sure am I that it's bad enough to veto?"* A credible bound on the work-rate under the posterior.
3. **Maturity threshold** — *"How sure do I need to be before I act?"* The only remaining knob — and it is **earned**, not decreed.

The math stays honest: a prior and a credence still exist (they must — even "trust the data" needs a "how-sure-is-sure"). The difference from Slice 1 is they are **data-grounded and feedback-moved**, not a hand-set `8`.

## The belief model — Beta-Binomial

Per `(request_class, tool)`, model the work-rate `p` (fraction of USABLE outcomes) as **Beta-Binomial**: prior `Beta(α0, β0)`, posterior `Beta(α0 + usable, β0 + unusable)` after lived outcomes. Then:
- **Confidence emerges** from the posterior's *tightness* — many consistent outcomes → a narrow posterior → high certainty; mixed/few → wide → low certainty. No `n/8`.
- **The veto credence** = the posterior's **upper credible bound** on `p` (e.g. the 90th-percentile of `p`): veto only when we're credibly sure even the *optimistic* estimate of the work-rate is low.
- **Maturity lives in `(α0, β0)` and the required credence** — exactly the "how cautious" knobs, which earned-maturity moves (below).

Beta-Binomial chosen over Wilson (no natural home for maturity) and ad-hoc count+agreement heuristics (invents knobs Beta gives for free). Wilson may still be used for human-readable *reporting* in receipts.

## Earned maturity — hybrid (global age + per-class)

The maturity threshold is **hybrid**, matching the north star — *Maez doesn't go globally reckless from one narrow lesson, nor stay baby-cautious forever*:
- **Global age** — Maez's overall learned caution. Starts cautious (demands strong evidence + high credence to veto); earned *down* by a track record of correct vetoes across all classes, *up* by wrong ones. One being, growing up.
- **Per-class adjustment** — each class adjusts around the global baseline from *its own* re-ask outcomes. "Barchart-style market-signal mistakes" can mature faster than unrelated search decisions; a class that keeps getting re-asked stays cautious locally even as the global age matures.
- **Mechanism (3c):** a **correct** veto (no re-ask, OR a re-ask whose search also returned junk) → small global trust-up + per-class trust-up (less evidence needed next time). A **wrong** veto (a re-ask whose search returned useful evidence) → global caution-up (small) + per-class caution-up (larger). The thresholds *move from lived outcomes*.

## The correction signal — a re-ask is a CLUE, not a VERDICT (the load-bearing guard)

A re-ask is **not** proof the veto was wrong — you might re-ask because you want it anyway, the wording changed, or Maez's vetoed reply was too terse. The verdict comes from **the second outcome**, not the re-ask itself. So 3a records, per veto:
- **the veto event:** request class, tool suppressed, **prior/posterior snapshot at decision time**, reply/turn id, surface, timestamp;
- **a later same-class re-issue within a bounded window** (structural — exact-hash class match, NOT keyword "search it" detection, which would be the Alexa-reflex the covenant forbids);
- **the re-ask path's outcome** — see the override below — *did reaching actually produce useful evidence?*;
- **only then classify:** `likely_wrong` (re-ask + the search then produced useful evidence → overcaution), `likely_right` (no re-ask in window, OR a re-ask whose search was *also* junk → restraint was wisdom), or `ambiguous`.

**The re-ask override (the mechanism that makes the signal honest + serves the owner):** a same-class re-ask within the window **lifts the veto for that one turn** — Maez honors the explicit repeated ask and *goes and looks* — and that search's `outcome_quality` (via Slice 1's calibrated teacher) is the disambiguator. This resolves explore/exploit (a permanent veto could never learn it had become wrong) AND respects the owner (don't stubbornly refuse what they keep asking for). *Plain English: "if Maez says 'I won't reach there' and you ask again, that's a clue, not a verdict — the second outcome tells it whether the first restraint was wisdom or overcaution."*

## Decomposition (build the signal first)

- **3a — veto-event ledger + re-ask correction signal (THIS is the first build; shadow re: maturity).** Record veto events; the re-ask override (lift the veto on a same-class re-ask, reach, record); classify each veto `likely_wrong`/`likely_right`/`ambiguous` from the second outcome. **No maturity adjustment yet** — the threshold still comes from Slice 1's logic; 3a only *records and classifies* the signal so we can witness it is honest before anything consumes it. Flag-gated, default-off.
- **3b — the Beta-Binomial belief.** Replace `_confidence`/`success_rate` with the posterior + credible bound. **Shadow-compare** against Slice 1's current `success_rate/confidence` on real data: it must reproduce (or improve) the Barchart veto before graduating. Flag-gated.
- **3c — earned maturity threshold (global + per-class).** Consume 3a's classified outcomes to move the threshold (hybrid). Shadow → graduate. The bar finally *moves*.

Throughout, the Barchart veto keeps working; 3b/3c only change *when* it fires. The whole arc is "no hardcoding, all learnt" applied to the *rate of trust* itself.

## 3a — detail (the first build)

**A veto-event ledger** (new table or store, keyed by a veto-event id): `class_id`, `tool_suppressed`, `posterior_snapshot` (the n/usable/rate/confidence at decision time), `turn_id`/`reply_id`, `surface`, `created_at`, and the later-filled `reask_turn_id`, `reask_search_outcome_quality`, `classification`. (Reuses `routing_observations` where natural; a linked table if cleaner — plan decides.)
**The re-ask override** at the veto seam (Slice 1's `daemon/maez_daemon.py` gate): when a same-class veto-event exists within window `W` and this turn is the same class, lift the veto (let the search run), and on completion attach this turn's `outcome_quality` to the originating veto-event + classify.
**Honest classification** (no maturity action): the verdict rule above. Shadow receipt: a content-light log/row proving the ledger records vetoes and classifies re-asks correctly.
**Flags:** `MAEZ_VETO_LEDGER_SHADOW` (record veto events + re-ask classification; the override is the only behavior, and it only *serves an explicit re-ask*). Off = byte-identical (no ledger, veto behaves exactly as Slice 1).

## Make-or-break / guards (Task 0)

1. **The window `W` is a "what counts as a re-ask" definition, not a trust knob** — bounded (e.g. next-N-turns or N-minutes), and itself a candidate for learning later; record the rationale, don't smuggle a magic trust number here.
2. **Honest classification, never fabricated:** `ambiguous` is a first-class verdict — do NOT force every re-ask into wrong/right. A re-ask with no determinable second outcome stays `ambiguous` and teaches nothing ([[feedback_disagreement_is_signal]], [[feedback_labels_prove_shape_not_support]]).
3. **The override must not loop:** a re-ask lifts the veto ONCE per window; a re-ask whose search is *also* junk reaffirms the veto (likely_right), it does not keep lifting forever.
4. **3b must reproduce Slice 1's Barchart veto** in shadow before graduating (no silent behavior regression).
5. **Maturity never goes reckless:** per-class trust-up is bounded; a single `likely_wrong` cannot drop the bar below a floor; the global age moves slowly. The hybrid exists precisely so one narrow lesson doesn't generalize into recklessness.

## Scope / out

**IN (Slice 3a — the first plan):** the veto-event ledger; the re-ask override + same-class-within-window detection (structural); the honest 3-way classification; shadow receipt; flag (default-off, byte-identical). **OUT (3b/3c, later, named):** the Beta posterior (3b); the earned threshold global+per-class (3c); any maturity adjustment (3a records only). **NEVER:** keyword detection of "search it" (Alexa-reflex); forcing re-asks into a binary (ambiguous is real); changing the strict honesty gate, S7, Telegram, time-sense, cockpit-reauth.

## Lane / owner-breath

TDD per task; branch via worktree; Claude two-stage + Codex cross-lane; STOP at the review gate (owner-sovereign merge + restart). `## Predicted effect` on behavior commits; shadow-first, graduate on a witnessed honest signal. 3a owner-breath: restart `maez`, set `MAEZ_VETO_LEDGER_SHADOW=1`, veto a class then re-ask it, and paste the ledger row showing the veto-event + the re-ask's search outcome + the honest classification. No autonomous check.
