# Recall Floor Task 0 — Data-Derived Base-Distance Floor

**Date:** 2026-06-22
**Plan:** `docs/superpowers/plans/2026-06-22-coherence-core-pair.md`
**Verdict:** GO — initial floor `0.7800`, derived from the live `living_recall_candidate` base-distance distribution.

## Source

Task 0 mined the existing living-recall telemetry in `/home/rohit/maez/logs/maez.log`.

The log seam is already present in `memory/memory_manager.py`: `living_recall_candidate id=... base_distance=... recency_factor=... effective_distance=...`.

## Distribution

From `1872` parsed candidate rows:

| percentile | base_distance |
| --- | ---: |
| min | 0.2734 |
| p05 | 0.4576 |
| p10 | 0.4916 |
| p25 | 0.5764 |
| median | 0.6742 |
| p60 | 0.7051 |
| p70 | 0.7445 |
| p75 | 0.7649 |
| p80 | 0.7830 |
| p85 | 0.8123 |
| p90 | 0.8241 |
| p95 | 0.8910 |
| max | 0.9829 |

Candidate drop rates for possible floors:

| floor | would drop | drop pct |
| ---: | ---: | ---: |
| 0.750 | 526 | 28.1% |
| 0.765 | 468 | 25.0% |
| 0.780 | 396 | 21.2% |
| 0.800 | 322 | 17.2% |
| 0.825 | 186 | 9.9% |
| 0.850 | 164 | 8.8% |
| 0.890 | 100 | 5.3% |

## Example Bands

Content-light examples only: id prefix, base distance, recency factor, effective distance.

Strong/kept band:

| id prefix | base | recency | effective |
| --- | ---: | ---: | ---: |
| `375bcb25-f869-44` | 0.2915 | 0.6329 | 0.4606 |
| `37f80013-3e19-43` | 0.3693 | 0.6102 | 0.6053 |
| `882d5b90-e29f-4d` | 0.3758 | 0.5917 | 0.6352 |
| `ca3221fb-02f7-4b` | 0.3848 | 0.5823 | 0.6610 |
| `189a5539-71db-43` | 0.3848 | 0.5919 | 0.6502 |

Near-boundary kept band:

| id prefix | base | recency | effective |
| --- | ---: | ---: | ---: |
| `daily-2026-04-29` | 0.7688 | 0.6702 | 1.1472 |
| `daily-2026-06-16` | 0.7696 | 0.9699 | 0.7935 |
| `daily-2026-06-03` | 0.7431 | 0.8775 | 0.8468 |
| `f04453de-3cb7-4e` | 0.7062 | 0.7615 | 0.9274 |
| `ce3fc132-e6fd-4c` | 0.7202 | 0.7957 | 0.9050 |

High-distance would-drop band:

| id prefix | base | recency | effective |
| --- | ---: | ---: | ---: |
| `daily-2026-06-19` | 0.7863 | 0.9926 | 0.7922 |
| `daily-2026-06-18` | 0.8217 | 0.9850 | 0.8342 |
| `daily-2026-05-05` | 0.8598 | 0.7019 | 1.2250 |
| `daily-2026-06-17` | 0.8486 | 0.9774 | 0.8682 |
| `941244d3-e6ba-42` | 0.7803 | 0.6676 | 1.1688 |

Tail would-drop band:

| id prefix | base | recency | effective |
| --- | ---: | ---: | ---: |
| `daily-2026-05-28` | 0.8910 | 0.8379 | 1.0634 |
| `daily-2026-05-01` | 0.9188 | 0.6806 | 1.3500 |
| `daily-2026-05-27` | 0.9371 | 0.8315 | 1.1270 |
| `daily-2026-06-04` | 0.9605 | 0.8843 | 1.0862 |
| `daily-2026-04-27` | 0.9731 | 0.6612 | 1.4718 |

## Floor Choice

Initial floor: `_RECALL_RELEVANCE_FLOOR_DEFAULT = 0.7800`.

Reasoning:

- `0.7800` is the p80 elbow of the observed distribution.
- It catches the known wound band where weak diary-flood rows were observed (`~0.78-0.93`).
- It still keeps the lower and near-boundary recall bands below p80.
- It drops about one fifth of observed candidates, making it strong enough to expose the diary flood in shadow without immediately claiming this is the final learned bar.

This is a data-derived **initial** bar for shadow and owner witness. Online adaptation remains collect-only in this slice; it must not auto-actuate from this proof alone.

## STOP Check

The distribution is not a perfect two-cluster split, but it has a clear high-distance tail aligned with the diary-flood band. Because the slice is shadow-first and default-off, the plan can proceed: shadow receipts must still prove that genuine recall is not over-dropped before `MAEZ_RECALL_FLOOR_ENABLED` is used live.

**Task 0 status:** GO.
