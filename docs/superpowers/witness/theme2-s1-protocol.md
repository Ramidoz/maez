# Theme 2 — S1 (phase truth) witness protocol, v6

Status: PROTOCOL v6. Body = v1; §9 = v3, §10 = v4, §11 = v5, §12 = v6.
Binding once its gate passes; S1 code is barred until then. The S1
implementation is judged against this file, not design prose.
v6 closes T5's execution model against the pre-execution audit; the
T5 archive digest and the volatile-column literal arrive in v7, which
per gate round 11 must precede the first S1 code commit.

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
  `PrivateThoughts.record_thought/record_secret/record_reflection`,
  `AuditLog.record(...)`, `AuditLog.start_direct_edit_session(...)`,
  `AuditLog.log_direct_edit(...)`, `source_awareness` path-gate
  helper, `span_planner.plan(...)`, and a production-mode
  `LedgerWriter.write_turn('system_event', ...)`; argument fixtures
  are literal in the harness file committed with the S1 code, whose
  digest is recorded in the run report. Heartbeat readers
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
- **T3 `_migration_null_normalize`**: invoked only via
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
  the airlock; its sha256 is added HERE by a protocol v5 amendment
  committed **before** the first S1 code commit — the ordering, not
  the timing, is the binding rule, and the S1 gate checks the
  amendment predates the code in history.
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

## 12. v6 amendment — T5's execution model, closed against the pre-execution audit

Round 10 pinned T5's *artifact* (path) and round 11 pinned its
*ordering* (digest amendment precedes the first S1 code commit).
Neither pinned how the run executes. The pre-execution audit
(`docs/superpowers/specs/2026-08-22-theme2-t5-airlock-audit.md`) found
three facts that make §6 unexecutable as written. This amendment
closes them. It is authored **before any T5 run and before any S1
code exists**, so nothing here is tuned to an outcome.

Owner rulings taken at audit time: containment approved subject to a
gate round; hermetic (no network); pre-registered projection; the live
daemon stopped for the run.

### 12.1 The three findings, restated as binding constraints

- **F-A** `memory/memory_manager.py:45` pins
  `BASE_DB = Path("/home/rohit/maez/memory/db")` with no environment
  override; `_make_client()` (`:597`) `mkdir`s and opens Chroma there.
  Environment redirection therefore cannot airlock this run. 54
  module-global absolute-path constants exist repo-wide; 9 sit on or
  beside the reply path.
- **F-B** Every store on the path stamps `uuid4()` and a wall clock
  (`memory_manager.py:1499`, `1598`, `2066`; `private_thoughts.py:1099`;
  `audit_log.py:245/444/513/568`; `writer.py:353`). Raw byte equality
  between two runs is impossible.
- **F-C** The brain, the airlock's starting state, and the live
  daemon's concurrency were all unspecified.

### 12.2 Containment replaces redirection (closes F-A)

The run executes inside `bwrap` with the live tree **read-only** and
airlock directories bound over exactly the writable targets. The live
absolute path still resolves — so a module-global literal is caught by
construction — and any path the bind set did not anticipate fails
`EROFS`, loudly, instead of writing to the live tree.

The wrapper is `docs/superpowers/witness/theme2_s1_airlock.sh`,
committed with its sha256 recorded in the run report. Its argv is:

```
bwrap \
  --ro-bind / / \
  --ro-bind /home/rohit/maez /home/rohit/maez \
  --bind  <AIRLOCK>/maez/memory        /home/rohit/maez/memory \
  --bind  <AIRLOCK>/maez/logs          /home/rohit/maez/logs \
  --bind  <AIRLOCK>/maez/.cache        /home/rohit/maez/.cache \
  --bind  <AIRLOCK>/home/.config/maez  /home/rohit/.config/maez \
  --bind  <AIRLOCK>/home/.cache/chroma /home/rohit/.cache/chroma \
  --tmpfs /tmp \
  --proc /proc --dev /dev \
  --unshare-net --unshare-pid --die-with-parent \
  --setenv PYTHONDONTWRITEBYTECODE 1 \
  --setenv HOME /home/rohit \
  --chdir /home/rohit/maez \
  <PYTHON> -m <DRIVER> ...
```

- `PYTHONDONTWRITEBYTECODE=1` is required: the repo is read-only and
  `__pycache__` writes would otherwise fail mid-import.
- `<AIRLOCK>/home/.cache/chroma` is seeded once by copying the host's
  `~/.cache/chroma` (167 MB, `ONNXMiniLM_L6_V2` per
  `memory/embedding_contract.json`). It is a read-only *asset* that
  must be writable-bound because Chroma may touch it; it is **excluded
  from the store tree and from the archive**.
- **Bind-set discovery is iterative and recorded.** The set above is
  the audit's prediction, not a proof. Any `EROFS` encountered during
  the run is a *finding*: the run report lists every path that failed
  read-only, and either the bind set grows (recorded, with the reason)
  or the run stops. A read-only failure is never worked around by
  loosening `--ro-bind /home/rohit/maez`.
- **Containment self-test, run immediately before the replay and
  recorded verbatim**: inside the same namespace, (1) a write to
  `/home/rohit/maez/CONTAINMENT_PROBE` must fail `EROFS`; (2) a write
  to `/home/rohit/maez/memory/CONTAINMENT_PROBE` must succeed and be
  visible only at `<AIRLOCK>/maez/memory/`; (3) after the namespace
  exits, neither probe exists in the live tree. Any deviation kills
  the run before the manifest is touched.

### 12.3 Hermetic (closes F-C.1)

`--unshare-net`. The LLM at `127.0.0.1:8080`, the judge at `:8081`,
and `maez-searxng` are all unreachable; `llm_client.chat` raises
`BackendError` and the reply path takes its fallback. This is
deliberate: T5's subject is the **store tree under flags-off**, not
reply quality, and it removes an entire non-determinism axis together
with every egress risk. The run report records that the brain was
unreachable and quotes one fallback reply verbatim so the shape of
what was exercised is legible.

### 12.4 Starting state (closes F-C.2)

The airlock starts **empty**. `<AIRLOCK>/maez/memory/ledger.db` is
created by `core.ledger.migrate.run` before the namespace is entered,
its sha256 recorded; every other store is created by the code under
test on first write. No live store is copied — a baseline archive
committed to git must never carry Maez's real memories.

### 12.5 The live daemon (closes F-C.3)

`maez.service` is stopped for the duration of the run and restarted
after, by the owner's ruling. The report records the stop time, the
restart time, and `systemctl --user is-active maez.service` before and
after. This is belt-and-braces on top of containment, not a substitute
for it.

### 12.6 The driver

`docs/superpowers/witness/theme2_s1_t5_replay.py`, committed with its
sha256 recorded in the report. It constructs `MaezDaemon()` and calls
`handle_message(text, source="UI")` once per manifest interaction in
manifest order — the manifest's `source: "UI"` field names that entry
point. It sets no `MAEZ_*` flag; the full environment is recorded.

### 12.7 The store tree, and what the archive contains

**Store tree** = `<AIRLOCK>/maez/memory/**`, in full.
**Excluded**: `<AIRLOCK>/maez/logs`, `<AIRLOCK>/maez/.cache`, and
`<AIRLOCK>/home/**` (the model cache). The archive
`docs/superpowers/witness/theme2-s1-baseline.tar.zst` is the store
tree, `tar` with sorted member order, numeric owner, and mtimes
normalized to `0`, `zstd -19`. If the archive exceeds 25 MB the run
stops and the owner rules on placement before anything is committed.

### 12.8 The invariance projection (closes F-B) — pre-registered

Raw byte equality is replaced by a projection fixed **here**, before
any S1 code exists. It has two frozen parts and one deferred literal.

**Byte-exact clauses. Any difference is a kill.**

- **B1** `ledger.db` sha256 after the run equals its post-migration
  sha256 recorded in §12.4. Flags off, `try_write_turn` returns `None`
  from `ledger_writes_enabled()` *before* constructing a writer
  (`writer.py:576-578`), so the ledger is never opened. This clause is
  exact, not projected.
- **B2** No `birth_observed/` directory, no `segment-*.jsonl`, and no
  `*.tmp` under any latch path anywhere in the airlock.
- **B3** The canonicalized relative path set of the store tree is
  identical between runs and to the baseline. Canonicalization: any
  path component matching
  `^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$` is
  replaced by `<uuid:N>`, N being its ordinal in first-appearance
  order under a lexicographic walk. Chroma names segment directories
  with fresh UUIDs; nothing else in the tree may vary.

**Projected clauses.**

- **P1 — SQLite stores** (every `*.db` and `chroma.sqlite3` in the
  tree): `SELECT name, type, sql FROM sqlite_master ORDER BY name,
  type` identical; per table, row count identical; per table, the rows
  with the declared volatile columns dropped, sorted by the full
  remaining tuple, identical.
- **P2 — Chroma collections**: per collection, the record count; the
  sorted multiset of `(document, metadata-with-volatile-keys-dropped)`;
  and the sha256 over the embedding vectors sorted by their document
  text, compared **exactly**. `ONNXMiniLM_L6_V2` is deterministic, so
  a vector difference is a real finding and is reported, never
  loosened to a tolerance.
- **P3 — phase-exactness**: for every store carrying `memory_phase`,
  the multiset of values, and per value the set of row identities
  under P1's ordinalization.

**The deferred literal, and why deferring it is still
pre-registration.** The *volatile column and metadata-key list* cannot
be enumerated before the baseline run, because the set of tables the
replay creates is not knowable by reading. The rule is frozen here —
a column or key is volatile iff its values across the two baseline
runs differ AND it is either UUID-shaped by B3's regex or a
time-shaped numeric/ISO-8601 field. The **literal list** is computed
from the two baseline runs and frozen in the v7 amendment, committed
together with the archive digest and, per round 11, **before the first
S1 code commit**. Pre-registration is preserved with respect to the
thing under test: the projection is fixed before any S1 code exists.
Any column whose values differ between the baseline runs and which is
*not* UUID-shaped or time-shaped is a **finding, not a volatile
column** — it is reported and ruled on, never absorbed.

### 12.9 Report obligations added to §8

The `bwrap` argv verbatim; the containment self-test output; the
wrapper and driver sha256; every `EROFS` path encountered; the
daemon stop/restart timestamps and `is-active` output; the
post-migration `ledger.db` digest; the brain-unreachable evidence and
one verbatim fallback reply; the archive digest and byte size; the
computed volatile list with the evidence for each entry.

### 12.10 What this amendment does not change

T1, T2, T3, T4, T6 are untouched. No storage layer is stubbed or
mocked — §12.3 is the absence of a network, not a fake brain.
`memory_manager.BASE_DB` is **not** made env-overridable: that is a
real defect deserving its own slice, but repairing production code so
a witness can run inverts the discipline. The witness survives the
code as shipped.
