# Theme 2 — S2 (schema v2) witness protocol, v1

Status: **PROTOCOL v1 — DRAFT, not binding.** Authoring was unlocked by
gate round 10 ("S2 protocol authoring MAY BEGIN"). Binding requires its
gate to pass and §11's open items to close. Per design §8, this file is
committed **before** any S2 code; the schema draft's own header makes
it a precondition ("Status: DESIGN ARTIFACT. Becomes migrations only
after the gate passes and S2's witness protocol is committed").

S2 = design §§3–4, 7: atomic admission, seals, fenced runs, two-phase
egress, enforced closures, the evidence relation, the birth-anchor
column, FK + triggers, digested migrations, hash domain v2. The
executable subject is `docs/superpowers/specs/2026-08-22-theme2-schema-
v2-draft.sql` revision 8, turned into shipped migrations 0006+.

The S2 implementation is judged against this file, not design prose.

## 0. Ground rules

- **Containment, not redirection.** Every S2 witness runs inside the
  `bwrap` namespace fixed by S1 protocol §12.2, with the live tree
  read-only and airlock directories bound over the writable targets.
  The reason is S1's audit finding F-A: `memory/memory_manager.py:45`
  pins an absolute live-store path with no environment override, so
  `MAEZ_LEDGER_DB_PATH` alone does not airlock anything that touches
  the reply path. S2's own tests are narrower than T5's, but the rule
  is uniform — no witness in this theme runs outside containment. The
  containment self-test of §12.2 runs first and is recorded.
- **Never test discovery against the live tree.** Explicit file lists
  only. S2's selector list is frozen at S2-authoring commit as
  `docs/superpowers/witness/theme2-s2-selectors.txt`.
- **SQLite pinned**: the run report records `sqlite3.sqlite_version`
  (expected 3.46.1) and the interpreter path. A different version is a
  reported deviation, not a silent substitution. See §7 — the version
  is not incidental to S2; it is load-bearing.
- **Clock**: every time value in a control row is a harness-injected
  integer named in that control. No witness in S2 calls wall-clock
  inside the construct under test.
- **Fixtures**: built by `docs/superpowers/witness/theme2_s2_fixtures.py`
  (committed at S2 authoring, digest frozen here by amendment), which
  refuses to run outside the airlock. Base fixture **G2** = a ledger
  with migrations 0001–0005 **plus** the S2 migrations applied,
  genesis intact, zero non-genesis rows.
- **Migration digests, 0001–0005** (unchanged from S1 protocol §0;
  re-frozen here because S2 adds to the set):
  - 0001 `eb126df1dd8c6ff5e249dab0259582747e3352991468acc936052d728db7ca75`
  - 0002 `7aa3876024f45778a67e3e744f4ed5624146e94603cd7dd1e188c56a740fdc38`
  - 0003 `5e0829a501408b5db940a15b47899bd2899eb551da3f5795babe215ea00d9185`
  - 0004 `69e5f4bc78ac8a81f742c61da49bab022234dfb8647b9977ce3e1812ce77a659`
  - 0005 `5b66deb643d346a7f0b1ff154618b83366b1c7816de7f1d1b7304102c78d7c86`
  The S2 migration digests are added by amendment when those files
  exist. **S1's T6 fingerprint list is re-frozen at the same moment** —
  S1 protocol §0 says so explicitly ("the list is re-frozen when S2's
  migrations land"), and forgetting that would silently break T6.
- **Genesis anchor**, byte-exact and deterministic across independent
  builds: `turn_id='genesis'`, `chain_position=0`,
  `raw_text='{"event":"genesis","schema_version":1}'`, chain hash
  `d313c6473ea19dbe038d3f2f1d714d1ce8c0a9b8e756ef0d4b1849f8eb09989d`.

## 1. The tests

| Test | Subject |
|---|---|
| U1 | The frozen invalid-row-rejection roster (design §8's obligation) |
| U2 | DDL inventory and integrity fingerprint |
| U3 | Migration digest witnesses |
| U4 | `--recreate-empty` exclusivity (design §13/§14 F6) |
| U5 | Cross-process `BEGIN IMMEDIATE` fencing (design §12 B10) |
| U6 | Hash domain v2 and chain-bound birth |
| U7 | Non-cooperating-opener conformance sweep |
| U8 | Flags-off invariance |

## 2. U1 — the frozen rejection roster

Design §8 makes this an obligation, not an option: "every adversarial
insert Codex executed in round 2 is a named negative control in the S2
protocol … each required to fail with the specific trigger/index
error."

**The roster artifact** is
`docs/superpowers/witness/theme2-s2-controls.json`, sha256
`c59b323ee2d1314345a0e4db5240d5bb283511c9ca2cc156e63f6b2d1382a6cd`.
It is a **verbatim record only**: for each of **100** control ids it
carries every table row any gate round ever wrote for that id, in
round order, the enclosing section heading, and the sha256 of each
source round document. `expected` is `null` on every entry **by
design** — no expectation is inferred, because inferring 100
expectations from prose is exactly the reconstruction-disguised-as-
continuity failure this theme exists to prevent.

Families present with per-id statements: `N` 22, `P` 26, `Q` 35,
`R7` 10, `C8` 7 = 100.

**Two gaps are recorded, not papered over:**

- `R4-01..R4-21` — gate round 5b records "21/21 PASS" for the retained
  round-4 rejection tests. **No per-id statement was ever written
  down.** They are not assumed to be a renaming of `N01..N22`: round
  10 counts `N 22/22` and `R4 21/21` as separate suites. These 21 must
  be re-derived from round 4's execution or re-authored, then
  re-executed.
- `R5-01..R5-02` — gate round 7 records both superseding-ordinal
  controls rejecting with `supersession re-observes the same attempt:
  retry_ordinal must match`; no per-id statement exists.

**U1's two obligations, both required before this protocol binds:**

1. **Literalize the expectation for all 123 ids** (100 recorded + 23
   named-only). Per id: `REJECT` with the exact expected error string,
   or `ACCEPT` as a declared lawful path. The derivation rule is fixed
   here: an id's expectation is whatever gate round 10's re-execution
   against DDL revision 8 observed — round 10 reports the suites
   wholly passing, so every invalid-row control rejects and every
   declared lawful path is accepted. **The rule does not license
   guessing per id**; each expectation is written down with the round
   and line that establishes it, and any id whose expectation cannot
   be established from the record is re-executed against rev 8 and the
   observation recorded as new evidence, labeled as such.
2. **Ship the executable suite.** `docs/superpowers/witness/
   theme2_s2_controls.py`, committed with its digest frozen by
   amendment, containing one executable statement or statement
   sequence per id. It runs against an **on-disk** fixture in the
   airlock, never `:memory:` — every gate round so far executed the
   DDL in `:memory:`, which cannot observe file locking, WAL, sidecar
   files, or cross-process behavior. Re-executing the roster on disk
   is itself a new witness, and a divergence from the in-memory result
   is a finding, not noise.

**Kill**: any invalid-row control accepted; any declared lawful path
rejected; any rejection whose error string differs from the frozen
expectation; any id in the roster with no executable statement; any
executable statement with no roster id.

## 3. U2 — DDL inventory and integrity fingerprint

Against G2, read from `sqlite_master` and compare to lists frozen by
amendment at S2 authoring: the table set, the trigger name set, the
index name set, the view name set. Round 10's execution of the
revision-8 draft observed **11 tables, 37 triggers, 5 indexes, 3
views** for the draft fragment; the shipped-migration inventory will
differ because it includes migrations 0001–0005's objects, so the
frozen lists are computed from G2, not copied from round 10.

`PRAGMA integrity_check` = `ok`. `PRAGMA foreign_key_check` empty.

Nine mutation controls in S1 protocol §7's shape, recomputed for G2's
inventory, each flipping the structural verdict — carried here so that
S1's T6 and S2's U2 cannot drift apart silently.

**Kill**: any inventory difference; any mutation the fingerprint misses.

## 4. U3 — migration digest witnesses

1. After migration, `schema_migrations` contains exactly the shipped
   names with digests equal to the sha256 of the shipped files on disk.
2. Re-running the migration is a no-op: zero rows change, the file
   digest is unchanged.
3. Tamper: `UPDATE schema_migrations SET digest=<flip one hex char>` →
   the structural validator reads `unknown`, and the migrator refuses
   to proceed.
4. Interrupted migration: kill the migrator between two migration
   files (sentinel + `SIGKILL`, the S1 §3 mechanism); the resulting DB
   must read `unknown`, never `gestation`, and a re-run must either
   complete cleanly or refuse — never silently rebaseline.
5. `--recreate-empty` is refused on any ledger carrying a birth anchor
   and on any ledger with non-genesis rows (design §7).

**Kill**: a tampered digest accepted; an interrupted migration reading
`gestation`; an in-place rebaseline.

## 5. U4 — recreate-empty exclusivity (F6)

Design §13/§14 pin the mechanism: v2 writers take a **shared `flock`**
on the `ledger.lock` sidecar at connection open and hold it for the
connection's life; `--recreate-empty` takes the **exclusive `flock`**,
verifies quiescence and sidecar absence, builds at a temp path,
renames, releases. The lock file is created once by migration, mode
0444-plus-owner-write, and is **never unlinked**; recreate verifies
the inode it locked is still the inode at the path before proceeding.

Witnesses, all cross-process in the airlock:

1. A live writer holds the shared lock → `--recreate-empty` blocks and
   then refuses; the original inode is unchanged; the writer's
   in-flight transaction commits normally.
2. No opener → recreate succeeds; the path's inode changes exactly
   once; a writer started after the rename sees the new inode.
3. Inode swap between lock acquisition and the build: the harness
   replaces `ledger.lock` with a fresh file while recreate holds the
   exclusive lock → recreate must detect the inode change and refuse.
4. `unlink`/`rename` on the lock path is banned repo-wide by the
   conformance sweep (§8); the sweep is executed here with a seeded
   violation that must be named, then removed.
5. Recreate refused on a ledger with a birth anchor, and on one with
   non-genesis rows.

**Kill**: a recreate that proceeds while a cooperating opener lives;
an opener that survives holding a stale inode; an unlink of the lock
path anywhere in the tree; a seeded sweep violation not named.

## 6. U5 — cross-process BEGIN IMMEDIATE fencing (B10)

This is the witness in-memory reviews could never execute, and its
literals are already frozen by design §12: a **pre-generated
deterministic arrival schedule, seed 20260822**; exactly **N = 1000
exchanges, 500 per writer**; the measured quantity is **wall-clock
`BEGIN IMMEDIATE` acquisition time per ledger transaction**; **p99 by
nearest rank**; **kill = any refusal, or p99 > 250 ms**; **positive
control = one scheduled 6 s lock-hold that must trip the rule**.

Two real OS processes, not threads. The schedule, both processes'
per-transaction acquisition samples, and the nearest-rank computation
are recorded raw in the report before any interpretation.

The positive control is coherent with the shipped writer: `writer.py:225`
sets `PRAGMA busy_timeout = 5000`, so a 6 s hold necessarily produces
a refusal, and a run in which it does **not** refuse means the harness
is not measuring what it claims.

**U5 does not run until §11's open item O-1 is ruled on.**

## 7. The WAL constraint — a design-level finding, recorded before any code

`core/ledger/migrate.py:218` sets `PRAGMA journal_mode = WAL`
persistently on the ledger file. B10 requires two processes writing
that file concurrently, 1000 exchanges.

The verified host fact: the runtime links **SQLite 3.46.1**
(`3.46.1-9ubuntu0.2`). SQLite documents a WAL-reset corruption defect
affecting versions **through 3.51.2** when multiple connections write
and checkpoint concurrently, fixed in 3.51.3 with backports to 3.44.6
and 3.50.7; the Ubuntu package changelog shows no corresponding
backport. Status: **likely affected, not certifiable.** The standing
design rule this imposed on the whole codebase is: any new SQLite
store must have a single writer process, or must not use WAL with
concurrent writers. The precision matters and must not be
over-corrected — the defect is WAL-specific; multi-process writing in
the default rollback-journal mode is serialized by file locks and is
not exposed.

So U5, executed as designed, would (a) exercise the exact hazard the
host is likely subject to, and (b) if it passed, certify a production
topology — two concurrent WAL writers on the ledger — that the
standing rule forbids. A green witness would be worse than no witness:
it would launder the constraint.

This is a finding against the **design**, not against the witness, and
it belongs to the owner and the gate, not to this file. §11 O-1
records it.

## 8. U7 — non-cooperating-opener conformance sweep

Design §13's F6 closure: "any `sqlite3.connect` to the canonical path
outside the lock-taking rail fails the AST sweep." The sweep walks
`core/ memory/ daemon/ skills/ cli/ scripts/` with `ast`
(interpreter-pinned), and fails on any `sqlite3.connect` whose
argument resolves to the canonical ledger path outside the rail, and
on any `unlink`/`rename` targeting `ledger.lock`.

The sweep must also cover the class S1's audit found the hard way:
**module-global absolute path literals**. An AST sweep of module-level
assignments over those roots currently finds **54** absolute-path
constants under the owner's home, of which `memory/memory_manager.py:45`
`BASE_DB` is the one with no environment override. S2 does not fix
them — that is its own slice — but the sweep enumerates them and the
count is frozen, so a new one cannot be added silently.

Controls: a seeded non-cooperating `sqlite3.connect` must be named and
then removed; a seeded 55th module-global constant must be named and
then removed.

**Kill**: sweep passes in either seeded state; the frozen count drifts
without an amendment.

## 9. U6 — hash domain v2 and chain-bound birth

- `meta.chain_hash_domain = '2'`; writer and verifier both dispatch on
  it and project through the single `chain.py`-owned v2 function. The
  v2 hash-consumer census is closed at: writer, genesis seeder,
  verifier, `core/consolidation/citation_lock.py`,
  `core/ledger/span_reader.py`. An AST control seeds a sixth consumer
  computing its own projection; the census must name it.
- `turns.is_birth_anchor` is **included in the v2 hash**, with at most
  one row = 1 enforced by trigger.
- Mutating `meta.birth_event_turn_id` alone does not move birth truth:
  the phase read joins it to the hashed anchor row and reads `unknown`
  on divergence. This is S1's F-X cell, re-executed against the v2
  schema so the two slices cannot drift.
- Chain verification to head; `meta.last_chain_hash` = actual tip.
- Mutation controls: flip one byte of the anchor row's hashed
  projection → verification fails; set `is_birth_anchor=1` on a second
  row → trigger rejects.

**Kill**: any divergence read as anything but `unknown`; two anchors
accepted; a hash consumer outside the census.

## 10. U8 — flags-off invariance

Same shape and the same honesty as S1's T5 under protocol §12: the
run is contained, hermetic, starts from an empty airlock, and is
compared under the pre-registered projection rather than raw bytes,
because the stores stamp `uuid4()` and wall clock. S2's additional
byte-exact clause: with the S2 flag off, `schema_migrations` gains no
row and the v2 tables are not created.

## 11. Open items — this protocol does not bind until these close

- **O-1 (blocking, owner + gate).** The WAL constraint of §7.

  **Gate round 14 upheld the finding and recommended an option.** Its
  precision correction is worth keeping: U5 instantiates the affected
  topology but freezes no checkpoint/reset schedule, so it does not
  deterministically trigger the race — a green U5 would prove
  *contention timing*, not corruption safety, and must not be read as
  authorizing the production topology. Its recommendation is **(b),
  strengthened**: one serialized ledger owner, not merely one process,
  because the defect also covers concurrent connections in separate
  threads. That has a consequence in shipped code — `core/ledger/
  model_reply_persistence.py:73` opens a bare secondary writer
  connection — which would have to join the ownership rail. Round 14
  rates (a) the best narrow fallback if multi-process writing must be
  preserved, (c) sound only once every production and witness
  interpreter is proven to load a fixed library, and (d)
  diagnostic-only. **The ruling is the owner's; this records the
  recommendation, it does not adopt it.**

  **RULED by the owner, 2026-08-23: option (c), upgrade the runtime.**
  Executed the same day: no apt pocket on Ubuntu 26.04 reaches the fix
  (3.46.1 everywhere) and `pysqlite3-binary` bundles 3.51.1 — still
  inside the window — so SQLite **3.53.4** is built repo-local at
  `vendor/sqlite` from the sqlite.org autoconf tarball (sha3-256
  verified against the download page), with Ubuntu's compile flags
  mirrored and FTS5 confirmed working under chroma. Loaded via
  `LD_LIBRARY_PATH` in the six maez systemd unit drop-ins and the venv
  activation — deliberately not system-wide. Every long-lived process
  logs its linked version at startup (`core/infra/sqlite_runtime.py`);
  the drop-ins initially applied *nothing* because they lacked a
  `[Service]` header, and that reporter caught it on the first boot.

  **The upgrade does not lift the no-concurrent-WAL-writers rule.** The
  rule stands until U5 witnesses the chosen topology under this library
  — 3.53.4 makes U5 *meaningful* (it no longer certifies a topology the
  host cannot safely run), not unnecessary. `require_fixed()` exists
  for the code that will someday depend on the fix; nothing calls it
  yet. U5 is UNBLOCKED for protocol purposes.

  The options as they stood before the ruling: (a) the v2 ledger moves off WAL for the fenced
  path so multi-process writing is lock-serialized and unexposed; (b)
  B10 is re-scoped to a single-writer topology and the fence is
  witnessed differently; (c) the runtime is upgraded or a backport is
  verified, making the concurrent-WAL topology certifiable; (d) the
  witness runs on a disposable airlock DB with the constraint recorded
  and production explicitly barred from the topology. Until this is
  ruled on, U5 does not run.
- **O-2 (blocking).** U1's 123 expectations are not literalized, and
  23 of the ids have no per-id statement in the record at all.
- **O-3 (blocking).** The executable suite `theme2_s2_controls.py`,
  the fixture builder `theme2_s2_fixtures.py`, and the selector list
  do not exist; their digests cannot be frozen yet.
- **O-4.** The S2 migration files do not exist, so §0's digest list
  and §3's inventory lists are unfrozen — and S1's T6 list must be
  re-frozen at the same commit.
- **O-5.** Round 10 executed every suite in `:memory:`. Re-execution
  on disk is required by §2 and may itself produce findings.
- **O-6 (new, gate round 14).** Design §5 requires latch publication
  around **every** lived commit, but S1's T2 witnesses a single writer
  path. Under the daemon-plus-web multi-writer topology the ordering of
  latch allocation and publication across processes is unwitnessed.
  Recorded in S1 protocol §12.13; it must close before S1 code lands.
  It is not a prerequisite for the pre-S1 T5 baseline.

## 12. Report obligations

Fixture digests (static verified, per-run recorded); the roster digest
and the suite digest; the containment argv and self-test output;
`sqlite3.sqlite_version` and interpreter path; every control's
observed outcome and error string **verbatim before interpretation**;
U5's raw acquisition samples and the nearest-rank computation; the
sweep's frozen counts; wall-clock; deviations. The protocol is never
edited retroactively to fit an outcome.
