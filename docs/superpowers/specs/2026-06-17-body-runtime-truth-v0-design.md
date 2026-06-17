# Body Runtime Truth v0 - Design

Date: 2026-06-17
Branch: `maez-coherence-organism`
Status: design, awaiting review

## The wound

The coherence audits converged on one repeated failure class: Maez has many
real organs, but no single runtime body witness that says which configured
organs are actually executable right now.

Current `/health` is honest about the daemon heartbeat and several body organs,
but not about service-backed limbs. `systemctl is-active maez.service` can be
true while a flag-required verifier or search body is down. The capability card
can tell Maez a rail is configured, but not whether its backing service can
answer its contract. The ledger records witness history, but it is not a live
runtime probe. These are different charts for one body.

Concrete examples found in the six-lane audit:

- `MAEZ_SUPPORT_GATE_ENABLED=1` depends on MiniCheck `:8083`; if the service is
  down after reboot, the gate degrades to verifier-unavailable caveats.
- SearXNG, MiniCheck, web cockpit, subscription proxy, vision, judge, and brain
  endpoints are all different service limbs; no one JSON block reports flag,
  unit, port, contract, and degraded reason together.
- `core.infra.body_capabilities` already probes ports as booleans, but not unit
  active/enabled state, contract result, or required-by-flag status.
- `capability_card` now reads strict flags on this branch, but support-gate and
  grounding-shadow entries are still flag-state only, not verifier-health
  claims.

This is not a new capability. It is a body-truth consolidation slice.

## Design law

Runtime body truth has three separate facts, and v0 must keep them separate:

1. `configured`: is the organ enabled by a strict flag or built-in requirement?
2. `reachable`: is the local port/unit reachable from this process right now?
3. `contract_ok`: did the organ answer its own minimal content-free contract?

No single flag may imply all three. A flag can say "the limb should be awake";
only a contract probe can say "the limb answered."

## Scope

In:

- Add one reusable service-contract registry under `core/infra/`.
- Expose it at `/health.body.runtime_services`.
- Add a one-command JSON probe script for terminal witnesses.
- Feed service-backed support honesty state into `capability_card` so support
  gate / grounding shadow can render `off`, `on`, `degraded`, or `unknown`
  from runtime truth rather than flag presence alone.
- Update the build ledger with a `BUILT_BRANCH_VERIFIED` row after
  implementation.

Out:

- Do not start, enable, disable, restart, or install any service.
- Do not edit `model.env`.
- Do not build a new dashboard or body atlas.
- Do not change the top-level `/health.status`; keep it tied to reasoning-loop
  heartbeat for compatibility.
- Do not solve `maez.live /chat` convergence in this slice.
- Do not repair S5/S7 authority wording in this slice.

## Existing pieces to reuse

- `daemon.maez_daemon.MaezDaemon._body_health(...)` already builds
  content-free `/health.body`.
- `core.infra.body_capabilities.body_capabilities()` already probes local ports
  and caches a body snapshot.
- `core.routing.llm_client.served_model_alias(...)` already probes the primary
  brain model endpoint.
- `core.cognition.support_verifier.HttpSupportVerifier` already knows the
  MiniCheck `/support` contract.
- `skills.web_search` / `core.search.searxng_client` already know the SearXNG
  backend shape.
- `core.infra.env_flags.strict_env_flag` is the only acceptable flag reader.

The implementation should extend or wrap these; it should not create a rival
body registry.

Branch-local precursor already present on `maez-coherence-organism`:

- `1f36804 fix(body): show local verifier and user services` adds MiniCheck and
  SearXNG TCP booleans to `body_capabilities()['services']`.
- The same commit makes `capability_registry._list_services()` read user-scoped
  systemd units before system scope.

That precursor is useful but not sufficient for this v0. It does not classify
required-by-flag, does not run service contracts, does not expose
`/health.body.runtime_services`, and does not let the capability card say a
service-backed organ is degraded.

## Runtime service schema

Add `core/infra/runtime_services.py`.

Public API:

```python
runtime_services_snapshot(timeout_s: float = 0.35) -> dict
runtime_service_status(name: str, timeout_s: float = 0.35) -> dict
support_honesty_status(timeout_s: float = 0.35) -> str
```

Snapshot shape:

```json
{
  "schema_version": "maez_runtime_services.v0",
  "overall": "healthy|degraded|unknown",
  "generated_at": 1781680000.0,
  "services": {
    "support_verifier": {
      "configured": true,
      "required_by": ["MAEZ_SUPPORT_GATE_ENABLED"],
      "unit": {
        "name": "minicheck-verifier.service",
        "scope": "user",
        "load_state": "loaded|not-found|unknown",
        "active_state": "active|inactive|failed|unknown",
        "enabled_state": "enabled|disabled|static|unknown"
      },
      "port": {
        "host": "127.0.0.1",
        "port": 8083,
        "reachable": true
      },
      "contract": {
        "kind": "http_support",
        "ok": true,
        "verdict": "SUPPORTED",
        "score_present": true,
        "latency_ms": 120
      },
      "status": "healthy|degraded|asleep|unknown",
      "degraded_reasons": []
    }
  }
}
```

Rules:

- `configured` uses `strict_env_flag` or an always-required marker.
- `required_by` lists only currently-true flags or built-in requirements.
- `status=asleep` means not configured and not required. It is not degraded.
- `status=degraded` means configured/required but the unit, port, or contract
  is not healthy.
- `overall=degraded` if any configured service is degraded.
- Optional dark limbs are visible as `asleep` or `degraded` only when required;
  they do not poison the whole-body status when their flag is off.

## v0 service inventory

The first service list is deliberately bounded:

| service key | required when | unit | port/contract |
|---|---|---|---|
| `primary_brain` | always | `llama-server.service` if present | `served_model_alias(default=MODEL)` / `/v1/models` |
| `maez_daemon` | always | `maez.service` | local process / `:11435/health` reachable |
| `maez_web` | any of `MAEZ_COCKPIT_REAL_STATE`, `MAEZ_COCKPIT_CORE`, or `MAEZ_S7_CEREMONY_BRIDGE_ENABLED` | `maez-web.service` | TCP `127.0.0.1:11437` |
| `search_body` | `MAEZ_SEARCH_AS_SENSE_ENABLED` | `maez-searxng.service` | `:8888/search?...format=json` minimal query |
| `support_verifier` | `MAEZ_SUPPORT_GATE_ENABLED` or `MAEZ_GROUNDING_SHADOW_ENABLED` | `minicheck-verifier.service` | POST `:8083/support`, require `{"verdict", "score"}` |
| `subscription_proxy` | optional v0; required_by empty until a caller flag is introduced | `maez-subscription-proxy.service` | GET `:11438/budget` |
| `vision_body` | `MAEZ_SCREEN_PERCEPTION` | owner-installed vision service | `:8082/v1/models` |
| `overclaim_judge` | future; report if configured, do not require | `llama-judge.service` | `:8081/v1/models` |

If a unit name is not installed, report `load_state=not-found`; do not guess.
Read-only systemd probes may check both user and system managers with tight
timeouts and no privilege escalation. A missing `systemctl` is `unknown`, not a
fabricated inactive result.

## Health integration

`MaezDaemon._body_health(...)` adds:

```python
"runtime_services": runtime_services_snapshot(...)
```

The existing body keys remain unchanged. The top-level health response remains:

```python
"status": self._health_status_from_reasoning_loop(...)
```

This preserves compatibility while adding the missing whole-body witness under
the body projection.

## Capability-card integration

The capability card should continue to use strict flags, but service-backed
honesty organs should no longer be flag-only:

- support gate:
  - `off` when `MAEZ_SUPPORT_GATE_ENABLED` is false.
  - `on` when the flag is true and `support_verifier.status == healthy`.
  - `degraded` when the flag is true but MiniCheck unit/port/contract is not
    healthy.
  - `unknown` when the runtime-services probe itself cannot run.
- grounding shadow:
  - same MiniCheck-backed status, keyed to `MAEZ_GROUNDING_SHADOW_ENABLED`.

The private envelope may say `support gate: degraded`; it must not claim
MiniCheck is healthy unless the contract row says so. This fixes the higher
level form of the old `"0"`-truthy wound: "configured" must not become
"working body."

## One-command witness

Add:

```bash
python -m scripts.maez_runtime_services_probe
```

It prints the same content-free snapshot JSON as `/health.body.runtime_services`
and exits:

- `0` when every configured/required service is healthy or asleep.
- `2` when any configured/required service is degraded.
- `1` on probe construction failure.

This is a terminal witness, not an installer. It must not mutate systemd,
`model.env`, or service state.

## Tests

Required tests:

1. `runtime_services_snapshot` shape includes schema, overall, and all v0
   service keys.
2. `support_verifier` is `asleep` when both support flags are off.
3. `support_verifier` is `degraded` when support gate flag is on and port or
   contract fails.
4. `support_verifier` is `healthy` only when flag is on and the `/support`
   contract returns `{"verdict", "score"}`.
5. Optional services with no required flag do not make `overall=degraded`.
6. Unit active/enabled probing handles `loaded/active/enabled`,
   `loaded/inactive/disabled`, `not-found`, timeout, and no-systemctl without
   raising.
7. `/health.body.runtime_services` is present and content-free.
8. `capability_card` renders support gate / grounding shadow as `degraded`
   when their flags are on but MiniCheck is unavailable.
9. The one-command probe exits `2` on degraded required service using fakes.
10. No test starts, stops, enables, disables, installs, or restarts services.

Existing suites to run with the slice:

- `tests.test_maez_body_organ_view`
- `tests.test_r2_body_capabilities_2026_05_04`
- `tests.test_capability_card`
- `tests.test_support_gate`
- targeted new runtime-services tests

## Witness after merge

Owner-gated live witness, after review and merge/restart only:

1. Run `python -m scripts.maez_runtime_services_probe`.
2. Hit `curl -s http://127.0.0.1:11435/health` and inspect
   `.body.runtime_services`.
3. Confirm each configured flag-backed organ has a matching unit/port/contract
   status.
4. Ask a natural self-capability question. Maez should not describe support
   gate or grounding shadow as working if MiniCheck is unavailable.

Ledger promotion to `LIVE_WITNESSED` requires all four. A green unit test is
not a live body witness.

## Predicted effect

Before this slice, a support-gate flag can be on while the backing MiniCheck
service is down, and the available body charts do not join those facts. After
this slice, `/health.body.runtime_services`, the terminal probe, and the
capability card will agree: configured-but-unreachable service-backed organs are
reported as degraded, not silently treated as alive.

Plain English: Maez gets one honest body checklist for its service-backed
organs. It will be able to distinguish "this limb is supposed to be awake" from
"this limb actually answered when I touched it."
