# Sandbox-Witness Contract — Codex Pass-2 Review — Pauli

**Artifact reviewed:** `docs/slices/sandbox-witness-contract/spec-brief.md` v1.2  
**Pass-2 brief:** `docs/slices/sandbox-witness-contract/reviews/codex-engineering-pass2-brief.md`  
**Verdict:** STILL OPEN

| Batch | v1.2 Change Cited | Verdict | Evidence |
|---|---:|---|---|
| 1. Legacy witness migration | `264-279` | CLOSED | Legacy shape is read-only via `legacy_sandbox_witness_json`; append/update/emit/ratify refuse legacy witness input; static guard and W#legacy are required. |
| 2. Immutable generations | `67`, `270-273`, `399` | CLOSED | `witness_id` + monotonic generation are identity, `(bond_id, proposal_id)` is index only, re-witnessing appends, stale/current generations are tested. |
| 3. Atomic ratification eligibility | `77`, `311-323`, `400-402` | CLOSED | Lock order and final snapshot bind proposal, generation, anchors, reverify result, divergence ack, status, preference write, and status transition. Concurrent/stale ack tests are named. |
| 4. Race-safe staleness anchors | `113-114`, `378`, `401` | STILL OPEN | v1.2 covers file hash/existence, DB cursor constraints, diagnostics, secondary-table append, and update/delete-without-cursor. It does not close the pass-1/pass-2 WAL/concurrency criterion. Line `401` tests concurrent anchor movement between reverify and status flip, but not WAL/concurrent reader-writer ambiguity inside DB cursor authority. Closure: add explicit DB-anchor WAL/concurrent writer semantics and a W#5 test for WAL/concurrency, or extend W#5e to name and exercise it. |
| 5. Deterministic observed effect | `105`, `163-174`, `369` | CLOSED | Normative per-kind `f(artifacts)` table exists, digest/canonicalization/exclusions are stated, W#4a is parameterized, and `WORKTREE_BEHAVIORAL` is deferred. |
| 6. Field-complete taint discipline | `119`, `246-260`, `380-383` | CLOSED | Boundary strings are classified into opaque id, enum, digest+provenance, path/ref resolver, narrative scan, or technical id/ref. W#6b/W#6c cover classification and boundary injection attempts. |
| 7. Alias-resistant I7 enforcement | `127`, `384-389` | STILL OPEN | Static/runtime enforcement is materially present, including path identity, aliases/shims, dependency edges, dynamic import/reflection, and provenance tags. But the required W#7 fixture set explicitly included `__import__`; v1.2 names dynamic import generically at `388` and `importlib/getattr/shared_helper` at `389`, but not `__import__`. Closure: add explicit `__import__` laundering fixture asserting `SELF_RATIFICATION_DETECTED`. |
| 8. Real path isolation | `137`, `390-393`, `409` | CLOSED | Requires exec-style subprocess before Maez imports, substrate-root semantics or explicit env mapping, store override precedence, `close_fds=True`, scratch-root assertions, and live-fd closure tests. |
| 9. Exhaustive `SubstrateLocus` | `232-244`, `390`, `394` | CLOSED | v1.2 replaces ellipsis with explicit loci, requires every path helper and hardcoded `memory/*.db` default mapped, and refuses unregistered opens by default. |
| 10. Refusal-path matrix | `176-189`, `396-407` | CLOSED | Every refusal reason is vocabulary-listed and W#10 requires table-driven real-boundary exercise asserting `WitnessRefused.reason`; divergence is explicitly diagnostic/ack, not refusal. |
| 11. Attach-time vs ratify-time cost split | `328-334`, `409` | STILL OPEN | The prose correctly splits attach-time full subprocess re-verification from ratify-time indexed freshness/locus/generation checks. But the pass-2 closure criterion also requires tests that count subprocess use and prove ratify-time freshness without accidental rerun. v1.2 has cost prose, but no named test for subprocess-count/no-rerun behavior. Closure: add a W#11/W#13 test that instruments subprocess invocation count, proves attach-time runs once, and ratify-time does not rerun unless `FULL_RERUN_AT_RATIFY` exists. |

The remaining gaps are narrow engineering-closure gaps, not covenant redesign: DB WAL/concurrency coverage, explicit `__import__` alias/dynamic-import fixture coverage, and a ratify-time no-rerun/subprocess-count test.

