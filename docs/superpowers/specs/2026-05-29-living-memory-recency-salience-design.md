# Living Memory — Recency-Salience + Continuity Faculty (v1) Design Spec

**Date:** 2026-05-29
**Status:** design, pending Rohit review (rev 3 — depends on the per-block role-contract precursor) → writing-plans
**Depends on:** [per-block-substrate-role-contract](2026-05-29-per-block-substrate-role-contract-design.md) (lands + witnessed first; provides the role-carrying contract this slice produces into).
**Origin:** Blocker B root-cause ([blocker-b-recall-ranking-rootcause-2026-05-29](../../slices/recall-axis-dispatcher/witness/blocker-b-recall-ranking-rootcause-2026-05-29.md)). Recall ranks pure cosine, age-blind; continuity/freshness asks are *semantically attracted* to old meta-memory ("what were we talking about earlier?" → a 43-day-old "what happened?" exchange).
**Grounding:** Generative Agents (recency × importance × relevance — canonical match) [2304.03442]; MemoryBank (time + significance) [2305.10250]. (Two 2026 refs Rohit cited are past Claude's Jan-2026 cutoff, unverified here; design doesn't rely on them.)

## Principle

Two memory faculties over the same substrate, expressed as **scoring + labeling** passes (not new databases):
- **Working / continuity faculty** — "what we've been talking about" = the recent thread, time-ordered. The recent thread *is* the answer; cosine similarity to the question's words is the wrong faculty.
- **Long-term / living recall** — "what do I know about X" = semantic relevance, but **present-weighted** (recent weighs more by default), **salience-preserving** (curated things stay *available*), and **deep recall still works** when explicitly reached for.

## Scope (v1)

- **`recall_for_telegram` ONLY** ([memory_manager.py:1650](../../../memory/memory_manager.py#L1650)). `recall_for_cycle` shares helpers but is a wider blast radius — explicitly untouched (RED test asserts byte-identical on/off).
- **Flag-gated** (`MAEZ_LIVING_RECALL_ENABLED`, default off) — behavior-affecting memory change; witnessed before any default-on.

## Two independent knobs (Rohit seam #3 — do NOT couple them)

- **`ranking_half_life_days` (gentle, default 90)** — governs ORDER only. `recency_factor = 0.5 ** (age_hours / (ranking_half_life_days*24))`. Stale ranks lower but stays retrievable.
- **`evidence_recency_days` (strict, default 14)** — governs the LABEL only. Only entries newer than this (or continuity recent-thread) may be `[memory evidence]`; everything older is `[memory context]` even if it ranks well. This is what actually stops the bug class: an 80-day memory can still *appear* (ranked, as context) but can never be *cited as evidence*.

## Decisions (rev 2)

1. **Distance-space integration.** Extend the existing `base_distance / weight` reorder ([memory_manager.py:1370](../../../memory/memory_manager.py#L1370)): `effective_distance = distance / max(recency_factor, 1e-3)`. No rewrite to a `similarity × …` descending score.
2. **Telegram-scoped OVERFETCH before rerank (Rohit seam #4).** `_query_collection` truncates to `n` at [line 1375](../../../memory/memory_manager.py#L1375) *before* `recall_for_telegram` sees it — so reranking the age-blind top-20 can't surface a fresher candidate that sat at rank 25. v1 must overfetch a larger telegram-scoped pool (e.g. 100), apply the living rerank, **then** truncate to the final ~10. Achieved WITHOUT changing `_query_collection`'s shared truncation (pass a larger `n` from the telegram path, or a telegram-only overfetch helper; the rerank+final-truncate live in `recall_for_telegram`).
3. **Salience = curated/core only; promotion_score SHADOW-ONLY.** `record_recall()` is fed by the *current broken ranking*, so promotion_score is polluted (stale entries scored "important" because the bug surfaced them) — applying it would launder the bug into salience. v1: promotion_score is **computed + logged, not applied**; activated only in v2 against a post-fix watermark.
4. **Core memories = availability floor, NOT evidence authority (Rohit seam #2).** The 88 core memories are query-independent and always-included. Labeling them `[memory evidence]` would re-create context-dominance with curated content. v1: **core defaults to `[memory context]`** — always available, never auto-authoritative. (A future explicit-reference/identity path may promote a specific core memory to evidence; not v1.)
5. **Per-block role contract lives in the PRECURSOR slice; this slice is its first PRODUCER.** The mechanism — `RecallBlock.role_hint`, `(source, role_hint)` grouping in merge + direct-render, legal-role validation, `SourceRole`→`spec.py`, and audit-envelope honesty (`source_role_entries`) — is built and tested in the [precursor](2026-05-29-per-block-substrate-role-contract-design.md). This slice **depends on it** and is the first code to *emit* role hints: it partitions the recalled set by `evidence_recency_days` into an **evidence block** (continuity recent-thread + semantic age ≤ cutoff) tagged `role_hint=SUBSTRATE_EVIDENCE` and a **context block** (older semantic + core) tagged `role_hint=SUBSTRATE_CONTEXT`. **Framing: v1 uses `SUBSTRATE_ONLY_NO_FRESH_VALIDATION`** for substrate-recall turns — it already permits both substrate roles (verified [provenance_renderer.py:137](../../../core/dispatcher/provenance_renderer.py#L137)). **No new framing, no legal-map extension.** Hybrid/fresh turns are out of scope — don't widen the contract before the witnessed substrate path needs it.
6. **Continuity is a separate faculty.** Reuse `dialogue_continuity_state()`. DIRECT/ANAPHORIC → recent thread (`_recent_telegram_exchange_rows` / dialogue anchors) goes in the **evidence** partition; old semantic hits go in the **context** partition (kept available, never evidence).
7. **Explicit-reference override NOT v1-load-bearing.** Reliable "that April post" detection is an NER/date problem; a flaky detector that fails would bury deep recall. v1 leans on gentle ranking-decay + strong cosine (a relevant old memory still *appears* as context). Explicit-reference *promotion to evidence* is a named v2 refinement.

### Decisions settled (Rohit, rev 3)
- `ranking_half_life_days` = **90**, `evidence_recency_days` = **14** (tunable; the witness validates the gentle-ranking / strict-evidence split).
- Framing = **`SUBSTRATE_ONLY_NO_FRESH_VALIDATION`** (existing; permits both substrate roles). No new framing, no legal-map change.
- **Sequenced after** the per-block role-contract precursor (built + tested first; this slice produces into it).

## Architecture (data flow inside `recall_for_telegram`, flag-on)

```
state = dialogue_continuity_state(query)
overfetch = telegram-scoped semantic pool (e.g. 100), NOT the shared n=20 truncation
for each candidate: recency_factor = 0.5**(age_h/(ranking_half_life_days*24))
                    effective_distance = base_distance / max(recency_factor, 1e-3)
rank ascending by effective_distance; truncate to final ~10
partition:
  evidence  = continuity recent-thread (if DIRECT/ANAPHORIC)
            + semantic entries with age ≤ evidence_recency_days
  context   = older semantic entries + all core memories
emit RecallBlock(role_hint=SUBSTRATE_EVIDENCE) and RecallBlock(role_hint=SUBSTRATE_CONTEXT)
render: provenance_renderer maps roles → [memory evidence] / [memory context];
        _humanize_age on each entry ("just now", "last evening", "weeks ago")
```
Deep-recall preservation (worked): strong old match (0.33 cosine, 80d, recency≈0.54) → effective 0.61; it still *appears* (as `[memory context]`), demoted but not amputated — and a flag-off run is identical.

## Telemetry (shadow + observability)
Per turn: faculty (`continuity`/`living_recall`), `ranking_half_life_days`, `evidence_recency_days`; per surfaced candidate: `base_distance`, `recency_factor`, `effective_distance`, age, tier, role_hint, and the **shadow** promotion_score (logged, not applied). No raw memory text beyond what already renders.

## Flag + Witness (three-way; all must pass)
Flag `MAEZ_LIVING_RECALL_ENABLED` (launch-env, default off; stop unit → launch flag-on → probe → restore). Predicted-effect written before the window.
1. **Stale meta-memory stops surfacing as evidence** — "what were we talking about earlier?" → recent thread; "what have we discussed recently?" → recent material; any old journal appears at most as `[memory context]`, never `[memory evidence]`.
2. **Recent/fresh asks improve.**
3. **Deep recall NOT buried** — a deliberately old, explicitly-reached-for memory still *appears* (as context). The falsifier against over-decay.

## RED tests (anchors)
1. `recency_factor`: 0d→1.0, 1d→≈0.992, 90d→0.5, monotonic.
2. `effective_distance`: stale-weak demoted below fresh; stale-strong still present (finite, never dropped).
3. **Two knobs independent:** with `ranking_half_life_days=90`, an 80-day strong match still *ranks* but is labeled `[memory context]` (fails `evidence_recency_days=14`), not `[memory evidence]`.
4. **Overfetch:** a fresh candidate that sat outside the age-blind top-20 appears after the living rerank (assert via a seeded pool).
5. **Producer partition correctness:** living recall emits an evidence block (continuity recent-thread + semantic age ≤ `evidence_recency_days`) and a context block (older semantic + core) with the correct `role_hint`s; end-to-end both `[memory evidence]` and `[memory context]` render and the audit `source_role_entries` carries both. (The *carrier* is the precursor's test; here we assert the *partition* is produced correctly.)
6. **Framing:** the turn uses `SUBSTRATE_ONLY_NO_FRESH_VALIDATION`; both substrate roles are legal (no refusal).
7. **Core → context:** core memories render `[memory context]`, never auto-`[memory evidence]`.
8. **Continuity:** DIRECT/ANAPHORIC → recent thread in the evidence partition; old semantic in context.
9. **promotion_score not applied:** identical ranking whether shadow score is high or low (assert logged, not used).
10. **Scope:** `recall_for_cycle` ranking byte-identical flag on/off.
11. **Flag-off parity:** flag absent → `recall_for_telegram` behaves exactly as today.

## Out of scope (named, not lost)
- `recall_for_cycle` (v2). promotion_score as an **active** input (v2, post-watermark). Explicit-reference → evidence promotion (v2). Self-echo suppression (separate slice). Pruning the 88 always-in core (separate). Per-entry (sub-block) fine-grained mixing beyond the evidence/context partition (v1 is a two-way partition, not arbitrary per-entry labels).
