# Ohm — Council Pass-1 Review — Sandbox-Witness Contract v1

**Reviewer:** Ohm (resistance / mechanism / what actually runs)
**Artifact:** `docs/slices/sandbox-witness-contract/spec-brief.md` v1
**Dispatched:** 2026-05-26
**Verdict:** **RATIFY-WITH-AMENDMENTS**

---

The contract is structurally honest and the lifecycle is implementable, but four mechanism questions need amendment before Codex panel sees this: re-verification cost model, the `injection_patterns.scan` ENCODING false-positive on witness digests, the AST-predicate for I7/self-ratification (concretely under-specified), and the witness storage seam against the existing `sandbox_witness_json` column.

---

## Blocking

### B1. `injection_patterns.scan` ENCODING bucket will fire on witness artifact digests — refusal-path collision

**Severity:** Blocking. Load-bearing.

The brief routes external-LLM-derived witness inputs through `core/safety/injection_patterns.py` (I6, W#6). But the ENCODING bucket includes `re.compile(r"[A-Za-z0-9+/]{40,}={0,2}")` — any contiguous 40+ char base64-looking blob. Witness payloads will routinely carry: a `witness_digest` (the dataclass already requires `hmac-sha256:` + 64 hex chars = 76 chars matching the alnum+/ pattern), test-trace assertion-reason digests, scratch DB content hashes, predicted/observed effect digests. Every digest-bearing field in a witness will trip ENCODING and be refused as `INBOUND_TAINT_UNCLEARED`. This makes I6 unimplementable as written without an exemption seam.

**8-step trace:**

1. **Dependency-map:** witness construction at I6 → `injection_patterns.scan()` → matches list → refusal verdict. Every closed-vocabulary `SandboxWitnessKind` carries digests; W#6 RED test will fail in both directions (false-positive on legitimate witness, OR the test gets watered down).
2. **Write-path:** witness attachment writes to `sandbox_witness_json` after the taint filter passes. If the filter never passes, the write never happens.
3. **Read-path:** `_sandbox_from_json` in `maintenance_proposals.py:379` already deserializes the current `SandboxWitness`. Nothing reads the filter result yet — read-path needs a `WitnessRefusalReason` discriminator.
4. **Test-path:** W#6 as drafted asserts "direct bypass refused." It does not assert "legitimate digest content passes." Both assertions must coexist.
5. **Fold-summary:** the brief's claim "the existing filter chain is invoked at the substrate boundary" is false if invoked unmodified — `scan()` is a *catalog* designed for free-form text, not a witness-input adjudicator. The wording should become "scan is invoked on the *narrative-content* sub-slice of witness input; digest fields are validated by `_is_digest`, not by the injection catalog."
6. **Cross-reference:** Q4 already hints at this ("injection_patterns catches known attack patterns but does not validate semantic shape"). The amendment should resolve Q4 explicitly: route only the free-text fields, not the digest fields.
7. **RED-test trace:** add `test_witness_with_legitimate_digests_does_not_trip_encoding_bucket` paired with W#6. The pair proves the boundary is *targeted*, not blunt.
8. **Verify-before-declaring:** run `scan("hmac-sha256:" + "a" * 64)` against current implementation. It will match `[A-Za-z0-9+/]{40,}` and return an ENCODING hit. (I confirmed the pattern at `injection_patterns.py:226`.)

---

## Major

### M1. I5 staleness mechanism is unspecified — cost ranges from 1ms to 30s

**Severity:** Major. Load-bearing.

I5 says the witness goes stale when "underlying substrate state has moved." At witness-attachment time the candidate signals are: git commit hash at `isolation_ref`, file mtimes/hashes of referenced source files, row-count or `MAX(rowid)` at referenced live DBs, episode-id high-water-mark, diagnostic-stream cursor. These have radically different IO costs. Hash-based staleness over a worktree diff is ~30ms; re-running a behavioral probe is seconds-to-minutes.

**8-step trace:**

1. **Dependency-map:** Q2 (attach + ratify checkpoints) compounds with I5; per ratification attempt, every witness on the bond's PROPOSED queue is re-checked. At 10s of proposals/week with cumulative PROPOSED queue size N, each ratification is O(N) re-verifications unless staleness is cached.
2. **Write-path:** none — staleness is a read-side derivation. But the witness object must persist a `staleness_anchor` (commit hash + mtimes + cursors) at construction so re-check is comparison, not recomputation.
3. **Read-path:** `is_stale(witness, now)` reads (a) git rev-parse on `isolation_ref`, (b) `os.stat` on referenced source paths, (c) `SELECT MAX(rowid)` on referenced DBs. All cheap *if* the anchor was captured at construction.
4. **Test-path:** W#5 as drafted only asserts commit-hash advance. Source-file mtime drift and live-DB row-count drift are equally stale-inducing and untested.
5. **Fold-summary:** "structurally stale" needs a closed enum: `StalenessAnchorKind = {COMMIT_HASH, FILE_HASH_SET, DB_CURSOR, DIAGNOSTIC_CURSOR}`. Per-`SandboxWitnessKind` the required anchor set is fixed.
6. **Cross-reference:** ADR 0019's `valid_from/valid_to` discipline assumes monotonic time anchors — the brief invokes it but doesn't carry the anchor-kind enumeration over.
7. **RED-test trace:** add `test_witness_stale_after_referenced_source_file_changes` and `test_witness_stale_after_live_db_row_count_advances` paired with W#5.
8. **Verify-before-declaring:** run `git rev-parse HEAD` (~5ms) + `os.stat` per file (~0.1ms) + one indexed `MAX(rowid)` per DB (~1ms). Per-witness staleness ≈ 10-50ms, acceptable. *Without* this anchor-set discipline, naive re-verification re-runs tests, which is seconds-to-minutes — orders of magnitude worse.

### M2. I7 static-AST predicate (self-ratification detection) is under-specified

**Severity:** Major. Load-bearing.

W#7 says "static-AST predicate refuses any module that exports both `construct_witness` and `reverify_witness` from the same namespace." The existing F17-shaped pattern at `tests/test_curiosity_producer_ceremony.py:468` works for `record_event`/`record_salience_event` because they're literal name-matched calls in a single file. Witness construction and re-verification cross modules.

**8-step trace:**

1. **Dependency-map:** the predicate must walk the witness package (`core/safety/sandbox_witness/`?) and refuse any module that names both functions at module scope. Cross-module aliasing (`from .construct import construct_witness as build`) defeats name-match.
2. **Write-path:** none.
3. **Read-path:** test imports `ast.parse(module.read_text())`, scans `ast.FunctionDef` and `ast.ImportFrom`, asserts disjoint namespaces.
4. **Test-path:** W#7 as written cannot handle (a) function aliases via `as`, (b) conditional imports inside `if TYPE_CHECKING`, (c) re-exports via `__init__.py`. The Slice 2 F17 pattern handled none of these because it didn't need to.
5. **Fold-summary:** the predicate becomes "no Python module that defines OR re-exports a `construct_*` symbol may also define OR re-export a `reverify_*` symbol." Re-export discipline must be added.
6. **Cross-reference:** `core/evolution/drive_driven_curiosity.py` is single-file, single-namespace — not a precedent for cross-module enforcement. Brief should not claim parity it doesn't have.
7. **RED-test trace:** add `test_witness_construction_module_does_not_re_export_reverification_helpers` and a positive test exercising the aliased-import attack.
8. **Verify-before-declaring:** confirmed `tests/test_curiosity_producer_ceremony.py:469` parses ONE file. Multi-module enforcement is new code.

### M3. Witness storage seam — `sandbox_witness_json` column already exists

**Severity:** Major. Q7 resolution required.

`maintenance_proposals.py:136` already declares a `sandbox_witness_json` column holding the legacy 3-bool witness (`red_tests_passed`, `focused_tests_passed`, `scratch_canary_passed`, `witness_digest`). W#9 ("witnessless proposals still ratify") must coexist with a *new* schema for the contract-honest witness. Options:

- **Option A (in-place upgrade):** add columns `witness_kind`, `witness_artifact_refs_json`, `staleness_anchor_json`, `observed_effect_digest`. Migration risk on existing DB rows; backward-compat shim required.
- **Option B (parallel table):** new `sandbox_witnesses` table keyed by `(bond_id, proposal_id)`, foreign-key shape. The existing `sandbox_witness_json` becomes a deprecated legacy field; W#9 verifies it still deserializes.

**8-step trace:** (1) read-path at `_sandbox_from_json` would need a discriminator field; (2) `update()` at line 215 already supports overwriting `sandbox_witness_json`, which is the wrong granularity for I8 non-disturbance — partial witness updates need atomicity at row level. **Recommend Option B.** Storage locality is not load-bearing; separation-of-concerns is, because I7 (witness-cannot-self-ratify) is structurally clearer when storage is also separated.

---

## Minor

### Mi1. I8 non-disturbance mechanism — process isolation vs filesystem isolation

The brief implies filesystem-path isolation suffices. It doesn't address: shared SQLite connections (the substrate's daemon may hold WAL locks), Python module-level singletons, in-memory caches. Mechanism: re-verification should run in a subprocess with `MAEZ_SUBSTRATE_ROOT` env override pointing at a scratch root, not in-process with path arguments. Add to invariant text: "re-verification runs in a child process with a substrate-root override; no live-process module state is shared." This is a one-sentence amendment.

### Mi2. W#1–W#9 implementability: 7 unit, 2 integration

W#1, W#2, W#3, W#7, W#9 are pure unit tests against the witness dataclass and refusal codepath — cheap (~1ms each). W#4 (divergence-attaches), W#5 (staleness), W#6 (taint filter on free-text), W#8 (no-live-mutation) require integration scaffolding: a tmp worktree, a tmp DB, and an injected diagnostic sink. Total RED suite runtime estimate: ~3-8 seconds, acceptable. Not a blocker; brief should say so explicitly so Codex doesn't over-scope.

### Mi3. Q3 (divergence) — operator-acknowledgment field needs schema seat

`requires_owner_acknowledgment_of_divergence` is mentioned in Q3 but absent from the lifecycle diagram. If it lives on `MaintenanceProposal`, that's a column add. If it lives on the witness, it complicates I7 (the witness must not author its own ratification path). Recommend: a separate `divergence_acknowledgments` table keyed `(bond_id, proposal_id, witness_id)`, owner-explicit signed entry — same shape as `_ratification_preference` at line 306.

---

## NIT

### N1. "alias-aware AST predicates mirroring Slice 2's F17 pattern"

The cited precedent doesn't actually handle aliasing — it handles literal-kwarg discipline within one module. Brief should drop "alias-aware" or specify the alias-handling mechanism. *Not applicable, pure framing — but framing on a load-bearing invariant.*

### N2. `SandboxWitnessKind` count

Five kinds at v1 is the right call; growth path via spec amendment is correct. *Not applicable, pure framing.*

---

## Closing Synthesis

The contract will hold under real load **if** three concrete amendments land: (a) `injection_patterns.scan` is gated to free-text witness fields only, with `_is_digest` adjudicating digest fields — otherwise W#6 is unimplementable; (b) the staleness anchor is a closed-vocabulary set captured at construction, making re-verification a 10-50ms comparison rather than a multi-second recomputation; (c) witness storage goes to a separate `sandbox_witnesses` table so the legacy `sandbox_witness_json` column can remain for W#9 backward-compat without schema entanglement. The brief underestimates the cross-module AST-predicate complexity (Slice 2's F17 is single-file) and overestimates the safety of routing raw witness payloads through the existing prompt-injection catalog. Under realistic load (10s of proposals/week, cumulative PROPOSED queue), per-ratification staleness re-check stays sub-second if anchored correctly and explodes if not — this is the single biggest mechanism risk. The lifecycle is otherwise a clean additive extension of `maintenance_proposals.py`; no separate substrate is required.
