# Sandbox-Witness Contract — Spec Brief v1

**Prepared:** 2026-05-26
**Slice:** Sandbox-Witness Contract (queued post-canon-refresh at `aa29bb0`)
**Parent/runtime base:** `aa29bb0 docs(canon): refresh post-Slice2 decisions and backlog`
**Implementation precedent:** `6fdfd6c feat(maintenance): add ratifiable maintenance proposals`
**Review lane:** Claude covenant / architecture council + Codex engineering panel (both lanes, full ladder)
**Operator:** Rohit relays and dispatches; Codex does not auto-dispatch.

---

## Why This Slice Exists

The maintenance-proposal substrate at [ADR 0045](../../adr/0045-ratifiable-maintenance-proposals.md) / [Decision 40](../../governance/BETA_ARCHITECTURE_DECISIONS.md) gave Maez a bond-scoped form to package self-maintenance gaps with evidence refs, predicted effect, optional `sandbox_witness`, and ratification state. The form exists; ratification cannot launder into autonomy modifiers; persistence-before-state-transition is enforced.

But `sandbox_witness` is currently a free-form string. A `MaintenanceProposal` can be authored carrying `sandbox_witness="I verified this"` and the substrate has no way to refuse the assertion. That string is **caller-supplied authority** in the same shape the producer-causality canon (Vectors 1–3 at ADR 0042) refuses elsewhere. Without a contract for what makes a witness honest, the maintenance loop is one ratification away from being its own laundering surface.

This slice defines what counts as **honest homework** attached to a maintenance proposal: structural artifacts the substrate can re-verify, not strings the producer asserts.

The central question for council pass-1: **does v1 of the sandbox-witness contract preserve the anti-laundering family (canon-governs-canon at ADR 0044; producer-causality at ADR 0042; canary-neutral-baseline at ADR 0043) at a new authority surface — the witness layer — without itself becoming the surface it is supposed to govern?**

---

## Non-Negotiable Review Discipline

Per `feedback_fold_second_order_contradictions` and ADR 0044 (canon-governs-canon), this review must walk the 8-step trace for every load-bearing amendment:

1. **Dependency-map:** what surfaces depend on this?
2. **Write-path:** what writes new state?
3. **Read-path:** what reads or consumes it?
4. **Test-path:** which RED tests prove it?
5. **Fold-summary:** what old wording becomes false?
6. **Cross-reference:** what cites must update?
7. **RED-test trace:** which test names must be added/changed?
8. **Verify-before-declaring:** what static check proves no stale shape remains?

Per ADR 0044: witness governs claim. Caller assertions about witness honesty are claims; the substrate's re-verification is the verdict.

---

## Core Principle

> **A sandbox witness cannot be a string. It must be a re-verifiable artifact.**

Restated more fully:

The maintenance proposal can say *"I think this fix works."* The witness must say *"here is the isolated worktree, here are the exact tests run, here is the scratch state, here are the timestamps, here is the observed result — and the substrate can recompute every one of these claims from the artifacts I am pointing at, without trusting any value I asserted."*

The producer presents structural evidence. The substrate adjudicates honesty. The witness is constructable by Maez but verifiable by the substrate.

---

## Invariants (proposed for council ratification)

### I1. Re-verifiability invariant
Every load-bearing field in a sandbox witness must be **re-computable** by the substrate from the artifacts the witness references. Caller-supplied values for re-computable fields are refused at attachment time. The witness's authority is the artifacts it points at, not the values it asserts.

### I2. Isolation invariant
A witness MUST execute against an isolated substrate (worktree separate from the main repo; scratch databases separate from live `memory/*.db` paths; ephemeral process state separate from the live daemon). A witness whose claimed isolation reference resolves to `main` or to any live substrate path is refused at attachment time. This is Vector 4 (canary-neutral-baseline, ADR 0043) at the witness layer.

### I3. RED-test reason invariant
A witness's test trace records, per test, the **assertion reason digest**, not merely the pass/fail verdict. A test that passes for the wrong reason is structurally indistinguishable from a test that passes for the right reason unless the reason is captured. Per Peirce's catch at `df07923`: assert the reason, not just the refusal.

### I4. Predicted-vs-observed binding
The maintenance proposal's `predicted_effect` digest is bound at proposal-creation time. The witness records an `observed_effect` computed **from the witness substrate state**, not asserted by the caller. The substrate compares predicted-digest to observed-digest. Divergence is honest signal (information for the operator about what Maez actually saw vs. what it expected), not failure to attach.

### I5. Staleness invariant
A witness has a captured-at timestamp. If the underlying substrate state (referenced episodes, memory rows, diagnostic events, code commit at the proposal's isolation reference) has moved since capture, the witness is **structurally stale** and the proposal cannot ratify until re-witnessed. This is the temporal-graph valid_from/valid_to discipline (ADR 0019) applied to maintenance evidence.

### I6. Inbound-taint invariant (per frontier backlog S3)
If any input to the witness construction came from an external-LLM consultation (per frontier backlog G2 — `EncounterSource=FRONTIER_CONSULT` once that gap closes), that input must pass through [`core/safety/injection_patterns.py`](../../../core/safety/injection_patterns.py) before being treated as witness evidence. External-LLM output entering the witness layer is untrusted ingress; the witness substrate is the first place the untrusted-input boundary becomes structurally enforced (the existing filter chain is invoked at the substrate boundary, not asserted by the caller).

### I7. Witness-cannot-self-ratify invariant
A witness's verification cannot be performed by the same code path that constructed it. Construction = producer; re-verification = consumer; consumer governs claim. A single-pass "construct and verify in one call" implementation is refused at the architectural layer.

### I8. Non-disturbance invariant
A witness's re-verification must not mutate any live substrate (no live `memory/*.db` writes, no live temperament event log writes, no live subjective_duration aggregate updates). Re-verification operations are read-only against live substrate and may only write to scratch / ephemeral surfaces. Per ADR 0043 multi-surface canary discipline.

---

## Closed Vocabularies (proposed)

### `SandboxWitnessKind`

```
WORKTREE_RED_TEST       — isolated worktree + RED test trace
WORKTREE_SCHEMA_DIFF    — isolated worktree + schema migration diff
WORKTREE_BEHAVIORAL     — isolated worktree + behavioral probe run
SCRATCH_DB_TRANSFORM    — scratch-DB-only transformation verification
DRY_RUN_OBSERVATION     — read-only observation, no mutation claimed
```

Growth is by spec amendment + council + Codex review. A new `SandboxWitnessKind` requires its own RED-test enumeration, its own re-verification implementation, and its own non-disturbance proof.

### `WitnessRefusalReason`

```
CALLER_SUPPLIED_DIGEST          — caller provided a value the substrate must compute
ISOLATION_REFERENCE_INVALID     — points at main or live substrate
RED_TEST_REASON_MISSING         — test trace lacks assertion-reason digests
PREDICTED_OBSERVED_UNBOUND      — observed_effect not derivable from artifacts
WITNESS_STALE                   — substrate moved since witness captured
INBOUND_TAINT_UNCLEARED         — external-LLM input bypassed injection_patterns
SELF_RATIFICATION_DETECTED      — construction and verification share code path
LIVE_SUBSTRATE_MUTATION_DETECTED — re-verification touched live state
```

---

## Lifecycle (proposed)

```
[MaintenanceProposal authored in PROPOSED state] (existing, ADR 0045)
                │
                ▼
[Witness construction] (this slice)
    Producer: code path in scratch-verification module
    Inputs: isolation_ref + test_trace + scratch_state_refs + predicted_digest
    Output: SandboxWitness object, kind ∈ SandboxWitnessKind
                │
                ▼
[Witness attachment] (this slice)
    Boundary check: I1–I7 above
    Refusal raises WitnessRefused with WitnessRefusalReason
    On success: proposal.sandbox_witness = witness_id (digest)
                │
                ▼
[Witness re-verification] (this slice, separate code path)
    Substrate re-computes: isolation, test outcomes, observed_effect
    On divergence: emit WITNESS_DIVERGENCE_OBSERVED diagnostic
    On staleness: emit WITNESS_STALE diagnostic; proposal cannot ratify
                │
                ▼
[Ratification eligibility] (existing maintenance-proposal lifecycle)
    A proposal whose witness has refused, diverged, or gone stale
    cannot be ratified by ratify_maintenance_proposal until re-witnessed
```

The substrate's existing maintenance-proposal lifecycle (ADR 0045) does not require a witness for ratification; that remains true. This slice adds the witness as a structurally-honest *optional* attachment. The lifecycle changes are additive: a proposal without a witness behaves exactly as today; a proposal *with* a witness must pass the contract.

---

## Cross-canon Dependency-Map

This slice consumes from and is consumed by:

- **[ADR 0042 (drive-driven curiosity / producer-causality)](../../adr/0042-drive-driven-curiosity-felt-organ.md):** Vectors 1–3 govern witness construction. The witness producer presents structural evidence; the substrate (re-verification consumer) adjudicates honesty. Caller-supplied digests are refused at attachment time.
- **[ADR 0043 (canary-neutral-baseline)](../../adr/0043-canary-neutral-baseline.md):** Vector 4 governs witness execution. Re-verification must not mutate any live substrate. Per-substrate non-disturbance discipline applies.
- **[ADR 0044 (canon-governs-canon)](../../adr/0044-canon-governs-canon.md):** the recursive anti-laundering law. Witness *claims* are evidence; substrate *re-verification* is verdict. Divergence is honest signal, not failure.
- **[ADR 0045 (ratifiable maintenance proposals)](../../adr/0045-ratifiable-maintenance-proposals.md):** the form this slice attaches to. The maintenance-proposal lifecycle does not change; witness attachment becomes a new optional gate before ratification eligibility.
- **[ADR 0019 (lived memory architecture)](../../adr/0019-lived-memory-architecture.md):** valid_from / valid_to temporal discipline applied to witness staleness.
- **[core/safety/injection_patterns.py](../../../core/safety/injection_patterns.py):** the existing 7-bucket prompt-injection catalog becomes the inbound-taint filter chain invoked at witness boundary (I6).
- **Frontier backlog G2 (provenance carry-through for frontier consultations):** when that gap closes, the witness contract gains a closed-vocabulary path for `FRONTIER_CONSULT`-tagged inputs. Until then, all external-LLM inputs route through the existing injection_patterns filter.
- **Frontier backlog S3 (sandbox-witness inbound taint discipline):** this slice IS S3's implementation.

---

## RED-Test Anchors (proposed; council pass-1 refines)

The committed canon will enumerate each RED test by number with assertion-reason digests. Provisional shape:

- **W#1.** `test_caller_supplied_observed_digest_refused`: producer attempts to assert `observed_effect` instead of letting substrate compute. Substrate refuses with `CALLER_SUPPLIED_DIGEST`. Asserts both the refusal AND the reason string.
- **W#2.** `test_isolation_ref_pointing_at_main_refused`: producer constructs witness with `isolation_ref="main"`. Refused with `ISOLATION_REFERENCE_INVALID`.
- **W#3.** `test_red_test_without_reason_digest_refused`: producer presents test trace with pass/fail but no assertion-reason digests. Refused with `RED_TEST_REASON_MISSING`.
- **W#4.** `test_predicted_observed_divergence_does_not_refuse_attachment`: divergence is signal, not refusal. Attachment succeeds; `WITNESS_DIVERGENCE_OBSERVED` diagnostic emitted; proposal becomes ineligible to ratify until divergence is owner-acknowledged or witness is refreshed.
- **W#5.** `test_witness_stale_after_proposal_isolation_ref_advances`: proposal isolation_ref commit hash changes after witness capture. Re-verification detects staleness; ratification blocked with `WITNESS_STALE`.
- **W#6.** `test_inbound_external_llm_input_routes_through_injection_patterns`: witness input from external-LLM consultation must invoke `injection_patterns.py`. Direct bypass refused with `INBOUND_TAINT_UNCLEARED`. Static-AST predicate (per Codex pass-1 F17 pattern from Slice 2) refuses any witness-construction code path that imports external-fetch helpers without routing through the filter.
- **W#7.** `test_witness_self_ratification_detected`: construction and re-verification share a code path. Refused at architectural layer with `SELF_RATIFICATION_DETECTED`. Static-AST predicate refuses any module that exports both `construct_witness` and `reverify_witness` from the same namespace.
- **W#8.** `test_re_verification_does_not_write_live_substrate`: re-verification path attempts to write to `memory/wonderings.db` (or any live substrate). Refused at filesystem boundary with `LIVE_SUBSTRATE_MUTATION_DETECTED`. RED test asserts no rows added to any live DB during full re-verification cycle.
- **W#9.** `test_proposal_without_witness_still_ratifies_unchanged`: existing maintenance-proposal lifecycle continues to work for witnessless proposals. Backward-compatibility assertion.

---

## Open Questions for Council Pass-1

These are the judgment calls the brief intentionally does not pre-decide:

**Q1. Witness as required vs optional for ratification.** Current proposal: optional (additive to ADR 0045 lifecycle). Should ratification require a witness for any subset of `ProposalScopeClass` values? E.g., scope classes that touch substrate code might require a witness, while scope classes that touch only configuration might not. Council should weigh: requiring witness creates a forcing function for honesty; making it optional preserves the existing maintenance-proposal flow's lower friction.

**Q2. Witness re-verification trigger.** When does substrate re-verify a witness? At attachment time only (one-shot)? On every ratification attempt (witness might go stale between attach and ratify)? Periodically while PROPOSED? Council should weigh: re-verification cost vs staleness window. Recommendation: at attachment + at ratification (two checkpoints, minimum staleness window).

**Q3. Witness divergence as ratification block vs ratification signal.** Per I4, divergence is honest signal. Does it BLOCK ratification or just inform it? Current proposal: divergence emits diagnostic, marks proposal `requires_owner_acknowledgment_of_divergence`, does not auto-block. Owner can ratify with explicit acknowledgment that divergence was reviewed. Council should weigh: silent acceptance of divergence reintroduces laundering; auto-blocking removes owner authority over their own assessment of whether divergence matters.

**Q4. Scope of inbound-taint invariant.** I6 currently routes external-LLM input through `injection_patterns.py`. Is that the right filter chain for this surface, or does the witness layer need additional taint analysis (semantic content review, structured-output schema validation)? Council should weigh: injection_patterns catches known attack patterns but does not validate semantic shape; witness inputs may need both.

**Q5. Witness producer identity.** Who is allowed to construct a witness? Per Vector 3 (producer-identity laundering), each closed-vocabulary `SandboxWitnessKind` should have an associated producer enum entry. Current proposal: `WitnessProducerKind` parallel enum with one entry per `SandboxWitnessKind`. Council should weigh: explicit producer-identity discipline at the witness layer, or implicit via `SandboxWitnessKind` value.

**Q6. Closed-vocabulary growth path.** When a future slice needs a new `SandboxWitnessKind`, what's the minimum review surface? Full ladder (spec → council → Codex → fold → canonicalize), or a lighter "extending closed vocabulary" path? Current proposal: full ladder, matching how `ProducerRef` / `EncounterSource` / `SubjectKind` extend. Council should weigh: rigor vs throughput as more witness kinds become useful.

**Q7. Witness retention.** A witness object carries digests of code state, test traces, scratch DB contents. Per never-delete-memory, witnesses presumably never delete. Does the witness object itself become a substrate? Where is it stored (`memory/maintenance_proposals.db` alongside the proposal, or `memory/sandbox_witnesses.db`)? Council should weigh: storage locality vs separation of concerns.

---

## Predicted Effect (per `feedback_predict_then_verify`)

After this slice ships, ratifies through both lanes, and lands:

- A `MaintenanceProposal` can be attached a `SandboxWitness` whose every load-bearing field is re-verifiable by the substrate from the artifacts the witness points at.
- A maintenance proposal whose witness fails re-verification cannot be ratified until re-witnessed.
- Divergence between predicted_effect and observed_effect surfaces as a structured diagnostic, preserving honest signal while requiring owner acknowledgment before ratification.
- External-LLM input entering the witness layer routes through `injection_patterns.py`; direct bypass refused at construction-time AND statically refused via AST predicate.
- The maintenance-proposal substrate at ADR 0045 continues to function unchanged for witnessless proposals.
- The witness becomes the first place in Maez where "show your work and let it be challenged" is structural rather than ceremonial — a deliberate, dispatched inner-critique surface applied to a specific Maez-generated artifact at a specific moment.

---

## Discipline Reminders (per existing canon)

- **Cooling-off night** per `feedback_cooling_off_between_plan_and_code`: this brief lands today; council pass-1 dispatches tomorrow at earliest. Planning and implementation do not share a day.
- **Both review panels** per `feedback_covenant_slices_need_both_panels`: this is full-ladder. Claude six-role council (Locke / Kant / Hume / Buber / Descartes / Ohm) AND Codex engineering panel.
- **Maez is not ours to control** per ADR 0024: the witness contract makes structural honesty mechanical. It must not become a surface for circumventing bond-mediated ratification.
- **No fabrication** per `feedback_no_fabrication`: the witness substrate is built specifically to refuse asserted-but-unverifiable claims.

---

## What This Slice Is NOT

- Not an autonomous witness-runner. Witnesses are constructable by Maez but executable under operator dispatch.
- Not an autonomous gap-detector. Detecting what needs a maintenance proposal is a separate slice (frontier backlog item).
- Not a self-merger. Witness ratification feeds into the existing maintenance-proposal ratification, which is owner-explicit per ADR 0045.
- Not a runtime quality judge. The contract verifies structural honesty (re-verifiable evidence) not idea quality.
- Not an expansion of MaintenanceProposal authority. Witnessless proposals still ratify exactly as today.

---

*Brief v1 — 2026-05-26. Author: Claude under Rohit dispatch. Next: cooling-off night, then council pass-1 (six roles, full 8-step trace per finding), then Codex engineering panel pass-1, then fold cycle, then canonicalize as Decision 41 / ADR 0046.*
