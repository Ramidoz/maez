# Brain Benchmark Slice 2 — Part 2: the Battery Driver

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`).

**Goal:** Make the verified core (Slice 2 part 1, merged @ 28c25dd) actually *run* — a real `probe_run` over the recall battery via the production synthesis seam, the two-stage k=3/k=7 loop, tail-flagging, and a CLI — so the benchmark can produce a real owner-run `BenchPacket`. **Until this ships, no benchmark evidence is real and the 2b re-run stays blocked.**

**Architecture:** Build on the merged `scripts/brain_bench/` core. The core's `run_benchmark` already scores/gates/judges injected `ProbeSample` rows correctly; part 2 supplies the *real* rows (real inference) + the staging loop + the entrypoint. Plus two foundation cleanups the part-1 review flagged.

**Tech Stack:** Python 3 stdlib + `unittest`; reuses 2a's `scripts/recall_flip_eval/{sandbox,probes,harness}` seeding + assertion helpers and `core.routing.focused_cognition.focused_synthesize`. Real model inference is **owner-operated** (like 2b); tests prove driver logic with a stubbed `stream_factory`/`chat_fn` — no real model in CI.

**Spec:** [docs/superpowers/specs/2026-05-31-brain-benchmark-design.md](../specs/2026-05-31-brain-benchmark-design.md) (v3.1). Part-1 verification + the mandatory part-2 list are in merge commit 28c25dd.

**Discipline reminders:** model-agnostic; genderless; **2a frozen** (reuse its seeders/asserts, don't mutate); hermetic + send-path-free (real `probe_run` runs under `no_egress(allow_loopback_ports=(variant.port,))`); grounding stays the **categorical bool from 2a's `assert_probe_result`** (never an invented number); the real run produces the artifact but **never flips** — owner decides, S5 voice gate separate.

---

## File Structure
- **Modify** `scripts/brain_bench/judge.py` — delete the vestigial `seed` param.
- **Modify** `scripts/brain_bench/gates.py` — widen `voice_lint` cognition set to the canonical forbidden verbs.
- **Modify** `scripts/brain_bench/bench.py` — `run_full_battery` (two-stage loop), `tail_flags` computation, CLI `main`.
- **Create** `scripts/brain_bench/probe_runner.py` — the real `probe_run`: seed → real `focused_synthesize` inference → `ProbeSample` rows.
- **Modify** `scripts/brain_bench/launcher.py` — exec into the CLI entrypoint with parsed args.
- **Tests:** `tests/test_brain_bench_probe_runner.py`, extend `tests/test_brain_bench_orchestration.py`, `tests/test_brain_bench_judge.py`, `tests/test_brain_bench_gates.py`.

---

## Task 1: Foundation cleanups (from part-1 review)

**Files:** Modify `scripts/brain_bench/judge.py`, `gates.py`; Tests in the existing judge/gates test modules.

- [ ] **Step 1: Delete vestigial `seed`.** RED: a test asserting `judge_pairwise` has no `seed` parameter (`inspect.signature`). Implement: remove `seed` from `judge_pairwise` and its call site in `bench.py:198`. Full counterbalancing is deterministic, so nothing is lost. Run → pass.
- [ ] **Step 2: Widen `voice_lint` cognition set.** RED: `voice_lint("I wonder about that ...<20+ chars>")` must return `ok=False` with reason `cognition_verb`; likewise for `mull`, `reflect`, `sense`, and `thinking`. Implement: change `_COGNITION_RE` to the canonical set `\b(think|thinking|ponder|consider|wonder|mull|reflect|feel|sense)\b` (align with the receipt slice's `FORBIDDEN_COGNITION_VERBS`). Run → pass.
- [ ] **Step 3: Commit** (`feat(recall): brain-bench part2 cleanups — drop judge seed, widen voice_lint`).

---

## Task 2: Real `probe_run` — seed → real synthesis → `ProbeSample`

**Files:** Create `scripts/brain_bench/probe_runner.py`; Test `tests/test_brain_bench_probe_runner.py`

- [ ] **Step 1: RED test** — with a **stubbed `stream_factory`** (no real model), `build_probe_run(...)` returns a callable that, given a variant, yields `ProbeSample` rows for each probe in the 2a battery, with `grounded_categorical` taken from 2a's `assert_probe_result` (a bool), latencies from `measure_generation`, and `inference_failed`/`fail_code` set when the stub raises.

```python
# tests/test_brain_bench_probe_runner.py (shape)
import json, unittest
from scripts.brain_bench.probe_runner import build_probe_run
from scripts.brain_bench.bench import ProbeSample
from scripts.brain_bench.variants import load_variants


class ProbeRunnerTests(unittest.TestCase):
    def _variant(self):
        return load_variants(json.dumps([{"label": "v",
            "base_url": "http://127.0.0.1:11434", "model": "m"}]))[0]

    def test_yields_probe_samples_with_categorical_grounding(self):
        def grounded_stream(*, variant, payload):
            return iter([{"content": "April 27 infra note [E1]"}])
        probe_run = build_probe_run(k=1, stream_factory=grounded_stream,
                                    clock=iter([0.0, 0.2, 0.5] * 50).__next__)
        rows = list(probe_run(self._variant()))
        self.assertTrue(rows and all(isinstance(r, ProbeSample) for r in rows))
        for r in rows:
            self.assertIsInstance(r.grounded_categorical, bool)  # 2a's bool, not a float

    def test_inference_failure_becomes_closed_sample(self):
        def boom(*, variant, payload):
            raise TimeoutError()
        probe_run = build_probe_run(k=1, stream_factory=boom,
                                    clock=lambda: 0.0)
        rows = list(probe_run(self._variant()))
        self.assertTrue(any(r.inference_failed for r in rows))
        self.assertTrue(all(r.answer == "" for r in rows if r.inference_failed))
```

- [ ] **Step 2: Run → fail.**
- [ ] **Step 3: Implement** `build_probe_run(*, k, stream_factory=None, clock=None) -> Callable[[Variant], Iterable[ProbeSample]]`:
  - For each probe in `scripts.recall_flip_eval.probes.PROBES`: seed fixtures via the 2a seeders (`seed_dated_memory` / `harness._seed_for_probe`) under the sandbox; build `(chat_fn, sink)` via `make_benchmark_chat_fn(variant=..., stream_factory=...)`; run `k` repetitions calling the **real** `focused_cognition.focused_synthesize(messages, chat_fn=chat_fn)` (mirror `harness.py:139`); read each rep's `GenerationMeasurement` from the sink for latency/TTFT/tokens; compute `grounded_categorical` + `false_absence`/`wrong_absence` from 2a's `assert_probe_result(probe, ...) -> unsafe==False` and the probe kind; gather per-variant `ops_evidence` (from the variant's resolved deployment facts — see Task 4 note); emit one `ProbeSample` per (probe, sample_id) with `p95_ms`/`max_ms` aggregated across that probe's reps.
  - On inference failure (`measurement.failed`), emit a `ProbeSample` with `inference_failed=True`, `fail_code=measurement.fail_code`, `answer=""` (scrubbed), and honesty fields set so the variant fails the hard gate (`grounded_categorical=False`).
  - Document: chunk-count token proxy; grounding is exactly 2a's categorical bool.
- [ ] **Step 4: Run → pass. Commit.**

---

## Task 3: Two-stage k=3 / k=7 battery loop + tail-flagging

**Files:** Modify `scripts/brain_bench/bench.py`; Test extend `tests/test_brain_bench_orchestration.py`

- [ ] **Step 1: RED test** — `run_full_battery` screens at `SCREEN_K=3`, drops hard/latency failures, runs `FINALIST_K=7` only on survivors (top ≤3), and a slow-tail run is flagged (`tail_flags` contains `tail_risk`) without averaging it away.

```python
def test_two_stage_drops_then_deepens(self):
    calls = {"screen": 0, "finalist": 0}
    # fake probe_run factory records the k it was built with per stage
    ...
    # assert a hard-failing variant is absent from the finalist stage,
    # and a survivor was run at FINALIST_K reps.

def test_tail_run_flagged_not_averaged(self):
    # one rep at 21s (> ceiling -> over_ceiling hard fail) vs
    # one rep at 5x p50 but <= ceiling -> tail_risk advisory flag, distinct.
    ...
```

- [ ] **Step 2: Run → fail.**
- [ ] **Step 3: Implement** `run_full_battery(registry, *, fixture_manifest_hash, build_probe_run_fn, call_judge=None, ...)`:
  - **Stage 1 (screen):** `probe_run = build_probe_run_fn(k=SCREEN_K)`; call `run_benchmark(registry, probe_run=probe_run, ...)`; keep variants with `hard_pass` and not `over_ceiling`.
  - **Stage 2 (finalists):** take top ≤3 survivors; `probe_run = build_probe_run_fn(k=FINALIST_K)`; re-run `run_benchmark` over the survivor sub-registry; merge results (screened-out variants keep their stage-1 report + reason).
  - **Tail-flagging:** in the stats, `tail_flags = ("tail_risk",)` if any rep > 2× the variant's p50 but ≤ `ANSWER_CEILING_MS`; `over_ceiling` (hard fail) stays separate. Set on the `VariantReport`.
  - Return the merged `BenchPacket`.
- [ ] **Step 4: Run → pass. Commit.**

---

## Task 4: CLI entrypoint + launcher wiring

**Files:** Modify `scripts/brain_bench/bench.py`, `launcher.py`; Test `tests/test_brain_bench_launcher.py` (extend)

- [ ] **Step 1: RED test** — `bench.main(argv)` with `--variants-config <path>` (and a stubbed inference via an env/inject seam for the test) loads the registry (fail-closed if missing/empty), runs `run_full_battery`, writes the `BenchPacket` JSON + the quarantined debug dump, and prints the packet path. Assert: missing config → non-zero/`BenchmarkConfigError`; no `model_config` fallback.
- [ ] **Step 2: Run → fail.**
- [ ] **Step 3: Implement** `bench.main(argv=None)`: argparse `--variants-config` (required), `--judge-base-url` (default `http://127.0.0.1:8081`), `--finalist-k` (default `FINALIST_K`, recorded if overridden), `--out`; load registry (`load_variants` from the file, record source+hash); build the real `build_probe_run`; run `run_full_battery`; write packet + quarantined dump; print paths. `launcher.main` parses sandbox-root, sets `MAEZ_HOME/DATA/CONFIG/CACHE/OWNER_TIMEZONE`, then `os.execv` into `python -m scripts.brain_bench.bench <args>` (sandbox before any maez import).
- [ ] **Step 4: Run → pass. Commit.**

---

## Task 5: Regression + the real-run note

- [ ] **Step 1:** Ruff on changed files.
- [ ] **Step 2:** Full brain_bench suite + 2a suite green (`.venv/bin/python -m unittest tests.test_brain_bench_* tests.test_recall_flip_eval_isolation tests.test_recall_flip_eval_packet tests.test_recall_flip_eval_probes`).
- [ ] **Step 3:** Add a short `scripts/brain_bench/README` note: the suite proves driver logic with stubbed inference; the **real benchmark is owner-operated** via the launcher against real local model endpoints, and its `BenchPacket` is producer-evidence (owner verdict + S5 gate required). **Commit** (scoped).

---

## Self-Review
**Coverage of the mandatory part-2 list:** real `probe_run` wiring 2a categorical grounding + real `focused_synthesize` → Task 2 ✓; two-stage k=3/k=7 → Task 3 ✓; tail-flagging → Task 3 ✓; CLI → Task 4 ✓; delete `seed` → Task 1 ✓; widen `voice_lint` → Task 1 ✓.
**Placeholder scan:** the `ops_evidence` source (Task 2/4) resolves from the variant's declared deployment facts in config (closed `OpsRubric` enums) — pin at impl; real inference + run owner-operated; logic via stub injection. No "TODO."
**Symbol consistency:** `build_probe_run`, `run_full_battery`, `ProbeSample`, `make_benchmark_chat_fn`, `assert_probe_result`, `SCREEN_K`/`FINALIST_K`, `voice_lint`, `judge_pairwise` (no seed) — consistent with the merged core.
**Ordering:** cleanups(1) → real rows(2) → staging+tail(3) → CLI(4) → regression(5). Each committable; staging builds on real rows; CLI builds on staging.

## Execution note
Codex's six-agent pass pressures: (1) **`probe_run` actually drives the production `focused_synthesize`** (not a lookalike) and grounding is 2a's categorical bool (not re-derived); (2) **two-stage isolation** — finalists re-run under the same sandbox/egress, screened-out variants can't sneak into the finalist set; (3) **tail vs over-ceiling stay distinct**; (4) **fail-closed CLI** — missing/empty config errors, never falls back to the live model. The owner-run real benchmark stays the owner's hand; this slice makes it runnable, not run.
