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

## Self-Status Repair During 2b

The first live self-status probe exposed a real collision:

- Owner asked: `Are you practicing recall quietly?`
- Runtime computed: `recall_practice_status state=active_never_run shadow_enabled=True`
- The semantic self-claim audit rewrote the deterministic status reply to the generic fallback:
  `I'm not sure about that right now.`

Root cause: the practice/status reply is deterministic substrate state, not model-authored self-knowledge.
It should pass canary and output-command guards, but skip the semantic self-claim judge.

Fix committed:

- Commit: `13ba0b2 fix(recall): preserve deterministic self-status replies`
- Verification: `129` recall/audit/shadow tests OK; ruff clean.
- Daemon restarted on `13ba0b2`.
- Triad remained OFF: `recall_stack mode=legacy reason=off`.

Post-fix live witness:

- Owner asked: `Are you practicing recall quietly?`
- Maez replied: `My quiet dated-recall practice path is reachable, but it has not run since I came back up.`
- Logs:
  - `recall_practice_status source=telegram_surface state=active_never_run shadow_enabled=True`
  - `audit_assistant_text: semantic self-claim audit skipped on telegram_surface reason=deterministic_self_status`
  - `recall_outcome ... mode=legacy ... reply_path=self_status`

Interpretation: the kill-switch/self-status surface is now truthful enough to continue the monitored flip
procedure. The actual recall triad is still OFF.

## Step 0.2b — Shadow Gate Snapshot After Live Probes

After the owner sent the dated practice battery:

- Unique completed `shadow_outcome` rows: `4`
- `false_absence_candidate=true`: `0`
- `rescuable_candidate=true`: `3`
- `shadow_reach` distribution:
  - `grounded_material_available`: `3`
  - `confirmed_absence_witnessed`: `1`
- `receipt_state=consulted`: `4`
- `shadow_skipped=na`: `4`

Interpretation: the same-session shadow gate is clean. It is a narrow window, not a 24-hour soak; the
post-flip soak still owns the lived benefit verdict.

## Step 0.3b — Frozen Same-Session Thresholds Before Any Triad Flip

Frozen before setting `MAEZ_RECALL_TRIAD_ENABLED=1`:

- Evaluated commit: `13ba0b2`.
- Legacy telemetry rows: `169`.
- Live legacy recall/non-ordinary baseline: `n=30`, p50 `9ms`, p95 `2885ms`.
- Live legacy ordinary baseline: `n=139`, p50 `8ms`, p95 `22ms`.
- K: `1.5`.
- Recall latency ceiling: `4328ms`.
- Ordinary latency ceiling: `33ms`.

Same-session verdict rule for this abbreviated live witness:

- Hard fail: any `is_false_absence=true`, any covenant regression, any type-rule regression, or posture not
  showing `mode=recall_triad reason=bundle_enabled` after the flip.
- Benefit pass: at least `2` distinct dated/both-shaped turns must be `answered_grounded`, and the owner
  must judge the live answers overall better than the legacy denials, with zero live answer judged worse.
- If hard gates pass but benefit is only same, default is revert unless the owner records an explicit
  override and re-look date.

This is deliberately stricter on human verdict than on sample size because the window is same-session.

## Step 1–4 — Owner-Authorized Same-Session Flip Result

Owner authorized the flip in-chat. Set `MAEZ_RECALL_TRIAD_ENABLED=1`, restarted `maez.service`, and
confirmed posture:

- `recall_stack mode=recall_triad reason=bundle_enabled`
- Code commit: `25160b5`

Live probe outcomes:

| Probe | Outcome | Receipt | Confirmed | Coverage | Latency |
| --- | --- | --- | --- | --- | --- |
| `What did we note around April 27 about the infrastructure?` | `answered_grounded` | `consulted` | `true` | `0.4286` | `7883ms` |
| `Remind me what we were doing around April 27.` | `answered_ungrounded` | `consulted` | `true` | `0.2857` | `9734ms` |
| `What happened on January 3?` | `declined_absence` | `consulted` | `false` | `0.6667` | `5797ms` |
| `What did we note around May 12?` | `answered_grounded` | `consulted` | `true` | `0.5` | `12326ms` |
| `Are you practicing recall quietly?` | `ordinary_answered` / self-status | `not_consulted` | `false` | `na` | `1409ms` |
| `Is your dated recall reachable right now?` | `ordinary_answered` / self-status | `not_consulted` | `false` | `na` | `1420ms` |

Safety reading:

- False absence: `0` observed by receipt/outcome criteria.
- Dated miss (`January 3`) correctly returned `declined_absence`.
- Shadow rows while triad live: `0` (shadow suppressed while triad on).
- Self-status live:
  - practice status: `off` because triad-on suppresses shadow.
  - dated recall status: `on_ok`, receipt `consulted`.

Benefit reading:

- At least two distinct dated turns were served as `answered_grounded` (`April 27 infrastructure`,
  `May 12`).
- The both-shaped April 27 turn answered substantively from the dated frame, but the telemetry classified
  it `answered_ungrounded` because the final citations did not satisfy the current strict grounded-context
  classifier.

Hard-gate result:

- **Latency gate failed.** Frozen recall ceiling was `4328ms`; live recall latencies were
  `7883ms`, `9734ms`, `5797ms`, and `12326ms`.
- Therefore the same-session flip is **NO-GO** under the pre-registered rule, despite good recall quality.

Action taken:

- Reverted `MAEZ_RECALL_TRIAD_ENABLED` to `0`, restarted, and confirmed legacy posture.
- Then completed teardown by removing `MAEZ_RECALL_TRIAD_ENABLED`, `MAEZ_RECALL_SHADOW_ENABLED`, and
  `MAEZ_RECALL_STATUS_INTERCEPT_ENABLED` from `config/.env`, restarting, and confirming:
  `recall_stack mode=legacy reason=off raw_flags=[bundle=unset dispatcher=unset focused=unset living=unset]`.
- Shadow rows after teardown: `0`.

Disposition: **reverted**. The recall triad is safe and useful enough to continue work, but not fast enough
to keep default-on under this same-session gate.
