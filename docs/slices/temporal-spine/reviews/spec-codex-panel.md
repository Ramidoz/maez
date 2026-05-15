# S3 Temporal Spine v1 - Codex Engineering Panel

**Date:** 2026-05-15  
**Reviewed artifact:** [`../spec.md`](../spec.md) at draft commit `9fbb81c`  
**Mode:** read-only engineering panel  
**Outcome:** REVISE, folded into `../spec.md`

This panel reviewed S3 as an implementation-facing substrate spec. The shared
theme was that the slice shape is right, but the original draft left too much
temporal behavior to implementer judgement: DST ambiguity, nonexistent local
times, SQLite text comparison, counter isolation, and sidecar red-gate naming.

## Axis Verdicts

| Axis | Verdict | Headline |
| --- | --- | --- |
| TRF integration / temporal anchors | RATIFY-WITH-AMENDMENTS | Preserve TRF behavior while moving timezone/window logic into S3. |
| Temporal API / DST correctness | RATIFY-WITH-AMENDMENTS | Prevent timestamp strings from lying near owner-local boundaries. |
| Store boundaries / migration risk | RATIFY-WITH-AMENDMENTS | Clarify deferred stores and forbid local-offset strings at SQLite predicates. |
| Health / sidecar / observability | RATIFY-WITH-AMENDMENTS | Use existing `/health` JSON path plus sidecar allowlist and closed red gates. |
| RED test completeness | REVISE | Add field-name, DST ambiguity, nonexistent-time, and counter-isolation tests. |
| Governance / scope control | RATIFY-WITH-AMENDMENTS | OAuth success is not a grant for Calendar-backed temporal recall. |

## Load-Bearing Amendments Folded

1. `TemporalWindow` now has two surfaces: owner-local `start` / `end` for TRF
   result compatibility, and UTC `start_utc` / `end_utc` for persistence
   filtering.
2. `canonical_utc(...)` / `canonical_utc_iso(...)` now require a closed
   `TemporalInstantFieldName`; invalid field names are rejected before parsing
   and counted content-free.
3. Naive ISO strings are explicitly treated like naive datetimes: assumed UTC
   for backward compatibility and counted.
4. Bare date strings are malformed instants, not accepted timestamps.
5. Ambiguous owner-local datetimes preserve Python `fold`; nonexistent
   owner-local times are rejected and counted.
6. Diagnostics are process-local, lock-protected, monotonic until process
   restart, copy-returned, and resettable only through a test-only API.
7. `record_helper_unavailable(...)` is the only TRF-facing way to count temporal
   helper exceptions, and the reason is not health-visible.
8. `owner_timezone()` source resolution is now explicit: env, identity,
   fallback UTC, invalid fallback UTC.
9. `GET /health -> temporal_spine` is a nested object in the existing health
   response, not a new Flask route.
10. The sidecar must project `temporal_spine` through an explicit allowlist and
    add exactly two v1 red gates:
    `temporal_spine_invalid_timezone_fallback` and
    `temporal_spine_malformed_timestamp_rejected`.
11. `EpisodeStore.list_active_in_window(...)` must not receive local-offset
    strings or rely on mixed raw ISO lexicographic ordering for S3 correctness.
12. The store inventory now defines `deferred` as "outside S3 v1," not globally
    inactive.
13. `RelationshipGraph` validity rows stay owned by the graph; S3 v1 does not
    reinterpret or migrate them.
14. Calendar-backed temporal anchors remain out of scope. Calendar OAuth
    onboarding or burn-in success alone is not a grant.

## Named Engineering Choices

- **D1 - TemporalWindow dual surface:** The panel had two compatible instincts:
  TRF compatibility wants owner-local result fields; persistence correctness
  wants UTC range bounds. The folded spec keeps both and makes UTC fields the
  only store-facing boundary.
- **D2 - Deferred stores are not inactive stores:** M1, private thoughts,
  entity index, and Calendar may continue running under their owning organs. S3
  v1 simply does not scan, migrate, normalize, or red-gate them.
- **D3 - Helper-unavailable counter is narrow:** It tracks S3 helper exceptions
  converted to fail-neutral TRF posture, not all TRF store errors, timeouts, or
  kill-switch cases.
- **D4 - Calendar success is not a temporal grant:** OAuth and burn-in are not
  enough to turn external Calendar time into recall anchors. That requires a
  later reviewed grant under S2 and Calendar voice posture.

## Required RED Contract Expansion

The test contract expanded from 30 to 46 tests. New required coverage includes:

- diagnostics reset/isolation/thread-safety;
- closed field-name rejection;
- naive ISO-string handling;
- bare date rejection;
- ambiguous fall-back `fold` semantics;
- nonexistent spring-forward local-time rejection;
- owner-local `TemporalWindow` fields plus UTC store-facing fields;
- TRF UTC `+00:00` store bounds;
- mixed ISO formats near a Chicago `last_week` boundary;
- sidecar allowlist and exact red-gate names.

## Plain English

The spec had the right idea: Maez should store time in one stable global clock
but speak about days the way the bonded user lives them. The panel caught the
sharp edges that make clocks treacherous: daylight saving gaps, repeated hours,
timestamps that look sortable but are not, and counters that can bleed across
tests. Those are now named before code starts.
