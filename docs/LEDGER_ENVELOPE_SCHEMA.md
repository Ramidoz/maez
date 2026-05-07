# Ledger / Evidence Envelope / Provenance — Joint Schema

**Slice 1 of Project A completion. Paper artifact. No implementation in this doc.**

**Status:** Draft for review (NOT ratified)
**Author:** Claude (drafted 2026-05-06, revised same day after audit pushback)
**Reviewers needed:** Rohit, plus one external (Codex or Hermes)
**Companion docs:** [MAEZ_FRONTIER.md](MAEZ_FRONTIER.md) §6 (dependency graph), §9.1 (build order)

---

## 0. Why this exists

Per [MAEZ_FRONTIER.md](MAEZ_FRONTIER.md) §6, the personalization stack has six layers and the dependency graph has a single root: **the ledger.** Every other layer reads from it. If the ledger schema is wrong, fixing it later requires a migration across persistent stores — the kind of operation that kills projects.

The ledger, the evidence envelope, and the provenance classes share one vocabulary. The provenance classes are the *enum* the ledger and envelope both use. The ledger records *what was claimed and what backed it*; the envelope declares *what may be claimed this turn*. Building any of the three in isolation causes drift.

This doc fixes the joint schema before any code lands.

---

## 1. Design principles

1. **B-ready for schema migration, NOT B-safe at runtime.** Every row has `tenant_id` (always `'owner'` for now, present and indexed) so that adding a second tenant later does not require a destructive schema change. **This alone does not make Maez multi-tenant safe.** Hard multi-tenancy (Project B) additionally requires path isolation (per-tenant DB file paths), process isolation (per-tenant runtime), encryption/key separation (per-tenant keys), and query guards (every read/write asserts current tenant matches row tenant). Schema is one of four B-prerequisites; the other three are out of scope for this doc.
2. **Append-only.** Rows are never updated. Corrections are new rows that link to the corrected row via `parent_turn_id` and a `correction_of` field. Enforced via SQLite trigger that raises on UPDATE/DELETE against `turns` and `claims`.
3. **Tamper-evident.** Each row carries a hash of the previous row's `chain_hash` plus its own canonical content. Breaking the chain means tampering happened. See §6 for crash semantics.
4. **Schema-versioned.** A `meta` table tracks the schema version. Migrations append new versions; old data stays readable.
5. **Single-purpose DB file.** `memory/ledger.db` is its own SQLite file. Easy to vacuum, easy to back up, easy to copy. (Per-tenant variant for Project B: `memory/<tenant_id>/ledger.db`.)
6. **Foreign keys to existing stores documented, not enforced.** SQLite cross-DB FKs aren't enforceable. The contract is in this doc and verified by tests + a reconciliation job. See §5 and §6.2 for crash semantics.
7. **WAL mode.** Concurrent reads (cockpit) while daemon writes. Standard pattern, no contention.
8. **No PII leakage in keys or indexes.** The ledger row may contain PII in the body, but indexes are on tenant_id, timestamp, surface, turn_id, turn_kind — never on user content.
9. **Multi-kind turns.** The ledger records *every* event in the conversation lifecycle — user messages, tool results, daemon cycles, approval decisions, peer messages, system events — not just model replies. See `turn_kind` enum in §4.2.

---

## 2. The provenance enum

Six classes. Every claim a Maez reply makes must map to exactly one. The audit layer weights them differently.

| Class | Definition | Weight | Required evidence |
|---|---|---|---|
| `owner-said` | Came from the owner's words this turn or in a prior verified turn (`source_kind="chat"` from owner). | Strongest | turn_id of the source turn |
| `tool-verified` | Result of a tool call (web search, file read, shell command, sensor read) within the last N turns. | Strongest | tool_call_id + result hash |
| `observed` | From a perception snapshot (camera presence, screen obs, system stats, calendar). | Strong | snapshot_id + timestamp |
| `recalled` | From a memory layer (raw / daily / core / continuity / lived / reflection). | Medium | memory_ids[] |
| `inferred` | Deduced from any combination of above with explicit reasoning chain. | Weak | reasoning_chain_id (a turn_id with the deduction) |
| `synthesized` | Meta-observation from the reflection layer (`source_kind="reflection"`). | Weak | source_episode_ids[] from the reflection's grounding |

**Audit rule:** A reply containing claims with no provenance class — or with `inferred`/`synthesized` claims that lack the required evidence — must be flagged or rewritten by audit Pass 2.

**Planned code anchor (Slice 2 implementation, not yet built):** `core.audit.provenance.ProvenanceClass` enum. String values exactly as written above (kebab-case, lowercase). No aliases.

---

## 3. The evidence envelope

**Built before generation.** Read by the daemon prompt as a constraint section. Logged into the ledger row.

### 3.1 Structure

```python
@dataclass
class EvidenceEnvelope:
    turn_id: str                          # uuid4, links to ledger row
    built_at: float                       # unix timestamp
    schema_version: int                   # matches ledger.schema_version

    claimable: list[ClaimSlot]            # what MAY be claimed, with provenance
    forbidden: list[ForbiddenClaim]       # what MUST NOT be claimed (and why)

    world_state: WorldStateBrief          # current snapshots
    memory_brief: MemoryBrief             # recalled items with ids
    tool_results: list[ToolResultRef]     # recent tool calls available

    signals_present: list[str]            # canonical signal labels (compatibility with audit_signal_manifest)
    signals_absent: list[str]             # labels for signals that should exist but don't

@dataclass
class ClaimSlot:
    fact: str                             # human-readable claim shape ("owner is at his desk")
    provenance: ProvenanceClass           # one of the 6
    evidence_refs: dict                   # populated per-class (see §2)
    confidence: float                     # 0..1

@dataclass
class ForbiddenClaim:
    fact: str                             # what the prompt may try to claim
    reason: str                           # why it's forbidden ("no presence snapshot this turn")
```

### 3.2 Prompt injection

The envelope is rendered into the daemon prompt as:

```
[EVIDENCE ENVELOPE — TURN <turn_id>]
You may claim:
  - "owner is at his desk"  (observed; presence snapshot 2026-05-06T18:02Z)
  - "owner asked about X"   (owner-said; turn_id abc123)
  - "the OpenRGB install failed"  (tool-verified; shell call result_hash=xyz)

You may NOT claim:
  - anything about the calendar (signal absent: calendar)
  - anything about screen contents (signal absent: screen observation)

If you must speak about a forbidden topic, name the absence ("I don't have a calendar read right now") instead of confabulating.
[END ENVELOPE]
```

The audit Pass 2 receives the envelope as part of its input and uses it to grade compliance.

---

## 4. The ledger schema (SQLite DDL)

### 4.1 `meta` table

```sql
CREATE TABLE meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
-- Seeded on first run:
-- INSERT INTO meta(key, value) VALUES ('schema_version', '1');
-- INSERT INTO meta(key, value) VALUES ('genesis_hash', '<hash_of_first_row>');
```

### 4.2 `turns` table — the ledger root

The ledger records every event in the conversation lifecycle, not just model replies. `turn_kind` declares which kind, and several columns are NULL for kinds where they don't apply (e.g., a `user_message` turn has no `model_id` or `audit_verdict_json`).

**`turn_kind` enum (string values):**
- `user_message` — incoming from owner-facing human surfaces
- `model_reply` — outgoing reply generated by the brain
- `tool_call` — a tool was invoked (run_shell, web_search, file_read, etc.)
- `tool_result` — result returned from a tool call
- `daemon_cycle` — internal monologue / proactive narration during ~30s tick
- `approval_decision` — user approved or rejected a pending card
- `self_mod_dialog_step` — one turn within a Lane 3 self-modification dialog
- `peer_message_in` — inbound from another Maez (Project C)
- `peer_message_out` — outbound to another Maez (Project C)
- `system_event` — startup, shutdown, integrity violation, model swap, etc.

```sql
CREATE TABLE turns (
    -- Identity
    turn_id          TEXT PRIMARY KEY,        -- uuid4
    tenant_id        TEXT NOT NULL DEFAULT 'owner',
    timestamp        REAL NOT NULL,           -- unix float
    schema_version   INTEGER NOT NULL,
    turn_kind        TEXT NOT NULL,           -- enum above

    -- Surface and routing
    surface          TEXT NOT NULL,           -- canonical group; see surface enum below
    raw_surface      TEXT,                    -- exact caller label (e.g. telegram_recovery, daemon_cycle_retry)
    parent_turn_id   TEXT,                    -- for follow-ups, recoveries, dialog continuations
    correction_of    TEXT,                    -- if this turn corrects a prior turn (append-only correction pattern)

    -- Model identity (NULL for non-model kinds: user_message, tool_call, tool_result, system_event)
    model_id         TEXT,                    -- e.g., 'qwen36-27b'
    lora_hash        TEXT,                    -- adapter fingerprint, NULL if none or N/A
    soul_hash        TEXT,                    -- hash of soul.md at turn time, NULL for non-model kinds
    prompt_hash      TEXT,                    -- hash of full prompt sent to model, NULL for non-model kinds

    -- Content
    -- For model_reply: raw_text is the model's first-pass output
    -- For user_message / peer_message_in / tool_result: raw_text is the inbound content
    -- For system_event / approval_decision: raw_text is a structured event description
    raw_text         TEXT NOT NULL,
    rewritten_text   TEXT,                    -- model_reply only; final user-facing text if audit Pass 2 rewrote
    was_rewritten    INTEGER NOT NULL DEFAULT 0,

    -- Audit signals (model_reply + daemon_cycle; NULL/empty for kinds where audit didn't run)
    signals_present  TEXT NOT NULL DEFAULT '[]',  -- JSON list of strings
    signals_absent   TEXT NOT NULL DEFAULT '[]',  -- JSON list of strings

    -- Envelope and audit (full structured records, kind-dependent)
    evidence_envelope_json  TEXT,             -- model_reply / daemon_cycle / peer_message_out only
    action_proposal_json    TEXT,             -- if turn proposed an action (any kind that can propose)
    audit_verdict_json      TEXT,             -- model_reply / daemon_cycle / approval_decision / self_mod_dialog_step
    will_i_json             TEXT,             -- Stage 6 deliberation if applicable

    -- Memory linkage (split: read context vs write side-effects)
    memory_read_ids     TEXT NOT NULL DEFAULT '[]',   -- JSON list of memory IDs *read* to ground this turn
    memory_written_ids  TEXT NOT NULL DEFAULT '[]',   -- JSON list of memory IDs *written* by this turn

    -- Cross-DB references (contract, not enforced; see §5 + §6.2)
    audit_log_id          INTEGER,            -- → audit_log.db::audit_log.id
    fabrication_event_id  INTEGER,            -- → fabrication_log.db::fabrication_events.id (nullable)
    self_mod_dialog_id    INTEGER,            -- → self_mod_dialogs.db::self_mod_dialogs.id (nullable; dialog_id text also stored in raw/evidence payload)
    pending_card_id       INTEGER,            -- → pending_cards.db::pending_cards.id (nullable; request_id text also stored in raw/evidence payload)

    -- Tamper-evidence
    prev_chain_hash  TEXT,                    -- hash of previous row's chain_hash, NULL only for genesis
    chain_hash       TEXT NOT NULL            -- sha256(prev_chain_hash || canonical_row_bytes)
);

CREATE INDEX idx_turns_tenant_ts ON turns (tenant_id, timestamp DESC);
CREATE INDEX idx_turns_surface_ts ON turns (tenant_id, surface, timestamp DESC);
CREATE INDEX idx_turns_raw_surface_ts ON turns (tenant_id, raw_surface, timestamp DESC) WHERE raw_surface IS NOT NULL;
CREATE INDEX idx_turns_kind_ts ON turns (tenant_id, turn_kind, timestamp DESC);
CREATE INDEX idx_turns_parent ON turns (parent_turn_id) WHERE parent_turn_id IS NOT NULL;
CREATE INDEX idx_turns_model ON turns (model_id, timestamp DESC) WHERE model_id IS NOT NULL;
```

**`surface` enum (canonical groups):**
- `telegram` — owner-facing Telegram surfaces, including raw labels like `telegram_text`, `telegram_recovery`, `telegram/show`
- `telegram_public` — stranger-facing Telegram bot
- `cockpit` — Workstation / cockpit browser surface
- `web_chat` — legacy web `/chat` owner bridge
- `daemon_cycle` — background narration and retry surfaces, including `daemon_cycle_retry`
- `self_mod_dialog` — Lane 3 self-modification dialog
- `voice` — future voice surface
- `inter_maez` — Project C peer messages
- `scheduled` — morning briefing, nightly journal, developmental heartbeat
- `tooling` — action engine, decision pipeline, GitHub publish, brain-loop dispatch, training proposals
- `test` — test/probe/dev harness calls, excluded from production-rate metrics by default
- `system` — startup, shutdown, integrity, reconciliation, model swap, and other non-conversational events

`raw_surface` preserves the exact surface label emitted by the caller. Queries that answer product questions use `surface`; forensic queries use `raw_surface`.

**Per-kind NOT-NULL contract** (enforced by the ledger writer in Slice 2, validated by `tests/test_ledger_kind_invariants.py`):

| Kind | Required non-null | Forbidden non-null |
|---|---|---|
| `user_message` | raw_text | model_id, prompt_hash, audit_verdict_json |
| `model_reply` | raw_text, model_id, prompt_hash, soul_hash, evidence_envelope_json, audit_verdict_json | — |
| `tool_call` | raw_text, action_proposal_json | model_id |
| `tool_result` | raw_text, parent_turn_id | model_id, evidence_envelope_json |
| `daemon_cycle` | raw_text, model_id, prompt_hash, soul_hash, evidence_envelope_json, audit_verdict_json | — |
| `approval_decision` | raw_text, audit_verdict_json, pending_card_id | model_id |
| `self_mod_dialog_step` | raw_text, audit_verdict_json, self_mod_dialog_id | — |
| `peer_message_in` | raw_text | — |
| `peer_message_out` | raw_text, evidence_envelope_json, audit_verdict_json | — |
| `system_event` | raw_text | model_id, prompt_hash |

### 4.3 `claims` table — what was claimed, immutable

Every claim shape extracted from `rewritten_text` (or `raw_text` if not rewritten) gets one row here. **Strictly immutable** — no UPDATEs, no provenance overwrites. Judgement of the claim lives in §4.3a (`claim_judgements`).

```sql
CREATE TABLE claims (
    claim_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    turn_id          TEXT NOT NULL,
    tenant_id        TEXT NOT NULL DEFAULT 'owner',
    fact             TEXT NOT NULL,            -- the claim text (extracted)
    extracted_at     REAL NOT NULL,            -- unix timestamp Pass A ran
    extractor_version TEXT NOT NULL,           -- heuristic version that produced this row

    -- Tamper-witness: must equal turns.chain_hash for this turn_id at insert time
    -- (verified by tests/test_ledger_chain.py + reconciliation)
    parent_turn_chain_hash TEXT NOT NULL,

    FOREIGN KEY (turn_id) REFERENCES turns(turn_id)
);

CREATE INDEX idx_claims_tenant_turn ON claims (tenant_id, turn_id);
CREATE INDEX idx_claims_extracted_ts ON claims (tenant_id, extracted_at DESC);
```

### 4.3a `claim_judgements` table — every judgement attempt, append-only

Pass B (and any reconciliation re-run) writes a new row here. **No row exists for a claim until it has been judged.** The absence of a `claim_judgements` row for a `claim_id` is itself the signal "extracted but not yet checked."

```sql
CREATE TABLE claim_judgements (
    judgement_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_id         INTEGER NOT NULL,
    tenant_id        TEXT NOT NULL DEFAULT 'owner',
    judged_at        REAL NOT NULL,
    judged_by        TEXT NOT NULL,            -- 'pass_b_judge' | 'reconciliation' | 'owner_manual'
    judge_model_id   TEXT,                     -- model that produced this judgement, NULL if owner_manual
    provenance       TEXT,                     -- one of the 6 enum values, NULL if unable_to_classify
    evidence_refs_json TEXT NOT NULL,
    confidence       REAL,                     -- 0..1, NULL if provenance is NULL
    audit_verdict    TEXT NOT NULL,            -- 'grounded' | 'rewritten_in_reply' | 'flagged' | 'unable_to_classify'

    -- Tamper-witness chain: must equal claims.parent_turn_chain_hash at insert time
    -- (so a judgement is bound to the turn-state in which the claim was extracted)
    parent_claim_witness TEXT NOT NULL,

    FOREIGN KEY (claim_id) REFERENCES claims(claim_id)
);

CREATE INDEX idx_judgements_claim_ts ON claim_judgements (claim_id, judged_at DESC);
CREATE INDEX idx_judgements_tenant_ts ON claim_judgements (tenant_id, judged_at DESC);
CREATE INDEX idx_judgements_provenance ON claim_judgements (tenant_id, provenance, judged_at DESC) WHERE provenance IS NOT NULL;

-- Latest-judgement view for cockpit queries
CREATE VIEW latest_claim_judgement AS
SELECT cj.*
FROM claim_judgements cj
JOIN (
    SELECT claim_id, MAX(judged_at) AS last_ts
    FROM claim_judgements
    GROUP BY claim_id
) latest ON cj.claim_id = latest.claim_id AND cj.judged_at = latest.last_ts;

-- Convenience view: every claim with its latest judgement (or NULL if not yet judged)
CREATE VIEW claims_with_judgement AS
SELECT
    c.*,
    lcj.provenance,
    lcj.confidence,
    lcj.audit_verdict,
    lcj.judged_at,
    lcj.judged_by
FROM claims c
LEFT JOIN latest_claim_judgement lcj ON lcj.claim_id = c.claim_id;
```

**Why two tables instead of one updatable row.** The two-table shape preserves strict append-only across the entire ledger. The history of judgement attempts becomes data — if reconciliation re-runs Pass B with a newer judge model, the prior judgement stays visible, and you can read the difference. This is what makes the ledger more trustworthy than memory: nothing is silently overwritten.

### 4.4 `model_swaps` table — for §11 model-agnostic spine

Every brain swap or LoRA rotation gets a row. The chain across rows is the identity history.

```sql
CREATE TABLE model_swaps (
    swap_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id        TEXT NOT NULL DEFAULT 'owner',
    timestamp        REAL NOT NULL,
    from_model_id    TEXT,                    -- NULL on first registration
    from_lora_hash   TEXT,
    to_model_id      TEXT NOT NULL,
    to_lora_hash     TEXT,
    soul_hash_before TEXT,
    soul_hash_after  TEXT,
    gold_corpus_hash TEXT,                    -- hash of the corpus used to fine-tune the new model
    eval_results_json TEXT NOT NULL,          -- voice/refusal/audit/memory continuity scores
    decision         TEXT NOT NULL,           -- 'approved' | 'rejected'
    decision_reason  TEXT NOT NULL,
    operator         TEXT NOT NULL            -- 'owner' (only owner can approve swaps)
);

CREATE INDEX idx_swaps_tenant_ts ON model_swaps (tenant_id, timestamp DESC);
```

---

## 5. Cross-DB foreign-key contract

SQLite cannot enforce cross-database foreign keys. The contract is documented here and verified by integration tests + a reconciliation job.

| Source column | Target | Nullability | Verifier |
|---|---|---|---|
| `turns.audit_log_id` | `audit_log.db::audit_log.id` | NOT NULL when audit ran (model_reply, daemon_cycle, etc.) | `tests/test_ledger_audit_link.py` + reconciliation |
| `turns.fabrication_event_id` | `fabrication_log.db::fabrication_events.id` | NULL except when fabrication detected | `tests/test_ledger_fabrication_link.py` + reconciliation |
| `turns.self_mod_dialog_id` | `self_mod_dialogs.db::self_mod_dialogs.id` | NULL except for self-mod turns | `tests/test_ledger_selfmod_link.py` + reconciliation |
| `turns.pending_card_id` | `pending_cards.db::pending_cards.id` | NULL except for card-bearing turns | `tests/test_ledger_card_link.py` + reconciliation |
| `claims.turn_id` | `ledger.db::turns.turn_id` | NOT NULL, enforced by SQLite | (within-DB FK, automatic) |

**Write order (Slice 2 implementation contract):**

1. Write the dependent row(s) in `audit_log.db` / `fabrication_log.db` / etc. *first*, capturing their assigned `id` values.
2. Build the ledger `turns` row with those ids populated.
3. Write the `turns` row.
4. Write the `claims` rows for that turn (within the same SQLite transaction as the `turns` row).

This ordering means: at any consistent observation point, *every* ledger row's cross-DB references resolve. There is no transient dangling state visible to readers because each individual DB write is atomic and the references point backward in time.

**Crash semantics:** see §6.2.

---

## 6. The tamper-evidence chain and crash semantics

### 6.1 Chain construction

The `turns` table carries the primary chain. Dependent tables (`claims`, `claim_judgements`) attach to the chain via tamper-witness columns.

**Primary chain (`turns`):**
- Each row's `chain_hash` is `sha256(prev_chain_hash || canonical_row_bytes)`.
- `canonical_row_bytes` = JSON-serialized row with keys sorted, omitting `chain_hash` and `prev_chain_hash` themselves.
- Genesis row: `prev_chain_hash` is NULL, `chain_hash = sha256("genesis" || canonical_row_bytes)`, also written to `meta.genesis_hash`.

**Witness binding (`claims`, `claim_judgements`):**
- `claims.parent_turn_chain_hash` MUST equal the parent turn's `chain_hash` at insert time. Verified at insert by the writer; verified retroactively by the chain verifier.
- `claim_judgements.parent_claim_witness` MUST equal the parent claim's `parent_turn_chain_hash` at insert time. (This binds a judgement to the turn-state-snapshot the claim was extracted under, even if reconciliation re-judges later.)

**Verification:** `scripts/verify_ledger_chain.py` walks the primary chain end-to-end, then walks every claim and every judgement and checks the witness columns match. Run nightly via the orchestrator that produces reflections.

**What this protects against:** silent edits to *any* ledger table. Modifying a `turns` row breaks the chain. Modifying a `claims` row requires also modifying the `parent_turn_chain_hash` to match, which then mismatches the actual `turns.chain_hash` and the verifier flags it. Same for `claim_judgements`.

**What this does NOT protect against:** wholesale deletion or substitution of the entire `ledger.db` file. That's a backup/restore problem, not a chain problem. Mitigation: nightly snapshot to a separate path, retained 30 days.

### 6.2 Crash semantics

The ledger writer touches multiple SQLite databases in §5's order. A crash anywhere in that sequence can leave the system in one of three states:

| State | What happened | Resolution |
|---|---|---|
| **A. No writes landed** | Crash before step 1 (audit_log write). | Nothing to reconcile. Next turn proceeds normally. |
| **B. Dependent rows landed, ledger row missing** | Crash between steps 1–3. Audit log has a row, ledger does not. | Reconciliation job (`scripts/reconcile_ledger.py`) runs at startup AND nightly. Detects orphan dependent rows (`audit_log`, `fabrication_events`, etc.) with no corresponding `turns` row, and writes a synthetic `turn_kind='system_event'` ledger entry referencing them, so the chain remains complete and the orphans become attributable. |
| **C. Ledger row landed, claims missing** | Crash between steps 3–4. `turns` row exists; `claims` rows for it do not. | Same reconciliation job re-runs claim extraction (Slice 4 logic) over the orphan turn's `rewritten_text` and writes the `claims` rows. The chain is unaffected because `claims` are not part of the chain. |

**Hard rule:** the ledger writer must NEVER use a single transaction that spans multiple SQLite databases. Each DB's writes are their own transaction; cross-DB integrity is restored by the reconciliation job, not by attempting a multi-DB atomic write (which SQLite cannot guarantee). This is a deliberate trade: best-effort cross-DB consistency in the steady state, eventual consistency after crashes, with the reconciliation job as the convergence mechanism.

**Reconciliation job invariants** (verified by `tests/test_reconciliation.py`):
- After running, every `audit_log` row has a corresponding `turns` row referencing it (for kinds where audit ran).
- After running, every `turns` row with `was_rewritten=1` has at least one `claims` row.
- The chain remains valid: synthetic reconciliation rows are appended at the chain head, never inserted mid-chain.

### 6.3 Synthetic reconciliation row spec

When §6.2 state B occurs, the reconciliation job appends a `turn_kind='system_event'` row. It does **not** attempt to recreate the missing model/user turn; that would fabricate context. It records the orphan as an integrity event.

Required fields:

| Field | Value |
|---|---|
| `turn_id` | fresh uuid4 generated by reconciliation |
| `tenant_id` | `'owner'` in v1; future Project B derives from the orphan row's tenant context |
| `timestamp` | reconciliation runtime timestamp |
| `turn_kind` | `system_event` |
| `surface` | `system` |
| `raw_surface` | `ledger_reconciliation` |
| `parent_turn_id` | NULL |
| `correction_of` | NULL |
| `model_id`, `lora_hash`, `soul_hash`, `prompt_hash` | NULL |
| `raw_text` | JSON string with `event='orphan_dependent_row'`, `source_db`, `source_table`, `source_id`, `source_ts`, `reason='ledger_write_missing_after_crash_or_legacy_write'` |
| `rewritten_text` | NULL |
| `was_rewritten` | 0 |
| `signals_present`, `signals_absent` | `'[]'` |
| `evidence_envelope_json` | NULL |
| `action_proposal_json` | NULL |
| `audit_verdict_json` | NULL unless the orphan source is `audit_log`, in which case a compact JSON pointer to `audit_log.id` is allowed |
| `will_i_json` | NULL |
| `memory_read_ids`, `memory_written_ids` | `'[]'` |
| FK pointer column | exactly one of `audit_log_id`, `fabrication_event_id`, `self_mod_dialog_id`, `pending_card_id` populated |
| `prev_chain_hash`, `chain_hash` | normal chain append semantics |

Rule: reconciliation rows are evidence *about ledger integrity*, not evidence about Maez's world. They must never be used as provenance for claims except the narrow claim "an orphan dependent row existed and was reconciled."

---

## 7. Migration plan

The ledger is a *new* store. There is no historical migration of old turns into it.

- **Backfill policy:** None. Ledger starts at the moment Slice 2 lands.
- **Existing stores stay:** `audit_log.db`, `fabrication_log.db`, `pending_cards.db`, `self_mod_dialogs.db` continue to exist with their current schemas. The ledger references them by id.
- **Forward path:** When future schema changes are needed, append `schema_version: 2` rows. Old rows stay readable. No destructive migrations.

---

## 8. Test plan (for Slice 2 implementation)

The schema is paper. Slice 2 implements the writer. These are the tests Slice 2 must pass before merging:

1. **Schema integrity** — `tests/test_ledger_schema.py`: every column declared above exists with the right type; every index exists.
2. **Append-only** — `tests/test_ledger_append_only.py`: an UPDATE on `turns` must fail (enforced via trigger).
3. **Chain hash** — `tests/test_ledger_chain.py`: writing 100 rows produces a verifiable chain; tampering with any row's body breaks the chain.
4. **Genesis** — `tests/test_ledger_genesis.py`: first row has NULL `prev_chain_hash`; `meta.genesis_hash` matches.
5. **Cross-DB FK contract** — one test per row in §5.
6. **Tenant filtering** — `tests/test_ledger_tenant_isolation.py`: queries that don't filter by `tenant_id` raise (lint or runtime).
7. **WAL mode** — `tests/test_ledger_wal.py`: concurrent reader during writer doesn't block.
8. **Provenance enum coverage** — `tests/test_provenance_enum.py`: every reply with rewritten_text has at least one row in `claims` with a valid provenance value.
9. **Envelope-claim consistency** — `tests/test_envelope_consistency.py`: every claim in `claims` for a turn has a provenance class that appears in that turn's `evidence_envelope_json`.
10. **Daemon-rewrite-rate signal** — `scripts/validate/track_a_harness.py` reads `claims.audit_verdict` to compute the live rewrite rate that gates adapter training (per [MAEZ_FRONTIER.md §7](MAEZ_FRONTIER.md) hard rule 5).

---

## 9. What this schema enables (downstream slices)

- **Slice 3 (evidence envelope at generation):** writes `evidence_envelope_json` + `signals_present`/`signals_absent` per turn.
- **Slice 4 (provenance tagging):** writes `claims` rows per generated reply, populates `audit_verdict` per claim.
- **Slice 5 (cockpit Session 3):** reads `turns` + `claims` for "click any reply, see why" — the ledger replaces the current scattered-endpoint approach.
- **Slice 6 (anti-sycophancy + uncertainty evals):** harness reads `claims` to compute kindly-resists and appropriate-abstention rates.
- **Slice 8 (will-I deliberator):** writes `will_i_json` on turns where Stage 6 fires.
- **Slice 10 (live acceptance):** every lane's verification produces a known set of ledger rows. The acceptance test asserts those rows exist with the right shape.
- **Project B (multi-tenancy):** dispatcher routes by `tenant_id`. Per-tenant stores partition by the same column. No schema migration required.
- **Project C (inter-Maez):** a Maez announcing or receiving a peer message writes a ledger row with `surface='inter_maez'`. The peer's signature and message hash go in `evidence_envelope_json`.
- **Model swaps:** every swap writes a `model_swaps` row; `turns.model_id` and `turns.lora_hash` carry the identity through the swap; gold-corpus continuity evals read from `claims` to compare voice across the swap boundary.

---

## 10. Claims extraction — v1 policy (load-bearing decision, must resolve before Slice 2)

This is the decision that determines whether the ledger lies elegantly or tells the truth. If claims extraction is wrong, every downstream slice (cockpit "why this reply", anti-sycophancy eval, daemon-rewrite-rate gate, voice-LoRA training) reads from a corrupted source.

**v1 policy (RATIFIED 2026-05-06 with three edits — see §10.1 for ratification record):**

1. **Two-pass extraction, both pre-existing in the audit pipeline.**
   - **Pass A — heuristic.** A deterministic extractor walks the rewritten reply text and pulls out claim-shaped sentences using surface patterns: assertive declaratives, "the X is/was/will Y", numeric assertions, named-entity references, temporal claims, and self-references about Maez's own state. Output: a list of candidate claim strings with surface-feature tags. **Inserts one row per candidate into `claims` (immutable).**
   - **Pass B — LLM-judged.** The audit Pass 2 judge (already running per turn) is extended with a structured-output instruction that returns, alongside its existing verdict, a list of `{claim_id, provenance, evidence_refs, confidence, audit_verdict}` for every candidate Pass A produced. The judge sees the evidence envelope (§3) and grades each candidate against it. **Inserts one row per judgement into `claim_judgements` (also immutable; reconciliation or future re-judge appends new rows).**

2. **Two-table shape, no UPDATEs anywhere.** `claims` rows are immutable from the moment Pass A inserts them. `claim_judgements` rows are immutable from the moment Pass B (or reconciliation, or owner_manual) inserts them. The cockpit queries the `latest_claim_judgement` view to see "what does Maez currently believe about this claim." History stays visible. The ledger preserves strict append-only across all three tables (`turns`, `claims`, `claim_judgements`) — there are no UPDATE carve-outs.

3. **A claim without a `claim_judgements` row is "extracted but not yet checked."** This is the truthful state during the gap between Pass A and Pass B, and during a Pass B failure. The cockpit and audit machinery distinguish "no judgement row yet" from "judgement says provenance=NULL" — the first means we haven't looked, the second means we looked and couldn't classify.

4. **Honest non-deferral, not fail-open.** If Pass B times out or errors, the user-facing reply still ships (existing audit pipeline behavior). The `claims` row stays without a `claim_judgements` row. **Maez may have spoken; the evidence notebook says "not checked yet."** This is *not* a fail-open posture — fail-open is about whether the user gets a reply. The ledger question is about what the notebook records actually happened. The notebook tells the truth even when the user-facing path keeps moving. Reconciliation (§6.2) revisits unjudged claims at the next quiet cycle and inserts a `claim_judgements` row.

5. **Judgements with `provenance=NULL`** (judge ran but couldn't classify) are written with `audit_verdict='unable_to_classify'`. They count toward the daemon-rewrite-rate metric and are flagged for owner review weekly.

6. **No third-party LLM in the extractor.** Pass B uses Maez's own judge (currently retired Qwen3.5-4B; otherwise the brain itself if judge is offline). Sending claim extraction to OpenRouter or Claude or Gemini would leak production text and would teach Maez to sound like the extractor's voice, not its own. Hard rule, no exceptions, enforced by a runtime check that the configured judge endpoint resolves to a Maez-owned model.

**Why two passes and not one:**
- Pure heuristic misses semantic claims (Maez says "I noticed you've been quiet" — that's a claim about the user's state, but the surface form is innocuous).
- Pure LLM is non-deterministic and expensive per turn. The heuristic shortlist makes the LLM's job bounded and the audit cost predictable.
- The separation also gives reconciliation a clean handoff: heuristic always runs synchronously; LLM judgement can be deferred or re-run, and re-runs append rather than overwrite.

**v1 acceptance — hard gates, not floors that erode:**

Slice 4 ships when 100 sampled turns show:
- **≥95% claim recall.** ≥95% of human-rated claims appear in the `claims` table.
- **≥80% non-NULL provenance.** ≥80% of `claims` rows have a corresponding `claim_judgements` row with non-NULL `provenance`.
- The remaining ≤20% (NULL provenance or no judgement yet) are reviewed by Rohit weekly and used to grow the heuristic and refine the judge prompt.

**If first measurement falls short, the response is NOT "lower the bar."** The response is one of:
- **Fix the extractor or judge** until the bar is met, OR
- **Amend the schema with explicit evidence and a schema_version bump.** A written amendment in this doc, ratified by Rohit, with the corpus showing why the original numbers are unreachable (e.g., some claim shapes are inherently fuzzy and require redefining "claim"). Numbers may move with cause; they do not erode silently.

The bar protects the ledger's honesty. Quietly relaxing it is how QA gates die.

**Open question deferred to Slice 4 ratification:** the exact heuristic patterns. v1 schema commits to the *two-pass shape*, not specific regex. Heuristic implementation is not a schema concern.

### 10.1 Ratification record

| Date | Decision | Edits applied |
|---|---|---|
| 2026-05-06 | Rohit ratified §10 | (#2) Rejected single-table UPDATE carve-out; required separate `claim_judgements` table with `latest_claim_judgement` view. (#3) Required wording change from "fail-open posture" to "honest non-deferral" with explicit "Maez may speak; notebook says not checked yet." (#5) Required hard-gate language: failures must be fixed or amended-with-evidence, never silently relaxed. |

---

## 11. Other open questions (RATIFIED 2026-05-06)

1. **Hash algorithm: sha256.** Ratified. Universally available and audit-friendly; perf is not the bottleneck.
2. **Retention policy: deferred to Project A.5.** Ratified. Disk is fine; decide when a real constraint surfaces.
3. **Normalization of `evidence_envelope_json` / `audit_verdict_json`: deferred to Slice 5.** Ratified. Wait until cockpit query patterns reveal the need.
4. **`tenant_id` mid-tenant rename: forbidden in v1.** Ratified. `tenant_aliases` is a v2 feature only if ever needed.
5. **New `turn_kind`: requires schema_version bump.** Ratified. Deliberately not free; prevents enum drift.

---

## 12. Sign-off checklist

This schema is ready for Slice 2 implementation when:

- [x] [MAEZ_FRONTIER.md](MAEZ_FRONTIER.md) is committed (cross-link target exists in git) — `aa1cb1a`
- [x] Rohit/Codex ratified the provenance enum values (§2) — 2026-05-06, accepted as v1
- [x] Rohit/Codex ratified the `turn_kind` enum values and per-kind NOT-NULL contract (§4.2) — 2026-05-06, with `peer_message_in.parent_turn_id` no longer required
- [x] Rohit/Codex confirmed the canonical surface enum and `raw_surface` preservation cover all current and near-term surfaces (§4.2 `surface` column) — 2026-05-06
- [x] **The v1 claims-extraction policy (§10) has been ratified or rewritten** — ratified 2026-05-06 with three edits (see §10.1)
- [x] External review completed — Codex reviewed and signed off 2026-05-06 after table-name, surface, and reconciliation-spec edits
- [x] The cross-DB FK contract (§5) has been verified against the current schema of `audit_log.db`, `fabrication_log.db`, `pending_cards.db`, `self_mod_dialogs.db` — 2026-05-06
- [x] The crash semantics (§6.2–§6.3) reconciliation job has been scoped and the synthetic row shape is accepted — 2026-05-06
- [x] The lower-stakes open questions in §11 have explicit decisions — ratified 2026-05-06

---

*This is paper. §12 is now checked off for Slice 2 design. Code still lands test-first: Slice 2 must implement the writer, reconciliation job, and schema tests before any production daemon writes to `ledger.db`.*
