# The bake-off's failures are a contract defect, not four bad models

2026-08-17. Diagnosed with **no GPU and no owner data** — the whole
finding is reproducible from pure functions.

## Claim

`TRANSCRIBE_PROMPT` instructs candidates to emit a format that
`parse_and_validate` then rejects. Every rejection mode observed in the
four-candidate bake-off is reproduced by feeding the parser output that
follows the prompt's own example.

## Evidence

`TRANSCRIBE_PROMPT` (`core/vision_contract/truth_contract.py:57`) shows:

```text
REGION: [short location label, e.g. titlebar, terminal, editor, dock]
TEXT: [the exact visible text, quoted verbatim — or [UNREADABLE] ...]
```

Square brackets are placeholder syntax here. But
`_REGION_LABEL_RE = ^[A-Za-z0-9][A-Za-z0-9 _-]*$` (`:74`) **forbids
brackets in a region label**. A model that copies the shown shape is
refused.

Worse for a model trying to infer the rule: brackets are *required* in
the TEXT field (`[UNREADABLE]`, `:72`) and *forbidden* in the REGION
field, while the prompt uses brackets as placeholders in both.

Parser behaviour, measured directly:

| candidate output | verdict |
|---|---|
| `REGION: titlebar` / `TEXT: Settings` | **ok** |
| `REGION: [titlebar]` — the prompt's own shape | rejected `invalid_region` |
| wrapped in a ``` fence | rejected `malformed_schema` |
| `Here is the transcription:` then the block | rejected `malformed_schema` |
| `**REGION:** titlebar` (markdown bold) | rejected `malformed_schema` |
| empty content | rejected `protocol_violation` |

## That set explains the entire run

Observed across the four candidates: `malformed_schema` ×18,
`invalid_region` ×4, `protocol_violation` ×2,
`unstructured_specificity` ×1, `line_limit_exceeded` ×1.

The three commonest map one-to-one onto the three commonest ways a
chat-tuned model decorates output — fences, preambles, bold — plus
echoing the placeholder brackets. **Nothing in that distribution
requires any candidate to have misread a pixel.**

## A second, independent cause of empty output

`build_transcribe_request` sets `max_tokens: 500` (`:163`). Several
current candidates are *thinking* models that emit reasoning before
content. Witnessed on Maez's own brain the same night: at
`max_tokens=16` Qwen3.6 returned `content: ''` with `finish_reason:
length` and all tokens in `reasoning_content`; at 400 it answered
correctly. 500 tokens on a dense screenshot is not obviously enough
budget for reasoning **plus** a full multi-region transcription — and if
reasoning consumes it, the result is `protocol_violation`, which is
exactly what MiniCPM produced twice.

This is the same trap I fell into with my own instrumentation last
night. It is baked into the production request shape.

## Why this is a real defect and not a harness quibble

`build_transcribe_request` is not test-only. `skills/screen_perception.py:821`
calls it on the live screen-perception path. So this prompt is what Maez
would use to read its own screen once that flag is enabled — meaning the
defect is scheduled to arrive in production, not confined to a bench.

## What I did NOT do

I did not change the prompt. Three reasons:

1. It is on a live path, so it is a production change, not a bench tweak.
2. Changing what candidates are told changes what the bake-off measures,
   and the four existing receipts would no longer be comparable. That
   needs to be a deliberate, dated cut with a re-run — not an edit
   folded into a diagnosis.
3. Making candidates pass more easily is the shape of pass-bucket
   widening. Even when the fix is correct, it should be argued and gated,
   not slipped in beside a favourable result.

## Proposed fix, for review

* **Show the format without placeholder brackets.** Give a literal
  worked example — `REGION: titlebar` / `TEXT: Settings` — instead of
  bracketed slots, and state that `[UNREADABLE]` is the one bracketed
  token permitted, only in TEXT.
* **Say explicitly: no code fences, no preamble, no markdown emphasis,
  no commentary — the first line must begin `REGION:`.** All three are
  observed failure modes and none is currently forbidden in words.
* **Raise `max_tokens`, or set a reasoning budget**, so a thinking model
  cannot spend the whole allowance before producing content. Whatever
  the number, it should be justified against a dense frame rather than
  guessed.
* Keep every parser rule exactly as strict as it is. **The parser is not
  the defect** — it is correctly refusing malformed input. The
  instruction is the defect.

## Sequence

1. Gate this diagnosis and the proposed prompt.
2. Change the prompt as one dated commit, noting that receipts before it
   are not comparable to receipts after.
3. Re-run all four candidates in a window.
4. *Then* the bake-off measures sight, and a winner means something.

The four existing receipts stay. They are the honest record of what this
contract does to compliant-but-decorated output, and they are the
before-half of the comparison.
