# Calendar v1 Diagnostic

Status: DIAGNOSTIC ONLY
Date: 2026-05-15
Maps to: Decision 27 / ADR 0032 (S2 Contextual Integrity at Ingest), Decision 26 / ADR 0031 (Daemon Credential Hygiene), Decision 25 / ADR 0030 (M1 Lived-Episode Promotion)

## Purpose

Calendar v1 is the first information-limb implementation candidate after S2 became canonical. This diagnostic maps Google Calendar's actual API surface and Maez's existing legacy calendar path before drafting any Calendar spec.

This document is intentionally not a spec and not an implementation plan. It records what is true now, what Google Calendar exposes, and where the future Calendar v1 contract must obey or sharpen S2.

## Diagnostic Guardrails

- No real OAuth flow was run for this diagnostic.
- No live Google Calendar API call was made.
- No operator calendar titles, attendees, descriptions, locations, email addresses, or token values are quoted here.
- Existing local OAuth files were inspected for key shape only, never for values.
- Decision 27 / ADR 0032 is used as the lens. If Google Calendar reality does not fit the S2 law-shape cleanly, the Calendar v1 spec must say so rather than hiding the mismatch.

## Evidence Sources

Local code and docs:

- `skills/calendar_perception.py`
- `skills/calendar_cache_worker.py`
- `daemon/maez_daemon.py`
- `pyproject.toml`
- `docs/slices/s2-contextual-integrity-at-ingest/spec.md`
- `docs/audits/2026-05-04-symphony/S2_operational_noise.md`
- `docs/N1_OPERATIONAL_NOISE_TRIAGE.md`

Provider docs:

- Google Calendar API sync guide: https://developers.google.com/workspace/calendar/api/guides/sync
- Google Calendar `events.list`: https://developers.google.com/workspace/calendar/api/v3/reference/events/list
- Google Calendar event resource: https://developers.google.com/workspace/calendar/api/v3/reference/events
- Google Calendar scopes: https://developers.google.com/workspace/calendar/api/auth
- Google Calendar push notifications: https://developers.google.com/workspace/calendar/api/guides/push
- Google Calendar API errors: https://developers.google.com/workspace/calendar/api/guides/errors
- Google OAuth web-server flow: https://developers.google.com/identity/protocols/oauth2/web-server

## Existing Maez Calendar Path

Maez already has a pre-S2 Calendar path. Calendar v1 must treat it as legacy surface evidence, not as a safe base to preserve unchanged.

`skills/calendar_perception.py` currently:

- Uses `https://www.googleapis.com/auth/calendar.readonly`.
- Loads OAuth token data from `config/token.json`.
- Loads client config from `config/credentials.json`.
- Refreshes expired access credentials and writes the refreshed credential JSON back to `config/token.json`.
- Calls `events().list(calendarId="primary", timeMin=..., timeMax=..., singleEvents=True, orderBy="startTime", maxResults=20)`.
- Parses `summary`, `start`, `end`, `location`, `description`, and `id`.
- Emits raw title and location through `CalendarEvent.format_for_context()`.
- Emits raw titles through `CalendarSnapshot.format_for_memory()`.
- Supports Telegram/voice alerts 15 and 5 minutes before an event.

`daemon/maez_daemon.py` currently:

- Imports `calendar_observe` directly from `skills.calendar_perception`.
- Appends `CalendarSnapshot.format_for_context()` directly into the daemon prompt when a snapshot exists.
- Calls `calendar_observe()` inside the reasoning cycle every Calendar cadence.
- Sends Telegram and speech alerts containing event title and location.
- Appends `format_for_memory()` output into the cognition scoring text.

`skills/calendar_cache_worker.py` exists as a staging-only bounded worker and says it is not registered with `maez.service`. It is useful prior art for bounded worker shape, but it does not replace the active direct daemon path.

### Diagnostic Conclusion: Legacy Path Is S2-Incompatible

The existing path violates the Calendar v1 target posture in multiple ways:

- It puts raw Calendar text into prompt context before S2 classification.
- It can send alert text that sounds like co-experiencing or scheduler voice.
- It writes token refresh state outside `core/infra/secrets.py`.
- It has no S2 envelope, consent-tier computation, redaction policy, keyed attendee hash, tombstone sidecar, or flow-policy version binding.
- It has no structural separation between provider facts and Maez biography.

Calendar v1 should replace this path behind a new S2-shaped ingest boundary. It should not merely add checks around the existing `format_for_context()` and alert behavior.

## Local Credential Surface

Local credential files exist and are gitignored:

- `config/token.json`
- `config/credentials.json`
- `config/token.json.invalid_grant.*`

The files were inspected for schema keys only. Observed key shapes:

- OAuth token record keys: `account`, `client_id`, `client_secret`, `expiry`, `refresh_token`, `scopes`, `token`, `token_uri`, `universe_domain`.
- OAuth client config keys: `auth_provider_x509_cert_url`, `auth_uri`, `client_id`, `client_secret`, `project_id`, `redirect_uris`, `token_uri`.

Decision 26 implication:

- Calendar v1 must not keep refreshed access or refresh tokens in ad hoc JSON files as the authoritative credential store.
- Refresh-token rotation must go through `core/infra/secrets.py` or a Decision-26-compliant extension to it.
- Any compatibility file, if temporarily needed for the Google client library, must be generated from the secret interface into a locked local runtime location and must never become the source of truth.

## Google OAuth Surface

Google's OAuth docs confirm:

- Offline access is the shape for a daemon that needs to read Calendar while the operator is not actively authorizing each request.
- Refresh tokens are obtained when requesting offline access and are then used to acquire new access tokens.
- The client library can refresh access tokens on API calls once credentials are set.
- The example docs demonstrate token printing and local client-secret files as developer examples; Calendar v1 must not inherit those example habits.

Maez-specific implication:

- The Calendar implementation must classify auth failures into the S2 states already named by Decision 27: `auth_access_expired`, `auth_refresh_revoked`, and `auth_scope_downgraded`.
- Refresh-token write-back is a load-bearing implementation point, not plumbing. If Google returns a new refresh token or materially different granted scopes, the update must pass through Decision 26 interfaces.
- Access tokens must not be placed in URLs. Authorization headers are the only acceptable request shape for bearer credentials.

## Calendar Scope Surface

Google Calendar offers multiple scope widths, including:

- Full calendar access.
- Calendar readonly access.
- Free/busy access.
- Event readonly access.
- Owned-event scopes.
- Public-event readonly access.

Existing Maez code uses broad `calendar.readonly`, which can see and download any calendar the account can access. Calendar v1 should not assume this is the final minimal scope.

Spec question:

- Is v1's source profile "primary owned calendar events only" implementable with a narrower scope and calendar selection policy, or does the Google API/library force broader visibility at the credential level while Maez enforces a narrower S2 selection layer?

## Sync Model

Google's sync model has two stages:

- Initial full sync obtains a `nextSyncToken`.
- Later incremental syncs provide the previous sync token and persist the new one from the response.

Provider details that matter for Calendar v1:

- Incremental sync responses include deleted entries so clients can remove local copies.
- Paginated incremental sync can return `nextPageToken` before the final `nextSyncToken`; the final sync token appears only after paging completes.
- Query parameters for incremental sync are restricted and must match the initial query shape.
- A `410 Gone` means the sync token is invalid and the client should clear its local synced store and perform a new full sync.
- Cancelled recurring-event exceptions and deleted events have different retention semantics. Some cancelled event details may remain visible on organizer calendars, but deleted events may eventually disappear.

S2 implications:

- Calendar v1 needs provider revision state, sync token state, and tombstone/audit sidecar state.
- Tombstones cannot be treated as ordinary deletion if they are needed for audit survivability.
- Provider timestamps must remain authoritative for event revision semantics; `received_at` is ingestion evidence only.
- The spec must define what happens when `410 Gone` forces local resync. A full wipe of the provider cache must not wipe the audit trail or provenance sidecars.

## Event Payload Surface

Google Calendar events combine structured facts and free-text fields.

Structured or semi-structured fields include:

- Event id, recurring event id, iCal UID.
- Status, created timestamp, updated timestamp.
- Start/end date or date-time, timezone.
- Organizer and creator records.
- Attendees.
- Visibility and transparency.
- Recurrence and recurring-instance fields.
- Conference data, attachments, reminders, extended properties.
- Working-location properties and event-type-specific properties.

Free-text or human-authored fields include:

- Summary/title.
- Description.
- Location.
- Attachment titles.
- Conference names or entry points.
- Custom working-location labels.
- Extended properties.

Third-party-bearing fields include:

- Attendee names and emails.
- Organizer and creator fields.
- Title/location/description strings that can contain names or body-adjacent details.
- Conferencing links and external attachment metadata.

Diagnostic conclusion:

- Calendar is not one privacy class. It is a mixed source where safe-looking fields can carry sensitive third-party identity.
- S2's rule that Calendar v1 computes consent tier and sensitivity inside Maez, not in the connector, is required by provider reality.
- Title and location require deterministic redaction/scrubbing before prompt context or audit surfaces.
- Description should be excluded from v1 prompt context by default. It is too injection-shaped and too likely to carry body-adjacent detail.

## Push Notification Surface

Google Calendar supports push notifications for events, but push is not a free replacement for sync:

- Push requires an HTTPS webhook callback.
- Each watched resource needs a notification channel.
- Channel setup includes channel id, webhook address, optional channel token, and optional expiration.
- Google says channel tokens must not include sensitive data such as OAuth tokens.
- Notifications contain headers and do not include the changed event body; the client must make another API call to get change details.
- Channels expire and must be replaced; there is no automatic renewal.

Calendar v1 implication:

- Polling with incremental sync is the simpler v1 shape.
- Push/webhook can be a v2 seam after Calendar v1 has a safe S2 ingest pipeline.
- If push is ever implemented, channel tokens fall under Decision 26 identity-bearing material rules and must not carry secrets or raw calendar content.

## Error Surface

Google Calendar errors relevant to v1:

- `400` permanent request errors: fix request shape; do not retry blindly.
- `401` invalid credentials: get a new access token through the refresh token; if refresh fails, route operator reauthorization.
- `403` user rate limit or rate limit exceeded: use exponential backoff.
- `429` rate limit exceeded: same backoff posture as 403 rate limiting.
- `500` backend error: retry with exponential backoff.
- `410` sync token invalid: clear synced provider cache and run full sync, while preserving audit sidecars.

S2 state implication:

- `401` is not one state. Calendar v1 must distinguish access-token expiry, refresh-token revocation, and scope downgrade where provider/library evidence allows it.
- Rate-limit failures should degrade to stale/unavailable, not hallucinated Calendar certainty.
- Provider errors should be logged as state classes and reason categories, not raw provider payloads if they might include sensitive request details.

## Existing Library Behavior

Installed library inspection confirms:

- `google.oauth2.credentials.Credentials.refresh(request)` mutates the credentials object.
- `Credentials.to_json(strip=None)` serializes credential state.
- `Credentials.__init__` can receive token, refresh token, scopes, granted scopes, client id, client secret, token URI, expiry, and account.
- `googleapiclient.discovery.build(..., credentials=..., cache_discovery=...)` accepts a credential object.

Implications:

- Calendar v1 can construct Google credential objects from Decision-26 secret material without making `config/token.json` the source of truth.
- The write-back seam is explicit: after refresh, credential state must be diffed and persisted through `core/infra/secrets.py` if refresh-token or grant state changed.
- Discovery/cache behavior should be configured intentionally. No credential-bearing URL construction is needed.

## Existing Maez Audit Trail

Prior Maez docs already classify Calendar as operationally noisy:

- Historical `invalid_grant` errors were treated as owner reauthorization/backoff noise.
- An untracked security audit hold notes that ambient Calendar text reaching prompts is an injection risk.

Diagnostic conclusion:

- Calendar v1 is not a new feature from a blank slate. It is a replacement of a known noisy, pre-S2 path.
- The spec should include a migration step that disables or gates the old daemon direct path before enabling the S2 path.

## S2 Mapping

Calendar v1 should inherit these S2 rules directly:

- Maez computes `consent_tier`; the connector reports provider facts only.
- Attendee identifiers are keyed-HMAC or redacted, not raw local audit strings.
- Third-party names and body-adjacent details in title/location are scrubbed or redacted.
- Schema version mismatch is a rejection, not best-effort parsing.
- Tombstones survive provider cache reset.
- TRF can see only S2-approved, source-anchored Calendar facts, never raw provider payloads.
- Calendar-to-biography promotion inherits M1's structural-summary-only rule from ADR 0030.
- Token-in-URL is forbidden.
- OAuth lifecycle states are split.
- Refresh-token rotation goes through Decision 26.
- Provider timestamps are authoritative for source revision.

## Spec-Stage Questions

1. Minimal scope: should Calendar v1 request `calendar.events.readonly`, `calendar.events.owned.readonly`, `calendar.freebusy`, or keep `calendar.readonly` while enforcing a narrower local selection policy?
2. Calendar selection: is v1 limited to primary calendar only, owner-selected calendars only, or all calendars visible under the selected credential with source-profile filtering?
3. Full sync horizon: what time window is allowed for initial full sync? A smaller window limits privacy blast radius but may miss recurrence/tombstone context.
4. Sync-token invalidation: on `410 Gone`, what exact state is cleared and what audit/tombstone sidecars must survive?
5. Token refresh: what Decision-26 interface owns refresh-token write-back, and how does rollback work if the writer fails?
6. Description field: is it entirely forbidden in v1, or stored in quarantined raw provider cache with no prompt/biography flow?
7. Alerts: should v1 ship no proactive alerts at all, or only S2-approved content-free availability notices after operator consent?
8. Web UI: what safe Calendar status can the project panel show without leaking titles, names, or locations?
9. Migration: should legacy `skills.calendar_perception` be disabled immediately once Calendar v1 lands, or kept only behind an explicit fallback flag?
10. Push notifications: should v1 explicitly defer push/webhook to v2 and require polling-only incremental sync?

## RED-First Tests Suggested by Diagnostic

The spec should decide the exact test list, but this diagnostic surfaces these necessary red tests:

- Legacy direct path is disabled or gated when Calendar v1 is enabled.
- Calendar connector cannot set `consent_tier`.
- Raw title, location, description, attendees, organizer, and conference URL cannot reach prompt context by default.
- Third-party identity in title/location is scrubbed or redacted.
- Description field is excluded from v1 prompt context.
- Attendee local audit identity is keyed-HMAC, not raw email/name.
- Calendar tombstone survives provider cache wipe after sync-token invalidation.
- `410 Gone` triggers provider-cache resync without audit-sidecar deletion.
- Refresh-token write-back goes through Decision 26 interface.
- Token-in-URL construction is impossible or scanner-forbidden.
- Authorization header path is used for access tokens.
- Subprocess environment is sanitized if any OAuth helper subprocess exists.
- Provider `updated` timestamp wins over local `received_at` for source revision.
- `401`, refresh revocation, scope downgrade, `403`/`429`, `500`, and `410` map to distinct observable state classes.
- Push notification channel token cannot contain sensitive material if push is ever enabled.

## Non-Goals For This Diagnostic

- No OAuth onboarding flow.
- No live Google API call.
- No Calendar spec.
- No code change.
- No S2 fold change.
- No real Calendar content in committed docs.
- No migration of existing token files.
- No project-panel Calendar UI.

## Plain English

Google Calendar is not a neat little "what time is my meeting?" pipe. It is a mixed bag: times and statuses are structured, but titles, locations, descriptions, attendees, conference links, and organizer fields can carry private human details. Some safe-looking entries can reveal someone else's life.

Maez already has an old Calendar path, but it is pre-S2. It reads Calendar, puts raw titles and locations into Maez's prompt, can send meeting reminders in Maez's voice, and refreshes OAuth tokens through local JSON files. That was useful early wiring, but it is not the shape we should build on.

Calendar v1 should be a replacement organ: Google Calendar data comes in, S2 classifies and redacts it, Decision 26 handles credentials, M1 rules prevent raw event text from becoming biography, and Maez can answer direct owner questions from safe grounded facts. The customs office has to sit before the mouth, before memory, and before alerts.
