# Latency-Attribution (Measurement) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Attribute focused-recall latency into prompt-build / brain-call / output components (live, passive, content-free) + an offline TTFT/throughput sweep — so the *fix* slice can choose its lever from data, not assumption.

**Architecture:** `FocusedResult` gains defaulted timing fields; `focused_synthesize` captures `prompt_build_ms`/`chat_total_ms`/`reply_token_est` around the **unchanged buffered** `chat_fn` call; the daemon emits one content-free `focused_synthesis_timing` event (it owns `turn_kind`). A thin offline sweep harness uses the existing brain-bench `GenerationMeasurement` for TTFT/throughput. **Measurement only — ships no fix; scoreboard byte-stable; recall off.**

**Tech Stack:** Python 3.14, **`unittest`** (no pytest). Runner: `.venv/bin/python -m unittest …`.

**Spec:** [docs/superpowers/specs/2026-06-01-latency-attribution-design.md](../specs/2026-06-01-latency-attribution-design.md)

**Process:** Codex switchboard. Claude cross-verifies every diff, runs suites independently, fires the coverage panel before merge on the legacy baseline. This plan IS the Codex handoff.

**Hard invariants:**
- **No fix:** no working-set trim/cap/rank, no `num_predict` cap, no model/runtime change.
- **Buffered call untouched:** the `chat_fn(... options={"num_predict":4096})` call, its options, and `FocusedResult.reply`/`cited_ids` are byte-identical.
- **Scoreboard byte-stable:** `recall_outcome` / `outcome_class` unchanged (existing daemon outcome tests stay green).
- **Content-free:** `focused_synthesis_timing` carries only durations + counts — no answer/evidence/question text.
- Recall flag off; brain-agnostic.

---

## Background: exact seams (verified 2026-06-01)

- `core/routing/focused_cognition.py:231` `@dataclass(frozen=True) class FocusedResult: reply: str; cited_ids: list[str]; working_set_chars: int`. Tests construct it positionally (`FocusedResult("April 27 answer [E1]", ["E1"], 120)`) — new fields must be **appended with defaults**.
- `focused_synthesize(working_set, *, surface, chat_fn=None, model=None)` at `:763`; builds `messages`, calls `chat_fn(model=…, messages=…, think=False, options={"temperature":0.7,"num_predict":4096})` at `:790`, parses `reply` + `cited_ids`, returns `FocusedResult`.
- Daemon: `_rk_turn_kind` computed at `daemon/maez_daemon.py:4435` (before the focused block); `_focused_result = _focused_synthesize(...)` at `:4679`; `_record_focused_cognition_run(...)` at `:4703`. The working set is `_focused_working_set`; `evidence_item_count = len(_focused_working_set.items)`, `working_set_chars` + `citation_render_version` are attributes used in the existing `focused_cognition_prompt_shape` emission.
- Existing content-free test pattern: `tests/test_recall_outcome.py` `ContentFreeSchemaTest` (forbidden-field set). Daemon harness: `tests/test_memory_integrity_invariant.py` (`_build_daemon_for_handle_message`, `_handle_message_mock_stack`, mocked `focused_synthesize`).

---

## Task 1: Stage-2 SAFETY contract — tests FIRST (front-load the live-path risk)

**Files:**
- Test: `tests/test_focused_synthesis_timing.py` (new)

- [ ] **Step 1: Write the safety tests (they will fail until Task 2)**

```python
import unittest
from types import SimpleNamespace
from unittest import mock

from core.routing import focused_cognition
from core.routing.focused_cognition import FocusedResult, focused_synthesize


class _WS:
    # minimal WorkingSet stand-in the synth path reads
    def __init__(self, question, evidence_text, chars, render_version):
        self.owner_question = question
        self.ordered_evidence_text = evidence_text
        self.working_set_chars = chars
        self.citation_render_version = render_version
        self.items = (SimpleNamespace(local_label="E1", source_type="memory_context"),)


class FocusedSynthesisTimingTest(unittest.TestCase):
    def _ws(self):
        return _WS("what did we note on April 27?", "[E1] April 27 note", 4242, "v1")

    def _chat_fn(self, reply_text):
        def fn(*, model, messages, think=False, options=None):
            return SimpleNamespace(message=SimpleNamespace(content=reply_text))
        return fn

    def test_reply_and_cited_ids_byte_stable(self):
        # the buffered reply/cited_ids must be exactly what chat_fn produced
        reply = "On April 27 we noted the incident [E1]."
        res = focused_synthesize(self._ws(), surface="telegram", chat_fn=self._chat_fn(reply))
        self.assertEqual(res.reply, reply)
        self.assertEqual(res.cited_ids, ["E1"])

    def test_timing_fields_populated(self):
        res = focused_synthesize(self._ws(), surface="telegram",
                                 chat_fn=self._chat_fn("reply [E1]"))
        self.assertIsInstance(res.prompt_build_ms, int)
        self.assertIsInstance(res.chat_total_ms, int)
        self.assertIsInstance(res.reply_token_est, int)
        self.assertGreaterEqual(res.prompt_build_ms, 0)
        self.assertGreaterEqual(res.chat_total_ms, 0)

    def test_chat_total_dominates_on_slow_chat_fn(self):
        import time as _t
        def slow_fn(*, model, messages, think=False, options=None):
            _t.sleep(0.05)
            return SimpleNamespace(message=SimpleNamespace(content="reply [E1]"))
        res = focused_synthesize(self._ws(), surface="telegram", chat_fn=slow_fn)
        self.assertGreater(res.chat_total_ms, res.prompt_build_ms)
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m unittest tests.test_focused_synthesis_timing -v`
Expected: `test_timing_fields_populated` / `test_chat_total_dominates…` ERROR (`FocusedResult` has no `prompt_build_ms`); `test_reply_and_cited_ids_byte_stable` may already pass (reply/cited_ids logic exists).

- [ ] **Step 3: Commit the contract**

```bash
git add tests/test_focused_synthesis_timing.py
git commit -m "test(focused): pin Stage-2 timing safety contract (byte-stable reply/cited_ids, timing fields)"
```

---

## Task 2: Stage-2 implementation — passive timing + daemon event

**Files:**
- Modify: `core/routing/focused_cognition.py` (`FocusedResult:231`, `focused_synthesize:763-800`)
- Modify: `daemon/maez_daemon.py` (~`:4679-4703`, the post-`focused_synthesize` site)
- Test: `tests/test_memory_integrity_invariant.py` (daemon content-free event test)

- [ ] **Step 1: Add defaulted timing fields to `FocusedResult`**

`core/routing/focused_cognition.py:231` — append three defaulted fields (keeps positional constructions valid):

```python
@dataclass(frozen=True)
class FocusedResult:
    reply: str
    cited_ids: list[str]
    working_set_chars: int
    prompt_build_ms: int | None = None
    chat_total_ms: int | None = None
    reply_token_est: int | None = None
```

- [ ] **Step 2: Capture timing in `focused_synthesize` (buffered call untouched)**

In `focused_synthesize`, wrap the existing flow with `time.monotonic()` stamps — **do not change the `chat_fn(...)` call or its options**. Around `:786-800`:

```python
    import time as _time
    _t0 = _time.monotonic()
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": working_set.owner_question},
    ]
    _t1 = _time.monotonic()
    response = chat_fn(
        model=model,
        messages=messages,
        think=False,
        options={"temperature": 0.7, "num_predict": 4096},
    )
    _t2 = _time.monotonic()
    reply = (getattr(getattr(response, "message", None), "content", None) or "").strip()
    cited_ids = sorted({f"E{match.group(1)}" for match in _CITE_RE.finditer(reply)})
    return FocusedResult(
        reply=reply,
        cited_ids=cited_ids,
        working_set_chars=working_set.working_set_chars,
        prompt_build_ms=int((_t1 - _t0) * 1000),
        chat_total_ms=int((_t2 - _t1) * 1000),
        reply_token_est=len(reply) // 4,
    )
```

(Match the existing `working_set_chars=` argument the current return uses; if the current return computes it differently, keep that computation — only ADD the three timing kwargs.)

- [ ] **Step 2b: Verify the Task-1 unit tests pass**

Run: `.venv/bin/python -m unittest tests.test_focused_synthesis_timing -v`
Expected: OK (all three).

- [ ] **Step 3: Emit the content-free `focused_synthesis_timing` event from the daemon**

At `daemon/maez_daemon.py` immediately after `_focused_result = _focused_synthesize(...)` (~:4679), where `_rk_turn_kind` (:4435) and `_focused_working_set` are in scope, add a content-free log (mirror the `focused_cognition_prompt_shape` style — durations + counts only, NO text):

```python
                            logger.info(
                                "focused_synthesis_timing prompt_build_ms=%s chat_total_ms=%s "
                                "reply_token_est=%s working_set_chars=%s evidence_item_count=%s "
                                "citation_render_version=%s turn_kind=%s",
                                getattr(_focused_result, "prompt_build_ms", None),
                                getattr(_focused_result, "chat_total_ms", None),
                                getattr(_focused_result, "reply_token_est", None),
                                getattr(_focused_working_set, "working_set_chars", None),
                                len(getattr(_focused_working_set, "items", ()) or ()),
                                getattr(_focused_working_set, "citation_render_version", None),
                                _rk_turn_kind,
                            )
```

> Place it inside the same `try`/block that already holds `_focused_result` so it only fires when a focused result exists. Do NOT add any field beyond the seven. Do NOT log `reply`, evidence text, or `owner_question`.

- [ ] **Step 4: Write the daemon content-free event test**

Add to `tests/test_memory_integrity_invariant.py` (model on `test_both_shaped_memory_plus_dialogue_logs_mixed_support`): drive a focused turn whose mocked `focused_synthesize` returns a `FocusedResult` with a **sentinel reply** and timing fields; assert a `focused_synthesis_timing` log line exists, contains the seven field names, and does **NOT** contain the sentinel reply text or evidence text.

```python
    def test_focused_synthesis_timing_is_content_free(self):
        from daemon import maez_daemon
        from core.routing.focused_cognition import FocusedResult, GroundednessVerdict

        SENTINEL = "ZZSECRETREPLYZZ"
        daemon = self._build_daemon_for_handle_message()
        focused_result = FocusedResult(
            reply=f"{SENTINEL} [E1]", cited_ids=["E1"], working_set_chars=10,
            prompt_build_ms=2, chat_total_ms=5000, reply_token_est=4,
        )
        with self.assertLogs("maez", level="INFO") as logs:
            with self._handle_message_mock_stack(maez_daemon, {}), mock.patch.dict(
                os.environ, {"MAEZ_RECALL_TRIAD_ENABLED": "1"}, clear=False
            ), mock.patch(
                "core.routing.focused_cognition.focused_synthesize", return_value=focused_result,
            ), mock.patch(
                "core.routing.focused_cognition.check_groundedness",
                return_value=GroundednessVerdict("grounded", 1.0, []),
            ):
                maez_daemon.MaezDaemon.handle_message(
                    daemon, "what did we note around April 27?",
                    chat_id="c1", source="telegram",
                    transcript='[memory context]\n<RECALLED id="m" date_match="exact_date">x</RECALLED>',
                )
        timing = [l for l in logs.output if "focused_synthesis_timing" in l]
        self.assertTrue(timing, "expected a focused_synthesis_timing line")
        line = timing[-1]
        for field in ("prompt_build_ms", "chat_total_ms", "reply_token_est",
                      "working_set_chars", "evidence_item_count",
                      "citation_render_version", "turn_kind"):
            self.assertIn(field, line)
        self.assertNotIn(SENTINEL, line)            # no reply text leaked
        self.assertNotIn("RECALLED", line)          # no evidence text leaked
```

- [ ] **Step 5: Run + verify scoreboard byte-stable**

Run: `.venv/bin/python -m unittest tests.test_focused_synthesis_timing tests.test_memory_integrity_invariant -v`
Expected: OK — the new timing/content-free tests pass AND every existing daemon outcome test (mixed-support, continuity-grounded, grounded, absence) stays green (scoreboard byte-stable).

- [ ] **Step 6: Commit**

```bash
git add core/routing/focused_cognition.py daemon/maez_daemon.py tests/test_memory_integrity_invariant.py
git commit -m "feat(focused): passive content-free focused_synthesis_timing (buffered call untouched)"
```

---

## Task 3: Stage-1 offline TTFT/throughput sweep harness

**Files:**
- Create: `scripts/brain_bench/latency_sweep.py`
- Test: `tests/test_latency_sweep.py` (new, smoke-level)

- [ ] **Step 1: Write the smoke test**

```python
import unittest
from types import SimpleNamespace
from scripts.brain_bench import latency_sweep


class LatencySweepTest(unittest.TestCase):
    def test_sweep_produces_attribution_rows(self):
        # stub stream_factory (signature: *, variant, payload) so no real model is needed
        def stub_stream(*, variant, payload):
            yield {"content": "hello "}
            yield {"content": "world"}
        rows = latency_sweep.run_sweep(
            ws_item_counts=(1, 4, 7),
            output_modes=("short", "long"),
            variant=SimpleNamespace(model="stub"),
            stream_factory=stub_stream,
        )
        self.assertTrue(rows)
        r = rows[0]
        for k in ("ws_items", "input_tokens", "output_tokens", "ttft_ms", "total_ms", "tok_s"):
            self.assertIn(k, r)
        self.assertEqual(len(rows), 6)  # 3 ws sizes x 2 output modes
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m unittest tests.test_latency_sweep -v`
Expected: FAIL — `latency_sweep` module does not exist.

- [ ] **Step 3: Implement the sweep harness**

Create `scripts/brain_bench/latency_sweep.py` using the existing `make_benchmark_chat_fn` (returns `(chat_fn, sink)`) and `GenerationMeasurement` (`ttft_ms`, `total_ms`, `output_tokens`, `tokens_per_sec`) over a fabricated working set of N items × two output-length prompts. One attribution row per (ws_items, output_mode):

```python
from __future__ import annotations

from scripts.brain_bench.inference import make_benchmark_chat_fn


def _fab_working_set_text(ws_items: int) -> str:
    return "\n".join(f"[E{i+1}] fabricated evidence line {i+1}" for i in range(ws_items))


def run_sweep(*, ws_item_counts, output_modes, variant, stream_factory=None):
    rows = []
    for ws_items in ws_item_counts:
        evidence = _fab_working_set_text(ws_items)
        for mode in output_modes:
            ask = "Answer in one short sentence." if mode == "short" else "Answer in full detail."
            chat_fn, sink = make_benchmark_chat_fn(variant=variant, stream_factory=stream_factory)
            messages = [
                {"role": "system", "content": f"=== EVIDENCE ===\n{evidence}\n{ask}"},
                {"role": "user", "content": "what did we note?"},
            ]
            chat_fn(model=variant.model, messages=messages, think=False,
                    options={"num_predict": 4096})
            m = sink.last()
            rows.append({
                "ws_items": ws_items,
                "input_tokens": len(evidence) // 4,
                "output_tokens": m.output_tokens,
                "ttft_ms": m.ttft_ms,
                "total_ms": m.total_ms,
                "tok_s": m.tokens_per_sec,
            })
    return rows
```

> `make_benchmark_chat_fn` returns `(chat_fn, sink)` and requires `variant` (uses `variant.model` in the payload); a `SimpleNamespace(model=…)` duck-types it for the stub test, and the real run passes the actual `Variant`. The bench `chat_fn` signature is `(*, model, messages, think, options)`. Keep the row keys exactly as the test asserts. Thin experiment harness — no live-path import.

- [ ] **Step 4: Run to verify pass**

Run: `.venv/bin/python -m unittest tests.test_latency_sweep -v`
Expected: OK.

- [ ] **Step 5: Commit**

```bash
git add scripts/brain_bench/latency_sweep.py tests/test_latency_sweep.py
git commit -m "feat(brain_bench): offline latency-attribution sweep harness (TTFT/throughput x ws-volume)"
```

---

## Task 4: Regression sweep + floor both directions

**Files:** none (verification)

- [ ] **Step 1: Targeted suites**

Run: `.venv/bin/python -m unittest tests.test_focused_synthesis_timing tests.test_latency_sweep tests.test_recall_outcome tests.test_memory_integrity_invariant -v`
Expected: OK.

- [ ] **Step 2: Broad discover (floor both directions)**

Run: `.venv/bin/python -m unittest discover -s tests -p "test_*.py" -q`
Expected: **zero branch-only failures.** Diff any broad-suite red against base in a **clean base checkout or the existing isolated worktree** (NOT `git stash`). Name any failure this branch introduces; confirm residual red is pre-existing (known trio: `egress_external_fetch_inventory`, `slice_3_5_envelope_wiring`, `smoke_imports`).

- [ ] **Step 3: Lint + import sanity**

Run: `.venv/bin/python -m ruff check core/routing/focused_cognition.py daemon/maez_daemon.py scripts/brain_bench/latency_sweep.py tests/test_focused_synthesis_timing.py tests/test_latency_sweep.py`
Run: `.venv/bin/python -c "import core.routing.focused_cognition, daemon.maez_daemon, scripts.brain_bench.latency_sweep; print('ok')"`
Expected: clean; `ok`.

- [ ] **Step 4: Final commit (only if a sweep fix was needed)**

```bash
git add -A
git commit -m "chore(focused): latency-attribution measurement slice green"
```

---

## Stage 3 (RECORDED — NOT built in this slice)

If Stages 1+2 leave TTFT ambiguous (e.g. `chat_total_ms` large but warmup-vs-generation unsplit), a follow-up adds a **default-off** measurement flag that switches the focused call to hidden streaming for live `ttft_ms` — requiring a test proving the `core/routing/llm_client.py` `chat(stream=…)` + llama.cpp streaming-adapter seam first, then a deliberate smoke. Out of scope here.

---

## Cross-lane verification gate (Claude, before merge — NOT optional)

1. **Buffered call untouched** — `chat_fn(...)` invocation + `options` byte-identical; only `time.monotonic()` stamps added around it.
2. **Scoreboard byte-stable** — `FocusedResult.reply`/`cited_ids` unchanged; all existing daemon outcome tests (mixed/continuity/grounded/absence) green; new `FocusedResult` fields are defaulted (positional constructions intact).
3. **Content-free** — `focused_synthesis_timing` has exactly the seven fields; the sentinel test proves no reply/evidence/question text leaks.
4. **No fix snuck in** — no trim/cap/rank, no `num_predict` change, no model/runtime edit; the offline harness imports no live-path module.
5. **Floor both directions** vs base; suites independently; coverage panel.
6. Merge on legacy baseline. **Recall off.** Then: run the sweep + collect one owner-run smoke's `focused_synthesis_timing` → read the attribution → open the fix slice's brainstorm with the lever chosen by data.
```
