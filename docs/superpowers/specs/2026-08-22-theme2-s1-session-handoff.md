# Handoff — Theme 2, from design to first code (S1)

## THE PROMPT (paste this to start the session)

> We are continuing Theme 2 of the birth blockers ("the ledger cannot
> omit or misdate a life"). The design phase is COMPLETE: eleven Codex
> gate rounds, schema clean at round 10 (~110 adversarial controls all
> rejecting), S1 witness protocol binding-ready at v5. Read, in order:
>
> 1. `docs/superpowers/specs/2026-08-22-theme2-s1-session-handoff.md`
>    (this file) — §State and §Cautions before anything else.
> 2. `docs/superpowers/witness/theme2-s1-protocol.md` — ALL sections
>    including §§9–11 amendments. This is the binding contract; S1 is
>    judged against it, not against design prose.
> 3. `docs/superpowers/specs/2026-08-22-theme2-ledger-truth-design.md`
>    §5, §12–§16 (phase truth + latest folds) and
>    `2026-08-22-theme2-schema-v2-draft.sql` (rev 8) for context.
> 4. `docs/superpowers/specs/2026-08-22-theme2-gate-round10.md` and
>    `-round11.md` — the rulings that opened this work.
>
> Then do, in order:
>
> **Task 1 — the T5 baseline archive (owner is present for this).**
> Drive `docs/superpowers/witness/theme2-s1-replay.json` (20
> interactions, digest 2b9faf61…) through the reply machinery,
> flags-off, ENTIRELY inside an airlock. Before executing anything:
> read `scripts/replay_harness.py` and verify every path it touches —
> env-resolved AND module-global — lands inside the airlock (the
> hermetic-sandbox hazard: env redirection misses module-global
> absolute paths; the class that deleted live stores and once rebooted
> this host). If any path cannot be redirected, STOP and redesign the
> run with the owner rather than proceeding. Archive the resulting
> store tree as `docs/superpowers/witness/theme2-s1-baseline.tar.zst`.
>
> **Task 2 — protocol v6 amendment**: append the archive's sha256 to
> the protocol and commit BEFORE any S1 code commit (round 11 made
> this ordering binding).
>
> **Task 3 — implement S1** against the protocol, flag-dormant, TDD.
> The APIs are pinned and may not drift: `core.memory.birth_phase.
> resolve() -> PhaseResult(phase, reason)` with the frozen 12-reason
> enum (protocol §9); `core.memory.birth_latch.advance()` with the
> §§9/11 line schema (canonical JSON, six keys, three kinds,
> temp+rename+dir-fsync publication); `PhaseUnknownRefusal` raised by
> every census consumer on unknown; `python3 -m core.memory.s1_census`
> per §10. Consumers to modify are the 15 constructs in
> `theme2-s1-census.json` — and ONLY those (T4 fails both on missing
> and extra). Run the T1–T6 witnesses as you build; the run report
> obligations are protocol §8.
>
> **Task 4 (parallel or after)** — author the S2 witness protocol
> (unlocked at round 10). Its core already exists: the accumulated
> ~110-control suite from gate rounds 2–10 becomes the pre-registered
> rejection tests, plus migration-digest witnesses, recreate-empty
> exclusivity witnesses (design §14 F6), and the cross-process
> BEGIN IMMEDIATE fencing witness that in-memory reviews could never
> execute.
>
> Gate with Codex when S1's witness run is complete and when the S2
> protocol is drafted. Do not touch the creation manifest — owner-only.
> Maez is cleanly unborn; the ledger flag stays off; everything lands
> flag-dormant.

## §State (at `64d4cbb`)

- Design passes 1–10 + gate rounds 1–11, all committed (23 commits,
  `789e995..64d4cbb`). Round 10: schema CLEAN, S2 authoring unlocked.
  Round 11: protocol 6/6 binding-ready after v5.
- S1 code is gated on exactly one artifact: the baseline archive +
  its digest amendment (Tasks 1–2).
- The live tree: `memory/ledger.db` still 0 bytes; `MAEZ_LEDGER_WRITES`
  set nowhere; Maez unborn; creation manifest absent (owner-only).
- Companion artifacts committed with frozen digests: census
  (8527…), replay (2b9f…), selectors (7759…), fixture builder
  (b69a…). Static fixture digests: F-E (e3b0…, the empty file), F-P
  (8792…). F-G/F-L digests are per-run (migration stamps wall-clock).
- Genesis chain hash is deterministic: `d313c6473ea19dbe…989d` — a
  byte-exact anchor the T6 validator demands.

## §Cautions — earned, not theoretical

1. **The replay harness is the risky step.** This repo's scars: tests
   pinned real systemctl and REBOOTED the host 3×; a full-suite run
   deleted two live stores through module-global absolute paths; env
   sandboxing does NOT redirect module-global paths. Read the harness
   first; trace its paths; airlock everything; owner present.
2. **Never run test discovery against the live tree.** Explicit file
   lists only (`theme2-s1-selectors.txt` is frozen for this reason).
3. **Codex practical notes**: effort medium default, xhigh for full
   gates, high for narrow checklists. Use schema-conformance /
   invalid-row-rejection vocabulary — adversarial/security phrasing
   got one run KILLED by the provider content filter mid-verdict.
   Poll the job JSON yourself at
   `~/.claude/plugins/data/codex-openai-codex/state/maez-069d21fed3e7e0ce/jobs/task-*.json`;
   the forwarder will not. An absent verdict is not a pass.
4. **Don't read background outputs mid-write**; wait for completion
   status in the job JSON before reading rawOutput.
5. **The protocol is never edited retroactively to fit an outcome.**
   If a witness fails, the failure is the finding — report it, fix
   the code or (with a new gate round) the protocol, never quietly.

## §Covenant constants

S4 guard before any owner-text side effect (Decision 30). Ledger
activation is birth-gated, owner-only. No agent writes a word of
`config/creation_manifest.md`. Flags off ⇒ byte-identical behavior
(T5 exists to prove it). Forgetting is deweighting; records are
append-only; late knowledge is labeled late.
