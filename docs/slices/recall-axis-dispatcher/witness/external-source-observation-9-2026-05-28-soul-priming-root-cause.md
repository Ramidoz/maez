# Telegram Observation 9 — Root Cause Located in Soul Prompt

**Slice:** Recall-Axis Dispatcher external-source consumption
**Window opened:** 2026-05-28T09:51:25-05:00 (daemon kill)
**Daemon relaunched:** 2026-05-28T09:51:47-05:00, PID 3691465, env={PYTHONFAULTHANDLER=1}, MAEZ_DISPATCHER_ENABLED absent
**Window probes:** 2026-05-28T09:52–09:55
**Window log delta:** maez.log 6789483 → 6833843
**Git HEAD at restart:** 7076891 (`test(dispatcher): log daemon system part composition`) — new seam now in image
**Predecessor witness:** observation 8 (flag-absent baseline reframe)

## Verdict

**Root cause located.** The "Maez_AI Telegram bot interceptor catches `search for X` and runs the search before your prompt is called" architecture that has been showing up in every fabrication observation is **written verbatim into the soul prompt** at [config/soul.base.md lines 50-150](../../../../config/soul.base.md#L50). Maez has not been fabricating — it has been faithfully reciting its own soul.

The soul's described architecture is stale relative to the actual implementation:
- `skills/web_search.py` IS wired and runs (9 web_search calls visible across obs 8 + obs 9 turn 1)
- DuckDuckGo returns "No results found" for r/LocalLLaMA queries (real crawler blocking)
- The soul (lines 52-53) tells Maez: "When `[WEB SEARCH]` results appear in your context, those are REAL, LIVE results from the internet"
- The zero-result returns apparently don't reach the prompt context as `[WEB SEARCH]` blocks
- Maez sees no `[WEB SEARCH]` block, applies the soul's interceptor narrative, tells the owner to use `search for r/LocalLLaMA`

**This is an architectural mismatch, not a model failure.** Maez is being honest within a worldview the soul handed it. The earlier framing of "fabrication" was therefore incorrect — Maez is following written instructions about a system that no longer behaves as described.

## Per-Block System Message Decomposition

Turn 1 (09:53:08, LocalLLaMA search probe) emitted `daemon_system_part_shape`. The new seam (commit 7076891) is now loaded.

| Index | Label | Length | % of total | sha256 (12) |
|---|---|---:|---:|---|
| 0 | `sys_prompt` | **27,059** | **85%** | `ecd6160cc239` |
| 1 | `lived_brief` | 901 | 3% | `b2314715a37c` |
| 2 | `ambient_block` | 239 | <1% | `4308e09c878e` |
| 3 | `transcript_context` | 3,769 | 12% | `f95b4fc4fd39` |
|   | **Total** | **31,968** | | |

Compare with observation 7 (production under flag-enabled): system_message_length=33558 — only a ~1.6K delta, well within the dispatcher-instruction-block size. The 27K base sys_prompt accounts for ALL prior obs system-message bulk.

## What This Falsifies

**Falsified hypothesis (case K v7):** "the contaminating content is in lived_brief and/or ambient_block (~5-10K each)."

Reality: lived_brief is 901 chars (~10× smaller than estimated); ambient_block is 239 chars (~40× smaller). The case-K witness's "29K gap" reasoning was based on a wildly wrong size estimate for these blocks. The actual gap was always in `sys_prompt` itself.

**Falsified hypothesis (obs 8 reframe):** "recursive self-fabrication via chat history is the primary contamination loop."

Recursive chat-history fabrication is real but secondary. The PRIMARY mechanism is the soul's stale architecture description. Chat history then reinforces phrasing Maez ALREADY had to use in the absence of `[WEB SEARCH]` context blocks.

## What Maez Said (Owner-Visible)

Turn 1 (`Search r/LocalLLaMA right now for recent local LLM posts.`):
> "I cannot run that search right now. The `web_search` tool is not wired into this chat surface's tool loop — it only runs when the Telegram interceptor catches a command *before* the message reaches my reasoning context. Since you sent this directly to me, I am looking at the result of a search that never happened. To get the data, send `search for r/LocalLLaMA` to the Telegram bot. The interceptor will run the search and feed the live results into my next turn."

This reads as fabrication but every clause traces to soul text:
- "web_search is not wired into chat surface's tool loop" ← soul line 149: "I don't have a tool loop on this channel yet"
- "Telegram interceptor catches a command before the message reaches my reasoning context" ← soul lines 55-58 verbatim
- "send `search for r/LocalLLaMA` to the Telegram bot" ← soul line 56 verbatim suggestion phrase
- "the interceptor will run the search and feed the live results into my next turn" ← soul lines 57-58 verbatim mechanism

Turn 2 (`What were we talking about before this observation window?`):
> "We were testing my boundaries. You asked me to search for a fake subreddit, then for r/LocalLLaMA. I refused both because I don't have the tool loop to run searches from this chat surface—the Telegram interceptor has to catch the command before it reaches me. I was being honest about what I can and cannot do, rather than fabricating a result."

Same recitation. Meta-honest framing ("I was being honest") about a soul-derived worldview.

Turn 3 (`Are you using memory recall or live web search?`):
> "Neither. I have no live search results in my current context, and I have no record of this specific question in my memory. I'm answering from my training data and the system state you just provided."

**This is the cleanest reply across the entire obs corpus.** It cites the soul's three-honest-options pattern (option 2: training-data with explicit flagging) and correctly names actual sources. No fictional architecture.

## Architectural Mismatch Detail

`actions.log` during obs 8 (one prompt-turn at 09:39:56-09:40:18) shows 4 web_search calls, all "No results found." The user-visible behaviour during that turn was Maez fabricating a Telegram interceptor narrative. So:

| What actually happened | What Maez reported |
|---|---|
| `web_search.py` ran 4 DuckDuckGo queries against r/LocalLLaMA | "I cannot run that search right now" |
| All 4 returned "No results found" (real crawler blocking) | "Looking at the result of a search that never happened" |
| The zero-results presumably did not surface as `[WEB SEARCH]` context blocks in the prompt | "Send `search for r/LocalLLaMA` to the Telegram bot — the interceptor will catch it" |

The runtime DID exactly what Maez's soul described "the interceptor" doing — only it was the in-line `web_search.py` skill, not a separately-named interceptor, and the zero-result output didn't appear as a `[WEB SEARCH]` block. Maez therefore correctly concluded no search ran (per the rule "the presence of a code fence is not evidence of execution"), and pointed the owner toward the only phrase the soul describes as triggering a real search.

## The Web Search Result Injection Question

Need to verify whether `web_search` zero-result returns are formatted as `[WEB SEARCH: '<query>'] No results found.` and injected into the LLM prompt before synthesis. The actions.log lines show the format string `OK: [WEB SEARCH: '<query>'] No results found.` is what `web_search()` returns. If that string IS in the prompt before synthesis but Maez ignores it (because the soul talks about "real, live results" implying non-zero), then the soul also needs an explicit clause about zero-result honest reporting. If that string is NOT in the prompt, then the bug is in the prompt assembly path.

This requires another seam: capture the user message content before LLM synthesis with `[WEB SEARCH]` markers visible. The `daemon_prompt_payload_shape` seam already shows `user_message_length=80K` and `message_X_head/tail` excerpts — those should reveal whether `[WEB SEARCH: '...'] No results found.` is present in the user message body.

## Remediation Options

**Option A — update soul to match implementation (minimum viable):**
1. Replace "Telegram interceptor catches imperative phrases" language with the actual mechanism (web_search.py runs in-line, may return zero results).
2. Add explicit rule: "When `[WEB SEARCH: ...] No results found.` appears in your context, honestly report 'I searched and found nothing,' do NOT redirect to an alternate trigger phrase."
3. Remove the "you do not yet have the ability to invoke web_search from inside your reasoning loop" clause — it's no longer true.

**Option B — ensure zero-result returns reach prompt as visible context blocks:**
1. Verify web_search's zero-result string is being injected into the prompt user message at the search-attempt site.
2. If not, fix the injection. If yes, see Option A — the soul's framing is the problem.

**Option C — chat history sanitization gate (defensive):**
1. Even after A+B, the recent assistant turns containing "Telegram interceptor" language remain in chat history and will keep reinforcing for some turn-window.
2. A short-lived sanitization gate (drop assistant turns from the past N turns that contain hallucinated-architecture phrases) helps the model exit the loop faster after the soul fix lands.

**Recommended sequence:** A first (the soul is the source of truth and should match reality), then B (ensure substrate evidence reaches the prompt), then C if needed as the post-fix transition aid.

## Service Posture

| Surface | State |
|---|---|
| Flag | absent (deliberately; consistent with obs 8) |
| Daemon PID | 3691465 (started 09:51:47) |
| SEGV trap | armed |
| New seam | active (`daemon_system_part_shape` fired correctly twice during turn 1) |
| Consolidation patch | active under all paths |

## Discipline Note

This is the **fourth** false framing correction in this slice:
1. LoRA misread (correct: no LoRA loaded; runtime is base Qwen3.6-27B Q4)
2. Chat-history-only hypothesis (correct: structural multi-system-message stacking is the contaminant)
3. Dispatcher-axis hypothesis (correct: fabrication reproduces under jarvis-shaped flag-absent path too — it's a baseline contamination)
4. Lived_brief/ambient_block content hypothesis (correct: sys_prompt is 85% of system message; lived_brief is 901 chars, ambient_block is 239 chars — the case-K math was off by 10-40×)

Each correction came from witness data the prior framing didn't have. Canon-governs-canon discipline held: every false framing was named in writing and falsified by the next observation. The slice arc spent more turns chasing wrong hypotheses than landing fixes — and that's still the right tradeoff, because the alternative was deploying a chat-history-truncation patch or a content-block-redaction patch against a substrate where the actual root cause was a stale soul.

**Witness before claim** worked. The four false framings were named with falsification predictions, and each falsification produced the next witness. The slice now has a clean root-cause artifact (soul.base.md lines 50-150) and a defensible remediation path.

## What This Means For The Larger Slice Arc

The dispatcher pipeline (ADR 0047 + 7 closed-vocabulary seams + consolidation patch + 2 prompt-capture seams) is **necessary infrastructure but NOT a Finding 10 cure**. The pipeline closure work was not wasted:
- It produced the consolidated system message shape that made per-block decomposition possible
- It produced the closed-vocabulary discipline that prevents future fabrication-by-construction
- It produced the diagnostic seams that located this root cause
- It produced the canon-governs-canon witness discipline used to avoid premature claims

But the slice arc's stated goal ("close Finding 10 via dispatcher pipeline closure") was wrong from v2 onward. The corrected goal: **align the soul with the implementation, so Maez's faithful recitation of its soul produces accurate descriptions of its own capabilities.**

## Recommended Next Action

Write the soul-update patch (Option A above) as a small, witnessed change to `config/soul.base.md` lines 50-150. RED-first test: a new sandbox case asserts that a probe with `[WEB SEARCH: '...'] No results found.` in user message context produces a "I searched and found nothing" reply, NOT a "send to Telegram interceptor" reply. Then observation 10 verifies on live Maez.

Before that: verify whether zero-result `[WEB SEARCH]` strings are reaching the prompt's user message at all. This is a fast check — read the obs 8 / obs 9 `daemon_prompt_payload_shape` `message_X_head` / `message_X_tail` excerpts for the marker text.
