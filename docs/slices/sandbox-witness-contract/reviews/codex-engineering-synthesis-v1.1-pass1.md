# Sandbox-Witness Contract — Codex Engineering Pass-1 Synthesis

**Prepared:** 2026-05-26
**Artifact reviewed:** `docs/slices/sandbox-witness-contract/spec-brief.md` v1.1
**Dispatch brief:** `docs/slices/sandbox-witness-contract/reviews/codex-engineering-pass1-brief.md`
**Review records:** `docs/slices/sandbox-witness-contract/reviews/codex-*-pass1.md`

This document is derivative reconstruction. The six `codex-*-pass1.md` files are the witnessed review record.

---

## Verdict Summary

| Seat | Verdict |
| --- | --- |
| Peirce | BLOCK |
| Arendt | BLOCK |
| Huygens | BLOCK |
| Pauli | BLOCK |
| Ohm | RATIFY-WITH-AMENDMENTS |
| Lovelace / Bernoulli | BLOCK |

Engineering pass-1 result: **BLOCK v1.1 from canonicalization or implementation until folded.**

The skeleton survived: no reviewer rejected the need for the contract. The blockers are implementability gaps where v1.1 still lets an implementer satisfy the prose without closing the actual trapdoor.

---

## Convergent Fold Batches

### Batch 1 — Legacy witness migration must close existing write paths

Seats: Peirce, Huygens, Pauli

v1.1 says the four-boolean `SandboxWitness` is deprecated, but the existing `MaintenanceProposal.sandbox_witness` / `sandbox_witness_json` write paths still exist. Codex found that an implementation could add a new honest attachment API while leaving `append()`, `update()`, `emit_maintenance_proposal()`, or ratification paths able to persist caller-asserted booleans.

Required v1.2 fold:

- legacy `SandboxWitness` becomes read-only compatibility state;
- new proposal append/update/ratify reject non-`None` legacy witness with `LEGACY_WITNESS_SHAPE_REFUSED`;
- old persisted rows deserialize only through a legacy-named surface;
- static guard catches any new production write to `sandbox_witness_json`;
- W#legacy exercises real append/update/ratify boundaries, not just the new attachment helper.

### Batch 2 — Witness persistence needs immutable generations, not `(bond_id, proposal_id)` primary identity

Seats: Arendt, Huygens

v1.1 says `sandbox_witnesses` is append-only and keyed `(bond_id, proposal_id)`. That cannot support re-witnessing after staleness, divergent witnesses, supersession, or concurrent attachment without overwrite or conflict.

Required v1.2 fold:

- `witness_id` or monotonic generation is the immutable primary identity;
- `(bond_id, proposal_id)` is an index, not the row identity;
- attaching a new witness appends a new generation;
- current eligible witness is derived or represented by an append-only attachment event;
- tests prove stale witness + re-witness keeps both rows and ratifies only the latest eligible generation.

### Batch 3 — Ratification eligibility must be atomic and generation-bound

Seats: Arendt, Huygens

v1.1 adds witness store, divergence acknowledgments, and `WitnessStatus`, but does not define a critical section across final anchor comparison, divergence acknowledgment lookup, witness generation, witness status write, owner preference write, and proposal status transition.

Required v1.2 fold:

- define ratification critical section and lock ordering;
- final eligibility snapshot binds `proposal_id`, `witness_id`, generation, anchor snapshot, reverify result, divergence acknowledgment id if any, and final eligibility reason;
- divergence acknowledgments bind to exact witness generation and predicted/observed digest pair;
- witnessless ratifications durably record `WitnessStatus`;
- tests cover concurrent anchor advancement between reverify and status flip, stale acknowledgments, and old acknowledgment against new divergence.

### Batch 4 — Staleness anchors need concrete, race-safe semantics

Seats: Arendt, Ohm, Peirce

`DB_CURSOR = SELECT MAX(rowid)` is not safe enough. It misses updates/deletes, misses secondary tables, and is ambiguous under WAL/concurrent readers. `FILE_HASH_SET` is declared, but W#5c still names mtime drift.

Required v1.2 fold:

- file anchors include path, content hash, existence bit, and deletion outcome;
- mtime is cache invalidation only, never the authority;
- DB anchors are per-locus cursor tuples over explicit tables;
- DB cursor requires append-only guarantees or a monotonic change table;
- diagnostic cursor defines high-water mark, truncation/rotation detection, and writer identity;
- tests cover file deletion, content-change-with-preserved-mtime, DB update/delete without rowid advance, secondary-table append, WAL concurrent writer, and diagnostic truncation.

### Batch 5 — Deterministic `observed_effect = f(artifacts)` must be normative per witness kind

Seats: Lovelace / Bernoulli, Pauli

v1.1 requires deterministic observed-effect functions but does not declare them. Implementers would invent digest bases, causing incompatible or noisy witness verdicts.

Required v1.2 fold:

- per-kind table for all populated `SandboxWitnessKind` values;
- for each: artifact inputs, canonicalization, excluded nondeterministic fields, ordering, digest algorithm, and idempotence proof;
- W#4a parameterized over every populated kind;
- `WORKTREE_BEHAVIORAL` remains deferred.

Specific kind pressure:

- `WORKTREE_RED_TEST`: needs command, env allowlist, runner/version, selected test ids, source file hash set, assertion extractor version, normalized outcome schema, and deterministic-fixture requirement.
- `WORKTREE_SCHEMA_DIFF`: narrow to canonical SQLite schema projection or defer; define before/after `sqlite_master` / PRAGMA extraction, normalized ordering, indexes/triggers/views, and data-migration exclusion/inclusion.
- `SCRATCH_DB_TRANSFORM`: needs source snapshot digest, scratch DB digest, transform recipe ref/hash, table/row scope, before/after canonical diff, SQLite version/pragmas, and refusal for time/random/network-dependent transforms.
- `DRY_RUN_OBSERVATION`: not yet deterministic; either narrow to closed durable `ObservationSourceKind` with cursor semantics and deterministic projection, or defer.

### Batch 6 — Narrative/digest taint discipline must be field-complete

Seats: Pauli

v1.1 says narratives are scanned and digests are validated, but it does not classify every string field. Several fields are refs, IDs, paths, kinds, effects, or producer names that are neither obvious narrative nor obvious digest.

Required v1.2 fold:

- mandatory witness/proposal boundary table for every string field;
- each field classified as one of:
  - substrate-computed digest,
  - narrative scanned by `injection_patterns.scan`,
  - closed vocabulary enum,
  - canonical path/ref with resolver validation,
  - opaque ID with character/length schema and no authority semantics;
- `_is_digest` proves both shape and substrate computation/provenance;
- W#6 is table-driven over every narrative field and includes injection attempts in refs, paths, test names, evidence kinds, and producer IDs.

### Batch 7 — I7 static enforcement needs alias/dynamic-import resistance or runtime provenance

Seats: Pauli, Peirce

v1.1 names AST predicates for self-ratification, but repo reality includes shim modules, `sys.modules` aliases, dynamic imports, `getattr`, and shared helper indirection. Direct-import AST checks would be ceremonial.

Required v1.2 fold:

- canonical module identity by resolved file path plus `sys.modules` alias normalization;
- forbidden dependency edges between producer and verifier packages;
- restrictions on dynamic import/reflection inside verifier code;
- runtime provenance tags on recomputable values so semantic laundering is caught when AST is inconclusive;
- W#7 fixtures for shim alias, `importlib.import_module`, `__import__`, `getattr`, and shared-helper laundering, all asserting `SELF_RATIFICATION_DETECTED`.

### Batch 8 — Subprocess isolation must bind to real path resolution and handle coverage

Seats: Ohm, Pauli

`MAEZ_SUBSTRATE_ROOT` currently exists only in prose. Actual path helpers use `MAEZ_HOME`, `MAEZ_DATA`, `MAEZ_CACHE`, and many modules cache DB paths at import time or open hardcoded `memory/*.db` paths.

Required v1.2 fold:

- define `MAEZ_SUBSTRATE_ROOT` at the path-helper layer or choose existing env var semantics;
- define precedence versus `MAEZ_HOME`, `MAEZ_DATA`, store-specific overrides;
- require exec-style subprocess launch with env set before any Maez imports, `close_fds=True`, and startup assertion that registered paths resolve under scratch root;
- forbid or remap store-specific live DB overrides inside witness subprocess;
- tests verify representative stores resolve to scratch paths, no inherited FD points at live `memory/*.db`, `*-wal`, or `*-shm`, and import-time constants cannot freeze live paths.

### Batch 9 — `SubstrateLocus` must be exhaustive for v1, with unregistered opens refused

Seats: Ohm, Pauli

v1.1 uses ellipsis in `SubstrateLocus`. Engineering found many actual DB surfaces not named: audit log, pending cards, entity index, recall stats, fabrication log, consequence memory, action trust, self-dev/workshop DBs, and more.

Required v1.2 fold:

- replace ellipsis with explicit v1 registry;
- every path helper and known hardcoded `memory/*.db` default maps to a `SubstrateLocus`;
- unregistered substrate opens refuse by default;
- W#8 includes static coverage over path helpers and `rg`-discovered DB defaults plus runtime monkeypatching of `sqlite3.connect` / store constructors.

### Batch 10 — Refusal tests need a refusal-path matrix

Seats: Peirce, Pauli

`WitnessRefusalReason` can still become vocabulary-only. Each reason needs a real boundary that emits it.

Required v1.2 fold:

- table mapping each refusal reason to exactly one exercised boundary: construction, attachment, re-verification, ratification-time recheck, or migration write-boundary;
- divergence remains a non-refusal signal;
- every reason has a fixture crossing the boundary and asserting `WitnessRefused.reason == <reason>`;
- W#10 is table-driven per populated kind and reserved cell, not enum-inspection.

### Batch 11 — Attach-time vs ratify-time verification cost must be split

Seats: Ohm, Arendt

v1.1 conflates full subprocess re-verification, anchor comparison, and ratification freshness checks.

Required v1.2 fold:

- attach-time: full subprocess re-verification;
- ratify-time: freshness/locus/generation eligibility check;
- optional full rerun policy named explicitly, if any;
- expected cost named for each path;
- tests count subprocess use where intended and prove ratify-time freshness without rerunning an expensive suite unless explicitly required.

---

## Material Outcome

v1.1 is not implementable honestly yet. The engineering panel did exactly what it was asked to do: it found where the brief's wording still allowed ceremonial compliance.

The strongest convergence:

1. legacy 4-boolean witness path remains a real bypass unless append/update/ratify refuse it;
2. append-only witness storage needs immutable generations;
3. ratification eligibility must bind to a specific witness generation and final anchor snapshot;
4. deterministic observed-effect functions are missing;
5. path/locus isolation is not yet tied to the real repo's path helpers and hardcoded DB surfaces.

These are foldable. None require abandoning the contract. They require v1.2 to be more concrete before canonicalization or implementation.

---

## Recommended Next Step

Fold to `spec-brief.md` v1.2 before any canonicalization. Do not dispatch implementation planning against v1.1.

The v1.2 fold should be structured around the eleven batches above, not around individual reviewer files, while keeping the raw `codex-*-pass1.md` records as the witnessed evidence.

