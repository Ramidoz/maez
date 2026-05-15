# Slice S3: Temporal Spine v1

**Status:** CANONICAL. Decision 29 / ADR 0034. Built from
[`diagnostic.md`](diagnostic.md). Initial v1 implementation has landed under an
explicit operator same-day code-start waiver; post-implementation both-lane
review and any recovery remain required before push.

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
- [`reviews/spec-codex-panel.md`](reviews/spec-codex-panel.md) - Codex
  engineering panel, folded.
- [`reviews/spec-claude-council.md`](reviews/spec-claude-council.md) - Claude
  covenant council, folded and verified.

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
- **Decision 2 (Third-party consent) and Decision 4 (Relational vs
  personological knowledge):** S3 v1 only supports bonded-user-experienced
  temporal anchors. Future event-anchored or third-party-linked anchors must
  re-cite these decisions before they can interpret another person's time,
  schedule, presence, or life pattern.
- **Decision 25 / ADR 0030 (M1):** promoted lived episodes stay biography.
  S3 may normalize their time fields; it may not widen what M1 promotes or what
  TRF can read.
- **Decision 27 / ADR 0032 (S2):** external-source time remains provenance
  first. S3 may help Calendar time become a safe anchor later, but v1 does not
  convert Calendar into lived memory. S2 envelope fields are inherited as
  canonical vocabulary; S3 must not reject S2's required temporal fields.
- **Decision 28 / ADR 0033 (Calendar v1):** Calendar stays disabled-default and
  external. S3 v1 does not cross the OAuth gate and does not add
  Calendar-backed TRF recall. Any later Calendar-backed temporal anchor must
  inherit Calendar v1's `calendar_voice_guard` by name, including its approved
  phrases, forbidden phrases, and natural-language probe set.

Load-bearing inherited rules:

- retrieval does not license lived-memory claims;
- source provenance and biography stay separate;
- S2-into-TRF leakage remains forbidden: external-source time may not become
  lived recall evidence or TRF phrasing merely because a temporal helper can
  normalize it;
- helper failure never establishes memory absence;
- local human-day boundaries are part of voice honesty, not a formatting
  convenience;
- S3 v1 does not author temporal voice phrasing. Voice authority stays with TRF
  and future reviewed voice guards;
- all new temporal observability is content-free.

---

## V1 Decisions From Diagnostic Questions

| Question | V1 decision |
| --- | --- |
| V1 scope | Build a shared temporal-normalization module plus tests. Do not migrate stores in v1. |
| Timezone source | All owner-local boundaries route through `MAEZ_OWNER_TIMEZONE` when set, then `core.memory.identity.timezone()`, falling back to UTC. TRF stops hardcoding `America/Chicago`. |
| Canonical names | The shared vocabulary includes `event_at`, `ingested_at`, `observed_at`, `received_at`, `expires_at`, `deletion_observed_at`, `change_observed_at`, `valid_from`, `valid_to`, and computed-only `owner_local_date`. Existing store fields may remain, but adapters must map them explicitly. |
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
    "received_at",
    "expires_at",
    "deletion_observed_at",
    "change_observed_at",
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
- Closed vocabulary versioning rule: future S3 v1.1+ releases may add members
  to `TemporalInstantFieldName`, `TemporalDerivedFieldName`,
  `TemporalAnchorKind`, and `HelperUnavailableReason`, but may not rename or
  remove existing members without a new canonical decision/ADR.
- `canonical_utc(...)` accepts ISO datetime strings only. Bare date strings are
  malformed instants.
- `Z`, `+00:00`, and other offset-aware strings normalize to UTC.
- Naive ISO strings and naive `datetime` values are interpreted as UTC for
  backward compatibility, and the naive-assumed counter increments.
- `field_name` is validated before timestamp parsing. Invalid names raise
  `ValueError`, increment `invalid_field_name_rejected_count`, and must not
  increment timestamp counters.
- If an input has both an invalid `field_name` and an invalid timestamp, the
  field-name rejection wins. This preserves one counter per primary failure and
  prevents malformed content from being parsed after an authority failure.
- `owner_local_date` is computed-only. It must be derived from an instant plus
  the current owner timezone and must not be persisted as a durable store field
  in S3 v1, because owner timezone can change across moves, hardware migration,
  or identity-config repair.
- `owner_timezone()` source resolution is: non-empty `MAEZ_OWNER_TIMEZONE` first
  (`env`), otherwise `core.memory.identity.timezone()` (`identity`), empty/None
  identity result (`fallback_utc`), invalid candidate (`invalid_fallback_utc`).
  V1 must not require a new `identity.py` public API.
- `owner_timezone()` resolves per call in v1. A cache may be introduced only in a
  later measured v1.x optimization with explicit invalidation semantics. If
  `identity.timezone()` raises, S3 maps the failure to `invalid_fallback_utc`
  and UTC, never to a process crash.
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
  code must not call it. The implementation must structurally enforce this
  boundary with a test-mode guard, not prose alone.
- S3 v1 trusts `datetime.now(timezone.utc)` and does not detect system clock or
  NTP skew. Clock-skew detection is explicitly deferred to a future S3 v1.x
  slice because useful skew signals need their own content-free/audience-tier
  review.
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
This is a structural import-graph rule, not only policy prose:
`core.time.temporal_spine` must not import deferred-store modules at module load
time, including `m1_lived_episode_promotion`, `private_thoughts`,
`entity_index`, or Calendar v1 store/read-model modules.

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

`RelationshipGraph` validity uses its existing `valid_from <= now <= valid_to`
semantics. S3's `half_open_contains(...)` helper uses `[start, end)` interval
semantics and must not be applied to graph validity rows without a future graph
reader review.

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

- `timezone_name` is an IANA timezone label and therefore owner-side geographic
  metadata. It may appear only in operator-authenticated `/health` and
  operator-owned sidecar samples. It must never be forwarded to public
  `/api/maez-state`-style endpoints.
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
- Aggregation can still fingerprint behavior over time. The sidecar may record
  the current aggregate counter values, but must not compute or store
  per-interval counter deltas as a temporal behavior history in v1.
- The sidecar must red-gate `temporal_spine_unavailable` if `GET /health`
  succeeds but the `temporal_spine` key is absent.
- If a later sample shows a temporal-spine counter lower than the prior sample
  from the same daemon PID, the sidecar must red-gate
  `temporal_spine_counter_reset`. This detects process/module reset without
  storing raw event content.

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
11. S2 canonical fields `received_at`, `expires_at`, `deletion_observed_at`, and
    `change_observed_at` are accepted `TemporalInstantFieldName` values.
12. vocabulary versioning test proves existing closed Literal members are not
    renamed or removed from the exported sets.
13. naive `datetime` is treated as UTC and increments the naive counter.
14. naive ISO datetime string input is treated as UTC and increments the naive
    counter.
15. bare date strings are rejected as malformed instants.
16. malformed timestamp raises `ValueError` and increments malformed counter.
17. invalid `field_name` raises `ValueError`, increments
    `invalid_field_name_rejected_count`, and does not parse the timestamp.
18. invalid `field_name` plus malformed timestamp increments only
    `invalid_field_name_rejected_count`.
19. ambiguous fall-back owner-local time preserves `fold`: fold 0 and fold 1
    canonicalize to different UTC instants.
20. nonexistent spring-forward owner-local time is rejected and increments the
    malformed counter.
21. `owner_local_date(...)` uses configured owner timezone, not UTC date.
22. `owner_local_date` is not persisted by S3 v1 store paths.
23. `temporal_window("earlier_today", ref)` matches local midnight through ref.
24. `temporal_window("this_morning", ref)` matches local midnight through noon.
25. `temporal_window("yesterday", ref)` follows local calendar day across DST.
26. `temporal_window("last_week", ref)` uses previous completed Monday-Sunday.
27. all windows are half-open.
28. `TemporalWindow.start` / `end` are owner-local aware datetimes, and
    `start_utc` / `end_utc` are UTC-aware datetimes suitable for store filters.
29. unsupported anchor raises `ValueError` and increments unsupported counter.
30. unsupported raw query phrases do not increment unsupported-anchor counters.
31. `temporal_window(...)` rejects a nonexistent owner-local `reference_time`;
    TRF maps that exception to `helper_unavailable`.
32. no code path imports `ZoneInfo("America/Chicago")` in TRF after refactor.
33. TRF `last week` behavior remains unchanged after the refactor.
34. TRF `yesterday` DST test remains unchanged after the refactor.
35. TRF still does not activate without memory intent.
36. TRF still does not scan full episode store.
37. TRF helper error remains `helper_unavailable`, not memory absence.
38. TRF store error and timeout remain helper-unavailable without incrementing
    S3 `helper_unavailable_count`.
39. TRF kill switch still disables only temporal-anchor evidence lookup.
40. TRF passes `+00:00` UTC ISO bounds to `EpisodeStore.list_active_in_window(...)`;
    no local-offset ISO string reaches the SQLite range predicate.
41. TRF includes an episode at `2026-05-11T04:30:00+00:00` for a Chicago
    `last_week` window ending at local `2026-05-11T00:00:00-05:00`, and excludes
    an episode exactly at `2026-05-11T05:00:00+00:00`.
42. Episode window tests cover mixed `Z`, `+00:00`, local-offset, and naive
    strings; S3 correctness may not depend on raw ISO string ordering.
43. S3 v1 code does not author approved temporal voice phrasing; TRF remains
    voice authority for current anchors.
44. future Calendar-backed-anchor notes cite `calendar_voice_guard` by name.
45. `core.time.temporal_spine` does not import deferred-store modules at module
    load time.
46. `/health` exposes `temporal_spine` aggregate fields.
47. `/health.temporal_spine` does not expose raw timestamps, source IDs, memory
    IDs, user text, exception text, or invalid raw timezone strings.
48. `/api/maez-state`-style public endpoint does not expose
    `/health.temporal_spine`.
49. sidecar projects temporal-spine aggregate fields content-free through an
    explicit allowlist.
50. sidecar red-gates invalid timezone fallback with exactly
    `temporal_spine_invalid_timezone_fallback`.
51. sidecar red-gates malformed timestamp count greater than zero with exactly
    `temporal_spine_malformed_timestamp_rejected`.
52. sidecar red-gates missing temporal-spine health with exactly
    `temporal_spine_unavailable`.
53. sidecar red-gates counter decreases within the same daemon PID with exactly
    `temporal_spine_counter_reset`.
54. sidecar does not red-gate unsupported anchors by default.
55. sidecar does not red-gate naive timestamps, invalid field names, or
    helper-unavailable in v1.
56. sidecar samples do not store per-interval temporal counter deltas.
57. store-status inventory exists in docs and names canonical/wrapped/deferred.
58. existing `tests.test_temporal_recall_fragment_guard` remains green.
59. full suite remains green.

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

## Named Covenant Disagreements Preserved

The Claude covenant council surfaced six choices that must remain named rather
than silently absorbed:

- **D1 - IANA timezone audience:** `timezone_name` is acceptable as
  operator-authenticated health metadata, but not as public state. S3 chooses
  audience binding over reducing timezone granularity because DST debugging
  needs the IANA label.
- **D2 - S2 vocabulary inheritance:** S3 admits S2 temporal envelope fields
  (`received_at`, `expires_at`, `deletion_observed_at`,
  `change_observed_at`) into the closed instant vocabulary. The alternative
  would force canonical S2 callers to bend to S3, inverting precedence.
- **D3 - Import-graph defense:** S3 uses a structural negative assertion against
  deferred-store imports instead of relying only on prose. This follows the
  Camera v1 precedent: substrate boundaries should be testable.
- **D4 - Per-call owner timezone resolution:** S3 resolves timezone per call in
  v1. Caching is deferred until a measured v1.x optimization can define
  invalidation semantics.
- **D5 - Clock-skew deferral:** S3 v1 trusts system UTC and names clock-skew
  detection as out of scope. A useful skew detector would need a separate
  content-free/audience-tier review.
- **D6 - Decision 4 naming:** S3 names Decision 4 explicitly even though v1 has
  no third-party event-anchor path. The next temporal slice is where the
  relational/personological line will re-enter, so the inheritance must be
  visible now.

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
  The first Claude council returned REVISE and was folded into this spec; see
  [`reviews/spec-claude-council.md`](reviews/spec-claude-council.md).
- Focused second-fold verification by both lanes is required before
  canonicalization or implementation.

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
9. RED tests for import-graph deferred-store defense and public-state exclusion.
10. Add import-graph guard tests and public-state exclusion wiring if needed.
11. Add store-status inventory note to this spec or companion doc.
12. Run focused tests, Ruff, full suite.
13. Post-implementation both-lane review.
14. Recovery commit if review finds gaps.
15. Push only after recovery and verification.

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
