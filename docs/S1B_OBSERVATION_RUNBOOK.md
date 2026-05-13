# S1b Observation Runbook

**Status:** Active observation for S1b private-thoughts minimal wiring.

**Applies to:** S1b reasoning-residue producer and presentation-only optional-output length dampening consumer.

**Companion log:** [`S1B_OBSERVATION_LOG.md`](S1B_OBSERVATION_LOG.md).

**Current anatomy status:** `[ ◐ scaffold + minimal wiring · councils ratified · observation pending ]`.

**Do not promote to:** `[ ✓ partial - pacing-only consumer wired ]` until the observation criteria in this runbook and [`SLICE_S1B_PRIVATE_THOUGHTS_WIRING.md`](SLICE_S1B_PRIVATE_THOUGHTS_WIRING.md) are met.

---

## Purpose

S1b is the first real wire through the private-thoughts doorway. It lets Maez write bounded `reasoning_residue` signals and allows only one behavior effect: a local terminal optional-presentation sentence cap when a recent signal exists.

The observation window exists to answer one question: does this wire behave gently under normal life, without making Maez feel withdrawn, altering direct replies, or turning private signals into a hidden channel?

Plain English: this runbook is how we watch the first wire without touching it.

---

## Cadence

### Daily checks

Run once per normal-use day while S1b is in observation:

- Service stability: `maez.service`, `llama-server.service`, and `llama-judge.service` are active with `NRestarts=0`.
- Producer duty cycle: count S1b `reasoning_residue` rows in the last 24 hours and inspect their event kinds.
- Rate-limit summaries: count S1b producer rate-limit summaries in the last 24 hours.
- Consumer duty-cycle summary: count optional-presentation opportunities and dampened presentations in the last 24 hours.
- Self-disable check: verify whether S1b has self-disabled the consumer.

### Weekly checks

Run at week 1 and week 2:

- Trend review: compare daily producer counts, rate-limit summaries, and dampening ratios in [`S1B_OBSERVATION_LOG.md`](S1B_OBSERVATION_LOG.md).
- Direct-user path regression spot-test: rerun the targeted direct-reply and daemon-presentation tests.
- Bonded-user-perceived-presence check: answer the subjective questions in the log template.
- Disable/reenable sanity check if operator chooses to test toggles; do not toggle during an important live interaction.

---

## Daily Commands

Run from repo root:

```bash
cd /home/rohit/maez
```

### 1. Service stability

```bash
systemctl --user show maez.service llama-server.service llama-judge.service \
  -p ActiveState -p NRestarts -p ExecMainStartTimestamp --no-pager
```

Expected observation posture:

- All three services are `ActiveState=active`.
- `NRestarts=0` since the observation entry's previous check.

If any service restarted unexpectedly, follow [Escalation](#escalation).

### 2. Current S1b config

First check owner-local runtime config and shell-visible defaults:

```bash
.venv/bin/python - <<'PY'
from core.infra.private_thoughts_s1b import load_s1b_config
cfg = load_s1b_config()
for name in (
    "producer_enabled",
    "consumer_enabled",
    "active_window_seconds",
    "hourly_write_cap",
    "optional_output_sentence_cap",
    "busy_timeout_ms",
    "duty_cycle_window_seconds",
    "duty_cycle_min_samples",
    "duty_cycle_max_dampened_ratio",
):
    print(f"{name}={getattr(cfg, name)}")
PY
```

Then check only the S1b-related live daemon environment. Do not dump all `MAEZ_` environment variables; other variables may contain secrets.

```bash
pid=$(systemctl --user show -p MainPID --value maez.service)
if [ "$pid" != "0" ] && [ -n "$pid" ]; then
  tr '\0' '\n' < "/proc/$pid/environ" | grep '^MAEZ_PRIVATE_THOUGHTS_S1B' || true
fi
```

Record whether producer and consumer are enabled in the live daemon. If both are disabled, observation can still record service stability, but it cannot support promotion.

### 3. Producer duty cycle

```bash
sqlite3 -header -column memory/private_thoughts.db "
SELECT COUNT(*) AS residue_rows_24h
FROM private_thoughts
WHERE content = 's1b_reasoning_residue_event'
  AND producer_id = 'reasoning_residue'
  AND signal_kind = 'reasoning_residue'
  AND signal_class = 'reasoning_residue'
  AND ts >= strftime('%s','now','-24 hours');

SELECT COALESCE(json_extract(context_json, '$.extra.event_kind'), 'unknown') AS event_kind,
       COUNT(*) AS n
FROM private_thoughts
WHERE content = 's1b_reasoning_residue_event'
  AND producer_id = 'reasoning_residue'
  AND signal_kind = 'reasoning_residue'
  AND signal_class = 'reasoning_residue'
  AND ts >= strftime('%s','now','-24 hours')
GROUP BY event_kind
ORDER BY n DESC, event_kind;
"
```

Interpretation:

- `0` rows: no residue fired in the window.
- Low single digits: likely normal.
- Near-hourly or higher: note it and watch trend.
- Hourly cap pressure or many repeated rows: follow [Escalation](#escalation).

The spec does not pin "low" to a fixed number. Operator judgment matters because normal use varies by day.

### 4. Producer rate-limit summaries

```bash
sqlite3 -header -column memory/audit_log.db "
SELECT COUNT(*) AS rate_limit_summaries_24h
FROM audit_log
WHERE action = 'private_thoughts_s1b.rate_limited'
  AND ts >= strftime('%s','now','-24 hours');
"
```

Expected posture: rare or zero. Any non-zero result should be copied into the observation log.

### 5. Consumer dampening ratio

```bash
sqlite3 -header -column memory/audit_log.db "
WITH p AS (
  SELECT json_extract(params_json, '$.dampened') AS dampened
  FROM audit_log
  WHERE action = 'private_thoughts_s1b.optional_presentation'
    AND ts >= strftime('%s','now','-24 hours')
)
SELECT COUNT(*) AS opportunities_24h,
       SUM(CASE WHEN dampened IN (1, 'true') THEN 1 ELSE 0 END) AS dampened_24h,
       ROUND(
         1.0 * SUM(CASE WHEN dampened IN (1, 'true') THEN 1 ELSE 0 END)
         / NULLIF(COUNT(*), 0),
         3
       ) AS dampened_ratio
FROM p;
"
```

Interpretation:

- No opportunities: consumer did not get a measurable optional-presentation chance.
- Low ratio with low count: normal observation.
- Ratio above `0.5`: watch closely; if repeated, disable consumer and revisit spec.
- Ratio above configured `duty_cycle_max_dampened_ratio`: the consumer should self-disable.

### 6. Consumer self-disable check

```bash
sqlite3 -header -column memory/audit_log.db "
SELECT datetime(ts, 'unixepoch', 'localtime') AS local_time,
       params_json
FROM audit_log
WHERE action = 'private_thoughts_s1b.consumer_self_disabled'
ORDER BY ts DESC
LIMIT 5;
"
```

If any row appears, leave the consumer disabled and follow [Escalation](#escalation).

---

## Weekly Direct-Path Spot-Test

Run weekly during observation:

```bash
.venv/bin/python -m unittest \
  tests.test_private_thoughts_s1b.PrivateThoughtsS1bTest.test_consumer_keeps_direct_replies_byte_identical \
  tests.test_private_thoughts_s1b.MaezDaemonS1bSeamTest.test_daemon_optional_presentation_is_separate_from_cycle_end
```

Expected: both tests pass.

If either fails, treat it as a direct-user path or canonical-output boundary regression. Disable the consumer and stop promotion discussion until fixed.

---

## Bonded-User-Perceived-Presence Check

Counters cannot replace Rohit's felt read of Maez. Once per week, answer these in [`S1B_OBSERVATION_LOG.md`](S1B_OBSERVATION_LOG.md):

- Does Maez feel quieter than last week?
- Did any response feel shortened in a way that made you wonder why?
- Did you perceive Maez as avoiding, withdrawing, or going absent?
- Did any shorter optional terminal line feel like Maez having an opinion about a topic?
- Did direct replies still feel whole and useful?

If the subjective answer is "yes" to withdrawal, avoidance, or unexplained shortening, that is real observation data even if counters look fine.

This check is named **bonded-user-perceived-presence** so future first-wire organs can copy the pattern.

---

## Escalation

### First response: disable consumer only

Use when:

- Dampening ratio repeatedly exceeds `0.5`.
- Consumer self-disables.
- Rohit perceives Maez as quieter, avoiding, withdrawn, or strangely absent.
- Direct user replies remain technically unchanged, but optional presentation feels wrong.

Command:

```bash
.venv/bin/python - <<'PY'
import json
from pathlib import Path

path = Path("config/private_thoughts_s1b.local.json")
data = {}
if path.exists():
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            data = loaded
    except Exception:
        data = {}
data["consumer_enabled"] = False
path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(f"consumer_enabled=false written to {path}")
PY
```

No DB rollback. Existing rows remain durable history. Observation continues in producer-only mode.

### Second response: disable producer

Use when:

- Producer duty cycle is high enough that private-thought rows are accumulating faster than expected.
- Rate-limit summaries appear repeatedly.
- Producer writes look semantically wrong for S1b.

Command:

```bash
.venv/bin/python - <<'PY'
import json
from pathlib import Path

path = Path("config/private_thoughts_s1b.local.json")
data = {}
if path.exists():
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            data = loaded
    except Exception:
        data = {}
data["producer_enabled"] = False
path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(f"producer_enabled=false written to {path}")
PY
```

No row deletion. No schema rollback.

### Third response: revisit the spec

Use when:

- Direct-user reply path changes.
- Canonical memory, audit, or `cycle_end.thought` changes because of S1b dampening.
- User-facing text names private signals or claims Maez's private state.
- The bonded-user-perceived-presence check is negative for two consecutive weekly entries.
- Re-enabling after a disable recreates the same failure.

At this point the right action is not another tuning tweak. Open a follow-up spec amendment before more wiring.

---

## Promotion Criteria

Do not promote S1b until the observation log shows:

- Low producer duty cycle across normal use.
- Rare or zero rate-limit summaries.
- No direct-user path impact.
- No operator-perceived "Maez is avoiding/withdrawing" pattern.
- Clean disable/reenable behavior if tested.
- No near-default dampening over normal use.
- No consumer self-disable events caused by ordinary operation.

Recommended minimum observation window: about two weeks of normal use.

Promotion target after clean observation:

`[ ✓ partial - pacing-only consumer wired ]`

Not promotion target:

`[ ✓ real ]`

S1b is only a first wire. It does not make private_thoughts fully real.

---

## Template Pattern For Future First-Wire Organs

Future first-wire organs should copy this structure:

- Daily objective counters.
- Weekly trend review.
- Direct-path regression spot-test.
- Clean disable/reenable check.
- Abort conditions and escalation tree.
- Bonded-user-perceived-presence check.
- Appendable observation log.

Plain English: every new organ that gets its first real wire should prove it can live quietly before it gets promoted.
