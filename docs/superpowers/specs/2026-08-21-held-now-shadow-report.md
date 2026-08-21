# Held-now — shadow report (day 1) and flip recommendation

Status: REPORT. Decision owed to the owner before
`MAEZ_HELD_NOW_ENABLED=1` is added at the next restart.

## 1. What ran

Live process pid 386011, flags read from `/proc/<pid>/environ` (not
from a file — merged ≠ activated doctrine):

- `MAEZ_HELD_NOW_SHADOW=1` — armed
- `MAEZ_HELD_NOW_ENABLED` — **absent** (organ correctly dormant)
- `MAEZ_LIVE_THREAD_ANCHOR=1` — **on**, and this matters (§3)

Receipts: 26 `held_now_shadow` lines in `logs/maez.log*`, window
2026-08-20 13:05:06 → 15:55:37. Two are non-telegram synthetic
surfaces (`surface_A`, `surface_B`, `turn_kind` unresolved/B_STATE)
and are excluded. **24 live telegram turns** remain.

## 2. Raw receipt distribution (24 live turns)

| Field | Values |
|---|---|
| `final_reply_path` | `focused` 24/24 |
| `ineligible_reason` | `None` 24/24 (every turn was eligible) |
| `fail_safe_legacy` | `False` 24/24 |
| `date_cue` | `False` 24/24 |
| `needs_dialogue` | `True` 12, `False` 12 |
| `pairs_available` | `3` 24/24 |
| `pairs_in_set` | `2` on 12 turns, `1` on 12 turns |
| `would_change` | **`True` 24/24** |

Receipt emitter: `def _held_now_whole_turn(fn)` at
`daemon/maez_daemon.py:3325`. Counterfactual computation at
`daemon/maez_daemon.py:8760` — `would_change = len(_cf_pairs) > _actual`.

## 3. The correction — what "would_change=True 24/24" actually means

Read alone, 100% would-change reads like a dramatic finding. It is
not. It is close to true by construction, and the magnitude field is
misleading on half the turns.

The presence rule is at
`core/routing/focused_cognition.py:1419` (`if held_now_enabled():`):

- **Today** (held-now off, `MAEZ_LIVE_THREAD_ANCHOR=1` on): the
  `elif` branch at `:1429` seeds `limit_pairs=2`; when the turn is
  dialogue-authoritative or date-cued, `:1442` trims to `anchors[:1]`.
  → 2 pairs normally, 1 pair on authoritative turns. This exactly
  reproduces the observed `pairs_in_set` split of 12×2 / 12×1.
- **With held-now enabled**: `:1428` seeds `limit_pairs=3`, and the
  same `:1442` trims to `anchors[:2]` on authoritative turns.
  → 3 pairs normally, 2 pairs on authoritative turns.

The shadow counterfactual calls `dialogue_anchor_items(..., limit_pairs=3)`
and never applies the `:1442` trim. So `pairs_available=3` is a
**pre-trim** number, not the count the enabled path would actually
seed. On the 12 authoritative turns the enabled path would seed 2, not
3; the receipt implies a delta of +2 where the real delta is +1.

**Corrected finding: held-now ENABLED adds exactly one additional
dialogue pair per turn — 24 out of 24 observed turns, uniformly.**
Direction confirmed, magnitude halved on half the sample.

## 4. What the shadow cannot tell us

The counterfactual measures *difference*, never *benefit*. Nothing in
these 24 receipts speaks to whether one more pair of recent dialogue
produces a better-held now, and the shadow has no quality axis to
consult (`reason`, `domain`, `pairs_rendered` were `None` on every
line — the allocation block is only populated on the enabled path).

There is also a live counter-consideration visible in the code, not in
the receipts: `:1419` makes presence unconditional whenever history is
non-empty — the "now is HELD, not classifier-gated" design choice. On
the 12 turns where `needs_dialogue=False`, the organ will seed dialogue
anchors into turns the continuity classifier judged not to need them.
That is the intended design (holding the now rather than detecting it),
but it is precisely where over-seeding would first appear.

## 5. Recommendation

**Flip, with a named witness — not on the strength of `would_change`.**

Rationale: the delta is small (+1 pair), uniform, fully reversible by
removing one environment variable, and the organ is already exercising
the whole eligible path (24/24 `focused`, zero ineligible, zero
fail-safe fallbacks) — the plumbing is witnessed. Holding it in shadow
longer accumulates more of the same non-quality-bearing evidence.

Conditions attached to the flip:

1. **Sampling sentinel witness** (already the agreed post-flip step):
   confirm on the live process that the enabled path seeds the counts
   §3 predicts — 3 pairs on non-authoritative turns, 2 on
   authoritative — read from receipts, not from code.
2. **Watch the `needs_dialogue=False` half.** If replies on those
   turns start dragging in stale thread material, that is the
   over-seeding failure and the flag comes back off same-day (seam
   revert, no cooling-off needed).
3. **Fix the counterfactual field before it is trusted again.**
   `pairs_available` should apply the `:1442` trim so the receipt
   reports the enabled-path count. Filed as a follow-up; it is a
   measurement-honesty defect, not a behavior defect, so it does not
   block the flip — but the current field must not be cited as
   evidence in any later gate.

## 6. Follow-up filed

- `held_now_shadow.pairs_available` is pre-trim and overstates the
  enabled-path seed count on dialogue-authoritative turns
  (`daemon/maez_daemon.py:8748` vs the trim at
  `core/routing/focused_cognition.py:1442`). Correct it, then the
  field is safe to cite.
