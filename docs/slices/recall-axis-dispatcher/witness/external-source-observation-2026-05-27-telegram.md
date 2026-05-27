# External-Source Observation Window - Telegram - 2026-05-27

**Slice:** Recall-Axis Dispatcher external-source consumption, post-v1.3 observation
**Git HEAD at flip:** `fd21828` (`fix(dispatcher): reserve unimplemented fallback sources`)
**Service:** `systemctl --user maez.service`, Telegram adapter surface
**Window opened:** 2026-05-27T17:12:00-05:00
**Window closed:** 2026-05-27T17:30:23-05:00 log end captured before flag restore
**Purpose:** observe real Telegram traffic under `MAEZ_DISPATCHER_ENABLED=1` after v1.3 and Finding-7 reclassification.

## Verdict

**Partially clean, with two new observation findings.** Telegram did enter the dispatcher path for all observed owner turns. The v1.3 renderer mismatch stayed closed. B3 budget truncation fired repeatedly and preserved renderable substrate evidence. But the observation surfaced two live gaps:

1. `fd21828` did not affect the live brain-loop inventory path: `ENTITY_INDEX` and `LIVED_EPISODES` still logged as Layer 1 `outcome=error`, because `core.brain.brain_loop._dispatcher_inventory_summary()` hardcodes all sources as `EXECUTABLE_UNKNOWN` instead of consuming the dispatcher inventory registry.
2. A fresh-looking Telegram turn triggered legacy `Web search` log lines after `dispatcher_path_exit`, even though the dispatcher external fan-out had `branch_count=0` and `actions.log` added 0 bytes.

## Window Boundaries

```text
maez.log start byte:    50368956
maez.log end byte:      50533207
maez.log delta bytes:     164371

actions.log start byte:  5803828
actions.log end byte:    5803828
actions.log delta bytes:       0
```

## Service Posture

```text
Observation PID: 3291912
Observation env: MAEZ_DISPATCHER_ENABLED=1, PYTHONFAULTHANDLER=1

Restored PID: 3300597
Restored env: MAEZ_DISPATCHER_ENABLED absent, PYTHONFAULTHANDLER=1
```

The flag was restored to absent after the delta capture. The SEGV trap remained armed. No SEGV or fatal Python error appeared in the observation delta.

## Aggregate Telemetry

| Signal | Count |
|---|---:|
| `dispatcher_path_entry` | 10 |
| `dispatcher_path_exit` | 10 |
| `dispatcher_external_branch` | 0 |
| `dispatcher_external_fanout` | 10 |
| `dispatcher_layer1_budget_limited` | 7 |
| `PROVENANCE_TEMPLATE_MISMATCH` | 0 |
| `actions.log` bytes added | 0 |
| SEGV / fatal Python error | 0 |

### `turn_seal_state`

| State | Count |
|---|---:|
| `clean` | 3 |
| `reconstructed` | 7 |

### Layer 0 Source Counts

| Shape | Count |
|---|---:|
| `substrate_source_count=3 external_source_count=0` | 7 |
| `substrate_source_count=1 external_source_count=0` | 3 |

No observed Telegram turn emitted external sources through Layer 0. Therefore this window did not exercise `LIVE_REDDIT` through `ExternalFanout` on Telegram.

### Layer 1 Branch Outcomes

| Source | Outcome | Count |
|---|---|---:|
| `TELEGRAM_SEMANTIC` | `rows` | 7 |
| `ENTITY_INDEX` | `error` | 7 |
| `LIVED_EPISODES` | `error` | 7 |
| `REDDIT_SOURCE` | `rows` | 3 |

### External Fan-Out

All 10 turns logged:

```text
dispatcher_external_fanout ... branch_count=0 seal_state=clean
```

The shared `fanout_generation_id` appeared on Layer 1 and external fan-out events for each turn, but external branch count was always zero.

## Representative Lines

### Dispatcher entered Telegram adapter path

```text
dispatcher_path_entry surface=adapter bond_id=rohit chat_id=6727062247 flag_state=enabled recovery_seed_present=False
dispatcher_path_exit surface=adapter bond_id=rohit chat_id=6727062247 path_taken=dispatcher turn_seal_state=reconstructed total_elapsed_ms=549.663
```

This closes the transport-level caveat that HTTP-only daemon witnesses could not prove: Telegram does reach `run_brain_loop` with the dispatcher flag enabled.

### B3 budget truncation active in real traffic

```text
dispatcher_layer1_budget_limited surface=adapter source=TELEGRAM_SEMANTIC truncated_blocks=1 dropped_blocks=0 original_chars=78121 capped_chars=1200
```

The B3+B1 fix is live on Telegram traffic. Large `TELEGRAM_SEMANTIC` rows are truncated and preserved rather than silently dropped.

### Finding 7 reclassification did not reach live brain-loop inventory

```text
dispatcher_layer1_branch surface=adapter source=ENTITY_INDEX outcome=error row_count=0 elapsed_ms=0.000
dispatcher_layer1_branch surface=adapter source=LIVED_EPISODES outcome=error row_count=0 elapsed_ms=0.000
```

This should have shifted to `reserved_skip` after `fd21828`, but it did not. The reason is now concrete: `brain_loop._dispatcher_inventory_summary()` builds an inline `InventorySummary` with every `SubstrateSource` marked `EXECUTABLE_UNKNOWN`, bypassing `InventoryRegistry.summarize()` and therefore bypassing the new `RESERVED_SOURCES` short-circuit.

### Legacy web search log after dispatcher exit

```text
dispatcher_path_exit surface=adapter ... path_taken=dispatcher turn_seal_state=clean total_elapsed_ms=35.515
telegram_surface message: Check r/LocalLLaMA right now for recent local LLM posts, and separate fresh evidence from memory con
Web search triggered for: Check r/LocalLLaMA right now for recent local LLM posts, and separate fresh evid
Web search: 0 results for 'Check r/LocalLLaMA right now for recent local LLM posts, and separate fresh evidence from memory context.'
```

`actions.log` added 0 bytes, so this is not the prior action-log JARVIS fallthrough shape. It is still a live Telegram-path gap: a legacy web-search path can run after dispatcher exit while `ExternalFanout` reports `branch_count=0`.

## Surface Verdicts

| Surface | Verdict | Witness |
|---|---|---|
| Telegram enters dispatcher path | **CLOSED** | 10 `dispatcher_path_entry surface=adapter` events |
| Dispatcher path returns on Telegram | **CLOSED** | 10 `dispatcher_path_exit path_taken=dispatcher` events |
| Shared seal on Telegram | **CLOSED** | matching Layer 1 / external fanout IDs per turn |
| v1.3 renderer mismatch | **CLOSED in observation** | 0 `PROVENANCE_TEMPLATE_MISMATCH` |
| B3 budget truncation | **CLOSED in observation** | 7 `dispatcher_layer1_budget_limited` events |
| No action-log JARVIS fallthrough | **CLOSED by actions.log** | actions delta 0 bytes |
| No legacy web-search side path | **OPEN** | `Web search triggered` lines after dispatcher exit |
| Telegram `LIVE_REDDIT` external fan-out | **NOT WITNESSED** | 0 `dispatcher_external_branch`; external branch count always 0 |
| Finding 7 reserved reclassification live | **STILL OPEN** | `ENTITY_INDEX` / `LIVED_EPISODES` still `outcome=error` |
| SEGV trap | **HOLDING** | `PYTHONFAULTHANDLER=1`; no fatal error in delta |

## Findings

### Finding 8 - Brain-loop inventory bypasses `InventoryRegistry`

`fd21828` correctly made `InventoryRegistry.summarize()` treat `ENTITY_INDEX` and `LIVED_EPISODES` as globally reserved. The live daemon path did not observe that reclassification because `core.brain.brain_loop._dispatcher_inventory_summary()` constructs a hardcoded summary:

```text
SubstrateSource -> EXECUTABLE_UNKNOWN
ExternalSource -> EXECUTABLE_UNKNOWN
availability_limitations -> INVENTORY_UNKNOWN
```

Layer 1 therefore still sees `ENTITY_INDEX` and `LIVED_EPISODES` as executable-unknown, falls through to the missing-adapter branch, and logs `outcome=error`.

**Recommended next patch:** replace or route `_dispatcher_inventory_summary()` through `InventoryRegistry().summarize(...)` so the registry is the single inventory authority. RED should assert the live brain-loop summary marks `ENTITY_INDEX` and `LIVED_EPISODES` as `RESERVED_UNAVAILABLE`.

### Finding 9 - Telegram legacy web-search side path can fire after dispatcher exit

For the r/LocalLLaMA prompt, the dispatcher completed with:

```text
substrate_source_count=1 external_source_count=0
dispatcher_external_fanout branch_count=0
dispatcher_path_exit path_taken=dispatcher
```

Immediately afterward, `maez.log` recorded legacy `Web search triggered` / `Web search: 0 results` lines. This did not add `actions.log` bytes, so it is not the same action-log fallthrough previously tested. It is still outside the external-source dispatcher path and should be classified before observation continues.

Two likely contributing facts:

- The prompt included both a subreddit anchor and "memory context"; Layer 0's current `live_reddit_anchor and not explicit_memory` condition suppresses `LIVE_REDDIT` when explicit memory wording is present.
- Telegram has a separate web-search trigger path downstream of dispatcher return.

**Recommended next diagnostic:** trace the Telegram post-dispatch tool loop and decide whether dispatcher-enabled `RenderedTurn` should suppress that legacy web-search trigger, or whether the trigger should be folded into the dispatcher external-source path.

## Recommendation

Do not leave the dispatcher observation window open yet. The flag is restored to absent. Before a sustained observation window, close the two small but load-bearing live gaps:

1. **Inventory authority patch:** make brain-loop use the dispatcher inventory registry so Finding 7's reserved reclassification is actually live.
2. **Telegram post-dispatch web-search diagnostic:** explain and either disable or route the legacy web-search side path under dispatcher-enabled turns.

After those two surfaces are witnessed, reopen observation with a targeted Telegram probe that does **not** include explicit memory wording:

```text
Search r/LocalLLaMA right now.
```

That should exercise `LIVE_REDDIT` on Telegram directly if the Layer 0 selector and external fan-out are wired correctly.
