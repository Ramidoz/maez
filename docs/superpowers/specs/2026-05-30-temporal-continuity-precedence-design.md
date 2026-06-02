# Temporal–Continuity Precedence (B-lite) — Design

> 2026-05-30. Repairs the composed-organ contract surfaced RED by the triad witness
> (`docs/slices/recall-axis-dispatcher/witness/triad-default-on-witness-2026-05-30.md`): a query that
> is BOTH continuity-shaped and date-shaped fetched the dated memory then discarded it via the
> continuity-anchor override, cascading the prior turn's non-answer. Makes the recall triad eligible
> for default-on again. Brain-swap-safe, substrate-side, flag-gated.

**Goal.** When a question carries an **explicit temporal address** ("around April 27", "last month",
"2026-04-06"), temporal recall is the **primary** frame; the dialogue anchor may appear only as
**secondary** context and can never replace, outrank, or answer for the dated frame.

**Binding v1 rule (Rohit, verbatim):** *"Explicit temporal address creates the primary recall frame.
Dialogue anchor may be included only as secondary context and must never replace, outrank, or answer
for the dated frame. If no dated match exists, do not fall back to dialogue as the answer."*

**Design principle.** *Explicit address beats vague address.* The triad bug was Maez mistaking the
conversational **wrapper** ("remind me / what were we") for the **address**; the real address was
"April 27". This is the SOTA pattern (temporal-semantic decomposition with the temporal part primary;
intent made explicit, not guessed) — B-lite is its deterministic on-ramp, not full decomposition/fusion.

## Architecture

**1. Shared explicit-date-address predicate (single source of truth).** Extract `AbsoluteRecallWindow`
+ `_absolute_date_window` + its pure helpers (`_exact_window`, `_month_window`,
`_most_recent_year_for`, `_day_bounds_local`, `_owner_local_to_utc`, `_NIGHTLY_FWD_TOL_DAYS`,
`_MONTH_NAMES`) from `memory/memory_manager.py` into a new lightweight module
**`core/routing/temporal_cue.py`** (only dependency: `core.time.temporal_spine`). Add:
```python
def has_absolute_recall_cue(question: str, now_local: datetime | None = None) -> bool:
    return _absolute_date_window(question, now_local) is not None
```
`memory/memory_manager.py` re-imports the window + helpers from `temporal_cue` (the recall logic
`_absolute_date_recall` / `_row_in_window` / `_temporal_topic_signal` / `_all_daily_rows` /
`_tag_temporal_rows` STAYS in memory_manager — it needs the collections). `brain_loop` and
`focused_cognition` import `has_absolute_recall_cue` from `temporal_cue`. No heavy/circular import
(verified: focused_cognition has no module-level memory_manager dep; memory_manager imports
focused_cognition only lazily). **Mechanical move, no logic change.** The predicate also accepts the
same optional `now_local` test seam as `_absolute_date_window` so parity tests are deterministic.

**2. Boundary 1 — adapter (`core/brain/brain_loop.py::_living_memory_manager_adapter`).** Today, on a
DIRECT/ANAPHORIC continuity question, the adapter REPLACES the evidence block with the dialogue anchor
(`ev_text = "Recent dialogue anchor: …"`). New rule: **if `has_absolute_recall_cue(user_text)` is
True, the anchor-as-evidence override does NOT fire.** The temporal recall returned by
`recall_for_telegram_living` (date-confirmed rows in the context partition) stays primary.
**Do not inject the dialogue anchor in the adapter for date-cued turns.** The secondary anchor belongs
to `assemble_working_set`, which already receives `chat_history`; duplicating it in the adapter would
make the prompt/telemetry look like memory supplied the anchor. **If the temporal recall has no
date-confirmed rows, the adapter still must not inject the anchor** — the turn is empty or caveated for
the date, per the binding rule.

**3. Boundary 2 — `core/routing/focused_cognition.py::assemble_working_set`.** Today a
DIRECT/ANAPHORIC question is *dialogue-authoritative*: it skips transcript parsing and keeps only the
newest dialogue anchor as the sole `[E1]`. New rule: **if `has_absolute_recall_cue(owner_question)` is
True, do NOT go dialogue-authoritative.** Parse the transcript blocks (the temporal `memory_context`)
as the **primary** items, and include the dialogue anchor (if present) only as a **secondary** item
ranked strictly **below** the temporal items (never `[E1]`, never outranking). `_ranked_items_for_state`
gains a date-present mode that demotes `dialogue_anchor` below `memory_context`/`memory_evidence`.
**If there are no date-confirmed temporal items, the anchor does not become the answer.** If caveated
`semantic_fallback` rows exist, they may remain as timing-uncertain context. If no temporal/fallback
rows exist at all, assemble a tiny retrieval-status working-set item (e.g. `temporal_recall_status`:
"no dated memory matched the explicit date cue") so focused cognition can answer honestly instead of
returning `None` and letting the daemon fall through to legacy chat-history synthesis.

**4. Honesty / corrigibility (unchanged guarantees, now enforced at the seam).** Temporal-match labels
(`date_match="exact_date"`, etc.) and the "no dated record" empty behavior from the temporal slice are
preserved. A date question with no in-window memory yields the honest "no dated record" reply — never a
dialogue-anchor stand-in. `semantic_fallback` is allowed only as labeled, timing-uncertain context; it
does not count as a dated match and does not permit dialogue-anchor substitution.

## Non-goals
- **No full decomposition/fusion** (multi-retriever fan-out + scored fusion) — that's a future slice
  if B-lite proves insufficient. B-lite is precedence only.
- **No memory-ranker / recency-salience changes**, **no renderer changes**, **no memory-write changes**,
  **no new flag** (rides the existing recall/focused flags). Prompt prose is not the fix.
- No change to relative-conversational temporal (`_temporal_telegram_age_window`).

## RED tests
- **Both-shaped + dated memory:** "remind me what we were doing around April 27" with chat history →
  the first/primary working-set item is `memory_context`, NOT `dialogue_anchor`; the dated row is
  present; if the anchor appears at all it is a non-`[E1]` secondary item.
- **Both-shaped + NO dated memory:** an explicit date with no in-window memory → does NOT answer from
  the dialogue anchor (no anchor-only working set; focused working set contains either caveated
  `semantic_fallback` context or a retrieval-status "no dated memory matched" item; no legacy fallback).
- **Plain continuity (no date):** "what were we just talking about?" → still `dialogue_anchor`
  authoritative (no regression).
- **Plain date / content recall:** "what did we note around April 27?" → temporal as before; a
  non-temporal content ask → unchanged.
- **Predicate parity:** `has_absolute_recall_cue(q) == (_absolute_date_window(q) is not None)` for a
  battery of dated and non-dated queries (single-source-of-truth guard).

## Files
- Create: `core/routing/temporal_cue.py` (moved window/predicate).
- Modify: `memory/memory_manager.py` (re-import the moved symbols), `core/brain/brain_loop.py`
  (`_living_memory_manager_adapter` precedence), `core/routing/focused_cognition.py`
  (`assemble_working_set` + `_ranked_items_for_state` date-present mode).
- Tests: `tests/test_focused_cognition.py` (assemble precedence + predicate parity),
  `tests/test_living_recall.py` (in-process both-shaped query → temporal primary, survives to
  `assemble_working_set`), `tests/test_memory_manager.py` (import-move smoke: resolver still works).

## Witness (after in-process green)
Re-run the **triad witness** (flag-on), focused on the interaction:
1. "remind me what we were doing around April 27" → recaps the **April-27** record (date primary),
   not the prior turn's "January 3 / no record"; recent thread may appear as a labeled side-note.
2. An explicit date with no memory → honest "no dated record", not a dialogue stand-in.
3. Plain "what were we just talking about?" → still recaps the recent thread (no regression).
4. Plain temporal ("around April 27") + plain recency/continuity probes → all still green.
Green → the triad graduates (eligible for an explicit default-on decision, separate step). Red → split.

## Self-review
- **Placeholders:** none — predicate, both boundary rules, the no-dated→no-anchor rule, and RED tests
  are concrete. **Consistency:** the binding rule is enforced identically at both boundaries via the
  one predicate; "secondary, never `[E1]`, never the answer when empty" is stated at adapter and
  assemble. **Scope:** precedence-only; ranker/renderer/memory-write/flag all explicitly out; the
  predicate move is mechanical. **Ambiguity:** "secondary" defined as ranked strictly below temporal
  items and never authoritative; "no dated match" defined as no `date_confirmed` temporal rows, with
  `semantic_fallback` explicitly not counting as a dated match.

---

## POST-VETO REVISION (2026-05-30) — verdict-propagation re-architecture

The first implementation (branch `temporal-continuity-precedence`) was faithful to the spec above but
the Claude 6-role switchboard's **Logical voice issued a VETO with three blockers, all verified by
Claude against the live code**. The slice's *shape* is right; it did not enforce its own binding rule
end-to-end. This revision supersedes the "re-derived boolean at two boundaries" mechanism.

### Verified blockers
- **B1 — cue over-triggers.** `has_absolute_recall_cue` returns `True` on incidental month/number
  mentions: `"I will be 30 in may"`, `"remind me to march 3 miles"`, `"in March we should ship"`,
  `"pick 2 may options"`, and — the harm — `"what were we just talking about, the 3 may bugs?"`
  (continuity + incidental date → the cue suppresses the dialogue anchor and **discards the correct
  continuity answer**). The `\d{1,2}\s+<month>`, `<month>\s+\d{1,2}`, and bare `in <month>` patterns
  fire on non-address uses.
- **B2 — binding rule NOT enforced on the live path.** Daemon gate `maez_daemon.py:3848`:
  `_focused_candidate = enabled AND source!=voice AND not echo AND (evidence_present OR
  _dialogue_needs_or_uncertain)`. A pure no-match dated query (no recall hit, no continuity, no topic)
  has `evidence_present=False` and `_dialogue_needs_or_uncertain=False` → `_focused_candidate=False`
  → **`assemble_working_set` is never called → the `temporal_recall_status` item never fires →
  fall-through to the legacy megaprompt.** The triad witness's honest "no record of January 3" was the
  legacy megaprompt answering honestly *by luck*, not the slice's guarantee.
- **B3 — web / semantic_fallback can answer the dated frame.** Under `date_cue`, `web_context` ranks
  `_PRIORITY=2` (above anchor 50 / status 60) and counts as `non_anchor` → untrusted web suppresses the
  status and can be primary; and `semantic_fallback` rows render as plain `memory_context`
  (the caveat lives only in tag text), structurally indistinguishable from a `date_confirmed` match —
  so a semantic guess can become `[E1]` ("most important, repeated") answering the dated question.

### New architecture — propagate the recall verdict; don't re-derive
The recall layer (`memory/memory_manager.py::_absolute_date_recall`) already computes the authoritative
fact — `date_confirmed` rows vs `semantic_fallback` rows vs empty. Make THAT the source of truth:

1. **Per-item temporal provenance is structural, not string-sniffed.** `assemble_working_set` must
   carry each recalled row's temporal verdict onto the `EvidenceItem` as a first-class field (e.g.
   `EvidenceItem.temporal_provenance = {method, confirmed, confidence, window_start, window_end}`).
   V1 may extract that field from the `<RECALLED ... date_match="..." ...>` opening-tag attributes
   because that envelope is Maez's structured recall protocol; it must NOT search arbitrary item text
   for words like `semantic_fallback` or `date_match`. Ranking, answer-eligibility, and the status
   decision key on this parsed/enveloped field — never on a re-derived boolean and never on substring
   matches in the memory body.
2. **Only `date_confirmed` may satisfy the dated-memory frame.** `semantic_fallback` is
   **timing-uncertain context only** — it may appear below a status/confirmed item, but it MUST NOT be
   `[E1]`/"most important, repeated" for a date-cued turn, and its presence does NOT suppress the
   `temporal_recall_status` item when there is no `date_confirmed` row. `web_context` is likewise NOT
   a dated-memory answer in v1: under a date cue it cannot be `[E1]` and cannot suppress the status.
   Future external/tool producers may satisfy a dated frame only if they carry an explicit
   date-confirmed provenance field equivalent to memory's `date_confirmed=True`.
3. **Open the daemon gate for date-addressed turns and close the legacy escape hatch.** Add a concrete
   cue resolver, not another free boolean:
   `absolute_recall_cue(question, now_local=None) -> AbsoluteRecallCue`, where
   `AbsoluteRecallCue` carries `{window, is_address, override_continuity, reason}`. Existing
   `_absolute_date_window` remains the low-level parser; any old `has_absolute_recall_cue` helper is
   parser-parity only and must not drive behavior. `_focused_candidate` gains
   `or absolute_recall_cue(text).is_address` so a no-match dated query reaches
   `assemble_working_set`, the status item fires, and the legacy megaprompt is not the date-cued
   answer. If a date-cued focused path returns `None` or the focused call errors, the daemon must use a
   deterministic dated-recall fallback ("I don't have a dated memory for that resolved window" / "I
   found dated context but couldn't synthesize it safely") rather than falling through to legacy chat
   synthesis. This is a daemon change — the slice is no longer "no daemon touch."
4. **Cue tightening (B1) — address-intent beats continuity; incidental month/number does not.**
   Introduce an address-intent notion (the deterministic seed of the future address-kind resolver):
   a date cue **overrides a present continuity cue only when the query is asking recall/history about
   that date**, not merely containing a month/number. Address-strong examples: ISO date; explicit
   year; `<Month Day>`/`<Day Month>` in a recall/question frame ("what happened May 6", "what were we
   doing April 27"); date prepositions or recall markers ("on/around/about/near/back around/from/for
   <Month Day>", "in April" only when paired with recall/history wording such as "what did we note /
   what happened / what were we working on"). A bare ordinal like "the 27th" is NOT v1 address-strong
   unless paired with a month/year or an existing resolved temporal antecedent (future slice). Incidental
   or future-planning language stays non-address: "I will be 30 in May", "remind me to march 3 miles",
   "in March we should ship", "pick 2 may options", and "what were we just talking about, the 3 may
   bugs?" → continuity/current intent wins. (This is the minimal robust deterministic fix; full
   natural-language date-intent classification stays out of scope.)

### Folded advisories (from the other five roles)
- Name the demotion ranks (`50`/`60`) as constants tied to "strictly after all evidence"; add
  cross-referencing comments at the adapter (provenance half) and assemble (precedence half) so the
  two-site contract isn't silently severed.
- `AbsoluteRecallWindow.confidence` is an intentional, currently-unused growth seam for richer
  address-weighing — comment it so it survives cleanup.
- Witness must record the resolved window bounds beside any "no dated memory matched" status, so a
  future audit can tell genuine-absence from out-of-resolved-year (the `_most_recent_year_for`
  single-year false-negative; multi-year disambiguation is a named future slice).
- This boolean `date_cue` + `and not date_cue` negations are the degenerate case of an address-kind
  resolver (EXPLICIT_DATE / LANDMARK / RECENCY / NONE); leave the room, don't build it now.

### Updated scope / files
- Add: `daemon/maez_daemon.py` (gate opening for date-cued turns).
- `core/routing/focused_cognition.py`: `EvidenceItem` gains `temporal_provenance`; assemble extracts +
  keys on it; web/semantic_fallback answer-eligibility rules; named ranks.
- `core/routing/temporal_cue.py`: `AbsoluteRecallCue` + `absolute_recall_cue(...)`; behavior call
  sites use `is_address` and `override_continuity`, not the raw parser predicate. The low-level
  `_absolute_date_window` remains for window construction and parity tests.
- `memory/memory_manager.py`: ensure the per-row `temporal_match_method` is reliably rendered so
  assemble can read it structurally.

### Updated RED tests (supersede / extend the originals)
- **B1:** the false-positive / true-positive battery — `"what were we just talking about, the 3 may
  bugs?"` stays DIALOGUE-primary (continuity wins; date is incidental); `"I will be 30 in May"`,
  `"remind me to march 3 miles"`, `"in March we should ship"`, and `"pick 2 may options"` do not
  trigger temporal override; while `"what did we note around April 27?"`, `"what were we doing April
  27?"`, `"what happened May 6?"`, and `"remind me what we were doing around April 27"` stay
  temporal-primary.
- **B2:** in-process/daemon-path test — a no-match dated query reaches `assemble_working_set` and yields
  the `temporal_recall_status` item; no legacy fall-through (assert the focused path is taken). Add a
  focused-exception/working-set-None daemon test for date-cued turns: fallback must be deterministic
  dated-recall honesty, not legacy synthesis.
- **B3:** date-cued turn with only `semantic_fallback` rows → fallback is NOT `[E1]` and the status
  fires/ co-renders as timing-uncertain; date-cued turn with `web_context` present → web is NOT `[E1]`
  and does not suppress the status; only a `date_confirmed` row is the dated answer.
- Provenance: `EvidenceItem.temporal_provenance` is populated from the `<RECALLED>` opening-tag
  attributes for confirmed and fallback rows (structured envelope parse, not body substring).

**Witness:** unchanged battery PLUS an explicit no-match-dated probe ("what about January 3?") confirmed
to take the focused path (status item), and a "what were we just talking about, the 3 may bugs?"-style
probe confirmed to stay continuity. Only after this passes does the triad re-witness for graduation.
