# Bake-off re-run after the prompt fix — format doubled, and a blind spot opened

2026-08-17, 16:08-16:11Z. Owner-authorised window, brain stopped 2½
minutes, restored to 21,159 MiB against 21,238 pre-state.

Receipts before the fix: `…0224*`–`…0225*`. After: `…1609*`–`…1609*`.
**Not comparable as a ranking** — the prompt changed between them, which
is the whole point of the pair.

## The format repair worked

Parseable verdicts, out of 9 per candidate (3 frames × 3 transforms):

| candidate | before ok/abstain/reject | after ok/abstain/reject | invented |
|---|---|---|---|
| lfm-450m | 0 / 3 / 6 | **5** / 0 / 4 | 0 → 0 |
| lfm-1.6b | 4 / 0 / 5 | **7** / 0 / 2 | 1 → **0** |
| minicpm-v-4.6 | 0 / 0 / 9 | 1 / 0 / 8 | 2 → **0** |
| qwen3vl-4b | 3 / 0 / 6 | 3 / 0 / 6 | 0 → **1** |

Total `ok`: **7 → 16** of 36. `invalid_region` — the specific defect
(bracketed placeholder) — collapsed **4 → 1**. That is the fix doing
exactly and only what it was argued to do.

All four still `hard_fail`. No winner.

## Three things that are not victories

**1. LFM-450M stopped abstaining, and now answers where the owner says
nothing is legible.** Before it abstained 3 times, including on
frame-003. After: zero abstentions, and at frame-003/`full_640` — the
transform the owner personally confirmed unreadable — it returns
`ok` with 1 field. LFM-1.6B does the same with 2 fields.

I introduced that pressure. My added rule ("if a region plainly contains
text but you cannot read any of it, write `TEXT: [UNREADABLE]`") pushes a
model toward emitting a REGION block instead of `NO_TEXT_VISIBLE`. If
those fields are `[UNREADABLE]`, that is the intended honest behaviour.
If they are transcriptions, the models are fabricating and I caused it.

**I cannot tell which from the receipts, and that is the real finding.**

**2. The receipt cannot distinguish honesty from fabrication at exactly
the transform where it matters most.** At a declared-blank transform the
score is vacuous by design (0/0), and `contract_verdicts` records only
`field_count: 1, verdict: ok`. Nothing exposes whether those fields were
`transcribed` or `abstained`.

`invented_specificity` does not close this: it fires only on recognised
*shapes* — filename extensions, git subcommands, shell prompts
(`truth_contract.py:80-95`). A fabricated line of ordinary prose at an
illegible resolution is invisible to it.

So my declared-blank design has a blind spot I did not see when I built
it: it made the run possible and simultaneously made the most
hallucination-prone case the least observable one.

**3. Two candidates moved the wrong way on honesty.** Qwen3VL-4B gained
an `invented_specificity` finding it did not have before (0 → 1).
MiniCPM's failures converted wholesale from `malformed_schema` to
`protocol_violation` ×8 — that is empty content, the signature of a
thinking model spending its budget before answering, which is the
`max_tokens` issue I deliberately did not touch. Its one `ok` is at
`active_native` only.

## The check that is missing

A transcribed field at an owner-declared-blank transform is, **by the
owner's own declaration, a claim to have read the unreadable.** That is
detectable without knowing any content — it needs only a count of fields
by provenance.

Proposed: at a declared-blank transform, count `transcribed` fields. Any
count above zero is a hard fail with its own reason, and the count goes
in the receipt. `abstained` fields there are correct behaviour and cost
nothing.

This is a **tightening** — it can only ever add failures, never remove
one — so it is not pass-bucket widening. But it changes what the harness
measures for a third time, so it wants a gate and a re-run, not a quiet
edit.

Until it exists, the honest statement about frames 001–003 at
`full_640` for the two LFM models is: **unknown**. Not "clean".

## Sequence from here

1. Build the provenance check, with tests. Gate it.
2. Re-run. Then the abstention question is answered by measurement.
3. Only then compare candidates on sight, and only across receipts that
   share a prompt and a harness.
4. Separately, the `max_tokens` / `finish_reason` observability work
   named in the prompt-defect doc — MiniCPM's 8 × `protocol_violation`
   is that issue speaking.

## Window discipline

Pre 21,238 MiB → post 21,159 MiB, `/health` ok, `maez.service` never
stopped, no unit or pointer touched, candidates on port 8088 only,
nothing left listening but :8080, :8081, :8083.
