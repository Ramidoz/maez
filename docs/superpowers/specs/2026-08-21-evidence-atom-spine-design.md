# Evidence-Atom Spine — design pass 3 (SCOPE-NARROWED, DDL-bearing)

Status: DESIGN, pass 3. Gate history: pass 1 BLOCKED (12 blockers),
pass 2 BLOCKED (2 closed, 10 open, 8 new, 0/15 falsifiers executable).
Round-2 report preserved verbatim at
`2026-08-21-spine-gate-round2.md`.

## 0. Why this pass is smaller, not bigger

Pass 2 answered every round-1 blocker by *adding* machinery — a keyed
lifetime primary key, sealed epochs, an in-process queue, exposure
capture across every model call. Round 2 then found eight new defects,
and all eight live in the machinery I added: keys rotate (B13), epochs
break joins (B14) and have no legal destination across a rotation
(B15), the queue is not a global writer (B18), and the exposure/recall
identity does not match the real call graph (B19, B7, B6).

This repository already learned this lesson once, in the Phase-2
deterministic-fact reflex: it was widened, then denylisted, then
dictionary-backed, and it only became correct when the promise was cut
down to what could actually be decided. **The right response to an
undecidable boundary is a smaller promise.**

So pass 3 narrows hard:

- **Halved scope.** This design now covers **D1 (atoms) and D2
  (lineage) only**. Recall events (D3) and prompt exposures (D4) are
  removed from this document and deferred to their own later design
  with their own gate. That deletes blockers 6, 7, 19 and the entire
  terminal-model-call coverage problem rather than answering them
  badly. Return Parallax needs only the atom layer; examined-life needs
  atoms plus lineage. Residual demand waits — it always was the organ
  most dependent on unbuilt substrate.
- **Bytes, not offsets** (B16). The spine stores atom bytes. Offsets
  into a live row are not durable: `scripts/metabolic_curation.py:370`
  copies rows under a new tier/id and deletes the hot id, which would
  make sealed evidence unrecomputable.
- **Plain hashes, no key authority** (B13, B11). Because the bytes are
  stored, a keyed hash protects nothing the file modes do not already
  protect — and it introduced rotation, key-ID, backup-keyring, and
  cross-key-equivalence problems that had no owner. `content_id =
  sha256(bytes)`, recomputable forever.
- **One file, no epochs** (B14, B15). Rotation is deferred to a later
  slice with its own gate. Growth is bounded by a numeric floor that
  *stops* the spine, never by deletion.
- **One process** (B18). The spine observes the daemon process only.
  Web and script writers are declared unobserved **by construction**,
  permanently and visibly, rather than promised and missed.
- **DDL, not prose** (B20). The contract below is executable SQLite
  with STRICT tables, CHECK enums, foreign keys, and append-only
  triggers.

What remains is a spine that can prove every claim it makes. It repairs
less. It does not lie about what it repairs.

## 1. Scope

| Defect | Measured | In this design? |
|---|---|---|
| D1 truncation blindness | over-limit rows: raw 3,571/44,037 (8.11%, max 2,910 tok); daily 24/40 (**60.00%**); core 10/134 (7.46%) | **YES** |
| D2 unfollowable ancestry | 16/82 rows carry the `,+N` sentinel (19.51%); 2,948/4,700 declared ancestor edges (**62.72%**) have no id recorded anywhere | **YES** |
| D3 discarded query vectors | 0 retained | **NO — deferred** |
| D4 no exposure record | construct absent | **NO — deferred** |

**Observation scope (permanent, declared):** the daemon process only.
Rows written by the web process, scripts, or benchmarks are
`UNOBSERVED_BY_SCOPE` — not gaps, not failures, and never silently
counted as observed.

## 2. All five write doors (B4)

Pass 2 said "three chokepoint methods" while naming four. The pinned
code has **five** `Collection.add` sites, all inside
`memory/memory_manager.py`:

| Site | Enclosing construct | Layer |
|---|---|---|
| `:1535` | `def store(...)` `:1479` | raw |
| `:1616` | `def store_telegram(...)` `:1576` | raw |
| `:1662` | `def _write_quiet_stub(...)` `:1651` (inside `consolidate_daily`) | daily |
| `:1884` | `def consolidate_daily(self)` `:1644` | daily |
| `:2079` | `def store_core(...)` `:1977` | core |

The quiet-stub path at `:1662` is the one pass 2 would have missed —
and daily is the layer with 60% over-limit rows. **Per-door witness
required:** one test per site proving an observation row is produced,
plus an AST test asserting the count of `.add(` sites inside
`memory_manager.py` is exactly five, so a sixth door cannot appear
unobserved.

## 3. The contract (DDL — B20, B3, B5, B13)

```sql
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;
PRAGMA busy_timeout = 5000;   -- short txns; pass 2's BEGIN IMMEDIATE withdrawn

-- Content identity: bytes-addressed, contract-independent.
CREATE TABLE atom_content (
  content_id   TEXT    NOT NULL PRIMARY KEY,   -- sha256(bytes), recomputable
  bytes        BLOB    NOT NULL,               -- the atom itself (B16)
  byte_len     INTEGER NOT NULL CHECK (byte_len > 0),
  created_ts   REAL    NOT NULL
) STRICT;

-- Embeddings hang off content, versioned by contract (B13).
CREATE TABLE atom_embeddings (
  content_id    TEXT    NOT NULL REFERENCES atom_content(content_id),
  contract_hash TEXT    NOT NULL,
  vector        BLOB    NOT NULL,              -- 384 x float32, canonical LE
  vector_hash   TEXT    NOT NULL,              -- sha256(vector bytes)
  token_count   INTEGER NOT NULL CHECK (token_count > 0),
  embed_ts      REAL    NOT NULL,
  PRIMARY KEY (content_id, contract_hash)
) STRICT;

-- Occurrence identity: one row per appearance (B2, kept from pass 2).
CREATE TABLE atom_occurrences (
  occurrence_id     TEXT    NOT NULL PRIMARY KEY,
  content_id        TEXT    NOT NULL REFERENCES atom_content(content_id),
  layer             TEXT    NOT NULL CHECK (layer IN ('raw','daily','core')),
  body_row_id       TEXT    NOT NULL,
  ordinal           INTEGER NOT NULL CHECK (ordinal >= 0),
  byte_start        INTEGER NOT NULL CHECK (byte_start >= 0),
  byte_end          INTEGER NOT NULL CHECK (byte_end > byte_start),
  row_content_hash  TEXT    NOT NULL,          -- sha256(whole row bytes)
  splitter_version  INTEGER NOT NULL,
  role              TEXT    NOT NULL CHECK (role IN (
                      'owner_utterance','maez_response','observation',
                      'reasoning','digest','external','unknown')),
  parse_status      TEXT    NOT NULL CHECK (parse_status IN (
                      'boundary_parsed','turn_linked_half',
                      'unparsed_container')),
  pair_id           TEXT,
  provenance_source TEXT,                       -- copied verbatim, never re-derived
  trust_tier        TEXT,
  door_site         TEXT    NOT NULL,           -- which of the five doors (§2)
  observed_late     INTEGER NOT NULL DEFAULT 0 CHECK (observed_late IN (0,1)),
  created_ts        REAL    NOT NULL,
  UNIQUE (layer, body_row_id, ordinal, splitter_version)
) STRICT;

-- Reassembly witness: one row per observed body row.
CREATE TABLE row_reassembly (
  layer            TEXT    NOT NULL CHECK (layer IN ('raw','daily','core')),
  body_row_id      TEXT    NOT NULL,
  splitter_version INTEGER NOT NULL,
  row_content_hash TEXT    NOT NULL,
  atom_count       INTEGER NOT NULL CHECK (atom_count > 0),
  covered_bytes    INTEGER NOT NULL,
  row_bytes        INTEGER NOT NULL,
  reassembly_ok    INTEGER NOT NULL CHECK (reassembly_ok IN (0,1)),
  PRIMARY KEY (layer, body_row_id, splitter_version)
) STRICT;

-- Lineage: edges are the only source of the known count (B5).
CREATE TABLE lineage_edges (
  child_id  TEXT NOT NULL,
  parent_id TEXT NOT NULL,
  relation  TEXT NOT NULL CHECK (relation IN (
              'consolidated_from','promoted_from','derived_from')),
  edge_ts   REAL NOT NULL,
  PRIMARY KEY (child_id, parent_id, relation)
) STRICT;

-- No known_edge_count column: it is COUNTed, never self-reported (B5).
CREATE TABLE lineage_summary (
  child_id            TEXT    NOT NULL PRIMARY KEY,
  declared_count      INTEGER NOT NULL CHECK (declared_count >= 0),
  unknown_parent_count INTEGER NOT NULL CHECK (unknown_parent_count >= 0),
  source_key          TEXT    NOT NULL,
  summary_ts          REAL    NOT NULL
) STRICT;

-- Every non-observation is a row, never an absence.
CREATE TABLE observation_gaps (
  gap_id      TEXT    NOT NULL PRIMARY KEY,
  layer       TEXT,
  body_row_id TEXT,
  gap_class   TEXT    NOT NULL CHECK (gap_class IN (
                'HISTORICAL_UNTRACEABLE','UNOBSERVED_BY_SCOPE',
                'WRITE_FAILED','QUEUE_OVERFLOW','CAPACITY_STOP',
                'CRASH_WINDOW')),
  reason      TEXT    NOT NULL,
  detected_ts REAL    NOT NULL
) STRICT;

-- Append-only enforced by the database, not by intention (B20).
CREATE TRIGGER atom_content_no_update BEFORE UPDATE ON atom_content
  BEGIN SELECT RAISE(ABORT, 'append-only'); END;
CREATE TRIGGER atom_content_no_delete BEFORE DELETE ON atom_content
  BEGIN SELECT RAISE(ABORT, 'append-only'); END;
-- ...identical pairs for every table above.
```

**Binding invariants (B3) — each recomputable from stored data alone:**
1. `content_id == sha256(atom_content.bytes)`.
2. `atom_embeddings.vector_hash == sha256(vector)` and the vector
   re-embeds from `bytes` under `contract_hash`.
3. `byte_end - byte_start == byte_len` for the occurrence's content.
4. For each `(layer, body_row_id, splitter_version)`: occurrences
   ordered by `ordinal` tile `[0, row_bytes)` with no gap and no
   overlap, and their concatenation hashes to `row_content_hash`.
5. `COUNT(lineage_edges WHERE child_id=X) + unknown_parent_count ==
   declared_count`. The known side is counted, never stored.

A self-consistent but false receipt is now impossible for 1–4 because
the bytes that would falsify it are in the same file.

## 4. Byte domain (B16)

The unit is **the exact Chroma document string, encoded strict UTF-8**
— not original network or LLM bytes, some of which were already
`.strip()`ped upstream. Codex verified round-trip preservation on the
real store: 44,037 raw, 40 daily, 134 core documents preserved exactly,
including Unicode, newlines, tabs, and trailing whitespace, so the
document string is a sound domain.

Physical-row reassembly (invariant 4) is distinct from synthetic
paired-turn assembly: `pair_id` may relate two atoms, but a pair is
never reassembled into a row and never claims to be one.

## 5. Failure posture (B9, B18)

- **Writes are enqueued after the live write succeeds**, drained by a
  single writer thread within the daemon. Admission is on the reply
  path (unavoidable — memories are written before delivery at
  `daemon/maez_daemon.py:9676`); admission is a bounded, non-blocking
  append that never raises. Draining is off-path.
- **Gap receipts do not live in the medium that failed.** They are
  appended to `memory/db/spine/spine_gaps.jsonl` — separate file,
  separate descriptor, fsync per line, and mirrored into
  `observation_gaps` when the database is writable again. Pass 2's
  contradiction — promising a durable GAP receipt to the same SQLite
  domain that is full or locked — is removed.
- **Queue overflow writes a `QUEUE_OVERFLOW` gap line**, not merely an
  in-memory counter (B9).
- **Capacity floor:** when free space falls below the numeric floor
  (F8), the spine writes one `CAPACITY_STOP` gap line and stops
  writing. It never deletes to make room and never blocks a reply.
- **Crash window:** on daemon start, rows in the live store newer than
  the spine's high-water mark and not observed produce `CRASH_WINDOW`
  gaps. Late observation is allowed (marked `observed_late=1`) only
  while the bytes are still present at the recorded id; if curation has
  relocated the row (`scripts/metabolic_curation.py:370`), the gap
  stands permanently.
- **Multi-process (B18):** the daemon holds the writer. Web/script
  writes are recorded once as `UNOBSERVED_BY_SCOPE` and never counted
  as observed. This is a smaller promise, kept.

## 6. Backup (B10)

Filenames are fixed and enumerable: `memory/db/spine/spine.sqlite3`
(+ WAL/SHM) and `spine_gaps.jsonl`. Required before S0 lands:
`_SQLITE_FILENAMES_INSIDE_DIRS` at `scripts/backup/backup.py:129` — a
frozenset that currently contains only `chroma.sqlite3` — gains
`spine.sqlite3`; the `.jsonl` copies flat.

**"Restore matches" is defined** as: identical row counts per table,
identical `sha256` over a canonical ordered dump of every table, the
five invariants of §3 re-verified on the restored file, and a canary
row present. F9 executes exactly that.

## 7. Retention and privacy (B11)

One file, lifetime, no deletion, no rotation in v0. Growth is measured
daily (bytes/day) with a **numeric** kill: projected 12-month size
> 5 GB, or free space on the volume < 10 GB, ⇒ the design is wrong and
rotation must be gated before the spine continues (F8).

The spine stores memory bytes, so it inherits the store's sensitivity
exactly: directory `0700`, files `0600`, verified per backup run (F10).
`chat_id` is stored as it already appears in live metadata — no new
exposure class is created, and none is laundered away either.

## 8. Falsifiers — 10, each executable, each owned by a slice

Every falsifier below ships with its harness **in the slice that
introduces it**; a slice is not done until its harness runs green from
a clean checkout. Corpus manifests are generated at S0 and pinned
(sha256 recorded in the slice commit), which is what pass 2's table
lacked.

| # | Falsifier | Harness | Slice | Kill |
|---|---|---|---|---|
| F1 | Invariants §3.1–3.4 hold for every row | `scripts/spine/verify_invariants.py` over the whole file | S1 | any violation |
| F2 | Twin rule: two occurrences of identical bytes share one `content_id`; distinct occurrences remain distinct rows | pinned twin manifest built at S0 from real duplicate rows | S1 | shared occurrence row, or split content row |
| F3 | Reassembly: for 100% of observed rows, ordered atoms tile the row with no gap/overlap and hash to `row_content_hash` | same harness as F1, reported separately | S1 | any row < 100% |
| F4 | Token bound: `token_count` **recomputed** from stored bytes with the pinned tokenizer ≤ contract limit | `verify_invariants.py --tokens` | S1 | any atom over |
| F5 | Vector sensitivity, tokenizer-visible (B17): mutations pre-registered as changing token IDs (verified by tokenizing both sides) change the atom vector | `scripts/spine/mutation_probe.py`, pinned mutation set | S1 | < 95% of tokenizer-visible mutations change the vector |
| F6 | Door coverage: each of the five `.add(` sites produces an observation; AST count of `.add(` sites in `memory_manager.py` == 5 | `tests/test_spine_doors.py` | S1 | any door unobserved, or count drift |
| F7 | Lineage: `COUNT(edges) + unknown_parent_count == declared_count` for every child, counted not reported | `verify_invariants.py --lineage` | S2 | any child violating |
| F8 | Capacity: measured bytes/day; simulated free-space breach writes `CAPACITY_STOP` to the JSONL and stops writing without blocking a turn | `tests/test_spine_capacity.py` with a faked `statvfs` | S1 | projected 12-month > 5 GB, free < 10 GB, or a blocked turn |
| F9 | Backup/restore: spine backed up under live writes restores to the §6 definition of "matches" | `tests/test_spine_backup_restore.py` | S0 | any mismatch |
| F10 | Modes + write confinement: `0700`/`0600` verified; the writer refuses any path outside `memory/db/spine/`; the existing bypass audit is green (now green at 61c6655) | `tests/test_spine_confinement.py` | S0 | wrong mode or any out-of-tree write |
| F11 | Crash: injected kills between live write and drain produce a `CRASH_WINDOW` gap line, never a silent absence | `tests/test_spine_crash.py`, ≥50 injections | S1 | any unrecorded miss |
| F12 | Flags-off ⇒ zero cost: no spine import, no SQLite open, no file created — asserted at the call site | `tests/test_spine_dormant.py` | S0 | any touch |

Deferred falsifiers (F2/F9 of pass 2 — neighborhood stability, encoder
parity) belong to the recall design, not this one, and leave with it.

## 9. Slices

- **S0** — file, DDL, triggers, modes, flags
  (`MAEZ_EVIDENCE_SPINE_SHADOW` / `_ENABLED` via `def _entry(...)`
  `core/cockpit/flags.py:65`, read through `def strict_env_flag(...)`
  `core/infra/env_flags.py:23`), gap JSONL, backup routing. Witness:
  F9, F10, F12.
- **S1** — atomization at all five doors, all three layers, plus the
  queue/gap machinery. Witness: F1–F6, F8, F11.
- **S2** — lineage edges + summary at `consolidate_daily` and
  `store_core`. Witness: F7.

Then, and only then, a separate design pass for recall events and
prompt exposures, with its own gate.

## 10. What this claims, exactly

That every atom's bytes are stored, its vector recomputable from those
bytes, its place in its row provable, its ancestry either recorded or
counted as unknown, and every non-observation written down as a row.

Not that meaning is captured. Not that importance is measured. Not that
the record is complete — only that its incompleteness is visible.
