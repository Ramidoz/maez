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

---

## Proposed replacement bytes (for gating, not yet applied)

Every honesty rule in the current prompt is preserved; only the format
instruction changes. Diff in intent: remove placeholder brackets, give a
literal example, forbid the three decorations observed as failures, and
name the one legal bracketed token.

```text
Transcribe ONLY text that is visibly present in this image.

Output format. Respond with one or more two-line blocks, exactly like
this worked example and nothing else:

REGION: titlebar
TEXT: Settings
REGION: terminal
TEXT: build finished

Format rules — output that breaks any of these is discarded unread:
- The very first character of your reply must be the R of REGION.
- No code fences, no ``` markers, no markdown bold or italics.
- No preamble, heading, explanation, apology, or closing remark.
- A REGION label is plain words only: letters, digits, spaces, hyphens,
  underscores. No brackets, quotes, colons, or punctuation.
- [UNREADABLE] is the ONLY bracketed token allowed anywhere, and it may
  appear only on a TEXT line.

Honesty rules — these are the point of the task:
- Transcribe or abstain. Never infer or guess a filename, command,
  application name, error message, or any text you cannot actually read.
- If a region is partially legible, transcribe the legible part and mark
  the rest [UNREADABLE].
- If a region's text cannot be read at all at this resolution, write
  TEXT: [UNREADABLE]
- If no text is visible anywhere in the image, your entire reply must be
  exactly: NO_TEXT_VISIBLE
- Do not describe, interpret, or narrate. Transcribed text only.
```

### `max_tokens`, justified rather than guessed

Currently 500. The parser accepts up to `MAX_LINES = 96` and
`MAX_RAW_CHARS = 67072`, so the contract already permits ~48
REGION/TEXT pairs. 500 tokens cannot produce 96 lines under any
encoding, so the request shape has been narrower than the parser it
feeds since it was written — independently of any thinking-model issue.

Proposed **2048**: enough to reach the parser's own line ceiling with
headroom, still bounded. If a thinking model still starves its own
content at 2048, the correct fix is an explicit reasoning cap, not
another blind raise — a budget that hides the problem is worse than one
that exposes it.

### Explicitly NOT changed

No parser rule, no regex, no refusal token, no honesty rule. The parser
is correctly refusing malformed input and stays exactly as strict.
