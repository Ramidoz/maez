# Codex Engineering Panel Pass 2 -- Fast-Backend Cloud Retirement Spec

**Artifact reviewed:** `docs/slices/privacy-egress-fast-backend-cloud-retirement/spec.md`
**Spec status at review:** DRAFT POST-PANEL FOLD (2026-05-23)
**Review date:** 2026-05-23
**Verdict:** RATIFY-WITH-AMENDMENTS

## Summary

The folded spec addresses the first-pass REVISE findings. It now names the real
router surfaces, explicitly closes the empty-reply cloud retry path, converts
`CloudBackend.generate(...)` into a caller-independent tombstone, adds safe audit
fields, fixes the inventory path/state, requires fresh `max(id)` canaries, and
records the in-file deprecation marker.

The second pass found three small but real tightening amendments. They were
about test exactness and implementation ambiguity, not a change to the
retirement architecture.

## Ratified First-Pass Folds

- Real router surfaces are used: `decide_policy(...)`,
  `select_backend(...)`, and `generate(...)` are the named surfaces, matching
  `core/routing/fast_backend_router.py`.
- The empty-reply retry side door is now explicit: the spec names the
  `policy="cloud"` retry branch and requires `retry_strategy` never becomes
  `cloud_fallback`.
- `CloudBackend.generate(...)` no longer relies on a caller parameter; the spec
  requires it to raise before env checks, redaction, `claude_tier.call(...)`,
  proxy calls, or provider/model request construction.
- Raise-side telemetry is content-free and must not write a proxy DB row because
  no egress occurred.
- `scripts/fast_reply_service.py` is in implementation scope, and the audit
  field set now includes `policy_requested`, `policy_effective`,
  `policy_downgraded`, `policy_rule`, and `retirement_reason_code`.
- The inventory path is corrected to
  `docs/slices/privacy-egress-gate/network_migration_allowlist.yaml`, and
  `deprecated` is treated as a deliberate lifecycle state.
- Forward proxy canaries use fresh `max(id)` baselines; the claude-router
  regression canary must insert new rows, not reuse historical row ids.
- The telemetry evidence block includes read-only commands, counts, dates, and
  the runtime-local caveat.
- The in-file deprecation marker is specified: `DEPRECATED = True`,
  `RETIREMENT_SPEC`, date, and retirement reason.

## Required Amendments From Pass 2

### 1. Pin `backend_call` To Production Call-Site Proof

The spec's first folded version allowed either a runtime guard or a production
call-site proof. The panel found that runtime callable introspection is not a
sound primary invariant: `fast_reply(..., backend_call=...)` accepts arbitrary
callables, including lambdas/wrappers whose cloud behavior cannot be reliably
classified.

Required amendment:

- Treat `backend_call` as test/bench-only.
- Require static production call-site proof as the v1 invariant.
- Explicitly include `scripts/fast_reply_service.py` and
  `scripts/fast_reply_cli.py` if present.
- Do not accept runtime callable introspection as the primary guard.
- A runtime deny/permit guard may exist only as defense-in-depth for explicitly
  marked test/bench paths.

Folded into the spec at `## backend_call Containment` and RED test #7.

### 2. Force Local-Unavailable In The `backend="auto"` Identity Canary

The folded spec required `backend="cloud"` and `backend="auto"` identity canary
coverage. The panel found that `backend="auto"` can pass trivially if local is
available, because the old leak only occurred when auto fell through to cloud.

Required amendment:

- The `backend="auto"` compact-identity canary must force local unavailable
  under cloud-enabled conditions.
- The test must then assert `claude_tier.call(...)` / proxy receives no prompt.

Folded into the spec at `## compact_identity() Containment` and RED test #9.

### 3. Specify Mandatory Local Logger For Tombstone Telemetry

The folded spec required content-free tombstone telemetry. The panel found one
implementation ambiguity: the mandatory surface should be local structured
logging, while metadata audit append can be optional best-effort.

Required amendment:

- `CloudBackend.generate(...)` must emit a local structured logger event before
  raising, wrapped in best-effort `try` / `except`.
- Optional metadata audit append is allowed but not required.
- Telemetry failure must not unblock egress.

Folded into the spec at `### Tombstone Raise Telemetry` and RED test #5.

## Additional Non-Blocking Tightening

One reviewer also recommended asserting that fast-lane router paths do not call
`CloudBackend.is_available()` after retirement. This was folded into RED test #1
as a router test that patches `CloudBackend.is_available()` to raise; fast-lane
routing must not call it.

## Post-Amendment State

After applying the pass-2 amendments, the panel has no remaining architectural
objection to canonicalization. A final human/Claude verification pass should
confirm the amended anchors, then the spec can be canonicalized as v1.

Plain version: the big door is closed correctly now. The second pass only asked
us to tighten the tests so they cannot pass accidentally: prove production never
uses the injection hook, make auto actually exercise the old cloud fallback
condition, and make the tombstone log locally before it shouts.
