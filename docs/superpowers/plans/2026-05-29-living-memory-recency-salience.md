# Living Memory — Recency-Salience + Continuity Faculty Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Telegram recall present-weighted (gentle recency decay) and continuity-aware, emitting recent/relevant memory as `[memory evidence]` and older memory as `[memory context]` via the (already-landed) per-block role contract — without burying deliberately-recalled deep memory.

**Architecture:** A new flag-gated method `recall_for_telegram_living()` over the *same* substrate: telegram-scoped overfetch → recency×salience effective-distance rerank → partition into evidence (recent / continuity recent-thread) vs context (older + core) → the adapter emits two role-hinted `RecallBlock`s. Flag-off is byte-identical to today; `recall_for_cycle` is never touched.

**Tech Stack:** Python 3, ChromaDB, `unittest` (pytest NOT installed — `.venv/bin/python -m unittest`). Depends on the merged per-block role contract (`SourceRole`, `RecallBlock.role_hint`, `source_summaries_for_render`, `source_role_entries`). Executor: **Codex** RED-first; **Claude** verifies diff + runs the three-way witness.

**Source of truth:** [spec rev 3](../specs/2026-05-29-living-memory-recency-salience-design.md). Read it first. Flag `MAEZ_LIVING_RECALL_ENABLED` (default off). Knobs: `RANKING_HALF_LIFE_DAYS=90`, `EVIDENCE_RECENCY_DAYS=14`.

---

## File Structure
- `memory/memory_manager.py` — **modify.** Add module knobs, `recency_factor()`, `recall_for_telegram_living()` (overfetch + effective-distance rerank + evidence/context partition + shadow promotion logging). `recall_for_telegram`, `recall_for_cycle`, `_query_collection`, `_topic_rerank` **unchanged** (flag-off + cycle parity).
- `core/brain/brain_loop.py` — **modify.** `_memory_manager_adapter`: flag-on → call living, format each partition, emit two role-hinted `RecallBlock`s; flag-off → current single None-hint block.
- `daemon/maez_daemon.py` — **modify (1 fn).** Add `_living_recall_enabled()` mirroring `_focused_cognition_enabled` (so the env flag has one reader); the adapter imports it. (Or define the reader in `brain_loop` if the adapter can't import the daemon — verify import direction; prefer the reader where the adapter already is.)
- `tests/test_living_recall.py` — **create.** All RED tests.

**Knobs (module constants in `memory_manager.py`, tunable):** `RANKING_HALF_LIFE_DAYS = 90.0`, `EVIDENCE_RECENCY_DAYS = 14.0`.

---

## Task 1: `recency_factor()` — gentle half-life decay

**Files:** Modify `memory/memory_manager.py`. Test: `tests/test_living_recall.py`

- [ ] **Step 1: Failing test**
```python
import unittest

class RecencyFactor(unittest.TestCase):
    def test_curve(self):
        from memory.memory_manager import recency_factor
        self.assertAlmostEqual(recency_factor(0.0), 1.0, places=6)
        self.assertAlmostEqual(recency_factor(24.0), 0.5 ** (24.0/(90.0*24)), places=6)   # ~0.9923
        self.assertAlmostEqual(recency_factor(90*24.0), 0.5, places=6)                     # half-life
        self.assertLess(recency_factor(180*24.0), recency_factor(90*24.0))                 # monotonic
    def test_handles_bad_age(self):
        from memory.memory_manager import recency_factor
        self.assertEqual(recency_factor(-5.0), 1.0)   # future/negative clamps to 1.0
```

- [ ] **Step 2: Run — FAIL** (`ImportError`). `.venv/bin/python -m unittest tests.test_living_recall.RecencyFactor -v`

- [ ] **Step 3: Implement** (near the other module helpers, after `_age_hours_from_iso`):
```python
RANKING_HALF_LIFE_DAYS = 90.0
EVIDENCE_RECENCY_DAYS = 14.0


def recency_factor(age_hours: float, half_life_days: float = RANKING_HALF_LIFE_DAYS) -> float:
    """Gentle half-life decay in (0, 1]; 1.0 at age 0, 0.5 at the half-life."""
    if age_hours is None or age_hours <= 0:
        return 1.0
    return 0.5 ** (age_hours / (half_life_days * 24.0))
```

- [ ] **Step 4: Run — PASS.** **Step 5: Commit** `feat(memory): recency_factor gentle half-life decay`

---

## Task 2: `recall_for_telegram_living()` — overfetch + effective-distance rerank + partition

**Files:** Modify `memory/memory_manager.py`. Test: `tests/test_living_recall.py`

This is the core. It must NOT modify `recall_for_telegram`/`_query_collection`/`recall_for_cycle`.

- [ ] **Step 1: Failing tests**
```python
class LivingRecallRanking(unittest.TestCase):
    # Build a MemoryManager against a temp Chroma dir seeded with a few raw
    # entries at known ages (fresh strong, old strong, fresh weak), following
    # the seeding pattern in tests/test_memory_manager.py. Assert:
    def test_overfetch_surfaces_fresh_outside_topN(self):
        # a fresh entry whose cosine sits outside the age-blind top-N appears
        # in the living result after the recency rerank.
        ...
    def test_stale_strong_demoted_not_dropped(self):
        # an old strong-cosine entry has higher effective_distance than a fresh
        # one, but is still PRESENT in the returned set.
        ...
    def test_partition_by_evidence_recency(self):
        # returns (evidence, context); entries with age <= EVIDENCE_RECENCY_DAYS
        # (and continuity recent-thread) land in evidence; older + ALL core land
        # in context.
        ...
    def test_core_always_context(self):
        # every core memory is in the context partition, never evidence.
        ...
```
**Executor:** reuse `tests/test_memory_manager.py`'s MemoryManager-on-temp-dir seeding; set `metadata.timestamp` to control age. Keep asserts concrete.

- [ ] **Step 2: Run — FAIL.**

- [ ] **Step 3: Implement.** Add to `MemoryManager`:
```python
def recall_for_telegram_living(
    self,
    query: str,
    *,
    half_life_days: float = RANKING_HALF_LIFE_DAYS,
    evidence_recency_days: float = EVIDENCE_RECENCY_DAYS,
) -> tuple[dict, dict]:
    """Recency-salience recall for Telegram, partitioned into
    (evidence_recalled, context_recalled). Same substrate as
    recall_for_telegram; reuses _query_collection but reranks on an
    effective distance = base_distance / recency_factor(age), then splits
    by age. Core memories always go to context (availability, not authority)."""
    core = self.get_all_core()
    now_s = _now_seconds()

    # Overfetch a larger telegram-scoped pool so recency can surface a
    # fresh-but-slightly-weaker candidate that sat outside the age-blind topN.
    daily = self._query_collection(self.daily, query, n=12)
    raw = self._query_collection(self.raw, query, n=60)
    raw = self._merge_recall_candidates(raw, self._recent_reddit_source_rows(self.raw, query))
    raw = self._merge_recall_candidates(raw, self._recent_telegram_exchange_rows(self.raw, query))

    def _eff(mem: dict) -> float:
        d = mem.get("distance")
        base = float(d) if isinstance(d, (int, float)) else 1.0
        age_h = _age_hours_from_iso((mem.get("metadata") or {}).get("timestamp", ""), now_s)
        rf = recency_factor(age_h, half_life_days)
        self._shadow_log_living(mem, base, rf)   # Task 4 (shadow promotion + per-candidate telemetry)
        return base / max(rf, 1e-3)

    raw = sorted(raw, key=_eff)[:10]
    daily = sorted(daily, key=_eff)[:3]

    cutoff_h = evidence_recency_days * 24.0
    def _is_evidence(mem: dict) -> bool:
        age_h = _age_hours_from_iso((mem.get("metadata") or {}).get("timestamp", ""), now_s)
        return age_h <= cutoff_h

    evidence = {"core": [], "daily": [m for m in daily if _is_evidence(m)],
                "raw": [m for m in raw if _is_evidence(m)]}
    context = {"core": core, "daily": [m for m in daily if not _is_evidence(m)],
               "raw": [m for m in raw if not _is_evidence(m)]}
    return evidence, context
```
(`_shadow_log_living` is added in Task 4; for Task 2 stub it as a no-op method so tests pass, then fill in Task 4.)

- [ ] **Step 4: Run — PASS.** **Step 5: Commit** `feat(memory): recall_for_telegram_living (rerank + evidence/context partition)`

---

## Task 3: Continuity faculty — recent thread into evidence

**Files:** Modify `memory/memory_manager.py` (`recall_for_telegram_living`). Test: `tests/test_living_recall.py`

- [ ] **Step 1: Failing test** — for a DIRECT/ANAPHORIC query (`dialogue_continuity_state`), the recent-thread rows (`_recent_telegram_exchange_rows`) are placed in the **evidence** partition regardless of cosine, and old question-word-similar meta-memories are NOT in evidence.
```python
class ContinuityFaculty(unittest.TestCase):
    def test_continuity_puts_recent_thread_in_evidence(self):
        # query "what were we talking about earlier?"; seed a recent telegram
        # exchange + an old "what happened?" meta-memory. Assert recent thread
        # in evidence, old meta in context (or absent from evidence).
        ...
```

- [ ] **Step 2: Run — FAIL.**
- [ ] **Step 3: Implement.** In `recall_for_telegram_living`, before the partition, detect continuity and force recent-thread rows into evidence:
```python
    from core.routing.focused_cognition import dialogue_continuity_state, ContinuityKind
    state = dialogue_continuity_state(query)
    if state.kind in (ContinuityKind.DIRECT, ContinuityKind.ANAPHORIC):
        thread = self._recent_telegram_exchange_rows(self.raw, query)   # already age-sorted, recent
        # recent thread is authoritative evidence; demote question-word semantic to context
        evidence["raw"] = thread[:5] + [m for m in evidence["raw"] if m not in thread]
        context["raw"] = [m for m in context["raw"] if m not in thread]
```
(Place after `evidence`/`context` are built. Keep it minimal; the existing tier-4 focused path already handles the focused-call side — this teaches the *substrate*.)

- [ ] **Step 4: Run — PASS.** **Step 5: Commit** `feat(memory): continuity asks route recent thread to evidence`

---

## Task 4: Shadow promotion_score + per-candidate telemetry (NOT applied)

**Files:** Modify `memory/memory_manager.py`. Test: `tests/test_living_recall.py`

- [ ] **Step 1: Failing test** — `recall_for_telegram_living` logs, per candidate, the shadow `promotion_score` and the `recency_factor`/`effective_distance`, but ranking is **identical** whether the shadow score is high or low (assert: monkeypatch `promotion_score` to return wildly different values → identical returned ordering).
```python
class ShadowPromotion(unittest.TestCase):
    def test_promotion_not_applied(self):
        # patch core.memory_scoring.promotion_score to return 0.0 then 1.0;
        # assert the (evidence,context) ids+order are identical both times.
        ...
```

- [ ] **Step 2: Run — FAIL.**
- [ ] **Step 3: Implement** `_shadow_log_living` (a method) that computes (but does not apply) the shadow score and logs it:
```python
def _shadow_log_living(self, mem: dict, base_distance: float, rf: float) -> None:
    try:
        from core.memory_scoring import promotion_score as _ps
        shadow = _ps(mem.get("id", ""))
    except Exception:
        shadow = None
    logger.info(
        "living_recall_candidate id=%s base=%.4f recency=%.4f eff=%.4f shadow_promotion=%s",
        str(mem.get("id", ""))[:16], base_distance, rf, base_distance / max(rf, 1e-3),
        "None" if shadow is None else f"{shadow:.4f}",
    )
```
Crucially: `_eff` (Task 2) uses ONLY `base_distance / recency_factor` — the shadow value is logged, never multiplied in.

- [ ] **Step 4: Run — PASS.** **Step 5: Commit** `feat(memory): shadow promotion_score logging (not applied)`

---

## Task 5: Flag reader `_living_recall_enabled()`

**Files:** Modify `core/brain/brain_loop.py` (or `daemon/maez_daemon.py` — see File Structure). Test: `tests/test_living_recall.py`

- [ ] **Step 1: Failing test**
```python
class FlagReader(unittest.TestCase):
    def test_default_off(self):
        import os
        from core.brain.brain_loop import _living_recall_enabled
        os.environ.pop("MAEZ_LIVING_RECALL_ENABLED", None)
        self.assertFalse(_living_recall_enabled())
    def test_on(self):
        import os
        from core.brain.brain_loop import _living_recall_enabled
        os.environ["MAEZ_LIVING_RECALL_ENABLED"] = "1"
        try:
            self.assertTrue(_living_recall_enabled())
        finally:
            os.environ.pop("MAEZ_LIVING_RECALL_ENABLED", None)
```

- [ ] **Step 2: Run — FAIL.**
- [ ] **Step 3: Implement** in `core/brain/brain_loop.py`:
```python
import os
def _living_recall_enabled() -> bool:
    return os.environ.get("MAEZ_LIVING_RECALL_ENABLED", "0") in ("1", "true", "True")
```

- [ ] **Step 4: Run — PASS.** **Step 5: Commit** `feat(brain): MAEZ_LIVING_RECALL_ENABLED flag reader`

---

## Task 6: `_memory_manager_adapter` emits two role-hinted blocks (flag-on); parity (flag-off)

**Files:** Modify `core/brain/brain_loop.py:237-252`. Test: `tests/test_living_recall.py`

- [ ] **Step 1: Failing tests**
```python
class AdapterTwoBlocks(unittest.TestCase):
    def test_flag_off_single_none_hint_block(self):
        # MAEZ_LIVING_RECALL_ENABLED absent → adapter returns exactly today's
        # single RecallBlock with role_hint is None (parity).
        ...
    def test_flag_on_emits_evidence_and_context_blocks(self):
        # flag on → up to two RecallBlocks: one role_hint=SUBSTRATE_EVIDENCE,
        # one role_hint=SUBSTRATE_CONTEXT (empty partitions omitted).
        ...
```
**Executor:** build the adapter via `_dispatcher_recall_adapters(user_text)` and a MemoryManager seeded on a temp dir; monkeypatch `_dispatcher_memory_manager` to return it.

- [ ] **Step 2: Run — FAIL.**
- [ ] **Step 3: Implement.** Replace `_memory_manager_adapter` body:
```python
def _memory_manager_adapter(source: SubstrateSource):
    memory = _dispatcher_memory_manager()
    if not _living_recall_enabled():
        recalled = memory.recall_for_telegram(user_text)
        text = memory.format_for_prompt(recalled, max_chars=1200)
        if not text:
            return []
        return [RecallBlock(source=source, text=text, timestamp=None,
                            freshness="memory_manager", rationale="recall_for_telegram",
                            prompt_cost=len(text))]
    # living: partitioned evidence/context with per-block roles
    from core.dispatcher.spec import SourceRole
    evidence, context = memory.recall_for_telegram_living(user_text)
    blocks = []
    ev_text = memory.format_for_prompt(evidence, max_chars=1000)
    if ev_text:
        blocks.append(RecallBlock(source=source, text=ev_text, timestamp=None,
                                  freshness="living_recall", rationale="living_evidence",
                                  prompt_cost=len(ev_text),
                                  role_hint=SourceRole.SUBSTRATE_EVIDENCE))
    ctx_text = memory.format_for_prompt(context, max_chars=1000)
    if ctx_text:
        blocks.append(RecallBlock(source=source, text=ctx_text, timestamp=None,
                                  freshness="living_recall", rationale="living_context",
                                  prompt_cost=len(ctx_text),
                                  role_hint=SourceRole.SUBSTRATE_CONTEXT))
    return blocks
```

- [ ] **Step 4: Run — PASS.** **Step 5: Commit** `feat(brain): living recall emits evidence/context role-hinted blocks (flag-gated)`

---

## Task 7: Framing — substrate turns use `SUBSTRATE_ONLY_NO_FRESH_VALIDATION`

**Files:** verify/adjust the composition that produces substrate-recall specs. Test: `tests/test_living_recall.py`

- [ ] **Step 1: Failing test** — with the flag on and two role-hinted substrate blocks, the rendered transcript contains BOTH `[memory evidence]` and `[memory context]` (i.e. the active framing permits both roles → no `_refuse_template_mismatch`).
- [ ] **Step 2: Run — FAIL or PASS** depending on the live composition hint for telegram substrate recall. **Verify which framing layer0 assigns** for a `TELEGRAM_SEMANTIC`-only substrate turn. If it is already `SUBSTRATE_ONLY_NO_FRESH_VALIDATION` (permits both) → test passes once Task 6 lands; if it assigns `SUBSTRATE_EVIDENCE_FRESH_CONTEXT` (permits evidence + FRESH_CONTEXT, not SUBSTRATE_CONTEXT) → the context block would be refused.
- [ ] **Step 3: Implement only if needed.** If the substrate-only turn is mis-framed, set the composition for substrate-recall-without-fresh turns to `SUBSTRATE_ONLY_NO_FRESH_VALIDATION` (the spec's chosen framing). Do **not** extend `_LEGAL_HINT_FRAMING`. (This task may be a no-op + a guard test; keep the assertion either way.)
- [ ] **Step 4: Run — PASS.** **Step 5: Commit** `test(living): substrate framing permits evidence+context`

---

## Task 8: Full verification + flag-off parity floor

- [ ] **Step 1:** `.venv/bin/python -m unittest tests.test_living_recall tests.test_memory_manager tests.test_dispatcher_merge tests.test_per_block_role_contract -v 2>&1 | tail -15` — all PASS.
- [ ] **Step 2 (parity):** a test asserting that with the flag **absent**, `_memory_manager_adapter` output and the rendered transcript are identical to pre-change for a seeded recall (the safety floor).
- [ ] **Step 3 (floor):** `.venv/bin/python -m unittest discover -s tests -p 'test_*.py' 2>&1 | tail -6` — no NEW failures beyond the documented floor (`web_search_direct_caller_inventory`, `service_audit…cloud_retirement` [flaky], `owner_bridge_chat…envelope`).
- [ ] **Step 4:** `.venv/bin/ruff check memory/memory_manager.py core/brain/brain_loop.py daemon/maez_daemon.py`
- [ ] **Step 5: Commit** `test(living): flag-off parity + floor`

---

## Task 9: Live three-way witness (Claude; flag via launch-env, under the unit)

After diff verification. Protocol mirrors Obs 17/18: `systemctl --user stop maez` → launch with `MAEZ_LIVING_RECALL_ENABLED=1` (launch-env only, NOT config/.env) → probes → restore (`kill` + `systemctl --user start maez`). Predicted-effect written before the window. **All three must pass:**
1. **Stale meta-memory stops surfacing as evidence:** "what were we talking about earlier?" → recent thread (evidence); "what have we discussed recently?" → recent material; any months-old journal appears at most as `[memory context]`, never `[memory evidence]`.
2. **Recent/fresh asks improve.**
3. **Deep recall NOT buried:** a deliberately old, explicitly-named memory still *appears* (as context). The falsifier.
Record in a witness doc; persist default-on only on a clean three-way pass (Rohit's act).

---

## Self-Review (against rev-3 spec)
**Coverage:** recency_factor gentle decay (T1); overfetch-before-rerank + effective-distance distance-space (T2); two decoupled knobs — `RANKING_HALF_LIFE_DAYS` order vs `EVIDENCE_RECENCY_DAYS` label (T1/T2); core→context (T2); continuity faculty (T3); promotion shadow-only (T4); flag (T5); two role-hinted blocks via the landed contract + flag-off parity (T6); framing `SUBSTRATE_ONLY_NO_FRESH_VALIDATION` (T7); telegram-only / `recall_for_cycle` untouched (new method, never called by cycle — T2/T8); three-way witness (T9). ✓

**Honest caveats (not hidden):** (a) several test *bodies* (T2/T3/T6) point to `tests/test_memory_manager.py`'s temp-dir seeding rather than inlining Chroma fixture construction — production steps are concrete. (b) T7 may be a no-op guard depending on the live composition hint — the executor must **verify which framing layer0 assigns to a TELEGRAM_SEMANTIC substrate turn** before assuming; the task documents both branches. (c) `format_for_prompt` is called per-partition — confirm it renders an empty-tier dict as `""` (it returns `""` when core/daily/raw all empty — verified at memory_manager.py:1775) so empty partitions emit no block.

**Type consistency:** `recency_factor(age_hours, half_life_days)`, `recall_for_telegram_living(query, *, half_life_days, evidence_recency_days) -> (evidence, context)`, `RecallBlock(..., role_hint=SourceRole.X)`, `_living_recall_enabled()` — consistent T1-T9.
