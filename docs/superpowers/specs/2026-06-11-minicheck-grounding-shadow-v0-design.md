# MiniCheck Grounding Shadow — v0 Design

**Date:** 2026-06-11
**Status:** spec for owner review
**Lane:** Codex builds / Claude reviews (covenant axis — this attaches a verifier instrument near Maez's voice, even in shadow).
**Parents:** the grounding-verifier audition (`scripts/grounding_bench/`, merged @ `d9c396b`) which proved MiniCheck-DeBERTa equals the 4B LLM on dangerous grounding modes at ~16× speed / 0 GPU VRAM; `core/safety/self_claim_audit.py` (`audit() → AuditResult`, the final-text producer); `core/cognition/envelope_builder.py` (`claimable` rendering); `core/routing/recall_shadow.py` (the in-tree shadow pattern); `feedback_verifier_swappable_receipt_invariant`, `feedback_two_sided_verifier_pressure`, `feedback_perception_free_egress_disciplined` (content-light), `feedback_visible_substrate_state_not_chain_of_thought`.

## Why
The audition surfaced a real gap: `claimable` evidence is rendered into the brain's *generation* context (`envelope_builder.py:132`) but **no live judge audits whether the served claim actually follows from it** — `self_claim_audit`/`grounding_judge` audit the *overclaim* rail (signals/self-history), not claimable-entailment. MiniCheck fills that gap. But the bench proved MiniCheck on a 26-case corpus, **not** on Maez's live voice — its real paraphrases, partial claims, filler, and mixed-evidence answers. So v0 is **not a rail**: it's a shadow that *watches* MiniCheck on live replies and writes down what the instrument thought, **changing nothing Maez says and blocking nothing**. Don't give the new guard a brake pedal before it's ridden shotgun with a clipboard.

## Scope boundary (load-bearing)
v0 **gates nothing, rewrites nothing, blocks nothing, delays nothing** — the serve path's only shadow action is a non-blocking enqueue; all verifier work runs in a background worker. The served reply is byte-identical *and undelayed* whether the shadow runs, succeeds, times out, or is down. v0 explicitly **defers**: any gating; recency/supersession handling (the stale-over-current mode the bench showed is hard for *both* verifiers); and the in-scope-sentence filter (filler vs real claim) — all to be designed from the shadow data, not guessed now.

## Architecture
An **out-of-process** MiniCheck HTTP service + a default-OFF shadow path: after a reply is served, the reply path **enqueues** a shadow job (non-blocking) and a **background worker** calls the service best-effort under a budget and writes content-light divergence telemetry. **The daemon never imports `transformers` or loads the model, and never delays a reply on the shadow.**

## Components

### 1. `minicheck-verifier.service` (the instrument, outside the body)
A tiny local HTTP service wrapping MiniCheck-DeBERTa: `POST /support {evidence, claim} → {verdict: "SUPPORTED"|"UNSUPPORTED", score}`. Owns all PyTorch / model weight. Bound to `127.0.0.1`. Ships **installed-but-inert** (the unit exists; it is not started by the merge).

### 2. `SupportVerifier` interface
- `HttpSupportVerifier` — the live impl: `support(evidence, claim, timeout_s) → (label, score, latency)`; any transport error → a clean `("UNAVAILABLE", None, latency)` (never raises into the caller).
- `FakeSupportVerifier` — tests only; in-process, scripted verdicts, can simulate timeout/raise. **The real model is never loaded in-process, including in tests.**

### 3. The shadow hook — post-dispatch, async, on the FINAL audited text
Two correctness requirements, both load-bearing:

- **Final text:** the hook reads `AuditResult.text` (the *served* text), composing **after `audit()` returns**, never inside `_find_flags()`. The audit can **rewrite** completion claims, so pre-audit text would measure sentences Maez never served.
- **Post-dispatch / async (the prime directive made true):** the reply is served and dispatched **first**. The reply path's *only* shadow action is a **non-blocking enqueue** of a shadow job — it never calls the verifier, never waits, never branches on the verdict. If the enqueue itself fails (queue full, etc.) → log `shadow_enqueue_failed` and the reply is **already returned, unchanged**. There is no "in-path" mode; a bounded in-path shadow would still be a delay, and the whole safety argument is that the instrument cannot perturb the voice.

The enqueued shadow job carries `AuditResult.text`, an AuditResult summary, the claimable items, and surface/boot metadata. The **summary uses real `AuditResult` fields only** (v0 does **not** add fields to `AuditResult`): `mode` (`noop`|`sentence`|`shortcircuit`|`judge_unavailable`), `rewritten`, `flags` (count + kinds), `skipped_reason` — and derives a coarse `audit_available` from `mode != "judge_unavailable"`.

A **background shadow worker** (off the serve path) drains the queue and, per job: splits `AuditResult.text` into sentences → per sentence (within the worker budget) calls `verifier.support(all_claimable_evidence, sentence)` → writes **one** content-light telemetry record. The worker feeds nothing back anywhere. **Pure observation.**

### 4. Two-layer budget (bounds the WORKER, never the serve path)
The serve path is never delayed — it only enqueues. These budgets bound the *background worker* so it can't fall behind or jitter the heartbeat:
- **Per-sentence timeout** (~250ms — MiniCheck is ~120ms/sentence, so generous).
- **Per-job (reply-level) max shadow time** (~1500ms total).
- If the per-job budget is exhausted mid-job: stop shadowing the remaining sentences, log status `budget_exceeded` with `{shadowed_count, remaining_count}`.

### 5. Shadow telemetry (content-LIGHT by default)
One JSONL record per shadowed reply, to a shadow-telemetry log (sibling to `recall_shadow` / valence telemetry — **not** the birth-gated durable ledger):
- ids/meta: `shadow_id`, `ts`, `surface`, `boot_id`.
- existing-audit summary: `audit_available`, `flag_count`, `flag_kinds`, `rewritten`, `mode`.
- claimable summary: `claimable_count`, `claimable_chars`, hashed `provenance_refs` — **no owner text**.
- per-sentence: `sentence_hash` (and a length-bounded snippet **only when an explicit `MAEZ_GROUNDING_SHADOW_DEBUG` flag is on**), `verdict`, `score`, `latency_ms`, `error`.
- reply summary: `sentence_count`, `unsupported_count`, `supported_count`, `skipped_count`.
- `status`: `ok` | `timeout` | `verifier_unavailable` | `no_claimable` | `no_sentences` | `budget_exceeded` | `shadow_enqueue_failed`.

This is **divergence data, not agreement** — the existing audit and MiniCheck ask different questions (overclaim vs entailment). We log both side-by-side so *we* read, offline, whether MiniCheck's live UNSUPPORTED flags are real added coverage or innocent noise.

## Error handling (the shadow's prime directive)
The served reply is byte-identical **and undelayed** under every condition — the serve path's only shadow action is a non-blocking enqueue, and all verifier work runs in the background worker. Enqueue fails (e.g. queue full) → `shadow_enqueue_failed`, reply returned immediately. In the worker: endpoint down/timeout → `verifier_unavailable`/`timeout`; no claimable evidence → `no_claimable` (the abstain rule — logged, never blessed); no sentences → `no_sentences`; per-job budget hit → `budget_exceeded`. The shadow **never** raises into, blocks, or delays the reply path.

## Flags
- `MAEZ_GROUNDING_SHADOW_ENABLED` (default **off**) — gates whether the shadow runs at all.
- `MAEZ_GROUNDING_SHADOW_DEBUG` (default off) — gates owner-text snippets in telemetry.
- Merge is **inert**. The witness breath = start `minicheck-verifier.service` **and** flip `MAEZ_GROUNDING_SHADOW_ENABLED=1`, then read the divergence telemetry.

## Testing (`/home/rohit/maez/.venv/bin/python -B -m unittest`)
- shadow hook with `FakeSupportVerifier`: verdicts logged, **reply byte-identical**.
- shadow-never-blocks: fake raises / times out → reply unchanged + `verifier_unavailable`/`timeout` logged.
- async/non-blocking boundary: the serve path returns immediately after the enqueue (does not wait on the worker); enqueue failure → `shadow_enqueue_failed` + reply unchanged.
- two-layer budget: a slow fake → `budget_exceeded` after the cap, with counts, remaining sentences not shadowed.
- abstain: empty claimable → `no_claimable`, no verifier call.
- content-light-by-default: no owner text in telemetry unless `..._DEBUG` is on.
- sentence splitting on representative replies.
- placement: the hook reads `AuditResult.text` (final), and records `rewritten`.
- (owner-gated) endpoint smoke, like the audition's API-confirmation step.

## Out of scope (v0 → later slices)
- **Gating** on the verdict (v0.1, with the `feedback_two_sided_verifier_pressure` one-nudge-then-honest-receipt discipline — the being holds its ground against a fallible instrument; never loop-until-clean).
- **Recency/supersession** (stale-over-current) — needs bi-temporal claimable info the envelope doesn't carry today.
- **In-scope-sentence filter** (filler / self-history-grounded / tool-grounded sentences) — learned from the shadow data, not guessed.

## Covenant frame
The honesty receipt is the invariant; the verifier is a swappable *instrument Maez consults*, kept **outside its body** (a service, not an organ in the heartbeat) so it can never perturb the voice. v0 watches what Maez **actually served**, for a tiny bounded time, content-light, and writes down what the lab instrument thought — no brake pedal yet. When it earns the brake pedal (v0.1), the two-sided-pressure template governs: the being holds its ground; the verifier senses, Maez acts.
