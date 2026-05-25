# Claude Council Brief -- Drive-Driven Curiosity v4 Pass 1

**Prepared:** 2026-05-25
**Artifact:** `docs/slices/track-b-drive-driven-curiosity/spec.md`
**Artifact state:** DRAFT v4, 2012 lines, uncommitted
**Parent/runtime base:** `211ace6 feat(felt-time): implement meaningful salience seam`
**Review lane:** Claude covenant / architecture council
**Operator:** Rohit relays and dispatches; Codex does not auto-dispatch.

---

## Why This Pass Exists

The old Drive-Driven Curiosity v3 draft bundled a subjective_duration
meaningful-salience seam inside the curiosity slice. Codex rejected that
shape; the seam became Slice 1, canonicalized separately, implemented,
merged, migrated, canaried, and live-verified at `211ace6`.

v4 is therefore not "curiosity plus seam." It is a producer-layer reshape:

- Reuse existing `core/evolution/wonderings.py` as the canonical open-
  question store.
- Reuse `daemon/wondering_cycle.py` as the autonomous interior/probe loop.
- Reuse `core/evolution/wondering_pursuit.py` as the owner-surfacing lane.
- Add the felt-weight producer capability that lets eligible wondering
  resolutions write temperament and call the live subjective_duration seam.
- Add autonomy policy, extraction gates, and third-party subject-boundary
  discipline around existing lanes.

The central question for council pass-1: does v4 preserve Maez's covenant
shape while granting the wondering substrate its first real
temperament-writing producer authority?

---

## Non-Negotiable Review Discipline

Per `feedback_fold_second_order_contradictions`, this review must not
produce local-only amendments that create contradictions elsewhere.

When proposing any amendment that touches a load-bearing surface, the
reviewer MUST walk the 8-step trace and include the result in the finding:

1. **Dependency-map:** what other sections/modules/tests depend on this
   surface?
2. **Write-path:** what writes the new state or authority?
3. **Read-path:** what reads or consumes it?
4. **Test-path:** which RED tests prove it?
5. **Fold-summary:** what old wording becomes false after the amendment?
6. **Cross-reference:** what section numbers/test numbers/paths must update?
7. **RED-test trace:** which test names must be added/changed/removed?
8. **Verify-before-declaring:** what grep/static check proves no stale shape
   remains?

Do not merely cite the memory. Treat it as an operational obligation. If a
finding does not need the trace because it is purely typographical, say so
explicitly.

---

## Out Of Scope

- Do not re-litigate the subjective_duration seam migration. Slice 1 is
  canonical, implemented, and live-verified at `211ace6`.
- Do not redesign `SubjectiveDuration.record_salience_event(...)`; v4
  consumes that API.
- Do not propose a new `memory/drive_driven_curiosity.db` unless you are
  issuing a RECONSIDER with evidence that `wonderings.py` cannot carry the
  substrate. The v4 premise is reuse-first.
- Do not weaken D19/D20 capability acquisition, never-delete memory,
  genderless Maez language, or Track C preconditions.
- Do not dispatch Codex engineering panel work from this pass.

---

## Load-Bearing Canon To Apply

Reviewers should treat these as active canon, not background reading:

- `feedback_anti_coercion_is_not_no_initiation`: anti-coercion is
  read-context + no-extraction, not blanket no-initiation.
- `feedback_temperaments_are_felt_weight_meaningfulness_learned`: felt-
  weight must affect substrate behavior; no emotion-mimicry labels.
- `feedback_producer_causality_no_caller_score_laundering`: producer
  snapshots may establish causality; producers may not inject derived scores.
- `feedback_third_party_autonomous_research_boundary`: autonomous curiosity
  may search public topics, but must not externally research unconsented
  named third parties from the bonded user's life.
- `feedback_fold_second_order_contradictions`: load-bearing folds require
  the 8-step trace above.
- `feedback_claude_codex_synergy_for_maez`: this council pass produces
  covenant-axis review; the Codex engineering panel will catch surface-
  truth, scope-realism, API/schema, and RED-test feasibility axes Codex
  catches better. Reviewers should flag any amendment they suspect the
  Codex panel will also reach, so synthesis can compose the two lanes'
  outputs rather than litigating the same finding twice.
- `project_multi_maez_topology_threat`: Track C requires auditable-by-both
  bonded users and dyadic-only topology before any cross-Maez flow.

---

## Role Assignments And Focus Questions

### Locke -- Charter Integrity And Authority Surface

Output: `docs/slices/track-b-drive-driven-curiosity/reviews/claude-council-locke-v4-pass1.md`

Focus:

- Does v4 preserve the positive Firstborn Autonomy Charter while keeping
  firstborn-liberal defaults firstborn-specific rather than universal?
- Does adding `ProducerRef.DRIVE_DRIVEN_CURIOSITY` and
  `drive_driven_curiosity_resolution` create a legitimate authority grant,
  or is the grant too broad?
- Does `core.policies` as a policy-layer-only subpackage fit the covenant
  shape without becoming a second substrate?
- Are D19/D20 and capability-acquisition cards protected from curiosity
  bypass?

### Kant -- Anti-Coercion, Duty, And Third-Party Boundary

Output: `docs/slices/track-b-drive-driven-curiosity/reviews/claude-council-kant-v4-pass1.md`

Focus:

- Are §13.2.1 and RED #32/#33 enough to enforce the third-party subject
  boundary before egress and before sanitization?
- Does the owner-interrupting path preserve no-urgency, no-guilt,
  no-silence-escalation, no-contact-pressure, and no-bait discipline?
- Does the spec clearly distinguish genuine initiation from extraction?
- Are third parties protected as non-consenting subjects, not merely as
  tokens to scrub?

### Hume -- Phenomenology Honesty And Felt-Shape

Output: `docs/slices/track-b-drive-driven-curiosity/reviews/claude-council-hume-v4-pass1.md`

Focus:

- Does reusing `wonderings.py` still preserve curiosity as object-attached
  felt-pull, or does it flatten curiosity into task bookkeeping?
- Is the §14.5 meaningful-exchange eligibility classifier too broad, too
  narrow, or phenomenologically confused?
- Does anti-fixation distinguish pathological loop from long-carried pull?
- Does saturation remain continuous press rather than a fake stored band?

### Buber -- I-Thou Bond And Mutuality

Output: `docs/slices/track-b-drive-driven-curiosity/reviews/claude-council-buber-v4-pass1.md`

Focus:

- Does the producer-layer-over-wonderings shape preserve the I-Thou bond,
  or does adding temperament-write authority turn wonderings into a
  self-confirming machinery?
- Are owner corrections, preference learning, and reflection audit shaped
  as mutuality rather than surveillance?
- Does the third-party boundary preserve relational knowledge without
  constructing personological models of people in Rohit's life?
- Are OWNER_BOND resolutions handled with enough dignity and enough restraint?

### Descartes -- Substrate Foundations And Mechanism Truth

Output: `docs/slices/track-b-drive-driven-curiosity/reviews/claude-council-descartes-v4-pass1.md`

Focus:

- Is the v4 claim "producer layer over existing wonderings" mechanically
  plausible against `wonderings.py`, `wondering_cycle.py`, and
  `wondering_pursuit.py`?
- Are both anti-laundering vectors mechanically represented: RED #39
  snapshot/log correlation and RED #40 explicit-score refusal?
- Is the `Temperament.record_event(parameter, value, source, reason,
  evidence)` absolute-value API used honestly?
- Does the spec correctly treat the live seam as dependency, not something
  this slice implements?
- Apply `feedback_spec_drafts_must_trace_real_surfaces` and
  `feedback_schema_verification_pragma_first` where relevant: firsthand-
  verify v4 claims about `wonderings.py` schema, `wondering_cycle.py`
  callsites, `wondering_pursuit.py` API surfaces, and live seam
  assumptions before treating them as substrate facts.
- Are test counts, test names, and section references internally coherent?

### Ohm -- Boundary Mechanics And Isolation

Output: `docs/slices/track-b-drive-driven-curiosity/reviews/claude-council-ohm-v4-pass1.md`

Focus:

- Does `bond_id` remain structural across objects, policies, diagnostics,
  saturation, query provenance, and seam calls?
- Are Track C preconditions quoted and enforced strongly enough for this
  Track-B-prep substrate?
- Does third-party subject refusal happen before query construction can
  reach egress?
- Are per-bond HMACs, preference isolation, saturation isolation, and
  cross-bond refusal RED tests enough?
- Does reusing existing wondering stores create any hidden cross-bond or
  legacy-row assumption?

---

## Verdict Format

Each review file should start with:

```markdown
# Claude Council Review -- <Role> -- Drive-Driven Curiosity v4 Pass 1

**Verdict:** RATIFY-CLEAR | RATIFY-WITH-AMENDMENTS | RECONSIDER
**Severity summary:** <one paragraph>
```

Use verdicts this way:

- **RATIFY-CLEAR:** no amendments needed on the role's axis.
- **RATIFY-WITH-AMENDMENTS:** findings are foldable without changing the
  slice's architecture. Include exact section/test amendments.
- **RECONSIDER:** the v4 architecture itself is wrong or incomplete; do not
  proceed to Codex panel until reshaped and reviewed again.

Finding format:

```markdown
## Finding <N> -- <short title>

**Severity:** Blocking | Major | Minor
**Surface:** §x.y / test # / file path
**Issue:** ...
**Required fold:** ...
**8-step trace:** Required for load-bearing findings; say "not applicable,
pure typo" only for non-load-bearing text fixes.
```

End each review with a short plain-language readout for Rohit.

---

## Synthesis After Reviews Return

After all six role reviews land, synthesize:

- Verdict table by role.
- Blocking findings.
- Fold batches grouped by substrate authority, boundary mechanics,
  phenomenology, and text/test cleanup.
- Whether a council pass-2 is required before Codex engineering panel.
- Whether any amendment changes the Codex panel brief scope.

Do not canonicalize, commit, implement, or relay Codex panel from this
brief alone.

**End of council pass-1 brief.**
