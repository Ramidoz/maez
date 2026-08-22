# Gate round 10 on Theme 2 (6335174) — schema CLEAN; S2 authoring UNLOCKED; S1 code held on 6 literals

Codex, `--effort xhigh`. **DDL revision 8 passed every retained suite
and every round-9 fold** (N 22/22, R4 21/21, R5 2/2, P 26/26 + 16 +
5, Q 25/25, C8 9/9, lawful 6+3+3, plus the four rev-8 controls), and
all three requested abuse probes were NOT REPRODUCIBLE: journal-fold
laundering across turns rejects (the trigger compares folded_turn_id
to the actual turn), the exhaustive view does not false-positive on
refused/unresolved_crash, and the lawful timeout→delivered late-ack
path survives the no-op-supersession ban. All four companion-artifact
digests MATCH. The frozen T6 inventory reproduced independently
twice, genesis hash confirmed deterministic.

**Rulings: S2 protocol authoring MAY BEGIN. S1 code may not** — six
specific literalization items remain, one per test:
T1 exact expected reason per cell; T2 frozen latch-line field order
and mate-line bytes; T3 invocation + expected outcome for
AuditLog._migration_null_normalize; T4 pinned census command; T5
committed baseline-archive path/digest; T6 mutation 6 must account
for the existing turns_no_update trigger.

Overall: HOLD, advancing.

---

Full gate text follows.

Round-9 findings file was absent; commit `6335174`’s git-log summary was used as the requested fallback.

## 1. DDL revision 8 execution

Execution used SQLite 3.46.1, `:memory:`, `foreign_keys=ON`, and the literal `turns` fragment from [DDL revision 8](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-schema-v2-draft.sql). `integrity_check=ok`.

- **PASS — DDL load:** 11 tables, 37 triggers, 5 indexes, 3 views.
- **PASS — N01–N22 retained invalid-row rejection:** 22/22.
- **PASS — R4-01–R4-21 retained invalid-row rejection:** 21/21.
- **PASS — R5 ordinal controls:** 2/2.
- **PASS — retained lawful paths:** 6/6.
- **PASS — P01–P26:** 26/26.
- **PASS — P22 append-only subcases:** 16/16.
- **PASS — P26 null-ID subcases:** 5/5.
- **PASS — Q03–Q12/Q22–Q35:** 25/25 statements.
- **PASS — three retained lawful variants:** 3/3.
- **PASS — C8 retained criteria:** 9/9; C8 lawful paths 3/3.
- **PASS — folded rows require their turn’s `journal_folds` row:** intent and reservation both rejected by `trg_egress_intents_fence` / `trg_egress_reservations_admission`, 2/2.
- **PASS — same-result supersession:** rejected by `trg_egress_results_supersede_same_attempt`.
- **PASS — folded-head consistency:** `closure_consistency_violations` returned exactly `[('t1','c1')]`.
- **PASS — `turns.tenant_id` byte discipline:** empty, embedded-NUL, and multibyte values rejected, 3/3.

## 2. Probe residue

- **a — Not reproducible.** With a `journal_folds` row only for turn A, folded intent and reservation activity for turn B both rejected with `folded rows require their journal fold`. The triggers compare `journal_folds.folded_turn_id` with the activity’s actual turn.

- **b — Not reproducible.** Lawful `refused/[]` and `unresolved_crash/[]` closures both inserted, while `closure_consistency_violations` remained empty. The view in [DDL revision 8](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-schema-v2-draft.sql) deliberately excludes those two closure classes.

- **c — The defined late-ack path is not broken.** Equal-value supersession rejected with `supersession must change the observed result`, but the declared lawful `timeout_unknown → delivered` late acknowledgment accepted and became the sole `current_results` head. The current [design’s `egress_results` construct](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md) defines that result-changing transition; it does not define equal-value re-observation as a new row.

## 3. T1–T6 BINDING-READY

The frozen T6 inventory independently reproduced twice: 7 tables, 6 triggers, 15 indexes, and genesis hash `d313c6473ea19dbe038d3f2f1d714d1ce8c0a9b8e756ef0d4b1849f8eb09989d`.

| Test | BINDING-READY | Single missing element |
|---|---|---|
| T1 | **No** | [Protocol §2/§9](/home/rohit/maez/docs/superpowers/witness/theme2-s1-protocol.md) says every cell asserts `PhaseResult.reason`, but supplies no exact expected reason per cell. |
| T2 | **No** | The exact JSONL segment and repaired mate-line bytes/field order remain unfrozen. |
| T3 | **No** | The census includes `AuditLog._migration_null_normalize`, but T3 supplies neither its public invocation nor expected outcome. |
| T4 | **No** | No exact census invocation/AST-normalization command is pinned. |
| T5 | **No** | The required baseline store archive has no committed path or digest. |
| T6 | **No** | Mutation 6 relies on an undefined “triggers-off connection”; the executed F-G schema contains `turns_no_update`, so the stated `UPDATE turns` is not executable as pinned. |

## 4. Artifact digests

- **MATCH —** [theme2-s1-census.json](/home/rohit/maez/docs/superpowers/witness/theme2-s1-census.json): `85276709…a3dc6`
- **MATCH —** [theme2-s1-replay.json](/home/rohit/maez/docs/superpowers/witness/theme2-s1-replay.json): `2b9faf61…b420`
- **MATCH —** [theme2-s1-selectors.txt](/home/rohit/maez/docs/superpowers/witness/theme2-s1-selectors.txt): `7759da99…b6d4`
- **MATCH —** [theme2_s1_fixtures.py](/home/rohit/maez/docs/superpowers/witness/theme2_s1_fixtures.py): `b69a8c0e…9dcb`

## 5. Rulings

- **S1 CODE may begin: No.** T1–T6 remain 0/6 BINDING-READY for the specific literalization findings above.
- **S2 protocol authoring may begin: Yes.** DDL revision 8 passed every retained suite and round-9 fold; probes a–c produced no unresolved schema-conformance finding under the declared design.
- **Overall verdict: HOLD.** Schema conformance may advance to S2 protocol authoring, but S1 code remains barred pending the six protocol elements.

