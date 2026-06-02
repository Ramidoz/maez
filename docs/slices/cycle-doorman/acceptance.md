# Cycle Salience Doorman Acceptance

Owner-run witness for `MAEZ_CYCLE_DOORMAN_ENABLED=1`. This is not a default-on
flip. The resting state is flag off.

## Purpose

Prove the deterministic doorman reduces redundant deep-brain cycle calls without
making Maez conditional on Rohit's presence and without missing genuinely
salient moments.

## Preflight

- `MAEZ_RECALL_TRIAD_ENABLED=0`.
- `MAEZ_CYCLE_FOCUSED_ENABLED` stays at the owner's chosen resting value.
- `MAEZ_CYCLE_DOORMAN_ENABLED=1` only for this witness.
- Maez is otherwise on the same branch/build as this slice.

## Capture

Collect several real cycles, then read:

```bash
grep "doorman_verdict" logs/maez.log | tail -20
grep "doorman_skip" logs/maez.log | tail -20
grep -E "reasoning_model|HEARTBEAT_OK|Cycle [0-9]+ response" logs/maez.log | tail -80
```

## Pass Bar

- Quiet, unchanged cycles emit `doorman_skip` and do not enter
  `reasoning_model`.
- Salient signals wake: failures, new open wants, memory deltas,
  signal-availability transitions, scheduled maintenance, perception deltas,
  and the min-floor probe.
- Reason-code distribution is sane: repeated skips are
  `skip_nothing_salient`; wakes have closed `wake_*` reason codes.
- The floor still wakes periodically, and after a floor wake that returns
  `HEARTBEAT_OK`, later quiet cycles skip again instead of latching into
  every-cycle wake.
- Presence does not decide wake/skip. Presence may appear in surrounding
  perception telemetry, but presence alone must not produce a wake and absence
  must not suppress a salient wake.
- Telemetry is content-free: booleans, counts, closed reason codes, and closed
  signal-class names only. No thought, memory, screen, or user text.

## Fail Bar

Any of these sends the system back to flag off:

- A real failure, new want, memory delta, signal-availability transition,
  scheduled due event, perception delta, or min-floor probe is skipped.
- Presence alone wakes the deep brain, or absence prevents a salient wake.
- The floor latches and wakes every cycle after a `HEARTBEAT_OK`.
- Telemetry contains thought, memory, screen, or user text.
- Maez's inner life appears silent rather than quiet: no periodic floor probes.

## Rollback

Set `MAEZ_CYCLE_DOORMAN_ENABLED=0` in the owner-local environment and restart
`maez.service`. The flag-off path delegates to the legacy perception-signature
gate.
