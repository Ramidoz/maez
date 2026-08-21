# Gate round 3 on Theme 2 design (5c8aa13) — HOLD, converging

Codex, `--effort xhigh`, with in-memory transcription of every
mechanism concrete enough to transcribe. **DISCHARGED: ND6, ND14, B4**
(chain-position ordering authority; torn-proof latch publication;
temporal truth). Confirmed working when transcribed faithfully: seal
serialization under BEGIN IMMEDIATE, one-active-run partial index,
dense closure ordinals, birth-anchor uniqueness. Remaining findings
F1–F10 share one root, stated in the verdict: *"pass 3 is not yet
transcribable into a schema/trigger/transaction system that enforces
its own invariants."*

Disposition: pass 4 ships the **literal DDL** —
`2026-08-22-theme2-schema-v2-draft.sql` — so the gate executes exactly
what will be built (the spine's schema-v7.sql precedent), plus design
amendments for the non-SQL findings: per-commit latch advance (F3),
journal taint stamps + entry hash chain (F4, F5), recreate-empty
exclusivity (F6), domain-owned v2 canonicalization projection (F7),
and the closed doorway inventory (ND1/B1).

---

Full gate text follows.

## 1. ND1–ND16 discharge table

Review pinned to `5c8aa136`; all SQL results below came from fresh, standalone `sqlite3.connect(":memory:")` exercises.

| Finding | Verdict | Reason and anchor |
|---|---|---|
| ND1 | PARTIAL | The typed, wildcard-free registry and egress chokepoint improve closure, but pass 3 supplies neither the actual exhaustive entries nor an executable primitive/reachability grammar, and its AST/startup checks are outside its own schema/trigger/transaction rule ([design §2](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:55)). |
| ND2 | PARTIAL | `edit` and `reaction` are now enumerated, but the literal result DDL accepted self-supersession and cross-intent supersession, so an edit can still claim to supersede unrelated delivery evidence ([design `egress_results`](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:164)). |
| ND3 | PARTIAL | A faithful seal trigger rejected a late `INSERT`, but the specified insert-only guard allowed an existing constituent to be updated onto the sealed turn, while late-as-new-turn overloads `parent_turn_id` without a relationship type ([design §3.1](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:99)). |
| ND4 | UNDERSPECIFIED | The transcribed composite tenant FK correctly rejected owner-event→public-turn, but “same identity + different payload” cannot be implemented from text that simultaneously calls the constituent identity the deduplicating PK without defining a versioned key or correction table ([design identity conflict rule](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:116)). |
| ND5 | PARTIAL | The exact `one_active_run` index rejected a second active run, but the available DDL accepted a regressed epoch and an intent for a superseded run; the epoch re-read has no transcribable conditional SQL, transaction mode, or durable action claim ([design §3.2](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:121)). |
| ND6 | DISCHARGED | Pass 3 explicitly makes `chain_position` the ordering authority and demotes provider/admission timestamps to preserved testimony, resolving the clock-domain authority contradiction ([design I10](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:48)). |
| ND7 | UNDERSPECIFIED | A faithful dense-ordinal transcription rejected double-initial, fork, gap, cross-turn, self-supersession, and reconciler-over-transport cases, but the document provides no actual trigger and leaves “new evidence rows” undefined and entangled with evidence insertion order ([design closure topology](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:181)). |
| ND8 | NOT DISCHARGED | With immediate FKs, parent-first closure insertion failed the evidence trigger and child-first evidence failed the FK; deferred child-first insertion worked but then accepted post-closure evidence expansion and cross-turn evidence ([design `closure_evidence`](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:192)). |
| ND9 | PARTIAL | Multiple observations, retry ordinals, and observed times are representable, but the literal DDL accepted self/cross-intent supersession and negative retry ordinals and defines no enforceable current-observation chain ([design `egress_results`](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:164)). |
| ND10 | PARTIAL | Durable intents and producer identities repair the direction, but duplicate intent shapes and stale-run intents remain schema-legal, and “must not blindly resend” is not a concrete recovery transaction or disposition ([design pre-effect claim](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:175)). |
| ND11 | PARTIAL | The FK and NULL trigger rejected nonexistent and NULL parents in memory, but a reply referencing itself and an owner reply referencing a public parent were both accepted ([design parent FK](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:281)). |
| ND12 | PARTIAL | The advancing latch catches prefixes older than its latest observation, but boot/reconciler cadence leaves every tail appended after that observation silently rewindable despite the claim that any stale prefix is caught ([design advancing latch](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:210)). |
| ND13 | PARTIAL | Full schema/genesis/chain validation and the three newly named consumers are improvements, but “complete expected table set” and “pass 2’s list plus” are not a closed executable phase contract in this document ([design phase census](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:202)). |
| ND14 | DISCHARGED | For the narrow torn-publication defect, same-directory temp write, file fsync, atomic rename, and directory fsync form a complete publication algorithm; multi-writer segment naming remains a fresh latch defect ([design publication](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:221)). |
| ND15 | PARTIAL | Raw reconstruction fields and the in-ledger fold PK close the earlier information and mark-order windows, but journal taint/privacy provenance and pre-fold content integrity remain absent ([design journal](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:242)). |
| ND16 | NOT DISCHARGED | Birth uniqueness is feasible—the transcribed trigger rejected a second `1`—but accepted non-boolean anchor value `2`, while v2 canonicalization and recreate-empty remain mechanically unsafe ([design §7](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:267)). |

## 2. Residual round-1 blocker table

| Blocker | Verdict | Reason and anchor |
|---|---|---|
| B1 | PARTIAL | Public scope is decided and wildcard entries are removed, but neither the registry inventory nor the AST/runtime matching grammar is actually closed in the document ([design §2](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:55)). |
| B2 | PARTIAL | Event, turn, and run identities are separated and membership sealing is introduced, but per-door identity rules, correction-key shape, and late-turn relationship semantics remain undefined ([design §3](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:97)). |
| B3 | PARTIAL | Active-run uniqueness and epochs create the right processing claim, but action/send fencing is not a transcribable atomic pre-effect transaction ([design epoch gates](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:127)). |
| B4 | DISCHARGED | Provider occurrence time is preserved while chain position becomes the deterministic cross-surface authority ([design I10](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:48)). |
| B5 | NOT DISCHARGED | Two-phase egress repairs cardinality, but closure evidence cannot be inserted through an ordinary immediate-FK path and remains mutable/cross-turn under the deferred path ([design §4](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:149)). |
| B6 | PARTIAL | Structural gestation validation and torn-proof latch publication improve phase proof, but the latch is still not bound to a canonical ledger identity/path and its complete structural contract is unspecified ([design §5](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:202)). |
| B7 | PARTIAL | The latch now advances and more consumers are named, but unobserved tail rewinds remain silent and the census is referenced rather than fully enumerated ([design latch/census](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:210)). |
| B8 | PARTIAL | Owner/auth→S4→admission now matches the authority contract and the journal is reconstructive, but missing taint/privacy and content-integrity fields prevent truthful fold-in ([design §6](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:236)). |
| B9 | NOT DISCHARGED | Domain versioning and recreate-empty are the right direction, but current caller-dependent canonicalization cannot hash the full stored v2 genesis row consistently, and recreation lacks exclusive ownership ([design §7](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:267)). |
| B10 | NOT DISCHARGED | Pass 3 only promises that S6 will later freeze the schedule, measurement, control, and kill rule; it supplies none of their actual values and no measurement ([design contention protocol](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:259)). |

## 3. New-defect list

- **F1 — Epoch re-read is not yet an atomic effect claim.** Anchor: [design epoch gates](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:127), [current `BEGIN IMMEDIATE` pattern](/home/rohit/maez/core/ledger/writer.py:400). **Severity: blocking.** A deferred transaction can read an old snapshot and perform an external action before a later database write exposes staleness; an extra epoch column is not strictly necessary if `run_id` binds an immutable epoch, but a committed conditional run/epoch claim before the physical effect is necessary, and the action path has none specified—actual daemon/web fencing is **UNVERIFIED**.

- **F2 — Seal safety is feasible, but membership and parent semantics are incomplete.** Anchor: [design sealed membership](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:108). **Severity: blocking.** The shared-memory `BEGIN IMMEDIATE` probe serialized seal/admission correctly—admission-first became a constituent and seal-first rejected it—but the insert-only trigger admitted an UPDATE onto a sealed turn, and readers cannot distinguish late-constituent parenting from reply/causal parenting; actual cross-process implementation remains **UNVERIFIED**.

- **F3 — Advancing latch has both a tail gap and a possible latch-ahead state.** Anchor: [design latch cadence](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:210), [current `synchronous=NORMAL`](/home/rohit/maez/core/ledger/writer.py:226). **Severity: blocking.** A crash after lived appends but before the next boot/reconciler observation leaves those rows outside the high-water mark; WAL checkpoint or `VACUUM` alone should not change logical position/hash and therefore should not report rewind, but implementation is **UNVERIFIED**, while a power loss can recover the database behind a separately fsynced latch.

- **F4 — The reconstruction journal cannot preserve provenance stamps.** Anchor: [journal field list](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:242), [mandatory writer stamps](/home/rohit/maez/core/ledger/writer.py:241), [`validate_turn_stamp`](/home/rohit/maez/core/ledger/taint_stamping.py:144). **Severity: blocking.** A fold must either refuse, invent labels/privacy, or use schema defaults that contradict the production writer; v2 then chain-hashes the fold-time invention, not the failure-time provenance.

- **F5 — Journal content is not integrity-bound before fold.** Anchor: [journal fold transaction](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:249), [v2 hash domain](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:269). **Severity: blocking.** Full raw JSONL can be altered before reconciliation, after which the ledger chain faithfully attests only to the altered bytes; segment sequence numbers do not supply an entry hash/segment chain or bind the original stamps.

- **F6 — `--recreate-empty` permits open-handle split brain.** Anchor: [design recreate-empty](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:284). **Severity: blocking.** After the command checks “genesis only/no anchor,” another process can append or retain an open old inode while the pathname is replaced, leaving daemon and web writing different ledgers; exclusive quiescence/locking plus WAL/SHM ownership is required.

- **F7 — Shared canonicalization is feasible, but not as specified.** Anchor: [design v2 rule](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:269), [`canonical_row_bytes`](/home/rohit/maez/core/ledger/chain.py:80), [writer row/hash order](/home/rohit/maez/core/ledger/writer.py:362), [genesis dictionary](/home/rohit/maez/core/ledger/migrate.py:46), [verifier `SELECT *`](/home/rohit/maez/scripts/verify_ledger_chain.py:77). **Severity: blocking.** A naïve v2 helper receives a writer/genesis dictionary missing stored default columns while the verifier receives every column; v2 needs an explicit domain-owned projection/default map, lifecycle resolved before hashing, and a complete v2 genesis row.

- **F8 — Closure evidence is neither frozen nor lineage-compatible.** Anchor: [design evidence relation](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:192). **Severity: blocking.** Immediate FKs provide no legal insertion order for the stated trigger, while deferred child-first insertion accepted later evidence additions and a result belonging to another turn.

- **F9 — Result supersession is unconstrained.** Anchor: [literal egress DDL](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:153). **Severity: blocking.** The exercised DDL accepted a result superseding itself, an edit superseding a result from another intent, and duplicate intent shapes, so reader truth can be redirected or duplicated.

- **F10 — Parent and anchor domains remain wider than their claimed meanings.** Anchor: [parent/anchor mechanics](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:275). **Severity: blocking.** The faithful schema accepted self-parent replies and cross-tenant parents, while the uniqueness trigger accepted `is_birth_anchor=2`; SQLite needs same-tenant/prior-row relationship constraints and `CHECK (is_birth_anchor IN (0,1))`.

## 4. Per-slice verdicts

- **S1 — NOT DISCHARGED:** advancing-latch cadence leaves an unlatched tail, canonical-ledger binding is absent, and the phase census/expected-schema set is not closed ([design S1](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:307)).
- **S2 — NOT DISCHARGED:** evidence insertion/freeze, epoch monotonicity, parent identity, birth domain, v2 genesis canonicalization, and recreate-empty exclusivity remain blocking ([design S2](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:309)).
- **S3 — NOT DISCHARGED:** the registry is not an executable closed universe and the cross-process effect fence is not a concrete transaction ([design S3](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:313)).
- **S4 — NOT DISCHARGED:** literal result DDL permits invalid supersession and duplicate intent shapes, while stale-run admission depends on an unspecified CAS ([design S4](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:315)).
- **S5 — NOT DISCHARGED:** producer identity is required in principle, but the complete door inventory and concrete identity rule for every producer are not present ([design S5](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:317)).
- **S6 — NOT DISCHARGED:** journal stamps/integrity, fold evidence binding, reconciler fencing, and the frozen contention protocol are unresolved ([design S6](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:319)).

## 5. Overall verdict

**HOLD — pass 3 is not yet transcribable into a schema/trigger/transaction system that enforces its own invariants.**

The decisive blockers are closure-evidence insertion and freeze semantics, non-atomic external-effect fencing, the unlatched rewind tail, provenance-less journal fold-in, unsafe recreate-empty concurrency, and the incomplete v2/genesis canonicalization contract.

