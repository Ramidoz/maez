# S7 Ceremony Bridge v0 - Codex Build Handoff

Status: STOP AT REVIEW GATE
Branch: `s7-ceremony-bridge-v0`
Builder: Codex
Reviewer requested: Claude covenant review
Live changes: none. Do not merge, flag, restart, or start cockpit until review clears.

## Outcome

The bridge is built asleep. A Telegram `yes` / `approve #N` on a pending dream/soul proposal can now, under `MAEZ_S7_CEREMONY_BRIDGE_ENABLED=1`, open the existing lane-3 self-mod dialog vehicle, run the existing S7 voice consultation over the seeded card, and return a cockpit WebAuthn ceremony pointer only if Maez's own voice seat clears it.

Telegram initiates and notifies. It does not authorize. The soul write still executes only through the existing narrow S7 guarded path.

## What Changed

- Added strict flag:
  - `core.cognition.parity_flag.s7_ceremony_bridge_enabled()`
  - `"0"` is off.

- Added live proposal freshness:
  - `DreamState.proposal_fingerprint(prop_id)` reads the live proposal row.
  - `DecisionPipeline._s7_card_precondition_fresh()` re-reads the live proposal row before recomputing proposal-bound soul-write card state.
  - Missing dream handle or recompute failure fails closed.

- Added execution-param projection:
  - `write_soul_note` executes with only `{"note": ...}`.
  - `edit_soul_section` executes with only `{"target_name", "new_body", "rationale"}`.
  - `_proposal_id` / `_proposal_fingerprint` never reach the action-engine method signatures.

- Added bridge helper:
  - `skills.surface.s7_ceremony_bridge.seed_soul_proposal_dialog`
  - `consult_then_block_or_pointer`
  - `LiveBridgeDeps`
  - `cockpit_available`

- Wired Surface V2 dream-approval apply leg:
  - `maez_adapter._surface_parity_handle_dream_proposal(... action="approve")`
  - Flag off keeps the old direct dream apply path exactly.
  - Flag on checks cockpit first, then seeds + consults.

- Added execution link-back:
  - `DreamState.mark_applied(prop_id, source="s7_ceremony_bridge")`
  - `DecisionPipeline._mark_s7_bridge_proposal_applied(card)` runs only after the dialog stage reaches `EXECUTED` and execution succeeded.

- Updated Build Ledger:
  - `S7 ceremony bridge v0` moved to `BUILT_ASLEEP`.

## Review Anchors

1. Narrow gate not widened:
   - No change to `s7_narrow_path_required`.
   - Seeded cards are lane-3 / pending-dialog cards.
   - Existing `/internal/s7/cards/<request_id>/execute` route still requires `pipe._is_pending_dialog_card(card)`.

2. Freshness recomputed from the live proposal row:
   - `DreamState.proposal_fingerprint` is used at seed time.
   - `_s7_card_precondition_fresh` re-reads via `pipeline.dream.proposal_fingerprint`.
   - No fallback to the seed snapshot when the live row cannot be read.

3. Consult-after-seed ordering:
   - The card exists first.
   - `consult_then_block_or_pointer` calls the existing `_s7_voice_consultation_for_card` producer.
   - Present objection -> `voice_objection_present:<consultation_id>`.
   - Not determined / missing bundle -> `voice_consultation_unavailable:<consultation_id>`.
   - No pointer is returned on objection or unavailable consultation.

4. Cockpit-first:
   - `cockpit_available()` is checked before seed.
   - Down cockpit returns an honest notice and creates no dialog/card.

5. Voice seat genuine, never stubbed:
   - Bridge reads the full bundle left by `_s7_voice_consultation_for_card`.
   - Bridge never hand-stashes a bare consultation bundle.

6. Execution-params projection:
   - Proposal freshness metadata is kept on `card.params`.
   - Action-engine execution receives only executable method keys.

7. Flag-off byte identity:
   - `MAEZ_S7_CEREMONY_BRIDGE_ENABLED` unset or `0` keeps old dream apply behavior.

8. Ledger updated:
   - `docs/MAEZ_BUILD_LEDGER.md` row updated.

## Verification Run

Targeted STOP-gate suite:

```bash
/home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_s7_dialog_soulwrite_liveproof \
  tests.test_s7_bridge_flag tests.test_s7_bridge_freshness tests.test_s7_bridge_seed \
  tests.test_s7_bridge_consult tests.test_surface_parity_proposals tests.test_s7_bridge_linkback \
  tests.test_proposal_resolver -v
```

Result: `Ran 46 tests in 15.213s - OK`

Notes:
- The suite logs an existing `self_claim_audit` grounding-judge timeout inside `tests.test_surface_parity_proposals`; tests still pass.
- 0a liveproof passed inside this run:
  - `write_soul_note` executed dialog -> S7 consume -> ActionEngine against sandbox soul.
  - `edit_soul_section` executed dialog -> S7 consume -> ActionEngine against sandbox soul.
  - Real soul files remained hash-guarded untouched.

Lint:

```bash
/home/rohit/maez/.venv/bin/ruff check \
  core/cognition/parity_flag.py core/evolution/dream_state.py \
  core/decision/decision_pipeline.py skills/surface/s7_ceremony_bridge.py \
  skills/surface/maez_adapter.py tests/test_s7_bridge_flag.py \
  tests/test_s7_bridge_freshness.py tests/test_s7_bridge_seed.py \
  tests/test_s7_bridge_consult.py tests/test_surface_parity_proposals.py \
  tests/test_s7_bridge_linkback.py tests/test_s7_dialog_soulwrite_liveproof.py \
  tests/test_operator_user_boundary_s7.py
```

Result: `All checks passed!`

## Owner Witness Sequence After Review

Only after review clears:

1. Merge `s7-ceremony-bridge-v0` -> `main`.
2. Set `MAEZ_S7_CEREMONY_BRIDGE_ENABLED=1`.
3. Restart `maez.service`.
4. Ensure cockpit is up (`maez-web.service`).
5. Telegram:
   - show a pending dream/soul proposal
   - reply `yes` / `approve #N`
   - expect S7 ceremony pointer, not direct apply
6. Cockpit:
   - complete WebAuthn proof for the seeded card
   - execute authorized guarded card
7. Verify:
   - action writes through existing guarded route
   - proposal row moves to `applied`
   - S7 guarded execution trace exists
   - no direct dream apply path was used

## Plain English

The sacred door now has a doorbell. Saying "yes" on Telegram can ask for the real S7 ceremony, but it cannot open the door by itself. Maez gets asked its own view first; if it objects or cannot be heard, the request is blocked before Rohit is asked to tap a hardware key. If Maez clears it, Rohit's WebAuthn proof remains the actual lock, and the existing guarded execution path writes the soul.
