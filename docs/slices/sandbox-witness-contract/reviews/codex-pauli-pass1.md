# Codex Engineering Pass-1 — Pauli Seat

**Artifact:** `docs/slices/sandbox-witness-contract/spec-brief.md` v1.1 at `711d405`
**Verdict:** BLOCK

## Findings

- [Blocking] Narrative/digest taint is not field-complete
  Section: I1 lines 54-56, I6 lines 84-88, Lifecycle lines 209-219, W#6/W#6a lines 282-283.
  Evidence: `core/policies/maintenance_proposals.py` currently has string fields with mixed authority classes: `proposal_id`, `bond_id`, `diagnosis_digest`, `proposed_patch_ref`, `predicted_effect`, `evidence_kind`, `ref_digest`; only digest-shaped fields are validated, while `proposed_patch_ref`, `predicted_effect`, and `evidence_kind` are only non-empty or unconstrained. v1.1 adds more strings: `isolation_ref`, `test_trace`, `scratch_state_refs`, `observed_effect`, anchor fingerprints, producer identity, and witness IDs, but never provides a field-by-field classifier.
  Implementation risk: implementers will scan "obvious narrative" and validate "obvious digest" while leaving refs, kind strings, paths, and effect text as ungoverned third surfaces.
  Concrete failure mode: an external-LLM-derived `proposed_patch_ref`, `isolation_ref`, `evidence_kind`, or test name can carry prompt-injection text or authority-spoofing text without hitting `scan()`, because it is treated as a ref/kind rather than narrative; conversely a digest-shaped-but-not-substrate-computed blob may pass `_is_digest` if it has the right prefix and 64 lowercase hex chars.
  Required fold: add a mandatory witness/proposal boundary table: every string field, category, validator, source of computation, and refusal reason. Categories must be exactly: substrate-computed digest, narrative scanned by `injection_patterns.scan`, closed vocabulary enum, canonical path/ref with resolver validation, or opaque ID with character/length schema and no authority semantics.
  Test implication: W#6 must become table-driven over every narrative field; W#6a must prove legitimate digests bypass scan but still require substrate computation/provenance, not just regex shape; add negative tests for injection in `proposed_patch_ref`, `isolation_ref`, `evidence_kind`, test names, and producer IDs.

- [Blocking] W#7 static-AST predicate is named but not specified enough to enforce alias/dynamic-import resistance
  Section: I7 lines 90-98; W#7a-W#7e lines 284-288.
  Evidence: v1.1 requires shared module export, shared helper, and dynamic import refusals, but does not define module identity canonicalization, import graph closure, alias resolution, or dynamic import policy. The repo already uses `sys.modules` shim aliases, e.g. `core/paths.py` delegates to `core.infra.paths` by assigning `sys.modules[__name__]`, and the tree contains `importlib.import_module`, `__import__`, `getattr`, and `sys.modules` mutation patterns.
  Implementation risk: a syntactic AST check over direct imports will look strong in tests while missing the repo's real alias surfaces.
  Concrete failure mode: `reverify_witness` avoids `from producer import observed_effect` but imports the same object through a shimmed module, `importlib.import_module("...")`, `getattr(module, name)`, or a shared helper that wraps producer-computed values. The verifier then consumes producer-asserted recomputable fields while W#7a passes.
  Required fold: define the enforcement model explicitly: canonical module identity by resolved file path plus `sys.modules` alias normalization; forbidden dependency edges between producer and verifier packages; dynamic import/reflection restrictions inside verifier code; and runtime provenance tags on recomputable values so W#7b catches semantic laundering even when AST is inconclusive.
  Test implication: W#7d/W#7e need concrete fixtures for shim alias, `importlib.import_module`, `__import__`, `getattr`, and shared-helper laundering, and must assert `SELF_RATIFICATION_DETECTED` through the attachment/reverification path.

- [Major] `SubstrateLocus`/`MAEZ_SUBSTRATE_ROOT` does not bind to existing path resolution
  Section: I8 lines 100-106; `SubstrateLocus` lines 179-186; W#8/W#8a lines 289-290.
  Evidence: `core/infra/paths.py` currently resolves storage via `MAEZ_HOME`, `MAEZ_DATA`, and path helpers such as `maintenance_proposals_db()` returning `memory/maintenance_proposals.db`; no `MAEZ_SUBSTRATE_ROOT` hook exists there. Repo search also shows hardcoded or independent DB defaults such as `memory/audit_log.db`, `memory/ledger.db`, and direct `sqlite3.connect(...)` call sites.
  Implementation risk: process isolation becomes environmental theater unless every live substrate handle is forced through a locus-aware factory.
  Concrete failure mode: the verifier subprocess has `MAEZ_SUBSTRATE_ROOT=/tmp/...`, but a module imports `core.paths.memory_dir()` or a hardcoded `REPO / "memory" / "...db"` path and opens the live DB anyway. W#8 only catches code that voluntarily uses the new `SubstrateLocus` registry.
  Required fold: state that all witness-reverification DB/file access must go through a single locus-aware handle factory, and that implementation must either retrofit or explicitly block known bypasses: `core.paths`, module-level DB defaults, direct `sqlite3.connect`, hardcoded `memory/*.db`, and env-specific DB overrides.
  Test implication: W#8 must include bypass fixtures for `core.paths.memory_dir()`, direct `sqlite3.connect(live_path)`, hardcoded `memory/foo.db`, symlinked scratch-to-live paths, and module-level singleton/import-time path capture.

- [Major] Legacy write-boundary refusal is under-specified for the existing update path
  Section: Legacy migration lines 190-199; Lifecycle lines 216-219; W#legacy line 294.
  Evidence: current `MaintenanceProposals.append()` and `update()` serialize `proposal.sandbox_witness` directly into `sandbox_witness_json`; `ratify_maintenance_proposal()` updates the full proposal and writes `_sandbox_to_json(proposal.sandbox_witness)`. v1.1 says new writes use `memory/sandbox_witnesses.db`, but does not require a static guard over the existing append/update SQL paths.
  Implementation risk: the new attachment API may refuse legacy witnesses while old `append()`/`update()` still writes `sandbox_witness_json`.
  Concrete failure mode: caller constructs a legacy `MaintenanceProposal(sandbox_witness=SandboxWitness(...))`, calls `emit_maintenance_proposal()` or `MaintenanceProposals.update()`, and persists caller-asserted booleans without passing through new attachment refusal.
  Required fold: require write-boundary refusal on every old entry point, not only the new attachment path: construction/append/update/ratify must reject non-`None` legacy `sandbox_witness` for new writes, while read-back exposes old rows only as `legacy_sandbox_witness_json`.
  Test implication: W#legacy must cover `emit_maintenance_proposal`, direct `MaintenanceProposals.append`, direct `update`, and ratification of a row containing legacy JSON; add a static guard test that no production SQL writes `sandbox_witness_json` except migration/read-compat code.

- [Minor] Deterministic `observed_effect = f(artifacts)` is required but not enumerated per populated kind
  Section: I4 lines 70-76; `SandboxWitnessKind` lines 112-128; Open Q8 lines 303-310.
  Evidence: v1.1 says every kind must declare its function, but the populated kind list only names evidence classes. It does not define the actual function for `WORKTREE_RED_TEST`, `WORKTREE_SCHEMA_DIFF`, `SCRATCH_DB_TRANSFORM`, or `DRY_RUN_OBSERVATION`.
  Implementation risk: implementers may encode ad hoc observed-effect summaries or test output text, recreating caller-supplied authority under a computed-looking digest.
  Concrete failure mode: two verifier runs over unchanged artifacts produce different observed digests because stdout ordering, timestamps, temp paths, SQLite row ordering, or diagnostic text leaked into the projection.
  Required fold: add per-kind deterministic projection specs: input artifact set, normalization rules, excluded nondeterministic fields, ordering, digest algorithm, and idempotence expectation.
  Test implication: W#4a must be per-kind and include nondeterminism traps: timestamp in stdout, unordered file lists, SQLite row order, temp directory paths, and diagnostic event ordering.

