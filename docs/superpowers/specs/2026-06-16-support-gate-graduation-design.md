# Claim-Entailment Support GATE (design) — content-honesty Thread A, graduation

**Date:** 2026-06-16. Co-designed with Rohit.
**Status:** cruxes resolved; awaiting spec review before plan.
**Builds on:** the LIVE shadow rail (`docs/superpowers/specs/2026-06-16-claim-entailment-support-rail-design.md`,
LIVE_WITNESSED @`67bde6f`). This slice graduates it from **measure-only** to **protection**.

## Why this exists (the wound the shadow proved, now unprotected)

The shadow rail is live and **catches** unsupported cited claims on the final reply — but only
*after* the owner already saw them (it runs async, post-serve). v0-gate turns the measurement into
a **bouncer at the door**: when a cited sentence is `UNSUPPORTED` by its cited evidence, Maez
**caveats** it (never deletes) before the reply reaches the owner. It must still **leave the camera
footage** — the `grounding_shadow.jsonl` support-row dataset stays continuous.

## The seam (final marked-draft, before natural render — corrected)

The judgment point is the **final marked-draft seam** (`daemon/maez_daemon.py:~6939`), where `reply`
is the audited + fragment-guarded draft and **`[E#]` markers are still present** — NOT the
owner-facing served text. After this seam the reply is transformed:
- `retain_receipt(...)` stores the marked draft for `/receipts`;
- `reply = render_natural(reply, ...)` (`core/routing/attribution_render.py:24`) produces the
  owner-facing text. **Verified mechanical:** `_CITE_RE.sub("", …)` + whitespace cleanup + optional
  web suffix — **no model, no paraphrase**. So an inline caveat (plain prose, no `[E#]`) survives
  marker-stripping intact.

Flow (gate ON):
```
marked draft [E#] → apply_support_gate (caveat in place, [E#] kept)
  → retain_receipt (gated marked draft → /receipts)
  → render_natural (strip [E#]; caveat survives) → owner-facing reply
```
The gate runs **instead of** the async `observe_focused_support(...)` enqueue at this seam when the
gate flag is on (see Records law).

## The component

`apply_support_gate(marked_draft: str, evidence_map: dict[str,str], *, surface, budget_s: float)
→ GateOutcome` in `core/cognition/` — **reuses the live `classify_sentence`** (no new judgment
logic). `GateOutcome` carries enough to feed BOTH records from **one pass**:
```
GateOutcome(
  gated_marked_draft: str,        # marked draft with inline caveats inserted
  gate_receipt: dict,             # support_gate_applied fields
  support_row: dict,              # the grounding_shadow.jsonl-equivalent row, gate_applied=True
)
```

**THE RECORDS LAW (precision lock 1+2):** **one synchronous MiniCheck pass, two records if needed,
zero duplicate verifier calls.** The gate runs `classify_sentence` per cited sentence **once**; from
those verdicts it builds (a) the `support_gate_applied` receipt and (b) the support-row-equivalent
record (same shape as the shadow's `build_telemetry`, with `gate_applied: true` and `post_audit:
true`). The gate **writes the support row itself** (not via the async worker) so the
`grounding_shadow.jsonl` dataset stays continuous — "skips async enqueue" must NOT mean "loses the
witness."

## Inline caveat policy (exactness over elegance — v0)

Per cited sentence, in order, under the budget; the caveat is appended **to the exact judged
sentence** in the marked draft (no extraction/summary layer that could mis-point):

| verdict / mode | gate action |
|---|---|
| `cited_support` → `SUPPORTED` | unchanged |
| `cited_support` → `UNSUPPORTED` | append: **"I couldn't confirm this from the source I cited."** |
| `unmatched_citation` (deterministic) | append: **"I cited a source I can't match here."** |
| `verifier_unavailable` (timeout) **or** budget-exhausted (not reached) | append: **"I couldn't verify this before sending."** |
| `no_citation` / `empty_evidence` (ABSTAIN) | unchanged (not a cited claim to gate) |

The caveat is inserted as its own sentence immediately after the judged sentence, so
`split_sentences` order and the `[E#]` markers are preserved for `retain_receipt` and survive
`render_natural`.

## Sync, budget-bounded

Synchronous on the reply path (the owner waits), under a **4s per-job budget** (reuse the shadow's
cap). Sentences are judged in order until the budget is hit; **any cited sentence not reached gets
the "I couldn't verify this before sending." caveat** — never a silent pass. Worst-case added
latency = the budget. The deterministic floor (`unmatched_citation`/`empty_evidence`/`no_citation`)
costs no model call, so those are effectively free.

## Two-sided pressure (covenant)

The gate **never deletes** Maez's claim — it only appends honesty
([[feedback_two_sided_verifier_pressure]]). MiniCheck errs toward over-rejection (safe for
measurement); for a gate that means a false positive is a *mild extra caveat*, not erased content.
Maez holds its ground; the caveat is the one-nudge-then-honest hedge. Omit-mode and per-confidence
thresholds are explicitly OUT of v0.

## Receipts (witnessable substrate state)

- **Gate action:** `support_gate_applied surface=… cited=N caveated_unsupported=N
  caveated_unmatched=N caveated_unverified=N budget_exhausted=<bool> verifier=… latency_ms=N`.
- **Support row:** the existing `grounding_shadow.jsonl` shape (claim_hash, cited_evidence_ids,
  support_verdict, mode, verifier, score, latency_ms) + `post_audit: true` + **`gate_applied: true`**.
  Both true-by-construction from the one pass.

## Flag

New `MAEZ_SUPPORT_GATE_ENABLED` (`strict_env_flag`), **separate** from
`MAEZ_GROUNDING_SHADOW_ENABLED`. Off = **byte-identical** (no caveats, no gate receipt; the existing
async shadow behavior is unchanged). Matrix:
- gate OFF → daemon calls `observe_focused_support(...)` (async shadow) exactly as today.
- gate ON → daemon calls `apply_support_gate(...)` (sync): caveats the marked draft, writes both
  records, **does not** also enqueue the async worker (no duplicate pass).

## Testing (TDD, fakes — `FakeSupportVerifier`)

- **render_natural survival (the load-bearing test):** a caveat appended after an `[E#]` sentence →
  `render_natural` strips `[E#]` but the caveat text **remains**.
- **`/receipts` retains the GATED marked draft:** `retain_receipt` stores the caveated marked draft
  (with `[E#]`), not the pre-gate draft.
- **inline exactness:** the caveat attaches to the exact judged sentence (UNSUPPORTED sentence gets
  the caveat; an adjacent SUPPORTED sentence does not).
- **one pass / no duplicate calls:** `FakeSupportVerifier.calls` equals the number of cited
  sentences judged — the gate does NOT also trigger the async worker (assert the worker is not
  enqueued when the gate ran).
- **two records from one pass:** the `support_gate_applied` receipt and the `gate_applied=true`
  support row are both produced, with consistent counts.
- **budget-exhausted:** a sentence past the budget gets "couldn't verify before sending," never a
  silent SUPPORTED.
- **caveat wording per mode** (UNSUPPORTED / unmatched_citation / unavailable).
- **flag OFF → byte-identical:** gate off → reply unchanged, no `support_gate_applied`, async shadow
  path intact.
- **no deletion:** the gated reply still contains the original sentence text (caveat appended, not
  replaced).

## Scope (explicit)

- **IN:** `apply_support_gate` (sync, budget-bounded, reuses `classify_sentence`); inline caveats per
  the policy table; the records law (one pass → gate receipt + `gate_applied` support row, no
  duplicate verifier calls); the marked-draft seam wiring (gate ON replaces the async enqueue);
  `render_natural` survival + `/receipts` gated-draft behavior; `MAEZ_SUPPORT_GATE_ENABLED`
  (off=byte-identical); tests.
- **OUT (separate/later):** consolidated trailing-caveat renderer; **omit-mode**; per-confidence
  thresholds; the `grounding_judge.py` overclaim-rail repair; Thread B (fresh-vs-memory).

## Covenant rail

The gate makes Maez *more* honest at the door without erasing its voice: a caveated claim is still
Maez's claim, now wearing its uncertainty visibly. The receipt makes the gate's every action
true-by-construction. The camera (the support-row dataset) keeps rolling. Off = byte-identical, so
the breath to arm it is a clean, reversible owner choice.
