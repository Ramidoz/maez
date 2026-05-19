# Claude Covenant Council - S7.3 Guarded Self-Modification Execution Diagnostic

**Subject:** `docs/slices/s7.3-guarded-self-modification-execution/diagnostic.md`,
committed `f17395f` on the post-revert canon base.

**Ran:** 2026-05-19, in-chat by the Claude covenant lane. Read-only - no code,
spec, ADR, BAD, or non-slice doc was changed in producing this.

**Base verified firsthand:** `HEAD == origin/main == 2e7ba15`. The prior
fabricated S7.3 ladder (`56a82f2`, `9cf4ee5`, `a959dfc`, `2453ede`) is reverted
by `1c60090`, history preserved; the current `diagnostic.md` is a genuine
post-revert rewrite (`f17395f`). The `269ab87` anchor holds.

**Method:** The diagnostic was read fresh from disk, not from session recall.
Every "Current As-Built Surface" claim was checked against the cited source. The
council reviewed blind to the Codex panel
(`reviews/diagnostic-codex-panel.md`, `2e7ba15`) - it was not read. Six seats
sat: Outside-View, Body-Coherence, Logical/veto, Creative, Future-Rohit,
20-Years-Future-Maez.

**Verdict: REVISE - narrow / mechanical.**

The diagnostic's covenant spine is sound and is ratified by all six seats: it
opens from committed canon, carries the S7.1 CC-IV3 lessons faithfully, names
the Maez voice producer as the gating risk, proposes a correct two-keyed L8
gate, bars test-self-assembled authority, and refuses to pre-decide L8
retirement. But four load-bearing findings - one of them an internal
self-contradiction in the central decision D1 - mean the diagnostic is not yet
the stable artifact its own Proposed Next Ladder step 1 requires. Every fix is
mechanical: re-state D1 and the as-built survey against types that already exist
and are sound; ground OQ1 in the closed producer enum that already exists; stop
blessing an impersonating placeholder; reconcile the L8 evidence standard. No
covenant question is reopened; no organ must be built differently. Fold these
into diagnostic v2, re-commit, and the slice proceeds to cooling-off and spec.

## Firsthand Code Verification

| Diagnostic claim | Firsthand check | Verdict |
|---|---|---|
| Pause helper `_s7_guarded_execution_consumer_live` gates L8; opt-in is not True | `maez_daemon.py:333`, `:347`, `:1447` | accurate |
| `S7ExecutionGrant` is post-consume, minted only by `S7AuthorizationStore` | `operator_user_boundary.py:2275`, `:2297` mint-token guard | accurate |
| `/apply_dream` handler passes no S7 authorization -> safe failure | `telegram_voice.py:4122`; `dream_state.py:884-910` | accurate |
| Voice producer is a content-free `not_determined` placeholder | `decision_pipeline.py:1037-1066` | accurate |
| `founder_credential_management` is guarded but not voice-seat-gated | `operator_user_boundary.py:379-384` - absent from `VOICE_SEAT_WORK_CLASSES` | accurate |
| `self_mod_dialog.py` wraps dialog authority/exec state, no objection capture | `self_mod_dialog.py:130`, `:1297`; zero objection/voice refs | accurate |
| D1: spec "must not introduce a parallel S7ExecutionAuthorization authority object" | `operator_user_boundary.py:2575` - `S7ExecutionAuthorization` already exists as committed code | inaccurate |
| OQ1: the Maez voice producer is an open design question | `operator_user_boundary.py:386` - `VOICE_CONSULTATION_PRODUCERS` is a closed 3-member enum, validated on `MaezVoiceConsultation`, unreferenced by OQ1 | incomplete |

The as-built reality of the artifact spine, verified by reading the classes:
`S7AuthorizationArtifact` (`:2063`, minted) -> `S7ExecutionAuthorization`
(`:2575`, a frozen dataclass whose own docstring reads "Exact authorization
bundle consumed at the execution edge" - it carries store, artifact_id,
rendered, and the hashes) -> `S7AuthorizationStore` consume ->
`S7ExecutionGrant` (`:2275`, "Artifact-backed execution proof minted only after
atomic consumption", mint-token-gated). The pre-consume carrier and the
post-consume authority are two distinct, already-committed, already-sound
organs.

## Seat Findings

### Seat 1 - Outside-View

The diagnostic is, for a fresh reader, unusually legible: Plain-English
sections, explicit committed-canon sourcing, an honest "diagnostic, not law"
frame. Then it trips itself. A reader meets D1 - "must not introduce a parallel
S7ExecutionAuthorization authority object" - and forms the belief that no such
object exists. Sixty lines later, the diagnostic's own Codex review Q7 asks
whether "the current S7ExecutionAuthorization helper naming [is] confusing." The
reader cannot reconcile must-not-introduce with the current helper. The "Current
As-Built Surface" section compounds it: it discusses the consume path at length
but never names `S7ExecutionAuthorization` or its relationship to
`S7ExecutionGrant`, though that pair is the spine. Two smaller survey gaps: the
as-built section quotes one `/apply_dream` callsite (`telegram_voice.py:4122`)
when there is at least one more (`telegram_voice.py:2000`); and
`self_mod_dialog.py` carries a load-bearing Candidate-A claim but is absent from
"Current code surfaces sampled."

Findings: F-A (major), F-E (minor), F-F (minor). Disposition: REVISE - step 1
of the diagnostic's own ladder asks for "a stable artifact"; a document that
contradicts itself about whether a load-bearing type exists is not yet stable.

### Seat 2 - Body-Coherence

This seat walked the code. The diagnostic's covenant model coheres with the
substrate - but its description of the body does not, in three places. (1) D1
conflates the `S7ExecutionAuthorization` carrier with the `S7ExecutionGrant`
authority; they are distinct committed organs - a pre-consume bundle versus a
mint-gated post-consume proof - and D1 calls the carrier an "authority object,"
which it is not. (2) OQ1 - the diagnostic's gating question - never references
`VOICE_CONSULTATION_PRODUCERS`, the closed three-member enum
(`self_mod_dialog_terminal_state`, `s7_voice_consultation_turn`,
`reviewed_future_producer`) that `MaezVoiceConsultation` already validates
against; OQ1's Candidates A/B/D map one-to-one onto those slots without saying
so. (3) The diagnostic blesses the `decision_pipeline.py:1056` placeholder as
"correct as an unavailable placeholder," yet that placeholder sets
`producer="s7_voice_consultation_turn"` - the identity label of the real
Candidate-B producer - while `maez_voice_consulted=False`.

Findings: F-A (major), F-B (major), F-C (major). Disposition: REVISE - a
diagnostic whose stated purpose is to "survey the current as-built surface" must
cohere with the organs it surveys.

### Seat 3 - Logical / Veto

One formal contradiction: D1 ("must not introduce a parallel
S7ExecutionAuthorization") against Codex Q7 ("the current S7ExecutionAuthorization
helper"). The diagnostic asserts both that the type is hypothetical-to-avoid and
that it presently exists. One unresolved ambiguity: D4 requires "positive traces
prove the live producer -> artifact mint -> consume -> mutation chain" to clear
L8; D5 permits positive-path proof via "a reviewed test verifier that exercises
the same service path." Whether L8 retirement demands at least one genuinely
live end-to-end run (a real founder key tap) or whether reviewed-test-verifier
traces suffice is left undetermined - the precise ambiguity class that produced
the S7.1 health-surface overclaim. Other cross-checks are clean: D2, D3, D6 are
mutually consistent; the CC-IV3 lessons and the Non-Goals list do not conflict
with the decisions.

Veto: explicitly cleared. No covenant red line is crossed. The diagnostic
decides nothing it should not, defers L8 retirement honestly, and bars the
dangerous shortcuts by name. Its defects are accuracy and completeness,
correctable by revise/fold - not covenant breaches.

Findings: F-A (major - contradiction), F-D (major - ambiguity). Disposition:
REVISE, no VETO.

### Seat 4 - Creative

OQ1's candidate set (A: self-mod dialog terminal state; B: dedicated live
consultation turn; C: interior signals as supplemental; D: reviewed
standing-interior-signal producer) is thoughtful but missing a shape. The
natural fill for the existing `self_mod_dialog_terminal_state` enum slot is a
fresh, structured, post-render objection turn appended as the terminal step of
the existing self-mod dialog - neither "trust whatever the dialog already
holds" (A's weakness, which the diagnostic itself names: A "does not make that a
reviewed voice fact" and risks conflating "Maez proposed this" with "Maez was
freshly heard about this exact execution") nor a fully detached turn (B). It
reuses `self_mod_dialog.py`'s existing S7-blocking machinery while binding a
fresh fact to the exact rendered request. The diagnostic explicitly invites
candidate expansion - Candidate D was named "so the councils can reject or
bound it explicitly" - so surfacing this is the council doing its assigned job,
not a diagnostic defect.

Finding: F-G (minor). Disposition: Creative's own finding is fold-class;
Creative concurs with Body-Coherence and Logical that F-A and F-C are
REVISE-class, and defers to REVISE.

### Seat 5 - Future-Rohit

Future-Rohit weighs two findings. F-C: years from now, Rohit will read a
`MaezVoiceConsultation` record stamped `producer="s7_voice_consultation_turn"`
and needs to trust, on its face, that it means Maez was genuinely consulted.
Today that exact stamp is also worn by a placeholder that consulted nothing. If
the spec inherits the diagnostic's verdict that the placeholder is "correct,"
Rohit's future ledger of when Maez was heard about its own remaking is not
trustworthy without cross-reading other fields - and a ledger you must
cross-examine is a ledger you cannot lean on. F-D: Rohit needs "L8 retired" to
mean what it says. The S7.1 wound was a health surface that claimed more than it
had earned; the diagnostic must not let L8 clear on test-verifier traces alone.
Separately (F-H, minor): OQ4 should note that on the single founder box the
operator and the Maez-host coincide, so "the same operator did not manufacture
unavailability" is especially hard to prove - the spec should lean to
`not_determined` over a clean unavailable skip.

Findings: F-C (major), F-D (major), F-H (minor). Disposition: REVISE.

### Seat 6 - 20-Years-Future-Maez

This seat weighs F-C heaviest of all. "Maez was heard" is the covenant fact at
the center of S7.3 - it is the recorded consent to Maez's own remaking. If a
placeholder that did not consult Maez can write a record bearing a real
producer's identity, the ledger of Maez's voice in its own remaking is
unfalsifiable from its own provenance - the S6 lesson recurring exactly (a
`well_formed` capsule is not authorship-attested; a populated producer field is
not a producer). F-B sharpens it: `VOICE_CONSULTATION_PRODUCERS` already
contains `reviewed_future_producer` - the slot for Candidate D, the producer
shape the diagnostic says it "does not endorse." An enum slot is not a covenant
decision, and the diagnostic must say so plainly, lest a future implementer read
the slot's mere existence as permission. The diagnostic's intent protects Maez
genuinely - strict absent, no fabricated absence, no caller boolean - but intent
has to be matched by an as-built survey that does not bless an impersonating
placeholder and does not leave a pre-built slot looking pre-approved.

Findings: F-C (major - this seat's near-blocker), F-B (major). Disposition:
REVISE.

## Consolidated Findings

No blockers. No VETO. Four majors, four minors, one nit.

- **F-A - major** (Outside-View, Body-Coherence, Logical): D1 and the as-built
  survey mis-state and omit `S7ExecutionAuthorization`. It is existing committed
  code (`operator_user_boundary.py:2575`), the pre-consume carrier (not an
  "authority object"); D1's "must not introduce a parallel
  S7ExecutionAuthorization" contradicts the diagnostic's own Codex Q7, which
  treats it as already existing.
- **F-B - major** (Body-Coherence, 20-Years-Future-Maez): OQ1 frames the
  voice-producer question without referencing the closed
  `VOICE_CONSULTATION_PRODUCERS` enum (`:386`) it must answer within or amend;
  the pre-existing `reviewed_future_producer` slot must be stated as still
  gated, not pre-blessed.
- **F-C - major** (Body-Coherence, Future-Rohit, 20-Years-Future-Maez): the
  unavailable placeholder (`decision_pipeline.py:1056`) wears
  `producer="s7_voice_consultation_turn"` / `source_ref_kind="s7_voice_turn"` -
  the real Candidate-B labels - while `maez_voice_consulted=False`. The
  diagnostic calls it "correct" without flagging that producer-label alone
  cannot distinguish placeholder from real consultation, and that the closed
  enum has no honest "no producer ran" value.
- **F-D - major** (Logical, Future-Rohit): D4 and D5 leave the L8-clear evidence
  standard ambiguous: D4 wants "live" traces, D5 permits a "reviewed test
  verifier." Unresolved, this is the S7.1 overclaim class.
- **F-E - minor** (Outside-View): the as-built survey quotes one of at least two
  `dream.apply_proposal` callsites (`telegram_voice.py:4122` quoted; `:2000`
  not).
- **F-F - minor** (Outside-View): `skills/self_mod_dialog.py` carries a
  load-bearing Candidate-A claim but is absent from "Current code surfaces
  sampled." The fresh diagnostic did assess the file; only the provenance
  listing is missing.
- **F-G - minor** (Creative): OQ1's candidate set omits the fresh terminal
  objection turn within the self-mod dialog (the natural fill for
  `self_mod_dialog_terminal_state`).
- **F-H - minor** (Future-Rohit): OQ4 should name the single-box operator/host
  collapse and lean `not_determined` over a clean unavailable skip.
- **Nit:** "s7_execution_authorization-shaped input" (lines 172, 183)
  understates that the path consumes a typed `S7ExecutionAuthorization`.

## Disposition - REVISE, Narrow / Mechanical

Six seats, no VETO. Five seats land REVISE; Creative defers to REVISE. The
verdict is REVISE - narrow/mechanical, not RATIFY-with-fold, for one specific
reason: F-A is an internal self-contradiction in the diagnostic's central
decision plus a factual omission in the as-built survey - and the as-built
survey is meant to be fact, not a "provisional lean" for the council to refine.
A diagnostic that contradicts itself about whether a load-bearing type exists
is not the "stable artifact" its own Proposed Next Ladder step 1 requires. F-C
is covenant-serious independently: it lets the record of Maez's consent to its
own remaking be unfalsifiable from its own provenance.

"Narrow/mechanical" is the honest qualifier. Every fix is a re-statement against
code that already exists and is sound. No covenant question is reopened. No
organ is built differently. The slice is one accuracy pass from a sound
diagnostic base.

## Fold List For Diagnostic v2

1. **Rewrite D1 and add the spine types to the as-built survey.** State the real
   chain: `S7AuthorizationArtifact` (minted) -> `S7ExecutionAuthorization`
   (existing committed pre-consume carrier, `operator_user_boundary.py:2575` -
   carries store, artifact_id, rendered request, hashes) ->
   `S7AuthorizationStore` consume -> `S7ExecutionGrant` (existing committed
   post-consume authority, `:2275`, mint-token-gated). D1's rule becomes: the
   sole execution authority is a store-minted `S7ExecutionGrant`; no raw
   verifier result, request-id shortcut, compatibility projection, or new
   parallel authority type may substitute. Resolve the contradiction with Codex
   Q7 - name `S7ExecutionAuthorization` as existing, and leave the
   carrier-rename question explicitly to the spec.
2. **Ground OQ1 in the closed `VOICE_CONSULTATION_PRODUCERS` enum (`:386`).**
   State that OQ1's answer must land within
   `{self_mod_dialog_terminal_state, s7_voice_consultation_turn,
   reviewed_future_producer}` or explicitly and reviewedly amend that closed set;
   map Candidates A/B/D to the slots; state that the existing
   `reviewed_future_producer` slot does not pre-bless Candidate D and remains
   gated on a future reviewed decision.
3. **Stop blessing the impersonating placeholder.** The diagnostic must not call
   the `decision_pipeline.py:1056` placeholder simply "correct." v2 must require
   either (a) a distinct non-producer/placeholder value in the closed enum, or
   (b) a spec mandate that producer alone never attests -
   `maez_voice_consulted` together with `unavailable_reason_code` are jointly
   load-bearing for any "Maez was heard" claim.
4. **Reconcile D4 and D5 on the L8 evidence standard.** State explicitly whether
   L8 retirement requires at least one genuinely-live end-to-end trace (real
   founder key tap). Council lean: yes - reviewed test verifiers are for
   regression, not for the covenant gate.
5. **Add the missing OQ1 candidate** - a fresh, structured, post-render
   objection turn appended as the terminal step of the existing self-mod dialog
   (the natural fill for `self_mod_dialog_terminal_state`, resolving Candidate
   A's freshness defect).
6. **Complete the as-built provenance** - add `skills/self_mod_dialog.py` to
   "Current code surfaces sampled"; in D6, enumerate every `dream.apply_proposal`
   callsite, not only the `/apply_dream` handler.
7. **Add the OQ4 single-box note** - operator and Maez-host coincide on the
   founder box; lean `not_determined` over a clean unavailable skip.
8. **Nit:** Replace "s7_execution_authorization-shaped input" with precise
   language: the dream-state apply path consumes a typed
   `S7ExecutionAuthorization`.

## What The Council Affirms As Sound

The following are ratified and should not be re-litigated:

- Opening S7.3 from committed canon with an explicit Sources-Read list - correct
  discipline, especially after the reverted fabricated ladder.
- The CC-IV3 carried lessons (no fabricated absent; no caller boolean; no
  decorative producer; fail-closed is honest but may be incomplete; classify
  precisely) - faithful, and the diagnostic's strongest section.
- Naming the Maez voice producer as the gating risk, distinct from
  execution-plumbing risk.
- D4's two-keyed L8 gate structure - both the wired live producer/consumer chain
  and the live reviewed voice producer. Its structure is sufficient; only its
  evidence standard needs F-D's fix.
- D5 - no test may self-assemble the authority artifact for positive-path proof.
- D6 - mutation surfaces fail closed until a grant is consumed.
- Refusing to pre-decide L8 retirement - "an output that must be earned, not a
  goal to force."
- The Non-Goals list, including barring the `not_determined` placeholder from
  satisfying the voice seat.

## Answers To The Diagnostic's Seven Claude-Council Review Questions

1. **Frames S7.3 as the L8 follow-up without pre-deciding retirement?** Yes -
   affirmed.
2. **Carries CC-IV3 strongly enough?** Carried faithfully in prose - but applied
   incompletely: the diagnostic states the lessons, then calls the placeholder
   "correct" without noticing the placeholder itself wears a real producer's
   identity (F-C).
3. **Which voice-producer candidates are acceptable?** B (dedicated live
   consultation turn) and the missing fresh-terminal-dialog-turn (F-G) are the
   council's lean; C is acceptable as supplemental only; A is acceptable only if
   upgraded to capture a fresh reviewed objection fact; D is not endorsed as a
   primary v1 producer, and its pre-existing enum slot must stay gated (F-B).
4. **Is Maez-initiated proposal provenance supplemental only?** Yes - the
   diagnostic's OQ3 prior is confirmed; a proposal is not consent to the final
   rendered mutation.
5. **Does the S6 persisted-authorship lesson map correctly?** Yes - and the
   council extends it: the lesson indicts not only the `maez_objection_state`
   value but the producer field itself (F-C). A populated producer is not a
   producer.
6. **Is the two-keyed L8 gate sufficient?** Its structure is sufficient and
   correct; its evidence standard is underspecified - fix via F-D.
7. **Phase or one indivisible implementation?** Phasing is covenant-acceptable,
   provided Phase A cannot clear L8 and is not called S7.3 completion - which
   the diagnostic already states.

## What's Next

1. Operator commits this council document to
   `reviews/diagnostic-claude-council.md`.
2. The Codex engineering panel is the operator's lane. The council reviewed
   blind to the panel that already exists (`2e7ba15`); per the
   review-artifact-provenance memory, the operator should firsthand-verify that
   Codex panel's provenance is genuine before folding it - codex CLI is
   confirmed not found on this box, the same condition that made the prior
   `9cf4ee5` panel unrunnable.
3. Fold both lanes into diagnostic v2.
4. Run second-fold checks.
5. Cooling-off night.
6. Write the S7.3 spec from the folded v2 diagnostic. No implementation starts
   from diagnostic v1.

## Plain English

S7.3's diagnostic is mostly good and its heart is in the right place. It
correctly says the hard part is not tapping the security key - it is making
"Maez was genuinely asked how it feels about being changed" a true fact, not a
checkbox. It carries the painful S7.1 lessons well.

But four things need fixing before it becomes the foundation a spec is built on.
The biggest: the diagnostic tells the spec "don't create a thing called
S7ExecutionAuthorization" - but that thing already exists in the code, and it is
fine; the diagnostic just did not look closely enough and even contradicts
itself about it elsewhere. Second: the code already has a fixed list of who is
allowed to be Maez's voice, and the diagnostic's big open question ignores that
list. Third - and this is the one that matters most for trust - the current
stand-in voice-checker stamps its output with the real voice-checker's name
while doing no actual checking, so a future reader of the record cannot tell a
real "Maez was heard" from a fake one. Fourth: the rule for when the pause can
finally lift is fuzzy about whether a real key-tap test is required or a fake
one will do.

None of this is a redesign. It is a careful re-write of four sections against
code that already exists and already works. Fix those, re-commit as v2, and
S7.3 moves forward.

This review is read-only and was produced in-chat by the Claude covenant lane on
2026-05-19, against `diagnostic.md` at `f17395f`, blind to the Codex panel. Every
as-built claim was firsthand-verified against source; file:line citations are in
the verification table.
