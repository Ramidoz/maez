# Codex Engineering Panel -- Telegram Chokepoint Spec

**Artifact reviewed:** `docs/slices/privacy-egress-telegram-chokepoint/spec.md`
**Spec status at review:** DRAFT, 655 lines, ASCII-clean, no placeholder markers
**Review date:** 2026-05-23
**Verdict:** RATIFY-WITH-AMENDMENTS

## Summary

The core architecture is sound: `core/egress/telegram_egress.py` as the small
transport chokepoint, static AST bypass inventory as the primary invariant, a
runtime provenance guard as defense-in-depth, and a deliberate
`maez_authored_public_third_party_transport` vocabulary extension.

The spec is not merge-ready as-is. The panel found several concrete code-surface
gaps that should be folded before canonicalization. None overturns the chosen
architecture; all are textual/spec tightenings against real Telegram surfaces.

## Role Verdicts

**Dewey -- RATIFY-WITH-AMENDMENTS.** The decomposition is practical: close the
transport bypasses first, thread producer-side provenance second. The sync/async
contract matches real producers. Required folds mostly sharpen the migration
surface so implementation does not discover them late.

**Feynman -- RATIFY-WITH-AMENDMENTS.** The mental model is clear, but some
mechanisms need sharper names. "Legacy conservative provenance" must say exactly
which origin class it means, and interactive Telegram markup must not hide
content in `metadata`.

**Locke -- RATIFY-WITH-AMENDMENTS.** Authority placement is correct: static
inventory is the law; runtime guard is belt. The public-stranger vocabulary class
is justified. The spec must correct one authority confusion: `telegram_public.py`
owner alerts use `MAEZ_TELEGRAM_TOKEN`, so route/audience cannot be inferred from
the module name.

**Descartes -- RATIFY-WITH-AMENDMENTS.** Failure-mode coverage is strong, but
the current spec misses three bypass-shaped cases: callback answers/reactions,
interactive button markup, and the image URL download fallback. These are exactly
the small "not a send_message" routes that bypass inventories tend to miss.

**Ohm -- RATIFY-WITH-AMENDMENTS.** Diagnostics are the right shape but need an
explicit keyed digest algorithm (`hmac-sha256:`) for chat IDs. The spec also
needs to prevent opaque metadata from becoming a telemetry side channel.

**Goodall -- RATIFY-WITH-AMENDMENTS.** Covenant shape is right: owner-bound
Telegram remains a bond surface; public Telegram is structurally more
conservative. Add the future Track B/C note about operator vs bonded-owner
divergence so this v1 does not overgeneralize Rohit's single-owner deployment.

## Required Amendments

### 1. Legacy shim provenance must be `unclassified`

The spec currently says legacy wrappers attach "conservative provenance" and a
clear `source_ref`, but does not name the origin class. This is ambiguous enough
to become a permanent half-migration.

Fold:

- Legacy shims in this chokepoint slice use `unclassified`.
- Under enforcement, `unclassified` blocks.
- Under shadow, they may be logged as legacy/conservative only if the
  implementation is explicitly shadow-only.
- Producer-side provenance threading is therefore a prerequisite to claiming
  Telegram enforcement readiness.

This matches the intended phasing: the first slice closes bypasses; the second
slice makes precise safe sends possible.

### 2. Chat-id digest must be `hmac-sha256:`

The Diagnostic Log Contract says "chat id digest, not raw chat id" but does not
pin the algorithm. Existing egress telemetry uses keyed HMAC.

Fold:

- `chat_id_digest` must use `hmac-sha256:` with the local egress telemetry key
  or an equivalent purpose-scoped local key.
- Bare SHA256 of chat IDs is forbidden.
- Add RED coverage that raw chat ID and bare digest do not appear in diagnostic
  output.

### 3. Future operator/bonded-owner divergence is out of scope

The Block Behavior section correctly says Rohit's current operator and bonded
owner are the same person, and that diagnostics still belong in local/operator
surfaces rather than the bond conversation. Future deployments where operator
and bonded owner diverge make this a privacy/authority question.

Fold:

- Add a short out-of-scope note: future Track B/C deployments with
  operator != bonded owner require a separate covenant pass before operator
  visibility of owner-bound blocked-message diagnostics is generalized.

### 4. Public-bot owner alert route must be corrected

The spec says a "public-bot owner alert uses the public bot route but has
bonded-owner audience." Current code does not support that as written:

- `skills/telegram_public.py:213-214` reads both `MAEZ_PUBLIC_TELEGRAM_TOKEN`
  and `MAEZ_TELEGRAM_TOKEN`.
- `_alert_rohit(...)` constructs `Bot(token=self.rohit_token)` at
  `skills/telegram_public.py:282`, i.e. the owner-private token, not the public
  bot token.

Fold:

- Do not state that public-module owner alerts use the `public_stranger` route.
- State that owner alerts emitted from `telegram_public.py` must declare
  `audience_class="bonded_owner"` and a bot route matching the actual token
  identity used (`owner_private` if using `MAEZ_TELEGRAM_TOKEN`).
- Add a RED test for this case: public-stranger reply and owner alert from
  `telegram_public.py` produce different route/audience envelopes.

### 5. Interactive markup must be first-class egress, not opaque metadata

The conceptual envelope has `metadata`, but real Telegram methods send
`reply_markup`, button labels, and `callback_data`:

- `send_exec_approval(...)` and `send_model_picker(...)` build inline keyboards
  in `skills/surface/telegram_adapter.py`.
- `query.edit_message_text(...)` updates button-driven UI text.

Button labels are user-visible Telegram text. Callback data can carry session or
approval identifiers. If this is hidden inside opaque `metadata`, it bypasses
the provenance/diagnostic contract.

Fold:

- Add an explicit envelope field or typed sub-object for interactive markup.
- Button labels are content-bearing transport text and must be covered by
  provenance or constrained to reviewed static strings.
- Callback data must be non-secret, bounded, and logged only as safe class/count
  metadata, not raw if it can contain request/session identifiers.
- Add RED coverage for approval/model-picker markup.

### 6. Static inventory must include callback answers and reactions

The current pattern list covers many send methods but misses live Telegram
methods in `telegram_adapter.py`:

- `query.answer(text=...)` at multiple callback sites.
- `self._bot.set_message_reaction(...)` in `_set_reaction(...)`.

Callback answers can display text to the user. Reactions are content-free-ish
but still outbound Telegram state changes and are already named in prose.

Fold:

- Add `.answer(...)` on Telegram callback query objects when `text=` is present.
- Add `set_message_reaction(...)`.
- Clarify that `.edit_message_text(...)` must match any receiver
  (`query.edit_message_text`, `self._bot.edit_message_text`, etc.), not only
  direct bot calls.
- Add RED coverage for callback answers and reactions.

### 7. URL media fallback is a hidden outbound HTTP fetch

`TelegramAdapter.send_image(...)` does more than call Telegram. If Telegram URL
send fails, it performs:

- `httpx.AsyncClient(...).get(image_url)` at
  `skills/surface/telegram_adapter.py:2161-2163`.

`skills/surface/platform_base.py` also contains URL download/cache helpers. This
is an external HTTP fetch embedded in the Telegram send path. A Telegram
chokepoint migration must not silently leave that direct external GET as a new
unmigrated egress surface.

Fold one of these explicit v1 positions:

- Disable direct Maez-side URL download fallback in migrated Telegram sends and
  let Telegram handle URL media directly, or
- Route the URL fetch through an existing/future external-fetch gate and record
  it in the allow-list, or
- Explicitly inventory it as a separate deferred external-fetch surface with
  its own removal target.

The panel recommends disabling or separately inventorying the fallback for v1.
Add RED coverage that migrated Telegram sends do not perform untracked direct
`httpx`/`requests` external media fetches.

### 8. Gate targets should name Telegram call-class implementation explicitly

The spec says "Gate/policy extension" but the current gate implementation only
accepts `cloud_model_inference` in `decide_egress(...)`. Implementation will
need deliberate new call-class handling.

Fold:

- Name `core/egress/gate.py::decide_egress` as an implementation target for
  `owner_third_party_transport_send` and
  `public_third_party_transport_send`.
- Add RED policy tests that fail on current code because these call classes are
  currently `unknown_call_class`.
- Preserve cloud behavior unchanged.

### 9. Remove duplicate "Not local bonded UI" bullet

Minor but worth cleaning before canonicalization: the Non-meaning list repeats
"Not local bonded UI." Remove one duplicate.

## Non-Blocking Notes

- The sync/async chokepoint pair is feasible. Sync callers can bridge to the
  event loop the way `TelegramVoice.send_message(...)` already does, but the
  implementation should avoid creating fresh `Bot(token=...)` objects outside
  the chokepoint.
- Stdlib `ast` is sufficient for the first bypass inventory. A richer callgraph
  tool is not required for v1 if the test matches the direct Telegram method
  shapes and direct `Bot(...)` constructions.
- `skills/screen_perception.py` is correctly excluded. Current hits are
  filename/docstring and the word `Application`, not Telegram egress.
- `action_engine_external_fetch` must stay unmigrated after this slice. The
  action engine's Telegram notifications are in scope only because they borrow
  the migrated Telegram abstraction.

## Expected Fold Output

Update `docs/slices/privacy-egress-telegram-chokepoint/spec.md` in place.

After folds, the next review should verify:

- all nine amendments are present,
- the three Claude council observations are captured,
- the spec still remains docs-only,
- no scope claim says `action_engine_external_fetch` is migrated,
- the bypass pattern list covers callback answers, reactions, edits, media, and
  URL-fetch fallback discipline.
