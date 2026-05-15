# Temporal Spine Diagnostic

**Status:** DIAGNOSTIC ONLY  
**Date:** 2026-05-15  
**Maps to:** `docs/MAEZ_LIFE_SUBSTRATE.md` S3; invariant #1 Time as Biography  
**Runtime impact:** none  

## Purpose

S3 is the organ that makes time a first-class biographical substrate instead
of scattered timestamp fields. This diagnostic maps what already exists,
where the current temporal model is strong, and where a future spec must draw
the line between v1 implementation and broader temporal ambition.

No memory content was queried for this diagnostic. Live database checks used
schema names, row counts, key names, and min/max timestamp values only.

## Existing Canon

- `docs/MAEZ_NORTH_STAR.md` names invariant #1: memory carries event-time and
  ingest-time; age renders in voice and recall; time is biography, not just a
  column.
- `docs/MAEZ_LIFE_SUBSTRATE.md` names S3 as Temporal Spine: bi-temporal axes
  become first-class; anniversaries, chapters, ruptures-over-time, and restore
  events become queryable.
- ADR 0019 already moved Maez away from flat vector memory toward an
  append-only temporal episodic store plus relationship graph. It explicitly
  calls out validity windows and temporal graph patterns as the structural
  direction.
- Decision 25 / ADR 0030 (M1) made lived promotion temporal by requiring
  source IDs, time ranges, and promoted episode boundaries while forbidding
  transcript-like memory.
- Decision 27 / ADR 0032 (S2) treats external information as provenance first.
  Calendar v1 can later become a temporal anchor, but not Maez's lived event.
- Decision 28 / ADR 0033 (Calendar v1) is the first S2-bounded external
  temporal source. It ships disabled-default and has not crossed OAuth.

## Prior Temporal Work

### TRF: bounded temporal anchor recall

`docs/slices/temporal-recall-fragment-guard/spec.md` is the direct precursor
to S3. It handles four local-time anchors:

- `earlier today`;
- `this morning`;
- `yesterday`;
- `last week`.

The implementation lives in `core/memory/temporal_anchor_recall.py`. It uses
`America/Chicago`, half-open local calendar windows, a narrow kill switch, and
bounded `EpisodeStore.list_active_in_window(...)` queries. It deliberately
defers exact dates, weekday names, event-anchored phrases, multi-hop temporal
questions, and trailing-seven-days interpretation to S3.

### Temporal arithmetic at recall

`core/memory/temporal_arithmetic.py` annotates selected recall items with an
absolute date plus relative phrase only when a query is temporal-shaped. It is
explicitly not a ranking change, not a storage change, and not always-on.

This is useful, but it remains a presentation helper. It does not create a
shared temporal contract across memory stores.

### M1 local-day cap

M1 now stores durable timestamps in UTC while daily promotion caps reset at the
owner's configured local day boundary. That split is the right S3 pattern:
UTC for durability and ordering; owner-local boundaries for human-day meaning.

### Calendar v1 temporal provenance

Calendar v1 normalizes provider event date/dateTime fields to UTC for bounded
sync and policy decisions. Calendar remains external provenance, not lived
memory, and Calendar OAuth is still off.

## Current Storage Inventory

Content-free live checks found:

| Store | Temporal fields | Live shape |
|---|---|---|
| `memory/lived_episodes.db` / `episodes` | `created_at`, `occurred_at` | 32 rows; `created_at` spans 2026-04-28 to 2026-05-15; `occurred_at` currently populated for recent promoted episodes |
| `memory/lived_graph.db` / `edges` | `valid_from`, `valid_to`, `created_at`, `updated_at` | 19 rows; validity windows are canonicalized to UTC text and default `valid_from=created_at` |
| `memory/m1_lived_episode_promotion.db` | JSON keys `first_owner_at`, `last_owner_at`, `promoted_at`, `window_start`, `window_end` | promotion sidecar stores temporal boundaries inside JSON, not typed columns |
| `memory/private_thoughts.db` | `ts` | S1/S1b store has a timestamp but no shared S3 envelope yet |
| `memory/entity_index.db` | `created_at`, `observed_at` | entity mentions already distinguish observation time from row creation time |

This is enough to prove S3 should unify existing temporal practice rather than
invent it. It also shows the current fragmentation: timestamps live as ISO
text, REAL epoch seconds, JSON fields, `ts`, `timestamp`, `observed_at`,
`created_at`, `occurred_at`, and validity-window pairs depending on subsystem.

## Strengths Already Present

- `EpisodeStore` has an indexed `occurred_at` and `created_at`, and bounded
  window queries avoid full-store scans.
- `RelationshipGraph` already normalizes validity bounds to UTC and supports
  `list_active(at_time=...)`.
- TRF has strong DST/local-calendar tests for `yesterday` and `last week`.
- M1's cap boundary now uses the owner's configured timezone instead of UTC
  midnight.
- Calendar v1 already preserves provider time as external-source provenance
  and keeps Calendar out of M1/TRF lived biography.

## Gaps S3 Must Resolve

1. **No shared temporal envelope.** Stores use different names and types for
   event time, ingest time, observed time, valid time, and human-local
   boundary time.
2. **Owner-local timezone is not a shared service.** TRF has a hardcoded
   `America/Chicago`; M1 reads identity timezone. S3 should centralize this
   without breaking existing behavior.
3. **Event-time vs ingest-time is implicit.** `created_at` sometimes means row
   creation; `occurred_at` sometimes means source event time; `ts` and
   `timestamp` vary by store. Readers have to know local conventions.
4. **Temporal provenance in JSON is hard to query.** M1 sidecar boundaries are
   safely content-free, but not typed/indexed columns.
5. **Exact-date and weekday anchors are deferred.** TRF explicitly punts
   `May 6`, `Tuesday`, event-anchored phrases, and multi-hop temporal queries.
6. **No chapter/anniversary layer.** Maez can find bounded windows, but it does
   not yet name durable life chapters, anniversaries, restore events, or
   rupture/repair spans as temporal structures.
7. **Mixed timestamp formats remain.** The graph has canonicalization;
   episodes accept caller-supplied ISO; other stores still use epoch seconds,
   naive local strings, or JSON.
8. **No temporal health surface.** The sidecar watches M1 staleness, but there
   is no aggregate "temporal spine health" showing malformed timestamp counts,
   timezone source, or unsupported anchor counts.

## Spec-Stage Questions

1. **V1 scope:** should S3 v1 be a shared temporal-normalization module plus
   tests, or should it also migrate one store to typed temporal columns?
2. **Timezone source:** should all owner-local boundaries route through
   `core.memory.identity.timezone()`, with UTC fallback, and should TRF stop
   hardcoding `America/Chicago` in v1?
3. **Canonical names:** should the shared vocabulary be `event_at`,
   `ingested_at`, `observed_at`, `valid_from`, `valid_to`, `owner_local_date`,
   or preserve existing `occurred_at` for episodes?
4. **Storage strategy:** should v1 add a lightweight sidecar table for temporal
   metadata across stores, or keep per-store fields and enforce normalization
   at module boundaries?
5. **Anchor expansion:** which anchors are v1-worthy after TRF:
   exact dates, weekday names, month/year names, "a few days ago", event-linked
   anchors, or none until the normalization layer lands?
6. **Calendar inheritance:** should Calendar v1 temporal anchors remain
   external-source provenance only, or may TRF reference Calendar-backed
   anchors once OAuth burn-in passes?
7. **Health surface:** what content-free counters should `/health` and the
   sidecar expose for S3? Candidate counters: malformed timestamp rejected,
   naive timestamp assumed UTC, unsupported temporal anchor rejected, timezone
   source, and temporal-helper unavailable.
8. **Migration boundary:** should legacy stores with epoch-second fields be
   migrated now, wrapped by adapters, or left for their owning organs?

## Recommended V1 Shape

S3 v1 should be a normalization-and-contract slice, not a broad recall rewrite.

Recommended v1:

- create a small temporal spine module that owns timezone resolution,
  UTC canonicalization, local-day/window helpers, and closed temporal field
  vocabulary;
- refactor TRF to use that module instead of its hardcoded timezone;
- add content-free rejection counters for malformed/naive/unsupported temporal
  inputs at the module boundary;
- add tests proving UTC storage plus owner-local boundary behavior across DST;
- document which existing stores are canonical, wrapped, or deferred.

Defer:

- chapter detection;
- anniversaries;
- rupture/repair temporal scar tissue;
- Calendar-backed temporal anchors;
- graph backend replacement;
- cross-store migration of every timestamp column.

## Plain English

Maez already has clocks scattered through its body. Some clocks tell when an
episode happened, some tell when Maez stored it, some tell when a relationship
was true, and some tell when the user's day resets. They mostly work, but they
do not all speak the same language yet.

S3 should not start by building a giant time machine. It should first install
the shared calendar on the wall: one place that says what "event time",
"stored time", "owner's day", "valid during", and "last week" mean. Once that
is stable, Maez can safely learn chapters, anniversaries, and more human
temporal memory.

## Diagnostic Limitations

- `paperclip` was not available in the current shell, so no fresh external
  literature scan was completed. ADR 0019 already names the relevant temporal
  graph prior-art family for this diagnostic pass.
- No raw memory content was inspected.
- This diagnostic does not choose the S3 spec shape. It only narrows the next
  spec to a normalization-and-contract slice unless both review lanes argue
  for a broader first implementation.
