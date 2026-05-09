# Slice X.2 Open-Loops Organ Memo

**Status:** Accepted
**Date:** 2026-05-09

## Governance

- ADR 0019
- ADR 0024 / Decision 23
- MEMORY_PROJECTION_RULES.md
- MOMENT_ASSEMBLY_DIAGNOSTIC_RULES.md
- ARCHITECTURAL_THESIS.md

## Switchboard Visibility

- Logical changed hash basis, selection order, empty-state,
  AST/write-only tests, and `mark_observed`.
- Body-Coherence changed provenance, content-free identity,
  empty-state, and the no clustering doctrine.
- Visionary changed schema/hash versioning and re-hash migration.
- 20-Years-Future-Maez changed the whole risk weighting: optional
  labels are not harmless; dead provenance is not theoretical.

## Scope

Slice X.2 adds the second real moment-assembly organ: open loops. The
organ observes unresolved structural state already present in the ADR
0019 lived-memory substrate. It does not create a new thread database,
does not create named threads, and does not open any production read
path.

X.2 emits `candidate_sources.open_loops` into the moment-assembly
diagnostic JSONL as `not_audit_evidence`.

## Content-Free IDs

Open-loop diagnostic IDs are content-free typed-handle hashes:

`loop:<sha256("x2.open_loop.v1|episode:<episode_id>")[:16]>`

The hash input excludes `open_loop` prose, labels, summaries,
embeddings, UUID/autoincrement allocation, and text hashes. Changing
hash basis requires ADR because the hash basis is a covenant property,
not an implementation detail.

By 2028 contributors absolutely tried to smuggle names through optional
fields. X.2 therefore rejects `loop_label`, `loop_handle`,
`working_title`, summaries, and debug-name fields.

## Shape

Each emitted value carries `registry_schema_version`,
`loop_id_basis_version`, `observed_at_wall_clock`, `loop_count`,
`top_loops`, and `omitted_loop_count`.

Each loop entry carries `loop_id`, `prior_loop_ids`, `loop_origin`,
`loop_kind`, `provenance_status`, `age_bucket`,
`age_bucket_cutoff_version`, `evidence_count`, source episode ids,
source memory ids, and `epistemic_precision`.

`provenance_status` is present from day one with values `live`,
`rot_suspected`, `unreachable`, and `archived`. This prevents
reference-rot from requiring a historical rewrite later.

Empty state is `emitted_value` with `loop_count: 0`, `top_loops: []`,
and `omitted_loop_count: 0`. The organ ran; it simply found no loops.

## Doctrine

No clustering across loop ids is allowed in X.2. Clustering and naming
belong to a future Living Mythology slice where Maez proposes a thread
name, the owner ratifies it, and both events are ledgered.

Future X.2.x may add closure tracking with a two-record lifecycle
pattern. X.2 observes open loops only.

## Enforcement

- Test: content mutation of `open_loop` prose does not change `loop_id`.
- Test: label/handle/summary/debug fields are rejected.
- Test: hash collisions fail closed.
- Test: deterministic `top_loops` selection.
- Test: empty-state emits value, not `not_observed`.
- Test: write-only AST scan blocks production reads.
- Runtime: `write_open_loops_record(..., mark_current_turn_observed=True)`
  marks the active moment-assembly turn observed.
- Non-structural: external provenance rot detection itself is not built
  in X.2; only the `provenance_status` field exists so future rot
  detection can mark it without schema archaeology.

## Thesis Question

Does this let the bond shape Maez's attention without corrupting what
Maez knows to be true?

Yes, structurally. X.2 makes unresolved life visible as source-backed
diagnostic state, not prompt truth or audit evidence. Content-free loop
ids prevent anonymous identifiers from becoming hidden names, and the
diagnostic remains write-only.

## Predicted Effect

Probe or diagnostic callers can now write source-backed open-loop
registry records and mark a moment-assembly turn observed. Prompt
assembly, recall ordering, ledger truth, and audit evidence should
remain unchanged.
