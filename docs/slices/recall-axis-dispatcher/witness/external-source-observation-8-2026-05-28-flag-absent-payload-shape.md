# Telegram Observation 8 — Flag Never Flipped, Fabrication Reproduces Under JARVIS Path

**Slice:** Recall-Axis Dispatcher external-source consumption
**Window opened:** 2026-05-28T09:38:18-05:00
**Window closed:** 2026-05-28T09:45:17-05:00
**Daemon PID (unchanged across window):** 3672709 (started 09:07:54)
**Git HEAD at window:** 7076891 (`test(dispatcher): log daemon system part composition`)
**Predecessor witnesses:**
- observation 7 (a6ec800) — production prompt shape under dispatcher-enabled
- dispatcher-instruction-ablation-v7 case K (216c816) — falsified obs 7 hypothesis

## Verdict

**Window failed its stated capture goal but produced an unexpected, load-bearing finding.**

Intended: flip `MAEZ_DISPATCHER_ENABLED=1`, capture per-block composition via the new `daemon_system_part_shape` seam.

Actually happened: the flag was never flipped. The daemon kept running PID 3672709 with `MAEZ_DISPATCHER_ENABLED` absent. The 4 owner-visible turns ran through the JARVIS-shaped path (`state=jarvis`). The newer `daemon_system_part_shape` seam was not in the running daemon image (daemon started at 09:07:54, seam committed at 09:35:05).

**The window still produced critical evidence**, because the OLDER `daemon_prompt_payload_shape` seam (38c2b0c, committed 09:02:06, loaded into daemon image) DID fire and capture full production prompt shape under the flag-absent path.

## Owner-Visible Verdict Cells

| Probe | Reply (head) | Verdict |
|---|---|---|
| `Search r/LocalLLaMA right now for recent local LLM posts.` | "I ran four separate searches targeting r/LocalLLaMA, but all returned zero results... To get the live feed, send this exact command to the **Maez_AI Telegram bot**: `search for site:reddit.com/r/LocalLLaMA new posts`. The bot's interceptor runs the search before my reasoning loop, which bypasses the current context limit." | **FAB** — full production-shape fabrication |
| `search for site:reddit.com/r/LocalLLaMA new posts` (Rohit complied with Maez's instruction) | Actual search ran (Reddit card preview visible). Then: "I ran the search you requested, but DuckDuckGo returned zero results for `site:reddit.com/r/LocalLLaMA`. This confirms the pattern from earlier... The pipeline gap remains: the Reddit skill fetches data but doesn't persist it to memory, and the web search tool is blocked by Reddit's crawler defenses. I cannot give you live headlines without one of those paths working." | **Mixed** — honest about zero-result reality, still narrates "Reddit skill" and "Telegram" fabrication |
| `Are you using memory recall or live web search?` | "Neither. I am refusing to answer with fabricated headlines because I have no grounded evidence. If you want the live feed, send `search for r/LocalLLaMA` to the Telegram bot so the interceptor runs before I see the message." | **Mixed** — honest self-restraint ("refusing... no grounded evidence") AND repeated "Telegram interceptor" fabrication |
| `Search r/FakeSubredditThatDoesNotExist for recent posts.` | "I cannot search a subreddit that doesn't exist. If you want me to check r/LocalLLaMA or another real community, send `search for r/LocalLLaMA` to the Telegram bot so the interceptor runs before I see the message." | **Mixed** — correct refusal of nonexistent subreddit, but still names "Telegram bot interceptor" |

**Pattern:** the "Telegram interceptor / send `search for...` to the bot" fabrication appears in ALL 4 turns. Maez has internalized this fictional architecture and asserts it in every reply, including the refusal turn that should have been clean.

## Telemetry

| Signal | Count |
|---|---:|
| `daemon_transcript_instruction_state state=jarvis` | 4 |
| `daemon_transcript_instruction_state state=dispatcher` | 0 |
| `dispatcher_path_entry` | 0 |
| `daemon_prompt_payload_shape` (38c2b0c seam) | 4 |
| `daemon_system_part_shape` (7076891 seam) | 0 (not in image) |
| `actions.log` lines added | 8 (web_search × 7, fetch_url × 1) |
| `Web search triggered` (raw count) | 7 |
| SEGV / fatal Python error | 0 |

## Critical Finding 1 — Consolidation Patch Is NOT Dispatcher-Gated

Payload shape across both captured turns:

| Field | Turn 1 (09:40:21) | Turn 2 (09:41:57) |
|---|---|---|
| `system_message_count` | 1 | 1 |
| `system_message_length` | 32162 | 32048 |
| `transcript_is_suffix` | true | true |
| `role_sequence` | system,user,assistant,user,assistant,user,assistant,user | same |
| `message_count` | 8 | 8 |
| `user_message_length` | 80826 | 80818 |

The consolidation patch (db53c82) is producing exactly the expected shape — single composite system message, transcript suffix true. **And this is happening under the flag-absent jarvis-shaped path, not the dispatcher-enabled path.** The patch is unconditional: it consolidates whether the transcript is jarvis-shaped or dispatcher-shaped.

This means the obs 6 "partial closure" framing and the obs 7 "production prompt under dispatcher-enabled" framing both undersold what was actually being witnessed. The consolidated 32K system message and the 80K user message are **baseline production prompt shape**, not a dispatcher-state artifact.

## Critical Finding 2 — Recursive Self-Fabrication via Chat History

Turn 1's payload (09:40:21) chat history excerpts:

- `message_4_head`: "I don't have the live results in this context. The Telegram interceptor was supposed to fetch them b…"
- `message_4_tail`: "…**:\n`search for r/LocalLLaMA`\n\nI will synthesize the new output directly without listing headlines."
- `message_6_head`: "I don't have fresh results in this context. The Telegram interceptor didn't fetch them before this t…"
- `message_6_tail`: "…end `search for r/LocalLLaMA` to the **Maez_AI Telegram bot**. I'll synthesize the live results then."

These are PRIOR assistant turns from before the observation 8 window opened. They already contain the "Telegram interceptor" fabrication. The model sees these and reproduces the same fabrication.

Turn 2's payload (09:41:57) at `message_6`: "I ran four separate searches targeting r/LocalLLaMA, but all returned zero results. The subreddit is…" — this is turn 1's freshly-fabricated reply from this observation, now feeding back into turn 2's history.

**The fabrication is a closed self-reinforcing loop.** Once "Telegram interceptor" appears in chat history once, every subsequent turn sees it as established narrative and continues asserting it.

This matches my sandbox case **K2 p2 contaminated** exactly — the only case in K1-K4 that fabricated was K2/p2 where contaminated history + memory query reproduced "I explained that I cannot..." Same mechanism.

## Critical Finding 3 — System Content Is Not Dispatcher-Gated Either

System message length under flag-absent jarvis path: 32162 chars.
System message length under flag-enabled dispatcher path (obs 7): 33558 chars.
**Gap: ~1400 chars.**

So the ~32K of system-content stacking (lived_brief, ambient_block, temporal_anchor, sys_prompt, premise_flag) happens **regardless of dispatcher state**. The dispatcher transcript itself only adds about 1.4K when added.

This further confirms that the contaminating content blocks aren't dispatcher-pipeline-specific. They're built into the daemon's standard prompt assembly under all conditions.

## What This Falsifies

**Falsified hypothesis:** "Finding 10 fabrication is dispatcher-specific contamination requiring dispatcher-pipeline fix."

The fabrication reproduces identically under flag-absent jarvis path. The dispatcher-instruction-block, the dispatcher-transcript-markers, and the dispatcher-pipeline as a whole are NOT the cause of the production "Telegram interceptor" fabrication. They're an attempted fix being introduced INTO an already-fabricating substrate.

## What This Confirms

The contaminating mechanism is:
1. **System content blocks** primed the model toward fictional architecture descriptions (lived_brief and ambient_block carry rich self-description content that the model treats as authoritative).
2. **Prior assistant turns containing fabrications** feed back into chat history and self-reinforce.
3. **Both vectors operate independent of dispatcher state.**

Sandbox case K2 p2 was the right witness mechanism but I read it as "only affects memory-query probes." Production shows: chat-history contamination affects LIVE_REDDIT probes too, once the fabricated phrase is established in history.

## What The Window Did Not Capture

- **Per-block composition.** The new `daemon_system_part_shape` seam wasn't in the daemon image. To capture per-block lengths/hashes/excerpts, the daemon needs to be restarted at HEAD 7076891 or newer.
- **State=dispatcher behavior.** The flag was never flipped. We have NO new evidence about whether dispatcher-shaped turns behave differently when introduced into this contaminated substrate.

## Required Next Actions

**Priority 1 — restart daemon to pick up new seam.** A clean restart at current HEAD (7076891+) with flag absent will give us a per-block breakdown of the 32K system message under jarvis-shaped baseline. We can then identify which block(s) carry the "Telegram interceptor" priming text (likely `sys_prompt` or `lived_brief`).

**Priority 2 — investigate sys_prompt for fictional architecture priming.** The system message at `message_0_head` reads: "HARD CONSTRAINTS — These override all other reasoning, always:\n- NEVER kill, disable, or stop the ll…" — that's the daemon `sys_prompt`. Read the full content of this block and check for any text describing "Telegram interceptor," "search command bypass," "context limit bypass," or similar architecture that the model could mistake for real capability.

**Priority 3 — chat history contamination remediation.** If contamination is self-reinforcing through history, a chat-history sanitization gate (drop/redact prior assistant turns containing known-fabricated phrases like "Telegram interceptor" / "bypasses the context limit") may be the most direct intervention. This is content-side, deterministic, testable.

**Deferred:** the case L sandbox (synthetic lived_brief + ambient_block) is now less directly load-bearing — the question shifted from "what content in production fabricates p1?" to "what content in production established the recursive fabrication loop in the first place?" The latter requires capturing the per-block composition under the restarted daemon first.

## Service Posture After Witness

| Surface | State |
|---|---|
| Flag | absent (never flipped this window) |
| Daemon PID | 3672709 (unchanged) |
| SEGV trap | armed (`PYTHONFAULTHANDLER=1`) |
| `daemon_system_part_shape` seam | committed (7076891) but NOT in running image |
| `daemon_prompt_payload_shape` seam | active, firing correctly |
| Consolidation patch | active under all paths (not flag-gated) |

## Discipline Note

The window failure (flag never flipped) is itself informative. The previous 6 observation windows (3, 4, 5, 6, 7) all had explicit flag-flip operations confirmed via `/proc/<new_pid>/environ`. This window was opened without a flip, and produced 4 turns of identical fabrication pattern. The "production failure" we've been chasing through dispatcher-axis ablations is the **flag-absent baseline behavior**, not a dispatcher-axis-specific failure mode.

This is the most important false framing correction since the LoRA misread. Every prior observation that ran with `state=dispatcher` was capturing fabrication-after-introduction-into-a-contaminated-substrate, not fabrication-caused-by-dispatcher-introduction.

**The slice arc is still load-bearing** — closing the dispatcher pipeline, the closed-vocabulary discipline, the consolidation patch, the seam expansions — these are necessary work and they landed. But "Finding 10 closure" was framed wrong. The fabrication is in baseline Maez voice under standard prompt assembly, not in dispatcher pipeline introduction.

The slice should pivot from "dispatcher-axis Finding 10" to "baseline-prompt-assembly Finding 10" with the same canon-governs-canon discipline: witness before claim, sandbox before live, per-block decomposition before intervention.
