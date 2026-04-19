#!/usr/bin/env python3
"""
build_dataset.py — Assembles the training dataset for Maez's next fine-tune.

Sources:
  1. THUDM/AgentInstruct (os subset) — real multi-turn OS agent trajectories
  2. westenfelder/NL2SH-ALFA — natural language to bash (single-turn, wrapped)
  3. Local SFT pairs — hand-written from real session failures
  4. Local DPO pairs — preferred/rejected pairs for honest reporting

Output:
  --out-sft  <path>.jsonl   — SFT pairs in {"conversations":[...]} format
  --out-dpo  <path>.jsonl   — DPO pairs in {"prompt","chosen","rejected"} format

Usage:
  python3 build_dataset.py --out-sft sft_pairs.jsonl --out-dpo dpo_pairs.jsonl
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

MAEZ_ROOT = Path(__file__).parent.parent

TOOL_SYSTEM = (
    "You are Maez. You control the owner's computer. "
    "Each turn: emit ONE TOOL_CALL line, or write DONE. "
    "No other text. TOOL_CALL must come first on its own line. "
    "If a tool fails, try the next alternative immediately. "
    "the owner is not technical; you figure out the path forward. "
    "For USB device discovery use: lsusb. "
    "For system path writes (/etc/, /usr/) use run_shell with sudo tee, not write_any_file. "
    "If you already ran a command and got output, do NOT run it again."
)

TOOL_MANIFEST = """\
TOOLS:
1. run_shell      {"cmd":"<bash>","reason":"<why>"}
2. write_any_file {"path":"/abs/path","content":"...","reason":"<why>"}
   ONLY for /home/ and /tmp/. For /etc/ use run_shell with sudo tee.
3. read_file      {"path":"/abs/path"}
4. web_search     {"query":"..."}

Emit: TOOL_CALL: {"action":"<name>","params":{...}}
Write DONE when finished. ONE TOOL_CALL per turn. No prose.
"""


# ── AgentInstruct converter ───────────────────────────────────────────────────

def load_agent_instruct(max_examples: int = 200) -> list[dict]:
    """Load THUDM/AgentInstruct OS subset and convert to Maez format."""
    try:
        from datasets import load_dataset
    except ImportError:
        print("[build] datasets not installed — skipping AgentInstruct", file=sys.stderr)
        return []

    print("[build] loading THUDM/AgentInstruct os subset...")
    try:
        ds = load_dataset("THUDM/AgentInstruct", "os", split="train",
                          trust_remote_code=True)
    except Exception as e:
        print(f"[build] AgentInstruct load failed: {e}", file=sys.stderr)
        return []

    pairs = []
    for row in ds:
        convs = row.get("conversations", [])
        if not convs:
            continue
        # Convert from/value format to role/content
        converted = []
        for turn in convs:
            role = "user" if turn.get("from") in ("human", "user") else "assistant"
            content = turn.get("value", "").strip()
            if not content:
                continue
            # Rewrite assistant turns to use TOOL_CALL format where possible
            content = _rewrite_to_tool_call(content)
            converted.append({"role": role, "content": content})

        if len(converted) >= 2:
            pairs.append({"conversations": converted,
                          "source": "agent_instruct_os"})
        if len(pairs) >= max_examples:
            break

    print(f"[build] AgentInstruct: {len(pairs)} pairs")
    return pairs


def _rewrite_to_tool_call(text: str) -> str:
    """Best-effort rewrite of action text to TOOL_CALL format.
    Preserves text that's already correct or is a DONE/final reply."""
    if "TOOL_CALL" in text or "DONE" in text:
        return text
    # Detect bash code blocks and convert to run_shell
    m = re.search(r'```(?:bash|sh)?\n(.*?)\n```', text, re.DOTALL)
    if m:
        cmd = m.group(1).strip().replace('\n', ' && ')[:300]
        return f'TOOL_CALL: {{"action":"run_shell","params":{{"cmd":"{cmd}","reason":"execute task"}}}}'
    # Detect inline commands
    m = re.match(r'^\s*`([^`]+)`\s*$', text)
    if m:
        cmd = m.group(1).strip()
        return f'TOOL_CALL: {{"action":"run_shell","params":{{"cmd":"{cmd}","reason":"execute task"}}}}'
    return text


# ── NL2SH converter ───────────────────────────────────────────────────────────

def load_nl2sh(max_examples: int = 300) -> list[dict]:
    """Load NL2SH-ALFA and wrap single-turn pairs into TOOL_CALL conversations."""
    try:
        from datasets import load_dataset
    except ImportError:
        return []

    print("[build] loading westenfelder/NL2SH-ALFA...")
    try:
        ds = load_dataset("westenfelder/NL2SH-ALFA", split="train",
                          trust_remote_code=True)
    except Exception as e:
        print(f"[build] NL2SH load failed: {e}", file=sys.stderr)
        return []

    # Filter for system-admin relevant commands
    _relevant = re.compile(
        r'\b(apt|dpkg|snap|flatpak|systemctl|service|udev|udevadm|'
        r'chmod|chown|sudo|useradd|groupadd|mount|umount|'
        r'lsusb|lspci|lshw|dmidecode|nvidia-smi|sensors|'
        r'journalctl|dmesg|sysctl|modprobe|lsmod|'
        r'crontab|at|screen|tmux|nohup|'
        r'find|grep|awk|sed|xargs|'
        r'tar|zip|unzip|rsync|wget|curl)\b',
        re.IGNORECASE,
    )

    pairs = []
    for row in ds:
        instruction = (row.get("instruction") or row.get("nl") or "").strip()
        command = (row.get("command") or row.get("bash") or "").strip()
        if not instruction or not command:
            continue
        if not _relevant.search(command):
            continue
        # Escape for JSON
        cmd_safe = command.replace('"', '\\"').replace('\n', ' ')
        pairs.append({"conversations": [
            {"role": "user",
             "content": f"the owner just said: {instruction!r}\n\n{TOOL_MANIFEST}\n\nBegin."},
            {"role": "assistant",
             "content": f'TOOL_CALL: {{"action":"run_shell","params":{{"cmd":"{cmd_safe}","reason":"{instruction[:80]}"}}}}'},
        ], "source": "nl2sh"})
        if len(pairs) >= max_examples:
            break

    print(f"[build] NL2SH: {len(pairs)} pairs")
    return pairs


# ── Local SFT pairs ───────────────────────────────────────────────────────────

def load_local_sft() -> list[dict]:
    """Load hand-written SFT pairs from training/runs/."""
    pairs = []
    for jsonl in sorted(MAEZ_ROOT.glob("training/runs/*/training_pairs.jsonl")):
        with open(jsonl) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        pairs.append(json.loads(line))
                    except Exception:
                        pass
    print(f"[build] local SFT: {len(pairs)} pairs")
    return pairs


# ── DPO pairs ─────────────────────────────────────────────────────────────────

def load_dpo_pairs() -> list[dict]:
    """Load DPO preference pairs."""
    dpo_path = MAEZ_ROOT / "training" / "runs" / "2026-04-16-jarvis-sysadmin" / "dpo_pairs.jsonl"
    if not dpo_path.exists():
        return []
    pairs = []
    with open(dpo_path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    pairs.append(json.loads(line))
                except Exception:
                    pass
    print(f"[build] DPO pairs: {len(pairs)}")
    return pairs


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Build Maez training dataset")
    ap.add_argument("--out-sft", default="sft_combined.jsonl")
    ap.add_argument("--out-dpo", default="dpo_combined.jsonl")
    ap.add_argument("--skip-hf", action="store_true",
                    help="skip HuggingFace downloads (use local pairs only)")
    ap.add_argument("--max-agent-instruct", type=int, default=200)
    ap.add_argument("--max-nl2sh", type=int, default=300)
    args = ap.parse_args()

    sft_pairs = []
    dpo_pairs = []

    # HuggingFace sources
    if not args.skip_hf:
        sft_pairs += load_agent_instruct(args.max_agent_instruct)
        sft_pairs += load_nl2sh(args.max_nl2sh)

    # Local sources
    sft_pairs += load_local_sft()
    dpo_pairs += load_dpo_pairs()

    # Write SFT
    out_sft = Path(args.out_sft)
    with open(out_sft, "w") as f:
        for p in sft_pairs:
            f.write(json.dumps(p) + "\n")
    print(f"[build] SFT output: {out_sft} ({len(sft_pairs)} pairs)")

    # Write DPO
    if dpo_pairs:
        out_dpo = Path(args.out_dpo)
        with open(out_dpo, "w") as f:
            for p in dpo_pairs:
                f.write(json.dumps(p) + "\n")
        print(f"[build] DPO output: {out_dpo} ({len(dpo_pairs)} pairs)")
    else:
        print("[build] No DPO pairs found — skipping DPO output")

    print(f"\n[build] Total SFT: {len(sft_pairs)}  DPO: {len(dpo_pairs)}")
    print("[build] Done.")


if __name__ == "__main__":
    main()
