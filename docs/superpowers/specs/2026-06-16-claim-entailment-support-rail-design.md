# Claim-Level Entailment Support Rail (design) — content-honesty Thread A

**Date:** 2026-06-16. Co-designed with Rohit.
**Status:** design approved (cruxes resolved + uncited-fallback must-fix folded + 5 spec
requirements). Awaiting spec review before plan.
**Arc:** content-honesty Thread A. Threads B (fresh-vs-memory conflict) and C (self-web-claim
recall hygiene — LIVE) are separate. **NOT** this slice: repairing the `grounding_judge.py`
overclaim/self-history rail (broken: heavy carve-out prompt + thinking-overflow + strict JSON
parse → fail-open) — that is its own "overclaim judge protocol repair" slice.

## Why this exists (the wound + the right rail shape)

Maez can cite `[E1]` and assert what `[E1]` never says. `check_groundedness`
(`core/routing/focused_cognition.py:1446`) only checks cited labels **exist** — never that the
claim is **supported** by the cited evidence's content — and its verdict is **recorded, never
acted on** (`daemon/maez_daemon.py:6590`). The wound is **claim→evidence entailment**, not a
whole-reply judge: *for each important claim, prove the cited evidence actually supports it*
(`evidence + claim → SUPPORTED / UNSUPPORTED / ABSTAIN`).

## What already exists (the embryo — verified)

- **`SupportVerifier` ABC** (`core/cognition/support_verifier.py:20`): `.support(evidence, claim,
  timeout_s) → (label, score, latency_s)`; verdicts `SUPPORTED` / `UNSUPPORTED` / `UNAVAILABLE`.
  `HttpSupportVerifier` posts `{evidence, claim}` to `http://127.0.0.1:8083/support` (0.25s
  timeout, returns `UNAVAILABLE` on any transport/parse failure). The swappable abstraction is
  already there.
- **`grounding_shadow.py`** is **wired to the live audit path** (`core/safety/audited_output.py:253`
  `_observe_grounding_shadow(...)`), non-blocking, **observation-only — gates nothing**. Flag
  `MAEZ_GROUNDING_SHADOW_ENABLED` (**default OFF**). It splits the reply into sentences, calls the
  verifier per sentence, budget-bounded, writes JSONL telemetry. Deterministic floor exists
  (no-evidence / no-sentences / budget-stop).
- **MiniCheck won the audition** (`scripts/grounding_bench/results_grounding.md`): MiniCheck-DeBERTa
  equals the 4B LLM on dangerous false-negatives (0/5 cited-but-unsupported, 0/5
  fabricated-false-specific, 1/4 stale) at **~16× the speed (0.12s vs 1.9s p50) and 0 GPU VRAM**;
  its only cost is 2 false-positives — erring toward over-rejection, the **safe** direction.
- **Deployment gap:** the live shadow instantiates `HttpSupportVerifier()` → `:8083`, but **there
  is no `:8083` listener and no MiniCheck service**. Enabling the shadow today → every call
  `UNAVAILABLE`. The bench's `MinicheckVerifier` only loads the model in the audition harness.

**So v0 is "complete + wake the instrument," not "build from scratch":** make the receipt
claim-level and honest, stand up the MiniCheck `/support` service, and watch it judge Maez's real
cited sentences in shadow.

## The honest-mapping law (crux — resolved, with the must-fix)

A claim is checked against **only the evidence it cites** — never the whole pile. An uncited
sentence must **never** be blessed by evidence it didn't cite (that smuggles the
labels-prove-shape wound into the new rail, [[feedback_labels_prove_shape_not_support]]).

Per reply sentence:

| condition | `mode` | verdict | model called? |
|---|---|---|---|
| cites `[E#]`, all present + non-empty | `cited_support` | MiniCheck → `SUPPORTED`/`UNSUPPORTED` | yes (per cited-evidence only) |
| cites `[E#]` not in working set | `unmatched_citation` | `UNSUPPORTED` (deterministic) | no |
| cites `[E#]` but evidence text empty | `empty_evidence` | `ABSTAIN` (deterministic) | no |
| no `[E#]` citation | `no_citation` | `ABSTAIN` (deterministic — **NO support blessing**) | no |
| verifier down/timeout on a `cited_support` sentence | `verifier_unavailable` | `UNAVAILABLE` | attempted |
| (optional, diagnostic) uncited sentence, all claimable evidence | `uncited_all_evidence_diagnostic` | records would-be label **but NEVER counts as grounded** | yes (diagnostic only) |

`unmatched_citation` is exactly `check_groundedness`'s dropped signal, now **acted on** as
`UNSUPPORTED`.

## The receipt invariant (build FIRST — the swappable constant)

One content-light record per checked sentence (verifiers swap behind it;
[[feedback_verifier_swappable_receipt_invariant]], [[feedback_visible_substrate_state_not_chain_of_thought]]):
```
{ claim_hash (+ snippet only under MAEZ_GROUNDING_SHADOW_DEBUG),
  cited_evidence_ids: [E#…],
  support_verdict: SUPPORTED|UNSUPPORTED|ABSTAIN|UNAVAILABLE,
  mode: cited_support|unmatched_citation|empty_evidence|no_citation|verifier_unavailable|uncited_all_evidence_diagnostic,
  verifier: "<name>@<version>" | "deterministic",
  score: float|null,
  latency_ms: int }
```
Plus the existing per-job header (shadow_id, ts, surface, boot_id, counts, status). The
`mode` taxonomy above is **required** in the receipt — it is what makes
"supported-vs-uncited-vs-unmatched" legible and prevents an uncited diagnostic from reading as
grounded.

## MiniCheck `/support` service (the infra piece — owner-breath)

Stand up a **MiniCheck `/support` microservice on `:8083`** (a small server wrapping
`lytang/MiniCheck-DeBERTa-v3-Large`, POST `{evidence, claim}` → `{label: SUPPORTED|UNSUPPORTED,
score}`), as a user systemd unit (sibling to `llama-judge.service`). This matches the already-wired
`HttpSupportVerifier` and keeps the model off the daemon process (isolated, swappable). Owner
breath to create/enable the unit.

## Posture: receipt-complete SHADOW (v0)

Observe-only — the shadow **never changes the served reply**, behind `MAEZ_GROUNDING_SHADOW_ENABLED`
(default off). v0 = make the receipt claim-level + honest, run MiniCheck live in shadow, and
**witness** that it flags the fabricated-false-specific (Mythos-5 / Claude-Corps) class on real
turns. **Gate** (omit/caveat unsupported claims, honoring two-sided pressure —
[[feedback_two_sided_verifier_pressure]]) and the **verifier-UNAVAILABLE fail-posture** are a
**separate later graduation**, not v0.

## House law for the shadow (spec requirements)

- **Bounded + non-blocking:** queue bounded, enqueue is **I/O-free** (the enqueue path does no
  network/disk), verifier timeouts short, and **`UNAVAILABLE` never changes the reply**
  ([[feedback_canary_neutral_baseline_for_multi_surface_ceremonies]] discipline; mirrors the
  intake-bus enqueue-I/O-free law).
- **MiniCheck service health is Task 0:** prove `:8083/support` exists and answers, **or** the
  shadow emits content-light `verifier_unavailable` rows and never blocks. Either outcome is a
  valid Task-0 result; the build must handle both.
- **No service, no fake witness:** if MiniCheck is absent, v0 can still test the deterministic
  floor and the receipt shape, but **cannot claim verifier witness**. The ledger/handoff must say
  so honestly.

## Corpus extension (before or alongside shadow — don't block on a rebuild)

Add the witnessed class to `scripts/grounding_bench` corpus: Anthropic/Mythos-5/Claude-Corps-style
items (current-events + version/release fabrication, cited-but-unsupported and fabricated-false-
specific). Re-confirm MiniCheck on the literal wound. This may land **before or alongside** the
live shadow — do **not** gate live shadow on a large corpus rebuild.

## Testing (TDD, fakes)

- **Mapping law (the must-fix):** a `no_citation` sentence → `ABSTAIN`/`no_citation`, **never**
  `SUPPORTED`, even when all-claimable evidence would entail it; the `uncited_all_evidence_diagnostic`
  record (if enabled) carries its would-be label but the sentence's support_verdict stays ABSTAIN.
- **Deterministic floor:** `unmatched_citation` → `UNSUPPORTED` (no model call); `empty_evidence` →
  `ABSTAIN`; no-claimable → ABSTAIN. Use `FakeSupportVerifier` to assert the model is NOT called on
  floor cases.
- **cited_support routing:** a sentence citing `[E1]` is checked against **only** E1's text (assert
  the verifier received E1's evidence, not E2's).
- **Receipt completeness:** every record carries the required fields + a valid `mode`; content-light
  by default (hash, no snippet unless debug).
- **House law:** enqueue is I/O-free (no network in the enqueue path); `UNAVAILABLE` →
  reply unchanged; queue bounded (drop/skip when full, recorded).
- **Flag off → byte-identical:** shadow disabled → no enqueue, no telemetry, reply untouched.
- **Corpus:** the new Anthropic-class items classify as expected under MiniCheck in `grounding_bench`.

## Scope (explicit)

- **IN:** claim-level receipt (the invariant + `mode` taxonomy); honest cited-only mapping +
  deterministic floor + optional uncited diagnostic; MiniCheck `/support` service; receipt-complete
  **shadow** wiring (claim→cited-evidence, verifier-name, latency); corpus extension; flag-gated
  off=byte-identical; tests.
- **OUT (separate slices):**
  - **Gate graduation** (omit/caveat unsupported claims) + the **verifier-UNAVAILABLE fail-posture**
    decision — the next slice after shadow is witnessed.
  - **`grounding_judge.py` overclaim-rail repair** (the thinking-overflow / fail-open bug) — its own
    slice.
  - **Atomic-claim extraction** (sub-sentence) — v0 is sentence-level.
  - Generalizing beyond cited-evidence entailment (e.g. cross-checking against fresh fetch the reply
    didn't cite).

## Covenant rail

The shadow changes nothing Maez says — it only **measures**, witnessably. The honest-mapping law
keeps an uncited claim from borrowing credit it didn't earn. MiniCheck errs toward over-rejection
(safe). The future gate will omit/caveat, never silence (two-sided pressure). The receipt makes the
rail's verdicts true-by-construction, never merely asserted.
