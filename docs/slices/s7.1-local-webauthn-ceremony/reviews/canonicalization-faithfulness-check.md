# Claude Covenant Council — S7.1 Canonicalization: Faithfulness Check

**Subject:** the S7.1 canonicalization — commit `2c3287d`
("docs(s7.1): canonicalize local webauthn ceremony"), which moved the S7.1 spec
from draft to canonical and wrote the ratified S7.1 decisions into S7's canonical
surfaces.

**This document verifies:** that the canonicalization faithfully carries
ratified S7.1 spec v2 (`690e765`, RATIFIED by both-lane second-fold) into the
five canonical documents, and that it introduced no drift, no overclaim, and no
covenant regression — most critically, that L8 was canonicalized as a
*conditional* retirement plan and **not** as retired, and L9 as a *live*
limitation.

**Verdict: PASS.** The canonicalization is faithful. All five surfaces carry the
ratified spec correctly; L8 is honestly conditional and L9 honestly live across
every canon surface; both spec-stage tightenings (T-1, T-2) landed; the
cooling-off discipline is canonicalized with the owner-waiver condition named; no
S7 v1 decision was altered and no `BETA_ARCHITECTURE_DECISIONS` entry was
deleted. Two cosmetic terminology nits remain (a stale "witnessed fallback" at
S7 RED test 148 and at S7.1 spec line 878); neither is a faithfulness failure and
neither blocks the ladder.

## Method

Read-only verification by the council synthesizer. The canonicalization commit
`2c3287d` was read firsthand via `git show` — the full diff of all five changed
files — and each changed surface checked against ratified spec v2 and the Claude
council's findings. The commit's file stat was verified, and two firsthand grep
sweeps confirmed the stale-self-description and stale-terminology state. No
`*codex-panel*` file was read; this is the covenant lane's post-canonicalization
verification.

## Scope of the canonicalization (verified)

`git show --stat 2c3287d` confirms exactly five documents changed — 243
insertions, 115 deletions, all under `docs/`:

- `docs/slices/s7.1-local-webauthn-ceremony/spec.md` — status draft → canonical;
- `docs/slices/s7-operator-user-role-boundary/spec.md` — S7 canon;
- `docs/adr/0039-operator-user-role-boundary-v1.md`;
- `docs/governance/BETA_ARCHITECTURE_DECISIONS.md` — Decision 34;
- `docs/slices/s7-operator-user-role-boundary/operator-runbook.md`.

No code, no test, no non-doc file touched. The 115 deletions are all
replaced/edited lines; verified below that no document section and no BAD
decision entry was removed.

## The load-bearing check — L8 conditional, L9 live

Before canonicalization the covenant lane flagged one risk: the canon edit must
record L8 as *retirement ratified in plan, conditional on S7.1 implementation
passing post-implementation verification* — **not** as retired — because the
spec is ratified while S7.1 is not implemented; and L9 as a *live* limitation
from the moment S7.1 is canon. Verified across all four canon surfaces:

- **S7 `spec.md`** — the L8 limitation header (`### L8 - Live Ceremony and
  Autonomous Guarded Self-Modification Deferred`) is unchanged; the limitation
  stays active: "That plan is not implementation. L8 remains active until S7.1
  code is built, tested, and ratified by post-implementation verification." The
  pre-L8 narrative adds "The S7.1 ... spec is ratified as the plan ... It is not
  implemented by this canon update." A new `### L9` section is added.
- **ADR 0039** — Context: "That ratifies the plan ... it does not implement it.
  L8 therefore remains active until S7.1 implementation and post-implementation
  verification pass. L9 ... is live as soon as this amendment is canonicalized."
  The new-reviewed-decision list now also includes "treating L8 as retired
  before the guarded execution consumer is live" — a canon-level guard against
  the premature-retirement overclaim.
- **BAD Decision 34** — "The plan is not implementation. Until S7.1 code passes
  post-implementation verification, L8 remains active ..."; a new
  "**Witnessed social recovery deferred.**" limitation bullet carries L9.
- **Operator runbook** — the L8 limitation entry is updated to the conditional
  form; a new L9 entry is added.

`guarded_self_modification_paused_pending_s7.1` is stated on every surface to
remain until S7.1 *implementation and post-implementation verification* — not
until spec canonicalization. L9 is written as live canon, the witnessed-recovery
deferral being true the moment S7.1 is canon. The honesty bar is met on every
surface. This is the CC-S17 discipline — a proposal not framed as accomplished —
held at the canon layer, and ADR 0039 strengthens it by making premature L8
retirement itself a canon-protected line.

## Surface-by-surface verification

| Surface | Canonicalization | Verified |
|---|---|---|
| **S7.1 spec.md** | Status "SPEC DRAFT v2 ONLY" → "Canonical spec; implementation pending"; "Maps to" → "ratified live form of S7 D13 and conditional resolution plan for S7 L8"; D15 header "Proposed" → "Conditional" with "not effective until implementation and post-implementation verification"; L8/L9 limitations re-labelled "This spec plans" / "Canonical limitation"; T-1 added to D5; T-2 added to D16. | **Faithful** — the ratified artifact is now self-labelled canonical with implementation honestly pending; "Conditional" is more accurate than "Proposed" at the canonical stage. |
| **S7 spec.md** | L8 kept active as a conditional retirement; new `### L9` live limitation; D13 updated with the ratified S7.1 plan ("When implemented and verified, S7.1 mounts:"); narrative / health-state rule / post-implementation-effect line updated to "implementation and post-implementation verification"; T-1 added to D13; "witnessed fallback" → "witnessed social recovery" through the prose. | **Faithful** — no S7 v1 decision altered; only forward-references to S7.1 corrected to match the ratified S7.1 scope, and L9 added. |
| **ADR 0039** | Status amended 2026-05-18; Context paragraph (L8 conditional, L9 live); the requires-list carries the ratified S7.1 plan — first-credential bootstrap, authenticated internal channel, primary/backup registration, class-conditional UV, optional `s7-webauthn` dep; "does not yet" framing throughout; cooling-off named with the owner-waiver condition; "treating L8 as retired before the guarded execution consumer is live" added to the new-reviewed-decision list; S7.1 references added. | **Faithful** — and the new-decision guard hardens canon against premature L8 retirement. |
| **BAD Decision 34** | Amended in place — no decision entry deleted, full prior-decision history preserved in the footer; L8 conditional, new L9 limitation bullet; cooling-off named with owner-waiver; review trail extended with the four S7.1 docs; footer dated 2026-05-18. | **Faithful** — the never-delete-BAD rule is respected; Decision 34 is amended, not replaced; every diff hunk falls inside Decision 34's block + footer. |
| **Operator runbook** | Intro, "Local Founder WebAuthn Ceremony" section, and operational rules updated; a new manual-recovery instruction carries T-2 ("Preserve evidence does not mean the `0600` audit JSONL is append-only or tamper-proof; a privileged local filesystem actor remains covered by L1"); L8 conditional + new L9 limitation entries. | **Faithful.** |

## T-1 and T-2

Both spec-stage tightenings the second-fold assigned to the canonicalization
stage landed — and each in two places:

- **T-1** (staged registration-before-authorization enable considered and
  rejected) — S7.1 spec D5 and S7 spec D13.
- **T-2** (the `0600` audit JSONL is not append-only / not tamper-proof, and the
  "preserve evidence" instruction must not describe it as forensic proof) —
  S7.1 spec D16 and the operator runbook's manual-recovery instruction.

## Drift check

- **No S7 v1 decision altered.** Every S7 `spec.md` edit updates a
  forward-reference to S7.1, corrects "witnessed fallback" terminology, adds L9,
  or makes L8's prose conditional. S7 v1's runtime behaviour — the operator/user
  boundary, execution-grant gating, the fail-closed pause — is untouched.
- **No `BETA_ARCHITECTURE_DECISIONS` entry deleted.** Every BAD diff hunk falls
  inside Decision 34's block and the footer; Decisions 1–33 are untouched and the
  footer preserves the full update history. The never-delete-BAD rule is honored.
- **No overclaim.** The canonicalization is scrupulously honest about the
  spec-ratified-but-not-implemented distinction: "ratified as the plan," "not
  implementation," "does not yet," "until S7.1 implementation and
  post-implementation verification pass." Nothing reads as accomplished that is
  not.
- **Cooling-off canonicalized correctly.** ADR 0039 and BAD Decision 34 both now
  state S7.1 implementation "must start after the canonicalization cooling-off
  night unless explicitly waived by the owner with residual momentum risk named"
  — the owner-only, per-slice, residual-named discipline written into canon.
- **No covenant regression.** The "witnessed recovery is not witness
  substitution; no witness gains read / bonded-user / maintainer authority"
  guarantee is preserved and, in S7 `spec.md`, sharpened.

## Nits — non-blocking, recommend trivial cleanup

The "witnessed fallback" → "witnessed social recovery" terminology sweep is
complete except for two cosmetic occurrences of the old synonym. Both state
correct, on-covenant substance; only the term is stale:

- **N-1** — `s7-operator-user-role-boundary/spec.md:148` (RED test contract):
  "Witnessed fallback does not grant witness read authority." The
  canonicalization swept the S7 prose but missed this test-contract line.
- **N-2** — `s7.1-local-webauthn-ceremony/spec.md:878` (D17 body): "Witnessed
  fallback is not witness substitution." This is a pre-existing term carried from
  ratified v2; D17's header and the L9 section already say "witnessed social
  recovery."

Neither is a faithfulness failure, an overclaim, or drift — "witnessed fallback"
and "witnessed social recovery" name the same deferred concept. Recommend a
one-word cleanup at convenience (naturally folded when S7's RED contract or the
S7.1 spec is next touched); neither blocks the cooling-off night or
implementation.

## Verdict and what's next

**PASS.** The S7.1 canonicalization faithfully carries ratified spec v2 into all
five canonical surfaces. L8 is honestly conditional, L9 honestly live, T-1/T-2
landed, the cooling-off discipline is canonical, and no S7 decision or BAD entry
was lost. The blueprint is now law; the front desk is not yet built, and canon
says exactly that.

Ladder:

1.–4. Diagnostic and spec ladders — done; both lanes ratified.
5. Canonicalize the S7.1 spec — done (`2c3287d`).
6. **Faithfulness check — this document, PASS.**
7. **Cooling-off night** — owner discipline. Planning and implementation do not
   share a day; the night between the sealed spec and the first line of code is
   structural. It is the owner's alone to keep or waive — per-slice, recorded,
   residual momentum-misjudgment risk named — and ADR 0039 / BAD Decision 34 now
   canonicalize exactly that.
8. RED-first implementation against the S7.1 115-test contract, both-lane
   post-implementation verification, push.

*This verification is read-only. No code, spec, ADR, BAD, or non-review file was
modified; this document is the council's deliverable. The canonicalization commit
`2c3287d` was read firsthand in full via `git show`; each of the five surfaces
was verified against ratified spec v2 and the Claude council findings, and the
stale-terminology state confirmed by direct grep. No `*codex-panel*` file was
read.*
