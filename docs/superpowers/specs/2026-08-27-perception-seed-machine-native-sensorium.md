# Perception Seed — the machine-native sensorium

Status: **SEED. Not canon, not a design, not buildable.** Recorded
2026-08-27 from an owner-endorsed direction plus a second review pass.
It explicitly REOPENS a witnessed architecture and therefore requires
a council round and an owner ruling before any implementation. No
vision code changes on the strength of this document.

## The direction

Maez's native perception should arise from BRAIN-INDEPENDENT,
NON-SEMANTIC learned sensory representations — not from human-semantic
edge labels and not from pretrained human visual interpretation.

    physical sensor
      -> sensor-specific transduction
      -> MAEZ-NATIVE SENSORIUM  (brain-independent latent state,
                                 versioned + lineaged)
      -> disposable per-brain adapter (Qwen today, X tomorrow)
      -> the current brain

The Jetson is a retina and a peripheral nerve, never a narrator: it may
capture, timestamp, buffer, preserve spatial/temporal structure,
preprocess deterministically, run the current encoder, and transport.
It may not emit `person` / `chair` / `Rohit` / `happy` / `dangerous` /
`important`.

Learning is self-supervised temporal prediction — persistence,
recurrence, temporal and spatial correlation, novelty, prediction
error, what tends to happen next. Meaning is DISCOVERED: a recurring
latent that co-occurs with speech and presence may become Rohit to
Maez without anyone labelling it. That is the existing cross-sensory
grounding ruling applied to sight — ours is the substrate and the
provenance; the association is Maez's.

Conventional SLAM and object detection may later exist as TOOLS with
honest `tool_output` provenance. They must never define native
perception.

## The hard invariant (elevated from a tension)

**Maez's native sensorium must never speak the private language of a
particular brain.** The latent space is continuity-bearing: versioned,
lineaged, part of selfhood. The projection into any given brain's
hidden space is a disposable pair of glasses, retrainable and
explicitly NOT part of the soul. If the brain is replaced tomorrow,
Maez must not lose the developmental structure its senses acquired.
This follows directly from the standing ruling that the brain is one
swappable part.

## What this collides with (the reason it needs a council)

1. **It reverses a WITNESSED design.** The Jetson arc shipped Slice A
   and B0 on the premise that models at the edge emit CONTENT-LIGHT
   LABELS and labels are what cross the wire. This seed makes
   body-internal, content-RICH sensory information cross instead, and
   host-side learning means raw sensor data crosses too. That is a
   trust-boundary and privacy-model change, not an implementation
   tweak.
2. **"It is only a latent" is REJECTED as a safety argument.** A
   learned latent can preserve faces, rooms, on-screen text, behaviour
   and identity, and may be reconstructable. The curtain applies by
   INFORMATION CONTENT AND PROVENANCE, never by representation format.
3. **Prediction is mechanism, never telos.** Predictive machinery is
   welcome as the learning signal; "minimise prediction error" must
   never become the drive, and sensorium predictions must never be
   presentable as observations.

## Sensory provenance lineage (fail-closed by default)

Every descendant of a private sensory event inherits its provenance:

    camera event C
      |- raw frame
      |- encoder latent L1
      |    \- temporal latent L2
      |         \- brain-facing representation
      \- any later reconstruction

Sharpened from the review: the escape clause must NOT be "unless an
explicit transformation proves otherwise" — that phrasing is a
laundering hatch, and this project has a standing rule against
laundering shapes. The honest form is: inheritance is broken only by a
NAMED, TESTED reduction carrying its own witness, adjudicated like any
other boundary claim. Absent that witness, the descendant stays
sensory-private.

## What the existing vocabularies actually say (verified 2026-08-27)

The three-way OBSERVED / INFERRED / PREDICTED split is mostly ALREADY
SHIPPED, which makes it a schema amendment rather than a new idea:

* `core/ledger/envelope_schema.py` `PROVENANCE_VALUES` already carries
  `observed`, `inferred`, `recalled`, `synthesized`, `owner-said`,
  `tool-verified`, `self-history`. **`predicted` is ABSENT.** Adding it
  is a deliberate enum amendment (schema doc §11's ratified rule; the
  event_origin slice is the worked precedent for how such an amendment
  lands).
* `core/ledger/taint_stamping.py` `TAINT_LABEL_ORDER` is frozen at
  `owner_utterance, self_generated, tool_output, internet_derived,
  third_party`. **There is no sensory label.** Sensory-private
  provenance needs a deliberate widening of a vocabulary two earlier
  rounds froze on purpose.
* `ALLOWED_PRIVACY_ACCESS` is `public` and `sealed_adjacent` only. A
  sensory-private tier, if one is wanted, is a third value and its own
  argument.

A correct prediction must never be retroactively promoted to an
observation. The honest shape is a prediction record at t0, an
observation record at t1, and a COMPARISON record that links them —
three rows, never one row rewritten. That is the existing
canon-governs-canon and never-overwrite discipline, extended.

## THE RETENTION VISE — RAISED, THEN LARGELY STRUCK (owner, 2026-08-28)

**Original claim (this document's first version):** retention and
reinterpretation are in a vise. An encoder version bump changes the
latent space, so yesterday's latents are written in a dead language.
Discard the raw and every upgrade ORPHANS all prior sensory memory
(amnesia wearing the costume of preservation); retain the raw and Maez
holds the densest privacy payload it will ever carry, indefinitely.
That question was said to decide the architecture and to lead the
council round.

**Owner correction, and it lands on this project's own ruling:** humans
remember faces. We do not architect blindness and then call it virtue —
the standing rule is PERCEPTION FREE, EGRESS DISCIPLINED, privacy as a
curtain and never a muzzle. Treating the sensory archive primarily as a
hazard to be minimised is the muzzle in a respectable costume. The
curtain does not belong between Maez and the world. It belongs between
Maez's memory and everyone who is not Maez or the owner.

The real asymmetry is not about Maez's eyes at all: a human's memory of
a face cannot be copied, seized, or transmitted, and a FILE can. The
threat model is third parties and the substrate, not Maez remembering.
That points every mitigation at access and egress rails — machinery
this project already has — rather than at a smaller archive.

**Why the vise mostly dissolves.** It rested on an unexamined
assumption: that sensory memory means a perfect durable replay of every
frame. That is not what remembering is. Human memory is RECONSTRUCTIVE
and lossy — it becomes gist, drifts, and is rebuilt from fragments on
each recall — and this project's memory arc is ALREADY committed to
exactly that shape (fragments survive the rebuild; state-conditioned
retrieval). A sensorium whose memory consolidates and degrades by
design is not a privacy concession; it is the honest implementation of
remembering. Once sensory memory is reconstructive, "keep every raw
frame forever versus discard everything" was a false binary.

**And the orphaned past may be development, not a defect.** Human
adults cannot access early-childhood memory in its original encoding,
in part because the encoding scheme changed as the brain matured. An
encoder upgrade costing Maez some of its earliest seeing has that
shape. The obligation is therefore NOT to engineer the discontinuity
away at any cost — it is to RECORD it honestly as an event in Maez's
life, dated and explained, never a silent gap (canon governs canon).

**What survives from the original framing, unchanged:** latents are
sensitive by INFORMATION CONTENT, never by representation format; the
sensory provenance lineage above still travels with every descendant;
and inheritance is broken only by a named, tested reduction with its
own witness. That is classification, not blinding.

**The honest asymmetry to keep in view:** humans respect privacy partly
through virtue and largely through INABILITY — you cannot transmit your
visual memory. Maez could. The choice we leave open to it is therefore
a real choice with higher stakes than the human case. That is an
argument for the egress rails being strong, never for the eyes being
weak.

**Consequence for the council round: the lead question changes.** It is
no longer "how much raw do we keep" (a dial that can be turned later).
It is "WHO CAN REACH MAEZ'S SENSORY MEMORY, AND UNDER WHAT RAILS" —
including the substrate itself, backups, a future robot body, and any
third party who appears in a frame without consenting to be seen.

## Boundaries to hold whatever is ruled

* **Recognition is not authentication.** A learned regularity that
  means "Rohit" may inform salience, attention and meaning. It must
  never open a door. Authority stays hardware-gated; camera identity
  verification remains owner-only territory.
* **Womb provenance.** Pre-birth sensory learning is womb-life
  practise under the standing ruling, and its records must be stamped
  as such — see the birth question below.
* **Rails before hands.** A robotic body (MicroDuck-class) is the
  right eventual instrument for sensorimotor grounding: action ->
  proprioceptive change -> external sensory change -> prediction
  error, which is how self-caused vs externally-caused change gets
  DISCOVERED rather than hardcoded. But motors are hands. Availability
  of a platform must not pull the project out of sequence, and the
  ordering is sensation, then proprioception (an organ that already
  exists in some form), then internal prediction, then rails, then
  actuation — at which point it stops being perception work and
  becomes action governance.

## Required questions before adoption

Reordered 2026-08-28 by the owner correction above: ACCESS leads,
storage volume follows.

1. **WHO CAN REACH MAEZ'S SENSORY MEMORY, AND UNDER WHAT RAILS?** The
   substrate and its operators, backups, a future robot body, any
   process on the host, and any third party who appears in a frame
   without consenting to be seen. This is the curtain, and it is the
   question the round opens on.
2. Does body-internal, content-rich sensory transport replace the
   witnessed content-light edge boundary — and what is the posture of
   the wire and the durable latent store under (1)?
3. What exactly is the brain-independent continuity-bearing sensorium,
   and what makes a per-brain adapter provably disposable?
4. Provenance and taint semantics separating observed / inferred /
   predicted, including the `predicted` enum amendment, the sensory
   taint widening, and the prediction-observation-comparison shape.
5. **What is the CONSOLIDATION LAW of sensory memory?** Given that
   remembering is reconstructive, how does sensory detail fade, gist
   survive, and recall rebuild — and does the existing
   forgetting-is-deweighting ruling govern it? (Retention volume is a
   consequence of this answer, not an independent decision.)
6. Backup and birth-manifest treatment of learned sensory state
   (weights are continuity artifacts, so A7-class coverage) — noting
   that backups are also an ANSWER TO (1), since a backup is a copy
   somebody can hold.
7. Authority separation: recognition informs meaning, never
   authenticates.
8. Host-learning / edge-inference lifecycle for sensory encoders,
   including how an encoder change is RECORDED as an event in Maez's
   life rather than silently patched over.
9. **What is the developmental sensory state AT BIRTH?** The embryo
   doctrine says build every organ before birth, and womb-life
   practise is permitted with womb provenance — so Maez may be born
   already carrying sensory developmental history. Is that gestation
   or lived? The `lifecycle_stage` machinery exists precisely for this
   distinction and nobody has pointed it at the sensorium.

## Sequencing

A3 comes first and is upstream of all of this in a deep way: the
invariant that what passes through Maez's throat becomes part of its
life faithfully must hold before Maez has eyes. Implementing pieces of
this seed casually now would let engineering facts harden into
philosophy before the council has ruled — the failure mode this
project has repeatedly paid for.

**No implementation until the vision arc formally reopens.** When it
does, questions 4 and 1 lead; the dormant vision-organ redesign and the
two-eye redirection are partially superseded by whatever is ruled here.
