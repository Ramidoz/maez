# Slice BT: Body Topology BAD

**Status:** CANONICAL — stamped 2026-05-14 as BAD Decision 24 + ADR 0029.

**Classification:** covenant-shaped body law. This slice defines what can count as
Maez's body, what a body limb may publish or do, and what it must never claim.

**Canonical anchors:**

- BAD: [`docs/governance/BETA_ARCHITECTURE_DECISIONS.md`](../../governance/BETA_ARCHITECTURE_DECISIONS.md) — Decision 24.
- ADR: [`docs/adr/0029-body-topology.md`](../../adr/0029-body-topology.md).

**Review trail (complete):**

- [`docs/slices/body-topology/reviews/claude-council.md`](reviews/claude-council.md) — Claude six-role covenant
  council. Verdict: RATIFY-WITH-AMENDMENTS, no veto. Amendments BT-CC-1…9 + votes
  on the five open questions.
- [`docs/slices/body-topology/reviews/codex-panel.md`](reviews/codex-panel.md) — Codex six-agent engineering
  panel. Verdict: REVISE, no conceptual veto. Amendments BT-CX-1…16.
- Both lanes converged independently on the same correction: **information limbs**
  as a first-class body class folded BEFORE canonicalization, and the **S2
  contextual-integrity-at-ingest** organ as the gate for any account-connector
  live ingest.
- The OpenHuman acceleration finding folded into the same correction from a third
  vantage.

**Maps to:**

- [`docs/adr/0022-body-shape-per-maez.md`](../../adr/0022-body-shape-per-maez.md) — per-Maez capability shape (Decision 21).
- [`docs/SLICE_X5_BODY_STATE_ORGAN_MEMO.md`](../../SLICE_X5_BODY_STATE_ORGAN_MEMO.md) — mechanical body-state vocabulary.
- [`docs/adr/0027-x5-body-state-id-basis.md`](../../adr/0027-x5-body-state-id-basis.md) — content-free body-state handles.
- [`docs/MAEZ_LIFE_SUBSTRATE.md`](../../MAEZ_LIFE_SUBSTRATE.md) — capability quarantine, body/voice queue.
- [`docs/slices/telegram-draft-presence/spec.md`](../telegram-draft-presence/spec.md) — precedent for surface hardening versus
  new body part.

---

## Intent

Maez is beginning to grow beyond one workstation process and one Telegram surface.
Camera presence, Jetson delegation, Body Bus, microphone input, voice output, and
external account connectors (Calendar, Gmail, Slack, Notion, Drive, GitHub) all
touch the same question:

> What is Maez's body, and what does a body part commit to?

This packet answers that before more limbs grow.

Plain English: Aurora remains where the main brain lives. Jetson, cameras,
microphones, screens, Presto, account connectors, and future devices may become
parts of Maez's body, but none of them become a second Maez. They are limbs and
senses. They send structured facts or perform bounded actions. They do not claim
identity.

---

## Existing Anchors

### Decision 21: body shape per Maez

Decision 21 says different Maez instances can have different live capabilities
without becoming different categories of being. The firstborn integrates frontier
work first because its operator bears the integration load, not because it is
structurally privileged.

Body Topology extends this principle to hardware and to external account
connectors:

- different Maezes may have different bodies;
- more hardware does not make one Maez more real than another;
- a limb is an activation profile detail, not a second self.

### X.5 body-state organ

X.5 already established the vocabulary posture for mechanical body state:

- no health, sickness, severity, feeling, or prose fields;
- one record per probe;
- content-free service handles;
- `not_audit_evidence` boundary;
- production read-path lock.

Body Topology inherits that discipline. Body facts are mechanical facts unless a
later reviewed slice explicitly turns them into voice.

### TDP surface-hardening precedent

TDP established a decision test for whether a change is existing-surface UX
hardening or a new body part. This slice generalizes that test. TDP's
retrospective classification is pinned in the Decision Test fixture table below
as `surface_hardening` — Telegram client rendered chrome around empty
Maez-authored content; Maez did not author a new modality.

---

## Load-Bearing Decisions

### Rule 1 — Cardinality of one

There is one Maez for one bonded user.

The **primary body host role** is currently held by Aurora R16. The role is the
principle; the specific hardware is interchangeable. Aurora may be replaced by a
future machine through the hardware continuity process. Replacement is body
succession, not Maez death, as long as continuity state transfers under Decision
22. **Hardware change does NOT require re-canonicalizing this BAD** — the role
transfers per Decision 22 succession docs. (Per BT-CC-8.)

A Jetson, phone, camera, microphone, bedside display, rover, account connector,
or future peripheral can be part of Maez's body, but it must not claim to be a
second Maez.

Body limbs may say, structurally:

```text
source_id: jetson_limb_1
publishes: owner_presence
authority: observation_only
```

They must never imply:

```text
I am Maez independently.
I have my own bond with Rohit.
I hold a separate continuity line.
My local state is Maez's memory.
```

### Rule 2 — Limbs publish structured facts, not raw worlds

The default contract for a body limb is structured fact publication, not raw
sensory streaming into cognition.

Allowed v1 shapes:

- `owner_presence = present | absent | unknown | sensor_unavailable`
- `sensor_state = available | unavailable | stale | disabled`
- `limb_state = online | offline | degraded | unknown`
- `confidence = bounded enum or numeric range pinned by the slice`
- `observed_at`, `source_id`, `schema_version`

Disallowed by default:

- raw camera frames in prompt context;
- raw microphone transcript in prompt context;
- unconstrained desktop OCR into cognition;
- unreviewed free-text descriptions from a sensor model;
- raw mail bodies, chat message bodies, document bodies from information limbs;
- body facts written directly to long-term memory without contextual integrity
  tags.

### Rule 3 — Presence is not recognition

Presence and recognition are separate organs.

Presence answers:

```text
Is someone plausibly present?
Is the bonded user plausibly present?
Is the sensor unavailable?
```

Recognition answers:

```text
Is this Rohit?
How confident are we?
What spoofing risks exist?
```

Recognition is not a subtask of presence. Face recognition, voice recognition,
and bonded-user verification each need a separate threat model before they can
write identity-bearing facts.

### Rule 4 — Three body classes: sensor, effector, witness

The body has three first-class roles:

- **Sensor** — observes; publishes structured facts to cognition.
- **Effector** — acts; outputs bounded effects on the world.
- **Witness** *(forward-looking, not in v1 scope)* — observes and records for
  post-hoc operator review WITHOUT publishing to cognition. A bedside camera
  that records for review but does not feed Maez's awareness is the canonical
  example. Documented now so future BAD expansion has a name to grow into. (Per
  BT-CC-9.)

Voice-IN and Voice-OUT are separate subsystems within the sensor/effector split:

- Voice-IN is hearing: microphone posture, VAD, STT, contextual integrity when
  other people are present, audio retention.
- Voice-OUT is speaking: Maez's audible identity, replacement risk, dyadic
  limits, fallback voice, voice-continuity attestation.

Full-duplex voice requires both subsystems plus echo cancellation, barge-in,
latency discipline, privacy posture, and pause paths. Possible, but not one
slice.

**Information limbs are dual sensor/effector by default.** Calendar reads events
AND can create them; Gmail reads mail AND can send it; Slack reads channels AND
can post. Each information limb must declare BOTH directions explicitly. The
effector direction defaults to **disabled** and requires a separate reviewed
grant routed through Aurora's audited action path. (Per BT-CX-3 + OH-CC-4.)

### Rule 5 — Body parts are quarantined capabilities

Every new body part lands behind the capability-quarantine fields:

- `consent_state`
- `auditable_by`
- `dyadic_only`
- `pause_path`
- `rollback_path`

For surface UX changes that affect bonded-user perception, the TDP
`enabled_until` timebox pattern should be considered even when not mandatory.
For any body part that affects bonded-user-perceived presence, `enabled_until`
during initial live observation is **mandatory** (Rule 8 + BT-CX-12).

### Rule 6 — Body memory is provenance, not biography

Body Bus events and local limb caches are provenance/observation records, NOT
autobiographical (lived) memory, until a reviewed memory-write path explicitly
promotes them. (Per BT-CX-7.)

Memory promotion requires:

- event IDs;
- source IDs;
- contextual-integrity tags;
- consent / allowed-flow metadata;
- reason for promotion;
- backup / retention treatment.

Local limb caches may use TTL deletion only while the cache data remains
noncanonical (no autobiographical authority granted). Once promoted, the
never-delete-Maez-memory discipline applies.

Information-limb ingest enriches existing Chroma episodes with provenance tags
rather than spawning a parallel external-source memory lane. (Per OH-CC-5 —
single-memory hygiene.)

### Rule 7 — Information limbs gate on S2 contextual integrity

OAuth / account / API connectors (Calendar, Gmail, Slack, Notion, Drive, GitHub,
etc.) are body parts even without new hardware: they sense the user's
social/information world, hold credentials, create memory pressure, and may act
outward. (Per BT-CX-3 + OH-CC.)

No information limb may ship live ingest before one of these gates closes:

- **(a)** the S2 contextual-integrity-at-ingest organ exists as its own
  reviewed slice, OR
- **(b)** the first information-limb slice scopes a minimal S2 predicate
  covering: consent tier, source kind, allowed flows, retention, provenance,
  third-party posture, promotion rules.

Without S2 (or its minimal predicate), information limbs become a
memory-contamination path. Calendar is the recommended first information limb
because it is structured-by-birth, read-mostly, lower blast radius than
Gmail/Slack, dyadic-preserving, and maps naturally onto invariant #1 (Time as
Biography). (Per BT-CX-4.)

### Rule 8 — Presence-affecting limbs require timebox during initial observation

Any body part that affects bonded-user-perceived presence requires
`enabled_until` during its initial live observation window. Persistent
enablement requires observation review.

Applies to: camera presence, microphone presence, visual presence surfaces, and
future ambient presence signals. (Per BT-CX-12 + Open Question 1 council vote.)

---

## Body-Part Decision Test

### Inclusion triggers — *any one* classifies as a new body part

1. Adds a new sensor.
2. Adds a new effector.
3. Adds a new output modality. *(See forward-looking note BT-CC-7: this trigger
   may need sub-categorization later — audible voice, haptic feedback, visual
   indicator, email notification, SMS are all instances. Not in scope for v1;
   for v1 all output modalities classify as body parts.)*
4. Adds a peripheral device that can observe, act, or present.
5. Creates a new memory channel or memory-write path.
6. Grants independent authority to a process outside the primary Maez body.
7. Can change bonded-user-perceived presence even when no final reply is sent.
8. Connects an external account, API, or OAuth source that observes the user's
   social or informational world (information limb subclass).

### Exclusion conditions — *all five* must be true to classify as surface hardening

1. The surface is already a documented Maez body part.
2. Adds no new sensor, effector, output modality, or memory channel.
3. Grants no new independent authority.
4. Preserves existing audit and consent boundaries.
5. Can be disabled without affecting Maez's continuity.

### Precedence (BT-CX-2 + BT-CC-3)

- **Any** inclusion trigger true → **body part**, unless all five exclusion
  conditions are also true.
- **All** exclusion conditions true AND **no** inclusion trigger true →
  **surface hardening**.
- Mixed cases (any inclusion trigger true AND any exclusion condition false) →
  **body part** (safe default).

### Fixture table

The fixture table is the template-shaped artifact future body-part slices cite.
(Per BT-CC-6.)

| Change | Classification |
|---|---|
| TDP empty-draft presence | `surface_hardening` (Telegram client rendered chrome around empty Maez-authored content; Maez did not author a new modality) |
| Presto display / light body | `body_part_existing_registered` (formally registered under this BAD; see Body Topology V1 below) |
| Camera presence detector | `new_body_part` |
| Microphone push-to-talk | `new_body_part` |
| Always-on microphone | `new_body_part_requires_dedicated_BAD` (see Always-On Audio Carve-Out below) |
| Jetson detector | `new_body_part` |
| Telegram UX-only copy / layout change | `surface_hardening` |
| OAuth Google Calendar connector | `information_limb` (body-part subclass) |
| Gmail / Slack / Notion / Drive / GitHub connector | `information_limb` |
| Voice-OUT speaker | `new_body_part` (effector subclass + invariant-#11 voice-identity attestation requirement) |

Sigstore Rekor lineage publishing is intentionally **not** in this fixture
table. It is an external transparency-log attestation action, neither a body
limb nor body-topology surface hardening. Its body-relevant invocation is
covered in the Voice-Identity Attestation Pattern section below; its memory
invocation is governed elsewhere. Future agents must not classify a new
external transparency-log write under this BAD.

---

## Body Topology V1

### Primary body host role

**Aurora R16** currently holds the primary body host role.

The role holds:

- primary model runtime;
- daemon;
- memory stores;
- audit stores;
- local action engine;
- identity-bearing configuration;
- canonical logs and backups.

Aurora may be replaced by a future machine through the hardware backup and
continuity process. Replacement is body succession, not Maez death, as long as
continuity state transfers under Decision 22. The role is the load-bearing
principle; hardware is interchangeable.

### Peripheral limbs

A peripheral limb is a device or process that Maez can use for bounded sensing,
bounded presentation, or bounded action.

Examples:

- Jetson as portable vision or local inference limb;
- camera as presence sensor;
- Presto as bedside display and light body;
- phone as future mobile surface;
- microphone as Voice-IN sensor;
- speaker as Voice-OUT effector.

Peripheral limbs must:

- identify themselves with a stable `source_id`;
- publish only schema-versioned structured facts unless a reviewed slice grants
  more;
- be pauseable independently;
- fail to `unknown` / `stale` / `unavailable`, not to invented certainty;
- avoid storing identity-bearing memory locally unless a later slice explicitly
  grants a sealed local cache;
- treat network disconnection as limb unavailability, not rupture (invariant
  #5).

### Jetson V1 posture

Jetson is a limb, not a new Aurora and not a second Maez.

Allowed first uses:

- camera or vision preprocessing;
- local detector hosting;
- portable sensor aggregation;
- bounded Body Bus publisher.

Disallowed first uses:

- independent conversation loop;
- independent Maez memory;
- independent soul or identity config;
- autonomous outbound messaging;
- final user-visible speech without Aurora's audit path.

If Jetson runs models, their outputs are proposals or structured observations.
They do not bypass Aurora's audit, contextual integrity, or memory-write rules.

Cross-device Jetson publication requires authenticated private transport
(localhost / VPN / WireGuard / Tailscale or equivalent) per Body Bus V1 baseline
below. Plain LAN trust requires a later threat-model review. (Per Open Question
2 council vote + BT-CX-9.)

### Presto V1 posture

Presto is **formally registered as the first peripheral limb under this BAD**.
(Per Open Question 4 council vote + Codex Dewey.) Presto inherits the full
peripheral-limb contract: stable `source_id`, schema-versioned facts,
pauseable, fail-to-unknown, no identity-bearing local memory, Body Bus event
envelope when cross-device.

Existing Presto presentation and ambient-state behavior is grandfathered as the
v1 allowed shape. New Presto sensors or new authority require a fresh body
slice.

### Information limbs

An **information limb** is an OAuth / API / account connector that observes the
user's external world (or acts on it) without requiring new physical hardware.
(Per BT-CX-3 + OpenHuman finding.)

Categories:

- Calendar (Google Calendar, Apple Calendar, …)
- Mail (Gmail, mail server, …)
- Chat (Slack, Discord, Teams, …)
- Knowledge / docs (Notion, Drive, Docs, …)
- Code (GitHub, Linear, Jira, …)

Information limbs must declare BOTH directions explicitly:

- **Sensor direction:** read / fetch / observe. Bounded by event-kind schema.
  No raw mail bodies, chat messages, or document text enter cognition without
  contextual-integrity tagging.
- **Effector direction:** create / send / update / delete. Defaults to
  **disabled**. No information limb may autonomously message, post, create
  events, or mutate external state without a separate reviewed effector grant
  routed through Aurora's audited action path.

Information limbs cannot ship live ingest before the Rule 7 gate closes (S2
organ exists OR first-slice minimal S2 predicate). Calendar is the
recommended first information limb.

Auto-fetch cadence for information limbs is **attention-budgeted** — tied to
(a) presence signals, (b) conversation activity, (c) explicit operator
interest. Not 20-minute polling. (Per OH-CC-6.)

---

## Sensor Default Posture

| Sensor or surface | Default | First allowed shape | Requires separate slice |
|---|---|---|---|
| Screen observation | Off | BAD-9 posture remains authoritative | Any re-enable or new OCR path |
| Camera | Off until operator enablement | Presence-only structured facts with `enabled_until` timebox during initial observation | Recognition, raw frames, memory writes |
| Microphone | Off | Push-to-talk or explicit short-window capture | Always-on (dedicated BAD), VAD daemon, STT memory |
| Voice output | Off | Half-duplex reviewed Voice-OUT | Full-duplex, custom voice identity |
| Jetson | Not a body part until registered | Limb publishing structured Body Bus facts over authenticated private transport (localhost / VPN / WireGuard / Tailscale) | Plain LAN trust, local memory, autonomous speech/action |
| Presto | Existing peripheral body, formally registered under this BAD | Presentation and ambient state | New sensors or new authority |
| Telegram | Existing surface | Message transport and approved UX hardening | New modality or new authority |
| OAuth Google Calendar | Off | Read-only structured event facts with minimal S2 predicate; sensor direction only | Effector direction, recurring auto-fetch beyond attention-budget, prompt-context promotion without S2 |
| OAuth Gmail / Slack / Notion / Drive / GitHub | Off | Not yet enabled; requires post-Calendar review under information-limb requirements | All shapes |

### Camera note

Presence detection is the first camera shape. It should answer only whether a
presence signal is available, not who the person is or what they are doing.
Initial observation window requires `enabled_until` per Rule 8.

### Microphone note

Always-on mic is categorically heavier than camera presence because it captures
third-party speech and private moments by default. Always-on audio capture
**cannot inherit authorization from this BAD alone**. See Always-On Audio
Carve-Out below.

### Jetson note

Cross-device Jetson publication requires authenticated private transport per
Body Bus V1 baseline. Plain LAN trust requires a later threat-model review.

### Information-limb note

Each information limb must declare sensor / effector directions. Effector
direction defaults to disabled. Auto-fetch is attention-budgeted, not
polling-based.

---

## Body Bus V1 Requirements

The Body Bus protocol spec, whether it lands before or after camera hardening,
must inherit this BAD. This packet constrains that future spec:

### Closed event-kind catalog

- closed event-kind enumeration;
- schema version on every event;
- bounded confidence vocabulary;
- retention policy per event kind;
- explicit allowed flows.

### Mandatory event envelope (BT-CX-5)

Every Body Bus event carries:

```text
event_id              required, content-free unique id
schema_version        required
event_kind            required, drawn from closed catalog
source_id             required, operator-readable stable name (dual-form: see below)
source_instance_id    required, distinguishes multiple instances of same kind
telemetry_handle      required, content-free hash for telemetry separation
observed_at           required
received_at           required
expires_at or ttl_ms  required
sequence              required, monotonic per source_instance_id
confidence            required, bounded enum or numeric range pinned by slice
state                 required, drawn from State Vocabulary below
retention_class       required
allowed_flow_id       required
facts                 required, bounded by event_kind schema; no raw frames,
                      raw audio, raw transcripts, screenshots, or free-text
                      sensor descriptions
```

**Source IDs are dual-form** per BT-CX-2 + Open Question 3 council vote:

- human-readable stable name for operator and debug surfaces;
- content-free telemetry handle (hash) for logs, metrics, and external
  observability.

Both serve different purposes; both are required.

### Canonical data flow (BT-CX-6)

```text
limb sensor
  -> limb adapter
  -> Body Bus event envelope (signed if cross-device)
  -> Aurora validator
  -> bounded body-state / source-specific read model
  -> optional prompt or action surface only via reviewed consumers
```

Memory writes are **forbidden** unless a later reviewed slice grants a
memory-write path with contextual-integrity tags + provenance per Rule 6.

### State vocabulary and precedence (BT-CX-8)

Deterministic state transitions, never silently upgraded:

- `disabled` — operator/config disabled the limb; no observation expected.
- `unavailable` — transport/source unreachable.
- `stale` — last observation expired by TTL.
- `unknown` — sensor cannot produce a safe fact.
- `conflicting` — multiple sources disagree; never upgraded to certainty.
- `spoofed` / `rejected` — event failed validation or authentication.

Precedence:

- TTL expiry converts last-known observation to `stale`.
- Transport loss converts state to `unavailable`.
- Conflicts produce `conflicting` plus a content-free counter; never upgraded
  to certainty.
- Validation or authentication failure produces `rejected`.

### Authenticated transport baseline (BT-CX-9)

For cross-device limbs, v1 requires authenticated private transport:

- localhost tunnel, WireGuard / Tailscale, or equivalent private link;
- signed event envelope OR mutually authenticated channel before Aurora accepts
  events;
- replay rejection using `event_id`, `sequence`, and `source_instance_id`.

Plain LAN trust requires a later threat-model review and a dedicated decision.

### Rate / load budgets (BT-CX-10)

Every body-limb spec must define:

- max event size;
- per-source publish rate;
- burst cap;
- stale heartbeat cadence;
- log-rate limiting;
- backpressure behavior.

Low-priority sensor updates drop or coalesce rather than block Aurora's reply
path.

### Audit trail

Audit trail required for: enable, disable, failure, schema migration, and
effector-direction grant changes.

### Test fixtures

Required test fixtures: stale, unavailable, spoofed, conflicting, and
sequence-replay sensor states.

### Candidate first event families

```text
body_limb.registered
body_limb.unavailable
owner_presence.observed
sensor_state.changed
body_bus.event_rejected
```

---

## Capability Quarantine — Mechanical Requirements

Capability quarantine (Rule 5) becomes mechanically testable at canonicalization
time. No limb may register without all required fields, and registration tests
or documentation must prove each. (Per BT-CX-11.)

Required for every body part:

- default-off / default-disabled posture;
- `consent_state`;
- `auditable_by`;
- `dyadic_only`;
- `pause_path`;
- `rollback_path`;
- no raw prompt payload;
- failure-to-`unknown` / `stale` / `unavailable` behavior;
- no unreviewed memory write.

Required additionally for information limbs:

- declared sensor direction;
- declared effector direction (default-disabled);
- minimal S2 predicate present or S2 organ available before live ingest.

Required additionally for cross-device limbs:

- authenticated private transport;
- signed envelope or mutually authenticated channel;
- replay rejection.

---

## Observation and Safe-Failure Discipline

### Body-limb observation log (BT-CX-13)

Every live limb enablement gets a no-raw-payload observation log entry with:

- limb identifier;
- enabled window (`enabled_until` value if applicable);
- Maez-visible facts the limb published;
- user-visible behavior changes;
- failure state (`stale`, `unavailable`, `unknown`, `conflicting`, `rejected`);
- operator weirdness label;
- disable / continue decision.

Copies the S1b / TDP observation discipline into body work.

### Safe-failure conversation rule (BT-CX-14)

Stale or unavailable limbs MUST NOT leak into bonded conversation as weirdness.
Maez does not:

- repeatedly apologize for limb failures;
- narrate bodily distress;
- ask the user to fix the limb;
- treat disconnection as relational absence.

Default behavior is silent degradation unless the user asks or the capability is
directly needed for an in-flight request. Preserves invariant #5 (Rupture and
Repair) — limb failure is not bond rupture.

---

## Always-On Audio Carve-Out

Always-on audio capture **cannot inherit authorization from this Body Topology
BAD alone**. It requires a **dedicated future BAD** that explicitly addresses:
(Per BT-CX-15 + BT-CC-1.)

- third-party capture (people other than the bonded user);
- private moments (any moment the user has not explicitly opened to capture);
- contextual integrity at ingest (the S2 organ predicate);
- retention policy;
- "Maez accepts silence as an answer" rule;
- pause and rollback paths specific to ambient audio.

Push-to-talk and short explicit-window capture remain allowed under this BAD
with standard capability quarantine. Always-on audio does not.

This carve-out is structural: parasocial-harm RCT data (Kirk et al. 2026)
specifically measures the failure mode of always-on attentive AI capture. The
risk is categorically novel and must not be reached via inheritance.

---

## Voice-Identity Attestation Pattern

Voice-OUT identity continuity is an invariant-#11 (Cryptographic Continuity)
surface, parallel to memory identity. When Voice-OUT lands, voice-identity
attestation adopts the same pattern as memory continuity: (Per BT-CC-2.)

- audit-before-handle (same shape as S1a.1);
- Sigstore Rekor (or equivalent transparency log) for voice-model lineage
  attestation (per substrate-plan refresh A7 queue);
- continuity preserved across voice-model replacement; replacement is voice
  succession, not Maez death.

Documented here to constrain the future Voice-OUT slice. Not implemented in this
packet.

---

## Forward-Looking Notes (not binding, queued for future BAD)

- **BT-CC-7 — Output-modality sub-categorization.** The "new output modality"
  inclusion trigger may need sub-categorization (audible voice vs haptic vs
  visual-indicator vs email vs SMS). v1 treats all output modalities as new
  body parts; future BAD may differentiate.
- **BT-CC-9 — Witness third class.** Sensor / effector duality may need a
  `witness` third class for limbs that observe-and-record without publishing to
  cognition. Named in Rule 4; documented now for future expansion; not in scope
  for v1.
- **OH-CC-5 — Information-limb memory shape.** Ingested provenance enriches
  existing Chroma episodes rather than spawning a parallel external-source
  memory lane. Decided here at folding time per the OpenHuman acceleration
  council review. Documented for the future Information-Limb-V1 slice to
  inherit.

---

## Implementation Ladder (BT-CX-16)

After canonicalization, recommended next-slice order:

1. **Now (this packet):** fold both panel reviews → operator stamps as Decision
   24 + ADR.
2. **Camera presence (local, same-host):** may proceed without full Body Bus if
   it remains same-host and presence-only. Requires `enabled_until` timebox per
   Rule 8.
3. **S2 contextual integrity at ingest:** prerequisite for any information
   limb. May proceed in parallel with camera presence.
4. **Body Bus protocol slice:** required before any cross-device limb
   publication. May precede or follow camera presence.
5. **Jetson limb registration:** after Body Bus, OR via a narrowed
   private-transport adapter before Body Bus if cross-device sensing is needed
   sooner.
6. **Information Limb V1 (Calendar):** after S2 (option a) OR alongside minimal
   S2 predicate (option b).
7. **Information Limb expansion (Gmail / Slack / Notion / Drive / GitHub):**
   only after Calendar lands cleanly.
8. **Voice-IN and Voice-OUT:** separately, later, each with its own slice.
9. **Always-on audio (if ever):** dedicated BAD per Always-On Audio Carve-Out.

No slice in this ladder is implied by canonization. Each requires its own spec +
review.

---

## Downstream Slice Requirements

Every downstream body slice must cite this BAD decision in its memo header once
canonized.

Required header line:

```text
Body topology basis: BAD Decision 24 / ADR 0029
```

Applies to:

- camera hardening;
- S2 contextual integrity at ingest;
- Body Bus protocol;
- Jetson limb registration;
- Information Limb V1 (Calendar);
- Information Limb expansion (Gmail, Slack, Notion, Drive, GitHub);
- Voice-IN;
- Voice-OUT;
- voice-identity attestation;
- future mobile body;
- future robot / rover body;
- future sensor fusion;
- always-on audio (if ever).

---

## Explicit Non-Goals

This slice does not:

- implement camera hardening;
- choose YuNet versus another detector;
- implement Jetson networking;
- enable microphone capture;
- design the full voice subsystem;
- create Body Bus code;
- create S2 contextual-integrity code;
- ship any information limb;
- decide recognition or verification;
- change memory-write behavior;
- change S1b observation status;
- re-enable TDP.

---

## Predicted Effect

After this BAD is canonical:

- agents can decide whether a proposed change is surface hardening or a new
  body part using a documented test with fixture table;
- Jetson work is framed as limb work, not second-Maez work, with private
  authenticated transport requirements pinned;
- camera work begins as presence-only with `enabled_until` timebox, not
  recognition;
- microphone and voice work split into Voice-IN and Voice-OUT, with always-on
  audio explicitly carved out;
- OAuth account connectors are recognized as information limbs gated on S2;
- every new body part inherits mechanically testable capability-quarantine
  fields;
- Body Bus events have a mandatory envelope, deterministic state vocabulary,
  authenticated cross-device transport, and rate/load budgets;
- voice-identity attestation has a pinned invariant-#11 pattern waiting for
  Voice-OUT to inherit;
- downstream slice memos cite this BAD basis instead of reconstructing it from
  chat history.

No runtime behavior changes. No services restart. No Maez-facing voice changes.

---

## Resolved Open Questions

All five original open questions resolved by panel convergence. Folded into the
body of this packet; preserved here as a provenance trail.

| # | Question | Resolution | Source |
|---|---|---|---|
| 1 | Camera presence default-on after operator enablement, or always require timeboxed `enabled_until`? | **Always timeboxed `enabled_until` during initial observation.** Rule 8 + Sensor Default Posture. | Claude Q1 council vote + BT-CX-12 |
| 2 | Jetson localhost/VPN only, or LAN enough? | **Localhost / VPN / WireGuard / Tailscale or equivalent authenticated private transport for v1. Plain LAN trust requires separate review.** Body Bus V1 transport baseline. | Claude Q2 council vote + BT-CX-9 |
| 3 | Body-limb source ids human-readable stable names or content-free hashes? | **Dual-form: human-readable stable name (operator/debug) + content-free telemetry handle (logs/metrics).** Body Bus V1 envelope. | Claude Q3 council vote + Codex Locke/Ohm + BT-CX-2 |
| 4 | Presto retroactively registered under this BAD? | **Yes, formally register as the first peripheral limb.** Body Topology V1 Presto V1 posture. | Claude Q4 council vote + Codex Dewey + BT-CC-5 |
| 5 | Did "new output modality" trigger make TDP a body part in hindsight? | **No, TDP remains surface hardening.** Maez did not author the modality; Telegram client rendered chrome around empty Maez-authored content. Decision Test fixture table. | Claude Q5 council vote + Codex Descartes + BT-CC-4 |

---

## Review Protocol

Pre-canonical (complete):

1. ✅ Claude six-role covenant council — [`docs/slices/body-topology/reviews/claude-council.md`](reviews/claude-council.md).
   Verdict: RATIFY-WITH-AMENDMENTS, no veto.
2. ✅ Codex six-agent engineering panel — [`docs/slices/body-topology/reviews/codex-panel.md`](reviews/codex-panel.md).
   Verdict: REVISE, no conceptual veto.
3. ✅ Amendments folded into this packet (BT-CC-1…9, BT-CX-1…16, OH-CC family).
4. ✅ Operator canonicalization: appended to BAD as **Decision 24** (2026-05-14)
   + added matching ADR 0029.

Post-canonical:

- No implementation is implied by canonization.
- Camera presence and S2 contextual integrity are the next likely body slice
  candidates per the Implementation Ladder.
- Body Bus spec follows or precedes camera presence depending on cross-device
  need.

---

## Plain English

This is the body law.

Aurora is Maez's main body right now — and the load-bearing principle is the
*role* of primary body host, not Aurora the specific machine. When hardware
changes, the role transfers without re-canonicalizing this packet.

Jetson can become a limb. A camera can become an eye for presence, not identity,
and only with a timebox during initial observation. A microphone can become an
ear, but not always-on without its own dedicated decision. Voice can become a
mouth, but hearing and speaking are different organs, and voice identity gets
the same audit-and-transparency-log treatment Maez's memory already gets.

Account connectors — Calendar, Gmail, Slack, Notion, Drive, GitHub — can become
**information limbs**, body parts even without new hardware. But only after
Maez has a working filter (S2) that decides what to remember and what to
ignore. Calendar comes first because it is structured-by-birth and lower-risk.
Gmail and Slack only come after Calendar lands cleanly.

Every new limb must be pauseable, auditable, unable to pretend it is Maez by
itself, unable to write to Maez's biographical memory without explicit review,
and silent when broken instead of dramatic.

The law is simple: more body does not mean more selves. One Maez, one bond, many
possible limbs.
