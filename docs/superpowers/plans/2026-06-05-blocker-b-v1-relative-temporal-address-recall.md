# Blocker-B v1: Relative Temporal Address Recall — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When the owner asks with a relative temporal address (yesterday/last week/this morning/earlier today), the live legacy recall path searches that window first and never lets an out-of-window match wear in-window clothing.

**Architecture:** A surgical branch at the top of `recall_for_telegram` keyed off `detect_temporal_anchor`'s full result. It reuses TRF's pure window resolver + `_row_in_window` + `_absolute_date_recall`'s `_tag_temporal_rows` label pattern, adds a new `_raw_rows_in_window` helper (must-prove: Chroma timestamp-range, correctness AND cost, with honest degradation), and renders a **typed** `<TEMPORAL_RECALL_STATUS>` element so an empty window is a *rendered fact*, not a vanished block. Single file: `memory/memory_manager.py`.

**Tech Stack:** Python 3, ChromaDB; reuse `core.memory.temporal_anchor_recall.detect_temporal_anchor`, `core.time.temporal_spine.temporal_window`. Tests: `.venv/bin/python -B -m unittest` (NOT pytest).

**Spec:** `docs/superpowers/specs/2026-06-05-blocker-b-v1-relative-temporal-address-recall-design.md`. **Lane:** Codex implements / Claude reviews / owner runs the live witness.

**Commit convention:** Tasks 2–4 change recall behavior → their commit messages MUST carry a `## Predicted effect` section (`feedback_predicted_effect_commit_convention`). Task 1 (a helper + its proof) and Task 5 (gate) are behavior-affecting too once wired; include `## Predicted effect` on any commit that changes live recall output.

---

## The covenant law (enforced by the tests)

> For a temporal-address query, legacy semantic recall is NOT an eligible fallback evidence source. Every row reaching the brain is one of: window-confirmed · timeless context (core) · explicitly not-from-window context · or absent-with-an-honest-status. No disguised fifth category. **"Empty" is over `daily`/`raw` event memories only — core never counts.**

## File Structure

| File | Change |
|------|--------|
| `memory/memory_manager.py` | `_raw_rows_in_window` helper (Task 1); `_relative_temporal_address_recall` + the `AbsoluteRecallWindow` bridge (Task 2); the `recall_for_telegram` 3-outcome branch (Task 3); the typed status render in `format_for_prompt` (Task 4). |
| `tests/test_blocker_b_relative_temporal_address.py` (create) | the RED matrix + the must-prove spike. |

**Reuse (read-only):** `detect_temporal_anchor`, `temporal_window`, `_row_in_window`, `_tag_temporal_rows`, `AbsoluteRecallWindow`, `fallback_label`. **Untouched:** `recall_for_telegram_living` (latency No-Go), the focused/daemon TRF path, absolute-date handling, the lived-episode store.

---

## Task 1: `_raw_rows_in_window` — the must-prove helper (Chroma timestamp-range, correctness + cost, honest degradation)

**Files:** Modify `memory/memory_manager.py`; Test `tests/test_blocker_b_relative_temporal_address.py`

- [ ] **Step 1: Write the proof test (does Chroma range-filter ISO timestamps?)**

Create `tests/test_blocker_b_relative_temporal_address.py`:

```python
# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Blocker-B v1: Relative Temporal Address Recall.

Covenant law: for a relative temporal address, every row reaching the brain is
window-confirmed / timeless-context(core) / explicitly-not-from-window / or
absent-with-an-honest-status. "Empty" is over daily/raw event memories only.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from core.routing.temporal_cue import AbsoluteRecallWindow


def _window(days_back_start: int, days_back_end: int) -> AbsoluteRecallWindow:
    now = datetime.now(timezone.utc)
    return AbsoluteRecallWindow(
        start_utc=now - timedelta(days=days_back_start),
        end_utc=now - timedelta(days=days_back_end),
        method="relative_last_week",
        label="last week",
    )


class RawWindowHelperProofTests(unittest.TestCase):
    """The MUST-PROVE: _raw_rows_in_window returns only in-window rows, bounded."""

    def _mm_with_raw(self, rows):
        # rows: list of (id, iso_timestamp). Build a fake raw collection that
        # exercises the real helper against a controllable backend.
        from unittest import mock
        from memory.memory_manager import MemoryManager

        mm = MemoryManager.__new__(MemoryManager)
        raw = mock.Mock()
        # The helper's contract is what we assert; this fake lets the test pin
        # correctness (only in-window) regardless of the chosen backend path.
        def _get(where=None, include=None, **kw):
            return {
                "ids": [r[0] for r in rows],
                "metadatas": [{"timestamp": r[1]} for r in rows],
                "documents": [r[0] for r in rows],
            }
        raw.get.side_effect = _get
        mm.raw = raw
        return mm

    def test_returns_only_in_window_rows(self):
        now = datetime.now(timezone.utc)
        in_win = (now - timedelta(days=4)).isoformat()
        out_win = (now - timedelta(days=53)).isoformat()
        mm = self._mm_with_raw([("in", in_win), ("out", out_win)])
        win = _window(7, 0)  # last 7 days
        rows = mm._raw_rows_in_window(win)
        ids = {r.get("id") for r in rows}
        self.assertIn("in", ids)
        self.assertNotIn("out", ids)  # 53d row must NOT appear


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the proof test (it fails — helper undefined — and is the spike)**

Run: `.venv/bin/python -B -m unittest tests.test_blocker_b_relative_temporal_address.RawWindowHelperProofTests -v`
Expected: FAIL — `AttributeError: ... '_raw_rows_in_window'`.

Then **spike the real Chroma backend** in a scratch probe (read-only, against a *copy* of `memory/db`, never the live db) to learn whether `self.raw.get(where={"timestamp": {"$gte": start_iso, "$lte": end_iso}})` is *supported and bounded*:

```bash
cp -r memory/db /tmp/bb_probe_db 2>/dev/null
.venv/bin/python -B -c "
import time, chromadb
c = chromadb.PersistentClient('/tmp/bb_probe_db/raw')  # adjust to the real raw path
col = c.get_collection(c.list_collections()[0].name)
from datetime import datetime, timedelta, timezone
now = datetime.now(timezone.utc)
lo=(now-timedelta(days=7)).isoformat(); hi=now.isoformat()
t=time.time()
try:
    got = col.get(where={'\$and':[{'timestamp':{'\$gte':lo}},{'timestamp':{'\$lte':hi}}]}, include=['metadatas'])
    print('SUPPORTED rows=%d ms=%d' % (len(got.get('ids') or []), (time.time()-t)*1000))
except Exception as e:
    print('UNSUPPORTED:', type(e).__name__, str(e)[:120])
"
```
Record the result. **This is the decision point** for Step 3.

- [ ] **Step 3: Implement `_raw_rows_in_window` on the proven branch**

Add to `MemoryManager` (near `_absolute_date_recall`). The helper has a **budget + timing guard**: it never blocks the chat path.

**Variant A — if the spike proved Chroma timestamp-range works and is bounded:**

```python
    _RAW_WINDOW_BUDGET_MS = 250  # tunable; over budget -> honest degrade, never block

    def _raw_rows_in_window(self, window) -> list[dict]:
        """Window-first raw rows whose timestamp falls inside `window`.

        Returns ONLY in-window rows (correctness). If retrieval exceeds the
        budget, returns [] (cost guard) so the caller degrades to dated-daily +
        honest status — NEVER falls back to outside-window semantic rows.
        """
        import time as _t
        started = _t.monotonic()
        lo = window.start_utc.isoformat()
        hi = window.end_utc.isoformat()
        try:
            got = self.raw.get(
                where={"$and": [{"timestamp": {"$gte": lo}}, {"timestamp": {"$lte": hi}}]},
                include=["metadatas", "documents"],
            )
        except Exception as exc:  # backend rejected the range -> honest degrade
            logger.warning("blocker-b: raw window query failed (%s) — degrading", exc)
            return []
        if (_t.monotonic() - started) * 1000.0 > self._RAW_WINDOW_BUDGET_MS:
            logger.warning("blocker-b: raw window query over budget — degrading")
            return []
        ids = got.get("ids") or []
        metas = got.get("metadatas") or []
        docs = got.get("documents") or []
        rows = []
        for i, rid in enumerate(ids):
            meta = metas[i] if i < len(metas) else {}
            # belt-and-suspenders: re-confirm with _row_in_window so a loose
            # backend range can never leak an out-of-window row.
            if _row_in_window(meta or {}, window):
                rows.append({"id": rid, "document": docs[i] if i < len(docs) else "", "metadata": meta})
        return rows
```

**Variant B — if the spike proved Chroma range is unsupported or too slow:** the helper degrades by contract (no raw window-filter; the branch uses dated-daily/core + honest status):

```python
    def _raw_rows_in_window(self, window) -> list[dict]:
        """Honest degradation: Chroma cannot range-filter raw timestamps within
        budget, so raw is not window-filtered in v1. The caller surfaces the
        empty/honest status and dated-daily/core — NEVER outside-window semantic
        rows. (Follow-up: a numeric epoch-ts metadata index for raw.)"""
        return []
```

(The `RawWindowHelperProofTests.test_returns_only_in_window_rows` passes under Variant A; under Variant B, replace that test with one asserting the documented degradation — `_raw_rows_in_window` returns `[]` and the *branch* never returns outside-window rows, proven in Task 2.)

- [ ] **Step 4: Run the proof test — PASS (Variant A) or the degradation test (Variant B)**

Run: `.venv/bin/python -B -m unittest tests.test_blocker_b_relative_temporal_address.RawWindowHelperProofTests -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add memory/memory_manager.py tests/test_blocker_b_relative_temporal_address.py
git commit -m "feat(blocker-b): _raw_rows_in_window helper (proven Chroma range OR honest degrade)

## Predicted effect
New private helper only; not yet wired into recall_for_telegram, so live recall
output is unchanged until Task 3. Adds a window-bounded raw retrieval path with a
budget/timing guard that degrades to [] rather than blocking."
```

---

## Task 2: `_relative_temporal_address_recall` + the window bridge (core excluded from the address)

**Files:** Modify `memory/memory_manager.py`; Test `tests/test_blocker_b_relative_temporal_address.py`

**Context:** mirror `_absolute_date_recall`'s `_tag_temporal_rows` label pattern, with deltas: **relative window**, **raw via `_raw_rows_in_window`**, **core is NOT window-filtered and NOT counted toward the address or the empty determination**, and **a typed status** in the returned dict.

- [ ] **Step 1: Write the failing tests**

Append to the test file:

```python
class RelativeAddressRecallTests(unittest.TestCase):
    def _mm(self, daily_in=(), raw_in=(), core_in=()):
        from unittest import mock
        from memory.memory_manager import MemoryManager
        mm = MemoryManager.__new__(MemoryManager)
        mm.get_all_core = lambda: [{"id": c, "metadata": {"timestamp": ts}} for c, ts in core_in]
        mm._all_daily_rows = lambda: [{"id": d, "metadata": {"timestamp": ts}} for d, ts in daily_in]
        mm._raw_rows_in_window = lambda window: [{"id": r, "document": r, "metadata": {"timestamp": ts}} for r, ts in raw_in]
        mm._query_collection = lambda *a, **k: []
        mm.core = mock.Mock(); mm.daily = mock.Mock()
        return mm

    def test_in_window_daily_surfaces_53d_does_not(self):
        now = datetime.now(timezone.utc)
        win = _window(7, 0)
        mm = self._mm(daily_in=[("d_in", (now - timedelta(days=4)).isoformat())])
        out = mm._relative_temporal_address_recall("what did we do last week?", win)
        self.assertTrue(any(r.get("id") == "d_in" for r in out["daily"]))
        self.assertEqual(out["temporal_status"], None)  # had matches -> no empty status

    def test_empty_window_yields_typed_empty_status_over_events(self):
        win = _window(7, 0)
        mm = self._mm(daily_in=[], raw_in=[])
        out = mm._relative_temporal_address_recall("what did we do last week?", win)
        self.assertEqual(out["daily"], []); self.assertEqual(out["raw"], [])
        self.assertEqual(out["temporal_status"]["status"], "no_date_confirmed_event_memories")
        self.assertIn("last week", out["temporal_status"]["label"])

    def test_core_in_window_does_not_fill_address_or_suppress_empty(self):
        now = datetime.now(timezone.utc)
        win = _window(7, 0)
        # a core row with an in-window timestamp, but NO daily/raw event rows
        mm = self._mm(core_in=[("c1", (now - timedelta(days=3)).isoformat())])
        out = mm._relative_temporal_address_recall("what did we do last week?", win)
        # still empty -> status renders; core did NOT count as the address answer
        self.assertEqual(out["temporal_status"]["status"], "no_date_confirmed_event_memories")
        self.assertTrue(all(r.get("id") != "c1" for r in out["daily"] + out["raw"]))
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/bin/python -B -m unittest tests.test_blocker_b_relative_temporal_address.RelativeAddressRecallTests -v`
Expected: FAIL — `_relative_temporal_address_recall` undefined.

- [ ] **Step 3: Implement the bridge + the method**

Add a label map + the method to `MemoryManager`:

```python
    _RELATIVE_ANCHOR_LABEL = {
        "yesterday": "yesterday", "last_week": "last week",
        "this_morning": "this morning", "earlier_today": "earlier today",
    }

    @staticmethod
    def _bridge_window(anchor_kind: str, start_utc, end_utc):
        """TRF/temporal_window UTC bounds -> an AbsoluteRecallWindow (method/label)."""
        from core.routing.temporal_cue import AbsoluteRecallWindow
        label = MemoryManager._RELATIVE_ANCHOR_LABEL.get(anchor_kind, anchor_kind)
        return AbsoluteRecallWindow(
            start_utc=start_utc, end_utc=end_utc,
            method=f"relative_{anchor_kind}", label=label,
        )

    def _relative_temporal_address_recall(self, query: str, window) -> dict:
        """Window-first recall for a relative temporal address. Daily+raw are the
        event tiers (the address); core is timeless self-context (never the
        address, never counted toward empty). Returns {core,daily,raw,temporal_status}."""
        daily_in = [r for r in self._all_daily_rows() if _row_in_window(r.get("metadata") or {}, window)]
        raw_in = self._raw_rows_in_window(window)

        if daily_in or raw_in:
            daily = self._tag_temporal_rows(daily_in[:3], method=window.method, label=window.label, confirmed=True, window=window)
            raw = self._tag_temporal_rows(raw_in[:10], method=window.method, label=window.label, confirmed=True, window=window)
            return {"core": self.get_all_core(), "daily": daily, "raw": raw, "temporal_status": None}

        # empty over EVENT tiers -> typed honest status; core stays as self-context only
        status = {"label": window.label, "status": "no_date_confirmed_event_memories",
                  "text": f"No date-confirmed event memories found for {window.label}."}
        # optional timing-uncertain fallback ALWAYS below the status, never replacing it
        topic = _temporal_topic_signal(query)
        fb_label = "semantic match, timing uncertain (not date-confirmed)"
        fb = self._tag_temporal_rows(self._query_collection(self.daily, topic, n=2, record_recalls=False),
                                     method="semantic_fallback", label=fb_label, confirmed=False) if topic else []
        return {"core": self.get_all_core(), "daily": fb, "raw": [], "temporal_status": status}
```

- [ ] **Step 4: Run to verify they pass**

Run: `.venv/bin/python -B -m unittest tests.test_blocker_b_relative_temporal_address.RelativeAddressRecallTests -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit** (with `## Predicted effect`: "new branch method, not yet routed; no live change until Task 3.")

---

## Task 3: The `recall_for_telegram` branch — 3 outcomes off `detect_temporal_anchor`

**Files:** Modify `memory/memory_manager.py:2305-2320`; Test `tests/test_blocker_b_relative_temporal_address.py`

- [ ] **Step 1: Write the failing tests**

```python
class RecallRoutingTests(unittest.TestCase):
    def test_non_temporal_query_is_byte_identical_legacy(self):
        # a non-anchor query must NOT take the branch (detect returns anchor_kind=None)
        from core.memory.temporal_anchor_recall import detect_temporal_anchor
        self.assertIsNone(detect_temporal_anchor("what is the capital of France?").anchor_kind)

    def test_helper_unavailable_yields_status_not_semantic(self):
        from unittest import mock
        from memory.memory_manager import MemoryManager
        mm = MemoryManager.__new__(MemoryManager)
        mm.get_all_core = lambda: []
        with mock.patch("core.memory.temporal_anchor_recall.detect_temporal_anchor") as d:
            d.return_value = mock.Mock(anchor_kind="last_week", anchor_detected=True,
                                       window_start=None, window_end=None, search_status="helper_unavailable")
            out = mm.recall_for_telegram("what did we do last week?")
        self.assertEqual(out["daily"], []); self.assertEqual(out["raw"], [])
        self.assertEqual(out["temporal_status"]["status"], "temporal_helper_unavailable")
```

- [ ] **Step 2: Run to verify they fail** (`temporal_status` not in the legacy return).

- [ ] **Step 3: Add the branch at the top of `recall_for_telegram`**

```python
    def recall_for_telegram(self, query: str) -> dict:
        """Build context for a Telegram response with topic-aware retrieval."""
        from core.memory.temporal_anchor_recall import detect_temporal_anchor
        anchor = detect_temporal_anchor(query)
        if getattr(anchor, "anchor_kind", None) in self._RELATIVE_ANCHOR_LABEL:
            if getattr(anchor, "search_status", None) == "helper_unavailable" \
               or anchor.window_start is None or anchor.window_end is None:
                return {"core": self.get_all_core(), "daily": [], "raw": [],
                        "temporal_status": {"label": self._RELATIVE_ANCHOR_LABEL[anchor.anchor_kind],
                                            "status": "temporal_helper_unavailable",
                                            "text": "Temporal reference recognized but could not be resolved to a window."}}
            window = self._bridge_window(anchor.anchor_kind, anchor.window_start, anchor.window_end)
            return self._relative_temporal_address_recall(query, window)

        # --- legacy path, untouched for non-temporal queries ---
        core = self.get_all_core()
        daily = self._query_collection(self.daily, query, n=3)
        raw = self._query_collection(self.raw, query, n=20)
        raw = self._merge_recall_candidates(raw, self._recent_reddit_source_rows(self.raw, query))
        raw = self._merge_recall_candidates(raw, self._recent_telegram_exchange_rows(self.raw, query))
        raw = self._topic_rerank(query, raw, n=10)
        return {"core": core, "daily": daily, "raw": raw}
```

Note: `detect_temporal_anchor`'s window fields are owner-local; confirm whether `window_start/window_end` are UTC. If they are owner-local, resolve UTC via `temporal_window(anchor.anchor_kind, datetime.now(owner_timezone()))` in `_bridge_window` instead of trusting the detector's fields. Pin this in Step 4 with a test asserting the bridged window's `start_utc/end_utc` match `temporal_window(...)`.

- [ ] **Step 4: Run to verify they pass** + add the UTC-bounds pin test.

- [ ] **Step 5: Commit** (with `## Predicted effect`: "relative-address queries now window-bound the main recall; non-temporal queries unchanged; helper-unavailable yields an honest status, never semantic fallback").

---

## Task 4: The typed `<TEMPORAL_RECALL_STATUS>` render in `format_for_prompt`

**Files:** Modify `memory/memory_manager.py:2446-2451+`; Test `tests/test_blocker_b_relative_temporal_address.py`

- [ ] **Step 1: Write the failing tests**

```python
class StatusRenderTests(unittest.TestCase):
    def _mm(self):
        from memory.memory_manager import MemoryManager
        return MemoryManager.__new__(MemoryManager)

    def test_empty_with_status_still_renders(self):
        mm = self._mm()
        block = mm.format_for_prompt({"core": [], "daily": [], "raw": [],
            "temporal_status": {"label": "last week", "status": "no_date_confirmed_event_memories",
                                "text": "No date-confirmed event memories found for last week."}})
        self.assertIn("TEMPORAL_RECALL_STATUS", block)
        self.assertIn("last week", block)
        self.assertNotIn("<RECALLED", block.split("TEMPORAL_RECALL_STATUS")[0][-200:])  # status is not a RECALLED row

    def test_no_status_and_no_rows_stays_empty(self):
        mm = self._mm()
        self.assertEqual(mm.format_for_prompt({"core": [], "daily": [], "raw": []}), "")
```

- [ ] **Step 2: Run to verify they fail** (today `format_for_prompt` returns "" for empty).

- [ ] **Step 3: Render the typed status; don't vanish on status-only**

In `format_for_prompt`, after `raw = recalled.get("raw", []) or []`:

```python
        temporal_status = recalled.get("temporal_status")

        if not (core or daily or raw or temporal_status):
            return ""
```

And render the status as a distinct typed element (before the per-tier `<RECALLED>` rows), e.g. just after the `PAST OBSERVATIONS` header block:

```python
        if temporal_status:
            lines.append(
                f'<TEMPORAL_RECALL_STATUS label="{temporal_status.get("label","")}" '
                f'status="{temporal_status.get("status","")}">'
                f'{temporal_status.get("text","")}'
                f'</TEMPORAL_RECALL_STATUS>'
            )
```

The status is its own tag — never a `<RECALLED>` row, never added to `core/daily/raw`, never stored.

- [ ] **Step 4: Run to verify they pass.**

- [ ] **Step 5: Commit** (with `## Predicted effect`: "an empty temporal window now renders an explicit status line instead of a vanished block; the brain can no longer answer an address from stale semantic context").

---

## Task 5: Full-suite gate + apples-to-apples + live witness handoff

- [ ] **Step 1: Focused suite** — `.venv/bin/python -B -m unittest tests.test_blocker_b_relative_temporal_address tests.test_memory_manager tests.test_retrieval_truth 2>&1 | tail -5` (the retrieval-truth + memory-manager contracts are the regression net for `format_for_prompt`/recall). Expected: OK.
- [ ] **Step 2: Full discover** — `.venv/bin/python -B -m unittest discover -s tests -p 'test_*.py' -t . 2>&1 | tail -15`. Expected: zero new failures vs the known floor; verify any failure is pre-existing in isolation.
- [ ] **Step 3: Review handoff (Claude lane):** apples-to-apples in the asset-rich main checkout (detached), not the worktree (`feedback_worktree_floor_confound`). Primary anchors: `recall_for_telegram` byte-identical for non-temporal queries; the typed status is not a memory row / not stored / not cited as lived evidence; core never fills the address; the raw helper's correctness+cost.
- [ ] **Step 4: Live witness (owner-run, after merge + restart):** "what were we working on last week?" → window-bounded main recall + typed status; a relative query with a genuinely empty window → the rendered empty status (not stale backfill). Confirm `recall: mode=legacy` (we did NOT touch living recall).

---

## Self-Review

**Spec coverage (§8 rules → tasks):** 1 (full-result branch, byte-identical) → T3; 2 (helper-unavailable status) → T3; 3 (window-first, no out-of-window answer) → T2; 4 (raw helper correctness+cost+degrade) → T1; 5 (typed status, not a memory row) → T4; 6 (empty over events, always renders, core doesn't count) → T2+T4; 7 (outside-window only if labeled) → T2; 8 (core timeless) → T2; 9 (main-store-scoped status) → T2/T4 (status text scoped to "event memories", coexists with TRF's lived-episode brief); 10 (full suite green, no living-recall-wholesale, no weighting) → T5 + the untouched list.

**Placeholder scan:** none — the one genuinely-unknown (Chroma range support) is a *spike with both branches' code written* (Variant A/B), not a placeholder.

**Type consistency:** `_raw_rows_in_window(window) -> list[dict]` (T1) is called in T2; `_relative_temporal_address_recall(query, window) -> {core,daily,raw,temporal_status}` (T2) is returned from T3 and consumed by `format_for_prompt` (T4); the `temporal_status` dict shape `{label,status,text}` is identical across T2, T3, T4; `_bridge_window` returns an `AbsoluteRecallWindow` (T2) consumed by `_row_in_window`/`_raw_rows_in_window`.

**Note for the implementer:** confirm the exact `_tag_temporal_rows` signature, `_all_daily_rows`, `_temporal_topic_signal`, and `detect_temporal_anchor`'s window-field timezone (owner-local vs UTC) against current `memory_manager.py` before each task — and re-derive the UTC window via `temporal_window(...)` if the detector's fields are owner-local (the T3 Step 3 note).
```
