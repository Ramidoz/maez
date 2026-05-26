# Sandbox-Witness Contract — Codex Pass-2 Review — Ohm

**Artifact reviewed:** `docs/slices/sandbox-witness-contract/spec-brief.md` v1.2  
**Pass-2 brief:** `docs/slices/sandbox-witness-contract/reviews/codex-engineering-pass2-brief.md`  
**Verdict:** STILL OPEN

Ohm closure audit, read-only. Receipts: workspace HEAD is `3fcafe9`; v1.2 fold is present at `22507a8`; pass-2 brief defines this as closure-only, not redesign.

| Batch | v1.2 change cited | Verdict | Evidence |
| --- | --- | --- | --- |
| 1 | spec lines 264-279, 403-404 | CLOSED | Legacy read-only surface, append/update/emit/ratify refusal with `LEGACY_WITNESS_SHAPE_REFUSED`, static guard, and W#legacy coverage are explicit. |
| 2 | lines 61-68, 270-273, 299, 399 | CLOSED | `witness_id` + monotonic generation are identity; `(bond_id, proposal_id)` is index; re-witness appends and preserves stale generations. |
| 3 | lines 71-78, 311-323, 400-402 | CLOSED | Ratification critical section binds proposal, generation, anchors, reverify result, divergence ack, status, owner preference, and status transition. |
| 4 | lines 113-114, 191-205, 373-379 | STILL OPEN | File and DB cursor semantics are mostly closed, but pass-1/pass-2 required WAL/concurrency coverage. v1.2 names `DB_CURSOR` semantics and tests deletion, preserved-mtime content change, secondary append, update/delete without change cursor, diagnostic truncation/rotation, but no explicit WAL/concurrent-reader/writer test or transaction-bound cursor rule. Closure: add a W#5g-style test for WAL/concurrent writer/reader behavior and specify the cursor comparison is taken from a race-safe snapshot/transaction. |
| 5 | lines 101-105, 163-174, 369 | CLOSED | Normative per-kind `observed_effect = f(artifacts)` table exists for all populated kinds; `WORKTREE_BEHAVIORAL` is deferred. |
| 6 | lines 115-120, 246-260, 380-383 | CLOSED | Field families are classified across digest, narrative, enum, path/ref, and opaque id; W#6 is table-driven and includes refs/paths/test names/producer ids. |
| 7 | lines 121-128, 384-389 | CLOSED | Alias-aware static enforcement plus runtime provenance tags are required; tests cover shared helper, dynamic import, shim alias, importlib/getattr. |
| 8 | lines 133-139, 390-394, 425 | CLOSED | v1.2 binds subprocess execution to env-before-import, path-helper substrate root semantics or explicit equivalent, override precedence, `close_fds=True`, startup scratch-root assertion, and unregistered open refusal. |
| 9 | lines 232-244, 390, 393-394 | CLOSED | `SubstrateLocus` has an explicit v1 enum with no ellipsis; registry must map every path helper and `rg`-discovered hardcoded `memory/*.db`; unmapped opens refuse by default. |
| 10 | lines 176-189, 396-407 | CLOSED | Every refusal reason is in closed vocabulary; W#10 is table-driven over every reason and asserts `WitnessRefused.reason`; divergence is explicitly diagnostic/ack, not refusal. |
| 11 | lines 328-334, 409 | STILL OPEN | The attach-time vs ratify-time cost model is correct in prose, but pass-2 closure required tests that count subprocess use and prove ratify-time freshness does not accidentally rerun the expensive verifier. v1.2 says attach-time full verification may take seconds and ratify-time must be bounded, but no W# explicitly counts subprocess invocations or asserts ratify-time zero reruns absent `FULL_RERUN_AT_RATIFY`. Closure: add a named test proving attach invokes the subprocess once, ratify invokes none by default, and only a future closed `FULL_RERUN_AT_RATIFY` policy can change that. |

No new covenant-axis concern found; no `COVENANT-ESCALATION`.

Plain English: v1.2 did the big structural repair. The remaining engineering gaps are narrow but real: one race-safety test for SQLite/WAL-style staleness, and one resource-cost guard proving ratification does not quietly rerun the expensive witness machinery.

