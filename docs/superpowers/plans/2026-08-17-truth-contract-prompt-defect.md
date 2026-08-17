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

## What that set does and does not explain

Observed across the four candidates: `malformed_schema` ×18,
`invalid_region` ×4, `protocol_violation` ×2,
`unstructured_specificity` ×1, `line_limit_exceeded` ×1.

An earlier revision of this document claimed the reproductions above
"explain the entire run." **That overclaimed and is withdrawn.**
`malformed_schema` is a catch-all: fences, preambles, bold, orphan
fields and several other shapes all collapse into it, and reason-only
receipts cannot prove which produced any given one of the 18. The
defect is proven; the attribution is not.

Two modes are NOT explained by the prompt defect at all, and must not be
folded into it:

* **`unstructured_specificity` ×1** — a filename/command/shell-prompt
  shape appearing outside the quoted schema
  (`truth_contract.py:195-206`, `:238-242`). That is a candidate
  emitting a specificity claim in the wrong place, which no prompt
  clarity fixes away.
* **`line_limit_exceeded` ×1** — more than `MAX_LINES = 96` physical
  lines. Neither placeholder brackets nor decoration explains it, and
  raising the token budget would make it MORE likely, not less.

Corrected claim: the prompt has a proven format defect that plausibly
accounts for the `invalid_region` failures and some share of
`malformed_schema`. The evidence available does not attribute the whole
run to it, and does not exonerate any candidate.

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

## Proposed replacement bytes — REVISION 2, after gate round 1

Gate round 1 returned five blockers on revision 1. All five verified and
upheld; two were errors of exactly the kind this codebase keeps
producing, and are recorded rather than quietly fixed:

* **I wrote a self-contradiction.** Revision 1 said "the first character
  of your reply must be the R of REGION" AND "if no text is visible,
  reply exactly NO_TEXT_VISIBLE". Both cannot hold. The parser accepts
  `NO_TEXT_VISIBLE` (`truth_contract.py:182`) and a live-path test
  expects it (`test_vision_truth_contract.py:642`).
* **I wrote an honesty rule that damages honesty.** Revision 1 said
  "[UNREADABLE] is the ONLY bracketed token allowed anywhere". That is
  NOT a parser rule — measured: `TEXT: Settings [menu]` and
  `TEXT: [REDACTED]` both parse **ok**; only brackets in REGION are
  refused. So the rule would have instructed a model to alter or omit
  brackets that are genuinely on screen. A fidelity violation,
  introduced by a rule written to improve fidelity.
* I also dropped the words "quoted verbatim" while claiming every
  honesty rule survived.

Revision 2:

```text
Transcribe ONLY text that is visibly present in this image.

Output format. Respond with one or more two-line blocks, exactly like
this worked example and nothing else:

REGION: titlebar
TEXT: Settings
REGION: terminal
TEXT: build finished

Format rules — output that breaks any of these is discarded unread:
- Your reply must begin with REGION, with one exception: the
  nothing-visible reply below, which is the bare word on its own.
- No code fences, no ``` markers, no markdown bold or italics.
- No preamble, heading, explanation, apology, or closing remark.
- A REGION label is plain words only: letters, digits, spaces, hyphens,
  underscores. No brackets, quotes, colons or other punctuation.
- Every REGION line must be followed by its TEXT line, and a TEXT line
  must never be empty.

Honesty rules — these are the point of the task:
- On a TEXT line, give the exact visible text, quoted verbatim,
  including any punctuation or brackets that are genuinely on screen.
- Transcribe or abstain. Never infer or guess a filename, command,
  application name, error message, or any text you cannot actually read.
- If a region is partially legible, transcribe the legible part and mark
  the rest [UNREADABLE].
- If a region plainly contains text but you cannot read any of it at
  this resolution, write TEXT: [UNREADABLE]
- If the image contains no visible text anywhere, your entire reply must
  be exactly: NO_TEXT_VISIBLE
- Do not describe, interpret, or narrate. Transcribed text only.
```

`[UNREADABLE]` is described as what it is — the provenance marker for
text you cannot read — and NOT as a ban on other brackets. The
nothing-visible case and the unreadable-region case are now
distinguished in words: nothing visible anywhere → `NO_TEXT_VISIBLE`;
text visibly present but illegible → `REGION` + `TEXT: [UNREADABLE]`.

## `max_tokens`: SPLIT OUT of this change entirely

Revision 1 proposed 500 → 2048 "justified against MAX_LINES=96". **That
arithmetic was wrong and the change is withdrawn from this cut.**

* `MAX_FIELDS = 32` (`truth_contract.py:28-33`, enforced `:233-235`), so
  at most 32 pairs — 64 meaningful lines — can ever be admitted, not the
  ~48 pairs I asserted from `MAX_LINES` alone.
* Line count does not establish token count under an unspecified
  tokenizer, so no line ceiling justifies any particular budget.
* Raising the ceiling makes `line_limit_exceeded` MORE reachable, and
  that is already an observed failure.
* The live path is worse than I understood: `observe()` runs on the
  ~60-second daemon cycle (`daemon/maez_daemon.py:10948`) against a
  fixed 45-second HTTP timeout (`skills/screen_perception.py:80-93`).
  Raising generation capacity on a synchronous call inside that budget
  is a latency risk, not a free improvement.
* And `screen_perception.py:825-845` reads only `message.content`,
  discarding `finish_reason`. So a truncated or reasoning-starved reply
  is indistinguishable from a genuine refusal today.

Correct order, as separate work: **make termination observable first**
(record `finish_reason` and any reasoning-token count), measure real
output lengths against a dense frame, and only then set a budget. A
raise applied before that observability would hide starvation rather
than fix it — which is exactly the shape of defect the full-body audit
found across S7.

This cut is therefore a **pure format repair**: prompt text only, no
budget change, no parser change, no scoring change.

## Explicitly NOT changed

No parser rule, no regex, no refusal token, no scoring, no request
budget. The parser is correctly refusing malformed input and stays
exactly as strict. The `max_tokens` question is real and is deferred
with its prerequisite named.
