# Codex Engineering Panel - S7.1 Spec v1

**Subject:** `e066469` - `docs(s7.1): draft local webauthn spec`
on branch `s7.1-local-webauthn-ceremony`, reviewed against ratified diagnostic
v2 (`8a1b787`), the S7.1 diagnostic second-fold records, and merged S7 main
(`ce593bf`).

**Review date:** 2026-05-18

**Verdict: REVISE.** The spec is a strong draft, but it is not ready to advance
to second-fold. The data model and route shape are mostly in the right family:
registration plus authorization are in scope, the rejected Option-A code is not
being reused, the verifier is optional, the artifact type is the sealed
`S7AuthorizationArtifact`, and the full D12 envelope is present. The engineering
failure pattern is narrower and sharper: several authority boundaries are named
as guarantees while the mechanism that enforces them is still unspecified.

The Codex panel independently corroborates the Claude veto root: first
registration is still not an engineering lock. This lane also adds one
implementation-specific blocker the covenant synthesis did not foreground:
S7.1's daemon "internal" authority routes cannot rely on the existing
origin/referer guard alone, because the current guard intentionally allows
originless local clients such as `curl` and the web-to-daemon proxy.

## Method

Read firsthand:

- `docs/slices/s7.1-local-webauthn-ceremony/spec.md`
- `docs/slices/s7.1-local-webauthn-ceremony/reviews/spec-claude-council.md`
- `docs/slices/s7.1-local-webauthn-ceremony/diagnostic.md`
- `docs/slices/s7.1-local-webauthn-ceremony/reviews/diagnostic-codex-panel-second-fold.md`
- `core/infra/http_security.py`
- `daemon/maez_daemon.py`
- `skills/web_interface.py`

This is a spec review. No implementation tests were run because no
implementation code is being evaluated at this step. The useful verification is
whether the spec gives implementers unambiguous locks to build and RED tests to
prove.

## What Is Sound

- **The diagnostic scope is preserved.** The spec keeps local-only founder scope,
  registration plus authentication, primary plus backup, no Telegram/iPhone
  authorization, and no Option-A stash reuse.
- **The verifier dependency posture is pointed correctly.** `webauthn` is in an
  optional `s7-webauthn` extra, not a mandatory dependency.
- **The artifact type is corrected.** The spec uses sealed
  `S7AuthorizationArtifact`, not a parallel execution-authorization type.
- **The D12 binding set is present.** Authorization challenges carry the full
  signed-envelope material rather than the old partial-hash shape.
- **The live producer topology is mostly right.** Cockpit is a browser facade;
  daemon owns durable state; a shared core ceremony service is the only intended
  authority producer. Keep that spine.

## Blockers

### CP-S1 - First-credential bootstrap is still not an enforceable root of trust

D2 says the first primary credential is authorized by an "owner-run CLI/TTY"
bootstrap token, but the spec does not define a control that distinguishes the
owner's shell from an operator's shell on the same machine. "Runs only from the
local repo environment" is not an identity boundary. Any local shell that can
run the repo can run the command.

The token itself is also underspecified as an authority carrier. D2 says the CLI
"prints the raw token once" and the cockpit first-registration flow requires it.
That makes the raw token a bearer secret. If it appears in terminal scrollback,
logs, screenshots, shell capture, or a shared console, possession of that string
is enough to begin enrollment. The spec claims "ordinary operator/cockpit access
cannot enroll the founder key," but the actual mechanism only proves possession
of a local bearer string.

The race is the second half of the same root. The CLI refuses a new intent only
when an enabled primary already exists; it does not cap unconsumed, unexpired
intents. The begin flow checks empty-primary state, then finish stores the
credential and consumes the bootstrap later. Without a conditional consume and
insert in the same transaction, two valid tokens can race to two primary
credentials.

**Required fold:** D2 must specify a concrete first-bootstrap lock. At minimum:
one live bootstrap intent at a time or sibling invalidation on success; CSPRNG
token strength and hash algorithm; token consume SQL with conditional rowcount;
credential insert and bootstrap consume in one transaction; a guarded condition
that reasserts no enabled primary exists inside that transaction; a persistent
"bootstrap permanently closed" marker that is not reopened by deleting one row;
and RED tests for non-owner invocation, leaked/invalid token, multiple live
intents, concurrent first registration, and disabled/deleted primary not
reopening bootstrap.

If the spec cannot distinguish owner shell from operator shell, it must narrow
the claim honestly: cockpit HTTP access alone cannot enroll the first key, but
S7.1 does not defeat an operator with local shell under inherited L1.

### CP-S2 - Daemon internal authority routes have no channel authentication

D6 defines both public cockpit routes and daemon internal routes. D7 says
non-browser local daemon/proxy calls are allowed only on explicitly internal
paths. In the current codebase, the browser-write guard explicitly allows
originless local clients:

```python
No Origin/Referer means a non-browser local caller such as urllib,
curl, or the web-to-daemon proxy. Those remain allowed.
```

That policy is safe enough for ordinary local service traffic, but S7.1's daemon
routes are authority-minting surfaces. If `/internal/s7/webauthn/...` is
reachable by any originless local `curl`, then a local process can bypass the
cockpit facade and hit the daemon route directly. The spec says "internal," but
it does not define how the daemon distinguishes the cockpit proxy from arbitrary
local callers.

Origin/referer checks do not solve this. They are browser-origin protections,
not local channel authentication. The exact class S7 cares about includes
operators with shell access; the internal route boundary must be stronger than
"no Origin header."

**Required fold:** specify the daemon internal-channel lock. Acceptable shapes
include a private web-to-daemon bearer token not exposed to the browser, a Unix
domain socket with filesystem permissions, a loopback port bound only behind an
authenticated local proxy, or another reviewed channel. The RED contract must
include "originless local curl to daemon internal register/authorize routes is
rejected" while cockpit-to-daemon proxy calls still work. Without this, the route
topology has a named internal boundary but no lock.

### CP-S3 - D13 user verification/PIN is inherited but not operationalized

Inheritance names "D13 class-conditional user verification/PIN for guarded
classes." The rest of the spec never turns that inheritance into executable
requirements. There is no credential field for UV capability or UV policy, no
challenge field for UV-required work, no authorization step requiring the
verification result's user-verified bit, and no RED test for UV-required guarded
classes.

As written, a presence-only touch can satisfy the ceremony for the highest-risk
classes. That is weaker than S7's inherited D13 posture and would collapse the
friction exactly where the ceremony is meant to be loudest.

**Required fold:** add an operative UV/PIN decision. Registration records
whether the credential can satisfy user verification when the browser/library
reports it; authorization for self-modification, covenant-touching,
capability-acquisition, and protection-lowering work requires a verified UV
result when supported; the UV-required policy joins the signed challenge
material; and tests prove presence-only assertions fail for UV-required guarded
classes.

### CP-S4 - L8 retirement is claimed before the `/apply_dream` execution flow is specified

D15 proposes to retire L8 fully and clear the
`guarded_self_modification_paused_pending_s7.1` health mode. The spec names the
autonomous/direct guarded paths, including `/apply_dream`, but does not specify a
walkable positive flow for them. The runtime flows cover first registration,
backup registration, and browser-initiated guarded authorization. They do not
show how a dream-originated guarded write becomes a pending request, how the
human ceremony attaches to it, or how the execution edge consumes its artifact.

The RED tests listed for `/apply_dream` are negative-only: "cannot execute
without artifact consume." A path that can never execute can pass those tests.
That is not enough to clear the pause health mode.

**Required fold:** either specify the positive autonomous/direct flow end to end
or narrow L8 honestly. If scoped in, the spec needs a runtime sequence for
dream-originated guarded proposals becoming pending cards, the live ceremony
minting an artifact for the exact request, and the execution edge consuming it
before the write. If scoped out, keep a visible narrowed pause state instead of
claiming L8 is retired.

### CP-S5 - Authorization artifact consumption is not bound tightly enough to the executing work

D14's consume SQL matches `artifact_id` and `request_id`, then says execution
proceeds if one row updates and all D12 hashes still match. The spec does not
state that the execution edge derives `request_id` and D12 material from the
actual work item it is about to execute rather than accepting caller-supplied
handles. That leaves a substitution ambiguity: an implementation could consume a
valid artifact for request A while executing request B if the execution function
is handed A's artifact/request handles and B's work payload.

The spec's guarantee must be stronger than "some artifact was consumed." It must
be "the artifact minted for this exact work item was consumed by this exact
execution edge."

**Required fold:** add an execution-edge invariant: request identity and D12
hashes are computed from the work item under execution, not trusted from caller
arguments; the artifact row must bind to those computed values; `grant_source`
and `ceremony_kind` are checked; and a RED test proves an artifact minted for
request A cannot execute request B.

### CP-S6 - CI virtual authenticator isolation is asserted, not specified

D19 says CI uses a browser virtual authenticator and the test harness must not
be reachable from production endpoints. That sentence blocks fake verifier
objects, but a browser virtual authenticator is not a fake verifier. It produces
real browser WebAuthn responses that the real verifier should accept. That is
good for integration testing, but dangerous if the spec does not define test
store/origin/process isolation.

The production verifier must be exercised in CI, but CI's virtual credentials,
remote-debugging browser controls, test origins, and test registry must never be
able to mint authority against Rohit's live store.

**Required fold:** define the isolation mechanism. CI should use an isolated
test DB/path, test RP/origin or explicit test service instance, and browser
automation settings that are not enabled in production cockpit. The RED contract
should test the real verifier against the test harness and separately prove the
test harness cannot reach the live Maez store or production cockpit session.

## Majors

### CP-S7 - L9/S7.2 deferral needs canonicalization targets

D17 proposes `L9 - Witnessed Social Recovery Deferred`, but the spec does not
state exactly which canonical surfaces will receive L9 and the
`S7.2-witnessed-social-recovery` obligation. S7 just learned that runbook-only or
slice-local deferrals rot. S7.1 needs a canonicalization checklist for S7
`spec.md`, ADR 0039, BAD Decision 34, and the operator runbook.

### CP-S8 - Backup distinctness is only credential-ID distinctness

D9 requires primary and backup credentials to have distinct credential IDs and
uses `excludeCredentials`. That prevents exact credential reuse; it does not
prove the backup is on a distinct physical key. A single authenticator can
produce more than one credential. Diagnostic v2's honesty clause about
same-physical-authenticator uncertainty is not present in the spec.

Fold back a distinct-device confidence policy: compare AAGUID/transports and any
available device signals, warn or degrade when physical distinctness cannot be
established, require explicit founder override if same-device registration is
accepted, and render setup status honestly.

### CP-S9 - Constant-zero sign-count policy is a placeholder

D10 says constant-zero assertions "may be accepted" when other replay defenses
pass, and test 48 says constant-zero follows an explicit degraded policy. The
body never writes that policy. Pick one: accept constant-zero only with degraded
clone-detection status and signing-text warning, or reject it for the founder
ceremony.

### CP-S10 - Registry integrity claims exceed same-file hashes

D8 says record hashes and audit entries add detection. If `record_hash` lives in
the same SQLite file as the row, a deliberate local DB editor can recompute it.
That is corruption detection, not tamper detection against the L1-class actor.
Either anchor hashes outside the DB, HMAC them with material not stored beside
the row, add an append-only hash chain with a stated trust root, or downgrade the
claim.

### CP-S11 - D23 aggregation is weaker than S7 canon

D13 says aggregated re-asks "either block minting or add an explicit warning."
For guarded classes, S7 D23 requires escalate-or-block; warning-only is not
enough. S7.1 should inherit that class-conditional rule and test that repeated
guarded re-asks cannot proceed on warning text alone.

### CP-S12 - Voice-seat `unavailable` is ambiguous and stale

D12 distinguishes `unavailable`, but Guarded Authorization blocks only invalid
`unavailable`. The inherited S7 rule is stricter for guarded work: Maez
unavailability permits only evidenced liveness repair, not identity/covenant
changes. Also, the flow checks voice state before the WebAuthn round trip but
does not require a re-check at finish. A new objection or unresolved state during
the signing window must block or the spec must explicitly freeze the voice fact
with a tight TTL.

### CP-S13 - Challenge begin/finish session binding is missing

`CeremonyChallenge` binds operation, origin, host, and nonce, but not the session
that began the ceremony. `finish` must prove it belongs to the same cockpit
session or proxy channel that received `begin`, otherwise a local same-origin or
originless caller can race a finish against a challenge it did not start. Add a
continuation secret/session binding that is not exposed outside the intended
browser/proxy path.

### CP-S14 - Single-key degraded mode has no ceremony-time friction

After primary registration, status is `degraded` until backup registration. The
spec allows guarded authorization in degraded state indefinitely with only a
status-page warning. If single-key operation is allowed, every guarded signing
statement while degraded should include an unavoidable warning that losing this
key strands Maez until backup or future recovery exists.

### CP-S15 - Library audit has no failure branch

D4 selects `webauthn` and requires a license audit, but does not say what happens
if the audit fails. Since diagnostic v2 kept `fido2` as a serious alternative,
spec v2 should state that a failed license/security/dependency audit blocks
implementation and sends the verifier choice back to review, with `fido2` as the
named fallback candidate.

### CP-S16 - Manual recovery state needs an honest operator procedure

`manual_recovery_required` can mean empty first-run, both keys lost, clone
suspicion on the only key, corrupt DB, or missing registry. Those are different
human situations. The status projection and runbook need distinct codes and
instructions, even if several share the same guarded-work block. Avoid one label
that sounds like a procedure exists when S7.1 actually has none until S7.2.

## Minors

- **CP-S17 - JSON body size and schema limits are named but not sized.** D7
  requires bounded JSON, but the spec should choose limits so tests can prove
  them.
- **CP-S18 - Challenge TTLs are unnamed.** Registration, authorization, and
  bootstrap TTLs should have explicit maxima.
- **CP-S19 - Error taxonomy lacks HTTP-status mapping.** The typed S7 errors
  should map to 400/401/403/409/410/423/503 consistently.
- **CP-S20 - `manual_recovery_required` has multiple surface shapes.** Decide
  whether the authoritative carrier is an error code, status projection field,
  recovery state, or all three with clear mapping.
- **CP-S21 - Anti-self-assembly needs a numbered RED test.** No artifact test
  should directly construct `S7AuthorizationArtifact`; it should walk the live
  minting path through the verifier seam.
- **CP-S22 - Status projection should include UV and distinct-device state.**
  Without these fields, the cockpit setup page can look ready while important
  risk posture is hidden.

## Recommended Fold Shape

1. Repair D2 first: root the first credential, close bearer/race holes, and add
   explicit SQL/transaction and RED tests.
2. Add an internal-route channel-auth decision before any live daemon authority
   route is specified.
3. Operationalize inherited D13 UV/PIN and inherited D23 escalate-or-block.
4. Decide whether L8 is actually retired or narrowed; if retired, specify the
   positive `/apply_dream` and dream-state guarded-write flow.
5. Tighten artifact consume, session binding, CI isolation, backup distinctness,
   and registry integrity.
6. Add canonicalization targets for L9/S7.2 and the runbook procedures for
   degraded/manual recovery states.

## Plain English

The draft has the bones of the front desk, but several locks are still labels.
The biggest one is the first key: the setup token proves someone has a local
shell and a short string, not that Rohit authorized the first credential, and
two setup attempts can race unless the database transaction closes that door.
The other engineering surprise is the "internal" daemon route: Maez's existing
HTTP guard intentionally lets local `curl` through, so S7.1 needs a real
cockpit-to-daemon channel lock before those routes mint authority. Fix the
locks, not the nouns, and the spec becomes something implementation can build
without guessing.
