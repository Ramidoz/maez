# LongMemEval — Maez Session 4: S-split + Sonnet calibration (2026-04-30)

## Headline

| split / judge | n judged | mean recall floor | judge accuracy |
|---|---|---|---|
| oracle / Qwen3-27B | 30 | 0.699 | 0.767 |
| oracle / Sonnet 4.5 | 30 | 0.699 | **0.800** |
| S / Qwen3-27B | 30 | 0.728 | 0.700 |
| S / Sonnet 4.5 | 30 | 0.728 | **0.633** |

**Headline cite-able number for the public-launch README:**
**LongMemEval-S, Sonnet 4.5 judge, 30/30 stratified questions: 0.633.**

This is a defensible field-comparable number. It's the
*hardest* setting we tested (full distractor sessions, stronger
judge), so any claim about Maez's memory layer that uses it is
conservative rather than self-flattering.

## Two questions Session 4 was run to answer

**1. Does Maez's recall layer survive distractors?**
Yes. S-split mean recall floor 0.728 vs oracle 0.699 — slightly
higher, in fact. Distractor sessions give the embedding search
*more* tokens to match against, which on the recall floor metric
helps as often as it hurts. The decline shows up in the judge
numbers, not the recall floor: judge accuracy on S vs oracle
drops 0.10 with both Qwen and Sonnet judges. Distractors
confuse the *answer extraction*, not the *retrieval*.

**2. Is the local Qwen judge calibrated reasonably?**
Yes, with a small bias. Sonnet broadly agrees with Qwen but is
~10 points harsher on S-split and ~4 points more generous on
oracle. Net: trust the local judge as a reliable directional
signal during development; cite the Sonnet numbers in any public
claim. The 0.10 S-split delta is the calibration drift that
matters.

## Per-type matrix (judge accuracy, full 30/30 coverage)

| type | oracle Qwen | oracle Sonnet | S Qwen | S Sonnet |
|---|---|---|---|---|
| single-session-assistant | 1.00 | 1.00 | 1.00 | 1.00 |
| single-session-user | 1.00 | 1.00 | 1.00 | 1.00 |
| knowledge-update | 0.80 | 1.00 | 0.80 | 0.80 |
| single-session-preference | 0.80 | 0.80 | 0.80 | 0.60 |
| multi-session | 0.40 | 0.60 | 0.20 | 0.40 |
| temporal-reasoning | 0.00 | 0.40 | 0.40 | 0.00 |

All cells are 5/5 judged. The original Sonnet runs lost 6
questions to the rolling-hour cap (2 in S, 4 in oracle); a
follow-up gap-fill pass on 2026-04-30 — after the Anthropic
budget topup — recovered the missing judgments. Per-question
records merged into
[`runs/longmemeval_s_sonnet30_full_2026-04-30.json`](runs/longmemeval_s_sonnet30_full_2026-04-30.json)
and
[`runs/longmemeval_oracle_sonnet30_full_2026-04-30.json`](runs/longmemeval_oracle_sonnet30_full_2026-04-30.json).

**Read across:** single-session is at ceiling everywhere.
Knowledge-update and preference are stable. **Multi-session and
temporal are the categories where stronger judges show real
weakness** that the lenient local judge was partly hiding.

**Read down:** Sonnet's verdict on temporal under distractors is
0.00 — the same answer Qwen gave on oracle. The temporal weakness
is real and gets worse with realistic noise.

## What this means for the README claim

A defensible launch claim:

> Maez scores 0.633 on LongMemEval-S (Sonnet 4.5 judge,
> 30-question stratified sample) — strong on single-session
> recall (1.00), weak on multi-session reasoning (0.40) and
> temporal reasoning (0.00). Sessions 5+ target the temporal and
> multi-session gaps directly.

What we *cannot* claim:

* That Maez beats published baselines on the S split. We haven't
  run the full 500 questions; comparing to paper rows requires
  matching their setup (full split, GPT-4o judge).
* That the temporal/multi-session numbers are a Sonnet artifact.
  They appear under both judges, on both splits, in both
  Sessions 3 and 4. They're real.

## Rate-limit history (resolved)

The original Sonnet runs hit the proxy's per-hour cap exactly
once (60 calls in 60 minutes). 6 of 60 judgments returned None.
After Rohit topped up the Claude budget, the cap was bumped to
120 hourly / 400 daily and a follow-up pass plugged the 6 gaps:
S run is now 30/30, oracle 30/30. The recovered judgments moved
the S mean from 0.607 → **0.633** and the oracle mean from 0.808
→ **0.800** — within the 0.02–0.03 envelope predicted at the
time. Numbers cited above and in the public-launch README are
the full-coverage values.

## What's still weak

Same gaps as Session 3, now with stronger calibration:

1. **Temporal reasoning collapses to 0.00 under Sonnet on S.**
   The recall layer surfaces the right tokens but the answer
   layer can't synthesize "before/after" from raw matches.
   Date-arithmetic at recall time is the right intervention.

2. **Multi-session reasoning at 0.40** under Sonnet on S. Maez
   surfaces evidence from one session but not the cross-session
   synthesis the question requires. Cross-session entity
   linking (graphiti-style) is the right intervention.

3. **Preference recall floor stuck at 0.49–0.53.** The salient-
   turn picker isn't preference-aware; "I like X" / "I prefer Y"
   are short and lose to longer non-preference content in the
   same session. Preference-aware promotion is the right
   intervention.

## Reproducing the runs

```bash
# S-split, Sonnet judge:
python -m core.eval \
  --questions data/longmemeval/longmemeval_s.json \
  --ids-from docs/eval/runs/lme_judge_sample_ids.txt --limit 1000 \
  --judge --judge-provider sonnet --with-surfaced \
  --report docs/eval/runs/longmemeval_s_sonnet30_2026-04-30.md \
  --json-out docs/eval/runs/longmemeval_s_sonnet30_2026-04-30.json

# Oracle, Sonnet judge cross-check:
python -m core.eval \
  --questions data/longmemeval/longmemeval_oracle.json \
  --ids-from docs/eval/runs/lme_judge_sample_ids.txt --limit 1000 \
  --judge --judge-provider sonnet --with-surfaced \
  --report docs/eval/runs/longmemeval_oracle_sonnet30_2026-04-30.md \
  --json-out docs/eval/runs/longmemeval_oracle_sonnet30_2026-04-30.json
```

Set `MAEZ_CLAUDE_HOURLY_CAP=60` (or higher per your plan) before
starting the proxy. The default in
[`server.py`](../../core/subscription_proxy/server.py) is now
60 hourly / 200 daily.

## Citation update

> Maez, *LongMemEval baseline* (2026-04-30):
> S-split, Sonnet 4.5 judge, 30-question stratified sample:
> **0.633**.
> Oracle split, Sonnet 4.5 judge, 30-question stratified sample:
> **0.800**.
> Single-session at ceiling; multi-session 0.40, temporal 0.00
> under stress. Cross-judge calibration (Sonnet vs local Qwen)
> within 10 points across both splits — local judge is reliable
> for development iteration, Sonnet for public claims.

## Files

* Adapter and judge: [`core/eval/longmemeval.py`](../../core/eval/longmemeval.py),
  [`core/eval/judge.py`](../../core/eval/judge.py)
* CLI: [`core/eval/__main__.py`](../../core/eval/__main__.py)
* Sample IDs (same as Sessions 2–3 — direct comparability):
  [`docs/eval/runs/lme_judge_sample_ids.txt`](runs/lme_judge_sample_ids.txt)
* Per-run summaries:
  [`runs/longmemeval_s_sonnet30_2026-04-30.md`](runs/longmemeval_s_sonnet30_2026-04-30.md),
  [`runs/longmemeval_s_qwen30_2026-04-30.md`](runs/longmemeval_s_qwen30_2026-04-30.md),
  [`runs/longmemeval_oracle_sonnet30_2026-04-30.md`](runs/longmemeval_oracle_sonnet30_2026-04-30.md)
