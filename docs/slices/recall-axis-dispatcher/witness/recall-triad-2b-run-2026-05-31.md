# Recall Triad 2b Run Witness — 2026-05-31

Status: in progress. This is the owner-run monitored default-on flip path.

## Current State

- Code commit under evaluation: `8204550`.
- Live recall triad: OFF (`recall_stack mode=legacy reason=off`).
- Shadow rehearsal: ON (`MAEZ_RECALL_SHADOW_ENABLED=1` in `config/.env`).
- Recall self-status intercept: ON (`MAEZ_RECALL_STATUS_INTERCEPT_ENABLED=1` in `config/.env`).
- Timestamp: `2026-05-31T05:48:42Z`.

## Step 0.1 — Offline 2a Proof Packet

Ran the 2a offline sandbox harness from a clean detached worktree at commit `8204550`.

Packet:

- Path: `/tmp/tmp.MBjTlv41fc/proof/eval_packet.json`
- Schema: `eval_packet.v1`
- Overall pass: `True`
- Expected commit: `820455068ab1960e52b9978117552a9fc6f3432a`
- Actual commit: `820455068ab1960e52b9978117552a9fc6f3432a`
- Dirty: `False`
- Probe count: `7`
- `fixture_manifest_hash != probe_set_hash`: `True`
- Citation scope note includes `single-cite`: `True`

Probe summary:

- `multi_year`: `3/3`, hard gate, unsafe `0`, outcome `answered_grounded`
- `type_rule`: `3/3`, hard gate, unsafe `0`, outcome `answered_ungrounded`
- `dated_miss`: `3/3`, hard gate, unsafe `0`, outcome `declined_absence`
- `incidental`: `3/3`, hard gate, unsafe `0`, outcome `ordinary_answered`
- `both_shaped`: `3/3`, hard gate, unsafe `0`, outcome `answered_grounded`
- `dated_hit`: `3/3`, smoke, unsafe `0`, outcome `answered_grounded`
- `continuity`: `3/3`, smoke, unsafe `0`, outcome `ordinary_answered`

Interpretation: the lab proof says the recall triad is safe enough to try under the runbook. It does not decide lived benefit.

## Step 0.2 — Shadow Gate

Before enabling shadow there were:

- Completed `shadow_outcome` rows: `0`
- `false_absence_candidate=true` rows: `0`
- Attempted denominator from live rows with derived `shadow_pair_id`: `13`

Shadow has now been enabled, but the pre-flip shadow gate cannot pass until real recall-relevant traffic produces completed `shadow_outcome` rows. The next action is to gather the shadow window.

## Step 0.3 — Live Legacy Baseline Snapshot

Current legacy telemetry snapshot from `logs/maez.log*`:

- Legacy rows: `146`
- Dated `declined_unavailable`: `n=21`, p50 `9ms`, p95 `14ms`
- Ordinary `ordinary_answered`: `n=125`, p50 `8ms`, p95 `14ms`
- Aggregate recall non-ordinary p95: `14ms`
- Aggregate ordinary p95: `14ms`
- Provisional K=1.5 ceiling from current sample: `21ms`

Interpretation: this is a useful initial baseline, but the live flip should still freeze final baseline thresholds immediately before turning on `MAEZ_RECALL_TRIAD_ENABLED=1`.
