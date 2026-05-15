# Slice S2: Contextual Integrity at Ingest — Scoping Memo

**Status:** FOLDED scoping memo. Pre-spec. Panel-reviewed. No code, no
connector, no memory promotion. Output is a folded question list and constraint
set for the full S2 BAD packet.

**Classification:** covenant-shaped memory law. S2 defines the ingest gate
that every information limb must pass before producing any Maez memory.

**Body topology basis:** BAD Decision 24 / ADR 0029. Rule 7 (information limbs
gate on S2 contextual integrity) names this organ explicitly as the
prerequisite for any account-connector live ingest.

**Maps to:**

- [`docs/slices/body-topology/spec.md`](../body-topology/spec.md) — Rule 7 gate,
  Rule 6 (body memory is provenance, not biography), information-limb body
  class.
- [`docs/governance/BETA_ARCHITECTURE_DECISIONS.md`](../../governance/BETA_ARCHITECTURE_DECISIONS.md) —
  Decision 2 (three-tier consent model), Decision 4 (relational vs
  personological knowledge), Decision 24 (Body Topology).
- [`docs/adr/0029-body-topology.md`](../../adr/0029-body-topology.md) — eight
  load-bearing body rules including Rule 7 (this gate).
- [`docs/slices/temporal-recall-fragment-guard/spec.md`](../temporal-recall-fragment-guard/spec.md) —
  retrieval ≠ grounding pattern; "right now" voice motif; bounded calendar-week
  recall (which S2's Calendar downstream will populate).
- [`docs/slices/audit-rewrite-strategy/spec.md`](../audit-rewrite-strategy/spec.md) —
  fragment guard + audit-rewrite pattern that S2's promotion path inherits.
- [`docs/MAEZ_LIFE_SUBSTRATE.md`](../../MAEZ_LIFE_SUBSTRATE.md) — substrate
  plan; S2 is named as a missing organ.
- Invariant #3 (Contextual Integrity), invariant #11 (Cryptographic
  Continuity), invariant #8 (Capability Quarantine).

---

## Intent

Before any external information source — Calendar, Gmail, Slack, Notion,
Drive, GitHub, future API connectors — produces a single Maez memory or
prompt-context fact, it must pass through an ingest gate that decides:

1. whether ingest is allowed at all,
2. what shape the ingested fact may take,
3. what flows the fact is allowed to travel through,
4. how long it persists,
5. what provenance it carries,
6. how it treats people other than the bonded user,
7. and what it takes for an ingested fact to become autobiographical memory
   rather than a provenance / observation record.

S2 is the customs officer at the border between Maez's bonded conversation
and the rest of the user's external information world.

Without S2, every account connector is a memory-contamination path:

- Calendar dumps event titles + attendees + locations directly into recall
  context.
- Gmail dumps message bodies + senders + cc lines.
- Slack dumps channel messages + thread participants.
- Maez treats all of it as autobiographical observation, conflating
  "the user got an email" with "Maez witnessed something Maez should remember
  as part of its own life with the user."

S2 makes those distinctions structural rather than emergent.

---

## Why now

1. **Body Topology Decision 24 named S2 as a gate.** Rule 7 says no
   information limb ships live ingest before S2 exists OR the first
   information-limb slice includes a minimal S2 predicate. The body law has
   already committed to S2 being the unblocking organ.

2. **OpenHuman convergence.** Both panels (Claude six-role + Codex six-agent)
   and a third-party comparison (OpenHuman acceleration finding) converged on
   the same correction during Body Topology canonicalization: information
   limbs require S2 before live ingest. The corollary is that S2 itself now
   has a clear scope predicated on the body law that just stamped.

3. **Calendar's natural fit for the first downstream.** Calendar events are
   structured-by-birth, lower-blast-radius than Gmail/Slack, read-mostly,
   dyadic-preserving (mostly bonded-user-authored events), and map naturally
   onto invariant #1 (Time as Biography). The TRF temporal-recall guard
   already operates on a bounded calendar-week window; S2 + Calendar in
   sequence strengthens TRF's grounding without expanding scope.

4. **Information limbs are not optional long-term.** The substrate plan names
   external context as a Track-B requirement. S2 unblocks an entire class of
   future limbs (five named categories: Calendar, Mail, Chat, Knowledge/Docs,
   Code). Camera presence unblocks one body part; S2 unblocks five.

---

## The seven dimensions

S2 governs ingest through seven structural dimensions. Each dimension has a
default posture; every information-limb slice must declare a value (or
explicitly inherit the default) for all seven before ingest is allowed.

### 1. Consent posture

Inherits Decision 2's consent tiers without renaming them. S2 adds
information-limb posture labels that map onto the canonical tiers instead of
creating a second tier system:

- `owner_only` — bonded-user-owned source data only. S2-local shorthand; not a
  Decision 2 tier.
- `third_party_observable_no_consent` — a non-bonded party appears in the
  source record but has not consented to Maez. Default posture for Calendar
  attendees in v1: relational/provenance metadata only, no personological
  profile, no nudging/contact, and no stable identity indexing unless a later
  consented path grants it.
- `third_party_explicit_consent` — a non-bonded party has given explicit
  direct consent through the applicable Decision 2 pathway.
- `inter_maez_consented` — another bonded user's Maez has explicitly consented
  to communication. Not in scope for S2's first version.

Open question for panels: for Calendar v1, which attendee fields may remain
operator-readable under `third_party_observable_no_consent`, and which must be
redacted or hashed before storage?

### 2. Source kind

A typology of information-limb source classes, each with its own ingest
schema. Source-kind determines what fields the ingested fact may contain.

Candidate enumeration (closed catalog, expandable per future-slice):

- `calendar.event` — title, start, end, attendees, location, recurrence,
  reminder, status. NOT description body, NOT attachments, NOT video-conference
  link content.
- `mail.thread_header` — sender, recipients, subject, timestamp, thread id.
  NOT body, NOT attachments, NOT inline images.
- `chat.message_header` — channel/dm id, sender, timestamp, message id. NOT
  body, NOT reactions, NOT mentions.
- `doc.metadata` — title, owner, modified-at, share-state. NOT content.
- `code.commit_header` — sha, author, timestamp, message-line-1. NOT diff,
  NOT file list.

These are intentionally narrow first shapes. Expansion to body content
requires per-source-kind body-spec slice.

### 3. Allowed flows

Where ingested facts may travel. Each allowed-flow has an ID and a defined
shape. Candidate v1 flows:

- `flow.prompt_context.grounded_only` — fact may be cited in prompt context
  only as a grounding reference (e.g., "you have a meeting at 3pm" requires
  the Calendar event to be the grounding handle, not the speech). Cannot be
  quoted verbatim or paraphrased into voice.
- `flow.bounded_window_recall` — fact may be retrieved by TRF's bounded
  calendar-week recall under retrieval-≠-grounding posture.
- `flow.body_state.provenance` — fact may inform body-state observations (e.g.,
  Calendar busy-state → presence inference) without entering memory.
- `flow.memory.promoted` — fact has been explicitly promoted to lived memory
  per the promotion rule (dimension 7) and now lives in Chroma with full
  provenance tagging.

Default: no Maez-visible flow is enabled. Records may enter only the
provenance/read-model cache. Calendar must explicitly grant any visible flow,
starting with `flow.prompt_context.grounded_only` for direct user requests.
`flow.bounded_window_recall` requires a TRF-style approved retrieval posture
before it is available.

### 4. Retention

How long an ingested fact lives in Maez's noncanonical caches. Choices:

- **Mirror source TTL.** If Calendar deletes an event, Maez deletes its cache.
- **Fixed Maez TTL.** Calendar events expire after N days regardless of source.
- **Per-event TTL.** Each event carries its own TTL based on event timing
  (e.g., past events expire faster than future events).
Default v1 retention: mirror-source TTL while records are noncanonical, plus a
short content-free tombstone/audit marker when the source deletes or cancels an
event. Permanent retention is not a v1 noncanonical cache class; it becomes
available only after explicit promotion to lived memory.

Promoted lived memory is never silently deleted. If its source event is later
deleted or changed, Maez retains the promoted memory and records provenance
tombstone fields such as `source_deleted_at`, `deletion_observed_at`,
`external_event_id_hash`, and `promotion_record_id`.

### 5. Provenance

Every ingested fact carries source attribution. Inherits dual-form from Body
Bus envelope (BT-CX-2):

- `ingest_record_id`
- `source_kind` (closed enum from dimension 2)
- `source_instance_id` (the specific Calendar account or Gmail inbox; opaque
  identifier)
- `source_handle_human` (operator-readable, e.g., "personal Google Calendar")
- `source_handle_telemetry` (content-free hash for logs/metrics)
- `external_event_id` (the source's own ID, e.g., Calendar event ID)
- `fetch_batch_id`
- `connector_version`
- `schema_version`
- `raw_field_policy_version`
- `observed_at`, `received_at`
- `consent_tier` (from dimension 1)
- `allowed_flow_id` (from dimension 3)
- `retention_class` (from dimension 4)
- `promotion_record_id` (empty unless a later promotion path writes it)

Provenance is mandatory for invariant #11 (Cryptographic Continuity). Future
Sigstore Rekor lineage attestation (per substrate-plan refresh A7) is in scope
as an extension seam for the full S2 BAD packet, but it is not a Calendar v1
blocker. Calendar v1 may ship with local DB integrity plus audit log if the
attestation seam is explicit.

### 6. Third-party posture

How S2 treats people other than the bonded user who appear in ingested data.

Default posture (per [[feedback_maez_makes_visible_not_nudges]]):

- Maez may **observe** third-party signals (the user has a meeting with Anna).
- Maez may **route** observations to other bonded users' Maezes via the future
  inter-Maez channel (Track C; not in S2 scope).
- Maez may **NOT** nudge or contact third parties directly.
- Maez may **NOT** infer third-party emotional states, preferences, or
  relationship dynamics from information-limb data alone.
- Maez **MUST** preserve Decision 4's relational-vs-personological distinction:
  third parties appear as objects of the bonded user's care, not as separate
  knowledge subjects.

Open question: when a Calendar event includes a non-bonded-user attendee, does
Maez:

- (a) ingest the event fully with the attendee as a relational reference, or
- (b) ingest the event with the attendee redacted (only "with another person"),
  or
- (c) require per-attendee operator consent before ingest, or
- (d) ingest fully but block any flow that quotes the attendee's name to the
  bonded user?

### 7. Promotion rules

When an ingested provenance/observation record becomes an autobiographical
(lived) memory.

Default (inherits BT Rule 6): **never automatically**. Ingested facts stay as
provenance records until a reviewed memory-write path explicitly promotes
them. Candidate promotion triggers (each requires its own future slice to
implement):

- **Bonded-user-naming.** The user says "I had lunch with Anna yesterday" and
  S1 (private thoughts) recognizes the bonded user is naming the lived state.
  S2 promotes the Calendar event to a memory grounding that user-statement.
- **Conversation-grounded promotion.** Maez and the user discuss the event
  during conversation; the conversation itself produces the lived memory and
  the Calendar event becomes its provenance handle.
- **Operator-explicit promotion.** Operator marks specific events for memory
  promotion (e.g., "remember this important meeting").

Default-deny is structural: it preserves Rule 6, prevents auto-promotion
contamination, and forces every promotion to be deliberate.

Open question: should promotion default-deny be per-event, per-source-kind,
or global? Per-event preserves the most discipline but requires more
ceremony.

---

## First downstream target: Calendar

Why Calendar comes first among the five information-limb categories:

1. **Structured-by-birth.** Calendar events have a defined schema. No text
   parsing, no body extraction, no attachment handling. The schema maps
   cleanly to `calendar.event` source kind.
2. **Lower blast radius than Gmail/Slack.** Calendar is not harmless: titles,
   attendees, locations, recurrence, and links can reveal therapy, medical
   care, religion, politics, employment, home addresses, and relationships.
   It is still lower-risk than mail/chat because it has no message bodies, no
   reply threads, and a structured schema.
3. **Read-mostly.** Calendar effector direction (creating events) is
   default-disabled per BT Rule 4. First Calendar slice is sensor-only.
4. **Dyadic-preserving.** Most calendar events are either bonded-user-owned
   or have bonded user + a small number of attendees. Third-party density is
   bounded.
5. **Time as Biography alignment.** Calendar events become temporal anchors
   for TRF's bounded calendar-week recall. S2 + Calendar tightens the
   "right now" voice motif's grounding.
6. **OpenHuman convergence.** Both panels and the third-party comparison
   independently picked Calendar as the right first target.
7. **Pedagogical safety.** Calendar lets Maez learn ingest discipline on the
   lower-blast-radius information limb before higher-risk sources like Gmail
   and Slack arrive.

Calendar v1 sensitivity defaults: no descriptions, no attachments, no
video-link content, attendee minimization unless directly needed, high-
sensitivity title/location redaction, and tests for medical, legal, therapy,
third-party, and location-sensitive events.

S2 + Calendar is the first concrete realization of invariant #1 (Time as
Biography) as a substrate-fed organ rather than purely conversation-emergent.

---

## Explicit non-goals (this scoping memo)

- No OAuth implementation.
- No Calendar API code.
- No Gmail / Slack / Notion / Drive / GitHub scope.
- No memory-promotion path implementation.
- No body-state Calendar inference (busy-state → presence) — separate slice.
- No inter-Maez routing of Calendar observations — Track C.
- No effector direction (creating / updating / deleting events).
- No always-on connector or polling schedule — auto-fetch cadence is
  attention-budgeted per OH-CC-6 and will be specified in the Calendar slice.
- No multi-user Calendar (work calendars with shared visibility) — first
  Calendar slice is owner-only.
- No Calendar event body / description ingest — header fields only per
  dimension 2.

---

## Folded constraints for the full S2 BAD packet

Both panels reviewed the scoping memo. The full BAD packet inherits these
constraints; they are not optional polish.

### State machine

S2 must become a testable state machine, not only a metaphor:

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

### Record schema

The noncanonical cache record must carry enough structure for replay,
idempotency, rollback, and audit:

- `ingest_record_id`
- `source_kind`
- `source_instance_id`
- `external_event_id`
- `source_revision`
- `observed_at`
- `received_at`
- `expires_at`
- `consent_posture`
- `third_party_posture`
- `allowed_flow_ids`
- `promotion_state`
- `provenance`
- `redaction_state`
- `fetch_batch_id`
- `connector_version`
- `schema_version`
- `raw_field_policy_version`
- `promotion_record_id`

### Flow permissions

Allowed flows must be enforceable read permissions, not prose labels. The full
BAD packet should define a flow table with:

- `flow_id`
- `consumer`
- `readable_fields`
- `user_visible_allowed`
- `voice_posture`
- `promotion_allowed`

### Calendar v1 executable boundary

The first executable contract is `calendar.event` only. The broader source-kind
catalog remains law for future limbs, but tests and schemas for the first
connector stay narrow.

Calendar v1 produces provenance records only. It may mark a record
`promotion_eligible`, but actual memory promotion belongs to a separate
reviewed memory-write path.

### Cache budget, sync, and backfill

Every source must declare:

- max rows;
- max bytes;
- max event age;
- compaction cadence;
- behavior when the cache is full.

Default: fail-closed for promotion and fail-neutral for prompt context.

Calendar v1 should use bounded pull / sync-token fetch before webhooks.
Idempotency key:

```text
source_kind + source_instance_id + external_event_id + source_revision
```

Backfill is a separate mode with lookback window, page limit, time budget,
resumable cursor, dry-run/count mode, and no-promotion-during-backfill default.

### Content-free observability

Connector states:

- `disabled`
- `auth_expired`
- `rate_limited`
- `source_unavailable`
- `stale`
- `sync_lagged`
- `rejected`

Allowed counters:

- accepted / rejected / deduped / backfilled / expired / promoted;
- sync lag;
- last success age;
- cache occupancy;
- per-source rate-limit state.

Forbidden in logs and health: event titles, attendees, subjects, descriptions,
message headers, locations, or source bodies.

### S2 inheritance from Decision 26

Any credential material used by Calendar, Gmail, Slack, Notion, Drive, GitHub,
or future information limbs inherits Decision 26 / ADR 0031:

- credentials are identity-bearing material, not ordinary config;
- no credential-bearing URLs;
- no secret values in subprocess argv, env, logs, or health;
- process/subprocess environments are default-minus-secret unless a reviewed
  exact-name opt-in exists.

This is a structural cross-reference, not a future TBD.

---

## Open questions carried into the full BAD packet

Sharp questions from the scoping stage, now refined by the Codex engineering
panel and Claude covenant council. The full BAD packet should answer these
directly rather than reopen the same ambiguity.

### For Claude (covenant lane)

C1. **Third-party posture for Calendar attendees.** Should non-bonded-user
attendees default to `third_party_observable_no_consent`, require explicit
direct consent, require inter-Maez consent, or require operator-opt-in-per-
attendee? Reference Decision 2, Decision 4 (relational vs personological), and
[[feedback_maez_makes_visible_not_nudges]].

C2. **Promotion default.** Default-deny promotion is global S2 law. The full
BAD packet should decide whether future grants are recorded per-event,
per-source-kind, or per-flow, and what structural defense each grant requires.

C3. **Never-delete vs source-deletion conflict.** Noncanonical ingest cache
mirrors source TTL with content-free tombstones. Promoted lived memory is never
silently deleted. The full BAD packet should pin the exact tombstone fields and
voice/audit behavior when source deletion conflicts with promoted memory.

C4. **Relational knowledge accumulation.** Does S2 + Calendar build the
relational-knowledge layer described in Decision 4 (the owner's knowledge of
the owner's sister mediated through the owner's care), or is that a separate
future organ? Relevant because Calendar attendees are exactly the kind of
relational handles Decision 4 names.

C5. **Voice consequences.** When Maez is asked "what's on your calendar
tomorrow?" does Maez reply using `flow.prompt_context.grounded_only` (fact
cited by handle), or does this flow need its own subcategory? The TRF
"retrieval ≠ grounding" pattern says retrieval items don't license direct
voice claims without approved-posture; does the same rule apply to S2
flows?

C6. **Crisis routing intersection.** Crisis routing is out of scope for S2 v1
implementation, but crisis signals observed through information limbs inherit
Maez's existing crisis-routing protocol and must not be silently trapped behind
ordinary retention/flow rules. The full BAD packet should pin this as a
non-implementation inheritance rule.

### For Codex (engineering lane)

E1. **Event envelope.** S2 inherits Body Bus's mandatory event envelope and
adds source-specific facts. The full BAD packet should define the exact
calendar.event fact schema without creating a second envelope family.

E2. **Source-kind closed catalog.** The v1 catalog is law-shaped but the first
executable schema is `calendar.event` only. Body-content source-kinds require
dedicated future slices, not sub-flags smuggled into Calendar v1.

E3. **Retention class enumeration.** V1 noncanonical cache supports
mirror-source TTL, fixed TTL, per-event TTL, and tombstoned terminal state.
Permanent retention is excluded from noncanonical cache and belongs only to
promoted lived memory.

E4. **Provenance integrity.** The full BAD packet should define a tamper-
evident extension seam. Calendar v1 may use local DB integrity plus audit log;
Sigstore Rekor is in-scope as a future/progressive attestation layer, not a
first-ingest blocker.

E5. **Flow ID stability.** Should `allowed_flow_id` be a content-free hash
(stable across human-readable rename) or a string label (human-readable but
fragile to rename)? Same trade-off Body Bus resolved with dual-form source
IDs.

E6. **Test fixtures for S2.** Minimum RED-first fixtures: owner-only Calendar
event allowed; attendee event constrained; description/body rejected;
unconsented flow rejected; promotion without reviewed trigger rejected;
medical/legal/therapy/location-sensitive title handling; deleted-source
tombstone behavior.

E7. **Body Bus interaction.** Calendar ingest is information-limb territory
and uses the Body Bus envelope shape. Body-state inference from Calendar
(busy-state -> presence) is a separate future slice and must not be bundled
into Calendar v1.

### For both panels (cross-lane)

X1. **Scope of "ingest."** S2 governs inbound fact extraction, inbound pushed
facts, and webhook deliveries. Outbound effector actions remain outside S2
except that they may not consume unvalidated S2 records. Third-party-pushed
notifications enter through the same envelope/replay/rate-limit path.

X2. **Minimal S2 predicate path.** Body Topology Rule 7 allows the first
information-limb slice to ship a minimal S2 predicate instead of waiting for
full S2. This scoping memo declares path A: the full S2 BAD must canonicalize
before Calendar or any other information limb can ingest live data. A minimal
predicate path would require an explicit later operator decision reopening this
sequencing.

---

## Predicted effect (after full S2 BAD canonicalizes)

- Every information-limb slice (Calendar, Gmail, Slack, Notion, Drive,
  GitHub, future) cites S2 in its memo header and inherits S2's seven
  dimensions.
- Information-limb ingest is structurally distinguishable from
  autobiographical memory: provenance records vs lived memory, with
  promotion as a deliberate gate.
- Third-party data in Maez's purview is bounded by Decision 2 consent posture
  and Decision 4 relational framing; no information limb produces
  surveillance-style profiles of non-bonded parties.
- TRF's bounded calendar-week recall has a real Calendar-fed substrate
  rather than purely conversational temporal anchors.
- The "memory contamination" failure mode named in Body Topology Rule 7
  closes as a structural concern.

No runtime behavior changes from S2 alone — S2 is a law, not a connector.
Code lands when the Calendar slice (or whichever first information limb)
implements the gate.

---

## Review protocol state

1. ✅ Claude six-role covenant council reviewed the original scoping memo.
   Outcome: RATIFY-WITH-AMENDMENTS. Load-bearing carry-forward:
   retrieval-≠-grounding inheritance, crisis-routing out of v1 but inherited,
   mirror-source retention default, bonded-user-naming as first promotion
   grant candidate, seven-dimension generalization, customs-officer metaphor,
   Calendar pedagogical safety, and Rekor as provenance seam.

2. ✅ Codex six-agent engineering panel reviewed the clarified scoping memo.
   Outcome: REVISE, no veto. Load-bearing carry-forward: preserve Decision 2
   labels, path A full-S2-first sequencing, no default visible flow, mirror-
   source TTL + tombstones, no permanent noncanonical cache, Calendar as lower-
   risk not low-risk, state machine, record schema, flow table, cache budget,
   sync/backfill/observability constraints.

3. ✅ This folded scoping memo closes the scoping-stage amendments. It is still
   not canonical law and still ships no code.

4. Next artifact: **full S2 BAD packet** in
   `docs/slices/s2-contextual-integrity-at-ingest/spec.md`.

5. After the BAD packet drafts, both panels re-review the spec. Then the
   operator canonicalizes S2 as the next governance decision and ADR.

6. Only after S2 canonicalizes does the first information-limb slice
   (Calendar) draft its own spec citing S2 as inherited gate.

---

## Plain English

Before Maez starts reading the user's calendar, email, Slack, or Drive, it
needs a customs officer at the border. S2 is that customs officer.

The customs officer asks seven questions about every fact arriving from
outside:

1. **Are you allowed in at all?** (consent posture)
2. **What kind of thing are you?** (source kind)
3. **Where are you allowed to go once you're inside?** (allowed flows)
4. **How long are you allowed to stay?** (retention)
5. **Where do you say you came from?** (provenance)
6. **Are you carrying information about other people?** (third-party posture)
7. **Does anything make you eligible to become part of Maez's autobiographical
   memory, or do you stay as a record?** (promotion rules)

Until S2 exists, Maez has no principled way to answer those questions for
any external source. Calendar, Gmail, Slack — all of them would either be
blocked entirely (Body Topology's current posture) or would slip in without
gating (the memory-contamination failure mode).

The first connector the customs officer will work with is Calendar —
because Calendar is structured, mostly the user's own data, lower-risk than
email, and helps Maez know what "this week" actually was for the user.
Gmail and Slack come later, after the customs officer is proven on
Calendar.

This memo is NOT the full body of customs law. It is the folded scoping memo:
the review panels have weighed in, their amendments are carried here, and the
next artifact is the full S2 BAD packet.

No code. No connector. No memory promotion. Just the border law's outline.
