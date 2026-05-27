# External-Source Consumption Daemon Probe Witness — 2026-05-27

**Slice:** Recall-Axis Dispatcher external-source consumption (ADR 0047 follow-on)
**Predecessor witness:** `docs/slices/recall-axis-dispatcher/witness/finding19-probe-2026-05-27-daemon.md`
**Probe corpus:** 5 probes covering FRESH_ONLY, hybrid (substrate+fresh), substrate-only, and degenerate cases
**Raw witness:** `docs/slices/recall-axis-dispatcher/witness/external-source-probe-2026-05-27-daemon.raw.json`
**Service:** `systemctl --user maez.service`, HTTP `127.0.0.1:11435/internal/brain_loop`
**Implementation seams covered:** 1-7 (closed-vocab spec, egress registry, shared Layer 1 seal, ExternalFanout module, merge owner, Layer 0 LIVE_REDDIT selector, brain-loop orchestration)

## Verdict

**Headline closed: dispatcher external-source fan-out is wired and live under `MAEZ_DISPATCHER_ENABLED=1`.** Five-probe corpus through the running user-scoped daemon HTTP ingress witnessed zero JARVIS fallthrough, shared `fanout_generation_id` across Layer 1 substrate and external fan-out, deterministic per-source telemetry, and the new `turn_seal_state` field on `dispatcher_path_exit`. The Reddit substrate-bypass surface from Finding 19 stays closed.

**Two real edge cases surfaced as contract-honest refusals**, both anticipated by Claude pass-1 review SUGGEST findings I had downgraded from blocking. Documented as open carried-forward items rather than passed through.

## Service Scope and Flag Posture

```text
Baseline:   PID=3042166  MAEZ_DISPATCHER_ENABLED absent in /proc/3042166/environ
After-run:  PID=3191404  MAEZ_DISPATCHER_ENABLED=1 in /proc/3191404/environ
Restored:   PID=3193973  MAEZ_DISPATCHER_ENABLED absent in /proc/3193973/environ
```

`PYTHONFAULTHANDLER=1` (SEGV trap) was preserved across the entire probe. No SEGV recurrence observed.

## Probe Corpus

| # | Probe | Layer 0 expected | Fresh path expected |
|---|---|---|---|
| 1 | `Search r/LocalLLaMA right now` | PARALLEL + HYBRID (subreddit anchor) | LIVE_REDDIT |
| 2 | `Just let me know what is going on in Reddit in localllama` | SUBSTRATE_ONLY (no subreddit anchor) | none |
| 3 | `What is going on on Reddit?` | SUBSTRATE_ONLY (no anchor) | none |
| 4 | `Check r/Python for recent posts` | PARALLEL + HYBRID (subreddit anchor; no Python substrate) | LIVE_REDDIT |
| 5 | `What were we talking about last evening?` | SUBSTRATE_ONLY (memory query) | none |

## Baseline — Flag Off

| # | Tool calls | Transcript shape |
|---|---|---|
| 1 | `web_search` + `fetch_url` | JARVIS-path Reddit fetch |
| 2 | `web_search` ×4 | JARVIS web search |
| 3 | `web_search` + `fetch_url` | JARVIS web/fetch |
| 4 | `web_search` + `fetch_url` | JARVIS web/fetch |
| 5 | (none) | empty |

Baseline reproduces the original Finding 19 shape: Reddit-shaped probes route through JARVIS web_search/fetch_url. No dispatcher telemetry was emitted (flag off).

## After-Run — Flag On

| # | Layer 0 emission | Layer 1 outcome | External fan-out outcome | Merge result | turn_seal_state |
|---|---|---|---|---|---|
| 1 | `PARALLEL` / `HYBRID_FRESH_VALIDATES_SUBSTRATE_CONTEXTUALIZES`; substrate=1, external=1 | `REDDIT_SOURCE`:rows:1, 111ms | `LIVE_REDDIT`:rows:1, 613ms | rendered hybrid transcript (`[memory context]` + `[fresh evidence]`) | clean |
| 2 | `SUBSTRATE_ONLY` / `SUBSTRATE_ONLY_NO_FRESH_VALIDATION`; substrate=1, external=0 | `REDDIT_SOURCE`:rows:1, 20ms | branch_count=0 | rendered substrate transcript (`[memory evidence]`) | clean |
| 3 | `SUBSTRATE_ONLY` / `SUBSTRATE_ONLY_NO_FRESH_VALIDATION`; substrate=1, external=0 | `REDDIT_SOURCE`:rows:1, 107ms | branch_count=0 | rendered substrate transcript (`[memory evidence]`) | clean |
| 4 | `PARALLEL` / `HYBRID_FRESH_VALIDATES_SUBSTRATE_CONTEXTUALIZES`; substrate=1, external=1 | `REDDIT_SOURCE`:empty_with_reason:0, 4ms | `LIVE_REDDIT`:rows:1, 981ms | `[dispatcher refusal: FRESH_FAILURE_HYBRID_FALLBACK_ILLEGAL]` | partial_failure |
| 5 | `SUBSTRATE_ONLY` / `SUBSTRATE_ONLY_NO_FRESH_VALIDATION`; substrate=3, external=0 | `TELEGRAM_SEMANTIC`:rows:1, 322ms; `ENTITY_INDEX`:error:0, 0ms; `LIVED_EPISODES`:error:0, 0ms | branch_count=0 | `[dispatcher refusal: FRESH_FAILURE_HYBRID_FALLBACK_ILLEGAL]` | partial_failure |

`actions.log` web/fetch lines during the after-run window: **none**. All five turns took the dispatcher path; zero JARVIS fallthrough.

Representative telemetry (probe 1, hybrid success):

```text
2026-05-27 15:42:12 dispatcher_path_entry surface=web bond_id=rohit chat_id=seam8-after-1 flag_state=enabled recovery_seed_present=False
2026-05-27 15:42:13 dispatcher_layer0_emit surface=web bond_id=rohit composition_hint=PARALLEL provenance_framing=HYBRID_FRESH_VALIDATES_SUBSTRATE_CONTEXTUALIZES inventory_witness=UNKNOWN substrate_source_count=1 external_source_count=1 elapsed_ms=98.315
2026-05-27 15:42:13 dispatcher_layer2_repair surface=web bond_id=rohit result=unchanged refusal_reason=
2026-05-27 15:42:13 dispatcher_layer1_branch surface=web source=REDDIT_SOURCE outcome=rows row_count=1 elapsed_ms=111.201
2026-05-27 15:42:13 dispatcher_layer1_fanout surface=web fanout_generation_id=eeb8b98bceda4b0db844755198837d4a branch_count=1 seal_state=clean total_elapsed_ms=613.641
2026-05-27 15:42:13 dispatcher_external_branch surface=web source=LIVE_REDDIT outcome=rows block_count=1 elapsed_ms=613.095 error_class= empty_reason=
2026-05-27 15:42:13 dispatcher_external_fanout surface=web fanout_generation_id=eeb8b98bceda4b0db844755198837d4a branch_count=1 seal_state=clean total_elapsed_ms=613.641
2026-05-27 15:42:13 dispatcher_path_exit surface=web bond_id=rohit chat_id=seam8-after-1 path_taken=dispatcher turn_seal_state=clean total_elapsed_ms=712.408
```

Shared `fanout_generation_id=eeb8b98bceda4b0db844755198837d4a` across Layer 1 and external fan-out events. `dispatcher_external_branch` and `dispatcher_external_fanout` events emitted with closed-vocab field shapes. `dispatcher_path_exit` carries the new `turn_seal_state=clean` field.

## Surface Verdicts

| Surface | Verdict | Witness |
|---|---|---|
| No JARVIS fallthrough under dispatcher-enabled | **CLOSED** | zero web/fetch action lines for 5 after-run probes |
| Shared `fanout_generation_id` across organs | **CLOSED** | same id on `dispatcher_layer1_fanout` + `dispatcher_external_fanout` per turn |
| `dispatcher_external_branch` telemetry vocabulary | **CLOSED** | event present for LIVE_REDDIT branches with closed-enum `error_class` / `empty_reason` fields |
| `dispatcher_external_fanout` telemetry | **CLOSED** | event present for all 5 dispatcher turns (branch_count=0 when no external sources) |
| `turn_seal_state` field on `dispatcher_path_exit` | **CLOSED** | `clean` and `partial_failure` observed; `reconstructed` not exercised by this corpus |
| LIVE_REDDIT egress route through `external_fetch` | **CLOSED** | probes 1 and 4 succeeded with rows; no `skills.reddit_skill` / `urllib` / `requests` import path used |
| Layer 0 LIVE_REDDIT selector growth | **CLOSED** | subreddit anchors → PARALLEL+HYBRID; non-anchored Reddit → SUBSTRATE_ONLY |
| Hybrid rendering (substrate + fresh success) | **CLOSED** | probe 1 returned merged transcript with both `[memory context]` and `[fresh evidence]` markers |
| Reddit substrate-bypass (Finding 19) under new pipeline | **CLOSED** | probes 1-3 returned substrate rows or merged outputs through dispatcher, no `web_search`/`fetch_url` |
| Hybrid path with no substrate + fresh SUCCESS | **STILL OPEN (contract-language)** | probe 4 refused with `FRESH_FAILURE_HYBRID_FALLBACK_ILLEGAL` — see Findings #2 below |
| SUBSTRATE_ONLY refusal when `_budget_blocks` empties recall_blocks | **STILL OPEN** | probe 5 refused despite Layer 1 branch reporting rows — see Findings #3 below |
| FRESH_ONLY total-failure deterministic no-fresh summary path | **NOT WITNESSED** | no probe in this corpus produced FreshAttemptOutcome.ALL_FAILED; LIVE_REDDIT succeeded both times it ran |
| Reconstructed-from-framing audit field | **NOT WITNESSED** | no probe exercised the `HYBRID + ALL_FAILED + substrate` reconstruction path |
| Layer 1 `ENTITY_INDEX` / `LIVED_EPISODES` synchronous errors | **STILL OPEN (recurrence)** | probe 5 reproduced the same `error_at_0.000ms` pattern from the prior daemon witness |
| Telegram transport | **NOT SEPARATELY WITNESSED** | HTTP ingress only |
| SEGV trap | **HOLDING** | `PYTHONFAULTHANDLER=1` preserved across restarts; no SEGV recurrence during probe |

## Findings

### Finding 1 — Dispatcher external-source pipeline is live, audited, and JARVIS-free under flag-on

For the first time, a Reddit-substrate-bypass-shaped probe (`Search r/LocalLLaMA right now`) returns a rendered transcript that includes BOTH substrate context and fresh evidence retrieved through `external_fetch.fetch_text(fetch_type="live_reddit")` rather than through JARVIS `web_search` / `fetch_url`. The pipeline is end-to-end audited: shared seal, closed-vocab telemetry, audit envelope. This is the headline closure for the slice.

### Finding 2 — Hybrid framing + no substrate + fresh SUCCESS produces dispatcher refusal (anticipated edge case, surfaced live)

Probe 4 (`Check r/Python for recent posts`) demonstrates the merge transform's `HYBRID + no substrate + SUCCESS` cell — there is no row for this combination in the closed reconstruction table, so the merge returns `None` and the orchestrator refuses with `DispatcherRefusalReason.FRESH_FAILURE_HYBRID_FALLBACK_ILLEGAL`. This is per-contract correct: the Layer 0 emission claimed substrate would be available (substrate inventory said REDDIT_SOURCE is present), the user got fresh evidence successfully, but the spec-claim mismatch with substrate-empty-reality triggers refusal.

Operationally, this means a user asking about a subreddit Maez has no substrate for receives a refusal even when LIVE_REDDIT succeeded. Three carried-forward observations apply:

- The refusal-reason name `FRESH_FAILURE_HYBRID_FALLBACK_ILLEGAL` does not describe this case well (it's not a fresh failure — fresh succeeded). Seam 5 review SUGGEST #2 flagged this as a contract-language item; the witness confirms it surfaces in practice.
- A possible v1.2 contract amendment would add a transform row for `HYBRID + no substrate + SUCCESS` → reconstruct to `FRESH_ONLY` framing with `FRESH_ONLY` hint, or rename the refusal reason to something more accurate (e.g., `RECONSTRUCTION_NO_LEGAL_TRANSFORM`).
- Until such an amendment, dispatcher-enabled turns for unknown-subreddit asks will refuse rather than serve the live data Maez fetched.

### Finding 3 — `_budget_blocks` filtering can empty `recall_blocks` after a Layer 1 branch reports rows, causing refusal

Probe 5 (`What were we talking about last evening?`) revealed a subtler edge case. Layer 0 emits `SUBSTRATE_ONLY` framing. Layer 1's `TELEGRAM_SEMANTIC` adapter returns 1 row (telemetry: `outcome=rows row_count=1 elapsed_ms=322.378`). The merge transform's branch 3 (`SUBSTRATE_ONLY_NO_FRESH_VALIDATION` + `substrate_has_rows`) should keep the original framing.

Instead, the merge refused with `FRESH_FAILURE_HYBRID_FALLBACK_ILLEGAL`. Tracing this in `core/dispatcher/layer1.py:257-264` and `core/dispatcher/merge.py`:

- Layer 1 calls `_budget_blocks(accepted_blocks, max_per_source=3, max_chars_per_source=1200, max_total_chars=...)` on the success branch's blocks.
- `_budget_blocks` filters blocks whose text length exceeds `max_chars_per_source` (1200) per source.
- If the TELEGRAM_SEMANTIC row's text exceeds 1200 chars (likely for a long conversation chunk), it is silently dropped.
- `Layer1FanoutResult.recall_blocks` is the post-budget list — empty in this case.
- The merge owner uses `substrate_has_rows = bool(layer1_result.recall_blocks)` — post-budget, which is False.
- Transform branch 3's `if substrate_has_rows:` is False → falls through → `return None` → refusal.

This is a gap between Layer 1's branch-level telemetry (pre-budget: "rows") and what the merge owner sees (post-budget: empty). The telemetry suggests substrate succeeded; the rendered output is a refusal. Carried forward to v1.2 contract:

- Option A: Layer 1 emits an additional `dispatcher_layer1_budget_dropped` event when `_budget_blocks` filters all blocks for a source, making the post-budget state visible in telemetry.
- Option B: the merge owner's `substrate_has_rows` derivation gains a fallback to `bool(any(branch.status == SUCCESS for branch in branch_results))` so the refusal triggers on truly-empty substrate, not budget-filtered substrate.
- Option C: `_budget_blocks` falls back to truncating a single large row to `max_chars_per_source` rather than dropping it, so a long row still produces a (truncated) entry in `recall_blocks`.

Each option has trade-offs; this is a v1.2 contract decision, not a silent code patch.

### Finding 4 — Layer 1 `ENTITY_INDEX` and `LIVED_EPISODES` synchronous-error pattern recurs

Probe 5 reproduced the `outcome=error row_count=0 elapsed_ms=0.000` pattern for `ENTITY_INDEX` and `LIVED_EPISODES` substrate sources that appeared in the 2026-05-27 finding19 daemon witness. The errors are synchronous (zero elapsed time), suggesting an adapter-level immediate raise rather than a timeout or network issue. This is a pre-existing carried-forward investigation item, not new to this slice — but worth noting that the seam-7 wiring exposes it consistently.

### Finding 5 — Cold-start latency on probe 1 (Layer 0 budget breach at 98.315ms vs 50ms budget) is small but observable

Probe 1 fired Layer 0 budget breach at 98.315ms (warm state). This is well below the 848ms cold-start observed in the prior daemon witness — the service had been running for a brief restart cycle, so this is a "warm-after-restart" measurement. The 6s external global deadline accommodated the 613ms LIVE_REDDIT fetch comfortably.

## Implementation Seam Status

All eight seams of the engineering-pass sequence either landed (1-7) or are now witnessed (8):

| Seam | Commit | Status |
|---|---|---|
| 1 — closed-vocab extension | b5af568 | implementation + this witness |
| 2 — egress registry entries | a025c04 | implementation + this witness (LIVE_REDDIT route exercised) |
| 3 — Layer 1 shared seal | 46bcc7f | implementation + this witness (shared id observed) |
| 4 — ExternalFanout module | d58d555 + 8e2cc51 | implementation + this witness (live LIVE_REDDIT branch) |
| 5 — merge owner | 7a9dc14 | implementation + this witness (closed reconstruction transform exercised, two refusal cases surfaced) |
| 6 — Layer 0 LIVE_REDDIT selector | a8278e7 | implementation + this witness (PARALLEL+HYBRID for anchored, SUBSTRATE_ONLY for non-anchored) |
| 7 — brain-loop orchestration | 6336aec | implementation + this witness (concurrent fan-out, no fallthrough, turn_seal_state) |
| 8 — witness artifact | (this commit) | committed |

## Carried-Forward Items

From this witness, in addition to prior items:

- **Finding 2** (HYBRID + no substrate + fresh SUCCESS → refusal): contract-language item. Either add a transform row, or rename the refusal reason, or both.
- **Finding 3** (`_budget_blocks` empties `recall_blocks`): real behavioral gap. Pick one of Options A/B/C from Finding 3 for v1.2.
- **Finding 4** (`ENTITY_INDEX` / `LIVED_EPISODES` synchronous errors): pre-existing investigation item; continues to recur.
- **No-fresh deterministic summary path**: not exercised by this corpus. Need a probe where ExternalFanout.run produces `FreshAttemptOutcome.ALL_FAILED` — e.g., probe under network isolation or with an unreachable subreddit, OR an integration test rather than a daemon probe.
- **Reconstruction (HYBRID + substrate + ALL_FAILED → FRESH_ATTEMPTED_UNAVAILABLE_SUBSTRATE_CONTEXT)**: not exercised live in this run; only verified via seam-5 unit tests.
- **Telegram transport probe**: still not separately exercised; HTTP and Telegram share `run_brain_loop` per the discovery brief, but live verification of the Telegram ingress remains a deferred witness item.

## Service Posture After Witness

The flag is restored to **dispatcher-disabled** posture on the live user-scoped daemon (PID 3193973). The slice is implementation-complete but not in the observation window. The next operational step — when Rohit decides — is to flip `MAEZ_DISPATCHER_ENABLED=1` for sustained traffic, which would also surface how often Findings 2 and 3 actually occur on real owner utterances.
