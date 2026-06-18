# Cockpit Real-State Bridge (organ) — design

**Date:** 2026-06-18. Co-designed with Rohit.
**Status:** design approved (always-on auth hardening + flag-gated real-state source); 5 spec
refinements folded. Awaiting spec review before planning.
**Arc:** decompose-the-organism ([[project_organism_decompose_organs]]), **Organ 2**. Organ 1 (runtime
body truth) is LIVE_WITNESSED. This is the first organ that secures a LIVE nerve between the web body
and the daemon.

## Why this exists — HARDEN the existing bridge, do NOT rebuild it

**The real-state bridge already exists on `main`** (it survived the revert) — but it is **exposed and
unauthenticated**. This organ puts the proper skin around it; it does **not** build it from scratch.
A builder must MODIFY the existing functions, never duplicate them:
- `_build_cockpit_state()` (`daemon/maez_daemon.py:2336`) — already builds the fast in-memory state and
  **omits** a missing organ rather than fabricating mood/uncertainty. **Reuse as-is.**
- `/api/v1/daemon/state` (`skills/web_interface.py:1552`) — already flag-switches log-scrape vs the real
  proxy. **Modify in place.**
- `_daemon_cockpit_state_proxy()` (`skills/web_interface.py:1537`) — already exists with the honest
  `{"status":"unreachable"}` fallback. **Modify in place (add the S7 header + reason).**
- `web/cockpit/sim.jsx` `_pollDaemon` (`:479`) — already handles legacy, real, and `unreachable` shapes.
  **No UI change.**

**What's missing is exactly the hardening:** the daemon `/internal/cockpit/state` is **open** (no S7
gate, `maez_daemon.py:10303`); the web `/api/v1/daemon/state` has **no owner gate** and the proxy sends
**no S7 header** (`web_interface.py:1537`). On current `main`, the daemon's live in-memory state —
`cycle_count`, `last_thought`, `cognition`, `valence`, `reasoning_loop`, the health rails, the env
flags, and `sampled_at` (`_build_cockpit_state` deliberately **omits** mood/uncertainty and does **not**
expose a scratchpad; the scratchpad is only in the legacy *log-scrape* shape) — is readable on the local
machine without any auth. This organ closes both gaps.

## What is already on main (so the organ composes)

- `_s7_internal_channel_trusted(req)` + `S7_INTERNAL_CHANNEL_HEADER`/`_ENV` constants (daemon side) — #2.
- `_owner_private_auth_ok` / `_is_owner` / `_request_is_loopback` (the loopback/claimed matrix) — #1.
- `S7_INTERNAL_CHANNEL_TOKEN` registered as a **managed secret** (`core/infra/secrets.py:22`; loaded by
  `web_interface.py:37`) — #2. Must be **provisioned via `config/secrets.local.env`** for both maez +
  maez-web (NOT model.env — the loader purges launch-env secrets).

## The design (the additive hardening only)

**1 · Daemon side — always-on S7 gate (close the open endpoint).** Add to the existing
`/internal/cockpit/state` handler, before `_build_cockpit_state()`:
```python
if not _s7_internal_channel_trusted(request):
    return jsonify({"ok": False, "error": "s7_internal_channel_untrusted"}), 403
```
Always-on (independent of any flag) — the endpoint should never be open. (Task 0 proves the web proxy
is its only consumer, so this breaks nothing.)

**2 · Web side — always-on owner gate + S7 header + honest reason (modify in place).**
- Add the web-side constants `_S7_INTERNAL_CHANNEL_HEADER = "X-Maez-S7-Internal-Channel"`,
  `_S7_INTERNAL_CHANNEL_TOKEN_ENV = "S7_INTERNAL_CHANNEL_TOKEN"`, and `_s7_internal_channel_headers()`
  (reads the token, raises `RuntimeError("s7_internal_channel_untrusted")` if absent).
- Add `_owner_private_auth_required_response()` → `jsonify({"ok": False, "error": "owner_auth_required"}), 401`.
- **Modify `_daemon_cockpit_state_proxy()`** to send the S7 header and return an honest, content-light
  reason on failure — **no scrape fallback, no fabricated state**:
```python
def _daemon_cockpit_state_proxy(timeout=1.5):
    import urllib.error as _urlerr   # web_interface.py only imports urllib.request at top — match the file's local-import style
    try:
        headers = _s7_internal_channel_headers()           # raises if token absent
    except RuntimeError:
        return {"status": "unreachable", "reason": "s7_internal_channel_untrusted"}
    try:
        req = urllib.request.Request(DAEMON_COCKPIT_STATE_URL, headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except _urlerr.HTTPError as e:
        reason = "s7_internal_channel_untrusted" if e.code == 403 else "daemon_error"
        return {"status": "unreachable", "reason": reason}
    except Exception:
        return {"status": "unreachable", "reason": "daemon_unreachable"}
```
- **Modify `/api/v1/daemon/state`** — owner-gate first (always-on, via #1's matrix → no lockout), then
  the existing flag-switch:
```python
@app.route("/api/v1/daemon/state")
def api_daemon_state():
    if not _owner_private_auth_ok():
        return _owner_private_auth_required_response()
    if strict_env_flag("MAEZ_COCKPIT_REAL_STATE"):
        return jsonify(_daemon_cockpit_state_proxy())     # real-or-unreachable, NEVER scrape fallback
    return _api_daemon_state_log_scrape()                 # legacy source, unchanged
```

**3 · Token provisioning (owner breath).** `S7_INTERNAL_CHANNEL_TOKEN` in `config/secrets.local.env` for
**both** services; restart both. Flag `MAEZ_COCKPIT_REAL_STATE` toggles the source (default off).

**4 · UI.** No change — `sim.jsx` already consumes legacy / real / `unreachable` shapes.

## Safe posture (refinement: NOT plain "byte-identical")

- The **real-state source is flag-gated**: `MAEZ_COCKPIT_REAL_STATE` off → the legacy log-scrape; on +
  token-provisioned → real state. **Flag-off serves the same source SHAPE (log-scrape) to *authorized*
  callers** — it is NOT byte-identical overall, because the **always-on owner gate intentionally changes
  access behavior**: a non-owner/remote request that succeeded before now correctly gets `401`. That
  access change is the security hardening, applied regardless of the flag.
- **Flag-on without a provisioned token → honest `{"status":"unreachable","reason":
  "s7_internal_channel_untrusted"}`** — NO fall-back to the log-scrape, NO fabricated state. The owner
  sees a diagnosable reason (provision the token) rather than a silent degrade to the reconstruction.
- **Read-only** across the boundary — the cockpit READS the daemon's state; it never mutates it.

## Covenant rail

Honest body truth: the cockpit shows the daemon's REAL in-memory state, never a reconstructed or
fabricated one when real is requested; a missing organ is omitted; a broken bridge is `unreachable`
with a reason — the [[feedback_visible_substrate_state_not_chain_of_thought]] / sim-stays-dead line.
The internal nerve's trust is the **S7 token** (constant-time match + no-Origin CSRF guard,
[[feedback_s7_trust_is_human_gated_by_design]]); the web edge's trust is **owner-identity** (#1). The
read is **owner-private** and **read-only**. Token provisioning is the owner's breath.

## Task 0 — proof gate (refinement 5 + Organ-1 lessons)

Docs/proof only, committed first. If any proof refutes the design, STOP and patch.
- **Consumer inventory (load-bearing):** prove the web `_daemon_cockpit_state_proxy` is the **only
  PRODUCTION consumer** of the daemon `/internal/cockpit/state` (grep all `internal/cockpit/state` /
  `DAEMON_COCKPIT_STATE_URL` references across daemon+web+cockpit+tests, and **classify** each as
  production vs test — test references to the route are expected and do NOT refute the design). If any
  non-test code reads it ungated, always-on S7 gating would break it — STOP for a scope decision.
- **Clean separation:** the daemon handler + the web proxy import/call NO web-owner-spine
  (`_proxy_web_owner_message_to_daemon`, `handle_message` spine) or voice-spine code. Grep to prove.
- **Import resolution:** `_owner_private_auth_ok`, `_s7_internal_channel_trusted`, `strict_env_flag`,
  `DAEMON_COCKPIT_STATE_URL`, `_api_daemon_state_log_scrape`, `_build_cockpit_state` all resolve on main.
- **Full consumer/mouth inventory** of `/api/v1/daemon/state` (who calls it: the cockpit `_pollDaemon`;
  any others?) so the always-on owner gate doesn't orphan a surface (the Organ-1 lesson).

## Testing (TDD; refinement 4 — hermetic owner mock)

- **Hermetic owner state:** the tests must mock the owner gate (`mock.patch` `_owner_private_auth_ok` /
  inject an owner session) — they must NOT depend on the live `users.db`. The quarry's
  `tests/test_cockpit_real_state_bridge.py` currently calls `/api/v1/daemon/state` without owner-gate
  setup; the ported tests add a hermetic `_owner_session()` (patch the gate True/False).
- Daemon `/internal/cockpit/state`: valid S7 header → 200 + state; headerless / wrong token → 403.
- **Origin-spoof rejection (pin it on this endpoint):** valid S7 header **plus** an `Origin` header →
  still **403**. `_s7_internal_channel_trusted` already has the no-Origin guard, but this is the new open
  nerve being closed, so the test pins browser-origin spoofing failing directly on this route.
- **The web proxy actually SENDS the S7 token (not just returns a payload):** patch `urllib.request.urlopen`
  to **capture the outgoing `Request`** and assert `req.get_header("X-maez-s7-internal-channel")` (urllib
  title-cases header keys) equals the managed token — a mock that only returns a payload would pass even
  if the header were never sent, so the test must inspect the request, not just the response.
- Web `/api/v1/daemon/state`: non-owner → 401; owner + flag-off → log-scrape shape; owner + flag-on +
  token → real proxy; owner + flag-on + **no token → `{"status":"unreachable","reason":
  "s7_internal_channel_untrusted"}`** (no scrape fallback); daemon-down → `unreachable` (reason
  `daemon_unreachable`).
- Scope-guard: port ONLY the real-state-bridge cases; drop any web-owner/voice cases.

## Witness (live, before LIVE_WITNESSED)

1. daemon `/internal/cockpit/state` with no/ wrong S7 header → **403** (the open endpoint is closed).
2. `/api/v1/daemon/state` from a non-owner session → **401**; from the owner → 200.
3. flag-off → cockpit shows the legacy reconstructed state (owner-gated).
4. **flag-on + token provisioned → cockpit DaemonPane shows REAL daemon state** — live `cycle_count`,
   `cognition.score`, `last_thought`, `valence`, `reasoning_loop`, not the reconstruction.
5. flag-on + token wrong/absent → honest `unreachable` with the reason (no fake, no silent scrape).
Owner confirms in the browser (logged in as the web owner). Cross-lane Codex review at the gate.

## Scope

- **IN:** the daemon `/internal/cockpit/state` S7 gate; the web `_s7_internal_channel_headers` + constants
  + `_owner_private_auth_required_response`; the `_daemon_cockpit_state_proxy` S7-header + reason
  modification; the `/api/v1/daemon/state` owner gate; the hermetic-owner tests; token provisioning
  (owner breath); the `MAEZ_COCKPIT_REAL_STATE` flag (existing).
- **OUT:** the web-owner shared spine (owner CHAT → daemon `handle_message`); the voice spine; the
  cockpit real-state daemon-message send; capability-card/prompt self-knowledge; any NEW daemon-state
  fields; the coherence ceremony. Do NOT rebuild `_build_cockpit_state`/`_daemon_cockpit_state_proxy`.
