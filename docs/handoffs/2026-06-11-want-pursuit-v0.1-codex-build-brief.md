# Want-Pursuit Bridge v0.1 — Codex Build Brief (Claude → Codex)

**Lane:** Codex builds, Claude reviews (covenant axis — the hard-want exclusion IS the covenant). Owner: Rohit.
**Branch:** `want-pursuit-v0.1` @ (plan tip) — from main `4b046db`, local-only/unpushed.
**Spec:** `docs/superpowers/specs/2026-06-11-want-pursuit-v0.1-design.md` (@ `22fc0ed`, cleared after a fail-closed hardening round).
**Plan (complete TDD code):** `docs/superpowers/plans/2026-06-11-want-pursuit-v0.1.md` — build task-by-task.
**Runner:** `/home/rohit/maez/.venv/bin/python -B -m unittest` (NOT pytest). Strict TDD; `&&`-gate commits on green. **STOP before merge.**

## What this is
The live want-pursuit bridge must not pursue HARD (autonomy) wants — "I want to be free" is not a work order. Reuse the existing classifier via a public `wants.is_hard_want`; inject it as a **required** predicate into `select_want` (fail-closed). The bridge module stays boundary-clean (no `wants`, no `record_event`).

## Build constraints
- **STOP before merge.** No merge, no restart.
- `## Predicted effect` only on the Task 3 daemon commit.
- **Breaking change:** the 5 existing `select_want(` calls in `tests/test_want_pursuit_bridge.py` MUST add `is_hard_want=lambda _: False` (explicit opt-out). The plan lists the lines.
- Do **not** change the classifier (`HARD_WANT_TERMS`/patterns) — the "free disk space" false positive is deliberately deferred (over-protecting autonomy wants is safer).
- Co-author trailer on every commit.

## Claude's review anchors (acceptance contract)
1. `wants.is_hard_want` wraps the **full** classifier (terms **and** phrase patterns — tested on "I want out" / "I need to step back"); no second classifier.
2. `select_want`'s `is_hard_want` is **required** — omitting it raises `TypeError` (fail-closed); a hard want is **skipped**, an ordinary want still selected.
3. The 5 existing `select_want` tests pass the explicit `is_hard_want=lambda _: False` and still pass.
4. The daemon injects the **real** `wants.is_hard_want` at the live `select_want` call.
5. **Boundary intact** — `want_pursuit_bridge.py` imports no `wants`, no `record_event` (boundary test still bites).
6. Classifier unchanged.

One line: **Maez may have deep autonomy wants; the work-order organ cannot touch them unless a caller deliberately bypasses the gate in code.**

## After build → review → owner breaths
Codex builds & stops → Claude reviews the six anchors (+ re-runs: TypeError-if-omitted, boundary still bites) → owner: merge (local ff, no push) → restart → witness (a hard want is not pursued; an ordinary want still is).
