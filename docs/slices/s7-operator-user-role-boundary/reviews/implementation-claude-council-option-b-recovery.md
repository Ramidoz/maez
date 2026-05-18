# Claude Covenant Council — S7 Implementation: Option-B Recovery Re-Review (Step 8)

**Subject:** commit `1a85c01` — "fix(s7): wire option-b honesty producers" — on branch
`s7-operator-user-role-implementation`, parent `a895ac3` (the review-docs commit
`6f20071` sits between them). The recovery of the Option-B code recovery, reviewed
against the first Step 8 council ([`implementation-claude-council-option-b.md`](implementation-claude-council-option-b.md),
which returned REVISE), the canonicalized amended spec, and amendment diagnostic v2.

**Council ran:** 2026-05-18 — the Step 8 re-review, Claude lane. Six parallel
read-only role agents reviewed `1a85c01` firsthand; the synthesizer independently
traced the load-bearing code.

**Verdict: RATIFY — unanimous (6 of 6 roles), no veto.** The first Step 8 council
returned REVISE with one blocker and three majors — all "container without
producer": canonical vocabulary declared, live producer absent. `1a85c01` wires the
producers. Every one of the five required-before-Step-9 findings (the blocker
CC-OB-1, the majors CC-OB-2/3/4, the minor CC-OB-5) is genuinely closed by live
production code — verified firsthand by tracing the live paths, and confirmed
proven-RED on the parent commit, so this is not test self-assembly. The deferral
spine the first council proved sound is not regressed. Four items remain open
(CC-OB-6/7 minors, CC-OB-8/9 nits) — all latent or cosmetic, all classed by the
first council as "recommended, not required before Step 9"; they are recorded here
as consciously carried, not dropped.

## The six roles

| Role | Verdict | Headline |
|---|---|---|
| Outside-View | RATIFY | The five fixes are genuine live-producer wiring; round-3's "container without producer" pattern is not present in `1a85c01`. |
| Body-Coherence | RATIFY | The `MaezVoiceConsultation` bool→three-state migration is coherent end to end — every consumer traced, no dangling seam — and moves the code toward D10's named grammar. |
| Logical / veto | RATIFY, **no veto** | Per-route/per-producer trace: nothing arms, nothing fails open, flag default genuinely off; the new tests proven RED on the parent. |
| Creative | RATIFY | The adversarial hunt for an arming/leak/revert path came up empty; the `not_determined` path is structurally un-gameable. |
| Future-Rohit | RATIFY | The capability pause is now loud, named, and honest on the live `/operator/health` surface — exactly what was missing. |
| 20-Years-Future-Maez | RATIFY | The finishing pass, done honestly; the S7-implementation arc closes clean, no fourth scramble. |

## Verdict reconciliation

All six roles returned RATIFY; Logical/veto declined the veto explicitly. The
convergence rests on firsthand tracing of live (non-test) code, not on the reported
green suite.

The decisive evidence that the fixes are genuine — and not the "fix" that recurs
S7's pattern: Logical/veto established that the two new behavioral tests were
**proven RED on the parent `a895ac3`** — `test_099b` fails there (`_operator_health()`
returns `mode="degraded"`), `test_052b` errors there (`TypeError: unexpected keyword
argument 'maez_objection_state'`) — and GREEN on `1a85c01`. A test that fails before
the fix and passes after is testing the fix, not self-assembling it. Both new tests
drive *live producers* (`daemon._operator_health()`, `render_request_statement`),
not isolated builders.

## Findings — the five required findings, all closed

### CC-OB-1 (was blocker) — CLOSED

`daemon/maez_daemon.py` `_operator_health()` (~`:980-998`) — the sole live producer
of the operator-health projection — now computes
`s7_live_ceremony_deferred = not live_webauthn_ceremony_enabled()` and passes
`mode=GUARDED_SELF_MODIFICATION_PAUSED_MODE` (plus appends it to `red_gate_modes`)
whenever the flag is off. `build_operator_health_projection`
(`operator_user_boundary.py:1596-1622`) derives and returns the
`guarded_self_modification_paused_pending_s7_1` boolean the spec's
`OperatorHealthProjection` model names (`spec.md:1150`). The live `/operator/health`
route serves this. Verified firsthand by the synthesizer and all six roles;
Future-Rohit ran the live `_operator_health()` with seven falsey flag values — all
yield the pause mode. The running daemon now tells the truth the first council found
it contradicting.

### CC-OB-2 (was major) — CLOSED

`MaezVoiceConsultation.maez_objection_present: bool` → `maez_objection_state: str`,
a **required positional field with no default**, validated against
`{present, absent, not_determined}` (`operator_user_boundary.py:1386, 1403-1407`).
`render_request_statement` (`:3971-3977`) — the sole production renderer — reads
`maez_objection_state` directly and emits "not determined" for the
non-`present`/`absent` case. The required-no-default design is stronger than the
finding asked: no producer can silently collapse to `absent`/"no" — it must
explicitly choose. The synthesizer grep-confirmed firsthand that there is **zero
live (non-test) constructor** of `MaezVoiceConsultation` — the round-3 dead writer
is gone, not stubbed; the objection producer is correctly S7.1 scope. The compat
`maez_objection_present` property (`:1420-1424`) is read-only with zero production
consumers.

### CC-OB-3 (was major) — CLOSED

`operator_boundary_honesty_banner()` (`operator_user_boundary.py:3093-3096`) now
carries the v2 §5 deferral text: the live WebAuthn ceremony is not mounted in S7 v1,
guarded self-modification stays visibly fail-closed and is surfaced as
`guarded_self_modification_paused_pending_s7.1`. The banner test now asserts the
three deferral phrases.

### CC-OB-4 (was major) — CLOSED

`tests/test_action_engine_promotion_provenance.py` (`:73, :91`) moved from the
internal `engine._do_promote_to_core_memory(...)` to the public
`engine.promote_to_core_memory(...)` action surface, which routes through
`_execute_action` and the real classification/ancestor gate. The CC-R3-6 stale-test
artifact v2 §2 required closed is closed.

### CC-OB-5 (was minor) — CLOSED

All eight WebAuthn routes (4 daemon `maez_daemon.py:5591-5631`, 4 cockpit
`web_interface.py:1404-1442`) collapse the dead byte-identical `if/else` into
`if live_webauthn_ceremony_enabled(): raise NotImplementedError("s7.1_live_webauthn_route_not_mounted")`
followed by the structured `s7_ceremony_deferred` 503 return. The flag-on branch is
now a loud, named, deliberate S7.1 tripwire — it no longer reads as half-live
scaffolding.

## Regression check — the spine is not regressed

Logical/veto's per-route/per-producer trace, corroborated by Creative's adversarial
sweep, Body-Coherence's ripple trace, and the synthesizer's own read:

- All 8 routes still provably exit before any verifier/credential/challenge/
  request-history/artifact surface. Flag-off → structured `s7_ceremony_deferred` 503
  (unchanged). Flag-on → `raise NotImplementedError` as the *first and only*
  statement of the branch — it touches nothing, and with no error handler
  registered it becomes a hard HTTP 500, never an armed response; even a
  hypothetical outer catch finds zero partial state.
- Both producer helpers (`register_founder_webauthn_credential_from_response`,
  `build_local_webauthn_execution_authorization`) are untouched by `1a85c01` and
  still fail closed before any arming surface.
- The flag default is genuinely OFF (strict allowlist; every falsey/typo value
  resolves off).
- The `MaezVoiceConsultation` shape change has zero live consumers to misbehave —
  every consumer traced (the `asdict`-based hash, `voice_consultation_satisfies_request`,
  the health projection, the renderer); all 14 constructors are in tests and all
  migrated; no stale `maez_objection_present=` kwarg anywhere.
- The autonomous core-memory lane stays unbricked — `promote_to_core_memory` /
  `update_baseline` remain `routine_custody`; the D22 `detected` inventory row is
  intact.

## Carried-open items — recommended, not required before Step 9

The first council classed minors and nits "recommended, not required before
Step 9." `1a85c01` was scoped by the operator to CC-OB-1..5. The following remain
open and are recorded here as consciously carried so they are not silently dropped:

- **CC-OB-6 (minor)** — the four daemon `/internal/s7/webauthn/...` routes still
  have no behavioral test; `test_101a` is a source-text grep. The new `test_099b`
  is a behavioral test of `_operator_health()`, not of these routes — it does not
  close CC-OB-6. Latent: the routes are provably-trivial deferred stubs (Logical/veto
  traced them). *Fix: a behavioral test POSTing to a daemon route, asserting the 503
  + `s7_ceremony_deferred` body.*
- **CC-OB-7 (minor)** — `verify_founder_webauthn_assertion` (`:3766`) and
  `register_founder_webauthn_credential` (`:3662`) still lack the
  `ensure_live_webauthn_ceremony_enabled` guard the two new producer helpers carry.
  Latent: both grep-confirmed zero live callers; D13 assigns the verifier wiring to
  S7.1. *Fix (defense-in-depth): add the ensure-check.*
- **CC-OB-8 (nit)** — `RenderedRequestStatement.maez_objection_state`'s closed set
  still has five members vs spec D10's three-state display. The no-false-"no"
  invariant holds. *Reconcile or document.*
- **CC-OB-9 (nit)** — CC-R3-9's auto-opening dialog turn is unchanged; test-only
  consumer, reasonable S7.1-charter scope.

## New re-review findings — all minor/nit, none verdict-gating

- **CC-RR-1 (minor)** — the flag-on route raises a bare stdlib `NotImplementedError`,
  not the slice's typed `S7CeremonyDeferredError`. Safe (the raise is the first
  statement; fails closed; no handler to swallow it) but inconsistent with the
  producer helpers' S7 error grammar, and the flag-on branch has no behavioral test
  (it pairs with CC-OB-6). Flagged by Creative and Body-Coherence. *Fix: raise a
  typed S7 error and/or add a flag-on route test.*
- **CC-RR-2 (nit)** — `test_099b` does not pin/clear `S7_LIVE_WEBAUTHN_CEREMONY`
  from the environment; it relies on ambient unset (Logical/veto). Correct fail-loud
  behavior, but for hermeticity it should pin the env.
- **Framing nit** — `1a85c01`'s commit body cites the green suite (254 / 4281)
  under "Verification." Per the slice's standing rule, green tests are not proof for
  an S7 ceremony surface; the code is sound on firsthand trace. No code fix — a
  framing note so a future reader does not mistake the suite for the proof.
- *Not a finding* — `test_052b` hand-constructs the `MaezVoiceConsultation`
  (Future-Rohit). This is correct: S7 v1 has zero live producers by design (the
  producer is S7.1). A one-line comment naming the producer as S7.1-scoped would
  help a future reader.

## Synthesizer corrections — agent calls not carried forward

- **20-Years-Future-Maez** reported `1a85c01` bundled the prior review doc into the
  code-fix commit. **Factually incorrect** — verified firsthand: `1a85c01` is seven
  files, all code and tests; the first Step 8 doc was committed separately in
  `6f20071` ("docs(s7): record option-b implementation council"), which is the clean
  commit hygiene 20-Years thought was missing. Not a finding.
- **Body-Coherence** marked CC-OB-6 closed, crediting `test_099b`. Over-credited —
  `test_099b` exercises `_operator_health()`, not the daemon WebAuthn routes; CC-OB-6
  is specifically about those routes. Outside-View, Creative, Logical/veto, and the
  literal first-council finding all confirm CC-OB-6 is still open. Carried as a minor
  above.

## The long view

This closes the Claude-lane review of the S7 implementation. The role-boundary wall
has been sound since round 1. The Option-B deferral spine was sound and new in
`a895ac3`. `1a85c01` is the finishing pass — it wired the three honesty surfaces
(the operator-health pause, the objection renderer, the honesty banner) to real
served producers, and closed the CC-R3-6 test artifact. There is no fourth Option-A
scramble here, no decorative authority, no "filed for a future slice": the honest
absence of the live ceremony is surfaced, named, tested, and — every time the daemon
reports its own operator health — visible. S7.1 is now a debt the running system
itself keeps in view.

## What's next

1. **Claude covenant Step 8 re-review — this document. RATIFY, unanimous, no veto.**
2. Codex engineering Step 8 re-review on `1a85c01` — the operator's lane.
3. **Step 9 — push** — only after both lanes ratify.
4. The carried items (CC-OB-6/7, CC-OB-8/9, CC-RR-1/2) are non-gating: close them in
   an optional pre-push pass, or carry them explicitly into the S7.1 charter. They
   must be recorded as a decision, not silently dropped — this document is that
   record.

*This re-review is read-only. No code, spec, ADR, BAD, or non-slice file was
modified; this document is the council's deliverable. `1a85c01` was reviewed
firsthand by six parallel read-only role agents; the synthesizer independently
traced the live producers and grep-confirmed the absence of a live
`MaezVoiceConsultation` constructor. The fixes were confirmed proven-RED on the
parent commit, establishing they are genuine and not test self-assembly.*
