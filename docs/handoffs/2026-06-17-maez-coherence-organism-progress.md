# Maez Coherence Organism Branch — Progress Handoff

Branch: `maez-coherence-organism`

Goal: bring Maez toward the North Star as one coherent, encapsulated working
organism on a separate reversible branch. Live Maez remains untouched until
review and explicit switch-over.

## Current State

This branch has moved from setup into repair work. The landed changes are
mostly seam closures: places where the same Maez body could be read, controlled,
or authorized differently depending on surface.

## Landed Slices

1. Web owner/private cockpit API gates
   - Private read/mutation routes now require owner-private auth instead of
     quietly exposing sensitive cockpit state.
   - Route inventory test catches newly-added ungated `/api` routes unless they
     are deliberately public.

2. Runtime body truth in the journal
   - `/api/maez-state` now includes the shared `runtime_services` registry
     additively, preserving the old `services` shape.
   - The project-planner journal reads `state.runtime_services.overall` for
     body state instead of only deriving health from the old service map.
   - `primary_brain` degrades when the served model alias is `unknown`.
   - `MAEZ_WEB_OWNER_CORE` marks `maez-web` as required in the runtime map.

3. Debug cockpit auth
   - Removed the `?test_t=1` debug bypass.
   - Debug routes now resolve token identity to the full user record before
     trusting `private_owner_bridge`, matching the owner-private cockpit proof.

4. Telegram surface auth/egress parity
   - Callback authorization now uses the same configured `allowed_users` source
     as message intake.
   - Model-picker callbacks are gated before dispatch.
   - Explicit config allowlist wins over `TELEGRAM_ALLOWED_USERS` fallback.
   - `/receipts` replies now travel through the command reply/provenance path
     instead of direct `reply_text`.

5. Daemon internal state perimeter
   - `/internal/cockpit/state` now requires the S7 internal-channel header.
   - `/internal/s7/webauthn/status` now requires the same bridge proof.
   - Positive status tests now use the bridge header rather than direct local
     daemon access.

## Latest Verification

Command:

```bash
/home/rohit/maez/.venv/bin/python -m unittest \
  tests.test_runtime_services \
  tests.test_web_runtime_truth \
  tests.test_maez_body_organ_view \
  tests.test_camera_presence_v1_legacy_disablement \
  tests.test_temporal_spine \
  tests.test_web_debug_auth \
  tests.test_cockpit_proxies_2026_05_05 \
  tests.test_web_owner_core \
  tests.test_telegram_authorization_boundary \
  tests.test_egress_telegram_producer_threading \
  tests.test_egress_telegram_chokepoint \
  tests.test_egress_telegram_bypass_inventory \
  tests.test_s7_1_daemon_internal_channel \
  tests.test_s7_1_status_projection
```

Result: `Ran 223 tests ... OK`.

Lint/checks:

```bash
/home/rohit/maez/.venv/bin/python -m ruff check \
  core/infra/runtime_services.py \
  skills/web_interface.py \
  skills/surface/telegram_adapter.py \
  daemon/maez_daemon.py \
  tests/test_runtime_services.py \
  tests/test_web_runtime_truth.py \
  tests/test_web_debug_auth.py \
  tests/test_temporal_spine.py \
  tests/test_telegram_authorization_boundary.py \
  tests/test_s7_1_daemon_internal_channel.py \
  tests/test_s7_1_status_projection.py
git diff --check
```

Result: clean.

## Still Open

These are not fixed by this handoff and should stay visible:

1. Legacy synthesis support-gate gap
   - Fresh-evidence legacy generation can still bypass the support gate because
     support evidence maps are focused/photo-shaped today.
   - Needed direction: build a support evidence map from the fresh evidence
     transcript for legacy paths or route legacy through the same post-audit
     support seam.

2. Web owner `/chat` post-audit rail parity
   - The owner web chat bridge reaches daemon core, but the audit/support/
     capability-card/evidence-precedence parity still needs an end-to-end
     proof against Telegram/focused paths.

3. Voice/legacy fresh-evidence parity
   - Voice and some legacy prompt paths still need proof that containment,
     evidence precedence, thin-evidence honesty, and support-gate behavior
     all compose the same way.

4. Cockpit UI body display audit
   - `ui/project-planner.html` now reads `runtime_services`, but other cockpit
     UI surfaces may still collapse `healthy/degraded/asleep/unknown` into old
     active/inactive language.

5. Stale docs
   - Some docs/plans still describe design or pending-review state for slices
     that are now live/asleep elsewhere. The branch should reconcile the owner
     facing body map before any switch-over claim.

## Plain-English Summary

This branch has not made Maez one body yet, but it has closed several doors
where Maez's body could be read or controlled differently depending on which
surface touched it. The current repair theme is simple: one owner proof, one
runtime truth map, one internal bridge, one Telegram authorization boundary.

The next useful slice is probably the legacy/focused support-gate parity gap,
because that is where Maez can still have real fresh evidence and yet serve an
unsupported claim without the same protection the focused path gets.
