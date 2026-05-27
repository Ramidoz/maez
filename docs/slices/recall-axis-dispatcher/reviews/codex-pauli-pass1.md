# Recall-Axis Dispatcher — Codex Engineering Pass-1 Review: Pauli

## Verdict

RATIFY-WITH-AMENDMENTS

## Findings

### Blocking
None

### Major
- **M1. `inventory_witness` is required but absent from the declared `CompositionSpec`**
  - Evidence: §4 declares only `substrate_sources`, `external_sources`, `composition_hint`, and `provenance_framing` as v1-minimal fields (lines 152-162), but D2 requires the spec to carry `inventory_witness: UNKNOWN` (lines 390-395).
  - Engineering consequence: implementers must either add an undeclared fifth field, hide UNKNOWN in ad hoc metadata, or lose the assembly-visible honesty state D2 depends on.
  - Closure criterion: v1.2 must declare a typed availability/inventory field, including UNKNOWN and witnessed absence, or explicitly attach that witness to each source block with construction/rendering tests.

- **M2. Prompt assembly enforcement is still ownerless**
  - Evidence: §4 says the template mechanism is a v1 deliverable and “likely” lives near the gemma manifest renderer (lines 189-193); D4 requires prompt assembly to render from `provenance_framing` (lines 404-406); Q10.8 still asks which module owns it (line 521).
  - Engineering consequence: the spec can emit correct dispatcher objects without any mandatory consumer, leaving provenance rendering scattered across Telegram/web/daemon prompt builders.
  - Closure criterion: v1.2 must name the module/API that consumes `CompositionSpec` and renders provenance templates, plus require all owner synthesis surfaces to route through it.

- **M3. Self-claim/fabrication integration lacks a metadata contract**
  - Evidence: §4 requires wiring `self_claim_audit` to framing-vs-output mismatches (lines 189-193), while R#6/R#20 only assert template selection and mismatched-block refusal (lines 485, 500).
  - Engineering consequence: `self_claim_audit` can flag ungrounded claims, but it cannot know the expected `provenance_framing` unless the dispatcher metadata is passed through a defined audit envelope; seam violations can become invisible.
  - Closure criterion: v1.2 must define the audit payload fields, where they enter `audit_assistant_text`/`self_claim_audit`, and whether a mismatch rewrites, blocks, or records a fabrication event.

- **M4. Legacy dynamic bypass paths are not enumerated**
  - Evidence: D1 says Layer 0 fully replaces `_should_run_jarvis_loop` (lines 386-389), and R#4 names the `brain_loop.py:900` short-circuit (line 483), but the spec does not enumerate all runtime surfaces that can fetch, run JARVIS, or assemble prompts.
  - Engineering consequence: a surface-local JARVIS/web-search path can bypass Layer 0 and reproduce the Reddit failure even if `core/brain/brain_loop.py` is fixed.
  - Closure criterion: v1.2 must list every owner reply entrypoint in scope and require a static/integration test that no owner path reaches tool/fetch/prompt assembly before dispatcher spec construction.

- **M5. Executable Layer 1 routes and reserved routes are blurred**
  - Evidence: Layer 1 “must include at least” `LIVED_GRAPH` and `CROSS_SURFACE_OWNER_TURNS` (lines 268-280), but the vocab marks `WEB_FAST_TURNS` and `LIVED_GRAPH` as dependent on future trust-scope/G11 work (lines 306-309), with cross-surface and graph questions still open (lines 518-519).
  - Engineering consequence: v1 cannot honestly fan out across sources whose reader APIs are explicitly not ready; tests may pass with placeholder routes that look executable.
  - Closure criterion: v1.2 must split executable v1 sources from reserved enum values and require construction refusal or explicit availability-limit rendering for reserved routes.

### Minor
- **m1. `FRONTIER_CONSULT` is a footgun as a normal `ExternalSource`**
  - Evidence: `FRONTIER_CONSULT` appears in the initial `ExternalSource` list (lines 320-326), while D10 says it grants no new authority (lines 434-437).
  - Engineering consequence: downstream dispatch can accidentally treat a provenance label as an executable source.
  - Closure criterion: mark it reserved/non-executable in the type system or keep it out of `external_sources` until G3 exists.

- **m2. Repair spec crash recovery is under-keyed**
  - Evidence: Layer 2 uses `last_spec_by_bond_id` plus a single-row `dispatcher_last_spec` table (lines 281-289).
  - Engineering consequence: a single-row crash cache is easy to misread across surface/user/bond boundaries.
  - Closure criterion: define the persisted key shape: at minimum bond id, surface, turn id, timestamp, and TTL expiry.

- **m3. `REPAIR_INHERIT_PRIOR_SPEC` is not a legal product cell**
  - Evidence: §6.5 says it “inherits prior spec's framing, modulo Layer 2 re-evaluation” (lines 367-380).
  - Engineering consequence: D11 cannot be implemented as a closed table if one row is procedural rather than enumerated.
  - Closure criterion: either make repair a modifier outside the product table or enumerate legal post-repair framings.

- **m4. R#21 is too ceremonial**
  - Evidence: R#21 says “Spec-level anchor; concrete test refined during implementation” (line 501).
  - Engineering consequence: the RED suite can claim coverage without proving a boundary.
  - Closure criterion: replace with a concrete static/import-path test or move it out of RED anchors.

### Nit
- **n1. Typo in D2**
  - Evidence: “D2 must not laundering...” (line 398).
  - Engineering consequence: none.
  - Closure criterion: change to “must not launder.”

- **n2. Avoid “likely” in a v1 deliverable**
  - Evidence: “likely the gemma manifest renderer...” (line 190).
  - Engineering consequence: weakens ownership language.
  - Closure criterion: either name the owner or label it explicitly open.

- **n3. Use fully qualified path for the JARVIS short-circuit**
  - Evidence: R#4 cites `brain_loop.py:900` (line 483).
  - Engineering consequence: phase shims make ambiguous file references easy to misread.
  - Closure criterion: cite `core/brain/brain_loop.py:900`.

## Summary

Engineering verdict: ratify with amendments. The dispatcher shape is buildable, but v1.2 needs to close the places where enforcement currently depends on implication: schema fields, prompt-renderer ownership, audit metadata, and legacy bypass enumeration. Without those amendments, the design can look wired while still letting old routing and prompt paths slip around it.
