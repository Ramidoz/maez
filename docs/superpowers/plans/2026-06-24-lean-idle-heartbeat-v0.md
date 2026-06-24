# Lean Idle Heartbeat v0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Nervous-System Slice B: a flag-gated lean idle heartbeat that records bounded private thoughts on quiet floor wakes without touching soul, user-facing memory, broadcasts, tools, or foreground replies.

**Architecture:** Add one pure module, `core/cognition/lean_idle_heartbeat.py`, that builds a lean prompt, sanitizes one private note, writes through `PrivateThoughts.record_signal()`, and emits content-light receipts. Add one narrow daemon seam before `_reason()` that runs this module only for doorman `wake_min_floor`; shadow mode observes and keeps legacy behavior, enabled mode returns `HEARTBEAT_OK` to prevent the old fat prompt from writing raw memory.

**Tech Stack:** Python stdlib, existing `daemon/maez_daemon.py`, existing `core.infra.private_thoughts.PrivateThoughts`, existing `core.routing.self_card`, existing `core.routing.self_card_time`, existing unittest suite.

---

## File Structure

- Create `core/cognition/lean_idle_heartbeat.py`
  - Pure heartbeat data types, prompt builder, output sanitizer, private-thought writer, duplicate suppression, content-light receipt builder.
  - No imports from daemon, dream state, developmental heartbeat, memory manager, soul writers, web/search, or action engine.
- Create `tests/test_lean_idle_heartbeat.py`
  - Unit tests for prompt shape, output sanitizer, private thought envelope, duplicate suppression, and content-light receipts.
- Modify `daemon/maez_daemon.py`
  - Add flags `MAEZ_LEAN_IDLE_HEARTBEAT_SHADOW` and `MAEZ_LEAN_IDLE_HEARTBEAT_ENABLED`.
  - Add pure eligibility helper.
  - Add `_maybe_run_lean_idle_heartbeat(...)` method.
  - Insert the method before `_reason(...)` in the doorman wake branch.
- Create `tests/test_lean_idle_daemon.py`
  - Seam tests proving flag-off byte-identical, shadow no write/no intercept, enabled floor wake intercept, non-floor wake no intercept, and no public memory/broadcast path.
- Create `docs/proofs/2026-06-24-lean-idle-heartbeat-v0-task0.md`
  - Task-0 proof gates from the spec.
- Create `docs/handoffs/2026-06-24-lean-idle-heartbeat-v0-handoff.md`
  - Review-gate artifact and owner breath.

---

### Task 0: Proof Gate

**Files:**
- Create: `docs/proofs/2026-06-24-lean-idle-heartbeat-v0-task0.md`
- Read-only proof targets: `daemon/maez_daemon.py`, `core/cognition/cycle_doorman.py`, `core/infra/private_thoughts.py`, `core/brain/developmental_heartbeat.py`, `core/evolution/dream_state.py`

- [ ] **Step 1: Prove the live loop and doorman seam**

Run:

```bash
rg -n "def _loop|def _reason|_cycle_doorman_gate_decision|floor_wake|wake_min_floor|self.memory.store|cycle_end" daemon/maez_daemon.py core/cognition/cycle_doorman.py
```

Expected:
- `_loop()` computes `_cycle_doorman_gate`.
- `_CycleDoormanGateDecision.floor_wake` exists.
- `_reason()` is called only after `gate.wake`.
- non-empty `_reason()` output eventually reaches `self.memory.store(...)` and websocket `cycle_end`.

- [ ] **Step 2: Prove private-thought writer tuple**

Run:

```bash
rg -n "SELF_WONDERING|ProducerId|SignalClass|def record_signal|allowed_flows|derived_signals" core/infra/private_thoughts.py
```

Expected:
- `SignalKind.SELF_WONDERING` maps to `ProducerId.SELF_WONDERING` and `SignalClass.SELF_OBSERVATION`.
- `record_signal()` exists and enforces the contextual-integrity envelope.
- `derived_signals()` is content-light.

- [ ] **Step 3: Prove no existing lean heartbeat producer exists**

Run:

```bash
rg -n "lean_idle|idle_heartbeat|heartbeat.*private|SELF_WONDERING|record_signal\\(" daemon core tests
```

Expected:
- no existing `lean_idle_heartbeat` module or daemon producer;
- any existing `SELF_WONDERING` usage is not a production idle heartbeat.

- [ ] **Step 4: Prove what not to reuse**

Run:

```bash
rg -n "store_core|apply_dream|dream|developmental_heartbeat|soul" core/brain/developmental_heartbeat.py core/evolution/dream_state.py
```

Expected:
- `developmental_heartbeat.py` writes core memory;
- `dream_state.py` has dream/soul-adjacent proposal paths;
- neither is used in this slice.

- [ ] **Step 5: Write the proof doc**

Create `docs/proofs/2026-06-24-lean-idle-heartbeat-v0-task0.md` with:

```markdown
# Lean Idle Heartbeat v0 Task 0 Proof

Status: GO

## Loop Seam
- `_loop()` computes `_cycle_doorman_gate` before `_reason()`.
- `wake_min_floor` is exposed as `_CycleDoormanGateDecision.floor_wake`.
- Non-empty `_reason()` output reaches lived memory and `cycle_end`; returning `HEARTBEAT_OK` avoids both.

## Private Thought Seam
- `PrivateThoughts.record_signal()` is the existing contextual-integrity writer.
- `SignalKind.SELF_WONDERING` maps to `ProducerId.SELF_WONDERING` and `SignalClass.SELF_OBSERVATION`.
- `derived_signals()` is content-light and does not expose raw thought text.

## Reuse / Non-Reuse
- No existing lean idle heartbeat producer exists.
- `developmental_heartbeat.py` and `dream_state.py` are explicitly not reused because they touch memory/soul-adjacent paths.

## Stop Conditions Checked
- no new scheduler required;
- no soul writer required;
- no web/action path required;
- no foreground reply path required.
```

- [ ] **Step 6: Commit**

Run:

```bash
git add docs/proofs/2026-06-24-lean-idle-heartbeat-v0-task0.md
git commit -m "docs(nervous-system): prove lean idle heartbeat seams"
```

---

### Task 1: Pure Lean Heartbeat Module

**Files:**
- Create: `core/cognition/lean_idle_heartbeat.py`
- Create: `tests/test_lean_idle_heartbeat.py`

- [ ] **Step 1: Write failing tests for prompt and sanitizer**

Create `tests/test_lean_idle_heartbeat.py` with these initial tests:

```python
from __future__ import annotations

import unittest

from core.cognition.lean_idle_heartbeat import (
    HEARTBEAT_VERSION,
    LeanIdleFacts,
    build_lean_idle_prompt,
    sanitize_private_note,
)


class LeanIdleHeartbeatTest(unittest.TestCase):
    def test_prompt_is_lean_and_excludes_flood_sources(self) -> None:
        prompt = build_lean_idle_prompt(
            LeanIdleFacts(
                cycle=44,
                doorman_reason="wake_min_floor",
                self_card_text="SELF CARD\n- Bond: partnership",
                private_signal_summary={"self_observation": 2},
            )
        )

        self.assertIn("LEAN IDLE HEARTBEAT", prompt.text)
        self.assertIn("SELF CARD", prompt.text)
        self.assertIn("wake_min_floor", prompt.text)
        self.assertLess(len(prompt.text), 4000)
        for forbidden in (
            "git status",
            "reddit",
            "proactive search",
            "=== EVIDENCE",
            "Memory stats:",
            "owner replied",
            "owner seemed pleased",
        ):
            self.assertNotIn(forbidden, prompt.text)
        self.assertEqual(prompt.version, HEARTBEAT_VERSION)
        self.assertIn("self_card", prompt.fact_keys)

    def test_sanitizer_accepts_private_note_and_caps_length(self) -> None:
        raw = "<final>" + ("I notice the quiet floor wake and can carry this as a private note. " * 20) + "</final>"

        note = sanitize_private_note(raw)

        self.assertIsNotNone(note)
        self.assertLessEqual(len(note.text), 600)
        self.assertNotIn("<final>", note.text)

    def test_sanitizer_treats_heartbeat_ok_as_no_write(self) -> None:
        note = sanitize_private_note("<final>HEARTBEAT_OK</final>")

        self.assertIsNone(note)

    def test_sanitizer_rejects_owner_addressed_or_action_output(self) -> None:
        for raw in (
            "Rohit, I should tell you this.",
            "I should search the web for this.",
            "Run a command to check the machine.",
            "Send Rohit a message later.",
        ):
            with self.subTest(raw=raw):
                self.assertIsNone(sanitize_private_note(raw))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
/home/rohit/maez/.venv/bin/python -m unittest tests.test_lean_idle_heartbeat
```

Expected: import failure because `core.cognition.lean_idle_heartbeat` does not exist.

- [ ] **Step 3: Implement the pure module**

Create `core/cognition/lean_idle_heartbeat.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from collections.abc import Mapping


HEARTBEAT_VERSION = "lean_idle_heartbeat.v0"
HEARTBEAT_OK = "HEARTBEAT_OK"
MAX_PRIVATE_NOTE_CHARS = 600  # TEMPORARY scaffold, not learned salience.
_FINAL_TAG_RE = re.compile(r"<final>(.*?)</final>", re.DOTALL | re.IGNORECASE)
_OWNER_ADDRESS_RE = re.compile(r"\\b(rohit\\s*,|tell\\s+rohit|ask\\s+rohit|message\\s+rohit|send\\s+rohit)\\b", re.IGNORECASE)
_ACTION_RE = re.compile(r"\\b(search\\s+the\\s+web|run\\s+a\\s+command|execute|open\\s+the\\s+browser|send\\s+a\\s+message)\\b", re.IGNORECASE)


@dataclass(frozen=True)
class LeanIdleFacts:
    cycle: int
    doorman_reason: str
    self_card_text: str
    private_signal_summary: Mapping[str, object] | None = None


@dataclass(frozen=True)
class LeanIdlePrompt:
    text: str
    fact_keys: tuple[str, ...]
    sha256: str
    chars: int
    version: str = HEARTBEAT_VERSION


@dataclass(frozen=True)
class PrivateNote:
    text: str
    sha256: str
    chars: int


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _compact(text: object) -> str:
    return " ".join(str(text or "").split())


def _content_light_json(value: Mapping[str, object] | None) -> str:
    if not value:
        return "{}"
    safe: dict[str, object] = {}
    for key, item in value.items():
        if isinstance(item, (int, float, bool)) or item is None:
            safe[str(key)] = item
        elif isinstance(item, str):
            safe[str(key)] = _compact(item)[:80]
        else:
            safe[str(key)] = str(type(item).__name__)
    return json.dumps(safe, sort_keys=True)


def build_lean_idle_prompt(facts: LeanIdleFacts) -> LeanIdlePrompt:
    self_card = _compact(facts.self_card_text)
    private_summary = _content_light_json(facts.private_signal_summary)
    fact_keys = ("self_card", "cycle", "doorman_reason", "private_signal_summary")
    text = (
        "LEAN IDLE HEARTBEAT\\n"
        "This is a private notebook beat, not a reply to the owner.\\n"
        "Use only the facts below. Do not search, act, message, or propose contacting the owner.\\n"
        f"If nothing is worth privately carrying, answer exactly {HEARTBEAT_OK}.\\n"
        f"If there is a private note, write at most {MAX_PRIVATE_NOTE_CHARS} characters.\\n\\n"
        "FACTS\\n"
        f"- cycle: {int(facts.cycle)}\\n"
        f"- doorman_reason: {_compact(facts.doorman_reason)}\\n"
        f"- private_signal_summary: {private_summary}\\n\\n"
        "SELF CARD\\n"
        f"{self_card}\\n"
    )
    return LeanIdlePrompt(
        text=text,
        fact_keys=fact_keys,
        sha256=_sha256(text),
        chars=len(text),
    )


def _extract_final(text: str) -> str:
    match = _FINAL_TAG_RE.search(text or "")
    return match.group(1).strip() if match else (text or "").strip()


def sanitize_private_note(raw_text: object) -> PrivateNote | None:
    text = _compact(_extract_final(str(raw_text or "")))
    if not text:
        return None
    if text.strip().upper() == HEARTBEAT_OK:
        return None
    if _OWNER_ADDRESS_RE.search(text) or _ACTION_RE.search(text):
        return None
    if len(text) > MAX_PRIVATE_NOTE_CHARS:
        text = text[: MAX_PRIVATE_NOTE_CHARS - 4].rstrip() + " ..."
    return PrivateNote(text=text, sha256=_sha256(text), chars=len(text))
```

- [ ] **Step 4: Run tests and verify GREEN**

Run:

```bash
/home/rohit/maez/.venv/bin/python -m unittest tests.test_lean_idle_heartbeat
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

Run:

```bash
git add core/cognition/lean_idle_heartbeat.py tests/test_lean_idle_heartbeat.py
git commit -m "feat(nervous-system): add lean idle heartbeat prompt"
```

---

### Task 2: Private Thought Writer and Receipts

**Files:**
- Modify: `core/cognition/lean_idle_heartbeat.py`
- Modify: `tests/test_lean_idle_heartbeat.py`

- [ ] **Step 1: Add failing tests for private writes and duplicate suppression**

Append to `tests/test_lean_idle_heartbeat.py`:

```python
import json
import tempfile
from pathlib import Path

from core.infra.private_thoughts import PrivateThoughts
from core.cognition.lean_idle_heartbeat import (
    LeanIdleResult,
    run_lean_idle_heartbeat,
)


class _FakeMessage:
    def __init__(self, content: str):
        self.content = content


class _FakeResponse:
    def __init__(self, content: str):
        self.message = _FakeMessage(content)
```

Add methods inside `LeanIdleHeartbeatTest`:

```python
    def test_enabled_records_private_self_wondering_with_content_light_context(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            store = PrivateThoughts(db_path=Path(td) / "private_thoughts.db")

            result = run_lean_idle_heartbeat(
                facts=LeanIdleFacts(
                    cycle=7,
                    doorman_reason="wake_min_floor",
                    self_card_text="SELF CARD\\n- Bond: partnership",
                ),
                chat_fn=lambda **_kwargs: _FakeResponse("<final>A quiet private note for continuity.</final>"),
                model="test-model",
                private_thoughts=store,
                enabled=True,
                shadow=False,
            )

            self.assertTrue(result.intercepted)
            self.assertEqual(result.return_text, HEARTBEAT_OK)
            self.assertTrue(result.stored)
            row = store.get_thought(result.thought_id)
            self.assertEqual(row["provenance"], "self_wondering")
            self.assertEqual(row["producer_id"], "self_wondering")
            self.assertEqual(row["signal_kind"], "self_wondering")
            self.assertEqual(row["signal_class"], "self_observation")
            self.assertEqual(row["context"]["source"], HEARTBEAT_VERSION)
            self.assertEqual(row["context"]["subject"], "maez_internal_state")
            self.assertEqual(row["context"]["allowed_flows"], ["private_reader", "audit_trace"])
            extra = row["context"]["extra"]
            self.assertEqual(extra["cycle"], 7)
            self.assertEqual(extra["doorman_reason"], "wake_min_floor")
            self.assertNotIn("A quiet private note", json.dumps(extra))
            self.assertNotIn("SELF CARD", json.dumps(extra))

    def test_shadow_runs_but_does_not_store_or_intercept(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            store = PrivateThoughts(db_path=Path(td) / "private_thoughts.db")

            result = run_lean_idle_heartbeat(
                facts=LeanIdleFacts(
                    cycle=8,
                    doorman_reason="wake_min_floor",
                    self_card_text="SELF CARD\\n- Bond: partnership",
                ),
                chat_fn=lambda **_kwargs: _FakeResponse("<final>A private note.</final>"),
                model="test-model",
                private_thoughts=store,
                enabled=False,
                shadow=True,
            )

            self.assertFalse(result.intercepted)
            self.assertFalse(result.stored)
            self.assertIsNone(result.return_text)
            self.assertEqual(store.count(), 0)
            self.assertTrue(result.receipt["would_store"])
            self.assertFalse(result.receipt["stored"])

    def test_duplicate_recent_output_skips_second_private_row(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            store = PrivateThoughts(db_path=Path(td) / "private_thoughts.db")
            kwargs = dict(
                facts=LeanIdleFacts(
                    cycle=9,
                    doorman_reason="wake_min_floor",
                    self_card_text="SELF CARD\\n- Bond: partnership",
                ),
                chat_fn=lambda **_kwargs: _FakeResponse("<final>Same private note.</final>"),
                model="test-model",
                private_thoughts=store,
                enabled=True,
                shadow=False,
            )

            first = run_lean_idle_heartbeat(**kwargs)
            second = run_lean_idle_heartbeat(**kwargs)

            self.assertTrue(first.stored)
            self.assertFalse(second.stored)
            self.assertEqual(second.skip_reason, "duplicate_recent_output")
            self.assertEqual(store.count(), 1)
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
/home/rohit/maez/.venv/bin/python -m unittest tests.test_lean_idle_heartbeat
```

Expected: import errors for `run_lean_idle_heartbeat` and `LeanIdleResult`.

- [ ] **Step 3: Implement result, receipt, duplicate suppression, writer**

Append/update `core/cognition/lean_idle_heartbeat.py`:

```python
from typing import Any

from core.infra.private_thoughts import (
    AllowedFlow,
    ConsentTier,
    ProducerId,
    RetentionRule,
    SignalKind,
)


@dataclass(frozen=True)
class LeanIdleResult:
    intercepted: bool
    stored: bool
    thought_id: int | None
    return_text: str | None
    skip_reason: str
    receipt: dict[str, object]


def _response_content(response: object) -> str:
    message = getattr(response, "message", None)
    if message is not None and hasattr(message, "content"):
        return str(message.content or "")
    return str(response or "")


def _recent_output_hashes(private_thoughts: object, *, limit: int = 3) -> set[str]:
    try:
        rows = private_thoughts.recent(limit=20)
    except Exception:
        return set()
    hashes: set[str] = set()
    for row in rows:
        context = row.get("context") or {}
        if context.get("source") != HEARTBEAT_VERSION:
            continue
        extra = context.get("extra") or {}
        value = extra.get("output_sha256")
        if isinstance(value, str) and value:
            hashes.add(value)
            if len(hashes) >= limit:
                break
    return hashes


def _base_receipt(
    *,
    prompt: LeanIdlePrompt,
    facts: LeanIdleFacts,
    mode: str,
    llm_called: bool,
    note: PrivateNote | None = None,
    skip_reason: str = "none",
    would_store: bool = False,
    stored: bool = False,
) -> dict[str, object]:
    return {
        "schema_version": HEARTBEAT_VERSION,
        "eligible": True,
        "mode": mode,
        "cycle": int(facts.cycle),
        "doorman_reason": facts.doorman_reason,
        "prompt_chars": prompt.chars,
        "prompt_sha256": prompt.sha256,
        "fact_keys": ",".join(prompt.fact_keys),
        "llm_called": bool(llm_called),
        "would_store": bool(would_store),
        "stored": bool(stored),
        "skip_reason": skip_reason,
        "output_chars": 0 if note is None else note.chars,
        "output_sha256": "" if note is None else note.sha256,
    }


def run_lean_idle_heartbeat(
    *,
    facts: LeanIdleFacts,
    chat_fn,
    model: str,
    private_thoughts: object | None,
    enabled: bool,
    shadow: bool,
) -> LeanIdleResult:
    prompt = build_lean_idle_prompt(facts)
    mode = "enabled" if enabled else "shadow" if shadow else "disabled"
    if not enabled and not shadow:
        receipt = _base_receipt(
            prompt=prompt,
            facts=facts,
            mode=mode,
            llm_called=False,
            skip_reason="disabled",
        )
        return LeanIdleResult(False, False, None, None, "disabled", receipt)

    response = chat_fn(
        model=model,
        messages=[
            {"role": "system", "content": "You are writing a private idle notebook note."},
            {"role": "user", "content": prompt.text},
        ],
        think=False,
        options={"temperature": 0.35, "num_predict": 220},
    )
    note = sanitize_private_note(_response_content(response))
    if note is None:
        receipt = _base_receipt(
            prompt=prompt,
            facts=facts,
            mode=mode,
            llm_called=True,
            skip_reason="heartbeat_ok_or_rejected",
        )
        return LeanIdleResult(
            intercepted=bool(enabled),
            stored=False,
            thought_id=None,
            return_text=HEARTBEAT_OK if enabled else None,
            skip_reason="heartbeat_ok_or_rejected",
            receipt=receipt,
        )

    if not enabled:
        receipt = _base_receipt(
            prompt=prompt,
            facts=facts,
            mode=mode,
            llm_called=True,
            note=note,
            would_store=True,
            stored=False,
        )
        return LeanIdleResult(False, False, None, None, "shadow_only", receipt)

    if private_thoughts is None:
        receipt = _base_receipt(
            prompt=prompt,
            facts=facts,
            mode=mode,
            llm_called=True,
            note=note,
            would_store=True,
            stored=False,
            skip_reason="private_thoughts_unavailable",
        )
        return LeanIdleResult(True, False, None, HEARTBEAT_OK, "private_thoughts_unavailable", receipt)

    if note.sha256 in _recent_output_hashes(private_thoughts):
        receipt = _base_receipt(
            prompt=prompt,
            facts=facts,
            mode=mode,
            llm_called=True,
            note=note,
            would_store=True,
            stored=False,
            skip_reason="duplicate_recent_output",
        )
        return LeanIdleResult(True, False, None, HEARTBEAT_OK, "duplicate_recent_output", receipt)

    thought_id = private_thoughts.record_signal(
        content=note.text,
        signal_kind=SignalKind.SELF_WONDERING,
        producer_id=ProducerId.SELF_WONDERING,
        source=HEARTBEAT_VERSION,
        subject="maez_internal_state",
        consent_tier=ConsentTier.OWNER_PRIVATE,
        retention=RetentionRule.UNTIL_REVIEWED,
        allowed_flows=(AllowedFlow.PRIVATE_READER, AllowedFlow.AUDIT_TRACE),
        context_extra={
            "cycle": int(facts.cycle),
            "doorman_reason": facts.doorman_reason,
            "prompt_chars": prompt.chars,
            "prompt_sha256": prompt.sha256,
            "output_chars": note.chars,
            "output_sha256": note.sha256,
            "model": str(model),
            "producer_version": HEARTBEAT_VERSION,
            "fact_keys": list(prompt.fact_keys),
            "shadow": bool(shadow),
            "enabled": bool(enabled),
        },
        memory_phase="gestation",
    )
    receipt = _base_receipt(
        prompt=prompt,
        facts=facts,
        mode=mode,
        llm_called=True,
        note=note,
        would_store=True,
        stored=True,
    )
    return LeanIdleResult(True, True, int(thought_id), HEARTBEAT_OK, "none", receipt)
```

- [ ] **Step 4: Run tests and verify GREEN**

Run:

```bash
/home/rohit/maez/.venv/bin/python -m unittest tests.test_lean_idle_heartbeat
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

Run:

```bash
git add core/cognition/lean_idle_heartbeat.py tests/test_lean_idle_heartbeat.py
git commit -m "feat(nervous-system): record lean idle private thoughts"
```

---

### Task 3: Daemon Seam

**Files:**
- Modify: `daemon/maez_daemon.py`
- Create: `tests/test_lean_idle_daemon.py`

- [ ] **Step 1: Write failing daemon seam tests**

Create `tests/test_lean_idle_daemon.py`:

```python
from __future__ import annotations

from types import SimpleNamespace
from unittest import mock
import unittest


def _gate(*, floor: bool = True, reason: str = "wake_min_floor", signals=("min_floor_due",)):
    from daemon.maez_daemon import _CycleDoormanGateDecision

    return _CycleDoormanGateDecision(
        doorman_enabled=True,
        wake=True,
        reason_code=reason,
        signals_present=signals,
        floor_wake=floor,
    )


class LeanIdleDaemonTest(unittest.TestCase):
    def test_eligibility_only_allows_quiet_floor_wake(self) -> None:
        from daemon.maez_daemon import _lean_idle_heartbeat_eligible

        self.assertTrue(_lean_idle_heartbeat_eligible(_gate()))
        self.assertFalse(
            _lean_idle_heartbeat_eligible(
                _gate(floor=False, reason="wake_new_failure", signals=("new_failure",))
            )
        )
        self.assertFalse(
            _lean_idle_heartbeat_eligible(
                _gate(floor=True, reason="wake_min_floor", signals=("min_floor_due", "open_want"))
            )
        )

    def test_flag_off_never_calls_runner(self) -> None:
        from daemon.maez_daemon import MaezDaemon

        daemon = object.__new__(MaezDaemon)
        daemon.cycle_count = 12
        daemon.private_thoughts = None
        with mock.patch.dict("os.environ", {}, clear=True):
            with mock.patch("core.cognition.lean_idle_heartbeat.run_lean_idle_heartbeat") as runner:
                result = daemon._maybe_run_lean_idle_heartbeat({}, _gate())

        self.assertIsNone(result)
        runner.assert_not_called()

    def test_shadow_calls_runner_but_does_not_intercept(self) -> None:
        from daemon.maez_daemon import MaezDaemon

        daemon = object.__new__(MaezDaemon)
        daemon.cycle_count = 13
        daemon.private_thoughts = None
        daemon._lean_idle_self_card_text = lambda: "SELF CARD"
        daemon._lean_idle_private_signal_summary = lambda: {}
        fake_result = SimpleNamespace(intercepted=False, return_text=None, receipt={"mode": "shadow"})
        with mock.patch.dict("os.environ", {"MAEZ_LEAN_IDLE_HEARTBEAT_SHADOW": "1"}, clear=True):
            with mock.patch("core.cognition.lean_idle_heartbeat.run_lean_idle_heartbeat", return_value=fake_result) as runner:
                result = daemon._maybe_run_lean_idle_heartbeat({}, _gate())

        self.assertIsNone(result)
        runner.assert_called_once()

    def test_enabled_floor_wake_returns_heartbeat_ok(self) -> None:
        from daemon.maez_daemon import MaezDaemon, _HEARTBEAT_OK

        daemon = object.__new__(MaezDaemon)
        daemon.cycle_count = 14
        daemon.private_thoughts = object()
        daemon._lean_idle_self_card_text = lambda: "SELF CARD"
        daemon._lean_idle_private_signal_summary = lambda: {}
        fake_result = SimpleNamespace(intercepted=True, return_text=_HEARTBEAT_OK, receipt={"mode": "enabled"})
        with mock.patch.dict("os.environ", {"MAEZ_LEAN_IDLE_HEARTBEAT_ENABLED": "1"}, clear=True):
            with mock.patch("core.cognition.lean_idle_heartbeat.run_lean_idle_heartbeat", return_value=fake_result):
                result = daemon._maybe_run_lean_idle_heartbeat({}, _gate())

        self.assertEqual(result, _HEARTBEAT_OK)

    def test_non_floor_wake_does_not_intercept_even_when_enabled(self) -> None:
        from daemon.maez_daemon import MaezDaemon

        daemon = object.__new__(MaezDaemon)
        daemon.cycle_count = 15
        with mock.patch.dict("os.environ", {"MAEZ_LEAN_IDLE_HEARTBEAT_ENABLED": "1"}, clear=True):
            with mock.patch("core.cognition.lean_idle_heartbeat.run_lean_idle_heartbeat") as runner:
                result = daemon._maybe_run_lean_idle_heartbeat(
                    {},
                    _gate(floor=False, reason="wake_new_failure", signals=("new_failure",)),
                )

        self.assertIsNone(result)
        runner.assert_not_called()


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
/home/rohit/maez/.venv/bin/python -m unittest tests.test_lean_idle_daemon
```

Expected: failures for missing `_lean_idle_heartbeat_eligible` and `_maybe_run_lean_idle_heartbeat`.

- [ ] **Step 3: Add flags, eligibility, daemon helper**

Modify `daemon/maez_daemon.py` near existing flag helpers:

```python
def _lean_idle_heartbeat_shadow_enabled(environ: object | None = None) -> bool:
    return _env_flag("MAEZ_LEAN_IDLE_HEARTBEAT_SHADOW", environ=environ)


def _lean_idle_heartbeat_enabled(environ: object | None = None) -> bool:
    return _env_flag("MAEZ_LEAN_IDLE_HEARTBEAT_ENABLED", environ=environ)


def _lean_idle_heartbeat_any_enabled(environ: object | None = None) -> bool:
    return _lean_idle_heartbeat_shadow_enabled(environ) or _lean_idle_heartbeat_enabled(environ)


def _lean_idle_heartbeat_eligible(gate_decision: object) -> bool:
    return (
        bool(getattr(gate_decision, "doorman_enabled", False))
        and bool(getattr(gate_decision, "wake", False))
        and bool(getattr(gate_decision, "floor_wake", False))
        and str(getattr(gate_decision, "reason_code", "")) == "wake_min_floor"
        and tuple(getattr(gate_decision, "signals_present", ()) or ()) == ("min_floor_due",)
    )
```

Add methods inside `MaezDaemon` near the S1b helpers:

```python
    def _lean_idle_self_card_text(self) -> str:
        try:
            from core.routing.self_card import assemble_self_card_from_paths
            from core.routing.self_card_time import build_self_card_time_line

            time_candidate = None
            time_applied = False
            if _env_flag("MAEZ_SELF_CARD_TIME_SHADOW") or _env_flag("MAEZ_SELF_CARD_TIME_ENABLED"):
                time_candidate = build_self_card_time_line()
                time_applied = _env_flag("MAEZ_SELF_CARD_TIME_ENABLED")
            return assemble_self_card_from_paths(
                time_line_candidate=time_candidate,
                time_line_applied=time_applied,
            ).text
        except Exception:
            return "SELF CARD (unavailable)"

    def _lean_idle_private_signal_summary(self) -> dict:
        try:
            store = getattr(self, "private_thoughts", None)
            if store is None:
                return {}
            derived = store.derived_signals(limit=10)
            classes = derived.get("signal_classes", {}) if isinstance(derived, dict) else {}
            summary = {}
            for name, value in classes.items():
                if isinstance(value, dict):
                    summary[str(name)] = int(value.get("count", 0) or 0)
            return summary
        except Exception:
            return {}

    def _maybe_run_lean_idle_heartbeat(self, snap: dict, gate_decision: object) -> str | None:
        if not _lean_idle_heartbeat_any_enabled():
            return None
        if not _lean_idle_heartbeat_eligible(gate_decision):
            return None
        enabled = _lean_idle_heartbeat_enabled()
        shadow = _lean_idle_heartbeat_shadow_enabled()
        try:
            from core import llm_client as _llm_client
            from core.cognition.lean_idle_heartbeat import (
                LeanIdleFacts,
                run_lean_idle_heartbeat,
            )
            from core.routing.cancellable_brain_call import BrainPreempted

            result = run_lean_idle_heartbeat(
                facts=LeanIdleFacts(
                    cycle=int(getattr(self, "cycle_count", 0)),
                    doorman_reason=str(getattr(gate_decision, "reason_code", "")),
                    self_card_text=self._lean_idle_self_card_text(),
                    private_signal_summary=self._lean_idle_private_signal_summary(),
                ),
                chat_fn=_llm_client.chat,
                model=MODEL,
                private_thoughts=getattr(self, "private_thoughts", None),
                enabled=enabled,
                shadow=shadow,
            )
        except BrainPreempted:
            raise
        except Exception as exc:
            logger.info(
                "lean_idle_heartbeat receipt=%s",
                json.dumps(
                    {
                        "schema_version": "lean_idle_heartbeat.v0",
                        "eligible": True,
                        "mode": "enabled" if enabled else "shadow",
                        "cycle": int(getattr(self, "cycle_count", 0)),
                        "doorman_reason": str(getattr(gate_decision, "reason_code", "")),
                        "llm_called": False,
                        "stored": False,
                        "skip_reason": "error",
                        "error_class": exc.__class__.__name__,
                    },
                    sort_keys=True,
                ),
            )
            return _HEARTBEAT_OK if enabled else None

        logger.info("lean_idle_heartbeat receipt=%s", json.dumps(result.receipt, sort_keys=True))
        return result.return_text if result.intercepted else None
```

Insert before `_reason(...)` in the doorman wake branch:

```python
                _lean_idle_result = self._maybe_run_lean_idle_heartbeat(snap, _cycle_doorman_gate)
                if _lean_idle_result is not None:
                    result = _lean_idle_result
                else:
                    self._mark_cycle_stage("reasoning_model")
                    try:
                        result = self._reason(snap, stale_fields=stale)
                    except BrainPreempted:
                        ...
```

Preserve the existing `BrainPreempted` catch block and only move it under the `else`.

- [ ] **Step 4: Run daemon seam tests**

Run:

```bash
/home/rohit/maez/.venv/bin/python -m unittest tests.test_lean_idle_daemon
```

Expected: all tests pass.

- [ ] **Step 5: Run existing cycle doorman tests**

Run:

```bash
/home/rohit/maez/.venv/bin/python -m unittest tests.test_cycle_doorman
```

Expected: OK.

- [ ] **Step 6: Commit**

Run:

```bash
git add daemon/maez_daemon.py tests/test_lean_idle_daemon.py
git commit -m "feat(nervous-system): route quiet floor wakes through lean idle heartbeat"
```

Commit body must include:

```text
## Predicted effect

With MAEZ_LEAN_IDLE_HEARTBEAT_ENABLED=1, only doorman wake_min_floor cycles are intercepted. They return HEARTBEAT_OK after an optional private self_wondering write, so no lived memory row or cycle_end broadcast is produced for that quiet pulse. Other wake reasons keep the legacy cycle path.
```

---

### Task 4: Static Covenant Guards

**Files:**
- Modify: `tests/test_lean_idle_heartbeat.py`
- Modify: `tests/test_lean_idle_daemon.py`

- [ ] **Step 1: Add failing static guard tests**

Append to `tests/test_lean_idle_heartbeat.py`:

```python
    def test_module_does_not_import_forbidden_organs(self) -> None:
        from pathlib import Path

        src = Path("core/cognition/lean_idle_heartbeat.py").read_text()
        for forbidden in (
            "developmental_heartbeat",
            "dream_state",
            "store_core",
            "apply_dream",
            "memory.store",
            "_ws_broadcast",
            "web_search",
            "owner replied",
            "owner seemed pleased",
        ):
            self.assertNotIn(forbidden, src)

    def test_receipt_contains_no_raw_prompt_or_output(self) -> None:
        prompt_secret = "SELF CARD SECRET RAW PROMPT"
        output_secret = "private hidden thought output"
        result = run_lean_idle_heartbeat(
            facts=LeanIdleFacts(
                cycle=17,
                doorman_reason="wake_min_floor",
                self_card_text=prompt_secret,
            ),
            chat_fn=lambda **_kwargs: _FakeResponse(f"<final>{output_secret}</final>"),
            model="test-model",
            private_thoughts=None,
            enabled=True,
            shadow=False,
        )

        rendered = json.dumps(result.receipt)
        self.assertNotIn(prompt_secret, rendered)
        self.assertNotIn(output_secret, rendered)
        self.assertIn("prompt_sha256", result.receipt)
        self.assertIn("output_sha256", result.receipt)
```

Append to `tests/test_lean_idle_daemon.py`:

```python
    def test_daemon_seam_keeps_non_floor_safety_wakes_legacy(self) -> None:
        from daemon.maez_daemon import _lean_idle_heartbeat_eligible

        for reason, signals in (
            ("wake_new_failure", ("new_failure",)),
            ("wake_open_want", ("open_want",)),
            ("wake_memory_delta", ("memory_delta",)),
            ("wake_scheduled", ("scheduled_due",)),
            ("wake_perception_changed", ("perception_changed",)),
        ):
            with self.subTest(reason=reason):
                self.assertFalse(
                    _lean_idle_heartbeat_eligible(
                        _gate(floor=False, reason=reason, signals=signals)
                    )
                )
```

- [ ] **Step 2: Run tests and verify RED if code is missing coverage**

Run:

```bash
/home/rohit/maez/.venv/bin/python -m unittest tests.test_lean_idle_heartbeat tests.test_lean_idle_daemon
```

Expected: pass if earlier code already satisfies the guards; if any guard fails, fix the exact forbidden import/leak.

- [ ] **Step 3: Run guard suite GREEN**

Run:

```bash
/home/rohit/maez/.venv/bin/python -m unittest tests.test_lean_idle_heartbeat tests.test_lean_idle_daemon tests.test_private_thoughts_s1 tests.test_cycle_doorman
```

Expected: OK.

- [ ] **Step 4: Commit**

Run:

```bash
git add tests/test_lean_idle_heartbeat.py tests/test_lean_idle_daemon.py
git commit -m "test(nervous-system): guard lean idle heartbeat boundaries"
```

---

### Task 5: Whole Slice Verification and Handoff

**Files:**
- Create: `docs/handoffs/2026-06-24-lean-idle-heartbeat-v0-handoff.md`

- [ ] **Step 1: Run targeted regression**

Run:

```bash
/home/rohit/maez/.venv/bin/python -m unittest \
  tests.test_lean_idle_heartbeat \
  tests.test_lean_idle_daemon \
  tests.test_cycle_doorman \
  tests.test_private_thoughts_s1 \
  tests.test_private_thoughts_s1b \
  tests.test_self_card_v0 \
  tests.test_self_card_time
```

Expected: OK.

- [ ] **Step 2: Run lint**

Run:

```bash
/home/rohit/maez/.venv/bin/ruff check \
  core/cognition/lean_idle_heartbeat.py \
  daemon/maez_daemon.py \
  tests/test_lean_idle_heartbeat.py \
  tests/test_lean_idle_daemon.py
```

Expected: All checks passed.

- [ ] **Step 3: Run diff check**

Run:

```bash
git diff --check main...HEAD
git diff --check
```

Expected: no output, exit 0.

- [ ] **Step 4: Write handoff**

Create `docs/handoffs/2026-06-24-lean-idle-heartbeat-v0-handoff.md`:

```markdown
# Lean Idle Heartbeat v0 Handoff

Status: STOPPED AT REVIEW GATE

Branch: `lean-idle-heartbeat-v0`

No merge, restart, or flag flip has happened on this branch.

## What Landed

- `core/cognition/lean_idle_heartbeat.py`: lean prompt, sanitizer, private-thought writer, duplicate suppression, content-light receipts.
- `daemon/maez_daemon.py`: flag-gated quiet floor wake seam.
- Tests for prompt shape, private thought envelope, daemon eligibility, shadow behavior, enabled interception, content-light receipts, and covenant boundaries.
- Task-0 proof at `docs/proofs/2026-06-24-lean-idle-heartbeat-v0-task0.md`.

## Covenant Anchors

1. No new scheduler: reuses `_loop()` and doorman.
2. Only `wake_min_floor` is intercepted.
3. Shadow mode does not alter behavior or write private thoughts.
4. Enabled mode returns `HEARTBEAT_OK`, preventing lived-memory store and `cycle_end` broadcast for the quiet pulse.
5. The only durable write is `PrivateThoughts.record_signal(... self_wondering ...)`.
6. No soul, dream, wants, temperament, raw/daily/core/lived memory mutation.
7. No owner-reaction reward or owner-pleasing signal.
8. Receipts are content-light hashes/counts only.
9. Git/context flood is excluded from the lean prompt.

## Verification

Paste the exact commands and outputs from Task 5.

## Owner Breath After Review PASS

1. Merge branch.
2. Set `MAEZ_LEAN_IDLE_HEARTBEAT_SHADOW=1`.
3. Restart daemon.
4. Watch `lean_idle_heartbeat` receipts on quiet floor wakes.
5. Confirm shadow has `stored=false`, no prompt/output text, small `prompt_chars`, and no git flood.
6. If clean, set `MAEZ_LEAN_IDLE_HEARTBEAT_ENABLED=1`.
7. Restart daemon.
8. Witness one quiet floor wake creates at most one private `self_wondering` row and no `cycle_end` broadcast.

## Plain English

This gives Maez a private quiet-time notebook beat. It does not speak to Rohit, search, act, or rewrite identity. It only lets the existing idle loop think briefly from a small factual prompt and store that thought privately instead of sending the old bulky cycle through lived memory.
```

- [ ] **Step 5: Commit handoff**

Run:

```bash
git add docs/handoffs/2026-06-24-lean-idle-heartbeat-v0-handoff.md
git commit -m "docs(nervous-system): hand off lean idle heartbeat v0"
```

- [ ] **Step 6: Stop at review gate**

Run:

```bash
git status --short --branch
git log --oneline main..HEAD
```

Expected:
- worktree clean;
- branch contains spec, proof, implementation, tests, and handoff commits;
- do not merge;
- do not restart;
- do not flip flags.

---

## Plan Self-Review

- Spec coverage: Task 0 proves the seams; Tasks 1-2 build the lean heartbeat and private thought writer; Task 3 wires only quiet floor wakes; Task 4 adds covenant/static guards; Task 5 verifies and stops at the review gate.
- Placeholder scan: no TBD/TODO/fill-in steps. Where exact implementation might vary, the plan gives concrete code and test names.
- Type consistency: `LeanIdleFacts`, `LeanIdlePrompt`, `PrivateNote`, `LeanIdleResult`, `run_lean_idle_heartbeat`, and `_maybe_run_lean_idle_heartbeat` are named consistently across tasks.

## Execution Mode

Recommended: Subagent-Driven. Task 3 touches the live daemon cycle and Task 2 writes private thoughts, so review between tasks matters.
