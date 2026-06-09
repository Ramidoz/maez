# Codex Handoff: Photo-Triggered Fact Check v0

Status: ready for Claude review, not merged, not live.

Branch: `photo-triggered-fact-check-v0`

Implementation commit: `499d933 feat(photo): fact-check freshness claims from images`

## Failure This Fixes

Live witness: the owner sent a photo of a benchmark chart captioned around
Anthropic's latest model. The local photo eye saw the chart and the focused photo
path cited `[E1]`, but the reply dismissed `Claude Mythos 5` / `Fable 5` as
nonexistent from stale model knowledge. Web verification showed the owner was
right: Anthropic had just announced the models.

The core mistake was not in vision or the citation rail. It was in treating a
photo as sufficient to answer a volatile public-world claim, then letting stale
memory overrule the image. A photo proves what the image appears to show; current
release truth needs a fresh check.

## What Changed

- Added `photo_freshness_search_query(caption, analysis_text)` in
  `core.routing.focused_cognition`.
- Extended `synthesize_photo_turn(..., fresh_context=None)` so bounded photo
  synthesis has:
  - `E1`: local photo analysis.
  - optional `E2`: fresh web-search context / no-results check.
- Updated citation validation so `E1` is always required and `E2` is allowed only
  when fresh context exists.
- Wired `daemon.handle_message` to run a targeted photo freshness web search when
  a successful photo analysis plus caption/image text implies a current-world
  claim and normal caption search did not already produce useful evidence.
- Passed the resulting `web_context` into photo focused synthesis as
  `fresh_context`.

## Covenant/Behavior Anchors for Review

1. **Photo is lead, not proof.** The prompt tells Maez to use `E1` for what the
   image appears to show and `E2` only for external current-world verification.
2. **Stale memory must not overrule current photo evidence.** If `E2` is empty,
   the prompt says to report that the image appears to show the claim but it was
   not verified, not to dismiss it from stale memory.
3. **No raw pixels egress.** The search query is derived only from the local
   vision text and caption. The raw image path is unchanged.
4. **Existing photo honesty organs stay intact.** Lane 1 citations and Lane 2
   contradiction sense are not replaced; `E2` only adds freshness evidence.
5. **No live activation.** This is ordinary code on a branch; no daemon restart,
   service change, flag flip, or model/env change was performed.

## Tests / Verification Run

RED was observed first in `tests.test_photo_focused_routing`:

- `test_photo_freshness_context_reaches_photo_synthesis` failed because
  `handle_message` did not contain `photo_freshness_search_query`.

GREEN verification after implementation:

```bash
/home/rohit/maez/.venv/bin/python -m unittest \
  tests.test_photo_contradiction \
  tests.test_photo_focused_synthesis \
  tests.test_photo_focused_routing \
  tests.test_chat_photo_wiring \
  tests.test_photo_judge_bakeoff
```

Result: `Ran 127 tests ... OK`.

```bash
/home/rohit/maez/.venv/bin/python -m ruff check \
  core/routing/focused_cognition.py \
  daemon/maez_daemon.py \
  tests/test_photo_focused_synthesis.py \
  tests/test_photo_focused_routing.py
```

Result: `All checks passed!`

Helper probe:

- `caption="Check out anthropic's latest model"` plus photo text containing
  `"Claude Mythos 5 and Fable 5"` returns a compact query:
  `Anthropic Claude Mythos 5 and Fable 5 Claude Mythos 5 Fable 5 latest`.
- A plain shape-description photo returns `None`.

## Review Questions

- Is the freshness detector conservative enough, or does it risk searching too
  often on ordinary photo descriptions?
- Is it acceptable to reuse `web_context` as `E2` even when the search is empty,
  so the synthesis can say "not verified" instead of letting the empty-search
  path preempt the photo?
- Does allowing `[E1]` plus `[E2]` preserve the Lane 1 citation rail strongly
  enough, or should a fresh-context reply be required to cite both labels?
