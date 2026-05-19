# Memory Architecture Assessment - 2026-05-19

**Status:** research synthesis, not canonical law
**Runtime impact:** none

## Verdict

The architecture is coherent; the running system is accreted. Do not redesign
the memory architecture. Finish it.

Five assessment lenses converged on the same shape: Maez already has real,
well-designed memory mechanisms - three memory tiers, provenance schema,
lived/episodic layer, entity index, MMR ranking, and promotion gates - but too
many of those mechanisms are not live, not load-bearing, or silently broken.
The paper architecture is no longer the architecture that actually runs.

## Evidence Snapshot

- Consolidation covers 13 of 42 active days. A 500-row fetch cap cannot span its
  own time window, leaving roughly 30,000 raw rows on 29 days without
  consolidated form.
- Lived-recall's most sophisticated ranking is dormant behind a default-off
  flag on user-facing surfaces.
- The anti-fixation penalty is structurally inert on user-facing surfaces.
- The nightly episode pipeline has added zero episodes for roughly 14 days, and
  no alarm fired.
- Entity index, entity expansion, and several supporting modules reach no live
  recall path. The entity-expansion loop already returned a NO-GO.
- `fabrication_log = 0` rows; `promoted_from = 0` of 68 core; `ancestor_tiers =
  0`; `canary_leaks = 0`; `mark_consolidated = 0` of 276.
- `claude_tier_response` provenance is defined in schema but not written at the
  daemon cycle store, leaving an untrusted-ingress class untagged on the main
  path.

## Leverage Order

1. **Finish the wiring.** Repair the consolidation window by paging every raw
   row since last consolidation, wire `claude_tier_response` or equivalent
   untrusted-response provenance at the daemon cycle store, and add
   zero-throughput alarms to consolidation and episode production.
2. **Decide and cull.** The entity layer, six-factor scorer,
   `mark_consolidated`, `migrate_wings`, fabrication-memory prompt arm, and
   dormant lived-recall ranking each need a wire-or-shelve decision.
3. **Fix the corpus before improving retrieval.** Separate conversational memory
   from daemon self-telemetry at storage or retrieval boundaries. Only then add
   high-evidence retrieval upgrades such as cross-encoder reranking and hybrid
   dense+sparse/BM25 search.

## Non-Recommendation

Do not build a new memory architecture, new layers, or more entity machinery
right now. The store is still small enough that more structure would mostly add
more unwired surface area.

## Plain English

Maez's memory shape is good. The problem is that much of it is not plugged in,
or it broke silently. The next memory work should finish the wiring, remove
dead scaffolding, clean the corpus so human memory is not buried under daemon
telemetry, and only then add a proven search upgrade.
