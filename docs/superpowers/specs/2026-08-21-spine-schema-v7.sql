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
  child_layer TEXT NOT NULL CHECK (child_layer IN ('raw','daily','core')),
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

-- ============================================================
-- pass 7.1: holes found by Claude's own round-7 self-attack
-- ============================================================

-- (1) SILENT INCOMPLETENESS: a run may not close 'complete' while any
-- row in its membership has neither a completion marker nor a gap row.
CREATE TRIGGER scan_complete_requires_full_disposition
BEFORE UPDATE ON scan_runs
BEGIN
  SELECT RAISE(ABORT,'complete with undisposed membership rows')
  WHERE NEW.status='complete' AND EXISTS (
    SELECT 1 FROM scan_membership m
    WHERE m.run_id=NEW.run_id
      AND NOT EXISTS (SELECT 1 FROM row_atomized a
            WHERE a.layer=m.layer AND a.body_row_id=m.body_row_id
              AND a.splitter_version=NEW.splitter_version)
      AND NOT EXISTS (SELECT 1 FROM observation_gaps g
            WHERE g.run_id=NEW.run_id AND g.layer=m.layer
              AND g.body_row_id=m.body_row_id));
END;

-- (2) LAUNDERING: a run carrying SNAPSHOT_FAILED may only close 'aborted'.
CREATE TRIGGER snapshot_failure_forces_abort BEFORE UPDATE ON scan_runs
BEGIN
  SELECT RAISE(ABORT,'snapshot failed: this run may only abort')
  WHERE NEW.status='complete' AND EXISTS (
    SELECT 1 FROM coverage_notes
    WHERE run_id=NEW.run_id AND note_class='SNAPSHOT_FAILED');
END;

-- (3) PHANTOM CHILD: a lineage summary requires the child to be a row
-- this run actually saw.
CREATE TRIGGER lineage_summary_child_is_real BEFORE INSERT ON lineage_summary
BEGIN
  -- layer-qualified: a 'daily' child may not borrow a 'raw' row's membership
  SELECT RAISE(ABORT,'lineage summary for a child not in run membership for its layer')
  WHERE NOT EXISTS (SELECT 1 FROM scan_membership
    WHERE run_id=NEW.run_id AND layer=NEW.child_layer AND body_row_id=NEW.child_id);
END;

-- (4) ORDINAL/TIME DISAGREEMENT: run_ordinal must advance with time, or
-- "the prior run" and "the most recent verification" mean two things.
CREATE TRIGGER run_ordinal_monotonic_with_time BEFORE INSERT ON scan_runs
BEGIN
  SELECT RAISE(ABORT,'run_ordinal not greater than every prior ordinal')
  WHERE NEW.run_ordinal <= COALESCE((SELECT MAX(run_ordinal) FROM scan_runs),0);
  SELECT RAISE(ABORT,'started_ts not later than every prior start')
  WHERE NEW.started_ts <= COALESCE((SELECT MAX(started_ts) FROM scan_runs),-1e18);
END;

-- ============================================================
-- pass 7.2: two more self-found holes
-- ============================================================

-- (5) WRONG-ROW ATTRIBUTION: atoms of one row attributed to another.
-- The schema cannot see live bytes, but it CAN refuse a row whose atoms
-- disagree about their own row hash -- failing at insert, not at seal.
CREATE TRIGGER occ_row_hash_consistent BEFORE INSERT ON atom_occurrences
BEGIN
  SELECT RAISE(ABORT,'row_content_hash disagrees with existing atoms of this row')
  WHERE EXISTS (SELECT 1 FROM atom_occurrences
    WHERE layer=NEW.layer AND body_row_id=NEW.body_row_id
      AND splitter_version=NEW.splitter_version
      AND row_content_hash <> NEW.row_content_hash);
END;

-- (6) GAP SPAM: disposing rows as gaps instead of investigating them.
-- A gap is sometimes the truth, so it is not forbidden -- it is made
-- UNDENIABLE: a run closing 'complete' with any gaps must have declared
-- them in a coverage note first.
CREATE TRIGGER gaps_must_be_declared_before_complete
BEFORE UPDATE ON scan_runs
BEGIN
  SELECT RAISE(ABORT,'complete with undeclared gaps: record a coverage note')
  WHERE NEW.status='complete'
    AND EXISTS (SELECT 1 FROM observation_gaps WHERE run_id=NEW.run_id)
    AND NOT EXISTS (SELECT 1 FROM coverage_notes
      WHERE run_id=NEW.run_id AND note_class='HISTORICAL_UNTRACEABLE');
END;

-- ============================================================
-- pass 7.3: the six minimum reopening fixes from the verdict round
-- ============================================================

-- (1) VACUOUS DISPOSITION: an empty membership satisfies "every row is
-- disposed" for free. Bind each layer's declared row_count to the
-- membership actually recorded before a run may close complete.
CREATE TRIGGER complete_requires_membership_matches_counts
BEFORE UPDATE ON scan_runs
BEGIN
  SELECT RAISE(ABORT,'declared row_count != recorded membership for a layer')
  WHERE NEW.status='complete' AND EXISTS (
    SELECT 1 FROM scan_layers l WHERE l.run_id=NEW.run_id
      AND l.row_count <> (SELECT COUNT(*) FROM scan_membership m
            WHERE m.run_id=l.run_id AND m.layer=l.layer));
  SELECT RAISE(ABORT,'complete with no captured layers')
  WHERE NEW.status='complete'
    AND NOT EXISTS (SELECT 1 FROM scan_layers WHERE run_id=NEW.run_id);
END;

-- (3) CLOSE-STATE CONSISTENCY: finished but still 'running' is not a state.
CREATE TRIGGER close_state_is_consistent BEFORE UPDATE ON scan_runs
BEGIN
  SELECT RAISE(ABORT,'finished_ts set while status is running')
  WHERE NEW.finished_ts IS NOT NULL AND NEW.status='running';
  SELECT RAISE(ABORT,'status closed without finished_ts')
  WHERE NEW.status IN ('complete','aborted') AND NEW.finished_ts IS NULL;
END;

-- (5) ROW_VANISHED must mean gone NOW, not merely seen before.
CREATE TRIGGER vanished_requires_current_absence BEFORE INSERT ON observation_gaps
BEGIN
  SELECT RAISE(ABORT,'ROW_VANISHED for a row present in this run membership')
  WHERE NEW.gap_class='ROW_VANISHED' AND EXISTS (
    SELECT 1 FROM scan_membership WHERE run_id=NEW.run_id
      AND layer=NEW.layer AND body_row_id=NEW.body_row_id);
END;

-- (6) VERIFICATION ORDINAL/TIME MONOTONIC: otherwise a chronologically
-- later FAIL can sort behind an earlier PASS and "most recent" lies.
CREATE TRIGGER verify_ordinal_monotonic_with_time BEFORE INSERT ON verification_runs
BEGIN
  SELECT RAISE(ABORT,'verify_ordinal not greater than every prior ordinal')
  WHERE NEW.verify_ordinal <= COALESCE((SELECT MAX(verify_ordinal) FROM verification_runs),0);
  SELECT RAISE(ABORT,'started_ts not later than every prior verification start')
  WHERE NEW.started_ts <= COALESCE((SELECT MAX(started_ts) FROM verification_runs),-1e18);
END;

-- (2) PASS REQUIRES A COMPLETED SCAN AND THE FULL REQUIRED-CHECK SET.
-- An aborted or empty scan can no longer earn a vacuous PASS.
CREATE TRIGGER pass_requires_completed_scan_and_checks
BEFORE UPDATE ON verification_runs
BEGIN
  SELECT RAISE(ABORT,'PASS for a scan that did not complete')
  WHERE NEW.result='PASS' AND (SELECT status FROM scan_runs
    WHERE run_id=NEW.scan_run_id) <> 'complete';
  SELECT RAISE(ABORT,'PASS for a scan with empty membership')
  WHERE NEW.result='PASS' AND NOT EXISTS (
    SELECT 1 FROM scan_membership WHERE run_id=NEW.scan_run_id);
  SELECT RAISE(ABORT,'PASS without the required check set')
  WHERE NEW.result='PASS' AND EXISTS (
    SELECT c.name FROM (SELECT 'schema_attested' AS name
                        UNION ALL SELECT 'contract_verified'
                        UNION ALL SELECT 'manifest_bound') c
    WHERE NOT EXISTS (SELECT 1 FROM verification_findings f
      WHERE f.verify_id=NEW.verify_id AND f.check_id=c.name AND f.outcome='pass'));
END;
