# Telegram Draft Presence Observation Log

Append one entry per enablement window.

This log tracks the user-visible Telegram client behavior that unit tests cannot prove: whether Telegram-owned empty-draft chrome appears, whether it persists, whether it triggers notifications, and whether the bonded user experiences it as present, neutral, or weird.

## Promotion Criteria

Do not promote Telegram draft presence beyond experimental surface hardening until an enablement window shows:

- Draft attempts remain empty-only from Maez's side.
- Final replies remain unchanged.
- No chat-history pollution.
- No draft failure blocks final replies.
- Rollback verification succeeds after disablement.
- Bonded-user presence check reports `present` or `neutral`, not weird/always-on in a bad way.
- Day-1, week-2, and month-2 rechecks are either complete or deliberately waived by the operator.

## Weirdness Categories

- `always_on_bad`
- `watched`
- `stale_draft`
- `chat_history_pollution`
- `visible_placeholder`
- `latency_felt`
- `invisible_no_effect`
- `other`

If the same weirdness category repeats after re-enable, leave draft presence disabled until the spec is amended.

---

## Entry Template

**Window:** YYYY-MM-DDTHH:MM:SSZ -> YYYY-MM-DDTHH:MM:SSZ or active

**Config:**

```json
{
  "schema_version": 1,
  "enabled": true,
  "enabled_until": "YYYY-MM-DDTHH:MM:SSZ",
  "attempt_timeout_ms": 750,
  "max_attempts_per_inbound_message": 1
}
```

**Telegram client/platform observed:**

- Client:
- Platform:
- Version if known:
- Client auto-update date if known:
- Notification settings relevant to Telegram drafts:
- Cross-client check performed: yes/no

**Counters:**

- `telegram_draft_presence.attempted`:
- `telegram_draft_presence.succeeded`:
- `telegram_draft_presence.failed`:
- Circuit breaker opened: yes/no

**Client behavior:**

- Telegram-owned empty-draft chrome appeared: yes/no/unknown
- Persisted to chat history: yes/no
- Notification triggered: yes/no/unknown
- Stale-draft duration if observed:
- Partial Maez-authored content appeared: yes/no

**Operator presence check:** present / neutral / weird

**Weirdness category if any:** none / category

**Prior weirdness windows:** none / links

**Repeat category:** yes/no

**Spec amendment id required before re-enable:** none / id

**Scheduled rechecks:**

- Day 1:
- Week 2:
- Month 2:
- After Telegram client update:

**Rollback verification if disabled:**

- Disabled via config: yes/no
- Restart/reload performed: yes/no
- Probe sent after disable: yes/no
- Zero `telegram_draft_presence.attempted` after disable: yes/no
- Final reply still works: yes/no

**Decision:** continue / disable / diagnose / amend spec

**Notes:**

---

## Entry 2026-05-13 — first live enablement window

**Window:** 2026-05-13T22:53:52Z -> 2026-05-14T00:53:52Z

**Config:**

```json
{
  "schema_version": 1,
  "enabled": true,
  "enabled_until": "2026-05-14T00:53:52Z",
  "attempt_timeout_ms": 750,
  "max_attempts_per_inbound_message": 1
}
```

**Telegram client/platform observed:**

- Client: Telegram desktop/web in Chrome + Telegram mobile
- Platform: desktop Chrome + mobile
- Version if known: unknown
- Client auto-update date if known: unknown
- Notification settings relevant to Telegram drafts: unknown
- Cross-client check performed: no

**Counters:**

- `telegram_draft_presence.attempted`: 2 (`2026-05-13 17:59:36 CDT`, `2026-05-13 18:01:51 CDT`)
- `telegram_draft_presence.succeeded`: 2 (`2026-05-13 17:59:36 CDT`, `2026-05-13 18:01:52 CDT`)
- `telegram_draft_presence.failed`: 0 observed
- Circuit breaker opened: no

**Client behavior:**

- Telegram-owned empty-draft chrome appeared: yes; desktop Chrome showed `typing` at top, mobile showed a large blank space below the conversation
- Persisted to chat history: no persistent Maez-authored draft text observed in screenshots
- Notification triggered: unknown
- Stale-draft duration if observed: visible during/around response window; exact duration not measured
- Partial Maez-authored content appeared: no

**Operator presence check:** weird

**Weirdness category if any:** `visible_placeholder` / `stale_draft`

**Prior weirdness windows:** none

**Repeat category:** no

**Spec amendment id required before re-enable:** TDP-FOLLOWUP-1

**Scheduled rechecks:**

- Day 1: not scheduled for this two-hour test window
- Week 2: not scheduled for this two-hour test window
- Month 2: not scheduled for this two-hour test window
- After Telegram client update: pending future enablement window

**Rollback verification if disabled:**

- Disabled via config: yes, after first visual report
- Restart/reload performed: yes, `maez.service` restarted to load TDP implementation code; old process required systemd SIGKILL after stop timeout
- Probe sent after disable: no
- Zero `telegram_draft_presence.attempted` after disable: not checked
- Final reply still works: yes; Telegram reply logged as `"Testing received. I'm here."`

**Decision:** disable / diagnose

**Notes:** First live TDP enablement window. Short timebox chosen so the operator can inspect Telegram-owned empty-draft chrome without leaving a perception-affecting surface UX feature enabled indefinitely. API/log-level verification passed: empty draft attempts succeeded before final audited Telegram replies. Client-visible behavior failed the subjective check: desktop showed typing chrome at top; mobile showed a large blank space below the conversation. Feature disabled pending diagnosis. Separately, the repeated "I don't have a grounded answer for that part" phrase was traced to `core/safety/self_claim_audit.py` rewrite behavior, not TDP.
