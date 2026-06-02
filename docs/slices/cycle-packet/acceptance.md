# Cycle Focused-Cognition Packet Acceptance

This is an owner-run witness for `MAEZ_CYCLE_FOCUSED_ENABLED=1`. It is not a recall flip.
Recall posture remains a separate decision.

## Purpose

The packet path replaces the daydream cycle's dynamic megaprompt with a bounded,
provenance-tagged evidence packet while preserving the static soul/system block.
The intended effect is lower cycle prefill cost and sharper reflection without
thinning Maez's inner life.

## Procedure

1. Confirm the daemon is on the expected branch/build and recall is in the
   intended posture.
2. Set `MAEZ_CYCLE_FOCUSED_ENABLED=1` in the launch environment.
3. Restart Maez.
4. Let several normal cognition cycles run.
5. Inspect `cycle_packet_shape` events in `logs/maez.log`.
6. Read the generated cycle reflections and compare them to nearby legacy
   cycle quality.
7. Set `MAEZ_CYCLE_FOCUSED_ENABLED=0` and restart if any acceptance condition
   misses.

## Expected Evidence

`cycle_packet_shape` is content-free and should expose only aggregate shape:

- `schema_version`
- `packet_tokens_est`
- `legacy_tokens_est`
- `evidence_item_count`
- `source_types`
- `prefill_ms`
- `cycle_outcome`
- `fallback_reason`

Expected live shape:

- Dynamic packet around 2k-4k tokens, target near 3k.
- Prefill around 2s-3s, compared with the prior roughly 16s dynamic dump.
- `fallback_reason` absent or empty during normal operation.
- Source types include the evidence Maez actually has, especially
  `signal_absence` when a signal is unavailable.

## Quality Bar

Pass only if all are true:

- Reflections remain coherent and in voice.
- Silent cycles remain honestly silent when the packet has no worthwhile
  thought.
- `signal_absence` is treated as absence, never narrated as presence.
- Action outcomes, open loops, quality signals, and memory context are not
  crowded out by one large source.
- Reflections cite or refer through packet evidence rather than laundering an
  ungrounded summary.
- No regression in cycle health, retry behavior, or foreground responsiveness.

## Rollback

Any miss means the witness fails. Flip `MAEZ_CYCLE_FOCUSED_ENABLED=0`, restart,
and treat the legacy megaprompt as the safe resting state.
