# Codex Handoff — Agnostic Local Judge Registry v0

Branch: `agnostic-local-judge-registry-v0`

## What Changed

- Replaced the hardcoded photo-judge adapter-class default with a data-driven local candidate registry.
- Fixed MiniCheck to public `lytang/*` repos and added RoBERTa / Flan-T5 / DeBERTa variants.
- Kept the bakeoff local/open only. ChatJudge specs are loopback-only and still verify served aliases before use.
- Runner defaults to `build_candidates()` from the registry.
- Downloaded-model candidates fail fast as `unavailable` when their `models/bakeoff/<name>/` artifact directory is absent, avoiding heavyweight imports during no-download smoke runs.

## Review Anchors

1. Registry is data, not hardcoded adapter classes.
2. MiniCheck uses only `lytang/*`, never `bespokelabs/*`.
3. ChatJudge specs cannot point outside loopback.
4. Runner still has no network/download/systemd/model.env behavior.
5. Report fingerprint behavior from Lane 2 remains intact.
6. Default no-download smoke honestly reports unavailable candidates instead of crashing or importing model libraries.

## Verification

- PASS — `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_photo_judge_bakeoff`
  - `Ran 45 tests ... OK`
- PASS — `PYTHONPATH=/home/rohit/maez-wt-judge-registry /home/rohit/maez/.venv/bin/python -B -m scripts.photo_judge_bakeoff --label registry-smoke --corpus <empty temp file> --out-dir /tmp/maez-photo-judge-registry-smoke`
  - `RECOMMENDATION: none — 0/8 candidates runnable; see unavailable_reason.`
- AMBIENT FLOOR RED — `/home/rohit/maez/.venv/bin/python -B -m unittest discover -s tests -p 'test_*.py'`
  - `Ran 6204 tests ... FAILED (failures=16, errors=35, skipped=3)`
  - No failures in `tests.test_photo_judge_bakeoff`; visible failures/errors are outside this slice (presence asset, web-interface secret requirement, temporal recall timezone/helper expectations, shim alias, live judge timeouts, and other ambient buckets).

## Notes For Review

- Running the real 14-case corpus with a local chatjudge candidate is the owner-greenlit witness run, not the cheap smoke. If `maez-judge` is live, that run may perform real CPU judge calls.
- The birth-readiness covenant-review backlog is tracked in the implementation plan, not treated as a blocker for this local-only eval refactor.
