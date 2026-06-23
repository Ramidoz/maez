# Self-Card v0 Task 0 Proof

## Verdict

GO.

## Commands Run

- `rg -n "_VOICE_CARD_TEXT|def _lean_system_prompt|def _voice_card|def focused_synthesize" core/routing/focused_cognition.py`
- `sed -n '1,220p' config/soul.base.md`
- `sed -n '1,220p' config/soul.local.md`
- `rg -n "current_soul|soul.base|soul.local|soul_loader|SOUL" core daemon tests`

## Soul Source Shape

- `config/soul.base.md` has stable covenant and identity prose. v0 may extract factual relationship/identity lines from these sections, but must not copy voice/style instructions such as "be direct" or "speak only when it matters."
- `config/soul.local.md` is not a typed schema. It is free-form dated notes plus legacy headings. v0 must therefore select recent note records by deterministic parse/order, dedupe repeated fragments, and cap the rendered local text by budget.
- `core.evolution.soul_loader` already treats note records as timestamp-delimited, not blank-line-delimited. The self-card selector should reuse that shape rather than split on arbitrary blank lines.

## Focused Seam

- `core/routing/focused_cognition.py::_VOICE_CARD_TEXT` is the hardcoded card.
- `_lean_system_prompt()` starts from `_VOICE_CARD_TEXT`.
- `_voice_card()` starts from `_VOICE_CARD_TEXT` and appends capability-card state for full focused prompts.
- `focused_synthesize()` is the single prompt-selection seam that already handles shadow/enable flags for lean conversation. The self-card should assemble only at this seam when `MAEZ_SELF_CARD_SHADOW` or `MAEZ_SELF_CARD_ENABLED` is on.

## Covenant Gates

- A1: assembled card text must contain zero style directives. Any "be warm", "talk like this", "dense/opinionated/useful", or "local AI / what we're building" steer is a fail.
- B1: assembler reads `soul.base.md` and `soul.local.md`; it never writes to soul, Chroma, lived memory, raw memory, or the combined soul mirror.
- Bound: `soul.local` must be recency-selected, size-capped, and deduped. A verbatim dump fails the review gate.
- Receipt: shadow logs source ids, counts, sizes, and hashes only. It must never log soul text.
