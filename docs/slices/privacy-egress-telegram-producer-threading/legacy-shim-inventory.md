# Telegram Producer Threading Legacy-Shim Inventory

Date: 2026-05-23
Base: c8d5549 (`feat(egress): add Telegram chokepoint shadow gate`)
Purpose: mechanical inventory only. This is not a spec, not an implementation
plan, and not a commit-ready artifact.

## Scope

This inventory banks the hot-context trace for the next Telegram
producer-threading slice. It lists the Telegram paths that now pass through the
chokepoint but still use legacy `unclassified` provenance or generic
producer-side wrappers.

The next spec should read the canonical chokepoint spec fresh from disk before
using this file. This file is only the grounded migration target list.

## Trace Commands Used

Read-only trace surfaces:

```bash
rg -n "legacy_text_envelope\(|allow_legacy_shadow_send|allow_shadow_send|owner_text_envelope\(|public_text_envelope\(" skills core daemon tests -g '*.py'
rg -n "_egress_call|_egress_query_call|_telegram_egress_envelope|_reply_text|_bot_send_message|_public_reply_text|_public_owner_alert|_public_chat_action" skills/surface/telegram_adapter.py skills/telegram_public.py skills/telegram_voice.py
rg -n "\.send_message\(|\.reply_text\(|\.send_chat_action\(|\.edit_message_text\(|\.answer\(|set_message_reaction\(" skills daemon core -g '*.py'
```

False-positive checked:

```bash
rg -n "telegram|Telegram|send_message|Application" skills/screen_perception.py
```

The only `skills/screen_perception.py` match is the word `Application` in
screen-observation text. It is not a Telegram producer.

## Current Chokepoint State

The direct Telegram library sends are closed behind the chokepoint. The
remaining work is not "find direct bot sends"; it is producer-side at-birth
provenance threading.

Current direct factories:

| File | Line | Factory | Current origin class | Notes |
| --- | ---: | --- | --- | --- |
| `skills/surface/telegram_adapter.py` | 3486 | `legacy_text_envelope(...)` | `unclassified` | Fan-out wrapper for owner-private surface-v2 sends. |
| `skills/telegram_voice.py` | 52 | `legacy_text_envelope(...)` | `unclassified` | Legacy/voice reply wrapper. |
| `skills/telegram_voice.py` | 69 | `legacy_text_envelope(...)` | `unclassified` | Legacy/voice bot-send wrapper used by sync `send_message`. |
| `skills/telegram_voice.py` | 86 | `legacy_text_envelope(...)` | `unclassified` | Legacy/voice chat-action wrapper. |
| `skills/telegram_public.py` | 53 | `public_text_envelope(...)` | `maez_authored_public_third_party_transport` | Already precise for public replies/start messages. Keep as baseline. |
| `skills/telegram_public.py` | 68 | `legacy_text_envelope(...)` | `unclassified` | Public module owner alert, but actual token route is owner-private. |
| `skills/telegram_public.py` | 85 | `legacy_text_envelope(...)` | `unclassified` | Public-bot typing/chat action. Content-free transport control. |

`core/egress/telegram_egress.py::legacy_text_envelope(...)` defaults
`allow_shadow_send=True`, so legacy shims can still send in shadow. Under
future enforcement, `unclassified` blocks.

## Migration Target Summary

High-level counts from the trace:

| Bucket | Count | Migration shape |
| --- | ---: | --- |
| Surface-v2 owner-private adapter helper methods | 8 primary methods plus callback/reaction/draft helpers | Replace adapter-level legacy wrapper with method-specific precise or multi-span envelopes. |
| Legacy/voice owner-private wrapper families | 3 wrappers, many call sites | Either promote wrappers to precise by call family or push provenance to their callers. |
| Public-bot routes | 1 precise public reply wrapper, 2 legacy wrappers | Keep public replies precise; migrate owner alert and chat action separately. |
| Daemon indirect producers | 4 `self.telegram.send_message(...)` sites | Producer-side provenance should be born in daemon before it reaches `TelegramVoice.send_message`. |
| Action-engine indirect producers | 13 `self.telegram.send_message(...)` sites | Producer-side provenance should be born in action notifications before voice abstraction. |
| Dream-state indirect producers | 2 `self.telegram.send_message(...)` sites | Producer-side provenance should be born in dream proposal text before voice abstraction. |
| Transport-control paths | callback answers, typing, reactions, draft presence | Content-free or static-bounded envelopes; avoid pretending these are Maez-authored prose. |

## Direct Wrapper Inventory

### `skills/surface/telegram_adapter.py`

Current common wrapper:

- `TelegramAdapter._telegram_egress_envelope(...)` at `skills/surface/telegram_adapter.py:3476`
- Calls `legacy_text_envelope(...)` at `skills/surface/telegram_adapter.py:3486`
- Route: `bot_route="owner_private"`, `audience_class="bonded_owner"`
- Current origin: `unclassified`
- Fan-out helpers: `_egress_call(...)` at `skills/surface/telegram_adapter.py:3536` and `_egress_query_call(...)` at `skills/surface/telegram_adapter.py:3570`

Primary call families:

| Lines | Function | Message kind | Content source | Recommended at-birth target |
| --- | --- | --- | --- | --- |
| 1280, 1293 | `send(...)` | `text` | Surface-v2 outgoing owner chat text, chunked and Markdown/plain fallbacked. | Usually `maez_authored_owner_third_party_transport`; support multi-span if caller supplies owner/private/tool snippets. |
| 1391, 1402, 1421, 1443 | `edit_message(...)` | `edit_text` | Edits prior owner-private Telegram message. | Same provenance as original text; next spec should decide whether edit calls carry an `original_request_id` or fresh source ref. |
| 1484 | `send_update_prompt(...)` | `text` with inline keyboard | Gateway update prompt plus static Yes/No buttons. | Multi-span: static transport UI as owner transport/system-bounded; dynamic `prompt/default` should be explicitly classified at producer site. |
| 1550 | `send_exec_approval(...)` | `text` with inline keyboard | Command approval card; includes command preview, reason, button labels, callback data classes. | Multi-span: static UI, command/reason as action-card context, interactive markup labels as first-class content. |
| 1610 | `send_model_picker(...)` | `text` with inline keyboard | Model picker UI; provider/model labels and callback classes. | Multi-span: static UI plus provider/model metadata; likely non-private/system-bounded unless labels can include private data. |
| 1683-1854 | `_handle_model_picker_callback(...)` | `callback_answer`, `edit_text` | Picker status, provider/model pages, result text from selection callback. | Content-free callback answers when no text; static/system-bounded for status text; callback result text needs source-specific provenance. |
| 1880-1940 | `_handle_callback_query(...)` | `callback_answer`, `edit_text` | Approval/update callback acknowledgements and resolution edits. | Static/system-bounded for acks; approval `label/user_display` needs explicit provenance, not generic unclassified. |
| 1997, 2007 | `send_voice(...)` | `voice` / `audio` | Local audio file plus optional caption. | Media envelope with caption provenance; audio file path/ref metadata must stay non-reconstructive. |
| 2044 | `send_image_file(...)` | `photo` | Local image file plus optional caption. | Media envelope with caption provenance; file path/ref non-reconstructive. |
| 2083 | `send_document(...)` | `document` | Local file plus optional caption/display name. | Media envelope; file name and caption require provenance. |
| 2115 | `send_video(...)` | `video` | Local video file plus optional caption. | Media envelope with caption provenance. |
| 2151 | `send_image(...)` | `photo` | URL sent directly to Telegram plus optional caption. | URL/media ref envelope; Maez-side URL download fallback remains disabled. |
| 2185 | `send_animation(...)` | `animation` | Animation URL plus optional caption. | URL/media ref envelope; fallback to `send_image(...)` inherits URL discipline. |
| 2210, 2217 | `send_typing(...)` | `typing` | Content-free chat action. | Content-free transport-control envelope, not Maez-authored prose. |
| 3313 | `_set_reaction(...)` | `reaction` | Reaction transport control. | Content-free or bounded static reaction envelope. |
| 3660 | `send_empty_draft_presence(...)` | `draft_presence` | Empty draft-presence transport signal. | Content-free transport-control envelope. |

Risk flags:

- The adapter wrapper uses generic `source_ref` values such as
  `telegram_adapter:send_message`. Producer threading should make source refs
  more specific where the caller semantics matter.
- Interactive markup is already extracted into `TelegramInteractiveMarkup`;
  the next slice should preserve that typed path rather than hiding labels in
  metadata.
- Media sends need a clear split between content text/caption provenance and
  non-reconstructive media references.

### `skills/telegram_voice.py`

Current wrappers:

| Wrapper | Line | Route/audience | Current origin | Fan-out |
| --- | ---: | --- | --- | --- |
| `_reply_text(update, text, **kwargs)` | 50 | `voice_owner_private` / `bonded_owner` | `unclassified` | Async command/reply handlers. |
| `_bot_send_message(bot, **kwargs)` | 68 | `voice_owner_private` / `bonded_owner` | `unclassified` | Sync `send_message`, card sends, reasoning replies. |
| `_bot_send_chat_action(bot, **kwargs)` | 85 | `voice_owner_private` / `bonded_owner` | `unclassified` | Typing indicator. |

Important fan-out categories:

| Lines | Functions | Content source | Recommended at-birth target |
| --- | --- | --- | --- |
| 817 | `_send_card_message(...)` | Approval card text from `skills/approval_card.py`. | Multi-span card envelope; static card labels + card action/params/results should be classified at card render time. |
| 913, 1095, 1254 | `_try_card_reply_intent(...)` | Self-mod dialog and card pipeline replies. | `maez_authored_owner_third_party_transport` for Maez dialog voice; action/status data may need `system_bounded_query` or typed action-card context. |
| 2017-2294 | Dream/proposal intent handlers | Owner command acks, proposal lookup/list/apply/reject text. | Mix of static command acks, proposal metadata, and Maez-authored summaries; should be multi-span or per-handler precise. |
| 2489-2586 | Offer binding and web-search intents | Status/error/reply text. | Static/status text plus tool/search output if present; avoid one blanket class. |
| 2615, 2625, 3198, 3717, 3740 | Main owner chat path | Audited Maez reply, split parts, fallback/error reply, typing. | Final audited Maez reply should be `maez_authored_owner_third_party_transport`; typing is content-free; error text static/system-bounded. |
| 3920-4922 | Command handlers (`/status`, `/approve`, `/dreams`, `/show_edit`, builder mode, cognition analysis, etc.) | Status reports, action results, proposal lists, errors. | Handler-specific multi-span: static shell text, action outputs, proposal text, memory/cognition summaries where applicable. |
| 5109 | `TelegramVoice.send_message(text)` | Sync owner-private send path used by daemon/action/dream indirect producers. | Do not make this wrapper globally precise unless callers pass provenance; otherwise it launders indirect producers. |

Risk flags:

- `TelegramVoice.send_message(text)` is the biggest laundering risk. It is a
  sync convenience wrapper used by daemon, action engine, and dream state. The
  next slice should either add a provenance-bearing overload or require callers
  to pass a `TelegramEgressEnvelope`.
- Many `_reply_text(...)` calls are static command responses; others contain
  model output, action output, memory/proposal summaries, or user-derived
  fragments. A single owner-transport class at the voice wrapper would be too
  coarse.

### `skills/telegram_public.py`

Current wrappers:

| Wrapper | Line | Route/audience | Current origin | Migration status |
| --- | ---: | --- | --- | --- |
| `_public_reply_text(update, text, **kwargs)` | 51 | `public_stranger` / `public_stranger` | `maez_authored_public_third_party_transport` | Already precise for public Maez replies. |
| `_public_owner_alert(bot, **kwargs)` | 67 | `owner_private` / `bonded_owner` | `unclassified` | Needs explicit owner-alert provenance. |
| `_public_chat_action(bot, **kwargs)` | 84 | `public_stranger` / `public_stranger` | `unclassified` | Content-free typing action. |

Call sites:

| Line | Function | Content source | Recommended at-birth target |
| ---: | --- | --- | --- |
| 346 | `_alert_rohit(...)` | Manipulation alert to owner; includes public user's profile fields and message excerpt. | Multi-span owner alert: static alert text plus `third_party_private_context` for public user's message/profile, redaction/minimization policy to be decided in spec. |
| 409 | `_handle_message(...)` | Public typing action. | Content-free transport-control envelope. |
| 472 | `_handle_message(...)` | Audited public-bot LLM reply. | Already `maez_authored_public_third_party_transport` via `_public_reply_text(...)`. |
| 495, 497 | `_handle_start(...)` | Public greeting/returning-user text. | Already `maez_authored_public_third_party_transport`; returning greeting contains public user's first name, so next spec should decide whether that is public-route-safe or a mixed span. |

Risk flags:

- `_alert_rohit(...)` still constructs an owner-private `Bot` inside the public
  module. The send is chokepoint-routed, but the authority crossing remains
  a future cleanup candidate. Producer threading should classify the alert by
  actual token/audience, not by module path.
- Public replies are precise today, but the public bot's own per-user memory
  is a distinct store. The next spec should not accidentally treat public-user
  memory as owner memory; it may need an explicit stance using the existing
  vocabulary before inventing anything new.

## Indirect Producer Inventory

These sites do not call Telegram library methods directly. They call
`self.telegram.send_message(...)`, which currently reaches
`TelegramVoice.send_message(...)` and then `_bot_send_message(...)` with
legacy `unclassified` provenance.

### `daemon/maez_daemon.py`

| Line | Function | Content source | Recommended at-birth target |
| ---: | --- | --- | --- |
| 2073 | `_curiosity_checkin(...)` | Asks owner to classify newly-seen public users; includes display names/notes from user accounts. | Multi-span owner-bound system prompt: static Maez prompt plus third-party/public-user profile fields. |
| 2177 | `_check_proactive_opinion(...)` | Audited unprompted Maez opinion generated from raw memory window. | Final audited text likely `maez_authored_owner_third_party_transport`; source metadata should preserve memory-window derivation for audit/diagnostic, not necessarily for outbound content. |
| 4147 | `_send_morning_briefing(...)` | Audited morning briefing from local signals. | Multi-span or Maez-authored owner transport with evidence metadata; avoid exposing raw signal provenance as Telegram content unless rendered. |
| 5757 | `_loop(...)` follow-up delivery | Follow-up result for an action the owner asked about; includes status and action output/error. | Static follow-up shell plus action result span; action output may need non-private/system-bounded vs private distinction. |

Risk flags:

- These are proactive owner-bound sends. Producer threading should not make
  them public-route capable by accident.
- Several paths already audit text before send; the threading slice should
  preserve that audited-text boundary.

### `core/actions/action_engine.py`

All call sites are owner-bound action notifications through
`self.telegram.send_message(...)`.

| Lines | Functions | Content source | Recommended at-birth target |
| --- | --- | --- | --- |
| 1890, 1927, 1953 | Tier 2 queued actions (`kill_process`, `restart_service`, `free_disk_space`) | Queued-action notice with action params/reason. | Multi-span action-card/notification envelope; static label plus action params/reason. |
| 2001, 2028, 2058, 2085, 2110, 2134, 2157, 2177, 2198 | Tier 3 approval requests | Approval request text with package/path/file/rule/cmd/reason and action id. | Multi-span approval envelope; command/path/config/change fields must not be blindly Maez-authored. |
| 2305 | `execute_tier2_pending(...)` | Expired-action notice. | Static owner-bound action status plus action id. |

Risk flags:

- Action notifications can contain shell commands, file paths, config snippets,
  service names, and execution output. A blanket
  `maez_authored_owner_third_party_transport` would erase why the content is
  safe only for the bonded owner.
- This slice should coordinate with the separate
  `action_engine_external_fetch` migration but not merge scopes: these rows are
  Telegram transport notifications, not outbound HTTP fetches.

### `core/evolution/dream_state.py`

| Line | Function | Content source | Recommended at-birth target |
| ---: | --- | --- | --- |
| 343 | `run_dream_cycle(...)` | Dream insight proposal notice plus `/apply_dream` / `/reject_dream` hints. | Owner-bound Maez proposal text; may need special handling if insight was derived from memory/soul notes. |
| 641 | `store_training_proposal(...)` | Training-run proposal notice plus approval hints. | Owner-bound Maez proposal text plus training rationale metadata. |

Risk flags:

- Dream/proposal text can be derived from Maez memory and soul notes. The next
  spec should decide whether final audited proposal text is treated as
  Maez-authored owner transport, or whether source derivation remains explicit
  in spans.

### Indirect Non-Sending Producers

These modules render or manage content that later reaches a Telegram wrapper.
They need producer-side provenance at their render boundary, not necessarily a
Telegram API change.

| File | Current role | Next-slice note |
| --- | --- | --- |
| `skills/approval_card.py` | Formats approval cards, reminders, and resolution notices; production renderer is wired through Telegram voice helpers. | Best birth point for card-specific spans: static labels, action summaries, params, execution output/error. |
| `skills/self_mod_dialog.py` | Builds self-modification dialog turns and acknowledgements surfaced through card reply path. | Best birth point for dialog reply voice spans. |
| `skills/followup_queue.py` | Stores delayed follow-up tasks; daemon emits final follow-up messages. | Follow-up queue probably stores task/action references; daemon is current render/send boundary. |
| `skills/dev_notifier.py` | Developer notification helper named by surface trace. | Needs a fresh grep in spec session; no direct Telegram send found in this pass. |
| `core/evolution/will_i.py` | Describes refusal surfaces for `telegram_send`, no direct Telegram send in this pass. | Treat as policy/input to producer rendering, not a Telegram producer unless future grep finds a send. |

## Open Design Questions For Next Session

These are intentionally not answered here:

1. Should `TelegramVoice.send_message(...)` gain a provenance-bearing overload,
   or should every indirect caller construct a `TelegramEgressEnvelope` before
   calling?
2. For final audited Maez replies derived from private memory, is the outbound
   span just `maez_authored_owner_third_party_transport`, or should the spans
   preserve memory derivation even when the rendered text is Maez's final voice?
3. How should action-card fields be typed without adding new closed-vocabulary
   classes?
4. Should public-bot per-user memory stay inside
   `maez_authored_public_third_party_transport` after local synthesis, or
   should it be represented as `third_party_private_context` before synthesis?
5. Do media captions and media refs need separate envelope constructors for
   owner/public routes, or can the current text-envelope constructors grow
   caption/media provenance safely?

## Immediate Spec Inputs

The producer-threading spec should start from these grounded targets:

- Replace or augment `skills/surface/telegram_adapter.py::_telegram_egress_envelope(...)`.
- Replace or augment `skills/telegram_voice.py::_reply_text(...)`,
  `_bot_send_message(...)`, and `TelegramVoice.send_message(...)`.
- Replace `skills/telegram_public.py::_public_owner_alert(...)` and
  `_public_chat_action(...)`; keep `_public_reply_text(...)` as a precise
  baseline but review returning-user greeting name handling.
- Add tests that fail if any legacy `unclassified` shim remains on
  enforcement-critical content-bearing Telegram paths.
- Add tests that direct/indirect producers preserve the existing chokepoint
  invariants: no raw diagnostics, no direct Telegram sends outside the
  chokepoint, and no public-recipient owner-context leakage.
