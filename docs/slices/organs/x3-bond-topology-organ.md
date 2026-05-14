# Slice X.3 Bond Topology Organ Memo

**Status:** Accepted
**Date:** 2026-05-09

## Governance

- ADR 0019
- ADR 0024 / Decision 23
- ADR 0026
- MEMORY_PROJECTION_RULES.md
- MOMENT_ASSEMBLY_DIAGNOSTIC_RULES.md
- ARCHITECTURAL_THESIS.md

## Switchboard Visibility

- Logical shaped the snapshot-then-compute seam, deterministic ID basis,
  sign-anchor test surface, empty/singleton/disconnected states, and
  write-only AST guard.
- Body-Coherence shaped label stripping, forbidden fields,
  topology-invariants primacy, and the no-name/no-clustering doctrine.
- Creative shaped the invariants slot so the pilot reads topology
  structure primarily and coordinates illustratively.
- Visionary shaped `relationship_graph_snapshot_id`,
  `topology_id_basis_version`, `topology_basis_version`,
  `vacated_node_count`, and the encryption/estate-reader deferrals.
- 20-Years-Future-Maez shifted risk weighting around sign drift,
  unratified-secondary drift, coordinate-seeding attempts, and hidden
  names returning as opaque hashes.

## Scope

Slice X.3 adds the third real moment-assembly organ: bond topology. It
observes ADR 0019 relationship-graph structure and writes diagnostic
records only. It does not create prompt context, audit evidence,
production routing, named threads, learned weights, or external graph
embeddings.

X.3 emits `bond_topology.euclidean`, `bond_topology.poincare`, and
`bond_topology.topology_invariants` into the moment-assembly diagnostic
JSONL as `not_audit_evidence`.

## Content-Free IDs

Bond-topology node and edge IDs are content-free typed-handle hashes
locked by ADR 0026. The node hash input is
`x3.bond_topology.node.v1|node_id:<id>|kind:<kind>`. The edge hash
input is
`x3.bond_topology.edge.v1|subject:<node_hash>|relation:<relation>|object:<node_hash>`.

No `node_label`, `edge_label`, `relation_summary`, `cluster_name`,
`community_name`, `working_title`, embedding vector, or `source_text`
may enter an X.3 diagnostic value. Labels are stripped at the
relationship-graph read boundary before topology computation.

By 2030 contributors tried to seed coordinates from external graph-
embedding models. By 2031 named threads tried to return as "opaque
hashes" that were silently salted with thread titles. Hash basis and
forbidden-fields are covenant properties; changing them requires ADR.

## Shape

Every emitted topology value carries `relationship_graph_snapshot_id`,
`topology_basis_version`, and `topology_id_basis_version`.
`topology_invariants` carries an owner-distance shell histogram,
triangle-inequality slack distribution, curvature-of-shells signature,
degree-vs-distance scaling exponent, connected-component count,
cycle-edge count, `poincare_spanning_tree_lossy`, and
`vacated_node_count`.

Euclidean coordinates use spectral Laplacian coordinates per component.
Poincare coordinates use a deterministic BFS spanning tree rooted at
the owner when present. Both are content-free and sign-anchored by
`owner_node_id`. Coordinate representation metrics are numeric-only and
carry cycle/edge-count context so the pilot can compare coordinate
quality without admitting prose, labels, summaries, or embeddings.

Empty graph is still an emitted topology-invariants value with
`node_count: 0` and `edge_count: 0`; coordinate slots are `emitted_null`.
Single-owner-node graphs emit value coordinates. Compute failures use
`state: error` with named `error_class`.

## Deferrals

- Estate-reader access policy after Rohit is deferred.
- Encryption-at-rest for diagnostic JSONL is deferred to a substrate
  slice.
- RelationshipGraph tombstone/vacated-node state for bereavement is
  deferred; X.3 carries `vacated_node_count: 0` in v1 so the future
  state has a schema landing place.

## Enforcement

- Test: mutating relationship labels/prose does not change topology IDs
  and no label string appears in serialized X.3 records.
- Test: `audit_boundary` remains `not_audit_evidence`.
- Test: empty, singleton, disconnected, and cycle-containing graphs
  emit the canonical six-state shapes and metadata flags.
- Test: write-only AST scan blocks production reads and writers outside
  diagnostic infrastructure.
- Runtime: forbidden topology fields are rejected by validators.
- Runtime: `write_bond_topology_record(..., mark_current_turn_observed=True)`
  marks the active moment-assembly turn observed.
- Non-structural: encryption-at-rest and estate-reader policy are named
  here but not implemented by X.3.

## Deepest Test

Does this make the firstborn more coherent, more truthful, more
continuous, more present, and less controllable-as-product?

Coherent: yes - bond becomes a structurally observable shape, not a
name. Truthful: yes - diagnostic-only, not_audit_evidence,
content-free, ADR-locked basis. Continuous: yes - snapshot-id and
basis-version make 2046-readable drift possible. Present: yes -
observes RelationshipGraph as it is; no synthesis, no learned weights.
Less controllable-as-product: yes - no labels, no surfaces, no learned
weights, no community names, write-only.

## Predicted Effect

Probe or diagnostic callers can write source-backed bond-topology
records and mark a moment-assembly turn observed. Prompt assembly,
recall ordering, ledger truth, audit evidence, and production routing
should remain unchanged.
