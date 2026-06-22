# Witness — Continuity Classifier + Trust-Tier Evidence Lines (2026-05-30)

**Slice:** First item of the organ-evolution roadmap. Branch `continuity-classifier-trust-tier`
(`c2ae550` classifier grammar, `88d1a8a` trust-tier). Implemented by Codex (Rohit-orchestrated,
VS Code), cross-verified + witnessed by Claude. **Merged ff → `main @ 88d1a8a`, flag-off.**

## Cross-verification (Claude, independent — not the implementer's report)
- Diff faithful to plan + spec's 5 refinements; ONLY the 2 planned files; **no `MAEZ_*` flag or
  `config/.env` change**; `[E#]` tokens preserved byte-for-byte.
- `.venv/bin/python -m unittest tests.test_focused_cognition tests.test_living_recall` → **79/79 OK**
  (run by Claude, not taken on report).
- The two broad-floor failures (`test_web_search_direct_caller_inventory_is_stable`,
  `test_owner_bridge_chat_uses_envelope_prompt_block_and_recall_cap`) **fail identically on clean
  `main` 1ef70a5** → pre-existing, not introduced (neither touches classifier/rendering).

## Live witness (flag-on Telegram, PID 187552, branch code; gates = live, not unit)
Probe order (probe 1 substantive → gives probe 2 a real anchor + tests content-recall first):

| Probe | Trace | Reply | Verdict |
|---|---|---|---|
| "What's the infrastructure ground-truth you noted earlier?" | `items=2, source_types=memory_context,memory_evidence` (NO dialogue_anchor) | recalled the April-2026 fabrication incident, caveated as *"permanent background, not current state"* / *"recalled context with heavy skepticism"*, cited `[E1][E2]` | ✅ content recall, not mis-anchored; trust labels reaching the brain |
| "What were we just talking about?" | `items=1, source_types=dialogue_anchor`; **`focused_cognition_skip=0`** | *"We were just discussing the 'infrastructure ground-truth' … [E1]"* — recapped the prior turn | ✅ classifier now fires DIRECT (was `kind=none` → "I don't know" before) |

**Before vs after:** the 2026-05-30 root-cause witness showed `"what were we just talking about?"` →
`kind=none` → no anchor → stale "I don't know", with `focused_cognition_skip` firing every continuity
turn. After: DIRECT → `dialogue_anchor` sole `[E1]` → correct recap; **zero skips**.

Trust-label rendering proven in-process by `test_render_uses_authority_label_and_preserves_labels`
(part of the 79/79); the live reply's caveat vocabulary corroborates. (Label strings absent from the
`system_part_shape` grep only because that log records head/tail, not mid-block — not absence.)

## Posture
Merged flag-off: both the classifier and trust-tier code paths run only under
`MAEZ_FOCUSED_COGNITION_ENABLED` / `MAEZ_LIVING_RECALL_ENABLED`, so inert in production until a
default-on decision. Daemon restored under the unit, flag-absent (PID 189781).

## Follow-ups (named, not in this slice)
- Default-on consideration for focused cognition + living recall now has continuity + trust-tier
  closed; remaining default-on work tracked in `memory/project_organ_roadmap.md`.
- Branch `continuity-classifier-trust-tier` is merged → safe to prune in the housekeeping batch.
