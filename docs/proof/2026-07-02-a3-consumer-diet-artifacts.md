# A3 Consumer Diet Artifacts

Date: 2026-07-02

Scope: dream, self-analysis, and proactive-opinion raw-recency consumers.

Owner decision carried from the A3 spec: these consumers get the durable-only diet. They feed on what the world did plus what Maez's own salience machinery marked, not on every passing cycle glance. This is an intentional behavior change, not parity preservation.

## Dream

Old: `DreamState.run_dream_cycle()` read `memory.recent_raw(n=40)`, which included all cycle rows, including quiet 30-second self-glances.

New: because untriggered glances no longer enter raw memory under `MAEZ_METABOLIC_MEMORY=1`, the same `recent_raw(n=40)` call sees durable material only: events, salience-rescued thoughts, and quiet-day stubs.

Witness: `tests.test_metabolic_consumers.DurableOnlyConsumerDietTests.test_dream_skips_when_durable_recent_raw_below_threshold` shows that when fewer than 10 durable rows are available, dream skips and does not call the LLM.

Expected consequence: dreams fire less during empty stretches. That is the named behavior change: nothing lived means nothing to dream from.

## Self-Analysis

Old: `skills.self_analysis.analyze()` read `memory.raw.get(limit=200)` and counted topics across all recent raw rows, including clock-driven cycle glances.

New: under A3, raw contains durable material plus stubs, so self-analysis counts the durable rows it is handed.

Witness: `tests.test_metabolic_consumers.DurableOnlyConsumerDietTests.test_self_analysis_counts_the_durable_rows_it_receives` proves the analyzer computes over the supplied durable rows without requiring legacy glance rows.

Expected consequence: self-analysis becomes less dominated by machine-vital repetition because empty cycle glances stop entering the analyzed feed.

## Proactive Opinion

Old: `MaezDaemon._check_proactive_opinion()` read the last 20 raw rows and returned early when fewer than 10 rows were present.

New: under A3, that same window is durable-only. If fewer than 10 durable rows exist, proactive opinion skips.

Witness: `tests.test_metabolic_consumers.DurableOnlyConsumerDietTests.test_proactive_opinion_skips_when_durable_window_below_threshold` proves the skip path does not build an evidence envelope or send a notice when the durable window is below threshold.

Expected consequence: proactive opinion fires less during empty stretches and does not manufacture something worth saying from clock-driven self-glances.

## Boundary

No consumer receives a new content-kind filter here. The change comes from A3's upstream durability vote: deterministic events plus Maez's salience signals decide what reaches raw. These consumers then keep using their existing raw-recency interfaces.
