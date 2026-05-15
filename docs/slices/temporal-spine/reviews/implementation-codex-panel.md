# Codex Post-Implementation Engineering Panel — S3 Temporal Spine v1

**Subject:** `293fd67 feat(temporal): implement S3 temporal spine v1` —
post-implementation engineering review before push.

**Panel ran:** 2026-05-15, after the Claude covenant lane ratified the
initial implementation. This review checks implementation completeness,
runtime edge cases, SQL behavior, health/public surfaces, and test
coverage against `docs/slices/temporal-spine/spec.md`.

**Initial verdict:** **BLOCK / REVISE.** One blocking implementation
gap and seven recovery-class findings. No new architecture requested.

**Recovery status:** Folded in follow-up recovery work before push.

---

## Seat Verdicts

| Seat | Verdict | Headline |
|---|---|---|
| TRF / EpisodeStore | **BLOCK** | `list_active_in_window()` materialized all active episodes before Python filtering |
| Schema / State | **REVISE** | generated DST-nonexistent window boundaries and non-UTC bounds were under-specified in code |
| Runtime / Import Graph | **REVISE** | EpisodeStore imported S3 at module load, widening activation beyond the wrapped call path |
| Health / Public / Sidecar | **REVISE** | `/api/debug/services` leaked `temporal_spine`; missing-health samples could double red-gate |
| Operational / Performance | **REVISE** | SQL predicate and candidate bounding needed explicit tests |
| Test Coverage | **RATIFY-WITH-AMENDMENTS** | RED contract existed but needed stronger behavioral tests for panel gaps |

---

## Findings And Recovery

| # | Severity | Finding | Recovery |
|---|---|---|---|
| F1 | BLOCK | `EpisodeStore.list_active_in_window()` selected every active row and filtered in Python, violating the bounded-query contract and risking large-store latency. | Added a coarse SQL date predicate using `substr(COALESCE(occurred_at, created_at), 1, 10)` before canonical Python verification. Added regression proving old rows are not materialized. |
| F2 | HIGH | EpisodeStore imported `core.time.temporal_spine` at module load, activating S3 for every EpisodeStore user rather than only the wrapped temporal query path. | Moved S3 import into `list_active_in_window()`. |
| F3 | HIGH | Ordinary stored-row parsing could increment public malformed-timestamp diagnostics, conflating historical data quality with runtime API-boundary failures. | Added non-mutating `try_canonical_utc()` for stored-row reads and regression coverage for malformed stored rows. |
| F4 | HIGH | `timezone_source()` could report stale fallback state until another call resolved owner timezone. | `timezone_source()` now resolves `owner_timezone()` before snapshotting diagnostics. |
| F5 | HIGH | `temporal_window()` validated the reference timestamp but not generated local boundaries; zones with midnight DST jumps could emit nonexistent bounds. | Generated `start` and `end` boundaries are now validated before returning a `TemporalWindow`. |
| F6 | MEDIUM | `half_open_contains()` silently accepted non-UTC aware bounds and converted them, despite the S3 contract requiring UTC bounds. | Added explicit UTC-bound rejection and regression coverage. |
| F7 | MEDIUM | Public debug route `/api/debug/services` returned raw daemon health including `temporal_spine`, bypassing the `/api/maez-state` strip. | Strip `temporal_spine` from `/api/debug/services` daemon payload. |
| F8 | MEDIUM | Sidecar could report both `temporal_spine_unavailable` and `temporal_spine_counter_reset` on the same sample when the current sample lacked the temporal aggregate. | Counter-reset detection now requires both current and previous samples to carry `temporal_spine_present=True` with the same daemon PID. |

---

## RED Coverage Added

- `tests/test_temporal_recall_fragment_guard.py` pins bounded SQL candidate
  filtering, mixed-offset canonical comparison, and non-mutating malformed
  stored-row reads.
- `tests/test_temporal_spine.py` pins fresh `timezone_source()` resolution,
  generated DST-nonexistent boundary rejection, UTC-only half-open bounds,
  runtime-only reset guard behavior, `/api/debug/services` public stripping,
  and sidecar no-double-red-gate behavior.

---

## Panel Outcome After Recovery

**RATIFY-WITH-RECOVERY.** The recovery keeps S3's contract-module shape
intact: no new voice surface, no new persistence, no public timezone
surface, no broad EpisodeStore activation, and no full-store scans for
temporal recall.

The remaining post-recovery step is focused verification by the covenant
lane, then push once both lanes are closed.

*This panel review records the engineering lane. It does not amend the
S3 spec and does not introduce new covenant law.*
