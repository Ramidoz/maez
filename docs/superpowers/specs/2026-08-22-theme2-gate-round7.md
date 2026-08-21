# Gate round 7 on Theme 2 (b50dae7) — HOLD, and S1 UNLOCKED

Codex, `--effort xhigh`. **Everything retained passes: 45/45 invalid
controls, 26/26 P-probes, 24/24 Q-criteria, all lawful paths.** The
three §13/§14 executability judgments are now DESIGN DISCHARGED
(ND1/B1 registry, ND13/B6 phase fingerprint, F6 recreate protocol).

**S1 — phase truth: MAY BEGIN binding witness-protocol authoring.**
The first slice to clear the gate in seven rounds. Its protocol must
freeze exact migration digests, trigger/index lists, genesis bytes,
the enumerated consumer constructs, and heartbeat readers.

S2–S6 remain held on a finite, fully-executed design list, R7-01–R7-10:

1. **R7-01 (load-bearing)** — reservation eligibility passes when the
   prior attempt has NO result: `NULL NOT IN ('failed','suppressed')`
   is unknown, the WHEN never fires. SQL-NULL semantics defeat the
   pre-send gate exactly when the prior outcome is most unknown.
2. R7-02 — reservation/result chronology unbound (run ≤ intent ≤
   reservation ≤ result ordering not enforced).
3. R7-03 — takeover has NO lawful retry path: the old intent's run is
   terminal, the new run can't recreate the slot. Needs an
   inherited-intent model (reservation fences the authorizing run
   separately from the originating run).
4. R7-04 — a correction turn can acquire a later unrelated
   constituent (one-directional enforcement).
5. R7-05 — closure evidence is not exhaustive: a failed closure can
   omit a delivered result on another intent; delivered can omit a
   result-less reservation.
6. R7-06 — later egress can invalidate the committed current closure;
   atomic closure-advancement contract needed.
7. R7-07 — `suppressed` and `unresolved_crash` labels unmapped.
8. R7-08 — empty-string ids/transport/identity accepted; embedded-NUL
   defeats the ASCII GLOB check.
9. R7-09 — finite/causal time missing on turns/admission/seals/folds
   and claims-vs-run.
10. R7-10 — `turn_kind` domain and reply-parent direction mapping
    incomplete in the baseline.

Verdict: HOLD for S2–S6; S1 authorized. The reviewer's judgment on
the design-level list: "not empty and not nearly empty" — three items
(reservation authority, takeover retries, closure completeness) are
load-bearing S2/S4 semantics, the rest mechanical.

---

Full gate text follows.

# Round 7 verdict: HOLD

DDL revision 5 closes every requested Q03–Q12/Q22–Q35 counterexample, but schema conformance is still **NO**. The new reservation gate contains a load-bearing SQL-NULL defect, closure evidence is not exhaustive, correction turns can still acquire extra constituents, and several identity/time carriers remain incomplete.

Only **S1 — phase truth** may begin binding witness-protocol authoring. S2–S6 remain held.

Review facts:

- Target files exactly matched commit `b50dae70c9d99e9e108fa351419855fdbcba7a84`.
- SQLite 3.46.1, `PRAGMA foreign_keys=ON`, fresh `:memory:` databases, STRICT turns baseline.
- Eleven user tables loaded as STRICT; `PRAGMA integrity_check` returned `ok`.
- No repository test suite ran.
- No repository file or repository `memory/` path was read or modified.

## 1. Executed-suite pass/fail table

### Aggregate result

| Suite | Executed result | Verdict |
|---|---:|---|
| Rounds 2–3 N01–N22 | 22/22 rejected | PASS |
| Round-4 R4-01–R4-21 | 21/21 rejected | PASS |
| Round-5 wrong-ordinal controls | 2/2 rejected | PASS |
| Total retained invalid-row controls | **45/45 rejected** | **PASS** |
| Six retained lawful paths | **6/6 accepted** | **PASS** |
| P01–P26 | **26/26 behaved as specified** | **PASS** |
| P22 append-only subcases | 16/16 rejected | PASS |
| P26 NULL-ID subcases | 5/5 rejected | PASS |
| Requested Q03–Q12/Q22–Q35 | **24/24 criteria; 25/25 SQL statements behaved as rev-5 expects** | **PASS** |
| Three requested lawful variants | **3/3 accepted** | **PASS** |

### Retained invalid-row controls

| Group | IDs | Observed result |
|---|---|---|
| Parent/run/admission | N01–N11 | All rejected: second active run; non-dense epoch; self/NULL/future/kindless parent; invalid/second birth anchor; sealed-turn admission; admission mutation; cross-tenant membership |
| Egress/closure/fencing | N12–N22 | All rejected: duplicate send slot; self/cross-intent result supersession; empty/cross-turn closure evidence; duplicate/gapped closure; reconciler-after-transport; closure mutation; stale-run claim/intent |
| Result/run/append-only | R4-01–R4-13 | All rejected, including result-chain fork, terminal resurrection, malformed JSON, six DELETE paths, and duplicate physical attempt |
| Closure/relationship/takeover | R4-14–R4-21 | All rejected: false delivered label, parent label without parent, unchanged transport evidence, doorway-after-transport, duplicate effect/send across epochs, duplicate evidence, unsealed cognition |
| Supersession ordinal | R5-01/R5-02 | Incremented and decremented superseding ordinals both rejected: `supersession re-observes the same attempt: retry_ordinal must match` |

### P01–P26

| Probe | Exact operation or operation family | Observed outcome |
|---|---|---|
| P01 | `UPDATE runs SET status='completed' WHERE run_id='r1'` | Accepted; exactly one `active → completed` event |
| P02 | `UPDATE runs SET lease_until=1000 WHERE run_id='r1'` | Accepted; lease `1000`, zero events |
| P03 | `INSERT INTO run_events ... ('r1','completed','completed',30)` | Rejected: `transitions only leave active` |
| P04 | `UPDATE runs SET lease_until=20 WHERE run_id='r1'` | Rejected: `lease renewal must strictly advance` |
| P05 | Supersede r1, then `INSERT INTO runs VALUES ('r2','t1',2,2,'active',21,30)` | Accepted |
| P06 | Same r2 insert before superseding r1 | Rejected: `UNIQUE constraint failed: runs.turn_id` |
| P07 | Revision 2 on ordinary t1 | Rejected: `a correction revision must land on a correction turn` |
| P08 | Revision 3 immediately after revision 1 | Rejected: `revision must be dense per identity` |
| P09 | Transport evidence `["e2","e1"]` | Rejected: `closure evidence must be sorted canonical form` |
| P10 | Object evidence `{"only":"e1"}` | Rejected: `closure evidence must be a JSON array` |
| P11 | Closure cites superseded e1 | Rejected: `closure evidence must be current result heads` |
| P12 | Mixed current heads from attempts 1 and 2 | Accepted |
| P13 | Doorway delivered with `[]` | Rejected: `outcome closures require evidence` |
| P14 | Reconciler without `discovered_at` | Rejected: `reconciler closures carry discovered_at` |
| P15 | First reservation at ordinal 2 | Rejected: `reservations are dense per intent` |
| P16 | Retry reservation after `timeout_unknown` | Rejected: prior attempt not resolved as non-delivered |
| P17 | Second final-text slot | Rejected by `UNIQUE(turn_id,egress_kind)` |
| P18–P21 | Turn UPDATE/DELETE cases | 4/4 rejected: `turns is append-only` |
| P22 | `UPDATE table SET pk=pk` and `DELETE FROM table` on the eight retained append-only tables | 16/16 rejected |
| P23 | Shared-memory connection B during A’s `BEGIN IMMEDIATE`; stale revision after A commit; next dense revision | Locked; then stale revision rejected; next dense revision accepted |
| P24 | NULL `journal_entry_id` | Rejected: NOT NULL |
| P25 | NULL seal `turn_id` | Rejected: NOT NULL |
| P26 | NULL run/claim/intent/result/closure IDs | 5/5 rejected: NOT NULL |

### Lawful paths

| Path | Exact decisive statement | Result |
|---|---|---|
| Same-attempt late acknowledgment | `INSERT INTO egress_results VALUES ('e2','i1',1,'delivered',14,'e1')` | Accepted; e2 became current head |
| Current-run cognition | `INSERT INTO effect_claims VALUES ('cl1','t1','r1','cognition_commit','cog:1',12)` | Accepted with admission + seal |
| Correction revision | `INSERT INTO admission_events VALUES ('owner','ev1',2,'t2',2,'bbbb',3)` | Accepted on new correction child |
| Auto-journal transition | `UPDATE runs SET status='completed' WHERE run_id='r1'` | Accepted; one event |
| Same-turn edit lineage | `INSERT INTO egress_intents VALUES ('i2','t1','r1','edit',NULL,'telegram','cccc','i1',12)` | Accepted |
| Update-then-insert takeover | `INSERT INTO runs VALUES ('r2','t1',2,2,'active',21,30)` | Accepted after r1 superseded |
| Mixed current heads, different attempts | Partial closure citing `["e1","e2"]` | Accepted |
| Reserved retry after resolved failure | `INSERT INTO egress_reservations VALUES ('i1',2,14)` | Accepted |
| Outbound reply with reply parent | `INSERT INTO turns VALUES ('t2','owner','model_reply',3,4,'out','t1',2,'reply',0)` | Accepted |

## 2. New consistency findings

The reservation controls that work are real:

```sql
-- Gap:
INSERT INTO egress_reservations VALUES ('i1',2,12);
-- REJECT: reservations are dense per intent

-- Prior delivered:
INSERT INTO egress_reservations VALUES ('i1',2,14);
-- REJECT: a new attempt requires the prior attempt resolved as non-delivered

-- Result without reservation:
INSERT INTO egress_results VALUES ('e1','i1',1,'failed',13,NULL);
-- REJECT: a result requires its pre-send reservation

UPDATE egress_reservations SET reserved_at=13
WHERE intent_id='i1' AND retry_ordinal=1;
-- REJECT: egress_reservations is append-only

DELETE FROM egress_reservations
WHERE intent_id='i1' AND retry_ordinal=1;
-- REJECT: egress_reservations is append-only
```

Those controls do not close the following.

### R7-01 — Missing prior result passes retry eligibility

Fixture: reservation 1 exists for i1, but it has no result.

```sql
INSERT INTO egress_reservations VALUES ('i1',2,13);
```

Observed:

```text
ACCEPT; COMMIT succeeded
SELECT retry_ordinal ... → [(1,), (2,)]
PRAGMA integrity_check → ok
```

Cause: the scalar subquery in [`trg_egress_reservations_admission`](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-schema-v2-draft.sql:363) returns NULL when attempt 1 has no current result. `NULL NOT IN ('failed','suppressed')` is unknown, so the `WHEN` does not fire.

This permits a second pre-send reservation precisely while the first attempt has unresolved outcome. This is a **DESIGN-LEVEL blocker for S2/S4**.

### R7-02 — Reservation/result chronology remains misordered

```sql
-- Run started_at=10; intent created_at=11
INSERT INTO egress_reservations VALUES ('i1',1,5);
```

Observed:

```text
ACCEPT → reserved_at=5, created_at=11, started_at=10
```

```sql
-- Reservation reserved_at=15
INSERT INTO egress_results
VALUES ('e1','i1',1,'failed',13,NULL);
```

Observed:

```text
ACCEPT → observed_at=13, reserved_at=15
```

```sql
-- Attempt 1 result observed_at=20
INSERT INTO egress_reservations VALUES ('i1',2,15);
```

Observed:

```text
ACCEPT → retry 2 reserved before retry 1 was observed
```

Rev 5 bounds these times but does not enforce:

```text
run.started_at ≤ intent.created_at ≤ reservation.reserved_at
reservation.reserved_at ≤ result.observed_at
prior-current-result.observed_at < next-reservation.reserved_at
```

### R7-03 — Takeover has no lawful retry path

Fixture: r1 owns final-text intent i1; attempt 1 failed; r1 is superseded; r2 is active.

```sql
INSERT INTO egress_reservations VALUES ('i1',2,22);
```

Observed:

```text
REJECT: reservation requires an active run
```

Trying to give r2 a new intent also fails:

```sql
INSERT INTO egress_intents
VALUES ('i2','t1','r2','final_text',NULL,'telegram','cccc',NULL,22);
```

Observed:

```text
REJECT: UNIQUE constraint failed:
egress_intents.turn_id, egress_intents.egress_kind
```

The old intent cannot be retried because its owning run is terminal, while the current run cannot create the already-reserved logical send slot. The design needs an explicit inherited-intent retry model—most likely a reservation that records and fences the current authorizing run separately from the intent’s originating run.

### R7-04 — Correction turn can acquire another constituent

Fixture: ev1 revision 2 lawfully occupies correction turn t2.

```sql
INSERT INTO admission_events
VALUES ('owner','other-event',1,'t2',3,'cccc',4);
```

Observed:

```text
ACCEPT
SELECT event_identity,revision
FROM admission_events WHERE turn_id='t2'
→ [('ev1',2), ('other-event',1)]
```

The trigger prevents inserting a correction revision into an already occupied turn, but it does not prevent a later revision-1 event from joining that correction turn. Thus the comment “a correction turn hosts exactly one revision” is only one-directionally enforced.

### R7-05 — Closure evidence is not exhaustive

With one failed intent and another delivered intent:

```sql
INSERT INTO turn_closures
VALUES ('c1','t1',1,'failed','["e1"]','transport',20,NULL);
```

Observed:

```text
ACCEPT → current closure is failed; e2(delivered) was omitted
```

With one delivered result and another reserved attempt lacking a result:

```sql
INSERT INTO turn_closures
VALUES ('c1','t1',1,'delivered','["e1"]','transport',20,NULL);
```

Observed:

```text
ACCEPT → current closure delivered; one reservation remains result-less
```

With timeout e1 on one intent and delivered e2 on another:

```sql
INSERT INTO turn_closures
VALUES ('c1','t1',1,'unknown_delivery','["e1"]','transport',20,NULL);
```

Observed:

```text
ACCEPT → delivered e2 was omitted
```

The closure trigger validates cited rows, but does not prove that the evidence covers all current intent/attempt heads and all pending reservations for the turn.

### R7-06 — Later egress can invalidate the current closure

After a failed closure and a lawful retry reservation:

```sql
INSERT INTO egress_results
VALUES ('e2','i1',2,'delivered',22,NULL);
```

Observed:

```text
ACCEPT
current closure = failed
current results = failed,delivered
```

After an `unknown_delivery` closure citing timeout e1:

```sql
INSERT INTO egress_results
VALUES ('e2','i1',1,'delivered',21,'e1');
```

Observed:

```text
ACCEPT
current closure = unknown_delivery
evidence_json = ["e1"]
e1 is no longer a current result head
```

After a refused closure:

```sql
INSERT INTO egress_intents
VALUES ('i1','t1','r1','final_text',NULL,'telegram','bbbb',NULL,21);
```

Observed:

```text
ACCEPT
current closure = refused
egress_intent count = 1
```

A build transaction could append a replacement closure together with new knowledge, but pass 7 does not state or enforce that atomic contract. Without it, committed current closures can cease to conform.

### R7-07 — Two closure labels remain unmapped

Against a delivered current result:

```sql
INSERT INTO turn_closures
VALUES ('c1','t1',1,'suppressed','["e1"]','transport',20,NULL);
```

```text
ACCEPT
```

```sql
INSERT INTO turn_closures
VALUES ('c1','t1',1,'unresolved_crash','["e1"]','transport',20,NULL);
```

```text
ACCEPT
```

Pass 7 says closure evidence semantics exist for every label, but [`trg_turn_closures_topology`](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-schema-v2-draft.sql:489) has no label-specific branches for `suppressed` or `unresolved_crash`.

### R7-08 — Empty and noncanonical carriers remain accepted

These exact statements accepted and committed:

```sql
INSERT INTO runs
VALUES ('','t1',1,1,'active',10,20);

INSERT INTO effect_claims
VALUES ('','t1','r1','action','act:1',12);

INSERT INTO egress_intents
VALUES ('','t1','r1','final_text',NULL,'telegram','bbbb',NULL,11);

INSERT INTO egress_results
VALUES ('','i1',1,'failed',13,NULL);

INSERT INTO turn_closures
VALUES ('','t1',1,'refused','[]','doorway',5,NULL);

INSERT INTO journal_folds
VALUES ('','aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
        't1',4);

INSERT INTO turns
VALUES ('','owner','user_message',1,2,'in',NULL,1,NULL,0);

INSERT INTO admission_events
VALUES ('owner','',1,'t1',1,'',2);

INSERT INTO egress_intents
VALUES ('i1','t1','r1','final_text',NULL,'','bbbb',NULL,11);

INSERT INTO egress_intents
VALUES ('i1','t1','r1','final_text',NULL,'telegram','x',NULL,11);
```

Observed lengths were zero for the empty IDs/transport. Both admission identity/hash were empty, and the egress `payload_hash='x'` had length 1.

The printable-ASCII CHECK also has an embedded-NUL edge:

```sql
INSERT INTO runs
VALUES ('r'||char(0)||'é','t1',1,1,'active',10,20);
```

Observed:

```text
ACCEPT
hex(run_id) = 7200C3A9
length(run_id) = 1
run_id NOT GLOB '*[^ -~]*' = 1
```

A plain Unicode result ID correctly rejected, so the issue is specifically the NUL-truncated TEXT/GLOB behavior.

### R7-09 — “Finite time everywhere” is not true

All these statements accepted:

```sql
INSERT INTO turns
VALUES ('t1','owner','user_message',1e999,1e999,'in',NULL,1,NULL,0);
-- occurred_at=inf, admitted_at=inf

INSERT INTO admission_events
VALUES ('owner','ev1',1,'t1',1e999,'aaaa',1e999);
-- occurred_at=inf, admitted_at=inf

INSERT INTO turn_seals VALUES ('t1',1e999);
-- sealed_at=inf

INSERT INTO journal_folds
VALUES ('j1','aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
        't1',1e999);
-- folded_at=inf
```

A claim can also predate its run:

```sql
-- r1.started_at=10
INSERT INTO effect_claims
VALUES ('cl1','t1','r1','action','act:1',5);
```

Observed:

```text
ACCEPT → claimed_at=5, started_at=10
```

The finite/causal treatment in rev 5 therefore covers only some time columns.

### R7-10 — Kind/relationship mapping remains partial

```sql
INSERT INTO turns
VALUES ('t1','owner','invented_kind',1,2,'out',NULL,1,NULL,0);
```

Observed:

```text
ACCEPT → ('invented_kind','out')
```

A reply may also name an outbound reply as its parent:

```sql
INSERT INTO turns
VALUES ('t2','owner','model_reply',3,4,'out','t1',3,'reply',0);
```

With t1 itself outbound, this accepted. Rev 5 correctly maps the named reply/message kinds and correction children, but it does not define the complete `turn_kind` domain or the permitted direction/kind of a `parent_kind='reply'` parent.

## 3. Updated Q-list and section 13 judgments

### Q01–Q35

`EXECUTED` below means replayed this round. `RETAINED` means outside the user-specified Q03–Q12/Q22–Q35 replay subset and not presented as a new execution result.

| Q | Round-7 state | Exact result or qualification |
|---|---|---|
| Q01 | RETAINED PASS | Resolved failure permits retry; separately confirmed by requested lawful variant |
| Q02 | RETAINED PASS | Delivered head forecloses retry; separately confirmed by reservation control |
| Q03 | **DISCHARGED — EXECUTED** | Retry at time 5 after prior observation 10 rejected: `retry chronology must advance` |
| Q04 | **DISCHARGED — EXECUTED** | Earlier superseding observation rejected |
| Q05 | **DISCHARGED — EXECUTED** | Duplicate run event rejected by `UNIQUE(run_id)` |
| Q06 | **DISCHARGED — EXECUTED** | Equal lease renewal rejected |
| Q07 | **DISCHARGED — EXECUTED** | Terminal transition changing lease rejected |
| Q08 | **DISCHARGED narrowly — EXECUTED** | Same-turn revision 3 rejected; R7-04 finds the reverse insertion order remains open |
| Q09 | **DISCHARGED — EXECUTED** | Unrelated correction ancestry rejected |
| Q10 | **DISCHARGED — EXECUTED** | `final_text` with ordinal rejected |
| Q11 | **DISCHARGED — EXECUTED** | `part` without ordinal rejected |
| Q12 | **DISCHARGED — EXECUTED** | Self-edit rejected |
| Q13–Q17 | RETAINED PASS | JSON canonicalization rules unchanged; direct non-ASCII result IDs are now refused earlier |
| Q18 | **PARTIAL** | Plain Unicode ID refused, but R7-08’s embedded-NUL value defeats the claimed ASCII-only carrier posture |
| Q19–Q21 | RETAINED PASS | Lossless STRICT coercion/BLOB/fractional-INTEGER judgments unchanged |
| Q22 | **DISCHARGED — EXECUTED** | `1e999` run time rejected |
| Q23 | **DISCHARGED — EXECUTED** | Lease before start rejected |
| Q24 | **DISCHARGED — EXECUTED** | Closure before evidence rejected |
| Q25 | **DISCHARGED — EXECUTED** | Discovery after recording rejected |
| Q26 | **DISCHARGED narrowly — EXECUTED** | Failed citing timeout rejected; evidence completeness remains open |
| Q27 | **DISCHARGED narrowly — EXECUTED** | Unknown citing delivered rejected; omitted delivery remains possible |
| Q28 | **DISCHARGED narrowly — EXECUTED** | Refused citing delivery rejected; later intent insertion remains possible |
| Q29 | **DISCHARGED — EXECUTED** | Evidence-free unknown rejected |
| Q30 | **DISCHARGED — EXECUTED** | `attempt=99, epoch=2` rejected |
| Q31 | **DISCHARGED narrowly — 2/2 EXECUTED** | Empty effect identity and egress payload hash rejected; other empty carriers remain |
| Q32 | **DISCHARGED — EXECUTED** | Cognition without admission rejected |
| Q33 | **DISCHARGED narrowly — EXECUTED** | Exact model-reply/correction/inbound row rejected; complete kind/parent mapping remains open |
| Q34 | **DISCHARGED — EXECUTED** | Intent before run rejected |
| Q35 | **DISCHARGED — EXECUTED** | Empty journal digest rejected |

### Section 13 / pass-7 judgments

These are design-text judgments; their eventual implementations were not executable in this in-memory review.

| Criterion | Round-7 judgment | Reason |
|---|---|---|
| ND1/B1 registry executability | **DESIGN DISCHARGED; BUILD UNVERIFIED** | Pass 7 supplies the missing closure-owner/egress-kind columns, freezes a finite primitive tuple, places allowlists in the registry with mandatory justification, and explicitly requires qualname pinning during S3 authoring. That is sufficient to begin protocol construction. |
| ND13/B6 phase fingerprint | **DESIGN DISCHARGED; BUILD UNVERIFIED** | Pass 7 requires exact migration names/digests, exact trigger/index sets, byte-exact v2 genesis projection, head=tip comparison, and a census that freezes exact constructs during S1 authoring. |
| F6 recreate-empty soundness | **DESIGN DISCHARGED; BUILD UNVERIFIED** | The three round-6 cases are now addressed: never-replaced lock inode plus inode recheck; rail-version last-boot markers for both services; temp DB built/closed in rollback-journal mode and verified sidecar-free. Integration witnesses remain mandatory. |

These judgments are grounded in [design pass 7 §14](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:573). They do not override the new executed schema findings above.

## 4. DESIGN-LEVEL vs BUILD-LEVEL gap split

### DESIGN-LEVEL

| Gap | Deciding evidence |
|---|---|
| Fix reservation eligibility when the preceding reservation has no current result | R7-01 accepted and committed |
| Bind reservation/result timestamps causally | R7-02 |
| Define takeover ownership/inheritance for retries of an existing logical intent | R7-03 |
| Make “one correction revision per correction turn” symmetric against later inserts | R7-04 |
| Require closure evidence to cover every current result head and every result-less reservation relevant to the turn | R7-05 |
| Define and enforce atomic closure advancement when later intent/result knowledge is appended | R7-06 |
| Define evidence semantics for `suppressed` and `unresolved_crash` | R7-07 |
| Require nonempty IDs, event identities, transports, and actual digest formats; exclude embedded NUL | R7-08 |
| Apply finite-time constraints to all promised time carriers and complete causal claim ordering | R7-09 |
| Finish the `turn_kind` domain and parent-kind/parent-direction mapping | R7-10 |

**Judgment:** the DESIGN-LEVEL list is **not empty and not nearly empty**. Several repairs are mechanically small, but reservation authority, takeover retries, and closure completeness are load-bearing S2/S4 semantics.

### BUILD-LEVEL

Once the design items above are folded:

- Implement and witness the S1 migration/trigger/index/genesis fingerprints and exact consumer census.
- Implement the two-line advancing/committed latch and rewind/checkpoint/VACUUM classifications.
- Witness atomic admission/seal/run rollback and correction sequencing.
- Execute cross-process/WAL fencing and takeover ordering.
- Implement the six-field doorway registry, runtime registration, finite AST sweep, and pinned qualnames.
- Implement egress reservation/transport/closure transactions against the corrected contract.
- Implement journal stamps, entry hashes, segment footer, and atomic fold marker.
- Implement the one shared v2 projection across all five consumers.
- Witness F6 stable-lock/version-marker/rollback-temp recreation.
- Execute the frozen B10 workload and positive control.

## 5. S1–S6 verdict and overall gate

| Slice | Verdict | Binding witness-protocol authoring |
|---|---|---|
| S1 — phase truth | **DESIGN READY; BUILD UNVERIFIED** | **MAY BEGIN.** The protocol must freeze the exact migrations/digests, trigger/index list, genesis bytes, audit methods, and heartbeat readers. |
| S2 — schema v2 | **BLOCKED — DESIGN-LEVEL** | **No.** Reservation NULL behavior, correction membership, carrier/time gaps, and retry ownership remain open. |
| S3 — rail + registry | **BLOCKED — S2 DEPENDENCY** | **No full binding protocol yet.** Its registry design is ready, but the declared dependency remains S2 → S3. |
| S4 — egress truth | **BLOCKED — DESIGN-LEVEL** | **No.** Reservation eligibility, takeover retry, chronology, closure completeness, and post-closure consistency remain open. |
| S5 — universe sweep | **BLOCKED — DEPENDENCY** | **No full binding protocol yet.** The finite grammar is ready, but S5 depends on S2/S3. |
| S6 — posture | **BLOCKED — DEPENDENCY** | **No full binding protocol yet.** F6/B10 design is ready, but S6 depends on unresolved S2/S3 contracts. |

**Slices permitted to begin binding witness-protocol authoring: S1 only.**

**Overall verdict: HOLD — schema conformance is NO.**

Plainly: rev 5 fixed every named Q row, but a missing prior result still lets the next send reservation through because of SQLite’s NULL behavior. The schema can also call a turn failed, delivered, unknown, or refused while omitting contradictory or still-pending egress. Those states must be closed before S2 or S4 witness authoring begins.