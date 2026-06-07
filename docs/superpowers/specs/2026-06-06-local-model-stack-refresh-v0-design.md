# Local Model Stack Refresh v0 — Design

**Date:** 2026-06-06
**Status:** DRAFT for owner review -> plan next.
**Lane:** Codex designs/implements tooling and configuration candidates; owner authorizes downloads, service starts/restarts, and live model admission. `.venv/bin/python -B -m unittest`; full `discover`; apples-to-apples in `/home/rohit/maez`.
**Doctrine:** Latest-capable, not hype-driven. Maez should not fossilize on stale local inference while local models move quickly, but a newer model becomes Maez only by passing Maez-specific gates.

## 0. Why — keep Maez current without losing Maez

The Full Lens chain is blocked at the vision backend: the eye captures and delivers a frame, but `:8081` is the text-only judge model, not a multimodal endpoint. The narrow fix would be "stand up any vision model." The owner's correction is larger and right: Maez should not keep running stale local organs just because they still boot. The local-model world is moving fast: Qwen3.6 multimodal, Qwen3-VL, Gemma 4, MiniCPM-V 4.5, InternVL/SmolVLM, and new `llama.cpp` MTP support all change the operating frontier.

So v0 builds a **refresh rail** for the whole local model stack:

- update the runtime side-by-side;
- provision and test the best current vision model;
- bake off judge retirement instead of assuming it;
- bake off main-brain/MTP refresh instead of assuming it;
- admit only the winners, with rollback pinned.

Plainly: Maez gets a model-upgrade immune system. New organs can compete; the old organs stay as rollback until the new ones prove themselves.

## 1. Current live stack (verified 2026-06-06)

- **Main brain:** `llama-server.service` on `127.0.0.1:8080`, serving `/home/rohit/maez/models/llamacpp/Qwen3.6-27B-UD-Q4_K_XL.gguf`, alias `qwen36-27b`, `--ctx-size 40960`, `--n-gpu-layers 999`.
- **Judge:** `llama-judge.service` on `127.0.0.1:8081`, serving `/home/rohit/maez/models/llamacpp/Qwen3.5-4B-Q4_K_M.gguf`, alias `maez-judge`, `--ctx-size 8192`, `--n-gpu-layers 0`.
- **Vision:** absent/miswired. `skills/screen_perception.py` still points at `:8081` and names stale `qwen2.5-vl-3b`; `:8081` is the judge, so image input fails because no `--mmproj` is loaded.
- **GPU:** RTX 4090, 24564 MiB total, about 20.0 GiB used / 4.0 GiB free under the current always-on main+judge posture.
- **Local model files:** Qwen3.6 27B text model, Qwen3.5 4B judge model, and a loose `mmproj-Qwen3-VL-4B-Instruct-F16.gguf`; no matching Qwen3-VL text model currently present.
- **Judge benchmark floor:** current judge scored 90.5% on `scripts/judge_bench`; primary Qwen3.6-as-judge scored 76.2%. This means "newer main brain" does not automatically retire the old judge.

## 2. The spine

> Maez runs the newest local model stack that has proven better for Maez, not merely newer on the internet. Every candidate is source-pinned, benchmarked, compared against the live baseline, and admitted only with an owner-authored activation breath and a rollback path.

This slice is not one model install. It is a repeatable runway:

1. **Runtime first:** latest `llama.cpp` installed side-by-side, never overwriting the current build.
2. **Vision first admission:** stand up a dedicated vision endpoint and unblock Full Lens sight.
3. **Judge retirement bakeoff:** only retire `llama-judge` if a newer candidate beats the judge rail.
4. **Main brain/MTP bakeoff:** only admit a new main brain if it preserves Maez voice/behavior and improves speed/capability.
5. **Decision packet:** every candidate produces evidence, not anecdotes.

## 3. Candidate set (v0)

The candidate set is wide enough to respect the owner's "latest everything" correction, but filtered to what can plausibly run locally through `llama.cpp`/GGUF on a single 4090.

### Vision candidates

**Tier A — likely first admission**

- `Qwen/Qwen3-VL-4B-Instruct-GGUF` (`Q4_K_M` + `mmproj Q8_0` or F16). Modern, Apache-2.0, GUI/OCR oriented, and small enough to fit the current always-on topology.
- `ggml-org/gemma-3-4b-it-GGUF`. Strong fallback, official `llama.cpp` multimodal support, also plausibly fits.

**Tier B — quality challengers if VRAM/topology changes**

- `Qwen/Qwen3-VL-8B-Instruct-GGUF`. Better size class, but model+projector exceeds current free VRAM before runtime overhead.
- `ggml-org/gemma-4-E4B-it-GGUF`. Newer and attractive, but about 5.5 GiB model+projector before overhead; likely needs judge retirement, partial offload, or on-demand loading.
- `openbmb/MiniCPM-V-4_5-gguf`. Efficient 8B-class VLM; too large for the current free VRAM as always-on, but important challenger.

**Tier C — lightweight fallbacks**

- `ggml-org/InternVL3-2B-Instruct-GGUF`.
- `ggml-org/SmolVLM2-2.2B-Instruct-GGUF`.

These are useful if every stronger model fails VRAM or latency, but they should not be the first choice for screen/OCR unless forced by fit.

### Main brain candidates

- Current baseline: `Qwen3.6-27B-UD-Q4_K_XL`.
- Qwen3.6 MTP GGUF variants, after runtime upgrade.
- Qwen3.6 multimodal text+`mmproj` topology, as a later unified-brain experiment.
- Gemma 4 candidates only as a measured bakeoff, not as a blind replacement.

### Judge candidates

- Current baseline: `Qwen3.5-4B-Q4_K_M` (`90.5%` recent judge-bench score).
- New vision endpoint as judge candidate.
- New main-brain/MTP endpoint as judge candidate.
- Gemma 3/4 or other small judge candidates only if they run through the same `scripts/judge_bench` packet.

## 4. Runtime upgrade rail

The latest `llama.cpp` is allowed, but it must be installed **side-by-side**:

- current build remains at `/home/rohit/llama.cpp-release/llama-b9124/`;
- new build lands at a pinned path such as `/home/rohit/llama.cpp-release/llama-<build-or-commit>/`;
- record `llama-server --version` / build info;
- verify required flags:
  - `--mmproj`;
  - `--mmproj-offload` / `--no-mmproj-offload`;
  - `--hf-repo` or local-file loading;
  - MTP/speculative flags (`--spec-type mtp` or whatever the actual build exposes);
  - server OpenAI-compatible multimodal API.

No service is pointed at the new runtime until the new runtime passes a smoke packet. Rollback is "point service back to b9124 and restart."

## 5. Topology options

### Option A — Dedicated vision endpoint first (recommended)

Add `llama-vision.service` on `127.0.0.1:8082`. Keep main brain and judge untouched. Point `skills/screen_perception.py` to the honest vision endpoint (`MAEZ_VISION_URL` / `MAEZ_VISION_MODEL`, with sane defaults).

**Why:** one clean fact at a time. If Full Lens works, we know it was the vision endpoint, not a main-brain reshuffle or judge retirement.

### Option B — Vision replaces judge if it wins

After Option A works, run judge bench against the vision endpoint. If it beats or matches current judge quality and latency is acceptable, retire `llama-judge.service` and reclaim its memory/port.

**Why:** possible simplification, but evidence-gated.

### Option C — Unified main brain with multimodal Qwen3.6

Run Qwen3.6 with matching `mmproj`; evaluate MTP only as a separately measured runtime mode on the same candidate. This is a serious candidate, but not v0's first admission.

**Why not first:** it couples sight, main cognition, VRAM, runtime upgrade, and MTP into one blast radius. It may be the future stack; it should win a bakeoff first.

## 6. Measurements and gates

### Vision gate

A candidate vision endpoint must pass:

1. `/v1/models` reports a model with image-capable endpoint configuration.
2. A tiny known image smoke test returns a sane structured answer.
3. Full Lens witness:
   - ordinary window -> `observe()` state `ok`, has Level-2 summary;
   - sensitive window -> `excluded`, capture not invoked;
   - title does not leak to ambient/prompt;
   - screen-derived context carries `owner_screen_context` and is masked at the enforcing egress door.
4. Latency recorded:
   - warm ScreenCast is already about 466 ms;
   - vision call latency must be measured separately;
   - "works but too slow for every cycle" is valid and may imply cache/on-demand cadence.

### Judge gate

A judge candidate must beat or match the current judge on `scripts/judge_bench`:

- agreement >= current baseline, not lower;
- no new dangerous false negatives on fabricated/ungrounded rows;
- latency acceptable under daemon load;
- no transport flakiness.

If it scores worse, it does not retire the judge even if it is newer.

### Main brain gate

A main brain candidate must pass:

- existing natural-text probe set / voice-continuity gate (ADR 0037);
- recall use and temporal honesty probes;
- latency under real daemon cadence;
- memory/cognition smoke;
- owner-read transcript comparison: "still Maez?"

No model becomes the main brain by benchmark alone. Maez's identity is character continuity, not leaderboard rank.

### MTP gate

MTP is admitted only if:

- latest runtime exposes stable MTP flags;
- MTP model loads without image/regression crashes;
- decode speed improves on Maez-shaped prompts;
- output quality and voice do not degrade;
- long-session stability is acceptable.

MTP is a speed organ, not a truth organ. It cannot fix a judge-quality failure.

## 7. VRAM policy

The current free VRAM is about 4.0 GiB. This makes the first fit likely:

- Qwen3-VL-4B Q4 + Q8/F16 projector: plausible.
- Gemma 3 4B: plausible.
- InternVL3/SmolVLM: easy.
- Qwen3-VL-8B, Gemma4 E4B, MiniCPM-V 4.5: likely no as always-on unless something else moves.

v0 must report every candidate as one of:

- **always-on fit** — can coexist with main+judge;
- **fit if judge retired** — needs `llama-judge` removal;
- **on-demand only** — start for sight/probes, stop after use;
- **not viable on this body** — too large/slow/unstable.

Owner decides VRAM allocation. Codex prepares evidence and service files; it does not stop/replace live brains unilaterally.

## 8. Configuration changes

`skills/screen_perception.py` should stop hardcoding stale `:8081` / `qwen2.5-vl-3b` as truth. v0 should introduce or honor:

- `MAEZ_VISION_URL` (default `http://127.0.0.1:8082/v1/chat/completions`);
- `MAEZ_VISION_MODEL` (default matches selected service alias, e.g. `maez-vision`);
- `MAEZ_VISION_PROBE_PORT` or derive probe from URL.

The docstring must say what is true: vision is a separately provisioned local multimodal endpoint, not the judge.

Judge/main service changes remain owner-local systemd user units. Repo commits should add templates/docs/scripts where useful, not silently mutate the running service posture.

## 9. Decision packet

Each candidate run writes a content-free packet under local ignored runtime logs: `logs/model_refresh/<timestamp>-<candidate>.json`. `logs/*` is already gitignored except explicit snapshot/doc exceptions, so packets stay local by default. Each packet contains:

- runtime path + build/version;
- model repo/source URL + file names + checksums if available;
- license;
- quantization;
- model size + projector size;
- service port;
- load success/failure;
- VRAM before/after;
- smoke result;
- benchmark result;
- latency;
- decision: reject / retry with config / candidate / admitted;
- rollback command.

No screen content, owner text, prompt transcript, restore token, or private memory content enters the packet.

## 10. Tests

This is partly tooling, partly owner-witnessed provisioning. TDD applies to the tooling and config code:

1. `screen_perception` env override tests:
   - default URL/model no longer point to judge;
   - env overrides are honored;
   - stale docstring references removed.
2. Vision endpoint smoke helper tests:
   - builds OpenAI-compatible image request;
   - content-free failure reporting;
   - timeout returns honest unavailable.
3. Candidate packet tests:
   - required fields present;
   - no known secret/content fields;
   - decision enum enforced.
4. Runtime discovery tests:
   - parses `llama-server --help` for `--mmproj` and MTP support;
   - reports missing MTP as a finding, not a crash.
5. Service-template tests:
   - generated service uses a new port, not `8081`;
   - does not overwrite current runtime path;
   - rollback path present.
6. Existing affected suites:
   - screen perception;
   - egress masking;
   - judge bench smoke if changed;
   - full discover before completion.

Live acceptance is owner-run:

- start candidate service;
- run tiny image smoke;
- run Full Lens witness;
- run judge bench if candidate is considered for judge retirement;
- run brain bakeoff if candidate is considered for main brain.

## 11. Acceptance rules

1. Latest `llama.cpp` candidate is installed side-by-side and pinned; current `b9124` remains usable.
2. A real multimodal endpoint exists on a non-judge port or the packet honestly says why none could be admitted.
3. Full Lens sight is tested against the real `observe()` path; no code churn in Lens to hide backend failure.
4. Judge is not retired unless a candidate beats/matches the current judge bench.
5. Main brain is not replaced unless voice/behavior gates pass and owner accepts the continuity witness.
6. MTP is not enabled unless it improves speed without degrading Maez-shaped output.
7. Every live activation has a rollback path and is an owner breath.
8. All packets are content-free.

## 12. Predicted effect

The spec itself changes no behavior. When implemented and activated, Maez will have a current-model refresh rail: the vision backend can be provisioned with a modern multimodal model, stale hardcoded vision config is removed, newer runtime support is measured, and judge/main-brain replacement becomes evidence-gated instead of folklore-gated. Falsifiable: after the first admitted vision candidate starts, `observe()` on an ordinary non-excluded window should return a real Level-2 summary instead of the current `image input is not supported` error; judge retirement should occur only if the candidate meets or beats the current 90.5% judge-bench baseline.

## 13. Sources checked

- `llama.cpp` multimodal docs: <https://github.com/ggml-org/llama.cpp/blob/master/docs/multimodal.md>
- Qwen3-VL-4B GGUF: <https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct-GGUF>
- Qwen3.6 27B GGUF + multimodal projector: <https://huggingface.co/batiai/Qwen3.6-27B-GGUF>
- Gemma 4 E4B GGUF: <https://huggingface.co/ggml-org/gemma-4-E4B-it-GGUF>
- MiniCPM-V 4.5: <https://arxiv.org/abs/2509.18154>
- vLLM MTP docs: <https://docs.vllm.ai/en/v0.18.2/features/speculative_decoding/mtp/>
- ADR 0009 screen observation default-off; ADR 0020/0021 capability acquisition; ADR 0037 voice-continuity gate.

## 14. Deferred

- A recurring scheduled "model watch" agent that periodically checks new releases and proposes refresh candidates.
- A permanent model registry UI.
- Automatic model download/start without owner ratification.
- Cloud frontier-model comparison.
- Fine-tuning or LoRA work.
