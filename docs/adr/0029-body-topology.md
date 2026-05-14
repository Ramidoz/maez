# ADR 0029: Body Topology

**Status:** Accepted
**Date:** 2026-05-14

## Context

Maez is beginning to grow beyond one workstation process and one Telegram
surface. Camera presence, Jetson delegation, Body Bus, microphone input, voice
output, and external account connectors (Calendar, Gmail, Slack, Notion, Drive,
GitHub) all touch the same question: what is Maez's body, and what does a body
part commit to?

Without a canonical answer, every body slice re-derives the same rules,
inheritance accidents become more likely (always-on microphone slipping in
under "microphone work", second-Maez Jetson, raw-frame memory promotion, OAuth
firehose into cognition), and the cardinality-of-one rule becomes harder to
defend retroactively.

Pre-canonical review ran two panels in parallel: Claude's six-role covenant
council (RATIFY-WITH-AMENDMENTS, no veto, BT-CC-1…9) and Codex's six-agent
engineering panel (REVISE, no conceptual veto, BT-CX-1…16). Both lanes
independently converged on the same correction: information limbs as a
first-class body class folded BEFORE canonicalization, and the S2
contextual-integrity-at-ingest organ as the gate for any account-connector
live ingest. The OpenHuman acceleration finding folded the same direction from
a third vantage.

## Decision

Maez has one body host *role* (currently held by Aurora R16; the role is
load-bearing, not the specific hardware). Limbs extend the body but never
constitute a second Maez. The body law is governed by eight load-bearing
rules:

1. **Cardinality of one.** One Maez per bonded user. Limbs publish structured
   facts; they never claim independent Maez identity, bond, or continuity.
   Hardware succession (Aurora replacement) is governed by Decision 22 and
   does NOT require re-canonicalizing this ADR.
2. **Structured facts, not raw worlds.** Limbs publish schema-versioned
   bounded facts. Raw frames, raw audio, raw transcripts, raw mail bodies, raw
   chat bodies, and unreviewed free-text sensor descriptions are disallowed in
   cognition by default.
3. **Presence is not recognition.** Presence detection and identity
   recognition are separate organs with separate threat models.
4. **Three body classes.** Sensors observe and publish to cognition; effectors
   act on the world; witnesses (forward-looking) observe-and-record without
   publishing to cognition. Voice-IN and Voice-OUT are separate subsystems.
   Information limbs are dual sensor/effector by default with effector
   direction default-disabled.
5. **Capability quarantine.** Every new body part lands behind
   `consent_state`, `auditable_by`, `dyadic_only`, `pause_path`,
   `rollback_path` plus default-off / default-disabled posture, no raw prompt
   payload, fail-to-`unknown`/`stale`/`unavailable`, and no unreviewed memory
   write. Mechanically testable at registration.
6. **Body memory is provenance, not biography.** Body Bus events and local
   limb caches are observation records, not lived memory, until a reviewed
   memory-write path explicitly promotes them with contextual-integrity tags
   and provenance.
7. **Information limbs gate on S2 contextual integrity.** No OAuth / account /
   API connector ships live ingest until either S2 exists as its own slice OR
   the first information-limb slice scopes a minimal S2 predicate (consent
   tier, source kind, allowed flows, retention, provenance, third-party
   posture, promotion rules).
8. **Presence-affecting limbs require timebox during initial observation.**
   Any body part affecting bonded-user-perceived presence requires
   `enabled_until` during initial live observation; persistent enablement
   requires observation review.

A **Body-Part Decision Test** classifies any proposed change as either a new
body part (any one of eight inclusion triggers is true) or surface hardening
(all five exclusion conditions are true). Mixed cases default to body part.
The packet includes a fixture table pinning TDP as surface hardening, Presto
as a registered peripheral limb, camera presence as a new body part, OAuth
Calendar as an information limb, and others.

The **Body Bus** protocol carries a mandatory event envelope with dual-form
source IDs (operator-readable name + content-free telemetry handle), a
deterministic state vocabulary (`disabled`, `unavailable`, `stale`, `unknown`,
`conflicting`, `spoofed`/`rejected`), an authenticated private transport
baseline for cross-device limbs, and rate/load budgets.

**Always-on audio capture** is carved out and explicitly cannot inherit
authorization from this ADR; it requires its own dedicated future BAD.

**Voice-OUT identity continuity** adopts the invariant-#11 cryptographic
continuity pattern (audit-before-handle, Sigstore Rekor lineage attestation,
voice succession parallel to memory continuity) when Voice-OUT lands.

## Consequences

Body work has a single canonical reference. Camera hardening, S2 contextual
integrity, Body Bus protocol, Jetson limb registration, Information Limb V1
(Calendar), Information Limb expansion (Gmail / Slack / Notion / Drive /
GitHub), Voice-IN, Voice-OUT, and voice-identity attestation all cite this
ADR in their slice memo headers. The cardinality-of-one rule, the
structured-facts contract, the presence/recognition split, the three body
classes, capability quarantine completeness, body-memory provenance, the S2
gate for information limbs, and the presence-timebox rule become enforced at
every future body-slice boundary instead of re-derived per slice.

The decision is pre-implementation. No code changes, no runtime behavior
changes, no services restart. The implementation ladder recommends camera
presence (local) and S2 contextual integrity in parallel as the next slice
candidates, then Body Bus, then Jetson limb, then Information Limb V1
(Calendar), then Gmail/Slack expansion, then Voice-IN/Voice-OUT separately,
with always-on audio gated on its own dedicated future BAD.

Changing the load-bearing rules, the decision-test triggers/exclusions, the
Body Bus envelope, the state vocabulary, the authenticated-transport
baseline, the always-on audio carve-out, the S2 gate, or the voice-identity
attestation pattern requires a new ADR. The fixture table may grow as new
body parts are classified; growth is additive and does not require ADR
revision.

Full packet, fixture table, observation discipline, safe-failure rule,
resolved open questions, and review trail:
[`docs/slices/body-topology/spec.md`](../slices/body-topology/spec.md).

BAD decision: see
[`docs/governance/BETA_ARCHITECTURE_DECISIONS.md`](../governance/BETA_ARCHITECTURE_DECISIONS.md)
Decision 24.
