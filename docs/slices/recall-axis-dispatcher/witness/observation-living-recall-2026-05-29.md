# Observation — Living Memory (Recency-Salience + Continuity) Live Witness

**Date:** 2026-05-29
**Purpose:** Behavioral proof of the living-recall slice on `main` **pre-merge** (path (b): three files transplanted into main's working tree, witnessed before any commit/merge). The whole risk is the **live framing path** — only main's runtime (`config/.env` + live daemon) exercises it. Diff already cross-lane verified GREEN (zero new failures vs the worktree baseline; the worktree's floor noise was a missing `config/.env`).
**Spec/plan:** [spec rev 3](../../../superpowers/specs/2026-05-29-living-memory-recency-salience-design.md) · [plan](../../../superpowers/plans/2026-05-29-living-memory-recency-salience.md). Flag `MAEZ_LIVING_RECALL_ENABLED=1` via **launch-env only** (NOT `config/.env`).

## Setup
- **First window (21:24, PID 144778) was lost to a system REBOOT at 21:54:11** — the enabled unit auto-started flag-absent (PID 3088) on boot; Rohit verified `/proc` and correctly refused to probe a flag-absent daemon. Window reopened.
- **Reopened window 2026-05-29T22:00:** witness daemon PID **9903** (setsid-detached, PPID 2971, survives the tool), launch-env flags `MAEZ_DISPATCHER_ENABLED=1 MAEZ_FOCUSED_COGNITION_ENABLED=1 MAEZ_LIVING_RECALL_ENABLED=1` (dispatcher needed to reach the recall adapters — the realistic default-on path, tests directly against the Obs-17 failure). `config/.env`: 0 flag matches (fully reversible). Owns ports 11435/11436; Telegram thread + reasoning loop up.
- **Live-path bug caught (Rohit, RED-first) before any probe:** `skills/surface/maez_adapter.py` passed `surface="adapter"`, but living recall gates on `surface.startswith("telegram")` — a real Telegram turn would have silently used legacy recall, invalidating the witness. Fixed to pass `SURFACE_NAME = "telegram_surface"` (verified: surface+living tests 35 OK). **Transplant is now 5 files** (adds `skills/surface/maez_adapter.py`, `tests/test_surface_adapter.py`).
- **Restarted from patched tree 22:56:** witness daemon PID **20128** (setsid-detached, 3 flags, owns ports 11435/11436, Telegram thread up 22:56:30). **Probe delta from offset: 27770326.** Probes go through the **real Telegram surface** (not `/message`, which hardcodes `source="UI"`).

## Predicted effect (written BEFORE probes — canon discipline)

For **Telegram** recall turns, flag-on:
1. **Stale meta-memory stops surfacing as evidence.** "What have we discussed about local AI recently?" / "What were we talking about earlier?" → recent material / the recent thread as `[memory evidence]`; any months-old journal appears **at most as `[memory context]`**, never `[memory evidence]`.
2. **Recent/fresh asks improve** — recency-weighted recall surfaces genuinely recent context near the top.
3. **Deep recall NOT buried** — a deliberately old, explicitly-named memory ("what did we note back around April 6?") still **appears** (as `[memory context]`). The falsifier against over-decay.

**Framing behavioral check (the live-path risk):** the telegram recall turn must emit **both** `[memory evidence]` and `[memory context]` (the two-block split), not collapse to evidence-only or context-only. Codex's adapter is framing-adaptive, so this confirms the turn actually gets `SUBSTRATE_ONLY_NO_FRESH_VALIDATION` (permits both), not a framing that drops a partition.

**Trace expectations:** `living_recall_candidate` log lines (with `base_distance`, `recency_factor`, `effective_distance`, `shadow_promotion=…` logged but NOT applied); the audit `source_role_entries` carries both `SUBSTRATE_EVIDENCE` and `SUBSTRATE_CONTEXT` for `TELEGRAM_SEMANTIC` in the same turn.

## Failure criteria (FALSIFY → red → revert the 3 files, leave branch unmerged)
- A months-old memory renders as `[memory evidence]`.
- A continuity ask ("what were we talking about earlier?") surfaces old meta-memory instead of the recent thread.
- An explicitly-named old memory is **absent entirely** (buried by over-decay).
- The split **collapses** to one role on a substrate-recall turn (evidence-only or context-only when both were expected).
- Telemetry lies (shadow promotion actually changes ranking; raw owner text persisted).
- Any SEGV / fatal, or a real (non-environmental) broad-floor regression.

## Suggested probes (Rohit sends; Claude reads the trace)
1. `What have we discussed about local AI recently?` — gate 1+2 + framing split.
2. `What were we talking about earlier?` — gate 1 continuity (recent thread, not old "what happened?").
3. `What did we note back around April 6 about the infrastructure?` — gate 3 deep recall (must still appear, as context).

## Results — RED (reverted, branch unmerged)

Daemon PID 20128, real Telegram probes (3), trace from offset 27770326.

**The recall ENGINE works (verified in trace):**
- Living recall fired — 432 `living_recall_candidate` lines; recency math correct (recent `recency_factor=0.9971`, ~15-day `0.8905` pushing `effective_distance` 0.369→0.414).
- `shadow_promotion=0.0000` **logged, not applied** (`effective = base/recency` only) — anti-laundering holds. ✓
- **Surface fix landed** — `surface=telegram_surface` (real Telegram path, not `/message`). ✓
- Framing correct — `provenance_framing=SUBSTRATE_ONLY_NO_FRESH_VALIDATION` (permits both substrate roles). ✓

**But the slice's value did NOT manifest live:**
| Gate | Result |
|------|--------|
| 1 — no *stale* memory cited as evidence | **PASS** — only recent (≤14d) memories cited `[E1]`; no months-old journal as evidence |
| 2 — fresh asks improve | partial — recent surfaced, but irrelevant (no recent local-AI memory existed; honest "only a 2-day health check") |
| 3 — deep recall NOT buried | **FAIL** — April-6 memory absent; it lives in the context partition that never rendered |
| two-block split renders | **FAIL** — **12 `[memory evidence]`, 0 `[memory context]`** |
| continuity → recent thread | **FAIL** — "what were we talking about earlier?" → a 2-day health check, not the recent thread |

**Root-cause direction (for the next branch cycle — NOT budget, NOT framing):** the context block is genuinely *built* (`format_for_prompt(context, max_chars=300)` renders ~4173 chars — core memories aren't dropped by budget) yet **never appears in the prompt as `[memory context]`** under a framing that *permits* it. So the bug is in the path between the living adapter emitting the `SUBSTRATE_CONTEXT` block and its rendering — to debug on the branch (likely an interaction with the per-block role grouping when both substrate sources each emit two roles, or the spec/source wiring). Separately, the continuity faculty did not surface the recent thread (recent exchange not yet stored, or `_latest_telegram_exchange_rows`) — debug alongside.

## Service posture (closed)
- **RED → reverted.** The 5 transplanted files restored to `main @ 1932387` (0 living refs); 69 unrelated dirty files untouched. Living-recall work preserved on branch `living-memory-recency-salience` (worktree), **unmerged**.
- Daemon restored under the unit: PID **23964**, `maez.service` active, **flag-absent**, single instance. `config/.env` never touched.
- **Next:** fix the context-block-render + continuity-thread on the branch (RED-first), then re-witness. The engine + recency + shadow-only + surface + framing are proven; the remaining bug is render/integration.

## Attempt 2 (after branch repair — 2026-05-29T23:29)

Branch fixes (Codex, RED-first; Claude diff-verified GREEN, 80 focused tests OK, no crash in the slice path): (1) each role block **hard-bounded** before Layer1 so context isn't budget-dropped; (2) continuity uses a **chat_history dialogue anchor** as evidence (threaded `chat_history` through the dispatcher); (3) context block renders **dynamic daily/raw ahead of core volume** so deep recall survives; (4) surface fix carried. 5 new RED tests.

- Transplanted 5 fixed files to main (verified: import OK, 56 slice tests OK). Witness daemon PID **45408** (setsid, 3 flags, owns ports, Telegram thread up 23:29:18). config/.env clean. **Probe delta from offset 28111619.** Same 3 probes, real Telegram surface.
- **Pinned checks (now test-backed):** both `[memory evidence]` AND `[memory context]` survive Layer1; continuity → the chat_history dialogue anchor (not stale semantic); April/deep old memory appears as `[memory context]` (not buried by core).

### Attempt 2 Results — RED again (same wall; budget hypothesis wrong)

Daemon PID 45408, 3 real Telegram probes, trace from 28111619.
- Engine still good: 432 `living_recall_candidate`, `surface=telegram_surface`, `provenance_framing=SUBSTRATE_ONLY_NO_FRESH_VALIDATION`, `shadow_promotion` logged-not-applied.
- **Progress:** continuity anchor fired — "Recent dialogue anchor" appears 4× (chat_history threading works; the recent thread reaches the evidence block).
- **STILL RED:** `[memory context]` = **0** (12 `[memory evidence]`, 0 `[memory context]`). The `SUBSTRATE_CONTEXT` block is emitted by the adapter but **still never renders** — the budget-bound fix addressed a hypothesis that was not the cause. Deep recall still buried; continuity reply still cited the health check (the anchor reached the prompt but the synthesis didn't use it — likely not `[E#]`-labeled).

**Critical lesson (canon: unit-test-is-not-integration-witness):** Codex's `test_layer1_budget_preserves_context_role_for_both_telegram_sources` **passes** while the live path drops `[memory context]`. The isolated test does not reproduce the live `_run_dispatcher_pipeline` render path. **Stop the guess-and-witness loop.** Next cycle must be **integration-first**: reproduce the *live* dispatcher render with two substrate sources each emitting two roles, and pin exactly where the `SUBSTRATE_CONTEXT` block is lost between adapter-emit and prompt-render (Layer1 fanout collection / merge / the `_source_role_for_dispatcher_block` spec-role override / the spec's `substrate_sources`). The trace doesn't expose recall-block roles, so instrumentation or a faithful integration repro is required — not another guess.

- **Reverted** (5 files → main@1932387, 0 living refs); daemon restored under unit PID 47937, flag-absent; `config/.env` untouched; branch unmerged.

## Integration Root-Cause (2026-05-30, read-only, in-process) — MAJOR CORRECTION

Traced every boundary in-process (worktree, shared Chroma), per Rohit's plan. Result overturns the prior RED diagnosis:

| Boundary | Result |
|----------|--------|
| 1. adapters | both sources emit `SUBSTRATE_EVIDENCE`(900) + `SUBSTRATE_CONTEXT`(300) ✓ |
| 2. `_budget_blocks` / real `Layer1.run` | all blocks kept, **role_hints preserved** (caps 3/1200/4200; total 2400) ✓ |
| 3. `source_summaries_for_render` | produces `SUBSTRATE_CONTEXT` summary ✓ |
| effective framing (`_transform_for`) | `SUBSTRATE_ONLY_NO_FRESH_VALIDATION` — **permits both roles** ✓ |
| 4-5. `merge_fanout_results → render_provenance` | **renders BOTH `[memory evidence]` AND `[memory context]`**; `source_role_entries` carries both roles ✓ |

The live pipeline uses exactly this path (`brain_loop.py:726` `merge_fanout_results`, `:780` `transcript=rendered_turn.prompt_block`). **So the split renders correctly and `[memory context]` IS in the live prompt.** The witness "`[memory context]`=0" was a **log-head artifact** — I grepped the truncated `daemon_prompt_payload_shape` heads/tails; `[memory evidence]` sits at the recall block's head, `[memory context]` in the un-logged middle. **Both Attempt-1 and Attempt-2 were misdiagnosed on the split-render gate, and Codex's budget-bound repair fixed a non-bug.**

**The actual bugs (two, both downstream of recall/render):**
1. **Self-echo** — the just-sent probes are stored to `raw` and re-retrieved at `age=0d` as the TOP of the EVIDENCE partition (the questions become the evidence). The deferred "no-re-retrieval" item is a live blocker here.
2. **Synthesis ignores `[memory context]`** — the April-6 memory IS in `[memory context]` (a 53-day core journal, present in the prompt), but the reply said "no April 6." The brain answered from `[memory evidence]` only. So deep recall + continuity fail at **synthesis**, not recall/render — `[memory context]` (and the dialogue anchor) reach the prompt but aren't used/cited.

**Next fix targets (evidence-pinned, not guessed):** (a) suppress self-echo so EVIDENCE holds real recent memory, not the current questions; (b) make synthesis actually consume `[memory context]` / the dialogue anchor (focused-cognition working-set must include + `[E#]`-label context items, or the megaprompt must weight the context block). The recency engine, partition, role contract, and render are all proven correct.

## Attempt 4 — GREEN (narrow scope) → MERGED `1ef70a5` (flag-off)

After the compact-renderer seam + the **core-first / raw-cap** ordering fix (the deep memory rendered last and was budget-truncated; core-first puts it on the desk first). Live in-process gate (the merge gate) passed before the witness. Witness (content-anchored, PID 106614):
- **Gate 3 PASS (content-addressed deep recall):** `infrastructure ground-truth` + `2026-04-27` rendered inside `[memory context]` (6×); probe 3 reply **cited** it [E2] (not "no record"). Both labels render (12 evidence / 6 context).
- **Self-echo PASS:** the same-turn probe echo absent from the prompt.
- **Recency PASS:** probe 1 → the Maez/local-AI project memory, not a stale health log.
- **shadow_promotion** logged-not-applied. ✓
- **Continuity FAIL → named default-on blocker** (probe 2 cited the health check, not the anchor). Does not block flag-off merge (Rohit's rule).
- Caveat: probe-3 long memory partially truncated ("only the error itself") — cited+used, gate passes; quality follow-up.

**Landed flag-off** (`MAEZ_LIVING_RECALL_ENABLED` default-off → inert/legacy in prod). Narrow claim proven: **recency-salience + same-turn self-echo + content-addressed deep context.** Out of scope (next slices): **date-anchored temporal recall**; **continuity-synthesis** (default-on blocker). Default-on requires both + a default-on witness.

**Process lesson:** isolated-fixture unit tests went green while the live path stayed red **three times**; only the live-Chroma in-process repro caught it. The merge gate for this kind of recall work must be the live in-process repro, not a seeded fixture.
