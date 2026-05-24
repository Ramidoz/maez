# Codex Engineering Panel Pass 2 -- Telegram Chokepoint Spec

**Artifact reviewed:** `docs/slices/privacy-egress-telegram-chokepoint/spec.md`
**Spec status at review:** DRAFT post-fold, 730 lines, ASCII-clean, no placeholder markers
**Prior panel artifact:** `docs/slices/privacy-egress-telegram-chokepoint/reviews/codex-engineering-panel.md`
**Review date:** 2026-05-23
**Verdict:** RATIFY-WITH-AMENDMENTS

## Summary

All nine pass-1 folds are present and materially faithful. The folded spec is
architecturally coherent: `unclassified` legacy shims force producer migration,
chat-id telemetry uses keyed HMAC, public-owner alerts route by actual token
identity, interactive markup is no longer opaque metadata, URL media fallback is
explicitly disabled/routed/inventoried, and the Telegram call classes are named
as `decide_egress(...)` targets.

Pass 2 found one remaining test-sharpening amendment. It does not change the
architecture. It closes a "passes on accident" gap in the static bypass
inventory around callback answers.

## Fold Fidelity Check

1. **Legacy shims unclassified:** present at envelope semantics, runtime guard,
   and producer responsibilities. Enforcement readiness is not claimed.
2. **Chat-id digest:** `chat_id_digest` is pinned to `hmac-sha256:` with the
   local egress telemetry key or equivalent purpose-scoped local key.
3. **Future operator/bonded-owner divergence:** Track B / Track C divergence is
   named out of scope and requires a separate covenant pass.
4. **Public owner alert token identity:** `telegram_public.py` owner alerts are
   routed by actual token identity, not module name.
5. **Interactive markup:** `interactive_markup` is a typed envelope field;
   button labels and callback data are not allowed to hide in metadata.
6. **AST inventory expansion:** receiver-varied `edit_message_text`,
   callback answers, and reactions are named.
7. **URL media fallback:** v1 position is explicit: disable direct
   `httpx`/`requests` media fetch fallback, or route/inventory before merge.
8. **Gate call classes:** `decide_egress(...)` is named as implementation
   target for `owner_third_party_transport_send` and
   `public_third_party_transport_send`.
9. **Duplicate bullet:** `Not local bonded UI` appears once.

## Role Verdicts

**Dewey -- RATIFY-WITH-AMENDMENTS.** The spec is implementable as a narrow
chokepoint slice. The only remaining issue is test sharpness for no-text
callback acknowledgements.

**Feynman -- RATIFY-WITH-AMENDMENTS.** The mechanism is clear, but the wording
"query.answer(text=...)" can be read too narrowly. A no-text callback answer is
still a Telegram API call and should not remain outside the chokepoint.

**Locke -- RATIFY-WITH-AMENDMENTS.** Authority boundaries are correct after the
folds. The static inventory is the primary authority; therefore it must include
all callback answer calls, not only content-bearing callback answers.

**Descartes -- RATIFY-WITH-AMENDMENTS.** Current code has both
`query.answer(text=...)` and `query.answer()` calls. A test that only detects
the former can pass while leaving the latter as a direct Telegram transport
call. That is the pass-2 failure mode.

**Ohm -- RATIFY-WITH-AMENDMENTS.** Content-free transport controls still need
route/audience metadata and telemetry. No-text callback answers should be
represented as content-free transport-control events.

**Goodall -- RATIFY-WITH-AMENDMENTS.** The covenant shape remains sound. The
amendment prevents a future "not content, so not egress" loophole from creeping
into the Telegram road.

## Required Amendment

### 1. Static inventory must cover all callback answers, not only `text=...`

The folded spec lists callback answers as `query.answer(text=...)`. Current code
also has multiple no-text callback acknowledgements, for example:

- `await query.answer()` in `skills/surface/telegram_adapter.py` model-picker
  callback paths.
- `await query.answer(text=...)` in the same callback handler family.

Both are outbound Telegram API calls. The text-bearing form is content-bearing;
the no-text form is a content-free transport-control event. The static inventory
must catch both.

Fold:

- Change the static pattern language from `query.answer(text=...)` to
  `query.answer(...)` / callback-query answer calls on any receiver.
- State that `text=` callback answers are content-bearing transport text, while
  no-text callback answers are content-free transport-control events.
- Update RED #6 / RED #14 so they fail independently for both forms:
  callback answer with text, and callback answer without text.
- Update the Acceptance Bar line "Callback answers..." to cover both forms.

## Non-Blocking Notes

- The `interactive_markup` field is sufficient as a conceptual shape. The
  implementation can define a small typed sub-object for button labels,
  callback-data class/count metadata, and reviewed-static markers.
- Stdlib `ast` remains sufficient for v1. The important point is matching the
  direct AST call shapes: `query.answer(...)`, `*.edit_message_text(...)`,
  `*.send_*`, and `*.set_message_reaction(...)`.
- The URL media fallback disposition is appropriately narrow: disabling the
  Maez-side `httpx` fallback is cleaner than dragging the external-fetch slice
  into this one.

## Expected Fold Output

Update `docs/slices/privacy-egress-telegram-chokepoint/spec.md` in place.

After the single amendment is folded, a third pass should only need to verify:

- all callback answer wording covers both text and no-text forms,
- RED tests name both forms,
- acceptance criteria names both forms,
- no new scope claims are introduced.

