# Gate round 1 on Theme 2 design (789e995) — BLOCKED, all six slices

Codex, `--effort xhigh`, static read-only at `789e995`. Verdict:
**every slice BLOCKED, 0/8 falsifiers binary-ready, 11 blockers
(B1–B9, B11 block birth; B10 should-fix).** Full verdict text follows at the end of this file; the top half
records the blockers and my independent verification of the decisive
claims before accepting them (standing rule: verify before you
encode).

## Verified by me at HEAD before accepting

- **B8 canon conflict — CONFIRMED, stronger than Codex stated.**
  `docs/governance/BETA_ARCHITECTURE_DECISIONS.md` (S4 front-door
  guard) requires `guard_owner_text` *"before any owner-text side
  effect: tool/interceptors, traces, ledgers, recall…"*. Design pass
  1's I1 ("admission precedes every interceptor") contradicts canon
  directly. Resolution for pass 2: ordering becomes authenticate → S4
  guard → admit → interceptors. The clinical path admits and closes
  its turn like every other path; the pass-1 "clinical exception"
  dissolves — S4's single-answer authority ships regardless of ledger
  health, and a failed admission on an S4-matched turn goes to the gap
  journal.
- **B9 migration skip — CONFIRMED.** `core/ledger/migrate.py:121`
  skips by filename with no digest check; my pass-1 D4 assumed a
  refusal mechanism that must in fact be built.
- **B11 rehearsal birth — CONFIRMED verbatim.**
  `core/ledger/writer.py:289` — "rehearsal writer refuses
  birth_anchor". A "born rehearsal ledger" is impossible with current
  machinery; the witness harness needs a sanctioned fixture path.
- **B6 zero-byte contradiction — confirmed by reasoning.** The 0-byte
  ledger *exists*, so pass 1's "file absent → gestation" branch never
  fires; the meta query errors and pass 1's own rule turns legitimate
  gestation into `unknown`. Pass 2 must distinguish
  *uninitialized-empty* (provable gestation pre-latch, via
  `sqlite_master`) from *initialized-but-unreadable* (`unknown`).

Accepted on Codex's anchors without re-execution (consistent with my
own earlier reads): B1 (doorway universe not closed: GUI, public
Telegram/web, fast lane, Telegram commands/callbacks, cockpit
decisions, outbound-first producers), B2 (raw event / logical turn /
run identities conflated; aggregation discards constituent ids; voice
and web lack identity; edits undefined), B3 (`was_replay` claims
nothing about execution — dedup without an execution claim), B4
(**occurrence time dropped** — writer stamps `time.time()` at
`writer.py:354` while `MessageEvent` carries provider time; the ledger
misdates by construction, which is Theme 2's title), B5 (outcome
cardinality wrong: one mutable row cannot represent multi-egress,
multipart, and reconciler races; append-only closure with precedence
needed), B7 (restore rewind with same birth id evades the latch), B10
(lock contention unmeasured).

## What pass 1 got right (per the gate, by omission from the blockers)

Admission-at-doorway as the structural fix, in-ledger idempotency over
the side store, transport-owned delivery truth, tri-state phase with
consumer refusal, pre-birth schema freedom, flag-dormant slices. The
blockers are about closure (registries, identity levels, temporal
truth, precedence, fixtures), not about the direction.

## Disposition

Design pass 2 (same file, revised) folds B1–B11. The eight falsifiers
become per-slice **witness protocols committed before the slice's
code** — pre-registered fixtures, exact commands, digests — meeting
the gate-round-1 standard from the adjacent turn-ledger review.

---

Full gate text follows.

## 1. Attack-section verdicts

1. **UNIVERSALITY — BLOCKED.** “Doorway” is not a closed production registry. Current inbound doors include Telegram V2 text, commands, location, media, and callbacks ([telegram_adapter.py:907-925](/home/rohit/maez/skills/surface/telegram_adapter.py:907)); `/receipts`, proposal/dream commands, and callbacks complete before normal message dispatch ([telegram_adapter.py:2742](/home/rohit/maez/skills/surface/telegram_adapter.py:2742), [telegram_adapter.py:1966](/home/rohit/maez/skills/surface/telegram_adapter.py:1966)). The legacy kill-switch exposes a second command/message ingress ([telegram_voice.py:5369](/home/rohit/maez/skills/telegram_voice.py:5369)); owner/public web share `/chat` but only owner currently reaches the ledger seam ([web_interface.py:6760](/home/rohit/maez/skills/web_interface.py:6760), [web_interface.py:6817](/home/rohit/maez/skills/web_interface.py:6817)); public Telegram ([telegram_public.py:371](/home/rohit/maez/skills/telegram_public.py:371)), fast lane ([web_interface.py:10127](/home/rohit/maez/skills/web_interface.py:10127)), GUI ([gui.py:627](/home/rohit/maez/gui.py:627)), CLI ([maez_chat.py:793](/home/rohit/maez/cli/maez_chat.py:793)), cockpit message/decision routes, and local voice are additional doors. Peer production is **ABSENT/reserved** in the inspected paths and Track A explicitly excludes inter-Maez communication ([TRACK_A.md:206](/home/rohit/maez/docs/TRACK_A.md:206)). Most importantly, the only proposed root is `admit_inbound` ([design:124-139](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:124)), so proactive opinions and follow-up reports have no parent or outcome ([maez_daemon.py:5349](/home/rohit/maez/daemon/maez_daemon.py:5349), [maez_daemon.py:11743](/home/rohit/maez/daemon/maez_daemon.py:11743)). `turn_outcomes` therefore does not cover outbound-first interaction.

2. **IDENTITY STABILITY — BLOCKED.** V2 has `update_id` before batching ([telegram_adapter.py:2726](/home/rohit/maez/skills/surface/telegram_adapter.py:2726)) and stores it on `MessageEvent` ([telegram_adapter.py:3657](/home/rohit/maez/skills/surface/telegram_adapter.py:3657). The legacy handler receives the full `Update`, but passes only `user_text` into its synthesis path ([telegram_voice.py:2949](/home/rohit/maez/skills/telegram_voice.py:2949), [telegram_voice.py:3568](/home/rohit/maez/skills/telegram_voice.py:3568)). Aggregation retains the first event object while appending later text/media, losing constituent IDs and times ([telegram_adapter.py:2979](/home/rohit/maez/skills/surface/telegram_adapter.py:2979), [telegram_adapter.py:3154](/home/rohit/maez/skills/surface/telegram_adapter.py:3154), [telegram_adapter.py:3379](/home/rohit/maez/skills/surface/telegram_adapter.py:3379)); the repository already labels that choice `UNVERIFIED` ([conversation_turn_seq.py:22](/home/rohit/maez/core/brain/conversation_turn_seq.py:22)). Thus `tg:{chat_id}:{update_id}` can identify either A or A+B depending on timing. Edited messages do not enter these handlers because they require `update.message` ([telegram_adapter.py:2726](/home/rohit/maez/skills/surface/telegram_adapter.py:2726)); no correction/suppression semantics are defined. Local voice has no segment identity at all—the callback carries only transcript text ([wake_word.py:578](/home/rohit/maez/skills/wake_word.py:578), [maez_daemon.py:12092](/home/rohit/maez/daemon/maez_daemon.py:12092)). The official web client also sends no idempotency header ([web_interface.py:9894](/home/rohit/maez/skills/web_interface.py:9894)). B3 requires distinct admission and run/turn identity ([census:250-258](/home/rohit/maez/docs/superpowers/specs/2026-08-22-codex-prebirth-census.md:250)); the design supplies only one conflated key.

3. **EXACTLY-ONE OUTCOME — BLOCKED.** The primary key proves first-writer-wins, not truth. `was_replay` has no required disposition stopping a second cognition/send ([design:129-139](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:129)); current idempotent sequence assignment returns the same ordinal but callers continue processing ([conversation_turn_seq.py:98](/home/rohit/maez/core/brain/conversation_turn_seq.py:98), [maez_adapter.py:817](/home/rohit/maez/skills/surface/maez_adapter.py:817)). The reconciler may classify an active, outcome-less turn as `unresolved_crash` because no lease, run identity, minimum age, or quiescence requirement exists ([design:242-244](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:242)); the later real `delivered` result then loses the PK race. A journaled known delivery and generic crash reconciliation are competing writers with no precedence. One interaction can also emit progress/intermediate messages, TTS, final text, and media ([maez_adapter.py:659](/home/rohit/maez/skills/surface/maez_adapter.py:659), [platform_base.py:1946](/home/rohit/maez/skills/surface/platform_base.py:1946)), while Telegram may partially deliver a multipart send ([telegram_adapter.py:1277](/home/rohit/maez/skills/surface/telegram_adapter.py:1277)). One outcome row cannot represent those distinct egress truths. Finally, the proposed outcome row is mutable because current append-only triggers protect only `turns`, `claims`, and `claim_judgements` ([0002_triggers.sql:7](/home/rohit/maez/core/ledger/migrations/0002_triggers.sql:7)), yet the PK would prevent append-only correction of provisional `unknown_delivery` or a false `unresolved_crash`.

4. **PHASE TRI-STATE — BLOCKED.** Section 4 contradicts the admitted pre-birth state: the design says the canonical ledger is zero-byte ([design:10](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:10)), but makes every query error `unknown` ([design:250-261](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:250)); querying `meta` in a zero-byte database therefore blocks legitimate gestation. Current code confirms why tri-state is needed—missing, query failure, and corruption all return `None`, then become gestation ([birth_phase.py:40](/home/rohit/maez/core/memory/birth_phase.py:40), [birth_phase.py:63](/home/rohit/maez/core/memory/birth_phase.py:63)). The proposed fixed latch is not bound to the resolved ledger path, although `MAEZ_LEDGER_DB_PATH` is resolved per call ([birth_phase.py:25](/home/rohit/maez/core/memory/birth_phase.py:25)); a rehearsal or sandbox ledger could poison the canonical latch. “Written once, fsync’d” ([design:262](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:262)) does not define atomic no-replace creation, race-loser validation, directory fsync, corruption handling, or equality between latched and current birth IDs. Restore copies snapshot files independently into place ([restore.py:151](/home/rohit/maez/scripts/backup/restore.py:151)); an older post-birth ledger with the same birth ID remains falsely acceptable, while a pre-birth rewind leaves ledger/latch divergence. Current `LedgerWriter` also derives stage directly from mutable `meta` after hashing ([writer.py:443](/home/rohit/maez/core/ledger/writer.py:443)), so the named consumer list is incomplete.

5. **FAILURE POSTURE — BLOCKED.** Admission failure creates no `turn_id`, yet the notice is said to be “itself journaled,” while the only proposed durable outcome requires an admitted `turn_id` ([design:177-189](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:177), [design:227-240](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:227)). The journal has no schema, identity, deduplication, ordering, reconciliation, or journal-failure state; disk-full/read-only/I/O failure can defeat both ledger and same-filesystem journal. The clinical carve-out also conflicts with accepted ordering: S4 must run before any ledger side effect ([BETA_ARCHITECTURE_DECISIONS.md:2045](/home/rohit/maez/docs/governance/BETA_ARCHITECTURE_DECISIONS.md:2045)), whereas I1 requires admission before every interceptor ([design:93](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:93)). A caller cannot arbitrarily label a path clinical—the guard decides—but D1 exempts all matched clinical classes, not merely crisis; the guard includes diagnosis, treatment, medication, and medical-fact requests and branches only on `.matched` ([clinical_boundary.py:375](/home/rohit/maez/core/safety/clinical_boundary.py:375)). On contention, each writer uses a process-local lock and five-second SQLite timeout ([writer.py:192](/home/rohit/maez/core/ledger/writer.py:192)); web is a separate process ([maez-web.template.service:13](/home/rohit/maez/scripts/maez-web.template.service:13)). A simultaneous web and daemon exchange causes at least four serialized transactions—user and reply for each—and the proposed one retry permits roughly ten seconds of lock waiting plus backoff. Normal short transactions should serialize, but routine muting under normal load is **UNVERIFIED**: there is no transaction-duration budget, load profile, or contention falsifier.

6. **SCHEMA MECHANICS — BLOCKED.** D3 is not a one-line exclusion change. The writer hashes its row before resolving `lifecycle_stage` ([writer.py:352](/home/rohit/maez/core/ledger/writer.py:352), [writer.py:441](/home/rohit/maez/core/ledger/writer.py:441)); the verifier later hashes `SELECT *`, including the stored stage once the exclusion is removed ([verify_ledger_chain.py:64](/home/rohit/maez/scripts/verify_ledger_chain.py:64), [chain.py:161](/home/rohit/maez/core/ledger/chain.py:161)). Genesis likewise lacks a stage ([migrate.py:46](/home/rohit/maez/core/ledger/migrate.py:46)). D4’s assertion that `migrate.py` will refuse an amended `0001` is false: migration identity is filename-only, and already-recorded names are skipped without a digest check ([migrate.py:92](/home/rohit/maez/core/ledger/migrate.py:92), [migrate.py:121](/home/rohit/maez/core/ledger/migrate.py:121)); `ledger_is_initialized` checks only the old structural anchors ([migrate.py:234](/home/rohit/maez/core/ledger/migrate.py:234)). `parent_turn_id` remains nullable and lacks a per-kind SQL constraint ([0001_init.sql:18](/home/rohit/maez/core/ledger/migrations/0001_init.sql:18)), so I5 is not schema-impossible. Adding `non_model_reply` also requires a schema-version decision under current canon ([envelope-schema.md:570](/home/rohit/maez/docs/ledger/envelope-schema.md:570)). Amending `0001` is legitimate only if no authoritative instance exists; the zero-byte live-ledger premise was **not re-verified**, because access under repo `memory/` was forbidden, and is taken as given.

7. **FALSIFIERS T-F1–T-F8 — 0/8 BINARY-READY.** Section 7 supplies claims and informal kill conditions, but none freezes exact selectors, fixture/schema digests, inputs, configuration, fault cutpoints, clock, observation window, or exact-set queries as required by the earlier gate standard ([gate-round1:62-71](/home/rohit/maez/docs/superpowers/specs/2026-08-22-gate-round1-ledger-and-repair.md:62), [design:322-336](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:322)). Several are additionally contradictory or refer to unavailable machinery; details follow in section 3 below.

8. **MISSES OUTSIDE I1–I8 — BLOCKED.** The design lacks a durable temporal model. `MessageEvent` already carries provider occurrence time ([platform_base.py:785](/home/rohit/maez/skills/surface/platform_base.py:785)) and Telegram fills it from `message.date` ([telegram_adapter.py:3657](/home/rohit/maez/skills/surface/telegram_adapter.py:3657)), but the proposed rail signature omits it and the writer substitutes local `time.time()` ([writer.py:352](/home/rohit/maez/core/ledger/writer.py:352)). Delayed/redelivered events and merged constituents can therefore be dated as “now”; current biography reads then order by that timestamp ([recent_turns.py:76](/home/rohit/maez/core/ledger/recent_turns.py:76)). The design also omits reader migration: current self-history reads reply rows without joining delivery outcomes and renders them as “Prior Maez utterances” ([recent_turns.py:87](/home/rohit/maez/core/ledger/recent_turns.py:87), [envelope_builder.py:166](/home/rohit/maez/core/cognition/envelope_builder.py:166)), so failed/suppressed/unknown speech can remain biographically asserted as spoken. Finally, I6 says no writer may stamp unknown as gestation, but the audit store defaults `memory_phase` to gestation and ordinary inserts omit it ([audit_log.py:88](/home/rohit/maez/core/cognition/audit_log.py:88), [audit_log.py:302](/home/rohit/maez/core/cognition/audit_log.py:302)). These are independent silent misdating/misrepresentation paths.

## 2. Deduplicated blocker list

- **B1 — Interaction universe and post-birth scope are not closed.** Sections 1, 8 · **BLOCKS-BIRTH**. GUI, public Telegram/web, fast lane, special Telegram commands/callbacks, cockpit decisions, and outbound-first producers are outside the proposed doorway/outcome registry. Anchors: [gui.py:627](/home/rohit/maez/gui.py:627), [telegram_public.py:371](/home/rohit/maez/skills/telegram_public.py:371), [web_interface.py:10127](/home/rohit/maez/skills/web_interface.py:10127), [maez_daemon.py:5449](/home/rohit/maez/daemon/maez_daemon.py:5449).

- **B2 — Raw event, logical turn, and processing run identities are conflated.** Sections 2, 3 · **BLOCKS-BIRTH**. Aggregation discards constituent identity/time; voice lacks identity; web has no actual retry key; edits lack correction semantics. Anchors: [conversation_turn_seq.py:22](/home/rohit/maez/core/brain/conversation_turn_seq.py:22), [telegram_adapter.py:2979](/home/rohit/maez/skills/surface/telegram_adapter.py:2979), [wake_word.py:663](/home/rohit/maez/skills/wake_word.py:663).

- **B3 — Admission dedup does not claim execution.** Sections 2, 3 · **BLOCKS-BIRTH**. `was_replay` does not define terminal/in-flight/stale-run behavior or stop duplicate cognition, actions, and sends. Anchors: [design:129-139](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:129), [platform_base.py:1745](/home/rohit/maez/skills/surface/platform_base.py:1745).

- **B4 — Occurrence time and authoritative ordering are absent.** Section 8 · **BLOCKS-BIRTH**. Provider time is dropped; admission-wall-clock is stored; aggregation loses constituent chronology; self-history orders by the substituted time. Anchors: [telegram_adapter.py:3668](/home/rohit/maez/skills/surface/telegram_adapter.py:3668), [writer.py:354](/home/rohit/maez/core/ledger/writer.py:354), [recent_turns.py:76](/home/rohit/maez/core/ledger/recent_turns.py:76).

- **B5 — Outcome evidence has the wrong cardinality and first-writer semantics.** Sections 3, 8 · **BLOCKS-BIRTH**. Multiple egresses, multipart partial delivery, live-turn reconciliation races, gap-journal precedence, late correction, outcome immutability, reply binding, and reader consumption are all unresolved. Anchors: [platform_base.py:1946](/home/rohit/maez/skills/surface/platform_base.py:1946), [telegram_adapter.py:1309](/home/rohit/maez/skills/surface/telegram_adapter.py:1309), [0002_triggers.sql:7](/home/rohit/maez/core/ledger/migrations/0002_triggers.sql:7).

- **B6 — Phase proof and latch mechanics are not coherent.** Section 4 · **BLOCKS-BIRTH**. Zero-byte gestation conflicts with error→unknown; the latch lacks ledger binding, atomic creation, corruption rules, and birth-ID equality. Anchors: [design:250-266](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:250), [birth_phase.py:25](/home/rohit/maez/core/memory/birth_phase.py:25).

- **B7 — Restore rewind and phase-consumer coverage remain open.** Sections 4, 8 · **BLOCKS-BIRTH**. Same-birth-ID stale restores evade the latch; file replacement is not coordinated with it; `LedgerWriter` and audit logging can still stamp gestation. Anchors: [restore.py:140](/home/rohit/maez/scripts/backup/restore.py:140), [writer.py:443](/home/rohit/maez/core/ledger/writer.py:443), [audit_log.py:113](/home/rohit/maez/core/cognition/audit_log.py:113).

- **B8 — Admission-failure and clinical authority contracts contradict.** Section 5 · **BLOCKS-BIRTH**. An unadmitted notice cannot use the proposed outcome schema; secondary journal failure is undefined; I1 conflicts with Decision 30’s clinical-first authority; “clinical” is broader than “crisis.” Anchors: [design:227-240](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:227), [BETA_ARCHITECTURE_DECISIONS.md:2047](/home/rohit/maez/docs/governance/BETA_ARCHITECTURE_DECISIONS.md:2047), [clinical_boundary.py:389](/home/rohit/maez/core/safety/clinical_boundary.py:389).

- **B9 — Chain and migration mechanics cannot enact D3/D4 safely.** Section 6 · **BLOCKS-BIRTH**. Stage is resolved after hashing; genesis lacks it; amended migrations are silently skipped by filename; schema readiness does not fingerprint the new baseline; I5 is not a SQL invariant. Anchors: [writer.py:441](/home/rohit/maez/core/ledger/writer.py:441), [migrate.py:121](/home/rohit/maez/core/ledger/migrate.py:121), [0001_init.sql:29](/home/rohit/maez/core/ledger/migrations/0001_init.sql:29).

- **B10 — Normal-load lock posture is unmeasured.** Section 5 · **SHOULD-FIX**. Static maximum is about ten seconds of SQLite waiting with the proposed retry, but ordinary-load mute probability is unverified. Anchor: [writer.py:223](/home/rohit/maez/core/ledger/writer.py:223).

- **B11 — Acceptance evidence is not pre-registered or currently executable.** Sections 6, 7 · **BLOCKS-BIRTH**. All falsifiers lack frozen contracts, and the existing rehearsal writer explicitly refuses `birth_anchor`, contradicting “born rehearsal ledger.” Anchors: [writer.py:279](/home/rohit/maez/core/ledger/writer.py:279), [design:303-336](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md:303).

## 3. Falsifier readiness

**0/8 falsifiers binary-ready.**

- **T-F1 — NOT READY:** referenced “§1 bypass table” is not a closed path matrix; exact production entrypoints, payloads, identities, flags, expected outcomes, queries, and deadlines are unfrozen.
- **T-F2 — NOT READY:** surface/payload/concurrency schedule is unspecified, Telegram aggregation is explicitly unresolved, and it does not assert one cognition/action/send.
- **T-F3 — NOT READY:** “user-write failure” is incompatible with an outcome FK requiring admission; exact fault seams, crash cutpoints, clocks, journal states, reconciliation command, and expected labels are absent.
- **T-F4 — NOT READY:** wording can wrongly forbid `delivered` for a successful fallback; fake-transport script, exact bytes, hash domain, attempts, and per-case expected outcomes are not frozen.
- **T-F5 — NOT READY:** “every memory/private-thought write” has no closed callable inventory, injected failure point, latch/cache state, typed result, or before/after store manifest.
- **T-F6 — NOT READY:** no exact command, environment, dependency baseline, flag list, replay manifest/digest, filesystem boundary, or exclusions.
- **T-F7 — NOT READY:** phase API, ledger/latch fixture bytes, first-observation operation, deletion/sidecar procedure, cache state, and exact typed result are unspecified.
- **T-F8 — NOT READY:** the promised SQL is absent; one seeded positive cannot prove “every,” and no negative controls or exact-set equality prevent false positives.

## 4. Per-slice verdicts

- **S1 — BLOCKED.** B6 and B7: zero-byte classification, latch binding/atomicity/corruption, restore behavior, and the complete phase-consumer census are unresolved; T-F5/T-F7 are not ready.

- **S2 — BLOCKED.** B2, B4, B5, and B9: identity levels, temporal fields, outcome schema, parent SQL enforcement, schema version, canonical hashing, and migration fingerprinting are unresolved.

- **S3 — BLOCKED.** B1, B2, B3, and B8: there is no complete doorway registry, stable raw-event/run model, replay processing claim, or lawful clinical/admission ordering; T-F1/T-F2 are not ready.

- **S4 — BLOCKED.** B4 and B5: one outcome cannot represent all egress attempts; reconciler races can persist the wrong terminal result; CLI streams before its final persistence point ([maez_chat.py:1019](/home/rohit/maez/cli/maez_chat.py:1019)); web only returns a Flask response object rather than observing socket completion ([web_interface.py:7473](/home/rohit/maez/skills/web_interface.py:7473)); T-F3/T-F4 are not ready.

- **S5 — BLOCKED.** B1, B2, and B8: non-synthesis coverage omits direct commands/callbacks, public/fast-lane/GUI paths, outbound-first interactions, edit semantics, and a real voice identity.

- **S6 — BLOCKED.** B5, B8, B10, and B11: refusal journaling is circular, known and inferred outcomes race, live turns are indistinguishable from crashes, journal failure is undefined, and reconciliation/load falsifiers are not ready.

This was a static read-only review at `789e995`; no tests, SQLite execution, repository writes, services, or repo `memory/` contents were touched.

