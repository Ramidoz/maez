# Evidence-Atom Spine — design pass 7 (one complete schema)

Status: DESIGN, pass 7. Gate: pass 1 (12 blockers) → 2 (10 open, 8 new)
→ 3 (8 closed) → 4 (1 closed, 5 new) → 5 (4 dissolved, 1 closed, 5 new)
→ 6 (**1 closed, 10 open**; 17 false receipts admitted). Reports at
`2026-08-21-spine-gate-round{1..6}.md`. Scope unchanged: D1 atoms +
D2 lineage; D3/D4 deferred with their own gate.

## 0. Why round 6 admitted so much — and the correction

Pass 6 was a **delta document**: "only the changed constructs are
shown, the rest of pass 5's schema stands." The gate had to reconstruct
a "strongest charitable assembly," and the seams between the two passes
were exactly where 17 false receipts walked through. A schema described
across two documents is not a schema.

Pass 7 is therefore **one complete, executable file** — 14 tables, 38
triggers, instantiated and attacked before being written down. No
deltas, no "the rest still stands."

## 1. My capture-order derivation was wrong

Pass 6 derived "children first, parents last" from the fact that
ancestry points backwards in time. The gate found the counterexample:
with child-first capture, a parent row created *after* the child
snapshot still appears in the later parent manifest — and membership
alone cannot tell "was already there" from "appeared afterwards". That
turns a future-created row into **false ancestry**. Undercounting is
safe; inventing ancestry is not.

**Corrected: capture parents first (raw → daily → core)**, which the
gate calls proof-safe, and pay the undercount. And the proof is no
longer trusted to ordering at all — it is enforced (§2, `edge_resolution_is_proved`):
a parent may be marked resolved only if it is in this run's membership
for its own layer **and** that layer's capture boundary closed no later
than the child layer's boundary opened. Every unproved edge is
`parent_resolved = 0` and counts as unknown.

Measured snapshot cost (executed, read-only, live stores): raw 191.0 ms
/ 516.76 MB / 44,037 ids; daily 2.2 ms / 3.51 MB / 92 ids; core 1.8 ms
/ 2.89 MB / 208 ids. Total **195 ms, 523 MB transient**, 327.8 GB free.

## 2. The schema

Every hash column is 64 lowercase hex, enforced. Every table is
append-only by trigger. `scan_runs.run_ordinal` and
`verification_runs.verify_ordinal` are UNIQUE and monotonic, which is
what makes "the most recent covering verification" a defined query
rather than a wish.

```sql
PRAGMA foreign_keys = ON;
PRAGMA recursive_triggers = ON;

CREATE TABLE embedding_contracts (
  contract_hash TEXT NOT NULL PRIMARY KEY
    CHECK (length(contract_hash)=64 AND contract_hash NOT GLOB '*[^0-9a-f]*'),
  contract_json TEXT NOT NULL CHECK (json_valid(contract_json)),
  model_name TEXT NOT NULL,
  model_artifact_sha TEXT NOT NULL
    CHECK (length(model_artifact_sha)=64 AND model_artifact_sha NOT GLOB '*[^0-9a-f]*'),
  tokenizer_id TEXT NOT NULL,
  truncation_tokens INTEGER NOT NULL CHECK (truncation_tokens > 0),
  dimensions INTEGER NOT NULL CHECK (dimensions > 0),
  package_version TEXT NOT NULL,
  recorded_ts REAL NOT NULL
) STRICT;

CREATE TABLE scan_runs (
  run_id TEXT NOT NULL PRIMARY KEY
    CHECK (length(run_id)=64 AND run_id NOT GLOB '*[^0-9a-f]*'),
  run_ordinal INTEGER NOT NULL UNIQUE CHECK (run_ordinal > 0),
  started_ts REAL NOT NULL,
  finished_ts REAL,
  splitter_version INTEGER NOT NULL CHECK (splitter_version >= 0),
  schema_attestation TEXT NOT NULL
    CHECK (length(schema_attestation)=64 AND schema_attestation NOT GLOB '*[^0-9a-f]*'),
  status TEXT NOT NULL CHECK (status IN ('running','complete','aborted'))
) STRICT;

CREATE TABLE scan_layers (
  run_id TEXT NOT NULL REFERENCES scan_runs(run_id),
  layer TEXT NOT NULL CHECK (layer IN ('raw','daily','core')),
  capture_order INTEGER NOT NULL CHECK (capture_order > 0),
  boundary_start_ts REAL NOT NULL,
  boundary_end_ts REAL NOT NULL CHECK (boundary_end_ts >= boundary_start_ts),
  snapshot_digest TEXT NOT NULL
    CHECK (length(snapshot_digest)=64 AND snapshot_digest NOT GLOB '*[^0-9a-f]*'),
  manifest_sha TEXT NOT NULL
    CHECK (length(manifest_sha)=64 AND manifest_sha NOT GLOB '*[^0-9a-f]*'),
  row_count INTEGER NOT NULL CHECK (row_count >= 0),
  PRIMARY KEY (run_id, layer)
) STRICT;

CREATE TABLE scan_membership (
  run_id TEXT NOT NULL,
  layer TEXT NOT NULL CHECK (layer IN ('raw','daily','core')),
  body_row_id TEXT NOT NULL,
  PRIMARY KEY (run_id, layer, body_row_id),
  FOREIGN KEY (run_id, layer) REFERENCES scan_layers(run_id, layer)
) STRICT;

CREATE TABLE atom_content (
  content_id TEXT NOT NULL PRIMARY KEY
    CHECK (length(content_id)=64 AND content_id NOT GLOB '*[^0-9a-f]*'),
  bytes BLOB NOT NULL,
  byte_len INTEGER NOT NULL CHECK (byte_len > 0 AND byte_len = length(bytes)),
  created_ts REAL NOT NULL
) STRICT;

CREATE TABLE atom_embeddings (
  content_id TEXT NOT NULL REFERENCES atom_content(content_id),
  contract_hash TEXT NOT NULL REFERENCES embedding_contracts(contract_hash),
  vector BLOB NOT NULL,
  vector_hash TEXT NOT NULL
    CHECK (length(vector_hash)=64 AND vector_hash NOT GLOB '*[^0-9a-f]*'),
  token_count INTEGER NOT NULL CHECK (token_count > 0),
  embed_ts REAL NOT NULL,
  PRIMARY KEY (content_id, contract_hash)
) STRICT;

CREATE TRIGGER emb_matches_contract BEFORE INSERT ON atom_embeddings
BEGIN
  SELECT RAISE(ABORT,'vector length != dimensions*4')
  WHERE (SELECT dimensions FROM embedding_contracts
         WHERE contract_hash=NEW.contract_hash)*4 <> length(NEW.vector);
  SELECT RAISE(ABORT,'token_count over contract limit')
  WHERE NEW.token_count > (SELECT truncation_tokens FROM embedding_contracts
                           WHERE contract_hash=NEW.contract_hash);
END;

CREATE TABLE atom_occurrences (
  occurrence_id TEXT NOT NULL PRIMARY KEY
    CHECK (length(occurrence_id)=64 AND occurrence_id NOT GLOB '*[^0-9a-f]*'),
  content_id TEXT NOT NULL REFERENCES atom_content(content_id),
  run_id TEXT NOT NULL REFERENCES scan_runs(run_id),
  layer TEXT NOT NULL CHECK (layer IN ('raw','daily','core')),
  body_row_id TEXT NOT NULL,
  ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
  byte_start INTEGER NOT NULL CHECK (byte_start >= 0),
  byte_end INTEGER NOT NULL CHECK (byte_end > byte_start),
  row_content_hash TEXT NOT NULL
    CHECK (length(row_content_hash)=64 AND row_content_hash NOT GLOB '*[^0-9a-f]*'),
  splitter_version INTEGER NOT NULL CHECK (splitter_version >= 0),
  role TEXT NOT NULL CHECK (role IN ('owner_utterance','maez_response',
    'observation','reasoning','digest','external','unknown')),
  parse_status TEXT NOT NULL CHECK (parse_status IN
    ('boundary_parsed','turn_linked_half','unparsed_container')),
  pair_id TEXT,
  provenance_source TEXT,
  trust_tier TEXT,
  observed_ts REAL NOT NULL,
  CHECK (parse_status <> 'turn_linked_half' OR pair_id IS NOT NULL),
  UNIQUE (layer, body_row_id, ordinal, splitter_version),
  UNIQUE (layer, body_row_id, byte_start, byte_end, splitter_version)
) STRICT;

CREATE TABLE row_atomized (
  layer TEXT NOT NULL CHECK (layer IN ('raw','daily','core')),
  body_row_id TEXT NOT NULL,
  splitter_version INTEGER NOT NULL CHECK (splitter_version >= 0),
  run_id TEXT NOT NULL REFERENCES scan_runs(run_id),
  atom_count INTEGER NOT NULL CHECK (atom_count > 0),
  row_content_hash TEXT NOT NULL
    CHECK (length(row_content_hash)=64 AND row_content_hash NOT GLOB '*[^0-9a-f]*'),
  completed_ts REAL NOT NULL,
  PRIMARY KEY (layer, body_row_id, splitter_version)
) STRICT;

-- occurrence: must be in this run's membership, version-consistent, unsealed
CREATE TRIGGER occ_guards BEFORE INSERT ON atom_occurrences
BEGIN
  SELECT RAISE(ABORT,'span length != content byte_len')
  WHERE (NEW.byte_end-NEW.byte_start) <>
        (SELECT byte_len FROM atom_content WHERE content_id=NEW.content_id);
  SELECT RAISE(ABORT,'row not in this run membership')
  WHERE NOT EXISTS (SELECT 1 FROM scan_membership
    WHERE run_id=NEW.run_id AND layer=NEW.layer AND body_row_id=NEW.body_row_id);
  SELECT RAISE(ABORT,'splitter_version != run splitter_version')
  WHERE NEW.splitter_version <>
        (SELECT splitter_version FROM scan_runs WHERE run_id=NEW.run_id);
  SELECT RAISE(ABORT,'row already sealed by a completion marker')
  WHERE EXISTS (SELECT 1 FROM row_atomized WHERE layer=NEW.layer
    AND body_row_id=NEW.body_row_id AND splitter_version=NEW.splitter_version);
END;

-- marker: must match the atoms that exist, and the run version
CREATE TRIGGER marker_binds_atoms BEFORE INSERT ON row_atomized
BEGIN
  SELECT RAISE(ABORT,'atom_count != actual occurrences')
  WHERE NEW.atom_count <> (SELECT COUNT(*) FROM atom_occurrences
    WHERE layer=NEW.layer AND body_row_id=NEW.body_row_id
      AND splitter_version=NEW.splitter_version);
  SELECT RAISE(ABORT,'row_content_hash disagrees with its atoms')
  WHERE EXISTS (SELECT 1 FROM atom_occurrences
    WHERE layer=NEW.layer AND body_row_id=NEW.body_row_id
      AND splitter_version=NEW.splitter_version
      AND row_content_hash <> NEW.row_content_hash);
  SELECT RAISE(ABORT,'splitter_version != run splitter_version')
  WHERE NEW.splitter_version <>
        (SELECT splitter_version FROM scan_runs WHERE run_id=NEW.run_id);
END;

CREATE TABLE lineage_edges (
  child_id TEXT NOT NULL,
  child_layer TEXT NOT NULL CHECK (child_layer IN ('raw','daily','core')),
  parent_id TEXT NOT NULL,
  parent_layer TEXT NOT NULL CHECK (parent_layer IN ('raw','daily','core')),
  relation TEXT NOT NULL CHECK (relation IN
    ('consolidated_from','promoted_from','derived_from')),
  parent_resolved INTEGER NOT NULL CHECK (parent_resolved IN (0,1)),
  run_id TEXT NOT NULL REFERENCES scan_runs(run_id),
  edge_ts REAL NOT NULL,
  PRIMARY KEY (child_id, parent_id, relation)
) STRICT;

-- resolved means: the parent was in THIS run's membership for its layer,
-- and its layer boundary closed no later than the child's (temporal proof)
CREATE TRIGGER edge_resolution_is_proved BEFORE INSERT ON lineage_edges
BEGIN
  SELECT RAISE(ABORT,'parent_resolved=1 without membership proof')
  WHERE NEW.parent_resolved=1 AND NOT EXISTS (SELECT 1 FROM scan_membership
    WHERE run_id=NEW.run_id AND layer=NEW.parent_layer AND body_row_id=NEW.parent_id);
  SELECT RAISE(ABORT,'parent_resolved=1 without temporal proof')
  WHERE NEW.parent_resolved=1 AND
    (SELECT boundary_end_ts FROM scan_layers
      WHERE run_id=NEW.run_id AND layer=NEW.parent_layer) >
    (SELECT boundary_start_ts FROM scan_layers
      WHERE run_id=NEW.run_id AND layer=NEW.child_layer);
END;

CREATE TABLE lineage_summary (
  child_id TEXT NOT NULL PRIMARY KEY,
  declared_count INTEGER NOT NULL CHECK (declared_count >= 0),
  unknown_parent_count INTEGER NOT NULL CHECK (unknown_parent_count >= 0),
  source_key TEXT NOT NULL,
  run_id TEXT NOT NULL REFERENCES scan_runs(run_id),
  summary_ts REAL NOT NULL
) STRICT;

CREATE TRIGGER lineage_summary_arithmetic BEFORE INSERT ON lineage_summary
BEGIN
  SELECT RAISE(ABORT,'known + unknown != declared')
  WHERE (SELECT COUNT(*) FROM lineage_edges WHERE child_id=NEW.child_id)
        + NEW.unknown_parent_count <> NEW.declared_count;
END;

CREATE TRIGGER lineage_edges_after_seal BEFORE INSERT ON lineage_edges
BEGIN
  SELECT RAISE(ABORT,'child already sealed')
  WHERE EXISTS (SELECT 1 FROM lineage_summary WHERE child_id=NEW.child_id);
END;

CREATE TABLE observation_gaps (
  gap_id TEXT NOT NULL PRIMARY KEY
    CHECK (length(gap_id)=64 AND gap_id NOT GLOB '*[^0-9a-f]*'),
  layer TEXT NOT NULL CHECK (layer IN ('raw','daily','core')),
  body_row_id TEXT NOT NULL,
  gap_class TEXT NOT NULL CHECK (gap_class IN
    ('ROW_VANISHED','UNREADABLE_DOCUMENT','CONTRACT_UNAVAILABLE')),
  reason TEXT NOT NULL,
  run_id TEXT NOT NULL REFERENCES scan_runs(run_id),
  detected_ts REAL NOT NULL,
  UNIQUE (layer, body_row_id, gap_class, run_id)
) STRICT;

-- ROW_VANISHED requires prior observation (N22), by run_ordinal
CREATE TRIGGER vanished_requires_prior_sighting BEFORE INSERT ON observation_gaps
BEGIN
  SELECT RAISE(ABORT,'ROW_VANISHED for a never-observed row')
  WHERE NEW.gap_class='ROW_VANISHED' AND NOT EXISTS (
    SELECT 1 FROM scan_membership m JOIN scan_runs r ON r.run_id=m.run_id
    WHERE m.layer=NEW.layer AND m.body_row_id=NEW.body_row_id
      AND r.run_ordinal < (SELECT run_ordinal FROM scan_runs WHERE run_id=NEW.run_id));
END;

CREATE TABLE coverage_notes (
  run_id TEXT NOT NULL REFERENCES scan_runs(run_id),
  note_class TEXT NOT NULL CHECK (note_class IN
    ('COVERAGE_BEGINS_HERE','HISTORICAL_UNTRACEABLE','SNAPSHOT_FAILED')),
  detail TEXT NOT NULL,
  noted_ts REAL NOT NULL,
  PRIMARY KEY (run_id, note_class)
) STRICT;

CREATE TABLE verification_runs (
  verify_id TEXT NOT NULL PRIMARY KEY
    CHECK (length(verify_id)=64 AND verify_id NOT GLOB '*[^0-9a-f]*'),
  scan_run_id TEXT NOT NULL REFERENCES scan_runs(run_id),
  verify_ordinal INTEGER NOT NULL UNIQUE CHECK (verify_ordinal > 0),
  started_ts REAL NOT NULL,
  finished_ts REAL,
  scope TEXT NOT NULL CHECK (scope IN ('full','incremental')),
  result TEXT CHECK (result IN ('PASS','FAIL','UNVERIFIABLE')),
  detail_json TEXT
) STRICT;

CREATE TABLE verification_findings (
  verify_id TEXT NOT NULL REFERENCES verification_runs(verify_id),
  check_id TEXT NOT NULL,
  subject TEXT NOT NULL,
  outcome TEXT NOT NULL CHECK (outcome IN ('pass','fail','unverifiable')),
  note TEXT,
  PRIMARY KEY (verify_id, check_id, subject)
) STRICT;

-- findings may only be added to an OPEN run (no late fail after PASS)
CREATE TRIGGER findings_only_while_open BEFORE INSERT ON verification_findings
BEGIN
  SELECT RAISE(ABORT,'finding added to a closed verification run')
  WHERE (SELECT finished_ts FROM verification_runs
         WHERE verify_id=NEW.verify_id) IS NOT NULL;
  SELECT RAISE(ABORT,'row_covered subject not in the scan membership')
  WHERE NEW.check_id='row_covered' AND NOT EXISTS (
    SELECT 1 FROM scan_membership m
    JOIN verification_runs v ON v.scan_run_id=m.run_id
    WHERE v.verify_id=NEW.verify_id
      AND (m.layer || '/' || m.body_row_id) = NEW.subject);
END;

-- PASS is EARNED, on INSERT and on UPDATE, by MEMBERSHIP not cardinality
CREATE TRIGGER verify_pass_earned_insert BEFORE INSERT ON verification_runs
BEGIN
  SELECT RAISE(ABORT,'closed-with-result insert is not permitted')
  WHERE NEW.result IS NOT NULL;
END;

CREATE TRIGGER verify_pass_earned_update BEFORE UPDATE ON verification_runs
BEGIN
  SELECT RAISE(ABORT,'only an open run may be closed')
  WHERE OLD.finished_ts IS NOT NULL OR NEW.verify_id <> OLD.verify_id
     OR NEW.scan_run_id <> OLD.scan_run_id OR NEW.started_ts <> OLD.started_ts;
  SELECT RAISE(ABORT,'result set without finishing')
  WHERE NEW.result IS NOT NULL AND NEW.finished_ts IS NULL;
  SELECT RAISE(ABORT,'PASS with non-pass findings')
  WHERE NEW.result='PASS' AND EXISTS (SELECT 1 FROM verification_findings
    WHERE verify_id=NEW.verify_id AND outcome<>'pass');
  SELECT RAISE(ABORT,'PASS without covering every membership row')
  WHERE NEW.result='PASS' AND EXISTS (
    SELECT 1 FROM scan_membership m WHERE m.run_id=NEW.scan_run_id
      AND NOT EXISTS (SELECT 1 FROM verification_findings f
        WHERE f.verify_id=NEW.verify_id AND f.check_id='row_covered'
          AND f.subject = (m.layer || '/' || m.body_row_id)));
  SELECT RAISE(ABORT,'scan already has a PASS')
  WHERE NEW.result='PASS' AND EXISTS (SELECT 1 FROM verification_runs
    WHERE scan_run_id=NEW.scan_run_id AND result='PASS' AND verify_id<>NEW.verify_id);
END;

-- membership is frozen once its scan closes
CREATE TRIGGER membership_frozen_after_close BEFORE INSERT ON scan_membership
BEGIN
  SELECT RAISE(ABORT,'membership insert after scan close')
  WHERE (SELECT finished_ts FROM scan_runs WHERE run_id=NEW.run_id) IS NOT NULL;
END;

CREATE TRIGGER scan_runs_close_only BEFORE UPDATE ON scan_runs
BEGIN
  SELECT RAISE(ABORT,'only an open run may be closed')
  WHERE OLD.finished_ts IS NOT NULL OR NEW.run_id<>OLD.run_id
     OR NEW.run_ordinal<>OLD.run_ordinal OR NEW.started_ts<>OLD.started_ts
     OR NEW.splitter_version<>OLD.splitter_version
     OR NEW.schema_attestation<>OLD.schema_attestation;
END;

CREATE TRIGGER embedding_contracts_no_update BEFORE UPDATE ON embedding_contracts
  BEGIN SELECT RAISE(ABORT,'append-only'); END;
CREATE TRIGGER embedding_contracts_no_delete BEFORE DELETE ON embedding_contracts
  BEGIN SELECT RAISE(ABORT,'append-only'); END;
CREATE TRIGGER scan_runs_no_delete BEFORE DELETE ON scan_runs
  BEGIN SELECT RAISE(ABORT,'append-only'); END;
CREATE TRIGGER scan_layers_no_update BEFORE UPDATE ON scan_layers
  BEGIN SELECT RAISE(ABORT,'append-only'); END;
CREATE TRIGGER scan_layers_no_delete BEFORE DELETE ON scan_layers
  BEGIN SELECT RAISE(ABORT,'append-only'); END;
CREATE TRIGGER scan_membership_no_update BEFORE UPDATE ON scan_membership
  BEGIN SELECT RAISE(ABORT,'append-only'); END;
CREATE TRIGGER scan_membership_no_delete BEFORE DELETE ON scan_membership
  BEGIN SELECT RAISE(ABORT,'append-only'); END;
CREATE TRIGGER atom_content_no_update BEFORE UPDATE ON atom_content
  BEGIN SELECT RAISE(ABORT,'append-only'); END;
CREATE TRIGGER atom_content_no_delete BEFORE DELETE ON atom_content
  BEGIN SELECT RAISE(ABORT,'append-only'); END;
CREATE TRIGGER atom_embeddings_no_update BEFORE UPDATE ON atom_embeddings
  BEGIN SELECT RAISE(ABORT,'append-only'); END;
CREATE TRIGGER atom_embeddings_no_delete BEFORE DELETE ON atom_embeddings
  BEGIN SELECT RAISE(ABORT,'append-only'); END;
CREATE TRIGGER atom_occurrences_no_update BEFORE UPDATE ON atom_occurrences
  BEGIN SELECT RAISE(ABORT,'append-only'); END;
CREATE TRIGGER atom_occurrences_no_delete BEFORE DELETE ON atom_occurrences
  BEGIN SELECT RAISE(ABORT,'append-only'); END;
CREATE TRIGGER row_atomized_no_update BEFORE UPDATE ON row_atomized
  BEGIN SELECT RAISE(ABORT,'append-only'); END;
CREATE TRIGGER row_atomized_no_delete BEFORE DELETE ON row_atomized
  BEGIN SELECT RAISE(ABORT,'append-only'); END;
CREATE TRIGGER lineage_edges_no_update BEFORE UPDATE ON lineage_edges
  BEGIN SELECT RAISE(ABORT,'append-only'); END;
CREATE TRIGGER lineage_edges_no_delete BEFORE DELETE ON lineage_edges
  BEGIN SELECT RAISE(ABORT,'append-only'); END;
CREATE TRIGGER lineage_summary_no_update BEFORE UPDATE ON lineage_summary
  BEGIN SELECT RAISE(ABORT,'append-only'); END;
CREATE TRIGGER lineage_summary_no_delete BEFORE DELETE ON lineage_summary
  BEGIN SELECT RAISE(ABORT,'append-only'); END;
CREATE TRIGGER observation_gaps_no_update BEFORE UPDATE ON observation_gaps
  BEGIN SELECT RAISE(ABORT,'append-only'); END;
CREATE TRIGGER observation_gaps_no_delete BEFORE DELETE ON observation_gaps
  BEGIN SELECT RAISE(ABORT,'append-only'); END;
CREATE TRIGGER coverage_notes_no_update BEFORE UPDATE ON coverage_notes
  BEGIN SELECT RAISE(ABORT,'append-only'); END;
CREATE TRIGGER coverage_notes_no_delete BEFORE DELETE ON coverage_notes
  BEGIN SELECT RAISE(ABORT,'append-only'); END;
CREATE TRIGGER verification_runs_no_delete BEFORE DELETE ON verification_runs
  BEGIN SELECT RAISE(ABORT,'append-only'); END;
CREATE TRIGGER verification_findings_no_update BEFORE UPDATE ON verification_findings
  BEGIN SELECT RAISE(ABORT,'append-only'); END;
CREATE TRIGGER verification_findings_no_delete BEFORE DELETE ON verification_findings
  BEGIN SELECT RAISE(ABORT,'append-only'); END;
```


## 2.1 Pass 7.1 — four holes I found in my own schema

Before the gate reported, I ran the round-7 attack directions against
pass 7 myself. Four succeeded. Fixed and retested in both directions:

| Self-attack | Fix |
|---|---|
| A run closes `complete` while membership rows have **neither** atoms **nor** a gap row — silent incompleteness wearing a completed badge | `scan_complete_requires_full_disposition`: every membership row must have a completion marker or a gap row |
| A run records `SNAPSHOT_FAILED`, then closes `complete` anyway — laundering a failed scan | `snapshot_failure_forces_abort`: such a run may only close `aborted` |
| A `lineage_summary` for a child that appears in no membership — ancestry for a memory the run never saw | `lineage_summary_child_is_real` |
| `run_ordinal` advancing while `started_ts` goes backwards, so "the prior run" and "the most recent verification" stop meaning the same thing | `run_ordinal_monotonic_with_time` |

Honest paths re-checked, not just the forbidden ones: a run **does**
close `complete` once every membership row is disposed, and a
snapshot-failed run **does** close as `aborted`.

**One attack I deliberately did NOT block.** Two runs may share a
`snapshot_digest` and `manifest_sha`. That looked like
cross-contamination, but it is the honest signature of *nothing having
changed between runs* — identical id lists hash identically. Blocking
it would reject a true state. The real obligation is a verifier check:
`manifest_sha` must equal the hash of the membership actually recorded
for that run. Restriction is not the same as correctness.


## 2.2 Pass 7.2 — two more, and the line between schema and verifier

| Self-attack | Outcome |
|---|---|
| Atoms of one row attributed to a **different** row in the same layer | Partially closable: the schema cannot see live bytes, but it can refuse a row whose atoms **disagree about their own row hash** — now enforced at insert, not only at seal (`occ_row_hash_consistent`) |
| **Gap spam**: dispose every row as a gap instead of investigating, then close `complete` | A gap is sometimes the truth, so it is not forbidden — it is made **undeniable**: a run closing `complete` with any gaps must first declare them in a coverage note (`gaps_must_be_declared_before_complete`) |

The wrong-row attack is the honest boundary of what any schema can do.
A *fully* self-consistent misattribution — every atom of row B carrying
row A's content and A's hash — is invisible inside the file, because
the truth is in the live store. It cannot earn a PASS: the verifier's
`row_covered` check reads the real row, hashes it, and fails. So the
receipt can exist but can never be read as evidence.

That is the division this design keeps making: the **schema** stops
what is expressible in the file, the **verifier** stops what requires
the world, and PASS is withheld until the verifier has spoken for every
row. Neither half is sufficient; naming which is which is what keeps
the claim honest.


## 2.3 Over-restriction check — an honest run must still complete

Seven rounds of adversarial review create a real pull toward proving
rigor by refusing more. A schema that blocks honest work is a failed
schema, so the design is checked in the constructive direction too: a
complete lifecycle, start to consumable evidence, with **16 steps and
zero blocks**.

1–5 open a run, capture `raw` then `daily` (parents first), record
membership for 3 rows, register the embedding contract.
6–9 atomize a row into two atoms that tile it exactly, embed both under
the contract, record the occurrences, seal the row.
10–11 atomize and seal the remaining raw row and the daily digest.
12 record lineage: one **proved** parent (membership + boundary) and
one honestly **unknown** ancestor, declared count 2.
13 close the run `complete` — permitted because every membership row is
disposed and there are no gaps.
14–16 open a verification run, record `row_covered` for every
membership row, close as `PASS`.

Result: the most recent covering verification reads `PASS`, so the run
is consumable as evidence; 4 atoms, 3 sealed rows, ancestry recorded as
1 known + 1 unknown.

This is the shape the whole design is for: a memory that is fully
visible, provably placed in its row, with ancestry that says exactly
how much it does not know — and no step of it is blocked by the rules
that stop the forgeries.

## 3. What the schema now refuses (round 6's admitted list, retested)

All executed in-memory against the file above; honest operations
re-checked in the same run so the rules are not merely restrictive.

| Round-6 attack | Now |
|---|---|
| Bogus `row_covered` subject not in membership | **rejected** |
| Verification run INSERTed already closed as PASS | **rejected** |
| Fail finding appended after PASS | **rejected** |
| Second contradictory PASS for one scan | **rejected** |
| Atom occurrence for a row not in membership | **rejected** |
| Occurrence whose `splitter_version` ≠ its run's | **rejected** |
| Completion marker whose `atom_count` lies | **rejected** |
| Marker with no atoms at all | **rejected** |
| Atom added after the row was sealed | **rejected** |
| `parent_resolved=1` for a nonexistent parent | **rejected** |
| `ROW_VANISHED` for a never-observed row | **rejected** |
| One-character manifest hash | **rejected** |
| Non-hex artifact hash / invalid contract JSON | **rejected** |
| Membership inserted after scan close; membership UPDATE/DELETE | **rejected** |
| PASS covering 1 of 2 membership rows | **rejected** |

Still ALLOWED, deliberately: an honest occurrence; an honest marker; a
resolved edge with membership **and** temporal proof; an honest PASS
covering every membership row; and a later verification run closing as
**FAIL** — honest disagreement must remain expressible.

## 4. What SQLite still cannot enforce (and the honest answer)

- `content_id == sha256(bytes)`, the vector re-embedding, the
  `occurrence_id` formula, and tiling are **verifier** obligations —
  SQLite has no sha256. They are bound to PASS by requiring a
  `row_covered` finding for **every** membership row, so a run that
  skipped them cannot close as PASS.
- `PRAGMA writable_schema` / `DROP TRIGGER` can still remove rules
  (gate round 5, executed). Answer unchanged and stated as a boundary:
  **detection, not prevention** — `schema_attestation` is recorded per
  run and re-checked; a removed trigger fails the check.

## 5. Unchanged from pass 6

Source-snapshot protocol (online backup → digest → manifest → immutable
read of the copy); `immutable=1` never used on a live store (it
silently omits committed WAL rows — reproduced); coverage begins at the
first manifest and says so; confinement by `O_EXCL|O_NOFOLLOW` +
`st_nlink` + ATTACH authorizer + pragma-verifying `open_spine()`; F5
fixture now exists (`tests/data/spine_mutations.json`, 73 entries,
oracle validated 73/73).

## 6. What this claims

The spine records what a consistent snapshot contained, names that
snapshot's boundary per layer, proves each atom's bytes and vector
recomputable from a recorded contract, proves each atom's place in its
row, marks ancestry resolved only with membership **and** temporal
proof, refuses to read as evidence without a covering PASS, and detects
tampering it cannot prevent.

Not meaning. Not importance. Not organ-readiness. Not completeness —
only that the edges of what it knows are written down.
