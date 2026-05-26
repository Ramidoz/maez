# Sandbox-Witness Contract — Codex Engineering Pass-3 Synthesis

**Prepared:** 2026-05-26  
**Artifact reviewed:** `docs/slices/sandbox-witness-contract/spec-brief.md` v1.3 at `4d69009`  
**Review records:** `docs/slices/sandbox-witness-contract/reviews/codex-pass3-{newton,nash,volta}.md`

This document is derivative reconstruction. The three pass-3 review files are the witnessed review record.

---

## Verdict Summary

| Seat | Verdict |
| --- | --- |
| Newton | RATIFY-WITH-NITS |
| Nash | RATIFY-WITH-NITS |
| Volta | RATIFY-WITH-NITS |

Engineering pass-3 result: **RATIFY-WITH-NITS.**

All material pass-2 opens are closed in v1.3:

- Batch 4: WAL/concurrent DB cursor semantics + W#5g closed.
- Batch 11: subprocess-count/no-rerun guard + W#13c closed.
- Batch 10: per-reason refusal-path matrix closed.
- NITs for `__import__` and divergence/refused/stale wording closed.

One typographical/framing nit remains:

- W#8b / refusal matrix should literally spell `*.db`, `*-wal`, and `*-shm` rather than only `live_db_wal_shm_fds` / `live DB-WAL-SHM fd`.

No material engineering open remains. No covenant-axis escalation surfaced.

---

## Recommended Next Step

Fold the W#8b wording nit, then canonicalize as Decision 41 / ADR 0046.

