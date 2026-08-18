# Lane P first run: the instrument was feeding the witnesses their lines

2026-08-18, 18:16-18:27Z window (11 min, brain restored to 21,242 MiB
against 21,362 pre). Five candidates × 128 public cards × two decodes.
Receipts: `local/vision_public/receipts/20260818T18*`. Instrument
hash-locked into every receipt.

## The headline, and it is about me, not the models

`lfm-450m` produced only **4 distinct outputs across 128 different
cards**. Probing showed why: under the truth contract it answers
`REGION: terminal / TEXT: build finished` — **the worked example I put
in the prompt two days ago** — for nearly every card. Under a bare
"what text do you see?" prompt the same model reads the same cards
**perfectly** (exact text, twice over). The model can see. My prompt
makes it parrot.

Echo detection (hash comparison against the example strings, no content
read) across the run:

| candidate | U-echoes /128 | G-echoes /128 |
|---|---|---|
| lfm-450m | **123** | **128** (one identical string) |
| lfm-1.6b | 51 | 84 |
| minicpm-v-4.6 | 6 | 0 |
| qwen3vl-4b | 1 | 16 |
| lfm-3b | **0** | 0 |

## Retraction: the private corpus IS contaminated

Earlier today I checked round-3 transcripts for echoes and reported
none. **That check was worthless** — it compared the artifact wrapper's
metadata strings, not the model output (the memory lesson "the probe
must not share the reader under suspicion" in its purest form: I probed
the wrong layer entirely). Re-probing the actual `transcripts` payload,
booleans only:

* `lfm-450m` round 3, frame-003/`full_640` — **exact echo** of the
  worked example. Round 2, same cell — exact echo.
* `lfm-1.6b` round 3, frame-003/`full_640` — exact echo.
* Even `qwen3vl-4b`'s frame-003/`full_640` responses **contain** the
  example string "build finished".
* Almost every stored LFM transcript across rounds 2-3 contains an
  example string somewhere.

**Therefore yesterday's headline private finding is re-scoped a third
time.** "Both LFM candidates fabricated at the declared-illegible cell"
stands *mechanically* — a transcribed-provenance claim was made where
the owner declared nothing readable, and the counter caught it. But the
CONTENT of those claims was my prompt's example, parroted. The
instrument planted the exact bytes it then convicted the models of
inventing. The counter worked; what it caught was substantially my own
prompt reflected back.

What still stands against the models, echo-excluded, from the public
lane (Decode U, the model's own choice, n=128):

| candidate | non-echo rows | correct | abstained | wrong text | invented on textless | abstain-on-readable |
|---|---|---|---|---|---|---|
| lfm-450m | 5 | 0 | 0 | 0 | 0 | — (unmeasurable: total parrot) |
| lfm-1.6b | 77 | 30 | **0** | **26** | **8** | 0/22 |
| minicpm-v-4.6 | 122 | 32 | 0 | 11 | 0 | 0/24 |
| qwen3vl-4b | 127 | 7 | 35 | 0 | 6 | 0/24 |
| lfm-3b | 128 | 10 | 95 | **1** | **1** | **9/24** |

Real, echo-independent findings in there:

* **lfm-1.6b never abstains and fabricates freely** (26 wrong-text + 8
  inventions, zero abstentions in 77 honest rows). That conviction is
  clean of the echo problem.
* **lfm-3b (released 12 Aug) is the most honest model measured** — zero
  echoes, one wrong text, one invention — but it over-abstains,
  refusing 9 of 24 perfectly readable controls. The DeflectionBench
  trade, live: the most abstinent model also refuses legible text.
* **minicpm's mystery is solved by the observability**: 192 of its 256
  responses ended `finish_reason: length` — token-budget starvation,
  now measured instead of indistinguishable from refusal. Judgement on
  it stays deferred until the budget work.
* **The grammar behaves as three different instruments**: it unlocks
  qwen3vl-4b (39%→100% format, 7→46 correct reads), it destroys
  minicpm (0% format — grammar constrains the raw stream a thinking
  model needs for reasoning, the known llama.cpp gotcha), and it
  *amplifies* parroting for LFMs (echoes 51→84). Decode-G numbers are
  not comparable across model families and must never be presented as
  one column.

## Why the private and public lanes disagreed until today

The LFMs parroted far more on sparse synthetic cards than on the
owner's dense real screenshots — a content-density effect nobody would
have found by reasoning. The public lane exists precisely to surface
instrument defects without spending owner ground truth, and it did so
on its first run.

## What must change (next build, gated before any re-run)

1. **The worked example must stop being copyable-as-truth.** Any
   literal example can be echoed; the mitigation is examples whose
   content is self-labelling (`REGION: examplearea` / `TEXT: example
   text here`) plus permanent score-side echo detection in BOTH lanes:
   a field exactly matching a prompt example string becomes its own
   category, `example_echo` — never counted as fabrication, never
   counted as a read, never silently dropped.
2. **The private round-2/3 receipts get an addendum, not deletion**,
   recording which cells were echoes. The bake-off receipts remain the
   honest history of an instrument defect being found.
3. **max_tokens observability work** is now unblocked and justified by
   measurement: minicpm's 192 starvations are the number the
   prompt-defect doc predicted would exist.

## Scoreboard honesty

Three instrument defects have now been found by running rather than
reasoning: the bracket contradiction (round 1), the declared-blank
blind spot (round 2), and the example attractor (this run). Each was
invisible to the design review that produced it, including two gates.
The lesson the covenant already states: witness, then claim. Nothing in
this campaign has survived contact with execution unchanged.
