# Recall-Axis Dispatcher — Codex Engineering Pass-1 Review: Peirce

## Verdict

RATIFY-WITH-AMENDMENTS

## Findings

### Blocking
None

### Major
- **M1. Repair specs are not actually closed under the legal product table**
  - Evidence: §6.5 says the legal `(CompositionHint × ProvenanceFraming)` table is closed and “growth via spec amendment” (lines 367–380), but `REPAIR_INHERIT_PRIOR_SPEC` is defined as “inherits prior spec's framing, modulo Layer 2 re-evaluation” (line 378). D11 then says outside-table pairs are refused at construction (lines 438–440).
  - Engineering consequence: the constructor cannot deterministically validate repair specs. “Modulo re-evaluation” is not a closed legal cell; it lets Layer 2 produce any framing without a table-verifiable rule.
  - Closure criterion: v1.2 must either enumerate every legal `REPAIR_INHERIT_PRIOR_SPEC × ProvenanceFraming` pair, or require Layer 2 to resolve repair turns into a concrete non-repair `CompositionHint` before `CompositionSpec` construction/validation.

- **M2. Caller-supplied verdict refusal only tests `composition_hint`, not the full forbidden verdict surface**
  - Evidence: D6 forbids non-owner callers from supplying final `composition_hint`, `provenance_framing`, or source selections as authority (lines 416–420). R#9 only refuses caller-supplied `composition_hint` (line 488), and R#22 only blocks a `composition_hint` kwarg (line 502).
  - Engineering consequence: upstream code could still launder a verdict through `provenance_framing`, `substrate_sources`, or `external_sources` while passing the named tests.
  - Closure criterion: v1.2 must require RED tests proving `brain_loop`, Telegram/web handlers, and public dispatcher APIs cannot supply authoritative `composition_hint`, `provenance_framing`, `substrate_sources`, or `external_sources`; owner utterance lexemes and intra-Maez signals must remain evidence-only inputs.

- **M3. Refusal semantics are underspecified**
  - Evidence: §6 says runtime extension is refused (lines 293–297); D11 says incoherent pairs are refused at construction (lines 438–440); R#10 and R#16 test refusal (lines 489 and 496). No section defines the refusal object, reason code, audit path, or whether execution halts.
  - Engineering consequence: implementers may raise raw exceptions, silently coerce to defaults, fall back to JARVIS, or produce partial specs. Any of those could satisfy “refused” locally while violating dispatch behavior.
  - Closure criterion: v1.2 must define a typed refusal path, e.g. closed `DispatcherRefusalReason`, no downstream JARVIS/tool/fetch execution after construction refusal, and an audit/logging expectation for unknown vocabulary and incoherent legal-product failures.

- **M4. `inventory_witness` contradicts the declared v1-minimal `CompositionSpec` schema**
  - Evidence: §4 declares a four-field `CompositionSpec` and says the four-tuple is v1-minimal (lines 152–163). D2 requires UNKNOWN inventory cases to emit hybrid spec carrying `inventory_witness: UNKNOWN` (lines 392–395).
  - Engineering consequence: schema validation and constructor tests cannot know whether `inventory_witness` is legal, required, or an ad hoc extra. This invites caller-supplied or optional metadata drift at the exact place D2 is trying to prevent verdict laundering.
  - Closure criterion: v1.2 must make `inventory_witness` an explicit field with closed values, or define it as metadata nested under an existing field with constructor-owned production and tests for PRESENT / ABSENT / UNKNOWN.

- **M5. RED tests still allow enum-existence passing without behavioral proof**
  - Evidence: R#10 tests unknown vocabulary value refusal (line 489), R#16 tests incoherent pair refusal (line 496), R#21 is explicitly “spec-level anchor; concrete test refined during implementation” (line 501).
  - Engineering consequence: tests can pass by checking enum constructors or static membership while the real turn path still accepts serialized bad values, coerces unknowns, or renders an answer after refusal.
  - Closure criterion: v1.2 must require behavioral RED tests at the serialized/public boundary and the reply path: bad vocabulary and incoherent pairs must prevent spec construction, prevent downstream fetch/recall/render, and produce the specified refusal/audit result.

### Minor
- **m1. `FRONTIER_CONSULT` should be non-executable in tests, not merely labeled**
  - Evidence: `FRONTIER_CONSULT` is listed as `ExternalSource` (lines 320–326), D10 says it grants no tool access (lines 435–436), and R#13 checks no capability grant (line 493).
  - Engineering consequence: a label-only enum can still accidentally map to a tool executor later.
  - Closure criterion: v1.2 should require the executor registry to refuse or omit `FRONTIER_CONSULT` until G3 exists, with a test that no callable/tool binding exists.

- **m2. Closed vocabulary growth path names ADR 0046 but not the implementation contract**
  - Evidence: §6 says new values enter via maintenance-proposal substrate (lines 295–298), and R#10a points at `core/policies/maintenance_proposals.py` (line 490).
  - Engineering consequence: implementers may test only that the module is touched, not that unratified values stay refused.
  - Closure criterion: v1.2 should require one negative test for an unratified proposal and one positive fixture for a ratified/sandbox-witnessed proposal, if dynamic growth is in v1 scope.

### Nit
- **n1. Typo in D2 weakens the invariant wording**
  - Evidence: “D2 must not laundering...” (line 398).
  - Engineering consequence: none mechanically, but this sentence is load-bearing and should read cleanly.
  - Closure criterion: change to “D2 must not launder...”

## Summary

v1.1 is directionally buildable, but Peirce’s lane needs a tighter refusal contract before implementation. The main issue is not the vocabulary set itself; it is proving that only the dispatcher’s own constructor can produce verdicts, that illegal values fail closed, and that tests exercise the real turn path rather than enum membership.
