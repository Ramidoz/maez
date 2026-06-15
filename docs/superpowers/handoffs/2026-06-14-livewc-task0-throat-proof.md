# Live Web-Context Containment — Task 0: Runtime Throat Proof

**Date:** 2026-06-14
**Branch:** `live-web-context-containment`
**Scope:** DOCS-ONLY proof gate. No behavior code changed. Hard GO/NO-GO.
**Purpose:** Prove every "throat" — every place fetched web content enters Maez's
reasoning prompt — exists at the spec's claimed seam BEFORE any wiring. This arc
exists because a prior build trusted a STATIC trace and wrapped the WRONG seam.
All citations below are verified against current live source line numbers (they
shifted from the spec's estimates; exact current lines recorded).

---

## THROAT 1 — focused-cognition final render

File: `core/routing/focused_cognition.py`, fn `assemble_working_set` (def `:727`).

- `_budget_items_for_prompt(...)` called at **`:858`-`:863`** — budgets/truncates
  items. Inside it, `_truncate_item_text` (def `:680`) is invoked at **`:723`**
  (`budgeted.append(replace(item, text=_truncate_item_text(item.text, allowance)))`).
- FINAL render: **`:865`** —
  `ordered = "\n".join(_render_evidence_lines(items, render_version=render_version))`
  **Var name = `ordered`.**
- `ordered` becomes `WorkingSet.ordered_evidence_text` at **`:870`**
  (`ordered_evidence_text=ordered`).
- That field enters the prompt at **`:913`** —
  `f"{working_set.ordered_evidence_text}"` inside the `system` string built at
  `:907`-`:914` (`=== EVIDENCE (cite [E#]) ===` block).

**Ordering proof (truncation BEFORE final render):** `_budget_items_for_prompt`
runs at `:858` and returns already-truncated `items` (truncation happens at
`:723`, inside it). The final render at `:865` consumes those returned `items`.
Therefore `:865` is unambiguously **post-truncation** — wrapping at `:865`
wraps already-truncated text. ✅

---

## THROAT 1 v1-repeat — top item rendered twice

File: `core/routing/focused_cognition.py`, fn `_render_evidence_lines` (def `:282`).

- **v2 branch** (`version == "v2"`, `:289`-`:299`): returns one line per item via a
  list comprehension over `items`. **No repeat.** ✅ (confirmed v2 does NOT repeat)
- **v1 branch** (`:300`-`:308`): builds `lines` (one per item), then at
  `:305`-`:307`:
  ```python
  if items:
      top = items[0]
      lines.append(f"(most important, repeated) [{top.local_label}] {top.text}")
  ```
  So the top item's text is emitted a SECOND time. A top item with
  `source_type == "web_context"` renders **TWICE = 2 segments** in the v1 prompt.
- Budgeter is aware of this: `_budget_items_for_prompt` weights index-0 as `2` in
  the v1 branch (`:716`-`:718`, `weights = [2 if index == 0 else 1 ...]`) precisely
  because "the first item's text is rendered twice." Containment wiring on a
  web_context top item under v1 must wrap BOTH segments. ✅

---

## THROAT 5 — photo-freshness fresh-world insertion

File: `core/routing/focused_cognition.py`, fn `synthesize_photo_turn` (def `:1134`).

- `base_system` base built `:1208`-`:1213`. When `fresh_context` is truthy
  (`:1214`), it is appended RAW at **`:1216`-`:1217`**:
  ```python
  base_system += (
      "\n\n=== FRESH WORLD CHECK (cite [E2] for current-world verification) ===\n"
      f"{fresh_context}\n\n"
      ...
  ```
  **Exact insertion line = `:1217`** (`f"{fresh_context}\n\n"`), under the
  `=== FRESH WORLD CHECK ...` header at `:1216`. `fresh_context` inserted raw. ✅

**Feeder** — File: `daemon/maez_daemon.py`, photo synth call **`:6428`-`:6437`**:
```python
_photo_result = _synthesize_photo_turn(
    analysis_text=photo_analysis,
    caption=text,
    surface=source,
    fresh_context=(
        web_context
        if _photo_freshness_query and web_context
        else None
    ),
)
```
`web_context` is passed as `fresh_context` exactly when `_photo_freshness_query`
is set and `web_context` is non-empty (**`:6432`-`:6434`**). Confirmed. ✅

---

## THROAT 2 — legacy (chat) prompt

File: `daemon/maez_daemon.py`, **`:5817`-`:5819`**:
```python
if web_context and not _empty_web_search:
    prompt += (
        f"{web_context}\n\n"
        ...
```
Legacy chat prompt concatenates `web_context` raw (`:5819`). Confirmed. ✅

---

## THROAT 3 — voice prompt

File: `daemon/maez_daemon.py`, **`:7471`-`:7472`**:
```python
if web_context:
    prompt += f"{web_context}\n\n"
```
Voice prompt concatenates `web_context` raw (`:7472`). Confirmed. ✅

---

## THROAT 4 — dispatcher truncation-safety — THE KEY VERIFY

**Question:** Rail 2 Layer A wraps fresh blocks in
`core/dispatcher/provenance_renderer.py::_render_prompt_block` via
`contain_fresh_text`. Does the dispatcher TRUNCATE the fresh block text AFTER
that wrap?

**Evidence:**

1. The wrap is applied per-summary at render time. In `_render_prompt_block`
   (`:161`), `_text_for(summary)` (`:172`-`:180`) calls
   `_fc.contain_fresh_text(summary.text, ...)` (`:174`) for fresh roles. The
   wrapped result is dropped directly into the section/inline string
   (REPORT: `:189`; inline: `:198`) and joined into `prompt_block` (`:190` /
   `:210`).
2. `prompt_block` flows UNCHANGED out: `render_provenance` returns it via
   `RenderedProvenance(prompt_block=prompt_block, ...)` (`:88`-`:92`), and
   merge.py passes it straight through (`:503`, `prompt_block=rendered.prompt_block`).
3. `summary.text` is built in `merge.py::source_summaries_for_render`
   (`:336`-`:381`) as the FULL `"\n".join(...)` of block texts
   (substrate `:360`, fresh `:373`) with **no truncation/slicing**. So the wrap
   at `:174` wraps the complete fresh text.
4. Grep for truncation/slicing/char-budget across BOTH files
   (`provenance_renderer.py` + `merge.py`) for
   `[:N] / [:_ ] / truncat / char_budget / max_chars / .slice / textwrap /
   shorten`: **ZERO hits.** Neither file truncates, slices, or budgets the fresh
   block text — before OR after the wrap.

**DECISION: (A)** — **No post-wrap truncation exists. Rail 2's existing wrap is
already safe.** Throat 4 reduces to a confirming test only (assert no future
post-wrap truncation regression). NOT a refutation. ✅

---

## THROAT 6 candidate — telegram_voice dead-inbound — THE OTHER REFUTATION POINT

File: `skills/telegram_voice.py`.

- **Module header (`:4`-`:11`):** verbatim —
  > "OUTBOUND-ONLY since 2026-04-20 (Surface V2 migration). The inbound methods
  > in this module (`_handle_message`, `_process_message`, the `_try_*_intent`
  > interceptors) DO NOT FIRE on live owner messages. Inbound Telegram routes
  > through `skills/surface/maez_adapter.py`."
- **The `web_context` insertion (`:3756`-`:3760`):**
  ```python
  if web_context:
      prompt += (
          f"{web_context}\n\n"
          f"INSTRUCTION: Real search results above. Synthesize, don't list.\n\n"
      )
  ```
  This sits inside **`_process_message`** (def `:3548`-`:3555`) — explicitly named
  as a dead-inbound method in the header.
- **Its only inbound entrypoint** is `_handle_message` (`:2929`), which is itself
  the outbound-only/dead path: on invocation it logs a WARNING
  ("this surface is outbound-only since 2026-04-20; live inbound is maez_adapter.
  Is this a test or the Surface V2 kill-switch path?", `:2935`-`:2939`).
- **Live inbound routing confirmed elsewhere:** `skills/surface/maez_adapter.py`
  routes inbound through `daemon.inbound_core.run_inbound_turn` (`:45`, `:790`-`:791`,
  gated by `inbound_core_v2_enabled()`); the surface stack's own message handling
  lives in `skills/surface/platform_base.py::_process_message_background`
  (`:1863`) — a DIFFERENT method on a DIFFERENT class.
- **No external caller of `telegram_voice._process_message`:** grep for
  `_process_message` / `_handle_message` across the repo (excluding
  `skills/telegram_voice.py` itself and tests) returns matches only in unrelated
  surfaces (`telegram_public.py`, `platform_base.py`, `telegram_adapter.py`) and
  comments — none reach `telegram_voice._process_message`.

**VERDICT: dead-inbound, out of v0 scope.** The `:3756` insertion CANNOT fire on a
live inbound owner turn. Throat 6 does NOT exist as a live throat; do NOT wire it.
NOT a refutation (it is a confirmed non-throat). ✅

---

## OVERALL VERDICT: GO

All six candidate seams behave exactly as the spec assumes:

| Throat | Seam | Exact line | Verdict |
|---|---|---|---|
| 1 | focused-cognition final render | `focused_cognition.py:865` (var `ordered`) → `:870` → `:913` | post-truncation ✅ |
| 1 v1-repeat | top item rendered twice (v1) | `focused_cognition.py:305-307` (v2 `:289` no-repeat) | confirmed ✅ |
| 5 | photo FRESH WORLD CHECK | `focused_cognition.py:1217`; feeder `maez_daemon.py:6432-6434` | confirmed ✅ |
| 2 | legacy chat prompt | `maez_daemon.py:5817-5819` | confirmed ✅ |
| 3 | voice prompt | `maez_daemon.py:7471-7472` | confirmed ✅ |
| 4 | dispatcher Rail 2 wrap | `provenance_renderer.py:174`; no post-wrap truncation in `provenance_renderer.py`/`merge.py` | **(A)** already safe ✅ |
| 6 | telegram_voice `:3756` | inside dead-inbound `_process_message` (`:3548`) | dead-inbound, out of scope ✅ |

**No refutation.** Throat 4 = (A): the existing Rail 2 wrap is already
truncation-safe (no post-wrap slicing exists), so Task-N for throat 4 is a
confirming/regression test, not a wrap relocation. Throat 6 is a confirmed
non-throat (dead-inbound) and must NOT be wired. Wiring may proceed against these
verified seams.
