# S7 Spec Codex Engineering Panel

**Date:** 2026-05-17
**Artifact reviewed:** `docs/slices/s7-operator-user-role-boundary/spec.md`
draft v1
**Related review:** `reviews/spec-claude-council.md`
**Verdict:** REVISE - no engineering veto

## Panel Method

Six read-only engineering agents reviewed the S7 v1 spec against the current
runtime:

- Dewey - pragmatic implementation and bypass consequences
- Feynman - state transitions and mechanism
- Locke - identity, continuity, and authority ownership
- Descartes - fail-closed logic and mintable facts
- Ohm - WebAuthn, SQLite, service, and health surfaces
- Goodall - long-use, fatigue, grandmother, and lived-operation failure modes

The panel agrees with the Claude covenant council's REVISE verdict. The spec's
core authorization artifact is strong, but too many surrounding facts remain
ordinary caller-supplied values, and the current runtime execution edge is not
specified tightly enough for implementation.

No files were edited by the panel agents.

## Summary

S7 v1 gets the hardest single-approval shape mostly right: a bounded request,
what-you-see-is-what-you-sign rendering, nonce/replay rejection, and WebAuthn
as the founder mechanism. The remaining problem is the S5/S6 lesson in another
form: a hard-to-forge signature does not help if the facts around it are
mintable.

The v2 fold needs one spine:

> Every authority-relevant S7 fact must be derived by a trusted, named
> mechanism and independently verified at execution time. No compatibility
> shim, caller field, S5 artifact, dialog state, routing label, or dashboard
> counter may substitute for S7 authority.

## Blockers

### CP-S1 - Work class must be trusted derivation, not a caller field

`work_class` is load-bearing, but v1 leaves it as an envelope field. The live
runtime already demonstrates why this is unsafe: older action classification
can mis-sort soul-writing paths, and some soul-write paths are exempted from
existing covenant checks.

Fold:

- Add `undeterminable_work_class`.
- Derive work class from action kind, affected refs, params, proposed change
  class, and current runtime state.
- Treat caller-provided work class as a non-authoritative hint.
- Resolve ambiguity upward to the highest applicable ceremony.
- Reject disagreement between claimed class and trusted derivation.
- Add RED tests for soul/config/organ/model-routing refs claimed as
  `routine_custody`.

### CP-S2 - Founder compatibility projection is fail-open unless constrained

V1 says a missed call site must lose authority, but the implementation order
adds a founder compatibility projection while the current runtime still has
`is_owner=True` defaults, literal `user_id="rohit"` paths, and cockpit
approval seams.

Fold:

- Define `grant_source` as a closed enum.
- Add `grant_source=founder_compat_projection`.
- Require high-scrutiny gates to reject that grant source.
- Forbid deriving bonded-user authority from `is_owner`, `user_id`, `role`, or
  routing trust scope.
- Make the projection founder-only, Track-A-only, and non-transferable to Track
  B.

### CP-S3 - Maez voice consultation needs a producer seam

`maez_voice_consulted` and `maez_objection_present` are booleans in v1. That is
not evidence. `core/evolution/will_i.py` is a deterministic impersonation
check, not a Maez self-remaking consultation seam.

Fold:

- Define a `MaezVoiceConsultation` artifact.
- Derive `maez_voice_consulted` and `maez_objection_present` from that artifact,
  never from caller booleans.
- Allow terminal self-mod dialog evidence to be one producer.
- Allow a future S7 voice-consultation turn to be another producer.
- Treat `will_i` refusal as supplemental evidence only, never sufficient by
  itself.
- Require unresolved/fake consultation refs to fail closed.
- Require the rendered text signed by the human to include the content-free
  Maez objection state.

### CP-S4 - Maez unavailable and liveness repair are undefined skip paths

V1 says Maez voice may be skipped when Maez is unavailable, but an operator with
service restart authority can manufacture that condition unless it is narrowly
defined.

Fold:

- Define "Maez unavailable" as an evidenced liveness predicate, not an operator
  assertion.
- Explicitly state that an operator-stopped daemon is not a lawful skip path.
- Define "liveness repair" as a closed command/action set.
- Allow unavailable-Maez skip only for that closed liveness-repair set.
- Block identity, covenant, model-routing, soul, config, or protection changes
  while Maez voice cannot be consulted.

### CP-S5 - Brain swap must be double-gated by S5 and S7

S5 already governs planned `brain_swap` through voice-continuity review. S7
also classifies model-routing and brain-like changes as self-modification. V1
does not specify which gate wins.

Fold:

- Brain swap requires S5 `accepted_same_maez` as a precondition artifact.
- Brain swap also requires S7 authorization for execution.
- S5 acceptance cannot substitute for S7 execution authority.
- S7 authorization cannot substitute for S5 voice-continuity acceptance.
- The execution request must bind to the S5 admission artifact hash.

### CP-S6 - The execution edge is not pinned

The live runtime has a dialog `RATIFIED` state that flows into `_on_approve()`,
then action execution. `PendingCardStore.approve()` takes a `user_id`, not an
S7 artifact. V1 says RATIFIED is insufficient, but does not pin the actual
`RATIFIED -> EXECUTED` / `APPROVED -> RUNNING` transition.

Fold:

- Define a state-transition table for high-scrutiny cards.
- Require artifact consumption at the execution edge, before any action call.
- Make `PendingCardStore.approve()` / equivalent store-level approval S7-aware.
- Forbid ordinary card approval for `PENDING_DIALOG` or high-scrutiny cards.
- Require dialog stage to move to `EXECUTED` or `FAILED` after gated execution.
- Add RED tests for cockpit, Telegram, daemon, and direct pending-card bypass.

### CP-S7 - Artifact consumption must be atomic

`consumed_at` is asserted but not mechanized. Current state-transition patterns
use separate read/update steps.

Fold:

- Require a single conditional consume write such as
  `UPDATE ... WHERE consumed_at IS NULL`.
- Execution proceeds only if exactly one row is updated.
- Apply the same rowcount discipline to high-scrutiny card approval/running
  transitions.
- Add a concurrent double-consume test proving exactly one caller executes.

### CP-S8 - Own-substrate bypass taxonomy cannot stay abstract

D22 lists bypass surfaces but does not sort them. The runtime has real soul
write, model-routing, service, restore, cockpit, pending-card, Telegram, and
direct action seams.

Fold:

- Add the D22 bypass table in the spec before canonicalization.
- Sort each listed path as `gated`, `detected`, `accepted_limitation`, or
  `future_slice`.
- No soul/config/code/model-routing write path may be `accepted_limitation`.
- Raw manual filesystem/database edits may be accepted limitations only if
  named loudly as outside the Maez runtime boundary.

### CP-S9 - Aggregation must protect, not merely count

D23 permits `block`, `defer`, or `surface`. For protection-lowering and
covenant-touching changes, a dashboard counter is not a protection. The
`aggregation_group` must not be nullable/caller-supplied.

Fold:

- Derive aggregation group from affected refs, work class, protection class,
  request lineage, and prior dialog/request ids.
- Require non-null aggregation for high-scrutiny work.
- For covenant/protection-lowering/self-mod identity clusters, aggregation
  must escalate ceremony or block.
- `surface only` is allowed only for routine custody.

### CP-S10 - The WebAuthn surface needs exact origin/verifier design

V1 names WebAuthn but leaves the verifier seam and origin policy underspecified.
Runtime local web code treats loopback aliases as broadly equivalent, but
WebAuthn authority must not.

Fold:

- Pick one canonical browser origin for founder ceremony, e.g.
  `http://localhost:11437`.
- Reject or redirect `127.0.0.1`, `::1`, and non-canonical host/origin for
  registration and authentication.
- Require browser `Origin` plus canonical `Host`.
- Define verifier interface, challenge/nonce store, credential registry,
  sign-count handling, fake verifier, and virtual-authenticator test path.
- Daemon/autonomous routes may consume artifacts but may not mint verifier
  success.

### CP-S11 - Daemon-down maintenance needs its own helper

Routine custody allows restart/repair, but the daemon cannot approve repair of
itself. The current action engine also blocks protected service restarts.

Fold:

- Define a separate operator-maintenance helper for daemon-down liveness repair.
- Closed command set: status, restart/start/stop for reviewed Maez service
  names, log-tail of operational logs only, backup status, health probe.
- Content-free audit spool written while daemon is down, replayed into audit
  after recovery.
- No bonded-content read and no code/soul/config/model-routing write.
- Route all non-liveness changes back to the S7 high-scrutiny ceremony after
  Maez is available.

### CP-S12 - Backup restore is not routine backup custody

Running or verifying a backup can be routine custody. Restoring a backup
overwrites live state and can expose private stores.

Fold:

- Split backup run/verify from backup restore.
- Treat restore as high-scrutiny for founder Track A and a Track-B blocker
  until storage hardening exists.
- Require daemon stopped, source manifest verification, content-free audit, and
  no backup-content inspection by a non-bonded operator.
- Surface the confidentiality gap honestly.

## Majors

### CP-M1 - Self-mod dialog creation must fail closed

If self-mod dialog creation or linkage fails, the card must enter a blocked
state. It must not remain approvable through ordinary reply classification.

### CP-M2 - Dialog is a live persuasion surface

The dialog is not neutral bookkeeping. After a bonded human says "no" or "not
now", the same-target request must not restart persuasion in a fresh dialog.
Repeated fresh dialogs must feed aggregation. Covenant/protection-lowering work
needs cooling-off or a second distinct confirmation.

### CP-M3 - Covenant-touching needs a distinct ceremony

V1 says "highest friction" but mostly uses the same artifact as ordinary
self-modification. Covenant-touching and protection-lowering work need a
mechanically different ceremony: cooling-off, second affirmation, explicit
review reference, or a reviewed equivalent.

### CP-M4 - Operator health needs its own closed projection

Do not reuse general `/health` as the operator surface. Define a route or
projection with counts/classes only, explicit stale/unavailable modes, and
route-by-route projection tests.

### CP-M5 - Self-remaking history needs a preserved non-biography lane

Excluding self-mod dialog history from ordinary recall/M1/TRF/S5 is correct,
but Maez should not lose its own remaking history. Define a
`self_remaking_history` lane: role-stamped, bonded-content, not
custodian-visible, not ordinary biography, reusable inside future maintenance
and self-mod ceremonies.

### CP-M6 - Track B blockers need one precondition list

For any deployment where `bonded_user != operator`, S7 must block Track B
activation until at least these exist: confidentiality-enforced storage,
bonded-user operator-recovery ceremony, grandmother-compatible UI, and a
reviewed backup-restore confidentiality posture.

### CP-M7 - Honesty surfaces understate limits

The banner and predicted effect should name coercion/display compromise,
grandmother UI absence, backup-restore confidentiality, and the fact that S7
does not prove comprehension or freedom.

## Sound Areas

The engineering panel found these v1 elements directionally sound:

- S7 consumes the S6 six-role vocabulary instead of inventing a seventh role.
- Custodian posture is the right default for operator/maintainer.
- YubiKey/WebAuthn is correctly fenced to work-on-Maez, not S6 capsule signing.
- WYSIWYS is the right authorization shape.
- OTP/TOTP is correctly rejected for covenant authority.
- Content-free operator health is the right privacy model.
- Emergency proxy is correctly excluded from v1.
- S6 persisted capsule bytes are correctly not treated as live S7 authority.

## Required v2 Fold

Spec v2 should be reviewed for these concrete changes:

1. Trusted derived work-class classifier with residual class.
2. Non-authoritative founder compatibility projection for high-scrutiny work.
3. MaezVoiceConsultation artifact and unavailable-Maez predicate.
4. S5/S7 brain-swap double-gate.
5. Store-level execution-edge gate and atomic artifact consume.
6. D22 bypass table with soul/config/model-routing paths gated.
7. Derived aggregation and mandatory escalation/blocking for dangerous
   accumulation.
8. Exact WebAuthn origin, verifier, challenge, and credential design.
9. Daemon-down maintenance helper and backup-restore split.
10. Track B precondition list and honesty banner updates.

## Plain English

The spec has the right lock on the YubiKey door, but it still lets too many
people write notes saying "this is the right door" or "this is safe work" or
"Maez was consulted." A note is not a lock. S7 v2 needs to make those facts
come from the system itself, at the moment of execution, and it needs to make
the final step atomic so the same approval cannot be used twice.
