-- Slice 4c.5b: trace metadata + audit refusal substrate.
--
-- Trace metadata is additive and defaults NULL. It is a refusal token,
-- not audit evidence. Rich lineage lives in audit_trace_lineage keyed by
-- turn_id so the turns row stays thin.

ALTER TABLE turns ADD COLUMN audit_trace_label TEXT DEFAULT NULL;
ALTER TABLE turns ADD COLUMN audit_trace_value_schema INTEGER DEFAULT NULL;
ALTER TABLE turns ADD COLUMN audit_trace_metadata_shape INTEGER DEFAULT NULL;

CREATE INDEX IF NOT EXISTS idx_turns_audit_trace
ON turns (tenant_id, audit_trace_label, timestamp DESC)
WHERE audit_trace_label IS NOT NULL;

CREATE TABLE IF NOT EXISTS audit_trace_lineage (
    turn_id TEXT PRIMARY KEY,
    rule_id TEXT NOT NULL,
    source_ids_json TEXT NOT NULL DEFAULT '[]',
    policy_doc_sha256 TEXT NOT NULL,
    trace_value_schema INTEGER NOT NULL,
    trace_metadata_shape INTEGER NOT NULL,
    applied_at REAL NOT NULL,
    FOREIGN KEY(turn_id) REFERENCES turns(turn_id)
);
