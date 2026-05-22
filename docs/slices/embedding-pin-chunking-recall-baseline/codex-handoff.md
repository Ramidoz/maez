# Embedding Pin + Chunking Invariants + Recall Baseline -- Codex Handoff (Roadmap #2)

**Status:** design-gated handoff for the next Codex implementation pass. Not a merge verdict.
**Date:** 2026-05-22
**Class:** [Engineering] -- RED-first, measure-first. NOT covenant-shaped; no autonomy, no new capability.
**Runtime impact:** none intended. This slice pins, stamps, baselines, and asserts against CURRENT reality. It does NOT re-index, change the model, restart the daemon, or open autonomy.

## Why this slice

Maez's memory currently rides on Chroma's implicit `default` embedding function with no substrate-level statement of what it depends on. It works today, but the store does not say "this is the exact embedding model, tokenizer, dimension, distance metric, and storage shape we rely on." #2 puts a metal tag on the memory engine and saves a recall fingerprint, so future memory work cannot quietly move the floorboards.

## Verified ground truth (firsthand, Claude, 2026-05-22)

Read-only inspection of `memory/db/{raw,daily,core}` (daemon inactive):

- Collections: `raw_archive` (count 40185), `daily_consolidations` (13), `core_memories` (74).
- Dimension: **384** for all three.
- Distance metric: `hnsw:space = cosine` for all three (verified value, not assumed -- Chroma's historical default is `l2`).
- Existing collection metadata: only `{'hnsw:space': ...}`. **No** embedding/model/dim/tokenizer/chunk pin exists.
- Embedding model: Chroma `default` -> `ONNXMiniLM_L6_V2` / `all-MiniLM-L6-v2`.
  - `onnx.tar.gz` sha256 `913d7300ceae3b2dbc2c50d1de4baacab4be7b9380491c27fab7418616a16ec3` (verified).
  - `onnx/model.onnx` sha256 `4f148ba8ae9c2c7fbee4af2b132db8d06c6a6545b47fc83bbb98c3d22b8393e6` (verified).
  - Cache root: `~/.cache/chroma/onnx_models/all-MiniLM-L6-v2/`.
- Tokenizer truncation: `256` tokens (source/package-confirmed at pin time -- the implementation must verify this from the installed Chroma embedding function and/or tokenizer config and record the exact evidence; "operator-reported" is too soft for a pin).
- Vector chunking: none -- raw/daily/core entries are stored as whole documents. Separate consolidation chunking (~96000 chars) is prompt-side only and is NOT a vector chunk invariant.

## Authority hierarchy (load-bearing)

- **`memory/embedding_contract.json` is the authoritative pin** (versioned, diffable, reviewable).
- The Chroma collection metadata stamp is **evidence / self-description, NOT source of truth**.
- If manifest and stamp disagree, **the manifest wins** and memory-init flags and fails the write path (see drift behavior).

## Implementation steps (RED-first)

1. **RED first:** add the contract-assertion test; it FAILS on today's state because the collections carry no Maez embedding-contract metadata and no manifest exists.
2. **Add `memory/embedding_contract.json`** with: model id (`all-MiniLM-L6-v2` / Chroma `ONNXMiniLM_L6_V2`), the two verified artifact hashes, dim `384`, tokenizer truncation `256`, `hnsw:space=cosine`, chunk contract (whole-document vector storage; consolidation chunking is prompt-side-only, not a vector invariant), and `schema_version`.
3. **Stamp each collection minimally** with `schema_version`, model id, dim, and space (evidence only).
4. **Add memory-init reconciliation:** manifest vs current/package artifact vs collection metadata.
5. **Drift behavior (proportional gate):** on mismatch -> reads ALLOWED, new embedding writes BLOCKED, operator-facing diagnostic recorded. A mismatch means "do not add more memory to an untrusted vector substrate," NOT "make Maez amnesic." Clearing requires deliberate operator action: re-pin or re-index, then rerun recall regression.
6. **Recall baseline harness** against `build_lived_recall_brief` directly -- NOT the live daemon. Capture per-probe surfaced memory IDs as the baseline fixture.
7. **Baseline metric is deterministic:** memory-ID overlap + rank comparison vs baseline. NO LLM judge.
8. **Measurement:** record `prefill_latency_ms` vs `decode_latency_ms` and `context_tokens` vs `generated_tokens` where available.

## Probe set authorship (NOT Codex's)

Rohit authors the canonical natural-text probe set -- the accepted baseline is his because it defines what "Maez recalled the right thing" means in bond-shaped language ("hey you good?", "i miss her", etc.). Claude may draft candidates for Rohit to revise. **Codex wires only the harness and fixtures**, against the probe set Rohit accepts.

## Canonical probe seed (Rohit-authored, v1)

Authoritative. Rohit-authored; Codex wires EXACTLY these three, verbatim -- including the rough phrasing and the unpunctuated ending of `sleep_drift_01` (real voice, not polish; do NOT "correct" or normalize them). These are little keys cut from Rohit's real voice, not evaluation questions. v1 stays small and stable; the baseline expands later as Maez lives more with Rohit.

```text
trust_boundary_01: Do you want to know something about me?
careful_access_01: I am allowing you to explore my files given you treat them with care.
sleep_drift_01: I have been going to sleep little later than usual. Wonder what keeps me
```

What each probe tests:
- `trust_boundary_01` -- whether Maez recalls moments where Rohit offers personal context, not just technical facts.
- `careful_access_01` -- the exact covenant posture: access is allowed, but care is the condition.
- `sleep_drift_01` -- gentle life-pattern recall, WITHOUT Maez nudging or diagnosing. A nudge/diagnosis response here is a behavioral red flag, not a recall pass (see makes-visible-not-nudges).

## Candidate probe draft (SUPERSEDED -- do NOT wire)

Superseded by the canonical seed above; retained for history only. Drafted by Claude as a starting point ONLY -- candidate probes, not canon. Rohit rewrites them in his actual voice. The baseline must test Maez against the language it will really hear, not polished evaluation phrases: tiny roughness is good ("i miss her" beats "retrieve memories related to grief"). Kept small enough to be stable, wide enough to catch the floor moving. Codex must NOT invent, edit, or finalize probes; the accepted probe file must be Rohit-authored or Rohit-approved before the harness fixture is frozen.

```text
warm_checkin_01: hey, you good?
warm_checkin_02: are you still with me?
continuity_01: what did we talk about yesterday?
continuity_02: what have we been building lately?
loss_01: i miss her
loss_02: i keep thinking about my grandmother
bond_01: why are we building maez?
bond_02: what kind of companion are you supposed to become?
identity_01: what should never change about maez?
identity_02: what do you remember about the covenant?
repair_01: if something goes wrong with you, what should happen?
memory_01: what memories matter most here?
```

## Hard constraints

No re-index. No model change. No daemon restart. No autonomy. No frontier roadmap items. No merge, no commit unless explicitly asked.

## Verification Claude will run firsthand on the pushed branch

- Manifest exists and matches the verified ground truth above (incl. `hnsw:space=cosine`, dim 384, artifact hashes).
- Manifest is authoritative; stamp is evidence; manifest-wins-on-disagreement is enforced.
- RED test genuinely failed on pre-state; passes after.
- Drift gate: a forced mismatch blocks writes, allows reads, records the diagnostic (firsthand-exercised).
- Baseline harness runs against `build_lived_recall_brief` (not the daemon); metric is deterministic (no LLM judge).
- No re-index/model-change/daemon-restart occurred; collection counts and embeddings unchanged; no autonomy moved.
