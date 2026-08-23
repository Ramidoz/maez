# T3 witness run — T4 then T3, airlocked, digest-bound

2026-08-23, judged at `f8a7a04a140029507bad1aa72d995077b26cd0df` (working tree clean; the one uncommitted
edit at run time was the airlock skip-deferral in test_s1_census.py,
committed with this report).

## Order and outcomes (protocol §5, gate 21/22 sequencing)

1. **T4** — `python3 -m core.memory.s1_census --repo . --expected
   theme2-s1-census.json`, inside the airlock:
   **census CLEAN — 66 constructs**, exit 0.
2. **T3** — the map-join suite, the census suite (host-only seeded
   control deferring to its clone-based twin, which ran), and the
   consumer-refusal harness, inside the airlock:
   **31 passed, 1 skipped (deferred, covered), 38 subtests**, exit 0.

## What T3 witnesses at this commit

- 14 stampers driven through their PUBLIC entries against REAL sinks —
  disposable Chroma, real private_thoughts/audit SQLite, real ledger
  rows, the real spine. Healthy: every stamper's stamp read back
  `gestation` from its own store. Broken + enabled: typed refusal,
  sink flat, at every site.
- Per-site bites at all 13 sqlite/chroma sites (a lying resolver's
  stamp must land AND be seen), the ledger writer's inverse bite, the
  span planner's vanishing-refusal bite, and predicate-isolated bites
  for the layered private_thoughts guards (each layer witnessed
  load-bearing with the other neutralized).
- The readers behaviourally, the `benchmark` exemption dynamically, and
  §10's NULL normalization on reopen.
- Census→map joined in BOTH directions for writers AND readers; a
  deleted row or an unmapped construct fails by name.

## Evidence digests

| artifact | sha256 |
|---|---|
| theme2-s1-census.json | `5c444463583d06c90b35d396d93ba876851aa216bc31776381402e80f707e3f2` |
| theme2-s1-t3-map.json | `e84f7eea44a3264de2b345025afe4cc1ac5bfbb1411c6568cd8edb6343ace4fc` |
| tests/test_t3_consumer_refusal.py | `8b4bbd8e2178e7690aacfcd5b97d79d4523bba31239dc8bc41c2c4158d51e5d7` |
| tests/test_t3_map_join.py | `0a8b49dbccf0f35f15fee59c0e9e3408f00f7033c4cb09326d0e678390e894f3` |
| tests/test_s1_census.py | `fe4ff1d401bb9d7a57fee79c7303026327650a20be604babf0a3183cb53c5f14` |

## Honest scope

Not witnessed here: the latch and every latch-dependent T1/T2 cell
(§12.13, blocked pending the O-1 topology amendment into T2), and T6's
nine mutations as a RETAINED artifact (executed and all-flipping during
the gate-20 closure; a retained re-execution belongs to the final S1
evidence report). The airlock ran the frozen system SQLite 3.46.1, as
the fixtures and baseline assume; the vendor 3.53.4 runs in production
units only.
