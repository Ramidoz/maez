# Brain Loop Chat History Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pass the last N telegram exchanges into `core.brain_loop.run_brain_loop`'s planning context so the tool-selection model sees recent conversation instead of a single disembodied user message.

**Architecture:** `run_brain_loop` currently receives only the current `user_text` and constructs its initial history as one sentence: `the owner just said: '<text>'` + tool manifest. This is why "What did you find?" the day of 2026-04-20 drifted to hardware probing — the planner had no reference to the prior turn's `git clone` of github.com/obra/superpowers. The fix adds an optional `chat_history: list[dict] | None = None` parameter to `run_brain_loop`; when provided, it renders as a `RECENT CONVERSATION` block that precedes the existing "owner just said" line. The surface adapter (`skills/surface/maez_adapter.py`) populates it by calling the existing `memory_manager.get_telegram_exchanges(limit=3)` helper on the daemon's memory manager. No new storage, no schema changes, no new retrieval path — just wiring two existing pieces together.

**Tech Stack:** Python 3.12, unittest, existing ChromaDB-backed `MemoryManager`, existing `core.brain_loop` module. No new dependencies.

---

## Scope boundary

**In:** pass last-3 telegram exchanges into brain_loop; unit-test the formatting; wire the surface adapter to supply them.

**Out:** turn-contract relevance gate; registry-sourced self-description; time-indexed memory recall; changes to synthesis path (`daemon.handle_message`); changes to the legacy `skills/telegram_voice.py` brain_loop delegation (left untouched for this plan because surface v2 is authoritative in production; the legacy path already returns through the same `run_brain_loop` function, so it gets the new kwarg as a no-op default).

## File Structure

- **Modify** `core/brain_loop.py` — add `chat_history` kwarg to `run_brain_loop`, render it into the initial prompt before the "owner just said" line. Keep the parameter optional with `None` default so no existing caller breaks.
- **Modify** `skills/surface/maez_adapter.py` — in `MaezMessageHandler.__call__`, fetch the last 3 telegram exchanges from the daemon's memory manager and pass them to `run_brain_loop`.
- **Modify** `tests/test_brain_loop.py` — add unit tests for (a) history is included when provided, (b) backward-compat: None skips the block, (c) empty list skips the block. Create file if it does not exist.

## Key facts for the implementer

**1. Evidence of the bug (for context, not to re-verify):**

- `core/brain_loop.py:736-738` builds history as:
  ```python
  history = [
      f"the owner just said: {user_text!r}{_retry_context}\n\n{_TOOL_MANIFEST}\n\nBegin."
  ]
  ```
- `skills/surface/maez_adapter.py:208-215` calls `run_brain_loop(text, action_engine=..., get_pipeline=..., user_id=..., chat_id=..., send_intermediate=...)` — no history source.
- `memory/memory_manager.py:569-590` already provides `get_telegram_exchanges(limit=N)` returning a list sorted oldest→newest by timestamp, tail-sliced. Each item is `{"id", "content", "metadata"}` where `content` is a multi-line string mixing the owner's message and Maez's reply (stored by the raw-archive write path in the telegram bot code; treat as opaque text).

**2. How the daemon exposes memory:**

- The daemon instance passed into `MaezMessageHandler(daemon)` is a `MaezDaemon` with a `self.memory` attribute that is the `MemoryManager`. The adapter can call `self.daemon.memory.get_telegram_exchanges(limit=3)` directly. If `self.daemon.memory` is ever `None` (startup race), fall open — don't crash.

**3. Format for the RECENT CONVERSATION block:**

The block should be compact enough to stay well under the 512-token planning budget but rich enough to disambiguate pronouns and continuations. Stored content from `get_telegram_exchanges` is free-form text; render the items verbatim with a separator and a header. Example shape the brain_loop should construct:

```
RECENT CONVERSATION (most recent last, you are the "maez" side):
--- exchange 1 of 3 ---
<content from item 0>
--- exchange 2 of 3 ---
<content from item 1>
--- exchange 3 of 3 ---
<content from item 2>

the owner just said: 'What did you find?'

<_TOOL_MANIFEST>

Begin.
```

Rationale: "most recent last" matches LLM context-window bias toward recency. Numbered separators prevent the model from confusing exchange boundaries. "you are the 'maez' side" reminds the planner which voice is which when the stored content mixes both.

**4. Do NOT add chat_history to the recovery path.**

`run_brain_loop` has a `recovery_seed is not None` branch that builds its own seed message (line 544 onward). Recovery passes already carry their own pivot context (the failed action + error). Adding chat history there risks diluting the recovery directive. Only use `chat_history` in the non-recovery else-branch at [core/brain_loop.py:688-738](../../../core/brain_loop.py).

**5. Test-running convention for this repo:**

The project uses the standard library `unittest`. Tests live under `tests/` and are discovered with:
```bash
cd /home/rohit/maez && .venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
```
To run a single test file:
```bash
cd /home/rohit/maez && .venv/bin/python -m unittest tests.test_brain_loop -v
```
There is no `pytest` in the venv. The daemon is `sudo systemctl restart maez.service`.

---

## Task 1: Add `chat_history` parameter to `run_brain_loop` and render it into the initial history

**Files:**
- Create: `tests/test_brain_loop.py`
- Modify: `core/brain_loop.py:482-492` (signature) and `core/brain_loop.py:736-738` (history construction)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_brain_loop.py` with this exact content:

```python
# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Unit tests for core.brain_loop chat-history plumbing.

The brain_loop's planning LLM picks tools based on the prompt it sees.
Prior to this change, the prompt was a single sentence quoting the
user's message — no prior turn, no conversation continuity. "What
did you find?" arriving after a clone had zero signal about the
clone and drifted to hardware probing (observed 2026-04-20).

These tests lock in the fix: when chat_history is provided, the
constructed prompt MUST include a RECENT CONVERSATION block before
the 'owner just said' line. When chat_history is None or empty,
behavior matches the legacy single-sentence shape."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch


class ChatHistoryPrompting(unittest.TestCase):
    """The RECENT CONVERSATION block is what disambiguates "what did
    you find?" from a bare question. These tests verify it reaches the
    planning LLM."""

    def _capture_first_prompt(self, user_text, chat_history):
        """Run run_brain_loop with a stub LLM that captures the prompt
        and returns DONE immediately. Returns the user-role content of
        the first call."""
        from core import brain_loop

        captured = {}

        def fake_chat(*, model, messages, stream, think, options):
            # Capture the first call's user content; subsequent calls
            # (if any) don't matter — we just want the initial prompt.
            if "user_content" not in captured:
                for m in messages:
                    if m.get("role") == "user":
                        captured["user_content"] = m["content"]
                        break
            resp = MagicMock()
            resp.message.content = "DONE"
            return resp

        fake_action_engine = MagicMock()
        fake_get_pipeline = MagicMock()

        with patch.object(brain_loop._llm_client_module(), "chat",
                          side_effect=fake_chat, create=True) \
                if hasattr(brain_loop, "_llm_client_module") else \
                patch("core.llm_client.chat", side_effect=fake_chat):
            brain_loop.run_brain_loop(
                user_text,
                action_engine=fake_action_engine,
                get_pipeline=fake_get_pipeline,
                chat_history=chat_history,
            )

        return captured.get("user_content", "")

    def test_history_block_included_when_provided(self):
        history = [
            {"content": "rohit: Take a look at https://github.com/obra/superpowers\n"
                        "maez: I've proposed cloning the repo to /home/rohit/maez/superpowers — waiting for your go-ahead.",
             "metadata": {"timestamp": "2026-04-20T20:11:28"}},
            {"content": "rohit: Yes\n"
                        "maez: Ran `git clone https://github.com/obra/superpowers /home/rohit/maez/superpowers`. Cloning into '/home/rohit/maez/superpowers'...",
             "metadata": {"timestamp": "2026-04-20T20:11:35"}},
        ]
        prompt = self._capture_first_prompt("What did you find?", history)
        self.assertIn("RECENT CONVERSATION", prompt,
                      f"expected conversation header in prompt; got: {prompt[:400]!r}")
        self.assertIn("superpowers", prompt,
                      f"expected 'superpowers' from history in prompt; got: {prompt[:400]!r}")
        self.assertIn("What did you find?", prompt,
                      f"expected current user text in prompt; got: {prompt[:400]!r}")

    def test_none_history_preserves_legacy_shape(self):
        prompt = self._capture_first_prompt("What did you find?", None)
        self.assertNotIn("RECENT CONVERSATION", prompt,
                         f"unexpected conversation header for None history: {prompt[:400]!r}")
        self.assertIn("What did you find?", prompt)

    def test_empty_history_preserves_legacy_shape(self):
        prompt = self._capture_first_prompt("What did you find?", [])
        self.assertNotIn("RECENT CONVERSATION", prompt,
                         f"unexpected conversation header for empty list: {prompt[:400]!r}")
        self.assertIn("What did you find?", prompt)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd /home/rohit/maez && .venv/bin/python -m unittest tests.test_brain_loop -v
```

Expected: three failures/errors with messages about either `TypeError: run_brain_loop() got an unexpected keyword argument 'chat_history'` OR `AssertionError: expected conversation header in prompt` — the feature is absent. If failures are for unrelated reasons (import errors, stub plumbing problems), fix those before proceeding.

- [ ] **Step 3: Implement — modify `run_brain_loop` signature**

In `core/brain_loop.py`, change the signature at line 482:

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
) -> str:
```

The parameter goes LAST, is keyword-only (already after `*`), and defaults to `None` so no existing caller breaks.

- [ ] **Step 4: Implement — render the history block**

In `core/brain_loop.py`, locate the non-recovery history construction at lines 736-738:

```python
        history = [
            f"the owner just said: {user_text!r}{_retry_context}\n\n{_TOOL_MANIFEST}\n\nBegin."
        ]
```

Replace with:

```python
        # Build RECENT CONVERSATION block from chat_history so the
        # planning model sees what "it", "that", "what did you find"
        # refer to. Without this block the planner operates on the
        # current user message in isolation and drifts to stereotypical
        # investigation commands. Observed 2026-04-20: "What did you
        # find?" (one minute after a git clone) drifted to hardware
        # probing because the planner had zero signal about the clone.
        _history_block = ""
        if chat_history:
            _parts = [
                "RECENT CONVERSATION (most recent last, you are the \"maez\" side):"
            ]
            for _i, _ex in enumerate(chat_history, 1):
                _content = ""
                if isinstance(_ex, dict):
                    _content = str(_ex.get("content") or "").strip()
                else:
                    _content = str(_ex).strip()
                if not _content:
                    continue
                _parts.append(f"--- exchange {_i} of {len(chat_history)} ---")
                _parts.append(_content)
            if len(_parts) > 1:
                _history_block = "\n".join(_parts) + "\n\n"

        history = [
            f"{_history_block}the owner just said: {user_text!r}{_retry_context}\n\n{_TOOL_MANIFEST}\n\nBegin."
        ]
```

- [ ] **Step 5: Run the tests to verify they pass**

```bash
cd /home/rohit/maez && .venv/bin/python -m unittest tests.test_brain_loop -v
```

Expected: `Ran 3 tests in <time> — OK`. All three assertions pass.

If the test's stub-LLM plumbing (`patch("core.llm_client.chat", ...)`) doesn't match the actual llm_client import path used inside `brain_loop.py`, read `core/brain_loop.py` around line 521 — the import is `from core import llm_client as _llm_client` — and adjust the patch target to `core.brain_loop._llm_client.chat`. If that still doesn't intercept (module-level caching), the simpler fallback is to monkeypatch the module attribute directly in the test: `brain_loop._llm_client.chat = fake_chat` inside a try/finally. Use whichever approach actually intercepts the call.

- [ ] **Step 6: Run the full test suite to catch regressions**

```bash
cd /home/rohit/maez && .venv/bin/python -m unittest discover -s tests -p 'test_*.py' 2>&1 | tail -5
```

Expected: 162 tests pass plus 3 new = 165 total OK (plus the one pre-existing `test_fix6_followups` syntax error which has a literal `<OWNER_TELEGRAM_ID>` placeholder and is unrelated to this change). Any NEW failures must be fixed before proceeding.

- [ ] **Step 7: Commit**

```bash
cd /home/rohit/maez && git add core/brain_loop.py tests/test_brain_loop.py && git commit -m "feat(brain_loop): accept chat_history kwarg and render it into planning prompt

The brain_loop's tool-planning model received only the current user
message plus the tool manifest — no prior conversation. Observed
2026-04-20: 'What did you find?' arrived one minute after a git
clone, the planner had zero signal about the clone, and drifted to
hardware probing.

Add chat_history: Optional[list[dict]] = None. When provided,
render as a RECENT CONVERSATION block before the 'owner just said'
line. None or empty preserves legacy behavior."
```

---

## Task 2: Wire `chat_history` into `MaezMessageHandler` so Telegram turns pass the last 3 exchanges

**Files:**
- Modify: `skills/surface/maez_adapter.py:200-216` (the brain-loop invocation block)

- [ ] **Step 1: Write the failing test**

Append the following test class to `tests/test_brain_loop.py` (after `ChatHistoryPrompting`, before `if __name__ == "__main__":`):

```python
class AdapterPassesChatHistory(unittest.TestCase):
    """The surface adapter must actually fetch recent exchanges from
    the daemon's memory manager and pass them into run_brain_loop.
    Without this wiring, Task 1's fix is inert."""

    def test_adapter_fetches_exchanges_and_passes_to_brain_loop(self):
        import asyncio
        from skills.surface import maez_adapter

        # Fake daemon with a fake memory manager that returns a fixed
        # list of exchanges. The adapter should query for the last N
        # (we accept any limit >= 2) and pass the returned list to
        # run_brain_loop.
        fake_exchanges = [
            {"content": "rohit: clone X\nmaez: cloned",
             "metadata": {"timestamp": "2026-04-20T20:11:00"}},
            {"content": "rohit: what did you find?\nmaez: ...",
             "metadata": {"timestamp": "2026-04-20T20:12:00"}},
        ]

        class FakeMemory:
            def __init__(self):
                self.last_limit = None

            def get_telegram_exchanges(self, limit=None):
                self.last_limit = limit
                return fake_exchanges

        class FakeDaemon:
            def __init__(self):
                self.memory = FakeMemory()
                self.actions = MagicMock()
                self.telegram = MagicMock()
                self.telegram._get_pipeline = MagicMock(return_value=MagicMock())
                # handle_message returns a fixed string so the adapter
                # can complete its run without hitting the real LLM.
                self.handle_message = MagicMock(return_value="ok")
                # v2 adapter hooks — None is fine for this test.
                self._surface_v2_adapter = None
                self._surface_v2_loop = None

        captured_kwargs = {}

        def fake_run_brain_loop(*args, **kwargs):
            captured_kwargs.update(kwargs)
            return ""  # empty transcript is fine

        daemon = FakeDaemon()
        handler = maez_adapter.MaezMessageHandler(daemon)

        event = MagicMock()
        event.text = "What did you find?"
        event.source = MagicMock()
        event.source.chat_id = "12345"
        event.reply_to_message_id = None

        # Disable card-reply path (no open cards) by making the fake
        # pipeline return [] for get_open_for_channel.
        pipe = daemon.telegram._get_pipeline.return_value
        pipe.card_store = MagicMock()
        pipe.card_store.get_open_for_channel = MagicMock(return_value=[])

        with patch("core.brain_loop.run_brain_loop",
                   side_effect=fake_run_brain_loop):
            asyncio.run(handler(event))

        self.assertIn("chat_history", captured_kwargs,
                      "adapter did not pass chat_history kwarg to run_brain_loop")
        self.assertEqual(captured_kwargs["chat_history"], fake_exchanges,
                         "adapter passed wrong value for chat_history")
        # Limit should be small (recent conversation), not 400 (default).
        self.assertIsNotNone(daemon.memory.last_limit,
                             "adapter did not specify a limit on get_telegram_exchanges")
        self.assertLessEqual(daemon.memory.last_limit, 10,
                             f"adapter used too-large limit: {daemon.memory.last_limit}")
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd /home/rohit/maez && .venv/bin/python -m unittest tests.test_brain_loop.AdapterPassesChatHistory -v
```

Expected: `AssertionError: adapter did not pass chat_history kwarg to run_brain_loop`. The adapter currently calls `run_brain_loop` without `chat_history`.

- [ ] **Step 3: Implement — fetch exchanges and pass them**

In `skills/surface/maez_adapter.py`, locate the brain-loop invocation block starting at line 200:

```python
        # Brain-loop stage — runs the tool iteration synchronously
        # with the pipeline for card-or-inline decisions.
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
                    ),
                )
        except Exception as e:
            logger.warning("brain_loop failed on %s: %s", SURFACE_NAME, e)
            jarvis_transcript = ""
```

Replace with:

```python
        # Fetch the last few telegram exchanges so the brain-loop's
        # tool-planner has conversational context. Without this, the
        # planner sees only the current user message and drifts on
        # follow-up questions ("what did you find?", "try that again").
        # get_telegram_exchanges already exists and is used by
        # continuity + dream_state; this just extends its reach to the
        # tool-planning path. None-safe — fall open if memory is
        # unreachable.
        chat_history = None
        try:
            _mem = getattr(self.daemon, "memory", None)
            if _mem is not None:
                chat_history = _mem.get_telegram_exchanges(limit=3)
        except Exception as e:
            logger.debug("chat_history fetch failed on %s: %s",
                         SURFACE_NAME, e)
            chat_history = None

        # Brain-loop stage — runs the tool iteration synchronously
        # with the pipeline for card-or-inline decisions.
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
                    ),
                )
        except Exception as e:
            logger.warning("brain_loop failed on %s: %s", SURFACE_NAME, e)
            jarvis_transcript = ""
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
cd /home/rohit/maez && .venv/bin/python -m unittest tests.test_brain_loop.AdapterPassesChatHistory -v
```

Expected: `OK`.

- [ ] **Step 5: Run full suite for regressions**

```bash
cd /home/rohit/maez && .venv/bin/python -m unittest discover -s tests -p 'test_*.py' 2>&1 | tail -5
```

Expected: 166 tests OK (162 previous + 3 from Task 1 + 1 from Task 2). The pre-existing `test_fix6_followups` syntax error still counts as 1 unrelated error. No NEW regressions.

- [ ] **Step 6: Deploy + live smoke**

```bash
sudo systemctl restart maez.service && sleep 4 && systemctl is-active maez && journalctl -u maez --since '5 seconds ago' --no-pager | grep -E 'surface v2 live|Cycle 1' | head
```

Expected: `active`, plus log lines showing `surface v2 live (tasks=5)` and `--- Cycle 1 ---` within the first few seconds of boot.

Then, in Telegram, manually reproduce the failing sequence:
1. Send: `Take a look at this https://github.com/obra/superpowers`
2. Approve the clone card.
3. Send: `What did you find?`

Expected behavior after the fix: Maez's first tool call should reference `/home/rohit/maez/superpowers` (e.g., `ls /home/rohit/maez/superpowers`, `cat /home/rohit/maez/superpowers/README.md`, or `find /home/rohit/maez/superpowers -maxdepth 2`) — NOT `/sys/class/leds` or `lsusb`. Check with:

```bash
journalctl -u maez --since '3 minutes ago' --no-pager | grep -E 'T0 \| run_shell | pipeline: chat: What did you find' | head -3
```

If the first `cmd` field still references `/sys/class/leds` or `lsusb` instead of `/home/rohit/maez/superpowers`, the fix is not working on the live path. Common causes (check in order):
- `self.daemon.memory` is `None` at runtime — check with: `journalctl -u maez --since '3 minutes ago' --no-pager | grep -i 'chat_history fetch failed'`. If present, investigate why `memory` is missing on the daemon surface the adapter sees.
- The model ignored the new block — verify by logging (temporarily) the constructed `history[0]` just before the first LLM call in `brain_loop`, restart, and confirm the RECENT CONVERSATION block is present. If the block is present but the model ignores it, that's a separate prompt-design problem, not a bug in this fix.

- [ ] **Step 7: Commit**

```bash
cd /home/rohit/maez && git add skills/surface/maez_adapter.py tests/test_brain_loop.py && git commit -m "feat(surface): pass last 3 telegram exchanges into brain_loop chat_history

Fetches from the existing memory_manager.get_telegram_exchanges helper
and passes into run_brain_loop's new chat_history kwarg. Fall-open on
any exception so a memory-manager hiccup can't break message handling.

This is the consumer side of the brain_loop fix; observed failure
being addressed: 'What did you find?' drifting to LED probing one
minute after a git clone because the planner had no prior-turn
signal."
```

---

## Self-review

**Spec coverage check:**

- Phase 1 (investigation) identified one root cause: brain_loop context starvation at `core/brain_loop.py:736-738`. Task 1 fixes the code site. ✓
- Phase 1 identified the existing retrieval helper (`get_telegram_exchanges`). Task 2 wires it. ✓
- Phase 1 established that the synthesis path already has memory; asymmetry was in the planner. Task 2 closes the asymmetry via the surface adapter only. ✓
- No spec item remains unaddressed.

**Placeholder scan:** No TBD, no "add error handling," no "implement later," no "similar to Task N" without code, no undefined identifiers. All code blocks are complete. ✓

**Type consistency:**
- `chat_history` is documented as `list[dict] | None` and used consistently in both tests (items are dicts with `"content"` str and `"metadata"` dict) and implementation (reads `_ex.get("content")`). ✓
- `get_telegram_exchanges(limit=3)` returns `list[dict]` per memory_manager.py:581 — matches what brain_loop expects. ✓
- Kwarg name `chat_history` is identical in signature, implementation, test assertions, and adapter call. ✓

Plan is internally consistent and self-contained.
