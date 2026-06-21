# Handoff — Earned-Maturity Routing Slice 3a (veto-event ledger + re-ask signal) — REVIEW GATE

**Date:** 2026-06-20. **Branch:** `earned-maturity-slice3a` (last code commit `1fbdbc2`; this handoff on top; local-only, NOT pushed/merged).
**Status:** built (Task 0 + 2 code commits) + Claude two-stage reviewed (Task 0 light controller-verified; Task 1 light controller-verified; Task 2 FULL spec+quality APPROVED). **STOPPED at the review gate** — awaiting Codex cross-lane, then owner breath. NOT live (`MAEZ_VETO_LEDGER` default-off).
**Spec:** `docs/superpowers/specs/2026-06-20-earned-maturity-routing-design.md`. **Plan:** `docs/superpowers/plans/2026-06-20-earned-maturity-routing-slice3a.md`.

## What this slice does (one line)

Makes Maez's vetoes *observable* and captures an honest "was the veto right?" signal — record each veto with its belief snapshot; an explicit exact-repeat re-ask within the window lifts the veto once and *goes to look*; classify the original veto `likely_wrong`/`likely_right`/`uncontested`/`ambiguous` from what that second reach found. **No maturity adjustment** (that's 3c).

## Commits

- `1d370c1` docs(proof): Task 0 GO — 3 seams confirmed (record@5903 / `_would_web_search` / classify `_q`@7230).
- `e7a1317` **Task 1** — `VetoLedger` store + `classify_outcome` (pure; lazy `uncontested`; `likely_right` only when the reach ALSO failed).
- `1fbdbc2` **Task 2 (behavior)** — wire the 3 seams behind `MAEZ_VETO_LEDGER` (record / one-time exact-repeat override / classify).

## Codex cross-lane review anchors

1. **Off = byte-identical.** `MAEZ_VETO_LEDGER` off → no ledger built, no record/override/classify; the only veto-condition change `and _override_event_id is None` is a no-op off-flag (`_override_event_id` set non-None only inside a flag-gated block). No reply-text change either state. (Spec review verified against `1fbdbc2^`.)
2. **Record only a REAL veto (must-fix 1).** `_would_web_search` mirrors the EXACT search gate (`not authoritative_tool_reply and _daemon_parallel_web_search_enabled(transcript, recall_stack_config=_recall_stack_config) and _reflex`); `record_veto` fires only when it's true — a veto that suppressed nothing is never recorded.
3. **Classify only from a REAL outcome (must-fix 2).** Seam 3 attaches only when `_override_event_id is not None AND _routing_turn_outcome_quality is not None`; the value is the real record-site outcome (`structured_evidence`/`empty_but_honest`, set at the executed-search block independent of the writeback flag), refined to `unusable` by `_q` when caveated/thin. NO fabricated `structured_evidence` default.
4. **Notebook always opens (the silent-skip bug).** All 3 seams use `_veto_ledger_get(_ledger)` (builds its own ledger; never relies on a sibling import). `test_ledger_get_opens_notebook_when_none` proves a first veto records even when the override lookup found nothing.
5. **Override lifts ONCE / no loop.** An open same-class in-window event sets `_override_event_id` → the veto is skipped → the search runs → that turn does NOT record a new veto; the event is classified+closed by seam 3.
6. **Silence ≠ wisdom.** No re-ask → `uncontested` (lazy, on next ledger read after the window; no scheduler), weak — NOT `likely_right`. `likely_right` requires a re-ask whose own reach also failed.
7. **No maturity (3a records only); exact-repeat-only v0** (utterance-hash; rephrase invisible; no keyword/regex). Untouched: strict honesty gate, S7, Telegram, time-sense, cockpit-reauth.

## A coupling to know (Task-2 reviewer note)

A single re-ask's verdict can differ by whether `MAEZ_ROUTING_QUALITY_WRITEBACK` is also on: with it on, a caveated/thin reach refines the outcome to `unusable` → `likely_right`; with it off, the raw `structured_evidence` → `likely_wrong`. This is intended (the writeback IS the honest "the reach was junk" signal). For the witness, the owner already runs `WRITEBACK=1` live (Slice 1), so the refined verdict applies.

## Verification

`test_veto_ledger` + `test_veto_ledger_seams` GREEN (incl. `-W error::ResourceWarning`); regression `test_routing_priors`/`_veto_seam`/`test_routing_observation`/`_writeback`/`test_support_gate` GREEN; ruff clean. Scope: 5 files (veto_ledger + daemon + 2 tests + Task-0 proof).

## Owner-breath (after both-lanes PASS + merge — owner-sovereign)

Code only; restart `maez`. Prereq: `MAEZ_ROUTING_PRIORS_ENABLED=1` (already live from Slice 1, so vetoes fire). Set `MAEZ_VETO_LEDGER=1` in `/home/rohit/.config/maez/model.env`; restart. Then:
1. Send "summarize today's signals" (the veto fires — Maez answers inward). A `veto_events` row is written.
2. **Re-ask the exact same** ("summarize today's signals") within the hour — Maez **lifts the veto once and searches** (the override), and that reach's outcome classifies the original veto.
3. Paste: `sqlite3 ~/maez/memory/veto_ledger.db "SELECT class_id, prior_confidence, reask_outcome_quality, classification FROM veto_events;"` — expect the veto row + the re-ask's outcome + an honest classification (`likely_right` if the reach was also junk, `likely_wrong` if it found useful data). A veto with no re-ask → `uncontested` after the hour. No autonomous check.
