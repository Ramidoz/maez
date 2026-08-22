# Theme 2 — the frozen S1 artifacts name code that does not exist

Status: **FINDING — owner decision required.** Surfaced by gate round 19
(`4a47238`) and verified independently against the tree before being
recorded here. Nothing has been changed in response.

## Why this matters more than the T5 rounds

This session opened on a stated premise: *the design phase is COMPLETE,
eleven gate rounds, schema clean, S1 witness protocol binding-ready at
v5.* Eight further rounds went into T5's execution model. Round 19
looked past T5 at the parts already declared **BINDING-READY** — §9's
T3 invocation contract, §10's T3/T4 literalizations, and the frozen
companion census — and found several of them referring to constructs
that are not in the codebase.

The companion digests all "MATCHED" at gate round 10. They did: a
digest proves a file has not changed. It does not prove the file's
claims are true. Every one of these would have been caught by executing
the contract once; none were caught by four rounds of reading it.

## Verified defects

1. **`AuditLog._migration_null_normalize` does not exist.**
   `core/cognition/audit_log.py` defines `_initialize`, `record`,
   `record_outcome`, `start_direct_edit_session`, `log_direct_edit`,
   `end_direct_edit_session`, `get`, `recent`, `recent_direct_edits`,
   `find_similar`, `stats`. There is no `_migration_null_normalize`.

   The *behavior* §10 describes is real — the NULL normalization is
   inline in `_initialize` (`audit_log.py:216-220`,
   `UPDATE audit_log SET memory_phase='gestation' WHERE memory_phase IS
   NULL`). So this is a naming error, not a fabricated behavior. But it
   is named in the **frozen census** (`theme2-s1-census.json`, digest
   `8527…`), and T4 compares `path::qualname` exactly, so **T4 as
   pinned fails on its own expectation file**. Gate round 11 closed a
   whole literalization item about this method.

2. **§9's `store_telegram` claim is false.** It states
   `memory_manager.store_telegram(...)` "reaches all three stamp sites
   via the three storage tiers". The three frozen anchors resolve to
   three *different* public entries: `@1506` → `store` (`:1479`),
   `@1605` → `store_telegram` (`:1576`), `@2073` → `store_core`
   (`:1977`). `store_telegram` writes `raw` only. T3 cannot exercise
   all three stamp sites through that one call.

3. **§9 named two `PrivateThoughts` methods that do not exist** —
   `record_secret`, `record_reflection`. Corrected in protocol v7 to
   `record_thought` (`:571`) and `record_signal` (`:604`), but the
   correction was itself incomplete: `insert_signal_in_transaction`
   (`:655`) is a third phase-writing surface and the anchor `@674`
   falls inside it.

4. **`span_planner.plan(...)` does not exist.** §9 names it as T3's
   invocation; the real public entry is
   `core/consolidation/span_planner.py:818 run_consolidation_pass()`.

5. **The "source_awareness public path-gate helper" is private** —
   `_should_skip_dir` (`core/memory/source_awareness.py:328`).

6. **A phase writer is outside the census.**
   `core/eval/longmemeval.py` contains `memory_phase` and sits under a
   censused root; the frozen census does not list it. Either it is a
   legitimate exclusion that must be stated, or the census is
   incomplete.

7. **`birth_phase.default_ledger_path()`'s docstring claim is false.**
   It says "EXACTLY the daemon's resolution (daemon/maez_daemon.py:186)".
   It resolves through `paths.memory_dir()` (honoring `MAEZ_DATA`),
   while the daemon builds its ledger path from a `MEMORY_DIR` derived
   from `paths.home()`. Dormant today because this host sets no
   `MAEZ_DATA`, but the two diverge under a supported configuration —
   and T5's own store-path guard leans on that claim.

## What this does and does not invalidate

- **It does not invalidate the schema work.** Rounds 2–10's ~110
  invalid-row controls were *executed* against real DDL; that evidence
  stands, subject to the S2 protocol's own open items.
- **It does not invalidate T5.** T5's contracts are the ones this
  session rebuilt and executed against.
- **It does invalidate "T3 and T4 are binding-ready".** Both were
  declared closed at rounds 10–11 on contracts that cannot be executed
  as written, and T4's frozen expectation file disagrees with the
  codebase.
- **It puts the census's frozen digest in an awkward position.** The
  digest is committed and gate-referenced; correcting the content
  changes it. That is a protocol revision, not an edit.

## The pattern worth keeping

Every defect in this file, and every defect that mattered in the eight
T5 rounds, was found by **executing** something — a control, a probe, a
sweep — and none by re-reading a document that had already passed a
gate. Four rounds certified `_migration_null_normalize` as a closed
literalization item. One AST sweep found it absent in seconds.

The reviewing was not the problem; treating *review of prose* as
equivalent to *execution against code* was.
