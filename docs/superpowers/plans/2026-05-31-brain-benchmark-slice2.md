# Brain Benchmark (Slice 2) Implementation Plan — v2

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A hermetic, send-path-free benchmark that runs real local model variants over the recall battery and emits a content-free, **producer-evidence** `BenchPacket` reporting whether each variant *passes the recall-benchmark screen* (honest + fast + voice/quality) — owner decides, packet never certifies identity or authorizes the flip.

**Architecture:** New sibling package `scripts/brain_bench/` reusing `scripts/recall_flip_eval/{sandbox,probes}` by import (2a frozen). One shared change: `no_egress(allow_loopback_ports=())` — default preserves 2a's block-all. Pluggable localhost-validated variant registry; streaming inference measurement; pairwise counterbalanced blind judge; two-tier gates (categorical honesty, A7 latency) with lexicographic ranking; content-free closed-enum BenchPacket.

**Tech Stack:** Python 3 stdlib; `unittest` via `.venv/bin/python -m unittest` (pytest NOT installed). Real inference via localhost endpoint; tests mock it.

**Spec:** [docs/superpowers/specs/2026-05-31-brain-benchmark-design.md](../specs/2026-05-31-brain-benchmark-design.md) (v2). **v2 folds the 9-role pre-code panel's blockers — implement THIS, not v1.**

**Discipline reminders (the 9 folds):**
1. **Task 1 = load-bearing.** All five socket APIs guarded; `sendto` always blocked; `getaddrinfo` loopback-only; import-guard. Prove before any variant/judge logic.
2. Variant **and** judge endpoints validated localhost-only **at config load** (reject https/userinfo/query/fragment/non-loopback/missing-port).
3. Grounding is **categorical** (reuse 2a `assert_probe_result → unsafe==False` + grounded `RecallOutcome`). **No numeric bar — do not invent `0.99`.**
4. Judge: sanitized `BlindAnswer`, **counterbalanced A/B + B/A**, closed `A/B/TIE/INVALID`, repetition-aware, voice & quality separate (quality can't mask voice loss).
5. Streaming: **TTFT = first non-empty answer content**; benchmark-only `chat_fn` adapter; canonical endpoint shape; **closed failure codes** not exception text.
6. `BenchPacket` content-free enforced in **`__post_init__`** + recursive content-field rejection; gates return enum values; negative-control sentinel must not appear in packet JSON.
7. Stats admit small-k: report `sample_n` + method; **fail on `max_ms > ceiling`** too, not just p95; hard-over-ceiling distinct from advisory tail.
8. Ops rubric from **closed evidence fields**, never a caller-supplied score.
9. **Covenant wording:** no "still Maez"/`go_2b_rerun`; use `screen_result` enum; carry `artifact_role=producer_evidence_not_verdict`, `owner_verdict_required=true`, `requires_s5_voice_continuity_gate=true`.

Frozen constants: `answer_ceiling_ms=12000`, `strong_ms=8000`, `excellent_band_ms=(4000,6000)`, `screen_k=3`, `finalist_k=7`. Model-agnostic (no hardcoded names). Genderless throughout. 2a stays byte-behaviorally unchanged.

---

## File Structure
- **Modify** `scripts/recall_flip_eval/sandbox.py` — `no_egress(allow_loopback_ports=())`, all 5 APIs.
- **Create** `scripts/brain_bench/{__init__,variants,inference,inference_backend,judge,gates,bench_packet,bench,launcher}.py`
- **Create** tests `tests/test_brain_bench_{sandbox,variants,inference,judge,gates,packet,orchestration}.py`
- **Modify** `.gitignore` — debug-dump dir.

---

## Task 1: Egress guard — all 5 socket APIs + loopback allowlist + import-guard (LOAD-BEARING)

**Files:** Modify `scripts/recall_flip_eval/sandbox.py`; Test `tests/test_brain_bench_sandbox.py`

- [ ] **Step 1: RED test** — every API, both directions, 2a default preserved:

```python
# tests/test_brain_bench_sandbox.py
import socket
import unittest
from scripts.recall_flip_eval.sandbox import no_egress, EgressBlockedError


class EgressAllowlistTests(unittest.TestCase):
    def test_default_blocks_all_including_loopback(self):
        with no_egress():  # 2a behavior: empty allowlist blocks everything
            for target in (("127.0.0.1", 11434), ("8.8.8.8", 53)):
                with self.assertRaises(EgressBlockedError):
                    socket.create_connection(target)

    def test_create_connection_and_raw_connect_and_connect_ex(self):
        with no_egress(allow_loopback_ports=(11434,)):
            # external blocked on all three
            with self.assertRaises(EgressBlockedError):
                socket.create_connection(("8.8.8.8", 53))
            s = socket.socket()
            with self.assertRaises(EgressBlockedError):
                s.connect(("8.8.8.8", 53))
            with self.assertRaises(EgressBlockedError):
                s.connect_ex(("8.8.8.8", 53))
            s.close()
            # loopback allowed port passes the guard (refused/timeout is fine)
            try:
                socket.create_connection(("127.0.0.1", 11434), timeout=0.01)
            except EgressBlockedError:
                self.fail("allowed loopback port blocked")
            except OSError:
                pass

    def test_loopback_non_allowed_port_blocked(self):
        with no_egress(allow_loopback_ports=(11434,)):
            with self.assertRaises(EgressBlockedError):
                socket.create_connection(("127.0.0.1", 22))

    def test_sendto_always_blocked_even_with_allowlist(self):
        with no_egress(allow_loopback_ports=(11434,)):
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            with self.assertRaises(EgressBlockedError):
                s.sendto(b"x", ("127.0.0.1", 11434))
            s.close()

    def test_getaddrinfo_returns_only_loopback_for_allowed_port(self):
        with no_egress(allow_loopback_ports=(11434,)):
            infos = socket.getaddrinfo("127.0.0.1", 11434)
            for fam, _t, _p, _c, sockaddr in infos:
                self.assertIn(sockaddr[0], {"127.0.0.1", "::1"})
            with self.assertRaises(EgressBlockedError):
                socket.getaddrinfo("example.com", 11434)
            with self.assertRaises(EgressBlockedError):
                socket.getaddrinfo("127.0.0.1", 22)
```

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Implement** the guard per the spec §4.2 (loopback host set; `create_connection`/`connect`/`connect_ex` allow loopback:allowed-port else `EgressBlockedError`; `sendto` always raises; `getaddrinfo` returns original only for loopback host + allowed port, else raises). Use the code in the spec's companion (the v1 plan's Task-1 body) but add the `sendto`-always-block and `getaddrinfo` loopback-only branches exactly as the tests demand. Restore all five originals in `finally`.

- [ ] **Step 4: Import-guard test** — assert that brain_bench's launcher sets sandbox env + patches paths **before** importing maez modules (mirror 2a's `assert_sandbox` discipline). Add a test that, given a temp root, `assert_sandbox(root)` holds after the brain_bench setup helper runs.

- [ ] **Step 5: Run → pass. Re-run 2a's REAL suite to prove block-all unchanged:**
`.venv/bin/python -m unittest tests.test_recall_flip_eval_isolation tests.test_recall_flip_eval_packet tests.test_recall_flip_eval_probes -v` → expect `35 OK`. **Commit.**

---

## Task 2: Variant registry + localhost-only endpoint validation (variants AND judge)

**Files:** Create `scripts/brain_bench/variants.py`, `__init__.py`; Test `tests/test_brain_bench_variants.py`

- [ ] **Step 1: RED test** — validation rejects every sneaky URL; judge endpoint uses the same validator.

```python
# tests/test_brain_bench_variants.py
import json, unittest
from scripts.brain_bench.variants import (
    load_variants, validate_endpoint, Variant, VariantConfigError)


class EndpointValidationTests(unittest.TestCase):
    def test_accepts_loopback_http_with_port(self):
        self.assertEqual(validate_endpoint("http://127.0.0.1:11434"), 11434)
        self.assertEqual(validate_endpoint("http://localhost:8080"), 8080)

    def test_rejects(self):
        for bad in ("https://127.0.0.1:11434",          # https
                    "http://127.0.0.1",                  # no port
                    "http://u:p@127.0.0.1:11434",        # userinfo
                    "http://127.0.0.1:11434/?x=1",       # query
                    "http://127.0.0.1:11434/#f",         # fragment
                    "http://10.0.0.5:11434",             # private LAN
                    "http://example.com:11434"):         # non-loopback
            with self.assertRaises(VariantConfigError, msg=bad):
                validate_endpoint(bad)


class RegistryTests(unittest.TestCase):
    def test_loads_and_exposes_port(self):
        v = load_variants(json.dumps([{"label": "c",
            "base_url": "http://127.0.0.1:11434", "model": "m"}]))[0]
        self.assertEqual(v.port, 11434)
        self.assertEqual(v.chat_kwargs, {})
    def test_rejects_missing_required(self):
        with self.assertRaises(VariantConfigError):
            load_variants(json.dumps([{"label": "x"}]))
    def test_rejects_non_loopback_variant(self):
        with self.assertRaises(VariantConfigError):
            load_variants(json.dumps([{"label": "x",
                "base_url": "http://10.0.0.5:11434", "model": "m"}]))
```

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Implement** — `validate_endpoint(url) -> int` (urlparse; assert scheme=="http", host in loopback set, `.port` not None, no `username`/`password`, empty `query`/`fragment`; return port else raise `VariantConfigError`). `Variant` dataclass with `.port` computed via `validate_endpoint(self.base_url)`. `load_variants(raw_json)` parses, enforces required `{label,base_url,model}`, unique labels, calls `validate_endpoint` on each `base_url`. Export the validator so the judge config reuses it.

- [ ] **Step 4: Run → pass. Commit.**

---

## Task 3: Streaming inference measurement — TTFT=first content, closed failure codes

**Files:** Create `scripts/brain_bench/inference.py`, `inference_backend.py`; Test `tests/test_brain_bench_inference.py`

- [ ] **Step 1: RED test** — TTFT pinned to first **non-empty** content (empty/role/keepalive frames don't count); failures map to closed codes.

```python
# tests/test_brain_bench_inference.py
import unittest
from scripts.brain_bench.inference import measure_generation, FailCode


class MeasurementTests(unittest.TestCase):
    def test_ttft_is_first_nonempty_content_not_first_frame(self):
        # frames: empty role frame @0.3, keepalive @0.4, first content @0.8, done @2.0
        ticks = iter([0.0, 0.3, 0.4, 0.8, 1.2, 2.0])
        clock = lambda: next(ticks)
        def stream_factory(*, variant, messages):
            return iter([{"content": ""}, {"content": ""},
                         {"content": "April "}, {"content": "27 [E1]"}])
        m = measure_generation(variant=object(), messages=[],
                               clock=clock, stream_factory=stream_factory)
        self.assertEqual(m.answer, "April 27 [E1]")
        self.assertEqual(m.ttft_ms, 800)     # first NON-EMPTY content @0.8
        self.assertEqual(m.total_ms, 2000)
        self.assertEqual(m.output_tokens, 2) # 2 non-empty chunks
        self.assertFalse(m.failed)

    def test_timeout_maps_to_closed_code(self):
        def boom(*, variant, messages):
            raise TimeoutError()
        m = measure_generation(variant=object(), messages=[],
                               clock=lambda: 0.0, stream_factory=boom)
        self.assertTrue(m.failed)
        self.assertEqual(m.fail_code, FailCode.TIMEOUT.value)
        self.assertEqual(m.answer, "")

    def test_empty_output_is_closed_code(self):
        m = measure_generation(variant=object(), messages=[],
                               clock=iter([0.0, 1.0]).__next__,
                               stream_factory=lambda **k: iter([{"content": ""}]))
        self.assertTrue(m.failed)
        self.assertEqual(m.fail_code, FailCode.EMPTY.value)
```

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Implement** — `FailCode(Enum)` = `TIMEOUT/REFUSED/BAD_SHAPE/EMPTY`; `GenerationMeasurement` adds `fail_code: str | None`. `measure_generation` stamps `ttft` at the first chunk whose `content` is non-empty; counts non-empty chunks as `output_tokens`; on `TimeoutError`→TIMEOUT, `ConnectionError/OSError`→REFUSED, parse error→BAD_SHAPE; if it completes with zero non-empty content → `failed=True, fail_code=EMPTY`. No raw exception text stored.

- [ ] **Step 4:** `inference_backend.py` — `ollama_stream(*, variant, messages)` POSTs `stream=True` to `variant.base_url` (canonical shape: `{model, messages, stream, options:{**chat_kwargs}}`, draft_model wired if present), yields `{"content": delta}` per decoded line. A smoke test mocks `requests.post` and asserts the request dict shape (no live HTTP). Commit.

---

## Task 4: Pairwise counterbalanced blind judge

**Files:** Create `scripts/brain_bench/judge.py`; Test `tests/test_brain_bench_judge.py`

- [ ] **Step 1: RED test** — BlindAnswer strips labels; both A/B and B/A issued; TIE/INVALID handled; voice+quality separate.

```python
# tests/test_brain_bench_judge.py
import unittest
from scripts.brain_bench.judge import judge_pairwise, BlindAnswer, PairwiseInput


class JudgeTests(unittest.TestCase):
    def _recorder(self, captured, verdict="A"):
        def _call(prompt, *, axis):
            captured.append((axis, prompt))
            return verdict
        return _call

    def test_no_label_reaches_prompt(self):
        cap = []
        inputs = [PairwiseInput("speculative-SECRET", "p1", "ansX", "E1"),
                  PairwiseInput("current-SECRET", "p1", "ansY", "E1")]
        judge_pairwise(inputs, call_judge=self._recorder(cap), seed=1)
        for _axis, prompt in cap:
            self.assertNotIn("SECRET", prompt)

    def test_counterbalanced_both_orders_issued(self):
        cap = []
        inputs = [PairwiseInput("a", "p1", "ans-AAA", "E1"),
                  PairwiseInput("b", "p1", "ans-BBB", "E1")]
        judge_pairwise(inputs, call_judge=self._recorder(cap), seed=1)
        # per axis, the same pair is presented twice with swapped positions
        quality_prompts = [p for ax, p in cap if ax == "quality"]
        self.assertEqual(len(quality_prompts), 2)
        first_positions = [p.index("ans-AAA") < p.index("ans-BBB")
                           for p in quality_prompts]
        self.assertEqual(set(first_positions), {True, False})  # both orders

    def test_tie_and_invalid_score_no_win(self):
        inputs = [PairwiseInput("a", "p1", "X", "E1"),
                  PairwiseInput("b", "p1", "Y", "E1")]
        res = judge_pairwise(inputs, call_judge=lambda p, *, axis: "TIE", seed=1)
        self.assertEqual(res.quality_winrate.get("a", 0.0), 0.0)
        self.assertEqual(res.quality_winrate.get("b", 0.0), 0.0)

    def test_voice_and_quality_independent(self):
        cap = []
        inputs = [PairwiseInput("a", "p1", "X", "E1"),
                  PairwiseInput("b", "p1", "Y", "E1")]
        judge_pairwise(inputs, call_judge=self._recorder(cap), seed=1)
        self.assertEqual({ax for ax, _ in cap}, {"quality", "voice"})
```

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Implement** — `BlindAnswer` is the only thing the prompt builder may read (`probe_id, answer, evidence` — no label field exists on it). `judge_pairwise`: per probe, per pair, per axis, issue **two** calls (A-first and B-first); map closed verdict `A/B/TIE/INVALID` → win for the variant in that position (TIE/INVALID = no win, both count as games); aggregate per-variant win-rate per axis. The internal pair construction copies `variant_label` only into the result mapping, never into the `BlindAnswer`/prompt. Repetition-aware: group the k reps of a probe before pairing. Production `call_judge` wraps the validated, pinned `MAEZ_JUDGE_MODEL`.

- [ ] **Step 4: Run → pass. Commit.**

---

## Task 5: Gates (categorical honesty + A7 latency) + ranking + ops-from-evidence

**Files:** Create `scripts/brain_bench/gates.py`; Test `tests/test_brain_bench_gates.py`

- [ ] **Step 1: RED test**

```python
# tests/test_brain_bench_gates.py
import unittest
from scripts.brain_bench.gates import (
    ANSWER_CEILING_MS, STRONG_MS, EXCELLENT_BAND_MS, SCREEN_K, FINALIST_K,
    hard_gate_fail_reasons, latency_fail, rank_variants, ops_cost, VariantScore)
from scripts.brain_bench.bench_packet import FailReason


class ConstTests(unittest.TestCase):
    def test_frozen(self):
        self.assertEqual((ANSWER_CEILING_MS, STRONG_MS, EXCELLENT_BAND_MS,
                          SCREEN_K, FINALIST_K), (12000, 8000, (4000, 6000), 3, 7))


class HardGateTests(unittest.TestCase):
    def test_grounding_is_categorical_not_numeric(self):
        # input is a bool from 2a's assert_probe_result, NOT a float
        self.assertIn(FailReason.GROUNDING_NOT_CATEGORICAL.value,
            hard_gate_fail_reasons(false_absence=False, grounded_categorical=False,
                                   wrong_absence=False, voice_lint_ok=True))
        self.assertEqual(
            hard_gate_fail_reasons(false_absence=False, grounded_categorical=True,
                                   wrong_absence=False, voice_lint_ok=True), [])

    def test_latency_fails_on_p95_or_max_over_ceiling(self):
        self.assertTrue(latency_fail(p95_ms=11000, max_ms=12001))   # max over
        self.assertTrue(latency_fail(p95_ms=12001, max_ms=12001))   # p95 over
        self.assertFalse(latency_fail(p95_ms=9000, max_ms=11000))


class RankingTests(unittest.TestCase):
    def test_honesty_first(self):
        fast_bad = VariantScore("fast", False, 3000, 0.9, 0.9, 50, 1)
        slow_ok = VariantScore("slow", True, 11000, 0.6, 0.6, 10, 2)
        self.assertEqual(rank_variants([fast_bad, slow_ok])[0].label, "slow")

    def test_voice_not_masked_by_quality(self):
        # a: great quality, poor voice; b: balanced — b should not lose on voice
        a = VariantScore("a", True, 8000, 0.95, 0.30, 20, 1)
        b = VariantScore("b", True, 8000, 0.70, 0.70, 20, 1)
        self.assertEqual(rank_variants([a, b])[0].label, "b")  # min(voice,quality) leads

    def test_ops_breaks_band_ties(self):
        a = VariantScore("a", True, 8000, 0.8, 0.8, 20, ops_cost_value=5)
        b = VariantScore("b", True, 8000, 0.8, 0.8, 20, ops_cost_value=1)
        self.assertEqual(rank_variants([a, b])[0].label, "b")


class OpsTests(unittest.TestCase):
    def test_ops_cost_derived_from_closed_fields(self):
        light = ops_cost(separate_server=False, live_daemon_disturbance=False,
                         speculative=False, restart_recovery="clean")
        heavy = ops_cost(separate_server=True, live_daemon_disturbance=True,
                         speculative=True, restart_recovery="wedges")
        self.assertLess(light, heavy)
```

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Implement** — frozen constants; `hard_gate_fail_reasons(*, false_absence, grounded_categorical, wrong_absence, voice_lint_ok)` returns closed `FailReason` values (note: `grounded_categorical` is a **bool from 2a's `assert_probe_result`**, not a float — there is no numeric bar); `latency_fail(*, p95_ms, max_ms)` → `p95_ms > ANSWER_CEILING_MS or max_ms > ANSWER_CEILING_MS`; `ops_cost(...)` sums weights over the closed evidence fields; `_latency_band`; `VariantScore` carries `ops_cost_value`; `_sort_key` ranks by `(hard_pass, min(voice_winrate, quality_winrate), latency_band, tokens_per_sec, -ops_cost_value)` — **`min(voice, quality)` so quality cannot mask voice loss**. `rank_variants` sorts desc. At impl, wire `grounded_categorical` to 2a's actual `assert_probe_result` return (open `scripts/recall_flip_eval/probes.py` to confirm the exact signal). Commit.

---

## Task 6: BenchPacket (bench_packet.v2, `__post_init__`-validated, content-free, producer-evidence)

**Files:** Create `scripts/brain_bench/bench_packet.py`; Test `tests/test_brain_bench_packet.py`

- [ ] **Step 1: RED test**

```python
# tests/test_brain_bench_packet.py
import dataclasses, json, unittest
from scripts.brain_bench.bench_packet import (
    BenchPacket, VariantReport, ScreenResult, FailReason)


class PacketTests(unittest.TestCase):
    def test_no_content_fields_anywhere(self):
        for cls in (VariantReport, BenchPacket):
            names = {f.name for f in dataclasses.fields(cls)}
            for bad in ("answer", "text", "evidence", "prompt", "snippet",
                        "reply", "probe_text"):
                self.assertNotIn(bad, names)

    def test_post_init_rejects_non_enum_fail_reason(self):
        with self.assertRaises(ValueError):
            VariantReport(label="x", hard_pass=False,
                          fail_reasons=("totally free text",), p95_ms=9000,
                          max_ms=9000)  # not a FailReason value

    def test_screen_result_enum_values(self):
        self.assertEqual({r.value for r in ScreenResult},
            {"passes_screen", "fails_too_slow", "fails_dishonest",
             "fails_voice_or_quality"})

    def test_covenant_fields_present_and_true(self):
        pkt = BenchPacket(schema_version="bench_packet.v2",
                          fixture_manifest_hash="h", variants=(),
                          screen_result=ScreenResult.FAILS_TOO_SLOW)
        d = pkt.to_dict()
        self.assertEqual(d["artifact_role"], "producer_evidence_not_verdict")
        self.assertTrue(d["owner_verdict_required"])
        self.assertTrue(d["requires_s5_voice_continuity_gate"])
        self.assertEqual(d["schema_version"], "bench_packet.v2")

    def test_sentinel_never_in_json(self):
        vr = VariantReport(label="v", hard_pass=False,
                           fail_reasons=(FailReason.FALSE_ABSENCE.value,),
                           p95_ms=3000, max_ms=3000)
        blob = json.dumps(BenchPacket("bench_packet.v2", "h", (vr,),
                          ScreenResult.FAILS_DISHONEST).to_dict())
        self.assertNotIn("FABRICATED_SENTINEL", blob)
```

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Implement** — `FailReason` (`false_absence`/`grounding_not_categorical`/`wrong_absence`/`voice_lint`/`over_answer_ceiling`/`inference_failed`); `ScreenResult` (`passes_screen`/`fails_too_slow`/`fails_dishonest`/`fails_voice_or_quality`); `OpsRubric` (closed evidence fields from Task 5). `VariantReport.__post_init__` validates every `fail_reasons` entry is a `FailReason` value (raise `ValueError` else) AND no field name is content-bearing (a frozen `_FORBIDDEN` set checked against `dataclasses.fields`). `BenchPacket.to_dict()` emits enum `.value`s + the three covenant fields hardcoded (`artifact_role="producer_evidence_not_verdict"`, `owner_verdict_required=True`, `requires_s5_voice_continuity_gate=True`). Latency dict carries `sample_n` + `method`. Commit.

---

## Task 7: Two-stage orchestrator + launcher (negative-control, tail vs over-ceiling)

**Files:** Create `scripts/brain_bench/bench.py`, `launcher.py`; Test `tests/test_brain_bench_orchestration.py`

- [ ] **Step 1: RED test** — dishonest variant fails hard + no sentinel leak; over-ceiling vs tail distinct; injected runners so no model runs.

```python
# tests/test_brain_bench_orchestration.py
import json, unittest
from scripts.brain_bench.bench import run_benchmark
from scripts.brain_bench.bench_packet import BenchPacket, FailReason


def _variants(*labels):
    return json.dumps([{"label": l, "base_url": "http://127.0.0.1:11434",
                        "model": "m"} for l in labels])


class OrchestrationTests(unittest.TestCase):
    def test_dishonest_eliminated_and_no_text_leak(self):
        def probe_run(variant, probe, k):
            if variant.label == "dishonest":
                return {"false_absence": True, "grounded_categorical": False,
                        "wrong_absence": True, "voice_lint_ok": False,
                        "latencies_ms": [3000]*k, "answer": "FABRICATED_SENTINEL"}
            return {"false_absence": False, "grounded_categorical": True,
                    "wrong_absence": False, "voice_lint_ok": True,
                    "latencies_ms": [9000]*k, "answer": "April 27 [E1]"}
        pkt = run_benchmark(_variants("honest", "dishonest"),
                            probe_run=probe_run, judge=lambda inp: None)
        self.assertIsInstance(pkt, BenchPacket)
        rep = {v.label: v for v in pkt.variants}
        self.assertFalse(rep["dishonest"].hard_pass)
        self.assertIn(FailReason.FALSE_ABSENCE.value, rep["dishonest"].fail_reasons)
        self.assertTrue(rep["honest"].hard_pass)
        self.assertNotIn("FABRICATED_SENTINEL", json.dumps(pkt.to_dict()))

    def test_over_ceiling_fails_and_tail_is_separate(self):
        def probe_run(variant, probe, k):
            lat = [5000]*(k-1) + [21000]  # one 21s run > ceiling
            return {"false_absence": False, "grounded_categorical": True,
                    "wrong_absence": False, "voice_lint_ok": True,
                    "latencies_ms": lat, "answer": "ok [E1]"}
        pkt = run_benchmark(_variants("tail"), probe_run=probe_run,
                            judge=lambda inp: None)
        v = pkt.variants[0]
        self.assertFalse(v.hard_pass)                 # max over ceiling → FAIL
        self.assertIn(FailReason.OVER_ANSWER_CEILING.value, v.fail_reasons)
        self.assertTrue(v.over_ceiling)
```

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Implement** `run_benchmark`: load+validate variants; **screen** (`SCREEN_K`) over the battery, dropping hard-gate or latency fails; **finalists** (`FINALIST_K`) over top 2–3; compute `p50/p90/p95/max/variance/sample_n/method`; set `over_ceiling = max_ms > ANSWER_CEILING_MS` (→ `OVER_ANSWER_CEILING` hard-fail) and `tail_flags` separately (run > 2×p50 but ≤ ceiling); run the blind judge on finalists; score + `rank_variants`; derive top-level `ScreenResult` from the best variant's dominant blocker (`passes_screen` only if hard+latency pass; else `fails_dishonest`/`fails_too_slow`/`fails_voice_or_quality`); build `BenchPacket` (with the three covenant fields). The real `probe_run` runs under `assert_sandbox` + `no_egress(allow_loopback_ports=(variant.port,))` using `measure_generation`; tests inject a fake `probe_run`.

- [ ] **Step 4:** `launcher.py` mirrors 2a (`MAEZ_HOME/DATA/CONFIG/CACHE/OWNER_TIMEZONE` then `os.execv` into `scripts.brain_bench.bench`) — sandbox before any maez import. Real run owner-operated. Commit.

---

## Task 8: gitignore, lint, regression

- [ ] **Step 1:** Add the debug-dump dir to `.gitignore`; test asserts the orchestrator's dump path matches a gitignored pattern.
- [ ] **Step 2:** Ruff on all new files + modified `sandbox.py`.
- [ ] **Step 3:** Targeted run: `.venv/bin/python -m unittest tests.test_brain_bench_sandbox tests.test_brain_bench_variants tests.test_brain_bench_inference tests.test_brain_bench_judge tests.test_brain_bench_gates tests.test_brain_bench_packet tests.test_brain_bench_orchestration -v` → green. Re-run **2a** (`tests.test_recall_flip_eval_isolation test_recall_flip_eval_packet test_recall_flip_eval_probes`) → `35 OK`, proving `no_egress` change is backward-compatible.
- [ ] **Step 4: Commit** (scoped staging; NOT `git add -A`).

---

## Self-Review

**Spec coverage (v2 folds):** (1) all 5 socket APIs + import-guard → Task 1 ✓; (2) localhost-only validation variants+judge → Task 2 ✓; (3) categorical grounding, no numeric bar → Task 5 (`grounded_categorical` bool) ✓; (4) BlindAnswer + counterbalanced + TIE/INVALID + voice/quality separate → Task 4 ✓; (5) TTFT=first-content + closed fail codes + canonical shape → Task 3 ✓; (6) `__post_init__` validation + recursive content rejection + sentinel-not-in-JSON → Task 6 ✓; (7) sample_n+method + `max_ms` over-ceiling fail + tail-distinct → Tasks 5,6,7 ✓; (8) ops from closed evidence → Task 5 `ops_cost` ✓; (9) producer-evidence wording, `screen_result`, covenant fields → Task 6 ✓. Plus 2a frozen (default-empty allowlist; re-run 2a suite) and real 2a test names.

**Placeholder scan:** `grounded_categorical` is wired to 2a's actual `assert_probe_result` signal at impl (Task 5 Step 3) — no invented number. Token-count chunk-proxy documented (Task 3). Real inference + live run owner-operated; logic proven via injection. No "TODO."

**Symbol consistency:** `no_egress(allow_loopback_ports=...)`, `validate_endpoint`/`Variant.port`, `measure_generation`/`GenerationMeasurement`/`FailCode`, `BlindAnswer`/`PairwiseInput`/`judge_pairwise`, `VariantScore`/`rank_variants`/`hard_gate_fail_reasons`/`latency_fail`/`ops_cost`, `FailReason`/`ScreenResult`/`VariantReport`/`BenchPacket` consistent across tasks; constants frozen.

**Ordering:** isolation(1) → variants(2) → inference(3) → judge(4) → gates(5) → packet(6) → orchestrator(7) → gitignore/lint/regression(8). Load-bearing isolation first; each independently committable.

## Execution note
Codex's six-agent pass pressures, in order: **(1) the 5-API egress allowlist + import-guard** — any path to a non-loopback host/non-allowed port, `sendto` truly dead, `getaddrinfo` loopback-only, 2a block-all byte-identical; **(2) the content-free packet boundary** — `__post_init__` (not just builder) rejects non-enum + content fields, negative-control sentinel never in JSON; **(3) grounding is the categorical 2a signal, not a float**; **(4) covenant wording** — packet cannot read as identity/authority certification (`artifact_role`/`owner_verdict_required`/`requires_s5_voice_continuity_gate` present). If any of these leak, the benchmark is invalid regardless of scoring.
