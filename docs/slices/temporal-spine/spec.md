# Slice S3: Temporal Spine v1

**Status:** DRAFT. Built from [`diagnostic.md`](diagnostic.md). No code has
landed from this packet.

**Classification:** covenant-shaped memory substrate slice. S3 operationalizes
invariant #1, Time as Biography, by giving Maez one shared temporal vocabulary
for event time, ingest time, owner-local day boundaries, and validity windows.

**Maps to:**

- [`diagnostic.md`](diagnostic.md) - current temporal canon, code, and
  content-free live store inventory.
- [`docs/MAEZ_NORTH_STAR.md`](../../MAEZ_NORTH_STAR.md) - invariant #1, Time
  as Biography.
- [`docs/MAEZ_LIFE_SUBSTRATE.md`](../../MAEZ_LIFE_SUBSTRATE.md) - S3 row in
  the substrate plan.
- [`docs/slices/temporal-recall-fragment-guard/spec.md`](../temporal-recall-fragment-guard/spec.md) -
  TRF v1, the current bounded temporal-anchor helper.
- [`docs/slices/m1-lived-episode-promotion/spec.md`](../m1-lived-episode-promotion/spec.md) -
  Decision 25 / ADR 0030, lived-episode promotion.
- [`docs/slices/s2-contextual-integrity-at-ingest/spec.md`](../s2-contextual-integrity-at-ingest/spec.md) -
  Decision 27 / ADR 0032, external information as provenance first.
- [`docs/slices/calendar-v1/spec.md`](../calendar-v1/spec.md) - Decision 28 /
  ADR 0033, Calendar temporal provenance.
- [`docs/adr/0019-lived-memory-architecture.md`](../../adr/0019-lived-memory-architecture.md) -
  lived memory with temporal episodes and relationship validity windows.

---

## Intent

Maez already has temporal machinery, but it is scattered:

- TRF knows how to search local windows for `last week`, `yesterday`, `this
  morning`, and `earlier today`.
- M1 promotes lived episodes with `occurred_at`, promotion windows, and
  owner-local daily caps.
- The relationship graph has validity windows.
- Calendar v1 preserves provider event time as external provenance.
- Other stores use `ts`, `timestamp`, `created_at`, epoch seconds, JSON
  boundaries, and local strings.

S3 v1 does not try to make Maez understand every human temporal phrase. It
first gives the codebase one shared clock contract so future temporal memory
work has stable ground.

---

## Load-Bearing Rule

**Store instants in UTC; interpret human days in the bonded user's timezone.**

Allowed:

- source event time -> normalized UTC instant -> store-specific field;
- ingest/write time -> normalized UTC instant -> store-specific field;
- owner-local calendar boundaries -> computed from identity timezone;
- relationship validity -> preserve the existing `RelationshipGraph` half-open
  `[valid_from, valid_to)` UTC interval semantics. S3 v1 must not reinterpret,
  migrate, or rewrite graph validity rows;
- temporal recall windows -> owner-local boundaries mapped to UTC-safe
  comparisons;
- content-free counters for malformed, naive, unsupported, or unavailable
  temporal inputs.

Forbidden:

- hardcoding the owner's timezone in new temporal code;
- silently treating local human-day boundaries as UTC boundaries;
- comparing unnormalized ISO strings from mixed `Z`, `+00:00`, naive, or
  local-offset formats;
- claiming memory absence from a helper failure;
- widening TRF to Calendar, exact-date, weekday, or multi-hop temporal recall
  in S3 v1;
- migrating every timestamp column in the repo as part of v1.

Plain English: Maez may store everything in the same global clock, but when it
answers "today", "yesterday", or "last week", it must mean the owner's day,
not the server's accident of time.

---

## Inheritance Ledger

S3 v1 inherits existing substrate rather than replacing it:

- **Invariant #1 (Time as Biography):** S3 is the shared temporal foundation.
  It makes event-time and ingest-time explicit enough for voice, recall, and
  later chapter/anniversary work.
- **ADR 0019 (Lived memory architecture):** episodes and graph validity windows
  remain the canonical lived-memory stores. S3 v1 wraps and normalizes their
  temporal inputs; it does not replace them.
- **Decision 25 / ADR 0030 (M1):** promoted lived episodes stay biography.
  S3 may normalize their time fields; it may not widen what M1 promotes or what
  TRF can read.
- **Decision 27 / ADR 0032 (S2):** external-source time remains provenance
  first. S3 may help Calendar time become a safe anchor later, but v1 does not
  convert Calendar into lived memory.
- **Decision 28 / ADR 0033 (Calendar v1):** Calendar stays disabled-default and
  external. S3 v1 does not cross the OAuth gate and does not add
  Calendar-backed TRF recall.

Load-bearing inherited rules:

- retrieval does not license lived-memory claims;
- source provenance and biography stay separate;
- helper failure never establishes memory absence;
- local human-day boundaries are part of voice honesty, not a formatting
  convenience;
- all new temporal observability is content-free.

---

## V1 Decisions From Diagnostic Questions

| Question | V1 decision |
| --- | --- |
| V1 scope | Build a shared temporal-normalization module plus tests. Do not migrate stores in v1. |
| Timezone source | All owner-local boundaries route through `MAEZ_OWNER_TIMEZONE` when set, then `core.memory.identity.timezone()`, falling back to UTC. TRF stops hardcoding `America/Chicago`. |
| Canonical names | The shared vocabulary is `event_at`, `ingested_at`, `observed_at`, `valid_from`, `valid_to`, and `owner_local_date`. Existing store fields may remain, but adapters must map them explicitly. |
| Storage strategy | Keep per-store fields in v1. Enforce normalization at module boundaries and document each store as canonical, wrapped, or deferred. |
| Anchor expansion | No new anchors in v1. Existing TRF anchors are reimplemented through the shared temporal module only. |
| Calendar inheritance | Calendar-backed temporal anchors remain out of scope for S3 v1. OAuth onboarding or Calendar burn-in success alone is not a grant. Any later Calendar-backed temporal-anchor path requires a reviewed S3 v1.1/v2 plus an S2-approved `flow.bounded_window_recall` retrieval posture and Calendar voice posture, and must phrase results as external-source provenance, not lived memory. |
| Health surface | Add aggregate, content-free counters for malformed timestamps, naive timestamps assumed UTC, unsupported anchors, helper unavailable, and timezone source. |
| Migration boundary | Legacy epoch/JSON stores are wrapped or documented; their owning organs migrate them later. |

---

## V1 Scope

### In Scope

- New shared temporal module.
- Owner timezone resolution through identity config and env overrides.
- UTC canonicalization for incoming instants.
- Local-day and local-window helpers for TRF's existing four anchors.
- Half-open interval helpers.
- Closed temporal field vocabulary.
- Content-free drift/rejection counters.
- TRF refactor to use the shared module.
- Health/sidecar projection for S3 aggregate state.
- Tests covering DST, naive timestamps, mixed ISO formats, identity timezone,
  helper failures, and unchanged TRF behavior.
- Documentation inventory of store status: canonical, wrapped, or deferred.

### Out of Scope

- Exact-date recall.
- Weekday recall.
- Month/year recall.
- Event-anchored recall.
- Multi-hop temporal questions.
- Chapter detection.
- Anniversaries.
- Rupture/repair scar tissue.
- Calendar-backed temporal anchors.
- Calendar OAuth.
- Broad database migrations.
- Graph backend replacement.
- Any new memory promotion path.

---

## Architecture

S3 v1 adds one shared module and refactors existing callers to use it.

```text
identity.yaml / MAEZ_OWNER_TIMEZONE
      |
      v
core.memory.identity.timezone()
      |
      v
core.time.temporal_spine
      |
      +--> UTC instant normalization
      +--> owner-local day/window boundaries
      +--> half-open interval helpers
      +--> closed temporal field names
      +--> content-free counters
      |
      +--> core.memory.temporal_anchor_recall
      +--> future temporal readers
      +--> /health aggregate
      +--> observe_sidecar red gates
```

`core.time.temporal_spine` is intentionally not under `core.memory`. Time is a
shared substrate for memory, information limbs, body sensors, and future
successor/repair organs.

---

## Module Contract

Create `core/time/temporal_spine.py` and `core/time/__init__.py`.

Public API:

```python
from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal
from zoneinfo import ZoneInfo

TemporalInstantFieldName = Literal[
    "event_at",
    "ingested_at",
    "observed_at",
    "valid_from",
    "valid_to",
]

TemporalDerivedFieldName = Literal[
    "owner_local_date",
]

TemporalAnchorKind = Literal[
    "earlier_today",
    "this_morning",
    "yesterday",
    "last_week",
]

HelperUnavailableReason = Literal[
    "temporal_helper_exception",
]

@dataclass(frozen=True)
class TemporalWindow:
    anchor_kind: TemporalAnchorKind
    # Owner-local aware boundaries, preserved for TRF result compatibility.
    start: datetime
    end: datetime
    # UTC-aware boundaries. Only these may be used for store filtering.
    start_utc: datetime
    end_utc: datetime
    timezone_name: str

@dataclass(frozen=True)
class TemporalDiagnostics:
    timezone_source: Literal["identity", "env", "fallback_utc", "invalid_fallback_utc"]
    timezone_name: str
    invalid_field_name_rejected_count: int
    malformed_timestamp_rejected_count: int
    naive_timestamp_assumed_utc_count: int
    unsupported_anchor_rejected_count: int
    helper_unavailable_count: int

def owner_timezone() -> ZoneInfo: ...
def timezone_source() -> str: ...
def canonical_utc(value: str | datetime, *, field_name: TemporalInstantFieldName) -> datetime: ...
def canonical_utc_iso(value: str | datetime, *, field_name: TemporalInstantFieldName) -> str: ...
def owner_local_date(value: str | datetime) -> date: ...
def temporal_window(anchor_kind: TemporalAnchorKind, reference_time: datetime) -> TemporalWindow: ...
def half_open_contains(value: str | datetime, *, start: datetime, end: datetime) -> bool: ...
def record_helper_unavailable(reason: HelperUnavailableReason) -> None: ...
def diagnostics_snapshot() -> TemporalDiagnostics: ...
def _reset_diagnostics_for_tests() -> None: ...
```

Contract rules:

- `canonical_utc(...)` returns an aware UTC `datetime`.
- `canonical_utc(...)` accepts ISO datetime strings only. Bare date strings are
  malformed instants.
- `Z`, `+00:00`, and other offset-aware strings normalize to UTC.
- Naive ISO strings and naive `datetime` values are interpreted as UTC for
  backward compatibility, and the naive-assumed counter increments.
- `field_name` is validated before timestamp parsing. Invalid names raise
  `ValueError`, increment `invalid_field_name_rejected_count`, and must not
  increment timestamp counters.
- `owner_timezone()` source resolution is: non-empty `MAEZ_OWNER_TIMEZONE` first
  (`env`), otherwise `core.memory.identity.timezone()` (`identity`), empty/None
  identity result (`fallback_utc`), invalid candidate (`invalid_fallback_utc`).
  V1 must not require a new `identity.py` public API.
- If timezone resolution falls back because a configured timezone is invalid,
  diagnostics report `timezone_source="invalid_fallback_utc"` and
  `timezone_name="UTC"`. The invalid raw timezone string must not appear in
  health, logs, sidecar samples, or red-gate names.
- `temporal_window(...)` treats a naive `reference_time` as owner-local wall
  time, matching TRF v1. Naive-as-UTC applies only to instant-normalization
  APIs such as `canonical_utc(...)`.
- Ambiguous owner-local datetimes preserve Python `fold` semantics; fold 0 and
  fold 1 are distinct instants.
- Nonexistent owner-local datetimes are rejected with `ValueError`, increment
  malformed timestamp count, and TRF must convert that helper exception to
  `helper_unavailable`.
- Local windows are computed from the owner timezone. `TemporalWindow.start` and
  `TemporalWindow.end` are owner-local aware datetimes for TRF result/voice
  compatibility; `TemporalWindow.start_utc` and `TemporalWindow.end_utc` are
  aware UTC datetimes and are the only fields allowed for persistence filtering,
  SQL window bounds, or cross-store comparison.
- Store-facing window strings must be emitted through `canonical_utc_iso(...)`
  or equivalent `+00:00` UTC serialization. Local-offset strings such as
  `-05:00` / `-06:00` must not be passed to
  `EpisodeStore.list_active_in_window(...)`.
- `half_open_contains(...)` expects aware UTC bounds and compares canonical UTC
  instants, not raw timestamp strings.
- Windows are half-open: `start <= event < end`.
- `unsupported_anchor_rejected_count` is a symbolic API-boundary counter only.
  It increments when `temporal_window(...)` receives a value outside the closed
  four-anchor enum. S3 v1 must not parse raw query text for exact dates,
  weekdays, month/year phrases, event-linked phrases, "a few days ago",
  Calendar phrases, or any other unsupported anchor.
- `record_helper_unavailable(...)` increments only the aggregate
  helper-unavailable counter. The reason is for code clarity and must not be
  exposed in `/health` unless separately reviewed.
- Diagnostic counter increments are lock-protected, best-effort, content-free,
  process-local, monotonic until process restart, and must never raise.
  Snapshots and test resets are isolated by the same module-local lock.
- `diagnostics_snapshot()` returns a copy, not a mutable module dictionary.
- `_reset_diagnostics_for_tests()` is test-only; runtime, health, and sidecar
  code must not call it.
- Diagnostics expose counts and source labels only, never timestamp values.

---

## TRF Refactor Contract

`core/memory/temporal_anchor_recall.py` must keep its public behavior and its
kill switch, but stop owning timezone/window logic.

Required changes:

- remove module-level `LOCAL_TZ = ZoneInfo("America/Chicago")`;
- call `core.time.temporal_spine.owner_timezone()` for local conversion;
- call `core.time.temporal_spine.temporal_window(...)` for all four existing
  anchor windows;
- preserve existing `TemporalAnchorRecallResult` fields and search statuses;
- preserve fail-neutral behavior on store error, timeout, disabled helper, or
  temporal helper exception;
- preserve `memory_absence_established=False`.

No new temporal anchor may be added in this refactor.

"Unchanged TRF behavior" means: when the resolved owner timezone is
`America/Chicago`, existing anchor detection gates, result fields, status
values, no-match/helper-unavailable postures, kill-switch semantics,
bounded-window definitions, and fragment-guard inputs remain field-compatible
with TRF v1. When the configured owner timezone differs, only the owner-local
calendar boundaries intentionally move.

TRF must preserve `TemporalAnchorRecallResult.window_start` and `window_end` as
owner-local aware datetimes, but must pass only `TemporalWindow.start_utc` and
`TemporalWindow.end_utc`, serialized in canonical `+00:00` UTC form, to
`EpisodeStore.list_active_in_window(...)` or any persistence/window query.

If TRF matches one of the four v1 anchors but
`temporal_spine.temporal_window(...)` raises, TRF must return
`anchor_detected=True`, the matched `anchor_kind`, `window_start=None`,
`window_end=None`, `search_status="helper_unavailable"`, empty `brief_text`,
and `memory_absence_established=False`. TRF must count that conversion through
`record_helper_unavailable("temporal_helper_exception")`.

`unsupported_anchor_rejected_count` must not be driven from raw user text. TRF
`_ANCHOR_PATTERNS` remains limited to the existing four regexes.

---

## Store Status Inventory

S3 v1 must document each touched store in one of three buckets:

| Bucket | Meaning |
| --- | --- |
| canonical | already uses typed or normalized temporal contract and can be cited as compliant |
| wrapped | existing fields remain, but access goes through S3 normalization helpers |
| deferred | existing temporal fields remain unchanged and are out of v1 runtime path |

For this inventory, "runtime path" means the S3 v1 module, TRF refactor,
`/health.temporal_spine`, and observation-sidecar projection. A deferred store
may still be active under its owning organ. Deferred means S3 v1 must not scan
it, migrate it, normalize its rows, or red-gate on its timestamp shape.

Initial v1 classification:

| Store | V1 status | Reason |
| --- | --- | --- |
| `memory/lived_episodes.db` / `episodes` | wrapped | `occurred_at` and `created_at` remain SQLite text. S3 v1 wraps the TRF read boundary only: TRF must pass UTC `+00:00` half-open bounds to `EpisodeStore.list_active_in_window(...)`. S3 v1 does not migrate rows or change `EpisodeStore.add(...)`. |
| `memory/lived_graph.db` / `edges` | canonical | `RelationshipGraph` owns graph temporal canonicalization for `valid_from` / `valid_to` and `list_active(at_time=...)`; S3 v1 must not add direct SQL graph callers or migrate graph rows. |
| `memory/m1_lived_episode_promotion.db` | deferred | M1 owns pending/promotion sidecar time, including JSON `first_owner_at`, `last_owner_at`, `window_start`, `window_end`, and `source_index.promoted_at`. S3 v1 may not read, migrate, or red-gate this sidecar. |
| `memory/private_thoughts.db` | deferred | Private-thought timestamps, including S1/S1b `ts` epoch seconds, remain owned by S1/S1b. S3 v1 may not read, migrate, or use them for temporal-spine health. |
| `memory/entity_index.db` | deferred | Entity `observed_at` / `created_at` remain owned by the entity-index organ and MSEL expansion. S3 v1 may not read, migrate, or normalize this store. |
| Calendar v1 offline store (`memory/calendar_v1.db` when enabled) | deferred | Calendar storage is noncanonical pre-body staging; Calendar OAuth/anchors remain out of S3 v1. S3 v1 may not read Calendar provider/read-model tables, migrate them, or turn Calendar time into lived-memory anchors. |

For wrapped `episodes` reads, S3 v1 must not rely on lexical SQLite TEXT
comparison across mixed `Z`, `+00:00`, local-offset, or naive ISO strings. Keep
`EpisodeStore.list_active_in_window(...)` public signature unchanged, but make
S3-touched TRF reads compare canonical UTC instants. Tests must include
mixed-offset episodes near an owner-local boundary.

---

## Health And Sidecar

Add `temporal_spine` as a nested object in the existing `GET /health`
response. Do not add a new `/health.temporal_spine` Flask route. In this spec
and tests, `/health.temporal_spine` means the JSON path
`GET /health -> temporal_spine`.

```json
{
  "timezone_source": "identity",
  "timezone_name": "America/Chicago",
  "invalid_field_name_rejected_count": 0,
  "malformed_timestamp_rejected_count": 0,
  "naive_timestamp_assumed_utc_count": 0,
  "unsupported_anchor_rejected_count": 0,
  "helper_unavailable_count": 0
}
```

Rules:

- `timezone_name` is an IANA timezone label, not content.
- If identity timezone resolution fails because the configured timezone is
  invalid, health must report `timezone_source: "invalid_fallback_utc"` and
  `timezone_name: "UTC"`.
- Counters are aggregate process counters only.
- No raw query text, timestamp values, event IDs, source IDs, memory IDs, or
  anchor phrases from user text may appear in health.
- The invalid raw timezone string must not appear in health, logs, sidecar
  samples, or red-gate names.
- `scripts.observe_sidecar.project_health(...)` must project `temporal_spine`
  with an explicit allowlist only: `timezone_source`, `timezone_name`,
  `invalid_field_name_rejected_count`, `malformed_timestamp_rejected_count`,
  `naive_timestamp_assumed_utc_count`, `unsupported_anchor_rejected_count`, and
  `helper_unavailable_count`. It must not pass through the whole health
  section.
- The first implementation must add exactly these red-gate names:
  `temporal_spine_invalid_timezone_fallback` when
  `timezone_source == "invalid_fallback_utc"` and
  `temporal_spine_malformed_timestamp_rejected` when
  `malformed_timestamp_rejected_count > 0`.
- No temporal-spine red gate may include timezone names, raw counter values,
  anchor phrases, timestamp values, source IDs, memory IDs, user text, or
  exception text. Unsupported anchors, invalid field names, naive timestamps,
  and helper-unavailable remain watch-only in v1.

---

## RED Test Contract

Minimum tests before implementation:

1. `_reset_diagnostics_for_tests()` clears all counters and timezone-source
   state between tests.
2. diagnostics counters are isolated: one malformed timestamp test does not
   affect the next naive timestamp test.
3. diagnostics counters are thread-safe under concurrent increments.
4. non-empty `MAEZ_OWNER_TIMEZONE` reports timezone source `env`.
5. `owner_timezone()` reads `core.memory.identity.timezone()` when env is empty.
6. invalid identity timezone falls back to UTC and reports
   `invalid_fallback_utc`.
7. missing or empty identity timezone falls back to UTC and reports
   `fallback_utc`.
8. invalid raw timezone string is absent from health, sidecar samples, logs, and
   red-gate names.
9. `canonical_utc_iso("2026-05-15T12:00:00Z")` emits `+00:00` UTC form.
10. `canonical_utc_iso("2026-05-15T07:00:00-05:00")` emits the same instant in
    `+00:00` UTC form.
11. naive `datetime` is treated as UTC and increments the naive counter.
12. naive ISO datetime string input is treated as UTC and increments the naive
    counter.
13. bare date strings are rejected as malformed instants.
14. malformed timestamp raises `ValueError` and increments malformed counter.
15. invalid `field_name` raises `ValueError`, increments
    `invalid_field_name_rejected_count`, and does not parse the timestamp.
16. ambiguous fall-back owner-local time preserves `fold`: fold 0 and fold 1
    canonicalize to different UTC instants.
17. nonexistent spring-forward owner-local time is rejected and increments the
    malformed counter.
18. `owner_local_date(...)` uses configured owner timezone, not UTC date.
19. `temporal_window("earlier_today", ref)` matches local midnight through ref.
20. `temporal_window("this_morning", ref)` matches local midnight through noon.
21. `temporal_window("yesterday", ref)` follows local calendar day across DST.
22. `temporal_window("last_week", ref)` uses previous completed Monday-Sunday.
23. all windows are half-open.
24. `TemporalWindow.start` / `end` are owner-local aware datetimes, and
    `start_utc` / `end_utc` are UTC-aware datetimes suitable for store filters.
25. unsupported anchor raises `ValueError` and increments unsupported counter.
26. `temporal_window(...)` rejects a nonexistent owner-local `reference_time`;
    TRF maps that exception to `helper_unavailable`.
27. no code path imports `ZoneInfo("America/Chicago")` in TRF after refactor.
28. TRF `last week` behavior remains unchanged after the refactor.
29. TRF `yesterday` DST test remains unchanged after the refactor.
30. TRF still does not activate without memory intent.
31. TRF still does not scan full episode store.
32. TRF helper error remains `helper_unavailable`, not memory absence.
33. TRF kill switch still disables only temporal-anchor evidence lookup.
34. TRF passes `+00:00` UTC ISO bounds to `EpisodeStore.list_active_in_window(...)`;
    no local-offset ISO string reaches the SQLite range predicate.
35. TRF includes an episode at `2026-05-11T04:30:00+00:00` for a Chicago
    `last_week` window ending at local `2026-05-11T00:00:00-05:00`, and excludes
    an episode exactly at `2026-05-11T05:00:00+00:00`.
36. Episode window tests cover mixed `Z`, `+00:00`, local-offset, and naive
    strings; S3 correctness may not depend on raw ISO string ordering.
37. `/health` exposes `temporal_spine` aggregate fields.
38. `/health.temporal_spine` does not expose raw timestamps, source IDs, memory
    IDs, user text, exception text, or invalid raw timezone strings.
39. sidecar projects temporal-spine aggregate fields content-free through an
    explicit allowlist.
40. sidecar red-gates invalid timezone fallback with exactly
    `temporal_spine_invalid_timezone_fallback`.
41. sidecar red-gates malformed timestamp count greater than zero with exactly
    `temporal_spine_malformed_timestamp_rejected`.
42. sidecar does not red-gate unsupported anchors by default.
43. sidecar does not red-gate naive timestamps, invalid field names, or
    helper-unavailable in v1.
44. store-status inventory exists in docs and names canonical/wrapped/deferred.
45. existing `tests.test_temporal_recall_fragment_guard` remains green.
46. full suite remains green.

---

## Named Engineering Choices Preserved

The Codex engineering review surfaced four choices that must stay explicit:

- **D1 - TemporalWindow dual surface:** `start` / `end` stay owner-local for
  TRF result compatibility; `start_utc` / `end_utc` are the only store-facing
  boundaries. This resolves the review tension between voice compatibility and
  SQLite correctness without overloading one field pair.
- **D2 - Deferred means outside S3, not inactive:** deferred stores may still
  run under their owning organs. S3 v1 simply does not scan, migrate, normalize,
  or red-gate them.
- **D3 - Helper-unavailable counter scope:** `helper_unavailable_count` tracks
  only temporal-spine helper exceptions converted to fail-neutral TRF posture.
  Store errors, timeouts, and the TRF kill switch keep their existing TRF
  behavior and do not increment this S3 counter.
- **D4 - Calendar success is not a temporal grant:** OAuth onboarding or
  Calendar burn-in does not unlock Calendar-backed recall. That requires a
  separate reviewed S3 v1.1/v2 grant under S2 and Calendar voice posture.

---

## Review Protocol

S3 is covenant-shaped because it touches Time as Biography. Before
implementation:

- Codex engineering panel reviews the spec for implementation ambiguity,
  race/counter behavior, store-boundary risk, and test completeness. The first
  Codex panel returned REVISE/RATIFY-WITH-AMENDMENTS and was folded into this
  spec; see [`reviews/spec-codex-panel.md`](reviews/spec-codex-panel.md).
- Claude covenant council reviews the spec for invariant #1 alignment and for
  whether the "UTC storage, owner-local boundary" rule preserves voice honesty.
- Fold both review lanes before code.

Post-implementation:

- Codex panel verifies the module, tests, health/sidecar wiring, and TRF
  behavior.
- Claude council verifies that no temporal helper now licenses memory absence,
  Calendar biography, or false lived claims.

---

## Implementation Order

1. RED tests for `core.time.temporal_spine` pure helpers.
2. Implement pure helper module.
3. RED tests for TRF refactor preserving existing behavior.
4. Refactor TRF to use S3 helpers.
5. RED tests for `/health.temporal_spine`.
6. Add daemon health aggregate.
7. RED tests for sidecar projection/red gates.
8. Add sidecar projection/red gates.
9. Add store-status inventory note to this spec or companion doc.
10. Run focused tests, Ruff, full suite.
11. Post-implementation both-lane review.
12. Recovery commit if review finds gaps.
13. Push only after recovery and verification.

---

## Predicted Effect

After S3 v1 implementation:

- TRF produces the same answers for its current four anchors, but its window
  math comes from the shared temporal spine.
- M1 and future per-day-cap organs have one canonical pattern: UTC timestamps
  for storage, owner-local day boundaries for human caps.
- `/health` and the observation sidecar can detect malformed timestamp drift
  and invalid timezone fallback without reading content.
- Future exact-date, weekday, chapter, anniversary, and Calendar-backed
  temporal work can build on one module instead of copying local time logic.

---

## Plain English

Maez has learned several little clocks: one for "last week", one for promoted
memories, one for relationship validity, one for Calendar events, one for the
owner's local day. S3 v1 is not the big memory time machine yet. It is the wall
clock all those little clocks agree to use.

The important rule is simple: save timestamps in UTC so the record is stable,
but interpret "today", "yesterday", and "last week" in the user's timezone so
Maez speaks about time the way the user lives it.
