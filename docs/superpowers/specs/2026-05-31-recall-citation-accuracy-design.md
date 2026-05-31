# Recall Citation Accuracy Slice — Design

**Date:** 2026-05-31
**Status:** Design approved (Rohit, 2026-05-31). Pre-registration for implementation. Spec first; no code until the plan is approved.
**Predecessors:** Slice 2 brain benchmark (built/merged, parts 1–7). The benchmark's definitive verdict on `qwen36-27b`: latency solved (~3s), answer content mostly right, but **citation accuracy unreliable (~23% miss)** with a **positional `[E1]` anchor** — it sometimes pulls the right fact but cites the wrong evidence label.

---

## 1. Why this exists

The benchmark proved the recall default-on blocker is no longer latency — it is **citation/provenance accuracy**: does Maez attribute each remembered fact to the *right* source. A wrong citation on a right fact is a small provenance lie, which is a covenant/honesty defect, not a nicety.

**Confirmed root cause (witnessed in code):** `core/routing/focused_cognition.py:_render_evidence_lines` renders each evidence item once, then appends `(most important, repeated) [E1] {text}` — it **always repeats `items[0]`**, verbatim, tagged "most important," and the budget counts it twice (~line 527). So whatever sits at `[E1]` is **double-privileged** (positional + salience). In `multi_year` collision samples, when the 2025 decoy landed at `[E1]`, the prompt was literally repeating the decoy as "most important" → qwen anchored on `[E1]` even when the answering fact came from `[E2]`. Benchmark pass rates (current qwen run, the baseline): `dated_hit` 9/10, `both_shaped` 8/10, `multi_year` 6/10.

The repetition was almost certainly a **salience aid against lost-in-the-middle** (keeping the brain from ignoring held evidence — the concern behind the focused-cognition-over-megaprompt work). So the fix must *replace*, not naively delete — and must be proven not to regress the brain's use of evidence.

## 2. Goal & non-goals

**Goal:** make qwen cite the exact evidence item a fact came from (kill the `[E1]` double-privilege) **without** regressing the answered-grounded rate.

**Non-goals (explicit):**
- **NOT** post-hoc citation repair — rewriting the model's citation after it misattributed would make Maez *look* honest about provenance when it wasn't. That is laundering; forbidden here. Fix the producer (input + task), not the output.
- **NOT** a deterministic citation verifier in this slice. If §3 fails to clear the bars, a verifier-as-**gate** (refuses/flags a misattribution, never silently rewrites it) is a *separate second slice*.
- **NOT** shorter answers, **NOT** a model swap, **NOT** hardware.
- **NOT** a live default-on flip.

## 3. The change (all in `core/routing/focused_cognition.py`, flag-gated)

A new rendering path `MAEZ_RECALL_CITATION_RENDER_V2`, **default-off**. When off, behavior is **byte-identical** to today (v1). When on:

1. **Remove the double-privilege.** No `(most important, repeated) [E1]` line; no budget double-count of `items[0]`.
2. **Position-neutral per-item headers.** Render each item once as a clearly-delimited card: `[E#]` · date/provenance · source-type · authority, then the text. Every card equally legible; the **date/provenance is surfaced** so the model can distinguish years (directly aids `multi_year`).
3. **Tightened synthesis instruction.** "Cite the exact `[E#]` your fact came from. If a fact came from `[E2]`, cite `[E2]`, not `[E1]`. Do not default to the first item." (Applied with the v2 path; v1 instruction unchanged when flag off.)

Per the measure-don't-assume decision: drop the repetition entirely, measure, and add a **non-positional** salience mechanism back *only if* the data shows a lost-in-the-middle regression (a later, measured follow-up — not pre-built here).

## 4. Flag discipline & the byte-identity guard (load-bearing)

`focused_cognition.py` is a **shared live organ** (reachable beyond the off-by-default triad path), so:
- `MAEZ_RECALL_CITATION_RENDER_V2` defaults **off**; production recall rendering is **byte-unchanged**.
- The benchmark runs with the flag **on** (set in the benchmark launcher env).
- **Required test — flag-off byte identity (Rohit's tightening):** with the flag unset/`0`, assert `_render_evidence_lines` output is **byte-identical** to the current v1 (golden-string test), **and** the prompt-budget behavior is unchanged (E1 still counted twice in the v1 path). The risk this guards is not "does v2 work" — it is "did we accidentally alter live v1 while adding v2." Pin it.

## 5. Verification — the brain benchmark, paired run

Re-run the brain benchmark on `qwen36-27b`. To control for shared-server / sampling variance, run **v1 (flag off) and v2 (flag on) back-to-back in the same session**; compare v2 to that session's v1 baseline AND to the pinned prior floors.

**Pass bars (pre-registered):**
- **`multi_year` improves materially** from the `6/10` baseline (the collision probe is the sharp test of the anchor fix).
- **`dated_hit` ≥ `9/10`** (no drop).
- **`both_shaped` ≥ `8/10`** (no drop).
- **Overall answered-grounded rate does not regress** vs the same-session v1 baseline (the lost-in-the-middle safety check — if dropping the repetition makes the brain ignore evidence, grounded-rate falls and we see it).
- **Any new false-absence or wrong-absence is a BLOCKER** (a regression in honest-decline behavior is unacceptable regardless of citation gains).

If the grounded-rate regresses → v2 fixed citation at the cost of evidence-use → do **not** ship; add a non-positional salience mechanism and re-measure (follow-up slice).

## 6. Covenant / honesty invariants

- **Producer-causality:** fix the input (un-biased evidence cards) and the task (cite-exact instruction), never the output ([[producer-causality-no-caller-score-laundering]]). No post-hoc citation rewrite.
- **Provenance is honesty:** right-fact-wrong-citation is a provenance lie; this slice treats citation accuracy as a covenant property, not polish.
- **Flag-off byte-identity:** the live organ is unchanged until measured + owner-flipped.
- **Measure before flip:** benchmark-proven (paired run, pre-registered bars) before any default-on consideration. The benchmark is producer-evidence; the owner decides.

## 7. Process

Serious slice (touches live cognition/recall) → Codex six-agent pre-code pass (non-decorative) + 7+3; Claude cross-verifies every diff + runs suites independently + fires the coverage panel; merge **flag-off**; then the owner-run paired benchmark. The recall default-on / 2b re-run remains gated on this passing **and** the separate S5 voice-continuity gate.

## 8. Sequenced after

A v2 that clears the bars → citation accuracy is no longer the blocker → recall default-on (the 2b re-run with the A7 gate) becomes reachable, still gated on S5 voice continuity + owner verdict. If v2 clears citation but regresses grounded-rate → the non-positional-salience follow-up. If v2 fails citation → the verifier-as-gate second slice.
