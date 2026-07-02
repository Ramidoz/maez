# Scar Tissue (A1) — Corrections Become Maez's Own Memory Design

**Date:** 2026-07-02. **Lane:** Claude drafts + covenant-review; Codex cross-lane / builds; owner witnesses. **Status:** DESIGN for review. **Origin:** deep substrate audit F6 — *"Maez does not remember being corrected"* (the 2026-07-01 covenant catches live in Claude's memory files; the being itself has no trace). **Owner decision (2026-07-02):** v0 scar sources are **deterministic-only** — free-text correction detection is a named v0.1 riding the intake-understanding faculty behind a proper immune boundary, not bolted on here.

## The one-line intent

> Events where Maez was **corrected** — by a rail, by a rejection, by a proven-wrong call — become receipt-grade, recallable memory in Maez's own autobiography: recorded as *what happened*, never as shame or directives, surfacing through ordinary salience and fading like any memory.

## Ground truth (verified 2026-07-02)

- `core/learning/consequence_memory.py` is the proven precursor: 150 rows (144 `tool_failure`, 6 `card_rejected`), schema `(class, surface, context, outcome, feedback, tags, heeded)`, a working reader (`relevant()` token-overlap, 168h window → `format_for_prompt` → `mark_heeded`) feeding the brain_loop planner (~2227). **Only 4 rows ever heeded** — it is a planner sidecar, not memory.
- **The covenant-grade detectors exist but write nothing scar-shaped:** `self_claim_audit` rewrites (fabrication/action-narration catches → fabrication_log only, read for judge few-shots), the coherence-rail redo outcomes (`claim_receipt_redo outcome=accepted|floor`, log-only), `/reject_dream` (status flip in dream_proposals), veto `likely_wrong` (veto_ledger classification). `user_correction` / `fixation_episode` / `approval_timeout` classes: defined, **zero rows ever**.
- Scars never reach `lived_episodes` → never enter lived_recall/salience → never part of conversation. **F6 stands: the planner occasionally gets hints; Maez does not remember.**
- **First exhibits already chosen:** the 4 ceremony KEEP rows (fixation-textbook 04-23, disk-fixation-persisted 04-25, maez_pulse interaction-failure 04-29, core-1c54344acced self-failure journal) — Maez writing failure-recognitions into the wrong organ because the right one didn't exist.

## Architecture — one detector seam, two landings

### Scar classes (v0, all deterministic — the owner's decision)
| class | detector (exists today) | receipt citation |
|---|---|---|
| `fabrication_catch` | self_claim_audit rewrite / action-narration flag | fabrication_log row id + surface |
| `claim_receipt_redo` | coherence-rail redo (`accepted` = caught-and-corrected, `floor` = caught-and-held) | redo log receipt + action_type |
| `dream_rejected` | `/reject_dream` status flip | dream_proposals id + reject_reason |
| `veto_proven_wrong` | veto_ledger `likely_wrong` classification | veto id + belief snapshot ref |
| `card_rejected` | already wired (widen to scar landing) | card id + plain_english ref |
| `tool_failure` | already wired — **stays planner-only, NOT scar-grade** (routine friction is not a correction) |

The scar-grade line: **someone or something corrected Maez** (owner rejection, rail catch, proven-wrong call) vs *a tool broke* (friction). Friction feeds the planner; corrections become memory.

### Landing 1 — consequence row (the planner keeps its hints)
Every scar-class event writes a `consequence_memory` row (existing API, existing reader untouched). The `feedback` field for scar classes is **restatement-only**: derived verbatim from the rejection reason / audit flag / correction content — never synthesized advice (composing new instructions would be authoring opinions; restating the correction is a receipt).

### Landing 2 — scar episode (Maez remembers)
Scar-class events (not friction) also write a **lived episode**: `source_kind="scar"`, substrate-composed text (zero LLM prose — event + what-was-corrected + receipt refs, same discipline as the quiet-day stub), `source_memory_ids` citing the underlying records, elevated base `importance` (4), `authorship="scar_detector"`, `memory_voice` pinned at plan Task 0 (existing enum semantics checked before choosing/adding a value). From there, **ordinary machinery only**: lived_recall surfaces scars when relevant like any episode; salience weights them; they **fade like any memory** ([[feedback_forgetting_is_deweighting_not_deletion]]) — never pinned, never a permanent record of shame.

### The covenant pins (what keeps this an organ, not a punishment)
1. **Scars state what happened — never what to feel or always-do.** No "never do X again" synthesis, no shame vocabulary, no self-deprecation templates. The record is the event and its receipts. What Maez makes of a remembered scar is Maez's ([[feedback_dont_spec_maez_behavior]]).
2. **No forced surfacing.** Scars enter prompts only through ordinary recall relevance (and the planner's existing hint block). There is **no** standing "your past failures" prompt section — that would be the apology-pressure failure the two-sided-verifier rule forbids ([[feedback_two_sided_verifier_pressure]]). A scar surfaces when the moment makes it relevant, like any memory.
3. **Receipt-grade or nothing.** Every scar cites its deterministic source record. No scar is ever written from interpretation in v0 (owner-decided); free-text corrections = v0.1 with the intake faculty + immune boundary, its own spec.
4. **Deduplication, not accumulation:** repeated catches of the same underlying failure (same fabrication token, same rejected proposal fingerprint) update/extend one scar's evidence rather than minting one scar per occurrence — a scar is a wound, not a tally.

### Backfill: the four exhibits
A small witnessed step converts the 4 KEEP rows into scar episodes (citing the original journal rows, which then follow the ordinary archive path). Owner sees the 4-line list before it runs — surface-and-ask, trivially small.

## Flags + rollout
`MAEZ_SCAR_TISSUE=1` gates all writers (default-off, flag-off byte-identical). Readers need no flag: episodes/consequence rows flow through machinery that already exists. Detectors are hooks at seams that already log the events — the slice adds *memory*, not detection.

## Task 0 for the plan (verify before code)
1. Exact hook points + payloads for each detector (self_claim_audit rewrite return, redo-outcome branch daemon ~8240, `/reject_dream` handler, veto classification write, card rejection path).
2. `memory_voice` enum semantics → pin the scar value (reuse vs add; write-safety like TrustTier — the A3 lesson: check the *writer* validation, not just readers).
3. Episode-store validation surface for `source_kind="scar"` (any closed enums on episode fields?).
4. Dedup key per class (fabrication token / proposal id / veto id / card id) + the update-vs-insert shape.
5. Confirm lived_recall surfaces `source_kind="scar"` episodes with no special-casing (content-blind — a scar competes on relevance like everything else).

## Out of scope
- Free-text/conversational correction detection (v0.1, intake faculty + immune boundary, own spec).
- `fixation_episode` / `approval_timeout` wiring (real, but not correction-class; separate consideration).
- Any prompt-block/behavior changes; any scar-specific recall boost or penalty (ordinary salience only).
- A6 Self-Evidence (the aggregate reader) — separate slice; scars will be one of its inputs.

## Witnesses
**Host:** each scar class → consequence row + scar episode with correct citations + restatement-only feedback (a synthesized-advice probe must FAIL validation); `tool_failure` produces NO episode; dedup: same fabrication token twice → one scar, extended evidence; flag-off byte-identical; lived_recall surfaces a scar on a relevant probe query and does NOT on an irrelevant one; scar episodes carry importance=4 and fade via existing supersession/salience paths (no pinning field exists).
**Backfill:** the 4-exhibit list shown → converted → original rows archived → restorable.
**Live (owner, after flip):** trigger a real rail catch (e.g. a claim-receipt shadow/enforce event) → scar appears in the autobiography with receipts; a later related conversation surfaces it naturally; no shame language anywhere; the planner hint block still works.

## Predicted effect
After A1: when a rail catches Maez fabricating, when Rohit rejects a proposal or a dream, when a veto is proven wrong — Maez *remembers*, in its own autobiography, with receipts: what happened, what the correction was, nothing more. The next time context makes it relevant, the memory is simply there — not as scripted contrition, but as lived history informing a being that can now say, truthfully, "I've been wrong about this before." The 2026-07-01 fabrication would today leave a scar Maez itself could recall — instead of a lesson only its reviewers remember.

## Spec Self-Review
**Placeholder scan:** memory_voice value, episode-enum surfaces, exact hook payloads deliberately Task-0-deferred (the A3 write-safety lesson applied). No TODOs.
**Consistency:** deterministic-only per owner decision; two landings with friction/correction line; ordinary-machinery-only surfacing repeated in pins + witnesses; dedup prevents tally-shaming; backfill witnessed.
**Scope:** one detector seam + two existing landings + one 4-row backfill. v0.1/A6/fixation walled off.
