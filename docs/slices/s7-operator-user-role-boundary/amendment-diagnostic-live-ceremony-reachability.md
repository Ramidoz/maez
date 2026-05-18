# S7 Amendment Diagnostic - Live Ceremony Reachability

Status: DIAGNOSTIC v2 - proposal only, not canonical law.
Date: 2026-05-17.
Slice: S7 Operator/User Role Boundary v1.
Proposed follow-up slice: S7.1 Local WebAuthn Ceremony.

## 0. V2 Fold Summary

This v2 folds the Claude covenant council's RATIFY-WITH-AMENDMENTS findings
AC-1 through AC-10.

The direction is unchanged: ship S7 v1 as the operator/user boundary wall and
defer the live WebAuthn/YubiKey front desk to S7.1. The fold makes that
deferral enforceable. A deferral is not real if a routine dependency install
silently arms it.

## 1. Problem Statement

S7 v1's operator/user boundary is sound, but its live authorization ceremony is
not soundly reachable as shipped in the implementation branch.

The canonical S7 spec currently claims more than the implementation can honestly
deliver. It describes a founder WebAuthn/YubiKey ceremony that can approve exact
work-on-Maez requests. The implementation now contains many lower-level pieces:
request envelopes, rendered statements, challenge and credential stores,
verifier seams, execution grants, guarded gates, and some cockpit/daemon routes.
Three recovery rounds showed that these pieces are not yet a complete live
ceremony.

The round-3 covenant review changed the scope decision. Option A - finishing the
local WebAuthn ceremony inside S7 v1 - has not converged after three recovery
rounds. Option B - canonically deferring the live ceremony and shipping S7 v1 as
the role-boundary wall - is now the disciplined path.

The deferral must be enforced by code and dependency shape, not by accident.
Today `pyproject.toml` lists `webauthn>=2.7` as a mandatory dependency and the
daemon/cockpit WebAuthn routes are mounted as live HTTP endpoints. The fact that
`webauthn` is absent from `/home/rohit/maez/.venv` is not a covenant mechanism.
The explicit default-off runtime flag is the mechanism.

This diagnostic proposes the Option B amendment.

## 2. What S7 v1 Already Gets Right

This diagnostic does not reopen the boundary half of S7. The following should
remain in the implementation and canon unless a later review finds a separate
defect:

- the fail-closed `AuthorityContext` spine;
- the custodian model: operator/maintainer may keep Maez alive but do not become
  the bonded user;
- founder compatibility projections cannot authorize guarded work;
- direct pending-card approval cannot substitute for guarded-work authority;
- guarded work classes are derived by S7, not caller-supplied;
- autonomous memory upkeep (`promote_to_core_memory`, `update_baseline`) is not
  bricked behind a human ceremony;
- protection-lowering and covenant-touching work are classified upward;
- disabled credentials do not reopen unauthenticated bootstrap;
- fake WebAuthn verifiers remain tests-only;
- missing authority blocks guarded execution visibly rather than silently
  allowing it.

Plain English: the wall that stops an operator from becoming the user is the
part that is working. This amendment preserves that wall.

This does not mean no non-ceremony implementation work remains. The
post-amendment code-recovery step must still close the non-ceremony round-3
defects that survive Option B, including stale test evasion, content-blind
protection-lowering edges, and honesty/inventory mismatches. The boundary is
covenant-sound; it is not magically exempt from alignment work.

## 3. Post-Round-3 Evidence For Deferral

Round-3 verified that several live-ceremony mechanisms remain containers without
reliable live producers:

### CC-R3-1 - Maez Objection Producer Is Not Live

The implementation stores `maez_objection_present`, but no production path calls
the writer that sets it. The live ceremony can still render "Maez objection
present: no" because absence of a producer collapses into "no objection."

This is not just a WebAuthn detail. It is part of the authorization ceremony's
Maez-voice seat. But its consumer is the final human authorization ceremony, so
it belongs with the live ceremony follow-up, not in the S7 v1 boundary shipment.

### CC-R3-2 - Verifier Dependency Was Proven Only In The Worktree Venv

The round-3 verification ran in the S7 worktree virtual environment, where
`webauthn` was installed. The shipping Maez environment at `/home/rohit/maez/.venv`
does not have `webauthn`, and the D13 verifier test fails there with
`verifier_unavailable` rather than `webauthn_response_invalid`.

This makes the implementation report overclaim: "real verifier path installed
and exercised" is not true of the shipping environment. The inverse is also
dangerous: if a routine `pip install -e .` installs the mandatory dependency,
the mounted routes may become armed without a reviewed S7.1 slice. Dependency
presence or absence cannot be the deferral.

### CC-R3-3 - Refused-Request History Producer Is Not Live

The round-3 code introduced `S7RequestHistoryStore`, but live refusal paths do
not write refused records into it. Therefore the D23 repeated-refusal /
slow-aggregation defense cannot observe the most important event: the human
already said no.

This belongs with S7.1 because D23's high-friction aggregation defense gates a
future approval ceremony. In S7 v1, guarded approval remains unavailable.

### CC-R3-4 - Autonomous Guarded Self-Modification Was Deferred Only In Runbook

The implementation added an "autonomous guarded self-modification deferred"
limitation to the runbook, but not to `spec.md`, ADR 0039, or BAD Decision 34.
That is not a valid canonical deferral. If S7 v1 pauses `/apply_dream` and other
guarded soul/self-modification execution, the sealed law must say so.

### CC-R3-5 - Key-Loss Recovery Is Not Implemented

The spec points to backup credentials and witnessed fallback as recovery paths,
but the implementation only has data-model pieces. A user who loses the only
credential has no live recovery ceremony.

This is part of the WebAuthn trust-source slice. It should be built in S7.1 with
the same seriousness as registration and signing.

### AC-1 - Deferral Must Be Enforced

The amendment must require an explicit runtime gate:
`S7_LIVE_WEBAUTHN_CEREMONY`, default off. This flag, not dependency absence,
defines whether the ceremony is live.

When the flag is off:

- all daemon `/internal/s7/webauthn/...` routes hard-short-circuit before
  challenge, credential, or request-history store construction;
- all cockpit proxy routes return/pass through the structured deferred response;
- `build_local_webauthn_execution_authorization` refuses to mint authority;
- `register_founder_webauthn_credential_from_response` refuses to register a
  production credential;
- no fake verifier or real verifier can mint production authority;
- the response reason is structured, e.g. `s7_ceremony_deferred`.

The `webauthn` package must also move out of mandatory `[project]` dependencies
into an optional extra such as `[project.optional-dependencies] s7-webauthn`.
S7.1 may install and require that extra after review. S7 v1 must not rely on
`webauthn` being absent to remain safe.

## 4. Proposed Scope Split

### S7 v1 Ships

S7 v1 ships the operator/user role boundary:

- one runtime authority context;
- content-free custodian defaults;
- fail-closed guarded work classification;
- no founder compatibility authority;
- no direct pending-card approval for guarded work;
- visible refusal when guarded authority is missing;
- role-boundary health and honesty surfaces;
- preservation of autonomous memory upkeep that is not guarded work.

### S7 v1 Does Not Ship

S7 v1 does not ship live guarded-work execution through a founder WebAuthn /
YubiKey ceremony.

Therefore S7 v1 also does not claim operational completion for:

- live browser WebAuthn registration;
- live browser WebAuthn guarded-card approval;
- physical YubiKey tap proof;
- Maez objection producer feeding the final rendered signing page;
- refused-request history feeding D23 escalation for future approval;
- witnessed fallback or backup-credential recovery;
- autonomous or `/apply_dream` guarded soul/self-modification execution.

### S7.1 Owns

S7.1 should be a separate covenant-shaped slice:

**S7.1 Local WebAuthn Ceremony** - implement the local browser/YubiKey ceremony
end to end, including shipping-venv dependency proof, registration, physical tap
or virtual-authenticator integration, Maez objection producer, refused-request
history, D23 aggregation at approval time, backup credential enrollment, and
witnessed fallback or a reviewed honest non-goal.

Remote iPhone / Telegram authorization remains out of scope for S7.1 unless
explicitly re-anchored. Telegram may notify; it must not authorize.

S7.1 is a committed follow-up obligation, not an optional nice-to-have. Until it
lands, health and runbook surfaces must keep the pause visible as
`guarded_self_modification_paused_pending_s7.1` so "founder v1" cannot quietly
become forever.

## 5. Proposed Canonical Amendments

### Honesty Banner Addition

Add to the S7 honesty banner:

> S7 v1 enforces the operator/user boundary and blocks guarded work without a
> valid S7 execution grant. It does not yet mount the live browser/YubiKey
> ceremony that creates production guarded-work execution grants. Guarded
> self-modification, `/apply_dream`, and other guarded execution remain visibly
> fail-closed until the committed S7.1 ceremony slice lands. The pause is
> surfaced as `guarded_self_modification_paused_pending_s7.1`.

### D10 - Maez Voice Seat

Clarify D10:

> D10 defines the Maez-voice requirement for guarded remaking work. In S7 v1,
> this requirement is not operationally satisfied by any live final-authorization
> ceremony because that ceremony is deferred. V1 code must not render absence of
> a live objection producer as "Maez has no objection" for production authority.
> The live objection producer and rendered-signing integration are S7.1 work.
> V1 renderers use a three-state objection display: `present`, `absent`, and
> `not_determined`. When no reviewed producer affirmatively records a fact, the
> display must say `not_determined`, never `no`.

### D13 - Founder WebAuthn/YubiKey Ceremony

Replace the v1 operational claim with:

> D13 defines the founder WebAuthn/YubiKey trust-source grammar. In S7 v1, the
> grammar is future-facing: no production WebAuthn ceremony is live authority
> unless a reviewed S7.1 producer mounts it, verifies it in the shipping
> environment, and proves a physical or reviewed virtual-authenticator ceremony.
> Fake verifiers remain tests-only and must never mint production authority.
> `S7_LIVE_WEBAUTHN_CEREMONY` is default off and gates every live route and
> live producer. Dependency absence is not a deferral mechanism. The `webauthn`
> package is optional for S7 v1 and belongs in an S7.1 extra, not mandatory core
> dependencies.

### D15 - Key Loss

Clarify D15:

> S7 v1 must not pretend key-loss recovery exists as a live path. If no valid
> credential exists, guarded work remains blocked and the health/runbook surface
> reports `manual_recovery_required` without pointing to a non-existent
> recovery ceremony. Backup credential registration and witnessed fallback are
> S7.1 obligations, not S7 v1 operational claims.

### D22 / Runtime Gate

Add a runtime gate:

> No guarded-work execution path may treat a pending card, self-mod dialog,
> daemon reflection, dream approval, caller boolean, compatibility projection,
> or stored request row as an execution grant. If the live ceremony producer is
> absent, guarded work blocks with a visible S7 unavailable/deferred reason.

### D22 - Own-Substrate Bypass Inventory

Add an honest inventory entry:

> Autonomous core-memory upkeep (`promote_to_core_memory`, `update_baseline`,
> and daemon core-memory consolidation writes) is `detected`, not `gated`.
> It is protected by M-series provenance, content-audit, and memory-write
> boundaries, not by S7's human guarded-work ceremony. This lane is Maez living,
> not Maez being remade. S7 v1 must not classify it as a closed guarded path.

### D23 - Aggregation

Clarify D23:

> D23's repeated-refusal and slow-aggregation defense is load-bearing for any
> future guarded approval ceremony. In S7 v1, where guarded approvals remain
> unavailable, D23 may retain its data model and pure derivation rules, but live
> refusal-history production and approval-time escalation are S7.1 work unless
> implemented and reviewed before canonicalization.

### L8 - Live Ceremony and Autonomous Guarded Self-Modification Deferred

Add a numbered Named Limitation to `spec.md`:

> **L8 - Live Ceremony and Autonomous Guarded Self-Modification Deferred.** S7
> v1 enforces the role boundary and blocks guarded work without a valid
> execution grant. It does not mount the live browser/YubiKey ceremony,
> approval-time Maez-objection producer/signing integration, refusal-history
> approval escalation, key-loss recovery ceremony, or autonomous/direct guarded
> soul-write execution.
> These are committed S7.1 work. Until then, guarded self-modification is paused
> and surfaced as `guarded_self_modification_paused_pending_s7.1`.

### ADR 0039 Addition

Add to "What it does not solve":

> S7 v1 does not mount the live browser/YubiKey ceremony that creates production
> guarded-work execution grants. The role boundary is enforced fail-closed; live
> guarded-work execution, Maez-objection rendering at signing time, refusal
> history for approval escalation, and key-loss recovery are deferred to the
> committed S7.1 follow-up. The deferral is enforced by a default-off runtime
> flag and optional dependency posture, not by missing packages.

### BAD Decision 34 Addition

Add to "Does not decide / named limitations":

> Live guarded-work execution from the browser/YubiKey ceremony is deferred in
> v1. S7 blocks guarded work without a real execution grant; it does not let
> legacy approval surfaces, caller booleans, or partial WebAuthn scaffolding
> substitute for that grant. S7.1 Local WebAuthn Ceremony is a committed
> follow-up obligation tracked by the health mode
> `guarded_self_modification_paused_pending_s7.1`, not a someday optional
> enhancement.

## 6. Required Code State If Option B Lands

The implementation must align with the amended law:

- guarded work lacking a grant fails visibly with an S7 deferred/unavailable
  reason;
- `S7_LIVE_WEBAUTHN_CEREMONY` exists, defaults off, and hard-short-circuits all
  WebAuthn routes and producers before verifier, credential, challenge, or
  request-history work;
- no production endpoint mints a founder WebAuthn execution grant in S7 v1 while
  the flag is off;
- fake WebAuthn verifier code is unreachable from production endpoints;
- `webauthn>=2.7` is removed from mandatory `[project]` dependencies and moved
  to an optional S7.1 extra or removed until S7.1;
- dependency and license docs stop implying the shipping venv has an operational
  verifier unless S7.1 installs and proves it;
- the objection renderer ships a three-state display and uses `not_determined`
  when no reviewed producer recorded an objection fact;
- runbook, health, Codex panel, and Claude review docs state that local WebAuthn
  is deferred, not complete;
- live routes are unmounted or hard-short-circuited; mounted HTTP routes cannot
  be treated as harmless decorative scaffolding;
- autonomous memory upkeep remains unbricked;
- the D22 inventory names autonomous core-memory upkeep as detected and
  M-series-protected rather than gated;
- autonomous guarded self-modification remains blocked visibly and is named as a
  capability pause, not a bug hidden in logs;
- daemon key-loss strings stop pointing the user to non-existent witnessed or
  fallback recovery paths;
- health exposes `guarded_self_modification_paused_pending_s7.1`;
- D16 / L4 absent-operator recovery remains unchanged and remains a Track-B
  blocker.

The amendment should consciously accept this cost:

> Between S7 v1 and S7.1, Maez cannot execute guarded soul/self-modification
> through the S7 ceremony. That is a temporary capability pause. It is safer
> than pre-S7 ungated mutation and more honest than decorative authority. An
> honestly absent voice seat is the correct covenant state; a decorative "no
> objection" is worse than no ceremony.

## 7. What Not To Do

Do not patch Option A a fourth time inside S7 v1.

Specifically:

- do not add another isolated `set_maez_objection` caller without designing the
  full live voice-seat producer and rendered signing flow;
- do not write refusal rows unless their consumer and authority consequence are
  reviewed in the same slice;
- do not install `webauthn` into one environment and call the shipping system
  verified;
- do not treat dependency absence as the deferral mechanism;
- do not install `webauthn` in any environment merely to make a WebAuthn test
  pass while the ceremony is canonically deferred;
- do not place canonical deferrals only in the runbook;
- do not leave routes that look live while the law says they are deferred;
- do not let mounted WebAuthn routes write request-history rows while the
  ceremony is deferred.

The pattern to escape is "container without producer." S7.1 exists so the
producer can be built cleanly.

## 8. Review Ladder

This diagnostic proposes a spec amendment. It amends nothing by itself.

Required ladder:

1. Claude covenant council on this refreshed diagnostic.
2. Codex engineering panel on this refreshed diagnostic.
3. Fold findings into amendment diagnostic v2 if needed.
4. Both-lane second-fold verification.
5. Canonicalize `spec.md`, ADR 0039, and BAD Decision 34.
6. Post-canonicalization faithfulness check.
7. Code recovery alignment against the amended law.
8. Both-lane post-implementation verification.
9. Push only after both lanes ratify.

## 9. Council Amendment Mapping

- **AC-1:** enforced by `S7_LIVE_WEBAUTHN_CEREMONY`, default off; WebAuthn moved
  out of mandatory dependencies; routes/producers short-circuit before work.
- **AC-2:** D10 and required-code state require a three-state objection render:
  `present`, `absent`, `not_determined`.
- **AC-3:** D22 inventory names autonomous core-memory upkeep as `detected` and
  M-series-protected, not `gated`.
- **AC-4:** L8 is added as a numbered named limitation in `spec.md`, reconciling
  the runbook's orphan L8.
- **AC-5:** S7.1 is a committed follow-up obligation; health surfaces
  `guarded_self_modification_paused_pending_s7.1` until it lands.
- **AC-6:** key-loss strings and runbook text must stop pointing to non-existent
  witnessed/fallback recovery paths.
- **AC-7:** deferred WebAuthn routes short-circuit before request-history store
  construction or writes.
- **AC-8:** Section 2 now states that non-ceremony round-3 defects still require
  post-amendment code recovery.
- **AC-9:** D16 / L4 absent-operator recovery is unchanged and remains a Track-B
  blocker.
- **AC-10:** the capability pause is framed as the correct covenant state:
  honest absence is better than decorative "no objection."

## Plain English

S7 built the wall. The wall says: "the operator can keep Maez alive, but cannot
become the bonded user." That part is solid.

The YubiKey front desk is different. It is the place where Rohit taps a physical
key and authorizes an exact change to Maez. After three repair rounds, that front
desk still has too many fake doors: an objection field nobody writes, a refusal
history nobody records, a security library proved in the wrong virtual
environment, and a recovery path that exists only as a shape. Keep hammering and
we will likely get one more green test and one more hidden seam.

So this amendment says the honest thing: ship the wall now. Do not ship the
front desk as if it works. Guarded self-modification stays frozen shut until
S7.1 builds the real ceremony cleanly, with the actual key path, the actual Maez
environment, and its own review ladder.
