# Photo-Contradiction Judge Bakeoff — Witness Run

Date: 2026-06-08
Branch: `judge-bakeoff-witness-run`
Base: main `864e4fc`

## Boundary

Offline eval only. No daemon restart, no service start/stop, no `model.env`
change, no systemd change, no live URL flip. Models were downloaded into the
non-live `models/bakeoff/` cache and run CPU-only with `CUDA_VISIBLE_DEVICES=''`.

The project venv did not include the model runtime libraries, so the witness used
an isolated throwaway runtime at `/tmp/maez-bakeoff-venv`.

## Obtainability

Fetched and manifest-hashed:

- `hhem` — `vectara/hallucination_evaluation_model`
- `minicheck-roberta` — `lytang/MiniCheck-RoBERTa-Large`
- `minicheck-flan-t5` — `lytang/MiniCheck-Flan-T5-Large`
- `minicheck-deberta` — `lytang/MiniCheck-DeBERTa-v3-Large`
- `nli` — `MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli`
- `reranker` — `Qwen/Qwen3-Reranker-0.6B`

Unavailable:

- `thinkncheck` — `thinkncheck/thinkncheck-1b-gemma3-q4` was not obtainable
  from Hugging Face in this run, so it remained unavailable.

Compatibility repairs made before the final run:

- MiniCheck adapters now run through `transformers.pipeline`; the `minicheck`
  package was not available for Python 3.14.
- HHEM needed a small Transformers-5 compatibility shim for
  `all_tied_weights_keys`.

## Final Run

Report files (gitignored):

- `logs/photo_judge_bakeoff/real-2026-06-08-r2.md`
- `logs/photo_judge_bakeoff/real-2026-06-08-r2.json`

Headline frontier:

| candidate | catch | false-flag | p95 cpu latency | read |
|---|---:|---:|---:|---|
| `minicheck-deberta` | 1.0 | 0.5 | 0.1586s | catches everything, too eager |
| `minicheck-roberta` | 1.0 | 0.6667 | 0.0840s | catches everything, even more eager |
| `minicheck-flan-t5` | 1.0 | 1.0 | 0.2043s | catches everything by rejecting everything |
| `nli@0.3`..`nli@0.7` | 0.875 | 0.0 | 0.1579s | conservative; misses one non-must year case |
| `hhem@0.3`..`hhem@0.5` | 0.0 | 0.0 | 0.0315s | misses all must-catch cases |
| `hhem@0.6`..`hhem@0.7` | 1.0 | 1.0 | 0.0315s | catches by rejecting everything |
| `reranker@0.3`..`reranker@0.7` | 0.375 | 0.5 | 0.5235s | relevance baseline fails must-catch cases |
| `chatjudge-maez-judge` | 0.375 | 0.0 | 30.0304s | timed out on 10 cases; not viable inline |

Specific tradeoff:

- `nli` caught all must-catch cases, including the WWDC anchor and numeric size /
  price contradictions, and had zero false-flags.
- `nli` missed `photo_num_year_contradiction_004`: premise says the chart years
  are 2021-2024 and the tallest bar is 2024; hypothesis says revenue peaked in
  2019.
- `minicheck-deberta` caught that year case too, but false-flagged:
  `photo_grounded_chart_011`, `photo_uncertainty_blur_012`, and
  `photo_uncertainty_partial_013`.

## Recommendation For Lane 2b

Do not wire the harness's raw aggregate recommendation directly as an inline
blocker. It chose `minicheck-deberta` because catch is maximized first, but a
50% false-flag rate on this small control set is too aggressive for Maez's live
voice.

The safer first placement is:

- `nli` as the conservative inline/passive verifier candidate, because it catches
  the must-catch photo contradictions with zero false-flags and ~158 ms CPU p95.
- `minicheck-deberta` as a stricter retry-only or post-hoc audit candidate, not
  a hard inline veto, unless the corpus is expanded and its false-flag behavior
  improves.

This is not the final Lane 2b decision. It is the measured frontier the decision
should start from.
