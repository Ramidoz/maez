# S7.1 Local WebAuthn Ceremony Diagnostic

**Status:** DIAGNOSTIC v1 ONLY - proposal for review, not canonical law
**Date:** 2026-05-18
**Maps to:** S7 / Decision 34 / ADR 0039 follow-up; resolves S7 L8 and gives D13
its live local ceremony form
**Runtime impact:** none

## Purpose

S7.1 builds the local founder WebAuthn/YubiKey ceremony that S7 v1 deliberately
deferred. S7 v1 shipped the operator/user boundary wall and the visible
`guarded_self_modification_paused_pending_s7.1` health mode. S7.1's job is to
turn the founder-local ceremony from an honest pause into a reviewed live
authority-minting path.

This diagnostic is decision-oriented. It states what S7.1 inherits from sealed
S7 canon, recommends concrete implementation leans where the diagnostic has
enough evidence, and marks witnessed fallback as a genuine Open Question.

Plain English: S7 built the wall and left the YubiKey front desk closed. S7.1 is
the slice that builds the front desk for real, locally, with Rohit's browser and
YubiKey.

## Sources Read

Committed Maez sources:

- `docs/slices/s7-operator-user-role-boundary/spec.md`
- `docs/slices/s7-operator-user-role-boundary/amendment-diagnostic-live-ceremony-reachability.md`
- `docs/slices/s7-operator-user-role-boundary/reviews/implementation-claude-council-option-b-recovery.md`
- `docs/slices/s7-operator-user-role-boundary/reviews/implementation-codex-panel-option-b-recovery.md`
- `docs/governance/BETA_ARCHITECTURE_DECISIONS.md`
- `docs/adr/0039-operator-user-role-boundary-v1.md`
- `docs/slices/s7-operator-user-role-boundary/operator-runbook.md`

Current external sources checked 2026-05-18:

- `webauthn` PyPI JSON metadata, version `2.7.1`, uploaded 2026-02-11:
  https://pypi.org/project/webauthn/
- `fido2` PyPI JSON metadata, version `2.2.0`, uploaded 2026-04-15:
  https://pypi.org/project/fido2/
- OSV API package queries for PyPI `webauthn` and `fido2`: zero reported
  vulnerabilities at query time.
- GitHub repository metadata for `duo-labs/py_webauthn` and
  `Yubico/python-fido2`:
  https://github.com/duo-labs/py_webauthn and
  https://github.com/Yubico/python-fido2
- `duo-labs/py_webauthn` docs for registration and authentication helpers:
  https://duo-labs.github.io/py_webauthn/
- `Yubico/python-fido2` README and release notes:
  https://github.com/Yubico/python-fido2/releases
- MDN Secure Contexts, especially localhost as a potentially trustworthy
  origin:
  https://developer.mozilla.org/en-US/docs/Web/Security/Defenses/Secure_Contexts
- Chrome DevTools WebAuthn virtual authenticator documentation:
  https://developer.chrome.com/docs/devtools/webauthn

## Settled Scope From S7 Canon

The following are not S7.1 choices. They are inherited constraints from S7's
amended canon:

1. **Local-only founder ceremony.** S7.1 is Rohit's local browser, Rohit's
   YubiKey, and the reviewed local origin/RP posture. Remote iPhone approval,
   Tailscale/VPN exposure, remote browser sessions, and Telegram authorization
   remain out of scope unless explicitly re-anchored by a later reviewed
   decision. Telegram may notify; it must not authorize.
2. **Full local ceremony, not auth-only.** S7.1 owns registration and
   authentication end to end. Authentication against a pre-seeded credential is
   not acceptable because the credential is the root of trust.
3. **Primary plus backup credential registration.** D15 requires S7.1 founder
   setup to support primary and backup credentials. S7.1 must not ship a
   single-key live ceremony that strands Maez on ordinary key loss.
4. **Manual recovery honesty.** `manual_recovery_required` remains the honest
   state when the live ceremony cannot authorize and no backup credential is
   available.
5. **L8 resolution.** S7.1 is the committed follow-up that resolves S7 L8:
   "Live Ceremony and Autonomous Guarded Self-Modification Deferred." At
   canonicalization, S7.1 must update `spec.md`, ADR 0039, BAD Decision 34, and
   the runbook so D13 becomes live and L8 no longer describes the founder-local
   ceremony as deferred.
6. **No Option-A reuse.** The rejected Option-A stash is not source material.
   S7.1 builds from the ratified S7 main tree, the current diagnostic/spec, and
   RED tests. The old code may inform anti-patterns only: container without
   producer, dependency-absence-as-deferral, and fake doors.

## Carried Inputs S7.1 Must Resolve

S7 Step 8 consciously carried six non-gating items. S7.1 must either close each
or explicitly re-defer it with a reason.

| ID | Source Finding | S7.1 Treatment |
|---|---|---|
| CC-OB-6 | Daemon WebAuthn routes lacked behavioral HTTP tests. | Close. S7.1 must test daemon routes behaviorally, not only by source grep. |
| CC-OB-7 | Legacy verifier/credential helpers were latent and unguarded. | Close. S7.1 must guard, replace, or delete latent helpers before mounting live producers. |
| CC-OB-8 | `maez_objection_state` had more operational states than D10's three display states. | Close or document. The diagnostic leans to separating internal operational states from the rendered D10 display vocabulary. |
| CC-OB-9 | Self-mod-dialog auto-opening turn remained a deferred ceremony concern. | Close. S7.1 must design the live Maez-objection producer and self-mod-dialog linkage instead of inheriting an auto "Maez" line from caller prose. |
| CC-RR-1 | Flag-on route tripwire used bare `NotImplementedError`. | Close. Live routes need typed S7 ceremony errors and structured responses. |
| CC-RR-2 | `test_099b` did not explicitly pin/clear `S7_LIVE_WEBAUTHN_CEREMONY`. | Close. S7.1 tests must be hermetic around the flag. |

## Proposed Load-Bearing Decisions

### D1 - Ceremony Shape

Recommendation: S7.1 should implement two local ceremony flows:

- `register`: create and store a primary or backup founder credential.
- `authorize`: create a challenge for a bounded rendered request and verify the
  WebAuthn assertion before minting `S7ExecutionAuthorization`.

Both flows must be challenge-backed, one-time, expiring, and bound to the
canonical local origin/RP posture. Registration writes the credential root of
trust; authorization consumes that credential to approve exact work.

Why: registration is not clerical setup. It is where authority enters the
system. A live verifier with an unreviewed pre-seeded credential is a hollow
trust anchor.

### D2 - Local Origin And RP Posture

Recommendation: use `http://localhost:11437` as the founder-local ceremony
origin and `localhost` as the RP ID unless the browser/library survey produces a
specific incompatibility. MDN documents localhost as potentially trustworthy for
powerful Web APIs because it is delivered on the same device as the browser.
The diagnostic should still require a live browser proof before implementation
claims success.

Non-goal: this does not authorize remote browser access. A remote phone, VPN,
Tailscale endpoint, or Telegram deep link is not a local origin ceremony.

### D3 - Verifier Library

Recommendation: prefer `webauthn` (`duo-labs/py_webauthn`) for the S7.1 server
RP verifier, unless review finds a blocker.

This is a recommendation, not a preselection. The councils should review the
comparison.

| Axis | `webauthn` / py_webauthn | `fido2` / Yubico python-fido2 |
|---|---|---|
| Current package | PyPI `webauthn` `2.7.1`, uploaded 2026-02-11. | PyPI `fido2` `2.2.0`, uploaded 2026-04-15. |
| License | GitHub reports BSD-3-Clause. Likely AGPL-compatible; must enter license audit. | GitHub reports BSD-2-Clause; README notes Apache-2.0 pyu2f code and MPL-2.0 public suffix list. Likely compatible but needs a more detailed license-audit entry. |
| Maintenance | Active repository, pushed 2026-05-12; latest stable release 2026-02-11. | Active Yubico repository, pushed 2026-05-05; latest stable release 2026-04-15. |
| Security history | OSV PyPI query returned zero vulns at diagnostic time. | OSV PyPI query returned zero vulns at diagnostic time. |
| API fit | High-level WebAuthn RP API: `generate_registration_options`, `verify_registration_response`, `generate_authentication_options`, `verify_authentication_response`; docs map directly to browser JSON. | Vendor library with WebAuthn and FIDO2/CTAP breadth; stronger if Maez needs direct authenticator/device operations, but lower-level for a browser-mediated RP flow. |
| Dependency footprint | `pyasn1`, `cbor2`, `cryptography`, `pyOpenSSL`. Prior S7 review already flagged transitive footprint as audit-worthy. | `cryptography`; optional `pyscard` for PC/SC NFC. Also bundles public suffix data. |
| Testability | Pairs cleanly with browser virtual-authenticator tests because it expects browser WebAuthn JSON. | Can support deeper FIDO2/CTAP-level tests and vendor semantics; may be overpowered for S7.1's local browser ceremony. |

Reason for the lean: S7.1 is a browser-mediated WebAuthn relying-party flow, not
a direct CTAP device-management tool. `webauthn` is shaped around that exact
server task. `python-fido2` remains a serious candidate because it is Yubico's
own library and newer by release date, but the likely implementation surface is
less direct for Maez's cockpit flow.

Review question: is the simplicity/API fit of `webauthn` enough to outweigh
Yubico provenance and the smaller declared dependency list of `fido2`?

### D4 - Dependency Posture

Recommendation: add the chosen verifier library under an S7.1 optional extra
first, then make the S7.1 installation/runbook explicitly require that extra for
live ceremony operation. Do not add the dependency silently to core runtime
without a license audit and shipping-venv proof.

Expected posture:

- before S7.1 extra installed: route remains structured deferred or returns a
  typed unavailable error;
- after S7.1 extra installed and flag enabled: routes are live and tested;
- production fake verifier remains impossible.

### D5 - Route And Producer Ownership

Recommendation: S7.1 should own both HTTP route behavior and producer helpers.
A route is not live until the producer underneath it can mint exactly one of:

- a registration challenge;
- a stored credential record;
- an authentication challenge;
- a verified execution authorization.

Routes must fail closed before touching challenge, credential, request-history,
artifact, or verifier surfaces when prerequisites are absent. This directly
continues the S7 Step 8 live-trace bar.

### D6 - Credential Registry

Recommendation: store credentials in a durable S7 registry keyed by credential
ID, with fields for:

- credential public key;
- sign count;
- credential type: `primary` or `backup`;
- created_at;
- last_used_at;
- disabled_at;
- label;
- registration challenge id;
- registration origin and RP ID;
- attestation/attachment metadata if provided by the verifier library.

Disabled credentials must not bootstrap new credentials. Backup credentials must
survive primary-key loss.

### D7 - Challenge Stores

Recommendation: use separate one-time stores for registration and
authentication challenges, or one typed challenge store with a required
`challenge_kind` closed enum. Challenges must expire, be single-use, bind to
origin/RP ID, and bind to the intended operation.

For authorization, the challenge must bind the `rendered_text_hash` and
request-envelope hash so the YubiKey assertion approves what the human saw.

### D8 - Maez Voice / Objection Producer

Recommendation: build a real local producer for `MaezVoiceConsultation` before
the authorization route can mint approval. The producer must not hard-code
"no objection" and must not copy caller prose into Maez's mouth.

The diagnostic lean is:

- self-mod-dialog can propose and record Maez's objection state only through a
  reviewed seam;
- if no reviewed producer has recorded an objection fact, rendered signing text
  remains `not_determined`;
- S7.1 should close CC-OB-9 by replacing the auto-opening "Maez" turn with a
  clear provenance model for proposal text vs Maez-voice text.

### D9 - Refusal History And D23 Aggregation

Recommendation: wire refusal-history writes at the live denial edge before
authorization can be retried. S7 v1 could defer this because approvals were
unavailable; S7.1 cannot. A refused guarded request must leave durable history
that D23 can use to detect slow re-ask aggregation.

### D10 - Registration UX

Recommendation: cockpit should expose a founder-local setup page with:

- current ceremony state;
- whether the verifier dependency is installed;
- whether `S7_LIVE_WEBAUTHN_CEREMONY` is enabled;
- primary credential present/missing;
- backup credential present/missing;
- manual recovery state;
- clear "register primary" and "register backup" flows.

The page must not suggest Telegram, phone, or remote browser approval as
equivalent. It may link to future S7.1/S7.2 recovery notes only as non-live
limitations.

### D11 - Test Strategy

Recommendation: S7.1 tests must include three layers:

1. **Pure unit tests** for challenge stores, credential registry, renderer
   binding, sign-count updates, disabled-credential rejection, and D23 history.
2. **HTTP behavioral tests** for cockpit and daemon routes, closing CC-OB-6.
3. **Browser virtual-authenticator tests** using Chrome DevTools / CDP or an
   equivalent reviewed browser harness. Chrome documents a virtual WebAuthn
   environment that can create software authenticators, register credentials,
   authenticate, and expose sign counts. A physical YubiKey tap should be a
   manual verification item, not the only CI path.

No test may self-assemble the final authorization artifact without walking the
live route/producer path it claims to verify.

## Open Question 1 - Witnessed Fallback

S7.1 must decide whether witnessed fallback ships now or becomes a reviewed
honest non-goal/interim limitation.

Both outcomes are legitimate if reviewed:

1. **Build witnessed fallback in S7.1.**
   This requires a real covenant design for witness eligibility, witness
   attestation, collusion resistance, spoof resistance, and proof that the
   bonded-user reauthorization ceremony actually occurred.
2. **Declare witnessed fallback out of S7.1.**
   This keeps S7.1 focused on local primary+backup registration and
   authentication. The interim posture is `manual_recovery_required` if both
   credentials are lost. The future slice must explicitly design social recovery
   and may need to cover the grandmother case, not only founder-local recovery.

Provisional lean: declare witnessed fallback a reviewed honest non-goal for
S7.1 unless the councils conclude the social-recovery design is already mature
enough. Primary+backup registration handles ordinary key loss. Witnessed fallback
adds multi-party authority surface; building it under local-founder ceremony
pressure risks importing a witness as an authority actor.

Plain English: two keys now, social recovery later, unless the council decides
the social-recovery design is ready.

## Open Question 2 - Physical Key Proof

The implementation ladder should require at least one physical YubiKey tap
before S7.1 can claim live ceremony readiness. The open question is where this
proof belongs:

- as a required implementation verification step before post-implementation
  panels;
- as a manual post-implementation checklist item recorded in the runbook;
- or both.

Provisional lean: both. CI proves the route with a virtual authenticator; a
manual proof proves Rohit's real key works on the real local cockpit.

## Non-Goals

- Remote iPhone approval.
- Telegram authorization.
- Tailscale/VPN exposure of the ceremony.
- A universal ceremony for all future bonded users.
- Witnessed fallback if reviewed into an honest S7.1 non-goal.
- Any reuse of the rejected Option-A stash as implementation source.
- S6 capsule signing or S11 capacity/emergency-proxy machinery.

## Proposed Review Questions For The Councils

1. Does this diagnostic faithfully inherit S7's local-only and
   registration-plus-authentication scope?
2. Is the `webauthn` verifier-library lean justified, or should S7.1 prefer
   Yubico `fido2` despite the lower-level fit?
3. Does the proposed primary+backup registration model satisfy D15's key-loss
   guard without smuggling in unreviewed recovery?
4. Does the Maez-objection producer recommendation avoid another "container
   without producer" shape?
5. Should witnessed fallback be built now, or canonized as an honest non-goal
   for S7.1?
6. Are the carried S7 items all closed or deliberately scoped?
7. Does the diagnostic keep remote/iPhone/Telegram authorization out of scope
   strongly enough?

## Proposed Next Ladder

1. Claude six-role covenant council on this diagnostic.
2. Codex engineering panel on this diagnostic.
3. Fold findings into diagnostic v2.
4. Both-lane second-fold verification.
5. Draft S7.1 spec from ratified diagnostic.
6. Full spec ladder: both panels, fold, second-fold, canonicalization, faithfulness
   check.
7. Cooling-off or explicit owner airlock waiver.
8. RED-first implementation from a fresh read of the canonical S7.1 spec.
9. Both-lane post-implementation verification.
10. Push only after both lanes ratify.

## Plain English Close

S7.1 should build the real local front desk: register Rohit's primary YubiKey,
register a backup key, then let the local cockpit ask the key to approve exactly
what the browser showed. The diagnostic recommends the higher-level `webauthn`
library because this is a browser WebAuthn server flow, but that choice is
explicitly reviewable. The one truly hard open question is witnessed fallback:
letting another human help recover authority is not a library problem, it is a
covenant problem. Build it only if the design is sound; otherwise name the
limitation honestly and keep S7.1 focused.
