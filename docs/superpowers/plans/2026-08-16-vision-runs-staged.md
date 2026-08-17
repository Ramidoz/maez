# Two staged runs — vision bake-off, and MTP+vision

2026-08-16. **STAGED, NOT RUN.** Both are prepared to the point where
the only thing missing is a decision or a window from the owner.
Everything mechanical is done and verified.

---

## Run A — the frozen-frame vision bake-off (Slice 8)

**Blocked on one owner decision. Not on machinery.**

### Verified working, 2026-08-15

* Corpus loads 3/3 (`load_frame_case` succeeds for all three frames).
* A candidate server starts, serves, and answers health — LFM-450M
  loaded in ~20s using ~850 MB, with Maez's brain untouched.
* The harness runs, reaches its scoring stage, and writes a receipt.

### The blocker, exactly

`local/vision_bench/labels/frame-003-terminal.json` — both of its
labels (`application_name`, `key_string`) are marked
`visible_in: ["full_1280", "active_native"]`. **Neither is marked
visible at `full_640`.** The harness derives three transforms
(`full_640`, `full_1280`, `active_native`), finds no label applicable
to `full_640` for that frame, and raises `labels_empty_for_transform`
(`core/vision_contract/frozen_frame.py:518`). The run refuses globally:
0 frames evaluated. Frames 001 and 002 are complete.

Receipt of the refused run:
`local/vision_bench/receipts/20260815T183247-10769457.json`

### The decision, which is the owner's alone

The corpus README is explicit — *"No model or AI lane may fill these
values… ruling 6: ground truth is human, never model
self-consistency."* So this is not a builder's edit. Two readings, and
only the owner can look at the frame and say which:

1. **The text IS legible at 640** and the box simply wasn't ticked.
   Fix: add `"full_640"` to both `visible_in` lists. Ten seconds.
2. **The text is NOT legible at 640** and the labels are correct. Then
   the *harness* is wrong to refuse the whole run: a frame where
   nothing is readable at a resolution is a legitimate measurement
   ("claim nothing here"), not a corpus defect. Fix: a harness change
   giving that case an honest third state instead of a global refusal.

**Do not resolve this by widening the harness to make the run pass.**
That is the pass-bucket-widening failure this repo has a standing rule
against. If reading (2) is right, the third state must be recorded as
its own outcome, not folded into success.

### Candidates and the VRAM ceiling

Free VRAM with Maez up: **~2.7-3.3 GB** of 24.5 GB, and it moves.
Measured holders, 2026-08-16:

| PID | What | GPU MiB |
|---|---|---|
| 2763 | the brain, Qwen3.6-27B MTP | 18,816 |
| 6219 | the judge, Qwen3.5-4B | 1,095 |
| 3091 | `gnome-remote-desktop-daemon` | 502 |
| 4714 | `snapd-desktop-integration` | 19 |

Two notes. The desktop daemons drift by several hundred MB depending
on session activity — which is why a reading taken an hour apart moved
by 580 MB — so plan against the LOW figure, not the high one. And the
judge holds ~1.1 GB despite running `--n-gpu-layers 0`: that is CUDA
context, not model weights, and it is a known-correct configuration
(the full-body audit already corrected one wrong "GPU contention"
diagnosis about this same process). Not to be touched to make room.

| Candidate | Weights + mmproj | Runs alongside Maez? |
|---|---|---|
| LFM2.5-VL-450M | 210 MB + 99 MB | yes — measured ~850 MB resident |
| LFM2.5-VL-1.6B | 664 MB + 557 MB | yes, comfortably |
| Qwen3VL-4B-Instruct | 2.4 GB + 433 MB | **no** — needs Maez's brain stopped |

The harness judges one candidate at a time and writes one receipt per
candidate, so splitting across sittings is the same experiment, not a
broken one.

### Exact commands (candidate 1 proven, others identical in shape)

```bash
# start a candidate on a free port (8084; 8080/8081/8083 are in use)
nohup /home/rohit/llama.cpp-release/llama-b9596-cuda13.2-sm89/llama-server \
  -m models/llamacpp/vision/LFM2.5-VL-450M-Q4_0.gguf \
  --mmproj models/llamacpp/vision/mmproj-LFM2.5-VL-450m-Q8_0.gguf \
  --alias vision-lfm-450m --host 127.0.0.1 --port 8084 \
  --ctx-size 4096 --n-gpu-layers 999 > /tmp/vision450.log 2>&1 &

curl -s http://127.0.0.1:8084/health          # expect {"status":"ok"}

.venv/bin/python -m scripts.vision_frozen_bench \
  --bench-root local/vision_bench \
  --candidate-label lfm-450m \
  --base-url http://127.0.0.1:8084 \
  --model vision-lfm-450m
```

Then the same with `LFM2.5-VL-1.6B-Q4_0.gguf` +
`mmproj-LFM2.5-VL-1.6b-Q8_0.gguf`, label `lfm-1.6b`; and
`Qwen3VL-4B-Instruct-Q4_K_M.gguf` + `mmproj-Qwen3VL-4B-Instruct-Q8_0.gguf`,
label `qwen3vl-4b` — that one only during a window with Maez stopped.

Kill each candidate when its run finishes; nothing should be left
holding VRAM.

### Open question, not yet answered

A newer candidate exists that fits the gap: **MiniCPM-V 4.6** (~1.3B,
reported to compete with 7B-class models on OCR and document
understanding — *unverified at source*). The three current candidates
were chosen in June. Adding a fourth costs one download and one run,
and would stop the bake-off from answering a question two months stale.
Owner's call.

---

## Run B — does the MTP + vision bug still bite?

**Blocked on a window with Maez's brain stopped. Nothing else.**

### Why this run exists

`docs/superpowers/specs/2026-06-06-local-model-stack-refresh-v0-design.md:111-115`
deferred the unified-brain option — a main brain that also sees — for
one recorded reason:

> **Why not first:** it couples sight, main cognition, VRAM, runtime
> upgrade, and MTP into one blast radius. It may be the future stack;
> it should win a bakeoff first.

Three of those five have since settled independently: the runtime
upgrade landed (b9596 + CUDA cutover), MTP is live, and VRAM is
measured. What remains is sight + cognition — and one new fact the June
decision did not have.

[llama.cpp issue #23371](https://github.com/ggml-org/llama.cpp/issues/23371)
reports that with Qwen3.6-27B MTP: long-context requests retain VRAM
after completion, and MTP+Vision accumulates enough residual pressure
that CLIP/mmproj initialisation fails with CUDA OOM, cascading into
restart loops. Filed May 2026 against build **9219**, went stale,
**closed as not planned**. Maez runs **b9596** — much newer — so
whether it still reproduces is genuinely unknown. Nobody fixed it; that
is not the same as it surviving.

### Prepared, 2026-08-16

The matching vision encoder is downloaded and verified as a genuine
pair for Maez's exact brain file:

* `models/llamacpp/mtp/mmproj-F16.gguf` — 885 MB, from
  `unsloth/Qwen3.6-27B-GGUF`, the same repo the running
  `Qwen3.6-27B-UD-Q4_K_XL.gguf` came from.
* GGUF header verified: `general.architecture = clip`,
  `general.name = Qwen3.6-27B`,
  `general.base_model.0.repo_url = huggingface.co/Qwen/Qwen3.6-27B`,
  `clip.has_vision_encoder = True`,
  `clip.projector_type = qwen3vl_merger`, `clip.vision.image_size = 768`.

### Protocol

The brain is `llama-server.service`, **user-scoped** systemd, with
`Restart=on-failure` (so a clean stop stays stopped; a crash restarts).
**The unit is not edited.** The test runs the same binary by hand with
the unit's own flags plus `--mmproj`, so rollback is "kill it, start
the service".

```bash
systemctl --user stop llama-server.service      # OWNER RUNS THIS
nvidia-smi --query-gpu=memory.free --format=csv,noheader   # expect ~24 GB

CUDA_VISIBLE_DEVICES=0 \
LD_LIBRARY_PATH=/home/rohit/llama.cpp-release/llama-b9596-cuda13.2-sm89:/usr/local/cuda-13.2/targets/x86_64-linux/lib \
/home/rohit/llama.cpp-release/llama-b9596-cuda13.2-sm89/llama-server \
  -m /home/rohit/maez/models/llamacpp/mtp/Qwen3.6-27B-UD-Q4_K_XL.gguf \
  --mmproj /home/rohit/maez/models/llamacpp/mtp/mmproj-F16.gguf \
  --alias qwen36-27b-mtp-vision --host 127.0.0.1 --port 8085 \
  --ctx-size 40960 --parallel 1 --n-gpu-layers 999 -fa on \
  --cache-type-k q4_0 --cache-type-v q4_0 \
  --spec-type draft-mtp --spec-draft-n-max 3 --kv-unified -fit off
```

Note the port is **8085**, not 8080 — nothing points at it, so a
half-working brain cannot be picked up by the live daemon by accident.

### What to measure — the issue's three symptoms, in order

1. **Does it even load?** Brain + mmproj together at 40k context. If it
   OOMs on load, that is the answer and the run stops there.
2. **VRAM retention.** Record free VRAM at idle. Send a long-context
   request (~35-40k tokens). Record VRAM during, and again 60s after
   completion. The issue predicts it stays elevated instead of
   returning to idle.
3. **mmproj survival under pressure.** After the long request, send an
   image request. The issue predicts CLIP/mmproj init fails with CUDA
   OOM once residual pressure has built. Repeat the long-request →
   image cycle three times; the issue describes it as accumulating.

Record every number. A clean pass on all three is a real result and
reopens the unified-brain option; a failure at any stage is equally
real and closes it until upstream moves.

### Rollback

```bash
kill <pid>                                      # the hand-run server
systemctl --user start llama-server.service     # OWNER RUNS THIS
curl -s http://127.0.0.1:8080/health            # brain is back
```

Nothing else changes. No unit edited, no model pointer moved, no
config touched.

### The bigger question this feeds

If MTP+vision holds on b9596, the same test should then be run against
**Qwen3.8-27B** — released 2026-08-14, Apache-2.0, 28B dense,
image-text-to-text, aimed at 24 GB consumer cards, GGUFs already
published by unsloth / ggml-org / bartowski. That is the current form
of the June "unified brain" option, and it would make Maez's own brain
the thing that sees.

That is an architecture decision, not maintenance, and it cuts across
the vision organ's existing design (which assumes sight arrives as a
separate small model that must earn admission). It should be its own
conversation, and it should not ride in on a bake-off.

---

## Nothing is running

No candidate server, no hand-run brain. VRAM is back to its normal
state with Maez's brain the only resident. The only change on disk is
the downloaded `mmproj-F16.gguf`, which is inert until something loads
it.
