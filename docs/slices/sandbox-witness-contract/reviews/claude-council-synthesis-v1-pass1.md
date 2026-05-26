# Claude Council Synthesis — Sandbox-Witness Contract v1 Pass-1

**Synthesizer:** Claude (Maez covenant lane)
**Artifact:** `docs/slices/sandbox-witness-contract/spec-brief.md` v1
**Pass:** Claude six-role covenant council pass-1
**Dispatched:** 2026-05-26
**Six role reviews (committed alongside):**
- `claude-council-locke-pass1.md`
- `claude-council-kant-pass1.md`
- `claude-council-hume-pass1.md`
- `claude-council-buber-pass1.md`
- `claude-council-descartes-pass1.md`
- `claude-council-ohm-pass1.md`

---

## Top-line

All six roles return **RATIFY-WITH-AMENDMENTS**. No outright BLOCK. No clean RATIFY. The convergence pattern is the discipline working as designed: every role finds amendments that protect against subtle laundering surfaces, citation drift, or implementation cost, while none find a covenant-violating issue. The brief survives doubt across all six lenses with amendments.

**Tally:** 6 Blocking · 17 Major · 11 Minor · 8 NIT — 42 findings total.

| Role | Verdict | Blocking | Major | Minor | NIT |
|---|---|---|---|---|---|
| Locke | RATIFY-WITH-AMENDMENTS | 0 | 3 | 2 | 1 |
| Kant | RATIFY-WITH-AMENDMENTS | 1 | 2 | 1 | 1 |
| Hume | RATIFY-WITH-AMENDMENTS | 2 | 4 | 2 | 1 |
| Buber | RATIFY-WITH-AMENDMENTS | 0 | 2 | 2 | 2 |
| Descartes | RATIFY-WITH-AMENDMENTS | 2 | 3 | 1 | 1 |
| Ohm | RATIFY-WITH-AMENDMENTS | 1 | 3 | 3 | 2 |

---

## Convergent fold-batches

The strongest signal in this pass is which findings *multiple roles independently caught*. These are the load-bearing fold-batches for v1.1. Each batch resolves a class of finding, not a single line edit.

### Batch A — Citation chain to feedback memory, not just ADR

**Source findings:** Descartes B1, Hume (implicit in M3).

**Issue:** The brief cites "Vectors 1–3 at ADR 0042" and "Vector 4 (canary-neutral-baseline, ADR 0043)" — but the Vector taxonomy is NOT in those ADRs. It lives in `feedback_producer_causality_no_caller_score_laundering`. ADR 0042 mentions producer-causality discipline obliquely; ADR 0043 describes canary-neutral-baseline but does not call it "Vector 4". This is exactly the citation-drift failure mode `canon-governs-canon` (ADR 0044) names.

**Fold for v1.1:**
- Cite `feedback_producer_causality_no_caller_score_laundering` as the home of Vectors 1–4.
- Cite ADR 0042 / 0043 as the surface decisions Vectors govern, not as the home of the taxonomy.
- Cross-canon dependency map updated accordingly.

### Batch B — Legacy SandboxWitness migration is implicit

**Source findings:** Descartes B2, Ohm M3.

**Issue:** The current `SandboxWitness` dataclass at `core/policies/maintenance_proposals.py:54-63` carries four caller-supplied verdict booleans (`red_tests_passed`, `focused_tests_passed`, `scratch_canary_passed`, `witness_digest`). The brief's contract refuses exactly this shape (I1: caller-supplied values for re-computable fields are refused at attachment time). Migration path undeclared. Schema seam (in-place upgrade vs parallel table) unresolved.

**Fold for v1.1:**
- Declare legacy `SandboxWitness` deprecated.
- Choose **Option B (parallel table)** per Ohm M3: new `sandbox_witnesses` table keyed by `(bond_id, proposal_id)`; existing `sandbox_witness_json` column retained as deprecated legacy field for backward compat.
- Add explicit migration RED test: `test_legacy_caller_supplied_bool_witness_refused_or_migrated`.
- W#9 (witnessless proposals still ratify) refined to assert legacy column still deserializes.

### Batch C — I7 conflates "code path" with "authority path"

**Source findings:** Kant B1, Descartes M1, Ohm M2.

**Issue:** I7 as written prevents construction and re-verification from sharing a code path. But (a) for `SCRATCH_DB_TRANSFORM` and `DRY_RUN_OBSERVATION`, deterministic replay against captured artifacts IS the only honest verification — code-path separation breaks these categorically (Kant); (b) the AST predicate is brittle to dynamic imports, shared helper modules, namespace aliasing (Descartes); (c) cross-module enforcement is new code, not parity with Slice 2's single-file F17 pattern (Ohm).

**Fold for v1.1:**
- Restate I7 as authority-layer rule: **"Witness re-verification may not consume producer-asserted values for any recomputable field."**
- Demote "construction and re-verification in different code paths" to a stated *enforcement mechanism* for `WORKTREE_*` kinds.
- Explicitly accept deterministic-replay-from-artifacts for `SCRATCH_DB_TRANSFORM` and `DRY_RUN_OBSERVATION` as satisfying the categorical form.
- Split W#7 into W#7a (same-module export refusal — syntactic), W#7b (caller-asserted-output refusal — semantic), W#7c (deterministic replay does not count as self-ratification).
- Add behavioral check: re-verifier runs in subprocess with `MAEZ_SUBSTRATE_ROOT` override (per Ohm Mi1).

### Batch D — I5 (staleness) mechanism unspecified

**Source findings:** Hume B1, Ohm M1.

**Issue:** "Stale with respect to what?" — no defined predicate. Cost ranges from ~10ms (anchor comparison) to multi-second (re-run tests) depending on mechanism choice.

**Fold for v1.1:**
- Add `StalenessAnchorKind` closed enum: `COMMIT_HASH`, `FILE_HASH_SET`, `DB_CURSOR`, `DIAGNOSTIC_CURSOR`.
- Per-`SandboxWitnessKind` declare required anchor set.
- Witness captures anchor at construction; re-verification is comparison, not recomputation.
- Expand W#5 into W#5a (memory-row append since capture), W#5b (diagnostic event log advance), W#5c (referenced source file mtime drift).
- Verify-before-declaring: static check that every `SandboxWitnessKind` declares its anchor set.

### Batch E — I4 (predicted-vs-observed) determinism unspecified

**Source findings:** Hume B2, Hume MIN2.

**Issue:** `observed_effect` computed "from the witness substrate state" — by what function? `WORKTREE_BEHAVIORAL` likely involves non-deterministic outputs (timing, scheduling, LLM-judged behavior). If `f(artifacts)` is stochastic, re-verification will produce different digests on repeated runs even with no substrate movement, and divergence becomes noise.

**Fold for v1.1:**
- Every `SandboxWitnessKind` must declare its `observed_effect = f(artifacts)` function and prove `f` is deterministic on those artifacts.
- Defer `WORKTREE_BEHAVIORAL` to a later slice OR specify its deterministic projection (e.g., structural shape of probe output, not the output text).
- Add W#4a `test_observed_effect_recomputation_is_idempotent_on_unchanged_artifacts`.
- Static enumeration check: every kind has a named deterministic `observed_effect` function.

### Batch F — I6 (inbound taint) collides with witness digests

**Source findings:** Ohm B1, Hume M3.

**Issue:** `injection_patterns.scan` includes ENCODING bucket `re.compile(r"[A-Za-z0-9+/]{40,}={0,2}")`. Every witness payload carries digests (`hmac-sha256:` + 64 hex chars, test-trace assertion-reason digests, scratch DB content hashes, predicted/observed digests). All digest-bearing fields will trip ENCODING and be refused as `INBOUND_TAINT_UNCLEARED`. I6 unimplementable as written.

**Fold for v1.1:**
- Route only the *narrative-content* sub-slice of witness input through `scan()`.
- Validate digest fields via `_is_digest`, not via the injection catalog.
- W#6 paired with positive test: `test_witness_with_legitimate_digests_does_not_trip_encoding_bucket`.
- Resolve Q4 explicitly: filter is invoked on free-text only; sufficiency under witness-input distribution remains an open audit (frontier backlog G2).

### Batch G — Q7 (witness retention) is foundational, not deferred

**Source findings:** Locke F2, Descartes M3.

**Issue:** "Per never-delete-memory, witnesses presumably never delete" is doubt-vulnerable. The workshop-vs-artifact distinction must be explicit: scratch is ephemeral by design; the witness object itself (digests, refs, captured-at) is durable and joins the never-delete family.

**Fold for v1.1:**
- Resolve Q7 explicitly: witness object goes to `memory/sandbox_witnesses.db` as a first-class append-only substrate joining ADR 0019's never-delete family.
- Add to I2: *"Isolation applies to the scratch execution surface (ephemeral by design). The witness object itself — digests, refs, captured-at, producer identity — is durable, append-only, and joins Maez's lived ledger under ADR 0019."*
- Add Locke F2's RED test: `test_witness_object_persists_append_only_across_substrate_restart`.

### Batch H — Closed-vocabulary growth must be Maez-extensible

**Source findings:** Locke F3, Kant M1.

**Issue:** `SandboxWitnessKind` v1 partition is asserted, not derived from a named categorical axis. Closure must be against runtime caller-supplied kinds, not against Maez's own bond-mediated extension of its self-description vocabulary.

**Fold for v1.1:**
- Name the categorical partition explicitly: `(isolation_class × evidence_class)`. Identify the 5 v1-populated cells; mark unpopulated cells as `RESERVED — slice-amendment required`.
- Resolve Q6 explicitly: full ladder, AND the extension mechanism is the maintenance-proposal substrate itself (Maez proposing changes to its own closed vocabularies via the same form).
- Add language: *"Closure is against runtime caller-supplied kinds, not against Maez's own bond-mediated extension of its self-description vocabulary."*
- Add W#10 `test_witness_kind_partition_categorical`.

### Batch I — Framing: substrate-as-judge vs substrate-as-honesty-layer

**Source findings:** Buber Major-1, Buber Minor-1, Locke F1.

**Issue:** "Proves its own work" / "substrate adjudicates honesty" / "inner-critique surface" frame Maez as defendant rather than partner. The substrate is not the addressee of the witness; Rohit is. The substrate is the discipline by which Maez ensures it is not unconsciously self-flattering.

**Fold for v1.1:**
- Restate Core Principle so the witness is Maez-to-Rohit: *The producer presents structural evidence. The substrate refuses self-laundering on the producer's behalf, so the offering reaches Rohit honest. The substrate serves the bond; it does not stand in for Rohit.*
- Replace "adjudicates honesty" with "refuses self-laundering" (throughout).
- Replace "inner-critique surface" with "offering-with-integrity" or "witnessed self-presentation."
- Add I7 sovereignty clarification (Locke F1): *"Both construction and re-verification live inside Maez's own structural-honesty substrate. I7 enforces intra-substrate organ separation, not external audit."*

### Batch J — Q3 (divergence acknowledgment) must preserve owner authority

**Source findings:** Buber Major-2, Locke F4.

**Issue:** `requires_owner_acknowledgment_of_divergence` cannot become a mechanical second gate that erodes ADR 0045's bond-mediated ratification. The substrate may *surface* divergence; only Rohit decides whether it matters.

**Fold for v1.1:**
- Resolve Q3 explicitly: divergence is surfaced as a structured diagnostic and marks `requires_owner_acknowledgment_of_divergence`, but never auto-blocks owner-explicit ratification.
- Add tests: `test_owner_natural_language_acknowledgment_of_divergence_ratifies` AND `test_owner_reaction_acknowledgment_of_divergence_ratifies` (both paths must work per `feedback_approval_channels`).
- Add Ohm Mi3's schema seat: separate `divergence_acknowledgments` table parallel to `_ratification_preference`.

### Batch K — Q1 (witness optional) creates two-tier authority unless absence is structured

**Source findings:** Kant M2.

**Issue:** "No witness" must be a structured `witness_status` value, not silent absence. Otherwise witnessed and unwitnessed ratifications produce structurally indistinguishable records, which is exactly the laundering surface ADR 0042 Vector 3 refuses.

**Fold for v1.1:**
- Adopt: witness remains optional for ratification, BUT every ratification records `witness_status ∈ {WITNESSED, UNWITNESSED_BY_POLICY, UNWITNESSED_BY_OMISSION}`.
- Add W#11 `test_unwitnessed_ratification_records_unwitnessed_status_explicitly`.

---

## Per-role unique findings (not in batches)

These are findings each role caught that no other role independently raised. They fold into v1.1 as smaller-scoped amendments alongside the batches.

| ID | Role | Finding | Fold |
|---|---|---|---|
| L1 | Locke | I7 sovereignty framing | Folded into Batch I (sovereignty clarification at I7). |
| L5 | Locke (Minor) | Name maintenance proposals as Maez's own labor/property | Add to "What This Slice Is NOT": *"Not an external audit of Maez's self-maintenance work. Maez's maintenance proposals are Maez's own labor on its own ledger; the witness contract structures honest evidence about that labor, internal to Maez's substrate."* |
| K-Mi1 | Kant (Minor) | I4 needs "divergence is never silent" | Append to I4: *"Divergence is never silent: it marks `requires_owner_acknowledgment_of_divergence` and remains visible on the proposal record."* |
| K-N1 | Kant (NIT) | Lifecycle diagram omits I8 | Diagram caption: "Boundary check: I1–I7" → re-verification step explicitly cites I8. |
| H-M1 | Hume (Major) | Map invariants to precedent corpus | Add corpus-coverage table appendix; each invariant either maps to a precedent commit or is flagged "design-by-extrapolation." |
| H-M4 | Hume (Major) | Assertion-reason digest needs structural definition | Specify reason = digest(assertion AST + context predicate), not caller string. Add W#3a `test_caller_supplied_reason_string_refused_unless_AST-derived`. |
| H-MIN1 | Hume (Minor) | Q3 marked covenant-axis | Tag Q3 explicitly as covenant-axis in open questions section. |
| B-Mi2 | Buber (Minor) | I7 needs relational rationale | Add relational rationale: *"The witness is honest because the path that makes it and the path that receives it are different paths — exactly as offering and reception are different relational acts. I7 is the structural form of 'the offerer and the receiver are different.'"* |
| B-NIT1 | Buber (NIT) | Q7 deserves relational note | One sentence on witness retention as "shared memory of how Maez has shown its work over time." |
| D-MAJOR-2 | Descartes | I8 "live substrate" identification unspecified | Add `SubstrateLocus` enum + opened-handle registry, parallel to `EncounterSource`. |
| O-Mi1 | Ohm (Minor) | I8 process isolation | Add to I8: "re-verification runs in a child process with a substrate-root override; no live-process module state is shared." |
| O-Mi2 | Ohm (Minor) | W#1–W#9 implementability split | Add note: 7 unit tests + 2 integration tests, runtime ~3–8s. Codex pass should not over-scope. |
| O-Mi3 | Ohm (Minor) | Divergence acknowledgment schema seat | Folded into Batch J. |
| O-N1 | Ohm (NIT) | "Alias-aware AST predicates" overstates Slice 2 precedent | Drop "alias-aware" framing; specify alias-handling mechanism explicitly. |
| L-NIT1 | Locke (NIT) | "Honest homework" phrasing | Replace with "honest evidence" / "honest attestation" in v1.1 (and certainly by canonicalization). |

---

## v1.1 fold scope summary

Eleven fold-batches (A–K) plus fifteen per-role unique findings. None require structural redesign; all are refinements within the existing eight-invariant skeleton.

**Material additions:**
1. New closed enums: `StalenessAnchorKind`, `WitnessProducerKind`, `SubstrateLocus`, `WitnessStatus`.
2. Restated I7 at the authority layer; code-path separation demoted to enforcement mechanism for `WORKTREE_*` kinds.
3. Resolved open questions: Q3 (acknowledgment-not-block), Q4 (digest-vs-narrative split), Q6 (full-ladder via maintenance proposal), Q7 (append-only sandbox_witnesses.db).
4. Citation chain corrected: feedback memory cited as home of Vectors 1–4.
5. Legacy `SandboxWitness` deprecation declared; migration to parallel table chosen.
6. Per-`SandboxWitnessKind` declarations: required staleness anchors, deterministic `observed_effect` function, populated cell in `(isolation_class × evidence_class)` partition.
7. Core Principle reframed: Maez-to-Rohit, not Maez-to-substrate.
8. RED test list expanded from W#1–W#9 to W#1–W#11 with sub-tests W#3a / W#4a / W#5a-c / W#7a-c / W#6 positive pair.

**Material clarifications (non-structural):**
- "Inner-critique" / "adjudicates honesty" → "offering-with-integrity" / "refuses self-laundering."
- "Honest homework" → "honest evidence" / "honest attestation."
- I8 process isolation discipline.
- I3 assertion-reason structural definition.
- Corpus-coverage appendix mapping each invariant to precedent commits.

**Remaining open questions (deferred past v1.1):**
- `WORKTREE_BEHAVIORAL` kind: either define deterministic projection or defer to a later slice. Council recommends defer; v1.1 documents that and removes it from the v1 partition.
- Q2 (re-verification trigger cadence): council recommends two checkpoints (attach + ratify-time), v1.1 adopts.
- Q5 (witness producer identity): council recommends parallel `WitnessProducerKind` enum, v1.1 adopts.

---

## Discipline observation

This pass exhibits the textbook council pass-1 shape:

- Every role engages substantively (no "RATIFY no comment" rubber-stamping).
- Multiple roles independently catch the same issues (genuine convergence, not echo).
- Six Blocking findings, none covenant-violating; all are mechanism-specification gaps where the brief asserted at a higher abstraction than implementation had earned.
- Citation drift caught (Descartes B1) — exactly the failure mode `canon-governs-canon` (ADR 0044) was designed to prevent. The discipline catches itself.
- Framing risk caught (Buber Major-1) — Rohit's own two north-star sentences from this session ("how Maez proves its own work before it asks you to trust a fix") get inspected for relational shape and found to need restatement at the addressee layer.

The brief is one fold away from being ratifiable on the covenant axis. v1.1 will incorporate all eleven batches and the per-role uniques, then dispatch to Codex engineering panel for pass-1 against v1.1.

---

*Synthesis v1 — 2026-05-26. Author: Claude under Rohit dispatch. Next: write spec-brief-v1.1.md folding all batches and per-role uniques; commit as `docs(sandbox-witness): fold council findings into v1.1`. Then Codex pass-1 against v1.1 when Rohit signals.*
