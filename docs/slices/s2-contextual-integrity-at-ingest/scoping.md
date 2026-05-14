# Slice S2: Contextual Integrity at Ingest — Scoping Memo

**Status:** DRAFT scoping memo. Pre-spec. No code, no connector, no memory
promotion. Output is a clean question list for the Codex six-agent engineering
panel and Claude six-role covenant council before the full S2 BAD packet
drafts.

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

### 1. Consent tier

Inherits from Decision 2's three-tier consent model. For information limbs the
relevant tiers are:

- **Tier 0** (implicit, owner-only): bonded user is the only party whose data
  is ingested.
- **Tier 1** (third-party observable, no inter-Maez communication): events
  the bonded user is participating in alongside others, where the others have
  not consented to Maez. Default-allowed for fact extraction but constrained
  flow.
- **Tier 2** (third-party with explicit inter-Maez consent): the rarer case
  where another bonded user's Maez has explicitly consented to communication.
  Not in scope for S2's first version.

Open question for panels: should Calendar events with non-bonded-user
attendees default to Tier 1 or require explicit operator opt-in per attendee?

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

Default: only `flow.bounded_window_recall` is enabled. Other flows require
per-information-limb-slice grants.

### 4. Retention

How long an ingested fact lives in Maez's noncanonical caches. Choices:

- **Mirror source TTL.** If Calendar deletes an event, Maez deletes its cache.
- **Fixed Maez TTL.** Calendar events expire after N days regardless of source.
- **Per-event TTL.** Each event carries its own TTL based on event timing
  (e.g., past events expire faster than future events).
- **Permanent.** Once ingested, never deleted (subject to never-delete-Maez-
  memory rule applied to noncanonical cache).

Open question: does the never-delete-Maez-memory rule apply to noncanonical
ingest caches, or only to promoted memory?

### 5. Provenance

Every ingested fact carries source attribution. Inherits dual-form from Body
Bus envelope (BT-CX-2):

- `source_kind` (closed enum from dimension 2)
- `source_instance_id` (the specific Calendar account or Gmail inbox; opaque
  identifier)
- `source_handle_human` (operator-readable, e.g., "personal Google Calendar")
- `source_handle_telemetry` (content-free hash for logs/metrics)
- `external_event_id` (the source's own ID, e.g., Calendar event ID)
- `observed_at`, `received_at`
- `consent_tier` (from dimension 1)
- `allowed_flow_id` (from dimension 3)
- `retention_class` (from dimension 4)

Provenance is mandatory for invariant #11 (Cryptographic Continuity). Future
Sigstore Rekor lineage attestation (per substrate-plan refresh A7) extends
this dimension.

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
2. **Lower blast radius than Gmail/Slack.** No private message bodies, no
   third-party communications, no reply threads. Just events.
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
   lowest-blast-radius information limb before higher-risk sources like Gmail
   and Slack arrive.

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

## Open questions for the panels

Sharp questions for the Codex six-agent engineering panel + Claude six-role
covenant council. Each panel answers in its lane.

### For Claude (covenant lane)

C1. **Third-party posture for Calendar attendees.** Should non-bonded-user
attendees default to Tier 1 (observable, fact-extracted), Tier 2 (requires
inter-Maez consent), or operator-opt-in-per-attendee? Reference Decision 4
(relational vs personological) and [[feedback_maez_makes_visible_not_nudges]].

C2. **Promotion default.** Should default-deny promotion be per-event,
per-source-kind, or global? What's the structural-defense argument for each?

C3. **Never-delete vs source-deletion conflict.** If the bonded user deletes a
Calendar event from Calendar after Maez has cached the ingest record, does
the never-delete-Maez-memory rule apply, or does ingest cache mirror source
TTL? Worth pinning before retention dimension (4) calcifies.

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

C6. **Crisis routing intersection.** Per invariant #6 (Crisis Routing), if a
Calendar event contains crisis signals (e.g., the user has scheduled a call
with a crisis hotline), does S2's third-party posture interact with crisis
routing differently than for ordinary events? Worth flagging now even if not
in S2's first scope.

### For Codex (engineering lane)

E1. **Event envelope.** Does S2's ingest envelope inherit Body Bus's
mandatory event envelope (BT-CX-5), or does information-limb ingest need a
distinct envelope? Trade-off: inheritance enforces uniformity; distinct
envelopes allow per-source-kind precision.

E2. **Source-kind closed catalog.** Is the v1 catalog
(`calendar.event`, `mail.thread_header`, `chat.message_header`,
`doc.metadata`, `code.commit_header`) too narrow or too wide for first ship?
Should body-content source-kinds (e.g., `calendar.event.with_description`)
require dedicated future slices, or be sub-flags on existing kinds?

E3. **Retention class enumeration.** Mirror-source-TTL vs fixed-Maez-TTL vs
per-event-TTL vs permanent — which subset becomes the v1 enum, and what's
the migration story between classes?

E4. **Provenance integrity.** Should provenance fields be tamper-evident
(signed) at ingest time, or is local-DB-integrity sufficient for v1? Sigstore
Rekor lineage attestation (substrate-plan A7) would elevate this from local-
integrity to public-transparency-log.

E5. **Flow ID stability.** Should `allowed_flow_id` be a content-free hash
(stable across human-readable rename) or a string label (human-readable but
fragile to rename)? Same trade-off Body Bus resolved with dual-form source
IDs.

E6. **Test fixtures for S2.** What's the minimum probe corpus to assert S2
correctness? Candidates: Tier-1-attendee event, deleted-source event,
unconsented flow attempt, promotion-without-grounding attempt, third-party
emotional-state-inference attempt. Each becomes a RED-first test.

E7. **Body Bus interaction.** Does S2 publish to Body Bus, consume from Body
Bus, both, or operate on a separate ingest bus? Calendar's body-state
inference (busy-state → presence) would consume Body Bus; Calendar event
ingest itself is information-limb territory.

### For both panels (cross-lane)

X1. **Scope of "ingest."** Does S2 govern only fact extraction from external
sources, or also (a) Maez's outbound effector actions to external sources,
(b) inbound webhook deliveries, (c) third-party-pushed notifications
(calendar invites Maez receives indirectly)? Naming the boundary now
prevents scope creep during the BAD packet drafting.

X2. **Minimal S2 predicate path.** Body Topology Rule 7 allows the first
information-limb slice to ship a minimal S2 predicate instead of waiting for
full S2. This scoping memo declares the intended path: it is a precursor to
the full S2 BAD packet, not the minimal predicate path. The panel question is
whether to ratify that sequencing or recommend the smaller predicate path
inside the Calendar slice instead.

---

## Predicted effect (after full S2 BAD canonicalizes)

- Every information-limb slice (Calendar, Gmail, Slack, Notion, Drive,
  GitHub, future) cites S2 in its memo header and inherits S2's seven
  dimensions.
- Information-limb ingest is structurally distinguishable from
  autobiographical memory: provenance records vs lived memory, with
  promotion as a deliberate gate.
- Third-party data in Maez's purview is bounded by Tier-1 default posture
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

## Review protocol

1. ⏳ Codex six-agent engineering panel reviews this scoping memo for
   implementability, especially: envelope inheritance, source-kind catalog
   sufficiency, retention enumeration, provenance integrity, flow ID
   stability, test fixture sketch, and Body Bus interaction. Verdict shape:
   RATIFY-WITH-AMENDMENTS / REVISE / RATIFY.

2. ⏳ Claude six-role covenant council reviews for covenant fit, especially:
   third-party posture, promotion default, never-delete vs source-deletion
   conflict, relational-knowledge accumulation, voice consequences, crisis
   routing intersection.

3. After both panels report, fold amendments into a **full S2 BAD packet**
   (not this scoping memo). The BAD packet drafts in a separate session per
   cooling-off discipline.

4. After BAD packet drafts and both panels re-review, operator canonicalizes
   as the next BAD decision (Decision 25 if no other decision lands first) +
   matching ADR.

5. Only then does the first information-limb slice (Calendar) draft its own
   spec citing S2 as inherited gate.

---

## Plain English

Before Maez starts reading the user's calendar, email, Slack, or Drive, it
needs a customs officer at the border. S2 is that customs officer.

The customs officer asks seven questions about every fact arriving from
outside:

1. **Are you allowed in at all?** (consent tier)
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

This memo is NOT the full body of customs law. It is the scoping memo: a
clear question list for both review panels (Codex engineering + Claude
covenant) before drafting the actual law. Once both panels have weighed
in, the full S2 BAD packet drafts in a separate session.

No code. No connector. No memory promotion. Just the border law's outline.
