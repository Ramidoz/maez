#!/usr/bin/env python3
"""
convert_adapter_to_gguf.py — Session 11t.

Thin wrapper around llama.cpp's upstream converter so the training
pipeline has a single, stable invocation regardless of where the
script lives in the llama.cpp tree.

Usage
-----
    python3 convert_adapter_to_gguf.py <adapter_dir> <out.gguf> \\
        [--base-model-id <hf_id>] [--outtype {f32,f16,bf16,q8_0,auto}]

<adapter_dir> is the directory saved by `model.save_pretrained(...)`
in train_lora.py — it contains `adapter_model.safetensors` and
`adapter_config.json`.

<out.gguf> is the path to write. If unset, defaults to
`<adapter_dir>/adapter.gguf`.

If the upstream `convert_lora_to_gguf.py` script moves or its args
change, this wrapper is the only thing that needs to update — the
rest of the pipeline keeps calling it the same way.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


UPSTREAM_SCRIPT = Path("/home/rohit/llama.cpp/convert_lora_to_gguf.py")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("adapter_dir", help="PEFT adapter directory")
    ap.add_argument("outfile", nargs="?", default=None,
                    help="output .gguf path (default: adapter_dir/adapter.gguf)")
    ap.add_argument("--base-model-id", default=None,
                    help="HF base model id, passed through if adapter_config.json "
                         "doesn't already record it")
    ap.add_argument("--outtype", default="f16",
                    choices=["f32", "f16", "bf16", "q8_0", "auto"])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    adapter_dir = Path(args.adapter_dir).resolve()
    if not adapter_dir.exists():
        print(f"ERROR: adapter dir not found: {adapter_dir}", file=sys.stderr)
        return 2

    cfg = adapter_dir / "adapter_config.json"
    if not cfg.exists():
        print(f"ERROR: {cfg} missing — is this a PEFT adapter dir?", file=sys.stderr)
        return 2

    outfile = Path(args.outfile) if args.outfile else adapter_dir / "adapter.gguf"
    outfile.parent.mkdir(parents=True, exist_ok=True)

    if not UPSTREAM_SCRIPT.exists():
        print(f"ERROR: upstream script missing: {UPSTREAM_SCRIPT}", file=sys.stderr)
        return 3

    cmd = [
        sys.executable, str(UPSTREAM_SCRIPT),
        str(adapter_dir),
        "--outfile", str(outfile),
        "--outtype", args.outtype,
    ]
    if args.base_model_id:
        cmd += ["--base-model-id", args.base_model_id]
    if args.dry_run:
        cmd += ["--dry-run"]

    print(f"[convert] running: {' '.join(cmd)}", file=sys.stderr)
    try:
        proc = subprocess.run(cmd, check=False)
    except Exception as e:
        print(f"[convert] subprocess failed: {e!r}", file=sys.stderr)
        return 4

    if proc.returncode != 0:
        print(f"[convert] upstream converter exited {proc.returncode}", file=sys.stderr)
        return proc.returncode

    if not args.dry_run and not outfile.exists():
        print(f"[convert] upstream claimed success but {outfile} missing", file=sys.stderr)
        return 5

    size_mb = (outfile.stat().st_size / (1024 * 1024)) if outfile.exists() else 0
    print(f"[convert] wrote {outfile} ({size_mb:.1f} MB)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
