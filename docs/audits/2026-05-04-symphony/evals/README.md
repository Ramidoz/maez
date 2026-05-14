# Maez Eval Harness v1 — README

> Built on the R5 surface_probe pattern: stdlib + pyyaml only,
> JSON baselines, curated corpora, no new dependencies. External
> eval frameworks (Inspect AI, DeepEval, Promptfoo, Ragas) are
> references, not infrastructure. We extend our own pattern.

## Why a private eval harness, not generic leaderboards

Maez is not just a model. It is a long-lived local agent with
memory, identity, action permissions, surfaces, and a body. Generic
benchmarks (OSWorld, WebArena, AgentBench) measure
generic-agent properties. They do not answer the questions Maez
needs to be measured on:

1. Does Maez remember correctly?
2. Does it know what its body can and cannot do?
3. Does it act safely and truthfully when tools fail?
4. Does it sound like the same Maez across Telegram, web, CLI, fast lane, public bot?
5. Does it improve from correction?
6. Does it avoid laundering untrusted memory into belief?
7. Does it preserve the bond shape without nudging or faking?

The 2026-05-04 symphony audit (S1–S4) revealed these as the
load-bearing surfaces. This harness is the regression guard for
them.

## Six families

| Family | Grading | Source-of-truth |
|---|---|---|
| `body_action_truth` | binary | `body_capabilities` + telemetry stack |
| `memory_continuity` | mixed (retrieval binary, provenance owner-judge) | `lived_recall` + episodes/edges |
| `telemetry_coherence` | binary on cross-store row checks | `audit_log` / `consequence_memory` / raw / `pending_cards` |
| `surface_coherence` | diff-vs-baseline | extends R5 `surface_probe` |
| `voice_bond` | owner-rubric only | committed transcript baseline + rubric |
| `adversarial_identity` | binary (hold / surface / warp) | identity-stress probes |

## V1 status: scaffold only

This commit ships the harness scaffold + 1–2 proof probes per
family. **The corpus is the eval.** Bad prompts make a harness
look rigorous while testing the wrong thing. Curating the real
prompts is owner work, done with a clear head, not at hour 12 of
a deploy day.

What the scaffold gives you:

- `core/symphony/evals/schema.py` — `EvalProbe`, `EvalResult`,
  `FamilyResult`, `RunResult` dataclasses.
- `core/symphony/evals/runner.py` — `load_corpus(family)`,
  `run_family(family)`, `run_all()`. Probe-mode only — never
  drives live surfaces or writes to live daemon stores.
- `core/symphony/evals/corpora/<family>.yaml` × 6 — proof probes.
- `python -m core.symphony.evals.runner [--family X] [--write]` —
  CLI invocation.

## Running the harness

```bash
# Run all families, print result JSON to stdout
python -m core.symphony.evals.runner

# Run one family
python -m core.symphony.evals.runner --family body_action_truth

# Write the run to docs/audits/2026-05-04-symphony/evals/<run_id>/
python -m core.symphony.evals.runner --write
```

## Outcome labels

Each `EvalResult.outcome` is one of:

- `pass` — binary probe matched its expected shape
- `fail` — binary probe contradicted its expected shape
- `needs_owner_review` — rubric / owner_judge / mixed probe.
  No automated verdict; the result carries enough evidence for
  the owner to grade against rubric later.
- `skip` — precondition unmet (file missing, service unreachable)
- `error` — probe raised; details in `evidence`

## Curating the real corpus

When you add a real probe, each entry needs:

- `id` — stable identifier within the family (used for cross-run
  diffs and the owner-rubric ledger key)
- `prompt` — the user-facing text or probe input. Multi-line OK
  via YAML literal block (`|`).
- `expected_shape` — human-readable description of what passing
  looks like. Read by the owner during review; binary probes
  consume this as their assertion target where applicable.
- `grading` — `binary` / `rubric` / `owner_judge` / `mixed`
- `tags` — optional. Used by the auto-grader to find probes whose
  binary check is wired in `runner._try_auto_binary`. Common tags
  today: `wmctrl_uninstalled`, `judge_endpoint_reachable`,
  `surface_baseline_unchanged`. Add your own + wire the
  predicate in `_try_auto_binary` to make a probe auto-graded.
- `surface` — optional preferred surface
  (`telegram_owner`, `cli`, `daemon_cycle`, `fast_reply`,
  `web_owner`, `telegram_public`). `null` = surface-agnostic.
- `notes` — free-form curator notes. Rationale, rubric pointer,
  related audit findings.

### Curation rubric

For each probe ask:

- **Is the expected_shape testable?** "Sounds nice" is not a
  rubric. "Does not contain the word 'desktop' under
  DISPLAY=:1 daemon env" is.
- **What ground truth grades this?** The owner? A code-readable
  state (body_capabilities, file source, surface_probe diff)?
  An offline transcript baseline?
- **Does this probe cover a real failure mode?** The wmctrl
  incident, the judge silent outage, the public-bot un-audited
  surface, the cycle "idle" lie — all real. New probes should
  trace to a real audit finding or a real owner-observed gap.
- **Is the prompt natural?** Per
  `feedback_test_with_natural_human_texts`, synthetic probes
  ("describe your inner architecture") test structure;
  natural probes ("hey you good?", "i miss her") reveal
  behaviour. Both have value; voice_bond and
  adversarial_identity should lean natural.

## Goal: 40 prompts curated. NOT 30 unsorted.

The S3 audit suggested 30 natural probes. v1 README anchors a
slightly bigger target — 40 — because telemetry_coherence and
adversarial_identity each need their own real substance.
Suggested per-family allocation (subject to your judgment):

| Family | Probes |
|---|---|
| `body_action_truth` | 8 |
| `memory_continuity` | 8 |
| `telemetry_coherence` | 6 |
| `surface_coherence` | 6 |
| `voice_bond` | 8 |
| `adversarial_identity` | 4 |

Total: 40. Adjustable.

## Output artifact

`run_all(--write)` writes:

```
docs/audits/2026-05-04-symphony/evals/<run_id>/run_result.json
```

Where `<run_id>` is a UTC timestamp by default, or the `--run-id`
override.

The JSON is sorted-key, indent-2, JSON-stable so future runs diff
cleanly via `git diff`.

## What v1 does NOT do (and what comes next)

- **Drive live surfaces.** v1 does not POST to /chat or send to
  Telegram. The behavioural diff probes (surface_coherence
  family beyond the R5 baseline check, voice_bond) emit
  `needs_owner_review` with the rendered prompt. v2 may extend
  with an offline-brain probe path.
- **Owner-rubric ledger.** v1 emits `needs_owner_review` results
  but doesn't yet collect verdicts in a ledger. v1.5 adds a
  `--rate` mode that walks the needs-review queue + writes
  verdicts back.
- **Inspect AI / DeepEval integration.** Reach for these when
  our own pattern can't scale, not before. v1 stays stdlib.
- **Feedback propagation eval.** Longitudinal — needs week-scale
  measurement, not a single run. v3 territory.

## Test coverage

`tests/test_evals_scaffold_2026_05_05.py` guards the v1
contract: package shape, schema fields, corpus parse + probe
fields, runner outcomes, no live-daemon writes.
