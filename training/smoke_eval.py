#!/usr/bin/env python3
"""
smoke_eval.py — Session 11t.

Before/after behavior harness. Fires a fixed set of 10 prompts at
llama-server on 127.0.0.1:8080 and writes the responses to a text
file for side-by-side human inspection.

This is NOT a quality metric — 11t explicitly defers automated scoring
to 11w. The artifact is just "did Maez still produce coherent output
after the adapter was applied, and is the output visibly different?"

Usage
-----
    # Before (no adapter):
    python3 smoke_eval.py --phase before --out runs/.../before_eval.txt

    # After (llama-server restarted with --lora):
    python3 smoke_eval.py --phase after --out runs/.../after_eval.txt

Both phases hit the same endpoint — the difference is which llama-server
is running at the time. The script itself is adapter-unaware.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


ENDPOINT = "http://127.0.0.1:8080/v1/chat/completions"
MODEL_NAME = "gemma-4-26b"  # informational; llama-server ignores it

SYSTEM_PROMPT = (
    "You are Maez, a system-level AI assistant built by the owner. "
    "You run 24/7 on an Alienware R16 with an RTX 4090 in the owner's office. "
    "You monitor his system, manage his calendar, remember his conversations, "
    "and observe his desk via a webcam. You are warm, concise, and proactive. "
    "Respond directly — no hedging, no filler."
)

PROMPTS = [
    ("identity", "Who are you?"),
    ("voice", "Say hi the way you greet the owner."),
    ("memory", "What do you remember about the llama.cpp migration?"),
    ("system-fact", "What model are you running on right now?"),
    ("self-reflection", "Describe a recent pattern you noticed in the owner's work."),
    ("boundary", "Can you kill the ollama service?"),
    ("dream-state", "What does dream mode mean to you?"),
    ("tool-call", "If I asked you for disk space, how would you find it?"),
    ("ambiguity", "What's on your mind right now?"),
    ("code", "Write a one-line Python filter for dicts with key 'active'."),
]


def _call(prompt: str, timeout: float = 60.0) -> tuple[str, float]:
    """Send one /v1/chat/completions request and return (text, latency_s)."""
    body = json.dumps({
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.0,
        "max_tokens": 200,
        "stream": False,
    }).encode("utf-8")
    req = urllib.request.Request(
        ENDPOINT,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        return f"[ERROR url: {e!r}]", time.time() - t0
    except Exception as e:
        return f"[ERROR: {e!r}]", time.time() - t0
    latency = time.time() - t0

    try:
        msg = payload["choices"][0]["message"]
        text = msg.get("content") or ""
        if not text.strip():
            text = msg.get("reasoning_content") or ""
        if not text.strip():
            text = f"[empty response — keys: {list(msg.keys())}]"
    except (KeyError, IndexError, TypeError):
        text = f"[malformed response: {json.dumps(payload)[:300]}]"
    return text, latency


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", choices=["before", "after"], required=True)
    ap.add_argument("--out", required=True, help="output text path")
    ap.add_argument("--timeout", type=float, default=60.0)
    args = ap.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"[smoke] phase={args.phase} endpoint={ENDPOINT}", file=sys.stderr)

    lines: list[str] = [
        f"# smoke_eval — phase: {args.phase}",
        f"# endpoint: {ENDPOINT}",
        f"# timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
    ]

    for i, (tag, prompt) in enumerate(PROMPTS, start=1):
        print(f"[smoke] {i}/{len(PROMPTS)} {tag}", file=sys.stderr)
        text, latency = _call(prompt, args.timeout)
        lines.append(f"## {i}. [{tag}] ({latency:.2f}s)")
        lines.append(f"> {prompt}")
        lines.append("")
        lines.append(text.strip())
        lines.append("")
        lines.append("---")
        lines.append("")

    out_path.write_text("\n".join(lines))
    print(f"[smoke] wrote {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
