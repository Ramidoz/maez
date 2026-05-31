# Recall-Flip Slice 1b — Shadow-Mode Counterfactual Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A silent, read-only, off-critical-path "second opinion" that, on flag-off recall-relevant turns, records whether the not-yet-live recall stack would have had useful dated material — content-free, side-effect-free, never served — to gather pre-flip safety + benefit evidence.

**Architecture:** A new pure module `core/routing/recall_shadow.py` (the `ShadowOutcome` record + `ShadowReach`/`ShadowSkip` enums + `derive_*` functions + `compute_shadow_pair_id`). The daemon runs the shadow on a **bounded single-worker background executor** after the reply is committed, via **direct read-only memory recall** (`recall_for_telegram_living(record_recalls=False)` → reused partition→RecallItem conversion → `assemble_working_set`) — **never** the dispatcher. The carried 1a ReplyPath brittleness is closed here.

**Tech Stack:** Python 3, stdlib `enum`/`dataclasses`/`hashlib`, `unittest` via `.venv/bin/python -m unittest`.

**Spec:** [docs/superpowers/specs/2026-05-30-recall-flip-1b-shadow-harness-design.md](../specs/2026-05-30-recall-flip-1b-shadow-harness-design.md) (committed @ d8baa55).

**Discipline reminders:**
- Lands **flag-off + shadow-off** (`MAEZ_RECALL_SHADOW_ENABLED` default-absent). The shadow is observe-only; it must NEVER change the served reply, write any substrate, or egress.
- Content-free telemetry — no query/snippet/reply text, no raw `trace_id`, no exception message. Enforced by tests.
- Do NOT touch `config/.env`. Flags via launch-env / `mock.patch.dict` in tests.
- Genderless self-reference in any speakable string.

---

## File Structure
- **Create** `core/routing/recall_shadow.py` — `ShadowReach`, `ShadowSkip`, `ShadowOutcome` (frozen, content-free, `shadow_outcome.v1`), `compute_shadow_pair_id`, `derive_shadow_reach`, `derive_shadow_outcome`.
- **Create** `tests/test_recall_shadow.py` — pure derivations + content-free closure + closed-enum tests.
- **Modify** `core/routing/recall_outcome.py` — add `reply_path_from_mode(mode) -> ReplyPath` (ReplyPath hardening).
- **Modify** `core/brain/brain_loop.py` — extract the partition→RecallItem conversion to a reusable module-level `recall_partitions_to_items(...)`; the live adapter calls it (refactor, no behavior change).
- **Modify** `daemon/maez_daemon.py` — `_shadow_worker` (bounded singleton); `_recall_shadow_enabled()`; post-reply-commit snapshot + submit; the read-only shadow run; emit `shadow_pair_id` on the live `recall_outcome` row; swap the ReplyPath coercion to `reply_path_from_mode`.
- **Modify** `core/routing/recall_self_status.py` — speakable shadow-active state.
- **Modify** `tests/test_memory_integrity_invariant.py` — daemon-shaped tests (off-critical-path, no-dispatcher, per-substrate non-disturbance, pairing, queue_full) in the harness-hosting class.

---

## Task 1: ReplyPath hardening (closes the carried 1a brittleness)

**Files:**
- Modify: `core/routing/recall_outcome.py`, `daemon/maez_daemon.py` (the coercion ~line 4165)
- Test: `tests/test_recall_outcome.py`

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_recall_outcome.py
from core.routing.recall_outcome import ReplyPath, reply_path_from_mode


class ReplyPathFromModeTest(unittest.TestCase):
    def test_known_modes_map(self):
        self.assertIs(reply_path_from_mode("focused"), ReplyPath.FOCUSED)
        self.assertIs(reply_path_from_mode("legacy"), ReplyPath.LEGACY)
        self.assertIs(reply_path_from_mode("tool"), ReplyPath.TOOL)

    def test_unknown_mode_falls_back_to_legacy_no_raise(self):
        # CLINICAL/CAMERA/BACKEND_ERROR are valid ReplyMode values with no ReplyPath member;
        # must NOT raise inside the daemon hot path.
        for unknown in ("clinical", "camera", "backend_error", "nonsense"):
            self.assertIs(reply_path_from_mode(unknown), ReplyPath.LEGACY, unknown)
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m unittest tests.test_recall_outcome.ReplyPathFromModeTest -v`
Expected: FAIL — `cannot import name 'reply_path_from_mode'`.

- [ ] **Step 3: Implement the helper**

Add to `core/routing/recall_outcome.py`:

```python
import logging as _logging

_log = _logging.getLogger(__name__)


def reply_path_from_mode(mode_value: str) -> "ReplyPath":
    """Total, crash-safe coercion of a ReplyMode value to a ReplyPath.

    ReplyMode has values (clinical/camera/backend_error) with no ReplyPath member;
    those never reach the recall_outcome reply-path site today, but coercing them
    must never raise inside handle_message. Unknown -> LEGACY + a content-free warning.
    """
    try:
        return ReplyPath(str(mode_value))
    except ValueError:
        _log.warning("reply_path_unknown_mode mode=%s -> legacy", str(mode_value))
        return ReplyPath.LEGACY
```

- [ ] **Step 4: Swap the daemon coercion**

In `daemon/maez_daemon.py` (~line 4165), replace `_reply_path = ReplyPath(_reply_decision.mode.value.lower())` with:

```python
        from core.routing.recall_outcome import reply_path_from_mode
        _reply_path = reply_path_from_mode(_reply_decision.mode.value.lower())
```

(Keep the existing `ReplyPath.SELF_STATUS`/`DATED_HONESTY`/`LEGACY` assignments at their branches.)

- [ ] **Step 5: Run + commit**

Run: `.venv/bin/python -m unittest tests.test_recall_outcome -v` → PASS.
```bash
git add core/routing/recall_outcome.py daemon/maez_daemon.py tests/test_recall_outcome.py
git commit -m "fix(recall): total crash-safe reply_path_from_mode (closes 1a coercion brittleness)"
```

---

## Task 2: `recall_shadow.py` pure module

**Files:**
- Create: `core/routing/recall_shadow.py`
- Test: `tests/test_recall_shadow.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_recall_shadow.py
import dataclasses
import unittest

from core.routing.recall_outcome import OutcomeClass
from core.routing.recall_shadow import (
    ShadowOutcome,
    ShadowReach,
    ShadowSkip,
    compute_shadow_pair_id,
    derive_shadow_outcome,
    derive_shadow_reach,
)


class _FakeItem:
    def __init__(self, source_type, confirmed):
        self.source_type = source_type
        self.local_label = "E1"
        self.text = "x"
        self.temporal_provenance = {"confirmed": confirmed} if confirmed is not None else None


class _FakeWS:
    def __init__(self, items):
        self.items = items


class PairIdTest(unittest.TestCase):
    def test_deterministic_and_not_raw_trace_id(self):
        a = compute_shadow_pair_id(boot_id="boot1", trace_id="abc123")
        b = compute_shadow_pair_id(boot_id="boot1", trace_id="abc123")
        self.assertEqual(a, b)
        self.assertEqual(len(a), 24)
        self.assertNotIn("abc123", a)          # never embeds the raw trace_id
    def test_varies_by_boot_and_trace(self):
        self.assertNotEqual(
            compute_shadow_pair_id(boot_id="boot1", trace_id="t"),
            compute_shadow_pair_id(boot_id="boot2", trace_id="t"),
        )


class ShadowReachTest(unittest.TestCase):
    def test_confirmed_memory_context_is_grounded_material(self):
        ws = _FakeWS([_FakeItem("memory_context", True)])
        self.assertIs(derive_shadow_reach(ws, date_addressed=True), ShadowReach.GROUNDED_MATERIAL_AVAILABLE)
    def test_consulted_no_confirmed_is_confirmed_absence(self):
        ws = _FakeWS([_FakeItem("memory_context", False)])
        self.assertIs(derive_shadow_reach(ws, date_addressed=True), ShadowReach.CONFIRMED_ABSENCE_WITNESSED)
    def test_semantic_or_web_does_not_count_as_grounded(self):
        ws = _FakeWS([_FakeItem("web_context", True), _FakeItem("memory_context", False)])
        self.assertIs(derive_shadow_reach(ws, date_addressed=True), ShadowReach.CONFIRMED_ABSENCE_WITNESSED)
    def test_none_working_set_is_carrier_unavailable(self):
        self.assertIs(derive_shadow_reach(None, date_addressed=True), ShadowReach.CARRIER_UNAVAILABLE)


class ShadowOutcomeDeriveTest(unittest.TestCase):
    def test_rescuable_when_legacy_declined_and_shadow_grounded(self):
        rec = derive_shadow_outcome(
            legacy_outcome=OutcomeClass.DECLINED_UNAVAILABLE,
            legacy_is_false_absence=False,
            shadow_reach=ShadowReach.GROUNDED_MATERIAL_AVAILABLE,
            legacy_was_decline=True,
            date_addressed=True,
            shadow_pair_id="p", latency_delta_ms=3, ts=1, boot_id="b",
        )
        self.assertTrue(rec.rescuable_candidate)
        self.assertFalse(rec.false_absence_candidate)
    def test_false_absence_candidate_when_shadow_absent_but_legacy_answered(self):
        rec = derive_shadow_outcome(
            legacy_outcome=OutcomeClass.ANSWERED_UNVERIFIABLE,
            legacy_is_false_absence=False,
            shadow_reach=ShadowReach.CONFIRMED_ABSENCE_WITNESSED,
            legacy_was_decline=False,
            date_addressed=True,
            shadow_pair_id="p", latency_delta_ms=3, ts=1, boot_id="b",
        )
        self.assertTrue(rec.false_absence_candidate)
    def test_continuity_only_cannot_be_false_absence_candidate(self):
        rec = derive_shadow_outcome(
            legacy_outcome=OutcomeClass.ANSWERED_UNVERIFIABLE,
            legacy_is_false_absence=False,
            shadow_reach=ShadowReach.CONFIRMED_ABSENCE_WITNESSED,
            legacy_was_decline=False,
            date_addressed=False,
            shadow_pair_id="p", latency_delta_ms=3, ts=1, boot_id="b",
        )
        self.assertFalse(rec.false_absence_candidate)
    def test_legacy_false_absence_rescuable(self):
        rec = derive_shadow_outcome(
            legacy_outcome=OutcomeClass.DECLINED_UNVERIFIED,
            legacy_is_false_absence=True,
            shadow_reach=ShadowReach.GROUNDED_MATERIAL_AVAILABLE,
            legacy_was_decline=True,
            date_addressed=True,
            shadow_pair_id="p", latency_delta_ms=3, ts=1, boot_id="b",
        )
        self.assertTrue(rec.legacy_false_absence_rescuable)


class ContentFreeAndClosedEnumTest(unittest.TestCase):
    def test_record_is_content_free(self):
        names = {f.name for f in dataclasses.fields(ShadowOutcome)}
        forbidden = {"query_text", "text", "raw_text", "reply", "recalled_snippet",
                     "content", "owner_question", "snippet", "trace_id", "exception_message"}
        self.assertEqual(names & forbidden, set())
    def test_skip_reasons_closed(self):
        self.assertEqual(
            {s.value for s in ShadowSkip},
            {"budget_exceeded", "queue_full", "carrier_unavailable", "exception"},
        )
    def test_schema_version(self):
        self.assertEqual(ShadowOutcome.schema_version, "shadow_outcome.v1")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m unittest tests.test_recall_shadow -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Write the module**

```python
# core/routing/recall_shadow.py
"""Content-free shadow (assemble-only) counterfactual record + derivations.

Records WHETHER the not-yet-live recall stack would have had useful dated
material, never WHAT was asked or recalled. Assemble-only: it witnesses
retrieval reach, never answer quality (no synthesis is run).
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum
from typing import ClassVar, Optional

from core.routing.recall_outcome import OutcomeClass


class ShadowReach(Enum):
    GROUNDED_MATERIAL_AVAILABLE = "grounded_material_available"
    CONFIRMED_ABSENCE_WITNESSED = "confirmed_absence_witnessed"
    CARRIER_UNAVAILABLE = "carrier_unavailable"


class ShadowSkip(Enum):
    BUDGET_EXCEEDED = "budget_exceeded"
    QUEUE_FULL = "queue_full"
    CARRIER_UNAVAILABLE = "carrier_unavailable"
    EXCEPTION = "exception"


_LEGACY_RESCUABLE_FROM = {
    OutcomeClass.DECLINED_UNAVAILABLE,
    OutcomeClass.DECLINED_FAILED,
    OutcomeClass.DECLINED_UNVERIFIED,
    OutcomeClass.ANSWERED_UNVERIFIABLE,
}


@dataclass(frozen=True)
class ShadowOutcome:
    schema_version: ClassVar[str] = "shadow_outcome.v1"

    shadow_pair_id: str            # derived, non-authoritative (NOT raw trace_id)
    legacy_outcome: OutcomeClass
    shadow_reach: ShadowReach
    rescuable_candidate: bool
    false_absence_candidate: bool
    legacy_false_absence_rescuable: bool
    latency_delta_ms: int
    receipt_state: str             # "consulted" | "not_consulted"
    ts: int
    boot_id: str


def compute_shadow_pair_id(*, boot_id: str, trace_id: str) -> str:
    """Derived, non-authoritative pairing key. NOT the raw trace_id (which other
    stores key owner labels by) and NOT the ledger turn_id (which reaches raw_text)."""
    digest = hashlib.sha256(
        ("recall_shadow.v1\0" + (boot_id or "") + "\0" + (trace_id or "")).encode("utf-8")
    )
    return digest.hexdigest()[:24]


def _item_confirmed_memory_context(item) -> bool:
    if getattr(item, "source_type", None) != "memory_context":
        return False
    prov = getattr(item, "temporal_provenance", None) or {}
    return bool(prov.get("confirmed"))


def derive_shadow_reach(working_set, *, date_addressed: bool) -> ShadowReach:
    """Retrieval-stage reach. grounded only on a date-confirmed memory_context item
    (not semantic fallback / web / temporal_recall_status). No synthesis."""
    items = list(getattr(working_set, "items", ()) or []) if working_set is not None else []
    if working_set is None or not items:
        return ShadowReach.CARRIER_UNAVAILABLE
    if any(_item_confirmed_memory_context(i) for i in items):
        return ShadowReach.GROUNDED_MATERIAL_AVAILABLE
    return ShadowReach.CONFIRMED_ABSENCE_WITNESSED


def derive_shadow_outcome(
    *,
    legacy_outcome: OutcomeClass,
    legacy_is_false_absence: bool,
    shadow_reach: ShadowReach,
    legacy_was_decline: bool,
    date_addressed: bool,
    shadow_pair_id: str,
    latency_delta_ms: int,
    ts: int,
    boot_id: str,
) -> ShadowOutcome:
    grounded = shadow_reach is ShadowReach.GROUNDED_MATERIAL_AVAILABLE
    rescuable = bool(legacy_outcome in _LEGACY_RESCUABLE_FROM and grounded)
    false_absence = bool(
        date_addressed
        and shadow_reach is ShadowReach.CONFIRMED_ABSENCE_WITNESSED
        and not legacy_was_decline
    )
    legacy_false_absence_rescuable = bool(legacy_is_false_absence and grounded)
    receipt_state = (
        "not_consulted" if shadow_reach is ShadowReach.CARRIER_UNAVAILABLE else "consulted"
    )
    return ShadowOutcome(
        shadow_pair_id=shadow_pair_id,
        legacy_outcome=legacy_outcome,
        shadow_reach=shadow_reach,
        rescuable_candidate=rescuable,
        false_absence_candidate=false_absence,
        legacy_false_absence_rescuable=legacy_false_absence_rescuable,
        latency_delta_ms=latency_delta_ms,
        receipt_state=receipt_state,
        ts=ts,
        boot_id=boot_id,
    )
```

- [ ] **Step 4: Run + commit**

Run: `.venv/bin/python -m unittest tests.test_recall_shadow -v` → PASS.
```bash
git add core/routing/recall_shadow.py tests/test_recall_shadow.py
git commit -m "feat(recall): shadow_outcome record + reach/skip enums + derived pair-id (content-free)"
```

---

## Task 3: Extract the partition→RecallItem conversion (DRY, shared confirmed-provenance)

**Files:**
- Modify: `core/brain/brain_loop.py` (~lines 360-394 — the local `_items_for`/`_combined_context_items` closures)
- Test: `tests/test_dispatcher_layer1.py` or a small new test (the live adapter still produces identical items)

Rationale: the shadow MUST derive `confirmed` (`method in ("exact_date","month_window")`) identically to the live adapter, or `grounded_material_available` diverges from the live `had_confirmed`. Extract to one reusable function.

- [ ] **Step 1: Write a failing test pinning the extracted function**

```python
# tests/test_recall_partitions_to_items.py
import unittest
from core.brain.brain_loop import recall_partitions_to_items


class PartitionsToItemsTest(unittest.TestCase):
    def test_exact_date_is_confirmed_memory_context(self):
        partition = {"core": [{"id": "m1", "content": "on April 27 X",
                               "metadata": {"temporal_match_method": "exact_date"}}]}
        items = recall_partitions_to_items(partition, role_source_type="memory_context")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].source_type, "memory_context")
        self.assertTrue(items[0].temporal_provenance["confirmed"])

    def test_semantic_method_is_not_confirmed(self):
        partition = {"daily": [{"id": "m2", "content": "y",
                                "metadata": {"temporal_match_method": "semantic"}}]}
        items = recall_partitions_to_items(partition, role_source_type="memory_context")
        self.assertFalse(items[0].temporal_provenance["confirmed"])
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m unittest tests.test_recall_partitions_to_items -v`
Expected: FAIL — `cannot import name 'recall_partitions_to_items'`.

- [ ] **Step 3: Extract to module level**

Lift the `_partition_rows` + `_items_for` logic from inside `_dispatcher_recall_adapters` (brain_loop.py ~360) to a module-level function (preserving the exact `confirmed = method in ("exact_date","month_window")` rule and `sanitize_prompt_text`):

```python
def recall_partitions_to_items(partition: dict, *, role_source_type: str) -> tuple["RecallItem", ...]:
    from core import llm_client as _llm_client
    rows: list[dict] = []
    for tier in ("core", "daily", "raw"):
        rows.extend((partition or {}).get(tier, []) or [])
    items = []
    for row in rows:
        meta = row.get("metadata") or {}
        method = meta.get("temporal_match_method")
        temporal_provenance = (
            {"method": method, "confirmed": method in ("exact_date", "month_window")}
            if method else None
        )
        text = _llm_client.sanitize_prompt_text(str(row.get("content") or ""))
        items.append(RecallItem(text=text, source_type=role_source_type,
                                durable_id=str(row.get("id") or "") or None,
                                temporal_provenance=temporal_provenance))
    return tuple(items)
```

Then refactor the in-closure `_items_for`/`_combined_context_items` to call `recall_partitions_to_items` (no behavior change — the closures become thin wrappers).

- [ ] **Step 4: Run to verify it passes + no regression**

Run: `.venv/bin/python -m unittest tests.test_recall_partitions_to_items tests.test_living_recall tests.test_dispatcher_layer1 -v`
Expected: PASS (the live adapter behavior is unchanged — existing suites green).

- [ ] **Step 5: Commit**

```bash
git add core/brain/brain_loop.py tests/test_recall_partitions_to_items.py
git commit -m "refactor(recall): extract recall_partitions_to_items (shared confirmed-provenance for shadow)"
```

---

## Task 4: Daemon — bounded shadow worker + read-only run + paired logging

**Files:**
- Modify: `daemon/maez_daemon.py`
- Test: `tests/test_memory_integrity_invariant.py` (new methods in the harness-hosting class)

- [ ] **Step 1: Write the failing daemon-shaped tests**

Add to the harness-hosting class (reuse `_build_daemon_for_handle_message` / `_handle_message_mock_stack`), real bodies (no skeletons):

```python
    def _shadow_lines(self, logs):
        return [ln for ln in logs.output if "shadow_outcome" in ln or "shadow_skipped" in ln]

    def test_shadow_off_by_default_emits_no_shadow_row(self):
        captured = {}
        daemon = self._build_daemon_for_handle_message()
        with self.assertLogs("maez", level="INFO") as logs:
            with self._handle_message_mock_stack(maez_daemon, captured), mock.patch.dict(
                os.environ, {}, clear=False
            ):
                os.environ.pop("MAEZ_RECALL_SHADOW_ENABLED", None)
                maez_daemon.MaezDaemon.handle_message(
                    daemon, "what did we decide around April 27?",
                    chat_id="c1", user_id="u1", source="telegram")
        self.assertEqual(self._shadow_lines(logs), [])   # no shadow rows flag-off

    def test_shadow_does_not_invoke_dispatcher(self):
        # MAEZ_RECALL_SHADOW_ENABLED=1; assert _run_dispatcher_pipeline is never called.
        captured = {}
        daemon = self._build_daemon_for_handle_message()
        with mock.patch("core.brain.brain_loop._run_dispatcher_pipeline") as disp:
            with self._handle_message_mock_stack(maez_daemon, captured), mock.patch.dict(
                os.environ, {"MAEZ_RECALL_SHADOW_ENABLED": "1"}, clear=False
            ):
                os.environ.pop("MAEZ_RECALL_TRIAD_ENABLED", None)
                maez_daemon.MaezDaemon.handle_message(
                    daemon, "what did we decide around April 27?",
                    chat_id="c1", user_id="u1", source="telegram")
                # shadow runs on a worker; drain it (see Step 3 for the test hook)
                daemon._shadow_worker_join_for_test(timeout=2.0)
        disp.assert_not_called()

    def test_shadow_leaves_last_recall_receipt_unchanged(self):
        captured = {}
        daemon = self._build_daemon_for_handle_message()
        daemon._last_recall_receipt = "SENTINEL"
        with self._handle_message_mock_stack(maez_daemon, captured), mock.patch.dict(
            os.environ, {"MAEZ_RECALL_SHADOW_ENABLED": "1"}, clear=False
        ):
            os.environ.pop("MAEZ_RECALL_TRIAD_ENABLED", None)
            maez_daemon.MaezDaemon.handle_message(
                daemon, "what did we decide around April 27?",
                chat_id="c1", user_id="u1", source="telegram")
            daemon._shadow_worker_join_for_test(timeout=2.0)
        self.assertEqual(daemon._last_recall_receipt, "SENTINEL")  # unchanged

    def test_live_recall_outcome_emits_shadow_pair_id(self):
        captured = {}
        daemon = self._build_daemon_for_handle_message()
        with self.assertLogs("maez", level="INFO") as logs:
            with self._handle_message_mock_stack(maez_daemon, captured), mock.patch.dict(
                os.environ, {}, clear=False
            ):
                maez_daemon.MaezDaemon.handle_message(
                    daemon, "what did we decide around April 27?",
                    chat_id="c1", user_id="u1", source="telegram")
        outcome = [ln for ln in logs.output if "recall_outcome " in ln][-1]
        self.assertIn("shadow_pair_id=", outcome)
        # content-free: the raw trace id must not appear on the shadow-adjacent fields
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/bin/python -m unittest tests.test_memory_integrity_invariant -v -k shadow`
Expected: FAIL.

- [ ] **Step 3: Implement the worker + flag + run + pairing**

In `daemon/maez_daemon.py`:

(a) Flag reader + `shadow_pair_id` helper near `_recall_status_intercept_enabled`:
```python
def _recall_shadow_enabled() -> bool:
    return (os.environ.get("MAEZ_RECALL_SHADOW_ENABLED", "") or "").strip().lower() in {"1", "true", "yes"}
```

(b) `MaezDaemon.__init__`: add a bounded single-worker executor mirroring the existing `_dream_worker`/`_presence_worker` pattern (a singleton worker whose `submit()` refuses when busy → `queue_full`). Add a `_shadow_worker_join_for_test(timeout)` that joins/drains the worker (test-only synchronization).

(c) On the live `recall_outcome` emit (Task-1a site, ~4612+): compute `shadow_pair_id = compute_shadow_pair_id(boot_id=str(self.boot_time or ""), trace_id=getattr(_trace, "trace_id", "") or "")` and add `shadow_pair_id=%s` to `_log_recall_outcome` (extend `RecallOutcome` with a `shadow_pair_id` field OR log it alongside — prefer adding the field so it's part of the content-free schema, and update the 1a content-free test forbidden-set check still passes since it's a derived hex, not content).

(d) After the reply is committed (the trace is written ~4910, before `return reply` ~4931): if `_recall_shadow_enabled()` and the turn is recall-relevant and the triad is off, snapshot `(text, legacy RecallOutcome fields, shadow_pair_id, str(self.boot_time))` and `submit` the shadow job to `_shadow_worker`. If submit refuses (busy), `logger.info("shadow_skipped reason=queue_full")`. Do NOT block; `return reply` proceeds immediately.

(e) The shadow job (runs on the worker):
```python
def _run_recall_shadow(self, *, text, legacy_outcome, legacy_is_false_absence,
                       legacy_was_decline, date_addressed, shadow_pair_id, boot_id):
    import time
    from core.routing.recall_shadow import (
        ShadowSkip, derive_shadow_outcome, derive_shadow_reach,
    )
    from core.routing.focused_cognition import assemble_working_set
    from core.brain.brain_loop import recall_partitions_to_items
    t0 = time.monotonic()
    try:
        evidence, context = self.memory.recall_for_telegram_living(text, record_recalls=False)
        items = (recall_partitions_to_items(evidence, role_source_type="memory_evidence")
                 + recall_partitions_to_items(context, role_source_type="memory_context"))
        ws = assemble_working_set(transcript="", web_context="", owner_question=text,
                                  recall_items=items)
        reach = derive_shadow_reach(ws, date_addressed=date_addressed)
        rec = derive_shadow_outcome(
            legacy_outcome=legacy_outcome, legacy_is_false_absence=legacy_is_false_absence,
            shadow_reach=reach, legacy_was_decline=legacy_was_decline,
            date_addressed=date_addressed,
            shadow_pair_id=shadow_pair_id,
            latency_delta_ms=int((time.monotonic() - t0) * 1000),
            ts=int(time.time()), boot_id=boot_id)
        _log_shadow_outcome(rec=rec)
    except Exception as exc:
        logger.info("shadow_skipped reason=%s error_class=%s",
                    ShadowSkip.EXCEPTION.value, type(exc).__name__)
```

Add `_log_shadow_outcome` (content-free, mirrors `_log_recall_outcome`, emits enum `.value`s + `shadow_pair_id` + ts/boot_id, NEVER text). The `legacy_was_decline` flag = legacy outcome_class in the declined_* family (compute at snapshot). **Note on the marker-producer check (spec, load-bearing):** verify a known dated memory yields `grounded_material_available` here — if `recall_for_telegram_living` partitions carry `temporal_match_method`, `recall_partitions_to_items` sets `confirmed`, and `assemble_working_set` preserves it via `recall_items`. The dated-fixture test in Step 1 (extend it) must prove this end-to-end; if it shows `carrier_unavailable` on a known dated memory, the partition→items shape is wrong and must be fixed before landing.

- [ ] **Step 4: Run to verify they pass**

Run: `.venv/bin/python -m unittest tests.test_memory_integrity_invariant -v -k shadow`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add daemon/maez_daemon.py core/routing/recall_outcome.py tests/test_memory_integrity_invariant.py
git commit -m "feat(recall): bounded shadow worker — read-only assemble-only second opinion, paired + off critical path"
```

---

## Task 5: Per-substrate non-disturbance + off-critical-path tests

**Files:**
- Modify: `tests/test_memory_integrity_invariant.py`

- [ ] **Step 1: Write the tests**

Add, each asserting one substrate is untouched by a shadow run (flag on, triad off, dated turn, worker drained):
- `focused_cognition_runs` row count unchanged (mock/spy `record_focused_cognition_run` → assert not called).
- promotion / `record_recall` not called (assert `recall_for_telegram_living` invoked with `record_recalls=False`).
- no egress (spy the external fetch / `external_fanout` entrypoint → assert not called).
- layer0 cache file mtime unchanged.
- `_run_dispatcher_pipeline` not called (Task 4 covered; keep).
- `queue_full`: submit two shadow jobs back-to-back with the worker held busy → second logs `shadow_skipped reason=queue_full`.
- **off-critical-path:** patch the shadow job to sleep; assert `handle_message` returns (time-to-return) without waiting for the sleep (the reply is not delayed by the shadow).

```python
    def test_shadow_does_not_delay_reply(self):
        import time as _t
        captured = {}
        daemon = self._build_daemon_for_handle_message()
        with mock.patch.object(daemon, "_run_recall_shadow",
                               side_effect=lambda **k: _t.sleep(1.0)):
            with self._handle_message_mock_stack(maez_daemon, captured), mock.patch.dict(
                os.environ, {"MAEZ_RECALL_SHADOW_ENABLED": "1"}, clear=False
            ):
                os.environ.pop("MAEZ_RECALL_TRIAD_ENABLED", None)
                start = _t.monotonic()
                maez_daemon.MaezDaemon.handle_message(
                    daemon, "what did we decide around April 27?",
                    chat_id="c1", user_id="u1", source="telegram")
                elapsed = _t.monotonic() - start
        self.assertLess(elapsed, 0.5)   # reply returned without waiting for the 1s shadow
        daemon._shadow_worker_join_for_test(timeout=3.0)
```

- [ ] **Step 2: Run → implement any missing spy hooks → pass**

Run: `.venv/bin/python -m unittest tests.test_memory_integrity_invariant -v -k shadow`
Expected: PASS (add minimal seams if a substrate isn't observable — e.g. ensure the shadow calls go through patchable module attributes).

- [ ] **Step 3: Commit**

```bash
git add tests/test_memory_integrity_invariant.py daemon/maez_daemon.py
git commit -m "test(recall): shadow per-substrate non-disturbance + off-critical-path + queue_full"
```

---

## Task 6: Speakable shadow-active state

**Files:**
- Modify: `core/routing/recall_self_status.py`, `daemon/maez_daemon.py` (self-status branch), tests.

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_recall_self_status.py
from core.routing.recall_self_status import is_recall_practice_query, build_recall_practice_reply


class PracticeStatusTest(unittest.TestCase):
    def test_practice_query_matches(self):
        for q in ("are you practicing recall quietly?",
                  "are you running anything in the background?"):
            self.assertTrue(is_recall_practice_query(q), q)
    def test_ordinary_not_matched(self):
        for q in ("what did we decide on April 27?", "is your dated recall reachable?"):
            self.assertFalse(is_recall_practice_query(q), q)
    def test_reply_reflects_shadow_state(self):
        on, _ = build_recall_practice_reply(shadow_enabled=True, ran_recently=True)
        self.assertIn("quietly", on.lower())
        off, _ = build_recall_practice_reply(shadow_enabled=False, ran_recently=False)
        self.assertNotIn("quietly practicing", off.lower())
```

- [ ] **Step 2: Run → fails → implement**

Add `is_recall_practice_query` (narrow, hard-FP boundary — must NOT match the 1a reachability query or ordinary dated queries) + `build_recall_practice_reply(shadow_enabled, ran_recently)` (event-shaped, faculty-language, genderless, never auto-volunteered). Wire into the daemon self-status branch (gated like 1a self-status; reads `_recall_shadow_enabled()` + a content-free "shadow ran since boot" flag). Run → PASS.

- [ ] **Step 3: Commit**

```bash
git add core/routing/recall_self_status.py daemon/maez_daemon.py tests/test_recall_self_status.py
git commit -m "feat(recall): speakable shadow-active self-status (event-shaped, on-demand)"
```

---

## Task 7: Regression sweep + guards

- [ ] **Step 1: Single-source + content-free guards**

Run: `.venv/bin/python -m unittest tests.test_recall_flag_single_source tests.test_recall_shadow tests.test_recall_outcome -v`
Expected: PASS. `MAEZ_RECALL_SHADOW_ENABLED` is a new flag (not one of the 3 raw recall flags), so the single-source guard is unaffected.

- [ ] **Step 2: Full targeted regression + ruff**

Run: `.venv/bin/python -m unittest tests.test_recall_shadow tests.test_recall_outcome tests.test_recall_self_status tests.test_recall_partitions_to_items tests.test_memory_integrity_invariant tests.test_focused_cognition tests.test_living_recall tests.test_recall_stack_config -v 2>&1 | tail -6`
Expected: all green. `.venv/bin/ruff check core/routing/recall_shadow.py core/routing/recall_outcome.py core/brain/brain_loop.py daemon/maez_daemon.py core/routing/recall_self_status.py` → All checks passed.
(Note the known `test_temporal_recall_fragment_guard` 5-failure worktree-env artifact — confirm it is unchanged, not newly broken.)

- [ ] **Step 3: Commit**

```bash
git add -p   # scoped staging; NOT git add -A
git commit -m "test(recall): slice 1b regression sweep green"
```

---

## Self-Review

**1. Spec coverage:**
- Read-only via `recall_for_telegram_living(record_recalls=False)` + reused `recall_partitions_to_items` + `assemble_working_set`; dispatcher forbidden (test) → Tasks 3, 4. ✓
- Assemble-only honest vocabulary (`ShadowReach`, `grounded_material_available`, `rescuable_candidate`) + `legacy_false_absence_rescuable` reusing `is_false_absence`; false-absence gated to dated frames only → Task 2. ✓
- Off-critical-path bounded single-worker + `queue_full`/`budget_exceeded`/`exception` closed reasons; no rows for flag-off/non-recall → Tasks 4, 5. ✓
- Side-effect-free per-substrate (focused_cognition_runs, `_last_recall_receipt`, promotion, egress, layer0, dispatcher) → Tasks 4, 5. ✓
- `shadow_pair_id` derived (not raw trace_id), non-authoritative, content-free; live `recall_outcome` also emits it → Tasks 2, 4. ✓
- Speakable shadow-active state → Task 6. ✓
- ReplyPath hardening → Task 1. ✓
- Content-free + closed-enum by test → Tasks 2, 5. ✓
- Marker-producer check (dated memory → grounded_material_available end-to-end) → Task 4 Step 3 note + fixture test. ✓
- Sunset + pre-flip blocking gate → **enforced at Phase-2** (defined in spec), not 1b code. ✓

**2. Placeholder scan:** Tasks 1, 2, 3, 6 contain complete code/tests. Task 4's worker construction + the post-reply snapshot site reference the daemon's existing bounded-worker pattern (`_dream_worker`/`_presence_worker`) and the 1a recall_outcome emit site — the implementer matches those existing names; the daemon-shaped tests pin the observable contract (no-dispatcher, receipt-unchanged, pair-id-on-live-row, no-delay, queue_full). Flagged honestly: the exact worker class + the snapshot insertion line are integration points matched to existing daemon idioms, not undefined logic.

**3. Type/symbol consistency:** `ShadowReach`, `ShadowSkip`, `ShadowOutcome`, `compute_shadow_pair_id`, `derive_shadow_reach`, `derive_shadow_outcome`, `recall_partitions_to_items`, `reply_path_from_mode` used identically across tasks; `OutcomeClass`/`is_false_absence` reused from 1a; `date_addressed` gates the dated false-absence metric; `shadow_pair_id` derivation identical on live + shadow rows (same `boot_id`+`trace_id`).

**4. Ordering:** ReplyPath hardening (1) → pure shadow module (2) → shared conversion extract (3) → daemon worker + run + pairing (4) → non-disturbance/off-path tests (5) → speakable state (6) → regression (7). Pure/shared code before daemon wiring; each task independently committable and green.

## Execution note
Task 4 touches `handle_message` after the reply-commit point (~4910, before `return reply` ~4931) and `__init__` (the worker). Read the existing `_dream_worker`/`_presence_worker` bounded-singleton pattern (~daemon lines 1886, 2324, 6945-6956) and mirror it for `_shadow_worker`; match the 1a `recall_outcome` emit site for the `shadow_pair_id` addition. Do not introduce parallel worker state.
