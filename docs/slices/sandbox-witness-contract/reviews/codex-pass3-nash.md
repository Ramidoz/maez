# Sandbox-Witness Contract — Codex Pass-3 Closure Check — Nash

**Artifact reviewed:** `docs/slices/sandbox-witness-contract/spec-brief.md` v1.3 at `4d69009`  
**Scope:** closure-only check against v1.3 deltas  
**Verdict:** RATIFY-WITH-NITS

| Delta | Verdict | Evidence |
|---|---:|---|
| Batch 4: WAL/concurrent DB cursor semantics + W#5g | CLOSED | v1.3 states DB cursor capture and ratify-time comparison must be transactionally coherent under concurrent SQLite WAL and that committed concurrent writes cannot hide behind stale snapshots: `spec-brief.md:116`. Authority notes require coherent transaction/snapshot discipline or disallow `DB_CURSOR`: `spec-brief.md:207`. W#5g is present: `spec-brief.md:387`. |
| Batch 11: subprocess-count/no-rerun guard + W#13c | CLOSED | Attach-time full subprocess exactly once and ratify-time zero full subprocesses by default are explicit: `spec-brief.md:335`, `spec-brief.md:341`. Future rerun requires `FULL_RERUN_AT_RATIFY`: `spec-brief.md:336`. W#13c is present: `spec-brief.md:411`. |
| Batch 10: per-reason refusal-path matrix | CLOSED | v1.3 adds the concrete matrix mapping each refusal reason to boundary and fixture: `spec-brief.md:416-430`. Reserved-cell condition is covered at `WITNESS_KIND_NOT_YET_VOCABULARY`: `spec-brief.md:428`. Divergence is affirmed as diagnostic/acknowledgment, not refusal: `spec-brief.md:430`. |
| NIT: explicit `__import__` | CLOSED | I7 now names `importlib.import_module`, `__import__`, and `getattr`: `spec-brief.md:130`. W#7e names dunder import: `spec-brief.md:396`. |
| NIT: split refused/stale vs divergence wording | CLOSED | Refused/stale now cannot ratify until re-witnessed, while diverged can ratify only with exact-generation acknowledgment: `spec-brief.md:321-324`. |
| NIT: live `*.db` / `*-wal` / `*-shm` fd wording | NIT | W#8b was improved to `closes_live_db_wal_shm_fds`: `spec-brief.md:400`, and the refusal matrix says live DB-WAL-SHM fd: `spec-brief.md:427`. This closes the substance, but not the exact requested glob spelling `*.db`, `*-wal`, `*-shm`. |

No material pass-2 opens remain. Verified artifact HEAD is `4d6900951949b217fac10e06185fc8186121aa35`.

RATIFY-WITH-NITS.

