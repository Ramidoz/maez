# Brain Gateway — Preempt Effectiveness (Handle-Install Timing) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make a foreground brain call (e.g. `owner_recall`) preempt an in-flight background cycle and own the single llama-server slot **sub-second**, by ensuring a cancellable handle exists *before* the background's stream-start blocks through prompt-eval.

**Architecture:** Measurement-first. A content-free `brain_gateway_preempt_probe` diagnostic proves the `handle_state=missing` gap live; a hermetic RED test pins the requirement that a cancellable handle must be obtainable before the blocking network read; the fix gives the llama-server transport a connection handle that is closeable during prompt-eval (F2 raw streaming POST, the probe-proven path) — or, only if a microprobe shows the existing SDK already exposes an early handle, a smaller reorder (F1). No MTP, no second slot, no prompt trimming.

**Tech Stack:** Python 3.14, `unittest` (NO pytest), `requests` (already a dep), llama-server OpenAI-compatible endpoint at `http://127.0.0.1:8080/v1`, existing `core/routing/brain_gateway.py` + `core/routing/cancellable_brain_call.py` + `core/routing/llm_client.py`.

**Spec:** `docs/superpowers/specs/2026-06-01-brain-gateway-preempt-effectiveness-design.md`

**Lane:** Codex implements (6-agent + 7+3); Claude cross-verifies (reads every diff, runs the suite independently, fires the coverage panel, floors both directions); Rohit owner-runs the live diagnostic + acceptance gate. **Recall stays OFF the entire slice.**

---

## File Structure

- `core/routing/brain_gateway.py` — add the content-free `brain_gateway_preempt_probe` emission inside `_reserve_slot`; no scheduler-logic change in the diagnostic task.
- `core/routing/llm_client.py` — the fix surface: `_start_llamacpp_stream` (and/or a new `_start_llamacpp_stream_raw`) must return a closeable handle before the response body is read.
- `core/routing/cancellable_brain_call.py` — unchanged unless the RED test reveals the wrapper needs the raw close handle surfaced differently (it already forwards `.close()`).
- `tests/test_brain_gateway_preempt_probe.py` — NEW: asserts the diagnostic fires with `handle_state=missing` when the background factory blocks, content-free.
- `tests/test_transport_early_handle.py` — NEW: the RED test — a fake stream-start that blocks before returning; the cancellable handle must be obtainable + closeable before the block releases.
- `tests/test_brain_gateway_forced_collision.py` — extend with a `factory-blocks-before-return` collision case (currently only the `__iter__`-blocks case is covered).
- `tools/probes/llamacpp_stream_handle_microprobe.py` — NEW owner-run probe (NOT a unit test): does `create(stream=True)` return a closeable handle before first SSE token? The F1-vs-F2 decider.

---

## Task 1: Diagnostic — `brain_gateway_preempt_probe` (content-free)

**Files:**
- Modify: `core/routing/brain_gateway.py` (`_reserve_slot`, ~`:197-216`)
- Test: `tests/test_brain_gateway_preempt_probe.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_brain_gateway_preempt_probe.py
import threading
import time
import unittest

from core.routing.brain_gateway import BrainGateway, BrainPurpose
from core.routing.cancellable_brain_call import BrainPreempted


class PreemptProbeTest(unittest.TestCase):
    def test_probe_reports_missing_handle_while_factory_blocks(self):
        gateway = BrainGateway(preempt_timeout_s=0.5)
        bg_started = threading.Event()
        release = threading.Event()

        def bg_stream():
            # Model the live bug: the factory itself blocks (prompt-eval)
            # BEFORE returning a stream object, so record.call stays None.
            bg_started.set()
            release.wait(timeout=2.0)
            return iter([{"content": "late background"}])

        def run_bg():
            try:
                gateway.submit(
                    purpose=BrainPurpose.DAEMON_CYCLE_GENERATION,
                    run_streaming_fn=bg_stream,
                )
            except BrainPreempted:
                pass

        worker = threading.Thread(target=run_bg)
        worker.start()
        self.assertTrue(bg_started.wait(timeout=2.0))

        def run_fg():
            gateway.submit(
                purpose=BrainPurpose.OWNER_RECALL,
                run_streaming_fn=lambda: iter([{"content": "fast [E1]"}]),
            )

        fg = threading.Thread(target=run_fg)
        fg.start()
        time.sleep(0.2)  # let the foreground spin against the None handle
        release.set()
        fg.join(timeout=3.0)
        worker.join(timeout=3.0)

        probes = [e for e in gateway.events
                  if e.get("event") == "brain_gateway_preempt_probe"]
        self.assertTrue(probes, "no preempt-probe event emitted")
        self.assertTrue(any(p["handle_state"] == "missing" for p in probes))
        # content-free: no prompt/reply/token text anywhere in the event
        for p in probes:
            self.assertEqual(
                set(p) - {"event"},
                {"schema_version", "purpose", "current_purpose",
                 "handle_state", "wait_ms", "preempt_attempts"},
            )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/bin/python -m unittest tests.test_brain_gateway_preempt_probe -v`
Expected: FAIL — no `brain_gateway_preempt_probe` event exists yet.

- [ ] **Step 3: Emit the probe inside `_reserve_slot`**

In `core/routing/brain_gateway.py`, inside the `if priority > current.priority:` branch of `_reserve_slot` (after `preempted_count += 1` at `:209`), emit a content-free probe. Add a small helper and call it there:

```python
                if priority > current.priority:
                    current.cancel_requested = True
                    call_to_cancel = current.call
                    preempted_count += 1
                    self._emit_preempt_probe(
                        purpose=purpose,
                        current_purpose=current.purpose,
                        handle_state="missing" if current.call is None else "present",
                        wait_ms=(time.monotonic() - _probe_t0) * 1000.0,
                        preempt_attempts=preempted_count,
                    )
```

Capture `_probe_t0 = time.monotonic()` once at the top of `_reserve_slot` (before the `while True:`). Then add the emitter (content-free, mirrors `_emit_event`'s discipline):

```python
    def _emit_preempt_probe(
        self,
        *,
        purpose: BrainPurpose,
        current_purpose: BrainPurpose,
        handle_state: str,
        wait_ms: float,
        preempt_attempts: int,
    ) -> None:
        event = {
            "event": "brain_gateway_preempt_probe",
            "schema_version": 1,
            "purpose": purpose.value,
            "current_purpose": current_purpose.value,
            "handle_state": handle_state,
            "wait_ms": round(wait_ms, 3),
            "preempt_attempts": int(preempt_attempts),
        }
        self.events.append(event)
        logger.info(
            "brain_gateway_preempt_probe schema_version=%s purpose=%s "
            "current_purpose=%s handle_state=%s wait_ms=%s preempt_attempts=%s",
            event["schema_version"], event["purpose"], event["current_purpose"],
            event["handle_state"], event["wait_ms"], event["preempt_attempts"],
        )
        if self._telemetry_sink is not None:
            self._telemetry_sink(dict(event))
```

Note: the existing `_emit_event` events have no `"event"` key; add `"event": "brain_gateway_event"` to `_emit_event`'s dict in the same task so consumers can filter both event kinds. Update `tests/test_brain_gateway*.py` assertions that index `gateway.events` to filter on `event.get("event") == "brain_gateway_event"` where they currently assume every entry is the main event (check `test_brain_gateway_forced_collision.py:55-57` and `test_brain_gateway_equivalence.py`).

**Witnessed schema evolution (discipline, not churn):** adding `"event"` changes the `brain_gateway_event` shape, even if additively. Update the content-free schema assertion(s) **explicitly and in this same commit** so the diff shows the schema changed on purpose — both events keep `schema_version=1` but now carry an `"event"` discriminator, and the probe's field set is asserted exactly (`schema_version/event/purpose/current_purpose/handle_state/wait_ms/preempt_attempts` — no prompt/reply/token text). Do not let the schema drift in silently by relying on missing-key inference. ([[feedback_canon_governs_canon_witness_before_claim]] applied to the telemetry surface.)

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/python -m unittest tests.test_brain_gateway_preempt_probe -v`
Expected: PASS.

- [ ] **Step 5: Run the full gateway suite to catch the events-shape change**

Run: `.venv/bin/python -m unittest tests.test_brain_gateway tests.test_brain_gateway_forced_collision tests.test_brain_gateway_equivalence tests.test_brain_gateway_routing tests.test_cancellable_brain_call -v`
Expected: PASS (after updating the `events` filters in Step 3).

- [ ] **Step 6: Commit**

```bash
git add core/routing/brain_gateway.py tests/test_brain_gateway_preempt_probe.py tests/test_brain_gateway_forced_collision.py tests/test_brain_gateway_equivalence.py
git commit -m "feat(brain-gateway): content-free preempt-probe diagnostic (handle_state)"
```

---

## Task 2: RED test — cancellable handle must exist before the stream-start blocks

**Files:**
- Test: `tests/test_transport_early_handle.py` (create)
- (No production change in this task — the test must be RED.)

- [ ] **Step 1: Write the failing test against the real transport seam**

```python
# tests/test_transport_early_handle.py
import threading
import time
import unittest
from unittest import mock

import core.routing.llm_client as llm_client


class EarlyHandleTest(unittest.TestCase):
    """start_cancellable_chat must return a closeable handle BEFORE the
    server finishes prompt-eval — i.e. without blocking on the response body."""

    def test_handle_available_before_first_token(self):
        release = threading.Event()

        class _FakeRawStream:
            """Models the llama-server stream: iterating blocks until prompt-eval
            completes (release), but .close() is available immediately."""
            def __init__(self):
                self.closed = False
            def __iter__(self):
                while not release.wait(timeout=0.05):
                    pass
                yield {"choices": [{"delta": {"content": "hi"}}]}
            def close(self):
                self.closed = True
                release.set()

        def fake_create(*args, **kwargs):
            # A COMPLIANT transport returns the stream object immediately;
            # the current openai-SDK path returns only after prompt-eval.
            return _FakeRawStream()

        with mock.patch.object(llm_client, "active_backend",
                               return_value=llm_client.BACKEND_LLAMACPP), \
             mock.patch.object(llm_client, "_get_openai_client") as gc:
            gc.return_value.chat.completions.create.side_effect = fake_create

            handle_box = {}
            def start():
                handle_box["call"] = llm_client.start_cancellable_chat(
                    model="m", messages=[{"role": "user", "content": "x"}],
                    think=False,
                )
            t = threading.Thread(target=start)
            t.start()
            t.join(timeout=1.0)

            # The handle must be obtainable BEFORE release is set (before
            # prompt-eval completes). A blocking-factory transport fails here.
            self.assertIn("call", handle_box, "handle not available before first token")
            self.assertTrue(hasattr(handle_box["call"], "cancel"))
            # And cancelling must free the (modeled) connection promptly.
            t0 = time.monotonic()
            handle_box["call"].cancel()
            self.assertLess((time.monotonic() - t0) * 1000, 800)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run it to confirm it characterizes the gap**

Run: `.venv/bin/python -m unittest tests.test_transport_early_handle -v`
Expected with the *fake-immediate* `create`: this specific fake returns fast, so it may PASS — meaning it proves the **gateway/transport contract is satisfiable**. To make it a true RED for the *current live* behavior, add a second test method that models the SDK blocking in `create()`:

```python
    def test_blocking_create_delays_handle(self):
        """Faithful model of the live openai SDK: create() blocks until
        prompt-eval ends. Asserts the failure we must fix."""
        release = threading.Event()
        def blocking_create(*args, **kwargs):
            release.wait(timeout=2.0)         # blocks like create() during prompt-eval
            return iter([{"choices": [{"delta": {"content": "hi"}}]}])
        with mock.patch.object(llm_client, "active_backend",
                               return_value=llm_client.BACKEND_LLAMACPP), \
             mock.patch.object(llm_client, "_get_openai_client") as gc:
            gc.return_value.chat.completions.create.side_effect = blocking_create
            handle_box = {}
            def start():
                handle_box["call"] = llm_client.start_cancellable_chat(
                    model="m", messages=[{"role": "user", "content": "x"}], think=False)
            t = threading.Thread(target=start); t.start(); t.join(timeout=0.5)
            # CURRENT code: handle is NOT available yet -> RED.
            # After F2 (raw transport that exposes the connection before the
            # body): handle IS available -> GREEN.
            self.assertIn("call", handle_box,
                          "RED until the transport exposes an early close handle")
            release.set(); t.join(timeout=2.0)
```

Run again. Expected: `test_blocking_create_delays_handle` FAILS on current `main` (handle absent at join) — this is the RED that the fix turns GREEN.

- [ ] **Step 3: Observe RED — do NOT commit yet**

Record the failure output in the slice notes as evidence the gap is real. **Do not land a standalone red commit before the owner-run CHECKPOINT.** This file stays uncommitted (or staged-only) until the selected F1/F2 implementation makes it pass; it is committed *together with* the GREEN fix in Task 3a Step 3 / Task 3b Step 4. This keeps the tree green at every commit and avoids a dangling red between the RED test and the evidence-gated fix.

---

## CHECKPOINT (owner-run): read the live diagnostic + microprobe before choosing F1 vs F2

- [ ] **Step 1: Build the transport microprobe (owner-run, not a unit test)**

```python
# tools/probes/llamacpp_stream_handle_microprobe.py
"""Owner-run: does create(stream=True) return a closeable handle BEFORE the
first SSE token (i.e. before prompt-eval ends)? Decides F1 vs F2.
Run with the live llama-server up. Content-free; prints timings only."""
import time
from core.routing.llm_client import _get_openai_client, LLAMACPP_MODEL

BIG = "The history of computing is long and detailed. " * 1800  # ~21k tokens

def main():
    t0 = time.monotonic()
    stream = _get_openai_client().chat.completions.create(
        model=LLAMACPP_MODEL,
        messages=[{"role": "user", "content": BIG}],
        max_tokens=8, stream=True,
        extra_body={"chat_template_kwargs": {"enable_thinking": False}},
    )
    create_ms = (time.monotonic() - t0) * 1000
    has_close = hasattr(stream, "close")
    print(f"create_returned_ms={create_ms:.0f} has_close={has_close}")
    # If create_returned_ms << prompt-eval time -> SDK exposes early handle (F1 viable).
    # If create_returned_ms ~= time-to-first-token -> SDK blocks (F2 required).
    t1 = time.monotonic()
    for _ in stream:
        break
    print(f"first_token_after_create_ms={(time.monotonic()-t1)*1000:.0f}")
    stream.close()

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Owner runs the live forced-collision diagnostic** — with the daemon up + a real cycle in flight, fire a foreground recall and read `brain_gateway_preempt_probe` from the daemon log. Record whether `handle_state=missing` persists through the wait.

- [ ] **Step 3: Decide (evidence-gated, per spec §5):**
  - If the microprobe shows `create_returned_ms` is small (handle available well before first token) **and** the live probe shows `handle_state=present` → the bug is pure gateway ordering → **F1 (Task 3a)**.
  - If `create_returned_ms ≈ time-to-first-token` (SDK blocks through prompt-eval) → **F2 (Task 3b)**. This is the expected path: the live 10-15s wait + `handle_state=missing` already imply `create()` blocks.
  - **No SDK heroics** either way.

---

## Task 3a (only if CHECKPOINT selects F1): install the handle before the blocking start

**Files:**
- Modify: `core/routing/llm_client.py` (`start_cancellable_chat`, `_start_llamacpp_stream`)

- [ ] **Step 1:** Split `_start_llamacpp_stream` so the closeable stream object is obtained and wrapped in `CancellableBrainCall` **before** any blocking body read, and `start_cancellable_chat` returns that handle immediately. (Only valid if the microprobe proved the SDK hands back the closeable stream before first token.)
- [ ] **Step 2:** Run `tests.test_transport_early_handle` → both methods GREEN.
- [ ] **Step 3:** Commit the fix **together with** the previously-uncommitted RED test (so the tree is green at this commit): `git add core/routing/llm_client.py tests/test_transport_early_handle.py && git commit -m "feat(transport): expose llama-server close handle before first token (F1 reorder)"`.

*(If the CHECKPOINT selects F2, skip Task 3a entirely.)*

---

## Task 3b (expected fix — F2 raw streaming transport)

**Files:**
- Modify: `core/routing/llm_client.py` (`_start_llamacpp_stream` → raw `requests` streaming POST)
- Test: `tests/test_transport_early_handle.py` (turns GREEN), `tests/test_brain_gateway_equivalence.py` (byte-equivalence still holds)

- [ ] **Step 1: Implement a raw streaming POST that exposes `.close()` immediately**

Replace the openai-SDK stream-start in `_start_llamacpp_stream` with a raw streaming POST whose `Response` (and underlying socket) is returned right after headers, before the body is read:

```python
import json
import requests

class _LlamaCppRawSSEStream:
    """Raw SSE stream over a requests.Response; .close() frees the socket
    immediately (probe-proven ~440ms slot release), even during prompt-eval."""

    def __init__(self, response: "requests.Response"):
        self._response = response

    def close(self):
        # Closing the underlying connection is what frees the server slot.
        self._response.close()

    def __iter__(self):
        for line in self._response.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data:"):
                continue
            payload = line[len("data:"):].strip()
            if payload == "[DONE]":
                break
            try:
                obj = json.loads(payload)
                delta = obj["choices"][0]["delta"]
                token = delta.get("content") or ""
                token = _strip_special_tokens(token)
            except Exception:
                token = ""
            yield _LlmResponse(message=_LlmMessage(content=token, thinking=None))


def _start_llamacpp_stream(*, model, messages, temperature, max_tokens,
                           extra_body, timeout_s=None):
    body = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
    }
    if extra_body:
        body.update(extra_body)
    # stream=True returns the Response after headers, before the body is read,
    # so the connection handle (and .close()) is available during prompt-eval.
    response = requests.post(
        f"{LLAMACPP_BASE_URL}/chat/completions",
        json=body,
        headers={"Authorization": "Bearer llamacpp"},
        stream=True,
        timeout=timeout_s,
    )
    response.raise_for_status()
    return _LlamaCppRawSSEStream(response)
```

Keep `_LlamaCppStreamAdapter` for any non-cancellable callers, or route them through the same raw stream — confirm via the existing `chat(stream=...)` callers that nothing else depends on the openai-SDK stream object shape.

- [ ] **Step 2: Run the RED test → GREEN**

Run: `.venv/bin/python -m unittest tests.test_transport_early_handle -v`
Expected: BOTH methods PASS (handle available before the modeled prompt-eval completes; cancel frees it promptly). Update `test_blocking_create_delays_handle` to patch `requests.post` instead of the openai client, mirroring the new transport.

- [ ] **Step 3: Byte-equivalence — buffered reply unchanged**

Run: `.venv/bin/python -m unittest tests.test_brain_gateway_equivalence -v`
Expected: PASS — a non-preempted background reply assembled from the raw SSE stream equals the prior path's reply for the same chunk sequence. If the equivalence test fakes the openai client, add/adjust a fake `requests.post` returning an SSE-shaped iterator so the test exercises the new transport.

- [ ] **Step 4: Commit**

```bash
git add core/routing/llm_client.py tests/test_transport_early_handle.py tests/test_brain_gateway_equivalence.py
git commit -m "feat(transport): raw SSE stream exposes close handle during prompt-eval (F2)"
```

---

## Task 4: Forced-collision GREEN — assert the FIXED transport contract

**Upfront, stated assumption (not a discovered risk):** a literally-blocking `run_streaming_fn()` **cannot** be made preemptible by gateway logic alone — the gateway has no object to close until the factory returns, which is the entire bug at [`brain_gateway.py:145`](../../../core/routing/brain_gateway.py#L145). With one server slot, the slot only frees when the **socket** closes, and the socket handle does not exist until the factory yields it. Therefore the fix is necessarily transport-level: **the transport factory must return a closeable handle fast and do its blocking in iteration/body-read.** This task asserts that *fixed contract*; it does NOT challenge Codex to preempt an impossible blocking factory.

**Files:**
- Test: `tests/test_brain_gateway_forced_collision.py` (extend)

- [ ] **Step 1: Add a collision test against a COMPLIANT (fixed-contract) factory**

The factory returns its stream object **immediately** (closeable handle available); the heavy work (modeling prompt-eval) happens inside `__iter__`. This is the contract F1/F2 must satisfy. The foreground must preempt sub-second.

```python
    def test_foreground_preempts_when_factory_returns_handle_fast(self):
        """Fixed-contract collision: stream-start returns a closeable handle
        immediately and blocks only in iteration; foreground wins sub-second.
        (A literally-blocking factory is out of scope by design — see the
        transport tests in test_transport_early_handle.py.)"""
        gateway = BrainGateway(preempt_timeout_s=0.5)
        bg_started = threading.Event()
        bg_outcome = {}

        def bg_stream():
            gate = threading.Event()

            class _Stream:
                def __iter__(self):
                    bg_started.set()
                    while not gate.wait(timeout=0.05):   # models prompt-eval/body read
                        pass
                    yield {"content": "late"}

                def close(self):                          # frees the slot
                    gate.set()

            return _Stream()                              # handle available NOW

        def run_bg():
            try:
                gateway.submit(purpose=BrainPurpose.DAEMON_CYCLE_GENERATION,
                               run_streaming_fn=bg_stream)
            except BrainPreempted:
                bg_outcome["preempted"] = True

        worker = threading.Thread(target=run_bg); worker.start()
        self.assertTrue(bg_started.wait(timeout=2.0))
        t0 = time.monotonic()
        reply = gateway.submit(purpose=BrainPurpose.OWNER_RECALL,
                               run_streaming_fn=lambda: iter([{"content": "fast [E1]"}]))
        fg_ms = (time.monotonic() - t0) * 1000
        worker.join(timeout=2.0)
        self.assertEqual(reply, "fast [E1]")
        self.assertLess(fg_ms, 1500)            # sub-second-ish, not 10-15s
        self.assertTrue(bg_outcome.get("preempted"))
```

Note: this is the same shape as the existing `test_foreground_preempts_inflight_background` — that's intentional. The existing test already proves the gateway logic is correct **given a compliant transport**. The whole slice is about making the *live transport* compliant (Task 3a/3b). This test is the contract guard; the transport tests in `test_transport_early_handle.py` are where the broken-vs-fixed transport behavior is actually exercised.

- [ ] **Step 2:** Run it. PASS on the compliant fake (confirms the gateway honors the contract). The broken→fixed transition is owned by `test_transport_early_handle.py` (Task 2 RED → Task 3 GREEN), not here.

- [ ] **Step 3: Commit** `test(brain-gateway): forced-collision guards the fixed transport contract`.

---

## Task 5: Regression sweep + acceptance-gate harness

**Files:**
- Test: full suite; floor both directions.

- [ ] **Step 1: No-bypass invariant still holds** — run the no-bypass test (every owner/cycle brain call routes through the gateway). Expected: PASS.
- [ ] **Step 2: Full brain-gateway + propagation suite**

Run: `.venv/bin/python -m unittest tests.test_brain_gateway tests.test_brain_gateway_routing tests.test_brain_gateway_forced_collision tests.test_brain_gateway_equivalence tests.test_brain_preempt_propagation tests.test_cancellable_brain_call tests.test_brain_gateway_preempt_probe tests.test_transport_early_handle -v`
Expected: ALL PASS.

- [ ] **Step 3: Floor both directions** — run the broader discover on a clean checkout (NOT git stash). Name the known-unrelated flaky trio (egress / web-slice / import-shim secrets cascade) explicitly; assert no NEW failures attributable to this slice.

- [ ] **Step 4: Acceptance-gate note (owner-run, separate)** — document the live procedure: daemon up, cognition active, fire the six-prompt smoke + a forced collision; assert `owner_recall wait_ms` sub-second, background `preempted=True`, no retry, no partial store, `preempt_timeout=false`, A7 ~12s p95 holds, Maez voice + inner-life intact. **This is owner-run; recall stays OFF — the gate proves preempt effectiveness, it does not flip recall.**

- [ ] **Step 5: Commit** `test(brain-gateway): preempt-effectiveness regression sweep + acceptance note`.

---

## Self-Review

- **Spec coverage:** §3 diagnostic → Task 1; §4 RED test → Task 2; §5 fix tree (F1/F2 gated) → CHECKPOINT + Task 3a/3b; §6 invariants (no-bypass, content-free, reschedule) → Task 1 content-free assertion + Task 5 Step 1; §7 acceptance → Task 5 Step 4; §8 hermetic-first + unittest + floor → Tasks 1-2 hermetic, Task 5 Step 3.
- **Measurement-first honored:** no fix lands before the CHECKPOINT reads the live diagnostic + microprobe.
- **No placeholders:** every code step carries real code; F1/F2 are both concrete, selected by the CHECKPOINT (a branch, not a TBD).
- **Green at every commit:** the RED test (Task 2) is observed but not committed standalone; it lands with the GREEN fix in Task 3a/3b.
- **Stated assumption (not a discovered risk):** a literally-blocking factory cannot be preempted by gateway logic alone (single slot frees only on socket close; the handle does not exist until the factory returns). The fix is necessarily transport-level — the factory must return a closeable handle fast and block in iteration. Task 4 asserts that fixed contract; the broken→fixed transport transition lives in `test_transport_early_handle.py`. Codex should not attempt gateway gymnastics to preempt a blocking factory.
