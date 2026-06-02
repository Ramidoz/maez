# Living `[memory context]` — Compact Renderer (final repair seam)

> RED-first, unittest only. Branch `living-memory-recency-salience`. No daemon/prod, no commit until verified.

**Goal:** The selected deep memory already reaches the context partition (content-addressed selection works). It's lost only because the context block is rendered with `format_for_prompt()`, whose ~600-char `=== PAST OBSERVATIONS … ===` warning header consumes the tiny role-hinted context budget before any `<RECALLED>` row appears. Fix = a **compact renderer for the living `[memory context]` block only**.

**Strict scope (Rohit):** Do **not** change `memory.format_for_prompt()` (correct for the legacy megaprompt), recall/ranking, `deep_context_priority`, or Layer1/merge/render. Do **not** add temporal/date parsing (that's the next slice). Role stays `SUBSTRATE_CONTEXT` / `[memory context]` — **never evidence**. Witness is **content-anchored**, not date-anchored.

## Task 1: Compact living-context formatter

**Files:** `memory/memory_manager.py` (new `format_living_context`), `core/brain/brain_loop.py` (adapter uses it for the context block only). Test: `tests/test_living_recall.py`.

- [ ] **Step 1: RED test — IN-PROCESS (the hard gate; no live witness until this passes)**
```python
def test_content_anchored_deep_context_renders_and_is_seen(self):
    import os, time
    os.environ["MAEZ_LIVING_RECALL_ENABLED"]="1"; os.environ["MAEZ_DISPATCHER_ENABLED"]="1"
    from core.dispatcher.layer0 import Layer0Dispatcher
    from core.dispatcher.inventory import InventoryRegistry
    from core.dispatcher.spec import SubstrateSource, ExternalSource
    from core.dispatcher.layer1 import Layer1Fanout
    from core.dispatcher.external_sources import ExternalFanout
    from core.dispatcher.merge import merge_fanout_results
    from core.brain.brain_loop import _dispatcher_index, _dispatcher_recall_adapters
    from core.routing.focused_cognition import assemble_working_set
    q="What's the infrastructure ground-truth you noted earlier?"   # content-anchored, no date
    inv=InventoryRegistry().summarize([*SubstrateSource,*ExternalSource])
    spec=Layer0Dispatcher(index=_dispatcher_index()).emit_spec(q, surface="telegram_surface", inventory=inv)
    ad=_dispatcher_recall_adapters(q, spec=spec, surface="telegram_surface", chat_history=[{"role":"user","content":"x"}])
    cs={"bond_id":"b","surface":"telegram_surface","chat_id":"c"}
    l1=Layer1Fanout(adapters=ad,branch_timeout_s=3.0,global_deadline_s=4.0).run(spec,utterance=q,conversation_state=cs,fanout_generation_id="g")
    ext=ExternalFanout().run(spec,utterance=q,conversation_state=cs,fanout_generation_id="g")
    tx=merge_fanout_results(spec,l1,ext,utterance=q,surface="telegram_surface",timestamp=time.strftime('%Y-%m-%dT%H:%M:%S')).prompt_block
    self.assertIn("[memory context]", tx)
    self.assertIn("infrastructure ground-truth", tx.lower())          # the note reaches the desk
    ws=assemble_working_set(transcript=tx, web_context="", owner_question=q)
    self.assertTrue(ws and any("infrastructure ground-truth" in i.text.lower()
                               and i.source_type=="memory_context" for i in ws.items))
```
**Note:** this uses the live shared Chroma (the infra-ground-truth core memory exists). If CI lacks it, add a seeded-temp-Chroma variant per `tests/test_memory_manager.py`; keep this live-Chroma version too — it's the in-process witness.

- [ ] **Step 2: Run — FAIL** (today: `[memory context]` present but `infrastructure ground-truth` truncated by the 600-char header at the 300 budget).

- [ ] **Step 3: Implement.** In `memory/memory_manager.py`, add a compact formatter (reuse the existing `<RECALLED>` row-rendering; lean one-line header):
```python
def format_living_context(self, recalled: dict, max_chars: int) -> str:
    """Compact renderer for the living [memory context] block.

    Unlike format_for_prompt (legacy megaprompt), the role-hinted context
    block is tiny; its 600-char PAST OBSERVATIONS warning would eat the
    whole budget. The [memory context] label + per-row age already signal
    'past', so one lean line suffices, then the selected RECALLED rows.
    """
    core = recalled.get("core") or []
    daily = recalled.get("daily") or []
    raw = recalled.get("raw") or []
    if not (core or daily or raw):
        return ""
    now = datetime.now(timezone.utc)
    lines = ["Past memory context, not current state."]
    # render dynamic rows then core, each as a <RECALLED .../> row (reuse the
    # same per-entry rendering format_for_prompt uses for tier/age/id/content).
    for tier, rows in (("daily", daily), ("raw", raw), ("core", core)):
        for mem in rows:
            meta = mem.get("metadata") or {}
            mem_id = str(mem.get("id", ""))[:16]
            age = (_humanize_daily_age(meta.get("date",""), now) if tier=="daily"
                   else _humanize_age(meta.get("timestamp"), now) if tier=="raw"
                   else "permanent")
            content = sanitize_prompt_text(mem.get("content", ""))
            lines.append(f'<RECALLED tier="{tier}" age="{age}" id="{mem_id}">')
            lines.append(content)
            lines.append("</RECALLED>")
    out = "\n".join(lines)
    return out[:max_chars] if max_chars and len(out) > max_chars else out
```
(Match the exact `<RECALLED>` attribute shape `format_for_prompt` emits so `assemble_working_set`'s `id="…"` parsing + the adapter's `_rendered_partition` id-extraction still work. Verify against the real `format_for_prompt` body before finalizing.)

In `core/brain/brain_loop.py` `_living_memory_manager_adapter`, render the **context block** with the compact formatter (leave the evidence block on `format_for_prompt`):
```python
ctx_text = _bounded_text(memory.format_living_context(context_for_prompt, max_chars=context_budget), limit=context_budget)
```

- [ ] **Step 4: Run — PASS** (in-process gate green). **Step 5:** focused/adjacent suites + ruff. **Step 6: Commit** `fix(memory): compact living [memory context] renderer (header no longer eats the budget)`

## Task 2: One live witness (Claude; after Task 1 in-process green) — revised scope
Honest scope revision (record in the witness doc): **this slice proves recency-salience + same-turn self-echo suppression + content-addressed deep context. Date-anchored/temporal recall is explicitly OUT of scope (next slice).**
Probes (content-anchored): recency/local-AI; continuity; **"What's the infrastructure ground-truth you noted earlier?"** (content-addressed deep recall). Gates: self-echo gone from evidence; recent→evidence; **content-addressed deep memory reaches + is cited as `[memory context]`**; freshness ask doesn't promote stale to evidence; shadow-only.
**Continuity-synthesis** (anchor present but not cited) is a separate boundary-pinned fix; if still failing, **land flag-off and record it as a named default-on blocker** (Rohit's rule), do not block the flag-off merge.

## Out of scope / next slices
- Date-anchored **temporal recall** (date extraction + temporal filter/boost) — its own slice + witness.
- **Continuity-synthesis** (make the dialogue anchor the cited authority for continuity asks) — own small RED-first fix before default-on.
