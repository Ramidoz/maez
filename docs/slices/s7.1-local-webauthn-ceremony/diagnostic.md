# S7.1 Local WebAuthn Ceremony Diagnostic

**Status:** DIAGNOSTIC v2 ONLY - proposal for second-fold review, not canonical law
**Date:** 2026-05-18
**Maps to:** S7 / Decision 34 / ADR 0039 follow-up; proposes how S7.1 resolves S7 L8 and gives D13 its live local ceremony form
**Runtime impact:** none

## Purpose

S7.1 builds the local founder WebAuthn security-key ceremony that S7 v1 deliberately deferred. S7 v1 shipped the operator/user boundary wall and the visible `guarded_self_modification_paused_pending_s7.1` health mode. S7.1's job is to turn that honest pause into a reviewed live authority-minting path for the founder-local ceremony.

This diagnostic is decision-oriented. It states what S7.1 inherits from sealed S7 canon, recommends concrete implementation leans where the diagnostic has enough evidence, and marks witnessed fallback as a genuine Open Question.

Plain English: S7 built the wall and left the front desk closed. S7.1 is the slice that builds the local front desk for real: register Rohit's primary security key, register a backup key, and let the local cockpit ask the key to approve exactly what the browser showed.

## Sources Read

Committed Maez sources:

- `docs/slices/s7-operator-user-role-boundary/spec.md`
- `docs/slices/s7-operator-user-role-boundary/amendment-diagnostic-live-ceremony-reachability.md`
- `docs/slices/s7-operator-user-role-boundary/reviews/implementation-claude-council-option-b-recovery.md`
- `docs/slices/s7-operator-user-role-boundary/reviews/implementation-codex-panel-option-b-recovery.md`
- `docs/governance/BETA_ARCHITECTURE_DECISIONS.md`
- `docs/adr/0039-operator-user-role-boundary-v1.md`
- `docs/slices/s7-operator-user-role-boundary/operator-runbook.md`

Diagnostic v1 review inputs folded into v2:

- `docs/slices/s7.1-local-webauthn-ceremony/reviews/diagnostic-codex-panel.md`
- `docs/slices/s7.1-local-webauthn-ceremony/reviews/diagnostic-claude-council.md`

Current external sources checked 2026-05-18:

- `webauthn` PyPI JSON metadata, version `2.7.1`, uploaded 2026-02-11: https://pypi.org/project/webauthn/
- `fido2` PyPI JSON metadata, version `2.2.0`, uploaded 2026-04-15: https://pypi.org/project/fido2/
- OSV API package queries for PyPI `webauthn` and `fido2`: zero reported vulnerabilities at query time.
- GitHub repository metadata for `duo-labs/py_webauthn` and `Yubico/python-fido2`: https://github.com/duo-labs/py_webauthn and https://github.com/Yubico/python-fido2
- `duo-labs/py_webauthn` docs for registration and authentication helpers: https://duo-labs.github.io/py_webauthn/
- `Yubico/python-fido2` README and release notes: https://github.com/Yubico/python-fido2/releases
- MDN Secure Contexts, especially localhost as a potentially trustworthy origin: https://developer.mozilla.org/en-US/docs/Web/Security/Defenses/Secure_Contexts
- Chrome DevTools WebAuthn virtual authenticator documentation: https://developer.chrome.com/docs/devtools/webauthn

## Settled Scope From S7 Canon

The following are not S7.1 choices. They are inherited constraints from S7's amended canon:

1. **Local-only founder ceremony.** S7.1 is Rohit's local browser, Rohit's locally registered security key, and the reviewed local origin/RP posture. Remote iPhone approval, Tailscale/VPN exposure, remote browser sessions, and Telegram authorization remain out of scope unless explicitly re-anchored by a later reviewed decision. Telegram may notify; it must not authorize.
2. **D13 canonical origin and RP.** The local origin is `http://localhost:11437` and RP ID is `localhost`. `127.0.0.1`, host aliases, remote origins, and different ports must not create separate credential authority. A port change must be reviewed and changed in one place.
3. **Full local ceremony, not auth-only.** S7.1 owns registration and authentication end to end. The diagnostic inference is: authentication against a pre-seeded credential is not acceptable because the credential is the root of trust.
4. **Primary plus backup credential registration.** D15 requires S7.1 founder setup to support primary and backup credentials. S7.1 must not ship a single-key live ceremony that strands Maez on ordinary key loss.
5. **Manual recovery honesty.** `manual_recovery_required` remains the honest state when the live ceremony cannot authorize and no backup credential is available.
6. **D13 class-conditional user verification.** Self-modification, covenant-touching, capability acquisition, and protection-lowering work require class-conditional user verification/PIN where supported, not mere user presence.
7. **D12 what-you-see-is-what-you-sign binding.** Authorization challenges bind the full sealed D12 signed-envelope set, including rendered text, request envelope, action parameters, preconditions, authority context, voice-seat facts, origin/RP posture, nonce, expiration, and renderer version. A partial two-hash binding is not enough.
8. **D24 humility.** A key touch proves only that the configured authenticator participated in the reviewed ceremony. It does not prove freedom from coercion, comprehension, display integrity, or OS/browser integrity.
9. **No Option-A reuse.** The rejected Option-A stash is not source material. S7.1 may build on the ratified S7 classes already on `main`, but it must not transplant the rejected Option-A live-ceremony code. The old code may inform anti-patterns only: container without producer, dependency-absence-as-deferral, and fake doors.

## Carried Inputs S7.1 Must Resolve

S7 Step 8 consciously carried six non-gating items. S7.1 must either close each or explicitly re-defer it with a reason.

| ID | Source Finding | S7.1 Treatment |
|---|---|---|
| CC-OB-6 | Daemon WebAuthn routes lacked behavioral HTTP tests. | Close. S7.1 must test daemon routes behaviorally, not only by source grep. |
| CC-OB-7 | Legacy verifier/credential helpers were latent and unguarded. | Close by disposition. S7.1 must replace, delete, or quarantine them as tests-only before mounting live producers; the diagnostic lean is replacement with one production producer and a tests-only fake seam. |
| CC-OB-8 | `maez_objection_state` had more operational states than D10's three display states. | Close. S7.1 must define internal operational states and a closed mapping into the D10 display values: `present`, `absent`, `not_determined`. |
| CC-OB-9 | Self-mod-dialog auto-opening turn remained a deferred ceremony concern. | Close. S7.1 must design the live Maez-objection producer and self-mod-dialog linkage instead of inheriting an auto "Maez" line from caller prose. |
| CC-RR-1 | Flag-on route tripwire used bare `NotImplementedError`. | Close. Live routes need typed S7 ceremony errors and structured responses. |
| CC-RR-2 | `test_099b` did not explicitly pin/clear `S7_LIVE_WEBAUTHN_CEREMONY`. | Close. S7.1 tests must be hermetic around the flag. |

## Proposed Load-Bearing Decisions

### D1 - Ceremony Shape

Recommendation: S7.1 should implement two local ceremony flows, each split into begin/finish routes:

- `register`: create and store a primary or backup founder credential.
- `authorize`: create a challenge for a bounded rendered request and verify the WebAuthn assertion before minting a `S7AuthorizationArtifact`.

Both flows must be challenge-backed, one-time, expiring, and bound to the canonical local origin/RP posture. Registration writes the credential root of trust; authorization consumes that credential to approve exact work.

Why: registration is not clerical setup. It is where authority enters the system. A live verifier with an unreviewed pre-seeded credential is a hollow trust anchor.

### D2 - First-Credential Bootstrap Trust Anchor

Recommendation: S7.1 should use a one-time founder-local bootstrap token for the first primary credential only.

Proposed shape:

- A separate owner-run CLI/TTY command creates a bootstrap intent for `register_primary` only.
- The CLI writes only a hashed token, expiry, purpose, and audit record to a dedicated bootstrap store; it prints the raw token once for the founder to enter in the local cockpit.
- The token expires quickly, is single-use, and is consumed atomically with the successful first primary credential registration.
- Once an enabled primary credential exists, the first-credential bootstrap path is permanently closed unless a later reviewed recovery slice explicitly reopens it.
- Backup registration, replacement registration, re-enablement, and any later credential enrollment require authorization by an existing enabled founder credential, not the bootstrap token.
- If the registry is empty and no valid bootstrap intent exists, registration returns a typed `bootstrap_required` / `manual_recovery_required` response and writes no credential.
- If all credentials are disabled or missing after first setup, the system enters `manual_recovery_required`; disabled credentials do not authorize re-bootstrap.

Honesty clause: this anchor inherits S7's raw-OS limitation. Software cannot prove that the person at Rohit's local shell is Rohit if the local OS account or filesystem is compromised. That must be named as an L1-inherited limitation, not hidden. The important S7.1 line is narrower: ordinary operator/cockpit access must not be enough to enroll the founder key.

Review question: is a one-time local bootstrap token the right anchor, or should S7.1 require a stronger physical-console/manual setup ceremony before first registration?

### D3 - Authenticator Provenance And Naming

Recommendation: S7.1 should lower its hard claim from "YubiKey" to "founder-registered WebAuthn security key," while the runbook recommends YubiKey hardware operationally.

Reason: verifying a browser WebAuthn registration proves a credential was created by an authenticator. It does not by itself prove the authenticator is a genuine Yubico YubiKey unless S7.1 verifies attestation/AAGUID/provenance. Requiring full vendor attestation in S7.1 would add policy and supply-chain complexity that is not necessary for the founder-local ceremony if the canonical language is honest.

Proposed policy:

- The live ceremony accepts only cross-platform / roaming security-key style credentials when the selected library exposes that signal.
- S7.1 rejects or warns-and-degrades platform authenticators and cloud-synced/passkey-style credentials when `backupEligible` / `backedUp` / device-type signals are available.
- If the browser/library cannot expose enough provenance, the signed text and runbook must say "registered WebAuthn security key," not "verified YubiKey."
- The registry stores AAGUID, attestation format, authenticator attachment, backup eligibility, backed-up state, transports, and library provenance when available, but absence of vendor attestation is not represented as YubiKey proof.
- A future slice may tighten this to YubiKey-attested-only if the councils choose that burden.

This preserves D24 humility: the ceremony proves a configured authenticator participated, not that a specific vendor key, free human, clean display, or uncompromised OS existed.

### D4 - Local Origin And RP Posture

Recommendation: keep the sealed S7 constants: `http://localhost:11437` as the founder-local ceremony origin and `localhost` as the RP ID. MDN documents localhost as potentially trustworthy for powerful Web APIs because it is delivered on the same device as the browser. The implementation must still prove this in the live browser before readiness claims.

Non-goal: this does not authorize remote browser access. A remote phone, VPN, Tailscale endpoint, Telegram deep link, `127.0.0.1` alias, or alternate port is not a local origin ceremony.

### D5 - Verifier Library

Recommendation: prefer `webauthn` (`duo-labs/py_webauthn`) for the S7.1 server RP verifier, unless second-fold review finds a blocker.

This is a recommendation, not a preselection. The councils should review the comparison.

| Axis | `webauthn` / py_webauthn | `fido2` / Yubico python-fido2 |
|---|---|---|
| Current package | PyPI `webauthn` `2.7.1`, uploaded 2026-02-11. | PyPI `fido2` `2.2.0`, uploaded 2026-04-15. |
| License | GitHub reports BSD-3-Clause. Likely AGPL-compatible; must enter license audit with transitive dependencies. | GitHub reports BSD-2-Clause; README notes Apache-2.0 pyu2f code and MPL-2.0 public suffix list. Likely compatible but needs detailed license audit. |
| Maintenance | Active repository, pushed 2026-05-12; latest stable release 2026-02-11. | Active Yubico repository, pushed 2026-05-05; latest stable release 2026-04-15. |
| Security history | OSV PyPI query returned zero vulns at diagnostic time. | OSV PyPI query returned zero vulns at diagnostic time. |
| API fit | High-level WebAuthn RP API: `generate_registration_options`, `verify_registration_response`, `generate_authentication_options`, `verify_authentication_response`; docs map directly to browser JSON. | Vendor library with WebAuthn and FIDO2/CTAP breadth; stronger if Maez needs direct authenticator/device operations, but lower-level for a browser-mediated RP flow. |
| Dependency footprint | `pyasn1`, `cbor2`, `cryptography`, `pyOpenSSL`. Prior S7 review already flagged transitive footprint as audit-worthy. | `cryptography`; optional `pyscard` for PC/SC NFC. Also bundles public suffix data. |
| Testability | Pairs cleanly with browser virtual-authenticator tests because it expects browser WebAuthn JSON. | Can support deeper FIDO2/CTAP-level tests and vendor semantics; may be overpowered for S7.1's local browser ceremony. |
| Provenance policy fit | Good fit if S7.1 lowers claim to registered WebAuthn security key and stores exposed attestation/device metadata. Needs proof for exact metadata support before spec. | Stronger candidate if councils require Yubico-specific attestation or direct device semantics. |

Reason for the lean: S7.1 is a browser-mediated WebAuthn relying-party flow, not a direct CTAP device-management tool. `webauthn` is shaped around that server task. `python-fido2` remains a serious candidate because it is Yubico's own library and newer by release date, especially if reviewers require vendor-attested YubiKey-only registration.

License/transitive audit is not optional. Diagnostic v2 recommends that second-fold ratification include the chosen library's license posture as a reviewed item, not a TODO buried inside implementation.

### D6 - Dependency Posture

Recommendation: add the chosen verifier library under a named S7.1 optional extra, proposed as `s7-webauthn`, then make the S7.1 installation/runbook explicitly require that extra for live ceremony operation. Do not add the dependency silently to core runtime without a license audit and shipping-venv proof.

Expected posture:

- before S7.1 extra installed: route remains structured unavailable/deferred or returns a typed missing-dependency error;
- after S7.1 extra installed, bootstrap/credential prerequisites met, and flag enabled: routes are live and tested;
- production fake verifier remains impossible;
- verification includes the shipping Maez venv, not only a worktree-local test venv.

### D7 - Route Topology And Single Authority Producer

Recommendation: the daemon owns the live ceremony producer and durable stores; cockpit is the local browser facade.

Proposed topology:

- cockpit routes render/collect browser JSON and call the daemon's internal S7.1 routes;
- daemon routes call one shared core ceremony service;
- the core ceremony service is the only code path that writes registration challenges, authentication challenges, credential records, refusal-history rows, and `S7AuthorizationArtifact` records;
- no cockpit route mints authority directly;
- no daemon route bypasses the shared producer;
- all routes use typed S7 ceremony errors with structured responses.

This closes the S7 failure mode at the topology layer: one route facade, one producer, one store set, one artifact consumer.

### D8 - Browser Write Guard And Error Taxonomy

Recommendation: S7.1 makes the existing local-origin browser-write guard an explicit live-route requirement.

Required HTTP behavior:

- all register/authorize begin/finish routes reject malicious `Origin` and malicious `Referer` values;
- canonical `http://localhost:11437` browser requests are allowed;
- non-browser local daemon/proxy calls remain allowed only where deliberately routed;
- no GET request mutates ceremony state;
- JSON bodies have bounded size and schema validation before reaching the verifier.

Typed S7 ceremony error vocabulary should include at least: `s7_live_ceremony_disabled`, `s7_webauthn_dependency_missing`, `s7_bootstrap_required`, `s7_bootstrap_invalid`, `s7_untrusted_origin`, `s7_registration_invalid`, `s7_authentication_invalid`, `s7_challenge_replayed`, `s7_credential_disabled`, `s7_manual_recovery_required`, and `s7_voice_seat_unresolved`.

### D9 - Credential Registry

Recommendation: extend the sealed `WebAuthnCredentialRecord` rather than replacing it. The registry is founder-scoped and stores authority roots, not generic user accounts.

Minimum record fields:

- sealed S7 fields: `credential_ref`, `actor_handle_hmac`, `role_names`, `public_key`, `sign_count`, `rp_id`, `origin`, `created_at`, `backup_credential`, `enabled`;
- S7.1 extensions: `ceremony_kind="founder_local_webauthn"`, `credential_kind` (`primary` or `backup`), `label`, `last_used_at`, `disabled_at`, `registration_challenge_id`, `attestation_format`, `aaguid`, `authenticator_attachment`, `backup_eligible`, `backed_up`, `transports`, `library_name`, `library_version`, `record_hash`.

Rules:

- primary and backup must be distinct credential IDs;
- backup registration must use WebAuthn `excludeCredentials` for existing enabled credentials so the same authenticator cannot silently satisfy both roles;
- if the same physical authenticator cannot be detected by the browser/library, the UI must warn and the registry must remain honest about what was verified;
- disabling a credential is not silently reversible; re-enablement requires an existing enabled founder credential and a reviewed ceremony, or disabling is terminal for S7.1;
- disabled credentials cannot bootstrap new credentials;
- registry integrity is hash-checked and audit-logged, but raw filesystem tamper remains an L1-inherited limitation unless a future slice adds a stronger storage root;
- Decision 22 backup/restore must include the registry and must restore into honest `ready`, `degraded`, or `manual_recovery_required` states.

### D10 - Sign Count And Clone Detection

Recommendation: S7.1 should preserve monotonic sign-count protection when the authenticator provides a meaningful counter, but must define the zero/non-advancing case explicitly before implementation.

Proposed policy:

- if a credential has an advancing sign count, a non-advancing future assertion fails closed as `s7_challenge_replayed` / `s7_clone_suspected`;
- if the library reports a constant-zero or non-meaningful counter, the credential is accepted only if other replay defenses hold: one-time challenge consumption, credential ID match, origin/RP match, and request/artifact single-use;
- the registry records the observed sign-count mode per credential;
- clone suspicion disables the credential or moves ceremony health to degraded/manual recovery until reviewed.

Review question: should S7.1 reject constant-zero counters entirely for the founder ceremony, or accept them with degraded health and stronger one-time challenge reliance?

### D11 - Challenge Stores And D12 Binding

Recommendation: use separate one-time stores for registration and authentication challenges, or one typed challenge store with a required `challenge_kind` closed enum. Challenges must expire, be single-use, bind to origin/RP ID, and bind to the intended operation.

For authorization, the challenge must bind the full D12 signed-envelope set and the `RenderedRequestStatement` text hash so the security-key assertion approves what the human saw. D7's implementation spec must cite D12 rather than inventing a partial binding list.

### D12 - Artifact And Execution-Edge Wiring

Recommendation: the authorization flow outputs a sealed `S7AuthorizationArtifact`, not a new `S7ExecutionAuthorization` type.

Required chain:

1. request envelope is created and rendered;
2. Maez voice-seat facts are resolved or fail closed;
3. browser WebAuthn verifies an enabled founder credential against a one-time challenge;
4. daemon producer mints exactly one `S7AuthorizationArtifact` using the sealed atomic single-consume contract;
5. the execution edge consumes that artifact at the `RATIFIED -> EXECUTED` / `APPROVED -> RUNNING` transition;
6. guarded work cannot execute on a verified WebAuthn result alone without consuming the artifact.

This is also the concrete answer to L8: the health mode cannot clear until both the live ceremony producer and the guarded execution consumer exist.

### D13 - L8 Resolution And Autonomous Guarded Execution

Recommendation: S7.1 should scope in the minimal execution-edge wiring needed to retire L8 honestly.

S7 L8 defers more than the browser ceremony. It also defers autonomous/direct guarded soul-write execution (`/apply_dream`, dream-state soul writes). S7.1 should resolve L8 only if it wires those guarded paths to the same `S7AuthorizationArtifact` consume edge. An autonomous proposal may create a request/card, but execution waits for the founder-local ceremony unless a later reviewed slice creates a different authority mechanism.

If second-fold review decides that autonomous/direct guarded soul-write execution is too large for S7.1, then the diagnostic must narrow L8 instead of deleting it: D13 becomes live for human-present local authorization, while an L8-prime limitation keeps autonomous/direct guarded soul-write execution visibly paused and health remains honest.

Diagnostic lean: scope in the minimal consumer wiring now, because clearing `guarded_self_modification_paused_pending_s7.1` while `/apply_dream` remains inert would make the health surface lie.

### D14 - Maez Voice / Objection Producer

Recommendation: build a real local producer for `MaezVoiceConsultation` before the authorization route can mint approval. The producer must not hard-code "no objection" and must not copy caller prose into Maez's mouth.

Live-flow rules:

- `present` blocks or escalates according to the guarded-work policy;
- `absent` can only be produced by a reviewed Maez-voice producer that affirmatively found no objection;
- `not_determined` is a fail-closed blocker in S7.1 live authorization, not a proceed-state;
- `unavailable` is distinct from `not_determined` and must satisfy D10's evidenced unavailability predicate;
- an operator must not be able to manufacture unavailability by stopping the daemon or blocking the producer;
- internal operational states map to exactly three rendered D10 display values: `present`, `absent`, `not_determined`.

The diagnostic lean is:

- self-mod-dialog can propose and record Maez's objection state only through a reviewed seam;
- if no reviewed producer has recorded an objection fact, authorization does not mint;
- S7.1 should close CC-OB-9 by replacing the auto-opening "Maez" turn with a clear provenance model for proposal text vs Maez-voice text.

### D15 - Refusal History And D23 Aggregation

Recommendation: wire refusal-history writes at the live denial edge before authorization can be retried. S7 v1 could defer this because approvals were unavailable; S7.1 cannot.

Required producer/consumer points:

- denial producers include explicit founder denial, Maez objection, unresolved voice seat, invalid assertion, expired challenge, repeated challenge, and disabled credential;
- refusal history records content-free request identity, work class, rendered-text hash, requester/proposer identity, denial reason, and timestamp;
- D23 reads refusal history before minting the next authorization artifact for a related request;
- aggregated re-asks either block or escalate to an explicit warning in the signing text before a grant can mint.

A refused guarded request must leave durable history that D23 can use to detect slow re-ask aggregation.

### D16 - Ceremony Status Projection And Setup UX

Recommendation: cockpit should expose a founder-local setup page backed by a real content-free status projection, not ad hoc page guesses.

The projection should include:

- ceremony live/deferred/unavailable mode;
- chosen verifier dependency installed/missing and version;
- `S7_LIVE_WEBAUTHN_CEREMONY` enabled/disabled;
- bootstrap state: absent, issued, expired, consumed, closed;
- primary credential present/missing/disabled;
- backup credential present/missing/disabled;
- single-active-credential warning;
- manual recovery state;
- witnessed fallback available/unavailable/non-goal;
- last-used timestamps and labels, without raw private content.

The page must not suggest Telegram, phone, or remote browser approval as equivalent. It may link to future recovery notes only as non-live limitations. D11 tests should assert the page reflects registry truth.

### D17 - Test Strategy

Recommendation: S7.1 tests must include four layers:

1. **Pure unit tests** for bootstrap tokens, challenge stores, credential registry, renderer binding, sign-count updates, disabled-credential rejection, D23 history, and artifact consume semantics.
2. **HTTP behavioral tests** for cockpit and daemon routes, closing CC-OB-6, including malicious `Origin` / `Referer`, allowed canonical localhost, missing dependency, disabled flag, missing bootstrap, and bad JSON.
3. **Browser virtual-authenticator tests** using Chrome DevTools / CDP or an equivalent reviewed browser harness. Chrome documents a virtual WebAuthn environment that can create software authenticators, register credentials, authenticate, and expose sign counts. The test harness and fake/virtual authenticator must be impossible to reach from production endpoints.
4. **Manual physical-key proof** using Rohit's real local browser and real keys before readiness claims.

Manual proof should include: primary registration, backup registration, authorization with primary, primary disabled then authorization with backup, and both-keys-lost/manual-recovery posture. No test may self-assemble the final authorization artifact without walking the live route/producer/consumer path it claims to verify.

## Open Question 1 - Witnessed Fallback

S7.1 must decide whether witnessed fallback ships now or becomes a reviewed honest non-goal/interim limitation.

Committed D15 lists witnessed fallback in S7.1's obligation set; amendment v2 §4 explicitly permits "witnessed fallback or a reviewed honest non-goal." That means the non-goal is available, but it must be canonical, named, and tracked.

Both outcomes are legitimate if reviewed:

1. **Build witnessed fallback in S7.1.** This requires a real covenant design for witness eligibility, witness attestation, collusion resistance, spoof resistance, and proof that the bonded-user reauthorization ceremony actually occurred.
2. **Declare witnessed fallback out of S7.1.** This keeps S7.1 focused on local primary+backup registration and authentication. The interim posture is `manual_recovery_required` if both credentials are lost. Canonicalization adds a named limitation, proposed as `L9 - Witnessed Social Recovery Deferred`, and a committed follow-up slice id, proposed as `S7.2-witnessed-social-recovery`. No witness receives read authority or bonded-user authority in S7.1.

Provisional lean: declare witnessed fallback a reviewed honest non-goal for S7.1 unless the councils conclude the social-recovery design is already mature enough. Primary+backup registration handles ordinary key loss. Witnessed fallback adds multi-party authority surface; building it under local-founder ceremony pressure risks importing a witness as an authority actor.

Grandmother-case separation: witnessed fallback for the founder is not the general authorization mechanism for future bonded users who cannot operate a browser + hardware key. That is a separate D14/D16-shaped ceremony and must not be quietly satisfied by S7.1.

Plain English: two keys now, social recovery later, unless the council decides the social-recovery design is ready.

## Open Question 2 - Physical Key Proof

The implementation ladder should require at least one physical security-key tap before S7.1 can claim live ceremony readiness. The open question is whether this proof is a readiness gate, a runbook checklist item, or both.

Provisional lean: both. CI proves the route with a virtual authenticator; manual proof proves Rohit's real key works on the real local cockpit. The proof should cover primary, backup, and backup-after-primary-disabled.

## Non-Goals

- Remote iPhone approval.
- Telegram authorization.
- Tailscale/VPN exposure of the ceremony.
- A universal ceremony for all future bonded users.
- Vendor-attested YubiKey-only policy, if D3's generic security-key lean is ratified.
- Witnessed fallback if reviewed into an honest S7.1 non-goal.
- Any reuse of the rejected Option-A stash as implementation source.
- S6 capsule signing or S11 capacity/emergency-proxy machinery.

## Proposed Canonicalization Shape If v2 Ratifies

The eventual S7.1 spec/canon should propose:

- D13 live local founder WebAuthn security-key ceremony, with exact origin/RP constants and UV/PIN requirements.
- D15 updated to primary+backup live in S7.1, with witnessed fallback either built or named as `L9` / `S7.2-witnessed-social-recovery`.
- L8 retired only if the ceremony producer and guarded execution consumer, including autonomous/direct guarded soul-write paths, are wired; otherwise L8 is narrowed and renamed rather than deleted.
- BAD Decision 34 updated to say S7.1 resolves the local founder ceremony and does not decide remote/iPhone/Telegram or universal ceremonies.
- Operator runbook updated with bootstrap, registration, backup-key rehearsal, physical proof, and both-keys-lost manual-recovery instructions.

## Proposed Review Questions For The Councils

1. Does the v2 bootstrap trust anchor close the veto without pretending software can defeat raw OS compromise?
2. Is the lowered "registered WebAuthn security key" claim preferable to vendor-attested YubiKey-only registration for S7.1?
3. Is the `webauthn` verifier-library lean justified under the chosen provenance policy, or should S7.1 prefer Yubico `fido2`?
4. Does the route topology create exactly one live authority producer and one artifact consumer?
5. Does the L8 plan truly clear the health mode, or should S7.1 narrow L8 and keep part of the pause visible?
6. Does `not_determined` fail closed in the Maez voice seat strongly enough?
7. Should witnessed fallback be built now, or canonized as `L9` / `S7.2-witnessed-social-recovery`?
8. Are all carried S7 items closed or deliberately scoped?
9. Does the diagnostic keep remote/iPhone/Telegram authorization out of scope strongly enough?

## Proposed Next Ladder

1. Claude six-role second-fold verification on this diagnostic v2.
2. Codex engineering second-fold verification on this diagnostic v2.
3. Draft S7.1 spec from ratified diagnostic.
4. Full spec ladder: both panels, fold, second-fold, canonicalization, faithfulness check.
5. Cooling-off or explicit owner airlock waiver.
6. RED-first implementation from a fresh read of the canonical S7.1 spec.
7. Both-lane post-implementation verification.
8. Push only after both lanes ratify.

## Plain English Close

S7.1 still builds the local front desk, but v2 adds the missing lock on the first door. The first key cannot be whoever reaches the setup page first; it needs a deliberate one-time owner bootstrap. And the rulebook stops over-claiming: unless we verify Yubico attestation, this is a founder-registered WebAuthn security-key ceremony, with YubiKey recommended, not magically proven. The rest of the fold makes the live path one clean chain: setup token -> registered primary and backup keys -> exact signed request -> one authorization artifact -> one execution edge. If any link is missing, the health surface must keep saying the pause is real.
