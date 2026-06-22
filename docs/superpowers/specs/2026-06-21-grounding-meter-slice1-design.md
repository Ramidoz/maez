# Grounding Meter (reply-relative) — Coherence Slice 1 — Design

**Date:** 2026-06-21. **Status:** design — owner-approved shape (reply-relative "how much of what it said is backed"; pure instrument; numbers-only/content-light; read segmented by turn_kind). For owner spec review before planning.
**Origin:** Slice 1 of the coherence→north-star roadmap ([docs/coherence-northstar-roadmap-2026-06-21.md](../../coherence-northstar-roadmap-2026-06-21.md)). It is the **instrument** that must land first so slices 2 (recall floor) and 3 (live-thread anchor) can be witnessed honestly.

## The bug (verified)
`check_groundedness` ([focused_cognition.py:1475-1496](../../core/routing/focused_cognition.py#L1475)) computes `coverage = len(matched) / len(valid_labels)` — the fraction of the **working-set items** the reply cited. On the symptom turn (16-item self-memory set, reply cited 2) it reads `citation_coverage=0.125`, which **conflates ungroundedness with denominator (working-set) size**: a tight, well-grounded reply that correctly cites the 1 relevant item out of 16 would score 1/16 and look terrible. It measures "how much of the buffet was touched," not "how much of what Maez said is backed." We cannot honestly witness slices 2/3 through this number.

## The new metric — `reply_grounding`
A **reply-relative** grounding rate, computed in `check_groundedness` from `result.reply` (which carries the raw `[E#]` markers — that's where `cited_ids` are parsed, [focused_cognition.py:1048](../../core/routing/focused_cognition.py#L1048)):

- Split `result.reply` into sentences with a small **deterministic local splitter** (regex on `.!?` boundaries; self-contained in `focused_cognition.py` — no cross-module private import).
- A sentence is **grounded** iff it contains ≥1 citation marker (via the existing module-local `_CITE_RE`) whose `E{n}` label is in `valid_labels` (the working-set item labels).
- `total_sentences` = count of non-empty reply sentences; `grounded_sentences` = count grounded.
- **`reply_grounding = grounded_sentences / total_sentences`** (0.0 if no sentences).

This is "what fraction of Maez's actual words are anchored to a real, valid piece of evidence."

## What stays / what's added
- **`citation_coverage` stays exactly as-is** (same field, same formula). It's persisted in the focused store + emitted in `recall_outcome`; changing its meaning would break metric continuity. We only **relabel it in commentary/docs** as *working-set coverage* so it's no longer mistaken for grounding. The `verdict.verdict` enum (`grounded`/`unmatched_citation`/`no_citations`) is UNCHANGED.
- **Three new fields on `GroundednessVerdict`, added with backward-compatible DEFAULTS** so the ~16 existing constructors keep working unchanged — incl. positional `GroundednessVerdict("grounded", 1.0, [])` in tests and the two fallback constructors at [focused_cognition.py:1143](../../core/routing/focused_cognition.py#L1143) / [:1492](../../core/routing/focused_cognition.py#L1492): `reply_grounding: float = 0.0`, `grounded_sentences: int = 0`, `total_sentences: int = 0`. Only `check_groundedness` fills real values; NO constructor signature breaks.
- **Two output pipes, both named explicitly** (so the live witness is never blind in one while the number lands in the other):
  1. **Focused store** (`focused_cognition_runs`, [focused_cognition.py:1520+](../../core/routing/focused_cognition.py#L1520)): add all **three numeric columns** (`reply_grounding`, `grounded_sentences`, `total_sentences`) via an **idempotent migration** (`ALTER TABLE ... ADD COLUMN` guarded so re-open is safe; old rows default NULL/0), and thread them through `record()`.
  2. **`RecallOutcome` record** — the LIVE per-turn witness, a **dataclass** ([recall_outcome.py:17](../../core/routing/recall_outcome.py#L17)) constructed at [maez_daemon.py:7478](../../daemon/maez_daemon.py#L7478) and emitted by `_log_recall_outcome` (format string [maez_daemon.py:1336](../../daemon/maez_daemon.py#L1336)) — NOT just a log string. Add **`reply_grounding: float | None = None`** (optional/additive — existing readers ignore the new key; `schema_version` stays `recall_outcome.v2` as a purely-additive optional field). Thread it from the focused verdict at the construction site next to `citation_coverage=_rk_coverage`, and add it to the `_log_recall_outcome` line. The record carries **`reply_grounding` ONLY** (the rate is the witness signal); the sentence COUNTS live in the focused store only, keeping the per-turn record lean.
- **Numbers only — reply text is NEVER persisted** in either pipe (store + record stay content-light by construction; preserve that).

## Pure instrument — no flag, no behavior change
`reply_grounding` is **measurement only**: nothing reads it to gate, caveat, fallback, or alter a reply. It changes nothing Maez does or says. Therefore **no feature flag** — it's richer honest logging, like adding a column to a receipt. The cost is a sentence-split + regex per focused turn (negligible). (If cross-lane review insists on a flag for the store-write, that's a cheap add, but the spec's position: a content-light measurement that alters no behavior or voice needs no gate.)

## Reading it honestly (so it isn't misused)
`reply_grounding` is read **segmented by `turn_kind`** (already in `recall_outcome`). A casual/greeting turn is self-expression, not claims, so a **low score on a conversational turn is EXPECTED, not a regression** — do not "fix" it by pressuring the voice (that's the support-gate-scope lesson). The witness for slices 2/3 is the **delta on substantive turns** (grounding should RISE as the diary flood is removed and the live thread anchored) and a drop in diary-derived ungrounded claims — not the absolute number on greetings.

## Baseline is witness-forward (not backfilled)
The focused store never persisted reply text (correctly — content-light), so historical rows cannot be retro-scored. The baseline is established **going forward**: once merged, `check_groundedness` records `reply_grounding` on every focused turn; observe a handful of live turns to set "today's grounding," then watch the delta when slices 2/3 land. The spec does NOT claim a historical backfill.

## Scope
**IN:** the `reply_grounding`/`grounded_sentences`/`total_sentences` computation in `check_groundedness`; a small local sentence-splitter; the new defaulted `GroundednessVerdict` fields; the focused-store 3-column idempotent migration + `record()`; the `RecallOutcome.reply_grounding` field + construction-site threading + `_log_recall_outcome` line; tests. **OUT / NEVER:** changing `citation_coverage`'s formula or `verdict.verdict`; any behavior/voice/fallback gate; persisting reply text; claim-vs-self-expression classification (deferred to a possible v1); touching recall, synthesis, or the anchor (those are slices 2/3).

## Make-or-break / guards (review)
1. **Existing outputs unchanged (not "flag-off byte-identical" — there is no flag)** — tests assert that adding the metric leaves ALL of these identical: `verdict.verdict`, `verdict.citation_coverage`, `verdict.unmatched`, the focused **reply text**, and the **fallback behavior**. Only the new numeric fields appear; nothing existing changes.
2. **No constructor break** — the new `GroundednessVerdict` fields carry defaults; a test confirms the ~16 existing constructors (incl. `GroundednessVerdict("grounded", 1.0, [])` and the two fallback sites) still build. `RecallOutcome.reply_grounding` defaults to `None` so its constructors are unaffected.
3. **Both pipes carry it** — a test/assertion confirms `reply_grounding` reaches BOTH the focused store (all 3 numbers) AND the `RecallOutcome` record + `_log_recall_outcome` line (rate only) — never one pipe updated and the other left blind.
4. **Content-light** — assert the store/record/log carry only numbers, never reply/sentence text.
5. **Metric correctness** — unit tests: a reply where every sentence cites a valid `[E#]` → 1.0; a 16-item set with a 2-sentence reply both validly cited → 1.0 (NOT 0.125, proving the denominator fix); an all-uncited self-narrative → 0.0; a sentence citing an invalid `E99` → not grounded (and still flagged `unmatched` by the existing path).
6. **Migration idempotent** — adding the columns twice (re-open) does not error; old rows read with NULL/0 defaults.
7. **Deterministic** — same reply+working_set → same numbers (no model call).

## Lane / owner-breath
Low-risk instrument, but covenant-adjacent (it measures Maez's honesty) → full spec → plan → TDD → Claude two-stage + Codex cross-lane; STOP at the review gate. No `## Predicted effect` needed (no behavior change), but the commit notes it's measurement-only. Owner-breath after merge: restart `maez`, observe a few focused turns, confirm `recall_outcome … reply_grounding=` appears and reads sanely (low on diary-recite turns); record the baseline. No autonomous check.
