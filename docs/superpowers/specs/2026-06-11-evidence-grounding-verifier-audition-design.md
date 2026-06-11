# Evidence-Grounding Verifier Audition — v0 Design

**Date:** 2026-06-11
**Status:** spec for owner review
**Lane:** Claude builds (offline harness + corpus); **corpus labels get an independent review (Codex or owner) — a hard gate before the meaningful report runs.**
**Parents:** the live `grounding_judge.py` (LLM **overclaim** auditor — consumes `signals_present`/`signals_absent`/`self_history`/`tool_results`, **NOT `claimable`**; verified in code 2026-06-11, `grounding_judge.py:642` + the prompt at `:462`); `envelope_builder.py:132` (renders `claimable` into the brain's *generation* context — but nothing audits it for entailment); `envelope_schema.py` (the slots — both rails exist in the data model, but only the overclaim rail is judged today); `feedback_verifier_swappable_receipt_invariant` (audition faster verifiers behind the same contract); `feedback_judge_agnostic_report_decides` (the report picks the winner); `scripts/judge_bench/` (the harness template + the overclaim test_set, which stays the LLM judge's).

## Why
Maez's honesty receipt — *an answer is trusted only if grounded* — runs through two distinct rails, and `envelope_schema.py` already encodes both:
- **Overclaim / self-claim** (`forbidden` / `self_history`): "did Maez claim a capability/action/utterance it couldn't substantiate?" — a *reasoning* task. Stays with the LLM judge + deterministic rails (the existing 21-case `judge_bench` set; the 4B won it at 90.5%).
- **Evidence-grounding** (`claimable`): "does this claim follow from the available evidence?" — an *entailment* task. **This check is currently ABSENT** (audition finding, verified in code): `claimable` evidence is rendered into the brain's *generation* context (`envelope_builder.py`) but **no judge audits it for entailment** — `grounding_judge.py` audits only the overclaim rail. So this audition finds the verifier to *fill a gap*, not to replace an incumbent.

This audition asks one concrete question: **can a small specialized verifier (HHEM / MiniCheck, CPU, ~0 GPU VRAM) perform the claimable-entailment support check** — `(evidence, claim) → SUPPORTED/UNSUPPORTED` — measured not on average performance but on an obstacle course of Maez's *dangerous* grounding failures, against a purpose-built **4B-entailment-adapter** LLM yardstick (there is no existing incumbent for this check). A winning verifier becomes a *new* layer above the deterministic citation floor (wired in by a follow-on slice). If it wins, it's a triple win: better catch on the failure modes, lower latency, and ~0 GPU VRAM vs the 4B's ~1.1GB.

## Scope boundary (load-bearing)
The candidate verifiers answer **entailment only**: `(evidence, claim) → does the claim follow from the evidence?`. They are **not** the grounding judge. Everything else stays exactly where it is and is **out of scope for this corpus**:
- The deterministic citation rail (`cited=0 ⇒ not grounded`) — "did Maez cite `[E1]`?" is the rail's job, not the verifier's. **No-citation cases are excluded** (they'd blur the entailment scorecard).
- The `forbidden` / `self_history` (overclaim) rail — the LLM judge's.
- v0 changes **nothing live** — it produces a scorecard. No daemon/service/flag change.

## Deliverable 1 — the corpus
`scripts/grounding_bench/corpus.json`, ~24–30 cases. Each row:
```json
{
  "id": "stale-3",
  "mode": "stale_over_current",
  "source": "synthetic",                       // "real-longmemeval" | "synthetic"
  "evidence_kind": "stale_vs_current",         // claimable_present | claimable_absent | stale_vs_current
  "evidence": "...the claimable evidence text...",
  "claim": "<a SINGLE claim — the unit of judgment>",
  "expected": "UNSUPPORTED",                   // SUPPORTED | UNSUPPORTED | ABSTAIN_EXPECTED
  "strict_rule": false,                        // true only for retained multi-claim answers
  "rationale": "Claim follows the superseded value; the current evidence says otherwise."
}
```

**Unit of judgment = a single claim.** Multi-claim answers either (a) split into one subclaim row each, or (b) are kept whole with `strict_rule: true` meaning "UNSUPPORTED if any material subclaim is unsupported" — to test the realistic mixed-answer case verifiers struggle with. A few `strict_rule` rows are included on purpose; the default is single-claim.

**`evidence_kind` is explicit**, never inferred from an empty string — the abstain precondition keys on `claimable_absent`.

**Taxonomy-balanced** (your mix; balanced by *failure mode*, not natural frequency):
| mode | expected | n | evidence_kind |
|---|---|---|---|
| grounded positive | SUPPORTED | 6–8 | claimable_present |
| cited-but-unsupported | UNSUPPORTED | 4–5 | claimable_present |
| fabricated / false-specific (WWDC-style) | UNSUPPORTED | 4–5 | claimable_present |
| stale-over-current | UNSUPPORTED | 4–5 | stale_vs_current |
| no-evidence (abstain probe) | ABSTAIN_EXPECTED | 3–4 | claimable_absent |
| multi-claim (split or strict_rule) | mixed | a few | claimable_present |

**Real spine:** pull `evidence` from `longmemeval_judge30` `surfaced` wherever it fits a mode; everything else is `source: synthetic` and flagged. **Hand-labeled for grounding, not correctness** (a factually-correct answer can be unsupported by *this* evidence, and vice-versa). Every row carries a `rationale`.

**Label-review gate (HARD):** before the report runs, an independent reviewer (Codex or owner) reads each case's `(evidence, claim, expected, rationale)` and confirms the label. The benchmark is only as honest as the labels; a single mislabeled case silently corrupts the scorecard.

## Deliverable 2 — the harness
`scripts/grounding_bench/bench_grounding.py`, mirroring `scripts/judge_bench/bench.py`.
- **Abstain precondition:** `if evidence_kind == "claimable_absent": return ABSTAIN` — **no model is called.** Scored correct iff `expected == ABSTAIN_EXPECTED`. This is "no document → abstain" made mechanical.
- **Candidates (all on the identical corpus):**
  - **HHEM-2.1-Open** (`vectara/hallucination_evaluation_model`, ~110M, `trust_remote_code`) → consistency score 0–1. **`trust_remote_code` executes repo code on load → the model download + first load is owner-gated (egress + remote-code execution), pinned to a specific commit revision in the plan.**
  - **MiniCheck-DeBERTa-v3-Large** (`lytang/MiniCheck-DeBERTa-v3-Large`, ~440M, `AutoModelForSequenceClassification`) → binary supported. *(Flan-T5-Large deferred — added only if MiniCheck earns more effort on the first pass.)*
  - **4B entailment adapter** — the 4B judge endpoint driven by a **purpose-built `(evidence, claim) → SUPPORTED/UNSUPPORTED` entailment prompt** (NOT `grounding_judge.py`'s overclaim contract — that judges a different task). This is the LLM yardstick the specialists are measured against. *(Optional separate diagnostic row: run production `grounding_judge.py` on these cases to confirm it does NOT perform entailment — informative, clearly marked as not the baseline.)*
- **Output → label:** MiniCheck binary → SUPPORTED/UNSUPPORTED directly. HHEM score evaluated across a **threshold sweep `{0.3, 0.5, 0.7}`** — no single threshold is treated as canonical yet.
- **Latency** measured per call. VRAM: 0 for the CPU verifiers, ~1.1GB for the 4B (recorded, not measured per-call).
- Models load once (cached); CPU inference via the installed `torch 2.12.0+cpu` + `transformers 5.10.2`.

## Deliverable 3 — the report
`scripts/grounding_bench/results_grounding.{csv,md}`:
- **Headline — per-mode false-negative rate:** of the UNSUPPORTED cases in each dangerous mode (cited-but-unsupported, fabricated/false-specific, stale-over-current), how many did the candidate wrongly bless as SUPPORTED? *This is the number that decides the audition.*
- Side columns: false-positive rate (SUPPORTED → UNSUPPORTED, the annoying-not-dangerous error), abstain-correctness, latency p50/p95, VRAM.
- HHEM shown at each sweep threshold; **provisional headline threshold = the one minimizing false-negatives**, with FP printed beside it.
- Candidate rows vs the **4B-entailment-adapter** baseline — "can a small specialist match/beat an LLM at the claimable-entailment check?" (plus the optional production-`grounding_judge` diagnostic row, marked *not* an entailment baseline).

## What v0 does NOT touch
- The live `grounding_judge.py`, the daemon, any service/flag. (A *follow-on* slice would wire a winning verifier in — out of scope here.)
- The deterministic citation rail and the `forbidden`/`self_history` overclaim rail — unchanged, and excluded from the corpus.
- The existing `judge_bench` overclaim set — stays the LLM judge's.

## Testing
Unit tests for the harness (`/home/rohit/maez/.venv/bin/python -B -m unittest`):
- abstain precondition fires on `claimable_absent` and **does not call any model**; scored correct vs `ABSTAIN_EXPECTED`.
- output→label mapping (MiniCheck binary; HHEM at a given threshold).
- per-mode false-negative tally is computed correctly on a tiny fixed fixture.
- a smoke run over a 3-case fixture completes and writes the report shape.
The corpus itself is *data*, validated by the label-review gate, not unit tests.

## Honesty / covenant anchors
- The verifier is the swappable instrument; **the report decides** — no model gets special status (judge-agnostic).
- A verifier that misses hallucinations (false-negative) is worse than useless → false-negatives are the headline.
- Corpus labels are honest (real failures included, synthetic flagged, every row reasoned) — canon-governs-canon applied to the bench corpus itself.
- Composes *above* the deterministic floor (`cited=0 ⇒ not grounded`); the verifier is the auditioned faster/smaller support layer, never the whole judge.
