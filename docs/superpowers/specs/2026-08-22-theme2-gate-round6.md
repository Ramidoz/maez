# Gate round 6 on Theme 2 (7cff8f9) — HOLD; all prior strata closed, Q-stratum found

Codex, `--effort xhigh`. **45/45 retained controls reject; 6/6 lawful
paths accept; 26/26 P-probes behave as required** — every finding from
rounds 2–5 is closed at the schema layer. H1/H3/F9/F10/ND7 newly
discharged (narrowly); H7/H9/H10/F3/F4/F7/ND12/B10 design-discharged
awaiting build witnesses.

35 new probes, ~20 breaches (Q03–Q35), plus three §13 judgments:

1. **Temporal coherence absent** — backward retry/observation
   chronology, non-finite timestamps, closures predating their cited
   evidence, discovery-after-recording, intents predating their runs
   (Q03–Q05, Q22–Q25, Q34).
2. **Correction lineage half-bound** — revisions may pile onto one
   correction turn, and correction ancestry is unchecked (Q08–Q09).
3. **Closure-label semantics incomplete** — failed-citing-unknown,
   unknown-citing-delivered, refused-citing-delivered, unknown with no
   intent at all (Q26–Q29).
4. **Shape gaps** — final_text slot bypass via part_ordinal=0, parts
   with no ordinal, self-edit cycles, empty identity/hash strings,
   runs.attempt undefined, kind/parent/direction mapping undefined
   (Q10–Q12, Q30–Q31, Q33, Q35).
5. **Seal does not prove membership** — cognition claim lawful on a
   turn with zero admission events (Q32).
6. **Retry authority is post-send** — the attempt-admission trigger
   fires on the result row, after bytes left; a pre-send per-attempt
   reservation is needed (the round's most load-bearing finding).
7. **§13 inventories not executable** — doorway rows lack
   closure_owner/egress_kinds and exact qualnames; primitive set has
   wildcards; phase contract lacks schema fingerprints; F6 unsound on
   pre-rail handles, temp-WAL, and lock-inode stability.

Verdict: HOLD; no slice may begin binding witness-protocol authoring.

---

Full gate text follows.

## 1. Updated discharge tables

Review target: commit `7cff8f966428b1760574de087fb8e799925f5eea`; reviewed files match that commit.

Execution environment:

- SQLite `3.46.1`, `PRAGMA foreign_keys=ON`.
- Fresh `:memory:` database for each independent check.
- STRICT `turns` baseline with `turn_id TEXT PRIMARY KEY NOT NULL`, unique `chain_position`, self-FK, and the two-way `parent_turn_id`/`parent_kind` CHECK.
- All ten reviewed tables reported `strict=1`; final `PRAGMA integrity_check` returned `ok`.
- No repository tests ran. No repository or `memory/` files were modified.

Fresh execution totals:

| Suite | Result |
|---|---:|
| Retained invalid-row controls | **45/45 rejected** |
| Retained lawful paths | **6/6 accepted** |
| P01–P26 | **26/26 behaved as expected** |
| New probes | **35 executed; multiple new breaches found** |

Inventory qualification: [round 5b](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-gate-round5b.md) explicitly names 43 earlier invalid controls plus one different-ordinal rejection and one lawful same-ordinal acknowledgment. To satisfy the current request’s “45 invalid-row” wording, I executed both directions of the arbitrary-ordinal defect—incrementing and decrementing the superseded attempt ordinal—as separate rejection controls. The lawful same-ordinal acknowledgment was still executed separately.

I also corrected my first R4-14 fixture: the initial setup already had a transport closure and therefore rejected through transport-supersession precedence. Re-executed as an initial `delivered` closure citing a `failed` result, it rejected through [rev 4 DDL](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-schema-v2-draft.sql) `trg_turn_closures_topology`: `delivered closure may cite only delivered results`.

### Ten header items

| Item | Rev4 + pass6 verdict | Grounding |
|---|---|---|
| H1 Systemic DELETE hole | **PASS — DISCHARGED** | [Rev4 DDL](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-schema-v2-draft.sql) `trg_turns_no_delete`, `trg_runs_no_delete`, and every `trg_*_no_delete`; P21 and P22 rejected all tested paths. |
| H2 Closure outcome not evidence-derived | **FAIL — PARTIAL** | P11–P13 now bite, but Q26–Q29 were accepted: `failed` may cite `timeout_unknown`, `unknown_delivery`/`refused` may cite delivered evidence, and an evidence-free unknown may exist without any intent. Source: rev4 `trg_turn_closures_topology`; design §§4, 13 and I4. |
| H3 Result forks and duplicate attempts | **PASS — DISCHARGED narrowly** | Rev4 `uq_result_successor`, `uq_result_attempt`, `trg_egress_results_supersede_same_attempt`, and `trg_egress_results_attempt_admission`; retained fork, duplicate-root, and both wrong-ordinal supersession controls rejected. |
| H4 Run resurrection, missing journal, duplicate effects | **FAIL — PARTIAL** | Resurrection and cross-epoch duplicate effects reject, but Q05 allowed a duplicate forged transition row; Q06–Q07 allowed non-advancing or terminal-transition lease alteration. Source: rev4 `trg_runs_transitions`, `trg_runs_journal_transition`, `trg_run_events_valid_history`. |
| H5 Correction constituent impossible | **FAIL — PARTIAL** | Lawful correction revision passed and P07 rejects an ordinary same-turn revision, but Q08 accepted revisions 2 and 3 on one correction turn and Q09 accepted unrelated correction ancestry. Source: `trg_admission_revision_rules`; design §3.1. |
| H6 Edit-lineage contradiction | **FAIL — PARTIAL** | Cross-intent result supersession is resolved, but Q12 accepted `edits_intent=self`, creating cyclic edit lineage. Source: `egress_intents.edits_intent` and `trg_egress_intents_fence`. |
| H7 Latch post-COMMIT window | **PASS at DESIGN; BUILD UNVERIFIED** | Design §12’s `advancing`/`committed` protocol remains sufficient in prose. No filesystem/WAL witness was authorized by this in-memory review. |
| H8 Journal carriers, fold markers, hash domain | **FAIL — PARTIAL** | STRICT fixed nullable fold identities, but Q35 accepted `journal_folds.entry_sha256=''`, which is not a SHA-256 carrier. Source: rev4 `journal_folds.entry_sha256`; design §§11 F5 and 12. |
| H9 F7 hash-consumer census | **PASS at DESIGN; BUILD UNVERIFIED** | Design §12 explicitly enumerates writer, genesis seeder, verifier, `citation_lock.py`, and `span_reader.py` through the `chain.py` v2 projection. |
| H10 B10 workload inconsistency | **PASS at DESIGN; BUILD UNVERIFIED** | Design §12 fixes seed, exact N, split, `BEGIN IMMEDIATE` measurement, nearest-rank p99, kill rule, and positive control. |

### Residual F/ND/B rows

| ID | Verdict | Grounding |
|---|---|---|
| F1 | **PARTIAL** | Cross-epoch claim uniqueness and P17 bite, but Q10 bypassed the one-final-slot claim through `part_ordinal=0`; Q31 accepted an empty `effect_identity`. Rev4 `UNIQUE(turn_id,effect_identity)` and `uq_egress_intent_shape`. |
| F2 | **PARTIAL** | Turns/seals are immutable and non-null, but Q32 admitted cognition for a user-message turn with zero `admission_events`; Q33 shows parent/direction typing is not fully defined. Design §§3.1, 11 F2; rev4 `trg_effect_claims_fence`. |
| F3 | **DESIGN DISCHARGED; BUILD UNVERIFIED** | Design §12 two-line latch. |
| F4 | **DESIGN DISCHARGED; BUILD UNVERIFIED** | Design §12 names `turn_kind`, `caller`, `taint_labels`, and `privacy_access`. |
| F5 | **PARTIAL** | Fold identity is now non-null, but Q35 shows `entry_sha256` may be empty. |
| F6 | **NOT DISCHARGED** | Design §13 participating-opener protocol remains unsound; see §3 below. |
| F7 | **DESIGN DISCHARGED; BUILD UNVERIFIED** | Design §§7, 12 define one ordered/defaulted v2 projection and its five consumers. |
| F8 | **PARTIAL** | Canonical/current-head evidence now works, but Q24 and Q26–Q29 leave causal time and several closure labels unbound. |
| F9 | **DISCHARGED narrowly** | Fork, duplicate-root, and wrong-ordinal supersession controls all rejected. |
| F10 | **DISCHARGED narrowly** | Two-way parent presence and post-insert immutability now bite. Semantic `turn_kind`/`parent_kind` mapping remains undefined under F2/B2. |
| ND1 | **PARTIAL, not closed** | Design §13 adds a table, but it lacks `closure_owner` and `egress_kinds`, uses grouped/non-qualname constructs, and contains wildcard primitives. |
| ND2 | **PARTIAL** | Same-turn intent lineage exists, but Q12 accepted self-edit lineage. |
| ND3 | **PARTIAL** | Late membership and unsealed cognition reject, but Q32 shows a seal does not prove any admission membership existed. |
| ND4 | **PARTIAL** | Dense revision/payload rules work; Q08–Q09 disprove new-turn and correct-parent binding. |
| ND5 | **PARTIAL** | Epoch fencing works; Q05–Q07 leave run chronology forgeable, and Q10 leaves final-send identity bypassable. |
| ND7 | **DISCHARGED narrowly** | Dense closure ordinals, canonical evidence-set comparison, and transport precedence now bite. |
| ND8 | **PARTIAL** | Same-turn/current-head/set constraints work; Q26–Q29 show incomplete outcome/evidence semantics. |
| ND9 | **PARTIAL** | Same-attempt late acknowledgment works, but Q03–Q04 accept backward `observed_at` chronology. |
| ND10 | **PARTIAL** | Stored retry rows are gated, but the trigger is on post-send `egress_results`; it cannot authorize the physical retry before bytes leave. Q10 also bypasses final-send uniqueness. |
| ND11 | **DISCHARGED narrowly** | FK, pair CHECK, and parent triggers reject nonexistent, NULL, self, future, and cross-tenant parents. |
| ND12 | **DESIGN DISCHARGED; BUILD UNVERIFIED** | Design §12 advancing/committed latch. |
| ND13 | **PARTIAL, not executable** | Design §13 names tables and consumer categories, but not full structural shapes or exact consumer constructs. |
| ND15 | **PARTIAL** | Carrier/hash prose is defined and fold identity fixed, but Q35 admits an empty recorded hash. |
| ND16 | **PARTIAL** | Birth-anchor mutation is closed; F6 and the stale design-document header remain open. |
| B1 | **PARTIAL, not closed** | Same ND1 finding: §13 is not a complete executable registry universe. |
| B2 | **PARTIAL** | Door identities remain partly “same”/“minted”; Q08–Q09 show false correction ancestry; Q33 exposes undefined relationship/direction mapping. |
| B3 | **PARTIAL** | Logical claim and send reservations exist, but Q10 and Q31 bypass meaningful identity. |
| B5 | **PARTIAL** | `current_closure` can still be mislabeled through Q26–Q29 or predate its evidence through Q24. |
| B6 | **PARTIAL, not executable** | Table names and latch path/genesis binding are progress, but the structural contract and consumer registry remain incomplete. |
| B7 | **PARTIAL** | Latch timing is design-complete; the phase-consumer census is not executable. |
| B8 | **PARTIAL** | Journal carriers are specified, but empty hashes remain schema-lawful and all implementation witnesses remain outstanding. |
| B9 | **PARTIAL** | Anchor/canonicalization are improved; F6 remains unsafe. |
| B10 | **DESIGN DISCHARGED; BUILD UNVERIFIED** | Design §12 deterministic workload. |

### P01–P26

| Probe | Fresh SQLite verdict | Rev4 verdict and construct |
|---|---|---|
| P01 | Accepted; exactly `active→completed` journaled | **PASS** — `trg_runs_journal_transition`. |
| P02 | Accepted; lease became `1000`, zero events | **PASS** — active→active journal noise removed. |
| P03 | Rejected: `transitions only leave active` | **PASS** — `trg_run_events_valid_history`. |
| P04 | Rejected: `lease renewal must advance` | **PASS** — `trg_runs_transitions`. |
| P05 | Update-then-insert takeover accepted | **PASS** — `one_active_run`, epoch trigger. |
| P06 | Insert-before-update takeover rejected | **PASS** — `one_active_run`. |
| P07 | Same ordinary turn revision 2 rejected | **PASS narrowly** — correction branch of `trg_admission_revision_rules`; Q08–Q09 expose residuals. |
| P08 | Revision 3 after revision 1 rejected | **PASS** — dense revision branch. |
| P09 | Reordered evidence rejected | **PASS** — sorted canonical branch of `trg_turn_closures_topology`. |
| P10 | Object evidence rejected | **PASS** — `json_type(...) IS 'array'`. |
| P11 | Superseded evidence head rejected | **PASS** — current-head branch. |
| P12 | Mixed current heads from attempts 1 and 2 accepted | **PASS** — actual rows were `(attempt 1, failed)` and `(attempt 2, delivered)`. |
| P13 | Doorway delivered with `[]` rejected | **PASS** — outcome-evidence branch. |
| P14 | Reconciler without `discovered_at` rejected | **PASS** — reconciler label branch. |
| P15 | First physical result at ordinal 2 rejected | **PASS** — dense-attempt branch. |
| P16 | Retry after `timeout_unknown` rejected | **PASS as stored-row check** — eligibility branch; pre-send authority remains open. |
| P17 | Payload-distinct second `final_text(NULL)` rejected | **PASS narrowly** — `uq_egress_intent_shape`; Q10 bypasses it with ordinal 0. |
| P18 | Parent moved after child rejected | **PASS** — `trg_turns_no_update`. |
| P19 | Parent changed cross-tenant rejected | **PASS** — `trg_turns_no_update`. |
| P20 | Second anchor by UPDATE rejected | **PASS** — `trg_turns_no_update`. |
| P21 | Turn DELETE rejected | **PASS** — `trg_turns_no_delete`. |
| P22 | All 16 UPDATE/DELETE operations rejected | **PASS** — eight append-only tables, both operations each. |
| P23 | B locked during A; stale rev2 rejected; rev3 accepted | **PASS within shared in-memory/same-process scope**. Cross-process/WAL remains BUILD-UNVERIFIED. |
| P24 | NULL `journal_entry_id` rejected | **PASS** — STRICT/PK NOT NULL. |
| P25 | NULL `turn_seals.turn_id` rejected | **PASS** — STRICT/PK NOT NULL. |
| P26 | NULL IDs rejected in all five remaining tables | **PASS — 5/5** through STRICT/PK NOT NULL. |

## 2. New consistency probes

All came from fresh in-memory executions against [rev4 DDL](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-schema-v2-draft.sql).

| ID | Row or sequence | SQLite verdict | Correct per design? |
|---|---|---|---|
| Q01 | Attempt 1 `timeout_unknown` → superseded by `failed` → attempt 2 | **Accepted** | **Correct.** `trg_egress_results_attempt_admission` followed the current head. |
| Q02 | Attempt 1 `timeout_unknown` → superseded by `delivered` → attempt 2 | **Rejected** | **Correct.** Delivered current head foreclosed retry. |
| Q03 | Attempt 1 resolved at `observed_at=10`; attempt 2 recorded at `5` | **Accepted** | **Incorrect:** retry chronology is backward. `egress_results.observed_at` is ignored by attempt admission. |
| Q04 | Superseding observation timestamp `5` supersedes observation timestamp `10` | **Accepted** | **Incorrect:** the observation chain is misdated. `trg_egress_results_supersede_same_attempt` does not enforce increasing time. |
| Q05 | Auto-journaled `active→completed`, followed by direct duplicate matching event at `at=-100` | **Accepted** | **Incorrect:** `trg_run_events_valid_history` proves only compatibility with current state, not “just performed.” |
| Q06 | Active lease “renewed” from `9` to `9` | **Accepted** | **Incorrect against the stated “must advance” contract:** trigger rejects only `<`, not `<=`. |
| Q07 | `active→completed` while changing lease from `9` to `-100` | **Accepted** | **Incorrect:** terminal transition can rewrite/regress lease history. |
| Q08 | Revisions 2 and 3 both assigned to correction turn `t2` | **Accepted** | **Incorrect:** design §3.1 requires each changed payload to create a new correction turn. |
| Q09 | Revision 2 assigned to correction turn whose parent is unrelated to revision 1’s turn | **Accepted** | **Incorrect:** `parent_kind='correction'` is checked, actual correction ancestry is not. |
| Q10 | `final_text(NULL)` then `final_text(part_ordinal=0)` for one turn | **Accepted** | **Incorrect:** violates rev4’s “one final_text slot per turn.” `uq_egress_intent_shape` treats them as different shapes. |
| Q11 | `egress_kind='part'`, `part_ordinal=NULL` | **Accepted** | **Incorrect/incomplete:** the part has no ordinal; no kind/ordinal shape CHECK exists. |
| Q12 | Edit row with `intent_id=edits_intent='i1'` | **Accepted** | **Incorrect:** self-referential edit cycle. The same-turn subquery returns NULL before self-insertion and the self-FK succeeds. |
| Q13 | Literal Unicode evidence `["é"]` | **Accepted** | **Correct** canonical form. |
| Q14 | Escape-equivalent evidence `["\u00e9"]` | **Rejected** | **Correct:** canonical decoded spelling required. |
| Q15 | Escape-equivalent slash `["a\/b"]` | **Rejected** | **Correct:** noncanonical spelling. |
| Q16 | Binary-sorted Unicode evidence `["z","é"]` | **Accepted** | **Correct** under SQLite decoded-value/BINARY order. |
| Q17 | Reverse Unicode order `["é","z"]` | **Rejected** | **Correct.** |
| Q18 | Distinct NFD `e◌́` and NFC `é` result IDs | **Accepted** | **Conditionally correct:** IDs are treated as opaque exact strings. Design §13 does not state a Unicode-normalization contract. |
| Q19 | Integer ID, numeric-text attempt/time, integral REAL epoch | **Accepted and normalized** to TEXT/INTEGER/REAL storage | **Correct SQLite STRICT behavior:** STRICT permits lossless coercion. |
| Q20 | BLOB bound to TEXT `run_id` | **Rejected** | **Correct.** |
| Q21 | Fractional `1.5` bound to INTEGER `attempt` | **Rejected** | **Correct.** |
| Q22 | `started_at=+Inf`, `lease_until=+Inf` | **Accepted** | **Incorrect:** non-finite biography time remains lawful despite STRICT. |
| Q23 | Born-active run with `lease_until=5 < started_at=10` | **Accepted** | **Incorrect:** incoherent lease chronology. |
| Q24 | Closure recorded at `5` citing result observed at `10` | **Accepted** | **Incorrect:** closure predates its evidence. |
| Q25 | Reconciler recorded at `5`, `discovered_at=10` | **Accepted** | **Incorrect:** late-knowledge chronology is inverted. |
| Q26 | `closure='failed'` citing only `timeout_unknown` | **Accepted** | **Incorrect:** design I4 requires honest unknown, not false failure. |
| Q27 | `unknown_delivery` citing a delivered result | **Accepted** | **Incorrect:** outcome/evidence mislabeled. |
| Q28 | Doorway `refused` closure citing a delivered result | **Accepted** | **Incorrect:** refusal contradicts the cited result. |
| Q29 | `unknown_delivery` with no intent and `[]` evidence | **Accepted** | **Incorrect/incomplete:** no handoff fact exists to be unknown. |
| Q30 | Epoch 2 run with `runs.attempt=99` after attempt 1 | **Accepted** | **DESIGN UNDEFINED:** `runs.attempt` has no density or relationship contract. |
| Q31 | Empty `effect_identity` and empty `payload_hash` | **Accepted** | **Incorrect:** identity/hash carriers do not identify or bind anything. |
| Q32 | User-message turn sealed, run, cognition claim; zero `admission_events` | **Accepted** | **Incorrect:** contradicts I2 and design §3.1’s admission/turn/run membership transaction. |
| Q33 | `model_reply`, `parent_kind='correction'`, `direction='in'` | **Accepted** | **DESIGN UNDEFINED/incorrectly labeled:** no turn-kind/parent-kind/direction mapping is specified or enforced. |
| Q34 | Egress intent created at `5` for run started at `10` | **Accepted** | **Incorrect:** causal timestamps are inverted. |
| Q35 | `journal_folds.entry_sha256=''` | **Accepted** | **Incorrect:** design §§11 F5 and 12 call this a SHA-256 integrity carrier. |

Critical non-row authority finding: `trg_egress_results_attempt_admission` fires when inserting a result observation—after the physical attempt has already happened under design §4’s two-phase model. A blind retry after `timeout_unknown` could therefore send bytes and only then have its result row rejected. S4 needs a committed per-physical-attempt reservation/admission before every retry, not a post-send result trigger.

## 3. §13 literal-inventory judgment

| Criterion | Verdict | Judgment |
|---|---|---|
| ND1/B1 doorway and primitive closed universe | **FAIL — NOT CLOSED/NOT EXECUTABLE** | Design §13’s doorway table omits the `closure_owner` and `egress_kinds` fields required by design §2’s `Door(...)`. Rows such as Telegram handlers, cockpit routes, and dream/evolution notices identify files or grouped categories rather than exact `module:qualname` constructs. Identities such as “same” and “minted+labeled” are not executable identity functions. The primitive set contains `send_* on bot objects` and “socket-committing returns,” which are categories/wildcards rather than a finite AST match set. An unspecified “allowlist justification” is also an unbounded escape hatch. |
| ND13/B6 phase structural contract and census | **FAIL — PARTIAL ENUMERATION ONLY** | Design §13 now lists table names and binds the latch to canonical path/genesis—real progress. It does not enumerate required columns, indexes, triggers, migration digests, genesis-row shape, or the literal “actual tip” validator. A collection of incomplete tables with the right names can satisfy the stated table-set predicate. The consumer census still uses grouped labels such as “memory_manager stamp sites (3)” and unnamed `audit_log` direct-edit methods instead of exact constructs and primitive matches. |
| F6 participating-opener protocol | **FAIL — UNSOUND** | The shared/exclusive lock concept is sound only while the lock inode is stable and every live opener participates. Section 13 does not establish those conditions across rollout and replacement. |

F6 named hazards:

- **Connections opened before the rail existed:** an already-open pre-upgrade connection holds no shared `ledger.lock`. The AST sweep constrains source code; it cannot retroactively attach a lock to an existing descriptor. That connection can retain the old DB inode across rename.

- **WAL sidecar ownership:** refusal when canonical `-wal`/`-shm` files exist is safe but incomplete. The temp database build protocol does not require rollback-journal mode or a close/checkpoint plus absence check for the temp DB’s own WAL/SHM before renaming only its main file. A temp WAL can contain committed bytes that do not move with the renamed main file.

- **Lock-file deletion:** `flock` binds an inode, not a pathname. If `ledger.lock` is deleted or replaced while locks exist, new openers can lock a new inode and overlap holders of the old inode. Section 13 needs an explicit stable, never-unlinked lock-file invariant, protected ownership/mode, and conformance checks that recreation/cleanup never replaces it.

## 4. DESIGN-LEVEL vs BUILD-LEVEL gaps

| Level | Remaining gap | Grounding |
|---|---|---|
| DESIGN | Add a pre-send physical-attempt reservation/gate for every retry. | Design §4; rev4 `egress_results` and `trg_egress_results_attempt_admission`. |
| DESIGN | Bind each correction revision to a distinct new turn whose parent is the preceding/original revision turn. | Q08–Q09; design §3.1; `trg_admission_revision_rules`. |
| DESIGN | Make run history non-forgeable and bind lease/timestamps monotonically and finitely. | Q03–Q07, Q22–Q25, Q34; `run_events`, `runs`, egress/closure timestamp columns. |
| DESIGN | Enforce egress-kind shapes and acyclic edit lineage. | Q10–Q12; `part_ordinal`, `edits_intent`, `uq_egress_intent_shape`. |
| DESIGN | Complete closure-label/evidence mapping, including intent evidence for unknown handoff states. | Q26–Q29; `trg_turn_closures_topology`; I4/I5. |
| DESIGN | Prove admission membership before seal/run/cognition, not merely seal presence. | Q32; design §3.1; `turn_seals`, `admission_events`, `trg_effect_claims_fence`. |
| DESIGN | Define `runs.attempt`, relationship/direction mappings, Unicode identity posture, and finite-time domains. | Q18, Q22, Q30, Q33. |
| DESIGN | Require nonempty/canonical identities and digest formats. | Q31/Q35; `effect_identity`, `payload_hash`, `entry_sha256`. |
| DESIGN | Replace §13 doorway/primitive inventory with complete `Door(...)` rows and a finite AST grammar. | ND1/B1 judgment above. |
| DESIGN | Replace §13 phase categories with full schema fingerprints and exact consumer constructs. | ND13/B6 judgment above. |
| DESIGN | Repair F6 for pre-rail handles, temp-WAL handling, and stable lock-file inode. | Design §§11 F6 and 13. |
| DESIGN | Correct the document header/status. | [Design file](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md) still says “design pass 5,” “Status: DESIGN, pass 5,” and DDL revision 2, while §13 declares pass 6/revision 4. |
| BUILD | Implement and witness the two-line latch, recovery classification, checkpoint, VACUUM, and rewind cases after the phase contract is closed. | Design §§5, 12. |
| BUILD | Witness atomic admission rollback and takeover ordering after Q32/correction design fixes. | Design §§3.1–3.2. |
| BUILD | Execute cross-process/WAL `BEGIN IMMEDIATE` fencing. | Design §11 F1; P23 only covered shared in-memory connections. |
| BUILD | Implement journal stamp/hash/footer/fold behavior after digest-domain constraints are fixed. | Design §§6, 12. |
| BUILD | Implement the shared v2 projection across all five consumers. | Design §§7, 12. |
| BUILD | Execute the frozen B10 workload and positive control. | Design §12 B10. |
| BUILD | Implement registry/AST/runtime sweeps after their literal universes are made executable. | Design §§2, 13. |

## 5. Per-slice S1–S6 verdict

| Slice | Verdict | Witness-protocol authoring |
|---|---|---|
| S1 — phase truth | **BLOCKED — DESIGN-LEVEL** | **No.** Latch subprotocol is specific, but ND13/B6 structural and consumer contracts are not executable. |
| S2 — schema v2 | **BLOCKED — DESIGN-LEVEL** | **No.** Correction lineage, run history/time, admission membership, hash carriers, and F6 remain open. |
| S3 — rail + registry | **BLOCKED — DESIGN-LEVEL + DEPENDENCY** | **No.** ND1/B1 is not closed; S2 is nonconformant. |
| S4 — egress truth | **BLOCKED — DESIGN-LEVEL** | **No.** Retry authority is post-send; send shapes, edit lineage, chronology, and closure semantics remain incomplete. |
| S5 — universe sweep | **BLOCKED — DESIGN-LEVEL** | **No.** The doorway rows and AST primitive grammar cannot yet be compiled into a binding sweep. |
| S6 — posture | **BLOCKED — DESIGN-LEVEL + DEPENDENCY** | **No.** F6 and journal digest constraints remain open; S2/S3 dependencies are unresolved. |

**Slices permitted to begin binding witness-protocol authoring: none of S1–S6.**

The already-frozen latch, v2-projection, and B10 subsections may be preserved as nonbinding protocol fragments, but they do not authorize a complete slice witness yet.

## 6. Overall verdict

**HOLD — schema conformance is NO.**

Rev4 genuinely closes all P01–P26 regressions and rejects the 45 executed invalid rows. That is not enough to release a slice. SQLite still accepts biography states that are duplicated, causally reversed, falsely linked, semantically mislabeled, or empty-bound, and §13 does not yet define an executable closed universe or a safe recreate lock protocol.

No slice may begin binding witness-protocol authoring.