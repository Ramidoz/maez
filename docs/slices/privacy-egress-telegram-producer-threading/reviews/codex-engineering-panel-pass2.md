# Codex Engineering Panel Pass 2 -- Telegram Producer Threading Spec

**Artifact reviewed:** `docs/slices/privacy-egress-telegram-producer-threading/spec.md`
**Base code checked:** `c8d5549` (`feat(egress): add Telegram chokepoint shadow gate`)
**Review date:** 2026-05-24
**Pass-1 verdict:** RATIFY-WITH-AMENDMENTS (7 folds)
**Pass-2 verdict:** RATIFY-WITH-AMENDMENTS

## Summary

All seven pass-1 folds landed faithfully. The draft now names both raw-string
laundering surfaces (`TelegramAdapter.send(...)` and
`TelegramVoice.send_message(...)`), tracks the deferred public-module owner Bot
cleanup, broadens legacy-shadow retirement to content-free controls, pins the
inventory lifecycle-state update, and makes metadata-side-channel tests
behavioral.

Pass 2 found two further test-sharpening amendments. Both are about preventing
the implementation from passing through the obvious call sites while leaving a
less obvious raw-string path open.

## Fold Fidelity

- Fold 1 landed at `spec.md:244-253` and RED #3 at `spec.md:469-475`.
  The three-option anti-laundering mechanism is present.
- Fold 2 landed at `spec.md:283-292` and RED #9 at `spec.md:489-495`.
  Static proof is primary; runtime guard is defense-in-depth.
- Fold 3 landed at `spec.md:60-67` and `spec.md:607-609`.
  The deferred `telegram_public.py:_alert_rohit(...)` Bot construction cleanup
  is now durable-tracked.
- Fold 4 landed at `spec.md:326-329` and RED #11 at `spec.md:498-503`.
  Token-identity routing rationale is explicit.
- Fold 5 landed at `spec.md:221-223` and RED #2 at `spec.md:466-468`.
  Content-free transport controls are covered by the broad static invariant.
- Fold 6 landed at `spec.md:445-449` and `spec.md:570-572`.
  `producer_threaded_shadow` must be accepted by inventory tests and the
  action external-fetch route must stay `unmigrated`.
- Fold 7 landed at `spec.md:518-527`.
  RED #17 now requires envelope and diagnostic capture for the four named
  producer shapes.

## Required Amendments

### 1. Fold 1 must cover inherited platform-base `self.send(...)` fallbacks

`TelegramAdapter.send(..., content: str)` is not only reached through explicit
producer call sites. It is also the target of inherited `BasePlatformAdapter`
fallback methods and retry/error paths.

Evidence:

- `skills/surface/platform_base.py:1216` falls back from `send_image(...)` to
  `self.send(chat_id=..., content=text, ...)`.
- `skills/surface/platform_base.py:1307`, `:1340`, `:1360`, and `:1380` do the
  same for audio, video, document, and image-file fallback text.
- `skills/surface/platform_base.py:1661`, `:1688`, `:1708`, and `:1715` call
  `self.send(...)` inside retry/failure fallback flow.
- `skills/surface/platform_base.py:2140` sends an exception/error notice through
  `self.send(...)`.
- `skills/surface/maez_adapter.py:313` calls `adapter.send(chat_id, msg_text)`
  for the self-mod intermediate dialog bridge.

As written, the spec's static proof can focus on obvious producer calls and
miss inherited fallback paths where content, URLs, file paths, exception text,
or formatting-failure text is assembled by the base class before Telegram
transport.

Required fold:

- Amend the Surface-v2 Owner Adapter section and RED #3 to state that the
  anti-laundering mechanism must cover inherited `BasePlatformAdapter`
  `self.send(...)` fallback paths as well as direct production calls.
- If implementation chooses static production-call-site proof for
  `TelegramAdapter.send(...)`, it must either prove the inherited fallback paths
  are unreachable for Telegram or override/migrate them to provenance-bearing
  media/error helpers.
- The negative test for unreviewed raw adapter send should include at least one
  inherited fallback shape, such as media fallback text or the platform-base
  delivery-failure/error notice.

### 2. Fold 2's AST proof must bound dynamic wrapper evasions

The current fold correctly names direct `self.telegram.send_message(...)`
production call sites in daemon, action engine, and dream state. A future
helper can still hide the same raw sync path behind one layer of indirection or
`getattr(...)`.

Evidence:

- Current direct sites are simple attribute calls:
  `daemon/maez_daemon.py:2073`, `:2177`, `:4147`, `:5757`;
  `core/actions/action_engine.py:1890-2305`;
  `core/evolution/dream_state.py:343`, `:641`.
- The existing chokepoint bypass inventory already uses AST receiver matching;
  this producer-threading proof should reuse that style rather than relying on
  exact line-number grep.

Required fold:

- Amend RED #9 to say the static proof scans production roots for raw sync
  send patterns, not only the currently listed files.
- The AST proof must catch at least direct attribute calls such as
  `self.telegram.send_message(...)`, alias-held TelegramVoice objects calling
  `.send_message(...)`, and string-literal dynamic calls such as
  `getattr(self.telegram, "send_message")(...)`.
- Explicitly bound what is out of v1 static scope: arbitrary `eval`,
  reflection with computed method names, or monkeypatched callables are not
  supported, but the runtime guard must still refuse raw content-bearing sends
  if such a path reaches `TelegramVoice.send_message(...)`.

## Non-Blocking Notes

- The three-option mechanism choice for `TelegramAdapter.send(...)` is
  implementable if the fold above is added. The panel does not recommend
  forbidding the three options pre-canonicalize; it recommends tightening the
  coverage target.
- `producer_threaded_shadow` inventory extension is mechanical: add one
  accepted status string and one targeted Telegram-entry assertion.
- RED #17 is implementable with fake Telegram bots and a temporary
  `MAEZ_TELEGRAM_EGRESS_LOG`, matching the chokepoint test style.

## Verdict

RATIFY-WITH-AMENDMENTS.

Apply the two amendments above, then a narrow council concurrence should be
enough. A full panel pass-3 is optional unless the fold materially changes the
chosen anti-laundering mechanism rather than only broadening test coverage.
