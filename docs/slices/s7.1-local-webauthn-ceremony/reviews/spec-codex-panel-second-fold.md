# Codex Engineering Panel - S7.1 Spec v2 Second-Fold

**Subject:** spec v2 committed at `690e765`
(`docs(s7.1): fold spec review findings`), reviewed against the Codex engineering
panel findings in [`spec-codex-panel.md`](spec-codex-panel.md) and the committed
S7.1 spec text.

**Review date:** 2026-05-18

**Verdict: RATIFY.** Spec v2 folds the Codex engineering panel's blockers,
majors, and load-bearing minors. The authority-root problem is no longer a named
promise without a lock: D2 narrows the first-bootstrap claim honestly and gives
the first-primary path a transaction-closed bootstrap; D6 gives daemon internal
authority routes a real channel boundary so local `curl` cannot become the back
door around cockpit. The rest of the panel's engineering gaps are either
specified directly or explicitly downgraded to the actual strength S7.1 can
support.

## Method

Read firsthand:

- `docs/slices/s7.1-local-webauthn-ceremony/spec.md`
- `docs/slices/s7.1-local-webauthn-ceremony/reviews/spec-codex-panel.md`
- `docs/slices/s7.1-local-webauthn-ceremony/reviews/spec-claude-council-second-fold.md`

This is a spec second-fold, not implementation verification. No runtime tests
are probative yet. The check is whether the spec now gives implementation a
clear, testable contract for every engineering finding raised against v1.

## Fold Verification

| Codex finding | v2 fold | Status |
|---|---|---|
| **CP-S1** - First-credential bootstrap not enforceable | D2 now states the enforceable claim narrowly: cockpit HTTP access alone and originless local daemon HTTP calls cannot enroll the first credential; it explicitly does not claim software can distinguish Rohit from an operator with Rohit's OS account. It adds TTY-only invocation, store-owner UID check, CSPRNG token, TTL cap, one live intent, conditional-rowcount consume SQL, same-transaction consume+insert, sibling invalidation, and `bootstrap_closed_at`. | **Folded.** The root is transaction-closed and the residual is honest L1, not hidden. |
| **CP-S2** - Daemon internal routes lack channel auth | D6 now requires an authenticated cockpit-to-daemon internal channel, rejects originless local `curl` with `s7_internal_channel_untrusted`, and states no implementation may claim CC-S1 closed while internal registration routes remain curl-able. D7 carries the same rule. RED 29-32 pin it. | **Folded.** Internal route topology is now a lock, not a label. |
| **CP-S3** - UV/PIN not operationalized | D9 adds UV fields, D11 sets `uv_required=True` for inherited guarded classes, D18 exposes `uv_policy_state`, and RED 62/65 require capability recording and presence-only rejection. | **Folded.** |
| **CP-S4** - L8 `/apply_dream` flow absent | D15 adds a positive autonomous/direct guarded-write flow and a Runtime Flow for Autonomous Guarded Write. RED 98-99 require execute-after-live-artifact-consume positive tests. | **Folded.** Negative-only tests are no longer enough. |
| **CP-S5** - Artifact consume not tied tightly enough to executing work | D14 requires the execution edge to derive request identity and D12 hashes from the work item under execution; consume SQL binds the D12 hashes, `grant_source`, and `ceremony_kind`; RED 80-82 cover substitution and scoping. | **Folded.** |
| **CP-S6** - CI virtual authenticator isolation asserted | D19 now specifies isolated test DB path, test app/origin/RP config, no production remote-debugging channel, no production fake verifier seam, and tests proving the harness cannot mint against the live store. | **Folded.** |
| **CP-S7** - L9 canonicalization targets missing | D17 names S7 `spec.md`, ADR 0039, BAD Decision 34, and the operator runbook; Implementation Order item 19 carries the canonicalization edit. | **Folded.** |
| **CP-S8** - Backup distinctness only credential-ID distinctness | D9 now records `distinct_device_confidence`, compares AAGUID/transports/attachment/device signals, keeps same-device override `degraded` not `ready`, and D16 says `ready` is not inferred from credential count. | **Folded.** |
| **CP-S9** - Constant-zero sign-count policy placeholder | D10 now accepts constant-zero only with explicit `sign_count_mode`, forces degraded clone-detection state, and adds signing-text warning; RED 76 covers it. | **Folded.** |
| **CP-S10** - Registry integrity overclaim | D8 downgrades same-file record hashes to accidental-corruption/schema-drift detection and says deliberate local tamper needs a future external root. RED 51 pins the downgrade. | **Folded.** |
| **CP-S11** - D23 aggregation weaker than S7 canon | D13 now requires guarded-class aggregated re-asks to escalate or block; warning-only is insufficient. RED 93 covers it. | **Folded.** |
| **CP-S12** - Voice-seat unavailable and stale value gap | D12 now blocks guarded work on `unavailable` except evidenced liveness repair and requires finish-time re-query/revalidation or a tight signed freeze TTL. RED 87/89 cover it. | **Folded.** |
| **CP-S13** - Challenge begin/finish session binding missing | D11 adds cockpit session / internal-channel continuation binding; `CeremonyChallenge` carries session and internal-channel binding hashes; RED 57/64 cover it. | **Folded.** |
| **CP-S14** - Single-key degraded mode lacks friction | D16 injects an unavoidable degraded warning into every guarded signing statement; RED 109 covers it. | **Folded.** |
| **CP-S15** - Verifier audit failure branch absent | D4 blocks implementation on license/security/dependency/API audit failure and returns the verifier choice to spec review, with `fido2` named as fallback. RED 23 covers it. | **Folded.** |
| **CP-S16** - Manual recovery state too broad | D16 adds `manual_recovery_cause` values and honest runbook instructions; D18 exposes `manual_recovery_cause`; RED 110-111 cover both-keys-lost versus first setup. | **Folded.** |
| **CP-S17-22** - Minors | D7 sets 64 KiB JSON limit and HTTP status map; D11 sets 10-minute registration / 5-minute authorization TTLs; RED 83 forbids artifact self-assembly; D18 adds UV, distinct-device, clone-detection, and internal-channel state. | **Folded.** |

## Additional Checks

- **RED numbering:** counted from committed v2: 115 tests, sequential 1-115, no
  gaps. Section counts: Bootstrap 17, Dependency/Flag 6, Origin/Internal Channel
  12, Credential Registry 16, Verifier/Registration 11, Authorization/Artifact
  21, Maez Voice/Refusal History 10, Execution Edge/L8 8, Status/Manual Proof 14.
- **Stale overclaim scan:** v2 no longer contains the v1 phrases
  `SPEC DRAFT v1`, `fully retired`, `block minting or add`, `block or warn`,
  `ordinary operator/cockpit access cannot`, `runs only from the local repo`, or
  `manual_recovery_required: true`.
- **Fold anchors found:** `cockpit HTTP access alone`, `s7_internal_channel_untrusted`,
  `NOT EXISTS`, `bootstrap_closed_at`, `uv_required`, `Positive autonomous/direct
  flow`, `grant_source = 'founder_webauthn'`, `ceremony_kind =
  'founder_local_webauthn'`, `isolated test service`, `distinct_device_confidence`,
  `counter_unavailable`, `manual_recovery_cause`, and `64 KiB` are all present in
  the committed spec.

## Carried Tightenings

The Claude second-fold names two canonicalization-stage tightenings. I concur
they are not engineering second-fold blockers:

- **T-1:** add one explicit D5 sentence at canonicalization that staged
  registration-before-authorization enablement was considered and rejected.
- **T-2:** ensure the runbook's "preserve evidence" wording does not treat the
  `0600` audit JSONL as tamper-proof evidence unless a future append-only or
  external-chain property is added.

Both are canonicalization polish against already-ratified substance, not v2 spec
holes.

## Verdict

**RATIFY.** The Codex engineering panel's v1 findings are folded. Spec v2 gives
implementation a testable contract for the first-bootstrap root, daemon internal
channel, UV/PIN, L8 execution edge, artifact consume, virtual-authenticator
isolation, backup distinctness, D23 aggregation, manual recovery, and
anti-self-assembly. The spec can advance once both second-fold records are
committed.

Plain English: the engineering locks are now named where implementation can
build them. The first key has a transaction lock, the daemon back office has a
channel lock, and the test contract now checks the places where a fake green
suite could otherwise assemble the ceremony for itself.
