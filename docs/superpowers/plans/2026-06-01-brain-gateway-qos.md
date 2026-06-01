# Brain Gateway (QoS / Priority Preemption) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A foreground (owner-visible) brain call preempts Maez's in-flight background cognition so it gets the single llama-server slot within ~hundreds of ms — curing the recall-on latency No-Go (periodic GPU-slot self-contention).

**Architecture:** A new `BrainGateway` module owns access to the 27B server. Every brain call routes through it as a typed request keyed on a **closed `BrainPurpose` enum** → derived priority. Foreground preempts in-flight background by **closing the background's streaming connection** (proven to free the slot ~230ms). Background runs the streaming adapter internally but returns one buffered string to callers; preemption raises a distinct `BrainPreempted` exception that outranks every broad `except`. Cancelled thoughts **reschedule, not resume**.

**Tech Stack:** Python 3.14, **`unittest`** (no pytest), `threading`/`contextvars`, the existing llama.cpp OpenAI-compatible streaming adapter.

**Spec:** [docs/superpowers/specs/2026-06-01-brain-gateway-qos-design.md](../specs/2026-06-01-brain-gateway-qos-design.md) (10 pins).

**Process:** Codex switchboard (six-agent + 7+3). Claude cross-verifies every diff, runs suites independently, fires the coverage panel before merge on the legacy baseline. **The most concurrency-heavy slice of the arc — thread-safety is the risk; Stage-0 proves the primitive before anything is built on it.** Recall stays off throughout.

**Hard invariants:**
- Recall flag off; brain-agnostic; substrate-side. **Maez's inner life is not thinned** — cancelled cycles reschedule (rerun from source), never delete.
- **No side door:** no owner/cycle path reaches the backend without the gateway (tested).
- **Zero `neutral`** on both the owner-reply path and the autonomous cycle (tested both directions).
- `BrainPreempted` never becomes a `BackendError`/retry — at `:3493` *and* every nested broad `except`.
- Non-preempted buffered reply byte-equivalent to the old path.

---

## Task 1: Stage-0 — `CancellableBrainCall` + hermetic cross-thread cancel proof (FIRST)

Prove the primitive on a **fake stream** (no live llama-server) before the gateway depends on it.

**Files:**
- Create: `core/routing/cancellable_brain_call.py`
- Test: `tests/test_cancellable_brain_call.py`

- [ ] **Step 1: Write the hermetic failing tests**

A fake stream models the two dangerous states — *blocked before first token* (prompt-processing, the 21s case) and *blocked mid-generation* — using a `threading.Event` to gate chunk delivery, so a second thread can cancel while the consumer is blocked.

```python
import threading, time, unittest
from core.routing.cancellable_brain_call import CancellableBrainCall, BrainPreempted


class _FakeStream:
    """Iterable that blocks until released; models llama.cpp SSE chunks.
    close() unblocks the consumer with a StopIteration-like end (server disconnect)."""
    def __init__(self, chunks, block_before_first=True):
        self._chunks = list(chunks)
        self._gate = threading.Event()
        self._closed = threading.Event()
        self._block_before_first = block_before_first

    def release(self):
        self._gate.set()

    def close(self):
        self._closed.set()
        self._gate.set()  # unblock any waiter so it can observe closure

    def __iter__(self):
        first = True
        for c in self._chunks:
            if first and self._block_before_first:
                while not self._gate.wait(timeout=0.05):
                    if self._closed.is_set():
                        return  # server disconnect before first token
            if self._closed.is_set():
                return
            first = False
            yield c


class CancellableBrainCallTest(unittest.TestCase):
    def test_cancel_before_first_token_unblocks_and_closes(self):
        fs = _FakeStream([{"content": "hi"}], block_before_first=True)
        call = CancellableBrainCall(raw_stream=fs)
        result = {}
        def consume():
            try:
                result["reply"] = call.collect()  # blocks waiting for first token
            except BrainPreempted:
                result["preempted"] = True
        t = threading.Thread(target=consume); t.start()
        time.sleep(0.1)                      # consumer is blocked pre-first-token
        call.cancel()                        # cross-thread cancel
        t.join(timeout=2.0)
        self.assertFalse(t.is_alive())       # cancel actually unblocked it
        self.assertTrue(result.get("preempted"))

    def test_cancel_mid_generation(self):
        fs = _FakeStream([{"content": "a"}, {"content": "b"}, {"content": "c"}], block_before_first=False)
        call = CancellableBrainCall(raw_stream=fs)
        # let it emit one chunk, then cancel
        gen = call.iter_tokens()
        next(gen)
        call.cancel()
        with self.assertRaises(BrainPreempted):
            for _ in gen:
                pass

    def test_cancel_is_idempotent_and_synchronous(self):
        fs = _FakeStream([{"content": "x"}], block_before_first=True)
        call = CancellableBrainCall(raw_stream=fs)
        call.cancel()
        call.cancel()  # second cancel harmless
        self.assertTrue(call.cancelled)

    def test_preempt_timeout_is_not_success(self):
        # a stream that refuses to close within the budget -> preempt_timeout, logged, NOT silent success
        class _StuckStream(_FakeStream):
            def close(self):  # never actually unblocks
                pass
        call = CancellableBrainCall(raw_stream=_StuckStream([{"content": "x"}]), preempt_timeout_s=0.2)
        timed_out = call.cancel()
        self.assertTrue(timed_out)  # cancel() returns True == preempt_timeout occurred
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m unittest tests.test_cancellable_brain_call -v`
Expected: ImportError (`cancellable_brain_call` does not exist).

- [ ] **Step 3: Implement `CancellableBrainCall`**

`core/routing/cancellable_brain_call.py`: wraps the raw streaming object, exposes `.cancel()` (closes `raw_stream` + sets a cancelled flag; idempotent; returns `True` iff the close did not complete within `preempt_timeout_s`), `.collect()` (assemble full buffered reply; raise `BrainPreempted` if cancelled before/while collecting), `.iter_tokens()` (yield tokens, raise `BrainPreempted` after cancel). `BrainPreempted` is a distinct `Exception` subclass (NOT `BackendError`).

```python
import threading


class BrainPreempted(Exception):
    """Raised when a brain call was deliberately preempted. NOT an error — reschedule."""


class CancellableBrainCall:
    def __init__(self, *, raw_stream, preempt_timeout_s: float = 1.5):
        self._raw = raw_stream
        self._timeout = preempt_timeout_s
        self._cancelled = threading.Event()
        self._closed = threading.Event()

    @property
    def cancelled(self) -> bool:
        return self._cancelled.is_set()

    def cancel(self) -> bool:
        """Idempotent, synchronous. Returns True iff a preempt_timeout occurred."""
        self._cancelled.set()
        closer = getattr(self._raw, "close", None)
        if closer is not None:
            t = threading.Thread(target=closer, daemon=True)
            t.start()
            t.join(timeout=self._timeout)
            if t.is_alive():
                return True  # preempt_timeout — caller must treat as gate failure, not success
        self._closed.set()
        return False

    def iter_tokens(self):
        try:
            for chunk in self._raw:
                if self._cancelled.is_set():
                    raise BrainPreempted()
                token = chunk.get("content") if isinstance(chunk, dict) else getattr(getattr(chunk, "message", None), "content", "")
                yield token or ""
        except BrainPreempted:
            raise
        except Exception:
            # On a LIVE stream, cancel() closes the socket mid-read -> a connection error
            # surfaces here. If we cancelled, that is expected -> BrainPreempted, not a backend failure.
            if self._cancelled.is_set():
                raise BrainPreempted()
            raise
        if self._cancelled.is_set():
            raise BrainPreempted()

    def collect(self) -> str:
        parts = []
        for token in self.iter_tokens():
            parts.append(token)
        return "".join(parts)
```

- [ ] **Step 4: Run to verify pass**

Run: `.venv/bin/python -m unittest tests.test_cancellable_brain_call -v`
Expected: OK.

- [ ] **Step 5: Commit**

```bash
git add core/routing/cancellable_brain_call.py tests/test_cancellable_brain_call.py
git commit -m "feat(brain): CancellableBrainCall + BrainPreempted (hermetic cross-thread cancel proof)"
```

> **Separate owner-run integration probe (NOT a unit test, documented in the plan):** after merge, an owner-run probe (extend `/tmp/maez_abort_probe.py`) confirms cancel-before-first-token frees the real `llama-server` slot — the live counterpart to the hermetic proof.

---

## Task 2: The grep-backed call-site INVENTORY (load-bearing — the slice's risk surface)

**Deliverable: a committed table classifying EVERY brain-call site.** The slice is dangerous only if one call escapes the gateway.

**Files:**
- Create: `docs/slices/brain-gateway/call-site-inventory.md`

- [ ] **Step 1: Regenerate the candidate list**

```bash
grep -rnE "_llm_client\.chat\(|llm_client\.chat\(" daemon/ core/ --include=*.py | grep -vE "test_|def chat"
```

- [ ] **Step 2: Classify each site into the table**

For every hit, **read the enclosing function** and record a row. Columns: `file:line | enclosing function | BrainPurpose | foreground/background/neutral | reason | covering test`. **Rubric:**
- **foreground** — on the owner-message → visible-reply path: `handle_message` reply synthesis, recall/focused synthesis, tool/intent planning that gates the reply, voice reply. Enum: `owner_reply` / `owner_recall` / `voice_reply`.
- **background** — autonomous cognition not triggered by an owner turn: the daemon cognition cycle, `wondering_cycle`, `dream_state`, self-audit/judge *when invoked by a cycle*, error_classifier/learning. Enum: `daemon_cycle_generation` / `daemon_cycle_audit_judge` / `daemon_cycle_rewrite` / `daemon_cycle_retry`.
- **neutral** — untouched legacy/offline paths not on either live path. Left unclassified deliberately; the no-bypass + zero-neutral tests guard the boundary.

Seed (verified candidates — Task 2 confirms each by reading context):

| file:line | likely path | first-pass class |
|---|---|---|
| `daemon/maez_daemon.py:3493` | cognition cycle generation | background `daemon_cycle_generation` |
| `daemon/maez_daemon.py:3522` | cycle retry | background `daemon_cycle_retry` |
| `daemon/maez_daemon.py:4805` | owner reply / focused synthesis | foreground (confirm which) |
| `daemon/maez_daemon.py:2801`, `5776`, `6449`, `6627`, `7168` | **read each** | classify |
| `daemon/wondering_cycle.py:144` | autonomous wondering | background |
| `core/cognition/audit.py:195`, `344` | self-claim audit / judge | background `daemon_cycle_audit_judge` **if cycle-invoked**; foreground if it audits owner replies (confirm — it may be BOTH, requiring purpose to propagate from the caller) |
| `core/cognition/grounding_judge.py:670` | grounding judge | classify by caller (recall grounding = foreground; cycle = background) |
| `core/memory/continuity.py:336` | continuity synthesis | foreground if owner-recall, else classify |
| `core/decision/decision_pipeline.py:1221`, `1256` | tool/intent planning | foreground if owner-turn |
| `core/brain/brain_loop.py:2157`, `core/brain/conversation_controller.py:1160` | owner conversation | foreground (confirm) |
| `core/evolution/dream_state.py:346`, `core/learning/error_classifier.py:200` | autonomous | background |
| `core/routing/fast_backend_local.py:162` | fast path | classify by caller |

> **Critical insight from the seed:** several sites (audit, grounding_judge, continuity) are invoked from BOTH foreground and background callers. These MUST take their purpose from the **propagated context** (Task 4), not a hardcoded class — otherwise an owner-triggered audit gets `background` and a cycle-triggered one gets `foreground`. The inventory flags every such dual-caller site.

- [ ] **Step 3: Commit the inventory**

```bash
git add docs/slices/brain-gateway/call-site-inventory.md
git commit -m "docs(brain-gateway): grep-backed brain-call-site inventory + classification"
```

---

## Task 3: `BrainGateway` module + closed `BrainPurpose` enum + no-bypass test

**Files:**
- Create: `core/routing/brain_gateway.py`
- Test: `tests/test_brain_gateway.py`

- [ ] **Step 1: Write tests for the enum + derived priority + no-bypass**

```python
import unittest
from core.routing.brain_gateway import BrainPurpose, priority_of, BrainGateway


class BrainPurposeTest(unittest.TestCase):
    def test_priority_is_derived_not_passed(self):
        self.assertGreater(priority_of(BrainPurpose.OWNER_RECALL), priority_of(BrainPurpose.DAEMON_CYCLE_GENERATION))
        self.assertEqual(priority_of(BrainPurpose.NEUTRAL), priority_of(BrainPurpose.NEUTRAL))

    def test_unknown_purpose_defaults_neutral_never_high(self):
        # a caller cannot smuggle high priority via an unknown value
        self.assertEqual(priority_of("not_a_real_purpose"), priority_of(BrainPurpose.NEUTRAL))
```

(Plus the **no-bypass** test — see Task 4 Step 1, since it requires the routing in place.)

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m unittest tests.test_brain_gateway -v`
Expected: ImportError.

- [ ] **Step 3: Implement the gateway core**

`core/routing/brain_gateway.py`:
- `class BrainPurpose(Enum)` with the closed values (owner_reply, owner_recall, voice_reply, daemon_cycle_generation, daemon_cycle_audit_judge, daemon_cycle_rewrite, daemon_cycle_retry, neutral).
- `priority_of(purpose) -> int` — FOREGROUND set → high, DAEMON_CYCLE_* → low, anything else (incl. unknown) → neutral. Derived, never caller-passed.
- `class BrainGateway`: holds a `threading.Lock` for the slot, the current in-flight `CancellableBrainCall` + its priority, and a `submit(purpose, run_streaming_fn) -> str` that: derives priority; if foreground and a lower-priority call is in-flight → `cancel()` it (synchronously, honoring preempt_timeout) then acquire; runs `run_streaming_fn` wrapped in `CancellableBrainCall`, returns `.collect()`; emits the content-free `brain_gateway` telemetry event (purpose/priority/wait_ms/preempted/preempted_count/slot_busy_before).
- A module-level singleton `GATEWAY = BrainGateway()`.

(Implement to satisfy the Task-3/4/5/7 tests; keep thread-safety explicit — every mutation of in-flight state under the lock.)

- [ ] **Step 4: Run + commit**

Run: `.venv/bin/python -m unittest tests.test_brain_gateway -v` → OK
```bash
git add core/routing/brain_gateway.py tests/test_brain_gateway.py
git commit -m "feat(brain-gateway): closed BrainPurpose enum + derived-priority scheduler + content-free telemetry"
```

---

## Task 4: Route classified call sites through the gateway + purpose propagation (executor-safe)

**Files:** Modify each inventoried owner/cycle call site; add propagation in `core/routing/llm_client.py` (or a thin gateway entrypoint).
**Test:** `tests/test_brain_gateway_routing.py`

- [ ] **Step 1: Write the routing + propagation + no-bypass tests**

```python
import unittest
from unittest import mock
from core.routing import brain_gateway


class RoutingTest(unittest.TestCase):
    def test_no_bypass_on_classified_paths(self):
        # every classified owner/cycle path must traverse the gateway: patch the gateway
        # and assert the backend is never reached directly during a representative owner turn + cycle.
        with mock.patch.object(brain_gateway.GATEWAY, "submit", wraps=brain_gateway.GATEWAY.submit) as g:
            # drive a representative owner-reply path and a cycle path (use the daemon harness)
            ...  # see test harness in tests/test_memory_integrity_invariant.py
            self.assertTrue(g.called)

    def test_purpose_survives_run_in_executor(self):
        import asyncio
        from core.routing.brain_gateway import current_purpose, BrainPurpose, with_purpose

        async def driver():
            with with_purpose(BrainPurpose.OWNER_RECALL):
                loop = asyncio.get_event_loop()
                # contextvar is NOT auto-copied into executor threads — the carry must be explicit
                return await loop.run_in_executor(None, current_purpose)
        got = asyncio.run(driver())
        self.assertEqual(got, BrainPurpose.OWNER_RECALL)  # purpose did NOT decay to neutral
```

- [ ] **Step 2: Run to verify failure** → propagation/no-bypass not implemented yet.

- [ ] **Step 3: Implement propagation + routing**

- Add `current_purpose()` (reads a `contextvars.ContextVar`) and `with_purpose(p)` (context manager) in `brain_gateway.py`.
- **Executor-safe carry (pin #9):** because `contextvars` is NOT auto-copied into `run_in_executor` threads, the foreground path must carry the purpose explicitly — either `loop.run_in_executor(None, functools.partial(contextvars.copy_context().run, fn))` at the owner handoff, or set `with_purpose(...)` *inside* the function that runs on the brain-call thread. The plan uses the explicit `copy_context().run` carry at the `handle_message`→executor boundary, and `with_purpose` at the cycle entry (`maez_daemon.py:~1785` cycle thread + `:3493` region).
- Route each inventoried call: replace `_llm_client.chat(...)` on classified paths with `brain_gateway.GATEWAY.submit(purpose=current_purpose() or <site default>, run_streaming_fn=lambda: _llm_client.chat(..., stream=True))`. Background sites stream internally; the gateway returns the buffered string, so caller code reads `.message.content`-equivalent unchanged.
- Set the owner-turn purpose at `handle_message` entry; set the cycle purposes at the cycle entry; **dual-caller sites (audit/grounding_judge/continuity) read `current_purpose()`** so they inherit the caller's class.

- [ ] **Step 4: Zero-neutral tests (both directions)**

```python
    def test_zero_neutral_on_cycle_path(self):
        # enumerate the cycle's brain-call sites; each resolves to a daemon_cycle_* purpose
        ...
    def test_zero_neutral_on_owner_path(self):
        # enumerate the owner-reply path's brain-call sites; each resolves to a foreground purpose
        ...
```

- [ ] **Step 5: Run + commit** → OK; `git commit -m "feat(brain-gateway): route owner/cycle calls + executor-safe purpose propagation (zero neutral)"`

---

## Task 5: Preemption + `BrainPreempted` outranks every broad `except`

**Files:** Modify `daemon/maez_daemon.py:3493` (and the cycle helpers); sweep broad `except`.
**Test:** `tests/test_brain_preempt_propagation.py`

- [ ] **Step 1: Write the deep-nested non-swallow test**

```python
import unittest
from core.routing.cancellable_brain_call import BrainPreempted


class PreemptPropagationTest(unittest.TestCase):
    def test_preempt_surfaces_through_nested_broad_except(self):
        from daemon import maez_daemon
        # a cycle helper that wraps the brain call in `except Exception` must let BrainPreempted pass
        def helper():
            try:
                raise BrainPreempted()
            except Exception:        # the dangerous broad handler
                return "SWALLOWED"
        # after the sweep, the helper must re-raise BrainPreempted, not swallow it
        with self.assertRaises(BrainPreempted):
            maez_daemon._cycle_brain_helper_under_test(helper)  # the real wrapped path
```

- [ ] **Step 2: Run to verify failure** (a naive `except Exception` swallows it).

- [ ] **Step 3: Implement preemption wiring + the broad-except sweep**

- `daemon/maez_daemon.py:3493`: add `except BrainPreempted: <reschedule: log brain_preempted, no retry>` **before** `except Exception as first_err:`.
- **Sweep (pin #10):** `grep -rnE "except Exception" daemon/maez_daemon.py core/cognition/audit.py core/cognition/grounding_judge.py core/memory/continuity.py core/brain/*.py core/decision/decision_pipeline.py daemon/wondering_cycle.py` — for every broad `except` on a cycle/owner brain-call chain, add `except BrainPreempted: raise` before it (or make the handler re-raise `BrainPreempted`). Record the swept sites in the inventory doc.
- Preemption in the gateway: a foreground `submit` cancels the in-flight background `CancellableBrainCall` (which raises `BrainPreempted` in the background thread); the background caller catches it as reschedule. **Partial text discarded — never stored.**

- [ ] **Step 4: Run + commit** → OK; `git commit -m "fix(brain-gateway): BrainPreempted outranks daemon:3493 + every nested broad except"`

---

## Task 6: Byte-equivalence + content-free telemetry

**Test:** `tests/test_brain_gateway_equivalence.py`

- [ ] **Step 1: Write the tests**

```python
import unittest
from core.routing.cancellable_brain_call import CancellableBrainCall


class EquivalenceTest(unittest.TestCase):
    def test_buffered_reply_byte_equivalent_to_nonstreaming(self):
        # a fake chunk stream's assembled reply == the old non-streaming concatenation
        chunks = [{"content": "On April 27 "}, {"content": "we noted "}, {"content": "the incident [E1]."}]
        call = CancellableBrainCall(raw_stream=iter(chunks))
        self.assertEqual(call.collect(), "On April 27 we noted the incident [E1].")

    def test_telemetry_is_content_free(self):
        # the brain_gateway event contains only purpose/priority/wait_ms/preempted/preempted_count/slot_busy_before
        # assert NO reply/prompt/evidence text (mirror ContentFreeSchemaTest forbidden-field approach)
        ...
```

- [ ] **Step 2-3: Run, implement if needed, run → OK. Commit.**

---

## Task 7: DETERMINISTIC forced-collision acceptance test (pin #5)

**Test:** `tests/test_brain_gateway_forced_collision.py`

- [ ] **Step 1: Write the forced-collision test**

Deterministically put a background cycle call in-flight (a controllable fake stream blocked before first token), then submit a foreground recall. Assert: foreground gets the slot quickly (the background call was cancelled), the background call raised `BrainPreempted` (logged `brain_preempted`), **no retry fired, no partial stored, and `preempt_timeout` did NOT occur.**

```python
import threading, time, unittest
from core.routing import brain_gateway
from core.routing.cancellable_brain_call import BrainPreempted


class ForcedCollisionTest(unittest.TestCase):
    def test_foreground_preempts_inflight_background(self):
        bg_started = threading.Event(); bg_outcome = {}
        def bg_stream():
            bg_started.set()
            # blocked-before-first-token fake stream the gateway will cancel
            ev = threading.Event()
            class S:
                def __iter__(self):
                    while not ev.wait(0.05):
                        pass
                    yield {"content": "late"}
                def close(self): ev.set()
            return S()
        def run_bg():
            try:
                brain_gateway.GATEWAY.submit(purpose=brain_gateway.BrainPurpose.DAEMON_CYCLE_GENERATION,
                                             run_streaming_fn=bg_stream)
            except BrainPreempted:
                bg_outcome["preempted"] = True
        t = threading.Thread(target=run_bg); t.start()
        self.assertTrue(bg_started.wait(2.0))
        t0 = time.monotonic()
        fg = brain_gateway.GATEWAY.submit(purpose=brain_gateway.BrainPurpose.OWNER_RECALL,
                                          run_streaming_fn=lambda: iter([{"content": "fast reply [E1]"}]))
        fg_ms = (time.monotonic() - t0) * 1000
        t.join(timeout=2.0)
        self.assertLess(fg_ms, 1500)               # foreground got the slot fast
        self.assertTrue(bg_outcome.get("preempted"))  # background was preempted, not errored
        self.assertEqual(fg, "fast reply [E1]")
```

- [ ] **Step 2-3: Run → OK (this is the gate the whole slice exists to pass). Commit.**

---

## Task 8: Regression sweep + floor both directions

- [ ] **Step 1:** `.venv/bin/python -m unittest tests.test_cancellable_brain_call tests.test_brain_gateway tests.test_brain_gateway_routing tests.test_brain_preempt_propagation tests.test_brain_gateway_equivalence tests.test_brain_gateway_forced_collision tests.test_memory_integrity_invariant -v` → OK.
- [ ] **Step 2:** `.venv/bin/python -m unittest discover -s tests -p "test_*.py" -q` → **zero branch-only failures** (diff vs base in a clean checkout/worktree, NOT `git stash`; known unrelated trio: egress / web-slice / import-shim).
- [ ] **Step 3:** `.venv/bin/python -m ruff check core/routing/brain_gateway.py core/routing/cancellable_brain_call.py daemon/maez_daemon.py` + `python -c "import daemon.maez_daemon, core.routing.brain_gateway, core.routing.cancellable_brain_call; print('ok')"` → clean; ok.
- [ ] **Step 4:** Final commit if a sweep fix was needed.

---

## Cross-lane verification gate (Claude, before merge — NOT optional)

1. **Stage-0 is genuinely hermetic** — no live llama-server in unit tests; the fake stream proves cancel-before-first-token + mid-gen + idempotent + preempt_timeout-is-not-success.
2. **No side door** — the inventory table is complete; every classified path traverses the gateway; the no-bypass test fails if any owner/cycle call reaches the backend directly.
3. **Zero neutral both directions**; **dual-caller sites take propagated purpose**, not hardcoded; **executor-boundary propagation** proven (no neutral decay across `run_in_executor`).
4. **`BrainPreempted` never retried** — at `:3493` AND every swept broad `except`; the deep-nested non-swallow test passes; partial discarded.
5. **Byte-equivalence** + content-free telemetry; **forced-collision gate** green (no preempt_timeout).
6. **Thread-safety** — in-flight state mutated only under the lock; cancel is cross-thread-safe.
7. **Inner life intact** — cancelled cycles reschedule (rerun from source), nothing deleted; `_ollama_lock` retired/wrapped (not a second coordinator); `_rohit_active_until` hint-only.
8. **Floor both directions**; recall stays off. Then the **owner-run acceptance gate**: six-prompt smoke with cycles ACTIVE + the forced-collision case, p95 under A7, voice/inner-life intact.
