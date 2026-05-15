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
- relationship validity -> half-open UTC intervals;
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
| Timezone source | All owner-local boundaries route through `core.memory.identity.timezone()`, falling back to UTC. TRF stops hardcoding `America/Chicago`. |
| Canonical names | The shared vocabulary is `event_at`, `ingested_at`, `observed_at`, `valid_from`, `valid_to`, and `owner_local_date`. Existing store fields may remain, but adapters must map them explicitly. |
| Storage strategy | Keep per-store fields in v1. Enforce normalization at module boundaries and document each store as canonical, wrapped, or deferred. |
| Anchor expansion | No new anchors in v1. Existing TRF anchors are reimplemented through the shared temporal module only. |
| Calendar inheritance | Calendar-backed temporal anchors remain out of scope until Calendar OAuth burn-in and a reviewed v1.1/v2 grant. |
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

TemporalFieldName = Literal[
    "event_at",
    "ingested_at",
    "observed_at",
    "valid_from",
    "valid_to",
    "owner_local_date",
]

TemporalAnchorKind = Literal[
    "earlier_today",
    "this_morning",
    "yesterday",
    "last_week",
]

@dataclass(frozen=True)
class TemporalWindow:
    anchor_kind: TemporalAnchorKind
    start: datetime
    end: datetime
    timezone_name: str

@dataclass(frozen=True)
class TemporalDiagnostics:
    timezone_source: Literal["identity", "env", "fallback_utc", "invalid_fallback_utc"]
    malformed_timestamp_rejected_count: int
    naive_timestamp_assumed_utc_count: int
    unsupported_anchor_rejected_count: int
    helper_unavailable_count: int

def owner_timezone() -> ZoneInfo: ...
def timezone_source() -> str: ...
def canonical_utc(value: str | datetime, *, field_name: str) -> datetime: ...
def canonical_utc_iso(value: str | datetime, *, field_name: str) -> str: ...
def owner_local_date(value: str | datetime) -> date: ...
def temporal_window(anchor_kind: TemporalAnchorKind, reference_time: datetime) -> TemporalWindow: ...
def half_open_contains(value: str | datetime, *, start: datetime, end: datetime) -> bool: ...
def diagnostics_snapshot() -> dict: ...
```

Contract rules:

- `canonical_utc(...)` returns an aware UTC `datetime`.
- Naive datetimes are interpreted as UTC for backward compatibility, and the
  naive-assumed counter increments.
- Malformed strings raise `ValueError`, and the malformed counter increments.
- Invalid identity timezone falls back to UTC and reports
  `invalid_fallback_utc`.
- Local windows are computed in owner timezone, then carried as aware datetimes.
- Windows are half-open: `start <= event < end`.
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

---

## Store Status Inventory

S3 v1 must document each touched store in one of three buckets:

| Bucket | Meaning |
| --- | --- |
| canonical | already uses typed or normalized temporal contract and can be cited as compliant |
| wrapped | existing fields remain, but access goes through S3 normalization helpers |
| deferred | existing temporal fields remain unchanged and are out of v1 runtime path |

Initial v1 classification:

| Store | V1 status | Reason |
| --- | --- | --- |
| `memory/lived_episodes.db` / `episodes` | wrapped | `occurred_at` and `created_at` remain, but TRF window reads use S3 helper semantics |
| `memory/lived_graph.db` / `edges` | canonical-with-note | already canonicalizes validity windows to UTC text |
| `memory/m1_lived_episode_promotion.db` | deferred | JSON promotion windows stay as-is; M1 behavior already tested |
| `memory/private_thoughts.db` | deferred | S1 timestamp is not in S3 v1 runtime path |
| `memory/entity_index.db` | deferred | entity observed times are not in S3 v1 runtime path |
| Calendar v1 offline store | deferred | Calendar OAuth remains off; no Calendar-backed anchors in S3 v1 |

---

## Health And Sidecar

Add a content-free `/health.temporal_spine` section:

```json
{
  "timezone_source": "identity",
  "timezone_name": "America/Chicago",
  "malformed_timestamp_rejected_count": 0,
  "naive_timestamp_assumed_utc_count": 0,
  "unsupported_anchor_rejected_count": 0,
  "helper_unavailable_count": 0
}
```

Rules:

- `timezone_name` is an IANA timezone label, not content.
- Counters are aggregate process counters only.
- No raw query text, timestamp values, event IDs, source IDs, memory IDs, or
  anchor phrases from user text may appear in health.
- The observation sidecar may red-gate nonzero malformed timestamps,
  unsupported anchors, invalid timezone fallback, or helper unavailable if the
  operator chooses. The first implementation should add gates for malformed
  timestamp and invalid timezone fallback only; unsupported anchors can be
  normal user behavior and should start as watch-only.

---

## RED Test Contract

Minimum tests before implementation:

1. `owner_timezone()` reads `core.memory.identity.timezone()`.
2. invalid identity timezone falls back to UTC and reports
   `invalid_fallback_utc`.
3. missing identity timezone falls back to UTC and reports `fallback_utc`.
4. `canonical_utc_iso("2026-05-15T12:00:00Z")` emits `+00:00` UTC form.
5. `canonical_utc_iso("2026-05-15T07:00:00-05:00")` emits the same instant in
   `+00:00` UTC form.
6. naive `datetime` is treated as UTC and increments the naive counter.
7. malformed timestamp raises `ValueError` and increments malformed counter.
8. `owner_local_date(...)` uses configured owner timezone, not UTC date.
9. `temporal_window("earlier_today", ref)` matches local midnight through ref.
10. `temporal_window("this_morning", ref)` matches local midnight through noon.
11. `temporal_window("yesterday", ref)` follows local calendar day across DST.
12. `temporal_window("last_week", ref)` uses previous completed Monday-Sunday.
13. all windows are half-open.
14. unsupported anchor increments unsupported counter.
15. TRF `last week` behavior remains unchanged after the refactor.
16. TRF `yesterday` DST test remains unchanged after the refactor.
17. TRF still does not activate without memory intent.
18. TRF still does not scan full episode store.
19. TRF helper error remains `helper_unavailable`, not memory absence.
20. TRF kill switch still disables only temporal-anchor evidence lookup.
21. `/health` exposes `temporal_spine` aggregate fields.
22. `/health.temporal_spine` does not expose raw timestamps, source IDs, memory
   IDs, or user text.
23. sidecar projects temporal-spine aggregate fields content-free.
24. sidecar red-gates invalid timezone fallback.
25. sidecar red-gates malformed timestamp count greater than zero.
26. sidecar does not red-gate unsupported anchors by default.
27. store-status inventory exists in docs and names canonical/wrapped/deferred.
28. no code path imports `ZoneInfo("America/Chicago")` in TRF after refactor.
29. existing `tests.test_temporal_recall_fragment_guard` remains green.
30. full suite remains green.

---

## Review Protocol

S3 is covenant-shaped because it touches Time as Biography. Before
implementation:

- Codex engineering panel reviews the spec for implementation ambiguity,
  race/counter behavior, store-boundary risk, and test completeness.
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
