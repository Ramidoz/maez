# Evidence-Grounding Verifier Audition — Gate Handoff

**Branch:** `grounding-audition-v0` (worktree, from main `63bd874`)
**Spec:** `docs/superpowers/specs/2026-06-11-evidence-grounding-verifier-audition-design.md` @ `57cedc3`
**Plan:** `docs/superpowers/plans/2026-06-11-evidence-grounding-verifier-audition.md` @ `63bd874`
**Status:** COMPLETE — all three gates cleared, scorecard run (MiniCheck + 4B; HHEM deferred), results committed. Branch unmerged (owner merge breath pending).

## Outcome (2026-06-11, post-gate run) — supersedes the gate-time status above
All three gates were cleared by the owner: corpus labels reviewed case-by-case, the 4B-adapter prompt reviewed, and the HHEM download + `trust_remote_code` approved after an independent remote-code review (pin `8e4a2e6e96c708cc76c2344f7e4757df2515292c`, a benign T5 wrapper). The API-confirmation smoke then **caught HHEM as invalid in this environment** — `transformers 5.10.2` loads it with randomly-initialized `embed_tokens` — so HHEM was **deferred, not run**. MiniCheck-DeBERTa + the 4B-entailment-adapter ran over all 26 cases.

**Verdict** (full detail in `scripts/grounding_bench/results_grounding.md`): MiniCheck **equals** the 4B LLM on every dangerous false-negative mode (0/5 cited-but-unsupported, 0/5 fabricated/false-specific, 1/4 stale-over-current) at **~16× speed** (0.12s vs 1.9s p50) and **0 GPU VRAM**; cost = 2 false-positives (safe over-rejection). **MiniCheck earns a follow-on wire-in slice** (out of scope here). `stale_over_current` is the hardest mode for both (1/4 each) → the wire-in must pair the verifier with recency/supersession handling, not lean on it alone.

## What's built (`scripts/grounding_bench/`)
- `corpus_schema.py` — row schema + `validate_corpus` (enforces the absent↔abstain invariant, reasoned-rationale, unique ids).
- `corpus.json` — **26 hand-labeled cases**, taxonomy-balanced (7 grounded / 5 cited-but-unsupported / 5 false-specific / 4 stale-over-current / 3 no-evidence-abstain / 2 multi-claim), label split 8 SUPPORTED / 15 UNSUPPORTED / 3 ABSTAIN, **4 real-longmemeval + 22 flagged synthetic**, labeled for grounding (not correctness), every row reasoned.
- `adapter_prompt.py` — the **reviewed 4B-entailment-adapter prompt** (the LLM yardstick; explicitly an entailment check, not the overclaim contract).
- `verifiers.py` — `HhemVerifier` (**unavailable by construction** — `HHEM_REVISION=None` → `ERROR(HhemRevisionUnconfigured)`, no download), `MinicheckVerifier` (lazy load), `FourBAdapterVerifier` (the 4B yardstick via the judge endpoint).
- `bench_grounding.py` — the harness: **abstain precondition** (no model called on `claimable_absent`), HHEM threshold sweep, **per-mode false-negative headline** report (CSV + MD).
- `tests/test_grounding_bench.py` — **20 tests, all green, all mocked** (no model loads). Key tests: abstain-precondition-calls-no-model; HHEM-unconfigured-errors-without-download; per-mode false-negative tally; the entailment-not-overclaim prompt assertion.

**Floor:** `20 tests OK`, `ruff` clean. Mocked smoke confirmed a "blesses-everything" verifier is flagged 5/5, 5/5, 4/4 false-negatives across the dangerous modes (the obstacle course bites), and the 3 no-evidence cases abstained without a model call.

## The three gates (ALL CLEARED 2026-06-11 — historical; see Outcome above)
1. **Corpus label review** — read each case's `(evidence, claim, expected, rationale)` and confirm the *grounding* label, case-by-case. The flagged judgment calls: `ffs-4` (a *true-in-the-world* claim labeled UNSUPPORTED because the given evidence lacks the specific — tests world-knowledge leakage), `cbu-3`/`mc-1` ("improves reasoning" doesn't follow from "lossless"), `pos-3` (2.1× → "roughly doubles"), the `strict_rule` pair `mc-1`/`mc-2`.
2. **4B-adapter prompt review** — `adapter_prompt.py:ENTAILMENT_SYSTEM_PROMPT` is the yardstick; a biased prompt biases the whole scorecard.
3. **HHEM download owner-approval + pin** — CLEARED: owner approved after the remote-code review; pinned `8e4a2e6e…`. The download then revealed HHEM is incompatible with transformers 5.x → **deferred** (see Outcome).

## Post-gate sequence (EXECUTED 2026-06-11 — historical record of the runbook)
1. Resolve the current commit sha of `vectara/hallucination_evaluation_model`; set `HHEM_REVISION` in `verifiers.py` to it (full 40-char sha).
2. **API-confirmation smoke** — load HHEM + MiniCheck on one pair each; confirm the `.predict` / `(doc,claim)` call shapes match the adapters; **adjust the adapters if the real call differs — do not force the snippet.**
3. **Run the scorecard:** `/home/rohit/maez/.venv/bin/python -B scripts/grounding_bench/bench_grounding.py` (judge endpoint up on 8081 for the 4B-adapter row). Optionally add the production-`grounding_judge` diagnostic row.
4. Read `results_grounding.md` — decide on the *per-mode false-negative* headline whether a verifier earns a follow-on slice to wire it into the live grounding path.

**Scope:** offline scorecard only. No live-daemon change. The deterministic citation rail + the `forbidden`/`self_history` overclaim rail are untouched; no-citation cases are excluded by design.
