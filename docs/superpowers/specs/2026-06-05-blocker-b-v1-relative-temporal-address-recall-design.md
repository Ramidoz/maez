# Blocker-B v1: Relative Temporal Address Recall — Design

**Date:** 2026-06-05
**Status:** DRAFT for owner review → Codex implements / Claude reviews; owner runs the live witness.
**Builds on:** the TRF temporal spine (`core/time/temporal_spine.py` `temporal_window`, `core/memory/temporal_anchor_recall.py` `detect_temporal_anchor` — both pure resolvers); the memory-manager date machinery (`_row_in_window`, `_date_string_bounds_utc`, `_absolute_date_recall`'s label pattern, `fallback_label`); the focused path's `temporal_recall_status` typed-status pattern; the origin-trust tiers (`6cd3478` — covenant-tier = timeless self). The "Blocker-B" recall-ranking root-cause diagnostic (2026-05-29) + the read-only current-memory reproduction (2026-06-05).

## 0. Why

The live legacy recall path (`memory_manager.recall_for_telegram`) is **temporal-blind**: it does `get_all_core()` (≈100 core, query-independent) + semantic daily/raw + `_topic_rerank()`. "yesterday/last week/recently" are just tokens in the embedding — there is **no date parse, no window filter, no recency awareness** on the primary search. Read-only reproduction (2026-06-05) confirms the bite: *"what were we working on last week?"* surfaces 53/58/41-day system-state memories rendered as if they answer the question.

This is a **honesty** bug as much as an accuracy one: the system implies "this is from last week" when it isn't. **Blocker-B v1 makes temporal-address recall honest: when the owner gives Maez a relative temporal *address*, main recall searches that window first, and an out-of-window match never wears in-window clothing.** Not "smarter recall" — *bounded-address honesty.*

**Reuse-check correction (load-bearing):** living recall (`recall_for_telegram_living`) already has window/partition/label machinery, but it is **flag-off for LATENCY, not for render/synthesis bugs** — its base latency (~4.7–8.4s) sits above the 4328ms recall-flip ceiling (`project_recall_flip_outcome`). So **v1 must NOT turn living recall on wholesale** (it would inherit the latency No-Go). v1 reuses the *machinery* cheaply on the legacy path, fired only for relative-address queries.

## 1. The covenant law (the slice's spine — owner's words, verbatim)

> **For a temporal-address query, legacy semantic recall is NOT an eligible fallback evidence source. Every row reaching the brain is one of: window-confirmed · timeless context (core) · explicitly not-from-window context · or absent-with-an-honest-status. There is no disguised fifth category.**

## 2. Scope

**In:** the four TRF relative *addresses* — `yesterday`, `last_week`, `this_morning`, `earlier_today` — on the **legacy `recall_for_telegram` path** (the live default; `mode=legacy`).

**Out:** recency/continuity asks (`recently`, `earlier`, "what were we talking about" — the continuity classifier's lane); recency **weighting** (the "newer = truer" danger — its own later slice); turning living recall on wholesale (latency No-Go, separate decision); the focused/living path; absolute dates (already handled); deletion; any recent-bias.

## 3. The mechanism

**Trigger — key off `detect_temporal_anchor`'s FULL result**, not just "anchor string present" (the detector already runs the intent gate + negative/self-memory guards + window resolution). Three outcomes:
1. `anchor_detected = False` → **legacy path runs untouched** (non-temporal queries pay nothing, identical output).
2. `anchor_detected = True` but window unresolved / `helper_unavailable` → **typed helper-unavailable status; NO semantic fallback** (§4 case 3).
3. `anchor_detected = True` with a resolved window → **window-first branch** `_relative_temporal_address_recall(query, window)`.

**Window-first retrieval (NOT semantic-then-filter), per tier:**
- **daily** (dated, consolidated, few rows): `_row_in_window` filter — cheap, exact.
- **raw** (large): new helper `_raw_rows_in_window(window)` — **window-first**, then optionally semantic-rank *within* the bounded set. This is the **must-prove** piece (§5).
- **core**: `get_all_core()` stays available, but for an address query it is **timeless self-context, not window-evidence** (origin-trust covenant-tier = "who Maez is," never "what happened last week").

**Coexistence with TRF:** TRF supplements the daemon chat path over the **lived-episode** store; Blocker-B bounds the **main** store (core/daily/raw). They compose; B's statuses are **main-store-scoped** ("no date-confirmed *dated/consolidated main-store* memories for last week") so they never read as a global "found nothing" when TRF found a lived episode.

## 4. The honest-empty status + authority contract

**Three temporal-status cases — all RENDERED, never silent:**
1. **Window has date-confirmed matches** → render as past-context with temporal labels (reuse `_absolute_date_recall`: `method/label/confirmed/window` on metadata *copies*; Chroma source unaltered; "date-confirmed, past context, never current-state evidence").
2. **Window resolved but empty** → an explicit status: `No date-confirmed dated/consolidated main-store memories found for <window label>` (e.g. *last week*). **Definition of empty: no date-confirmed `daily` or `raw` (event) in-window rows.** In v1 Variant B, raw cannot be timestamp-range searched without a numeric index, so the rendered status names the dated/consolidated record that was actually checked rather than claiming a confirmed-empty raw firehose. Core is timeless self-context by contract and **never counts toward filling the temporal address or toward the empty determination** — a core row whose timestamp happens to fall in the window is still self-context, *not* event evidence; it may sit beside the answer, never as the answer, and never suppresses the empty status.
3. **Helper unavailable** (anchor detected, window unresolved) → `Temporal reference recognized but could not be resolved to a window` — explicitly not a semantic answer.

**The fallback — the single permitted door for outside-window content (precise):**
- Date-confirmed in-window rows → allowed as temporal context.
- Outside-window semantic rows → **optional, and only if visibly labeled** `semantic match, timing uncertain (not date-confirmed)` (the existing `fallback_label`).
- **The empty status (case 2) is ALWAYS rendered when no date-confirmed main-store rows exist — EVEN IF optional fallback context is shown.** Fallback context **never replaces** the empty status; it sits *below* it as "related, but not from the address." (This is the rule that stops fallback from quietly becoming the answer.)

**Core** renders as timeless self-context (covenant-tier), never as window-evidence.

## 5. The render — typed status, NOT a faux memory

The status renders as a **first-class, typed recall-system element** — its own tag, distinct from a `<RECALLED>` memory row — carried from the `recall_for_telegram` branch into `format_for_prompt`'s `PAST OBSERVATIONS` block:

```
<TEMPORAL_RECALL_STATUS label="last week" status="no_date_confirmed_event_memories">
No date-confirmed dated/consolidated main-store memories found for last week.
</TEMPORAL_RECALL_STATUS>
```

(House-style equivalent acceptable; the tag/typing is the requirement.) The brain reads it, but it is **a status, not a remembered event**: not a member of `{core, daily, raw}`, not stored, not cited as lived `[E#]` evidence, not confused with `raw`. *The empty window is itself a rendered fact — there is no silence for the brain to fill with vibes.*

## 6. The must-prove: the `_raw_rows_in_window` helper has TWO obligations

The target is Chroma `query(..., where=<ISO-8601 timestamp range>)` — "filter to window, then vector-rank within window" (ISO-8601 sorts lexicographically, so a `$gte/$lte` string range *may* work). It must satisfy **both**, proven before relied on:
1. **Correctness** — returns *only* in-window rows (no outside-window leakage).
2. **Cost** — stays within a small latency budget so total recall stays on the legacy fast path (a correct-but-slow scan that takes seconds recreates the living-recall latency No-Go under a temporal name). **A timing guard wraps the helper: if raw window retrieval exceeds budget, DEGRADE HONESTLY (dated-daily/core + the empty/helper status) — never block the chat path.** Budget number is tunable in the plan; the *degrade-don't-block guard* is the covenant requirement.

If Chroma cannot satisfy correctness **and** cost, v1 degrades to **dated-daily + core + honest status** — and **never** the semantic-then-filter path that pulls outside-window rows as answers.

## 7. Tests (RED-first, deterministic/hermetic)

**Routing (3 outcomes):** non-temporal → no branch, `recall_for_telegram` output byte-identical to today (regression); anchor+window → window-first; anchor+helper-unavailable → typed helper-unavailable status, no semantic fallback.

**Window-first honesty:** an in-window row surfaces; a 53-day row does **NOT** surface as an answer for "last week" (only ever as the labeled timing-uncertain fallback).

**The must-prove (both obligations):** `_raw_rows_in_window(window)` returns exactly the in-window rows (correctness); a timing-guard test proves over-budget retrieval **degrades** to dated-daily/core + status rather than blocking, and the degraded path returns **no** outside-window semantic rows as answers (cost + honest degradation).

**Typed status (not faux memory):** empty window → `<TEMPORAL_RECALL_STATUS status="no_date_confirmed_event_memories">` renders **and** is asserted not in `{core,daily,raw}`, not stored, not cited as lived `[E#]` evidence; helper-unavailable → its own typed status.

**Always-render-empty + core-doesn't-count:** a window with no in-window `daily`/`raw` rows **but** with optional fallback context → the empty status **still renders above** the fallback (fallback never replaces it). And a window where a **core** row's timestamp falls inside it but no `daily`/`raw` rows do → still **empty** (the core in-window row neither suppresses the empty status nor renders as the address answer; it may appear only as timeless self-context).

**Authority + coexistence:** date-confirmed matches render past-context-not-current-state; core renders timeless self-context, not window-evidence; B's empty status is main-store-scoped (no global "found nothing" when TRF found a lived episode).

**Live witness (owner-run, after merge + restart):** "what were we working on last week?" → window-bounded main recall + typed status; a relative query with a genuinely empty window → the rendered empty status, not stale backfill. Full `discover` before done; cross-lane apples-to-apples in the asset-rich checkout.

## 8. Acceptance rules

1. Branch keys off `detect_temporal_anchor`'s full result; non-temporal queries leave `recall_for_telegram` byte-identical.
2. Helper-unavailable → typed honest status, never semantic fallback.
3. Window-first retrieval; an out-of-window row never reaches the brain as an answer (only as labeled not-from-window context).
4. `_raw_rows_in_window` proven for **correctness AND cost**; a timing guard degrades honestly (never blocks) when over budget; degradation never returns outside-window semantic rows as answers.
5. Three typed status cases render in the block; the status is not a memory row (not in `{core,daily,raw}`, not stored, not cited as lived evidence).
6. **Empty is defined over event memories only: the empty status always renders when no date-confirmed `daily`/`raw` in-window rows exist** — even if core self-context or fallback context is shown. In Variant B, the human-facing text says "dated/consolidated main-store memories" so the brain does not read raw-firehose degradation as a confirmed-empty week. A core row whose timestamp falls in the window does **not** count toward the empty determination and does **not** fill the address.
7. Outside-window semantic content appears only if visibly labeled "timing uncertain / not date-confirmed."
8. Core renders as timeless self-context, never as temporal-address (window) evidence.
9. B's statuses are main-store-scoped (coexist with TRF, no global "found nothing").
10. Full suite green (zero new failures, apples-to-apples); no living-recall-wholesale; no recency weighting; no recent-bias.

## 9. File structure

**Modify:** `memory/memory_manager.py` — the `recall_for_telegram` branch (detect → window-first), the new `_raw_rows_in_window` helper (+ timing guard + honest degradation), the typed status carried into `format_for_prompt`. Reuse `_row_in_window`, `_absolute_date_recall`'s label pattern, `fallback_label`.
**Reuse (read-only):** `core/memory/temporal_anchor_recall.detect_temporal_anchor`, `core/time/temporal_spine.temporal_window`, the focused path's `temporal_recall_status` shape.
**Untouched:** living recall (`recall_for_telegram_living`), the focused/daemon TRF path, the lived-episode store, absolute-date handling.

## 10. Lane

Codex implements / Claude reviews (touches the core recall path — multi-piece, delicate; not inline). Cross-lane verification mandatory; the legacy-path-byte-identical regression + the honest-empty/typed-status invariants are the primary review anchors. Owner runs the live witness.
