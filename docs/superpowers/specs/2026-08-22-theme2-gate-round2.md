# Gate round 2 on Theme 2 design (36e63cd) — HOLD

Codex, `--effort xhigh`, static + in-memory-SQLite exercise of the
proposed DDL. Verdict: **HOLD.** B11 DISCHARGED (witness discipline +
airlocked born fixture accepted); B2/B4/B5/B6/B8/B9/B10 PARTIAL;
B1/B3/B7 NOT DISCHARGED; **16 new defects ND1–ND16**, several proven
by executing the pass-2 schema (two simultaneous active runs, three
"current" closure heads, cross-turn supersession, reply to a
nonexistent turn all ACCEPTED by the DDL as written).

The shape of the findings: pass 2 stated the right invariants and
left them as prose. Round 2's demand is that the schema and the
transaction boundaries enforce them. Pass 3 folds all sixteen.

Audit-process note from the verdict, preserved: one delegated census
surfaced a single tracked import line under memory/memory_manager.py;
no live datastore was opened or written.

---

Full gate text follows.

## 1. Per-blocker discharge table

B1: NOT DISCHARGED -- The inventory names many known doors but leaves public scope undecided, uses wildcard outbound entries, and gives no closed AST/runtime grammar capable of detecting dynamically activated routes or dispatch ([pass 2 §2:71–101](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:71); [round 1 B1:91](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-gate-round1.md:91)).

B2: PARTIAL -- Separate event, turn, and run tables resolve the identity conflation, but no membership seal or mixed known/new constituent rule handles a Telegram constituent arriving after admission ([pass 2 §3.1:103–133](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:103); [round 1 B2:93](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-gate-round1.md:93)).

B3: NOT DISCHARGED -- Runs and four dispositions exist, but lease expiry is not a fencing boundary, admission/run creation is not required to be atomic, and stale recovery can overlap or repeat a still-live run’s cognition, action, or send ([pass 2 §3.2:135–159](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:135); [round 1 B3:95](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-gate-round1.md:95); [birth B3:62–64](/home/rohit/maez/docs/superpowers/specs/2026-08-22-birth-blocker-ledger.md:62)).

B4: PARTIAL -- Provider and admission times are now preserved separately, but earliest-constituent ordering is incompatible with late immutable membership and raw provider time is promoted to ordering authority without skew, future-time, or tie policy ([pass 2 §3.1:128–133](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:128); [round 1 B4:97](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-gate-round1.md:97); [birth A4:55–56](/home/rohit/maez/docs/superpowers/specs/2026-08-22-birth-blocker-ledger.md:55)).

B5: PARTIAL -- Per-attempt rows and append-only corrections fix representational cardinality, but the proposed DDL does not enforce one closure head, same-turn supersession, evidence membership, or transport-versus-transport precedence ([pass 2 §4:167–230](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:167); [round 1 B5:99](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-gate-round1.md:99)).

B6: PARTIAL -- Zero-table and read-error cells are corrected and the latch gains useful fields, but partially initialized/meta-missing states can still become gestation, canonical-path binding is ambiguous, and latch publication is not atomic ([pass 2 §5:232–260](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:232); [round 1 B6:101](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-gate-round1.md:101); [birth A6:57–61](/home/rohit/maez/docs/superpowers/specs/2026-08-22-birth-blocker-ledger.md:57)).

B7: NOT DISCHARGED -- A one-time first-observation head catches only rewinds before that checkpoint, not later stale restores, and the claimed phase-consumer census still omits direct-edit/defaulting and direct-meta consumers ([pass 2 §5:248–275](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:248); [round 1 B7:103](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-gate-round1.md:103)).

B8: PARTIAL -- The normative owner/auth → S4 → admission order now matches Decision 30, but the hash-only journal cannot represent and later reconstruct both the failed inbound life and its refusal/S4/transport outcome ([pass 2 I1:25–34](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:25); [pass 2 §6:277–302](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:277); [round 1 B8:105](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-gate-round1.md:105)).

B9: PARTIAL -- Stage-before-hash is coherent for newly created ordinary, birth, and rehearsal rows, but birth identity remains outside the chain, the hash domain is unversioned, `--rebaseline-empty` is ineffective for genesis-seeded ledgers, and initialization can accept a non-tip head ([pass 2 §7:312–332](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:312); [round 1 B9:107](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-gate-round1.md:107)).

B10: PARTIAL -- The design supplies N=1000 and target latency/refusal values, but “normal load,” concurrency schedule, exact measurement, positive control, and binding kill rule remain unfrozen and no measurement exists yet ([pass 2 §6:304–310](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:304); [round 1 B10:109](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-gate-round1.md:109)).

B11: DISCHARGED -- Round 1 explicitly prescribed protocols committed before each slice’s code, and pass 2 adopts that exact timing plus a coherent airlocked production-writer born fixture; protocols need not predate this design gate, but no slice may begin code until its protocol is committed ([round 1 disposition:60–65](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-gate-round1.md:60); [pass 2 §8:334–364](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:334); [writer rehearsal/birth rules:279–293](/home/rohit/maez/core/ledger/writer.py:279)).

## 2. NEW-DEFECT LIST

- **ND1 — The registry is not a closed executable universe.** [Pass 2 §2:71–95](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:71) says entries name an admission point and closure owner, but the displayed registry contains neither column and its outbound entry is a wildcard. Current `/chat` and fast-lane routes can become live merely by changing a runtime parked-endpoint table ([web_interface.py:10359–10434](/home/rohit/maez/skills/web_interface.py:10359)), while Telegram transport dispatch uses `getattr(target, method_name)` ([telegram_egress.py:383–417](/home/rohit/maez/core/egress/telegram_egress.py:383)). An AST matcher over registration nodes can therefore miss a newly live door or send and silently omit that interaction. Flask blueprints are absent at this HEAD; their future bypassability is **UNVERIFIED**, but the design neither bans nor defines matching for them.

- **ND2 — The egress universe excludes owner-visible mutations.** The registry’s sole outbound wildcard and the closed `egress_kind` enum ([design:94](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:94); [design:174–184](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:174)) omit edits and reactions even though Telegram performs them ([telegram_adapter.py:1448](/home/rohit/maez/skills/surface/telegram_adapter.py:1448); [telegram_adapter.py:3677](/home/rohit/maez/skills/surface/telegram_adapter.py:3677)). An edit can replace the bytes the owner sees while the ledger continues to assert the superseded text as delivered.

- **ND3 — Mixed or late constituents have no lawful state transition.** Pass 2 says any constituent resolves the existing turn ([design:120–126](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:120)), but current aggregation retains one scalar identity/time while mutating the first event’s content ([telegram_adapter.py:2979–2993](/home/rohit/maez/skills/surface/telegram_adapter.py:2979); [platform_base.py:751–786](/home/rohit/maez/skills/surface/platform_base.py:751)). For an already-admitted A followed by fresh B, dropping A+B omits B, creating A+B anew duplicates A, and attaching B after cognition falsely claims B was consumed; the proposed schema permits attaching B after the run is completed.

- **ND4 — Admission identity is not transactionally or semantically bound.** The independent `admission_events` and `runs` tables ([design:109–147](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:109)) lack a required atomic event+turn+run transaction, tenant-equality FK, membership seal, and identity/payload-conflict disposition. An in-memory execution of the shown shape accepted an owner event pointing to a public turn and a late event on a completed turn; a reused identity with different content would be treated as replay, silently omitting the new content.

- **ND5 — Leases are not fences.** `UNIQUE(turn_id, attempt)` permits multiple active attempts, and `replay_stale` starts another run solely because wall-clock lease time expired ([design:137–159](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:137)). The in-memory schema accepted two simultaneous active runs; no epoch/CAS must be revalidated by cognition, action, or transport gates, so a paused first run can resume alongside its takeover and duplicate actions or sends. Separately, `replay_completed` explicitly permits physical re-delivery despite I3’s promise that replay cannot cause a second send ([design:39–41](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:39); [design:153–156](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:153)).

- **ND6 — Turn ordering promotes untrusted clock domains into biography authority.** `turns.occurred_at` is immutable earliest-constituent time and readers order directly by it ([design:128–131](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:128)). A late constituent with an earlier provider timestamp cannot repair an append-only turn, while provider/local skew can produce `occurred_at > admitted_at` and place a newly admitted turn arbitrarily in the future; equal timestamps also have no deterministic tie-break. Raw occurrence truth needs preservation, but it is not by itself a safe cross-surface ordering key.

- **ND7 — The supersession lattice is unenforced.** `turn_closures.supersedes` is only a nullable self-FK ([design:187–212](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:187)). The in-memory witness accepted two initial closures, two successors to one predecessor, cross-turn supersession, self-supersession, and three simultaneous “current” heads; append-only triggers preserve rather than prevent those invalid inserts. The precedence prose also defines transport-over-reconciler but not failed transport versus successful retry or two conflicting transport-evidenced closures, so a life can have zero or multiple current outcomes.

- **ND8 — Closure evidence is not relationally bound.** `evidence_hash` is nullable and has no immutable attempt-membership carrier, canonical byte domain, exact-set rule, or run/reply binding ([design:187–205](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:187)). Attempts may be appended after the closure, so a verifier cannot reconstruct which historical subset was consulted; a caller can label a closure `recorded_by='transport'` without joined transport evidence. Reader migration therefore cannot prove which reply bytes were actually received.

- **ND9 — One immutable result row cannot represent retry chronology or late acknowledgment.** `egress_attempts` contains `attempted_at`, `part_ordinal`, and a terminal `result`, but no retry ordinal or result-observed timestamp ([design:173–185](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:173)). Telegram performs multiple physical attempts per part ([telegram_adapter.py:1309](/home/rohit/maez/skills/surface/telegram_adapter.py:1309)); a late success for the same `timeout_unknown` attempt cannot update an append-only row, while inserting another row falsely records a second physical send. Delivery truth can consequently be misdated or miscounted.

- **ND10 — Transport and outbound producers lack a durable pre-effect claim.** Because an attempt row requires a known terminal result, the design has no durable state before bytes leave; a crash after transport handoff but before the insert/journal can omit a delivered utterance and permit stale recovery to resend it ([design I4:42–45](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:42); [design failure posture:287–288](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:287)). `admit_outbound` also specifies no stable producer identity ([design:161–165](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:161)); the current follow-up path sends before marking its durable queue item delivered ([maez_daemon.py:11783–11787](/home/rohit/maez/daemon/maez_daemon.py:11783)), so a crash can admit and send the same life-event twice.

- **ND11 — “No reply without a parent” checks only NULL, not parent existence or identity.** Pass 2 specifies a trigger that rejects only a NULL `parent_turn_id` ([design:327–329](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:327)), while the existing column has no FK ([0001_init.sql:29–30](/home/rohit/maez/core/ledger/migrations/0001_init.sql:29)). The in-memory witness accepted a model reply pointing to a nonexistent turn; combined with the undefined closure-to-reply join, this can orphan a reply or attach delivery truth to the wrong life.

- **ND12 — The latch is not a durable high-water mark.** The `O_EXCL` latch records only the head at first observation and is never advanced ([design:248–265](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:248)). A restore to any later point that still contains that first observed head passes while silently dropping every subsequently lived row; a hash alone also cannot express “shorter than” without a verified position/ancestry rule. A rewind plus unreadable ledger correctly yields `unknown` under the last phase-table row, but a readable stale prefix remains silently acceptable.

- **ND13 — The phase table and consumer census still admit gestation misdating.** “Initialized, meta key absent” returns gestation without requiring complete schema and chain validation ([design:236–243](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:236)), so a partial or damaged ledger can be mistaken for legitimate gestation before a latch exists. The claimed census ([design:267–275](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:267)) names `AuditLog.record` but misses direct-edit methods that independently default to gestation ([audit_log.py:405–412](/home/rohit/maez/core/cognition/audit_log.py:405); [audit_log.py:480–489](/home/rohit/maez/core/cognition/audit_log.py:480)), and `PrivateThoughts` accepts caller-supplied phase without gate revalidation ([private_thoughts.py:571–602](/home/rohit/maez/core/infra/private_thoughts.py:571)).

- **ND14 — Latch name creation is atomic, but latch publication is not.** `O_CREAT|O_EXCL` publishes the pathname before its contents are completely written and fsynced ([design:248–259](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:248)). A crash or race loser can observe an empty/torn latch, which the design then permanently classifies as corrupt and unrecreatable; post-birth turns are refused into the already-insufficient journal, creating an avoidable omission window.

- **ND15 — The gap journal cannot reconstruct or atomically fold biography.** Its hash-only entry lacks raw content, constituent set, turn/run/attempt identity, transport result, part/retry identity, sent-byte hash, lifecycle phase, or ledger/birth binding ([design:290–302](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:290)). One row cannot represent both an admission-failed inbound event and its refusal/S4 answer, or the multiple TTS/text/media attempts of an egress failure; segment-level marking also has a crash window where mark-before-fold omits and fold-before-mark duplicates. Importing such unsealed JSONL later makes the strong ledger chain attest only to an unverified, possibly misdated tombstone.

- **ND16 — Stage hashing still does not chain-bind birth, and migration rebasing is not executable as specified.** `birth_anchor` is a transient argument while mutable `meta.birth_event_turn_id` selects the anchor separately ([writer.py:285–293](/home/rohit/maez/core/ledger/writer.py:285); [writer.py:513–524](/home/rohit/maez/core/ledger/writer.py:513)), so changing that pointer does not break the chain. The writer hashes a manually selected key set while the verifier hashes `SELECT *` minus a fixed exclusion tuple ([writer.py:362–393](/home/rohit/maez/core/ledger/writer.py:362); [chain.py:69–88](/home/rohit/maez/core/ledger/chain.py:69); [verify_ledger_chain.py:77](/home/rohit/maez/scripts/verify_ledger_chain.py:77)), requiring a versioned hash domain or hard fresh-v2 cutover. Finally, every migrated database is seeded with genesis ([migrate.py:161–178](/home/rohit/maez/core/ledger/migrate.py:161)), so pass 2’s “zero turns” rebaseline escape is unavailable to an initialized empty-life ledger and digest replacement alone cannot enact amended `CREATE TABLE IF NOT EXISTS` DDL.

## 3. Per-slice verdict table

S1: BLOCKED -- ND12, ND13, ND14, ND16.

S2: BLOCKED -- ND3, ND4, ND6, ND7, ND8, ND9, ND11, ND16.

S3: BLOCKED -- ND1, ND3, ND4, ND5, ND10.

S4: BLOCKED -- ND2, ND5, ND6, ND7, ND8, ND9, ND10, ND11.

S5: BLOCKED -- ND1, ND2, ND3, ND4, ND10.

S6: BLOCKED -- B10, ND5, ND7, ND10, ND15.

## 4. Overall verdict

GATE HOLD -- Pass 2 still permits omitted, duplicated, and misordered interactions through unsealed constituent membership, unfenced execution, unenforced closure topology, incomplete latch/journal truth, and incoherent chain/migration mechanics; audit-process note: one delegated broad census unintentionally surfaced a single tracked import line under `memory/memory_manager.py`, but no live datastore was opened or written.