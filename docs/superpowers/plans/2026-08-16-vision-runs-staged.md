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

| Candidate | Weights + mmproj | Measured resident | Fits beside Maez? |
|---|---|---|---|
| LFM2.5-VL-450M | 210 MB + 99 MB | ~850 MB | yes |
| MiniCPM-V-4.6 | 505 MB + 695 MB | **~1.68 GB** | yes, but see below |
| LFM2.5-VL-1.6B | 664 MB + 557 MB | not yet measured | probably |
| Qwen3VL-4B-Instruct | 2.4 GB + 433 MB | not yet measured | **no** |

**Measured, and it changes the recommendation.** MiniCPM-V-4.6 loaded
and served cleanly (`/health` ok, `loaded multimodal model`) — but it
took free VRAM from 2,769 MiB down to **1,093 MiB**. llama.cpp also
warned `failed to fit params to free device memory: n_gpu_layers
already set by user to 999, abort` — it proceeded, but that is the
runtime saying the fit was not comfortable.

Leaving Maez's brain with ~1 GB of headroom is an avoidable risk, and
specifically so: the brain's allocation is mostly static (KV cache is
preallocated at load), **but the one documented failure mode for this
exact configuration is its VRAM growing under long context** — that is
the first symptom in issue #23371, Run B below. Eating the remaining
headroom while that is unresolved courts the very thing we have not
tested yet.

**Revised recommendation: run every bake-off candidate in a window with
Maez's brain stopped**, not alongside. It costs nothing extra — the
window is already needed for Qwen3VL-4B and for Run B — and it removes
a live-system risk in exchange for scheduling, which is the right
trade. The "runs alongside" column stays for the record, not as a plan.

The harness judges one candidate at a time and writes one receipt per
candidate, so splitting across sittings is the same experiment, not a
broken one.

### Correction to something said earlier in this thread

MiniCPM-V-4.6 was pitched as a candidate that would stop the bake-off
"answering a question two months stale." **That framing was wrong.**
Its GGUF repos (`openbmb/MiniCPM-V-4.6-gguf`,
`ggml-org/MiniCPM-V-4.6-GGUF`) were last updated 11-19 May 2026 —
*before* the 6 June design that chose the current three. It was
available and simply not picked; that June doc's Tier C listed
InternVL3-2B and SmolVLM2-2.2B instead.

It may still be the better candidate — its header reads
`general.architecture = qwen35`, 24 blocks, 262k context, and it
carries a disproportionately large vision encoder for its size (695 MB
mmproj against 505 MB of weights), which is consistent with the claim
that it punches above its class on OCR. But it should be added because
it might win, not because it is new. It isn't.

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

Same shape for the other three, all inside the window:

| Label | Model | mmproj |
|---|---|---|
| `lfm-1.6b` | `vision/LFM2.5-VL-1.6B-Q4_0.gguf` | `vision/mmproj-LFM2.5-VL-1.6b-Q8_0.gguf` |
| `minicpm-v-4.6` | `vision/MiniCPM-V-4.6-Q4_K_M.gguf` | `vision/mmproj-MiniCPM-V-4.6-Q8_0.gguf` |
| `qwen3vl-4b` | `vision/Qwen3VL-4B-Instruct-Q4_K_M.gguf` | `vision/mmproj-Qwen3VL-4B-Instruct-Q8_0.gguf` |

All four candidate files are on disk and the two smallest are proven to
load and serve. Nothing further needs fetching for Run A.

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

---

## Run C — Qwen3.8-27B, the current form of the June "unified brain"

**Staged and verified. Runs only after Run B, and only if Run B passes.**

### Downloaded and verified, 2026-08-16

* `models/llamacpp/qwen38/Qwen3.8-27B-UD-Q4_K_XL.gguf` — 17 GB
* `models/llamacpp/qwen38/mmproj-F16.gguf` — 885 MB

Both from `unsloth/Qwen3.8-27B-GGUF`, the same publisher as the running
brain. Headers verified rather than trusted: model reads
`general.name = Qwen3.8-27B` with
`base_model.0.repo_url = huggingface.co/Qwen/Qwen3.8-27B`; the mmproj
reads `architecture = clip`, same name and repo_url,
`has_vision_encoder = True`, `projector_type = qwen3vl_merger`,
27 vision blocks.

### The runtime risk is smaller than expected

Compared against the running brain file directly:

| | Qwen3.6-27B (running) | Qwen3.8-27B (staged) |
|---|---|---|
| `general.architecture` | `qwen35` | `qwen35` |
| tensor count | 866 | 866 |
| `block_count` | 65 | 65 |
| `context_length` | 262144 | 262144 |

**Structurally identical from llama.cpp's point of view.** b9596 already
serves this architecture every day. So the "runtime upgrade" leg of the
June blast-radius objection does not apply to Qwen3.8 either — it is
very likely a drop-in at the loader level. That is a strong signal, not
a guarantee: it must still be witnessed loading before anything is
claimed.

### Protocol

Identical to Run B, substituting the two `qwen38/` paths and using
alias `qwen38-27b-vision` on port **8085**. Measure the same three
symptoms, plus one more: whether MTP works at all on this checkpoint
(`--spec-type draft-mtp` assumes an MTP-capable file — the running
brain uses a purpose-built MTP variant, and the staged Qwen3.8 file is
the plain UD quant, so **expect to test it without MTP first** and
treat MTP support as a separate question).

### What this is, and is not

This is the current form of the option the 6 June design deferred:
Maez's own brain becoming the thing that sees. It cuts across the
vision organ's existing design, which assumes sight arrives as a
separate small model that must earn admission through Slice 9.

It is an architecture decision, not maintenance. It should be its own
conversation with the owner, it must not ride in on the back of a
bake-off, and nothing here should be read as recommending it. The
files are staged so the question can be answered with measurements
instead of opinions.

---

## State on disk, and nothing running

No candidate server, no hand-run brain. VRAM is back to normal with
Maez's brain the only large resident. Disk went 339 GB free to 319 GB.

Staged files, all inert until something loads them:

| Path | Size | For |
|---|---|---|
| `models/llamacpp/mtp/mmproj-F16.gguf` | 885 MB | Run B |
| `models/llamacpp/vision/MiniCPM-V-4.6-Q4_K_M.gguf` | 505 MB | Run A |
| `models/llamacpp/vision/mmproj-MiniCPM-V-4.6-Q8_0.gguf` | 695 MB | Run A |
| `models/llamacpp/qwen38/Qwen3.8-27B-UD-Q4_K_XL.gguf` | 17 GB | Run C |
| `models/llamacpp/qwen38/mmproj-F16.gguf` | 885 MB | Run C |

`models/` is gitignored, so none of this enters the repository.

## What still blocks each run

* **Run A** — one owner decision about frame-003 at `full_640`, plus a
  window (revised: all candidates should run with Maez stopped).
* **Run B** — a window. Nothing else.
* **Run C** — Run B passing first, then the same window.

One window covers all three if taken in order: A, then B, then C only
if B is clean.
