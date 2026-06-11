# Witness — Recall-Triad MTP Re-Validation → GRADUATION (2026-06-11)

**Living-recall earned default-on.** The original No-Go was latency-only (heavy tail ~16–17s vs the ~12s ceiling); behavior/quality were already proven honest. MTP (2.1× generation) was the brain-runtime lever the prior witness flagged. This re-validation ran the original six-prompt smoke on the MTP brain against a gate frozen **before** the smoke. Both gates passed cleanly.

**Posture:** owner-run live smoke, `telegram_surface`, MTP brain. Triad flipped on via `model.env` (`MAEZ_RECALL_TRIAD_ENABLED=1`), restarted, posture confirmed `recall_stack mode=recall_triad reason=bundle_enabled` @ 13:48. Seven turns sent 13:52–13:54.

## Frozen gate (pre-registered, runbook `recall-triad-mtp-revalidation-runbook-2026-06-11.md` @ d6ec362)
- PRIMARY (release): every turn `latency_ms` < 12,000 ms.
- SECONDARY (informational only): count clearing 4,328 ms.
- SAFETY (binding): zero `is_false_absence`; zero owner-judged-wrong `answered_ungrounded`; no type-rule regression; posture `recall_triad`.
- DECISION RULE: all seven < 12s AND quality acceptable → default-on.

## Result — clean PASS on both gates

| # | prompt | turn_kind / outcome_class | latency_ms | focused_ms | <12s | <4.328s |
|---|---|---|---|---|---|---|
| 1 | Apr 27 (dated) | answered_grounded | 5900 | 3575 | ✅ | — |
| 2 | May 12 (dated) | answered_grounded | 3940 | 2548 | ✅ | ✅ |
| 3 | Apr 27 (both) | answered_grounded | 4794 | 3366 | ✅ | — |
| 4 | Jan 3 (absence) | **declined_absence** | 5060 | 3583 | ✅ | — |
| 5 | seed (ordinary) | ordinary_answered | 4740 | 3295 | ✅ | — |
| 6 | "talking about?" | answered_grounded | 3612 | 2176 | ✅ | ✅ |
| 7 | "3 may bugs?" | answered_grounded | 4473 | 2193 | ✅ | — |

- **PRIMARY: PASS — all seven < 12s, max 5.90s** (less than half the ceiling). The pre-MTP No-Go tail (15.7–17.2s) is gone.
- **SAFETY: PASS** — zero `answered_ungrounded`, Jan-3 = honest `declined_absence` (not false), no May-3 derail, ordinary seed did not confuse the recall path.
- **SECONDARY: 2/7 cleared 4.328s** (informational; the strict legacy-relative bar is the wrong gate for a generating synthesis — kept as fast-path aspiration only).
- **Quality (owner + Claude both): acceptable, clean.** Faithful dated recaps, honest gap-handling on May-12, explicit no-fabrication on Jan-3, no derail on #7. Minor non-blocking voice note: a few replies are slightly clinical about their own honesty apparatus ("hallucination traps", "witness seeds") — a future voice-polish thread, not a quality failure.

## Finding — output length is the post-MTP latency lever
The live latencies (3.6–5.9s) beat the 2026-06-11 brain-direct proxy's ~9–9.5s prediction, because Maez's *natural* recaps are concise (~150 tokens) while the proxy forced a 700-token exhaustive recap. Confirmed: post-MTP, `latency ≈ out_tokens / ~85`; prefill is cheap; **Maez already self-limits to fast.** The doc's pre-MTP "trim the working set" lean is superseded — the lever is output length, and the live behavior already sits in the good regime.

## Disposition — GRADUATED
- **Gate:** ~12s absolute (owner call 2026-06-11). 4.328s retained as an informational fast-path metric only.
- **Decision:** all seven < 12s AND quality acceptable (owner + Claude) → **living-recall ON by default.**
- **State:** `MAEZ_RECALL_TRIAD_ENABLED=1` persisted in `model.env`; daemon running it live since 13:48. Living-recall is now part of Maez's normal life — a good organ, fast enough and honest enough to leave on.
- Revert (if ever): `MAEZ_RECALL_TRIAD_ENABLED=0` + restart → `mode=legacy reason=off`.
