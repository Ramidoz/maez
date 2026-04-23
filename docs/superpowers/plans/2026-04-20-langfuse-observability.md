# Langfuse Observability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Instrument Maez's `core.brain_loop.run_brain_loop` and the Telegram surface handler with Langfuse traces so every Telegram turn produces a hierarchical, inspectable record (prompt → LLM outputs → tool calls → results → synthesis → audit) viewable in a real UI instead of 30KB of `journalctl | grep` output.

**Architecture:** A thin abstraction `core/observability.py` wraps the Langfuse SDK. It exposes `observe_turn(name, input, metadata) -> TurnContext` as a context manager and `TurnContext.llm_call(...)` / `TurnContext.tool_call(...)` helpers. When `LANGFUSE_PUBLIC_KEY` + `LANGFUSE_SECRET_KEY` are set in the environment, it sends real traces to Langfuse; when they're missing (default for everyone who hasn't signed up), it degrades to silent no-ops. This means the code lands safely without requiring anyone to have Langfuse credentials — activation is flipped by the user setting the env vars and restarting the daemon. `brain_loop.py` and `skills/surface/maez_adapter.py` gain calls into this abstraction without taking a hard dependency on the Langfuse SDK's surface — we can swap vendors (LangSmith, Helicone, local SQLite tracer) by rewriting `core/observability.py` and nothing else.

**Tech Stack:** Python 3.12, `langfuse` pip package, unittest, env-var config.

---

## Scope boundary

**In:**
- New module `core/observability.py` — Langfuse-wrapping abstraction with graceful no-op.
- Instrumentation inside `core.brain_loop.run_brain_loop` — one outer span per brain_loop call, one `llm_call` per LLM iteration, one `tool_call` per tool dispatch.
- Instrumentation inside `skills/surface/maez_adapter.py::MaezMessageHandler.__call__` — outer `observe_turn` wrapping the whole Telegram turn.
- `langfuse` added to whatever requirements file the venv uses (check `requirements.txt` or `pyproject.toml`).
- Unit tests for the no-op / active switching behavior.

**Out:**
- Instrumenting `daemon.handle_message` synthesis call (follow-up; brain_loop is where the mystery lives tonight).
- Instrumenting `core.self_claim_audit::audit` (follow-up).
- Memory-recall tracing (follow-up).
- Self-hosted Langfuse deployment.
- Frontier-model routing (separate plan).

## User action required before live verification

To see traces in the Langfuse UI, you need to:
1. Sign up at https://cloud.langfuse.com (free tier, 50k events/month).
2. Create a project.
3. Copy the public key + secret key.
4. Add to `/home/rohit/maez/.env` (or wherever the daemon reads env from):
   ```
   LANGFUSE_PUBLIC_KEY=pk-lf-...
   LANGFUSE_SECRET_KEY=sk-lf-...
   LANGFUSE_HOST=https://cloud.langfuse.com
   ```
5. Restart the daemon: `sudo systemctl restart maez.service`.

Until those env vars are set, the code is inert — all observability calls are no-ops. The code is still ship-safe without them.

## File structure

- **Create** `core/observability.py` — ~150 lines. `observe_turn(name, input, metadata) -> TurnContext` context manager. `TurnContext.llm_call(name, model, input, output, metadata)`, `.tool_call(name, params, output, ok, metadata)`, `.event(name, payload)`. Graceful degradation when `langfuse` import fails OR env vars missing.
- **Modify** `core/brain_loop.py` — accept optional `turn: TurnContext | None = None` kwarg on `run_brain_loop`. For each LLM iteration, call `turn.llm_call(...)`. For each dispatched tool, call `turn.tool_call(...)`. If `turn is None`, all calls are no-ops (the context helper handles this).
- **Modify** `skills/surface/maez_adapter.py` — in `MaezMessageHandler.__call__`, wrap the entire turn with `with observe_turn("telegram_turn", input=text) as turn:` and pass `turn` into `run_brain_loop`.
- **Create** `tests/test_observability.py` — unit tests for the no-op path (no env vars) and the construction path (env vars present, but don't actually ship traces — assert the SDK is called with expected args via mock).
- **Modify** `requirements.txt` (or `pyproject.toml` — check first) — add `langfuse>=2.60.0`.
- **Modify** `.env.example` (if it exists — check first) — document the three Langfuse env vars with comments.

## Key facts for the implementer

1. **Langfuse SDK surface** (as of v2.60+):
   ```python
   from langfuse import Langfuse
   client = Langfuse(public_key=..., secret_key=..., host=...)

   trace = client.trace(name="telegram_turn", input={"text": "..."},
                        metadata={"user_id": "rohit", "chat_id": "..."})
   span = trace.span(name="brain_loop", input={...})
   gen = trace.generation(name="planner", model="gemma-4-26b",
                          input=[{"role": "user", "content": "..."}],
                          output="TOOL_CALL: ...")
   gen.end()
   span.end(output={...})
   trace.update(output="final reply text")
   client.flush()  # important — async sends
   ```

   `span` / `generation` / `trace` all have `.update(...)` and `.end(...)` methods.

2. **No-op pattern when env vars are missing:** instantiate a `_NoopTrace` class with `.span()`, `.generation()`, `.update()`, `.end()` methods that all return another no-op or `self`. Keeps the call sites in `brain_loop` and `maez_adapter` unchanged regardless of whether Langfuse is active.

3. **Import safety:** `langfuse` should be imported lazily inside `core/observability.py` — if it's not installed, the module still loads and everything becomes no-op. Don't let a missing langfuse install break the daemon.

4. **Brain_loop LLM calls happen at `core/brain_loop.py:780` (`_llm_client.chat(...)`).** Wrap that call with a `generation()` span. Extract `model`, `messages`, and the response `text` as input/output.

5. **Brain_loop tool dispatches happen via `action_engine._execute_action(...)`.** There isn't a single clean seam — the tool name comes from the parsed TOOL_CALL, and the result comes back as a string that gets appended to `transcript`. The cleanest wrap: in the loop at around L790-L850, after parsing `action` + `params` and before/after calling `action_engine`, emit a `span()` with input=params and output=the result string.

6. **`maez_adapter.py` is async** (`async def __call__(self, event)`). Langfuse SDK v2+ is synchronous-safe; the context manager and `.update()` calls work in async code fine. `client.flush()` can also run in async.

7. **`dotenv`-style env loading**: check if the daemon already loads env vars from a file. If there's an existing `load_dotenv()` call somewhere in `daemon/maez_daemon.py` or `__main__`, we piggyback on that. If not, the user puts env vars in the systemd service file or exports them manually.

8. **Tests convention:** `cd /home/rohit/maez && .venv/bin/python -m unittest discover -s tests -p 'test_*.py'`.

9. **langfuse package install:** after adding to requirements, run `cd /home/rohit/maez && .venv/bin/pip install langfuse` to install into the venv. Only the daemon needs it — not system-wide.

---

## Task 1: `core/observability.py` — abstraction with no-op fallback

**Files:**
- Create: `core/observability.py`
- Create: `tests/test_observability.py`
- Modify: `requirements.txt` (or whatever dependency manifest exists — implementer verifies first)

- [ ] **Step 0: Environment prep**

Before writing code, verify the dependency manifest format:

```bash
ls /home/rohit/maez/requirements*.txt /home/rohit/maez/pyproject.toml 2>&1 | head -5
```

If `requirements.txt` exists, you'll add `langfuse>=2.60.0` there. If only `pyproject.toml`, add to the `[project] dependencies` list. If both, prefer the one the project actively uses (check `grep -l langfuse .` to see if it's already mentioned anywhere).

Install the package into the venv (required for the tests to import it):
```bash
cd /home/rohit/maez && .venv/bin/pip install 'langfuse>=2.60.0'
```

Expected: successful install. If it fails due to network/index issues, investigate — the whole plan depends on this.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_observability.py` with this exact content:

```python
# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Unit tests for core.observability — the Langfuse-wrapping abstraction
that gives every Telegram turn a hierarchical trace viewable in a real
UI instead of 30KB of journalctl output.

Core design constraint: code MUST load and run with no Langfuse env
vars set, because the daemon defaults are 'observability off'. Turning
it on is a user action (signup + env vars + restart)."""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch, MagicMock


class ObserveTurnNoOpWhenEnvMissing(unittest.TestCase):
    """When LANGFUSE_PUBLIC_KEY is not set, observe_turn returns a
    no-op context that accepts all the same calls but does nothing.
    This is the default state for anyone who hasn't signed up."""

    def test_observe_turn_is_noop_without_env(self):
        from core import observability
        # Patch the env so the secrets are clearly absent
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("LANGFUSE_PUBLIC_KEY", None)
            os.environ.pop("LANGFUSE_SECRET_KEY", None)
            with observability.observe_turn(
                "test_turn", input={"text": "hi"}, metadata={"x": 1}
            ) as turn:
                # All these calls must work and return without raising
                turn.llm_call(
                    name="planner", model="fake-model",
                    input=[{"role": "user", "content": "hi"}],
                    output="DONE",
                )
                turn.tool_call(
                    name="run_shell",
                    params={"cmd": "ls"},
                    output="file1\nfile2",
                    ok=True,
                )
                turn.event("something_happened", {"k": "v"})
                turn.update(output="final reply")
        # Reaching here = no exceptions raised. Good.

    def test_noop_turn_safe_for_nested_calls(self):
        """The no-op turn must tolerate being called inside a tight
        loop — e.g. one per brain_loop iteration."""
        from core import observability
        os.environ.pop("LANGFUSE_PUBLIC_KEY", None)
        os.environ.pop("LANGFUSE_SECRET_KEY", None)
        with observability.observe_turn("loop", input={}) as turn:
            for i in range(10):
                turn.llm_call(
                    name=f"iter_{i}", model="x",
                    input=[], output="",
                )
                turn.tool_call(
                    name="t", params={}, output="", ok=True,
                )


class ObserveTurnActiveWhenEnvPresent(unittest.TestCase):
    """When env vars are set, observe_turn instantiates a Langfuse
    client and records real traces. We mock the SDK to verify call
    shapes without actually shipping data to Langfuse."""

    def test_env_present_creates_trace(self):
        from core import observability

        env = {
            "LANGFUSE_PUBLIC_KEY": "pk-lf-test",
            "LANGFUSE_SECRET_KEY": "sk-lf-test",
            "LANGFUSE_HOST": "https://cloud.langfuse.com",
        }

        fake_client = MagicMock()
        fake_trace = MagicMock()
        fake_client.trace.return_value = fake_trace

        with patch.dict(os.environ, env, clear=False), \
             patch.object(observability, "_get_client",
                          return_value=fake_client):
            with observability.observe_turn(
                "test", input={"q": "x"}, metadata={"u": "rohit"}
            ) as turn:
                turn.llm_call(
                    name="planner", model="gemma-4-26b",
                    input=[{"role": "user", "content": "x"}],
                    output="DONE",
                )
                turn.tool_call(
                    name="run_shell",
                    params={"cmd": "ls"},
                    output="out", ok=True,
                )
                turn.update(output="reply")

        # Trace was created:
        fake_client.trace.assert_called_once()
        call = fake_client.trace.call_args
        self.assertEqual(call.kwargs.get("name"), "test")
        # Generation (llm_call) was recorded:
        self.assertTrue(fake_trace.generation.called,
                        "expected trace.generation() to be called for llm_call")
        # Span (tool_call) was recorded:
        self.assertTrue(fake_trace.span.called,
                        "expected trace.span() to be called for tool_call")


class ObserveTurnSwallowsSdkErrors(unittest.TestCase):
    """If the Langfuse SDK raises (network blip, bad creds), the turn
    must NOT crash the calling code. Observability failures are
    silent — Maez keeps working."""

    def test_sdk_raise_does_not_propagate(self):
        from core import observability

        env = {
            "LANGFUSE_PUBLIC_KEY": "pk-lf-test",
            "LANGFUSE_SECRET_KEY": "sk-lf-test",
        }

        fake_client = MagicMock()
        fake_client.trace.side_effect = RuntimeError("network blip")

        with patch.dict(os.environ, env, clear=False), \
             patch.object(observability, "_get_client",
                          return_value=fake_client):
            # This must not raise — Maez code paths are oblivious to
            # observability failures.
            with observability.observe_turn("test", input={}) as turn:
                turn.llm_call(name="x", model="y", input=[], output="")
                turn.tool_call(name="t", params={}, output="", ok=True)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd /home/rohit/maez && .venv/bin/python -m unittest tests.test_observability -v
```

Expected: all three tests fail with `ImportError: No module named 'core.observability'` OR `AttributeError` on `observe_turn`. Do not proceed until RED is for the right reason.

- [ ] **Step 3: Implement `core/observability.py`**

Create `core/observability.py` with this exact content:

```python
# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""
observability.py — thin Langfuse-wrapping abstraction for tracing
Maez's brain_loop and Telegram surface turns.

Design goals:
  1. Zero hard dependency on Langfuse. If the package is missing OR
     the LANGFUSE_PUBLIC_KEY env var isn't set, every call degrades
     to a silent no-op. The daemon ships and runs safely without
     anyone needing a Langfuse account.
  2. Vendor-swappable. All call sites in brain_loop / maez_adapter go
     through this module's API — `observe_turn`, `TurnContext.llm_call`,
     `TurnContext.tool_call`, `TurnContext.event`, `TurnContext.update`.
     Swapping Langfuse for LangSmith / Helicone / a local SQLite tracer
     means rewriting this module only.
  3. Silent on failure. If the Langfuse SDK raises (network blip, bad
     creds, etc.), we catch and continue. An observability failure
     must never break a Telegram turn.

Env vars consumed:
  LANGFUSE_PUBLIC_KEY  — required to activate (default off)
  LANGFUSE_SECRET_KEY  — required to activate
  LANGFUSE_HOST        — optional, defaults to https://cloud.langfuse.com

Typical call shape:
    from core.observability import observe_turn
    with observe_turn("telegram_turn", input={"text": text},
                      metadata={"user_id": "rohit", "chat_id": "..."}) as turn:
        # ... do work ...
        turn.llm_call(name="planner", model="gemma-4-26b",
                      input=messages, output=response_text)
        turn.tool_call(name="run_shell", params=params,
                       output=result_str, ok=True)
        turn.update(output=final_reply)
"""
from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Any, Optional

logger = logging.getLogger("maez.observability")

_client_cache: dict[str, Any] = {}


def _env_active() -> bool:
    """True iff the required env vars are present."""
    return bool(
        os.environ.get("LANGFUSE_PUBLIC_KEY")
        and os.environ.get("LANGFUSE_SECRET_KEY")
    )


def _get_client():
    """Return a cached Langfuse client, or None if unavailable.
    Cached so we don't re-instantiate per turn. Import is lazy so
    missing langfuse package is a no-op rather than ImportError."""
    if "client" in _client_cache:
        return _client_cache["client"]
    if not _env_active():
        _client_cache["client"] = None
        return None
    try:
        from langfuse import Langfuse
    except Exception as e:
        logger.debug("langfuse import failed, observability off: %s", e)
        _client_cache["client"] = None
        return None
    try:
        client = Langfuse(
            public_key=os.environ["LANGFUSE_PUBLIC_KEY"],
            secret_key=os.environ["LANGFUSE_SECRET_KEY"],
            host=os.environ.get(
                "LANGFUSE_HOST", "https://cloud.langfuse.com"
            ),
        )
    except Exception as e:
        logger.debug("langfuse client init failed: %s", e)
        _client_cache["client"] = None
        return None
    _client_cache["client"] = client
    return client


class _NoopTurn:
    """Drop-in replacement for an active TurnContext when the env
    vars aren't set. Every method accepts the same kwargs as the
    real one and returns without side effects."""

    def llm_call(self, **kwargs) -> None:
        return None

    def tool_call(self, **kwargs) -> None:
        return None

    def event(self, name: str, payload: Optional[dict] = None) -> None:
        return None

    def update(self, **kwargs) -> None:
        return None


class _ActiveTurn:
    """Real TurnContext backed by a Langfuse trace object."""

    def __init__(self, trace) -> None:
        self._trace = trace

    def llm_call(
        self,
        *,
        name: str,
        model: str,
        input: Any,
        output: Any,
        metadata: Optional[dict] = None,
    ) -> None:
        try:
            gen = self._trace.generation(
                name=name,
                model=model,
                input=input,
                output=output,
                metadata=metadata or {},
            )
            gen.end()
        except Exception as e:
            logger.debug("langfuse llm_call failed: %s", e)

    def tool_call(
        self,
        *,
        name: str,
        params: Any,
        output: Any,
        ok: bool,
        metadata: Optional[dict] = None,
    ) -> None:
        try:
            span = self._trace.span(
                name=f"tool:{name}",
                input=params,
                metadata={"ok": ok, **(metadata or {})},
            )
            span.end(output=output)
        except Exception as e:
            logger.debug("langfuse tool_call failed: %s", e)

    def event(self, name: str, payload: Optional[dict] = None) -> None:
        try:
            self._trace.event(name=name, metadata=payload or {})
        except Exception as e:
            logger.debug("langfuse event failed: %s", e)

    def update(
        self, *, output: Any = None, metadata: Optional[dict] = None
    ) -> None:
        try:
            self._trace.update(
                output=output, metadata=metadata or {}
            )
        except Exception as e:
            logger.debug("langfuse update failed: %s", e)


@contextmanager
def observe_turn(
    name: str,
    *,
    input: Any = None,
    metadata: Optional[dict] = None,
):
    """Context manager yielding a TurnContext. Always safe to use —
    no-op when Langfuse is off, real trace when it's on. SDK errors
    are swallowed so observability never breaks the caller."""
    client = _get_client()
    if client is None:
        yield _NoopTurn()
        return

    trace = None
    try:
        trace = client.trace(
            name=name,
            input=input,
            metadata=metadata or {},
        )
    except Exception as e:
        logger.debug("langfuse trace creation failed: %s", e)
        yield _NoopTurn()
        return

    try:
        yield _ActiveTurn(trace)
    finally:
        try:
            client.flush()
        except Exception as e:
            logger.debug("langfuse flush failed: %s", e)
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd /home/rohit/maez && .venv/bin/python -m unittest tests.test_observability -v
```

Expected: 4 tests pass (no-op path, nested-calls safety, env-active creates trace, SDK errors swallowed).

- [ ] **Step 5: Add `langfuse` to requirements manifest**

Verify where dependencies live, then add `langfuse>=2.60.0`:

```bash
# Pick whichever file is canonical:
grep -l 'anthropic\|openai\|chromadb' /home/rohit/maez/requirements*.txt /home/rohit/maez/pyproject.toml 2>/dev/null
```

Add a single line `langfuse>=2.60.0` to that file (preserve alphabetical order if the file uses it; otherwise append at the bottom). If both exist and are duplicates, update the one that matches the pip-freeze style.

- [ ] **Step 6: Full suite regression**

```bash
cd /home/rohit/maez && .venv/bin/python -m unittest discover -s tests -p 'test_*.py' 2>&1 | tail -5
```

Expected: 182 tests OK (178 previous + 4 new) + 1 pre-existing `test_fix6_followups` error. No NEW failures.

- [ ] **Step 7: Commit**

```bash
cd /home/rohit/maez && git add core/observability.py tests/test_observability.py requirements.txt && git commit -m "feat(observability): Langfuse abstraction with no-op fallback

Thin wrapper over the Langfuse SDK so Maez can emit hierarchical
traces (Telegram turn → brain_loop → LLM calls + tool dispatches)
to a real UI instead of relying on journalctl.

Design: zero hard dependency. If langfuse isn't installed OR
LANGFUSE_PUBLIC_KEY isn't set, every call is a silent no-op. The
daemon ships and runs safely without anyone needing an account.
Activation is env-var flip + daemon restart. SDK errors are caught
and swallowed — observability never breaks a Telegram turn.

Next task wires this into brain_loop and maez_adapter call sites."
```

If the dependency file path is different (e.g. `pyproject.toml` instead of `requirements.txt`), adjust the `git add` accordingly.

---

## Task 2: Instrument `brain_loop` + `maez_adapter` call sites

**Files:**
- Modify: `core/brain_loop.py` — add `turn: Optional[object] = None` kwarg on `run_brain_loop`; for each LLM call, call `turn.llm_call(...)`; for each tool dispatch, call `turn.tool_call(...)`.
- Modify: `skills/surface/maez_adapter.py` — in `MaezMessageHandler.__call__`, wrap the whole turn in `with observe_turn("telegram_turn", input=text) as turn:` and pass `turn` to `run_brain_loop`.
- Modify: `tests/test_observability.py` — append integration test using a fake `turn` that captures calls.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_observability.py` (BEFORE the `if __name__ == "__main__":` line):

```python
class BrainLoopAcceptsTurnKwarg(unittest.TestCase):
    """run_brain_loop must accept an optional `turn` kwarg and forward
    llm + tool-call events into it. Without this wiring, Task 1's
    abstraction is inert."""

    def test_brain_loop_calls_llm_call_and_tool_call(self):
        """Minimal smoke: the planner emits TOOL_CALL once, the tool
        runs, the planner emits DONE. We expect at least:
          - 2 llm_call invocations on the turn (planner iter 1 + 2)
          - 1 tool_call invocation on the turn"""
        from core import brain_loop

        recorded = {"llm_calls": [], "tool_calls": []}

        class FakeTurn:
            def llm_call(self, **kwargs):
                recorded["llm_calls"].append(kwargs)

            def tool_call(self, **kwargs):
                recorded["tool_calls"].append(kwargs)

            def event(self, *a, **k):
                pass

            def update(self, **k):
                pass

        # Fake LLM that emits TOOL_CALL then DONE
        responses = iter([
            'TOOL_CALL: {"action":"run_shell","params":{"cmd":"echo hi","reason":"greet"}}',
            "DONE",
        ])

        def fake_chat(*args, **kwargs):
            resp = MagicMock()
            resp.message.content = next(responses)
            return resp

        # Fake action engine that returns a success string
        fake_engine = MagicMock()
        fake_engine._execute_action = MagicMock(
            return_value=MagicMock(success=True, output="hi", error=None)
        )
        fake_pipeline = MagicMock()
        fake_pipeline.handle_action = MagicMock(
            return_value=MagicMock(
                status=MagicMock(value="executed"),
                message="hi",
                card=None,
            )
        )

        with patch("core.brain_loop._llm_client.chat",
                   side_effect=fake_chat):
            brain_loop.run_brain_loop(
                "say hi",
                action_engine=fake_engine,
                get_pipeline=lambda: fake_pipeline,
                turn=FakeTurn(),
            )

        self.assertGreaterEqual(
            len(recorded["llm_calls"]), 1,
            "expected at least one llm_call to be recorded; got "
            f"{recorded['llm_calls']!r}"
        )
        self.assertGreaterEqual(
            len(recorded["tool_calls"]), 1,
            "expected at least one tool_call to be recorded; got "
            f"{recorded['tool_calls']!r}"
        )
```

- [ ] **Step 2: Run to verify RED**

```bash
cd /home/rohit/maez && .venv/bin/python -m unittest tests.test_observability.BrainLoopAcceptsTurnKwarg -v
```

Expected: `TypeError: run_brain_loop() got an unexpected keyword argument 'turn'`. If it fails for other reasons (fake pipeline shape wrong, etc.) fix the test before proceeding.

- [ ] **Step 3: Add `turn` kwarg to `run_brain_loop`**

In `core/brain_loop.py`, change the signature at L482-493:

```python
def run_brain_loop(
    user_text: str,
    *,
    action_engine,
    get_pipeline,
    user_id: str = "rohit",
    chat_id: str = "",
    model: str = "gemma-4-26b",
    max_iters: int = 4,
    recovery_seed=None,
    send_intermediate=None,
    chat_history=None,
    turn=None,
) -> str:
```

At the top of the function body (around L514 before the `if not action_engine:` check), add:

```python
    # If no turn was supplied, use a no-op so call-site code can
    # unconditionally invoke turn.llm_call(...) / turn.tool_call(...)
    # without guarding on None.
    if turn is None:
        from core.observability import _NoopTurn
        turn = _NoopTurn()
```

- [ ] **Step 4: Emit `llm_call` around every LLM invocation**

Locate the LLM call site at approximately `core/brain_loop.py:780`. It currently looks like:

```python
            resp = _llm_client.chat(
                model=model,
                messages=[
                    {"role": "system",
                     "content": "You are Maez planning tool use. Emit ONE TOOL_CALL line per turn or write DONE."},
                    {"role": "user", "content": convo},
                ],
                stream=False, think=False,
                options={"temperature": 0.15, "num_predict": 512},
            )
            text = (resp.message.content or "").strip()
```

Replace with:

```python
            _llm_messages = [
                {"role": "system",
                 "content": "You are Maez planning tool use. Emit ONE TOOL_CALL line per turn or write DONE."},
                {"role": "user", "content": convo},
            ]
            resp = _llm_client.chat(
                model=model,
                messages=_llm_messages,
                stream=False, think=False,
                options={"temperature": 0.15, "num_predict": 512},
            )
            text = (resp.message.content or "").strip()
            turn.llm_call(
                name=f"planner_iter_{step}",
                model=model,
                input=_llm_messages,
                output=text,
                metadata={"step": step, "max_iters": max_iters},
            )
```

- [ ] **Step 5: Emit `tool_call` around every tool dispatch**

In `core/brain_loop.py`, find where the pipeline/action_engine dispatches a tool (look for `pipeline.handle_action(...)` or `action_engine._execute_action(...)` inside the `for step in range(max_iters)` loop). Around each dispatch, capture the result and emit:

```python
            # After obtaining result from pipeline / action_engine:
            turn.tool_call(
                name=action,
                params=params,
                output=<the string that gets appended to transcript>,
                ok=<bool — executed vs rejected>,
                metadata={"step": step},
            )
```

The existing logic that appends to `transcript` is the authoritative source of the output string and success state — mirror it into the turn call.

If the dispatch happens in multiple branches (Lane 0 inline vs Lane 2 card-created vs rejected), emit the `tool_call` in each so nothing's missed. Better to over-emit than miss a dispatch class.

- [ ] **Step 6: Wire maez_adapter**

In `skills/surface/maez_adapter.py::MaezMessageHandler.__call__`, locate where the brain_loop is invoked (around L206 with `_brain_loop.run_brain_loop(...)`). Immediately before that block, wrap the whole brain_loop + synthesis path in a turn context:

```python
        # Observability: wrap the whole turn. No-op when Langfuse env
        # is missing; hierarchical trace in Langfuse UI when active.
        from core.observability import observe_turn
        with observe_turn(
            "telegram_turn",
            input={"text": text, "chat_id": chat_id},
            metadata={"user_id": "rohit", "surface": SURFACE_NAME},
        ) as turn:
            # [existing chat_history fetch, brain_loop invocation,
            #  synthesis, audit — all stays inside the with-block]
            jarvis_transcript = ""
            try:
                from core import brain_loop as _brain_loop
                if action_engine is not None and get_pipeline is not None:
                    jarvis_transcript = await loop.run_in_executor(
                        None,
                        lambda: _brain_loop.run_brain_loop(
                            text,
                            action_engine=action_engine,
                            get_pipeline=get_pipeline,
                            user_id="rohit",
                            chat_id=chat_id,
                            send_intermediate=_send_intermediate,
                            chat_history=chat_history,
                            turn=turn,
                        ),
                    )
            except Exception as e:
                logger.warning("brain_loop failed on %s: %s", SURFACE_NAME, e)
                jarvis_transcript = ""

            # ... [rest of the existing block: synthesis, audit] ...

            turn.update(output=reply if isinstance(reply, str) else "(empty)")
            return reply
```

The `turn.update(output=...)` at the end records the final user-visible reply so it's visible in the trace.

**Important:** the existing code has multiple `return` paths (card-reply short-circuit, empty reply, etc.). Make sure the turn context wraps ALL of them, OR accept that early-return paths are un-traced for now (acceptable — most mystery lives in the brain_loop path).

- [ ] **Step 7: Verify GREEN on integration test**

```bash
cd /home/rohit/maez && .venv/bin/python -m unittest tests.test_observability.BrainLoopAcceptsTurnKwarg -v
```

Expected: 1 OK.

- [ ] **Step 8: Full suite regression**

```bash
cd /home/rohit/maez && .venv/bin/python -m unittest discover -s tests -p 'test_*.py' 2>&1 | tail -5
```

Expected: 183 tests OK (182 previous + 1 new) + 1 pre-existing `test_fix6_followups` error.

- [ ] **Step 9: Deploy + confirm clean boot**

```bash
sudo systemctl restart maez.service && sleep 4 && systemctl is-active maez && journalctl -u maez --since '10 seconds ago' --no-pager | grep -E 'surface v2 live|Cycle 1|ERROR|traceback' | head
```

Expected: `active`, surface v2 live, Cycle 1 running, NO tracebacks referencing `observability` or `langfuse`. If the daemon fails to boot because of an import error, the no-op fallback isn't actually degrading gracefully — investigate.

Do not send Telegram messages for live smoke; the user will set env vars + retry themselves after this commit lands.

- [ ] **Step 10: Commit**

```bash
cd /home/rohit/maez && git add core/brain_loop.py skills/surface/maez_adapter.py tests/test_observability.py && git commit -m "feat(brain_loop,surface): emit Langfuse traces per turn

brain_loop now accepts a 'turn' kwarg (no-op TurnContext default)
and emits turn.llm_call for each planning LLM iteration plus
turn.tool_call for each dispatched tool. maez_adapter wraps the
whole Telegram turn in observe_turn so every message produces a
complete hierarchical trace.

With LANGFUSE_PUBLIC_KEY + LANGFUSE_SECRET_KEY set, every Telegram
turn lights up in the Langfuse UI showing prompt -> planner LLM
call -> tool -> result -> next LLM call. Without them, everything
is a silent no-op."
```

Only those three files.

---

## Self-review

**Spec coverage:**
- Task 1 creates abstraction + tests + requirement. ✓
- Task 2 instruments call sites so the abstraction actually receives data. ✓
- Degraded mode (no env vars) is tested, must not crash, must not log noise. ✓
- SDK error swallowing is tested. ✓
- Live smoke is intentionally minimal — the user has to set env vars to actually see traces. Full UI verification is a manual post-step.

**Placeholder scan:** no TBDs. All code shown verbatim except:
- Task 2 Step 5 has `<the string that gets appended to transcript>` / `<bool — executed vs rejected>` placeholders because the exact lines around brain_loop's dispatch branches require the implementer to read the surrounding code and choose the right variable name (the transcript append logic is intricate and fragmenting it with verbatim code here would be more misleading than guiding — the implementer should read L790-L850 and mirror whatever gets appended).

**Type consistency:**
- `turn` is always a `_NoopTurn | _ActiveTurn` — both have identical surface (`llm_call`, `tool_call`, `event`, `update`). ✓
- `observe_turn` returns a context manager yielding either `_NoopTurn` or `_ActiveTurn`. ✓
- `_get_client` return type is `Langfuse | None` — None path leads to `_NoopTurn`. ✓

**Known non-placeholder:** the brain_loop tool-dispatch instrumentation point (Task 2 Step 5) is described rather than literally patched because the existing dispatch has multiple branches (Lane 0 inline, Lane 2 card, rejection, recovery) and a verbatim replace-block would be too fragile. The implementer must read the code and make judgment calls. This is an acceptable level of guidance for an experienced engineer — the plan documents which seams matter and what data to emit at each.
