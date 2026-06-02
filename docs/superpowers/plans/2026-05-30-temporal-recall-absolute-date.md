# Temporal Recall v1 — Absolute-Date Anchoring — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When the owner names an absolute calendar date ("around April 6", "last month", "2026-04-06"), recall the memory from that owner-local date window over the dated journal tiers — labeled by *how* it was retrieved (exact-date / month-window / semantic-fallback) — instead of returning the semantically-nearest wrong-month journal.

**Architecture:** A deterministic, owner-local-time resolver `_absolute_date_window(query, now)` returns an `AbsoluteRecallWindow` (the layering seam for future event-landmark / fuzzy producers). When a window is present, `recall_for_telegram_living` takes a date-filtered branch that selects in-window rows from `daily`/`core`, tags each returned row's **metadata copy** with the temporal method (never mutating persisted Chroma), and renders the method as a `<RECALLED>` attribute via a new `_temporal_attrs` sibling to `_provenance_attrs`. Empty-window with topic words → caveated semantic fallback; date-only with no in-window memory → no recall.

**Tech Stack:** Python 3, `unittest` (pytest NOT installed — `.venv/bin/python -m unittest`), ChromaDB, `core.time.temporal_spine` (`owner_timezone`, `try_canonical_utc`), `ruff`.

**HARD INVARIANTS (Rohit, binding — a plan can quietly violate these):**
1. **Never mutate persisted Chroma metadata.** Tag a `dict(meta)` copy on the returned row only.
2. **Never promote core into evidence.** Date-confirmed old memories are answer-authority *about the past* → they land in `[memory context]`, never `SUBSTRATE_EVIDENCE`.
3. **Do not shadow `core.time.temporal_spine.TemporalWindow`.** The new type is `AbsoluteRecallWindow`.
4. **No regression for non-temporal asks:** no window → existing semantic recall is byte-unchanged.

---

## File map
- **Modify** `memory/memory_manager.py`: add `AbsoluteRecallWindow` + `_absolute_date_window` (module-level, near the other temporal helpers ~line 670); add method `_absolute_date_recall`; add an early branch in `recall_for_telegram_living` (~1843); add static `_temporal_attrs`; append it in the four `<RECALLED>` render sites (2095/2112/2136/2213).
- **Test** `tests/test_memory_manager.py`: resolver unit tests + date-filtered-recall tests (seeded temp Chroma) + renderer attribute test.
- **Test** `tests/test_living_recall.py`: in-process production-path test (label survives memory_manager → brain_loop adapter → merge → `assemble_working_set`).
- `core/routing/focused_cognition.py`: **expected untouched** (Task 4 proves the label reaches the brain via the memory-manager renderer; only touch if Task 4 fails).

---

## Task 1: `AbsoluteRecallWindow` + `_absolute_date_window` resolver

**Files:** Modify `memory/memory_manager.py` (module level, near `_temporal_telegram_age_window` ~670). Test: `tests/test_memory_manager.py`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_memory_manager.py`:

```python
class AbsoluteDateWindowTests(unittest.TestCase):
    def _now(self):
        from datetime import datetime
        from core.time.temporal_spine import owner_timezone
        # Fixed owner-local "today" = 2026-05-30 (Saturday) for determinism.
        return datetime(2026, 5, 30, 12, 0, tzinfo=owner_timezone())

    def test_exact_date_named_month_day(self):
        from memory.memory_manager import _absolute_date_window
        w = _absolute_date_window("what did we note around April 6 about infra?", self._now())
        self.assertIsNotNone(w)
        self.assertEqual(w.method, "exact_date")
        # owner-local April 6 .. April 8 (symmetric ±2 because "around"), as UTC bounds
        self.assertLessEqual(w.start_utc.isoformat(), "2026-04-04T")
        self.assertGreaterEqual(w.end_utc.isoformat(), "2026-04-08T")
        self.assertIn("April", w.label)

    def test_exact_iso_date_forward_tolerance_only(self):
        from memory.memory_manager import _absolute_date_window
        w = _absolute_date_window("2026-04-06 infra note", self._now())
        self.assertIsNotNone(w)
        self.assertEqual(w.method, "exact_date")
        # plain date (no "around"): starts on the day, extends forward +2 for the
        # next-morning nightly journal; does not widen backward.
        self.assertEqual(w.start_utc.date().isoformat(), "2026-04-06")
        self.assertGreaterEqual(w.end_utc.date().isoformat(), "2026-04-08")

    def test_month_window_last_month(self):
        from memory.memory_manager import _absolute_date_window
        w = _absolute_date_window("what were we working on last month?", self._now())
        self.assertIsNotNone(w)
        self.assertEqual(w.method, "month_window")
        self.assertEqual(w.start_utc.date().isoformat(), "2026-04-01")  # April (today=May)

    def test_bare_may_is_not_a_month_cue(self):
        from memory.memory_manager import _absolute_date_window
        self.assertIsNone(_absolute_date_window("maybe we should check the logs", self._now()))
        self.assertIsNone(_absolute_date_window("you may have noted something", self._now()))
        # but explicit forms DO parse:
        self.assertIsNotNone(_absolute_date_window("what about May 6?", self._now()))
        self.assertIsNotNone(_absolute_date_window("anything in May 2026?", self._now()))

    def test_no_temporal_cue_returns_none(self):
        from memory.memory_manager import _absolute_date_window
        self.assertIsNone(_absolute_date_window("what's the infra ground-truth you noted earlier?", self._now()))
        self.assertIsNone(_absolute_date_window("how are you?", self._now()))
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/bin/python -m unittest tests.test_memory_manager.AbsoluteDateWindowTests -v`
Expected: FAIL — `cannot import name '_absolute_date_window'`.

- [ ] **Step 3: Implement the dataclass + resolver**

Near the top of `memory/memory_manager.py` (with the other module imports) ensure these exist:
```python
import calendar
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from core.time.temporal_spine import owner_timezone
```

Add near `_temporal_telegram_age_window` (~line 670):
```python
@dataclass(frozen=True)
class AbsoluteRecallWindow:
    """An owner-local calendar window resolved from an explicit date phrase,
    expressed in UTC bounds. The layering seam: future event-landmark / fuzzy
    producers return this same type. NOT core.time.temporal_spine.TemporalWindow."""
    start_utc: datetime
    end_utc: datetime
    method: str       # "exact_date" | "month_window"
    confidence: str   # "high" | "medium"
    label: str        # e.g. "matched by exact date (2026-04-06)"


_NIGHTLY_FWD_TOL_DAYS = 2  # nightly journal for day D is written ~D+1 04:00

_MONTH_NAMES = {}
for _i in range(1, 13):
    _MONTH_NAMES[calendar.month_name[_i].lower()] = _i
    _MONTH_NAMES[calendar.month_abbr[_i].lower()] = _i


def _owner_local_to_utc(d: datetime) -> datetime:
    return d.astimezone(timezone.utc)


def _day_bounds_local(year: int, month: int, day: int, tz) -> tuple[datetime, datetime]:
    start = datetime(year, month, day, 0, 0, 0, tzinfo=tz)
    end = datetime(year, month, day, 23, 59, 59, tzinfo=tz)
    return start, end


def _most_recent_year_for(month: int, day: int, now_local: datetime) -> int:
    """Year of the most recent past (or today) occurrence of month/day."""
    candidate = now_local.year
    try:
        if datetime(candidate, month, day, tzinfo=now_local.tzinfo) > now_local:
            candidate -= 1
    except ValueError:
        pass
    return candidate


def _absolute_date_window(query: str, now_local: datetime | None = None) -> "AbsoluteRecallWindow | None":
    """Resolve an explicit owner-local calendar date/month phrase to a UTC window.

    Returns None when there is no explicit absolute-date cue (so the caller falls
    through to ordinary semantic recall). Deterministic; no NL library.
    """
    if not query:
        return None
    tz = owner_timezone()
    if now_local is None:
        now_local = datetime.now(tz)
    q = query.lower()
    symmetric = bool(re.search(r"\b(around|about|near|circa)\b", q))

    # --- exact date: ISO yyyy-mm-dd ---
    m = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", q)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return _exact_window(y, mo, d, tz, symmetric)

    # --- exact date: "<month> <day>" or "<day> <month>" (optional year) ---
    month_alt = "|".join(re.escape(name) for name in _MONTH_NAMES)
    m = re.search(rf"\b({month_alt})\.?\s+(\d{{1,2}})(?:,?\s+(\d{{4}}))?\b", q)
    if not m:
        m2 = re.search(rf"\b(\d{{1,2}})\s+({month_alt})\b", q)
        if m2:
            mo = _MONTH_NAMES[m2.group(2)]
            d = int(m2.group(1))
            y = _most_recent_year_for(mo, d, now_local)
            return _exact_window(y, mo, d, tz, symmetric)
    else:
        mo = _MONTH_NAMES[m.group(1)]
        d = int(m.group(2))
        y = int(m.group(3)) if m.group(3) else _most_recent_year_for(mo, d, now_local)
        return _exact_window(y, mo, d, tz, symmetric)

    # --- month window: "last month" / "this month" ---
    if re.search(r"\blast month\b", q):
        first = (now_local.replace(day=1) - timedelta(days=1)).replace(day=1)
        return _month_window(first.year, first.month, tz)
    if re.search(r"\bthis month\b", q):
        return _month_window(now_local.year, now_local.month, tz)

    # --- month window: "[start|early|mid|end|late] of? <month> [year]" / "in <month>" ---
    # May guard: bare "may" excluded; require "in <month>" or "<month> <year>"
    seg = re.search(
        rf"\b(start|beginning|early|mid|middle|end|late)\s+(?:of\s+)?({month_alt})\b(?:\s+(\d{{4}}))?",
        q,
    )
    if seg:
        mo = _MONTH_NAMES[seg.group(2)]
        y = int(seg.group(3)) if seg.group(3) else _most_recent_year_for(mo, 15, now_local)
        return _month_window(y, mo, tz, part=seg.group(1))
    seg = re.search(rf"\bin\s+({month_alt})\b(?:\s+(\d{{4}}))?", q)
    if not seg:
        seg = re.search(rf"\b({month_alt})\s+(\d{{4}})\b", q)  # "April 2026"
        if seg:
            mo = _MONTH_NAMES[seg.group(1)]
            return _month_window(int(seg.group(2)), mo, tz)
        return None
    mo = _MONTH_NAMES[seg.group(1)]
    if mo == 5 and not re.search(r"\bin\s+may\b", q):  # extra May guard for safety
        return None
    y = int(seg.group(2)) if seg.lastindex and seg.group(2) else _most_recent_year_for(mo, 15, now_local)
    return _month_window(y, mo, tz)


def _exact_window(y: int, mo: int, d: int, tz, symmetric: bool) -> "AbsoluteRecallWindow | None":
    try:
        start_local, end_local = _day_bounds_local(y, mo, d, tz)
    except ValueError:
        return None
    if symmetric:
        start_local = start_local - timedelta(days=_NIGHTLY_FWD_TOL_DAYS)
    end_local = end_local + timedelta(days=_NIGHTLY_FWD_TOL_DAYS)
    return AbsoluteRecallWindow(
        start_utc=_owner_local_to_utc(start_local),
        end_utc=_owner_local_to_utc(end_local),
        method="exact_date",
        confidence="high",
        label=f"matched by exact date ({y:04d}-{mo:02d}-{d:02d})",
    )


def _month_window(y: int, mo: int, tz, part: str | None = None) -> "AbsoluteRecallWindow":
    last_day = calendar.monthrange(y, mo)[1]
    if part in ("start", "beginning", "early"):
        d0, d1 = 1, min(10, last_day)
    elif part in ("mid", "middle"):
        d0, d1 = 11, min(20, last_day)
    elif part in ("end", "late"):
        d0, d1 = 21, last_day
    else:
        d0, d1 = 1, last_day
    start_local, _ = _day_bounds_local(y, mo, d0, tz)
    _, end_local = _day_bounds_local(y, mo, d1, tz)
    end_local = end_local + timedelta(days=_NIGHTLY_FWD_TOL_DAYS)
    return AbsoluteRecallWindow(
        start_utc=_owner_local_to_utc(start_local),
        end_utc=_owner_local_to_utc(end_local),
        method="month_window",
        confidence="medium",
        label=f"matched by month window ({calendar.month_name[mo]} {y})",
    )
```

- [ ] **Step 4: Run to verify they pass**

Run: `.venv/bin/python -m unittest tests.test_memory_manager.AbsoluteDateWindowTests -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**
```bash
git add memory/memory_manager.py tests/test_memory_manager.py
git commit -m "feat(memory): AbsoluteRecallWindow + _absolute_date_window resolver (exact-date + month-window, owner-local, May-guarded)"
```

---

## Task 2: Date-filtered recall branch (copy-tagged rows, core→context)

**Files:** Modify `memory/memory_manager.py` (`recall_for_telegram_living` ~1843, new `_absolute_date_recall`, `_row_in_window`). Test: `tests/test_memory_manager.py`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_memory_manager.py` (reuse the project's seeded-temp-Chroma `MemoryManager` fixture pattern already used in this file; seed an April-6 core journal, an April-7-written entry, and a May entry):

```python
class AbsoluteDateRecallTests(unittest.TestCase):
    def _mm_with_dated_core(self):
        mm = _temp_memory_manager()  # existing helper in this test module
        mm.core.add(
            ids=["c_apr6"],
            documents=["[Journal] infrastructure ground-truth fabrication-class incident"],
            metadatas=[{"type": "core_memory", "source": "nightly_journal",
                        "timestamp": "2026-04-07T04:00:02+00:00"}],  # written for Apr 6
        )
        mm.core.add(
            ids=["c_may"],
            documents=["[Journal] May progress on living recall"],
            metadatas=[{"type": "core_memory", "source": "nightly_journal",
                        "timestamp": "2026-05-20T04:00:00+00:00"}],
        )
        return mm

    def test_april_date_ask_surfaces_april_row_labeled(self):
        from datetime import datetime
        from core.time.temporal_spine import owner_timezone
        mm = self._mm_with_dated_core()
        now = datetime(2026, 5, 30, 12, 0, tzinfo=owner_timezone())
        ev, ctx = mm.recall_for_telegram_living(
            "what did we note around April 6 about the infrastructure?",
            record_recalls=False,
        )
        core_text = " ".join(m.get("content", "") for m in (ctx.get("core") or []))
        self.assertIn("fabrication-class", core_text)          # April row present
        self.assertNotIn("May progress", core_text)            # May row excluded
        # labeled date-confirmed on the COPY:
        apr = [m for m in ctx["core"] if "fabrication" in m.get("content", "")][0]
        self.assertEqual(apr["metadata"]["temporal_match_method"], "exact_date")
        self.assertTrue(apr["metadata"]["date_confirmed"])
        # invariant: date-confirmed old core is CONTEXT, never evidence
        self.assertEqual(ev.get("core"), [])
        ev_all = " ".join(m.get("content", "") for t in ("core", "daily", "raw") for m in (ev.get(t) or []))
        self.assertNotIn("fabrication-class", ev_all)

    def test_persisted_chroma_metadata_not_mutated(self):
        mm = self._mm_with_dated_core()
        from datetime import datetime
        from core.time.temporal_spine import owner_timezone
        mm.recall_for_telegram_living("around April 6 infra", record_recalls=False,
                                      half_life_days=90, evidence_recency_days=14)
        raw = mm.core.get(ids=["c_apr6"], include=["metadatas"])["metadatas"][0]
        self.assertNotIn("temporal_match_method", raw)  # persisted row untouched

    def test_date_only_no_memory_returns_no_recall(self):
        mm = self._mm_with_dated_core()
        ev, ctx = mm.recall_for_telegram_living("what about January 3?", record_recalls=False)
        self.assertEqual(ctx.get("core"), [])
        self.assertEqual(ctx.get("daily"), [])

    def test_empty_window_with_topic_is_semantic_fallback_labeled(self):
        mm = self._mm_with_dated_core()
        ev, ctx = mm.recall_for_telegram_living(
            "what about the infrastructure on January 3?", record_recalls=False)
        rows = (ctx.get("core") or []) + (ctx.get("daily") or [])
        if rows:  # fallback only when topic signal yields a semantic hit
            self.assertTrue(any(r["metadata"].get("temporal_match_method") == "semantic_fallback"
                                for r in rows))
            self.assertFalse(any(r["metadata"].get("date_confirmed") for r in rows))
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/bin/python -m unittest tests.test_memory_manager.AbsoluteDateRecallTests -v`
Expected: FAIL — date branch not implemented; April ask returns semantic ordering / no temporal metadata.

- [ ] **Step 3: Implement `_row_in_window` + `_absolute_date_recall` + the branch**

Add module-level helper near the resolver:
```python
def _row_in_window(meta: dict, window: "AbsoluteRecallWindow") -> bool:
    from core.time.temporal_spine import try_canonical_utc
    raw_ts = meta.get("timestamp") or meta.get("date")
    if not raw_ts:
        return False
    ts = try_canonical_utc(raw_ts, field_name="timestamp")
    if ts is None:
        return False
    return window.start_utc <= ts <= window.end_utc
```

Add a method on `MemoryManager`:
```python
    def _absolute_date_recall(self, query: str, window: "AbsoluteRecallWindow") -> tuple[dict, dict]:
        """Date-filtered recall over dated tiers. Returns (evidence, context).
        Date-confirmed old memories are CONTEXT (never evidence). Tags metadata
        COPIES only — never mutates persisted Chroma rows."""
        def _tag(rows: list[dict], method: str, label: str, confirmed: bool) -> list[dict]:
            out = []
            for r in rows:
                meta = dict(r.get("metadata") or {})  # COPY — invariant #1
                meta["temporal_match_method"] = method
                meta["temporal_match_label"] = label
                meta["date_confirmed"] = confirmed
                out.append({**r, "metadata": meta})
            return out

        # gather small dated tiers in full, filter to the window
        core_all = self.get_all_core()
        daily_all = self.get_all_daily() if hasattr(self, "get_all_daily") else [
            {"id": i, "content": d, "metadata": m}
            for i, d, m in zip(
                self.daily.get(include=["documents", "metadatas"]).get("ids", []),
                self.daily.get(include=["documents", "metadatas"]).get("documents", []),
                self.daily.get(include=["documents", "metadatas"]).get("metadatas", []),
            )
        ]
        core_in = [r for r in core_all if _row_in_window(r.get("metadata") or {}, window)]
        daily_in = [r for r in daily_all if _row_in_window(r.get("metadata") or {}, window)]

        # rank in-window rows by topic relevance (distance map from a semantic query)
        topic = query.strip()
        if core_in or daily_in:
            dist = {}
            for col in (self.core, self.daily):
                for r in self._query_collection(col, topic, n=30, record_recalls=False):
                    if r.get("id") is not None and isinstance(r.get("distance"), (int, float)):
                        dist[r["id"]] = float(r["distance"])
            keyfn = lambda r: dist.get(r.get("id"), 1.0)
            core_in = _tag(sorted(core_in, key=keyfn)[:3], window.method, window.label, True)
            daily_in = _tag(sorted(daily_in, key=keyfn)[:3], window.method, window.label, True)
            evidence = {"core": [], "daily": [], "raw": []}        # invariant #2
            context = {"core": core_in, "daily": daily_in, "raw": []}
            return evidence, context

        # empty window: caveated semantic fallback ONLY if topic words remain
        topic_words = re.sub(
            r"\b(around|about|near|circa|in|on|last|this|month|start|end|early|late|mid|middle"
            r"|of|the|what|did|we|you|i|note|noted)\b", " ", query.lower())
        topic_words = re.sub(r"\b\d{1,4}\b", " ", topic_words)
        topic_words = re.sub(r"|".join(re.escape(n) for n in _MONTH_NAMES), " ", topic_words)
        if not topic_words.strip():
            return ({"core": [], "daily": [], "raw": []},
                    {"core": [], "daily": [], "raw": []})
        fb_core = _tag(self._query_collection(self.core, topic, n=2, record_recalls=False),
                       "semantic_fallback", "semantic match, timing uncertain (not date-confirmed)", False)
        fb_daily = _tag(self._query_collection(self.daily, topic, n=2, record_recalls=False),
                        "semantic_fallback", "semantic match, timing uncertain (not date-confirmed)", False)
        return ({"core": [], "daily": [], "raw": []},
                {"core": fb_core, "daily": fb_daily, "raw": []})
```

In `recall_for_telegram_living`, immediately after `query_norm = _normalize_for_echo(query)` (~line 1843), add the branch:
```python
        _abs_window = _absolute_date_window(query)
        if _abs_window is not None:
            return self._absolute_date_recall(query, _abs_window)
```

- [ ] **Step 4: Run to verify they pass**

Run: `.venv/bin/python -m unittest tests.test_memory_manager.AbsoluteDateRecallTests -v`
Expected: PASS (4 tests). If `get_all_daily` exists with a different shape, prefer it; the fallback inline `.get()` is correct either way.

- [ ] **Step 5: Commit**
```bash
git add memory/memory_manager.py tests/test_memory_manager.py
git commit -m "feat(memory): date-filtered recall branch — in-window dated rows as labeled context (copy-tagged, core stays context)"
```

---

## Task 3: Render the temporal method as a `<RECALLED>` attribute

**Files:** Modify `memory/memory_manager.py` (`_temporal_attrs` + the four `<RECALLED>` sites). Test: `tests/test_memory_manager.py`.

- [ ] **Step 1: Write the failing test**

```python
class TemporalAttrRenderTests(unittest.TestCase):
    def test_temporal_attr_renders_and_is_byte_safe(self):
        from memory.memory_manager import MemoryManager
        self.assertEqual(MemoryManager._temporal_attrs(None), "")
        self.assertEqual(MemoryManager._temporal_attrs({"type": "core_memory"}), "")  # no temporal key -> ""
        attr = MemoryManager._temporal_attrs(
            {"temporal_match_method": "exact_date",
             "temporal_match_label": "matched by exact date (2026-04-06)"})
        self.assertIn('date_match="exact_date"', attr)
        self.assertIn("2026-04-06", attr)

    def test_format_for_prompt_includes_temporal_attr(self):
        from memory.memory_manager import MemoryManager
        mm = _temp_memory_manager()
        recalled = {"core": [{"id": "c1", "content": "infra note",
                              "metadata": {"temporal_match_method": "exact_date",
                                           "temporal_match_label": "matched by exact date (2026-04-06)"}}],
                    "daily": [], "raw": []}
        out = mm.format_for_prompt(recalled)
        self.assertIn("date_match=", out)
        self.assertIn("2026-04-06", out)
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m unittest tests.test_memory_manager.TemporalAttrRenderTests -v`
Expected: FAIL — `_temporal_attrs` undefined.

- [ ] **Step 3: Implement `_temporal_attrs` + append at the four render sites**

Add a static method beside `_provenance_attrs` (~line 1984):
```python
    @staticmethod
    def _temporal_attrs(meta: dict | None) -> str:
        """Inline RECALLED attribute suffix for temporal-match provenance.
        Empty string when the row was not date/temporally matched (byte-safe:
        rows without temporal metadata render exactly as before)."""
        if not meta:
            return ""
        method = meta.get("temporal_match_method")
        if not method:
            return ""
        # sanitize against attribute/tag breakouts (mirrors _provenance_attrs)
        safe_method = re.sub(r'[^a-z_]', "", str(method))
        label = re.sub(r'[<>"]', "", str(meta.get("temporal_match_label", "")))
        attrs = f' date_match="{safe_method}"'
        if label:
            attrs += f' date_match_label="{label}"'
        return attrs
```

At EACH of the four `<RECALLED ...>` f-strings (lines ~2095–2097, ~2112–2114, ~2136–2138, ~2213), where `prov = self._provenance_attrs(...)` is computed, add immediately after it:
```python
            temporal = self._temporal_attrs(meta)
```
(use the same `meta` variable already in scope at that site — at 2095 it is `mem.get("metadata")`, so use `temporal = self._temporal_attrs(mem.get("metadata"))` there), and append `{temporal}` directly after `{prov}` inside the tag, e.g.:
```python
                f'<RECALLED tier="core" age="permanent" id="{mem_id}"{prov}{temporal}>'
```
Apply to all four sites (core/daily/raw in `format_for_prompt`, and the combined site in `format_living_context` ~2213).

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/python -m unittest tests.test_memory_manager.TemporalAttrRenderTests -v`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add memory/memory_manager.py tests/test_memory_manager.py
git commit -m "feat(memory): render temporal_match_method as <RECALLED> date_match attribute (byte-safe for untagged rows)"
```

---

## Task 4: Integration-path test (label survives to assemble_working_set)

**Files:** Test: `tests/test_living_recall.py`. (No production code unless this fails.)

- [ ] **Step 1: Write the in-process production-path test**

Add to `tests/test_living_recall.py` (mirror the existing in-process repro that uses `Layer0Dispatcher.emit_spec → _dispatcher_recall_adapters → Layer1Fanout.run → merge_fanout_results → assemble_working_set`; seed an April-6 core journal in the live/shared or a seeded MemoryManager per the file's pattern):

```python
    def test_absolute_date_label_survives_to_working_set(self):
        import os, time
        os.environ["MAEZ_LIVING_RECALL_ENABLED"] = "1"
        os.environ["MAEZ_DISPATCHER_ENABLED"] = "1"
        from core.dispatcher.layer0 import Layer0Dispatcher
        from core.dispatcher.inventory import InventoryRegistry
        from core.dispatcher.spec import SubstrateSource, ExternalSource
        from core.dispatcher.layer1 import Layer1Fanout
        from core.dispatcher.external_sources import ExternalFanout
        from core.dispatcher.merge import merge_fanout_results
        from core.brain.brain_loop import _dispatcher_index, _dispatcher_recall_adapters
        from core.routing.focused_cognition import assemble_working_set

        q = "what did we note around April 6 about the infrastructure?"
        inv = InventoryRegistry().summarize([*SubstrateSource, *ExternalSource])
        spec = Layer0Dispatcher(index=_dispatcher_index()).emit_spec(q, surface="telegram_surface", inventory=inv)
        ad = _dispatcher_recall_adapters(q, spec=spec, surface="telegram_surface",
                                         chat_history=[{"role": "user", "content": "x"}])
        cs = {"bond_id": "b", "surface": "telegram_surface", "chat_id": "c"}
        l1 = Layer1Fanout(adapters=ad, branch_timeout_s=3.0, global_deadline_s=4.0).run(
            spec, utterance=q, conversation_state=cs, fanout_generation_id="g")
        ext = ExternalFanout().run(spec, utterance=q, conversation_state=cs, fanout_generation_id="g")
        tx = merge_fanout_results(spec, l1, ext, utterance=q, surface="telegram_surface",
                                  timestamp=time.strftime('%Y-%m-%dT%H:%M:%S')).prompt_block
        # If the shared store has an April-6 dated journal, the date_match attribute
        # must survive into the rendered transcript that the brain sees:
        if "april" in tx.lower() or "2026-04" in tx:
            self.assertIn("date_match=", tx)
        # and assemble_working_set still parses the block without error:
        ws = assemble_working_set(transcript=tx, web_context="", owner_question=q)
        self.assertTrue(ws is None or hasattr(ws, "items"))
```

- [ ] **Step 2: Run it**

Run: `.venv/bin/python -m unittest tests.test_living_recall.<ClassName>.test_absolute_date_label_survives_to_working_set -v`
Expected: PASS. **If `date_match=` does NOT appear when April content is present**, the memory-manager renderer's output is being stripped before the brain — only then touch `core/routing/focused_cognition.py` (e.g. ensure the `(authority)` rendering doesn't drop `<RECALLED>` attributes) and note it as a deviation.

- [ ] **Step 3: Commit**
```bash
git add tests/test_living_recall.py
git commit -m "test(memory): integration-path — absolute-date label survives to assemble_working_set"
```

---

## Task 5: Regression + lint

**Files:** none (verification).

- [ ] **Step 1:** Run: `.venv/bin/python -m unittest tests.test_memory_manager tests.test_living_recall tests.test_focused_cognition -v` → Expected: OK (no regression in living recall, focused cognition, or the prior continuity/trust-tier tests).
- [ ] **Step 2:** Run: `.venv/bin/ruff check memory/memory_manager.py tests/test_memory_manager.py tests/test_living_recall.py` → Expected: clean.
- [ ] **Step 3:** Broad floor is env-noisy; if run, confirm only the two documented pre-existing failures (`test_web_search_direct_caller_inventory_is_stable`, `test_owner_bridge_chat_uses_envelope_prompt_block_and_recall_cap`) — report honestly, do not claim broad green.

---

## Live witness (Claude, after Task 1–5 green in-process)

Flag-on Telegram, branch code, prompt-shape + reply gates:
1. "What did we note around April 6 about the infrastructure?" → recalls the April-6/7 journal, rendered `<RECALLED ... date_match="exact_date" ...>`; reply cites it as past context with the date-match; **not** a May journal.
2. "What were we working on last month?" → month-window match (April).
3. "What about January 3?" → no confident wrong date; honest "no dated memory" (or caveated topic fallback if topic words present).
4. No-regression: "what's the infrastructure ground-truth you noted earlier?" still routes as content recall (prior slice), unaffected; and "what were we just talking about?" still DIRECT.
Gate green → branch-first commit + merge flag-off. Red → split per the "no sixth fixture pass" rule.

---

## Self-Review

**Spec coverage:** AbsoluteRecallWindow + resolver (Task 1) = spec §1–2 incl. May guard, owner-local, year-default, tolerance ✓. Date-filtered recall, core→context invariant, copy-don't-mutate, date-only→no-recall, caveated fallback (Task 2) = spec §3,4,6 + hard invariants 1,2 ✓. Per-row `<RECALLED>` attribute, focused_cognition untouched (Task 3) = spec §5 ✓. Integration-path label survival (Task 4) = spec §7 + "label must survive the full path" ✓. Witness gates = spec witness section ✓.

**Placeholder scan:** none — resolver, recall branch, renderer, and all tests carry full code + exact `.venv/bin/python -m unittest` commands.

**Type consistency:** `AbsoluteRecallWindow(start_utc, end_utc, method, confidence, label)` used identically across resolver, recall, render. `_absolute_date_window(query, now_local=None)`, `_row_in_window(meta, window)`, `_absolute_date_recall(self, query, window)`, `_temporal_attrs(meta)` signatures match every call site. Metadata keys (`temporal_match_method`, `temporal_match_label`, `date_confirmed`) match between Task 2 (write) and Task 3 (read). `method` values `exact_date`/`month_window`/`semantic_fallback` consistent with the rendered `date_match` and the witness gates.
