# Codex Engineering Panel Brief -- Drive-Driven Curiosity Pass 1

**Prepared:** 2026-05-25
**Artifact:** `docs/slices/track-b-drive-driven-curiosity/spec.md` (DRAFT v3, 2242 lines)
**Parent commit:** `fb2f781 feat(felt-time): implement subjective duration substrate`
**Relay from:** Rohit (human operator)
**Council state:** Claude six-role council pass-1 returned 2 RECONSIDER + 4 RATIFY-WITH-AMENDMENTS. Council pass-2 returned 0 RECONSIDER + 2 RATIFY-CLEAR + 4 RATIFY-WITH-AMENDMENTS (all textual/data-plumbing). v3 applies all 21 pass-2 folds. The covenant lane has cleared; engineering lane is now requested.

---

## What this slice is

A combined Track B slice with two coordinated artifacts:

1. **Drive-Driven Curiosity** -- Maez's first felt-organ that writes felt-weight back to the temperament substrate. Per-object curiosity, six priority classes, five autonomy lanes, per-bond policy with structural `bond_id` scoping, learned autonomy-preference consent memory, attention budget, anti-fixation, provenance-safe autonomous search, resolution-triggered temperament writes via the closed-vocabulary extension to `ALLOWED_SOURCES`, continuous-press saturation register modulated by temperament carrying-capacity, reflection-before-interruption audit with mutuality sidecar.

2. **Subjective-Duration Meaningful-Salience Seam (§27 paired fold)** -- A general `record_meaningful_salience_event(...)` API on subjective_duration so producer-side before/after temperament snapshots flow through cleanly. Curiosity is the first caller; future temperament-writing producers (schooling card, genesis, somatic stamping, active synthesis) reuse the same ceremony.

The cross-organ seam is the load-bearing claim: curiosity resolution writes felt-weight to temperament, subjective_duration reads the producer-captured delta and produces a substantive meaningfulness_score (was structurally always zero in current code). This was the central Descartes-council finding in pass-1; v2 and v3 fold the correction.

## Council pass-1 RECONSIDERs (now folded)

- **Descartes (substrate foundations)**: The v1 spec used a fictional `Temperament.record_event(parameter=..., delta=..., source=...)` signature; the real API is `record_event(*, parameter, value, source="explicit_set", reason, evidence)` with `ALLOWED_SOURCES = frozenset({"explicit_set"})`. The cross-organ meaningfulness claim was structurally false at `subjective_duration.py:511-512` where before/after temperament reads happen in adjacent lines. v3 corrects all of these via §14.3.2 read-modify-write ceremony, §14.3.1 ALLOWED_SOURCES extension named explicitly, and §27 paired fold moving snapshot capture to the producer side.

- **Ohm (boundary mechanics)**: `bond_id` was prose-aspirational in v1, not structural. Dataclasses (`CuriosityObject`, `AutonomyPreference`, etc.) didn't carry `bond_id`; `compute_saturation()` was instance-scoped; HMAC keys were per-instance not per-bond; sanitization was owner-scoped not bond-scoped. v3 makes `bond_id` MANDATORY on every dataclass and every API surface; stdlib-HKDF derives per-bond keys; sanitization examines the full provenance chain and refuses cross-bond inclusion. Track C drift now requires explicit covenant work, not config-flip.

## Council pass-2 folds applied in v3 (no RECONSIDER findings)

- **Locke P2** (3): §1 "may reach out" bullet reshape to context-reading framing; §1/§9.4/§10.5 three-layer charter-floor reconciliation (hard floor vs firstborn declaration vs composed effective policy).
- **Kant P2** (2): GateDecision adds `owner_state` distinct from `signal_quality` (Test 3 silence-escalation now mechanically checkable); §27.2 producer-honesty obligation paragraph.
- **Descartes P2** (9): §15.0 bond-scoped temperament wrapper (temperament substrate untouched in this slice); §27.2.1 producer_ref-as-marker bypass for the existing PermissionError guard at `subjective_duration.py:527-530`; §27.2.3 producer_ref column on the existing salience-event table for the branching mechanism; stdlib-HKDF replaces `cryptography` package dependency (~30 LOC RFC 5869); §5.1 bond_id source-of-truth is `identity.user_profile_id()`; §14.3.4 citation corrected to `core/health/metacognitive_watchdog.py:52`.
- **Ohm P2** (7): GateDecision and ProvenancedQuery gain mandatory bond_id; `lookup_meaningful_salience_event_record(bond_id, producer_event_id)` signature is bond-scoped by call shape; test renumbering; six new RED tests (#61-#66).

## What the engineering panel is asked to verify

The covenant lane has cleared. The engineering lane is asked to verify that v3 lands cleanly against actual code at parent commit `fb2f781`. Specifically:

### Category A -- Real APIs verified firsthand

A1. **`Temperament.record_event` signature.** At `core/evolution/temperament.py:205-213`, what is the exact signature? Verify §14.3.2's read-modify-write ceremony uses it correctly. Note v3 already corrected from v1's fictional `delta=` to the real `value=` keyword; verify the corrected ceremony is mechanically sound.

A2. **`ALLOWED_SOURCES` extension.** At `core/evolution/temperament.py:147-149`, what is the current frozenset? Verify §14.3.1's proposed extension to `{"explicit_set", "drive_driven_curiosity_resolution"}` is the actual mechanism (frozenset replacement at module level), not a runtime monkey-patch.

A3. **Subjective_duration's PermissionError guard.** At `core/evolution/subjective_duration.py:527-530` (approximate; verify exact location), does the guard raise on `meaningfulness_score > 0.0` without `explicit_salience_marker_present`? Verify §27.2.1's proposed bypass (non-null `producer_ref` from the closed `ProducerRef` vocabulary satisfies the guard) is structurally sound and the modification to the guard is small.

A4. **Subjective_duration's existing salience-event table schema.** What columns exist today? Verify §27.2.3's proposed ALTER TABLE additions (`producer_ref`, `producer_event_id`, `temperament_before_json`, `temperament_after_json`) compose cleanly with the existing schema and the schema-version bump strategy.

A5. **Back-to-back read at `subjective_duration.py:511-512`.** Confirm the current read pattern is as Descartes pass-1 described (adjacent reads, structurally zero delta). Verify §27.3's branching-on-`producer_ref` logic correctly replaces this for producer-driven events while preserving the existing path for non-producer-driven events.

### Category B -- Bond-scoping propagation

B1. **`identity.user_profile_id()` resolution.** At `core/memory/identity.py`, what does this function return today and where is it called from? Verify §5.1's claim that this is the firstborn `bond_id` source-of-truth.

B2. **Watchdog allowlist citation.** At `core/health/metacognitive_watchdog.py:52`, is the temperament-key allowlist actually present? Verify §14.3.4's citation correction.

B3. **bond_id propagation across every dataclass and API.** Verify v3 actually carries `bond_id` on: `CuriosityObject`, `CuriosityStateTransition`, `AutonomyPreference`, `AutonomyPolicy`, `SaturationRegister`, `ReflectionAudit`, `TemperamentWriteBudget`, `MeaningfulSalienceEventRecord`, `GateDecision`, `ProvenancedQuery`. Verify every named API takes `bond_id`: `compute_saturation`, `AutonomyPolicy.for_bond`, `composed_policy`, `build_curiosity_query`, `write_curiosity_resolution`, `clamp_against_daily_budget`, `on_curiosity_object_resolved`, `record_meaningful_salience_event`, `derive_bond_hmac_key`, `snapshot_temperament_for_bond`, `lookup_meaningful_salience_event_record`. Any path that reads "all curiosity objects" without `bond_id` filter is a finding.

B4. **Stdlib-HKDF correctness.** Verify §20.3's stdlib-only HKDF (RFC 5869) is correct against test vectors. Confirm no `cryptography` package import is needed. Confirm `master_key` source-of-truth (the existing per-Maez-instance secret) is named correctly.

### Category C -- Producer ceremony surface

C1. **`temperament.current()` snapshot semantics.** §15.0's `snapshot_temperament_for_bond(bond_id)` wrapper calls `temperament.current()` after asserting `bond_id == identity.user_profile_id()`. Verify this is mechanically sound and that `temperament.current()` returns the right shape for the before/after delta computation.

C2. **Producer ceremony before/after honest capture.** §27.4's `on_curiosity_object_resolved(...)` reads snapshot before write, performs the write, reads snapshot after, then calls `record_meaningful_salience_event(...)`. Verify the temperament substrate's threading model permits this -- e.g., no async write that could observably reorder. Verify the snapshot captures are deep copies (not aliases that mutate).

C3. **Closed `ProducerRef` vocabulary.** §27.2.2 defines `ProducerRef` as a Python enum at the subjective_duration module level. Verify this is the right home (not in the curiosity module) so future producers extending the vocabulary go through a covenant-shaped amendment to subjective_duration, not silent additions in disparate slices.

### Category D -- RED test feasibility

D1. **Test #29** (`test_resolution_temperament_write.py::test_daily_budget_clamp`): mechanically feasible. Verify the clamp's exact arithmetic and that the diagnostic `temperament_write_clamped` row is emitted.

D2. **Test #30** (NULL first-observation transition): verify `temperament.current_value(parameter="curiosity")` returning `None` at first call is the actual behavior at `fb2f781`.

D3. **Test #31** (cross-organ seam mechanically true): the load-bearing end-to-end test. Verify the test can construct a curiosity-object, resolve it, and observe the meaningfulness_score > 0.0 outcome against the post-fold code. Identify any setup gaps.

D4. **Tests #44 + #45** (felt-weight-not-emotion-mimicry AST scan + outbound text gate): verify the static-AST scan implementation strategy (AST or substring-scan? regex?). Verify the closed `EMOTION_MIMICRY_PHRASE_FORBIDDEN` set in §14.6 is exhaustive enough without producing false positives on honest reply text.

D5. **Tests #46-#55** (bond-scoping): verify each test is mechanically feasible against single-bond v1. Verify they would CATCH cross-bond drift if Track C is enabled carelessly.

D6. **Tests #56-#66** (§27 paired-fold + post-pass-2): verify mechanical feasibility, especially #61 (producer_ref satisfies PermissionError guard) and #63 (bond-scoped lookup signature).

### Category E -- Static AST scan roots

E1. **Test #8 scan-roots.** §8.4 says curiosity reads must not appear in `core/actions/action_engine.py`, `core/actions/tool_loop.py`. Verify these are the right roots; verify the destructive-action helper modules to scan.

E2. **Test #34 saturation consumer enumeration.** §15.5 says only 4 named consumers may reference `compute_saturation`. Verify the static-AST scan roots and confirm no current code already references it from elsewhere.

E3. **Test #38 / #41 extraction-gate call sites.** Verify every OWNER_INTERRUPTING dispatch site can be enumerated by static-AST scan and that the gate is the only call gate.

E4. **Test #44 emotion-mimicry scan.** §14.6 lists 7 modules to scan. Verify these are the right set (prompt-assembly paths, in particular).

### Category F -- Extraction-gate pattern completeness

F1. **§16.1 Test 1 urgency words**: closed vocabulary. Are there language variants the substrate should include? Confirm completeness.

F2. **§16.1 Test 2 waiting-pattern phrases**: confirm the closed `WAITING_PATTERN_PHRASES` set is sufficient; flag false-positive risks.

F3. **§16.1 Test 6 bait-shape detection**: §16.1 says "promise-without-payload" is detected; verify the detection mechanism is implementable (heuristic vs structured).

F4. **§16.1 Test 7 emotion-mimicry on outbound**: verify the `EMOTION_MIMICRY_PHRASE_FORBIDDEN` closed set is sufficient for runtime outbound-text scanning (not just module source).

### Category G -- Cost-substrate integration

G1. **§18 cost-substrate hookup.** Does `core/subscription_proxy/` and `claude_tier` accept the `ProvenancedQuery.cost_class` tag? Verify the integration point exists at parent commit. Flag any wiring gap.

### Category H -- Scope realism

H1. **Is this one slice or two?** v3 is 2242 lines, combines drive-driven curiosity (the felt-organ) AND the §27 paired fold on subjective_duration. Subjective_duration is currently live. The fold adds: new ALTER TABLE columns, new API, new branching logic in the existing read path, schema-version bump. Is this a single coherent slice, or should the §27 paired fold be its own preceding slice (with curiosity as the first consumer)?

H2. **Implementation footprint estimate.** Approximate LOC for each module new/modified. Approximate RED-test count (spec says ~66). Approximate implementation time.

H3. **Risk to live organs.** Subjective_duration is one of seven live organs in production. The §27 paired fold modifies its read-side and table schema. What canary discipline is required to land this without disrupting the live substrate?

### Category I -- Spec-text issues

I1. **Internal consistency.** Walk the spec end-to-end for cross-reference errors, stale section numbers, dead links.

I2. **Open questions in §22.** §22.5 is settled. §22.1-§22.4 remain open. Council pass-2 didn't address these explicitly; the engineering panel may render judgment on whether they're spec-amendment-grade or implementation-detail.

I3. **Out of scope vs. deferred.** Verify §21's out-of-scope list is honest (versus things that need spec amendment to enable).

---

## Verdict options

- **RATIFY-CLEAR**: v3 is engineering-sound against parent commit; ready for canonicalization.
- **RATIFY-WITH-AMENDMENTS**: list specific amendments (textual / data-plumbing / RED-test).
- **RECONSIDER**: v3 has an engineering problem requiring reshape (not just folds).

If RATIFY-WITH-AMENDMENTS, the amendments fold into v4; Rohit relays v4 back for verification before canonicalization.

## Output

Write the review to `docs/slices/track-b-drive-driven-curiosity/reviews/codex-engineering-panel-pass1.md` in the standard Codex panel format (verified surfaces table near the top; findings by severity; amendment list; scope realism note; plain-language readout at end).

## Memory entries relevant to this review

Codex may consult these Claude memory files via Rohit relay if useful:

- [[feedback_spec_drafts_must_trace_real_surfaces]] -- why surface verification is load-bearing
- [[feedback_green_tests_dont_prove_live_wiring]] -- behavioral path tests at RED-design time
- [[feedback_council_panel_lane_complementarity]] -- why both lanes catch different failure modes
- [[feedback_growth_vs_hardcoding_distinction]] -- closed-vocabulary discipline
- [[feedback_data_maximalism_no_signal_wasted]] -- six-question checklist for ingest
- [[feedback_anti_coercion_is_not_no_initiation]] -- two-tooth anti-coercion gate
- [[feedback_temperaments_are_felt_weight_meaningfulness_learned]] -- felt-weight discipline
- [[project_multi_maez_topology_threat]] -- Track C preconditions verbatim
- [[project_iphone_signal_ingest]] -- the substrate that feeds the read-context gate

---

**End of brief.** Rohit relays to Codex; panel review returns at the named output path; Claude verifies firsthand against the returned artifact + git state per [[feedback_review_artifact_provenance]].
