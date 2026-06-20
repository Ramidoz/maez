# Handoff — Learned Tool-Routing Slice 1 (the priors spine) — REVIEW GATE

**Date:** 2026-06-20. **Branch:** `learned-routing-slice1` (tip `bd1d48e`; local-only, NOT pushed, NOT merged).
**Status:** built (Task 0 + 6 implementation commits) + Claude two-stage reviewed per the owner's calibration (Task 0 light; Tasks 2/3/5 FULL spec+quality; Tasks 1/4 light controller-verified). **STOPPED at the review gate** — awaiting Codex cross-lane, then owner breath. NOT live (all four flags default-off).
**Spec:** `docs/superpowers/specs/2026-06-20-learned-tool-routing-organ-design.md`. **Plan:** `docs/superpowers/plans/2026-06-20-learned-tool-routing-slice1.md`.

## What this slice does (one line)

Closes the learning loop on routing: it teaches the existing `routing_observations` notebook to record *"that web reach was unusable"*, files each request under a *learnt* class, and reads it back into a **prior + confidence** that — once witnessed — can suppress the keyword reflex that causes the Barchart loop. No hardcoding; all learnt; shadow-first.

## Commits (Task 0 + 6)

- `f8711ed` docs(proof): Task 0 GO — write-back seam / signal / class fork resolved.
- `29df733` **Task 1** — `attach_post_turn_quality` write-back (UPDATE-by-id, fail-silent) + `post_turn_signal` col.
- `87cbf54` **Task 2 (1a, behavior)** — calibrate the teacher: post-synthesis `unusable` signal written back.
- `b59ef58` **Task 3a** — `classify_request_class` module (exact-hash; Layer0 branch tested but `_LAYER0_ENABLED=False`).
- `47aa722` **Task 3b (behavior)** — forward-only `request_class_*` columns + capture seam.
- `61422a7` **Task 4 (1c)** — pure priors reader (`learn_priors` → `RoutingPrior`, honest cold-start).
- `dc8854f` **Task 5 (behavior)** — shadow log + flag-gated learned veto over `needs_web_search`.
- `bd1d48e` cleanup — drop dead `_BAD` constant.

## The four flags (all default-off = byte-identical)

| Flag | What it turns on |
|---|---|
| `MAEZ_ROUTING_QUALITY_WRITEBACK` | 1a: revise a row's `outcome_quality` → `unusable` when the reply got support-gate caveats OR the search was nonempty-but-thin |
| `MAEZ_ROUTING_CLASS_CAPTURE` | 1b: persist the learnt request-class (exact `utterance_hash`) on new rows |
| `MAEZ_ROUTING_PRIORS_SHADOW` | 1c: compute + log the prior + `would_veto` per reflex-eligible turn (NO behavior change) |
| `MAEZ_ROUTING_PRIORS_ENABLED` | graduation: a CONFIDENT-bad prior (conf≥0.6, success≤0.4) suppresses the reflex |

## Codex cross-lane review anchors

1. **Off = byte-identical (the cardinal invariant), verified per behavior task.** Both routing-priors flags off → no store read, no classify, `_reflex == needs_web_search(text)`, gate unchanged. WRITEBACK/CLASS_CAPTURE off → no store call / class fields NULL.
2. **Teacher calibration is honest (Codex must-fix #1 resolved).** `outcome_quality` → `unusable` ONLY on `caveated_unsupported≥1` OR (`_compute_quality(sr).quality=="thin"` AND `result_count>0`) — uses the REAL thin signal, NOT `evidence_block_count`; a true-empty search keeps `empty_but_honest` (guard tested). Main DB confirmed the wound (195/211 `structured_evidence` pre-calibration).
3. **The write-back seam is real (Codex pin resolved).** `observe_focused_support_gate` now returns `(reply, gate_receipt)` (reply string unchanged; one production caller updated); `attach_post_turn_quality(id)` is the only update path; the id is threaded post-synthesis.
4. **Grouping is learnt + forward-only (Codex must-fix #2 resolved).** Exact-`utterance_hash` class (Task 0 chose hash-only: Layer0's MiniLM encode too heavy at the live seam); old rows NOT backfilled (`request_class_id IS NOT NULL` filters priors); `producer_version` bumped v1→v2 (provenance only — nothing branches on it).
5. **The veto is conservative + lookup-parity holds.** Confident-bad-only; the veto's `classify_request_class(text)[0]` matches the function that STORED the class → priors are findable. Only the 5874 gate changed; the voice path (`needs_web_search` ~7881) is untouched.
6. **Fail-safe + scope.** The prior consult is `try/except` (a store/classify error → `_prior=None` → no veto, reply unbroken). Untouched: the strict honesty-gate LOGIC (only its return shape changed), daemon S7 path, Telegram, time-sense, the cockpit-reauth work.

## Verification

5 new test modules GREEN; regression (`test_routing_observation` + `test_support_gate` + `test_grounding_shadow`) GREEN; ruff clean across all touched files.

## GRADUATION CONCERN (record before flipping ENABLED default-on)

`learn_priors(_default_store())` runs a full-table read + re-aggregation **per reflex-eligible turn** when a flag is on. Fine for the short witness phase (flag-gated, off-path untouched, small table). **Before ENABLED ever becomes durable/default-on, add caching** (memoize on max `created_at` / row count, or refresh on interval) — else it's a live-path latency item as the priors store grows.

## Owner-breath (after both-lanes PASS + merge — owner-sovereign)

Code + flags; restart `maez`. Then the **witness recipe** (forward-only — the lesson must be lived):
1. Set `MAEZ_ROUTING_QUALITY_WRITEBACK=1`, `MAEZ_ROUTING_CLASS_CAPTURE=1`, `MAEZ_ROUTING_PRIORS_SHADOW=1` (NOT yet `ENABLED`).
2. Live a handful of "summarize today's signals"-class turns (the ones that get caveats / thin junk).
3. Paste the shadow receipt: `grep routing_prior_shadow` in the logs — expect a `would_veto=True` with a `RoutingPrior(... success_rate≈low, confidence≥0.6)` for the signals-class, backed by real `unusable` rows (`SELECT outcome_quality,post_turn_signal,request_class_id FROM routing_observations WHERE post_turn_signal IS NOT NULL`).
4. ONLY THEN flip `MAEZ_ROUTING_PRIORS_ENABLED=1` and witness the same prompt no longer reflexively searching.

NO autonomous scheduled check — paste when you've lived the turns.
