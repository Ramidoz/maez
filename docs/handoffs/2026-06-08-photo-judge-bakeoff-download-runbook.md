# Photo-Contradiction Judge Bakeoff — Download / Smoke Runbook

**Status:** execution+witness step, run AFTER the code lands + Codex passes.
**Policy (owner-set):** agent may download bakeoff artifacts — PINNED revision,
sha256-recorded, into the NON-live `models/bakeoff/` cache, NEVER started as a
service / wired into env / systemd. Live wiring is Lane 2b + owner's.

The fetch helper is the ONLY network component. The runner
(`scripts/photo_judge_bakeoff.py`) never downloads.

## Per-candidate fetch (fill `--revision` with a PINNED commit SHA at obtain-time)

```
/home/rohit/maez/.venv/bin/python -B -m scripts.photo_judge_bakeoff_fetch \
    --repo-id <hf repo> --revision <PINNED sha/tag> --name <name>
```

| name | candidate | likely repo_id (verify at obtain) | revision (PIN) | sha256 | smoke |
|---|---|---|---|---|---|
| hhem | Vectara HHEM-2.1-Open | `vectara/hallucination_evaluation_model` | _TBD_ | _record_ | _record_ |
| minicheck | Bespoke MiniCheck (small) | `bespokelabs/Bespoke-MiniCheck-RoBERTa-Large` (verify exact id/size) | _TBD_ | _record_ | _record_ |
| nli | DeBERTa-v3 NLI baseline | `MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli` | _TBD_ | _record_ | _record_ |
| reranker | Qwen3-Reranker-0.6B (BASELINE only) | `Qwen/Qwen3-Reranker-0.6B` | _TBD_ | _record_ | _record_ |
| thinkncheck | ThinknCheck 1B-Q4 Gemma3 (arXiv 2604.01652) | _verify a checkpoint is RELEASED_ | _TBD_ | _record_ | _record_ |

- **ThinknCheck obtainability is verified HERE.** If no checkpoint is released
  (paper-only), record it `unavailable` — NOT a blocker; the other candidates run.
- The `--revision` MUST be a specific commit/tag (the helper refuses an empty
  revision). Record the printed `sha256` in the table above.
- The exact model API for each adapter (`_load` / `_raw_predict`) is verified here
  too; adjust the adapter body if a real API differs from the best-known form. The
  unit tests mock that boundary, so they stay green across such adjustments.

## Smoke

The fetch CLI records `smoke: skipped` by default — the **runner's adapter-load is
the integration smoke** (a candidate that won't load is recorded `unavailable` and
skipped, never crashing the run). To smoke at fetch-time, call `fetch_one(...,
smoke_fn=<load+predict>)` programmatically.

## Run the bakeoff (after artifacts are present)

```
/home/rohit/maez/.venv/bin/python -B -m scripts.photo_judge_bakeoff \
    --label real-20260608
# → logs/photo_judge_bakeoff/real-20260608.md + .json (gitignored)
```

The report ranks the catch×latency frontier with per-threshold rows for score-based
candidates, a loud `MISSED MUST-CATCH` line for any missed anchor/numeric case, an
`errors` column, and a `RECOMMENDATION`. Latency is REPORTED, not gated — the owner
picks the winner + placement (inline / retry-only / post-hoc / memory-labeling) in
Lane 2b.
