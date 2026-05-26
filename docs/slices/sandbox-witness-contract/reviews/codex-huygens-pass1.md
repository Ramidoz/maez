# Codex Engineering Pass-1 — Huygens Seat

**Artifact:** `docs/slices/sandbox-witness-contract/spec-brief.md` v1.1 at `711d405`
**Verdict:** BLOCK

## Findings

- [Blocking] Append-only witness table is keyed too narrowly for re-witnessing
  Section: v1.1 "Legacy SandboxWitness migration", W#persist, Lifecycle staleness/re-witness path.
  Evidence: `spec-brief.md:196` says `sandbox_witnesses` is keyed `(bond_id, proposal_id)` and append-only; `spec-brief.md:226` says stale proposals must be re-witnessed.
  Risk: the schema cannot both allow multiple witness attempts for the same proposal and enforce one `(bond_id, proposal_id)` key without update/replace.
  Concrete failure mode: first witness goes stale; second witness insert hits uniqueness conflict, or implementer uses `INSERT OR REPLACE`, deleting/overwriting the lived witness artifact.
  Required fold: define the table as an append-only event/artifact table keyed by immutable `witness_id` or monotonic sequence, with `(bond_id, proposal_id)` as an index, plus a deterministic "current attached witness" derivation or separate append-only attachment events.
  Test implication: add RED for `attach_witness_v1`, stale it, attach `witness_v2`, then assert both rows remain readable and ratification uses the latest eligible witness.

- [Blocking] Legacy 4-boolean write refusal does not close the existing write path
  Section: v1.1 "Legacy SandboxWitness migration", W#legacy.
  Evidence: spec says new writes use the new substrate and legacy shape is refused (`spec-brief.md:197`, `spec-brief.md:199`); current code still has `SandboxWitness` on `MaintenanceProposal` and serializes it into `sandbox_witness_json` on append/update (`maintenance_proposals.py:75`, `:156`, `:211`, `:365`).
  Risk: implementer can add a new attachment API while leaving direct `MaintenanceProposals.append/update` as a laundering bypass.
  Concrete failure mode: a caller constructs `MaintenanceProposal(sandbox_witness=SandboxWitness(True, True, True, digest))`; store append persists caller-asserted verdicts without touching the new refusal boundary.
  Required fold: explicitly require `SandboxWitness` to become legacy-read-only, forbid non-`None` legacy witness on new proposal append/update, and name the only allowed legacy deserialization boundary.
  Test implication: W#legacy must exercise `MaintenanceProposals.append` and `update`, not only the new attachment helper, and assert `LEGACY_WITNESS_SHAPE_REFUSED`.

- [Major] Read rename is underspecified: physical column, API field, and compatibility alias are not separated
  Section: v1.1 "Legacy SandboxWitness migration", W#9.
  Evidence: spec says existing `sandbox_witness_json` is "retained as `legacy_sandbox_witness_json`" (`spec-brief.md:197`); current schema physically creates `sandbox_witness_json` and row loader reads that exact name (`maintenance_proposals.py:128`, `:416`).
  Risk: implementers may physically rename the column and break old readers, or leave the physical column name and keep exposing it as current `sandbox_witness`.
  Concrete failure mode: first boot over an existing DB renames the column; `_row_to_proposal(row["sandbox_witness_json"])` crashes, or compatibility code continues to present legacy booleans as current `sandbox_witness`.
  Required fold: state whether the SQLite column is physically renamed or only API-renamed; require a read alias such as `SELECT sandbox_witness_json AS legacy_sandbox_witness_json`; define the returned dataclass/API field name.
  Test implication: add migration/readback RED from a pre-v1.1 DB with `sandbox_witness_json`, asserting old rows deserialize only through `legacy_sandbox_witness_json` and never populate current witness state.

- [Major] First-boot schema and migration race shape are not specified
  Section: v1.1 "Legacy SandboxWitness migration", I2 append-only artifact, W#persist.
  Evidence: spec names a new `memory/sandbox_witnesses.db` but gives no DDL, schema version/meta row, transaction boundary, lock/busy-timeout posture, or first-boot ordering (`spec-brief.md:196`); current path registry has `maintenance_proposals_db()` but no `sandbox_witnesses_db()` (`paths.py:153`).
  Risk: concurrent daemon/operator/test processes can initialize or migrate half a schema, especially with one DB for proposals and another for witnesses.
  Concrete failure mode: process A creates `sandbox_witnesses` without indexes/triggers; process B attaches a witness before migration metadata exists; later code treats the DB as current but append-only guarantees were never installed.
  Required fold: add concrete DDL, `schema_version`/migration marker, idempotent migration order, SQLite `busy_timeout`/transaction mode, and failure recovery rule before any writer is opened.
  Test implication: add first-boot RED that opens two stores concurrently against the same temp root and asserts one complete schema, no partial tables, and append-only constraints installed.

- [Major] `WitnessStatus` has no migration carrier
  Section: `WitnessStatus`, Lifecycle ratification eligibility, W#11.
  Evidence: spec requires every ratification to record `witness_status` (`spec-brief.md:163`, `:232`); current `maintenance_proposals` schema/update path has no such column or side table (`maintenance_proposals.py:128`, `:211`).
  Risk: "witnessless proposals ratify unchanged" conflicts with "silent absence is refused" unless the schema seat is named.
  Concrete failure mode: ratification succeeds and writes owner preference/status, but no durable `UNWITNESSED_BY_POLICY` or `UNWITNESSED_BY_OMISSION` record exists; later audit cannot distinguish omission from legacy absence.
  Required fold: define whether `witness_status` is a new proposal column, ratification event column, or separate append-only table; include migration default for pre-v1.1 ratified rows.
  Test implication: W#11 must inspect durable storage after ratification, not just returned object state.

