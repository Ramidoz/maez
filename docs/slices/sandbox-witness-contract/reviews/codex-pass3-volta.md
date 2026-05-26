# Sandbox-Witness Contract — Codex Pass-3 Closure Check — Volta

**Artifact reviewed:** `docs/slices/sandbox-witness-contract/spec-brief.md` v1.3 at `4d69009`  
**Scope:** closure-only check against v1.3 deltas  
**Verdict:** RATIFY-WITH-NITS

Reviewed `spec-brief.md` v1.3 at `4d69009` against the pass-2 closure deltas only. No files edited.

| Delta | Verdict | Evidence |
|---|---:|---|
| Batch 4 WAL/concurrent DB cursor semantics + W#5g | CLOSED | v1.3 requires DB cursor capture/compare to be transactionally coherent under SQLite WAL and says a committed concurrent write cannot hide behind a stale cursor snapshot: `spec-brief.md:116`. Authority notes add coherent transaction/snapshot discipline and disallow DB_CURSOR authority if that cannot be guaranteed: `spec-brief.md:207`. W#5g is present: `spec-brief.md:387`. Resolved question records closure: `spec-brief.md:449`. |
| Batch 11 subprocess-count/no-rerun guard + W#13c | CLOSED | Attach-time runs full subprocess once; ratify-time does anchor/locus/generation checks and does not rerun full suite unless future `FULL_RERUN_AT_RATIFY`: `spec-brief.md:333-341`. W#13c is present: `spec-brief.md:411`. Implementability split instruments counts: attach exactly one, ratify zero by default: `spec-brief.md:432`. Resolved question records closure: `spec-brief.md:450`. |
| Batch 10 per-reason refusal-path matrix | CLOSED | Enum vocabulary is listed at `spec-brief.md:181-191`. v1.3 adds a concrete matrix mapping every refusal reason to boundary and fixture: `spec-brief.md:416-429`. Divergence is explicitly not a refusal: `spec-brief.md:416` and `spec-brief.md:430`. |
| NIT: explicit `__import__` | CLOSED | Static checks explicitly include `__import__`: `spec-brief.md:130`. W#7e names dynamic import and dunder import refusal: `spec-brief.md:396`. |
| NIT: split refused/stale vs divergence wording | CLOSED | Ratification flow now splits refused/stale generations from diverged generations: refused/stale cannot ratify until re-witnessed, diverged can ratify only with exact-generation acknowledgment: `spec-brief.md:321-324`. |
| NIT: live `*.db` / `*-wal` / `*-shm` fd wording | NIT | v1.3 says `live_db_wal_shm_fds` in W#8b: `spec-brief.md:400`, and `live DB-WAL-SHM fd` in the matrix: `spec-brief.md:427`. This captures the substance, but does not literally spell the requested glob forms `*.db`, `*-wal`, and `*-shm`. |

RATIFY-WITH-NITS.

