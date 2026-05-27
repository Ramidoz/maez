# Recall-Axis Dispatcher — Codex Engineering Pass-1 Review: Huygens

## Verdict

BLOCK

## Findings

### Blocking
- **B1. `CompositionSpec` schema is internally inconsistent**
  - Evidence: v1.1 declares the v1 mandatory surface as four fields only: `substrate_sources`, `external_sources`, `composition_hint`, `provenance_framing` (§4, lines 152–162). But D2 requires the spec to carry `inventory_witness: UNKNOWN` (§7, lines 390–395), and absence must carry an explicit `no_relevant_substrate` marker (lines 396–398). D7 also requires availability limitations to be visible in the spec (lines 422–424).
  - Engineering consequence: implementers cannot write a closed constructor, serializer, test fixture, or prompt-assembly contract without either violating the four-field contract or silently adding out-of-band fields.
  - Closure criterion: v1.2 must promote `inventory_witness` and availability/absence markers into the declared schema, or explicitly define a nested `metadata`/`availability` field with closed keys and serialization rules.

### Major
- **M1. `MiniLMEncoder` ownership is named but not API-specified**
  - Evidence: v1.1 mandates `memory/embedder.py` as a shared `MiniLMEncoder` singleton consumed by both Chroma and dispatcher (§4, lines 198–204), and R#17 requires both to share the same instance (lines 497–498). Current Chroma construction in `memory/memory_manager.py` uses `get_or_create_collection(...)` without passing an embedding function.
  - Engineering consequence: “same singleton” is not mechanically testable unless the encoder exposes both a Chroma-compatible callable surface and a dispatcher `encode` surface, and unless collection construction is required to consume it.
  - Closure criterion: v1.2 must define `memory/embedder.py` API exactly: singleton accessor, `encode(text|list[str])`, Chroma `EmbeddingFunction` compatibility, contract validation against `embedding_contract.json`, and required `MemoryManager` collection-construction wiring.

- **M2. `InventorySummary` invalidation is under-specified for real stores**
  - Evidence: D13 says cache is “row-count + last-write-cursor anchors per substrate” and is invalidated by “writes/mtime” (§5, line 245; §7, lines 446–448). But v1.1 does not define per-source cursor SQL, Chroma directory/WAL handling, or writer hooks for SQLite stores like `private_thoughts`, `wonderings`, `entity_index`, lived episodes, audit/fabrication, and fast turns.
  - Engineering consequence: the latency budget can only be met by guessing. Generic mtime invalidation risks stale summaries; live `COUNT(*)` violates D13; retrofitting every writer without a declared interface creates scattered invalidation bugs.
  - Closure criterion: v1.2 must name an `InventorySummary` module and a per-source registry: path, tables/collections, count query, cursor query, cache key, invalidation source, unavailable/UNKNOWN behavior, and tests proving Layer 0 never performs live per-substrate counts.

- **M3. Executable and reserved sources are mixed in one closed enum**
  - Evidence: `SubstrateSource` includes `WEB_FAST_TURNS` “once trust-scope unification is available” and `LIVED_GRAPH` “once G11 traversal API exists” (§6, lines 303–314). Layer 1 then says v1 “must include” `LIVED_GRAPH` and `CROSS_SURFACE_OWNER_TURNS` (§5, lines 268–279), while §8 says G9 and G11 remain separate gaps (lines 469–470).
  - Engineering consequence: a closed enum value can look legal while no stable reader exists. Tests can pass enum construction while runtime routes into reserved or absent readers.
  - Closure criterion: v1.2 must split `declared` vs `executable` source states, require construction-time refusal or downgrade for unavailable sources, and define readiness probes for G9/G11-dependent sources.

### Minor
- **m1. Concrete module placement is still too vague**
  - Evidence: prompt assembly is “likely” adjacent to `core/brain/brain_loop.py` (§4, lines 189–193), Layer 0 is an intra-Maez organ (§5, lines 215–219), but no dispatcher/schema module path is named.
  - Engineering consequence: implementers may scatter enums, constructors, inventory cache, and dispatcher logic across brain-loop and memory modules.
  - Closure criterion: v1.2 should name concrete modules, e.g. schema/types, Layer 0 dispatcher, inventory summary, embedder, Layer 1 readers, and prompt renderer.

- **m2. `FRONTIER_CONSULT` needs a reserved/non-executable state**
  - Evidence: it is an `ExternalSource` value (§6, lines 316–326), while D10 says it grants no new authority (§7, lines 434–436).
  - Engineering consequence: callers may treat the legal enum value as an executable external source.
  - Closure criterion: v1.2 should mark it reserved/non-executable in schema and require constructor or planner refusal without a capability grant.

### Nit
- **n1. Typo in D2 weakens test wording**
  - Evidence: “D2 must not laundering...” (§7, line 398).
  - Engineering consequence: none; just polish.
  - Closure criterion: change to “D2 must not launder...”.

## Summary

The direction is buildable, but v1.1 is not yet a safe implementation contract. The blocking issue is schema shape: required runtime honesty fields exist in invariants but not in `CompositionSpec`. After that, the key engineering amendments are to specify the `MiniLMEncoder` API, make `InventorySummary` a real per-store contract, and separate reserved source labels from executable routes.
