# Codex Engineering Panel Review Pass 2: External Fetch Substrate Spec

Spec: `docs/slices/privacy-egress-external-fetch-substrate/spec.md`
Base reviewed: `de3cc9d` (`feat(egress): thread Telegram producer provenance`)
Review date: 2026-05-24
Verdict: **RATIFY-WITH-AMENDMENTS**

## Summary

The pass-1 folds landed faithfully. The spec now has the right substrate shape:
closed threat classes, open fetch-type registry, SSRF preflight, diagnostics,
concrete `skills.web_search` caller inventory, local-only exemption discipline,
and D19/D20 integration hooks.

Pass 2 finds no architecture reversal. The remaining amendments are
implementation-shape sharpenings. They matter because folds #5 and #6 moved the
spec from "describe the substrate" into concrete registry and consent-card
surfaces; those surfaces need deterministic contracts before canonicalize.

## Fold Fidelity

### Fold 1: Preflight Completeness

Faithful with one recommended tightening. The forbidden-destination list now
includes the pass-1 named set:

- `::`
- `255.255.255.255`
- `0.0.0.0/8`
- `100.64.0.0/10`
- `fc00::/7`
- `::ffff:127.0.0.1`

The address-normalization invariant is implementable in Python. The likely
implementation is `urllib.parse.urlsplit(...)` for URL parsing plus
`ipaddress.ip_address(...)` / `ipaddress.ip_network(...)` for normalized address
classification, with explicit handling for `IPv6Address.ipv4_mapped`.

Amendment: name the stdlib approach as the expected implementation path unless
the implementation proves an equivalent parser/classifier in tests. This avoids
hand-rolled IP parsing in the most security-sensitive part of the slice.

### Fold 2: DNS Rebinding Pinning

Mostly faithful. The spec now requires validated address set use or revalidation
at connect time.

Missing edge: multiple A/AAAA records. The spec does not say whether one bad
answer poisons the whole hostname.

Amendment: state that **all returned A/AAAA answers must pass preflight; any
forbidden address refuses the hostname before network**. This is the safer v1
rule and avoids an implementation picking "use the first public answer, ignore
the private answer."

### Fold 3: `preflight_refusal_kind`

Faithful. The eleven refusal kinds cover the named preflight classes. A
`method_not_allowed` result should not be a preflight refusal kind; it is an API
method-policy refusal.

Amendment: because the spec says v1 is GET-oriented, explicitly define non-GET
behavior. Panel recommendation: v1 refuses non-GET methods before network with
`decision="block"` and `reason_codes=("method_not_allowed",)`. This is distinct
from `preflight_refusal_kind`.

### Fold 4: User-Agent and Header Policy

Partially faithful. The spec now says headers are destination-disclosed, the
primitive sets a deliberate User-Agent, and sensitive/fingerprinting headers
must not be forwarded.

Remaining ambiguity: "owner-machine fingerprinting headers" is not bounded.
Current code contains browser-like User-Agent strings, and future caller-provided
headers could sneak in `Accept-Language`, browser UA strings, cookies, or
Authorization values.

Amendment: define a default outbound header policy:

- Primitive-owned `User-Agent` only, with a fixed bounded value such as
  `MaezExternalFetch/1.0`.
- Caller-provided headers are denied by default.
- If any caller header is allowed in v1, it must pass through an explicit
  allowlist by header name and value shape.
- `Accept-Language`, `Cookie`, `Authorization`, `Proxy-Authorization`,
  `X-Forwarded-*`, browser-like User-Agent strings, and OS-identifying headers
  are forbidden unless a future threat class explicitly allows them.

### Fold 5: Reserved-Class Runtime Guard

Faithful in principle, but too loose at the signature level.

The spec now says `register_fetch_type(...)` refuses reserved-class mappings
unless `spec_extension_acknowledged` or equivalent marker is present, and RED #4
includes a negative reserved registration attempt.

Required amendment:

- Specify the marker shape as `spec_extension_acknowledged: str | None = None`,
  not a boolean.
- The string must identify the canonical spec extension, e.g. canonical spec
  path plus commit SHA or canonical review state.
- Successful reserved-class registration must be queryable and logged with that
  marker.
- Tests must exercise `register_fetch_type(...)` directly and assert the
  marker is not needed for normal classes, is rejected when absent for reserved
  classes, and is recorded when present in a simulated future extension path.

Registry construction timing should also be named. Panel recommendation:
provide a deterministic `build_fetch_registry()` or module-level registry
factory that tests can call in isolation. Whether production builds at import or
first use is implementation detail, but tests need a stable constructor.

### Fold 6: D19/D20 Schema Extension

Faithful at target-file level, but still underspecified at payload shape.

Verified real code:

- `_compose_card_action_payload(...)` currently returns `params` with
  `capability_id`, `source`, `manual_source_path`, `acquisition`, and
  `proposal_id`.
- `capability_integration_plans` persists `plan_json`.
- `_do_capability_acquire(...)` delegates to
  `handle_capability_acquire(params)` and returns strings, not typed results.

Required amendment:

- Use one nested field named `fetch_mapping` rather than three loose top-level
  fields.
- Required schema:
  `{"fetch_type": str, "threat_model_class": str, "result_origin_class": str,
  "destination_family": str, "class_exists": bool}`.
- `card_plain_english` must include a sentence naming the mapping, for example:
  "This capability would make outbound HTTP requests as `<fetch_type>`, treated
  as `<threat_model_class>`, producing `<result_origin_class>`."
- `plan_json` must preserve the same `fetch_mapping` object unchanged.
- `_do_capability_acquire(...)` should return a deterministic refusal string for
  missing/invalid external-fetch mapping rather than raising through the action
  path.

Downstream card storage can likely carry this through existing `params` and
`plain_english`; no `PendingCardStore` schema change is required unless the
implementation finds a typed card renderer that rejects extra params.

### Fold 7: Concrete Caller Inventory

Faithful. The line numbers listed in the spec match current code:

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

No amendment beyond what the spec already says: implementation should generate
or snapshot the inventory because line numbers will drift.

### Fold 8: Local-Only Exemption Whitelist

Mostly faithful. The whitelist requirement, loopback validation, no blind
environment-controlled URL exemption, and file/line/rationale report all landed.

Implementation note: AST-only validation is enough for literal
`http://localhost:...` and `http://127.0.0.1:...` strings. Environment-derived
or variable-composed URLs need runtime/preflight validation, not AST inference.
The current spec says this; no extra fold required.

### Fold 9: Watchdog HALT Interaction

Faithful. The spec now says watchdog cancellation is out of scope and in-flight
requests complete or timeout with best-effort diagnostics.

Amendment: make `timeout_s` bounded and non-null. The API currently defaults to
`10.0`, but the contract should explicitly refuse `timeout_s=None`, non-positive
timeouts, or unbounded values.

### Fold 10: RED Test Sharpenings

Faithful. RED #4 now includes negative registration refusal, RED #11 separates
redirect and DNS rebinding, and RED #20 requires diagnostic-row capture plus
byte-for-byte forbidden-substring absence.

RED #20 is implementable by capturing a diagnostic JSON row, recursively
walking string-valued fields, and asserting absence of raw host, path/query,
credentials, cookie value, authorization value, and response-body chunks.

## Scope Assessment

Folds #5 and #6 are substantial, but they do not need a separate slice. They are
load-bearing for the substrate claim: a growth-capable HTTP registry without
reserved-class runtime authority and consent-card mapping would recreate the
"silent capability growth" hole this slice is meant to close.

Keep them in this slice, but tighten their implementation contracts as above.

## Required Pass-2 Folds

1. Name the expected Python URL/address normalization approach:
   `urllib.parse` plus `ipaddress`, including `IPv6Address.ipv4_mapped`
   unwrapping, or an explicitly equivalent tested implementation.
2. State that all DNS A/AAAA answers must pass preflight; any forbidden answer
   refuses the hostname before network.
3. Define v1 non-GET behavior as `method_not_allowed` before network, distinct
   from `preflight_refusal_kind`, unless implementation finds migrated
   production roots that require another method and folds that into the spec.
4. Replace the loose header language with a default-deny caller-header policy
   and fixed bounded primitive-owned User-Agent.
5. Specify `spec_extension_acknowledged: str | None = None` for reserved-class
   registration, require canonical spec-extension identity in the string, and
   require queryable/logged evidence when used.
6. Name a deterministic registry constructor such as `build_fetch_registry()`
   for tests; production import-vs-first-use timing may remain implementation
   detail.
7. Specify D19/D20 `fetch_mapping` as a nested schema object with
   `fetch_type`, `threat_model_class`, `result_origin_class`,
   `destination_family`, and `class_exists`.
8. Require `_do_capability_acquire(...)` to return a deterministic refusal
   string for missing/invalid external-fetch mapping on external-HTTP
   capability payloads.
9. Make `timeout_s` bounded and non-null: refuse `None`, non-positive, and
   unbounded timeout values.

## Verdict

**RATIFY-WITH-AMENDMENTS.**

The folded spec is close. After the nine pass-2 folds above, panel pass-3 can
likely be skipped if the fold is purely textual and Claude council verifies the
anchors. If the fold introduces new registry or D19/D20 mechanism options rather
than pinning the shapes above, run panel pass-3.
