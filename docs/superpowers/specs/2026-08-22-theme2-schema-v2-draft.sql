-- Theme 2 schema v2 DRAFT, revision 5 (gate round 7).
-- Revision 5 folds gate-round-6's Q-stratum: finite/causal time
-- everywhere; one transition record per run; correction ancestry
-- bound; kind/ordinal shapes; acyclic edits; PRE-SEND per-attempt
-- reservations (retry authority before bytes leave); closure-label
-- evidence semantics for every label; nonempty/canonical identity
-- carriers (ASCII ids, 64-hex digests); membership before cognition;
-- kind/parent/direction mapping.
-- (Revision 3 = round-5 same-attempt supersession fix; revision 4 =
--  round-5-rerun folds P01-P26: STRICT tables so TEXT PRIMARY KEYs
--  reject NULL; turns immutable and undeletable; run_events inserts
--  validated against live run state; lease renewal monotonic;
--  correction revisions bound to correction turns; closure evidence
--  array-typed, self-normalized, current-head, per-attempt distinct,
--  outcome-classes-with-evidence; dense retry admission with no
--  retry past an unresolved or delivered attempt; payload-independent
--  logical send identity.)
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

-- Q33: kind/parent/direction mapping.
CREATE TRIGGER IF NOT EXISTS trg_turns_kind_mapping
BEFORE INSERT ON turns
BEGIN
    SELECT CASE
        WHEN NEW.turn_kind IN ('model_reply','non_model_reply','peer_message_out')
             AND NEW.direction <> 'out'
            THEN RAISE(ABORT, 'reply kinds are outbound')
        WHEN NEW.turn_kind IN ('user_message','peer_message_in')
             AND NEW.direction <> 'in'
            THEN RAISE(ABORT, 'message-in kinds are inbound')
        WHEN NEW.parent_kind = 'reply'
             AND NEW.turn_kind NOT IN ('model_reply','non_model_reply')
            THEN RAISE(ABORT, 'parent_kind reply belongs to reply kinds')
        WHEN NEW.turn_kind IN ('model_reply','non_model_reply')
             AND NEW.parent_kind IS NOT 'reply'
            THEN RAISE(ABORT, 'reply kinds carry parent_kind reply')
        WHEN NEW.parent_kind = 'correction'
             AND NEW.turn_kind <> 'user_message'
            THEN RAISE(ABORT, 'corrections are owner-message turns')
    END;
END;

CREATE TRIGGER IF NOT EXISTS trg_turns_reply_needs_parent
BEFORE INSERT ON turns
WHEN NEW.turn_kind IN ('model_reply','non_model_reply')
     AND NEW.parent_turn_id IS NULL
BEGIN
    SELECT RAISE(ABORT, 'reply kinds require parent_turn_id');
END;

-- turns is append-only, full stop: no UPDATE (closes P18-P20 UPDATE
-- bypasses of parent/anchor semantics), no DELETE (P21).
CREATE TRIGGER IF NOT EXISTS trg_turns_no_update BEFORE UPDATE ON turns
BEGIN SELECT RAISE(ABORT, 'turns is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_turns_no_delete BEFORE DELETE ON turns
BEGIN SELECT RAISE(ABORT, 'turns is append-only'); END;

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
) STRICT;
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
) STRICT;
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
        WHEN NEW.revision > 1 AND
             (SELECT parent_kind FROM turns WHERE turn_id = NEW.turn_id)
             IS NOT 'correction'
            THEN RAISE(ABORT, 'a correction revision must land on a correction turn')
        WHEN NEW.revision > 1 AND
             (SELECT parent_turn_id FROM turns WHERE turn_id = NEW.turn_id)
             IS NOT (SELECT turn_id FROM admission_events
                     WHERE tenant_id = NEW.tenant_id
                       AND event_identity = NEW.event_identity
                       AND revision = NEW.revision - 1)
            THEN RAISE(ABORT, 'correction turn must descend from the prior revision turn')
        WHEN NEW.revision > 1 AND EXISTS (
                SELECT 1 FROM admission_events WHERE turn_id = NEW.turn_id)
            THEN RAISE(ABORT, 'a correction turn hosts exactly one revision')
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
    started_at  REAL NOT NULL CHECK (started_at > 0 AND started_at < 1e11),
    lease_until REAL NOT NULL CHECK (lease_until < 1e11),
    UNIQUE (turn_id, attempt),
    UNIQUE (turn_id, epoch),
    CHECK (attempt = epoch),                 -- Q30: one counter, defined
    CHECK (lease_until >= started_at),       -- Q23
    CHECK (run_id NOT GLOB '*[^ -~]*')       -- Q18: ASCII id posture
) STRICT;
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
        WHEN NEW.status = 'active' AND NEW.lease_until <= OLD.lease_until
            THEN RAISE(ABORT, 'lease renewal must strictly advance')
        WHEN NEW.status <> 'active' AND NEW.lease_until <> OLD.lease_until
            THEN RAISE(ABORT, 'terminal transition may not alter the lease')
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
    at           REAL NOT NULL CHECK (at > 0 AND at < 1e11),
    UNIQUE (run_id)                          -- Q05: at most one transition per run
) STRICT;
CREATE TRIGGER IF NOT EXISTS trg_runs_journal_transition
AFTER UPDATE OF status ON runs
WHEN OLD.status <> NEW.status
BEGIN
    INSERT INTO run_events(run_id, from_status, to_status, at)
    VALUES (NEW.run_id, OLD.status, NEW.status, unixepoch('subsec'));
END;
-- History rows must describe a real, just-performed transition (P03):
-- from must be 'active' (the only non-terminal state) and to must be
-- the run's live status at insert time.
CREATE TRIGGER IF NOT EXISTS trg_run_events_valid_history
BEFORE INSERT ON run_events
BEGIN
    SELECT CASE
        WHEN NEW.from_status <> 'active'
            THEN RAISE(ABORT, 'transitions only leave active')
        WHEN NEW.to_status <> (SELECT status FROM runs WHERE run_id = NEW.run_id)
            THEN RAISE(ABORT, 'history row must match live run state')
        WHEN NEW.from_status = NEW.to_status
            THEN RAISE(ABORT, 'not a transition')
        WHEN NEW.at < (SELECT started_at FROM runs WHERE run_id = NEW.run_id)
            THEN RAISE(ABORT, 'transition precedes its run')
    END;
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
    effect_identity TEXT NOT NULL CHECK (length(effect_identity) > 0),
    claimed_at      REAL NOT NULL CHECK (claimed_at > 0 AND claimed_at < 1e11),
    UNIQUE (turn_id, effect_identity),
    CHECK (claim_id NOT GLOB '*[^ -~]*')
) STRICT;
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
        WHEN NEW.claim_kind = 'cognition_commit'
             AND NOT EXISTS (SELECT 1 FROM admission_events WHERE turn_id = NEW.turn_id)
            THEN RAISE(ABORT, 'cognition requires admitted membership')   -- Q32
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
    payload_hash TEXT NOT NULL CHECK (length(payload_hash) > 0),
    edits_intent TEXT REFERENCES egress_intents(intent_id),
    created_at   REAL NOT NULL CHECK (created_at > 0 AND created_at < 1e11),
    CHECK ((egress_kind = 'edit' AND edits_intent IS NOT NULL)
        OR (egress_kind <> 'edit' AND edits_intent IS NULL)),
    CHECK (edits_intent IS NULL OR edits_intent <> intent_id),          -- Q12
    CHECK ((egress_kind = 'part') = (part_ordinal IS NOT NULL)),        -- Q10/Q11
    CHECK (intent_id NOT GLOB '*[^ -~]*')
) STRICT;
-- One logical send shape per TURN (not per run): takeover epochs
-- cannot recreate the same send. progress is exempt (repeatable).
-- Logical send identity is payload-INDEPENDENT (P17): one final_text
-- slot per turn, one slot per (kind, part); replacements go through
-- egress_kind='edit' lineage, retries through egress_results.
CREATE UNIQUE INDEX IF NOT EXISTS uq_egress_intent_slot
    ON egress_intents (turn_id, egress_kind)
    WHERE egress_kind IN ('final_text','tts','media');
CREATE UNIQUE INDEX IF NOT EXISTS uq_egress_intent_part
    ON egress_intents (turn_id, part_ordinal)
    WHERE egress_kind = 'part';
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
             IS NOT NEW.turn_id
            THEN RAISE(ABORT, 'edit must reference an existing intent of the same turn')
        WHEN NEW.created_at < (SELECT started_at FROM runs WHERE run_id = NEW.run_id)
            THEN RAISE(ABORT, 'intent precedes its run')                 -- Q34
    END;
END;
CREATE TRIGGER IF NOT EXISTS trg_egress_intents_no_update BEFORE UPDATE ON egress_intents
BEGIN SELECT RAISE(ABORT, 'egress_intents is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_egress_intents_no_delete BEFORE DELETE ON egress_intents
BEGIN SELECT RAISE(ABORT, 'egress_intents is append-only'); END;

-- PRE-SEND attempt reservation (round-6 authority finding): the
-- durable per-physical-attempt claim, committed BEFORE bytes leave.
-- Density and eligibility are enforced HERE, pre-send; the result
-- trigger keeps them as a backstop. A result row without its
-- reservation is impossible.
CREATE TABLE IF NOT EXISTS egress_reservations (
    intent_id     TEXT NOT NULL REFERENCES egress_intents(intent_id),
    retry_ordinal INTEGER NOT NULL CHECK (retry_ordinal >= 1),
    reserved_at   REAL NOT NULL CHECK (reserved_at > 0 AND reserved_at < 1e11),
    PRIMARY KEY (intent_id, retry_ordinal)
) STRICT;
CREATE TRIGGER IF NOT EXISTS trg_egress_reservations_admission
BEFORE INSERT ON egress_reservations
BEGIN
    SELECT CASE
        WHEN (SELECT status FROM runs WHERE run_id =
                (SELECT run_id FROM egress_intents WHERE intent_id = NEW.intent_id))
             <> 'active'
            THEN RAISE(ABORT, 'reservation requires an active run')
        WHEN NEW.retry_ordinal <> 1 + COALESCE(
                (SELECT MAX(retry_ordinal) FROM egress_reservations
                 WHERE intent_id = NEW.intent_id), 0)
            THEN RAISE(ABORT, 'reservations are dense per intent')
        WHEN NEW.retry_ordinal > 1 AND (
                SELECT r.result FROM egress_results r
                WHERE r.intent_id = NEW.intent_id
                  AND r.retry_ordinal = NEW.retry_ordinal - 1
                  AND NOT EXISTS (SELECT 1 FROM egress_results s
                                  WHERE s.supersedes_result = r.result_id)
             ) NOT IN ('failed','suppressed')
            THEN RAISE(ABORT, 'a new attempt requires the prior attempt resolved as non-delivered')
    END;
END;
CREATE TRIGGER IF NOT EXISTS trg_egress_reservations_no_update BEFORE UPDATE ON egress_reservations
BEGIN SELECT RAISE(ABORT, 'egress_reservations is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_egress_reservations_no_delete BEFORE DELETE ON egress_reservations
BEGIN SELECT RAISE(ABORT, 'egress_reservations is append-only'); END;

CREATE TABLE IF NOT EXISTS egress_results (
    result_id         TEXT PRIMARY KEY,
    intent_id         TEXT NOT NULL REFERENCES egress_intents(intent_id),
    retry_ordinal     INTEGER NOT NULL CHECK (retry_ordinal >= 1),
    result            TEXT NOT NULL CHECK (result IN
        ('delivered','failed','timeout_unknown','suppressed')),
    observed_at       REAL NOT NULL CHECK (observed_at > 0 AND observed_at < 1e11),
    supersedes_result TEXT REFERENCES egress_results(result_id),
    CHECK (supersedes_result IS NULL OR supersedes_result <> result_id),
    UNIQUE (intent_id, retry_ordinal, supersedes_result),
    CHECK (result_id NOT GLOB '*[^ -~]*')
) STRICT;
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
        WHEN (SELECT observed_at FROM egress_results WHERE result_id = NEW.supersedes_result)
             >= NEW.observed_at
            THEN RAISE(ABORT, 'a later observation carries a later time')   -- Q04
    END;
END;
-- Physical attempts are dense (P15) and eligible (P16): a new attempt
-- may start only when the previous attempt's current head is a
-- resolved non-delivery ('failed'/'suppressed'). timeout_unknown must
-- be superseded by a real observation first (I4: no blind resend past
-- an unknown), and 'delivered' forecloses further attempts.
CREATE TRIGGER IF NOT EXISTS trg_egress_results_attempt_admission
BEFORE INSERT ON egress_results
WHEN NEW.supersedes_result IS NULL
BEGIN
    SELECT CASE
        WHEN NOT EXISTS (SELECT 1 FROM egress_reservations
                WHERE intent_id = NEW.intent_id AND retry_ordinal = NEW.retry_ordinal)
            THEN RAISE(ABORT, 'a result requires its pre-send reservation')
        WHEN NEW.retry_ordinal <> 1 + COALESCE(
                (SELECT MAX(retry_ordinal) FROM egress_results
                 WHERE intent_id = NEW.intent_id AND supersedes_result IS NULL), 0)
            THEN RAISE(ABORT, 'physical attempts are dense per intent')
        WHEN NEW.retry_ordinal > 1 AND NEW.observed_at <= (
                SELECT MAX(r.observed_at) FROM egress_results r
                WHERE r.intent_id = NEW.intent_id
                  AND r.retry_ordinal = NEW.retry_ordinal - 1)
            THEN RAISE(ABORT, 'retry chronology must advance')            -- Q03
        WHEN NEW.retry_ordinal > 1 AND (
                SELECT r.result FROM egress_results r
                WHERE r.intent_id = NEW.intent_id
                  AND r.retry_ordinal = NEW.retry_ordinal - 1
                  AND NOT EXISTS (SELECT 1 FROM egress_results s
                                  WHERE s.supersedes_result = r.result_id)
             ) NOT IN ('failed','suppressed')
            THEN RAISE(ABORT, 'new attempt requires the prior attempt resolved as non-delivered')
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
    recorded_at     REAL NOT NULL CHECK (recorded_at > 0 AND recorded_at < 1e11),
    discovered_at   REAL CHECK (discovered_at IS NULL
                                OR (discovered_at > 0 AND discovered_at <= recorded_at)),  -- Q25
    UNIQUE (turn_id, closure_ordinal),
    CHECK (closure_id NOT GLOB '*[^ -~]*')
) STRICT;
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
        WHEN json_type(NEW.evidence_json) IS NOT 'array'
            THEN RAISE(ABORT, 'closure evidence must be a JSON array')
        -- self-normalized: the stored array must be sorted, so equal
        -- sets are equal strings (P09 reorder-as-new-evidence)
        WHEN NEW.evidence_json <> (
                SELECT COALESCE(json_group_array(value), json_array())
                FROM (SELECT je.value AS value FROM json_each(NEW.evidence_json) je
                      ORDER BY je.value))
            THEN RAISE(ABORT, 'closure evidence must be sorted canonical form')
        -- outcome classes that assert egress facts require evidence
        -- whoever records them (P13)
        WHEN NEW.closure IN ('delivered','partially_delivered','failed')
             AND json_array_length(NEW.evidence_json) < 1
            THEN RAISE(ABORT, 'outcome closures require evidence')
        WHEN NEW.recorded_by = 'reconciler' AND NEW.discovered_at IS NULL
            THEN RAISE(ABORT, 'reconciler closures carry discovered_at')
        -- evidence must be current heads (P11), one per physical
        -- attempt (P12)
        WHEN EXISTS (
                SELECT 1 FROM json_each(NEW.evidence_json) je
                JOIN egress_results r ON r.result_id = je.value
                WHERE EXISTS (SELECT 1 FROM egress_results s
                              WHERE s.supersedes_result = r.result_id))
            THEN RAISE(ABORT, 'closure evidence must be current result heads')
        WHEN (SELECT COUNT(*) FROM json_each(NEW.evidence_json))
             <> (SELECT COUNT(DISTINCT r.intent_id || ':' || r.retry_ordinal)
                 FROM json_each(NEW.evidence_json) je
                 JOIN egress_results r ON r.result_id = je.value)
            THEN RAISE(ABORT, 'one evidence head per physical attempt')
        -- closure cannot predate its evidence (Q24)
        WHEN NEW.recorded_at < (
                SELECT MAX(r.observed_at) FROM json_each(NEW.evidence_json) je
                JOIN egress_results r ON r.result_id = je.value)
            THEN RAISE(ABORT, 'closure cannot predate its evidence')
        -- per-label evidence semantics (Q26-Q29)
        WHEN NEW.closure = 'failed' AND (
                EXISTS (SELECT 1 FROM json_each(NEW.evidence_json) je
                        JOIN egress_results r ON r.result_id = je.value
                        WHERE r.result NOT IN ('failed','suppressed')))
            THEN RAISE(ABORT, 'failed closure cites only resolved non-delivery')
        WHEN NEW.closure = 'unknown_delivery' AND (
                json_array_length(NEW.evidence_json) < 1
                OR EXISTS (SELECT 1 FROM json_each(NEW.evidence_json) je
                           JOIN egress_results r ON r.result_id = je.value
                           WHERE r.result = 'delivered')
                OR NOT EXISTS (SELECT 1 FROM json_each(NEW.evidence_json) je
                               JOIN egress_results r ON r.result_id = je.value
                               WHERE r.result = 'timeout_unknown'))
            THEN RAISE(ABORT, 'unknown_delivery cites an unresolved handoff and no delivery')
        WHEN NEW.closure = 'refused' AND (
                json_array_length(NEW.evidence_json) > 0
                OR EXISTS (SELECT 1 FROM egress_intents WHERE turn_id = NEW.turn_id))
            THEN RAISE(ABORT, 'refused means nothing was ever handed to a transport')
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
    entry_sha256     TEXT NOT NULL
        CHECK (length(entry_sha256) = 64 AND entry_sha256 NOT GLOB '*[^0-9a-f]*'),
    folded_turn_id   TEXT NOT NULL REFERENCES turns(turn_id),
    folded_at        REAL NOT NULL
) STRICT;
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
