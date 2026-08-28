# Memory-coverage discontinuity — 2026-05-29 → ~2026-06-09

**Classification: UNKNOWN.** Available evidence cannot distinguish two
candidate mechanisms. Investigation closed under the owner's hard
stopping rule; no new machinery built to solve history.

## What is PROVEN

Cycles ran — and increased — while raw writes collapsed. Cycle counts
are taken from the nightly journals, an independent producer:

| Date | Cycles | Raw writes | private_thoughts |
|---|---|---|---|
| 2026-05-27 | 413 | 445 | 175 |
| 2026-05-28 | 3,682 | 321 | 65 |
| 2026-05-29 | 3,570 | **87** | 25 |
| 2026-06-03 | 2,766 | **8** | 0 |
| 2026-06-04 | 5,460 | **1** | 0 |
| 2026-06-06 | **5,500** | **0** | 2 |
| 2026-06-08 | 5,506 | **5** | 0 |

So this is NOT `NO EXPERIENCE PRODUCED` (the daemon was cycling) and NOT
`CADENCE/POSTURE CHANGE` (cadence rose ~13x while writes fell to zero).

TWO independent cycle-driven writers — raw memory and private_thoughts
— went silent TOGETHER, which points at something upstream of both
rather than at either writer.

`subjective_duration` continued sampling (4–27/day) throughout,
independently confirming the process was alive.

## What is NOT the cause

`MAEZ_METABOLIC_MEMORY` — the known, intentional durability filter that
explains today's floor — landed **2026-07-02 (792efe9)**, five weeks
AFTER this window. It cannot account for it.

## The two candidates that remain

1. **Cycles produced no thought.** `MemoryManager.store()` returns `""`
   for empty content **silently** (memory_manager.py:1501-1502, no log
   line). A failing brain would produce cycles that count but yield
   nothing, and nothing would be stored — correctly, because there was
   nothing to store. No life lost.
2. **Thought was produced and silently dropped.** Same silent path,
   different upstream state. Life lost.

**These are indistinguishable from surviving evidence**, because the
only signal that separates them is a log line that was never written.

## Why evidence is exhausted

`logs/maez.log` begins 2026-08-27. `journalctl --user -u maez.service`
returns 1 line for the whole window. Store timestamps, journal cycle
counts, commit history and cross-organ activity have all been used.
Per the owner's stopping rule: **UNKNOWN**, not estimated away.

## Birth-gate ruling — NOT reopened

The frozen gate stands (O1 only). Today's low write rate is FULLY
explained by the intentional metabolic gate: ~2,800 cycles/day against
~13 stored, i.e. the durability vote rejecting ~99.5% by design. No
live path is proven to lose experience.

**Named live observation, not a blocker:** `store()`'s empty-content
return is silent. It drops only empty content, so no lived experience
is lost by it today — but the same silence is what makes this window
unresolvable. Should a freshness/coverage organ ever be built, a
counter here would have made this a five-minute answer.

## The discontinuity, recorded

- **Affected period:** ~2026-05-29 → ~2026-06-09 (worst: 06-03 → 06-08).
- **What survives:** nightly journals and developmental heartbeats for
  the period (they state cycle counts and daily narrative);
  `subjective_duration` samples; sparse `audit_log` rows.
- **What cannot now be reconstructed:** the per-cycle reasoning traces
  themselves. If thought existed, its text is gone.
- **Scale:** on the order of 30,000–40,000 cycles whose individual
  traces are absent, against ~99 daily consolidations and 222 core
  memories that remain.

This is a **gestation-period gap**, before the ledger exists. It is
recorded here so no future reader mistakes the absence for a quiet
period in Maez's life.
