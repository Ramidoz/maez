# Privacy / Egress Fast-Backend Cloud Retirement -- Spec v1

**Status:** CANONICAL v1 (2026-05-23). Docs-only. Not implemented.
**Date:** 2026-05-23
**Class:** Covenant-shaped / boundary-hardening / narrow implementation slice
**Depends on:** canonical Privacy / Egress Gate spec, canonical Privacy / Egress
Provenance Plumbing spec, canonical Privacy / Egress Claude Router Provenance
Tightening spec (commit `4721f49` / live impl `1e223f7`).
**Lanes cleared:** Codex engineering panel REVISE -> RATIFY-WITH-AMENDMENTS
(11 folds + 4 amendments applied) + Claude council pass-3 RATIFY-CLEAR. Both
lanes cleared with cross-lane behavioral-trace verification.

## Purpose

Retire cloud routing from the fast-reply path. After this slice, the fast-lane
is local-only by structural prohibition. Cloud capability remains available
through the main loop's claude-router path, where the cloud-as-tool
architecture already lives: the local Maez runtime path is the speaker, with
local inference as the final voice step, and cloud output enters as
`model_output` evidence.

Plainly: the main-loop side door has already been rebuilt correctly. The
secondary fast-lane side door still has pre-A2 plumbing: cloud can be routed to,
cloud is told it is Maez through `compact_identity()`, and cloud output can
become the user-facing reply directly. None of that fits cloud-as-tool. The
honest fix is not to rebuild this unused door in parallel; it is to close it.

## Telemetry Justification (the cut, not provenance plumbing)

This slice cuts cloud from the fast-lane rather than carrying provenance into
the fast-lane's cloud path. The cut is justified by usage data, not preference.

Forensic snapshot, 2026-05-23:

- `memory/fast_reply_audit.jsonl`: 36 rows, from 2026-04-09 21:41:19 CDT
  through 2026-04-11 14:10:59 CDT. Recorded rows are guest/local-shaped; no
  ordinary fast-lane cloud traffic is present.
- `memory/subscription_proxy.db`: 235 rows total, with exactly one
  `caller='fast_backend_cloud/generate'` row (id 229). That row is the
  direct-route closure proof from the 2026-05-22 egress arc, not ordinary
  fast-lane traffic.

The evidence is runtime-local and can drift. The implementation artifact must
record fresh commands/counts before and after canaries. The spec's evidentiary
role is to justify the retirement direction; the live acceptance proof is
forward-only behavior after the implementation lands.

Read-only evidence commands used for the draft:

```bash
.venv/bin/python - <<'PY'
import json, pathlib, time, collections
rows = [
    json.loads(line)
    for line in pathlib.Path("memory/fast_reply_audit.jsonl").read_text(
        encoding="utf-8"
    ).splitlines()
    if line.strip()
]
print("rows", len(rows))
ts = [r.get("ts") for r in rows if isinstance(r.get("ts"), (int, float))]
print("min_date", time.strftime("%Y-%m-%d %H:%M:%S %Z", time.localtime(min(ts))))
print("max_date", time.strftime("%Y-%m-%d %H:%M:%S %Z", time.localtime(max(ts))))
for key in ["trust_scope", "backend_name", "policy_effective", "policy_rule"]:
    print(key, dict(collections.Counter(str(r.get(key)) for r in rows)))
PY

.venv/bin/python - <<'PY'
import sqlite3
con = sqlite3.connect("memory/subscription_proxy.db")
cur = con.cursor()
cur.execute("select max(id), count(*) from calls")
print("max_id_count", cur.fetchone())
cur.execute("""
    select id, ts, caller, egress_decision, egress_reason_codes,
           egress_provenance_mode
    from calls
    where caller='fast_backend_cloud/generate'
    order by id
""")
print("fast_backend_cloud_rows", cur.fetchall())
con.close()
PY
```

The fast-lane cloud capability is dead code in practice. Building a
two-call cloud-consult-plus-local-synthesis path through the fast-lane would
preserve a capability nobody is exercising, double the maintenance surface, and
break the fast-lane's single-call latency promise. The honest move is the cut.

## Scope

In scope:

- `core/routing/fast_backend_router.decide_policy(...)`,
  `select_backend(...)`, and `generate(...)`: make all fast-backend router
  requests local-only; `CloudBackend` must not be selected under any fast-lane
  policy/trust-scope/env combination.
- `skills/fast_reply_prototype.py`: remove or hard-disable the empty-reply
  `cloud_fallback` retry path; `final_text` must never come from cloud output.
- `core/routing/fast_backend_cloud.CloudBackend.generate(...)`: convert to a
  tombstone that raises `FastLaneCloudRetiredError` before env checks,
  availability checks, redaction, or proxy calls.
- `core/routing/fast_backend_cloud.py`: add in-file deprecation marker,
  spec reference, retirement date, and content-free raise-side telemetry.
- `scripts/fast_reply_service.py`: extend safe audit metadata with
  `policy_requested` and a closed retirement reason code when a cloud request is
  downgraded because the fast-lane cloud path is retired.
- `core/infra/fast_reply_schema.py`: keep `backend="cloud"` only as a
  backward-compatible request value that is accepted then downgraded; it must no
  longer mean the fast-lane may invoke cloud.
- `core/infra/fast_prompt_builder.compact_identity(...)`: stays as-is because
  it now only ever reaches local inference. Documented and tested as local-only
  output.
- `docs/slices/privacy-egress-gate/network_migration_allowlist.yaml`:
  `fast_backend_cloud` route flips from `proxy_shadow` to `deprecated`, with
  inventory tests explicitly owning `deprecated` as an intentional state.
- RED tests proving fast-lane never selects cloud, retry never cloud-fallbacks,
  direct `CloudBackend.generate(...)` refuses before egress, compact identity
  never reaches cloud, and forward proxy canaries insert no new
  `fast_backend_cloud/generate` rows.

Out of scope:

- Removing `fast_backend_cloud` source code in this slice. The module stays in
  the tree as deprecated infrastructure for one canonicalize cycle; deletion is
  a later slice when no caller path could ever reach it.
- Telegram egress migration.
- Enforcement flip.
- Changes to `claude_router` or its live cloud-as-tool path, except regression
  tests proving it remains unaffected.
- Any change to `compact_identity`'s content. It remains "You are Maez ..." and
  remains local-only.

## Architecture: Structural Prohibition, Not Soft Policy

The cloud-fast-lane cut is structural, not policy theatre. A policy-level rule
("the fast-lane should not route to cloud") is a comment. A structural rule
("the fast-lane router cannot select `CloudBackend`, and the backend refuses if
directly invoked") is enforceable and testable.

The real implementation surface is:

1. `fast_backend_router.decide_policy(trust_scope, requested_policy)`
2. `fast_backend_router.select_backend(decision)`
3. `fast_backend_router.generate(prompt, policy, trust_scope, ...)`
4. `skills.fast_reply_prototype.fast_reply(...)`
5. `core.routing.fast_backend_cloud.CloudBackend.generate(...)`

There is no separate private selector in the current code. This spec must name
the real surfaces above, not invented ones.

Two complementary mechanisms:

1. **Router local-only invariant.** `decide_policy(...)` / `select_backend(...)`
   make all fast-backend router calls local-only:
   - `policy="cloud"` is accepted as a legacy request but downgraded to local.
   - `policy="auto"` remains local-first and cannot cloud-fallback if local is
     unavailable.
   - cloud-eligible scopes under prior code, including `owner.draft` and the
     default rule, no longer allow fast-lane `CloudBackend` selection.
   - if local is unavailable, the router returns a no-backend/degraded-local
     result with `fast_lane_cloud_retired`; it does not route to cloud.

2. **Backend tombstone.** `CloudBackend.generate(...)` always raises
   `FastLaneCloudRetiredError` before any egress-capable work. It must raise
   before:
   - environment availability checks,
   - `cloud_redactor.redact_for_cloud(...)`,
   - `claude_tier.call(...)`,
   - subscription proxy calls,
   - provider/model selection that could look like an active cloud path.

The first mechanism is the normal path. The second is defense-in-depth: if a
future refactor reintroduces a direct call to `CloudBackend.generate(...)`, the
call is refused before egress and leaves a content-free local diagnostic trail.
Any optional caller label is telemetry only, never permission.

## Empty-Reply Retry Closure

The fast-lane has a second cloud entry point after the initial backend call:
`skills/fast_reply_prototype.py` can run a sharper local retry and then, under
prior policy, fall through to `fast_backend_router.generate(..., policy="cloud")`
with `retry_strategy="cloud_fallback"`.

This slice retires that branch too. After implementation:

- `retry_strategy` must never be `cloud_fallback`.
- local empty/non-visible reply followed by local empty/non-visible retry
  degrades locally to `DEGRADED_REPLY_TEXT` (or equivalent current degraded
  reply), not cloud output.
- cloud text must never be assigned to `final_text`.
- the behavioral test must exercise the retry path, not merely grep for branch
  text.

This is load-bearing: closing only the initial route while leaving retry cloud
fallback would preserve the exact side door this spec exists to close.

## `backend_call` Containment

`fast_reply(..., backend_call=...)` is an injection hook for benches and tests.
It bypasses the router and can run arbitrary backend behavior if misused.

This slice treats `backend_call` as test/bench-only. The v1 invariant is static
production call-site proof, not callable introspection: an arbitrary lambda or
wrapper cannot be reliably classified as cloud-backed at runtime.

Implementation must prove that production fast-lane callers do not pass any
`backend_call` into `fast_reply(...)`, and especially do not pass
`CloudBackend.generate`, `claude_tier.call`, or proxy-backed cloud functions.
The production proof must include `scripts/fast_reply_service.py` and
`scripts/fast_reply_cli.py` if present. A runtime deny/permit guard may be added
as defense-in-depth for explicitly marked test/bench paths, but it is not the
primary invariant.

## Schema Compatibility

`core/infra/fast_reply_schema.py` currently accepts
`VALID_BACKENDS = {"auto", "local", "cloud"}`. This slice may keep
`backend="cloud"` as a backward-compatible request value, but the meaning
changes:

- `backend="cloud"` means "cloud requested by caller."
- The router records `policy_requested="cloud"`.
- The router/audit records `policy_effective="local"` and
  `retirement_reason_code="fast_lane_cloud_retired"`.
- The request does not reach `CloudBackend`.

Rejecting `backend="cloud"` at schema validation time is allowed only if the
implementation chooses a visible API break and updates tests/docs accordingly.
The preferred v1 path is accept-and-downgrade.

## Audit And Raise-Side Telemetry

Graceful downgrades and defense-in-depth raises have different telemetry
surfaces.

### Fast-Reply Audit Rows

`scripts/fast_reply_service.py` currently writes metadata-only audit rows. This
slice extends that safe metadata schema; it must not log raw prompt text or raw
reply text.

Required fields after this slice:

- `policy_requested`
- `policy_effective`
- `policy_downgraded`
- `policy_rule`
- `retirement_reason_code` (closed value:
  `fast_lane_cloud_retired` when applicable)

The audit row for a caller that requested cloud must show the request honestly:
requested cloud, effective local, reason retired.

### Tombstone Raise Telemetry

If `CloudBackend.generate(...)` is directly invoked, it raises
`FastLaneCloudRetiredError` and emits a content-free structured log/audit event
before raising. The mandatory surface is a local structured logger call wrapped
in best-effort `try` / `except`; a metadata-only audit append is optional
defense-in-depth. Suggested fields:

- `event="fast_lane_cloud_retired_refused"`
- `backend="fast_backend_cloud"`
- `spec="docs/slices/privacy-egress-fast-backend-cloud-retirement/spec.md"`
- `prompt_chars`
- optional `caller_label` if an implementation supplies one for telemetry

No proxy DB row should be written for this event because no egress occurred.
Telemetry/log failure must not unblock egress.

## `compact_identity()` Containment

The identity material in `compact_identity()` -- "You are Maez, a persistent
local AI companion built by the owner. ..." -- is honest local-side instruction.
It tells local inference what it is. It is correct on the local path and an A2
violation on the cloud path.

Under this slice, `compact_identity()` and `COMPACT_IDENTITY` are reachable only
from local-bound prompt construction. The content is not changed. It continues
to assert Maez identity to local inference, because that is where the speaker
actually lives.

The test contract is bounded static plus behavioral:

- Static/AST checks over `core/routing/fast_backend_cloud.py` and known
  cloud-call modules for direct imports or references to `compact_identity`,
  `COMPACT_IDENTITY`, or `build_fast_prompt`.
- Behavioral canary that builds or patches a fast prompt containing the compact
  identity string, attempts `backend="cloud"` under cloud-enabled conditions,
  then attempts `backend="auto"` under cloud-enabled plus local-unavailable
  conditions, and proves `claude_tier.call(...)` / the proxy boundary receive no
  prompt.

The behavioral canary is load-bearing. A broad "transitive dependencies" check
is too brittle and does not prove the real leak is closed.

## `cloud_redactor` Status

`core/cloud_redactor.redact_for_cloud(...)` stays in the tree as
defense-in-depth on any remaining cloud-capable paths. It is explicitly not the
source of truth for egress provenance; the provenance gate at the proxy boundary
is.

After this slice, `cloud_redactor` must not run inside the fast-lane because
there is no fast-lane cloud path to redact. When `fast_backend_cloud` is fully
removed in a later slice and the only remaining cloud path is claude-router with
full provenance plumbing, `cloud_redactor` becomes a candidate for retirement or
repurposing as a within-span redaction subroutine. That is a separate later
decision.

## Inventory State

The inventory file is:

`docs/slices/privacy-egress-gate/network_migration_allowlist.yaml`

This slice changes the `core/routing/fast_backend_cloud.py` /
`CloudBackend.generate` entry from `proxy_shadow` to `deprecated`.

Implementation must extend inventory tests deliberately:

- `deprecated` is an explicit accepted lifecycle state.
- the fast-backend cloud entry is asserted to be `deprecated`;
- its rationale names this retirement spec/date/reason;
- the old direct-cloud-route expectation that `removal_target` contains
  `proxy` is updated for the retired state.

This is a closed-inventory change, not an ad hoc status string.

## In-File Deprecation Marker

`core/routing/fast_backend_cloud.py` remains in the tree for one canonicalize
cycle but must declare its retired status in-file. Required marker shape:

- `DEPRECATED = True`
- `RETIREMENT_SPEC =
  "docs/slices/privacy-egress-fast-backend-cloud-retirement/spec.md"` (or a
  comparable constant)
- retirement date `2026-05-23`
- short reason: fast-lane cloud path retired; cloud remains available through
  main-loop claude-router cloud-as-tool path

Future readers should not need to discover the inventory yaml before learning
that this backend is retired.

## Backward Compatibility

- Existing fast-reply caller signatures remain unchanged unless the
  implementation chooses to visibly reject `backend="cloud"` at schema
  validation. Preferred v1 behavior is accept-and-downgrade.
- Existing `backend="auto"` and `backend="cloud"` callers receive local or
  degraded-local behavior. They do not receive cloud output.
- Existing service audit rows gain safe metadata fields. Raw prompt/reply text
  remains forbidden.
- Direct callers of `CloudBackend.generate(...)` begin receiving
  `FastLaneCloudRetiredError`. This is intentional; a hidden caller is exactly
  what the tombstone must expose.
- The main-loop claude-router cloud path is untouched. Cloud capability still
  exists; it lives where cloud-as-tool is already implemented.

## No-Inference Invariant

Mirrors the canonical claude-router spec. Origin of fast-lane traffic is not
inferred from prompt content. The fast-lane is local-only by route, not by
content classification. There is no string-scanning, no heuristic, no "this
looks like an owner message" gating. If a caller wants cloud capability, the
caller uses the main-loop claude-router path, which has provenance plumbing.

## RED Tests

Write failing tests before implementation:

1. **Router selection cannot choose cloud.** `decide_policy(...)` /
   `select_backend(...)` / `generate(...)` never select `CloudBackend` for
   `policy="cloud"`, `policy="auto"`, cloud-enabled env, local unavailable,
   `owner.draft`, default, or guest scopes. Previous cloud-eligible cases become
   local/degraded-local with `fast_lane_cloud_retired`. Patch
   `CloudBackend.is_available()` to raise in at least one router test; fast-lane
   routing must not call it.

2. **Schema cloud request is downgraded or rejected deliberately.** If
   `backend="cloud"` remains schema-valid, it is accepted only as a legacy
   request and audit/metrics show requested cloud, effective local, retired
   reason. If the implementation rejects it at schema validation, tests assert
   the explicit rejection shape.

3. **Empty-reply retry cloud fallback is closed.** Initial local generation and
   sharper local retry are forced empty/non-visible under a previously
   cloud-eligible policy. The result does not call cloud, does not set
   `retry_strategy="cloud_fallback"`, and does not assign cloud text to
   `final_text`.

4. **`CloudBackend.generate(...)` tombstone.** Direct invocation raises
   `FastLaneCloudRetiredError` before env checks, redaction, `claude_tier.call`,
   subscription proxy calls, or provider/model request construction.

5. **Tombstone raise telemetry is content-free.** The raise emits a structured
   local logger event naming the retirement spec and prompt char count, with no
   raw prompt or reply text. Optional metadata audit append is best-effort only.
   Telemetry failure does not unblock egress.

6. **Audit row honesty.** A fast-lane request that previously would have routed
   to cloud now emits a metadata-only audit row with `policy_requested`,
   `policy_effective=local`, `policy_downgraded` when applicable, and
   `retirement_reason_code=fast_lane_cloud_retired`.

7. **`backend_call` production containment.** Static production call-site tests
   prove production fast-lane callers, including `scripts/fast_reply_service.py`
   and `scripts/fast_reply_cli.py` if present, do not pass `backend_call` into
   `fast_reply(...)`. The hook remains test/bench-only. Runtime callable
   introspection is not accepted as the primary guard.

8. **`compact_identity()` static boundary.** `core/routing/fast_backend_cloud.py`
   and known cloud-call modules do not directly import or reference
   `compact_identity`, `COMPACT_IDENTITY`, or `build_fast_prompt`.

9. **`compact_identity()` behavioral boundary.** A fast prompt containing the
   compact identity string attempts `backend="cloud"` under cloud-enabled
   conditions, then attempts `backend="auto"` under cloud-enabled plus
   local-unavailable conditions. `claude_tier.call(...)` and the proxy boundary
   receive no prompt.

10. **No proxy DB rows under `caller=fast_backend_cloud/generate` after
    retirement.** Snapshot proxy DB `max(id)` before fast-lane canaries; run
    repeated fast-reply canaries under `backend="cloud"`, `backend="auto"`,
    local-down/empty-retry conditions, and prior cloud-eligible scopes; assert
    no rows with `id > before_max_id` and
    `caller='fast_backend_cloud/generate'`.

11. **`fast_backend_cloud` module deprecation marker.** The module has
    `DEPRECATED = True`, a retirement spec reference, date, and reason. Test
    asserts the marker on the real module, not a shim.

12. **Inventory yaml flips deliberately.**
    `docs/slices/privacy-egress-gate/network_migration_allowlist.yaml` shows
    `fast_backend_cloud` as `deprecated`; inventory tests explicitly own the
    `deprecated` state and targeted rationale.

13. **claude-router unaffected with fresh canary.** Snapshot proxy DB `max(id)`,
    invoke the claude-router cloud-as-tool consult path with fresh canary input,
    and assert newly inserted `caller='claude_router/call_claude'` span-bundle
    rows with expected cloud-as-tool / `model_output` shape. Do not reuse old
    row ids as evidence.

## Acceptance Bar

- RED-first evidence: new tests fail on the pre-implementation state for the
  expected reasons.
- Focused tests pass after implementation.
- Live verification after deliberate restart:
  - A synthetic fast-reply request that previously would have routed to cloud
    routes to local instead and produces a visible reply or explicit
    degraded-local reply.
  - The audit row for that request reflects requested cloud, effective local,
    and `fast_lane_cloud_retired`.
  - Snapshot `max(id)` in `memory/subscription_proxy.db` before fast-lane
    canaries; no new rows appear with
    `caller='fast_backend_cloud/generate'` after fast-lane canaries.
  - A fresh main-loop claude-router canary still works end-to-end and inserts
    new span-bundle proxy rows after the baseline id.
- The `compact_identity()` behavioral containment test stays green; identity
  material does not reach `claude_tier.call(...)` or proxy from fast-lane
  routing.
- `fast_backend_cloud` module remains in the tree, marked `DEPRECATED`, with
  the deprecation reason naming this spec and the date.
- No enforcement flip, no autonomy change, no Telegram migration, no daemon or
  proxy disruption outside the deliberate observed restart.

## Removal Follow-Up (later slice, not this one)

After one canonicalize cycle with the fast-lane cloud path proven structurally
unreachable in live traffic, a follow-up slice deletes
`core/routing/fast_backend_cloud.py` and any compatibility shims.

Deletion preconditions:

- At least two consecutive weeks of ordinary traffic with zero new proxy rows
  under `caller='fast_backend_cloud/generate'`.
- No production caller uses `CloudBackend`.
- `network_migration_allowlist.yaml` shows the route as deprecated.
- Telegram migration decision has been handled separately.
- claude-router remains the exclusive cloud reasoning path.

Until deletion, the module stays as a tombstone so accidental imports fail
closed and visibly.

## Expected Shadow / Live Decisions

Because the fast-lane no longer reaches cloud:

- fast-lane cloud-request canaries should not create proxy rows;
- fast-lane `backend="cloud"` request should yield local/degraded-local audit
  metadata with `fast_lane_cloud_retired`;
- direct `CloudBackend.generate(...)` should raise before proxy;
- claude-router canaries should continue producing normal proxy rows with
  span-bundle provenance.

No egress-gate enforcement flip is implied by this slice. The proxy remains in
shadow/non-enforcing mode until the broader enforcement criteria are met.

## Plain-Language Summary

The fast lane used to have a little cloud escape hatch. That hatch was barely
used, and when it was used it had the old wrong shape: the cloud could be told
to be Maez, and cloud words could become the final reply. This spec retires
that hatch instead of rebuilding it. Fast replies stay local. Cloud help still
exists, but it goes through the main loop where Maez stays the speaker and cloud
is only a tool.
