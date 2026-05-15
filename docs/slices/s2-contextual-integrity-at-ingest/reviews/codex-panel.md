# S2 Contextual Integrity at Ingest — Codex Engineering Panel Review

**Subject:** `docs/slices/s2-contextual-integrity-at-ingest/scoping.md`

**Review stage:** pre-BAD scoping memo, after Claude council pre-panel
clarifications were folded.

**Date:** 2026-05-14

**Verdict:** REVISE. No veto / no block on S2 as the next architectural
thread.

The seven-dimension shape is the right architecture for S2, Calendar remains
the right first downstream information limb, and the memo is correctly scoped
as law-before-connector. The panel's revise verdict is about two load-bearing
precision issues that must not enter the full BAD packet ambiguously:

1. S2 must not redefine canonical consent-tier labels from Decision 2.
2. S2 must pin default flow and retention posture before any information limb
   can ingest live data.

---

## Seat Verdicts

| Seat | Verdict | Core finding |
|---|---|---|
| Dewey | RATIFY-WITH-AMENDMENTS | Keep Calendar v1 small; do not let provenance purity or future Gmail/Slack needs make first ingest heavy. |
| Feynman | RATIFY-WITH-AMENDMENTS | Add exact data-flow/state-machine mechanics so "customs officer" becomes testable behavior. |
| Locke | REVISE | Consent-tier naming and deletion semantics are memory law, not wording details. |
| Descartes | REVISE | The draft still has false-safety risks in default flow, retention, and "Calendar is low blast radius" framing. |
| Ohm | RATIFY-WITH-AMENDMENTS | Convert S2 into daemon-safe contracts: one envelope, bounded cache, idempotent sync, bounded backfill, fail-neutral telemetry. |
| Goodall | RATIFY-WITH-AMENDMENTS | Calendar can pass API tests and still feel too schedule-aware; add longitudinal observation gates. |

Overall panel verdict follows the strictest substantive lane: REVISE.

---

## Load-Bearing Revisions

### S2-CX-L1 / S2-CX-DC1 — Preserve Decision 2 consent labels

The scoping memo says it inherits Decision 2, but then uses S2-local Tier 0 /
Tier 1 / Tier 2 meanings for owner-only, unconsented third-party observable
data, and inter-Maez consent. That conflicts with canonical Decision 2.

**Required revision:** preserve Decision 2 tier labels exactly. Add S2-local
posture labels instead, for example:

- `owner_only`
- `third_party_observable_no_consent`
- `third_party_explicit_consent`
- `inter_maez_consented`

If a Tier 0-like owner-only shorthand remains, it must be explicitly marked as
S2-local and not a Decision 2 consent tier.

### S2-CX-DC2 — Resolve minimal-predicate sequencing as path A

The scoping memo now declares full-S2-BAD-first as the intended path, but still
frames the panel question as whether to recommend the smaller predicate path.

**Required revision:** make the current operator-facing path unambiguous:
Calendar cannot proceed until the full S2 BAD is canonicalized, unless the
operator explicitly reopens Rule 7 and chooses a minimal predicate in a later
decision.

### S2-CX-DC3 — Default allowed flow should be no Maez-visible flow

The current default of `flow.bounded_window_recall` is not obviously safer than
prompt context. It may make Calendar facts available to recall-like behavior
before voice posture and retention are settled.

**Required revision:** default to provenance/read-model storage only. Calendar
must explicitly grant any Maez-visible flow, starting with
`flow.prompt_context.grounded_only` for direct user requests. Bounded recall
should require a TRF-style approved retrieval posture.

### S2-CX-L2 / S2-CX-DC4 — Pin v1 retention before ingest

The memo lists mirror-source TTL, fixed TTL, per-event TTL, and permanent
noncanonical cache. Permanent noncanonical cache conflicts with the cache-vs-
memory distinction.

**Required revision:** v1 noncanonical ingest cache defaults to mirror-source
TTL plus a short content-free tombstone / audit marker. Promoted lived memory
is never silently deleted; if its source is later deleted, preserve the memory
with provenance tombstone fields.

### S2-CX-L3 — Remove permanent noncanonical cache as a v1 option

**Required revision:** v1 cache classes may be TTL, mirror-source, or
tombstoned. Permanent retention is only available after explicit promotion to
lived memory.

### S2-CX-DC5 — Calendar is lower-blast-radius, not low-blast-radius

Calendar titles, attendees, locations, recurrence, and links can expose
therapy, medical care, religion, politics, employment, home addresses, and
third-party relationships.

**Required revision:** keep Calendar-first, but frame it as lower risk than
Gmail/Slack, not intrinsically low risk. Add sensitivity defaults:

- no descriptions, attachments, or video-link content,
- attendee minimization unless directly needed,
- high-sensitivity title/location redaction,
- tests for medical, legal, therapy, third-party, and location-sensitive
  events.

---

## Engineering Amendments for the Full BAD Packet

### S2-CX-D1 — Keep Rekor / attestation as a seam, not a v1 blocker

The BAD should define tamper-evident provenance fields and an attestation
extension point. Calendar v1 should be allowed to ship with local DB integrity
plus audit log. Public transparency infrastructure should not block first
ingest.

### S2-CX-D2 — Pin Calendar v1 to no promotion implementation

Calendar v1 produces provenance records only. Promotion triggers are law for
later slices, not Calendar v1 work.

### S2-CX-D3 — Narrow first executable contract to `calendar.event`

The broader source-kind catalog is useful as law. First schemas and tests cover
only `calendar.event`; mail/chat/doc/code remain placeholders until their own
slices.

### S2-CX-D4 — Avoid per-attendee operator consent in Calendar v1

Per-attendee consent is too much ceremony for first ingest. Use a constrained
Tier-1-equivalent posture: relational/provenance metadata only, no
personological inference, no nudging/contact, and blocked voice exposure unless
an allowed flow explicitly permits it.

### S2-CX-D5 — Define a small mandatory S2 probe set

Minimum RED-first fixtures for v1:

- owner-only Calendar event allowed,
- attendee event constrained,
- description/body rejected,
- unconsented flow rejected,
- promotion without reviewed trigger rejected.

### S2-CX-F1 — Define the exact S2 state machine

Add ordered flow:

`external source -> connector fetch/webhook -> S2 envelope validation -> noncanonical ingest cache -> allowed-flow read model -> recall/prompt consumer OR promotion gate -> lived memory`

Allowed terminal states:

- `rejected`
- `cached`
- `expired`
- `flow_blocked`
- `promotion_pending`
- `promoted`

### S2-CX-F2 — Define the v1 ingest boundary

v1 S2 governs inbound fact extraction and inbound pushed facts. Outbound
effector actions stay outside S2 except that they must not consume unvalidated
S2 records.

### S2-CX-F3 — Name the noncanonical cache record schema

Required fields:

- `ingest_record_id`
- `source_kind`
- `source_instance_id`
- `external_event_id`
- `observed_at`
- `received_at`
- `expires_at`
- `consent_tier`
- `third_party_posture`
- `allowed_flow_ids`
- `promotion_state`
- `provenance`
- `redaction_state`

Locke adds rollback/debug fields:

- `fetch_batch_id`
- `connector_version`
- `schema_version`
- `raw_field_policy_version`
- `promotion_record_id`

### S2-CX-F4 — Convert flows into enforceable read permissions

Add a flow table with:

- `flow_id`
- `consumer`
- `readable_fields`
- `user_visible_allowed`
- `voice_posture`
- `promotion_allowed`

### S2-CX-F5 — Separate promotion eligibility from promotion execution

S2 may mark records `promotion_eligible` with reason and provenance handle. A
separate reviewed memory-write path performs actual promotion.

### S2-CX-O1 — Inherit Body Bus envelope with source-specific facts

S2 records use the canonical Body Bus envelope fields, then constrain `facts`
by `source_kind`. Distinct envelopes would duplicate idempotency and replay
semantics.

### S2-CX-O2 — Add cache budget and eviction contract

Each source must declare max rows, max bytes, max event age, compaction cadence,
and behavior when full. Default: fail-closed for promotion and fail-neutral for
prompt context.

### S2-CX-O3 — Calendar sync cadence: pull-first, attention-budgeted, idempotent

Prefer bounded pull / sync-token fetch for v1. Webhooks are later and must
enter the same envelope, auth, replay, and rate-limit path.

Idempotency key:

`source_kind + source_instance_id + external_event_id + source_revision`

### S2-CX-O4 — Backfill is a separate mode and budget

Backfill requires lookback window, page limit, time budget, resumable cursor,
dry-run/count mode, and no-promotion-during-backfill default.

### S2-CX-O5 — Source outage and observability are content-free

Connector states:

- `disabled`
- `auth_expired`
- `rate_limited`
- `source_unavailable`
- `stale`
- `sync_lagged`
- `rejected`

Counters only:

- accepted / rejected / deduped / backfilled / expired / promoted,
- sync lag,
- last success age,
- cache occupancy,
- per-source rate-limit state.

No event titles, attendees, subjects, descriptions, or message headers in
logs.

### S2-CX-G1 — Calendar burn-in observation gate

Before Calendar can become precedent for Gmail/Slack, require an observation
log covering prompt category, source kind, allowed flow, whether Maez
volunteered the fact or only answered, operator weirdness label, contamination
concern, and promote/hold decision.

### S2-CX-G2 — No ambient schedule personality

Calendar facts must not change Maez's conversational initiative unless a later
slice explicitly grants an attention-budgeted notification or briefing flow.

### S2-CX-G3 — Negative controls for subtle autobiographical contamination

Add probes where Calendar exists but Maez must not:

- say "I remember,"
- treat attendance as witnessed experience,
- infer why an event mattered,
- carry a deleted/cancelled event into lived recall unless separately promoted
  through conversation.

### S2-CX-G4 — Changed/deleted event weirdness criterion

Calendar v1 must test and observe modified, cancelled, and deleted events
before Gmail/Slack promotion.

### S2-CX-G5 — Promotion-to-next-source criteria

Before Gmail/Slack:

- zero raw-body leaks,
- zero ungrounded "I remember" claims,
- no third-party personological drift,
- no recurring operator-rated weirdness,
- successful changed/deleted-event handling across Calendar burn-in.

---

## What Ratifies Cleanly

- S2 is the right next architectural move after Body Topology.
- Calendar remains the right first information limb.
- The seven-dimension structure is useful and should carry into the full BAD.
- S2 should be law-before-connector, not OAuth implementation.
- Information-limb records must stay distinct from autobiographical memory
  until reviewed promotion.
- Customs-officer metaphor is helpful, as long as the BAD also defines the
  state machine and record schema.

---

## Required Next Step

Revise the scoping memo before drafting the full S2 BAD:

1. Fix consent-tier terminology to preserve Decision 2.
2. Make full-S2-BAD-before-Calendar the explicit path.
3. Change default allowed flow to provenance/read-model storage only.
4. Pin v1 retention to mirror-source TTL plus tombstones.
5. Reframe Calendar as lower-blast-radius with sensitivity defaults.

After that revision, the full S2 BAD packet can draft with both review trails
as inputs.

---

## Plain English

The panel agrees S2 is the right next organ. The problem is not the idea; the
problem is that a few words in the draft would become dangerous if they became
law.

The biggest one: S2 cannot rename the consent tiers. Maez already has a consent
model. S2 must inherit it, not create a second one.

The second biggest: Calendar is safer than Gmail and Slack, but it is not
harmless. A calendar can reveal therapy, health, religion, work, home location,
and relationships. So Calendar is still the first teacher, but it needs gloves
on.

The third: no external fact should become Maez-visible by default. First it
lands as provenance. Then a slice grants a specific flow. Then, much later and
only through reviewed gates, it can become memory.

This is a revise, not a rejection. The border-law shape is right. The draft just
needs sharper locks before it becomes the full S2 BAD packet.
