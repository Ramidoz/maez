# External-Source Consumption Brief — v1.2 Amendment Proposal

**Status:** witness-derived amendment proposal for the v1.1 external-source consumption brief at `external-source-consumption-brief.md`
**Date:** 2026-05-27
**Witness source:** `docs/slices/recall-axis-dispatcher/witness/external-source-probe-2026-05-27-daemon.md` (commit 53a820b)
**Prior fold convention:** v1.1 synthesis → Codex fold (commit c00ce95). Same shape applies for v1.2.

## Overall Verdict

**Two witness-derived findings need contract treatment before the observation window opens.** Both surfaced in the seam-8 daemon probe as contract-honest refusals that contradict operational expectations:

1. **Finding 2:** `HYBRID + no substrate + fresh SUCCESS` produces refusal even when LIVE_REDDIT succeeded (probe 4: `Check r/Python for recent posts`).
2. **Finding 3:** `_budget_blocks` silently empties `recall_blocks` when text exceeds 1200 chars/source, causing refusal when Layer 1 branch telemetry says rows succeeded (probe 5: `What were we talking about last evening?`).

Both have multiple resolution options that the brief should pick deliberately. The amendment also bundles eight carried-forward SUGGEST items from seams 4-7 review where they intersect with the same contract surfaces.

Neither finding is a regression — they are contract-language gaps that the closed reconstruction transform and the budget-vs-witness disagreement surface honestly. The slice ships honest; the contract needs the language refinement.

## Decisions Required Before Fold

### Decision A — Finding 2 resolution

**Choice between two paths:**

**A1. Add a transform row to `merge.py:_transform_for`.** When `HYBRID` framing + no substrate + fresh SUCCESS or PARTIAL, reconstruct to `FRESH_ONLY` framing + `FRESH_ONLY` hint, with `availability_limitations` recording the substrate-empty fact. The reconstruction is honest — the spec's HYBRID claim turned out wrong on substrate, but fresh succeeded, so render under FRESH_ONLY. Audit envelope records `reconstructed_from_framing=HYBRID_FRESH_VALIDATES_SUBSTRATE_CONTEXTUALIZES` so the original Layer 0 claim is recoverable.

- **Pro:** user gets the fresh evidence they asked for; no surprise refusal.
- **Pro:** producer-causality preserved via reconstructed_from_framing.
- **Con:** asymmetric with current `HYBRID + no substrate + ALL_FAILED` which still refuses (no fresh AND no substrate is genuinely empty).
- **Con:** widens the reconstruction surface that v1.1 narrowed deliberately.

**A2. Rename `DispatcherRefusalReason.FRESH_FAILURE_HYBRID_FALLBACK_ILLEGAL` and tighten the trigger.** The name should describe the actual trigger ("no row matches the reconstruction transform table") rather than imply fresh failure. New name candidates: `RECONSTRUCTION_NO_LEGAL_TRANSFORM`, `HYBRID_FALLBACK_NO_LEGAL_FRAMING`, or `SPEC_CLAIM_REALITY_MISMATCH`. Refusal continues; only the language changes.

- **Pro:** preserves the v1.1 closed-reconstruction discipline (refuse when no legal transform).
- **Pro:** honest about what the refusal means.
- **Con:** user-facing operational consequence unchanged — Reddit asks for unknown subreddits still refuse even when fresh succeeded.

**Recommendation:** A1 (add the transform row) — the operational benefit outweighs the surface widening, and the audit envelope preserves the contract honesty via `reconstructed_from_framing`.

### Decision B — Finding 3 resolution

**Choice between three paths (per witness Finding 3):**

**B1. Add `dispatcher_layer1_budget_dropped` telemetry event.** When `_budget_blocks` filters all blocks for a source, emit a structured event naming the source and the bytes-dropped count. The merge owner's `substrate_has_rows` derivation stays as-is. The telemetry surfaces the gap so observation can see it.

- **Pro:** smallest mechanical change.
- **Pro:** makes the gap visible without changing behavior.
- **Con:** doesn't fix the user-facing refusal — only documents it.

**B2. Change `substrate_has_rows` derivation in merge.py.** Use `bool(any(branch.status == SUCCESS for branch in layer1_result.branch_results))` instead of `bool(layer1_result.recall_blocks)`. The branch-level witness becomes the source of truth, not the post-budget aggregation.

- **Pro:** merge owner trusts the branch witness (producer-causality applied at the right layer).
- **Pro:** eliminates the refusal for budget-filtered-but-genuinely-substrate-present turns.
- **Con:** if `recall_blocks` is empty, the rendered substrate section will be empty even though `substrate_has_rows=True` — the rendered turn would claim substrate context without showing it.
- **Mitigation:** the renderer's `_validate_source_roles` would catch this and refuse — back to refusal, just at a different layer.

**B3. Modify `_budget_blocks` to truncate rather than drop.** When a single block exceeds `max_chars_per_source`, truncate to the cap (with a clear "...[truncated]" marker) rather than dropping it. `recall_blocks` always carries the source's evidence in some form.

- **Pro:** preserves substrate evidence in rendered output, just bounded.
- **Pro:** user gets substrate context even for long conversation chunks.
- **Con:** truncation changes the producer-causality story — the block's content_digest now doesn't match the original retrieved text.
- **Mitigation:** add an `original_chars` and `truncated: bool` field to RecallBlock so audit can record what happened.

**Recommendation:** B3 (truncate) combined with B1 (telemetry) — preserves user experience, makes truncation visible in audit, doesn't widen the substrate_has_rows derivation. The truncation marker is honest about what happened.

## Bundled SUGGEST Items (Seams 4-7)

These accumulated from prior seam reviews and fit naturally into a v1.2 fold:

| Item | Source | Recommended action |
|---|---|---|
| Paperclip-utterance disambiguation (line 342-343 in external_sources.py reserves ARXIV_OR_PAPERCLIP only when "paperclip" appears literally) | Seam 4 review | Name explicitly in brief §5: "ARXIV_OR_PAPERCLIP is reserved when the utterance contains the literal word 'paperclip'; otherwise routes to arXiv via fetch_text(fetch_type='arxiv')." Or remove the special case. Recommend: name it. |
| MAX_FRESH_CHARS_PER_SOURCE truncation cap (2000 chars in external_sources.py) | Seam 4 review | Name in brief §5: "External-source text is truncated to 2000 chars per source as a defensive cap." Add to audit envelope shape if not already captured. |
| `_LEGAL_HINT_FRAMING` duplicated in merge.py:485-517 | Seam 5 review | Import the canonical constant from spec.py, or add a comment tying these together with a CI test that asserts equivalence. |
| Regex distinction `_REDDIT_ANCHOR_RE` vs `_SUBREDDIT_ANCHOR_RE` | Seam 6 review | Add a one-line comment at each regex declaration explaining the semantic split. |
| `turn_seal_state` lumps refusal under partial_failure | Seam 7 review | Add `"refused"` as a fourth value (`clean | partial_failure | reconstructed | refused`). Telemetry distinguishes the cases. |
| `record_completed_spec` behavioral change (fires for any non-refused turn, previously required recall_blocks rows) | Seam 7 review | Name in brief §8: "After a non-refused dispatcher turn, the orchestrator records the final effective spec for next-turn Layer 2 repair inheritance regardless of whether substrate rows returned." This is implicit in the engineering pass but worth being explicit. |
| `_fresh_attempt_outcome` returns `ALL_SUCCEEDED` for empty external_sources (semantically odd) | Seam 5 review | Add `FreshAttemptOutcome.NOT_ATTEMPTED` value. Substrate-only turns report NOT_ATTEMPTED rather than the misleading ALL_SUCCEEDED. |
| `template_version_hash` placeholder string in merge.py:431 | Seam 5 review | Either compute a real content hash of the template or use a non-sha256 prefix (e.g., `"version:adr0047-merge-v1"`). |

## Patch List by Brief Section

| Brief section | Change | Source |
|---|---|---|
| §4 `FreshBlock` | Document `text` is bounded to MAX_FRESH_CHARS_PER_SOURCE=2000 chars | Bundle |
| §4 `RenderedTurn` audit shape | Add `truncated` flag to recall_block audit footprint if B3 chosen | Decision B |
| §5 `ARXIV_OR_PAPERCLIP` | Document paperclip-utterance reservation behavior explicitly | Bundle |
| §6 failure mapping | If A1 chosen: add row for `HYBRID + no_substrate + SUCCESS → reconstruct to FRESH_ONLY`. If A2 chosen: rename `FRESH_FAILURE_HYBRID_FALLBACK_ILLEGAL`. | Decision A |
| §6 closing | Document `_budget_blocks` truncation behavior (B3) or budget-drop telemetry (B1) | Decision B |
| §7 reconstruction table | If A1 chosen: extend the closed reconstruction transform table with the new row | Decision A |
| §8 wiring | Document `record_completed_spec` fires for any non-refused turn (not gated on substrate rows) | Bundle |
| §8.1 telemetry | Add `dispatcher_layer1_budget_dropped` event if B1 chosen. Add `refused` value to `turn_seal_state` enum. | Decision B + Bundle |
| §9 RED tests | Add tests for: HYBRID+no_substrate+SUCCESS path (per A1 choice), _budget_blocks truncation/drop path (per B choice), turn_seal_state=refused, NOT_ATTEMPTED outcome | All decisions |
| §10 non-goals | Add: "Paperclip executable adapter remains reserved" (clarify v1.1's reservation) | Bundle |

## What Stays Out of v1.2

Carried further (not blocking observation):

- **Layer 1 ENTITY_INDEX / LIVED_EPISODES synchronous errors:** reproduces consistently but is an adapter-level investigation, not a contract gap. Should be its own targeted seam.
- **Telegram transport probe:** still HTTP-only witnessed. Discovery brief established HTTP/Telegram convergence; live verification deferred.
- **FRESH_ONLY total-failure deterministic summary path:** not exercised live in seam 8 (LIVE_REDDIT succeeded both times). Needs either a network-isolated probe or a non-Reddit external source under degraded conditions.
- **Cold-start latency budget:** seam 8 saw 98ms warm-after-restart vs prior 848ms cold; the 50ms Layer 0 budget is repeatedly breached but telemetry surfaces it cleanly. Not a contract change, an observation-window decision.

## Recommended Path

1. **Rohit picks A and B decisions** (recommend A1 + B3+B1 combined).
2. **Codex folds v1.2 into `external-source-consumption-brief.md`** with the picked options, bundling the SUGGEST items as in the patch list.
3. **Codex implements the contract changes** in subsequent seams (small-surface follow-on commits, RED-first, one decision per commit if multiple commits are needed).
4. **Then** observation window flip — running on the cleaned contract surfaces, not the known-surprising v1.1 surfaces.

The amendment can land same-day with implementation as a small bundle (similar to ADR 0046's foundation-seam follow-ons that landed same-day as canon under the [[feedback-seam-vs-slice-cooling-off]] rule — this is contract cleanup of trapdoors that the witness identified, not a new capability surface).
