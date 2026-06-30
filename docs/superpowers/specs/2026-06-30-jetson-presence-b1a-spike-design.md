# Real-Presence Jetson — B1a Pipeline Spike Design & Covenant Brief

**Date:** 2026-06-30. **Lane:** Claude drafts + covenant-reviews; Codex cross-lane reviews; owner runs the device witnesses. **Status:** DESIGN for sign-off (Codex direction-approved with 5 tightenings, folded in). **Scope:** a **standalone, non-live** technical spike that proves the on-device face-recognition pipeline (`SCRFD` detect + `ArcFace` embed, ONNX → TensorRT) runs on the Orin, distinguishes the owner from an empty frame, and is fast enough — **without touching Maez's live behavior.**

## Why
B1 (owner recognition) splits into **B1a (this: prove the muscle)** and **B1b (the covenant logic: real enrollment + decision rule + live `present`/`absent`)**. B1a de-risks the unproven technical part — TensorRT inference on the Orin, the install gap, the model/latency — so B1b's covenant-dense work builds on a *proven* pipeline. B1a **prints** results; it never POSTs, never changes host state, and the doorway keeps receiving B0's `unknown`.

## Locked decisions
- **Split B1a → B1b** (owner-approved). B1a is non-live and technical; B1b is the careful covenant slice.
- **Model path: SCRFD detector + ArcFace embedding (InsightFace), ONNX → TensorRT via `trtexec`** (owner-approved). Spike measures latency; fallback is embedding → MobileFaceNet if too slow (detector stays SCRFD).
- **Task 0 grounding:** Orin Nano, TensorRT 10.3 + `trtexec`, egress works, camera 1080p via `cv2.CAP_V4L2`+MJPG, install gap = `onnx` + `pycuda`/`cuda-python` + pip.

## Components (in `devices/jetson_presence/` package; source in repo, artifacts Jetson-local)
- **`models/manifest.json` + `setup_models.sh`** — the tracked manifest pins each model: `name, source_url, sha256, license, input_shape, expected_engine_path`. The script installs the gap, pulls the ONNX (verifying SHA256), and `trtexec`-compiles to engines. **`.onnx`/`.engine` are Jetson-local + gitignored; the manifest + script are the repo source of truth.**
- **`detector.py`** — thin TensorRT wrapper: frame → face boxes + score.
- **`embedding.py`** — thin TensorRT wrapper: face crop → identity vector.
- **`matcher.py`** — **pure logic** (host-unit-testable): two vectors → cosine distance; `distance < threshold` → match.
- **`spike.py`** — bounded harness (`--frames N`): V4L2 capture → detect → crop most-confident face → embed → compare to a **RAM-only owner reference** → print `match? / distance / per-stage latency`. **Prints only. No network, no emit.**

## Covenant rails (the 5 Codex tightenings + the inherited B0 rails)
**R1 — No live non-owner, ever.** B1a's "distinguishes" proof uses only: owner-present → match; empty/covered frame → no-match; and **random/synthetic vectors in `matcher.py` unit tests** → no-match. **No real non-owner face is captured, stored, or tested** — the non-owner-indistinguishable-from-empty proof belongs to B1b (decision-layer, mocked).

**R2 — Temporary owner reference is RAM-only by default.** The reference embedding is biometric: captured at process start, held in memory, discarded on exit. A `--keep-reference` flag may persist it **only** Jetson-local + gitignored + never redeployed; default is ephemeral.

**R3 — Model artifacts via tracked manifest.** Models are pinned by SHA256 + license + input shape + source URL in `manifest.json`; `setup_models.sh` verifies the hash on pull. Script + manifest in repo; `.onnx`/`.engine` out of repo (Jetson-local, gitignored).

**R4 — Engine sanity/parity, not just "trtexec succeeded."** The spike must prove the engine produces *sane* outputs (SCRFD's NMS heads are where TensorRT conversion breaks): **blank/no-face → no detection; owner → a detection + a stable embedding; and an ONNX-vs-TensorRT same-frame comparison in RAM** (the TensorRT engine's outputs must match the ONNX reference within tolerance). Conversion success without output parity is a fail.

**R5 — Structurally unable to POST.** A static/AST test asserts `spike.py` (and the spike path) imports no `requests`, no `emitter`, no `post_label`, and references no host URL/token. B1a is local-only **by construction**, not by promise.

**Inherited:** on-device only (models, engines, reference embedding never cross); **no-frame-write extends to crops** (frames *and* face crops stay in RAM, no `imwrite`/`VideoWriter`/sink — same structural guard as B0); not wired to the live emit (zero behavior risk); capture via `cv2.CAP_V4L2`.

## Witnesses
- **Device (owner-run):** the TensorRT engines load + infer on the Orin; owner-present → `match` (low distance), empty/covered → no-match; per-stage + total **latency** reported (validates SCRFD+ArcFace, or signals the MobileFaceNet fallback).
- **Engine parity (R4):** blank-frame sanity + owner-frame sanity + ONNX-vs-TensorRT same-frame parity in RAM.
- **Structural (host tests):** `matcher.py` cosine/threshold logic incl. random-vector no-match (R1); the no-POST static guard (R5); the no-crop-write guard.

## Testing shape
B1a's core (TensorRT inference) is **device-only** — it can't be meaningfully host-mocked. So: host tests cover `matcher.py` (pure logic, incl. synthetic-vector discrimination) + the structural guards (no-POST, no-crop-write); the **pipeline + parity + latency are witnessed on the device** by the spike harness. That is the honest nature of a hardware spike.

## Out of scope (→ B1b)
- The real owner-gated enrollment ceremony (B1a's reference is an ephemeral spike artifact, not the durable enrollment).
- The decision rule: the label-confidence composite, the reliable-observation-window input table, `present`/`absent`/`unknown` derivation.
- The occupancy-non-leak (decision-layer, mocked detector/embedding outputs).
- Wiring `present`/`absent` to the live emit through the doorway.

## Covenant compliance
- Boring classifier, not a VLM; the Jetson emits labels (here: prints a match result), never thoughts/descriptions ([[project_jetson_body_not_second_maez]]).
- Biometric minimization: reference RAM-only by default; no stored/tested non-owner face ([[feedback_third_party_autonomous_research_boundary]]).
- Witnessable, structural proofs (no-POST, no-crop-write, engine parity) over promises ([[feedback_witnessable_receipt_for_prompt_boundary]], [[feedback_static_code_trace_is_not_integration_witness]]).
- Supply-chain hygiene on pulled models ([[feedback_verify_provider_policy_before_build]] shape).

## Predicted effect
After B1a: we know — on the actual Orin — whether SCRFD+ArcFace via TensorRT can recognize the owner, at what latency, with verified engine parity, all proven locally with the owner's own (ephemeral) face and zero non-owner data, zero frames/crops written, and zero ability to affect Maez's live behavior. That answer (and the validated model + threshold + cadence) is what B1b's covenant slice builds on.
