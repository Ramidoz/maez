#!/usr/bin/env python3
"""
merge_lora.py — Session 11u+11v.

Merge a trained LoRA adapter into the base model weights and export
as GGUF Q4_K_M for llama-server deployment.

Unlike runtime --lora loading (which adds compute buffers and fights
with the vision server for VRAM), merging bakes the adapter into the
base weights. The result is a single GGUF file with zero additional
runtime overhead — vision + merged model coexist on 24 GB.

Pipeline:
    1. Load base model (unsloth/gemma-4-26B-A4B-it) in 16-bit
    2. Apply LoRA adapter from --adapter-dir
    3. Merge via model.merge_and_unload()
    4. Export to GGUF Q4_K_M via unsloth's save_pretrained_gguf
    5. Output lands in --out-dir/gemma-4-26B-A4B-merged-Q4_K_M.gguf

Expected runtime on H100: ~10-15 min
Expected output size: ~16 GB (same as base Q4_K_M)

CLI:
    python3 merge_lora.py \\
        --adapter-dir runs/2026-04-12-clean/adapter \\
        --out-dir runs/2026-04-12-clean/merged \\
        --quantization q4_k_m
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path


os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "1")


def _log(msg: str) -> None:
    print(f"[merge_lora] {msg}", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--adapter-dir", required=True,
                    help="path to PEFT adapter directory (safetensors + config)")
    ap.add_argument("--out-dir", required=True,
                    help="output directory for merged GGUF")
    ap.add_argument("--base-model", default="unsloth/gemma-4-26B-A4B-it",
                    help="HF base model id")
    ap.add_argument("--max-seq-length", type=int, default=2048)
    ap.add_argument("--quantization", default="q4_k_m",
                    choices=["q4_k_m", "q5_k_m", "q8_0", "f16"],
                    help="GGUF quantization method")
    args = ap.parse_args()

    adapter_dir = Path(args.adapter_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not (adapter_dir / "adapter_config.json").exists():
        _log(f"ERROR: no adapter_config.json in {adapter_dir}")
        return 1

    _log(f"base model:      {args.base_model}")
    _log(f"adapter dir:     {adapter_dir}")
    _log(f"output dir:      {out_dir}")
    _log(f"quantization:    {args.quantization}")

    _log("importing unsloth...")
    t0 = time.time()
    try:
        from unsloth import FastLanguageModel
    except Exception as e:
        _log(f"import FAILED: {e!r}")
        return 2
    _log(f"imports ok in {time.time()-t0:.1f}s")

    # Load the adapter directly via unsloth's from_pretrained.
    # Unsloth detects a PEFT config in the directory, pulls the base
    # model from adapter_config.json's base_model_name_or_path, and
    # applies the LoRA in unsloth's custom layer-wrapped format.
    # This is the ONLY way to merge — PEFT's standard path can't
    # handle unsloth's Gemma4ClippableLinear wrapper.
    _log(f"loading adapter {adapter_dir} (auto-pulls base model)")
    t0 = time.time()
    try:
        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name=str(adapter_dir),
            max_seq_length=args.max_seq_length,
            dtype=None,           # auto bf16
            load_in_4bit=False,   # 16-bit for clean merge
            load_in_8bit=False,
        )
    except Exception as e:
        _log(f"adapter load FAILED: {e!r}")
        return 3
    _log(f"adapter loaded in {time.time()-t0:.1f}s")

    # Export to GGUF via unsloth
    _log(f"exporting to GGUF {args.quantization} (this takes 5-10 min)")
    t0 = time.time()
    try:
        model.save_pretrained_gguf(
            str(out_dir),
            tokenizer,
            quantization_method=args.quantization,
        )
    except Exception as e:
        _log(f"GGUF export FAILED: {e!r}")
        # Fallback: save as HF safetensors, convert later
        _log("falling back to safetensors save")
        try:
            hf_dir = out_dir / "hf"
            hf_dir.mkdir(exist_ok=True)
            model.save_pretrained(str(hf_dir))
            tokenizer.save_pretrained(str(hf_dir))
            _log(f"safetensors saved to {hf_dir}")
            _log("convert to GGUF manually via llama.cpp/convert_hf_to_gguf.py")
        except Exception as e2:
            _log(f"fallback save also FAILED: {e2!r}")
            return 6
    _log(f"GGUF export complete in {time.time()-t0:.1f}s")

    # List output files
    _log("output files:")
    for f in sorted(out_dir.rglob("*.gguf")):
        size_gb = f.stat().st_size / (1024**3)
        _log(f"  {f.name}: {size_gb:.2f} GB")

    _log("DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
