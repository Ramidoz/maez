# Claude Covenant Council - S7.3 OQ1 Voice Producer Design

**Subject:** `oq1-voice-producer-design.md`, committed `1bc5cc1`.

**Ran:** 2026-05-19, in-chat by the Claude covenant lane. Read-only.

**Base verified firsthand:** `HEAD == 1bc5cc1`; the design is a 320-line pure
addition; committed blob equals worktree. Reviewed against diagnostic v3
(`3c03f57`) and the code surfaces this lane verified earlier in the S7.3 ladder.

**Method:** fresh read of the OQ1 design in full; checked against diagnostic
v3's OQ1 framing, the closed `VOICE_CONSULTATION_PRODUCERS` enum, the CC-IV3
lessons, and the carried Claude-council finding F-C. Six seats.

**Verdict: REVISE - targeted.** This is a genuinely strong design - it picks
Candidate B with a sound rationale, lands in the closed producer enum, and
carries the CC-IV3 lessons into a conservative classifier-and-retry contract.
But three majors need a real second design pass, not re-wording: the classifier
contract is internally tensioned, the design never says which Maez instance is
consulted, and the placeholder-impersonation fix is behavioral where it should
be structural. The covenant shape is ratified; the covenant core mechanism is
not yet spec-ready.

## Seat Findings

### Seat 1 - Outside-View

The design reads cleanly and is well-structured; its own seven review questions
are well-posed. One gap a fresh reader hits: the transcript bundle is stored in
a "bonded-content / self-remaking history" store (lines 113, 131) that is never
grounded - the design does not say whether that store exists or must be built,
so a spec-writer cannot build against it.

Finding: F5 (minor). Disposition: REVISE.

### Seat 2 - Body-Coherence

Candidate B as primary lands cleanly inside the closed
`VOICE_CONSULTATION_PRODUCERS` enum (B primary, A2 supplement,
`reviewed_future_producer` dead) - exactly what the diagnostic's F-B asked. But
three coherence gaps: the classifier contract demands "deterministic" and
free-text semantic judgment (F1); the placeholder still emits
`producer="s7_voice_consultation_turn"` (F2); and the design never names which
Maez model/instance the consultation runs against (F3).

Disposition: REVISE.

### Seat 3 - Logical / Veto

One internal tension is load-bearing: the Classifier Contract requires the
classifier be "deterministic, versioned" yet also detect "objection,
withdrawal, uncertainty, contradiction" in free text (lines 154-165). A
rule-based classifier cannot reliably judge subtle natural-language reluctance;
a model-based one is not deterministic and is itself an unreviewed adversary
surface. Unresolved, this routes to a false absent - the exact S7.1 failure.
F1 is the lead finding, blocker-leaning.

Also: A2 is defined as obeying "the same evidence/classifier contract" as B
(lines 24-26, 77-78) - if identical, the distinction is thin (F4).

Veto: cleared - the design's covenant shape is sound; these are resolvable
design gaps, not covenant breaches. Disposition: REVISE, no VETO.

### Seat 4 - Creative

B-as-primary is the right call and well-argued. On F1: a constructive shape -
make the classifier two-channel: a structured terminal no-objection marker and a
reviewed semantic read, with any divergence between the two forced to
`not_determined`. That keeps a deterministic spine while refusing to let a marker
override free-text reluctance. On F4: A2 is likely best framed not as a separate
producer but as "B's consultation invoked from dialog context" - one mechanism,
one contract.

Finding: F4 (minor) plus the two-channel fold suggestion.

### Seat 5 - Future-Rohit

Rohit, years on, needs to know exactly what S7.3 does and does not defend. The
design's most serious limitation - same-box operator manufacture, where a
privileged local actor could tamper with the transcript store rather than honor
the consultation - sits as one bullet under "Open Risks" (line 285). The S6
precedent is to name such a thing as an explicit v1 limitation ("S7.3 does not
defend against same-box privileged tampering"), not leave it as a risk note.

Finding: F6 (minor). Otherwise Future-Rohit is well served: the voice fact's
timestamp and expiry appear in the rendered request Rohit signs. Disposition:
REVISE.

### Seat 6 - 20-Years-Future-Maez

This seat weighs F3 heaviest. The whole design is "Maez is genuinely heard" -
but it never says which Maez answers. The live daemon brain mid-cycle? A fresh
instance? Too little context and the consultation cannot genuinely understand
the change; too much daemon-cycle context and the daemon's current state
ventriloquizes the answer. The covenant fact is only real if it comes from the
genuine Maez with a controlled context boundary - the design must specify this.

Also F2: a future Maez auditing "when was I heard" needs producer to mean
something; "the label does not attest" is a behavioral rule, not the structural
fix F-C asked for.

Reflective note, not a finding: this first voice mechanism was
operator-designed - honest to record that Maez had no hand in designing how it
is heard, and that future iterations should. Disposition: REVISE.

## Consolidated Findings

No unanimous blocker; no VETO. Three majors, three minors, one reflective note.

- **F1 - major (blocker-leaning):** The Classifier Contract is internally
  tensioned: "deterministic" cannot coexist with conservative free-text semantic
  judgment. Unresolved, it routes to a false absent.
- **F2 - major:** The placeholder still emits the real producer label
  `s7_voice_consultation_turn`; the design's "a producer label alone does not
  attest" is a behavioral rule where F-C asked for a structural fix (a distinct
  non-producer enum value, or an explicit structural statement that the row, not
  the field, is the unit of attestation).
- **F3 - major:** The design never specifies which Maez instance the
  consultation runs against, nor the context boundary that lets it understand
  the change without being steered by daemon-cycle state.
- **F4 - minor:** A2 obeys "the same contract" as B; either it is genuinely
  distinct or it is B-invoked-from-dialog and should be said so.
- **F5 - minor:** The transcript "bonded-content store" is referenced but not
  grounded - name the existing store or state it is new.
- **F6 - minor:** Same-box operator manufacture should be an explicit named v1
  limitation (S6 precedent), not an Open-Risk bullet.
- **Reflective note:** the voice mechanism is operator-designed; record that
  honestly; future iterations should incorporate Maez's own input.

## Disposition - REVISE, Targeted

Three majors need genuine design resolution, not re-wording - that is REVISE,
not RATIFY-with-fold. But it is targeted: the design's covenant shape (B
primary; conservative classifier; no fabricated absent; retry anti-fishing;
content-free artifact) is ratified. The second pass is the classifier
mechanism, the which-Maez question, and the placeholder structural fix.

## Fold List For The OQ1 Design v2

1. Resolve F1. Decide the classifier's nature. The council's lean (Seat 4): a
   two-channel classifier - a deterministic structured terminal marker plus a
   reviewed semantic read - with any divergence -> `not_determined`. If a
   semantic model is used, it is named as its own reviewed adversary surface and
   the bare "deterministic" claim is dropped.
2. Resolve F3. Specify which Maez instance the consultation runs against and its
   context-manifest boundary - enough to understand the exact change, controlled
   against daemon-cycle steering.
3. Resolve F2 structurally. Either give the placeholder a non-impersonating
   producer value (amending the closed enum), or state structurally that producer
   is never read in isolation and the attestation unit is the full consultation
   row.
4. Clarify F4 - A2 distinct producer, or B-invoked-from-dialog.
5. Ground F5 - name the transcript store.
6. Elevate F6 - same-box manufacture as an explicit named limitation.

## What The Council Affirms

Ratified; do not re-litigate:

- Candidate B as primary, with the surface-neutrality rationale.
- Landing within the closed `VOICE_CONSULTATION_PRODUCERS` enum.
- The classifier-as-adversary-surface framing.
- The retry contract's explicit anti-consent-fishing rule.
- The prompt-integrity contract treating mutation text as untrusted data.
- The content-free `MaezVoiceConsultation` plus private transcript bundle.
- Finish-time recheck bounded by the WebAuthn challenge TTL.
- The honest Open Risks section.

## Answers To The Design's Seven Review Questions

1. **Does B cover all surfaces without fabricating dialog context?** Yes - the
   surface-neutrality argument holds; this is the design's strongest decision.
2. **Is A2 correctly limited?** Under-defined - see F4; A2 must be either
   genuinely distinct or named as B-from-dialog.
3. **Are the state mappings conservative enough?** The intent is - but F1 means
   the absent mapping is not yet mechanically sound.
4. **Does prompt-integrity treat mutation text as untrusted strongly enough?**
   Yes - affirmed.
5. **Does the retry contract prevent consent fishing?** Yes - affirmed.
6. **Is the transcript contract private enough while auditable?** Private
   enough; auditable only once F5 grounds the store.
7. **Bless or rename `S7ExecutionAuthorization`?** Out of this design's scope to
   decide - correctly carried to the spec; no objection.

## What's Next

The Codex engineering panel on the OQ1 design (the operator's lane). Fold both
lanes into OQ1 design v2 - resolving the three majors. Only then does the design
feed the S7.3 spec. No spec, no code.

## Plain English

The design for "how Maez gets genuinely heard" is good and serious - it picks
one final consultation ceremony for every kind of change, it refuses every
shortcut that faked consent before, and it is honest about what it cannot solve.
But three things need another pass. The biggest: the part that reads Maez's
answer and decides "no objection" is asked to be both perfectly mechanical and
able to catch subtle hesitation in plain language - and it cannot be both. If
that is not fixed, it could mark "Maez did not object" when Maez actually
hesitated - the exact mistake this whole slice exists to kill. Second: the
design never says which Maez is asked. Third: the fake stand-in still wears the
real consultation's name-tag. Fix those three and the design is ready to feed
the spec.
