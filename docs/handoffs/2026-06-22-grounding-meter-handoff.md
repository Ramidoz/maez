# Handoff — Grounding Meter (reply-relative), Coherence Slice 1

**Date:** 2026-06-22. **Branch:** `grounding-meter-slice1` (off `main` @ `00408af`). **Status:** built, all tasks two-stage-reviewed (Claude spec+quality per task), **145 tests green** (slice + recall/focused regression), ruff clean. **Awaiting:** Codex cross-lane → owner `merge it`. NOT merged/restarted/witnessed.

## What this is
Slice 1 of the coherence→north-star roadmap ([docs/coherence-northstar-roadmap-2026-06-21.md](../coherence-northstar-roadmap-2026-06-21.md)): the **instrument** that must land first so slices 2 (recall floor) and 3 (live-thread anchor) can be witnessed honestly. It adds a **reply-relative** grounding meter; it is **measurement-only — zero behavior change**.

## The fix
`check_groundedness` computed `citation_coverage = matched/valid_labels` (fraction of the 16-item working SET cited) — which reads `0.125` on the symptom turn and conflates ungroundedness with denominator size. We ADD `reply_grounding = grounded_sentences/total_sentences` (a reply sentence is grounded iff it carries a valid `[E#]`). The keystone test proves the divergence: a 16-item set with a 2-sentence both-cited reply now reads `reply_grounding=1.0` while `citation_coverage` stays `2/16`.

## Commit trail
- `2d48f77` Task 0 — constructor inventory (defaults proven safe: 16 `GroundednessVerdict` + 6 `RecallOutcome`, all keyword or ≤3-positional).
- `c1f4695` + `6c9728e` — `reply_grounding` in `check_groundedness` + defaulted `GroundednessVerdict` fields; v0 splitter docstring + no-punctuation test.
- `f0c5ffe` + `3d00681` — focused store: 3 numeric columns via PRAGMA-guarded migration; verdict=None→NULL test.
- `95201f8` + `579fc38` — `RecallOutcome.reply_grounding` + daemon threading + `_log_recall_outcome` (the live witness mouth).

## The two pipes (both wired — verify)
1. **Focused store** `focused_cognition_runs`: all **three** numbers (`reply_grounding` REAL, `grounded_sentences` INTEGER, `total_sentences` INTEGER), idempotent PRAGMA migration, numbers-only.
2. **`RecallOutcome` record + `_log_recall_outcome`**: the **rate only** (`reply_grounding`), threaded `_focused_verdict → _rk_reply_grounding → RecallOutcome(...) → log`. `schema_version` stays `recall_outcome.v2` (additive optional field).

## Invariants held
- `citation_coverage` formula UNCHANGED; `verdict.verdict` enum UNCHANGED; `unmatched` UNCHANGED.
- **No flag, no behavior gate** — nothing reads `reply_grounding` to alter/caveat/fallback a reply (grep confirms only assignment/log/record uses).
- **Content-light** — reply text NEVER persisted in store, record, or log (only numbers). A test asserts the reply word doesn't appear in any stored row.
- **No constructor break** — new `GroundednessVerdict` fields + `RecallOutcome.reply_grounding` all defaulted (Task-0 proven).

## Codex cross-lane anchors (verify independently)
- (a) The 3 `GroundednessVerdict` fields + `RecallOutcome.reply_grounding` are defaulted; no constructor (prod or test) breaks.
- (b) BOTH pipes carry it: store = all 3 numbers, record/log = the rate. Neither pipe left blind.
- (c) NO reply text persisted anywhere (store/record/log are numbers-only).
- (d) `citation_coverage` math + `verdict.verdict` untouched; the only metric semantics added are the new fields.
- (e) Migration idempotent (PRAGMA column-check, not exception-swallow); old rows default NULL.
- (f) Zero behavior change — `reply_grounding` is never read to branch/gate/alter a reply.
- (g) `_log_recall_outcome` format `%s` count == arg count (18) after the addition.

## Note for context (not this slice)
`tests/test_memory_integrity_invariant` has **2 pre-existing failures** (soul-prompt string assertions about `web_search.py runs inline`) that exist identically on `main` — NOT introduced here. Worth a separate look sometime, unrelated to the meter.

## Owner-breath (after both-lanes PASS + your `merge it`)
1. Merge `grounding-meter-slice1` into `main`, prune worktree + branch.
2. Restart `maez` (no flag to set — the meter is always-on instrument).
3. Witness: live a few focused turns; `journalctl --user -u maez | grep recall_outcome` (or `logs/maez.log`) now shows `reply_grounding=` alongside `citation_coverage=`. On a diary-recite/casual turn it should read **low** (expected — self-expression isn't claims); on a substantive turn it reads higher. **Record today's baseline** (a few numbers) — that's the ruler we'll watch rise when slices 2+3 land. Read it segmented by `turn_kind`. No autonomous check.
