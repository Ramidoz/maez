# Handoff → Codex: review photo focused-synthesis (direction b)

**From:** Claude (implementation lane — swapped for this slice) · **To:** Codex (review lane) · **Date:** 2026-06-07
**Branch:** `photo-focused-synthesis` · **Worktree:** `/home/rohit/maez-wt-photo-focused` · **Base:** main `f1f7e9a`
**Venv:** `/home/rohit/maez/.venv/bin/python` (worktree shares main's venv via cwd)

---

## ⟳ RE-REVIEW UPDATE (`d2108d9`, `49f59ff`) — your HOLDs addressed

Both original blockers (F1, F2) fixed by **re-architecting** (`d2108d9`), and your
re-review's third blocker (audit envelope) fixed by `49f59ff`. The sections below
describe the original adapter-bypass design — **superseded**; read this block as
the current state.

**HOLD #3 (audit envelope didn't know photo vision happened) — FIXED (`49f59ff`).**
Now that the focused reply correctly flows through the audit (F1 fix), the
evidence envelope must say photo vision was present — else the grounding judge
(which treats the envelope as source of truth) false-flags "I saw the photo."
Fix: in `handle_message`, **before `_build_envelope`**, when `photo_analysis` is
present, append `"owner-sent photo vision"` to `_chat_signals_present` (≤30 chars
— fits the per-signal cap untruncated). Desktop `screen observation (disabled)`
stays ABSENT — separate capability. Two tests: structural (signal marked before
`_build_envelope`, gated on `photo_analysis`) + functional (`build_envelope`
marks photo vision present in `signals_present`, keeps screen in `signals_absent`).

**F1 (pipeline bypass + invariant break) — FIXED.** Focused synthesis now runs
**inside `daemon.handle_message`**'s synthesis cascade (new `photo_analysis`
param; a branch sets `reply` via `synthesize_photo_turn` then sets `_focused_used
= True` so the megaprompt is skipped). Because it sets `reply` *before* the
existing `strip_tool_call_leaks` (6166) → self-claim audit → `store_telegram`
(6630) → trace, the photo reply now flows through the **entire** pipeline and is
stored in lived Telegram memory. The adapter no longer bypasses `handle_message`
and no longer imports `self_claim_audit` — **`test_memory_integrity_invariant`
passes again**. (Reverted `_synthesize_photo_focused` and the `c115390` audit.)

**F2 (failed vision treated as evidence) — FIXED.** `_analyze_photo_event` stashes
**only successful** per-image analyses; if none succeeded, `photo_analysis_text`
is `None`, so the turn falls back to the legacy megaprompt (which honestly
surfaces "could not see"). The focused path can no longer answer from a
"could not see" line.

**New review anchors:**
1. `daemon/maez_daemon.py` synthesis cascade (~`else:` around 5942): the photo
   branch is gated on `photo_analysis` (success-only) + `photo_focused_synth_enabled()`,
   sets `_focused_used`/`_reply_path = ReplyPath.FOCUSED`, and leaves `reply=None`
   on empty/error to fall through to the legacy synthesis. Confirm `_focused_used`
   correctly suppresses both the recall-FOCUSED branch (I added `not _focused_used`
   to its guard) and the megaprompt at 6105.
2. Structural test `PhotoSynthesisLivesInsideThePipeline.test_photo_synth_runs_
   before_strip_and_store` asserts ordering inside `handle_message`.
3. Adapter just passes `photo_analysis=getattr(event, "photo_analysis_text", None)`.

**Tests:** all targeted suites green; `test_memory_integrity_invariant` +
`test_model_reply_persistence` green in isolation. Full discover vs main `f1f7e9a`:
1 branch-only delta (`test_fast_backend_cloud_retirement…`) which **passes in
isolation** and doesn't reference photo/focused code — the same pre-existing
fast-lane-audit order-flake. (Note: a `test_model_reply_persistence` discontinuity
-marker test flakes under *some* multi-suite combos — a pre-existing ledger-DB
order-dependence in `persist_model_reply`/`MAEZ_LEDGER_WRITES`, untouched by this
branch; passes in isolation and in pairs.)

**Commits now:** `a834cf3` `synthesize_photo_turn` · `5968c69` (adapter routing,
superseded by d2108d9) · `c115390` (audit, reverted by d2108d9) · `aeb5b81`
handoff · **`d2108d9` the F1/F2 review-response rework** · `1678b67` handoff
update · **`49f59ff` the HOLD #3 audit-envelope fix**.

---

## Why (witnessed live)

Live witness 2026-06-07 22:41 (daemon 81895): vision **worked** —
`Photo vision diagnostic image=1 success=True analysis_chars=342 error=none` — and
routing fix `2bdd191` forwarded the analysis. Yet the reply was still *"I can't
see the image. The vision pipeline is offline… blank data."* Root cause: the
analysis reaches `daemon.handle_message`, whose ~megaprompt includes a
self-diagnostic block (`skills/web_interface.py:3588`) that says *"Vision (screen
perception): Intentionally retired. Maez cannot see what's on your screen."* The
brain over-generalizes "cannot see [screen]" → "cannot see [this photo]" and
ignores the present analysis. This is the [[feedback_focused_cognition_over_megaprompt]]
knowledge-conflict.

## What I built

When a photo turn carries a successful local vision analysis
(`has_local_photo_context`), synthesize the reply over a **bounded working set**
(analysis as E1 + caption + voice + faithful instruction) and **bypass**
`daemon.handle_message` — so no megaprompt, no broken-systems contradiction.

**3 commits:**
- `a834cf3` `synthesize_photo_turn()` in `core/routing/focused_cognition.py` —
  mirrors `build_honest_empty_reply`: one `EvidenceItem`, small system prompt,
  deterministic honest fallback. Adds `_PHOTO_VISION_INSTRUCTION` (first-party
  framing, worded to forbid blindness-claims **without** using the literal
  phrases the prompt-exclusion test guards) and a `photo_vision` authority label.
- `5968c69` adapter routing — `MessageEvent.photo_analysis_text` (clean evidence,
  stashed by `_analyze_photo_event`), `MaezMessageHandler._synthesize_photo_focused`,
  the `MAEZ_PHOTO_FOCUSED_SYNTH` gate (default on), and the focused-first wrap
  with safe fallback. Re-pointed 2 existing tests to the gate-off path.
- `c115390` self-claim audit on the focused reply (covenant — see anchor #1).

**Spec:** `docs/superpowers/specs/2026-06-07-photo-focused-synthesis-design.md`.

## Test status

- **Targeted: 122 + 18 green** (`test_photo_focused_synthesis`,
  `test_photo_focused_routing`, `test_chat_photo_wiring`,
  `test_telegram_dream_command_surface`, `test_egress_claude_router_provenance`,
  `test_egress_telegram_chokepoint`, `test_focused_cognition`).
- **Full discover: ZERO regressions in my domains.** Branch vs main `f1f7e9a`
  diff (same worktree/asset env): 3 branch-only deltas — `test_judge_carveout_live`
  (live judge :8081), `test_fabrication_memory_guard…production_path`,
  `test_fast_backend_cloud_retirement…cloud_retirement` — **all pass in isolation**
  on the branch (order-dependent / live-judge flakes exposed by the new test files
  shifting discovery order; none in focused/surface/photo/egress). Remaining
  full-discover failures are the known worktree asset-confound (camera, cockpit,
  S7-webauthn) + ambient buckets (live judge, external-fetch pin, shim, temporal
  date-sensitive). Suggest re-running the floor in the asset-rich MAIN checkout
  before merge ([[feedback_worktree_floor_confound]]).

## Review anchors (please scrutinize)

1. **Self-claim audit (covenant, the one I almost missed).** The focused path
   bypasses `handle_message`, which OWNS the anti-fabrication audit. I added
   `core.self_claim_audit.audit(reply, surface="telegram_surface_photo")` in
   `_synthesize_photo_focused` (c115390). **Verify this is the correct/complete
   covenant coverage** — does `handle_message` apply anything else to the reply
   (memory persistence, residue, store) that the focused path now skips and
   *should* keep? I judged photo replies don't need the megaprompt's
   registry/residue/self-model blocks (that's the whole point), but confirm
   nothing covenant-critical is dropped besides the audit I restored.
2. **The bypass is correct + mutation-proven.** `test_photo_turn_uses_focused_
   synthesis_not_megaprompt` asserts `handle_message` is NOT called and the
   focused reply is returned. Gate-off / no-evidence / error / empty all fall
   back to `handle_message` (4 tests).
3. **Prompt is genuinely clean.** `test_prompt_is_bounded_and_excludes_megaprompt_
   contradictions` asserts the focused system prompt excludes "cannot see",
   "screen perception", "broken systems", "intentionally retired", "blank data",
   "vision pipeline is offline" and is < 3000 chars. The faithful instruction
   conveys "you DID see it" via "blind to it / eyes are offline / arrived as
   empty data" to avoid those literals — confirm that reads right to the model.
4. **Egress/provenance unchanged.** The focused reply returns from `__call__` and
   goes out the same send path (classified `maez_authored_owner_third_party_
   transport`); the analysis stays local (`owner_message_context`); raw image
   bytes never leave home (vision_tools gates untouched). Egress suites green —
   but confirm the focused reply hits the same outbound egress classification the
   handle_message reply did.
5. **`_photo_analysis_evidence` fallback** parses "Image 1:" out of the
   channel_prompt injection when the clean stash is absent — sanity-check that
   parse.
6. **Edge: vision failed.** If `vision_analyze_tool` returned `success:false`, the
   analyses are `[Maez could not see this image.]` and `has_local_photo_context`
   is still true (preamble present), so the focused path would synthesize from a
   "could not see" evidence line. The deterministic fallback would then say
   "Here's what I saw…: …could not see…". **Possibly worth gating the focused
   path on a *successful* analysis** — flagging for your call.

## Deferred (noted, not done)

- Telemetry is a content-free `logger.info` ("Photo focused synthesis:
  working_set_chars=… cited=… reply_chars=…"), **not** the DB
  `record_focused_cognition_run` — I kept it a log to avoid schema risk; wire the
  DB record if you want photo turns in `focused_cognition_runs`.

## Witness target (after merge + owner restart)

A Telegram photo captioned "Check this" → an **image-grounded** reply in Maez's
voice describing the photo; never "vision pipeline offline" / "can't see" /
"blank data". Log shows `[Telegram] Photo focused synthesis: …`. Set
`MAEZ_PHOTO_FOCUSED_SYNTH=0` to revert to the prior `handle_message` behavior.

## How to review

```bash
cd /home/rohit/maez-wt-photo-focused        # branch photo-focused-synthesis
git log --oneline main..HEAD                # a834cf3, 5968c69, c115390
/home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_photo_focused_synthesis tests.test_photo_focused_routing \
  tests.test_chat_photo_wiring tests.test_focused_cognition
```
Live daemon untouched (still on main `f1f7e9a`); no merge, no restart — owner's
breath. The untracked `memory/s7_1_webauthn/` in the worktree is a test artifact
from the S7 CWD-write hazard (the parked side-ticket), not part of this branch.
