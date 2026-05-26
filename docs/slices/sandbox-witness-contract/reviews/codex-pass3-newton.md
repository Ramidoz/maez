# Sandbox-Witness Contract — Codex Pass-3 Closure Check — Newton

**Artifact reviewed:** `docs/slices/sandbox-witness-contract/spec-brief.md` v1.3 at `4d69009`  
**Scope:** closure-only check against v1.3 deltas  
**Verdict:** RATIFY-WITH-NITS

| Delta | Verdict | Evidence lines |
|---|---:|---|
| Batch 4 WAL/concurrent DB cursor semantics | CLOSED | v1.3 requires DB cursor capture/compare to be transactionally coherent under concurrent SQLite WAL reader/writer behavior and says committed concurrent writes cannot hide behind stale snapshots: `spec-brief.md:116`. Authority notes also forbid `DB_CURSOR` where coherent WAL snapshot discipline cannot be guaranteed: `spec-brief.md:207`. |
| Batch 4 W#5g anchor | CLOSED | W#5g is present as `test_db_cursor_detects_wal_concurrent_writer_between_capture_and_ratification`: `spec-brief.md:387`. Integration scaffolding includes concurrency harness for W#5*: `spec-brief.md:432`. |
| Batch 11 subprocess-count/no-rerun guard | CLOSED | v1.3 says attach-time full subprocess re-verification runs once, while ratify-time does anchor/generation/locus checks and does not rerun the full suite unless future `FULL_RERUN_AT_RATIFY` policy exists: `spec-brief.md:333`. The subprocess-count guard requires instrumentation, exactly one attach-time subprocess, and zero ratify-time subprocesses by default: `spec-brief.md:341`. |
| Batch 11 W#13c anchor | CLOSED | W#13c is present as `test_ratification_does_not_rerun_full_witness_subprocess_without_full_rerun_policy`: `spec-brief.md:411`. Implementability text specifies count exactly one at attach-time and zero at ratify-time unless future policy exists: `spec-brief.md:432`. |
| Batch 10 per-reason refusal-path matrix | CLOSED | Matrix now maps every `WitnessRefusalReason` to a boundary and fixture, and explicitly says divergence is diagnostic/acknowledgment, not refusal: `spec-brief.md:416`. Rows cover all ten refusal reasons plus divergence: `spec-brief.md:418`. |
| NIT: explicit `__import__` | CLOSED | I7 now explicitly names `importlib.import_module`, `__import__`, and `getattr` indirection: `spec-brief.md:130`. W#7e also names dunder import: `spec-brief.md:396`. |
| NIT: split refused/stale vs divergence wording | CLOSED | Ratification lifecycle now separates refused/stale generations, which cannot ratify until re-witnessed, from divergent generations, which can ratify only with exact-generation acknowledgment: `spec-brief.md:321`. |
| NIT: live `*.db` / `*-wal` / `*-shm` fd wording | NIT | W#8b now says `live_db_wal_shm_fds`, and the matrix says `live DB-WAL-SHM fd`: `spec-brief.md:400`, `spec-brief.md:427`. This closes the semantic requirement, but not the exact pass-2 wording that asked for literal `*.db`, `*-wal`, and `*-shm` spelling. |

RATIFY-WITH-NITS.

