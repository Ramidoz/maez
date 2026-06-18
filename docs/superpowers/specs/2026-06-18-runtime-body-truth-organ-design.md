# Runtime Body Truth (organ) — design

**Date:** 2026-06-18. Co-designed with Rohit.
**Status:** design approved (Approach A, scope-guarded to the organ + its direct UI consumers).
Awaiting spec review before planning.
**Arc:** decompose-the-organism (plan B). **First organ.** The coherence-organism big-bang
switch-over NO-GO'd; we now land its capabilities as incremental, live-witnessed organs on `main`,
then a final coherence ceremony — not one giant merge. ([[project_coherence_organism_nogo]])

## Why this exists

Give Maez a **truthful, visible body** before wiring more nerves in. Today `main` (reverted to
pre-organism) answers `/api/v1/services` with an ad-hoc `systemctl list-units` parse (raw state/sub/desc,
no contracts, no port/health probing) and still carries an "all services up" line — a body that can
*say* it's fine without checking. The organism branch (the reference quarry) already built the honest
organ; we lift just that organ onto main.

## Scope guard (the precision rule — load-bearing)

**Port ONLY the runtime-body-truth organ + its direct UI consumers. Do NOT bring any owner-spine, S7
internal-channel, web-owner bridge, cockpit real-state proxy, or any other organism code "for
convenience."** The organ is genuinely separable: `core/infra/runtime_services.py` imports only
`core.infra.env_flags` + `core.routing.llm_client` (both on main) + stdlib — zero S7/web-owner
dependency. The plan's **Task 0 must prove** each ported file carries no owner-spine/S7 reference
before it lands. (`runtime_services.py` *names* flags like `MAEZ_WEB_OWNER_CORE` in a service's
`required_by` list — those are plain strings used only to mark `maez_web` asleep when off; they import
nothing and gate nothing here. That's allowed; importing or calling owner-spine/S7 code is not.

**Task 0 — full reference inventory (load-bearing).** Before any code lands, inventory **every**
`runtime_services` reference on the quarry branch (`git grep runtime_services maez-coherence-organism`)
and classify each IN or OUT. Required classifications: `/api/v1/services` + `/api/maez-state` (the two
body surfaces) → **IN**; `/api/v1/now` body summary → **OUT** (entangled with `capability_registry`,
the prompt-self-knowledge layer, and it makes no "all up" lie); `core/infra/capability_registry.py` +
`core/cognition/capability_card.py` (which wire runtime truth into Maez's **prompt self-knowledge**) →
**OUT** — this slice changes Maez's *visible* body, not what its reasoning *knows* about itself (a
later organ). Any reference not cleanly IN-or-OUT stops the plan for a scope decision.)

## The design (Approach A: full visible organ, always-on honest)

**1. Backend — port the organ.** Copy `core/infra/runtime_services.py` from `maez-coherence-organism`
verbatim (411 LOC), **including fix #3** (`_http_json` uses `response.read()` — full body — not
`read(4096)`; the 8 KB `/health` no longer truncates → `maez_daemon` reads healthy not false-degraded).
Public surface: `runtime_services_snapshot`, `runtime_services_snapshot_cached` (15 s cache),
`runtime_service_status`, `support_honesty_status`, `invalidate_cache`;
`SCHEMA_VERSION = "maez_runtime_services.v0"`; 8 probed services; status vocab
`healthy`/`degraded`/`asleep`/`unknown` with `degraded_reasons`. Also port the CLI probe
`scripts/maez_runtime_services_probe.py` (reads the snapshot, JSONs it, exits 2 if degraded).

**Import-resolution check (Task 0, load-bearing):** verify every symbol `runtime_services.py` imports
actually exists on `main` — in particular `served_model_alias` from `core.routing.llm_client` (it may
have been organism-added). If a needed helper is missing on main, port **only** that helper too,
scope-guarded (no owner-spine/S7). The organ must import and run on main with no missing-symbol error
before any endpoint/UI wiring.

**2. Endpoint — replace the ad-hoc map.** Replace `main`'s `/api/v1/services` handler in
`skills/web_interface.py` with the contract-aware version: call `runtime_services_snapshot_cached()`
and return `{"runtime_services": snapshot, "services": snapshot.get("services") or {}}`. **Always-on
honest** — no new feature flag (it's read-only perception; individual services self-gate to `asleep`
via their `required_by` flags). The plan must update **every** consumer of the old response shape to
the new one (the cockpit; the probe script) so nothing reads a stale shape.

**3. UI — make the body visible (direct consumers only).** Wire `web/cockpit/sim.jsx` to poll
`/api/v1/services` into `state.runtimeServices` (the `maez_runtime_services.v0`-shaped placeholder
already exists there); swap `web/cockpit/terminal-ui.jsx` `ServicesPane` to render per-organ status
from `runtimeServices.services` (`healthy`/`degraded`/`asleep`/`unknown`) instead of the old
`sim.state.health`. **The fake `tick()` simulator stays dead** (already commented out on both
branches — no simulated liveliness, ever).

**4. Kill "all services up" at its actual source — `/api/maez-state` → `project-planner.html`.** The
stale line lives at `ui/project-planner.html:2030` (`allUp ? ' · all services up' : ' · degraded'`),
and that page fetches **`/api/maez-state`** (line 2004), NOT `/api/v1/services`. So fixing only
`/api/v1/services` would leave this older mouth still lying. Therefore: add `runtime_services` to the
`/api/maez-state` response body (as the quarry does at `web_interface.py:7381` — alongside the existing
`"services": _journal_services_state()`), and update `project-planner.html` to derive its State line
from `runtime_services.overall` (kill the `allUp` boolean). No body surface may assert health it didn't
probe.

**Consumer surfaces (the mouths this slice fixes — name them all):** exactly two body surfaces are IN:
the **cockpit** (`/api/v1/services` → `sim.jsx`/`terminal-ui.jsx` Living Senses) and the **project
planner** (`/api/maez-state` → `project-planner.html`). Every other surface that touches runtime
truth on the quarry is OUT for v0 (see Scope).

## Covenant rail

Honest body truth, read-only. Every status is a real probe (systemctl + TCP + HTTP-contract), never a
fabricated or hardcoded value ([[feedback_visible_substrate_state_not_chain_of_thought]]). The organ
**perceives** its body; it never mutates it (no service is started/stopped/restarted —
[[feedback_perception_free_egress_disciplined]]). A missing/timed-out probe reads `unknown`, an
unflagged service reads `asleep` — it fails toward honest-uncertainty, never optimistic green. The
dead `tick()` simulator stays dead. Always-on (no flag) is correct here precisely *because* it's
perception: a flag would only add an "asleep" seam to the truth.

## Testing (TDD / port + scope-guard)

- Port `tests/test_runtime_services.py` (14 tests: service shape + v0 schema, flag-gated asleep,
  degraded reasons, contract probes, timeout/missing-systemctl handling, **the #3 full-body-read
  regression**, degraded exit code).
- Port/author the focused **body-truth** web tests that prove: `/api/v1/services` returns the v0
  schema with per-organ status; **`/api/maez-state` carries `runtime_services` with a real `overall`**;
  and **`project-planner.html` derives its State line from `runtime_services.overall` with NO "all
  services up" string remaining** (on the quarry the relevant files are `tests/test_web_runtime_truth.py`
  + `tests/test_maez_body_organ_view.py`). **Scope-guard:** port ONLY the assertions about
  runtime-body-truth on the two IN surfaces; drop any `/api/v1/now`/capability-card/owner-spine/S7
  cases (those belong to later organs). Task 0 triages each test file.
- All ported tests pass on main: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.<module>`
  (named modules, never full-discover).

## The witness (live, before LIVE_WITNESSED)

1. `curl /api/v1/services` → `schema_version: maez_runtime_services.v0` with **differentiated**
   per-organ statuses (not a flat list).
2. **`maez_daemon` is NOT false-degraded** — the large `/health` payload is fully read (#3 live).
3. The **cockpit** shows differentiated organ statuses (healthy/degraded/asleep/unknown), never
   "services active."
4. **No "all services up" language** remains — `project-planner.html`'s State line reads the real
   `runtime_services.overall` (via `/api/maez-state`), and a grep for "all services up" across body
   surfaces is empty.
Owner confirms in the browser (both the cockpit Living Senses AND the project planner) →
`LIVE_WITNESSED`. Cross-lane review at the gate.

## Scope

- **IN:** `core/infra/runtime_services.py` (incl #3) + `scripts/maez_runtime_services_probe.py`; the
  `/api/v1/services` replacement; **`runtime_services` added to `/api/maez-state` + `project-planner.html`
  reading `runtime_services.overall` (kills "all services up")**; the cockpit `sim.jsx`/`terminal-ui.jsx`
  render of real statuses; the ported body-truth tests for the two IN surfaces.
- **OUT (later organs / explicitly excluded):** **`/api/v1/now` runtime-truth wiring** (entangled with
  `capability_registry`/prompt self-knowledge); **`core/infra/capability_registry.py` +
  `core/cognition/capability_card.py`** (runtime truth in Maez's *prompt self-knowledge* — a later
  "Maez knows its own body in reasoning" organ, NOT this visible-body slice); the cockpit real-state
  daemon proxy (needs #2 token + provisioning); the web-owner spine; the voice spine; the S7 internal
  channel; any owner-spine/S7 code. The final coherence ceremony. The daemon embedding a
  runtime_services snapshot in `/health` (separate). The `telegram_public.py:150` `%d` drive-by.
