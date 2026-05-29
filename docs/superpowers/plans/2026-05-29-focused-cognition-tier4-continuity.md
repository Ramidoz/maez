# Focused Cognition Tier-4 Continuity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve recent conversational continuity inside Focused Cognition so default-on focused synthesis does not regress follow-up or "what were we talking about?" turns.

**Architecture:** Extend the existing `core/routing/focused_cognition.py` working-set assembler with a deterministic continuity classifier and bounded dialogue anchors reused from `history_to_messages`. The daemon remains fail-safe: if a turn needs or may need dialogue and no usable anchor exists, it falls back to legacy synthesis rather than focused synthesis without the thread.

**Tech Stack:** Python 3.14, `unittest`, `core/routing/focused_cognition.py`, `core.brain.conversation_history.history_to_messages`, `daemon/maez_daemon.py`, existing focused-cognition SQLite trace store.

---

## Spec

`docs/superpowers/specs/2026-05-29-focused-cognition-tier4-continuity-design.md`

## Verified Source Facts

- `core/routing/focused_cognition.py:138-145` currently early-returns when `turn_evidence_state(...).evidence_present` is false. This must change because dialogue-only continuity can be a valid focused working set.
- `daemon/maez_daemon.py:3192` has `chat_history` in scope, and the focused branch currently calls `assemble_working_set(transcript=..., web_context=..., owner_question=text)` without it.
- `core/brain/conversation_history.py:69` exposes the canonical `history_to_messages(chat_history)` parser. Reuse it; do not duplicate parsing logic.
- `FocusedCognitionStore.record(...)` already stores `evidence_map_json` as labels/source types/durable ids only. No schema change is required for `dialogue_anchor`.

## File Structure

- **Modify:** `core/routing/focused_cognition.py`
  - Add `ContinuityKind`, `DialogueContinuityState`, `EvidenceItemSeed`.
  - Add `dialogue_continuity_state(owner_question)`.
  - Add `dialogue_anchor_items(chat_history, limit_pairs=3)`.
  - Extend `assemble_working_set(..., chat_history=None)` and priority ordering.
- **Modify:** `daemon/maez_daemon.py`
  - Import/use `dialogue_continuity_state`.
  - Widen focused-candidate gate to evidence-present OR continuity-needed.
  - Pass `chat_history` into `assemble_working_set`.
  - Log `focused_skip_reason="continuity_no_dialogue_anchor"` when the fail-safe routes to legacy.
- **Modify:** `tests/test_focused_cognition.py`
  - Add classifier, anchor, assembler, and privacy tests.
- **Modify:** `tests/test_memory_integrity_invariant.py`
  - Add daemon gate tests for direct/anaphoric/no-anchor fail-safe.

## Executor Warning: Fail-Safe Seam

The most important bug to avoid is:

> `fail_safe_legacy=True` + stale query evidence present + no usable `chat_history` accidentally runs focused cognition without the thread.

Rule: **any turn where dialogue is needed-or-uncertain and no usable anchor exists must land on legacy.** Implement that in the assembler and daemon tests. Do not rely on `evidence_state.evidence_present` alone.

Non-goal: v1 does not re-retrieve on follow-ups. It resolves references from dialogue/evidence already present in the turn. Query-rewrite-then-retrieve is a future slice.

---

### Task 1: Continuity Classifier

**Files:**
- Modify: `core/routing/focused_cognition.py`
- Test: `tests/test_focused_cognition.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_focused_cognition.py`:

```python
class DialogueContinuityStateTests(unittest.TestCase):
    def test_direct_continuity_state(self):
        from core.routing.focused_cognition import (
            ContinuityKind,
            dialogue_continuity_state,
        )

        examples = [
            "What were we talking about earlier?",
            "What did we just discuss?",
            "What was the last thing I said?",
            "What did you say before this?",
        ]
        for text in examples:
            with self.subTest(text=text):
                state = dialogue_continuity_state(text)
                self.assertEqual(state.kind, ContinuityKind.DIRECT)
                self.assertTrue(state.needs_dialogue)
                self.assertFalse(state.fail_safe_legacy)

    def test_anaphoric_continuity_state(self):
        from core.routing.focused_cognition import (
            ContinuityKind,
            dialogue_continuity_state,
        )

        examples = [
            "Which one matters most?",
            "Try that.",
            "Why does that matter?",
            "What about those?",
        ]
        for text in examples:
            with self.subTest(text=text):
                state = dialogue_continuity_state(text)
                self.assertEqual(state.kind, ContinuityKind.ANAPHORIC)
                self.assertTrue(state.needs_dialogue)
                self.assertFalse(state.fail_safe_legacy)

    def test_conservative_uncertain_continuity_state(self):
        from core.routing.focused_cognition import (
            ContinuityKind,
            dialogue_continuity_state,
        )

        state = dialogue_continuity_state("Anything since we were talking?")
        self.assertEqual(state.kind, ContinuityKind.NONE)
        self.assertFalse(state.needs_dialogue)
        self.assertTrue(state.fail_safe_legacy)
        self.assertIn("we were", state.matched_reason or "")

    def test_recent_freshness_query_is_not_continuity(self):
        from core.routing.focused_cognition import (
            ContinuityKind,
            dialogue_continuity_state,
        )

        state = dialogue_continuity_state(
            "Search r/LocalLLaMA right now for recent local LLM posts."
        )
        self.assertEqual(state.kind, ContinuityKind.NONE)
        self.assertFalse(state.needs_dialogue)
        self.assertFalse(state.fail_safe_legacy)
        self.assertIsNone(state.matched_reason)

    def test_bare_temporal_freshness_queries_are_not_continuity(self):
        from core.routing.focused_cognition import (
            ContinuityKind,
            dialogue_continuity_state,
        )

        examples = [
            "what are the last 5 posts on r/LocalLLaMA",
            "any news before the launch",
            "Anything since earlier?",
        ]
        for text in examples:
            with self.subTest(text=text):
                state = dialogue_continuity_state(text)
                self.assertEqual(state.kind, ContinuityKind.NONE)
                self.assertFalse(state.needs_dialogue)
                self.assertFalse(state.fail_safe_legacy)
                self.assertIsNone(state.matched_reason)
```

- [ ] **Step 2: Run tests to verify fail**

Run:

```bash
.venv/bin/python -m unittest tests.test_focused_cognition.DialogueContinuityStateTests -v
```

Expected: FAIL with import error for `ContinuityKind` / `dialogue_continuity_state`.

- [ ] **Step 3: Implement classifier**

In `core/routing/focused_cognition.py`, add imports near the top:

```python
from enum import Enum
from typing import Iterable
```

Add after existing dataclasses:

```python
class ContinuityKind(str, Enum):
    DIRECT = "direct"
    ANAPHORIC = "anaphoric"
    NONE = "none"


@dataclass(frozen=True)
class DialogueContinuityState:
    kind: ContinuityKind
    needs_dialogue: bool
    fail_safe_legacy: bool
    matched_reason: str | None = None


_DIRECT_CONTINUITY_PATTERNS = (
    "what were we talking about",
    "what did we just discuss",
    "what were we discussing",
    "what was the last thing i said",
    "what was the last thing you said",
    "what was the last thing we discussed",
    "what was the last thing we talked about",
    "what did i say",
    "what did you say",
    "what were we doing earlier",
    "what were we doing before",
    "before this",
    "before that",
)

_ANAPHORIC_PHRASES = (
    "which one",
    "try that",
    "do it",
    "what about that",
    "why does that matter",
)
_ANAPHORIC_WORDS = ("that", "this", "those", "it")

_UNCERTAIN_CONTINUITY_PATTERNS = (
    "we were",
    "you said",
    "i said",
    "that thing",
)


def dialogue_continuity_state(owner_question: str) -> DialogueContinuityState:
    text = (owner_question or "").strip().lower()
    for pattern in _DIRECT_CONTINUITY_PATTERNS:
        if pattern in text:
            return DialogueContinuityState(
                kind=ContinuityKind.DIRECT,
                needs_dialogue=True,
                fail_safe_legacy=False,
                matched_reason=pattern,
            )
    for pattern in _ANAPHORIC_PHRASES:
        if pattern in text:
            return DialogueContinuityState(
                kind=ContinuityKind.ANAPHORIC,
                needs_dialogue=True,
                fail_safe_legacy=False,
                matched_reason=pattern,
            )
    for pattern in _ANAPHORIC_WORDS:
        if re.search(rf"\b{re.escape(pattern)}\b", text):
            return DialogueContinuityState(
                kind=ContinuityKind.ANAPHORIC,
                needs_dialogue=True,
                fail_safe_legacy=False,
                matched_reason=pattern,
            )
    for pattern in _UNCERTAIN_CONTINUITY_PATTERNS:
        if pattern in text:
            return DialogueContinuityState(
                kind=ContinuityKind.NONE,
                needs_dialogue=False,
                fail_safe_legacy=True,
                matched_reason=pattern,
            )
    return DialogueContinuityState(
        kind=ContinuityKind.NONE,
        needs_dialogue=False,
        fail_safe_legacy=False,
        matched_reason=None,
    )
```

- [ ] **Step 4: Run tests to verify pass**

Run:

```bash
.venv/bin/python -m unittest tests.test_focused_cognition.DialogueContinuityStateTests -v
```

Expected: OK.

- [ ] **Step 5: Commit**

```bash
git add core/routing/focused_cognition.py tests/test_focused_cognition.py
git commit -m "feat(focused-cognition): classify continuity-shaped turns"
```

---

### Task 2: Dialogue Anchor Extraction

**Files:**
- Modify: `core/routing/focused_cognition.py`
- Test: `tests/test_focused_cognition.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_focused_cognition.py`:

```python
class DialogueAnchorTests(unittest.TestCase):
    def test_dialogue_anchor_reuses_history_to_messages(self):
        from unittest import mock

        from core.routing import focused_cognition

        with mock.patch(
            "core.brain.conversation_history.history_to_messages",
            return_value=[
                {"role": "user", "content": "Search r/LocalLLaMA"},
                {"role": "assistant", "content": "I found LiquidAI [E1]."},
            ],
        ) as parser:
            items = focused_cognition.dialogue_anchor_items(
                [{"content": "ignored because parser is patched"}],
                limit_pairs=3,
            )

        parser.assert_called_once()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].source_type, "dialogue_anchor")
        self.assertIn("User: Search r/LocalLLaMA", items[0].text)
        self.assertIn("Maez: I found LiquidAI", items[0].text)
        self.assertTrue(items[0].durable_id.startswith("ch_"))

    def test_dialogue_anchor_limits_to_recent_pairs(self):
        from core.routing.focused_cognition import dialogue_anchor_items

        history = [
            {"content": "Rohit: first\nMaez: one"},
            {"content": "Rohit: second\nMaez: two"},
            {"content": "Rohit: third\nMaez: three"},
            {"content": "Rohit: fourth\nMaez: four"},
        ]
        items = dialogue_anchor_items(history, limit_pairs=2)
        self.assertEqual(len(items), 2)
        joined = "\n".join(item.text for item in items)
        self.assertNotIn("first", joined)
        self.assertNotIn("one", joined)
        self.assertIn("third", joined)
        self.assertIn("fourth", joined)

    def test_dialogue_anchor_orders_newest_pair_first(self):
        from core.routing.focused_cognition import dialogue_anchor_items

        history = [
            {"content": "Rohit: first\nMaez: one"},
            {"content": "Rohit: second\nMaez: two"},
            {"content": "Rohit: third\nMaez: three"},
            {"content": "Rohit: fourth\nMaez: four"},
        ]
        items = dialogue_anchor_items(history, limit_pairs=3)
        self.assertEqual(len(items), 3)
        self.assertIn("fourth", items[0].text)
        self.assertIn("three", items[1].text)
        self.assertIn("second", items[2].text)
```

- [ ] **Step 2: Run tests to verify fail**

Run:

```bash
.venv/bin/python -m unittest tests.test_focused_cognition.DialogueAnchorTests -v
```

Expected: FAIL with `AttributeError: module 'core.routing.focused_cognition' has no attribute 'dialogue_anchor_items'`.

- [ ] **Step 3: Implement anchor helper**

In `core/routing/focused_cognition.py`, add:

```python
@dataclass(frozen=True)
class EvidenceItemSeed:
    source_type: str
    text: str
    durable_id: str


def dialogue_anchor_items(
    chat_history: Iterable[dict] | None,
    *,
    limit_pairs: int = 3,
) -> list[EvidenceItemSeed]:
    from core.brain.conversation_history import history_to_messages

    messages = history_to_messages(chat_history)
    pairs: list[tuple[str, str]] = []
    pending_user: str | None = None
    for message in messages:
        role = message.get("role")
        content = (message.get("content") or "").strip()
        if not content:
            continue
        if role == "user":
            pending_user = content
        elif role == "assistant" and pending_user:
            pairs.append((pending_user, content))
            pending_user = None

    selected = list(reversed(pairs[-limit_pairs:]))
    return [
        EvidenceItemSeed(
            source_type="dialogue_anchor",
            text=f"User: {user_text}\nMaez: {assistant_text}",
            durable_id=_content_hash(f"{user_text}\n{assistant_text}"),
        )
        for user_text, assistant_text in selected
    ]
```

- [ ] **Step 4: Run tests to verify pass**

Run:

```bash
.venv/bin/python -m unittest tests.test_focused_cognition.DialogueAnchorTests -v
```

Expected: OK.

- [ ] **Step 5: Commit**

```bash
git add core/routing/focused_cognition.py tests/test_focused_cognition.py
git commit -m "feat(focused-cognition): extract bounded dialogue anchors"
```

---

### Task 3: Working-Set Assembly With Conditional Dialogue Authority

**Files:**
- Modify: `core/routing/focused_cognition.py`
- Test: `tests/test_focused_cognition.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_focused_cognition.py`:

```python
class DialogueAwareAssembleTests(unittest.TestCase):
    def _history(self):
        return [
            {
                "content": (
                    "Rohit: Search r/LocalLLaMA right now\n"
                    "Maez: LiquidAI and Reachy Mini were the active threads."
                )
            }
        ]

    def test_direct_continuity_prioritizes_dialogue_over_stale_memory(self):
        ws = assemble_working_set(
            transcript="[memory evidence] stale journal:\n- April 6 journaling note",
            web_context="",
            owner_question="What were we talking about earlier?",
            chat_history=self._history(),
        )
        self.assertIsNotNone(ws)
        self.assertEqual(ws.items[0].source_type, "dialogue_anchor")
        self.assertIn("Search r/LocalLLaMA", ws.items[0].text)
        self.assertGreaterEqual(
            ws.ordered_evidence_text.count(f"[{ws.items[0].local_label}]"),
            2,
        )
        self.assertEqual(len(ws.items), 1)

    def test_direct_continuity_keeps_only_newest_dialogue_anchor(self):
        history = [
            {
                "content": (
                    "Rohit: What were we talking about earlier?\n"
                    "Maez: I only have the April 6 journal."
                )
            },
            {
                "content": (
                    "Rohit: For the continuity witness: bare temporal words "
                    "are freshness.\n"
                    "Maez: Bare temporal words are freshness, and newest "
                    "dialogue anchors come first."
                )
            },
        ]
        ws = assemble_working_set(
            transcript="[memory evidence] stale journal:\n- April 6 journaling note",
            web_context="",
            owner_question="What were we talking about earlier?",
            chat_history=history,
        )
        self.assertIsNotNone(ws)
        dialogue_items = [
            item for item in ws.items if item.source_type == "dialogue_anchor"
        ]
        self.assertEqual(len(dialogue_items), 1)
        self.assertIn("bare temporal words are freshness", dialogue_items[0].text)
        self.assertNotIn("I only have the April 6 journal", dialogue_items[0].text)
        self.assertEqual(ws.items[0].source_type, "dialogue_anchor")
        self.assertEqual(len(ws.items), 1)

    def test_direct_continuity_without_anchor_returns_none(self):
        ws = assemble_working_set(
            transcript="[memory evidence] stale journal:\n- April 6 journaling note",
            web_context="",
            owner_question="What were we talking about earlier?",
            chat_history=[],
        )
        self.assertIsNone(ws)

    def test_uncertain_continuity_without_anchor_returns_none_even_with_stale_evidence(self):
        ws = assemble_working_set(
            transcript="[memory evidence] stale journal:\n- April 6 journaling note",
            web_context="",
            owner_question="Anything since we were talking?",
            chat_history=[],
        )
        self.assertIsNone(ws)

    def test_uncertain_continuity_with_anchor_prioritizes_dialogue(self):
        ws = assemble_working_set(
            transcript="[memory evidence] stale journal:\n- April 6 journaling note",
            web_context="",
            owner_question="Anything since we were talking?",
            chat_history=self._history(),
        )
        self.assertIsNotNone(ws)
        self.assertEqual(ws.items[0].source_type, "dialogue_anchor")

    def test_anaphoric_uses_only_newest_dialogue_anchor(self):
        history = [
            {
                "content": (
                    "Rohit: For the continuity witness: bare temporal words "
                    "are freshness.\n"
                    "Maez: Bare temporal words are freshness, and newest "
                    "dialogue anchors come first."
                )
            },
            {
                "content": (
                    "Rohit: What were we talking about earlier?\n"
                    "Maez: We were discussing the direct-continuity fix."
                )
            },
        ]
        ws = assemble_working_set(
            transcript=_FRESH,
            web_context="",
            owner_question="Which one matters most?",
            chat_history=history,
        )
        self.assertIsNotNone(ws)
        self.assertEqual(len(ws.items), 1)
        self.assertEqual(ws.items[0].source_type, "dialogue_anchor")
        self.assertIn("direct-continuity fix", ws.items[0].text)
        self.assertNotIn("bare temporal words are freshness", ws.items[0].text)

    def test_normal_evidence_excludes_dialogue_anchor(self):
        ws = assemble_working_set(
            transcript=_FRESH,
            web_context="",
            owner_question="Search r/LocalLLaMA right now for recent local LLM posts.",
            chat_history=self._history(),
        )
        self.assertIsNotNone(ws)
        self.assertFalse(any(item.source_type == "dialogue_anchor" for item in ws.items))
```

- [ ] **Step 2: Run tests to verify fail**

Run:

```bash
.venv/bin/python -m unittest tests.test_focused_cognition.DialogueAwareAssembleTests -v
```

Expected: FAIL because `assemble_working_set` does not accept `chat_history` and/or direct continuity without query evidence returns stale memory.

- [ ] **Step 3: Update assembler signature and control flow**

Change `assemble_working_set` in `core/routing/focused_cognition.py` to:

```python
def _ranked_items_for_state(
    raw_items: list[tuple[str, str, str | None]],
    dialogue_state: DialogueContinuityState,
) -> list[tuple[str, str, str | None]]:
    def rank(item: tuple[str, str, str | None]) -> tuple[int, int]:
        source_type = item[0]
        if (
            dialogue_state.kind == ContinuityKind.DIRECT
            or dialogue_state.fail_safe_legacy
        ):
            if source_type == "dialogue_anchor":
                return (0, 0)
            return (_PRIORITY.get(source_type, 9) + 1, 0)
        if dialogue_state.kind == ContinuityKind.ANAPHORIC:
            if source_type == "dialogue_anchor":
                return (3, 0)
            return (_PRIORITY.get(source_type, 9), 0)
        return (_PRIORITY.get(source_type, 9), 0)

    return sorted(raw_items, key=rank)


def assemble_working_set(
    *,
    transcript: str,
    web_context: str,
    owner_question: str,
    chat_history: Iterable[dict] | None = None,
) -> WorkingSet | None:
    state = turn_evidence_state(transcript=transcript, web_context=web_context)
    dialogue_state = dialogue_continuity_state(owner_question)
    anchors = (
        dialogue_anchor_items(chat_history)
        if dialogue_state.needs_dialogue or dialogue_state.fail_safe_legacy
        else []
    )
    if dialogue_state.kind == ContinuityKind.DIRECT:
        anchors = anchors[:1]

    if (dialogue_state.needs_dialogue or dialogue_state.fail_safe_legacy) and not anchors:
        return None
    if not state.evidence_present and not anchors:
        return None

    raw_items: list[tuple[str, str, str | None]] = []
    if dialogue_state.kind != ContinuityKind.DIRECT:
        for marker, body in _split_blocks(transcript or ""):
            for item_text in _atomic_items(body):
                raw_items.append((_SOURCE_TYPE[marker], item_text, None))

        web_context = web_context or ""
        if web_context.strip() and _WEB_NO_RESULTS not in web_context:
            for item_text in _atomic_items(web_context):
                raw_items.append(("web_context", item_text, None))

    for anchor in anchors:
        raw_items.append((anchor.source_type, anchor.text, anchor.durable_id))

    if not raw_items:
        return None

    raw_items = _ranked_items_for_state(raw_items, dialogue_state)
    items = [
        EvidenceItem(
            local_label=f"E{index + 1}",
            source_type=source_type,
            text=text,
            durable_id=durable_id or _content_hash(text),
        )
        for index, (source_type, text, durable_id) in enumerate(raw_items)
    ]

    lines = [f"[{item.local_label}] ({item.source_type}) {item.text}" for item in items]
    top = items[0]
    lines.append(f"(most important, repeated) [{top.local_label}] {top.text}")
    ordered = "\n".join(lines)

    total_chars = len(ordered) + len(owner_question or "")
    return WorkingSet(
        items=items,
        ordered_evidence_text=ordered,
        owner_question=owner_question,
        working_set_chars=total_chars,
        working_set_tokens_est=total_chars // 4,
    )
```

- [ ] **Step 4: Run tests to verify pass**

Run:

```bash
.venv/bin/python -m unittest tests.test_focused_cognition -v
```

Expected: all focused-cognition tests OK.

- [ ] **Step 5: Commit**

```bash
git add core/routing/focused_cognition.py tests/test_focused_cognition.py
git commit -m "feat(focused-cognition): add conditional dialogue anchors"
```

---

### Task 4: Privacy Guard For Dialogue Anchors

**Files:**
- Modify: `tests/test_focused_cognition.py`

- [ ] **Step 1: Write failing/privacy regression test**

Add to `FocusedCognitionStoreTests` in `tests/test_focused_cognition.py`:

```python
    def test_dialogue_anchor_trace_stores_no_raw_dialogue_text(self):
        import sqlite3

        from core.routing.focused_cognition import (
            FocusedResult,
            GroundednessVerdict,
        )

        store = self._store()
        secret = "DIALOGUE_SECRET_MARKER_ABC"
        ws = assemble_working_set(
            transcript="",
            web_context="",
            owner_question="What were we talking about earlier?",
            chat_history=[
                {"content": f"Rohit: {secret}\nMaez: We were discussing local models."}
            ],
        )
        self.assertIsNotNone(ws)
        store.record(
            surface="telegram",
            chat_id="c1",
            working_set=ws,
            result=FocusedResult("We were discussing local models [E1]", ["E1"], ws.working_set_chars),
            verdict=GroundednessVerdict("grounded", 1.0, []),
            legacy_prompt_chars=104000,
            fallback_reason=None,
            routing_observation_id=None,
        )
        conn = sqlite3.connect(store.db_path)
        try:
            rows = conn.execute("SELECT * FROM focused_cognition_runs").fetchall()
        finally:
            conn.close()
        stored = " ".join(str(row) for row in rows)
        self.assertNotIn(secret, stored)
        self.assertIn("dialogue_anchor", stored)
```

- [ ] **Step 2: Run privacy test**

Run:

```bash
.venv/bin/python -m unittest tests.test_focused_cognition.FocusedCognitionStoreTests.test_dialogue_anchor_trace_stores_no_raw_dialogue_text -v
```

Expected: PASS if Task 3 reused existing evidence-map storage correctly. If it fails, fix `FocusedCognitionStore._evidence_map` to store only `local_label`, `source_type`, and `durable_id`.

- [ ] **Step 3: Commit**

```bash
git add tests/test_focused_cognition.py core/routing/focused_cognition.py
git commit -m "test(focused-cognition): guard dialogue trace privacy"
```

---

### Task 5: Daemon Gate And Integration

**Files:**
- Modify: `daemon/maez_daemon.py`
- Modify: `tests/test_memory_integrity_invariant.py`

- [ ] **Step 1: Write failing daemon tests**

Append to the existing daemon focused-cognition test class in `tests/test_memory_integrity_invariant.py`:

```python
    def test_daemon_continuity_no_anchor_falls_back_to_legacy(self):
        from daemon import maez_daemon

        captured: dict[str, list[dict]] = {}
        daemon = self._build_daemon_for_handle_message()

        with self._handle_message_mock_stack(maez_daemon, captured), mock.patch.dict(
            os.environ,
            {"MAEZ_FOCUSED_COGNITION_ENABLED": "1"},
        ), mock.patch(
            "core.routing.focused_cognition.focused_synthesize",
        ) as fsyn, mock.patch(
            "core.llm_client.chat",
        ) as megachat:
            megachat.return_value = types.SimpleNamespace(
                message=types.SimpleNamespace(content="legacy continuity reply")
            )
            reply = maez_daemon.MaezDaemon.handle_message(
                daemon,
                "What were we talking about earlier?",
                source="telegram_surface",
                transcript="[memory evidence] stale:\n- April 6 journal",
                chat_history=[],
            )

        self.assertEqual(reply, "legacy continuity reply")
        fsyn.assert_not_called()
        megachat.assert_called_once()

    def test_daemon_uncertain_continuity_no_anchor_falls_back_to_legacy(self):
        from daemon import maez_daemon

        captured: dict[str, list[dict]] = {}
        daemon = self._build_daemon_for_handle_message()

        with self._handle_message_mock_stack(maez_daemon, captured), mock.patch.dict(
            os.environ,
            {"MAEZ_FOCUSED_COGNITION_ENABLED": "1"},
        ), mock.patch(
            "core.routing.focused_cognition.focused_synthesize",
        ) as fsyn, mock.patch(
            "core.llm_client.chat",
        ) as megachat:
            megachat.return_value = types.SimpleNamespace(
                message=types.SimpleNamespace(content="legacy uncertain reply")
            )
            reply = maez_daemon.MaezDaemon.handle_message(
                daemon,
                "Anything since we were talking?",
                source="telegram_surface",
                transcript="[memory evidence] stale:\n- April 6 journal",
                chat_history=[],
            )

        self.assertEqual(reply, "legacy uncertain reply")
        fsyn.assert_not_called()
        megachat.assert_called_once()

    def test_daemon_continuity_with_anchor_uses_focused(self):
        from daemon import maez_daemon

        captured: dict[str, list[dict]] = {}
        daemon = self._build_daemon_for_handle_message()

        with self._handle_message_mock_stack(maez_daemon, captured), mock.patch.dict(
            os.environ,
            {"MAEZ_FOCUSED_COGNITION_ENABLED": "1"},
        ), mock.patch(
            "core.routing.focused_cognition.focused_synthesize",
        ) as fsyn, mock.patch(
            "core.routing.focused_cognition.record_focused_cognition_run",
            return_value="focused-row-1",
        ), mock.patch(
            "core.llm_client.chat",
        ) as megachat:
            from core.routing.focused_cognition import FocusedResult

            fsyn.return_value = FocusedResult("We were discussing Reddit [E1]", ["E1"], 800)
            reply = maez_daemon.MaezDaemon.handle_message(
                daemon,
                "What were we talking about earlier?",
                source="telegram_surface",
                transcript="[memory evidence] stale:\n- April 6 journal",
                chat_history=[
                    {"content": "Rohit: Search r/LocalLLaMA\nMaez: I found LiquidAI."}
                ],
            )

        self.assertEqual(reply, "We were discussing Reddit [E1]")
        fsyn.assert_called_once()
        megachat.assert_not_called()

    def test_daemon_anaphoric_with_anchor_uses_focused(self):
        from daemon import maez_daemon

        captured: dict[str, list[dict]] = {}
        daemon = self._build_daemon_for_handle_message()

        with self._handle_message_mock_stack(maez_daemon, captured), mock.patch.dict(
            os.environ,
            {"MAEZ_FOCUSED_COGNITION_ENABLED": "1"},
        ), mock.patch(
            "core.routing.focused_cognition.focused_synthesize",
        ) as fsyn, mock.patch(
            "core.routing.focused_cognition.record_focused_cognition_run",
            return_value="focused-row-1",
        ):
            from core.routing.focused_cognition import FocusedResult

            fsyn.return_value = FocusedResult("LiquidAI matters most [E1]", ["E1"], 800)
            reply = maez_daemon.MaezDaemon.handle_message(
                daemon,
                "Which one matters most?",
                source="telegram_surface",
                transcript="[fresh evidence] r/LocalLLaMA:\n- LiquidAI LFM2.5\n- Reachy Mini",
                chat_history=[
                    {"content": "Rohit: Search r/LocalLLaMA\nMaez: LiquidAI and Reachy were active."}
                ],
            )

        self.assertEqual(reply, "LiquidAI matters most [E1]")
        fsyn.assert_called_once()
```

- [ ] **Step 2: Run daemon tests to verify fail**

Run:

```bash
.venv/bin/python -m unittest \
  tests.test_memory_integrity_invariant.DaemonHandleMessageContract.test_daemon_continuity_no_anchor_falls_back_to_legacy \
  tests.test_memory_integrity_invariant.DaemonHandleMessageContract.test_daemon_uncertain_continuity_no_anchor_falls_back_to_legacy \
  tests.test_memory_integrity_invariant.DaemonHandleMessageContract.test_daemon_continuity_with_anchor_uses_focused \
  tests.test_memory_integrity_invariant.DaemonHandleMessageContract.test_daemon_anaphoric_with_anchor_uses_focused \
  -v
```

Expected: at least the anchored continuity tests FAIL because focused candidate is gated only on `evidence_state.evidence_present` and assembler is not receiving `chat_history`.

- [ ] **Step 3: Update daemon gate**

In `daemon/maez_daemon.py`, just before `_focused_candidate`, import/compute dialogue state:

```python
        try:
            from core.routing.focused_cognition import (
                dialogue_continuity_state as _dialogue_continuity_state,
            )

            _dialogue_state = _dialogue_continuity_state(text)
        except Exception:
            _dialogue_state = None
```

Replace `_focused_candidate = ...` with:

```python
        _dialogue_needs_or_uncertain = bool(
            _dialogue_state
            and (
                getattr(_dialogue_state, "needs_dialogue", False)
                or getattr(_dialogue_state, "fail_safe_legacy", False)
            )
        )
        _focused_candidate = (
            _focused_cognition_enabled()
            and source != "voice"
            and (
                _evidence_state.evidence_present
                or _dialogue_needs_or_uncertain
            )
        )
```

Then update the assembler call:

```python
                    _focused_working_set = _assemble_working_set(
                        transcript=transcript,
                        web_context=web_context,
                        owner_question=text,
                        chat_history=chat_history,
                    )
```

After the assembler call, before `if _focused_working_set is not None:`, add skip logging for the fail-safe:

```python
                    if _focused_working_set is None and _dialogue_needs_or_uncertain:
                        logger.info(
                            "focused_cognition_skip surface=%s reason=continuity_no_dialogue_anchor",
                            source,
                        )
```

- [ ] **Step 4: Run daemon tests to verify pass**

Run the same four tests from Step 2.

Expected: OK.

- [ ] **Step 5: Run focused integration floor**

Run:

```bash
.venv/bin/python -m unittest tests.test_focused_cognition tests.test_memory_integrity_invariant -v
```

Expected: OK. Known unrelated ResourceWarnings may appear but must not fail.

- [ ] **Step 6: Commit**

```bash
git add daemon/maez_daemon.py tests/test_memory_integrity_invariant.py
git commit -m "feat(daemon): preserve continuity in focused cognition gate"
```

---

### Task 6: Verification And Handoff

**Files:**
- Verify only; no planned source edits.

- [ ] **Step 1: Run focused suite**

Run:

```bash
.venv/bin/python -m unittest \
  tests.test_focused_cognition \
  tests.test_evidence_state \
  tests.test_routing_observation \
  tests.test_memory_integrity_invariant \
  -v
```

Expected: OK.

- [ ] **Step 2: Run lint on touched files**

Run:

```bash
.venv/bin/ruff check \
  core/routing/focused_cognition.py \
  daemon/maez_daemon.py \
  tests/test_focused_cognition.py \
  tests/test_memory_integrity_invariant.py
```

Expected: `All checks passed!`

- [ ] **Step 3: Run broad suite floor**

Run:

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_*.py' 2>&1 | tee /tmp/maez-tier4-continuity-broad.log | grep -E '^(Ran|OK|FAILED)'
```

Expected floor: broad suite holds the established floor (recently 5030 tests, 2 deterministic failures plus optional cloud-retirement flake; no new routing/focused-cognition failures). If a new failure appears in touched areas, stop and debug.

- [ ] **Step 4: Document predicted effect for the final commit or handoff**

Include this in the final behavior-affecting commit body or handoff:

```markdown
## Predicted effect

With MAEZ_FOCUSED_COGNITION_ENABLED=1, continuity-shaped text turns now preserve recent dialogue:
- "What were we talking about earlier?" uses dialogue_anchor evidence first when chat_history is available.
- "Which one matters most?" includes recent dialogue as referent support while keeping current evidence primary.
- If a continuity-shaped turn has no usable chat_history, focused cognition skips and the legacy path handles the turn.
- Normal evidence asks remain unchanged and do not include dialogue anchors.
```

- [ ] **Step 5: Hand off for cross-lane verification**

Report:

- commits created
- focused test command output
- ruff output
- broad-suite floor output
- confirmation that `test_daemon_uncertain_continuity_no_anchor_falls_back_to_legacy` exists and passes
- confirmation that no raw dialogue text is stored in focused traces

Do not flip `MAEZ_FOCUSED_COGNITION_ENABLED` default-on until Obs 16 crosses live.
