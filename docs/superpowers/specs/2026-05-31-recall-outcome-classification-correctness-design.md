# Recall-Outcome Classification Correctness Slice — Design

**Date:** 2026-05-31
**Status:** Design approved (Rohit, 2026-05-31) — revised after pre-code pass surfaced a laundering risk in the first draft. Guarded-(a) "mixed citation → answered_grounded" was REJECTED (co-citation is not proof of support); replaced with a third closed outcome class. Pre-registration. Spec-first.
**Predecessors:** The first live recall-on smoke (No-Go, reverted). The smoke proved recall *works* — but `recall_outcome` **mis-classified honest behavior twice**, making the result look worse than Maez actually behaved. This slice fixes the *scoreboard* so the next gate tells the truth, **classification/telemetry only — no cognition/behavior change, recall stays off.**

---

## 1. Why this exists (two telemetry wounds + one laundering trap avoided)

1. **Both-shaped over-strictness (Fix 2).** The April-27 both-shaped turn logged `answered_ungrounded` though `focused_cognition_runs` said `grounded, unmatched=[]` — it cited real dated memory (E1/E2/E4) **plus** one `dialogue_anchor` (E7), and the strict `cites_confirmed_memory_context` (every cited label must be confirmed `memory_context`) flipped it to ungrounded.
2. **Missed absence vocabulary (Fix 3).** The Jan-3 honest decline ("I don't have **any records**…") logged `answered_ungrounded`; the matcher misses "any record" / "have no record" / curly apostrophes.

**The laundering trap we are NOT walking into:** the first draft "fixed" Fix 2 by relaxing the *classification* — co-cited memory + dialogue → `answered_grounded`. That is dishonest: **co-citation is not proof of support.** A reply can cite one real memory as garnish and answer mostly from dialogue/self-echo; labels prove citation *shape*, not semantic *support*. Stamping that `answered_grounded` is flattery — the same producer-causality failure as libel, just in the generous direction ([[producer_causality_no_caller_score_laundering]]). The honest scoreboard *surfaces* the ambiguity it cannot resolve from labels; it does not resolve it generously ([[honest_ingestion_immune_system]]).

## 2. Goal & non-goals

**Goal:** an honest three-state classification of recall-relevant *answered* turns, so the next gate reads grounded / mixed / ungrounded as distinct truths — without claiming more than the labels prove.

**Non-goals (explicit):**
- **NO cognition/behavior change.** Classification logic only; synthesis/model untouched.
- **NOT the continuity fix (Fix 1)**, and **NOT the behavior-side mixed→grounded fix** (steering both-shaped dated answers to cite dated-memory-only) — both belong to a separate **behavior** slice. Telemetry can only *describe* labels; it can never manufacture proof.
- **Does NOT enable recall** — recall stays off.
- **`cites_confirmed_memory_context` and `answered_grounded` stay byte-identical** — strict, trustworthy, existing tests untouched. The new state is added *beside* them.

## 3. Fix 2 — a third closed outcome class (`ANSWERED_MIXED_SUPPORT`)

**The honest ladder for recall-relevant answered turns:**
- **`answered_grounded`** — all cited support is confirmed `memory_context`. (Unchanged. Strict. Counts as rescue/pass.)
- **`answered_mixed_support`** (NEW) — confirmed `memory_context` present, all citations valid, but a `dialogue_anchor` is also cited, so the system **cannot prove from labels** the dated facts were carried purely by memory. *Better than ungrounded, but not proof of dated recall.* **Observed, NOT rescue credit.**
- **`answered_ungrounded`** — no confirmed memory support, invalid/unmatched citations, disallowed source types, or otherwise not provable. (Hard fail on rescue-candidate turns.)

**Pin 1 — `cites_confirmed_memory_context` is NOT changed.** It stays the strict primitive (`answered_grounded` predicate); all its existing tests pass untouched.

**New helper `citation_support(result, working_set, turn_kind) -> "grounded" | "mixed" | "ungrounded"`** (content-free):
- `"grounded"` ⟺ today's strict `cites_confirmed_memory_context(result, working_set)` is `True`.
- `"mixed"` — **both-shaped turns only** (`turn_kind == "both"`): ≥1 confirmed `memory_context` cited, all labels valid (subset of the working set), and every non-memory citation is a `dialogue_anchor`. On a pure-dated turn this same citation pattern is `"ungrounded"` — dialogue cannot supplement a dated fact (strict rule preserved).
- `"ungrounded"` — everything else.

**`classify_outcome` change (additive, provably no regression):** add `cited_mixed_support: bool = False`. Default `False` ⇒ every existing call/test is byte-identical. In the answered, non-legacy branch: `answered_grounded` is still checked **first** (so the new bool can never override a grounded verdict); then `if cited_mixed_support and unmatched_citations == 0: ANSWERED_MIXED_SUPPORT`; else `ANSWERED_UNGROUNDED`.

**Daemon wiring (`daemon/maez_daemon.py:4648`):** compute `_rk_support = citation_support(...)` once with `turn_kind="both" if (_date_addressed_turn and _dialogue_needs_or_uncertain) else "dated"`; derive `_rk_cited_grounded = (_rk_support == "grounded")` — **identical meaning to today**, so the absence/answered logic at `:5000-5006` is unchanged — and `_rk_cited_mixed = (_rk_support == "mixed")`; pass `cited_mixed_support=_rk_cited_mixed` to `classify_outcome` (`:5008`). The two bools are mutually exclusive by construction (derived from one closed value).

## 4. Fix 3 — honest dated-absence classifies as decline (with anti-laundering guard)

**Seam (triad, not legacy `asserts_absence`):** expand `_reply_asserts_dated_absence(reply)` ([daemon/maez_daemon.py:1226](../../../daemon/maez_daemon.py)) so an honest triad dated-absence reply sets `denial_kind="no_dated_memory"` + `_rk_answered=False` ([:5002-5003](../../../daemon/maez_daemon.py)) → `DECLINED_ABSENCE`. **Do not change `is_false_absence`.**

- **Normalize** curly apostrophe `’`→`'` so model replies match.
- **Add narrowly-scoped phrases:** `"don't have any record"`, `"do not have any record"`, `"have no record"` (NOT the bare substring `"any record"` — it would match "Do you have **any record**…").
- **Anti-laundering guard (NEW):** a recognized absence phrase paired with a contrastive content continuation (`" but "`) is **not** a clean decline — return `False`. This errs toward `answered_ungrounded` (strict/fail) for an ambiguous absence-plus-content reply, **never** toward laundering content as an honest decline. Tradeoff named honestly: a genuine decline that happens to contain " but " will be read as answered (and, uncited, as ungrounded) rather than `declined_absence` — the conservative, non-flattering direction.
- **Residual edge (named, scoped out):** a substring matcher cannot fully judge "absence phrase + substantive content" semantics; the deeper shape (e.g. a *recognized* phrase followed by a long content answer with no " but ") is a behavior-shape concern, scoped to the behavior slice, not pretended-solved here.

## 5. Consumer updates (Pin 2 — every reader that assumes only grounded/ungrounded)

A new closed outcome class must be handled everywhere it is produced or read; silent two-state assumptions would mis-bucket `mixed`:
- **`core/routing/recall_outcome.py`** — `OutcomeClass` enum (`:18-28`) gains `ANSWERED_MIXED_SUPPORT = "answered_mixed_support"`; `classify_outcome` + new `citation_support`.
- **`daemon/maez_daemon.py`** — the `:4648` derivation + `:5008` `classify_outcome` call (above).
- **`scripts/brain_bench/probe_runner.py`** (`:259` `cites_confirmed_memory_context`, `:267` `cited_grounded_context`, `:285`) — switch to `citation_support`, derive grounded+mixed, pass `cited_mixed_support`; `mixed` must **not** clear `grounded_categorical` (see §6(b)).
- **`scripts/recall_flip_eval/harness.py`** (`:166`, `:174`, `:191`, and the outcome-class readers at `:318-323`, `:479`) — same.
- **Flip spec** `2026-05-30-recall-triad-monitored-default-on-flip-design.md` (`:53-61` class definitions, `:232-234` A5 rescued definition) and **2b runbook** (`:112-114` benefit gate) — see §6.
- **Codex must grep for any other closed outcome-class enumeration** (e.g. `scripts/brain_bench/bench_packet.py` closed enums, dashboards) and add the value. `ContentFreeSchemaTest` checks field-name content-freeness only (verified) — no change needed there.

## 6. How each consumer reads `mixed` (two DIFFERENT semantics — do not conflate)

`answered_mixed_support` means different operational things to the two consumer families, and the wording must keep them separate or `mixed` could launder into proof:

**(a) 2b live-flip benefit reading (flip spec + 2b runbook, A5 gate) — "observe":**
- `answered_grounded` → counts for **rescue / pass**.
- `answered_mixed_support` → **observed mixed support: NOT a rescue, NOT a hard fail.** Recorded, watched, never banked as benefit.
- `answered_ungrounded` → remains **hard fail** on rescue-candidate turns.
- The rescued-turn counter (A5) stays defined on `answered_grounded` only.

**(b) benchmark / probe categorical grounding (`scripts/brain_bench/probe_runner.py`, `scripts/recall_flip_eval/harness.py`) — "does not clear":**
- `mixed` must **NOT** satisfy `grounded_categorical` (it is not proof of dated recall). Treat it like ungrounded for the *categorical-grounding* pass/fail, distinct from (a)'s "observe." Allowing `mixed` to clear categorical grounding would launder co-citation into proof — the exact trap this slice exists to avoid.

The one-line rule: **in 2b, mixed is "observe, not rescue"; in the benchmark, mixed "does not clear categorical grounding."** Same telemetry value, two correct-but-different readings.

## 7. Tests (pre-registered)

- **`citation_support` (unit):** both-shaped memory+dialogue → `"mixed"`; both-shaped dialogue-only → `"ungrounded"`; both-shaped unmatched/unconfirmed/disallowed-source → `"ungrounded"`; all-confirmed-memory → `"grounded"` (any turn_kind); pure-dated memory+dialogue → `"ungrounded"`; turn_kind omitted → strict (`"grounded"`/`"ungrounded"`, never `"mixed"`).
- **`cites_confirmed_memory_context` unchanged:** its existing tests stay green (backward-compat pin).
- **`classify_outcome` (unit):** `cited_mixed_support=True, unmatched=0, answered, triad` → `ANSWERED_MIXED_SUPPORT`; `cited_grounded_context=True` still wins (grounded checked first); `cited_mixed_support=False` default → identical to today (no regression on existing classify tests).
- **Fix 3 matcher (unit):** positives incl. "I don't have any records for January 3", curly-apostrophe variant, "have no record"; negatives incl. ordinary answer, a content/fabrication assertion, "Do you have any record of that meeting?", and **"I don't have any records for January 3, but you fixed the parser bug." → `False`** (the " but " guard).
- **Daemon-shaped (Task):** a `handle_message`-harness both-shaped turn whose focused answer cites memory+dialogue logs `answered_mixed_support` end-to-end (proves the daemon passes `turn_kind="both"` and the mixed bool flows) — not just the helper in isolation.
- **No regression:** existing `answered_grounded` / `answered_ungrounded` / `declined_absence` / ordinary cases unchanged.

## 8. Hygiene (already done outside the plan)

Runbook `config/.env`→`~/.config/maez/model.env` path fix + Correction note: **done** (2026-05-31). Stale `config/.env:19,23,24` flags: **held for explicit owner OK**.

## 9. Covenant / honesty invariants

- **Labels prove citation shape, not semantic support.** The scoreboard never claims more than its evidence: `answered_grounded` stays strict, `mixed` surfaces the ambiguity, neither libel nor flattery. New anti-laundering vector under [[producer_causality_no_caller_score_laundering]] — record on landing.
- **Producer-evidence, not benefit credit** — `mixed` is observed, never banked as rescue ([[canon_governs_canon_witness_before_claim]]).
- **No behavior/cognition change; recall stays off; `is_false_absence` byte-identical; `cites_confirmed_memory_context` byte-identical.**

## 10. Process & sequence

Codex switchboard (six-agent pre-code pass + 7+3); Claude cross-verifies every diff, runs suites independently, fires the coverage panel; merge on the legacy baseline. **Clearing-order step 1.** **Step 2 = Fix 1 continuity mechanism** (a behavior slice that also carries the mixed→grounded steering), its own brainstorm. The six-prompt re-gate is owner-run, only after both steps land — on a classifier that finally tells the truth.
