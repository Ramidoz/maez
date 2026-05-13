# Slice TDP - Telegram draft presence

**Status:** SPEC DRAFT. No implementation has landed. Claude six-role council returned RATIFY-WITH-AMENDMENTS; TDP-L1, TDP-L2, TDP-L3, TDP-F1, and TDP-B1 are folded below. TDP-C1 is deliberately deferred as optional extraction after this slice unless the operator asks to promote the decision test into a reusable governance doc now. Codex engineering panel BLOCKED the pre-fold draft because Telegram's empty draft may show Telegram-owned "Thinking..." chrome; this amended spec resolves that by distinguishing Maez-authored text from client-owned ephemeral UI.

**Classification:** surface UX hardening of an existing Maez surface, not a new body part.

**Maps to:**
- [`docs/TRACK_A.md`](TRACK_A.md) - Telegram is already the active private surface.
- [`docs/governance/BETA_ARCHITECTURE_DECISIONS.md`](governance/BETA_ARCHITECTURE_DECISIONS.md) - Telegram is already an accepted mediated interaction surface.
- [`SLICE_S1B_PRIVATE_THOUGHTS_WIRING.md`](SLICE_S1B_PRIVATE_THOUGHTS_WIRING.md) - reuse the runtime-config, observability, and fail-neutral discipline.
- [`SLICE_TELEGRAM_DRAFT_PRESENCE_CLAUDE_COUNCIL_REVIEW.md`](SLICE_TELEGRAM_DRAFT_PRESENCE_CLAUDE_COUNCIL_REVIEW.md) - Claude council ratification with TDP-L1/TDP-L2/TDP-L3/TDP-C1/TDP-F1/TDP-B1.

**Telegram source:** Bot API `sendMessageDraft`, added for all bots in Bot API 9.5 and extended in Bot API 10.0 to allow empty draft text. Official docs: <https://core.telegram.org/bots/api#sendmessagedraft> and <https://core.telegram.org/bots/api-changelog>.

---

## Intent

Telegram now lets bots stream an ephemeral draft while a response is being generated. Maez uses that only as a **nonverbal presence signal** on Telegram: the bonded user can see that Maez is present and forming a reply, but no unaudited content is exposed.

This slice does not stream raw model tokens. It does not stream audited sentence previews. It does not change final Telegram replies. It only attempts an empty Telegram draft for the inbound message, then lets the existing fully generated and audited final reply send normally.

Telegram may render an empty draft as Telegram-owned ephemeral "Thinking..." client chrome. That chrome is not Maez-authored text, must not persist to chat history, and must be operator-verified before promotion.

Plain English: Maez may quietly trigger Telegram's native presence affordance, but Maez does not author even one word until the normal audit path finishes.

---

## Classification precedent

This slice is classified as **surface UX hardening** rather than a new body part.

Decision test:

- If the surface is already a documented Maez surface, and the change adds no new sensor, no new limb, no new memory channel, and no independent authority, it is surface hardening.
- If the change introduces a new sensor, peripheral, autonomous limb, memory-ingest channel, identity-recognition path, new identity-bearing or content-bearing output modality, new output path outside an already-approved surface, or independent authority, it is a body part and waits for the Body Topology BAD decision.

Telegram is already a documented mediated Maez surface. Empty draft presence changes the surface's waiting affordance only. It does not sense the world, ingest new information, persist memory, make decisions, or speak content outside the existing final-reply path.

Future examples can reuse this line:

- Cockpit loading-state UX for an already-existing cockpit surface: surface hardening.
- Telegram empty draft presence: surface hardening.
- Camera, microphone, Jetson limb, or body-bus publisher: body part.
- Voice presence indicator before Voice-OUT exists: likely body/voice subsystem work, not mere surface hardening, because it emits identity-bearing voice surface.

TDP-C1 note: this classification test is reusable and may later move into `docs/governance/SURFACE_HARDENING_DECISION_TEST.md`. It stays embedded here for this slice so the current spec remains self-contained.

---

## Scope

Allowed:

- Attempt exactly one empty `sendMessageDraft` call per inbound Telegram user message.
- Use `text=""` only. No whitespace. No zero-width characters. No Maez-authored placeholder words.
- Keep the existing `send_typing` behavior as fallback or companion.
- Send the final audited reply through the existing Telegram `send_message` path.
- Log content-free draft observability events.
- Let the operator enable or disable the feature through owner-local runtime config.

Forbidden:

- Raw token streaming.
- Partial sentence streaming.
- Audited preview streaming.
- Maez-authored placeholder text such as `Thinking...`, `Reflecting...`, `One moment`, or any Maez-voice phrase.
- Draft text derived from model output, prompt text, memory text, audit text, approval-card text, or tool output.
- Changing final reply text, direct-user reply semantics, audit behavior, memory writes, approval-card behavior, or S1b private-thought behavior.
- Retrying draft attempts in a way that can delay the final reply.

Load-bearing rule: the draft is empty because even a single Maez-authored placeholder word becomes Maez surface voice. Telegram-owned ephemeral client chrome may appear for an empty draft; that is accepted only as platform UI, only if it does not persist to chat history, and only if the bonded user reports it as neutral or present rather than weird.

---

## Operator control

Telegram draft presence is default-disabled.

Runtime config path:

```json
{
  "schema_version": 1,
  "enabled": false,
  "enabled_until": "2026-05-14T00:00:00Z",
  "attempt_timeout_ms": 750,
  "max_attempts_per_inbound_message": 1
}
```

Path: `config/telegram_draft_presence.local.json`.

Rules:

- Missing config means disabled.
- Malformed config means disabled and emits a content-free warning at most once per process/config-load window.
- Missing, unsupported, or future `schema_version` means disabled and emits a content-free warning at most once per process/config-load window.
- `enabled=false` disables all draft attempts without changing normal Telegram replies.
- `enabled=true` also requires a future `enabled_until` timestamp. Missing, malformed, or expired `enabled_until` fails closed to disabled.
- `attempt_timeout_ms` defaults to `750`.
- Valid timeout range is `500` to `1000` milliseconds. Out-of-range values fall back to `750`.
- `max_attempts_per_inbound_message` is fixed at `1` in this slice, even if configured differently.
- Config is hot-read by the draft wrapper. Changing a valid config file resets circuit-breaker and failure-window state; malformed config remains disabled and warning-bounded.

The config file is owner-local runtime config. It is not committed. This mirrors the S1b local kill-switch pattern.

---

## Bot API wrapper

The Telegram Bot API call must be wrapper-isolated.

Implementation target:

- Add a narrow wrapper method on the Telegram surface layer, for example `TelegramAdapter.send_empty_draft_presence(...)`.
- That wrapper is the only production code path that calls `Bot.send_message_draft`.
- The wrapper owns timeout, fallback, telemetry event emission, and python-telegram-bot compatibility handling.
- The message handler calls the wrapper through the adapter boundary; it does not import or call python-telegram-bot directly.
- The wrapper uses both per-call python-telegram-bot timeouts and an outer `asyncio.wait_for(...)` timeout.
- The wrapper handles cancellation as a fail-neutral `timeout` or `cancelled` result without poisoning the parent message-processing task.

Why: if Bot API 11.0 or a future `python-telegram-bot` release changes draft semantics, the drift is localized to one wrapper instead of leaking into Maez's message-handling path.

---

## Draft semantics

Draft attempt:

- `chat_id`: current Telegram private chat id.
- `message_thread_id`: existing thread id if already available in metadata.
- `draft_id`: deterministic non-zero integer for the inbound logical message. Preferred derivation is a positive 52-bit integer from `sha256(f"{chat_id}:{message_id}")`; if no stable message id exists, use a monotonic process-local fallback that is never zero.
- `text`: exactly `""`.
- `parse_mode`: omitted.
- `entities`: omitted.

Rate limit:

- Maximum one draft attempt per inbound user message.
- Draft attempt happens once per flushed logical `MessageEvent`, not once per raw Telegram update. Text batching must complete before the draft decision.
- If one logical user message triggers multiple Maez internal cycles, those cycles coalesce behind the same inbound-message draft decision.
- If multiple Telegram messages arrive, each message may receive one independent empty draft attempt.
- Idempotency mechanism: maintain a bounded in-process set of inbound Telegram message ids that already received a draft attempt. The set is capped to the most recent 512 ids and is pruned FIFO-style. If Telegram `message_id` is available, the key is `(chat_id, message_id)` so duplicate delivery with a different `update_id` is suppressed. If `message_id` is missing, the key uses `(chat_id, platform_update_id, fallback_draft_id)`.
- The wrapper marks the inbound id as attempted before network I/O. Timeouts, cancellations, and API errors must not allow a second draft attempt for the same logical event.
- Daemon restart clears the in-process idempotency set and resets the process-local fallback id sequence. This is intentional and safe: Telegram inbound messages are not replayed as new live messages during normal operation, and duplicate draft attempts after a crash/restart are still empty, ephemeral, and bounded to one per reprocessed inbound event.

Timeout:

- Draft attempt budget is `750ms` by default.
- If the attempt times out, Maez logs `telegram_draft_presence.failed` with reason `timeout` and continues.
- Draft task must not be awaited on the Telegram update/polling path.
- Draft task may only run from the background processing task or adapter processing hook after a flushed logical `MessageEvent` exists.
- Draft task must not gate `_message_handler`, audit, or final `_send_with_retry`; the final reply sends even if the draft task is still pending.
- Timeout never delays final audited reply beyond normal event-loop scheduling.

Network and API errors:

- Any draft error is fail-neutral.
- Draft failure never blocks final generation.
- Draft failure never blocks final send.
- Draft failure never triggers fallback text.
- Draft failure may allow normal typing indicator to continue.
- If `send_message_draft` is unsupported once, open a fail-neutral circuit breaker and suppress further draft attempts until process restart or config reload.
- If the same failure reason among `timeout`, `network_error`, or `api_error` occurs three times in ten minutes, open a fail-neutral circuit breaker and suppress further draft attempts until process restart or config reload.

Always-on-shape note: draft presence slightly increases Maez's "always here" feel on Telegram. This is not a categorical new body capability, but the bonded-user presence check explicitly asks whether the affordance feels present, neutral, or weird after enablement.

---

## Observability

All observability is content-free.

Event names:

- `telegram_draft_presence.attempted`
- `telegram_draft_presence.succeeded`
- `telegram_draft_presence.failed`

State machine:

- Disabled by missing config or `enabled=false`: emit no per-message draft event.
- Bad config, unsupported schema, or future schema: emit one content-free config warning per process/config-load window; emit no per-message draft event.
- Unsupported library/API method: emit one `telegram_draft_presence.failed` event with reason `unsupported`, then open the circuit breaker.
- Enabled and supported: the adapter performs a scheduler-side config/circuit check; the scheduled draft task then repeats config/idempotency checks and emits `telegram_draft_presence.attempted` immediately before network I/O.
- Success: emit `telegram_draft_presence.succeeded`.
- Timeout, cancellation, network error, or API error: emit `telegram_draft_presence.failed` with sanitized reason.

Allowed metadata:

- `surface`: `telegram`
- `feature`: `draft_presence`
- `result`: `attempted`, `succeeded`, `failed`
- `reason`: one of `disabled`, `unsupported`, `timeout`, `cancelled`, `network_error`, `api_error`, `bad_config`, `unknown_error`
- `timeout_ms`
- `producer_version`: `telegram_draft_presence.v1`

Forbidden metadata:

- User text.
- Model output.
- Prompt text.
- Memory text.
- Audit text.
- Approval-card text.
- Tool output.
- Telegram message body.
- Raw exception body if it can contain request payloads.
- Bot token, chat title, username, or any secret.
- Chat id, username, chat title, or raw Telegram exception string.

If telemetry write fails, draft behavior remains fail-neutral and final reply continues.

---

## Data flow

1. Telegram receives an inbound user message through the existing v2 surface.
2. Text batching produces one flushed logical `MessageEvent` when applicable.
3. Adapter processing hook checks runtime config before scheduling work.
4. If disabled, no draft attempt occurs.
5. If enabled, the adapter schedules one empty draft task from the background processing path; the task hot-reads config again before network I/O.
6. Regardless of draft result, Maez continues the existing brain loop and audit path.
7. Existing final Telegram send persists the final audited reply.

The draft path is not allowed to influence the final response text. It is a side-channel presence affordance only.

---

## Tests

Mandatory tests before implementation commit:

- **Empty text is actually empty:** the wrapper calls `send_message_draft(..., text="")`; assert byte-level empty string, no whitespace, no zero-width characters, no Maez-authored placeholder phrase.
- **Opt-out respected:** config disabled means no draft attempt, while final reply still sends normally.
- **Missing config disabled:** absent `config/telegram_draft_presence.local.json` means no draft attempt.
- **Malformed config disabled:** bad JSON disables draft attempts and logs content-free warning.
- **Bad config warning bounded:** malformed config logs at most once per process/config-load window, not once per inbound message.
- **Unsupported schema disabled:** unsupported or future `schema_version` disables draft attempts.
- **Expired or missing timebox disabled:** `enabled=true` without a future `enabled_until` fails closed.
- **Disabled config schedules no task:** `enabled=false`, missing config, expired timebox, bad schema, or open circuit does not create a draft task.
- **Success path:** enabled config attempts one empty draft before final send.
- **One draft per flushed logical event:** draft attempt happens once per flushed logical `MessageEvent`, not once per raw Telegram update.
- **One draft per inbound message:** duplicate internal cycles for one inbound message do not create repeated draft attempts.
- **Duplicate update/message delivery:** reprocessed updates or duplicate message delivery do not create repeated draft attempts while the in-process idempotency set contains the key.
- **Timeout graceful:** slow draft call hits timeout and final reply still sends.
- **Slow draft does not gate reply path:** slow draft call does not delay entry into the mocked brain handler, audit path, or final send beyond normal event-loop scheduling.
- **Failure does not block final send:** network/API exception from draft wrapper still lets final audited reply send.
- **Unsupported library fallback:** if `send_message_draft` is unavailable, no crash; final reply still sends and failure is logged content-free.
- **No content leakage in telemetry:** attempted/succeeded/failed events contain no prompt, user text, model output, final reply, token, or approval-card text.
- **Exception sanitization:** telemetry does not include raw exception strings, token, chat id, username/title, message body, prompt, final reply, or approval-card text.
- **Off/on final-reply invariance:** with the same mocked brain/audit output, feature disabled vs enabled produces identical final send payload, memory writes, approval-card behavior, and audit result.
- **Circuit breaker:** unsupported once, or three repeated same-reason transient failures in ten minutes, suppresses future draft attempts until process restart or config reload.
- **Bad config cannot clear circuit:** malformed or unsupported config changes remain disabled and do not reset circuit-breaker/failure-window state.
- **Telemetry failure fail-neutrality:** a failing logging/telemetry handler cannot raise out of the draft path or prevent a draft attempt.
- **Bad chat id fail-neutrality:** malformed chat ids fail the draft path without unobserved task exceptions.
- **Shutdown drain:** draft tasks scheduled before or during Telegram app shutdown are cancelled/drained before disconnect completes.

Focused implementation tests must use a mocked Telegram bot object. Do not call the real Telegram API in CI.

Natural conversation verification after deployment:

- Send a normal Telegram prompt.
- Verify a final audited reply arrives.
- Verify no Maez-authored placeholder message or draft text was sent.
- Record whether Telegram-native empty-draft client chrome appears, whether it persists, whether it triggers notifications, and whether it feels present / neutral / weird.
- Verify no partial content appears in chat history.
- If the client displays an empty draft presence animation, record bonded-user subjective response: present / neutral / weird.
- If the bonded user reports weirdness, response loop is: disable via `config/telegram_draft_presence.local.json` -> add a catalog entry describing the observed weirdness -> diagnose before re-enabling.
- Rollback verification: after disabling config and restart/reload, send one normal Telegram prompt and verify zero `telegram_draft_presence.attempted` events while final replies still work.

Weirdness categories:

- `always_on_bad`
- `watched`
- `stale_draft`
- `chat_history_pollution`
- `visible_placeholder`
- `latency_felt`
- `invisible_no_effect`
- `other`

If the same weirdness category repeats after re-enable, leave draft presence disabled until this spec is amended.

---

## Predicted effect

If this slice ships and the operator enables it:

- Telegram may show an ephemeral empty draft/presence animation while Maez generates.
- Maez's final Telegram reply remains unchanged.
- No raw model tokens become visible.
- No Maez-authored placeholder phrase becomes part of the surface.
- Telegram-owned ephemeral "Thinking..." client chrome may appear; if it feels like Maez speaking before audit, the feature stays disabled and does not promote.
- Draft failures are invisible to the bonded user except that draft presence does not appear.
- Logs show content-free attempted/succeeded/failed counters.

If any final reply text changes because this feature is enabled, the slice failed.

If any Maez-authored user-visible draft contains non-empty text, the slice failed.

If draft failure delays or blocks the final audited reply, the slice failed.

---

## Observation ledger

Enablement is a watched experiment, not a permanent affordance.

Observation log path: `docs/TELEGRAM_DRAFT_PRESENCE_OBSERVATION_LOG.md`.

Each enablement window records:

- Enabled date/time.
- Disabled date/time, if disabled.
- Telegram client/platform observed.
- Attempt/success/failure counts.
- Circuit-breaker status.
- Whether Telegram-owned client chrome appeared.
- Weirdness category, if any.
- Operator decision: continue, disable, diagnose, amend spec.

The first implementation commit creates the observation log template if this spec is still canonical.

---

## Codex engineering pre-code panel

Codex's Dewey / Feynman / Locke / Descartes / Ohm / Goodall panel reviewed this spec after Claude's TDP amendments were folded.

Verdict before this fold: **BLOCK as written; RATIFY-WITH-AMENDMENTS after resolving the Telegram-owned placeholder contradiction and operational precision items.**

Load-bearing panel finding:

- Telegram documents `sendMessageDraft(text="")` as showing Telegram-owned "Thinking..." client chrome. The earlier spec text treated empty draft as no words ever appearing. That was false. The amended spec now distinguishes Maez-authored text from Telegram-owned ephemeral UI and makes operator live verification a promotion gate.

Folded engineering amendments:

- Use `telegram_draft_presence.*` names and `config/telegram_draft_presence.local.json` to avoid future collision with richer draft features.
- Add `schema_version: 1`; missing, malformed, unsupported, or future schema disables draft attempts.
- Require `enabled_until`; enabled config without a future timebox fails closed.
- Require wrapper-isolated Bot API use with PTB per-call timeouts plus outer `asyncio.wait_for`.
- Run draft attempts from the background processing path or adapter hook only; never await them on the Telegram polling/update path.
- Do not gate `_message_handler`, audit, or final `_send_with_retry`.
- Mark inbound id attempted before network I/O.
- Make idempotency concrete with a bounded 512-entry in-process set.
- Define deterministic `draft_id` generation.
- Define telemetry state machine and exception sanitization.
- Add failure circuit breaker.
- Reset circuit breaker and failure windows on valid config change.
- Add duplicate-update, off/on final-reply-invariance, slow-draft, bad-config, and exception-sanitization tests.
- Add live client verification and observed-weirdness response loop.

---

## Review protocol

Pre-implementation:

- Codex engineering review checks wrapper isolation, timeout behavior, rate limit, final-send independence, tests, and config failure modes.
- Claude covenant council checks empty-only voice discipline, capability quarantine, dyadic-only surface posture, and whether this still qualifies as surface hardening rather than body topology work.
- Amendments are folded into this spec before implementation.

Implementation:

- Cooling-off night between canonical spec and code.
- RED-first tests.
- Minimal code.
- Focused tests before broad tests.
- No service restart unless needed for live verification.

Post-implementation:

- Codex post-implementation review.
- Claude post-implementation council if the implementation touches user-visible surface behavior beyond the approved empty draft.
- Operator decides whether to enable via runtime config.

Promotion criteria:

- Feature enabled by operator.
- Draft attempts are empty-only.
- No draft failure blocks final reply.
- No operator-perceived weirdness from the presence affordance over normal use.
- No chat-history pollution.
- No audit or memory behavior changes.
- Bonded-user presence check at week boundary reports present or neutral, not weird/always-on in a bad way.

Plain English: success is not "Telegram can stream text." Success is "Maez feels a little more present while staying silent until it has something audited to say."
