# Evidence-Grounding Verifier Audition — Gate Handoff

**Branch:** `grounding-audition-v0` (worktree, from main `63bd874`)
**Spec:** `docs/superpowers/specs/2026-06-11-evidence-grounding-verifier-audition-design.md` @ `57cedc3`
**Plan:** `docs/superpowers/plans/2026-06-11-evidence-grounding-verifier-audition.md` @ `63bd874`
**Status:** BUILT + unit-tested (mocked). **STOPPED at the gate. No real-model run, no merge, no download has happened.**

## What's built (`scripts/grounding_bench/`)
- `corpus_schema.py` — row schema + `validate_corpus` (enforces the absent↔abstain invariant, reasoned-rationale, unique ids).
- `corpus.json` — **26 hand-labeled cases**, taxonomy-balanced (7 grounded / 5 cited-but-unsupported / 5 false-specific / 4 stale-over-current / 3 no-evidence-abstain / 2 multi-claim), label split 8 SUPPORTED / 15 UNSUPPORTED / 3 ABSTAIN, **4 real-longmemeval + 22 flagged synthetic**, labeled for grounding (not correctness), every row reasoned.
- `adapter_prompt.py` — the **reviewed 4B-entailment-adapter prompt** (the LLM yardstick; explicitly an entailment check, not the overclaim contract).
- `verifiers.py` — `HhemVerifier` (**unavailable by construction** — `HHEM_REVISION=None` → `ERROR(HhemRevisionUnconfigured)`, no download), `MinicheckVerifier` (lazy load), `FourBAdapterVerifier` (the 4B yardstick via the judge endpoint).
- `bench_grounding.py` — the harness: **abstain precondition** (no model called on `claimable_absent`), HHEM threshold sweep, **per-mode false-negative headline** report (CSV + MD).
- `tests/test_grounding_bench.py` — **20 tests, all green, all mocked** (no model loads). Key tests: abstain-precondition-calls-no-model; HHEM-unconfigured-errors-without-download; per-mode false-negative tally; the entailment-not-overclaim prompt assertion.

**Floor:** `20 tests OK`, `ruff` clean. Mocked smoke confirmed a "blesses-everything" verifier is flagged 5/5, 5/5, 4/4 false-negatives across the dangerous modes (the obstacle course bites), and the 3 no-evidence cases abstained without a model call.

## The three HARD GATES — clear all before the scorecard run
1. **Corpus label review** — read each case's `(evidence, claim, expected, rationale)` and confirm the *grounding* label, case-by-case. The flagged judgment calls: `ffs-4` (a *true-in-the-world* claim labeled UNSUPPORTED because the given evidence lacks the specific — tests world-knowledge leakage), `cbu-3`/`mc-1` ("improves reasoning" doesn't follow from "lossless"), `pos-3` (2.1× → "roughly doubles"), the `strict_rule` pair `mc-1`/`mc-2`.
2. **4B-adapter prompt review** — `adapter_prompt.py:ENTAILMENT_SYSTEM_PROMPT` is the yardstick; a biased prompt biases the whole scorecard.
3. **HHEM download owner-approval + pin** — `HhemVerifier` ships inert until `HHEM_REVISION` is set; nothing has downloaded. Owner approves the ~440MB download + `trust_remote_code` execution.

## Post-gate sequence (only after all three clear)
1. Resolve the current commit sha of `vectara/hallucination_evaluation_model`; set `HHEM_REVISION` in `verifiers.py` to it (full 40-char sha).
2. **API-confirmation smoke** — load HHEM + MiniCheck on one pair each; confirm the `.predict` / `(doc,claim)` call shapes match the adapters; **adjust the adapters if the real call differs — do not force the snippet.**
3. **Run the scorecard:** `/home/rohit/maez/.venv/bin/python -B scripts/grounding_bench/bench_grounding.py` (judge endpoint up on 8081 for the 4B-adapter row). Optionally add the production-`grounding_judge` diagnostic row.
4. Read `results_grounding.md` — decide on the *per-mode false-negative* headline whether a verifier earns a follow-on slice to wire it into the live grounding path.

**Scope:** offline scorecard only. No live-daemon change. The deterministic citation rail + the `forbidden`/`self_history` overclaim rail are untouched; no-citation cases are excluded by design.
