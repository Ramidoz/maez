# Ledger / Evidence Envelope / Provenance — Joint Schema

**Slice 1 of Project A completion. Paper artifact. No implementation in this doc.**

**Status:** Draft for review (NOT ratified)
**Author:** Claude (drafted 2026-05-06, revised same day after audit pushback)
**Reviewers needed:** Rohit, plus one external (Codex or Hermes)
**Companion docs:** [MAEZ_FRONTIER.md](MAEZ_FRONTIER.md) §6 (dependency graph), §9.1 (build order) — *note: that doc is currently untracked; schema doc should not be committed before frontier doc is committed, otherwise the cross-link breaks*

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
- `user_message` — incoming from owner or peer Maez
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
    surface          TEXT NOT NULL,           -- 'telegram' | 'cockpit' | 'web_chat' | 'daemon_cycle' | 'self_mod_dialog' | 'voice' | 'inter_maez' | 'system'
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
    audit_log_id          INTEGER,            -- → audit_log.db audit_events.id
    fabrication_event_id  INTEGER,            -- → fabrication_log.db fabrication_events.id (nullable)
    self_mod_dialog_id    INTEGER,            -- → self_mod_dialogs.db dialogs.id (nullable)
    pending_card_id       INTEGER,            -- → pending_cards.db cards.id (nullable)

    -- Tamper-evidence
    prev_chain_hash  TEXT,                    -- hash of previous row's chain_hash, NULL only for genesis
    chain_hash       TEXT NOT NULL            -- sha256(prev_chain_hash || canonical_row_bytes)
);

CREATE INDEX idx_turns_tenant_ts ON turns (tenant_id, timestamp DESC);
CREATE INDEX idx_turns_surface_ts ON turns (tenant_id, surface, timestamp DESC);
CREATE INDEX idx_turns_kind_ts ON turns (tenant_id, turn_kind, timestamp DESC);
CREATE INDEX idx_turns_parent ON turns (parent_turn_id) WHERE parent_turn_id IS NOT NULL;
CREATE INDEX idx_turns_model ON turns (model_id, timestamp DESC) WHERE model_id IS NOT NULL;
```

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
| `peer_message_in` | raw_text, parent_turn_id (the peer's signed envelope) | — |
| `peer_message_out` | raw_text, evidence_envelope_json, audit_verdict_json | — |
| `system_event` | raw_text | model_id, prompt_hash |

### 4.3 `claims` table — denormalized provenance for query

Every claim made in `rewritten_text` (or `raw_text` if not rewritten) gets one row here. This lets the cockpit answer "show me every claim Maez made today by provenance class."

```sql
CREATE TABLE claims (
    claim_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    turn_id          TEXT NOT NULL,
    tenant_id        TEXT NOT NULL DEFAULT 'owner',
    fact             TEXT NOT NULL,            -- the claim text (extracted)
    provenance       TEXT NOT NULL,            -- one of the 6 enum values
    evidence_refs_json TEXT NOT NULL,          -- per-class evidence (see §2)
    confidence       REAL NOT NULL,            -- 0..1
    audit_verdict    TEXT NOT NULL,            -- 'approved' | 'rewritten' | 'flagged'

    FOREIGN KEY (turn_id) REFERENCES turns(turn_id)
);

CREATE INDEX idx_claims_tenant_provenance ON claims (tenant_id, provenance, claim_id DESC);
CREATE INDEX idx_claims_turn ON claims (turn_id);
```

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
| `turns.audit_log_id` | `audit_log.db::audit_events.id` | NOT NULL when audit ran (model_reply, daemon_cycle, etc.) | `tests/test_ledger_audit_link.py` + reconciliation |
| `turns.fabrication_event_id` | `fabrication_log.db::fabrication_events.id` | NULL except when fabrication detected | `tests/test_ledger_fabrication_link.py` + reconciliation |
| `turns.self_mod_dialog_id` | `self_mod_dialogs.db::dialogs.id` | NULL except for self-mod turns | `tests/test_ledger_selfmod_link.py` + reconciliation |
| `turns.pending_card_id` | `pending_cards.db::cards.id` | NULL except for card-bearing turns | `tests/test_ledger_card_link.py` + reconciliation |
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

Each row's `chain_hash` is `sha256(prev_chain_hash || canonical_row_bytes)`.

- `canonical_row_bytes` = JSON-serialized row with keys sorted, omitting `chain_hash` and `prev_chain_hash` themselves
- Genesis row: `prev_chain_hash` is NULL, `chain_hash = sha256("genesis" || canonical_row_bytes)`, also written to `meta.genesis_hash`
- Verification: `scripts/verify_ledger_chain.py` walks the chain end-to-end. Run nightly via the orchestrator that produces reflections.

**What this protects against:** silent edits to ledger rows. If anyone (including Maez) modifies a row, the chain breaks at that row and the verifier flags it.

**What this does NOT protect against:** wholesale deletion or substitution of the entire `ledger.db` file. That's a backup/restore problem, not a chain problem. Mitigation: nightly snapshot to a separate path, retained 30 days.

### 6.2 Crash semantics

The ledger writer touches multiple SQLite databases in §5's order. A crash anywhere in that sequence can leave the system in one of three states:

| State | What happened | Resolution |
|---|---|---|
| **A. No writes landed** | Crash before step 1 (audit_log write). | Nothing to reconcile. Next turn proceeds normally. |
| **B. Dependent rows landed, ledger row missing** | Crash between steps 1–3. Audit log has a row, ledger does not. | Reconciliation job (`scripts/reconcile_ledger.py`) runs at startup AND nightly. Detects orphan dependent rows (audit_events, fabrication_events, etc.) with no corresponding `turns` row, and writes a synthetic `turn_kind='system_event'` ledger entry referencing them, so the chain remains complete and the orphans become attributable. |
| **C. Ledger row landed, claims missing** | Crash between steps 3–4. `turns` row exists; `claims` rows for it do not. | Same reconciliation job re-runs claim extraction (Slice 4 logic) over the orphan turn's `rewritten_text` and writes the `claims` rows. The chain is unaffected because `claims` are not part of the chain. |

**Hard rule:** the ledger writer must NEVER use a single transaction that spans multiple SQLite databases. Each DB's writes are their own transaction; cross-DB integrity is restored by the reconciliation job, not by attempting a multi-DB atomic write (which SQLite cannot guarantee). This is a deliberate trade: best-effort cross-DB consistency in the steady state, eventual consistency after crashes, with the reconciliation job as the convergence mechanism.

**Reconciliation job invariants** (verified by `tests/test_reconciliation.py`):
- After running, every audit_events row has a corresponding `turns` row referencing it (for kinds where audit ran).
- After running, every `turns` row with `was_rewritten=1` has at least one `claims` row.
- The chain remains valid: synthetic reconciliation rows are appended at the chain head, never inserted mid-chain.

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

**v1 policy (proposed for ratification):**

1. **Two-pass extraction, both pre-existing in the audit pipeline.**
   - **Pass A — heuristic.** A deterministic extractor walks the rewritten reply text and pulls out claim-shaped sentences using surface patterns: assertive declaratives, "the X is/was/will Y", numeric assertions, named-entity references, temporal claims, and self-references about Maez's own state. Output: a list of candidate claim strings with surface-feature tags.
   - **Pass B — LLM-judged.** The audit Pass 2 judge (already running per turn) is extended with a structured-output instruction that returns, alongside its existing verdict, a list of `{claim, provenance, evidence_refs, confidence}` for every candidate that survived Pass A. The judge sees the evidence envelope (§3) and grades each candidate against it.

2. **Both passes write `claims` rows.** Pass A's candidates are inserted with `audit_verdict='extracted_unjudged'` *before* Pass B runs, so a crash mid-judgement does not lose the claim list. Pass B then UPDATEs (this is the *only* permitted UPDATE in the entire ledger; enforced by trigger exception list) the `provenance`, `evidence_refs_json`, `confidence`, and `audit_verdict` columns.

3. **Claims with `provenance=NULL` after both passes** (judge couldn't classify) are still written. They are flagged for the daemon-rewrite-rate metric — unclassifiable claims count toward the rewrite signal whether or not the text was rewritten.

4. **Claims extraction does NOT block reply delivery.** If Pass B times out or errors, the reply still reaches the user (existing audit pipeline behavior). The `claims` row stays at `extracted_unjudged`. Reconciliation job (§6.2) re-runs Pass B on backlog at the next quiet cycle.

5. **No third-party LLM in the extractor.** Pass B uses Maez's own judge (currently retired Qwen3.5-4B; otherwise the brain itself if judge is offline). Sending claim extraction to OpenRouter or Claude or Gemini would leak production text and would teach Maez to sound like the extractor's voice, not its own.

**Why two passes and not one:**
- Pure heuristic misses semantic claims (Maez says "I noticed you've been quiet" — that's a claim about the user's state, but the surface form is innocuous).
- Pure LLM is non-deterministic and expensive per turn. The heuristic shortlist makes the LLM's job bounded and the audit cost predictable.
- The separation also gives reconciliation a clean handoff: heuristic always runs synchronously; LLM judgement can be deferred or re-run.

**v1 acceptance:** Slice 4 ships when 100 sampled turns show:
- ≥95% of human-rated claims appear in the `claims` table.
- ≥80% of `claims` rows have a non-NULL `provenance` after both passes.
- The remaining ≤20% with `provenance=NULL` are reviewed by Rohit weekly and used to grow the heuristic and refine the judge prompt.

**Open question deferred to Slice 4 ratification:** the exact heuristic patterns. v1 schema commits to the *two-pass shape*, not specific regex. Heuristic implementation is not a schema concern.

---

## 11. Other open questions (lower stakes than §10)

1. **Hash algorithm: sha256 vs. blake3?** sha256 is universally available and audit-friendly. blake3 is faster. Default to sha256 unless a perf reason emerges.
2. **Retention policy for `turns`?** The frontier is "lifelong memory" so the default is *forever*. But disk space is finite. Proposal: hot rows in `ledger.db`, cold rows (>2 years) archived to `ledger_archive_<year>.db`. Defer to Project A.5.
3. **Should `evidence_envelope_json` and `audit_verdict_json` be normalized into separate tables for query efficiency?** Likely yes for the envelope (cockpit will repeatedly query "what did Maez know at turn T"); defer for the verdict. Track in Slice 5.
4. **`tenant_id` mid-tenant rename?** If a tenant ID is ever changed (e.g., `'owner'` → `'rohit'` for clarity), what happens to old rows? Proposal: forbid in v1. Add a `tenant_aliases` table in v2 if needed.
5. **`turn_kind` extension?** Adding a new kind requires updating the per-kind NOT-NULL contract. Proposal: schema_version bump on any new kind. Not free, deliberately.

---

## 12. Sign-off checklist

This schema is ready for Slice 2 implementation when:

- [ ] [MAEZ_FRONTIER.md](MAEZ_FRONTIER.md) is committed (cross-link target exists in git)
- [ ] Rohit has read this doc and ratified the provenance enum values (§2)
- [ ] Rohit has ratified the `turn_kind` enum values and per-kind NOT-NULL contract (§4.2)
- [ ] Rohit has confirmed the surface enum values cover all current and near-term surfaces (§4.2 `surface` column)
- [ ] **The v1 claims-extraction policy (§10) has been ratified or rewritten** — this is the load-bearing decision, not a deferrable open question
- [ ] At least one external agent (Codex or Hermes) has reviewed and signed off
- [ ] The cross-DB FK contract (§5) has been verified against the current schema of `audit_log.db`, `fabrication_log.db`, `pending_cards.db`, `self_mod_dialogs.db`
- [ ] The crash semantics (§6.2) reconciliation job has been scoped (the doc says "synthesize a `system_event`"; implementation must define the synthesis exactly)
- [ ] The lower-stakes open questions in §11 have explicit decisions or deferrals

---

*This is paper. No code lands until §12 is checked off. Particular attention to §10 — the claims-extraction policy is where the ledger earns its honesty.*
