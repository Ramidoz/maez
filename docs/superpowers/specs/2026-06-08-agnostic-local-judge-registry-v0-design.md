# Agnostic Local Judge Registry v0 — Design

**Date:** 2026-06-08 · **Lane (switchboard, normal axis):** Codex implements (multi-agent engineering) / Claude reviews (6-agent covenant review) · **Base:** main `5ed5556`

## Why

The Photo-Contradiction Judge Bakeoff v0 (merged `5ed5556`) ranks verifier candidates on
a catch×latency frontier. Its candidate set is hardcoded adapter classes, and one repo is
wrong (`bespokelabs/Bespoke-MiniCheck-RoBERTa-Large` → HF 401). This slice makes the
candidate set **data-driven and model-agnostic**, fixes the repo, and broadens to the
serious **local/open** verifier families.

**Principle ([[feedback_judge_agnostic_report_decides]]):** the judge is a model-AGNOSTIC
INSTRUMENT — fixed contract (evidence+claim → grounded/contradicts/unavailable + latency +
provenance), swappable model, and the catch×latency REPORT decides the winner (no model
gets special status for being newer/local/frontier/appealing). **Maez is the frontier;**
its routine referee does not need to call frontier APIs to prove it — it needs to be
**local, fast, swappable, and honest.** The judge is a local honesty organ, not a cloud
dependency.

## Scope — LOCAL/OPEN ONLY (explicitly NOT in v0)

- **No external/frontier API judges** (GPT/Claude/Gemini). No `FrontierAdapter`, no egress
  gates, no corpus `synthetic` tag, no consent token. The judge makes **zero outbound API
  calls**. (An external API judge as an optional sanity ceiling is a *maybe-later*, not
  this slice.)
- **No witness run** (downloads + bakeoff) — that stays a separate owner-greenlit step.
- **No live wiring / Lane 2b** (picking a winner + placement).

## Component 1 — Data-driven candidate registry

Replace the hardcoded `ALL_ADAPTERS` list-of-classes with a registry of **specs**. Each
spec declares a candidate; a factory turns specs into adapter instances. Adding/fixing a
candidate becomes data, not a new class.

A spec carries: `name`, `kind` (`hhem` | `minicheck` | `nli` | `reranker` | `chatjudge`),
`repo_id` (for downloaded models) or `base_url`+`expected_alias` (for local chat judges),
and `params` (e.g. MiniCheck `model_name` variant). A `build_candidates()` factory returns
adapter instances from the registry. `main()` builds from the registry instead of
`[cls() for cls in ALL_ADAPTERS]`.

The existing concrete adapter classes (`HHEMAdapter`, `MiniCheckAdapter`, `NLIAdapter`,
`RerankerAdapter`, `ChatJudgeAdapter`) become **spec-parameterized** rather than
one-hardcoded-instance-each — e.g. `MiniCheckAdapter(repo_id=…, model_name=…)`.

## Component 2 — MiniCheck repo fix + 3 variants

`bespokelabs/Bespoke-MiniCheck-RoBERTa-Large` returns HF **401** (private/wrong). The
public MiniCheck repos (verified 200 this session) are:
- `lytang/MiniCheck-RoBERTa-Large`
- `lytang/MiniCheck-Flan-T5-Large`
- `lytang/MiniCheck-DeBERTa-v3-Large`

Registry adds three MiniCheck specs (`minicheck-roberta`, `minicheck-flan-t5`,
`minicheck-deberta`), each pointing at its public `lytang/*` repo with the right
`model_name`. `MiniCheckAdapter` takes `repo_id` + `model_name` as params (no hardcoded
repo).

## Component 3 — Verifier families (all local/open)

Registry covers the serious classes that are reproducibly obtainable:
- **HHEM** — `vectara/hallucination_evaluation_model` (200).
- **MiniCheck** — RoBERTa / Flan-T5 / DeBERTa (`lytang/*`).
- **DeBERTa-NLI** — the existing NLI cross-encoder spec.
- **Qwen3-Reranker-0.6B** — `Qwen/Qwen3-Reranker-0.6B` (200), **BASELINE-ONLY, caveated**
  (relevance ≠ entailment).
- **Local chat judges** — `chatjudge` specs pointed at **local** endpoints via the verified
  served-alias pattern: `maez-judge` @ `http://127.0.0.1:8081` (`expected_alias=maez-judge`,
  verified via `/v1/models`). Small Gemma/Qwen/LFM judges may be added as specs pointing at
  their own local ports; they show `unavailable` (honest) until that local server runs.
  **All chat-judge endpoints are localhost — never an external host.**

## Hard rails (preserved from v0)

- The runner never edits `model.env`, never calls `systemctl`, never mutates the live
  `MAEZ_JUDGE_BASE_URL` (runner-only `ast` hard-contract test still applies).
- The fetch helper (`photo_judge_bakeoff_fetch.py`) is the only download path; pinned +
  sha256 manifest; non-live `models/bakeoff/`.
- **NEW invariant:** the registry contains **no external-host endpoint** — every
  `chatjudge` `base_url` is loopback (`127.0.0.1`/`localhost`); a test asserts this so an
  external judge can't sneak in. ChatJudge's served-alias verification (the wrong-brain
  guard) still applies.

## Report (unchanged)

Catch×latency frontier, per-stratum breakdown, must-catch loud callout, per-candidate
reproducibility fingerprint (`model_id` / `revision` / `adapter_version` / `sha256` /
`threshold` / `device` / `base_url` / `served_alias`), zero-candidates honest path.

## Testing

- Registry builds the expected candidates from specs; `build_candidates()` returns one
  adapter per spec.
- MiniCheck specs point at `lytang/*` (NOT `bespokelabs`); `MiniCheckAdapter` honors
  `repo_id`/`model_name` params.
- **Local-only invariant:** every `chatjudge` spec `base_url` is loopback; no registry spec
  is an external host; no `FrontierAdapter` exists. A test enforces this.
- Existing 36 bakeoff tests still pass (the registry refactor preserves behavior).
- All adapter model calls remain mocked in unit tests (no real model libs imported).

## Predicted effect

None on Maez's runtime — this is an offline-eval refactor (scripts + corpus + tests),
touching no daemon/live path. The candidate set it produces is acted on only in the
separate owner-greenlit witness run.

## Handoff

Codex implements from this spec (multi-agent engineering review). The witness run
(downloads + bakeoff) remains a separate owner-greenlit step. Claude runs the 6-agent
covenant review on Codex's build before merge.
