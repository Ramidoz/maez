#!/usr/bin/env bash
# training/remote/setup_pod.sh — Session 11t.
#
# One-time bootstrap on a fresh RunPod instance with a network volume
# mounted at /workspace. Idempotent — safe to re-run. Everything that
# touches the network goes on the persistent volume so future pods
# start warm.
#
# Usage (inside a SSH'd-in RunPod pod):
#     cd /workspace/training
#     bash remote/setup_pod.sh
#
# What it does:
#   1. Creates /workspace/training/.venv (on the persistent volume)
#   2. pip installs from training/requirements.lock.txt (frozen from
#      today's successful local install)
#   3. Pre-downloads unsloth/gemma-4-26B-A4B-it into the HF cache
#      at /workspace/.cache/huggingface (also on the volume)
#   4. Verifies torch sees CUDA + the RunPod GPU
#   5. Exits 0 on success, non-zero on any step failure

set -euo pipefail

VOL=/workspace
TRAIN_DIR="$VOL/training"
VENV="$TRAIN_DIR/.venv"
HF_CACHE="$VOL/.cache/huggingface"

echo "[setup_pod] starting — $(date -Iseconds)"
echo "[setup_pod] volume mount: $VOL"
echo "[setup_pod] training dir: $TRAIN_DIR"

if [ ! -d "$TRAIN_DIR" ]; then
    echo "[setup_pod] ERROR: $TRAIN_DIR missing. rsync from local first."
    exit 1
fi

# 1. Venv on persistent volume
if [ ! -x "$VENV/bin/python3" ]; then
    echo "[setup_pod] creating venv at $VENV"
    python3 -m venv "$VENV"
    "$VENV/bin/pip" install --upgrade pip
else
    echo "[setup_pod] venv exists — reusing"
fi

# 2. Install deps. Prefer the lockfile (reproducible) over requirements.txt.
LOCKFILE="$TRAIN_DIR/requirements.lock.txt"
REQFILE="$TRAIN_DIR/requirements.txt"
if [ -f "$LOCKFILE" ]; then
    echo "[setup_pod] installing from lockfile: $LOCKFILE"
    "$VENV/bin/pip" install -r "$LOCKFILE"
elif [ -f "$REQFILE" ]; then
    echo "[setup_pod] installing from requirements.txt"
    "$VENV/bin/pip" install -r "$REQFILE"
else
    echo "[setup_pod] ERROR: neither lockfile nor requirements.txt found"
    exit 2
fi

# 3. Point HF caches at the persistent volume so future pods reuse them
export HF_HOME="$HF_CACHE"
export TRANSFORMERS_CACHE="$HF_CACHE/hub"
export HUGGINGFACE_HUB_CACHE="$HF_CACHE/hub"
mkdir -p "$HF_CACHE/hub"

# 4. Pre-download the base model into the volume cache.
#    hf_transfer is already installed from requirements — use it for speed.
echo "[setup_pod] warming HF cache with unsloth/gemma-4-26B-A4B-it"
echo "[setup_pod]   (first run: ~50 GB download, ~5-10 min on RunPod)"
export HF_HUB_ENABLE_HF_TRANSFER=1
"$VENV/bin/python3" -c "
import os
os.environ['HF_HOME'] = '$HF_CACHE'
os.environ['TRANSFORMERS_CACHE'] = '$HF_CACHE/hub'
os.environ['HUGGINGFACE_HUB_CACHE'] = '$HF_CACHE/hub'
from huggingface_hub import snapshot_download
path = snapshot_download(
    repo_id='unsloth/gemma-4-26B-A4B-it',
    cache_dir='$HF_CACHE/hub',
)
print(f'[setup_pod] model cached at: {path}')
"

# 5. Sanity check: torch + CUDA + unsloth
"$VENV/bin/python3" -c "
import torch
assert torch.cuda.is_available(), 'CUDA not available on this pod'
dev = torch.cuda.get_device_name(0)
props = torch.cuda.get_device_properties(0)
total_mib = props.total_memory // 1024**2
print(f'[setup_pod] GPU: {dev} ({total_mib} MiB total)')
print(f'[setup_pod] compute capability: {torch.cuda.get_device_capability(0)}')
import unsloth
print(f'[setup_pod] unsloth: {getattr(unsloth, \"__version__\", \"?\")}')
"

# Persist env var settings for future train_run.sh invocations in this pod
# Thunder Compute: libcuda.so symlink missing on fresh instances
if [ ! -f /lib/x86_64-linux-gnu/libcuda.so ] && [ -f /lib/x86_64-linux-gnu/libcuda.so.1 ]; then
    echo "[setup_pod] fixing libcuda.so symlink"
    sudo ln -sf /lib/x86_64-linux-gnu/libcuda.so.1 /lib/x86_64-linux-gnu/libcuda.so
    sudo ldconfig
fi

# Persist inductor cache on volume so future pods skip JIT compilation
INDUCTOR_CACHE="$VOL/.cache/torchinductor"
mkdir -p "$INDUCTOR_CACHE"

cat > "$TRAIN_DIR/remote/env.sh" <<EOF
export HF_HOME=$HF_CACHE
export TRANSFORMERS_CACHE=$HF_CACHE/hub
export HUGGINGFACE_HUB_CACHE=$HF_CACHE/hub
export HF_HUB_ENABLE_HF_TRANSFER=1
export TORCHINDUCTOR_CACHE_DIR=$INDUCTOR_CACHE
EOF

echo "[setup_pod] DONE at $(date -Iseconds)"
echo "[setup_pod] next: bash remote/train_run.sh <run-name>"
