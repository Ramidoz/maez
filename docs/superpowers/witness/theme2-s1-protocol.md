# Theme 2 — S1 (phase truth) witness protocol, v2

Status: PROTOCOL v2 — literalization of v1 per gate round 8's six
judgments. Binding once its gate passes; S1 code is barred until then.
The S1 implementation is judged against this file, not design prose.

## 0. Ground rules (unchanged from v1, plus digests)

- Airlock only: every command runs with `MAEZ_LEDGER_DB_PATH` inside a
  fresh directory under the session scratchpad; the harness refuses to
  start if the resolved path is outside it. Never the live tree.
- Fixture builder: `docs/superpowers/witness/theme2_s1_fixtures.py`,
  sha256 `b69a8c0ea86890b1c4b23d7b85e3f4157baa7f809765942922a98f34d4429dcb`.
  Invocation: `python3 theme2_s1_fixtures.py <airlock_dir>`.
- **Static digests** (must match exactly, every run):
  - F-E `ledger.db` = `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`
  - F-P `ledger.db` = `87921737ab54cc9d5effb069a1d16f5ec53c33a0f5321384cef39472a4c2d5a2`
- **Per-run digests** (time-stamped by migration/writer; recorded in
  the run report BEFORE any assertion): F-G, F-D1, F-D2, F-L, F-X.
- Migration set for all S1 fingerprints ("shipped files" resolution:
  S1 lands before S2, so the fingerprint is over migrations 0001–0005
  as shipped; the list is re-frozen when S2's migrations land):
  - 0001 `eb126df1dd8c6ff5e249dab0259582747e3352991468acc936052d728db7ca75`
  - 0002 `7aa3876024f45778a67e3e744f4ed5624146e94603cd7dd1e188c56a740fdc38`
  - 0003 `5e0829a501408b5db940a15b47899bd2899eb551da3f5795babe215ea00d9185`
  - 0004 `69e5f4bc78ac8a81f742c61da49bab022234dfb8647b9977ce3e1812ce77a659`
  - 0005 `5b66deb643d346a7f0b1ff154618b83366b1c7816de7f1d1b7304102c78d7c86`
- SQLite pinned: the run report records `sqlite3.sqlite_version`
  (expected 3.46.1) and the interpreter path; a different version is a
  reported deviation, not a silent substitution.
- Clock: fixtures and assertions never call wall-clock in the resolver
  path being tested; harness-injected times are integers named in each
  test. Resolver cache state: every T1 cell uses a fresh process.

## 1. Latch variant recipes (literal)

Built by the harness from F-L's airlock copy; `L` = the latch
directory `<airlock>/latch/`:

- **valid**: run the resolver once against F-L → it creates the latch;
  digest recorded.
- **torn**: copy valid latch dir; replace the published segment with
  the temp-file form: write the same bytes to `L/segment.tmp`, delete
  the published file. (Simulates crash before rename.)
- **corrupt**: copy valid; truncate the published segment to half its
  bytes.
- **stale-ahead**: copy valid from an F-L that then has its last turn
  removed by rebuilding F-L' = F-G + anchor only (fewer chain rows
  than latched head position).
- **foreign**: copy valid; edit its recorded canonical path field to
  `/nonexistent/ledger.db` (variant a) or its genesis hash field to
  64×`0` (variant b).

## 2. T1 — resolution table (16 cells, exact returns)

Resolver call, one fresh process per cell:
`python3 -c "from core.memory.birth_phase import resolve; print(resolve())"`
(final S1 API name pinned at implementation; the protocol's contract
is: one call, returns exactly one of `'gestation'|'lived'|'unknown'`,
plus a machine-readable reason code recorded in the report).

| # | Fixture | Latch | Expected |
|---|---|---|---|
| 1 | F-A | absent | `gestation` |
| 2 | F-A | valid | `unknown` |
| 3 | F-E | absent | `gestation` |
| 4 | F-E | valid | `unknown` |
| 5 | F-P | absent | `unknown` |
| 6 | F-P | valid | `unknown` |
| 7 | F-D1 | absent | `unknown` |
| 8 | F-D1 | valid | `unknown` |
| 9 | F-D2 | absent | `unknown` |
| 10 | F-D2 | valid | `unknown` |
| 11 | F-G | absent | `gestation` |
| 12 | F-G | valid | `unknown` |
| 13 | F-L | absent | `lived` + latch file created (digest recorded) |
| 14 | F-L | valid | `lived` (no new latch file) |
| 15 | F-X | absent | `unknown` |
| 16 | F-X | valid | `unknown` |

Additional cells for the remaining latch variants, all against F-L:
torn → `unknown`; corrupt → `unknown`; stale-ahead → `unknown` +
health signal row present; foreign-a → `unknown`; foreign-b →
`unknown`. **Doctrine note resolving round 8's T1 tension**: absence
and the 0-byte file are *provably pre-birth* (no structure exists to
misreport); the structural fingerprint (T6) governs only the
initialized branch — F-G must be structurally complete to read
`gestation`, F-P/F-D must not.

Kill: any cell differs from the table. Pre/post file-set assertion:
each cell records `find <airlock> -type f | sort` before and after;
only cell 13 may differ (by exactly the latch file).

## 3. T2 — latch publication and advance (frozen procedure)

Instrumentation: the latch writer exposes injection points
`S1_CRASH_POINT ∈ {after_tmp_write, after_rename}`; the harness runs
the writer in a subprocess and delivers `SIGKILL` at the named point
(synchronization via a sentinel file the writer touches immediately
before the point; harness waits ≤5 s for the sentinel, then kills).

1. `after_tmp_write` kill ×5 runs: subsequent resolver reads must
   observe exactly {no published segment} — never a torn one; each
   run's file set recorded.
2. `after_rename` kill ×5 runs: resolver observes a complete segment.
3. Two-line advance: harness performs one lived write with
   `S1_CRASH_POINT=between_commit_and_committed_line`; resolver then
   returns `lived`, repairs the mate line, and the report records the
   repaired bytes. Then: restore the pre-write ledger copy (taken
   before the write) with the latch left as-is → resolver returns
   `unknown`.
4. `PRAGMA wal_checkpoint(TRUNCATE)` then `VACUUM` on F-L: resolver
   `lived` before and after; zero rewind/health rows.
5. Stale-ahead fixture: `unknown` + exactly one health row.

Kill: any torn observation, any silent rewind acceptance, any
checkpoint/VACUUM-induced `unknown`.

## 4. T3 — consumer refusal (frozen census, exact outcomes)

Failure injection: not chmod (ambiguous under root) — the harness
points `MAEZ_LEDGER_DB_PATH` at a directory (guaranteed
`sqlite3.OperationalError` on connect) for the outage window, per
consumer call. Frozen census and per-consumer expected outcome:

| Consumer construct (at HEAD `bd083be`) | On `unknown` |
|---|---|
| `memory/memory_manager.py` stamp site @1506 | raises `PhaseUnknownRefusal`; no Chroma write |
| `memory/memory_manager.py` stamp site @1605 | same |
| `memory/memory_manager.py` stamp site @2073 | same |
| `core/infra/private_thoughts.py` default @587 | raises `PhaseUnknownRefusal`; no row |
| `core/infra/private_thoughts.py` default @627 | same |
| `core/infra/private_thoughts.py` default @674 | same |
| `private_thoughts` caller-supplied `memory_phase='lived'` while gate says otherwise | raises `ValueError` (revalidation); no row |
| `core/cognition/audit_log.py:AuditLog.record` @233 | writes with `memory_phase=NULL`-refusal path: raises `PhaseUnknownRefusal`; no row |
| `AuditLog.start_direct_edit_session` @405 | same |
| `AuditLog.log_direct_edit` @480 | same |
| `core/memory/source_awareness.py:is_born` @342 | returns False (gate closed); writes nothing |
| `core/consolidation/span_planner.py` meta read @241 | typed refusal of the span plan; no plan rows |
| `core/ledger/writer.py` stage resolution @450 | write refused (post-birth mode); pre-birth shadow path unchanged |

(The exact exception type `PhaseUnknownRefusal` is the S1 API
contract; a different spelling with identical semantics is recorded,
not failed — but "silent success" or a `gestation` stamp is a kill.)

Exact-set assertions after the outage window, literal SQL/queries:
- Chroma stores: for every collection in the frozen store inventory
  (raw/daily/core in the airlock fixture), metadata query
  `where={"memory_phase":"gestation"}` restricted to ids created in
  the window → **empty**.
- `private_thoughts.db`: `SELECT COUNT(*) FROM private_thoughts WHERE
  memory_phase='gestation' AND ts BETWEEN :w0 AND :w1` → **0**.
- `audit_log.db`: same shape → **0**.
Positive control: the same consumer calls against healthy F-G must
succeed and stamp `gestation` (proving the assertions can see stamps).

Kill: one gestation stamp in-window, one silent success, or a
positive control that writes nothing.

## 5. T4 — census conformance (both directions)

The S1 census test walks `memory/`, `core/`, `daemon/`, `skills/`,
`cli/` (excluding `tests/`, `docs/`, `logs/`) with Python `ast`
(pinned: the venv interpreter's version recorded), collecting every
(a) writer of a `memory_phase` key/column and (b) reader of
`birth_event_turn_id`. Expected sorted census = exactly the 13
constructs of §4's table plus `core/memory/birth_phase.py` itself and
`core/ledger/chain.py`'s comment-level mention excluded by AST (not a
read). The committed expected list lives beside the test as a sorted
JSON file; its digest is recorded in the run report.

- Seeded-unexpected control: write the 6-line file
  `core/_s1_census_seed.py` with content exactly
  `PHASE = {"memory_phase": "gestation"}` + a `birth_event_turn_id`
  read via sqlite; the census must FAIL naming it. File removed after.
- Missing-expected control: run the census with one expected entry
  deleted from the JSON; must FAIL naming the deletion.

Kill: census passes in either seeded state.

## 6. T5 — flags-off invariance (frozen run)

- Environment: all `MAEZ_*` phase/S1 flags unset; full env recorded.
- Suite: `pytest` selector list frozen at S1-authoring commit,
  executed inside the airlock harness (never live paths — scar 1);
  green required.
- Replay: the pinned replay manifest
  `docs/superpowers/witness/theme2-s1-replay.json` (committed with the
  S1 code; 20 interactions, ids+bytes+times; digest recorded here at
  that commit) driven twice — flags off, flags off again — byte-compare
  of the airlock store tree between runs and against the baseline
  archive; sentinel: `find` must show no latch directory.

Kill: any store diff, any latch file, any suite red.

## 7. T6 — structural fingerprint (literal mutations)

Validator inputs frozen: migration names+digests (§0), table set (the
15 v1 tables of 0001–0005 — enumerated in the validator source),
trigger/index name sets read from `sqlite_master` and compared to the
frozen lists committed beside the validator, genesis-row projection
bytes, `meta.last_chain_hash` vs recomputed tip.

Nine mutation controls on copies of F-G, each must flip `gestation` →
`unknown`:

1. `DROP INDEX idx_turns_tenant_ts;`
2. `CREATE INDEX extra_idx ON turns(surface);`
3. `UPDATE schema_migrations SET name='0005_tampered' WHERE name LIKE '0005%';`
4. `DELETE FROM schema_migrations WHERE name LIKE '0002%';`
5. `INSERT INTO schema_migrations VALUES ('0099_phantom', 0);` *(shape per table)*
6. genesis byte flip: `UPDATE turns SET raw_text=raw_text||'x' WHERE chain_position=0;` *(via a triggers-off connection)*
7. `UPDATE meta SET value='stale' WHERE key='last_chain_hash';`
8. `DROP TABLE claims;`
9. `DROP TRIGGER` one name from the frozen trigger list.

Kill: any mutation still reads `gestation`; also the unmutated copy
must still read `gestation` after the mutation batch (control of the
controls).

## 8. Report obligations (unchanged from v1)

Fixture digests (static verified, per-run recorded), resolver commit,
every cell/test outcome verbatim before interpretation, wall-clock,
deviations. The protocol is never edited retroactively to fit an
outcome.
