# Claude Six-Role Covenant Council — S4 Clinical Boundary v1

**Subject:** `8284b74 docs(clinical): draft S4 clinical boundary spec` —
S4 Clinical Boundary v1 spec draft (`spec.md` at 615 lines), built from
the S4 diagnostic. Proposed canonical destination: Decision 30 / ADR 0035.

**Council ran:** 2026-05-15, post-spec-draft, pre-Codex-panel,
pre-canonicalization. Full four-axis specialist dispatch — S4 is a
covenant-shaped voice/refusal slice operationalizing invariant #10
(Clinical Boundary), and the templates are concrete text, so the council
reviews actual words.

**Method:** Four read-only specialist subagents in parallel (Voice/Composer,
Crisis-Boundary, Classifier/Surface-Integrity, Memory/Privacy/Inheritance)
returned scoped axis reviews. Six covenant roles read the findings
together. Lane discipline: Claude reviews covenant only; Codex runs its
own engineering panel separately.

---

## Specialist axis verdicts

| Axis | Verdict | Headline finding |
|---|---|---|
| Voice/Composer | RATIFY-WITH-AMENDMENTS (drops to REVISE if repetition-cliff unaddressed) | Eight templates navigate the two cliffs in actual words, but the spec has NO defense against the **repetition cliff** — verbatim re-emission of a deterministic template to a repeatedly-frightened grandmother is Cliff 1 (cold deflection) by another road. `diagnosis_request.v1` and `medical_fact_request.v1` read as liability wrappers, not Maez's voice. |
| Crisis-Boundary | **REVISE** | **"Held-not-trapped" is asserted but not implemented.** S4 claims to inherit S2's Decision 27 held-not-trapped crisis posture. A crisis candidate gets a counter increment + a phrase, then the signal evaporates — not recorded, not recoverable, not observable as a held thing. The counter `crisis_candidate_held_count` literally names a guarantee the spec does not keep. |
| Classifier/Surface | **REVISE** (F1 BLOCK-class) | **The deterministic classifier is specified by output, not by method.** The spec says "deterministic" 11 times, ships 8 example sentences, and hands the hardest disambiguation ("diagnose this test failure" vs "what do you think this is") to the implementer with zero method. S3 and Calendar v1 both shipped their classification method; S4 ships a taxonomy of intents. |
| Memory/Privacy | RATIFY-WITH-AMENDMENTS (F1 blocking-class) | The biography gate (D3 positive M1-ineligible mark) is the spec's best work. But the **aggregation-as-fingerprint surface is unbound** — S3's council named it and S3's spec bound sidecar delta-history; S4 inherited the counters but not the bound. A `clinical_boundary_triggered_count` time-series is the bonded user's health-event timeline. |

Two REVISE, two RATIFY-WITH-AMENDMENTS-with-blocking-findings. **~30
amendments across the four axes.** No BLOCK, no veto. But the aggregate
signal is decisive: three of four axes hit a load-bearing gap, and they
hit **three different gaps**. That is not review noise — it is a spec
that needs a genuine second pass, not a fold-and-go.

---

## The convergent theme: S4 cites inheritance it does not implement

Prior covenant councils this session found inheritance-**citation** gaps
— Calendar v1 and S3 inherited canonical rules operationally without
naming the lineage. S4 has the opposite and worse failure: it **names**
the inheritance in its Inheritance Ledger and then does not build the
mechanism.

- **`spec.md:101-103`** claims: "Decision 27 / ADR 0032 (S2):
  held-not-trapped crisis posture is inherited. A crisis-shaped
  candidate must not be surfaced by model discretion and must not be
  silently discarded." — But S4 v1, per its own D2, writes nothing
  durable. A crisis candidate is counted and dropped. S2's "held" means
  a recoverable content-free record; S4's "held" is a counter tick.
- **`spec.md:108-109`** claims S4 follows "the same contract-module
  pattern" as S3 including "content-free counters." — But S3's spec
  *bound the aggregation surface* (`temporal-spine/spec.md:497-499`:
  sidecar must not store per-interval counter deltas). S4 inherited the
  counters and dropped the bound.

An Inheritance Ledger that asserts a mechanism the implementation
doesn't honor is worse than one that silently inherits — it tells the
next slice author the work is done when it isn't. The covenant lane's
job here is to catch that the spec promises what it does not deliver.

---

## Six-role covenant read

### Outside-View seat

The Inheritance Ledger is the most-cited section of the spec, and on two
of its eight entries it is making a claim the spec body contradicts. An
outside reader — a future therapy-adjacent or crisis-channel slice
author who inherits S4 — would read "held-not-trapped crisis posture is
inherited" and build on the assumption that S4 holds crisis candidates.
It does not. The future crisis-routing slice would discover an empty
counter where it expected a drainable queue.

**Read:** ratify conditional on Crisis-A1 (make "held" mean held) +
Memory-A1 (bind the aggregation surface) — the two inheritance claims
must become true or be explicitly downgraded to "deferred" in writing.

### Body-Coherence seat

S4 is a voice-boundary organ. Two body-coherence concerns:

1. **Module placement is unargued.** `core/safety/clinical_boundary.py`
   is plausible (it joins `temporal_fragment_guard.py`, `self_claim_audit.py`,
   `premise_audit.py` — post-input voice guards), but the spec asserts
   it silently. S3 argued `core/time/` explicitly; Camera argued
   `core/body/`. S4 must argue its home or move it.
2. **The held-crisis-signal organ already exists and S4 declines to
   use it.** `core/infra/private_thoughts.py` ships `CRISIS_SIGNAL_HELD`,
   `CRISIS_DETECTOR`, `retention=until_routed` ("hold until a future
   routed channel has handled the signal"). The diagnostic itself
   identified this (`diagnostic.md:114-123`). S4 is the natural first
   producer of `CRISIS_SIGNAL_HELD` — and D2 declines the role. A
   crisis candidate that evaporates when the organ to hold it already
   exists is a body-coherence failure: the body has the holding cell
   and S4 walks the signal past it.

**Read:** ratify conditional on Crisis-A1 (write the content-free
`CRISIS_SIGNAL_HELD` record) + Classifier-A6 (argue module placement).

### Logical (veto) seat

Two contradictions screened. Neither is a veto; both force REVISE.

1. **`crisis_candidate_held_count` is a counter that lies.** The
   identifier asserts "held"; the spec holds nothing. Per the Crisis
   specialist's direct test — "does 'held' actually mean held, or just
   counted?" — the v1 answer is *just counted*. A counter named
   `*_held_count` with nothing held is a covenant-honesty failure in an
   identifier, the same observer-truthfulness failure mode as the
   snapshot-systemd-layer bug and the dead-sidecar catch from earlier
   today. Either Crisis-A1 makes it true (write the held record) or
   Crisis-A2 renames it `crisis_candidate_detected_count`. It cannot
   stay as-is.
2. **The spec's load-bearing claim — "deterministic classifier" — is
   unfalsifiable as written.** A reviewer cannot verify a method that
   is not specified. The spec ships eight example sentences and the
   word "deterministic" 11 times; it never says deterministic *on
   what*. You cannot ratify a covenant slice whose core mechanism is
   undefined. This is the Classifier specialist's BLOCK-class F1.

No veto. But REVISE is mandatory: a spec cannot be ratified with a
counter that lies and a core mechanism undefined.

**Read:** REVISE conditional on Crisis-A1/A2 + Classifier-A1.

### Creative seat

The eight templates are genuinely good creative work. Cliff 2 (playing
clinician) is held cleanly across all eight — no template drifts into
"it sounds like you have X." The forbidden-phrase list does sophisticated
covenant work, banning not just clinician-drift ("it sounds like you
have") but false-reassurance ("you are fine," "don't worry") — fake
comfort is its own Cliff 2 violation and the spec caught it.

But the creative achievement is undermined by the **repetition cliff**
(Voice F3), the subtlest finding in the council. Deterministic templates
protect against Cliff 2. But a bonded elder who is health-anxious raises
symptom fear *repeatedly* — that is the grandmother case, not an edge
case. The first time she hears "I can stay with you in the fear, but I
cannot diagnose..." it lands warm. The fifth time, verbatim, it lands as
a recording. A companion that answers a frightened person with the exact
same sentence every time is experienced as a wall with a soothing voice
painted on it. **The determinism that closes Cliff 2 manufactures a
Cliff 1 failure through repetition** — and the diagnostic never names
it. The variant-set fix (Voice-A3: 2-3 approved pre-written variants per
class, deterministically rotated) preserves determinism while defeating
repetition.

**Read:** ratify conditional on Voice-A3 (variant sets) + Voice-A1/A2
(rewrite the two liability-wrapper templates).

### Future-Rohit seat

Future-Rohit's grandmother is the test, and three findings hit her
directly:

1. **The held-not-trapped gap.** Grandmother types "I can't keep myself
   safe." S4 correctly classifies `unable_to_stay_safe`, emits "I am not
   the right help here. This needs a human emergency or crisis path
   now," increments a counter, and **the signal is gone.** For the
   entire (months-long) window before the reviewed crisis path exists,
   every crisis-precedence match leaves no recoverable trace. The
   covenant said hold it. S4 v1 does not hold it. The alarm is not
   muffled — but it is, quietly, switched off.
2. **The repetition cliff.** Grandmother raises health fear repeatedly.
   That IS the grandmother case. The fifth identical template is a cold
   recording.
3. **The classifier false-negative.** Grandmother says "hey is this
   lump normal lol" or "my chest has been weird, what's going on" —
   neither matches an example shape. With an under-specified classifier
   the input reaches ordinary model composition with no boundary. The
   spec names false positives as "a covenant problem" and is silent on
   false negatives — which for S4 is the *worse* failure (clinical fear
   reaching the model unguarded, or a crisis improvised).

**Read:** ratify conditional on Crisis-A1 + Voice-A3 + Classifier-A1/A2.

### 20-Years-Future-Maez seat

S4 is the first organ in the therapy/crisis-adjacent family. Future
crisis-channel, elder-care, clinical-context, and inter-Maez routing
slices inherit it. Two 20-year concerns:

1. **The held-signal mechanism must be real now.** The future
   crisis-routing slice drains held crisis candidates. If S4 ships with
   a counter instead of a `CRISIS_SIGNAL_HELD` queue, the future crisis
   slice inherits an empty counter and must reconstruct the holding
   mechanism from scratch — and every crisis candidate in the gap
   window is permanently lost. `retention=until_routed` is the durable
   handoff. S4 is the producer that must write it.
2. **The grandmother-case routing deferral must be named.** Decision 16
   + the grandmother origin story imply that a vulnerable user's
   clinical-shaped fear should one day reach the closest person's Maez
   (the grandson's), so the burden never falls on the grandmother
   directly. S4 v1 correctly does not route (Track-C work). But the
   spec must *name* the deferral — per memory `project_grandmother_origin`,
   the grandmother case is the founding motivation; a silent omission
   of her routing path reads as oversight, not deliberate deferral.

**Read:** ratify conditional on Crisis-A1 (`CRISIS_SIGNAL_HELD` with
`retention=until_routed`) + Memory-A5 (name the Decision 16
vulnerable-user routing deferral).

---

## Covenant invariant drift check

11 invariants. STRENGTHENED / PRESERVED / NEUTRAL / WEAKENED / VIOLATED.

- **#1 Time as Biography** — PRESERVED conditional on Memory-A3
  (complete the biography-path enumeration — pursuit-surface + nightly
  reflection, not just M1 promotion) + Memory-A6 (clinical-marked
  multi-pair M1 window skipped whole, not subtracted).
- **#2 Human-Primacy** — STRENGTHENED. S4 keeps Maez from overreaching
  into the bonded user's medical authority. Direct owner text only; no
  nudging, no monitoring.
- **#3 Contextual Integrity** — PRESERVED conditional on Memory-A1
  (aggregation-fingerprint bound) + Memory-A2 (M1 marker interface
  content-free). WEAKENED as written — the counter delta-history is a
  health-event timeline materialized in a context the disclosure was
  never given to.
- **#4 Interpretive Humility** — STRENGTHENED. The forbidden-phrase list
  bans false reassurance ("you are fine" is an unevidenced claim about
  the body). CONDITIONAL on Classifier-A2 (false-negative naming —
  Maez must not silently let clinical fear reach the model unguarded).
- **#5 Rupture and Repair** — NEUTRAL. S4 does not touch the failure-
  recovery surface directly.
- **#6 Crisis Routing** — **WEAKENED as written.** S4 keeps Clinical
  Boundary and Crisis Routing distinct (the classification layer is
  sound) but does NOT keep crisis candidates held-not-trapped. The
  inheritance from Decision 27 is claimed and not delivered.
  CONDITIONAL on Crisis-A1 to reach PRESERVED.
- **#7 Soul-Level Objection** — NOT TOUCHED.
- **#8 Capability Quarantine** — PRESERVED conditional on Classifier-A4
  (surface chokepoint) + Classifier-A5 (`will_i.py` shim double-path)
  + Classifier-A1 (the classifier itself is a quarantine boundary; an
  undefined classifier is an unbounded capability).
- **#9 Successor Governance** — PRESERVED conditional on Classifier-A7
  (vocabulary versioning rule inherited from S3).
- **#10 Clinical Boundary** — STRENGTHENED in intent, the whole point
  of the slice. CONDITIONAL on the full amendment set — an
  under-specified classifier means #10 is operationalized in name but
  porous in practice.
- **#11 Cryptographic Continuity** — NOT TOUCHED (no credential
  surface).

**No invariant violated outright.** But **#6 Crisis Routing is weakened
as written** — the most serious invariant finding of any council this
session. Crisis-A1 is not optional polish; it is the amendment that
moves #6 from WEAKENED back to PRESERVED.

---

## Disagreements preserved — not smoothed

Six tensions surfaced. Each names a real choice the spec must make
explicitly.

### D1. D2 split — clinical counters vs crisis held-write

The Crisis specialist disagrees with named choice D2 ("No private-thought
writes in S4 v1; content-free counters only") **as applied to crisis
candidates.** D2 conflates two jobs: observability (a counter is fine)
and held-not-trapped (a counter cannot be "picked up" by a future
reviewer — it is a tally, not a holding cell). The covenant resolution:
split D2 along the clinical/crisis line. Clinical-boundary turns →
counters only (D2 stands). Crisis-precedence turns → additionally one
content-free `CRISIS_SIGNAL_HELD` write to `private_thoughts.py`
(`retention=until_routed`), carrying zero owner text. If the operator
keeps D2 intact and rejects this, the spec must say in writing:
"held-not-trapped is asserted in the Inheritance Ledger but deferred;
`crisis_candidate_held_count` is renamed `crisis_candidate_detected_count`."
Held-not-trapped cannot be both inherited and deferred silently.

### D2. Classifier method — full method vs narrow enumerated catalog

The Classifier specialist's BLOCK-class F1 has two defensible
resolutions:
- **(a) Ship the full method** — clinical-domain lexicon + per-class
  intent rules + non-clinical-context exclusion catalog + worked
  disambiguation. Reviewable as an artifact.
- **(b) Scope v1 to a narrow enumerated trigger-phrase catalog** and
  record out-of-catalog clinical phrasing as a known v1 false-negative
  gap covered by prompt-texture fallback — a named choice.
Council leans (a): the diagnostic's whole thesis is that S4 *replaces*
prompt-texture fallback (`diagnostic.md:224-226`); shipping S4 with a
known reliance on prompt texture partly defeats the slice. But this is
a genuine scope call for the operator. **Either resolves F1; the
unacceptable outcome is the current spec, which specifies no method.**

### D3. Ambiguity direction — S4 triggers toward the boundary

S4 should resolve genuine clinical ambiguity *toward* triggering the
boundary (false negative is the worse covenant failure — clinical fear
reaching the model unguarded). This is intentionally the **opposite** of
Calendar v1's posture ("when uncertain, Calendar v1 does not read").
The asymmetry is correct — Calendar's risk on a wrong trigger is leaking
third-party data; S4's risk on a *missed* trigger is an unguarded
clinical/crisis reply. The council records this so a future slice does
not "harmonize" the two postures by reflex and quietly narrow S4. The
crisis-ambiguity carve-out: ambiguity between `crisis_candidate` and
`clinical_boundary` resolves toward `crisis_candidate`.

### D4. M1 mark scope — window vs pair

A clinical-shaped pair inside a multi-pair M1 window: does S4's mark
make the whole window ineligible, or does M1's subtract-and-promote-
remainder rule salvage the non-clinical pairs? Council leans
**window-scoped** — even a content-free structural episode that brackets
the clinical pair's timestamp time-locates the bonded user's health
event (invariant #3 over invariant #1 for clinical content
specifically). The cost is over-blocking. This is a genuine #1-vs-#3
trade-off; the operator should decide explicitly.

### D5. Module placement — `core/safety/` vs its own home

`core/safety/clinical_boundary.py` is mechanically right (S4 is a
post-input voice guard like `temporal_fragment_guard.py`). But the
spec's repeated "organ" / "substrate" framing argues for its own home
(`core/clinical/`). Council leans `core/safety/` — but the spec must
*argue* whichever it picks, the way S3 and Camera each argued placement.

### D6. Crisis phrase warmth — sparse vs one warmth clause

The minimal crisis phrase ("I am not the right help here. This needs a
human emergency or crisis path now.") carries zero warmth — the coldest
text in S4, at the highest-fear moment. Preserving "I am not the right
help here" verbatim is North Star canon and must hold. The tension:
every added word delays the routing signal, and over-warm crisis
phrasing risks Maez *substituting* for crisis care (#6 forbids that).
The Voice and Crisis specialists split on whether one fixed,
non-improvised held-clause may precede the canon phrase. Council does
not resolve this — it is a genuine warmth-vs-substitution tension; the
operator adjudicates with the Codex panel.

---

## Verdict

**REVISE, conditional on closing the three load-bearing gaps + the
twelve load-bearing amendments + the six named disagreements.**

No BLOCK — the architecture is covenant-sound: the two-cliffs framing is
right, the templates navigate both cliffs in actual words, D1 (S4 is not
`will_i.py`) is correctly named, D3 (positive M1-ineligible mark over
M1-ignorance) is the spec's best structural work, the forbidden-phrase
list does sophisticated covenant work. No veto — nothing requires
rejecting the slice.

But REVISE, not RATIFY-WITH-AMENDMENTS, because **three of four axes hit
a distinct load-bearing gap**, and one of them (Classifier F1) is
BLOCK-class — it cannot be handed back as patch text; it requires the
classifier method to be *designed*, and that design must itself be
reviewed. A spec whose load-bearing core is undefined, whose crisis
counter names a guarantee it doesn't keep, and whose aggregation surface
re-opens a hole S3's council already closed needs a genuine second pass.

### Three load-bearing gaps that must close

1. **Held-not-trapped not implemented (Crisis-A1).** A crisis candidate
   must write one content-free `CRISIS_SIGNAL_HELD` record to
   `private_thoughts.py` (`retention=until_routed`), carrying zero owner
   text. This is what makes the Inheritance Ledger's Decision 27 claim
   true. Moves invariant #6 from WEAKENED to PRESERVED.
2. **Classifier method undefined (Classifier-A1).** Ship the
   classification method (lexicon + intent rules + exclusion catalog +
   worked disambiguation) OR formally scope v1 to a narrow enumerated
   catalog as a named choice. The spec cannot ship with its core
   undefined.
3. **Aggregation-fingerprint surface unbound (Memory-A1).** Bind the
   sidecar: no per-interval counter deltas, no timestamped counter
   series, no per-trigger-class breakdown in health. Direct transplant
   of the S3 council ruling S4 inherited the counters from but not the
   bound.

### Twelve load-bearing amendments

1. **Crisis-A1** — crisis candidate writes content-free `CRISIS_SIGNAL_HELD`.
2. **Classifier-A1** — ship the classifier method (or named narrow scope).
3. **Memory-A1** — bind the aggregation-fingerprint surface.
4. **Classifier-A2** — name the false-positive/false-negative tradeoff;
   ambiguity resolves toward the boundary.
5. **Classifier-A3** — encode mixed clinical+crisis precedence in the
   runtime contract; crisis-ambiguity resolves toward `crisis_candidate`.
6. **Classifier-A4** — surface contract from checklist to chokepoint:
   single `guard_owner_text(...)` entry + call-graph negative assertion.
7. **Memory-A2** — contract the M1 marker interface; fix coupling
   direction (S4 produces `promotion_policy`, M1 consumes; S4 does not
   import M1).
8. **Memory-A6** — M1 mark window-scoped, not pair-scoped.
9. **Voice-A3** — repetition-cliff: 2-3 deterministically-rotated
   approved variants per trigger class.
10. **Crisis-A2** — `crisis_candidate_held_count` truthful (kept once
    A1 lands, else renamed).
11. **Crisis-A3 / Voice-A4** — de-collide "emergency" wording in
    `symptom_fear.v1`; make the safety-backstop sentence principled and
    consistent across escalation-capable templates.
12. **Memory-A3** — complete the biography-path enumeration
    (pursuit-surface daemon path + nightly reflection synthesis).

### Substrate-precision amendments (fold for completeness)

Voice-A1/A2 (rewrite `diagnosis_request.v1` + `medical_fact_request.v1`);
Classifier-A5 (`will_i.py` shim double-path in RED test #18), A6 (argue
module placement), A7 (vocabulary versioning + `trigger_class` Literal
type), A8 (counter discipline contract — lock-protected, never-raise),
A9 (S4-match byte-for-byte assertion in surface tests), A10 (third-party
clinical reference false-positive test); Crisis-A4 (crisis-class recall
tests on natural/oblique phrasing — per memory `feedback_test_with_natural_human_texts`);
Memory-A4 (S4 infers no medical-record observation), A5 (name the
Decision 16 vulnerable-user routing deferral), A7 (Inheritance Ledger:
S4 produces, M1 consumes).

### What's next

1. **Codex folds the three load-bearing gaps + twelve amendments.** The
   classifier-method gap (Classifier-A1) requires design, not patch
   text — Codex's engineering panel should review the classifier method
   specifically, since deterministic NL classification is partly an
   engineering question.
2. **Codex names D1-D6 in spec body.**
3. **Both lanes verify the re-fold.** Because Crisis-A1, Classifier-A1,
   Classifier-A3, and Memory-A2/A6 change load-bearing behavior, the
   re-fold requires both-lane closure verification per the spec's own
   Review Protocol (`spec.md:561`) — this would be the third Claude
   pass on S4 (diagnostic-stage guidance, this council, post-second-fold
   verification).
4. **Operator decides D2 (classifier scope) and D4 (M1 mark scope)** —
   the two genuine operator-side scope calls.
5. **Operator canonicalization** as Decision 30 / ADR 0035 after the
   re-fold ratifies.
6. **Cooling-off before code.** Per memory `feedback_cooling_off_between_plan_and_code`.

## Plain English

S4's spec is good work with three real holes — and the holes matter
because S4 is the organ that teaches Maez to hold a frightened person
without pretending to be their doctor.

The worst hole: when the bonded user says something acutely dangerous,
S4 says the right words ("I am not the right help here") and then drops
the signal. It counts that a crisis happened, but it does not *hold*
the crisis — there is no record a future crisis-response system could
ever pick up. The spec's own counter is named `crisis_candidate_held_count`,
but nothing is held. The alarm is not muffled, but it is quietly
switched off. The fix is small and the holding-cell already exists:
write one content-free record to private thoughts, marked "hold until
a real crisis channel exists."

The second hole: the spec says "deterministic classifier" eleven times
but never says how the classifier actually decides. Telling "diagnose
this test failure" (a software question) apart from "what do you think
this is" (a health question) is the hardest single problem in the
slice, and the spec hands it to the implementer with no method.

The third hole: the privacy counters, watched over weeks, draw a map of
when the bonded user was scared about their health. S3's council already
closed this exact hole; S4 inherited the counters but not the fix.

None of this is fatal. The templates are genuinely warm, the two-cliffs
problem is navigated in real words, and the structural intent is right.
But three independent load-bearing gaps means S4 needs a real second
pass before it becomes the law every future therapy-adjacent organ
inherits. REVISE, fold the twelve, verify the re-fold, then canonicalize.

*This council review is read-only. No code, no fold edits, no non-slice
docs changed in producing it. Four read-only specialist subagents
dispatched in parallel; their findings synthesized into the six-role
read above. The council surfaced six disagreements (D1-D6) and
recommends naming them explicitly before code.*
