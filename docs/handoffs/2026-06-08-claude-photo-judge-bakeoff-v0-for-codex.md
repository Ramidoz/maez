# Handoff → Codex: review Photo-Contradiction Judge Bakeoff v0

**From:** Claude (implementation lane) · **To:** Codex (review lane) · **Date:** 2026-06-08
**Branch:** `photo-judge-bakeoff-v0` · **Worktree:** `/home/rohit/maez-wt-photo-judge` · **Base:** main `b4833e5`
**Venv:** `/home/rohit/maez/.venv/bin/python -B -m unittest` (NOT pytest)

## What this is

Lane 2 = the COMPLEMENT to Lane 1's deterministic citation rail: catch
*cited-but-CONTRADICTS* photo replies (the WWDC2024-vs-2026 class). This slice is the
**offline measurement report** — it ranks candidate verifiers on a catch×latency
frontier over a stratified corpus. It is NOT a live gate, wires nothing into Maez, and
touches NO daemon/live path. Owner picks the winner + placement in a follow-on Lane 2b.

3 owner HOLD rounds were cleared during spec+plan review (see the plan's Self-Review).

## What this builds (TDD, strict RED→GREEN→commit, green-gated)

- `e105b06` — stratified corpus `tests/data/judge_eval_photo_contradiction_v1.jsonl`
  (14 cases, all 5 strata; WWDC anchor + numeric must_catch) + validating loader.
- `c8d6209` — `Verdict` + `CandidateAdapter` base + threshold protocol (`THRESHOLD_GRID`,
  `score_to_label`).
- `31d43e8` — six adapters: HHEM, MiniCheck, ThinknCheck, NLI, Reranker (BASELINE-caveated),
  ChatJudge. Model calls live in `_load`/`_raw_predict` (mocked in tests; real API verified
  at obtain-time).
- `9228f69` — aggregator + frontier report (per-stratum, must_catch loud callout,
  `error_count`/`error_rate`, zero-candidates honest path).
- `2cf0c36` — runner `main()` + grid sweep + structural hard-contract + per-case-error.
- `3edb392` — separate pinned+hashed fetch helper (the only network component).

## Review anchors (the things owner review hardened)

1. **Threshold sweep is real, not single-point:** `run_candidate` expands each score-based
   candidate into one row per `THRESHOLD_GRID` point (`name@0.3`…`@0.7`), calling the model
   ONCE per case and re-grading the same raw score. `RunnerMain.test_score_based_candidate_
   expands_across_grid` locks it. Threshold is printed per row.
2. **Hard-contract test is STRUCTURAL + runner-scoped:** `HardContract` parses
   `photo_judge_bakeoff.py` with `ast` and checks behavior (no `huggingface_hub`/`subprocess`/
   fetch-helper import; no `os.environ["MAEZ_JUDGE_BASE_URL"]` assignment; no `open(…,"w")`
   to `model.env`). It inspects the RUNNER FILE ONLY — NOT `photo_judge_bakeoff_fetch.py`,
   whose job IS network. **Please confirm that scoping is correct** (the owner watch-point).
3. **Per-case error never crashes the sweep:** a `None`-score / per-case `unavailable` is
   graded `"error"` (never `score_to_label(None)`): an errored contradiction is MISSED
   (lowers catch, lands in `missed_must_catch` if must_catch), an errored grounded is NOT a
   false flag, both surface as `error_count`/`error_rate` + an `errors` column. Candidate is
   `unavailable` only when EVERY case fails. `test_per_case_error_does_not_crash_the_sweep`.
4. **Downloads are separated:** the runner never fetches; `photo_judge_bakeoff_fetch.py`
   refuses an unpinned revision, records sha256, smoke field is honest (`skipped`/`ok`/
   `failed: …`). Non-live `models/bakeoff/` cache.
5. **Reranker is baseline-caveated** (relevance ≠ entailment); NLI baseline guarantees an
   entailment-shaped verifier even if ThinknCheck's checkpoint isn't released.

## Tests / floor

- Full slice suite `tests.test_photo_judge_bakeoff`: **29 OK**.
- Full discover vs `b4833e5`: **zero real regressions.** Proven additive —
  `git diff --name-only b4833e5..HEAD` is 7 NEW files only (3 scripts, 1 corpus, 1 test,
  2 docs); no existing file is modified, so the slice cannot regress an existing test.
  Branch discover = 15 failures / 35 errors, all in the known ambient worktree-confound
  set (S7-WebAuthn / camera / daemon-proxy / db-path asset gaps + the
  `test_env_only_blocks_against_production_path` order-flake) — NONE in files this slice
  touches; my 29 new tests produce 0 failures under discover. **Empirical clean baseline:**
  `b4833e5` = 14 failures / 34 errors (48 ambient); branch = 15 / 35; the single TRUE
  branch-only delta is `test_env_only_blocks_against_production_path` — it **passes in
  isolation** (the documented order-flake), in a file this slice never touched. Net: zero
  real regressions. (The first baseline pass was cut off by a hanging daemon-proxy test and
  captured empty; a timeout-guarded re-run confirmed it.) See
  [[feedback_worktree_floor_confound]].
- This slice adds only `scripts/*` + a corpus + one test file; no model libs are imported
  in the test suite (every adapter is mocked at its `_load`/`_raw_predict` boundary).

## NOT in v0 (separate steps)

- **Real model downloads + the live bakeoff run** — a SEPARATE owner-greenlit witness step
  AFTER Codex passes (see `…-download-runbook.md`). Agent may download bakeoff artifacts
  (pinned/hashed/non-live); live wiring is owner's.
- **Wiring a winner + placement** (inline / retry-only / post-hoc / memory-labeling) — Lane 2b.

## How to review

```bash
cd /home/rohit/maez-wt-photo-judge   # branch photo-judge-bakeoff-v0
git log --oneline b4833e5..HEAD
/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_photo_judge_bakeoff
```
Live daemon untouched (main `b4833e5`); ledger off (irrelevant here); no merge, no
downloads taken — STOP for review.
