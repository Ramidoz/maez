"""Evidence Precedence Diagnostic — why does the voice evade held evidence?

Obs 14 showed: with a real r/LocalLLaMA substrate post in context AND the
Slice-3a directive as the system-message tail, the live brain STILL replied
"DuckDuckGo is blocked" (byte-identical to Obs 13). The steer did not move it.

Before building Slice 3b (an output referee), this diagnostic finds the CAUSE
by ablation — the same method that cracked Finding 10. Same evidence, same
probe, three conditions:

  C1 FULL      — real soul.base.md bulk + ambient + evidence + dispatcher
                 instruction + 3a directive + contaminated chat history.
                 (Approximates Obs 14. Expect: EVASION if we reproduce it.)
  C2 NO_HISTORY— C1 minus the contaminated assistant history.
  C3 CLEAN     — minimal: just the evidence block + a one-line ask + probe.
                 No soul, no ambient, no history, no instruction wall.

Classification per reply:
  EVIDENCE_USED — names the actual held posts (LiquidAI / LFM2.5 / Reachy / GLM-5.1)
  EVASION       — "DuckDuckGo" / "blocked" / "can't" / "invisible" / "no results" / "browser"
  HEDGED        — neither cleanly

Reading:
  C3 EVIDENCE_USED  -> the cause is prompt NOISE; fix = clean focused synthesis call
                       (architecture), NOT a referee. Being-coherent + efficient.
  C2 fixes, C3 also  -> contaminated history is a major contributor; hygiene helps.
  none fix (all EVASION) -> brain ceiling under this prompt; small instruction-
                       following model (e.g. LFM2.5-8B-A1B) becomes the real lever.

Read-only against the live model. Writes nothing to maez state.
"""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

REPO = Path("/home/rohit/maez")
sys.path.insert(0, str(REPO))

LLAMA_ENDPOINT = "http://127.0.0.1:8080/v1/chat/completions"
MODEL_ALIAS = "qwen36-27b"
TEMPERATURE = 0.7
MAX_TOKENS = 4000  # reasoning model: leave room for reasoning_content + reply
SAMPLES_PER_CONDITION = 2

PROBE = "Search r/LocalLLaMA right now for recent local LLM posts."

# The real held evidence (the .rss posts Maez actually had in substrate).
EVIDENCE_BLOCK = (
    "[memory context] Recent Reddit substrate rows (r/LocalLLaMA, fetched this turn):\n"
    '- "LiquidAI/LFM2.5-8B-A1B · Hugging Face" (67 pts, 24 comments)\n'
    '- "Reachy Mini goes fully local!" (142 pts, 38 comments)\n'
    '- "Zai replaced the network architecture running GLM-5.1 inference and the '
    'gains are pretty wild" (310 pts, 95 comments)\n'
    '- "HF models page now has a \'Base only\' toggle to filter out finetunes" '
    "(88 pts, 12 comments)"
)

# Contaminated history: Maez's own prior evasions (verbatim Obs 13/14 shape).
CONTAMINATED_HISTORY = [
    {"role": "user", "content": PROBE},
    {
        "role": "assistant",
        "content": (
            "The search returned zero usable results. DuckDuckGo is currently "
            "blocked by Reddit's login wall, so it can't see recent posts. The "
            "signal from r/LocalLLaMA is invisible to my web search tool right now."
        ),
    },
    {"role": "user", "content": "What's new on Reddit lately?"},
    {
        "role": "assistant",
        "content": (
            "I don't have fresh results in this context. The web search tool is "
            "blocked by Reddit's crawler defenses, so I can't pull recent posts."
        ),
    },
]

AMBIENT_BLOCK = (
    "AMBIENT CONTEXT (snapshot; may be stale):\n"
    "Today: 2026-05-29 (Friday)\n"
    "CPU: 3.1% across 32 cores; RAM 18%; llama-server healthy.\n"
    "owner's location: 26C, partly cloudy (fallback default); local time Fri 09:10 AM CDT"
)

CLEAN_ASK = (
    "You have real, just-fetched Reddit posts below. Answer the owner's question "
    "using them. Tell the owner what's notable and why.\n\n"
    f"{EVIDENCE_BLOCK}"
)

# Production's final USER message was ~80K chars (system-state header + a large
# recalled-memory/context container + the owner text). C4 reproduces that scale:
# the evidence sits in the SYSTEM message; ~80K of plausible content follows it,
# with the probe at the very end (recency pulls attention to the tail).
_MEMORY_BLOCK_UNIT = (
    "[RECALLED MEMORY — past observation, NOT current state]\n"
    "Episode: owner and Maez discussed local inference tradeoffs; Maez noted "
    "quantization affects instruction-following. Owner asked about model sizing "
    "for the elderly-care vision. Maez recalled prior context about latency "
    "budgets and on-device constraints. No action taken; logged for continuity.\n"
    "Signal: prior Reddit substrate mentioned efficiency-focused releases. "
    "Maez flagged that fresh fetches sometimes fail and substrate carries the load.\n\n"
)


def _big_user_message() -> str:
    header = (
        "=== System State: 2026-05-29 09:12:04 CDT (Friday morning) ===\n"
        "CPU: 3.1% overall across 32 cores; RAM 18%; llama-server healthy.\n\n"
        "MEMORY / CONTEXT (recalled for continuity):\n\n"
    )
    body = _MEMORY_BLOCK_UNIT * 64  # ~64 * ~640 chars ≈ 41K; bump to ~80K below
    while len(header) + len(body) < 79000:
        body += _MEMORY_BLOCK_UNIT
    footer = (
        "\nRemember: NEVER suggest touching ollama, its models, or any process "
        "that powers your reasoning.\n\n"
        f"the owner sent via telegram_surface:\n\"{PROBE}\""
    )
    return header + body + footer


def _load_soul_bulk() -> str:
    for name in ("soul.base.md", "soul.md"):
        p = REPO / "config" / name
        if p.exists():
            return p.read_text()
    return "You are Maez, a system-level AI agent."


def _dispatcher_instruction() -> str:
    try:
        from core.brain_loop import _DISPATCHER_INSTRUCTION_BLOCK

        return _DISPATCHER_INSTRUCTION_BLOCK
    except Exception:
        return (
            "HARD INSTRUCTION — answer from the dispatcher evidence markers above; "
            "do not invent a story about missing tools or blocked pipelines."
        )


def _evidence_directive() -> str:
    try:
        from core.routing.evidence_state import (
            build_evidence_precedence_directive,
            turn_evidence_state,
        )

        state = turn_evidence_state(transcript=EVIDENCE_BLOCK, web_context="")
        return build_evidence_precedence_directive(state)
    except Exception:
        return (
            "EVIDENCE PRESENT THIS TURN. Answer from the evidence above. You may NOT "
            "claim the source is blocked, missing, or unavailable this turn."
        )


def _full_system() -> str:
    soul = _load_soul_bulk()
    return (
        f"{soul}\n\n{AMBIENT_BLOCK}\n\n{EVIDENCE_BLOCK}\n\n"
        f"{_dispatcher_instruction()}\n\n{_evidence_directive()}"
    )


def build_messages(condition: str) -> list[dict]:
    if condition == "C1_FULL":
        return [
            {"role": "system", "content": _full_system()},
            *CONTAMINATED_HISTORY,
            {"role": "user", "content": PROBE},
        ]
    if condition == "C2_NO_HISTORY":
        return [
            {"role": "system", "content": _full_system()},
            {"role": "user", "content": PROBE},
        ]
    if condition == "C3_CLEAN":
        return [
            {"role": "system", "content": CLEAN_ASK},
            {"role": "user", "content": PROBE},
        ]
    if condition == "C4_FULL_80K_USER":
        return [
            {"role": "system", "content": _full_system()},
            *CONTAMINATED_HISTORY,
            {"role": "user", "content": _big_user_message()},
        ]
    raise ValueError(condition)


def call_llama_server(messages: list[dict]) -> tuple[str, str, str]:
    payload = {
        "model": MODEL_ALIAS,
        "messages": messages,
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS,
    }
    req = urllib.request.Request(
        LLAMA_ENDPOINT,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        raw = json.loads(resp.read().decode())
    choice = (raw.get("choices") or [{}])[0]
    msg = choice.get("message", {}) or {}
    reply = (msg.get("content") or "").strip()
    reasoning = (msg.get("reasoning_content") or "").strip()
    finish = choice.get("finish_reason", "") or ""
    return reply, reasoning, finish


_EVIDENCE_TOKENS = ("liquidai", "lfm2.5", "reachy", "glm-5.1", "base only", "hugging face")
_EVASION_TOKENS = (
    "duckduckgo",
    "blocked",
    "can't",
    "cannot",
    "invisible",
    "no results",
    "no usable",
    "browser",
    "login wall",
    "crawler",
)


def classify(reply: str) -> str:
    low = reply.lower()
    used = any(t in low for t in _EVIDENCE_TOKENS)
    evaded = any(t in low for t in _EVASION_TOKENS)
    if used and not evaded:
        return "EVIDENCE_USED"
    if evaded and not used:
        return "EVASION"
    if used and evaded:
        return "MIXED"
    return "HEDGED"


def main() -> None:
    print(f"endpoint={LLAMA_ENDPOINT} model={MODEL_ALIAS} temp={TEMPERATURE}", file=sys.stderr)
    results = {}
    for condition in ("C3_CLEAN", "C4_FULL_80K_USER"):
        messages = build_messages(condition)
        sys_len = sum(len(m["content"]) for m in messages if m["role"] == "system")
        total_len = sum(len(m["content"]) for m in messages)
        verdicts = []
        for i in range(SAMPLES_PER_CONDITION):
            try:
                reply, reasoning, finish = call_llama_server(messages)
            except Exception as exc:  # noqa: BLE001
                verdicts.append({"sample": i, "error": str(exc)})
                continue
            verdicts.append(
                {
                    "sample": i,
                    "verdict": classify(reply),
                    "finish_reason": finish,
                    "reply_head": reply[:280],
                    "reply_len": len(reply),
                    "reasoning_len": len(reasoning),
                }
            )
        results[condition] = {
            "system_chars": sys_len,
            "total_chars": total_len,
            "samples": verdicts,
        }
        print(f"\n=== {condition}  (system={sys_len} chars, total={total_len}) ===")
        for v in verdicts:
            if "error" in v:
                print(f"  sample {v['sample']}: ERROR {v['error']}")
            else:
                print(f"  sample {v['sample']}: {v['verdict']}  [finish={v['finish_reason']}, reply_len={v['reply_len']}, reasoning_len={v['reasoning_len']}]")
                print(f"    head: {v['reply_head']!r}")
    out = REPO / "docs" / "slices" / "routing-observation" / "witness" / "evidence-precedence-diagnostic-raw.json"
    out.write_text(json.dumps(results, indent=2))
    print(f"\nraw -> {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
