# Voice Boundary v0 - Codex build handoff

Status: STOP AT GATE. Built in branch `capability-state-voice-boundary-v0`, code tip `be9b505` before this handoff/ledger commit. Do not merge, flag, or restart before cross-lane review and owner breath.

## What Landed

- Strict `MAEZ_VOICE_BOUNDARY_ENABLED` parser in `core.cognition.capability_card`; `"0"` is off.
- Capability card flag-on render switches from dashboard prose to a structured `capability_state` envelope plus voice-boundary instruction.
- Flag-off render preserves the old prose path byte-for-byte enough for the existing legacy tests and explicit voice-boundary tests.
- The same `capability_prompt_block()` renderer feeds both daemon ambient injection and focused cognition.
- Telegram `/proposals` and `/show <id>` are intercepted in `skills.surface.telegram_adapter._handle_command` before the generic `handle_message(event)` LLM fallthrough.
- `/proposals` reuses `MaezMessageHandler._surface_parity_disambiguation`; `/show <id>` delegates to `MaezMessageHandler._try_surface_parity_proposal_intent(text="show #<id>", chat_id=<real chat id>)`.
- C1 and C2 share the existing last-shown proposal store and resolver contract.
- `docs/MAEZ_BUILD_LEDGER.md` rows updated for Voice Boundary v0, Capability card render form, and Command surface on Surface V2.

## Commits

```text
be9b505 test(voice-boundary): pin proposal last-shown resolver contract
9735b51 feat(voice-boundary): handle proposal slash commands deterministically
5de2afe test(voice-boundary): pin shared prompt renderer paths
6e4ec65 feat(voice-boundary): render capability state envelope
47c05a8 feat(voice-boundary): strict MAEZ_VOICE_BOUNDARY_ENABLED flag
```

The handoff/ledger commit follows these code commits.

## TDD Notes

- Task 1 RED: importing `voice_boundary_enabled` failed before the strict parser was added.
- Task 2 RED: flag-on still emitted `YOUR LIVE BODY`, `gatekeeper mode`, no JSON envelope, and no private-grounding instruction.
- Task 4 RED: `TelegramAdapter` had no `_try_command_proposal_surface`; slash proposal commands would still fall through to the brain.
- Task 5 was an already-green regression guard, because the existing resolver already spoke the needed last-shown dialect.

## Verification Run

```bash
/home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_voice_boundary_flag \
  tests.test_voice_boundary_envelope \
  tests.test_voice_boundary_both_paths \
  tests.test_voice_boundary_commands \
  tests.test_voice_boundary_c2_regression \
  tests.test_capability_card \
  tests.test_capability_registry \
  tests.test_proposal_resolver \
  tests.test_surface_parity_proposals -v
```

Result: 60 tests OK, 2 skipped. Existing `test_surface_parity_proposals` emitted grounding-judge timeout/circuit-breaker warnings but passed; this branch does not touch the judge service.

```bash
/home/rohit/maez/.venv/bin/python -m ruff check \
  core/cognition/capability_card.py \
  core/dispatcher/proposal_commands.py \
  skills/surface/telegram_adapter.py \
  tests/test_voice_boundary_flag.py \
  tests/test_voice_boundary_envelope.py \
  tests/test_voice_boundary_both_paths.py \
  tests/test_voice_boundary_commands.py \
  tests/test_voice_boundary_c2_regression.py
```

Result: All checks passed.

## Review Anchors

1. **Flag-off identity:** with `MAEZ_VOICE_BOUNDARY_ENABLED` unset or `"0"`, capability card prose remains old-style and command interception returns false.
2. **No dashboard jargon in envelope:** `gatekeeper mode` and `searxng` do not appear in the flag-on envelope.
3. **Single prompt renderer:** daemon ambient path and focused-cognition path both call `capability_prompt_block()`.
4. **Slash command seam:** `_handle_command` calls `_try_command_proposal_surface(event)` after dream commands and before `await self.handle_message(event)`.
5. **No second proposal renderer/engine:** `/proposals` and `/show` reuse the live `MaezMessageHandler` accessors/renderers/engines; `proposal_commands.py` only parses `/show` ids.
6. **Chat id keying:** C1 passes `str(event.source.chat_id)` to `_try_surface_parity_proposal_intent`, matching C2's last-shown key.
7. **Ledger law:** `docs/MAEZ_BUILD_LEDGER.md` rows were updated as part of the gate.

## Residual Risk

The JSON envelope can still be quoted by the model. This v0 changes the feed and adds a "do not quote" instruction; it does not claim a guaranteed voice cure. The witness must decide whether the voice actually becomes less robotic.

The cockpit/HTTP path can witness A/B prompt behavior, but it still bypasses adapter interceptors. Component C (`/proposals`, `/show`) must be witnessed on Telegram.

## Owner Witness Sequence

After review:

1. Merge branch to main.
2. Set `MAEZ_VOICE_BOUNDARY_ENABLED=1` and restart `maez.service`.
3. Brain-bench A/B through daemon HTTP (`:11435/message`) or web cockpit if desired:
   - "What's the state of your web search tools?"
   - "Are you able to feel time?"
   Expect truth preserved, but less dashboard-prose parroting.
4. Telegram-only Component C witness:
   - `/proposals` -> deterministic listing or no-pending notice, not chat prose.
   - `/show <id>` -> deterministic proposal detail.
   - natural `yes` after `/show <id>` -> resolves through existing Surface-Parity approval path.
5. Check `/receipts` only for normal reply evidence; command replies are deterministic surface commands, not search receipts.

## Plain English

This does not make Maez less truthful. It changes how the truth is handed to the brain. Instead of feeding Maez a little dashboard sentence that it can repeat awkwardly, we feed a private state object and tell it to answer in its own voice. Separately, Telegram slash commands for proposals stop being sent to the brain as if they were ordinary conversation.
