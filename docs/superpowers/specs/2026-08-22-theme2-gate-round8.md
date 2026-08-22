# Gate round 8 on Theme 2 (6c1b37e) — HOLD; R7-01/03/04/10 discharged; C8 stratum + S1 protocol literalization

Codex, `--effort xhigh`. All retained suites pass (45/45, 26/26,
25/25 Q, 16/16, 5/5). **DISCHARGED: R7-01 (NULL-proof eligibility),
R7-03 (authorized-run takeover retry), R7-04 (correction symmetry),
R7-10 (kind/parent/direction domain).** PARTIAL: R7-02/05/06/07/08/09
via seven new executed findings:

- C8-01 reservation may predate its authorizing run's start.
- C8-02 unknown_delivery is not exhaustive — may omit a delivered head.
- C8-03 reconciler cannot lawfully repair a transport closure that
  late knowledge invalidated (precedence needs a flagged-view escape).
- C8-04 closed-turn refusal also blocks the journal fold of
  historical intents/reservations — the fold path needs a marked
  historical lane.
- C8-05 suppressed accepts empty evidence; unresolved_crash checks
  only cited rows, not turn-wide delivered heads.
- C8-06 event_identity/transport/tenant_id lack the byte-discipline
  the id columns got.
- C8-07 the turns-fragment REAL columns lack bounds in the literal
  fragment; cognition may predate its seal.

S1 witness protocol: 0/6 tests BINDING-READY — the judgment is about
literalization (fixture digests, frozen commands, exact-set SQL,
sorted census bytes, per-consumer exact outcomes), not about test
design. S1 authoring MAY CONTINUE; no S1 code until the protocol
passes. S2 may not begin authoring.

Verdict: HOLD.

---

Full gate text follows.

## 1. New consistency findings

Execution basis: HEAD `6c1b37e`; SQLite 3.46.1; `:memory:` only; `foreign_keys=ON`; 11 STRICT tables; `integrity_check=ok`. No repository tests ran, nothing was modified, and repository `memory/` was neither read nor touched.

Retained results: **45/45** invalid rows rejected; **6/6** lawful paths accepted; **P01–P26: 26/26**; **Q-statements: 25/25** rejected; P22 subcases **16/16**; P26 subcases **5/5**.

| ID | Executed SQL/scenario | Result |
|---|---|---|
| C8-01 | After `r1` failed and was superseded, create `r2(started_at=20)`, then `INSERT INTO egress_reservations VALUES ('i1',2,'r2',14)` | **ACCEPT**: reservation time `14` predates its authorizing run time `20`. The matching effect claim at time 14 correctly rejects. The reservation checks never compare `reserved_at` to `authorized_run.started_at`. [DDL:391](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-schema-v2-draft.sql:391), [claim comparison:311](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-schema-v2-draft.sql:311) |
| C8-02 | Current heads: `e1=timeout_unknown`, `e2=delivered`; `INSERT ... closure='unknown_delivery', evidence_json='["e1"]'` | **ACCEPT**, and `closure_consistency_violations=[]`. The intentionally non-exhaustive treatment is a gap: it permits an uncited delivery while rev 6 claims the label derives from the full set. [DDL:605](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-schema-v2-draft.sql:605), [pass 8:674](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:674) |
| C8-03 | Cited timeout `e1`; insert late `e2(delivered)` superseding `e1`; query the view | Exact result was `[('t1','c1')]` and nothing else. But `INSERT ... closure='delivered', recorded_by='reconciler'` then **REJECTED**: `only transport may supersede transport closure`. A reconciler cannot restore schema conformance after late knowledge invalidates a transport closure. [DDL:546](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-schema-v2-draft.sql:546), [view:709](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-schema-v2-draft.sql:709) |
| C8-04 | Close as `refused`, then fold a historical intent with `created_at` before the closure | Intent **REJECTED**: `no new intents on a closed turn`. The same applies to historical reservations, leaving no reconciler path for late intent/reservation knowledge. [DDL:353](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-schema-v2-draft.sql:353), [design fold requirement:248](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:248) |
| C8-05 | `suppressed` with `[]` and no egress; separately, `unresolved_crash []` while an uncited delivered head exists | Both **ACCEPT**; the consistency view remains empty. `suppressed` lacks a nonempty-evidence requirement, while `unresolved_crash` checks only cited rows. [DDL:574](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-schema-v2-draft.sql:574), [DDL:636](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-schema-v2-draft.sql:636) |
| C8-06 | Insert embedded-NUL and multibyte values into `event_identity` and `transport` | Both **ACCEPT**; examples stored as hex `780079` and `C3A9`. Empty values reject, but these columns have only `length(...)>0`. Empty/NUL/multibyte `tenant_id` also accepts. [DDL:141](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-schema-v2-draft.sql:141), [DDL:323](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-schema-v2-draft.sql:323), [pass-8 claim:683](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:683) |
| C8-07 | Literal rev-6 turns fragment: `INSERT ... occurred_at=1e999, admitted_at=1e999`; separately, seal time `20` followed by cognition claim time `12` | Both **ACCEPT**. The turns fragment still declares bare `REAL` columns, and cognition chronology compares against run start but not seal time. [DDL:41](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-schema-v2-draft.sql:41), [DDL:126](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-schema-v2-draft.sql:126), [design:105](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:105) |

## 2. R7-01–R7-10 discharge

| Item | Verdict | Reason |
|---|---|---|
| R7-01 | **DISCHARGED** | A result-less prior reservation now rejects the next reservation through the NULL-proof `COALESCE(...,'missing')` check. |
| R7-02 | **PARTIAL** | Ordinary intent/reservation/result chronology rejects correctly, but C8-01 allows a reservation before its new `authorized_run` began. |
| R7-03 | **DISCHARGED** | Retry under current `r2` accepts; retry using terminal `r1` rejects; current/stale effect-claim checks also behaved correctly. |
| R7-04 | **DISCHARGED** | Both insertion orders for a second constituent on a correction turn reject with `a correction turn hosts exactly one constituent`. |
| R7-05 | **PARTIAL** | Resolved labels are exhaustive, but C8-02 confirms `unknown_delivery` may omit a delivered current head. |
| R7-06 | **PARTIAL** | Closed-turn invalid-row rejection and the exact late-ack view result work, but omitted new heads are invisible and a reconciler cannot replace a transport closure. |
| R7-07 | **PARTIAL** | Mixed `suppressed` evidence and directly cited delivery under `unresolved_crash` reject, but the empty/omitted cases in C8-05 accept. |
| R7-08 | **PARTIAL** | Primary ID carriers rejected all 21 empty/NUL/multibyte probes, but `event_identity`, `transport`, and `tenant_id` remain incomplete. |
| R7-09 | **PARTIAL** | Named non-turn infinities and claim-before-run reject; the literal turns fragment and seal-to-claim chronology remain incomplete. |
| R7-10 | **DISCHARGED** | Under the requested reconstructed domain, invented kinds, outbound reply parents, and non-owner correction parents reject; lawful inbound-parent replies accept. |

## 3. T1–T6 BINDING-READY judgments

The standard requires pre-registered fixtures, exact commands/digests/selectors/configuration/interruption points/clocks/windows, binary kills, exact-set queries, and no post-hoc selection. [Theme-2 round 1:62](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-gate-round1.md:62), [detailed standard:62](/home/rohit/maez/docs/superpowers/specs/2026-08-22-gate-round1-ledger-and-repair.md:62)

| Test | Judgment | Required additions before S1 code |
|---|---|---|
| T1 | **NOT BINDING-READY** | The enumerated matrix is **16 cells**, not 24; replace “best-fit” with named fixture/latch artifacts and literal digests; freeze commands, resolver selector, exact returns, PRAGMAs, clock/cache state, and pre/post file sets. Resolve absent/zero-byte `gestation` versus the structurally-complete gestation requirement. [Protocol:45](/home/rohit/maez/docs/superpowers/witness/theme2-s1-protocol.md:45) |
| T2 | **NOT BINDING-READY** | Freeze each command, starting digest, exact interruption point, synchronization barrier, PID/signal operation, timeout, clock treatment, permitted exact file set, repair bytes, restore artifact, and health-result query. [Protocol:63](/home/rohit/maez/docs/superpowers/witness/theme2-s1-protocol.md:63) |
| T3 | **NOT BINDING-READY** | Freeze every consumer qualname and one exact outcome per consumer—not “typed error or queue”; include writer, span-planner, and heartbeat readers; replace ambiguous `chmod 000` behavior with a deterministic injected failure point; supply literal exact-set SQL, store inventory, outage markers, and positive controls. [Protocol:83](/home/rohit/maez/docs/superpowers/witness/theme2-s1-protocol.md:83) |
| T4 | **NOT BINDING-READY** | Commit the sorted expected census now, with scan roots/exclusions, AST grammar, normalization, parser version, exact command, and digest. Freeze the seeded file bytes/path and add both unexpected-consumer and missing-expected-consumer binary kills. [Protocol:97](/home/rohit/maez/docs/superpowers/witness/theme2-s1-protocol.md:97) |
| T5 | **NOT BINDING-READY** | Freeze the suite selectors, complete flag/environment list, 20-interaction bytes/IDs/times/digest, baseline store artifacts, exact store inventory, comparison commands, deadlines, and changed-byte/sentinel-file binary kills. [Protocol:106](/home/rohit/maez/docs/superpowers/witness/theme2-s1-protocol.md:106) |
| T6 | **NOT BINDING-READY** | Supply literal migration names/digests, table/trigger/index sets, genesis projection bytes, head/tip SQL, fixture digest, and exact mutation SQL. Add missing-trigger, extra-index, and missing/extra-migration-name controls; freeze whether “shipped files” means current migrations or the rev-6 design artifact. [Protocol:115](/home/rohit/maez/docs/superpowers/witness/theme2-s1-protocol.md:115), [DDL status:27](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-schema-v2-draft.sql:27) |

**S1 code may not begin: 0/6 tests are BINDING-READY.**

## 4. DESIGN-LEVEL / BUILD-LEVEL split and S1–S6

| Level | Verdict |
|---|---|
| DESIGN-LEVEL | **HOLD:** authorized-run chronology, full-head closure labeling, reconciler late-knowledge ordering, closed-turn historical folding, carrier discipline, and remaining chronology require revision. |
| BUILD-LEVEL | **UNVERIFIED:** no migrations, production code, reconciler, registry, or repository tests were executed; S1’s protocol is not yet binding-ready. |

| Slice | Verdict | Witness-protocol authoring |
|---|---|---|
| S1 — phase truth | **DESIGN READY; PROTOCOL NOT BINDING-READY** | **MAY CONTINUE AUTHORING.** No S1 code yet. |
| S2 — schema v2 | **HOLD — DESIGN-LEVEL** | **NO.** The current schema consistency findings must be resolved first. |
| S3 — rail + registry | **HOLD — S2 DEPENDENCY** | No full binding protocol yet. |
| S4 — egress truth | **HOLD — DESIGN-LEVEL** | No; C8-01 through C8-05 affect its contract. |
| S5 — universe sweep | **HOLD — DEPENDENCY** | No full binding protocol yet. |
| S6 — posture | **HOLD — DEPENDENCY** | No full binding protocol yet. |

Slices permitted to author a witness protocol now: **S1 only, as a revision/continuation. S2 may not begin.**

## 5. Overall verdict

**OVERALL VERDICT: HOLD**