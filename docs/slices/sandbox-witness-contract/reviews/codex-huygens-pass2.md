# Sandbox-Witness Contract — Codex Pass-2 Review — Huygens

**Artifact reviewed:** `docs/slices/sandbox-witness-contract/spec-brief.md` v1.2  
**Pass-2 brief:** `docs/slices/sandbox-witness-contract/reviews/codex-engineering-pass2-brief.md`  
**Verdict:** STILL OPEN

No edits made. I reviewed the pass-2 brief, v1.2 spec, and pass-1 synthesis at the requested worktree/commits.

| Batch | Verdict | Receipts | Audit note |
| --- | --- | --- | --- |
| 1. Legacy witness migration | CLOSED | `spec-brief.md:264-279`, `403-404` | Closes read-only legacy compatibility, renamed read surface, append/update/emit/ratify refusal, static guard, and real-boundary tests. First-boot race is named at `277`. |
| 2. Immutable witness generations | CLOSED | `61-68`, `270-273`, `399-400` | `witness_id` + monotonic generation is identity; `(bond_id, proposal_id)` is index; re-witnessing appends; stale/current generations are tested. |
| 3. Atomic ratification eligibility | CLOSED | `71-78`, `311-323`, `400-402` | Lock order and final eligibility snapshot bind generation, anchors, reverify result, ack id, `WitnessStatus`, and final reason. Stale ack/concurrent advancement tests are present. |
| 4. Race-safe staleness anchors | STILL OPEN | Failing lines: `378`, `409` | File/DB/diagnostic semantics are mostly closed at `191-205`, but the pass-2 criterion requires WAL/concurrency coverage. v1.2 names secondary-table/update/delete and generic integration concurrency, but not WAL/concurrent DB cursor behavior. Closure criteria: add explicit WAL/concurrent-writer anchor test or state the cursor authority rule that makes WAL/concurrency impossible/irrelevant. |
| 5. Deterministic observed-effect functions | CLOSED | `163-174`, `369` | Normative per-kind table exists; digest algorithm/canonical JSON/exclusions are declared; W#4a is parameterized over populated kinds; `WORKTREE_BEHAVIORAL` deferred. |
| 6. Field-complete taint discipline | CLOSED | `115-120`, `246-260`, `380-383` | Field-family table covers ids, enums, digests, refs/paths, narrative, and technical ids; tests include classification and injected refs/paths/test names/producer ids. |
| 7. Alias-resistant I7 enforcement | CLOSED | `121-128`, `384-389` | Resolved-file module identity, alias/shim normalization, dynamic import/reflection restrictions, runtime provenance tags, and laundering fixtures are specified. |
| 8. Real path isolation | NIT | `133-139`, `390-393`, `409` | Materially closed: env before import, path-helper binding/equivalent semantics, precedence, `close_fds=True`, startup scratch-root assertion. Nit: W#8b says "live fds"; spelling out `*.db`, `*-wal`, `*-shm` would match the pass-1 wording exactly. |
| 9. Exhaustive `SubstrateLocus` | CLOSED | `232-245`, `390`, `393-394` | Registry has no ellipsis, requires mapping every path helper and `rg`-discovered hardcoded `memory/*.db`, and refuses unmapped opens. |
| 10. Refusal-path matrix | STILL OPEN | Failing lines: `176-189`, `407` | v1.2 lists reasons and says every reason maps to a real boundary, but does not provide the per-reason matrix. Closure criteria: add a table mapping each `WitnessRefusalReason` to exactly one exercised boundary and the fixture that asserts `WitnessRefused.reason`. |
| 11. Attach-time vs ratify-time cost split | STILL OPEN | Failing lines: `328-334`, `409` | The split itself is clear, but pass-2 requires tests that count subprocess use and prove ratify-time freshness without accidental rerun. v1.2 does not name that test. Closure criteria: add a W# test that counts subprocess invocations: attach = one full rerun, ratify = zero full reruns unless `FULL_RERUN_AT_RATIFY` is explicitly enabled. |

Huygens closure read: Batches 1-3 are closed. The remaining engineering opens are narrow and foldable: explicit WAL/concurrency coverage for DB anchors, an actual refusal-reason matrix, and a subprocess-count/no-accidental-rerun cost test.

