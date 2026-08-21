# Evidence-Atom Spine — design pass 6

Status: DESIGN, pass 6. Gate: pass 1 BLOCKED (12) → pass 2 (10 open, 8
new) → pass 3 (8 closed) → pass 4 (1 closed, 5 new) → pass 5 (**4
dissolved by architecture, 1 closed**, 6 open, 5 new; 5/11 falsifiers
executable). Reports at `2026-08-21-spine-gate-round{1..5}.md`. Scope
unchanged: D1 atoms + D2 lineage; D3/D4 deferred with their own gate.

Pass 5's batch reframe was ruled a genuine dissolution, not a dodge:
blockers 9 and 18 and N23/N24 **cannot occur** without a queue, hooks,
or multi-process writer. Pass 6 fixes what the reframe exposed.

## 0. The finding that mattered most

The gate proved `immutable=1` returns **stale** data on a WAL database
— not torn, missing. Independently reproduced here:

```
mode=ro              -> ['checkpointed', 'wal-only']
mode=ro&immutable=1  -> ['checkpointed']          # committed row LOST
```

Pass 5's §2 said "read-only, immutable URI." That would have built the
spine on a false snapshot: atoms derived from a store the spine could
not fully see, which is D1's own disease reproduced in the cure.

**Scope check performed before raising an alarm:** Maez's live Chroma
stores are in `delete` (rollback-journal) mode with no WAL sidecars
(`raw`, `daily`, `core` all verified). So the probes run during this
session's foundation work were *not* affected, and their numbers stand.
The hazard is real; it did not touch our measurements. It is recorded
next to the SQLite WAL multi-writer hazard as an instrument caveat.

## 1. Source-snapshot protocol (closes N27, gives F6/F7 their authority)

The batch no longer reads the live store directly. Each run:

1. **Online backup** each live layer (`sqlite3` backup API) into a
   private, disposable snapshot directory the spine owns. SQLite
   guarantees a completed online backup is a consistent copy.
2. Compute a **snapshot digest** (sha256 of the copied file) and a
   **row manifest**: the full sorted id list per layer, and its sha256.
3. Read the snapshot with `mode=ro&immutable=1` — now legitimate,
   because the copy genuinely cannot change.
4. Store digest + manifest hash + row counts in `scan_runs`, and the
   ids themselves in `scan_membership`.
5. Delete the snapshot at run end.

The manifest **is** the watermark: "what this run could see" is a
recorded set, not a time window. It also gives lineage a membership
oracle — `parent_resolved = 1` means "present in this run's manifest,"
which is now checkable rather than asserted (N25).

If a backup cannot be taken, the run aborts. It never falls back to
reading a moving store.

## 2. Honest limits (N22, and what cannot be claimed)

A row written and removed before **any** scan is unknowable. Pass 5
would have labelled it `ROW_VANISHED`/`PRE_SPINE`, which is a claim
about something never observed.

Corrected: `ROW_VANISHED` may be recorded **only** for an id present in
a prior run's `scan_membership` and absent from this run's. Rows never
seen are not labelled at all, and the spine states in its own output
that its coverage begins at the first run's manifest. Not knowing is
reported as not knowing.

## 3. What SQLite cannot defend, said plainly (blocker 20)

The gate removed an append-only trigger via `PRAGMA writable_schema`,
and plain `DROP TRIGGER` did the same. That is not fixable inside
SQLite: **a process with write access to the file can always rewrite
the rules.**

So the claim changes from *prevented* to *prevented-and-detected*:

- Triggers stop accidents, bugs, and ordinary mistakes — the realistic
  threat for a single-writer batch job.
- **Schema attestation** catches the rest: `sha256` over
  `sqlite_schema` (sorted, normalized) is recorded at S0 and re-checked
  at the start of every run and every verification. A removed or
  altered trigger fails the check.
- The verifier's own findings are content-addressed, so a tampered file
  fails re-verification even if the schema were restored afterwards.

This is the honest form: integrity by detection, with the boundary
stated, rather than a prevention claim that a five-line SQL session
can falsify.

## 4. DDL — corrections since pass 5

Only the changed constructs are shown; the rest of pass 5's schema
stands (it was confirmed 14/14 against the named attacks).

```sql
-- (a) N31: the old composite PK made gap identity effectively NOT NULL,
-- contradicting the classes that have no row identity. Split them.
CREATE TABLE observation_gaps (
  gap_id      TEXT NOT NULL PRIMARY KEY
              CHECK (length(gap_id) = 64 AND gap_id NOT GLOB '*[^0-9a-f]*'),
  layer       TEXT NOT NULL CHECK (layer IN ('raw','daily','core')),
  body_row_id TEXT NOT NULL,
  gap_class   TEXT NOT NULL CHECK (gap_class IN (
                'ROW_VANISHED','UNREADABLE_DOCUMENT','CONTRACT_UNAVAILABLE')),
  reason      TEXT NOT NULL,
  run_id      TEXT NOT NULL REFERENCES scan_runs(run_id),
  detected_ts REAL NOT NULL,
  UNIQUE (layer, body_row_id, gap_class, run_id)
) STRICT;

-- Run-scoped classes have no row identity and live in their own table.
CREATE TABLE coverage_notes (
  run_id     TEXT NOT NULL REFERENCES scan_runs(run_id),
  note_class TEXT NOT NULL CHECK (note_class IN (
               'COVERAGE_BEGINS_HERE','HISTORICAL_UNTRACEABLE','SNAPSHOT_FAILED')),
  detail     TEXT NOT NULL,
  noted_ts   REAL NOT NULL,
  PRIMARY KEY (run_id, note_class)
) STRICT;

-- (b) N27/F6/N25: the manifest is the watermark and the membership oracle.
CREATE TABLE scan_membership (
  run_id      TEXT NOT NULL REFERENCES scan_runs(run_id),
  layer       TEXT NOT NULL CHECK (layer IN ('raw','daily','core')),
  body_row_id TEXT NOT NULL,
  PRIMARY KEY (run_id, layer, body_row_id)
) STRICT;

-- scan_runs gains the snapshot bindings (replacing bare counts).
ALTER TABLE scan_runs ADD COLUMN raw_manifest_sha   TEXT;
ALTER TABLE scan_runs ADD COLUMN daily_manifest_sha TEXT;
ALTER TABLE scan_runs ADD COLUMN core_manifest_sha  TEXT;
ALTER TABLE scan_runs ADD COLUMN schema_attestation TEXT;

-- (c) N29: per-row completion. A row counts as atomized ONLY with a
-- marker written in the same transaction as its atoms.
CREATE TABLE row_atomized (
  layer            TEXT NOT NULL CHECK (layer IN ('raw','daily','core')),
  body_row_id      TEXT NOT NULL,
  splitter_version INTEGER NOT NULL CHECK (splitter_version >= 0),
  run_id           TEXT NOT NULL REFERENCES scan_runs(run_id),
  atom_count       INTEGER NOT NULL CHECK (atom_count > 0),
  row_content_hash TEXT NOT NULL,
  completed_ts     REAL NOT NULL,
  PRIMARY KEY (layer, body_row_id, splitter_version)
) STRICT;
CREATE TRIGGER row_atomized_no_update BEFORE UPDATE ON row_atomized
  BEGIN SELECT RAISE(ABORT, 'append-only'); END;
CREATE TRIGGER row_atomized_no_delete BEFORE DELETE ON row_atomized
  BEGIN SELECT RAISE(ABORT, 'append-only'); END;

-- (d) N28: PASS is DERIVED, never asserted. A run may close as PASS
-- only with zero non-pass findings and coverage equal to its scan.
CREATE TRIGGER verification_pass_is_earned BEFORE UPDATE ON verification_runs
BEGIN
  SELECT RAISE(ABORT, 'PASS with non-pass findings')
  WHERE NEW.result = 'PASS'
    AND EXISTS (SELECT 1 FROM verification_findings
                WHERE verify_id = NEW.verify_id AND outcome <> 'pass');
  SELECT RAISE(ABORT, 'PASS without full coverage')
  WHERE NEW.result = 'PASS'
    AND (SELECT COUNT(*) FROM verification_findings
         WHERE verify_id = NEW.verify_id AND check_id = 'row_covered')
        <> (SELECT COUNT(*) FROM scan_membership WHERE run_id = NEW.scan_run_id);
  SELECT RAISE(ABORT, 'result set without finishing')
  WHERE NEW.result IS NOT NULL AND NEW.finished_ts IS NULL;
END;

-- (e) blocker 3: invalid contract JSON is no longer admitted, and the
-- artifact hash is mandatory (absent artifact => UNVERIFIABLE, not PASS).
--   contract_json  TEXT NOT NULL CHECK (json_valid(contract_json))
--   model_artifact_sha TEXT NOT NULL CHECK (length(model_artifact_sha) = 64)
```

Also fixed: `verification_runs` gains `scan_run_id` (bound coverage);
`scan_runs`' close-only trigger extended to freeze counts, splitter
version, and status once `finished_ts` is set (pass 5 left them mutable
while open — gate-confirmed).

**`occurrence_id` formula (N30), previously unstated:**
`sha256(layer ‖ 0x00 ‖ body_row_id ‖ 0x00 ‖ ordinal ‖ 0x00 ‖
splitter_version)`. Tiling (F3) is evaluated **per
`(layer, body_row_id, splitter_version)`**, so two splitter versions
coexist without ambiguity.

## 5. Confinement (N26, ATTACH)

Inode membership cannot reject an external hardlink to an allowed
inode — the gate's probe returned membership=true. Replaced with
creation-time control:

- Files are created with `O_CREAT|O_EXCL|O_NOFOLLOW` in a directory the
  spine owns (`0700`), and `st_nlink == 1` is asserted on open. A
  hardlinked file has `st_nlink > 1` and is refused.
- An **authorizer callback** on every spine connection denies
  `SQLITE_ATTACH` and `SQLITE_DETACH`, closing the ATTACH escape.
- `open_spine()` is the only opener; it sets **and verifies**
  `foreign_keys`, `recursive_triggers`, WAL, `busy_timeout`, and
  refuses a connection where any verification fails (the gate's
  fresh-connection bypass).

## 6. Falsifiers — the six that were unexecutable, and what makes them run

| # | Was missing | Now |
|---|---|---|
| F1 | model resolver, contract binding | `model_artifact_sha` NOT NULL; artifact absent ⇒ `unverifiable`; `contract_hash` = sha256 of canonical JSON, re-derived by the verifier |
| F2 | snapshot protocol, membership | §1 backup snapshot + `scan_membership`; three outcomes (pass/fail/unverifiable) unchanged |
| F4 | tokenizer resolver, invocation | registry `tokenizer_id` + `truncation_tokens`; recomputed count must **equal** stored |
| F5 | fixture absent | `tests/data/spine_mutations.json` is an **S0 deliverable**: ≥50 entries, each pre-verified to change token ids, seed + sha256 pinned in the S0 commit. Named honestly as not-yet-existing |
| F6 | watermark, per-row completion | `scan_membership` + `row_atomized` |
| F7 | membership authority | `parent_resolved` checked against `scan_membership` |
| F8/F10/F11 | were RED | F8 measures spine dir size incl. sidecars; F10 uses O_EXCL/O_NOFOLLOW/`st_nlink`; F11 asserts pragma verification on a fresh connection |
| F12 (new) | — | **Schema attestation**: `sqlite_schema` hash matches the S0 record at every run |

## 7. Slices

S0 schema + `open_spine()` + confinement + attestation + backup routing
+ mutation fixture · S1 batch deriver (snapshot, manifest, atoms,
per-row completion) · S2 lineage · S3 verifier + fail-closed
consumption.

## 8. What this claims

The spine records what a consistent snapshot contained, names the
boundary of that snapshot, proves each atom's bytes and vector
recomputable from a recorded contract, proves each atom's place in its
row, records ancestry or counts it unknown, refuses to be read as
evidence unless a covering verification currently passes, and detects
tampering it cannot prevent.

Not meaning. Not importance. Not organ-readiness (N21 stands). Not
completeness — only that the edges of what it knows are written down.
