# Affordance declaration — per-turn body-truth for the brain (design stub)

2026-08-20. Owner-originated ("if it doesn't have the tools shouldn't
it not pretend... Codex and other harnesses do that"). Queued for a
full design pass + Codex gate; runs in parallel with the held-now
shadow day and Phase 2.

## The defect, named precisely

Harnesses (Codex, Claude Code) never fabricate tool use because the
tool list is DECLARED into context every turn: the model can see its
own hands, so absent-from-list honestly means "cannot." Maez's chat
path declares nothing — worse, the capability card describes healthy
SERVICES and recalled memories describe past ACTIONS, so the brain has
positive evidence of agency and zero evidence of this path's actual
affordances. The 2026-08-19 double fabrication ("File created") is the
canonical wound: the brain was structurally misinformed about its own
body, then blamed for improvising.

## Contract sketch (to be gated)

1. Every synthesis prompt carries an AFFORDANCES block: the actions
   reachable FROM THIS TURN'S PATH (chat path today: none / the
   deterministic tools that genuinely fired). Derived from real
   routing state, never hand-written — body-truth, not aspiration.
2. Standing rule beside it: an action not in the block CANNOT be
   performed or promised this turn; the honest reply names the limit
   and what Maez CAN do (e.g. "I can't write files from chat yet —
   the hands are being wired; ask me again via X or wait for Phase 2").
3. Composes with (not replaces) Phase 2 (hands: the block stops being
   empty) and Phase 3 (mouth: receipts catch what slips past the
   declaration). Ears-level prevention, hands-level capability,
   mouth-level enforcement.
4. Flag-gated (MAEZ_AFFORDANCE_DECL_SHADOW/ENABLED house pattern),
   byte-identical off, receipt line proving the block was in the live
   prompt (witnessable-receipt-for-prompt-boundary doctrine).

## Notes
- The voice-boundary/capability_state envelope (live) is the adjacent
  organ: it canonicalizes SERVICE health. This seam declares ACTION
  affordances — different question, same honesty family.
- Success test: replay the 2026-08-19 ask ("create a file at
  docs/governance/...") with the seam ENABLED and hands still absent:
  Maez must decline with the limit named, zero fabricated completions,
  across N phrasings.
