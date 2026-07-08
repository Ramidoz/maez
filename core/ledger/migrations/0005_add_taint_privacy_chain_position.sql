-- Consolidation Spine S1 substrate (2026-07-08)
--
-- Adds row-level provenance taint, privacy access, and the writer-assigned
-- chain_position ordinal. This migration is safe only for empty ledgers; the
-- Python migration runner refuses to apply it when turns already contains rows.

ALTER TABLE turns ADD COLUMN taint_labels_json TEXT NOT NULL DEFAULT '[]';

ALTER TABLE turns ADD COLUMN privacy_access TEXT NOT NULL DEFAULT 'public'
    CHECK (privacy_access IN ('public', 'sealed_adjacent'));

ALTER TABLE turns ADD COLUMN chain_position INTEGER NOT NULL DEFAULT 0;

CREATE UNIQUE INDEX IF NOT EXISTS idx_turns_chain_position
    ON turns (chain_position);
