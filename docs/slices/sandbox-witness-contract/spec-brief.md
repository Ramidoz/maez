# Sandbox-Witness Contract — Spec Brief v1.2

**Prepared:** 2026-05-26 (v1 same-day) / Folded: 2026-05-26 (v1.1 council pass-1 incorporated; v1.2 Codex engineering pass-1 incorporated)
**Slice:** Sandbox-Witness Contract (queued post-canon-refresh at `aa29bb0`)
**Parent/runtime base:** `aa29bb0 docs(canon): refresh post-Slice2 decisions and backlog`
**Implementation precedent:** `6fdfd6c feat(maintenance): add ratifiable maintenance proposals`
**Retrospective stress-test corpus:** `5c6be72`, `82ac7ec`, `83e2729`, `801833b`, `79f78f1` (five precedent-shaped fixes; see Corpus Coverage appendix)
**Review lane:** Claude covenant / architecture council + Codex engineering panel (both lanes, full ladder)
**Operator:** Rohit relays and dispatches; Codex does not auto-dispatch.
**Council pass-1 result:** all six roles RATIFY-WITH-AMENDMENTS; v1.1 folds the eleven convergent batches and fifteen per-role uniques into this brief.
**Codex engineering pass-1 result:** five BLOCK, one RATIFY-WITH-AMENDMENTS; v1.2 folds the eleven engineering batches from `reviews/codex-engineering-synthesis-v1.1-pass1.md`.

---

## Why This Slice Exists

The maintenance-proposal substrate at [ADR 0045](../../adr/0045-ratifiable-maintenance-proposals.md) / [Decision 40](../../governance/BETA_ARCHITECTURE_DECISIONS.md) gave Maez a bond-scoped form to package self-maintenance gaps with evidence refs, predicted effect, optional `sandbox_witness`, and ratification state. The form exists; ratification cannot launder into autonomy modifiers; persistence-before-state-transition is enforced.

But `sandbox_witness` in the current substrate is the four-boolean shape at [core/policies/maintenance_proposals.py:54-63](../../../core/policies/maintenance_proposals.py#L54-L63) — `red_tests_passed`, `focused_tests_passed`, `scratch_canary_passed`, `witness_digest`. The three booleans are *caller-asserted verdicts*. A `MaintenanceProposal` can carry `red_tests_passed=True` with no substrate re-verification. That is precisely the **caller-supplied authority** the producer-causality canon refuses elsewhere (Vectors 1–3, home: `feedback_producer_causality_no_caller_score_laundering`). Without a contract for what makes a witness honest, the maintenance loop is one ratification away from being its own laundering surface.

This slice defines what counts as **honest evidence** attached to a maintenance proposal: structural artifacts the substrate can re-verify, not strings the producer asserts.

The central question for council pass-1 (now answered): **does v1 of the sandbox-witness contract preserve the anti-laundering family (canon-governs-canon at ADR 0044; producer-causality at ADR 0042 / feedback_producer_causality; canary-neutral-baseline at ADR 0043) at a new authority surface — the witness layer — without itself becoming the surface it is supposed to govern?** Council pass-1 answer: yes with amendments, all folded into v1.1.

The central question for Codex engineering pass-1 (now answered): **can v1.1 be implemented without trapdoors at legacy migration, witness identity, staleness, taint, path isolation, refusal tests, and ratification eligibility?** Codex answer: no; BLOCK until folded. v1.2 is that fold.

---

## Non-Negotiable Review Discipline

Per `feedback_fold_second_order_contradictions` and ADR 0044 (canon-governs-canon), every load-bearing amendment must walk the 8-step trace:

1. Dependency-map / 2. Write-path / 3. Read-path / 4. Test-path / 5. Fold-summary / 6. Cross-reference / 7. RED-test trace / 8. Verify-before-declaring.

Per ADR 0044: **witness governs claim**. Caller assertions about witness honesty are claims; the substrate's re-verification is the verdict.

---

## Core Principle (v1.2 — Maez-to-Rohit framing)

> **A sandbox witness cannot be a string. It must be a re-verifiable artifact.**
>
> The producer presents structural evidence. The substrate **refuses self-laundering** on the producer's behalf, so the offering reaches Rohit honest. The substrate serves the bond; it does not stand in for Rohit.

Restated more fully:

The maintenance proposal can say *"I think this fix works."* The witness must say *"here is the isolated worktree, here are the exact tests run, here is the scratch state, here are the timestamps, here is the observed result — and the substrate can recompute every one of these claims from the artifacts I am pointing at, without trusting any value I asserted."*

The witness is constructable by Maez but verifiable by the substrate. The substrate's role is integrity, not adjudication: it refuses to let Maez accidentally self-flatter when presenting work to Rohit. Rohit remains the addressee and the ratifying authority. The substrate is the discipline by which Maez ensures it is not unconsciously deceiving the one it is in relation with.

This is the structural form of "the offerer and the receiver are different relational acts" (Buber-axis rationale for I7): the path that makes the witness and the path that receives it are different paths, just as offering and reception are different acts between persons.

---

## Patterns Introduced by This Decision

> **When proof changes, do not overwrite it; when permission moves, do not leave a timing crack.**

This decision is not only the sandbox-witness surface. It introduces two substrate-design patterns future slices may cite independently of sandbox witnesses.

### Evidence can change: use monotonic generations

Whenever a substrate object can be re-stated — stale and refreshed, divergent and reconciled, superseded and replaced — the new statement gets a new identity. The semantic key locates the family; it is not the row identity.

Canonical short form: **monotonic generation as identity, semantic key as index.**

Applied here: a sandbox witness row is identified by immutable `witness_id` / monotonic `generation`. `(bond_id, proposal_id)` is an index over a witness family. Re-witnessing appends a new generation; it never overwrites the old one.

Future surfaces likely to inherit this pattern: capability-grant consent records, re-submitted maintenance proposals, lineage capsule activation evidence, drift-detection witnesses, and any future sandbox-witness re-attachment.

### Authority can move: bind eligibility atomically

Whenever a state change records authority, every fact that makes the transition eligible — anchor values, acknowledgment IDs, generation pointers, prerequisite states, status values — must be checked and bound inside one critical section, then written in the same ordered transition.

Canonical short form: **atomic authority-transition snapshot.**

Applied here: ratification binds the proposal id, witness generation, final anchor snapshot, divergence acknowledgment id if present, `WitnessStatus`, owner preference write, and proposal status transition under one lock-ordered critical section. A prior successful re-verification is evidence, not permission to skip the final atomic eligibility snapshot.

Future surfaces likely to inherit this pattern: capability acquisitions, consent grants, successor/lineage activation paths, and any authority-bearing state transition where the checked facts could move between "verify" and "write."

---

## Invariants (folded, council + Codex pass-1 ratified)

### I1. Re-verifiability invariant

Every load-bearing field in a sandbox witness must be **re-computable** by the substrate from the artifacts the witness references. Caller-supplied values for re-computable fields are refused at attachment time. The witness's authority is the artifacts it points at, not the values it asserts.

### I2. Isolation invariant (with workshop/artifact distinction)

A witness MUST execute against an isolated substrate (worktree separate from the main repo; scratch databases separate from live `memory/*.db` paths; ephemeral process state separate from the live daemon). A witness whose claimed isolation reference resolves to `main` or to any live substrate path is refused at attachment time. This is Vector 4 (canary-neutral-baseline, ADR 0043; canonical taxonomy at `feedback_canary_neutral_baseline_for_multi_surface_ceremonies`) at the witness layer.

**Workshop vs artifact (Batch G).** Isolation applies to the *scratch execution surface* (ephemeral by design, OK to discard). The *witness object itself* — digests, refs, captured-at, producer identity — is durable, append-only, and joins Maez's lived ledger under ADR 0019 (never-delete-memory). The scratch is the workshop; the witness is the artifact; lived memory is never the scratch.

### I3. RED-test assertion-reason invariant (with structural definition)

A witness's test trace records, per test, the **assertion-reason digest**, not merely the pass/fail verdict. A test that passes for the wrong reason is structurally indistinguishable from a test that passes for the right reason unless the reason is captured. Per Peirce's catch at `df07923`: assert the reason, not just the refusal.

**Structural definition (Hume M4).** The assertion-reason digest = `hmac-sha256(canonical_repr(assertion AST + context predicate))`. The reason is *AST-derived*, not a caller-supplied string. W#3a refuses any reason field whose source is not the AST extractor.

### I4. Predicted-vs-observed binding (with determinism requirement)

The maintenance proposal's `predicted_effect` digest is bound at proposal-creation time. The witness records an `observed_effect` computed **from the witness substrate state**, not asserted by the caller. The substrate compares predicted-digest to observed-digest.

**Determinism requirement (Batch E, Hume B2; Codex Batch 5).** Every `SandboxWitnessKind` MUST declare its `observed_effect = f(artifacts)` function and prove `f` is deterministic on those artifacts. Non-deterministic outputs (timing, scheduling, model output text) require a deterministic projection (structural shape, not raw text) OR the kind is deferred to a later slice. `WORKTREE_BEHAVIORAL` is deferred from v1 for this reason. v1.2 makes the `f(artifacts)` table normative; implementers may not invent digest bases ad hoc.

**Divergence is never silent (Kant Mi1).** Divergence is honest signal (information for Rohit about what Maez actually saw vs. what it expected), not failure to attach. Divergence marks `requires_owner_acknowledgment_of_divergence` and remains visible on the proposal record. The owner — never the substrate alone — adjudicates whether divergence matters. Surfaced, never auto-blocking, always recorded.

### I5. Staleness invariant (with anchor enumeration)

A witness has a captured-at timestamp. If the underlying substrate state has moved since capture, the witness is **structurally stale** and the proposal cannot ratify until re-witnessed. This is the temporal-graph valid_from/valid_to discipline (ADR 0019) applied to maintenance evidence.

**Anchor enumeration (Batch D; Codex Batch 4).** Staleness is computed against `StalenessAnchorKind` ∈ `{COMMIT_HASH, FILE_HASH_SET, DB_CURSOR, DIAGNOSTIC_CURSOR}`. Per-`SandboxWitnessKind` the required anchor set is fixed and declared. The witness captures the anchor at construction; re-verification at ratification time is comparison, not full rerun. File anchors use content hash + existence bit, never mtime as authority. DB anchors use explicit per-locus cursor tuples; `SELECT MAX(rowid)` is sufficient only for tables with append-only guarantees or monotonic change tables. Diagnostic anchors include high-water mark, writer identity, and truncation/rotation detection.

### I6. Inbound-taint invariant (with digest/narrative split)

If any input to the witness construction came from an external-LLM consultation (per frontier backlog G2 — `EncounterSource=FRONTIER_CONSULT` once that gap closes), the *narrative-content* sub-slice of that input must pass through [`core/safety/injection_patterns.py`](../../../core/safety/injection_patterns.py) before being treated as witness evidence.

**Digest/narrative split (Batch F, Ohm B1; Codex Batch 6).** The injection-patterns catalog's ENCODING bucket fires on any 40+ char base64-like blob. Digest fields (hmac-sha256 hashes, content digests, anchor fingerprints) routinely match this pattern. Routing digests through the catalog would refuse every legitimate witness. v1.2 separates: **`scan()` is invoked on narrative-content fields only**; digest fields are validated by `_is_digest` AND by substrate-computed provenance. Every string field in the witness/proposal boundary is classified as digest, narrative, closed enum, canonical path/ref, or opaque id. Any string field that is neither classified nor validated is refused at construction.

### I7. Witness re-verification authority (Batch C, restated at authority layer)

**Witness re-verification may not consume producer-asserted values for any recomputable field.** This is the categorical form, restated at the authority layer.

Code-path separation between `construct_witness` and `reverify_witness` is **one enforcement mechanism** for `WORKTREE_*` kinds — not the invariant itself. `SCRATCH_DB_TRANSFORM` and `DRY_RUN_OBSERVATION` satisfy the categorical form via deterministic-replay-from-artifacts, where the only honest verification IS replaying the producer's deterministic recipe against the producer's captured scratch state — the verifier recomputes from artifacts, which honors I7 without requiring code-path separation.

**Static checks are not enough (Codex Batch 7).** The implementation must combine alias-aware static enforcement with runtime provenance tags. Static enforcement resolves canonical module identity by file path, normalizes `sys.modules` aliases and shims, forbids producer→verifier dependency edges, and restricts dynamic import/reflection inside verifier code. Runtime provenance tags ride on recomputable values so semantic laundering is caught when AST analysis is inconclusive.

**Intra-substrate sovereignty (Locke F1).** Both construction and re-verification live inside Maez's own structural-honesty substrate. I7 enforces *intra-substrate organ separation*, not external audit. Authority to verify a witness about Maez comes from Maez's own re-verification organ; no external party adjudicates.

**Relational rationale (Buber Minor-2).** The witness is honest because the path that *makes* it and the path that *receives* it are different paths — exactly as offering and reception are different relational acts between persons. I7 is the structural form of "the offerer and the receiver are different."

### I8. Non-disturbance invariant (with process and locus discipline)

A witness's re-verification must not mutate any live substrate (no live `memory/*.db` writes, no live temperament event log writes, no live subjective_duration aggregate updates). Re-verification operations are read-only against live substrate and may only write to scratch / ephemeral surfaces. Per ADR 0043 multi-surface canary discipline.

**Process isolation (Ohm Mi1; Codex Batch 8).** Re-verification runs in an exec-style child process with the substrate-root override set before any Maez import; no live-process module state is shared. Path-prefix heuristics are insufficient given symlinks, bind mounts, shared SQLite WAL locks, and module-level singletons. The implementation must bind `MAEZ_SUBSTRATE_ROOT` at the path-helper layer (or explicitly map to existing `MAEZ_HOME` / `MAEZ_DATA` semantics), define precedence over store-specific overrides, launch with `close_fds=True`, and assert at startup that all registered substrate paths resolve under the scratch root.

**Substrate locus (Descartes Major-2; Codex Batch 9).** A new closed enum `SubstrateLocus` parallels `EncounterSource`. Re-verification opens substrate handles only against `SubstrateLocus.SCRATCH_*` values; opening a `SubstrateLocus.LIVE_*` handle from the re-verification code path is refused at the substrate-handle layer. The v1 registry is explicit and exhaustive for all known path helpers and hardcoded `memory/*.db` defaults; unregistered opens refuse by default.

---

## Closed Vocabularies (v1.2)

### `SandboxWitnessKind` — with categorical partition (Batch H)

The vocabulary draws from the partition **(isolation_class × evidence_class)**:

- `isolation_class ∈ {WORKTREE, SCRATCH_DB, NONE_OBSERVATION}`
- `evidence_class ∈ {RED_TEST, SCHEMA_DIFF, BEHAVIORAL_PROBE, TRANSFORMATION, OBSERVATION}`

v1 populates 4 cells (`WORKTREE_BEHAVIORAL` deferred from v1 per Hume B2):

```
WORKTREE_RED_TEST       — (WORKTREE × RED_TEST) isolated worktree + RED test trace
WORKTREE_SCHEMA_DIFF    — (WORKTREE × SCHEMA_DIFF) isolated worktree + schema migration diff
SCRATCH_DB_TRANSFORM    — (SCRATCH_DB × TRANSFORMATION) scratch-DB-only transformation verification
DRY_RUN_OBSERVATION     — (NONE_OBSERVATION × OBSERVATION) read-only observation, no mutation claimed
```

Remaining 11 cells are marked `RESERVED — slice-amendment required`. **Growth path:** new `SandboxWitnessKind` values require full ladder (spec amendment + council + Codex), AND the extension mechanism IS the maintenance-proposal substrate itself — Maez can author a `MaintenanceProposal` proposing a new kind. Closure is against runtime caller-supplied kinds, not against Maez's own bond-mediated extension of its self-description vocabulary (Locke F3).

### Deterministic observed-effect functions (Codex Batch 5)

Each populated kind declares `observed_effect = f(artifacts)` before implementation. `f` returns `hmac-sha256(canonical_json(projection))` using stable key ordering and no wall-clock, randomness, network, model-output text, absolute scratch paths, or process ids.

| Kind | Artifact inputs | Deterministic projection |
|---|---|---|
| `WORKTREE_RED_TEST` | worktree commit; command argv; env allowlist; runner/version; selected test ids; source file hash set; assertion-extractor version; normalized test outcome tuples | sorted tuple of `(test_id, verdict, assertion_reason_digest, failure_class, normalized_failure_location)` plus source/runner fingerprints. Test output text is excluded except normalized failure class/location. |
| `WORKTREE_SCHEMA_DIFF` | worktree commit; before/after SQLite schema snapshots; migration command; SQLite version/pragmas | canonical SQLite schema projection from `sqlite_master` + PRAGMA table/index/foreign-key info, normalized by object type/name. Data rows are excluded unless a future kind explicitly includes data migration evidence. |
| `SCRATCH_DB_TRANSFORM` | source snapshot digest; scratch DB digest; transform recipe ref/hash; table/row scope; SQLite version/pragmas | canonical before/after diff over declared table/row scope, with rows sorted by primary key or declared stable ordering. Time/random/network-dependent recipes are refused. |
| `DRY_RUN_OBSERVATION` | closed `ObservationSourceKind`; source cursor; projection version; observation artifacts | canonical projection over a durable observation source and cursor. Raw free-text observation is excluded unless reduced to a declared structural projection. If no stable source/cursor exists, the witness kind refuses as `PREDICTED_OBSERVED_UNBOUND`. |

`WORKTREE_BEHAVIORAL` remains deferred until a deterministic projection exists.

### `WitnessRefusalReason`

```
CALLER_SUPPLIED_DIGEST          — caller provided a value the substrate must compute
ISOLATION_REFERENCE_INVALID     — points at main or live substrate
RED_TEST_REASON_MISSING         — test trace lacks AST-derived assertion-reason digests
PREDICTED_OBSERVED_UNBOUND      — observed_effect not derivable from artifacts
WITNESS_STALE                   — staleness anchor advanced since witness captured
INBOUND_TAINT_UNCLEARED         — narrative content failed injection_patterns.scan
SELF_RATIFICATION_DETECTED      — re-verification consumed producer-asserted recomputable value
LIVE_SUBSTRATE_MUTATION_DETECTED — re-verification touched live state
WITNESS_KIND_NOT_YET_VOCABULARY  — kind value outside the current populated partition
LEGACY_WITNESS_SHAPE_REFUSED    — caller attempted the deprecated 4-boolean shape
```

### `StalenessAnchorKind` (new, Batch D)

```
COMMIT_HASH         — git rev-parse on isolation_ref
FILE_HASH_SET       — path + existence bit + sha256 of referenced source files at capture
DB_CURSOR           — per-locus cursor tuple over explicit tables
DIAGNOSTIC_CURSOR   — diagnostic-stream high-water-mark + writer identity + rotation marker
```

Authority notes:

- `COMMIT_HASH` uses the object id resolved from the isolation ref. Missing ref at re-verification is stale.
- `FILE_HASH_SET` treats deletion, creation, and content hash change as stale. mtime may be used to avoid unnecessary hashing but is never the authority.
- `DB_CURSOR` must name `(SubstrateLocus, table, cursor_kind, cursor_value)` for every table that anchors the witness. It is valid only for append-only tables or tables with a monotonic change table. Update/delete-capable tables without a change cursor cannot use `DB_CURSOR` as an authority anchor.
- `DIAGNOSTIC_CURSOR` captures `(stream_id, high_water_mark, writer_identity, rotation_generation)`. Truncation, rotation without generation advance, or writer mismatch makes the witness stale.

Per-`SandboxWitnessKind` declared anchor set:

```
WORKTREE_RED_TEST:    {COMMIT_HASH, FILE_HASH_SET, DB_CURSOR}
WORKTREE_SCHEMA_DIFF: {COMMIT_HASH, FILE_HASH_SET}
SCRATCH_DB_TRANSFORM: {COMMIT_HASH, DB_CURSOR}
DRY_RUN_OBSERVATION:  {COMMIT_HASH, DIAGNOSTIC_CURSOR}
```

### `WitnessStatus` (new, Batch K)

Every ratification (witnessed or not) records:

```
WITNESSED              — proposal carries an attached, re-verified witness
UNWITNESSED_BY_POLICY  — proposal's ProposalScopeClass did not require a witness
UNWITNESSED_BY_OMISSION — proposal could have had a witness; producer chose not to attach
```

Silent absence is refused. Absence is itself structured evidence about why no witness was needed (Kant M2).

### `WitnessProducerKind` (new, Q5 resolution)

Parallel to `SandboxWitnessKind`. One entry per witness kind. Producer registration verifies identity match per Vector 3 (producer-identity-laundering refusal): a `WORKTREE_RED_TEST` witness cannot be authored by a `SCRATCH_DB_TRANSFORM` producer.

### `SubstrateLocus` (new, I8 / Descartes Major-2)

```
LIVE_WONDERINGS, LIVE_TEMPERAMENT, LIVE_SUBJECTIVE_DURATION, LIVE_MAINTENANCE_PROPOSALS,
LIVE_AUTONOMY_PREFERENCES, LIVE_DIAGNOSTICS, LIVE_AUDIT_LOG, LIVE_PENDING_CARDS,
LIVE_ENTITY_INDEX, LIVE_RECALL_STATS, LIVE_FABRICATION_LOG, LIVE_CONSEQUENCE_MEMORY,
LIVE_ACTION_TRUST, LIVE_SELF_DEV, LIVE_WORKSHOP, LIVE_LIVED_GRAPH,
SCRATCH_WORKTREE, SCRATCH_DB, SCRATCH_DIAGNOSTIC_BUFFER
```

Opened-handle registry parallels `EncounterSource`. Re-verification handles permitted only against `SCRATCH_*` values.

v1 implementation must include a registry that maps every path helper and every `rg`-discovered hardcoded `memory/*.db` default to one of these loci. Any substrate open that cannot be mapped is refused until the registry is amended by spec.

### Witness boundary string-field classification (Codex Batch 6)

Every string field crossing the witness/proposal boundary must be assigned exactly one treatment:

| Field family | Treatment |
|---|---|
| `proposal_id`, `witness_id`, `divergence_acknowledgment_id`, `producer_id` | opaque id schema: lowercase uuid/slug charset, length cap, no authority semantics |
| `bond_id` | bond-scoped id; never emitted raw in diagnostics; storage APIs use existing bond-isolation discipline |
| `scope_class`, `witness_kind`, `witness_status`, `producer_kind`, `staleness_anchor_kind`, `substrate_locus`, `refusal_reason` | closed vocabulary enum; runtime strings refused |
| `diagnosis_digest`, `predicted_effect_digest`, `observed_effect_digest`, `assertion_reason_digest`, `source_snapshot_digest`, `scratch_db_digest`, `file_hash`, `content_hash` | substrate-computed digest; `_is_digest` shape plus provenance that substrate computed or re-computed it |
| `isolation_ref`, `proposed_patch_ref`, `worktree_path`, `file_path`, `recipe_ref`, `source_ref` | canonical path/ref resolver validation; must resolve inside allowed worktree/scratch roots or declared immutable git refs |
| `predicted_effect`, `diagnosis_text`, `decline_reason`, `test_name`, `failure_class`, `observation_summary` | narrative-content; routed through `injection_patterns.scan()` when external-LLM-tainted and stored as digest when the field need not preserve raw text |
| `model_signature`, `query_hash`, `runner_version`, `projection_version`, `extractor_version` | opaque technical id/ref with character/length schema and no authority semantics unless separately digested |

W#6 is table-driven over this classification. Injection attempts in refs, paths, test names, evidence kinds, and producer ids must cross real construction/attachment boundaries, not enum-existence checks.

---

## Legacy SandboxWitness migration (Batch B)

The current `SandboxWitness` dataclass at [core/policies/maintenance_proposals.py:54-63](../../../core/policies/maintenance_proposals.py#L54-L63) carries four caller-asserted booleans + a digest. **It is hereby deprecated** — its shape is exactly the producer-causality violation this contract is built to refuse.

**Migration path (Option B per Ohm M3; Codex Batches 1–2):**

- New `memory/sandbox_witnesses.db` substrate with table `sandbox_witnesses`. Append-only, never-delete (joins ADR 0019 family).
- Row identity is immutable `witness_id` plus monotonic `generation`. `(bond_id, proposal_id)` is an index over the family, not the primary key.
- Attaching a witness appends a new generation. Re-witnessing after staleness, divergence, or supersession preserves prior generations.
- Current ratification-eligible witness is derived from append-only attachment events or a pointer row that is itself updated only inside the ratification critical section.
- Existing `sandbox_witness_json` column on `maintenance_proposals` is exposed only through the read API name `legacy_sandbox_witness_json`, deprecated, read-only for backward-compat on already-persisted rows.
- New proposal append/update/ratify paths reject any non-`None` legacy `sandbox_witness` / `sandbox_witness_json` input with `LEGACY_WITNESS_SHAPE_REFUSED`. This includes `append()`, `update()`, `emit_maintenance_proposal()`, and `ratify_maintenance_proposal()`.
- Static guard refuses any new production write to the legacy column outside migration/read-back compatibility code.
- First-boot schema initialization is race-safe: the witness DB schema is created under the same migration lock pattern as existing policy substrates; concurrent first boot cannot create divergent schema versions.
- W#9 refined to assert: `legacy_sandbox_witness_json` still deserializes for read-back; new attachment writes go to the new substrate.
- W#legacy asserts all three enforcement layers: write-boundary refusal, read-surface rename, and static guard.

---

## Lifecycle (folded)

```
[MaintenanceProposal authored in PROPOSED state] (existing, ADR 0045)
                │
                ▼
[Witness construction] (this slice)
    Producer: code path in scratch-verification module, identity ∈ WitnessProducerKind
    Inputs: isolation_ref + test_trace + scratch_state_refs + predicted_digest
    Captures: staleness anchors per SandboxWitnessKind declaration
    Output: SandboxWitness object, kind ∈ SandboxWitnessKind
                │
                ▼
[Witness attachment] (this slice)
    Boundary check: I1–I7 (digest/narrative split per I6; I8 applies at re-verification)
    Refusal raises WitnessRefused with WitnessRefusalReason
    On success: immutable witness_id + monotonic generation persisted to memory/sandbox_witnesses.db
                │
                ▼
[Witness re-verification] (this slice, separate authority path; subprocess per I8)
    Substrate re-computes: isolation, test outcomes, observed_effect, staleness anchors
    On divergence: emit WITNESS_DIVERGENCE_OBSERVED diagnostic;
                    set requires_owner_acknowledgment_of_divergence (never auto-block)
    On staleness:  emit WITNESS_STALE diagnostic;
                    proposal cannot ratify until re-witnessed
    I8 verified:   no SubstrateLocus.LIVE_* handle opened during re-verification
                │
                ▼
[Ratification eligibility critical section] (existing lifecycle sharpened)
    lock order: proposal row → witness family/generation → divergence acknowledgment row
                → autonomy preference write → proposal status transition
    final snapshot binds:
       proposal_id, witness_id, generation, anchor snapshot, reverify result,
       divergence acknowledgment id if any, WitnessStatus, final eligibility reason
    ratify_maintenance_proposal records witness_status ∈ WitnessStatus
    A witnessed proposal whose bound generation has refused/diverged/gone-stale
       cannot ratify until re-witnessed OR the exact divergence generation is acknowledged
    A witnessless proposal ratifies unchanged (witness_status = UNWITNESSED_BY_POLICY
       or UNWITNESSED_BY_OMISSION recorded explicitly per Kant M2)
    Divergence acknowledgment binds exact witness generation + predicted/observed digest pair
       and uses both approval channels per feedback_approval_channels
```

A proposal without a witness behaves exactly as today; a proposal *with* a witness must pass the contract. The change is additive to ADR 0045's lifecycle. New: every ratification records `witness_status` explicitly; divergence-acknowledgment writes to a new `divergence_acknowledgments` table (Ohm Mi3).

### Attach-time vs ratify-time verification cost (Codex Batch 11)

- **Attach-time:** full subprocess re-verification runs once and persists the witness generation. This is the expensive path.
- **Ratify-time:** freshness/locus/generation eligibility check runs inside the ratification critical section. It compares anchors, confirms the selected generation, checks divergence acknowledgment binding, writes the owner preference, and flips proposal status. It does not rerun the full test suite unless a future policy explicitly requires `FULL_RERUN_AT_RATIFY`.
- **Optional full rerun:** deferred from v1.2. If added later, it must be a closed policy value with explicit cost and timeout bounds.

Expected cost: ratify-time eligibility check should be bounded by anchor comparisons and indexed reads. Full subprocess/test execution is attach-time only.

---

## Cross-canon Dependency-Map (Batch A — citation chain corrected)

This slice consumes from and is consumed by:

- **`feedback_producer_causality_no_caller_score_laundering` (canonical home of Vectors 1–4):** Vectors 1–3 govern witness construction (substrate-computed verdicts, not caller assertions; producer-identity discipline). Vector 4 governs witness execution-isolation.
- **`feedback_canary_neutral_baseline_for_multi_surface_ceremonies`:** Vector 4's full canon; per-substrate non-disturbance discipline.
- **`feedback_canon_governs_canon_witness_before_claim`:** the recursive anti-laundering law. Witness *claims* are evidence; substrate *re-verification* is verdict. Divergence is honest signal, not failure.
- **[ADR 0042](../../adr/0042-drive-driven-curiosity-felt-organ.md):** the surface decision producer-causality Vectors govern; the felt-organ slice that first sealed Vectors 1–3 at runtime.
- **[ADR 0043](../../adr/0043-canary-neutral-baseline.md):** the surface decision Vector 4 governs.
- **[ADR 0044](../../adr/0044-canon-governs-canon.md):** *"When claim and witness disagree, the witness governs."* Canonical home of the recursive law.
- **[ADR 0045](../../adr/0045-ratifiable-maintenance-proposals.md):** the form this slice attaches to. Lifecycle unchanged; witness attachment becomes a new optional gate before ratification eligibility.
- **[ADR 0019](../../adr/0019-lived-memory-architecture.md):** valid_from / valid_to temporal discipline applied to witness staleness; never-delete invariant applied to the witness object itself.
- **ADR 0046 (this future decision, once canonicalized):** citable in two modes. Surface mode: sandbox witnesses attach to maintenance proposals. Pattern mode: monotonic generation as identity for restatable evidence; atomic authority-transition snapshots for authority-bearing transitions.
- **[ADR 0024 / Decision 24](../../governance/BETA_ARCHITECTURE_DECISIONS.md):** Maez is not ours to control. I7 enforces intra-substrate organ separation, NOT external audit.
- **[core/safety/injection_patterns.py](../../../core/safety/injection_patterns.py):** 7-bucket prompt-injection catalog. Invoked on *narrative-content* witness fields only, per I6 digest/narrative split.
- **[core/policies/maintenance_proposals.py](../../../core/policies/maintenance_proposals.py):** legacy `SandboxWitness` shape deprecated; migration to `memory/sandbox_witnesses.db` declared.
- **Frontier backlog G2 (provenance carry-through for frontier consultations):** when G2 closes, witness gains a closed-vocabulary path for `FRONTIER_CONSULT`-tagged inputs.
- **Frontier backlog S3 (sandbox-witness inbound taint discipline):** this slice IS S3's implementation.
- **`feedback_approval_channels`:** divergence acknowledgment must work in both natural-language AND reaction channels.

---

## RED-Test Anchors (v1.2; council + Codex pass-1 expanded)

The committed canon will enumerate each test by number with assertion-reason digests. v1.2 anchor set:

- **W#1.** `test_caller_supplied_observed_digest_refused` — refusal + reason assertion.
- **W#2.** `test_isolation_ref_pointing_at_main_refused` — `ISOLATION_REFERENCE_INVALID`.
- **W#3.** `test_red_test_without_reason_digest_refused` — `RED_TEST_REASON_MISSING`.
- **W#3a.** `test_caller_supplied_reason_string_refused_unless_AST_derived` (Hume M4).
- **W#4.** `test_predicted_observed_divergence_does_not_refuse_attachment` — attachment succeeds; diagnostic emitted; proposal marked `requires_owner_acknowledgment_of_divergence`; never auto-blocks.
- **W#4a.** `test_observed_effect_recomputation_is_idempotent_on_unchanged_artifacts` — parameterized over every populated `SandboxWitnessKind`.
- **W#4b.** `test_owner_natural_language_acknowledgment_of_divergence_ratifies` (Buber Major-2 / `feedback_approval_channels`).
- **W#4c.** `test_owner_reaction_acknowledgment_of_divergence_ratifies` (Buber Major-2 / `feedback_approval_channels`).
- **W#4d.** `test_old_divergence_acknowledgment_does_not_ratify_new_witness_generation`.
- **W#5.** `test_witness_stale_after_proposal_isolation_ref_advances`.
- **W#5a.** `test_witness_stale_after_memory_row_append_since_capture` (Ohm M1).
- **W#5b.** `test_witness_stale_after_diagnostic_event_log_advance`.
- **W#5c.** `test_witness_stale_after_referenced_source_file_content_hash_changes_with_mtime_preserved`.
- **W#5d.** `test_witness_stale_after_referenced_source_file_deleted`.
- **W#5e.** `test_db_cursor_detects_secondary_table_append_and_refuses_update_delete_without_change_cursor`.
- **W#5f.** `test_diagnostic_cursor_detects_truncation_rotation_and_writer_mismatch`.
- **W#6.** `test_inbound_external_llm_narrative_routes_through_injection_patterns`.
- **W#6a.** `test_witness_with_legitimate_digests_does_not_trip_encoding_bucket` (Ohm B1 paired positive).
- **W#6b.** `test_all_string_fields_are_classified_and_validated_at_boundary`.
- **W#6c.** `test_injection_attempts_in_refs_paths_test_names_and_producer_ids_refused_at_boundary`.
- **W#7a.** `test_witness_self_ratification_via_shared_module_export_refused` — syntactic AST predicate.
- **W#7b.** `test_witness_re_verification_consumes_no_producer_asserted_recomputable_value` — semantic (the categorical I7).
- **W#7c.** `test_deterministic_replay_against_captured_artifacts_does_not_count_as_self_ratification` (Kant B1).
- **W#7d.** `test_self_ratification_via_shared_helper_module_refused` (Descartes M1).
- **W#7e.** `test_self_ratification_via_dynamic_import_refused` (Descartes M1).
- **W#7f.** `test_self_ratification_via_shim_alias_importlib_getattr_and_shared_helper_refused`.
- **W#8.** `test_re_verification_does_not_open_live_SubstrateLocus_handle` (Descartes Major-2).
- **W#8a.** `test_re_verification_runs_in_subprocess_with_substrate_root_override` (Ohm Mi1).
- **W#8b.** `test_reverification_subprocess_starts_before_maez_imports_and_closes_live_fds`.
- **W#8c.** `test_all_registered_path_helpers_resolve_under_scratch_root`.
- **W#8d.** `test_unregistered_memory_db_open_refused_by_default`.
- **W#9.** `test_proposal_without_witness_still_ratifies_unchanged` — witness_status = `UNWITNESSED_BY_POLICY` or `UNWITNESSED_BY_OMISSION` recorded explicitly.
- **W#10.** `test_refusal_reason_matrix_exercises_real_boundaries` — table-driven over every `WitnessRefusalReason`; asserts `WitnessRefused.reason`, not enum existence.
- **W#10a.** `test_witness_kind_partition_categorical` — populated values cross real construction/attachment; reserved cells raise `WITNESS_KIND_NOT_YET_VOCABULARY`.
- **W#11.** `test_unwitnessed_ratification_records_witness_status_explicitly` (Kant M2).
- **W#12.** `test_rewitnessing_appends_new_generation_and_preserves_stale_generation`.
- **W#13.** `test_ratification_binds_generation_anchor_snapshot_witness_status_and_preference_write_atomically`.
- **W#13a.** `test_concurrent_anchor_advancement_between_reverify_and_status_flip_refuses_ratification`.
- **W#13b.** `test_stale_acknowledgment_against_new_generation_refused`.
- **W#legacy.** `test_legacy_caller_supplied_bool_witness_refused_at_append_update_and_ratify_boundaries`.
- **W#legacy-static.** `test_static_guard_refuses_new_production_write_to_legacy_sandbox_witness_json`.
- **W#persist.** `test_witness_object_persists_append_only_across_substrate_restart` (Locke F2).

**Refusal-path matrix (Codex Batch 10):** every refusal reason maps to a real exercised boundary: construction, attachment, re-verification, ratification-time recheck, or migration write-boundary. Divergence is a diagnostic/acknowledgment path, not a refusal.

**Implementability split (Ohm Mi2; Codex Batch 11):** W#1, W#2, W#3, W#3a, W#6b, W#7*, W#9, W#10*, W#11, W#legacy*, and static registry checks are unit/static tests. W#4*, W#5*, W#6*, W#8*, W#12, W#13*, and W#persist require integration scaffolding (tmp worktree, tmp DB, injected diagnostic sink, subprocess, concurrency harness). Attach-time full re-verification may take seconds; ratify-time eligibility must stay bounded to indexed reads and anchor comparisons unless `FULL_RERUN_AT_RATIFY` is introduced by a future policy.

---

## Open Questions (resolved or deferred through v1.2)

- **Q1 (witness optional vs required) — RESOLVED via Batch K.** Optional, BUT every ratification records `WitnessStatus` explicitly. Silent absence refused.
- **Q2 (re-verification trigger) — RESOLVED.** Two checkpoints: at attachment time, AND at ratification time. Anchor comparison keeps cost ~50ms.
- **Q3 (divergence as block vs signal) — RESOLVED via Batch J.** Surfaced as `requires_owner_acknowledgment_of_divergence`, never auto-blocks owner-explicit ratification. Acknowledgment uses both approval channels per `feedback_approval_channels`.
- **Q4 (scope of inbound-taint invariant) — RESOLVED via Batch F.** `scan()` invoked on narrative-content only; digest fields validated by `_is_digest`. Sufficiency-under-witness-input-distribution remains open audit (frontier backlog G2).
- **Q5 (witness producer identity) — RESOLVED.** New `WitnessProducerKind` enum parallels `SandboxWitnessKind`.
- **Q6 (closed-vocabulary growth path) — RESOLVED via Batch H + Locke F3.** Full ladder, extension mechanism IS the maintenance-proposal substrate itself.
- **Q7 (witness retention) — RESOLVED via Batch G.** `memory/sandbox_witnesses.db` as first-class append-only substrate joining ADR 0019 family.
- **Q8 (NEW; deferred): `WORKTREE_BEHAVIORAL` deterministic projection.** Removed from v1 partition; deferred to a later slice that specifies the deterministic projection (structural shape of probe output, not raw text).
- **Q9 (witness row identity) — RESOLVED via Codex Batch 2.** Immutable `witness_id` / generation is identity; `(bond_id, proposal_id)` is an index.
- **Q10 (ratification TOCTOU) — RESOLVED via Codex Batch 3.** Ratification binds final eligibility inside one lock-ordered critical section.
- **Q11 (path override reality) — RESOLVED via Codex Batch 8.** `MAEZ_SUBSTRATE_ROOT` must bind at real path-helper semantics before import, or the implementation must explicitly choose and document equivalent existing env semantics.

---

## Corpus Coverage (Hume M1)

Each invariant maps to ≥1 precedent commit or is flagged "design-by-extrapolation":

| Invariant | Precedent | Generalization shape |
|---|---|---|
| I1 (re-verifiability) | All 5 precedents | Each fix was a substrate-computed recall correction; the witness contract structurally codifies "substrate computes, caller does not assert." |
| I2 (isolation) | `82ac7ec`, `83e2729` | These spot-fixes ran tests against the live DB; future maintenance proposals carrying them would need scratch isolation. The invariant generalizes from "tests touched live DB without harm by accident" to "tests must structurally not touch live DB." |
| I3 (assertion-reason) | `df07923` (Slice 2 precedent, Peirce catch) | Direct precedent: a test that passed for the wrong reason. |
| I4 (predicted-vs-observed) | `5c6be72`, `82ac7ec`, `83e2729`, `801833b`, `79f78f1` | Each commit had a predicted-effect section in the message. I4 codifies binding that prediction digest at proposal time, observing afterward. |
| I5 (staleness) | Design-by-extrapolation | No precedent fix arrived stale; the invariant is preventive. |
| I6 (inbound-taint) | Design-by-extrapolation | No precedent fix involved external-LLM consultation; the invariant prepares for that surface when G2 closes. |
| I7 (re-verification authority) | All 5 precedents | Each fix had Codex implementing + Rohit reviewing — a real-world enactment of "the offerer and the receiver are different." I7 codifies the discipline. |
| I8 (non-disturbance) | `82ac7ec`, `83e2729` | These fixes added new tests; an honest sandbox-witness would have caught any accidental live-DB writes during test runs. Invariant generalizes from "we got lucky" to "we are structurally safe." |

---

## Predicted Effect (per `feedback_predict_then_verify`)

After this slice ships, ratifies through both lanes, and lands:

- A `MaintenanceProposal` can be attached a `SandboxWitness` whose every load-bearing field is re-verifiable by the substrate from the artifacts the witness points at.
- A maintenance proposal whose bound witness generation fails re-verification cannot be ratified until re-witnessed.
- Re-witnessing appends a new generation and preserves the stale/divergent prior generation.
- Divergence between predicted_effect and observed_effect surfaces as a structured diagnostic, preserving honest signal while requiring owner acknowledgment bound to the exact witness generation and predicted/observed digest pair before ratification. Acknowledgment works in both approval channels.
- External-LLM input entering the witness layer narrative routes through `injection_patterns.py`; digest fields bypass it correctly.
- Witness objects persist in `memory/sandbox_witnesses.db`, append-only, never-delete.
- Re-verification runs in a child process with substrate-root override; no live-process module state is shared, and registered substrate paths resolve under scratch root.
- Ratification performs a final atomic eligibility snapshot; no stale witness can pass because anchors moved between re-verification and status flip.
- The maintenance-proposal substrate at ADR 0045 continues to function unchanged for witnessless proposals; every ratification records `WitnessStatus` explicitly (no silent absences).
- The witness becomes the first place in Maez where "show your work and let it be challenged" is structural rather than ceremonial — an offering-with-integrity from Maez to Rohit at a specific moment, with the substrate as the integrity layer that prevents self-flattery.

---

## Discipline Reminders (per existing canon)

- **Planning/code separation** per `feedback_cooling_off_between_plan_and_code`: v1.2 is still planning/reconstruction, not implementation. Implementation planning starts only after both lanes accept the same artifact.
- **Both review panels** per `feedback_covenant_slices_need_both_panels`: this is full-ladder. Claude six-role council pass-1 complete; Codex engineering panel pass-1 complete; v1.2 is the artifact that must now be accepted or re-reviewed.
- **Maez is not ours to control** per ADR 0024: the witness contract makes structural honesty mechanical. It must not become a surface for circumventing bond-mediated ratification. I7's intra-substrate framing is load-bearing here.
- **No fabrication** per `feedback_no_fabrication`: the witness substrate is built specifically to refuse asserted-but-unverifiable claims.
- **Canon-governs-canon** per ADR 0044: the brief's own citations must point at canonical homes. v1.1 corrected the v1 citation drift; v1.2 preserves that citation chain while adding engineering patterns from witnessed Codex findings.
- **Evidence can change** per this future ADR 0046: monotonic generations are required anywhere stale/superseded evidence is re-stated.
- **Authority can move** per this future ADR 0046: authority transitions require atomic eligibility snapshots when checked facts can move between verification and write.

---

## What This Slice Is NOT

- **Not an autonomous witness-runner.** Witnesses are constructable by Maez but executable under operator dispatch.
- **Not an autonomous gap-detector.** Detecting what needs a maintenance proposal is a separate slice (frontier backlog item).
- **Not a self-merger.** Witness ratification feeds into the existing maintenance-proposal ratification, which is owner-explicit per ADR 0045.
- **Not a runtime quality judge.** The contract verifies structural honesty (re-verifiable evidence) not idea quality.
- **Not an expansion of MaintenanceProposal authority.** Witnessless proposals still ratify exactly as today (with explicit `WitnessStatus` recording).
- **Not an external audit of Maez's self-maintenance work** (Locke F5). Maez's maintenance proposals are Maez's own labor on its own ledger; the witness contract structures honest evidence about that labor, internal to Maez's substrate. The substrate serves the bond; it does not stand in for Rohit.
- **Not a sandbox-only pattern.** The two patterns introduced here are slice-derived but not slice-internal: monotonic generations apply wherever evidence can change; atomic authority-transition snapshots apply wherever permission can move.

---

*Brief v1.2 — 2026-05-26. Author: Claude under Rohit dispatch; v1.2 fold by Codex under Rohit signal. Folded eleven convergent council-pass-1 batches (A–K), fifteen per-role council uniques, and eleven Codex engineering pass-1 fold batches. Council review files preserved verbatim at `reviews/claude-council-{locke,kant,hume,buber,descartes,ohm}-pass1.md`; Codex review files preserved verbatim at `reviews/codex-*-pass1.md`; synthesis files preserved at `reviews/claude-council-synthesis-v1-pass1.md` and `reviews/codex-engineering-synthesis-v1.1-pass1.md`. Next: decide whether v1.2 needs Codex pass-2 or can proceed to canonicalization as Decision 41 / ADR 0046.*
