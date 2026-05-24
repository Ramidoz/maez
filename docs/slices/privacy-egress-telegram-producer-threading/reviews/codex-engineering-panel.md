# Codex Engineering Panel -- Telegram Producer Threading Spec

**Artifact reviewed:** `docs/slices/privacy-egress-telegram-producer-threading/spec.md`
**Companion reviewed:** `docs/slices/privacy-egress-telegram-producer-threading/legacy-shim-inventory.md`
**Base code checked:** `c8d5549` (`feat(egress): add Telegram chokepoint shadow gate`)
**Review date:** 2026-05-24
**Verdict:** RATIFY-WITH-AMENDMENTS

## Summary

The draft is grounded in real code surfaces. The six legacy factory call sites
and one already-precise public reply call site in the Current State table match
the code at `c8d5549`, and the producer categories are the right ones for this
sub-slice. The spec also preserves the chokepoint slice's key boundary:
producer threading must not claim `action_engine_external_fetch` migration.

The architecture is sound. The required folds are test-sharpening and
tracking folds, not a redesign: close raw-string laundering at the two real
compatibility wrappers, make the deferred cross-module Telegram authority
cleanup durable, pin the new inventory lifecycle state in tests, and make
metadata-side-channel tests behavioral enough that implementation cannot pass
accidentally.

## Verified Surface Matches

- `skills/surface/telegram_adapter.py:3486` still constructs
  `legacy_text_envelope(...)` inside `_telegram_egress_envelope(...)`.
- `skills/telegram_voice.py:52`, `:69`, and `:86` still construct
  `legacy_text_envelope(...)` for `_reply_text(...)`,
  `_bot_send_message(...)`, and `_bot_send_chat_action(...)`.
- `skills/telegram_public.py:53` is already precise through
  `public_text_envelope(...)`.
- `skills/telegram_public.py:68` and `:85` still construct
  `legacy_text_envelope(...)` for owner alerts and public chat actions.
- `core/actions/action_engine.py` has the 13 Telegram notification sends named
  by the draft: 12 Tier 2/Tier 3 request/queue sends plus the expired-action
  notification.
- `daemon/maez_daemon.py` has the four indirect `self.telegram.send_message(...)`
  sites named by the draft.
- `core/evolution/dream_state.py` has the two proposal notification sends named
  by the draft.

## Required Amendments

### 1. Pin the raw `TelegramAdapter.send(content: str)` anti-laundering mechanism

The draft correctly says `TelegramAdapter.send(...)` must preserve provenance
when supplied and may classify final reviewed Maez owner text as
`maez_authored_owner_third_party_transport`. As written, however, RED #3 can be
implemented by blanket-promoting every raw `content: str` passed to
`TelegramAdapter.send(...)`.

Evidence:

- `skills/surface/telegram_adapter.py:1222-1228` exposes
  `async def send(..., content: str, ...)`.
- The current send path formats/splits the raw string, then calls
  `_egress_call(...)`; the producer provenance boundary has already been lost
  by then.

Required fold:

- Add explicit language that raw `TelegramAdapter.send(..., content: str)` is a
  compatibility surface, not a provenance authority.
- RED #3 must name the mechanism that prevents laundering: either
  `send(...)` accepts a provenance-bearing content type / explicit reviewed
  source argument, or static production-call-site proof shows every raw-string
  call site is reviewed and mapped to a precise helper before transport.
- Include a negative test where an unreviewed raw string reaches
  `TelegramAdapter.send(...)`; it must stay `unclassified`/blocked or fail the
  static proof, not become owner Maez-authored text.

### 2. Make RED #9 use both static proof and runtime guard for `TelegramVoice.send_message(...)`

Claude council's Descartes observation is correct: RED #9 names the laundering
point but not the enforcement mechanism. The risk is real because
`TelegramVoice.send_message(text)` is the sync bridge used by daemon, action
engine, and dream-state producers.

Evidence:

- `skills/telegram_voice.py:5094-5110` exposes
  `def send_message(self, text: str)` and forwards each split part to
  `_bot_send_message(...)`.
- `daemon/maez_daemon.py:2073`, `:2177`, `:4147`, and `:5757` use
  `self.telegram.send_message(...)`.
- `core/actions/action_engine.py:1890-2305` uses
  `self.telegram.send_message(...)` for action notifications.
- `core/evolution/dream_state.py:343` and `:641` use
  `self.telegram.send_message(...)` for proposal notices.

Required fold:

- RED #9 should require static production-call-site proof for raw sync sends.
  At minimum, the AST inventory must flag production `self.telegram.send_message(...)`
  in the named producer files until those sites pass envelopes or typed helper
  objects.
- RED #9 should also require a runtime defense-in-depth guard on the retained
  sync compatibility surface: content-bearing raw strings cannot silently become
  owner/public transport classes without explicit provenance.
- State the role split: static proof is the primary invariant; runtime guard is
  defense-in-depth, matching the fast-backend and Telegram chokepoint pattern.

### 3. Track deferred `telegram_public.py` owner-private Bot construction as a future cleanup

The draft correctly keeps the deeper cleanup out of this slice. But as Locke
flagged, the carve-out is currently easy to lose after canonicalization.

Evidence:

- `skills/telegram_public.py:337` constructs `Bot(token=self.rohit_token)`.
- `skills/telegram_public.py:346` routes the actual send through
  `_public_owner_alert(...)`, so this slice only needs to preserve route and
  audience correctness.

Required fold:

- Add the deferred cross-module Bot construction cleanup to a durable
  follow-up location: Non-Goals plus a "Deferred Cleanup" or "Future
  Producer-Architecture Cleanup" subsection is enough.
- Name the desired future shape: owner alerts emitted from the public module
  should eventually route through the owner-private adapter/voice surface
  instead of constructing an owner-private Bot inside `telegram_public.py`.

### 4. Name the token-identity routing rationale in RED #11

The spec already says route/audience must follow actual token identity, not
module path. RED #11 should make the reason explicit so the implementation does
not regress to "public module means public route."

Evidence:

- `skills/telegram_public.py:45` loads `MAEZ_TELEGRAM_TOKEN`.
- `_alert_rohit(...)` uses `self.rohit_token`, then `_public_owner_alert(...)`
  declares `bot_route="owner_private"` and `audience_class="bonded_owner"`.

Required fold:

- Expand RED #11 to say the owner alert from `telegram_public.py` is
  owner-private because the actual token is `MAEZ_TELEGRAM_TOKEN`; the route is
  `owner_private` and audience is `bonded_owner` even though the producer lives
  in the public module.

### 5. Extend legacy-shadow retirement to content-free controls, not only content-bearing sends

The prose disallows legacy wrappers for typing controls, but RED #2 only says
"content-bearing Telegram paths." That can pass while leaving `_bot_send_chat_action(...)`
or `_public_chat_action(...)` on legacy `unclassified`.

Evidence:

- `skills/telegram_voice.py:85-99` wraps `send_chat_action` with
  `legacy_text_envelope(...)`.
- `skills/telegram_public.py:84-98` wraps public chat action with
  `legacy_text_envelope(...)`.
- The draft's RED #6 and RED #12 cover transport controls, but RED #2 remains
  narrower than the prose.

Required fold:

- Update RED #2 to say no production Telegram path, including content-free
  transport controls, sets or inherits `allow_legacy_shadow_send=True`.
- Keep RED #6/#12 as behavior tests, but make RED #2 the broad static invariant.

### 6. Specify the inventory-state test update for `producer_threaded_shadow`

The draft proposes `producer_threaded_shadow`, which is a sensible lifecycle
state. Current inventory tests do not accept it yet.

Evidence:

- `tests/test_privacy_egress_inventory.py:40-48` has the accepted status set;
  it includes `chokepoint_shadow` and `deprecated`, but not
  `producer_threaded_shadow`.

Required fold:

- Add a RED test requirement that `producer_threaded_shadow` is an explicit
  accepted inventory lifecycle state.
- Add a targeted test that the Telegram entry flips from `chokepoint_shadow` to
  `producer_threaded_shadow` only after producer threading, while
  `action_engine_external_fetch` stays `unmigrated`.

### 7. Make "No opaque metadata content" behaviorally assertable

RED #17 is directionally right but too abstract. The implementation could pass
with source grep while still hiding button labels, action output, URLs, or file
names in opaque metadata structures that diagnostics later log.

Evidence:

- `skills/surface/telegram_adapter.py:1477-1488` builds update-prompt text plus
  inline button labels and callback data.
- `skills/surface/telegram_adapter.py:1510-1544` builds command approval text,
  button labels, callback data, and command preview.
- `skills/approval_card.py:153-164`, `:183-240`, and `:288-310` format card
  body/resolution/reminder text and then call an injected send function.

Required fold:

- RED #17 should require behavioral capture of the produced
  `TelegramEgressEnvelope` and diagnostic row for at least:
  `send_exec_approval(...)`, `send_model_picker(...)`, one action-engine
  notification, and one approval-card renderer send.
- The test must assert user-visible text is represented as `content`,
  `caption`, or typed `interactive_markup`, not generic metadata.
- The diagnostic row must contain only bounded metadata/digests for markup and
  no raw labels, raw callback payloads, raw command text, raw action output,
  raw URL, or raw file name.

## Non-Blocking Observations

- The draft's "No new origin class" boundary is correct and verified. This slice
  should not extend closed vocabulary again.
- The action-engine boundary is correctly scoped: Telegram notifications are in
  scope; `action_engine_external_fetch` remains unmigrated.
- The Paperclip-unavailable discipline is correct: do not add unverifiable
  literature claims to this spec body.

## Verdict

RATIFY-WITH-AMENDMENTS.

The producer-threading architecture is right and the surface trace is credible.
Fold the seven amendments above, then run a second council pass. A full Codex
panel pass-2 is optional if the folds are purely textual/test-sharpening, but
recommended if the fold changes the implementation target surface for either
raw wrapper.
