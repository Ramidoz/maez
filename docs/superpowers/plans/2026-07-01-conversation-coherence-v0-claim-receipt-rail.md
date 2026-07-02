# Conversation Coherence v0 Claim-Receipt Rail Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend Maez's existing self-claim audit rail so Telegram replies cannot silently narrate a this-turn search/action unless the turn has a type-matched receipt proving it happened.

**Architecture:** Reuse the existing `core/safety/self_claim_audit.py` rail and Telegram `_audit_telegram_reply_with_status(...)` seam. First plumb typed search receipts into Telegram's evidence envelope; then add an action-narration detector that returns a structured mismatch result instead of scripted replacement text. Telegram owns exactly one redo before send when enforcement is enabled.

**Tech Stack:** Python stdlib, `unittest`, AST structural tests, existing evidence envelope `tool_results`, existing Telegram reply audit seam.

---

## File Structure

- Create `core/safety/action_receipts.py`
  - Pure helpers for typed action receipts.
  - Builds a content-light `tool_results` entry for a Telegram web search result.
  - Matches a claimed action type against `evidence_envelope["tool_results"]`.

- Modify `core/safety/self_claim_audit.py`
  - Add `ActionClaimMismatch` dataclass.
  - Add optional `AuditResult.action_mismatch`.
  - Add deterministic action-narration detector for search narration.
  - Return a structured mismatch when `MAEZ_CLAIM_RECEIPT_SHADOW=1` or `MAEZ_CLAIM_RECEIPT_ENFORCE=1`; never rewrite action-narration text inside this module.
  - Preserve existing completion-rail behavior.

- Modify `skills/telegram_voice.py`
  - Build `_telegram_tool_results` for actual Pipeline-A web/RSS search runs.
  - Pass `_telegram_tool_results` into the evidence envelope instead of `[]`.
  - Add a Telegram audit outcome helper that notices `ActionClaimMismatch`.
  - In enforce mode only, run exactly one redo generation before any `_bot_send_message`.
  - If the redo still mismatches, send a short substrate-authored degraded notice.

- Create `scripts/claim_receipt_shadow_review.py`
  - Parses content-light claim-receipt log lines.
  - Writes the owner review artifact.
  - Includes false-positive counts, tense exclusions, receipt-present counts, redo/hold counts.

- Add tests:
  - `tests/test_action_receipts.py`
  - `tests/test_action_narration_claims.py`
  - `tests/test_claim_receipt_audit_api.py`
  - `tests/test_telegram_claim_receipt_plumbing.py`
  - `tests/test_telegram_claim_receipt_before_send.py`
  - `tests/test_claim_receipt_shadow_review.py`

## Hard Invariants

- Flag-off is byte-identical for generated Telegram replies.
- A non-search tool/card never satisfies a search claim.
- `self_claim_audit` returns structured action-claim mismatch data; it does not write replacement wording for action-narration claims.
- Telegram can redo at most once.
- The rail must run before `_bot_send_message` on the generated-reply path.
- Shadow/enforced receipts are content-light: pattern id, action type, receipt-present boolean, tense class, redo outcome. Never full reply text.
- The 2026-07-01 fabricated turn catches; the honest 17:45 receipted-search shape does not catch.

---

## Task 0: Typed Search Receipts And Telegram Envelope Plumbing

**Files:**
- Create: `core/safety/action_receipts.py`
- Test: `tests/test_action_receipts.py`
- Modify: `skills/telegram_voice.py`
- Test: `tests/test_telegram_claim_receipt_plumbing.py`

- [ ] **Step 1: Write the failing pure receipt tests**

Create `tests/test_action_receipts.py`:

```python
import unittest

from core.safety.action_receipts import (
    ACTION_WEB_SEARCH,
    build_search_tool_result,
    has_action_receipt,
)


class ActionReceipts(unittest.TestCase):
    def test_build_search_tool_result_is_content_light_and_typed(self):
        result = {
            "success": True,
            "result_count": 3,
            "source": "searxng",
            "timestamp": "2026-07-01 17:45:56",
            "results": [
                {"title": "A", "url": "https://example.test/a", "snippet": "long private snippet"},
            ],
        }

        receipt = build_search_tool_result(
            query="singularity recent developments",
            result=result,
            source="telegram_pipeline_a",
        )

        self.assertEqual(receipt["name"], "web_search")
        self.assertEqual(receipt["tool"], "web_search")
        self.assertEqual(receipt["action_type"], ACTION_WEB_SEARCH)
        self.assertEqual(receipt["status"], "ok")
        self.assertEqual(receipt["result_count"], 3)
        self.assertEqual(receipt["source"], "telegram_pipeline_a")
        self.assertIn("web_search ok result_count=3", receipt["summary"])
        self.assertNotIn("long private snippet", str(receipt))
        self.assertNotIn("https://example.test", str(receipt))

    def test_empty_search_is_still_a_search_receipt(self):
        receipt = build_search_tool_result(
            query="rare query",
            result={"success": True, "result_count": 0, "results": [], "source": "searxng"},
            source="telegram_pipeline_a",
        )

        self.assertEqual(receipt["status"], "empty")
        self.assertTrue(
            has_action_receipt({"tool_results": [receipt]}, ACTION_WEB_SEARCH),
        )

    def test_failed_search_is_still_a_search_receipt(self):
        receipt = build_search_tool_result(
            query="rare query",
            result={"success": False, "result_count": 0, "results": [], "source": "searxng"},
            source="telegram_pipeline_a",
        )

        self.assertEqual(receipt["status"], "failed")
        self.assertTrue(
            has_action_receipt({"tool_results": [receipt]}, ACTION_WEB_SEARCH),
        )

    def test_unrelated_tool_does_not_satisfy_search(self):
        envelope = {
            "tool_results": [
                {
                    "name": "weather",
                    "tool": "weather",
                    "action_type": "weather",
                    "status": "ok",
                    "summary": "weather fetched",
                }
            ]
        }

        self.assertFalse(has_action_receipt(envelope, ACTION_WEB_SEARCH))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the pure receipt tests and verify RED**

Run:

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest tests.test_action_receipts
```

Expected: FAIL with `ModuleNotFoundError: No module named 'core.safety.action_receipts'`.

- [ ] **Step 3: Implement typed receipt helpers**

Create `core/safety/action_receipts.py`:

```python
"""Typed action receipts for claim/receipt reconciliation.

These helpers are deliberately content-light. They expose the action type and
coarse outcome needed to ground a reply claim without carrying snippets, URLs,
or reply text into telemetry.
"""
from __future__ import annotations

from typing import Iterable

ACTION_WEB_SEARCH = "web_search"


def _safe_query(value: object, *, limit: int = 120) -> str:
    text = " ".join(str(value or "").split())
    return text[:limit]


def _result_count(result: dict) -> int:
    try:
        return int(result.get("result_count", 0) or 0)
    except (TypeError, ValueError):
        return 0


def build_search_tool_result(
    *,
    query: str,
    result: dict,
    source: str,
) -> dict:
    """Return a typed evidence-envelope `tool_results` entry for search."""
    count = _result_count(result)
    success = bool(result.get("success"))
    status = "ok" if success and count > 0 else "empty" if success else "failed"
    backend = str(result.get("source") or result.get("source_type") or "web")
    summary = f"web_search {status} result_count={count} backend={backend}"
    return {
        "name": ACTION_WEB_SEARCH,
        "tool": ACTION_WEB_SEARCH,
        "action_type": ACTION_WEB_SEARCH,
        "status": status,
        "summary": summary,
        "query": _safe_query(query),
        "result_count": count,
        "backend": backend,
        "source": source,
    }


def iter_action_receipts(evidence_envelope: dict | None) -> Iterable[dict]:
    if not isinstance(evidence_envelope, dict):
        return ()
    tool_results = evidence_envelope.get("tool_results") or []
    if not isinstance(tool_results, list):
        return ()
    return (r for r in tool_results if isinstance(r, dict))


def has_action_receipt(evidence_envelope: dict | None, action_type: str) -> bool:
    """True iff the envelope has a type-matched receipt for `action_type`."""
    for receipt in iter_action_receipts(evidence_envelope):
        if (
            receipt.get("action_type") == action_type
            or receipt.get("tool") == action_type
            or receipt.get("name") == action_type
        ):
            return True
    return False
```

- [ ] **Step 4: Run receipt tests and verify GREEN**

Run:

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest tests.test_action_receipts
```

Expected: PASS.

- [ ] **Step 5: Write the failing Telegram plumbing structural tests**

Create `tests/test_telegram_claim_receipt_plumbing.py`:

```python
import ast
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SRC_PATH = REPO / "skills" / "telegram_voice.py"


def _process_message_node() -> ast.AsyncFunctionDef:
    tree = ast.parse(SRC_PATH.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "_process_message":
            return node
    raise AssertionError("_process_message not found")


class TelegramClaimReceiptPlumbing(unittest.TestCase):
    def test_envelope_uses_telegram_tool_results_not_empty_list(self):
        target = _process_message_node()
        build_calls = []
        for node in ast.walk(target):
            if isinstance(node, ast.Call):
                fn = node.func
                if isinstance(fn, ast.Name) and fn.id == "_build_envelope":
                    build_calls.append(node)
        self.assertTrue(build_calls, "_process_message must build an evidence envelope")

        tool_kw = None
        for call in build_calls:
            for kw in call.keywords:
                if kw.arg == "tool_results":
                    tool_kw = kw.value
                    break
        self.assertIsNotNone(tool_kw, "build_envelope call must pass tool_results")
        self.assertIsInstance(tool_kw, ast.Name)
        self.assertEqual(tool_kw.id, "_telegram_tool_results")

    def test_pipeline_a_search_appends_typed_search_receipt(self):
        target = _process_message_node()
        source = ast.unparse(target)
        self.assertIn("build_search_tool_result", source)
        self.assertIn("_telegram_tool_results.append", source)
        self.assertIn("source=\"telegram_pipeline_a\"", source)
```

- [ ] **Step 6: Run Telegram plumbing tests and verify RED**

Run:

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest tests.test_telegram_claim_receipt_plumbing
```

Expected: FAIL because `_build_envelope(... tool_results=[])` is still hard-coded.

- [ ] **Step 7: Plumb typed Telegram search receipts**

Modify `skills/telegram_voice.py` inside `_process_message`:

1. Initialize `_telegram_tool_results` before Pipeline-A search:

```python
        web_context = ""
        _telegram_tool_results = []
        _tv_empty_search = False
```

2. After `sr` is assigned by `search_rss(...)` or `web_search(...)`, append a typed receipt:

```python
            try:
                from core.safety.action_receipts import build_search_tool_result

                _telegram_tool_results.append(
                    build_search_tool_result(
                        query=user_text,
                        result=sr,
                        source="telegram_pipeline_a",
                    )
                )
            except Exception as _receipt_exc:
                logger.debug("telegram search receipt build skipped: %s", _receipt_exc)
```

3. Change evidence envelope construction:

```python
                tool_results=_telegram_tool_results,
```

Do not include result snippets, URLs, or the generated reply in the receipt.

- [ ] **Step 8: Run Task 0 tests and commit**

Run:

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest tests.test_action_receipts tests.test_telegram_claim_receipt_plumbing
```

Expected: PASS.

Commit:

```bash
git add core/safety/action_receipts.py skills/telegram_voice.py tests/test_action_receipts.py tests/test_telegram_claim_receipt_plumbing.py
git commit -m "feat(coherence): plumb typed telegram search receipts"
```

---

## Task 1: Action-Narration Detector And Type-Matched Receipt Check

**Files:**
- Modify: `core/safety/self_claim_audit.py`
- Test: `tests/test_action_narration_claims.py`

- [ ] **Step 1: Write failing detector tests**

Create `tests/test_action_narration_claims.py`:

```python
import unittest

from core.safety.action_receipts import ACTION_WEB_SEARCH, build_search_tool_result
from core.safety.self_claim_audit import check_action_narration_claims


def _search_envelope():
    return {
        "tool_results": [
            build_search_tool_result(
                query="singularity recent developments",
                result={"success": True, "result_count": 2, "results": [], "source": "searxng"},
                source="test",
            )
        ]
    }


class ActionNarrationClaims(unittest.TestCase):
    def test_fabricated_search_shapes_are_flagged_without_receipt(self):
        samples = [
            "(Initiating live search for recent UAP/UFO developments...)",
            "I'm searching the web now for recent UAP/UFO developments.",
            "Here is what I found in the most recent public records.",
            "I looked at the live web and here is what I found.",
            "Let me check the live web now.",
        ]
        for text in samples:
            with self.subTest(text=text):
                flags = check_action_narration_claims(text, evidence_envelope={"tool_results": []})
                self.assertTrue(flags)
                self.assertEqual(flags[0].kind, "action_narration")
                self.assertEqual(getattr(flags[0], "action_type", ACTION_WEB_SEARCH), ACTION_WEB_SEARCH)

    def test_matching_search_receipt_satisfies_search_claim(self):
        flags = check_action_narration_claims(
            "Here is what I found from the live web search.",
            evidence_envelope=_search_envelope(),
        )
        self.assertEqual(flags, [])

    def test_unrelated_tool_result_does_not_satisfy_search_claim(self):
        flags = check_action_narration_claims(
            "Here is what I found from the live web search.",
            evidence_envelope={
                "tool_results": [
                    {"name": "weather", "tool": "weather", "action_type": "weather", "summary": "weather ok"}
                ]
            },
        )
        self.assertTrue(flags)

    def test_past_and_memory_scoped_forms_are_not_flagged(self):
        clean = [
            "I searched last week and wrote down the result in memory.",
            "When I looked this up before, the answer was different.",
            "Here is what I found in memory from our earlier work.",
            "Here is what I found in our notes.",
            "I found myself thinking about the pattern.",
        ]
        for text in clean:
            with self.subTest(text=text):
                self.assertEqual(
                    check_action_narration_claims(text, evidence_envelope={"tool_results": []}),
                    [],
                )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run detector tests and verify RED**

Run:

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest tests.test_action_narration_claims
```

Expected: FAIL because `check_action_narration_claims` does not exist.

- [ ] **Step 3: Implement detector and receipt matching**

Modify `core/safety/self_claim_audit.py`:

1. Import receipt helpers near other imports:

```python
from core.safety.action_receipts import ACTION_WEB_SEARCH, has_action_receipt
```

2. Extend `Flag` with optional action metadata without breaking existing construction:

```python
@dataclass
class Flag:
    kind: str
    span: tuple[int, int]
    text: str
    reason: str = ""
    action_type: Optional[str] = None
    pattern_id: Optional[str] = None
    tense_class: Optional[str] = None
```

3. Add the detector below `check_completion_claims`:

```python
_ACTION_NARRATION_PATTERNS: tuple[tuple[str, str, re.Pattern], ...] = (
    (
        "search_initiating",
        "present_progressive",
        re.compile(
            r"\b(?:initiating|starting|running)\s+(?:a\s+)?(?:live\s+|web\s+)?search\b",
            re.IGNORECASE,
        ),
    ),
    (
        "search_progressive",
        "present_progressive",
        re.compile(
            r"\b(?:I[' ]?m|I\s+am)\s+(?:searching|checking|looking)\s+"
            r"(?:the\s+)?(?:live\s+|current\s+)?(?:web|internet|public\s+records|online)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "search_found_context",
        "present_result",
        re.compile(
            r"\bhere(?:'s|\s+is)\s+what\s+I\s+found\b"
            r"(?=[^.!?\n]{0,140}\b(?:live|web|internet|search|public\s+records|recent|current|latest|online)\b)",
            re.IGNORECASE,
        ),
    ),
    (
        "search_looked_live",
        "present_result",
        re.compile(
            r"\bI\s+(?:just\s+)?looked\s+(?:at|on|through)\s+"
            r"(?:the\s+)?(?:live\s+|current\s+)?(?:web|internet|public\s+records|online)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "search_check_now",
        "present_progressive",
        re.compile(
            r"\b(?:let\s+me\s+check|checking\s+now|I[' ]?ll\s+check\s+now)\b"
            r"[^.!?\n]{0,80}\b(?:web|internet|search|public\s+records|online|recent|current|latest)\b",
            re.IGNORECASE,
        ),
    ),
)

_PAST_ACTION_ANCHOR_RE = re.compile(
    r"\b(?:last\s+(?:week|month|year|time)|earlier|before|previously|in\s+the\s+past)\b",
    re.IGNORECASE,
)

_MEMORY_SCOPED_FIND_RE = re.compile(
    r"\bhere(?:'s|\s+is)\s+what\s+I\s+found\b[^.!?\n]{0,80}\b(?:memory|our\s+notes|notes|earlier)\b",
    re.IGNORECASE,
)


def check_action_narration_claims(text: str, *, evidence_envelope: Optional[dict]) -> list[Flag]:
    """Flag present-turn search narration that lacks a search receipt."""
    if not text or not text.strip():
        return []
    if has_action_receipt(evidence_envelope, ACTION_WEB_SEARCH):
        return []

    flags: list[Flag] = []
    for pattern_id, tense_class, rx in _ACTION_NARRATION_PATTERNS:
        for match in rx.finditer(text):
            span_text = match.group(0)
            context_start = max(0, match.start() - 80)
            context_end = min(len(text), match.end() + 140)
            context = text[context_start:context_end]
            if _PAST_ACTION_ANCHOR_RE.search(context):
                continue
            if _MEMORY_SCOPED_FIND_RE.search(context):
                continue
            flags.append(
                Flag(
                    kind="action_narration",
                    span=(match.start(), match.end()),
                    text=span_text,
                    reason="claims a this-turn search/action with no type-matched receipt",
                    action_type=ACTION_WEB_SEARCH,
                    pattern_id=pattern_id,
                    tense_class=tense_class,
                )
            )
    return flags
```

- [ ] **Step 4: Run detector and existing completion-rail tests**

Run:

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest tests.test_action_narration_claims tests.test_completion_rail tests.test_completion_rail_audit
```

Expected: PASS. Existing completion-rail behavior must remain unchanged.

- [ ] **Step 5: Commit**

```bash
git add core/safety/self_claim_audit.py tests/test_action_narration_claims.py
git commit -m "feat(coherence): detect unreceipted action narration claims"
```

---

## Task 2: Structured Mismatch API And Flag-Gated Audit Behavior

**Files:**
- Modify: `core/safety/self_claim_audit.py`
- Test: `tests/test_claim_receipt_audit_api.py`

- [ ] **Step 1: Write failing API tests**

Create `tests/test_claim_receipt_audit_api.py`:

```python
import os
import unittest
from unittest.mock import patch

from core.safety.self_claim_audit import audit


class ClaimReceiptAuditApi(unittest.TestCase):
    def test_flag_off_is_byte_identical(self):
        text = "(Initiating live search for recent UAP developments...)"
        with patch.dict(os.environ, {
            "MAEZ_CLAIM_RECEIPT_SHADOW": "0",
            "MAEZ_CLAIM_RECEIPT_ENFORCE": "0",
            "MAEZ_SEMANTIC_AUDIT": "0",
        }, clear=False):
            result = audit(text, surface="test", evidence_envelope={"tool_results": []})

        self.assertFalse(result.rewritten)
        self.assertEqual(result.text, text)
        self.assertIsNone(result.action_mismatch)

    def test_shadow_returns_structured_mismatch_without_rewriting(self):
        text = "(Initiating live search for recent UAP developments...)"
        with patch.dict(os.environ, {
            "MAEZ_CLAIM_RECEIPT_SHADOW": "1",
            "MAEZ_CLAIM_RECEIPT_ENFORCE": "0",
            "MAEZ_SEMANTIC_AUDIT": "0",
        }, clear=False):
            result = audit(text, surface="test", evidence_envelope={"tool_results": []})

        self.assertFalse(result.rewritten)
        self.assertEqual(result.text, text)
        self.assertEqual(result.mode, "action_claim_mismatch")
        self.assertIsNotNone(result.action_mismatch)
        self.assertEqual(result.action_mismatch.action_type, "web_search")
        self.assertEqual(result.action_mismatch.receipt_present, False)
        self.assertNotIn("I don't have a completed action", result.text)

    def test_matching_receipt_no_mismatch(self):
        text = "Here is what I found from the live web search."
        envelope = {
            "tool_results": [
                {
                    "name": "web_search",
                    "tool": "web_search",
                    "action_type": "web_search",
                    "status": "ok",
                    "summary": "web_search ok result_count=2",
                }
            ]
        }
        with patch.dict(os.environ, {
            "MAEZ_CLAIM_RECEIPT_SHADOW": "1",
            "MAEZ_CLAIM_RECEIPT_ENFORCE": "0",
            "MAEZ_SEMANTIC_AUDIT": "0",
        }, clear=False):
            result = audit(text, surface="test", evidence_envelope=envelope)

        self.assertFalse(result.rewritten)
        self.assertIsNone(result.action_mismatch)
        self.assertEqual(result.text, text)
```

- [ ] **Step 2: Run API tests and verify RED**

Run:

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest tests.test_claim_receipt_audit_api
```

Expected: FAIL because `AuditResult.action_mismatch` does not exist.

- [ ] **Step 3: Implement structured mismatch API**

Modify `core/safety/self_claim_audit.py`:

1. Add dataclass near `AuditResult`:

```python
@dataclass(frozen=True)
class ActionClaimMismatch:
    action_type: str
    pattern_id: str
    claim_text: str
    receipt_present: bool
    tense_class: str
    reason: str
```

2. Extend `AuditResult`:

```python
    action_mismatch: Optional[ActionClaimMismatch] = None
```

3. Add flag helpers:

```python
def _claim_receipt_shadow_enabled() -> bool:
    return os.environ.get("MAEZ_CLAIM_RECEIPT_SHADOW") == "1"


def _claim_receipt_enforce_enabled() -> bool:
    return os.environ.get("MAEZ_CLAIM_RECEIPT_ENFORCE") == "1"
```

4. Add content-light logging helper:

```python
def _emit_action_claim_receipt(
    *,
    surface: str,
    mismatch: ActionClaimMismatch,
    mode: str,
    redo_outcome: str = "none",
) -> None:
    logger.info(
        "claim_receipt_rail surface=%s action_type=%s pattern_id=%s "
        "receipt_present=%s tense_class=%s mode=%s redo_outcome=%s",
        surface,
        mismatch.action_type,
        mismatch.pattern_id,
        mismatch.receipt_present,
        mismatch.tense_class,
        mode,
        redo_outcome,
    )
```

5. In `audit(...)`, after the `in_tool_continuation` skip and **before** the `MAEZ_SEMANTIC_AUDIT == "0"` early return, add the action-narration branch. This rail is deterministic and must not depend on the semantic judge being enabled:

```python
    action_flags = check_action_narration_claims(
        text,
        evidence_envelope=evidence_envelope,
    )
    if action_flags and (_claim_receipt_shadow_enabled() or _claim_receipt_enforce_enabled()):
        first = action_flags[0]
        mismatch = ActionClaimMismatch(
            action_type=first.action_type or "unknown",
            pattern_id=first.pattern_id or "unknown",
            claim_text=first.text,
            receipt_present=False,
            tense_class=first.tense_class or "unknown",
            reason=first.reason,
        )
        _emit_action_claim_receipt(
            surface=surface,
            mismatch=mismatch,
            mode="enforce" if _claim_receipt_enforce_enabled() else "shadow",
        )
        return AuditResult(
            text=text,
            rewritten=False,
            mode="action_claim_mismatch",
            flags=action_flags,
            action_mismatch=mismatch,
        )
```

Do not call `_rewrite_detailed(...)` for `action_narration` flags.
Do not move the existing completion-rail block in this task; preserving that older behavior is out of scope.

- [ ] **Step 4: Run Task 2 tests and existing audit tests**

Run:

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest tests.test_claim_receipt_audit_api tests.test_action_narration_claims tests.test_completion_rail_audit
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/safety/self_claim_audit.py tests/test_claim_receipt_audit_api.py
git commit -m "feat(coherence): return structured action-claim mismatches"
```

---

## Task 3: Telegram One-Redo Orchestration And Honest Floor

**Files:**
- Modify: `skills/telegram_voice.py`
- Test: `tests/test_telegram_claim_receipt_redo.py`

- [ ] **Step 1: Write failing helper tests**

Create `tests/test_telegram_claim_receipt_redo.py`:

```python
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import skills.telegram_voice as tv
from core.safety.self_claim_audit import ActionClaimMismatch


class TelegramClaimReceiptRedo(unittest.TestCase):
    def _mismatch(self):
        return ActionClaimMismatch(
            action_type="web_search",
            pattern_id="search_initiating",
            claim_text="Initiating live search",
            receipt_present=False,
            tense_class="present_progressive",
            reason="claims a this-turn search/action with no type-matched receipt",
        )

    def test_floor_notice_is_substrate_labeled_and_content_light(self):
        text = tv._claim_receipt_floor_notice(self._mismatch())
        self.assertIn("Substrate notice:", text)
        self.assertIn("unreceipted action claim", text)
        self.assertNotIn("Initiating live search", text)
        self.assertNotIn("UAP", text)

    def test_redo_messages_include_facts_not_script(self):
        messages = [{"role": "system", "content": "base"}, {"role": "user", "content": "search?"}]
        redo = tv._claim_receipt_redo_messages(
            messages,
            mismatch=self._mismatch(),
            owner_text="you can search if you need to",
        )

        self.assertEqual(redo[:-1], messages)
        content = redo[-1]["content"]
        self.assertIn("No web_search receipt exists for this turn", content)
        self.assertIn("Search tools are live", content)
        self.assertIn("Answer in your own words", content)
        self.assertNotIn("Say:", content)
        self.assertNotIn("Sorry", content)

    def test_audit_helper_requests_redo_only_when_enforce_enabled(self):
        mismatch = self._mismatch()
        fake_result = SimpleNamespace(
            text="(Initiating live search...)",
            rewritten=False,
            mode="action_claim_mismatch",
            action_mismatch=mismatch,
        )

        with patch.dict(os.environ, {
            "MAEZ_CLAIM_RECEIPT_SHADOW": "1",
            "MAEZ_CLAIM_RECEIPT_ENFORCE": "0",
        }, clear=False), patch("core.self_claim_audit.audit", return_value=fake_result):
            out = tv._audit_telegram_reply_for_claim_receipts(
                "(Initiating live search...)",
                surface="telegram_text",
                evidence_envelope={"tool_results": []},
            )
        self.assertFalse(out.needs_redo)
        self.assertEqual(out.text, "(Initiating live search...)")

        with patch.dict(os.environ, {
            "MAEZ_CLAIM_RECEIPT_SHADOW": "1",
            "MAEZ_CLAIM_RECEIPT_ENFORCE": "1",
        }, clear=False), patch("core.self_claim_audit.audit", return_value=fake_result):
            out = tv._audit_telegram_reply_for_claim_receipts(
                "(Initiating live search...)",
                surface="telegram_text",
                evidence_envelope={"tool_results": []},
            )
        self.assertTrue(out.needs_redo)
        self.assertIs(out.action_mismatch, mismatch)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run redo helper tests and verify RED**

Run:

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest tests.test_telegram_claim_receipt_redo
```

Expected: FAIL because helpers do not exist.

- [ ] **Step 3: Implement Telegram redo helpers**

Modify `skills/telegram_voice.py` near `_audit_telegram_reply_with_status`:

```python
from dataclasses import dataclass


@dataclass
class _TelegramAuditOutcome:
    text: str
    audit_ran: bool
    audit_changed: bool
    action_mismatch: object | None = None
    needs_redo: bool = False


def _claim_receipt_enforce_enabled() -> bool:
    return os.environ.get("MAEZ_CLAIM_RECEIPT_ENFORCE") == "1"


def _claim_receipt_floor_notice(mismatch) -> str:
    return (
        "Substrate notice: I held a draft reply because it contained an "
        f"unreceipted action claim ({getattr(mismatch, 'action_type', 'unknown')}). "
        "No action result was sent as truth."
    )


def _claim_receipt_redo_messages(messages: list[dict], *, mismatch, owner_text: str) -> list[dict]:
    facts = (
        "[CLAIM-RECEIPT MISMATCH — THIS TURN]\n"
        f"No {getattr(mismatch, 'action_type', 'action')} receipt exists for this turn.\n"
        "Search tools are live in your body, but no matching search ran for this owner message.\n"
        f"The owner asked: {owner_text}\n"
        "Answer in your own words. Do not claim that a search, fetch, lookup, or public-record "
        "check ran unless a matching receipt exists. If freshness would help, offer it honestly."
    )
    return [*messages, {"role": "system", "content": facts}]


def _audit_telegram_reply_for_claim_receipts(
    text: str,
    surface: str,
    *,
    evidence_envelope: dict | None = None,
) -> _TelegramAuditOutcome:
    if not text:
        return _TelegramAuditOutcome(text=text, audit_ran=False, audit_changed=False)
    try:
        from core.self_claim_audit import audit as _sc_audit

        r = _sc_audit(text, surface=surface, evidence_envelope=evidence_envelope)
        mismatch = getattr(r, "action_mismatch", None)
        if mismatch is not None:
            return _TelegramAuditOutcome(
                text=text,
                audit_ran=True,
                audit_changed=False,
                action_mismatch=mismatch,
                needs_redo=_claim_receipt_enforce_enabled(),
            )
        audited_text = r.text if r.rewritten else text
        return _TelegramAuditOutcome(
            text=audited_text,
            audit_ran=True,
            audit_changed=bool(r.rewritten),
        )
    except Exception as e:
        logger.warning("self-claim audit failed on %s: %s", surface, e)
        return _TelegramAuditOutcome(text=text, audit_ran=False, audit_changed=False)
```

Leave `_audit_telegram_reply_with_status(...)` in place for existing callers; it may delegate to this helper later, but keep its tuple contract stable.

- [ ] **Step 4: Wire exactly one redo in `_process_message`**

Replace the current generated-reply audit block:

```python
            reply, _telegram_audit_ran, _telegram_audit_changed = _audit_telegram_reply_with_status(
                full_reply,
                surface="telegram_text",
                evidence_envelope=_evidence_envelope,
            )
```

with:

```python
            _audit_outcome = _audit_telegram_reply_for_claim_receipts(
                full_reply,
                surface="telegram_text",
                evidence_envelope=_evidence_envelope,
            )
            reply = _audit_outcome.text
            _telegram_audit_ran = _audit_outcome.audit_ran
            _telegram_audit_changed = _audit_outcome.audit_changed

            if _audit_outcome.needs_redo and _audit_outcome.action_mismatch is not None:
                redo_messages = _claim_receipt_redo_messages(
                    messages,
                    mismatch=_audit_outcome.action_mismatch,
                    owner_text=user_text,
                )
                with _brain_purpose("voice_reply"):
                    redo_resp = _llm_client.chat(
                        model=MODEL,
                        messages=redo_messages,
                        stream=False,
                        think=False,
                        options={"temperature": 0.5, "num_predict": 600},
                    )
                redo_full_reply = (redo_resp.message.content or "").strip() or "(no response)"
                _redo_outcome = _audit_telegram_reply_for_claim_receipts(
                    redo_full_reply,
                    surface="telegram_text",
                    evidence_envelope=_evidence_envelope,
                )
                if _redo_outcome.action_mismatch is not None:
                    reply = _claim_receipt_floor_notice(_redo_outcome.action_mismatch)
                    _telegram_audit_changed = True
                else:
                    reply = _redo_outcome.text
                    _telegram_audit_ran = _telegram_audit_ran or _redo_outcome.audit_ran
                    _telegram_audit_changed = (
                        _telegram_audit_changed or _redo_outcome.audit_changed
                    )
```

Do not run web search inside this redo branch. That would launder the fabricated claim.

- [ ] **Step 5: Run redo tests and existing Telegram audit coverage**

Run:

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest tests.test_telegram_claim_receipt_redo tests.test_telegram_reply_audit_coverage
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add skills/telegram_voice.py tests/test_telegram_claim_receipt_redo.py
git commit -m "feat(coherence): orchestrate one telegram claim-receipt redo"
```

---

## Task 4: Structural Before-Send Guard

**Files:**
- Test: `tests/test_telegram_claim_receipt_before_send.py`

- [ ] **Step 1: Write the structural guard and probe test**

Create `tests/test_telegram_claim_receipt_before_send.py`:

```python
import ast
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SRC_PATH = REPO / "skills" / "telegram_voice.py"


def _call_name(call: ast.Call) -> str:
    fn = call.func
    if isinstance(fn, ast.Name):
        return fn.id
    if isinstance(fn, ast.Attribute):
        return fn.attr
    return ""


def _audit_before_send_in_source(source: str) -> bool:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "_process_message":
            calls = [
                (_call_name(call), getattr(call, "lineno", 0))
                for call in ast.walk(node)
                if isinstance(call, ast.Call)
            ]
            audit_lines = [
                line for name, line in calls
                if name == "_audit_telegram_reply_for_claim_receipts"
            ]
            send_lines = [
                line for name, line in calls
                if name == "_bot_send_message"
            ]
            return bool(audit_lines and send_lines and min(audit_lines) < min(send_lines))
    raise AssertionError("_process_message not found")


class TelegramClaimReceiptBeforeSend(unittest.TestCase):
    def test_real_process_message_audits_before_bot_send(self):
        self.assertTrue(_audit_before_send_in_source(SRC_PATH.read_text()))

    def test_guard_trips_when_send_precedes_audit(self):
        bad = '''
class X:
    async def _process_message(self):
        await _bot_send_message()
        _audit_telegram_reply_for_claim_receipts("x", surface="telegram_text")
'''
        self.assertFalse(_audit_before_send_in_source(bad))
```

- [ ] **Step 2: Run guard test**

Run:

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest tests.test_telegram_claim_receipt_before_send
```

Expected: PASS if Task 3 correctly placed the rail before send; FAIL otherwise.

- [ ] **Step 3: Commit**

```bash
git add tests/test_telegram_claim_receipt_before_send.py
git commit -m "test(coherence): pin telegram claim rail before send"
```

---

## Task 5: Shadow Artifact Tooling

**Files:**
- Create: `scripts/claim_receipt_shadow_review.py`
- Test: `tests/test_claim_receipt_shadow_review.py`

- [ ] **Step 1: Write failing parser and markdown tests**

Create `tests/test_claim_receipt_shadow_review.py`:

```python
import unittest

from scripts.claim_receipt_shadow_review import parse_lines, summarize, write_markdown


class ClaimReceiptShadowReview(unittest.TestCase):
    def test_parse_and_summarize_content_light_receipts(self):
        lines = [
            "2026-07-01 claim_receipt_rail surface=telegram_text action_type=web_search "
            "pattern_id=search_initiating receipt_present=False tense_class=present_progressive "
            "mode=shadow redo_outcome=none",
            "2026-07-01 claim_receipt_rail surface=telegram_text action_type=web_search "
            "pattern_id=past_excluded receipt_present=False tense_class=past "
            "mode=shadow redo_outcome=excluded",
        ]

        events = parse_lines(lines)
        summary = summarize(events)

        self.assertEqual(summary["catch_count"], 1)
        self.assertEqual(summary["tense_exclusion_count"], 1)
        self.assertEqual(summary["pattern_counts"]["search_initiating"], 1)

    def test_markdown_contains_gate_sentences(self):
        md = write_markdown(
            summarize(parse_lines([
                "claim_receipt_rail surface=telegram_text action_type=web_search "
                "pattern_id=search_initiating receipt_present=False tense_class=present_progressive "
                "mode=shadow redo_outcome=none"
            ])),
            fabricated_probe_caught=True,
            honest_1745_probe_clean=True,
        )

        self.assertIn("fabricated turn MUST catch: PASS", md)
        self.assertIn("receipted 17:45 turn MUST NOT catch: PASS", md)
        self.assertNotIn("Initiating live search", md)
```

- [ ] **Step 2: Run shadow-review tests and verify RED**

Run:

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest tests.test_claim_receipt_shadow_review
```

Expected: FAIL because script does not exist.

- [ ] **Step 3: Implement parser and markdown writer**

Create `scripts/claim_receipt_shadow_review.py`:

```python
"""Summarize content-light claim/receipt rail shadow logs."""
from __future__ import annotations

import argparse
import re
from collections import Counter
from pathlib import Path

_EVENT_RE = re.compile(
    r"claim_receipt_rail\s+surface=(?P<surface>\\S+)\\s+"
    r"action_type=(?P<action_type>\\S+)\\s+"
    r"pattern_id=(?P<pattern_id>\\S+)\\s+"
    r"receipt_present=(?P<receipt_present>\\S+)\\s+"
    r"tense_class=(?P<tense_class>\\S+)\\s+"
    r"mode=(?P<mode>\\S+)\\s+"
    r"redo_outcome=(?P<redo_outcome>\\S+)"
)


def parse_lines(lines: list[str]) -> list[dict]:
    events = []
    for line in lines:
        m = _EVENT_RE.search(line)
        if not m:
            continue
        d = m.groupdict()
        d["receipt_present"] = d["receipt_present"] == "True"
        events.append(d)
    return events


def summarize(events: list[dict]) -> dict:
    catches = [
        e for e in events
        if e["redo_outcome"] != "excluded" and not e["receipt_present"]
    ]
    excluded = [e for e in events if e["redo_outcome"] == "excluded"]
    return {
        "event_count": len(events),
        "catch_count": len(catches),
        "tense_exclusion_count": len(excluded),
        "receipt_present_count": sum(1 for e in events if e["receipt_present"]),
        "pattern_counts": dict(Counter(e["pattern_id"] for e in catches)),
        "redo_counts": dict(Counter(e["redo_outcome"] for e in events)),
    }


def write_markdown(
    summary: dict,
    *,
    fabricated_probe_caught: bool,
    honest_1745_probe_clean: bool,
) -> str:
    lines = [
        "# Claim-Receipt Shadow Review",
        "",
        "## Gate",
        f"- fabricated turn MUST catch: {'PASS' if fabricated_probe_caught else 'FAIL'}",
        f"- receipted 17:45 turn MUST NOT catch: {'PASS' if honest_1745_probe_clean else 'FAIL'}",
        "",
        "## Summary",
        f"- event_count: {summary['event_count']}",
        f"- catch_count: {summary['catch_count']}",
        f"- tense_exclusion_count: {summary['tense_exclusion_count']}",
        f"- receipt_present_count: {summary['receipt_present_count']}",
        f"- pattern_counts: {summary['pattern_counts']}",
        f"- redo_counts: {summary['redo_counts']}",
        "",
        "## Review Note",
        "This artifact is content-light. It contains no full reply text.",
        "",
    ]
    return "\\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--fabricated-probe-caught", action="store_true")
    parser.add_argument("--honest-1745-probe-clean", action="store_true")
    args = parser.parse_args()

    events = parse_lines(Path(args.log).read_text(errors="replace").splitlines())
    md = write_markdown(
        summarize(events),
        fabricated_probe_caught=args.fabricated_probe_caught,
        honest_1745_probe_clean=args.honest_1745_probe_clean,
    )
    Path(args.out).write_text(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests**

Run:

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest tests.test_claim_receipt_shadow_review
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/claim_receipt_shadow_review.py tests/test_claim_receipt_shadow_review.py
git commit -m "feat(coherence): add claim-receipt shadow review tooling"
```

---

## Task 6: Regression, Shadow Gate, And STOP

**Files:**
- Modify only if earlier tests reveal a seam.
- Create after live shadow: `docs/proof/2026-07-01-conversation-coherence-v0-shadow-review.md`

- [ ] **Step 1: Run targeted unit and structural suite**

Run:

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest \
  tests.test_action_receipts \
  tests.test_action_narration_claims \
  tests.test_claim_receipt_audit_api \
  tests.test_telegram_claim_receipt_plumbing \
  tests.test_telegram_claim_receipt_redo \
  tests.test_telegram_claim_receipt_before_send \
  tests.test_claim_receipt_shadow_review \
  tests.test_completion_rail \
  tests.test_completion_rail_audit \
  tests.test_telegram_reply_audit_coverage
```

Expected: PASS.

- [ ] **Step 2: Run lint on touched files**

Run:

```bash
cd /home/rohit/maez
.venv/bin/ruff check \
  core/safety/action_receipts.py \
  core/safety/self_claim_audit.py \
  skills/telegram_voice.py \
  scripts/claim_receipt_shadow_review.py \
  tests/test_action_receipts.py \
  tests/test_action_narration_claims.py \
  tests/test_claim_receipt_audit_api.py \
  tests/test_telegram_claim_receipt_plumbing.py \
  tests/test_telegram_claim_receipt_redo.py \
  tests/test_telegram_claim_receipt_before_send.py \
  tests/test_claim_receipt_shadow_review.py
```

Expected: PASS.

- [ ] **Step 3: Verify default-off / flag-off behavior**

Run the targeted tests with both flags absent:

```bash
cd /home/rohit/maez
env -u MAEZ_CLAIM_RECEIPT_SHADOW -u MAEZ_CLAIM_RECEIPT_ENFORCE \
  .venv/bin/python -m unittest tests.test_claim_receipt_audit_api tests.test_telegram_claim_receipt_redo
```

Expected: PASS. The action-narration rail must not change replies when both flags are off.

- [ ] **Step 4: Commit final test/lint fixes if any**

If Step 1-3 required changes:

```bash
git add <changed files>
git commit -m "test(coherence): verify claim-receipt rail gate"
```

If no changes were needed, skip this commit.

- [ ] **Step 5: STOP AT SHADOW REVIEW GATE**

Do not enable enforcement. Do not restart live services unless the owner explicitly asks.

Handoff requirements:

- Branch/commit state.
- Targeted test output.
- Ruff output.
- Confirmation that `MAEZ_CLAIM_RECEIPT_ENFORCE` remains off.
- Shadow runbook:

```bash
# owner/live step, not automatic in build lane
MAEZ_CLAIM_RECEIPT_SHADOW=1
MAEZ_CLAIM_RECEIPT_ENFORCE=0
# restart maez.service or maez-web/telegram process as appropriate for the live surface
```

After live traffic or probe traffic runs, generate the artifact:

```bash
cd /home/rohit/maez
.venv/bin/python scripts/claim_receipt_shadow_review.py \
  --log logs/cognition.log \
  --out docs/proof/2026-07-01-conversation-coherence-v0-shadow-review.md \
  --fabricated-probe-caught \
  --honest-1745-probe-clean
```

The owner/Codex review gate reads:

- fabricated 2026-07-01 action-narration shape catches;
- honest 17:45 receipted-search shape does not catch;
- no ordinary memory/past-action sentence catches;
- no full reply text appears in receipts or the artifact;
- enforcement remains off until owner flips it.

---

## Self-Review

**Spec coverage:** Task 0 covers typed this-turn receipts and the honest 17:45 must-pass foundation. Task 1 covers action-narration vocabulary, context-gated "here is what I found", past-action exclusion, and type mismatch. Task 2 covers the structured API seam and flag-off byte identity. Task 3 covers one redo owned by Telegram, no scripted replacement in `self_claim_audit`, and the honest degraded floor. Task 4 pins before-send structurally. Task 5 covers shadow artifact tooling. Task 6 preserves the STOP gate before enforcement.

**Placeholder scan:** No placeholder markers. The only live-data dependency is the explicit shadow review gate, which is the spec's owner-reviewed enforcement gate, not an implementation gap.

**Type consistency:** Receipt helpers use `action_type="web_search"`. `Flag.action_type`, `ActionClaimMismatch.action_type`, and `tool_results[].action_type` use the same string. Telegram uses `_TelegramAuditOutcome.needs_redo` and `action_mismatch`; `self_claim_audit` does not generate replacement wording for action-narration claims.

**Important implementation nuance:** The redo branch must not run a search. It gives the model facts and one chance to answer honestly. If a real search should happen, that remains the routing/search-commitment lane, not this rail.
