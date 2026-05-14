-- 0001_init.sql — Maez ledger initial schema migration
-- Source of truth: docs/ledger/envelope-schema.md §4.1–§4.4
-- Safe to re-run (every CREATE uses IF NOT EXISTS).
-- This file contains schema only. Triggers live in 0002_triggers.sql.
-- Seeding (schema_version, genesis_hash) is performed by migrate.py.

-- ---------------------------------------------------------------------------
-- §4.1  meta
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- ---------------------------------------------------------------------------
-- §4.2  turns — the ledger root
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS turns (
    -- Identity
    turn_id          TEXT PRIMARY KEY,
    tenant_id        TEXT NOT NULL DEFAULT 'owner',
    timestamp        REAL NOT NULL,
    schema_version   INTEGER NOT NULL,
    turn_kind        TEXT NOT NULL,

    -- Surface and routing
    surface          TEXT NOT NULL,
    raw_surface      TEXT,
    parent_turn_id   TEXT,
    correction_of    TEXT,

    -- Model identity
    model_id         TEXT,
    lora_hash        TEXT,
    soul_hash        TEXT,
    prompt_hash      TEXT,

    -- Content
    raw_text         TEXT NOT NULL,
    rewritten_text   TEXT,
    was_rewritten    INTEGER NOT NULL DEFAULT 0,

    -- Audit signals
    signals_present  TEXT NOT NULL DEFAULT '[]',
    signals_absent   TEXT NOT NULL DEFAULT '[]',

    -- Envelope and audit payloads
    evidence_envelope_json TEXT,
    action_proposal_json   TEXT,
    audit_verdict_json     TEXT,
    will_i_json            TEXT,

    -- Memory linkage
    memory_read_ids    TEXT NOT NULL DEFAULT '[]',
    memory_written_ids TEXT NOT NULL DEFAULT '[]',

    -- Cross-DB references (contract, not enforced)
    audit_log_id         INTEGER,
    fabrication_event_id INTEGER,
    self_mod_dialog_id   INTEGER,
    pending_card_id      INTEGER,

    -- Tamper-evidence
    prev_chain_hash TEXT,
    chain_hash      TEXT NOT NULL,

    CHECK (turn_kind IN (
        'user_message',
        'model_reply',
        'tool_call',
        'tool_result',
        'daemon_cycle',
        'approval_decision',
        'self_mod_dialog_step',
        'peer_message_in',
        'peer_message_out',
        'system_event'
    ))
);

CREATE INDEX IF NOT EXISTS idx_turns_tenant_ts
    ON turns (tenant_id, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_turns_surface_ts
    ON turns (tenant_id, surface, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_turns_raw_surface_ts
    ON turns (tenant_id, raw_surface, timestamp DESC)
    WHERE raw_surface IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_turns_kind_ts
    ON turns (tenant_id, turn_kind, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_turns_parent
    ON turns (parent_turn_id)
    WHERE parent_turn_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_turns_model
    ON turns (model_id, timestamp DESC)
    WHERE model_id IS NOT NULL;

-- ---------------------------------------------------------------------------
-- §4.3  claims — what was claimed, immutable
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS claims (
    claim_id               INTEGER PRIMARY KEY AUTOINCREMENT,
    turn_id                TEXT NOT NULL,
    tenant_id              TEXT NOT NULL DEFAULT 'owner',
    fact                   TEXT NOT NULL,
    extracted_at           REAL NOT NULL,
    extractor_version      TEXT NOT NULL,
    parent_turn_chain_hash TEXT NOT NULL,
    FOREIGN KEY (turn_id) REFERENCES turns(turn_id)
);

CREATE INDEX IF NOT EXISTS idx_claims_tenant_turn
    ON claims (tenant_id, turn_id);

CREATE INDEX IF NOT EXISTS idx_claims_extracted_ts
    ON claims (tenant_id, extracted_at DESC);

-- ---------------------------------------------------------------------------
-- §4.3a  claim_judgements — every judgement attempt, append-only
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS claim_judgements (
    judgement_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_id             INTEGER NOT NULL,
    tenant_id            TEXT NOT NULL DEFAULT 'owner',
    judged_at            REAL NOT NULL,
    judged_by            TEXT NOT NULL,
    judge_model_id       TEXT,
    provenance           TEXT,
    evidence_refs_json   TEXT NOT NULL,
    confidence           REAL,
    audit_verdict        TEXT NOT NULL,
    parent_claim_witness TEXT NOT NULL,
    FOREIGN KEY (claim_id) REFERENCES claims(claim_id)
);

CREATE INDEX IF NOT EXISTS idx_judgements_claim_ts
    ON claim_judgements (claim_id, judged_at DESC);

CREATE INDEX IF NOT EXISTS idx_judgements_tenant_ts
    ON claim_judgements (tenant_id, judged_at DESC);

CREATE INDEX IF NOT EXISTS idx_judgements_provenance
    ON claim_judgements (tenant_id, provenance, judged_at DESC)
    WHERE provenance IS NOT NULL;

-- ---------------------------------------------------------------------------
-- §4.4  model_swaps — model-agnostic spine identity history
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS model_swaps (
    swap_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id         TEXT NOT NULL DEFAULT 'owner',
    timestamp         REAL NOT NULL,
    from_model_id     TEXT,
    from_lora_hash    TEXT,
    to_model_id       TEXT NOT NULL,
    to_lora_hash      TEXT,
    soul_hash_before  TEXT,
    soul_hash_after   TEXT,
    gold_corpus_hash  TEXT,
    eval_results_json TEXT NOT NULL,
    decision          TEXT NOT NULL,
    decision_reason   TEXT NOT NULL,
    operator          TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_swaps_tenant_ts
    ON model_swaps (tenant_id, timestamp DESC);

-- ---------------------------------------------------------------------------
-- §4.3a  Views
-- ---------------------------------------------------------------------------
CREATE VIEW IF NOT EXISTS latest_claim_judgement AS
SELECT cj.*
FROM claim_judgements cj
JOIN (
    SELECT claim_id, MAX(judged_at) AS last_ts
    FROM claim_judgements
    GROUP BY claim_id
) latest
  ON cj.claim_id = latest.claim_id
 AND cj.judged_at = latest.last_ts;

CREATE VIEW IF NOT EXISTS claims_with_judgement AS
SELECT
    c.claim_id,
    c.turn_id,
    c.tenant_id,
    c.fact,
    c.extracted_at,
    c.extractor_version,
    c.parent_turn_chain_hash,
    lcj.provenance,
    lcj.confidence,
    lcj.audit_verdict,
    lcj.judged_at,
    lcj.judged_by
FROM claims c
LEFT JOIN latest_claim_judgement lcj
       ON lcj.claim_id = c.claim_id;
