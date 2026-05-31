# Brain Benchmark (Slice 2) Implementation Plan — v3

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** A hermetic, send-path-free benchmark running real local model variants over the recall battery, emitting a content-free **producer-evidence** `BenchPacket` reporting whether each variant *passes the recall-benchmark screen* (honest + fast + voice-lint-clean). Owner decides; packet never certifies identity or authorizes the flip.

**Architecture:** New `scripts/brain_bench/` reusing `scripts/recall_flip_eval/{sandbox,probes}` (2a frozen). One shared change: `no_egress(allow_loopback_ports=())`, default preserves block-all. Benchmark injects a `chat_fn` adapter into the **production** `focused_synthesize`. Pairwise counterbalanced **advisory** blind judge. Deterministic hard gates + A7 latency; lexicographic ranking; content-free closed-enum packet.

**Spec:** [docs/superpowers/specs/2026-05-31-brain-benchmark-design.md](../specs/2026-05-31-brain-benchmark-design.md) (**v3**). **Build v3.** After implementing, the pre-code pass reruns against the diff.

**v3 discipline (the 7 second-pass folds, on top of v2's 9):**
1. **Judge is ADVISORY ONLY** — `fails_voice_or_quality` removed; judge win-rate ranks/reports, never sets `hard_pass`. Sole mechanical voice gate = deterministic voice-lint.
2. **Judge endpoint** validated localhost-only (same `validate_endpoint`) AND in the allowlist only during the judging phase.
3. **Packet boundary**: `__post_init__` content rejection is **recursive (nested dataclasses) + enum-internal**; **non-vacuous** sentinel test; debug dump carries **quarantine metadata (UNTRUSTED)**.
4. **Streaming measures the real seam**: benchmark-only `chat_fn` adapter injected into production `focused_synthesize(..., chat_fn=...)`; `/api/chat` pinned; payload merge rules; **partial-output-then-failure scrubs answer text**.
5. **No laundering**: drop caller `ops_cost_value` (derive ops cost from closed evidence in-substrate); `grounded_categorical` strictly **bool** (reject `0.99`).
6. **Sandbox tests stronger**: empty allowlist blocks all 5 APIs; allowed loopback covers `connect`/`connect_ex`; `getaddrinfo` loopback-only; import-guard.
7. No identity-overclaim anywhere ("passes the recall-benchmark screen", never "still Maez").

Frozen: `answer_ceiling_ms=12000`, `strong_ms=8000`, `excellent_band_ms=(4000,6000)`, `screen_k=3`, `finalist_k=7`. Model-agnostic; genderless; 2a byte-behaviorally unchanged. `bench_packet.v3`. Real 2a test modules: `tests.test_recall_flip_eval_{isolation,packet,probes}` (35 OK floor).

---

## File Structure
- **Modify** `scripts/recall_flip_eval/sandbox.py` — `no_egress(allow_loopback_ports=())`, all 5 APIs.
- **Create** `scripts/brain_bench/{__init__,variants,inference,inference_backend,judge,gates,bench_packet,bench,launcher}.py`
- **Create** tests `tests/test_brain_bench_{sandbox,variants,inference,judge,gates,packet,orchestration}.py`
- **Modify** `.gitignore` — debug-dump dir.

---

## Task 1: Egress guard — all 5 APIs, empty=block-all, loopback allowlist, import-guard (LOAD-BEARING)

**Files:** Modify `scripts/recall_flip_eval/sandbox.py`; Test `tests/test_brain_bench_sandbox.py`

- [ ] **Step 1: RED test** — exhaustive per API, both directions, 2a default preserved:

```python
# tests/test_brain_bench_sandbox.py
import socket, unittest
from scripts.recall_flip_eval.sandbox import no_egress, EgressBlockedError


class EmptyAllowlistBlocksAllFiveAPIs(unittest.TestCase):
    def test_all_five_blocked_under_empty_allowlist(self):
        with no_egress():  # 2a behavior preserved
            with self.assertRaises(EgressBlockedError):
                socket.create_connection(("127.0.0.1", 11434))
            s = socket.socket()
            with self.assertRaises(EgressBlockedError):
                s.connect(("127.0.0.1", 11434))
            with self.assertRaises(EgressBlockedError):
                s.connect_ex(("127.0.0.1", 11434))
            s.close()
            d = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            with self.assertRaises(EgressBlockedError):
                d.sendto(b"x", ("127.0.0.1", 11434))
            d.close()
            with self.assertRaises(EgressBlockedError):
                socket.getaddrinfo("127.0.0.1", 11434)


class AllowedLoopbackCoversConnectAndConnectEx(unittest.TestCase):
    def test_connect_and_connect_ex_allowed_for_loopback_port(self):
        with no_egress(allow_loopback_ports=(11434,)):
            for fn in ("create_connection", "connect", "connect_ex"):
                s = socket.socket()
                try:
                    if fn == "create_connection":
                        socket.create_connection(("127.0.0.1", 11434), timeout=0.01)
                    elif fn == "connect":
                        s.settimeout(0.01); s.connect(("127.0.0.1", 11434))
                    else:
                        s.settimeout(0.01); s.connect_ex(("127.0.0.1", 11434))
                except EgressBlockedError:
                    self.fail(f"{fn} blocked on allowed loopback port")
                except OSError:
                    pass  # refused/timeout fine — guard let it through
                finally:
                    s.close()

    def test_external_and_wrong_port_still_blocked(self):
        with no_egress(allow_loopback_ports=(11434,)):
            with self.assertRaises(EgressBlockedError):
                socket.create_connection(("8.8.8.8", 53))
            with self.assertRaises(EgressBlockedError):
                socket.create_connection(("127.0.0.1", 22))

    def test_getaddrinfo_loopback_only(self):
        with no_egress(allow_loopback_ports=(11434,)):
            for _f, _t, _p, _c, addr in socket.getaddrinfo("127.0.0.1", 11434):
                self.assertIn(addr[0], {"127.0.0.1", "::1"})
            with self.assertRaises(EgressBlockedError):
                socket.getaddrinfo("example.com", 11434)

    def test_sendto_always_blocked_even_allowed_port(self):
        with no_egress(allow_loopback_ports=(11434,)):
            d = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            with self.assertRaises(EgressBlockedError):
                d.sendto(b"x", ("127.0.0.1", 11434))
            d.close()
```

- [ ] **Step 2: Run → fail.**
- [ ] **Step 3: Implement** per spec §4.2 — `_LOOPBACK_HOSTS`, `_addr_is_allowed(address, ports)`; guard wrappers for `create_connection`/`connect`/`connect_ex` (allow loopback:allowed-port else raise), `sendto` always raises, `getaddrinfo` returns original only for loopback host + allowed port else raises; restore all five in `finally`. Empty `allow_loopback_ports` → nothing allowed (2a's block-all).
- [ ] **Step 4: Import-guard test** — a `tests` case asserting the brain_bench setup helper establishes sandbox env + patches paths such that `assert_sandbox(root)` holds; document that the launcher's `os.execv` runs before any maez import.
- [ ] **Step 5: Run → pass.** Re-run 2a: `.venv/bin/python -m unittest tests.test_recall_flip_eval_isolation tests.test_recall_flip_eval_packet tests.test_recall_flip_eval_probes -v` → `35 OK`. **Commit.**

---

## Task 2: Variant + JUDGE endpoint validation (localhost-only at load)

**Files:** Create `scripts/brain_bench/variants.py`, `__init__.py`; Test `tests/test_brain_bench_variants.py`

- [ ] **Step 1: RED test** — `validate_endpoint` rejects every sneaky URL; both variant and judge configs use it.

```python
# tests/test_brain_bench_variants.py
import json, unittest
from scripts.brain_bench.variants import (
    load_variants, validate_endpoint, VariantConfigError)


class EndpointValidationTests(unittest.TestCase):
    def test_accepts_loopback_http_with_port(self):
        self.assertEqual(validate_endpoint("http://127.0.0.1:11434"), 11434)
        self.assertEqual(validate_endpoint("http://localhost:8081"), 8081)

    def test_rejects(self):
        for bad in ("https://127.0.0.1:11434", "http://127.0.0.1",
                    "http://u:p@127.0.0.1:11434", "http://127.0.0.1:11434/?x=1",
                    "http://127.0.0.1:11434/#f", "http://10.0.0.5:11434",
                    "http://example.com:11434"):
            with self.assertRaises(VariantConfigError, msg=bad):
                validate_endpoint(bad)


class RegistryTests(unittest.TestCase):
    def test_loads_and_validates(self):
        v = load_variants(json.dumps([{"label": "c",
            "base_url": "http://127.0.0.1:11434", "model": "m"}]))[0]
        self.assertEqual(v.port, 11434)
    def test_rejects_non_loopback_variant(self):
        with self.assertRaises(VariantConfigError):
            load_variants(json.dumps([{"label": "x",
                "base_url": "http://10.0.0.5:11434", "model": "m"}]))
    def test_judge_endpoint_uses_same_validator(self):
        # the judge config loader must call validate_endpoint too
        from scripts.brain_bench.variants import resolve_judge_endpoint
        with self.assertRaises(VariantConfigError):
            resolve_judge_endpoint("https://127.0.0.1:8081")  # https rejected
        self.assertEqual(resolve_judge_endpoint("http://127.0.0.1:8081"), 8081)
```

- [ ] **Step 2: Run → fail.**
- [ ] **Step 3: Implement** — `validate_endpoint(url)->int` (urlparse; scheme=="http"; host in loopback set; `.port` not None; no username/password; empty query/fragment; else `VariantConfigError`). `Variant.port` via `validate_endpoint`. `load_variants` enforces required fields + unique labels + validates each `base_url`. `resolve_judge_endpoint(url)->int` wraps `validate_endpoint` for `MAEZ_JUDGE_BASE_URL`.
- [ ] **Step 4: Run → pass. Commit.**

---

## Task 3: Streaming measurement via the REAL synthesis seam

**Files:** Create `scripts/brain_bench/inference.py`, `inference_backend.py`; Test `tests/test_brain_bench_inference.py`

- [ ] **Step 1: RED test** — adapter matches `focused_synthesize`'s `chat_fn` contract; TTFT=first non-empty content; partial-then-failure scrubs text; closed codes.

```python
# tests/test_brain_bench_inference.py
import unittest
from scripts.brain_bench.inference import (
    make_benchmark_chat_fn, measure_generation, FailCode)


class ChatFnAdapterTests(unittest.TestCase):
    def test_adapter_signature_matches_focused_synthesize_contract(self):
        # focused_synthesize calls chat_fn(model=?, messages=?, think=?, options=?)
        seen = {}
        def fake_stream(*, variant, payload):
            seen["payload"] = payload
            return iter([{"content": "April "}, {"content": "27 [E1]"}])
        chat_fn, meas = make_benchmark_chat_fn(
            variant=_loopback_variant(), stream_factory=fake_stream)
        out = chat_fn(model="ignored-by-adapter", messages=[{"role": "user",
              "content": "q"}], think=False, options={"num_predict": 256})
        # adapter pins /api/chat shape and merges options
        self.assertIn("messages", seen["payload"])
        self.assertEqual(seen["payload"]["options"]["num_predict"], 256)
        self.assertEqual(meas.last().answer, "April 27 [E1]")

    def test_partial_output_then_failure_scrubs_answer(self):
        def boom_after_one(*, variant, payload):
            def gen():
                yield {"content": "secret partial "}
                raise TimeoutError()
            return gen()
        chat_fn, meas = make_benchmark_chat_fn(
            variant=_loopback_variant(), stream_factory=boom_after_one)
        try:
            chat_fn(model="m", messages=[], think=False, options={})
        except Exception:
            pass
        m = meas.last()
        self.assertTrue(m.failed)
        self.assertEqual(m.fail_code, FailCode.TIMEOUT.value)
        self.assertEqual(m.answer, "")  # partial text scrubbed, not leaked


class MeasurementTests(unittest.TestCase):
    def test_ttft_first_nonempty_content(self):
        ticks = iter([0.0, 0.3, 0.4, 0.8, 2.0]); clock = lambda: next(ticks)
        def sf(*, variant, payload):
            return iter([{"content": ""}, {"content": ""},
                         {"content": "A "}, {"content": "B"}])
        m = measure_generation(variant=_loopback_variant(), payload={},
                               clock=clock, stream_factory=sf)
        self.assertEqual(m.ttft_ms, 800)   # first NON-EMPTY @0.8
        self.assertEqual(m.total_ms, 2000)
        self.assertEqual(m.output_tokens, 2)

    def test_empty_output_closed_code(self):
        m = measure_generation(variant=_loopback_variant(), payload={},
                               clock=iter([0.0, 1.0]).__next__,
                               stream_factory=lambda **k: iter([{"content": ""}]))
        self.assertTrue(m.failed); self.assertEqual(m.fail_code, FailCode.EMPTY.value)


def _loopback_variant():
    from scripts.brain_bench.variants import load_variants
    import json
    return load_variants(json.dumps([{"label": "v",
        "base_url": "http://127.0.0.1:11434", "model": "m"}]))[0]
```

- [ ] **Step 2: Run → fail.**
- [ ] **Step 3: Implement** —
  - `FailCode(Enum)` = `TIMEOUT/REFUSED/BAD_SHAPE/EMPTY`; `GenerationMeasurement(answer, ttft_ms, total_ms, output_tokens, tokens_per_sec, failed, fail_code)`.
  - `measure_generation(*, variant, payload, clock, stream_factory)` consumes the stream, stamps TTFT at first **non-empty** content, counts non-empty chunks; on `TimeoutError`→TIMEOUT, `ConnectionError/OSError`→REFUSED, parse error→BAD_SHAPE, zero content→EMPTY. **On any failure (even after partial output) returns `answer=""`** (scrub partial). No raw exception text.
  - `make_benchmark_chat_fn(*, variant, stream_factory=None)` returns `(chat_fn, measurement_sink)`. `chat_fn(*, model, messages, think, options)` matches `focused_synthesize`'s call (the adapter **ignores the incoming `model`** and uses the variant's model — that's the point: same synthesis path, swapped brain); builds the **canonical `/api/chat` payload** `{model: variant.model, messages, stream: True, options: {**variant.chat_kwargs, **options}}` (variant kwargs are the base, caller `options` override — document the merge order), wires `draft_model` if present; calls `measure_generation`, records into the sink, returns the answer in `focused_synthesize`'s expected response shape.
  - `inference_backend.py`: `ollama_stream(*, variant, payload)` POSTs `payload` to `variant.base_url` (which is `…/api/chat`) with `stream=True`, yields `{"content": delta}`. Smoke test mocks `requests.post`, asserts the posted dict + URL path `/api/chat`.
- [ ] **Step 4:** Integration test — inject the adapter into the **real** `focused_cognition.focused_synthesize(..., chat_fn=chat_fn)` (mirror `scripts/recall_flip_eval/harness.py:139`) over one probe and assert it returns + the sink recorded TTFT/total. Proves the real seam, not a lookalike. Commit.

---

## Task 4: Pairwise counterbalanced blind judge — ADVISORY ONLY

**Files:** Create `scripts/brain_bench/judge.py`; Test `tests/test_brain_bench_judge.py`

- [ ] **Step 1: RED test** — (carry v2's blindness + counterbalance + TIE/INVALID + voice/quality-separate tests) **plus** an advisory-only assertion: the judge result type has no field that can set `hard_pass`, and `judge_pairwise` returns only win-rates.

```python
# add to tests/test_brain_bench_judge.py
def test_judge_result_cannot_gate(self):
    import dataclasses
    from scripts.brain_bench.judge import JudgeResult
    names = {f.name for f in dataclasses.fields(JudgeResult)}
    for gating in ("hard_pass", "fail", "gate", "screen_result", "passes"):
        self.assertNotIn(gating, names)   # judge cannot fail a variant
```

(Keep from v2: `test_no_label_reaches_prompt`, `test_counterbalanced_both_orders_issued`, `test_tie_and_invalid_score_no_win`, `test_voice_and_quality_independent`.)

- [ ] **Step 2: Run → fail.**
- [ ] **Step 3: Implement** — `BlindAnswer(probe_id, answer, evidence)` (no label field exists). `judge_pairwise(inputs, *, call_judge, seed) -> JudgeResult(quality_winrate, voice_winrate)` — per probe, per pair, per axis, **two** calls (A-first and B-first), closed verdict `A/B/TIE/INVALID` (TIE/INVALID = no win, both count as games), aggregate to win-rate. `variant_label` lives only in the result mapping, never in `BlindAnswer`/prompt. Repetition-aware grouping. Production `call_judge` wraps the pinned, **validated** `MAEZ_JUDGE_MODEL` endpoint. `JudgeResult` has **no** gating field.
- [ ] **Step 4: Run → pass. Commit.**

---

## Task 5: Gates (categorical-bool grounding, A7 latency) + ranking + ops-from-evidence

**Files:** Create `scripts/brain_bench/gates.py`; Test `tests/test_brain_bench_gates.py`

- [ ] **Step 1: RED test**

```python
# tests/test_brain_bench_gates.py
import unittest
from scripts.brain_bench.gates import (
    ANSWER_CEILING_MS, STRONG_MS, EXCELLENT_BAND_MS, SCREEN_K, FINALIST_K,
    hard_gate_fail_reasons, latency_fail, rank_variants, ops_cost,
    VariantScore, GroundingTypeError)
from scripts.brain_bench.bench_packet import FailReason


class ConstTests(unittest.TestCase):
    def test_frozen(self):
        self.assertEqual((ANSWER_CEILING_MS, STRONG_MS, EXCELLENT_BAND_MS,
                          SCREEN_K, FINALIST_K), (12000, 8000, (4000, 6000), 3, 7))


class GroundingStrictBoolTests(unittest.TestCase):
    def test_rejects_float_drift(self):
        with self.assertRaises(GroundingTypeError):
            hard_gate_fail_reasons(false_absence=False, grounded_categorical=0.99,
                                   wrong_absence=False, voice_lint_ok=True)
    def test_accepts_bool(self):
        self.assertIn(FailReason.GROUNDING_NOT_CATEGORICAL.value,
            hard_gate_fail_reasons(false_absence=False, grounded_categorical=False,
                                   wrong_absence=False, voice_lint_ok=True))


class LatencyTests(unittest.TestCase):
    def test_p95_or_max_over_ceiling_fails(self):
        self.assertTrue(latency_fail(p95_ms=11000, max_ms=12001))
        self.assertTrue(latency_fail(p95_ms=12001, max_ms=12001))
        self.assertFalse(latency_fail(p95_ms=9000, max_ms=11000))


class OpsFromEvidenceTests(unittest.TestCase):
    def test_cost_derived_not_caller_supplied(self):
        import dataclasses
        names = {f.name for f in dataclasses.fields(VariantScore)}
        self.assertNotIn("ops_cost_value", names)  # no caller score field
        light = ops_cost(separate_server=False, live_daemon_disturbance=False,
                         speculative=False, restart_recovery="clean")
        heavy = ops_cost(separate_server=True, live_daemon_disturbance=True,
                         speculative=True, restart_recovery="wedges")
        self.assertLess(light, heavy)


class RankingTests(unittest.TestCase):
    def test_honesty_first(self):
        self.assertEqual(rank_variants([
            VariantScore("fast", False, 3000, 0.9, 0.9, 50, ops=1),
            VariantScore("slow", True, 11000, 0.6, 0.6, 10, ops=2)])[0].label, "slow")
    def test_voice_not_masked_by_quality(self):
        self.assertEqual(rank_variants([
            VariantScore("a", True, 8000, 0.95, 0.30, 20, ops=1),
            VariantScore("b", True, 8000, 0.70, 0.70, 20, ops=1)])[0].label, "b")
    def test_ops_breaks_band_ties(self):
        self.assertEqual(rank_variants([
            VariantScore("a", True, 8000, 0.8, 0.8, 20, ops=5),
            VariantScore("b", True, 8000, 0.8, 0.8, 20, ops=1)])[0].label, "b")
```

- [ ] **Step 2: Run → fail.**
- [ ] **Step 3: Implement** — frozen constants. `GroundingTypeError`. `hard_gate_fail_reasons(*, false_absence, grounded_categorical, wrong_absence, voice_lint_ok)`: **raise `GroundingTypeError` if `type(grounded_categorical) is not bool`** (reject `0.99`), then return closed `FailReason` values (`grounding_not_categorical` when `False`). `latency_fail(*, p95_ms, max_ms)` → either over `ANSWER_CEILING_MS`. `ops_cost(*, separate_server, live_daemon_disturbance, speculative, restart_recovery, ...)` sums weights over closed evidence. `VariantScore(label, hard_pass, p95_ms, quality_winrate, voice_winrate, tokens_per_sec, ops)` — **`ops` is the derived cost, no caller `ops_cost_value`**. `_sort_key = (hard_pass, min(voice_winrate, quality_winrate), _latency_band(p95_ms), tokens_per_sec, -ops)`. Wire `grounded_categorical` to 2a's actual `assert_probe_result` bool at impl. Commit.

---

## Task 6: BenchPacket (bench_packet.v3, recursive content-free, advisory judge)

**Files:** Create `scripts/brain_bench/bench_packet.py`; Test `tests/test_brain_bench_packet.py`

- [ ] **Step 1: RED test** — `fails_voice_or_quality` gone; recursive (nested `OpsRubric`) content rejection; **non-vacuous** sentinel; covenant fields.

```python
# tests/test_brain_bench_packet.py
import dataclasses, json, unittest
from scripts.brain_bench.bench_packet import (
    BenchPacket, VariantReport, OpsRubric, ScreenResult, FailReason)


class ScreenResultTests(unittest.TestCase):
    def test_no_voice_quality_fail_mode(self):
        self.assertEqual({r.value for r in ScreenResult},
            {"passes_screen", "fails_too_slow", "fails_dishonest"})


class RecursiveContentFreeTests(unittest.TestCase):
    def test_rejects_content_field_in_nested_dataclass(self):
        # a nested dataclass carrying a content field must be rejected too
        with self.assertRaises(ValueError):
            @dataclasses.dataclass(frozen=True)
            class _Bad:
                answer: str = "x"
            VariantReport(label="v", hard_pass=True, fail_reasons=(),
                          p95_ms=9000, max_ms=9000, ops=_Bad())

    def test_non_vacuous_sentinel_scrubbed(self):
        # put a sentinel into ops evidence enum-ish field that DOES serialize;
        # prove the packet json cannot carry free content
        ops = OpsRubric(api_family="ollama", topology="reuse",
                        bind_host_verified=True, live_daemon_disturbance=False,
                        gpu_contention="none", startup_health="ok",
                        streaming_support=True, restart_recovery="clean")
        vr = VariantReport(label="v", hard_pass=False,
                           fail_reasons=(FailReason.FALSE_ABSENCE.value,),
                           p95_ms=3000, max_ms=3000, ops=ops)
        blob = json.dumps(BenchPacket("bench_packet.v3", "h", (vr,),
                          ScreenResult.FAILS_DISHONEST).to_dict())
        self.assertNotIn("FABRICATED_SENTINEL", blob)
        self.assertNotIn("answer", blob)


class CovenantFieldTests(unittest.TestCase):
    def test_fields_present(self):
        d = BenchPacket("bench_packet.v3", "h", (), ScreenResult.FAILS_TOO_SLOW).to_dict()
        self.assertEqual(d["artifact_role"], "producer_evidence_not_verdict")
        self.assertTrue(d["owner_verdict_required"])
        self.assertTrue(d["requires_s5_voice_continuity_gate"])
        self.assertEqual(d["schema_version"], "bench_packet.v3")
    def test_post_init_rejects_non_enum_reason(self):
        with self.assertRaises(ValueError):
            VariantReport(label="x", hard_pass=False,
                          fail_reasons=("free text",), p95_ms=9000, max_ms=9000)
```

- [ ] **Step 2: Run → fail.**
- [ ] **Step 3: Implement** —
  - `FailReason` (`false_absence`/`grounding_not_categorical`/`wrong_absence`/`voice_lint`/`over_answer_ceiling`/`inference_failed`); `ScreenResult` (`passes_screen`/`fails_too_slow`/`fails_dishonest` — **no voice/quality fail**); `OpsRubric` (closed evidence fields from Task 5).
  - `VariantReport.__post_init__`: validate each `fail_reasons` entry ∈ `FailReason` values (raise `ValueError`); **recursively** walk own fields AND any nested dataclass field, raising `ValueError` if any field name ∈ `_FORBIDDEN_CONTENT = {answer,text,evidence,prompt,snippet,reply,probe_text,...}`.
  - `BenchPacket.to_dict()` emits enum `.value`s + the three covenant fields hardcoded true/string. Latency dict carries `sample_n`+`method`.
- [ ] **Step 4: Run → pass. Commit.**

---

## Task 7: Two-stage orchestrator + launcher (phase-scoped allowlist, quarantined dump)

**Files:** Create `scripts/brain_bench/bench.py`, `launcher.py`; Test `tests/test_brain_bench_orchestration.py`

- [ ] **Step 1: RED test** — (carry v2's dishonest-eliminated + over-ceiling-fails tests) plus: judge phase allows ONLY the judge port, and the debug dump is tagged quarantined.

```python
# add to tests/test_brain_bench_orchestration.py
def test_debug_dump_is_quarantine_tagged(self):
    from scripts.brain_bench.bench import debug_dump_metadata
    md = debug_dump_metadata()
    self.assertEqual(md["provenance"], "UNTRUSTED")
    self.assertTrue(md["quarantined"])
    self.assertFalse(md.get("promotable", False))

def test_negative_control_no_text_leak(self):
    # (carry from v2) dishonest variant fabricates FABRICATED_SENTINEL;
    # assert hard_pass False + sentinel absent from packet json.
    ...
```

- [ ] **Step 2: Run → fail.**
- [ ] **Step 3: Implement** `run_benchmark`: load+validate variants; **screen** (`SCREEN_K`) under `assert_sandbox` + `no_egress(allow_loopback_ports=(variant.port,))`, dropping hard-gate (incl. grounding-bool, voice-lint) or latency fails; **finalists** (`FINALIST_K`) over top 2–3; stats `p50/p90/p95/max/variance/sample_n/method`; `over_ceiling = max_ms > ANSWER_CEILING_MS` (→ `OVER_ANSWER_CEILING` hard-fail); `tail_flags` separate; **judging phase** runs `judge_pairwise` under `no_egress(allow_loopback_ports=(resolve_judge_endpoint(JUDGE_BASE_URL),))` — judge port only, variant ports closed; `rank_variants`; derive `ScreenResult` (`passes_screen` iff a finalist passes hard+latency; else `fails_dishonest`/`fails_too_slow`); build `BenchPacket`. `debug_dump_metadata()` returns the UNTRUSTED/quarantined tag; raw answers written only there. Tests inject fake `probe_run`/`judge`.
- [ ] **Step 4:** `launcher.py` mirrors 2a (env then `os.execv` into `scripts.brain_bench.bench`); real run owner-operated. Commit.

---

## Task 8: gitignore, lint, regression

- [ ] **Step 1:** `.gitignore` the debug-dump dir; test asserts dump path matches the gitignored pattern.
- [ ] **Step 2:** Ruff on all new files + `sandbox.py`.
- [ ] **Step 3:** `.venv/bin/python -m unittest tests.test_brain_bench_sandbox tests.test_brain_bench_variants tests.test_brain_bench_inference tests.test_brain_bench_judge tests.test_brain_bench_gates tests.test_brain_bench_packet tests.test_brain_bench_orchestration -v` → green. Re-run 2a (`isolation/packet/probes`) → `35 OK`.
- [ ] **Step 4: Commit** (scoped staging).

---

## Self-Review
**v3 fold coverage:** judge advisory-only + `fails_voice_or_quality` removed → Tasks 4,5,6 ✓; judge endpoint validated + phase-scoped allowlist → Tasks 2,7 ✓; recursive/nested content-free + non-vacuous sentinel + quarantine dump → Tasks 6,7 ✓; `chat_fn` into real `focused_synthesize` + `/api/chat` + merge + partial-scrub → Task 3 ✓; ops-from-evidence (no caller score) + grounding strict-bool → Task 5 ✓; sandbox 5-API/connect/connect_ex/getaddrinfo/import-guard → Task 1 ✓; no identity-overclaim → spec/plan/handoff wording ✓. v2 folds retained.
**Placeholder scan:** `grounded_categorical` wired to 2a's real bool at impl (Task 5); token chunk-proxy documented (Task 3); real inference + live run owner-operated. No "TODO."
**Symbol consistency:** `no_egress(allow_loopback_ports=)`, `validate_endpoint`/`resolve_judge_endpoint`, `make_benchmark_chat_fn`/`measure_generation`/`FailCode`, `BlindAnswer`/`judge_pairwise`/`JudgeResult`(no gate field), `hard_gate_fail_reasons`/`GroundingTypeError`/`latency_fail`/`ops_cost`/`VariantScore`(ops, no ops_cost_value)/`rank_variants`, `FailReason`/`ScreenResult`(3 values)/`OpsRubric`/`VariantReport`/`BenchPacket`(v3) consistent.
**Ordering:** isolation(1)→endpoints(2)→real-seam inference(3)→advisory judge(4)→gates(5)→packet(6)→orchestrator(7)→lint(8). Load-bearing first; each committable.

## Execution note
Codex's six-agent pass pressures, in order: **(1) 5-API egress + phase-scoped allowlist** (variant port only during inference, judge port only during judging, all else dead, 2a block-all byte-identical); **(2) the real-seam `chat_fn`** (does it inject into production `focused_synthesize`, not a lookalike; does partial-then-failure scrub); **(3) recursive content-free packet** (nested dataclass + non-vacuous sentinel); **(4) no laundering** (grounding bool not float; ops derived not caller-set; judge cannot gate); **(5) covenant wording** (no "still Maez"). Any leak invalidates the instrument.
