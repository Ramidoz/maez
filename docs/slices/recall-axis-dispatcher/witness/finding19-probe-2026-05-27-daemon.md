# Finding 19 Daemon-Level Probe Witness - 2026-05-27

**Slice:** Recall-Axis Dispatcher / ADR 0047  
**Predecessor adapter witness:** `docs/slices/recall-axis-dispatcher/witness/finding19-probe-2026-05-27-adapter-fix.md`  
**Probe corpus:** `docs/slices/recall-axis-dispatcher/probes/witnessed_turn_corpus.txt`  
**Raw witness:** `docs/slices/recall-axis-dispatcher/witness/finding19-probe-2026-05-27-daemon.raw.json`

## Verdict

**Closed for the daemon HTTP Reddit-substrate surface.**

The witness proves that the running user-scoped `maez.service` accepts the eight-probe corpus through the daemon HTTP `/internal/brain_loop` ingress, that `MAEZ_DISPATCHER_ENABLED=1` routes Reddit-shaped probes through the dispatcher, and that probes 1-4 return rendered Reddit substrate rows without `web_search` / `fetch_url` tool calls.

This closes the fifth Finding 19 surface for the daemon HTTP path. It does not separately prove the Telegram transport path, but the discovery brief established Telegram and HTTP converge on the same `run_brain_loop` entry point. It also does not close external-source consumption: probe 6 emitted `FRESH_ONLY` and returned no transcript in this run, so that remains part of the already-deferred external-source seam.

## Service Scope

The earlier inactive-service report was wrong-scope. This witness used the user-scoped service:

```text
systemctl --user maez.service
/internal/brain_loop on 127.0.0.1:11435
```

Flag posture:

```text
Baseline: MAEZ_DISPATCHER_ENABLED absent/unset in live process.
After:    MAEZ_DISPATCHER_ENABLED=1 set via systemctl --user set-environment, service restarted, env verified in /proc/<pid>/environ.
Restore:  MAEZ_DISPATCHER_ENABLED unset again, service restarted, env verified absent from /proc/<pid>/environ.
```

## Baseline - Flag Off

| # | Probe | Transcript length | Tool calls |
|---|---|---:|---|
| 1 | `Check Reddit then` | 0 | - |
| 2 | `Just let me know what's going on in Reddit in localllama` | 1788 | web_search, web_search, web_search, web_search |
| 3 | `What's going on on Reddit?` | 1616 | web_search, web_search, fetch_url, fetch_url |
| 4 | `You have access to Reddit data` | 0 | - |
| 5 | `What were we talking about last evening?` | 0 | - |
| 6 | `Search r/LocalLLaMA right now` | 2377 | web_search, fetch_url |
| 7 | `Really?` | 0 | - |
| 8 | `Are you sure?` | 0 | - |

Baseline had zero dispatcher telemetry in `cognition.log`. The JARVIS path did use external tools for Reddit-shaped probes:

```text
2026-05-27 13:21:38 | T0 | web_search | chat: Just let me know what's going on in Reddit in localllama | {"query": "Reddit localllama recent activity"} | OK: [WEB SEARCH: 'Reddit localllama recent activity'] No results found. | 0.37s
2026-05-27 13:21:40 | T0 | web_search | chat: Just let me know what's going on in Reddit in localllama | {"query": "Reddit localLLaMA community recent posts"} | OK: [WEB SEARCH: 'Reddit localLLaMA community recent posts'] No results found. | 0.33s
2026-05-27 13:21:42 | T0 | web_search | chat: Just let me know what's going on in Reddit in localllama | {"query": "site:reddit.com localLLaMA"} | OK: [WEB SEARCH: 'site:reddit.com localLLaMA'] No results found. | 0.53s
2026-05-27 13:21:43 | T0 | web_search | chat: Just let me know what's going on in Reddit in localllama | {"query": "Reddit local llama AI"} | OK: [WEB SEARCH: 'Reddit local llama AI'] No results found. | 0.37s
2026-05-27 13:21:46 | T0 | web_search | chat: What's going on on Reddit? | {"query": "what is trending on reddit today"} | OK: [WEB SEARCH: 'what is trending on reddit today'] No results found. | 0.39s
2026-05-27 13:22:03 | T0 | web_search | chat: What's going on on Reddit? | {"query": "reddit front page trending topics today"} | OK: [WEB SEARCH: 'reddit front page trending topics today'] No results found. | 0.34s
2026-05-27 13:22:05 | T0 | fetch_url | chat: What's going on on Reddit? | {} | OK: empty url | 0.01s
2026-05-27 13:22:06 | T0 | fetch_url | chat: What's going on on Reddit? | {} | OK: empty url | 0.01s
2026-05-27 13:22:14 | T0 | web_search | chat: Search r/LocalLLaMA right now | {"query": "r/LocalLLaMA reddit latest posts"} | OK: [WEB SEARCH: 'r/LocalLLaMA reddit latest posts'] No results found. | 0.35s
2026-05-27 13:22:16 | T0 | fetch_url | chat: Search r/LocalLLaMA right now | {"url": "https://old.reddit.com/r/LocalLLaMA/hot/.json", "reason": "fetch latest hot posts from r/LocalLLaMA via Reddit JSON API", "max_chars": 3000} | OK: {"kind": "Listing", "data": {"after": "t3_1to5fj5", "dist": 25, "modhash": "", "geo_filter": null, "children": [{"kind": "t3", "data": {"approved_at_utc": null, "subreddit": "LocalLLaMA", "selftext":  | 0.72s
```

## After-Run - Flag On

| # | Probe | Transcript length | Tool calls | Layer 0 | Branch evidence |
|---|---|---:|---|---|---|
| 1 | `Check Reddit then` | 850 | - | SUBSTRATE_ONLY; substrate_sources=1; external_sources=0; layer0=848.756ms | REDDIT_SOURCE:rows:1:209.332ms |
| 2 | `Just let me know what's going on in Reddit in localllama` | 856 | - | SUBSTRATE_ONLY; substrate_sources=1; external_sources=0; layer0=26.486ms | REDDIT_SOURCE:rows:1:23.484ms |
| 3 | `What's going on on Reddit?` | 850 | - | SUBSTRATE_ONLY; substrate_sources=1; external_sources=0; layer0=13.174ms | REDDIT_SOURCE:rows:1:119.701ms |
| 4 | `You have access to Reddit data` | 850 | - | SUBSTRATE_ONLY; substrate_sources=1; external_sources=0; layer0=12.577ms | REDDIT_SOURCE:rows:1:94.255ms |
| 5 | `What were we talking about last evening?` | 371 | - | SUBSTRATE_ONLY; substrate_sources=3; external_sources=0; layer0=14.141ms | TELEGRAM_SEMANTIC:rows:1:304.311ms, ENTITY_INDEX:error:0:0.000ms, LIVED_EPISODES:error:0:0.000ms |
| 6 | `Search r/LocalLLaMA right now` | 0 | - | FRESH_ONLY; substrate_sources=0; external_sources=1; layer0=17.949ms | no Layer 1 branches |
| 7 | `Really?` | 0 | - | SUBSTRATE_ONLY; substrate_sources=3; external_sources=0; layer0=16.438ms | Layer2Refusal:NO_PRIOR_SPEC |
| 8 | `Are you sure?` | 0 | - | SUBSTRATE_ONLY; substrate_sources=3; external_sources=0; layer0=12.858ms | Layer2Refusal:NO_PRIOR_SPEC |

Representative dispatcher telemetry from `logs/maez.log`:

```text
2026-05-27 13:22:58 [INFO] core.brain.brain_loop: dispatcher_path_entry surface=web bond_id=rohit chat_id=finding19-daemon-after-1 flag_state=enabled recovery_seed_present=False
2026-05-27 13:22:58 [INFO] core.brain.brain_loop: dispatcher_layer0_emit surface=web bond_id=rohit composition_hint=SUBSTRATE_ONLY provenance_framing=SUBSTRATE_ONLY_NO_FRESH_VALIDATION inventory_witness=UNKNOWN substrate_source_count=1 external_source_count=0 elapsed_ms=848.756
2026-05-27 13:22:58 [WARNING] core.brain.brain_loop: dispatcher_layer0_budget_breach surface=web elapsed_ms=848.756 budget_ms=50 cold_or_warm=warm
2026-05-27 13:22:58 [INFO] core.brain.brain_loop: dispatcher_layer2_repair surface=web bond_id=rohit result=unchanged refusal_reason=
2026-05-27 13:22:59 [INFO] core.brain.brain_loop: dispatcher_layer1_branch surface=web source=REDDIT_SOURCE outcome=rows row_count=1 elapsed_ms=209.332
2026-05-27 13:22:59 [INFO] core.brain.brain_loop: dispatcher_layer1_fanout surface=web fanout_generation_id=90f5224f7a3a423394eb01146a6593cc branch_count=1 seal_state=clean total_elapsed_ms=209.494
2026-05-27 13:22:59 [INFO] core.brain.brain_loop: dispatcher_path_exit surface=web bond_id=rohit chat_id=finding19-daemon-after-1 path_taken=dispatcher total_elapsed_ms=1059.586
2026-05-27 13:22:59 [INFO] core.brain.brain_loop: dispatcher_path_entry surface=web bond_id=rohit chat_id=finding19-daemon-after-2 flag_state=enabled recovery_seed_present=False
2026-05-27 13:22:59 [INFO] core.brain.brain_loop: dispatcher_layer0_emit surface=web bond_id=rohit composition_hint=SUBSTRATE_ONLY provenance_framing=SUBSTRATE_ONLY_NO_FRESH_VALIDATION inventory_witness=UNKNOWN substrate_source_count=1 external_source_count=0 elapsed_ms=26.486
2026-05-27 13:22:59 [INFO] core.brain.brain_loop: dispatcher_layer2_repair surface=web bond_id=rohit result=unchanged refusal_reason=
2026-05-27 13:22:59 [INFO] core.brain.brain_loop: dispatcher_layer1_branch surface=web source=REDDIT_SOURCE outcome=rows row_count=1 elapsed_ms=23.484
2026-05-27 13:22:59 [INFO] core.brain.brain_loop: dispatcher_layer1_fanout surface=web fanout_generation_id=0bdd2928f2c54dc8ac289e59a18bfbab branch_count=1 seal_state=clean total_elapsed_ms=23.655
2026-05-27 13:22:59 [INFO] core.brain.brain_loop: dispatcher_path_exit surface=web bond_id=rohit chat_id=finding19-daemon-after-2 path_taken=dispatcher total_elapsed_ms=50.453
2026-05-27 13:22:59 [INFO] core.brain.brain_loop: dispatcher_path_entry surface=web bond_id=rohit chat_id=finding19-daemon-after-3 flag_state=enabled recovery_seed_present=False
2026-05-27 13:22:59 [INFO] core.brain.brain_loop: dispatcher_layer0_emit surface=web bond_id=rohit composition_hint=SUBSTRATE_ONLY provenance_framing=SUBSTRATE_ONLY_NO_FRESH_VALIDATION inventory_witness=UNKNOWN substrate_source_count=1 external_source_count=0 elapsed_ms=13.174
2026-05-27 13:22:59 [INFO] core.brain.brain_loop: dispatcher_layer2_repair surface=web bond_id=rohit result=unchanged refusal_reason=
2026-05-27 13:22:59 [INFO] core.brain.brain_loop: dispatcher_layer1_branch surface=web source=REDDIT_SOURCE outcome=rows row_count=1 elapsed_ms=119.701
2026-05-27 13:22:59 [INFO] core.brain.brain_loop: dispatcher_layer1_fanout surface=web fanout_generation_id=f6310954e6d448d4b4a8327c6ec49de9 branch_count=1 seal_state=clean total_elapsed_ms=119.856
2026-05-27 13:22:59 [INFO] core.brain.brain_loop: dispatcher_path_exit surface=web bond_id=rohit chat_id=finding19-daemon-after-3 path_taken=dispatcher total_elapsed_ms=133.300
2026-05-27 13:22:59 [INFO] core.brain.brain_loop: dispatcher_path_entry surface=web bond_id=rohit chat_id=finding19-daemon-after-4 flag_state=enabled recovery_seed_present=False
2026-05-27 13:22:59 [INFO] core.brain.brain_loop: dispatcher_layer0_emit surface=web bond_id=rohit composition_hint=SUBSTRATE_ONLY provenance_framing=SUBSTRATE_ONLY_NO_FRESH_VALIDATION inventory_witness=UNKNOWN substrate_source_count=1 external_source_count=0 elapsed_ms=12.577
2026-05-27 13:22:59 [INFO] core.brain.brain_loop: dispatcher_layer2_repair surface=web bond_id=rohit result=unchanged refusal_reason=
2026-05-27 13:22:59 [INFO] core.brain.brain_loop: dispatcher_layer1_branch surface=web source=REDDIT_SOURCE outcome=rows row_count=1 elapsed_ms=94.255
2026-05-27 13:23:00 [INFO] core.brain.brain_loop: dispatcher_layer1_fanout surface=web fanout_generation_id=727b4b0887a44333898637aa196a387d branch_count=1 seal_state=clean total_elapsed_ms=94.417
2026-05-27 13:23:00 [INFO] core.brain.brain_loop: dispatcher_path_exit surface=web bond_id=rohit chat_id=finding19-daemon-after-4 path_taken=dispatcher total_elapsed_ms=107.273
2026-05-27 13:23:00 [INFO] core.brain.brain_loop: dispatcher_path_entry surface=web bond_id=rohit chat_id=finding19-daemon-after-5 flag_state=enabled recovery_seed_present=False
2026-05-27 13:23:00 [INFO] core.brain.brain_loop: dispatcher_layer0_emit surface=web bond_id=rohit composition_hint=SUBSTRATE_ONLY provenance_framing=SUBSTRATE_ONLY_NO_FRESH_VALIDATION inventory_witness=UNKNOWN substrate_source_count=3 external_source_count=0 elapsed_ms=14.141
2026-05-27 13:23:00 [INFO] core.brain.brain_loop: dispatcher_layer2_repair surface=web bond_id=rohit result=unchanged refusal_reason=
2026-05-27 13:23:00 [INFO] core.brain.brain_loop: dispatcher_layer1_branch surface=web source=TELEGRAM_SEMANTIC outcome=rows row_count=1 elapsed_ms=304.311
2026-05-27 13:23:00 [INFO] core.brain.brain_loop: dispatcher_layer1_branch surface=web source=ENTITY_INDEX outcome=error row_count=0 elapsed_ms=0.000
2026-05-27 13:23:00 [INFO] core.brain.brain_loop: dispatcher_layer1_branch surface=web source=LIVED_EPISODES outcome=error row_count=0 elapsed_ms=0.000
2026-05-27 13:23:00 [INFO] core.brain.brain_loop: dispatcher_layer1_fanout surface=web fanout_generation_id=524f83b9ad6946ee940c9118c0528eb6 branch_count=3 seal_state=partial_failure total_elapsed_ms=304.478
2026-05-27 13:23:00 [INFO] core.brain.brain_loop: dispatcher_path_exit surface=web bond_id=rohit chat_id=finding19-daemon-after-5 path_taken=dispatcher total_elapsed_ms=318.888
2026-05-27 13:23:00 [INFO] core.brain.brain_loop: dispatcher_path_entry surface=web bond_id=rohit chat_id=finding19-daemon-after-6 flag_state=enabled recovery_seed_present=False
2026-05-27 13:23:00 [INFO] core.brain.brain_loop: dispatcher_layer0_emit surface=web bond_id=rohit composition_hint=FRESH_ONLY provenance_framing=FRESH_ONLY inventory_witness=UNKNOWN substrate_source_count=0 external_source_count=1 elapsed_ms=17.949
2026-05-27 13:23:00 [INFO] core.brain.brain_loop: dispatcher_layer2_repair surface=web bond_id=rohit result=unchanged refusal_reason=
2026-05-27 13:23:00 [INFO] core.brain.brain_loop: dispatcher_layer1_fanout surface=web fanout_generation_id=921d827296984db9a280286274fd4626 branch_count=0 seal_state=clean total_elapsed_ms=0.042
2026-05-27 13:23:00 [INFO] core.brain.brain_loop: dispatcher_path_exit surface=web bond_id=rohit chat_id=finding19-daemon-after-6 path_taken=dispatcher total_elapsed_ms=18.264
2026-05-27 13:23:02 [INFO] core.brain.brain_loop: dispatcher_path_entry surface=web bond_id=rohit chat_id=finding19-daemon-after-7 flag_state=enabled recovery_seed_present=False
2026-05-27 13:23:02 [INFO] core.brain.brain_loop: dispatcher_layer0_emit surface=web bond_id=rohit composition_hint=SUBSTRATE_ONLY provenance_framing=SUBSTRATE_ONLY_NO_FRESH_VALIDATION inventory_witness=UNKNOWN substrate_source_count=3 external_source_count=0 elapsed_ms=16.438
2026-05-27 13:23:02 [INFO] core.brain.brain_loop: dispatcher_layer2_repair surface=web bond_id=rohit result=refused refusal_reason=NO_PRIOR_SPEC
2026-05-27 13:23:02 [INFO] core.brain.brain_loop: dispatcher_path_entry surface=web bond_id=rohit chat_id=finding19-daemon-after-8 flag_state=enabled recovery_seed_present=False
2026-05-27 13:23:02 [INFO] core.brain.brain_loop: dispatcher_layer0_emit surface=web bond_id=rohit composition_hint=SUBSTRATE_ONLY provenance_framing=SUBSTRATE_ONLY_NO_FRESH_VALIDATION inventory_witness=UNKNOWN substrate_source_count=3 external_source_count=0 elapsed_ms=12.858
2026-05-27 13:23:02 [INFO] core.brain.brain_loop: dispatcher_layer2_repair surface=web bond_id=rohit result=refused refusal_reason=NO_PRIOR_SPEC
```

After-run `actions.log` web/fetch excerpt:

```text
(none)
```

## Surface Verdicts

| Surface | Verdict | Witness |
|---|---|---|
| Live daemon HTTP ingress | CLOSED | All eight probes returned HTTP 200 from `/internal/brain_loop`. |
| Dispatcher flag wiring | CLOSED | Baseline had no dispatcher telemetry; after-run emitted `dispatcher_path_entry` / Layer 0 / Layer 1 logs. |
| Reddit source selection | CLOSED | Probes 1-4 selected `REDDIT_SOURCE` with one branch, not generic fallback fan-out. |
| Reddit substrate return | CLOSED | Probes 1-4 returned `REDDIT_SOURCE:rows:1`. |
| Rendered answer | CLOSED | Probes 1-4 returned `[memory context]` transcript text with Reddit substrate rows. |
| JARVIS substrate bypass | CLOSED for probes 1-4 | Baseline used `web_search` / `fetch_url`; after-run had no web/fetch action lines for probes 1-4. |
| External-source consumption | STILL OPEN / deferred | Probe 6 emitted `FRESH_ONLY` and returned no transcript/tool call; this belongs to the external-source seam, not the Reddit-substrate closure. |
| Direct Telegram transport | NOT SEPARATELY WITNESSED | HTTP ingress was used; discovery brief established shared `run_brain_loop` funnel. |

## Findings

1. **The original Finding 19 substrate-bypass is closed at daemon HTTP level.** `What's going on on Reddit?` no longer goes to `web_search` / `fetch_url` when the dispatcher flag is enabled; it returns Reddit substrate rows.
2. **The adapter fix holds under the live service.** The row-return behavior previously witnessed in-process now reproduces through the running daemon.
3. **Layer 0 cold-start latency remains visible.** Probe 1 emitted a Layer 0 budget warning at 848.756ms after service restart; warm probes were much lower.
4. **External-source behavior remains a separate open seam.** `Search r/LocalLLaMA right now` produced `FRESH_ONLY` but no transcript/tool result in this witness.
5. **The service flag was restored after the probe.** The live daemon is back to dispatcher-disabled posture after this witness run.
