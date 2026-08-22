# Theme 2 — S1 (phase truth) witness protocol, v1

Status: PROTOCOL, committed before any S1 code (per design §8).
Authorized by gate round 7 (`ee26402`): S1 may begin binding
witness-protocol authoring. This file is the binding contract; the S1
implementation is judged against it, not against the design prose.
Design references: §5 (tri-state + latch), §12 (two-line latch,
consumer carriers), §13/§14 (fingerprinted structural contract,
census).

## 0. Ground rules

- Every run below executes in the **airlock**: a temp directory under
  the session scratchpad, `MAEZ_LEDGER_DB_PATH` pointing inside it,
  and a harness precondition that refuses to start if the resolved
  path is outside the airlock root. Never the live tree (scar rule 1).
- Fixture digests (sha256 of every fixture DB and latch file, the
  migration files applied, and the frozen consumer list) are recorded
  in the run report before any assertion executes.
- Every test is binary: expected exact outcome, or the protocol
  fails. No "improved"/"mostly" language.
- The live `memory/` tree is never read or written. Flags stay off
  outside the airlock.

## 1. Fixtures

- **F-A absent**: no file at the resolved path.
- **F-E uninitialized-empty**: 0-byte file (today's live shape).
- **F-P partially-migrated**: migrations applied through 0002 only.
- **F-D damaged**: valid DB with `turns` table dropped; and a second
  variant with 16 bytes overwritten mid-file.
- **F-G gestation-complete**: fully migrated, genesis intact, zero
  non-genesis rows, digests recorded.
- **F-L lived**: F-G plus a birth-anchor row written through the
  production writer (flag on, airlock path) and `meta` pointer set.
- **F-X divergent**: F-L with `meta.birth_event_turn_id` UPDATEd to a
  nonexistent id (simulating meta mutation).
- **Latch variants**: none / valid (matching F-L) / torn (temp file
  present, no rename) / corrupt (truncated JSON) / stale-ahead
  (latch chain-head beyond the ledger tip) / foreign (valid latch
  whose recorded canonical path or genesis differs from the fixture).

## 2. Tests and exact expected outcomes

### T1 — resolution table (24 cells)

For each fixture {F-A, F-E, F-P, F-D×2, F-G, F-L, F-X} × latch
{absent, present-matching-or-best-fit}: call the tri-state resolver;
the result must equal the design §5/§13 table exactly:

| Fixture | latch absent | latch present |
|---|---|---|
| F-A | gestation | unknown |
| F-E | gestation | unknown |
| F-P | unknown | unknown |
| F-D (both) | unknown | unknown |
| F-G | gestation | unknown |
| F-L | lived (latch created) | lived (equality verified) |
| F-X | unknown | unknown |

Kill: any cell differs.

### T2 — latch publication and advance

1. Crash injection between temp-write and rename, and between rename
   and directory fsync (kill -9 the writer process at instrumented
   points): a subsequent reader must never observe a torn latch —
   observed states are exactly {no latch, complete latch}.
2. Two-line advance: crash between ledger COMMIT and the `committed`
   line: next observation reads `advancing` without mate → resolver
   returns `lived` (the ledger has the row) and repairs the mate;
   restore-to-latest-latch inside that window → `unknown`.
3. `PRAGMA wal_checkpoint(TRUNCATE)` and `VACUUM` on F-L: resolver
   result unchanged (`lived`), zero rewind reports.
4. Stale-ahead latch (power-loss simulation: ledger truncated to an
   earlier consistent snapshot, latch retained): `unknown`, plus the
   health signal fires.
5. Foreign latch: `unknown`, never `gestation`, never adopted.

Kill: any observed torn latch, any silent rewind acceptance, any
checkpoint/VACUUM false rewind.

### T3 — consumer refusal (the A6 core)

Against F-L, make the ledger unreadable mid-run (chmod 000 between
two writes). For every consumer in the frozen census — the three
`memory_manager` stamp sites, `private_thoughts` (default AND
caller-supplied paths), `audit_log.record` AND each direct-edit
session method (enumerated by T4's census at authoring time),
`source_awareness.is_born` — the write must refuse with the typed
error or queue; then exact-set SQL over every store: **zero rows
stamped `gestation` during the outage window**. `source_awareness`
gates must read as not-proven-born without stamping anything.

Kill: one gestation stamp, or one consumer that silently succeeded.

### T4 — census conformance

The AST census test enumerates every writer of `memory_phase` and
every reader of `meta.birth_event_turn_id` in the repo and compares
to the frozen list committed with the S1 code. Seeding a synthetic
new consumer file must fail the test.

Kill: census passes with the seeded consumer present.

### T5 — flags-off invariance

With all S1 flags off: the full existing test suite is green
(airlock-redirected, never live), a pinned 20-interaction replay
produces byte-identical stores, and no file appears under the latch
directory.

Kill: any diff, any file.

### T6 — structural fingerprint

The gestation validator on F-G must verify: migration names + sha256
digests match the shipped files exactly; `sqlite_master` trigger and
index name sets equal the frozen lists; genesis row bytes equal the
recorded projection; `meta.last_chain_hash` equals the recomputed
tip. Each of six seeded mutations (one missing index, one extra
trigger, one altered migration digest, one genesis byte flip, one
stale head pointer, one dropped table) must flip the result to
`unknown`.

Kill: any seeded mutation still reads `gestation`.

## 3. Report obligations

The run report records: fixture digests, the exact resolver build
(commit), each cell/test outcome, wall-clock, and any deviation —
verbatim, before interpretation. A failed cell is reported as failed;
the protocol is never edited retroactively to fit an outcome (canon:
witness before claim).
