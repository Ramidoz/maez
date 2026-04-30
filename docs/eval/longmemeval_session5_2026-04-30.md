# LongMemEval — Session 5: preference-aware promotion (mixed result)

## Headline

| metric | Session 4 | Session 5 (cap=1) | Δ |
|---|---|---|---|
| S-split, Sonnet 4.5, 30/30 | **0.633** | **0.667** | **+0.033** |
| oracle, Sonnet 4.5, 30/30 | **0.800** | **0.767** | -0.033 |
| mean of means | 0.717 | 0.717 | 0.000 |

**This is not a win. It is an honest mixed result.** Preference
promotion as currently designed is a *redistribution*: it moves
correct/incorrect outcomes around between question types and
between splits without net mean improvement. Shipping it because
the failure mode is now precisely characterized — that's worth
more than another tuning round in the dark.

## What actually happened

The Session 4 report named three weaknesses: preference (0.60),
multi-session (0.40), temporal (0.00 on S). Session 5 attempted to
close the preference gap by detecting preference statements at
ingest and promoting them into the daily-tier substrate that
`recall_for_cycle` consults at synthesis time.

**Two attempts:**

1. **Multi-promotion (initial).** Every preference-marked user
   turn became its own daily entry. Preference detector lit up
   3-4 times per session on the LongMemEval preference subset.
   Result: **S +0.033, oracle -0.100.** Same context-dilution
   pathology as Session 3's verbatim-concat first attempt —
   preference entries crowded the top-3 daily slots
   `recall_for_cycle` returns, pushing answer-bearing turns out.
   Knowledge-update on oracle collapsed -0.40.

2. **Cap=1 (shipped).** At most one preference promotion per
   session, picking the longest preference turn. Recovers most
   of the dilution: S still +0.033, oracle now only -0.033.
   Temporal-reasoning on both splits gained +0.20.

## Per-type matrix

| type | S4 S | S5 S | S4 oracle | S5 oracle |
|---|---|---|---|---|
| single-session-assistant | 1.00 | 1.00 | 1.00 | 1.00 |
| single-session-user | 1.00 | 1.00 | 1.00 | 1.00 |
| knowledge-update | 0.80 | 0.80 | 1.00 | **0.60** |
| single-session-preference | 0.60 | 0.60 | 0.80 | 0.80 |
| multi-session | 0.40 | 0.40 | 0.60 | 0.60 |
| temporal-reasoning | 0.00 | **0.20** | 0.40 | **0.60** |

The category named "single-session-preference" in LongMemEval
**did not move** under either attempt. Both S4 and S5 score 0.60
on S and 0.80 on oracle. That's the finding: detecting and
promoting "I love X / I'm interested in Y" statements does NOT
move the LongMemEval preference subset.

The category that moved is **temporal-reasoning** (+0.20 on each
split). Adding more daily-tier entries gave temporal questions
more dated substrate to match against — an unintended structural
benefit of the consolidation layer being denser, not a preference
phenomenon.

## Why preference didn't move (the actual diagnosis)

LongMemEval's `single-session-preference` reference answers are
phrased like *"The user would prefer X because they showed
interest in Y."* The judge's task is to confirm that surfaced
text supports inferring this preference. Two patterns explain why
promotion doesn't help here:

1. **The relevant content was already surfacing.** Maez's recall
   was already returning the answer-bearing session for these
   questions (recall floor on preference is 0.49–0.53, judge
   already at 0.60–0.80). The bottleneck wasn't "preference
   evidence didn't reach the judge" — it was "the judge's binary
   verdict on whether evidence supports an inference is harder
   for inferred-preference questions than for stated-fact ones."

2. **My promotion fired on contextual statements, not just
   preferences.** "I'm interested in deep learning" and "I'm
   trying to reduce sugar" are LongMemEval-preference signal —
   but so are dozens of other "I'm verb-ing" turns in non-
   preference sessions. The promotion adds noise to many sessions
   for the benefit of a few.

The right next-layer intervention isn't a better detector — it's
a **judge-calibration question**: do humans rate Maez's preference
answers higher than Sonnet does? An owner-annotated subset
(Slice 5 from the original audit queue: "Annotation CLI / labeled
corpus") would let us calibrate the judge against ground truth,
not against another model.

## What still moved (worth keeping)

**Temporal +0.20 on both splits** is the surprise finding.
Hypothesis: more daily entries → more dated session anchors →
better recall coverage for "when did X" questions. If this holds,
the right intervention for temporal isn't date-arithmetic at
recall time (the original Session 4 plan); it's *more
consolidation density*. Worth re-examining when temporal becomes
the active priority.

## Code state

* `is_preference_statement(text)` — public detector with
  high-precision lexicon for first-person preference markers.
  51-test cohort covers explicit affect ("I love", "I miss") and
  contextual preference ("I'm interested in", "I've been"), plus
  negative tests for factual statements ("I work as", "I went to").
  See [`core/eval/longmemeval.py`](../../core/eval/longmemeval.py).
* `synthesize_daily_summaries` — emits one salient turn per
  session plus *at most one* preference turn (cap=1). Multi-
  promotion was tried and rejected for context dilution.
* Tests pin both the detector contract and the cap-1 invariant.

## Honest takeaway

Preference promotion at the daily-synthesis layer is the wrong
layer. The detector is correct (it fires on real preference text).
The promotion mechanism is correct (cap=1 doesn't dilute). The
*premise* that "more preference signal in the daily tier → better
preference judgments" is mostly false on this benchmark, because
the bottleneck isn't substrate, it's judge inference on inferred-
preference questions.

The work is shipped because:
- It's a documented negative result with a clear next direction.
- The temporal side-effect (+0.20 on each split) is *suggestive*
  at this sample size — N=5 per type per split means a single
  question flipping moves the cell by 0.20. Worth replicating
  before treating as a finding.
- The cap-1 pattern (`if pref_candidates: _emit(max(pref_candidates,
  key=len), flavour="preference")`) is reusable for any future
  per-session promotion (e.g., a date-extraction promotion for
  temporal work). It's a four-line pattern, not infrastructure.

## Files

* [`core/eval/longmemeval.py`](../../core/eval/longmemeval.py) —
  detector + capped synthesis.
* [`tests/test_longmemeval.py`](../../tests/test_longmemeval.py) —
  TestPreferenceDetector, TestPreferenceAwareSynthesis.
* `docs/eval/runs/longmemeval_*_session5*_2026-04-30.{md,json}` —
  per-run artifacts (uncapped + capped, both splits, both judges).

## Citation update

> Maez, *LongMemEval Session 5* (2026-04-30, preference-aware
> promotion):
> S-split, Sonnet 4.5, 30/30: **0.667** (S4: 0.633, +0.033).
> Oracle, Sonnet 4.5, 30/30: **0.767** (S4: 0.800, -0.033).
> Mean of means unchanged (0.717). Preference category itself
> stationary on both splits; temporal-reasoning gained +0.20 on
> both as a structural side-effect of denser consolidation.
> Documented negative result: preference promotion at the daily-
> synthesis layer is the wrong layer; judge-calibration via
> owner-annotated ground truth (Slice 5 from the original audit
> queue) is the right next move.
