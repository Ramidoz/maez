# Codex Handoff — Recall Citation Accuracy Slice

**From:** Claude · **To:** Codex · **Date:** 2026-05-31
**Branch base:** `main` (spec @ 5804af4 + plan + this brief committed; flag-off, no live flip).

## What you're building
Behind `MAEZ_RECALL_CITATION_RENDER_V2` (**default-off**), fix the confirmed `[E1]` positional/salience double-privilege in `core/routing/focused_cognition.py` so qwen cites the exact evidence item a fact came from — **without** altering live v1 and **without** post-hoc citation repair. Verified by the brain benchmark (owner-run paired v1/v2).

**Read first:** plan `docs/superpowers/plans/2026-05-31-recall-citation-accuracy.md` (the contract); spec `docs/superpowers/specs/2026-05-31-recall-citation-accuracy-design.md`. Confirmed root cause: `_render_evidence_lines` repeats `items[0]` as `(most important, repeated) [E1]` + budget double-counts it (~line 527).

## Process
- **Six-agent pre-code pass first** (non-decorative). Pressure, in order:
  1. **Flag-OFF byte-identity** — is v1 rendering AND budget weighting truly unchanged? (golden + double-count test). The real risk is breaking live v1 while adding v2.
  2. **v2 golden** — exact card format **carrying date/provenance**; a future refactor that drops them must FAIL the test (the multi_year fix depends on dates being visible).
  3. **Prove-ran-v2** — the recorded `citation_render_version` must derive from the *actual* render path at synthesis time, not the launcher's intent; launcher must pass the flag through.
  4. **No post-hoc repair** — confirm nothing anywhere rewrites the model's citation. Fix is input + task ONLY.
- Then 7+3, RED-first, plan task order. **Task 1 pins v1 before v2 exists.** Scoped commits.
- No live flip. Genderless. 2a frozen.

## Hard constraints
- `MAEZ_RECALL_CITATION_RENDER_V2` default-off → byte-identical v1. Benchmark runs with it on.
- v2 = drop the repeated line + position-neutral per-item headers (label · date/provenance · source-type · authority · text) + cite-exact-item instruction + no budget double-count. Producer-causality: never rewrite the output.
- The two owner tightenings are **required tasks**, not optional: flag-off byte-identity golden (Task 1) and v2 format golden incl. date/provenance (Task 2); plus prove-ran-v2 (Task 5).

## Handback shape (for Claude cross-verify + coverage panel)
Commits; exact test output (focused-cognition + brain-bench + 2a all green); the flag-off byte-identity proof; the v2 golden; the prove-ran-v2 proof (recorded version tracks flag + dump shows v2 card shape); six-agent concrete deltas; any deviations disclosed. I re-run all suites myself, confirm v1 byte-identity, and fire the coverage panel before merge flag-off.

## Verification is owner-operated (not your job)
The pass/fail is the **owner-run paired benchmark** (v1 off then v2 on, same session): multi_year materially >6/10, dated_hit ≥9/10, both_shaped ≥8/10, overall grounded not regressed, any new false/wrong-absence = blocker. You build the flagged change + tests; the benchmark verdict is Rohit's/Claude's run.

## Out of scope
Post-hoc citation repair; the verifier-as-gate (separate second slice, only if this fails); non-positional salience re-add (only if grounded-rate regresses, measured); any live flip; model/hardware changes.
