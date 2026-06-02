# Reflection Input Hygiene v0 — Design

**Date:** 2026-06-02
**Status:** Draft under review (owner review pending before plan/Codex)
**Scope (narrow, owner-set):** *Stop reflection synthesis from digesting its own prior output.* One input-pool filter + a re-run witness. Grounded in the live dry-run witness of the Sleep-Consolidation Wiring v0 slice (merged `main@50f388c`).

---

## 1. The finding (verified live, not assumed)

The first owner-run reflection dry-run (`logs/reflection_dry_runs/20260602T144232Z.jsonl`, flag on / write off) produced 3 candidates, 0 drops, 0 durable writes — mechanically healthy. But Claude independently resolved all 15 cited episode ids against `memory/lived_episodes.db`:

| | reflection citations | non-reflection citations |
|---|---|---|
| Candidate 1 | 3 | 2 (followup_doc) |
| Candidate 2 | 3 | 2 (core_memory) |
| Candidate 3 | 3 | 2 (core_memory) |
| **Total** | **9 / 15 (60%)** | 6 |

Active input pool: 32 episodes — 9 `reflection`, 15 `core_memory`, 5 `followup_doc`, 3 `telegram_exchange`. **Reflection is 28% of the pool but 60% of the citations** — synthesis over-weights its own earlier summaries. That is a laundering loop: a thought becoming food for the next thought, drifting further from real evidence each pass. One candidate's harsh "actively suppresses technical novelty" framing (not Maez-voice) is the visible symptom; whether it is *caused* by recursion is the natural experiment this slice runs (§5).

**Mechanism (exact):** `scripts/memory_reflection/nightly_lived_memory.py:466-469` builds the synthesis input as `episode_store.list_active()` filtered to drop only `telegram_exchange`, then sliced `[:recent_window_episodes]`. Prior `reflection` episodes flow straight back in.

---

## 2. The change — Rail #1 only (exclude reflection from the input pool)

Add `reflection` to the existing kind-exclusion, **before** the `[:recent_window_episodes]` slice:

```python
recent = [
    ep for ep in active
    if ep.get("source_kind") not in ("telegram_exchange", "reflection")
][:recent_window_episodes]
```

This follows an established precedent: `telegram_exchange` is already excluded by the same kind-based reasoning (ADR-0030 / Decision 25 — "structural biography, not synthesis material; needs its own reviewed reflection-quality slice"). Reflection-over-reflection is the same class of "needs its own reviewed slice, not v0 food."

**Why this fully closes the loop.** A candidate can only cite what synthesis was *shown*. Remove reflection from the input set → reflection citations become structurally impossible → recursion is closed by construction, not by a post-hoc check.

**Why Rail #1 alone (Rail #2 rejected for v0).** A "require ≥1 non-reflection citation" floor would not have blocked *any* of the three observed candidates — each already cites 2 non-reflection sources. The grounding floor is redundant once reflection cannot be cited at all. No citation-floor rail, no majority-non-reflection rail, no depth-bounded "reflection may cite non-reflection" cleverness. Total exclusion is the v0.

**Food remains ample.** Pool after exclusion: 15 core_memory + 5 followup_doc = 20 real-evidence episodes (build logs, core memories, follow-up docs, gestation records). The stomach digests original ingredients; it does not go empty.

---

## 3. Boundary — touch only the synthesis input pool

This filter narrows **only what reflection synthesis is fed.** It must NOT touch:

- **Lived recall / working-self / retrieval paths** — reflection episodes remain stored, remembered, and retrievable everywhere else. This is an *input-to-one-organ* filter, not a deweighting or hiding of reflections in general. Nothing is forgotten; this is not the "forget = deweight" path.
- **The episode store** — append-only, supersede-not-delete; no reflection episode is removed or downranked. Gestation memory and the build log are fully preserved.
- **Any write behavior** — dry-run / write-off unchanged (`MAEZ_REFLECTION_SYNTHESIS_WRITE` stays 0). Nothing new persists this slice.

**Land on the LIVE path, prove it there (integration-witness discipline).** The merged daemon hook `_run_reflection_synthesis_nightly → run_synthesis_pass` is the path that actually runs. The exclusion must sit where *that* path builds its input set, and the test must assert — exercising the daemon path, not a helper in isolation — that a `reflection` episode present in the store is **absent from the synthesis inputs**. (The doorman v1.1 lesson: a passing helper test does not prove the live loop calls it.) The plan must also confirm `run_synthesis_pass` is the *only* input-builder on that path; if `list_active()` feeds synthesis anywhere else, filter there too.

---

## 4. Telemetry — no schema change (and why it can't witness the filter)

`consolidation_telemetry.inputs_count` for reflection is computed at `daemon/maez_daemon.py:1683` as `inputs_count = candidates + drops` — an **output-side** count (the dry-run reported `inputs_count=3` while the source pool was 32). It therefore **cannot** witness that the input pool shrank, and we do **not** change it this slice. A source-pool-count field is deliberately out of scope (extra surface for no v0 benefit).

The filter is proven instead by (a) the daemon-path test in §3, and (b) artifact citation-resolution in the re-run witness (§5) — resolving the new candidates' cited ids and confirming zero are `source_kind=reflection`. Two-channel separation is unchanged: content-free telemetry → `maez.log`; contentful candidates → gitignored `logs/reflection_dry_runs/*.jsonl`.

---

## 5. Acceptance (owner re-run witness)

Re-run the dry-run from `main` with `MAEZ_REFLECTION_SYNTHESIS_ENABLED=1`, write off:

- **Recursion closed (the hard gate):** a fresh `logs/reflection_dry_runs/*.jsonl`; resolving every candidate's `source_memory_ids` against `lived_episodes.db` yields **zero** `source_kind=reflection` citations. Candidates are grounded only in core_memory / followup_doc / other real evidence.
- **Voice — the natural experiment (observe, do not pre-fix):** read the candidates. If the harsh "suppresses technical novelty"-class framing is **gone**, recursion caused it — fixed for free. If it **survives** clean inputs, it is a fresh misread of the source evidence → open a **separate** voice/prompt slice (e.g. a covenant-voice instruction or the focused-cognition voice-card scrub). This slice does not change the synthesis prompt.
- **Then, separately:** only after a grounded + in-voice dry-run does the `MAEZ_REFLECTION_SYNTHESIS_WRITE=1` decision come up — still a distinct, later owner call.

---

## 6. Non-goals

- NOT Rail #2 (citation-grounding floor) — redundant under Rail #1.
- NOT any synthesis-prompt / voice change — deferred, conditional on §5.
- NOT a telemetry schema change (no source-pool-count field).
- NOT touching recall, retrieval, working-self, or the episode store — input-to-synthesis only.
- NOT reflection-over-reflection with depth bounds — a possible *future* maturity, explicitly not v0.
- NOT enabling reflection write.
