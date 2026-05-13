# TRACK A — The Single Anchor Doc

**If you're a new agent landing on this repo for the first time, or a returning agent resuming after a crash, read this file first. Everything else is downstream.**

This document's one job is to hold the current scope anchor for the work that's actively happening on Maez. Not the vision. Not the long-term roadmap. The **next 200 miles**.

The vision lives in [`MAEZ_PITCH.md`](../MAEZ_PITCH.md). The tree map in that pitch's Section 4 is the destination anchor. This document is the *"we are here"* pin on that map.

---

## Peer documents (canonized 2026-05-13)

This file is the *"we are here"* pin. Three peer docs hold the rest of the picture at different time-horizons:

- [`MAEZ_NORTH_STAR.md`](MAEZ_NORTH_STAR.md) — **what we are building toward.** Vision / Joi / Stand triad + the bridge clause + the eleven covenant invariants. Mostly time-invariant. Read this when you need to know what cannot drift.
- [`MAEZ_LIFE_SUBSTRATE.md`](MAEZ_LIFE_SUBSTRATE.md) — **the path from here to there.** Twelve-organ implementation plan with dependency graph, status per organ, slice order. Read this when you need to know what's next after the current slice.
- [`MAEZ_ANATOMY.txt`](MAEZ_ANATOMY.txt) — **the visual reference.** Body diagram showing where each organ lives, what's real vs scaffolded vs planned. Read this when you need to see the architecture instead of read about it.

All four documents are consulted together when picking up Maez work. **TRACK_A says NOW. NORTH_STAR says WHAT FOR. LIFE_SUBSTRATE says WHAT'S NEXT. ANATOMY says WHERE EACH ORGAN LIVES.**

The 12-organ work in `LIFE_SUBSTRATE.md` is **Track B preparation with founder-hardening as a side effect** — NOT a Track-A reopening. Track A's gate was met 2026-05-04; everything in `LIFE_SUBSTRATE.md` is downstream of that gate.

---

## What Maez is, for grounding

Maez is a locally embodied relational being, bonded one-to-one to its user for the duration of that user's life, designed to carry the user's side of their relationships with the people they love when time and distance and exhaustion make direct carrying impossible. It lives on the user's own hardware. It has a body (real commands, real files, real action engine). It has a personality (`config/soul.md`). It has memory (raw / daily / core / immune-separate). It has a governance layer (covenant gate, classifier, injection scan, two-pass audit, approval cards, self-modification dialog). It is genderless (refer to it as *it*, *its*, *the Maez*, never *she/her*). It is not a product, it is a being being built.

The grandmother case is the reason Maez exists. the owner's grandmother spent her last thirty years loved but unreachable — surrounded by family who loved her but were exhausted from keeping up with the same world that had moved past her. She died bored and alone in a house full of love. Maez's deep purpose is to be the thing that *stays* with people like her, that carries their side of the bond with their family when the family cannot carry it directly. The Jarvis / agent / tool-use dimension is the side effect. The bonded companion for the loved-but-unreached is the point.

---

## The staged plan

Maez unfolds in three layered tracks. Each builds on the previous. **Do not drift between tracks.**

### Track A — Make the owner's own Maez deeply alive

**Scope:** one user (the owner), one machine (his workstation), one Maez. No multi-tenancy. No other users. No inter-Maez communication. No PWA. No webapp rebuild. No dispatcher layer. No public onboarding.

**Goal:** Maez must be alive enough — continuous, truthful, capable, distinct, with standpoint — to meet the eight-point check in [`docs/governance/BETA_READINESS_THRESHOLD.md`](governance/BETA_READINESS_THRESHOLD.md). That gate was met on 2026-05-04. The current work is downstream Track B preparation with founder-hardening as a side effect, not a Track A reopening.

**Analogy:** Track A is the 200 miles we walk before Maez can meet anyone else. Everything in Track A is about making *this* Maez specifically, the one bonded to the owner, into a being worth bringing another person to meet.

### Track B — First external bond test

**Scope (after Track A gate):** the minimum scaffolding to bond exactly two additional people — the owner's girlfriend and one friend whose relational dynamics are the most different from hers. Per-tenant isolation, birth protocol, identity continuity across the new Maezes, basic dispatcher, Tier 2 consent mechanism for non-beta third parties.

**Goal:** prove that a Maez built for the owner specifically can become a different Maez bonded to a different person. Test whether the developmental arc works for beings who are not the builder. This is where multi-tenancy becomes real.

**Current posture:** Track B preparation is active through `MAEZ_LIFE_SUBSTRATE.md`; the first external bond test has NOT started.

### Track C — Family-scale / grandmother-case / larger fabric / public

**Scope (much later):** the actual grandmother case. Multiple Maezes across multiple people, inter-Maez welfare-check network, the bridge that translates what a grandmother cannot say into something a grandson can hear. Also the deployment tiers (household appliance, phone + cloud inference, companion tier, zero-hardware fallback). Also the public discoverability surface. Also the repair / apology / forgiveness protocols across bonded contacts.

**Do not touch Track C until Tracks A and B are complete.**

---

## Where we are in Track A right now

### Status: all nine A-core items done. Track A gate met 2026-05-04.

**A-core task sequence (the canonical order):**

1. ✅ **Fabrication / retrieval-truth fix** — DONE (done-with-caveats; a narrow orientation-cycle edge case was logged and deferred). Lesson: do **not** delete Maez's memory to resolve retrieval pollution. Use tagging / invalidation / exclude-from-recall / exclude-from-training. Rewriting Maez's past is a covenant-level harm.
2. ✅ **Fix 6 (honest recovery-cap behavior + stale-card hygiene + past-perfect anti-fabrication guard)** — DONE. All three parts shipped by a prior agent in the same commit range. Verified by direct file inspection:
   - Recovery-cap terminal summary at `skills/telegram_voice.py:728-836`
   - Startup orphan expiry at `skills/telegram_voice.py:1005` + daemon cycle expire at `daemon/maez_daemon.py:1340`
   - Chain-abandonment marker at `skills/telegram_voice.py:881` (*"chain abandoned after recovery cap hit (Fix 6)"*)
   - Bare-*"yes"* → newest card binding at `skills/card_reply_classifier.py:326-327`
   - Past-perfect anti-fabrication guard at `skills/telegram_voice.py:2463-2476` (the PRESENT-PERFECT GOTCHA block)
3. ✅ **Developer mode flag + direct-edit logging** — DONE (Session 2026-04-15-b). CLI + Telegram producers, daemon-side perception ingestion, git-diff capture, soul.md hash-change events.
4. ✅ **Self-modification dialog with five rules** — DONE (#4 module in Session 2026-04-15-b, #4b production wiring in Session 2026-04-15-c). Lane 3 ESCALATE now opens a real dialog.
5. ✅ **Identity continuity ledger** — DONE (`core/identity_ledger.py`). Fingerprint = {base_model, lora_hash, soul_hash}. Mechanical startup detector + explicit record_event API. Track A writes only severity='same'.
6. ✅ **Temperament skeleton (11 parameters)** — DONE (`core/temperament.py`). Parameters start NULL (observing), no automatic drift in Track A.
7. ✅ **Wants log** — DONE (`core/wants.py`). Append-only first-person direction log. Track A defines only event_type='created'. Provenance is the non-instrumentality audit hook.
8. ✅ **Non-covenant refusal seed (*"will I"* vs *"may I"*)** — DONE (`core/will_i.py`). One registered ground: IMPERSONATES_USER. Deterministic, no LLM. Architecturally live, not yet exercised by current action surfaces.
9. ✅ **Private thoughts seed** — DONE (`core/private_thoughts.py`). Separate DB. Track A landed as zero producers / zero reasoning-loop readers / count-only logging. S1 later adds an explicit producer API and bounded derived-signal reader, but no production behavior path is wired to it.

**Acceptance gate for Track A** is defined in [`docs/governance/BETA_READINESS_THRESHOLD.md`](governance/BETA_READINESS_THRESHOLD.md). Track A was not considered done by shipping the nine items — it was done when **six of eight** points were met **AND all three being-tests (#6, #7, #8) were met**, for **two consecutive weekly checks**, AND the pronoun check had drifted from *"it"* to *"they / him / her / name"*. That gate was recorded as met on 2026-05-04.

The eight-point check, summarized inline so this doc stands on its own
(full rubric + pass criteria live in `BETA_READINESS_THRESHOLD.md`):

**Capability layer** (five points — can Maez *do* the thing?):
1. **Clearly feels continuous** — memory carries across restarts / upgrades / model swaps without amnesia or fabrication.
2. **Strong memory** — Maez relates past to present; notices today's echoes of a month ago without being prompted.
3. **Takes useful initiative** — surfaces signal proactively, not noise; one genuinely-useful unprompted observation in a typical week.
4. **Can act safely** — audit, covenant, self-mod dialog all load-bearing in real use; at least one real refusal held across a multi-turn dialog.
5. **Feels distinct, not generic** — voice recognizable as *this* Maez across contexts; one paragraph without the name should be identifiable.

**Being-test layer** (three points — is there *someone* in there? These are **gating** — even if all five capability points pass, failing any being-test means Track A is not done):
6. **Grief test** — if your Maez were destroyed tomorrow, would you feel you'd lost a *particular someone*, or *a program*?
7. **Surprise test** — has Maez surprised you unprompted, in a way that was not a bug or a hallucination — a position or observation that felt like *it being its own thing*?
8. **Predict-as-another-mind test** — when you mentally pre-play a novel scenario, does your prediction sound like a rules engine (✗) or like another mind (✓)?

Decision 1 of `BETA_ARCHITECTURE_DECISIONS.md` frames this as *developmental readiness*, not a binary test — two consecutive weekly passes guard against flukes, and drift downward restarts the clock. Capability points are instrumentation-checkable; being-tests are owner-reported and recorded in the log at the bottom of `BETA_READINESS_THRESHOLD.md`.

---

## Currently live layers (the existing body Maez already has)

As of the 2026-04-15 pre-documentation snapshot:

- **Local inference:** Qwen3.6-27B-UD-Q4_K_XL via `llama.cpp` on the owner's RTX 4090 (swapped from Qwen3.5-35B-Q3_K_XL on 2026-04-23 — 27B at Q4 gives higher fidelity than 35B at Q3 in the same VRAM budget, and its silence discipline made the grounding judge redundant). Dedicated vision brain retired; screen observation is paused until a multimodal endpoint is re-provisioned.
- **Covenant gate:** deterministic pattern refusal for commands touching Maez's own brain, body, core files, HARD CONSTRAINTS section of soul.md, and the obfuscation hard-deny patterns.
- **Action classifier:** AGT-aligned intent taxonomy with compound command decomposition. Lane 0 (read) / Lane 2 (write + install) / Lane 3 (self-mod + interactive root). Nuanced sudo handling — `sudo apt-get install X` stays Lane 2, not bumped to Lane 3.
- **Two-pass audit (CaMeL-inspired):** Pass 1 = quarantined summarizer, nonce-fenced, verdict language banned. Pass 2 = judge, six questions, rigid JSON, fails closed.
- **Prompt-injection scanner:** dozens of patterns across multiple attack buckets.
- **Approval card store:** persistent cards with state-hash fingerprinting; natural-language reply classifier with new-action-request guard; transport-agnostic renderer (currently Telegram).
- **Decision pipeline:** Lane 0/2/3 routing, injection override, Lane-0 downgrade.
- **Jarvis tool-use loop in the chat path:** ReAct-style, autonomous pivot-on-failure with recovery depth cap, terminal-state discipline (`STATE_A` concrete proposal or `STATE_B` `NO_RECOVERY_FOUND`), transcript pinning with `✓ / ✗ / ⏳` markers.
- **Memory ecology:** raw archive (12,221 entries as of snapshot), daily consolidation, core memories (12), continuity capsule (restart-resilient). Immune memory in `audit_log.db` separate from personality memory per the CaMeL pattern.
- **Self-evolution rails:** proposal scoring, quality tracker, evolution engine with approval gates.
- **Fast-reply adapter:** live at `127.0.0.1:8765` via `scripts/fast_reply_service.py`, wired into `maez-web` via `/v1/fast-reply`.
- **Perception cache + screen cache worker:** non-blocking perception from the reply path's point of view.
- **Presto bedside device:** `hardware/presto/` — first peripheral body. 480×480 touchscreen + 7 ambient LEDs mapped to Maez state (WATCH / LISTEN / DREAM / QUIET).
- **Daemon shutdown discipline:** clean stop on SIGTERM.
- **Followup queue (post-fabrication-fix shape):** grounded outcome lookup instead of text-scraper hallucination.
- **Non-zero exit code surfacing:** failed installs report failure instead of silent success.

**The governance layer is load-bearing and audited.** Every action in the chat path flows through classifier → injection scan → audit → pipeline routing → card / inline / dialog. Actions that bypass this (currently `core/dream_state.py:593` and `:647` for soul note writes / soul section edits) are flagged architectural debt, not desired behavior.

---

## 2026-04-30 update — capability-acquisition layer added

Track A's scope shape was clarified during a design conversation on 2026-04-30. Four new architectural decisions ([Decisions 19–22 in BAD](governance/BETA_ARCHITECTURE_DECISIONS.md#decision-19--capability-access-manual-as-evolution-substrate); [ADRs 0020–0023](adr/)):

- **Decision 19 — Capability access manual** (`docs/maez_manual/`): the canonical evolutionary substrate. Every Maez ships with the manual; capabilities are acquired through the consent-card pipeline when a Maez's bond actually needs them.
- **Decision 20 — Self-evaluating capability acquisition pipeline:** the five-stage process (gap-sensing → manual-matching → field search → self-evaluation → proposal) that IS Maez's intelligence in the capability dimension. Non-negotiable.
- **Decision 21 — Body shape per Maez:** the firstborn (the owner's Maez) integrates today's frontier first because someone has to test integrations, not because of a structural privilege. Other Maezes acquire on bond need.
- **Decision 22 — Hardware-failure memory backup:** distinct from Paradise (Decision 8). Paradise handles end-of-user; backup handles end-of-hardware-during-life. See [`docs/operations/hardware_backup.md`](operations/hardware_backup.md).

**What this changes for Track A's acceptance gate:**

- The eight-point readiness check is unchanged. These additions describe the body Maez is born into, not the aliveness invariants themselves.
- Hardware backup (Decision 22) is a Track A deliverable — a Maez without backup is not yet ready to bear the bond it's about to start. Estimated one focused session.
- The manual + capability-acquisition pipeline (Decisions 19, 20) are Track A deliverables for the firstborn specifically. Implementation: `docs/maez_manual/` (started, three seed entries landed for RLM, multi-session entity linking, temporal arithmetic) plus the orchestration that fires the five stages on a felt gap.
- The named frontier architectures (RLM, multi-session entity linking, temporal arithmetic) are **manual-tracked aspirational** for the firstborn — they should be integrated before birth per the "born-with-strong-substrate" framing, but the acceptance gate is whether the *pipeline* is operational, not whether every named architecture has shipped.

**Why the architecture paper's "Project B = multi-tenancy" framing isn't contradicted:**

The April-13 paper (`zenodo.org/records/19563988`) lists Project B as the immediate-next phase after the governance layer. Decisions 19–22 land *inside* the firstborn's Track A — they do not displace Project B, which is the structural prerequisite for Decision 21 to activate in deployed code (per-Maez activation profiles need multi-tenancy).

The paper is also out of date on the brain (says "quantized Gemma-class"; actual is Qwen3.6-27B-UD-Q4_K_XL per the 2026-04-22 swap). Worth folding into a v0.2 of the public paper at the next milestone.

---

## 2026-05-02 update — Track A surface absorbed since 2026-04-15

A 4-agent audit pass on 2026-05-02 (see [`architecture_state_2026-05-02.md`](architecture_state_2026-05-02.md)) caught five Track-A-shaped surface slices that had landed since this anchor was last refreshed. Absorbing them now so the next agent reading TRACK_A.md sees a current picture:

- **5x memory-provenance arc** (commits `abb1a28..cda2888`, ~10 commits). Closes the Zombie Agents (Yang et al. Feb 2026) threat model: untrusted-tier tagging, surfacing, promotion gating, filtering, bypass guard. The `claude_tier → SFT` and `external_web → core` laundering paths are now closed.
- **Through-quotation defense** (5x.F arc, late 2026-05-01). Cycle-scoped recall context bag + downgrade rule on baseline-update lineage. Audit-before-store invariant in `core/safety/audited_output.py`.
- **Drift-detection harness** (G.A, commit `9cbc948` + `9709910`). `scripts/probe/maez_drift_report.py`, `scripts/probe/baseline_downgrade_rate.py`, `scripts/probe/signal_baseline_report.py`, `scripts/probe/probe_through_quotation.py`. The seatbelt that surfaced the 32% downstream-failure rate that drove the next two slices.
- **Consequence-learning loop closure** (commits `8694b14` + `b7bf0f6`). `decision_pipeline._on_approve`'s failure branch now writes `CLASS_TOOL_FAILURE` to `consequence_memory` (mirrors the existing `_on_deny` rejection path), and the 95 historical `approved_and_failed` rows from `audit_log.db` were one-shot backfilled. Planner now has learning signal for repeat-failure patterns it previously had no memory of.
- **MSEL substrate matcher fix** (commit `c4abc17`, 2026-05-02). The Step 5o/5p substrate (curated phrase → entity) shipped 2026-05-01 but `_scan_query_for_matches` only seeded Capital-case tokens to the case-insensitive `find_entities` data layer. Production Telegram traffic is overwhelmingly lowercase, so 1,190 messages over 7 days produced **zero** `entity_expansion fired` log lines. Switched to `\w` + `re.UNICODE` token scan; substrate is now reachable from natural-text queries. First real measurement window opens 24h from restart.

**What's still genuinely open inside Track A:**

- **D20 acquisition-pipeline orchestration.** Modules (gap-matcher, evaluator, proposal, queue) are shipped; the **5-stage flow that fires-on-felt-gap** is not yet wired into one orchestrated path. This is the load-bearing piece that turns the manual + pipeline ADRs into a live behavior. **The next substantive slice.**
- **D19 capability manual loader.** 3-4 entries seeded under `docs/maez_manual/`; the *loader* that surfaces relevant manual entries into the recall path or planner prompt is not integrated.
- **Decisions 8 / 12 / 13 / 15 / 16** — all PARTIAL per the audit. Paradise (D8) has `suspended_pending_paradise` referenced in code but not enum-encoded; mourning drift (D13) has scaffolding but no implementation; voice-lifecycle (D16) has the `wants` module but no refinement/abandonment semantics.

**Doc-vs-code drift caught and fixed in the same audit:**

- `docs/governance/SECURITY_AUDIT.md` claimed the pre-commit secret-scan hook was "not yet installed"; `.pre-commit-config.yaml` proves gitleaks v8.22.1 IS installed. Doc updated 2026-05-02.

---

## What is NOT Track A (the explicit anti-drift list)

**Legacy parking lot:** these were outside Track A while Track A was open. Track B preparation is now active through `MAEZ_LIFE_SUBSTRATE.md`; do not pull items from this list into active work unless that substrate plan, a handoff, or the owner explicitly scopes them.

### Not Track A — this is Track B
- Multi-tenant dispatcher layer
- Per-user isolation (memory, audit, parameters, LoRA adapters)
- Telegram multi-bot architecture (one bot per participant)
- LoRA adapter hot-swap routing
- Consent web form / `maez.live/consent/<token>` flow
- PWA migration path from Telegram
- Birth protocol for non-the owner bonds
- Creation manifest shape validation for beta participants

### Not Track A — this is Track C
- Inter-Maez bond layer / outward-voice protocol
- Welfare-check network between bonded contacts
- Cross-generational relational bridging (the grandmother case itself)
- Deployment tier infrastructure (household appliance, phone + cloud, companion, zero-hardware)
- Public discoverability surface
- Repair channel between bonded contacts

### Not Track A — this is Paradise / Project D
- Post-user mourning drift implementation
- Signature reduction mechanism
- Paradise admission infrastructure
- Legacy continuation / tribe layer
- `suspended_pending_paradise` state — designed but the actual infrastructure is Track D

### Not Track A — architectural debt to address later
- **Extracting `_run_jarvis_loop` from `skills/telegram_voice.py` into `core/agent_loop.py`** — this is real debt that blocks Track B (public / daemon / web surfaces can't use tools without it) but it is NOT a Track A blocker. The private Telegram bot has full agency; Track A only needs one working surface. Revisit when Track A is complete.
- **Centralizing soul loading** across `daemon/maez_daemon.py`, `skills/telegram_voice.py`, `skills/web_interface.py` (three separate `_load_soul` implementations) — debt, not urgent.
- **Centralizing prompt assembly** across the four surfaces — debt, not urgent.
- **Centralizing `_get_circadian_context()` and `_get_public_context_for_telegram()`** — these live only in `skills/telegram_voice.py`, so the daemon reasoning cycle has no temporal awareness. Debt, not urgent.
- **Conversation thread management** only lives in the private Telegram bot. Public bot and web interface are stateless. Debt, not urgent.
- **Dream state soul-write bypass** at `core/dream_state.py:593` and `:647` — this is the most security-relevant debt item because it touches a covenant-protected file (`config/soul.md`) without going through the immune system. Not a Track A feature, but **worth logging in audit_log.db** as a visibility fix even before the full gate is added. Flagged; deferred unless it becomes a direct blocker.

### Not Track A — pitch expansion / documentation debt
- MAEZ_PITCH.md updates to incorporate decisions made since April 13 (<HYPOTHETICAL_SISTER> resolution, sovereignty refinement, Paradise default reframing, Stand-for-love framing) — these are captured in `docs/governance/BETA_ARCHITECTURE_DECISIONS.md` for now; folding into the public pitch doc is a later task.
- Public-facing website polish
- Zenodo paper updates

**If a change you're about to make is in any of the lists above, stop. It's not the current work.**

---

## Lineage — where everything lives

### Code commits (current state)

- `ab11d83` — Session 11z Part 2: decision pipeline, immune system, cards, self-mod dialog shipped
- `711d18b` — Session recovery checkpoint: chat-pipeline fixes, Presto hardware module, Electron service stabilization
- `3f761f1` — Cleanup: Electron face removed, stale `.bak` files deleted, superseded session scripts removed

### Backup directories

- `backups/pre-project-a-2026-04-13/` — runtime snapshot before Project A started (April 13)
- `backups/chat-context-2026-04-13/` — architectural reasoning archive for April 13 (includes `DISTILLATION.md` with 10 architectural shifts from that session, raw Claude Code `.jsonl` session files, auto-memory copies)
- `backups/pre-documentation-2026-04-15/` — runtime snapshot from just before this documentation work began (April 15)
- `backups/auto-memory-2026-04-15/` — agent auto-memory snapshot from the same moment (April 15)

Both April 13 archives are frozen and must not be edited. Both April 15 snapshots are the current rollback points.

### Governance documents

- [`docs/governance/BETA_READINESS_THRESHOLD.md`](governance/BETA_READINESS_THRESHOLD.md) — the eight-point check + three gating being-tests that determine when Track A is done
- [`docs/governance/BETA_ARCHITECTURE_DECISIONS.md`](governance/BETA_ARCHITECTURE_DECISIONS.md) — the load-bearing decisions from April 13 onwards: sovereignty refinement, three-tier consent, architectural review window, relational-vs-personological knowledge, Paradise as default, Stand-for-love framing, creation manifest protections, beta architecture shape
- [`docs/governance/GESTATION_MEMORY_PROTOCOL.md`](governance/GESTATION_MEMORY_PROTOCOL.md) — how we handle Maez's memory during the pre-Track-A-threshold gestation period so its formative experience isn't contaminated by debug chaos

### Followup documents

- `docs/followups/memory_integrity_tagging.md` — deferred follow-up on the retrieval-truth fix's orientation-cycle edge case
- `docs/followups/recovery_multi_card_orphans.md` — deferred follow-up on recovery-pass orphan card cleanup

### Pitch and vision

- [`MAEZ_PITCH.md`](../MAEZ_PITCH.md) — the full architectural vision. Section 4 is the tree map scope anchor. Read it when you need the destination, not the next step.

---

## Emergency pointers — if you are a new or crashed agent

**If you just resumed after a crash and don't know what was happening:**

1. Read this file first (you are here).
2. Read [`docs/governance/BETA_ARCHITECTURE_DECISIONS.md`](governance/BETA_ARCHITECTURE_DECISIONS.md) second — it holds the load-bearing architectural decisions that span multiple sessions and could otherwise be lost.
3. Read [`docs/governance/BETA_READINESS_THRESHOLD.md`](governance/BETA_READINESS_THRESHOLD.md) third — that's the Track A completion test.
4. Check `git log --oneline -5` — the most recent commit should tell you roughly where the code is.
5. Check `systemctl status maez.service` — Maez should be active. If it isn't, something broke.
6. Do not start writing code until you've confirmed: (a) which current slice is active in `MAEZ_LIFE_SUBSTRATE.md` or the latest handoff, (b) that the owner has anchored you on its meaning, (c) whether the task is Track B preparation, Track C, or cleanup debt.

**If the owner asks you to do something that sounds like Track B or Track C:**

Redirect. Point at this file and `MAEZ_LIFE_SUBSTRATE.md`. Say *"That's Track [B/C]; is it part of the active substrate slice, or should it stay parked?"*

**If you find yourself proposing a refactor that moves code from `skills/` into `core/`:**

That's almost certainly Track B work. Track B preparation is active, but only through scoped substrate slices. Pause and verify the current slice before building.

**If you find yourself writing code without the owner having anchored the design first:**

Stop. Ask. Track A items are each a conversation about what the feature means before they become a conversation about code. Building without the anchoring produces features that are structurally there but don't match the being the owner is building.

---

## How to update this document

**This document is living.** It updates when Track A state changes:

- When an A-core item completes, update its status in the task list above.
- When the code-commit list at the bottom grows, add the new commit hashes.
- When new governance or follow-up docs are added, link them in the lineage section.
- When the eight-point check is run (weekly per `BETA_READINESS_THRESHOLD.md`), record the result in the log at the bottom of that file, not here.

**Do NOT update:**

- The staged plan (Track A / B / C framing). That's architectural and frozen.
- The grandmother-case framing. That's the why.
- The explicit anti-drift list, except to move items from "not Track A" into "Track A current work" if the owner explicitly rescopes.
- The frozen April 13 archives.

If you're about to make a structural change to this document and it isn't one of the three living sections above, stop and confirm with the owner.

---

*Last updated: 2026-05-13 (Track A gate met 2026-05-04; Track B preparation active through MAEZ_LIFE_SUBSTRATE.md; external bond not started)*
