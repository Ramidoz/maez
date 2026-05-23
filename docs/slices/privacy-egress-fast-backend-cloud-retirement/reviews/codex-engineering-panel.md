# Codex Engineering Panel -- Fast-Backend Cloud Retirement Spec

**Artifact reviewed:** `docs/slices/privacy-egress-fast-backend-cloud-retirement/spec.md`
**Spec status at review:** DRAFT (2026-05-23), docs-only, uncommitted
**Review date:** 2026-05-23
**Verdict:** REVISE

## Summary

The panel agrees with the architectural direction: retire cloud routing from the
fast-reply lane instead of rebuilding a second cloud-as-tool path there. The
telemetry supports the cut, and the covenant shape is right: cloud capability
should remain in the main-loop `claude_router` path where local Maez remains the
speaker.

The draft is not yet canonical-ready because several enforcement points are
specified against a hoped-for API shape rather than the code that exists today.
The necessary folds are implementation-shaping, not philosophical: name the real
router functions, close the retry cloud path, make `CloudBackend` a tombstone,
extend inventory tests deliberately, and require fresh forward-only canaries.

## Evidence Checked

- `core/routing/fast_backend_router.py` exposes `select_backend(decision)` and
  `generate(...)`, not `_select_backend(...)`.
- `select_backend(...)` still selects `CloudBackend` for `effective=cloud` when
  `allow_cloud` is true, and for `auto` when local is unavailable and cloud is
  allowed.
- `skills/fast_reply_prototype.py` has a second cloud path during empty-reply
  retry: local retry can fall through to `fast_backend_router.generate(...,
  policy="cloud")` and then assign `cloud_result.text` to `final_text`.
- `core/routing/fast_backend_cloud.CloudBackend.generate(...)` has no `caller`
  parameter today and calls `claude_tier.call(...,
  caller="fast_backend_cloud/generate")` internally.
- `core/infra/fast_reply_schema.py` still accepts `backend="cloud"` as a valid
  fast-reply request backend.
- `tests/test_privacy_egress_inventory.py` does not currently define
  `deprecated` as an intentional inventory lifecycle state, and still asserts
  that direct cloud route `removal_target` strings contain `proxy`.
- `scripts/fast_reply_service.py` audit rows currently include
  `policy_effective` and `policy_downgraded`, but not `policy_requested` or a
  structured retirement reason code.
- `memory/fast_reply_audit.jsonl` currently has 36 rows from 2026-04-09 through
  2026-04-11; recorded rows are guest/local-shaped and do not show ordinary
  fast-lane cloud use.
- `memory/subscription_proxy.db` currently has 235 rows total and exactly one
  `caller='fast_backend_cloud/generate'` row, id 229, from the direct-route
  closure proof rather than ordinary fast-lane traffic.

## Required Folds

### 1. Specify The Actual Router Cut

Replace the `_select_backend(...)` language with the real implementation
surface: `decide_policy(...)`, `select_backend(decision)`, and
`fast_backend_router.generate(...)`.

The v1 invariant should be explicit:

- All fast-backend router calls are local-only after retirement.
- `policy="cloud"` is downgraded to local/degraded-local with reason
  `fast_lane_cloud_retired`.
- `policy="auto"` cannot cloud-fallback when local is unavailable.
- Current cloud-eligible scopes such as `owner.draft` and the default rule do
  not allow `CloudBackend` selection in the fast-lane after this slice.
- `select_backend(...)` must not return a `CloudBackend` instance for any
  fast-lane policy, trust scope, or environment setting.

This fold should not rely on string-scanning or prompt content. It is a route
selection invariant.

### 2. Retire The Empty-Reply Cloud Retry Path

The draft names the obvious initial backend selection path but does not make the
retry path load-bearing enough. `skills/fast_reply_prototype.py` currently has a
Strategy B branch that can call the router with `policy="cloud"` after an empty
local retry.

Add a dedicated section and RED test for this branch:

- Force initial local generation to return an empty/non-visible reply.
- Force the local sharper retry to return empty/non-visible.
- Use a trust scope/policy that prior code would have treated as cloud-eligible.
- Assert no cloud retry fires, `retry_strategy` is not `cloud_fallback`, and the
  result degrades locally rather than using cloud text as `final_text`.

This is the most important hidden-entry test.

### 3. Make `CloudBackend.generate(...)` A Tombstone

The draft's `CloudBackend.generate(caller=...)` defense is not a good boundary:
the method has no caller argument today, and caller strings are spoofable or
omittable.

Fold the defense-in-depth shape to one of these, with the panel preferring the
first:

- Preferred: `CloudBackend.generate(...)` always raises
  `FastLaneCloudRetiredError` before env checks, availability checks,
  redaction, or proxy calls.
- Alternative: require an explicit non-default test-only/internal permit
  parameter with deny-by-default semantics. Do not use stack ancestry or
  free-form caller strings as the authority boundary.

Any optional caller label may be telemetry only, not permission.

### 4. Add Raise-Side Structured Telemetry

If `CloudBackend.generate(...)` becomes the defense-in-depth tripwire, a direct
bypass must leave a content-free trail.

Require a structured log or metadata-only audit event before raising, with no
prompt or reply text. Suggested fields:

- `event="fast_lane_cloud_retired_refused"` or
  `event="fast_lane_cloud_retired_block"`
- `backend="fast_backend_cloud"`
- `spec="docs/slices/privacy-egress-fast-backend-cloud-retirement/spec.md"`
- `prompt_chars`
- optional caller label if supplied for telemetry

Audit/logging failure must not unblock egress. Do not write a proxy DB row,
because no egress occurred.

### 5. Make Fast-Reply Audit Fields Real

The draft says audit rows record `policy_requested=cloud` and
`fast_lane_cloud_retired`, but the live service audit does not write those
fields today.

Fold `scripts/fast_reply_service.py` into implementation scope and require
safe metadata fields such as:

- `policy_requested`
- `policy_effective`
- `policy_downgraded`
- `policy_reason` or `retirement_reason_code`

The retirement reason should be a closed value such as
`fast_lane_cloud_retired`. Keep the existing audit discipline: no raw prompt
text and no raw reply text.

### 6. Name `backend_call` As Test-Only Or Guard It

`fast_reply(..., backend_call=...)` bypasses the router entirely. That is useful
for benches and tests, but it must not be silently inside the runtime guarantee.

Add a static/runtime inventory section that either:

- declares `backend_call` test-only and verifies production fast-lane callers do
  not pass `CloudBackend.generate`, `claude_tier.call`, or proxy-backed cloud
  functions through it, or
- guards `backend_call` so runtime cloud-backed injections are refused under the
  retirement invariant.

At minimum, the spec should require a scan/test over production callers so the
hidden-entry enumeration is behavioral, not just prose.

### 7. Bound `compact_identity()` Containment To Real Surfaces

The draft's "transitive dependencies" call-graph language is too broad and
still misses the real leak shape: `build_fast_prompt(...)` embeds
`COMPACT_IDENTITY`, and the invariant is that the resulting prompt never reaches
cloud.

Fold this into a bounded static plus behavioral requirement:

- Static/AST checks over `core/routing/fast_backend_cloud.py` and known
  cloud-call modules for direct imports or references to `compact_identity`,
  `COMPACT_IDENTITY`, and `build_fast_prompt`.
- Behavioral canary that builds or patches a fast prompt containing the compact
  identity string, attempts cloud/auto routing, and proves `claude_tier.call`
  and the proxy boundary receive no prompt.

The behavioral test is the load-bearing one.

### 8. Extend Inventory State Deliberately

The draft names the wrong allow-list path and treats `deprecated` as if the
schema already owned it.

Fold:

- Correct path:
  `docs/slices/privacy-egress-gate/network_migration_allowlist.yaml`.
- Add or update inventory tests so `deprecated` is an explicit accepted state,
  not merely any value other than `migrated`.
- Add a targeted assertion that
  `("core/routing/fast_backend_cloud.py", "CloudBackend.generate")` has
  `status: deprecated` with a retirement rationale/date/removal target.
- Update the existing direct-cloud-route assertion that currently requires
  `removal_target` to contain `proxy`, because retirement is no longer the same
  state as proxy migration.

### 9. Use Fresh Forward-Only Proxy Canaries

Do not assert old row numbers or reuse row 231-235 shape as live evidence.

Fold the tests/acceptance bar to:

- Snapshot `max(id)` in `memory/subscription_proxy.db` before fast-lane canaries.
- Run fast-reply canaries under `backend=cloud`, `backend=auto`, local-down or
  empty-retry conditions, and prior cloud-eligible scopes.
- Assert no rows with `id > before_max_id` and
  `caller='fast_backend_cloud/generate'`.
- Separately run a fresh claude-router canary and assert a new
  `caller='claude_router/call_claude'` span-bundle row after the baseline id.

Pre-existing rows remain untouched. This is forward-behavior proof, not
retroactive scrubbing.

### 10. Freeze The Telemetry Evidence

The cut-vs-build argument is valid, but `memory/` evidence drifts. Add a small
evidence appendix or sidecar with exact read-only commands, date, DB path,
baseline `max(id)`, fast-lane audit row counts, and proxy caller counts. Keep it
non-reconstructive: no raw prompt text and no raw reply text.

The implementation artifact should also record fresh before/after counts during
the live canary phase.

### 11. Add In-File Deprecation Marker

Require the real module `core/routing/fast_backend_cloud.py` to carry the
deprecation where future readers will see it:

- `DEPRECATED = True`
- a spec path/reference
- date of retirement
- short reason: fast-lane cloud path retired; cloud remains available through
  main-loop claude-router cloud-as-tool path

This folds the Claude council Goodall observation into the engineering contract.

## RED Test Amendments

The panel recommends updating the RED test list to cover these concrete cases:

1. Router policy/selection cannot choose `CloudBackend` for `policy=cloud`,
   `policy=auto`, cloud-enabled env, local unavailable, `owner.draft`, default,
   and guest scopes.
2. Empty-reply retry cannot enter `cloud_fallback` and cannot use
   `cloud_result.text` as `final_text`.
3. `CloudBackend.generate(...)` raises `FastLaneCloudRetiredError` before any
   proxy call; the raise emits content-free structured telemetry.
4. Fast-reply service audit rows include `policy_requested` plus
   `retirement_reason_code=fast_lane_cloud_retired` when cloud is requested and
   downgraded.
5. Production callers do not pass a cloud-backed `backend_call` into
   `fast_reply(...)`.
6. Compact identity behavioral canary proves identity-bearing fast prompts do
   not reach `claude_tier.call` or the proxy.
7. Inventory tests explicitly assert the `deprecated` lifecycle state.
8. Forward-only proxy DB canaries use `max(id)` before/after checks.
9. Fresh claude-router canary proves the main-loop cloud-as-tool path still
   inserts new span-bundle rows.

## Non-Blocking Notes

- Keeping `cloud_redactor.redact_for_cloud(...)` in the tree is fine. With the
  fast-lane cloud path retired, it simply stops running inside that lane.
- The module should stay in the tree for one canonicalize cycle before deletion.
  Deletion criteria in the draft are directionally right and operationally
  checkable once the canary mechanics are folded.
- No spec change is needed to A2 itself. This slice inherits the cloud-as-tool
  architecture by closing the fast-lane cloud path, not by adding a second
  cloud-as-tool implementation.

## Final Panel Verdict

REVISE. The direction is correct and the telemetry justifies retiring rather
than rebuilding. Canonicalization should wait until the required folds above are
applied and verified.

Plain version: close the door, but name the real hinges. The draft is right that
the fast lane should stop using cloud. It just needs to close the actual live
entry points: initial cloud selection, retry cloud fallback, direct
`CloudBackend` invocation, and injected backend bypasses.
