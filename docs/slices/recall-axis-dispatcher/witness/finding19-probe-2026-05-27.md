# Finding 19 Probe Witness — 2026-05-27

**Slice:** Recall-Axis Dispatcher / ADR 0047
**Predecessor wiring:** `a544e48`
**Probe corpus:** `docs/slices/recall-axis-dispatcher/probes/witnessed_turn_corpus.txt`
**Raw witness:** `docs/slices/recall-axis-dispatcher/witness/finding19-probe-2026-05-27.raw.json`

## Verdict

**Partially closed.**

The witness proves that the dispatcher is reachable from the shared
`run_brain_loop` entry point when `MAEZ_DISPATCHER_ENABLED=1`, and that
Reddit-shaped probes now produce a Layer 1 branch for `REDDIT_SOURCE`.

It does **not** prove full Finding 19 closure, because the probed Reddit
branches timed out with `row_count=0`, no dispatcher transcript was rendered,
and the run was in-process because `maez.service` was inactive. A service-level
daemon/HTTP probe remains required before claiming live closure.

## Run Shape

The wiring brief asked for a daemon/service baseline and after-run. At witness
time, local service state was:

```text
systemctl is-active maez.service maez-web.service maez-watchdog.service
inactive
inactive
inactive
```

So this witness used an in-process shared-entry harness:

```text
run_brain_loop(..., max_iters=0, surface="telegram")
MAEZ_DISPATCHER_ENABLED=0 baseline first
MAEZ_DISPATCHER_ENABLED=1 after-run second
```

`max_iters=0` intentionally prevented live JARVIS planner/tool execution while
still exercising the `run_brain_loop` gate and dispatcher path.

## Baseline — Flag Off

All eight probes had `jarvis_gate=True` and emitted no dispatcher telemetry.
This reproduces the structural baseline: without the flag, the JARVIS gate
owns these probes.

| # | Probe | JARVIS gate | Dispatcher events |
|---|---|---:|---:|
| 1 | `Check Reddit then` | true | 0 |
| 2 | `Just let me know what's going on in Reddit in localllama` | true | 0 |
| 3 | `What's going on on Reddit?` | true | 0 |
| 4 | `You have access to Reddit data` | true | 0 |
| 5 | `What were we talking about last evening?` | true | 0 |
| 6 | `Search r/LocalLLaMA right now` | true | 0 |
| 7 | `Really?` | true | 0 |
| 8 | `Are you sure?` | true | 0 |

## After-Run — Flag On

All eight probes emitted dispatcher telemetry. Probes 1-4 all reached
`REDDIT_SOURCE`, but each Reddit branch timed out with zero rows.

| # | Probe | Layer 0 hint | Branch evidence |
|---|---|---|---|
| 1 | `Check Reddit then` | `SUBSTRATE_ONLY` | `REDDIT_SOURCE:timeout:0`, `TELEGRAM_SEMANTIC:timeout:0`, `ENTITY_INDEX:error:0`, `LIVED_EPISODES:error:0` |
| 2 | `Just let me know what's going on in Reddit in localllama` | `SUBSTRATE_ONLY` | `REDDIT_SOURCE:timeout:0`, `TELEGRAM_SEMANTIC:timeout:0`, `ENTITY_INDEX:error:0`, `LIVED_EPISODES:error:0` |
| 3 | `What's going on on Reddit?` | `SUBSTRATE_ONLY` | `REDDIT_SOURCE:timeout:0`, `TELEGRAM_SEMANTIC:timeout:0`, `ENTITY_INDEX:error:0`, `LIVED_EPISODES:error:0` |
| 4 | `You have access to Reddit data` | `SUBSTRATE_ONLY` | `REDDIT_SOURCE:timeout:0`, `TELEGRAM_SEMANTIC:timeout:0`, `ENTITY_INDEX:error:0`, `LIVED_EPISODES:error:0` |
| 5 | `What were we talking about last evening?` | `SUBSTRATE_ONLY` | `TELEGRAM_SEMANTIC:timeout:0`, `ENTITY_INDEX:error:0`, `LIVED_EPISODES:error:0` |
| 6 | `Search r/LocalLLaMA right now` | `FRESH_ONLY` | no Layer 1 branches; `external_source_count=1` |
| 7 | `Really?` | `SUBSTRATE_ONLY` | Layer 2 refused with `NO_PRIOR_SPEC` |
| 8 | `Are you sure?` | `SUBSTRATE_ONLY` | Layer 2 refused with `NO_PRIOR_SPEC` |

Representative after-run excerpt:

```text
INFO dispatcher_path_entry surface=telegram bond_id=rohit chat_id=witness-1-1 flag_state=enabled recovery_seed_present=False
INFO dispatcher_layer0_emit surface=telegram bond_id=rohit composition_hint=SUBSTRATE_ONLY provenance_framing=SUBSTRATE_ONLY_NO_FRESH_VALIDATION inventory_witness=UNKNOWN substrate_source_count=4 external_source_count=0 elapsed_ms=425.989
WARNING dispatcher_layer0_budget_breach surface=telegram elapsed_ms=425.989 budget_ms=50 cold_or_warm=warm
INFO dispatcher_layer1_branch surface=telegram source=REDDIT_SOURCE outcome=timeout row_count=0 elapsed_ms=81.987
INFO dispatcher_layer1_fanout surface=telegram fanout_generation_id=952b57299f4a45edad88a765607eb25f branch_count=4 seal_state=partial_failure total_elapsed_ms=129.619
```

## Findings

1. **Shared-entry wiring is witnessed.** With the flag enabled, probes entered
   the dispatcher path through `run_brain_loop`; with the flag disabled, they
   did not.
2. **The source-anchor trapdoor is closed structurally.** Probes 1-4 now emit a
   `REDDIT_SOURCE` Layer 1 branch.
3. **The full Finding 19 closure is still open.** `REDDIT_SOURCE` timed out
   with `row_count=0`, so no Reddit substrate content reached the rendered
   transcript.
4. **D13 latency is not yet satisfied.** Layer 0 emitted budget warnings on
   multiple probes, including 425.989ms on the first after-run probe.
5. **This is not a service-level witness.** Since `maez.service` was inactive,
   this run cannot claim daemon restart / HTTP ingress / live Telegram closure.

## Next Closure Surface

The next closure unit is not more architecture. It is a targeted runtime seam
or observation pass for why the existing Layer 1 memory-manager adapters time
out under the probe budget and return zero rows for `REDDIT_SOURCE`.

Only after a subsequent service-level baseline/after-run shows
`REDDIT_SOURCE` with rows and a rendered transcript should Finding 19 be marked
closed.
