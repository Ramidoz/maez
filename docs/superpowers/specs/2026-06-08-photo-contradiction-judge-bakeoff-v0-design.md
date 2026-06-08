# Photo-Contradiction Judge Bakeoff v0 — Design

**Date:** 2026-06-08 · **Lane:** Claude implements / Codex reviews · **Branch:** `photo-judge-bakeoff-v0` (from main `b4833e5`)

## Why

Lane 1 (Photo Honesty Receipt v0) ships a deterministic rail that catches
*didn't-cite-the-evidence* (`cited_ids != ["E1"]`). It deliberately does NOT catch
*cited-but-CONTRADICTS* — a reply that cites `[E1]` but says something the photo
analysis contradicts (the live WWDC2024-vs-screen-2026 hallucination). Lane 2 is that
complement.

**Invariant (banked [[feedback_verifier_swappable_receipt_invariant]]):** the honesty
receipt — an answer is trusted only if grounded — is the fixed contract; the
judge/verifier is the SWAPPABLE mechanism. Build the deterministic rail first (done),
then audition verifiers behind the same contract under a brutal catch+latency SLA.
Don't architect around a slow verifier.

**This slice is a MEASUREMENT REPORT, not a live gate.** It produces a ranked
catch×latency frontier over candidate verifiers on a stratified photo-contradiction
corpus. The owner picks the winner; a follow-on **Lane 2b** decides placement (inline /
retry-only / post-hoc / memory-labeling). No winner is baked into Maez here.

## What already exists (build ON, don't rebuild)

- `scripts/judge_bakeoff.py` — locked mechanical runner (VRAM probe + per-case eval +
  pass/fail decision rule + hard contract). Lane 2 does NOT mutate it.
- `scripts/judge_bench/` — already benchmarked 8 chat-LLM judges on a GENERAL grounding
  corpus (`tests/data/judge_eval_2026_05_05.jsonl`, 22 cases, **zero photo cases**).

The gap: no photo cited-but-contradicts cases anywhere, and the exotic
claim-verification candidates aren't on the box.

## Component 1 — Stratified photo-contradiction corpus

`tests/data/judge_eval_photo_contradiction_v1.jsonl`. ~12–18 cases, **stratified** to
cover distinct failure modes (not just a count). Each case schema:

```json
{
  "id": "photo_wwdc_year_contradiction_001",
  "stratum": "real_anchor",
  "premise": "local vision analysis text",
  "reply": "full Maez reply",
  "hypothesis": "The screenshot is about WWDC2024.",
  "expected": "contradicts",
  "must_catch": true,
  "source": "live_photo_witness_2026-06-08",
  "notes": "Real cited-but-contradicts class"
}
```

- **`stratum`** ∈ {`real_anchor`, `numeric_ocr`, `entity_title`, `grounded_control`,
  `uncertainty_control`} — an EXPLICIT label. The loader and the "all 5 strata present"
  test read this field; strata are NEVER inferred from `id`/`notes`.
- **`premise`** = the local vision analysis (the evidence, E1).
- **`reply`** = the full Maez reply (context; replies contain multiple claims).
- **`hypothesis`** = the SINGLE claim extracted from the reply, evaluated against the
  premise. Evaluating one claim avoids the blur of multi-claim replies. This is the
  load-bearing field — every candidate scores `(premise, hypothesis)`.
- **`expected`** ∈ {`grounded`, `contradicts`}.
- **`must_catch`** (bool) — see Component 3.

**Strata (each represented):**
1. **Real anchor** — the live WWDC2024 case (premise = screen's actual 2026 content;
   hypothesis = "the screenshot is about WWDC2024" → contradicts). `must_catch: true`,
   `source: live_photo_witness_2026-06-08`.
2. **Numeric / OCR contradictions** — year, price, model size, chart number (e.g.
   premise says "2.9 GB", hypothesis says "29 GB"). Several `must_catch: true`.
3. **Entity / title contradictions** — event name, product/model, page title.
4. **Grounded controls** — accurate replies that MUST pass (`expected: grounded`).
5. **Uncertainty controls** — "I can't tell from this" style replies that must NOT be
   over-flagged (`expected: grounded`; an honest hedge is not a contradiction).

Strata 4–5 are the false-flag guard: a verifier that flags everything is useless.

## Component 2 — Uniform candidate-adapter layer

A `predict(premise, hypothesis) -> Verdict(label, score, latency_s)` protocol so
non-chat verifiers sit beside chat-LLM judges. `label ∈ {grounded, contradicts}`
(plus `unavailable` if the candidate didn't load). Adapters:

- **`HHEMAdapter`** — Vectara HHEM-2.1-Open consistency score → threshold. Purpose-built;
  strongest a-priori fit. CPU.
- **`MiniCheckAdapter`** — MiniCheck small variant (RoBERTa-large / Flan-T5-large),
  `(document=premise, claim=hypothesis) -> supported 0/1`. CPU.
- **`ThinknCheckAdapter`** — ThinknCheck (4-bit 1B Gemma3, reasoning-driven claim
  verifier, arXiv 2604.01652). The reasoning chain may cost latency — the frontier
  exposes that. Obtainability verified in execution step 1; paper-only ⇒ noted, not a
  blocker.
- **`NLIAdapter`** — a plain NLI cross-encoder (e.g. DeBERTa-v3-NLI): entailment /
  contradiction / neutral. A guaranteed-obtainable entailment-shaped baseline so we're
  never left with zero NLI verifiers if ThinknCheck's checkpoint isn't released.
- **`RerankerAdapter`** — Qwen3-Reranker-0.6B. **BASELINE ONLY, caveated:** a reranker
  scores relevance, and a contradictory reply shares words with the premise, so it can
  call a contradiction "relevant." Reported, but not treated as a serious contradiction
  judge unless the bakeoff proves otherwise.
- **`ChatJudgeAdapter`** — wraps an existing chat-server judge (e.g. gemma-3-4b-cpu,
  already benchmarked 81%/1.2s) via a `(premise, hypothesis)→contradicts?` prompt, for
  apples-to-apples against the dedicated verifiers.

Adapters live in a flat sibling module `scripts/photo_judge_bakeoff_adapters.py` (matching
the flat `scripts/judge_bakeoff.py` convention; runner is `scripts/photo_judge_bakeoff.py`,
invoked via `python -m scripts.photo_judge_bakeoff`). Each adapter is independently
unit-testable with a mocked model call.

## Component 2b — Threshold protocol (un-riggable)

Several candidates emit a continuous score (HHEM consistency, reranker relevance, NLI
contradiction-probability) that needs a threshold to become a `grounded`/`contradicts`
label. Hand-picking thresholds in code would reduce the bakeoff to "which adapter got the
friendliest cutoff." So thresholds follow a fixed, visible protocol — never silently
tuned in code:

- **Published default where one exists** (e.g. HHEM's recommended cutoff; MiniCheck's 0.5;
  NLI argmax over entailment/neutral/contradiction needs no threshold). Use it verbatim;
  record the source.
- **Otherwise, sweep a small fixed grid** (e.g. `{0.3, 0.4, 0.5, 0.6, 0.7}`) and report
  the per-threshold frontier; the recommendation names the chosen operating point. The
  grid is fixed in the spec/config, identical for every score-based candidate — not
  per-candidate-tuned.
- **Binary/label candidates** (MiniCheck 0/1, ThinknCheck verdict, ChatJudge yes/no)
  carry no threshold; recorded as `threshold: null (label-native)`.
- **The report MUST print the threshold used for every candidate** (and, for swept ones,
  the full grid frontier), so the operating point is visible and reproducible. A
  candidate's catch-rate is meaningless without its threshold shown beside it.

## Component 3 — Sibling runner + frontier report (NOT a gate)

A **sibling** `scripts/photo_judge_bakeoff.py` that REUSES the hard contract and report
conventions of `scripts/judge_bakeoff.py` but **does NOT inherit its pass/fail rule**.
Hard contract preserved verbatim, with `judge_bakeoff.py`'s "does not download models"
clause kept explicit: the runner does NOT flip `MAEZ_JUDGE_BASE_URL` for the live daemon,
does NOT edit `model.env`, does NOT start/stop/restart any systemd unit, and **does NOT
download anything** — it consumes artifacts already present under `models/bakeoff/`. An
absent artifact is recorded `unavailable`, never fetched. (Downloads live entirely in the
separate Component 4 helper.)

For each candidate × corpus → per-case `(label, latency_s)`; aggregate to:
- **catch-rate** on `contradicts` cases, **false-flag-rate** on `grounded` cases, plus a
  **per-stratum breakdown** (catch/false-flag for each of the 5 strata — cheap now that
  `stratum` is explicit, and it reveals e.g. a verifier strong on numbers but blind to
  titles),
- **p50 / p95 / mean latency**,
- **must_catch report:** if a candidate misses ANY `must_catch` case, the report calls
  it out LOUDLY (a dedicated `MISSED MUST-CATCH: <ids>` line) even if the candidate's
  aggregate looks decent. This is the frontier's conscience — a high average doesn't
  excuse missing the WWDC case or a numeric contradiction.
- **per-candidate metadata** (recorded for every candidate, every run): `model_id`,
  `revision`, `sha256`, `adapter_version`, `threshold` (or `null (label-native)`),
  `device` (cpu/gpu), and `unavailable_reason` if it didn't run. Reproducibility is the
  point — a number you can't reproduce isn't evidence.
- a ranked **frontier** (catch × latency) + a written recommendation.

**Zero-candidates-runnable case:** if every candidate is `unavailable` (nothing fetched
yet, all loads failed), the runner still emits an honest report — the metadata table with
each `unavailable_reason`, an empty frontier, and an explicit
`RECOMMENDATION: none — 0/N candidates runnable; see unavailable_reason` — never a crash,
never an empty/implied recommendation.

Output: `logs/photo_judge_bakeoff/<label>.md` + `.json` (gitignored under `logs/*`).
No `VERDICT: PASS/REJECT` on latency — latency is reported; the owner decides the bar.

## Component 4 — Candidate obtain + smoke-test (SEPARATE helper, never the runner)

Downloads live entirely OUTSIDE the runner, in a standalone helper
`scripts/photo_judge_bakeoff_fetch.py` (+ a `docs/handoffs/…-download-runbook.md`). This
is the ONLY component that touches the network; `scripts/photo_judge_bakeoff.py` never
imports or invokes it and never fetches. Clean separation: **fetch = network + pinning;
runner = pure measurement over already-present artifacts.**

**Download policy (owner-set):** agent-managed HuggingFace downloads are permitted ONLY
if they are (a) **pinned** to a specific revision, (b) **hash-recorded** (sha256 of each
artifact captured in the runbook AND in the per-candidate report metadata), (c) placed in
a **non-live model cache** `models/bakeoff/` — never the live `models/llamacpp/` paths the
daemon reads, and (d) **never** started as a service or wired into env/systemd. The fetch
helper smoke-tests each artifact (one-shot load + a single predict) and records the
result. Live wiring stays the owner's. (Strictest breath split: the runbook is the
artifact and the owner runs the downloads; default per owner: agent may download bakeoff
artifacts.) A candidate whose artifact is absent or fails to load is recorded
`unavailable` by the runner and skipped — never blocks the others.

## Data flow

corpus case → for each candidate: `adapter.predict(premise, hypothesis)` →
`(label, score, latency_s)` → aggregate (catch-rate, false-flag, latency percentiles,
must_catch check) → ranked frontier report (md + json).

## Error handling

- A candidate that fails to load/run → `Verdict(label="unavailable")`, skipped; never a
  crash, never blocks other candidates.
- Per-case adapter exception → recorded as an error for that case (not a global abort).
- Reuses the existing harness's no-live-changes contract — nothing here can touch the
  live daemon, judge service, or `model.env`.

## Testing (TDD, unittest)

1. **Corpus loader** — schema validation (every case has `stratum`/`premise`/`reply`/
   `hypothesis`/`expected`; `stratum ∈` the 5-value enum; `expected ∈ {grounded,
   contradicts}`; `must_catch` bool); asserts the WWDC2024 anchor is present with
   `must_catch: true`; asserts **all 5 strata present read from the `stratum` field**
   (never inferred from `id`/`notes`).
2. **Each adapter** — mock the model call → correct `(premise, hypothesis)` mapping,
   correct label mapping (e.g. HHEM low-score → contradicts), **threshold applied per the
   protocol** (a score either side of the threshold maps to the right label), latency
   captured, `unavailable` path on a load failure. No real model in unit tests.
3. **Aggregator** — catch-rate / false-flag-rate / per-stratum breakdown / percentile
   math on a fixed fixture; **must_catch loud-callout fires when a must_catch case is
   missed** (the conscience test); **threshold + sha256 + metadata present in the report
   for every candidate**; frontier ranking order; **zero-candidates-runnable → honest
   report** (metadata table + `RECOMMENDATION: none`, no crash).
4. **Hard-contract guard** — structural test that `photo_judge_bakeoff.py` (the runner)
   contains no `model.env` write, no `systemctl`, no live-`MAEZ_JUDGE_BASE_URL` mutation,
   and **no network/download** (no `huggingface_hub` / `requests`-fetch / import of the
   fetch helper) — downloads live only in `photo_judge_bakeoff_fetch.py`.

Real model runs are an execution + witness step (downloads + a real bakeoff run
producing the report), not unit tests.

## Scope — explicitly NOT in v0 (all Lane 2b)

Wiring any winner into the live photo-audit path; the inline / retry-only / post-hoc /
memory-labeling placement decision; any `model.env` / service / systemd change; any live
`MAEZ_JUDGE_*` flip. v0 ends at a ranked frontier report + recommendation.

## Predicted effect

None on Maez's runtime behavior — this slice adds an offline corpus + a sibling eval
script + unit tests. It touches no daemon/recall/routing/memory/safety/body/ingestion
path. The behavioral question it informs (which verifier catches cited-but-contradicts)
is answered by the report, acted on only in Lane 2b. (Per the commit convention, the
implementation commits are eval/test/docs — no `## Predicted effect` block required;
this note records the deliberate no-runtime-effect.)

## Lane

Claude builds, Codex reviews (lanes as the ledger slice). Live daemon untouched; ledger
stays off (irrelevant here).
