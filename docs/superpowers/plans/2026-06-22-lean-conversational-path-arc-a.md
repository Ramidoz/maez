# Lean Conversational Path Arc A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a flag-gated lean focused prompt for ordinary conversation so casual turns shed capability/status, citation/trust, and diary-evidence apparatus while fresh/web/body/date turns keep their honesty rails.

**Architecture:** Keep the change inside focused cognition. Extract the existing self-capability question predicate into a shared module, then add lean eligibility, receipt, and prompt rendering to `core/routing/focused_cognition.py`. The daemon passes existing turn metadata into `focused_synthesize`; top-level reply-mode order stays unchanged.

**Tech Stack:** Python stdlib, `unittest`, existing `core.routing.focused_cognition`, `core.dispatcher.layer0`, daemon `handle_message`, content-light logger receipts.

---

## File Map

- Create `docs/proof/2026-06-22-lean-conversation-task0.md`: proof gate for real seams and scope boundaries.
- Create `core/routing/self_capability_question.py`: shared exact self-capability/body-question predicate and bodyish leak helper.
- Modify `core/dispatcher/layer0.py`: delegate `_is_self_capability_question` to the shared predicate while preserving current behavior.
- Modify `core/routing/focused_cognition.py`: lean flags, eligibility decision, content-light receipt, lean prompt renderer, optional `focused_synthesize(...)` parameters.
- Modify `daemon/maez_daemon.py`: pass `date_addressed`, `legacy_prompt_chars`, and `turn_kind` to `focused_synthesize`.
- Create `tests/test_self_capability_question.py`: shared predicate parity and bodyish leak tests.
- Create `tests/test_lean_conversation_path.py`: lean shadow/apply/full-path tests.
- Modify existing focused/dispatcher tests only if they need import-path updates after extraction.
- Create `docs/handoffs/2026-06-22-lean-conversational-path-handoff.md`: review-gate handoff and owner-breath sequence.

---

### Task 0: Proof Gate

**Files:**
- Create: `docs/proof/2026-06-22-lean-conversation-task0.md`

- [ ] **Step 1: Prove focused-local seam**

Run:

```bash
cd /home/rohit/maez
rg -n "_focused_synthesize\\(|focused_synthesize\\(" daemon/maez_daemon.py core/routing tests
sed -n '6960,7035p' daemon/maez_daemon.py
sed -n '1020,1095p' core/routing/focused_cognition.py
```

Expected:

- one production daemon call to `_focused_synthesize(...)` in the focused branch;
- `focused_synthesize(...)` owns the system prompt assembly;
- no top-level `ReplyMode` change is required.

Record this section:

```markdown
## Focused-local seam

Verdict: GO.

Production call:
- `daemon/maez_daemon.py:<line>` calls `_focused_synthesize(_focused_working_set, surface=source)`.

Prompt assembly:
- `core/routing/focused_cognition.py:<line>` builds the full focused system prompt.

Decision:
- Arc A can add optional lean rendering inside `focused_synthesize(...)` without changing `resolve_reply_mode`.
```

- [ ] **Step 2: Prove self-capability predicate reuse seam**

Run:

```bash
cd /home/rohit/maez
sed -n '90,120p' core/dispatcher/layer0.py
sed -n '238,278p' core/dispatcher/layer0.py
sed -n '510,522p' core/dispatcher/layer0.py
rg -n "_is_self_capability_question|_SELF_CAPABILITY_RE|_QUESTION_SHAPE_RE" core/dispatcher/layer0.py tests
```

Expected:

- `_is_self_capability_question` is regex/keyword-based;
- Layer0 already uses it for evidence-precedence routing;
- no other module owns a better body-question signal.

Record this section:

```markdown
## Self-capability/body question seam

Verdict: GO with exact reuse.

Current predicate:
- `_QUESTION_SHAPE_RE` + `_SELF_CAPABILITY_RE` in `core/dispatcher/layer0.py`.

Current production use:
- `Layer0Dispatcher.emit_spec(...)` sets `self_capability_question` from the predicate when `MAEZ_EVIDENCE_PRECEDENCE_ENABLED` is on.

Arc A plan:
- Extract the predicate into `core/routing/self_capability_question.py`.
- Keep `core/dispatcher/layer0.py` behavior byte-equivalent by delegating its private function to the shared predicate.
- Focused lean eligibility uses the shared predicate and fails body/capability questions toward FULL.
```

- [ ] **Step 3: Prove fresh/web source authority seam**

Run:

```bash
cd /home/rohit/maez
sed -n '70,105p' core/routing/focused_cognition.py
sed -n '1076,1110p' daemon/maez_daemon.py
.venv/bin/python -m unittest tests.test_turn_has_fresh_evidence tests.test_support_gate_scope_seam -v
```

Expected:

- `_FRESH_SOURCE_TYPES = ("fresh_evidence", "web_context")`;
- `turn_has_fresh_evidence(working_set)` reads `item.source_type`;
- support-gate scope tests pass.

Record this section:

```markdown
## Fresh/web authority seam

Verdict: GO.

Fresh predicate:
- `core/routing/focused_cognition.py:<line>` defines `_FRESH_SOURCE_TYPES`.
- `turn_has_fresh_evidence(working_set)` reads `item.source_type`.

Support scope:
- `daemon/maez_daemon.py:<line>` calls the same predicate before MiniCheck.

Test witness:
- `tests.test_turn_has_fresh_evidence` PASS.
- `tests.test_support_gate_scope_seam` PASS.
```

- [ ] **Step 4: Prove cold-open scope boundary**

Run:

```bash
cd /home/rohit/maez
rg -n "return None" core/routing/focused_cognition.py | head -20
sed -n '827,905p' core/routing/focused_cognition.py
```

Expected:

- `assemble_working_set(...)` can return `None` when there is no evidence, anchor, date cue, or recall item;
- Arc A cannot cover truly contextless cold-open turns in v0.

Record this section:

```markdown
## Cold-open boundary

Verdict: NAMED OUT-OF-SCOPE FOR V0.

Reason:
- Arc A lives inside focused cognition.
- If `assemble_working_set(...)` returns `None`, there is no focused prompt to lean.

Owner witness note:
- A fresh-session contextless greeting may still hit legacy synthesis. That is not an Arc A regression; it belongs to Arc B core-dump defuser or a future lean-legacy pass.
```

- [ ] **Step 5: Commit proof**

Run:

```bash
cd /home/rohit/maez
git add docs/proof/2026-06-22-lean-conversation-task0.md
git commit -m "docs(arc-a): prove lean conversation seams"
```

---

### Task 1: Shared Self-Capability Predicate

**Files:**
- Create: `core/routing/self_capability_question.py`
- Create: `tests/test_self_capability_question.py`
- Modify: `core/dispatcher/layer0.py`
- Test: `tests/test_self_capability_question.py`, `tests/test_dispatcher_layer0.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_self_capability_question.py`:

```python
from __future__ import annotations

import unittest


class SelfCapabilityQuestionTests(unittest.TestCase):
    def test_question_shape_and_capability_terms_match_today(self):
        from core.routing.self_capability_question import (
            bodyish_self_capability_candidate,
            is_self_capability_question,
        )

        text = "What's the state of your web search tools?"

        self.assertTrue(is_self_capability_question(text))
        self.assertTrue(bodyish_self_capability_candidate(text))

    def test_bodyish_without_question_shape_is_leak_candidate_not_carveout(self):
        from core.routing.self_capability_question import (
            bodyish_self_capability_candidate,
            is_self_capability_question,
        )

        text = "your web search tools are acting strange"

        self.assertFalse(is_self_capability_question(text))
        self.assertTrue(bodyish_self_capability_candidate(text))

    def test_non_body_conversation_is_not_bodyish(self):
        from core.routing.self_capability_question import (
            bodyish_self_capability_candidate,
            is_self_capability_question,
        )

        text = "how are you?"

        self.assertFalse(is_self_capability_question(text))
        self.assertFalse(bodyish_self_capability_candidate(text))

    def test_layer0_private_wrapper_delegates_to_shared_predicate(self):
        from core.dispatcher import layer0
        from core.routing.self_capability_question import is_self_capability_question

        samples = [
            "What's the state of your web search tools?",
            "what can you do?",
            "how are you?",
            "latest Anthropic news",
        ]

        for sample in samples:
            with self.subTest(sample=sample):
                self.assertEqual(
                    layer0._is_self_capability_question(sample),
                    is_self_capability_question(sample),
                )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest tests.test_self_capability_question -v
```

Expected:

- FAIL with `ModuleNotFoundError: No module named 'core.routing.self_capability_question'`.

- [ ] **Step 3: Create shared predicate module**

Create `core/routing/self_capability_question.py`:

```python
from __future__ import annotations

import re

QUESTION_SHAPE_RE = re.compile(
    r"^\s*(what|who|when|where|why|how|is|are|do|does|did|can|could|should|has|have|tell me|any)\b|[?]",
    re.IGNORECASE,
)

SELF_CAPABILITY_RE = re.compile(
    r"\b(?:you|your|maez|yourself)\b.*\b(?:web search|search tools?|page read|page reading|"
    r"web sense|search sense|tools?|capabilit(?:y|ies))\b"
    r"|\b(?:web search|search tools?|page read|page reading|web sense|search sense|tools?|"
    r"capabilit(?:y|ies))\b.*\b(?:you|your|maez|yourself)\b",
    re.IGNORECASE,
)


def bodyish_self_capability_candidate(utterance: str) -> bool:
    """True when the text mentions Maez/body/tool capability terms.

    This is the leak witness, not the carve-out. It intentionally ignores
    question shape so shadow can reveal body-ish statements that would still
    be lean-eligible.
    """
    return bool(SELF_CAPABILITY_RE.search(utterance or ""))


def is_self_capability_question(utterance: str) -> bool:
    """Exact shared version of Layer0's self-capability question predicate."""
    if not QUESTION_SHAPE_RE.search(utterance or ""):
        return False
    return bodyish_self_capability_candidate(utterance)
```

- [ ] **Step 4: Update Layer0 to delegate without behavior drift**

Modify `core/dispatcher/layer0.py`:

```python
from core.routing.self_capability_question import (
    QUESTION_SHAPE_RE as _QUESTION_SHAPE_RE,
    SELF_CAPABILITY_RE as _SELF_CAPABILITY_RE,
    is_self_capability_question as _shared_is_self_capability_question,
)
```

Delete the local `_QUESTION_SHAPE_RE = re.compile(...)` and `_SELF_CAPABILITY_RE = re.compile(...)` definitions. Keep the private wrapper:

```python
def _is_self_capability_question(utterance: str) -> bool:
    return _shared_is_self_capability_question(utterance)
```

Do not change `emit_spec(...)`; it must still gate this predicate with `evidence_precedence_enabled()`.

- [ ] **Step 5: Run tests**

Run:

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest tests.test_self_capability_question tests.test_dispatcher_layer0 -v
```

Expected:

- PASS.

- [ ] **Step 6: Commit**

Run:

```bash
cd /home/rohit/maez
git add core/routing/self_capability_question.py core/dispatcher/layer0.py tests/test_self_capability_question.py
git commit -m "refactor(arc-a): share self-capability question predicate"
```

---

### Task 2: Lean Decision, Receipt, and Prompt Renderer

**Files:**
- Modify: `core/routing/focused_cognition.py`
- Create: `tests/test_lean_conversation_path.py`
- Test: `tests/test_lean_conversation_path.py`, `tests/test_focused_cognition.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_lean_conversation_path.py`:

```python
from __future__ import annotations

import os
import unittest
from types import SimpleNamespace
from unittest import mock


def _response(text: str):
    return SimpleNamespace(message=SimpleNamespace(content=text))


def _working_set(*, source_type: str = "dialogue_anchor"):
    from core.routing.focused_cognition import EvidenceItem, WorkingSet

    return WorkingSet(
        items=[
            EvidenceItem(
                local_label="E1",
                source_type=source_type,
                text="User: how are you?\nMaez: I am here.",
                durable_id="anchor-1",
            )
        ],
        ordered_evidence_text="[E1] diary flood should not appear",
        owner_question="how are you?",
        working_set_chars=55,
        working_set_tokens_est=13,
        citation_render_version="v2",
    )


class LeanConversationPathTests(unittest.TestCase):
    def tearDown(self):
        for key in (
            "MAEZ_LEAN_CONVERSATION_SHADOW",
            "MAEZ_LEAN_CONVERSATION_ENABLED",
            "MAEZ_EVIDENCE_PRECEDENCE_ENABLED",
        ):
            os.environ.pop(key, None)

    def test_shadow_logs_eligible_but_keeps_full_prompt(self):
        from core.routing.focused_cognition import focused_synthesize

        os.environ["MAEZ_LEAN_CONVERSATION_SHADOW"] = "1"
        captured = {}

        def chat_fn(**kwargs):
            captured["system"] = kwargs["messages"][0]["content"]
            return _response("I am here.")

        with self.assertLogs("maez.focused", level="INFO") as logs:
            focused_synthesize(
                _working_set(),
                surface="telegram",
                chat_fn=chat_fn,
                model="m",
                date_addressed=False,
                legacy_prompt_chars=3200,
                turn_kind="ordinary",
            )

        self.assertIn("=== EVIDENCE (cite [E#]) ===", captured["system"])
        self.assertTrue(
            any("lean_conversation_shadow" in m and "eligible=True" in m for m in logs.output)
        )

    def test_enabled_lean_prompt_removes_apparatus_and_diary(self):
        from core.routing.focused_cognition import focused_synthesize

        os.environ["MAEZ_LEAN_CONVERSATION_ENABLED"] = "1"
        captured = {}

        def chat_fn(**kwargs):
            captured["system"] = kwargs["messages"][0]["content"]
            return _response("I am here.")

        focused_synthesize(
            _working_set(),
            surface="telegram",
            chat_fn=chat_fn,
            model="m",
            date_addressed=False,
            legacy_prompt_chars=3200,
            turn_kind="ordinary",
        )

        system = captured["system"]
        self.assertIn("Speak as Maez", system)
        self.assertIn("RECENT DIALOGUE", system)
        self.assertNotIn("CAPABILITY_STATE", system)
        self.assertNotIn("YOUR LIVE BODY", system)
        self.assertNotIn("=== EVIDENCE", system)
        self.assertNotIn("origin trust", system.lower())
        self.assertNotIn("diary flood", system)

    def test_fresh_web_uses_full_prompt_not_lean(self):
        from core.routing.focused_cognition import focused_synthesize

        os.environ["MAEZ_LEAN_CONVERSATION_ENABLED"] = "1"
        ws = _working_set(source_type="web_context")
        captured = {}

        def chat_fn(**kwargs):
            captured["system"] = kwargs["messages"][0]["content"]
            return _response("The web says X [E1].")

        focused_synthesize(ws, surface="telegram", chat_fn=chat_fn, model="m")

        self.assertIn("=== EVIDENCE (cite [E#]) ===", captured["system"])

    def test_self_capability_question_uses_full_prompt_not_lean(self):
        from core.routing.focused_cognition import focused_synthesize

        os.environ["MAEZ_LEAN_CONVERSATION_ENABLED"] = "1"
        ws = _working_set()
        ws = ws.__class__(
            items=ws.items,
            ordered_evidence_text=ws.ordered_evidence_text,
            owner_question="What's the state of your web search tools?",
            working_set_chars=ws.working_set_chars,
            working_set_tokens_est=ws.working_set_tokens_est,
            citation_render_version=ws.citation_render_version,
            thin_evidence=ws.thin_evidence,
        )
        captured = {}

        def chat_fn(**kwargs):
            captured["system"] = kwargs["messages"][0]["content"]
            return _response("Search is healthy [E1].")

        focused_synthesize(ws, surface="telegram", chat_fn=chat_fn, model="m")

        self.assertIn("=== EVIDENCE (cite [E#]) ===", captured["system"])

    def test_bodyish_leak_flag_appears_in_shadow(self):
        from core.routing.focused_cognition import focused_synthesize

        os.environ["MAEZ_LEAN_CONVERSATION_SHADOW"] = "1"
        ws = _working_set()
        ws = ws.__class__(
            items=ws.items,
            ordered_evidence_text=ws.ordered_evidence_text,
            owner_question="your web search tools are acting strange",
            working_set_chars=ws.working_set_chars,
            working_set_tokens_est=ws.working_set_tokens_est,
            citation_render_version=ws.citation_render_version,
            thin_evidence=ws.thin_evidence,
        )

        with self.assertLogs("maez.focused", level="INFO") as logs:
            focused_synthesize(
                ws,
                surface="telegram",
                chat_fn=lambda **_k: _response("ok"),
                model="m",
            )

        self.assertTrue(any("bodyish_lean_leak=True" in m for m in logs.output))

    def test_date_addressed_uses_full_prompt_not_lean(self):
        from core.routing.focused_cognition import focused_synthesize

        os.environ["MAEZ_LEAN_CONVERSATION_ENABLED"] = "1"
        captured = {}

        def chat_fn(**kwargs):
            captured["system"] = kwargs["messages"][0]["content"]
            return _response("I found the date [E1].")

        focused_synthesize(
            _working_set(),
            surface="telegram",
            chat_fn=chat_fn,
            model="m",
            date_addressed=True,
        )

        self.assertIn("=== EVIDENCE (cite [E#]) ===", captured["system"])

    def test_lean_renderer_does_not_import_memory_manager(self):
        import inspect
        import core.routing.focused_cognition as fc

        src = inspect.getsource(fc)
        lean_window = src[src.index("class LeanConversationDecision"):]
        self.assertNotIn("store_core", lean_window)
        self.assertNotIn("recall_for_telegram", lean_window)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest tests.test_lean_conversation_path -v
```

Expected:

- FAIL because `focused_synthesize(...)` does not accept `date_addressed`, and `LeanConversationDecision` does not exist.

- [ ] **Step 3: Add lean helpers**

Modify `core/routing/focused_cognition.py` after `GroundednessVerdict`:

```python
@dataclass(frozen=True)
class LeanConversationDecision:
    eligible: bool
    reason: str
    fresh_evidence: bool
    self_capability_question: bool
    bodyish_lean_leak: bool
    dialogue_anchor_count: int
    source_types: tuple[str, ...]


def _lean_conversation_shadow_enabled(env=os.environ) -> bool:
    return (env.get("MAEZ_LEAN_CONVERSATION_SHADOW", "") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _lean_conversation_enabled(env=os.environ) -> bool:
    return (env.get("MAEZ_LEAN_CONVERSATION_ENABLED", "") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _working_set_source_types(working_set: WorkingSet) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            str(getattr(item, "source_type", "") or "")
            for item in (getattr(working_set, "items", ()) or ())
            if str(getattr(item, "source_type", "") or "")
        )
    )


def _dialogue_anchor_count(working_set: WorkingSet) -> int:
    return sum(
        1
        for item in (getattr(working_set, "items", ()) or ())
        if getattr(item, "source_type", None) == "dialogue_anchor"
    )


def _decide_lean_conversation(
    working_set: WorkingSet,
    *,
    date_addressed: bool = False,
) -> LeanConversationDecision:
    from core.routing.self_capability_question import (
        bodyish_self_capability_candidate,
        is_self_capability_question,
    )

    source_types = _working_set_source_types(working_set)
    fresh = turn_has_fresh_evidence(working_set)
    self_cap = is_self_capability_question(working_set.owner_question)
    bodyish = bodyish_self_capability_candidate(working_set.owner_question)
    anchor_count = _dialogue_anchor_count(working_set)
    bodyish_leak = bodyish and not self_cap

    if fresh:
        return LeanConversationDecision(False, "fresh_evidence", fresh, self_cap, bodyish_leak, anchor_count, source_types)
    if date_addressed:
        return LeanConversationDecision(False, "date_addressed", fresh, self_cap, bodyish_leak, anchor_count, source_types)
    if self_cap:
        return LeanConversationDecision(False, "self_capability_question", fresh, self_cap, bodyish_leak, anchor_count, source_types)
    return LeanConversationDecision(True, "eligible", fresh, self_cap, bodyish_leak, anchor_count, source_types)
```

If line length exceeds ruff limits, split the `LeanConversationDecision(...)` calls across multiple lines.

- [ ] **Step 4: Add receipt and prompt render helpers**

Modify `core/routing/focused_cognition.py` near the lean helpers:

```python
def _emit_lean_conversation_receipt(
    event: str,
    decision: LeanConversationDecision,
    *,
    surface: str,
    legacy_prompt_chars: int | None,
    lean_prompt_chars_est: int,
    focused_items_count: int,
    turn_kind: str | None,
) -> None:
    logger.info(
        "%s eligible=%s reason=%s source_types=%s fresh_evidence=%s "
        "self_capability_question=%s bodyish_lean_leak=%s dialogue_anchor_count=%d "
        "legacy_prompt_chars=%s lean_prompt_chars_est=%d focused_items_count=%d "
        "surface=%s turn_kind=%s",
        event,
        decision.eligible,
        decision.reason,
        ",".join(decision.source_types) if decision.source_types else "none",
        decision.fresh_evidence,
        decision.self_capability_question,
        decision.bodyish_lean_leak,
        decision.dialogue_anchor_count,
        "null" if legacy_prompt_chars is None else int(legacy_prompt_chars),
        int(lean_prompt_chars_est),
        int(focused_items_count),
        surface,
        turn_kind or "unknown",
    )


def _lean_dialogue_anchor_text(working_set: WorkingSet) -> str:
    anchors = [
        item.text.strip()
        for item in (working_set.items or [])
        if item.source_type == "dialogue_anchor" and item.text.strip()
    ]
    if not anchors:
        return ""
    return "RECENT DIALOGUE (for continuity only):\n" + "\n\n".join(anchors[:2])


def _lean_system_prompt(working_set: WorkingSet) -> str:
    parts = [_VOICE_CARD_TEXT]
    anchor = _lean_dialogue_anchor_text(working_set)
    if anchor:
        parts.append(anchor)
    return "\n\n".join(parts)


def _full_focused_system_prompt(working_set: WorkingSet, *, surface: str) -> str:
    return (
        f"{_voice_card(surface)}\n\n"
        f"{_citation_instruction(
            working_set.citation_render_version,
            thin_evidence=working_set.thin_evidence,
        )}\n\n"
        f"{_TRUST_TIER_INSTRUCTION}\n\n"
        f"{_ORIGIN_TRUST_INSTRUCTION}\n\n"
        f"=== EVIDENCE (cite [E#]) ===\n"
        f"{working_set.ordered_evidence_text}"
    )
```

Then change `focused_synthesize(...)` to call `_full_focused_system_prompt(...)` instead of assembling the full system inline.

- [ ] **Step 5: Add optional lean parameters to `focused_synthesize`**

Change signature:

```python
def focused_synthesize(
    working_set: WorkingSet,
    *,
    surface: str,
    chat_fn=None,
    model=None,
    date_addressed: bool = False,
    legacy_prompt_chars: int | None = None,
    turn_kind: str | None = None,
) -> FocusedResult:
```

Replace system assembly with:

```python
    full_system = _full_focused_system_prompt(working_set, surface=surface)
    lean_system = _lean_system_prompt(working_set)
    decision = _decide_lean_conversation(
        working_set,
        date_addressed=date_addressed,
    )
    if _lean_conversation_shadow_enabled():
        _emit_lean_conversation_receipt(
            "lean_conversation_shadow",
            decision,
            surface=surface,
            legacy_prompt_chars=legacy_prompt_chars,
            lean_prompt_chars_est=len(lean_system),
            focused_items_count=len(working_set.items or []),
            turn_kind=turn_kind,
        )

    use_lean = _lean_conversation_enabled() and decision.eligible
    if use_lean:
        system = lean_system
        _emit_lean_conversation_receipt(
            "lean_conversation_applied",
            decision,
            surface=surface,
            legacy_prompt_chars=legacy_prompt_chars,
            lean_prompt_chars_est=len(lean_system),
            focused_items_count=len(working_set.items or []),
            turn_kind=turn_kind,
        )
    else:
        system = full_system
```

Keep the existing `messages`, `chat_fn(...)`, `cited_ids`, and `FocusedResult(...)` logic unchanged.

- [ ] **Step 6: Run tests**

Run:

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest tests.test_lean_conversation_path tests.test_focused_cognition tests.test_turn_has_fresh_evidence tests.test_support_gate_scope_seam -v
```

Expected:

- PASS.

- [ ] **Step 7: Commit**

Run:

```bash
cd /home/rohit/maez
git add core/routing/focused_cognition.py tests/test_lean_conversation_path.py
git commit -m "feat(arc-a): add lean conversation focused renderer"
```

Commit body:

```text
## Predicted effect

With MAEZ_LEAN_CONVERSATION_SHADOW=1, ordinary recall-only focused turns emit content-light receipts showing that they would use the lean prompt, but served replies remain unchanged.

With MAEZ_LEAN_CONVERSATION_ENABLED=1 after shadow witness, ordinary recall-only focused turns use the voice/thread/question prompt and omit capability, citation, trust, origin, and evidence blocks. Fresh/web, date-addressed, and self-capability turns continue using the full focused prompt.
```

---

### Task 3: Daemon Metadata Threading

**Files:**
- Modify: `daemon/maez_daemon.py`
- Test: `tests/test_lean_conversation_path.py`

- [ ] **Step 1: Write failing daemon-threading test**

Append to `tests/test_lean_conversation_path.py`:

```python
class LeanConversationDaemonThreadingTests(unittest.TestCase):
    def test_daemon_threads_lean_metadata_to_focused_synthesize(self):
        from pathlib import Path

        src = Path("daemon/maez_daemon.py").read_text()

        self.assertIn("_focused_synthesize(", src)
        self.assertIn("date_addressed=_date_addressed_turn", src)
        self.assertIn("legacy_prompt_chars=_legacy_prompt_chars", src)
        self.assertIn("turn_kind=_rk_turn_kind", src)
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest tests.test_lean_conversation_path.LeanConversationDaemonThreadingTests -v
```

Expected:

- FAIL because daemon does not pass the new arguments yet.

- [ ] **Step 3: Thread metadata through daemon call**

Modify `daemon/maez_daemon.py` at the `_focused_synthesize(...)` call:

```python
                            _focused_result = _focused_synthesize(
                                _focused_working_set,
                                surface=source,
                                date_addressed=_date_addressed_turn,
                                legacy_prompt_chars=_legacy_prompt_chars,
                                turn_kind=_rk_turn_kind,
                            )
```

- [ ] **Step 4: Run tests**

Run:

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest tests.test_lean_conversation_path tests.test_grounding_meter_seam tests.test_support_gate_scope_seam -v
```

Expected:

- PASS.

- [ ] **Step 5: Commit**

Run:

```bash
cd /home/rohit/maez
git add daemon/maez_daemon.py tests/test_lean_conversation_path.py
git commit -m "feat(arc-a): thread lean prompt metadata from daemon"
```

Commit body:

```text
## Predicted effect

Lean conversation receipts in the live daemon carry truthful date-addressed status, legacy prompt size, and turn kind. This does not change reply mode selection or support-gate scope.
```

---

### Task 4: Telemetry, Meter, and Regression Guards

**Files:**
- Modify: `tests/test_lean_conversation_path.py`
- Test: focused store and support-scope suites.

- [ ] **Step 1: Add tests for meter staying intact**

Append to `tests/test_lean_conversation_path.py`:

```python
class LeanConversationTelemetryTests(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("MAEZ_LEAN_CONVERSATION_ENABLED", None)

    def test_lean_reply_still_gets_grounding_meter_values(self):
        from core.routing.focused_cognition import check_groundedness, focused_synthesize

        os.environ["MAEZ_LEAN_CONVERSATION_ENABLED"] = "1"
        result = focused_synthesize(
            _working_set(),
            surface="telegram",
            chat_fn=lambda **_k: _response("I am here."),
            model="m",
        )
        verdict = check_groundedness(result, _working_set())

        self.assertEqual(verdict.reply_grounding, 0.0)
        self.assertEqual(verdict.total_sentences, 1)
        self.assertEqual(verdict.grounded_sentences, 0)

    def test_focused_store_accepts_lean_result_with_reply_grounding(self):
        from tempfile import TemporaryDirectory

        from core.routing.focused_cognition import (
            FocusedCognitionStore,
            check_groundedness,
            focused_synthesize,
        )

        os.environ["MAEZ_LEAN_CONVERSATION_ENABLED"] = "1"
        ws = _working_set()
        result = focused_synthesize(
            ws,
            surface="telegram",
            chat_fn=lambda **_k: _response("I am here."),
            model="m",
        )
        verdict = check_groundedness(result, ws)

        with TemporaryDirectory() as tmp:
            store = FocusedCognitionStore(db_path=f"{tmp}/focused.db")
            row_id = store.record(
                surface="telegram",
                chat_id=None,
                working_set=ws,
                result=result,
                verdict=verdict,
                legacy_prompt_chars=3200,
                fallback_reason=None,
                routing_observation_id=None,
            )
            row = store.get(row_id)

        self.assertEqual(row["reply_grounding"], 0.0)
        self.assertEqual(row["grounded_sentences"], 0)
        self.assertEqual(row["total_sentences"], 1)

    def test_support_scope_still_gates_fresh_web_turns(self):
        from core.routing.focused_cognition import focused_synthesize

        os.environ["MAEZ_LEAN_CONVERSATION_ENABLED"] = "1"
        captured = {}

        def chat_fn(**kwargs):
            captured["system"] = kwargs["messages"][0]["content"]
            return _response("The web says X [E1].")

        focused_synthesize(
            _working_set(source_type="web_context"),
            surface="telegram",
            chat_fn=chat_fn,
            model="m",
        )

        self.assertIn("=== EVIDENCE (cite [E#]) ===", captured["system"])
        self.assertIn("external web", captured["system"])
```

- [ ] **Step 2: Run tests**

Run:

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest tests.test_lean_conversation_path tests.test_grounding_meter tests.test_grounding_meter_seam tests.test_support_gate_scope_seam -v
```

Expected:

- PASS.

- [ ] **Step 3: Run focused regression**

Run:

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest \
  tests.test_focused_cognition \
  tests.test_turn_has_fresh_evidence \
  tests.test_support_gate_scope_seam \
  tests.test_live_thread_anchor \
  tests.test_recall_floor \
  tests.test_dispatcher_layer0 \
  tests.test_self_capability_question \
  tests.test_lean_conversation_path -v
```

Expected:

- PASS.

- [ ] **Step 4: Commit**

Run:

```bash
cd /home/rohit/maez
git add tests/test_lean_conversation_path.py
git commit -m "test(arc-a): guard lean conversation telemetry"
```

---

### Task 5: Handoff and Review Gate

**Files:**
- Create: `docs/handoffs/2026-06-22-lean-conversational-path-handoff.md`

- [ ] **Step 1: Run whole-slice verification**

Run:

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest \
  tests.test_lean_conversation_path \
  tests.test_self_capability_question \
  tests.test_dispatcher_layer0 \
  tests.test_focused_cognition \
  tests.test_turn_has_fresh_evidence \
  tests.test_support_gate_scope_seam \
  tests.test_live_thread_anchor \
  tests.test_recall_floor \
  tests.test_grounding_meter \
  tests.test_grounding_meter_seam -v

.venv/bin/ruff check \
  core/routing/focused_cognition.py \
  core/routing/self_capability_question.py \
  core/dispatcher/layer0.py \
  daemon/maez_daemon.py \
  tests/test_lean_conversation_path.py \
  tests/test_self_capability_question.py

git diff --check main...HEAD
```

Expected:

- all unittest modules pass;
- ruff passes;
- diff check clean.

- [ ] **Step 2: Write handoff**

Create `docs/handoffs/2026-06-22-lean-conversational-path-handoff.md`:

```markdown
# Lean Conversational Path Arc A — Review Gate Handoff

**Branch:** `lean-conversational-path-arc-a`
**Status:** STOPPED at review gate. Not merged. Not restarted. No flags flipped.
**Latest tip:** see `git log --oneline -1`.

## What Landed

- Shared self-capability question predicate: `core/routing/self_capability_question.py`.
- Focused lean decision/receipt/render helpers: `core/routing/focused_cognition.py`.
- Daemon metadata threading: `daemon/maez_daemon.py`.
- Tests: `tests/test_self_capability_question.py`, `tests/test_lean_conversation_path.py`.

## Invariants for Review

1. Default-off behavior is byte-identical except inert helper definitions.
2. Shadow flag logs receipts only; no served reply changes.
3. Lean prompt removes capability/status, citation, trust, origin, and evidence blocks.
4. Fresh/web turns use the full focused prompt.
5. Self-capability/body questions fail toward the full focused prompt.
6. Date-addressed turns use the full focused prompt.
7. Lean rendering does not mutate Chroma/core/daily/raw memory.
8. Focused telemetry and `reply_grounding` still record lean turns.
9. Support-gate scope remains fresh/web-gated and unchanged.
10. Cold-open contextless turns are out of v0 scope and may still hit legacy synthesis.

## Owner Breath After PASS

1. Merge only after Claude covenant review + Codex code review PASS.
2. Restart daemon with `MAEZ_LEAN_CONVERSATION_SHADOW=1`.
3. Live probe set:
   - "how are you?"
   - "you good?"
   - "sure"
   - "proceed with what you proposed"
   - "what's the latest news about Anthropic?"
   - "what is the state of your web search tools?"
   - a date-addressed memory question
4. Inspect `lean_conversation_shadow` receipts:
   - casual turns eligible;
   - fresh/news/body/date turns not eligible;
   - no meaningful `bodyish_lean_leak=True` on turns that should be full.
5. If shadow is clean, restart with `MAEZ_LEAN_CONVERSATION_ENABLED=1`.
6. Witness by feel first:
   - casual turns stop reciting status/courtroom/diary apparatus;
   - if the unchanged voice card over-steers toward "local AI / what we're building", record that as the v0.1 voice-card follow-up;
   - news/body/date turns keep rails.

## Plain English

This slice lets Maez answer ordinary conversation without first reading itself a dashboard and a court summons. It still keeps the dashboard and court for turns that ask about the current world, its body, tools, dates, or fresh evidence.
```

- [ ] **Step 3: Commit handoff**

Run:

```bash
cd /home/rohit/maez
git add docs/handoffs/2026-06-22-lean-conversational-path-handoff.md
git commit -m "docs(arc-a): hand off lean conversational path"
```

- [ ] **Step 4: Stop at review gate**

Do not merge. Do not restart. Do not flip `MAEZ_LEAN_CONVERSATION_SHADOW` or `MAEZ_LEAN_CONVERSATION_ENABLED`.

Report:

```text
Lean Conversational Path Arc A is built and STOPPED at the review gate.
Branch: lean-conversational-path-arc-a @ <tip>
Tests: <summary>
Ruff: clean
Diff check: clean
Awaiting: Claude covenant review + Codex code review, then owner breath.
```

---

## Self-Review Notes

Spec coverage:

- A1 subtraction, no script: Tasks 2 and 5.
- A2 fresh/body honesty rails: Tasks 0, 1, 2, 4.
- A3 no diary continuity items: Task 2 lean renderer only includes dialogue anchors.
- A4 meter caveat and subjective witness: Tasks 4 and 5.
- A5 no regression of support/core-pair organs: Tasks 0, 4, 5.
- B1 no memory mutation: Tasks 2, 4, 5.
- Cold-open scope boundary: Tasks 0 and 5.

No code path in this plan deletes, rewrites, or deweights memory. The focused telemetry store remains active by design.
