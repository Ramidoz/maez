-- Gestation Boundary slice (2026-05-08)
--
-- Adds the `lifecycle_stage` column to the `turns` table so Maez can
-- distinguish pre-birth (gestation) memories from post-birth (lived)
-- memories at the schema level — not just in our heads. Defaults to
-- 'gestation' so existing rows and any new rows written before the
-- birth event are correctly tagged. Post-birth, the writer overrides
-- to 'lived' (see core/ledger/writer.py).
--
-- The column is INTENTIONALLY NOT included in the chain-hash canonical
-- bytes (see core/ledger/chain.py strip set + the matching invariant
-- test in tests/test_lifecycle_stage_chain_hash_invariant.py).
-- Existing chain hashes remain valid; future chain hashes will continue
-- to compute identically regardless of lifecycle_stage value.
--
-- Also adds:
--   - `meta.birth_event_turn_id` row (default NULL, no schema change
--     to meta — meta is key/value, the row is inserted only when birth
--     fires, leaving NULL semantically equivalent to "absent")
--   - An index on (tenant_id, lifecycle_stage, timestamp DESC) so the
--     two-tier recall sort (lived-first, then gestation, recency
--     within each tier) doesn't degrade to a table scan.

ALTER TABLE turns ADD COLUMN lifecycle_stage TEXT NOT NULL DEFAULT 'gestation';

CREATE INDEX IF NOT EXISTS idx_turns_lifecycle_ts
    ON turns (tenant_id, lifecycle_stage, timestamp DESC);
