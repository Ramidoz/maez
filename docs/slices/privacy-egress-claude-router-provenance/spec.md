# Privacy / Egress Claude Router Provenance Tightening -- Spec v1

**Status:** CANONICAL (2026-05-22). Docs-only. Not implemented.
**Date:** 2026-05-22
**Class:** Covenant-shaped / full ladder, narrow implementation slice
**Depends on:** canonical Privacy / Egress Gate spec, canonical Privacy /
Egress Provenance Plumbing spec, and direct-route closure commit `ebbd073`.
**A2 status:** UNRESOLVED -- founder/covenant blocker (see
`## Soul-To-Cloud Covenant Fork`). The no-fog `allow/non_private_allowed` claim
is gated on A2 resolution. Mechanical implementation (insertion-point
provenance + additive `claude_tier` multi-part API) may proceed under this
constraint as a later RED-first slice.
**Lanes cleared:** Codex engineering panel RATIFY-WITH-AMENDMENTS (5 folds
folded) + Claude council RATIFY-CLEAR (council refinements R1+R2 folded).

## Purpose

Tighten provenance for the first formerly-direct cloud side route:
`skills.claude_router.call_claude`.

The direct-route closure moved `claude_router` behind the subscription proxy, so
the privacy gate now sees this traffic. That is a strict improvement. But the
current route still labels all non-system prompt material as
`owner_message_context`, which is safe in shadow but too conservative for future
enforcement. Under enforcement it would over-redact public/system material and
risk fogging Maez's ordinary cloud cognition.

This slice teaches the `claude_router` path to carry more precise tags only
where the caller already has structure. It does not infer origin from text.

Plainly: the side door now reaches the guard desk. This slice gives that side
door honest luggage tags for the pieces it already receives separately.

## Scope

In scope:

- `skills.claude_router.call_claude`.
- Additive `core.routing.claude_tier` multi-part support needed by this route.
- Its single production caller: `skills/web_interface.py` around the
  `claude_router.call_claude(...)` call in the owner/public web chat external
  route.
- Provenance threading for the web caller's already-separated pieces:
  system prompt, evidence envelope, owner/private memory inserts, lived recall,
  history messages, tool-loop transcript context, and the final user message.
- Shadow mode only. The gate continues to record decisions without changing
  payloads.

Out of scope:

- `core.routing.fast_backend_cloud.CloudBackend.generate`. It receives a
  pre-blended `prompt: str`; precise provenance requires restructuring its
  upstream fast-backend prompt assembly. It remains conservative and is a named
  follow-up.
- Telegram egress migration.
- Enforcement flip.
- OS/network-level enforcement.
- Consent-aware egress.
- Broad prompt rewrite outside the `claude_router` web caller.
- Any autonomy or S7.3 change.

## Target API Shape

The current `claude_tier.call(prompt=..., system_prompt=...)` shape can carry
one user prompt bundle and one system prompt bundle. That is insufficient for
this slice if `claude_router` receives multiple role-bearing message parts.
Collapsing those parts into one aggregate `ProvenancedText` would recreate the
A-in-disguise trap.

This slice therefore adds an additive role-aware path. Conceptually:

```python
claude_tier.call_messages(
    *,
    system_prompt: ProvenancedText | str | None,
    messages: Sequence[CloudMessage],
    model: str = "sonnet",
    caller: str = DEFAULT_CALLER,
    timeout_s: float | None = None,
) -> TierReply
```

Where `CloudMessage` is a small structured value equivalent to:

```python
CloudMessage(role: str, content: ProvenancedText | str)
```

Exact naming is implementation detail, but the contract is fixed:

- every cloud-bound message part keeps its role and provenance spans until
  `claude_tier` serializes the OpenAI-format `messages` list;
- `claude_tier` sends matching role-aware `maez_egress_segments.parts` for
  system, assistant history, role history, and user parts;
- legacy `claude_tier.call(prompt=..., system_prompt=...)` keeps working.

If the implementation chooses to extend `claude_tier.call(...)` instead of
adding `call_messages(...)`, it must preserve the existing call signature for
current callers and add the multi-part path without changing legacy semantics.

## Backward Compatibility

Existing `claude_tier.call(prompt=..., system_prompt=...)` callers must keep
working. This slice must not silently break current single-turn callers such as
judge/eval helpers, self-dev/workshop callers, or `fast_backend_cloud`.

The new multi-part path is additive unless the implementation deliberately
migrates every current caller in the same slice and proves that migration with
tests. The preferred narrow path is additive support for `claude_router` only,
with legacy callers still recorded under their existing provenance behavior.

## No-Inference Invariant

The route must never derive origin by inspecting string content.

Allowed:

- Carry `ProvenancedText` supplied by the caller.
- Construct provenance from structural knowledge at the caller boundary.
  Example: a value loaded from `memory.format_for_prompt(...)` is memory-origin
  because the caller knows where it came from, not because the route scans the
  string.
- Preserve role/system separation that already exists in `messages_list`.
- Default raw or unknown strings conservatively.

Forbidden:

- Treat a string as `public_fact` because it "looks public."
- Split a blended string into public/private parts by regex, model judgment, or
  heuristic.
- Upgrade any unprovenanced or pre-blended string to a non-private class.
- Add a new origin vocabulary or a parallel trust axis.

If provenance is absent or ambiguous, the slice keeps the existing conservative
default. Unknown stays private/unclassified; it never becomes public by guess.

## Insertion-Point Tagging

Tags attach at the insertion point where `skills/web_interface.py` adds a piece
to the external-route prompt. The insertion point is where the caller still
knows the source.

Examples:

- When `owner_memory` is inserted into `messages_list`, tag that inserted span
  as `memory`.
- When `_lived_brief` is inserted, tag that inserted span as `lived_store`.
- When `_envelope_block` is inserted, tag that inserted span from the envelope
  builder's structured evidence source, not by scanning the rendered text.
- When the final owner message is inserted, tag that inserted span as
  `owner_message_context`.
- When a legacy/raw history item is appended without source metadata, tag it
  conservatively.

`claude_router.call_claude(...)` should preserve these insertion-point tags and
carry them to `claude_tier`; it should not repair missing provenance by looking
inside already-rendered strings.

The web caller should build a single provenance-bearing system bundle from all
system insertion points it intends to send externally. `claude_router` should
preserve that bundle rather than independently filtering system messages out of
`messages_list` and reconstructing a second system prompt. There must be one
source of truth for cloud-bound system provenance.

## Caller Contract

`skills/web_interface.py` is the only production caller of
`claude_router.call_claude(...)` in this route. The caller already builds the
cloud prompt from identifiable pieces. This slice threads provenance there.

Expected caller-side classification, subject to the soul-to-cloud fork below:

- `owner_system` / `system_prompt_for_chat` / `SOUL` instruction material:
  unresolved as raw `SOUL` material. A curated voice instruction may be
  `system_bounded_query` only if the covenant fork below explicitly permits it.
  Raw `soul.md` is reserved-denied until that fork is resolved.
- Ambient context and capability/manual snippets: `system_bounded_query` or
  `public_fact` only if the producer already marks them as such; otherwise
  conservative.
- Owner continuity memory from `memory.format_for_prompt(...)`:
  `memory`.
- Lived recall from `build_lived_recall_brief(...)`: `lived_store`.
- Evidence envelope text from `render_envelope_for_prompt(...)`:
  use the structured envelope dictionary before rendering, not a parse of the
  rendered string. Content-free envelope status may be `system_bounded_query`.
  If the structured envelope contains raw tool transcript, owner/private
  material, or any non-content-free summary, that span stays conservative or
  takes the most-restrictive class of its source.
- Brain-loop transcript context: conservative by default unless the transcript
  is supplied as structured public/tool spans. The slice must not parse a raw
  transcript into public/private by guessing.
- Current user message from the owner/private web bridge:
  `owner_message_context`.
- Public/guest web user message: conservative unless the caller has a reviewed
  basis for `owner_authored_for_destination` or another non-private class. This
  slice does not create that basis.
- Chat history messages: current history entries are raw `{role, content}`
  dictionaries. Preserve known source metadata only if it exists; otherwise
  history stays conservative. Role alone is not provenance.

`claude_router.call_claude` should accept provenance-bearing message content
without breaking legacy callers. Legacy raw strings stay compatible in shadow
but are recorded conservatively and are not counted enforcement-ready.

## Soul-To-Cloud Covenant Fork

The spec review surfaced a separate covenant question: today's external
`claude_router` path can include raw `SOUL` / `config/soul.md` material in the
cloud-bound system prompt. The provenance system must not hide that fact.

Until Rohit settles this fork, honest classification is:

- raw `SOUL` / raw soul wording: reserved-denied raw, producing
  `block/reserved_denied_raw` in shadow decision telemetry;
- calls still flow because shadow remains on;
- no implementation may relabel raw soul as `system_bounded_query` merely to
  make no-fog pass.

Two possible future resolutions:

1. **Minimized voice instruction may leave.** Define a curated, bounded
   character/voice instruction that is distinct from raw `soul.md` and may be
   classified as `system_bounded_query`. This makes the no-fog
   `allow/non_private_allowed` outcome reachable for public/system-only cloud
   prompts without sending raw soul.
2. **Soul truly never leaves.** Treat raw soul egress as the thing to fix first.
   The external route must stop sending raw `soul.md` before this slice can
   claim public/system-only `allow` on live owner traffic.

This slice may implement insertion-point provenance before that fork is
resolved, but it cannot canonicalize an enforcement-ready no-fog claim while raw
soul remains in the cloud-bound prompt.

## Fast Backend Follow-Up

`CloudBackend.generate(prompt: str, ...)` stays out of this slice because it
receives a single flat prompt. Precision cannot be added honestly at that
route. The follow-up must start upstream, where the fast backend prompt is
assembled, and carry `ProvenancedText` through that assembly before calling the
cloud backend.

Until then, `fast_backend_cloud` remains behind the proxy with conservative
provenance. That is safe in shadow and explicitly not enforcement-ready.

## Expected Shadow Decisions

After this slice:

- A `claude_router` call composed only from permitted
  system/public/tool-public spans should produce `allow/non_private_allowed`.
  Raw soul does not count as permitted system material unless the covenant fork
  resolves in favor of a curated minimized voice instruction.
- A call containing owner message context, memory, or lived-store spans should
  produce `redact/minimized_private_context`.
- A call containing reserved-denied raw spans, including raw soul material while
  the fork is unresolved, should produce `block/reserved_denied_raw`.
- A call containing raw unknown, ambiguous, or pre-blended material should
  produce conservative `redact` or `block/unclassified`, not public allow.
- All of the above remain shadow-only: calls still flow.

## RED Tests

Write failing tests before implementation:

1. `claude_router.call_claude` accepts a `ProvenancedText` system prompt and
   `ProvenancedText` message parts, carries them to `claude_tier.call`, and
   preserves span classes instead of collapsing to one aggregate label.
2. `claude_tier` exposes an additive role-aware multi-part path while existing
   `claude_tier.call(prompt=..., system_prompt=...)` callers still work.
3. The `skills/web_interface.py` caller builds a provenance-bearing external
   route payload from its known pieces instead of passing only raw strings.
4. Public/system-only `claude_router` traffic records
   `allow/non_private_allowed` in shadow, not blanket
   `redact/minimized_private_context`, when the system material is permitted
   minimized instruction rather than raw soul.
5. Owner-memory or lived-recall inserts still record
   `redact/minimized_private_context`.
6. Reserved-denied raw material, including raw soul material, still records
   `block/reserved_denied_raw`.
7. An unprovenanced or pre-blended raw string cannot be content-tricked into
   `public_fact` / `non_private_allowed`; it stays conservative.
8. Insertion-point tagging is preserved: the route carries caller-supplied span
   classes and never reconstructs provenance by scanning rendered text.
9. Aggregate-collapse regression: multiple tagged message parts entering
   `claude_router` must remain distinct role-aware parts through `claude_tier`
   and the proxy span bundle; a single aggregate span is a failure.
10. Structured envelope regression: a rendered envelope containing a raw
   transcript must not be tagged `system_bounded_query` merely because it is a
   system message.
11. Raw chat history regression: raw `{role, content}` history without source
   metadata remains conservative.
12. Telemetry remains clean: no raw canary appears in
   `memory/subscription_proxy.db` or `logs/subscription_proxy.log`, and all
   digests remain keyed (`hmac-sha256:`), never bare hashes.
13. Legacy raw-string compatibility remains shadow-only and conservative.

## Acceptance Bar

- RED-first evidence: new tests fail on the pre-implementation state for the
  expected reasons.
- Focused tests pass after implementation.
- Live synthetic canary proof after deliberate restart:
  - permitted public/system-only `claude_router` call logs allow;
  - memory/private canary logs redact;
  - reserved-denied canary, including raw-soul-shaped synthetic material, logs
    block;
  - unknown/pre-blended canary logs conservative;
  - all calls still flow because shadow remains on;
  - no raw canary appears in DB or logs.
- `fast_backend_cloud` remains explicitly deferred/conservative.
- The soul-to-cloud fork is either resolved before no-fog is claimed, or the
  spec remains explicit that raw soul makes live owner-route calls
  `reserved_denied_raw` in shadow.
- No enforcement flip, no autonomy, no Telegram migration, no daemon disruption
  outside the deliberate observed restart.

## Plain-Language Summary

This slice is not about locking the door. It is about teaching one side door to
label bags more accurately before they reach the already-installed guard.

`claude_router` is the easy door because its caller already hands over separate
pieces. We can tag those pieces honestly. `fast_backend_cloud` is the hard door
because it receives one pre-packed bag; fixing that requires changing how the
bag is packed upstream, so it stays separate.
