# Codex Engineering Panel - S7.1 Diagnostic v2 Second-Fold

**Subject:** diagnostic v2 committed at `8a1b787`
(`docs(s7.1): fold diagnostic review findings`), reviewed against the Codex
engineering panel v1 findings in
[`diagnostic-codex-panel.md`](diagnostic-codex-panel.md) and the current S7.1
diagnostic text.

**Review date:** 2026-05-18

**Verdict: RATIFY.** The v2 fold resolves the engineering panel's blockers and
majors. The authority-root defects in v1 are no longer unowned: first
registration has a named bootstrap trust anchor, "YubiKey" provenance is made
honest and reviewable, route topology has one producer/owner, and the artifact
has a named execution-edge consumer. Two details should be tightened in the spec
draft, but neither blocks diagnostic ratification.

## Method

Read firsthand:

- `docs/slices/s7.1-local-webauthn-ceremony/diagnostic.md`
- `docs/slices/s7.1-local-webauthn-ceremony/reviews/diagnostic-codex-panel.md`
- `docs/slices/s7.1-local-webauthn-ceremony/reviews/diagnostic-claude-council.md`
- `docs/slices/s7.1-local-webauthn-ceremony/reviews/diagnostic-claude-council-second-fold.md`

This is a diagnostic text verification. No implementation code changed in
`8a1b787`; no test suite run is probative for this step. The relevant check is
whether v2 carries the required design decisions forward without drift.

## Fold Verification

| Codex finding | v2 fold | Status |
|---|---|---|
| **CP-D1** - First-credential bootstrap not rooted | New **D2 - First-Credential Bootstrap Trust Anchor**: owner-run CLI/TTY token, hashed at rest, single-use, expires, atomically consumed with first primary registration; empty registry without token fails closed; later enrollment requires an existing credential. | **Folded.** The root-of-trust producer is named and the closure condition is explicit. |
| **CP-D2** - "YubiKey" provenance undecided | New **D3 - Authenticator Provenance And Naming** lowers the hard claim to "founder-registered WebAuthn security key," stores attestation/device metadata when available, rejects or degrades platform/cloud-synced credentials when signals exist, and leaves vendor-attested YubiKey-only as a future tightening. | **Folded.** The diagnostic no longer overclaims YubiKey provenance. |
| **CP-D3** - Route topology / producer ownership ambiguous | New **D7 - Route Topology And Single Authority Producer** assigns cockpit as browser facade, daemon as live producer/store owner, and a shared core ceremony service as the only authority-writing path. | **Folded.** One facade, one producer, one store set, one artifact path. |
| **CP-D4** - Durable store and backup posture missing | **D9** defines the founder-scoped registry, sealed fields plus S7.1 extensions, record hash/audit integrity, Decision 22 backup/restore inclusion, and honest L1 residual for raw filesystem tamper. | **Substantively folded.** Exact path and file permissions move to spec tightening T-1 below. |
| **CP-D5** - Backup distinctness not enforced | **D9** requires distinct primary/backup credential IDs and WebAuthn `excludeCredentials` for existing enabled credentials. | **Folded.** |
| **CP-D6** - Sign-count / clone policy underdefined | New **D10 - Sign Count And Clone Detection** defines advancing-counter fail-closed behavior, constant-zero handling, stored sign-count mode, and clone-suspicion health/degrade behavior. | **Folded.** |
| **CP-D7** - Browser-write guard implicit | New **D8 - Browser Write Guard And Error Taxonomy** requires malicious `Origin`/`Referer` rejection, canonical localhost allowance, no GET mutation, bounded JSON/schema validation, and typed S7 errors. | **Folded.** |
| **CP-D8** - Witnessed-fallback non-goal needed canonical shape | **Open Question 1** now quotes the D15/v2 authority, proposes `L9 - Witnessed Social Recovery Deferred`, names `S7.2-witnessed-social-recovery`, and keeps witnesses from gaining authority in S7.1. | **Folded.** |
| **CP-D9** - Optional extra name / shipping proof | **D6** names `s7-webauthn`, keeps verifier out of core runtime, and requires shipping-venv proof. | **Folded.** |
| **CP-D10** - Duplicate test-strategy numbering | **D17** has four distinct numbered test layers. | **Folded.** |
| **CP-D11** - Typed error taxonomy missing | **D8** names the core typed error vocabulary. | **Folded.** |
| **CP-D12** - No Option-A reuse might forbid ratified S7 grammar | Settled Scope item 9 explicitly allows building on ratified S7 classes on `main` while forbidding transplant of the rejected stash code. | **Folded.** |

## Additional Engineering Checks

- The v2 artifact chain uses the sealed `S7AuthorizationArtifact`, not the v1
  phantom `S7ExecutionAuthorization`.
- The L8 line is no longer a header overclaim: v2 says it proposes how S7.1
  resolves L8 and requires either execution-edge wiring or a narrowed surviving
  limitation.
- The Maez voice seat now fails closed on `not_determined` during live
  authorization and carries the unavailable/anti-gaming branch.
- The status page is backed by a real content-free projection rather than page
  guesses.
- The browser virtual-authenticator path is explicitly tests-only and must be
  unreachable from production endpoints.

## Spec-Stage Tightenings

- **T-C1 - Choose the concrete registry path and permissions.** D7/D9 now say the
  daemon owns durable stores and Decision 22 backs up the registry, which is
  enough for diagnostic ratification. The spec should choose the actual file path,
  owner/mode expectations, and restore behavior precisely.
- **T-C2 - State the flag staging policy.** v2 still leaves one flag,
  `S7_LIVE_WEBAUTHN_CEREMONY`, as the broad live-ceremony switch. The spec should
  say whether registration and authorization intentionally arm together, or
  whether setup uses a staged mode where registration can be live before guarded
  authorization.

These are spec precision items, not diagnostic blockers. They do not reopen the
veto or change the recommended S7.1 shape.

## Verdict

**RATIFY.** Diagnostic v2 carries the Codex engineering panel's findings
faithfully and adds the missing authority-root decisions. The diagnostic can move
to the S7.1 spec draft once both lanes' second-fold records are committed.

Plain English: v1 had a front desk with no rule for who gets to become the first
clerk. v2 adds that rule: a deliberate one-time setup token from the owner shell,
then the door locks. It also stops pretending every registered key is magically a
verified YubiKey. The remaining work is spec precision, not another diagnostic
hole.
