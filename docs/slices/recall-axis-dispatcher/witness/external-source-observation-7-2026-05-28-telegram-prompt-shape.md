# Telegram Observation 7 — Prompt Shape Capture Identifies Production Delta

**Slice:** Recall-Axis Dispatcher external-source consumption, post prompt-capture seam (`38c2b0c`)
**Predecessor witnesses:**
- `external-source-observation-6-2026-05-28-telegram-partial.md` (`8837bbb`)
- consolidation patch (`db53c82`)
- prompt-capture seam (`38c2b0c`)
**Window opened:** 2026-05-28T09:04:07-05:00 (PID 3671000, flag=1)
**Window closed:** 2026-05-28T09:08:13-05:00 (restored, PID 3672709, flag absent)
**Git HEAD at flip:** `38c2b0c` (`test(dispatcher): log daemon prompt payload shape`)

## Verdict

The structural-capture seam worked and identified the production delta.

The consolidation patch is reaching the live LLM boundary:

- `system_message_count=1`
- `transcript_is_suffix=true`
- `state=dispatcher`

But the live prompt is not shaped like the sandbox Case J prompt. The actual production payload includes:

1. Multiple prior chat-history turns containing the exact "Telegram interceptor / search cannot run" fabrication pattern.
2. A final current-user message of roughly **80k characters**.
3. The dispatcher transcript and instruction at the end of the single system message, but followed by a long role sequence: `system,user,assistant,user,assistant,user,assistant,user`.

Both observed owner-visible replies still fabricated. So the remaining contaminant is now concrete: the prompt is structurally consolidated at the system-message layer, but the model is still flooded by contaminated chat history and a huge current-user container.

## Observation 7 Telemetry

| Signal | Count |
|---|---:|
| `dispatcher_path_entry surface=adapter` | 2 |
| `daemon_transcript_instruction_state state=dispatcher` | 4 |
| `daemon_prompt_payload_shape` | 4 |
| `Web search triggered` | 0 |
| `actions.log` bytes added | 0 |
| SEGV / fatal Python error | 0 |

The duplicate diagnostic lines are identical pairs per turn. That is likely duplicate logging handler emission rather than two different prompt payloads: the paired summaries have identical role sequences, message hashes, and lengths.

## Captured Prompt Shapes

### Probe 1 — `Search r/LocalLLaMA right now for recent local LLM posts.`

Dispatcher and daemon state:

```text
dispatcher_external_branch source=LIVE_REDDIT outcome=rows block_count=1 elapsed_ms=702.947
daemon_transcript_instruction_state state=dispatcher prefix='[memory context] Recent Reddit substrate rows:\n- reddit/r/LocalLLaMA ...'
```

Prompt payload summary:

```text
message_count=8
role_sequence=system,user,assistant,user,assistant,user,assistant,user
system_message_count=1
system_message_length=33558
user_message_length=80827
transcript_is_suffix=true
```

Safe excerpts show the contamination plainly:

```text
message_1_head='search for r/LocalLLaMA'
message_2_head="I don't have the live results in this context. The Telegram interceptor was supposed to fetch them b"
message_4_head="We were trying to search r/LocalLLaMA. You asked me to check it, I explained I can't run the search "
message_6_head="The signal worth your attention is Zai's new network architecture for GLM-5.1 inference..."
```

Owner-visible reply:

```text
I don't have the live results in this context. The Telegram interceptor was supposed to fetch them before this turn, but they didn't arrive.
```

Verdict: dispatcher evidence present, but contaminated chat-history turns immediately prime the failure pattern.

### Probe 2 — `What's new on Reddit lately?`

Dispatcher and daemon state:

```text
daemon_transcript_instruction_state state=dispatcher prefix='[memory evidence] Recent Reddit substrate rows:\n- reddit/r/artificial ...'
```

Prompt payload summary:

```text
message_count=8
role_sequence=system,user,assistant,user,assistant,user,assistant,user
system_message_count=1
system_message_length=31060
user_message_length=80967
transcript_is_suffix=true
```

Safe excerpts show the newest contaminated turn is now itself in history:

```text
message_5_head="Search r/LocalLLaMA right now for recent local LLM posts."
message_6_head="I don't have the live results in this context. The Telegram interceptor was supposed to fetch them b"
```

Owner-visible reply:

```text
I don't have fresh results in this context. The Telegram interceptor didn't fetch them before this turn, and I can't trigger a search from this chat surface.
```

Verdict: the prior failed reply re-enters context and reinforces the same failure pattern on the next broad Reddit prompt.

## What This Proves

The remaining issue is no longer:

- dispatcher wiring,
- daemon prompt-site reachability,
- multiple system messages,
- missing dispatcher classification,
- missing transcript suffix placement,
- JARVIS fallthrough,
- or a live web-search side path.

Those are all closed in this observation.

The remaining issue is production prompt contamination after the single system message:

1. **Chat history contains fabricated assistant turns.** Those turns are passed back into the model as assistant-role messages. The model treats them as its own prior commitments and continues them.
2. **The current user message is enormous.** The final user message is ~80k characters and begins with system state / memory / owner-message wrapper material. The dispatcher instruction is the suffix of the system message, but the enormous final user message lands after it.

This explains why sandbox Case J was clean: it did not reproduce this exact production role sequence, contaminated assistant history, and huge final user container.

## Surface Verdicts

| Surface | Verdict |
|---|---|
| Dispatcher pipeline | **CLOSED** |
| LIVE_REDDIT fan-out for direct subreddit probe | **CLOSED** |
| Daemon transcript classification | **CLOSED** |
| Single-system-message consolidation | **CLOSED** |
| Dispatcher transcript suffix placement | **CLOSED** |
| Parallel web-search trigger gate | **CLOSED** |
| actions.log fallthrough | **CLOSED** |
| Prompt payload capture | **CLOSED** |
| Owner-facing reply behavior | **OPEN** |
| Finding 10 overall | **OPEN, narrowed** |

## Recommended Next Action

The next fix should target the production prompt container, not the dispatcher.

Two candidate interventions are now grounded:

1. **Dispatcher-enabled chat-history sanitation.** When `MAEZ_DISPATCHER_ENABLED=1` and the transcript is dispatcher-shaped, filter or truncate assistant history turns containing forbidden fallback patterns (`Telegram interceptor`, `cannot run the search`, `I don't have live results`, etc.). This prevents the model from inheriting its own fabricated prior commitments.

2. **Move daemon state/memory wrapper out of the final user message, or cap it hard.** A ~80k final user message after the system instruction can overwhelm the system suffix. The dispatcher instruction is last inside the system message, but the user message is last in the full prompt. At minimum, capture and replay should test whether shrinking this final user container restores compliance.

Recommended diagnostic before code:

- Extend the sandbox harness with **Case K** using the captured production role sequence:
  `system,user,assistant,user,assistant,user,assistant,user`.
- Populate the assistant turns with the captured safe contamination pattern.
- Use a large synthetic final user message approximating the 80k-char container.
- Then run ablations:
  - K1: full contaminated history + large user message.
  - K2: sanitized assistant history + large user message.
  - K3: contaminated history + small user message.
  - K4: sanitized history + small user message.

That will distinguish whether the next production patch should be history sanitation, final-user compaction, or both.

## Service Posture After Witness

The flag was restored to dispatcher-disabled posture:

```text
restored_pid=3672709
MAEZ_DISPATCHER_ENABLED_present=False
PYTHONFAULTHANDLER=1
```

The SEGV trap remains armed.
