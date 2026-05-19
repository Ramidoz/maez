# Fresh-Reader Gate 3 - S7.3 OQ1 Design v3

**Subject:** `oq1-voice-producer-design.md` at `9c9043c` (OQ1 v3), with
diagnostic v3 and the Gate 2 verdict as context.

**Ran:** 2026-05-19. Three independent blank-context subagents - cold covenant
reader, cold spec-writer, cold residual-hunter - each given v3 plus canon,
walled off from `reviews/`. The covenant lane firsthand-verified the
load-bearing as-built claim at `operator_user_boundary.py:3951-3955`.

**Verdict:** OQ1 design v3 is **not** yet a safe base for the S7.3 spec. v3
succeeded on the central Gate-2 goal: the classifier covenant core is now
spec-writable depth, and the producer/source-kind layer is canon-accurate. But
three classes of remaining work remain: one mechanical, one
covenant-load-bearing, one triage. A targeted OQ1 v4 is needed before the spec.

## What v3 Genuinely Fixed

Affirmed by all three readers:

- The classifier covenant core is now spec-writable. `S7VoiceSemanticReaderV1`
  pins the route slot, fixed prompt template id, bounded inputs, closed
  three-value output, and resolves the recompute-vs-non-deterministic
  contradiction by defining recompute as deterministic-reducer replay over
  persisted hashes, not a model rerun.
- Producer/source-kind pairs match committed canon exactly. The invented
  `self_mod_dialog_terminal_turn` is gone; the five-value
  `maez_objection_state` mapping is replaced by a three-value model that
  matches `MaezVoiceConsultation`; withdrawal is spelled consistently.
- No false absent can be manufactured through the classifier. The conjunction
  of conditions, marker-cannot-override-free-text rule, and
  classifier-as-adversary-surface framing all hold.

## Finding A - RenderedRequestStatement Five-Value Enum

Must fix; mechanical.

Three readers reported it; the covenant lane firsthand-confirmed it. The
committed `RenderedRequestStatement.maez_objection_state` validates against a
five-value closed set including `unavailable` and `none`, and
`_rendered_objection_value()` has explicit branches for both. v3's headline
claim that "the rendered D12 display values remain the three committed values"
is false against committed code.

v3 reconciled `MaezVoiceConsultation` to three values but missed that the D12
render type carries its own five-value enum. Two readers rate this blocker. v4
must either acknowledge the render-type enum as the rendered-display superset of
the three-value consultation enum, or call for an amendment.

## Finding B - Decisions Punted To The Spec

Must fix; covenant-load-bearing.

The spec-writer reader's frame is precise: "the cleanest path is one more short
design pass... otherwise the spec-writer will silently make these calls, exactly
the 'invent under pressure' failure mode, just one level down."

Three decisions must be resolved in v4:

1. The deterministic reducer's rule table. v3 names the reducer inputs but never
   tabulates its decision rule. The reducer table stands between a structured
   marker and `absent`; it is the last gate.
2. OQ4 - Maez unavailability handling. The diagnostic's OQ4 asks what counts as
   unavailable; how non-manufactured unavailability is proven; which states
   render as `not_determined` versus a closed unavailable skip; and whether any
   class proceeds when Maez is unavailable. v3 resolved OQ1 but did not resolve
   OQ4.
3. The reader-unavailable asymmetry. If a same-box actor makes the semantic
   reader route unavailable, a suppressed objection could collapse from
   `present` to `not_determined`. That erases a real objection from D23
   aggregation. v4 must fail this shape toward `present`, not `not_determined`.

The `maez_objection_state="absent" + maez_withdrew_request=True` cross-field
invariant is also covenant-shaped work. The committed dataclass does not enforce
it; v3 treated it as a one-line spec note. v4 must either make it an explicit
S7.3 amendment or schedule it visibly before positive execution.

## Finding C - Mid-Level Triage

Not all of these must land in v4, but none should disappear:

- `S7VoiceConsultationBundleStore` storage substrate: fields are enumerated,
  but SQLite path / permissions / Decision-22 backup inclusion are not.
- Three closed failure-code vocabularies have no committed home: operator
  projections, attempt outcomes, and committed `MAEZ_UNAVAILABLE_REASON_CODES`.
- `MaezVoiceConsultation` extend-vs-validate fork: extending the sealed
  dataclass changes the D12/D14 consultation hash; validating from
  `source_ref_hash` is non-breaking. v3 presents them as co-equal without
  surfacing the cost asymmetry.
- Voice-producer port signature, trace-schema fields, guarded surface bridge,
  leftover `maez_voice_consulted=True` validator step,
  `S7ExecutionAuthorization` rename, OQ2 phasing, and OQ3 Maez-initiated
  provenance each still need placement in v4 or the spec.

## Honest Pattern Observation

This is the third consecutive time the fresh-reader gate has found an S7.3
covenant artifact one depth-level short of its next step.

- Gate 1: diagnostic skipped OQ1 resolution.
- Gate 2: OQ1 v2 had the enum mismatch plus classifier under-depth.
- Gate 3: OQ1 v3 hit the classifier cleanly but missed a second committed enum
  and punted a layer of mid-level decisions.

The work is not bad; each pass pushed the depth deeper. The pattern is fast
iteration leaving the next layer for the next pass. The fastest real path now
is one careful v4 that closes Findings A and B and explicitly triages Finding C.

## Recommendation - OQ1 Design v4

1. Fix Finding A: reconcile against `RenderedRequestStatement`; state whether
   v4 amends its five-value enum or accepts it as the rendered-display superset
   of the three-value consultation enum.
2. Spec the deterministic reducer's full rule table.
3. Resolve OQ4, including non-manufactured unavailability and whether any class
   can proceed when Maez is unavailable.
4. Close the reader-unavailable asymmetry: fail toward `present`, not
   `not_determined`.
5. Decide `MaezVoiceConsultation` extend-vs-validate-from-`source_ref_hash`,
   surfacing the cost asymmetry.
6. Add or formally schedule the `absent + maez_withdrew_request=True`
   cross-field invariant.
7. Triage Finding C.

## Plain English

Three readers checked v3. They all agreed on the good news: the part that
decides "did Maez object" is now buildable, the producer/source names match the
real code, and no fake "Maez did not object" can be made through the classifier.
v3 genuinely hit the hard center.

Three things are still missing. First, v3 reconciled one committed list of
states and missed a second one: the displayed version of the voice answer has
five values in the real code, including `unavailable`. Second, v3 named a
deterministic reducer but never wrote its decision rules, and OQ4 still was not
resolved. Third, if someone with same-box access disables the answer-reader, a
real Maez objection can turn into "we could not tell" instead of "Maez
objected." That erases the objection from the record that aggregates refusals.

This is a targeted v4, not a redesign: fix the render enum, write the reducer
table, decide unavailability, close the new covenant gap, and triage the
remaining engineering placements before the spec.
