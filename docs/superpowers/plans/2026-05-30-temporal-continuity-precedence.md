# Temporal–Continuity Precedence (B-lite) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When a question carries an explicit temporal address ("around April 27", "last month"), make temporal recall the primary frame; the dialogue anchor may appear only as a secondary, lower-ranked item and can never replace, outrank, or answer for the dated frame — and when no dated memory matches, never fall back to the dialogue anchor (or legacy chat synthesis) for the answer.

**Architecture:** A single shared predicate `has_absolute_recall_cue()` (single source of truth) lives in a new lightweight module `core/routing/temporal_cue.py` (the absolute-date window + helpers move there from `memory_manager`). Two boundaries consult it: the brain_loop adapter stops firing the dialogue-anchor evidence override on date-cued turns (and does NOT inject the anchor); `assemble_working_set` stops going dialogue-authoritative on date-cued turns, ranks any dialogue anchor strictly below temporal items, and — when no temporal/fallback items exist — emits a `temporal_recall_status` working-set item so focused cognition answers honestly instead of returning `None` (which would let the daemon fall through to legacy chat synthesis).

**Tech Stack:** Python 3, `unittest` (pytest NOT installed — `.venv/bin/python -m unittest`), `ruff`.

**BINDING RULE (Rohit, verbatim):** *"Explicit temporal address creates the primary recall frame. Dialogue anchor may be included only as secondary context and must never replace, outrank, or answer for the dated frame. If no dated match exists, do not fall back to dialogue as the answer."*

**HARD CONSTRAINTS:** precedence-only — no memory-ranker / recency-salience changes, no renderer changes, no memory-write changes, no new flag; `_temporal_telegram_age_window` (relative-conversational) untouched; brain-swap-safe; the `temporal_cue` move is mechanical (no logic change).

---

## File map
- **Create** `core/routing/temporal_cue.py` — moved `AbsoluteRecallWindow`, `_absolute_date_window`, helpers; new `has_absolute_recall_cue()`.
- **Modify** `memory/memory_manager.py` — delete the moved symbols, re-import them from `temporal_cue`.
- **Modify** `core/brain/brain_loop.py` — `_living_memory_manager_adapter` date-cue precedence.
- **Modify** `core/routing/focused_cognition.py` — `assemble_working_set` date-cue precedence + `_ranked_items_for_state` date-present mode + `temporal_recall_status` item.
- **Tests** `tests/test_memory_manager.py`, `tests/test_focused_cognition.py`, `tests/test_living_recall.py`.

---

## Task 1: Extract the shared predicate to `core/routing/temporal_cue.py`

**Files:** Create `core/routing/temporal_cue.py`; Modify `memory/memory_manager.py`. Test: `tests/test_memory_manager.py`.

- [ ] **Step 1: Write the failing parity test**

Add to `tests/test_memory_manager.py`:
```python
class HasAbsoluteRecallCueParityTests(unittest.TestCase):
    def _now(self):
        from datetime import datetime
        from core.time.temporal_spine import owner_timezone
        return datetime(2026, 5, 30, 12, 0, tzinfo=owner_timezone())

    def test_predicate_matches_window_resolver(self):
        from core.routing.temporal_cue import (
            has_absolute_recall_cue,
            _absolute_date_window,
        )
        now = self._now()
        battery = [
            "what did we note around April 27 about infra?",
            "remind me what we were doing around April 27",
            "what were we working on last month?",
            "2026-04-06 infra note",
            "what about May 6?",
            "what were we just talking about?",      # no date
            "how are you?",                           # no date
            "maybe we should check the logs",         # bare 'may' guard
        ]
        for q in battery:
            with self.subTest(q=q):
                self.assertEqual(
                    has_absolute_recall_cue(q, now),
                    _absolute_date_window(q, now) is not None,
                )

    def test_memory_manager_reimports_resolver(self):
        # import-move smoke: memory_manager still exposes the resolver it uses
        from memory.memory_manager import _absolute_date_window as mm_resolver
        from core.routing.temporal_cue import _absolute_date_window as tc_resolver
        self.assertIs(mm_resolver, tc_resolver)
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m unittest tests.test_memory_manager.HasAbsoluteRecallCueParityTests -v`
Expected: FAIL — `No module named 'core.routing.temporal_cue'`.

- [ ] **Step 3: Create `core/routing/temporal_cue.py`**

Create the file with this header, then **move verbatim** from `memory/memory_manager.py` these symbols (currently at ~lines 705–800): `_NIGHTLY_FWD_TOL_DAYS`, `_MONTH_NAMES` (and its build loop), `AbsoluteRecallWindow`, `_owner_local_to_utc`, `_day_bounds_local`, `_most_recent_year_for`, `_exact_window`, `_month_window`, `_absolute_date_window`. Then add `has_absolute_recall_cue`:
```python
"""Absolute-date recall cue detection — single source of truth.

Lightweight (depends only on core.time.temporal_spine) so memory_manager,
brain_loop, and focused_cognition can all share one predicate without heavy or
circular imports. The recall LOGIC (filtering Chroma tiers) stays in
memory_manager; only the cue/window detection lives here.
"""
import calendar
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from core.time.temporal_spine import owner_timezone

# <<< moved verbatim: _NIGHTLY_FWD_TOL_DAYS, _MONTH_NAMES (+ loop),
#     AbsoluteRecallWindow, _owner_local_to_utc, _day_bounds_local,
#     _most_recent_year_for, _exact_window, _month_window, _absolute_date_window >>>


def has_absolute_recall_cue(question: str, now_local: datetime | None = None) -> bool:
    """True iff the question names an explicit absolute date/month address.

    Shares the same now_local test seam as _absolute_date_window so parity
    tests are deterministic (independent of wall-clock date)."""
    return _absolute_date_window(question, now_local) is not None
```

- [ ] **Step 4: Re-import in `memory/memory_manager.py`**

Delete the moved symbols from `memory/memory_manager.py`. Add an import near the top (after the `owner_timezone` import, ~line 25):
```python
from core.routing.temporal_cue import (
    AbsoluteRecallWindow,
    _absolute_date_window,
    _MONTH_NAMES,
)
```
(`memory_manager` still uses `AbsoluteRecallWindow` in `_absolute_date_recall`/`_row_in_window`/`_tag_temporal_rows` type hints, `_absolute_date_window` in `recall_for_telegram_living`, and `_MONTH_NAMES` in `_temporal_topic_signal`. Confirm `calendar`/`re`/`timedelta`/`timezone` are still imported in `memory_manager` for its remaining code — they are. Watch for a circular import: `temporal_cue` imports only `core.time.temporal_spine`, so `memory_manager` → `temporal_cue` is clean.)

- [ ] **Step 5: Run to verify pass + no resolver regression**

Run: `.venv/bin/python -m unittest tests.test_memory_manager.HasAbsoluteRecallCueParityTests tests.test_memory_manager.AbsoluteDateWindowTests tests.test_memory_manager.AbsoluteDateRecallTests -v`
Expected: PASS (parity + the moved resolver's existing tests still green from their new home).

- [ ] **Step 6: Commit**
```bash
git add core/routing/temporal_cue.py memory/memory_manager.py tests/test_memory_manager.py
git commit -m "refactor(recall): extract absolute-date cue/window to core/routing/temporal_cue + has_absolute_recall_cue (single source of truth)"
```

---

## Task 2: `assemble_working_set` date-cue precedence + `_ranked_items_for_state` + status item

**Files:** Modify `core/routing/focused_cognition.py`. Test: `tests/test_focused_cognition.py`.

- [ ] **Step 1: Write the failing tests**

Add a class to `tests/test_focused_cognition.py`:
```python
class TemporalContinuityPrecedenceTests(unittest.TestCase):
    def _history(self):
        # one cleaned exchange so dialogue_anchor_items can build an anchor
        return [{"content": "Rohit: What about January 3?\nMaez: I have no record of January 3."}]

    def test_date_cue_keeps_temporal_primary_anchor_secondary(self):
        from core.routing.focused_cognition import assemble_working_set
        transcript = (
            "[memory context]\n"
            '<RECALLED tier="core" age="permanent" id="c1" date_match="exact_date">\n'
            "infrastructure ground-truth fabrication-class incident\n"
            "</RECALLED>"
        )
        ws = assemble_working_set(
            transcript=transcript, web_context="",
            owner_question="remind me what we were doing around April 27",
            chat_history=self._history(),
        )
        self.assertIsNotNone(ws)
        # primary (first) item is temporal context, not the dialogue anchor
        self.assertEqual(ws.items[0].source_type, "memory_context")
        # if the anchor is present at all, it is NOT [E1] and ranks below temporal
        anchor_items = [it for it in ws.items if it.source_type == "dialogue_anchor"]
        for a in anchor_items:
            self.assertNotEqual(a.local_label, "E1")

    def test_date_cue_no_match_emits_status_not_anchor(self):
        from core.routing.focused_cognition import assemble_working_set
        # explicit date cue, but transcript has NO memory context (no dated match)
        ws = assemble_working_set(
            transcript="", web_context="",
            owner_question="what about January 3?",
            chat_history=self._history(),
        )
        self.assertIsNotNone(ws)  # must NOT return None (no legacy fallback)
        self.assertTrue(any(it.source_type == "temporal_recall_status" for it in ws.items))
        self.assertFalse(any(it.source_type == "dialogue_anchor" for it in ws.items))

    def test_plain_continuity_still_dialogue_authoritative(self):
        from core.routing.focused_cognition import assemble_working_set
        ws = assemble_working_set(
            transcript="", web_context="",
            owner_question="what were we just talking about?",
            chat_history=self._history(),
        )
        self.assertIsNotNone(ws)
        self.assertEqual(ws.items[0].source_type, "dialogue_anchor")
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/bin/python -m unittest tests.test_focused_cognition.TemporalContinuityPrecedenceTests -v`
Expected: FAIL — date-cued query currently goes dialogue-authoritative (anchor is `[E1]`) / returns None for the no-match case.

- [ ] **Step 3: Add the import + status source-type**

In `core/routing/focused_cognition.py`, near the other imports:
```python
from core.routing.temporal_cue import has_absolute_recall_cue
```

- [ ] **Step 4: Add `date_cue` mode to `_ranked_items_for_state`**

Replace the signature and body of `_ranked_items_for_state` (currently `(raw_items, dialogue_state)`):
```python
def _ranked_items_for_state(
    raw_items: list[tuple[str, str, str | None]],
    dialogue_state: DialogueContinuityState,
    date_cue: bool = False,
) -> list[tuple[str, str, str | None]]:
    def rank(item: tuple[str, str, str | None]) -> int:
        source_type = item[0]
        if date_cue:
            # explicit temporal address: temporal/context primary, anchor strictly below
            if source_type == "dialogue_anchor":
                return 50
            if source_type == "temporal_recall_status":
                return 60
            return _PRIORITY.get(source_type, 9)
        if (
            dialogue_state.kind == ContinuityKind.DIRECT
            or dialogue_state.fail_safe_legacy
        ):
            if source_type == "dialogue_anchor":
                return 0
            return _PRIORITY.get(source_type, 9) + 1
        if dialogue_state.kind == ContinuityKind.ANAPHORIC:
            if source_type == "dialogue_anchor":
                return 3
            return _PRIORITY.get(source_type, 9)
        return _PRIORITY.get(source_type, 9)

    return sorted(raw_items, key=rank)
```

- [ ] **Step 5: Add date-cue precedence to `assemble_working_set`**

In `assemble_working_set`, right after `dialogue_state = dialogue_continuity_state(owner_question)`:
```python
    date_cue = has_absolute_recall_cue(owner_question)
```
Change `dialogue_authoritative` so a date cue suppresses it:
```python
    dialogue_authoritative = (
        dialogue_state.kind in (ContinuityKind.DIRECT, ContinuityKind.ANAPHORIC)
        and not date_cue
    )
```
Build anchors when a date cue is present too (as a secondary, capped to one):
```python
    anchors = (
        dialogue_anchor_items(chat_history)
        if (dialogue_state.needs_dialogue or dialogue_state.fail_safe_legacy or date_cue)
        else []
    )
    if dialogue_authoritative or date_cue:
        anchors = anchors[:1]
```
Guard the two early `return None` exits so a date cue never returns None (it must yield at least a status item):
```python
    if (dialogue_state.needs_dialogue or dialogue_state.fail_safe_legacy) and not anchors and not date_cue:
        return None
    if not state.evidence_present and not anchors and not date_cue:
        return None
```
After the `raw_items` are gathered (transcript blocks + web + anchors) and BEFORE `if not raw_items: return None`, insert the no-dated-match handling:
```python
    if date_cue:
        non_anchor = [it for it in raw_items if it[0] != "dialogue_anchor"]
        if not non_anchor:
            # no temporal/fallback context matched the date → the anchor must not
            # answer; emit an honest status item instead of falling back.
            raw_items = [
                ("temporal_recall_status",
                 "No dated memory matched the explicit date cue in the question.",
                 None)
            ]
```
Pass `date_cue` into the ranker:
```python
    raw_items = _ranked_items_for_state(raw_items, dialogue_state, date_cue)
```

- [ ] **Step 6: Run to verify pass**

Run: `.venv/bin/python -m unittest tests.test_focused_cognition.TemporalContinuityPrecedenceTests -v`
Expected: PASS (3 tests).

- [ ] **Step 7: Full focused suite (no regression)**

Run: `.venv/bin/python -m unittest tests.test_focused_cognition -v`
Expected: OK (DialogueContinuityStateTests, AssembleWorkingSetTests, TrustTierRenderingTests, DialogueAwareAssembleTests all green).

- [ ] **Step 8: Commit**
```bash
git add core/routing/focused_cognition.py tests/test_focused_cognition.py
git commit -m "fix(focused): date cue makes temporal primary; anchor secondary; no-dated-match emits honest status (no legacy fallback)"
```

---

## Task 3: Adapter precedence — no anchor override / injection on date-cued turns

**Files:** Modify `core/brain/brain_loop.py` (`_living_memory_manager_adapter`). Test: `tests/test_living_recall.py`.

- [ ] **Step 1: Write the failing in-process test**

Add to `tests/test_living_recall.py` (mirror the existing in-process adapter tests; seed an April-dated core row via `_manager`, supply chat_history so the anchor would otherwise fire):
```python
    def test_date_cue_adapter_does_not_inject_dialogue_anchor(self):
        import os
        from core import brain_loop
        os.environ["MAEZ_LIVING_RECALL_ENABLED"] = "1"
        try:
            april = {
                "id": "core-apr", "distance": 0.02,
                "content": "[Journal 2026-04-06] infrastructure ground-truth fabrication-class incident.",
                "metadata": {"type": "core_memory", "source": "nightly_journal",
                             "timestamp": "2026-04-07T04:00:02+00:00"},
            }
            mm = _manager(core_rows=[april])
            spec = _substrate_semantic_spec()
            with (
                mock.patch("core.brain.brain_loop._dispatcher_memory_manager", return_value=mm),
                mock.patch("memory.memory_manager._now_seconds",
                           return_value=datetime(2026, 5, 29, 12, 0, tzinfo=timezone.utc).timestamp()),
            ):
                adapters = brain_loop._dispatcher_recall_adapters(
                    "remind me what we were doing around April 6",
                    spec=spec, surface="telegram_surface",
                    chat_history=[{"content": "Rohit: What about January 3?\nMaez: No record."}],
                )
                blocks = []
                for src, fn in adapters.items():
                    blocks.extend(fn(src) or [])
            text = "\n".join(b.text for b in blocks)
            # temporal memory reached the prompt; the dialogue anchor did NOT get injected by the adapter
            self.assertIn("fabrication-class", text)
            self.assertNotIn("Recent dialogue anchor", text)
        finally:
            os.environ.pop("MAEZ_LIVING_RECALL_ENABLED", None)
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m unittest tests.test_living_recall.<ClassName>.test_date_cue_adapter_does_not_inject_dialogue_anchor -v`
Expected: FAIL — the adapter currently fires `_continuity_needs_dialogue_anchor()` (DIRECT on "remind me … we were doing") and injects "Recent dialogue anchor".

- [ ] **Step 3: Implement the adapter guard**

In `core/brain/brain_loop.py`, add the import near the other focused-cognition imports:
```python
        from core.routing.temporal_cue import has_absolute_recall_cue
```
In `_living_memory_manager_adapter`, the continuity block currently reads:
```python
        anchor_active = False
        if _continuity_needs_dialogue_anchor():
            anchor = _latest_dialogue_anchor_text()
            if anchor:
                anchor_active = True
                ev_text = _bounded_text(f"Recent dialogue anchor:\n{anchor}", limit=evidence_budget)
                ctx_text = _bounded_text("\n".join(part for part in (memory_ev_text, ctx_text) if part), limit=context_budget)
```
Guard it so an explicit date cue suppresses the anchor override entirely (temporal recall, already in `ctx_text`/`ev_text` from `recall_for_telegram_living`'s date branch, stays primary; the secondary anchor is added downstream in `assemble_working_set`, not here):
```python
        anchor_active = False
        if _continuity_needs_dialogue_anchor() and not has_absolute_recall_cue(user_text):
            anchor = _latest_dialogue_anchor_text()
            if anchor:
                anchor_active = True
                ev_text = _bounded_text(f"Recent dialogue anchor:\n{anchor}", limit=evidence_budget)
                ctx_text = _bounded_text("\n".join(part for part in (memory_ev_text, ctx_text) if part), limit=context_budget)
```
(Confirm `user_text` is the in-scope owner-question variable at this site — it is, per `_continuity_needs_dialogue_anchor` calling `dialogue_continuity_state(user_text)`.)

- [ ] **Step 4: Run to verify pass**

Run: `.venv/bin/python -m unittest tests.test_living_recall.<ClassName>.test_date_cue_adapter_does_not_inject_dialogue_anchor -v`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add core/brain/brain_loop.py tests/test_living_recall.py
git commit -m "fix(brain_loop): date cue suppresses dialogue-anchor override in living adapter (temporal stays primary)"
```

---

## Task 4: Integration-path test — both-shaped query → temporal primary to `assemble_working_set`

**Files:** Test: `tests/test_living_recall.py`.

- [ ] **Step 1: Write the in-process production-path test** (mirror `test_absolute_date_label_survives_to_working_set`; same `_manager` seed + dispatcher→merge→assemble path):
```python
    def test_both_shaped_query_temporal_primary_end_to_end(self):
        import os, time
        from core import brain_loop
        from core.dispatcher.external_sources import ExternalFanout
        from core.dispatcher.layer1 import Layer1Fanout
        from core.dispatcher.merge import merge_fanout_results
        from core.routing.focused_cognition import assemble_working_set
        os.environ["MAEZ_LIVING_RECALL_ENABLED"] = "1"
        try:
            april = {
                "id": "core-apr", "distance": 0.02,
                "content": "[Journal 2026-04-06] infrastructure ground-truth fabrication-class incident.",
                "metadata": {"type": "core_memory", "source": "nightly_journal",
                             "timestamp": "2026-04-07T04:00:02+00:00"},
            }
            mm = _manager(core_rows=[april])
            spec = _substrate_semantic_spec()
            q = "remind me what we were doing around April 6"
            with (
                mock.patch("core.brain.brain_loop._dispatcher_memory_manager", return_value=mm),
                mock.patch("memory.memory_manager._now_seconds",
                           return_value=datetime(2026, 5, 29, 12, 0, tzinfo=timezone.utc).timestamp()),
            ):
                l1 = Layer1Fanout(
                    adapters=brain_loop._dispatcher_recall_adapters(
                        q, spec=spec, surface="telegram_surface",
                        chat_history=[{"content": "Rohit: What about January 3?\nMaez: No record."}]),
                    branch_timeout_s=1.0, global_deadline_s=1.0,
                ).run(spec, utterance=q, conversation_state={"surface": "telegram_surface"},
                      fanout_generation_id="prec")
                ext = ExternalFanout().run(spec, utterance=q,
                      conversation_state={"surface": "telegram_surface"}, fanout_generation_id="prec")
                rendered = merge_fanout_results(spec, l1, ext, utterance=q,
                      surface="telegram_surface", timestamp="2026-05-29T12:00:00Z")
            tx = rendered.prompt_block
            ws = assemble_working_set(transcript=tx, web_context="", owner_question=q,
                                      chat_history=[{"content": "Rohit: What about January 3?\nMaez: No record."}])
            self.assertIsNotNone(ws)
            self.assertEqual(ws.items[0].source_type, "memory_context")     # temporal primary
            self.assertTrue(any("fabrication-class" in it.text for it in ws.items))
            for it in ws.items:
                if it.source_type == "dialogue_anchor":
                    self.assertNotEqual(it.local_label, "E1")                # anchor never primary
        finally:
            os.environ.pop("MAEZ_LIVING_RECALL_ENABLED", None)
```

- [ ] **Step 2: Run it** — Run: `.venv/bin/python -m unittest tests.test_living_recall.<ClassName>.test_both_shaped_query_temporal_primary_end_to_end -v` → Expected: PASS.

- [ ] **Step 3: Commit**
```bash
git add tests/test_living_recall.py
git commit -m "test(recall): both-shaped query keeps temporal primary end-to-end (dispatcher→merge→assemble)"
```

---

## Task 5: Regression + lint

- [ ] **Step 1:** `.venv/bin/python -m unittest tests.test_memory_manager tests.test_focused_cognition tests.test_living_recall -v` → Expected: OK (no regression in the triad's existing tests).
- [ ] **Step 2:** `.venv/bin/ruff check core/routing/temporal_cue.py core/routing/focused_cognition.py core/brain/brain_loop.py memory/memory_manager.py` → Expected: clean.
- [ ] **Step 3:** Broad floor is env-noisy; if run, confirm only the documented pre-existing failures (`test_web_search_direct_caller_inventory_is_stable`, `test_owner_bridge_chat_uses_envelope_prompt_block_and_recall_cap`, and the ordering-flaky `test_service_audit_behavior_records_cloud_retirement_without_raw_text`). Report honestly; do not claim broad green.

---

## Witness (Claude, after Task 1–5 green): RE-RUN THE TRIAD WITNESS
Flag-on Telegram, the composed battery, with the interaction probe as the graduation gate:
1. "remind me what we were doing around April 27" → recaps the **April-27** record (temporal primary); recent thread may appear only as a labeled secondary; **NOT** the prior turn's "January 3 / no record".
2. An explicit date with no memory ("what about January 3?") → honest "no dated record", not a dialogue stand-in (and not legacy chat synthesis).
3. "what were we just talking about?" (no date) → still recaps the recent thread (no regression).
4. Plain temporal + plain recency/continuity → all still green.
Green → the triad graduates (eligible for an explicit default-on decision — separate step, Rohit's call). Red → split per the "no sixth fixture pass" rule.

---

## Self-Review
**Spec coverage:** shared predicate in neutral module + now_local seam (Task 1) = spec §1 ✓. Adapter stops override + does NOT inject anchor, even when temporal empty (Task 3) = spec §2 ✓. assemble not dialogue-authoritative on date cue, anchor ranked below temporal, retrieval-status item instead of None, semantic_fallback allowed as context (Task 2) = spec §3,4 ✓. Integration-path temporal-primary (Task 4) + RED battery incl. predicate parity (Tasks 1–2) = spec RED tests ✓. Re-run triad witness = spec witness ✓.
**Placeholder scan:** none — every code step shows real code; the Task 1 move lists exact symbols to relocate verbatim + shows the new `has_absolute_recall_cue` + the import line.
**Type consistency:** `has_absolute_recall_cue(question, now_local=None)` signature matches the parity test and both call sites; `_ranked_items_for_state(raw_items, dialogue_state, date_cue=False)` matches its one call site; `temporal_recall_status` source-type string identical across assemble (write) and the RED test (read); `AbsoluteRecallWindow`/`_absolute_date_window`/`_MONTH_NAMES` re-import names match memory_manager's remaining usages.
