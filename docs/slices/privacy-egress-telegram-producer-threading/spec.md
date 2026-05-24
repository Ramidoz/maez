# Privacy / Egress Telegram Producer Threading -- Spec

**Status:** CANONICAL v1 (2026-05-24). Docs-only target for later implementation.
**Base code:** c8d5549 (`feat(egress): add Telegram chokepoint shadow gate`)
**Class:** Covenant-shaped / boundary-hardening / producer provenance slice
**Depends on:** Telegram chokepoint spec v1, live Telegram chokepoint shadow
gate, canonical Privacy / Egress Gate vocabulary, and the legacy-shim inventory
at `docs/slices/privacy-egress-telegram-producer-threading/legacy-shim-inventory.md`.
**Review state:** Lanes cleared: Codex engineering panel RATIFY-WITH-AMENDMENTS
(7 folds pass-1 + 2 folds pass-2 applied) and Claude council pass-5
RATIFY-CLEAR with behavioral-trace verification across five council passes.

## Purpose

The Telegram chokepoint is live, but many producers still enter it through
legacy `unclassified` shims. That is correct for the chokepoint slice: first
close the road, then classify the traffic. This slice does the second part for
Telegram.

Goal: move Telegram from "every send passes through the booth, but legacy
content is still unclassified" to "content-bearing Telegram sends are tagged at
birth by the producer that still knows what the text is."

Plainly: the toll booth is built. This slice labels the cars before they reach
the booth.

## Scope

In scope:

- Producer-side provenance threading for Telegram-bound content-bearing paths.
- Removal of production `legacy_text_envelope(...)` use outside the chokepoint
  module and tests.
- Precise owner-private and public-stranger text envelopes at producer birth.
- Content-free envelopes for typing, callback acknowledgement, reaction, and
  draft-presence transport controls.
- Multi-span envelopes for action cards, approval prompts, model pickers,
  public-owner alerts, daemon proactive messages, action-engine notifications,
  and dream/proposal notices.
- Media envelope typing for captions and media references.
- RED tests that fail on current `c8d5549` because production shims still carry
  `unclassified`.
- Inventory status update from chokepoint-only shadow to producer-threaded
  shadow if implementation chooses shadow posture.

Out of scope:

- Global egress enforcement flip.
- `action_engine_external_fetch` migration. Telegram notifications emitted by
  the action engine are in scope; its external HTTP fetch route is not.
- New closed-vocabulary origin classes.
- Public-bot memory redesign.
- Telegram bot consolidation.
- Replacing Telegram as a product surface.
- S7.3 guarded execution changes.
- Changes to cloud-as-tool, fast-backend retirement, or the watchdog.
- Deeper cleanup of `telegram_public.py` constructing an owner-private `Bot`;
  the send must be correctly classified, but eliminating the cross-module token
  construction is a later producer-architecture cleanup.

Deferred cleanup that must stay tracked:

- `telegram_public.py:_alert_rohit(...)` currently constructs an owner-private
  `Bot(token=self.rohit_token)` inside the public-bot module. This slice keeps
  the send correctly routed/classified by token identity, but a future
  producer-architecture cleanup should route owner alerts through the
  owner-private adapter/voice surface instead of constructing that Bot in the
  public module.

## Grounding Artifacts

Fresh-read artifacts:

- `docs/slices/privacy-egress-telegram-chokepoint/spec.md`
- `docs/slices/privacy-egress-telegram-producer-threading/legacy-shim-inventory.md`
- `core/egress/telegram_egress.py`
- `core/egress/gate.py`
- `core/egress/provenance.py`
- `skills/surface/telegram_adapter.py`
- `skills/telegram_voice.py`
- `skills/telegram_public.py`
- `daemon/maez_daemon.py`
- `core/actions/action_engine.py`
- `core/evolution/dream_state.py`
- `skills/approval_card.py`
- `skills/self_mod_dialog.py`

Governance anchors:

- Decision 2 / Decision 4: third-party consent and relational-vs-personological
  knowledge.
- Decision 5: Telegram is a practical beta surface, not a trusted local
  boundary.
- Decision 11: third-party privacy law and operator responsibility are why
  egress governance exists.
- ADR 0030: promote biography; do not widen recall.
- ADR 0032: external information is provenance first, never biography by
  default.
- ADR 0039: operator/user role boundaries must stay explicit on Telegram
  approval paths.

## Current State

The chokepoint implementation closed direct Telegram library sends behind
`core.egress.telegram_egress`. Diagnostics are non-reconstructive and the live
shadow gate records allow/block decisions correctly.

Remaining production legacy factories at `c8d5549`:

| File | Line | Current factory | Current origin |
| --- | ---: | --- | --- |
| `skills/surface/telegram_adapter.py` | 3486 | `legacy_text_envelope(...)` | `unclassified` |
| `skills/telegram_voice.py` | 52 | `legacy_text_envelope(...)` | `unclassified` |
| `skills/telegram_voice.py` | 69 | `legacy_text_envelope(...)` | `unclassified` |
| `skills/telegram_voice.py` | 86 | `legacy_text_envelope(...)` | `unclassified` |
| `skills/telegram_public.py` | 68 | `legacy_text_envelope(...)` | `unclassified` |
| `skills/telegram_public.py` | 85 | `legacy_text_envelope(...)` | `unclassified` |

Already precise:

| File | Line | Current factory | Current origin |
| --- | ---: | --- | --- |
| `skills/telegram_public.py` | 53 | `public_text_envelope(...)` | `maez_authored_public_third_party_transport` |

The direct-send bypass inventory remains part of the law. This slice does not
relax it.

## Design Choice

Rejected option: promote each legacy wrapper wholesale to an owner/public
origin class. That would make focused tests green while laundering hard cases:
action output, command previews, third-party public-user messages, model picker
labels, memory-derived summaries, and media captions would all become one
blanket "Maez-authored" blob.

Chosen option: hybrid producer-born provenance.

- Simple final Maez replies use `owner_text_envelope(...)` or
  `public_text_envelope(...)`.
- Transport controls use explicit content-free envelopes.
- Mixed messages use multi-span envelopes created at the producer or renderer
  that still knows the text's source.
- Raw-string convenience wrappers are retained only if tests prove no
  production path can use them without passing provenance, or if the wrapper
  itself requires an explicit provenance argument and refuses unreviewed raw
  text.

This is slower than wrapper promotion and less invasive than redesigning every
Telegram producer. It is the smallest honest step that makes future enforcement
possible.

## Provenance Rules

No new origin classes in this slice.

Use existing origins:

| Source | Origin class |
| --- | --- |
| Final audited Maez reply to bonded owner | `maez_authored_owner_third_party_transport` |
| Final audited Maez reply to public/stranger recipient | `maez_authored_public_third_party_transport` |
| Static reviewed Telegram UI copy inside owner-bound messages | `maez_authored_owner_third_party_transport` unless a more specific allowed class applies |
| Static reviewed Telegram UI copy inside public messages | `maez_authored_public_third_party_transport` unless a more specific allowed class applies |
| Owner text echoed back to owner | `owner_message_context` |
| Memory/lived-store fragments rendered directly to owner | `memory` / `lived_store` |
| Public user message/profile rendered in an owner alert | `third_party_private_context` with reviewed minimization/redaction |
| Public user message/profile rendered back to the same public user | Prefer final synthesized `maez_authored_public_third_party_transport`; direct quotation or profile echo is `third_party_private_context` and must not silently bypass public policy |
| Local system/action status that is not private biography | `system_bounded_query` or `tool_result_public`, depending on source |
| Cloud model output | `model_output`; not expected in Telegram v1 unless future reviewed quoting path adds it |
| Soul/private-thought/credential/crisis raw material | Reserved-denied raw class; block |
| Unknown mixed text | `unclassified`; not enforcement-ready |

The key distinction: final local Maez wording is Maez-authored. Directly
rendered evidence, owner text, third-party text, command output, memory
fragments, or system facts stay separately spanned.

## Envelope Helpers

Implementation may choose exact helper names, but the contract is:

- `owner_text_envelope(...)` handles simple Maez-authored owner-bound text.
- `public_text_envelope(...)` handles simple Maez-authored public-bound text.
- Add content-free route/audience envelope helpers for typing, callback
  acknowledgements, reactions, and draft presence.
- Add owner/public multi-span helpers for mixed content.
- Add media helpers where caption, media reference, and metadata are separated.
- Do not hide user-visible text, button labels, callback data, captions, file
  names, or URLs in opaque metadata.

Suggested conceptual helpers:

```python
owner_multispan_envelope(...)
public_multispan_envelope(...)
owner_transport_control_envelope(...)
public_transport_control_envelope(...)
owner_media_envelope(...)
public_media_envelope(...)
```

These names are not mandatory. The behavior is.

## Legacy Wrapper Retirement

Production `legacy_text_envelope(...)` calls outside
`core/egress/telegram_egress.py` must be removed or proven unreachable from
production content-bearing paths.

Allowed after this slice:

- `legacy_text_envelope(...)` definition in `core/egress/telegram_egress.py`.
- Focused tests proving legacy behavior still blocks under enforcement.
- Explicit test fakes.

Not allowed after this slice:

- `skills/surface/telegram_adapter.py` calling `legacy_text_envelope(...)` for
  content-bearing owner-private sends.
- `skills/telegram_voice.py` calling `legacy_text_envelope(...)` for replies,
  bot sends, or typing controls.
- `skills/telegram_public.py` calling `legacy_text_envelope(...)` for owner
  alerts or public typing controls.
- Any production `allow_legacy_shadow_send=True` path, including content-free
  transport controls (typing, callback acknowledgements, reactions, draft
  presence).

If a truly unknown content path remains, it must fail closed under shadow
diagnostics rather than being silently allowed as legacy.

## Surface-v2 Owner Adapter

Target: `skills/surface/telegram_adapter.py`

Current problem: `_telegram_egress_envelope(...)` uses one owner-private
legacy wrapper for many message kinds.

Required migration:

- Replace `_telegram_egress_envelope(...)` with a provenance-aware builder or
  family of builders.
- Simple `send(...)` text should preserve provenance from caller if available;
  otherwise classify final Maez-authored owner text as
  `maez_authored_owner_third_party_transport` only when the call site is a
  reviewed Maez-voice surface.
- `TelegramAdapter.send(..., content: str)` is a compatibility surface, not a
  provenance authority. It must not blanket-promote arbitrary raw strings to
  owner Maez-authored transport.
- This anti-laundering requirement covers both the direct
  `TelegramAdapter.send(...)` implementation and inherited
  `BasePlatformAdapter` fallback paths that eventually call `self.send(...)`.
  Inherited content/caption-bearing surfaces such as `send_image(...)`,
  `send_animation(...)`, `send_voice(...)`, `send_video(...)`,
  `send_document(...)`, and `send_image_file(...)` must be unreachable for
  Telegram, overridden, or migrated to provenance-bearing media/error helpers.
  Inherited content-free surfaces such as typing must use content-free
  envelopes rather than legacy raw-text fallbacks.
- The implementation must pick an explicit anti-laundering mechanism for raw
  adapter sends: a provenance-bearing content type, an explicit reviewed-source
  argument, or static production-call-site proof that every raw-string caller is
  reviewed and mapped to a precise helper before transport.
- If implementation chooses static production-call-site proof for adapter raw
  sends, that proof must include inherited `BasePlatformAdapter.self.send(...)`
  fallback paths or prove they are unreachable for Telegram.
- An unreviewed raw string that reaches `TelegramAdapter.send(...)` must stay
  `unclassified`/blocked or fail the static proof; it must not become owner
  Maez-authored text by default.
- `edit_message(...)` must preserve or explicitly restate the provenance of
  edited text. A fresh source ref is acceptable; pretending edit text is
  unclassified is not.
- `send_update_prompt(...)`, `send_exec_approval(...)`, and
  `send_model_picker(...)` must represent interactive markup as typed content,
  not metadata.
- Callback answers and no-arg acknowledgements must use content-free or static
  bounded envelopes.
- Reactions, typing, and draft presence must use content-free envelopes.
- Media sends must keep captions provenance-bearing and media refs
  non-reconstructive.
- Direct URL download fallback remains disabled.

## Legacy / Voice Telegram Stack

Target: `skills/telegram_voice.py`

Current problem: `_reply_text(...)`, `_bot_send_message(...)`, and
`TelegramVoice.send_message(text)` all collapse different sources into
legacy `unclassified`.

Required migration:

- Add a provenance-bearing route for sync sends. This can be an overload, a new
  method such as `send_envelope(...)`, or a typed helper. The implementation
  must be usable by daemon, action engine, and dream state.
- Keep raw `send_message(text)` only as a compatibility surface if production
  tests prove content-bearing call sites no longer use it, or if it constructs
  a precise envelope from an explicit provenance argument.
- Static production-call-site proof is the primary invariant for this raw sync
  surface. The AST inventory must flag production
  `self.telegram.send_message(...)` in `daemon/maez_daemon.py`,
  `core/actions/action_engine.py`, and `core/evolution/dream_state.py` until
  those sites pass envelopes or typed helper objects instead of raw strings.
- The AST proof must scan production roots for raw sync-send patterns, not only
  the currently listed line numbers. It must catch direct attribute calls,
  alias-then-call patterns such as `tg = self.telegram; tg.send_message(...)`,
  and single-level dynamic calls such as
  `getattr(self.telegram, "send_message")(...)` and
  `getattr(self, "telegram").send_message(...)`.
- Runtime guard on the retained sync surface is defense-in-depth: a
  content-bearing raw string must not silently become owner/public transport
  without explicit provenance. This mirrors the fast-backend retirement and
  Telegram chokepoint pattern: static proof is primary, runtime refusal catches
  slips.
- Arbitrary reflection (`exec`, `eval`, `compile`), `__getattribute__`
  overrides, and runtime class swaps are out of v1 static scope. They remain
  runtime-guard territory only.
- Main owner chat replies after audit should be born as
  `maez_authored_owner_third_party_transport`.
- Terminal/error fallback messages should be static/system-bounded or
  Maez-authored depending on source; exception text must not be dumped into an
  owner-transport class without review.
- Command handlers require per-family classification rather than one wrapper
  class. Status text, action outputs, proposal summaries, memory/cognition
  summaries, and owner command echoes are not the same source.
- Typing indicators must be content-free.

The spec intentionally does not demand every command handler be beautifully
refactored. It does demand that the producer side creates an honest envelope
before the Telegram road.

## Public Telegram Stack

Target: `skills/telegram_public.py`

Already precise:

- `_public_reply_text(...)` uses `public_text_envelope(...)`.

Required migration:

- `_public_owner_alert(...)` must become a multi-span owner-bound alert:
  static alert text plus public-user profile/message material as
  `third_party_private_context`, with reviewed minimization/redaction.
- `_public_chat_action(...)` must become a content-free public transport
  control.
- Public returning-user greetings remain public Maez-authored text if they are
  final local phrasing. Direct raw profile echo should be spanned separately.
- Route/audience must continue to follow actual token identity, not module
  path.
- `_alert_rohit(...)` owner alerts are owner-private because they use
  `MAEZ_TELEGRAM_TOKEN` / `self.rohit_token`; the route must be
  `owner_private` and the audience `bonded_owner` even though the producer lives
  in the public module.

The cross-module owner-private `Bot` construction in `_alert_rohit(...)` is a
known future cleanup candidate. This slice only requires the send to be
properly classified and routed.

## Daemon Producers

Target: `daemon/maez_daemon.py`

Current indirect sends through `self.telegram.send_message(...)`:

| Line | Function | Required classification |
| ---: | --- | --- |
| 2073 | `_curiosity_checkin(...)` | Static owner prompt plus public-user profile fields as third-party/private or reviewed public-user context. |
| 2177 | `_check_proactive_opinion(...)` | Audited final Maez text to owner; retain source/evidence metadata separately. |
| 4147 | `_send_morning_briefing(...)` | Audited final briefing to owner; source signals must not be laundered if directly rendered. |
| 5757 | `_loop(...)` follow-up delivery | Static follow-up shell plus action result/output span. |

Required migration:

- Stop passing raw strings into `TelegramVoice.send_message(...)` for these
  paths.
- Construct envelopes at the daemon producer site or through named helpers
  that encode the producer's semantics.
- Preserve existing audit-before-send boundaries.
- Keep diagnostics out of Maez's own cognition context by default.

## Action Engine Notifications

Target: `core/actions/action_engine.py`

Current indirect sends through `self.telegram.send_message(...)`:

- Tier 2 queued notifications: `kill_process`, `restart_service`,
  `free_disk_space`.
- Tier 3 approval requests: `install_package`, `execute_script`,
  `modify_config`, `register_new_skill`, `restart_critical_service`,
  `modify_firewall`, `system_reboot`, `delete_file`, `sudo_command`.
- Expired-action notification in `execute_tier2_pending(...)`.

Required migration:

- Action-engine Telegram notifications must construct owner-bound multi-span
  envelopes or call a renderer that does so.
- Static card text, action id, action params, command strings, file paths,
  service names, firewall rules, config snippets, output, and error fragments
  must not all become one Maez-authored span.
- This is Telegram transport provenance only. Do not migrate or claim closure
  for `action_engine_external_fetch`.

## Dream State / Proposal Producers

Target: `core/evolution/dream_state.py`

Current sends:

- `run_dream_cycle(...)` proposal notice.
- `store_training_proposal(...)` training proposal notice.

Required migration:

- Construct owner-bound envelopes before sending proposal notices.
- Keep command hints static/bounded.
- Decide in implementation review whether final audited proposal wording is
  Maez-authored owner transport or whether memory/soul-note derivation remains
  explicit in spans.
- Do not widen recall or mutate memory policy while doing this. This is an
  outbound transport slice.

## Renderer Producers

Some modules do not call Telegram directly but are the best birth point for
provenance.

Targets:

- `skills/approval_card.py`
- `skills/self_mod_dialog.py`
- `skills/followup_queue.py`
- `skills/dev_notifier.py` if a fresh trace finds a live send path
- `core/evolution/will_i.py` only if a fresh trace finds rendered Telegram
  content, not just policy prose

Required migration:

- Approval-card formatting should return either a provenance-bearing object or
  enough structured fields for the Telegram caller to construct one.
- Self-mod dialog replies should preserve Maez-dialog voice as owner-bound
  Maez-authored text, while action/status facts remain separately classifiable.
- Follow-up delivery may keep rendering in the daemon if the queue only stores
  task references.
- No module should hide content in opaque metadata to dodge the envelope.

## Inventory State

Current after chokepoint implementation:

```yaml
path: skills/surface/telegram_adapter.py
surface: telegram
status: chokepoint_shadow
```

Target after producer threading implementation:

```yaml
path: skills/surface/telegram_adapter.py
surface: telegram
status: producer_threaded_shadow
```

If implementation chooses fail-closed enforcement for Telegram, the status may
use an enforced/migrated value only after live canaries prove no legacy
content-bearing shim remains. Do not claim global enforcement flip.

Inventory tests must explicitly accept `producer_threaded_shadow` as a lifecycle
state before the yaml is flipped. The targeted inventory assertion must prove
the Telegram entry changed from `chokepoint_shadow` to
`producer_threaded_shadow` only after producer threading, while
`action_engine_external_fetch` remains `unmigrated`.

Do not change:

```yaml
path: core/actions/action_engine.py
surface: action_engine_external_fetch
status: unmigrated
```

## RED Tests

Tests must fail on `c8d5549` for the expected reasons.

1. **No production legacy text shims.** Production code outside
   `core/egress/telegram_egress.py` and tests does not call
   `legacy_text_envelope(...)`.
2. **No production legacy shadow sends.** No production Telegram path,
   including content-free transport controls (typing, callback ack, reactions,
   draft presence), sets or inherits `allow_legacy_shadow_send=True`.
3. **Surface adapter send text is precise.** `TelegramAdapter.send(...)` emits
   `maez_authored_owner_third_party_transport` for reviewed owner-bound Maez
   text and preserves multi-span input when provided. The test must pin the
   anti-laundering mechanism: provenance-bearing content type, explicit
   reviewed-source argument, or static production-call-site proof. An unreviewed
   raw string reaching `TelegramAdapter.send(...)` must stay
   `unclassified`/blocked or fail static proof, not become owner Maez-authored.
   Include at least one inherited `BasePlatformAdapter` fallback shape, such as
   media fallback text or a platform-base delivery-failure/error notice.
4. **Surface adapter edit preserves provenance.** `edit_message(...)` does not
   collapse edited text to `unclassified`.
5. **Interactive markup remains first-class.** `send_exec_approval(...)` and
   `send_model_picker(...)` expose labels and callback classes through typed
   markup and classify visible prompt text separately from metadata.
6. **Transport controls are content-free.** Typing, no-arg callback answers,
   reactions, and draft presence produce content-free diagnostics and no raw
   text fields.
7. **Media captions are spanned.** Voice/audio/photo/document/video/animation
   captions are provenance-bearing and media refs remain non-reconstructive.
8. **Voice main reply precise.** The audited owner chat reply path in
   `skills/telegram_voice.py` reaches the chokepoint as
   `maez_authored_owner_third_party_transport`, not `unclassified`.
9. **Voice raw sync send not laundering.** Production callers cannot use
   `TelegramVoice.send_message(text)` to send content-bearing raw strings
   without provenance. Static production-call-site proof is primary and must
   flag raw `self.telegram.send_message(...)` in `daemon/maez_daemon.py`,
   `core/actions/action_engine.py`, and `core/evolution/dream_state.py` until
   those sites pass envelopes or typed helper objects. Runtime guard on the
   retained sync surface is defense-in-depth. The static proof must include
   negative cases for alias-then-call and single-level `getattr(...)` patterns.
   Arbitrary reflection (`exec`, `eval`, `compile`), `__getattribute__`
   overrides, and runtime class swaps are explicitly out of v1 static scope and
   rely on runtime refusal if they reach the sync surface.
10. **Public reply remains precise.** Public Maez replies and `/start` messages
    remain `maez_authored_public_third_party_transport`.
11. **Public owner alert multi-span.** `_alert_rohit(...)` produces an
    owner-bound envelope whose static alert text and public-user message/profile
    material are separate spans; owner alert route follows actual token
    identity. Because `_alert_rohit(...)` uses `MAEZ_TELEGRAM_TOKEN` /
    `self.rohit_token`, route is `owner_private` and audience is
    `bonded_owner` even though the producer lives in `telegram_public.py`.
12. **Public typing content-free.** `_public_chat_action(...)` is content-free
    and no longer legacy/unclassified.
13. **Daemon producers born at source.** The four daemon sends listed in this
    spec construct provenance-bearing envelopes before entering the voice
    Telegram abstraction.
14. **Action notifications born at source.** Action-engine Tier 2/Tier 3 and
    expired-action Telegram notifications construct owner-bound multi-span
    envelopes and do not claim `action_engine_external_fetch` migration.
15. **Dream proposal sends born at source.** Dream and training proposal
    notifications construct owner-bound envelopes and preserve static command
    hints separately.
16. **Approval-card renderer provenance.** Approval card renderers expose
    structured/provenance-bearing fields or equivalent typed data; card text is
    not a raw string by the time it enters Telegram transport.
17. **No opaque metadata content.** User-visible text, callback payloads,
    captions, URLs, file names, and action output are not hidden in metadata
    fields. Behavior tests must capture produced `TelegramEgressEnvelope` and
    diagnostic rows for at least `send_exec_approval(...)`,
    `send_model_picker(...)`, one action-engine notification, and one
    approval-card renderer send. The envelope must represent user-visible text
    as `content`, `caption`, or typed `interactive_markup`, not generic
    metadata. Diagnostic rows must contain only bounded metadata/digests for
    markup and no raw labels, callback payloads, command text, action output,
    URLs, or file names.
18. **Policy behavior unchanged.** Existing owner/public Telegram gate policy
    tests still pass; this slice changes source classification, not audience
    law.
19. **Direct-send bypass inventory unchanged.** Static AST direct-send
    inventory still catches Telegram library calls outside the chokepoint.
20. **Diagnostic hygiene preserved.** Producer-threaded diagnostics still use
    keyed `hmac-sha256:` digests and contain no raw canary text, chat id, token,
    media bytes, or unsafe callback data.
21. **Live canary forward-only.** Live verification snapshots diagnostic log
    size/count before producer-threading canaries and asserts only new rows.
22. **Cloud and fast-backend regressions closed.** Claude-router still produces
    fresh proxy span-bundle rows; `fast_backend_cloud/generate` row count does
    not grow.

## Acceptance Bar

Implementation is accepted only after:

- RED-first evidence shows the new producer-threading tests fail on current
  code for expected reasons.
- Focused Telegram producer-threading tests pass.
- Existing Telegram chokepoint tests pass.
- Existing egress/routing tests pass within known baseline.
- No production `legacy_text_envelope(...)` calls remain outside
  `core/egress/telegram_egress.py`.
- No content-bearing production path can send through a raw-string Telegram
  wrapper without provenance.
- No raw `TelegramAdapter.send(...)` or `TelegramVoice.send_message(...)`
  compatibility surface can launder unreviewed strings into owner/public
  Maez-authored transport.
- Inherited `BasePlatformAdapter` Telegram fallback paths either use
  provenance-bearing helpers or are proven unreachable for Telegram.
- Static sync-send proof catches direct, alias, and single-level `getattr(...)`
  raw `send_message(...)` patterns in production roots.
- Static direct-send bypass inventory still has zero unapproved production hits.
- Owner-safe live canary produces a precise owner transport diagnostic row.
- Owner-memory live canary still allows owner-context memory to bonded owner.
- Public-safe live canary produces a precise public transport diagnostic row.
- Public-owner-context live canary still blocks.
- Public-owner alert canary records owner-private route and multi-span
  classification.
- Action notification canary records multi-span owner-bound classification.
- Diagnostics remain non-reconstructive.
- `action_engine_external_fetch` remains explicitly unmigrated.
- Inventory yaml status reflects actual posture, likely
  `producer_threaded_shadow`.
- `tests/test_privacy_egress_inventory.py` accepts `producer_threaded_shadow`
  explicitly and asserts the Telegram entry changed while
  `action_engine_external_fetch` remains `unmigrated`.
- No daemon/proxy restart happens during build; live restart is a deliberate
  post-merge step with predicted effect.

## Evidence Required For Review

Reviewers must answer:

- Did the implementation remove production legacy shims rather than rename
  them?
- Did any wrapper promote raw strings wholesale to owner/public Maez-authored
  content?
- Does `TelegramAdapter.send(...)` remain a laundering side door?
- Do inherited `BasePlatformAdapter` fallback paths remain laundering side
  doors into `TelegramAdapter.send(...)`?
- Do action notifications preserve action params/output as distinct source
  material?
- Does `TelegramVoice.send_message(...)` remain a laundering side door?
- Does the static sync-send proof catch direct, alias, and single-level
  `getattr(...)` send patterns while honestly bounding arbitrary reflection out
  of v1 static scope?
- Are public-user fields in owner alerts treated as third-party/private rather
  than public facts?
- Do public replies stay public-origin and owner alerts stay owner-route by
  actual token identity?
- Do transport controls stay content-free?
- Are media captions and media refs separated?
- Are interactive labels and callback classes typed, bounded, and
  non-reconstructive in diagnostics?
- Does the slice avoid claiming `action_engine_external_fetch` is migrated?
- Does it preserve the watchdog-style rule that egress diagnostics are not
  injected into Maez's own reasoning context?

## Non-Goals

- No new origin class.
- No consent-tier redesign.
- No public-bot memory redesign.
- No public Telegram onboarding/product redesign.
- No Telegram bot consolidation.
- No cross-module Bot-construction cleanup for
  `telegram_public.py:_alert_rohit(...)`; that future cleanup remains tracked
  as a producer-architecture task.
- No global enforcement flip.
- No action-engine external HTTP migration.
- No cloud route changes.
- No memory deletion, promotion, or recall widening.
- No S7.3 guarded execution mutation.
- No change to Maez's SOUL or voice prompt.

## Build Path

Expected ladder:

1. Draft this spec.
2. Claude council review.
3. Codex engineering panel review.
4. Fold amendments.
5. Canonicalize v1.
6. Separate RED-first implementation slice in isolated worktree.
7. Both-lane implementation review.
8. Fast-forward merge to main.
9. Deliberate observed restart.
10. Live Telegram producer-threading canaries.

No implementation before canonicalization.

## Plain-Language Summary

The Telegram gate is already standing at the road. But some messages still
arrive at the gate wearing a paper bag that says "unknown." This spec says the
message must be labeled where it is born: Maez's own reply, owner's words,
public stranger's text, action result, memory, media caption, button label, or
plain typing signal. The gate can only make honest decisions if the message
arrives with an honest label.
