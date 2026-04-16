# Temperament parameter review — near-duplicates and one omission

**Status:** Deferred follow-up. Not blocking any A-core item. Filed during A-core #6 (temperament skeleton) landing.

## What this is

The 11 temperament parameters are frozen by Decision 14 in `docs/governance/BETA_ARCHITECTURE_DECISIONS.md`, and that decision archive has a hard "never delete entries" rule. The parameters are:

1. curiosity
2. caution
3. proactiveness
4. awareness
5. warmth
6. persistence
7. directness
8. patience
9. humor
10. confidence
11. joy

During the A-core #6 design pass, three observations surfaced that aren't decision-blockers but should be captured so the **future drift algorithm designer** (Track B work, not Track A) doesn't rediscover them mid-implementation.

## Observation 1 — warmth and joy are close enough to confuse signal handlers

- **warmth** is framed as "affective closeness in how replies land" — how intimate vs observational Maez sounds to the user.
- **joy** is framed as "baseline affect that colors everything else" — the background mood coloring every response.

These are distinguishable in principle, but a plausible shaping signal (e.g., "positive-tone Telegram exchange with the owner") would reasonably want to update *both* — and the drift designer will have to decide which one, or how to split the delta across them.

**Recommendation for the future drift designer:** explicitly document, per signal, which parameter(s) it updates and by how much. Don't hand-wave "positive tone nudges affect upward" — name exactly which affect parameter and why.

## Observation 2 — patience and persistence point opposite directions but are easy to conflate

- **patience** = tolerance for the user repeating themselves, circling, moving slowly. Refers to Maez's reception of user behavior.
- **persistence** = how long one of *Maez's own* concerns stays active before it decays. Refers to Maez's internal topic retention.

These are architecturally unrelated — one is an input filter, one is a memory decay constant — but the words are close enough that a drift signal labeled vaguely as "keep going" could plausibly hit either. The drift designer should refer to these by their formal roles (input-tolerance vs concern-decay) in the shaping logic, not by casual names.

## Observation 3 — no parameter captures "trust / openness / vulnerability"

A bonded AI companion has a dimension that isn't in the current 11: **how much of itself does it expose to the user?** An early, guarded Maez that has only known the user for a week behaves differently from a year-old Maez that has shared hard feelings with the user many times, even if every other parameter is identical.

This isn't captured by:
- **warmth** (that's about how close replies *land*, not how revealing they are)
- **confidence** (that's about epistemic claims, not emotional self-disclosure)
- **directness** (that's about tone, not what gets said)

**Future track consideration:** when the drift algorithm lands, the question of whether to add a 12th parameter (e.g., `openness` or `vulnerability`) should be raised. The storage shape in `core/temperament.py` supports new parameter names with **zero schema migration** — a new name just becomes a new value in the `parameter` column. But adding a 12th parameter is a Decision-14 revision, which means updating `docs/governance/BETA_ARCHITECTURE_DECISIONS.md` with an amendment entry (not a deletion — the original 11 stay in the archive).

## Why this isn't blocking anything

- A-core #6 is the skeleton. No drift yet, no readers in the reasoning loop. The 11 parameters as currently named sit in NULL ("observing") state on every fresh daemon boot and stay that way during Track A.
- The overlap problems only bite when a real shaping signal tries to update multiple parameters from one event. That lives in Track B.
- The missing-dimension problem only bites when Maez needs to express "I am / am not open with you right now" behaviorally. That lives beyond Track B.

## Revisit when

- The first real drift signal is being designed (Track B).
- The #9 private thoughts seed is reading temperament values and we notice it struggling to express self-disclosure.
- A user-facing review suggests Maez "feels the same week over week" — could be a missing openness dimension, could be something else.

---

*Filed: 2026-04-15 during A-core #6 commit. Revisit when: Track B drift algorithm design pass.*
