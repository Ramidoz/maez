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

6. Legacy/fallback support-rail parity
   - Non-focused replies with fresh evidence now backfill a best-effort support
     evidence map from `web_context` or `transcript_context` before the
     support-gate/shadow guard.
   - Focused/photo evidence maps still win when present; fallback paths expose
     the rendered fresh block as `E1` rather than bypassing the rail entirely.
   - This closes the immediate "fresh evidence but empty focused support map"
     bypass class.

7. Web owner inbound-spine proof
   - Added a regression proving the owner web bridge enters
     `daemon.handle_message` with `source="web_owner"` through
     `run_inbound_turn`.
   - This keeps the web owner surface on the shared post-audit rail surface
     instead of silently becoming a generic `UI` tunnel.
   - Tightened the inbound-core test executor shim so fire-and-forget executor
     calls return completed futures instead of leaking coroutine warnings.

8. Voice inbound-spine convergence
   - `handle_voice_stream` no longer owns a private LLM/search/store path.
   - Voice input now calls `handle_message(text, source="voice")` for synthesis,
     then speaks the returned audited reply at the TTS edge.
   - This makes voice inherit the same audit, support-gate/shadow,
     evidence-precedence, thin-evidence, self-claim hygiene, storage, and
     broadcast rails as the other owner surfaces.
   - The old `voice_reply` private brain side door is pinned absent by a
     structural routing test.

9. Legacy fresh-evidence full-chain proof
   - Added a behavioral regression for a non-focused legacy fresh-evidence turn.
   - The test forces `MAEZ_RECALL_TRIAD_ENABLED=0`, turns on thin-evidence
     honesty, evidence precedence, support gate, and self-claim hygiene, then
     verifies all of them compose on one turn.
   - It proves the legacy prompt receives the thin directive, the support gate
     receives the rendered fresh block as `E1`, the final returned reply carries
     the gate caveat, focused synthesis did not run, and the web-grounded reply
     is stored as `self_web_claim` / `untrusted` while the owner utterance stays
     `user_utterance` / `lived`.

10. Cockpit runtime-body display convergence
   - `/api/v1/services` already returned the contract-aware
     `runtime_services` snapshot, but `web/cockpit/sim.jsx` flattened every
     service back to legacy `active/inactive` status.
   - The cockpit sim now preserves `healthy/degraded/asleep/unknown` runtime
     service truth and stores the whole `runtimeServices` snapshot.
   - The living cockpit "Senses" organ now describes Maez's runtime body from
     that snapshot instead of saying "services active."
   - The technical services pane now renders runtime organ statuses directly.
   - The field journal no longer falls back to legacy "all services up" or
     `llama_server_vision` for body/vision status; when runtime truth is
     missing it says `body unknown` / `runtime unknown`.

11. Runtime-body map reconciliation
   - `docs/superpowers/specs/2026-06-17-body-runtime-truth-v0-design.md` no
     longer says the runtime body witness is merely awaiting review.
   - `docs/superpowers/plans/2026-06-17-body-runtime-truth-v0.md` is now
     explicitly marked as the historical implementation recipe, not pending
     work.
   - The current authority for branch state is this handoff plus the
     `BUILT_BRANCH_VERIFIED` row in `docs/MAEZ_BUILD_LEDGER.md`.

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

Result before slice 6: `Ran 223 tests ... OK`.

Additional slice 6 verification:

```bash
/home/rohit/maez/.venv/bin/python -m unittest \
  tests.test_support_gate \
  tests.test_grounding_shadow \
  tests.test_focused_cognition \
  tests.test_thin_evidence_honesty \
  tests.test_self_web_claim_hygiene
```

Result: `Ran 164 tests ... OK`.

Additional slice 7 verification:

```bash
/home/rohit/maez/.venv/bin/python -m unittest \
  tests.test_cockpit_inbound_core \
  tests.test_web_owner_core \
  tests.test_inbound_core_equivalence
```

Result: `Ran 38 tests ... OK`.

Additional slice 8 verification:

```bash
/home/rohit/maez/.venv/bin/python -m unittest discover -s tests -p 'test_voice_shared_spine.py'
/home/rohit/maez/.venv/bin/python -m unittest \
  tests.test_daemon_shutdown_lifecycle \
  tests.test_rail2_containment \
  tests.test_livewc_helper \
  tests.test_thin_evidence_honesty \
  tests.test_support_gate \
  tests.test_grounding_shadow \
  tests.test_self_web_claim_hygiene \
  tests.test_brain_gateway_routing
```

Result: `Ran 1 test ... OK` and `Ran 135 tests ... OK`.

Additional slice 9 verification:

```bash
/home/rohit/maez/.venv/bin/python -m unittest \
  tests.test_memory_integrity_invariant.DaemonHandleMessageContract.test_legacy_fresh_turn_carries_thin_directive_and_support_gate
```

Result: `Ran 1 test ... OK`.

Additional slice 10 verification:

```bash
/home/rohit/maez/.venv/bin/python -m unittest \
  tests.test_cockpit_living_dashboard \
  tests.test_web_runtime_truth \
  tests.test_maez_body_organ_view \
  tests.test_runtime_services \
  tests.test_web_owner_core \
  tests.test_cockpit_inbound_core \
  tests.test_cockpit_proxies_2026_05_05
/home/rohit/maez/.venv/bin/python -m ruff check \
  skills/web_interface.py \
  tests/test_cockpit_living_dashboard.py \
  tests/test_web_runtime_truth.py
git diff --check
```

Result: `Ran 88 tests ... OK`; ruff clean; diff check clean.

Additional slice 11 verification:

```bash
rg -n "Status: design, awaiting review|runtime body truth.*pending|all services up|services active|llama_server_vision" \
  docs/superpowers/specs/2026-06-17-body-runtime-truth-v0-design.md \
  docs/superpowers/plans/2026-06-17-body-runtime-truth-v0.md \
  ui/project-planner.html \
  web/cockpit/index.html \
  web/cockpit/sim.jsx
```

Result: no stale body-state/status hits in the authoritative spec, plan, or UI
targets. This handoff deliberately names the old phrases in slice descriptions.

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

1. Final branch review and switch-over proof
   - The branch has multiple verified seam closures, but it still needs a
     cross-lane review pass and an explicit owner switch-over decision before
     any live Maez restart or mainline claim.

## Plain-English Summary

This branch has not made Maez one body yet, but it has closed several doors
where Maez's body could be read or controlled differently depending on which
surface touched it. The current repair theme is simple: one owner proof, one
runtime truth map, one internal bridge, one Telegram authorization boundary,
one voice input spine, one fresh-evidence honesty spine, one cockpit body
display language, and one current map of those repairs.

The next useful slice is the final review package: summarize the branch,
run the agreed verification set, and ask the review lane to attack the remaining
surface/reader divergence before any switch-over.
