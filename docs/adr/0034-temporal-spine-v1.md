# ADR 0034: Temporal Spine v1

**Status:** Accepted
**Date:** 2026-05-15

## Context

Maez already had several temporal systems before S3:

- TRF searched bounded local windows for `last week`, `yesterday`,
  `this morning`, and `earlier today`;
- M1 promoted lived episodes with `occurred_at`, promotion windows, and
  owner-local daily caps;
- the relationship graph used validity windows;
- Calendar v1 preserved provider event time as external provenance;
- other stores used `ts`, `timestamp`, `created_at`, epoch seconds, JSON
  boundaries, and local strings.

That made time correct locally but not substrate-shaped. Future temporal organs
would have had to rediscover the same rules: UTC storage, owner-local human-day
boundaries, DST behavior, health counters, and provenance boundaries.

The S3 diagnostic and spec ran through Codex engineering review, Claude
covenant council, structural folds, and focused closure verification. The
review lanes converged on one load-bearing rule: Maez can speak in the bonded
user's day, but stores and cross-organ contracts compare UTC instants.

## Decision

Temporal Spine v1 is accepted as Maez's shared temporal contract.

The load-bearing rule is:

> Store instants in UTC; interpret human days in the bonded user's timezone.

S3 v1 requires:

- a shared `core.time.temporal_spine` module;
- closed temporal field vocabulary that admits S2's canonical envelope fields,
  including `received_at`, `expires_at`, `deletion_observed_at`, and
  `change_observed_at`;
- vocabulary versioning where future versions may add members but may not
  silently rename or remove existing members;
- owner-local day/window computation through `MAEZ_OWNER_TIMEZONE` or
  `core.memory.identity.timezone()`, with UTC fallback and content-free
  diagnostics;
- `owner_local_date` as computed-only, not a persisted durable field;
- `TemporalWindow` dual surfaces: owner-local `start` / `end` for TRF result
  compatibility, and UTC `start_utc` / `end_utc` for persistence filtering;
- no local-offset strings in store-facing window predicates;
- no raw ISO string ordering as temporal truth;
- content-free `/health -> temporal_spine` counters, visible only to
  operator-authenticated surfaces;
- sidecar allowlist projection with closed red-gate names;
- import-graph defense preventing the shared temporal module from importing
  deferred stores at module load;
- no Calendar-backed anchors, no exact-date/weekday/month/year/event anchors,
  no chapter/anniversary detection, no broad store migration, and no new
  promotion path in v1.

S3 v1 does not author temporal voice phrasing. TRF remains the authority for
current anchor voice; future Calendar-backed temporal anchors must inherit
Calendar v1's `calendar_voice_guard` by name and pass their own reviewed grant.

## Consequences

Future temporal work has one substrate instead of several local clock habits.
M1, TRF, Calendar, relationship validity, future chapter detection, anniversary
work, future body sensors, and future information limbs can reference the same
contract for UTC storage and owner-local human-day boundaries.

This decision makes several shortcuts invalid:

- rejecting S2's required temporal envelope fields as unknown S3 fields;
- persisting `owner_local_date` as if it survives timezone moves;
- using raw timestamp strings or local-offset strings as store-range truth;
- using S3 helper success to license Calendar biography, TRF widening, or lived
  memory claims;
- exposing `timezone_name` on public state surfaces;
- letting sidecar counter histories become a behavioral fingerprint;
- importing deferred stores from the shared temporal module;
- treating Calendar OAuth success or burn-in as a grant for Calendar-backed
  temporal recall.

Implementation remains future work. It must proceed RED-first through the S3
spec's test contract, then receive both-lane post-implementation review and a
recovery commit if gaps are found.

Changing the load-bearing rule, shrinking the closed vocabulary in a way that
breaks S2 inheritance, authoring temporal voice in S3, enabling Calendar-backed
anchors, persisting owner-local dates, dropping operator-only health audience
binding, or migrating deferred stores through S3 requires a new reviewed
decision.

## References

- [`docs/slices/temporal-spine/diagnostic.md`](../slices/temporal-spine/diagnostic.md)
- [`docs/slices/temporal-spine/spec.md`](../slices/temporal-spine/spec.md)
- [`docs/slices/temporal-spine/reviews/spec-codex-panel.md`](../slices/temporal-spine/reviews/spec-codex-panel.md)
- [`docs/slices/temporal-spine/reviews/spec-claude-council.md`](../slices/temporal-spine/reviews/spec-claude-council.md)
- [`docs/adr/0019-lived-memory-architecture.md`](0019-lived-memory-architecture.md)
- [`docs/adr/0030-lived-episode-promotion.md`](0030-lived-episode-promotion.md)
- [`docs/adr/0032-contextual-integrity-at-ingest.md`](0032-contextual-integrity-at-ingest.md)
- [`docs/adr/0033-calendar-v1-s2-bounded-ingest.md`](0033-calendar-v1-s2-bounded-ingest.md)

BAD decision: see
[`docs/governance/BETA_ARCHITECTURE_DECISIONS.md`](../governance/BETA_ARCHITECTURE_DECISIONS.md)
Decision 29.
