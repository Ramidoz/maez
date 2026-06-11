# Evidence-grounding verifier audition

Headline metric: **per-mode false-negative rate** (an UNSUPPORTED claim wrongly blessed SUPPORTED — the dangerous miss).

## False-negatives by mode (lower is safer)

| candidate | cited_but_unsupported | fabricated_false_specific | stale_over_current |
|---|---|---|---|
| minicheck-deberta | 0/5 | 0/5 | 1/4 |
| 4b-entailment-adapter | 0/5 | 0/5 | 1/4 |

## Side metrics

| candidate | n | false_pos | abstain_ok | abstain_wrong | errors | p50 s | p95 s |
|---|--:|--:|--:|--:|--:|--:|--:|
| minicheck-deberta | 26 | 2 | 3 | 0 | 0 | 0.12 | 0.159 |
| 4b-entailment-adapter | 26 | 0 | 3 | 0 | 0 | 1.905 | 3.153 |

## Deferred candidate
- **HHEM-2.1-Open**: DEFERRED — incompatible with the installed `transformers 5.10.2` (loads with randomly-initialized `embed_tokens`; the API-confirmation smoke caught it before any number was trusted). Auditioning it would require an isolated `transformers-4.x` environment. Not a valid candidate in this environment.

## Verdict
On the headline (per-mode dangerous false-negatives), **MiniCheck-DeBERTa equals the 4B LLM** — 0/5 cited-but-unsupported, 0/5 fabricated/false-specific (incl. the true-in-world-but-unsupported `ffs-4`), 1/4 stale-over-current — at **~16× the speed (0.12s vs 1.9s p50) and 0 GPU VRAM** (vs the 4B's ~1.1GB). MiniCheck's cost is **2 false-positives** (over-rejecting `pos-3` "roughly doubles" and the strict-rule `mc-2`) vs the 4B's 0 — i.e. it errs toward over-rejection, the *safe* direction for an honesty judge (a false alarm is annoying; a blessed hallucination is dangerous).

**MiniCheck earns a follow-on slice** to wire it into the live grounding path as the claimable-entailment support check — the triple win realized (equal dangerous-mode catch, ~16× faster, frees the judge's GPU). Out of scope for this audition v0.

**Secondary finding:** `stale_over_current` is the hardest mode for *both* the specialist and the LLM (1/4 miss each — MiniCheck missed soc-3, the 4B missed soc-1). A pure entailment verifier doesn't reliably catch "the claim follows a stale value when the evidence also gives the current one"; the wire-in slice should pair the verifier with recency/supersession handling, not lean on it alone.
