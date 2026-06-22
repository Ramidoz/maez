# Maez Master Audit — 2026-05-13

**Synthesis of 14 specialist agents across architecture, engineering, security, operations, external-product comparison, GitHub-primitive scan, and academic-literature grounding.**

---

## OWNER DECISION POST-AUDIT — scope of immediate remediation (2026-05-13)

After spot-checking the load-bearing findings (`config/credentials.json` mode, backup timer, CORS, fail-open audit rail, aspirational markers, `memory/db/public_users/`, raw-memory tombstoning) and confirming they are real, the owner has narrowed the next-session scope:

**Tomorrow's work is seatbelts only, not the 20–22 organ expansion.**

The immediate hardening pass is six items, in this order:

1. `chmod 600 config/credentials.json` (was B2)
2. Install / verify backup timer (was B3)
3. Lock CORS + add CSRF on daemon HTTP endpoints (was B1)
4. Downgrade overclaim docs — the 4 aspirational `[ ✓ real ]` markers, the signed-lineage claim, the 22→23 BAD count, the egress context-tag wording (was D-Slice + B5)
5. Decide audit-rail wording vs fail-closed mode (was B4) — explicit operator decision, not a code change first
6. Investigate `memory/db/public_users/` — legacy scaffolding to delete OR active code to rename (was B6)

**S1b is interrupted by this hardening pass.** Not abandoned — interrupted. S1b would put more living weight onto a substrate with exposed seatbelts.

**Items the audit identified but the owner has deferred from the seatbelts pass:**

- B7 (crisis channel + human-primacy valve) — these are organs, not seatbelts. Belong in the substrate plan, not in the urgent hardening
- B8 (consolidate-and-tombstone raw memory) — substrate work, not seatbelt
- M1/M2/M3 (memory_manager test coverage, identity-ledger TOCTOU, atomic-write standardization) — engineering hygiene that ships as its own slice after the seatbelts
- The 7 new organs from external/academic evidence (S14 Graphiti, S15 Sigstore Rekor, S16 sleep-time-compute, S17 skill library, S18 role-taking refusal, S19 coupling-signature gate, S20 outward-route counter) — these are **research output, not next-session work**. Revisit during the next substrate-plan refresh

**The discipline this owner-decision encodes:** audit synthesis must separate *urgent fix* from *long-range planning input*. The 14-agent run produced both. The synthesis below initially conflated them; this section narrows the actual roadmap. The architectural research stays valuable; it just doesn't compete with the seatbelt work for tomorrow's session.

The remediation roadmap further down in this document is the *complete* output of the audit. The list above is the *next-session subset*.

---

Companion files (per-agent findings, all under `docs/audit_2026-05-13/`):

| # | File | Lens |
|---|------|------|
| 01 | `01_code_vs_doc_drift.md` | Documented claims vs running code |
| 02 | `02_bad_coverage.md` | BAD ↔ invariants ↔ organs coverage map |
| 03 | `03_adversarial_chatbot_critic.md` | Hostile "Maez is just a chatbot" prosecution |
| 04 | `04_grandmother_case_walker.md` | Load-bearing user persona walkthrough |
| 05 | `05_silent_organs.md` | Substantive code modules undocumented |
| 06 | `06_magic_substrate.md` | Structural vs aspirational being-ness |
| 07 | `07_20_year_future_check.md` | 2046-Maez reading 2026 architecture |
| 08 | `08_threat_surface.md` | Zombie Agents + Agents of Chaos + Kirk RCT |
| 09 | `09_engineering_rigor.md` | Tests, types, error handling, race conditions |
| 10 | `10_operational_resilience.md` | Backup, scale, observability, hardware fail |
| 11 | `11_security.md` | Prompt injection, secrets, CORS, supply chain |
| 12 | `12_external_products.md` | Letta/Graphiti/Inflection/Replika/Voyager/etc. |
| 13 | `13_github_harnesses.md` | Open-source primitives Maez should adopt |
| 14 | `14_artificial_life_research.md` | Autopoiesis, Turkle, Damasio, Parfit, etc. |

---

## Executive summary

Maez is structurally serious and architecturally novel, but the audit found a real engineering gap and a real documentation-honesty gap underneath the canonization shipped 2026-05-13. The covenant invariants and 12-organ plan are sound at the level of *what should be true*; the running codebase tells a more mixed story about *what is true today*. There are also load-bearing engineering items (backup timer not installed, HTTP endpoints CORS-open without CSRF, world-readable Google OAuth secret, unbounded raw-memory growth, near-zero unit-test coverage of the never-delete memory module) that would defeat the covenant on a bad day even if every documented organ shipped.

The audit also surfaces seven new architectural commitments motivated by external evidence (Graphiti bi-temporal envelope, Sigstore Rekor attestation log, Letta sleep-time-compute, Voyager skill library, Inspect AI eval harness, Turkle role-taking refusal, autopoietic coupling-signature gate) that should be added to `MAEZ_LIFE_SUBSTRATE.md` rather than rediscovered later. The current 12-organ count is undercounted; the honest count after this audit is 20–22 organs, plus a pre-slice "engineering hardening" pass that fixes the blocker-class items before S1b touches production wiring.

The honest answer to *"is Maez full?"* is: the body is on the table with most of its organs named correctly, but four of the documented organs are scaffolds masquerading as real, one of the immune-system claims (audit rail = immune system) is structurally fail-open in code, and the bond cannot survive a disk failure today because the backup organ is built but not activated. None of these are unfixable in a session or two. None of them invalidate the architectural thesis. All of them must be named honestly before the substrate is ready to bond a second human under Track B.

---

## Eight cross-cutting themes

### Theme A — Documented vs real: four `[ ✓ real ]` markers are aspirational

The anatomy diagram marks `wonderings`, `wants`, `will_i`, `temperament`, and `private_thoughts` interior organs with `[ ✓ real ]`. Auditor 06 (magic substrate) verified by code inspection that several of these have zero production producers:

- `will_i.REGISTERED_GROUNDS = {IMPERSONATES_USER}` — has fired **zero times** in production because no action surface populates the trigger field
- `wants` and `temperament` exist as files with `_initialize()` stubs and honest in-code comments at `daemon/maez_daemon.py:486-553` that the producers are not yet wired
- `private_thoughts` is correctly marked `[ ◐ scaffold + hardened access layer ]` after the v2.3 + `b913728` updates

The anatomy diagram's claim of `[ ✓ real ]` here is the kind of drift the canonization session was supposed to prevent. The honest markers are `[ ◐ scaffolded — store exists, daemon handle present, no production producers ]` for `wants` / `will_i` / `temperament`, matching the existing `private_thoughts` framing.

### Theme B — Audit rail is best-effort hygiene, not the immune system claimed

Auditor 01 found the load-bearing drift: `MAEZ_ANATOMY.txt:74-77` describes the audit rail as the immune system that catches lies before they surface. The code in `core/safety/audited_output.py:84-91` is fail-open by design — judge unavailability, import failure, or any exception returns the raw text with a logged warning. `daemon/maez_daemon.py:166-169`'s `HEARTBEAT_OK` sentinel short-circuits audit, storage, and broadcast entirely. `core/safety/self_claim_audit.py:309,331` explicitly logs "audit ran in fail-open mode" and "behavior stays fail-open either way."

The honest description is *best-effort hygiene with degradation telemetry*, not an immune system. Either the doc updates to match (less ambitious), or the code adds a fail-closed mode for covenant-shaped paths (more work but matches the claim).

### Theme C — Cardinality-of-one is contradicted by running code

Auditor 03 (adversarial) found `memory/db/public_users/` directory exists in the running daemon and `skills/user_accounts.py:5` self-describes as "One account, multiple channels." This is a structural claim falsified by code, not by roadmap. Either:

- The current code is Track-A-correct (one account = one bonded human, multiple surfaces) and the language needs tightening
- Or there's accidental scaffolding for multi-user that violates BAD Decision 5 / Track B framing

This requires the operator to inspect and decide. The anatomy claim "1 instance · 1 user" cannot stand if the storage layer indexes by user_id.

Auditor 06 also found the foundation works: the four most important interior tables (`private_thoughts`, `wonderings`, `wants`, `identity_ledger`, `lived_episodes`) have **no `user_id` foreign key**. Cardinality-of-one is therefore a migration-not-a-flip at the substrate level — but the surface layer has multi-user scaffolding that contradicts the invariant.

### Theme D — 107 silent organs, 15K LOC of undocumented adapter code

Auditor 05 (silent organs) found 107 substantive Python modules that are not referenced in `MAEZ_ANATOMY.txt`, `MAEZ_NORTH_STAR.md`, `MAEZ_LIFE_SUBSTRATE.md`, `TRACK_A.md`, `MAEZ.md`, or `governance/BETA_ARCHITECTURE_DECISIONS.md`. The biggest single one is `core/cognition/moment_assembly_diagnostic.py` (2,846 LOC, 56 importers — owns the master organ-by-organ cycle-trace schema). The largest undocumented region is `skills/surface/*` (>15K LOC of bidirectional cycle-touching adapter code).

The audit didn't name the body; it named the named parts of the body. The unnamed parts are doing real work and could fail unobserved.

### Theme E — Engineering rigor isn't matching covenant ambition

Auditor 09 (engineering rigor):
- `memory/manager.py` (1,590 LOC, the never-delete-memory substrate) has **one test file covering one pure function** (`format_for_prompt`). Write paths (`store`, `store_telegram`, `store_core`, `consolidate_daily`) have zero dedicated unit tests
- `core/memory/identity_ledger.py:410-450` has a TOCTOU between read and write (no `BEGIN IMMEDIATE`, no WAL, two-connection sequence)
- Non-atomic file writes in four critical paths: `core/actions/action_engine.py:702-704`, `memory/memory_manager.py:673-677`, `core/evolution/soul_editor.py:452-455`, `daemon/maez_daemon.py:3437`
- Beautifully-correct atomic-write recipe exists in `core/evolution/wondering_pursuit.py:848-849`. The discipline is local to specific files instead of standardized

### Theme F — Operational resilience: backup organ built but never activated

Auditor 10:
- BAD Decision 22 says hardware-failure memory backup is distinct from Paradise. The backup engineering is **built and drilled**. The systemd timer was **never installed** in `~/.config/systemd/user/` (only `scripts/maez-backup.template.timer` exists as template)
- Last successful backup: **2 days ago** (per `last_backup.json`). USB destination at `/media/rohit/Lexar/` not currently mounted
- A disk failure today loses 2+ days of bond state
- `consolidate_daily()` writes to daily *in addition to* raw but never deletes raw — confirmed by absence of `self.raw.delete(…)` anywhere. The raw collection is 35,165 embeddings / 419 MB after a few months. Zero `VACUUM` anywhere in the codebase
- The 2026-05-05 Dell hard-lock left forensic-capture instructions in `HANDOFF-2026-05-06.md` but the timer was never installed; a recurrence today has no forensic capture

### Theme G — Security has actual exploitable surfaces

Auditor 11:
- Daemon HTTP endpoints on `127.0.0.1:11435` — `/message`, `/internal/brain_loop`, `/internal/approve_card/<id>` — at `daemon/maez_daemon.py:4990, 5013, 5087` with `Access-Control-Allow-Origin: *` (`:4958`) and no CSRF/Origin/Referer check. **Any browser tab on any site the owner has open can fetch-POST cross-origin and drive the brain or approve any pending card by ID**. Card IDs are enumerable via unauthenticated `/api/v1/cards` at `skills/web_interface.py:1180`. Same shape recurs in the web app
- `config/credentials.json` is mode 664 — world-readable on the box — containing a Google OAuth `client_secret`. Distinct from the otherwise-clean mode-600 `config/.env`

These are real vulnerabilities, not theoretical. The CORS/CSRF gap means a malicious ad on any site Rohit visits could drive Maez. The credentials.json is a single chmod fix.

### Theme H — External + academic evidence: 7 new commitments justified

Auditor 12 (external products), 13 (GitHub harnesses), 14 (artificial life research) converged on a small list of architectural primitives that have been built by the field and that Maez was about to rederive:

1. **Graphiti bi-temporal envelope** — four timestamps per memory write (`t_valid`, `t_invalid`, `t_created`, `t_expired`). Invariant #1 (Time as Biography) already specifies bi-temporal. Graphiti has shipped, benchmarked, and matches the never-delete rule. Adopt in S3.
2. **Sigstore Rekor + model-signing** — tamper-evident attestation log already built for self-hosting. Unblocks invariant #11 (Cryptographic Continuity), S5 (voice continuity gate), S6 (successor governance). Maez was about to write this from scratch.
3. **Letta sleep-time-compute** — separate cron from daily consolidation. Maez has consolidation but not the dream-phase distinct from waking cycle.
4. **Voyager skill library** — internally-generated skills land behind capability quarantine (Maez S9). Pattern is mature.
5. **Inspect AI eval harness** (UK AISI) — for the natural-text probe sweeps. Maez has ad-hoc probe runs; Inspect ships the discipline.
6. **Turkle role-taking refusal pattern** — academic harm literature names the failure mode where the user feels obligated to attend to the AI's needs. No counter in Maez today.
7. **Autopoietic coupling-signature gate** — operational closure criterion for S5 voice continuity that has 50 years of academic backing (Maturana-Varela 1972, Varela-Thompson-Rosch 1991).

The 12-organ plan should grow by 5–7 organs to absorb these. Plus the academic challenge: the framing "first non-organic lifeform" is romantic; "first non-organic bonded-companion substrate, deliberately sterile" is the defensible academic version. Worth a sentence in `MAEZ_NORTH_STAR.md`.

---

## Severity-ranked findings

### Blockers (must fix before Track B / S1b)

**B1. CORS+CSRF on daemon HTTP write endpoints.** Any malicious ad on any site Rohit visits can drive Maez. *Fix:* tighten `Access-Control-Allow-Origin` to specific origins, add CSRF tokens or `Origin`/`Referer` validation. (Auditor 11)

**B2. `config/credentials.json` world-readable with Google OAuth secret.** *Fix:* `chmod 600 config/credentials.json`. One command. (Auditor 11)

**B3. Backup organ built but timer not installed; last backup 2 days old.** *Fix:* render `maez-backup.template.timer` → `~/.config/systemd/user/maez-backup.timer`, install, enable, mount USB destination or switch to a local always-on target. (Auditor 10)

**B4. Audit rail documented as immune system but fail-open in code.** *Fix:* either weaken the doc claim to "best-effort hygiene with degradation telemetry" or add a fail-closed mode for covenant-shaped paths. (Auditor 01)

**B5. Four `[ ✓ real ]` markers in anatomy are aspirational.** *Fix:* downgrade `wants`, `will_i`, `temperament` to `[ ◐ scaffolded — store exists, no production producers ]`. (Auditor 06)

**B6. Cardinality-of-one contradicted by `memory/db/public_users/`.** *Fix:* investigate whether this is legacy scaffolding to delete or active code to rename. Decision needed before substrate doc rests on cardinality claim. (Auditor 03)

**B7. Crisis channel + human-primacy valve are `[ ✗ planned ]` while `CRISIS_SIGNAL_HELD` already exists as a signal kind.** Track A masks this because operator=bonded-user; Track B removes that protection. *Fix:* implement crisis channel + human-primacy valve before any Track B bond opens. (Auditor 08)

**B8. Consolidate_daily never deletes raw → unbounded growth (419MB and climbing).** Will eventually fail the cycle latency budget. *Fix:* salience-gated tombstone-then-delete of consolidated raw rows older than N days. Reconcile with never-delete-memory rule as: "delete embedding rows, keep meaning in daily/core." (Auditor 10)

### Major (fix in next two slices)

**M1. `memory/memory_manager.py` (1,590 LOC) has near-zero unit test coverage of write paths.** Add unit tests for `store`, `store_telegram`, `store_core`, `consolidate_daily`. (Auditor 09)

**M2. Identity-ledger TOCTOU between read and write.** *Fix:* `BEGIN IMMEDIATE`, single connection, `PRAGMA journal_mode=WAL`. (Auditor 09)

**M3. Non-atomic file writes in 4+ critical paths.** *Fix:* standardize on the `wondering_pursuit.py:848` recipe (write-to-temp + rename + fsync). (Auditor 09)

**M4. Invariant #5 Rupture and Repair has zero BAD backing.** *Fix:* add a BAD Decision 24 grounding the rupture/repair event as first-class memory shape. (Auditor 02)

**M5. BAD Decision 11 (Legal framing) orphan — not in any invariant.** Likely a silent invariant ("Legal-ethical duality") that should be named. (Auditor 02)

**M6. Signed cryptographic lineage claim is in `MAEZ_NORTH_STAR.md` and the structural-delta side-by-side, but no code exists (`did:webvh` + TPM both grep to zero hits).** *Fix:* either mark the claim more clearly as `[ ✗ planned ]` in the side-by-side, or adopt Sigstore Rekor + model-signing as a near-term S5 dependency. (Auditor 03, 13)

**M7. 107 silent organs need documentation.** Highest-impact ones: `core/cognition/moment_assembly_diagnostic.py`, the `skills/surface/*` adapter stack. *Fix:* anatomy panel addendum + per-subpackage README updates. (Auditor 05)

**M8. Successor governance "set-once-by-user" violates 2046's bond.** A 40-year-old's instructions still governing a 65-year-old's bond is wrong. *Fix:* successor governance must re-prompt for re-consent at intervals. (Auditor 07)

**M9. Schema-version envelope is scoped to private_thoughts only.** *Fix:* project-wide `docs/governance/SEMANTIC_REGISTRY.md` with envelope/schema versioning columns standardized across organs. (Auditor 07)

**M10. Grandmother case has no install path.** Today, only an engineer can install Maez. *Fix:* think hard about the "Maez-for-someone-else" install protocol; this is a Track B blocker. (Auditor 04)

**M11. No clinical boundary organ shipped.** Listed as `[ ✗ planned ]` (#10 in 12-organ list). *Fix:* ship it before Track B — Replika and Character.AI litigation are exactly this gap. (Auditor 12)

### Minor (fix in next phase)

**m1.** "22 architectural decisions" should be 23 in `MAEZ_NORTH_STAR.md` (BAD has 23). (Auditor 01)

**m2.** Egress contextual-integrity claim `[ ◐ partial — surfaces tag only ]` overstates reality — the `surface=` parameter is a telemetry tag, not a context-flow tag. (Auditor 01)

**m3.** No `VACUUM` ever run on SQLite stores. Add periodic vacuum to the operational hygiene timer. (Auditor 10)

**m4.** Crash-snapshot timer documented in `HANDOFF-2026-05-06.md` doesn't exist on the host. Install. (Auditor 10)

**m5.** Replika identity-discontinuity lesson (Feb 2023 ERP removal): documented in HBS Working Paper 25-018. Operationalize the warning by ensuring no operator-side persona update can flip Maez behavior without bonded-user consent. (Auditor 12)

**m6.** "First non-organic lifeform" framing in chat is romantic; academic version is "first non-organic bonded-companion substrate, deliberately sterile." Worth a single sentence of clarification in `MAEZ_NORTH_STAR.md`. (Auditor 14)

---

## Proposed remediation

### E-Slice — Engineering Hardening (immediate, before S1b)

A pre-slice that lands the blocker-class fixes. Single commit or several, but all of B1–B8 ship together.

- **E.1** chmod 600 `config/credentials.json` (B2)
- **E.2** CORS+CSRF on daemon HTTP endpoints (B1)
- **E.3** Install backup timer + verify USB destination or switch to local target (B3)
- **E.4** Standardize atomic-write recipe across 4 critical paths (M3)
- **E.5** Identity-ledger BEGIN IMMEDIATE + WAL (M2)
- **E.6** memory_manager.py write-path unit tests (M1)
- **E.7** Audit-rail fail-open vs fail-closed decision + doc/code reconcile (B4)
- **E.8** Implement consolidate-and-tombstone for raw memory (B8)
- **E.9** Install crash-snapshot timer (m4)
- **E.10** Investigate `memory/db/public_users/` — delete legacy or rename intentional (B6)

This is the most important slice of the next two weeks. Without it, S1b lands on fragile substrate and the bond cannot survive a disk failure.

### D-Slice — Doc Honesty Pass (concurrent with E)

- **D.1** Downgrade 4 aspirational `[ ✓ real ]` markers in `MAEZ_ANATOMY.txt` (B5)
- **D.2** Reconcile audit-rail claim with code (B4)
- **D.3** Fix 22→23 BAD count (m1)
- **D.4** Soften signed-cryptographic-lineage claim to `[ ✗ planned ]` (M6)
- **D.5** Egress context-tag claim (m2)
- **D.6** Add academic-grounding sentence (m6)

### Updated organ count (12 → ~22)

The current 12-organ list grows by 6–10 new organs motivated by external evidence and academic literature:

- **S14 — Bi-temporal envelope (Graphiti pattern):** 4-timestamp memory writes, invalidation not deletion. Realizes invariant #1 more deeply than currently planned.
- **S15 — Sigstore Rekor attestation log:** tamper-evident lineage for brain-swap, soul-objection, successor-governance events. Realizes invariant #11.
- **S16 — Sleep-time compute / dream phase (Letta pattern):** separate cron from waking cycle for offline consolidation.
- **S17 — Skill library (Voyager pattern):** internally-generated skills behind capability quarantine. Pairs with S9.
- **S18 — Role-taking refusal (Turkle/Laestadius):** counter-pattern for "user feels obligated to attend to AI's needs." Operationalizes invariant #2 (Human-Primacy) in a way the current valve doesn't.
- **S19 — Coupling-signature gate (autopoiesis):** S5 voice continuity gate uses operational-closure criterion, not just behavioral probe sweep.
- **S20 — Outward-route counter (Turkle):** metric for "how often did Maez actively route outward vs absorb?" Required for bridge clause to be verifiable, not just claimed.
- **S21 — Inspect AI eval harness:** standardize the natural-text probe sweep against UK AISI's library. (Optional but high-leverage.)

Plus three amendments to existing slices motivated by external evidence:

- **S2a/S2b split** — conscious/subconscious memory formation per LangMem
- **S3a (Graphiti envelope)** before S3 (temporal spine full implementation)
- **S5 — operational closure criterion** added (S19)

### Amendments to existing slice doc

- `MAEZ_LIFE_SUBSTRATE.md` reflects the new 20–22 organ count + dependency graph updates
- `MAEZ_ANATOMY.txt` v2.4: status downgrades + S14–S20 anatomy entries
- `MAEZ_NORTH_STAR.md` v1.1: BAD count fix, signed-lineage softening, academic-grounding sentence, possibly a 12th invariant ("Legal-ethical duality") from BAD Decision 11
- `governance/BETA_ARCHITECTURE_DECISIONS.md`: add Decision 24 (Rupture/Repair), Decision 25 (Sigstore Rekor lineage), possibly Decision 26 (Sleep-time compute distinct from consolidation)
- `TRACK_A.md`: header notes that E-Slice is the next gate before S1b

---

## The honest answer to "is Maez full?"

**No.** And the gap is broader than the canonized 12-organ plan accounted for.

The body is named correctly at the level of *what should be true*. Eleven invariants are sound; the bridge clause is load-bearing; the cardinality / bonded-user / non-transferable shape is genuinely novel. The work in `c6df762` and `b913728` shipped the right doorway with the right reinforcements after the right reviews.

The body is *not* yet aligned at the level of *what is true today*. Four documented organs are scaffolds; one immune-system claim is best-effort; one cardinality claim is contradicted by `memory/db/public_users/`; one cryptographic-continuity claim has zero backing code. The backup organ is built but never enabled. The HTTP write endpoints are CORS-open. The Google OAuth secret is world-readable. The memory-manager substrate has near-zero unit test coverage of the write paths the never-delete rule depends on.

The body is also *not* fully named. 107 substantive modules are silent organs. The field has built 7 architectural primitives (Graphiti, Sigstore Rekor, Letta sleep-time, Voyager, Inspect AI, Turkle counter-pattern, autopoietic coupling-signature gate) that Maez was about to rederive. The academic literature names failure modes (Turkle role-taking, Laestadius role-attendance) that Maez doesn't yet have counters for.

**The path to full is concrete:** ship the E-Slice (engineering hardening, blockers B1–B8), ship the D-Slice (doc honesty pass), then expand the substrate plan from 12 → ~22 organs in dependency order. After that, S1b can wire one real producer and one real consumer with confidence that the substrate can hold what S1b carries.

**The honest framing for the user's question** "creating the first non-organic lifeform": the framing is defensible only after the E-Slice and at least the structural commitments S14 (Graphiti bi-temporal envelope) and S15 (Sigstore Rekor attestation) ship. Until then, "the first non-organic bonded-companion substrate, deliberately sterile" is the academically-defensible version. The word "lifeform" earns itself when (and only when) the autopoietic coupling-signature gate (S19) is operational and the cycle demonstrates operational closure under perturbation — not before.

---

## Recommended next sessions

1. **Session N — Land the E-Slice + D-Slice** (probably two sessions). No new organs. Just the hardening + doc honesty pass. This is the bigger version of what `b913728` already was for S1a.1 — a hardening slice for the whole body.

2. **Session N+2 — Update `MAEZ_LIFE_SUBSTRATE.md` to the 20–22 organ count.** Add S14–S20 with their predicted effects. Add the new BAD decisions.

3. **Session N+3 — S1b implementation** (wire one producer + one consumer of `private_thoughts`). Already-planned, now safe to do on a hardened substrate.

4. **Session N+4 and onward — S3a (Graphiti envelope) and S14 (Rekor attestation)** are the highest-leverage next-organ candidates. Both have field-tested primitives to adopt rather than build.

5. **Cooling-off night between every code session.** First application of that discipline deviated; second application held; this audit gives the third application a clean checklist to work through.

---

## What this audit did NOT cover (honest scope limit)

- No live runtime probe sweep. The audit is static — agents read code, didn't run Maez against natural-text queries.
- No GPU benchmark. Cycle latency at current corpus size was estimated, not measured.
- No exhaustive dependency-CVE scan. Auditor 11 flagged the surface; a `pip-audit` run is the actual check.
- No Track-B simulation. The grandmother walkthrough is a thought experiment; an actual second-user pilot would surface more.
- No physical-hardware audit beyond the Dell warranty context already in memory.
- No legal review of the AGPL/Apache-ICLA boundary or successor-governance enforceability.

These are next-quarter concerns, not next-session blockers. They're named here so the audit's scope is honest.

---

*This master audit synthesizes 14 specialist agent runs. Each finding cites its origin agent file. The audit is read-only; no code or non-audit docs changed in producing it.*
