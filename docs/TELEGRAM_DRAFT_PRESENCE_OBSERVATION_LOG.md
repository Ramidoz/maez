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
  "attempt_timeout_ms": 750,
  "max_attempts_per_inbound_message": 1
}
```

**Telegram client/platform observed:**

- Client:
- Platform:
- Version if known:

**Counters:**

- `telegram_draft_presence.attempted`:
- `telegram_draft_presence.succeeded`:
- `telegram_draft_presence.failed`:
- Circuit breaker opened: yes/no

**Client behavior:**

- Telegram-owned empty-draft chrome appeared: yes/no/unknown
- Persisted to chat history: yes/no
- Notification triggered: yes/no/unknown
- Partial Maez-authored content appeared: yes/no

**Operator presence check:** present / neutral / weird

**Weirdness category if any:** none / category

**Rollback verification if disabled:**

- Disabled via config: yes/no
- Restart/reload performed: yes/no
- Probe sent after disable: yes/no
- Zero `telegram_draft_presence.attempted` after disable: yes/no
- Final reply still works: yes/no

**Decision:** continue / disable / diagnose / amend spec

**Notes:**

