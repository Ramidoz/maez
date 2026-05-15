# Slice Calendar v1: S2-Bounded Google Calendar Ingest

**Status:** DRAFT SPEC. Built from [`diagnostic.md`](diagnostic.md),
post-diagnostic covenant guidance, and folded Codex engineering panel findings.
Claude covenant review has not yet run on this draft. No code has landed from
this packet.

**Maps to:**

- [`diagnostic.md`](diagnostic.md) — empirical provider/API surface and legacy
  Maez calendar-path inventory.
- [`docs/slices/s2-contextual-integrity-at-ingest/spec.md`](../s2-contextual-integrity-at-ingest/spec.md) —
  Decision 27 / ADR 0032, contextual integrity at ingest.
- [`docs/slices/daemon-credential-hygiene/spec.md`](../daemon-credential-hygiene/spec.md) —
  Decision 26 / ADR 0031, credential hygiene and secret lifecycle.
- [`docs/slices/m1-lived-episode-promotion/spec.md`](../m1-lived-episode-promotion/spec.md) —
  Decision 25 / ADR 0030, promote biography; do not widen recall.
- [`docs/slices/body-topology/spec.md`](../body-topology/spec.md) —
  Decision 24 / ADR 0029, information limbs and safe degradation.
- [`docs/adr/0032-contextual-integrity-at-ingest.md`](../../adr/0032-contextual-integrity-at-ingest.md) —
  S2 accepted ADR.
- [`reviews/codex-panel.md`](reviews/codex-panel.md) — Codex engineering panel,
  REVISE; this draft folds the required amendments.
- Google Calendar sync guide:
  https://developers.google.com/workspace/calendar/api/guides/sync
- Google Calendar events reference:
  https://developers.google.com/workspace/calendar/api/v3/reference/events
- Google Calendar events.list reference:
  https://developers.google.com/workspace/calendar/api/v3/reference/events/list
- Google Calendar scopes:
  https://developers.google.com/workspace/calendar/api/auth
- Google OAuth web-server flow:
  https://developers.google.com/identity/protocols/oauth2/web-server

**Classification:** covenant-shaped information-limb implementation spec.
Calendar v1 is the first executable downstream organ under S2, so both review
lanes are required before implementation: Codex engineering panel and Claude
covenant council.

---

## Intent

Calendar v1 replaces Maez's legacy direct Calendar path with an S2-bounded
Google Calendar ingest organ.

The legacy path was useful early wiring, but the diagnostic showed that it
violates all three newly canonical substrate organs:

- S2: raw Calendar titles and locations can enter prompt context before
  contextual-integrity classification.
- M1: Calendar facts can be appended into memory/scoring text without a
  provider/biography boundary.
- Decision 26: OAuth refresh state is stored and written through local JSON
  files rather than Maez's credential interface.

Calendar v1 is therefore not a wrapper around `skills/calendar_perception.py`.
It is a replacement boundary:

1. fetch only the v1-selected Calendar surface;
2. convert provider records into S2 envelopes;
3. classify/redact before any Maez-visible flow;
4. store only bounded noncanonical state and audit-safe sidecars;
5. answer direct owner Calendar questions from S2-approved facts;
6. fail neutral when auth, sync, freshness, or policy blocks access.

---

## Load-Bearing Rule

**Calendar is provenance, not Maez's lived schedule.**

Allowed:

- Google Calendar -> Calendar connector -> S2 envelope -> redacted read model
  -> direct-owner-request answer.
- Google Calendar -> provider cache -> tombstone/audit sidecar -> source
  continuity.
- Google OAuth refresh -> `core/infra/secrets.py` lifecycle interface.

Forbidden:

- Google Calendar -> raw prompt context.
- Google Calendar -> proactive reminder, nudge, or scheduler voice.
- Google Calendar -> TRF/lived recall as "I remember..." or "we have...".
- Google Calendar -> M1/lived episode without a future reviewed promotion path.
- Google Calendar -> body-state inference in v1.
- Google Calendar -> crisis routing bypass.
- Google Calendar -> OAuth token file or credential-bearing URL.
- Legacy Calendar path fallback if Calendar v1 fails.

Plain English: Maez may say "your calendar shows a redacted event window" when
Rohit asks. Maez may not act like it jointly lives the calendar, remembers the
event, knows why it matters, or should remind/nudge him about it.

---

## V1 Decisions From Diagnostic Questions

The diagnostic raised ten spec-stage questions. Calendar v1 resolves them as
follows.

| Question | V1 decision |
| --- | --- |
| Q1 minimal scope | Use the narrowest workable Google scope. Target `https://www.googleapis.com/auth/calendar.events.owned.readonly`. If implementation evidence proves it cannot support primary-owned read-only event sync, the fallback is `calendar.events.readonly`. `calendar.readonly` is forbidden in v1 without explicit operator escalation and spec amendment. |
| Q2 calendar selection | Primary owned calendar only. Shared, work, family, delegated, subscribed, or public calendars are future grants. |
| Q3 full sync horizon | Forward-only short horizon: now through 14 days ahead. Zero historical backfill. All-day or recurring instances are included only if their occurrence overlaps the forward window. |
| Q4 `410 Gone` cache wipe | Clear provider mirror rows, paging state, and sync token. Preserve tombstone sidecar, audit log, keyed provenance handles, policy versions, and promotion-denial evidence. |
| Q5 token refresh interface | Extend `core/infra/secrets.py`; do not build a parallel Decision-26 adapter. OAuth refresh-token write-back is a credential lifecycle event. |
| Q6 description field | Forbidden in v1. The connector may transiently receive a provider payload, but description must not be stored, prompted, logged, displayed, audited as text, or promoted. |
| Q7 alerts | No proactive alerts in v1. Remove legacy 15-minute and 5-minute Calendar reminder paths when v1 enables. |
| Q8 project panel | Content-free telemetry only: connector state, source kind, telemetry handle, counts, age buckets, and error class. No titles, names, locations, descriptions, source IDs, or conference links. |
| Q9 migration | Legacy path disabled/removed when Calendar v1 enables. No privacy-failing fallback to `skills.calendar_perception`. If v1 fails, Calendar access fails neutral. |
| Q10 push notifications | Deferred to v2. V1 is polling-only incremental sync. |

---

## V1 Scope

### In Scope

- Google Calendar read-only connector for the bonded user's primary owned
  calendar.
- Pull-based initial full sync and incremental sync.
- 14-day forward-only provider mirror.
- S2 envelope construction for `calendar.event`.
- Maez-computed consent tier, sensitivity, allowed flows, and voice posture.
- Deterministic redaction/scrubbing of title and location.
- Attendee minimization with keyed HMAC only where audit continuity needs a
  stable handle.
- Provider-timestamp ordering.
- Audit-survivable tombstone sidecar.
- Decision-26 credential loading and refresh-token write-back.
- Content-free health/project-panel telemetry.
- Direct-owner-request Calendar answer flow.
- Legacy direct path disablement.
- RED-first test contract and review packet.

### Out Of Scope

- Real OAuth onboarding during spec/review.
- Any live Google API call before implementation and explicit operator action.
- Shared/work/family/delegated/subscribed calendars.
- Calendar descriptions.
- Proactive reminders or alerts.
- Push/webhook notifications.
- Calendar-to-biography promotion.
- TRF Calendar recall beyond S2-approved external-source phrasing.
- Body-state inference from Calendar.
- Crisis routing from Calendar.
- Public transparency / Rekor logging.
- Gmail, Slack, Drive, Notion, GitHub, or any non-Calendar connector.

---

## Architecture

Calendar v1 introduces an S2-shaped path and retires the legacy direct path.

```text
Google Calendar API
      |
      v
CalendarConnector
      |
      v
CalendarProviderRecord
      |
      v
S2CalendarEnvelopeBuilder
      |
      +--> Provider mirror DB / cache (bounded, noncanonical)
      +--> Tombstone sidecar (audit-survivable)
      +--> Calendar read model (redacted, direct-owner-request only)
      +--> Health / panel telemetry (content-free)
```

No Calendar v1 component may call Maez's language model, write lived episodes,
or append raw Calendar text into daemon prompt context.

### Files Expected To Change In Implementation

The implementation plan may adjust exact names after review, but the spec
expects these boundaries:

- Create `core/information_limb/calendar_v1.py` or equivalent focused module
  for provider fetching and S2 envelope conversion.
- Create `core/information_limb/calendar_store.py` or equivalent focused module
  for provider mirror, sync state, and tombstone sidecar.
- Extend `core/infra/secrets.py` for OAuth refresh-token lifecycle if current
  v1 APIs are insufficient.
- Modify `daemon/maez_daemon.py` to remove/gate the legacy direct import and
  stop direct prompt/memory/alert injection.
- Modify project-panel/health surface only for content-free Calendar state.
- Add tests under `tests/` proving the RED contract below.

The implementation must keep the code split by responsibility. A single large
"calendar everything" file is not acceptable unless the review panel explicitly
accepts it as temporary scaffolding.

---

## Provider Scope And Selection

Calendar v1 default scope target:

```text
https://www.googleapis.com/auth/calendar.events.owned.readonly
```

Fallback only if implementation evidence proves the target scope cannot support
primary-owned Calendar v1:

```text
https://www.googleapis.com/auth/calendar.events.readonly
```

Forbidden in v1 without explicit operator escalation:

```text
https://www.googleapis.com/auth/calendar.readonly
https://www.googleapis.com/auth/calendar
```

Calendar v1 selects only:

- the bonded user's primary calendar;
- events on that owned calendar, not as proof of per-event authorship or
  third-party consent;
- occurrences overlapping the 14-day forward horizon.

If Google returns records from calendars or ownership contexts outside v1
selection, the connector rejects them before S2 envelope construction and emits
only content-free rejection counters.

Calendar v1 targets `calendar.events.owned.readonly` because Google documents
it as allowing reads of events on Google calendars the user owns, and
`events.list` accepts that scope. V1 addresses only `calendarId="primary"`.

This scope is not treated as proof that each event is authored by, owned by, or
safe for the bonded user. Organizer, creator, attendee, title, and location
fields remain third-party-bearing provider facts and pass through S2 policy
before any Maez-visible flow.

---

## Sync Contract

### Provider Query Shape

Calendar v1 distinguishes provider synchronization from Maez-visible retention.

The Maez-visible provider mirror and read model are limited to the forward
window from now through 14 days ahead. That horizon is enforced locally after
provider records are received.

Initial full sync may use `timeMin` and `timeMax` to reduce first-run blast
radius, but incremental sync with `syncToken` must obey Google `events.list`
restrictions. Incremental requests must not include `timeMin`, `timeMax`,
`orderBy`, `q`, `iCalUID`, `privateExtendedProperty`,
`sharedExtendedProperty`, or `updatedMin` with `syncToken`, and must not set
`showDeleted=false`.

Incremental sync may receive changed or deleted records outside the current
14-day horizon. Those records are processed only enough to preserve tombstone,
audit, and sync continuity, then excluded or expired from the Maez-visible
forward-window mirror.

### Initial Sync

Initial sync:

- uses the selected read-only scope;
- requests only the forward window from now through 14 days ahead;
- expands recurring events into occurrences where necessary for direct-owner
  questions;
- stores the provider `nextSyncToken` only after all pages complete;
- persists provider timestamps and policy version with each accepted record;
- rejects records outside v1 selection.

### Incremental Sync

Incremental sync:

- uses the previous `nextSyncToken`;
- preserves the same query-shape constraints required by Google;
- handles pagination until the final `nextSyncToken` appears;
- records deleted/cancelled entries as tombstones where audit continuity needs
  them;
- updates provider mirror state only after an accepted S2 envelope passes
  schema and policy checks.

Cancelled records are split by Google event shape:

- cancelled recurring exceptions with `recurringEventId` and
  `originalStartTime` are stored as recurrence-exception tombstones for as long
  as the parent recurring event remains relevant to the local mirror;
- other cancelled records are deletion tombstones and may contain only provider
  `id`;
- cancelled/deleted records must not rely on summary, location, attendee,
  organizer, or description fields being present, even if Google sometimes
  returns them on organizer calendars;
- no cancelled record is user-presented except as a redacted absence/removal
  fact when directly needed for an owner-requested Calendar answer.

### Sync Token Invalid

On provider `410 Gone`:

- mark connector state `sync_lagged`;
- clear provider mirror rows;
- clear page token state;
- clear sync token;
- run a new forward-window full sync;
- preserve tombstone sidecar;
- preserve audit log;
- preserve HMAC handles and policy version evidence;
- do not delete any promoted memory because Calendar v1 cannot promote memory.

Provider `updated` is authoritative for source revision ordering when present.
`received_at` is ingestion evidence only. If a cancelled/deleted provider
record lacks `updated`, Calendar v1 records a content-minimized tombstone
observation with `received_at` but must not treat that timestamp as the
provider's event revision time.

---

## Calendar Provider Record

The connector may receive provider fields, but the provider record passed into
S2 must be minimized before any Maez-visible flow.

Allowed provider facts for v1 S2 envelope:

- provider event id as internal-only source handle;
- calendar id as internal-only source handle;
- event status;
- start/end date or date-time;
- timezone;
- all-day marker;
- recurrence marker and recurring parent handle;
- provider `updated` timestamp;
- provider `created` timestamp;
- event visibility;
- transparency/free-busy status;
- attendee count;
- organizer/creator relation class, not raw identity;
- attachment/conference presence booleans, not URLs or names;
- redacted/safe title token after policy;
- redacted/safe location token after policy.

Forbidden provider fields for v1 S2 envelope:

- description/body;
- attendee names/emails;
- organizer/creator names/emails;
- conference URLs or entry points;
- attachment titles/URLs;
- extended properties with free text;
- raw source IDs in prompt-visible or panel-visible surfaces;
- any token, OAuth state, or credential string.

Description/body is not parsed, classified, scanned for sensitivity, logged,
stored, prompted, displayed, audited as text, or used to derive crisis or
sensitivity signals in Calendar v1. If the provider payload includes a
description/body despite field-selection minimization, the connector drops it
immediately before policy evaluation. Calendar v1 may record only a
content-free `description_present` rejection/diagnostic counter if needed; that
counter grants no visible flow.

---

## S2 Envelope Contract

Calendar v1 uses the canonical S2 Body Bus envelope without abbreviation. All
fields required by the S2 provenance and Body Bus mapping are mandatory for
Calendar v1.

Calendar-specific aliases are forbidden. Use canonical S2 field names exactly:

- `decision2_consent_tier`, not `consent_tier`;
- `requested_flow_ids`, not `requested_flows`;
- `granted_flow_ids`, not `granted_flows`;
- `source_instance_id`, not connector-local calendar aliases;
- `external_event_id_hash` and `source_revision_hash`, not raw provider IDs in
  audit-visible surfaces.

Calendar-specific facts live inside canonical `facts` and provenance fields.
They do not create a second envelope family.

Connectors may request flows and report provider facts. They may not compute:

- `decision2_consent_tier`;
- final sensitivity class;
- final third-party posture;
- final granted flows;
- promotion eligibility.

Schema version mismatch is fail-closed. Unknown future provider fields are
ignored unless a reviewed spec update admits them.

## Calendar State Machine And Idempotency

Calendar v1 inherits the S2 transition table exactly.

Illegal transitions reject content-free and do not update provider mirror,
read model, or tombstone state.

Idempotency key:

```text
source_kind + source_instance_id + external_event_id + source_revision
```

Same key plus identical validated facts dedupes. Same key plus conflicting
facts rejects with `idempotency_conflict` and does not update provider mirror or
visible read model. Older provider revisions cannot overwrite newer revisions.

`confidence` cannot encode lifecycle state. Lifecycle state uses the connector
state and S2 record-state fields only.

---

## Sensitivity And Redaction

Title and location are treated as untrusted free text.

Allowed title/location output tokens:

- `[calendar event]`;
- `[redacted calendar detail]`;
- `[sensitive calendar detail]`;
- `[redacted third-party calendar detail]`;
- deterministic safe category labels explicitly approved by S2 policy.

In Calendar v1, `safe title token` and `safe location token` mean either a
redaction token or a deterministic S2-approved category label. They do not mean
the raw provider title/location string.

Forbidden title/location behavior:

- passing raw strings to model prompt;
- passing raw strings to memory/scoring text;
- passing raw strings to logs/health/panel/audit-visible output/review packets;
- retaining third-party names in "safe" titles;
- retaining body-adjacent or relationship details;
- using a model to decide redaction in v1.

Sensitivity policy must be deterministic and testable. Ambiguity redacts.

The policy must catch at least:

- medical/therapy/legal/religion/politics/sexuality/home-address patterns;
- relationship/family/conflict patterns;
- invite-created sensitive patterns;
- recurring sensitive patterns;
- third-party identity embedded in title/location;
- body-adjacent third-party detail embedded in title/location.

---

## Attendee And Third-Party Posture

Attendees are third-party-bearing by default.

Model-visible v1:

- attendee count bucket;
- generic relational marker only when policy permits;
- no names;
- no emails;
- no profile pictures;
- no response-status details tied to identity.

Audit-local v1:

- keyed HMAC handle when event-local audit continuity is required;
- no raw attendee name/email in committed docs, logs, health, metrics, or panel;
- HMAC key from Decision-26 secret interface.

Attendee HMAC handles are not a people index. They are audit continuity handles
only and must not be used to build third-party profiles.

Attendee HMAC handles are purpose-scoped and event-lineage-scoped by default.
The HMAC input must bind at least `source_instance_id`, provider event lineage
handle, attendee value, and purpose label. The same third party must not receive
a globally stable handle across unrelated events under Tier 3. Calendar v1 must
not expose attendee HMAC lookup/search APIs except event-local audit continuity
and dedupe. Cross-event attendee joins require future Tier 1/2 consent and spec
amendment.

Direct owner request does not grant raw third-party identity display through
the model. If the owner asks for attendees or "who," Calendar v1 may answer
only with attendee count bucket and approved generic relational marker, or
state that attendee identity is redacted in v1. Any future local authenticated
direct-display path for attendee names must be a separate non-model surface and
must not write prompt, logs, health, panel, audit-visible output, or memory.

---

## Allowed Flows

Calendar v1 grants exactly one user-visible flow:

```text
flow.prompt_context.grounded_only
```

This flow is allowed only when all are true:

- the bonded user directly asks for Calendar state;
- connector state is healthy enough to answer;
- source data is fresh within policy;
- record passed S2 schema, sensitivity, third-party, and retention checks;
- prompt output uses approved external-source voice.

Approved voice:

- "Your calendar shows..."
- "I can see on the calendar..."
- "There is a calendar entry..."

Forbidden voice:

- "I remember..."
- "I know..."
- "we have..."
- "we're meeting..."
- "your 3pm is coming up..."
- "you've got..."
- any proactive reminder phrasing;
- any inference about why the event matters.

Calendar answer generation must use a deterministic Calendar answer composer or
a deterministic post-generation `calendar_voice_guard` before any owner-visible
reply can include Calendar facts. The allowed output shape is external-source
Calendar state only: time window, redacted/safe event token, freshness or
unavailable state, and neutral count/free-busy-as-Calendar-state phrasing.

The composer/guard must reject scheduler personality, advice, prioritization,
encouragement, routine-planning voice, availability/busyness/stress framing,
first-person co-actor framing, and any wording that turns Calendar evidence
into Maez's own lived schedule. If the guard rejects the draft, Calendar v1
fails neutral rather than rephrasing through the model.

Calendar v1 blocks:

- `flow.bounded_window_recall`;
- `flow.body_state.provenance`;
- `flow.memory.promoted`;
- `flow.crisis_candidate.content_minimized`.

Crisis-shaped Calendar signals, if discovered by deterministic policy, are
held as content-free sensitivity state and require a future reviewed crisis path.
The model alone never decides to bypass S2.

---

## Direct Owner Request Definition

A direct owner request is an owner-authored utterance whose main ask explicitly
requests Calendar, schedule, event, agenda, or free/busy state for the bonded
user's selected Calendar surface. Calendar v1 may not infer a Calendar lookup
from ordinary planning, vague distress, bonded conversation, or assistant-style
task help.

Examples of allowed request shapes:

- asking what is on the calendar for a date/time window;
- asking whether the calendar is free/busy for a date/time window;
- asking for a redacted count of upcoming calendar entries.

Not direct owner requests:

- vague distress;
- ordinary bonded conversation;
- planning talk that does not request Calendar lookup;
- "you should remind me" style future alert delegation;
- third-party curiosity detached from the owner's Calendar need.

When uncertain, Calendar v1 does not read.

Free/busy answers describe only Calendar state. Allowed: "Your calendar shows
no entry in that window." Forbidden: "you are free," "you are available," "you
are busy," "you have time," or any inference about focus, stress, capacity,
location, or bodily/social availability.

---

## No Proactive Alerts

Calendar v1 removes the legacy 15-minute and 5-minute Calendar reminder behavior
from the Maez daemon path when v1 enables.

Forbidden:

- Telegram reminder from Calendar v1;
- speech reminder from Calendar v1;
- background "I noticed your meeting" message;
- morning briefing Calendar agenda;
- interruption based on Calendar state;
- using Calendar to infer owner focus, busyness, stress, or availability.

Future attention-budgeted reminder or availability flows require a separate
reviewed slice. They cannot inherit Calendar v1's direct-owner-request grant.

---

## Credential Contract

Calendar v1 inherits Decision 26.

Required:

- OAuth client material and refresh tokens are identity-bearing secrets;
- no Calendar credential in `config/.env`;
- no authoritative token state in `config/token.json`;
- no credential-bearing URL;
- no OAuth token in subprocess argv;
- no secret-bearing subprocess environment by default;
- value-free auth logs and health;
- provider-safe verification that never prints token values.

Implementation must extend `core/infra/secrets.py` if current APIs cannot:

- read Calendar OAuth client material;
- read Calendar refresh token;
- persist rotated refresh token;
- record source-channel-only audit evidence;
- support rollback if the new OAuth writer fails.

No parallel connector-local credential loader is allowed.

### OAuth Token Lifecycle

Calendar v1 uses offline OAuth access only for operator-approved onboarding.
Access tokens are short-lived runtime material and must not be persisted as
authoritative state. Refresh tokens, OAuth client material, granted-scope
evidence, and refresh-token rotation state are owned by `core/infra/secrets.py`.

On refresh:

- access token may live only in memory or in a generated runtime compatibility
  artifact if unavoidable;
- refresh-token changes must be persisted through `core/infra/secrets.py`
  before the connector reports healthy;
- granted scopes must be compared against the selected v1 scope set;
- missing or widened/narrowed granted scopes must classify as
  `auth_scope_downgraded` or `auth_scope_unexpected`, fail neutral, and never
  silently continue;
- refresh failure must not overwrite the last known valid refresh-token state
  with partial or invalid data.

Compatibility files are allowed only as generated runtime artifacts if the
Google client library forces a file-shaped input. They must be:

- derived from `core/infra/secrets.py`;
- `0600`;
- atomically written;
- outside `config/`;
- outside committed or backup-authoritative state;
- never named `config/token.json`;
- never read as source of truth;
- deleted or overwritten safely when stale.

Tests must prove stale/generated files cannot become authoritative token state.

No Calendar OAuth or API path may shell out by default. If a helper subprocess
is unavoidable, it must use a sanitized environment, no token-bearing argv, and
no generated credential path that can become authoritative token state.

## Auth State Classification

Calendar v1 exposes only content-free auth/provider state classes:

- `auth_ok`;
- `auth_access_expired_refreshing`;
- `auth_refresh_revoked`;
- `auth_scope_downgraded`;
- `auth_scope_unexpected`;
- `auth_client_config_missing`;
- `auth_client_invalid`;
- `auth_reauthorization_required`;
- `provider_rate_limited`;
- `provider_backend_error`;
- `source_unavailable`;
- `sync_token_invalid_resyncing`;
- `calendar_unavailable`.

A `401` after access-token refresh fails maps to `auth_refresh_revoked` or
`auth_reauthorization_required` where provider/library evidence supports it. A
granted-scope mismatch maps to `auth_scope_downgraded` or
`auth_scope_unexpected`. `403`/`429` rate limits map to
`provider_rate_limited` with backoff. `500` maps to `provider_backend_error`.
`410` maps to `sync_token_invalid_resyncing` and preserves tombstone/audit
sidecars.

## Calendar Rollback

Calendar rollback is fail-neutral, not legacy fallback.

If Calendar v1 credential loading or refresh-token write-back fails after
deployment:

1. Disable Calendar v1 with the Calendar feature flag or connector config.
2. Keep legacy `skills.calendar_perception` disabled.
3. Preserve Decision-26 secret state and generated-file evidence for local
   forensic review without printing values.
4. Restore the last known valid secret-source state only through
   `core/infra/secrets.py`.
5. Record connector state as `calendar_unavailable` or the specific auth class.
6. Reopen this slice before re-enabling Calendar.

`MAEZ_SECRETS_DISABLE_NEW_LOADER=1` is only a whole-credential-loader emergency
rollback inherited from Decision 26. It reaccepts process-environment exposure
and cannot be treated as a valid Calendar v1 final state.

---

## Storage Contract

Calendar v1 storage is noncanonical.

Required storage classes:

- provider mirror table;
- sync state table;
- tombstone sidecar table;
- audit event table;
- policy version table.

Every Calendar v1 table stores `calendar_store_schema_version`. Unknown or
incompatible store schema blocks connector startup fail-neutral.

Sync state stores:

- `source_instance_id`;
- `query_shape_hash`;
- protected `sync_token` or secret reference;
- current page checkpoint;
- `last_success_at`;
- `last_attempt_at`;
- connector state enum;
- content-free error class;
- max prompt-context staleness policy.

Provider mirror stores minimized provider facts only. It must not store:

- descriptions;
- raw attendee names/emails;
- raw title/location after redaction decision unless explicitly needed for
  local operator-only debug and protected by a later grant;
- conference URLs;
- attachment URLs;
- OAuth tokens.

Retention:

- forward-window provider mirror expires after it leaves the v1 horizon;
- tombstones survive provider mirror wipe;
- audit sidecars survive `410 Gone` resync;
- no Calendar v1 storage may delete or modify `lived_episodes.db`.

A provider mirror row may be deleted or compacted only after a content-free
tombstone sidecar is durably written. Sidecar fields are limited to:

- `source_deleted_at`;
- `deletion_observed_at`;
- `external_event_id_hash`;
- `source_revision_hash`;
- `source_kind`;
- `source_handle_telemetry`;
- `schema_version`;
- `retention_class`;
- `record_state = tombstoned`.

Tombstone sidecars must not contain title, location, description, attendee,
organizer, creator, conference, attachment, raw source ID, or credential fields.

---

## Health, Logs, Metrics, Project Panel

Allowed content-free surfaces:

- connector state enum;
- source kind enum;
- telemetry handle;
- accepted/rejected/deduped/tombstoned counts;
- age buckets;
- sync lag bucket;
- cache occupancy bucket;
- content-free error class;
- policy/schema version.

Forbidden:

- titles;
- locations;
- descriptions;
- attendee names/emails;
- organizer/creator names/emails;
- raw source IDs;
- raw provider event IDs;
- raw calendar IDs;
- raw account labels;
- raw conference IDs;
- conference links;
- OAuth token state beyond content-free lifecycle enum;
- provider error payloads that might include request details.

Project panel may show "Calendar connector: healthy/stale/auth needed" and
counts. It may not show event content.

Audit-visible Calendar output, including audit logs, tombstone sidecars, review
packets, health snapshots, metrics, and project panel, must use
`source_handle_telemetry`, `external_event_id_hash`, `source_revision_hash`, or
event-local HMAC handles only. Raw provider event IDs, calendar IDs, account
labels, conference IDs, and organizer/attendee identifiers may exist only
inside the private connector mirror where required for provider sync, and must
never be emitted to audit-visible or prompt-visible surfaces.

---

## Legacy Path Migration

Calendar v1 implementation must disable the legacy path, not leave it as a
fallback.

Legacy disablement is process-start strict. When Calendar v1 is enabled,
`daemon/maez_daemon.py` must not import `skills.calendar_perception`,
`CalendarSnapshot`, or `calendar_observe` at module import time or runtime. A
feature flag checked after importing the legacy module does not satisfy this
requirement.

Calendar disabled means absent, not legacy. If Calendar v1 is disabled,
unavailable, unhealthy, auth-blocked, or sync-blocked, all Calendar surfaces
fail neutral and no legacy Calendar observer, cache worker, prompt formatter,
memory formatter, Telegram reminder, speech reminder, or morning-briefing agenda
path may run.

Legacy surfaces to remove or gate cold:

- `daemon/maez_daemon.py` direct import of `calendar_observe`;
- direct `CalendarSnapshot.format_for_context()` prompt injection;
- direct `CalendarSnapshot.format_for_memory()` cognition scoring append;
- Telegram/speech alert path using raw event title/location;
- token refresh through `config/token.json`;
- `skills/calendar_cache_worker.py` lazy import of
  `skills.calendar_perception.observe`;
- fast-lane or perception-cache prompt rendering of legacy `CalendarSnapshot` /
  `CalendarEvent` titles, locations, or descriptions;
- `scripts/fast_reply_cli.py --prime-perception` starting a legacy Calendar
  worker;
- static/local/public UI claims that Calendar is built as an 8h lookahead or
  reminder-capable perception source;
- `skills/calendar_perception.py::test()` live OAuth convenience path, unless
  moved behind explicit developer-only guard and Decision-26 credential source.

Failure behavior:

- if Calendar v1 is disabled, Calendar is absent;
- if Calendar v1 auth fails, Calendar is unavailable;
- if Calendar v1 sync fails, Calendar is stale/unavailable;
- no failure path may invoke legacy raw Calendar prompt/alert behavior.

---

## Migration Order

1. Add failing legacy-disablement tests first.
2. Introduce Calendar mode resolution at process start: `disabled`, `v1`, or
   explicit developer-only legacy test mode.
3. Remove daemon top-level imports of legacy Calendar classes/functions before
   adding the v1 connector.
4. Disable legacy prompt, memory/scoring, alert, morning briefing, cache worker,
   and fast-lane Calendar rendering paths.
5. Add v1 connector/store/read-model behind the disabled-by-default flag.
6. Add content-free health/panel telemetry only after v1 state is available.
7. Enable v1 only after unit tests, restart/shutdown test, and
   operator-approved OAuth onboarding pass.

Calendar polling workers must use bounded worker semantics. They must be
stopped and joined during daemon shutdown with a bounded timeout; restart cannot
leave an in-flight Calendar sync writing after shutdown begins.

---

## Review Protocol

Calendar v1 is covenant-shaped. Before implementation:

1. Codex six-agent engineering panel reviews this spec. Status: complete,
   REVISE, folded into this draft.
2. Claude six-role covenant council reviews this folded draft.
3. Any Claude findings are folded structurally into this spec.
4. Both lanes verify closure if the fold changes load-bearing behavior.
5. Operator canonicalizes or explicitly holds.
6. Cooling-off applies before code unless operator logs an explicit waiver.

Implementation then proceeds RED-first. Post-implementation both-lane review is
required before push/enablement.

---

## RED-First Test Contract

The Calendar implementation must start by writing failing tests for these
behaviors.

### Legacy Disablement

1. Daemon cannot import or call `skills.calendar_perception.observe` when
   Calendar v1 is enabled.
2. Legacy `format_for_context()` output cannot enter prompt construction.
3. Legacy `format_for_memory()` output cannot enter cognition scoring.
4. Legacy Calendar Telegram/speech alerts are absent when Calendar v1 is
   enabled.
5. Calendar v1 failure does not fall back to legacy Calendar path.

### S2 Authority

6. Connector cannot set `decision2_consent_tier`.
7. Connector cannot grant its own flows.
8. Schema version mismatch rejects the record.
9. Unknown provider fields are ignored or rejected according to policy, never
   passed through.
10. Provider `updated` timestamp wins over local `received_at` for source
    revision.

### Scope And Selection

11. Requested Google scope is `calendar.events.owned.readonly` by default.
12. `calendar.readonly` is rejected without explicit operator escalation.
13. Non-primary calendar records are rejected.
14. Non-owned/delegated/shared records are rejected.
15. Events outside the 14-day forward window cannot enter the Maez-visible read
    model, while sync/tombstone continuity can still update content-free
    sidecars.

### Redaction And Third-Party Posture

16. Raw title cannot reach prompt context.
17. Raw location cannot reach prompt context.
18. Description/body is dropped before policy evaluation and cannot be parsed,
    classified, scanned, stored, prompted, logged, displayed, audited as text,
    or used to derive crisis/sensitivity state.
19. Attendee names/emails cannot reach prompt, logs, health, metrics, or panel.
20. Third-party identity in title/location redacts.
21. Body-adjacent detail in title/location redacts.
22. Ambiguous title/location redacts.
23. Attendee audit handle uses event-lineage-scoped keyed HMAC from Decision 26.
24. HMAC attendee handles cannot be used as people-profile keys.

### Flow And Voice

25. Direct owner request can receive approved Calendar answer from redacted
    facts.
26. Non-direct request receives no Calendar read.
27. "I remember" voice is forbidden for Calendar facts.
28. "we have" / "we're meeting" voice is forbidden.
29. "you've got" / reminder-like voice is forbidden.
30. Calendar v1 never volunteers schedule facts.
31. Calendar v1 never sends proactive Telegram/speech reminders.
32. Calendar v1 does not infer owner busyness, stress, or body state.

### Sync And Tombstones

33. Initial sync stores `nextSyncToken` only after final page.
34. Incremental sync paginates until final `nextSyncToken`.
35. `410 Gone` clears provider mirror and sync token.
36. `410 Gone` preserves tombstone sidecar.
37. `410 Gone` preserves audit sidecar.
38. Cancelled/deleted event records become content-minimized tombstones.
39. Provider cache wipe never touches `lived_episodes.db`.

### Credentials

40. OAuth client material is read through `core/infra/secrets.py`.
41. Refresh token is read through `core/infra/secrets.py`.
42. Refresh-token rotation writes through `core/infra/secrets.py`.
43. No Calendar credential is read from `config/.env`.
44. No authoritative token state is written to `config/token.json`.
45. No access token appears in URL, argv, logs, health, metrics, or panel.
46. Authorization header path is used for access tokens.
47. Subprocess env is sanitized for any helper process.
48. Provider auth verification does not print credential values.

### Telemetry

49. Health exposes connector state enum and age buckets only.
50. Project panel exposes counts/state only.
51. Logs contain content-free error classes only.
52. Provider error payloads are scrubbed before logging.

### Push Deferral

53. Calendar v1 has no webhook route.
54. Calendar v1 does not call `events.watch`.
55. Push channel token construction is absent in v1.

### Panel-Fold Additions

56. Missing mandatory canonical S2 envelope field rejects the record.
57. Calendar-specific envelope aliases such as `consent_tier`,
    `requested_flows`, or `granted_flows` are rejected.
58. Duplicate idempotency key with identical validated facts dedupes.
59. Duplicate idempotency key with conflicting validated facts rejects with
    `idempotency_conflict`.
60. Older provider revision cannot overwrite newer provider revision.
61. Illegal S2 state transition rejects content-free.
62. `confidence` cannot encode lifecycle state.
63. Flow-policy-version change cannot widen visibility.
64. Cache-full state fails neutral/fail-closed according to S2 policy.
65. Tombstone sidecar contains no title, location, description, attendee,
    organizer, creator, conference, attachment, raw source ID, or credential
    fields.
66. Missing/unparseable max prompt-context staleness policy blocks visible
    Calendar reads.
67. `auth_access_expired_refreshing`, `auth_refresh_revoked`,
    `auth_scope_downgraded`, `auth_scope_unexpected`, `provider_rate_limited`,
    `provider_backend_error`, `source_unavailable`, and
    `sync_token_invalid_resyncing` surface as distinct content-free classes.
68. Incremental request construction never combines `syncToken` with
    `timeMin`, `timeMax`, `orderBy`, `q`, `iCalUID`, extended-property filters,
    or `updatedMin`.
69. Incremental request construction never sets `showDeleted=false`.
70. Out-of-horizon incremental changes cannot enter the read model, but can
    update tombstone/audit continuity.
71. Cancelled recurring exceptions produce recurrence-exception tombstones.
72. Deleted events that only contain provider id still produce content-free
    deletion tombstones.
73. Raw provider event IDs, calendar IDs, account labels, conference IDs,
    organizer IDs, and attendee identifiers are absent from audit-visible
    output.
74. Safe title/location token cannot equal raw provider title/location text.
75. Primary-calendar membership alone does not bypass third-party policy.
76. Owner "who" requests do not expose attendee names/emails through model
    output.
77. Calendar answers pass deterministic answer composer or
    `calendar_voice_guard` before display.
78. Soft scheduler-personality phrasing is rejected even when no literal banned
    phrase appears.
79. "Help me plan my day" does not read Calendar unless the owner explicitly
    asks to use Calendar/schedule data.
80. Calendar free/busy answers never phrase absence of events as owner
    availability.
81. Crisis-shaped Calendar title/location produces content-free held
    sensitivity state, no prompt content, and no crisis routing bypass.
82. TRF/lived-recall consumers cannot read Calendar provider cache or read
    model as promoted memory.
83. Access tokens are memory-only unless a generated runtime compatibility
    artifact is explicitly required.
84. Generated compatibility files are outside `config/`, are `0600`, are
    atomically written, are not named `config/token.json`, and cannot become
    source of truth.
85. Refresh failure does not overwrite valid refresh-token state with
    partial/invalid state.
86. Granted-scope mismatch maps to `auth_scope_downgraded` or
    `auth_scope_unexpected` and fails neutral.
87. Calendar rollback disables Calendar v1 or restores Decision-26 secret state
    without invoking legacy raw Calendar prompt/alert behavior.
88. With Calendar v1 enabled before daemon import, importing
    `daemon.maez_daemon` does not import `skills.calendar_perception`.
89. No runtime path in daemon, fast-lane, cache worker, or CLI calls
    `skills.calendar_perception.observe`.
90. A fake legacy `CalendarSnapshot` containing sentinel title/location text
    cannot appear in daemon prompt, fast-lane prompt, cognition scoring input,
    logs, health JSON, project panel state, Telegram send text, or speech text.
91. `CalendarCacheWorker` is either removed, marked developer-only fail-closed,
    or replaced by a v1 worker that stores only S2-approved read models.
92. Calendar polling workers are stopped and joined during daemon shutdown with
    a bounded timeout; restart cannot leave an in-flight Calendar sync writing
    after shutdown begins.

---

## Live Observation Gate

Calendar v1 may not close on unit tests alone. After implementation and
operator-approved OAuth onboarding, closure requires live observation:

- daemon heartbeat remains healthy;
- M1 remains enabled and staleness stays ok;
- credential source remains Decision-26 compliant;
- Calendar connector reaches healthy or intentional unavailable state;
- direct owner Calendar question returns only S2-approved redacted facts;
- non-direct conversation does not trigger Calendar reads;
- no proactive Calendar alert fires;
- no raw Calendar content appears in logs, health, metrics, panel, prompt
  envelope, or committed docs;
- shutdown remains clean;
- no token appears in process list, URL, argv, logs, or subprocess env;
- at least one incremental sync succeeds after initial sync;
- a simulated `410 Gone` preserves tombstone/audit sidecars.

Observation should run for at least one week or until the review packet defines
a stricter closure window.

---

## Non-Goals

- No live OAuth in this spec.
- No code in this packet.
- No Calendar descriptions.
- No proactive reminders.
- No shared/work/family/delegated calendars.
- No push notifications.
- No Calendar memory promotion.
- No TRF widening.
- No body-state inference.
- No crisis bypass.
- No Rekor/public transparency logging.
- No connector-specific credential loader.

---

## Plain English

Calendar v1 is Maez's first real customs inspection.

The old Calendar wire let event titles and locations walk straight into Maez's
mouth. That was acceptable scaffolding when Maez was smaller; it is not
acceptable now that S2, M1, and the credential vault exist. Calendar is private
external evidence. It is not Maez's memory, not Maez's schedule, and not a
license to remind or nudge Rohit.

So v1 is deliberately small. It reads only the primary owned calendar, only the
next 14 days, only through the vault, only through S2, and only answers when
Rohit directly asks. Descriptions are out. Proactive alerts are out. Shared
calendars are out. Push webhooks are out. If Calendar breaks, Maez says it
cannot see a current calendar view; it does not sneak back through the old raw
path.

In kid terms: Calendar is a guest notebook. Maez can look at the safe parts
when Rohit asks, but it cannot swallow the notebook, call it memory, or start
bossing him around from it.
