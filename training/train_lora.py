#!/usr/bin/env python3
"""
train_lora.py — Session 11t.

Unsloth-based QLoRA trainer for Maez's first weight-level learning run.

Two modes
---------
  --mode sanity-check      Load the model, attach a LoRA adapter, run
                           ONE training step on a 3-pair fake dataset,
                           save the stub adapter. ~5 minutes. Used to
                           catch "MoE not supported" / OOM / toolchain
                           breakage BEFORE committing to the full run.

  --mode full              Real training on the extracted corpus.
                           Reads --pairs JSONL, trains for N epochs,
                           saves the adapter.

Both modes write a `train.log` style summary and exit non-zero on any
unrecoverable error.

Default model
-------------
The production substrate is gemma-4-26B-A4B, served by llama.cpp on
port 8080. Unsloth's MoE support for gemma-4 is unverified at time of
writing — pass a different --model to fall back to a dense variant
(gemma-2 27B or gemma-3 12B) if the MoE load fails in sanity-check.

Memory budget
-------------
Target 24 GB GPU (RTX 4090). The default config below aims to fit
inside that envelope:
  - 4-bit QLoRA (bitsandbytes NF4 + double-quant)
  - max_seq_length = 2048
  - LoRA rank = 16
  - batch size 1, gradient_accumulation_steps 8
  - unsloth gradient checkpointing
If OOM hits, reduce max_seq_length first (2048 → 1024) then rank
(16 → 8) then drop FFN target_modules.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path


DEFAULT_MODEL = "unsloth/gemma-3-27b-it-bnb-4bit"
# 11t default: the dense gemma-3 27B. If the MoE gemma-4-26B-A4B is
# available via unsloth, pass --model unsloth/gemma-4-26b-it-bnb-4bit
# explicitly. The sanity-check mode aborts fast on unknown model IDs.

DEFAULT_CHAT_TEMPLATE = "gemma-3"
# unsloth.chat_templates.get_chat_template supports "gemma", "gemma-2",
# "gemma-3". If a "gemma-4" template is added, pass --chat-template.


# Enable fast HF downloads globally
os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "1")


def _log(msg: str) -> None:
    print(f"[train_lora] {msg}", flush=True)


def _preflight_disk(min_free_gb: int = 80) -> bool:
    """Refuse to start if /home doesn't have enough free space for the
    HuggingFace model cache (~50 GB) plus training overhead."""
    stat = shutil.disk_usage("/home")
    free_gb = stat.free / (1024 ** 3)
    _log(f"preflight: /home free = {free_gb:.1f} GB (need ≥ {min_free_gb})")
    if free_gb < min_free_gb:
        _log(f"preflight FAILED: only {free_gb:.1f} GB free on /home")
        return False
    return True


def _preflight_gpu() -> bool:
    """Warn if llama-server is still running (VRAM not free)."""
    try:
        import subprocess
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.used,memory.free",
             "--format=csv,noheader,nounits"],
            text=True, timeout=10,
        ).strip()
        used_mb, free_mb = [int(x.strip()) for x in out.split(",")]
        _log(f"preflight: GPU used={used_mb} MiB  free={free_mb} MiB")
        if free_mb < 18000:
            _log(f"preflight WARNING: only {free_mb} MiB free — "
                 f"expected ≥18000. llama-server still running?")
            return False
        return True
    except Exception as e:
        _log(f"preflight: nvidia-smi check failed ({e}) — continuing")
        return True


def _build_fake_dataset(tokenizer, out_dir: Path):
    """3 trivial pairs for sanity-check mode."""
    from datasets import Dataset
    pairs = [
        {"conversations": [
            {"role": "user", "content": "Say hi."},
            {"role": "assistant", "content": "Hi, Rohit."},
        ]},
        {"conversations": [
            {"role": "user", "content": "One-word: color of the sky."},
            {"role": "assistant", "content": "Blue."},
        ]},
        {"conversations": [
            {"role": "user", "content": "What are you?"},
            {"role": "assistant", "content": "I am Maez, your system-level assistant."},
        ]},
    ]
    fake_path = out_dir / "fake_pairs.jsonl"
    with fake_path.open("w") as f:
        for p in pairs:
            f.write(json.dumps(p) + "\n")
    return _load_json_dataset(fake_path, tokenizer)


def _load_json_dataset(path: Path, tokenizer):
    from datasets import load_dataset
    ds = load_dataset("json", data_files=str(path), split="train")

    def _apply_template(ex):
        text = tokenizer.apply_chat_template(
            ex["conversations"],
            tokenize=False,
            add_generation_prompt=False,
        )
        return {"text": text}

    ds = ds.map(_apply_template, remove_columns=ds.column_names)
    return ds


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--mode", choices=["sanity-check", "full"], required=True)
    ap.add_argument("--out", required=True, help="run output directory")
    ap.add_argument("--pairs", help="JSONL of training pairs (required for --mode full)")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--chat-template", default=DEFAULT_CHAT_TEMPLATE)
    ap.add_argument("--max-seq-length", type=int, default=2048)
    ap.add_argument("--lora-rank", type=int, default=16)
    ap.add_argument("--epochs", type=float, default=1.0)
    ap.add_argument("--learning-rate", type=float, default=2e-4)
    ap.add_argument("--grad-accum", type=int, default=8)
    ap.add_argument("--skip-preflight", action="store_true",
                    help="skip disk+GPU preflight checks (dev only)")
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    _log(f"mode={args.mode}  model={args.model}  out={out_dir}")
    _log(f"seq_len={args.max_seq_length}  rank={args.lora_rank}  "
         f"epochs={args.epochs}  grad_accum={args.grad_accum}")

    # Preflight
    if not args.skip_preflight:
        if not _preflight_disk():
            return 2
        if not _preflight_gpu():
            _log("abort: GPU preflight failed. Stop llama-server first.")
            return 3

    # Import unsloth LATE so preflight can fail fast without loading
    # 15 GB of CUDA kernels into memory.
    _log("importing unsloth + transformers + trl ...")
    t0 = time.time()
    try:
        from unsloth import FastLanguageModel
        from unsloth.chat_templates import get_chat_template
        from trl import SFTTrainer, SFTConfig
    except Exception as e:
        _log(f"import FAILED: {e!r}")
        return 4
    _log(f"imports ok in {time.time()-t0:.1f}s")

    # Load base model + tokenizer
    _log(f"loading base model: {args.model}")
    t0 = time.time()
    try:
        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name=args.model,
            max_seq_length=args.max_seq_length,
            dtype=None,        # auto bf16 on Ampere+
            load_in_4bit=True,
        )
    except Exception as e:
        _log(f"model load FAILED: {e!r}")
        _log("hint: MoE / unsupported arch? Try --model "
             "unsloth/gemma-3-12b-it-bnb-4bit for a dense fallback.")
        return 5
    _log(f"base model loaded in {time.time()-t0:.1f}s")

    # Attach LoRA
    _log(f"attaching LoRA (r={args.lora_rank})")
    try:
        model = FastLanguageModel.get_peft_model(
            model,
            r=args.lora_rank,
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                            "gate_proj", "up_proj", "down_proj"],
            lora_alpha=args.lora_rank,
            lora_dropout=0,
            bias="none",
            use_gradient_checkpointing="unsloth",
            random_state=42,
        )
    except Exception as e:
        _log(f"LoRA attach FAILED: {e!r}")
        return 6

    # Chat template
    try:
        tokenizer = get_chat_template(tokenizer, chat_template=args.chat_template)
    except Exception as e:
        _log(f"chat template {args.chat_template!r} unknown, falling back to 'gemma'")
        try:
            tokenizer = get_chat_template(tokenizer, chat_template="gemma")
        except Exception as e2:
            _log(f"chat template fallback FAILED: {e2!r}")
            return 7

    # Dataset
    if args.mode == "sanity-check":
        _log("building fake 3-pair dataset")
        dataset = _build_fake_dataset(tokenizer, out_dir)
        max_steps = 1
        epochs = 1
    else:
        if not args.pairs:
            _log("ERROR: --pairs is required for --mode full")
            return 1
        pairs_path = Path(args.pairs)
        if not pairs_path.exists():
            _log(f"ERROR: pairs file not found: {pairs_path}")
            return 1
        _log(f"loading dataset from {pairs_path}")
        dataset = _load_json_dataset(pairs_path, tokenizer)
        max_steps = -1
        epochs = args.epochs

    _log(f"dataset size: {len(dataset)} examples")

    # Trainer — in full mode, save checkpoints every 25 steps so a
    # mid-run failure leaves a resumable partial adapter on disk. In
    # sanity mode we skip saving (only the 1-step result matters).
    training_args = SFTConfig(
        per_device_train_batch_size=1,
        gradient_accumulation_steps=args.grad_accum,
        warmup_steps=5 if args.mode == "full" else 0,
        num_train_epochs=epochs,
        max_steps=max_steps,
        learning_rate=args.learning_rate,
        bf16=True,
        optim="adamw_8bit",
        weight_decay=0.01,
        lr_scheduler_type="linear",
        seed=42,
        output_dir=str(out_dir),
        logging_steps=1 if args.mode == "sanity-check" else 5,
        save_strategy="steps" if args.mode == "full" else "no",
        save_steps=25,
        save_total_limit=2,
        report_to="none",
        dataset_text_field="text",
        max_seq_length=args.max_seq_length,
    )

    _log("constructing SFTTrainer")
    try:
        trainer = SFTTrainer(
            model=model,
            tokenizer=tokenizer,
            train_dataset=dataset,
            args=training_args,
        )
    except TypeError:
        # Older TRL versions don't accept tokenizer= / max_seq_length= inline
        _log("falling back to TRL without tokenizer/max_seq_length kwargs")
        trainer = SFTTrainer(
            model=model,
            train_dataset=dataset,
            args=training_args,
        )

    _log("starting training")
    t_train = time.time()
    try:
        train_result = trainer.train()
    except Exception as e:
        _log(f"training FAILED: {e!r}")
        return 8
    train_secs = time.time() - t_train
    _log(f"training finished in {train_secs/60:.1f} min")

    # Save
    adapter_dir = out_dir / "adapter"
    _log(f"saving adapter to {adapter_dir}")
    try:
        model.save_pretrained(str(adapter_dir))
        tokenizer.save_pretrained(str(adapter_dir))
    except Exception as e:
        _log(f"save FAILED: {e!r}")
        return 9

    # Summary
    summary = {
        "mode": args.mode,
        "model": args.model,
        "dataset_size": len(dataset),
        "epochs": epochs,
        "lora_rank": args.lora_rank,
        "max_seq_length": args.max_seq_length,
        "train_seconds": train_secs,
        "train_loss": float(getattr(train_result, "training_loss", 0.0)),
        "adapter_dir": str(adapter_dir),
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    _log(f"summary: {json.dumps(summary)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
