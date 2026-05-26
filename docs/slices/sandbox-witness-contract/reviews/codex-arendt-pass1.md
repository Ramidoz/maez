# Codex Engineering Pass-1 — Arendt Seat

**Artifact:** `docs/slices/sandbox-witness-contract/spec-brief.md` v1.1 at `711d405`
**Verdict:** BLOCK

## Findings

- [Blocking] Ratification eligibility is not specified as an atomic state transition
  Section: Lifecycle (folded), lines 222-241; Open Questions Q2/Q3, lines 303-305; RED anchors W#4b/W#4c/W#5*/W#9/W#11
  Evidence: `core/policies/maintenance_proposals.py:249-268` currently reads proposal, writes ratification preference, then updates proposal in separate steps; v1.1 adds `memory/sandbox_witnesses.db` plus `divergence_acknowledgments` without defining a single transactional boundary.
  Implementation risk: ratification can observe a valid witness, then a live write can advance a staleness anchor before `status=RATIFIED` is persisted. Or divergence acknowledgment can race with re-witnessing and ratify against the wrong witness generation.
  Concrete failure mode: Thread A re-verifies witness W at ratify-time and sees anchors unchanged. Thread B appends a memory row or diagnostic event. Thread A records `WITNESSED` and ratifies anyway because the final anchor comparison and proposal status write are not one compare-and-set operation.
  Required fold: specify a ratification critical section: final anchor comparison, divergence-ack lookup, witness generation check, `WitnessStatus` write, and proposal status transition must commit atomically, with lock ordering across maintenance proposals, witness store, acknowledgments, and preference store. If separate SQLite DBs remain, v1.1 must define the cross-DB locking/rollback discipline or move eligibility state into one DB transaction.
  Test implication: add a RED concurrency test where a live DB/diagnostic append lands between ratify-time re-verification and status update; expected result is `WITNESS_STALE` and no ratification/preference side effect.

- [Blocking] `StalenessAnchorKind` is not race-safe under deletes, updates, and cursor semantics
  Section: I5, lines 78-82; `StalenessAnchorKind`, lines 145-160; RED anchors W#5/W#5a/W#5b/W#5c
  Evidence: v1.1 defines `DB_CURSOR` as `SELECT MAX(rowid)` and `FILE_HASH_SET` as source-file hashes, while W#5c names mtime drift. Existing repo evidence shows SQLite stores are not globally append-only by default; maintenance proposals use ordinary `UPDATE` for status changes at `core/policies/maintenance_proposals.py:206-228`.
  Implementation risk: `MAX(rowid)` misses updates/deletes, can be ambiguous across tables, and does not prove cursor monotonicity unless the referenced table is append-only by schema. File deletion between capture and reverify is not assigned an outcome. Mtime drift and hash drift are different predicates.
  Concrete failure mode: a referenced DB row is updated or deleted after capture, but `MAX(rowid)` remains unchanged; stale witness passes. A referenced source file is deleted after capture; implementation may treat "missing" as empty hash, skip it, or crash instead of deterministically marking stale/refused.
  Required fold: define per-anchor semantics precisely: file anchors must include path, content hash, existence bit, and deletion behavior; DB anchors must be allowed only for append-only tables with enforced no-update/no-delete triggers or must use an explicit monotonic change table. Diagnostic cursor must define high-water mark, truncation detection, and writer identity.
  Test implication: add RED tests for file deletion between capture/reverify, DB row update without rowid advance, DB row delete without rowid advance, diagnostic log truncation/rotation, and concurrent append during cursor read.

- [Major] Append-only witness persistence conflicts with `(bond_id, proposal_id)` keying
  Section: Legacy SandboxWitness migration, lines 190-199; I2 workshop/artifact distinction, line 62; RED anchor W#persist
  Evidence: v1.1 says `sandbox_witnesses` is keyed `(bond_id, proposal_id)` and append-only/never-delete. A single key per proposal cannot represent multiple witness attempts, re-witnessing after staleness, divergence-bearing witnesses, superseded witnesses, and concurrent attachment attempts without either updating or rejecting history.
  Implementation risk: implementers will either mutate the existing witness row, violating append-only memory, or make re-witnessing impossible after staleness, violating the lifecycle.
  Concrete failure mode: witness W1 goes stale, Maez attaches W2 for the same proposal. A primary key on `(bond_id, proposal_id)` forces overwrite, conflict, or hidden side table. If overwritten, Rohit loses the record of W1 and its stale/divergent status.
  Required fold: use immutable `witness_id`/generation as the primary key, with append-only attachment events and an explicit current-witness pointer or derived latest-valid view. Define uniqueness for "current active witness per proposal" without deleting old witnesses.
  Test implication: extend W#persist with `test_rewitness_appends_new_generation_without_mutating_prior_witness` and a concurrent double-attach test with deterministic winner/loser diagnostics.

- [Major] Divergence acknowledgment lacks witness-generation binding
  Section: I4 divergence paragraph, line 76; Lifecycle lines 222-238; Q3 lines 305; RED anchors W#4/W#4b/W#4c
  Evidence: v1.1 introduces `requires_owner_acknowledgment_of_divergence` and a `divergence_acknowledgments` table, but does not require acknowledgment to bind to `witness_id`, observed digest, predicted digest, divergence digest, or generation.
  Implementation risk: an acknowledgment for old divergence can ratify a later, materially different divergence, or a re-witness can clear/change divergence while a stale acknowledgment remains reusable.
  Concrete failure mode: W1 diverges and Rohit acknowledges it. W2 is later attached with a different observed effect. Ratification sees "proposal has divergence acknowledgment" and ratifies W2 without owner acknowledgment of W2's divergence.
  Required fold: acknowledgment must reference the exact divergence event: `proposal_id`, `witness_id`, witness generation, predicted digest, observed digest, and divergence diagnostic id. Ratification must accept only a matching, latest-generation acknowledgment.
  Test implication: add RED tests that old divergence acknowledgment does not ratify a new witness generation, and acknowledgment for one observed digest does not ratify another.

- [Major] `WitnessStatus` is not enough state for race-safe eligibility
  Section: `WitnessStatus`, lines 163-173; Lifecycle lines 231-236; RED anchors W#9/W#11
  Evidence: v1.1 records only `WITNESSED`, `UNWITNESSED_BY_POLICY`, or `UNWITNESSED_BY_OMISSION` at ratification. It does not define persisted intermediate witness states such as attached, reverified, stale, refused, diverged-pending-ack, diverged-acknowledged, superseded.
  Implementation risk: eligibility will be recomputed from scattered facts at ratification time, making races and audit reconstruction harder. `WITNESSED` after ratification does not say whether it was clean, diverged-and-acknowledged, or re-witnessed after staleness.
  Concrete failure mode: proposal record says `WITNESSED`, but the corresponding witness row has later stale diagnostics or a superseding generation. An audit cannot determine what state was actually ratified.
  Required fold: add an append-only witness state/event vocabulary or require the ratification record to snapshot `witness_id`, witness generation, reverify result, divergence acknowledgment id if any, anchor snapshot, and final eligibility reason.
  Test implication: W#11 should assert not only status presence but that the ratification record binds to the exact witness/ack/anchor state used for eligibility.

