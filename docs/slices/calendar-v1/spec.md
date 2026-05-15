# Slice Calendar v1: S2-Bounded Google Calendar Ingest

**Status:** DRAFT SPEC. Built from [`diagnostic.md`](diagnostic.md) and
post-diagnostic covenant guidance. No code has landed from this packet.

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
- events owned by that calendar/account;
- occurrences overlapping the 14-day forward horizon.

If Google returns records from calendars or ownership contexts outside v1
selection, the connector rejects them before S2 envelope construction and emits
only content-free rejection counters.

---

## Sync Contract

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

Description is not a "quarantined prompt-denied field" in v1. It is dropped at
the connector boundary after any content-free sensitivity flags are computed.

---

## S2 Envelope Contract

Every accepted Calendar record becomes an S2 envelope with:

- `schema_version`;
- `source_kind = "calendar.event"`;
- `source_profile = "google_calendar_primary_owned_v1"`;
- `provider = "google_calendar"`;
- `source_id_internal`;
- `source_handle_telemetry`;
- `received_at`;
- provider `created`;
- provider `updated`;
- `flow_policy_version`;
- `consent_tier` computed by Maez;
- `requested_flows`;
- `granted_flows`;
- sensitivity class;
- third-party posture;
- retention class;
- tombstone status;
- audit sidecar pointer.

Connectors may request flows and report provider facts. They may not compute:

- `consent_tier`;
- final sensitivity class;
- final third-party posture;
- final granted flows;
- promotion eligibility.

Schema version mismatch is fail-closed. Unknown future provider fields are
ignored unless a reviewed spec update admits them.

---

## Sensitivity And Redaction

Title and location are treated as untrusted free text.

Allowed title/location output tokens:

- `[calendar event]`;
- `[redacted calendar detail]`;
- `[sensitive calendar detail]`;
- `[redacted third-party calendar detail]`;
- deterministic safe category labels explicitly approved by S2 policy.

Forbidden title/location behavior:

- passing raw strings to model prompt;
- passing raw strings to memory/scoring text;
- passing raw strings to logs/health/panel;
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

- keyed HMAC handle when stable audit continuity is required;
- no raw attendee name/email in committed docs, logs, health, metrics, or panel;
- HMAC key from Decision-26 secret interface.

Attendee HMAC handles are not a people index. They are audit continuity handles
only and must not be used to build third-party profiles.

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

A direct owner request is an utterance whose main ask is to inspect Calendar
state or plan from explicitly requested Calendar data.

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

Compatibility files are allowed only as generated runtime artifacts if the
Google client library forces a file-shaped input. They must be:

- derived from the secret interface;
- `0600`;
- outside committed state;
- not the source of truth;
- deleted or overwritten safely when stale.

---

## Storage Contract

Calendar v1 storage is noncanonical.

Suggested storage classes:

- provider mirror table;
- sync state table;
- tombstone sidecar table;
- audit event table;
- policy version table.

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
- conference links;
- OAuth token state beyond content-free lifecycle enum;
- provider error payloads that might include request details.

Project panel may show "Calendar connector: healthy/stale/auth needed" and
counts. It may not show event content.

---

## Legacy Path Migration

Calendar v1 implementation must disable the legacy path, not leave it as a
fallback.

Legacy surfaces to remove or gate cold:

- `daemon/maez_daemon.py` direct import of `calendar_observe`;
- direct `CalendarSnapshot.format_for_context()` prompt injection;
- direct `CalendarSnapshot.format_for_memory()` cognition scoring append;
- Telegram/speech alert path using raw event title/location;
- token refresh through `config/token.json`;
- `skills/calendar_perception.py::test()` live OAuth convenience path, unless
  moved behind explicit developer-only guard and Decision-26 credential source.

Failure behavior:

- if Calendar v1 is disabled, Calendar is absent;
- if Calendar v1 auth fails, Calendar is unavailable;
- if Calendar v1 sync fails, Calendar is stale/unavailable;
- no failure path may invoke legacy raw Calendar prompt/alert behavior.

---

## Review Protocol

Calendar v1 is covenant-shaped. Before implementation:

1. Codex six-agent engineering panel reviews this spec.
2. Claude six-role covenant council reviews this spec.
3. Findings are folded structurally into this spec.
4. Operator canonicalizes or explicitly holds.
5. Cooling-off applies before code unless operator logs an explicit waiver.

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

6. Connector cannot set `consent_tier`.
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
15. Events outside the 14-day forward window are rejected or expired.

### Redaction And Third-Party Posture

16. Raw title cannot reach prompt context.
17. Raw location cannot reach prompt context.
18. Description cannot be stored or prompted.
19. Attendee names/emails cannot reach prompt, logs, health, metrics, or panel.
20. Third-party identity in title/location redacts.
21. Body-adjacent detail in title/location redacts.
22. Ambiguous title/location redacts.
23. Attendee audit handle uses keyed HMAC from Decision 26.
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
