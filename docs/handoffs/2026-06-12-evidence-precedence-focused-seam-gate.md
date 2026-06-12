# Evidence-Precedence Focused-Prompt Seam Fix — For Review

## Status

Built, stopped at the gate. No merge, restart, flag flip, or live witness.

Branch: `evidence-precedence-focused-seam`
Tip: `fb96109` before this handoff commit.

## Root Cause

The v0 components were built and captured in the daemon-side prompt parts, but
the wound turns are answered by `focused_cognition.focused_synthesize()`, whose
bounded system prompt is built inside `core/routing/focused_cognition.py` from:

- `_voice_card(surface)`
- `_citation_instruction(...)`
- trust/origin instructions
- `working_set.ordered_evidence_text`

The daemon ambient card and daemon evidence directive do not reach that prompt.

## Fix

`core/routing/focused_cognition.py` now injects the same organ into the focused
prompt layer under `MAEZ_EVIDENCE_PRECEDENCE_ENABLED`:

- capability card appended to `_voice_card(...)`
- precedence lines appended to `_citation_instruction(...)`
- helper failures fall back to the old text
- flag-off focused prompt contains none of the new strings

The daemon-side v0 wiring remains in place for legacy/non-focused paths.

## Review Anchors

1. Focused prompt flag-on contains `YOUR LIVE BODY` and the
   `CONTEXTUALIZE`/`re-read the evidence` precedence rule.
2. Focused prompt flag-off remains free of the card/rule strings.
3. No evidence items are added; the card is substrate state, not `[E#]`
   evidence.
4. No memory deletion/deweighting/mutation. This is still composition-only.
5. Existing citation-render behavior remains green.

## Verification

Targeted:

```text
/home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_focused_cognition.FocusedSynthesizeTests \
  tests.test_focused_cognition_citation_render.V2Instruction -v

Ran 6 tests
OK
```

Focused/evidence-precedence floor:

```text
/home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_focused_cognition tests.test_focused_cognition_citation_render \
  tests.test_capability_card tests.test_evidence_state \
  tests.test_evidence_precedence_shadow tests.test_daemon_prompt_seams \
  tests.test_attribution_render -v

Ran 105 tests
OK
```

Ruff:

```text
/home/rohit/maez/.venv/bin/ruff check \
  core/routing/focused_cognition.py tests/test_focused_cognition.py

All checks passed!
```

## Owner Witness After Review + Merge

With `MAEZ_EVIDENCE_PRECEDENCE_ENABLED=1`, ask the same three wounds:

1. "What's the state of your web search tools?"
2. "Are you able to feel time?"
3. `check https://github.com/ggml-org/llama.cpp/releases — what's the latest release?`

Expected: the focused prompt now carries the live body card and precedence rule,
so the answers should be governed by current substrate/page evidence rather than
stale self-capability memory or recalled failure narrative. The Component C
ledger should continue to record absence-claim shapes if they appear.
