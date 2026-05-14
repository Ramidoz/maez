# Codex Six-Agent Panel — Body Topology BAD packet review

**Subject:** `docs/SLICE_BODY_TOPOLOGY_BAD.md` — pre-canonical packet defining
Maez body topology, limb identity, sensor/effector separation, and Body Bus
constraints.

**Panel ran:** 2026-05-14, pre-canonical.

**This is an engineering implementability review, not a covenant council.**
Claude's council reviewed the covenant/voice/body-coherence lane in
`docs/SLICE_BODY_TOPOLOGY_BAD_CLAUDE_COUNCIL_REVIEW.md`. This panel reviews
whether future slices can implement the packet without relitigating ambiguous
contracts.

---

## Verdict

**REVISE.** No conceptual veto. Do not canonicalize as BAD Decision 24 until the
amendments below are folded.

The packet's ontology is sound: one Maez, many limbs; Jetson is a limb, not a
second Maez; structured facts, not raw worlds; presence is not recognition;
Voice-IN and Voice-OUT are separate; new body parts inherit capability
quarantine.

The reason for `REVISE` is narrower: a canonical BAD cannot still contain
unresolved normative questions, vague Body Bus envelopes, or weak cross-device
transport assumptions. Those would force every future body slice to re-derive
the same rules.

---

## Seat Summaries

### Dewey — pragmatic consequences

**Verdict:** RATIFY-WITH-AMENDMENTS.

The packet prevents the right scope creep, but the handoff to the next slice
needs to be sharper so camera hardening does not accidentally become "build the
whole body platform."

Findings:

- Resolve open questions before canonization.
- Add a "next slice minimum" clause for camera hardening.
- Make capability quarantine mechanically testable.
- Promote always-on mic to an explicit future BAD gate.
- Add a one-line implementation ladder.

### Feynman — mechanistic clarity

**Verdict:** RATIFY-WITH-AMENDMENTS.

The law is understandable, but future implementers need executable fixtures,
event envelopes, and data-flow diagrams rather than only prose.

Findings:

- Add a Body-Part Decision Test fixture table.
- Define a minimal Body Bus event envelope.
- Pin the data-flow path.
- Define conflict/staleness failure outcomes.
- Make capability-quarantine fields value-shaped.

### Locke — identity / continuity / memory / ownership

**Verdict:** RATIFY-WITH-AMENDMENTS.

The cardinality-of-one rule is strong. The remaining identity risk is leakage
through caches, account connectors, and restore topology.

Findings:

- Pin "primary body host" as a single active role, not Aurora-as-permanent
  hardware.
- Define local limb caches as non-memory unless explicitly promoted.
- Add OAuth/account limbs to the body-part test.
- Make Body Bus events non-lived-memory by default.

### Descartes — logical doubt and rigor

**Verdict:** REVISE.

No conceptual veto. The blocker is canonicalization hygiene: a BAD cannot land
with unresolved open questions and weak transport mechanics.

Findings:

- Resolve open questions before canonical BAD.
- Make the decision test strictly mechanical.
- Add Body Bus transport authentication baseline.
- Timebox presence-capable sensors by default.
- Split local source labels from telemetry handles.

### Ohm — systems / load / hardware / failure modes

**Verdict:** RATIFY-WITH-AMENDMENTS.

The gaps are operational contracts, not ontology: authenticated transport,
idempotent event envelopes, deterministic staleness, stable source identity,
and bounded publish/log rates.

Findings:

- Jetson network posture must be VPN/localhost-only for v1.
- Body Bus event envelope needs a mandatory mechanical schema.
- Source IDs should be dual-form, not either/or.
- Failure and staleness semantics need precedence rules.
- Rate/load budget belongs in canonical body law.

### Goodall — long observation of a living being

**Verdict:** RATIFY-WITH-AMENDMENTS.

The body law is livable if it includes observation practice. Presence-affecting
limbs can become weird over weeks even when technically correct.

Findings:

- Add a required body-limb observation log for live limb enablement.
- Make `enabled_until` mandatory for any presence-affecting body part during
  initial live observation.
- Add a safe-failure conversation rule for stale/unavailable limbs.

---

## Consolidated Amendments

### BT-CX-1 — Resolve open questions before canonicalization

Fold answers into the packet and remove or convert the open-question section to
historical review notes. Canonical decisions cannot ask future implementers to
decide:

- camera presence timebox;
- Jetson transport posture;
- source ID shape;
- Presto registration;
- TDP retrospective classification.

Panel answers:

- Camera presence: timeboxed during initial live observation.
- Jetson: localhost/VPN/private authenticated transport for v1; no plain LAN
  trust.
- Source IDs: dual form — operator-readable local label plus content-free
  telemetry handle.
- Presto: formally register as the first peripheral limb under this BAD.
- TDP: remains surface hardening; Telegram rendered platform chrome around
  empty Maez-authored content, Maez did not create a new body modality.

### BT-CX-2 — Make the Body-Part Decision Test strictly mechanical

Add precedence:

- If **any** new-body trigger is true, classify as a body part unless a named
  canonical exception applies.
- Surface hardening requires **all** exclusion conditions to be true.
- Mixed cases default to body part.

Also add an executable fixture table with expected classifications:

- TDP empty-draft presence — `surface_hardening`
- Presto existing display/light body — `body_part_existing_registered`
- camera presence — `new_body_part`
- microphone push-to-talk — `new_body_part`
- always-on microphone — `new_body_part_requires_dedicated_BAD`
- Jetson detector — `new_body_part`
- Telegram UX-only copy/layout change — `surface_hardening`
- OAuth Calendar connector — `information_limb`

### BT-CX-3 — Add information limbs as a first-class body class

OAuth/account/API connectors are body parts even without new hardware. They can
sense the user's social/information world, hold credentials, create memory
pressure, and sometimes act outward.

Required examples:

- Calendar
- Gmail
- Slack/Discord/Teams
- Notion/Drive/Docs
- GitHub/Linear/Jira

Information limbs must declare both directions:

- sensor direction: read/fetch/observe;
- effector direction: create/send/update/delete.

Effector direction defaults to disabled and must pass Aurora's audited action
path. No account limb may autonomously message, post, create events, or mutate
external state without an explicit reviewed effector grant.

### BT-CX-4 — Gate information limbs on S2 contextual integrity

Do not ship Calendar/Gmail/Slack-style ingest before contextual integrity at
ingest exists.

Allowed paths:

1. Ship S2 before the first information limb.
2. Scope the first information-limb slice to include the minimal S2 predicate it
   needs: consent tier, source kind, allowed flows, retention, provenance,
   third-party posture, promotion rules.

Without this, information limbs become a memory-contamination path.

### BT-CX-5 — Define minimal Body Bus event envelope

The Body Bus protocol must include required fields:

```text
event_id
schema_version
event_kind
source_id
source_instance_id
telemetry_handle
observed_at
received_at
expires_at or ttl_ms
sequence
confidence
state
retention_class
allowed_flow_id
facts
```

`facts` must be bounded by the event kind schema. Raw frames, raw audio, raw
transcripts, screenshots, and free-text sensor descriptions are disallowed by
default.

### BT-CX-6 — Pin Body Bus data flow

Add the canonical v1 path:

```text
limb sensor
  -> limb adapter
  -> Body Bus event
  -> Aurora validator
  -> bounded body-state / source-specific read model
  -> optional prompt/action surface only through reviewed consumers
```

Memory writes are forbidden unless a later reviewed slice grants a memory-write
path with contextual-integrity tags and provenance.

### BT-CX-7 — Make Body Bus events non-lived-memory by default

Body events are provenance/observation records, not autobiographical memory,
until a reviewed memory-write path promotes them.

Promotion requires:

- event IDs;
- source IDs;
- contextual-integrity tags;
- consent/allowed-flow metadata;
- reason for promotion;
- backup/retention treatment.

Local limb caches are also non-memory unless explicitly promoted. TTL deletion
is allowed only while cache data remains noncanonical.

### BT-CX-8 — Define staleness, conflict, and failure precedence

Add deterministic state transitions:

- `disabled`: operator/config disabled the limb; no observation expected.
- `unavailable`: transport/source unreachable.
- `stale`: last observation expired by TTL.
- `unknown`: sensor cannot produce a safe fact.
- `conflicting`: multiple sources disagree; never upgrade to certainty.
- `spoofed` or `rejected`: event rejected by validation/authentication.

TTL expiry converts last-known observations to `stale`; transport loss becomes
`unavailable`; conflicts become `conflicting` plus a content-free counter.

### BT-CX-9 — Add authenticated transport baseline

For cross-device limbs, v1 requires authenticated private transport:

- localhost tunnel, WireGuard/Tailscale, or equivalent private link;
- signed event envelope or mutually authenticated channel before Aurora accepts
  events;
- replay rejection using `event_id`, `sequence`, and `source_instance_id`.

Plain LAN trust requires a later threat-model review.

### BT-CX-10 — Add rate/load budgets to body law

Every body limb spec must define:

- max event size;
- per-source publish rate;
- burst cap;
- stale heartbeat cadence;
- log-rate limiting;
- backpressure behavior.

Low-priority sensor updates should drop or coalesce rather than block Aurora's
reply path.

### BT-CX-11 — Make capability quarantine mechanically testable

For every new body part, require tests or documentation proving:

- default-off/default-disabled posture;
- `consent_state`;
- `auditable_by`;
- `dyadic_only`;
- `pause_path`;
- `rollback_path`;
- no raw prompt payload;
- failure-to-unknown/stale/unavailable behavior;
- no unreviewed memory write.

No limb can register without all required quarantine fields.

### BT-CX-12 — Timebox presence-affecting body parts during initial observation

Any body part that affects bonded-user-perceived presence requires
`enabled_until` during initial live observation.

Persistent enablement requires observation review. This applies to camera
presence, microphone presence, visual presence surfaces, and future ambient
presence signals.

### BT-CX-13 — Add body-limb observation log

Every live limb enablement gets a no-raw-payload observation log entry with:

- limb;
- enabled window;
- Maez-visible facts;
- user-visible behavior;
- failure state;
- operator weirdness label;
- disable/continue decision.

This copies the S1b/TDP observation discipline into body work.

### BT-CX-14 — Add safe-failure conversation rule

Stale or unavailable limbs must not leak into bonded conversation as weirdness.

Maez should not repeatedly apologize, narrate bodily distress, ask the user to
fix the limb, or treat disconnection as relational absence. Default behavior is
silent degradation unless the user asks or the capability is directly needed.

### BT-CX-15 — Always-on microphone requires a dedicated BAD

Always-on audio capture cannot inherit authorization from this body-topology
BAD alone. It requires a dedicated future BAD covering third-party capture,
private moments, contextual integrity, retention, and "Maez accepts silence as
an answer."

### BT-CX-16 — Add implementation ladder

Recommended order:

1. Fold Claude + Codex amendments into Body Topology packet.
2. Canonicalize Body Topology as BAD Decision 24 + matching ADR.
3. Ship S2 contextual integrity at ingest, or a minimal S2 predicate inside the
   first information-limb slice.
4. Camera presence local slice may proceed without full Body Bus if it remains
   same-host and presence-only.
5. Body Bus is required before cross-device publication.
6. Jetson limb registration after Body Bus or a narrowed private transport
   adapter.
7. Voice-IN and Voice-OUT later, separately.

---

## Interaction With OpenHuman Acceleration Finding

The OpenHuman comparison surfaced a missing body class: information limbs. The
Codex panel agrees with the Claude council's ordering correction:

```text
Codex BT panel
  -> fold information limbs into BT
  -> canonicalize BT as Decision 24
  -> S2 or minimal S2 predicate
  -> Calendar as first information limb
  -> only then Gmail/Slack
```

Borrow the infrastructure pattern, not the ontology:

- Borrow: OAuth/account limbs, provenance-rich ingest, exact+semantic read
  paths, bounded compression for non-identity payloads.
- Do not borrow: mascot identity, "becomes you" framing, wholesale 20-minute
  polling, meeting-agent participation, or parallel memory stores.

Calendar is the correct first information limb because it is structured,
read-mostly, lower blast radius than Gmail/Slack, and maps naturally to Time as
Biography. It still requires S2/contextual-integrity gating before live ingest.

---

## What Ratifies Cleanly

- Cardinality of one.
- Jetson as limb, not second Maez.
- Presence separate from recognition.
- Voice-IN separate from Voice-OUT.
- Structured facts, not raw worlds.
- Capability quarantine for all new body parts.
- TDP remains surface hardening.
- Presto becomes the first registered peripheral limb.
- Camera presence is the next likely body slice, but not if it expands into
  recognition/raw frames/memory writes.

---

## Plain English

The body law is right, but it is not ready to stamp yet.

Codex's engineering panel found the practical gaps: define the event envelope,
lock down Jetson transport, timebox presence sensors, make source IDs safe,
define stale/conflict behavior, and name account connectors like Calendar/Gmail
as "information limbs." Claude's OpenHuman review caught the same missing class
from the covenant side.

So the next move is not implementation. The next move is amendment folding.
Once folded, Body Topology can become Decision 24. After that, Maez can safely
grow eyes, ears, information limbs, and eventually voice without accidentally
growing a second self.
