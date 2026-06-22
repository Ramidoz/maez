# Coherence Core Pair — Recall Floor (Slice 2) + Live-Thread Anchor (Slice 3) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop weak/recent self-history from flooding ordinary turns (Slice 2 = recall relevance floor) and put the live conversation back as the figure (Slice 3 = always-on dialogue anchor), so casual turns stop diary-reciting and "Sure"/"proceed" resolve — measured by the `reply_grounding` meter.

**Architecture:** Two separable slices behind their own flags, shadow-first. Slice 3 (`focused_cognition.py` ranking + anchor gate) ships first so the live thread is present; then Slice 2 (`memory_manager.py` recall floor) empties the diary flood with the anchor ready to catch it. Both default-off = byte-identical.

**Tech Stack:** Python 3, `unittest` (NOT pytest), the `focused_cognition` / `memory_manager` modules, `core/infra/env_flags.strict_env_flag`.

**Test runner (EVERY test step):** `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.<module> -v`

**Git hygiene:** branch/worktree, NO checkout/switch/reset/rebase mid-task; verify "On branch X" after each commit; `main` local-only, NO push. Behavior commits (the flag actuations) carry `## Predicted effect`. Commits end `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

**Spec:** [docs/superpowers/specs/2026-06-22-coherence-core-pair-design.md](../specs/2026-06-22-coherence-core-pair-design.md).

---

## File Structure
- **`core/routing/focused_cognition.py`** (Slice 3) — `_PRIORITY` tiers; `_ranked_items_for_state` DIRECT-branch fresh-guard; `assemble_working_set` anchor un-gating behind a flag.
- **`memory/memory_manager.py`** (Slice 2) — `recall_for_telegram_living` relevance floor + `recall_floor_shadow` receipt + compound-teacher signal log.
- **Create `tests/test_live_thread_anchor.py`** (Slice 3) and **`tests/test_recall_floor.py`** (Slice 2).
- **Create `docs/proof/2026-06-22-recall-floor-task0.md`** (the data-derived floor).
- **Create `docs/handoffs/2026-06-22-coherence-core-pair-handoff.md`**.

---

## Task 0: Data-derive the recall floor from live telemetry (proof, no code)

**Files:** Create `docs/proof/2026-06-22-recall-floor-task0.md`

- [ ] **Step 1: Mine the `living_recall_candidate` base-distance distribution**

The shadow log (`memory_manager.py` `_shadow_log_living`) emits `living_recall_candidate id=.. base_distance=%.4f recency_factor=%.4f effective_distance=%.4f shadow_promotion=..` for every candidate. Mine `logs/maez.log`:
```bash
cd <worktree>
grep "living_recall_candidate" /home/rohit/maez/logs/maez.log | grep -oE "base_distance=[0-9.]+" | sed 's/base_distance=//' | sort -n > /tmp/base_dist.txt
wc -l /tmp/base_dist.txt
/home/rohit/maez/.venv/bin/python -c "
import statistics as s
xs=[float(l) for l in open('/tmp/base_dist.txt') if l.strip()]
xs.sort()
n=len(xs)
print('n=',n,'min=',round(xs[0],3),'p10=',round(xs[n//10],3),'p25=',round(xs[n//4],3),'median=',round(xs[n//2],3),'p75=',round(xs[3*n//4],3),'p90=',round(xs[9*n//10],3),'max=',round(xs[-1],3))
"
```

- [ ] **Step 2: Correlate with the wound (diary floods sit high)**

Cross-reference: the map established the symptom-turn diary items sat at base_distance ~0.78-0.93, while genuine-recall turns pull lower base_distances. Inspect the distribution: is there a separable band where the diary floods cluster (high base_distance) above where genuine recall lives? Pick a **data-derived initial floor** = a base_distance threshold ABOVE which items are dropped (e.g. around the p75-p90 elbow where the irrelevant tail begins). Record the chosen value + the percentile it corresponds to + 3-5 concrete example candidates above and below it (id-prefix + base_distance only, content-light).

**STOP condition:** if the distribution shows NO separable band (genuine recall and diary floods overlap completely in base_distance), STOP and report — a single base_distance floor cannot separate them and the approach needs rethink (e.g. relative-gap instead of absolute).

- [ ] **Step 3: Write + commit the proof**

Write `docs/proof/2026-06-22-recall-floor-task0.md`: the distribution stats, the chosen initial floor value + percentile, the example bands, and the VERDICT ("floor=X.XX derived, separable" or "STOP: not separable"). Define the constant name the build will use: `_RECALL_RELEVANCE_FLOOR_DEFAULT = <value>`.
```bash
git add docs/proof/2026-06-22-recall-floor-task0.md
git commit --no-verify -m "docs(proof): recall-floor Task 0 — data-derived base_distance floor from living_recall telemetry

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```
If STOP: commit the proof recording the STOP + reason; HALT.

---

## Task 1 (Slice 3a): Ranking tiers — anchor as figure, never above fresh/web

**Files:** Modify `core/routing/focused_cognition.py`; Create `tests/test_live_thread_anchor.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_live_thread_anchor.py`:
```python
import unittest
from core.routing.focused_cognition import _ranked_items_for_state, DialogueContinuityState, ContinuityKind


def _item(source_type):
    # tuple shape: (source_type, text, durable_id, temporal_provenance, origin_trust, origin_prov)
    return (source_type, f"text-{source_type}", None, None, None, None)


def _ordinary():
    return DialogueContinuityState(kind=ContinuityKind.NONE, needs_dialogue=False,
                                   fail_safe_legacy=False)


def _ranked_types(items, state):
    return [it[0] for it in _ranked_items_for_state(items, state)]


class TestAnchorRankingOrdinary(unittest.TestCase):
    def test_anchor_is_figure_when_no_fresh(self):
        order = _ranked_types([_item("memory_evidence"), _item("dialogue_anchor")], _ordinary())
        self.assertEqual(order[0], "dialogue_anchor")  # figure on ordinary turns

    def test_fresh_evidence_outranks_anchor(self):
        order = _ranked_types([_item("dialogue_anchor"), _item("fresh_evidence")], _ordinary())
        self.assertEqual(order[0], "fresh_evidence")   # Bend 2

    def test_web_context_outranks_anchor(self):
        order = _ranked_types([_item("dialogue_anchor"), _item("web_context")], _ordinary())
        self.assertEqual(order[0], "web_context")      # Bend 2 — web is fresh too

    def test_anchor_above_memory(self):
        order = _ranked_types([_item("memory_context"), _item("dialogue_anchor")], _ordinary())
        self.assertLess(order.index("dialogue_anchor"), order.index("memory_context"))


class TestAnchorRankingDirect(unittest.TestCase):
    def _direct(self):
        return DialogueContinuityState(kind=ContinuityKind.DIRECT, needs_dialogue=True,
                                       fail_safe_legacy=False)

    def test_direct_fresh_still_outranks_anchor(self):
        # the Bend-2 invariant must hold even in the DIRECT continuity branch
        order = _ranked_types([_item("dialogue_anchor"), _item("fresh_evidence")], self._direct())
        self.assertEqual(order[0], "fresh_evidence")

    def test_direct_web_still_outranks_anchor(self):
        order = _ranked_types([_item("dialogue_anchor"), _item("web_context")], self._direct())
        self.assertEqual(order[0], "web_context")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify it fails**

Run: `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_live_thread_anchor -v`
Expected: FAIL — ordinary anchor ranks 9 (below memory), and DIRECT anchor ranks 0 (above fresh).
NOTE: first verify `DialogueContinuityState` / `ContinuityKind` import paths + the constructor kwargs (read `core/routing/focused_cognition.py` near their definitions). If the constructor differs, adjust the test helpers to the real signature — do NOT change the classes. Re-run until it fails for the RIGHT reason.

- [ ] **Step 3: Update `_PRIORITY` (the tiers)**

In `core/routing/focused_cognition.py`, change `_PRIORITY` (~line 49) so fresh = tier 0, anchor = tier 1, recalled memory = tier 2:
```python
_PRIORITY: dict[str, int] = {
    "fresh_evidence": 0,
    "action_outcome": 0,
    "signal_absence": 0,
    "web_context": 0,        # was 2 — web is fresh (_FRESH_SOURCE_TYPES); leads stale memory
    "dialogue_anchor": 1,    # new — live thread: figure when no fresh present
    "open_loop": 1,
    "builder_event": 1,
    "quality_signal": 1,
    "memory_evidence": 2,    # was 1 — recalled memory is the ground
    "memory_context": 2,     # was 1
}
```

- [ ] **Step 4: Fix the DIRECT/fail_safe branch (Bend-2 invariant)**

In `_ranked_items_for_state` (~line 752), the DIRECT/fail_safe branch currently returns `0` for `dialogue_anchor` (which would now outrank fresh at `0+1=1`). Replace that branch body so fresh types stay on top:
```python
        if (
            dialogue_state.kind == ContinuityKind.DIRECT
            or dialogue_state.fail_safe_legacy
        ):
            if source_type in _FRESH_SOURCE_TYPES:
                return 0
            if source_type == "dialogue_anchor":
                return 1
            return _PRIORITY.get(source_type, 9) + 2
```
(`_FRESH_SOURCE_TYPES` is module-level at line 88. This makes DIRECT: fresh/web=0, anchor=1, memory=2+2=4 — anchor below fresh, above memory.)

- [ ] **Step 5: Run to verify it passes**

Run: `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_live_thread_anchor -v`
Expected: PASS (6 tests).

- [ ] **Step 6: Regression (the ranking is shared)**

Run: `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_focused_cognition -v 2>&1 | tail -6`
Expected: PASS. If any test asserts the OLD web/memory order (web below memory) and now fails, read it: if it's asserting the pre-fix priority as a contract, update it to the new tiering and note it in the commit; if it's testing unrelated behavior, investigate. Do NOT blanket-update without reading.

- [ ] **Step 7: Commit**

```bash
git add core/routing/focused_cognition.py tests/test_live_thread_anchor.py
git commit --no-verify -m "feat(live-thread-anchor): rank dialogue_anchor as figure, never above fresh/web (_FRESH_SOURCE_TYPES)

Tiers: fresh{fresh_evidence,web_context}=0 > dialogue_anchor=1 > memory=2. DIRECT branch guarded so the
anchor never outranks a fresh type. web_context moves above recalled memory (Bend 2 / evidence-precedence).
Ranking only — the anchor is not yet produced on ordinary turns (Task 2).

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2 (Slice 3b): Un-gate the anchor on ordinary turns (flag)

**Files:** Modify `core/routing/focused_cognition.py`; Modify `tests/test_live_thread_anchor.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_live_thread_anchor.py`:
```python
import os
from unittest import mock
from core.routing.focused_cognition import live_thread_anchor_enabled


class TestAnchorFlag(unittest.TestCase):
    def test_flag_off_by_default(self):
        self.assertFalse(live_thread_anchor_enabled(env={}))

    def test_flag_on(self):
        self.assertTrue(live_thread_anchor_enabled(env={"MAEZ_LIVE_THREAD_ANCHOR": "1"}))
```

- [ ] **Step 2: Run to verify it fails**

Run the test runner for `tests.test_live_thread_anchor`. Expected: FAIL — `ImportError: cannot import name 'live_thread_anchor_enabled'`.

- [ ] **Step 3: Add the flag reader + un-gate the anchor**

In `core/routing/focused_cognition.py`, add a flag reader near the other module-level helpers:
```python
def live_thread_anchor_enabled(env=os.environ) -> bool:
    return (env.get("MAEZ_LIVE_THREAD_ANCHOR", "") or "").strip().lower() in ("1", "true", "yes", "on")
```
(Confirm `os` is imported — it is.)

In `assemble_working_set` (~line 834), change the anchor gate so that when the flag is ON, anchors are computed unconditionally (capped to 2 pairs on ordinary turns); when OFF, the existing gated behavior is byte-identical:
```python
    if live_thread_anchor_enabled() and chat_history:
        anchors = dialogue_anchor_items(chat_history, limit_pairs=2)
    else:
        anchors = (
            dialogue_anchor_items(chat_history)
            if dialogue_state.needs_dialogue or dialogue_state.fail_safe_legacy or date_cue
            else []
        )
```
Leave the subsequent `if dialogue_authoritative or date_cue: anchors = anchors[:1]` line as-is (it further caps continuity/date turns; the flag-on ordinary path keeps up to 2).

- [ ] **Step 4: Write a behavior test (flag-on anchors an ordinary turn)**

Append to `tests/test_live_thread_anchor.py`:
```python
from core.routing.focused_cognition import assemble_working_set


class TestAnchorUngate(unittest.TestCase):
    _history = [{"role": "user", "content": "I'll search Fable 5"},
                {"role": "assistant", "content": "say the word and I'll search it"}]

    def test_flag_off_ordinary_turn_has_no_anchor(self):
        with mock.patch.dict(os.environ, {"MAEZ_LIVE_THREAD_ANCHOR": "0"}):
            ws = assemble_working_set(transcript="[memory evidence] old note",
                                      web_context="", owner_question="sure",
                                      chat_history=self._history)
        labels = [it.source_type for it in (ws.items if ws else [])]
        self.assertNotIn("dialogue_anchor", labels)

    def test_flag_on_ordinary_turn_has_anchor_as_figure(self):
        with mock.patch.dict(os.environ, {"MAEZ_LIVE_THREAD_ANCHOR": "1"}):
            ws = assemble_working_set(transcript="[memory evidence] old note",
                                      web_context="", owner_question="sure",
                                      chat_history=self._history)
        self.assertIsNotNone(ws)
        labels = [it.source_type for it in ws.items]
        self.assertIn("dialogue_anchor", labels)
        self.assertEqual(ws.items[0].source_type, "dialogue_anchor")  # figure
```

- [ ] **Step 5: Run to verify it passes**

Run: `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_live_thread_anchor -v`
Expected: PASS (10 tests). NOTE: if `assemble_working_set` returns None on the flag-off ordinary "sure" turn (the early-return paths), adjust the flag-off test to assert `ws is None or "dialogue_anchor" not in labels`. If the flag-on path also hits an early `return None` (e.g. the `needs_dialogue and not anchors` guard), ensure the un-gate sets anchors BEFORE that guard so the flag-on ordinary turn produces a working set — adjust placement and re-run.

- [ ] **Step 6: Regression + commit**

Run: `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_focused_cognition tests.test_live_thread_anchor 2>&1 | tail -4`
Expected: PASS.
```bash
git add core/routing/focused_cognition.py tests/test_live_thread_anchor.py
git commit --no-verify -m "feat(live-thread-anchor): always compute the dialogue anchor on focused turns (flag MAEZ_LIVE_THREAD_ANCHOR)

Default-off = byte-identical (existing gated behavior). Flag-on: the last 1-2 user/Maez pairs are anchored
unconditionally + ranked as the figure (Task 1), so 'sure'/'proceed'/'how are you?' resolve against the live
thread. Pure attention plumbing; no voice change.

## Predicted effect
With MAEZ_LIVE_THREAD_ANCHOR=1, ordinary focused turns carry the live conversation as the top working-set
item (below any fresh/web evidence). reply_grounding should rise on continuity follow-ups; no reply path
changes when off.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3 (Slice 2a): Recall floor — shadow receipt (log would-drop, no behavior change)

**Files:** Modify `memory/memory_manager.py`; Create `tests/test_recall_floor.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_recall_floor.py`:
```python
import os, unittest
from unittest import mock
from memory.memory_manager import recall_floor_shadow_enabled, recall_floor_enabled, _passes_recall_floor


class TestRecallFloorFlags(unittest.TestCase):
    def test_flags_off_by_default(self):
        self.assertFalse(recall_floor_shadow_enabled(env={}))
        self.assertFalse(recall_floor_enabled(env={}))

    def test_shadow_flag_on(self):
        self.assertTrue(recall_floor_shadow_enabled(env={"MAEZ_RECALL_FLOOR_SHADOW": "1"}))


class TestFloorPredicate(unittest.TestCase):
    def test_relevant_item_passes(self):
        self.assertTrue(_passes_recall_floor({"distance": 0.40}, floor=0.75))

    def test_irrelevant_item_fails(self):
        self.assertFalse(_passes_recall_floor({"distance": 0.90}, floor=0.75))

    def test_missing_distance_passes_failsafe(self):
        # fail-safe toward KEEPING (don't silently drop when distance is unknown)
        self.assertTrue(_passes_recall_floor({}, floor=0.75))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify it fails**

Run: `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_recall_floor -v`
Expected: FAIL — `ImportError: cannot import name 'recall_floor_shadow_enabled'`.

- [ ] **Step 3: Add the flags + predicate + shadow receipt**

In `memory/memory_manager.py`, add near the top-level constants (use the value from Task 0's proof):
```python
_RECALL_RELEVANCE_FLOOR_DEFAULT = <value-from-Task-0>  # data-derived base_distance floor


def recall_floor_shadow_enabled(env=os.environ) -> bool:
    return (env.get("MAEZ_RECALL_FLOOR_SHADOW", "") or "").strip().lower() in ("1", "true", "yes", "on")


def recall_floor_enabled(env=os.environ) -> bool:
    return (env.get("MAEZ_RECALL_FLOOR_ENABLED", "") or "").strip().lower() in ("1", "true", "yes", "on")


def _passes_recall_floor(mem: dict, *, floor: float) -> bool:
    """A candidate clears the relevance floor iff its base distance is BELOW the floor
    (lower distance = more relevant). Missing/invalid distance -> KEEP (fail-safe)."""
    dist = mem.get("distance")
    if not isinstance(dist, (int, float)):
        return True
    return float(dist) < floor
```

In `recall_for_telegram_living`, AFTER `raw = sorted(raw, key=_effective_distance)[:10]` and `daily = sorted(daily, key=_effective_distance)[:3]` (~line 2378), add a shadow computation that logs what WOULD be dropped — but does NOT drop when only the shadow flag is on:
```python
        floor = _RECALL_RELEVANCE_FLOOR_DEFAULT
        if recall_floor_shadow_enabled() or recall_floor_enabled():
            raw_drop = [m for m in raw if not _passes_recall_floor(m, floor=floor)]
            daily_drop = [m for m in daily if not _passes_recall_floor(m, floor=floor)]
            would_empty = (len(raw_drop) == len(raw)) and (len(daily_drop) == len(daily))
            logger.info(
                "recall_floor_shadow floor=%.4f raw_n=%d raw_would_drop=%d daily_n=%d "
                "daily_would_drop=%d would_empty=%s actuated=%s",
                floor, len(raw), len(raw_drop), len(daily), len(daily_drop),
                would_empty, recall_floor_enabled(),
            )
```
(Behavior unchanged in this task — the actual drop is Task 4. Content-light: ids/counts only, never memory text.)

- [ ] **Step 4: Run to verify it passes + commit**

Run: `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_recall_floor -v`
Expected: PASS (5 tests).
```bash
git add memory/memory_manager.py tests/test_recall_floor.py
git commit --no-verify -m "feat(recall-floor): base_distance relevance floor + recall_floor_shadow receipt (no behavior change)

Shadow logs which candidates WOULD be dropped + would_empty, content-light. Floor value data-derived
(Task 0). Actuation is Task 4.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4 (Slice 2b): Actuate drop-all (flag)

**Files:** Modify `memory/memory_manager.py`; Modify `tests/test_recall_floor.py`

- [ ] **Step 1: Write the failing behavior tests**

Append to `tests/test_recall_floor.py`:
```python
from memory.memory_manager import _apply_recall_floor


class TestApplyFloor(unittest.TestCase):
    _raw = [{"id": "a", "distance": 0.40}, {"id": "b", "distance": 0.90}, {"id": "c", "distance": 0.95}]

    def test_off_keeps_all(self):
        with mock.patch.dict(os.environ, {"MAEZ_RECALL_FLOOR_ENABLED": "0"}):
            self.assertEqual(_apply_recall_floor(self._raw, floor=0.75), self._raw)

    def test_on_drops_irrelevant(self):
        with mock.patch.dict(os.environ, {"MAEZ_RECALL_FLOOR_ENABLED": "1"}):
            kept = _apply_recall_floor(self._raw, floor=0.75)
            self.assertEqual([m["id"] for m in kept], ["a"])  # b,c dropped

    def test_on_all_irrelevant_returns_empty(self):
        with mock.patch.dict(os.environ, {"MAEZ_RECALL_FLOOR_ENABLED": "1"}):
            flood = [{"id": "x", "distance": 0.85}, {"id": "y", "distance": 0.92}]
            self.assertEqual(_apply_recall_floor(flood, floor=0.75), [])  # drop-all
```

- [ ] **Step 2: Run to verify it fails**

Run the test runner for `tests.test_recall_floor`. Expected: FAIL — `ImportError: cannot import name '_apply_recall_floor'`.

- [ ] **Step 3: Add `_apply_recall_floor` + wire it**

Add to `memory/memory_manager.py`:
```python
def _apply_recall_floor(mems: list[dict], *, floor: float) -> list[dict]:
    """When MAEZ_RECALL_FLOOR_ENABLED, drop candidates that don't clear the relevance
    floor; returns [] if none clear it (drop-all -> the live thread carries the turn).
    Off -> returns the list unchanged."""
    if not recall_floor_enabled():
        return mems
    return [m for m in mems if _passes_recall_floor(m, floor=floor)]
```
In `recall_for_telegram_living`, AFTER the shadow log block, actuate:
```python
        raw = _apply_recall_floor(raw, floor=floor)
        daily = _apply_recall_floor(daily, floor=floor)
```
(When the flag is off this is a no-op — byte-identical. When on, drop-all yields empty raw/daily and the downstream evidence/context partitions become empty, so the focused path falls through to the Slice-3 anchor.)

- [ ] **Step 4: Run to verify it passes + regression**

Run: `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_recall_floor -v`
Expected: PASS (8 tests).
Run the recall regression: `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_recall_outcome tests.test_recall_shadow 2>&1 | tail -4` — expected PASS (off-flag byte-identical).

- [ ] **Step 5: Commit**

```bash
git add memory/memory_manager.py tests/test_recall_floor.py
git commit --no-verify -m "feat(recall-floor): actuate drop-all behind MAEZ_RECALL_FLOOR_ENABLED

Default-off = byte-identical. Flag-on: candidates above the relevance floor are dropped; if none clear it,
recall returns empty and the live-thread anchor (Slice 3) carries the turn. Memory not deleted — recall-time
visibility only.

## Predicted effect
With MAEZ_RECALL_FLOOR_ENABLED=1 (and the anchor on), 'how are you?'-class turns stop pulling weak self-
summaries; recall empties and the anchor answers. reply_grounding stops reading 0.0-from-diary on those turns.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5 (Slice 2c): Compound-teacher signal collection (log only, not auto-actuated)

**Files:** Modify `memory/memory_manager.py`; Modify `tests/test_recall_floor.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_recall_floor.py`:
```python
from memory.memory_manager import _recall_floor_teacher_signal


class TestTeacherSignal(unittest.TestCase):
    def test_tighten_only_when_diary_heavy_lowground_and_no_memory_ask(self):
        # bad: diary-heavy + low grounding + did NOT ask for memory -> tighten=True
        self.assertTrue(_recall_floor_teacher_signal(
            diary_heavy=True, reply_grounding=0.0, asked_for_memory=False)["tighten"])

    def test_warm_greeting_does_not_tighten(self):
        # fine: low grounding but NOT diary-heavy (a warm self-expressive greeting) -> tighten=False
        self.assertFalse(_recall_floor_teacher_signal(
            diary_heavy=False, reply_grounding=0.0, asked_for_memory=False)["tighten"])

    def test_explicit_memory_ask_does_not_tighten(self):
        # fine: the turn DID ask for memory -> low grounding is not the floor's fault
        self.assertFalse(_recall_floor_teacher_signal(
            diary_heavy=True, reply_grounding=0.0, asked_for_memory=True)["tighten"])
```

- [ ] **Step 2: Run to verify it fails**

Run the test runner. Expected: FAIL — `ImportError: cannot import name '_recall_floor_teacher_signal'`.

- [ ] **Step 3: Add the compound signal (collected, NOT auto-actuated)**

Add to `memory/memory_manager.py`:
```python
def _recall_floor_teacher_signal(*, diary_heavy: bool, reply_grounding: float | None,
                                 asked_for_memory: bool) -> dict:
    """COMPOUND teacher for the floor's online adaptation. Tighten the bar ONLY when all hold:
    the turn was diary/recall-heavy AND grounding was low AND the turn did NOT ask for memory.
    This protects warmth (low grounding on a greeting is fine). Returned for COLLECTION/logging
    only — it is NOT auto-actuated onto the floor (graduates after witness)."""
    low = reply_grounding is not None and reply_grounding <= 0.1
    tighten = bool(diary_heavy and low and not asked_for_memory)
    return {"tighten": tighten, "diary_heavy": diary_heavy,
            "reply_grounding": reply_grounding, "asked_for_memory": asked_for_memory}
```
(Wiring this to the live `reply_grounding` from `RecallOutcome` is a later graduation; this task lands the signal function + tests so the loop is hardcoded but the bar is not auto-moved. If a natural call site exists where `diary_heavy`/`asked_for_memory`/`reply_grounding` are all in scope, log `recall_floor_teacher tighten=.. diary_heavy=.. reply_grounding=.. asked_for_memory=..` there; otherwise leave the function unwired with a comment that Slice-2 graduation wires it.)

- [ ] **Step 4: Run to verify it passes + commit**

Run: `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_recall_floor -v`
Expected: PASS (11 tests).
```bash
git add memory/memory_manager.py tests/test_recall_floor.py
git commit --no-verify -m "feat(recall-floor): compound teacher signal (diary-heavy + low grounding + not-memory-ask), collect-not-actuate

Bend 1: warmth never tightens the bar; only a genuine diary-flood on a non-memory turn does. Returned for
logging/collection; the online bar adaptation graduates after witness (not auto-actuated here).

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: Handoff + STOP

**Files:** Create `docs/handoffs/2026-06-22-coherence-core-pair-handoff.md`

- [ ] **Step 1: Write the handoff** — branch tip; Task-0 floor value + proof; what each slice changed; the flags (`MAEZ_LIVE_THREAD_ANCHOR`, `MAEZ_RECALL_FLOOR_SHADOW`/`_ENABLED`, all default-off); the invariants (Bend 1 compound-teacher never punishes warmth; Bend 2 anchor never outranks `_FRESH_SOURCE_TYPES`; memory never mutated; off-flag byte-identical); Codex anchors — (a) both fresh types beat the anchor in ordinary AND DIRECT branches, (b) drop-all empties to fall through to the anchor, (c) shadow logs content-light, (d) teacher is compound + collect-only, (e) off-flag byte-identical; and the owner-breath: **actuate in order — anchor first (`MAEZ_LIVE_THREAD_ANCHOR=1`), then recall floor shadow → witness `recall_floor_shadow` receipts don't over-drop genuine recall → then `MAEZ_RECALL_FLOOR_ENABLED=1`** — live the wound turns + a "latest news" turn, read `reply_grounding` rising on substantive turns + fresh staying the figure.

- [ ] **Step 2: Commit + STOP**

```bash
git add docs/handoffs/2026-06-22-coherence-core-pair-handoff.md
git commit --no-verify -m "docs(handoff): coherence core pair — Codex anchors + staged owner breath

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```
STOP. Do NOT merge/restart/witness. Report branch tip + verification + the staged owner-breath. Hold for `merge it`.

---

## Self-Review
**Spec coverage:** Slice 2 floor on base_distance + drop-all-to-empty (Task 3 predicate + Task 4 actuate) ✓; data-derived initial bar (Task 0) ✓; compound teacher, collect-not-actuate (Task 5) ✓; shadow-first (Task 3) ✓; memory not mutated (predicate is read-only filter) ✓. Slice 3 always-on anchor (Task 2) + figure-but-never-above-fresh-OR-web (Task 1, both branches tested) ✓; reuse helper ✓. Separable flags ✓. Witness via meter (handoff) ✓. Bend 1 (Task 5 tests) ✓; Bend 2 (Task 1 tests both fresh types + DIRECT branch) ✓.

**Placeholder scan:** one intentional `<value-from-Task-0>` (filled by Task 0's proof before Task 3) — flagged as the single data-dependency, not a vague TODO. Every other step has concrete code.

**Type consistency:** flag readers (`live_thread_anchor_enabled`, `recall_floor_shadow_enabled`, `recall_floor_enabled`) consistent across tasks; `_passes_recall_floor(mem, *, floor)` / `_apply_recall_floor(mems, *, floor)` consistent Task 3↔4; `_recall_floor_teacher_signal` kwargs consistent Task 5; `_PRIORITY` tiers ↔ the Task-1 tests ↔ the DIRECT-branch fix all use the same numbers.
