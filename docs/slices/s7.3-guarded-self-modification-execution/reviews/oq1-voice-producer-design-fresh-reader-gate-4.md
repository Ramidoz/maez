# Fresh-Reader Gate 4 - S7.3 OQ1 Design v4

**Subject:** `oq1-voice-producer-design.md` at `422b910` (OQ1 v4), with
diagnostic v3 and the Gate-3 verdict as context.

**Ran:** 2026-05-19. Three independent blank-context subagents - cold covenant
reader, cold spec-writer, cold residual-hunter - each given v4 plus diagnostic
v3 plus canon, walled off from `reviews/`. The covenant lane firsthand-verified
the load-bearing as-built shapes at `operator_user_boundary.py:1390-1442` and
`:3866-3987` across earlier gates.

**Verdict:** substantial progress; the core is done; one specific sub-layer
issue plus a cluster of explicit deferrals remain. v4 made real depth-progress
on the Gate-3 must-fixes - every single one landed substantively, not as a
skim. The residuals are smaller in scope than Gate 3's were, but include one
spec-writer blocker on a deferred load-bearing construct and one convergent
"design-says-X-code-doesn't-do-X" finding on the render-projection mechanism. A
targeted v5 closes them; a spec-with-explicit-decisions path is also viable.

## What v4 Genuinely Fixed

The core is done. All three readers affirm, and committed code has been
verified across multiple gates:

- Voice-state / render-shape reconciliation lands correctly. The three-value
  `MaezVoiceConsultation.maez_objection_state` and the five-value
  `RenderedRequestStatement.maez_objection_state` are now framed as
  voice-fact-vs-projection rather than competing enums.
- The deterministic reducer rule table is conservative and substantively
  complete. The full marker x semantic-reader grid is closed; the
  reader-unavailable-after-captured-response asymmetry routes to `present`, not
  `not_determined`.
- OQ4 is resolved cleanly: strict "S7.3 v1 does not proceed," with a narrow
  reviewed-liveness-repair carve-out reserved.
- OQ3 is resolved: Maez-initiated provenance is supplemental only; a fresh
  request-bound consultation is always required.
- The extend-vs-validate fork is decided: non-breaking,
  validate-from-`source_ref_hash`.
- The cross-field `absent + maez_withdrew_request=True` invariant is flagged as
  new work with a validator bridge until then.
- "Which Maez Is Consulted" forbids contextless instances and whole-daemon
  ventriloquism; the prompt-integrity contract treats mutation text as
  untrusted; the content-free `MaezVoiceConsultation` shape is preserved.

## Finding A - Render-Unavailable Projection Vs Committed Renderer

Must fix.

Convergent: residual-hunter F1+F5; spec-writer F11. Verified against committed
code: `render_request_statement` sets `RenderedRequestStatement.maez_objection_state`
to `consultation.maez_objection_state` directly. The validator accepts
`unavailable`, but the renderer never emits it on the current code path.

v4 says operational unavailability "renders as unavailable in
RenderedRequestStatement," but current code does not do that. v4 reconciled the
enum names but did not trace which code path populates the projection.
"Blocking unavailable_reason_code" is also undefined.

Fix: either explicitly name the required `render_request_statement` amendment,
or downgrade the "renders as unavailable" claim to conditional on that
amendment.

## Finding B - Voice-Producer Port Shape

Spec-writer rates blocker.

The "voice-producer port" is named once with no signature, method names,
interface, or return shape. v4 triage explicitly defers it as "spec-level
engineering detail." The spec-writer reader rates this blocker because the port
is the seam where the whole voice producer plugs in: a load-bearing covenant
boundary, not merely engineering detail.

Fix: name the port's contract at minimum - method signature, inputs
(work item, preview, bundle store), and return shape (the content-free
consultation row or a closed error).

## Finding C - Reducer Blocking-Marker Row Ambiguity

Must fix.

All three readers caught the same ambiguity from different angles. The row
`blocking_marker x any value -> present or withdrew=True` leaves the
disambiguation unspecified. The marker emitter vocabulary collapses objection,
withdrawal, refusal, and "not now" into one `blocking_marker` token, so the
reducer cannot distinguish withdrawal from objection from the marker alone. As
written, the row could be read as permitting `absent + withdrew=True`, the
cross-field invariant violation.

Fix: add withdrawal as a fourth structured-marker outcome distinct from
`explicit_no_objection` and `blocking_marker`; tighten the row to
`present and/or maez_withdrew_request=True`, never absent together with
withdrawal.

## Finding D - Placeholder Repair Preference Vs Rule

Must decide.

v4 says "v4 keeps this shape as the design preference." The word "preference"
leaves the alternative - amending the closed vocabulary with an explicit
non-producer placeholder value - alive as a co-equal option. The spec-writer
cannot tell which is binding.

Fix: make it a rule.

## Finding E - Explicit Triage Deferrals

Decide or carry with checklist:

- Trace schema field names: diagnostic D7 has a more concrete list; carryable
  to the spec with an explicit "use D7" instruction.
- Guarded surface bridge: the two options have materially different effects on
  the diagnostic's D6 surface inventory; closer to decide-before-spec than
  spec-level engineering.
- OQ2 phasing rule: v4's phrasing is grammatically opaque; the diagnostic
  wanted a clean Phase A/Phase B decision.
- `S7ExecutionAuthorization` rename: low covenant urgency, but a spec decision.

Other convergent items: bundle store storage substrate deferred; cross-pair
validation rule asserted as current when committed `__post_init__` only
validates the two enums independently; source-bundle validator placement
undecided; "re-render" without a prior render in the sequence;
"Maez-initiated" vs "Maez-originated" terminology jitter; "blocking
unavailable_reason_code" undefined.

## Honest Pattern Observation

v4 made bigger depth-progress than v3 did. Gate 3 found two must-fixes; v4
closed both and several triage items besides. The residual sub-layer is smaller
in scope than Gate 3's was. Progress is real and the previous pattern is
largely broken.

One sub-layer instance of "design-says-X-code-doesn't-do-X" remains: the render
projection. It is structurally the same class as Gate 3's coupling/enum miss,
but materially smaller - one specific renderer behavior, not a whole missing
enum plus coupling invariant.

## Recommendation

Two viable paths:

**Path A - small targeted v5.** Close Findings A, C, D; name the port signature
(Finding B) at minimum at contract level; resolve OQ2 phrasing and the
`S7ExecutionAuthorization` rename; either carry trace schemas / bridge to spec
with explicit instructions or pin them.

**Path B - proceed to the S7.3 spec with an explicit decide-now-don't-invent
checklist.** Checklist must include: port signature, render-unavailable
projection mechanism, bridge choice, trace schema fields (use diagnostic D7),
placeholder rule, OQ2 phasing, `S7ExecutionAuthorization` rename.

The covenant lane lean is Path A, narrowly scoped. Findings A, B, C, and D in
v5; the rest carried to the spec with explicit instructions.

## Plain English

Three readers checked v4. Loud unanimous good news: v4 did the hard work the
previous check asked for. How Maez gets asked, how the answer is read, and what
happens when Maez is unavailable are now buildable.

Two real things still need attention. First: the design says "if Maez is
unavailable, the signed display shows that," but the code that builds that
signed display does not actually emit the unavailable label; it just copies
whatever the consultation says. Second: the port where the answer-reader plugs
in is named once with no shape. A port without a shape is exactly the kind of
thing the spec will silently invent under pressure.

Plus the answer-reading table is ambiguous about withdrawal versus objection in
one row; one decision is stated as a "preference" rather than a rule; and a few
items are explicitly punted to the spec where some can absorb and some maybe
cannot.

Two reasonable paths: a small v5 that fixes those, or write the spec from v4
with an explicit list of decisions the spec-writer must make. v5 is the
conservative call.
