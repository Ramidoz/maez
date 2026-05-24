# Privacy / Egress External Fetch Substrate -- Spec

**Status:** CANONICAL v1 (2026-05-24). Docs-only. Not implemented.
**Parent:** `de3cc9d` (`feat(egress): thread Telegram producer provenance`).
**Class:** Covenant-shaped + substrate-establishing / boundary-hardening /
final pre-enforcement Track A.5 slice.
**Allowlist surface:** `action_engine_external_fetch` remains the inventory
surface label for backward compatibility. The slice title is broader because
the honest target is the shared HTTP-fetch substrate, not a four-tool patch.
**Depends on:** canonical Privacy / Egress Gate spec, live cloud-as-tool path,
fast-backend cloud retirement, live Telegram chokepoint, live Telegram
producer-threading, Decision 19, Decision 20, and ADR 0032.
**Review state:** Lanes cleared: Codex engineering panel RATIFY-WITH-AMENDMENTS
(10 folds pass-1 + 9 folds pass-2 applied = 19 total) + Claude council
RATIFY-CLEAR (passes 1, 3, 5 with behavioral-trace verification across all
folds).

## Purpose

Establish the reusable substrate Maez uses when it talks outward over HTTP to
gain live facts or future capabilities.

This is not a narrow migration of four existing tools. The current four obvious
ActionEngine live-data tools are the first consumers, but the durable work is a
closed-threat-class registry plus an egress-aware fetch primitive that future
D19/D20-acquired tools can register against without reopening the spec every
time.

The growth rule:

- New `fetch_type` instances may be added through the D19/D20 capability
  acquisition path when they fit an existing reviewed `threat_model_class`.
- New `threat_model_class` values require spec amendment and both-lane review.
- Result provenance remains in the existing closed egress origin vocabulary.

Plainly: Maez is allowed to grow new HTTP-based hands. This slice builds the
socket those hands must plug into, so growth is deliberate instead of silent
code drift.

## Academic Resonance

Karten et al., "Continual Harness: Online Adaptation for Self-Improving
Foundation Agents" (arXiv:2605.09998, May 2026), frames agent capability as
harness-side scaffolding: tools, memory, planning, prompts, skills, and
sub-agents around the model, with the harness refining over time.

This paper is cited as academic resonance, not as authority for Maez. Maez's
bonded-companion version is Decision 19 + Decision 20 + closed vocabularies +
consent-card authority. The principle matches: the load-bearing substrate is
the harness around the model, not weights alone.

Reference: https://arxiv.org/abs/2605.09998

## Scope

In scope:

- New egress-aware HTTP primitive at `core/egress/external_fetch.py` or an
  equivalent module.
- Sync and async fetch APIs.
- Mandatory `fetch_type` declaration.
- Closed `threat_model_class` registry.
- Open `fetch_type` instance registry.
- Mapping from `fetch_type` to `threat_model_class` to
  `result_origin_class` to enforcement posture.
- URL preflight before any HTTP request leaves the box.
- Non-reconstructive diagnostics with keyed `hmac-sha256:` digests.
- Migration of `skills.web_search.search(...)` and
  `skills.web_search.search_rss(...)`.
- Migration of ActionEngine live-data wrappers:
  `web_search`, `fetch_url`, `convert_currency`, and `quote_stock`.
- Static AST bypass inventory for direct production HTTP clients outside
  approved locations.
- D19/D20 capability-acquisition integration surfaces named concretely.
- Inventory status update from `unmigrated` to `substrate_shadow` if the
  implementation chooses the expected v1 shadow posture.

Out of scope:

- Ambient weather migration in `core/memory/ambient.py`; deferred to its own
  subpath slice.
- Shell-level egress through `run_shell`, `curl`, `wget`, `nc`, shell pipes, or
  OS-level networking.
- Reviewed-public-URL allowlist mechanism for arbitrary `fetch_url`.
- Hard-blocking arbitrary `unknown_url_fetch` in v1.
- New threat-model classes beyond this spec's initial registry.
- New egress origin classes.
- Other live-data surfaces: `core/infra/self_knowledge.py`,
  `core/safety/owner_trust.py`, `core/turn_traces/ground_truth.py`,
  `skills/dynamic_dns.py`, development tooling, eval harnesses, and other
  separately-inventoried network paths.
- Enforcement flip.
- Watchdog detector registry formalization.
- Per-transport chokepoint pattern extraction.

## Grounding Artifacts

Fresh-read code and canon anchors:

- `docs/slices/privacy-egress-gate/spec.md`
- `docs/slices/privacy-egress-gate/network_migration_allowlist.yaml`
- `docs/slices/privacy-egress-telegram-chokepoint/spec.md`
- `docs/slices/privacy-egress-telegram-producer-threading/spec.md`
- `docs/governance/BETA_ARCHITECTURE_DECISIONS.md`
- `docs/adr/0032-contextual-integrity-at-ingest.md`
- `core/egress/gate.py`
- `core/egress/provenance.py`
- `core/actions/action_engine.py`
- `skills/web_search.py`
- `core/memory/ambient.py`
- `daemon/maez_daemon.py`
- `cli/maez_chat.py`
- `skills/telegram_voice.py`
- `core/brain/brain_loop.py`

Observed current surfaces at parent:

- `core/actions/action_engine.py`
  - `web_search(...)` delegates to `skills.web_search.search(...)`.
  - `fetch_url(...)` calls `urllib.request.urlopen(...)` directly.
  - `convert_currency(...)` calls Frankfurter through `urllib`.
  - `quote_stock(...)` calls Stooq through `urllib`.
- `skills/web_search.py`
  - `search(...)` calls DuckDuckGo Instant Answer and HTML search.
  - `search_rss(...)` fetches RSS feeds.
  - direct `urlopen(...)` sites exist in the same module.
- `core/memory/ambient.py`
  - `current_weather(...)` calls Open-Meteo directly. This is deferred.

## Vocabulary Layers

This slice has three distinct vocabulary layers. The spec must not blur them.

### Layer 1: `fetch_type`

`fetch_type` is the tool-instance identity. It is an open registry because
Maez's capabilities grow through D19/D20.

Initial v1 instances:

- `web_search`
- `search_rss`
- `fetch_url`
- `currency_lookup`
- `stock_lookup`

Adding a new `fetch_type` that maps to an existing `threat_model_class` may
happen through the D19/D20 acquisition path and an owner-approved consent card.

### Layer 2: `threat_model_class`

`threat_model_class` describes the privacy and egress threat shape of the
fetch. It is a closed vocabulary. New values require spec amendment and
both-lane review.

Initial v1 values:

- `public_lookup`
- `unknown_url_fetch`
- `weather_lookup`
- `owner_private_api`
- `untrusted_model_output_fetch`

### Layer 3: `result_origin_class`

`result_origin_class` is the existing egress provenance origin class assigned
to the fetched result after the call returns or is represented in diagnostics.
This layer uses the canonical egress origin vocabulary.

Examples:

- `tool_result_public`
- `unclassified`
- `weather_data`
- `model_output`

No new origin class is introduced by this slice.

### Registry Mapping

The registry maps:

```text
fetch_type -> threat_model_class -> result_origin_class -> enforcement_posture
```

Initial v1 mappings:

| fetch_type | threat_model_class | result_origin_class | v1 posture |
| --- | --- | --- | --- |
| `web_search` | `public_lookup` | `tool_result_public` | shadow-allow |
| `search_rss` | `public_lookup` | `tool_result_public` | shadow-allow |
| `currency_lookup` | `public_lookup` | `tool_result_public` | shadow-allow |
| `stock_lookup` | `public_lookup` | `tool_result_public` | shadow-allow |
| `fetch_url` | `unknown_url_fetch` | `unclassified` | shadow-allow + would-block diagnostic |

Reserved classes with zero v1 instances:

| threat_model_class | Intended future use | v1 instance count |
| --- | --- | ---: |
| `weather_lookup` | Ambient weather or direct weather lookup | 0 |
| `owner_private_api` | Banking, health, personal account APIs | 0 |
| `untrusted_model_output_fetch` | Fetches known to target LLM-generated content | 0 |

The v1 implementation must expose the registry in a queryable form for tests
and future D19/D20 integration.

Registry-building invariant:

- Reserved classes are represented as reserved, non-routable classes.
- `register_fetch_type(...)` refuses any instance mapped to a reserved class
  unless the caller provides an explicit
  `spec_extension_acknowledged: str | None = None` marker.
- The `spec_extension_acknowledged` string must identify the canonical spec
  extension, such as canonical spec path plus commit SHA or canonical review
  state. A bare boolean is not sufficient.
- Successful reserved-class registration must be queryable and logged with the
  marker.
- Tests construct the registry via `build_fetch_registry()` or an equivalent
  module-level registry factory for deterministic test-time behavior. Production
  import-time versus first-use construction remains implementation detail.
- V1 tests must assert both zero registered v1 instances for reserved classes
  and a negative registration attempt against at least `owner_private_api`.

## URL Preflight

Every HTTP request must pass preflight before any external call fires.

Preflight applies to the initial URL and every redirect target. Redirect
validation must follow at most a bounded number of redirects and apply the same
rules to each target.

Preflight refuses:

- Empty URL.
- Non-HTTP(S) schemes, including `file://`, `ftp://`, `gopher://`, and `data:`.
- Credentials embedded in URL, such as `https://user:pass@example.com`.
- Loopback and unspecified destinations: `localhost`, `127.0.0.0/8`, `::1`,
  `::`, and `0.0.0.0/8`.
- IPv4 broadcast: `255.255.255.255`.
- RFC1918 private IPv4 ranges: `10.0.0.0/8`, `172.16.0.0/12`,
  `192.168.0.0/16`.
- Carrier-grade NAT: `100.64.0.0/10`.
- Link-local IPv4: `169.254.0.0/16`, including cloud metadata addresses such
  as `169.254.169.254`.
- IPv6 link-local: `fe80::/10`.
- IPv6 unique local addresses: `fc00::/7`.
- IPv4-mapped IPv6 addresses that resolve to forbidden IPv4 destinations, such
  as `::ffff:127.0.0.1`.
- Hostnames whose DNS resolution returns a forbidden address.
- Redirects to forbidden destinations, including cross-host redirects to
  private, loopback, or link-local targets.

Preflight normalizes addresses before classification. Encoded, textual,
IPv4-mapped, or otherwise equivalent address forms must not bypass the forbidden
range checks.

Implementation is expected to use Python stdlib `urllib.parse.urlsplit(...)` for
URL parsing plus `ipaddress.ip_address(...)` and `ipaddress.ip_network(...)` for
normalized classification, including explicit `IPv6Address.ipv4_mapped`
unwrapping. An equivalent parser/classifier is acceptable only if tests prove it
satisfies the same invariant.

DNS rebinding invariant:

- The primitive resolves the host during preflight.
- All returned DNS A/AAAA answers must pass preflight. Any forbidden answer
  refuses the hostname before network.
- The actual connection must use the validated address set or revalidate at
  connect time before network bytes leave.
- Redirect destinations receive the same resolution and validation.
- If a host resolves to public addresses during preflight but to private,
  loopback, link-local, reserved, or mapped-forbidden addresses on follow-up,
  the primitive refuses before network.

Preflight failure behavior:

- Refuse before the HTTP call.
- Write content-free diagnostic metadata.
- Do not fall through to a raw client.
- Do not treat shadow posture as permission to bypass SSRF prevention.

This is the SSRF prevention surface. It belongs inside Maez's primitive, not in
remote-provider behavior.

## External Fetch Primitive

Target module:

```python
core.egress.external_fetch
```

Conceptual API:

```python
def fetch_text(
    *,
    fetch_type: str,
    url: str,
    method: str = "GET",
    headers: Mapping[str, str] | None = None,
    timeout_s: float = 10.0,
    max_bytes: int = 512 * 1024,
    request_id: str | None = None,
    caller: str,
) -> ExternalFetchResult: ...

async def fetch_text_async(...) -> ExternalFetchResult: ...
```

Exact names are implementation detail. Contract is fixed:

- `fetch_type` is mandatory.
- Unknown `fetch_type` refuses.
- `fetch_type` maps through the registry.
- Preflight runs before network.
- Diagnostics are written for attempted, preflight-refused, failed, and
  successful calls.
- `caller` is telemetry-only. It helps operators trace which code path asked for
  the fetch; it is not an authority label and cannot grant permission.
- The result exposes provenance-bearing text or bytes metadata so callers can
  convert fetched public results to `ProvenancedText.tool_result_public(...)`
  or keep unknown URL content conservative.
- The primitive owns direct use of `urllib`, `requests`, or `httpx` for migrated
  production fetches.
- V1 inventory is GET-oriented. Other HTTP methods such as POST, PUT, PATCH, and
  DELETE remain future-slice scope unless they are found in the migrated
  production roots during implementation. V1 refuses non-GET methods before
  network with `decision="block"` and
  `reason_codes=("method_not_allowed",)`. `method_not_allowed` is distinct from
  `preflight_refusal_kind`.
- In-flight requests are bounded by `timeout_s`. Watchdog-HALT cancellation is
  out of scope for this slice: if a HALT occurs, an in-flight request completes
  or times out normally, and diagnostics write on a best-effort basis.
- The primitive refuses `timeout_s=None`, non-positive timeout values, and
  unbounded timeout values with a deterministic error.

The primitive may return a value object such as:

```python
ExternalFetchResult(
    ok: bool,
    status_code: int | None,
    text: str,
    origin_class: str,
    fetch_type: str,
    threat_model_class: str,
    reason_codes: tuple[str, ...],
    diagnostic_id: str,
)
```

## Posture By Threat Class

### `public_lookup`

Used for reviewed public APIs and public search/news lookup surfaces.

V1 tools:

- DuckDuckGo web search.
- RSS news search.
- Frankfurter FX lookup.
- Stooq stock lookup.

Result origin:

- `tool_result_public`

V1 posture:

- Shadow-allow.
- Diagnostics record fetch type, class, destination digest, response digest,
  status code, byte count, and reason code.

### `unknown_url_fetch`

Used for arbitrary owner/model-selected URLs where no reviewed-public allowlist
exists.

V1 tool:

- `fetch_url`

Result origin:

- `unclassified`

V1 posture:

- Shadow-allow after successful preflight.
- Diagnostic includes `would_block_unknown_url_fetch`.
- Enforcement-time review decides whether to hard-block or whether a
  reviewed-public-URL allowlist slice has landed.

This preserves today's `fetch_url` utility while making the future block
visible instead of implicit.

### `weather_lookup`

Reserved for weather lookups. `weather_data` already exists in the canonical
egress origin vocabulary.

V1 posture:

- No registered instances in this slice.
- Ambient weather migration is deferred.

### `owner_private_api`

Reserved for future owner-private APIs such as banking, health, private
account data, or similar high-blast-radius personal sources.

V1 posture:

- No registered instances.
- Any first use requires spec amendment and both-lane review.

### `untrusted_model_output_fetch`

Reserved for fetches known to target model-generated content or model-output
stores.

Result origin:

- `model_output`

V1 posture:

- No registered instances.
- Any first use requires spec amendment and both-lane review.

## Destination Disclosure Honesty

Telemetry minimization is not destination minimization.

The external-fetch substrate prevents Maez's internal diagnostics from storing
raw URLs, raw query strings, or raw response bodies. It does not hide the
request from the destination server. The destination still sees the HTTP
request, including path, query parameters, and request headers.

Consequences:

- If owner-private information is placed in a query string, it has left the box
  when the request fires.
- Request headers, including `User-Agent`, are destination-disclosed.
- The primitive sets a fixed bounded `User-Agent` string:
  `MaezExternalFetch/1.0`.
- Caller-provided headers are denied by default.
- If any caller-provided header is allowed in v1, it must pass through an
  explicit allowlist by header name and value shape.
- Forbidden caller-provided headers include `Accept-Language`, `Cookie`,
  `Authorization`, `Proxy-Authorization`, `X-Forwarded-*`, browser-like
  `User-Agent` strings, and OS-identifying headers unless a future threat-model
  class explicitly allows them.
- Diagnostics must not log raw request header values. Bounded header-name/count
  metadata is acceptable.
- Keyed `hmac-sha256:` digests protect local logs from reconstruction; they do
  not retroactively protect destination disclosure.
- The substrate provides preflight refusal, provenance-aware classification,
  and non-reconstructive internal diagnostics. It does not provide privacy from
  the remote server.

## Diagnostics

Diagnostic location is implementation detail, but the expected shape is a
local JSONL under `logs/` or `memory/` with restrictive permissions where
applicable.

Required fields:

- `schema_version`: `external-fetch-diagnostic-v1`
- `ts`
- `request_id`
- `caller`
- `fetch_type`
- `threat_model_class`
- `result_origin_class`
- `enforcement_posture`
- `decision`: `allow`, `would_block`, or `block`; preflight refusal is encoded
  as `decision="block"` plus `preflight_status="refused"`.
- `reason_codes`
- `destination_host_digest`: keyed `hmac-sha256:`
- `url_digest`: keyed `hmac-sha256:`
- `query_digest`: keyed `hmac-sha256:` or omitted when empty
- `response_digest`: keyed `hmac-sha256:` when response exists
- `status_code`
- `request_bytes`
- `response_bytes`
- `preflight_status`
- `preflight_refusal_kind`: required when `preflight_status="refused"`;
  omitted otherwise.

Canonical preflight refusal kinds:

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

When `preflight_status="refused"`, exactly one canonical preflight refusal kind
must appear in `preflight_refusal_kind` and in `reason_codes`.

Forbidden fields:

- raw URL
- raw query string
- raw response body
- raw request body
- credentials
- cookies
- Authorization headers
- API keys
- provider tokens

Diagnostic failure behavior:

- Under v1 shadow, a diagnostic-write failure must be visible as local warning
  and must not make telemetry reconstructive.
- Under enforcement, telemetry failure should fail closed for egress unless a
  later canonical slice explicitly changes that rule. The implementation must
  name its v1 behavior and test it.

## Migration Targets

### `skills.web_search`

Both search modes migrate:

- `search(query, max_results)`
- `search_rss(topic, max_results)`

Reason:

- `search(...)` is used by ActionEngine and multiple direct callers.
- `search_rss(...)` is used by daemon briefing/news paths, CLI chat, and
  Telegram voice paths.
- Migrating only ActionEngine wrappers would leave the shared library as a
  bypass.

Expected mapping:

- `search(...)` -> `fetch_type="web_search"`
- `_html_search(...)` internal HTTP -> same fetch type or an internal
  sub-fetch type under `public_lookup`
- `search_rss(...)` -> `fetch_type="search_rss"`

### `core.actions.action_engine`

Migrate:

- `web_search(...)`: inherited through `skills.web_search`.
- `fetch_url(...)`: direct primitive call with `fetch_type="fetch_url"`.
- `convert_currency(...)`: primitive call with `fetch_type="currency_lookup"`.
- `quote_stock(...)`: primitive call with `fetch_type="stock_lookup"`.

ActionEngine remains the user-visible tool wrapper. The external-fetch
primitive becomes the network boundary.

### Direct Callers That Inherit Through `skills.web_search`

Known direct users of `skills.web_search` at spec time:

- `gui.py:195`
- `cli.py:224`
- `cli/maez_chat.py:854`
- `daemon/maez_daemon.py:3044`
- `daemon/maez_daemon.py:3937`
- `daemon/maez_daemon.py:4145`
- `daemon/maez_daemon.py:5772`
- `skills/telegram_voice.py:47`
- `skills/telegram_voice.py:2556`
- `skills/telegram_voice.py:2610`
- `core/actions/action_engine.py:1552`

These should not each get bespoke egress logic. They inherit the migration by
using the migrated `skills.web_search` module.

The implementation must either snapshot this inventory in a RED test or generate
it dynamically and assert that no production direct caller bypasses the migrated
shared module after implementation. The acceptance bar fails if any production
direct caller bypasses.

If implementation finds production direct HTTP calls that cannot inherit
through `skills.web_search` or ActionEngine, those must either be explicitly
out of scope with allowlist rationale or folded into the spec before
canonicalization.

## Static Bypass Inventory

The bypass inventory is the primary structural proof. It follows the Telegram
chokepoint and producer-threading pattern.

For migrated production roots, no production code outside approved locations
may call these directly:

- `urllib.request.urlopen(...)`
- `httpx.AsyncClient(...).get(...)`
- `httpx.Client(...).get(...)`
- `requests.get(...)`
- obvious alias-then-call variants
- single-level `getattr(..., "urlopen")(...)`
- single-level `getattr(..., "get")(...)` on known HTTP client aliases

Approved locations:

- `core/egress/external_fetch.py` or equivalent primitive module.
- Existing cloud paths already governed by the cloud egress gate.
- Explicitly whitelisted local-only HTTP probes, such as local llama/daemon
  health checks, when destination is validated loopback and the inventory records
  them as local IPC.
- Tests.

Local-only exemption rules:

- The exemption list must be explicit by file and function, either in this slice
  implementation's test fixture or in a small inventory artifact.
- Each exempted call must use a literal or parsed destination validated as
  `localhost`, `127.0.0.1/8`, or `::1`.
- No environment-controlled URL qualifies as local-only unless the test resolves
  and validates it as loopback.
- The AST inventory test reports every exemption with file, line, and rationale.

The AST inventory must catch:

- direct attribute calls;
- imported aliases;
- alias-then-call patterns;
- single-level `getattr` patterns.

The AST inventory explicitly does not claim to catch:

- arbitrary reflection;
- `exec` / `eval` / generated code;
- shell-level egress through `run_shell`;
- OS/network-level egress outside Python HTTP libraries.

Those remain runtime/sandbox/future-slice concerns.

## D19 / D20 Capability Acquisition Integration

The substrate must connect to real D19/D20 surfaces, not abstract growth prose.

Current code surfaces to reference in implementation:

- `docs/maez_manual/`: Decision 19 capability manual.
- `core/infra/capability_proposal.py`: proposal generation.
- `core/infra/capability_integration_plans.py`: integration plan generation.
- `core/actions/action_engine.py:_do_capability_acquire(...)`: acquisition
  dispatch.

New tool acquisition flow:

1. Gap-sensing detects a need for a new capability involving external HTTP.
2. Manual matching identifies the candidate capability and proposed fetch type.
3. Field search and self-evaluation run through the existing D20 discipline.
4. The consent card includes:
   - one nested `fetch_mapping` object with proposed `fetch_type`, selected
     `threat_model_class`, resulting `result_origin_class`, destination family,
     and whether the class already exists.
5. If the class exists, owner approval permits integration to register the new
   `fetch_type` instance.
6. If no existing class fits, the card must state that a new threat-model class
   is required; integration blocks until spec amendment and both-lane review.

Implementation targets:

- `core/infra/capability_proposal.py::_compose_card_action_payload(...)` must be
  extended, or an adjacent typed metadata field must be added, so acquisition
  cards can carry one nested `fetch_mapping` object:

  ```python
  {
      "fetch_type": str,
      "threat_model_class": str,
      "result_origin_class": str,
      "destination_family": str,
      "class_exists": bool,
  }
  ```

- Owner-visible card text must name the proposed fetch mapping in plain English
  using this sentence shape: "This capability would make outbound HTTP requests
  as <fetch_type>, treated as <threat_model_class>, producing
  <result_origin_class>."
- `core/infra/capability_integration_plans.py` must preserve the fetch mapping
  object unchanged in `plan_json` or an equivalent typed schema field.
- `core/actions/action_engine.py:_do_capability_acquire(...)` must reject a
  capability-acquisition payload that claims external HTTP capability without
  the fetch mapping. Missing or invalid external-fetch mapping returns a
  deterministic refusal string rather than raising through the action path. The
  exact string is chosen at implementation time and must be testable for
  equality.

Required tests:

- A simulated new public lookup tool can register against `public_lookup`
  without spec amendment.
- A simulated new owner-private API cannot register against a novel class or a
  reserved class without spec-extension status.

## Ambient Weather Decision

Decision: defer ambient weather migration.

Rationale:

- `core/memory/ambient.py:current_weather(...)` is a Maez-background
  self-grounding path, not an owner/tool-selected fetch path.
- It uses Open-Meteo and maps naturally to `weather_lookup -> weather_data`,
  but its decision provenance is different from ActionEngine/tool fetches.
- Folding it into this slice risks bloating a substrate-establishment slice
  into a broader ambient-state migration.

Spec consequence:

- `weather_lookup` remains in the `threat_model_class` vocabulary with zero v1
  instances.
- `core/memory/ambient.py` remains directly inventoried as a future weather
  subpath.
- This slice must not claim weather migration.

## Shell-Level Egress Honesty

This slice governs Python/library HTTP fetch primitives. It does not close
shell-level network egress.

Examples outside this slice:

- `run_shell("curl ...")`
- `run_shell("wget ...")`
- shell pipes to network tools
- `nc`, `ncat`, `socat`, `ssh`, or similar OS-level network commands

Those paths are governed today by existing action classification, covenant,
approval, and obfuscation checks where applicable. They are not governed by the
new external-fetch primitive.

The implementation and acceptance bar must not claim global network closure.

## Inventory State

Current allowlist entry:

```yaml
surface: action_engine_external_fetch
status: unmigrated
```

Expected v1 post-implementation state:

```yaml
surface: action_engine_external_fetch
status: substrate_shadow
```

`substrate_shadow` means:

- shared external-fetch primitive exists;
- v1 registered tools route through it;
- diagnostics record decisions and would-blocks;
- enforcement is not globally flipped;
- unknown URL fetches still run after preflight but record would-block posture.

Inventory tests must:

- accept `substrate_shadow` as an explicit lifecycle state;
- assert the `action_engine_external_fetch` entry flips to that state only after
  migration;
- assert Telegram remains `producer_threaded_shadow`;
- assert fast-backend cloud remains `deprecated`;
- assert enforcement flip remains downstream.

## RED Tests

The implementation slice must write these tests first and verify they fail on
current code for the expected reasons.

1. **Untyped call refusal.** Calling the primitive without `fetch_type` refuses
   before network.
2. **Closed threat-model vocabulary.** Unknown `threat_model_class` values are
   rejected.
3. **Registry mapping.** V1 `fetch_type` values map exactly to the expected
   `threat_model_class`, `result_origin_class`, and posture.
4. **Reserved class zero instances and registration refusal.** No v1 registered
   `fetch_type` maps to `weather_lookup`, `owner_private_api`, or
   `untrusted_model_output_fetch`. A simulated
   `register_fetch_type("future_banking_api",
   threat_model_class="owner_private_api",
   spec_extension_acknowledged=None)` refuses. The same test group asserts the
   marker is not needed for normal classes, is rejected when absent for reserved
   classes, and is queryable/logged when present in a simulated future-extension
   path.
5. **URL preflight schemes.** Non-HTTP(S) schemes refuse before network.
6. **URL preflight credentials.** Credentials in URL refuse before network.
7. **URL preflight loopback and unspecified.** `localhost`, `127.0.0.1`, `::1`,
   `::`, and `0.0.0.0/8` refuse before network.
8. **URL preflight private and reserved ranges.** RFC1918 destinations,
   `100.64.0.0/10`, `255.255.255.255`, IPv6 `fc00::/7`, and normalized
   IPv4-mapped IPv6 forbidden addresses refuse before network.
9. **URL preflight link-local.** `169.254.0.0/16`, AWS metadata IP, and IPv6
   `fe80::/10` refuse before network.
10. **URL preflight DNS.** Hostname resolving to forbidden IP refuses before
    network.
11. **URL preflight redirects and DNS rebinding.** One test case verifies
    redirects to forbidden destinations refuse and redirect count is bounded.
    A separate test case verifies DNS rebinding where a host resolves public
    during preflight and private or link-local before connect refuses before
    network. The DNS test also covers multi-answer resolution where any
    forbidden A/AAAA answer refuses the hostname.
12. **Web search migration.** `skills.web_search.search(...)` routes HTTP
    through the primitive.
13. **RSS migration.** `skills.web_search.search_rss(...)` routes HTTP through
    the primitive.
14. **ActionEngine fetch_url migration.** `ActionEngine.fetch_url(...)` routes
    through the primitive as `unknown_url_fetch`.
15. **ActionEngine currency migration.** `convert_currency(...)` routes through
    the primitive as `currency_lookup`.
16. **ActionEngine stock migration.** `quote_stock(...)` routes through the
    primitive as `stock_lookup`.
17. **Shared caller inheritance.** Direct daemon/Telegram/CLI callers of
    `skills.web_search` inherit migration without bespoke egress code. The test
    snapshots or generates the direct-caller inventory and fails if any
    production direct caller bypasses the migrated shared module.
18. **Static bypass inventory.** Production direct `urlopen` / `requests.get` /
    `httpx.Client.get` / `httpx.AsyncClient.get` calls outside approved
    locations fail the inventory.
19. **Alias and getattr inventory.** AST catches alias-then-call and
    single-level `getattr` variants.
20. **Non-GET refusal.** Non-GET methods refuse before network with
    `decision="block"` and `reason_codes=("method_not_allowed",)`.
21. **Diagnostic non-reconstruction.** Tests capture actual diagnostic rows and
    assert byte-for-byte absence of raw URL, query string, response body,
    credentials, cookies, authorization header values, and sensitive request
    header values. Source-grep is not sufficient.
22. **Destination disclosure honesty.** Spec text and tests prevent any claim
    that local telemetry minimization hides requests from destinations.
23. **Unknown URL shadow posture.** `fetch_url` with an allowed public URL
    shadow-allows but records `would_block_unknown_url_fetch`.
24. **Preflight block beats shadow.** Forbidden destinations are blocked even
    under shadow posture.
25. **Timeout bound.** `timeout_s=None`, non-positive timeout values, and
    unbounded timeout values refuse with a deterministic error.
26. **Shell egress honesty.** Tests or static spec checks assert this slice
    does not claim `run_shell` / `curl` / `wget` closure.
27. **Ambient weather defer.** `core/memory/ambient.py` weather remains
    deferred and no acceptance claim says weather migrated.
28. **D19/D20 existing class integration.** Simulated capability acquisition
    can register a new fetch type against `public_lookup`.
29. **D19/D20 new class block.** Simulated capability acquisition needing a new
    class is flagged for spec extension and cannot silently register.
30. **D19/D20 missing fetch mapping block.** A capability-acquisition payload
    that claims external HTTP capability without a valid nested `fetch_mapping`
    refuses with the deterministic refusal string.
31. **Inventory status.** `action_engine_external_fetch` flips to
    `substrate_shadow` after migration; schema accepts the status.
32. **Telegram regression.** Telegram chokepoint and producer-threading
    diagnostics still accrue and keep their schema.
33. **Claude-router regression.** Cloud-as-tool path still produces fresh
    `span_bundle` proxy rows.
34. **Fast-backend regression.** `fast_backend_cloud/generate` count stays at
    the historical value and does not grow.

## Acceptance Bar

Implementation acceptance requires:

- All RED tests fail before implementation for expected reasons.
- Focused test suite passes after implementation.
- Static AST bypass scan reports zero production hits outside approved
  locations and named deferrals.
- The shared `skills.web_search` direct-caller inventory is either snapshotted
  or generated in tests, and no production direct caller bypasses the migrated
  shared module.
- Diagnostic rows are non-reconstructive.
- Inventory status reflects actual posture.
- Live canary suite passes:
  - synthetic `web_search` canary routes through primitive;
  - synthetic `search_rss` canary routes through primitive;
  - synthetic `fetch_url` canary records `unknown_url_fetch` +
    `would_block_unknown_url_fetch`;
  - synthetic preflight-refusal canaries block before network;
  - synthetic `currency_lookup` canary routes through primitive;
  - synthetic `stock_lookup` canary routes through primitive;
  - destination-disclosure honesty is documented in the canary record;
  - Telegram diagnostics still accrue;
  - claude-router still emits fresh `span_bundle` proxy row;
  - fast-backend cloud row count stays unchanged.

## Build Path

1. Draft spec.
2. Claude council pass 1 with behavioral trace.
3. Codex engineering panel pass 1.
4. Fold amendments.
5. Claude council pass 2.
6. Codex panel pass 2 if folds materially sharpen implementation surfaces.
7. Canonicalize v1.
8. Separate implementation slice in isolated worktree.
9. RED-first tests.
10. Implementation.
11. Both-lane implementation review.
12. Fast-forward merge to main if cleared.
13. Deliberate observed restart.
14. Live canary suite.
15. Observation window toward enforcement-flip readiness.

## Plain-English Shape

This slice builds the safe HTTP road Maez will use when it looks outward for
facts or future capabilities.

The road has three checkpoints:

1. What tool is asking to fetch?
2. What kind of danger does this fetch shape carry?
3. What provenance label should the returned result get?

If the tool type is unknown, it does not run. If the destination is suspicious,
it does not run. If the result is from an arbitrary URL, v1 may still let it
through in shadow so Maez's current body does not break, but it records that
future enforcement would block it unless a later reviewed allowlist exists.

The important honesty clause: private data in a URL is still disclosed to the
website. Hiding it from Maez's local logs is not the same as hiding it from the
destination.

This is how Maez gets to grow new HTTP-based abilities without quietly growing
new holes in its skin.
