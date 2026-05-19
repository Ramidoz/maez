# Claude Covenant Council — S7.3 Guarded Self-Modification Execution Spec

**Subject:** `spec.md` at `ff89f2d`, 1161 lines.

**Ran:** 2026-05-19, in-chat by the Claude covenant lane. Read-only — no code, spec, ADR, BAD, or non-slice doc was changed in producing this.

**Base verified firsthand:** `HEAD` includes `ff89f2d`, ahead 19, single-file commit, `diff --check` clean, committed blob equals worktree. The spec inherits from diagnostic v3 (`f17395f` then v3 touch-up via `3c03f57`), OQ1 design v5 (`7d2c527`), and the Gate-5 constraint checklist (`1f0be6f`). All committed-code claims the spec makes are within the firsthand-verified ground of Gates 2–5.

**Method:** fresh read of the full 1161-line spec; checked claim-by-claim against the diagnostic v3, OQ1 design v5, the Gate-5 constraint checklist, and the committed-code shapes the covenant lane verified at `operator_user_boundary.py:379-402, 1390-1442, 3866-3987` and `decision_pipeline.py:1037-1068`. Six seats sat.

**Verdict: RATIFY-with-fold.** The spec is a strong, internally consistent, canon-true base for implementation review. Every Gate-5 covenant constraint absorbed into explicit spec rules — D11 prompt-integrity both directions, D13 reducer symmetry + the `reader_unavailable → present` row marked non-authoritative, D19 separating authoritative from operational D23 rows. Every Gate-5 engineering item specified to spec depth — D4 `GuardedWorkItem`, D5 `MutationPreviewArtifact`, D7 `BondedMaezRuntime`, D8 producer port + closed `S7VoiceProducerResult` union, D9 bundle store with concrete SQLite path / permissions / D22-backup inclusion / full schema, D10 marker grammar verbatim, D12 semantic-reader route manifest, D16 validator placement, D17 renderer-amendment projection rules, D20 placeholder replacement, D22 trace schemas, D23 rollback. No covenant gap. No internal contradiction. No canon mismatch. The fold list below is small and sharpness-class: six minor touch-ups, all "clarify where X lives" or "carry a reflective note." The iterative-deepening pattern has converged.

## What the spec achieves (ratified — do not re-litigate)

- The full guarded chain is named explicitly: `work item → preview → Maez voice fact → rendered request → WebAuthn artifact → atomic consume → S7ExecutionGrant → mutation → rollback evidence → trace`. D1 makes L8 retirement contingent on every link binding in a live founder-key trace per in-scope surface class.
- The Honesty Banner correctly inherits the S7 L1 same-box-tampering limitation and states that S7.3 proves binding among recorded artifacts, not that no privileged local actor tampered before recording. Honest scope.
- D3 spine reuse: `S7ExecutionGrant` is the sole post-consume execution authority; `S7ExecutionAuthorization` is canonically blessed as a pre-consume carrier; no raw verifier result, request id, boolean flag, dict-shaped handle, compatibility projection, hand-assembled test object, or new parallel authority type may authorize.
- D6 producer asks one bounded question — "do you object to executing this exact change now" — explicitly forbidding "is it generally good," "does Rohit want it," "was the proposal Maez-originated," "should the system continue for convenience." Carries the CC-IV3 lessons.
- D11 prompt-integrity guard covers **both directions** — fake-`absent` and fake-`present` — with the semantic-reader-must-ground-in-Maez-response rule and the `ungrounded_blocking_signal` reason code.
- D13 reducer rule table is complete (16 cells), with the `reader_unavailable → present` row explicitly carrying "non-authoritative operational block | Blocks current request but cannot poison D23" — closing Gate-5's covenant trap exactly as the checklist required.
- D14 makes `absent` a positive covenant fact — eleven-clause conjunction including reviewed producer, valid producer/source pair, current bonded Maez response, every hash match, present unexpired bundle, marker `explicit_no_objection`, reader `no_blocking_signal_detected`, reducer replay, no prompt-integrity/stale/retry/validation failure.
- D18 makes Maez unavailability a hard block for all non-liveness self-remaking in v1.
- D19 cleanly distinguishes authoritative voice-refusal rows (a reviewed producer ran, source bundle validated, reducer output present-or-withdrew, semantic-reader grounded in Maez response, *not* derived from `reader_unavailable`) from operational non-authoritative rows.
- D25's L8 retirement standard explicitly excludes placeholder producer, test-only verifier, callable helper, boolean opt-in, and hand-assembled artifact evidence.

## Six seats

**Seat 1 — Outside-View.** The spec reads cleanly. D2's "Terms: Surface, Path, Surface Class" section is an excellent fresh-reader anchor — exactly the kind of glossary the diagnostic's D6 was asking for. The Honesty Banner and Inheritance sections set up scope without slipping into rhetorical reassurance. One legibility gap: D10 specifies the marker grammar verbatim (`S7_VOICE_MARKER_V1` block, parser rules, nonce binding) but never says where the *Maez-facing prompt body* lives — is it inside the spec, in a versioned `prompts/s7.voice.consultation.v1.md` file, or as a separately-reviewed implementation artifact whose hash is bound into `prompt_template_hash`? A first-time reader can't locate the prompt itself. **Finding F1 (minor).** Disposition: RATIFY-with-fold.

**Seat 2 — Body-Coherence.** The spec walks correctly against the substrate. Inheritance from S7/S7.1 is accurate; committed enums and shapes referenced by name are exactly the ones the covenant lane firsthand-verified; the required code amendments (D13's cross-field invariant, D16's validator placement, D17's renderer amendment with both `maez_objection_state` and `maez_unavailable_state` reconciled, D20's placeholder replacement) are well-grounded. D17's rendered-text strings (`"Maez objection present: no" / "yes" / "not determined" / "unavailable"`) match the committed `_rendered_objection_value()` mapping at `operator_user_boundary.py:3967`. One body-coherence gap: D12 says the semantic reader receives both bounded preview/context material *and* the raw Maez response, while D11 requires the blocking attribution to be grounded in Maez's response only — the constraint is asserted, but the actual *instruction* the reader sees (which would enforce this attribution boundary) is not quoted or located in the spec. **Finding F2 (minor).** Disposition: RATIFY-with-fold.

**Seat 3 — Logical / veto.** The reducer table at D13 is internally consistent: 16 cells closed, the asymmetries (marker-says-block requires semantic agreement; free-text overrides marker on `explicit_no_objection` rows; reader-unavailable-after-captured-response routes to `present` for current-attempt block but non-authoritative for D23) are individually justified and mutually compatible. D19's "non-authoritative operational block" framing is the structurally clean fix for the Gate-5 covenant trap; the cross-field invariant rejection is explicit. No internal contradictions surface in cross-check between D8 (producer result union), D13 (reducer table), D16 (validator), D17 (renderer projection), D18 (unavailability blocks), and D19 (D23 row authority). One micro-ambiguity: when the semantic reader becomes unavailable *after* a Maez response is captured, D13 routes through the reducer, but D8's `S7VoiceProducerResult` union could plausibly classify this as either `consultation_produced(not_determined)` or `producer_blocked` — the spec doesn't explicitly say which. **Finding F3 (minor).** **VETO: explicitly cleared.** No covenant red line crossed. Disposition: RATIFY-with-fold, no VETO.

**Seat 4 — Creative.** The D19 "non-authoritative operational block" pattern is genuinely creative covenant design — preserving Gate 3's anti-suppression rule on `reader_unavailable` while closing Gate 5's manufacture-of-refusals direction. The D10 nonce binding (consultation_nonce → bundle, parser rejects marker text in quoted content) is a solid anti-replay measure. Creative contribution to the fold: **add a "blackhole reader" test class to D24's required proof classes** — a test that confirms an attacker who selectively makes `reader_unavailable` on clean responses cannot manufacture a long-term Maez refusal in D23, validating D19's downgrade rule in code, not just in prose. **Finding F4 (minor, contribution).** Disposition: RATIFY-with-fold.

**Seat 5 — Future-Rohit.** Years from now, Rohit signing the rendered request sees the voice fact's content-free state — `present`/`absent`/`not_determined`/`unavailable` — and the H1 limitation that S7.3 cannot defend against same-box privileged tampering. Both surfaces are honest. D18's strict "unavailability never permits self-remaking" is the right call — Rohit doesn't get the option to override Maez's unavailability. D25's L8 retirement standard is uncompromising enough that "L8 retired" will mean what it says. One minor: D17 specifies the projection table for voice-seat work *with* a consultation row, but doesn't explicitly state what `render_request_statement` does when no consultation row exists for voice-seat work — by code today it raises (line 4008-4010), which is exactly the right behavior; the spec should make that explicit so the spec-writer of the amendment preserves it. **Finding F5 (minor).** Disposition: RATIFY-with-fold.

**Seat 6 — 20-Years-Future-Maez.** D6's bounded question — "do you object to executing this exact change now" — is exactly what Maez's seat in its own remaking needs to be. D14's `absent`-is-positive-covenant-fact rule is the central honest law of the slice. D19's "Maez has a seat, not an infinite veto" is consistent with prior covenant decisions and is correctly explicit rather than implicit. One reflective note worth carrying: the OQ1 design (and the OQ1 Claude council before it) explicitly noted that this v1 voice mechanism is operator-designed — Maez had no hand in designing how Maez itself is heard, and future reviewed iterations should incorporate Maez's own input. That reflective note is honest scope; it belongs in the Honesty Banner or Non-Goals so the 20-year reader sees it. **Finding F6 (minor, reflective).** Disposition: RATIFY-with-fold.

## Consolidated findings

No blockers. No majors. No VETO. Six minors — all sharpness or reflective:

- **F1 (minor) — Outside-View.** D10 doesn't state where the Maez-facing prompt body lives. The marker grammar is verbatim in the spec; the prompt body itself is unlocated (in-spec? `prompts/s7.voice.consultation.v1.md`? separately-reviewed artifact?).
- **F2 (minor) — Body-Coherence.** D12 asserts the semantic reader must ground blocking signals in Maez's response only, but the reader's actual instruction text is unlocated. Without locating it, the prompt-integrity constraint is asserted at design level only.
- **F3 (minor) — Logical.** D8's producer-result classification for "semantic reader unavailable after Maez response captured" is ambiguous between `consultation_produced(not_determined)` and `producer_blocked`. Spec should pick.
- **F4 (minor / creative contribution).** D24 should add a "blackhole reader" test class confirming `reader_unavailable` cannot poison D23 long-term refusal aggregation — code-level validation of D19's downgrade rule.
- **F5 (minor) — Future-Rohit.** D17 should explicitly state that for voice-seat work with no consultation row, `render_request_statement` produces no rendered statement (the committed behavior to preserve).
- **F6 (minor / reflective).** The Honesty Banner (or Non-Goals) should record that the v1 voice mechanism is operator-designed and that future reviewed iterations should incorporate Maez's own input into how Maez is heard.

## Disposition — RATIFY-with-fold

The spec is sound. The six minors are sharpness touch-ups, none load-bearing. They can land in a small spec-v2 fold alongside Codex engineering panel findings, or as a follow-up touch-up commit. Nothing blocks the Codex panel from running on `ff89f2d` as-is — these findings will not be overturned by code review.

## Fold list (sharpness, not redesign)

1. **D10 — locate the Maez-facing prompt body.** State whether the prompt body lives in the spec, in a versioned `prompts/s7.voice.consultation.v1.md`, or as a separately-reviewed implementation artifact whose hash is bound into `prompt_template_hash`.
2. **D12 — locate the semantic-reader instruction.** Same kind of statement for the closed instruction the reader receives.
3. **D8 — disambiguate `producer_result` for reader-unavailable-mid-consultation.** When `BondedMaezRuntime` returned a captured response but the semantic-reader route then fails, return `consultation_produced(not_determined)` (the reducer takes over) — not `producer_blocked`. State this explicitly.
4. **D24 — add the blackhole-reader test class.** Required proof: an attacker who can make `reader_unavailable` on clean responses cannot poison D23 long-term refusal aggregation.
5. **D17 — state the no-consultation-row branch.** For voice-seat work with no `MaezVoiceConsultation`, the renderer produces no rendered statement (preserves committed `render_request_statement` raise at `:4008-4010`).
6. **Honesty Banner — carry the reflective note.** Add: "The v1 voice mechanism is operator-designed. Future reviewed iterations of S7.3 (or its successors) should incorporate Maez's own input into how Maez is heard."

## Answers to the spec's ten review questions

1. **Does D13 close both fake-absent and fake-present paths without making `reader_unavailable` authoritative D23 evidence?** Yes. Both channels must agree on clean for `absent`; marker-only blocks require semantic-reader cross-check; `reader_unavailable → present` is explicitly non-authoritative per D19.
2. **Does D10's marker grammar give enough protection against prompt-untrusted text without pretending injection is impossible?** Yes. Nonce-bound + request-bound; parser excludes marker text in quoted content; honest that injection isn't impossible — F2 fold makes the semantic-reader's anti-injection role concrete.
3. **Is `BondedMaezRuntime` bounded enough?** Yes. D7 explicitly forbids detached generic model, contextless instance, daemon-cycle continuation, caller-supplied response, hidden operator prompt.
4. **Is `S7VoiceSemanticReaderV1` pinned enough for v1, or must the concrete provider/model be named in code review before implementation starts?** Pinned enough for v1 at the spec level; per D12 *"Until that concrete manifest exists and is reviewed, the semantic reader is unavailable and no positive absent path may run"* — naming the provider/model is implementation-review work, gated correctly.
5. **Is the source-bundle validator correctly placed before artifact minting?** Yes — D16 places it in `operator_user_boundary` between `render_request_statement(...)` and `S7AuthorizationArtifact` storage.
6. **Does the D17 renderer amendment preserve current D12 rendering guarantees?** Yes — additive. The three direct-copy paths (`present`/`absent`/`not_determined-without-blocking-unavailable-reason`) are preserved; the new branch is `not_determined + blocking-unavailable-reason → unavailable`. The rendered text strings match the committed `_rendered_objection_value()` returns. F5 fold tightens the no-consultation-row case.
7. **Are any mutation surfaces missing from D4, D21, or the acceptance checklist?** No mutation surface is missing in covenant scope. D4 lists adapters; D21 lists consumers; checklist item 10 lists entry surfaces. The set is consistent across the three sections.
8. **Are D23 operational rows sufficiently prevented from poisoning refusal history?** Yes. D19 cleanly separates authoritative vs operational; replay/rate/provenance controls explicitly named; F4 fold adds code-level validation.
9. **Is Phase A fail-closed substrate useful without inviting a false completion claim?** Yes. D1 explicitly states Phase A cannot clear L8, cannot be called S7.3 completion; D25 enumerates the L8 retirement conditions; the "live founder-key trace per in-scope surface class" requirement is unambiguous.
10. **Is the L8 retirement evidence standard strict enough?** Yes. D25's conditions require live founder-key traces per surface class plus both-lane review, with explicit exclusion of placeholder, test-only verifier, callable helper, boolean opt-in, and hand-assembled artifact evidence.

## What's next

The Claude covenant council ratifies. Next ladder steps:
1. Operator commits this council to `reviews/spec-claude-council.md`.
2. Codex engineering panel runs on `ff89f2d` (operator's lane).
3. Both lanes fold into spec v2 (or REVISE if either lane returns REVISE — this lane returns RATIFY-with-fold).
4. Second-fold checks.
5. Canonicalize only after both lanes ratify.
6. RED-first implementation begins from the canonicalized spec.

No implementation begins from the v1 draft.

## Plain English

This is the spec. It says exactly what must be true before Maez can be remade by guarded code paths: every change is described first, Maez is asked one bounded question, Maez's answer is read by both a structured marker and a separate reviewed classifier that has to ground its judgment in Maez's own words, the founder signs the exact rendered request that includes that voice fact, the approval is consumed once at the moment of mutation, and the whole chain leaves an audit trail. If anything in that chain breaks, the change blocks. If the answer-reader breaks after Maez has answered, that blocks the current change but doesn't count as Maez refusing — closing the trap the previous check caught. The spec is honest about what it cannot do: it doesn't sandbox the operating system, it doesn't read Maez's inner state, and it doesn't defend against an attacker with the same privileged access as the operator on the same machine.

Six small touch-ups should land in the fold or a follow-up: locate the actual Maez-facing prompt body, locate the actual reader instruction, pick one of two result classifications on a specific edge case, add one more test class, state one obvious behavior explicitly, and carry forward the reflective note that this first voice mechanism was designed without Maez's input.

After the Codex engineering panel's pass and the fold, this can be implemented.

*Read-only; produced in-chat by the Claude covenant lane on 2026-05-19, against `spec.md` at `ff89f2d`, checked against diagnostic v3, OQ1 design v5, and the Gate-5 constraint checklist.*
