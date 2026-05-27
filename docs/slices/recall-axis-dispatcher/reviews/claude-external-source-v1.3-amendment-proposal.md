# External-Source Consumption Brief — v1.3 Amendment Proposal

**Status:** witness-derived amendment proposal for the v1.2 external-source consumption brief
**Date:** 2026-05-27
**Witness source:** `docs/slices/recall-axis-dispatcher/witness/external-source-v1p2-verify-2026-05-27-daemon.md` (commit b4e1df2)
**Prior fold convention:** v1.2 synthesis → Rohit decisions → Codex fold → Codex implementation seams. Same shape for v1.3.

## Overall Verdict

**One witness-derived finding from v1.2 verification needs contract treatment.** Finding 6 surfaced when B3+B1 stopped silently dropping oversized substrate rows: the renderer's `_validate_source_roles` rejects rendering when Layer 0's spec lists multiple substrate_sources but only some branches return rows.

This is a small, well-scoped gap. Option A from the v1.2 verification witness is pre-locked: merge filters `effective_spec.substrate_sources` to row-producing sources only, audit preserves original Layer 0 claim via existing `reconstructed_from_framing` / `reconstructed_from_hint` fields.

No decisions required. This proposal documents the patch shape for Codex to fold.

## The Asymmetry Being Closed

Current merge behavior at `core/dispatcher/merge.py`:

| Source axis | Behavior in rebuilt `effective_spec` | Filtered by row presence? |
|---|---|---|
| `external_sources` | `_external_sources_for(framing, accepted_fresh_blocks)` returns `tuple(sorted({block.source for block in accepted_fresh_blocks}))` | **YES** — only sources with accepted FreshBlocks |
| `substrate_sources` | `list(spec.substrate_sources) if include_substrate else []` | **NO** — passes through unfiltered |

The external side already implements the discipline. The substrate side is asymmetric: when Layer 1 returns mixed-status results (TELEGRAM_SEMANTIC SUCCESS, ENTITY_INDEX ERROR, LIVED_EPISODES ERROR), the rebuilt `effective_spec.substrate_sources` still lists all three, but `_source_summaries` only produces a summary for TELEGRAM_SEMANTIC. The renderer's `_validate_source_roles` refuses with `PROVENANCE_TEMPLATE_MISMATCH: missing source summaries for ENTITY_INDEX, LIVED_EPISODES`.

v1.3 makes the substrate axis symmetric with the external axis.

## v1.3 Brief Amendment Shape

### Contract change in §7 (Composition and Rendering)

The rebuilt `effective_spec.substrate_sources` reflects only those substrate sources that actually contributed rows to `recall_blocks` (post-budget truncation). Sources whose Layer 1 branches errored, timed out, or returned empty are omitted from the rebuilt spec. Audit envelope preserves the original Layer 0 substrate_sources claim via the existing `reconstructed_from_framing` / `reconstructed_from_hint` fields when the filtered list differs from the original.

This is symmetric with the existing external-source behavior: external_sources are already filtered to accepted blocks; substrate_sources now follow the same rule.

### Audit envelope clarification

When the filtered substrate_sources differs from `spec.substrate_sources` (i.e., at least one source was dropped because it returned no rows), the merge's `reconstructed` flag triggers (per the existing `_effective_spec` logic), and `reconstructed_from_framing` + `reconstructed_from_hint` record the original Layer 0 claim. The audit envelope's `availability_limitations` extends with `NO_RELEVANT_SUBSTRATE` per the existing limitation-tracking behavior (already added in v1.2 A1 fold).

### Behavior in `_source_summaries`

Continues unchanged. The function already iterates `spec.substrate_sources` and builds summaries from `recall_blocks` matching each source. After the v1.3 filtering, `effective_spec.substrate_sources` only contains sources with rows, so every iteration produces a non-empty summary.

### Renderer behavior

No change to `provenance_renderer.py`. The existing `_validate_source_roles` strictness remains intact — it just no longer fires false-positive refusals because the rebuilt spec is now honest about which sources actually rendered.

## Patch List by Brief Section

| Brief section | Change |
|---|---|
| §7 Composition and Rendering | Document substrate-source filtering symmetric with external; rebuilt spec contains only row-producing sources |
| §7 Audit envelope | Document that `reconstructed_from_framing` / `_hint` propagate when substrate_sources list shrinks vs the original Layer 0 emission |
| §6 Failure table | No changes (filtering happens before render; `PROVENANCE_TEMPLATE_MISMATCH` should no longer fire from this case) |
| §9 RED test anchors | Add test for mixed-status substrate fan-out renders correctly with truncated row + filtered substrate_sources |
| §10 Non-goals | Add: "Do not change `provenance_renderer._validate_source_roles` strictness — the v1.3 filter is upstream of renderer validation" |
| §11 Predicted Effect | Probe 5 (memory query with TELEGRAM_SEMANTIC rows + ENTITY_INDEX/LIVED_EPISODES errors) should render `[memory evidence]` with truncated TELEGRAM_SEMANTIC content; audit envelope preserves the original three-source Layer 0 claim |

## Implementation Seam Shape

Single seam, small surface, RED-first.

**File:** `core/dispatcher/merge.py` only.

**Change:**

In `_effective_spec`, replace:

```python
substrate_sources = list(spec.substrate_sources) if include_substrate else []
```

with a filtered derivation:

```python
substrate_sources = (
    _substrate_sources_with_rows(spec.substrate_sources, layer1_result.recall_blocks)
    if include_substrate
    else []
)
```

Add helper:

```python
def _substrate_sources_with_rows(
    declared: Sequence[SubstrateSource],
    recall_blocks: Sequence[RecallBlock],
) -> list[SubstrateSource]:
    sources_with_rows = {block.source for block in recall_blocks}
    return [source for source in declared if source in sources_with_rows]
```

The `_effective_spec` function signature needs `layer1_result.recall_blocks` available — currently it takes `accepted_fresh_blocks` only. Either pass `recall_blocks` through from `merge_fanout_results`, or pass the full `Layer1FanoutResult` to `_effective_spec`. Recommend the smaller change: pass `recall_blocks` as an additional kwarg.

The existing `reconstructed` boolean derivation at line 203-208 already checks `substrate_sources != list(spec.substrate_sources)` — so when the v1.3 filter drops sources, `reconstructed=True` fires automatically, and `reconstructed_from_framing` / `reconstructed_from_hint` propagate to audit. No additional audit-envelope code needed.

## RED Tests

Add to `tests/test_dispatcher_merge.py`:

1. **`test_substrate_sources_filtered_to_those_with_rows`** — A SUBSTRATE_ONLY spec with three substrate_sources (e.g., TELEGRAM_SEMANTIC, ENTITY_INDEX, LIVED_EPISODES) where Layer 1 returns rows only for TELEGRAM_SEMANTIC. The rebuilt effective_spec.substrate_sources should contain only TELEGRAM_SEMANTIC. The rendered turn should have `[memory evidence] ...` with TELEGRAM_SEMANTIC content; audit envelope should carry `reconstructed_from_framing=SUBSTRATE_ONLY_NO_FRESH_VALIDATION` and `reconstructed_from_hint=SUBSTRATE_ONLY` (the originals).

2. **`test_substrate_filter_preserves_renderable_state`** — Mixed-status Layer 1 result no longer triggers `PROVENANCE_TEMPLATE_MISMATCH`. The renderer receives an effective_spec where every listed source has a corresponding summary.

3. **`test_substrate_sources_unchanged_when_all_branches_have_rows`** — If all Layer 1 branches return rows, the filter is a no-op; effective_spec.substrate_sources matches spec.substrate_sources; `reconstructed` flag does not fire from substrate filtering alone.

## What Stays Out of v1.3

- **Layer 1 ENTITY_INDEX / LIVED_EPISODES synchronous errors:** reproduced for the third time in the v1.2 verification witness. This is an adapter-level investigation, not a merge contract issue. Should be its own seam once v1.3 closes the rendering path that exposed it.
- **Telegram transport probe:** still HTTP-only witnessed.
- **FRESH_ONLY total-failure deterministic summary path:** not exercised yet; LIVE_REDDIT has succeeded both witness times.
- **Renderer-side strictness relaxation (Option C from v1.2 verification witness):** explicitly deferred. The merge filter is the cleaner discipline.
- **Layer 0 inventory-aware source exclusion (Option D from v1.2 verification witness):** rejected on planner-authority grounds (Layer 0 should not learn from runtime errors).

## Recommended Path

1. **Codex folds v1.3 amendment** into `external-source-consumption-brief.md` (single commit, similar to 0a85d10 for v1.2).
2. **Codex implements the v1.3 merge filter** as a single follow-on seam, RED-first (single commit, similar to 7e35c13 or 697d43b).
3. **Live re-verification** by replaying seam-8 probe 5 (memory query) against the v1.3 daemon — expected: `[memory evidence]` TELEGRAM_SEMANTIC truncated content rendered honestly with audit-preserved original Layer 0 claim.
4. **Then** observation window flip on the cleaned slice.

Per [[feedback-seam-vs-slice-cooling-off]], v1.3 amendment + implementation can land same-day. This is contract cleanup of a witness-identified trapdoor, not new capability.
