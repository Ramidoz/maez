# Codex Engineering Panel Review: External Fetch Substrate Spec

Spec: `docs/slices/privacy-egress-external-fetch-substrate/spec.md`
Base reviewed: `de3cc9d` (`feat(egress): thread Telegram producer provenance`)
Review date: 2026-05-24
Verdict: **RATIFY-WITH-AMENDMENTS**

## Summary

The spec's core substrate shape is right: this is not a one-off migration of a
few ActionEngine methods, but a reusable HTTP egress substrate with separate
registries for tool identity, threat model, and result provenance. The named
ActionEngine and `skills.web_search` surfaces are real, and the broad D19/D20
integration anchors point at real files.

The required amendments are boundary-hardening folds, not architecture reversal.
Most are the predictable corners of an HTTP egress substrate: SSRF preflight
coverage, DNS rebinding, reserved-class registration authority, concrete
caller inventory, and destination-visible request headers.

## Surface Verification

Verified against current code:

- `skills/web_search.py:26` defines `search(...)`.
- `skills/web_search.py:183` defines `search_rss(...)`.
- `skills/web_search.py:58`, `:117`, and `:211` are direct
  `urllib.request.urlopen(...)` sites inside the shared search module.
- `core/actions/action_engine.py:1129` defines
  `_do_capability_acquire(...)`.
- `core/actions/action_engine.py:1533` defines `web_search(...)`.
- `core/actions/action_engine.py:1562` defines `fetch_url(...)`.
- `core/actions/action_engine.py:1603` defines `convert_currency(...)`.
- `core/actions/action_engine.py:1692` defines `quote_stock(...)`.
- `core/infra/capability_proposal.py` exists and builds
  `card_action_payload` through `_compose_card_action_payload(...)`.
- `core/infra/capability_integration_plans.py` exists and persists
  integration-plan JSON in `integration_plans.plan_json`.
- `docs/maez_manual/` exists and contains current D19/D20 manual entries.
- `docs/slices/privacy-egress-gate/network_migration_allowlist.yaml` still
  records `action_engine_external_fetch` as `unmigrated`.

The current consent-card payload has `capability_id`, `source`,
`manual_source_path`, `acquisition`, and `proposal_id`; it does not currently
carry `fetch_type`, `threat_model_class`, or `result_origin_class`. That is an
implementation target, not an existing surface.

## What Lands Correctly

Vocabulary layering is clean. The spec separates:

- `fetch_type`: open tool-instance registry.
- `threat_model_class`: closed threat-shape vocabulary.
- `result_origin_class`: canonical egress origin vocabulary.

The initial registry table is queryable as a v1 contract, and the reserved
classes are explicitly called zero-instance classes. The spec also correctly
keeps `unknown_url_fetch` shadow-allowed for v1 while recording
`would_block_unknown_url_fetch`, so existing `fetch_url` utility does not break
during shadow migration.

The primitive API direction is implementable. A sync `fetch_text(...)` plus
async `fetch_text_async(...)` is the right shape for the current mixed codebase.
`ExternalFetchResult` has enough surface to carry status, origin class,
registry identity, and diagnostics for callers to construct
`ProvenancedText.tool_result_public(...)` or keep unknown URL results
conservative.

The static bypass inventory follows the Telegram producer-threading pattern and
includes alias and single-level `getattr` coverage. That is the right primary
invariant for this slice, with runtime preflight as the network-side guard.

## Required Folds

### 1. URL Preflight Must Cover Additional Forbidden Destinations

The preflight list at spec lines 214-227 covers the obvious SSRF cases but is
not complete enough for a canonical substrate.

Fold in these forbidden destinations:

- IPv6 unspecified `::`.
- IPv4 broadcast `255.255.255.255`.
- IPv4 reserved/this-network range `0.0.0.0/8`, not only literal
  `0.0.0.0`.
- Carrier-grade NAT `100.64.0.0/10`.
- IPv6 unique local addresses `fc00::/7`.
- IPv4-mapped IPv6 addresses such as `::ffff:127.0.0.1`.

Also specify address normalization before classification, so encoded,
mapped, or textual variants do not bypass the range check.

### 2. DNS Rebinding Needs an Explicit Pinning Rule

The spec says hostnames whose DNS resolution returns a forbidden address are
refused, but does not define what happens after an initial public resolution.

Add an explicit DNS-rebinding invariant:

- The primitive resolves the host during preflight.
- The actual connection must use the validated address set or revalidate at
  connect time.
- Redirect destinations get the same resolution and validation.
- A host that resolves public during preflight and private/link-local on a
  follow-up resolution must refuse before network.

RED #11 should cover both redirect-to-forbidden and DNS-rebinding behavior, not
only redirect count.

### 3. Diagnostics Need Canonical Preflight Refusal Kinds

The diagnostics section includes `reason_codes` and `preflight_status`, but it
does not enumerate canonical preflight refusal kinds. This is the same
observability mistake the Telegram specs avoided by naming precise reason
codes.

Add a closed set such as:

- `preflight_refused_empty_url`
- `preflight_refused_scheme`
- `preflight_refused_credentials`
- `preflight_refused_loopback`
- `preflight_refused_private_range`
- `preflight_refused_link_local`
- `preflight_refused_reserved_range`
- `preflight_refused_dns_resolution`
- `preflight_refused_redirect_target`
- `preflight_refused_redirect_limit`
- `preflight_refused_ipv4_mapped_ipv6`

Also make the diagnostic field explicit: either add
`preflight_refusal_kind` or require that exactly one of these appears in
`reason_codes` when `preflight_status="refused"`.

### 4. User-Agent and Destination-Visible Headers Must Be Named

The destination-disclosure section correctly says URL/query privacy is not
privacy from the destination, but it omits request headers. Current code sends
identifying User-Agent strings in several places, including
`skills/web_search.py` and `core/actions/action_engine.py`.

Fold in:

- Request headers, including User-Agent, are destination-disclosed.
- The primitive sets a deliberate bounded User-Agent string.
- The primitive must not forward owner-machine fingerprinting headers,
  cookies, Authorization headers, or caller-supplied sensitive headers unless
  a future class explicitly allows them.
- Diagnostics must not log raw header values; bounded header-name/count
  metadata is acceptable.

This matches the council Goodall observation and closes a real current-code
surface.

### 5. Reserved Threat Classes Need Runtime Registration Guards

The spec says `weather_lookup`, `owner_private_api`, and
`untrusted_model_output_fetch` have zero v1 instances and first use requires a
spec amendment. RED #4 catches current violations, but the registry itself
should make this hard to bypass accidentally.

Add a registry-building invariant:

- Reserved classes are represented as reserved, non-routable classes.
- `register_fetch_type(...)` refuses any instance mapped to a reserved class
  unless an explicit `spec_extension_acknowledged` or equivalent canonical
  marker is provided.
- V1 tests include both zero-instance assertion and a negative registration
  test where a simulated `owner_private_api` fetch type refuses.

Without this, the rule is mostly documentation plus a test that future edits
could weaken.

### 6. D19/D20 Consent Card Schema Extension Must Be Explicit

The spec references the right D19/D20 files, but current code does not already
have fields for `fetch_type`, `threat_model_class`, or
`result_origin_class`.

Fold in implementation targets:

- `core/infra/capability_proposal.py::_compose_card_action_payload(...)` must
  be extended, or an adjacent typed metadata field must be added, so acquisition
  cards can carry the fetch mapping.
- The owner-visible card text must name the fetch mapping in plain English.
- `core/infra/capability_integration_plans.py` must preserve the mapping in
  `plan_json` or a typed schema field.
- `_do_capability_acquire(...)` must reject a capability-acquisition payload
  that claims external HTTP capability without the mapping.

The current schema is compatible with extension, but it is not already enough.

### 7. Direct `skills.web_search` Caller Inventory Is Too Coarse

Spec lines 476-485 say direct users include daemon, Telegram voice, CLI chat,
and brain-loop surfaces. The code has concrete call sites and imports; the
canonical spec should name the inventory instead of relying on category prose.

Observed current call sites include:

- `gui.py:195`
- `cli.py:224`
- `cli/maez_chat.py:854`
- `daemon/maez_daemon.py:3044`, `:3937`, `:4145`, `:5772`
- `skills/telegram_voice.py:47`, `:2556`, `:2610`
- `core/actions/action_engine.py:1552`

Some of these are wrapper or direct-import sites, but they are all relevant to
the inheritance claim. Add a concrete caller inventory or require the RED test
to generate and snapshot the current inventory. The acceptance bar should fail
if a production direct caller bypasses the migrated shared module.

### 8. Local-Only HTTP Exemption Needs a Whitelist and Destination Assertion

The static bypass inventory permits "local llama/daemon health checks" when the
destination is loopback. Current code has many direct HTTP sites, including
local health probes and non-local external fetches. A broad exemption will
become a hole.

Fold in:

- Explicit local-only exemption list by file/function.
- Each exempted call must use a literal or parsed destination validated as
  `localhost`, `127.0.0.1/8`, or `::1`.
- No environment-controlled URL may qualify as local-only unless the test
  resolves and validates it as loopback.
- The AST inventory test reports every exemption with file, line, and rationale.

This keeps local IPC from being confused with external egress.

### 9. Watchdog HALT Interaction Must Be Named

The spec does not say what happens to in-flight HTTP if the watchdog HALTs Maez.
This does not need a full cancellation architecture in this slice, but it must
not remain implicit.

Pick one:

- In-flight fetches complete or timeout, and diagnostics still write.
- Watchdog interaction is out of scope; the primitive only guarantees bounded
  timeout and diagnostic best effort.

Panel recommendation: choose the second for v1, but require bounded timeouts
and best-effort diagnostics so a HALT cannot create an unbounded HTTP hang.

### 10. RED Tests Need Three Sharpenings

RED #11 should cover redirect target validation and DNS rebinding separately.

RED #20 should capture actual diagnostic rows and assert byte-for-byte absence
of raw URL, query, response body, credentials, cookies, and authorization
values. Source-grep is not sufficient.

RED #4 should include a negative reserved-class registration attempt, not only
a zero-instance count.

These are the "do not pass accidentally" amendments.

## Non-Blocking Notes

The `caller: str` parameter should be explicitly telemetry-only. It is useful
for diagnostics but must not become an authority label. This mirrors the
Telegram chokepoint discipline.

The diagnostic `decision` vocabulary currently lists `allow`, `would_block`,
and `block`. Preflight refusal can be represented as `block` plus
`preflight_status="refused"`, but the spec should state that explicitly or add
`preflight_refused` as a distinct decision value. Do not leave implementers to
infer it.

The static pattern list names GET-only HTTP calls. That is acceptable for the
current `action_engine_external_fetch` and `skills.web_search` target, but the
spec should say the v1 inventory is GET-oriented and other methods remain
future-slice scope unless found in the migrated production roots.

## Verdict

**RATIFY-WITH-AMENDMENTS.**

The substrate is canonical-eligible after the folds above. None of the findings
requires changing the basic architecture. The largest substantive folds are
URL preflight completeness, D19/D20 schema specificity, reserved-class runtime
guarding, and concrete direct-caller inventory.
