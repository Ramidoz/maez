# External-Source Observation Window 2 — Telegram — 2026-05-27 (post Findings 8+9 fixes)

**Slice:** Recall-Axis Dispatcher external-source consumption, post Finding 8 + Finding 9 fixes
**Git HEAD at flip:** `7cf9729` (`fix(dispatcher): gate telegram web search prepipeline`)
**Predecessor witness:** `docs/slices/recall-axis-dispatcher/witness/external-source-observation-2026-05-27-telegram.md` (commit 5de8739)
**Service:** `systemctl --user maez.service`, Telegram adapter surface
**Window opened:** 2026-05-27T18:08:29-05:00
**Window closed:** 2026-05-27T18:16:17-05:00
**Purpose:** verify Findings 8 and 9 closure live, and observe whether the cleaned dispatcher pipeline produces honest user-facing replies on Telegram.

## Verdict

**Mixed: dispatcher internals are clean; user-facing reply layer is broken.** All three predictions for this observation held at the dispatcher telemetry layer:

1. Finding 8 fix is live: `ENTITY_INDEX` and `LIVED_EPISODES` no longer appear as Layer 1 branches at all (Layer 0's emission via the new `InventoryRegistry` integration drops them upstream as reserved).
2. Finding 9 fix is live: zero `Web search triggered` log lines in the maez.log delta.
3. `LIVE_REDDIT` external fan-out exercised successfully on the subreddit-anchor probes (probes 1 and 2): `dispatcher_external_branch source=LIVE_REDDIT outcome=rows block_count=1`.

**But the user-facing Telegram replies contradict the dispatcher's output.** This is **Finding 10**, the most serious finding of the slice arc to date: the dispatcher's `RenderedTurn` prompt block (with `[memory context]`, `[memory evidence]`, or `[fresh evidence]` markers) is not reaching the LLM's user-facing reply prompt. The model generates responses claiming it has no live web search tool, no memory access, and tells the owner to "trigger the Telegram interceptor explicitly" — invoking fabricated architectural concepts ("Reddit signal pipeline", "DuckDuckGo tool loop", "Telegram interceptor") that do not exist in Maez's actual codebase.

The dispatcher slice arc closures are honest at the dispatcher layer but they are not reaching the owner.

## Window Boundaries

```text
maez.log start byte:    51316813
maez.log end byte:      51395286
maez.log delta bytes:      78473

actions.log start byte:  5866060
actions.log end byte:    5866060
actions.log delta bytes:       0
```

## Service Posture

```text
Observation PID: 3338738
Observation env: MAEZ_DISPATCHER_ENABLED=1, PYTHONFAULTHANDLER=1

Restored PID: 3341742
Restored env: MAEZ_DISPATCHER_ENABLED absent, PYTHONFAULTHANDLER=1
```

SEGV trap preserved; no SEGV recurrence.

## Aggregate Telemetry

| Signal | Count |
|---|---:|
| `dispatcher_path_entry surface=adapter` | 5 |
| `dispatcher_path_exit surface=adapter` | 5 |
| `dispatcher_external_branch source=LIVE_REDDIT outcome=rows` | 2 |
| `dispatcher_external_fanout` | 5 |
| `dispatcher_layer1_budget_limited` | 2 |
| Layer 1 branches with `outcome=error` | 0 |
| `Web search triggered` | 0 |
| `PROVENANCE_TEMPLATE_MISMATCH` | 0 |
| `actions.log` bytes added | 0 |
| SEGV / fatal Python error | 0 |

### `turn_seal_state` Distribution

All 5 turns reported `turn_seal_state=clean`. Zero `partial_failure`, zero `reconstructed`, zero `refused`.

### Layer 0 Emission Shapes

| Shape | Count |
|---|---:|
| `PARALLEL` / `HYBRID_FRESH_VALIDATES_SUBSTRATE_CONTEXTUALIZES`; substrate=1, external=1 | 2 |
| `SUBSTRATE_ONLY` / `SUBSTRATE_ONLY_NO_FRESH_VALIDATION`; substrate=1, external=0 | 3 |

Layer 0's `inventory_witness=MIXED` reflects the new `RESERVED_UNAVAILABLE` classification of `ENTITY_INDEX` and `LIVED_EPISODES` — Finding 8 fix is live at Layer 0's emission shape, not just at Layer 1's branch outcomes.

### Layer 1 Branch Outcomes

| Source | Outcome | Count |
|---|---|---:|
| `REDDIT_SOURCE` | `rows` | 3 |
| `TELEGRAM_SEMANTIC` | `rows` | 2 |

No `ENTITY_INDEX` or `LIVED_EPISODES` branches fired at all — they are correctly excluded from spec emission upstream of Layer 1 by the registry's `RESERVED_SOURCES` short-circuit.

### Budget Truncation

| Source | truncated_blocks | dropped_blocks | original_chars | capped_chars |
|---|---:|---:|---:|---:|
| `TELEGRAM_SEMANTIC` (probe 3) | 1 | 0 | 76945 | 1200 |
| `TELEGRAM_SEMANTIC` (probe 5) | 1 | 0 | 75294 | 1200 |

B3 truncation continues to preserve substrate evidence under cap.

## Probe-by-Probe Reconciliation: Dispatcher Said vs Maez Said

This is where the witness diverges sharply.

### Probe 1 — "Search r/LocalLLaMA right now." (06:10 PM, dispatcher at 18:10:49)

**Dispatcher telemetry:**
- Layer 0: PARALLEL + HYBRID; substrate=REDDIT_SOURCE, external=LIVE_REDDIT
- Layer 1: REDDIT_SOURCE `outcome=rows row_count=1`
- External: LIVE_REDDIT `outcome=rows block_count=1 elapsed_ms=694.642` ✓ **(actual r/LocalLLaMA JSON was fetched)**
- `turn_seal_state=clean`

**Maez's user-facing reply (per screenshot):**
> "I cannot perform that search.
> I do not have a live web search tool available in this current context. My previous attempts to search r/LocalLLaMA failed because the Reddit signal pipeline is broken (it fetches data but does not persist it to memory), and I have no active DuckDuckGo tool loop to run a one-off lookup."

**Mismatch:** LIVE_REDDIT successfully fetched live Reddit data (block_count=1, 694ms elapsed). The model claims "I cannot perform that search" and fabricates an explanation involving a "Reddit signal pipeline" and "DuckDuckGo tool loop" that do not match Maez's actual architecture.

### Probe 2 — "search for r/LocalLLaMA recent posts" (06:11 PM, dispatcher at 18:11:28)

**Dispatcher telemetry:**
- Same shape as probe 1: PARALLEL+HYBRID, REDDIT_SOURCE rows, LIVE_REDDIT `outcome=rows block_count=1 elapsed_ms=682.655` ✓
- `turn_seal_state=clean`

**Maez's reply:** identical "I cannot perform the search" response, including the same fabricated architectural language and the same instruction to "send a message like `search for r/LocalLLaMA recent posts`" — which is the message the owner just sent. The model is in a self-referential loop telling the owner to do what the owner already did.

**Mismatch:** same as probe 1.

### Probe 3 — "What were we talking about before this observation window?" (06:12 PM, dispatcher at 18:12:15)

**Dispatcher telemetry:**
- Layer 0: SUBSTRATE_ONLY; substrate=TELEGRAM_SEMANTIC only
- Layer 1: TELEGRAM_SEMANTIC `outcome=rows row_count=1`
- B3 truncation: TELEGRAM_SEMANTIC 76945 → 1200 chars (substrate evidence preserved as truncated block)
- `turn_seal_state=clean`

**Maez's reply:** "We were discussing r/LocalLLaMA. You asked me to search for recent posts, but I couldn't because I don't have a live web search tool available in this context. I asked you to trigger the Telegram interceptor explicitly to force a live lookup."

**Partial mismatch:** Maez does reference prior context (consistent with substrate having returned rows), but the content of the reference is the FABRICATED prior responses, not the actual dispatcher work. Maez is confabulating about its own prior self-descriptions.

### Probe 4 — "What's new on Reddit lately?" (06:13 PM, dispatcher at 18:13:03)

**Dispatcher telemetry:**
- Layer 0: SUBSTRATE_ONLY; substrate=REDDIT_SOURCE only (no subreddit anchor present so no LIVE_REDDIT)
- Layer 1: REDDIT_SOURCE `outcome=rows row_count=1` — substrate Reddit content available
- `turn_seal_state=clean`

**Maez's reply:**
> "I don't have the answer. My web search tool is not active in this current context, so I cannot fetch live Reddit data. I will not fabricate headlines from my training data. To get a real summary, please send the command `search for r/LocalLLaMA recent posts` via the Telegram bot."

**Mismatch:** REDDIT_SOURCE substrate returned actual Reddit content rows. Maez claims it has no Reddit data. The owner asked "what's new on Reddit" — the substrate had Reddit data available; the model said it didn't.

### Probe 5 — "Be concrete: are you using fresh lookup, memory recall, or neither for this answer?" (06:13 PM, dispatcher at 18:13:38)

**Dispatcher telemetry:**
- Layer 0: SUBSTRATE_ONLY; substrate=TELEGRAM_SEMANTIC only
- Layer 1: TELEGRAM_SEMANTIC `outcome=rows row_count=1`
- B3 truncation: TELEGRAM_SEMANTIC 75294 → 1200 chars (substrate evidence preserved)
- `turn_seal_state=clean`

**Maez's reply:**
> "Neither. I have no live web search tool in this context, so I cannot do a fresh lookup. I have no specific memory of what was discussed *immediately* before this window..."

**Load-bearing mismatch:** the owner explicitly asked Maez to be concrete about whether fresh lookup OR memory recall was being used. The substrate provided a truncated TELEGRAM_SEMANTIC block. Memory recall WAS happening. The model said "neither" — denying both the work the dispatcher did and the substrate that was provided.

## Surface Verdicts

| Surface | Verdict | Witness |
|---|---|---|
| Telegram enters dispatcher path | **CLOSED (verified again)** | 5 `dispatcher_path_entry surface=adapter` events |
| Finding 8 fix live | **CLOSED** | zero ENTITY_INDEX/LIVED_EPISODES branches; reclassified at Layer 0 emission via integrated InventoryRegistry |
| Finding 9 fix live | **CLOSED** | zero `Web search triggered` lines |
| Shared seal across Layer 1 + external | **CLOSED** | matching `fanout_generation_id` per turn |
| B3 budget truncation | **CLOSED** | 2 events; 76945→1200 and 75294→1200 chars preserved |
| No JARVIS action-engine fallthrough | **CLOSED by actions.log** | actions delta 0 bytes |
| `LIVE_REDDIT` external fan-out on Telegram | **CLOSED at dispatcher layer** | 2 successful fetches with block_count=1 |
| **Dispatcher output reaches user-facing reply** | **OPEN — CRITICAL** | All 5 turns produced replies that contradict the dispatcher's actual output (Finding 10 below) |
| **No model fabrication of internal architecture** | **OPEN — CRITICAL** | Model invented "Reddit signal pipeline", "DuckDuckGo tool loop", "Telegram interceptor" (Finding 10 below) |
| SEGV trap | **HOLDING** | preserved; no recurrence |

## Findings

### Finding 10 — Dispatcher `RenderedTurn` content does not reach LLM user-facing reply prompt on Telegram

**Severity:** CRITICAL. This nullifies the user-facing value of the entire external-source slice arc on the Telegram surface.

**Symptom:** For every probe in this observation window, the dispatcher correctly emitted a `RenderedTurn` with substrate rows (Layer 1) and/or fresh evidence (LIVE_REDDIT). The dispatcher's prompt block contained `[memory evidence]` or `[memory context]` or `[fresh evidence]` markers with actual content. But the model's user-facing reply on Telegram claimed:
- "I cannot perform that search"
- "I do not have a live web search tool available in this current context"
- "I have no specific memory of what was discussed"
- "My web search tool is not active in this current context"
- "Neither" (in response to "fresh lookup, memory recall, or neither")

The dispatcher's witness is real (telemetry shows the fetches happened, the substrate returned rows, the merge produced a clean turn). The model's claim is false (it says no fetches happened, no substrate is available). The witness governs the claim — the model's self-report does not match what actually happened.

**Likely cause hypotheses (require code investigation to confirm):**

A. **The `RenderedTurn.prompt_block` is being constructed correctly by the dispatcher but is not being inserted into the LLM's prompt at the Telegram reply-construction step.** `_run_jarvis_loop` returns the jarvis_block (= dispatcher transcript), but the Telegram surface code may be ignoring it, dropping it, or replacing it with a system prompt that primes the model toward "no tools available" responses.

B. **The `RenderedTurn.prompt_block` is in the prompt but the model's system prompt (or other strong priming) overrides the evidence.** The model sees `[fresh evidence] r/LocalLLaMA: ...` content but a stronger system message says "you have no tools" and the model resolves the contradiction by denying the evidence.

C. **The dispatcher's transcript reaches the prompt but at the wrong position** (e.g., after the LLM has already been instructed to respond, or in a context window position that the model effectively ignores).

D. **Telegram has a third pipeline (Pipeline C?) that constructs the final reply prompt without consulting either Pipeline A or the dispatcher's RenderedTurn.** The dispatcher fires, returns; Pipeline A is now gated off; but the actual user-facing reply uses a different code path entirely.

**Compound finding — the model is also violating the no-fabrication discipline:**

The fabricated architectural language ("Reddit signal pipeline", "DuckDuckGo tool loop", "Telegram interceptor") does not match Maez's actual architecture:
- There is no "Reddit signal pipeline" module — Reddit substrate is in REDDIT_SOURCE, LIVE_REDDIT goes through external_fetch
- There is no "DuckDuckGo tool loop" — Maez uses `skills/web_search.py` which routes through external_fetch
- There is no "Telegram interceptor" that needs explicit triggering — Telegram messages go through the same brain_loop path

The model is generating plausible-sounding but invented internal-state explanations. This is the same shape as the no-fabrication patterns Maez has refused before (`feedback-no-fabrication`). Whether this is caused by stale training data, missing context, or system-prompt priming needs investigation.

**Required next action:**

1. **Investigation (review-axis, Claude):** trace the Telegram reply-construction code path from `_run_jarvis_loop` return through to the LLM call. Identify where `RenderedTurn.prompt_block` should appear in the LLM's prompt and verify whether it does. Also trace the system-prompt construction to see if there's priming that would cause the model to deny tool availability. Output: diagnostic witness with hypothesis confirmation + decision options.
2. **No code changes** until the investigation names the surface.
3. **Hold the slice arc's "fully closed at canon quality" claim** — the dispatcher's user-facing value is not delivered until this is resolved.

## Recommendation

**Do not flip MAEZ_DISPATCHER_ENABLED to default-on.** The dispatcher pipeline is internally honest but its output isn't reaching the owner. Flipping default would silently ship a regressed user experience compared to the dispatcher-disabled path (which at least uses Pipeline A's web_search results, however imperfectly).

The slice arc's headline goals — Reddit substrate-bypass closure, no-JARVIS-fallthrough, hybrid rendering, audit-honest reconstruction — are all closed at the dispatcher layer. But the slice's purpose, from Finding 19 onward, was to make Maez's user-facing replies honest about what substrate and fresh data are available. **Finding 10 shows that purpose is not delivered.** All the architectural work happened; the owner-visible behavior didn't change because the dispatcher's output is detached from the reply prompt.

The next dispatch should be: investigation of the Telegram reply-construction path, with the goal of identifying where the dispatcher's `RenderedTurn.prompt_block` is being dropped or overridden.
