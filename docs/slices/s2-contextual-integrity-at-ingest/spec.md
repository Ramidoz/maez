# Slice S2: Contextual Integrity at Ingest

**Status:** DRAFT BAD packet. Codex BAD-panel folded. No code, no connector,
no memory promotion. This packet folds the S2 scoping memo plus scoping-stage
Claude council, scoping-stage Codex panel, and BAD-stage Codex engineering
panel constraints into the candidate canonical law for information-limb ingest.

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
- [`reviews/spec-codex-panel.md`](reviews/spec-codex-panel.md) — BAD-packet
  engineering review, REVISE/RATIFY-WITH-AMENDMENTS across six seats; this
  spec folds the required revisions.
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
decision2_consent_tier = tier3
consent_posture = third_party_observable_no_consent
```

The Calendar source-profile fallback is Tier 3 because calendar events may
contain non-bonded attendees. Each event still computes its record-level
posture. Events with no non-bonded attendee/provenance field may set:

```text
decision2_consent_tier = none
consent_posture = owner_only
```

Decision 2 mapping:

| S2 posture | Canonical Decision 2 tier | Retention/indexing consequence |
| --- | --- | --- |
| `owner_only` | `none` | Bonded-user-owned source data only; no non-bonded party is present; S2 retention still applies. |
| `third_party_observable_no_consent` | `tier3` | TTL-bounded, not identity-indexable, not promotable, no third-party profile. |
| `third_party_explicit_consent` | `tier2` | Scope and duration must follow the explicit consent record. Not Calendar v1 default. |
| `inter_maez_consented` | `tier1` | Requires future Project C/inter-Maez consent. Not Calendar v1. |

Constraints under that default:

- relational/provenance metadata only;
- no personological profile;
- no nudging/contact;
- no stable third-party identity index unless Tier 1/2 consent grants it;
- attendee names/fields minimized, redacted, or hashed unless a local
  authenticated direct-display path explicitly grants operator-visible display.

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

All non-Calendar source kinds are catalog placeholders only. Gmail, Slack,
Notion, Drive, GitHub, and code-hosting slices must draft their own executable
profiles. Mail subjects, chat channel names, senders, message IDs, document
names, and commit headers are body-adjacent until a later slice proves a safer
classification. They have no Maez-visible default.

Calendar v1 "owner-only" means bonded-user-owned calendar accounts only. Events
from those accounts may still include non-bonded attendees; those attendee
fields remain Tier 3-minimized unless a future consented path exists.

Calendar v1 may include:

- event id;
- title only after deterministic sensitivity policy returns `safe_to_show`;
- start/end;
- status;
- recurrence marker;
- owner calendar handle;
- minimized attendee/provenance fields;
- location only after deterministic sensitivity policy returns `safe_to_show`;
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

Calendar v1 sensitivity policy:

| Field class | Default | Read-model output |
| --- | --- | --- |
| unknown or ambiguous title/location | redact | `[redacted calendar detail]` |
| medical, therapy, legal, religion, politics, sexuality, home address, invite-created sensitive, or recurring sensitive pattern | redact | `[sensitive calendar detail]` |
| ordinary title explicitly classified safe by deterministic rules | allow | title string |
| ordinary location explicitly classified safe by deterministic rules | allow | location string |

The policy is fail-closed. Unknown patterns, classifier errors, or missing
policy version redact the field. Calendar implementation must not invent an NLP
privacy classifier in the connector slice; it must use the deterministic v1
policy or reject the field.

### 3. Allowed Flows

Default:

```text
requested_flow_ids = []
granted_flow_ids = []
```

No Maez-visible flow is enabled by default. Records may enter only the
noncanonical cache and provenance/read-model staging.

Connectors may request flows, but connectors never grant visibility. S2 derives
`granted_flow_ids` from a static/versioned policy registry. A connector-supplied
`granted_flow_ids`, `allowed_flow_ids`, or equivalent visibility grant rejects
the record.

Candidate flow IDs:

- `flow.prompt_context.grounded_only`
- `flow.bounded_window_recall`
- `flow.body_state.provenance`
- `flow.memory.promoted`
- `flow.crisis_candidate.content_minimized`

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

Calendar v1 flow policy registry:

| Flow ID | Consumer | Calendar v1 grant | Model-readable fields | Direct display fields | Denied fields | Voice posture | Promotion allowed |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `flow.prompt_context.grounded_only` | prompt context for direct owner question | Allowed only for non-stale records with deterministic redaction applied | event time window, status, recurrence marker, safe/redacted title token, attendee count/generic relational marker, source freshness phrase | same plus operator-local attendee display only if explicit direct owner request and sensitivity policy permits | descriptions, attachments, video links, raw conferencing URLs, raw source IDs, attendee names by default, body-state fields | "Your calendar shows..." / "I can see on the calendar..." | false |
| `flow.bounded_window_recall` | TRF-style recall | Blocked until later retrieval posture canonicalizes | none | none | all Calendar fields | no "I remember" / no "I know" from S2 cache | false |
| `flow.body_state.provenance` | body-state evidence | Blocked in Calendar v1 | none | none | all Calendar fields | not applicable | false |
| `flow.memory.promoted` | separate memory-write path | Blocked in Calendar v1; future path only | none from S2 directly | none | all fields unless separate promotion path grants | promotion voice defined by memory-write slice | false |
| `flow.crisis_candidate.content_minimized` | future crisis triage | Defined but not granted in Calendar v1 | source kind, observed_at, content-free sensitivity class only | none | title, location, description, body, attendee names, external IDs | "possible external crisis signal; needs reviewed crisis path" | false |

Calendar v1 answers only direct owner requests. It must not volunteer schedule
facts, reminders, "I noticed..." framing, briefings, or proactive schedule
personality without a later attention-budgeted flow. Approved user-facing
phrases include "Your calendar shows..." and "I can see on the calendar...".
Forbidden phrases include "I remember", "we have", "I know you're busy", or any
inference about why the event matters.

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

Noncanonical tombstone fields:

- `source_deleted_at`
- `deletion_observed_at`
- `external_event_id_hash`
- `source_revision_hash`
- `retention_class`
- `record_state = tombstoned`

Permanent retention is not a noncanonical cache class.

Promoted lived memory is never silently deleted. If source deletion happens
after promotion, the promoted memory remains and records tombstone provenance:

- `source_deleted_at`
- `deletion_observed_at`
- `external_event_id_hash`
- `source_changed_at`
- `change_observed_at`
- `prior_source_revision_hash`
- `promotion_record_id`

Maez may say the source record changed or disappeared, but must not silently
rewrite or delete promoted biography.

### 5. Provenance

Every S2 record carries provenance as a Body Bus specialization. Missing
provenance rejects ingest. S2 must not create a second envelope family.

S2 Body Bus envelope mapping:

| Body Bus field | S2 field | Required? | Calendar v1 value |
| --- | --- | --- | --- |
| `event_id` | `ingest_record_id` | yes | content-free deterministic ingest id |
| `schema_version` | `schema_version` | yes | S2 schema version |
| `event_kind` | `source_kind` | yes | `calendar.event` |
| `source_id` | `source_handle_human` | yes | operator-readable account/calendar label; not for logs/health/metrics/panel |
| `source_instance_id` | `source_instance_id` | yes | stable connector instance id |
| `telemetry_handle` | `source_handle_telemetry` | yes | content-free hash for metrics/panel |
| `observed_at` | `observed_at` | yes | provider event timestamp if available |
| `received_at` | `received_at` | yes | Maez ingest timestamp |
| `expires_at or ttl_ms` | `expires_at` | yes | mirror-source TTL or fixed/per-event TTL |
| `sequence` | `sequence` | yes | monotonic per `source_instance_id` |
| `confidence` | `confidence` | yes | bounded enum: `provider_record`, `redacted`, `tombstone`, `unknown` |
| `state` | `record_state` | yes | see transition table |
| `retention_class` | `retention_class` | yes | `mirror_source_ttl` by default |
| `allowed_flow_id` | `granted_flow_ids` | yes | policy-derived list; empty by default |
| `facts` | `facts` | yes | bounded `calendar.event` fields only; no raw body/free text beyond sensitivity-approved title/location |

Additional required S2 fields:

- `external_event_id`
- `external_event_id_hash`
- `source_revision`
- `source_revision_hash`
- `decision2_consent_tier`
- `consent_posture`
- `third_party_posture`
- `requested_flow_ids`
- `granted_flow_ids`
- `flow_policy_version`
- `promotion_state`
- `promotion_eligibility_reason`
- `promotion_eligibility_provenance_handle`
- `promotion_record_id`
- `redaction_state`
- `fetch_batch_id`
- `connector_version`
- `raw_field_policy_version`
- `backfill_origin`
- `provenance`

V1 integrity:

- local DB integrity;
- audit log;
- deterministic idempotency key.

Attestation seam:

Sigstore Rekor or equivalent tamper-evident lineage attestation is in scope as
an extension seam for the full S2 law. It is not a Calendar v1 blocker.

No public transparency log may receive raw source IDs, event IDs, account
handles, titles, attendee hashes vulnerable to dictionary attack, precise event
timestamps, credential-adjacent metadata, or any value that can reconstruct a
private calendar record. V1 uses local/private append-only audit first. Public
commitments, if later approved, must use salted/HMAC content-free commitments.

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
- event-local or purpose-scoped hashed/minimized handles for idempotency and
  dedupe;
- operator-visible attendee fields only through an explicitly granted direct
  display path.

Forbidden:

- "Anna is stressed";
- "you should text Anna";
- stable third-party profile creation;
- third-party salience ranking;
- cross-source third-party enrichment.
- attendee hash as cross-event search key unless Tier 1/2 consent exists;
- third-party profile join key unless Tier 1/2 consent exists.

`operator_display_fields` and `model_readable_fields` are separate. Default
Calendar v1 model-readable attendee surface is attendee count plus generic
relational marker only. Attendee names may appear only in local authenticated
operator display after direct owner request and sensitivity policy approval;
they must not enter model prompt context, logs, health, metrics, project panel,
or memory substrate.

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

but S2 does not execute promotion in v1. S2 may set only:

- `promotion_state`
- `promotion_eligibility_reason`
- `promotion_eligibility_provenance_handle`

Only a separate reviewed memory-write path may set `promotion_record_id` or
write lived memory.

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
  -> connector fetch
  -> S2 envelope validation
  -> noncanonical ingest cache
  -> allowed-flow read model
  -> recall/prompt consumer OR promotion gate
  -> lived memory (only through a separate reviewed memory-write path)
```

Calendar v1 has no webhook receiver. Later webhook slices may only enqueue or
trigger the same S2-validated sync path. They must inherit Decision 26
credentials, replay protection, rate limits, and content-free logging.

Record states:

- `rejected`
- `cached`
- `visible_ready`
- `expired`
- `tombstoned`
- `flow_blocked`
- `promotion_pending`
- `promoted`
- `sync_stale`

Transition rules:

| Current state | Event | Guard | Next state | Side effects | Forbidden effects |
| --- | --- | --- | --- | --- | --- |
| none | fetch record | envelope invalid or forbidden field present | `rejected` | content-free counter only | no cache content, no prompt context |
| none | fetch record | valid envelope, no granted visible flow | `cached` | write noncanonical cache | no model read |
| none/cached | policy evaluation | granted visible flow and redaction complete | `visible_ready` | write read model | no denied fields |
| cached/visible_ready | consumer requests denied field | flow row denies field | `flow_blocked` | content-free blocked counter | no partial leak |
| cached/visible_ready | TTL/source expiry | not promoted | `expired` | remove content | no tombstone body |
| cached/visible_ready | source delete/cancel | not promoted | `tombstoned` | keep content-free tombstone fields | no source body/title/attendee |
| cached/visible_ready | source revision changed | changed record validates | `cached` or `visible_ready` | store prior revision hash and changed timestamps | no silent biography rewrite |
| cached/visible_ready | promotion eligibility detected | separate policy permits eligibility | `promotion_pending` | set eligibility reason/provenance handle | no memory write |
| promotion_pending | reviewed memory-write path succeeds | external writer returns artifact | `promoted` | set `promotion_record_id` | S2 itself must not write memory |
| any readable state | sync stale/outage exceeds max age | source unavailable or lagged | `sync_stale` | omit from prompt context, emit stale metric | no answer from stale cache as current |

Illegal transitions reject and emit content-free audit counters.

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

Sync/outage behavior:

| Condition | Required behavior |
| --- | --- |
| valid sync page | validate complete page before checkpointing cursor/token |
| partial page failure | do not advance cursor/token; retry from last validated checkpoint |
| invalid/expired sync token | enter `sync_stale`, run bounded full resync, preserve tombstones |
| deletion/cancellation replay | process as tombstone transition before new visible reads |
| source outage/rate limit | omit stale records from prompt context once max staleness passes |
| stale but below max age | answer only with stale phrasing if direct owner asks and flow permits |
| stale above max age | fail-neutral: "I can't see a current calendar view right now" |

Calendar v1 max prompt-context staleness must be explicitly configured. Missing
or unparseable staleness policy blocks visible reads.

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

Backfill records are cache-only by default:

- set `backfill_origin = true`;
- block `promotion_eligible`;
- exclude from visible read models until dry-run summary and operator/review
  gate approve the batch;
- never use backfilled history to establish Calendar precedent for Gmail/Slack.

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

Eviction semantics:

- apply per-source-instance quotas before global quotas;
- prefer expired records, tombstones, and non-visible records;
- use deterministic order within each class;
- never evict promoted memory or its provenance handle;
- never silently replace visible context with unrelated records;
- when cache is full, block new visible/promotion paths until compaction or
  operator action succeeds.

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

Telemetry whitelist for logs, health, metrics, and project panel:

- connector state enum;
- source kind enum;
- `source_handle_telemetry`;
- counts;
- ages/durations rounded to configured buckets;
- cache percentage/size buckets;
- content-free error class;
- schema/policy version.

Forbidden in logs, health, metrics, and project panel:

- event titles;
- attendee names;
- subjects;
- descriptions;
- message headers;
- locations;
- source bodies;
- raw source IDs where a content-free hash is sufficient.

`source_handle_human` appears only in local authenticated operator debug views
behind explicit allowlist. "Operator-visible" means local authenticated UI or
explicit operator debug readout only; it never means model prompt, logs, health,
metrics, or public/project-panel output.

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

Information-limb credential tests must include:

- OAuth auth code and state never appear in logs, exceptions, health, panel, or
  subprocess argv;
- refresh/access tokens never appear in URLs;
- provider error payloads are redacted before logging;
- callback URLs are logged without query secrets;
- subprocess credential opt-in is exact-name only;
- no connector-specific secret loader bypasses `core/infra/secrets.py`.

---

## Crisis Routing

Crisis routing is not implemented by S2 v1.

S2 does not create an implicit crisis bypass. If crisis signals appear through
an information limb, they may only move through an explicit, reviewed flow such
as:

```text
flow.crisis_candidate.content_minimized
```

That flow is defined in this packet but not granted to Calendar v1 by default.
It may carry only source kind, observed time, content-free sensitivity class,
and provenance handle. It may not scan Gmail/Slack bodies, Calendar
descriptions, titles, locations, attendee names, or message contents unless a
future body-ingest/crisis slice explicitly grants those fields.

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
16. missing mandatory Body Bus/S2 envelope field rejected;
17. duplicate idempotency key dedupes without new visible record;
18. stale source revision cannot overwrite newer validated record;
19. illegal state transition rejected content-free;
20. connector-supplied `granted_flow_ids` rejected;
21. S2 policy registry computes grants from `requested_flow_ids`;
22. `promotion_eligible` does not write memory or set `promotion_record_id`;
23. noncanonical tombstone removes content and keeps only allowed tombstone
    fields;
24. attendee hash cannot be used as cross-event/profile search key under
    Tier 3;
25. `operator_display_fields` do not enter `model_readable_fields`;
26. no ambient schedule facts volunteered when owner did not ask;
27. Calendar answer uses approved voice posture and never says "I remember" or
    "I know";
28. ambiguous title/location redacts by default;
29. backfilled records are excluded from visible read models until operator gate;
30. sync token invalidation triggers bounded full-resync behavior without stale
    current answer;
31. webhook input, if later added, cannot bypass S2 envelope validation;
32. logs/health/panel use `source_handle_telemetry`, not `source_handle_human`;
33. OAuth code/state, refresh tokens, callback query secrets, and provider error
    payloads are redacted from logs/exceptions/argv/env.

## Calendar Burn-In Observation Gate

Calendar v1 cannot become precedent for Gmail, Slack, Notion, Drive, GitHub, or
any higher-blast-radius information limb until a live burn-in log passes.

Required observation log fields:

- prompt category;
- direct owner request vs unsolicited context;
- flow requested and flow granted;
- source freshness/staleness;
- whether Maez volunteered the fact;
- user-facing phrase used;
- attendee display posture;
- weirdness label: `none`, `schedule_personality`, `third_party_creep`,
  `stale_confidence`, `memory_voice`, `other`;
- contamination concern;
- promote/hold decision;
- changed/deleted-event behavior if applicable.

Natural prompt categories:

- direct schedule question;
- vague planning question;
- emotionally loaded but non-calendar question;
- third-party-attendee question;
- stale/outage question;
- deleted/changed-event question;
- unrelated bonded conversation where Calendar must stay silent.

Minimum closure before next information limb:

- at least one week of live Calendar observation;
- at least 10 natural Calendar-relevant prompts;
- at least 10 unrelated bonded prompts where Calendar stays silent;
- zero raw body/description leaks;
- zero ungrounded "I remember" / "I know" claims from Calendar cache;
- zero unsolicited schedule facts;
- zero third-party personological drift;
- no recurring weirdness label;
- changed and deleted events handled with source-change/source-disappeared
  posture, not silent rewrite;
- operator marks the burn-in gate passed.

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

1. Codex six-agent engineering panel reviewed this BAD packet for:
   state-machine completeness, schema sufficiency, flow enforceability, cache
   budget, sync/backfill design, credential inheritance, and testability.
   Status: REVISE/RATIFY-WITH-AMENDMENTS; folded here.
2. Claude six-role covenant council reviews the folded BAD packet for:
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

Calendar v1 is also not allowed to make Maez act like a scheduler. If you ask
what is on your calendar, Maez can answer from a grounded, redacted record. If
you are just talking, Calendar stays quiet. That difference is the point of S2:
the outside world can inform Maez only through named, testable gates.
