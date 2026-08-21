# Evidence-Atom Spine — design pass 5 (batch derivation, full DDL)

Status: DESIGN, pass 5. Gate history: pass 1 BLOCKED (12), pass 2
(10 open + 8 new), pass 3 (8 closed, 6 open, 1 new), pass 4 (1 closed,
6 open, 5 new; **5/13 falsifiers executable**). Round reports at
`2026-08-21-spine-gate-round{1,2,3,4}.md`. Scope remains D1+D2 only.

## 0. Two admissions, then the change

**Admission 1 — I described the fix instead of writing it.** Pass 4
said triggers were "written out per table." The gate counted the
committed document: **one `CREATE TABLE`, zero `CREATE TRIGGER`.** I
wrote a table of attacks-and-fixes in prose and called it DDL. That is
precisely the laundering this repo's doctrine exists to catch, and it
was mine. §3 of this pass is the complete schema, literally.

**Admission 2 — my architecture was inside a corruption window.**
Pass 4 had the observer fire inside the chokepoint in every writing
process (daemon + web + GUI), i.e. multiple connections writing and
checkpointing a WAL database concurrently. This host runs SQLite
**3.46.1** (`libsqlite3-0:amd64 3.46.1-9ubuntu0.2`, verified directly
via `sqlite3.sqlite_version` and `dpkg`). SQLite documents a WAL-reset
corruption bug affecting versions through 3.51.2 under exactly that
topology, fixed in 3.51.3 with backports to 3.44.6 / 3.50.7 — none
present in this package. Recorded as a repo-wide hazard, not just a
spine one.

### The change: derive, don't observe

The spine no longer hooks the write path at all. It is a **batch
deriver**: a single-process job that reads the live store and
atomizes what it finds.

This is not a patch; it deletes the defect class:

| Defect | Why it is gone |
|---|---|
| B18, N24 multi-process writers, WAL corruption window | one process, one writer, ever |
| N23 causal gap labels indistinguishable | no queue, no crash window — a row either exists at scan time or it does not |
| B9 durable-overflow impossibility | no queue to overflow |
| reply-path hazard (`daemon/maez_daemon.py:9676` stores before broadcast) | nothing runs on the reply path; no lazy open, no hashing, no tokenization |
| F11 crash injection | the batch is idempotent and restartable; a killed run re-derives |
| F12 flags-off cost | it is a separate script the daemon never imports |

What it costs, stated plainly: a row written and then removed by
curation **before the batch runs is never atomized**. That is N22, and
it is unavoidable for any design — pass 4 only appeared to solve it.
The batch answers it honestly instead (§4).

## 1. Scope

D1 atoms · D2 lineage. Measured: over-limit rows raw 3,571/44,037
(8.11%, max 2,910 tok), daily 24/40 (**60.00%**), core 10/134 (7.46%);
lineage 16/82 rows carry `,+N` (19.51%), 2,948/4,700 declared ancestor
edges (**62.72%**) have no recorded id. D3/D4 remain deferred with
their own gate (gate-confirmed honest, not reopened).

## 2. How the batch runs

Single process, invoked by cron or by hand, never by the daemon:

1. Open the live stores **read-only, immutable URI**. The spine never
   holds a write handle to Chroma.
2. Record a `scan_runs` row: start time, per-layer row count, and the
   **scan watermark** — the set boundary the run could see.
3. For each layer, for each row id not already atomized under the
   current `splitter_version`: read the document, split, store atoms,
   record correspondence *at observation time* (§4), derive lineage.
4. Close the run: end time, counts, and the derived
   `HISTORICAL_UNTRACEABLE` / `PRE_SPINE` classes.

Idempotent by construction: re-running derives nothing new, because
`(layer, body_row_id, splitter_version)` is unique. Interrupt at any
point and re-run; there is no partial-write class to reason about.

## 3. The schema — complete, literal

```sql
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;
PRAGMA recursive_triggers = ON;
PRAGMA busy_timeout = 5000;

CREATE TABLE embedding_contracts (
  contract_hash     TEXT NOT NULL PRIMARY KEY
                    CHECK (length(contract_hash) = 64
                           AND contract_hash NOT GLOB '*[^0-9a-f]*'),
  contract_json     TEXT NOT NULL,
  model_name        TEXT NOT NULL,
  model_artifact_sha TEXT,          -- NULL => artifact unavailable, see §5
  tokenizer_id      TEXT NOT NULL,
  truncation_tokens INTEGER NOT NULL CHECK (truncation_tokens > 0),
  dimensions        INTEGER NOT NULL CHECK (dimensions > 0),
  package_version   TEXT NOT NULL,
  recorded_ts       REAL NOT NULL
) STRICT;

CREATE TABLE scan_runs (
  run_id        TEXT NOT NULL PRIMARY KEY,
  started_ts    REAL NOT NULL,
  finished_ts   REAL,
  raw_seen      INTEGER NOT NULL DEFAULT 0,
  daily_seen    INTEGER NOT NULL DEFAULT 0,
  core_seen     INTEGER NOT NULL DEFAULT 0,
  splitter_version INTEGER NOT NULL CHECK (splitter_version >= 0),
  status        TEXT NOT NULL CHECK (status IN ('running','complete','aborted'))
) STRICT;

CREATE TABLE atom_content (
  content_id  TEXT NOT NULL PRIMARY KEY
              CHECK (length(content_id) = 64
                     AND content_id NOT GLOB '*[^0-9a-f]*'),
  bytes       BLOB NOT NULL,
  byte_len    INTEGER NOT NULL CHECK (byte_len > 0 AND byte_len = length(bytes)),
  created_ts  REAL NOT NULL
) STRICT;

CREATE TABLE atom_embeddings (
  content_id    TEXT NOT NULL REFERENCES atom_content(content_id),
  contract_hash TEXT NOT NULL REFERENCES embedding_contracts(contract_hash),
  vector        BLOB NOT NULL CHECK (length(vector) % 4 = 0),
  vector_hash   TEXT NOT NULL CHECK (length(vector_hash) = 64
                                     AND vector_hash NOT GLOB '*[^0-9a-f]*'),
  token_count   INTEGER NOT NULL CHECK (token_count > 0),
  embed_ts      REAL NOT NULL,
  PRIMARY KEY (content_id, contract_hash)
) STRICT;

-- vector length must match the contract's declared dimensions
CREATE TRIGGER emb_dim_match BEFORE INSERT ON atom_embeddings
BEGIN
  SELECT RAISE(ABORT, 'vector length != contract dimensions * 4')
  WHERE (SELECT dimensions FROM embedding_contracts
         WHERE contract_hash = NEW.contract_hash) * 4 <> length(NEW.vector);
  SELECT RAISE(ABORT, 'token_count exceeds contract truncation limit')
  WHERE NEW.token_count > (SELECT truncation_tokens FROM embedding_contracts
                           WHERE contract_hash = NEW.contract_hash);
END;

CREATE TABLE atom_occurrences (
  occurrence_id TEXT NOT NULL PRIMARY KEY
                CHECK (length(occurrence_id) = 64
                       AND occurrence_id NOT GLOB '*[^0-9a-f]*'),
  content_id    TEXT NOT NULL REFERENCES atom_content(content_id),
  run_id        TEXT NOT NULL REFERENCES scan_runs(run_id),
  layer         TEXT NOT NULL CHECK (layer IN ('raw','daily','core')),
  body_row_id   TEXT NOT NULL,
  ordinal       INTEGER NOT NULL CHECK (ordinal >= 0),
  byte_start    INTEGER NOT NULL CHECK (byte_start >= 0),
  byte_end      INTEGER NOT NULL CHECK (byte_end > byte_start),
  row_content_hash TEXT NOT NULL CHECK (length(row_content_hash) = 64
                       AND row_content_hash NOT GLOB '*[^0-9a-f]*'),
  splitter_version INTEGER NOT NULL CHECK (splitter_version >= 0),
  role          TEXT NOT NULL CHECK (role IN (
                  'owner_utterance','maez_response','observation',
                  'reasoning','digest','external','unknown')),
  parse_status  TEXT NOT NULL CHECK (parse_status IN (
                  'boundary_parsed','turn_linked_half','unparsed_container')),
  pair_id       TEXT,
  provenance_source TEXT,
  trust_tier    TEXT,
  observed_ts   REAL NOT NULL,
  CHECK (parse_status <> 'turn_linked_half' OR pair_id IS NOT NULL),
  UNIQUE (layer, body_row_id, ordinal, splitter_version),
  UNIQUE (layer, body_row_id, byte_start, byte_end, splitter_version)
) STRICT;

-- span length must equal the referenced content's byte length
CREATE TRIGGER occ_span_matches_content BEFORE INSERT ON atom_occurrences
BEGIN
  SELECT RAISE(ABORT, 'span length != content byte_len')
  WHERE (NEW.byte_end - NEW.byte_start) <>
        (SELECT byte_len FROM atom_content WHERE content_id = NEW.content_id);
END;

CREATE TABLE lineage_edges (
  child_id  TEXT NOT NULL,
  parent_id TEXT NOT NULL,
  relation  TEXT NOT NULL CHECK (relation IN (
              'consolidated_from','promoted_from','derived_from')),
  parent_resolved INTEGER NOT NULL CHECK (parent_resolved IN (0,1)),
  run_id    TEXT NOT NULL REFERENCES scan_runs(run_id),
  edge_ts   REAL NOT NULL,
  PRIMARY KEY (child_id, parent_id, relation)
) STRICT;

CREATE TABLE lineage_summary (
  child_id             TEXT NOT NULL PRIMARY KEY,
  declared_count       INTEGER NOT NULL CHECK (declared_count >= 0),
  unknown_parent_count INTEGER NOT NULL CHECK (unknown_parent_count >= 0),
  source_key           TEXT NOT NULL,
  run_id               TEXT NOT NULL REFERENCES scan_runs(run_id),
  summary_ts           REAL NOT NULL
) STRICT;

-- the summary is SEALED: arithmetic checked at insert, and no edge may
-- be added for a child that already has one (closes the "valid summary
-- then an extra edge" attack)
CREATE TRIGGER lineage_summary_arithmetic BEFORE INSERT ON lineage_summary
BEGIN
  SELECT RAISE(ABORT, 'known + unknown != declared')
  WHERE (SELECT COUNT(*) FROM lineage_edges WHERE child_id = NEW.child_id)
        + NEW.unknown_parent_count <> NEW.declared_count;
END;

CREATE TRIGGER lineage_edges_after_seal BEFORE INSERT ON lineage_edges
BEGIN
  SELECT RAISE(ABORT, 'child already sealed by a summary')
  WHERE EXISTS (SELECT 1 FROM lineage_summary WHERE child_id = NEW.child_id);
END;

CREATE TABLE observation_gaps (
  layer       TEXT CHECK (layer IS NULL OR layer IN ('raw','daily','core')),
  body_row_id TEXT,
  gap_class   TEXT NOT NULL CHECK (gap_class IN (
                'HISTORICAL_UNTRACEABLE','PRE_SPINE','ROW_VANISHED',
                'UNREADABLE_DOCUMENT','CONTRACT_UNAVAILABLE')),
  reason      TEXT NOT NULL,
  run_id      TEXT NOT NULL REFERENCES scan_runs(run_id),
  detected_ts REAL NOT NULL,
  PRIMARY KEY (layer, body_row_id, gap_class)     -- no duplicate gap rows
) STRICT;

-- Verification is a RUN, not a forgeable per-row flag.
CREATE TABLE verification_runs (
  verify_id   TEXT NOT NULL PRIMARY KEY,
  started_ts  REAL NOT NULL,
  finished_ts REAL,
  scope       TEXT NOT NULL CHECK (scope IN ('full','incremental')),
  result      TEXT CHECK (result IN ('PASS','FAIL','UNVERIFIABLE')),
  detail_json TEXT
) STRICT;

CREATE TABLE verification_findings (
  verify_id TEXT NOT NULL REFERENCES verification_runs(verify_id),
  check_id  TEXT NOT NULL,
  subject   TEXT NOT NULL,
  outcome   TEXT NOT NULL CHECK (outcome IN ('pass','fail','unverifiable')),
  note      TEXT,
  PRIMARY KEY (verify_id, check_id, subject)
) STRICT;

-- Append-only, written out per table. No summarising comment.
CREATE TRIGGER embedding_contracts_no_update BEFORE UPDATE ON embedding_contracts
  BEGIN SELECT RAISE(ABORT, 'append-only'); END;
CREATE TRIGGER embedding_contracts_no_delete BEFORE DELETE ON embedding_contracts
  BEGIN SELECT RAISE(ABORT, 'append-only'); END;
CREATE TRIGGER atom_content_no_update BEFORE UPDATE ON atom_content
  BEGIN SELECT RAISE(ABORT, 'append-only'); END;
CREATE TRIGGER atom_content_no_delete BEFORE DELETE ON atom_content
  BEGIN SELECT RAISE(ABORT, 'append-only'); END;
CREATE TRIGGER atom_embeddings_no_update BEFORE UPDATE ON atom_embeddings
  BEGIN SELECT RAISE(ABORT, 'append-only'); END;
CREATE TRIGGER atom_embeddings_no_delete BEFORE DELETE ON atom_embeddings
  BEGIN SELECT RAISE(ABORT, 'append-only'); END;
CREATE TRIGGER atom_occurrences_no_update BEFORE UPDATE ON atom_occurrences
  BEGIN SELECT RAISE(ABORT, 'append-only'); END;
CREATE TRIGGER atom_occurrences_no_delete BEFORE DELETE ON atom_occurrences
  BEGIN SELECT RAISE(ABORT, 'append-only'); END;
CREATE TRIGGER lineage_edges_no_update BEFORE UPDATE ON lineage_edges
  BEGIN SELECT RAISE(ABORT, 'append-only'); END;
CREATE TRIGGER lineage_edges_no_delete BEFORE DELETE ON lineage_edges
  BEGIN SELECT RAISE(ABORT, 'append-only'); END;
CREATE TRIGGER lineage_summary_no_update BEFORE UPDATE ON lineage_summary
  BEGIN SELECT RAISE(ABORT, 'append-only'); END;
CREATE TRIGGER lineage_summary_no_delete BEFORE DELETE ON lineage_summary
  BEGIN SELECT RAISE(ABORT, 'append-only'); END;
CREATE TRIGGER observation_gaps_no_update BEFORE UPDATE ON observation_gaps
  BEGIN SELECT RAISE(ABORT, 'append-only'); END;
CREATE TRIGGER observation_gaps_no_delete BEFORE DELETE ON observation_gaps
  BEGIN SELECT RAISE(ABORT, 'append-only'); END;
CREATE TRIGGER verification_findings_no_update BEFORE UPDATE ON verification_findings
  BEGIN SELECT RAISE(ABORT, 'append-only'); END;
CREATE TRIGGER verification_findings_no_delete BEFORE DELETE ON verification_findings
  BEGIN SELECT RAISE(ABORT, 'append-only'); END;
-- scan_runs and verification_runs permit exactly one UPDATE: closing an
-- open run. Enforced by predicate, not by convention.
CREATE TRIGGER scan_runs_close_only BEFORE UPDATE ON scan_runs
BEGIN
  SELECT RAISE(ABORT, 'only an open run may be closed')
  WHERE OLD.finished_ts IS NOT NULL
     OR NEW.run_id <> OLD.run_id
     OR NEW.started_ts <> OLD.started_ts;
END;
CREATE TRIGGER scan_runs_no_delete BEFORE DELETE ON scan_runs
  BEGIN SELECT RAISE(ABORT, 'append-only'); END;
CREATE TRIGGER verification_runs_close_only BEFORE UPDATE ON verification_runs
BEGIN
  SELECT RAISE(ABORT, 'only an open run may be closed')
  WHERE OLD.finished_ts IS NOT NULL OR NEW.verify_id <> OLD.verify_id;
END;
CREATE TRIGGER verification_runs_no_delete BEFORE DELETE ON verification_runs
  BEGIN SELECT RAISE(ABORT, 'append-only'); END;
```

Notes on specific attacks the gate landed:

- `door_site` is **gone** — the batch has no doors to record.
- `reassembly_ok` is **gone** as a stored flag; forging it was possible
  because "verifier-only" was an application convention. Tiling is now
  a `verification_findings` row tied to a run.
- Non-hex 64-char hashes are rejected by `NOT GLOB '*[^0-9a-f]*'`.
- `byte_len = length(bytes)` and span-vs-content-length are enforced.
- Duplicate gap rows are impossible (composite PK).
- `turn_linked_half` without `pair_id` is rejected.
- An extra edge after a sealed summary is rejected.

What DDL still cannot enforce, by nature: that `content_id` truly
hashes its bytes, that a vector re-embeds, and that a `body_row_id`
exists in the live store. Those are §5.

## 4. Correspondence, honestly (closes N22's second half)

Correspondence is verified **at observation time** and recorded then:
the row existed in that layer and its document hashed to
`row_content_hash`, witnessed under `run_id` with `observed_ts`.

Later re-verification therefore has **three** outcomes, not two:
`pass`, `fail` (the row exists and its bytes differ — a real alarm),
and `unverifiable` (the row is no longer at that id, e.g. curation
relocated it at `scripts/metabolic_curation.py:370`). Pass 4 would have
called that third case a failure and slandered an honest receipt.

Rows removed before the batch ever saw them are `ROW_VANISHED` /
`PRE_SPINE` and are never claimed as observed.

## 5. The verifier as an admission boundary

`scripts/spine/verify.py` recomputes rather than trusts: `sha256`,
re-embedding, tokenization, tiling, lineage arithmetic, and live
correspondence. It writes a `verification_runs` row and per-check
findings.

Two rules make it a boundary rather than a diagnostic:
1. **Fail-closed consumption.** No consumer may read spine rows whose
   most recent covering verification run is not `PASS`. A later organ
   asking "is this atom evidence?" gets `no` unless verification says
   yes.
2. **`UNVERIFIABLE` is a first-class result** — e.g. the model artifact
   named by `model_artifact_sha` is absent, so a vector cannot be
   recomputed. That is neither pass nor fail, and it is never silently
   coerced (the same discipline as the examined-life organ's
   `UNRECONCILABLE`).

`canonical(contract_json)` is defined: JSON with sorted keys, no
insignificant whitespace, UTF-8, LF — `json.dumps(obj, sort_keys=True,
separators=(",", ":"), ensure_ascii=False)`.

## 6. Falsifiers — 11, with the artifact each needs

| # | Falsifier | Artifact / definition | Kill |
|---|---|---|---|
| F1 | `content_id == sha256(bytes)`; `byte_len == length(bytes)`; vector re-embeds to `vector_hash` under the registry contract | canonical JSON per §5; vector serialized little-endian float32; artifact absent ⇒ `unverifiable`, not pass | any mismatch |
| F2 | Correspondence at observation time; re-verify yields pass/fail/unverifiable per §4 | live store read-only | any `fail` |
| F3 | Tiling: ordered atoms cover each row with no gap/overlap and hash to `row_content_hash` | internal | any row < 100% |
| F4 | `token_count` recomputed **equals** the stored value and ≤ limit | registry tokenizer_id + truncation_tokens; special tokens included as the encoder counts them | any mismatch |
| F5 | Tokenizer-visible mutation changes the vector | `tests/data/spine_mutations.json`: ≥50 entries, each pre-verified to change token ids, seed recorded, sha256 pinned in the slice commit; "changes" = cosine < 0.9999 | < 95% |
| F6 | Coverage: every live row present at the run's watermark is atomized or has a gap row | scan_runs watermark | any row neither |
| F7 | `COUNT(edges) + unknown_parent_count == declared_count`, and every `parent_resolved = 1` edge names a row that existed at scan time | internal + live store | any violation |
| F8 | Capacity: bytes/day over a 7-day window, linear annualization | numerator = spine file size delta; day = UTC midnight | projected > 5 GB/yr or free < 10 GB |
| F9 | Backup/restore: canonical dump matches | tables ordered by name, rows by PK, `.mode quote`, LF; canary = a fixed sentinel `scan_runs` row; batch quiesced during capture (no live-write linearization problem, because the spine has no live writer) | any mismatch |
| F10 | Write confinement by **inode**, not path string | compare `st_dev`/`st_ino` of the target against the allowlisted tree; rejects hardlinks, which `Path.resolve()` cannot (closes N26) | any escape |
| F11 | Append-only + pragma enforcement: every trigger fires; `open_spine()` is the only opener; a connection without the pragmas is refused | AST test forbidding other `sqlite3.connect` on the spine path, including aliased/dynamic opens | any bypass |

Gone with the architecture: crash-injection, queue-overflow, and
flags-off-cost falsifiers — there is no queue, no crash window, and
nothing imported by the daemon.

## 7. Slices

- **S0** — schema + `open_spine()` + confinement + backup routing.
  Witness: F9, F10, F11.
- **S1** — the batch deriver: atoms, embeddings, correspondence, gaps.
  Witness: F1–F6, F8.
- **S2** — lineage derivation. Witness: F7.
- **S3** — the verifier and the fail-closed consumption boundary.

## 8. What this claims

That the spine records what existed when it looked, proves each atom's
bytes and vector recomputable, proves each atom's place in its row,
records ancestry or counts it unknown, and refuses to be read as
evidence unless verification currently passes.

Not meaning. Not importance. Not organ-readiness (N21 withdrawal
stands). Not completeness — only that incompleteness is visible and
that the boundary of the last look is written down.
