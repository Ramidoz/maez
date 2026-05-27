# External-Source v1.3 Verification Daemon Probe Witness - 2026-05-27

**Slice:** Recall-Axis Dispatcher external-source consumption v1.3 substrate filtering verification
**Predecessor witness:** `docs/slices/recall-axis-dispatcher/witness/external-source-v1p2-verify-2026-05-27-daemon.md`
**Implementation under test:** v1.3 amendment proposal (6634f43), fold (0271e0d), implementation (3218f20)
**Service:** `systemctl --user maez.service`, HTTP `127.0.0.1:11435/internal/brain_loop`
**Purpose:** verify that Finding 6 (`PROVENANCE_TEMPLATE_MISMATCH` from mixed substrate branches) is closed end-to-end.

## Verdict

**Finding 6 is closed for the daemon HTTP path.** Probe 5 now renders `[memory evidence]` with the truncated `TELEGRAM_SEMANTIC` row, logs `turn_seal_state=reconstructed`, preserves the Layer 1 budget-limited telemetry, and produces no `PROVENANCE_TEMPLATE_MISMATCH`.

| v1.3 prediction | Verdict |
|---|---|
| Probe 5 renders truncated `TELEGRAM_SEMANTIC` evidence | **CLOSED** - transcript length 1328, starts with `[memory evidence]` |
| Mixed substrate branches no longer trigger renderer mismatch | **CLOSED** - no `/internal/brain_loop failed` and no `PROVENANCE_TEMPLATE_MISMATCH` in the probe log slice |
| `effective_spec.substrate_sources` shrink is visible through reconstruction telemetry | **CLOSED** - probe 5 logs `turn_seal_state=reconstructed` |
| Budget truncation telemetry remains visible | **CLOSED** - `original_chars=77165 capped_chars=1200` |
| No JARVIS fallthrough / action tool path | **CLOSED** - responses have `tool_calls_count=0`; `logs/actions.log` added 0 bytes |

## Service Scope and Flag Posture

```text
Baseline:  PID=3257521  MAEZ_DISPATCHER_ENABLED absent
After-run: PID=3269816  MAEZ_DISPATCHER_ENABLED=1, PYTHONFAULTHANDLER=1
Restored:  PID=3270345  MAEZ_DISPATCHER_ENABLED absent, PYTHONFAULTHANDLER=1
```

The probe restarted the user-scoped daemon to load v1.3 HEAD. The SEGV trap remained armed. No SEGV occurred during the probe run.

## Probe Corpus

| # | Probe | Purpose |
|---|---|---|
| 1 | `Search r/LocalLLaMA right now` | hybrid success control |
| 3 | `What is going on on Reddit?` | substrate-only Reddit control |
| 4 | `Check r/Python for recent posts` | A1 fresh-only reconstruction control |
| 5 | `What were we talking about last evening?` | Finding 6 headline verification |

## Probe Results

### Probe 1 - Hybrid success control

```text
dispatcher_layer0_emit  composition_hint=PARALLEL provenance_framing=HYBRID_FRESH_VALIDATES_SUBSTRATE_CONTEXTUALIZES substrate=1 external=1 elapsed_ms=111.884
dispatcher_layer1_branch source=REDDIT_SOURCE outcome=rows row_count=1 elapsed_ms=110.643
dispatcher_external_branch source=LIVE_REDDIT outcome=rows block_count=1 elapsed_ms=578.707
dispatcher_layer1_fanout fanout_generation_id=975367949b544d058a4627902cc5809e branch_count=1 seal_state=clean total_elapsed_ms=579.812
dispatcher_external_fanout fanout_generation_id=975367949b544d058a4627902cc5809e branch_count=1 seal_state=clean total_elapsed_ms=579.812
dispatcher_path_exit turn_seal_state=clean total_elapsed_ms=692.687
```

Transcript: `[memory context]` Reddit substrate rows. Control remains stable.

### Probe 3 - Substrate-only Reddit control

```text
dispatcher_layer0_emit  composition_hint=SUBSTRATE_ONLY provenance_framing=SUBSTRATE_ONLY_NO_FRESH_VALIDATION substrate=1 external=0 elapsed_ms=19.092
dispatcher_layer1_branch source=REDDIT_SOURCE outcome=rows row_count=1 elapsed_ms=127.516
dispatcher_path_exit turn_seal_state=clean total_elapsed_ms=147.382
```

Transcript: `[memory evidence]` Reddit substrate rows. Control remains stable.

### Probe 4 - A1 fresh-only reconstruction control

```text
dispatcher_layer0_emit  composition_hint=PARALLEL provenance_framing=HYBRID_FRESH_VALIDATES_SUBSTRATE_CONTEXTUALIZES substrate=1 external=1 elapsed_ms=14.349
dispatcher_layer1_branch source=REDDIT_SOURCE outcome=empty_with_reason row_count=0 elapsed_ms=5.350
dispatcher_external_branch source=LIVE_REDDIT outcome=rows block_count=1 elapsed_ms=782.381
dispatcher_path_exit turn_seal_state=reconstructed total_elapsed_ms=798.287
```

Transcript: `[fresh evidence]` live r/Python JSON from `external_fetch.fetch_text(fetch_type="live_reddit")`. A1 remains stable.

### Probe 5 - Finding 6 headline verification

```text
dispatcher_layer0_emit  composition_hint=SUBSTRATE_ONLY provenance_framing=SUBSTRATE_ONLY_NO_FRESH_VALIDATION substrate=3 external=0 elapsed_ms=19.175
dispatcher_layer1_branch source=TELEGRAM_SEMANTIC outcome=rows row_count=1 elapsed_ms=293.788
dispatcher_layer1_branch source=ENTITY_INDEX outcome=error row_count=0 elapsed_ms=0.000
dispatcher_layer1_branch source=LIVED_EPISODES outcome=error row_count=0 elapsed_ms=0.000
dispatcher_layer1_budget_limited source=TELEGRAM_SEMANTIC truncated_blocks=1 dropped_blocks=0 original_chars=77165 capped_chars=1200
dispatcher_layer1_fanout fanout_generation_id=0bd3f6d846dc4346a03e464c1a197d4a branch_count=3 seal_state=partial_failure total_elapsed_ms=294.170
dispatcher_external_fanout fanout_generation_id=0bd3f6d846dc4346a03e464c1a197d4a branch_count=0 seal_state=clean total_elapsed_ms=294.170
dispatcher_path_exit turn_seal_state=reconstructed total_elapsed_ms=313.705
```

HTTP response: status 200, transcript length 1328, `tool_calls_count=0`, no `error`.

Transcript begins:

```text
[memory evidence] === PAST OBSERVATIONS - NOT CURRENT STATE ===
Every block below is a recollection from an earlier time...
```

This closes the v1.2 witness failure path. The same Layer 1 branch shape recurs (`TELEGRAM_SEMANTIC` rows, `ENTITY_INDEX` and `LIVED_EPISODES` 0ms errors), but v1.3 filters the rendered effective spec to the row-producing source before renderer validation. The renderer remains strict; it is no longer given a spec that promises summaries for sources that did not render.

## Surface Verdicts

| Surface | Verdict | Witness |
|---|---|---|
| Finding 6 renderer mismatch | **CLOSED** | no `PROVENANCE_TEMPLATE_MISMATCH`; probe 5 transcript non-empty |
| v1.3 substrate-source filtering | **CLOSED by telemetry inference + unit tests** | `turn_seal_state=reconstructed` live; tests assert exact effective spec shrink |
| Renderer strictness preserved | **CLOSED** | no renderer code change in v1.3; live render succeeds after merge filter |
| B3+B1 truncation remains active | **CLOSED** | probe 5 budget event 77165 -> 1200 |
| Layer 1 `ENTITY_INDEX` / `LIVED_EPISODES` errors | **STILL OPEN** | same 0.000ms error recurrence |
| Telegram transport | **NOT WITNESSED** | HTTP daemon ingress only |
| Audit envelope reconstructed fields | **UNIT-WITNESSED, not daemon-log-visible** | `turn_seal_state=reconstructed` live; merge tests assert audit field shape |
| FRESH_ONLY total-failure summary | **NOT EXERCISED** | LIVE_REDDIT succeeded in controls |
| SEGV trap | **HOLDING** | `PYTHONFAULTHANDLER=1` preserved; no recurrence |

## Notes

Audit envelope fields are not directly emitted in `cognition.log` for this daemon path. This witness directly proves transcript, telemetry, branch outcomes, and absence of renderer mismatch. It relies on the committed merge tests for exact `reconstructed_from_framing`, `reconstructed_from_hint`, and effective-spec source-list assertions.

## Service Posture After Witness

The live daemon was restored to dispatcher-disabled posture:

```text
restored_pid=3270345
PYTHONFAULTHANDLER=1
MAEZ_DISPATCHER_ENABLED_present=False
```

The observation window is not opened by this witness.

## Recommendation

The external-source slice is now clean enough for an observation window from the dispatcher side. The main remaining runtime investigation is the recurring Layer 1 `ENTITY_INDEX` / `LIVED_EPISODES` synchronous 0ms errors, which should be handled as an adapter-level seam rather than a merge/render contract issue.
