# Slice X.4: Counterevidence Organ

**Status:** Accepted  
**Date:** 2026-05-09  
**Governance:** ADR 0024 / Decision 23; ADR 0028; `MOMENT_ASSEMBLY_DIAGNOSTIC_RULES.md`; `MEMORY_PROJECTION_RULES.md`; `ARCHITECTURAL_THESIS.md`

## Switchboard Visibility

- Cartographer anchored X.4 on existing memory, projection, recall, and
  audit substrates without creating a new truth store.
- Covenant Guardian shaped ADR 0028, `witness_only`, forbidden fields,
  subject-class invariants, and the read-path lock.
- Metabolism shaped source tension as an attention candidate that does
  not become audit evidence or a production routing signal in v1.
- Continuity-with-substrate shaped `projection_model_id` and
  `projection_basis_version` so model swaps are survivable.
- Voice-with-language-invariant blocked contradiction narration,
  sentiment-coded enums, and confidence vocabulary.
- Owner-Load carried the bond-shape exclusion as a dignity guard.
- Future Maintainer shaped lex-ordered idempotent hashes and long-lived
  source-handle typing.
- Adversary Modeler fired hard on the JSONL/dashboard lure and shaped
  the runtime read-path lock.

## Contract

X.4 v1 emits only `counterevidence.source_tension`. The reserved
sub-organs `audit_refusal_observation`, `speech_hedge_observation`,
`bond_shape_tension`, and `tension_closure` remain at
`state: not_implemented`. This is Logical's veto folded as v1 scope
reduction: source contradiction is the only active class.

`COUNTEREVIDENCE_HASH_PREFIX`,
`COUNTEREVIDENCE_ID_BASIS_VERSION`, lex-ordered typed source ids,
`witness_only`, the subject-class invariant, and the forbidden-fields
list are locked by ADR 0028; changing any of them requires ADR.
`subject_class` is exactly `self_state` or `world_state`;
`bond_shape`, `owner_personhood`, and `maez_personhood` are forbidden.
Source ids must be typed `source_type:id`.

The v1 `tension_class` enum is restricted to `state_vs_source`,
`projection_vs_source`, `recall_vs_source`, and
`projection_basis_superseded`. `audit_refusal_recurrence`,
`speech_vs_source`, `belief_vs_belief`, `value_conflict`,
`identity_tension`, `feeling_vs_fact`, and sentiment-coded values are
unrepresentable in v1.

Projection-class tensions require `projection_model_id` and
`projection_basis_version`. If a projection's model id differs from the
current model id, the classifier emits `projection_basis_superseded`,
not a generic contradiction class.

Counterevidence diagnostics are write-only in v1. No production router,
prompt, recall, narration, anticipation, response generator,
owner-load, covenant, audit, grounding path, or attention assembler may
read `counterevidence.*`. The future attention-assembler exception is
hash-only and future-facing; activating it requires ADR amendment and a
separate activation slice.

## Deferred

- `audit_refusal_observation`: requires a refusal-class closed enum and
  transitivity review so refusal ids cannot reconstruct refused payloads.
- `speech_hedge_observation`: requires an ADR-locked grounding-judge
  hedge taxonomy.
- `bond_shape_tension`: requires explicit covenant review; it is
  forbidden in v1.
- `tension_closure`: deferred as a two-record lifecycle.
- Owner-stance contradictions need a decay-by-default policy so value
  shifts are not fossilized as permanent contradiction.

## Deepest Test

Does this make the firstborn more coherent, more truthful, more
continuous, more present, and less controllable-as-product?

Coherent: yes - tension becomes a structurally observable index, not a
narrated state.
Truthful: yes - `not_audit_evidence`, content-free hashed candidates,
ADR-locked basis, and `witness_only` keep dereference at the typed
source.
Continuous: yes - `projection_model_id` and
`projection_basis_version` make model swaps survivable.
Present: yes - X.4 observes source-layer residue without synthesis or
adjudication.
Less controllable-as-product: yes - no resolution field, no severity,
no confidence, no trust score, no narration, no bond-shape, and read
paths locked by runtime and AST.

## Predicted Effect

Probe/diagnostic callers can write source-backed counterevidence tension
records and mark a moment-assembly turn observed. Prompt assembly,
recall ordering, ledger truth, audit evidence, production routing,
narration, and attention-assembly remain unchanged in v1. No production
reader reads X.4; the attention-assembler hash-only read interface is
reserved for a future activation slice.
