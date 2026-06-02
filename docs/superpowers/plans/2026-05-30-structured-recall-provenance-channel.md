# Structured Recall Provenance Channel — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development or executing-plans. Checkbox steps.
>
> From spec `docs/superpowers/specs/2026-05-30-structured-recall-provenance-channel-design.md` (Rohit-amended: 3 load-bearing invariants + the full runtime boundary). Branch off `main` (HEAD `3086d26`).

**Goal:** Carry recalled memory items as structured data (`RecallItem`) from the recall adapter through merge and the dispatcher boundary to `assemble_working_set`, which builds substrate evidence items from that data — so date provenance and full content survive even when the rendered prompt is truncated.

**Architecture:** `RecallBlock.items` (the adapter populates from the rows it already has) → `RenderedTurn.recall_items` → `_DispatcherPathResult.recall_items` → `handle_message(recall_items=…)` → `assemble_working_set(recall_items=…)`, which builds substrate `EvidenceItem`s from the structured items (transcript only for fresh/web; chat_history for anchor). `recall_items=None` falls back to today's regex parse.

**Tech Stack:** Python 3, `unittest` (`.venv/bin/python -m unittest`), `ruff`.

**THREE LOAD-BEARING INVARIANTS (Rohit):**
- **I1 (role wins):** `RecallItem.source_type` follows the *rendered/legal role* of its block, never the raw pre-merge partition. Context-only block → all items `memory_context`; evidence-only → only evidence-eligible carried; both legal → items follow their separate blocks. No `memory_evidence` leaking through a context block.
- **I2 (budget-immune provenance, bounded prompt):** `items` carry full text through recall/merge (provenance never truncation-erased), but `assemble`/focused cognition still enforce an *item-aware* working-set budget — truncate item *text* after selection, never drop `durable_id`/`temporal_provenance`, never create/remove `date_confirmed`.
- **I3 (no accidental raw-text telemetry):** `RecallBlock.to_dict()` / observation envelopes must not serialize full `RecallItem.text`; expose `durable_id`/`source_type`/`temporal_provenance` only.

---

## File map
- `core/dispatcher/layer1.py` — `RecallItem`; `RecallBlock.items` (+ `to_dict` discipline, I3).
- `core/brain/brain_loop.py` — `_living_memory_manager_adapter` populates `items` (I1); `_DispatcherPathResult.recall_items`; `_run_dispatcher_pipeline` carries them.
- `core/dispatcher/merge.py` — `RenderedTurn.recall_items`; aggregate from blocks.
- `daemon/maez_daemon.py` — `handle_message(recall_items=None)`; pass to `assemble_working_set`.
- `core/routing/focused_cognition.py` — `assemble_working_set(recall_items=None)` builds substrate from items (I2 budget); regex path = `None` fallback.
- Tests: `tests/test_focused_cognition.py`, `tests/test_living_recall.py`, dispatcher/merge tests.

---

## Task 1: `RecallItem` + `RecallBlock.items` (+ telemetry discipline I3)

**Files:** `core/dispatcher/layer1.py`. Test: `tests/test_dispatcher_layer1.py` (or the existing layer1 test module).

- [ ] **Step 1: RED test**
```python
class RecallItemTests(unittest.TestCase):
    def test_recall_item_fields_and_block_default(self):
        from core.dispatcher.layer1 import RecallItem, RecallBlock
        from core.dispatcher.spec import SubstrateSource
        it = RecallItem(text="full memory body", source_type="memory_context",
                        durable_id="core-1", temporal_provenance={"method":"exact_date","confirmed":True})
        self.assertEqual(it.source_type, "memory_context")
        self.assertTrue(it.temporal_provenance["confirmed"])
        b = RecallBlock(source=SubstrateSource.TELEGRAM_SEMANTIC, text="rendered", timestamp=None,
                        freshness="living_recall", rationale="x", prompt_cost=8)
        self.assertEqual(b.items, ())   # default empty

    def test_to_dict_does_not_serialize_item_text(self):
        from core.dispatcher.layer1 import RecallItem, RecallBlock
        from core.dispatcher.spec import SubstrateSource
        b = RecallBlock(source=SubstrateSource.TELEGRAM_SEMANTIC, text="rendered", timestamp=None,
                        freshness="living_recall", rationale="x", prompt_cost=8,
                        items=(RecallItem(text="SECRET FULL MEMORY", source_type="memory_context",
                                          durable_id="core-1", temporal_provenance=None),))
        d = b.to_dict()
        self.assertNotIn("SECRET FULL MEMORY", str(d))   # I3: no raw item text in telemetry
```

- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement.** In `core/dispatcher/layer1.py` add (above `RecallBlock`):
```python
@dataclass(frozen=True)
class RecallItem:
    text: str
    source_type: str                       # "memory_evidence" | "memory_context"
    durable_id: str | None = None
    temporal_provenance: dict | None = None
```
Add to `RecallBlock`: `items: tuple[RecallItem, ...] = ()`. In `RecallBlock.to_dict`, **do not** add `items`/`text`-of-items; if a structured summary is wanted, add only ids/source_type/provenance:
```python
        if self.items:
            payload["items"] = [
                {"durable_id": i.durable_id, "source_type": i.source_type,
                 "temporal_provenance": i.temporal_provenance}
                for i in self.items
            ]
```
- [ ] **Step 4: Run → PASS.** **Step 5: Commit** `feat(dispatcher): RecallItem + RecallBlock.items structured channel (telemetry-safe)`

---

## Task 2: Adapter populates `items` following the rendered role (I1)

**Files:** `core/brain/brain_loop.py` (`_living_memory_manager_adapter`). Test: `tests/test_living_recall.py`.

- [ ] **Step 1: RED in-process tests** (I1 is the load-bearing one):
```python
    def test_adapter_items_carry_full_content_and_provenance(self):
        # dated query; seed a LONG date_confirmed core memory that overflows the render budget.
        # The RecallBlock.items must carry FULL untruncated text + temporal_provenance.confirmed=True,
        # even though block.text is budget-truncated.
        ...
        block = [b for b in blocks if b.items][0]
        self.assertTrue(any(i.temporal_provenance and i.temporal_provenance["confirmed"] for i in block.items))
        self.assertTrue(any(len(i.text) > len(block.text) for i in block.items))  # items not truncated

    def test_context_only_framing_items_are_all_memory_context(self):
        # under a context-only framing (SUBSTRATE_CONTEXT / hybrid), NO item may be memory_evidence.
        ...
        for b in blocks:
            for i in b.items:
                self.assertEqual(i.source_type, "memory_context")
```

- [ ] **Step 2: Run → FAIL** (adapter doesn't populate items yet).
- [ ] **Step 3: Implement.** In `_living_memory_manager_adapter`, when emitting each `RecallBlock`, populate `items` from the recalled rows that fed that block, with `source_type` set to **the block's rendered role**, not the raw partition:
```python
        def _items_for(rows, role_source_type):
            out = []
            for mem in rows or []:
                meta = mem.get("metadata") or {}
                method = meta.get("temporal_match_method")
                prov = ({"method": method, "confirmed": method in ("exact_date", "month_window")}
                        if method else None)
                out.append(RecallItem(
                    text=sanitize_prompt_text(mem.get("content", "")),   # full content, not budget-bounded
                    source_type=role_source_type,
                    durable_id=str(mem.get("id") or "") or None,
                    temporal_provenance=prov,
                ))
            return tuple(out)
```
Wire it per the existing role branches: where the adapter emits an evidence block (`role_hint=SUBSTRATE_EVIDENCE`) use `role_source_type="memory_evidence"` over the evidence rows; where it emits a context block (`SUBSTRATE_CONTEXT`) use `"memory_context"` over the context rows; under the combined/context-only framing (single SUBSTRATE_CONTEXT block carrying both partitions), ALL items are `"memory_context"` (I1). Attach `items=_items_for(...)` to the matching `RecallBlock(...)`. Import `RecallItem` from `core.dispatcher.layer1`.
- [ ] **Step 4: Run → PASS.** **Step 5: Commit** `feat(brain_loop): living adapter emits structured RecallItems following rendered role (I1)`

---

## Task 3: Carry `recall_items` across merge → dispatcher → handle_message

**Files:** `core/dispatcher/merge.py`, `core/brain/brain_loop.py`, `daemon/maez_daemon.py`. Test: merge test + a boundary test.

- [ ] **Step 1: RED test** — assert `recall_items` survives each hop: `merge_fanout_results(...).recall_items` is non-empty for a substrate recall; `_run_dispatcher_pipeline(...).recall_items` carries it; `handle_message` accepts `recall_items=`.
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement the four hops:**
  1. `RenderedTurn` (merge.py:49) gains `recall_items: tuple[RecallItem, ...] = ()`. In `merge_fanout_results`, aggregate: `recall_items = tuple(i for b in recall_blocks for i in b.items)` (substrate blocks; fresh/web have none) and pass into the `RenderedTurn(...)` construction (and the `_rendered_turn` helper at ~444).
  2. `_DispatcherPathResult` (brain_loop.py:79) gains `recall_items: tuple[RecallItem, ...] = ()`. `_run_dispatcher_pipeline` sets it from the merge result (`rendered.recall_items`) at the success construction (~799); the early returns (~623) default to `()`.
  3. Thread from `_DispatcherPathResult` to `handle_message` along the existing transcript path (whatever passes `transcript=result.transcript` today passes `recall_items=result.recall_items` too — adapt to the real intermediate, e.g. `BrainLoopResult`/`maez_adapter`; the contract is: the same object that carries `transcript` now also carries `recall_items`).
  4. `handle_message` (daemon:3184) signature gains `recall_items: "list | None" = None`.
- [ ] **Step 4: Run → PASS.** **Step 5: Commit** `feat: thread recall_items RenderedTurn→_DispatcherPathResult→handle_message`

---

## Task 4: `assemble_working_set` builds substrate from `recall_items` (+ item-aware budget I2)

**Files:** `core/routing/focused_cognition.py`. Test: `tests/test_focused_cognition.py`.

- [ ] **Step 1: RED tests** (the live-witness failure, now deterministic):
```python
class StructuredRecallChannelTests(unittest.TestCase):
    def test_recall_items_carry_confirmed_no_status(self):
        from core.dispatcher.layer1 import RecallItem
        from core.routing.focused_cognition import assemble_working_set
        items = [RecallItem(text="INFRASTRUCTURE GROUND-TRUTH 2026-04-27 ...long...",
                            source_type="memory_context", durable_id="core-1",
                            temporal_provenance={"method":"exact_date","confirmed":True})]
        ws = assemble_working_set(transcript="[memory context]\n(truncated junk no closing tag",
                                  web_context="", owner_question="what did we note around April 27?",
                                  recall_items=items)
        self.assertIsNotNone(ws)
        # date_confirmed survived → primary, NO temporal_recall_status
        self.assertFalse(any(i.source_type == "temporal_recall_status" for i in ws.items))
        top = ws.items[0]
        self.assertEqual(top.source_type, "memory_context")
        self.assertTrue(top.temporal_provenance["confirmed"])
        self.assertIn("INFRASTRUCTURE GROUND-TRUTH", top.text)   # FULL content, not truncated

    def test_recall_items_none_falls_back_to_transcript(self):
        # existing transcript-parse behavior preserved when recall_items is None
        ...

    def test_item_aware_budget_preserves_provenance(self):
        # with a tiny working-set budget, item TEXT may be truncated but temporal_provenance + durable_id
        # are preserved and confirmed is unchanged (I2)
        ...
```
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement.** `assemble_working_set(..., recall_items: list | None = None)`:
  - When `recall_items` is not None: build the substrate `raw_items` from them — `(item.source_type, item.text, item.durable_id, item.temporal_provenance)` — instead of parsing `[memory context]`/`[memory evidence]` from the transcript. Still parse `[fresh evidence]`/web from the transcript and the dialogue anchor from `chat_history`. The date-cue precedence + `date_confirmed`/status logic read `item.temporal_provenance["confirmed"]` from these structured items.
  - **I2 item-aware budget:** apply the working-set char budget AFTER ranking/selection by truncating each selected item's `text` (keep `durable_id`/`temporal_provenance`/`source_type` intact); never let truncation change `confirmed` or drop the item's provenance.
  - When `recall_items is None`: the existing transcript-parse path (`_memory_items_with_provenance`) runs unchanged.
- [ ] **Step 4: Run → PASS** + full focused suite green (fallback path unchanged). **Step 5: Commit** `fix(focused): assemble builds substrate from structured recall_items; item-aware budget (I2)`

---

## Task 5: Daemon wires recall_items into the assemble call

**Files:** `daemon/maez_daemon.py`. Test: `tests/test_memory_integrity_invariant.py`.

- [ ] **Step 1: RED daemon-path test** — a dated turn whose dispatcher recall produced a long `date_confirmed` memory yields a focused working set with `date_confirmed` + full content and **no** `temporal_recall_status` (end-to-end through handle_message).
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement.** In `handle_message`, pass the threaded `recall_items` into the `_assemble_working_set(transcript=transcript, ..., recall_items=recall_items)` call (daemon ~3969). The B5 `_had_confirmed` check (Slice 2) already reads `_focused_working_set.items[*].temporal_provenance` — now sourced from the structured channel, so it's correct end-to-end.
- [ ] **Step 4: Run → PASS.** **Step 5: Commit** `fix(daemon): pass structured recall_items into assemble_working_set`

---

## Task 6: Integration + regression + lint

- [ ] **Step 1:** Integration (`tests/test_living_recall.py`): full `dispatcher → merge → daemon-style assemble` for "around April 27" with a long live-shaped dated memory → working-set item is `date_confirmed`, full INFRASTRUCTURE GROUND-TRUTH content, no status item.
- [ ] **Step 2:** `.venv/bin/python -m unittest tests.test_dispatcher_layer1 tests.test_focused_cognition tests.test_living_recall tests.test_memory_integrity_invariant -v` → OK (fallback/non-dated/Slice-2 precedence all green).
- [ ] **Step 3:** `.venv/bin/ruff check core/dispatcher/layer1.py core/dispatcher/merge.py core/brain/brain_loop.py daemon/maez_daemon.py core/routing/focused_cognition.py` → clean.
- [ ] **Step 4:** Broad floor: only the 2 documented pre-existing failures. Report honestly.
- [ ] **Step 5: Commit** `test: structured recall channel integration + regression`

---

## Witness (Claude, after green): FULL 6-role switchboard (touches the recall→assemble contract across 5 files), THEN dated re-witness
Full switchboard on the diff — Logical (the dual-mode assemble + I2 budget correctness), Adversary (I1 role-leak: can a context item ever carry memory_evidence? I3 telemetry: any raw item text in logs/to_dict?), Body-Coherence (does the full-content delivery + honest dated recall restore the bond's memory truthfulness?). Then live flag-on dated re-witness: "around April 27" → full April-27 incident as `date_confirmed` context, **no** spurious "no dated memory" status; the both-shaped + incidental + continuity probes unchanged. Green → **the triad graduates** (dated recall honest AND complete) → eligible for the explicit default-on decision.

## Self-Review
**Spec coverage:** RecallItem + RecallBlock.items + I3 telemetry (Task 1) ✓; adapter populates following rendered role I1 (Task 2) ✓; merge→_DispatcherPathResult→handle_message boundary, all four hops (Task 3) = the amended boundary ✓; assemble builds from structured items + I2 item-aware budget + None fallback (Task 4) ✓; daemon wiring + B5 read from structured channel (Task 5) ✓; integration/regression/witness (Task 6) ✓.
**Placeholder scan:** Task 1/3/4/5 carry concrete code; Task 2's `_items_for` is full code with the I1 role-following rule spelled out; the in-process test bodies (Task 2/4/5/6) describe exact setup + assertions (long-dated-memory-overflows-budget; context-only-framing-all-context; recall_items-None-fallback; item-aware-budget-preserves-provenance) for the executor to wire to the existing fixtures.
**Type consistency:** `RecallItem{text,source_type,durable_id,temporal_provenance}` identical across layer1/adapter/merge/assemble; `recall_items` param name consistent (`RenderedTurn`/`_DispatcherPathResult`/`handle_message`/`assemble_working_set`); `temporal_provenance={method,confirmed}` matches v2 EvidenceItem + Slice-2 daemon read; `source_type` ∈ {memory_evidence, memory_context} matches `_SOURCE_TYPE`.
