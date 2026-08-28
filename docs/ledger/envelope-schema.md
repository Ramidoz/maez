# Ledger / Evidence Envelope / Provenance — Joint Schema

**Slice 1 of Project A completion. Paper artifact. No implementation in this doc.**

**Status:** Ratified 2026-05-06 (Slice 2 design checkpoint). Schema additions land via amendments and a schema_version bump per §11; the ratification covers the §2 enum and §3–§4 structures as of that date. Slice 3.0b (2026-05-07) extends the §2 enum with `self-history` (kebab-case provenance value) and §3 with the matching `self_history` slot (snake_case Python field).
**Author:** Claude (drafted 2026-05-06, revised same day after audit pushback)
**Companion docs:** [MAEZ_FRONTIER.md](../MAEZ_FRONTIER.md) §6 (dependency graph), §9.1 (build order)

---

## 0. Why this exists

Per [MAEZ_FRONTIER.md](../MAEZ_FRONTIER.md) §6, the personalization stack has six layers and the dependency graph has a single root: **the ledger.** Every other layer reads from it. If the ledger schema is wrong, fixing it later requires a migration across persistent stores — the kind of operation that kills projects.

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

Seven classes. Every claim a Maez reply makes must map to exactly one. The audit layer weights them differently.

| Class | Definition | Weight | Required evidence |
|---|---|---|---|
| `owner-said` | Came from the owner's words this turn or in a prior verified turn (`source_kind="chat"` from owner). | Strongest | turn_id of the source turn |
| `tool-verified` | Result of a tool call (web search, file read, shell command, sensor read) within the last N turns. | Strongest | tool_call_id + result hash |
| `observed` | From a perception snapshot (camera presence, screen obs, system stats, calendar). | Strong | snapshot_id + timestamp |
| `recalled` | From a memory layer (raw / daily / core / continuity / lived / reflection). | Medium | memory_ids[] |
| `inferred` | Deduced from any combination of above with explicit reasoning chain. | Weak | reasoning_chain_id (a turn_id with the deduction) |
| `synthesized` | Meta-observation from the reflection layer (`source_kind="reflection"`). | Weak | source_episode_ids[] from the reflection's grounding |
| `self-history` | Claims about Maez's prior utterances or actions, traceable to ledger turn_ids of prior `model_reply`, `daemon_cycle`, or `peer_message_out` entries within the relevant session/chat scope. Symmetric with how `tool_results` (slot) pairs with `tool-verified` (provenance value). Added Slice 3.0b 2026-05-07 to address self-history fabrications (e.g. "I told you the weather earlier" with no such ledger row). The provenance VALUE is kebab-case to match `owner-said` / `tool-verified`; the envelope SLOT field is `self_history` (snake_case Python convention). | Strong | self_history slot ref (turn_id + utterance_summary) |

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
    self_history: list[SelfHistoryRef]    # bounded prior-utterance summaries (slice 3.0b)

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

@dataclass
class SelfHistoryRef:
    turn_id: str                          # links into ledger.turns
    timestamp: float                      # unix seconds, prior turn's wall-clock time
    utterance_summary: str                # ≤200 chars; bounded summary of what was said
    kind: str                             # one of: model_reply, daemon_cycle, peer_message_out
```

**Slice 3.0b notes (2026-05-07):**

- The `self_history` slot is OPTIONAL on every turn_kind. Absence/empty list means "no prior-utterance evidence available this turn." It is not yet REQUIRED on `model_reply` / `daemon_cycle` because the population path (the envelope BUILDER) is not yet implemented.
- **Population is the responsibility of the envelope BUILDER (slice 3 proper, not 3.0b).** The builder will run a bounded ledger lookback over the last N `model_reply` / `daemon_cycle` / `peer_message_out` turns within the relevant session/chat scope, summarize each into ≤200 chars, and attach them as `SelfHistoryRef` entries. Slice 3.0b only ratifies the schema vocabulary, validators, and minimal consumer awareness.
- Pairing rule: a claim labeled `provenance="self-history"` MUST cite one or more `turn_id`s that appear in this envelope's `self_history` slot. Note the asymmetry — the provenance VALUE is kebab-case (`self-history`), the slot FIELD is snake_case (`self_history`). Enforcement of that pairing is a Slice 4 (provenance tagging) consumer concern; this slice declares the contract only.

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

    -- S1 row provenance / privacy / ordering substrate
    taint_labels_json TEXT NOT NULL DEFAULT '[]', -- JSON list from owner_utterance, self_generated, tool_output, internet_derived, third_party
    privacy_access    TEXT NOT NULL DEFAULT 'public' CHECK (privacy_access IN ('public', 'sealed_adjacent')),
    chain_position    INTEGER NOT NULL DEFAULT 0, -- monotonic writer-assigned ordinal; genesis=0

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
CREATE UNIQUE INDEX idx_turns_chain_position ON turns (chain_position);
```

> **RETIRED 2026-08-27 by owner ruling — NOT IMPLEMENTED, and must not be.**
> The enum below sorts surfaces into groups and says what each one
> MEANS ("owner-facing", "stranger-facing", "future voice surface",
> "excluded from production-rate metrics"). The owner ruled that we do
> not define Maez's body parts for it: *"Our job is to just provide the
> body. Let it run loops or whatever to understand what each part of it
> is and understand itself. I don't define anything for Maez."*
> Meaning is learned through Maez's own loops; the substrate supplies
> identifiers only.
>
> The code never implemented this. What ships instead is
> `core/body/surface_registry.py` — stable identifiers with zero
> semantics, no groups and no descriptions, enforced by an allowlist
> test. Its ids are names the body already emits (`cli`,
> `telegram_text`, `web_owner`); it mints none, because `surface` sits
> inside the chain-hash preimage.
>
> Kept below as history so the divergence is legible rather than
> silently deleted. Do not treat any of it as a contract.

**`surface` enum (canonical groups) — RETIRED, historical only:**
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
- `canonical_row_bytes` = JSON-serialized row with keys sorted, omitting chain links and derived/readout metadata: `chain_hash`, `prev_chain_hash`, `chain_position`, `lifecycle_stage`, `audit_trace_label`, `audit_trace_value_schema`, and `audit_trace_metadata_shape`.
- `taint_labels_json` and `privacy_access` are hash-included; tampering with provenance or privacy labels must break verification.
- `chain_position` is not hash-included. It is derived from the `prev_chain_hash` walk and the verifier checks `chain_position == walk index` so the column and chain walk agree.
- Genesis row: `prev_chain_hash` is NULL, `chain_hash = sha256("genesis" || canonical_row_bytes)`, also written to `meta.genesis_hash`.

**Witness binding (`claims`, `claim_judgements`):**
- `claims.parent_turn_chain_hash` MUST equal the parent turn's `chain_hash` at insert time. Verified at insert by the writer; verified retroactively by the chain verifier.
- `claim_judgements.parent_claim_witness` MUST equal the parent claim's `parent_turn_chain_hash` at insert time. (This binds a judgement to the turn-state-snapshot the claim was extracted under, even if reconciliation re-judges later.)

**Verification:** `scripts/verify_ledger_chain.py` walks the primary chain end-to-end, then walks every claim and every judgement and checks the witness columns match. Run nightly via the orchestrator that produces reflections.

**Head pointer (truncation defense):** `meta.last_chain_hash` is updated by the writer in the same transaction as every `turns` INSERT. The chain verifier asserts that the final reached row's `chain_hash` equals `meta.last_chain_hash`. Without this anchor, an attacker who deletes the last N rows of `turns` would pass verification cleanly — the remaining rows are internally consistent, the walker just sees a shorter chain. Persisting the head closes the truncation gap.

**What this protects against:**
- Silent edits to a `turns` row's body: `chain_hash` recomputation flags it.
- Silent rewrites of a `turns` row's `chain_hash`: the next row's `prev_chain_hash` no longer matches, AND the head pointer no longer matches if it was the tail.
- Truncation of the chain tail: head pointer mismatch flags it.
- Insertion of a forged turn: `prev_chain_hash` won't match the previous row, OR the next row's link breaks, OR both.
- Tampering with a claim's `parent_turn_chain_hash`: claim witness verifier flags the mismatch against the parent turn's `chain_hash`.
- Coordinated rewrite of a turn's body AND dependent claims' `parent_turn_chain_hash` to match: the chain walker's recipe recomputation catches the turn body tamper, even if the witnesses appear consistent in isolation.

**What this does NOT protect against (known limitations):**

1. **Tampering with a claim or claim_judgement BODY.** The witness columns bind *parent identity* — they do not hash the claim's `fact`, `extracted_at`, `extractor_version`, or any judgement content. An attacker who rewrites `claims.fact` from `"owner is at his desk"` to `"owner approved $10k transfer"` while leaving `parent_turn_chain_hash` untouched: invisible to all current verifiers. Tightening this requires extending the chain to cover claim and judgement bodies (each row would gain its own `chain_hash` linked into the primary chain), which is a schema_version bump and a future slice (tracked as Slice 2.5 candidate).

2. **Coordinated rewrite of `turns.chain_hash` AND `meta.last_chain_hash` AND every dependent claim/judgement witness in lockstep.** With the head pointer in place, the attacker now needs to rewrite N + 1 + M places consistently. The chain walker's recipe recompute still catches the turn body tamper because canonical bytes can't be forged. So this is theoretically resistant — but if the body is unchanged and only metadata is shuffled, the verifier accepts it. Same medicine as #1: extend the chain.

3. **Wholesale deletion or substitution of the entire `ledger.db` file.** That's a backup/restore problem, not a chain problem. Mitigation: nightly snapshot to a separate path, retained 30 days.

**Witness verifier design note:** `verify_claim_witnesses` and `verify_judgement_witnesses` are *relative-binding* checks — they compare a stored witness to the currently-stored parent identity. They MUST be paired with `verify_chain` (which recomputes parent identity from canonical bytes) for full integrity. The production walker (`scripts/verify_ledger_chain.py`) runs all three unconditionally; downstream callers (e.g., a future cockpit "is this binding intact" probe) MUST follow the same discipline.

### 6.2 Crash semantics

The ledger writer touches multiple SQLite databases in §5's order. A crash anywhere in that sequence can leave the system in one of three states:

| State | What happened | Resolution |
|---|---|---|
| **A. No writes landed** | Crash before step 1 (audit_log write). | Nothing to reconcile. Next turn proceeds normally. |
| **B. Dependent rows landed, ledger row missing** | Crash between steps 1–3. Audit log has a row, ledger does not. | Operator runs `scripts/reconcile_ledger.py` manually (dry-run first, then `--apply` with `MAEZ_LEDGER_WRITES=1`). The job detects orphan dependent rows (`audit_log`, `fabrication_events`, etc.) with no corresponding `turns` row, and writes a synthetic `turn_kind='system_event'` ledger entry referencing them, so the chain remains complete and the orphans become attributable. **Current Slice 2.4 implementation is operator-invokable only; no daemon startup/nightly auto-run exists yet.** |
| **C. Ledger row landed, claims missing** | Crash between steps 3–4. `turns` row exists; `claims` rows for it do not. | Current Slice 2.4 implementation is **detect-only**: the job reports `state_c_turns` and exits with CLI code 3 when this is the highest-priority signal. Auto-repair waits for Slice 4 claim extraction. A sandbox run that shows State C is a hard fail for production flip. |

**Hard rule:** the ledger writer must NEVER use a single transaction that spans multiple SQLite databases. Each DB's writes are their own transaction; cross-DB integrity is restored by the reconciliation job, not by attempting a multi-DB atomic write (which SQLite cannot guarantee). This is a deliberate trade: best-effort cross-DB consistency in the steady state, eventual consistency after crashes, with the reconciliation job as the convergence mechanism.

**Reconciliation job invariants** (verified by `tests/test_ledger_reconcile.py` and `tests/test_reconcile_ledger_cli.py`):
- After `--apply`, every post-era orphan in `audit_log`, `fabrication_events`, `pending_cards`, and `self_mod_dialogs` has a corresponding synthetic `turns` row referencing it.
- `was_rewritten=1` turns without claims are detected as State C and reported; they are not repaired in Slice 2.4.
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
10. **Daemon-rewrite-rate signal** — `scripts/validate/track_a_harness.py` reads `claims.audit_verdict` to compute the live rewrite rate that gates adapter training (per [MAEZ_FRONTIER.md §7](../MAEZ_FRONTIER.md) hard rule 5).

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

- [x] [MAEZ_FRONTIER.md](../MAEZ_FRONTIER.md) is committed (cross-link target exists in git) — `aa1cb1a`
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

---

## 13. Amendment — `event_origin` and the v2 canonical era (2026-08-27)

**Recorded, not authored here: the OWNER RULED this column** (2026-08-27,
twentieth council round Q1 fork — see
`docs/superpowers/witness/theme2-s2-owner-delegated-council-rulings.md`).
This section records the ruling and its schema consequences; the
contract details were frozen by the twenty-first round.

**The column.** `turns.event_origin TEXT NULL`, no SQL default
(migration `0007_add_event_origin.sql`). One column, one meaning: which
ORGAN produced this row's bytes, for interceptor speech that answers
the owner before the model runs. `surface` stays the conversation
channel; `raw_surface` stays transport provenance and taint authority —
the taint-caller coupling is removed rather than pinned around.

**Writer contract** (enforced in `core/ledger/writer.py`, pinned by
`tests/test_ledger_event_origin.py`):

- Non-None `event_origin` ⇒ `turn_kind = 'system_event'`; every other
  kind refuses it in the §4.2 forbidden-field shape. The REVERSE is not
  frozen: generic system rows (genesis, reconcile) legally carry NULL.
- Verbatim free-form non-empty string. No enum, no rewrite, no default:
  a curated organ roster goes stale silently, and a default fabricates
  attribution no caller made. NULL is the ONLY spelling of "no organ";
  `''` refuses. The value is a caller ASSERTION — the recorder seam
  binds production constants; the writer verifies shape, not truth.

**The v2 canonical era.** Unlike every column added since ratification
(0003–0006, all excluded from chain-hash canonical bytes),
`event_origin` ENTERS the §6.1 preimage: the key is always present
(`null` included) in canonical row bytes, so "no organ claimed" is
itself a chain-covered claim and post-hoc attribution edits break
verification even for an adversary who drops the append-only triggers.
Per this doc's status line and `GENESIS_ROW`'s own rule, that preimage
edit bumps `schema_version` 1 → 2 (genesis row, embedded genesis JSON,
writer rows, `meta.schema_version`). Ruled and landed while the ledger
held ZERO rows — migration 0007 refuses to apply to a populated
`turns` table, so pre-v2 artifacts (the retained rehearsal sidecars)
keep their own era instead of silently losing their chains.

**Which bytes a row binds to** (twenty-fourth round, 2026-08-28,
ruled 3-0). An organ row's `raw_text` is the bytes the organ PRODUCED —
never "the bytes the owner received". Executed: the surface transforms
a reply after the closure has already recorded it, and egress is not a
byte-string at all — a reply naming an on-disk image has the path
stripped from the text and the FILE uploaded out of band, so what
crossed the wire is a tuple `(text, images, media, local_files)`. A row
bound to delivered text would both omit content the owner did receive
and contain text authored by the surface's regexes. "Exact bytes, never
content-light" therefore means: do not summarise, hash or paraphrase AT
THE SEAM. It was never a claim about the wire. The owner's
`user_message` row answers differently and structurally so — the
owner's `.strip()` is a HEARING transform upstream of the guard, while
the surface's extraction is a SPEAKING transform downstream; both rows
bind at the seam, and the seam sits between them.

**Readers.** `span_reader` exposes the column by contract. The
prompt-feeding `recent_turns_by_kind` is deliberately NOT widened —
prompt-content exposure is the owner's decision, deferred by name
(same class as the owed `submitted_at` selection). A future
conversation-stream reader's contract must carry `event_origin` on
`system_event` rows.

That reader carries THREE obligations, all of them presentation rules
over rows that are already honest:

1. It must never present an UNPARENTED organ row as though Maez
   authored owner text quoted inside it (owner ruling, 2026-08-28 —
   owner-provenance rides the parent edge).
2. It must never present a row as SPOKEN. A row is GENERATED, not
   delivered: the record is written before transport, the surface may
   still discard the reply, and on a timeout the transport itself
   cannot say whether the bytes arrived. Delivery evidence is A4's,
   and A4 is not built.
3. It must not present `raw_text` as "what the owner saw". Per the
   binding above, it is what the organ said; the two diverge whenever
   the reply carries a media-shaped token.
