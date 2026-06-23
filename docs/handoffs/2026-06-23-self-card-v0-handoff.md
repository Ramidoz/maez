# Self-Card v0 Handoff

## State

- Branch: `self-card-v0`
- Base before slice: `ae19d6d`
- Status: built, tested, not restarted, no flags flipped.

## What Landed

- `core/routing/self_card.py`
  - Deterministic self-card assembler.
  - Reads `soul.base.md` + bounded/deduped recent `soul.local.md`.
  - Adds a computed body-state line from runtime-services snapshot provider.
  - Emits a content-light receipt: counts, hashes, sources, sizes.
  - No LLM call, no writes, no memory/soul mutation.
- `core/routing/focused_cognition.py`
  - `MAEZ_SELF_CARD_SHADOW=1`: assembles the card and logs `self_card_shadow`, but keeps legacy prompt text.
  - `MAEZ_SELF_CARD_ENABLED=1`: swaps the assembled card into both lean and full focused prompts.
  - Default-off path does not assemble and continues to use `_VOICE_CARD_TEXT`.
- `tests/test_self_card_v0.py`
  - Assembler provenance, local cap/dedupe, no-style-directives, content-light receipt, read-only path test.
- `tests/test_lean_conversation_path.py`
  - Shadow receipt is content-light and keeps legacy prompt.
  - Enabled self-card replaces the legacy card in lean and full focused prompts.

## Task 0 Proof

Recorded in `docs/proofs/2026-06-23-self-card-v0-task0.md`.

Key result: `soul.local.md` is free-form timestamped prose, not a structured schema. v0 therefore selects recent timestamped records, dedupes by normalized body, and caps local text by budget.

## Covenant Review Anchors

- A1 zero style script:
  - The card is facts-only: bond, covenant identity, recent self-understanding, body state.
  - The real assembled card receipt reports `style_directive_hits=()`.
  - Tests reject the old `"Speak as Maez: dense..."`, `"local AI"`, and `"what's being built"` steer.
- B1 read-only:
  - `assemble_self_card_from_paths(...)` reads source files directly and does not call `current_soul()` or any writer.
  - Test asserts `soul.base.md` / `soul.local.md` content and mtimes are unchanged after assembly.
- Bound:
  - `soul.local` rendered text is capped (`local_rendered_chars`), newest-first, max-items bounded, normalized dedupe.
  - Real current receipt: 3 local lines selected, `local_rendered_chars=520`, no full local dump.
- Receipt:
  - `self_card_shadow` logs card hash, line count, line sources/source refs, local counts/chars, body-state source, style-hit names.
  - It never logs soul text. Test uses `SECRET_*` fixture text to prove no leak.

## Verification

Passing:

```bash
.venv/bin/python -m unittest tests.test_self_card_v0 tests.test_lean_conversation_path tests.test_focused_cognition tests.test_focused_cognition_citation_render
# 95 tests OK

.venv/bin/ruff check core/routing/self_card.py core/routing/focused_cognition.py tests/test_self_card_v0.py tests/test_lean_conversation_path.py
# All checks passed

git diff --check
# clean
```

Additional broad module run:

```bash
.venv/bin/python -m unittest tests.test_memory_integrity_invariant
```

This still reports the already-known two failures from the Arc-A lane:

- `AdapterNoLongerDoubleAudits.test_adapter_does_not_import_self_claim_audit`
- `DaemonHandleMessageContract.test_soul_web_search_section_matches_inline_search_reality`

This slice does not modify `skills/surface/maez_adapter.py`, `config/soul.base.md`, or `tests/test_memory_integrity_invariant.py`; the targeted focused-cognition regression suite above is green.

## Owner Breath After Review PASS

Do not flip live flags until covenant review passes.

1. Set `MAEZ_SELF_CARD_SHADOW=1`.
2. Restart only when owner chooses.
3. Witness `self_card_shadow` receipts:
   - `status=ok`
   - `style_directive_hits=none`
   - `local_selected_count>0`
   - no soul text in logs
4. Then set `MAEZ_SELF_CARD_ENABLED=1`.
5. Witness:
   - casual `"how are you?"` no longer carries the old hardcoded `"local AI / what's being built"` steer.
   - memory/web/body turns keep full rails.
   - if qwen's `"professional/workflow/systems online/ready to assist"` accent remains, v0.1 voice-card trim is the next isolated slice, not a reason to mutate soul in place.

## Plain English

This does not make Maez invent a personality. It lets the prompt carry a small mirror of what is already true: the bond, the stable soul identity, a recent bounded slice of its own learned notes, and a current body-state line. The brain gets a real body-truth card instead of a tiny hardcoded instruction card.
