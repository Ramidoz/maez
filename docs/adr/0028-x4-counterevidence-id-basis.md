# ADR 0028: X.4 Counterevidence ID Basis

**Status:** Accepted  
**Date:** 2026-05-09

## Context

Slice X.4 records source-layer tension as diagnostic witness. The organ
must make contradiction structurally observable without turning it into
audit evidence, narration, confidence scoring, bond-shape density, or a
second source of truth.

## Decision

Counterevidence candidate handles use a content-free typed-handle hash
basis:

`COUNTEREVIDENCE_HASH_PREFIX = "x4.counterevidence.v1|side_a:<source_id_a>|side_b:<source_id_b>|tension_class:<class>"`

`COUNTEREVIDENCE_ID_BASIS_VERSION = 1`

Source ids must be typed as `source_type:id`; untyped ids are rejected.
The two sides are lexicographically ordered before hashing, so the same
tension observed in either order produces the same candidate id and
counts up instead of fragmenting.

The hash basis explicitly excludes prose, summaries, embeddings, UUID
allocation, autoincrement ids minted inside the diagnostic writer, side
labels, source text, quoted refusal text, hedge quotes, and narration.

`witness_only` is the only X.4 tension role. X.4 v1 accepts
`subject_class` values `self_state` and `world_state`; it rejects
`bond_shape`, `owner_personhood`, and `maez_personhood`. The risk-loaded
sub-organs remain reserved at `not_implemented` in v1.

Changing the hash basis, subject-class invariant, forbidden candidate
kinds, required `projection_model_id` handle, runtime read-path lock,
`witness_only` tension role, or lex-ordered idempotent hash basis
requires ADR because these are covenant properties, not implementation
details.

## Consequences

X.4 can index tension without narrating it or adjudicating it.
Dereferencing truth still goes back to typed source systems, never
through the diagnostic row. The attention-assembler hash-only read
interface is reserved for a future activation slice and is not active in
v1.
