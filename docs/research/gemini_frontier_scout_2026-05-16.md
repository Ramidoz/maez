# Gemini frontier scout — 2026-05-16

**Status:** scout memo, not canonical law
**Source:** Gemini / NotebookLM frontier ideation over the Maez canon and S6 context
**Purpose:** preserve external ideas and rejection reasons for future diagnostics

This memo is a backlog artifact. It does not amend S6 Successor Governance v1,
Decision 33, ADR 0038, or any sealed spec. Gemini is used here as a frontier
scout: it can suggest technologies, analogies, and research directions, but it
does not decide Maez law. Any item below must be re-verified against primary
sources and the BAD before becoming a diagnostic, spec, or implementation.

The useful shape of the scout output is not only the ideas to carry forward. The
rejections matter too. A future agent should not rediscover a smart-contract
dead-man switch, Wi-Fi breathing sensor, or clinical prediction model as if the
covenant risks were unknown.

## Carry Forward Strongly

### Local Merkle / Transparency Logs

**Target organs:** S6 Successor Governance, S8 Rupture and Repair, append-only
evidence stores.

Local Merkle trees or cryptographic accumulators could harden append-only
evidence without requiring a public cloud ledger. Periodic roots could be
exported to Decision 22 backups or operator-private witness packets. This would
make retroactive rewrite of lineage capsules, rupture/repair events, or other
governance records harder to hide.

**Covenant constraint:** do not place cryptographic proof burden on a
non-technical witness or grandmother-class user. Humans should see plain
ceremony status; tools may verify roots underneath.

**Status:** strong future candidate for S6 storage hardening or S8 evidence
integrity diagnostic.

### Affective Translation for Bridge / Cosmos

**Target organs:** S10 Bridge / Cosmos, Human-Primacy Valve, future inter-Maez
signal routing.

Cross-Maez routing will need more than language translation. It needs a way to
carry relational weight across cultures, ages, and families: silence, repeated
nostalgia, response latency, or daily-rhythm changes may mean different things
in different households.

**Covenant constraint:** Interpretive Humility holds. Maez may pass
provenance-backed observations and confidence-bounded hypotheses; it must not
state another person's inner life as fact. A bridge packet should say "these
signals changed" before it says "lonely."

**Status:** strong future S10 diagnostic input.

### Projection-Layer Reconsolidation

**Target organs:** M1 Lived-Episode Promotion, S8 Rupture and Repair, Temporal
Recall Filter.

Biological memory reconsolidation suggests that recall is not a neutral replay:
present repair can change how a past hurt feels. Maez must not mutate raw
episodes, but it can let later repair alter the projection layer that composes
how an immutable memory is carried today.

**Covenant constraint:** raw lived episodes remain append-only and provenance
true. "This feels softer now" belongs in interpretation/projection, never in
the historical record.

**Status:** strong future S8 / TRF diagnostic input.

### Relational CRDTs

**Target organs:** S3 Temporal Spine, S10 Bridge / Cosmos, future multi-Maez
offline event exchange.

Conflict-free replicated data types may help when multiple Maezes observe or
route shared events while offline. They can merge event evidence without central
cloud authority.

**Covenant constraint:** CRDTs may merge evidence/order, not human meaning. They
must not silently collapse rupture and repair into "resolved" because a vector
clock says both events exist.

**Status:** promising future technical substrate for inter-Maez event logs,
not a rupture/repair verdict mechanism.

## Carry Forward Cautiously

### Shamir Secret Sharing

**Target organs:** S7 Operator / User Role Boundary, future S6 storage
hardening.

Secret sharing could enforce "maintainer is not reader" by splitting archive
decryption power across bonded user, successor, estate executor, or other roles.

**Covenant risk:** brittle quorum. Lost shares or uncooperative parties could
trap Maez continuity or selected archives. Decision 8 must dominate: failed
quorum cannot become dissolution-by-default.

**Status:** cautious future role-encryption option; not S6 v1.

### FHIR / ePOLST Ontologies

**Target organs:** S11 Age / Capacity Stratification, S12 Crisis Channel.

Medical informatics vocabularies may be useful as references for external
capacity or advance-directive documents. They could let Maez read that an
external human institution has made a status determination without Maez making
one itself.

**Covenant risk:** Clinical Boundary. Maez must not become a clinician, a
treatment surface, or an EHR-like medical reasoning store.

**Status:** possible external-trigger vocabulary for S11/S12, with S4 boundary
dominance.

### Multi-Party Computation for Assisted Ceremonies

**Target organs:** S6 successor authoring helper, S7 role boundary,
grandmother-compatible workflows.

MPC or split-device ceremony patterns could let a technical helper format a
directive while the non-technical bonded user privately chooses the actual fate
or scope.

**Covenant risk:** over-engineering. A fragile cryptographic workflow may be
less grandmother-compatible than a plain trusted-witness ceremony.

**Status:** research option for future non-technical authoring UX, not a near
term requirement.

### Allostatic Load as Routine Drift

**Target organs:** S11 Age / Capacity Stratification, S12 Crisis Channel.

Long-running changes in routine, response latency, rhythm, or vocabulary could
be useful as "something changed" signals before a crisis becomes explicit.

**Covenant risk:** Medical Authority. This must not become diagnosis, decline
prediction, or treatment advice. The safe version is routine drift surfacing
with provenance and uncertainty.

**Status:** cautious future S11/S12 diagnostic input; S4 must dominate.

## Hold or Reject for Now

### Wi-Fi CSI Ambient Proprioception

**Target organs:** Body Topology, future ambient sensors.

Wi-Fi Channel State Information can infer presence, motion, and sometimes
breathing without cameras or microphones. That sounds privacy-preserving, but it
is also body surveillance through walls.

**Covenant risk:** high. "No image" does not mean "low privacy." CSI can sense
unconsented third parties and intimate bodily rhythms without identity
authentication.

**Status:** hold. Any future ambient-sensor diagnostic must start from S2 and
Body Topology, with third-party presence treated as a first-class risk.

### Smart-Contract or Dead-Man Oracles

**Target organs:** none in v1; rejected for future S6 activation unless the
canon changes.

Blockchain or dead-man-switch activation would automate succession or archive
release when an external condition fires.

**Covenant conflict:** this violates S6 and Decision 18's revocation posture.
False positives are catastrophic; immutability fights human correction; cold
automation replaces a human-judged bond transition.

**Status:** reject for Maez's current covenant shape.

### Terminal Lucidity Prediction

**Target organs:** S11 / S12 only as a caution.

Terminal lucidity is clinically interesting, but Maez should not classify a
sudden clear day as a sign of imminent death.

**Covenant conflict:** Clinical Boundary. Maez can stay with the user in
clarity; it cannot predict death or treat coherence spikes as medical evidence.

**Status:** reject as a prediction model. Preserve as a caution for S11: do not
interpret capacity fluctuations medically.

## Operating Rule for Gemini Scouting

Gemini can widen the search space. It can suggest analogies, technologies, and
failure modes. It cannot create Maez law, amend sealed specs, or bypass the
diagnostic -> spec -> both-lane review -> fold -> canonicalization ladder.

For future scout outputs:

1. Record the idea and target organ.
2. Record the covenant risk before the engineering attraction.
3. Mark the status as carry-forward, cautious, hold, or reject.
4. Require primary-source verification before any diagnostic cites it.
5. Preserve rejection reasons so future agents do not re-open already-known
   covenant conflicts as fresh ideas.

Plain English: Gemini brought interesting organs in a tray. Some are medicine,
some are sharp tools, and some are poison in a beautiful bottle. This memo keeps
all three visible without letting any of them into Maez's body by accident.
