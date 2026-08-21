# Gate round 5 (rerun) on Theme 2 (d7c6259) — HOLD; 45/45 controls pass; 17 new probes fail; gap list now finite

Codex, `--effort xhigh`, conformance-framed rerun after the classifier
kill. Executed DDL rev 3: **22 round-2/3 + 21 round-4 + 2 round-5
rejection tests ALL PASS; 6 lawful paths pass.** Newly DISCHARGED:
H1 (DELETE holes), H3 (forks/dup attempts), H6 (edit lineage), H7
(two-line latch), H9 (hash census), H10 (B10 protocol), F3, F4, F7,
F9, ND2, ND3, ND9, ND12, B10 — plus ND11 upheld.

Probes P01–P26: 17 FAIL, clustering into mechanical classes:
1. **UPDATE-path bypass** — parent/anchor/seal triggers cover INSERT
   only; turns mutable/deletable (P18–P21); active→active journaling
   noise; lease regression; direct false run_events inserts (P02–P04).
2. **Nullable TEXT PRIMARY KEYs** — SQLite non-STRICT quirk: seven
   identifier PKs accept NULL, incl. anonymous journal folds
   (P24–P26).
3. **Closure evidence refinements** — array-type not enforced for
   non-transport rows, set-compare done on raw JSON text (reorder =
   "new evidence"), evidence joins all results not current heads,
   per-attempt double counting, doorway 'delivered' with empty
   evidence, reconciler rows without discovered_at (P09–P14).
4. **Egress admission semantics** — no dense ordinal admission, retry
   permitted while an attempt head is timeout_unknown (I4 conflict),
   payload-distinct duplicate final_text intents (P15–P17).
5. **Correction lineage unbound** — revision>1 not required to land
   on a parent_kind='correction' turn (P07).

DESIGN-LEVEL vs BUILD-LEVEL split delivered; the DESIGN list is 11
bullets (§4 of the verdict), including the literal doorway/primitive
inventories, phase-table contract, F6 exclusivity, and a
revision-label inconsistency (header says rev 2, gate/commit say
rev 3). BUILD-LEVEL items (latch, atomic admission tx, cross-process
fencing, journal fold, v2 projection, B10 run) are adequately
specified and wait on implementation witnesses.

No slice may begin witness-protocol authoring yet. Verdict: HOLD.

---

Full gate text follows.

## 1. DDL-revision-3 execution log summary

Reviewed bytes: commit `d7c62597771a3e486f91d8805df9496b5f703259`, SHA-256 `472d0962d48cd53c8ca08df217518623330cdc15d1429de1e4c9da194a3ccdf5`. The four named files match that commit.

Environment: SQLite 3.46.1, fresh `:memory:` database per check, minimal `turns` baseline from the [DDL comments](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-schema-v2-draft.sql:16), `PRAGMA foreign_keys=ON`. Final DDL load produced 10 tables, 29 triggers, 4 indexes, 2 views; `PRAGMA integrity_check` returned `ok`.

| Group | Result | Failures |
|---|---:|---|
| Rounds 2–3 retained invalid-row rejection tests N01–N22 | **22/22 PASS** | None |
| Round-4 retained invalid-row rejection tests R4-01–R4-21 | **21/21 PASS** | None |
| Round-5 fix check | **2/2 PASS** | None |
| Retained lawful paths | **6/6 PASS** | None |

The 22 retained names were: second active run, regressed epoch, self/NULL/future/kindless parent, invalid/second birth anchor, late/updated constituent after seal, cross-tenant admission, duplicate intent shape, self/cross-intent result supersession, evidence-less/cross-turn closure evidence, second/gapped closure, reconciler-over-transport, closure mutation, and claim/intent from a superseded run.

The 21 round-4 names were: JSON-number result identity, forked result chain, supersede-then-claim, terminal resurrection, duplicate NULL-part shape, malformed evidence JSON, six deletion paths, duplicate attempt ordinal, false delivered closure, parent label without parent, same-evidence transport supersession, doorway-over-transport, cross-epoch duplicate effect, cross-epoch duplicate egress shape, duplicate evidence membership, and cognition on an unsealed turn.

Round 5 specifically confirmed:

- **PASS—rejected:** superseding `e1(retry_ordinal=1)` using `retry_ordinal=2`, by `trg_egress_results_supersede_same_attempt`.
- **PASS—accepted:** same-ordinal late acknowledgment, leaving `e2(1, delivered)` as the `current_results` head.

The lawful paths also covered correction revision on a new correction turn, active-epoch cognition claim, active→completed auto-journaling, same-turn `edits_intent`, and update-then-insert takeover.

One initial late-ack fixture invocation mis-bound helper arguments and produced an unrelated FK failure. I corrected the fixture and re-executed both round-5 checks; the results above are the corrected executions.

No repository test suite ran. No repository file was modified.

## 2. Newly designed consistency findings

Result convention: **PASS** means schema conformance held; **FAIL** means SQLite accepted an incomplete, duplicated, misordered, or mislabeled record.

| ID | Result | Finding and grounding |
|---|---|---|
| P01 | **PASS** | Active→completed produced exactly `active → completed` in `run_events` through `trg_runs_journal_transition`. |
| P02 | **FAIL** | `UPDATE runs SET status='active'` on an active run was accepted and journaled `active → active`; `trg_runs_transitions` does not implement its stated active→terminal-only matrix. |
| P03 | **FAIL** | A direct `INSERT` of `completed → active` into `run_events` was accepted; only `trg_run_events_no_update/no_delete` exist, with no insert-validity trigger. |
| P04 | **FAIL** | An active run’s `lease_until` regressed from 999 to 1; `trg_runs_transitions` checks active status but not that a lease “renewal” advances. |
| P05 | **PASS** | Within one `BEGIN IMMEDIATE`, superseding epoch 1 before inserting epoch 2 succeeded under `one_active_run`, `UNIQUE(turn_id,epoch)`, and `trg_runs_epoch_monotonic`. |
| P06 | **PASS** | Inserting epoch 2 before superseding epoch 1 was rejected by `one_active_run`; takeover statement order therefore matters as specified by design §3.2. |
| P07 | **FAIL** | Revisions 1 and 2 for the same identity and different payloads were accepted on the same `turn_id`; `trg_admission_revision_rules` does not enforce design §3.1’s new correction turn or `parent_kind='correction'`. |
| P08 | **PASS** | Revision 3 immediately after revision 1 was rejected by `trg_admission_revision_rules`. |
| P09 | **FAIL** | Transport evidence `["e1","e2"]` was followed by `["e2","e1"]`; `trg_turn_closures_topology` compares raw JSON text, not set membership, so the same set counted as new evidence. |
| P10 | **FAIL** | A doorway closure accepted `{"only":"e1"}`; `trg_turn_closures_topology` requires an array only indirectly for transport rows and lacks `json_type(...)='array'`. |
| P11 | **FAIL** | A failed closure cited `e1(failed)` after `e2(delivered)` superseded it; `trg_turn_closures_topology` joins `egress_results`, not `current_results`. |
| P12 | **FAIL** | A partial closure cited both timeout and delivered observations from one retry chain; the trigger counted two result IDs rather than one physical attempt head. |
| P13 | **FAIL** | A doorway row recorded `closure='delivered'` with `evidence_json='[]'`; evidence is mandatory only when `recorded_by='transport'`. |
| P14 | **FAIL** | A reconciler closure with `discovered_at=NULL` was accepted; `turn_closures` does not enforce design I8/§6’s late-knowledge label. |
| P15 | **FAIL** | The first `egress_results` row used `retry_ordinal=2`; the table has `retry_ordinal>=1` and uniqueness but no dense-admission trigger. |
| P16 | **FAIL** | A new ordinal-2 attempt followed an unresolved ordinal-1 `timeout_unknown`; `uq_result_attempt` prevents duplicates but does not enforce design I4’s no-blind-resend rule. |
| P17 | **FAIL** | Two `final_text` intents with different payload hashes were accepted for one turn; `uq_egress_intent_shape` includes `payload_hash`, so it does not reserve the logical final-text slot. |
| P18 | **FAIL** | Updating a parent’s `chain_position` placed it after its child; `trg_turns_parent_semantics` covers INSERT only. |
| P19 | **FAIL** | Updating a child’s parent from an owner turn to a public turn succeeded; the FK proves existence, while tenant equality is checked only by the INSERT trigger. |
| P20 | **FAIL** | Updating a second turn to `is_birth_anchor=1` produced two anchors; `trg_turns_single_birth_anchor` covers INSERT only. |
| P21 | **FAIL** | An unreferenced turn was deleted; the DDL’s “turns itself never updates” statement has no `trg_turns_no_update` or `trg_turns_no_delete`. |
| P22 | **PASS** | UPDATE and DELETE were rejected for all eight declared append-only tables—16/16—by their `*_no_update`/`*_no_delete` triggers. |
| P23 | **PASS** | Two shared-memory connections serialized dense admission revisions: connection B was locked while A held `BEGIN IMMEDIATE`, then its stale revision 2 was rejected and revision 3 accepted by `trg_admission_revision_rules`. |
| P24 | **FAIL** | Two `journal_folds` rows with `journal_entry_id=NULL` were accepted; ordinary SQLite `TEXT PRIMARY KEY` left `notnull=0`, contradicting design §12’s non-null-bound claim. |
| P25 | **FAIL** | Two anonymous `turn_seals` rows with `turn_id=NULL` were accepted for the same reason; `turn_id TEXT PRIMARY KEY REFERENCES turns` is not an effective non-null binding. |
| P26 | **FAIL** | Direct NULL identifiers were also accepted by `runs.run_id`, `effect_claims.claim_id`, `egress_intents.intent_id`, `egress_results.result_id`, and `turn_closures.closure_id`; all seven single-column text primary keys report `notnull=0`. |

P23 directly observes two connections in one process with `journal_mode=memory`. True cross-process/WAL behavior is **REASONED-NOT-EXECUTED** because the required in-memory database cannot supply that environment.

## 3. Round-4 discharge table

`DISCHARGED` means the prior criterion is complete at design/schema level; `PARTIAL` means named paths were fixed but the same criterion remains incomplete; `NOT` means the documents still lack an adequate resolution.

### Ten header items

| Item | Verdict | Reason |
|---|---|---|
| H1 Systemic DELETE hole | **DISCHARGED** | R4-07–R4-12 all rejected under `trg_*_no_delete` and `trg_runs_no_delete`; the separate mutable/deletable `turns` finding is P18–P21. |
| H2 Closure outcome not evidence-derived | **PARTIAL** | `trg_turn_closures_topology` now rejects delivered→failed evidence, but P11–P13 show non-head, double-counted, and empty evidence can still establish an outcome. |
| H3 Result forks and duplicate attempts | **DISCHARGED** | `uq_result_successor`, `uq_result_attempt`, and `trg_egress_results_supersede_same_attempt` rejected the fork, duplicate root, and different-ordinal supersession tests. |
| H4 Run resurrection, missing journal, duplicate effects | **PARTIAL** | `trg_runs_transitions`, `trg_runs_journal_transition`, and `UNIQUE(turn_id,effect_identity)` close the named rows, but P02–P04 permit false transition history and lease regression. |
| H5 Correction constituent impossible | **PARTIAL** | `admission_events.revision` plus `trg_admission_revision_rules` permits the lawful correction, but P07 shows no new correction-turn lineage is enforced. |
| H6 Edit-lineage contradiction | **DISCHARGED** | `egress_intents.edits_intent`, its two-way CHECK, and `trg_egress_intents_fence` accept same-turn edit lineage while result supersession remains same-intent. |
| H7 Latch post-COMMIT window | **DISCHARGED** | Design §12 specifies durable pre-COMMIT `advancing` and post-COMMIT `committed` lines with unmatched/behind states→unknown; **REASONED-NOT-EXECUTED**, requiring the S1 build witness. |
| H8 Journal carriers, fold markers, hash domain | **PARTIAL** | Design §12 freezes carriers and hashing and `trg_journal_folds_no_delete` bites, but P24 disproves the claimed non-null `journal_entry_id`. |
| H9 F7 hash-consumer census | **DISCHARGED** | Design §12 explicitly adds `citation_lock.py` and `span_reader.py` to the one `chain.py` projection; **REASONED-NOT-EXECUTED** pending build witness. |
| H10 B10 workload inconsistency | **DISCHARGED** | Design §12 freezes seed, exact N, writer split, acquisition measurement, nearest-rank p99, kill rule, and scheduled positive control; **REASONED-NOT-EXECUTED** pending S6. |

### Residual F/ND/B entries

| ID | Verdict | Reason |
|---|---|---|
| F1 | **PARTIAL** | `effect_claims.UNIQUE(turn_id,effect_identity)` bites across epochs, but P17 shows `uq_egress_intent_shape` uses payload bytes rather than an immutable logical final-send identity. |
| F2 | **PARTIAL** | The parent two-way CHECK and sealed cognition claim bite, but P18–P21 and P25 contradict the claimed immutable turns and fully bound seals. |
| F3 | **DISCHARGED** | Design §12’s two-line latch protocol closes the silent committed-tail window; **REASONED-NOT-EXECUTED** pending S1. |
| F4 | **DISCHARGED** | Design §12 names `turn_kind`, `caller`, `taint_labels`, and `privacy_access` as failure-time carriers; **REASONED-NOT-EXECUTED** pending S6. |
| F5 | **PARTIAL** | Design §12 defines canonical entry bytes and footer hashing, but `journal_folds.journal_entry_id TEXT PRIMARY KEY` remains nullable under executed SQLite semantics. |
| F6 | **NOT** | Design §11 F6 still relies on service/handle/sidecar snapshot checks plus advisory `flock` without requiring every opener to participate, leaving the open-after-check/old-inode interval unresolved; **REASONED-NOT-EXECUTED**. |
| F7 | **DISCHARGED** | Design §§7 and 12 freeze one ordered/defaulted v2 projection and enumerate all five consumers; **REASONED-NOT-EXECUTED** pending build. |
| F8 | **PARTIAL** | Result deletion and basic set/outcome checks now bite, but P09–P13 and nullable result/closure IDs leave evidence noncanonical and non-head-bound. |
| F9 | **DISCHARGED** | `uq_result_successor`, `uq_result_attempt`, and `trg_egress_results_supersede_same_attempt` close the exact fork and duplicate-attempt criterion. |
| F10 | **PARTIAL** | The two-way parent CHECK closes parent-kind-without-parent on INSERT, but P18–P20 show parent and anchor semantics remain mutable afterward. |
| ND1 | **PARTIAL** | Design §12 names primitive categories and producers but still says “§2’s table row-for-row”; §2 contains only the `Door(...)` signature, not literal doorway rows. |
| ND2 | **DISCHARGED** | Design §12 and `egress_intents.edits_intent` replace contradictory cross-intent result supersession with same-turn intent lineage. |
| ND3 | **DISCHARGED** | `trg_admission_revision_rules`, `trg_admission_events_no_update`, and the cognition branch of `trg_effect_claims_fence` enforce no post-seal membership change before cognition. |
| ND4 | **PARTIAL** | Dense revision and payload replay rules work, but P07 shows revision rows are not bound to a new `parent_kind='correction'` turn as design §3.1 requires. |
| ND5 | **PARTIAL** | Epoch fencing and terminal freezing work, but P02–P04 and P17 leave false run history and payload-dependent cross-epoch egress identity. |
| ND7 | **PARTIAL** | Dense closure ordinals and transport precedence bite, but P09 lets the same evidence set supersede itself through array reordering. |
| ND8 | **PARTIAL** | `trg_turn_closures_topology` checks same-turn IDs and duplicates, yet P10–P13 show the JSON carrier is neither array-enforced nor current-head/attempt-bound. |
| ND9 | **DISCHARGED** | Same-ordinal late acknowledgment passed while forks and different-ordinal supersession rejected under the result indexes and same-attempt trigger. |
| ND10 | **PARTIAL** | Exact duplicate egress shapes reject per turn, but P16–P17 permit a retry after unknown and a second final-text intent when payload changes. |
| ND11 | **DISCHARGED** | For its narrow no-orphan-reply criterion, the parent FK, pair CHECK, `trg_turns_parent_semantics`, and `trg_turns_reply_needs_parent` reject all retained insert forms. |
| ND12 | **DISCHARGED** | Design §12’s advancing/committed latch makes a committed rewind detectable; **REASONED-NOT-EXECUTED** pending S1. |
| ND13 | **NOT** | Design §5 still says “complete expected table set” and “pass 2’s list plus” without enumerating the phase schema and consumer census. |
| ND15 | **PARTIAL** | Design §§6/12 specify stamps, entry hashing, footer hashing, and fold transaction semantics, but P24 permits duplicated anonymous fold markers. |
| ND16 | **PARTIAL** | `trg_turns_single_birth_anchor` and design §§7/12 fix insertion/canonicalization, but P20 bypasses anchor uniqueness by UPDATE and F6 remains unresolved. |
| B1 | **PARTIAL** | Design §§2/12 provide a registry type and producer categories but no literal complete doorway table or exact transport-send primitive list. |
| B2 | **PARTIAL** | Parent typing is present, but the missing literal door identities and P07’s absent correction-turn binding leave identity semantics incomplete. |
| B3 | **PARTIAL** | `effect_claims.effect_identity` is unique per turn, but P17 shows egress has no payload-independent logical-effect identity. |
| B5 | **PARTIAL** | Result chains no longer fork, but P09–P13 show `current_closure` may still rest on reordered, stale, double-counted, or absent evidence. |
| B6 | **NOT** | Design §5 still lacks the literal gestation table contract and canonical ledger identity/path required by the round-4 finding. |
| B7 | **PARTIAL** | Design §12 closes the latch timing window, but design §5’s phase-consumer census remains referential rather than enumerated. |
| B8 | **PARTIAL** | Journal carriers and hash domains are adequately specified in §§6/12, but nullable `journal_folds.journal_entry_id` contradicts reconstruction-grade identity. |
| B9 | **PARTIAL** | Design §§7/12 freeze canonicalization and actual-tip verification, but F6 recreate exclusivity and P20’s mutable birth anchor remain open. |
| B10 | **DISCHARGED** | Design §12 freezes the complete deterministic contention protocol; **REASONED-NOT-EXECUTED** pending S6. |

## 4. DESIGN-LEVEL vs BUILD-LEVEL gaps

### DESIGN-LEVEL

- Make every identifier explicitly non-null: `turn_seals.turn_id`, `runs.run_id`, `effect_claims.claim_id`, `egress_intents.intent_id`, `egress_results.result_id`, `turn_closures.closure_id`, and `journal_folds.journal_entry_id`; P24–P26 show `TEXT PRIMARY KEY` alone is insufficient.
- Enforce `turns` immutability and deletion refusal; P18–P21 bypass `trg_turns_parent_semantics` and `trg_turns_single_birth_anchor`.
- Complete `trg_runs_transitions`: reject active→active status writes, define monotonic lease renewal, and prevent direct non-transition `run_events` inserts.
- Bind `admission_events.revision>1` to a new correction turn and explicit correction lineage, per design §3.1.
- Define dense/eligible physical retry admission; `uq_result_attempt` alone does not prevent ordinal gaps or retry after `timeout_unknown`.
- Give egress a payload-independent logical-send identity; `uq_egress_intent_shape` currently permits two final-text intents when bytes differ.
- Require evidence JSON arrays, compare transport evidence as sets, require current result heads, prevent multiple observations of one physical attempt from being counted separately, and define evidence obligations for every closure label.
- Bind reconciler rows to non-null `discovered_at`, per I8/§6.
- Replace §2/§5’s referential doorway, primitive, phase-table, phase-consumer, and canonical-ledger descriptions with literal inventories.
- Repair F6 recreate exclusivity so every potential opener participates in one authoritative exclusion protocol.
- Correct document labels: the [DDL header](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-schema-v2-draft.sql:1) and design pass-5 status/§12 call the artifact revision 2, while [gate round 5](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-gate-round5.md:15) and commit `d7c6259` call it revision 3.

### BUILD-LEVEL

These are adequately specified but still need implementation and witnesses:

- Design §12’s two-line latch, crash recovery, WAL/checkpoint/VACUUM, and rewind classification.
- Design §§3.1–3.2’s atomic admission/seal/run transaction and update-before-insert takeover, including rollback after any failed statement.
- Design §11 F1’s cross-process/WAL `BEGIN IMMEDIATE` fencing; P23 covered only two same-process in-memory connections.
- Design §§6/12’s journal stamp capture, canonical entry hash, sealed footer, ordinary-door fold, and atomic ledger-row/fold-marker transaction—after the identifier fix.
- Design §§7/12’s shared canonical v2 projection across writer, genesis, verifier, citation lock, and span reader.
- Design §12’s deterministic B10 workload and positive-control execution.

## 5. Per-slice S1–S6 verdict

| Slice | Verdict | Deciding reason |
|---|---|---|
| S1 — phase truth | **BLOCKED — DESIGN-LEVEL** | The §12 latch protocol is witness-ready, but ND13/B6 remain unspecified in design §5. |
| S2 — schema v2 | **BLOCKED — DESIGN-LEVEL** | P02–P21 and P24–P26 show mutable history, nullable identities, incomplete correction lineage, egress/closure gaps, and unresolved F6. |
| S3 — rail + registry | **BLOCKED — DESIGN-LEVEL/DEPENDENCY** | S2 is not conformant, §2/§12 lack a literal registry, and egress lacks payload-independent effect identity. |
| S4 — egress truth | **BLOCKED — DESIGN-LEVEL** | P09–P17 leave closure evidence, attempt admission, and logical final-send identity incomplete. |
| S5 — universe sweep | **BLOCKED — DESIGN-LEVEL** | ND1/B1 still lack the literal doorway rows and exact primitive inventory that the sweep would consume. |
| S6 — posture | **BLOCKED — DESIGN-LEVEL/DEPENDENCY** | B10 is adequately frozen, but nullable fold identity remains and S6 depends on nonconformant S2/S3 contracts. |

## 6. Slices that may begin witness-protocol authoring

**None of S1–S6 may begin binding witness-protocol authoring.**

Individual BUILD-LEVEL witness sections—especially the S1 latch and S6 contention schedules—are specific enough to preserve, but their complete slice protocols would currently encode unresolved DESIGN-LEVEL contracts.

## 7. Overall verdict

**HOLD — schema conformance is NO.**

DDL revision 3 successfully rejects all 43 retained invalid rows and closes the round-5 retry-ordinal finding. That is real progress, but it is not enough to release a slice: SQLite still accepts anonymous primary-key rows, mutable/deletable turns, false run events, correction revisions without correction lineage, retries after unknown delivery, payload-distinct duplicate final sends, and closures based on non-array, reordered, stale, double-counted, or empty evidence.