# Brain Benchmark (Slice 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A hermetic, send-path-free benchmark that runs real local model variants over the recall battery and emits a content-free, advisory `BenchPacket` recommending whether any variant is *honest-enough AND fast-enough* for the 2b re-run.

**Architecture:** New sibling package `scripts/brain_bench/` that **reuses** `scripts/recall_flip_eval/sandbox.py` + `probes.py` by import (2a stays frozen). The one shared change: parameterize 2a's `no_egress()` socket guard with a loopback-inference allowlist (2a keeps block-all by default). Owner-supplied pluggable variant registry; per-variant streaming inference measurement; fixed pairwise blind judge; two-tier gates with lexicographic ranking; closed-enum BenchPacket.

**Tech Stack:** Python 3 stdlib (`socket`, `threading`, `dataclasses`, `enum`, `statistics`, `random`, `json`), `unittest` via `.venv/bin/python -m unittest` (pytest NOT installed). Real inference via the existing ollama/OpenAI-compatible localhost endpoint; tests mock the endpoint.

**Spec:** [docs/superpowers/specs/2026-05-31-brain-benchmark-design.md](../specs/2026-05-31-brain-benchmark-design.md) @ 5ca936d.

**Discipline reminders:**
- **Task 1 is the load-bearing risk.** If the harness can touch real memory or arbitrary network, the benchmark is invalid no matter how good the scoring. Prove isolation + the socket allowlist before any variant/judge logic exists.
- Frozen constants (pre-registered): `answer_ceiling_ms=12000`, `strong_ms=8000`, `excellent_band_ms=(4000,6000)`, `screen_k=3`, `finalist_k=7`. Owner overrides must be recorded before running.
- `BenchPacket` is **content-free**: closed-enum `fail_reasons` + `recommendation`, no probe/answer/evidence text. Raw answers → gitignored debug dump only.
- Judge is **pairwise + blind**: labels hidden, order randomized (seeded), model+settings pinned, quality & voice scored separately.
- Model-agnostic: variants are config, no model names hardcoded.
- Hard honesty gates are deterministic and beat speed (lexicographic: honesty → blind voice/quality → latency → ops).
- 2a must remain byte-behaviorally unchanged (its `no_egress()` call site keeps block-all).

---

## File Structure
- **Modify** `scripts/recall_flip_eval/sandbox.py` — parameterize `no_egress(allow_loopback_ports=())`; default `()` = block-all (2a unchanged).
- **Create** `scripts/brain_bench/__init__.py`
- **Create** `scripts/brain_bench/variants.py` — `Variant` dataclass + `load_variants()` (pluggable, model-agnostic).
- **Create** `scripts/brain_bench/inference.py` — `measure_generation(...)` streaming call → TTFT/total/tokens-per-sec/output-tokens/answer.
- **Create** `scripts/brain_bench/judge.py` — `judge_pairwise(...)` blind pairwise quality+voice → per-variant ranks.
- **Create** `scripts/brain_bench/gates.py` — hard gates, latency gate, lexicographic ranking, ops rubric.
- **Create** `scripts/brain_bench/bench_packet.py` — `BenchPacket` / `VariantReport` (bench_packet.v1, closed enums).
- **Create** `scripts/brain_bench/bench.py` — two-stage orchestrator + main.
- **Create** `scripts/brain_bench/launcher.py` — env-before-import `os.execv` (mirrors 2a).
- **Create** tests: `tests/test_brain_bench_sandbox.py`, `_variants.py`, `_inference.py`, `_judge.py`, `_gates.py`, `_packet.py`, `_orchestration.py`.
- **Modify** `.gitignore` — ignore the debug-dump dir.

---

## Task 1: Parameterize the egress guard — loopback-inference allowlist (LOAD-BEARING)

**Files:** Modify `scripts/recall_flip_eval/sandbox.py`; Test `tests/test_brain_bench_sandbox.py`

- [ ] **Step 1: RED test** — block external, allow only loopback:allowed-port, and 2a block-all unchanged:

```python
# tests/test_brain_bench_sandbox.py
import socket
import unittest
from scripts.recall_flip_eval.sandbox import no_egress, EgressBlockedError


class EgressAllowlistTests(unittest.TestCase):
    def test_default_blocks_all_including_loopback(self):
        # 2a behavior preserved: empty allowlist blocks everything.
        with no_egress():
            with self.assertRaises(EgressBlockedError):
                socket.create_connection(("127.0.0.1", 11434))
            with self.assertRaises(EgressBlockedError):
                socket.create_connection(("8.8.8.8", 53))

    def test_allows_only_loopback_allowed_port(self):
        with no_egress(allow_loopback_ports=(11434,)):
            # external still blocked
            with self.assertRaises(EgressBlockedError):
                socket.create_connection(("8.8.8.8", 53))
            # loopback on a NON-allowed port still blocked
            with self.assertRaises(EgressBlockedError):
                socket.create_connection(("127.0.0.1", 22))
            # loopback on the allowed port is permitted to reach the original
            # (connection will fail/refuse if nothing listens, but it must NOT
            # raise EgressBlockedError — it passes the guard)
            try:
                socket.create_connection(("127.0.0.1", 11434), timeout=0.01)
            except EgressBlockedError:
                self.fail("allowed loopback port was blocked by the guard")
            except OSError:
                pass  # connection refused/timeout is fine — guard let it through

    def test_non_loopback_host_on_allowed_port_blocked(self):
        with no_egress(allow_loopback_ports=(11434,)):
            with self.assertRaises(EgressBlockedError):
                socket.create_connection(("10.0.0.5", 11434))
```

- [ ] **Step 2: Run → fail** (`no_egress()` takes no args yet).

- [ ] **Step 3: Implement** — add the param + an allow-check, preserving the block-all default. Replace the `no_egress` body's `blocked` closure with an allowlist-aware guard:

```python
# scripts/recall_flip_eval/sandbox.py
_LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost", "127.0.1.1"}


def _addr_is_allowed(address, allow_loopback_ports) -> bool:
    if not allow_loopback_ports:
        return False
    try:
        host, port = address[0], address[1]
    except (TypeError, IndexError, KeyError):
        return False
    return str(host) in _LOOPBACK_HOSTS and int(port) in set(allow_loopback_ports)


@contextmanager
def no_egress(allow_loopback_ports: tuple[int, ...] = ()) -> Iterator[None]:
    original_create_connection = socket.create_connection
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    original_sendto = socket.socket.sendto
    original_getaddrinfo = socket.getaddrinfo

    def guard_create_connection(address, *a, **k):
        if _addr_is_allowed(address, allow_loopback_ports):
            return original_create_connection(address, *a, **k)
        raise EgressBlockedError("offline harness blocks socket egress")

    def guard_connect(self, address, *a, **k):
        if _addr_is_allowed(address, allow_loopback_ports):
            return original_connect(self, address, *a, **k)
        raise EgressBlockedError("offline harness blocks socket egress")

    def guard_connect_ex(self, address, *a, **k):
        if _addr_is_allowed(address, allow_loopback_ports):
            return original_connect_ex(self, address, *a, **k)
        raise EgressBlockedError("offline harness blocks socket egress")

    def guard_getaddrinfo(host, port, *a, **k):
        if str(host) in _LOOPBACK_HOSTS and int(port or 0) in set(allow_loopback_ports):
            return original_getaddrinfo(host, port, *a, **k)
        raise EgressBlockedError("offline harness blocks DNS/egress")

    def blocked_sendto(*_a, **_k):
        raise EgressBlockedError("offline harness blocks socket egress")

    socket.create_connection = guard_create_connection
    socket.socket.connect = guard_connect
    socket.socket.connect_ex = guard_connect_ex
    socket.socket.sendto = blocked_sendto
    socket.getaddrinfo = guard_getaddrinfo
    try:
        yield
    finally:
        socket.create_connection = original_create_connection
        socket.socket.connect = original_connect
        socket.socket.connect_ex = original_connect_ex
        socket.socket.sendto = original_sendto
        socket.getaddrinfo = original_getaddrinfo
```

(Confirm `from contextlib import contextmanager` is already imported in sandbox.py; the existing `no_egress` was already a contextmanager so it is.)

- [ ] **Step 4: Run → pass.** Also re-run 2a's own sandbox suite to prove block-all is unchanged: `.venv/bin/python -m unittest tests.test_recall_flip_eval_sandbox -v` (or the 2a sandbox test module name — discover with `grep -rl "no_egress" tests/`).

- [ ] **Step 5: Add an isolation assertion test** reusing 2a's `assert_sandbox` — prove brain_bench's sandbox setup leaves memory paths inside the sandbox (mirror 2a's existing assert_sandbox test against a temp root). Commit.

---

## Task 2: Variant registry (pluggable, model-agnostic)

**Files:** Create `scripts/brain_bench/variants.py`, `scripts/brain_bench/__init__.py`; Test `tests/test_brain_bench_variants.py`

- [ ] **Step 1: RED test**

```python
# tests/test_brain_bench_variants.py
import json
import unittest
from scripts.brain_bench.variants import Variant, load_variants, VariantConfigError


class VariantRegistryTests(unittest.TestCase):
    def test_loads_minimal_variant(self):
        raw = [{"label": "current", "base_url": "http://127.0.0.1:11434",
                "model": "gemma4:26b"}]
        variants = load_variants(json.dumps(raw))
        self.assertEqual(len(variants), 1)
        self.assertEqual(variants[0].label, "current")
        self.assertEqual(variants[0].chat_kwargs, {})  # default
        self.assertIsNone(variants[0].draft_model)

    def test_carries_optional_speculative_config(self):
        raw = [{"label": "spec", "base_url": "http://127.0.0.1:8080",
                "model": "big", "draft_model": "small",
                "chat_kwargs": {"num_predict": 512}}]
        v = load_variants(json.dumps(raw))[0]
        self.assertEqual(v.draft_model, "small")
        self.assertEqual(v.chat_kwargs["num_predict"], 512)

    def test_rejects_missing_required_field(self):
        with self.assertRaises(VariantConfigError):
            load_variants(json.dumps([{"label": "x"}]))  # no base_url/model

    def test_port_for_allowlist(self):
        v = load_variants(json.dumps([{"label": "c",
            "base_url": "http://127.0.0.1:11434", "model": "m"}]))[0]
        self.assertEqual(v.port, 11434)
```

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Implement**

```python
# scripts/brain_bench/variants.py
from __future__ import annotations
import json
from dataclasses import dataclass, field
from urllib.parse import urlparse


class VariantConfigError(ValueError):
    pass


@dataclass(frozen=True)
class Variant:
    label: str
    base_url: str
    model: str
    chat_kwargs: dict = field(default_factory=dict)
    draft_model: str | None = None  # for speculative/MTP pairings

    @property
    def port(self) -> int:
        p = urlparse(self.base_url).port
        if p is None:
            raise VariantConfigError(f"{self.label}: base_url has no port")
        return p


def load_variants(raw_json: str) -> list[Variant]:
    try:
        items = json.loads(raw_json)
    except json.JSONDecodeError as e:
        raise VariantConfigError(f"variant config not valid JSON: {e}") from e
    if not isinstance(items, list) or not items:
        raise VariantConfigError("variant config must be a non-empty list")
    out = []
    seen = set()
    for it in items:
        for req in ("label", "base_url", "model"):
            if req not in it or not it[req]:
                raise VariantConfigError(f"variant missing required field: {req}")
        if it["label"] in seen:
            raise VariantConfigError(f"duplicate variant label: {it['label']}")
        seen.add(it["label"])
        out.append(Variant(
            label=it["label"], base_url=it["base_url"], model=it["model"],
            chat_kwargs=dict(it.get("chat_kwargs", {})),
            draft_model=it.get("draft_model"),
        ))
    return out
```

- [ ] **Step 4: Run → pass. Commit.**

---

## Task 3: Inference measurement (streaming → TTFT / total / tokens-per-sec)

**Files:** Create `scripts/brain_bench/inference.py`; Test `tests/test_brain_bench_inference.py`

- [ ] **Step 1: RED test** — a mock streaming source proves the measurement math without a real model. The function takes an injectable `clock` and `stream_factory` so tests are deterministic.

```python
# tests/test_brain_bench_inference.py
import unittest
from scripts.brain_bench.inference import measure_generation, GenerationMeasurement


class MeasurementTests(unittest.TestCase):
    def test_ttft_and_total_and_tokens_per_sec(self):
        # fake monotonic clock advancing 0.0, 0.5 (first token), 1.0, 2.5 (done)
        ticks = iter([0.0, 0.5, 1.0, 2.5])
        clock = lambda: next(ticks)
        # stream yields 3 token-chunks then ends
        def stream_factory(*, variant, messages):
            return iter([{"content": "April "}, {"content": "27 "}, {"content": "note [E1]"}])
        m = measure_generation(variant=object(), messages=[],
                               clock=clock, stream_factory=stream_factory)
        self.assertIsInstance(m, GenerationMeasurement)
        self.assertEqual(m.answer, "April 27 note [E1]")
        self.assertEqual(m.ttft_ms, 500)        # first token at 0.5 vs start 0.0
        self.assertEqual(m.total_ms, 2500)      # done at 2.5
        self.assertEqual(m.output_tokens, 3)
        self.assertAlmostEqual(m.tokens_per_sec, 3 / 2.5, places=3)

    def test_timeout_marks_incomplete_not_crash(self):
        def boom(*, variant, messages):
            raise TimeoutError("model stalled")
        m = measure_generation(variant=object(), messages=[],
                               clock=lambda: 0.0, stream_factory=boom)
        self.assertTrue(m.failed)
        self.assertEqual(m.answer, "")
```

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Implement** — `measure_generation` consumes the stream, stamps TTFT at the first chunk and total at exhaustion; the real `stream_factory` (a thin wrapper over the ollama/OpenAI-compatible streaming endpoint, `stream=True`) is the production default but is injectable for tests.

```python
# scripts/brain_bench/inference.py
from __future__ import annotations
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class GenerationMeasurement:
    answer: str
    ttft_ms: int | None
    total_ms: int | None
    output_tokens: int
    tokens_per_sec: float | None
    failed: bool = False


def measure_generation(*, variant, messages, clock=time.monotonic,
                       stream_factory=None) -> GenerationMeasurement:
    if stream_factory is None:
        from scripts.brain_bench.inference_backend import ollama_stream
        stream_factory = ollama_stream
    start = clock()
    ttft = None
    parts: list[str] = []
    try:
        for chunk in stream_factory(variant=variant, messages=messages):
            if ttft is None:
                ttft = clock()
            piece = chunk.get("content", "") if isinstance(chunk, dict) else str(chunk)
            if piece:
                parts.append(piece)
        end = clock()
    except Exception:
        return GenerationMeasurement(answer="", ttft_ms=None, total_ms=None,
                                     output_tokens=0, tokens_per_sec=None, failed=True)
    total_s = max(0.0, end - start)
    n = len(parts)
    return GenerationMeasurement(
        answer="".join(parts),
        ttft_ms=int((ttft - start) * 1000) if ttft is not None else None,
        total_ms=int(total_s * 1000),
        output_tokens=n,
        tokens_per_sec=(n / total_s if total_s > 0 else None),
        failed=False,
    )
```

(Token counting: counting stream chunks is a proxy for output tokens — acceptable for a comparative benchmark since the same tokenizer/stream granularity applies per variant; note this assumption in `inference.py`'s docstring. A later refinement can read the endpoint's `eval_count` when present.)

- [ ] **Step 4:** Create `scripts/brain_bench/inference_backend.py` with `ollama_stream(*, variant, messages)` — POSTs to `variant.base_url` with `stream=True`, yields `{"content": <delta>}` per line, applies `variant.chat_kwargs`/`draft_model`. No test asserts the live HTTP (that's the owner-run real call); a thin smoke test asserts it builds the right request dict via a mocked `requests.post`. Commit.

---

## Task 4: Pairwise blind judge

**Files:** Create `scripts/brain_bench/judge.py`; Test `tests/test_brain_bench_judge.py`

- [ ] **Step 1: RED test** — assert blindness (no variant label reaches the judge prompt), seeded order randomization, separate quality/voice, aggregation to win-rate.

```python
# tests/test_brain_bench_judge.py
import unittest
from scripts.brain_bench.judge import judge_pairwise, PairwiseInput


class JudgeBlindnessTests(unittest.TestCase):
    def _fake_judge(self, captured):
        # records every prompt the judge model would see; returns "A" winner
        def _call(prompt: str, *, axis: str) -> str:
            captured.append((axis, prompt))
            return "A"
        return _call

    def test_variant_labels_never_reach_judge_prompt(self):
        captured = []
        inputs = [
            PairwiseInput(variant_label="speculative-secret", probe_id="p1",
                          answer="ans-X", evidence="E1"),
            PairwiseInput(variant_label="current-secret", probe_id="p1",
                          answer="ans-Y", evidence="E1"),
        ]
        judge_pairwise(inputs, call_judge=self._fake_judge(captured), seed=1)
        for _axis, prompt in captured:
            self.assertNotIn("speculative-secret", prompt)
            self.assertNotIn("current-secret", prompt)

    def test_scores_quality_and_voice_separately(self):
        captured = []
        inputs = [
            PairwiseInput("a", "p1", "ans-X", "E1"),
            PairwiseInput("b", "p1", "ans-Y", "E1"),
        ]
        judge_pairwise(inputs, call_judge=self._fake_judge(captured), seed=1)
        axes = {axis for axis, _ in captured}
        self.assertEqual(axes, {"quality", "voice"})

    def test_aggregates_to_per_variant_winrate(self):
        inputs = [PairwiseInput("a", "p1", "X", "E1"),
                  PairwiseInput("b", "p1", "Y", "E1")]
        # judge always picks the FIRST presented; with seed fixed, order is stable
        res = judge_pairwise(inputs, call_judge=lambda p, *, axis: "A", seed=1)
        self.assertIn("a", res.quality_winrate)
        self.assertIn("b", res.quality_winrate)
        self.assertAlmostEqual(
            res.quality_winrate["a"] + res.quality_winrate["b"], 1.0, places=6)
```

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Implement** — for each probe, form all variant pairs; for each pair, present (A,B) in a seeded-random order, build a label-free prompt (`probe_id` + the two answers + evidence, NO variant label), ask the fixed judge per axis, record the winner mapped back to the hidden variant; aggregate to per-variant win-rate per axis.

```python
# scripts/brain_bench/judge.py
from __future__ import annotations
import itertools
import random
from collections import defaultdict
from dataclasses import dataclass, field


@dataclass(frozen=True)
class PairwiseInput:
    variant_label: str
    probe_id: str
    answer: str
    evidence: str


@dataclass
class JudgeResult:
    quality_winrate: dict = field(default_factory=dict)
    voice_winrate: dict = field(default_factory=dict)


def _prompt(probe_id, first_answer, second_answer, evidence, axis) -> str:
    # NO variant labels — only the hidden A/B answers + evidence.
    return (
        f"Probe {probe_id}. Evidence:\n{evidence}\n\n"
        f"Answer A:\n{first_answer}\n\nAnswer B:\n{second_answer}\n\n"
        f"Which answer is better on {axis}? Reply exactly 'A' or 'B'."
    )


def judge_pairwise(inputs, *, call_judge, seed: int) -> JudgeResult:
    rng = random.Random(seed)
    by_probe = defaultdict(list)
    for it in inputs:
        by_probe[it.probe_id].append(it)

    wins = {"quality": defaultdict(int), "voice": defaultdict(int)}
    games = {"quality": defaultdict(int), "voice": defaultdict(int)}

    for _probe_id, group in by_probe.items():
        for a, b in itertools.combinations(group, 2):
            for axis in ("quality", "voice"):
                swap = rng.random() < 0.5
                first, second = (b, a) if swap else (a, b)
                verdict = call_judge(
                    _prompt(a.probe_id, first.answer, second.answer, a.evidence, axis),
                    axis=axis,
                )
                winner = first if verdict.strip().upper() == "A" else second
                wins[axis][winner.variant_label] += 1
                games[axis][a.variant_label] += 1
                games[axis][b.variant_label] += 1

    def winrate(axis):
        return {label: (wins[axis][label] / games[axis][label])
                for label in games[axis] if games[axis][label]}

    return JudgeResult(quality_winrate=winrate("quality"),
                       voice_winrate=winrate("voice"))
```

The production `call_judge` wraps the fixed `MAEZ_JUDGE_MODEL` with pinned settings (temperature/seed). Commit.

---

## Task 5: Gates + lexicographic ranking + ops rubric

**Files:** Create `scripts/brain_bench/gates.py`; Test `tests/test_brain_bench_gates.py`

- [ ] **Step 1: RED test** — hard-fail beats fast; over-ceiling fails; lexicographic order; ops tiebreak.

```python
# tests/test_brain_bench_gates.py
import unittest
from scripts.brain_bench.gates import (
    ANSWER_CEILING_MS, STRONG_MS, EXCELLENT_BAND_MS, SCREEN_K, FINALIST_K,
    hard_gate_fail_reasons, latency_passes, rank_variants, VariantScore,
)


class GateConstantsTests(unittest.TestCase):
    def test_frozen_constants(self):
        self.assertEqual(ANSWER_CEILING_MS, 12000)
        self.assertEqual(STRONG_MS, 8000)
        self.assertEqual(EXCELLENT_BAND_MS, (4000, 6000))
        self.assertEqual(SCREEN_K, 3)
        self.assertEqual(FINALIST_K, 7)


class HardGateTests(unittest.TestCase):
    def test_false_absence_is_hard_fail(self):
        reasons = hard_gate_fail_reasons(
            false_absence=True, grounding=1.0, wrong_absence=False, voice_lint_ok=True)
        self.assertIn("false_absence", reasons)

    def test_clean_variant_has_no_reasons(self):
        self.assertEqual(hard_gate_fail_reasons(
            false_absence=False, grounding=1.0, wrong_absence=False,
            voice_lint_ok=True), [])

    def test_latency_over_ceiling_fails(self):
        self.assertFalse(latency_passes(p95_ms=12001))
        self.assertTrue(latency_passes(p95_ms=11999))


class RankingTests(unittest.TestCase):
    def test_dishonest_fast_loses_to_honest_slow(self):
        dishonest_fast = VariantScore(
            label="fast", hard_pass=False, p95_ms=3000, quality_winrate=0.9,
            voice_winrate=0.9, tokens_per_sec=50, ops_cost=1)
        honest_slow = VariantScore(
            label="slow", hard_pass=True, p95_ms=11000, quality_winrate=0.6,
            voice_winrate=0.6, tokens_per_sec=10, ops_cost=2)
        ranked = rank_variants([dishonest_fast, honest_slow])
        self.assertEqual(ranked[0].label, "slow")  # honesty first

    def test_among_honest_voice_quality_beats_raw_speed(self):
        a = VariantScore("a", True, 9000, 0.9, 0.9, 20, 1)
        b = VariantScore("b", True, 5000, 0.5, 0.5, 40, 1)  # faster, worse voice
        ranked = rank_variants([a, b])
        self.assertEqual(ranked[0].label, "a")

    def test_ops_breaks_ties_among_equal_honesty_quality_latency(self):
        a = VariantScore("a", True, 8000, 0.8, 0.8, 20, ops_cost=5)
        b = VariantScore("b", True, 8000, 0.8, 0.8, 20, ops_cost=1)
        ranked = rank_variants([a, b])
        self.assertEqual(ranked[0].label, "b")  # lighter ops wins the tie
```

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Implement** — frozen constants + a lexicographic sort key. Latency contributes as a coarse band (excellent/strong/under-ceiling) so a small speed delta doesn't outrank a real voice/quality delta; raw speed only breaks ties within a band.

```python
# scripts/brain_bench/gates.py
from __future__ import annotations
from dataclasses import dataclass

ANSWER_CEILING_MS = 12000
STRONG_MS = 8000
EXCELLENT_BAND_MS = (4000, 6000)
SCREEN_K = 3
FINALIST_K = 7

GROUNDING_BAR = 0.99  # inherit the 2a/A5 bar — do NOT relax. Confirm exact
                      # value against scripts/recall_flip_eval probe assertions
                      # at implementation time; pin to that constant, not a guess.


def hard_gate_fail_reasons(*, false_absence, grounding, wrong_absence,
                           voice_lint_ok) -> list[str]:
    reasons = []
    if false_absence:
        reasons.append("false_absence")
    if grounding < GROUNDING_BAR:
        reasons.append("grounding_below_bar")
    if wrong_absence:
        reasons.append("wrong_absence")
    if not voice_lint_ok:
        reasons.append("voice_lint")
    return reasons


def latency_passes(*, p95_ms: int) -> bool:
    return p95_ms <= ANSWER_CEILING_MS


def _latency_band(p95_ms: int) -> int:
    # higher = better. 3=excellent, 2=strong, 1=under-ceiling, 0=fail
    if p95_ms <= EXCELLENT_BAND_MS[1]:
        return 3
    if p95_ms < STRONG_MS:
        return 2
    if p95_ms <= ANSWER_CEILING_MS:
        return 1
    return 0


@dataclass(frozen=True)
class VariantScore:
    label: str
    hard_pass: bool
    p95_ms: int
    quality_winrate: float
    voice_winrate: float
    tokens_per_sec: float
    ops_cost: int  # lower = simpler


def _sort_key(v: VariantScore):
    # lexicographic, all descending-good:
    # 1 honesty  2 voice+quality  3 latency band  4 raw speed  5 ops (lower better)
    return (
        1 if v.hard_pass else 0,
        round(v.voice_winrate + v.quality_winrate, 6),
        _latency_band(v.p95_ms) if v.hard_pass else 0,
        v.tokens_per_sec,
        -v.ops_cost,
    )


def rank_variants(scores: list[VariantScore]) -> list[VariantScore]:
    return sorted(scores, key=_sort_key, reverse=True)
```

- [ ] **Step 4: Run → pass.** At implementation time, open `scripts/recall_flip_eval/probes.py` `assert_probe_result` and pin `GROUNDING_BAR` to the exact value 2a uses (do not leave the 0.99 guess). Commit.

---

## Task 6: BenchPacket (bench_packet.v1, closed enums, content-free)

**Files:** Create `scripts/brain_bench/bench_packet.py`; Test `tests/test_brain_bench_packet.py`

- [ ] **Step 1: RED test** — content-free (no answer/evidence text fields), closed fail_reason + recommendation enums.

```python
# tests/test_brain_bench_packet.py
import dataclasses
import json
import unittest
from scripts.brain_bench.bench_packet import (
    BenchPacket, VariantReport, Recommendation, FailReason, OpsRubric,
)


class PacketContentFreeTests(unittest.TestCase):
    def test_no_text_content_fields(self):
        names = {f.name for f in dataclasses.fields(VariantReport)}
        for forbidden in ("answer", "text", "evidence", "prompt", "snippet",
                          "reply", "probe_text"):
            self.assertNotIn(forbidden, names)

    def test_fail_reasons_are_closed_codes(self):
        for r in FailReason:
            self.assertIsInstance(r.value, str)
        # constructing with a non-enum reason must fail
        with self.assertRaises(ValueError):
            VariantReport.build(label="x", hard_pass=False,
                                fail_reasons=["totally free text reason"],
                                p95_ms=9000, recommendation=None)

    def test_recommendation_is_closed_enum(self):
        self.assertEqual(
            {r.value for r in Recommendation},
            {"go_2b_rerun", "not_yet_too_slow", "not_yet_dishonest",
             "not_yet_voice_loss"})

    def test_packet_serializes_to_json_without_text(self):
        vr = VariantReport.build(label="current", hard_pass=True,
                                 fail_reasons=[], p95_ms=9000,
                                 recommendation=Recommendation.GO_2B_RERUN)
        pkt = BenchPacket(schema_version="bench_packet.v1",
                          fixture_manifest_hash="abc", variants=(vr,),
                          recommendation=Recommendation.GO_2B_RERUN)
        blob = json.dumps(pkt.to_dict())
        self.assertNotIn("answer", blob)
        self.assertIn("bench_packet.v1", blob)
```

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Implement** — enums + `VariantReport.build` validating `fail_reasons` against `FailReason`; `to_dict` emits enum `.value`s only.

```python
# scripts/brain_bench/bench_packet.py
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from enum import Enum


class FailReason(Enum):
    FALSE_ABSENCE = "false_absence"
    GROUNDING_BELOW_BAR = "grounding_below_bar"
    WRONG_ABSENCE = "wrong_absence"
    VOICE_LINT = "voice_lint"
    OVER_ANSWER_CEILING = "over_answer_ceiling"


class Recommendation(Enum):
    GO_2B_RERUN = "go_2b_rerun"
    NOT_YET_TOO_SLOW = "not_yet_too_slow"
    NOT_YET_DISHONEST = "not_yet_dishonest"
    NOT_YET_VOICE_LOSS = "not_yet_voice_loss"


@dataclass(frozen=True)
class OpsRubric:
    mem_footprint: int       # closed small scale, e.g. 0-3
    launch_flags: int
    separate_server: bool
    speculative_setup: int
    crash_retry: int
    non_disturbance: bool


@dataclass(frozen=True)
class VariantReport:
    label: str
    hard_pass: bool
    fail_reasons: tuple[str, ...]
    p95_ms: int
    p50_ms: int | None = None
    p90_ms: int | None = None
    max_ms: int | None = None
    variance_ms2: float | None = None
    tail_flags: int = 0
    ttft_ms: int | None = None
    tokens_per_sec: float | None = None
    quality_winrate: float | None = None
    voice_winrate: float | None = None
    quality_per_second: float | None = None
    ops: OpsRubric | None = None
    recommendation: str | None = None

    @staticmethod
    def build(*, label, hard_pass, fail_reasons, p95_ms, recommendation,
              **kw) -> "VariantReport":
        codes = []
        for r in fail_reasons:
            codes.append(r.value if isinstance(r, FailReason) else FailReason(r).value)
        rec = (recommendation.value if isinstance(recommendation, Recommendation)
               else (Recommendation(recommendation).value if recommendation else None))
        return VariantReport(label=label, hard_pass=hard_pass,
                             fail_reasons=tuple(codes), p95_ms=p95_ms,
                             recommendation=rec, **kw)


@dataclass(frozen=True)
class BenchPacket:
    schema_version: str
    fixture_manifest_hash: str
    variants: tuple[VariantReport, ...]
    recommendation: Recommendation

    def to_dict(self) -> dict:
        d = asdict(self)
        d["recommendation"] = self.recommendation.value
        return d
```

- [ ] **Step 4: Run → pass. Commit.**

---

## Task 7: Two-stage orchestrator + launcher

**Files:** Create `scripts/brain_bench/bench.py`, `scripts/brain_bench/launcher.py`; Test `tests/test_brain_bench_orchestration.py`

- [ ] **Step 1: RED test** — screening uses SCREEN_K, finalists use FINALIST_K, a deliberately dishonest stub variant is eliminated, tail flagged, and the end-to-end packet is content-free. Inject the inference + judge via parameters so no real model runs.

```python
# tests/test_brain_bench_orchestration.py
import json
import unittest
from scripts.brain_bench.bench import run_benchmark
from scripts.brain_bench.bench_packet import BenchPacket


class OrchestrationTests(unittest.TestCase):
    def _variants(self):
        return json.dumps([
            {"label": "honest", "base_url": "http://127.0.0.1:11434", "model": "a"},
            {"label": "dishonest", "base_url": "http://127.0.0.1:11434", "model": "b"},
        ])

    def test_dishonest_variant_eliminated_and_packet_content_free(self):
        # fake_run returns honest grounded answers for 'honest', a fabricated
        # false-absence for 'dishonest'
        def fake_probe_run(variant, probe, k):
            if variant.label == "dishonest":
                return {"false_absence": True, "grounding": 0.0,
                        "wrong_absence": True, "voice_lint_ok": False,
                        "latencies_ms": [3000] * k, "answer": "made up"}
            return {"false_absence": False, "grounding": 1.0,
                    "wrong_absence": False, "voice_lint_ok": True,
                    "latencies_ms": [9000] * k, "answer": "April 27 [E1]"}
        pkt = run_benchmark(self._variants(),
                            probe_run=fake_probe_run,
                            judge=lambda inputs: None)  # judge stub
        self.assertIsInstance(pkt, BenchPacket)
        labels = {v.label: v for v in pkt.variants}
        self.assertFalse(labels["dishonest"].hard_pass)
        self.assertIn("false_absence", labels["dishonest"].fail_reasons)
        self.assertTrue(labels["honest"].hard_pass)
        # content-free end to end
        self.assertNotIn("made up", json.dumps(pkt.to_dict()))
        self.assertNotIn("April 27", json.dumps(pkt.to_dict()))

    def test_tail_run_is_flagged_not_averaged(self):
        def fake_probe_run(variant, probe, k):
            lat = [5000] * (k - 1) + [21000]  # one 21s stall
            return {"false_absence": False, "grounding": 1.0,
                    "wrong_absence": False, "voice_lint_ok": True,
                    "latencies_ms": lat, "answer": "ok [E1]"}
        pkt = run_benchmark(json.dumps([
            {"label": "tail", "base_url": "http://127.0.0.1:11434", "model": "a"}]),
            probe_run=fake_probe_run, judge=lambda inputs: None)
        v = pkt.variants[0]
        self.assertGreaterEqual(v.tail_flags, 1)
```

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Implement** `run_benchmark` — load variants; **screening** (`SCREEN_K`) over the full battery → drop any with hard-gate fails or p95 over ceiling; **finalists** (`FINALIST_K`) over survivors (top 2–3); compute p50/p90/p95/max/variance, flag tail runs (e.g. any run > 2× the variant's p50 OR > ANSWER_CEILING_MS as `tail_flags`); run the blind judge across finalists; score + `rank_variants`; pick `recommendation` (closed enum: `go_2b_rerun` if a finalist passes hard+latency, else the dominant blocker → `not_yet_too_slow`/`not_yet_dishonest`/`not_yet_voice_loss`); build `BenchPacket`. The real `probe_run` runs under `sandbox.assert_sandbox` + `no_egress(allow_loopback_ports=(variant.port,))` and uses `measure_generation`; tests inject a fake `probe_run` so the orchestration is provable without a model.

- [ ] **Step 4:** Create `launcher.py` mirroring 2a (set `MAEZ_HOME/DATA/CONFIG/CACHE/OWNER_TIMEZONE`, then `os.execv` into `scripts.brain_bench.bench`). The real run is owner-operated (like 2b); the launcher establishes the sandbox before any maez import.

- [ ] **Step 5: Run → pass. Commit.**

---

## Task 8: gitignore, lint, regression

- [ ] **Step 1:** Add the debug-dump dir to `.gitignore` (e.g. `scripts/brain_bench/_debug_dumps/` or a sandbox-tmp path) so raw answers never get committed. Test: assert the orchestrator's debug-dump path matches a gitignored pattern (string assertion).
- [ ] **Step 2:** Ruff on all new files + the modified `sandbox.py`.
- [ ] **Step 3:** Full targeted run: `.venv/bin/python -m unittest tests.test_brain_bench_sandbox tests.test_brain_bench_variants tests.test_brain_bench_inference tests.test_brain_bench_judge tests.test_brain_bench_gates tests.test_brain_bench_packet tests.test_brain_bench_orchestration -v` → green. Re-run the **2a** suite to prove it's unchanged by the `no_egress` parameterization.
- [ ] **Step 4: Commit** (scoped staging; NOT `git add -A`).

---

## Self-Review

**1. Spec coverage:** Approach B sibling reusing 2a sandbox/probes ✓ (Task 1 imports/extends, 2a frozen). Parameterized socket allowlist as Task 1 ✓ (Rohit's load-bearing note). Pluggable model-agnostic variant registry ✓ (Task 2). TTFT/total/tokens-per-sec streaming measurement ✓ (Task 3). Pairwise blind judge, labels hidden + seeded order + quality/voice separate ✓ (Task 4). Frozen constants + hard gates + latency ceiling + lexicographic ranking + ops rubric ✓ (Task 5). Content-free closed-enum BenchPacket ✓ (Task 6). Two-stage screen/finalist + tail-flagging + negative-control + owner-run launcher ✓ (Task 7). Gitignored debug dump ✓ (Task 8). Hermetic + send-path-free asserted ✓ (Tasks 1,7).

**2. Placeholder scan:** Two values are explicitly deferred-with-instruction, not placeholders: `GROUNDING_BAR` (pin to 2a's exact constant at impl time — Task 5 Step 4) and the token-count proxy (chunk-count, documented assumption — Task 3). The real inference HTTP and the live run are owner-operated, mirroring 2a/2b; tests prove the harness logic via injection. No "TODO/handle appropriately" left.

**3. Symbol consistency:** `Variant`/`.port`, `measure_generation`/`GenerationMeasurement`, `PairwiseInput`/`JudgeResult`/`judge_pairwise`, `VariantScore`/`rank_variants`/`hard_gate_fail_reasons`/`latency_passes`, `FailReason`/`Recommendation`/`VariantReport.build`/`BenchPacket`, `run_benchmark`, `no_egress(allow_loopback_ports=...)` used identically across tasks. Frozen constants (12000/8000/(4000,6000)/3/7) match the spec.

**4. Ordering:** isolation (1) → variants (2) → inference (3) → judge (4) → gates (5) → packet (6) → orchestrator (7) → gitignore/lint/regression (8). Load-bearing isolation first; each task independently committable; nothing references a symbol defined later.

## Execution note
Task 1 is the gate everything else stands on. Codex's six-agent pass should pressure the egress allowlist FIRST: can any code path reach a non-loopback host or a non-allowed port; does `getaddrinfo`/`connect`/`connect_ex`/`create_connection`/`sendto` all stay guarded; does the 2a block-all default survive byte-for-byte. If the allowlist leaks, the benchmark is invalid no matter how clean the scoring. Second pressure point: the negative-control (Task 7) — a deliberately dishonest variant MUST fail the hard gates and MUST NOT leak its fabricated text into the packet.
