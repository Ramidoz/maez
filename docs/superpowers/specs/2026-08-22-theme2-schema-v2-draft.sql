-- Theme 2 schema v2 DRAFT, revision 2 (gate round 5).
-- Status: DESIGN ARTIFACT. Becomes migrations only after the gate
-- passes and S2's witness protocol is committed.
-- Rule: every invariant is HERE as a constraint or trigger.
-- Round-4 folds: DELETE holes closed on every append-only table;
-- runs get a transition matrix + self-journaling + no delete;
-- effect claims carry logical-effect identity unique per TURN
-- (cross-epoch reservation); egress shape unique per TURN; result
-- chains cannot fork and retry ordinals are unique; closure outcome
-- must agree with cited evidence and evidence is a proper set;
-- admission identity gains a revision dimension so corrections are
-- lawful; parent_kind <-> parent_turn_id is two-way; cognition
-- claims require a sealed turn; edits carry lineage via
-- edits_intent instead of cross-intent result supersession.

-- ===================================================================
-- turns: v2 column additions (folded into CREATE TABLE on recreation)
-- ===================================================================
-- occurred_at REAL; admitted_at REAL;
-- direction TEXT NOT NULL DEFAULT 'in' CHECK (direction IN ('in','out'));
-- parent_kind TEXT CHECK (parent_kind IN ('reply','continuation','correction'));
-- is_birth_anchor INTEGER NOT NULL DEFAULT 0 CHECK (is_birth_anchor IN (0,1));
-- FOREIGN KEY (parent_turn_id) REFERENCES turns(turn_id);
-- CHECK (parent_turn_id IS NULL OR parent_turn_id <> turn_id);
-- CHECK ((parent_turn_id IS NULL AND parent_kind IS NULL)
--     OR (parent_turn_id IS NOT NULL AND parent_kind IS NOT NULL));  -- F10 two-way
-- UNIQUE (tenant_id, turn_id);

CREATE TRIGGER IF NOT EXISTS trg_turns_parent_semantics
BEFORE INSERT ON turns
WHEN NEW.parent_turn_id IS NOT NULL
BEGIN
    SELECT CASE
        WHEN (SELECT tenant_id FROM turns WHERE turn_id = NEW.parent_turn_id)
             IS NOT NEW.tenant_id THEN
            RAISE(ABORT, 'parent must share tenant')
        WHEN (SELECT chain_position FROM turns WHERE turn_id = NEW.parent_turn_id)
             >= NEW.chain_position THEN
            RAISE(ABORT, 'parent must be a strictly prior row')
    END;
END;

CREATE TRIGGER IF NOT EXISTS trg_turns_reply_needs_parent
BEFORE INSERT ON turns
WHEN NEW.turn_kind IN ('model_reply','non_model_reply')
     AND NEW.parent_turn_id IS NULL
BEGIN
    SELECT RAISE(ABORT, 'reply kinds require parent_turn_id');
END;

CREATE TRIGGER IF NOT EXISTS trg_turns_single_birth_anchor
BEFORE INSERT ON turns
WHEN NEW.is_birth_anchor = 1
BEGIN
    SELECT CASE WHEN EXISTS (SELECT 1 FROM turns WHERE is_birth_anchor = 1)
        THEN RAISE(ABORT, 'birth anchor already exists — we do not re-birth')
    END;
END;

-- ===================================================================
-- turn_seals — append-only; turns itself never updates
-- ===================================================================
CREATE TABLE IF NOT EXISTS turn_seals (
    turn_id   TEXT PRIMARY KEY REFERENCES turns(turn_id),
    sealed_at REAL NOT NULL
);
CREATE TRIGGER IF NOT EXISTS trg_turn_seals_no_update BEFORE UPDATE ON turn_seals
BEGIN SELECT RAISE(ABORT, 'turn_seals is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_turn_seals_no_delete BEFORE DELETE ON turn_seals
BEGIN SELECT RAISE(ABORT, 'turn_seals is append-only'); END;

-- ===================================================================
-- admission_events — revisioned identity (round-4 correction fix)
-- Same identity + same payload  = replay (a SELECT, no insert).
-- Same identity + new payload   = revision+1, linked to a NEW
--                                 correction turn. Lawful, dense.
-- ===================================================================
CREATE TABLE IF NOT EXISTS admission_events (
    tenant_id      TEXT NOT NULL,
    event_identity TEXT NOT NULL,
    revision       INTEGER NOT NULL CHECK (revision >= 1),
    turn_id        TEXT NOT NULL,
    occurred_at    REAL,
    payload_hash   TEXT NOT NULL,
    admitted_at    REAL NOT NULL,
    PRIMARY KEY (tenant_id, event_identity, revision),
    FOREIGN KEY (tenant_id, turn_id) REFERENCES turns(tenant_id, turn_id)
);
CREATE TRIGGER IF NOT EXISTS trg_admission_revision_rules
BEFORE INSERT ON admission_events
BEGIN
    SELECT CASE
        WHEN NEW.revision <> 1 + COALESCE((SELECT MAX(revision) FROM admission_events
              WHERE tenant_id = NEW.tenant_id AND event_identity = NEW.event_identity), 0)
            THEN RAISE(ABORT, 'revision must be dense per identity')
        WHEN EXISTS (SELECT 1 FROM admission_events
              WHERE tenant_id = NEW.tenant_id AND event_identity = NEW.event_identity
                AND payload_hash = NEW.payload_hash)
            THEN RAISE(ABORT, 'same identity+payload is a replay, not a new revision')
        WHEN EXISTS (SELECT 1 FROM turn_seals WHERE turn_id = NEW.turn_id)
            THEN RAISE(ABORT, 'turn is sealed — admit a new turn instead')
    END;
END;
CREATE TRIGGER IF NOT EXISTS trg_admission_events_no_update BEFORE UPDATE ON admission_events
BEGIN SELECT RAISE(ABORT, 'admission_events is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_admission_events_no_delete BEFORE DELETE ON admission_events
BEGIN SELECT RAISE(ABORT, 'admission_events is append-only'); END;

-- ===================================================================
-- runs — fenced, matrix-transitioned, self-journaling, undeletable
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
CREATE TRIGGER IF NOT EXISTS trg_runs_epoch_monotonic
BEFORE INSERT ON runs
WHEN NEW.epoch <> 1 + COALESCE((SELECT MAX(epoch) FROM runs WHERE turn_id = NEW.turn_id), 0)
BEGIN SELECT RAISE(ABORT, 'run epoch must be exactly max(epoch)+1 for its turn'); END;
CREATE TRIGGER IF NOT EXISTS trg_runs_born_active
BEFORE INSERT ON runs
WHEN NEW.status <> 'active'
BEGIN SELECT RAISE(ABORT, 'runs are born active'); END;
-- Transition matrix: active -> {completed,superseded,abandoned} only.
-- Terminal states are frozen; identity fields immutable; lease may
-- only be renewed while active.
CREATE TRIGGER IF NOT EXISTS trg_runs_transitions
BEFORE UPDATE ON runs
BEGIN
    SELECT CASE
        WHEN NEW.run_id <> OLD.run_id OR NEW.turn_id <> OLD.turn_id
             OR NEW.attempt <> OLD.attempt OR NEW.epoch <> OLD.epoch
             OR NEW.started_at <> OLD.started_at
            THEN RAISE(ABORT, 'run identity fields are immutable')
        WHEN OLD.status <> 'active'
            THEN RAISE(ABORT, 'terminal run states are frozen')
        WHEN NEW.status NOT IN ('active','completed','superseded','abandoned')
            THEN RAISE(ABORT, 'unknown run status')
    END;
END;
CREATE TRIGGER IF NOT EXISTS trg_runs_no_delete BEFORE DELETE ON runs
BEGIN SELECT RAISE(ABORT, 'runs are never deleted'); END;
-- Self-journaling: the transition row cannot be forgotten.
CREATE TABLE IF NOT EXISTS run_events (
    run_event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id       TEXT NOT NULL REFERENCES runs(run_id),
    from_status  TEXT NOT NULL,
    to_status    TEXT NOT NULL,
    at           REAL NOT NULL
);
CREATE TRIGGER IF NOT EXISTS trg_runs_journal_transition
AFTER UPDATE OF status ON runs
BEGIN
    INSERT INTO run_events(run_id, from_status, to_status, at)
    VALUES (NEW.run_id, OLD.status, NEW.status, unixepoch('subsec'));
END;
CREATE TRIGGER IF NOT EXISTS trg_run_events_no_update BEFORE UPDATE ON run_events
BEGIN SELECT RAISE(ABORT, 'run_events is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_run_events_no_delete BEFORE DELETE ON run_events
BEGIN SELECT RAISE(ABORT, 'run_events is append-only'); END;

-- ===================================================================
-- effect_claims — logical-effect reservation ACROSS epochs (F1)
-- effect_identity names the logical effect (e.g. 'reply:final',
-- 'action:<proposal-hash>'); UNIQUE(turn_id, effect_identity) makes a
-- takeover epoch unable to re-claim what any epoch already claimed.
-- ===================================================================
CREATE TABLE IF NOT EXISTS effect_claims (
    claim_id        TEXT PRIMARY KEY,
    turn_id         TEXT NOT NULL REFERENCES turns(turn_id),
    run_id          TEXT NOT NULL REFERENCES runs(run_id),
    claim_kind      TEXT NOT NULL CHECK (claim_kind IN ('cognition_commit','action')),
    effect_identity TEXT NOT NULL,
    claimed_at      REAL NOT NULL,
    UNIQUE (turn_id, effect_identity)
);
CREATE TRIGGER IF NOT EXISTS trg_effect_claims_fence
BEFORE INSERT ON effect_claims
BEGIN
    SELECT CASE
        WHEN (SELECT turn_id FROM runs WHERE run_id = NEW.run_id) <> NEW.turn_id
            THEN RAISE(ABORT, 'claim turn must match run turn')
        WHEN (SELECT status FROM runs WHERE run_id = NEW.run_id) <> 'active'
            THEN RAISE(ABORT, 'claiming run is not active')
        WHEN (SELECT epoch FROM runs WHERE run_id = NEW.run_id)
             <> (SELECT MAX(epoch) FROM runs WHERE turn_id = NEW.turn_id)
            THEN RAISE(ABORT, 'claiming run epoch is stale')
        WHEN NEW.claim_kind = 'cognition_commit'
             AND NOT EXISTS (SELECT 1 FROM turn_seals WHERE turn_id = NEW.turn_id)
            THEN RAISE(ABORT, 'cognition requires a sealed turn')
    END;
END;
CREATE TRIGGER IF NOT EXISTS trg_effect_claims_no_update BEFORE UPDATE ON effect_claims
BEGIN SELECT RAISE(ABORT, 'effect_claims is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_effect_claims_no_delete BEFORE DELETE ON effect_claims
BEGIN SELECT RAISE(ABORT, 'effect_claims is append-only'); END;

-- ===================================================================
-- egress: two-phase, fenced, shape-unique PER TURN, edit lineage
-- ===================================================================
CREATE TABLE IF NOT EXISTS egress_intents (
    intent_id    TEXT PRIMARY KEY,
    turn_id      TEXT NOT NULL REFERENCES turns(turn_id),
    run_id       TEXT NOT NULL REFERENCES runs(run_id),
    egress_kind  TEXT NOT NULL CHECK (egress_kind IN
        ('final_text','part','progress','tts','media','edit','reaction')),
    part_ordinal INTEGER CHECK (part_ordinal IS NULL OR part_ordinal >= 0),
    transport    TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    edits_intent TEXT REFERENCES egress_intents(intent_id),
    created_at   REAL NOT NULL,
    CHECK ((egress_kind = 'edit' AND edits_intent IS NOT NULL)
        OR (egress_kind <> 'edit' AND edits_intent IS NULL))
);
-- One logical send shape per TURN (not per run): takeover epochs
-- cannot recreate the same send. progress is exempt (repeatable).
CREATE UNIQUE INDEX IF NOT EXISTS uq_egress_intent_shape
    ON egress_intents (turn_id, egress_kind, COALESCE(part_ordinal, -1), payload_hash)
    WHERE egress_kind <> 'progress';
CREATE TRIGGER IF NOT EXISTS trg_egress_intents_fence
BEFORE INSERT ON egress_intents
BEGIN
    SELECT CASE
        WHEN (SELECT turn_id FROM runs WHERE run_id = NEW.run_id) <> NEW.turn_id
            THEN RAISE(ABORT, 'intent turn must match run turn')
        WHEN (SELECT status FROM runs WHERE run_id = NEW.run_id) <> 'active'
            THEN RAISE(ABORT, 'intent for non-active run')
        WHEN (SELECT epoch FROM runs WHERE run_id = NEW.run_id)
             <> (SELECT MAX(epoch) FROM runs WHERE turn_id = NEW.turn_id)
            THEN RAISE(ABORT, 'intent from stale-epoch run')
        WHEN NEW.edits_intent IS NOT NULL AND
             (SELECT turn_id FROM egress_intents WHERE intent_id = NEW.edits_intent)
             <> NEW.turn_id
            THEN RAISE(ABORT, 'edit must reference an intent of the same turn')
    END;
END;
CREATE TRIGGER IF NOT EXISTS trg_egress_intents_no_update BEFORE UPDATE ON egress_intents
BEGIN SELECT RAISE(ABORT, 'egress_intents is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_egress_intents_no_delete BEFORE DELETE ON egress_intents
BEGIN SELECT RAISE(ABORT, 'egress_intents is append-only'); END;

CREATE TABLE IF NOT EXISTS egress_results (
    result_id         TEXT PRIMARY KEY,
    intent_id         TEXT NOT NULL REFERENCES egress_intents(intent_id),
    retry_ordinal     INTEGER NOT NULL CHECK (retry_ordinal >= 1),
    result            TEXT NOT NULL CHECK (result IN
        ('delivered','failed','timeout_unknown','suppressed')),
    observed_at       REAL NOT NULL,
    supersedes_result TEXT REFERENCES egress_results(result_id),
    CHECK (supersedes_result IS NULL OR supersedes_result <> result_id),
    UNIQUE (intent_id, retry_ordinal, supersedes_result)
);
-- No forked chains (unique successor) and no duplicate physical
-- attempt rows: a late ack supersedes; it does not re-count.
CREATE UNIQUE INDEX IF NOT EXISTS uq_result_successor
    ON egress_results (supersedes_result) WHERE supersedes_result IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_result_attempt
    ON egress_results (intent_id, retry_ordinal) WHERE supersedes_result IS NULL;
-- Supersession is a RE-OBSERVATION of the same physical attempt:
-- same intent AND same retry_ordinal (round-5 partial finding). New
-- physical attempts enter only as non-superseding rows, which are
-- unique per (intent, ordinal) — no phantom attempt can be minted.
CREATE TRIGGER IF NOT EXISTS trg_egress_results_supersede_same_attempt
BEFORE INSERT ON egress_results
WHEN NEW.supersedes_result IS NOT NULL
BEGIN
    SELECT CASE
        WHEN (SELECT intent_id FROM egress_results WHERE result_id = NEW.supersedes_result)
             <> NEW.intent_id
            THEN RAISE(ABORT, 'result may only supersede a result of its own intent')
        WHEN (SELECT retry_ordinal FROM egress_results WHERE result_id = NEW.supersedes_result)
             <> NEW.retry_ordinal
            THEN RAISE(ABORT, 'supersession re-observes the same attempt: retry_ordinal must match')
    END;
END;
CREATE TRIGGER IF NOT EXISTS trg_egress_results_no_update BEFORE UPDATE ON egress_results
BEGIN SELECT RAISE(ABORT, 'egress_results is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_egress_results_no_delete BEFORE DELETE ON egress_results
BEGIN SELECT RAISE(ABORT, 'egress_results is append-only'); END;
-- Head of each intent's observation chain (result not yet superseded).
CREATE VIEW IF NOT EXISTS current_results AS
SELECT r.* FROM egress_results r
WHERE NOT EXISTS (SELECT 1 FROM egress_results s WHERE s.supersedes_result = r.result_id);

-- ===================================================================
-- turn_closures — dense chain; evidence is a SET; outcome must agree
-- with the cited evidence heads; precedence: only transport-with-new-
-- evidence may supersede transport.
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
    SELECT CASE
        WHEN NEW.closure_ordinal <> 1 + COALESCE(
                (SELECT MAX(closure_ordinal) FROM turn_closures
                 WHERE turn_id = NEW.turn_id), 0)
            THEN RAISE(ABORT, 'closure ordinal must be dense per turn')
        -- precedence: only transport may follow transport, and only
        -- with evidence that differs from its predecessor
        WHEN EXISTS (SELECT 1 FROM turn_closures
                     WHERE turn_id = NEW.turn_id AND recorded_by = 'transport')
             AND NEW.recorded_by <> 'transport'
            THEN RAISE(ABORT, 'only transport may supersede transport closure')
        WHEN NEW.recorded_by = 'transport'
             AND EXISTS (SELECT 1 FROM turn_closures
                         WHERE turn_id = NEW.turn_id AND recorded_by = 'transport'
                           AND evidence_json = NEW.evidence_json)
            THEN RAISE(ABORT, 'transport supersession requires new evidence')
        WHEN NEW.recorded_by = 'transport'
             AND json_array_length(NEW.evidence_json) < 1
            THEN RAISE(ABORT, 'transport closure requires evidence')
        -- evidence is a set of real result-ids of THIS turn
        WHEN (SELECT COUNT(*) FROM json_each(NEW.evidence_json))
             <> (SELECT COUNT(DISTINCT value) FROM json_each(NEW.evidence_json))
            THEN RAISE(ABORT, 'closure evidence must be a set')
        WHEN EXISTS (
                SELECT 1 FROM json_each(NEW.evidence_json) je
                WHERE NOT EXISTS (
                    SELECT 1 FROM egress_results r
                    JOIN egress_intents i ON i.intent_id = r.intent_id
                    WHERE r.result_id = je.value AND i.turn_id = NEW.turn_id))
            THEN RAISE(ABORT, 'closure evidence must be results of the same turn')
        -- outcome/evidence agreement, judged on the cited results
        WHEN NEW.closure = 'delivered' AND EXISTS (
                SELECT 1 FROM json_each(NEW.evidence_json) je
                JOIN egress_results r ON r.result_id = je.value
                WHERE r.result <> 'delivered')
            THEN RAISE(ABORT, 'delivered closure may cite only delivered results')
        WHEN NEW.closure = 'failed' AND EXISTS (
                SELECT 1 FROM json_each(NEW.evidence_json) je
                JOIN egress_results r ON r.result_id = je.value
                WHERE r.result = 'delivered')
            THEN RAISE(ABORT, 'failed closure may not cite a delivered result')
        WHEN NEW.closure = 'partially_delivered' AND NOT (
                EXISTS (SELECT 1 FROM json_each(NEW.evidence_json) je
                        JOIN egress_results r ON r.result_id = je.value
                        WHERE r.result = 'delivered')
                AND EXISTS (SELECT 1 FROM json_each(NEW.evidence_json) je
                        JOIN egress_results r ON r.result_id = je.value
                        WHERE r.result <> 'delivered'))
            THEN RAISE(ABORT, 'partial closure requires mixed evidence')
    END;
END;
CREATE TRIGGER IF NOT EXISTS trg_turn_closures_no_update BEFORE UPDATE ON turn_closures
BEGIN SELECT RAISE(ABORT, 'turn_closures is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_turn_closures_no_delete BEFORE DELETE ON turn_closures
BEGIN SELECT RAISE(ABORT, 'turn_closures is append-only'); END;
CREATE VIEW IF NOT EXISTS current_closure AS
SELECT tc.* FROM turn_closures tc
JOIN (SELECT turn_id, MAX(closure_ordinal) AS mo
      FROM turn_closures GROUP BY turn_id) m
  ON m.turn_id = tc.turn_id AND m.mo = tc.closure_ordinal;

-- ===================================================================
-- journal_folds — fold marker: bound, non-null, undeletable
-- ===================================================================
CREATE TABLE IF NOT EXISTS journal_folds (
    journal_entry_id TEXT PRIMARY KEY,
    entry_sha256     TEXT NOT NULL,
    folded_turn_id   TEXT NOT NULL REFERENCES turns(turn_id),
    folded_at        REAL NOT NULL
);
CREATE TRIGGER IF NOT EXISTS trg_journal_folds_no_update BEFORE UPDATE ON journal_folds
BEGIN SELECT RAISE(ABORT, 'journal_folds is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_journal_folds_no_delete BEFORE DELETE ON journal_folds
BEGIN SELECT RAISE(ABORT, 'journal_folds is append-only'); END;

-- meta (v2 init): chain_hash_domain = '2'.
-- v2 canonicalization: chain.py owns CANONICAL_V2_COLUMNS + defaults;
-- used by writer, genesis seeder, verifier, AND the other production
-- hash consumers (core/consolidation/citation_lock.py,
-- core/ledger/span_reader.py). lifecycle_stage resolves before
-- hashing; genesis is written fully populated.
