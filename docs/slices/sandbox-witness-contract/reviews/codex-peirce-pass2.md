# Sandbox-Witness Contract — Codex Pass-2 Review — Peirce

**Artifact reviewed:** `docs/slices/sandbox-witness-contract/spec-brief.md` v1.2  
**Pass-2 brief:** `docs/slices/sandbox-witness-contract/reviews/codex-engineering-pass2-brief.md`  
**Verdict:** STILL OPEN

Closure audit complete. I did not edit files. Lens: Peirce, so I treated "there is a named refusal reason/test" as insufficient unless v1.2 makes the refusal path prove the actual boundary.

| Batch | Verdict | Receipts / Audit |
| --- | --- | --- |
| 1. Legacy witness migration | CLOSED | v1.2 closes the bypass: legacy read-only surface renamed at lines 274-275, append/update/emit/ratify refusal with `LEGACY_WITNESS_SHAPE_REFUSED` at 275, static guard at 276, W#legacy/static at 403-404. |
| 2. Immutable generations | CLOSED | Immutable `witness_id` + monotonic generation at 270-273; current eligible witness derived/pointer constrained at 273; preservation test at 399. |
| 3. Atomic ratification eligibility | CLOSED | Critical section and lock order at 311-323; final snapshot binds proposal, witness, generation, anchors, reverify result, divergence ack, status, reason at 314-317; stale/concurrent tests at 400-402. |
| 4. Race-safe staleness anchors | STILL OPEN | v1.2 covers file hash/existence and DB cursor constraints at 113 and tests deletion/content/secondary/update-delete/diagnostic at 376-379, but omits the pass-2-required WAL/concurrent writer test. Closure criterion: add explicit WAL/concurrency semantics or a W#5* test proving DB cursor freshness cannot miss a concurrent writer/reader state transition. |
| 5. Deterministic observed-effect functions | CLOSED | Normative per-kind table at 163-174; digest algorithm/exclusions at 165; all populated kinds covered at 169-172; `WORKTREE_BEHAVIORAL` deferred at 174; W#4a parameterized at 369. |
| 6. Field-complete taint discipline | CLOSED | Digest/narrative split at 117-119; field-family classification at 246-259; boundary coverage at 260 and W#6b/W#6c at 382-383. |
| 7. Alias-resistant I7 enforcement | CLOSED | v1.2 directly addresses the pass-1 trapdoor: canonical path identity, `sys.modules` aliases/shims, forbidden edges, dynamic import/reflection restrictions, and runtime provenance tags at 127; W#7d-W#7f fixtures cover helper, dynamic import, shim alias, importlib/getattr at 387-389. |
| 8. Real path isolation | CLOSED | Subprocess/root discipline at 137; `SubstrateLocus` handle refusal at 139; lifecycle subprocess/non-live checks at 302-308; W#8a-W#8c cover env-before-import, fd closure, and registered path resolution at 391-393. |
| 9. Exhaustive `SubstrateLocus` | CLOSED | Explicit v1 locus list with no ellipsis at 232-240; registry maps path helpers and hardcoded `memory/*.db` defaults at 242-244; unregistered opens refused by W#8d at 394. |
| 10. Refusal-path matrix | STILL OPEN | v1.2 names refusal reasons at 176-189 and adds W#10 at 396 plus a general matrix sentence at 407, but it does not actually map each refusal reason to its exercised boundary. This risks vocabulary-only compliance, exactly Peirce's pass-1 concern. Closure criterion: add a real matrix row per `WitnessRefusalReason`, naming boundary type and fixture, including reserved-kind coverage and affirming divergence is non-refusal. |
| 11. Attach-time vs ratify-time cost split | STILL OPEN | v1.2 states attach-time full subprocess and ratify-time bounded checks at 328-334, and reiterates bounded ratify-time at 409. It does not require the pass-2 criterion that tests count subprocess/full-rerun usage and prove ratify-time freshness without accidental rerun. Closure criterion: add a W#13/W#cost test that instruments subprocess invocation count and proves ratify-time anchor failure/refusal happens without rerunning the expensive verifier unless `FULL_RERUN_AT_RATIFY` exists. |

No covenant-axis concern surfaced that needs `COVENANT-ESCALATION`; these are engineering closure gaps.

