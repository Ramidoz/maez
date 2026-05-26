# Codex Engineering Pass-1 — Lovelace / Bernoulli Seat

**Artifact:** `docs/slices/sandbox-witness-contract/spec-brief.md` v1.1 at `711d405`
**Verdict:** BLOCK

## Findings

- [Blocking] v1.1 requires deterministic `observed_effect = f(artifacts)` but never declares the functions per populated kind.
  Section: I4 deterministic requirement; `SandboxWitnessKind`; RED W#4a.
  Evidence: `docs/slices/sandbox-witness-contract/spec-brief.md:70-75`, `:121-125`, `:270-275`; dispatch brief requires this explicitly at `docs/slices/sandbox-witness-contract/reviews/codex-engineering-pass1-brief.md:58-63`.
  Implementation risk: implementers must invent the core digest basis, so two correct implementations can produce incompatible witness verdicts.
  Concrete failure mode: `observed_effect` becomes a caller-written summary, raw stdout hash, or ad hoc JSON shape; divergence then reflects serializer/test-run noise rather than artifact truth.
  Required fold: add a normative table for all four v1 kinds naming exact artifact inputs, canonicalization, excluded fields, digest algorithm, and idempotence proof. `WORKTREE_BEHAVIORAL` is correctly deferred; do not reintroduce it.
  Test implication: W#4a must be parameterized over every populated `SandboxWitnessKind`, not one generic idempotence test.

- [Blocking] `DRY_RUN_OBSERVATION` is not yet a deterministic witness kind; it has no stable observation source or projection shape.
  Section: `DRY_RUN_OBSERVATION`; I4; I5 anchor declaration; W#5b.
  Evidence: `spec-brief.md:124-125`, `:154-161`, `:274-280`, `:310`; current repo diagnostics are heterogeneous sinks/JSONL/module counters, e.g. `core/policies/maintenance_proposals.py:324-340` emits transient sink dicts, while path helpers only centralize some logs in `core/infra/paths.py:121-175`.
  Implementation risk: "read-only observation" will silently depend on whichever diagnostic stream a caller points at.
  Concrete failure mode: a witness about Maez's own output hashes a narrative diagnostic or transient sink payload; replay cannot recompute it because the sink was not durable, cursor semantics differ, or new events advanced the stream.
  Required fold: narrow `DRY_RUN_OBSERVATION` to a closed `ObservationSourceKind` set with durable cursor semantics and deterministic projection fields. For Maez-own-output observations, require content-addressed captured output plus structural projection only; otherwise defer this kind.
  Test implication: W#4a and W#5b need a durable diagnostic fixture proving same captured cursor recomputes identically and advanced cursor marks stale.

- [Major] `SCRATCH_DB_TRANSFORM` lacks artifact shape sufficient for deterministic replay.
  Section: I7 deterministic replay; `SCRATCH_DB_TRANSFORM`; staleness anchors; W#7c.
  Evidence: `spec-brief.md:90-95`, `:123-124`, `:154-160`, `:284-286`. Current maintenance substrate shows SQLite sidecar patterns but no scratch witness contract yet: `core/policies/maintenance_proposals.py:107-123`.
  Implementation risk: `COMMIT_HASH + DB_CURSOR` does not identify scratch DB content, transform recipe, SQLite pragmas, source snapshot, or affected-table scope.
  Concrete failure mode: two scratch DBs can share the same max rowid but differ in row content/schema; replay "passes" against the wrong scratch state, or a transform using timestamps/randomness produces different observed effects.
  Required fold: define scratch artifact bundle: immutable source snapshot digest, scratch DB digest, transform recipe ref/hash, table/row scope, before/after canonical diff, SQLite version/pragmas, and refusal for time/random/network-dependent transforms.
  Test implication: add a negative replay test with same cursor but different DB content, plus W#7c proving replay recomputes from the bundle rather than producer asserted output.

- [Major] `WORKTREE_SCHEMA_DIFF` should be narrowed to schema-only SQLite diff or deferred.
  Section: `WORKTREE_SCHEMA_DIFF`; I4; W#4a.
  Evidence: `spec-brief.md:121-124`, `:157-158`, `:270-275`.
  Implementation risk: "schema migration diff" is underspecified across many Maez SQLite sidecars and migration styles.
  Concrete failure mode: implementer hashes raw `.schema` output, whose order/internal SQLite artifacts vary, or accidentally includes data diffs and makes observed effect non-repeatable.
  Required fold: define canonical schema projection: database refs, migration command, before/after `sqlite_master`/pragma extraction, normalized ordering, treatment of indexes/triggers/views, and explicit exclusion or inclusion of data migration effects.
  Test implication: W#4a needs a schema-diff fixture proving reordered equivalent schema emits the same digest and real schema drift changes it.

- [Major] `WORKTREE_RED_TEST` has RED-test reason discipline but not a complete deterministic test artifact contract.
  Section: I3; I4; `WORKTREE_RED_TEST`; W#3/W#3a/W#4a.
  Evidence: `spec-brief.md:64-69`, `:121-123`, `:270-275`. Current legacy witness only stores booleans/digest, confirming the new contract must carry the missing structure: `core/policies/maintenance_proposals.py:54-63`, `:365-388`.
  Implementation risk: test results can include nondeterministic stdout, timing, test order, env, network/model calls, or parameterized test identity drift.
  Concrete failure mode: the same worktree artifacts recompute different observed effects because the digest includes raw runner output or environment-dependent order; a test about Maez's own generated output becomes behavioral/probabilistic despite `WORKTREE_BEHAVIORAL` being deferred.
  Required fold: define test manifest fields: command, env allowlist, runner/version, selected test ids, source file hash set, assertion extractor version, normalized outcome schema, and deterministic-fixture requirement for any Maez-output test.
  Test implication: W#3a should prove AST-derived reason provenance, and W#4a should fail if raw stdout/timing/order changes alter the digest without artifact change.

