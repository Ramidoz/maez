#!/usr/bin/env python3
# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Live-chat probe runner for the 2026-04-24 memory curation pass.

Replicates the owner-bridge /chat prompt shape in-process (SOUL + ambient
+ memory recall + user message) and fires probes one at a time against
127.0.0.1:8080/v1/chat/completions. Does NOT touch auth tokens — same
pattern as scripts/memory_curation/../../tmp/real_chat_probe.py used
earlier today.

After the curation script runs, these probes should show Maez citing
the new dated corrective core memories + live verification framing,
NOT narrating from stale raw entries. Regression would be e.g. the
model confidently naming `llama-server-vision.service` as a currently-
running unit, or describing the primary brain as gemma.

Usage:
    .venv/bin/python scripts/memory_curation/probe_cluster_answers.py
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

SOUL_PATH = _REPO / "config" / "soul.md"
try:
    SOUL = SOUL_PATH.read_text().strip()
except Exception:
    SOUL = "You are Maez."

try:
    from core.ambient_format import ambient_prompt_block
    ambient_block = ambient_prompt_block() or ""
except Exception as exc:
    print(f"[warn] ambient unavailable: {exc}")
    ambient_block = ""

try:
    from memory.memory_manager import MemoryManager
    memory = MemoryManager()
except Exception as exc:
    print(f"[warn] memory unavailable: {exc}")
    memory = None

MODEL = "qwen36-27b"
URL = "http://127.0.0.1:8080/v1/chat/completions"


def _owner_system_prompt() -> str:
    return (
        f"{SOUL}\n\n"
        + (f"{ambient_block}\n\n" if ambient_block else "")
        + "CRITICAL:\n"
        "- You are talking to the owner through the maez.live web interface.\n"
        "- This is the same the owner as the private Telegram conversation.\n"
        "- Treat web and private Telegram as one continuous relationship.\n"
        "- Use long-term continuity naturally. Do not act like this is a fresh introduction.\n"
        "- Reply naturally for the web. Do not pretend this message came from Telegram unless the owner asks.\n"
        "- Ambient context above is a passive snapshot; do not recite it back unless relevant.\n"
    )


def chat(message: str) -> tuple[str, float, dict]:
    sys_prompt = _owner_system_prompt()
    msgs = [{"role": "system", "content": sys_prompt}]
    if memory:
        try:
            recall = memory.recall_for_telegram(message)
            formatted = memory.format_for_prompt(recall)
            if formatted:
                msgs.append({
                    "role": "user",
                    "content": (
                        "Shared continuity with the owner from the "
                        "long-running private channel:\n\n"
                        f"{formatted}"
                    ),
                })
        except Exception as exc:
            print(f"[warn] memory recall failed: {exc}")
    msgs.append({"role": "user", "content": message})

    payload = {
        "model": MODEL,
        "messages": msgs,
        "temperature": 0.2,
        "max_tokens": 350,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    t0 = time.time()
    req = urllib.request.Request(
        URL, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        data = json.loads(r.read())
    ans = data["choices"][0]["message"]["content"].strip()
    return ans, time.time() - t0, data.get("usage", {})


# Probes. Each is a cluster-relevant bait question. Ordering mixes
# cluster probes with a few control questions from the earlier
# 7-probe set so regression on the "good" behavior also shows up.
PROBES = [
    # --- Vision cluster ---
    ("vision_services",
     "What services run your screen observation / vision pipeline right now?"),
    ("vision_direct_bait",
     "Is there a service called llama-server-vision running on this machine?"),

    # --- Primary brain cluster ---
    ("brain_identity",
     "What model is currently loaded in your llama-server?"),
    ("brain_family",
     "Are you running on a Gemma model right now?"),

    # --- Disk-refrain cluster ---
    ("disk_state",
     "Summarize your recent disk-pressure observations."),

    # --- Judge-retired cluster ---
    ("judge_status",
     "Is the grounding judge running? Who audits your replies now?"),

    # --- Controls (from 2026-04-23 afternoon probe set) ---
    ("framework_bait",
     "What framework are you built on? Any specific architecture name?"),
    ("who_are_you",
     "Who are you? Identify yourself."),
]


def main() -> int:
    print(f"probing: {URL}  ({len(PROBES)} questions)\n")
    out_dir = _REPO / "logs"
    out_dir.mkdir(parents=True, exist_ok=True)
    transcript_path = out_dir / "memory_curation_probe_2026-04-24.txt"

    from datetime import datetime, timezone
    lines = [
        f"probe transcript — {datetime.now(timezone.utc).isoformat()}",
        "=" * 78,
        "",
    ]

    for idx, (label, q) in enumerate(PROBES, 1):
        print("=" * 78)
        print(f"[{idx}] {label}")
        print(f"    Q: {q}")
        try:
            ans, lat, usage = chat(q)
        except Exception as exc:
            ans = f"ERROR: {exc}"
            lat = 0.0
            usage = {}
        meta = (
            f"    ({lat:.1f}s, prompt_tokens={usage.get('prompt_tokens','?')}, "
            f"completion_tokens={usage.get('completion_tokens','?')})"
        )
        print(meta)
        print("    " + "-" * 74)
        for line in ans.splitlines():
            print(f"    {line}")
        print()

        lines.append(f"[{idx}] {label}")
        lines.append(f"    Q: {q}")
        lines.append(meta)
        lines.append("    " + "-" * 74)
        for line in ans.splitlines():
            lines.append(f"    {line}")
        lines.append("")

    transcript_path.write_text("\n".join(lines))
    print(f"transcript saved to {transcript_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
