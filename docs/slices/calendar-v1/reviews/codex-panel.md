# Calendar v1 Spec — Codex Engineering Panel

Date: 2026-05-15
Spec reviewed: [`../spec.md`](../spec.md) at `aa9a805`
Diagnostic: [`../diagnostic.md`](../diagnostic.md)

## Verdict

**REVISE before implementation.**

No panel seat vetoed the core covenant posture. The spec correctly treats
Calendar as S2-bounded external provenance, blocks proactive reminders, rejects
legacy fallback, and inherits Decision 26 credential handling. The revision is
required because the first draft still leaves implementation ambiguity in six
engineering seams:

1. canonical S2 envelope/state fidelity;
2. privacy/audit leakage through descriptions, HMAC handles, and raw IDs;
3. Google incremental-sync constraints;
4. deterministic voice/flow enforcement;
5. credential lifecycle and rollback precision;
6. complete legacy-path disablement, including fast-lane/cache-worker paths.

## Seat Verdicts

| Seat | Verdict | Headline |
| --- | --- | --- |
| Schema/State | REVISE | Calendar envelope must use canonical S2 fields exactly; storage and state machine are not executable enough. |
| OAuth/Credential | REVISE | Auth taxonomy, refresh-token write-back, access-token memory-only behavior, compatibility-file rules, and rollback need sharper contract. |
| Runtime/Daemon Migration | REVISE | Legacy disablement must cover daemon import, cache worker, fast-lane prompt rendering, UI claims, and worker shutdown lifecycle. |
| Privacy/Third-Party | REVISE | Description/body handling, attendee HMAC scope, raw source IDs, "safe token" wording, ownership oracle, and "who" requests need locks. |
| Flow/Voice | REVISE / RATIFY-WITH-AMENDMENTS | Literal forbidden phrases are insufficient; Calendar answer generation needs deterministic composer/voice guard. |
| Sync/Provider API | RATIFY-WITH-AMENDMENTS | V1 overclaims 14-day sync with `syncToken`; provider sync continuity must be separated from local read-model horizon. |

## Load-Bearing Amendments

### CP-1 Canonical S2 Envelope

Calendar v1 must use the canonical S2 Body Bus envelope without abbreviation.
Calendar-specific aliases such as `consent_tier`, `requested_flows`, and
`granted_flows` are forbidden; use `decision2_consent_tier`,
`requested_flow_ids`, and `granted_flow_ids` exactly.

### CP-2 Required Store Schema And Sync State

Calendar storage classes are required, not suggested. Each table needs a
`calendar_store_schema_version`. Unknown/incompatible schema blocks connector
startup fail-neutral. Sync state needs `source_instance_id`,
`query_shape_hash`, protected sync-token state or secret reference, page
checkpoint, success/attempt timestamps, connector state enum, content-free
error class, and prompt-context staleness policy.

### CP-3 State Machine And Idempotency

Calendar v1 inherits the S2 transition table exactly. Illegal transitions
reject content-free. Idempotency is keyed on source kind, source instance,
external event id, and source revision. Same key plus identical facts dedupes;
same key plus conflicting facts rejects without updating mirror or read model.
Older provider revisions cannot overwrite newer revisions.

### CP-4 Tombstone Sidecar Completeness

Provider mirror rows may be deleted/compacted only after a content-free
tombstone sidecar is durably written. Sidecar fields are strictly bounded and
must contain no raw title, location, attendee, organizer, description, or raw
provider ID.

### CP-5 Description/Body Drop

Description/body is not parsed, classified, scanned for sensitivity, logged,
stored, prompted, displayed, audited as text, or used to derive crisis or
sensitivity signals in Calendar v1. It is dropped immediately before policy
evaluation. A content-free `description_present` counter may exist but grants
no visible flow.

### CP-6 Attendee HMAC Scope

Attendee HMAC handles are purpose-scoped and event-lineage-scoped by default.
They must not become globally stable third-party identifiers across unrelated
events. Cross-event attendee joins require future Tier 1/2 consent and spec
amendment.

### CP-7 Raw Provider IDs And Safe Tokens

Audit-visible output must use telemetry handles or hashes, not raw provider
event IDs, calendar IDs, account labels, conference IDs, organizer IDs, or
attendee identifiers. "Safe title/location token" means redaction token or
deterministic category label, never raw provider text.

### CP-8 Ownership Oracle And "Who" Requests

Primary-calendar membership is necessary but insufficient. Calendar v1 needs a
provider-backed relation class and must still treat organizer, creator,
attendee, title, and location as third-party-bearing. Direct owner requests for
"who" do not grant raw attendee names through the model.

### CP-9 Provider Query Shape

The 14-day boundary is a local Maez-visible read-model horizon, not a claim that
incremental provider sync can always use `timeMin`/`timeMax`. Incremental sync
with `syncToken` must obey Google `events.list` restrictions and may receive
out-of-horizon changes that are processed only for sync/tombstone continuity.

### CP-10 Cancelled Record Semantics

Cancelled recurring exceptions and deleted events are different shapes.
Recurring exceptions need recurrence-exception tombstones; ordinary deletions
may have only provider id. No cancelled record may rely on summary, location,
attendee, organizer, or description fields.

### CP-11 Deterministic Calendar Voice Guard

Calendar facts may reach owner-visible answers only through deterministic
Calendar answer composition or a deterministic post-generation
`calendar_voice_guard`. Literal phrase bans are insufficient; soft scheduler
personality, advice, prioritization, availability/busyness/stress framing, and
first-person co-actor framing must reject fail-neutral.

### CP-12 Direct Request And Free/Busy Boundary

Calendar reads require an explicit owner request for Calendar/schedule/event/
agenda/free-busy state. Free/busy answers describe only Calendar state, never
owner availability, focus, stress, capacity, location, or bodily/social state.

### CP-13 OAuth Lifecycle And Generated Files

Access tokens are runtime-only. Refresh tokens, client material, granted-scope
evidence, and rotation state are owned by `core/infra/secrets.py`. Generated
compatibility files, if unavoidable, must be outside `config/`, atomically
written, `0600`, never named `config/token.json`, and never authoritative.

### CP-14 Auth State Taxonomy And Rollback

Calendar v1 needs content-free auth/provider state classes and a rollback
section. Rollback disables Calendar v1 or restores Decision-26 secret state; it
never revives legacy raw Calendar prompt/alert behavior.

### CP-15 Process-Start-Strict Legacy Disablement

When Calendar v1 is enabled, daemon import must not import
`skills.calendar_perception`, `CalendarSnapshot`, or `calendar_observe`.
Feature flags checked after importing legacy code are insufficient.

### CP-16 Fast-Lane / Cache-Worker / UI Surface Closure

Legacy disablement must cover `skills/calendar_cache_worker.py`,
`scripts/fast_reply_cli.py --prime-perception`, fast prompt rendering,
perception-cache snapshots, static/local/public UI claims, morning briefing,
Telegram, speech, prompt, scoring, logs, health, and project panel paths.

### CP-17 Worker Lifecycle

Calendar polling workers must be bounded, stopped, and joined during daemon
shutdown. Restart must not leave an in-flight Calendar sync writing after
shutdown begins.

## Required Test Additions

The RED-first contract must add tests for:

- canonical S2 mandatory envelope field rejection;
- duplicate idempotency dedupe and idempotency conflict rejection;
- older provider revision cannot overwrite newer revision;
- illegal state transition rejection;
- `confidence` cannot encode lifecycle state;
- flow-policy-version changes cannot widen visibility;
- cache-full fail-neutral/fail-closed behavior;
- tombstone sidecar contains no content fields;
- max staleness missing/unparseable blocks visible reads;
- distinct state classes for access expiry, refresh revocation, scope downgrade,
  rate limit, backend error, source unavailable, and sync-token invalidation;
- incremental sync never combines `syncToken` with Google-forbidden filters;
- out-of-horizon incremental changes cannot enter read model;
- description/body is dropped before policy evaluation;
- event-lineage-scoped attendee HMAC behavior;
- raw source IDs absent from audit-visible output;
- "who" requests do not expose attendee identity through the model;
- Calendar answer guard rejects soft scheduler personality;
- planning talk does not imply Calendar lookup;
- free/busy absence is not owner availability;
- crisis-shaped title/location is held content-free without bypass;
- TRF/lived recall cannot read Calendar cache as memory;
- access tokens are memory-only unless runtime compatibility file is required;
- generated compatibility files cannot become `config/token.json`;
- refresh failure cannot overwrite valid refresh-token state;
- rollback cannot revive legacy Calendar prompt/alert behavior;
- daemon import with Calendar v1 enabled does not import legacy calendar module;
- fake legacy Calendar sentinel cannot appear in any prompt/alert/log/panel
  surface;
- Calendar worker shutdown is bounded and joined.

## Bottom Line

Calendar v1 has the right customs-office law. It needs a more exact customs
form before anyone writes code from it.

The panel's strongest finding is that the spec must not become a second,
Calendar-specific interpretation of S2. It must instantiate S2 exactly, with
Google-specific sync and OAuth reality folded underneath it.
