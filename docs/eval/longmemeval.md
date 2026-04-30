# LongMemEval — running the benchmark against Maez

This is the field-standard long-horizon memory benchmark
(Wu et al. 2024, [arxiv 2410.10813](https://arxiv.org/abs/2410.10813),
ICLR 2025; [github xiaowu0162/LongMemEval](https://github.com/xiaowu0162/LongMemEval)).
500 curated questions over scalable user-assistant chat histories,
testing five abilities:

1. Information extraction
2. Multi-session reasoning
3. Knowledge updates
4. Temporal reasoning
5. Abstention

## Adapter shape

The Maez harness ([`core/eval/longmemeval.py`](../../core/eval/longmemeval.py)):

- `IsolatedMemoryHarness` — context manager that monkeypatches
  `memory.memory_manager.BASE_DB` to a tmpdir, instantiates
  `MemoryManager`, and restores the live `BASE_DB` on exit. The
  benchmark **cannot** pollute the live store.
- `ingest_haystack` — converts each session's turns into raw archive
  entries, dated to `haystack_dates` so temporal-reasoning questions
  see realistic chronology.
- `recall_for_question` — runs `recall_for_cycle` (the daemon's
  recall path) and returns the surfaced text fragments.
- `score_answer` — token-overlap heuristic mirroring
  `lived_recall._tokenize`. Lower bound on whether reference signal
  surfaced. **Not** the official GPT-4o judge — that's a Session 2
  follow-up.
- `run_subset` — driver that loads + runs N questions through
  isolated harnesses (one per question, no cross-contamination).

## Download the dataset

```bash
mkdir -p data/longmemeval
cd data/longmemeval
# Oracle split (small, fast — only the evidence-bearing sessions):
wget https://huggingface.co/datasets/xiaowu0162/longmemeval/resolve/main/longmemeval_oracle.json
# S split (~115k tokens / question, full distractor sessions):
wget https://huggingface.co/datasets/xiaowu0162/longmemeval/resolve/main/longmemeval_s.json
# M split (~1.5M tokens / question — only run if you have the time):
# wget https://huggingface.co/datasets/xiaowu0162/longmemeval/resolve/main/longmemeval_m.json
```

`data/longmemeval/` is gitignored — these files don't ship with the
repo.

## Run a subset

```bash
# 10 questions from the oracle split, summary to stdout:
python -m core.eval --questions data/longmemeval/longmemeval_oracle.json --limit 10

# Full oracle split with a markdown report + per-question JSON:
python -m core.eval \
  --questions data/longmemeval/longmemeval_oracle.json \
  --limit 500 \
  --report docs/eval/runs/longmemeval_oracle_2026-04-29.md \
  --json-out docs/eval/runs/longmemeval_oracle_2026-04-29.json
```

## Reading the score

The current scorer is a fast token-overlap heuristic, not the
official GPT-4o judge. Treat the output as a **recall floor**:

- `mean_score = 1.0` on a single-session question → all reference
  content tokens surfaced through `recall_for_cycle`.
- `mean_score < 0.5` on a category → recall is the bottleneck for
  that category before generation even runs. That's a memory-stack
  problem.
- The judge gap (proper-noun matches, multi-session synthesis,
  abstention) closes when Session 2 wires the GPT-4o (or
  Sonnet/Opus via `claude_tier`) judge.

## Operational note: do not run while the daemon is up

The harness monkeypatches `memory.memory_manager.BASE_DB` (a module-
global) for the lifetime of each question. The daemon normally runs
in its own process, so this is safe. **Don't run the benchmark inside
the same Python process that's serving the daemon** — both would
share the rebound BASE_DB. The CLI is single-process by design.

## Why an isolated tmpdir is non-negotiable

The live MemoryManager (`memory/db/`) is bonded-companion memory. It
contains gestation memories, lived memories, and core covenant
content. **A benchmark run pumping 500 synthetic chat histories into
that store would be a covenant breach**: it would corrupt continuity
and leave fabricated content in the canonical archive.

The harness asserts the tmpdir path before yielding the manager and
unconditionally restores `BASE_DB` on exit — the test
`test_harness_restores_base_db_after_exit` enforces both.

## What's intentionally NOT in Session 1

- **The GPT-4o judge.** Session 2. The token-overlap scorer is enough
  to surface recall regressions across slices; the judge is what's
  needed for a citable benchmark number.
- **Generation.** We score what the recall path surfaces, not what
  Maez writes back. Latency on a 500-question generation run via the
  local brain is hours; defer until the recall-only number is
  validated.
- **The S/M splits as default.** Oracle (~10k tokens / question,
  evidence sessions only) is the right starting load. Move to S
  once oracle is clean.
