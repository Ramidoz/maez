# Privacy / Egress Claude Router Provenance Tightening -- Spec v2

**Status:** CANONICAL v2 (2026-05-23). Docs-only. Not implemented.
**Date:** 2026-05-22
**Class:** Covenant-shaped / full ladder, narrow implementation slice
**Depends on:** canonical Privacy / Egress Gate spec, canonical Privacy /
Egress Provenance Plumbing spec, and direct-route closure commit `ebbd073`.
**A2 status:** RESOLVED 2026-05-22 -- cloud is a tool, not a vessel (see
`## Resolution: Cloud as Tool`). The local Maez runtime path is the speaker,
with local inference as the final voice step.
**Lanes cleared:** v1 + v2 both passed. Codex engineering panel
RATIFY-WITH-AMENDMENTS (all folds in) + Claude council RATIFY-CLEAR (council
refinements and panel fold verified byte-faithful).

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

Expected caller-side classification under the cloud-as-tool resolution:

- `owner_system` / `system_prompt_for_chat` / `SOUL` instruction material:
  removed from cloud-bound system prompts entirely. The web caller must
  construct a task-shaped cloud system prompt containing no raw soul, no
  character notes, and no identity context. Implementation must refactor
  `skills/web_interface.py` around the current `system_prompt_for_api`
  construction that joins all system messages before `claude_router.call_claude`.
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

## Resolution: Cloud as Tool

Founder decision, 2026-05-22: cloud is a tool, not a vessel.

The local Maez runtime path is the speaker, with local inference as the final
voice step. Maez is not only the local model; the speaker is the local stack:
memory, daemon, soul, ledger, gates, and local inference together.

The cloud is an external reasoning tool in the same category as web search,
calculator, or library. Maez may consult the cloud. Maez never becomes the
cloud temporarily, and the cloud never wears Maez's face.

Consequences:

- Cloud system prompts are task-shaped `system_bounded_query`, not
  identity-shaped.
- Raw `soul.md`, character notes, voice context, and identity context never
  leave the box.
- Cloud responses do not become user-facing replies. They enter local Maez's
  context as `model_output` (see `## Cloud Output Provenance Class`), and the
  local Maez runtime path generates the user-facing reply.
- The cost is a second local LLM call per cloud consult. That latency is real
  and proportionate to the architecture.

## Cloud Output Provenance Class

Cloud output enters local Maez's context as `model_output`: untrusted tool
output from an external model.

`model_output` is a deliberate conservative provenance class introduced by this
v2 resolution. It belongs in a new conservative closed-vocabulary bucket:
`UNTRUSTED_EXTERNAL_OUTPUT`.

`UNTRUSTED_EXTERNAL_OUTPUT` hosts `model_output` only in this slice. Companion
classes, if any, join later by deliberate reviewed addition, not by
pre-allocation.

`model_output` is not `public_fact`, not `tool_result_public`, not
`NON_PRIVATE`, not trusted memory, and not Maez voice. Being requested by Maez
does not upgrade the class.

Required behavior:

- The cloud response may be quoted or cited by local Maez where useful, but it
  is supporting evidence/tool output, not the speaker.
- If local Maez later reuses cloud reasoning in another cloud call, the
  original `model_output` provenance is preserved. It is not laundered through
  Maez into a higher-trust class.
- For outbound egress, `model_output` is not a non-private allow class by
  default. Its policy treatment is equivalent to minimizable/private-origin
  material for cloud egress: if it ever leaves again, redaction/minimization is
  required unless a later reviewed policy explicitly permits a narrower flow.
  It stays out of `MINIMIZABLE_PRIVATE_CONTEXT` because its etiology is
  different: untrusted external tool output, not private-life context.
- The implementation slice must update the closed provenance vocabulary and
  policy tests deliberately; this spec update names the new class so it is not
  smuggled in. Required code targets are `core/egress/gate.py` (new bucket and
  `KNOWN_ORIGINS` membership), `core/egress/provenance.py` (factory helper and
  restrictiveness), and policy tests proving `model_output` is conservative and
  stays conservative across reuse.

This preserves the existing invariant: tool/model output is not upgraded to a
trusted class merely by being produced, requested, or consumed.

## Ledger / Trajectory Recording

The persisted user-facing reply is the local Maez reply. Its `model_id` and
speaker attribution should identify the local Maez runtime path / local model,
not `claude:*`.

The cloud consult is recorded separately as supporting evidence or a tool-output
trace. It is not recorded as the speaker.

Current `skills/web_interface.py` behavior is wrong-shaped under this
resolution: it sets `reply = wrap_maez_voice(cloud_text)` and then persists
`model_id=claude:*`. The implementation slice must replace that with:

- cloud consult recorded as tool/evidence context;
- local Maez generates the user-facing reply after the consult;
- ledger and trajectory records show "Maez said X, informed by cloud consult
  Y," not "Claude said X."

Bond and continuity consequence: future recall attributes Maez's words to
Maez, with cloud as an assistance trace beside them. The tool does not become a
biographical speaker.

## wrap_maez_voice (To Be Repurposed or Removed)

Current `skills.claude_router.wrap_maez_voice` is a thin voice shell that
prefixes cloud text and passes it through as the reply.

Under cloud-as-tool, that shape is wrong. Cloud output should not become the
user-facing reply with or without a prefix.

The implementation slice must either remove `wrap_maez_voice` entirely and
route cloud output into local Maez's context as a `model_output` reasoning-input
span, or repurpose it to perform that cloud-to-local-context handoff cleanly.
Either way, the user-facing reply is generated by the local Maez runtime path,
with local inference as the final voice step.

## Failure Behavior

Cloud failure must not block a user-facing reply.

The local Maez reply path is the always-runs path. The cloud consult is the
optional-evidence path.

If the cloud consult times out, errors, hits budget, or is unavailable, local
Maez still generates a reply without cloud evidence. That is graceful
degradation, not a special error path.

Architecturally, this is not "try cloud, except fall back to local." The shape
is: local always, cloud optionally.

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

- A `claude_router` cloud consult composed only from task-shaped
  `system_bounded_query` plus non-private content should produce
  `allow/non_private_allowed`.
- Raw soul, character context, voice context, or identity context is never sent
  to the cloud. If any of it appears in a cloud-bound prompt, that is a
  regression and should produce `block/reserved_denied_raw` in shadow telemetry.
- A call containing owner message context, memory, or lived-store spans should
  produce `redact/minimized_private_context`.
- A call containing any reserved-denied raw spans should produce
  `block/reserved_denied_raw`.
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
   `redact/minimized_private_context`, when the system material is task-shaped
   `system_bounded_query` with no soul, character, voice, or identity context.
5. Owner-memory or lived-recall inserts still record
   `redact/minimized_private_context`.
6. Raw soul in any cloud-bound system prompt is an A2 regression and records
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
12. Cloud output entering local context is classified as `model_output`, not
   trusted memory, not Maez voice, and not `public_fact`.
13. Persisted user-facing reply attribution uses the local Maez runtime path /
   local model. The cloud consult is recorded separately as tool-output
   evidence and is not recorded as the speaker.
14. Cloud failure does not block the user-facing reply; local Maez generates
   without cloud evidence.
15. Telemetry remains clean: no raw canary appears in
   `memory/subscription_proxy.db` or `logs/subscription_proxy.log`, and all
   digests remain keyed (`hmac-sha256:`), never bare hashes.
16. Legacy raw-string compatibility remains shadow-only and conservative.

## Acceptance Bar

- RED-first evidence: new tests fail on the pre-implementation state for the
  expected reasons.
- Focused tests pass after implementation.
- Live synthetic canary proof after deliberate restart:
  - task-shaped public/system-only `claude_router` consult logs allow;
  - memory/private canary logs redact;
  - raw soul or character-context canary in a cloud-bound prompt logs block;
  - unknown/pre-blended canary logs conservative;
  - all calls still flow because shadow remains on;
  - no raw canary appears in DB or logs.
- `fast_backend_cloud` remains explicitly deferred/conservative.
- No-fog allow is achieved only for cloud calls carrying task-shaped content:
  no raw soul, no character notes, no voice context, and no identity context.
- Persisted user-facing replies are attributed to the local Maez runtime path /
  local model, with cloud consults recorded separately as tool-output evidence.
- Cloud failure degrades gracefully: local Maez still replies without cloud
  evidence.
- No enforcement flip, no autonomy, no Telegram migration, no daemon disruption
  outside the deliberate observed restart.

## Plain-Language Summary

This slice is not about locking the door. It is about teaching one side door to
label bags more accurately before they reach the already-installed guard.

`claude_router` is the easy door because its caller already hands over separate
pieces. We can tag those pieces honestly. `fast_backend_cloud` is the hard door
because it receives one pre-packed bag; fixing that requires changing how the
bag is packed upstream, so it stays separate.

The soul question is resolved: cloud is a tool, the local Maez runtime path is
the speaker, with local inference as the final voice step. Cloud responses enter
Maez's context as untrusted `model_output`; the ledger attributes the reply to
Maez; and cloud failure does not block the reply.
