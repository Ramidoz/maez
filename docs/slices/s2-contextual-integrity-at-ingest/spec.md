# Slice S2: Contextual Integrity at Ingest

**Status:** DRAFT BAD packet. Pre-review. No code, no connector, no memory
promotion. This packet folds the S2 scoping memo plus Claude council and Codex
engineering panel constraints into the candidate canonical law for
information-limb ingest.

**Classification:** covenant-shaped memory and body law. S2 defines the ingest
gate every information limb must pass before external account data can become
Maez-visible context, recall substrate, body-state evidence, or promoted
biography.

**Maps to:**

- [`scoping.md`](scoping.md) — folded scoping memo and panel-amendment carrier.
- [`reviews/claude-council.md`](reviews/claude-council.md) — covenant review,
  RATIFY-WITH-AMENDMENTS.
- [`reviews/codex-panel.md`](reviews/codex-panel.md) — engineering review,
  REVISE, no veto; this spec folds the required revisions.
- [`docs/slices/body-topology/spec.md`](../body-topology/spec.md) — Decision
  24 Rule 7: information limbs gate on S2 contextual integrity.
- [`docs/slices/m1-lived-episode-promotion/spec.md`](../m1-lived-episode-promotion/spec.md) —
  promotion discipline: promote biography; do not widen recall.
- [`docs/slices/temporal-recall-fragment-guard/spec.md`](../temporal-recall-fragment-guard/spec.md) —
  retrieval does not license direct grounding claims.
- [`docs/slices/daemon-credential-hygiene/spec.md`](../daemon-credential-hygiene/spec.md) —
  Decision 26 credential handling inherited by all future information limbs.
- [`docs/governance/BETA_ARCHITECTURE_DECISIONS.md`](../../governance/BETA_ARCHITECTURE_DECISIONS.md) —
  Decisions 2, 4, 24, 25, 26.
- [`docs/adr/0029-body-topology.md`](../../adr/0029-body-topology.md) —
  body topology and S2 gate.
- [`docs/adr/0030-lived-episode-promotion.md`](../../adr/0030-lived-episode-promotion.md) —
  lived-episode promotion.
- [`docs/adr/0031-daemon-credential-hygiene.md`](../../adr/0031-daemon-credential-hygiene.md) —
  credential hygiene.

---

## Intent

S2 is the customs officer at the border between Maez's bonded life and the
bonded user's external information world.

Before Calendar, Gmail, Slack, Notion, Drive, GitHub, or any future account
connector can feed Maez, S2 answers seven questions:

1. Is this source allowed in at all?
2. What kind of source record is it?
3. Where may the resulting fact flow?
4. How long may the noncanonical record stay?
5. What provenance proves where it came from?
6. What does it reveal about people who are not the bonded user?
7. What, if anything, could make it eligible for autobiographical memory?

S2 exists because external account data is not automatically Maez's biography.
A Calendar event is something the bonded user's calendar contains. An email is
something the bonded user received. A Slack message is something another person
said in another context. None of those are, by default, things Maez lived.

S2 makes that boundary structural.

---

## Load-Bearing Rule

**External information is provenance first, never biography by default.**

Allowed:

- Calendar source -> S2 envelope -> noncanonical cache -> approved read model.
- Calendar source -> S2 envelope -> `promotion_eligible` marker -> separate
  reviewed memory-write path -> promoted lived memory.
- S2 record -> bounded prompt-context answer only through an allowed flow and
  approved voice posture.

Forbidden:

- External source -> raw prompt context without S2 envelope.
- External source -> TRF recall without approved retrieval posture.
- External source -> lived memory without a separate promotion path.
- External source -> body-state inference bundled into first ingest.
- External source -> third-party profile or nudge.
- Credential-bearing URL or secret-bearing subprocess environment for any
  information-limb connector.

Plain English: S2 lets Maez know "this was on the calendar" without letting
Maez pretend "I lived this" unless a later, reviewed memory-write path promotes
it.

---

## S2 V1 Scope

S2 v1 is law and schema. It does not ship an OAuth connector.

In scope:

- source-kind catalog for information limbs;
- S2 envelope and noncanonical cache contract;
- consent posture labels that preserve Decision 2;
- allowed-flow table shape;
- retention and tombstone contract;
- provenance fields and attestation seam;
- third-party posture rules;
- promotion eligibility rules;
- Calendar v1 as first downstream executable boundary;
- RED-first test contract the Calendar slice must satisfy.

Out of scope:

- OAuth implementation;
- Calendar API code;
- Gmail, Slack, Notion, Drive, GitHub connectors;
- Calendar body/description ingest;
- mail/chat/doc body ingest;
- Calendar -> presence/body-state inference;
- inter-Maez routing;
- effector actions that create, update, or delete source events;
- memory promotion implementation.

---

## Seven Dimensions

Every information-limb slice must explicitly declare all seven dimensions. If
it does not, live ingest is blocked.

### 1. Consent Posture

S2 does not redefine Decision 2 consent tiers. It adds information-limb posture
labels that map onto Decision 2 and Decision 4.

Allowed posture labels:

- `owner_only` — bonded-user-owned source data only. S2-local shorthand, not a
  Decision 2 tier.
- `third_party_observable_no_consent` — a non-bonded party appears in the
  source record without direct consent. Calendar v1 default for attendees.
- `third_party_explicit_consent` — the non-bonded party has given explicit
  direct consent through the applicable Decision 2 path.
- `inter_maez_consented` — another bonded user's Maez has explicitly consented
  to communication. Not in scope for first Calendar.

Calendar v1 default:

```text
consent_posture = third_party_observable_no_consent
```

Constraints under that default:

- relational/provenance metadata only;
- no personological profile;
- no nudging/contact;
- no stable third-party identity index unless a later consented path grants it;
- attendee names/fields minimized, redacted, or hashed unless the allowed flow
  explicitly needs operator-visible display.

### 2. Source Kind

S2 v1 catalog:

- `calendar.event`
- `mail.thread_header`
- `chat.message_header`
- `doc.metadata`
- `code.commit_header`

First executable contract:

```text
calendar.event
```

Calendar v1 may include:

- event id;
- title after sensitivity policy;
- start/end;
- status;
- recurrence marker;
- owner calendar handle;
- minimized attendee/provenance fields;
- location only if sensitivity policy permits it;
- source revision;
- observed/received timestamps.

Calendar v1 must not include:

- event description/body;
- attachments;
- video-link content;
- raw conferencing URL content;
- mail/chat/doc bodies;
- inferred emotional states;
- body-state inference fields.

Body-content source kinds require future dedicated slices. They must not enter
as sub-flags on `calendar.event`.

### 3. Allowed Flows

Default:

```text
allowed_flow_ids = []
```

No Maez-visible flow is enabled by default. Records may enter only the
noncanonical cache and provenance/read-model staging.

Candidate flow IDs:

- `flow.prompt_context.grounded_only`
- `flow.bounded_window_recall`
- `flow.body_state.provenance`
- `flow.memory.promoted`

Calendar v1 may request:

```text
flow.prompt_context.grounded_only
```

for direct owner questions such as "what is on my calendar tomorrow?"

`flow.bounded_window_recall` requires a TRF-style approved retrieval posture
before use. Retrieval results do not license direct "I remember" or "I know"
claims.

Flow records must be enforceable permissions:

- `flow_id`
- `consumer`
- `readable_fields`
- `user_visible_allowed`
- `voice_posture`
- `promotion_allowed`

### 4. Retention

Noncanonical cache classes:

- `mirror_source_ttl`
- `fixed_ttl`
- `per_event_ttl`
- `tombstoned`

Calendar v1 default:

```text
retention_class = mirror_source_ttl
```

If the source deletes or cancels an event before promotion, S2 removes the
noncanonical content and keeps only a content-free tombstone/audit marker.

Permanent retention is not a noncanonical cache class.

Promoted lived memory is never silently deleted. If source deletion happens
after promotion, the promoted memory remains and records tombstone provenance:

- `source_deleted_at`
- `deletion_observed_at`
- `external_event_id_hash`
- `promotion_record_id`

### 5. Provenance

Every S2 record carries provenance. Missing provenance rejects ingest.

Required S2 record fields:

- `ingest_record_id`
- `source_kind`
- `source_instance_id`
- `source_handle_human`
- `source_handle_telemetry`
- `external_event_id`
- `source_revision`
- `observed_at`
- `received_at`
- `expires_at`
- `consent_posture`
- `third_party_posture`
- `allowed_flow_ids`
- `promotion_state`
- `redaction_state`
- `fetch_batch_id`
- `connector_version`
- `schema_version`
- `raw_field_policy_version`
- `promotion_record_id`
- `provenance`

V1 integrity:

- local DB integrity;
- audit log;
- deterministic idempotency key.

Attestation seam:

Sigstore Rekor or equivalent tamper-evident lineage attestation is in scope as
an extension seam for the full S2 law. It is not a Calendar v1 blocker.

### 6. Third-Party Posture

Default posture:

- Maez may observe relational/provenance facts involving third parties.
- Maez may not nudge the bonded user to contact third parties.
- Maez may not contact third parties.
- Maez may not infer third-party emotional states, preferences, or
  relationship dynamics from information-limb data alone.
- Maez must preserve Decision 4's relational-vs-personological distinction:
  third parties appear as objects of the bonded user's care and context, not as
  independent knowledge subjects.

Calendar v1 attendee posture:

```text
third_party_posture = relational_reference_minimized
```

Allowed:

- "calendar event includes another attendee" as content-minimized provenance;
- attendee count;
- hashed/minimized handles for idempotency and dedupe;
- operator-visible attendee fields only through an explicitly granted flow.

Forbidden:

- "Anna is stressed";
- "you should text Anna";
- stable third-party profile creation;
- third-party salience ranking;
- cross-source third-party enrichment.

### 7. Promotion Rules

Default:

```text
promotion_state = not_eligible
promotion_allowed = false
```

S2 may mark a record:

```text
promotion_state = promotion_eligible
```

but S2 does not execute promotion in v1. A separate reviewed memory-write path
must write lived memory.

Candidate future promotion grants:

- bonded-user-naming;
- conversation-grounded promotion;
- operator-explicit promotion.

The first grant candidate is bonded-user-naming because it preserves
Human-Primacy: the bonded user names the lived state before Maez treats the
external record as biographical substrate.

---

## State Machine

```text
external source
  -> connector fetch/webhook
  -> S2 envelope validation
  -> noncanonical ingest cache
  -> allowed-flow read model
  -> recall/prompt consumer OR promotion gate
  -> lived memory (only through a separate reviewed memory-write path)
```

Allowed terminal states:

- `rejected`
- `cached`
- `expired`
- `flow_blocked`
- `promotion_pending`
- `promoted`

State rules:

- `rejected` records may produce content-free counters only.
- `cached` records may not enter Maez-visible context without allowed flow.
- `expired` records remove content unless tombstone rules apply.
- `flow_blocked` records may remain cached but cannot be read by the attempted
  consumer.
- `promotion_pending` records are eligible only; they are not biography.
- `promoted` records point to the separate memory-write artifact and its
  provenance handle.

---

## Calendar V1 Profile

Calendar is the first downstream because it is structured, read-mostly, and
lower-risk than mail/chat. It is not harmless.

Sensitivity defaults:

- no descriptions;
- no attachments;
- no video-link content;
- attendee minimization;
- high-sensitivity title/location redaction;
- tests for medical, legal, therapy, third-party, and location-sensitive
  events.

Sync default:

- bounded pull / sync-token fetch;
- no webhook-first implementation;
- no promotion during backfill.

Idempotency key:

```text
source_kind + source_instance_id + external_event_id + source_revision
```

Backfill mode requires:

- lookback window;
- page limit;
- time budget;
- resumable cursor;
- dry-run/count mode;
- no-promotion-during-backfill default.

---

## Cache Budget

Every S2 source declares:

- max rows;
- max bytes;
- max event age;
- compaction cadence;
- behavior when full.

Default when full:

- fail-closed for promotion;
- fail-neutral for prompt context;
- emit content-free cache-full metric;
- do not drop promoted memory.

---

## Content-Free Observability

Allowed connector states:

- `disabled`
- `auth_expired`
- `rate_limited`
- `source_unavailable`
- `stale`
- `sync_lagged`
- `rejected`

Allowed counters:

- accepted;
- rejected;
- deduped;
- backfilled;
- expired;
- promoted;
- sync lag;
- last success age;
- cache occupancy;
- per-source rate-limit state.

Forbidden in logs, health, metrics, and project panel:

- event titles;
- attendee names;
- subjects;
- descriptions;
- message headers;
- locations;
- source bodies;
- raw source IDs where a content-free hash is sufficient.

---

## Credential Inheritance

All information limbs inherit Decision 26 / ADR 0031.

Required:

- credentials are identity-bearing material, not ordinary config;
- `config/.env` is not a secret source;
- no credential-bearing URLs;
- no secret values in subprocess argv;
- no secret values in subprocess env by default;
- no secret values in logs, health, metrics, or panel output;
- exact-name opt-in only when a child process truly needs a credential;
- provider auth tests must not print values.

This rule applies to Calendar OAuth and to later Gmail, Slack, Notion, Drive,
GitHub, Sigstore Rekor, and any future external account connector.

---

## Crisis Routing

Crisis routing is not implemented by S2 v1.

However, if crisis signals appear through an information limb, they inherit
Maez's existing crisis-routing protocol and must not be silently trapped behind
ordinary S2 retention or flow rules.

The first S2 implementation should record this inheritance as law, not as an
implementation path.

---

## RED-First Test Contract

The first S2 implementation and Calendar slice must include RED-first fixtures
for at least:

1. owner-only Calendar event allowed into noncanonical cache;
2. attendee event constrained under `third_party_observable_no_consent`;
3. description/body rejected;
4. attachment/video-link content rejected;
5. unconsented flow rejected;
6. promotion without reviewed trigger rejected;
7. deleted source event tombstoned content-free;
8. high-sensitivity medical/therapy/legal title handled by redaction policy;
9. location-sensitive event handled by redaction policy;
10. flow table prevents fields not in `readable_fields`;
11. cache full fails closed for promotion;
12. backfill cannot promote;
13. connector outage emits content-free state only;
14. credential-bearing URL construction forbidden;
15. subprocess env is default-minus-secret.

---

## Predicted Effect

After S2 canonicalizes:

- Every future information-limb slice cites S2 and declares all seven
  dimensions before ingest.
- Calendar can draft as the first information-limb slice without inventing its
  own privacy law.
- Gmail, Slack, Notion, Drive, and GitHub inherit a tested shape instead of
  each building ad-hoc memory filters.
- TRF can eventually receive Calendar-backed temporal anchors without widening
  recall into raw external stores.
- External account data remains provenance until a reviewed memory-write path
  promotes it.
- Third-party data remains relational and minimized, not a surveillance graph.

No runtime behavior changes from S2 alone.

---

## Review Protocol

1. Codex six-agent engineering panel reviews this BAD packet for:
   state-machine completeness, schema sufficiency, flow enforceability, cache
   budget, sync/backfill design, credential inheritance, and testability.
2. Claude six-role covenant council reviews this BAD packet for:
   consent posture, third-party treatment, Human-Primacy, crisis-routing
   inheritance, retrieval voice posture, and never-delete interactions.
3. Fold both review lanes.
4. Operator canonicalizes as the next governance decision + ADR.
5. Only then does Calendar draft as the first information-limb implementation
   slice.

---

## Plain English

S2 is the border guard for Maez's outside-world information.

Before Maez reads your calendar, email, Slack, Drive, or GitHub, S2 checks what
the fact is, who it is about, where it may go, how long it may stay, and whether
it can ever become part of Maez's life story.

The first source will be Calendar because it is structured and safer to learn
on than email or Slack. But Calendar is still private. A calendar can reveal
therapy, doctors, relationships, home addresses, religion, politics, work, and
third parties. So S2 treats it carefully.

The core rule is simple: outside information is not Maez's memory just because
Maez can see it. It starts as a documented record. Only a later, reviewed path
can turn it into biography.
