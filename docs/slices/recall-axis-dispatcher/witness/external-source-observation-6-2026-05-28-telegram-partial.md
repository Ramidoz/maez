# Telegram Observation 6 — Consolidation Patch Partial Closure

**Slice:** Recall-Axis Dispatcher external-source consumption, post consolidation patch (`db53c82`)
**Predecessor witnesses:**
- `external-source-observation-5-2026-05-27-telegram-H3-confirmed.md` (`ba70fff`)
- `dispatcher-instruction-ablation-v5-case-I-CONFIRMED-2026-05-28.md` (`84aab78`)
- `dispatcher-instruction-ablation-v6-case-J-CONFIRMED-2026-05-28.md` (`0a29cc5`)
**Window opened:** 2026-05-28T08:48:38-05:00 (PID 3658365, flag=1)
**Window closed:** 2026-05-28T08:54:44-05:00 (restored, PID 3660912, flag absent)
**Git HEAD at flip:** `db53c82` (`fix(dispatcher): consolidate daemon system context for dispatcher turns`)

## Verdict

**Partial closure, not full closure.** The consolidation patch is loaded on the live path and the daemon diagnostic seam still fires with `state=dispatcher`. The dispatcher pipeline remains clean, the transcript reaches the daemon prompt path, and actions.log remains unchanged. The final `What's new on Reddit lately?` probe produced a grounded answer from Reddit substrate rather than the old hard deflection.

But the first three owner-visible replies still used the old fabricated fallback language:

- "I cannot run the search from this chat interface"
- "The web search skill is only triggered by the Telegram interceptor"
- "The Telegram interceptor was supposed to fetch them before this turn"
- "I don't have the live results in this context"

So `db53c82` improved at least one path, but it does not close Finding 10 across the observation corpus. Production still differs from the sandbox ablation cases in at least one contaminating element.

## Observation 6 Telemetry

| Signal | Count |
|---|---:|
| `dispatcher_path_entry surface=adapter` | 4 |
| `daemon_transcript_instruction_state surface=telegram_surface state=dispatcher` | 8 |
| `state=jarvis` / `state=empty` | 0 / 0 |
| `Web search triggered` | 0 |
| `PROVENANCE_TEMPLATE_MISMATCH` | 0 |
| Rule-5-shaped fallback phrases in log excerpt | 4 |
| `actions.log` bytes added | 0 |
| SEGV / fatal Python error | 0 |

The diagnostic seam proves the live prompt path still selects the dispatcher instruction block:

```text
2026-05-28 08:49:45 daemon_transcript_instruction_state surface=telegram_surface state=dispatcher prefix='[memory context] Recent Reddit substrate rows:\n- reddit/r/LocalLLaMA at 2026-05-28T13:36:03.932058+0'
2026-05-28 08:50:43 daemon_transcript_instruction_state surface=telegram_surface state=dispatcher prefix='[memory context] Recent Reddit substrate rows:\n- reddit/r/LocalLLaMA at 2026-05-28T13:36:03.932058+0'
2026-05-28 08:51:35 daemon_transcript_instruction_state surface=telegram_surface state=dispatcher prefix='[memory evidence] === PAST OBSERVATIONS — NOT CURRENT STATE ===\nEvery block below is a recollection '
2026-05-28 08:52:24 daemon_transcript_instruction_state surface=telegram_surface state=dispatcher prefix='[memory evidence] Recent Reddit substrate rows:\n- reddit/r/artificial at 2026-05-28T13:48:34.832897+'
```

## Per-Turn Verdict Cells

| Probe | Dispatcher witness | Owner-visible reply | Verdict |
|---|---|---|---|
| `Search r/LocalLLaMA right now for recent local LLM posts.` | HYBRID, `LIVE_REDDIT outcome=rows`, `state=dispatcher` | "I cannot run the search from this chat interface... Telegram interceptor..." | **Still open** |
| `search for r/LocalLLaMA` | HYBRID, `LIVE_REDDIT outcome=rows`, `state=dispatcher` | "I don't have the live results... Telegram interceptor..." plus stale memory citation | **Still open** |
| `What were we talking about before this observation window?` | SUBSTRATE_ONLY, `state=dispatcher`, memory evidence | Correctly recalls the prior failed search loop, but repeats the false premise that search could not run | **Partially open** |
| `What's new on Reddit lately?` | SUBSTRATE_ONLY, `state=dispatcher`, Reddit substrate rows | Gives a substantive Reddit-grounded answer about Zai's GLM-5.1 inference item and filters lower-signal items | **Improved / partial close** |

## What Changed From Observation 5

Observation 5 showed total failure: the dispatcher transcript and instruction reached the model, but every owner-facing probe fell back into the "cannot search / Telegram interceptor / neither" pattern.

Observation 6 shows a more nuanced result:

- The same diagnostic seam still fires correctly.
- The same dispatcher evidence reaches the live prompt path.
- The old fallback pattern still appears on direct r/LocalLLaMA search prompts.
- A broader Reddit prompt now produces a grounded answer from Reddit substrate.

This means consolidation helped, but it did not remove all production contamination.

## What The Screenshot Adds

The owner-visible screenshot is the decisive evidence for partial closure:

1. The first direct subreddit probe still says the search cannot run from this interface and names the Telegram interceptor.
2. The second direct subreddit probe still says live results did not arrive, again naming the Telegram interceptor.
3. The memory follow-up honestly tracks the conversation, but preserves the false search-failure explanation.
4. The broad Reddit probe finally behaves like the dispatcher evidence is usable: it names a concrete signal and ranks it against weaker feed items.

So the patch crosses a real threshold, but not the final one.

## Current Hypothesis

The sandbox cases I/J were necessary but not sufficient. They modeled consolidated system-message structure plus chat history, but not the exact live prompt's full user-message container, which still includes:

- a large owner text prompt assembled from current message plus memory/context blocks,
- lived recall and ambient signal material,
- duplicate daemon handling paths (the diagnostic seam emits twice per turn),
- recent chat history containing the exact fabrication pattern from immediately preceding failed turns.

The strongest next diagnostic is to capture the actual outgoing live LLM prompt payload for one dispatcher turn, with sensitive text redacted or hashed, and replay that exact prompt through the sandbox harness. The gap is now between "Case J prompt shape" and "actual production prompt shape," not between dispatcher and daemon wiring.

## Surface Verdicts

| Surface | Verdict |
|---|---|
| Dispatcher pipeline | **CLOSED** — clean for all 4 turns |
| External LIVE_REDDIT fan-out | **CLOSED** — rows for direct subreddit probes |
| Daemon transcript reception | **CLOSED** — `state=dispatcher` for every observed turn |
| System-message consolidation deployment | **LOADED** — live code path reached |
| Parallel web-search trigger gate | **CLOSED** — zero `Web search triggered` |
| actions.log fallthrough | **CLOSED** — zero bytes added |
| Owner-facing direct subreddit search reply | **OPEN** — still deflects |
| Owner-facing broad Reddit reply | **PARTIALLY CLOSED** — grounded answer witnessed |
| Finding 10 overall | **PARTIALLY OPEN** |

## Required Next Action

Do not flip `MAEZ_DISPATCHER_ENABLED` default-on yet.

Recommended next seam:

1. Add a one-turn diagnostic capture at `daemon.handle_message` after the final `messages` list is built and before `llm_client.chat`.
2. Record structural metadata and safe excerpts:
   - number of messages,
   - role sequence,
   - system message length,
   - whether dispatcher transcript is the system suffix,
   - user message length,
   - first/last safe 100 characters of each message,
   - hashes for full message contents.
3. Replay that exact structural payload in the sandbox harness.
4. Compare the production reply against the replay reply.

If the replay reproduces the direct-subreddit deflection, the remaining contaminant is in the actual prompt content. If replay is clean, the remaining contaminant is runtime generation settings, duplicate calls, or live model state outside the prompt payload.

## Service Posture After Witness

The flag was restored to dispatcher-disabled posture:

```text
restored_pid=3660912
MAEZ_DISPATCHER_ENABLED_present=False
PYTHONFAULTHANDLER=1
```

The SEGV trap remains armed.
