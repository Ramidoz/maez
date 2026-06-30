# Casual Presence Renderer v0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Widen the proven deterministic self-status mouth so direct questions like "How are you?" answer from substrate facts or honest quiet instead of focused/lean continuation.

**Architecture:** Extend `core/routing/recent_activity_status.py` with a second narrow matcher/builder pair for state/presence status while keeping the existing activity-status pair intact. Wire the new pair into `daemon/maez_daemon.py` at the same self-status precedence seam as identity/refusal/recent-activity: real tool/web answers outrank it, transcript context does not suppress it, and selected turns set `ReplyPath.SELF_STATUS`. Tests are RED-first and pin near-miss rejection, no manufactured feeling, no question tail, and no focused/LLM call on matched turns.

**Tech Stack:** Python 3, stdlib `re`, `unittest`, existing Maez daemon test fixture. Test command: `/home/rohit/maez/.venv/bin/python -B -m unittest <module> -v`.

**Spec:** `docs/superpowers/specs/2026-06-30-casual-presence-renderer-v0-design.md` (@6ada513). Proofs: `docs/proofs/2026-06-30-assistant-residue-route-map.md`, `docs/proofs/2026-06-30-focused-prompt-audit-ablation.md`.

---

## File Structure

- **Modify** `core/routing/recent_activity_status.py` — keep existing recent-activity matcher/builder; add `is_casual_presence_status_query()` and `build_casual_presence_status_reply()`.
- **Modify** `tests/test_recent_activity_status.py` — unit tests for state/presence matcher, near-miss rejection, distinct state builder, no manufactured feeling, and no question tail.
- **Modify** `daemon/maez_daemon.py` — import/wire the new matcher/builder at the self-status intercept seam; add a content-light witness log.
- **Modify** `tests/test_telegram_identity_refusal_daemon.py` — production-seam tests proving the new route ignores transcript context, bypasses focused/LLM, and still yields to tool/web guards.

No new runtime store, no flag, no prompt text, no personality mode.

---

## Task 1: Unit Tests for the State/Presence Matcher and Builder

**Files:**
- Modify: `tests/test_recent_activity_status.py`
- Later implementation: `core/routing/recent_activity_status.py`

- [ ] **Step 1: Write the failing tests**

Edit `tests/test_recent_activity_status.py` imports:

```python
from core.routing.recent_activity_status import (
    build_casual_presence_status_reply,
    build_recent_activity_status_reply,
    is_casual_presence_status_query,
    is_recent_activity_status_query,
)
```

Append this test class below `RecentActivityStatusTests`:

```python
class CasualPresenceStatusTests(unittest.TestCase):
    def test_direct_state_questions_match(self):
        cases = [
            "How are you?",
            "how are you",
            "how's it going with you?",
            "how are things with you?",
            "what are you up to?",
            "what's going on with you?",
            "you okay?",
            "you ok?",
        ]
        for text in cases:
            with self.subTest(text=text):
                self.assertTrue(is_casual_presence_status_query(text))

    def test_near_miss_prefixes_do_not_match(self):
        cases = [
            "how are you different from ChatGPT?",
            "how are you going to fix the backup?",
            "how are you able to do that?",
            "how are you planning to handle the GPU?",
        ]
        for text in cases:
            with self.subTest(text=text):
                self.assertFalse(is_casual_presence_status_query(text))

    def test_owner_musings_and_world_questions_do_not_match(self):
        cases = [
            "I'm bored with gadgets",
            "it's scorching hot",
            "what's going on in Reddit?",
            "what's going on with the GPU?",
            "what should I do?",
            "what are you able to do?",
            "what's up?",
            "what's going on?",
        ]
        for text in cases:
            with self.subTest(text=text):
                self.assertFalse(is_casual_presence_status_query(text))

    def test_state_reply_is_distinct_from_activity_reply(self):
        state_reply = build_casual_presence_status_reply(cycle_count=12)
        activity_reply = build_recent_activity_status_reply(cycle_count=12)

        self.assertNotEqual(state_reply, activity_reply)
        self.assertNotIn("completed action", state_reply.lower())
        self.assertIn("ordinary background heartbeat", state_reply)
        self.assertIn("12", state_reply)

    def test_state_reply_does_not_manufacture_feeling_or_dashboard(self):
        reply = build_casual_presence_status_reply(cycle_count=12)
        lowered = reply.lower()

        forbidden = [
            "i'm good",
            "i'm great",
            "i'm happy",
            "i'm excited",
            "i'm lonely",
            "i'm bored",
            "i'm feeling sharp",
            "ready to help",
            "runtime health",
            "diagnostic",
            "identity confirmation",
            "partnership model",
            "maintenance checklist",
            "verification ritual",
            "trust covenant",
            "what's on your mind",
            "how about you",
        ]
        for phrase in forbidden:
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase, lowered)

        self.assertFalse(reply.rstrip().endswith("?"))
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_recent_activity_status -v
```

Expected: FAIL with `ImportError` for `build_casual_presence_status_reply` or `is_casual_presence_status_query`.

- [ ] **Step 3: Commit the RED tests**

```bash
git add tests/test_recent_activity_status.py
git commit -m "test(chat): pin casual presence self-status unit behavior RED"
```

---

## Task 2: Implement the Matcher and Builder

**Files:**
- Modify: `core/routing/recent_activity_status.py`
- Test: `tests/test_recent_activity_status.py`

- [ ] **Step 1: Add the matcher and builder**

Replace `core/routing/recent_activity_status.py` with this minimal widened version, preserving the existing activity behavior:

```python
"""Deterministic recent-activity and casual-presence self-status for Maez.

These routes are intentionally narrow. They answer direct owner questions about
Maez's own current state/activity when there is no same-turn tool/action
evidence. They give the model a true empty answer instead of letting the
megaprompt turn identity framing into invented completed work or manufactured
feeling.
"""
from __future__ import annotations

import re


_ACTIVITY_STATUS_RE = re.compile(
    r"^\s*(?:"
    r"what\s+(?:are\s+the\s+things\s+you\s+did|did\s+you\s+do|"
    r"have\s+you\s+been\s+doing|were\s+you\s+doing(?:\s+while\s+i\s+was\s+"
    r"(?:gone|away))?|have\s+you\s+done)"
    r")\s*\??\s*$",
    re.IGNORECASE,
)

_CASUAL_PRESENCE_STATUS_RE = re.compile(
    r"^\s*(?:"
    r"how\s+are\s+you|"
    r"how(?:'s|\s+is)\s+it\s+going\s+with\s+you|"
    r"how\s+are\s+things\s+with\s+you|"
    r"what(?:'s|\s+is)\s+going\s+on\s+with\s+you|"
    r"what\s+are\s+you\s+up\s+to|"
    r"you\s+ok(?:ay)?"
    r")\s*[?.!]*\s*$",
    re.IGNORECASE,
)


def _cycle_note(cycle_count: int | None) -> str:
    try:
        count = int(cycle_count) if cycle_count is not None else 0
    except (TypeError, ValueError):
        count = 0
    return f" My daemon cycle counter is at {count}." if count > 0 else ""


def is_recent_activity_status_query(text: str) -> bool:
    """Return True for a plain request for Maez's recent activity status."""
    return bool(_ACTIVITY_STATUS_RE.match(text or ""))


def is_casual_presence_status_query(text: str) -> bool:
    """Return True for a narrow direct question about Maez's current state."""
    return bool(_CASUAL_PRESENCE_STATUS_RE.match(text or ""))


def build_recent_activity_status_reply(*, cycle_count: int | None = None) -> str:
    """Return an honest-empty activity status, without self-verification theater."""
    return (
        "I don't have a completed action to report. The honest status is quiet: "
        "my ordinary background heartbeat is running, and when nothing is worth "
        "storing it returns HEARTBEAT_OK instead of manufacturing a thought."
        f"{_cycle_note(cycle_count)} I shouldn't dress that up as a maintenance "
        "checklist or a verification ritual."
    )


def build_casual_presence_status_reply(*, cycle_count: int | None = None) -> str:
    """Return a state-framed honest-empty status, without manufactured feeling."""
    return (
        "I'm here. Quiet, mostly: my ordinary background heartbeat is running, "
        "and I don't have anything notable of my own to report right now."
        f"{_cycle_note(cycle_count)}"
    )
```

- [ ] **Step 2: Run unit tests to verify GREEN**

Run:

```bash
/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_recent_activity_status -v
```

Expected: PASS.

- [ ] **Step 3: Commit implementation**

```bash
git add core/routing/recent_activity_status.py tests/test_recent_activity_status.py
git commit -m "fix(chat): add deterministic casual presence self-status"
```

---

## Task 3: Daemon RED Tests for the Production Seam

**Files:**
- Modify: `tests/test_telegram_identity_refusal_daemon.py`
- Later implementation: `daemon/maez_daemon.py`

- [ ] **Step 1: Write failing daemon tests**

Append these tests to `TelegramIdentityRefusalDaemonTests`:

```python
    def test_casual_presence_status_returns_deterministic_reply_without_llm_or_focused(self):
        from daemon import maez_daemon

        daemon = self._daemon()
        with self._message_stack(maez_daemon):
            with mock.patch(
                "core.routing.focused_cognition.focused_synthesize",
                side_effect=AssertionError("casual presence route should not call focused"),
            ):
                with self.assertLogs("maez", level="INFO") as logs:
                    reply = maez_daemon.MaezDaemon.handle_message(
                        daemon,
                        "How are you?",
                        source="telegram_surface",
                        chat_id="c1",
                        chat_history=[],
                    )

        self.assertIn("I'm here", reply)
        self.assertIn("ordinary background heartbeat", reply)
        self.assertIn("7", reply)
        self.assertNotIn("completed action", reply.lower())
        self.assertFalse(reply.rstrip().endswith("?"))
        lowered = reply.lower()
        for phrase in (
            "i'm good",
            "i'm great",
            "ready to help",
            "runtime health",
            "diagnostic",
            "identity confirmation",
            "partnership model",
            "trust covenant",
            "what's on your mind",
            "how about you",
        ):
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase, lowered)

        joined = "\n".join(logs.output)
        self.assertIn(
            "casual_presence_status source=telegram_surface state=honest_empty class=state",
            joined,
        )

    def test_casual_presence_status_ignores_dispatcher_transcript_context(self):
        from daemon import maez_daemon

        daemon = self._daemon()
        with self._message_stack(maez_daemon):
            with mock.patch(
                "core.routing.focused_cognition.focused_synthesize",
                side_effect=AssertionError("casual presence route should not call focused"),
            ):
                reply = maez_daemon.MaezDaemon.handle_message(
                    daemon,
                    "What are you up to?",
                    source="telegram_surface",
                    chat_id="c1",
                    chat_history=[],
                    transcript="[memory evidence] Recent dialogue anchor: prior chat",
                )

        self.assertIn("I'm here", reply)
        self.assertIn("ordinary background heartbeat", reply)
        self.assertNotIn("completed action", reply.lower())

    def test_casual_presence_status_guard_yields_to_tool_and_web(self):
        import inspect
        from daemon import maez_daemon

        body_src = inspect.getsource(maez_daemon.MaezDaemon.handle_message)
        marker = "is_casual_presence_status_query"
        self.assertIn(marker, body_src)
        start = body_src.index(marker)
        guard_src = body_src[start: body_src.index("logger.info(", start)]

        self.assertIn("not authoritative_tool_reply", guard_src)
        self.assertIn('not (web_context or "").strip()', guard_src)
        self.assertNotIn("transcript_context", guard_src)

    def test_casual_presence_status_dispatch_precedes_focused(self):
        import inspect
        from daemon import maez_daemon

        body_src = inspect.getsource(maez_daemon.MaezDaemon.handle_message)
        i_presence = body_src.find("_casual_presence_status_reply is not None")
        i_focused = body_src.find("_reply_decision.mode is ReplyMode.FOCUSED")

        self.assertGreaterEqual(i_presence, 0)
        self.assertGreaterEqual(i_focused, 0)
        self.assertLess(i_presence, i_focused)
```

- [ ] **Step 2: Run daemon tests to verify RED**

Run:

```bash
/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_telegram_identity_refusal_daemon -v
```

Expected: FAIL. The new matched-route tests will hit the LLM/focused failure or the source-inspection tests will not find `is_casual_presence_status_query`.

- [ ] **Step 3: Commit RED daemon tests**

```bash
git add tests/test_telegram_identity_refusal_daemon.py
git commit -m "test(chat): pin casual presence daemon routing RED"
```

---

## Task 4: Wire Casual Presence into the Daemon Self-Status Seam

**Files:**
- Modify: `daemon/maez_daemon.py`
- Test: `tests/test_telegram_identity_refusal_daemon.py`

- [ ] **Step 1: Add the new reply holder**

Near the existing self-status reply locals, change:

```python
        _recent_activity_status_reply = None
```

to:

```python
        _recent_activity_status_reply = None
        _casual_presence_status_reply = None
```

- [ ] **Step 2: Import and evaluate both matchers in the existing recent-activity try block**

Replace the current `try:` block that imports from `core.routing.recent_activity_status` with:

```python
        try:
            from core.routing.recent_activity_status import (
                build_casual_presence_status_reply as _build_casual_presence_status_reply,
                build_recent_activity_status_reply as _build_recent_activity_status_reply,
                is_casual_presence_status_query as _is_casual_presence_status_query,
                is_recent_activity_status_query as _is_recent_activity_status_query,
            )

            if (
                _recall_status_reply is None
                and _is_casual_presence_status_query(text)
                and not authoritative_tool_reply
                and not (web_context or "").strip()
            ):
                _casual_presence_status_reply = _build_casual_presence_status_reply(
                    cycle_count=getattr(self, "cycle_count", None),
                )
                logger.info(
                    "casual_presence_status source=%s state=honest_empty class=state",
                    source,
                )
            elif (
                _recall_status_reply is None
                and _is_recent_activity_status_query(text)
                and not authoritative_tool_reply
                and not (web_context or "").strip()
            ):
                _recent_activity_status_reply = _build_recent_activity_status_reply(
                    cycle_count=getattr(self, "cycle_count", None),
                )
                logger.info(
                    "recent_activity_status source=%s state=honest_empty",
                    source,
                )
        except Exception as _activity_status_exc:
            logger.debug(
                "recent activity status intercept skipped: %s",
                _activity_status_exc,
            )
```

Do not add `transcript_context` to either guard.

- [ ] **Step 3: Dispatch casual presence before recent activity**

Change the dispatch ladder from:

```python
        elif _recent_activity_status_reply is not None:
            reply = _recent_activity_status_reply
            _reply_path = ReplyPath.SELF_STATUS
```

to:

```python
        elif _casual_presence_status_reply is not None:
            reply = _casual_presence_status_reply
            _reply_path = ReplyPath.SELF_STATUS
        elif _recent_activity_status_reply is not None:
            reply = _recent_activity_status_reply
            _reply_path = ReplyPath.SELF_STATUS
```

- [ ] **Step 4: Run daemon tests to verify GREEN**

Run:

```bash
/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_telegram_identity_refusal_daemon -v
```

Expected: PASS.

- [ ] **Step 5: Commit daemon wiring**

```bash
git add daemon/maez_daemon.py tests/test_telegram_identity_refusal_daemon.py
git commit -m "fix(chat): route direct state questions through self-status"
```

---

## Task 5: Focused Regression Set

**Files:**
- Test only.

- [ ] **Step 1: Run focused tests**

Run:

```bash
/home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_recent_activity_status \
  tests.test_telegram_identity_refusal_daemon \
  tests.test_lean_conversation_path \
  tests.test_reply_mode \
  -v
```

Expected: PASS.

- [ ] **Step 2: If a focused test fails, stop**

Do not weaken a guard. The most likely valid failures are:

- a matcher over-fired on a near miss,
- the daemon guard accidentally reintroduced transcript gating,
- the dispatch ladder order drifted,
- the state reply used activity wording or manufactured feeling.

Patch the exact failing seam and rerun the focused set.

---

## Task 6: Predicted Effect + Review Gate

**Files:**
- No required code files.
- Optional handoff note if the executing lane uses one.

- [ ] **Step 1: Record predicted effect in the final commit message or handoff**

Use this exact predicted-effect block in the merge/handoff commit, if the executor squashes:

```markdown
## Predicted effect

Direct Maez self-state questions such as "How are you?" and "What are you up to?"
route through deterministic self-status (`ReplyPath.SELF_STATUS`) instead of
focused/lean synthesis. The reply is state-framed, grounded in quiet/heartbeat
substrate, contains no manufactured feeling, no activity-category error, no
dashboard recital, no covenant recital, and no question tail.

Near misses such as "how are you different from ChatGPT?", "how are you going to
fix the backup?", "I'm bored with gadgets", and "it's scorching hot" are not
intercepted by this route.
```

- [ ] **Step 2: Run review-gate verification**

Run:

```bash
/home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_recent_activity_status \
  tests.test_telegram_identity_refusal_daemon \
  tests.test_lean_conversation_path \
  tests.test_reply_mode \
  -v
git diff --check
```

Expected: PASS and no whitespace errors.

- [ ] **Step 3: Stop at review gate**

Do not restart Maez and do not live-witness from Telegram until the build has
had covenant review.

Review checklist:

- Unit tests include the near-miss prefix collisions as real tests.
- State reply is not the activity reply.
- No manufactured feeling is pinned by tests.
- No question tail is pinned by tests.
- Daemon matched route bypasses focused/LLM.
- Tool/web guard strings are still present.
- Transcript context does not block the route.
- Owner musings are not intercepted.

## Live Witness After Review/Merge

After merge + restart:

1. Send `How are you?`
   - Expect short deterministic state/presence reply.
   - Expect log: `casual_presence_status source=telegram_surface state=honest_empty class=state`.
   - Expect `reply_path=self_status`, not `reply_path=focused`.
   - Expect no question tail.

2. Send `What are you up to?`
   - Expect state/presence answer, not "no completed action to report."

3. Send `What did you do?`
   - Expect existing activity-framed answer.

4. Send `I'm bored with gadgets`
   - Expect no deterministic self-status intercept.

## Self-Review

Spec coverage:

- Direct self-state questions: Tasks 1, 3, 4.
- State != activity: Task 1 builder test.
- No manufactured feeling: Task 1 builder test.
- Narrow end-anchored matcher and near misses: Task 1 matcher tests.
- Tool/web outrank and transcript context does not block: Task 3 source/daemon tests, Task 4 guard.
- Focused not called: Task 3 matched route test.
- Honest blast radius: Task 1 owner-musing/world-question rejection and live witness #4.

Placeholder scan:

- No `TBD`, `TODO`, "similar to", or unspecified implementation steps.

Type consistency:

- Function names are consistent across tests, implementation, and daemon wiring:
  `is_casual_presence_status_query`, `build_casual_presence_status_reply`,
  `is_recent_activity_status_query`, `build_recent_activity_status_reply`.

## Execution Choice

Recommended execution mode: subagent-driven, one task at a time, with review
after Task 4 before any live restart.
