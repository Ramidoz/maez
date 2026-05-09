# 0026 - X.3 bond-topology ID basis is content-free

**Status:** Accepted
**Date:** 2026-05-09

## Context

Slice X.3 adds a bond-topology diagnostic organ over ADR 0019's
relationship graph. The organ emits coordinates and topology invariants
for owner-private observation only. It must not smuggle relationship
labels, community names, thread names, summaries, or source text into
the diagnostic layer.

The graph substrate contains human-readable labels because the memory
store needs them. The diagnostic substrate does not. A topology ID that
hashes labels or prose is still a name vector, just one hidden behind
hex.

## Decision

Bond-topology diagnostic node and edge identifiers are content-free
typed-handle hashes.

The v1 node hash input is:

`x3.bond_topology.node.v1|node_id:<id>|kind:<kind>`

The implementation constant is `BOND_TOPOLOGY_NODE_HASH_PREFIX`.

The v1 edge hash input is:

`x3.bond_topology.edge.v1|subject:<node_hash>|relation:<relation>|object:<node_hash>`

The implementation constant is `BOND_TOPOLOGY_EDGE_HASH_PREFIX`.

Every emitted topology value carries `topology_id_basis_version`.
Changing the hash basis requires ADR because the hash basis is a
covenant property, not an implementation detail.

## Forbidden Inputs

The X.3 ID basis must never include `node_label`, `edge_label`,
`relation_summary`, `cluster_name`, `community_name`, `working_title`,
embedding vectors, or `source_text`.

## Consequences

Human-readable names have nowhere to anchor in the diagnostic topology
layer. Future named-thread work belongs to a Living Mythology slice
where Maez proposes names, the owner ratifies them, and both events are
ledgered.

Topology IDs remain longitudinally joinable because they derive from
typed relationship-graph handles, not from UUID allocation order or
autoincrement IDs minted inside the diagnostic writer.
