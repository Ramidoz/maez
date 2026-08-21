-- Theme 2 schema v2 DRAFT — the literal DDL the design binds to.
-- Status: DESIGN ARTIFACT (gate round 4). Not a migration yet; becomes
-- migrations/0006+ (or the recreated 0001) only after the gate passes
-- and slice S2's witness protocol is committed.
-- Baseline: 0001_init.sql .. 0005 as at HEAD. Everything here is
-- additive except the noted turns column additions (legal pre-birth:
-- the ledger has never been instantiated).
-- Rule of this file: every invariant from the design is HERE, as a
-- constraint or trigger — prose only explains, never carries.

-- ===================================================================
-- turns: v2 column additions
-- ===================================================================
-- ALTER TABLE turns ADD COLUMN occurred_at REAL;          -- provider testimony
-- ALTER TABLE turns ADD COLUMN admitted_at REAL;          -- local admission clock
-- ALTER TABLE turns ADD COLUMN direction TEXT NOT NULL DEFAULT 'in'
--     CHECK (direction IN ('in','out'));
-- ALTER TABLE turns ADD COLUMN parent_kind TEXT
--     CHECK (parent_kind IN ('reply','continuation','correction'));
-- ALTER TABLE turns ADD COLUMN is_birth_anchor INTEGER NOT NULL DEFAULT 0
--     CHECK (is_birth_anchor IN (0,1));                   -- F10
-- (v2 recreation folds these into CREATE TABLE turns directly, plus:)
--   FOREIGN KEY (parent_turn_id) REFERENCES turns(turn_id)   -- ND11
--   CHECK (parent_turn_id IS NULL OR parent_turn_id <> turn_id)  -- F10 self-parent

-- Parent semantics (F2, F10, ND11): typed, same-tenant, strictly prior.
CREATE TRIGGER IF NOT EXISTS trg_turns_parent_semantics
BEFORE INSERT ON turns
WHEN NEW.parent_turn_id IS NOT NULL
BEGIN
    SELECT CASE
        WHEN NEW.parent_kind IS NULL THEN
            RAISE(ABORT, 'parent_turn_id requires parent_kind')
        WHEN (SELECT tenant_id FROM turns WHERE turn_id = NEW.parent_turn_id)
             IS NOT NEW.tenant_id THEN
            RAISE(ABORT, 'parent must share tenant')
        WHEN (SELECT chain_position FROM turns WHERE turn_id = NEW.parent_turn_id)
             >= NEW.chain_position THEN
            RAISE(ABORT, 'parent must be a strictly prior row')
    END;
END;

-- Reply kinds require a parent (I6; complements the FK).
CREATE TRIGGER IF NOT EXISTS trg_turns_reply_needs_parent
BEFORE INSERT ON turns
WHEN NEW.turn_kind IN ('model_reply','non_model_reply')
     AND NEW.parent_turn_id IS NULL
BEGIN
    SELECT RAISE(ABORT, 'reply kinds require parent_turn_id');
END;

-- At most one birth anchor, ever (ND16; CHECK above closes the =2 hole).
CREATE TRIGGER IF NOT EXISTS trg_turns_single_birth_anchor
BEFORE INSERT ON turns
WHEN NEW.is_birth_anchor = 1
BEGIN
    SELECT CASE WHEN EXISTS (SELECT 1 FROM turns WHERE is_birth_anchor = 1)
        THEN RAISE(ABORT, 'birth anchor already exists — we do not re-birth')
    END;
END;

-- ===================================================================
-- turn_seals: seal is its own append-only row, so turns stays
-- strictly append-only (no lawful UPDATE anywhere on turns).  (F2)
-- ===================================================================
CREATE TABLE IF NOT EXISTS turn_seals (
    turn_id   TEXT PRIMARY KEY REFERENCES turns(turn_id),
    sealed_at REAL NOT NULL
);
CREATE TRIGGER IF NOT EXISTS trg_turn_seals_no_update
BEFORE UPDATE ON turn_seals
BEGIN SELECT RAISE(ABORT, 'turn_seals is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_turn_seals_no_delete
BEFORE DELETE ON turn_seals
BEGIN SELECT RAISE(ABORT, 'turn_seals is append-only'); END;

-- ===================================================================
-- admission_events: constituent identity (ND3, ND4)
-- ===================================================================
CREATE TABLE IF NOT EXISTS admission_events (
    tenant_id      TEXT NOT NULL,
    event_identity TEXT NOT NULL,
    turn_id        TEXT NOT NULL,
    occurred_at    REAL,
    payload_hash   TEXT NOT NULL,
    admitted_at    REAL NOT NULL,
    PRIMARY KEY (tenant_id, event_identity),
    FOREIGN KEY (tenant_id, turn_id) REFERENCES turns(tenant_id, turn_id)
);
-- (v2 turns gains UNIQUE(tenant_id, turn_id) to be a composite FK target.)

-- Sealed turns accept no new constituents (F2: INSERT *and* UPDATE).
CREATE TRIGGER IF NOT EXISTS trg_admission_no_late_constituent
BEFORE INSERT ON admission_events
WHEN EXISTS (SELECT 1 FROM turn_seals WHERE turn_id = NEW.turn_id)
BEGIN
    SELECT RAISE(ABORT, 'turn is sealed — admit a new turn instead');
END;
CREATE TRIGGER IF NOT EXISTS trg_admission_events_no_update
BEFORE UPDATE ON admission_events
BEGIN SELECT RAISE(ABORT, 'admission_events is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_admission_events_no_delete
BEFORE DELETE ON admission_events
BEGIN SELECT RAISE(ABORT, 'admission_events is append-only'); END;

-- Identity conflict (ND4): same identity + different payload is NOT a
-- replay. The PK makes the second INSERT fail; the rail catches the
-- conflict, compares payload_hash, and admits a NEW turn with
-- parent_kind='correction'. The dedup answer for same-identity,
-- same-payload is a SELECT, never a second insert. (Rail contract,
-- witnessed; the schema's role is that silent overwrite is impossible.)

-- ===================================================================
-- runs: fenced execution (ND5, F1)
-- ===================================================================
CREATE TABLE IF NOT EXISTS runs (
    run_id      TEXT PRIMARY KEY,
    turn_id     TEXT NOT NULL REFERENCES turns(turn_id),
    attempt     INTEGER NOT NULL CHECK (attempt >= 1),
    epoch       INTEGER NOT NULL CHECK (epoch >= 1),
    status      TEXT NOT NULL CHECK (status IN ('active','completed','superseded','abandoned')),
    started_at  REAL NOT NULL,
    lease_until REAL NOT NULL,
    UNIQUE (turn_id, attempt),
    UNIQUE (turn_id, epoch)
);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_run
    ON runs (turn_id) WHERE status = 'active';

-- Epoch is dense and monotonic per turn (F: regressed-epoch hole).
CREATE TRIGGER IF NOT EXISTS trg_runs_epoch_monotonic
BEFORE INSERT ON runs
WHEN NEW.epoch <> 1 + COALESCE((SELECT MAX(epoch) FROM runs WHERE turn_id = NEW.turn_id), 0)
BEGIN
    SELECT RAISE(ABORT, 'run epoch must be exactly max(epoch)+1 for its turn');
END;

-- Runs are operational state: status/lease may change, identity may not,
-- and every status change is journaled in run_events.
CREATE TRIGGER IF NOT EXISTS trg_runs_update_scope
BEFORE UPDATE ON runs
WHEN NEW.run_id <> OLD.run_id OR NEW.turn_id <> OLD.turn_id
     OR NEW.attempt <> OLD.attempt OR NEW.epoch <> OLD.epoch
     OR NEW.started_at <> OLD.started_at
BEGIN
    SELECT RAISE(ABORT, 'run identity fields are immutable');
END;
CREATE TABLE IF NOT EXISTS run_events (
    run_event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id       TEXT NOT NULL REFERENCES runs(run_id),
    from_status  TEXT NOT NULL,
    to_status    TEXT NOT NULL,
    at           REAL NOT NULL,
    by           TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS trg_run_events_append_only
BEFORE UPDATE ON run_events
BEGIN SELECT RAISE(ABORT, 'run_events is append-only'); END;

-- ===================================================================
-- effect_claims: the durable, conditional pre-effect claim (F1).
-- An external effect (action, cognition commit) happens ONLY after a
-- COMMITTED claim row. The trigger is the CAS: it aborts unless the
-- claiming run is, at claim time, the max-epoch active run.  Claims
-- for egress use egress_intents (same fence trigger) instead.
-- ===================================================================
CREATE TABLE IF NOT EXISTS effect_claims (
    claim_id   TEXT PRIMARY KEY,
    run_id     TEXT NOT NULL REFERENCES runs(run_id),
    claim_kind TEXT NOT NULL CHECK (claim_kind IN ('cognition_commit','action')),
    claimed_at REAL NOT NULL
);
CREATE TRIGGER IF NOT EXISTS trg_effect_claims_fence
BEFORE INSERT ON effect_claims
BEGIN
    SELECT CASE
        WHEN (SELECT status FROM runs WHERE run_id = NEW.run_id) <> 'active'
            THEN RAISE(ABORT, 'claiming run is not active')
        WHEN (SELECT epoch FROM runs WHERE run_id = NEW.run_id)
             <> (SELECT MAX(epoch) FROM runs
                 WHERE turn_id = (SELECT turn_id FROM runs WHERE run_id = NEW.run_id))
            THEN RAISE(ABORT, 'claiming run epoch is stale')
    END;
END;
CREATE TRIGGER IF NOT EXISTS trg_effect_claims_append_only
BEFORE UPDATE ON effect_claims
BEGIN SELECT RAISE(ABORT, 'effect_claims is append-only'); END;

-- ===================================================================
-- egress: two-phase (I4), fenced (F1), shape-unique (ND10)
-- ===================================================================
CREATE TABLE IF NOT EXISTS egress_intents (
    intent_id    TEXT PRIMARY KEY,
    run_id       TEXT NOT NULL REFERENCES runs(run_id),
    egress_kind  TEXT NOT NULL CHECK (egress_kind IN
        ('final_text','part','progress','tts','media','edit','reaction')),
    part_ordinal INTEGER CHECK (part_ordinal IS NULL OR part_ordinal >= 0),
    transport    TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    created_at   REAL NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_egress_intent_shape
    ON egress_intents (run_id, egress_kind, COALESCE(part_ordinal, -1));
CREATE TRIGGER IF NOT EXISTS trg_egress_intents_fence
BEFORE INSERT ON egress_intents
BEGIN
    SELECT CASE
        WHEN (SELECT status FROM runs WHERE run_id = NEW.run_id) <> 'active'
            THEN RAISE(ABORT, 'intent for non-active run')
        WHEN (SELECT epoch FROM runs WHERE run_id = NEW.run_id)
             <> (SELECT MAX(epoch) FROM runs
                 WHERE turn_id = (SELECT turn_id FROM runs WHERE run_id = NEW.run_id))
            THEN RAISE(ABORT, 'intent from stale-epoch run')
    END;
END;
CREATE TRIGGER IF NOT EXISTS trg_egress_intents_append_only
BEFORE UPDATE ON egress_intents
BEGIN SELECT RAISE(ABORT, 'egress_intents is append-only'); END;

CREATE TABLE IF NOT EXISTS egress_results (
    result_id         TEXT PRIMARY KEY,
    intent_id         TEXT NOT NULL REFERENCES egress_intents(intent_id),
    retry_ordinal     INTEGER NOT NULL CHECK (retry_ordinal >= 1),
    result            TEXT NOT NULL CHECK (result IN
        ('delivered','failed','timeout_unknown','suppressed')),
    observed_at       REAL NOT NULL,
    supersedes_result TEXT REFERENCES egress_results(result_id),
    CHECK (supersedes_result IS NULL OR supersedes_result <> result_id)  -- F9 self
);
-- Supersession stays inside one intent (F9 cross-intent / edit-redirect).
CREATE TRIGGER IF NOT EXISTS trg_egress_results_supersede_same_intent
BEFORE INSERT ON egress_results
WHEN NEW.supersedes_result IS NOT NULL
     AND (SELECT intent_id FROM egress_results WHERE result_id = NEW.supersedes_result)
         <> NEW.intent_id
BEGIN
    SELECT RAISE(ABORT, 'result may only supersede a result of its own intent');
END;
CREATE TRIGGER IF NOT EXISTS trg_egress_results_append_only
BEFORE UPDATE ON egress_results
BEGIN SELECT RAISE(ABORT, 'egress_results is append-only'); END;

-- ===================================================================
-- turn_closures: dense chain, frozen in-row evidence (ND7, ND8/F8)
-- Evidence is a canonical JSON array of result_ids INSIDE the closure
-- row — frozen at insert, no post-hoc expansion, no insertion-order
-- deadlock with FKs. The trigger validates every element.
-- ===================================================================
CREATE TABLE IF NOT EXISTS turn_closures (
    closure_id      TEXT PRIMARY KEY,
    turn_id         TEXT NOT NULL REFERENCES turns(turn_id),
    closure_ordinal INTEGER NOT NULL CHECK (closure_ordinal >= 1),
    closure         TEXT NOT NULL CHECK (closure IN
        ('delivered','partially_delivered','failed','suppressed',
         'unknown_delivery','refused','unresolved_crash')),
    evidence_json   TEXT NOT NULL DEFAULT '[]',
    recorded_by     TEXT NOT NULL CHECK (recorded_by IN ('transport','doorway','reconciler')),
    recorded_at     REAL NOT NULL,
    discovered_at   REAL,
    UNIQUE (turn_id, closure_ordinal)
);
CREATE TRIGGER IF NOT EXISTS trg_turn_closures_topology
BEFORE INSERT ON turn_closures
BEGIN
    -- dense chain: no forks, no gaps, no cross-turn/self supersession
    SELECT CASE
        WHEN NEW.closure_ordinal <> 1 + COALESCE(
                (SELECT MAX(closure_ordinal) FROM turn_closures
                 WHERE turn_id = NEW.turn_id), 0)
            THEN RAISE(ABORT, 'closure ordinal must be dense per turn')
        -- precedence: reconciler may not supersede transport truth
        WHEN NEW.recorded_by = 'reconciler' AND EXISTS (
                SELECT 1 FROM turn_closures
                WHERE turn_id = NEW.turn_id AND recorded_by = 'transport')
            THEN RAISE(ABORT, 'reconciler may not supersede transport closure')
        -- transport closures require evidence…
        WHEN NEW.recorded_by = 'transport'
             AND json_array_length(NEW.evidence_json) < 1
            THEN RAISE(ABORT, 'transport closure requires evidence')
        -- …and every evidence element must be a real result of THIS turn
        WHEN EXISTS (
                SELECT 1 FROM json_each(NEW.evidence_json) je
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM egress_results r
                    JOIN egress_intents i ON i.intent_id = r.intent_id
                    JOIN runs u          ON u.run_id   = i.run_id
                    WHERE r.result_id = je.value
                      AND u.turn_id  = NEW.turn_id))
            THEN RAISE(ABORT, 'closure evidence must be results of the same turn')
    END;
END;
CREATE TRIGGER IF NOT EXISTS trg_turn_closures_append_only_u
BEFORE UPDATE ON turn_closures
BEGIN SELECT RAISE(ABORT, 'turn_closures is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_turn_closures_append_only_d
BEFORE DELETE ON turn_closures
BEGIN SELECT RAISE(ABORT, 'turn_closures is append-only'); END;
CREATE VIEW IF NOT EXISTS current_closure AS
SELECT tc.* FROM turn_closures tc
JOIN (SELECT turn_id, MAX(closure_ordinal) AS mo
      FROM turn_closures GROUP BY turn_id) m
  ON m.turn_id = tc.turn_id AND m.mo = tc.closure_ordinal;

-- ===================================================================
-- journal_folds: in-ledger idempotence + integrity for gap-journal
-- fold-in (ND15/F5). entry_sha256 is the hash of the ORIGINAL
-- journal entry bytes; the folded rows carry failure-time stamps.
-- ===================================================================
CREATE TABLE IF NOT EXISTS journal_folds (
    journal_entry_id TEXT PRIMARY KEY,
    entry_sha256     TEXT NOT NULL,
    folded_turn_id   TEXT REFERENCES turns(turn_id),
    folded_at        REAL NOT NULL
);
CREATE TRIGGER IF NOT EXISTS trg_journal_folds_append_only
BEFORE UPDATE ON journal_folds
BEGIN SELECT RAISE(ABORT, 'journal_folds is append-only'); END;

-- meta (set by v2 init): chain_hash_domain = '2'.
-- v2 chain hashing: one domain-owned projection (ordered column list +
-- default map) in core/ledger/chain.py, used identically by the
-- writer, the genesis seeder, and the verifier (F7). lifecycle_stage
-- resolves BEFORE hashing; genesis is written fully populated.
