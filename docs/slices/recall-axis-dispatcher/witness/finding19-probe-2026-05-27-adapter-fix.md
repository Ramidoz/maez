# Finding 19 Adapter-Fix Probe Witness — 2026-05-27

**Slice:** Recall-Axis Dispatcher / ADR 0047  
**Predecessor partial witness:** `docs/slices/recall-axis-dispatcher/witness/finding19-probe-2026-05-27.md`  
**Raw witness:** `docs/slices/recall-axis-dispatcher/witness/finding19-probe-2026-05-27-adapter-fix.raw.json`

## Verdict

**Adapter-level in-process closure; daemon-level closure still open.**

The witness proves that the in-process dispatcher path now reaches `REDDIT_SOURCE`, returns bounded Reddit substrate rows, and renders dispatcher transcript for the four Reddit-shaped probes in the witnessed corpus.

It does **not** prove full Finding 19 closure at daemon level. This run still uses the in-process shared-entry harness because the prior witness established `maez.service` was inactive. A service-level daemon/HTTP or Telegram probe remains required before claiming live service closure.

## Baseline — Flag Off

| # | Probe | Transcript length | Dispatcher events |
|---|---|---:|---:|
| 1 | `Check Reddit then` | 0 | 0 |
| 2 | `Just let me know what's going on in Reddit in localllama` | 0 | 0 |
| 3 | `What's going on on Reddit?` | 0 | 0 |
| 4 | `You have access to Reddit data` | 0 | 0 |
| 5 | `What were we talking about last evening?` | 0 | 0 |
| 6 | `Search r/LocalLLaMA right now` | 0 | 0 |
| 7 | `Really?` | 0 | 0 |
| 8 | `Are you sure?` | 0 | 0 |

## After-Run — Flag On

| # | Probe | Transcript length | Branch evidence |
|---|---|---:|---|
| 1 | `Check Reddit then` | 771 | REDDIT_SOURCE:rows:1:345.036ms |
| 2 | `Just let me know what's going on in Reddit in localllama` | 823 | REDDIT_SOURCE:rows:1:21.837ms |
| 3 | `What's going on on Reddit?` | 771 | REDDIT_SOURCE:rows:1:101.325ms |
| 4 | `You have access to Reddit data` | 771 | REDDIT_SOURCE:rows:1:116.915ms |
| 5 | `What were we talking about last evening?` | 371 | TELEGRAM_SEMANTIC:rows:1:345.313ms, ENTITY_INDEX:error:0:0.000ms, LIVED_EPISODES:error:0:0.000ms |
| 6 | `Search r/LocalLLaMA right now` | 0 | no Layer 1 branches |
| 7 | `Really?` | 0 | no Layer 1 branches |
| 8 | `Are you sure?` | 0 | no Layer 1 branches |

## Findings

1. **The Reddit adapter failure is closed in-process.** Probes 1-4 all returned `REDDIT_SOURCE:rows` with rendered transcript.
2. **The source-anchor fan-out is narrowed.** Reddit-shaped probes select `REDDIT_SOURCE` without generic Telegram/entity fallback branches.
3. **Empty selected branches now remain visible.** If a selected source returns no usable rows, the renderer emits an explicit no-usable-recall summary instead of dropping the transcript.
4. **D13 latency is still observable, not hidden.** The first cold Layer 0 path may still emit a budget warning; the adapter fix does not claim latency closure.
5. **Daemon-level closure remains open.** This witness does not prove service-level ingress behavior.

## Next Closure Surface

Run the same probe corpus through the live daemon/service path with `MAEZ_DISPATCHER_ENABLED=1`, then commit the service-level diff before marking Finding 19 fully closed.
