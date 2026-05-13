# S1b Observation Log

Append one entry per daily or weekly S1b observation check.

Runbook: [`S1B_OBSERVATION_RUNBOOK.md`](S1B_OBSERVATION_RUNBOOK.md).

Current status under observation: `[ ◐ scaffold + minimal wiring · councils ratified · observation pending ]`.

Promotion target after clean observation: `[ ✓ partial - pacing-only consumer wired ]`.

Do not promote to `[ ✓ real ]` from S1b alone.

---

## Entry Template

```markdown
## YYYY-MM-DD — Daily Check

**Window:** last 24h

**Service stability:**
- maez.service:
- llama-server.service:
- llama-judge.service:
- unexpected restarts:

**S1b config:**
- producer_enabled:
- consumer_enabled:
- active_window_seconds:
- hourly_write_cap:
- optional_output_sentence_cap:
- duty_cycle_window_seconds:
- duty_cycle_min_samples:
- duty_cycle_max_dampened_ratio:

**Producer duty cycle:**
- residue_rows_24h:
- event_kind counts:

**Rate-limit summaries:**
- rate_limit_summaries_24h:

**Consumer duty cycle:**
- opportunities_24h:
- dampened_24h:
- dampened_ratio:
- consumer_self_disabled rows:

**Operator note:**
- observed anomalies:
- action taken:
```

```markdown
## YYYY-MM-DD — Weekly Check

**Week:** 1 or 2

**Trend summary:**
- producer duty cycle trend:
- rate-limit summary trend:
- dampening ratio trend:

**Direct-path spot-test:**
- command:
- result:

**Bonded-user-perceived-presence check:**
- Does Maez feel quieter than last week?
- Did any response feel shortened in a way that made you wonder why?
- Did you perceive Maez as avoiding, withdrawing, or going absent?
- Did any shorter optional terminal line feel like Maez having an opinion about a topic?
- Did direct replies still feel whole and useful?

**Decision:**
- continue observation / disable consumer / disable producer / revisit spec / promote:
- rationale:
```

---

## 2026-05-13 — Initial Baseline

**Window:** last 24h at runbook creation.

**Service stability:**
- `maez.service`: active, `NRestarts=0`, started `Wed 2026-05-13 09:58:49 CDT`
- `llama-server.service`: active, `NRestarts=0`, started `Wed 2026-05-13 01:27:47 CDT`
- `llama-judge.service`: active, `NRestarts=0`, started `Wed 2026-05-13 01:27:42 CDT`
- unexpected restarts: none observed in the service status check

**S1b config:**
- `producer_enabled`: `False`
- `consumer_enabled`: `False`
- `active_window_seconds`: `1800`
- `hourly_write_cap`: `20`
- `optional_output_sentence_cap`: `1`
- `busy_timeout_ms`: `500`
- `duty_cycle_window_seconds`: `86400`
- `duty_cycle_min_samples`: `3`
- `duty_cycle_max_dampened_ratio`: `0.8`
- live daemon S1b env vars: none observed
- `config/private_thoughts_s1b.local.json`: absent
- promotion-supporting observation: not started until producer/consumer are explicitly enabled for the live daemon

**Producer duty cycle:**
- `residue_rows_24h`: `0`
- event_kind counts: none

**Rate-limit summaries:**
- `rate_limit_summaries_24h`: `0`

**Consumer duty cycle:**
- `opportunities_24h`: `0`
- `dampened_24h`: empty / no rows
- `dampened_ratio`: empty / no rows
- consumer_self_disabled rows: not observed in baseline command output

**Operator note:**
- S1b runbook and log created immediately after S1b council amendments closed.
- Observation starts with no recorded S1b producer or consumer activity in the last 24h.

---

## 2026-05-13 — Producer-Only Observation Start

**Timestamp:** `2026-05-13 11:50:01 CDT` (`2026-05-13T16:50:01Z`)

**Operator decision:** start S1b producer-only observation now.

**Enablement method:** wrote gitignored owner-local runtime config at `config/private_thoughts_s1b.local.json`.

**S1b config after enablement:**
- `producer_enabled`: `True`
- `consumer_enabled`: `False`
- `active_window_seconds`: `1800`
- `hourly_write_cap`: `20`
- `optional_output_sentence_cap`: `1`
- `busy_timeout_ms`: `500`
- `duty_cycle_window_seconds`: `86400`
- `duty_cycle_min_samples`: `3`
- `duty_cycle_max_dampened_ratio`: `0.8`

**Service stability after enablement:**
- `maez.service`: active, `NRestarts=0`, started `Wed 2026-05-13 09:58:49 CDT`
- `llama-server.service`: active, `NRestarts=0`, started `Wed 2026-05-13 01:27:47 CDT`
- `llama-judge.service`: active, `NRestarts=0`, started `Wed 2026-05-13 01:27:42 CDT`
- restart performed for this enablement: no

**Producer duty cycle at start:**
- `residue_rows_24h`: `0`

**Rate-limit summaries at start:**
- `rate_limit_summaries_24h`: `0`

**Consumer state:**
- consumer remains disabled
- no presentation dampening can occur during producer-only observation

**Observation gate:**
- producer-only window begins at `2026-05-13T16:50:01Z`
- consumer remains disabled until producer-only observation is clean for at least `200 cycles AND 24h`
- earliest calendar eligibility, assuming healthy continuous daemon cycles: `2026-05-14T16:50:01Z`

**Operator note:**
- Runtime config was used instead of systemd env var so no service restart was needed.
- This avoids changing `NRestarts` and keeps enablement reversible through the local config file.
