# Sandbox-Witness Contract — Codex Pass-2 Review — Arendt

**Artifact reviewed:** `docs/slices/sandbox-witness-contract/spec-brief.md` v1.2  
**Pass-2 brief:** `docs/slices/sandbox-witness-contract/reviews/codex-engineering-pass2-brief.md`  
**Verdict:** STILL OPEN

Reviewed at worktree HEAD `3fcafe9`, with v1.2 fold at `22507a8`. No files edited.

| Batch | Verdict | Evidence |
| --- | --- | --- |
| 1. Legacy witness migration | CLOSED | `spec-brief.md:270`, `274`, `275`, `276`, `279`: legacy read-only rename, write-boundary refusal, static guard, and real append/update/ratify test are all named. |
| 2. Immutable witness generations | CLOSED | `67`, `271`, `272`, `273`, `399`: identity is `witness_id`/generation; semantic key is index; re-witness appends; eligible pointer/event derivation is constrained; stale/current generation preservation is tested. |
| 3. Atomic ratification eligibility | NIT | `73`, `77`, `311`, `315`, `322`, `400`: material closure is present. Nit: `318-319` groups refused/diverged/stale under one "OR acknowledgment" sentence. Elsewhere staleness requires re-witnessing, so this is wording, but canonical text should split divergence from refused/stale. |
| 4. Race-safe staleness anchors | STILL OPEN | `113`, `195`, `203`, `204`, `378`: file and DB cursor semantics mostly close, but WAL/concurrency remains absent from the test anchor. Closure requires explicit DB cursor capture/compare semantics under concurrent WAL writer/reader conditions, plus a W#5 test naming that race. |
| 5. Deterministic observed-effect functions | CLOSED | `105`, `163`, `165`, `169`, `174`, `369`: normative `f(artifacts)` table covers populated kinds, excludes nondeterminism, fixes digest algorithm, parameterizes W#4a, and defers `WORKTREE_BEHAVIORAL`. |
| 6. Field-complete taint discipline | CLOSED | `119`, `248`, `252`, `255`, `260`, `382`: every boundary string family is classified; digests require provenance; refs/paths/test names/producer ids cross real boundaries in W#6 coverage. |
| 7. Alias-resistant I7 enforcement | NIT | `127`, `384`, `388`, `389`: closed by alias-aware static enforcement plus runtime provenance. Nit: pass-2 checklist names `__import__`; v1.2 says dynamic import/reflection but should spell `__import__` into W#7e/W#7f for receipt parity. |
| 8. Real path isolation | CLOSED | `137`, `391`, `392`, `393`, `409`: root override/path-helper binding, env-before-import subprocess, `close_fds`, registered path assertion, and import-time/FD coverage are all required. |
| 9. Exhaustive `SubstrateLocus` | CLOSED | `232`, `235`, `242`, `244`, `394`: explicit v1 enum replaces ellipsis; path helpers and hardcoded `memory/*.db` defaults must map; unmapped opens refuse. |
| 10. Refusal-path matrix | CLOSED | `176`, `396`, `397`, `407`: real-boundary matrix, reason assertion, populated/reserved kind coverage, and divergence-as-non-refusal are required. |
| 11. Attach-time vs ratify-time cost split | STILL OPEN | `330`, `331`, `332`, `334`, `409`: the prose splits cost correctly, but the pass-2 closure criterion requires tests that count subprocess use and prove ratify-time freshness without accidental rerun. v1.2 has no W# test for subprocess invocation count or ratify-time no-rerun enforcement. |

## Still Open Closure Criteria

Batch 4 needs one concrete fold: add WAL/concurrency to the staleness-anchor contract and test matrix. The minimal closure text would require DB cursor capture and ratify-time comparison to be transactionally coherent under concurrent SQLite WAL writer/reader behavior, with a W#5g-style test that proves a concurrent committed write cannot hide behind a stale cursor snapshot.

Batch 11 needs one concrete fold: add a test anchor that instruments/counts subprocess runner invocations. It should prove attach-time performs exactly the intended full subprocess re-verification, while ratify-time performs freshness/locus/generation checks without launching the full rerun path unless `FULL_RERUN_AT_RATIFY` is explicitly enabled by a later policy.

No new covenant-axis concern found; no COVENANT-ESCALATION.

