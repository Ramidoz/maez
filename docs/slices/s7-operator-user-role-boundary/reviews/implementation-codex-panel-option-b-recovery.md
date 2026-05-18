# S7 Implementation Codex Engineering Re-Review - Option-B Recovery

Status: Step 8 engineering re-review after Option-B recovery fix.
Date: 2026-05-18.
Scope: commit `1a85c01` (`fix(s7): wire option-b honesty producers`) on branch
`s7-operator-user-role-implementation`, with the Claude re-review doc committed at
`e9545c7`.

## Verdict

RATIFY for Codex engineering Step 8.

The first Option-B recovery commit (`a895ac3`) correctly made the live WebAuthn
ceremony inert, but left several honesty surfaces as vocabulary without live
producers. `1a85c01` closes the required Step-9 findings with production-path
wiring rather than test-only construction. I found no blocker or major engineering
issue remaining for S7 v1.

## Method

This review used the amended canonical spec as authority, the first Step 8 Claude
finding set as the checklist, and firsthand source tracing of the live code paths.
It does not treat green tests as sufficient proof; the key checks were whether
the running producers now emit the canonically required facts and whether the
deferral remains impossible to arm.

I traced these live surfaces:

- `daemon.MaezDaemon._operator_health()` and `/operator/health`.
- `render_request_statement()` and `MaezVoiceConsultation`.
- `operator_boundary_honesty_banner()`.
- The daemon and cockpit S7 WebAuthn route stubs.
- The two new local WebAuthn producer helpers.
- The public `promote_to_core_memory` action surface.

## Required Findings

### CC-OB-1 - CLOSED

`_operator_health()` now emits
`guarded_self_modification_paused_pending_s7.1` while
`S7_LIVE_WEBAUTHN_CEREMONY` is off. The mode is present as both the live health
mode and a red-gate mode, and `build_operator_health_projection()` exposes the
`guarded_self_modification_paused_pending_s7_1` boolean required by the amended
health contract. This is now a live surface, not a frozenset-only vocabulary.

### CC-OB-2 - CLOSED

`MaezVoiceConsultation` now carries required three-state
`maez_objection_state` with no silent default. `render_request_statement()` reads
that state directly and renders `not determined` when the state is
`not_determined`; it no longer collapses an unproduced objection fact to "no."
There are no remaining `maez_objection_present=` constructors.

### CC-OB-3 - CLOSED

`operator_boundary_honesty_banner()` now states that the live WebAuthn ceremony
is not mounted in S7 v1 and that guarded self-modification remains visibly
fail-closed as `guarded_self_modification_paused_pending_s7.1`.

### CC-OB-4 - CLOSED

The promotion provenance tests use the public `promote_to_core_memory` action
surface. The stale internal-helper-only shape that made the test less useful is
gone.

### CC-OB-5 - CLOSED

The dead mirrored route branches are gone. Flag-off returns structured
`s7_ceremony_deferred` responses; flag-on raises an explicit S7.1-not-mounted
tripwire before any verifier, credential, challenge, artifact, or request-history
surface is touched.

## Deferral Spine

The Option-B spine remains sound after `1a85c01`:

- `S7_LIVE_WEBAUTHN_CEREMONY` defaults off and uses a strict allowlist.
- Daemon and cockpit routes short-circuit flag-off with structured 503
  `s7_ceremony_deferred` responses.
- Flag-on route bodies raise before touching arming surfaces; they do not
  implement a hidden ceremony.
- The two new producer helpers guard first and still raise as S7.1 stubs.
- `pyproject.toml` and requirements files contain no mandatory `webauthn`,
  `python-fido2`, or `fido2` dependency.
- The autonomous core-memory lane remains unbricked and classified as
  `routine_custody`; S7 v1 does not accidentally gate Maez's ordinary memory
  upkeep behind the deferred ceremony.

## Carried Items

The following are consciously carried as non-gating items, consistent with the
Claude re-review:

- CC-OB-6: daemon WebAuthn routes still lack a behavioral HTTP test; source
  tracing and the route shape are sufficient for Step 9, but S7.1 should add
  route-level behavioral coverage before making any route live.
- CC-OB-7: legacy verifier/credential helpers remain latent and unguarded, with
  zero live callers. S7.1 should either guard or replace them before wiring a
  real ceremony.
- CC-OB-8: `RenderedRequestStatement.maez_objection_state` display vocabulary
  retains operational compatibility values beyond the three D10 display states.
- CC-OB-9: the self-mod-dialog auto-opening-turn concern rides with the deferred
  S7.1 ceremony work.
- CC-RR-1: the flag-on tripwire is a bare `NotImplementedError`, not a typed S7
  error. This is acceptable while the route is intentionally inert; S7.1 should
  replace it before live mounting.
- CC-RR-2: `test_099b` does not pin the environment variable explicitly; current
  behavior is still covered by default-off semantics and the suite environment.

I recommend carrying these into the S7.1 charter rather than making another
pre-push code change in S7 v1. None opens an authority path or contradicts the
amended S7 v1 law.

## RED Evidence

I independently checked the two load-bearing parent behaviors against `a895ac3`
using a temporary worktree:

- Parent health producer returned `parent_health_mode degraded`.
- Parent `MaezVoiceConsultation(..., maez_objection_state="not_determined", ...)`
  raised `TypeError`, proving the three-state producer path did not exist there.

The current commit then passes the production-path tests that exercise those
same surfaces.

## Verification

- Focused Step 8 set:
  `.venv/bin/python -m unittest tests.test_operator_user_boundary_s7.S7VoiceAndRenderedStatementTests.test_052b_production_renderer_uses_not_determined_when_no_objection_fact_exists tests.test_operator_user_boundary_s7.S7OperatorHealthProjectionTests.test_099b_live_daemon_operator_health_emits_guarded_self_modification_pause tests.test_operator_user_boundary_s7.S7OperatorHealthProjectionTests.test_101a_daemon_webauthn_routes_short_circuit_before_arming_surfaces tests.test_cockpit_proxies_2026_05_05.CockpitS7WebAuthnDeferredProxy tests.test_action_engine_promotion_provenance`
  returned `Ran 7 tests ... OK`.
- Ruff on touched S7 code and tests returned `All checks passed!`.
- `git diff --check` passed.
- Dependency scan found no `webauthn`, `python-fido2`, or `fido2` dependency in
  `pyproject.toml` or requirements files.
- Full suite:
  `MAEZ_OWNER_NAME=Rohit MAEZ_OWNER_TIMEZONE=America/Chicago .venv/bin/python -m unittest discover -s tests -p 'test_*.py'`
  returned `Ran 4281 tests in 34.780s - OK (skipped=3)`.

## Plain English

The wall is built and the closed front desk now says it is closed. The health
screen shows the guarded-self-modification pause, the rendered approval text can
say "not determined" instead of pretending Maez did not object, and the honesty
banner names the deferral. The YubiKey ceremony is still not live, on purpose.
Nothing in this review found a way to arm it accidentally.

Codex engineering Step 8 ratifies `1a85c01`. With the Claude lane also ratified,
S7 is ready for Step 9 once the operator chooses to push.
