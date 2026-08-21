# Gate round 4 on Theme 2 (4ec2cc4) — HOLD; old attacks all blocked, next stratum found

Codex, `--effort xhigh`, executed the draft DDL (artifact sha256
f34c44c4eef3...). **All 22 round-2/3 negative controls REJECT; both
lawful paths pass; ND11 DISCHARGED** (no-orphan-reply). New
counterexamples, all executed:

1. **Systemic DELETE hole** — five "append-only" tables have only
   BEFORE UPDATE triggers; proof rows and runs are deletable.
2. **Closure outcome not evidence-derived** — a `delivered` closure
   can cite a `failed` result.
3. **Result chains fork** — `supersedes_result` not unique; duplicate
   `(intent, retry_ordinal)` legal.
4. **Completed runs resurrect** — no transition matrix; unjournaled
   transitions; cross-epoch duplicate effect claims (no logical-effect
   identity above run scope).
5. **Correction constituent impossible** — the admission PK rejects
   the promised different-payload correction; identity needs a
   revision dimension.
6. **Edit lineage contradicts the same-intent trigger.**
7. **Latch post-COMMIT window** — restore inside commit→append
   silently accepted; needs a pre-commit advancing line.
8. **Journal stamp carriers incomplete** (turn_kind, caller); fold
   markers nullable/deletable; hash domain undefined.
9. **F7 census incomplete** — citation_lock.py and span_reader.py also
   recompute chain hashes.
10. **B10 workload internally inconsistent** (per-admission vs
    per-transaction; Poisson N expected-not-exact; unfrozen seed).

F1 cross-process serialization reasoning judged SOUND for the narrow
snapshot argument (SQLITE_BUSY_SNAPSHOT forces retry); unsound overall
until claims carry logical-effect identity across epochs.

Verdict: HOLD; no slice may begin witness-protocol authoring from
pass 4. The 22 controls are retained for the future S2 protocol.

---

Full gate text follows.

# 1. DDL execution findings

Pinned artifact: `4ec2cc41ee3a5fe85f65f52e9bd86050ea807b9b`, SHA-256 `f34c44c4eef34f340627770faee761444ad8ce64b24fec5ca41c83701d617a6f`.

Execution used SQLite 3.46.1, `sqlite3.connect(":memory:")`, `PRAGMA foreign_keys=ON`, and the minimal `turns` table described by the DDL comments. No repository test ran. Final `PRAGMA integrity_check` was `ok`; the worktree remained clean.

## Round-2/round-3 controls

All 22 negative controls named in [design §11](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:333) rejected:

| ID | Attack | Result and enforcing mechanism |
|---|---|---|
| N01 | Second active run | **PASS** — `one_active_run` rejected it. |
| N02 | Regressed epoch | **PASS** — `trg_runs_epoch_monotonic`. |
| N03 | Self-parent reply | **PASS** — rejected by `trg_turns_parent_semantics`; diagnostic was misleading because the `BEFORE INSERT` trigger saw no existing parent before the self-check. |
| N04 | Reply with NULL parent | **PASS** — `trg_turns_reply_needs_parent`. |
| N05 | Future parent | **PASS** — `trg_turns_parent_semantics` strictly-prior branch. |
| N06 | Parent without `parent_kind` | **PASS** — `trg_turns_parent_semantics`. |
| N07 | `is_birth_anchor=2` | **PASS** — boolean `CHECK` from the required `turns` baseline. |
| N08 | Second birth anchor | **PASS** — `trg_turns_single_birth_anchor`. |
| N09 | Late constituent after seal | **PASS** — `trg_admission_no_late_constituent`. |
| N10 | Update constituent onto sealed turn | **PASS** — `trg_admission_events_no_update`. |
| N11 | Owner event pointing to public turn | **PASS** — composite tenant/turn FK. |
| N12 | Duplicate non-NULL intent shape | **PASS** — `uq_egress_intent_shape`. |
| N13 | Self-superseding result | **PASS** — `egress_results` self `CHECK`. |
| N14 | Cross-intent result supersession | **PASS** — `trg_egress_results_supersede_same_intent`. |
| N15 | Evidence-less transport closure | **PASS** — `trg_turn_closures_topology`. |
| N16 | Cross-turn closure evidence | **PASS** — same-turn join inside `trg_turn_closures_topology`. |
| N17 | Second initial closure | **PASS** — dense ordinal branch. |
| N18 | Gapped closure ordinal | **PASS** — dense ordinal branch. |
| N19 | Reconciler over transport | **PASS** — precedence branch. |
| N20 | Closure mutation | **PASS** — `trg_turn_closures_append_only_u`. |
| N21 | Claim by superseded run | **PASS** — `trg_effect_claims_fence`. |
| N22 | Intent from superseded run | **PASS** — `trg_egress_intents_fence`. |

The two declared lawful controls also passed: same-intent late acknowledgment supersession and a claim by the current active maximum-epoch run.

These mechanisms are in the [draft DDL](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-schema-v2-draft.sql:116).

## New requested attacks

- Same-turn result from a subsequently superseded run: **accepted lawfully, not a breach**. An intent created while its run was active may receive a late delivery acknowledgment after takeover; supersession does not make actual delivery false. The closure invariant in `trg_turn_closures_topology` is turn identity, not current-run identity.

- JSON number `1` versus TEXT result ID `'1'`: **PASS — rejected**. SQLite returned `typeof(je.value)='integer'`, and `r.result_id = je.value` was false. `CAST(je.value AS TEXT)` would match, but the trigger does not cast.

- Forked result chain: **BREACH**. `trg_egress_results_supersede_same_intent` checks intent equality but does not make `supersedes_result` unique:

```sql
INSERT INTO egress_results
VALUES ('e3','i1',3,'failed',23,'e1');
```

This succeeded after `e2(delivered)` already superseded `e1(timeout_unknown)`, producing two conflicting heads.

- Dense-ordinal race under `BEGIN IMMEDIATE`: **PASS within the allowed witness boundary**. Connection B received `database table is locked` while A held the write transaction; after A committed ordinal 1, B’s retry was rejected by the dense-ordinal trigger. Shared in-memory databases cannot provide a true cross-process or WAL witness (`journal_mode` remained `memory`), so that part is **UNVERIFIED**.

- Same-transaction run mutation:

  - Supersede then claim: **PASS — rejected** because the trigger saw the transaction’s own `superseded` state.
  - Claim then supersede: accepted. This is coherent only if the committed claim is an irrevocable reservation inherited by takeover.
  - Terminal-run resurrection then claim: **BREACH**:

```sql
BEGIN IMMEDIATE;
UPDATE runs SET status='active' WHERE run_id='r1';
INSERT INTO effect_claims VALUES ('cl1','r1','action',30);
COMMIT;
```

Starting from `r1.status='completed'`, this committed with zero `run_events`.

- Two NULL `part_ordinal` shapes: **PASS — rejected** by `uq_egress_intent_shape`, whose `COALESCE(part_ordinal,-1)` safely maps NULL outside the permitted non-NULL domain.

- Malformed `evidence_json`: **PASS — rejected** with `OperationalError: malformed JSON`. It is a statement-aborting parse error, not a silent pass.

## Additional attacks executed

The following also broke through:

```sql
-- Claimed append-only rows are deletable:
DELETE FROM effect_claims WHERE claim_id='cl1';
DELETE FROM egress_intents WHERE intent_id='i1';
DELETE FROM egress_results WHERE result_id='e1';
DELETE FROM run_events WHERE run_event_id=1;
DELETE FROM journal_folds WHERE journal_entry_id='j1';
DELETE FROM runs WHERE run_id='r1';

-- Duplicate physical attempt ordinal:
INSERT INTO egress_results
VALUES ('e2','i1',1,'delivered',22,'e1');

-- False closure/result binding:
INSERT INTO turn_closures
VALUES ('c1','t1',1,'delivered','["e1"]','transport',30,NULL);
-- e1.result was 'failed'

-- Relationship label without a relationship:
INSERT INTO turns(
  turn_id,tenant_id,turn_kind,parent_turn_id,chain_position,parent_kind
) VALUES ('x','owner','user_message',NULL,1,'reply');

-- Transport supersession without new evidence:
INSERT INTO turn_closures
VALUES ('c2','t1',2,'delivered','["e1"]','transport',31,NULL);

-- Doorway overwrites current transport truth:
INSERT INTO turn_closures
VALUES ('c2','t1',2,'refused','[]','doorway',31,NULL);

-- Run status transition without its claimed journal row:
UPDATE runs SET status='completed' WHERE run_id='r1';

-- Same logical effect claimed by the takeover epoch:
INSERT INTO effect_claims VALUES ('cl2','r2','action',30);

-- Same logical egress shape recreated by the takeover epoch:
INSERT INTO egress_intents
VALUES ('i2','r2','final_text',NULL,'telegram','h',30);

-- Evidence result deleted after closure insertion:
DELETE FROM egress_results WHERE result_id='e1';

-- Duplicate evidence membership:
INSERT INTO turn_closures
VALUES ('c1','t1',1,'delivered','["e1","e1"]','transport',4,NULL);

-- Cognition-capable run on an unsealed turn:
INSERT INTO runs VALUES ('r1','t1',1,1,'active',1,999);
```

All are **BREACHES** against the claimed append-only, sealed-membership, result chronology, closure-truth, or transition-history invariants.

One required lawful path instead failed closed, causing omission:

```sql
INSERT INTO admission_events
VALUES ('owner','ev1','t2',2,'h2',2);
```

After `('owner','ev1')` already identified the original payload, the different-payload correction was rejected by `admission_events`’ primary key. The comments promise a new correction turn, but provide no lawful constituent identity for it.

Reactivating an older epoch while a higher active epoch existed was correctly rejected by `one_active_run`; that positive control bites.

# 2. F1–F10 and residual blocker discharge

## F1-specific serialization judgment

The narrow snapshot argument is sound only under the stated transaction protocol:

- SQLite permits one writer at a time; a successful fresh `BEGIN IMMEDIATE` establishes the write transaction before the trigger reads status/epoch.
- A WAL reader holding a stale snapshot cannot later upgrade after another commit; SQLite returns `SQLITE_BUSY_SNAPSHOT`, requiring rollback and a fresh transaction.
- Therefore, takeover-first causes the old claim to see the committed supersession and reject.

That is supported by SQLite’s [transaction semantics](https://www.sqlite.org/lang_transaction.html) and [WAL snapshot-isolation rules](https://www.sqlite.org/isolation.html). It was not executable cross-process under the mandated in-memory-only restriction.

The overall F1 claim is nevertheless unsound: `effect_claims` has no immutable logical-effect identity or cross-epoch uniqueness. Claim-first, takeover-second, then a second claim from the new epoch all commit. The physical first effect may occur after takeover while the second epoch performs the duplicate.

## Discharge table

Round-3 statuses come from [the round-3 F1–F10 list](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-gate-round3.md:63), [ND table](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-gate-round3.md:25), and [residual B table](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-gate-round3.md:48).

| ID | Round-3 status | Round-4 verdict | Mechanism-based reason |
|---|---|---|---|
| F1 | BLOCKING | **STILL-OPEN** | `trg_effect_claims_fence` serializes a fresh claim transaction, but generic/deletable claims and per-run intent uniqueness permit duplicate logical effects across epochs; terminal resurrection also passes. |
| F2 | BLOCKING | **STILL-OPEN** | `turn_seals` and constituent guards work, but runs can start without a seal and `parent_kind` may exist without `parent_turn_id`; see [DDL parent/seal rules](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-schema-v2-draft.sql:27). |
| F3 | BLOCKING | **STILL-OPEN** | The DB commit precedes latch append. If restoration to the latest latch occurs inside that interval, position/hash equality silently accepts loss of the just-committed turn; “rewindable tail = zero” contradicts [§11’s admitted crash window](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:365). |
| F4 | BLOCKING | **STILL-OPEN** | §11 stores labels/privacy, but `validate_turn_stamp` also requires exact `turn_kind` and potentially caller identity; those carriers are absent from the journal schema. See [taint_stamping.py](/home/rohit/maez/core/ledger/taint_stamping.py:91) and [writer caller derivation](/home/rohit/maez/core/ledger/writer.py:295). |
| F5 | BLOCKING | **STILL-OPEN** | “Canonical entry bytes” and footer domain are undefined; `journal_folds` is nullable, marker-only, and deletable. The existing ledger hash contract shows the missing specificity at [chain.py](/home/rohit/maez/core/ledger/chain.py:80). |
| F6 | BLOCKING | **STILL-OPEN** | `fuser`/service/sidecar checks are snapshots; `flock` is advisory and old-inode scoped across rename. Current writers do not take a cooperating flock ([writer.py](/home/rohit/maez/core/ledger/writer.py:207)); the ceremony check also omits `maez-web.service` ([birth_ceremony.py](/home/rohit/maez/scripts/birth_ceremony.py:34)). |
| F7 | BLOCKING | **STILL-OPEN** | Current `canonical_row_bytes` hashes caller-supplied keys minus exclusions; there is no ordered v2 projection/default map ([chain.py](/home/rohit/maez/core/ledger/chain.py:69)). Writer hashes before resolving lifecycle ([writer.py](/home/rohit/maez/core/ledger/writer.py:441)); genesis and verifier still supply different row shapes ([migrate.py](/home/rohit/maez/core/ledger/migrate.py:43), [verifier](/home/rohit/maez/scripts/verify_ledger_chain.py:77)). |
| F8 | BLOCKING | **STILL-OPEN** | In-row JSON fixes insertion order and closure-row mutation, but cited results remain deletable and closure outcome is not checked against result outcome; see `trg_turn_closures_topology`. |
| F9 | BLOCKING | **STILL-OPEN** | Same-intent/self checks bite, but result chains fork and retry ordinals duplicate because neither `supersedes_result` nor `(intent_id,retry_ordinal)` is unique. |
| F10 | BLOCKING | **STILL-OPEN** | Named self/future/cross-tenant/anchor attacks reject, but the reverse relationship implication is absent: `parent_kind='reply'` with NULL parent succeeds. |
| ND1 | PARTIAL | **STILL-OPEN** | §11 refers to “§2’s table,” but §2 contains only a `Door(...)` type signature, not entries or a literal primitive set ([§2](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:57)). Current repo has 138 Flask registrations, 42 Telegram handler registrations, dynamic `getattr` dispatch ([telegram_egress.py](/home/rohit/maez/core/egress/telegram_egress.py:383)), and a raw Bot-API bypass ([dev_notifier.py](/home/rohit/maez/skills/dev_notifier.py:41)). |
| ND2 | PARTIAL | **STILL-OPEN** | An edit is a distinct intent, but `trg_egress_results_supersede_same_intent` forbids its result from superseding the prior final-text intent, contradicting [§2’s edit rule](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:91). |
| ND3 | PARTIAL | **STILL-OPEN** | Late constituent INSERT/UPDATE is closed, but `runs` accepts an unsealed turn; §3.1’s transaction list does not coherently include the new `turn_seals` row. |
| ND4 | UNDERSPECIFIED | **STILL-OPEN** | `(tenant_id,event_identity)` PK rejects the promised same-identity/different-payload correction constituent; the DDL comment supplies no versioned identity or correction-membership row. |
| ND5 | PARTIAL | **STILL-OPEN** | Dense epochs and one-active index work, but arbitrary status resurrection, unjournaled transitions, and cross-epoch duplicate claims remain legal. |
| ND7 | UNDERSPECIFIED | **STILL-OPEN** | Dense closure ordinals work; the claimed lattice does not prevent doorway-over-transport or transport supersession reusing identical evidence. |
| ND8 | NOT DISCHARGED | **STILL-OPEN** | Same-turn membership is checked only at insertion; JSON references are not FKs, so a cited result can later be deleted, duplicated, or semantically contradict the closure. |
| ND9 | PARTIAL | **STILL-OPEN** | Late acknowledgments are representable, but duplicate retry ordinals and forked observation heads remain legal. |
| ND10 | PARTIAL | **STILL-OPEN** | `uq_egress_intent_shape` is scoped to `run_id`; a takeover epoch can create the same logical send shape, so “must not blindly resend” is not enforced. |
| ND11 | PARTIAL | **DISCHARGED** | For its narrow no-orphan-reply criterion, FK/self-check plus `trg_turns_parent_semantics` and `trg_turns_reply_needs_parent` reject nonexistent, NULL, self, future, and cross-tenant parents. |
| ND12 | PARTIAL | **STILL-OPEN** | Same as F3: the post-COMMIT pre-latch interval remains silently rewindable against the latest latch. |
| ND13 | PARTIAL | **STILL-OPEN** | “Complete expected table set” and “pass 2’s list plus” remain references rather than an enumerated executable schema/consumer census ([§5](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:204)). |
| ND15 | PARTIAL | **STILL-OPEN** | `journal_folds` can be inserted without a folded turn and later deleted; exact hash/footer and multi-row fold bindings remain undefined. |
| ND16 | NOT DISCHARGED | **STILL-OPEN** | Anchor boolean/uniqueness is fixed, but F6 recreate exclusivity and F7 domain canonicalization remain open. |
| B1 | PARTIAL | **STILL-OPEN** | D-public is fixed, but no literal door or primitive inventory exists; `core/ledger/doorways.py` is absent. |
| B2 | PARTIAL | **STILL-OPEN** | Per-door identities remain unspecified, correction identity is impossible under the PK, and parent typing is only one-way. |
| B3 | PARTIAL | **STILL-OPEN** | Durable claims exist, but they neither identify nor uniquely reserve a logical effect across epochs. |
| B5 | NOT DISCHARGED | **STILL-OPEN** | Current closure can cite false or deleted result truth, and result chronology may fork. |
| B6 | PARTIAL | **STILL-OPEN** | Pass 4 does not bind the latch to a canonical ledger identity/path or enumerate the complete gestation structural contract. |
| B7 | PARTIAL | **STILL-OPEN** | Post-COMMIT latch gap and incomplete phase-consumer census remain. |
| B8 | PARTIAL | **STILL-OPEN** | Failure-time stamps improve the design, but incomplete stamp carriers, undefined journal hash domain, and deletable fold markers prevent truthful reconstruction. |
| B9 | NOT DISCHARGED | **STILL-OPEN** | Recreate exclusivity is racy and the v2 projection/default map is promised rather than frozen; current `ledger_is_initialized` only proves that the head points to some row, not the actual tip ([migrate.py](/home/rohit/maez/core/ledger/migrate.py:294)). |
| B10 | NOT DISCHARGED | **STILL-OPEN** | Two independent Poisson processes at 1/s for 500 s have expected—not exact—`N=1000`; §6 says per-admission wait while §11 says per-transaction wait, and the seed, percentile convention, lock-wait boundary, and synchronized positive-control schedule remain unfrozen ([§11 B10](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:416)). |

ND6, ND14, B4, and the earlier B11 discharge remain discharged; this review does not re-open their narrow rulings.

# 3. New-defect list

1. **Systemic DELETE hole.** `run_events`, `effect_claims`, `egress_intents`, `egress_results`, and `journal_folds` call themselves append-only but define only `BEFORE UPDATE` triggers ([DDL](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-schema-v2-draft.sql:148)). `runs` is also freely deletable when no FK currently references it.

2. **Closure outcome is not evidence-derived.** `trg_turn_closures_topology` validates only result existence and turn membership; a `delivered` closure can cite `failed`, `suppressed`, or `timeout_unknown`.

3. **Canonical evidence is not canonical or set-like.** Duplicate result IDs and noncanonical JSON encodings are accepted even though the DDL calls `evidence_json` a canonical array.

4. **F7’s migration census omits production hash consumers.** Beyond the named writer/genesis/verifier, [citation_lock.py](/home/rohit/maez/core/consolidation/citation_lock.py:261) and [span_reader.py](/home/rohit/maez/core/ledger/span_reader.py:277) recompute hashes without a `chain_hash_domain` input.

# 4. Per-slice S1–S6 verdict

| Slice | Verdict | Deciding reason |
|---|---|---|
| S1 — phase truth | **BLOCKED** | F3’s post-COMMIT latch window, missing canonical ledger binding, and unclosed phase census. |
| S2 — schema v2 | **BLOCKED** | F7–F10, correction omission, deletable evidence, forked results, false closure binding, and unsafe recreation. |
| S3 — rail + registry | **BLOCKED** | F1 lacks cross-epoch logical-effect reservation; ND1/B1 inventory and per-door identities are not frozen. |
| S4 — egress truth | **BLOCKED** | Edit lineage contradicts the same-intent trigger; result heads fork; takeover epochs may duplicate sends; closure truth can be false or dangling. |
| S5 — universe sweep | **BLOCKED** | There is no literal registry-entry set, primitive list, reachability grammar, or per-producer identity oracle to test against. |
| S6 — posture | **BLOCKED** | Journal stamp carrier and hash domain remain underspecified, fold markers are deletable, and B10’s workload is internally inconsistent. |

# 5. Overall verdict

**HOLD. No S1–S6 slice may begin binding witness-protocol authoring from design pass 4.**

The 22 named negative controls are valid and should be retained for the future S2 protocol, but they do not close the newly executed counterexamples or the non-SQL contract gaps.

Plainly: the draft successfully blocks yesterday’s attacks, but it can still erase the proof rows, resurrect completed work, authorize the same effect in two epochs, fork delivery truth, and call a failed result “delivered.” That is not yet a trustworthy pre-birth ledger design.