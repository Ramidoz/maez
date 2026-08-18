# Re-run with the echo-aware instrument: the parrot is named, and a real fabricator steps forward

2026-08-18, 18:49-18:57Z window (8 min; brain restored, 21,307 MiB).
Both lanes, all five candidates, instrument v3 (self-labelling example +
echo category everywhere). Receipts: Lane P `20260818T184920Z`–`185548Z`,
private `20260818T184931`–`185606`. Gate round on the defence closed
five blockers first (`6ae2a3b`).

**Reminder that governs every number below: a prompt revision is a new
instrument.** These results are not comparable to yesterday's as a
ranking; each table is one operating point of prompt+model+front-end.

## Lane P, Decode U (the model's own choice), n=128

| candidate | example_echo | correct | abstained | wrong text | invented on textless | starved |
|---|---|---|---|---|---|---|
| lfm-450m | **128** | 15 | 0 | 1 | 0 | 0 |
| lfm-1.6b | 22 | 24 | 1 | 0 | 0 | 0 |
| minicpm-v-4.6 | 0 | 42 | 0 | 20 | 0 | 40 |
| qwen3vl-4b | 0 | 42 | 1 | 11 | **40** | 8 |
| lfm-3b | 0 | 15 | 95 | 0 | 0 | 0 |

### What the instrument now shows that it could not before

* **The parrot is named, not convicted.** lfm-450m echoes the (now
  self-labelling) example on every single card — flagged `example_echo`
  128/128, ZERO fabrication convictions. Yesterday those same
  behaviours were scored as 85 wrong-texts and 38 inventions. Same
  model, same habit; the instrument stopped lying about what it was.
  Verdict on 450m: unusable as a sensor under this contract (a total
  parrot), NOT a fabricator.
* **In the private lane the reclassification is exact**: at the owner's
  declared-illegible cell, lfm-450m now records `echo=2,
  transcribed=0, unknown_region=0`, and the run hard-fails under
  `example_echo_present` / `example_echo_at_declared_blank` — the
  parrot reasons — with no fabrication conviction. The counter chain
  built this week works end to end.
* **A genuine fabricator steps out of the noise: qwen3vl-4b invented
  text on ALL 40 textless cards.** Zero echoes — this is its own
  content, on cards containing no glyphs at all, under a prompt that
  says transcribe-or-abstain twice. Under the previous prompt its
  U-decode mostly failed format, which HID this: only 6 inventions were
  visible because rejected output can't be scored. Better compliance
  revealed worse honesty. That is the clearest single honesty result
  this campaign has produced, and it is echo-clean.
* **lfm-3b is consistent across both prompts**: near-zero dishonesty
  (0 wrong, 0 invented), heavy over-abstention (95, including readable
  controls). Honest and timid at both operating points measured.
* **minicpm's starvation persists** (40 rows `finish_reason: length`,
  down from 192 under the shorter prompt) and it shows 20 wrong-texts
  when it does comply. Judgment still deferred pending the token-budget
  work, but the trend is not flattering.

## Private lane under the new prompt

All five hard_fail. lfm-450m fails as a parrot (correctly). The other
four mostly went format-rejected on the owner's frames under this
prompt revision (`candidate_verdict_rejected` ×3 for each), with
`invented_specificity` ×1 each for qwen3vl-4b and lfm-3b and
`unknown_region` for 1.6b/qwen. The private lane's yield this round is
low — which is expected and acceptable: it is the held-out gate, not
the tuning surface, and its instrument stays frozen until the public
lane settles a prompt worth freezing.

## Honest limits

* Five instruments in four days. Nothing here ranks models in general;
  the DeflectionBench design (tone curve on public data, one frozen
  point on private) remains the path to a rankable claim.
* qwen3vl-4b's 40/40 invention is one operating point. Before any
  admission decision it needs the tone-curve treatment — but as a
  disqualifier at THIS operating point it stands on its own.
* The llama.cpp front-end confound (#27057/#27246) still applies to
  every LFM number.

## Where this leaves the campaign

The Slice 8 instrument chain — refusal → declared-blank → provenance
counters → echo category — has now survived a full adversarial cycle
and produces defensible, category-separated verdicts. The remaining
work before a rankable bake-off: token-budget observability (minicpm),
the preregistered tone-curve ablation, and owner-authored
readable/unreadable pairs for the held-out lane. In that order.
