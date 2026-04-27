# Maez training pipeline — Session 11t

Isolated QLoRA fine-tuning substrate for gemma-4-26B-A4B. Built in
Session 11t. Does NOT run in production — the daemon keeps calling
llama-server on port 8080 throughout.

**Training happens on a rented GPU, not the local RTX 4090.** The
local 4090 (24 GB) cannot fit gemma-4-26B-A4B in 4-bit for training —
all MoE experts must stay GPU-resident during gradient computation,
which exceeds 24 GB. Training runs on a RunPod H100 PCIe 80 GB pod
with a persistent volume. See `remote/README_REMOTE.md` for the
step-by-step runbook.

**What lives locally:** the extractor (reads ChromaDB + fast_log),
the adapter→GGUF converter (wraps llama.cpp's tool), and the smoke
eval harness (hits local llama-server). Those run on the local venv.

**What runs remotely:** `train_lora.py` (unsloth QLoRA trainer).
Same script, same arguments, different host.

## Layout

```
training/
├── .venv/                       isolated venv (not in repo)
├── requirements.txt             pinned training deps
├── requirements.lock.txt        frozen after first successful install
├── extract_training_pairs.py    corpus extractor
├── train_lora.py                unsloth QLoRA trainer
├── convert_adapter_to_gguf.py   safetensors → GGUF wrapper
├── smoke_eval.py                before/after behavior harness
└── runs/                        artifacts (not in repo)
    └── <date>-<name>/
        ├── adapter/             unsloth save_pretrained output
        ├── adapter.gguf         converted for llama-server
        ├── training_pairs.jsonl extracted corpus
        ├── before_eval.txt      smoke eval — base model
        ├── after_eval.txt       smoke eval — with adapter
        └── train.log            full training stdout/stderr
```

## One-time install

```bash
cd /home/rohit/maez/training
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
.venv/bin/pip freeze > requirements.lock.txt
```

This installs ~15 GB of Python packages (torch, cuda kernels,
bitsandbytes, unsloth). The first training run additionally downloads
the gemma-4-26B HuggingFace weights (~50 GB) into
`~/.cache/huggingface/hub/`. Ensure at least 80 GB free on `/home`
before starting.

## Run order

### 1. Extract training pairs (zero downtime)

```bash
cd /home/rohit/maez/training
.venv/bin/python extract_training_pairs.py \
    --out runs/$(date +%Y-%m-%d)-first-run/training_pairs.jsonl \
    --max-pairs 2000
```

Pulls Telegram exchanges from ChromaDB, fast conversation turns,
SOUL-derived stable voice/identity pairs, evolution candidates, and
continuity capsules. Read-only — safe to run anytime.

The extractor intentionally excludes daemon reasoning cycles by
default. Those records contain live CPU/GPU/RAM/process observations;
they belong in perception/retrieval, not in LoRA/SFT weights. If you
are deliberately reviewing a capability experiment, pass
`--include-reasoning-cycles`, inspect the output, and do not promote the
adapter unless the validation battery proves it did not memorize stale
system facts.

### 2. Sanity-check training (MAINTENANCE WINDOW REQUIRED)

The RTX 4090 has only ~444 MiB free during production. Any training
step requires stopping both llama-servers first. Announce the window
on Telegram before stopping anything.

```bash
# Announce
sudo systemctl stop llama-server.service llama-server-vision.service
nvidia-smi   # verify VRAM near-zero

cd /home/rohit/maez/training
.venv/bin/python train_lora.py --mode sanity-check --out runs/sanity
```

Loads the model, attaches a LoRA adapter, runs 1 training step on a
fake 3-pair dataset. ~5 minutes. Catches "MoE not supported" and
CUDA OOM early, before committing to the full window.

### 3. Full training run

```bash
.venv/bin/python train_lora.py \
    --mode full \
    --pairs runs/$(date +%Y-%m-%d)-first-run/training_pairs.jsonl \
    --out runs/$(date +%Y-%m-%d)-first-run \
    2>&1 | tee runs/$(date +%Y-%m-%d)-first-run/train.log
```

1–3 hours depending on corpus size. Monitor VRAM with
`watch nvidia-smi` in another terminal.

### 4. Convert to GGUF

```bash
.venv/bin/python convert_adapter_to_gguf.py \
    runs/$(date +%Y-%m-%d)-first-run/adapter \
    runs/$(date +%Y-%m-%d)-first-run/adapter.gguf
```

### 5. Smoke eval

```bash
# Before (no adapter)
sudo systemctl start llama-server.service
.venv/bin/python smoke_eval.py --phase before \
    --out runs/$(date +%Y-%m-%d)-first-run/before_eval.txt

# After (with adapter)
sudo systemctl stop llama-server.service
# Manually start llama-server with --lora flag:
/home/rohit/llama.cpp/build/bin/llama-server \
    -m /path/to/gemma-4-26b.gguf \
    --lora runs/$(date +%Y-%m-%d)-first-run/adapter.gguf \
    --host 127.0.0.1 --port 8080 \
    <other flags from llama-server.service> &

.venv/bin/python smoke_eval.py --phase after \
    --out runs/$(date +%Y-%m-%d)-first-run/after_eval.txt
```

### 6. Restore production

```bash
# Kill manually-started llama-server
pkill -f "llama-server.*--lora"
# Restart via systemd (WITHOUT --lora — this is 11t's contract)
sudo systemctl start llama-server.service llama-server-vision.service
# Announce window closed on Telegram
```

## Maintenance-window contract

11t does NOT promote the adapter. The production `llama-server.service`
unit file is NOT modified. The adapter exists on disk in
`training/runs/<date>-first-run/adapter.gguf` and is NOT loaded at
service boot. 11u is the session that decides whether to promote.

If something goes wrong mid-window and production comes up broken:
restart llama-server.service without `--lora`, and the adapter never
touches the production inference path.
