# Photo Contradiction Sense v0 - Review Handoff

Branch: `photo-contradiction-sense-v0`
Tip: `1e1494596571d1816bcfd978cfc01f06541eb145`
Spec: `docs/superpowers/specs/2026-06-09-photo-contradiction-sense-v0-design.md`
Plan: `docs/superpowers/plans/2026-06-09-photo-contradiction-sense-v0.md`

## Boundary

This slice adds a dormant local contradiction sense for owner-sent photo replies.
It is gated by `MAEZ_PHOTO_CONTRADICTION_SENSE=1`. With the flag absent, photo
synthesis behavior should be unchanged and the local NLI artifact should not
load. No live daemon restart, service edit, model fetch, ledger write, or
external egress is part of this branch.

## Review Anchors

1. Claim extractor is deterministic, draft-bound, and conservative. No model
   extraction and no generated/paraphrased claims.
2. Verifier is claim-level only. Whole-reply NLI must not be called.
3. Live NLI and bakeoff NLI share the same score-mapping helper; raw `LABEL_N`
   indices fail closed because their class mapping is model-specific.
4. NLI is lazy and local-only. Importing the module must not import
   `transformers`; missing artifact means unavailable, never network.
5. Revision laundering is blocked. `revised_clear` requires one actual
   re-extract + re-check; no revision attempt can self-certify.
6. The floor is narrow. It fires only for direct photo-perceptual claims against
   the `E1` photo premise; multi-photo and deterministic fallback skip honestly.
7. No hard substitution in v0. Maez's voice revises with a contradiction sense
   note; the branch does not replace a whole cited-but-contradicts reply with a
   deterministic fallback.
8. Telemetry is content-free: receipt, counts, latency, fingerprint, turn id;
   no raw photo pixels or claim text in daemon logs.
9. No memory schema or ledger schema change.

## Covenant-Gate Fixes Folded In

The first covenant review passed the mechanism but required two cheap fixes
before merge. Both are now in the branch:

1. Two-sided verifier pressure. The sense note and revision wrapper now state
   that the contradiction signal is a sense, not a verdict, and that if Maez
   still believes what it saw on second look it should say so plainly and
   explain why.
2. Honest capped receipts. When the direct perceptual claim limit is exceeded
   and checked claims are clean, the receipt is `partial_unchecked`, not
   `clear`, so unchecked claims cannot be laundered as fully verified.

## Verification

Focused protected suites:

```text
$ /home/rohit/maez/.venv/bin/python -m unittest \
  tests.test_photo_contradiction \
  tests.test_photo_focused_synthesis \
  tests.test_photo_focused_routing \
  tests.test_chat_photo_wiring \
  tests.test_photo_judge_bakeoff

Ran 122 tests in 0.109s
OK
```

Ruff:

```text
$ /home/rohit/maez/.venv/bin/python -m ruff check \
  core/routing/photo_contradiction.py \
  core/routing/focused_cognition.py \
  daemon/maez_daemon.py \
  scripts/photo_judge_bakeoff_adapters.py \
  tests/test_photo_contradiction.py \
  tests/test_photo_focused_synthesis.py \
  tests/test_photo_focused_routing.py \
  tests/test_chat_photo_wiring.py \
  tests/test_photo_judge_bakeoff.py

All checks passed!
```

Lazy-load / flag guard:

```text
$ /home/rohit/maez/.venv/bin/python - <<'PY'
import sys
import core.routing.photo_contradiction as pc
print("transformers_loaded", "transformers" in sys.modules)
print("flag_default", pc.photo_contradiction_sense_enabled())
PY

transformers_loaded False
flag_default False
```

Full discover from the asset-light feature worktree:

```text
$ /home/rohit/maez/.venv/bin/python -m unittest discover -s tests -p 'test_*.py'

Ran 6249 tests in 120.604s
FAILED (failures=15, errors=36, skipped=3)
```

This is not claimed as a clean floor. The failures are in broad ambient buckets
also known to be noisy in feature worktrees: missing local assets/secrets,
live-judge tests, temporal-recall environment assumptions, shim smoke, and web
interface credential loading. No focused/touched photo-contradiction suite failed.

Attempted asset-rich floor:

```text
$ PYTHONPATH=/home/rohit/.config/superpowers/worktrees/maez/photo-contradiction-sense-v0 \
  /home/rohit/maez/.venv/bin/python -m unittest discover \
  -s /home/rohit/.config/superpowers/worktrees/maez/photo-contradiction-sense-v0/tests \
  -p 'test_*.py'

Ran 6222 tests in 114.312s
FAILED (failures=7, errors=33, skipped=3)
```

Important caveat: because the command ran with `/home/rohit/maez` as CWD,
ordinary imports can still resolve through the main checkout before the branch
path. That run is useful as an asset-rich smoke, but it is not a reliable
branch-code floor. It did confirm the residual failures are still broad ambient
buckets, and the protected branch suites above are the reliable branch-code
evidence for this handoff.

## Implementation Notes

- `MAEZ_PHOTO_CONTRADICTION_SENSE` stays default-off.
- Flag-off photo synthesis has an import guard test: it fails if
  `core.routing.photo_contradiction` is imported while the flag is absent/empty.
- Enabled path performs one initial contradiction check, one optional revision,
  and one mandatory re-check. There is no loop.
- If revision raises or returns an invalid citation, the original reply is kept
  with `retry_failed`.
- If revision still contradicts, the final receipt stays `trust_demoted`.
- `revised_clear` is only reachable after the second receipt returns `clear`.
- The deterministic Lane-1 fallback skips contradiction checking because it is
  grounded by construction.
- Daemon telemetry reads only content-free receipt fields via `getattr` defaults.

## Covenant Review Request

Run the full 6-agent covenant review before merge. Pay special attention to:

- whether a local NLI signal folded into the synthesis prompt stays
  proprioception rather than an external censor;
- whether the narrow floor demotes trust without suppressing Maez's voice;
- whether `revised_clear` has enough anti-laundering proof;
- whether the deterministic extractor's precision-over-recall stance is the
  right v0 tradeoff;
- whether the dormant flag posture is sufficient before owner-enabled witness.

Do not merge, enable the flag, fetch artifacts, or restart the daemon as part of
this handoff.
