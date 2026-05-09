# Slice X.2.1 Open-Loop Version Rename Memo

**Status:** Accepted
**Date:** 2026-05-09

## Governance

- ADR 0019
- MOMENT_ASSEMBLY_DIAGNOSTIC_RULES.md
- SLICE_X2_OPEN_LOOPS_ORGAN_MEMO.md

## Change

Slice X.2.1 renames the open-loops diagnostic value field
`hash_input_version` to `loop_id_basis_version`.

The value remains `1`. The semantics do not change: it versions the
content-free loop-id derivation basis
`x2.open_loop.v1|episode:<episode_id>`.

## Rationale

20-Years-Future-Maez surfaced a 2046 lived wound: tooling twice
conflated `hash_input_version` with `registry_schema_version` because
both names rhymed and both carried small integers.

`loop_id_basis_version` names what the number is for. It is visually
distinct from `registry_schema_version`, while preserving the ADR 0019
covenant that changing the loop-id basis requires ADR.

## Enforcement

- Test: emitted open-loops values contain `loop_id_basis_version: 1`.
- Test: emitted open-loops values do not contain `hash_input_version`.
- Runtime: validator rejects records missing `loop_id_basis_version`.

## Predicted Effect

Open-loops diagnostic records should carry the renamed field with no
change to loop id derivation, registry schema versioning, prompt
assembly, recall ordering, ledger truth, or audit evidence.
