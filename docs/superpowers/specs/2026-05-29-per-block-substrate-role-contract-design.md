# Per-Block Substrate Role Contract (precursor slice) Design Spec

**Date:** 2026-05-29
**Status:** design, pending Rohit review → writing-plans
**Why:** Precursor to [Living Memory — Recency-Salience](2026-05-29-living-memory-recency-salience-design.md). That slice needs the dispatcher to carry "this memory is **evidence**, that memory is **context**" from the *same* substrate source. Today it physically cannot: `RecallBlock` has no role; `_source_summaries` joins all blocks of a source into one text with one spec-level role; and `_audit_envelope` would flatten/lie if a source had two roles. This slice builds that carrier — **inert until a producer uses it** — so the ranking/partitioning work lands on a proven, honest contract.

## Goal

Let a recall producer tag individual `RecallBlock`s with a substrate role, and have that role flow **honestly end-to-end** — prompt render AND audit envelope — without flattening duplicates or lying in telemetry. With no producer emitting role hints, behavior is **byte-identical to today**.

## Scope

- Dispatcher plumbing only: `spec.py`, `layer1.py`, `merge.py`, `brain_loop.py` (render path), `provenance_renderer.py` (audit shape).
- **No recall-ranking changes** (that's the next slice). **No flag** — the carrier is inert-until-used; correctness is proven by parity tests (no hints → identical) + new tests exercising hints.

## The four mechanical changes

1. **Move `SourceRole` to `spec.py` (layering fix).** It currently lives in `provenance_renderer.py:37`; `RecallBlock` lives in `layer1.py`. A role field on `RecallBlock` must not import a *renderer* concept upward. Move the `SourceRole` `StrEnum` into `spec.py` (the dispatcher's foundation module); update the 3 importers (`provenance_renderer`, `merge`, `brain_loop`) to import it from `spec`. `SourceSummary` stays in `provenance_renderer`. Modest, mechanical churn (verified: 3 non-test files).

2. **Add `role_hint` to `RecallBlock`** (`layer1.py`):
   ```python
   role_hint: SourceRole | None = None   # None = use the spec-default substrate role (today's behavior)
   ```

3. **Group by `(source, role_hint)` in both render paths.**
   - `merge._source_summaries` ([merge.py:263](../../../core/dispatcher/merge.py#L263)) currently does `text = "\n".join(block.text for block in recall_blocks if block.source == source)` with one `substrate_role`. Change to: for each source, group its blocks by effective role (`block.role_hint or substrate_role`); emit **one `SourceSummary` per (source, role)** group, joining only the blocks in that group.
   - `brain_loop` direct-render ([brain_loop.py:280-289](../../../core/brain/brain_loop.py#L280-L289)) does the same single-role assignment — apply the identical grouping.
   - **Legal-role validation:** every emitted role must be in `_allowed_roles(spec.provenance_framing)` ([provenance_renderer.py:135](../../../core/dispatcher/provenance_renderer.py#L135)). If a `role_hint` is illegal for the active framing → **refuse** via the existing `_refuse_template_mismatch` (fail honest, do not silently coerce). v1 producers will use `SUBSTRATE_ONLY_NO_FRESH_VALIDATION`, which permits both `SUBSTRATE_EVIDENCE` and `SUBSTRATE_CONTEXT` (verified line 137).

4. **Audit envelope must carry every (source, role) — not a source-keyed dict.** `_audit_envelope` ([provenance_renderer.py:237-242](../../../core/dispatcher/provenance_renderer.py#L237-L242)) builds `source_role_map` / `source_digests` as comprehensions keyed by `summary.source.value` — a second summary for the same source overwrites the first, so the recorder would log one role while the prompt shows two. Add an honest list:
   ```python
   "source_role_entries": [
       {"source": s.source.value, "role": s.role.value, "digest": s.content_digest}
       for s in source_summaries
   ]
   ```
   Decision for review: **keep `source_role_map`/`source_digests` for back-compat** (document them as "first-role-per-source, lossy when a source has multiple roles" — the plan greps consumers) **and add `source_role_entries` as the authoritative honest record**, OR migrate consumers off the dicts. Lean: keep + add (non-breaking), make `source_role_entries` the source of truth.

## RED tests (anchors)
1. **Parity (inert):** with all `role_hint=None`, rendered prompt + audit envelope are byte-identical to pre-change for a representative substrate spec. (The safety floor — landing this changes nothing until used.)
2. **Two roles, one source — render:** two `RecallBlock`s for `TELEGRAM_SEMANTIC` with `role_hint=SUBSTRATE_EVIDENCE` and `SUBSTRATE_CONTEXT` under `SUBSTRATE_ONLY_NO_FRESH_VALIDATION` → prompt contains BOTH `[memory evidence]` and `[memory context]`. (Fails today — fundamental.)
3. **Two roles, one source — audit honesty:** the same case → `source_role_entries` contains BOTH entries for `TELEGRAM_SEMANTIC` (evidence + context), with distinct digests. (Fails today — the dict flattens it.)
4. **Illegal role refused:** a `role_hint` not permitted by the active framing → `_refuse_template_mismatch` (no silent coercion).
5. **Merge + direct-render agree:** both paths produce the same (source, role) grouping for the same blocks.
6. **Default role still applies:** a `role_hint=None` block under `SUBSTRATE_EVIDENCE_FRESH_CONTEXT` still renders `[memory evidence]` exactly as today.

## Witness
No live witness needed in isolation (inert carrier; covered by the parity + contract tests). The behavioral witness happens in the living-recall slice, which is the first producer to emit role hints. Broad-suite floor must hold (no new failures beyond the documented 2-3).

## Out of scope
- Recall ranking / recency-salience (next slice).
- Which entries become evidence vs context (next slice decides; this slice only *carries* the decision).
- Fresh/external role plumbing (unchanged).
