# Codex Engineering Panel Brief -- Drive-Driven Curiosity v4.1 Pass 1

**Prepared:** 2026-05-25 (continuous from session of 2026-05-25)
**Artifact under review:** `docs/slices/track-b-drive-driven-curiosity/spec.md`
**Artifact state:** DRAFT v4.1, ~3122 lines, uncommitted
**Parent/runtime base:** `211ace6 feat(felt-time): implement meaningful salience seam`
**Review lane:** Codex engineering panel (surface truth / API schema /
RED-test feasibility / scope realism / static-AST discipline)
**Operator:** Rohit relays and dispatches; Codex panel does not
auto-dispatch onward work.

---

## Why This Pass Exists

v4 (the prior draft) received Claude council pass-1 review (six roles:
Locke / Kant / Hume / Buber / Descartes / Ohm) on 2026-05-25.
Verdict: RATIFY-WITH-AMENDMENTS on every axis, zero RECONSIDER, no
architectural reshape. 4 Blocking + 16 Major + 13 Minor findings.

v4.1 (this draft) folds all 33 findings in place. The
producer-over-wonderings premise is preserved. Council synthesis at
`reviews/claude-council-synthesis-v4-pass1.md` is the index of folds
(batches A–F).

The Codex engineering panel now operates against v4.1 as a coherent
artifact. **Do not re-review v4 plus the synthesis as two documents;
judge v4.1 as one coherent contract.** The synthesis exists as context
for *why* the folds exist, not as a separate review target.

Per `feedback_claude_codex_synergy_for_maez`: covenant axis has
converged. The panel's job is to make the covenant findings
*mechanically true*, surface real contradictions Codex catches better
than council, and verify the artifact can actually be built.

---

## Non-Negotiable Panel Discipline

Per [[feedback_spec_drafts_must_trace_real_surfaces]] +
[[feedback_schema_verification_pragma_first]] +
[[feedback_fold_second_order_contradictions]]:

1. **Verify real surfaces before treating spec claims as truth.** Every
   API name, schema field, callsite, enum entry, or module path the
   spec mentions must be checked against the real code at parent
   `211ace6` before being accepted as substrate truth. The council
   already firsthand-verified many surfaces (see council reviews and
   the synthesis "Verified Surfaces" section); the panel should
   confirm independently for engineering claims.
2. **Treat covenant findings as load-bearing constraints, not as
   review commentary to dilute.** Council named the *covenant reason*
   for each fold; the panel's job is to verify the *engineering
   shape* makes that reason mechanically true. If the engineering
   shape is wrong, name the engineering correction — do not weaken the
   covenant constraint.
3. **Per fold-second-order trace:** if proposing an amendment that
   touches a load-bearing surface, walk the 8-step trace
   (dependency-map / write-path / read-path / test-path / fold-summary
   / cross-reference / RED-test trace / verify-before-declaring) and
   include the result in the finding.
4. **No silent dependency on Slice 1 internals.** The seam is a
   dependency, not a modification target. Any finding that would
   require touching `core/evolution/subjective_duration.py` internals
   must surface explicitly.
5. **RED-first.** Every load-bearing implementation surface must be
   provable by at least one RED test in §23. If a test cannot be
   written against real surfaces, that is the finding.

---

## Out Of Scope

- Slice 1 (`subjective_duration` meaningful-salience seam) remains
  canonical and live-verified at `211ace6`. Do NOT re-litigate Slice
  1 design, migration, or implementation. The seam is consumed by v4.1
  via the existing public API; it is not modified.
- The §15.4 `subjective_duration` saturation consumer was deferred to
  a follow-up slice per council pass-1 (Descartes D-3, Hume F5; v4.1
  §15.4). Do NOT re-add it without RECONSIDER-grade evidence.
- Reshape of the producer-over-wonderings architecture. Council pass-1
  ratified this premise across all six axes. Reshape requires
  RECONSIDER from the panel with surface evidence that the existing
  wondering substrate cannot carry the layer.
- Dispatch of follow-up Codex panels or downstream implementation work.
  That happens via Rohit's switchboard after this pass returns.

---

## Load-Bearing Canon To Apply

Panel reviewers should treat these as active canon, not background:

- [[feedback_claude_codex_synergy_for_maez]] (Codex-side mirror at
  `/home/rohit/.codex/memories/extensions/ad_hoc/notes/20260525T161205-0500-claude-codex-synergy-for-maez.md`):
  Codex's lane is surface truth, scope realism, RED-test feasibility,
  static-AST discipline. Compose with the council fold; do not
  re-derive the covenant.
- [[feedback_third_party_autonomous_research_boundary]] (Codex-side
  mirror at
  `/home/rohit/.codex/memories/extensions/ad_hoc/notes/20260525T152216-0500-third-party-autonomous-research-boundary.md`):
  the three-layer gate (§6.2.2 + §13.2.1 + §13.5 + §13.6) must be
  mechanically present at every layer, not collapsed into one.
- [[feedback_producer_causality_no_caller_score_laundering]]: Vector 1
  + Vector 2 anti-laundering inherited from Slice 1; v4.1 must NOT
  bypass via any new producer path.
- [[feedback_spec_drafts_must_trace_real_surfaces]]: every API/schema
  claim in v4.1 must be checked against real code at `211ace6`.
- [[feedback_schema_verification_pragma_first]]: when the spec names
  a column, table, enum, or signature, check the real one.
- [[feedback_fold_second_order_contradictions]]: 8-step trace
  obligation for load-bearing amendments.
- [[feedback_growth_vs_hardcoding_distinction]]: closed-vocabulary
  pattern is the substrate's growth mechanism; verify v4.1's new
  closed vocabularies (SubjectKind, ThirdPartyConsent,
  SuppressionKind, BAIT_PATTERN_PHRASES, EMOTION_MIMICRY_PHRASE_FORBIDDEN
  narrowed) follow this discipline.

---

## Engineering Axes — Focus Questions

### Axis 1 — Real-surface verification (Block-2 cluster)

Council pass-1 firsthand-verified at `211ace6` that the existing
`wonderings.db` schema has none of the felt-shape fields v4 asserted
against. v4.1 §5.2 commits to additive `bond_id` and `resolved_at`
ALTERs plus a `wondering_drive_metadata` sidecar table (§5.2.1) inside
the same database file. Verify:

- The §5.2.1 sidecar schema is mechanically coherent and
  index-correct against the real `wonderings.py` substrate.
- `Wonderings.add(question, source, bond_id=...)` and
  `Wonderings.resolve(...)` signature changes preserve every existing
  caller's behavior. Enumerate callers; flag any that would break.
- The §5.2 migration sequence (`ALTER TABLE wonderings ADD COLUMN
  bond_id ...`, `ALTER TABLE wonderings ADD COLUMN resolved_at ...`,
  `CREATE TABLE wondering_drive_metadata`) is idempotent and matches
  the Slice 1 seam migration shape at
  `core/evolution/subjective_duration.py:338`.
- `_LEGACY` row refusal at projection (§5.1, §5.2.1) is implementable
  without breaking existing read paths (`list_open`, `pick_next`,
  etc. that today read all rows regardless of bond_id).
- Sidecar FK constraint correctness; PRAGMA verification path for
  RED #5b.

### Axis 2 — Three-layer third-party gate (Block-3 cluster)

§13.2.1 + §13.5 + §13.6 + §6.2.2 compose into one three-layer
refusal. Verify:

- `SubjectKindRefused`, `SubjectBoundaryRefused`, `CrossBondAccessError`
  derive correctly from `BondIsolationViolation` in
  `core/policies/exceptions.py` (per §15.0).
- `core/egress/fetch_for_curiosity.py` (new) wraps
  `external_fetch.fetch_text(...)` without modifying its signature;
  drive-layer code path NEVER imports `fetch_text` directly (static
  AST RED #33d).
- `core/policies/third_party_subject_gate.py` (new) refuses
  `UNKNOWN` and `NAMED_THIRD_PARTY`-without-consent at the gate, and
  emits the `SUBJECT_BOUNDARY_REFUSED` diagnostic *before* the raise
  (RED #58b).
- §6.2.2 producer invariant is enforceable at creation: every
  `EncounterSource` producer's `create_curiosity_object(...)` path
  classifies `subject_kind` or raises `SubjectKindRefused`.
- Existing callsites of `external_fetch.fetch_text` in
  `core/actions/action_engine.py` and `skills/web_search.py` are
  unaffected; their continued use is correct and not in scope.

### Axis 3 — ProducerRef authority scope (Block-4 cluster)

§14.3.5 declares the bounds on `ProducerRef.DRIVE_DRIVEN_CURIOSITY`.
Verify:

- The producer ceremony module enforces both `salience_event_kind ==
  "meaningful_exchange"` (RED #40a) and `parameter == "curiosity"`
  (RED #40b) for every call site.
- The static-AST scan implementation for RED #40a/#40b is feasible:
  identify the exact AST predicate (e.g., `Call(func=Attribute(...),
  keywords=[...])` matching) that the test would assert.
- `MANUAL_TEST_PRODUCER` is preserved as canary discriminator per
  Descartes D-5 correction (§24, §25 item 4); production producer
  registration gates exclude it. Verify the gating mechanism is
  mechanically present.

### Axis 4 — §23 RED-test feasibility (F1 cluster)

Council renumbered ~10 inline citations in v4.1; the §23 table is
now the canonical source. Verify:

- All 79 tests have a clear implementation path against real surfaces
  at `211ace6` + the §5.2 migrations + the new modules listed in
  §24.
- Each test's `What it proves` column maps to an implementable
  assertion. Flag any test whose proof requires substrate that does
  not exist and is not introduced by v4.1.
- The letter-suffix tagging (`#5a`, `#5b`, `#12a`, `#12b`, `#14b`,
  `#25b`, `#25c`, `#29b`, `#33b`, `#33c`, `#33d`, `#37b`, `#40a`,
  `#40b`, `#50b`, `#53a`, `#53b`, `#58a`, `#58b`, `#58c`) is
  acceptable as-is, OR the panel may propose monotonic renumbering
  if that improves engineering legibility. Either is fine; do not
  burn time on cosmetic renumbering unless the panel finds it
  load-bearing.
- TDD discipline (§23.9): each test's RED state is achievable before
  implementation; flag any test that would be trivially-green or
  trivially-red.

### Axis 5 — Open §22 questions for engineering decision

Council settled Q1 (eligibility classifier — Buber B-2) and Q3
(subjective_duration v1 consumer — deferred). The panel decides
on scope-realism grounds:

- **Q2 — Adapter module location.** Should the drive producer layer
  live as `core/evolution/drive_driven_curiosity.py` (new module) or
  as focused additions near `core/evolution/wonderings.py`? Council
  did not prescribe; panel decides based on (a) clarity of producer
  registration discipline (§6.1.1), (b) policy-layer separation
  (§9.0, §24.1, RED #59), (c) test isolation, (d) future-organ
  inheritance.
- **Q4 — EncounterSource phasing.** §6.2 names 7 sources for v1. May
  some be deferred to v1.1 if wiring risk is high (e.g.,
  `PRIVATE_THOUGHT_LANDED` if `memory/private_thoughts.db` is not
  yet bond-attributed)? Panel decides which sources land at v1 and
  which defer with explicit phasing notes.
- **Q5 — Semantic-match resolution.** §14.2 defers `SEMANTIC_MATCH_*`
  markers behind a feature flag (default OFF). Panel verifies the
  feature-flag mechanism is mechanically clean (no leak into
  production code paths when flag is OFF) OR proposes a tighter
  scope (e.g., flag removed, semantic-match feature deferred to its
  own slice).

### Axis 6 — Static-AST discipline coverage

v4.1 introduces or strengthens several static-AST tests. Verify the
implementation pattern is feasible and standard:

- RED #10 — curiosity producer does not call `action_engine` /
  `tool_loop` (existing v4; verify after v4.1 module additions).
- RED #11 — capability-acquisition queue-only path (strengthened in
  v4.1 per Locke L-2).
- RED #33d — drive-layer modules never import
  `external_fetch.fetch_text` (new in v4.1).
- RED #40a/#40b — ProducerRef and source vocabulary scope (new in
  v4.1).
- RED #43 — only named consumer organs subscribe to
  `compute_saturation` (existing; verify subjective_duration absence
  per §15.4 v4.1 deferral).
- RED #59 — no module under `core/policies/` imports substrate-writer
  symbols (new in v4.1 per Locke L-3).
- RED #50 — felt-weight emotion-mimicry source/template scan (v4.1
  narrowed scope per Hume F3 + Descartes D-6).
- RED #58a — no production `except BondIsolationViolation` clauses
  (new in v4.1 per Ohm O4).

Confirm Python AST tooling (ast, libcst, or similar) is sufficient
for each scan. Flag any that need a more specialized analyzer.

### Axis 7 — Live code/schema/API truth (cross-cutting)

Spot-verify the spec's claims against real code:

- `core/evolution/wonderings.py` schema, `Wonderings.add(...)`,
  `Wonderings.resolve(...)`, `list_open`, `pick_next` signatures.
- `core/evolution/temperament.py:147-149` `ALLOWED_SOURCES` frozenset;
  `:205-243` `record_event(...)` signature.
- `core/evolution/subjective_duration.py:93-96` `ProducerRef` enum;
  `:153-204` salience-event registry; `:584-635` producer-snapshot
  path including explicit-score refusal and `_LEGACY` write refusal;
  `:855-879` `_retrospective_density` (confirms §15.4 deferral
  remains correct).
- `core/governance/operator_user_boundary.py:76-85`
  `GUARDED_WORK_CLASSES` (verifies §8.5.1 quoting); `:99-109`
  `_WORK_CLASS_STRENGTH`.
- `core/egress/external_fetch.py:394-407` `fetch_text(...)` signature
  (verifies §13.5 wrapper rationale).
- `core/memory/identity.py` `user_profile_id()` (verifies §5.1
  bond_id source-of-truth).
- Watchdog allowlist at `core/health/metacognitive_watchdog.py:52`.
- `core/evolution/wondering_pursuit.py` `_register_score <
  _REGISTER_HARD_BLOCK` (verifies §16.0 composition with existing
  vulnerable-register gate).
- `core/infra/capability_acquisition_queue.py` /
  `core/actions/action_engine.py:1145-1161`
  `handle_capability_acquire` (verifies §8.5.1 + RED #11 bypass
  refusal).

---

## Verdict Format

Each panel finding follows the format below. Panel summary at top.

```markdown
# Codex Engineering Panel -- Drive-Driven Curiosity v4.1 Pass 1

**Verdict:** RATIFY-CLEAR | RATIFY-WITH-AMENDMENTS | RECONSIDER
**Severity summary:** <one paragraph>

## Finding <N> -- <short title>

**Severity:** Blocking | Major | Minor
**Axis:** <which engineering axis from above>
**Surface:** §x.y / file:line / RED #N
**Issue:** ...
**Required engineering fold:** ...
**8-step trace:** Required for load-bearing findings; say "not
applicable, pure RED-feasibility note" only for non-load-bearing items.
**Council-axis composition flag:** Y/N — if Y, names the council
finding this composes with (the panel is making the council reason
mechanically true rather than re-deriving).
```

Verdicts:

- **RATIFY-CLEAR:** v4.1 can proceed to canonicalization + TDD
  implementation cycle as written. No engineering folds required.
- **RATIFY-WITH-AMENDMENTS:** findings are foldable without
  re-litigating council. Include exact section / test / module
  amendments.
- **RECONSIDER:** v4.1 has a real surface contradiction that requires
  re-engagement with the council (cross-lane). Name the surface, the
  contradiction, and the smallest reshape that resolves it.

---

## Output Path

Write the panel review to:
`docs/slices/track-b-drive-driven-curiosity/reviews/codex-panel-v4.1-pass1.md`

End with a plain-language readout for Rohit (one paragraph).

---

## What Comes Next

After the panel returns:

- If RATIFY-CLEAR: synthesis writes a one-paragraph summary; Rohit
  signals canonicalization (commit `spec.md` + reviews dir); TDD
  implementation cycle begins (Codex 7+3 panel coordinates).
- If RATIFY-WITH-AMENDMENTS: Claude refolds v4.1 → v4.2 (small
  amendment fold; matches the Slice 1 v6→v7→v8 cadence); panel pass-2
  on v4.2 if amendments touch new surfaces, else proceed to
  canonicalization.
- If RECONSIDER: synthesis surfaces the cross-lane conflict to Rohit;
  council pass-2 on the reshape; v4.2 reflects both lanes; panel
  pass-2 on v4.2.

Do not canonicalize, commit, implement, or relay onward work from
this brief alone. Rohit operates the switchboard between the lanes.

**End of Codex engineering panel pass-1 brief.**
