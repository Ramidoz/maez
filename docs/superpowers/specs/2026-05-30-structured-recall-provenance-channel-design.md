# Structured Recall Provenance Channel — Design

> 2026-05-30. Fixes the live-witnessed provenance-survival bug: the char-budget truncates the rendered
> `[memory context]` block mid-`<RECALLED>` envelope, dropping the closing tag, so `assemble_working_set`'s
> regex parses no provenance → `date_confirmed` lost → spurious `temporal_recall_status` → over-cautious
> dated recall. Root cause: provenance (and content) ride on the rendered prompt string, which truncates.
> Fix (Rohit's choice, Approach A): carry recall items as **structured data** from recall → assemble, so
> the working set is built from data, never re-parsed from the rendered text.

**Goal.** `assemble_working_set` builds substrate `EvidenceItem`s from a **structured recall-items
channel** (each carrying full text + temporal provenance), not by regex-parsing the rendered transcript.
This restores `date_confirmed` end-to-end AND delivers complete memory content to focused cognition
(no more "...under a d"). The rendered transcript remains, unchanged, for the brain prompt and the legacy
path; it is no longer the source of the working set's substrate items.

**Why structured, not robust-regex.** Patching the regex to tolerate truncated closing tags (Approach B)
restores provenance but still feeds focused cognition truncated *content*. Provenance and content both
belong as data; the rendered string is for the brain, not for reconstructing the working set. This kills
the whole "render-truncation breaks the working set" class.

## Current data flow (verified)
`recall_for_telegram_living` → rows with metadata (`temporal_match_method`, `date_confirmed`) → the living
adapter renders them to `RecallBlock.text` (string) via `format_living_context`/`format_for_prompt` →
`merge_fanout_results` joins `block.text` → `prompt_block` (string) → daemon `transcript = prompt_block`
→ `assemble_working_set(transcript=…)` regex-parses `<RECALLED date_match=…>` from the string. The budget
truncation (in the adapter's `_bounded_text`/`format_living_context max_chars`) cuts the last envelope,
dropping `</RECALLED>`, so `_RECALLED_RE` (needs the closing tag) matches nothing → provenance lost.

## Architecture (Approach A)

**1. `RecallItem` — the structured unit.** A new frozen dataclass (in `core/dispatcher/layer1.py`
beside `RecallBlock`):
```python
@dataclass(frozen=True)
class RecallItem:
    text: str                          # FULL memory content (untruncated)
    source_type: str                   # "memory_evidence" | "memory_context"
    durable_id: str | None = None
    temporal_provenance: dict | None = None   # {method, confirmed} or None
```
(Shaped so trust-tier authority can ride later as another field; this slice populates only
`temporal_provenance`.)

**2. `RecallBlock` gains `items: tuple[RecallItem, ...] = ()`.** The living adapter
(`core/brain/brain_loop.py::_living_memory_manager_adapter`) populates `items` from the recalled rows it
already has — full `content`, `source_type` from the evidence/context partition, `temporal_provenance`
from the row metadata (`temporal_match_method` → `{method, confirmed: method in (exact_date,month_window)}`).
The adapter still renders `text` for the prompt as today; `items` is the parallel structured channel. The
`prompt_cost`/budget logic continues to bound `text` only — **`items` are never truncated**.

**3. `merge_fanout_results` carries the items.** The merge result (the `RenderedTurn`/merge dataclass)
gains `recall_items: tuple[RecallItem, ...]` — the concatenation of every substrate `RecallBlock.items`
in render order. (Fresh-evidence/web blocks carry no `items`; they remain transcript-only.) `prompt_block`
is unchanged.

**4. Daemon passes the structured channel to assemble.** `assemble_working_set` gains a
`recall_items: list[RecallItem] | None = None` parameter; the daemon passes the merge result's
`recall_items`. (Default `None` preserves every existing caller/test that passes only `transcript`.)

Concretely, this also means `_DispatcherPathResult` and `MaezDaemon.handle_message(...)` need the same
field. The current runtime boundary is `_run_dispatcher_pipeline(...) -> _DispatcherPathResult(transcript)`
and then the surface calls `handle_message(..., transcript=result.transcript)`. A merge-only
`RenderedTurn.recall_items` field is insufficient unless `_DispatcherPathResult.recall_items` carries it
across that boundary and `handle_message(..., recall_items=...)` hands it to `assemble_working_set`.

**5. `assemble_working_set` builds substrate items from `recall_items`.** When `recall_items` is provided:
- Build substrate `EvidenceItem`s from `recall_items` (text = full content, `temporal_provenance` carried
  directly, source_type from the item). **No regex on the transcript for substrate.**
- Parse the transcript ONLY for non-substrate sources (`[fresh evidence]`, web) and take the dialogue
  anchor from `chat_history` as today.
- The Slice-2 date-cue precedence + the `date_confirmed`/status logic now key on
  `item.temporal_provenance["confirmed"]` from the **structured** items — so the truncation can't lose it.
- When `recall_items is None` (legacy callers / non-dispatcher paths), fall back to today's transcript
  parsing (`_memory_items_with_provenance`) so nothing else breaks.

**6. Remove the substrate regex dependency on the live path.** `_RECALLED_RE` / `_DATE_MATCH_ATTR` /
`_memory_items_with_provenance` remain only as the `recall_items is None` fallback; the live focused path
no longer depends on them. (Do not delete them this slice — they guard the fallback + legacy callers.)

## Load-bearing invariants

1. **Rendered/legal role wins over original partition.** `RecallItem.source_type` must match the role that
   is actually allowed/rendered for its block, not blindly the pre-merge evidence/context partition. Today
   `_living_memory_manager_adapter` can coerce both partitions into one `SUBSTRATE_CONTEXT` block under
   hybrid/context-only framings, or emit evidence-only under `SUBSTRATE_EVIDENCE_FRESH_CONTEXT`. The
   structured channel must not leak `memory_evidence` items through a block that the framing rendered as
   context. Rule: when a block is context-only, all its items are `memory_context`; when evidence-only,
   only evidence-eligible items are carried; when both roles are legal, items follow their separate
   evidence/context blocks.

2. **Budget no longer controls provenance, but prompt size is still bounded.** `items` may carry full row
   text through recall/merge so provenance is not destroyed by prompt rendering, but focused cognition
   must still enforce its own bounded working-set budget before sending `ordered_evidence_text` to the
   brain. Any working-set truncation must be item-aware (truncate the item text after selection, preserve
   `durable_id` and `temporal_provenance`) and must never create or remove `date_confirmed`. The bug is
   "render-truncation erased provenance," not "focused cognition may send unlimited memory text."

3. **No new raw-text telemetry by accident.** `RecallBlock.to_dict()` / observation envelopes should not
   start serializing full `RecallItem.text` unless the text is already intentionally rendered somewhere.
   If tests need structured visibility, expose IDs/source_type/temporal_provenance or keep it in process.
   This preserves the existing telemetry discipline: no raw memory text beyond what already reaches the
   prompt/focused call.

## Coexistence / non-goals
- **The rendered transcript is unchanged** and still feeds the brain (legacy megaprompt + the focused
  system block's `ordered_evidence_text` is rebuilt from the structured EvidenceItems — full content).
  The legacy megaprompt's own truncation is out of scope (separate concern, not the focused/working-set
  path).
- **Trust-tier authority labels** keep riding the rendered text for now; shape `RecallItem` to carry them
  later, but do NOT migrate them this slice (YAGNI).
- No flag change; no change to recall ranking/recency, to the resolver precedence (Slice 2 stays), or to
  `_temporal_telegram_age_window`.

## Testing
- **Structured carry end-to-end:** a recall with a long (budget-overflowing) `date_confirmed` memory →
  `RecallBlock.items` carries it with `temporal_provenance.confirmed=True` and **full** text; merge's
  `recall_items` carries it; `assemble_working_set(recall_items=…)` yields a substrate `EvidenceItem` with
  `temporal_provenance.confirmed=True` and full content — **no `temporal_recall_status`**. (This is the
  exact live-witness failure, now a deterministic test.)
- **Boundary carry:** `_run_dispatcher_pipeline` returns both `prompt_block` and `recall_items`; the daemon
  receives both and passes the structured channel into `assemble_working_set`. A test should fail if
  `RenderedTurn.recall_items` exists but is dropped at `_DispatcherPathResult` or `handle_message`.
- **Role-coercion guard:** under a context-only framing, evidence-partition rows carried structurally are
  exposed to focused cognition as `memory_context`, not `memory_evidence`.
- **Focused budget guard:** a huge structured memory item cannot make `working_set_chars` unbounded; if it
  is shortened for the focused prompt, `temporal_provenance.confirmed` and `durable_id` survive.
- **Truncation no longer loses provenance/content:** even when `prompt_block`'s rendered `[memory context]`
  is truncated mid-envelope, the working set is correct (built from `recall_items`).
- **Fallback path:** `assemble_working_set(transcript=…, recall_items=None)` behaves as today (regex
  parse) — existing focused-cognition tests stay green.
- **No regression:** fresh/web/dialogue-anchor items still come from transcript/chat_history; non-dated
  continuity/recency unchanged; Slice-2 precedence tests unchanged.
- Integration: the full `dispatcher → merge → daemon → assemble` path for "around April 27" yields a
  `date_confirmed` working-set item with the full INFRASTRUCTURE GROUND-TRUTH content.

## Witness
Re-run the dated triad probes (flag-on). Expected after the fix: "around April 27" recalls the full
April-27 incident as `date_confirmed` context with **no** spurious "no dated memory" status; "remind me
what we were doing around April 27" recaps it (dated primary); incidental/continuity unchanged. Green →
the triad graduates (dated recall honest AND complete) → eligible for the explicit default-on decision.

## Files
- `core/dispatcher/layer1.py` — `RecallItem`; `RecallBlock.items`.
- `core/brain/brain_loop.py` — adapter populates `items` from recalled rows.
- `core/dispatcher/merge.py` — merge result carries `recall_items`.
- `core/brain/brain_loop.py` — `_DispatcherPathResult` carries `recall_items` alongside `transcript`.
- `daemon/maez_daemon.py` — `handle_message(..., recall_items=...)` passes them to `assemble_working_set`.
- `core/routing/focused_cognition.py` — `assemble_working_set` builds substrate from `recall_items`;
  regex path becomes the `None` fallback.
- Tests: `tests/test_focused_cognition.py`, `tests/test_living_recall.py`, dispatcher/merge tests.

## Self-review
- **Placeholders:** none — `RecallItem` fields, the `items`/`recall_items` carries, the assemble dual-mode
  (structured-or-transcript), and the test contracts are concrete.
- **Consistency:** `temporal_provenance={method,confirmed}` matches the v2 EvidenceItem field + the Slice-2
  daemon `_had_confirmed` read (which now reads structured-sourced items); `source_type` values
  `memory_evidence`/`memory_context` match `_SOURCE_TYPE`.
- **Scope:** structured channel for substrate temporal provenance + content only; legacy/megaprompt
  truncation, trust-tier migration, and ranking all explicitly out. `recall_items=None` fallback keeps
  every existing caller working.
- **Ambiguity:** "substrate" = memory_evidence/memory_context (from recall); fresh/web/anchor stay their
  current sources; "full content" = the untruncated row `content`, never budget-bounded in `items`.
