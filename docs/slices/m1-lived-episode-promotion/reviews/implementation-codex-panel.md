# Codex Six-Agent Panel — M1 implementation review (post-impl)

**Date:** 2026-05-14  
**Scope:** implementation commit `42aafce` plus recovery work after panel review.  
**Subject:** Decision 25 / ADR 0030, M1 lived-episode promotion from bonded
conversation.

## Verdict

**Initial verdict:** BLOCK / REVISE.  
**Post-recovery verdict:** RATIFY-WITH-RECOVERY.

No panel seat found raw transcript leakage in promoted M1 summaries. The core
load-bearing rule, "promote biography; do not widen recall," remains intact.
The panel did find real engineering holes around surface scope, sidecar
continuity, partial-overlap semantics, runtime race safety, and reader-side
testing. Recovery commits close those mechanically.

## Seat Findings

### Descartes — Blocker Logic

**Verdict:** BLOCK.

- **M1-DESC-B1:** M1 was wired to every `handle_message(...)` surface, not only
  bonded Telegram DM. UI/web/voice turns could be promoted as
  `source_kind="telegram_exchange"`.
- **M1-DESC-B2:** Source-ID idempotency depended only on the M1 sidecar. If the
  sidecar was lost or restored behind `lived_episodes.db`, duplicate promotion
  could occur.
- **M1-DESC-R1:** Partial-overlap promotion could assign the original window
  timestamp to the unpromoted remainder, putting an episode in the wrong
  temporal window.

### Ohm — Runtime Reliability

**Verdict:** REVISE.

- **M1-OHM-1:** Turn-close promotion and daemon-cycle flush could race on the
  same pending-window row.
- **M1-OHM-2:** Rate limiting dropped eligible source IDs because callers cleared
  the pending window even when `promote_window(...)` returned `rate_limited`.
- **M1-OHM-3:** `/health` scanned all active lived episodes and did the scan twice
  on a single-threaded server path.

### Locke — Identity And Provenance

**Verdict:** BLOCK.

- **M1-CX-B1:** M1 sidecar state was not in the Decision 22 backup manifest; loss
  of the sidecar erased promotion provenance and idempotency continuity.
- **M1-CX-B2:** Partial-overlap promotion could promote a non-eligible remainder
  by carrying the original eligibility reason forward.
- **M1-CX-R1:** `Rohit` is hardcoded in v1 title/summary/participants. Accepted
  for founder Maez v1 but queued for OSS portability.

### Feynman — Test Contract

**Verdict:** REVISE.

- **M1-FY-1:** Tests did not prove M1 was Telegram-DM-only.
- **M1-FY-2:** Tests blessed partial-overlap promotion rather than rejecting the
  unsafe remainder case.
- **M1-FY-3:** Promotion provenance envelope was written but uninspectable and
  untested.
- **M1-FY-4:** Third-party marker negatives were too narrow.
- **M1-FY-5:** Reader-side behavior tests did not prove TRF avoided surfacing the
  generic storage title.

### Goodall — Live Behavior

**Verdict:** REVISE.

- **M1-GD-1:** M1 promoted non-Telegram surfaces as `telegram_exchange`.
- **M1-GD-2:** "Remember this" promoted the whole pending window, not the current
  exchange.
- **M1-GD-3:** V1 structural summaries are intentionally thin; live observation
  must treat "remembers that the exchange happened" as v1 scope, not "remembers
  what was said."
- **M1-GD-4:** Disabled-state observation needed less noisy logs and clearer
  health state.

### Dewey — Integration And Prior Art

**Verdict:** BLOCK.

- **M1-DW-1:** TRF preferred `title` over `summary`, so M1 episodes would surface
  the generic storage label "Bonded conversation with Rohit."
- **M1-DW-2:** Third-party reported markers still triggered promotion.
- **M1-DW-3:** Partial-overlap promotion could promote a remainder using
  eligibility from already-promoted source IDs.

## Recovery Closure

The recovery patch closes the blocking findings mechanically:

- M1 promotion is gated to `M1_ALLOWED_PROMOTION_SOURCES`, currently
  `telegram_surface` and `telegram_text`.
- Daemon turn-close promotion and daemon-cycle flush share `self._m1_lock`.
- Explicit marker promotion writes only the current audited exchange.
- Partial-overlap candidates now skip in v1 with `partial_overlap`.
- Rate-limited windows persist as `deferred_rate_limited` instead of being
  dropped.
- `M1PromotionStore` rebuilds source-id idempotency from existing
  `telegram_exchange` episodes on init.
- `memory/m1_lived_episode_promotion.db` is included in the Decision 22 backup
  manifest.
- Promotion provenance is inspectable through `get_provenance(...)` and tested.
- Marker detection rejects named/possessive third-party reports such as
  "Anna said remember this" and "my mom told me save this."
- `/health` exposes content-free M1 enabled/pending state.
- Lived-episode freshness uses a bounded aggregate query instead of full row
  scans when backed by `EpisodeStore`.
- TRF now uses structural summary text for `source_kind="telegram_exchange"` so
  it does not mechanically surface the generic storage title.

## Verification

Focused recovery verification:

```bash
.venv/bin/python -m unittest \
  tests.test_m1_lived_episode_promotion \
  tests.test_m1_daemon_wiring \
  tests.test_temporal_recall_fragment_guard \
  tests.test_nightly_lived_memory \
  tests.test_memory_integrity_invariant
```

Result: 88 tests passed. Existing sqlite `ResourceWarning` noise remains present
in the focused suite output and is not treated as closed by M1.

