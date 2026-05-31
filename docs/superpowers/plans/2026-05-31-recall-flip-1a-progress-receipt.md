# Recall-Flip Slice 1a — Progress Receipt + A7 Telemetry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One truthful, substrate-backed progress receipt fired only when a recall answer is genuinely slow — never touching the answer — plus the content-free ack telemetry A7 needs. Visible substrate state, not chain-of-thought.

**Architecture:** A pure `core/routing/recall_receipt.py` (the receipt string, the eligibility/ack-status logic, the cognition-verb lint surface). `core/routing/recall_outcome.py` gains content-free A7 fields (schema bump to `recall_outcome.v2`). `daemon/maez_daemon.py` threads a keyword-only fire-and-forget `send_intermediate` sink into `handle_message`, arms a **one-shot watchdog** after the FOCUSED working set is observed + carrier→consulted (before `_focused_synthesize` blocks), and emits the ack telemetry. `skills/surface/maez_adapter.py` passes a non-blocking progress sink. Gated by `MAEZ_RECALL_RECEIPT_ENABLED` (default-off).

**Tech Stack:** Python 3, stdlib `threading`/`enum`/`dataclasses`, `unittest` via `.venv/bin/python -m unittest`.

**Spec:** [docs/superpowers/specs/2026-05-31-recall-progress-receipt-and-a7-gate-design.md](../specs/2026-05-31-recall-progress-receipt-and-a7-gate-design.md); A7 amendment in the frozen flip spec @ ccac4a4. Constants v1: `RECEIPT_AFTER_MS=900`, `ACK_CEILING_MS=1500`, `RECEIPT_SEND_TIMEOUT_MS=1000`.

**Discipline reminders:**
- The answer path is **untouched**: receipts are emission-only, never a gate. A failing/throttling/timing-out send must leave `reply` **byte-identical**.
- The receipt fires **only after** the FOCUSED carrier path is engaged (not on `_date_addressed_turn`), **only** if elapsed crosses `RECEIPT_AFTER_MS`, **at most once**.
- **Visible substrate state, not chain-of-thought** ([[feedback_visible_substrate_state_not_chain_of_thought]]): closed body-verb wording; a cognition-verb lint enforces it.
- Telemetry content-free (`ack_emit_ms` = successful *send completion*, never "queued"; no query/answer text).
- Don't touch `config/.env`. Flag via launch-env; default-off.

---

## File Structure
- **Create** `core/routing/recall_receipt.py` — `AckStatus` enum, `WORKING_RECEIPT_TEXT`, `FORBIDDEN_COGNITION_VERBS`, `receipt_eligible(...)`, `resolve_ack_status(...)`.
- **Create** `tests/test_recall_receipt.py` — wording lint + eligibility/ack-status truth table.
- **Modify** `core/routing/recall_outcome.py` — add A7 fields, bump `schema_version` to `recall_outcome.v2`; content-free test still passes.
- **Modify** `daemon/maez_daemon.py` — keyword-only `send_intermediate` param on `handle_message`; the one-shot watchdog; emit A7 telemetry; `_recall_receipt_enabled()`.
- **Modify** `skills/surface/maez_adapter.py` — pass a non-blocking progress sink into `handle_message`.
- **Modify** `tests/test_memory_integrity_invariant.py` — daemon-shaped tests (slow→receipt, fast→none, byte-identical-reply, send-failure-doesn't-break).

---

## Task 1: Extend `RecallOutcome` with content-free A7 ack fields

**Files:** Modify `core/routing/recall_outcome.py`; Test `tests/test_recall_outcome.py`

- [ ] **Step 1: Failing test** — add A7 fields + `AckStatus`, bump schema:

```python
# add to tests/test_recall_outcome.py
def test_schema_bumped_to_v2_with_ack_fields(self):
    import dataclasses
    from core.routing.recall_outcome import RecallOutcome
    self.assertEqual(RecallOutcome.schema_version, "recall_outcome.v2")
    names = {f.name for f in dataclasses.fields(RecallOutcome)}
    self.assertTrue({"receipt_eligible", "receipt_after_ms", "ack_required",
                     "ack_status", "ack_emit_ms"} <= names)

def test_ack_fields_are_content_free(self):
    import dataclasses
    from core.routing.recall_outcome import RecallOutcome
    names = {f.name for f in dataclasses.fields(RecallOutcome)}
    forbidden = {"query_text", "text", "reply", "recalled_snippet", "content",
                 "receipt_text", "owner_question"}
    self.assertEqual(names & forbidden, set())
```

- [ ] **Step 2: Run → fail** (`.venv/bin/python -m unittest tests.test_recall_outcome -v`).

- [ ] **Step 3: Implement** — bump `schema_version = "recall_outcome.v2"`; add fields with safe defaults so existing constructors stay valid:
```python
    receipt_eligible: bool = False
    receipt_after_ms: int | None = None
    ack_required: bool = False
    ack_status: str = "not_eligible"     # AckStatus value
    ack_emit_ms: int | None = None
```
(Keep `ack_status` a plain str carrying an `AckStatus` value — same pattern as `denial_kind` — so the record stays a simple frozen dataclass.)

- [ ] **Step 4: Run → pass. Commit.**

---

## Task 2: `recall_receipt.py` — wording, lint, eligibility/ack logic (pure)

**Files:** Create `core/routing/recall_receipt.py`, `tests/test_recall_receipt.py`

- [ ] **Step 1: Failing test**

```python
# tests/test_recall_receipt.py
import unittest
from core.routing.recall_receipt import (
    AckStatus, WORKING_RECEIPT_TEXT, FORBIDDEN_COGNITION_VERBS,
    receipt_eligible, resolve_ack_status,
)

RECEIPT_AFTER_MS = 900


class ReceiptWordingTest(unittest.TestCase):
    def test_working_receipt_is_body_state_not_thought(self):
        low = WORKING_RECEIPT_TEXT.lower()
        for verb in FORBIDDEN_COGNITION_VERBS:
            self.assertNotIn(verb, low, f"cognition-verb leaked: {verb}")
        self.assertIn("checking", low)               # body-verb
    def test_genderless(self):
        low = f" {WORKING_RECEIPT_TEXT.lower()} "
        for bad in (" she ", " he ", " her ", " his ", " him "):
            self.assertNotIn(bad, low)


class EligibilityTest(unittest.TestCase):
    def test_eligible_only_when_focused_carrier_engaged(self):
        self.assertTrue(receipt_eligible(flag_on=True, focused_carrier_engaged=True))
        self.assertFalse(receipt_eligible(flag_on=True, focused_carrier_engaged=False))
        self.assertFalse(receipt_eligible(flag_on=False, focused_carrier_engaged=True))


class AckStatusTest(unittest.TestCase):
    def test_fast_answer_no_receipt(self):
        # answer ready before threshold → not_required_fast_answer, ack not required
        self.assertEqual(resolve_ack_status(eligible=True, fired=False,
                         send_result=None), AckStatus.NOT_REQUIRED_FAST_ANSWER.value)
    def test_emitted_on_successful_send(self):
        self.assertEqual(resolve_ack_status(eligible=True, fired=True,
                         send_result="ok"), AckStatus.EMITTED.value)
    def test_send_failed_and_timeout_are_distinct(self):
        self.assertEqual(resolve_ack_status(eligible=True, fired=True,
                         send_result="failed"), AckStatus.SEND_FAILED.value)
        self.assertEqual(resolve_ack_status(eligible=True, fired=True,
                         send_result="timeout"), AckStatus.SEND_TIMEOUT.value)
    def test_disabled_and_not_eligible(self):
        self.assertEqual(resolve_ack_status(eligible=False, fired=False,
                         send_result=None, disabled=True), AckStatus.DISABLED.value)
        self.assertEqual(resolve_ack_status(eligible=False, fired=False,
                         send_result=None), AckStatus.NOT_ELIGIBLE.value)
```

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Implement**

```python
# core/routing/recall_receipt.py
"""One truthful substrate-backed recall progress receipt. State, not thought."""
from __future__ import annotations
from enum import Enum

WORKING_RECEIPT_TEXT = "I'm checking my dated memory for that."
FORBIDDEN_COGNITION_VERBS = (
    "think", "thinking", "ponder", "consider", "wonder", "mull", "reflect",
    "feel", "sense",
)


class AckStatus(Enum):
    NOT_REQUIRED_FAST_ANSWER = "not_required_fast_answer"
    EMITTED = "emitted"
    SEND_FAILED = "send_failed"
    SEND_TIMEOUT = "send_timeout"
    DISABLED = "disabled"
    NOT_ELIGIBLE = "not_eligible"


def receipt_eligible(*, flag_on: bool, focused_carrier_engaged: bool) -> bool:
    """A receipt is eligible only when the flag is on AND the FOCUSED carrier
    path is actually engaged (not merely a date-addressed turn)."""
    return bool(flag_on and focused_carrier_engaged)


def resolve_ack_status(*, eligible: bool, fired: bool, send_result, disabled: bool = False) -> str:
    if disabled:
        return AckStatus.DISABLED.value
    if not eligible:
        return AckStatus.NOT_ELIGIBLE.value
    if not fired:
        # eligible but the answer was ready before the threshold → no receipt needed
        return AckStatus.NOT_REQUIRED_FAST_ANSWER.value
    return {
        "ok": AckStatus.EMITTED.value,
        "failed": AckStatus.SEND_FAILED.value,
        "timeout": AckStatus.SEND_TIMEOUT.value,
    }.get(send_result, AckStatus.SEND_FAILED.value)
```

- [ ] **Step 4: Run → pass. Commit.**

---

## Task 3: Non-blocking progress sink (surface)

**Files:** Modify `skills/surface/maez_adapter.py`; test in `tests/test_memory_integrity_invariant.py` (Task 5).

- [ ] **Step 1:** Add a fire-and-forget progress sink wrapper near `_send_intermediate` (`maez_adapter.py:309`): a synchronous callable `progress_sink(text) -> None` that **schedules** the send on the surface loop and returns immediately — `asyncio.run_coroutine_threadsafe(...)` wrapping the actual Telegram send in `asyncio.wait_for(..., timeout=RECEIPT_SEND_TIMEOUT_MS/1000)`, swallowing+logging exceptions, and recording a content-free outcome (`ok`/`failed`/`timeout`) the daemon can read back for `ack_status`. It must **never** call `.result()` on the synthesis thread. (Contrast the existing `_send_intermediate` which does `fut.result(timeout=20)` — do NOT reuse that blocking shape.)

- [ ] **Step 2:** At the `handle_message(...)` call site (`maez_adapter.py:437`), pass `send_intermediate=progress_sink`.

- [ ] **Step 3: Commit** (with Task 4, since the daemon side is needed to exercise it).

---

## Task 4: Daemon — keyword param + one-shot watchdog + A7 telemetry

**Files:** Modify `daemon/maez_daemon.py`; tests in Task 5.

- [ ] **Step 1:** Add `_recall_receipt_enabled()` (reads `MAEZ_RECALL_RECEIPT_ENABLED`, default-off) near `_recall_status_intercept_enabled` (`:1010`).

- [ ] **Step 2:** Add a **keyword-only** `send_intermediate=None` parameter to `handle_message` (`:3556`). Default `None` → all existing callers/tests unchanged.

- [ ] **Step 3: The one-shot watchdog.** Immediately after the FOCUSED carrier path observes a non-`None` working set and sets `_recall_carrier_receipt = RECALL_CARRIER_CONSULTED` (`:4431`), and **before** `_focused_synthesize` (`:4452`), arm a `threading.Timer`:
```python
        _receipt_fired = {"v": False}
        _receipt_timer = None
        if (send_intermediate is not None and _recall_receipt_enabled()
                and receipt_eligible(flag_on=True, focused_carrier_engaged=True)):
            from core.routing.recall_receipt import WORKING_RECEIPT_TEXT
            elapsed_ms = (time.monotonic() - _trace_t_start) * 1000  # _trace_t_start = turn start
            delay_s = max(0.0, (RECEIPT_AFTER_MS - elapsed_ms) / 1000.0)
            def _fire():
                _receipt_fired["v"] = True
                try:
                    send_intermediate(WORKING_RECEIPT_TEXT)
                except Exception as exc:
                    logger.debug("recall receipt send skipped: %s", type(exc).__name__)
            _receipt_timer = threading.Timer(delay_s, _fire)
            _receipt_timer.daemon = True
            _receipt_timer.start()
```
After `_focused_synthesize` returns (and on every exit path of the FOCUSED block), cancel the timer if it hasn't fired:
```python
        finally:
            if _receipt_timer is not None:
                _receipt_timer.cancel()
```
The timer fires the receipt **only if** synthesis is still running at `RECEIPT_AFTER_MS`; a fast answer cancels it first (→ `not_required_fast_answer`). The watchdog runs on its own thread; `send_intermediate` is itself non-blocking, so it never delays synthesis.

- [ ] **Step 4: Emit A7 telemetry** on the `recall_outcome` row: `receipt_eligible`, `receipt_after_ms=RECEIPT_AFTER_MS`, `ack_required = _receipt_fired["v"]`, `ack_status = resolve_ack_status(eligible=…, fired=_receipt_fired["v"], send_result=<from the sink>, disabled=not _recall_receipt_enabled())`, `ack_emit_ms` = elapsed at successful send completion (the sink reports it back) else `None`. (The sink writes its result + completion time to a turn-local box the daemon reads after synthesis.)

- [ ] **Step 5: Commit** (Tasks 3+4 together).

---

## Task 5: Daemon-shaped tests (the contract)

**Files:** `tests/test_memory_integrity_invariant.py` (reuse the harness)

- [ ] **Step 1: Real tests** (mirror the existing fold tests' `handle_message` harness):
```python
def test_slow_synthesis_fires_one_receipt(self):
    # MAEZ_RECALL_RECEIPT_ENABLED=1; mock _focused_synthesize to sleep > RECEIPT_AFTER_MS;
    # capture the progress sink; assert exactly ONE receipt = WORKING_RECEIPT_TEXT,
    # ack_status=emitted in the recall_outcome line, ack_emit_ms present.
    ...
def test_fast_synthesis_fires_no_receipt(self):
    # fast synthesis (< RECEIPT_AFTER_MS) → zero receipts, ack_status=not_required_fast_answer.
    ...
def test_receipt_send_failure_leaves_reply_byte_identical(self):
    # progress sink raises/times out → reply identical to receipts-off; synthesis not delayed.
    ...
def test_non_focused_dated_turn_emits_no_receipt(self):
    # a date-addressed turn answered by TOOL/ECHO/HONEST_EMPTY → no dangling receipt.
    ...
def test_receipt_disabled_by_default(self):
    # flag unset → no receipt, ack_status=disabled, reply unchanged.
    ...
```
(Write real bodies using `_build_daemon_for_handle_message` + `_handle_message_mock_stack`; mock `_focused_synthesize` timing via `mock.patch` with a sleep; capture the sink via a list.)

- [ ] **Step 2: Run → implement any seams → pass.**

- [ ] **Step 3: Commit.**

---

## Task 6: Lint + regression

- [ ] **Step 1:** Cognition-verb lint over every receipt/terminal string the slice can emit (`WORKING_RECEIPT_TEXT` + confirm the reused decline strings are unchanged) → no forbidden verb.
- [ ] **Step 2:** `.venv/bin/python -m unittest tests.test_recall_receipt tests.test_recall_outcome tests.test_recall_shadow tests.test_recall_self_status tests.test_memory_integrity_invariant -v 2>&1 | tail -6` → green. Ruff on the changed files. Confirm the temporal-guard cluster is unchanged (worktree-env artifact, not introduced).
- [ ] **Step 3: Commit** (scoped staging; NOT `git add -A`).

---

## Self-Review
**1. Spec coverage:** one receipt, real-wait-gated (Task 4 watchdog at `RECEIPT_AFTER_MS`) ✓; true-by-construction (armed after carrier=consulted, eligible only when FOCUSED engaged) ✓; closed body-verb wording + cognition-verb lint (Tasks 2,6) ✓; decline reuses shipped strings, no re-mint (no decline code in this slice) ✓; non-blocking fire-and-forget sink + byte-identical-reply test (Tasks 3,5) ✓; content-free A7 telemetry, `ack_emit_ms` = send completion (Tasks 1,4) ✓; own flag default-off ✓; A7 gate computation is the 2b re-run (not this slice) ✓; re-witness dependency is a runbook step (not code). ✓

**2. Placeholder scan:** Tasks 1,2 complete code. Tasks 3,4,5 give the watchdog code + the sink contract + real test intents; the exact `finally`-placement and the sink-result-box wiring are marked to match the daemon's existing FOCUSED-block control flow (the daemon-shaped tests in Task 5 pin the observable contract: one-receipt-on-slow, none-on-fast, byte-identical-on-failure). Flagged as integration points, not undefined logic — same pattern as 1a/1b/2a.

**3. Type/symbol consistency:** `AckStatus`/`receipt_eligible`/`resolve_ack_status`/`WORKING_RECEIPT_TEXT`/`FORBIDDEN_COGNITION_VERBS`, `send_intermediate` param, `recall_outcome.v2` fields used identically across tasks; `RECEIPT_AFTER_MS=900` / `RECEIPT_SEND_TIMEOUT_MS=1000` from the spec.

**4. Ordering:** record fields (1) → pure receipt logic (2) → surface sink (3) → daemon watchdog + telemetry (4) → daemon-shaped tests (5) → lint+regression (6). Pure before wiring; each task independently committable.

## Execution note
The watchdog touches `handle_message`'s FOCUSED block (`:4413–4525`). Read that block first: arm after `_recall_carrier_receipt = RECALL_CARRIER_CONSULTED` (`:4431`), cancel in a `finally` covering all FOCUSED exits, before/around `_focused_synthesize` (`:4452`). The non-negotiable test is `test_receipt_send_failure_leaves_reply_byte_identical` — if the receipt can change or delay the answer, the slice is wrong. Codex's six-agent pass should pressure the answer-path-isolation before the wording.
