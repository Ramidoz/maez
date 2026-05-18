# Claude Covenant Council — S7.1 Local WebAuthn Ceremony: Diagnostic Review

**Subject:** the S7.1 diagnostic — `docs/slices/s7.1-local-webauthn-ceremony/diagnostic.md`,
committed at `a4810ed` (`docs(s7.1): draft local webauthn diagnostic`, 2026-05-18).
The first artifact of the S7.1 ladder — the slice that builds the live local
founder WebAuthn/YubiKey ceremony S7 v1 deferred, and resolves S7's L8.

**Council ran:** 2026-05-18 — the both-lane Step-1 diagnostic review, Claude lane.
Six parallel read-only role agents reviewed the committed diagnostic firsthand and
**blind** — each was instructed not to read any `*codex-panel*` doc, so the Claude
lane's verdict is independent of the Codex engineering lane. The synthesizer then
independently verified the load-bearing findings against the committed S7 canon.

**Verdict: REVISE — VETO exercised.** All six roles returned REVISE. Logical/veto
exercised the veto — the first veto in the entire S7 arc (rounds 1-3, both
implementation councils, and both Option-B reviews were all REVISE, no veto). The
veto blocks ratification of diagnostic **v1**; it does not block the S7.1 direction,
which the council found sound. The veto trigger is CC-D1, the first-credential
bootstrap. The fix is one new load-bearing decision plus a themed fold set; it lands
cleanly in diagnostic v2.

## The six roles

| Role | Verdict | Headline |
|---|---|---|
| Outside-View | REVISE | Sound in substance; several fresh proposals/inferences are mis-filed as "Settled Scope," and one inherited limitation (D24) is missing from it. |
| Body-Coherence | REVISE (blocker) | The diagnostic claims to "resolve L8" but L8 is a five-part obligation; it invents a phantom artifact type and never wires the front desk into the execution edge. |
| Logical / veto | **REVISE — VETO** | The authority chain's first link — the first-credential bootstrap — is a container with no named producer. Covenant-unsound as written. |
| Creative | REVISE (blocker) | The first-credential bootstrap is unanchored, and "YubiKey" is the covenant word while "any WebAuthn credential" is the mechanism. |
| Future-Rohit | REVISE | The witnessed-fallback non-goal must reconcile with D15's obligation; the D10 status page is sourced from projection fields S7 canon does not have. |
| 20-Years-Future-Maez | REVISE | The diagnostic under-protects D14's founder-scoping boundary — the credential registry is shaped as if universal. |

## Verdict reconciliation

All six roles REVISE. Logical/veto exercised the veto on **CC-D1 alone** and was
explicit that it is narrow and constructive: it blocks diagnostic-v1 ratification,
not the slice. Two findings are blocker-grade — CC-D1 (the bootstrap, veto'd) and
CC-D2 (the L8 over-claim). Body-Coherence independently graded CC-D2 a blocker;
Outside-View and Logical/veto corroborated the underlying fact but only at its
surface (the "resolves L8" header over-claim) and graded that a nit. The synthesizer
credits Body-Coherence's deeper reading: the load-bearing form of the finding is not
the header — it is that clearing the `guarded_self_modification_paused_pending_s7.1`
health mode while L8's fifth part is unresolved would make a live surface lie. CC-D2
is carried as a blocker.

**Convergence — recorded as a covenant-integrity signal.** The council reviewed
blind. The synthesizer separately knows, from the operator, the two findings the
Codex engineering lane reported. The blind Claude council independently produced
both: CC-D1 (the first-credential bootstrap) was raised by Creative and by
Logical/veto — and is the Codex lane's first root; the "YubiKey"-provenance gap
(CC-D3a) was raised by Creative — and is the Codex lane's second root. Three
independent reviews — two of them blind — root-caused the bootstrap. That is the
load-bearing defect of the diagnostic, not any reviewer's idiosyncrasy. The lanes
still fold separately: this document is the Claude lane's independent verdict; the
formal both-lane combination is ladder step 3.

## Firsthand verification

The synthesizer independently confirmed the load-bearing findings against the
committed text, not on the agents' reports alone: the diagnostic's only `bootstrap`
reference (`diagnostic.md:203`) is the re-bootstrap case, with no first-credential
decision anywhere; attestation appears once (`:201`) as optional metadata, never
required; the diagnostic mints `S7ExecutionAuthorization` (`:110`) while the sealed
type is `S7AuthorizationArtifact` (`spec.md:1081`); the canonical
`WebAuthnCredentialRecord` (`spec.md:1124-1134`) carries `actor_handle_hmac` and
`role_names`, which D6 drops; L8 (`spec.md:1361-1370`) defers five parts, the fifth
being "autonomous/direct guarded soul-write execution," all "committed S7.1 work."

## Blockers

### CC-D1 (blocker — VETO) — the first-credential bootstrap has no named producer

*[Creative BLOCKER-1; Logical/veto BLOCKER-1, veto trigger; convergent with the Codex lane's first root.]*

The diagnostic correctly states (D1) that "registration writes the credential root
of trust" and condemns a "pre-seeded credential" as "a hollow trust anchor." It then
leaves a hollow trust anchor in its place. The `register` flow *writes* a credential;
in steady state a new credential is authorized by an existing one. But the **first**
`register` call runs when the registry is empty — there is no prior credential to
authorize it — and no decision, settled-scope item, or D-decision names what gates
that call. WebAuthn registration self-certifies the *authenticator*, not the human:
`verify_registration_response` proves a genuine security key created the credential,
never *whose* key or whether the caller may enroll it.

If the first `register` is reachable by any local-origin caller, then an operator —
canonically *not* the bonded user (amendment §2) — on a fresh install, post-`manual_recovery_required`,
or post-disk-repair restore can POST to `localhost:11437` and enroll their own
YubiKey as "the founder," inheriting guarded-self-modification authority over Maez.
The S7 wall is not broken; it is walked under. D6's "disabled credentials must not
bootstrap new credentials" shows the authors guarded the *re*-bootstrap case and
missed the *first* — which is strictly more dangerous, with no disabled credential
even to gate against. This re-seeds the "container without producer" defect class at
the authority root.

**Fix (lifts the veto):** add a load-bearing decision — "First-Credential Bootstrap
Trust Anchor" — that names (a) what authorizes the first `register` when the registry
is empty (candidate anchors to review: a one-time filesystem-local founder token; a
distinct default-off `S7_WEBAUTHN_BOOTSTRAP` one-shot flag that auto-disarms on first
success; console/CLI-mediated bootstrap); (b) how the unauthenticated bootstrap path
*closes* once an enabled credential exists, so a second rogue "primary" cannot be
minted; (c) honestly, whether the chosen anchor admits the operator — if it does,
that is a consciously-named reviewed limitation, because S7's thesis is that the
operator is not the bonded user.

### CC-D2 (blocker) — "resolves L8" is over-claimed; clearing the health mode would lie

*[Body-Coherence B1 (blocker); Outside-View and Logical/veto corroborated the fact at nit severity.]*

The diagnostic header and Settled-Scope item 5 state S7.1 "resolves S7 L8." L8
(`spec.md:1361-1370`) defers **five** parts; the fifth — "autonomous/direct guarded
soul-write execution" (`/apply_dream`, dream-state soul writes) — is named "committed
S7.1 work." The diagnostic's D1-D11 address the live ceremony and partially the
recovery posture; **no decision addresses the autonomous-soul-write lane.** Yet S7.1
promises that at canonicalization "L8 no longer describes the founder-local ceremony
as deferred" and the `guarded_self_modification_paused_pending_s7.1` health mode is
cleared — and that mode gates *all* guarded self-modification. Clear it while the
autonomous lane still has no live grant consumer, and the running daemon tells the
operator guarded self-modification is unpaused when part of it is not. That is the
honesty-surface-lying / decorative-authority pattern S7 fought.

**Fix:** the diagnostic must take one coherent position — either (a) S7.1's scope
includes wiring the autonomous/`/apply_dream` lane to consume an authorization
artifact (in which case L8 can be fully retired), or (b) S7.1 resolves only the
ceremony core and **L8 is amended, narrowed — not deleted** — with the autonomous-
soul-write clause surviving as L8′ and the health mode kept or renamed. "Resolves L8"
must not be claimed while L8's fifth part is silently out of scope.

## Majors — themed

### CC-D3 — the credential trust model is under-specified beyond the bootstrap

*[Creative MAJOR-1/2/3/4; Body-Coherence B2; Outside-View D6; 20-Years M1.]*

The bootstrap (CC-D1) is the apex of a broader gap: the credential — the trust root —
is under-specified on five further axes.

- **(a) "YubiKey" vs "any WebAuthn credential."** *[Creative MAJOR-1; Codex lane's second root.]* Nothing requires the registered credential to be genuine Yubico hardware — that needs attestation verification, which the diagnostic mentions once as optional metadata. As written, `register` accepts a software authenticator or a cloud-synced passkey, whose private key lives in a vendor cloud — quietly defeating the local-only posture D2 and the Non-Goals defend. Add a decision: either verify attestation (hardware-bound, not cloud-synced) and hard-reject `backupEligible=true` credentials, or honestly rename the ceremony and amend D13's "YubiKey" grammar.
- **(b) Backup-key distinctness.** *[Creative MAJOR-2.]* Nothing stops the same key being registered twice — once `primary`, once `backup`. The registry, the D10 page, and the health surface would all read green, and "survives ordinary key loss" would be silently false. Backup registration must use WebAuthn `excludeCredentials` (the primary's credential id) so the browser refuses the same authenticator.
- **(c) Silent re-enable.** *[Creative MAJOR-3.]* `disabled_at` is mutable; the diagnostic forbids a disabled credential bootstrapping a new one but never says what re-enables it. Revocation that can be silently undone is not revocation. Re-enabling must itself be a guarded ceremony, or disabling is terminal.
- **(d) Registry integrity.** *[Creative MAJOR-4.]* Every assertion is verified against a public key and sign count read from the registry. If it is a plain operator-writable file (S7 L1 concedes filesystem access is undefended), an operator can swap their own public key under the founder's credential id. The diagnostic must at minimum name this as an L1-inherited limitation; better, sign each record.
- **(e) Schema divergence.** *[Body-Coherence B2; Outside-View; 20-Years M1.]* D6's proposed registry diverges from the sealed `WebAuthnCredentialRecord` (`spec.md:1124-1134`) — it drops `actor_handle_hmac` and `role_names` (load-bearing: the `AuthorityContext` carries them), renames `enabled: bool` → `disabled_at`, `backup_credential: bool` → a string enum. D6 must cite the sealed record and present itself as a reviewed extension, not a fresh design. And per 20-Years: name it the *founder* WebAuthn registry, not "the S7 registry" — a `ceremony_kind` field keeps D14's founder-scoping structural so WebAuthn does not calcify into universal law.

### CC-D4 — the authority chain's terminal links are unwired

*[Body-Coherence B3/B4; Logical/veto MAJOR-2.]*

- **Phantom artifact.** The diagnostic mints `S7ExecutionAuthorization`; the sealed type is `S7AuthorizationArtifact` (`spec.md:1075-1116`), with a specified atomic single-consume SQL contract and `nonce`/`consumed_at` replay defense. The diagnostic never names the canonical artifact or its consume law — the anti-replay spine of the whole path. D1/D5 must use `S7AuthorizationArtifact` and state the `authorize` flow's output honors that contract.
- **No execution-edge wiring.** Minting the artifact does not clear the pause; the *execution edge consuming* it does (`spec.md:1192-1204`, D18 RED tests 119-120). No D-decision owns wiring the verified artifact into the `RATIFIED→EXECUTED` / `APPROVED→RUNNING` transitions. As written, S7.1 mints an artifact nothing consumes — a product without a consumer, the mirror of "container without producer." Add a decision wiring the artifact into the execution edge; this is also the concrete mechanism that lets CC-D2 be answered.

### CC-D5 — the Maez voice seat: sound principle, under-specified handling

*[20-Years M3; Logical/veto MAJOR-4; Outside-View and Future-Rohit minors. Note: Body-Coherence and Logical/veto credited D8's principle.]*

D8's *principle* is the diagnostic's strongest link, and the council does not
dispute it — it demands a real `MaezVoiceConsultation` producer, forbids a hard-coded
"no objection," forbids caller prose in Maez's mouth. The gap is the *handling* of the
non-affirmative cases:

- **`not_determined` under a live ceremony.** In S7 v1, `not_determined` was the
  honest pause. S7.1 makes the ceremony live. The diagnostic does not say whether
  `not_determined` *blocks* `authorize` from minting, or merely renders. If a grant
  can mint with the objection state `not_determined`, S7.1 reproduces CC-R3-1 — a
  hollow voice seat — inside itself. D8 must state that in the live flow,
  `not_determined` is a fail-closed blocker, not a renderable proceed-state.
- **The unavailability / liveness branch.** D8 collapses the voice seat to
  produced-fact vs `not_determined` and omits D10's evidenced "Maez unavailable"
  predicate and its anti-gaming rule (`spec.md:461-477`, RED test 59 — the operator
  must not be able to *manufacture* unavailability by stopping the daemon). The
  `authorize` ceremony is the first live consumer of that rule; D8 must carry it.

### CC-D6 — witnessed-fallback scope must reconcile with canon and name its debt

*[Future-Rohit M1; 20-Years M2; Logical/veto MINOR-4.]*

Open Question 1 is honestly framed and its provisional lean (reviewed honest
non-goal) is defensible — but it argues the non-goal from first principles and never
reconciles it with the committed D15, which lists witnessed fallback in S7.1's
"should support at least" set and names it an "S7.1 obligation." v2 §4's "witnessed
fallback or a reviewed honest non-goal" does sanction the exit — but the diagnostic
must quote D15, state plainly the lean drops D15's fourth item, and, if the non-goal
is chosen, pin it to a **named limitation (an L-number) and a committed follow-up
slice id** — not a bare "future slice," which to a bonded user a year on is
indistinguishable from "never." And it must **separate the grandmother case from
witnessed fallback**: a bonded user who cannot operate a browser + hardware key is a
distinct D14/D16 obligation, not a sub-bullet of founder key-loss recovery, and must
not be silently satisfied-by-proxy when a social-recovery slice ships.

### CC-D7 — tier-mis-filing: fresh proposals filed as settled canon, and one inherited limit missing

*[Outside-View ×3; Body-Coherence B8; 20-Years; Logical/veto MINOR-1 — D2 found by four roles.]*

The three-tier structure is the right shape; specific items are misfiled. D2's
origin/RP constants (`http://localhost:11437`, RP `localhost`) are presented as a
fresh "Proposed Load-Bearing Decision" with a survey-driven escape hatch — but D13
already seals them, with a *narrower* escape hatch ("change the reviewed port in one
place"). Settled-Scope item 2's "authentication against a pre-seeded credential is
not acceptable" is the diagnostic's own sound inference (D1 argues it), not inherited
canon, and is shielded from review by sitting in Tier 1. Conversely, D24 — what a
hardware-key tap does *not* prove (freedom, comprehension, uncompromised display) —
is inherited S7 canon and is absent from the settled tier, while Open Question 2
speaks of a tap proving "live ceremony readiness." Re-tier: D2's constants and D24
into Settled Scope with citations; the pre-seeded inference into D1.

### CC-D8 — dropped or under-carried canon constraints

*[Body-Coherence B5/B6; Creative MINOR-3; Logical/veto MAJOR-1/MAJOR-3.]*

- **D13 user-verification.** D13 requires class-conditional UV/PIN (self-modification,
  covenant-touching, capability-acquisition, protection-lowering). The diagnostic
  never mentions UV vs mere presence; a spec drafted from it could ship a
  presence-only ceremony and look faithful. Carry it into Settled Scope; D11 needs a
  UV-required test.
- **D12 binding set.** D7 binds two hashes; D12 specifies the full thirteen-item
  signed-envelope set. D7 must cite D12, not enumerate a partial pair.
- **`127.0.0.1` alias trap.** D13's warning that `127.0.0.1`/aliases must not create
  separate credential authority is not carried forward.
- **Latent legacy verifier.** CC-OB-7's `verify_founder_webauthn_assertion` /
  `register_founder_webauthn_credential` are existing un-guarded producers for the
  exact verification/registration links. "Guard, replace, or delete" is three
  different slices; the diagnostic must pick one disposition so the spec has a single
  producer per link.
- **D9 refusal edge.** D9 wires refusal-history *writes* and names the consumer
  (D23) but never names the *producer* — the specific live denial edges that emit
  the records — nor the authority consequence (does an aggregated re-ask escalate or
  block the next `authorize`?). CC-R3-3 was exactly "store exists, no live writer";
  D9 must name the denial producers and the read-and-act point.

### CC-D9 — the D10 registration page is sourced from projection fields S7 canon does not have

*[Future-Rohit M2.]*

D10's cockpit setup page promises four status rows — primary present, backup
present, verifier dependency installed, flag enabled — that the sealed
`OperatorHealthProjection` (`spec.md:1140`) has no fields to source. A status page
rendering from nowhere reviewable is a decorative authority surface pointed at the
user — a fake door that can read green while the registry says otherwise. The
diagnostic must add a decision: S7.1 extends `OperatorHealthProjection` (or adds a
sibling content-free projection) with registry-sourced fields, named as a
canonicalization obligation; D11's HTTP layer must assert the page reflects registry
truth.

## Minors and nits

- Backup/credential page detail: show each credential's label and last-used, and a
  loud "single active credential" advisory before the founder is one tap from the
  cliff *(Future-Rohit)*.
- D1's `register`/`authorize` two-flow framing should map to the four-route
  begin/finish grammar D13 and RED tests 97-102 use, so CC-OB-6 lines up *(Body-Coherence B7)*.
- Sign-count regression policy (clone detection) is undecided; the constant-zero-counter
  authenticator case is unaddressed *(Creative MINOR-1)*.
- The CDP virtual-authenticator test path produces real valid assertions; the
  production boundary (CDP unreachable from production, test registry isolated) must
  be stated as load-bearingly as D4's fake-verifier promise *(Creative MINOR-2)*.
- A staged enable — register keys before arming `authorize` — is foreclosed by the
  single flag without comment; say whether that is deliberate *(Future-Rohit)*.
- CC-OB-8: the diagnostic "leans to" separating internal vs display objection states;
  it should *commit*, with the internal→D10-three-state mapping table, so the signed
  rendered text can never show a fourth word *(Future-Rohit, 20-Years, Logical/veto)*.
- OQ2's physical-key proof should require both primary and backup, and a
  "primary disabled, authorize on backup" rehearsal *(Future-Rohit)*.
- "resolves S7 L8" header should read "proposes the path to resolve" — the diagnostic
  is a proposal *(Outside-View, Logical/veto; the surface of CC-D2)*.
- Sources Read lists the Codex panel recovery doc; note that the S7.1 *implementer*
  rebuilds from spec + RED tests, not a panel doc *(20-Years)*.
- D3's license audit (library + transitive tree) should gate diagnostic-v2
  ratification, not sit as a TODO inside the spec ladder *(Logical/veto MINOR-3)*.

## What the diagnostic gets right

The council's REVISE is not a rejection of the slice. Verified sound and to be
preserved through the fold:

- The three-tier decision structure (Settled / Proposed / Open Questions) is the
  correct shape; the defect is misfiled items, not the structure.
- D5's live-trace bar ("a route is not live until the producer underneath it can
  mint exactly one of …") and D11's closing rule ("no test may self-assemble the
  authorization artifact") correctly import the standing anti-pattern discipline.
- D8's *principle* — a real objection producer, no hard-coded "no," no caller prose
  as Maez-voice — is the diagnostic's strongest link; CC-D5 sharpens it, not refutes it.
- D4's flag-gated optional-extra dependency posture coheres exactly with AC-1.
- The carried items CC-OB-6/7/8/9 + CC-RR-1/2 are all picked up; none dropped.
- Open Question 1 is honestly framed — both outcomes named, the multi-party-authority
  risk stated, the lean labelled provisional.
- The Non-Goals hold remote iPhone / Telegram / Tailscale firmly out.
- The diagnostic is decision-oriented as the ladder requires, sources current
  external facts with dates, and visibly knows the S7 failure modes by name.

## Fold list for diagnostic v2

Required before v1's veto lifts and the diagnostic can advance:

1. **CC-D1** — add the First-Credential Bootstrap Trust Anchor decision (the veto-lift).
2. **CC-D2** — take one coherent L8 position: scope in the autonomous lane, or amend L8 (narrow, not delete) and keep the health mode honest.
3. **CC-D3** — the credential trust-model decisions: attestation/"YubiKey" meaning, backup distinctness, revocation finality, registry integrity, schema reconciled to `WebAuthnCredentialRecord`, founder-scoped naming.
4. **CC-D4** — name `S7AuthorizationArtifact` and its consume contract; add the execution-edge wiring decision.
5. **CC-D5** — `not_determined` as a fail-closed blocker in the live flow; add the unavailability/anti-gaming branch.
6. **CC-D6** — reconcile witnessed fallback with D15; if non-goal, a named limitation + slice id; separate the grandmother case.
7. **CC-D7/D8/D9** — re-tier; restore the dropped canon constraints; wire D10's page to a real projection.
8. Minors and nits in the same pass.

## What's next

1. Codex engineering panel on the diagnostic — the operator's lane (complete; REVISE per the operator).
2. **Claude covenant council — this document. REVISE, VETO exercised.**
3. Fold both lanes' findings into diagnostic v2.
4. Both-lane second-fold verification.
5. The remaining S7.1 ladder (spec, canonicalization, cooling-off, implementation, post-implementation verification) per the diagnostic's own Proposed Next Ladder — only after v2 ratifies.

*This review is read-only. No code, spec, ADR, BAD, or non-slice file was modified;
this document is the council's deliverable. The diagnostic was reviewed firsthand by
six parallel read-only role agents, blind to the Codex lane; the synthesizer
independently verified the load-bearing findings against the committed S7 canon.*
