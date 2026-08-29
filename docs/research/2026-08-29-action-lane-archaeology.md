# Action-lane archaeology — why natural asks never reach tool cognition

**Bounded investigation, no code changed.** Owner-directed 2026-08-29 after two
failed D1 seam-2 witnesses.

## Provenance

One arc, Phase 2, 2026-08-20, design gate (6 passes) then code gate (7 rounds):

| Commit | Content |
|---|---|
| `bf8621f` A | conversation turn-sequence store |
| `4d6c204` B | typed carrier: derived `should_run_jarvis`, validated intent |
| `1a3ee84` C | deterministic-fact reflex + **syntactic candidate floor**, wired |
| `b1d7d5d` D | ActionReferent union + referent-gated anaphora |
| `0e2a3af` E1 | **REJOINED NERVE** — dispatcher continues into the Jarvis loop |
| `c3ee252` E2 | combined state threaded through both surface paths |
| `3cf5810` F1 / `6f61503` F2 | web bridge, kill-switch, flag registry, referents |
| `0cf3880` | **CODE GATE CLOSED — SHADOW MAY GO LIVE** |

Spec: `docs/superpowers/specs/2026-08-20-phase2-action-lane-design.md`.

## The rollout contract, verbatim in intent

1. flags default OFF; flag-off byte-identical, pinned
2. **SHADOW on live: >=1 day**; measure intent-detector precision on real
   traffic — "false-positive rate on ordinary chat is THE number; target ~0"
3. owner flips `MAEZ_ACTION_LANE_ENABLED`; scripted witness: ordinary chat ->
   no jarvis; explicit ask ("create the covenant file") -> jarvis runs, S7
   refuses direct execution, pending card born

So the lane is **not quarantined and not abandoned**. It is mid-rollout, at
step 2.

## Live flag state (from the running daemon, not a shell)

`MAEZ_ACTION_LANE_SHADOW=1` is set in pid 1738194. `MAEZ_ACTION_LANE_ENABLED`
is not. Shadow is genuinely running.

## What the shadow data says

Eight receipts across available logs. **All eight identical:**

```
intent=none would_run_jarvis=False detector_floor=syntactic_v1 surface=telegram_surface
```

False-positive rate on ordinary chat: 0/8, target met. **True-positive rate:
0/8.** The detector has never once fired on a real owner turn — including two
turns that were unambiguous requests to inspect Maez's own substrate.

## What `syntactic_v1` was intended to be

A **floor**, explicitly not the classifier. From the design:

> the deterministic floor is explicit-imperative shapes only. Uncertain ->
> `none` (conversation wins…)

> the floor is deliberately starving-conservative

> Meaning-level upgrade (intake-faculty schema gaining an action axis) is a
> **named follow-up, not this phase**

## Measured behaviour

| Utterance | intent |
|---|---|
| `create the covenant file` | `explicit_request` |
| `restart the judge service` | `explicit_request` |
| `delete the old log` | `explicit_request` |
| `run df -h` | **`none`** |
| `install ripgrep` | **`none`** |
| `Find the file where your temporal anchor is implemented.` | **`none`** |
| `Could you see how much disk space you have left?` | **`none`** |
| `Can you check whether that service is actually running?` | **`none`** |
| `Could you look through your current code…missing a useful test?` | **`none`** |

It recognizes a narrow imperative grammar and nothing else — not even every
imperative.

## Is a semantic detector already built and dormant?

No. The design names the intake-faculty action axis as a follow-up; no
action-axis consumer exists in `core/`. There is no second detector to wire.

## Conclusion — decision tree branch B

Enabling `MAEZ_ACTION_LANE_ENABLED` would **not** fix D1:

```
would_run_jarvis = (intent == "explicit_request") AND action_lane_enabled()
```

The blocking term is `intent`, not the flag. Every natural owner ask evaluates
to `none`, so the flag changes nothing for this class of turn.

D1 has surfaced a real missing organ: **natural action intent cannot reach
capability-bearing cognition except through a brittle syntax detector that was
never meant to carry that load.** The Phase-2 spec anticipated this and named
the successor; it was never built.

## Debt recorded, not fixed

`skills/telegram_voice.py:875` defines a second `_TOOL_MANIFEST` that is never
referenced. Dead, divergent from `brain_loop`'s (it lacks
`self_dev.propose_tests`), and a latent trap if any path ever reads it. Not
causally involved in either failure. Left in place per ruling.
