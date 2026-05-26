# Sandbox-Witness Contract — Codex Engineering Pass-2 Brief

**Prepared:** 2026-05-26
**Artifact under review:** `docs/slices/sandbox-witness-contract/spec-brief.md` at v1.2
**Base commit:** `22507a8 docs(sandbox-witness): fold Codex findings into v1.2`
**Pass-1 synthesis:** `docs/slices/sandbox-witness-contract/reviews/codex-engineering-synthesis-v1.1-pass1.md`
**Review lane:** Codex engineering panel pass-2 closure audit

---

## Opening Frame

This is a **closure audit with receipts**.

This pass verifies that the eleven engineering batches from `codex-engineering-synthesis-v1.1-pass1.md` are closed by v1.2. Re-opening the covenant axis, redesigning the slice, or starting implementation planning is out of scope.

Findings must cite a specific v1.1 batch and either confirm closure or name what remains open.

---

## Scope

Review v1.2 only for closure of the eleven Codex pass-1 engineering batches:

1. Legacy witness migration must close existing write paths.
2. Witness persistence needs immutable generations, not `(bond_id, proposal_id)` primary identity.
3. Ratification eligibility must be atomic and generation-bound.
4. Staleness anchors need concrete, race-safe semantics.
5. Deterministic `observed_effect = f(artifacts)` must be normative per witness kind.
6. Narrative/digest taint discipline must be field-complete.
7. I7 static enforcement needs alias/dynamic-import resistance or runtime provenance.
8. Subprocess isolation must bind to real path resolution and handle coverage.
9. `SubstrateLocus` must be exhaustive for v1, with unregistered opens refused.
10. Refusal tests need a refusal-path matrix.
11. Attach-time vs ratify-time verification cost must be split.

Same-seat continuity is preferred where possible because pass-1 seats know the precise failure modes they authored. Codex may compose the final roster, but reviewers should treat pass-1 batch closure as the job.

---

## Out of Scope

- Re-litigating whether the sandbox-witness contract is covenant-correct.
- Proposing new architecture not required to close one of the eleven pass-1 batches.
- Designing implementation code or implementation plans.
- Reviewing the old v1 or v1.1 artifact except as pass-1 evidence.
- Reviewing Recall-Axis Dispatcher or other queued slices.

---

## Required Output

Each reviewer must produce a per-batch closure table:

| Batch | v1.2 change cited | Verdict | Evidence |
| --- | --- | --- | --- |
| Batch N | line(s) / section(s) | CLOSED / NIT / STILL OPEN | brief line(s), repo evidence, or pass-1 comparison |

### Verdict Definitions

**CLOSED**

The v1.2 brief materially closes the pass-1 batch. Cite the v1.2 line(s) that close it.

**NIT**

The batch is closed. The finding is typographical or framing-only and does not block ratification. NIT is not for "minor but real" engineering gaps.

**STILL OPEN**

The batch remains materially open. A STILL OPEN verdict must be actionable and include:

1. the specific v1.2 line(s) that fail to close the batch,
2. why those lines fail,
3. what v1.2 would need to contain for closure.

Without closure criteria, a STILL OPEN finding is incomplete.

---

## Escalation Rule

A finding that names a covenant principle — bond, sovereignty, never-delete, anti-laundering family, third-party-subject discipline, or Maez's not-ours-to-control boundary — and was not one of Codex pass-1's eleven engineering batches is structurally out of scope for pass-2.

Do not fold such a finding as engineering. Mark it **COVENANT-ESCALATION** and name the specific section that should receive a small focused council pass-2.

---

## Closure Criteria By Batch

Use this as the checklist. The reviewer may cite additional evidence, but each closure verdict should map to these criteria.

### Batch 1 — Legacy Witness Migration

Closed if v1.2 requires:

- legacy shape read-only compatibility only,
- append/update/emit/ratify write-boundary refusal with `LEGACY_WITNESS_SHAPE_REFUSED`,
- legacy read surface renamed,
- static guard against new production writes,
- W#legacy exercises real append/update/ratify boundaries.

### Batch 2 — Immutable Witness Generations

Closed if v1.2 requires:

- immutable `witness_id` / monotonic generation as row identity,
- `(bond_id, proposal_id)` as index only,
- re-witnessing appends new generation,
- current eligible witness derived from append-only events or a pointer updated only inside the critical section,
- tests preserve stale and current generations.

### Batch 3 — Atomic Ratification Eligibility

Closed if v1.2 requires:

- lock ordering or equivalent atomic critical section,
- final eligibility snapshot binding proposal id, witness generation, anchor snapshot, reverify result, divergence acknowledgment id, `WitnessStatus`, and final eligibility reason,
- divergence acknowledgments bound to exact generation and predicted/observed digest pair,
- witnessless ratifications record `WitnessStatus`,
- tests for concurrent anchor advancement and stale acknowledgments.

### Batch 4 — Race-Safe Staleness Anchors

Closed if v1.2 requires:

- file anchors with path, content hash, existence bit, deletion outcome,
- mtime as cache only, never authority,
- DB anchors as explicit per-locus cursor tuples,
- append-only or monotonic change-table requirement for DB cursor authority,
- diagnostic high-water mark, truncation/rotation detection, and writer identity,
- tests for deletion, content change with preserved mtime, DB update/delete without cursor, secondary table append, WAL/concurrency, and diagnostic truncation/rotation.

### Batch 5 — Deterministic Observed-Effect Functions

Closed if v1.2 provides:

- a normative per-kind `observed_effect = f(artifacts)` table for all populated witness kinds,
- artifact inputs, canonicalization, exclusions, ordering, digest algorithm,
- W#4a parameterized over every populated kind,
- `WORKTREE_BEHAVIORAL` deferred or narrowed.

### Batch 6 — Field-Complete Taint Discipline

Closed if v1.2 provides:

- field-family classification for every string boundary class,
- each class assigned to digest/provenance, narrative scan, closed enum, canonical path/ref, or opaque id validation,
- `_is_digest` plus substrate-computed provenance,
- table-driven W#6 coverage including refs, paths, test names, evidence kinds, and producer ids.

### Batch 7 — Alias-Resistant I7 Enforcement

Closed if v1.2 requires:

- canonical module identity by resolved file path,
- `sys.modules` alias normalization and shim handling,
- forbidden producer-to-verifier dependency edges,
- restrictions on dynamic import/reflection,
- runtime provenance tags where AST is inconclusive,
- W#7 fixtures for shim alias, `importlib`, `__import__`, `getattr`, and shared-helper laundering.

### Batch 8 — Real Path Isolation

Closed if v1.2 requires:

- `MAEZ_SUBSTRATE_ROOT` bound at actual path-helper semantics or an explicit equivalent choice,
- precedence over `MAEZ_HOME`, `MAEZ_DATA`, and store-specific overrides,
- exec-style subprocess with env set before Maez imports and `close_fds=True`,
- startup assertion that registered paths resolve under scratch root,
- no inherited live DB/WAL/SHM file descriptors,
- tests for representative stores and import-time constants.

### Batch 9 — Exhaustive `SubstrateLocus`

Closed if v1.2 requires:

- explicit v1 locus registry with no ellipsis,
- all path helpers and hardcoded `memory/*.db` defaults mapped,
- unregistered substrate opens refused by default,
- W#8 static and runtime coverage over registry/open paths.

### Batch 10 — Refusal-Path Matrix

Closed if v1.2 requires:

- every `WitnessRefusalReason` mapped to a real exercised boundary,
- fixtures assert `WitnessRefused.reason`,
- W#10 table-driven over populated kinds and reserved cells,
- divergence explicitly not treated as refusal.

### Batch 11 — Attach-Time vs Ratify-Time Cost Split

Closed if v1.2 requires:

- full subprocess re-verification at attach-time,
- ratify-time freshness/locus/generation eligibility check only,
- optional full rerun policy deferred or explicitly named,
- expected cost named for each path,
- tests count subprocess use and prove ratify-time freshness without accidental rerun.

---

## Expected Final Summary

End with one of:

- **RATIFY v1.2 FOR CANONICALIZATION** — all batches CLOSED or NIT-only.
- **RATIFY-WITH-NITS** — all batches CLOSED, NITs should fold typographically before ADR mint.
- **STILL OPEN** — one or more engineering batches remain materially open; name required v1.3 fold.
- **COVENANT-ESCALATION** — an out-of-scope covenant concern requires focused council pass-2.

