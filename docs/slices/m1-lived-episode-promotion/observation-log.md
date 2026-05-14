# M1 Lived-Episode Promotion Observation Log

**Slice:** M1 lived-episode promotion from bonded conversation  
**Decision:** Decision 25 / ADR 0030  
**Runtime flag:** `MAEZ_M1_LIVED_EPISODE_PROMOTION`

## Observation Standard

M1 v1 remembers that a bounded bonded Telegram exchange happened, when it
happened, why it was promoted, and which raw source IDs prove it.

M1 v1 does not make raw conversation contents TRF-readable biography. A live
observation should not be judged as failing merely because Maez cannot quote or
summarize what was said inside a promoted exchange.

## 2026-05-14 Enablement

**Time:** 2026-05-14 13:44 CDT  
**Action:** enabled `MAEZ_M1_LIVED_EPISODE_PROMOTION=1` in local
`config/.env`, then restarted `maez.service`.

**Health after restart:**

- `lived_episodes.m1.enabled`: `true`
- `lived_episodes.m1.pending_source_count`: `0`
- `lived_episodes.m1.pending_state`: `pending`
- `lived_episodes.staleness.active_count`: `29`
- `lived_episodes.staleness.newest_created_at`:
  `2026-05-01T09:01:20.349492+00:00`
- `lived_episodes.staleness.newest_age_hours`: approximately `321.7`
- `lived_episodes.staleness.staleness_status`: `alarm`

**Service status after restart:**

- `maez.service`: active/running
- `llama-server.service`: active/running
- `llama-judge.service`: active/running

**Operational caveat:** `systemctl --user restart maez.service` did not complete
the stop path cleanly; `maez.service` remained in `deactivating
(stop-sigterm)` and required `systemctl --user kill --signal=SIGKILL
maez.service` before restart. This is not treated as an M1 logic failure, but
it is a daemon shutdown-path issue that should be queued separately.

## Closure Gate

Initial smoke observation:

- 24 hours after enablement;
- at least 3 natural bonded Telegram conversations;
- at least 1 explicit marker test if the operator is willing;
- at least 1 natural temporal recall probe after a promoted episode exists.

Behavioral closure:

- one full week after enablement;
- operator labels promotion density as `too_sparse`, `about_right`,
  `too_sticky`, or `weirdly_specific`;
- catalog closure waits for the week gate unless the operator explicitly waives
  it after reviewing smoke observation.

