# Brain Gateway Preempt-Effectiveness Acceptance Gate

Date: 2026-06-01

This is the owner-run gate after the socket-level transport lands. It verifies
that foreground owner recall can make an in-flight background llama.cpp eval
yield the single llama-server slot quickly. This is not a recall default-on
flip.

## Procedure

1. Start from the normal legacy posture.
2. Temporarily enable the monitored smoke posture: recall triad on, v2 citation
   rendering on, receipt on, autonomous cycles active.
3. Seed one continuity marker turn, then run the frozen six-prompt smoke.
4. Force or wait for a cycle collision during at least one foreground recall.
5. Capture `brain_gateway_event`, `brain_gateway_preempt_probe`,
   `focused_synthesis_timing`, and `recall_outcome` log lines for the window.
6. Revert immediately to legacy posture and confirm `recall_stack mode=legacy`.

## Pass Bar

- Background socket abort releases the slot within about 1.5 seconds.
- Background cycle logs `preempted=true`.
- No `preempt_timeout=true`.
- No background retry caused by `BrainPreempted`.
- No partial cancelled cognition is stored.
- Six-prompt smoke remains scoreboard-honest.
- Full-answer p95 stays under the A7 ceiling.
- Maez voice and inner-life cadence remain acceptable to Rohit.

Any miss keeps recall off.
