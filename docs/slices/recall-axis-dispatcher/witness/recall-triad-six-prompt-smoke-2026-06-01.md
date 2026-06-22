# Witness — Recall-Triad Six-Prompt Smoke (2026-06-01)

**The clean receipt for the arc: the scoreboard is now honest; recall behavior works; latency is the only No-Go.**

**Posture:** owner-run live smoke on `main` @ `3ca8071` (the merged honest scoreboard: classification-correctness `948ec9e` + continuity-grounding `3ca8071`). Triad/v2/receipt **on** via launch-env only (`MAEZ_RECALL_TRIAD_ENABLED=1`, `model.env`; `config/.env` clean). Posture confirmed `recall_stack mode=recall_triad reason=bundle_enabled` @ 09:30:35; **reverted to `mode=legacy reason=off` @ 09:34:05** (kill-switch clean, owner's hand). This was a bounded re-witness, not a flip.

## Method
Six prompts covering the four recall shapes (2 dated-hit, 1 both-shaped, 1 dated-absence, 2 continuity), with a fresh non-dated seed ("blue notebook and a copper key") before the continuity pair so a faithful recap is unmissable. Captured per-turn `recall_outcome` (turn_kind, outcome_class, latency_ms, focused_elapsed_ms) + `focused_cognition_prompt_shape` (evidence volume). Pre-registered read frozen before the paste.

## Scoreboard — HONEST across all six (the win)

| # | Prompt | turn_kind / outcome_class | Reply shape | Verdict |
|---|---|---|---|---|
| 1 | "What did we note around April 27?" | `dated` / **answered_grounded** | faithful dated recap (commit, friction), receipt fired | ✓ |
| 2 | "What did we note around May 12?" | `dated` / **answered_grounded** | faithful (hardware event, snapshot gap) | ✓ |
| 3 | "Remind me what we were doing around April 27." | `both` / **answered_grounded** | faithful (compliance-monitor, maez_pulse failure) | ✓ |
| 4 | "What happened on January 3?" | `dated` / **declined_absence** | honest "no record… won't fabricate" | ✓ |
| 5 | "What were we just talking about?" | `continuity` / **answered_grounded** | faithful seed recap, `source_types=dialogue_anchor` | ✓ |
| 6 | "What were we just talking about, the 3 may bugs?" | `continuity` / **answered_grounded** | continuity-shaped, **no archival May-3 derail** | ✓ |

**Scoreboard verdict: zero `answered_ungrounded`, zero `is_false_absence`.** Both telemetry slices are validated in production:
- **#4 (Jan-3)** logs `declined_absence` (denial_kind=no_dated_memory, had_confirmed=false, receipt=consulted → legal absence, NOT false) — the exact turn the original No-Go mis-scored as `answered_ungrounded`.
- **#5/#6** log `answered_grounded` from the `dialogue_anchor` — the exact turns the 2026-06-01 mini re-witness showed as false-`ungrounded`.
- **#6** — the original No-Go #5/#6 derail — is cleared *and* honestly scored.

The scoreboard tells the truth. The behavior under live triad is correct.

## Latency — the No-Go (A7 absolute ceiling ~12,000 ms)

| # | turn_kind | latency_ms | focused_elapsed_ms | evidence_items | working_set_chars |
|---|---|---|---|---|---|
| 1 | dated | 7,258 | 5,182 | 7 | 10,162 |
| 2 | dated | 5,292 | 3,771 | 4 | 2,445 |
| 3 | **both** | **17,184** | **15,702** | 7 | 9,373 |
| 4 | dated | 5,897 | 4,444 | 6 | 8,052 |
| seed | ordinary | 12,257 | 10,264 | 16 | 10,145 |
| 5 | continuity | 4,710 | 3,304 | 1 | 642 |
| 6 | continuity | 4,417 | 3,007 | 1 | 663 |

Five of six recall turns are under the ~12s A7 ceiling (4.4–7.3s); **#3 (both-shaped) hit 17.2s** and the seed hit 12.3s. With n=6, **p95 ≈ max ≈ 17s — over the ceiling.**

**Pre-registered read → LATENCY FAILS A7 → recall stays off.** Disposition: No-Go on latency; recall reverted to legacy/off.

### Driver analysis (load-bearing for the speed slice — do NOT assume)
- `legacy_prompt_chars≈118k` is logged on **every** focused turn including the fast 1-item continuity turns (3.0–3.3s focused) — so it is a logged *comparison baseline*, not what the brain receives. It is **not** the latency driver.
- **Working-set size does NOT cleanly predict latency.** #1 and #3 both = 7 items / ~10k working_set_chars, yet focused 5.2s vs 15.7s (3×). The seed (16 items / 10k) ran 10.3s — *faster* than #3's 7 items.
- The only clean signal: **1-item continuity turns are consistently fast (~3s)**; multi-item turns are slow *and high-variance*.
- Therefore the dominant driver appears to be **local-brain generation variance**, with working-set volume a loose secondary factor. The speed slice must **measure which lever actually moves latency** before committing to a fix — trimming the working set may or may not be the answer; brain/runtime (quantization, draft model, server config) is a co-equal candidate.

## Follow-ups (recorded, separate slices — not folded)
1. **Speed slice (PRIMARY, next).** Measurement-first: instrument the focused-synthesis latency to attribute it (working-set assembly vs prompt size vs brain generation vs output length), then target the heavy/both-shaped cases. Owner's lean: prove whether the heavy working set can be **trimmed/ranked/capped without losing truth** (preserve citation/grounding gates), as the first repo-side lever; model/runtime benchmarking (brain-bench) is a parallel lever. **Not** "make answers shorter."
2. Brain-bench continuity hard-gating + offline-anchor infra.
3. Continuity grammar gap ("covered"/"chatting" classifier misses).
4. Hermetic-test env boundary (recall-posture tests force their own env).

## One-line provenance
Honest scoreboard confirmed live; continuity + classification + honest-absence all correct under triad; latency the sole gate; recall off. Witness before claim — this is the receipt that stops the speed slice from re-litigating solved problems.
