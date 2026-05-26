# Hume — Council Pass-1 Review — Sandbox-Witness Contract v1

**Reviewer:** Hume (empirical scrutiny / inductive reasoning / cause-and-effect)
**Artifact:** `docs/slices/sandbox-witness-contract/spec-brief.md` v1
**Dispatched:** 2026-05-26
**Verdict:** **RATIFY-WITH-AMENDMENTS**

---

The brief is structurally honest about the producer/consumer split and the artifact-not-string principle. But several load-bearing claims — especially the mechanisms for re-verification, staleness, and predicted/observed binding — are asserted at a level of abstraction that the brief itself has not yet witnessed. The 5 precedent fixes are a small corpus, and the brief extrapolates from them to a general contract without naming which precedents exercised which invariants. The first witness round-trip has not yet run; the design is conjecture about what that round-trip will reveal. None of these are fatal; all are fixable by tightening empirical commitments before canonicalization.

---

## Blocking findings

### B1. I5 (staleness) has no specified computation mechanism

**Severity:** Blocking.

The brief asserts "if the underlying substrate state has moved since capture, the witness is structurally stale" — but stale *with respect to what*? Code commit hash? Yes, named. But "referenced episodes, memory rows, diagnostic events" are listed without saying what identity those rows are compared against. A `memory_row` has no monotonic version; an episode may be append-only but reference graph changes. Without a defined staleness predicate, I5 is a vibe.

**8-step trace:**

1. **Dependency-map:** I5 depends on per-substrate identity-of-state; touches `memory/*.db` rows, diagnostic event IDs, commit refs, and any aggregate the witness reads (subjective_duration, temperament).
2. **Write-path:** witness-capture records `staleness_fingerprint` per referenced substrate; today undefined.
3. **Read-path:** re-verification recomputes fingerprint per substrate and diffs.
4. **Test-path:** W#5 only covers commit-hash advance; does not cover memory-row append, diagnostic-event log growth, aggregate drift.
5. **Fold-summary:** the unqualified phrase "underlying substrate state has moved" must be replaced with an enumerated per-substrate staleness predicate.
6. **Cross-reference:** ADR 0019 valid_from/valid_to is cited but the brief does not show *which* valid_from on *which* substrate maps to *which* fingerprint.
7. **RED-test trace:** need W#5a (memory-row append since capture), W#5b (diagnostic event log advance), W#5c (aggregate drift).
8. **Verify-before-declaring:** static check that every `SandboxWitnessKind` declares its staleness fingerprint set.

### B2. I4 (predicted vs observed) does not name what makes `observed_effect` deterministic

**Severity:** Blocking.

"observed_effect computed from the witness substrate state" — by what function? For `WORKTREE_RED_TEST` it might be a digest of test-result tuples. For `WORKTREE_BEHAVIORAL` ("behavioral probe run") it almost certainly involves non-deterministic outputs (timing, scheduling, possibly LLM-judged behavior). If observed_effect is computed by a stochastic operation, then "the substrate compares predicted-digest to observed-digest" cannot be binding in the sense the brief implies — re-verification will produce a different digest on a second run even with no substrate movement, and divergence becomes noise.

**8-step trace:**

1. **Dependency-map:** every `SandboxWitnessKind` must declare the function `observed_effect = f(artifacts)` and prove `f` is deterministic on those artifacts.
2. **Write-path:** witness records both the function identity (digest of code path) and the observed value.
3. **Read-path:** re-verification re-runs `f` and compares.
4. **Test-path:** brief has no test that `f` is run twice and produces identical output; without that test, "re-verifiable" is unverified.
5. **Fold-summary:** the unqualified word "computed" must be replaced with "deterministically derived"; `WORKTREE_BEHAVIORAL` either needs a deterministic projection (e.g., a structural shape of probe output, not the output text) or must be deferred to a later slice.
6. **Cross-reference:** ADR 0042 producer-causality demands the substrate-computed verdict be reproducible.
7. **RED-test trace:** add W#4a `test_observed_effect_recomputation_is_idempotent_on_unchanged_artifacts`.
8. **Verify-before-declaring:** static enumeration that every kind has a named deterministic `observed_effect` function.

---

## Major findings

### M1. The 5-precedent corpus is invoked as stress-test ground truth but never mapped to invariants

**Severity:** Major.

The context names 5 precedent commits (5c6be72, 82ac7ec, 83e2729, 801833b, 79f78f1) as the retrospective stress-test corpus, but the brief never says *which precedent exercised which invariant*. Without that mapping, the claim "this contract is informed by the precedent corpus" is unwitnessed. The risk is exactly what Hume names: reasoning from a small observed set to a general contract without showing the inferential bridge.

**8-step trace:**

1. **Dependency-map:** every invariant I1–I8 must map to ≥1 precedent or be flagged "not witnessed in corpus, design-by-extrapolation."
2. **Write-path:** brief gains a corpus-coverage table.
3. **Read-path:** council reads the table during pass-1.
4. **Test-path:** RED tests W#1–W#9 should each cite the precedent shape they generalize from, OR mark themselves "synthetic, no precedent."
5. **Fold-summary:** the phrase "retrospective stress-test corpus" should not appear in canon unless a per-precedent mapping exists.
6. **Cross-reference:** the 5 commits get cited in the brief body, not just in the dispatch context.
7. **RED-test trace:** add corpus-mapping appendix.
8. **Verify-before-declaring:** invariants without corpus support are explicitly labeled, so council sees the inferential leap.

### M3. I6 (inbound-taint) assumes 7-bucket `injection_patterns.py` is sufficient at the witness layer without testing

**Severity:** Major.

Q4 acknowledges the gap honestly. But the brief still defaults to using the existing filter chain. The existing filter was built for a different boundary (LLM prompts entering the substrate generally), not for witness-shaped inputs (which may include structured test traces, scratch DB content, code diffs). Re-using the filter without a witness-input test pass is exactly the "borrow shapes, not the constraints those shapes were built to serve" pattern flagged in `project_external_borrow_rule`.

**8-step trace:**

1. **Dependency-map:** I6 binds witness ingestion to `injection_patterns.py`; if that filter's input distribution does not match witness inputs, the binding is shaped wrong.
2. **Write-path:** witness ingest invokes filter; on miss, false negative slips through silently.
3. **Read-path:** re-verification cannot detect a semantic-shape attack the filter wasn't built for.
4. **Test-path:** W#6 tests that the filter is *invoked*, not that it *catches witness-shaped attacks*. Coverage gap.
5. **Fold-summary:** brief must say "filter is invoked; sufficiency under witness-input distribution is an open question (Q4) and is canon-tagged as such."
6. **Cross-reference:** frontier backlog G2 cited; add explicit "until witness-input audit completes, treat I6 as necessary-but-not-proven-sufficient."
7. **RED-test trace:** add W#6a probing whether at least one witness-shaped attack pattern not in the 7 buckets exists; if yes, mark gap.
8. **Verify-before-declaring:** static check is insufficient; needs corpus-driven audit.

### M4. I3 (assertion-reason digest) does not say what a "reason" is

**Severity:** Major.

The Peirce-catch precedent at `df07923` is invoked, but the brief never defines what an "assertion reason digest" structurally is. Hash of the assertion source line? Hash of the asserted predicate AST? A model-generated natural-language reason (which would be non-deterministic and unsuitable for digesting)? Without definition, I3 can be satisfied by any string the producer attaches — which is the exact laundering surface I1 forbids.

**8-step trace:**

1. **Dependency-map:** I3 binds RED-test trace to per-assertion reason; reason-shape must be re-computable per I1.
2. **Write-path:** test runner emits reason; brief does not name the emit shape.
3. **Read-path:** re-verification recomputes reason from test source AST.
4. **Test-path:** W#3 refuses absence but does not refuse a forged reason.
5. **Fold-summary:** must specify reason = digest(assertion AST + context predicate), not a caller string.
6. **Cross-reference:** `df07923` and its surrounding canon.
7. **RED-test trace:** add W#3a `test_caller_supplied_reason_string_refused_unless_AST-derived`.
8. **Verify-before-declaring:** static check that reason field is sourced from AST-extractor, not caller arg.

---

## Minor findings

### MIN1. Q3 (divergence as block vs signal) is genuinely a covenant question, not just engineering

**Severity:** Minor. Not applicable to 8-step trace — framing question, not load-bearing claim. Hume flags only that the brief lists Q3 alongside engineering Qs; it should be marked covenant-axis explicitly so the right reviewer weighs in.

### MIN2. "Behavioral" in `WORKTREE_BEHAVIORAL` is undefined

**Severity:** Minor. The word "behavioral probe run" needs a closed-vocabulary definition or council pass-1 must explicitly defer the kind to a later slice. See B2's concern: behavioral evidence frequently has non-deterministic projections.

**8-step trace:** subsumed under B2.

### NIT1. "Honest homework" is rhetorically lovely but appears in section heading

Not applicable, pure framing.

---

## Closing synthesis

What is genuinely witnessed in this brief: the producer/consumer split (well-grounded in ADR 0042), the canon-governs-canon recursion at the witness layer (well-grounded in ADR 0044), and the additive non-breaking attachment to ADR 0045's lifecycle (mechanically verifiable). What is inferred but not witnessed: that staleness can be computed (B1), that observed_effect can be deterministic across kinds (B2), that 5 spot-fixes generalize to a contract (M1), that an LLM-prompt filter suffices at a different boundary (M3), and that "assertion reason" has a structural shape (M4). The brief over-extends where it asserts re-verifiability as a property of the contract before naming the per-kind functions that make re-verifiability concrete. Hume's recommendation: ratify the architectural skeleton, amend before canonicalization so each invariant carries its concrete computation mechanism — substrate-witnessed, not council-inferred. The first witness round-trip should run against an early `WORKTREE_RED_TEST` kind, the cleanest case, before the looser kinds (`WORKTREE_BEHAVIORAL`, `DRY_RUN_OBSERVATION`) are even formally specified.
