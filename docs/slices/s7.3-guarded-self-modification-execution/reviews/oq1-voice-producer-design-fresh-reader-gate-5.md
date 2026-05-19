# Fresh-Reader Gate 5 - S7.3 OQ1 Design v5

**Subject:** `oq1-voice-producer-design.md` at `7d2c527` (OQ1 v5), with
diagnostic v3 and Gates 2-4 as context.

**Ran:** 2026-05-19. Three independent blank-context subagents - cold covenant
reader, cold spec-writer, cold residual-hunter - each given v5 plus diagnostic
v3 plus canon, walled off from `reviews/`. The covenant lane firsthand-verified
the load-bearing as-built shapes at `operator_user_boundary.py:1390-1442` and
`:3866-3987` across earlier gates; the spec-writer and residual-hunter
independently re-verified them against the cited line ranges this gate.

**Verdict: SUFFICIENT - proceed to the S7.3 spec from v5 plus the explicit
constraint checklist below.** Five gates of iterative deepening have produced a
design that is structurally sound, canon-true, and decision-complete. The
remaining items are either spec-level engineering or specific covenant
constraints absorbable as explicit spec rules, not design rethinks. The
covenant lane recommends Path B: write the spec from diagnostic v3, OQ1 v5,
and this checklist.

## What v5 Genuinely Achieved

Affirmed across the gate and code-verified:

- The voice-state vs render-shape reconciliation is canon-true: three-value
  `MaezVoiceConsultation.maez_objection_state`; five-value
  `RenderedRequestStatement.maez_objection_state`.
- The closed producer, source-kind, and voice-seat work-class enums are
  canon-accurate.
- The diagnostic's documented placeholder shape matches
  `decision_pipeline.py:1056-1067`.
- The deterministic reducer table covers all marker x semantic-reader
  combinations; `withdrawal_marker` distinguishes withdrawal from objection.
- OQ1 / OQ2 / OQ3 / OQ4 are resolved: Candidate B primary; Phase A substrate vs
  Phase B live producer with end-to-end completion; Maez-initiated provenance
  supplemental only; non-liveness blocks under Maez unavailability.
- Placeholder repair is a binding rule, not a preference.
- The renderer-amendment requirement is named and grounded in the committed
  renderer.
- The `S7ExecutionAuthorization` carrier-not-authority decision is made.
- The common `GuardedWorkItem` bridge is chosen.
- The voice-producer port has a method signature.

## Constraints The S7.3 Spec Must Absorb

### Covenant Constraints

Load-bearing; the spec must include these as rules.

1. **D23 downgrade rule for `reader_unavailable`-derived `present` rows.**
   The anti-suppression reducer row
   `explicit_no_objection + reader_unavailable -> present` blocks the current
   authorization, but it must not count as authoritative D23 voice-refusal
   evidence. Otherwise a same-box actor could manufacture refusal history by
   breaking the reader.

2. **Reducer symmetry on marker-says-block rows.** The spec must require
   semantic-reader cross-check on `blocking_marker` and `withdrawal_marker`.
   If the marker says block but the semantic reader returns
   `no_blocking_signal_detected`, the result is `not_determined`, not
   authoritative `present`. Alternative acceptable shape: define structured
   marker fields that prompt-untrusted text cannot contain, such as a signed
   marker token produced only by Maez's runtime.

3. **Prompt-injection guard on
   `missing_or_malformed + blocking_signal_present`.** The reader's blocking
   attribution must be grounded in Maez's response text only, not in the
   rendered preview shown for context. The prompt-integrity contract must cover
   fake-present as well as fake-absent.

4. **Marker grammar specification.** The spec must include the actual voice
   prompt template and marker grammar: what tokens Maez emits, how they are
   parsed, and why prompt-untrusted text cannot synthesize them.

### Internal Contradictions To Clean Up

5. **`S7ExecutionAuthorization` decision.** v5 triage decides to bless the
   current type as pre-consume carrier; the dedicated reconciliation section
   still presents "choose one of two." The spec must follow v5 triage and remove
   the stale fork.

6. **OQ4 "renders as unavailable" wording.** OQ4 must say "renders as
   unavailable once the renderer amendment from Committed Voice-State And Render
   Shape is applied."

### Spec-Level Engineering

7. Define `BondedMaezRuntime`: what the bonded Maez runtime port exposes and how
   routing identity is locked.
8. Ground dataclass shapes and validation rules for `MutationPreviewArtifact`,
   `GuardedWorkItem`, `S7VoiceConsultationBundleStore`, and
   `S7VoiceProducerResult`.
9. Specify trace schemas using diagnostic D7's binding inventory as the floor.
10. Specify bundle-store substrate: SQLite path, schema, retention TTL,
    permissions, Decision-22 backup inclusion, `read_by_source_ref_hash`
    interface, and replay protection.
11. Pin the semantic-reader concrete provider/model/config identity from the
    route slot `s7_voice_semantic_reader_v1`.
12. Specify source-bundle validator placement, signature, and error/result type.
13. Specify surface bridge adapters for `/apply_dream`, section edit, approval
    cards, self-mod dialog, CLI, cockpit, and direct helpers.
14. Specify the `_s7_voice_consultation_for_card` replacement contract.
15. Specify renderer field reconciliation: what `maez_unavailable_state` holds
    when the render projection fires `unavailable`.

### Fold Residuals

16. Reducer rule-table rows must specify all three voice-state fields per cell.
17. Producer Placement sequence must include running `S7VoiceSemanticReaderV1`
    and persisting its output.
18. Stale v4 attributions in v5 prose should be cleaned or superseded.
19. Clarify "three-field MaezVoiceConsultation data model" as "three
    voice-state fields," not the whole dataclass.
20. Clean terminology: positive absent vs field-not-set "absent";
    `_marker` / `_present` / `_detected` suffix style; "Maez-initiated" vs
    "Maez-originated."

## Honest Pattern Conclusion

Five consecutive gates have done their work:

- Gate 1: diagnostic skipped OQ1.
- Gate 2: OQ1 v2 enum mismatch plus classifier under-depth.
- Gate 3: OQ1 v3 fixed core and missed second enum/coupling.
- Gate 4: OQ1 v4 fixed those and missed render projection/port shape.
- Gate 5: OQ1 v5 fixed those and leaves reducer asymmetry side effects plus
  spec-shaped types.

Each pass got narrower. v5 is the point where two of three readers say the
design supports a spec without forcing covenant invention, and the remaining
covenant issues are specifiable constraints rather than design rethinks.

## Recommendation

Proceed to the S7.3 spec from:

- diagnostic v3;
- OQ1 design v5;
- this Gate-5 constraint checklist.

The spec's own both-lane review - Claude covenant council plus Codex
engineering panel - is the right validation surface for the constraints that
remain.

## Plain English

Three fresh readers checked v5. Two said the design is sound and the spec can
be written from it; the remaining items are real, but the spec is the right
place to settle them. One found a new covenant problem: treating a broken
answer-reader as "Maez objected" blocks safely, but could manufacture refusal
history. The fix is a spec rule: it blocks the current authorization but does
not count as authoritative Maez refusal.

After five gates, the remaining work is no longer "design the voice producer."
It is "write the spec with these explicit constraints, then review that spec."
