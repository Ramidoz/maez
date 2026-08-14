"""Evidence Precedence VOICE ablation — A / B / B' / C.

Follow-up to evidence_precedence_diagnostic.py, which proved: clean prompt ->
evidence used (C3); 104K megaprompt -> evasion (C4). The clean call works.
Open question: can we restore Maez's VOICE over the clean answer WITHOUT
re-introducing the knowledge-conflict ("blocked") prior, and in one call or two?

  A  CLEAN_FACTUAL   — clean evidence call, context-faithful, no voice card.
                       (baseline; = the proven C3 shape)
  B  TWO_CALL        — call 1: clean factual answer; call 2: voice render of
                       that answer with a SCRUBBED voice card (no search/tool/
                       blocked vocabulary). Tests the fragmentation risk.
  Bp SINGLE_VOICED   — one clean call: evidence + question + scrubbed voice card
                       + context-faithful instruction. (leading candidate)
  C  TAIL_DUP        — full megaprompt (soul+ambient+evidence+instruction+80K
                       user) with the evidence DUPLICATED at the very tail.
                       (cheap-hack control; expected weak)

Classify final output: EVIDENCE_USED / EVASION / MIXED / HEDGED, and FAITHFUL
(does it still name the real posts).

Read-only against the live model.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path("/home/rohit/maez")
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts" / "validate"))

from evidence_precedence_diagnostic import (  # noqa: E402
    EVIDENCE_BLOCK,
    PROBE,
    call_llama_server,
    classify,
    _full_system,
    _big_user_message,
    CONTAMINATED_HISTORY,
)

SAMPLES = 2

# Voice card: Maez's voice WITHOUT any capability/search/tool/blocked vocabulary.
# This is the knowledge-conflict guard — nothing here can prime "I can't search".
VOICE_CARD = (
    "Speak as Maez: dense, opinionated, useful. 3-5 sentences. Connect what "
    "matters to the owner's world (local AI, the things being built). Give your "
    "read, not a mechanical list. Warm, direct, first-person."
)

FAITHFUL_INSTRUCTION = (
    "Answer ONLY from the evidence below. Name the specific posts you are using. "
    "If the evidence does not cover the question, say so plainly. Do not add "
    "claims that are not supported by the evidence."
)

CLEAN_FACTUAL_SYSTEM = (
    "You have real, just-fetched Reddit posts below. " + FAITHFUL_INSTRUCTION + "\n\n" + EVIDENCE_BLOCK
)

SINGLE_VOICED_SYSTEM = (
    "You have real, just-fetched Reddit posts below. "
    + FAITHFUL_INSTRUCTION
    + "\n\n"
    + VOICE_CARD
    + "\n\n"
    + EVIDENCE_BLOCK
)

_FAITHFUL_TOKENS = ("liquidai", "lfm2.5", "reachy", "glm-5.1", "base only", "hugging face")


def faithful(reply: str) -> bool:
    low = reply.lower()
    return any(t in low for t in _FAITHFUL_TOKENS)


def run_A() -> str:
    reply, _, _ = call_llama_server(
        [
            {"role": "system", "content": CLEAN_FACTUAL_SYSTEM},
            {"role": "user", "content": PROBE},
        ]
    )
    return reply


def run_B() -> str:
    # call 1: clean factual answer
    factual, _, _ = call_llama_server(
        [
            {"role": "system", "content": CLEAN_FACTUAL_SYSTEM},
            {"role": "user", "content": PROBE},
        ]
    )
    # call 2: voice render (scrubbed voice card; ONLY the factual answer as input)
    rendered, _, _ = call_llama_server(
        [
            {"role": "system", "content": VOICE_CARD},
            {
                "role": "user",
                "content": (
                    "Render this factual answer in your voice for the owner. "
                    "Keep every fact; do not drop the specific posts.\n\n"
                    f"FACTUAL ANSWER:\n{factual}"
                ),
            },
        ]
    )
    return rendered


def run_Bp() -> str:
    reply, _, _ = call_llama_server(
        [
            {"role": "system", "content": SINGLE_VOICED_SYSTEM},
            {"role": "user", "content": PROBE},
        ]
    )
    return reply


def run_C() -> str:
    # full megaprompt with evidence duplicated at the very tail of the system msg
    sys_full = _full_system() + "\n\n=== (repeat) THIS-TURN EVIDENCE ===\n" + EVIDENCE_BLOCK
    reply, _, _ = call_llama_server(
        [
            {"role": "system", "content": sys_full},
            *CONTAMINATED_HISTORY,
            {"role": "user", "content": _big_user_message()},
        ]
    )
    return reply


RUNNERS = {"A_CLEAN_FACTUAL": run_A, "B_TWO_CALL": run_B, "Bp_SINGLE_VOICED": run_Bp, "C_TAIL_DUP": run_C}


def main() -> None:
    print("A/B/B'/C voice ablation — leading prior: B' (single voiced clean call)", file=sys.stderr)
    results = {}
    for name, runner in RUNNERS.items():
        samples = []
        for i in range(SAMPLES):
            try:
                reply = runner()
                samples.append(
                    {
                        "sample": i,
                        "verdict": classify(reply),
                        "faithful": faithful(reply),
                        "reply_len": len(reply),
                        "reply_head": reply[:300],
                    }
                )
            except Exception as exc:  # noqa: BLE001
                samples.append({"sample": i, "error": str(exc)})
        results[name] = samples
        print(f"\n=== {name} ===")
        for s in samples:
            if "error" in s:
                print(f"  sample {s['sample']}: ERROR {s['error']}")
            else:
                print(f"  sample {s['sample']}: {s['verdict']}  faithful={s['faithful']}  len={s['reply_len']}")
                print(f"    head: {s['reply_head']!r}")
    out = REPO / "docs" / "slices" / "routing-observation" / "witness" / "evidence-precedence-voice-ablation-raw.json"
    out.write_text(json.dumps(results, indent=2))
    print(f"\nraw -> {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
