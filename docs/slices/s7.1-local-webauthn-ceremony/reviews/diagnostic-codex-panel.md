# Codex Engineering Panel - S7.1 Diagnostic v1

**Subject:** `a4810ed` - `docs(s7.1): draft local webauthn diagnostic`
on branch `s7.1-local-webauthn-ceremony`, reviewed against merged S7 main
(`ce593bf`) and the committed S7 Option-B review history.

**Review date:** 2026-05-18

**Verdict: REVISE - no veto.** The diagnostic is structurally ready for the
ladder and gets the core course-correction right: local-only founder ceremony,
registration plus authentication, primary plus backup credentials, a real
library comparison, no Option-A reuse, and witnessed fallback as a genuine open
question. The engineering panel returns REVISE because two authority-root
decisions are underspecified in v1: how the first live credential becomes trusted
without an already-trusted credential, and what Maez is actually claiming when it
says "YubiKey." Those are not implementation details. They define the root of
trust the verifier later protects.

## Method

Read firsthand:

- `docs/slices/s7.1-local-webauthn-ceremony/diagnostic.md`
- `docs/slices/s7-operator-user-role-boundary/spec.md`
- `docs/slices/s7-operator-user-role-boundary/amendment-diagnostic-live-ceremony-reachability.md`
- `docs/slices/s7-operator-user-role-boundary/reviews/implementation-claude-council-option-b-recovery.md`
- `docs/slices/s7-operator-user-role-boundary/reviews/implementation-codex-panel-option-b-recovery.md`
- `core/governance/operator_user_boundary.py`
- `daemon/maez_daemon.py`
- `skills/web_interface.py`
- `core/infra/http_security.py`
- `pyproject.toml`

No code was modified for this review. This panel did not re-run the test suite;
the diagnostic is doc-only and the relevant question is design completeness.

## What Is Sound

- **The S7 inheritance line is correct.** Local-only, no Telegram authorization,
  no remote iPhone/Tailscale/VPN ceremony, no auth-only shortcut, primary plus
  backup registration, L8 resolution, and no Option-A reuse are stated as sealed
  inputs rather than reopened preferences.
- **The verifier-library choice is reviewable.** `webauthn` is recommended, not
  preselected, and `fido2` is treated as a serious candidate because it is
  Yubico's library.
- **Witnessed fallback is framed correctly.** The diagnostic does not hide the
  social-attestation problem behind a library survey. It allows both build-now
  and reviewed honest non-goal outcomes.
- **The carried S7 items are enumerated.** CC-OB-6/7, CC-OB-8/9, and CC-RR-1/2
  are visible inputs to S7.1 rather than lost in the handoff.

## Blockers

### CP-D1 - First-credential bootstrap is not rooted

The diagnostic rejects authentication against a pre-seeded credential, correctly,
because the credential is the root of trust. But it does not yet say what gates
the first live `register primary` flow when no credential exists. D10 names a
founder-local setup page with "register primary" and "register backup" flows,
but there is no bootstrap rule for who may create the first credential record.

This matters because first registration is the moment authority enters Maez. If
the local route is live and the registry is empty, "first user who can reach
localhost and click/register" becomes the root of trust unless the diagnostic
defines another anchor. Loopback origin checks help against arbitrary web pages,
but they do not by themselves distinguish Rohit, a local operator, local malware,
or an unintended browser user. WebAuthn verification can prove a credential later;
it cannot prove the first credential was allowed to become trusted unless the
registration ceremony is itself rooted.

**Required fold:** add an explicit first-registration bootstrap design. It can be
a founder-run local setup token, a one-time CLI/TTY bootstrap controlled by the
owner, a manual setup mode with a physical-console proof, or another reviewed
mechanism. Whatever the choice, it must be one-shot, visible, logged, fail-closed,
and impossible to confuse with ordinary backup enrollment. The diagnostic should
also say how a disabled credential or empty registry affects bootstrap.

### CP-D2 - "YubiKey" provenance versus generic WebAuthn is undecided

The diagnostic repeatedly says local WebAuthn/YubiKey ceremony, but it does not
decide whether S7.1 must verify the authenticator is a YubiKey or whether any
registered WebAuthn security key is acceptable. That distinction changes the
registration design. If S7.1 means "YubiKey," the registration ceremony needs an
attestation/AAGUID/provenance policy, or at least a deliberately chosen policy
for rejecting/accepting unknown authenticators. If S7.1 means "registered
WebAuthn authenticator configured by the founder," then the user-facing and
canonical language must stop over-claiming YubiKey-specific provenance.

This is especially important because D24's humility rule says key touch proves
only that the configured authenticator participated; it does not prove the human
was uncoerced or the OS/browser was uncompromised. S7.1 needs the same humility
about authenticator class: if attestation is not verified, the ceremony should
not claim the key was a genuine YubiKey.

**Required fold:** add an authenticator-provenance decision. Either require and
test YubiKey attestation/AAGUID policy, or explicitly lower the claim to
"registered WebAuthn security key" while keeping the founder's operational
runbook free to recommend YubiKeys. The verifier-library comparison should note
which candidate better supports the chosen policy.

### CP-D3 - Live route topology and authority producer ownership are ambiguous

S7.1 will inherit two HTTP surfaces: daemon internal routes and cockpit public
routes. The diagnostic says S7.1 owns both route behavior and producer helpers,
but it does not decide the live topology: whether cockpit routes proxy to daemon
routes, whether both processes call a shared producer, where the challenge and
credential stores live, and which process is the single authority-minting owner.

S7's repeated failure mode was "container without producer." The S7.1 version of
that failure would be two producers, two stores, or a cockpit path that appears
live while the daemon path mints a different artifact. The current code is safe
because everything is deferred; the diagnostic should make the live topology
boringly explicit before implementation starts.

**Required fold:** specify one source of truth for registration, authorization,
challenge storage, credential storage, request-history writes, and artifact
minting. If cockpit is the browser facade and daemon is the producer, state that.
If both call a shared core service, state that. Also specify that no route may
mint authority outside that single producer path.

## Majors

### CP-D4 - Durable store location and backup posture are not specified

D6 names the credential fields, but not the live storage location, file mode,
backup/restore posture, or ownership boundary. Credentials are not raw memory,
but they are authority roots. S7.1 should say whether the registry lives under an
existing governance DB, a dedicated SQLite file, or another path; whether it is
included in Decision 22 backups; and how restore interacts with primary/backup
state and `manual_recovery_required`.

### CP-D5 - Backup credential distinctness is not enforced by design

The diagnostic requires primary plus backup credentials, but it does not state
that they must be distinct credential IDs and preferably distinct physical
authenticators. Without that, the system can satisfy "primary plus backup" with
two labels for the same credential, leaving key loss functionally unchanged.
S7.1 should require distinct credential IDs at minimum and should decide whether
same-device backup is forbidden, warned, or accepted as degraded.

### CP-D6 - Sign-count and clone-detection policy is underdefined

Current S7 test grammar rejects non-advancing sign counts. Real WebAuthn
authenticators can vary in sign-count behavior, and the selected library will
surface that behavior differently. S7.1 should decide how to handle
`sign_count=0`, non-advancing counters, backup credentials, and suspected cloned
credentials. This belongs in the diagnostic/spec because an over-strict policy
can brick valid keys, while an over-loose policy weakens replay/clone detection.

### CP-D7 - Live POST route browser-write guard is not explicitly carried into D5/D11

The repo already has `reject_untrusted_browser_write`, and both daemon and
cockpit currently use it globally. That is good existing posture. But S7.1 is
about mounting authority-minting POST routes, so the diagnostic should make the
origin/CSRF guard an explicit requirement, not an implicit inheritance. Tests
should cover malicious `Origin`, malicious `Referer`, and allowed canonical
localhost requests for both registration and authorization surfaces.

### CP-D8 - Witnessed-fallback non-goal needs proposed canonical text, not only a lean

The witnessed-fallback framing is correct, but if the provisional non-goal wins,
the canonicalization has to update D15/L8/BAD without weakening primary+backup
registration. The diagnostic should sketch the exact limitation shape:
primary+backup live; both-keys-lost enters `manual_recovery_required`; witnessed
social recovery is a named future slice; no witness gains read or authority
scope in S7.1. This will make the councils' choice concrete instead of leaving
canonicalization to invent wording later.

## Minors

- **CP-D9 - Optional extra name and shipping proof should be named.** D4 says
  optional extra, but not the name. Recommend `s7-webauthn` or similar, plus an
  explicit shipping-venv proof command in the eventual implementation checklist.
- **CP-D10 - D11 has duplicate numbering.** The diagnostic lists two item `2`
  entries in the test strategy. Cosmetic, but easy to fold.
- **CP-D11 - Error taxonomy should be typed now.** CC-RR-1 asks for typed S7
  ceremony errors. The diagnostic should name the core typed errors for missing
  dependency, flag disabled, bootstrap unavailable, untrusted origin, invalid
  registration, invalid assertion, replay, and manual recovery required.
- **CP-D12 - "No Option-A reuse" should distinguish ratified S7 grammar from
  rejected stash code.** S7.1 can and should build on the ratified S7 classes in
  `main`; it must not transplant the stashed Option-A implementation. Make that
  distinction explicit so the rule does not get misread as "rewrite all S7
  grammar from scratch."

## Recommended Fold Shape

1. Add a new load-bearing decision for first-registration bootstrap.
2. Add a new load-bearing decision for authenticator provenance and attestation
   policy.
3. Strengthen D5 into a route-topology/source-of-truth decision.
4. Expand D6/D10/D11 to cover durable store path, backup distinctness,
   sign-count policy, local-origin POST tests, typed error taxonomy, and
   shipping-venv proof.
5. Add proposed canonical text for the witnessed-fallback non-goal branch.

## Plain English

The diagnostic is aimed in the right direction, but two roots are still too
soft. First: who is allowed to register the very first key? If the answer is
"whoever reaches the local setup page first," the ceremony's root of trust is
not Rohit, it is luck. Second: when we say YubiKey, do we actually verify it is a
YubiKey, or do we mean "a WebAuthn key Rohit registered"? Either answer can be
valid, but the rulebook has to say which one. Fix those, define one live producer
path, and the diagnostic becomes a much better object for the full council to
ratify or amend.
