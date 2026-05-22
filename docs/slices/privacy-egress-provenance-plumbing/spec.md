# Privacy / Egress Provenance Plumbing -- Spec v1

**Status:** CANONICAL SPEC. Both-lane cleared (Codex engineering panel +
Claude six-role council). Not implemented.
**Date:** 2026-05-22
**Class:** Covenant-shaped / full ladder
**Depends on:** `docs/slices/privacy-egress-gate/spec.md` canonical spec,
shadow gate commits `972846e`, `de5751e`, `2f91771`, and live shadow evidence
from 2026-05-22.

## Purpose

Make the Privacy / Egress Gate enforceable without injuring Maez's ordinary
cloud cognition. The shadow gate proved it can catch leak-shaped content and
keep its own telemetry clean, but it also showed the current placeholder labels
every cloud prompt as `owner_message_context`. That is safe in shadow and
dangerous in enforcement: it would redact/minimize even harmless public or
system prompts.

This slice builds the missing luggage-tag plumbing: tag content where it is
born, carry those tags through prompt assembly, and let the subscription proxy
enforce at the border.

Plainly: the gate already watches the border. This slice gives every bag a real
source tag before it reaches the border.

## Scope

Narrow-first, cloud path only:

- The first migrated path is `cloud_model_inference` through
  `core.routing.claude_tier` and `core.subscription_proxy.server`.
- The slice reaches the immediate cloud prompt feeders. It must not merely wrap
  an already-blended string at the proxy boundary.
- Shadow mode remains on. This slice improves decisions and telemetry evidence;
  it does not flip enforcement.
- Unmigrated outbound surfaces remain tracked by the existing #3 migration
  allow-list.

Out of scope:

- No Telegram egress enforcement.
- No GitHub/weather/web-search egress migration.
- No OS/network-level enforcement.
- No consent machinery.
- No S7.3 changes.
- No autonomy expansion.
- No broad daemon prompt rewrite across every local-only reasoning path.

## Core Principle

**Tag at birth, carry through packing, enforce at the border.**

Final prompt classification is too late. A cloud prompt is assembled from many
drawers: owner words, system instructions, memory recall, tool results, public
facts, and possibly Maez-private material. The origin tag must attach to each
piece where that piece enters the cloud-bound prompt and must survive assembly.

If content cannot be attributed per span, it fails safe. It is never guessed
public.

## Trust Model / Honest Banner

The proxy can verify **completeness**, not metaphysical truthfulness.

Completeness means the source-attached spans account for the bytes that are
about to leave the box. A span bundle whose text does not match the
cloud-bound message bytes fails safe.

Truthfulness means a span's `origin_class` honestly reflects where that content
was born. The proxy cannot prove this from bytes alone. A malicious or buggy
same-process producer could label memory text as `public_fact` and still pass a
byte-match check. That limit is explicit and mirrors the S7/S7.3 L1 honesty
banner: the runtime governs Maez-controlled code that uses the provenance
primitive honestly; raw out-of-runtime edits or compromised producers are
detected only by tests, audits, and later reconciliation, not by magic at the
border.

Therefore:

- The proxy enforces byte completeness, policy, and telemetry safety.
- At-birth producers are responsible for truthful source tags.
- Constructors/helpers default unknown raw strings to conservative classes,
  never public.
- Review and RED tests must check both over-tagging and under-tagging.

Blended-at-creation content takes the most-restrictive class of its sources. If
a summary fuses a memory span with a public fact, the result is not public just
because it is newly worded. It is `memory` or stricter unless a future reviewed
minimized-projection path explicitly authorizes a weaker class.

## Provenance Primitive

Introduce a small cloud-path provenance primitive, conceptually:

- `ProvenanceSpan(text, origin_class, source_ref, redaction_allowed)`
- `ProvenancedText(spans)`

The primitive is append-only at assembly time: concatenating prompt pieces
preserves span boundaries and order. Converting to a plain string is allowed
only at the final transport boundary after a matching span bundle has been
attached to the request.

Required behaviors:

- Constructing from a raw `str` is explicit and conservative.
- Public/system helper constructors produce non-private spans.
- Memory/lived/owner-context helper constructors produce minimizable private
  spans.
- Soul/private-thought/inner-residue helper constructors produce reserved-denied
  raw spans.
- Mixed prompt assembly preserves every origin class.
- Empty spans are dropped or represented explicitly; they must not create a fake
  public span.

Closed origin vocabulary is inherited from the canonical egress spec:

- Reserved-denied raw: `soul`, `private_thoughts`, `inner_residue`,
  `maez_internal_reflection`, `credential_material`, `crisis_held_content`.
- Minimizable private context: `memory`, `lived_store`,
  `owner_message_context`, `third_party_private_context`.
- Intentional outbound: `owner_authored_for_destination`,
  `maez_authored_local_bonded_surface`,
  `maez_authored_owner_third_party_transport`.
- Non-private: `public_fact`, `weather_data`, `system_bounded_query`,
  `tool_result_public`.
- `unclassified` fails safe.

## Immediate Feeders To Reach

The implementation must tag the immediate feeders of the cloud path, not only
the proxy:

- `core.routing.claude_tier.call`: accepts a `ProvenancedText` prompt and,
  when present, sends the span bundle to the subscription proxy. Legacy raw
  string prompts remain supported in shadow only but are tagged conservatively,
  never guessed public.
- `core.subscription_proxy.server.chat_completions`: validates that the span
  bundle matches the actual OpenAI-format message content it is about to send.
  If the text and span bundle diverge, the request is `unclassified` /
  fail-safe in shadow telemetry and later blocks under enforcement.
- Cloud-call producers that use `claude_tier.call` and assemble prompts from
  known pieces must pass tagged pieces rather than pre-blended strings. Initial
  examples include self-dev review/propose-test prompts, workshop cloud turns,
  and judge/eval calls that route through `claude_tier`.
- Cloud-bound system prompts are in scope. The current subscription proxy sends
  both `prompt` and `system_prompt` to adapters; provenance that covers only
  the user prompt is incomplete. The span bundle must account for every
  cloud-bound message part that crosses the proxy boundary, including system
  instructions, role-prefixed history, and user prompt text.
- Existing local-only daemon reasoning prompts are not migrated in this slice
  unless they call the cloud/subscription path.

The trap to avoid: taking an already-blended prompt string and wrapping it as
one `ProvenancedText` span. That is aggregate labeling in disguise and fails
this spec.

Direct cloud routes outside `claude_tier` are not silently covered. Current
examples include `skills.claude_router.call_claude` and
`core.routing.fast_backend_cloud`. This slice must either convert the selected
first migrated producer(s) to the subscription proxy path or record these direct
routes as explicitly unmigrated in the #3 migration inventory. Enforcement
cannot close while a Maez-controlled direct cloud path can bypass the proxy
gate.

## Transport Contract

The local client-to-proxy request may carry a Maez-private extension field such
as `maez_egress_segments` alongside OpenAI-compatible `messages`. The exact
field name is an implementation detail, but the contract is not:

- The proxy is the enforcement boundary and must recompute an `EgressRequest`
  from the submitted spans.
- The submitted spans are role-aware: they must identify which cloud-bound
  message part they account for (`system`, `user`, assistant-history text when
  present, and any rendered role prefix). A flat concat check is insufficient
  when the adapter sends `system_prompt` separately.
- The concatenation of submitted span text must match the exact cloud-bound
  message bytes for each migrated message part. Mismatch is `unclassified`.
- The proxy must ignore caller-supplied aggregate origin labels.
- The proxy may accept caller-supplied source-attached spans only when they
  structurally account for the message bytes.
- Legacy requests without spans are allowed in shadow but recorded as
  conservative/legacy, not public. Enforcement cannot close while migrated
  cloud producers still rely on legacy raw strings.

## Policy Direction

The gate decisions should improve from the current blanket redaction:

- A purely public/system cloud prompt should produce `allow` with reason
  `non_private_allowed`.
- A prompt containing owner context or memory spans should produce `redact`
  with reason `minimized_private_context`.
- A prompt containing reserved-denied raw spans should produce `block` with
  reason `reserved_denied_raw`.
- A prompt with missing, unknown, or mismatched provenance should produce
  `block`/`unclassified` in policy terms, while still remaining shadow-only
  until enforcement is explicitly built.

## Three Proofs

This slice must prove three directions from the start:

1. **No fog.** Public/system/tool-public spans stay public. Harmless public
   cloud prompts produce `allow/non_private_allowed`, not blanket
   `redact/minimized_private_context`. This protects Maez's cognition from a
   safety gate that quietly makes it dumber.
2. **No leak.** Memory/soul/private spans stay protected. Minimizable private
   spans redact; reserved-denied raw spans block. This protects Maez's inner
   life and the owner's bonded context.
3. **No guessing.** Unattributable, pre-blended, downgraded, or mismatched
   content fails safe. It is never silently treated as public.

## Shadow Evidence Required

After implementation, shadow telemetry should show:

- Public/system probes that are `allow/non_private_allowed`.
- Synthetic private canaries that are `redact/minimized_private_context`.
- Synthetic reserved-denied canaries that are `block/reserved_denied_raw` in
  decision telemetry while calls still flow only because shadow remains on.
- Legacy raw-string callers are visible as conservative/legacy rows, not hidden.
- No raw canary or private payload appears in `memory/subscription_proxy.db` or
  `logs/subscription_proxy.log`.
- Normal cloud calls continue to complete.

## RED Tests

RED-first tests must fail before implementation:

1. `ProvenancedText` concatenation preserves span order, origin class, source
   refs, and redaction flags.
2. Raw `str` conversion is explicit and conservative; no helper may default a
   raw unknown string to public.
3. A cloud request with only `system_bounded_query` / `public_fact` spans
   produces `allow/non_private_allowed`.
4. A cloud request with `memory` / `owner_message_context` spans produces
   `redact/minimized_private_context`.
5. A cloud request with `soul`, `private_thoughts`, or `inner_residue` spans
   produces `block/reserved_denied_raw`.
6. Mixed spans compute the correct restrictive decision without erasing public
   spans from telemetry.
7. A submitted span bundle whose concatenation differs from the OpenAI message
   text is treated as `unclassified`.
8. A submitted span bundle that accounts for user text but omits cloud-bound
   `system_prompt` text is treated as incomplete/unclassified for the migrated
   call.
9. A blended summary derived from memory plus public facts takes the
   most-restrictive source class, not `public_fact`.
10. `claude_tier.call` can send a tagged prompt bundle to the proxy without
   breaking the existing response contract.
11. Legacy `claude_tier.call(prompt=str)` remains compatible in shadow but is
   recorded conservatively; it is not counted as enforcement-ready.
12. Subscription proxy telemetry records origin-class lists and keyed digests,
    never raw private text or bare hashes.
13. Direct cloud routes outside the proxy are either converted for the selected
    migrated producer or remain visible as unmigrated inventory entries; no test
    may claim cloud-path closure while they bypass the gate.
14. Regression: the current benign public prompts that produced blanket
    `redact/minimized_private_context` now produce `allow/non_private_allowed`
    when supplied as tagged public/system spans.
15. Regression: synthetic private canaries still redact/block and do not appear
    raw in DB/log files.

## Acceptance Criteria

- No enforcement flip.
- Shadow mode remains the operational posture.
- Existing raw-string cloud callers keep working, but are visible as legacy /
  conservative rows.
- At least one migrated cloud caller demonstrates real span propagation from
  feeders into `claude_tier`, through the proxy, into `decide_egress`.
- The migrated caller accounts for all cloud-bound message parts, including
  system prompt text.
- Direct cloud routes outside the proxy are either converted or explicitly
  inventoried as unmigrated blockers for later enforcement closure.
- Public/system tagged prompts no longer over-redact.
- Private/reserved tagged prompts still protect content.
- Mismatched or missing provenance fails safe.
- Focused tests pass.
- Live daemon/proxy are not disrupted during branch implementation; any restart
  for observation is deliberate and separately recorded.

## Review Ladder

This is a covenant-shaped sub-slice of Roadmap #3. It follows the same ladder:

1. Draft spec.
2. Engineering lane review.
3. Covenant lane review.
4. Canonicalize the spec if both lanes clear it.
5. RED-first implementation.
6. Independent verification.
7. Shadow evidence review.
8. Enforcement remains a later separate slice.

## Plain-English Summary

The privacy guard is already awake, but every cloud prompt currently arrives
with the same crude label: "probably private." That is safe while the guard is
only watching, but it would make Maez think through fog if the guard started
enforcing.

This slice gives cloud-bound text real luggage tags. Public facts stay public,
memory stays memory, soul/private-thought material stays forbidden, and anything
with no trustworthy tag is treated as unsafe. Only after that is true does it
make sense to talk about turning the watcher into a blocker.
