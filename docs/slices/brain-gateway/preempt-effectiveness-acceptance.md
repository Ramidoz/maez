# Brain Gateway Preempt-Effectiveness Acceptance Gate

Date: 2026-06-01

This is the owner-run gate after the socket-level transport lands. It verifies
that foreground owner recall can preempt an in-flight background llama.cpp eval
through the Brain Gateway and then measures whether the resulting full answer
clears the A7 ceiling. This is not a recall default-on flip.

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

- Gateway handoff is fast: `brain_gateway_preempt_probe` reports
  `handle_state=present`, the background cycle logs `preempted=true`, and the
  foreground `owner_recall` `wait_ms` stays within about 1.5 seconds.
- Physical server release is not the same metric as gateway handoff; read it
  from the collision turn's full latency / `foreground_wall_ms` against A7.
- No `preempt_timeout=true`.
- No background retry caused by `BrainPreempted`.
- No partial cancelled cognition is stored.
- Six-prompt smoke remains scoreboard-honest.
- Full-answer p95 stays under the A7 ceiling.
- Maez voice and inner-life cadence remain acceptable to Rohit.

Any miss keeps recall off.
