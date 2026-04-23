#!/usr/bin/env python3
"""
extract_training_pairs.py — Sessions 11t + 11u/11v.

Read Maez's real conversation and reasoning data from the production
stores and emit a single JSONL of `{conversations: [...]}` training
pairs in the Gemma chat template form expected by unsloth's SFTTrainer.

Sources (11u/11v expansion)
---------------------------
1. ChromaDB telegram exchanges (167 records, "the owner asked / Maez replied")
2. fast_conversation_log.db (35 rows, alternating user/maez turns)
3. ChromaDB daemon reasoning cycles (type="reasoning", ~377 records)
4. Soul.md synthetic Q&A (~50 identity-reinforcing pairs)
5. Evolution engine candidates (evolution_track.db, ~13 weakness→fix pairs)
6. Continuity capsule archive (~23 state→resumption pairs)

Sources considered and REJECTED
-------------------------------
- `memory/site_analytics.jsonl` — pageview/CTA tracking, NOT chat.
- `memory/fast_reply_audit.jsonl` — metadata+hashes only, no text.

Output format
-------------
One JSONL line per pair:
    {"conversations": [
        {"role": "user", "content": "..."},
        {"role": "assistant", "content": "..."}
    ]}

Matches unsloth's `standardize_sharegpt` conventions so
`tokenizer.apply_chat_template(x["conversations"], ...)` works directly.

Filters applied
---------------
- assistant shorter than --min-assistant-chars (default 30) → drop
- user is a slash command (/start, /help, /status, etc.) → drop
- assistant is a known fallback phrase → drop
- exact-dedup on (user_norm, assistant_norm) where _norm =
  lowercase + whitespace-collapsed
- cap to the most recent --max-pairs (default 2000)

CLI
---
    python3 extract_training_pairs.py \\
        --out runs/<date>-first-run/training_pairs.jsonl \\
        --max-pairs 2000 \\
        --min-assistant-chars 30
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path
from typing import Iterator


# Gemma-4 special tokens that must be stripped from training data.
# If left in, the model learns to emit them in output, breaking
# llama-server's jinja template parser. Discovered in 11u+11v.
_SPECIAL_TOKEN_RE = re.compile(
    r"<\|[^|]*\|>"          # <|channel>, <|end_of_turn|>, etc.
    r"|<start_of_turn>"
    r"|<end_of_turn>"
    r"|<maez_thought>"
    r"|</maez_thought>"
    r"|<bos>"
    r"|<eos>"
)


def _strip_special_tokens(text: str) -> str:
    """Remove gemma-4 chat template tokens from training text."""
    return _SPECIAL_TOKEN_RE.sub("", text).strip()


MAEZ_ROOT = Path("/home/rohit/maez")
FAST_LOG_DB = MAEZ_ROOT / "memory" / "fast_conversation_log.db"
EVOLUTION_DB = MAEZ_ROOT / "memory" / "evolution_track.db"
CONTINUITY_ARCHIVE = MAEZ_ROOT / "memory" / "continuity_archive"
SOUL_PATH = MAEZ_ROOT / "config" / "soul.md"

# Phrases that indicate a degraded/fallback reply — we don't want to
# train the adapter to reproduce them. Grepped from web_interface.py
# and scripts/fast_reply_service.py fallback branches.
FALLBACK_PHRASES = (
    "I'm having trouble reaching",
    "Let me get back to you",
    "backend unavailable",
    "service degraded",
    "temporarily unable",
)

# Slash commands to drop on the user side
SLASH_COMMANDS = re.compile(r"^\s*/[a-zA-Z_]+(\s|$)")

# Fast-log scopes that are test probes, not real conversations
FAST_LOG_SKIP_SCOPES = {"test_11d", "rohit.web_dev_probe"}


# ── parsers ──────────────────────────────────────────────────────────
def parse_telegram_exchange(content: str) -> tuple[str, str] | None:
    """Parse one telegram_exchange document into (user, assistant).
    Returns None if neither known format matches."""
    text = (content or "").strip()
    if not text:
        return None

    # Format 1: "the owner asked: X\nMaez replied: Y"
    if text.startswith("the owner asked:") and "\nMaez replied:" in text:
        head, tail = text.split("\nMaez replied:", 1)
        user = head[len("the owner asked:"):].strip()
        assistant = tail.strip()
        if user and assistant:
            return user, assistant

    # Format 2: "the owner (source): X\nMaez: Y"  (daemon voice/text)
    m = re.match(
        r"^the owner\s*\([^)]+\)\s*:\s*(.*?)\nMaez\s*:\s*(.*)$",
        text,
        re.DOTALL,
    )
    if m:
        user = m.group(1).strip()
        assistant = m.group(2).strip()
        if user and assistant:
            return user, assistant

    return None


def iter_chromadb_pairs() -> Iterator[tuple[str, str, str, str]]:
    """Yield (user, assistant, source, timestamp) tuples from ChromaDB
    telegram exchanges. source is 'chromadb'."""
    try:
        m = _get_memory_manager()
        rows = m.get_telegram_exchanges(limit=None)
    except Exception as e:
        print(f"[extract] get_telegram_exchanges failed: {e}", file=sys.stderr)
        return

    for row in rows:
        parsed = parse_telegram_exchange(row.get("content", ""))
        if parsed is None:
            continue
        ts = (row.get("metadata") or {}).get("timestamp", "")
        user, assistant = parsed
        yield user, assistant, "chromadb", ts


def iter_fast_log_pairs() -> Iterator[tuple[str, str, str, str]]:
    """Yield (user, assistant, source, timestamp) tuples from the fast
    conversation log. Pairs adjacent user→maez rows within the same
    trust_scope."""
    if not FAST_LOG_DB.exists():
        return
    try:
        conn = sqlite3.connect(f"file:{FAST_LOG_DB}?mode=ro", uri=True)
    except Exception as e:
        print(f"[extract] fast_conversation_log open failed: {e}", file=sys.stderr)
        return

    cur = conn.execute(
        "SELECT id, trust_scope, role, text, created_at "
        "FROM fast_turns ORDER BY id"
    )
    prev_user: tuple[str, float, str] | None = None  # (text, ts, scope)
    for _id, scope, role, text, created_at in cur.fetchall():
        if scope in FAST_LOG_SKIP_SCOPES:
            prev_user = None
            continue
        role = (role or "").lower()
        text = (text or "").strip()
        if not text:
            continue
        if role == "user":
            prev_user = (text, float(created_at or 0), scope)
            continue
        if role in ("maez", "assistant") and prev_user is not None:
            u_text, u_ts, u_scope = prev_user
            if u_scope == scope:
                yield u_text, text, "fast_log", str(u_ts)
            prev_user = None
    conn.close()


# ── Session 11u/11v: new data sources ────────────────────────────────

def _get_memory_manager():
    """Lazy-load MemoryManager (needs MAEZ_ROOT on sys.path)."""
    sys.path.insert(0, str(MAEZ_ROOT))
    from memory.memory_manager import MemoryManager
    return MemoryManager()


def iter_reasoning_pairs() -> Iterator[tuple[str, str, str, str]]:
    """Yield (user, assistant, source, timestamp) from daemon reasoning
    cycles. Each cycle's output becomes the assistant response; the user
    prompt is synthesized from the cycle's metadata (wing, system state)."""
    try:
        m = _get_memory_manager()
        results = m.raw.get(
            where={"type": "reasoning"},
            include=["documents", "metadatas"],
        )
    except Exception as e:
        print(f"[extract] reasoning fetch failed: {e}", file=sys.stderr)
        return

    docs = results.get("documents") or []
    metas = results.get("metadatas") or []
    for doc, meta in zip(docs, metas, strict=False):
        doc = (doc or "").strip()
        if len(doc) < 50:
            continue
        wing = meta.get("wing", "system")
        tod = meta.get("time_of_day", "")
        dow = meta.get("day_of_week", "")
        cpu = meta.get("cpu_pct", "?")
        gpu = meta.get("gpu_pct", "?")
        ram = meta.get("ram_pct", "?")
        ts = meta.get("timestamp", "")

        context_parts = []
        if dow and tod:
            context_parts.append(f"{dow} {tod}")
        context_parts.append(f"CPU {cpu}%, GPU {gpu}%, RAM {ram}%")
        context_brief = ". ".join(context_parts)

        user_prompt = (
            f"Analyze the current system state and share observations. "
            f"Topic area: {wing}. Context: {context_brief}."
        )
        yield user_prompt, doc, "reasoning", ts


def iter_soul_qa_pairs() -> Iterator[tuple[str, str, str, str]]:
    """Yield synthetic Q&A pairs derived from soul.md sections.
    Anchors the adapter's voice to Maez's documented identity."""
    if not SOUL_PATH.exists():
        return
    try:
        sys.path.insert(0, str(MAEZ_ROOT))
        from core.soul_editor import parse
        doc = parse(SOUL_PATH.read_text())
    except Exception as e:
        print(f"[extract] soul parse failed: {e}", file=sys.stderr)
        return

    preamble_questions = [
        ("Who are you?", "identity"),
        ("Introduce yourself briefly.", "identity"),
        ("What kind of AI are you?", "identity"),
    ]
    if doc.preamble.strip():
        for q, tag in preamble_questions:
            yield q, doc.preamble.strip()[:1500], f"soul_qa:{tag}", ""

    section_questions = {
        "voice": [
            "How do you communicate? Describe your voice and style.",
            "What tone do you use with the owner?",
        ],
        "self-reflection": [
            "How do you reflect on your own behavior?",
            "Describe your self-reflection process.",
        ],
        "presence awareness": [
            "How do you detect whether the owner is at his desk?",
        ],
        "public bot identity": [
            "How do you behave with people other than the owner?",
            "What's your public personality like?",
        ],
        "internet access": [
            "Can you browse the internet?",
        ],
        "calendar awareness": [
            "How do you use calendar information?",
        ],
    }

    for section in doc.sections:
        name_lower = section.name.strip().lower()
        body = section.body.strip()
        if not body or len(body) < 30:
            continue
        questions = []
        for key, qs in section_questions.items():
            if key in name_lower:
                questions = qs
                break
        if not questions:
            questions = [f"Tell me about your {section.name} capabilities."]
        for q in questions:
            yield q, body[:1500], f"soul_qa:{name_lower}", ""


def iter_evolution_pairs() -> Iterator[tuple[str, str, str, str]]:
    """Yield (user, assistant, source, timestamp) from evolution engine
    candidates. Each candidate is a weakness→fix pair with measured
    pre/post scores."""
    if not EVOLUTION_DB.exists():
        return
    try:
        conn = sqlite3.connect(f"file:{EVOLUTION_DB}?mode=ro", uri=True)
    except Exception as e:
        print(f"[extract] evolution_track open failed: {e}", file=sys.stderr)
        return

    rows = conn.execute(
        "SELECT weakness_description, target_file, diff_text, "
        "justification, cognition_evidence, pre_patch_score_avg, "
        "post_patch_score_avg, created_at "
        "FROM candidates WHERE diff_text IS NOT NULL AND diff_text != ''"
    ).fetchall()
    conn.close()

    for weakness, target, diff, justification, cog_ev, pre_score, post_score, ts in rows:
        if not weakness or not diff:
            continue
        user_prompt = f"Weakness detected: {weakness}"
        if pre_score:
            user_prompt += f" Pre-patch score: {pre_score:.0f}."
        user_prompt += " Propose a fix."

        assistant_parts = [f"Target: {target or '?'}"]
        if justification:
            assistant_parts.append(f"Rationale: {justification}")
        assistant_parts.append(f"Diff:\n{diff[:1500]}")
        if post_score and pre_score:
            assistant_parts.append(
                f"Result: score {pre_score:.0f} → {post_score:.0f}"
            )
        assistant_resp = "\n".join(assistant_parts)
        yield user_prompt, assistant_resp, "evolution", ts or ""


def iter_continuity_pairs() -> Iterator[tuple[str, str, str, str]]:
    """Yield (user, assistant, source, timestamp) from continuity
    capsule archive. Teaches meta-cognitive state resumption."""
    if not CONTINUITY_ARCHIVE.exists():
        return
    try:
        capsule_files = sorted(CONTINUITY_ARCHIVE.iterdir())
    except Exception as e:
        print(f"[extract] continuity archive read failed: {e}", file=sys.stderr)
        return

    for fpath in capsule_files:
        if not fpath.name.endswith(".json"):
            continue
        try:
            cap = json.loads(fpath.read_text())
        except Exception:
            continue

        resume = (cap.get("resume_instructions") or "").strip()
        if not resume or len(resume) < 20:
            continue

        lt = cap.get("last_thought") or {}
        last_text = lt.get("text", "").strip() if isinstance(lt, dict) else ""
        concerns = cap.get("active_concerns") or []
        mode = cap.get("current_mode", "standard")
        checkpoint_type = cap.get("checkpoint_type", "periodic")
        ts = cap.get("written_at", "")

        context_parts = [f"Checkpoint type: {checkpoint_type}. Mode: {mode}."]
        if last_text:
            context_parts.append(f"Last thought: {last_text[:300]}")
        if concerns:
            context_parts.append(f"Active concerns: {', '.join(str(c) for c in concerns[:5])}")

        user_prompt = (
            "You are resuming after a restart. " + " ".join(context_parts) +
            " What should you focus on?"
        )
        yield user_prompt, resume, "continuity", ts


# ── filters ──────────────────────────────────────────────────────────
def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def is_slash_command(user: str) -> bool:
    return bool(SLASH_COMMANDS.match(user or ""))


def is_fallback(assistant: str) -> bool:
    lo = (assistant or "").lower()
    return any(p.lower() in lo for p in FALLBACK_PHRASES)


def pair_passes(
    user: str, assistant: str, min_assistant_chars: int
) -> bool:
    if not user or not assistant:
        return False
    if is_slash_command(user):
        return False
    if len(assistant) < min_assistant_chars:
        return False
    if is_fallback(assistant):
        return False
    return True


# ── main ─────────────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--out", required=True, help="output JSONL path")
    ap.add_argument("--max-pairs", type=int, default=2000)
    ap.add_argument("--min-assistant-chars", type=int, default=30)
    args = ap.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    per_source: dict[str, int] = {}
    raw_total = 0
    dropped_slash = 0
    dropped_short = 0
    dropped_fallback = 0

    seen: set[tuple[str, str]] = set()
    kept: list[dict] = []

    all_iterators = (
        iter_chromadb_pairs(),
        iter_fast_log_pairs(),
        iter_reasoning_pairs(),
        iter_soul_qa_pairs(),
        iter_evolution_pairs(),
        iter_continuity_pairs(),
    )
    for iterator in all_iterators:
        for user, assistant, source, _ts in iterator:
            raw_total += 1
            per_source[source] = per_source.get(source, 0) + 1

            # 11u fix: strip gemma-4 special tokens that break
            # llama-server when the model learns to reproduce them
            user = _strip_special_tokens(user)
            assistant = _strip_special_tokens(assistant)

            if is_slash_command(user):
                dropped_slash += 1
                continue
            if len(assistant) < args.min_assistant_chars:
                dropped_short += 1
                continue
            if is_fallback(assistant):
                dropped_fallback += 1
                continue

            key = (_norm(user), _norm(assistant))
            if key in seen:
                continue
            seen.add(key)

            kept.append({
                "conversations": [
                    {"role": "user", "content": user},
                    {"role": "assistant", "content": assistant},
                ]
            })

    # Cap to the most recent N (iterators yield chronologically from
    # ChromaDB, then fast_log; we want the freshest signal first)
    if args.max_pairs and len(kept) > args.max_pairs:
        kept = kept[-args.max_pairs:]

    with out_path.open("w") as f:
        for row in kept:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    # Summary to stderr so stdout remains clean for pipelining
    print(f"[extract] raw pairs scanned   : {raw_total}", file=sys.stderr)
    for src, count in per_source.items():
        print(f"[extract]   {src:12s}           : {count}", file=sys.stderr)
    print(f"[extract] dropped (slash cmd) : {dropped_slash}", file=sys.stderr)
    print(f"[extract] dropped (too short) : {dropped_short}", file=sys.stderr)
    print(f"[extract] dropped (fallback)  : {dropped_fallback}", file=sys.stderr)
    print(f"[extract] after dedup + cap   : {len(kept)}", file=sys.stderr)
    print(f"[extract] wrote {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
