# Handoff -> Codex: Local Model Stack Refresh v0

## Job

Build the refresh rail that keeps Maez's local model stack current without disturbing the live brain/judge by default.

## Current facts

- Main brain: `:8080` / `qwen36-27b`.
- Judge: `:8081` / `maez-judge`.
- Vision: absent; `screen_perception.py` must point to `:8082`.
- Current free VRAM snapshot: about 3975 MiB. Treat this as a snapshot, not proof of always-on fit.

## First candidate

Provision candidate artifacts for `Qwen/Qwen3-VL-4B-Instruct-GGUF`:

- `Qwen3VL-4B-Instruct-Q4_K_M.gguf`
- `mmproj-Qwen3VL-4B-Instruct-Q8_0.gguf` unless the F16 projector is intentionally chosen and VRAM allows it.

Pin source URLs and record hashes. The model GGUF is not currently on disk; only an older loose F16 projector exists.

## Owner breaths

Codex prepares files, tests, and service text. Rohit authorizes downloads, starts/stops user services, restarts Maez, and admits any live model.

## Witness order

1. Verify latest or candidate `llama.cpp` side-by-side.
2. Start `llama-vision.service` on `:8082`.
3. Verify `/v1/models` exposes `maez-vision`.
4. Run a tiny image smoke.
5. Run Full Lens witness through `observe()`.
6. Measure VRAM after load and after real image inference.
7. Only then consider judge retirement benchmark.
