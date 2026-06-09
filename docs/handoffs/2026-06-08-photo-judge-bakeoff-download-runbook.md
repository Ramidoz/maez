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

| name (`--name`, must match `CandidateSpec.name`) | candidate | likely repo_id (verify at obtain) | revision (PIN) | sha256 | smoke |
|---|---|---|---|---|---|
| hhem | Vectara HHEM-2.1-Open | `vectara/hallucination_evaluation_model` | `8e4a2e6e96c708cc76c2344f7e4757df2515292c` | `d900412605dc3fa496037922e119d498520d530992dbb30261538da53866e55b` | fetch skipped; runner loaded with Transformers-5 shim |
| minicheck-roberta | MiniCheck RoBERTa-Large | `lytang/MiniCheck-RoBERTa-Large` | `74c8919647e61ed0f71bc177d94f10930f090068` | `0576e5777bf1c79158f2c975c918721f57c1194678c0f8c7877c986a24e6b01f` | fetch skipped; runner loaded |
| minicheck-flan-t5 | MiniCheck Flan-T5-Large | `lytang/MiniCheck-Flan-T5-Large` | `96eafd01cee2d16cf81aaa2fb226b14f422a37b3` | `9037cda4eb817b0e7d596439f147625b834e16500c435e3580af5d0dd2581e15` | fetch skipped; runner loaded |
| minicheck-deberta | MiniCheck DeBERTa-v3-Large | `lytang/MiniCheck-DeBERTa-v3-Large` | `2f2d01a54fa022a7ffadb76260e1ea8bc88c82bb` | `e299a33ff200bb879dc7248cbab8a50f127c5d0fb08d1fffd86c3598aebaf62e` | fetch skipped; runner loaded |
| nli | DeBERTa-v3 NLI baseline | `MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli` | `6f5cf0a2b59cabb106aca4c287eed12e357e90eb` | `c504f1da00c343a8989048f6f941cd804b64b8833a3773402ed8a6b586a20bbc` | fetch skipped; runner loaded |
| reranker | Qwen3-Reranker-0.6B (BASELINE only) | `Qwen/Qwen3-Reranker-0.6B` | `e61197ed45024b0ed8a2d74b80b4d909f1255473` | `99a509a286c362a3fa87796660e0468c1f69e2768a1337511e2176ed0ea5d8d3` | fetch skipped; runner loaded |
| thinkncheck | ThinknCheck 1B-Q4 Gemma3 (arXiv 2604.01652) | `thinkncheck/thinkncheck-1b-gemma3-q4` (verify released/obtainable) | unavailable | unavailable | HF repo was not obtainable (404/401); left unavailable |

- The `--name` value must be copied verbatim from the table. Adapters load from
  `models/bakeoff/<CandidateSpec.name>/`; a mismatched name produces an honest
  `unavailable`, not a fallback.
- The git-tracked `CandidateSpec.revision` value is the source of truth for
  obtainable candidates. The table mirrors those pins so a future witness run
  can be reproduced without trusting a transient local cache.
- **ThinknCheck obtainability is verified HERE.** If no checkpoint is released
  (paper-only), record it `unavailable` — NOT a blocker; the other candidates run.
- The `--revision` MUST be a specific commit/tag (the helper refuses an empty
  revision). Record the printed `sha256` in the table above.
- The exact model API for each adapter (`_load` / `_raw_predict`) is verified here
  too; adjust the adapter body if a real API differs from the best-known form. The
  unit tests mock that boundary, so they stay green across such adjustments.

## ChatJudge baseline (server-backed, opt-in — NOT a download)

ChatJudge is the chat-LLM judge baseline. It takes **no default port** (a wrong port
could benchmark the wrong brain — on this box `:8082` serves `maez-vision`, `:8081`
serves `maez-judge`). A default run marks it `unavailable` ("refusing to guess a port").
To include it, construct it explicitly with the REAL judge endpoint + expected alias,
e.g. `ChatJudgeAdapter(base_url="http://127.0.0.1:8081", expected_alias="maez-judge")`;
at load it verifies `/v1/models` actually serves that alias (else `unavailable` with a
served-vs-expected reason), labels `model_id` as `chatjudge:<alias>@<base_url>`, and the
report records the actual `base_url` + `served_alias`. Verify the alias with
`curl -s http://127.0.0.1:8081/v1/models` before configuring.

## Reproducibility manifest (how revision/sha256 reach the report)

`fetch_one` writes `models/bakeoff/<name>/bakeoff_manifest.json` = `{repo_id, revision,
sha256}` (the manifest is excluded from the artifact hash, so re-downloads are stable).
`CandidateAdapter.__init__` reads that manifest at load and sets `self.revision` /
`self.sha256`, which the runner carries into per-candidate metadata and the report prints
(`model_id | revision | adapter_version | … | sha256`). So the report's `revision`/`sha256`
ARE the pinned download's — no hand-editing. A candidate with no manifest (e.g. ChatJudge,
or a not-yet-downloaded model) shows `revision=None` honestly.

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

The 2026-06-08 witness used an isolated runtime at `/tmp/maez-bakeoff-venv`
because the project venv intentionally did not carry `torch` / `transformers` /
`sentence-transformers`. It ran CPU-only:

```
CUDA_VISIBLE_DEVICES='' TOKENIZERS_PARALLELISM=false \
PYTHONPATH=/home/rohit/maez-wt-judge-witness \
/tmp/maez-bakeoff-venv/bin/python -B -m scripts.photo_judge_bakeoff \
    --label real-2026-06-08-r2 \
    --out-dir logs/photo_judge_bakeoff \
    --corpus tests/data/judge_eval_photo_contradiction_v1.jsonl
```

The report ranks the catch×latency frontier with per-threshold rows for score-based
candidates, a loud `MISSED MUST-CATCH` line for any missed anchor/numeric case, an
`errors` column, and a `RECOMMENDATION`. Latency is REPORTED, not gated — the owner
picks the winner + placement (inline / retry-only / post-hoc / memory-labeling) in
Lane 2b.
