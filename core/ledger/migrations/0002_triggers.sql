-- 0002_triggers.sql
-- Append-only enforcement for the Maez ledger.
--
-- Per docs/LEDGER_ENVELOPE_SCHEMA.md §1 principle 2 ("Append-only") and
-- §10 / §10.1 (claims-extraction + ratification: claim_judgements is
-- strictly immutable; the proposed single-UPDATE carve-out was REJECTED),
-- the tables `turns`, `claims`, and `claim_judgements` must reject every
-- UPDATE and DELETE unconditionally.
--
-- Triggers are table-scoped (no `OF <column>` clause) so that any future
-- column added to these tables inherits the immutability invariant
-- automatically. No `WHEN` clause: refusal is unconditional.
--
-- `meta`, `model_swaps`, and `schema_migrations` are intentionally NOT
-- covered here -- they are legitimately mutable.

-- ---------------------------------------------------------------------------
-- turns
-- ---------------------------------------------------------------------------
CREATE TRIGGER IF NOT EXISTS turns_no_update
BEFORE UPDATE ON turns
BEGIN
    SELECT RAISE(ABORT, 'turns is append-only: UPDATE rejected per §1 principle 2 + §10 ratification');
END;

CREATE TRIGGER IF NOT EXISTS turns_no_delete
BEFORE DELETE ON turns
BEGIN
    SELECT RAISE(ABORT, 'turns is append-only: DELETE rejected per §1 principle 2 + §10 ratification');
END;

-- ---------------------------------------------------------------------------
-- claims
-- ---------------------------------------------------------------------------
CREATE TRIGGER IF NOT EXISTS claims_no_update
BEFORE UPDATE ON claims
BEGIN
    SELECT RAISE(ABORT, 'claims is append-only: UPDATE rejected per §1 principle 2 + §10 ratification');
END;

CREATE TRIGGER IF NOT EXISTS claims_no_delete
BEFORE DELETE ON claims
BEGIN
    SELECT RAISE(ABORT, 'claims is append-only: DELETE rejected per §1 principle 2 + §10 ratification');
END;

-- ---------------------------------------------------------------------------
-- claim_judgements
-- ---------------------------------------------------------------------------
-- Per §10.1 ratification: the "single permitted UPDATE" carve-out was
-- REJECTED. Pass B inserts new judgement rows; it never mutates existing
-- ones. Therefore UPDATE is refused unconditionally, same as DELETE.
CREATE TRIGGER IF NOT EXISTS claim_judgements_no_update
BEFORE UPDATE ON claim_judgements
BEGIN
    SELECT RAISE(ABORT, 'claim_judgements is append-only: UPDATE rejected per §1 principle 2 + §10 ratification');
END;

CREATE TRIGGER IF NOT EXISTS claim_judgements_no_delete
BEFORE DELETE ON claim_judgements
BEGIN
    SELECT RAISE(ABORT, 'claim_judgements is append-only: DELETE rejected per §1 principle 2 + §10 ratification');
END;
