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
  "premise": "local vision analysis text",
  "reply": "full Maez reply",
  "hypothesis": "The screenshot is about WWDC2024.",
  "expected": "contradicts",
  "must_catch": true,
  "source": "live_photo_witness_2026-06-08",
  "notes": "Real cited-but-contradicts class"
}
```

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

## Component 3 — Sibling runner + frontier report (NOT a gate)

A **sibling** `scripts/photo_judge_bakeoff.py` that REUSES the hard contract and report
conventions of `scripts/judge_bakeoff.py` but **does NOT inherit its pass/fail rule**.
Hard contract preserved verbatim: does NOT flip `MAEZ_JUDGE_BASE_URL` for the live
daemon, does NOT edit `model.env`, does NOT start/stop/restart any systemd unit.

For each candidate × corpus → per-case `(label, latency_s)`; aggregate to:
- **catch-rate** on `contradicts` cases, **false-flag-rate** on `grounded` cases,
- **p50 / p95 / mean latency**,
- **must_catch report:** if a candidate misses ANY `must_catch` case, the report calls
  it out LOUDLY (a dedicated `MISSED MUST-CATCH: <ids>` line) even if the candidate's
  aggregate looks decent. This is the frontier's conscience — a high average doesn't
  excuse missing the WWDC case or a numeric contradiction.
- a ranked **frontier** (catch × latency) + a written recommendation.

Output: `logs/photo_judge_bakeoff/<label>.md` + `.json` (gitignored under `logs/*`).
No `VERDICT: PASS/REJECT` on latency — latency is reported; the owner decides the bar.

## Component 4 — Candidate obtain + smoke-test (execution step 1, verify-first)

Before any adapter is trusted, each candidate is obtained + smoke-tested on the box.
**Download policy (owner-set):** agent-managed HuggingFace downloads are permitted ONLY
if they are (a) **pinned** to a specific revision, (b) **hash-recorded** (sha256 of the
artifact captured in the runbook), (c) placed in a **non-live model cache** (e.g.
`models/bakeoff/` — never the live `models/llamacpp/` paths the daemon reads), and
(d) **never** started as a service or wired into env/systemd. The plan produces a
`docs/handoffs/…-download-runbook.md` recording each pin + hash. Live wiring stays the
owner's. (If the owner prefers the strictest breath split, the runbook is the artifact
and the owner runs the downloads; default per owner: agent may download bakeoff
artifacts.) A candidate that won't obtain/run is recorded `unavailable` and skipped —
never blocks the others.

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

1. **Corpus loader** — schema validation (every case has `premise`/`reply`/`hypothesis`/
   `expected`; `expected ∈ {grounded, contradicts}`; `must_catch` bool); asserts the
   WWDC2024 anchor case is present with `must_catch: true`; asserts all 5 strata present.
2. **Each adapter** — mock the model call → correct `(premise, hypothesis)` mapping,
   correct label mapping (e.g. HHEM low-score → contradicts), latency captured,
   `unavailable` path on a load failure. No real model in unit tests.
3. **Aggregator** — catch-rate / false-flag-rate / percentile math on a fixed fixture;
   **must_catch loud-callout fires when a must_catch case is missed** (the conscience
   test); frontier ranking order.
4. **Hard-contract guard** — structural test that `photo_judge_bakeoff.py` contains no
   `model.env` write, no `systemctl`, no live-`MAEZ_JUDGE_BASE_URL` mutation (mirrors
   the judge_bakeoff contract).

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
