# Theme 2 — S1 (phase truth) witness protocol, v7.4

Status: PROTOCOL v7.4. (Earlier headers drifted across string-edited bumps — title and status disagreed; this line is now the single authority.) Body = v1; §9 = v3, §10 = v4 (one v6.1
correction), §11 = v5, §12 = v6.6.
Binding once its gate passes; S1 code is barred until then. The S1
implementation is judged against this file, not design prose.
v6 closed T5's execution model against the pre-execution audit; v6.1
closed gate round 12's six items (A, B, C, D, E, G — F passed); v6.2
closed gate round 13's three reopened items (B, D, E — A, C, G passed)
and its finding I; v6.3 closed gate round 14's B, D, E, I and its
blocking finding J, and recorded finding K; v6.4 closed gate round 15's
B, D, E and J (I passed); v6.5 closed gate round 16's B, D and J and
acted on its finding L, which changed what T5 measures; v6.6 made the
gate executable and pinned the discriminator's activation. v7 cut
T5 to the discriminator on the owner's ruling after gate round 18, and
corrected §9's T3 contract. **v7.1 carries the executed baseline's
digests — this is the amendment gate round 11 requires to precede the
first S1 code commit.** The T5
archive digest and the volatile-field literal arrive in v7, which per
gate round 11 must precede the first S1 code commit.

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
| `core/cognition/audit_log.py:AuditLog.record` | raises `PhaseUnknownRefusal`; no row *(v7.4: RESOLVED — owner ruled the explicit stamp; `record()` now names the column through the gate, and the SQL DEFAULT is a fallback only)* |
| `AuditLog.start_direct_edit_session` | raises `PhaseUnknownRefusal`; no row |
| `AuditLog.log_direct_edit` | same |
| `AuditLog.end_direct_edit_session` | same *(added v7.2: a real writer the frozen census omitted)* |
| `AuditLog._initialize` | the inline NULL normalization; §10's ruling applies here, not to a `_migration_null_normalize` method *(v7.2)* |
| `core/memory/source_awareness.py:is_born` @342 | returns False (gate closed); writes nothing |
| `core/consolidation/span_planner.py` meta read @241 | typed refusal of the span plan; no plan rows |
| `core/ledger/writer.py` stage resolution @450 | write refused (post-birth mode); pre-birth shadow path unchanged |

(The exact exception type `PhaseUnknownRefusal` is the S1 API
contract; a different spelling with identical semantics is recorded,
not failed — but "silent success" or a `gestation` stamp is a kill.)

### v7.4 — the T3 authority is the map, and the harness drives real sinks

Gate round 21 rejected the first T3 harness (gate-level exercise where
the map named store methods; one bite; no census→map join) and found two
production regressions in my new wiring, both closed: the ledger
writer's S1 check sits AFTER the disabled no-op (a disabled writer is a
shadow no-op and must stay one; direct enabled callers seeing
`PhaseUnknownRefusal` is ratified, not accidental), and dormant
`store()` accepts caller metadata sentinels verbatim as legacy did.

The authoritative T3 surface is now `theme2-s1-t3-map.json` (14
stampers, 6 readers/exemptions, census→map join enforced by
`tests/test_t3_map_join.py`) and `tests/test_t3_consumer_refusal.py`,
which drives real disposable Chroma and real SQLite/ledger sinks,
reads stamped phases back from every store, and bites per-site — with
an inverse bite for the ledger writer, whose broken-fixture forward
bite is physically impossible (the chain-head read dies before any
stamp could land). The daemon's birth-readiness panel is wired: enabled
+ unknown paints RED with the reason; `LatchBlocked` reads as "joins
but latch blocked".

### v7.3 — gate round 20's executed findings, closed

Round 20 executed adversarial controls against the first S1 code and
failed A/B/D/E (C passed). Closed in code the same day; the protocol
records what changed and why, so the next reader does not re-derive it:

- **Census roots now include `scripts/`** — the owner birth ceremony
  performs the re-birth-prevention anchor read, and a census blind to the
  birth transaction is not a census of birth-state readers. The daemon's
  own import form (`from core.memory import birth_phase`) is recognized;
  `phase_for_stamp` is an accessor; unscannable files fail the census
  loudly instead of vanishing as empty results. The frozen digest in §9 is
  superseded by the derived artifact's current digest (the JSON itself is
  authoritative; §9's literal is historical).
- **The resolver's structural check is the full T6 fingerprint** — exact
  table/trigger/index sets, migration rows against the shipped files'
  frozen digests, genesis projection, chain verification to head, and
  head == tip. Round 20 showed eight of nine T6 mutations passing a
  name-only check; all nine now flip to `unknown, structural`, and
  `PRAGMA quick_check`'s *result* is checked, not merely executed.
- **`resolve()`'s joined branch raises `LatchBlocked`** rather than
  returning `lived, joined`. Answering `lived` without latch creation is
  the latch-dependent truth claim §12.13 blocks; T1 cells 13–14 are
  therefore unexecutable until the latch lands, by design.
- **Reason `"dormant"`** is returned only when `MAEZ_S1_PHASE_TRUTH` is
  unset. It is deliberately outside §9's frozen twelve: T1 runs enabled,
  and a dormant answer must be distinguishable from a classification.
- **Dormant defaults are per-consumer** (`dormant_default`): audit_log's
  legacy default was the literal `gestation` (Python constant /
  SQL DEFAULT), while private_thoughts and memory_manager defaulted to
  `current_phase()`. Dormant parity reproduces each consumer's own legacy
  answer. On the current unborn ledger these coincide.
- **Authority is at the sinks**: `MemoryManager.store` revalidates a
  caller-supplied phase pulled from free-form metadata (round 20's
  executed overwrite witness), and `PrivateThoughts._insert_thought*`
  gate directly so the public wrappers cannot be bypassed.
- **`AuditLog._initialize` normalizes NULL phases on every open**,
  idempotently, per §10's ruling — not only when the column is added.

### v7.2 correction — the census was derived, and this table inherited its errors

`core/memory/s1_census.py` now derives the census by execution
(`docs/superpowers/specs/2026-08-22-theme2-census-correction.md`). Eight of
the frozen census's ten writer entries did not resolve to a real construct,
and this table was built from the same authoring. Corrected above:
`_migration_null_normalize` does not exist — the behaviour §10 literalizes
is inline in `AuditLog._initialize`; `end_direct_edit_session` is a real
writer that was omitted; the `@line` suffixes are dropped in favour of
qualnames, which is what T4 actually compares.

**`AuditLog.record` is not a phase writer, and that is a hole in the design
rather than a typo in the table.** It never names the column
(`audit_log.py:233-341`). Its rows are stamped `'gestation'` by the SQL
column default at `audit_log.py:113`:

```sql
memory_phase         TEXT    DEFAULT 'gestation',
```

**A stamp supplied by the database cannot be refused by application code.**
With the resolver reading `unknown`, `record()` still writes a row asserting
`gestation`, because SQLite fills it in. That is precisely the A6 defect
Theme 2 exists to close — phase degrading to `gestation` — sitting inside
the audit store's own schema, and no consumer-refusal wiring in Python can
reach it.

The two candidate closures, neither adopted here:

1. Make `record()` name the column explicitly and gate it like its
   siblings. Cheapest; leaves the default in place for any other writer.
2. Drop the column default in a migration so an unstamped insert is a NULL
   the resolver can distinguish from a claim. Correct, but it is a schema
   change to a live store with 506 rows, and it interacts with §10's ruling
   that pre-S1 legacy rows are gestation by census fact.

This must be ruled before T3 can pass, and it is recorded rather than
decided. Note the asymmetry it creates today: the direct-edit methods
default in *Python* (`memory_phase: str = MEMORY_PHASE_GESTATION`), which is
refusable by changing the default; `record()` defaults in *SQL*, which is
not.

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

## 9. v3 amendments — round-9 MUST-CLOSE items, closed

- **Resolver API, pinned now**: `core.memory.birth_phase.resolve()`
  → a `PhaseResult` namedtuple `(phase, reason)`; `phase ∈
  {'gestation','lived','unknown'}`; `reason` is a machine string from
  a frozen enum (`absent`, `uninitialized_empty`, `structural`,
  `corrupt`, `meta_absent`, `joined`, `join_failed`, `latch_conflict`,
  `latch_torn`, `latch_foreign`, `rewind`, `io_error`). T1 cells
  assert BOTH fields; the exact command is
  `python3 -c "from core.memory.birth_phase import resolve; r=resolve(); print(r.phase, r.reason)"`.
- **Latch writer API, pinned now**: `core.memory.birth_latch.advance()`;
  published segments are `<latch_dir>/segment-%06d.jsonl`; the temp
  form is `<name>.tmp`; sentinel files for T2 crash points are
  `<latch_dir>/.crash-<point>` touched immediately before the point.
  Health rows are `SELECT COUNT(*) FROM health_signals WHERE kind='phase_rewind'`
  in the S1 health store (airlock path; schema shipped with S1).
- **S1 activation, pinned now** *(v6.6, gate round 17 M(iii))*: the S1
  resolver is dormant unless `MAEZ_S1_PHASE_TRUTH=1`. With the flag
  unset, `core.memory.birth_phase` keeps its pre-S1 behavior exactly —
  `current_phase()` answers `gestation` for any ledger without a
  readable birth anchor — and `resolve()` may exist but is consulted by
  no consumer. With the flag set, `resolve()` governs and every census
  consumer raises `PhaseUnknownRefusal` on `unknown`. Round 17 was
  right that without a pinned activation mechanism G5 is unspecifiable
  and unexecutable; this is that mechanism, fixed before the code that
  implements it. The flag is already on T5's must-be-unset list, so a
  flags-off run cannot set it by accident.
- **Companion artifacts, committed literal** (digests frozen):
  - census `theme2-s1-census.json` =
    `85276709f632e0cdab98fa877a0ca8ff1a1e164c224d2fec68c2299a1f0a3dc6`
  - replay `theme2-s1-replay.json` =
    `2b9faf616941bb6a0ab6294e1323e2dd73cb57389ab021cc2b868f59109cb420`
  - selectors `theme2-s1-selectors.txt` =
    `7759da99b4cbb500c53276d1b585c7738b3edb209fff94a5971a587ed706b6d4`
- **T4 seeded file, literal bytes** (path `core/_s1_census_seed.py`):

  ```python
  import sqlite3
  PHASE = {"memory_phase": "gestation"}
  def probe(p):
      return sqlite3.connect(p).execute(
          "SELECT value FROM meta WHERE key='birth_event_turn_id'").fetchone()
  ```

- **T6 frozen lists, computed from the executed F-G fixture**:
  - tables = audit_trace_lineage, claim_judgements, claims, meta,
    model_swaps, schema_migrations, turns
  - triggers = claim_judgements_no_delete, claim_judgements_no_update,
    claims_no_delete, claims_no_update, turns_no_delete,
    turns_no_update
  - indexes = idx_claims_extracted_ts, idx_claims_tenant_turn,
    idx_judgements_claim_ts, idx_judgements_provenance,
    idx_judgements_tenant_ts, idx_swaps_tenant_ts,
    idx_turns_audit_trace, idx_turns_chain_position,
    idx_turns_kind_ts, idx_turns_lifecycle_ts, idx_turns_model,
    idx_turns_parent, idx_turns_raw_surface_ts, idx_turns_surface_ts,
    idx_turns_tenant_ts
  - genesis anchor: `turn_id='genesis'`, `chain_position=0`,
    `raw_text='{"event":"genesis","schema_version":1}'`, chain hash
    `d313c6473ea19dbe038d3f2f1d714d1ce8c0a9b8e756ef0d4b1849f8eb09989d`
    (deterministic — verified across independent builds).
  - T6 mutation #9's named trigger: `claims_no_update`.
- **T3 exact invocations**: each census construct is exercised through
  its public entry — `memory_manager.store_telegram(...)` (reaches all
  three stamp sites via the three storage tiers),
  `PrivateThoughts.record_thought(...)` and `record_signal(...)`
  *(corrected in v7 — see the note below)*,
  `AuditLog.record(...)`, `AuditLog.start_direct_edit_session(...)`,
  `AuditLog.log_direct_edit(...)`, `source_awareness` path-gate
  helper, `span_planner.run_consolidation_pass(...)` *(v7.4: the
  previously named `plan(...)` never existed)*, and a production-mode
  `LedgerWriter.write_turn('system_event', ...)`; argument fixtures
  are literal in the harness file committed with the S1 code, whose
  digest is recorded in the run report.

  **v7 correction, gate round 18.** §9's T3 contract named
  `PrivateThoughts.record_secret` and `record_reflection`. **Neither
  method exists.** Verified: `core/infra/private_thoughts.py` defines
  `record_thought` (`:571`), `record_signal` (`:604`) and
  `insert_signal_in_transaction` (`:655`); the census JSON's
  `PrivateThoughts@587/@627/@674` anchors fall inside those three, so
  the *census* was right and only the prose was wrong. T3's invocation
  contract is repointed at the surfaces that exist.

  This is worth recording rather than quietly fixing: §9 was declared
  **BINDING-READY at gate round 11**, and an unimplementable contract
  passed. Review is not execution. It is the same lesson the T5 rounds
  taught from the other direction — the defects that mattered were
  found by *running* controls, not by reading — and it is why T3 must
  be executed against the real APIs before it is called closed.

  Heartbeat readers
  (`lean_idle_heartbeat@295`) are readers of stored values, not
  stampers: censused (see census JSON `readers_of_memory_phase_values`)
  and exercised read-only in T3's positive control.

## 10. v4 amendments — round-10's six literals, closed

- **T1 reasons per cell** (phase, reason): 1 `gestation,absent` · 2
  `unknown,latch_conflict` · 3 `gestation,uninitialized_empty` · 4
  `unknown,latch_conflict` · 5 `unknown,structural` · 6
  `unknown,structural` · 7 `unknown,structural` · 8
  `unknown,structural` · 9 `unknown,corrupt` · 10 `unknown,corrupt` ·
  11 `gestation,meta_absent` · 12 `unknown,latch_conflict` · 13
  `lived,joined` · 14 `lived,joined` · 15 `unknown,join_failed` · 16
  `unknown,join_failed`. Latch variants: torn `unknown,latch_torn`;
  corrupt `unknown,latch_torn`; stale-ahead `unknown,rewind`;
  foreign-a/b `unknown,latch_foreign`.
- **T2 latch line schema, frozen**: each segment line is canonical
  JSON (sorted keys, compact separators, UTF-8, trailing `\n`) with
  exactly the keys `{"birth_turn_id","chain_head_hash",
  "chain_position","kind","observed_at","pid"}`, `kind ∈
  {"advancing","committed","observed"}`. The repaired mate line is
  byte-identical to the `advancing` line except `kind:"committed"`
  and its own `observed_at`; the report quotes both lines verbatim.
- **T3 `_migration_null_normalize`** *(v7.4: this method never existed —
  the behaviour lives inline in `AuditLog._initialize`, which now
  normalizes on every open; the ruling below stands, re-addressed to the
  real construct)*: invoked only via
  `AuditLog.__init__` against a legacy fixture (audit DB with 3 rows,
  `memory_phase NULL`). Ruling recorded: pre-S1 legacy rows are
  gestation **by census fact** (all 506 live rows are gestation-era),
  so normalization is historical annotation, not a fresh stamp — it
  proceeds even when the resolver reads `unknown`, is idempotent
  (second open changes zero rows), and never touches rows written
  after the migration ran. Expected outcome: 3 rows → `gestation`,
  rerun delta 0, and a post-migration insert during an `unknown`
  window still refuses per §4.
- **T4 census command, pinned**:
  `python3 -m core.memory.s1_census --repo . --expected docs/superpowers/witness/theme2-s1-census.json`
  — walks the §5 roots with `ast.parse` (interpreter-pinned),
  normalizes each hit to `path::qualname` (falling back to
  `path::@line` where the write is module-level), sorts, and diffs
  exactly against the expected JSON. Exit 0 on equality; exit 1
  naming every asymmetric difference.
- **T5 baseline archive, pinned**: path
  `docs/superpowers/witness/theme2-s1-baseline.tar.zst`; produced by
  driving the replay manifest once against pre-S1 HEAD flags-off in
  the airlock; its sha256 is added HERE by a later protocol amendment
  committed **before** the first S1 code commit — the ordering, not
  the timing, is the binding rule, and the S1 gate checks the
  amendment predates the code in history. *(Corrected in v6.1 per gate
  round 12 item G: this clause originally named "v5", but v5 was
  consumed by T2's mate-line amendment at `64d4cbb`. The digest
  amendment is **v7**.)*
- **T6 mutation 6, executable form** (corruption does not respect
  triggers): `DROP TRIGGER turns_no_update; UPDATE turns SET
  raw_text = raw_text || 'x' WHERE chain_position = 0;` — two
  statements, applied to the mutation copy only. The validator must
  return `unknown` on BOTH counts: the genesis projection mismatch
  and the now-missing trigger name (double-verified single mutation).

## 11. v5 amendment — T2's mate-line bytes, exactly

The repaired mate line is **byte-identical to the `advancing` line
with exactly one difference**: the value of `"kind"` is `"committed"`
instead of `"advancing"` — including the SAME `observed_at` (the
commit's own time, which the advancing line already carries; the
repair adds no new claim about when the commit happened). The
*repair event itself* is recorded as a third line, `"kind":"observed"`,
whose `observed_at` is the harness-injected repair clock (an integer
named in the T2 run script) and whose other five keys are copied
byte-identically from the mate line. All three lines' full byte
content is therefore determined by the fixture plus the injected
clocks; the report quotes all three verbatim and diffs mate-vs-
advancing to show exactly the one differing key.

## 12. v6 → v6.3 amendment — T5's execution model, closed against the pre-execution audit and gate rounds 12, 13 and 14

Round 10 pinned T5's *artifact* (path) and round 11 pinned its
*ordering* (digest amendment precedes the first S1 code commit).
Neither pinned how the run executes. The pre-execution audit
(`docs/superpowers/specs/2026-08-22-theme2-t5-airlock-audit.md`) found
three facts that make §6 unexecutable as written; **gate round 12**
(`-gate-round12.md`) then found six defects in v6's answer. This
section is the closed form. It is authored **before any T5 run and
before any S1 code exists**, so nothing here is tuned to an outcome.

Owner rulings taken at audit time: containment approved subject to a
gate round; hermetic (no network); pre-registered projection; the live
daemon stopped for the run. Round 12 ruled **T5 must not run** until
items A/B/C/D/E/G closed; v6.1 closes them, and the run remains barred
until a further gate says otherwise.

### 12.0 What T5 measures, and why v6.5 changed it (round-16 finding L)

Five gate rounds hardened T5's comparator. Round 16 was asked whether
the witness was worth its cost and whether it measured the right thing,
and answered that it was **over-specified and under-discriminating**.
That finding was verified on this host before it was acted on:

```
legacy current_phase() per fixture — the flags-off behavior T5 must preserve
  F-G healthy    -> gestation
  F-P partial    -> gestation      ← S1 must say unknown
  F-E 0-byte     -> gestation
  F-D2 corrupt   -> gestation      ← S1 must say unknown
  F-A absent     -> gestation
```

`core/memory/birth_phase.py:38-66` returns `gestation` for **every**
ledger that lacks a readable birth anchor — absent, empty, half-built,
corrupt alike. That is precisely the defect S1 exists to fix (design §5,
ND13). And T5's fixture was a **healthy** ledger, which is exactly where
the legacy resolver and S1 **agree**: both answer `gestation`.

So T5 as specified could not tell a dormant S1 from an accidentally
always-enabled one. Two runs would match, the projection would report
identity, and the witness would pass without ever proving the guard
exists. Byte-level invariance of a store that looks the same either way
is not a dormancy proof.

**What v6.5 changes, on the owner's ruling:**

1. **A discriminating fixture is added.** The replay also runs against a
   `partial` ledger — migrations 0001–0002 only — where legacy and S1
   must **diverge**: legacy stamps `gestation`, S1 must read `unknown`
   and every consumer must refuse. Flags off must reproduce the legacy
   stamps exactly; once S1 exists, a forced-on run must **not**. That
   divergence is the dormancy proof.
2. **The gate narrows to what S1 needs.** The kill clauses are: no latch
   directory; the ledger main file unchanged; the `memory_phase` stamp
   census identical per store on **both** fixtures; record counts
   identical; and — once S1 exists — the forced-on run *must* differ.
3. **The byte projection is demoted to forensic evidence.** It is still
   computed, recorded and archived, and its self-test still runs; it is
   no longer the gate's authority. It kept producing defects because it
   was measuring physical layout, which is not the invariant of
   interest.
4. **The archive is still produced and its digest still committed in
   v7, before the first S1 code commit.** Round 11's ordering rule is
   honored exactly; only the archive's evidentiary weight changes, from
   comparison basis to documentation of what the pre-S1 store tree was.

What T5 keeps unchanged: the airlock and its self-test, the path
checks, the live-tree probes, the hermetic ruling, the positive
controls, and one real `handle_message` exchange through production
code rather than a stub.

### 12.1 The findings, as binding constraints

From the audit:

- **F-A** `memory/memory_manager.py:45` pins
  `BASE_DB = Path("/home/rohit/maez/memory/db")`; `_make_client()`
  (`:597`) `mkdir`s and opens Chroma there, and
  `MemoryManager.__init__` invokes it for raw (`:1499`), daily
  (`:1841`) and core (`:2066`) at `:1412`. **`memory_manager` itself
  exposes no environment override for it**, and neither does any
  production caller. *(v6.1 correction, round 12 item A: v6 said "no
  environment override anywhere in the repo", which is false —
  `scripts/recall_flip_eval/sandbox.py` monkeypatches the module
  global at `:121`/`:124`, guards it at `:178`, and restores it at
  `:370`/`:386`. The accurate claim is that the module and every
  production path have no intrinsic override; a specialized harness can
  rebind the global. That is why T5 uses containment rather than
  imitating the sandbox's rebind: a monkeypatch covers the one literal
  someone remembered, and the audit found 54 module-global absolute
  paths.)*
- **F-B** Every store on the path stamps `uuid4()` and a wall clock
  (`memory_manager.py:1499`, `1598`, `1841`, `2066`;
  `private_thoughts.py:1099`; `audit_log.py:245/444/513/568`;
  `writer.py:353`). Raw byte equality between two runs is impossible.
- **F-C** The brain, the airlock's starting state, and the live
  daemon's concurrency were unspecified.

From round 12: the launch boundary was not total (B), B1's stated
reason was false (C), the projection was not total and admitted real
false passes (D), the volatility classifier was not deterministic (E),
and §10 named the wrong amendment version (G). Round 12 item **F
passed**: no census construct is reachable only on a successful-brain
path, so the hermetic ruling costs no coverage.

### 12.2 Containment replaces redirection (closes F-A and round-12 B)

The run executes inside `bwrap` with the live tree **read-only** and
airlock directories bound over exactly the writable targets. The live
absolute path still resolves — so a module-global literal is caught by
construction — and any path the bind set did not anticipate fails
`EROFS`, loudly.

The wrapper is `docs/superpowers/witness/theme2_s1_airlock.sh`,
sha256 recorded in the run report; `theme2_s1_airlock.sh <dir> --argv`
prints the frozen argv, which the report quotes verbatim. Its shape:

```
bwrap --ro-bind / /
  --tmpfs /home/rohit
  --ro-bind /home/rohit/maez /home/rohit/maez
  --bind <A>/maez/memory        /home/rohit/maez/memory
  --bind <A>/maez/logs          /home/rohit/maez/logs
  --bind <A>/maez/.cache        /home/rohit/maez/.cache
  --bind <A>/home/.config/maez  /home/rohit/.config/maez
  --bind <A>/home/.cache/chroma /home/rohit/.cache/chroma
  --tmpfs /tmp --tmpfs /run --tmpfs /var/tmp
  --proc /proc --dev /dev
  --unshare-net --unshare-pid --die-with-parent
  --clearenv
  --setenv HOME /home/rohit
  --setenv PATH /home/rohit/maez/.venv/bin:/usr/local/bin:/usr/bin:/bin
  --setenv VIRTUAL_ENV /home/rohit/maez/.venv
  --setenv PYTHONDONTWRITEBYTECODE 1
  --setenv PYTHONHASHSEED 0
  --setenv LANG C.UTF-8  --setenv LC_ALL C.UTF-8
  --setenv TZ America/Chicago
  --chdir /home/rohit/maez
```

Round-12 and round-13 gaps, closed:

- **`--tmpfs /home/rohit` before the repo bind, plus `--tmpfs /run` and
  `--tmpfs /var/tmp`.** `--unshare-net` does not block filesystem Unix
  sockets, and read-only-mounting a socket pathname does not stop an
  outside process from acting on it. `/run` alone was not enough: a
  census found **142 socket pathnames under `/home/rohit`** — IBus,
  the keyring, Codex — still reachable. A tmpfs over the home
  directory, with the repo and the two airlock subpaths bound back on
  top, takes the count to **zero on the whole root device**, verified
  inside the namespace. *(v6.2, round 13 item B.)*

- **The airlock is acquired atomically and held under an exclusive
  lock.** v6.2 checked emptiness and then created the directory, which
  two concurrent invocations could both pass, and it canonicalized the
  supplied path with `readlink -f` *before* validating — erasing the
  evidence that a component was a symlink. v6.3: the literal path must
  equal its own canonicalization and its parent must not be a symlink;
  acquisition is a bare `mkdir` (one syscall, fails if the path exists
  at all); the run then holds `flock` on a lock file inside the airlock
  for its whole life; later commands of the same run opt in explicitly
  with `T5_REUSE_AIRLOCK=1`, which requires the claim marker this run
  wrote. Verified: a second invocation without the opt-in refuses, and
  a symlinked parent refuses. *(v6.3, round 14 item B.)* The wrapper
  also refuses a symlinked airlock, a parent it does not own, and any
  of the five bind sources that resolves elsewhere. Without this a stale overlay could carry store bytes into
  something called a baseline, and a symlinked bind source could
  redirect the writable mount out of the scratch tree. *(v6.2, round 13
  item B.)*

- **`TZ` is a constant, not a default.** An inherited `T5_TZ` would
  have silently moved the pin. Changing the zone is a protocol
  revision, not an invocation choice. *(v6.2, round 13 item B.)*
- **`--clearenv` plus eight explicit `--setenv` pairs** (nine variables
  observed at entry — the shell adds `PWD`). `PYTHONHASHSEED=0` and the
  pinned `TZ` remove two determinism axes the manifest exposes ("what
  day is it today").

  **But `--clearenv` does not survive the import, and the protocol now
  says so.** Importing the daemon runs the shipped secrets loader
  (`maez_daemon.py:34` → `secrets.load_ordinary_config_for_process`,
  `secrets.py:150`), which repopulates `config/.env` into `os.environ`
  exactly as it does in production — **10 `MAEZ_*` names** on this
  host. That is correct behavior to exercise, not a leak to suppress,
  and v6.1's "exactly nine variables, nothing MAEZ-shaped" was simply
  false about the environment that executes `handle_message`. What T5
  asserts is the narrower true thing §6 actually requires: **no
  phase/S1 flag is set.** The frozen list is
  `MAEZ_LEDGER_WRITES`, `MAEZ_BIRTH_PHASE`, `MAEZ_BIRTH_LATCH`,
  `MAEZ_S1_PHASE_TRUTH`; S1's own flags join it when they exist.
  Verified on this host: `MAEZ_LEDGER_WRITES` is **not** among the
  `config/.env` names, so flags-off holds.

  **A second class of name matters just as much**: `MAEZ_LEDGER_DB_PATH`,
  `MAEZ_HOME`, `MAEZ_DATA`, `MAEZ_CONFIG`, `MAEZ_CACHE` do not gate
  writes — they select *which store* is read and written.
  `core.memory.birth_phase.default_ledger_path()` honors
  `MAEZ_LEDGER_DB_PATH` and then `core.infra.paths.memory_dir()`, which
  honors `MAEZ_DATA`/`MAEZ_HOME`, and the ordinary config loader can
  repopulate any non-secret name after `--clearenv`. They are absent
  from this host's `config/.env` today, but absence is not a guarantee:
  the driver now refuses unless each is either unset or resolves
  **inside the overlay**, and it records
  `default_ledger_path()`'s actual value rather than inferring it.
  *(v6.3, round 14 item B.)* The driver records the
  environment **twice** — at entry and after the import — and refuses
  to continue if any listed flag is set. Values are recorded only for
  a declared non-secret allowlist; everything else is recorded by
  **name only**, because `config/.env` carries credentials and a
  witness report is a committed file. *(v6.2, round 13 item B.)*
- **The `memory/` overlay must be seeded with the package sources.**
  The repo's `memory/` directory is **both a Python package and the
  data directory**: it holds `memory_manager.py`, which
  `daemon/maez_daemon.py:70` imports, alongside `memory/db/` and the
  sqlite stores. Binding an empty airlock directory over it hides the
  package and the driver cannot import the reply machinery at all —
  verified: `ModuleNotFoundError: No module named
  'memory.memory_manager'`. The wrapper therefore installs exactly the
  files listed by `git ls-files memory/` (10 files at this commit) into
  the overlay and records each one's sha256 in
  `<A>/maez/logs/seeded-sources.txt`. They are **code, not store**: the
  projection excludes them from the store tree by that manifest, and
  compares the manifest itself between runs.
- **No Maez code runs outside the namespace.** Host-side shell setup —
  `mkdir`, `git ls-files`, copying and hashing the seed sources and the
  model cache — necessarily runs outside, and v6.2's "nothing runs
  outside" was the wrong word for it *(v6.3, round 14 item B)*. What is
  true, and what matters, is that no Maez module is imported and no
  store is opened outside the boundary. v6 migrated the ledger before
  namespace entry, which left a whole Python startup — imports,
  `site`/`.pth`, bytecode, inherited descriptors — outside the boundary
  the protocol claimed was total. The migration is now the driver's
  first act *inside* the namespace, after the containment proof.

**Bind-set discovery is iterative and recorded.** Any `EROFS`
encountered is a *finding*: the report lists every path that failed
read-only, and either the bind set grows (recorded, with the reason) or
the run stops. A read-only failure is never worked around by loosening
`--ro-bind /home/rohit/maez`.

**Containment self-test, run immediately before the replay, output
quoted verbatim in the report.** Eight assertions, all currently
passing on this host: (1) a write to `/home/rohit/maez` fails `EROFS`;
(2) a write to `/home/rohit/maez/memory` succeeds; (3) the namespace's
TCP table is empty; (4) **zero socket pathnames exist on the root
device and under `/home/rohit`, and `/run` is empty**; (5)
`import memory.memory_manager` succeeds **and** `BASE_DB` resolves to
`/home/rohit/maez/memory/db`, i.e. into the overlay; (6) the entry
environment is exactly the nine declared names and none is
`MAEZ_`-shaped; (7) the probe exists in the airlock; (8) neither probe
exists in the live tree afterwards. Any deviation kills the run before
the manifest is touched.

The driver re-proves containment **from inside**, before importing a
single Maez module, because constructing `MaezDaemon` builds
`MemoryManager`: repo read-only, `memory/` writable and not the live
579 MB store, `127.0.0.1:8080` unreachable, no `MAEZ_*` set. Verified
to refuse outside the namespace, before any import, leaving no trace.

### 12.3 Hermetic (closes F-C.1; round-12 F confirms the cost)

`--unshare-net`. The LLM at `127.0.0.1:8080`, the judge at `:8081`, and
`maez-searxng` are unreachable; `llm_client.chat` raises `BackendError`
and the reply path takes its fallback. Round 12 verified that both the
successful-synthesis branch (`maez_daemon.py:8937`) and the
`BackendError` branch (`:8958`) rejoin before the common storage tail
(`:9676`), so **no census construct is reachable only on a
successful-brain path** and the hermetic ruling costs no coverage.

Round 12 also established the honest scope of the replay: it exercises
**1 of the 13 census constructs** (`MemoryManager.store_telegram`). The
other 12 are T3's job, via the public entries §9 pins. T5 is a
store-tree invariance witness, not a census witness, and the report
says so rather than implying breadth it does not have.

The report records that the brain was unreachable and quotes one
fallback reply verbatim.

### 12.4 Starting state (closes F-C.2)

The airlock starts with **no store data**: only the seeded package
sources of §12.2. `memory/ledger.db` is created by
`core.ledger.migrate.run` as the driver's first in-namespace act, and
its sha256 plus its `ledger.db*` file set are recorded before the
replay. Every other store is created by the code under test on first
write. No live store is copied — a baseline archive committed to git
must never carry Maez's real memories.

### 12.5 The live daemon (closes F-C.3)

`maez.service` is stopped for the duration of the run and restarted
after, by the owner's ruling. The report records the stop time, the
restart time, and `systemctl --user is-active maez.service` before and
after. Belt-and-braces on top of containment, not a substitute.

### 12.6 The driver

`docs/superpowers/witness/theme2_s1_t5_replay.py`, sha256 recorded in
the report. It verifies the manifest digest
(`2b9faf61…b420`), constructs `MaezDaemon()`, and calls
`handle_message(text, source="UI")` once per interaction in manifest
order — the manifest's `source: "UI"` names that entry point. It sets
no `MAEZ_*` flag. Its report goes to `logs/`, which §12.7 excludes from
the store tree, so writing it cannot perturb what T5 compares.

**The manifest's `at` field is ordinal, not a clock.** Its values
advance by 60 s, but nothing on the `handle_message` path accepts an
injected time — every store stamps `time.time()` directly — so the
calls run back-to-back at real wall-clock time and `at` fixes only the
order. v6.1 left this unstated, which would have let two baselines
agree on a timing regime the manifest appears to describe (round 13,
finding I.3). Declaring it is the honest closure: T5 is not a
timing witness, and a future protocol revision that wants one has to
add an injection point to the path first, not reinterpret this field.

### 12.7 The store tree, and what the archive contains

**Store tree** = `<A>/maez/memory/**`, minus the seeded package sources
named in `logs/seeded-sources.txt`. The archive is taken from the
**healthy** fixture's run `a`; the partial fixture's tree is recorded in
the run report but not archived, since its role is the discriminator's
stamp census rather than a byte baseline.
**Excluded**: `<A>/maez/logs`, `<A>/maez/.cache`, `<A>/home/**` (the
167 MB `ONNXMiniLM_L6_V2` cache, a read-only asset the hermetic run
cannot re-download), and the seeded sources.

The archive `docs/superpowers/witness/theme2-s1-baseline.tar.zst` is
the store tree, `tar` with sorted member order, numeric owner, mtimes
normalized to `0`, `zstd -19`. If it exceeds 25 MB the run stops and
the owner rules on placement before anything is committed.

### 12.8 The invariance projection (closes F-B and rounds 12/13/14 D and E)

Raw byte equality is replaced by a projection fixed **here**, before
any S1 code exists, and implemented by
`docs/superpowers/witness/theme2_s1_t5_projection.py` (sha256 in the
report), which is self-tested against each clause before it is pointed
at a real baseline.

**The gate, v7 — cut to the discriminator.**

Gate round 18 executed synthetic controls against v6.6's gate and found
it **failed an honest run**: G3 demanded stamps from stores this T5 path
never writes. `MemoryManager.store_telegram` (`memory_manager.py:1576`)
adds to `raw` and nothing else, and T5 reaches exactly one of the
thirteen census consumers — so daily, core, `private_thoughts` and
`audit_log` are *legitimately* empty, and a gate that rejects that is
broken. It also passed a minimal forged forced-on report, a report with
no phase probe, and a document-plus-metadata mutation.

On the owner's ruling the gate is now four kills plus the
discriminator. Everything else — the byte projection, HNSW layout,
embedding vectors, cross-store record counts, the volatile derivation —
is **forensic**: computed, recorded, archived, and never deciding.

- **K1 — the ledger main file is unchanged**, per the digests the driver
  records post-migration and post-replay. Read-only opens and their
  `-wal`/`-shm` sidecars are expected (§12.8 B4).
- **K2 — no latch artifact** anywhere on either fixture.
- **K3 — the positive controls passed** on every flags-off run, with the
  underlying numbers re-derived rather than the `PASS` label trusted:
  no interaction raised, none missed the storage tail, at least one
  returned, at least one collection grew.
- **K4 — no store landed outside the projected tree.** The driver sweeps
  every writable root — `logs/`, `.cache/`, `~/.config/maez`,
  `~/.cache/chroma`, `/tmp`, `/run`, `/var/tmp` — and detects SQLite by
  its 16-byte magic header, not by file extension, because a selector
  can name an extensionless path.
- **D — the discriminator.** *(EXECUTED 2026-08-23: **PASS** — see
  `theme2-s1-discriminator-report.md` and the committed verdict JSON.
  Flags-off matched the pinned census on both fixtures; forced-on read
  `unknown, structural`, refused 20/20 with typed, named refusals, grew
  nothing, stamped nothing.)* Both fixtures are required. Flags-off must
  read `gestation` on the **partial** fixture — the legacy behavior T5
  exists to preserve — and, once a baseline is pinned, each fixture's
  census must equal it **exactly**. The census is narrow on purpose:
  the resolver's answer plus the stamps of the one store this path
  writes.

  Once S1 exists, a **forced-on** run is mandatory and must flip. It is
  bound on four counts, because round 18 passed a forgery that was
  bound on none: it must be against the **partial** fixture; its
  recorded post-import environment must carry
  `MAEZ_S1_PHASE_TRUTH=1`; `resolve()` must return `unknown`; and it
  must carry `PhaseUnknownRefusal` evidence. Its census must differ
  from the flags-off census and must contain no `gestation` stamp.
  **A T5 whose discriminator does not flip is a failed T5**, however
  cleanly K1–K4 pass, because it means the guard is not there. The gate
  refuses a `not-applicable` answer the moment `birth_phase.resolve`
  exists.

**Schema is fail-closed.** A missing key, a malformed phase probe, an
empty census, or an exercised store with no stamps fails before any
clause is evaluated. Absent evidence is not evidence.

**The gate has its own self-test**, `theme2_s1_t5_gate_selftest.py`, 21
cases, run by the orchestrator *before* the daemon is touched. Round 18
was right that a sole authority without one is a blocking gap — the
first version of the gate would have failed every honest baseline while
passing four forgeries, and nothing in the witness would have said so.
Every case is a defect a gate round reproduced or a mutation the gate
must bite on, and the honest-run case is first.

**§6's frozen selector suite is restored to the orchestrator.** It was
required by the protocol and absent from the executable *(gate round 18
finding P)*.

### The executed baseline (v7.1 — the digest amendment)

T5 ran to completion at HEAD `db0d65e`, orchestrator exit **0**, gate
verdict **PASS** (K1–K4 all PASS; `D_discriminator: NOT-APPLICABLE`,
the correct pre-S1 answer). Full evidence:
`docs/superpowers/witness/theme2-s1-t5-run-report.md`.

| Artifact | sha256 |
|---|---|
| `theme2-s1-baseline.tar.zst` | `328f98d4d9cb222e437e97a74b22cee46a4cac9114d7f3875bb56def0b445216` |
| `theme2-s1-baseline-census.json` | `9e4c145b07fc6d000f8ed9c6c1739c71c711e99b3409dc198e2a03ea78eef21b` |

The census carries `bound_archive_sha256` so the pair cannot drift.
The pinned baseline, both fixtures, flags off:

```
current_phase: gestation
chroma::raw {"gestation": 20}; daily, core, private_thoughts,
audit_log all empty — honestly, since store_telegram writes raw only.
```

**Round 11's ordering rule is satisfied by this amendment**, and its
weight is stated plainly: the archive is *forensic* — it documents what
the pre-S1 store tree was. The gate's authority is the census and the
four kills, not byte equality with the tarball. That is the owner's
ruling after gate round 16.

**What this baseline does not prove.** It does not show the S1 guard is
dormant, because no S1 code exists: on a healthy ledger legacy and S1
agree, and the partial fixture's `gestation` is what a *correct* S1
must later refuse to say when forced on. Dormancy is proven by the
forced-on run, which the gate makes mandatory the moment
`birth_phase.resolve` exists.

**The pinned census.** The gate emits the census it observed, and the
orchestrator publishes it to
`docs/superpowers/witness/theme2-s1-baseline-census.json`, digest
committed here beside the archive's. Without a durable basis a later
flags-off run has nothing exact to match and G3 decays into "some
gestation stamp exists" *(gate round 17, M(iv))*.

**Forensic clauses (recorded, not gating).** Any difference here is
reported in the run report and ruled on; it does not by itself fail
T5. This is the demotion round 16 recommended and the owner adopted.

- **B1** — the ledger's **main file** sha256 after the replay equals its
  post-migration sha256 from §12.4. The digest is read from the sqlite
  projection's recorded `file_sha256`; `ledger.db` is a sqlite store,
  not a blob, and v6.1's comparator looked it up in the blob table and
  therefore always reported it absent *(v6.2, round 13 item D)*. *(v6.1 correction, round 12 item C:
  v6 justified this with "the ledger is never opened", which is false.
  `try_write_turn` does return `None` before constructing a writer
  (`writer.py:574`) and model-reply persistence returns before probing
  (`model_reply_persistence.py:165`), so no **write** path runs — but a
  tail-reaching `handle_message` calls the evidence-envelope builder
  (`maez_daemon.py:7788`), which opens the ledger **read-only** at
  `envelope_builder.py:268` and again at `recent_turns.py:97`.
  Empirically verified on this host: those read-only opens create
  `ledger.db-wal` and `ledger.db-shm` and leave the main-file digest
  unchanged. B1 asserts the main file; the sidecars are named in B4.)*
- **B2** — no `birth_observed/` directory, no `segment-*.jsonl`, no
  `*.tmp` under any latch path anywhere in the airlock.
- **B3** — four canonicalized path sets compared independently: sqlite
  files, other files, sidecar files, seeded sources. Canonicalization:
  a path component matching
  `^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$`
  becomes `<uuid:N>`, N its ordinal in first-appearance order under a
  lexicographic walk (Chroma names segment directories with fresh
  UUIDs). A path whose name varies by anything else is fail-closed.
  The mapping is **injective**: a literal component that could be
  mistaken for a placeholder is escaped as `<lit:...>`, and
  `uuid_map_size` is compared. *(v6.4, round 15 item D: a real UUID
  directory and a directory literally named `<uuid:0>` both
  canonicalized to `<uuid:0>`, so one could be substituted for the
  other.)*
- **B4** — `-wal` / `-shm` sidecars: **presence compared, bytes not.**
  They are checkpoint-timing artifacts, and their existence is expected
  per B1. Naming them explicitly is the point: v6 left them
  unprojected, which is a hole, not a decision.

  **This is not a licence to ignore WAL contents.** v6.1's comparator
  opened each store with `immutable=1`, which tells SQLite to ignore
  the write-ahead log — so a committed change living only in the WAL
  was invisible while sidecar presence compared equal. Every store is
  now copied **with its sidecars** to scratch and opened normally, so
  the WAL is applied before anything is read. Verified: a row committed
  only in the WAL now kills on `P1.count`. *(v6.2, round 13 item D.)*

- **B3.dirs / B3.modes / B3.irregular** — the walk covers **every
  entry**, not only regular files: the directory set and every entry's
  mode are compared, and anything that is neither a regular file nor a
  directory (symlink, fifo, socket, device) is reported and kills.
  v6.2 walked `is_file()` only, so an empty directory, a mode change,
  or a file replaced by a symlink was invisible. *(v6.3, round 14
  item D.)*

- **B5** — seeded package sources are compared **by digest**, not by
  path name. v6.1 compared only the names, so a changed source file
  inside the overlay would have passed. *(v6.2, round 13 item D.)*

**Forensic, continued. Ordinalization, never dropping.**

Round 12's decisive objection: v6 *dropped* volatile columns, so any
change inside one was invisible — flags-off S1 could replace every
timestamp in the tree with epoch zero and the comparison would still
report equality. The fix is to normalize, not discard:

- **P1** — per sqlite store: `sqlite_master` (name, type, sql) identical;
  `user_version`, `application_id`, `page_size`, `journal_mode`,
  `encoding` identical (an unprojected pragma change is a real
  behavior change); per table, the column list and row count identical;
  per table, the **normalized row multiset** identical, where
  normalization is:
  1. a **time**-classified column's value becomes its dense rank among
     the column's sorted distinct values — preserving ordering,
     uniqueness and monotonic structure, so a collapse to one value
     changes the rank structure and is caught;
  2. rows are sorted by their **stable key** = the non-volatile column
     values plus the time ranks. This is the row-alignment procedure:
     it needs no row identity and is identical in both runs whenever
     the stable content is;
  3. a **uuid**-classified column's value becomes a **per-database**
     first-appearance ordinal assigned in that sorted order — per
     database, not per column, so a scrambled foreign-key relationship
     shows up as an ordinal mismatch.
  A table the projection cannot normalize (row cap exceeded, read
  error) is a kill, never a skip; so is any store whose projection
  recorded an `error` — v6.1 stored the error as data, and two matching
  error objects compared equal and passed *(v6.2, round 13 item D)*.

  Three further clauses close the false passes round 13 reproduced
  *(all v6.2, item D)*:
  - **P1.class** — every value of a volatile field is revalidated
    against its **frozen class at compare time**. v6.1 trusted the
    baseline classification blindly, so a single-row time column could
    be rewritten to epoch zero and still normalize to `<t:0>`. Zero is
    outside the frozen window, therefore not time-shaped, therefore a
    kill.
  - **P1.timewindow** — per time field, the multiset of unit domains
    (`unix_s`, `unix_ms`, `iso8601`) is compared. A
    seconds-to-milliseconds rewrite preserves rank and would otherwise
    normalize identically.
  - **P1.collision, fail-closed** — if two rows in a table carrying
    uuid-classified columns share a stable key, uuid ordinal assignment
    is ambiguous: a genuine relationship scramble and a harmless
    relabel look the same, so the table kills rather than being ordered
    by whatever `SELECT *` happened to return. *(v6.3, round 14 item D:
    v6.2 returned a sentinel **string**, so when both sides collided the
    two sentinels compared equal and the comparison passed with
    `kills=[]` — the entire row relationship silently discarded. It now
    raises, and the caller must record a kill. Reproduced and
    re-tested.)*
  - **P1.volatile_unresolved** — a frozen volatile entry naming a store,
    table or column that no longer exists kills. v6.2 ignored it, so
    the literal and the tree could drift apart unnoticed.
  - **P1.nulls** — the per-column NULL count is compared and kills.
- **P2** — computed from `theme2_s1_t5_extract.py`'s output, folded
  into each side's projection with `project --extract` and **compared
  as part of the verdict**. v6.1 specified P2 and shipped an extractor,
  but nothing read it *(round 13 item D)*; v6.2 then read it only when
  present, so two projections that both omitted it compared equal and
  passed. **P2 is mandatory**: a missing extract on either side kills
  *(v6.3, round 14 item D)*. Metadata is **normalized with the same
  grammar as P1** before comparison — uuid- and time-shaped values
  become class placeholders, keys are never dropped — because comparing
  it raw made an honest one-second difference between runs a spurious
  `P2.records` kill *(v6.3, round 14 item D)*. Per collection: record
  count; the sorted multiset of
  `(document, metadata)` under the same normalization; and the
  embedding vectors compared **exactly**. `ONNXMiniLM_L6_V2` is
  deterministic, so a vector difference is a real finding and is
  reported, never loosened to a tolerance. Vector framing is frozen:
  records ordered by `(document, canonical-JSON metadata, canonical-JSON
  record)` — the third key breaks duplicate-document ties — and each
  vector serialized as IEEE-754 little-endian doubles, concatenated,
  sha256.
- **P2b** — every non-database file in the tree compared by sha256, and
  a difference is a **kill**. *(v6 made this a note. An HNSW graph
  rebuilt with a different topology — `data_level0.bin`,
  `link_lists.bin`, `length.bin`, `header.bin` — is a real behavior
  change, and a note is how it would have slipped through.)*
- **P3** — phase-exactness: per store carrying `memory_phase`, the
  multiset of values, killing **independently of P1** so that an error
  in the volatile list can never quietly swallow a phase change.

**The volatility classifier, frozen (closes round-12 E).** A field is
volatile iff its value multiset differs between the two baseline runs.
It is then classified by **shape only** — no field-name rule, because a
name-based rule is exactly the discretion round 12 objected to:

- **uuid-shaped** iff it matches
  `^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$` or
  `^[a-z][a-z0-9_]*-[0-9a-f]{8,32}$` — the two forms the codebase
  actually mints.

  *(v6.5, round 16 item D:* v6.4 still admitted a generic prefix plus
  8–32 hex, and round 16 executed `digest-<32a> → digest-<32b>` through
  the real comparator: classified `uuid`, normalized to `<id:0>` on both
  sides, `IDENTICAL-UNDER-PROJECTION`, `kills=[]`. Excluding bare 64-hex
  protects nothing against prefixed, MD5-shaped or truncated digests.
  The class is now an **exact allowlist** of the three forms the
  codebase mints, each pinned to its construction site —
  `core-<12hex>` (`memory_manager.py:2066`),
  `quiet-<YYYY-MM-DD>-<8hex>` (`:1660`),
  `daily-<YYYY-MM-DD>-<8hex>` (`:1842`) — plus canonical uuid4. Adding
  a form means adding a line and re-freezing.*)

  *(v6.4, round 15 item D, and the most consequential fix of the
  round.* v6.3 admitted any 12–64-character lowercase hex string, so a
  **semantic digest was absorbed as an identifier**: executed control,
  a `content_sha256` changing from `"a"*64` to `"b"*64` was classified
  volatile, normalized to `<id:0>` on both sides, and read
  `IDENTICAL-UNDER-PROJECTION` with `kills=[]`. A digest is not an
  identifier. Bare hex is no longer a class at all; anything that
  varies and is not one of the two minted forms surfaces as a FINDING,
  which is the safe direction — fail toward reporting, never toward
  absorbing.)*
- **time-shaped** iff it is a non-boolean number in `[1600000000,
  2600000000]` (unix seconds, 2020-09-13 .. 2052-06-07) or in
  `[1600000000000, 2600000000000]` (the same window in milliseconds),
  or a string matching
  `^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:?\d{2})?$`.
  A number outside those two windows is **not** time-shaped, whatever
  it is called.
- **Classification covers the UNION of both sides' columns.** A column
  present on only one side is a schema difference and is reported as a
  FINDING, never skipped. v6.3 iterated only side A's columns, so a
  B-only column was never visited — the comparator killed it later
  through `P1.columns`, but the derivation has to agree with the frozen
  contract rather than lean on a downstream clause. *(v6.4, round 15
  item E.)*
- **Classification looks at the values that actually DIFFER** — the
  symmetric difference of the two runs' value multisets — not at every
  value in the column. v6.2 classified the union, so a Chroma-style
  EAV column holding an unchanged `"gestation"` beside differing ISO
  timestamps became a FINDING instead of a time-classified volatile
  field. *(v6.3, round 14 item E; reproduced and re-tested.)*
- **NULL is class-neutral**: it belongs to no shape and classification
  runs over non-NULL values. But **any change in the NULL pattern is a
  FINDING, never a volatile field** — if the differing set contains
  NULL at all, the field is reported, not absorbed. v6.2 classified
  `NULL → UUID` as a uuid volatile field with zero findings, which
  contradicted this same paragraph; the derivation and the prose now
  agree. `P1.nulls` compares the per-column NULL count and kills at
  compare time as well. *(v6.3, round 14 item E.)*
- Every differing non-NULL value in the field must satisfy one class,
  and the same class. A field that differs and satisfies neither is a
  **FINDING**, reported and ruled on, never absorbed. The derivation
  exits non-zero when any finding exists.

**The deferred literal, and why deferring it is still
pre-registration.** The *field list* cannot be enumerated before the
baseline run, because the set of tables the replay creates is not
knowable by reading. The rule and the grammar are frozen here; the
**literal list** is computed from the two baseline runs and frozen in
the v7 amendment, committed with the archive digest and, per round 11,
**before the first S1 code commit**. Round 12 accepted the timing and
the finding-not-absorbed rule; what it rejected was the vagueness, and
the grammar above removes it. Pre-registration is preserved with
respect to the thing under test: the projection is fixed before any S1
code exists.

### 12.9 Report obligations added to §8

The `bwrap` argv verbatim (from `--argv`); the eight-assertion
self-test output; the wrapper, driver and projection-tool sha256s; the
seeded-sources manifest with digests; every `EROFS` path encountered;
the daemon stop/restart timestamps and `is-active` output; the
post-migration `ledger.db` digest and `ledger.db*` file set; the
post-replay digest and file set and the B1 verdict; the
brain-unreachable evidence and one verbatim fallback reply; the archive
digest and byte size; the derived volatile field list with each entry's
class and the evidence for it; every finding from the derivation.

Added in v6.2: the socket census inside the namespace; the airlock-seal
refusals exercised; the environment recorded **twice** (at entry and
after the import) with values only for the declared non-secret
allowlist and everything else by name; the flags-off assertion result;
the positive-control block of §12.11 — interactions returned, storage
tail invocations, and collection counts before and after; and the
statement that the manifest's `at` is ordinal, with the observed
wall-clock span of the run beside it.

Added in v6.3: the orchestrator's full log; the comparator self-test's
13-case output; the airlock claim marker and lock evidence; the
resolved `default_ledger_path()` value and the store-path overlay
assertion; **per-interaction** tail-passage counts; `brain_reachable:
false` with the per-interaction reply shapes; and the archive exclusion
list.

### 12.11 Positive controls — the baseline must prove it happened

Round 13's finding I is the one that could have wasted the whole
exercise: **two equally empty store trees agree with each other and
prove nothing.** Every `handle_message` call could raise, the driver
would catch each one, exit 0, and produce a "baseline" that a later S1
run would match perfectly — certifying invariance across a pair of runs
in which the reply path never stored anything.

The run is therefore not a baseline unless all three hold, and the
driver exits non-zero if any fails:

1. **Every interaction returned.** 20 of 20, no exception. Any raise is
   listed by id in the report.
2. **Every interaction reached the storage tail.**
   `MemoryManager.store_telegram` is wrapped in a counting proxy that
   calls through unchanged and is removed before the tree is projected;
   the count is sampled **around each individual call**, and every
   interaction must show at least one passage. *(v6.3, round 14 item I:
   v6.2 required only an aggregate greater than zero, which 19
   returned-before-tail interactions plus one stored one would satisfy
   — and production has returned-before-tail paths at
   `maez_daemon.py:7197`.)* This is observation, not substitution —
   declared here so the report is not read as an untouched path.
3. **The stores actually grew.** Chroma `raw`/`daily`/`core` counts are
   recorded before and after; at least one must increase.

**What the controls deliberately do not assert.** T5 runs hermetic, so
`BackendError` is converted to a returned fallback string and stored
(`maez_daemon.py:8958`). Twenty returned fallbacks are the expected
shape, not a failure — but they are **not healthy synthesis**, and the
report must never present them as such. The driver records
`brain_reachable: false` and the per-interaction reply shape (length,
emptiness) so the reader can see exactly what was exercised.

Round 13's other two I-findings are closed elsewhere: the `config/.env`
reload in §12.2, and the `at` semantics in §12.6.

### 12.12 The orchestrator (closes round-14 J)

Round 14 ruled hand-driving unacceptable, and it was right: a report
can record what a human did, but it cannot make a failed exit code
bite, and it cannot guarantee the daemon comes back after an
intermediate failure. `docs/superpowers/witness/theme2_s1_t5_run.sh` is
the single committed authority for

```
preflight → stop daemon → (fresh airlock → self-test → replay →
extract → project) ×2 → derive volatile → compare → archive → restart
```

with `set -euo pipefail`, every step's status consumed, the archive
produced **only** after every prior step succeeded, and the daemon
restarted from an `EXIT` trap so it returns even on failure or
interrupt. It refuses a dirty working tree — a baseline must be pinned
to a commit — and it refuses to run at all if `maez.service` is active
and `--stop-daemon` was not passed, rather than quietly racing the live
daemon. It runs the comparator's own self-test **first**, because the
comparator is the instrument the verdict rests on.

Two v6.4 corrections, both round 15 item J:

- **The workdir is claimed atomically and locked run-wide.** v6.3 gave
  `--work` only a lexical `/tmp` check and `mkdir -p`, so a
  pre-existing hardlink or symlink could alias `proj-a.json` to
  `proj-b.json`: run B would overwrite run A's evidence, the derivation
  and comparison would read B twice, and the archive would still come
  from physical airlock A. The orchestrator now refuses a workdir that
  already exists, refuses an unowned or symlinked parent, and holds
  `flock` on the workdir for the whole run.
- **Publication is contingent on the daemon coming back.** v6.3 copied
  the archive into the repo and only then ran the trap, where a failed
  `systemctl start` was a warning and `inactive` was ignored — so a
  baseline could be published while Maez stayed down. Restoration now
  runs **before** publication, polls until the unit reports `active`,
  and a failure to restore both blocks the copy and sets a non-zero
  exit.
- **The archive digest is computed as its own checked command, and
  published atomically.** v6.4 hashed inside a command substitution
  passed to `say`; `say` succeeded, so `set -e` never saw the failing
  `sha256sum` and publication proceeded with an empty digest. The hash
  is now its own statement with an emptiness check, the copy goes to a
  `.tmp` destination, the digest is re-verified there, and only then is
  it `mv`'d into place — so an interrupt during the copy cannot leave a
  partial archive at the committed path. *(v6.5, round 16 item J.)*

### 12.13 Finding K — recorded here, ruled elsewhere

Round 14 upheld the S2 protocol's O-1 WAL finding and added a
consequence for S1 that belongs in this file: design §5 requires latch
publication around **every** lived commit, while T2 witnesses a single
writer path (§3). Under the daemon-plus-web multi-writer topology the
ordering of latch allocation and publication across processes is
**unwitnessed**. It is not a prerequisite for generating the
pre-S1 baseline, and it is recorded as an open item rather than
silently folded into T2.

**Scope, ruled by Codex 2026-08-22 and adopted.** The original wording —
"that must close before S1 code lands" — read strictly blocks the whole
slice, which is broader than the actual dependency. The ruling:

> This blocks `core.memory.birth_latch.advance()`, every lived-writer
> latch-publication hook, and the latch-dependent publication/repair
> branches of `birth_phase.resolve()` until the production writer
> topology is ruled and T2 witnesses that topology. It does not block
> `core.memory.s1_census`, the pinned `PhaseResult`/reason contract,
> latch-independent resolver classification, or flag-dormant consumer
> refusal wiring. **S1 must not be enabled or declared complete until
> this closes.**

Build order, with the reason for each position:

1. `s1_census.py` — static AST enumeration; it neither allocates latch
   positions nor interprets their ordering, and it fixes the
   implementation boundary before any runtime change.
2. The topology-neutral part of `birth_phase.py` — the namedtuple, the
   frozen reason vocabulary, the exception, the activation switch, and
   the absent/empty/structural/error classifications. Latch publication
   and repair stay behind a fail-closed seam.
3. The 13 consumer refusals, flag-dormant — witnessable against
   structural `unknown` and healthy `gestation` without claiming
   anything about lived multi-writer ordering.
4. **After O-1 is ruled**: `birth_latch.advance()`, the commit hook, and
   the latch-dependent resolver branches, together, with T2 amended for
   the chosen topology.

"Full resolver first" is explicitly *not* safe: its first-lived and
repair behavior would already encode assumptions about latch allocation
that O-1 may invalidate.

K has no direct T5 consequence: the airlock ledger has writes disabled
and the replay is single-process.

### 12.10 What this amendment does not change

T1, T2, T3, T4, T6 are untouched. No storage layer is stubbed or
mocked — §12.3 is the absence of a network, not a fake brain.
`memory_manager.BASE_DB` is **not** made env-overridable, and T5 does
**not** imitate the recall-eval sandbox's monkeypatch: a rebind covers
the one literal someone remembered, while containment covers all 54.
Repairing production code so a witness can run inverts the discipline.
The witness survives the code as shipped.
