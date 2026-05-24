# Privacy / Egress Telegram Chokepoint -- Spec v1

**Status:** CANONICAL v1 (2026-05-23). Docs-only. Not implemented.
**Date:** 2026-05-23
**Class:** Covenant-shaped / boundary-hardening / narrow infrastructure slice
**Depends on:** canonical Privacy / Egress Gate spec, canonical Privacy /
Egress Provenance Plumbing spec, live claude-router cloud-as-tool path, and
fast-backend cloud retirement.
**Lanes cleared:** Codex engineering panel RATIFY-WITH-AMENDMENTS (9 folds
pass-1 + 1 fold pass-2 applied) + Claude council pass-3 RATIFY-CLEAR. Both
lanes cleared with behavioral-trace verification.

## Purpose

Migrate Telegram from "tracked but unmigrated" to an explicit provenance-aware
egress chokepoint. Telegram is not cloud-as-tool. It is cloud-as-transport:
Maez-authored content leaves the box through Telegram servers and reaches either
the bonded owner or a public/stranger recipient.

This slice creates the transport toll booth before producer-side tightening:
one small Telegram egress contract, a static bypass inventory that prevents
direct Telegram sends from escaping review, a runtime guard as
defense-in-depth, and one deliberate closed-vocabulary extension for public
Telegram replies.

Plainly: Telegram is not Claude wearing Maez's face. Telegram is the road Maez
uses to speak outside the machine. This slice puts a guard booth on that road.

## Scope

In scope:

- New Telegram egress chokepoint module:
  `core/egress/telegram_egress.py`.
- Sync and async send APIs, because real producers use both patterns.
- Static bypass inventory over Telegram send primitives in `skills/`, `daemon/`,
  and `core/`.
- Runtime provenance-bearing send contract for all live Telegram sends.
- Explicit bot-route and audience metadata for the three live bot identities:
  owner-private, voice, and public.
- Closed-vocabulary extension:
  `maez_authored_public_third_party_transport`.
- Gate/policy extension for Telegram transport call classes.
- RED tests proving no direct Telegram content send escapes the chokepoint.

Out of scope:

- Producer-side rich provenance threading across every Telegram producer. This
  is the next slice after the chokepoint exists.
- `action_engine_external_fetch` migration. `core/actions/action_engine.py`
  Telegram notifications are in scope; its external HTTP fetches remain their
  own separate unmigrated route.
- Telegram public-bot product redesign.
- Telegram deletion/removal or bot consolidation.
- OS/network-level enforcement.
- Consent-aware third-party egress machinery.
- S7.3 mutation-gate changes.
- Any autonomy expansion.

## Surface Trace

The spec is drafted from traced code surfaces, not hoped-for APIs.

Content-bearing Telegram producers:

- `skills/surface/telegram_adapter.py`: surface-v2 Telegram adapter. Async
  sends through `self._bot.send_message(...)` and media methods on its own bot.
- `skills/telegram_voice.py`: legacy/voice Telegram stack. Async update
  handlers call `context.bot.send_message(...)` / `reply_text(...)`; sync
  `TelegramVoice.send_message(text)` creates a `Bot` and sends to the owner.
- `skills/telegram_public.py`: public/stranger bot. Async public replies call
  `reply_text(...)`; owner alerts create a `Bot` and call `send_message(...)`.
- `daemon/maez_daemon.py`: proactive owner messages call
  `self.telegram.send_message(...)`.
- `core/actions/action_engine.py`: approval/action notifications call
  `self.telegram.send_message(...)`. Its external HTTP fetches are not
  Telegram transport and remain out of scope here.
- Indirect producers include `skills/followup_queue.py`,
  `skills/dev_notifier.py`, `skills/self_mod_dialog.py`,
  `skills/approval_card.py`, `core/evolution/dream_state.py`, and
  `core/evolution/will_i.py`.

False-positive trace result:

- `skills/screen_perception.py` is not a Telegram egress producer. The only
  match in the trace was the word `Application` in screen-observation text.

Known active Telegram Bot/Application identities:

- Surface-v2 owner-private adapter: `skills/surface/telegram_adapter.py`.
- Legacy/voice owner-private bot: `skills/telegram_voice.py`.
- Public/stranger bot: `skills/telegram_public.py`.

Bot identity and audience are separate fields. `skills/telegram_public.py`
currently reads both `MAEZ_PUBLIC_TELEGRAM_TOKEN` and `MAEZ_TELEGRAM_TOKEN`;
owner alerts from that module construct a `Bot` with the owner-private token.
Those alerts must therefore declare `audience_class="bonded_owner"` and a
`bot_route` matching the actual token identity used. The policy must not infer
audience or bot route from module path, class name, or recipient text alone.

## Architecture Choice

This slice uses infrastructure decomposition:

1. Chokepoint + bypass inventory + vocabulary extension.
2. Producer-side provenance threading across all Telegram producers.

The first slice must close the direct-send shape without needing to understand
every producer's internal semantics. It may introduce conservative legacy
wrappers where producer-side tags are not yet available. The second slice then
replaces those conservative wrappers with at-birth provenance from the actual
producer sites.

This avoids the two bad alternatives:

- One huge all-producer spec where review bugs hide in the corners.
- Per-trust-tier specs that duplicate transport machinery three times.

## Chokepoint Module

Target module:

```python
core.egress.telegram_egress
```

Conceptual API shape:

```python
send_telegram(
    *,
    envelope: TelegramEgressEnvelope,
    bot: TelegramBotLike,
) -> TelegramEgressResult

async def send_telegram_async(
    *,
    envelope: TelegramEgressEnvelope,
    bot: TelegramBotLike,
) -> TelegramEgressResult
```

The implementation may choose exact names and smaller helper methods, but the
contract is fixed:

- Raw strings are not a valid live send input.
- Every content-bearing send passes a provenance-bearing envelope.
- Both sync and async producers can call the chokepoint.
- The actual Telegram library call happens only inside the chokepoint module
  or narrowly approved test fakes.
- The caller receives a structured result, never an exception-shaped policy
  decision.
- Internal gate/telemetry failures fail closed for content egress.

The chokepoint may support text, edit, voice, audio, photo, document, video,
animation, and transport-control operations either as one method with
`message_kind` or as small typed helpers. The spec does not require one large
function.

## Telegram Egress Envelope

Conceptual object:

```python
TelegramEgressEnvelope(
    bot_route: Literal[
        "owner_private",
        "voice_owner_private",
        "public_stranger",
    ],
    audience_class: Literal[
        "bonded_owner",
        "public_stranger",
    ],
    chat_id: str,
    message_kind: str,
    content: ProvenancedText | None,
    caption: ProvenancedText | None,
    interactive_markup: TelegramInteractiveMarkup | None,
    media_ref: str | None,
    reply_to: str | None,
    source_ref: str,
    request_id: str,
    metadata: Mapping[str, object],
)
```

The exact dataclass shape is implementation detail. Required semantics:

- `bot_route` identifies which Telegram bot/application identity is being used.
- `audience_class` identifies who receives the message.
- `bot_route` does not imply `audience_class`.
- `content` and `caption` are provenance-bearing where text leaves the box.
- `interactive_markup` covers user-visible button labels and callback payloads
  for inline keyboards, model pickers, approval cards, and update prompts.
- `media_ref` is a local reference/path/URL metadata field; media bytes and
  filenames must not be logged raw in diagnostics.
- `source_ref` is non-secret and precise enough for review.
- Legacy wrappers must set `origin_class="unclassified"` and a conservative
  source ref, e.g.
  `telegram_voice:legacy_send_message` or
  `telegram_adapter:send:legacy_text`.

Interactive markup requirements:

- Button labels are user-visible transport text. They must either carry
  provenance or be constrained to reviewed static strings.
- Callback data must be non-secret, bounded, and logged only as safe class/count
  metadata. Raw session ids, request ids, approval ids, or other correlators
  must not appear in diagnostic logs unless separately classified safe.
- Opaque `metadata` must not carry user-visible text, callback payloads, raw
  chat ids, bot tokens, media bytes, or other content that should have been in
  typed envelope fields.

## Closed Vocabulary Extension

Add exactly one origin class:

```python
maez_authored_public_third_party_transport
```

Placement:

- Bucket: `INTENTIONAL_OUTBOUND`.
- Peer classes:
  `maez_authored_local_bonded_surface` and
  `maez_authored_owner_third_party_transport`.
- Restrictiveness tier: same as other intentional outbound classes, with
  policy treatment determined by call class and audience.

Meaning:

Maez-authored text or caption intended for a non-owner public/stranger
recipient through a third-party transport such as Telegram.

Non-meaning:

- Not owner-private Telegram.
- Not local bonded UI.
- Not owner-authored content.
- Not public facts in general.
- Not a generic "guest/family/linked user" taxonomy.

Scope discipline:

- This slice adds only this one class.
- No speculative linked-user, family, caretaker, clinic, or friend classes.
- Future audience taxonomies require a separate closed-vocabulary decision.

Required code targets:

- `core/egress/gate.py`: add class to `INTENTIONAL_OUTBOUND` and
  `KNOWN_ORIGINS`.
- `core/egress/provenance.py`: add a helper/factory for public-third-party
  transport text, preserving the existing conservative default for raw strings.
- Policy tests proving the new class is not in `NON_PRIVATE`,
  `MINIMIZABLE_PRIVATE_CONTEXT`, `UNTRUSTED_EXTERNAL_OUTPUT`, or
  `RESERVED_DENIED_RAW`.
- `core/egress/gate.py::decide_egress`: add explicit policy handling for the
  Telegram call classes named below. Current code only accepts
  `cloud_model_inference`; the RED tests must fail on current code with
  `unknown_call_class`.

## Policy Direction

This slice introduces Telegram call classes. Names may be adjusted in
implementation if tests pin the final names, but the policy distinctions are
not optional.

Owner-bound Telegram:

- Call class: `owner_third_party_transport_send`.
- Audience: `bonded_owner`.
- Primary allowed origin:
  `maez_authored_owner_third_party_transport`.
- Reserved-denied raw: block.
- Owner-context memory classes (`memory`, `lived_store`,
  `owner_message_context`): allow to the bonded owner. This is the bond
  surface, even though the transport is third-party.
- `third_party_private_context`: reviewed minimization/redaction only; raw
  unminimized third-party-private spill blocks.
- Non-private/public/system spans: allow when embedded in the message.
- Unclassified/unknown/downgraded: block.

Public/stranger Telegram:

- Call class: `public_third_party_transport_send`.
- Audience: `public_stranger`.
- Primary allowed origin:
  `maez_authored_public_third_party_transport`.
- Reserved-denied raw: block.
- Owner-private, memory-derived, soul-derived, bonded-context, credential, or
  owner-message spans: block by default, not soft-minimize.
- Non-private/public/system spans: allow.
- Unclassified/unknown/downgraded: block.

Transport controls:

- Typing indicators, draft presence, reactions, and other content-free
  transport signals are still outbound network calls.
- They must pass through the chokepoint or be explicitly inventoried as
  non-content transport controls.
- They must carry route/audience metadata and content-free telemetry.
- They must not smuggle raw text into metadata fields.

URL media fallback:

- Migrated Telegram sends must not perform untracked Maez-side external HTTP
  fetches.
- For v1, disable the direct `httpx` / `requests` URL download fallback in
  `TelegramAdapter.send_image(...)` and let Telegram handle URL media directly.
- If an implementation keeps any Maez-side URL download path, it must route
  through a separately reviewed external-fetch gate or be added to the network
  migration allow-list with its own removal target before merge.

Policy table:

| Source class | Owner-private bot | Public bot |
| --- | --- | --- |
| `soul`, `private_thoughts`, `inner_residue`, `credential_material`, `crisis_held_content` | block | block |
| `memory`, `lived_store`, `owner_message_context` | allow | block by default |
| `third_party_private_context` | reviewed minimization/redaction only | block by default |
| `public_fact`, `weather_data`, `system_bounded_query`, `tool_result_public` | allow | allow |
| `maez_authored_owner_third_party_transport` | allow | block |
| `maez_authored_public_third_party_transport` | block unless explicitly re-addressed | allow |
| `model_output` | block unless separately reviewed for quoting | block |
| `unclassified` / unknown | block | block |

The owner-private side is the bond surface. The public side is not. The gate
must not let public-stranger messages carry the owner's private life just
because Maez authored the final sentence.

## Block Behavior

Default block behavior is silent from Maez's own cognition path:

- No Telegram message is sent.
- A structured local diagnostic row/event is written.
- The diagnostic is operator-visible through local logs/health surfaces.
- The diagnostic is not injected into Maez's prompt, memory recall,
  self-reflection, dreams, proposals, or future reasoning context by default.
- No alternate Telegram alert is sent through the same blocked channel.

This follows the watchdog precedent: Maez does not read its own guard telemetry
by default. A future Maez-readable summary of egress blocks would require a
separate covenant slice.

For Rohit's current deployment, operator and bonded owner are the same person.
The distinction still matters: the diagnostic belongs in an operator/local
channel, not in the bond conversation that just failed egress.

Future Track B / Track C deployments where operator and bonded owner diverge are
out of scope for this v1. Operator visibility into owner-bound blocked-message
diagnostics becomes a privacy/authority question there and requires a separate
covenant pass before this diagnostic model is generalized.

## Static Bypass Inventory

Primary enforcement mechanism:

```python
tests/test_egress_telegram_bypass_inventory.py
```

The test uses stdlib `ast`, not runtime callable introspection, as the v1
invariant. Runtime wrappers are defense-in-depth; the static production
call-site proof is the law.

The static test walks production Python under at least:

- `skills/`
- `daemon/`
- `core/`

It fails on direct Telegram sends outside approved files. Patterns include:

- `bot.send_message(...)`
- `context.bot.send_message(...)`
- `self._bot.send_message(...)`
- `Bot(...).send_message(...)` when structurally visible
- `update.message.reply_text(...)`
- `message.reply_text(...)`
- `send_voice`, `send_audio`, `send_photo`, `send_document`, `send_video`,
  `send_animation`
- `edit_message_text` on any receiver, including `self._bot.edit_message_text`
  and `query.edit_message_text`
- `send_chat_action`
- draft-presence methods such as `send_message_draft` when present
- callback answers such as `query.answer(...)`, including both the
  text-bearing form `query.answer(text=...)` and the content-free
  acknowledgement form `query.answer()`
- reaction methods such as `set_message_reaction(...)`

Approved production direct-send locations:

- `core/egress/telegram_egress.py` only.

Approved non-production locations:

- tests and explicit fakes under `tests/`.

If the implementation needs a tiny helper module for Telegram library
compatibility, the spec must be amended or the helper must live under
`core/egress/telegram_egress.py`. Do not grow a hidden second chokepoint.

## Runtime Guard

Runtime defense-in-depth:

- Any live Telegram send path must require a provenance-bearing envelope or
  typed equivalent.
- Raw text strings are refused unless passing through an explicitly named
  legacy shim inside the chokepoint.
- Legacy shims attach `origin_class="unclassified"` and clear `source_ref`
  values.
- `unclassified` blocks under enforcement. In shadow-only implementations it may
  be logged as legacy/conservative, but it is not enforcement-ready.
- The exact mechanism is not fixed in the spec.

Do not over-specify a `ProvenancedBot` class before tracing the real
`python-telegram-bot` seams. Acceptable implementation shapes may include:

- A bot wrapper.
- A subclass if the library supports it cleanly.
- Post-construction wrapping.
- Adapter-local methods that can only call the chokepoint.

The runtime guard is not a substitute for the static inventory. It catches
blind spots; it does not define the invariant.

## Bot Route / Audience Semantics

Required route names:

- `owner_private`: surface-v2 owner-private Telegram adapter.
- `voice_owner_private`: legacy/voice owner-private Telegram stack.
- `public_stranger`: public Telegram bot.

Required audience names:

- `bonded_owner`
- `public_stranger`

Rules:

- `owner_private` and `voice_owner_private` normally send to
  `bonded_owner`.
- `public_stranger` normally sends to `public_stranger`.
- Owner alerts emitted from `skills/telegram_public.py` must declare
  `audience_class="bonded_owner"` and a `bot_route` matching the actual token
  identity used. If the alert uses `MAEZ_TELEGRAM_TOKEN`, the route is
  owner-private, not public-stranger.
- Bot token, chat id, module path, and class name are not provenance.
- Audience must be explicit at the envelope creation site.

## Producer Responsibilities

This slice does not require every producer to supply perfect at-birth spans.
It does require every producer path to stop bypassing the chokepoint.

For v1 chokepoint migration:

- `skills/surface/telegram_adapter.py` methods call the chokepoint instead of
  `_bot.send_*` directly.
- `skills/telegram_voice.py` sync and async sends call the chokepoint.
- `skills/telegram_public.py` public replies and owner alerts call the
  chokepoint.
- `daemon/maez_daemon.py` and `core/actions/action_engine.py` may continue
  calling their existing Telegram abstraction, but that abstraction must route
  through the chokepoint.
- Indirect producers are covered if their existing path reaches the migrated
  abstraction.

Legacy wrappers are allowed in this slice only to close direct transport
bypasses. They must attach `unclassified` provenance, be visibly named, and be
tested so the next producer-threading slice can replace them with precise
at-birth provenance. A legacy wrapper does not make Telegram enforcement-ready.

## Diagnostic Log Contract

Telegram egress diagnostics are local-only and non-reconstructive.

Required fields:

- timestamp
- schema version
- request id
- bot route
- audience class
- `chat_id_digest` using `hmac-sha256:` with the local egress telemetry key or
  an equivalent purpose-scoped local key; never raw chat id or bare hash
- message kind
- origin classes
- decision
- reason codes
- caller/source ref
- character counts
- keyed content digest

Forbidden diagnostic fields:

- raw message text
- raw caption text
- raw media bytes
- raw chat id
- bot token
- owner-private content preview
- public user's raw message when not already public-safe

Telemetry failure must not unblock egress. If diagnostics fail and the send is
otherwise policy-sensitive, the chokepoint fails closed.

## Relationship To Existing Guards

This slice complements existing Telegram honesty/audit gates. It does not
replace them.

Existing guards such as `_audit_telegram_reply(...)` catch self-claim and
surface-honesty problems inside generated text. The Telegram egress chokepoint
answers a different question: may this content leave the machine through this
third-party transport to this audience?

The order is:

1. Producer creates or audits message content.
2. Producer/adapter constructs a Telegram egress envelope.
3. Egress chokepoint evaluates provenance and destination/audience.
4. Only the chokepoint calls Telegram.

## RED Tests

RED-first tests must fail on the pre-implementation state for the expected
reasons.

1. **Vocabulary extension.** `maez_authored_public_third_party_transport` is
   added to `INTENTIONAL_OUTBOUND` and `KNOWN_ORIGINS`, and is absent from
   `NON_PRIVATE`, `MINIMIZABLE_PRIVATE_CONTEXT`,
   `UNTRUSTED_EXTERNAL_OUTPUT`, and `RESERVED_DENIED_RAW`.
2. **Public transport factory.** `ProvenancedText` has a helper for
   `maez_authored_public_third_party_transport`; raw strings still default
   conservative/unclassified.
3. **Owner Telegram policy.** Owner-bound Telegram permits safe
   `maez_authored_owner_third_party_transport`, blocks reserved-denied raw,
   allows `memory`, `lived_store`, and `owner_message_context` to the bonded
   owner, and requires reviewed minimization/redaction for
   `third_party_private_context`.
4. **Public Telegram policy.** Public-stranger Telegram permits
   `maez_authored_public_third_party_transport`, permits non-private spans,
   and blocks owner-message/memory/bonded-context spans by default.
5. **Audience mismatch.** Public-origin transport to bonded-owner route and
   owner-origin transport to public route block unless a reviewed re-addressing
   path is explicitly invoked.
6. **Static direct-send inventory.** AST walk fails on current direct
   `bot.send_message`, `context.bot.send_message`, `_bot.send_message`,
   `reply_text`, media send, receiver-varied `edit_message_text`, typing,
   callback answers with text, callback answers without text, reactions, and
   draft-presence calls outside `core/egress/telegram_egress.py`.
7. **Adapter bypass closure.** After migration, `TelegramAdapter.send`,
   `send_voice`, `send_document`, `send_video`, `send_image`,
   `send_animation`, `send_update_prompt`, `send_exec_approval`, and
   `send_model_picker` all route through the chokepoint.
8. **Legacy voice bypass closure.** `TelegramVoice.send_message`,
   `_send_card_message`, update-handler replies, and command replies route
   through the chokepoint.
9. **Public bot bypass closure.** Public replies and owner alerts route
   through the chokepoint with explicit audience class; public-stranger replies
   and owner alerts from `skills/telegram_public.py` produce different
   route/audience envelopes.
10. **Action-engine Telegram notifications.** `ActionEngine` approval/action
    notifications reach Telegram only through the migrated Telegram
    abstraction; its external HTTP fetch route remains untouched.
11. **Runtime raw-string refusal.** Live chokepoint send APIs refuse raw text
   without envelope/provenance, except through explicitly named legacy shims
   that attach `unclassified` provenance and are not enforcement-ready.
12. **Silent local-log block.** A blocked owner-private Telegram send produces
   a local diagnostic, sends no Telegram message, and does not inject the
   diagnostic into Maez prompt/memory/dream/proposal context.
13. **Diagnostic non-reconstruction.** Diagnostics contain keyed digests and
    counts, not raw content, raw chat ids, bare chat-id hashes, tokens,
    captions, or media bytes. `chat_id_digest` uses `hmac-sha256:`.
14. **Transport control coverage.** Typing/draft/reaction controls are either
    routed through the chokepoint as content-free events or explicitly
    inventoried as non-content transport controls; callback answers with
    `text=...` and no-arg callback acknowledgements are both covered; raw text
    cannot hide in metadata.
15. **No screen-perception false producer.** The inventory does not classify
    `skills/screen_perception.py` as a Telegram egress producer unless a real
    Telegram send call appears there.
16. **Interactive markup coverage.** `send_exec_approval(...)` and
    `send_model_picker(...)` expose button labels and callback data through
    typed envelope fields, not opaque metadata.
17. **URL media fallback discipline.** Migrated Telegram sends do not perform
    untracked direct `httpx` or `requests` external media fetches. The current
    `TelegramAdapter.send_image(...)` URL download fallback must be disabled,
    routed through a reviewed external-fetch gate, or inventoried separately
    before merge.
18. **Telegram call-class policy target.** `decide_egress(...)` handles
    `owner_third_party_transport_send` and
    `public_third_party_transport_send`; current-code tests fail because these
    call classes are `unknown_call_class`.
19. **Existing cloud paths unchanged.** claude-router cloud-as-tool remains
    routed through the subscription proxy; fast-backend cloud remains retired;
    this slice does not reopen cloud egress.
20. **Fresh live canary discipline.** Live verification snapshots Telegram
    diagnostic max id / log size before canaries and asserts only new rows,
    never reuses old row ids or historical evidence.

## Acceptance Bar

Implementation is accepted only after:

- All RED tests fail before implementation for the expected reasons.
- Focused Telegram egress tests pass.
- Existing egress/routing/proxy tests remain green within known baseline.
- Static bypass inventory has zero unapproved production direct-send hits.
- Owner-private canary sends a safe message through the chokepoint.
- Owner-private memory canary allows owner-context memory to the bonded owner.
- Public-stranger canary sends a safe public message through the chokepoint.
- Owner-private reserved-denied canary blocks with local diagnostic and no
  Telegram send.
- Public-stranger owner-context canary blocks with local diagnostic and no
  Telegram send.
- Owner alert from `skills/telegram_public.py` is routed according to the actual
  owner-private token identity when it uses `MAEZ_TELEGRAM_TOKEN`.
- Interactive approval/model-picker markup is covered by the envelope and cannot
  hide labels or callback payloads in opaque metadata.
- Callback answers with text, callback acknowledgements without text, reactions,
  edits, media sends, typing, and draft presence are covered by the static
  bypass inventory.
- Migrated Telegram sends do not perform untracked direct URL media downloads.
- Diagnostics contain no raw canary text, raw chat id, bot token, or media
  bytes.
- Existing claude-router cloud canary still produces a fresh proxy span-bundle
  row.
- Fast-backend cloud remains retired with zero new
  `fast_backend_cloud/generate` rows.
- `docs/slices/privacy-egress-gate/network_migration_allowlist.yaml` updates
  Telegram from `unmigrated` to the correct post-slice state, without claiming
  `action_engine_external_fetch` is migrated.

## Inventory State

Current allow-list entry:

```yaml
path: skills/surface/telegram_adapter.py
surface: telegram
status: unmigrated
```

Target after implementation:

```yaml
path: skills/surface/telegram_adapter.py
surface: telegram
status: chokepoint_shadow_or_enforced
```

The exact status value should match the implementation posture. If the first
implementation runs shadow-only, the status must say shadow and the acceptance
bar must not claim enforcement. If fail-closed Telegram enforcement is live,
the status must say enforced/migrated. Either way, direct-send bypasses must be
closed.

Do not change:

```yaml
path: core/actions/action_engine.py
surface: action_engine_external_fetch
status: unmigrated
```

Action-engine Telegram notifications are in this slice. Action-engine external
HTTP fetches are not.

## Evidence Required For Review

Spec review must answer:

- Does the new origin class preserve etiology instead of category-drifting
  public Telegram into owner Telegram?
- Does the policy table treat public-stranger recipients more conservatively
  than bonded-owner recipients?
- Does the static AST bypass test inspect real production call sites, not
  runtime callables that lambdas/wrappers can evade?
- Does the runtime guard remain mechanism-agnostic until implementation traces
  `python-telegram-bot` seams?
- Does the spec keep bot identity separate from audience identity?
- Does it route `telegram_public.py` owner alerts by actual token identity, not
  by module name?
- Does it cover both sync and async Telegram sends?
- Does it cover interactive markup, callback answers, reactions, and
  receiver-varied edits?
- Does it prevent direct URL media fallback from becoming an untracked external
  HTTP fetch?
- Does it keep watchdog-style diagnostics out of Maez's own cognition by
  default?
- Does it avoid claiming `action_engine_external_fetch` is migrated?

## Non-Goals

- No Telegram product redesign.
- No deletion of legacy TelegramVoice in this slice.
- No public-bot memory policy redesign.
- No linked-user/family/caretaker taxonomy.
- No Telegram media-content semantic classifier.
- No global egress enforcement flip.
- No OS/network firewall enforcement.
- No memory deletion or mutation policy change.
- No change to the watchdog.
- No change to cloud-as-tool.

## Build Path

Full ladder:

1. Draft this spec.
2. Claude council review.
3. Codex engineering panel review.
4. Fold amendments.
5. Canonicalize v1.
6. Separate RED-first implementation slice in an isolated worktree.
7. Both-lane implementation review.
8. Merge and deliberate observed restart.
9. Live Telegram canaries.
10. Producer-side provenance threading follow-up.

No code before canonicalization.

## Plain-Language Summary

Telegram is Maez talking through someone else's road. The owner-private road and
the public-stranger road are not the same road. This spec puts one guard booth
in front of every Telegram send, gives the public road its own honest source
label, and makes tests fail if any code tries to sneak around the booth.
