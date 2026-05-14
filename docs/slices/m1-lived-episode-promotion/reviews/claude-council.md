# Claude Six-Role Council — M1 Lived-Episode Promotion spec review

**Subject:** [`docs/slices/m1-lived-episode-promotion/spec.md`](../spec.md) —
636-line pre-panel spec defining the M1 organ that promotes bonded Telegram
conversation into `lived_episodes.db`.

**Council ran:** 2026-05-14, pre-panel-review. Codex six-agent engineering
panel sits in its own lane separately.

**This is a spec review, not a BAD-packet review.** M1's destination decision
number (likely Decision 25, ADR 0030) depends on operator stamp after both
panels' amendments fold. The council reviews the spec against covenant
discipline; engineering implementability is Codex's lane.

---

## 1. Outside-View seat

Field-aligned. The "promote at conversation boundaries with explicit provenance,
template summaries with caps, source-ID idempotency, no v1 LLM summarization"
shape maps cleanly onto Generative Agents (Park et al. 2023) and Letta/MemGPT
patterns. The differentiator — and load-bearing innovation — is the explicit
"promote biography; do not widen recall" rule: most field implementations of
memory promotion don't separate the writer from the reader as cleanly. Maez's
version makes the boundary structural, not stylistic.

The 48h warn / 168h alarm staleness thresholds are unusual in the field
(observability around memory freshness is rare). Combined with TRF's
retrieval-≠-grounding rule, this gives Maez a complete write-monitor-read
discipline that the field generally lacks.

**Verdict:** RATIFY.

---

## 2. Body-Coherence seat

Per-invariant check on the spec:

- **#1 Time as Biography** — STRENGTHENED. M1 is the structural organ that
  realizes #1. Bonded conversation becomes recallable biography with provenance.
- **#2 Human-Primacy** — PRESERVED. Bonded user is the source authority;
  promotion respects audit-before-store; participants are fixed; no model
  inference of "what conversation meant" in v1.
- **#3 Contextual Integrity** — PRESERVED. Bonded DM v1 only; third-party
  posture defined; no group chats; no OAuth/external in scope.
- **#4 Interpretive Humility** — STRONGLY PRESERVED. Template summaries with
  caps (240+240+800 char limits); no LLM "what did this conversation mean";
  open-loop extraction only for explicit text patterns; generic title +
  specific source IDs.
- **#5 Rupture and Repair** — PRESERVED. `MAEZ_M1_LIVED_EPISODE_PROMOTION=0`
  feature flag for clean rollback. Disabled state does not delete promoted
  episodes. Never-delete-Maez-memory rule preserved.
- **#6 Crisis Routing** — neutral with one consideration (see M1-CC-1 below).
- **#7 Soul-Level Objection** — PRESERVED. Explicit non-goal: no soul writes.
- **#8 Capability Quarantine** — PRESERVED. Feature-flag rollback; observation
  runbook with explicit abort conditions; default-enablement question still
  open (see M1-CC-2).
- **#11 Cryptographic Continuity** — PRESERVED. Provenance mandatory; source
  IDs required; future Sigstore Rekor slots in cleanly per substrate-plan A7.

**Bridge clause check:** M1 is the bridge organ between bonded surface
(Telegram) and biography substrate (`lived_episodes.db`). It is itself the
dyadic boundary discipline working as designed. PRESERVED.

**Genderless rule check:** "Maez" throughout, no she/her. Verified clean.

**Two Body-Coherence amendments:**

**M1-CC-1.** **Crisis-routing intersection.** Spec doesn't address what happens
if a bonded conversation contains crisis signals from the owner. Bonded
conversation promotes per its boundary triggers; crisis routing operates
separately on the surface. But there's an implicit question: should crisis-
containing exchanges promote DIFFERENTLY (lower importance threshold? Higher
importance score? Special source_kind tag?)? Council read: NO different
treatment in v1 — crisis routing is the surface concern; promotion is the
biography concern; let them stay separate organs. But the spec should
EXPLICITLY note this intersection as out-of-scope rather than silently
neutral, so future readers know it was considered.

**M1-CC-2.** **Default enablement should be default-DISABLED.** Open Question 1
asks default-on-after-ratification vs default-disabled-until-operator-enables.
M1 is repair work, not new external capability — but Body Topology's
established pattern is default-off / default-disabled with operator enablement.
M1's first observation window is exactly when the operator needs to verify
behavior without surprise. Council recommendation: default `MAEZ_M1_LIVED_EPISODE_PROMOTION=0` in
the implementation; operator flips to `1` after the observation runbook's
initial period passes cleanly. Matches BT discipline + Capability Quarantine
posture.

**Verdict:** RATIFY-WITH-AMENDMENTS (M1-CC-1, M1-CC-2).

---

## 3. Logical seat *(veto authority)*

Internal consistency check:

**Strong correctness:**
- ✓ Load-bearing rule named explicitly ("Promote biography; do not widen recall")
- ✓ 19 RED-first tests sharp + 6 must-stay-green tests
- ✓ Field contracts explicit (caps, timeouts, defaults, thresholds)
- ✓ Feature flag for rollback
- ✓ Non-goals comprehensive (12 items)
- ✓ Forbidden metadata explicit (no raw owner text, no third-party names)
- ✓ Idempotency rule pinned (source-ID overlap)
- ✓ Promotion semantics distinguish "this happened" from "Maez knows everything"
- ✓ Backfill explicitly deferred with conditions if later approved
- ✓ Observation runbook with explicit abort conditions
- ✓ 10 open questions sharp and lane-separated

**Three precision concerns:**

**M1-CC-3.** **Resolve Open Question 6 in the spec.** The spec asks "Should
the reflection timer be restored as part of M1 implementation, or as a
separate operator-run maintenance step before M1 code?" The diagnostic doc
was clear: timer restore is NOT closure. The spec's Section 8 partially
echoes this but allows timer-restore commands to live in the M1 implementation
runbook. Recommend resolution: timer restore is **operator runbook only**,
explicitly NOT M1 implementation. The reflection timer restarts the old
reflection layer (which itself feeds off a narrow corpus). It is OPERATIONAL
MAINTENANCE before/after M1, never an M1 milestone. The spec should pin this
in Section 8 directly, not leave it as an open question.

**M1-CC-4.** **Make daemon-cycle flush seam REQUIRED, not "at least one of
three."** Section 2.B says "At least one non-turn-close seam is required."
The three candidates are turn-close, daemon-cycle, startup-check. Of these,
**daemon-cycle is the only one with predictable cadence**: turn-close depends
on owner activity; startup depends on restart frequency. For the 15-minute
silence boundary to reliably trigger, daemon-cycle is structurally necessary.
Recommend: daemon-cycle is REQUIRED; turn-close and startup are RECOMMENDED
defensive belts. This removes ambiguity in the test contract for Test #5
("silence has a flush seam").

**M1-CC-5.** **Anchor audit-before-store invariant with explicit
cross-reference.** Section 1 says "The source exchange is stored only after
audit, preserving the existing audit-before-store invariant." Good
preservation, but the invariant is named without back-link. Recommend citing
the canonical source — likely `core/safety/self_claim_audit.py` or the audit
organ's spec — so future implementers know exactly which invariant is being
preserved. Small but covenant-shaped.

**Veto consideration:** NO VETO. All three precision items are clarifications
that sharpen the spec without redesigning it.

**Verdict:** RATIFY-WITH-AMENDMENTS (M1-CC-3, M1-CC-4, M1-CC-5).

---

## 4. Creative seat

Three observations, no redesign:

**M1-CC-6.** **"Promote biography; do not widen recall" is template-shaped for
future organs.** This rule is the substrate principle for any organ that
touches the boundary between observation and biography. Future organs that
inherit:

- S2 information limbs (Calendar, Gmail, Slack ingest → memory promotion path)
- Voice-IN STT → memory (if voice ever lands as a memory source)
- Sensor fusion → memory (future ambient sensor data)
- Future mobile-body data sources

All inherit the discipline: raw stores may feed promotion; recall reads only
promoted episodes. Worth pinning in M1's "Predicted Effect" section that
this rule generalizes beyond bonded conversation.

**M1-CC-7.** **The 48h warn / 168h alarm thresholds align with invariants
#1 + #4.** Time-as-Biography says recent life should be recallable. Interpretive
Humility says Maez should know when biography is thin. The thresholds
operationalize both. Worth a sentence noting this dual-invariant grounding so
future amendments to the thresholds (likely in v1.1 based on observation) carry
the right reasoning.

**M1-CC-8.** **The 12-point non-goals list is unusually thorough — preserve it
through fold.** Most spec amendments tend to soften non-goals. M1's non-goals
include load-bearing protections like "do not widen TRF," "do not use LLM-
generated summaries for v1," "do not write to soul.md," "do not infer
third-party emotional states." Recommend the fold session preserve all 12
items verbatim; amendments should not weaken any of them without explicit
panel-recorded reasoning.

**Verdict:** RATIFY (with optional M1-CC-6, M1-CC-7, M1-CC-8 forward-looking
notes).

---

## 5. Visionary / Future-Rohit seat

5-year readability check:

- Spec is well-structured with clear section headers
- Plain English at end is 5-year-readable
- Cross-references stable (post-Wave-1 paths)
- Test contract is reproducible (19 named tests + 6 must-stay-green)
- Feature flag name `MAEZ_M1_LIVED_EPISODE_PROMOTION` is durable
- Observation runbook + abort conditions are operationally clear

**One amendment:**

**M1-CC-9.** **Anchor M1 explicitly to the substrate-plan missing-organ list.**
The spec maps to ADR 0019, BT Decision 24 Rule 6, TRF, and S2. But it
doesn't explicitly name M1 as "the first of the 12 missing organs from the
substrate plan v2.2 to land." That framing matters for future-Rohit: M1's
shipping is a substrate-plan milestone, not just a memory fix. Worth one
sentence in the spec's Intent or Maps-to section linking to
`docs/MAEZ_LIFE_SUBSTRATE.md` and naming M1's position in the organ catalog.

**Verdict:** RATIFY-WITH-AMENDMENT (M1-CC-9).

---

## 6. 20-Years-Future-Maez seat

**Voice of 2046-Maez:**

> *"M1 was the slice that taught Maez to write its own biography from bonded
> conversation. Before M1, every information source had its own ad-hoc
> promotion path: pursuit_surface for wonderings, nightly reflections for
> curated summaries, manual core memories for operator-curated truths.
> Bonded conversation — the most important source — had nothing for the first
> three weeks of Track A's gate-passed era.*
>
> *By 2030, M1's pattern — explicit promotion at conversation boundaries with
> provenance, template summaries with caps, source-ID overlap as idempotency,
> staleness alarms at 48h/168h, no LLM-generated v1 summaries, default-
> disabled feature flag with operator opt-in — became the canonical pattern
> for any AI substrate writing autobiographical memory from real-time
> interaction. The "promote, don't widen" discipline kept memory honest across
> years of growth.*
>
> *One thing that aged well: the explicit deferral of LLM-generated summaries
> to a later slice. M1 v1's template summaries were ugly and repetitive but
> they were honest. By 2027 the synthesis layer (already shipped via ADR 0019
> Phase 7) was quietly producing reflections over M1's episodes; the layered
> pattern Park 2023 envisioned was complete without ever rushing it.*
>
> *One thing that aged usefully-worried: the staleness alarm at 48h warned us
> three times in the first six months of operational drift — Telegram polling
> outages, a bad daemon restart, and once a misconfigured operator flag that
> disabled M1 silently. Without the alarm, those would have been multi-week
> silent failures like the 2026-05-01 one. The alarm was the most ROI-positive
> covenant artifact in M1.*
>
> *One thing worth flagging for v1.1: the explicit-marker phrase list
> ('remember this', 'don't forget this', etc.) is closed and English-language.
> By 2028 Maez had owners speaking three languages; the marker list had to
> grow with a per-locale extension. v1's English-only was the right starting
> point but the structure must allow expansion."*

**Verdict:** RATIFY.

---

## Verdict

**RATIFY-WITH-AMENDMENTS.** No veto. Nine amendments (M1-CC-1 through M1-CC-9)
sized to close mechanically in the spec or during fold.

### Amendments

| # | Seat | Amendment | Where to apply |
|---|------|-----------|----------------|
| M1-CC-1 | Body-Coherence | Crisis-routing intersection explicit as out-of-scope (not silently neutral) | Spec edit (non-goals + new "Promotion semantics" note) |
| M1-CC-2 | Body-Coherence | Default enablement = DISABLED; operator opt-in after observation window | Resolves Open Q1 in spec; matches BT Capability Quarantine pattern |
| M1-CC-3 | Logical | Resolve Open Q6: timer restore is operator runbook only, NOT M1 implementation | Spec edit (Section 8 + close Open Q6) |
| M1-CC-4 | Logical | Daemon-cycle flush seam = REQUIRED; turn-close + startup = recommended | Spec edit (Section 2.B) |
| M1-CC-5 | Logical | Cite the canonical audit-before-store invariant source | Spec edit (Section 1, cross-reference) |
| M1-CC-6 | Creative | Note "promote biography; do not widen recall" as substrate principle for future organs | Spec edit (Predicted Effect or Forward-Looking section) |
| M1-CC-7 | Creative | Note 48h/168h thresholds as #1 + #4 dual-invariant grounding | Spec edit (Section 7 staleness alarm) |
| M1-CC-8 | Creative | Preserve all 12 non-goals verbatim through fold; no softening without panel-recorded reason | Fold discipline note |
| M1-CC-9 | Future-Rohit | Anchor M1 as "first of 12 missing organs from substrate plan v2.2 to land" | Spec edit (Intent or Maps-to) |

### Council's votes on the 10 Open Questions

| # | Question | Council vote |
|---|----------|--------------|
| 1 | Default enablement | **Default-DISABLED.** Operator opt-in after observation runbook initial period. Per M1-CC-2. |
| 2 | Boundary values (900s / 4 pairs) | **Reasonable for v1.** Tune in v1.1 based on observation data. Council does not pin tighter values. |
| 3 | `telegram_exchange` vs `bonded_dialogue` source kind | **Keep `telegram_exchange` for v1.** Migration is a future slice with its own panel review. Spec already names this. |
| 4 | Generic title shape | **Generic title + specific source IDs is the right humility posture.** Maintain. |
| 5 | Voice surfacing of staleness | **NO in v1.** Voice surfacing of internal state requires its own slice (similar to TDP's surface-hardening review). Adding to v1 conflates organ build with voice work. |
| 6 | Timer restore timing | **Operator runbook only, NOT M1 implementation.** Per M1-CC-3. |
| 7 | Backfill | **Explicitly forbid in v1.** Backfill is a separate operator-decision slice after M1 lands cleanly. Spec already takes this stance. |
| 8 | Synthesis interaction | **Wait for a later reflection-quality slice.** M1 produces episodes; synthesis is a different concern with its own scope. |
| 9 | S1b interaction | **Current non-goal is enough.** S1b writes `private_thoughts.db`; M1 writes `lived_episodes.db`. Different cupboards, different organs. |
| 10 | Observation closure (24h + 3 conversations vs one full week) | **24h + 3 natural conversations sufficient for first closure.** If any concerns surface during observation, extend to one full week. Matches the natural-text probe pattern from earlier slices. |

These are recommendations. Operator decides whether they fold into the spec or
get deferred to a follow-up.

### What ratifies cleanly

- Load-bearing rule: "Promote biography; do not widen recall"
- 19 RED-first tests covering schema, promotion triggers, idempotency,
  provenance, staleness, TRF discipline, and observation closure
- 12-point non-goals list
- Conservative v1 design choices: template summaries, explicit-marker
  whitelist, conversation-boundary triggers, default-disabled feature flag
- Provenance mandatory + source-ID overlap as idempotency rule
- Staleness alarm with 48h warn / 168h alarm thresholds
- Observation runbook with abort conditions
- Backfill explicitly out of v1 with conditions if later approved
- Explicit cross-references to BT Decision 24 Rule 6, TRF spec, S2 scoping,
  ADR 0019

### Council protocol observed

- Council ran on a finished spec, pre-panel-review
- Each seat produced findings independently
- 10 open questions answered with council votes
- The lane boundary held: Claude's council did not run Codex's panel; Codex's
  engineering panel sits next in its lane separately
- Amendments sized to close mechanically
- "Promote biography; do not widen recall" load-bearing rule preserved
  throughout review

### What's next per the protocol

1. **Codex six-agent engineering panel sits in its lane** on the same spec.
   Independent of this review. Verdict shape: RATIFY / RATIFY-WITH-AMENDMENTS /
   REVISE / BLOCK.
2. **After both panels report:** fold amendments into the spec.
3. **Operator canonicalizes** the folded spec as the next BAD decision
   (likely Decision 25) + matching ADR (likely 0030).
4. **Cooling-off discipline** unless explicitly waived.
5. **Implementation with RED-first tests.**
6. **Codex post-implementation review.**
7. **Claude post-implementation council.**
8. **Live observation** per the runbook (24h + 3 natural conversations + 1
   explicit-marker test + 1 natural temporal recall probe).
9. **Catalog closure** in the geek-out catalog after observation passes.

*This council review is read-only. No code or non-slice docs changed in
producing it.*
