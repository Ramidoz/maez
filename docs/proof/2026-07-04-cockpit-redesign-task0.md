# Cockpit Redesign Task 0 Census

**Date:** 2026-07-04
**Scope:** read-only census for `docs/superpowers/specs/2026-07-04-cockpit-redesign-umbrella-design.md`.
**Status:** no runtime code changed.

## Ground Truth

The live web surface is the existing Flask app:

- Unit: `maez-web.service`
- Command: `/home/rohit/maez/.venv/bin/python3 /home/rohit/maez/skills/web_interface.py`
- Bound surface: loopback-only `http://localhost:11437`
- Live env observed in the web process: `MAEZ_COCKPIT_REAL_STATE=1`, `MAEZ_WEB_OWNER_CORE=1`, `MAEZ_JETSON_PRESENCE_SHADOW=1`, `MAEZ_JETSON_FACE_FACTS_SHADOW=1`
- The daemon process was not live through the queried systemd unit at the moment of this census (`MainPID=0`), so process-env truth for Maez itself must be read at runtime and rendered as unavailable when absent.

The current cockpit is served at `/cockpit` from `web/cockpit`:

- `index.html` - top-level app shell and current living/technical dashboard.
- `sim.jsx` - data loader for existing `/api/v1/*` cockpit APIs.
- `terminal-ui.jsx` - large current component bundle including chat, services, memory, soul, dreams, identity, logs, router, quality, self-dev, workshop.
- `inner-ui.jsx` and `design-canvas.jsx` exist but are not the live production bundle.

The current cockpit uses React/Babel from the browser and is prototype-shaped. The redesign should not mutate it in place first. The safe shape is a new V2 subtree and a flag-gated route switch.

## Existing Web Seams To Reuse

`skills/web_interface.py` already owns the cockpit door:

- `/cockpit` and `/cockpit/<path>` static routes.
- `/cockpit/s7-webauthn-proof` and `/api/v1/s7/*` WebAuthn/S7 proxy routes.
- `/api/v1/daemon/state` real-state bridge, already owner-private and gated by `MAEZ_COCKPIT_REAL_STATE`.
- `/api/v1/cockpit/message` owner bridge to the daemon.
- Existing read endpoints for services, GPU, signals, soul, memory, lived memory, turn/latest, now, rail timeline, dreams, quality, self-dev, identity, router, logs, and workshop.

Auth is already present:

- Cookie: `maez_token`.
- Owner-private gate: `_owner_private_auth_ok()`.
- Required response: `_owner_private_auth_required_response()`.
- S7 proxy helpers: `_s7_internal_channel_headers()`, `_s7_cockpit_proxy_to_daemon()`, `_s7_cockpit_ceremony_deferred()`.

The redesign should extend these seams rather than invent a second web authority.

## Read Surfaces To Reuse

Recent organs already expose read surfaces that can feed the cockpit:

- A1 scars: `core.learning.scar_tissue.ScarSidecar.list_all_at()` and `coverage_at()`.
- A2 continuity: `core.continuity_fingerprint` store/read modules plus `scripts/continuity_fingerprint.py`.
- A6 self-evidence: `core.learning.self_evidence.self_evidence_digest()` plus `scripts/self_evidence.py`.
- Interaction preferences: `core.interaction_preferences` store/render/script surfaces.
- Narrative spine/weave/coverage: `core.memory.narrative`, `core.memory.narrative_readers`, `scripts/narrative_spine.py`, `scripts/narrative_coverage_shadow.py`.
- Fabrication/consequence receipts: `core.learning.fabrication_memory`, `core.learning.consequence_memory`.

Rule carried from A6/A4: cockpit readers must use read-only sqlite access where they read runtime stores. A missing source renders `no_data` or `unavailable`; it must not create an empty DB.

## Flag Surface

The repo contains many `MAEZ_*` flags. Task 0 did not assign every flag by hand; that table is itself an owner-reviewed artifact. The build must treat unclassified flags as read-only until tiered.

Initial tier expectations from the umbrella spec:

- T0 read: all observed flag state, file/process divergence, source health, witness links.
- T1 safe writes: shadow flags, pure read-surface wakes, and backfill list commands.
- T2 guarded writes: enforce flags, restart, backfill apply, preference CLI retraction, and anything that mutates runtime config.
- T3 ceremony: soul writes, dream apply, dangerous grants, and birth. The cockpit must route through existing S7/WebAuthn; no bypass.

Current cockpit-adjacent flags discovered include `MAEZ_COCKPIT_REAL_STATE`, `MAEZ_COCKPIT_CORE`, `MAEZ_COCKPIT_FELT_TIME`, `MAEZ_COCKPIT_INTERCEPTORS`, `MAEZ_COCKPIT_TOOL_LOOP`, and the new umbrella flag `MAEZ_COCKPIT_V2`.

## OSS Inspiration Pass

Borrow shapes, not code:

- Hermes Agent: command-center framing, slash-command/tool output density, multi-surface agent operations.
- btop: resource-monitor density, readable terminal meters, panel hierarchy.
- k9s: watched resource lists, keyboard-first drilldown, namespace/status scanning.
- lazygit: persistent multi-pane flow with focused preview/details.

These are visual and interaction references only. The cockpit remains Maez-native, owner-private, and covenant-tiered.

## Required New Architecture

Recommended implementation shape:

- New static frontend under `web/cockpit/v2/`, not a first-pass rewrite of current `web/cockpit/index.html`.
- Thin Flask route switch: `/cockpit` serves old cockpit unless `MAEZ_COCKPIT_V2=1`.
- New read aggregate endpoints under `/api/v2/cockpit/*`, all owner-private.
- New backend package under `core/cockpit/` for state aggregation, flag registry, write receipts, and restart safety.
- Existing `skills/web_interface.py` should stay a route shim, not absorb another several thousand lines of logic.

## Hard Witnesses

- Old cockpit byte-identical until `MAEZ_COCKPIT_V2=1`.
- V2 never shows file truth as live truth when process env disagrees.
- Missing daemon/process/env renders unavailable, not fake healthy.
- T3 routes fail without real S7 proof.
- Read endpoints do not create missing DB files.
- A7-pending interiority renders content-light only.
- Restart UI never auto-restarts; it offers and receipts owner-confirmed restart only.

## Task 0 Verdict

Proceed to a campaign plan, but do not implement the UI before the visual mock/review gate. The live codebase can support the redesign without replacing the old cockpit first: a V2 subtree, new read/write backend modules, owner-private API routes, and a strict route flag preserve the current surface until witness.
