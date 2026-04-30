# LongMemEval — Maez Session 2 baseline (2026-04-29)

## Headline

| metric | value | n |
|---|---|---|
| Recall-floor mean (token overlap) | **0.717** | 90 |
| Local-judge accuracy (Qwen3-27B) | **0.633** | 30 |

This is Maez's first published number against the field's standard
long-horizon memory benchmark
([Wu et al. 2024, arxiv 2410.10813](https://arxiv.org/abs/2410.10813),
ICLR 2025). It is a baseline, not a finished result — the published
numbers in the paper use **GPT-4o** as the judge and the **S split**
(~115k tokens / question with full distractor sessions). This run
uses the local Qwen3-27B judge and the **oracle split** (evidence
sessions only). Cross-comparisons with paper rows must adjust for
both axes.

## What ran

* Dataset: `longmemeval_oracle` (15 MB, 500 questions across six
  question types).
* Recall floor: 90 questions, stratified — 15 per type.
* Local judge: 30 questions, stratified — 5 per type.
* Memory stack: live `MemoryManager` raw archive, isolated per
  question into a tmpdir (live store never touched).
* Recall path: `MemoryManager.recall_for_cycle` (exactly what the
  daemon uses at synthesis time).
* Judge model: `qwen36-27b` on llama-server :8080, temperature 0,
  binary CORRECT/INCORRECT verdict, fail-closed parsing.

## By question type

| type | n (recall) | recall mean | n (judge) | judge accuracy |
|---|---|---|---|---|
| single-session-assistant | 15 | 0.837 | 5 | **1.00** |
| single-session-user | 15 | 0.892 | 5 | **1.00** |
| knowledge-update | 15 | 0.867 | 5 | 0.80 |
| single-session-preference | 15 | 0.483 | 5 | 0.80 |
| multi-session | 15 | 0.402 | 5 | **0.20** |
| temporal-reasoning | 15 | 0.820 | 5 | **0.00** |

## What this tells us

**Strong:** single-session recall (user + assistant turns) is at
ceiling. Knowledge updates and preferences are good. The base
retrieval path works for "what did the user say" lookups.

**Weak — and clearly localized:**

1. **Temporal reasoning collapses under the judge** (recall floor
   0.82 → judge 0.00). The recall path surfaces the right *tokens*
   (dates, event names) but doesn't deliver the temporal synthesis
   the question demands ("which came first", "how long after"). The
   token-overlap score is a false positive for this type.

2. **Multi-session reasoning is the weakest by both metrics**
   (recall 0.40 / judge 0.20). The harness does NOT run the daily
   consolidator between session-date boundaries; the recall layer
   sees raw turns only. This was flagged in the Slice 9 Session 1
   audit as a fidelity gap and is now empirically confirmed.

3. **Preference recall is below half** at the floor (0.48). User-
   preference statements ("I like X", "I prefer Y") are exactly the
   bonded-companion signal Maez most needs to retain — this is the
   most actionable gap.

## Why these numbers, not the paper's

* **Oracle split, not S/M.** No distractor sessions. Easier
  problem; numbers are an upper bound on what Maez does on the
  full split.
* **Local Qwen3-27B judge, not GPT-4o.** Cheaper, free, but the
  paper's calibration is against the GPT-4o judge. Expect some
  drift on borderline answers.
* **Recall-floor scoring on the 90.** Token overlap, not
  generation. We measure what the memory layer surfaces, not what
  Maez writes back.

## Reproducing this run

```bash
# Download oracle split (~15 MB):
mkdir -p data/longmemeval && cd data/longmemeval
wget -O longmemeval_oracle.json \
  https://huggingface.co/datasets/xiaowu0162/longmemeval/resolve/main/longmemeval_oracle
cd ../..

# Recall-floor stratified 90:
python -m core.eval \
  --questions data/longmemeval/longmemeval_oracle.json \
  --ids-from docs/eval/runs/lme_sample_ids.txt --limit 1000 \
  --report docs/eval/runs/longmemeval_oracle_strat90_2026-04-29.md \
  --json-out docs/eval/runs/longmemeval_oracle_strat90_2026-04-29.json

# Local judge 30:
python -m core.eval \
  --questions data/longmemeval/longmemeval_oracle.json \
  --ids-from docs/eval/runs/lme_judge_sample_ids.txt --limit 1000 \
  --judge --with-surfaced \
  --report docs/eval/runs/longmemeval_judge30_2026-04-29.md \
  --json-out docs/eval/runs/longmemeval_judge30_2026-04-29.json
```

Sample-ID files are committed under `docs/eval/runs/`; the run is
reproducible on any clone with the dataset downloaded.

## Next moves (informed by these numbers)

* **Run the consolidator between haystack date boundaries.** The
  multi-session gap is partially structural — Maez's normal recall
  flow consults daily summaries; the benchmark currently gives it
  raw-only. Fix in adapter; expect the multi-session and temporal
  numbers to improve.
* **Add a preference-extraction promotion path.** "I like X" / "I
  prefer Y" are below half on the simplest split — they should be
  promoted to a longer-lived tier the moment they're observed.
* **Move to the S split.** Oracle is the warm-up; S (~115k tokens
  with distractors) is the headline-comparable load.
* **Wire a stronger judge for the publication number.** Either
  Sonnet/Opus via `claude_tier`, or GPT-4o via subscription proxy,
  to match the paper's calibration.

## Files

* Adapter: [`core/eval/longmemeval.py`](../../core/eval/longmemeval.py)
* CLI: [`core/eval/__main__.py`](../../core/eval/__main__.py)
* Local judge: [`core/eval/judge.py`](../../core/eval/judge.py)
* Sample IDs: [`docs/eval/runs/lme_sample_ids.txt`](runs/lme_sample_ids.txt) (90), [`docs/eval/runs/lme_judge_sample_ids.txt`](runs/lme_judge_sample_ids.txt) (30)
* Per-question raw: `docs/eval/runs/longmemeval_*_2026-04-29.json`
  (gitignored — large)

## Citation

If you cite this baseline:

> Maez, *LongMemEval oracle baseline* (2026-04-29):
> recall-floor 0.717 / local-Qwen3-27B-judge 0.633 across stratified
> samples. Per-type breakdown shows multi-session reasoning (judge
> 0.20) and temporal reasoning (judge 0.00) as primary gaps;
> single-session and knowledge-update are at or near ceiling.
