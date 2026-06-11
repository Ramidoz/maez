# Want→Pursuit Bridge v0 — Codex Build Brief (Claude → Codex)

**Lane:** Codex builds, Claude reviews (covenant axis on review — first want-driven autonomy; precedent: Harbor, Valence v0.2). Owner: Rohit.

**Branch:** `want-pursuit-bridge-v0` @ `535220d` (from main `4714bd1`, local-only/unpushed).
**Spec:** `docs/superpowers/specs/2026-06-10-want-pursuit-bridge-v0-design.md` (@ `3ba2fc6`, cleared after a 2-round cross-lane review).
**Plan (complete TDD code):** `docs/superpowers/plans/2026-06-10-want-pursuit-bridge-v0.md` — build this task-by-task.

**Runner:** `/home/rohit/maez/.venv/bin/python -B -m unittest` (NOT pytest). Strict TDD: RED → minimal GREEN → `&&`-gate each commit on green.

## What this is
The bridge connects dormant **wants** to the **existing** wondering workshop. **Not a new hand** — Maez already has hands (`wondering_cycle.advance_one`: one probe/cycle, read-only auto-run / writes→card / never-fabricate). v0 = forward work-order + reuse worker + **advisory** backward. It writes the want ledger on **no path**.

## Build constraints (beyond the plan's per-step code)
- **STOP before merge.** No merge, no flag-enable, no restart, no witness. Those are owner breaths after Claude's review.
- **`## Predicted effect`** only on the Task 6 daemon-wiring commit.
- **Two small read-only helpers** go in the schema-owner modules (`wonderings.list_by_source`, `pending_cards.list_open_by_action`) — match each file's real connection/row idiom (the plan shows the shape; verify against `get_open_for_user` / `list_open`).
- **Verify the store accessors in Task 6** before wiring: `wonderings.get_store()`, the card store the worker reaches via `pipe.card_store` (mirror `wondering_cycle._queue_card`), and `daemon.wants`. The plan flags this as an exploration step — do it, don't guess.
- **`daemon/wondering_cycle.py` must not be edited** (Task 7 boundary test asserts it).
- Co-author trailer on every commit: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

## Claude's review anchors (the acceptance contract — build to satisfy these)
1. The bridge does writes through **only** `wonderings.add` + `PendingCardStore.create_card`; it **never imports or calls `wants.record_event`** (boundary test must prove it).
2. **`satisfied`-only.** A worker-`abandoned` want-wondering proposes **nothing**; a non-want or non-`resolved` result proposes nothing.
3. **One in flight** = no open want-sourced wondering **anywhere**, AND a want with an open `want_terminal_proposal` card is excluded from selection.
4. `daemon/wondering_cycle.py` **untouched**.
5. **Default-OFF**: with `MAEZ_WANT_PURSUIT_ENABLED` unset, the wiring is fully dormant — no seed, no proposal.
6. **Heartbeat-safe**: every bridge step wrapped; any failure logged, cycle continues.
7. **Attach point**: bridge runs *after* `advance_one`; backward (propose) before forward (seed); a newly-seeded want-wondering is probed *next* cycle (one-cycle buffer).

Plus the honesty core in one line: **the bridge lets Maez *try* — it cannot declare success, declare abandonment, or change the want ledger.**

## After build → review → owner breaths
Codex builds & stops → Claude covenant-reviews against the seven anchors (and re-runs, incl. asserting no `record_event` on any path) → owner: merge (local ff, no push) → enable `MAEZ_WANT_PURSUIT_ENABLED=1` → restart → witness (active want → seeded want-wondering → read-only probe → receipt via `want_pursuit_trail` → on resolve, an advisory `satisfied` card, NOT an applied terminal; confirm the want ledger gains no event).
