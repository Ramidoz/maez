# Held-now ENABLED + action-lane SHADOW — post-restart witness

Owner restarted with `MAEZ_HELD_NOW_ENABLED=1` and
`MAEZ_ACTION_LANE_SHADOW=1`, both confirmed in `/proc/<pid>/environ`
(not from a config file — merged is not activated). Four owner turns
followed.

## 1. Held-now: the sampling sentinel PASSES, exactly as predicted

Yesterday's shadow report predicted, from reading the code **before the
flag was on**: 3 dialogue pairs on ordinary turns, trimmed to 2 on
dialogue-authoritative turns.

Live receipts after the flip:

| trace | turn_kind | pairs_rendered |
|---|---|---|
| `0f66a58e` | ordinary | **3** |
| `8f052be6` | ordinary | **3** |
| `c9af0fb6` | continuity | **2** |
| `e1197cc3` | continuity | **2** |

**3 and 2, on the nose.** Every pre-flip receipt shows
`pairs_rendered=None` because the allocation block only populates on
the enabled path — which is itself confirmation that the enabled path
is the one now running.

`domain=full_count` is now populated where it was `None` throughout the
shadow day. `pairs_available` / `pairs_in_set` / `would_change` are
correctly `None`: the counterfactual block runs only under
`if not _held_now_on()`, so with the organ enabled there is nothing to
counterfactualise. That also retires the overstatement filed
yesterday — the misleading field is no longer computed at all.

## 2. Action lane shadow: the number that matters is 0

Four ordinary conversational turns, four receipts, all identical in the
only fields that matter:

```
action_lane_shadow intent=none would_run_jarvis=False
                   detector_floor=syntactic_v1 surface=telegram_surface
```

**False-positive rate: 0/4.** The intent detector did not fire on any
ordinary turn — including one containing "I got busy with work" and one
containing "Go get that rest", both of which are verb-bearing sentences
that a naive detector would have caught. The syntactic floor and its
exclusions are holding.

This is the number the whole Phase-2 gate was about. Four turns is a
start, not a result; it wants a day.

## 3. Turn-sequence store: created on first admitted turn, working

```
conversation_seq:   telegram_text / <chat> / 4
event_assignments:  update:...178 -> 1
                    update:...179 -> 2
                    update:...180 -> 3
                    update:...181 -> 4
```

Created only after the first turn (absent before it, as designed),
channel key `telegram_text` as specified, sequential, and keyed by
Telegram update id so a redelivery cannot double-count.

## 4. Known defect confirmed, unchanged

Every receipt is emitted twice (2 log lines per `trace_id`). This is
the double-logging handler bug already on the follow-ups ledger. It
does not affect behavior or the counts above — the analysis
de-duplicates by `trace_id` — but it should be fixed before any
receipt-rate statistic is quoted.

## Verdict

Both flips behave exactly as designed and predicted. Nothing to revert.

Watch item, unchanged from the shadow report: the ordinary turns now
receive 3 anchor pairs whether or not the continuity classifier thought
dialogue was needed — that is the "hold the now rather than detect it"
choice. If replies begin dragging in stale thread material, that is
over-seeding and the flag comes off the same day.
