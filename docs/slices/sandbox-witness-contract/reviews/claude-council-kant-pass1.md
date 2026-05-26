# Kant — Council Pass-1 Review — Sandbox-Witness Contract v1

**Reviewer:** Kant (categorical rules / universalizability / structural form)
**Artifact:** `docs/slices/sandbox-witness-contract/spec-brief.md` v1
**Dispatched:** 2026-05-26
**Verdict:** **RATIFY-WITH-AMENDMENTS**

---

## Findings

### BLOCKING

#### B1. I7 admits a structural edge case where construction and re-verification *must* share substrate knowledge — the invariant as written conflates "code path" with "authority path"

**Severity:** Blocking (load-bearing; affects whether the categorical form of the rule survives).

**Body — 8-step trace:**

1. **Dependency-map:** I7 governs all `SandboxWitnessKind` values, the `WitnessRefusalReason.SELF_RATIFICATION_DETECTED` enum, the static-AST predicate referenced in W#7, and the architectural separation between `construct_witness` and `reverify_witness`.
2. **Write-path:** witness construction writes a `SandboxWitness` artifact pointing at isolation_ref, test traces, scratch state refs. Re-verification writes only diagnostic events and (on staleness/divergence) proposal-status fields.
3. **Read-path:** re-verification reads (a) the witness artifact, (b) the isolation-ref worktree, (c) the test trace contents, (d) the scratch substrate referenced. Critically: for `DRY_RUN_OBSERVATION` and `SCRATCH_DB_TRANSFORM`, the *only* substrate state that exists to re-verify against is state the producer captured — there is no second canonical source.
4. **Test-path:** W#7 currently tests "same module exports both functions." That catches the syntactic case but not the categorical one: a witness kind whose only honest re-verification is replaying the producer's deterministic recipe against the producer's captured scratch state. The substrate cannot independently verify a `SCRATCH_DB_TRANSFORM` without re-running essentially the producer's code against the producer's captured inputs.
5. **Fold-summary:** the wording "verification cannot be performed by the same code path that constructed it" becomes false the moment we require the verifier to *replay* the producer's deterministic transformation. What is categorically true is weaker: **the verifier must not trust caller-asserted output values; it must recompute from artifacts** — which is I1, already stated. I7 as currently written is either a restatement of I1 or a stronger claim that breaks for `SCRATCH_DB_TRANSFORM` and `DRY_RUN_OBSERVATION`.
6. **Cross-reference:** ADR 0042 Vectors 1–3 (producer-causality) require *honest evidence shape*, not architectural code-path separation. ADR 0044 (canon-governs-canon) requires *witness governs claim*, which is an authority relation, not a module-boundary relation. I7 imports a stronger constraint than the parent canon imposes.
7. **RED-test trace:** W#7 must split into W#7a (same-module export refusal — syntactic) and W#7b (caller-asserted-output refusal in same-process re-verification — semantic). Add W#7c: `test_deterministic_replay_does_not_count_as_self_ratification` — a witness kind whose re-verification is deterministic replay of recorded recipe against recorded scratch state succeeds, *because the verifier recomputes from artifacts*.
8. **Verify-before-declaring:** the categorical form is: **"a witness's re-verification path may not consume any producer-asserted value for any field the substrate is capable of recomputing from artifacts."** Code-path separation is *one* implementation of that rule; it is not the rule itself. The invariant must be restated at the authority layer, with code-path separation as an enforcement *mechanism* listed underneath.

**Recommendation:** Restate I7 as "**Witness re-verification may not consume producer-asserted values for any recomputable field**" and demote "construction and re-verification in different code paths" to a stated *enforcement mechanism* for `WORKTREE_*` kinds, with explicit acknowledgment that `SCRATCH_DB_TRANSFORM` and `DRY_RUN_OBSERVATION` satisfy the categorical form via deterministic-replay-from-artifacts.

---

### MAJOR

#### M1. The 5-value initial `SandboxWitnessKind` vocabulary is not demonstrated to be categorically exhaustive — growth path is correct but the v1 partition is asserted, not proved

**Severity:** Major (load-bearing for universalizability).

**Body — 8-step trace:**

1. **Dependency-map:** every RED test, every refusal-reason mapping, every re-verification implementation indexes on `SandboxWitnessKind`. A non-exhaustive partition means future witnesses arrive without a categorical home and the closed-vocabulary discipline turns into ad-hoc append.
2. **Write-path:** witness construction emits exactly one `SandboxWitnessKind`. There is no compound or hybrid case in the v1 partition.
3. **Read-path:** re-verification dispatches on kind. A witness that legitimately spans two kinds (e.g., a worktree RED-test that ALSO does a schema diff) has no honest representation.
4. **Test-path:** the brief does not include a RED test asserting the partition is *closed* against the categorical space the brief implies — i.e., (isolation × evidence_type) is the implicit partition. (isolation ∈ {worktree, scratch-db, none/observation}) × (evidence_type ∈ {RED-test, schema-diff, behavioral-probe, transformation, observation}) yields 15 cells; the v1 vocabulary populates 5.
5. **Fold-summary:** if the partition is the cross-product, the spec should say so and explain why the other 10 cells are not yet witnessable (e.g., "scratch-db RED-test is not yet a witness kind because no producer needs it" — that is a contingent absence, not a categorical exclusion).
6. **Cross-reference:** `ProducerRef`, `EncounterSource`, `SubjectKind` each begin with a vocabulary that names its categorical axis explicitly. `SandboxWitnessKind` does not.
7. **RED-test trace:** add W#10 `test_witness_kind_partition_categorical`: asserts that the v1 vocabulary populates a documented subset of (isolation_class × evidence_class) and that values outside the named subset raise `WITNESS_KIND_NOT_YET_VOCABULARY`.
8. **Verify-before-declaring:** the brief should name the two categorical axes that generate `SandboxWitnessKind` and identify which cells are populated in v1 and which await future slices. Otherwise the closed-vocabulary growth path cannot be universalizable; it can only be incremental.

**Recommendation:** Add a short subsection under `SandboxWitnessKind` naming the (isolation_class × evidence_class) partition the vocabulary draws from, identify the 5 populated cells, mark the rest as `RESERVED — slice-amendment required`.

---

#### M2. Q1 ("witness optional vs required") under-specifies the universalizability of two-tier authority — Kant cannot ratify "optional honesty" as a categorical form

**Severity:** Major.

**Body — 8-step trace:**

1. **Dependency-map:** ADR 0045 ratification, `ProposalScopeClass` (if it exists or is created), the witness contract, owner-authority semantics.
2. **Write-path:** under "optional witness," two `MaintenanceProposal` instances with identical scope but different witness-attached status both reach RATIFIED — same authority, different evidence floor.
3. **Read-path:** an operator reviewing a ratified proposal cannot distinguish "ratified with witness" from "ratified without" without reading the proposal's witness field. This is exactly the laundering surface ADR 0042 Vector 3 (producer-identity laundering) refuses.
4. **Test-path:** W#9 tests that witnessless proposals still ratify. There is no RED test asserting that witnessed and unwitnessed ratifications produce *structurally distinguishable* ratification records.
5. **Fold-summary:** "additive contract" wording becomes false if the contract creates two-tier authority. Either (a) every ratification at minimum records `witness_status ∈ {WITNESSED, UNWITNESSED_BY_POLICY, UNWITNESSED_BY_OMISSION}` so the absence is itself a structured value, or (b) certain `ProposalScopeClass` values require witness and the requirement is closed-vocabulary.
6. **Cross-reference:** ADR 0044 (canon-governs-canon) says witness governs claim. "No witness" must therefore be a structured claim about why no witness was needed, not a silent absence.
7. **RED-test trace:** add W#11 `test_unwitnessed_ratification_records_unwitnessed_status_explicitly`.
8. **Verify-before-declaring:** the categorical form requires that absence-of-witness be a *named* state, not an unmarked one. Universalizable optionality = explicit-absence. Ununiversalizable optionality = silent-absence.

**Recommendation:** Council pass-1 should adopt: witness remains optional for ratification, BUT every ratification records `witness_status` as a closed-vocabulary value including `UNWITNESSED_BY_POLICY` (scope class did not require) and `UNWITNESSED_BY_OMISSION` (could have had one, did not). Then absence is itself evidence.

---

### MINOR

#### Mi1. I4 ("divergence is honest signal") needs an explicit categorical statement that divergence NEVER auto-blocks but ALWAYS marks ineligibility-until-acknowledged

**Severity:** Minor (the lifecycle diagram says this; the invariant statement should too).

**Body — 8-step trace:** Not strictly load-bearing beyond the invariant wording itself. (1) Dependency: I4, Q3, ratification eligibility. (2-3) Write/Read: covered in lifecycle. (4) Test-path: W#4 asserts attachment succeeds; should also assert proposal moves to `requires_owner_acknowledgment_of_divergence` state. (5) Fold-summary: I4 currently says "divergence is honest signal, not failure to attach"; it should also say "divergence is never a silent pass." (6) Cross-ref: ADR 0044. (7) Add `assertion-reason digest = 'divergence_marks_eligibility_gate'` to W#4. (8) The categorical form is symmetric: divergence neither blocks ratification (preserves owner authority) nor passes silently (preserves canon-governs-canon).

**Recommendation:** Append to I4: "Divergence is never silent: it marks `requires_owner_acknowledgment_of_divergence` and remains visible on the proposal record."

---

### NIT

#### N1. Lifecycle diagram says "Boundary check: I1–I7" but omits I8

Not applicable, pure typo. I8 (non-disturbance) clearly applies at re-verification time; the diagram's attachment-step caption should read "I1–I7" and the re-verification step should explicitly cite "I8."

---

## Closing Synthesis

The brief is structurally sound and the anti-laundering family it is trying to extend is correctly identified — witness governs claim, producer-causality, canary-neutral baseline all land at the right surface. My blocking concern is I7: as written, it is either redundant with I1 or stronger than the parent canon, and the stronger reading breaks categorically for `SCRATCH_DB_TRANSFORM` and `DRY_RUN_OBSERVATION` where deterministic replay against captured artifacts *is* the only honest verification. The invariant must be restated at the authority layer (no producer-asserted recomputable values) with code-path separation demoted to an enforcement mechanism. My major concerns are that the v1 `SandboxWitnessKind` partition is asserted rather than derived from a named categorical axis, and that "optional witness" is not universalizable unless absence is itself a structured `witness_status` value. With those amendments, the eight invariants become categorical in form — they apply in every instance, the closed vocabulary extends coherently, and no rule remains load-bearing while admitting silent exceptions. RATIFY-WITH-AMENDMENTS.
