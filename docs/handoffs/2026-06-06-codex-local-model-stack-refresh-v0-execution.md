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

## Owner-run candidate commands

These commands are a runbook, not autonomous execution. Rohit decides when to run each.

### Download and verify candidate artifacts

Target directory:

```bash
mkdir -p /home/rohit/maez/models/llamacpp/vision
```

Candidate files:

```text
https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct-GGUF/resolve/main/Qwen3VL-4B-Instruct-Q4_K_M.gguf
https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct-GGUF/resolve/main/mmproj-Qwen3VL-4B-Instruct-Q8_0.gguf
```

After download, record:

```bash
sha256sum /home/rohit/maez/models/llamacpp/vision/Qwen3VL-4B-Instruct-Q4_K_M.gguf
sha256sum /home/rohit/maez/models/llamacpp/vision/mmproj-Qwen3VL-4B-Instruct-Q8_0.gguf
```

### Runtime support probe

```bash
/home/rohit/llama.cpp-release/llama-b9124/llama-server --help | rg -- '--mmproj|--spec-type|mtp'
```

If `b9124` cannot load the candidate or lacks required support, build latest llama.cpp side-by-side under:

```text
/home/rohit/llama.cpp-release/llama-<commit>/
```

Do not overwrite `llama-b9124`.

### Render service template

```bash
cd /home/rohit/maez
.venv/bin/python -B scripts/model_refresh.py --render-vision-service \
  --runtime /home/rohit/llama.cpp-release/llama-b9124/llama-server \
  --model-path /home/rohit/maez/models/llamacpp/vision/Qwen3VL-4B-Instruct-Q4_K_M.gguf \
  --mmproj-path /home/rohit/maez/models/llamacpp/vision/mmproj-Qwen3VL-4B-Instruct-Q8_0.gguf \
  --alias maez-vision \
  --port 8082 \
  --ctx-size 4096
```

Write the rendered unit to:

```text
/home/rohit/.config/systemd/user/llama-vision.service
```

### Owner breath: start vision service

```bash
systemctl --user daemon-reload
systemctl --user start llama-vision.service
curl -s http://127.0.0.1:8082/v1/models
```

The `/v1/models` response must expose `maez-vision`; otherwise stop and fix alias/config before touching Maez.

### VRAM measurements

Record three snapshots:

```bash
nvidia-smi --query-gpu=name,memory.total,memory.used,memory.free --format=csv,noheader
```

1. before starting `llama-vision.service`;
2. after `/v1/models` succeeds;
3. after a real image inference.

Do not call the service "always-on fit" from load alone. Fit means load plus real image inference plus normal daemon coexistence.
