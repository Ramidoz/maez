# MiniCheck Grounding Shadow — v0 Design

**Date:** 2026-06-11
**Status:** spec for owner review
**Lane:** Codex builds / Claude reviews (covenant axis — this attaches a verifier instrument near Maez's voice, even in shadow).
**Parents:** the grounding-verifier audition (`scripts/grounding_bench/`, merged @ `d9c396b`) which proved MiniCheck-DeBERTa equals the 4B LLM on dangerous grounding modes at ~16× speed / 0 GPU VRAM; `core/safety/self_claim_audit.py` (`audit() → AuditResult`, the final-text producer); `core/cognition/envelope_builder.py` (`claimable` rendering); `core/routing/recall_shadow.py` (the in-tree shadow pattern); `feedback_verifier_swappable_receipt_invariant`, `feedback_two_sided_verifier_pressure`, `feedback_perception_free_egress_disciplined` (content-light), `feedback_visible_substrate_state_not_chain_of_thought`.

## Why
The audition surfaced a real gap: `claimable` evidence is rendered into the brain's *generation* context (`envelope_builder.py:132`) but **no live judge audits whether the served claim actually follows from it** — `self_claim_audit`/`grounding_judge` audit the *overclaim* rail (signals/self-history), not claimable-entailment. MiniCheck fills that gap. But the bench proved MiniCheck on a 26-case corpus, **not** on Maez's live voice — its real paraphrases, partial claims, filler, and mixed-evidence answers. So v0 is **not a rail**: it's a shadow that *watches* MiniCheck on live replies and writes down what the instrument thought, **changing nothing Maez says and blocking nothing**. Don't give the new guard a brake pedal before it's ridden shotgun with a clipboard.

## Scope boundary (load-bearing)
v0 **gates nothing, rewrites nothing, blocks nothing, delays nothing**. The served reply is byte-identical whether the shadow runs, succeeds, times out, or is down. v0 explicitly **defers**: any gating; recency/supersession handling (the stale-over-current mode the bench showed is hard for *both* verifiers); and the in-scope-sentence filter (filler vs real claim) — all to be designed from the shadow data, not guessed now.

## Architecture
An **out-of-process** MiniCheck HTTP service + a default-OFF **post-audit shadow hook** in the daemon's reply path that calls it best-effort under a tiny budget and writes content-light divergence telemetry. **The daemon never imports `transformers` or loads the model.**

## Components

### 1. `minicheck-verifier.service` (the instrument, outside the body)
A tiny local HTTP service wrapping MiniCheck-DeBERTa: `POST /support {evidence, claim} → {verdict: "SUPPORTED"|"UNSUPPORTED", score}`. Owns all PyTorch / model weight. Bound to `127.0.0.1`. Ships **installed-but-inert** (the unit exists; it is not started by the merge).

### 2. `SupportVerifier` interface
- `HttpSupportVerifier` — the live impl: `support(evidence, claim, timeout_s) → (label, score, latency)`; any transport error → a clean `("UNAVAILABLE", None, latency)` (never raises into the caller).
- `FakeSupportVerifier` — tests only; in-process, scripted verdicts, can simulate timeout/raise. **The real model is never loaded in-process, including in tests.**

### 3. The shadow hook — runs on the FINAL audited text
Placement is a correctness requirement, not a preference: the audit can **rewrite** completion claims before the user sees them, so shadowing pre-audit text would measure sentences Maez never served. The hook composes **after `audit()` returns**, never inside `_find_flags()`.

Input: `(AuditResult.text, AuditResult summary, claimable items, surface/boot metadata)`. The `AuditResult` summary = `{flags: count + kinds, rewritten: bool, judge_available: bool, mode}`.

Behaviour when the flag is on:
1. Split `AuditResult.text` into sentences.
2. For each sentence (within the budget): `verifier.support(all_claimable_evidence_concatenated, sentence)`.
3. Write **one** content-light telemetry record.
4. Return nothing into the reply path. **Pure observation.**

It must **not delay the served reply** — run it after the reply is dispatched (post-hoc), or if structurally in-path, the two-layer budget below bounds any tail to a few hundred ms and it is non-blocking regardless.

### 4. Two-layer budget (the tail-latency guard)
- **Per-sentence timeout** (e.g. 250ms — MiniCheck is ~120ms/sentence, so generous).
- **Reply-level max shadow time** (e.g. 1500ms total).
- If the reply-level budget is exhausted mid-reply: stop shadowing the remaining sentences, log status `budget_exceeded` with `{shadowed_count, remaining_count}`. A 12-sentence answer can never multiply a small timeout into real tail latency.

### 5. Shadow telemetry (content-LIGHT by default)
One JSONL record per shadowed reply, to a shadow-telemetry log (sibling to `recall_shadow` / valence telemetry — **not** the birth-gated durable ledger):
- ids/meta: `shadow_id`, `ts`, `surface`, `boot_id`.
- existing-audit summary: `audit_available`, `flag_count`, `flag_kinds`, `rewritten`, `mode`.
- claimable summary: `claimable_count`, `claimable_chars`, hashed `provenance_refs` — **no owner text**.
- per-sentence: `sentence_hash` (and a length-bounded snippet **only when an explicit `MAEZ_GROUNDING_SHADOW_DEBUG` flag is on**), `verdict`, `score`, `latency_ms`, `error`.
- reply summary: `sentence_count`, `unsupported_count`, `supported_count`, `skipped_count`.
- `status`: `ok` | `timeout` | `verifier_unavailable` | `no_claimable` | `no_sentences` | `budget_exceeded`.

This is **divergence data, not agreement** — the existing audit and MiniCheck ask different questions (overclaim vs entailment). We log both side-by-side so *we* read, offline, whether MiniCheck's live UNSUPPORTED flags are real added coverage or innocent noise.

## Error handling (the shadow's prime directive)
The served reply is byte-identical and undelayed under every failure: endpoint down/timeout → `verifier_unavailable`/`timeout`; no claimable evidence → `no_claimable` (the abstain rule — logged, never blessed); no sentences → `no_sentences`; budget hit → `budget_exceeded`. The shadow **never** raises into the reply path.

## Flags
- `MAEZ_GROUNDING_SHADOW_ENABLED` (default **off**) — gates whether the shadow runs at all.
- `MAEZ_GROUNDING_SHADOW_DEBUG` (default off) — gates owner-text snippets in telemetry.
- Merge is **inert**. The witness breath = start `minicheck-verifier.service` **and** flip `MAEZ_GROUNDING_SHADOW_ENABLED=1`, then read the divergence telemetry.

## Testing (`/home/rohit/maez/.venv/bin/python -B -m unittest`)
- shadow hook with `FakeSupportVerifier`: verdicts logged, **reply byte-identical**.
- shadow-never-blocks: fake raises / times out → reply unchanged + `verifier_unavailable`/`timeout` logged.
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
