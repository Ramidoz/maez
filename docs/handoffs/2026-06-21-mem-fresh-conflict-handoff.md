# Handoff — Trusted Memory ↔ Fresh Evidence Conflict SENSE (Shadow Detector v0), Thread B Slice 1

**Date:** 2026-06-21. **Branch:** `mem-fresh-conflict-sense` (off `main`). **Status:** built, both review stages PASS (Claude two-stage per task), 19/19 module+seam tests green, 60/60 protected regression green. **Awaiting:** Codex cross-lane review → owner `merge it`. NOT merged, NOT restarted, NOT witnessed live.

## What this is
The deepest honesty wound of the content-honesty arc ([[project_content_honesty_arc]]): trusted-grade memory beat fresh evidence in synthesis (the Anthropic-fabrication case). Thread C already excluded Maez's *own unverified* replies (`self_web_claim`). Thread B is the general case — genuinely trusted memory vs fresh evidence disagreeing on substance. **Slice 1 (this) is the SHADOW DETECTOR only**: it senses the clash and logs a redacted receipt. It changes NO reply. Domain-routing action (world→fresh-governs+name; owner→ask) is **Slice 2, out of scope**.

## Commit trail
- `b05ee57` Task 0 — STOP gates CLEARED (proof: `docs/proof/2026-06-21-mem-fresh-conflict-task0.md`).
- `0d17842` redacted receipt struct + shadow flag.
- `4cdd9c7` selectors — trusted-memory (fail-closed) + fresh + memory-claim extract.
- `cc33c4f` orchestration — pair/predict/redacted-receipt/fail-safe.
- `af15032` review fix — honest `pair_count` (pairs-examined, not budget cap) + split `non_decisive` from `verifier_unavailable`.
- `c808f7b` redaction trip-wire test (sentinel strings never reach the receipt).
- `4190134` daemon shadow seam (behavior commit, `## Predicted effect`).

## The load-bearing design choices (Codex: verify these held)
1. **CONTRADICTION, not absence-of-support.** The detector uses `LocalNLIContradictionVerifier` (NLI; `label=="contradicts"` iff P(contradiction)>0.5). **MiniCheck (entailment-support) is NOT wired** — "unsupported ≠ contradicted." Task 0b measured precision **1.0 / zero false-positives** on a labeled set incl. thin/irrelevant/partial fresh sources (they scored `grounded` 0.86–0.999). A thin fresh source cannot make Maez doubt a true memory.
2. **Trusted-only pairing, EXACT + fail-closed.** `trusted_memory_items`: qualifies IFF `origin_trust ∈ {"lived","covenant"}` AND `origin_provenance != "self_web_claim"`. `None`/unknown trust → EXCLUDED. (Task 0a proved these fields ARE populated at the live seam via the structured-recall path — live store: 40 covenant + 42 lived.)
3. **Redacted receipt — content-light by CONSTRUCTION.** `MemoryFreshConflictReceipt` has NO text-bearing field; it stores `_sha256` digests of the claim/fresh text, ids/labels/verdict/confidence/verifier@rev/reason_code/counts only. The photo-contradiction `ContradictionReceipt` (which carries text in `claim_details[].text`/`sense_note`) is **NOT reused** — only the verifier *shape* is. Task 4 asserts sentinel text never appears in the receipt.
4. **Fail-safe toward the memory.** Only an explicit `"contradicts"` → `verdict="contradiction"`. Verifier exception / `"unavailable"` / any non-decisive label → `"ambiguous"` (never accuse). No fresh+trusted pair → receipt is `None`.
5. **Shadow-only, pure observer.** Flag `MAEZ_MEM_FRESH_CONFLICT_SENSE` default-off = byte-identical. The seam call (`daemon/maez_daemon.py`, immediately after `_run_support_scope`, guarded `if _focused_working_set is not None`) discards its return value and never touches `reply`. Helper swallows all exceptions.

## Codex cross-lane anchors (please verify independently)
- (a) The seam call does NOT mutate `reply`/`_gate_receipt` (it's a bare expression statement after the support-scope assignment).
- (b) Flag-off path returns before any verifier import/instantiation (byte-identical).
- (c) `_sha256` produces a 64-hex digest; no raw memory/fresh text appears in any logged field.
- (d) Fail-safe: confirm no path other than `label=="contradicts"` yields `verdict="contradiction"`.
- (e) The trusted predicate cannot let `None`/unknown/`self_web_claim` through.
- (f) The NLI verifier default artifact path resolves in production (main checkout `/home/rohit/maez/models/bakeoff/nli`); the worktree does NOT vendor weights, so seam tests MOCK the verifier (they never load the model).

## Notes for later (non-blocking, from code review)
- The error-branch log in `_run_mem_fresh_conflict_sense` logs only `type(exc).__name__`; consider `exc_info=True` at DEBUG for cheaper live root-causing.
- `test_sense_is_called_at_the_focused_seam` is a module-level presence tripwire (catches deletion, not mis-placement); seam adjacency is spec-confirmed in the diff. Could be tightened.

## Owner-breath (after both-lanes PASS + your `merge it`)
1. Merge `mem-fresh-conflict-sense` into `main`, prune worktree + branch.
2. Set `MAEZ_MEM_FRESH_CONFLICT_SENSE=1` in `~/.config/maez/model.env`; restart `maez`.
3. Witness: live a turn that recalls a TRUSTED fact (lived/covenant) AND pulls fresh/web evidence that CLASHES → expect a `mem_fresh_conflict_sense ... verdict=contradiction` log line, **and the reply is unchanged** (shadow). Then a turn with a thin/irrelevant fresh source → expect NO `contradiction` (verdict `none`/`ambiguous`). This proves the detector "has eyes" before Slice 2 ever gives it hands. No autonomous check — paste the receipt.
