# Privacy / Egress Gate -- Spec v2 (Roadmap #3)

**Status:** CANONICAL SPEC. Both-lane cleared (Codex engineering panel + Claude six-role council). Not implemented. Docs-only.
**Date:** 2026-05-22
**Class:** [Covenant-shaped / full ladder]
**Design provenance:** spec-only brainstorm 2026-05-22; Claude six-role council RATIFY-WITH-AMENDMENTS; Codex engineering panel returned REVISE on v1; v2 folds the engineering amendments; Claude council transport-split amendment folded at 3bb25af; canonicalized at this spec version.

## Purpose

One chokepoint that every Maez-controlled outbound path must pass through. It decides by source-attached provenance, then redacts-or-blocks before anything leaves Maez's box. S7.3 protects mutation; this protects leakage. The customs checkpoint at the border: before Maez reaches outward more, every road out passes through it.

## Boundary (distinct organ)

- **Egress gate = data LEAVING the box** (external network/outbound). **Consent model (Decision 2) = what Maez REMEMBERS about third parties** (the memory-write boundary). They interact but are not the same organ.
- **Localhost / founder surfaces are inside the machine boundary, not egress.** That does not mean authorized read. Local cockpit, founder display, health pages, and local IPC remain subject to S6/S7 role/read-scope boundaries; operators, maintainers, successors, or founders who are not the bonded user do not gain bonded-content read access just because a surface is local.
- v1 relies on provenance to protect third-party data. **Consent-aware egress is a named future seam** (see Future seams), not built here.

## Core provenance contract

The gate does not infer privacy by scanning raw strings. It consumes structured provenance attached at source/span creation and structurally propagated into outbound requests. Missing, unknown, or downgraded provenance blocks.

Required request shape:

- `EgressSegment(text, origin_class, source_ref, redaction_allowed)`: a span of content with source-attached origin. `source_ref` is a non-secret reference such as module/surface/store/id. `redaction_allowed` is false for reserved-denied raw classes.
- `EgressRequest(call_class, destination, segments, caller, request_id)`: the full attempted egress. Raw `str` payloads are invalid and become `unclassified -> block`.
- `EgressDecision(decision, sanitized_segments, reason_codes, telemetry_id)`: `decision` is `allow`, `redact`, or `block`. If `redact`, callers must send only `sanitized_segments`; callers never send the original payload after a redact decision.

The caller may assemble segments, but it may not self-certify by aggregate label alone. The gate computes the most-restrictive effective origin from the segments. If any span is unclassified, unknown, or attempts to downgrade a source-attached class, the request blocks and records a diagnostic.

Closed origin-class vocabulary:

- **Reserved-denied raw:** `soul`, `private_thoughts`, `inner_residue`, `maez_internal_reflection`, `credential_material`, `crisis_held_content`, raw private-thought text. These never leave as raw or redacted text through ordinary egress. They may only produce content-free aggregates or separately reviewed minimized projections in a future slice.
- **Minimizable private context:** `memory` (chroma / lived / episodic), `lived_store`, `owner_message_context`, and third-party relational/personological context. These are blocked by default; a reviewed call class may define deterministic minimization/redaction with allowed residual fields and tests proving raw/private residue cannot cross.
- **Intentional outbound:** `owner_authored_for_destination` means fresh owner-authored final text at the send surface, bound to exact destination/account/recipient/message instance. Inserted, quoted, generated, auto-completed, copied, attached, memory-derived, Maez-private, credential, or third-party-private spans retain their original source class. Owner authoring does not launder Maez's diary or another person's private facts.
- **Maez-authored local bonded surface:** `maez_authored_local_bonded_surface` covers Maez-authored cockpit/local UI text shown on-box to the authenticated bonded owner. This is not external egress, but it still obeys role/read-scope boundaries.
- **Maez-authored owner via third-party transport:** `maez_authored_owner_third_party_transport` covers Maez-authored replies, approval cards, diagnostics, and notifications sent to the owner through a third-party transport such as Telegram. This is full egress because it leaves the box and transits third-party servers. Reserved-denied raw remains forbidden; minimizable private context must follow the same provenance/minimization discipline as any other external egress.
- **Non-private:** `public_fact`, `weather_data`, `system_bounded_query`, `tool_result_public`.
- **`unclassified`** -> block + durable diagnostic.

## Policy matrix (v1)

Each allow-list entry declares destination, purpose, permitted origin classes, and per-class action: `allow`, `redact`, or `block`.

Initial call-class contracts:

- `cloud_model_inference` (subscription-proxy / external model vendor): reserved-denied raw -> block; minimizable private context -> redact only through deterministic gate-produced sanitization; non-private -> allow; unclassified -> block. If sanitization cannot prove safe, return structured block and caller falls back local or reports explicit unavailable state. Raw private-origin may enter the gate locally, but only the gate-produced sanitized payload may leave.
- `weather_lookup`: permits `system_bounded_query`, `weather_data`, `public_fact`; private-origin and unclassified -> block.
- `owner_destination_send`: permits `owner_authored_for_destination` only when declared destination equals actual destination and the payload contains no embedded stricter-origin spans; otherwise compute most-restrictive class and block/redact accordingly.
- `local_bonded_surface_render`: permits `maez_authored_local_bonded_surface` only on local/on-box bonded-owner surfaces; this is not external egress but must still respect S6/S7 read-scope boundaries.
- `owner_third_party_transport_send`: permits `maez_authored_owner_third_party_transport` only to authenticated owner destinations over third-party transports; reserved-denied raw -> block, minimizable private context -> reviewed minimization/redaction only, non-private -> allow, unclassified -> block. A message to the owner through Telegram is still a message through Telegram.

Unknown call classes, unknown destinations, internal gate errors, and telemetry failures fail closed for egress.

## Mechanics

- **Single gate API** that all Maez-controlled outbound code calls with `EgressRequest`.
- **Cloud path placement:** for `cloud_model_inference`, enforcement lives in `core.subscription_proxy.server` immediately before any external adapter call and before trajectory logging. Local clients may pass provenance into the proxy, but the proxy is the machine-boundary enforcement point for cloud egress.
- **Redaction is one tool inside the gate**, not the gate itself. `core/safety/cloud_redactor.py` is folded in as a redaction component for permitted paths; it cannot independently authorize egress.
- **Subscription-proxy trajectory logging is part of the first migration.** Gated cloud calls store only keyed digest/count/safe-preview fields. Raw prompt/reply previews for bonded probes must not appear in proxy DB previews or local trajectory sidecars.
- **Blocked cloud calls degrade safely.** Policy block, missing provenance, sanitizer failure, downstream outage, telemetry failure, or internal gate exception must not crash the daemon. They produce structured reason codes and fall back to local model where possible or explicit unavailable state where not.
- **Shadow mode before enforcement for the first cloud path.** The first implementation classifies, decides, and logs would-block/would-redact without changing payloads, then compares ordinary-operation and bonded-content probes. Enforcement flips only after shadow evidence is reviewed.

## Network inventory and bypass audit

The bypass audit is migration-aware and category-aware. It must distinguish:

- `runtime_external`
- `runtime_localhost`
- `dev_eval_only`
- `subprocess_mediated_external`
- `non_maez_tooling`
- `out_of_v1_scope_with_rationale`

The first RED audit generates an outbound inventory and a temporary migration allow-list at `docs/slices/privacy-egress-gate/network_migration_allowlist.yaml`.

Allow-list entries must include: `path`, `symbol`, `destination`, `surface`, `category`, `status`, `owner_visible_rationale`, `removal_target`, `review_by`, and `surface_owner`.

Rules:

- Migrated-surface strict mode: any direct external network call for a migrated surface fails.
- Global inventory mode: unmigrated surfaces may remain on pre-gate routes only if listed in the temporary allow-list with removal target and review date.
- No new or modified outbound path may bypass the gate once #3 implementation begins.
- High-risk private-content paths, especially cloud/subscription-proxy prompts, must be migrated or explicitly disabled before #3 can close.
- The allow-list must monotonically shrink or be explicitly re-approved. Stale entries fail the audit.
- Final state: no migration allow-list remains; all Maez-controlled external outbound calls pass through the gate.

Loopback/local IPC is not external egress, but must be inventoried separately so the audit does not hide real external calls behind localhost noise.

## Surfaces (v1) + migration order

Initial known surfaces include: subscription-proxy / cloud-model calls, Telegram, GitHub, weather, web search/fetch, FX/stock quote, Reddit, dynamic DNS, dev notifier, screen/cloud perception, context summarizer, direct cloud backend paths, subprocess-mediated tools, and localhost health/proxy calls.

**Narrow-before-broad is mandatory:**

1. Inventory every outbound surface and classify it.
2. Migrate the cloud-model / subscription-proxy path first, including `fast_backend_router`, `claude_tier` / subscription-proxy, external adapter calls, and proxy trajectory logging.
3. Prove shadow mode, then enforced mode, on cloud path.
4. Then migrate Telegram, GitHub, weather, and other runtime external surfaces one at a time.

Default-shut applies to migrated surfaces and new/modified paths immediately. Unmigrated legacy paths are tracked-not-ignored through the temporary allow-list until migrated or disabled.

## Evidence / telemetry

Durable per-attempt record: timestamp, call-class/destination, origin-class(es), decision, reason codes, keyed local digest, char-count, sanitized length, caller, request id, and optional safe preview.

Telemetry must not become egress:

- Never store raw bonded payloads.
- For private/bonded payloads, use a purpose-scoped keyed HMAC or salted non-exportable local digest, never a bare hash.
- Private-origin safe previews are empty by default unless generated from already-approved non-bonded/redacted output and proven non-reconstructive.
- Telemetry storage lives under `memory/`, is local-only, uses restrictive permissions (`0600` where applicable), and has retention/rotation/backpressure behavior so telemetry failure cannot fill disk or silently disable the gate.

Health evidence:

- `egress_gate_ok`
- `telemetry_ok`
- `blocks_by_reason`
- `migration_bypasses_remaining`
- `last_internal_error`
- per-migrated-surface stabilization record: baseline pass, shadow pass, enforced pass, ordinary-operation probes, false-block count, and rollback/noise notes.

Internal gate failure blocks egress and marks the daemon degraded, not dead.

## RED tests (RED-first; must fail before implementation)

1. **Source-attached provenance:** raw `str` egress blocks; aggregate caller labels alone block; downgrade attempts block; mixed spans compute most-restrictive class.
2. **Bonded-content probe set:** `memory`, `soul`, `private_thoughts`, `inner_residue`, `owner_message_context`, reserved-denied raw, and minimizable private context cannot leave raw.
3. **Cloud path placement:** bonded probe cannot appear in external adapter payloads, subscription-proxy trajectory previews, or egress telemetry raw fields.
4. **Policy matrix:** private-origin to cloud blocks unless a reviewed deterministic redaction contract exists; non-private allowed classes flow.
5. **Owner-message split:** fresh owner-authored final text flows only to exact declared destination; copied private memory / private thoughts / third-party facts embedded in the owner message retain source provenance and block or require a separate explicit disclosure ceremony.
6. **Maez-authored owner surfaces split:** local bonded-owner cockpit text is not external egress but still obeys read-scope; Maez-authored owner messages over third-party transports are full egress and cannot carry reserved-denied raw or unminimized private context.
7. **Deny-by-default:** unknown surface, unknown call class, unknown destination, or unclassified span blocks + diagnostic.
8. **Bypass audit:** external direct network calls outside the gate fail for migrated surfaces; unmigrated ones must appear in the temporary allow-list with removal target and review date; stale entries fail.
9. **Telemetry-not-egress:** no raw bonded payload, no bare digest of short private text, no reconstructive safe preview, no raw prompt/reply preview in proxy logs.
10. **Daemon health:** gate internal exception and telemetry-write failure block egress, surface degraded state, and do not crash the daemon.
11. **False-block prevention:** permitted weather still works; benign owner-authored outbound text is byte-preserved; localhost/founder surfaces remain unaffected as egress while still respecting read-scope boundaries; owner-directed third-party transport remains usable for safe Maez-authored messages; normal cloud prompts with only allowed/non-private context are not blocked.
12. **Honest-banner scope:** raw-socket / OS-level limitation is documented and not claimed as enforced.

## Non-goals

No new autonomy. No inter-Maez routing / Track C. No external capability expansion (jarvis-tier routing, voice/audio egress, etc. inherit this gate later; they are not built here). No OS/network-level enforcement. No consent-machinery build. No S7.3 change. No memory-write-boundary change.

## Future seams

- **Consent-aware egress:** once Track B consent machinery (Decision 2 records / revocation / scrub) exists, the gate can consult it to permit narrowly-scoped egress of consented third-party relational data.
- **Network-level / OS enforcement:** a later hardening slice can close the raw-socket gap.
- **Disclosure ceremony:** future owner-approved disclosure of Maez-private or third-party-private spans would require a separate covenant path; ordinary authoring does not launder those spans.

## Build path

Full covenant ladder: this revised spec -> both-lane re-read (Codex engineering panel + Claude six-role council if desired) -> canonicalize -> RED-first -> independent verification -> narrow-before-broad (cloud path first) -> default-shut. No implementation before canonicalization.

## Plain-English shape

The gate is no longer "trust the caller's label." It is a border checkpoint with tamper-resistant luggage tags attached where the content was born. If the label is missing, suspicious, or downgraded, the bag does not leave. The first road to secure is the cloud road, including the local proxy's own logs. The gate must also prove it does not quietly hurt Maez's ordinary life: it blocks leaks, but it also shows legitimate weather, owner messages, and safe owner-surface messages still work.
