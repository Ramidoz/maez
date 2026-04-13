#!/usr/bin/env bash
# training/remote/train_run.sh — Session 11t.
#
# Runs the two-phase QLoRA training ladder on the rented GPU pod:
#   1. Sanity check — 1 step on fake 3-pair data (fast fail gate)
#   2. Full training — real run on the uploaded training_pairs.jsonl
#
# Usage (inside a SSH'd-in pod, after setup_pod.sh has run):
#     cd /workspace/training
#     bash remote/train_run.sh <run-name>
#
# Expects training_pairs.jsonl already at runs/<run-name>/training_pairs.jsonl
# (rsync'd up from local before this runs).
#
# Writes all artifacts to /workspace/training/runs/<run-name>/:
#   adapter/       — PEFT safetensors dump
#   sanity.log     — sanity-check output
#   train.log      — full training output
#   summary.json   — hyperparams + loss + runtime

set -euo pipefail

if [ $# -ne 1 ]; then
    echo "Usage: bash remote/train_run.sh <run-name>"
    echo "Example: bash remote/train_run.sh 2026-04-11-first-run"
    exit 1
fi
RUN_NAME="$1"
RUN_DIR="runs/$RUN_NAME"
SANITY_DIR="runs/sanity"

cd /workspace/training

if [ -f remote/env.sh ]; then
    # shellcheck disable=SC1091
    source remote/env.sh
fi

# Thunder Compute: ensure libcuda.so exists
if [ ! -f /lib/x86_64-linux-gnu/libcuda.so ] && [ -f /lib/x86_64-linux-gnu/libcuda.so.1 ]; then
    sudo ln -sf /lib/x86_64-linux-gnu/libcuda.so.1 /lib/x86_64-linux-gnu/libcuda.so 2>/dev/null
    sudo ldconfig 2>/dev/null
fi

VENV=.venv
if [ ! -x "$VENV/bin/python3" ]; then
    echo "[train_run] ERROR: venv missing at $VENV. Run remote/setup_pod.sh first."
    exit 2
fi

if [ ! -f "$RUN_DIR/training_pairs.jsonl" ]; then
    echo "[train_run] ERROR: $RUN_DIR/training_pairs.jsonl missing."
    echo "[train_run] Upload the extracted pairs before running this script:"
    echo "[train_run]   rsync /tmp/probe.jsonl pod:$RUN_DIR/training_pairs.jsonl"
    exit 3
fi

echo "[train_run] run: $RUN_NAME"
echo "[train_run] pairs: $(wc -l < "$RUN_DIR/training_pairs.jsonl") JSONL lines"
echo "[train_run] starting sanity check — $(date -Iseconds)"

mkdir -p "$SANITY_DIR"
"$VENV/bin/python3" train_lora.py \
    --mode sanity-check \
    --model unsloth/gemma-4-26B-A4B-it \
    --chat-template gemma-3 \
    --out "$SANITY_DIR" \
    --skip-preflight \
    2>&1 | tee "$SANITY_DIR/sanity.log"

# Fail loud if sanity didn't produce an adapter
if [ ! -f "$SANITY_DIR/adapter/adapter_model.safetensors" ]; then
    echo "[train_run] SANITY FAILED — no adapter at $SANITY_DIR/adapter/"
    echo "[train_run] Check $SANITY_DIR/sanity.log for details."
    echo "[train_run] Aborting before full training."
    exit 4
fi

echo "[train_run] sanity ok — $(date -Iseconds)"
echo "[train_run] starting full training run"

"$VENV/bin/python3" train_lora.py \
    --mode full \
    --model unsloth/gemma-4-26B-A4B-it \
    --chat-template gemma-3 \
    --pairs "$RUN_DIR/training_pairs.jsonl" \
    --out "$RUN_DIR" \
    --skip-preflight \
    2>&1 | tee "$RUN_DIR/train.log"

if [ ! -f "$RUN_DIR/adapter/adapter_model.safetensors" ]; then
    echo "[train_run] FULL TRAINING FAILED — no adapter at $RUN_DIR/adapter/"
    echo "[train_run] Check $RUN_DIR/train.log for details."
    exit 5
fi

echo "[train_run] DONE at $(date -Iseconds)"
echo "[train_run] artifacts at $RUN_DIR/"
ls -la "$RUN_DIR/adapter/" 2>/dev/null
cat "$RUN_DIR/summary.json" 2>/dev/null || echo "(no summary.json)"
