# Idle Heartbeat Body-State Window v0 — Task 0 Window Table

Date: 2026-06-28
Status: OWNER SIGN-OFF PENDING
Plan: `docs/superpowers/plans/2026-06-28-idle-heartbeat-world-window-v0.md`
Spec: `docs/superpowers/specs/2026-06-28-idle-heartbeat-world-window-v0-design.md`

## Task 0 Finding

The live `core.perception.snapshot()` surface is thinner than the plan examples.
It currently exposes Maez's machine-body/system/runtime state only:

- `timestamp`, `day_of_week`, `hour`, `time_of_day`
- `cpu`, `ram`, `gpu`, `disk`, `network`
- `top_processes_cpu`, `top_processes_mem`

It does **not** currently expose desk presence, git state, screen perception, or
screen text. Those fields must not be invented in this slice.

Interpretation guard: this signed table is a body/self-state sense, not a full
owner-world sense. If this slice witnesses quiet, the correct conclusion is
"machine-body signal alone was thin," not "world-signal failed." The owner-world
arc (presence/screen/git/work context/vision/Jetson/connectors) is separate and
unbuilt here.

Implementation seam correction: `core.perception` is a shim to
`core.memory.perception`. The legitimate production touch set for this slice is:

- `core/cognition/world_window.py` (new)
- `core/cognition/lean_idle_heartbeat.py`
- `daemon/maez_daemon.py`

The sequencing guard remains: no `core/evolution/` changes and no
`drive_driven_curiosity` touch.

## Baseline Cache

Prior projected signatures should be stored at:

`~/.local/state/maez/world_window_signatures.json`

This is a transient runtime cache, not Maez memory and not welfare evidence. It
may contain only projected signatures: hashes, buckets, booleans, and labels.
It must not contain raw snapshot values, private thoughts, salience, wants,
soul, lived memory, or action state.

If the cache is missing, the window performs a clean cold start: record the
current projected signatures and emit zero deltas. With
`MAEZ_WORLD_WINDOW_SHADOW` off, the cache must not be created.

## Owner-Readable Approved Window

Classes:

- `safe_delta`: allowed as a content-light body-state change fact.
- `sensitive_delta`: allowed only as a coarser shadow/label; provenance and
  sensitivity must be attached.
- `raw_private`: never enters the prompt.
- `unavailable`: not approved for this window in v0, either because it is absent
  or already represented by another heartbeat fact.

Projection rule: v0 shows shadows and labels only, never the room.

| field | class | projection | signature | prompt phrase | exclusion receipt |
|---|---|---|---|---|---|
| `timestamp` | `unavailable` | none | none | none | `excluded: duplicate_time_nerve_clock_tick` |
| `day_of_week` | `unavailable` | none | none | none | `excluded: duplicate_time_nerve` |
| `hour` | `unavailable` | none | none | none | `excluded: duplicate_time_nerve_clock_tick` |
| `time_of_day` | `unavailable` | none | none | none | `excluded: duplicate_time_nerve` |
| `cpu` | `safe_delta` | shadow: coarse load band + coarse thermal band + core-count-known label | `cpu:{load_band}:{thermal_band}:{core_count_known}` | `cpu load or temperature band changed` | raw `percent`, `per_core`, `freq_mhz`, and exact temperature omitted by projection |
| `ram` | `safe_delta` | shadow: coarse memory-use band | `ram:{usage_band}` | `memory-use band changed` | raw GB values and exact percent omitted by projection |
| `gpu` | `safe_delta` | label/shadow: available/unavailable + coarse utilization/memory/thermal bands when present | `gpu:{available}:{util_band}:{memory_band}:{thermal_band}` | `gpu availability or load band changed` | raw GPU utilization, memory MB, and exact temperature omitted by projection |
| `disk` | `safe_delta` | shadow: per-approved-mount pressure bands for `/` and `/home` | `disk:{root_band}:{home_band}` | `disk-use band changed` | raw sizes and exact percents omitted by projection |
| `network` | `sensitive_delta` | shadow: coarse send/receive activity bands from current rates only | `network:{send_band}:{recv_band}` | `network-activity band changed` | cumulative byte totals and exact rates omitted by projection |
| `top_processes_cpu` | `sensitive_delta` | shadow: salted/content-light hash of sorted top process names; no names shown | `top_processes_cpu:{set_hash}` | `active process set changed` | process names, pids, cpu percentages, and memory percentages omitted by projection |
| `top_processes_mem` | `sensitive_delta` | shadow: salted/content-light hash of sorted memory-heavy process names; no names shown | `top_processes_mem:{set_hash}` | `memory-heavy process set changed` | process names, pids, cpu percentages, and memory percentages omitted by projection |

## Notes For Implementation

- The prompt may show field/provenance/sensitivity labels and the neutral prompt
  phrase. It must never show the signature hash itself unless the owner
  explicitly approves that later; hashes are for comparison and receipts.
- Allowed fields still omit raw subfields by projection. This is not silent
  leakage; the omission is part of the signed projection table above.
- Time fields are excluded from the body-state window because the heartbeat already
  carries felt-time facts. Including wall-clock fields here would rebuild the
  clock-tick flood under a second name.
- `top_processes_*` are sensitive because process names can reveal private
  activity. v0 may use them only as change shadows, never as visible names.
- `network` is sensitive because activity level can reveal owner/device
  behavior. v0 may use only coarse activity bands.

## Owner Sign-Off Question

Approve this window table as the v0 boundary?

If yes, implementation may proceed under the plan's tests. If no, edit the
field classifications/projections before any production code is written.
