# Theme 2 — S1 (phase truth) witness protocol, v6

Status: PROTOCOL v6.1. Body = v1; §9 = v3, §10 = v4 (one v6.1
correction), §11 = v5, §12 = v6.1.
Binding once its gate passes; S1 code is barred until then. The S1
implementation is judged against this file, not design prose.
v6 closed T5's execution model against the pre-execution audit; v6.1
closes gate round 12's six items (A, B, C, D, E, G — F passed). The T5
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

## 12. v6/v6.1 amendment — T5's execution model, closed against the pre-execution audit and gate round 12

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
bwrap --ro-bind / /  --ro-bind /home/rohit/maez /home/rohit/maez
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

Three round-12 gaps, closed:

- **`--tmpfs /run` and `--tmpfs /var/tmp`.** `--unshare-net` does not
  block filesystem Unix sockets; the host session D-Bus under `/run`
  would have remained reachable, and read-only-mounting a socket
  pathname does not stop an outside process from acting on it. `/run`
  is now an empty tmpfs, asserted by the self-test.
- **`--clearenv` plus an explicit nine-variable set.** §6 requires
  "all `MAEZ_*` flags unset; full env recorded". Inheriting the
  environment made that a claim to be inspected; clearing it makes it
  true by construction, and the recorded environment is exactly nine
  variables. `PYTHONHASHSEED=0` and a pinned `TZ` remove two
  determinism axes the manifest exposes ("what day is it today").
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
- **Nothing runs outside the namespace.** v6 migrated the ledger before
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
TCP table is empty; (4) `/run` is an empty tmpfs; (5)
`import memory.memory_manager` succeeds **and** `BASE_DB` resolves to
`/home/rohit/maez/memory/db`, i.e. into the overlay; (6) no `MAEZ_*`
variable is set; (7) the probe exists in the airlock; (8) neither probe
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

### 12.7 The store tree, and what the archive contains

**Store tree** = `<A>/maez/memory/**`, minus the seeded package sources
named in `logs/seeded-sources.txt`.
**Excluded**: `<A>/maez/logs`, `<A>/maez/.cache`, `<A>/home/**` (the
167 MB `ONNXMiniLM_L6_V2` cache, a read-only asset the hermetic run
cannot re-download), and the seeded sources.

The archive `docs/superpowers/witness/theme2-s1-baseline.tar.zst` is
the store tree, `tar` with sorted member order, numeric owner, mtimes
normalized to `0`, `zstd -19`. If it exceeds 25 MB the run stops and
the owner rules on placement before anything is committed.

### 12.8 The invariance projection (closes F-B and round-12 D and E)

Raw byte equality is replaced by a projection fixed **here**, before
any S1 code exists, and implemented by
`docs/superpowers/witness/theme2_s1_t5_projection.py` (sha256 in the
report), which is self-tested against each clause before it is pointed
at a real baseline.

**Byte-exact clauses. Any difference is a kill.**

- **B1** — the ledger's **main file** sha256 after the replay equals its
  post-migration sha256 from §12.4. *(v6.1 correction, round 12 item C:
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
- **B4** — `-wal` / `-shm` sidecars: **presence compared, bytes not.**
  They are checkpoint-timing artifacts, and their existence is expected
  per B1. Naming them explicitly is the point: v6 left them
  unprojected, which is a hole, not a decision.

**Projected clauses. Ordinalization, never dropping.**

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
  error) is a kill, never a skip.
- **P2** — Chroma collections: record count; the sorted multiset of
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
  `^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$`,
  or `^[0-9a-f]{12,64}$`, or `^[a-z][a-z0-9_]*-[0-9a-f]{8,32}$`.
- **time-shaped** iff it is a non-boolean number in `[1600000000,
  2600000000]` (unix seconds, 2020-09-13 .. 2052-06-07) or in
  `[1600000000000, 2600000000000]` (the same window in milliseconds),
  or a string matching
  `^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:?\d{2})?$`.
  A number outside those two windows is **not** time-shaped, whatever
  it is called.
- Every differing value in the field must satisfy one class, and the
  same class. A field that differs and satisfies neither is a
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

### 12.10 What this amendment does not change

T1, T2, T3, T4, T6 are untouched. No storage layer is stubbed or
mocked — §12.3 is the absence of a network, not a fake brain.
`memory_manager.BASE_DB` is **not** made env-overridable, and T5 does
**not** imitate the recall-eval sandbox's monkeypatch: a rebind covers
the one literal someone remembered, while containment covers all 54.
Repairing production code so a witness can run inverts the discipline.
The witness survives the code as shipped.
