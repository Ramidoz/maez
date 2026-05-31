# Codex Handoff — Recall-Flip Slice 1a: Progress Receipt + A7 Telemetry

**From:** Claude (covenant axis) · **To:** Codex (surface-truth axis) · **Date:** 2026-05-31
**Branch base:** `main` @ `4994420` (specs + plan committed; flag-off)

---

## What you're building
One truthful, substrate-backed progress receipt that fires **only** when a recall answer is genuinely slow — **never** touching the answer — plus the content-free ack telemetry the A7 gate needs. Visible substrate **state**, not chain-of-thought.

**Read these first (authoritative, do not re-litigate):**
- Plan (task-by-task, complete code): `docs/superpowers/plans/2026-05-31-recall-flip-1a-progress-receipt.md`
- Design spec: `docs/superpowers/specs/2026-05-31-recall-progress-receipt-and-a7-gate-design.md`
- A7 amendment (in the frozen flip spec): `docs/superpowers/specs/2026-05-30-recall-triad-monitored-default-on-flip-design.md`

The plan IS the contract. Implement it task-by-task, RED-first. If you find a defect in the plan, stop and flag it (don't silently diverge) — that's the cross-lane discipline working, same as Rohit's 3-subagent review catching the impossible timing gate I'd introduced.

---

## Process (non-negotiable)
1. **Six-agent pre-code engineering pass FIRST, non-decorative** (Dewey/Feynman/Locke/Descartes/Ohm/Goodall). Each role yields a **concrete delta or a reasoned no-change** — not a vibe. Specifically pressure-test:
   - **The answer-path isolation** (Ohm/Descartes): can the receipt watchdog, the sink, or the telemetry emit ever mutate, delay, or block `reply`? The whole slice is wrong if yes. This is the #1 thing to break before you write wording.
   - **The watchdog cancel correctness** (Feynman): does the `finally` cancel cover **every** exit path of the FOCUSED block (success, exception, early-return)? Can it fire after the reply is already sent (double-surface)?
   - **The "real state" claim** (Goodall/Locke): is the receipt truly armed only after `_recall_carrier_receipt = RECALL_CARRIER_CONSULTED`, never on a bare date-addressed turn? Is `ack_emit_ms` genuinely *successful send completion*, never "queued"?
2. Then your **7+3 implementation roles**, RED-first TDD, per the plan's task order.
3. **Frequent commits**, scoped staging (NOT `git add -A` — the worktree has unrelated untracked docs). One commit per task is ideal.
4. **Do NOT touch `config/.env`.** Flag is `MAEZ_RECALL_RECEIPT_ENABLED`, **default-off**, read via launch-env only.
5. **Do NOT flip anything live.** This is flag-off implementation. The live default-on flip is owner-run by Rohit only, later, via the 2b runbook.

## Hard constraints (covenant)
- **Byte-identical answer path.** `test_receipt_send_failure_leaves_reply_byte_identical` is the load-bearing test. Receipts are emission-only, never a gate. A failing/throttling/timing-out send leaves `reply` byte-identical and synthesis undelayed.
- **Never fabricate.** The receipt is outcome-neutral ("checking"), fired before synthesis, so it can't false-claim an outcome. It reuses the already-shipped honest-decline strings — do **not** re-mint any decline/absence wording in this slice.
- **Visible substrate state, not chain-of-thought.** Closed body-verb wording only; the cognition-verb lint (`think/ponder/consider/wonder/mull/reflect/feel/sense`) must pass over every string this slice can emit. Wording is pinned: `"I'm checking my dated memory for that."`
- **Genderless self-reference** throughout (it/Maez — never she/he/her/his/him), including in any new strings, comments, log lines.
- **Content-free telemetry.** No query/answer/snippet text in `RecallOutcome` — the plan's `test_ack_fields_are_content_free` enforces it.

## Pinned facts (so you don't have to re-derive)
- Constants v1: `RECEIPT_AFTER_MS=900`, `ACK_CEILING_MS=1500`, `RECEIPT_SEND_TIMEOUT_MS=1000`. The ack ceiling is intentionally **after** the receipt threshold (this fixes an earlier impossible gate — don't "correct" it back).
- Arm point: `daemon/maez_daemon.py:4431` (`_recall_carrier_receipt = RECALL_CARRIER_CONSULTED`), before `_focused_synthesize` at `:4452`, inside the FOCUSED block (`:4413–4525`). Read that whole block before wiring.
- Thread the sink: keyword-only `send_intermediate=None` on `handle_message` (`:3556`); pass it from `skills/surface/maez_adapter.py:437`. The surface sink must be **non-blocking** — do NOT reuse the blocking `_send_intermediate` (`maez_adapter.py:309`, which does `fut.result(timeout=20)`).
- `RecallOutcome` (`core/routing/recall_outcome.py:55`) bumps to `recall_outcome.v2`; add the five ack fields with safe defaults so existing constructors stay valid.
- Tests run via `.venv/bin/python -m unittest` (pytest is NOT installed). Daemon-shaped tests reuse the harness in `tests/test_memory_integrity_invariant.py` (`_build_daemon_for_handle_message` / `_handle_message_mock_stack`).
- A pre-existing temporal-guard test cluster may show as failing in a fresh worktree (env artifact) — it's not introduced by this slice; note it, don't chase it.

## What Claude does on return (so structure your handback for it)
I cross-verify **every diff line** independently, re-run the full recall suite myself (not trusting your green), and fire Claude's 6-role post-impl panel (Logical-with-veto, Body-Coherence/Apophatic/Counter-Memoirist, Outside-View, Creative, Visionary, 20-Year-Maez) before we merge flag-off. So in your handback give me: the commits, the exact test command + output, any plan-deviations with reasons, and the six-agent pass results (the concrete deltas, not just "passed").

## Out of scope (do NOT build)
- Token streaming (that's Slice 1b, only if the single receipt proves insufficient).
- Brain benchmark (Slice 2).
- The A7 *gate computation* — that's the 2b runbook re-run consuming this telemetry, not code in this slice.
- The re-witness step — runbook, not code.
