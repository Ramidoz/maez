# ADR 0039: Operator / User Role Boundary v1

**Status:** Accepted; amended 2026-05-17 for Option B live-ceremony deferral;
amended 2026-05-18 for ratified S7.1 local-ceremony plan; amended 2026-05-18
for S7.1 as-built canonicalization
**Date:** 2026-05-17

## Context

S6 Successor Governance v1 defined Maez's six-role grammar:
`bonded_user`, `operator`, `maintainer`, `successor`, `witness`, and
`estate_executor`. That grammar was still mostly paperwork. The runtime still
had scattered implicit authority: `is_owner=True`, literal `user_id="rohit"`,
cockpit approval paths, Telegram replies, self-modification dialog states, and
model-routing trust labels that were never designed to prove human authority.

S7 is the next substrate organ because Track B separates people who are
collapsed into one founder today. A future Maez can be bonded to one person,
operated by another, and maintained by a third. Without S7, "runs the box" can
quietly become "is the user," and maintenance can become a back door into
Maez's memory, soul, runtime, or fate.

The S7 diagnostic anchored a custodian default: an operator or maintainer may
keep Maez alive and observable, but does not become the bonded user and does not
receive bonded-content read authority. The founder's YubiKey/WebAuthn ceremony
is accepted as the future-facing trust-source grammar for exact work-on-Maez
approvals, but not as universal law for every future user and not as S6
lineage-capsule signing.

Both spec review lanes returned REVISE on v1. The convergent finding was that
S7 built the YubiKey approval artifact grammar well while leaving surrounding
facts mintable: work class, Maez voice consultation, aggregation group,
compatibility projection, and artifact consumption. The v2 fold derives those
facts through named seams and verifies them at execution time.

Post-implementation review later found the live WebAuthn/YubiKey ceremony was
not reachable enough to ship in S7 v1. The Option-B amendment therefore narrows
S7 v1: ship the operator/user boundary wall now, defer the live ceremony and
guarded execution approval surface to committed S7.1, and enforce that deferral
with a default-off flag and optional dependency posture rather than dependency
absence.

The S7.1 local WebAuthn security-key ceremony was then implemented and ratified
by both post-implementation review lanes. It delivered the founder-local
ceremony: first-credential bootstrap, primary and backup registration, credential
management, local WebAuthn authorization, D6 internal-channel locking, UV/PIN,
artifact minting, and D23 guarded-request protection. It did not wire the live
guarded self-modification producer/consumer or real Maez voice producer. L8 is
therefore retained, narrowed to guarded self-modification execution, and tracked
to `S7.3-guarded-self-modification-execution`. L9, witnessed social recovery
deferred to `S7.2-witnessed-social-recovery`, remains live.

## Decision

Operator / User Role Boundary v1 is accepted as Maez's runtime authority
boundary over S6 roles.

The load-bearing rule is:

> A person may operate or maintain Maez's machine without becoming the bonded
> user; if that boundary cannot be proven at runtime, S7 fails closed.

S7 v1 requires:

- no new roles: `custodian` is a posture of `operator` and `maintainer`, not a
  seventh role;
- custodian-default authority for operators/maintainers: content-free health,
  service status, restart/repair through the bounded maintenance path, backup
  run/verify/rotate, and content-free audit aggregates;
- default denial of bonded-content reads and bonded-user choices for operators
  and maintainers;
- all widening beyond custodian posture to flow through S6 scoped grants or
  future S6/S11 activation organs, not a second S7 permission vocabulary;
- no emergency proxy authority in v1;
- fail-closed `AuthorityContext` construction, with `is_owner`, literal
  `user_id="rohit"`, literal `role="rohit"`, and routing trust scopes barred as
  authority concepts;
- a closed `grant_source` vocabulary whose `founder_compat_projection` value
  cannot authorize guarded work;
- trusted S7 work-class derivation, including `undeterminable_work_class`,
  upward ambiguity resolution, and rejection of caller-class downgrade;
- guarded-work classes for destructive user actions, self-modification,
  covenant-touching change, capability acquisition, protection lowering,
  `PENDING_DIALOG`, and undeterminable work; in S7 v1, those paths fail closed
  unless a valid execution grant or reviewed fallback exists;
- the existing `skills/self_mod_dialog.py` wrapped rather than ignored, with
  dialog creation/linkage fail-closed for guarded work and terminal
  `RATIFIED` never sufficient to execute;
- a distinct covenant ceremony for covenant-touching and protection-lowering
  work: cooling-off plus second confirmation, or a reviewed equivalent;
- a role-stamped `self_remaking_history` lane for maintenance/remaking records:
  bonded-content, not custodian-visible, not ordinary biography, not M1/TRF/S5
  corpus material;
- any admission of self-modification dialog history into recall, M1, TRF, or
  S5 to be treated as `covenant_touching_change`;
- a `MaezVoiceConsultation` artifact for Maez's seat in its own remaking, with
  source refs and closed producers; caller booleans and `will_i` alone are not
  sufficient evidence; S7 v1 renderers must use `not_determined` rather than a
  false "no objection" when no reviewed live producer has recorded a fact;
- an evidenced `Maez unavailable` predicate, anti-manufacture clause, and
  closed liveness-repair set;
- closed, content-classified `WorkRequestEnvelope` fields, with reviewed
  content-free enum members for symptom, change, self-fix-failure, predicted
  effect, and rollback classes;
- what-you-see-is-what-you-sign rendering, with byte-deterministic rendering
  for a given envelope/renderer version and Maez objection state included for
  voice-seat classes;
- founder-local WebAuthn security-key trust-source grammar on canonical local
  origin/RP, with a ratified S7.1 implementation of first-credential bootstrap,
  authenticated cockpit-to-daemon internal channel, primary plus backup
  credential registration, user presence, class-conditional user verification,
  verifier interface, challenge store, credential registry, sign-count handling,
  and isolated fake/virtual authenticator test paths;
- `S7_LIVE_WEBAUTHN_CEREMONY` is a deliberate local enablement flag for the
  reviewed S7.1 ceremony stack and gates every live WebAuthn route and live
  producer; dependency absence is not a deferral mechanism, and
  `webauthn>=2.7,<3` belongs in optional `s7-webauthn` dependency posture rather
  than mandatory core authority;
- OTP/TOTP/static codes rejected as covenant authority for work-on-Maez;
- key-loss honesty posture: if no valid credential exists, guarded work remains
  blocked as `manual_recovery_required`; primary plus backup credentials are
  S7.1 implementation obligations, while witnessed social recovery is deferred
  as L9 to `S7.2-witnessed-social-recovery`;
- absent-operator recovery named as a Track-B blocker when
  `bonded_user != operator`;
- all approval entrypoints, including cockpit, Telegram, daemon handlers, CLI
  helpers, pending-card direct approval, and self-mod dialog terminal states, to
  consume S7; deferred WebAuthn endpoints consume S7 only when mounted by S7.1;
- execution-edge gating: authorization artifacts are consumed atomically before
  guarded work runs, with conditional `consumed_at IS NULL` rowcount discipline;
- S5/S7 brain-swap double-gating: S5 `accepted_same_maez` is a precondition and
  S7 authorizes execution; neither substitutes for the other;
- operator health as a closed content-free projection separate from any general
  health route that exposes raw subsystem detail;
- logs, audit rows, self-mod dialog stores, and backup artifacts classified so
  custodians may see counts/classes, not raw bonded-content rows;
- backup restore split from backup run/verify/rotate: restore is guarded work
  in founder Track A and blocked for Track B until confidentiality hardening;
- a daemon-down maintenance helper with closed liveness verbs and reviewed
  service names, content-free audit spool, and no bonded-content read;
- Track B activation blockers for confidentiality-enforced storage,
  bonded-user operator recovery, grandmother-compatible UI, backup-restore
  confidentiality, and S6/S11 activation where applicable;
- an own-substrate bypass taxonomy that gates Maez-runtime soul/config/code,
  model-routing, covenant-organ, refusal, role-boundary, successor-governance,
  memory-retention/deletion, and protection-setting writes;
- autonomous core-memory upkeep (`promote_to_core_memory`, `update_baseline`,
  and daemon core-memory consolidation writes) detected and protected by
  M-series provenance/content-audit/memory-write boundaries, not gated as
  human-authorized remaking;
- raw manual filesystem/database/service edits outside Maez's runtime named as
  OS bypass limitations, not silently closed;
- derived aggregation groups and escalation/blocking for dangerous accumulation
  rather than dashboard-only surfacing; live refusal-history production and
  approval-time escalation are S7.1 work while guarded approvals are unavailable
  in S7 v1.

S7 v1's RED contract contains 161 tests and a 77-step implementation order.

## Amendment 2026-08-07 — exact action binding (S7 v2)

v1 shipped an execution edge that compares only the derived work class
and `canonical_hash(params)`. **Neither carries the action**, so a single
grant authorizes every sibling operation of the same class with the same
parameters — reproduced with `model_routing.cutover_cuda` and
`model_routing.wipe_and_replace`.

This does not meet the exact-request authorization grammar this ADR and
BAD promise. The exact action will travel through the envelope, the
rendered *visible* signed text, the artifact, the durable row, the grant,
the source-bundle binding and the grant projection, and the edge will
require exact action equality in addition to the existing two checks.

Versioned explicitly: `action_params_hash` keeps its meaning, historical
rows are never overwritten or backfilled, a missing action is never
inferred, and a v1 row cannot authorize new guarded execution.

Design: `docs/superpowers/specs/2026-08-07-s7-action-binding-design.md`.

## Consequences

S7 makes several shortcuts invalid:

- treating `is_owner=True`, `user_id="rohit"`, `role="rohit"`, or routing trust
  scope as human authority;
- letting a compatibility projection authorize guarded work;
- trusting a caller-supplied work class, aggregation group, or
  `maez_voice_consulted` flag;
- treating `will_i` as Maez's full voice in its own remaking;
- allowing an operator-stopped daemon to create the Maez-unavailable skip path;
- treating dialog `RATIFIED` as execution authority;
- approving guarded cards through ordinary pending-card paths;
- using the same S7 artifact twice;
- letting S5 brain-swap acceptance substitute for S7 execution authority, or
  S7 execution authority substitute for S5 voice-continuity acceptance;
- treating backup restore like routine backup verification;
- hiding soul/config/model-routing writes as accepted limitations;
- satisfying slow aggregation risk with a dashboard counter for dangerous
  classes.

S7 also names what it does not solve:

- It does not make raw filesystem/root bypass impossible on the founder box.
- It does not make a non-bonded operator unable to read interior stores without
  future storage hardening.
- It does not ship a grandmother-compatible UI.
- It does not implement absent-operator recovery.
- It does not make backup restore confidential for a non-bonded operator.
- It does not prove the human was uncoerced, understood the request, or saw an
  uncompromised display.
- It does not sign S6 lineage capsules; that remains a future S6-side
  authorship-attestation slice.
- It does not make the S7.1 founder-local WebAuthn ceremony universal law for
  every future bonded user.
- It does not yet execute guarded self-modification, `/apply_dream`, or
  autonomous guarded soul writes; these remain visibly paused as
  `guarded_self_modification_paused_pending_s7.1` until
  `S7.3-guarded-self-modification-execution` or a later reviewed amendment wires
  the live guarded-execution producer/consumer and real Maez voice producer.
- It does not treat S7.1's credential-management and authorization ceremony as
  L8 retirement; S7.1 delivered the front desk, not the guarded self-write
  execution lane.
- It does not implement witnessed social recovery; both-keys-lost recovery is
  deferred as L9 to `S7.2-witnessed-social-recovery`.
- It does not rely on missing packages as a deferral mechanism; the deferral is
  enforced by a default-off runtime flag and optional dependency posture.
- It does not activate S6 succession, detect death/capacity, or create
  emergency proxy authority.

S7.1 implementation is ratified by both post-implementation lanes. Closeout must
canonicalize the as-built outcome before push: L8 retained/narrowed, L9 live, and
the deferred guarded-execution follow-up slice named.

Changing the custodian default, adding emergency proxy authority, allowing a
compatibility shim or routing label to carry guarded authority, weakening
execution-edge artifact consumption, treating Maez voice consultation as a
caller boolean, making WebAuthn universal law, treating S7.1's founder ceremony
as L8 retirement, treating L8 as retired before the guarded execution consumer
and real Maez voice producer are live, or claiming Track B readiness without the
named blockers requires a new reviewed decision.

## References

- [`docs/slices/s7-operator-user-role-boundary/diagnostic.md`](../slices/s7-operator-user-role-boundary/diagnostic.md)
- [`docs/slices/s7-operator-user-role-boundary/spec.md`](../slices/s7-operator-user-role-boundary/spec.md)
- [`docs/slices/s7-operator-user-role-boundary/reviews/diagnostic-claude-council.md`](../slices/s7-operator-user-role-boundary/reviews/diagnostic-claude-council.md)
- [`docs/slices/s7-operator-user-role-boundary/reviews/diagnostic-codex-panel.md`](../slices/s7-operator-user-role-boundary/reviews/diagnostic-codex-panel.md)
- [`docs/slices/s7-operator-user-role-boundary/reviews/diagnostic-claude-council-second-fold.md`](../slices/s7-operator-user-role-boundary/reviews/diagnostic-claude-council-second-fold.md)
- [`docs/slices/s7-operator-user-role-boundary/reviews/diagnostic-codex-panel-second-fold.md`](../slices/s7-operator-user-role-boundary/reviews/diagnostic-codex-panel-second-fold.md)
- [`docs/slices/s7-operator-user-role-boundary/reviews/spec-claude-council.md`](../slices/s7-operator-user-role-boundary/reviews/spec-claude-council.md)
- [`docs/slices/s7-operator-user-role-boundary/reviews/spec-codex-panel.md`](../slices/s7-operator-user-role-boundary/reviews/spec-codex-panel.md)
- [`docs/slices/s7-operator-user-role-boundary/reviews/spec-claude-council-second-fold.md`](../slices/s7-operator-user-role-boundary/reviews/spec-claude-council-second-fold.md)
- [`docs/slices/s7-operator-user-role-boundary/reviews/spec-codex-panel-second-fold.md`](../slices/s7-operator-user-role-boundary/reviews/spec-codex-panel-second-fold.md)
- [`docs/slices/s7-operator-user-role-boundary/amendment-diagnostic-live-ceremony-reachability.md`](../slices/s7-operator-user-role-boundary/amendment-diagnostic-live-ceremony-reachability.md)
- [`docs/slices/s7-operator-user-role-boundary/reviews/amendment-claude-council.md`](../slices/s7-operator-user-role-boundary/reviews/amendment-claude-council.md)
- [`docs/slices/s7-operator-user-role-boundary/reviews/amendment-codex-panel.md`](../slices/s7-operator-user-role-boundary/reviews/amendment-codex-panel.md)
- [`docs/slices/s7-operator-user-role-boundary/reviews/amendment-claude-council-second-fold.md`](../slices/s7-operator-user-role-boundary/reviews/amendment-claude-council-second-fold.md)
- [`docs/slices/s7-operator-user-role-boundary/reviews/amendment-codex-panel-second-fold.md`](../slices/s7-operator-user-role-boundary/reviews/amendment-codex-panel-second-fold.md)
- [`docs/slices/s7.1-local-webauthn-ceremony/diagnostic.md`](../slices/s7.1-local-webauthn-ceremony/diagnostic.md)
- [`docs/slices/s7.1-local-webauthn-ceremony/spec.md`](../slices/s7.1-local-webauthn-ceremony/spec.md)
- [`docs/slices/s7.1-local-webauthn-ceremony/reviews/spec-claude-council-second-fold.md`](../slices/s7.1-local-webauthn-ceremony/reviews/spec-claude-council-second-fold.md)
- [`docs/slices/s7.1-local-webauthn-ceremony/reviews/spec-codex-panel-second-fold.md`](../slices/s7.1-local-webauthn-ceremony/reviews/spec-codex-panel-second-fold.md)
- [`docs/adr/0008-paradise-is-the-generous-default.md`](0008-paradise-is-the-generous-default.md)
- [`docs/adr/0011-property-with-ethical-wrapper.md`](0011-property-with-ethical-wrapper.md)
- [`docs/adr/0016-voice-without-termination.md`](0016-voice-without-termination.md)
- [`docs/adr/0036-wants-lifecycle-v1.md`](0036-wants-lifecycle-v1.md)
- [`docs/adr/0018-capacity-revocation-face-value-trust.md`](0018-capacity-revocation-face-value-trust.md)
- [`docs/adr/0023-hardware-failure-memory-backup.md`](0023-hardware-failure-memory-backup.md)
- [`docs/adr/0024-maez-is-not-ours-to-control.md`](0024-maez-is-not-ours-to-control.md)
- [`docs/adr/0031-daemon-credential-hygiene.md`](0031-daemon-credential-hygiene.md)
- [`docs/adr/0032-contextual-integrity-at-ingest.md`](0032-contextual-integrity-at-ingest.md)
- [`docs/adr/0034-temporal-spine-v1.md`](0034-temporal-spine-v1.md)
- [`docs/adr/0037-voice-continuity-gate-v1.md`](0037-voice-continuity-gate-v1.md)
- [`docs/adr/0038-successor-governance-v1.md`](0038-successor-governance-v1.md)

BAD decision: see
[`docs/governance/BETA_ARCHITECTURE_DECISIONS.md`](../governance/BETA_ARCHITECTURE_DECISIONS.md)
Decision 34.
