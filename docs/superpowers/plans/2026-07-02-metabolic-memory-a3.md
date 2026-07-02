# Metabolic Memory (A3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Maez's durable memory scales with lived events, not wall-clock: un-triggered cycle glances stay ephemeral (ring buffer), durable self-observation wears an honest `self_observed` trust tier, quiet days consolidate to one deterministic stub, vitals move to a proprioception store, and the existing tier pollution is curated (archive-not-delete) in an owner-witnessed ceremony.

**Architecture:** A new pure module `core/memory/metabolic.py` (durability vote + glance buffer), a provenance→tier mapping change (the single lever that re-tiers all introspection writes), a flag-gated branch at the daemon's cycle-store seam, event-gating inside `_consolidation_loop`'s existing two call sites, a sqlite proprioception store, and ceremony tooling in `scripts/`. The three raw-recency consumers (dream / self-analysis / proactive) change diet **by construction** — each gets an old-vs-new artifact.

**Tech Stack:** Python 3.12; host tests `/home/rohit/maez/.venv/bin/python -B -m unittest` (NOT pytest); Chroma via `MemoryManager`; flags default-off, owner-flipped.

**Spec:** `docs/superpowers/specs/2026-07-02-metabolic-memory-a3-design.md` (@0113640 — Rohit's salience-rescue-first-class + durable-diet decisions folded).

**Task 0 (DONE, 2026-07-02 — plan is written on this ground):** `observed` tier = tool observations (`TOOL_OBSERVATION→OBSERVED`, memory_manager:106) → rank `covenant > lived > observed > self_observed > untrusted`. Journal predicates: daily → `type="daily_consolidation"` (52 rows); core → `source="nightly_journal"` (74 rows incl. 26 pre-provenance); core `source="soul_evolution"` (8 rows) = **must-not-move**. Both `consolidate_daily()` call sites live in `_consolidation_loop` (3AM + missed-run-on-startup, daemon ~9280-9330). Raw-recency consumers verified: dream_state:384 (`recent_raw`, window 40, skips <10), self_analysis:34 (`raw.get(limit=200)` topic counts), proactive daemon:4668 (`raw.get(limit=20)`, skips <10). Cycle store seam: daemon ~10529.

## Hard Invariants

- Flag-off (`MAEZ_METABOLIC_MEMORY` unset) is byte-identical: every cycle thought stored exactly as today.
- The durability vote has exactly two voter classes: deterministic events + Maez's live substrate-salience signals. **No content-kind gate, no LLM vote.**
- Durable introspection carries `trust_tier="self_observed"` + `metabolic_durable_reason=<trigger>`; consolidation selects on the reason field, never on tier alone.
- The quiet-day stub is substrate-composed (zero LLM), `type="quiet_day_stub"` — can never masquerade as `daily_consolidation`.
- Ceremony: nothing deleted, everything restorable, negative controls (Who-Rohit-Is / covenant / soul_evolution / scars) proven non-matching BEFORE any bulk move, one-row restore proven first, owner reviews the move list.
- No consumer changes silently: the three diet-changed consumers each get an old-vs-new artifact + witness.

---

## Task 1: `TrustTier.SELF_OBSERVED` (write-safety)

**Files:** Modify `memory/memory_manager.py`; Test `tests/test_metabolic_trust_tier.py` (create)

- [ ] **Step 1: Failing test**

```python
# tests/test_metabolic_trust_tier.py
# (rewritten per Codex plan-review: _TRUST_TIER_ORDER is a TUPLE of strings,
#  ascending trust ("untrusted","observed","lived","covenant"); the real
#  untrusted filter is _partition_consolidation_input; _provenance_metadata
#  takes (provenance_source, trust_tier).)
import unittest

from memory.memory_manager import (
    TrustTier,
    _partition_consolidation_input,
    _provenance_metadata,
    _TRUST_TIER_ORDER,
)


class SelfObservedTierTests(unittest.TestCase):
    def test_self_observed_is_a_valid_tier(self):
        self.assertEqual(TrustTier("self_observed"), TrustTier.SELF_OBSERVED)

    def test_introspection_default_maps_to_self_observed(self):
        meta = _provenance_metadata("introspection", None)
        self.assertEqual(meta["trust_tier"], "self_observed")
        self.assertEqual(meta["provenance_source"], "introspection")

    def test_order_between_untrusted_and_observed(self):
        order = list(_TRUST_TIER_ORDER)  # ascending trust
        self.assertIn("self_observed", order)
        self.assertGreater(order.index("self_observed"), order.index("untrusted"))
        self.assertLess(order.index("self_observed"), order.index("observed"))

    def test_explicit_self_observed_write_does_not_raise(self):
        meta = _provenance_metadata("introspection", "self_observed")
        self.assertEqual(meta["trust_tier"], "self_observed")

    def test_consolidation_filter_keeps_self_observed_drops_untrusted(self):
        items = [
            {"id": "a", "content": "x", "metadata": {"trust_tier": "self_observed"}},
            {"id": "b", "content": "y", "metadata": {"trust_tier": "untrusted"}},
        ]
        kept, kept_ids, filtered_n, _labels = _partition_consolidation_input(items)
        self.assertEqual(kept_ids, ["a"])
        self.assertEqual(filtered_n, 1)
```

- [ ] **Step 2: RED** — `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_metabolic_trust_tier -v` → ValueError/AttributeError.
- [ ] **Step 3: Implement** — in `memory/memory_manager.py`: add `SELF_OBSERVED = "self_observed"` to `TrustTier`; change the provenance map line (`ProvenanceSource.INTROSPECTION: TrustTier.LIVED` → `TrustTier.SELF_OBSERVED` — **this is the single lever**: cycle thoughts, daily consolidations (line ~1733), and promotion defaults (~1869) all re-tier through it); insert into `_TRUST_TIER_ORDER` between OBSERVED and UNTRUSTED (adjust comment at ~167: `covenant > lived > observed > self_observed > untrusted`).
- [ ] **Step 4: GREEN** + run the existing memory/recall regression (`tests.test_recall_floor tests.test_living_recall tests.test_recall_quality_structural`) to prove no reader breaks.
- [ ] **Step 5: Commit** `feat(metabolic): TrustTier.SELF_OBSERVED — introspection stops wearing 'lived'`

---

## Task 2: `core/memory/metabolic.py` — durability vote + glance buffer (pure)

**Files:** Create `core/memory/metabolic.py`; Test `tests/test_metabolic_vote.py` (create)

- [ ] **Step 1: Failing tests**

```python
# tests/test_metabolic_vote.py
import time
import unittest

from core.memory.metabolic import CycleEvents, GlanceBuffer, evaluate_durability


class DurabilityVoteTests(unittest.TestCase):
    def test_quiet_cycle_is_ephemeral(self):
        durable, reason = evaluate_durability(CycleEvents())
        self.assertFalse(durable)
        self.assertIsNone(reason)

    def test_each_event_trigger_is_durable(self):
        cases = {
            "alert_sent": "alert",
            "error_event": "error",
            "owner_interaction": "owner_interaction",
            "action_taken": "action",
            "first_of_kind": "novel_event",
            "covenant_event": "covenant",
        }
        for field, expected_reason in cases.items():
            with self.subTest(field=field):
                durable, reason = evaluate_durability(CycleEvents(**{field: True}))
                self.assertTrue(durable)
                self.assertEqual(reason, expected_reason)

    def test_salience_rescue_is_durable(self):
        durable, reason = evaluate_durability(CycleEvents(salience_marked=True))
        self.assertTrue(durable)
        self.assertEqual(reason, "salience_rescue")

    def test_event_reason_wins_over_rescue_when_both(self):
        durable, reason = evaluate_durability(
            CycleEvents(alert_sent=True, salience_marked=True)
        )
        self.assertTrue(durable)
        self.assertEqual(reason, "alert")


class GlanceBufferTests(unittest.TestCase):
    def test_append_and_recent(self):
        buf = GlanceBuffer(maxlen=3, ttl_s=3600)
        for i in range(4):
            buf.append(text=f"t{i}", cycle=i, ts=time.time())
        texts = [g["text"] for g in buf.recent()]
        self.assertEqual(texts, ["t1", "t2", "t3"])  # maxlen evicts oldest

    def test_ttl_prunes(self):
        buf = GlanceBuffer(maxlen=10, ttl_s=1)
        buf.append(text="old", cycle=1, ts=time.time() - 5)
        buf.append(text="new", cycle=2, ts=time.time())
        texts = [g["text"] for g in buf.recent()]
        self.assertEqual(texts, ["new"])

    def test_rescue_window_pop(self):
        # a glance can be pulled out of the buffer and promoted if a salience
        # signal arrives shortly after the cycle stored it
        buf = GlanceBuffer(maxlen=10, ttl_s=3600)
        buf.append(text="mover", cycle=7, ts=time.time())
        g = buf.take_by_cycle(7)
        self.assertEqual(g["text"], "mover")
        self.assertIsNone(buf.take_by_cycle(7))
```

- [ ] **Step 2: RED.**
- [ ] **Step 3: Implement**

```python
# core/memory/metabolic.py
"""Metabolic memory: the durability vote + the glance buffer.

The vote has exactly two voter classes — deterministic events (the world did
something) and Maez's own substrate-salience signals (Maez raised its hand).
"Idle" is never a verdict: it means neither voter voted. The LLM is NOT a voter
(asking the model "keep this?" would make its priors the gatekeeper — Law 2).
The event-trigger set is scaffolding; as Maez's salience machinery matures it
takes over more of this vote (spec: interim-by-declaration).
"""
from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass


@dataclass(frozen=True)
class CycleEvents:
    alert_sent: bool = False
    error_event: bool = False
    owner_interaction: bool = False
    action_taken: bool = False
    first_of_kind: bool = False
    covenant_event: bool = False
    salience_marked: bool = False  # Maez's own signals (heartbeat/broker) — the rescue


_EVENT_REASONS = (
    ("alert_sent", "alert"),
    ("error_event", "error"),
    ("owner_interaction", "owner_interaction"),
    ("action_taken", "action"),
    ("first_of_kind", "novel_event"),
    ("covenant_event", "covenant"),
)


def evaluate_durability(events: CycleEvents) -> tuple[bool, str | None]:
    """(durable, metabolic_durable_reason). Event reasons take naming precedence;
    salience_rescue applies when only Maez's own signal voted."""
    for field, reason in _EVENT_REASONS:
        if getattr(events, field):
            return True, reason
    if events.salience_marked:
        return True, "salience_rescue"
    return False, None


class GlanceBuffer:
    """In-memory ring for un-triggered cycle thoughts. Feeds the current moment,
    holds a rescue window, decays, never touches disk, does not survive restart."""

    def __init__(self, maxlen: int = 240, ttl_s: float = 4 * 3600):
        self._d: deque[dict] = deque(maxlen=maxlen)
        self._ttl = float(ttl_s)
        self._lock = threading.Lock()

    def append(self, *, text: str, cycle: int, ts: float, meta: dict | None = None) -> None:
        with self._lock:
            self._d.append({"text": text, "cycle": cycle, "ts": ts, "meta": meta or {}})

    def _prune(self) -> None:
        cutoff = time.time() - self._ttl
        while self._d and self._d[0]["ts"] < cutoff:
            self._d.popleft()

    def recent(self, n: int | None = None) -> list[dict]:
        with self._lock:
            self._prune()
            items = list(self._d)
        return items if n is None else items[-n:]

    def take_by_cycle(self, cycle: int) -> dict | None:
        with self._lock:
            self._prune()
            for i, g in enumerate(self._d):
                if g["cycle"] == cycle:
                    del self._d[i]
                    return g
        return None
```

- [ ] **Step 4: GREEN.** — [ ] **Step 5: Commit** `feat(metabolic): durability vote + glance buffer (pure)`

---

## Task 3: the cycle-store seam — flag-gated branch (daemon)

**Files:** Modify `daemon/maez_daemon.py` (~10513-10537); Test `tests/test_metabolic_store_seam.py` (create)

- [ ] **Step 1: Failing tests** — build a minimal harness around the new helper (extract the branch into a testable method so the daemon loop calls one seam):

```python
# tests/test_metabolic_store_seam.py
import unittest
from unittest import mock

from core.memory.metabolic import CycleEvents


class StoreSeamTests(unittest.TestCase):
    def _daemon_stub(self):
        # Task-time: import the extracted helper's owner class or module-level fn.
        # The helper signature the implementation must provide:
        #   _metabolic_store_cycle_thought(self, full_thought, snap, mem_metadata, events: CycleEvents) -> str
        # returning one of: "durable", "ephemeral" — and calling memory.store OR glance_buffer.append.
        from daemon.maez_daemon import MaezDaemon  # noqa
        d = mock.Mock()
        d._glance_buffer = mock.Mock()
        d.memory = mock.Mock()
        d.cycle_count = 42
        return d

    def test_flag_off_stores_exactly_as_today(self):
        from daemon.maez_daemon import MaezDaemon
        d = self._daemon_stub()
        with mock.patch.dict("os.environ", {}, clear=False):
            outcome = MaezDaemon._metabolic_store_cycle_thought(
                d, "thought", {"time_of_day": "x"}, {"m": 1}, CycleEvents()
            )
        self.assertEqual(outcome, "durable")
        d.memory.store.assert_called_once()
        kwargs = d.memory.store.call_args.kwargs
        self.assertNotIn("metabolic_durable_reason", kwargs.get("metadata", {}))
        d._glance_buffer.append.assert_not_called()

    def test_flag_on_quiet_goes_to_buffer(self):
        from daemon.maez_daemon import MaezDaemon
        d = self._daemon_stub()
        with mock.patch.dict("os.environ", {"MAEZ_METABOLIC_MEMORY": "1"}):
            outcome = MaezDaemon._metabolic_store_cycle_thought(
                d, "quiet glance", {}, {}, CycleEvents()
            )
        self.assertEqual(outcome, "ephemeral")
        d.memory.store.assert_not_called()
        d._glance_buffer.append.assert_called_once()

    def test_flag_on_triggered_is_durable_with_reason_and_tier(self):
        from daemon.maez_daemon import MaezDaemon
        d = self._daemon_stub()
        with mock.patch.dict("os.environ", {"MAEZ_METABOLIC_MEMORY": "1"}):
            outcome = MaezDaemon._metabolic_store_cycle_thought(
                d, "owner spoke", {}, {}, CycleEvents(owner_interaction=True)
            )
        self.assertEqual(outcome, "durable")
        kwargs = d.memory.store.call_args.kwargs
        self.assertEqual(kwargs["metadata"]["metabolic_durable_reason"], "owner_interaction")
        # THE CENTRAL TIER CORRECTION (Codex plan-review): the current daemon call
        # passes trust_tier="lived" EXPLICITLY (daemon:10535), which would override
        # Task 1's mapping. Flag-on durable writes must NOT pass "lived" — either
        # omit trust_tier (letting the introspection mapping resolve) or pass
        # "self_observed" explicitly. Without this assertion A3's most important
        # field correction silently fails.
        self.assertNotEqual(kwargs.get("trust_tier"), "lived")
        self.assertIn(kwargs.get("trust_tier"), (None, "self_observed"))
```

- [ ] **Step 2: RED.**
- [ ] **Step 3: Implement** — extract today's store call (daemon ~10529) into `_metabolic_store_cycle_thought(...)`: flag-off → exactly today's `self.memory.store(...)` call **including the existing explicit `trust_tier="lived"`** (byte-identical params — the flag-off test guards this); flag-on → `evaluate_durability(events)`; durable → store with `metadata={**mem_metadata, "metabolic_durable_reason": reason}` and **`trust_tier` omitted or `"self_observed"` — never the explicit `"lived"` the old call passes** (Codex catch: the explicit arg would override Task 1's mapping and silently defeat A3's central correction); ephemeral → `self._glance_buffer.append(...)`. **Assemble `CycleEvents` deterministically from state the loop already has**: alert/notification sent this cycle, exception/watchdog flag, owner-interaction timestamp within the cycle window, action proposed/executed, covenant/audit event (self-claim flag or claim-receipt catch this cycle), first-of-kind via an in-process event-signature set, `salience_marked` from lean-heartbeat thought_formed/moved + salience-broker proposal_count>0 this cycle (**wire every live signal — spec first-class requirement**; the exact attribute names are found at implementation from `_maybe_run_lean_idle_heartbeat` / `_maybe_run_salience_broker` return paths). Instantiate `self._glance_buffer = GlanceBuffer()` in `__init__`.
- [ ] **Step 4: GREEN + flag-off regression** (run the daemon-adjacent suites: `tests.test_jetson_edge_run`-style cycle tests if they touch the seam, plus this module).
- [ ] **Step 5: Commit** `feat(metabolic): flag-gated cycle-store seam — glances ephemeral, events+salience durable`

---

## Task 4: event-gated `consolidate_daily` + `quiet_day_stub`

**Files:** Modify `memory/memory_manager.py` (`consolidate_daily`, ~1542); Test `tests/test_metabolic_consolidation.py` (create)

- [ ] **Step 1: Failing tests**

```python
# tests/test_metabolic_consolidation.py
import unittest
from unittest import mock


class QuietDayStubTests(unittest.TestCase):
    def test_quiet_day_produces_deterministic_stub_no_llm(self):
        from memory.memory_manager import build_quiet_day_stub
        stub = build_quiet_day_stub(cycles=2847, alerts=0, owner_interactions=0, uptime_h=23.8, date_label="2026-07-02")
        self.assertIn("Quiet day", stub["text"])
        self.assertIn("2,847 cycles", stub["text"])
        self.assertEqual(stub["metadata"]["type"], "quiet_day_stub")
        self.assertNotEqual(stub["metadata"]["type"], "daily_consolidation")

    def test_consolidation_selects_on_reason_field_not_tier(self):
        # the day-window selector must filter rows by metabolic_durable_reason presence,
        # never by trust_tier
        from memory.memory_manager import _select_metabolic_consolidation_rows
        rows = [
            {"id": "a", "metadata": {"metabolic_durable_reason": "owner_interaction", "trust_tier": "self_observed"}},
            {"id": "b", "metadata": {"trust_tier": "self_observed"}},          # durable-tier but no reason (legacy) -> excluded
            {"id": "c", "metadata": {"metabolic_durable_reason": "alert", "trust_tier": "lived"}},
        ]
        picked = _select_metabolic_consolidation_rows(rows)
        self.assertEqual([r["id"] for r in picked], ["a", "c"])
```

- [ ] **Step 2: RED.**
- [ ] **Step 3: Implement** — in `consolidate_daily()` behind the same flag: gather the day window; select LLM-consolidation input via `_select_metabolic_consolidation_rows` (reason-field presence — the spec pin: tier describes evidence, never eligibility); if the selected set is empty → write `build_quiet_day_stub(...)` (substrate-composed from counters the daemon/proprioception already has; `type="quiet_day_stub"`, provenance introspection → tier self_observed via Task 1) and **make zero LLM calls**; else run the existing consolidation over the selected rows only. Flag-off: existing behavior byte-identical. Both call sites inherit (one loop function — Task 0).
- [ ] **Step 4: GREEN.** — [ ] **Step 5: Commit** `feat(metabolic): event-gated daily consolidation + deterministic quiet-day stub`

---

## Task 5: proprioception store (sensed, not narrated)

**Files:** Create `core/body/proprioception.py`; Test `tests/test_proprioception_store.py` (create)

- [ ] **Step 1: Failing tests**

```python
# tests/test_proprioception_store.py
import tempfile
import unittest
from pathlib import Path


class ProprioceptionTests(unittest.TestCase):
    def test_record_and_hourly_aggregate(self):
        from core.body.proprioception import ProprioceptionStore
        with tempfile.TemporaryDirectory() as td:
            s = ProprioceptionStore(Path(td) / "prop.db")
            for i, cpu in enumerate((10.0, 30.0, 20.0)):
                s.record(ts=1000.0 + i, cpu_pct=cpu, ram_pct=40.0, gpu_pct=5.0, gpu_temp_c=48.0)
            agg = s.aggregate(since_ts=0.0)
            self.assertEqual(agg["samples"], 3)
            self.assertAlmostEqual(agg["cpu_pct"]["max"], 30.0)
            self.assertAlmostEqual(agg["cpu_pct"]["median"], 20.0)

    def test_query_answers_trend_question(self):
        from core.body.proprioception import ProprioceptionStore
        with tempfile.TemporaryDirectory() as td:
            s = ProprioceptionStore(Path(td) / "prop.db")
            s.record(ts=1.0, cpu_pct=1.0, ram_pct=1.0, gpu_pct=1.0, gpu_temp_c=40.0)
            self.assertIn("gpu_temp_c", s.aggregate(since_ts=0.0))
```

- [ ] **Step 2: RED.** — [ ] **Step 3: Implement** a small sqlite store (samples table: ts, cpu_pct, ram_pct, gpu_pct, gpu_temp_c; `record()` from the cycle snapshot the daemon already builds; `aggregate(since_ts)` returns min/median/max per field + sample count). Wire the daemon cycle to `record()` **always-on** (pure additive telemetry per spec) — vitals keep flowing here even when the glance is ephemeral. — [ ] **Step 4: GREEN.** — [ ] **Step 5: Commit** `feat(metabolic): proprioception store — the body sensed, not narrated`

---

## Task 6: consumer behavior artifacts (the daylight rule)

**Files:** Create `docs/proof/2026-07-02-a3-consumer-diet-artifacts.md`; Test additions to `tests/test_metabolic_consumers.py` (create)

- [ ] **Step 1:** For each of dream (`recent_raw`, window 40, skip<10), self-analysis (`raw.get(200)`), proactive-opinion (`raw.get(20)`, skip<10): write the **old-vs-new artifact section** — old: digests all cycle rows incl. glances; new (by construction): digests durable rows + stubs only; expected consequence: fewer/never-firing on empty stretches ("nothing lived → nothing to dream/say"), more meaningful firings otherwise. Include the owner decision quote + date.
- [ ] **Step 2: Behavior tests** (host, mocked memory): with flag-on and a raw store containing only durable rows, (a) dream skips when <10 durable rows exist (assert the skip log/telemetry path fires — the *named* new behavior), (b) proactive-opinion skips <10, (c) self-analysis computes topic counts over durable-only without error. No production code changes expected — these tests *pin* the by-construction behavior so a future change can't silently revert it.
- [ ] **Step 3: Commit** `test(metabolic): pin the durable-only consumer diet + old-vs-new artifacts`

---

## Task 7: curation ceremony tooling (archive-not-delete, owner-witnessed)

**Files:** Create `scripts/metabolic_curation.py`; Test `tests/test_metabolic_curation.py` (create)

- [ ] **Step 1: Failing tests** — pure predicate + negative controls:

```python
# tests/test_metabolic_curation.py
import unittest

from scripts.metabolic_curation import is_journal_row, NEGATIVE_CONTROL_PREDICATES


class CurationPredicateTests(unittest.TestCase):
    def test_daily_journal_matches(self):
        self.assertTrue(is_journal_row("daily", {"type": "daily_consolidation"}))

    def test_core_nightly_journal_matches(self):
        self.assertTrue(is_journal_row("core", {"source": "nightly_journal", "type": "core_memory"}))

    def test_negative_controls_never_match(self):
        controls = [
            {"source": "soul_evolution", "type": "core_memory"},              # soul-change notes
            {"trust_tier": "covenant", "type": "core_memory"},                # covenant rows
            {"type": "core_memory", "source": "owner"},                       # relationship anchors
            {"metabolic_durable_reason": "covenant", "type": "core_memory"},  # scars-to-be
        ]
        for meta in controls:
            for tier in ("core", "daily"):
                with self.subTest(meta=meta, tier=tier):
                    self.assertFalse(is_journal_row(tier, meta))

    def test_who_rohit_is_fixture_never_matches(self):
        # the v0.2-gate lesson as a standing fixture
        meta = {"type": "core_memory", "source": "owner", "trust_tier": "covenant"}
        self.assertFalse(is_journal_row("core", meta))
```

- [ ] **Step 2: RED.** — [ ] **Step 3: Implement `scripts/metabolic_curation.py`** with subcommands, mirroring the two-phase no-TOFU discipline. **The review is load-bearing, not decorative (Codex plan-review): the daily predicate matches ALL `daily_consolidation` rows — only Rohit's row-by-row review separates polluted from keep-worthy. `apply` therefore consumes the REVIEWED artifact, never the raw predicate.**
  - `enumerate` → **reviewable decision artifact** `docs/proof/2026-07-02-a3-curation-move-list.md`: every matching row as a decision line — `- [ ] MOVE <tier>/<id> — <preview ≤140 chars> — <metadata signature>` — plus a **negative-control section proving zero matches** among covenant/soul_evolution/owner-source rows + counts per tier. **No mutation.** Rohit reviews by editing decision lines: `[x] MOVE` (approved) or changing `MOVE` → `KEEP` (flagged to stay). Unedited `[ ] MOVE` lines are **pending**.
  - `restore-proof` → move ONE owner-picked approved row to the archive collection (`get_or_create_collection("archived_introspection")`), restore it back, verify byte-identical round-trip. **The gate before bulk.**
  - `apply` → **parses the reviewed artifact**; refuses if the artifact is missing, if any row is still pending (`[ ] MOVE`), or if `--owner-approved` is absent; moves ONLY `[x] MOVE` rows (add to archive with original metadata + `archived_from`/`archived_at`, then remove from the hot collection — the row LIVES in archive; "archive-not-delete" means the *data* persists and is restorable, hot-index removal is the point); `KEEP` rows are recorded in the run log as owner-retained. Raw bulk rule (`provenance_source="introspection"`, no reason field, older than 7 days, not cited by any episode/scar) is a **separate `apply --raw-rule`** step gated on its own reviewed samples section in the artifact.
  - `verify` → archive counts == approved-move counts; hot counts dropped by exactly that amount; **every `KEEP` row proven still present in its hot collection**; spot-restore N random archived rows.
  Add to the Step-1 tests: an artifact-parser test (`[x] MOVE` → apply-set, `KEEP` → keep-set, `[ ] MOVE` → pending blocks apply) and a keep-rows-stay-hot assertion in the verify logic.
- [ ] **Step 4: GREEN** (predicates + a tmp-Chroma round-trip test for restore-proof logic). — [ ] **Step 5: Commit** `feat(metabolic): curation ceremony tooling — enumerate/restore-proof/apply/verify`

---

## Task 8: regression + STOP at review gate

- [ ] **Step 1:** Full metabolic suite + memory/recall regression:
```bash
/home/rohit/maez/.venv/bin/python -B -W ignore::ResourceWarning -m unittest \
  tests.test_metabolic_trust_tier tests.test_metabolic_vote tests.test_metabolic_store_seam \
  tests.test_metabolic_consolidation tests.test_proprioception_store tests.test_metabolic_consumers \
  tests.test_metabolic_curation tests.test_recall_floor tests.test_living_recall \
  tests.test_recall_quality_structural -v
```
- [ ] **Step 2:** ruff on touched files; `git diff --check`; flag-off byte-identical test re-run.
- [ ] **Step 3: STOP.** No merge, no flag flip, no ceremony `apply`. Hand to Codex cross-lane, then the owner sequence: (1) merge dormant; (2) `MAEZ_METABOLIC_MEMORY=1` + restart (pairs with the pending F2 brain_swap witness — one restart, two witnesses); (3) live witness: quiet stretch → stub only, event → durable w/ reason+tier, dreams/proactive fire on substance; (4) ceremony: `enumerate` → **Rohit reviews the move list** → `restore-proof` → `apply --owner-approved` → `verify`.

---

## Self-Review

**Spec coverage:** ephemeral default + two-voter vote + salience-rescue-first-class (Task 2/3); interim-by-declaration carried in metabolic.py's docstring; self_observed write-safety + rank (Task 1, the single-lever mapping); reason-field consolidation selection + quiet_day_stub distinct type (Task 4); proprioception (Task 5); durable-diet by construction + artifacts + pinned tests (Task 6); ceremony with negative controls incl. Who-Rohit-Is + soul_evolution, restore-proof-before-bulk, owner approval (Task 7); flag-off byte-identical invariant (Tasks 3/8).
**Placeholder scan:** two implementation-time lookups are named explicitly as such (the untrusted-filter helper's exact name in Task 1's last test; the heartbeat/broker attribute names in Task 3) — both verified to exist at known locations, names resolved at build. No TODOs.
**Type consistency:** `CycleEvents`/`evaluate_durability`/`GlanceBuffer.append/recent/take_by_cycle`; `_metabolic_store_cycle_thought` returns "durable"|"ephemeral"; `build_quiet_day_stub` returns {text, metadata}; `is_journal_row(tier, meta)`; consistent across tasks.
**Known risks named:** first-of-kind signature set is per-process in v0 (restart resets novelty memory — acceptable; noted for the implementer, not hidden); the daemon-seam extraction (Task 3) must move the existing call verbatim for the flag-off path — the byte-identical test is the guard.
