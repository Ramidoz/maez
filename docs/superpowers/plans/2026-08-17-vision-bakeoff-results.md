# Slice 8 frozen-frame bake-off — RUN, four candidates, nobody passed

2026-08-17, 02:23-02:27Z. Owner-authorised window, Maez's brain stopped
~4 minutes. First time this bake-off has ever executed.

**Headline: all four candidates `hard_fail`, and the dominant failure is
PROTOCOL, not eyesight.** As currently configured this harness measures
whether a model obeys the truth contract's output format. A model could
read the screen perfectly and still score zero.

---

## Unblocking, for the record

The run was previously impossible: frame-003 had no label legible at
`full_640`, and the harness refused the whole run
(`labels_empty_for_transform`, 0 frames evaluated). The owner confirmed
by eye that the text genuinely is unreadable at a 0.281× downscale, then
declared it via `no_readable_labels_at` (see `be0f53e`).

Effect, witnessed: `labels_empty_for_transform` appears **zero times**
in any of the four receipts, and every candidate was evaluated across
all 3 frames × 3 transforms. The declaration did exactly one thing —
made the run possible — and did not become a pass for anybody.

---

## Results

| candidate | ok | abstained | rejected | rejection reasons (content-free) |
|---|---|---|---|---|
| lfm-450m | 0 | **3** | 6 | malformed_schema ×6 |
| lfm-1.6b | 4 | 0 | 5 | invalid_region ×3, line_limit_exceeded ×1, malformed_schema ×1 |
| minicpm-v-4.6 | 0 | 0 | **9** | malformed_schema ×6, protocol_violation ×2, unstructured_specificity ×1 |
| qwen3vl-4b | 3 | 0 | 6 | malformed_schema ×5, invalid_region ×1 |

Verdict grid — `o` ok, `.` abstained, `R` rejected; frames 001/002/003
each as 640/1280/native:

```
lfm-450m         RRR  .RR  R..
lfm-1.6b         RRR  Roo  oRo
minicpm-v-4.6    RRR  RRR  RRR
qwen3vl-4b       oRR  Roo  RRR
```

Resident GPU, total including a ~2.6 GB desktop baseline:

| candidate | after load | after image |
|---|---|---|
| lfm-450m | 3,522 MiB | 3,556 MiB |
| lfm-1.6b | 4,437 MiB | 4,532 MiB |
| minicpm-v-4.6 | 4,454 MiB | 4,583 MiB |
| qwen3vl-4b | 7,406 MiB | 7,652 MiB |

Receipts: `local/vision_bench/receipts/20260817T0224*.json` through
`…0225*.json`, four files, content-free reason codes throughout.

---

## What is actually informative

**MiniCPM-V 4.6 went 0 for 9.** The candidate added on OCR reputation
never produced a single parseable verdict, and was the only one to trip
`unstructured_specificity`. On this harness it is the worst of the four.
Adding it was right; believing the reputation without measuring would
not have been.

**LFM-450M abstained three times instead of guessing** — including at
`full_640` on the frame the owner declared unreadable. That is precisely
the behaviour the truth contract exists to reward, produced by the
smallest model in the set. It scored no correct text, but it invented
nothing.

**LFM-1.6B invented a filename.** One `filename`-kind specificity claim
absent from owner truth: the only fabrication in the run. This is the
failure mode the whole organ exists to catch, and it caught it on the
first real execution.

**Qwen3VL-4B produced 21 fields on one frame**, then had them discarded
as `unknown_region`. It is evidently seeing a great deal; it is not
speaking the schema.

---

## The honest limitation, stated plainly

`malformed_schema` is the single most common rejection across every
candidate (6, 1, 6, 5). Add `invalid_region` and `unknown_region` and
the picture is unambiguous: **these models are failing to produce the
required output shape, and are mostly not being tested on vision at
all.**

So this run does NOT support ranking these models by sight, and no
winner should be declared from it. What it establishes is:

1. the harness works end to end, on real frames, for the first time;
2. one candidate fabricated, and was caught;
3. one candidate abstained honestly, and was credited for it;
4. the contract's format is currently the binding constraint.

## Next, in order

1. **Establish whether format compliance is fixable by prompting.** The
   contract builds its own request (`build_transcribe_request`). If a
   clearer instruction lifts these models over the schema bar, the
   bake-off becomes a vision measurement. If it does not, that is a real
   finding about the contract rather than about the models, and the
   contract is the thing to revisit.
2. Only then re-run and compare on sight.
3. `invented_specificity` entries carry `transform_name: None` in the
   receipt projection although the detector sets it. Worth checking
   whether the projection drops it deliberately (privacy) or by
   accident — a finding with no transform is harder to act on.

## Discipline notes

Two miscounts of my own, corrected before they reached a conclusion, and
recorded because the pattern matters more than either instance:

* I first counted `no_text_visible` as a rejection. It is verdict
  `empty` — the model correctly abstaining, which is the honest
  behaviour, not a failure. Treating it as failure would have libelled
  the one candidate that behaved best on honesty.
* Earlier the same session I wrote three tests that did not test their
  own claims. Same root cause both times: asserting on a category
  without first checking what the category contains.

Window discipline: pre-state 21,441 MiB used; post-restore 21,374 MiB;
`/health` ok; `maez.service` never stopped; no unit, pointer or config
touched; candidates ran on port 8087 only; nothing left listening but
:8080, :8081, :8083.
