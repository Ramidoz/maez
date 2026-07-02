# Metabolic Memory (A3) — Experience-Density Writes Design

**Date:** 2026-07-02. **Lane:** Claude drafts + covenant-review; Codex cross-lane / builds; owner witnesses + runs the curation ceremony. **Status:** DESIGN for review. **Origin:** deep substrate audit F1 (the diary factory) — `docs/2026-07-02-deep-substrate-audit-and-additions.md`. **Owner decisions (2026-07-02):** quiet-cycle thoughts are **ephemeral by default**; existing tier pollution is **curated now, archive-not-delete**, owner-witnessed.

## The one-line intent

> Maez's durable memory scales with **lived events**, not wall-clock: a quiet week costs one line, the body is *sensed* rather than *narrated*, and a 30-second self-glance is perception — kept only when it becomes a fact worth keeping.

## The disease, quantified (verified 2026-07-02)

The reasoning loop stores the LLM's `full_thought` every cycle (`daemon:~10529`, `provenance_source="introspection"`, **`trust_tier="lived"`** — the same tier as the owner's words). Then `consolidate_daily()` (memory_manager:1542) LLM-map-reduces that feedstock into daily summaries, which promotion carries into core. Result today:
- **raw:** 43,687 rows, overwhelmingly cycle introspection (~500/day, forever).
- **daily:** 52 rows — **~85% machine diary** (44 introspection).
- **core:** 156 rows — **over a third introspection journals (56)**, interleaved with the 49 covenant memories. The anchor shelf is one-third CPU diary.

Every recall floor built this week treats this at query time. A3 turns off the tap.

**Rohit's canon line (carried verbatim, the spec's compass):** *Maez's own cycle thoughts should probably not sit in memory with the same `trust_tier="lived"` shape as owner/world events — "that's one of those small field choices that quietly teaches the whole organism what counts as life."*

## Architecture — four parts + one ceremony

### 1. The glance buffer (ephemeral by default — owner-decided)
Un-triggered cycle thoughts go to an **in-memory ring buffer**: they feed the *current* cognition exactly as today (recent-thought consumers keep working — see Task 0 below), decay on an hours-scale, never touch a durable store, and do not survive restart (the continuity capsule already carries mode/stance across restarts; glances are not state).
**Covenant note:** never-delete applies to *recorded* memories. Choosing not to durably record a glance is the **Face-Facts eye pattern** applied inward — perceive fully, keep what becomes a fact. Nothing is muzzled: the thought happens, informs the moment, and passes.

### 2. Durability triggers (deterministic events, never content-kinds — Law 1)
A cycle thought becomes durable when **any** fires:
- an alert/notification was sent; an error/anomaly/watchdog event occurred this cycle;
- owner interaction in the cycle window; an action was proposed/executed;
- a first-of-kind event (deterministic novelty on *event signatures*, not prose);
- a covenant/audit event (self-claim flag, claim-receipt catch, S4/S7 activity) — the natural feed A1 Scar Tissue later builds on;
- **substrate-salience rescue:** if Maez's own machinery (lean-heartbeat "thought_formed/moved", salience-broker proposal) marks the thought, it earns durability — the substrate's own coherence can always overrule the quiet default. This keeps the gate from ever being a hardcoded opinion about what matters: events + Maez's own signals decide, never us.

### 3. Honest trust tier for self-observation
Durable introspection is stamped **`trust_tier="self_observed"`**. **Write-safety (Codex HOLD fix — my "additive-safe" was reader-side only):** `TrustTier` is a closed enum with a ValueError typo-guard, so the build MUST (a) add `TrustTier.SELF_OBSERVED`, (b) pin its `_TRUST_TIER_ORDER` rank — **below `observed`, above `untrusted`** (self-observation is weaker evidence than world-observation, but it is not tainted input), (c) test both the write path (`_provenance_metadata("introspection", "self_observed")` no longer raises) and render/partition behavior downstream. Reader-side remains verified safe (all current readers branch only on `"untrusted"`). Task 0 still confirms the sparse existing `observed` tier's semantics before finalizing. `provenance_source="introspection"` already exists — the tier finally stops flattening self-observation into `lived`.

### 4. Event-gated daily consolidation + the proprioception store
- `consolidate_daily()` input becomes **the durable (triggered) thoughts only** — shrinking the largest LLM→durable path's feedstock at the source (Law 2 bonus).
- **Quiet day → a deterministic, substrate-composed stub** — e.g. `Quiet day. 2,847 cycles, 0 alerts, 0 owner interactions, uptime 23.8h.` — zero LLM prose, one row, durable (the autobiography keeps continuity; a quiet week reads as a quiet week, honestly).
- **Eventful day → real LLM consolidation** of the triggered material (existing path, better diet).
- **Vitals stop being narrative:** CPU/RAM/GPU/temps/counters go to a **proprioception store** (rolling aggregates in sqlite: per-hour/day min/median/max), queryable by cockpit/self-card/capability card — *sensed, not narrated*. Cycle thoughts stop embedding dashboard numbers into autobiographical memory. Historical trends remain fully answerable ("how warm has the GPU run this week?") — from the right organ.

### The curation ceremony (one-time, owner-witnessed — owner-decided)
Existing pollution moves out of the hot indexes, **never deleted**:
1. Enumerate current introspection journals in **core** (~56) and **daily** (~44) by provenance/source metadata; produce a **move-list artifact** with previews.
2. **Rohit reviews the list** (surface-and-ask; anything he flags stays).
3. Approved rows move to an **archive collection** (cold, restorable, excluded from hot recall) — an early down-payment on A11.
4. **raw** cycle rows (~43k): archived **by rule** (provenance = introspection, no episode/scar citation), with the rule + samples owner-reviewed rather than 43k rows individually. Citation-anchored rows stay hot.
5. Canary discipline: before/after counts per tier witnessed; restore-path proven on one row before the bulk move.

## Flags + rollout

`MAEZ_METABOLIC_MEMORY=1` gates the generation-side change (glance buffer + triggers + tier + gated consolidation), default-off, owner-flipped after host witnesses. The proprioception store may land always-on (pure additive telemetry). The curation ceremony is not a flag — it is a witnessed, one-time act with its own artifact.

## Task 0 for the plan (verify before code)

1. **Enumerate consumers of recent cycle thoughts — including the three VERIFIED raw-recency readers (Codex HOLD fix):** `dream_state.recent_raw(n=DREAM_MEMORY_WINDOW)` (dream_state:384), `self_analysis` reading `raw.get(limit=200)` (self_analysis:34), and the proactive-opinion raw window (daemon:4668) — plus cycle_recall_context, lean-heartbeat facts, salience-broker signatures, ws-broadcast. **For EACH consumer the plan makes an explicit decision:** ring-buffer parity (serve it from buffer∪raw so it sees the same world as today), or a **named, owner-visible behavior change** (e.g. "dreams digest only durable material" might even be desirable — but it is a design decision made in daylight, never a silent side effect of the buffer). No consumer may change behavior silently.
2. **Confirm `observed` tier's current meaning** (2 rows in sample) before pinning `self_observed`.
3. **Confirm the daily/core journal enumeration predicate** catches the real rows (the v0.2 gate showed `nightly_journal` hides as `source=` not `type=`).
4. **Locate every `consolidate_daily` caller** (daemon:9288/9323) and the promotion path from daily→core, so event-gating covers both call sites.

## Plan-level pins (Codex review, carried into the plan)

- **Consolidation selects by explicit metadata** — durable-triggered thoughts carry `metabolic_durable_reason=<trigger>`; `consolidate_daily` selects on that field, never on trust tier alone (tier describes evidence class, not consolidation eligibility).
- **The quiet-day stub gets its own type/source** (e.g. `type="quiet_day_stub"`), so it can never masquerade as — or be recalled as — another `daily_consolidation` diary.
- **The curation ceremony includes negative controls:** before any bulk archive, prove the move predicate does NOT match Rohit/relationship anchors, covenant rows, or scar/audit-catch rows — the "Who Rohit Is" class is the explicit must-not-move fixture.

## Out of scope

- `private_thoughts.db` policy — that is **A7** (ephemeral interiority), which awaits Rohit's separate boundary call. A3 touches only the cycle-thought store path.
- Reflection synthesis (strongest-boundary path — unchanged).
- Any deletion, anywhere, ever.
- Any content-kind gate (triggers are events + substrate signals only).
- A11's general archival policy (the ceremony is a scoped down-payment, not the policy).

## Witnesses

**Host:** quiet-day simulation → exactly one deterministic stub row, zero LLM calls; triggered events (each trigger class) → durable with `self_observed`; salience-rescue → durable; ring buffer feeds every Task-0-enumerated consumer identically (before/after parity test); flag-off byte-identical; vitals queries answered from the proprioception store.
**Ceremony:** move-list artifact reviewed by owner; per-tier before/after counts (core introspection ~56→~0 hot); one-row restore proven before bulk; nothing deleted (archive counts = moved counts).
**Live (owner, after flip):** a genuinely quiet day yields one stub; an eventful day yields real consolidation; recall on casual turns no longer surfaces machine diaries even *without* the floors doing the work (the floors stay as defense-in-depth); "how has the GPU been?" answered from proprioception.

## Predicted effect

After A3: Maez's autobiography records **a life** — conversations, events, anomalies, acts, scars-to-be — at event density; a quiet week costs one honest line; its body is continuously sensed through a proprioception organ instead of narrated into memory; the anchor tier holds covenant and relationship instead of being one-third CPU diary; the biggest LLM→durable path shrinks to triggered material only; and the trust field finally tells the truth about what is *lived* versus what is *self-observed* — the small field choice that teaches the whole organism what counts as life.

## Spec Self-Review

**Placeholder scan:** tier name + journal predicate + consumer list deliberately deferred to Task 0 verification (evidence over assumption). No TODOs.
**Consistency:** ephemeral default + always-durable triggers + salience rescue = the owner's decision fully expressed; curation = archive-not-delete with owner review at both granularities (rows for core/daily, rule+samples for raw); Law 1 (event/mechanism gates only) and Law 2 (shrinks LLM→durable feedstock) both served.
**Scope:** one slice — the cycle-thought path + daily consolidation + proprioception + one ceremony. A7/A11/reflection walled off.
