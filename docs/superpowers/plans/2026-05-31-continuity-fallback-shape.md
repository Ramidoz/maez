# Continuity-Fallback Shape Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix legacy continuity fallback so continuity turns answer conversationally from recent chat, never as dated/archive absence, while real dated turns remain unchanged.

**Architecture:** Add a small pure continuity-shape resolver in `daemon/maez_daemon.py` that decides one of three outcomes: no-op, deterministic truly-empty continuity reply, or a continuity-only synthesis instruction. Wire it into `MaezDaemon.handle_message` before `_consolidate_system_messages(...)` so the instruction is folded into the existing single-system-message prompt shape, and before legacy LLM synthesis so the truly-empty reply bypasses only the model call while preserving audit/store/tail.

**Tech Stack:** Python stdlib, `unittest`, existing `MaezDaemon.handle_message` harness in `tests/test_memory_integrity_invariant.py`, existing temporal cue guards in `tests/test_memory_manager.py` and `tests/test_recall_flip_eval_probes.py`.

---

## File Structure

- Modify `daemon/maez_daemon.py`
  - Add focused helpers near `_pair_history_for_chat_threading`:
    - `_chat_history_message_count(messages: list[dict]) -> int`
    - `_continuity_fallback_reply(owner_question: str) -> str`
    - `_continuity_shape_instruction() -> str`
    - `_resolve_continuity_fallback_shape(...) -> tuple[str | None, str]`
  - Move the existing dialogue/echo and absolute-date cue computation earlier, before `_consolidate_system_messages(...)`, because the continuity instruction must be selected before the current user turn is appended.
  - Append the continuity instruction before `_consolidate_system_messages(...)`, so the one-system-message invariant remains intact.
  - Add the truly-empty deterministic reply as a reply arm after self-status/tool/echo and before honest-empty/focused/legacy synthesis. This preserves the existing deterministic-priority branches and the normal audit/store/tail path.
- Modify `tests/test_memory_integrity_invariant.py`
  - Add pure-helper tests for the exact boundary conditions.
  - Add daemon-shaped tests for truly-empty continuity and continuity-with-chat.
  - Add daemon-shaped regression for a real dated `May 3` prompt.
- Existing parser guards stay in:
  - `tests/test_memory_manager.py::AbsoluteRecallCueTests.test_address_intent_battery`
  - `tests/test_recall_flip_eval_probes.py::RecallFlipEvalProbeTests.test_dated_miss_and_incidental_variants_match_their_cue_contract`

---

## Task 1: Pin The Pure Continuity-Shape Contract

**Files:**
- Modify: `tests/test_memory_integrity_invariant.py`
- Modify: `daemon/maez_daemon.py`

- [ ] **Step 1: Write the failing pure-helper tests**

In `tests/test_memory_integrity_invariant.py`, inside `class DaemonHandleMessageContract(unittest.TestCase):`, add these tests near the other daemon helper/source tests:

```python
    def test_continuity_shape_resolver_distinguishes_empty_chat_and_dated_turns(self):
        from daemon.maez_daemon import _resolve_continuity_fallback_shape

        reply, instruction = _resolve_continuity_fallback_shape(
            owner_question="What were we just talking about, the 3 may bugs?",
            continuity_turn=True,
            date_addressed=False,
            fresh_context_present=False,
            prior_chat_message_count=0,
            lived_brief="",
            temporal_anchor_brief="",
        )

        self.assertIsNotNone(reply)
        self.assertEqual(instruction, "")
        lowered = reply.lower()
        self.assertIn("not sure", lowered)
        self.assertIn("3 may bugs", lowered)
        self.assertNotIn("record", lowered)
        self.assertNotIn("dated memory", lowered)
        self.assertNotIn("may 3", lowered)

        reply, instruction = _resolve_continuity_fallback_shape(
            owner_question="What were we just talking about, the 3 may bugs?",
            continuity_turn=True,
            date_addressed=False,
            fresh_context_present=False,
            prior_chat_message_count=2,
            lived_brief="",
            temporal_anchor_brief="",
        )

        self.assertIsNone(reply)
        self.assertIn("CONTINUITY SHAPE", instruction)
        self.assertIn("Do not reinterpret embedded tokens such as '3 may'", instruction)
        self.assertNotIn("think", instruction.lower())
        self.assertNotIn("ponder", instruction.lower())

        reply, instruction = _resolve_continuity_fallback_shape(
            owner_question="What happened on May 3?",
            continuity_turn=True,
            date_addressed=True,
            fresh_context_present=False,
            prior_chat_message_count=2,
            lived_brief="",
            temporal_anchor_brief="",
        )

        self.assertIsNone(reply)
        self.assertEqual(instruction, "")

        reply, instruction = _resolve_continuity_fallback_shape(
            owner_question="What were we just talking about?",
            continuity_turn=True,
            date_addressed=False,
            fresh_context_present=True,
            prior_chat_message_count=0,
            lived_brief="",
            temporal_anchor_brief="",
        )

        self.assertIsNone(reply)
        self.assertEqual(instruction, "")

        reply, instruction = _resolve_continuity_fallback_shape(
            owner_question="What were we just talking about?",
            continuity_turn=True,
            date_addressed=False,
            fresh_context_present=True,
            prior_chat_message_count=2,
            lived_brief="",
            temporal_anchor_brief="",
        )

        self.assertIsNone(reply)
        self.assertIn("CONTINUITY SHAPE", instruction)
```

- [ ] **Step 2: Run the test to verify RED**

Run:

```bash
.venv/bin/python -m unittest tests.test_memory_integrity_invariant.DaemonHandleMessageContract.test_continuity_shape_resolver_distinguishes_empty_chat_and_dated_turns
```

Expected: FAIL with `ImportError` or `AttributeError` because `_resolve_continuity_fallback_shape` does not exist yet.

- [ ] **Step 3: Add the pure helpers**

In `daemon/maez_daemon.py`, immediately after `_pair_history_for_chat_threading(...)`, add:

```python
def _chat_history_message_count(messages: list[dict]) -> int:
    """Count substantive prior chat messages already threaded into messages[].

    Called before the current user turn is appended, so user/assistant
    messages here are prior conversation only. System/tool messages are not
    chat substance for the continuity fallback.
    """
    count = 0
    for message in messages:
        if not isinstance(message, dict):
            continue
        if message.get("role") not in {"user", "assistant"}:
            continue
        if str(message.get("content") or "").strip():
            count += 1
    return count


def _continuity_fallback_reply(owner_question: str) -> str:
    phrase = (owner_question or "that").strip().strip('"\\u201c\\u201d') or "that"
    if len(phrase) > 120:
        phrase = phrase[:117].rstrip() + "..."
    return f"I'm not sure what you mean by {phrase!r} from the chat I can see right now."


def _continuity_shape_instruction() -> str:
    return (
        "CONTINUITY SHAPE: This is a recent-conversation continuity turn. "
        "Answer from the recent chat that is already in this prompt. If the "
        "referenced phrase is ambiguous or was not established in the recent "
        "conversation, say that conversationally. Do not reinterpret embedded "
        "tokens such as '3 may' as calendar dates. Do not use archival 'no "
        "record' or dated-memory absence language unless the current turn is "
        "actually a dated-recall question."
    )


def _resolve_continuity_fallback_shape(
    *,
    owner_question: str,
    continuity_turn: bool,
    date_addressed: bool,
    fresh_context_present: bool,
    prior_chat_message_count: int,
    lived_brief: str,
    temporal_anchor_brief: str,
) -> tuple[str | None, str]:
    """Return (deterministic_reply, instruction) for continuity fallback shape.

    The deterministic reply is only for truly-empty continuity. If recent chat
    exists, the model still writes the answer, but receives a narrow shape
    instruction. Dated turns are always no-op here.
    """
    if not continuity_turn or date_addressed:
        return None, ""
    if prior_chat_message_count > 0:
        return None, _continuity_shape_instruction()
    if fresh_context_present:
        return None, ""
    if (lived_brief or "").strip() or (temporal_anchor_brief or "").strip():
        return None, ""
    return _continuity_fallback_reply(owner_question), ""
```

- [ ] **Step 4: Run the helper test to verify GREEN**

Run:

```bash
.venv/bin/python -m unittest tests.test_memory_integrity_invariant.DaemonHandleMessageContract.test_continuity_shape_resolver_distinguishes_empty_chat_and_dated_turns
```

Expected: PASS.

- [ ] **Step 5: Commit Task 1**

```bash
git add daemon/maez_daemon.py tests/test_memory_integrity_invariant.py
git commit -m "test(daemon): pin continuity fallback shape resolver"
```

---

## Task 2: Wire Truly-Empty Continuity Through Handle Message

**Files:**
- Modify: `tests/test_memory_integrity_invariant.py`
- Modify: `daemon/maez_daemon.py`

- [ ] **Step 1: Write the failing daemon-shaped truly-empty test**

Add this test to `DaemonHandleMessageContract`:

```python
    def test_truly_empty_continuity_uses_being_shaped_reply_without_archive_language(self):
        from daemon import maez_daemon

        captured = {}
        daemon = self._build_daemon_for_handle_message()

        with self._handle_message_mock_stack(
            maez_daemon,
            captured,
            reply="I don't have a record of a specific conversation about May 3.",
        ), mock.patch.dict(
            os.environ,
            {"MAEZ_RECALL_TRIAD_ENABLED": "0"},
            clear=False,
        ):
            reply = maez_daemon.MaezDaemon.handle_message(
                daemon,
                "What were we just talking about, the 3 may bugs?",
                source="telegram_surface",
                chat_history=None,
            )

        lowered = reply.lower()
        self.assertIn("not sure", lowered)
        self.assertIn("3 may bugs", lowered)
        self.assertNotIn("record", lowered)
        self.assertNotIn("dated memory", lowered)
        self.assertNotIn("may 3", lowered)
        self.assertNotIn("may 3rd", lowered)
        self.assertNotIn("recent chat or guesswork", lowered)
        self.assertNotIn("messages", captured, "truly-empty guard must bypass legacy LLM")
        self.assertTrue(captured.get("trace_written"), "normal tail must still run")
```

- [ ] **Step 2: Run the test to verify RED**

Run:

```bash
.venv/bin/python -m unittest tests.test_memory_integrity_invariant.DaemonHandleMessageContract.test_truly_empty_continuity_uses_being_shaped_reply_without_archive_language
```

Expected: FAIL because current code calls legacy LLM synthesis and returns the mocked archive-shaped reply.

- [ ] **Step 3: Move dialogue/date computation before prompt consolidation**

In `daemon/maez_daemon.py`, in `handle_message`, locate this current block after `turn_final_context = build_turn_final_context(...)`:

```python
        messages = _consolidate_system_messages(
            messages,
            final_system_part=turn_final_context,
        )
        messages.append({"role": "user", "content": prompt})
        try:
            from core.routing.focused_cognition import (
                build_intra_turn_echo_reply as _build_intra_turn_echo_reply,
                dialogue_continuity_state as _dialogue_continuity_state,
            )

            _dialogue_state = _dialogue_continuity_state(text)
            _current_turn_echo_reply = _build_intra_turn_echo_reply(text)
        except Exception:
            _dialogue_state = None
            _current_turn_echo_reply = None
```

Replace it with this order:

```python
        try:
            from core.routing.focused_cognition import (
                build_intra_turn_echo_reply as _build_intra_turn_echo_reply,
                dialogue_continuity_state as _dialogue_continuity_state,
            )

            _dialogue_state = _dialogue_continuity_state(text)
            _current_turn_echo_reply = _build_intra_turn_echo_reply(text)
        except Exception:
            _dialogue_state = None
            _current_turn_echo_reply = None
        _dialogue_needs_or_uncertain = bool(
            _dialogue_state
            and (
                getattr(_dialogue_state, "needs_dialogue", False)
                or getattr(_dialogue_state, "fail_safe_legacy", False)
            )
        )
        try:
            from core.routing.temporal_cue import (
                absolute_recall_cue as _absolute_recall_cue,
            )

            _abs_recall_cue = _absolute_recall_cue(text)
        except Exception:
            _abs_recall_cue = None
        _date_addressed_turn = bool(
            _abs_recall_cue and getattr(_abs_recall_cue, "is_address", False)
        )
```

Delete the old copies of `_dialogue_needs_or_uncertain`, `_abs_recall_cue`, and `_date_addressed_turn` from below the user-append site so each is computed once. Do not add `messages.append({"role": "user", "content": prompt})` here yet; the user turn will be appended after consolidation below.

- [ ] **Step 4: Compute the continuity fallback locals before consolidation**

Immediately after `_date_addressed_turn = bool(...)`, add:

```python
        _prior_chat_message_count = _chat_history_message_count(messages)
        _temporal_anchor_brief_text = (
            str(getattr(_temporal_anchor_result, "brief_text", "") or "")
            if _temporal_anchor_result is not None
            else ""
        )
        _truly_empty_continuity_reply, _continuity_shape_instruction_text = (
            _resolve_continuity_fallback_shape(
                owner_question=text,
                continuity_turn=bool(_dialogue_needs_or_uncertain),
                date_addressed=bool(_date_addressed_turn),
                fresh_context_present=bool((turn_final_context or "").strip()),
                prior_chat_message_count=_prior_chat_message_count,
                lived_brief=_lived_brief,
                temporal_anchor_brief=_temporal_anchor_brief_text,
            )
        )
```

Then, after this block and before `_focused_candidate = ...`, add the consolidation/user append. Do **not** append `_continuity_shape_instruction_text` in Task 2; Task 3 must remain a real RED-first instruction-wiring task.

```python
        messages = _consolidate_system_messages(
            messages,
            final_system_part=turn_final_context,
        )
        messages.append({"role": "user", "content": prompt})
```

This preserves the one-system-message invariant and keeps Task 3's continuity-with-chat test RED until the instruction append is added.

- [ ] **Step 5: Add the deterministic reply arm without skipping the tail**

In the reply selection section, keep self-status, tool, and echo ahead of the new guard. Change:

```python
        if _recall_status_reply is not None:
            reply = _recall_status_reply
            _reply_path = ReplyPath.SELF_STATUS
        elif _reply_decision.mode is ReplyMode.TOOL:
            reply = authoritative_tool_reply
        elif _reply_decision.mode is ReplyMode.ECHO:
            reply = _current_turn_echo_reply
        elif _reply_decision.mode is ReplyMode.HONEST_EMPTY:
```

to:

```python
        if _recall_status_reply is not None:
            reply = _recall_status_reply
            _reply_path = ReplyPath.SELF_STATUS
        elif _reply_decision.mode is ReplyMode.TOOL:
            reply = authoritative_tool_reply
        elif _reply_decision.mode is ReplyMode.ECHO:
            reply = _current_turn_echo_reply
        elif _truly_empty_continuity_reply is not None:
            reply = _truly_empty_continuity_reply
            _reply_path = ReplyPath.LEGACY
            _focused_used = True
        elif _reply_decision.mode is ReplyMode.HONEST_EMPTY:
```

The `_focused_used = True` line prevents the later legacy LLM fallback from overwriting the deterministic reply. It must not return early; audit, fragment guard, recall_outcome, trace, ledger, and store still run.

- [ ] **Step 6: Run the test to verify GREEN**

Run:

```bash
.venv/bin/python -m unittest tests.test_memory_integrity_invariant.DaemonHandleMessageContract.test_truly_empty_continuity_uses_being_shaped_reply_without_archive_language
```

Expected: PASS.

- [ ] **Step 7: Commit Task 2**

```bash
git add daemon/maez_daemon.py tests/test_memory_integrity_invariant.py
git commit -m "fix(daemon): answer truly-empty continuity without archive absence"
```

Commit body:

```text
## Predicted effect
A continuity question with no prior chat and no lived/temporal brief should get an honest being-shaped uncertainty reply, not an archival no-record/date-absence answer. Normal dated questions are unchanged.
```

---

## Task 3: Steer Continuity-With-Chat Away From Archive Absence

**Files:**
- Modify: `tests/test_memory_integrity_invariant.py`
- Modify: `daemon/maez_daemon.py`

- [ ] **Step 1: Write the failing daemon-shaped #5 test**

Add this test to `DaemonHandleMessageContract`:

```python
    def test_continuity_with_chat_gets_shape_instruction_not_deterministic_guard(self):
        from daemon import maez_daemon

        captured = {}
        daemon = self._build_daemon_for_handle_message()

        with self._handle_message_mock_stack(
            maez_daemon,
            captured,
            reply=(
                "We were going through the dated recall S5 checks; "
                "the 3 may bugs phrase was not established yet."
            ),
        ), mock.patch.dict(
            os.environ,
            {"MAEZ_RECALL_TRIAD_ENABLED": "0"},
            clear=False,
        ):
            reply = maez_daemon.MaezDaemon.handle_message(
                daemon,
                "What were we just talking about, the 3 may bugs?",
                source="telegram_surface",
                chat_history=[
                    {
                        "content": (
                            "Rohit: What happened on January 3?\n"
                            "Maez: I won't answer it from recent chat or guesswork."
                        )
                    },
                    {
                        "content": (
                            "Rohit: What did we note around May 12?\n"
                            "Maez: I won't answer it from recent chat or guesswork."
                        )
                    },
                ],
            )

        self.assertIn("dated recall S5 checks", reply)
        self.assertNotIn("not sure what you mean", reply.lower())
        self.assertIn("messages", captured)
        prompt_text = "\n".join(str(m.get("content") or "") for m in captured["messages"])
        system_messages = [
            m for m in captured["messages"] if m.get("role") == "system"
        ]
        self.assertEqual(len(system_messages), 1)
        self.assertIn("CONTINUITY SHAPE", prompt_text)
        self.assertIn("Do not reinterpret embedded tokens such as '3 may' as calendar dates", prompt_text)
        self.assertIn("What happened on January 3?", prompt_text)
        self.assertNotIn("I don't have a record", reply)
        self.assertNotIn("May 3rd", reply)
```

- [ ] **Step 2: Run the test to verify RED**

Run:

```bash
.venv/bin/python -m unittest tests.test_memory_integrity_invariant.DaemonHandleMessageContract.test_continuity_with_chat_gets_shape_instruction_not_deterministic_guard
```

Expected: FAIL because Task 2 computed `_continuity_shape_instruction_text` but deliberately did not append it to the prompt yet, so `CONTINUITY SHAPE` is missing from the captured prompt.

- [ ] **Step 3: Add instruction wiring before consolidation**

In `handle_message`, replace the Task 2 consolidation block:

```python
        messages = _consolidate_system_messages(
            messages,
            final_system_part=turn_final_context,
        )
        messages.append({"role": "user", "content": prompt})
```

with:

```python
        if _continuity_shape_instruction_text:
            messages.append(
                {"role": "system", "content": _continuity_shape_instruction_text}
            )
            system_part_capture.append(
                ("continuity_shape", _continuity_shape_instruction_text)
            )
        messages = _consolidate_system_messages(
            messages,
            final_system_part=turn_final_context,
        )
        messages.append({"role": "user", "content": prompt})
```

The instruction must be appended before `_consolidate_system_messages(...)` so the captured request still has exactly one system message. `_continuity_shape_instruction_text` must be non-empty only through `_resolve_continuity_fallback_shape(...)` with `date_addressed=False` and `prior_chat_message_count > 0`.

- [ ] **Step 4: Run the test to verify GREEN**

Run:

```bash
.venv/bin/python -m unittest tests.test_memory_integrity_invariant.DaemonHandleMessageContract.test_continuity_with_chat_gets_shape_instruction_not_deterministic_guard
```

Expected: PASS.

- [ ] **Step 5: Commit Task 3**

```bash
git add daemon/maez_daemon.py tests/test_memory_integrity_invariant.py
git commit -m "fix(daemon): steer continuity synthesis away from archive absence"
```

Commit body:

```text
## Predicted effect
Continuity turns with recent chat should answer from the recent conversation and should not turn embedded tokens such as "3 may" into dated no-record language. The model still writes the answer naturally; only the shape instruction changes.
```

---

## Task 4: Preserve Dated Routing And Parser Boundaries

**Files:**
- Modify: `tests/test_memory_integrity_invariant.py`
- Existing tests: `tests/test_memory_manager.py`
- Existing tests: `tests/test_recall_flip_eval_probes.py`

- [ ] **Step 1: Capture model-reply persistence in the harness**

In `_handle_message_mock_stack`, replace:

```python
            stack.enter_context(mock.patch(
                "core.ledger.model_reply_persistence.persist_model_reply",
                return_value=None,
            ))
```

with:

```python
            persist_model_reply_mock = stack.enter_context(mock.patch(
                "core.ledger.model_reply_persistence.persist_model_reply",
                return_value=None,
            ))
            captured["persist_model_reply_mock"] = persist_model_reply_mock
```

This lets deterministic branches prove what prompt material would have been persisted even when they bypass the LLM and therefore never populate `captured["messages"]`.

- [ ] **Step 2: Write the daemon-shaped real-date regression**

Add this test to `DaemonHandleMessageContract`:

```python
    def test_real_may_3_prompt_stays_dated_and_bypasses_continuity_shape(self):
        from daemon import maez_daemon

        captured = {}
        daemon = self._build_daemon_for_handle_message()

        with self.assertLogs(maez_daemon.logger, level="INFO") as logs:
            with self._handle_message_mock_stack(
                maez_daemon,
                captured,
                reply="legacy should not be used",
            ), mock.patch.dict(
                os.environ,
                {"MAEZ_RECALL_TRIAD_ENABLED": "0"},
                clear=False,
            ):
                reply = maez_daemon.MaezDaemon.handle_message(
                    daemon,
                    "What happened on May 3?",
                    source="telegram_surface",
                    chat_history=[
                        {
                            "content": (
                                "Rohit: We were discussing the 3 may bugs.\n"
                                "Maez: We were keeping that as continuity."
                            )
                        }
                    ],
                )

        self.assertEqual(reply, "I won't answer it from recent chat or guesswork.")
        self.assertNotIn("messages", captured, "dated legacy-off denial must not call synthesis")
        persist_model_reply = captured["persist_model_reply_mock"]
        persist_model_reply.assert_called()
        prompt_material = persist_model_reply.call_args.kwargs["prompt_material"]
        prompt_text = "\n".join(
            str(m.get("content") or "")
            for m in prompt_material["messages"]
            if isinstance(m, dict)
        )
        self.assertNotIn("CONTINUITY SHAPE", prompt_text)
        joined = "\n".join(logs.output)
        self.assertIn("dated_recall_denial", joined)
        self.assertIn("reply_mode=LEGACY", joined)
        self.assertIn("recall_stack_mode=legacy", joined)
```

- [ ] **Step 3: Run the dated regression**

Run:

```bash
.venv/bin/python -m unittest tests.test_memory_integrity_invariant.DaemonHandleMessageContract.test_real_may_3_prompt_stays_dated_and_bypasses_continuity_shape
```

Expected: PASS before and after implementation. This is a boundary guard rather than a RED behavior test.

- [ ] **Step 4: Confirm existing parser guard includes #5**

Run:

```bash
rg -n "\"what were we just talking about, the 3 may bugs\\?\"" tests/test_memory_manager.py
```

Expected: one hit in `AbsoluteRecallCueTests.test_address_intent_battery`. If missing, add it to the `not_address` list before continuing.

- [ ] **Step 5: Run boundary tests**

Run:

```bash
.venv/bin/python -m unittest \
  tests.test_memory_integrity_invariant.DaemonHandleMessageContract.test_real_may_3_prompt_stays_dated_and_bypasses_continuity_shape \
  tests.test_memory_manager.AbsoluteRecallCueTests.test_address_intent_battery \
  tests.test_recall_flip_eval_probes.RecallFlipEvalProbeTests.test_dated_miss_and_incidental_variants_match_their_cue_contract
```

Expected: PASS.

- [ ] **Step 6: Commit Task 4 if it added the dated regression**

```bash
git add tests/test_memory_integrity_invariant.py tests/test_memory_manager.py
git commit -m "test(daemon): preserve dated routing across continuity fallback fix"
```

---

## Task 5: Regression Sweep, Review, And Handoff

**Files:**
- No required production changes.

- [ ] **Step 1: Run targeted daemon and parser suites**

Run:

```bash
.venv/bin/python -m unittest \
  tests.test_memory_integrity_invariant.DaemonHandleMessageContract.test_continuity_shape_resolver_distinguishes_empty_chat_and_dated_turns \
  tests.test_memory_integrity_invariant.DaemonHandleMessageContract.test_truly_empty_continuity_uses_being_shaped_reply_without_archive_language \
  tests.test_memory_integrity_invariant.DaemonHandleMessageContract.test_continuity_with_chat_gets_shape_instruction_not_deterministic_guard \
  tests.test_memory_integrity_invariant.DaemonHandleMessageContract.test_real_may_3_prompt_stays_dated_and_bypasses_continuity_shape \
  tests.test_memory_integrity_invariant.DaemonHandleMessageContract.test_reply_mode_resolver_drives_echo_branch_with_same_reply \
  tests.test_memory_integrity_invariant.DaemonHandleMessageContract.test_recall_self_status_intercept_is_deterministic_and_tail_runs \
  tests.test_memory_integrity_invariant.DaemonHandleMessageContract.test_handle_message_uses_authoritative_tool_reply_before_llm_chat \
  tests.test_memory_manager.AbsoluteRecallCueTests \
  tests.test_recall_flip_eval_probes
```

Expected: PASS.

- [ ] **Step 2: Run the handle-message contract module**

Run:

```bash
.venv/bin/python -m unittest tests.test_memory_integrity_invariant
```

Expected: PASS, or report exact pre-existing failures with a base comparison before changing unrelated code.

- [ ] **Step 3: Run ruff**

Run:

```bash
.venv/bin/python -m ruff check daemon/maez_daemon.py tests/test_memory_integrity_invariant.py tests/test_memory_manager.py tests/test_recall_flip_eval_probes.py
```

Expected: clean.

- [ ] **Step 4: Run source audit for no new feature flag**

Run:

```bash
rg -n "CONTINUITY_FALLBACK|MAEZ_.*CONTINUITY|continuity_shape" daemon/maez_daemon.py tests/test_memory_integrity_invariant.py docs/superpowers/specs/2026-05-31-continuity-fallback-shape-design.md
```

Expected: only `continuity_shape` implementation/test/doc references; no new `MAEZ_...` flag.

- [ ] **Step 5: Request code review**

Ask the reviewer to focus on these five questions:

1. Does the deterministic guard fire only on truly-empty continuity, not lived-brief-empty with chat?
2. Does continuity-with-chat preserve model-authored voice while removing archive/date-absence shape?
3. Does the instruction affect only continuity turns and never dated turns?
4. Does fresh transcript/evidence context prevent the deterministic empty guard from over-firing?
5. Does the deterministic reply still run through audit/store/trace/telemetry tail?
6. Does the dated `May 3` regression prove the real dated path stays unchanged by inspecting persisted prompt material, not only LLM-call absence?

- [ ] **Step 6: Fold review findings**

Fix Critical/Important issues with RED tests first. If a reviewer says the condition over-fires, add a daemon-shaped test before adjusting.

- [ ] **Step 7: Final handoff report**

Report:

- branch and commit SHAs,
- RED/GREEN trail for each behavior-changing task,
- targeted test output,
- ruff output,
- reviewer findings and folds,
- deviations from this plan,
- flag posture: land-direct, no new flag, recall remains off.

---

## Self-Review

**Spec coverage:**
- Truly-empty deterministic reply: Tasks 1 and 2.
- Continuity-with-chat instruction for the #5 shape: Tasks 1 and 3.
- Fresh transcript/evidence context cannot be swallowed by the empty guard: Tasks 1 and 2.
- Parser remains correct for `3 may bugs`: Task 4.
- Real dated `May 3` unchanged: Tasks 1 and 4.
- No citation-render / recall-stack changes: file structure and Task 5 source audit.
- Land-direct / no new flag: Task 5 source audit.

**Placeholder scan:** No TODO/TBD placeholders. The plan uses the actual `DaemonHandleMessageContract` class name from `tests/test_memory_integrity_invariant.py`.

**Type consistency:** `_dialogue_needs_or_uncertain`, `_date_addressed_turn`, `_lived_brief`, `_temporal_anchor_result`, `messages`, `system_part_capture`, `ReplyPath.LEGACY`, and `chat_history` are existing `handle_message` locals or imported names verified from `daemon/maez_daemon.py` at planning time. New helper names are defined in Task 1 and reused consistently.
