# Codex Engineering Pass-1 — Peirce Seat

**Artifact:** `docs/slices/sandbox-witness-contract/spec-brief.md` v1.1 at `711d405`
**Verdict:** BLOCK

## Findings

- [Blocking] W#legacy does not close the existing legacy write boundaries
  Section: v1.1 "Legacy SandboxWitness migration", W#legacy
  Evidence: `spec-brief.md:190-199`, `spec-brief.md:291-295`; current write paths in `core/policies/maintenance_proposals.py:151-172`, `206-224`, `348-357`, `365-376`; current tests still construct and round-trip legacy `SandboxWitness` at `tests/test_maintenance_proposals.py:39-61`, `92-99`.
  Risk: The implementation can add a new honest attachment API while the old `MaintenanceProposal.sandbox_witness` / `sandbox_witness_json` path still accepts caller-supplied booleans.
  Concrete failure mode: A proposal is emitted or updated with `SandboxWitness(red_tests_passed=True, focused_tests_passed=True, ...)`; W#legacy passes against the new attachment API, but legacy booleans still persist through `append()` / `update()` and can be read as current witness authority.
  Required fold: Split W#legacy into explicit write-boundary tests: `append` refuses legacy witness with `LEGACY_WITNESS_SHAPE_REFUSED`; `update` refuses legacy witness writes; new attachment writes only to `memory/sandbox_witnesses.db`; old persisted rows deserialize only through a legacy-named read surface; static guard catches new writes to `sandbox_witness_json`.
  Test implication: The RED test must exercise the real write APIs, not only enum existence or a new happy-path attachment function.

- [Blocking] RED assertion-reason tests still allow "refusal vocabulary" instead of "refusal reason proved"
  Section: I3, W#3, W#3a
  Evidence: `spec-brief.md:64-69`, `266-274`.
  Risk: W#3/W#3a can be satisfied by checking that a digest exists or that a caller string is rejected, without proving the RED test asserts the specific refusal path it claims.
  Concrete failure mode: A test catches `WitnessRefused` or checks an enum value exists, but never asserts that the executed refusal was `RED_TEST_REASON_MISSING`; the original Peirce failure class recurs: test passes for the wrong reason.
  Required fold: Add an anchor that feeds a RED-test trace whose assertion AST inspects the wrong predicate, for example exception type only or the wrong refusal reason, and require attachment/re-verification to refuse that trace as reason-mismatched or reason-missing. The digest must be AST-extractor produced and bound to the actual refusal predicate.
  Test implication: The test must mutate the asserted refusal reason and fail for that mutation; otherwise it is still vocabulary coverage.

- [Major] `WitnessRefusalReason` lacks a mandatory refusal-path matrix
  Section: `WitnessRefusalReason`, RED-Test Anchors
  Evidence: `spec-brief.md:130-143`, `270-295`.
  Risk: The enum can be implemented and tested without every reason being emitted by a real boundary.
  Concrete failure mode: `CALLER_SUPPLIED_DIGEST`, `SELF_RATIFICATION_DETECTED`, or `WITNESS_KIND_NOT_YET_VOCABULARY` exist as enum members, but actual attach/reverify failures raise generic `ValueError`, parser errors, or diagnostics with no stable `WitnessRefusalReason`.
  Required fold: Add a table mapping each `WitnessRefusalReason` to exactly one exercised boundary: construction, attachment, re-verification, ratification-time recheck, or migration write-boundary. Mark W#4 divergence separately as non-refusal signal.
  Test implication: Each refusal reason gets a fixture that crosses the boundary and asserts `WitnessRefused.reason == <reason>`.

- [Major] W#10 can still collapse into enum/partition existence testing
  Section: `SandboxWitnessKind`, W#10
  Evidence: `spec-brief.md:112-128`, `154-161`, `270-292`.
  Risk: The partition may be correct on paper while individual populated kinds have no behavior handler, required anchors, producer match, or deterministic observed-effect function.
  Concrete failure mode: `DRY_RUN_OBSERVATION` exists in the enum and W#10 passes, but no verifier implements its `DIAGNOSTIC_CURSOR` behavior or observed-effect projection; the first real witness fails late or falls through to default handling.
  Required fold: W#10 should become table-driven behavioral coverage: for every populated `SandboxWitnessKind`, assert registered producer kind, required anchor set, deterministic observed-effect function, and verifier route; for every reserved cell, assert construction/attachment refuses through `WITNESS_KIND_NOT_YET_VOCABULARY`.
  Test implication: No W# anchor should pass by inspecting enum members alone.

- [Minor] W#5c tests mtime while the declared anchor is file hash
  Section: I5 / `StalenessAnchorKind`, W#5c
  Evidence: `spec-brief.md:78-83`, `147-160`, `278-281`.
  Risk: The test name pulls implementation toward mtime drift, but the contract declares `FILE_HASH_SET`.
  Concrete failure mode: A file content change with preserved mtime is not detected, or metadata-only mtime churn is treated as stale despite identical content.
  Required fold: Rename/restate W#5c as source file hash-set drift, with optional mtime only as cache invalidation, not authority.
  Test implication: The RED test should change file content and assert `WITNESS_STALE`; a metadata-only change should not be the load-bearing proof.

