# Temporal Recall v1 — Absolute-Date Anchoring (layered, labeled, corrigible) — Design

> 2026-05-30. Third slice of the recall-quality triad (living recall → continuity classifier →
> temporal recall). Closes Blocker-B-temporal. Brain-swap-safe, substrate-side, flag-gated
> (rides `MAEZ_LIVING_RECALL_ENABLED` / focused cognition).

**Goal.** When the owner names an absolute date ("around April 6", "start of April", "2026-04-06",
"last month"), recall the memory from that *date window* over the dated journal tiers — not the
semantically-nearest May journal — and label every match by **how** it was retrieved so the brain
knows "I found this by date" vs "this merely sounds related."

**Design philosophy (Rohit, binding).** Humans do *layered* temporal recall (exact anchors →
landmarks → relative → era → semantic fallback) but are *overconfident*. Maez improves on this:
**layered AND honest** — every temporal match carries its retrieval method + confidence, the guess is
always visible and corrigible. We borrow the layered shape; we reject the false confidence.

## What already exists (verified on `main` — do NOT duplicate)
- `_temporal_telegram_age_window(query)` (`memory/memory_manager.py:670`): **relative conversational**
  phrases ("yesterday", "two days ago", "this morning") → an **age-window in hours** over
  `telegram_exchange` rows. Untouched by this slice.
- `_is_temporal_recall_followup` + `D_TEMPORAL_RECALL` / `TEMPORAL_ANCHORED` dispatcher intent.
- `deep_context_priority` (`core/brain/brain_loop.py:350`): a regex on month-names/dates that already
  swaps recall budget toward context for date-shaped asks — the new path composes with it.

**The gap:** none of the above handles **absolute calendar dates over the dated journal tiers**.
`_temporal_telegram_age_window` returns `None` for "April 6" → no temporal filtering → pure semantic
recall → wrong-month result.

## Metadata reality (verified, read-only)
- `raw_archive` (42,697): `timestamp` ISO string.
- `daily_consolidations` (20): `date` ("YYYY-MM-DD") + `timestamp` ISO.
- `core_memories` (90): `timestamp` ISO; `source` e.g. `nightly_journal`.
- **Gotcha:** a nightly journal *for* April 6 is written ~`2026-04-07T04:00` (next morning). So a date
  window MUST carry a tolerance (≥ +1 day) or "April 6" misses its own journal. Tolerance also makes
  the recall human-shaped ("around April 6").

## Architecture

**1. A typed window contract — the layering seam.**
```
AbsoluteRecallWindow(start_utc: datetime, end_utc: datetime, method: str, confidence: str, label: str)
  method ∈ {"exact_date", "month_window"}        # v1 only
  confidence ∈ {"high", "medium"}
  label = human phrase for the authority tag, e.g. "matched by exact date (2026-04-06)"
```
A resolver `_absolute_date_window(query, now) -> AbsoluteRecallWindow | None`. This type is the seam:
**v2 (event landmarks: "when we fixed honest-empty") and v3 (fuzzy: "a few weeks ago") become
additional producers of `AbsoluteRecallWindow`** later — they don't rewrite recall. Full-NL, if ever, is
one more producer, never the authority.

Do **not** shadow `core.time.temporal_spine.TemporalWindow` (already exists for relative owner-local
anchors). Reuse `core.time.temporal_spine.owner_timezone()` and UTC-canonical timestamp helpers where
possible; v1's absolute-date contract is recall-specific and should be named differently.

**2. v1 producers (deterministic, lightweight — no new dependency):**
- **exact date** → owner-local calendar day, converted to UTC, plus a forward nightly-journal
  tolerance (default +2 days) so an April-6 journal written on April 7 is in-window. If the query says
  "around April 6", use a symmetric ±2-day window. Plain "April 6" should not silently widen backward
  unless needed by a named tolerance rule.
  Forms: `April 6`, `Apr 6`, `April 6 2026`, `2026-04-06`, `6 April`. Year defaults to the most
  recent past occurrence if omitted. `method="exact_date"`, confidence high.
- **month window** → that month's [first, last] day (+ tolerance into the next month's first nightly
  journal). Forms: `April`, `in March`, `start of April` (first third), `end of April` (last third),
  `last month`, `this month`. `method="month_window"`, confidence medium.
- **May ambiguity guard:** bare `may` is not a month cue. Parse May only with an explicit date/year or
  preposition (`May 6`, `May 2026`, `in May`). This mirrors the existing `deep_context_priority`
  caution and avoids turning ordinary modal text into temporal recall.
- No cue → `None` → today's semantic recall, **unchanged** (no regression). Ambiguous/unparseable →
  `None` (fall through), never a bad guess.

**3. Date-filtered recall over the dated tiers.** When `_absolute_date_window` returns a window, in
`recall_for_telegram_living` recall by date over `daily` (filter by `date`/`timestamp` in window) and
`core` (filter by `timestamp` in window, tolerance for nightly offset); rank in-window candidates by
semantic relevance to the topic words. Raw is OUT of v1 unless a plan proves a cheap, bounded timestamp
filter; the witnessed journal target is core/daily and this slice should not scan 40k+ raw rows.

**4. Preserve the evidence/context invariant.** Date-confirmed old memories are answer-authority
**about the past**, not current-state evidence. Do not globally promote core memories into
`SUBSTRATE_EVIDENCE`; the prior invariant "core -> context" still holds unless a future spec changes
it explicitly. For an old date ask, the correct behavior is: the dated row reaches `[memory context]`
with a temporal-match label, and focused cognition cites it with the caveat. Fresh dated daily/raw rows
may remain evidence only if the existing recency partition already makes them evidence.

**5. Carry the method per row, not by global source_type.** `_AUTHORITY_LABEL` maps `source_type`
(`memory_context`, `memory_evidence`, etc.) and cannot express that one recalled row was date-confirmed
while another was semantic fallback. Temporal method must be stored on the returned row metadata (copy,
do not mutate persisted Chroma metadata), e.g.:
```
metadata["temporal_match_method"] = "exact_date"
metadata["temporal_match_label"] = "matched by exact date (2026-04-06)"
metadata["temporal_window_start_utc"] = "..."
metadata["temporal_window_end_utc"] = "..."
metadata["temporal_confidence"] = "high"
metadata["date_confirmed"] = True
```
Then `format_for_prompt` / `format_living_context` render those as `<RECALLED ...>` attributes or a
short inline prefix. `focused_cognition.py` should not need a global authority-label change for this
slice unless an in-process production-path test proves the label is otherwise invisible.

**6. Empty window -> caveated fallback only when there is topic signal.** If the date window is empty
and the query still has non-date topic words ("infrastructure", "ground-truth"), return a semantic
fallback labeled `semantic match, timing uncertain (not date-confirmed)`. If the query is only a date
("what about January 3?"), return no recall and let the answer say no dated memory was found. Never
retrieve a random top semantic row just to have something to say.

**7. Integration & posture.** New `_absolute_date_window` resolver + a date-filtered branch in
`recall_for_telegram_living`, sibling to the relative-conversational path. Flag-gated; brain-swap-safe;
the dated-tier recall is substrate-side. The retrieval-method label flows through the existing
memory-manager renderers into focused-cognition evidence text.

## Non-goals (named for the layering, explicitly OUT of v1)
- **v2: event-landmark anchors** ("when we fixed honest-empty", "during the living-recall witness") —
  a future `AbsoluteRecallWindow` producer that maps named events → date windows (needs an event index).
- **v3: fuzzy relative** ("a few weeks ago", "earlier this year") — tolerance-window producer.
- **Full-NL date parsing** — only ever as one candidate producer, never the authority.
- No change to `_temporal_telegram_age_window` (relative-conversational) or the dispatcher intent.

## Witness gates (live Telegram, flag-on)
1. "What did we note around April 6 about the infrastructure?" → returns the April-6/7 journal
   (the infra ground-truth), rendered with **matched by exact date** — not a May journal.
2. "What were we working on last month?" → month-window match (April, given today is May 30),
   labeled **matched by month window**.
3. A date with no memory (e.g. "what about January 3?") → **caveated semantic fallback** ("nothing
   dated near January 3"; no random memory if there is no topic; if topic words exist, closest by topic
   is timing-unconfirmed) — never a confident wrong date.
4. No-regression: a non-temporal ask ("what's the infrastructure ground-truth you noted earlier?")
   still routes as content recall (the prior slice), unaffected.

## Files (anticipated)
- `memory/memory_manager.py` — new `_absolute_date_window`, date-filtered branch in
  `recall_for_telegram_living`, method label on recalled rows.
- `core/time/temporal_spine.py` — reference/reuse owner-local timezone and UTC canonicalization helpers;
  do not modify or redefine its existing `TemporalWindow` unless implementation proves a helper belongs
  there.
- `core/routing/focused_cognition.py` — only touched if tests prove the memory-manager-rendered temporal
  label is not visible to the brain; default expectation is no focused-cognition change.
- Tests: `tests/test_memory_manager.py` (resolver + date-filtered recall, seeded temp Chroma) and/or
  `tests/test_living_recall.py` (in-process production-path repro: date query surfaces the dated row,
  label survives brain_loop adapter + merge + `assemble_working_set`).

## Self-review
- **Placeholders:** none — producers, tolerance, label strings, and gates are concrete.
- **Consistency:** `AbsoluteRecallWindow.method` values match the rendered temporal labels and the witness gates.
  Caveated-fallback (confirmed) and label-folding (confirmed) are reflected throughout.
- **Scope:** single recall-quality slice; v2/v3/full-NL explicitly deferred with the contract built to
  receive them. The nightly-journal +1day offset is handled by tolerance (named, not hand-waved).
- **Ambiguity:** "start/end of month" defined (first/last third); year-omitted → most recent past
  occurrence in owner-local time; bare `may` guarded; unparseable → `None` (fall through, no bad guess).
