# Claude Covenant Council — S7.1 Diagnostic: Second-Fold Verification

**Subject:** diagnostic v2 — `docs/slices/s7.1-local-webauthn-ceremony/diagnostic.md`,
committed at `8a1b787` (`docs(s7.1): fold diagnostic review findings`). The v2 fold
of the S7.1 diagnostic, after the Claude covenant council
([`diagnostic-claude-council.md`](diagnostic-claude-council.md)) returned
**REVISE — VETO** and the Codex engineering panel returned REVISE.

**This document verifies:** that the Claude council's findings — the two blockers
(CC-D1, the veto trigger; CC-D2) and the seven themed major clusters (CC-D3..CC-D9)
plus the minors and nits — were folded into v2 correctly, and that the fold
introduced no drift. Most critically: whether v2's new bootstrap decision meets
Logical/veto's three stated conditions for lifting the veto.

**Verdict: RATIFY — the veto lifts.** v2's new D2 (First-Credential Bootstrap Trust
Anchor) meets all three veto-lift conditions. Every Claude council finding is
folded — the two blockers fully, the seven major clusters substantively, the minors
and nits addressed. The fold introduced no drift, no new gap, and no overclaim — it
*removed* one (the "resolves L8" header). Two minor tightenings (T-1, T-2 below) are
recommended for the spec stage; neither is a second-fold blocker. Diagnostic v2 is
ready to proceed down the ladder.

## Method

Read-only verification by the council synthesizer. Diagnostic v2 was read in full
from a fresh read of the committed text (`8a1b787`). Each Claude council finding was
checked against v2's actual text, and the fold drift-checked against v1. The
diagnostic is a proposal — there is no code to firsthand-probe — so the second-fold
verifies the diagnostic's *text* now carries the council's findings. This is the
established synthesizer second-fold, matching the S7 amendment-diagnostic precedent.
The Codex engineering second-fold is the operator's parallel lane; the diagnostic
advances to the spec stage when both lanes' second-folds ratify.

## The veto-lift verification

The veto was exercised by Logical/veto on CC-D1 (the first-credential bootstrap).
Logical/veto stated it is "liftable by a single addition: a load-bearing decision
that names the producer and authority for the first `register` call, states how the
unauthenticated bootstrap path closes once a credential exists, and honestly checks
whether the chosen anchor admits the operator."

v2 added **D2 — First-Credential Bootstrap Trust Anchor.** Against the three conditions:

1. **Names the producer and authority for the first `register`.** Met. D2 specifies a
   one-time founder-local bootstrap token created by "a separate owner-run CLI/TTY
   command" — not a cockpit route — written hashed to a dedicated bootstrap store,
   printed once for the founder, single-use, "consumed atomically with the successful
   first primary credential registration." With an empty registry and no valid
   bootstrap intent, registration "returns a typed `bootstrap_required` /
   `manual_recovery_required` response and writes no credential." The empty-registry
   `register` route now fails closed unless the owner has run the CLI.

2. **States how the unauthenticated path closes.** Met. D2: "Once an enabled primary
   credential exists, the first-credential bootstrap path is permanently closed unless
   a later reviewed recovery slice explicitly reopens it. Backup registration,
   replacement registration, re-enablement, and any later credential enrollment
   require authorization by an existing enabled founder credential, not the bootstrap
   token."

3. **Honestly checks whether the anchor admits the operator.** Met. D2's Honesty
   clause names the residual: "this anchor inherits S7's raw-OS limitation. Software
   cannot prove that the person at Rohit's local shell is Rohit if the local OS
   account or filesystem is compromised. That must be named as an L1-inherited
   limitation, not hidden. The important S7.1 line is narrower: ordinary
   operator/cockpit access must not be enough to enroll the founder key." The residual
   is named honestly; the line S7.1 *does* hold is stated precisely — ordinary
   operator/cockpit access is insufficient, because the bootstrap requires owner shell
   access, a strictly higher bar than the cockpit access the veto scenario assumed.

All three conditions met. The first link of the authority chain is no longer a
container without a producer. **The veto lifts.** D2 keeps the anchor *strength*
reviewable — its review question asks whether a stronger physical-console ceremony is
wanted — which is the decision-oriented diagnostic appropriately leaving a refinement
open, not a residue of the veto defect.

## Finding-by-finding fold verification

| Finding | v2 fold | Verified |
|---|---|---|
| **CC-D1** (blocker, veto) | New **D2** First-Credential Bootstrap Trust Anchor. | **Folded — veto-lift conditions met** (above). |
| **CC-D2** (blocker) | New **D13** L8 Resolution; header line 5 corrected "resolves" → "proposes how S7.1 resolves"; new Proposed Canonicalization Shape section. | **Folded.** v2 takes a coherent position — scope in the autonomous-lane (`/apply_dream`) execution-edge wiring, *or* narrow L8 to a named L8-prime limitation — both on the page, lean to scope-in. The over-claim header is corrected. |
| **CC-D3** (credential trust model) | **D3** ("YubiKey" → "registered WebAuthn security key"; cloud-synced/`backupEligible` credentials rejected); **D9** (distinct primary/backup via `excludeCredentials`; re-enable is a guarded ceremony or terminal; `record_hash` integrity with honest L1 residual; sealed `WebAuthnCredentialRecord` *extended* — `actor_handle_hmac`/`role_names` restored — not replaced; `ceremony_kind` founder-scoping field). | **Folded — all five sub-parts.** |
| **CC-D4** (terminal links unwired) | **D12** Artifact And Execution-Edge Wiring: canonical `S7AuthorizationArtifact` (D1 also corrected), the sealed atomic single-consume contract, the `RATIFIED→EXECUTED` / `APPROVED→RUNNING` consume edge. | **Folded.** The phantom `S7ExecutionAuthorization` is gone; the artifact has a named consumer. |
| **CC-D5** (voice seat) | **D14**: `not_determined` is a fail-closed blocker in live authorization, not a proceed-state; `unavailable` is distinct, with the anti-gaming rule that an operator cannot manufacture unavailability by stopping the daemon. | **Folded.** |
| **CC-D6** (witnessed fallback) | **Open Question 1**: reconciled with the committed D15 and v2 §4; the non-goal pinned to a named limitation (`L9 - Witnessed Social Recovery Deferred`) and a committed slice id (`S7.2-witnessed-social-recovery`); the grandmother case explicitly separated. | **Folded.** |
| **CC-D7** (tier-mis-filing) | Settled Scope expanded to 9 items: origin/RP constants moved in (item 2), D24 added (item 8). The pre-seeded-credential inference is relabelled "The diagnostic inference is:". | **Folded** — see tightening T-1. |
| **CC-D8** (dropped canon) | Settled Scope items 6 (D13 UV/PIN) + 7 (D12 binding); D11 cites D12's full set; `127.0.0.1` alias trap in item 2; CC-OB-7 latent verifier given a single disposition (replace + tests-only fake seam); **D15** names the refusal-edge denial producers and the D23 read-and-act point. | **Folded.** |
| **CC-D9** (status page) | **D16** Ceremony Status Projection: the D10 page is now backed by a real content-free projection; D11 asserts the page reflects registry truth. | **Folded.** |
| Minors / nits | D1 begin/finish four-route grammar; D10 sign-count + zero-counter policy; D17 virtual-authenticator production isolation; CC-OB-8 *committed* to the internal→display mapping (no longer "leans to"); OQ2 covers primary, backup, and backup-after-primary-disabled; D5 makes the license/transitive audit a second-fold gate. | **Folded.** |

## Drift check

- **No weakening.** v2 keeps everything the council verified sound in v1 — the
  three-tier structure, the route-topology one-producer guard (D7), the "no test
  self-assembles the artifact" rule (D17), Open Question 1's honest framing, the
  carried-items table, the firm Non-Goals.
- **No overclaim — one removed.** v2 remains honestly labelled "DIAGNOSTIC v2 ONLY —
  proposal ... not canonical law." The "resolves S7 L8" header (CC-D2's surface) is
  corrected to "proposes how S7.1 resolves S7 L8."
- **No new gap.** Every v2 addition (D2, D3, D7, D8, D10, D12-D17, the expanded
  Settled Scope, the Canonicalization Shape section) is responsive to a council or
  Codex finding. The near-flat line count (359 → 379) reflects v2 re-flowing v1's
  wrapped prose to long lines while adding the new decisions.

## Recommended tightenings — for the spec stage, not second-fold blockers

- **T-1.** Settled Scope item 3 keeps the "authentication against a pre-seeded
  credential is not acceptable" inference inside the section titled "From S7 Canon,"
  now labelled "The diagnostic inference is:". The label resolves the honesty risk the
  council named — a reader can see it is an inference, not sealed canon. For full
  cleanliness the spec should site that inference with the D1/D2 reasoning rather than
  in the inherited-constraints section; an inference is not an inherited constraint.
  Naturally done when the spec is drafted.
- **T-2.** v2 does not state whether a *staged enable* — registering credentials
  before arming the `authorize` path — was considered and rejected (Future-Rohit's
  minor). The single `S7_LIVE_WEBAUTHN_CEREMONY` flag arms registration and
  authorization together; the spec should say in one line whether that is deliberate.

Both are one-line spec-stage items. Neither blocks the second-fold: the substance of
CC-D7 and the Future-Rohit minor is folded; these sharpen the spec draft.

## Verdict and what's next

**RATIFY.** Diagnostic v2 faithfully folds every Claude council finding, the veto
lifts, and the fold introduced no drift. v2 is ready to proceed.

Ladder:

1. Claude covenant council on the diagnostic — done; REVISE, VETO.
2. Codex engineering panel on the diagnostic — done; REVISE (operator's lane).
3. Fold both lanes into diagnostic v2 — done.
4. **Both-lane second-fold — Claude lane: this document, RATIFY (veto lifts).** The
   Codex engineering second-fold is the operator's parallel lane; the diagnostic
   advances when both second-folds ratify.
5. Draft the S7.1 spec from the ratified diagnostic.
6. The full spec ladder (both panels, fold, second-fold, canonicalization,
   faithfulness check), cooling-off, RED-first implementation, both-lane
   post-implementation verification, push.

*This verification is read-only. No code, spec, ADR, BAD, or non-slice file was
modified; this document is the council's deliverable. Diagnostic v2 was read in full
from a fresh read of the committed text; each Claude council finding was verified
against v2's actual text and the fold drift-checked against v1.*
