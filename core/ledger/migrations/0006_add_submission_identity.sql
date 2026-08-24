-- Admission-protocol slice (2026-08-24, council-ruled)
--
-- Adds submission identity to the turns table:
--
--   submission_id — client-minted identity, minted BEFORE the first
--     write attempt. UNIQUE where present. This is what makes
--     exactly-once enforceable by construction: a crash-window redrive
--     hits the constraint and resolves to the existing row instead of
--     duplicating a life-event. NULL for legacy/system rows — identity
--     is optional at the writer layer, unique when given.
--
--   submitted_at — when the event LIVED (producer clock), as opposed
--     to `timestamp` = when it committed. Ledger order is honestly
--     commit order; lived-time is provenance, so a turn drained from a
--     spool hours later is never presented as having happened at drain
--     time (canon-governs-canon).
--
-- Both columns are INTENTIONALLY excluded from chain-hash canonical
-- bytes (core/ledger/chain.py strip set, same treatment as
-- lifecycle_stage): identity is for dedupe, the chain is for
-- integrity, and pre-0006 chains must remain valid.

ALTER TABLE turns ADD COLUMN submission_id TEXT;
ALTER TABLE turns ADD COLUMN submitted_at REAL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_turns_submission_id
    ON turns (submission_id) WHERE submission_id IS NOT NULL;
