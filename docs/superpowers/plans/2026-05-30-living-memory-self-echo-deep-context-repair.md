# Living Memory Repair — Self-Echo Suppression + Deep Context Selection

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development or superpowers:executing-plans. RED-first, checkbox steps. unittest only (`.venv/bin/python -m unittest …`; pytest not installed).

**Goal:** On branch `living-memory-recency-salience`, fix the two real (in-process-proven) bugs so the living-recall witness can finally cross gate 3: (1) the current query's echo must not occupy `[memory evidence]`; (2) the query-relevant deep/old memory must reach the rendered `[memory context]`.

**Architecture:** Both fixes live in `memory/memory_manager.recall_for_telegram_living` + the `brain_loop` living adapter. The recency engine, partition shape, per-block role contract, and render are already proven correct in-process — **do not** touch Layer1/merge/render. Two RED-first tasks, one branch, strictly sequenced (self-echo first — it pollutes the input both fixes depend on).

**Proven context (in-process root-cause, 2026-05-30):** split renders both labels; focused cognition already consumes `[memory context]` (`E2`); the failures are (a) `age=0d` query-echo rows topping EVIDENCE, and (b) the rendered context lacking April-6 because the adapter does `core:[]` and `recall_for_telegram_living` puts all 90 core in context **unranked**.

**Design constraint (Rohit, binding):** `[memory context]` is **past/background, citeable for explicitly-old/continuity asks — never promoted to `[memory evidence]` authority for present-tense claims.** And: **do NOT make all core eligible for the tiny context budget** — it must be query-relevance-selected, or we recreate "90 unranked core rows."

---

## Task 1: Self-echo suppression (strict — exclude, don't demote)

**Files:** Modify `memory/memory_manager.py` (`recall_for_telegram_living`); Test: `tests/test_living_recall.py`

If the owner side of a **recent** `telegram_exchange` candidate normalizes to the **same** question as the current query, drop it from living recall **entirely** — it's a copy of the ask, not memory of the answer.

- [ ] **Step 1: RED test**
```python
def test_query_echo_excluded_from_evidence(self):
    # seed a telegram_exchange whose owner side == the current query, age ~0
    # (see tests/test_memory_manager.py seeding). Then:
    ev, ctx = mm.recall_for_telegram_living("What did we note back around April 6 about the infrastructure?")
    def _texts(p): return " ".join((m.get("content","") for tier in ("raw","daily","core") for m in (p.get(tier) or [])))
    # the echoed question must NOT appear in EVIDENCE (strict: nor in context)
    self.assertNotIn("What did we note back around April 6", _texts(ev))
    self.assertNotIn("the owner (telegram_surface): What did we note back around April 6", _texts(ev))
```
**Executor:** seed via the temp-dir MemoryManager pattern in `tests/test_memory_manager.py`; the echo row metadata `type="telegram_exchange"`, `timestamp` = now, content = `"the owner (telegram_surface): What did we note back around April 6 about the infrastructure?"`.

- [ ] **Step 2: Run — FAIL** (`.venv/bin/python -m unittest tests.test_living_recall.<Class>.test_query_echo_excluded_from_evidence -v`)

- [ ] **Step 3: Implement.** Add a normalizer + echo predicate near the module helpers in `memory/memory_manager.py`:
```python
import re as _re_echo  # or reuse existing `re`

def _normalize_for_echo(text: str) -> str:
    return _re_echo.sub(r"\s+", " ", _re_echo.sub(r"[^\w\s]", " ", (text or "").lower())).strip()

_ECHO_OWNER_PREFIXES = ("the owner", "rohit asked:", "rohit:", "owner:")

def _row_is_query_echo(content: str, query_norm: str) -> bool:
    """True when a telegram_exchange row's owner side is the current query echoed."""
    c = _normalize_for_echo(content)
    if not c or not query_norm:
        return False
    # strict: the normalized query is the owner-side question of this row
    return query_norm in c and any(c.startswith(_normalize_for_echo(p)) for p in _ECHO_OWNER_PREFIXES) or c == query_norm
```
In `recall_for_telegram_living`, after the candidate pools are built (raw + the merged telegram-exchange supplement) and **before** ranking/partition, filter:
```python
query_norm = _normalize_for_echo(query)
def _keep(mem):
    return not _row_is_query_echo(mem.get("content", ""), query_norm)
raw = [m for m in raw if _keep(m)]
daily = [m for m in daily if _keep(m)]
```
Apply the same `_keep` to the continuity-anchor thread source if it pulls exchange rows.

- [ ] **Step 4: Run — PASS.** **Step 5: Commit** `fix(memory): exclude current-query echo from living recall (strict)`

---

## Task 2: Deep context selection (query-relevant core, ranked — NOT all core)

**Files:** Modify `memory/memory_manager.py` (`recall_for_telegram_living` context build) + `core/brain/brain_loop.py` (adapter's `context_for_prompt`); Test: `tests/test_living_recall.py`

`recall_for_telegram_living` must put **query-relevant** core into context (semantic top-K), not all 90; and the adapter must **render that core** (stop dropping it with `core:[]`), capped to the context budget.

- [ ] **Step 1: RED test — selection**
```python
def test_relevant_core_selected_into_context(self):
    # seed a core memory: "[Journal 2026-04-06] ... infrastructure ground-truth ..."
    # plus several irrelevant core rows.
    ev, ctx = mm.recall_for_telegram_living("What did we note back around April 6 about the infrastructure?")
    core_text = " ".join(m.get("content","") for m in (ctx.get("core") or []))
    self.assertIn("2026-04-06", core_text)                 # relevant core present in CONTEXT
    self.assertLessEqual(len(ctx.get("core") or []), 5)    # ranked/capped, NOT all 90
    # and NOT in evidence (stays context/background)
    ev_text = " ".join(m.get("content","") for tier in ("raw","daily","core") for m in (ev.get(tier) or []))
    self.assertNotIn("2026-04-06", ev_text)
```

- [ ] **Step 2: RED test — synthesis (the real gate, in-process)**
```python
def test_focused_synthesis_uses_april_context(self):
    # build the live rendered transcript (Layer0 emit_spec -> adapters -> Layer1.run
    # -> merge_fanout_results -> rt.prompt_block) exactly as the in-process repro,
    # with MAEZ_LIVING_RECALL_ENABLED=1, for the April query.
    self.assertIn("[memory context]", transcript)
    self.assertIn("2026-04-06", transcript)                # April-6 reaches rendered context
    ws = assemble_working_set(transcript=transcript, web_context="", owner_question=q)
    self.assertTrue(any(("2026-04" in i.text or "april" in i.text.lower())
                        and i.source_type == "memory_context" for i in ws.items))
```
**Executor:** lift the in-process repro from the root-cause witness doc (Layer0Dispatcher.emit_spec → `_dispatcher_recall_adapters(..., surface="telegram_surface")` → `Layer1Fanout.run(..., fanout_generation_id="g")` → `ExternalFanout().run(..., fanout_generation_id="g")` → `merge_fanout_results`). This is the faithful synthesis boundary.

- [ ] **Step 3: Run — FAIL** (both)

- [ ] **Step 4: Implement.**
(a) In `recall_for_telegram_living`, replace the unconditional `core = self.get_all_core()` *for the context partition* with a **query-relevant** selection (keep `get_all_core` only if some flow still needs all):
```python
core_relevant = self._query_collection(self.core, query, n=3, record_recalls=False)
# context core = semantically relevant core (NOT recency-decayed — context is the
# past/background tier; an explicitly-old ask should surface the matching old memory)
context = {"core": core_relevant, "daily": [...old...], "raw": [...old...]}
```
(Evidence partition keeps `core: []` — core is never evidence authority. Verify `get_all_core` callers elsewhere are unaffected; this change is scoped to the context partition.)

(b) In `core/brain/brain_loop.py` `_living_memory_manager_adapter`, **remove the `core:[]` drop** so the relevance-selected core renders. Replace:
```python
context_for_prompt = context
if (context.get("daily") or context.get("raw")):
    context_for_prompt = {"core": [], "daily": context.get("daily") or [], "raw": context.get("raw") or []}
```
with:
```python
# context already carries query-relevant (small) core + old dynamic rows; render as-is,
# capped by the context budget. Do NOT drop core — that buried explicitly-asked deep memory.
context_for_prompt = context
```
The existing `_bounded_text(format_for_prompt(context_for_prompt, max_chars=context_budget), limit=context_budget)` caps it before render.

- [ ] **Step 5: Run — PASS** (both). **Step 6: Commit** `fix(memory): query-relevant core into [memory context]; stop dropping core`

---

## Task 3: Guards (RED, must stay green)

**Files:** Test: `tests/test_living_recall.py`

- [ ] **Guard A — freshness ask doesn't promote old context to evidence:**
```python
def test_present_ask_keeps_old_core_out_of_evidence(self):
    ev, ctx = mm.recall_for_telegram_living("How are you doing right now?")
    ev_text = " ".join(m.get("content","") for tier in ("raw","daily","core") for m in (ev.get(tier) or []))
    self.assertNotIn("2026-04-06", ev_text)   # old core never enters EVIDENCE
```
- [ ] **Guard B — promotion_score stays shadow-only:** keep/confirm the existing `test_promotion_not_applied` (patch `promotion_score` high vs low → identical ordering).
- [ ] Run both; commit `test(memory): guards for evidence/context boundary + shadow promotion`

---

## Task 4: Verification
- [ ] `.venv/bin/python -m unittest tests.test_living_recall tests.test_surface_adapter tests.test_per_block_role_contract -v` — all PASS.
- [ ] `.venv/bin/ruff check memory/memory_manager.py core/brain/brain_loop.py`
- [ ] Broad floor in the worktree is env-noisy (missing `config/.env`); not a clean signal — run focused suites + report honestly, do not claim broad green.
- [ ] Commit.

## Out of scope / next
- No Layer1/merge/render changes (proven correct). No new flag (rides `MAEZ_LIVING_RECALL_ENABLED`).
- After GREEN: Claude transplants the (now larger) file set to main + runs **one** witness (path b), with the synthesis test having already pinned the boundary in-process. No more render/budget changes unless a NEW in-process synthesis test proves that boundary failing.

## Self-Review
**Coverage:** self-echo strict-exclude (T1) + its RED; query-relevant core selected + capped, core no longer dropped, NOT all-90 (T2a); in-process synthesis cites April context (T2b — the real gate); freshness guard (T3A); shadow-only guard (T3B). Design constraint honored: context relevance-ranked but role_hint stays `SUBSTRATE_CONTEXT`. **Honest caveat:** several test bodies reference the temp-dir seeding in `tests/test_memory_manager.py` and the in-process repro in the witness doc rather than inlining — production steps are concrete.
**Types:** `_normalize_for_echo`, `_row_is_query_echo(content, query_norm)`, `recall_for_telegram_living(...) -> (evidence, context)` unchanged signature; `context["core"]` = query-relevant rows.
