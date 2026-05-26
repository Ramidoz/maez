# Descartes — Council Pass-1 Review — Sandbox-Witness Contract v1

**Reviewer:** Descartes (foundations / doubt / indubitability)
**Artifact:** `docs/slices/sandbox-witness-contract/spec-brief.md` v1
**Dispatched:** 2026-05-26
**Verdict:** **RATIFY-WITH-AMENDMENTS**

---

## Findings

### BLOCKING-1. Citation drift: ADR 0042 does not contain "Vectors 1–3"

**Severity:** Blocking (citation drift — Major per Descartes' lens).

The brief asserts (line 16, line 147) that "producer-causality canon (Vectors 1–3 at ADR 0042)" governs witness construction. I read `/home/rohit/maez/docs/adr/0042-drive-driven-curiosity-felt-organ.md` in full (47 lines). It does NOT enumerate Vectors 1, 2, 3, or 4. It contains a felt-organ context/decision/consequences trio. The Vector taxonomy lives in `/home/rohit/.claude/projects/-home-rohit-maez/memory/feedback_producer_causality_no_caller_score_laundering.md`, NOT in the ADR. The ADR references the discipline obliquely through "producer evidence honest, substrate-computed verdict" framing but never names the four Vectors. Similarly, line 59 cites "Vector 4 (canary-neutral-baseline, ADR 0043)" — ADR 0043 does name canary-neutral-baseline but does not call it "Vector 4"; that label lives in the same memory file.

**8-step trace:**

1. **Dependency-map:** every I1–I8 invariant grounds its authority in these Vector citations.
2. **Write-path:** brief proposes new schema explicitly anchored to "Vectors 1–3."
3. **Read-path:** council reviewers, Codex panel, and future fold cycles will follow citations to find authority.
4. **Test-path:** RED-test names (W#1–W#8) inherit Vector semantics by reference.
5. **Fold-summary:** the brief's authority chain currently routes through an ADR that does not contain the cited primitives.
6. **Cross-reference:** the actual home of the Vector taxonomy is the feedback memory file; the brief must cite it directly.
7. **RED-test trace:** no test currently asserts citation integrity; this is exactly the failure mode `canon-governs-canon` (ADR 0044) names.
8. **Verify-before-declaring:** re-reading ADR 0042 line-by-line confirms absence.

**Amendment required:** cite `feedback_producer_causality_no_caller_score_laundering` as the home of Vectors 1–4, with ADR 0042 / 0043 cited as the surface-level decisions they govern.

---

### BLOCKING-2. Schema-replacement is implicit, not declared

**Severity:** Blocking.

The current `SandboxWitness` in `/home/rohit/maez/core/policies/maintenance_proposals.py` lines 54–63 is:

```
red_tests_passed: bool
focused_tests_passed: bool
scratch_canary_passed: bool
witness_digest: str
```

Four caller-supplied booleans + one digest. The brief's contract refuses exactly this shape (I1: "caller-supplied values for re-computable fields are refused at attachment time"). The three booleans are caller-asserted verdicts. Yet the brief never names what happens to the existing SandboxWitness dataclass, its JSON serializer (`_sandbox_to_json` / `_sandbox_from_json`, lines 365–390), its persisted rows in `memory/maintenance_proposals.db`, or backward compatibility for proposals already carrying the legacy shape.

**8-step trace:**

1. **Dependency-map:** `maintenance_proposals.py` consumers, persisted rows, ADR 0045 references.
2. **Write-path:** existing `_sandbox_to_json` writes the bool-bearing shape today; new contract refuses it.
3. **Read-path:** existing `_sandbox_from_json` reconstructs the legacy shape on load.
4. **Test-path:** brief's W#9 asserts "proposal without witness still ratifies" but is silent on "proposal WITH legacy-shape witness."
5. **Fold-summary:** the old dataclass becomes structurally false under the new contract.
6. **Cross-reference:** ADR 0045 should be amended; brief currently asserts "lifecycle does not change" but the witness type *does* change.
7. **RED-test trace:** missing — needs `test_legacy_caller_supplied_bool_witness_refused_or_migrated`.
8. **Verify-before-declaring:** no static check proposed to confirm no live row carries the legacy shape.

**Amendment required:** the brief must explicitly state (a) the legacy `SandboxWitness` is deprecated, (b) the migration path for any rows already persisted, and (c) whether existing tests of the legacy shape become RED or are removed.

---

### MAJOR-1. I7 static-AST predicate is brittle foundation

**Severity:** Major.

I7 (witness-cannot-self-ratify) rests on a static-AST predicate that "refuses any module that exports both `construct_witness` and `reverify_witness` from the same namespace." This is doubt-vulnerable on three foundations: (a) dynamic imports / `importlib` / reflection evade it; (b) two modules in the same package can collude (`pkg.construct` and `pkg.reverify` both import from `pkg._shared`); (c) "same code path" is the load-bearing concept but "same namespace" is the proxy — these are not identical. A module-namespace check refuses the most legible offense and provides no defense against the legitimately dangerous one.

**8-step trace:**

1. **Dependency-map:** every witness producer module is downstream of this predicate.
2. **Write-path:** predicate runs at construction-time and at CI.
3. **Read-path:** re-verification trusts the predicate held.
4. **Test-path:** W#7 names the AST predicate but does not stress-test the evasion paths.
5. **Fold-summary:** I7's authority is "code path separation"; brief's mechanism is "namespace separation."
6. **Cross-reference:** precedent F17 from Slice 2 should be re-examined for the same gap.
7. **RED-test trace:** needs `test_self_ratification_via_shared_helper_module_refused`, `test_self_ratification_via_dynamic_import_refused`.
8. **Verify-before-declaring:** brief should declare what indubitable mechanism (e.g., separate process boundary, capability tokens) defends the cases AST cannot reach.

**Amendment required:** either strengthen the predicate to a behavioral check (re-verifier runs in a separate import context / subprocess; or capability-token discipline where construction-issued tokens are not re-verification-accepting), OR explicitly accept the AST predicate as a partial defense with named residual risk.

---

### MAJOR-2. I8 "live substrate" identification is foundationally unspecified

**Severity:** Major.

I8 asserts re-verification "must not mutate any live substrate" but does not specify the indubitable mechanism for distinguishing live from scratch. Path-prefix heuristic (`memory/*.db`)? Connection-string filter? Filesystem-namespace separation? Each has known failure modes (symlinks, bind mounts, in-memory SQLite shared cache). W#8's RED test names "filesystem boundary" without defining it.

**8-step trace abridged:** the load-bearing primitive (what *is* a live substrate) is undefended; every downstream non-disturbance assertion inherits this gap; remediation requires the brief to declare the mechanism (recommendation: an explicit `SubstrateLocus` enum + opened-handle registry, parallel to how `EncounterSource` works).

---

### MAJOR-3. Q7 (witness retention) is asserted-not-explored

**Severity:** Major.

Q7 says "per never-delete-memory, witnesses presumably never delete." I verified ADR 0019 line 95 ("Append-only, never delete") — the canon is real. But "presumably" is exactly the doubt-vulnerable shape Descartes refuses. A witness object carries digests of scratch DB contents and code state at a point in time; some witnesses will become stale (I5) and be superseded. Does "never-delete" apply, with superseded witnesses marked stale-but-retained, or do witnesses live outside the lived-memory substrate? The brief defers this but the answer changes the storage schema and the staleness lifecycle. This is not genuinely open; it is foundational and assumed.

**8-step trace abridged:** storage locus (Q7 second sub-question) is downstream of retention semantics (Q7 first); both must be answered before W#5's staleness RED test has a well-defined target.

---

### MINOR-1. I6 injection_patterns integration is load-bearing and confirmed

**Severity:** Minor — confirmatory, not blocking.

I verified `/home/rohit/maez/core/safety/injection_patterns.py` exists and contains the seven-bucket catalog (DIRECT_OVERRIDE, DELIMITER_INJECTION, ROLEPLAY, CONTEXT_MANIPULATION, ENCODING, MULTITURN_ESCALATION, USER_EXTENSIBLE). Citation holds. However, the brief should name the integration function (e.g., `scan()` returning `InjectionMatch`) so the boundary is mechanical, not aspirational. Not applicable to 8-step trace requirement: confirmatory check, not amendment.

---

### NIT-1. ADR 0044 wording

The brief paraphrases ADR 0044 as "witness governs claim." ADR 0044 line 27 actually says "When claim and witness disagree, the witness governs." Close enough that this is not load-bearing — pure phrasing. Not applicable, near-typo.

---

## Closing synthesis

The foundational claim — *a sandbox witness must be a re-verifiable artifact* — survives doubt. It rests on the indubitable observation that caller-asserted booleans are not evidence; the existing legacy `SandboxWitness` shape *is* exactly the producer-causality violation the new contract is built to refuse, which is a strong sign the contract is needed. What does NOT survive doubt as currently written: the citation chain (ADR 0042 does not contain the Vector taxonomy the brief leans on), the silent schema replacement (legacy `SandboxWitness` is structurally refused but never named for deprecation), and two load-bearing mechanisms (I7's namespace-proxy for code-path separation; I8's unspecified live-substrate identification). These are shoring-up amendments, not structural objections. The brief is ratifiable once Vector citations land at their actual canonical home, schema migration is declared, and the two mechanism-gaps are either tightened or declared as accepted residual risk with named follow-up slices.

**Files inspected:**

- `/home/rohit/maez/docs/slices/sandbox-witness-contract/spec-brief.md`
- `/home/rohit/maez/docs/adr/0042-drive-driven-curiosity-felt-organ.md`
- `/home/rohit/maez/docs/adr/0043-canary-neutral-baseline.md`
- `/home/rohit/maez/docs/adr/0044-canon-governs-canon.md`
- `/home/rohit/maez/docs/adr/0045-ratifiable-maintenance-proposals.md` (referenced)
- `/home/rohit/maez/docs/adr/0019-lived-memory-architecture.md`
- `/home/rohit/maez/core/safety/injection_patterns.py`
- `/home/rohit/maez/core/policies/maintenance_proposals.py`
- `/home/rohit/.claude/projects/-home-rohit-maez/memory/feedback_producer_causality_no_caller_score_laundering.md`
