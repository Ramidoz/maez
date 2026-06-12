# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""OUTBOUND-ONLY since 2026-04-20 (Surface V2 migration).

The inbound methods in this module (_handle_message, _process_message, the
_try_*_intent interceptors) DO NOT FIRE on live owner messages. Inbound
Telegram routes through skills/surface/maez_adapter.py. Wire new inbound
features into maez_adapter, not here. See
docs/SURFACE_PARITY_MAP_2026-06-12.md and docs/MAEZ_BUILD_LEDGER.md.
"""

import asyncio
import logging
import os
import threading
import time
from dataclasses import replace
from pathlib import Path
from typing import Optional

from telegram import Bot, Update, BotCommand, BotCommandScopeChat, MenuButtonCommands
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import sys

_MAEZ_HOME_PATH = Path(__file__).resolve().parent.parent
if str(_MAEZ_HOME_PATH) not in sys.path:
    sys.path.insert(0, str(_MAEZ_HOME_PATH))
from core.infra.secrets import sanitize_env
from core.health.shared_executor import get_shared_executor
from core.search.sense_flag import sense_enabled
from core.search.search_commitment import is_search_offer_worthy
from core.perception import snapshot as perception_snapshot, format_snapshot
from core.conversation_controller import ConversationController, _search_commitment_enabled
from core.body.camera_presence_voice import answer_camera_presence_question
from core.safety.clinical_boundary import PrivateThoughtsCrisisSignalWriter, guard_owner_text
from core.egress.provenance import ProvenanceSpan, ProvenancedText
from core.egress.telegram_egress import (
    TelegramEgressEnvelope,
    call_telegram_method_async,
    owner_multispan_envelope,
    owner_text_envelope,
    owner_transport_control_envelope,
)
from memory.memory_manager import MemoryManager
from skills.web_search import (
    search as web_search,
    format_for_context as web_format,
    needs_web_search,
    search_rss,
    is_news_query,
)

logger = logging.getLogger("maez")
_INBOUND_WARNED = False


DISPATCHER_TRANSCRIPT_MARKERS = (
    "[memory evidence]",
    "[memory context]",
    "[fresh evidence]",
    "[no fresh evidence available:",
    "[dispatcher refusal:",
)


def _telegram_pipeline_a_web_search_enabled() -> bool:
    from core.routing.recall_stack_config import resolve_recall_stack

    return not resolve_recall_stack().triad_on


def _telegram_jarvis_block_is_dispatcher_shaped(jarvis_block: str) -> bool:
    return any(marker in jarvis_block for marker in DISPATCHER_TRANSCRIPT_MARKERS)


def _telegram_jarvis_block_state(jarvis_block: str) -> str:
    if not jarvis_block:
        return "empty"
    if _telegram_jarvis_block_is_dispatcher_shaped(jarvis_block):
        return "dispatcher"
    return "jarvis"


def _telegram_log_jarvis_block_state(*, chat_id: str, jarvis_block: str) -> None:
    logger.info(
        "telegram_jarvis_block_state chat_id=%s state=%s prefix=%r",
        chat_id,
        _telegram_jarvis_block_state(jarvis_block),
        jarvis_block[:100],
    )


def _telegram_dispatcher_hard_instruction() -> str:
    return (
        "HARD INSTRUCTION — read this before writing a single word of your reply:\n"
        "\n"
        "1. Marker vocabulary. The transcript above is dispatcher output from THIS turn:\n"
        "   · [memory evidence] — substrate recall returned content for this turn.\n"
        "     This is dispatcher-emitted grounding. Cite it directly when it answers\n"
        "     the owner's question.\n"
        "   · [memory context] — substrate recall returned context for fresh evidence.\n"
        "     It is real grounding for this turn, but the fresh evidence is the headline.\n"
        "   · [fresh evidence] — live external fetch succeeded for this turn. Treat it\n"
        "     as just-fetched data and report what it says.\n"
        "   · [no fresh evidence available: <SOURCE>:<STATUS>:<CLASS>:<LIMITATION>]\n"
        "     means the dispatcher attempted fresh evidence and failed honestly. Say\n"
        "     what was tried and use the closed-vocab labels as written.\n"
        "   · [dispatcher refusal: <REASON>] means the dispatcher refused this turn.\n"
        "     Report the refusal reason honestly. Do not bypass it.\n"
        "\n"
        "2. This-turn semantics. Content under dispatcher markers is the result of\n"
        "   THIS turn's substrate and external fan-out. The JARVIS rule that memory\n"
        "   recall is only history does NOT apply to dispatcher-emitted [memory\n"
        "   evidence] or [memory context]. Do not confuse these markers with the\n"
        "   older [RECALLED MEMORY] historical section elsewhere in the prompt.\n"
        "\n"
        "3. Use the evidence, not architecture stories. If the dispatcher emitted\n"
        "   relevant evidence, answer from it. If it emitted no relevant evidence,\n"
        "   say that plainly. Do not invent internal-architecture descriptions such\n"
        "   as 'Reddit signal pipeline', 'tool loop', 'Telegram interceptor', or\n"
        "   'DuckDuckGo loop' to explain absence.\n"
        "\n"
        "4. Closed-vocabulary discipline. When citing failures, limitations, or\n"
        "   refusals, use the labels in the marker as written, such as AUTH_DENIED,\n"
        "   SOURCE_TIMEOUT, FRESH_ATTEMPT_FAILED, or\n"
        "   FRESH_FAILURE_HYBRID_FALLBACK_ILLEGAL. Do not paraphrase them into a\n"
        "   different reason.\n"
        "\n"
        "5. Forbidden fallback phrases for dispatcher turns:\n"
        "   · 'I cannot perform that search'\n"
        "   · 'I have no live web search tool'\n"
        "   · 'the Reddit pipeline is broken'\n"
        "   · 'the X pipeline is broken'\n"
        "   · 'I am blind to Reddit'\n"
        "   · 'trigger a Telegram interceptor'\n"
        "   These phrases are false when dispatcher evidence is present. If the\n"
        "   dispatcher reports a failure, name the marker's closed-vocab failure\n"
        "   instead of inventing a system explanation.\n"
        "\n"
        "SUMMARY: The dispatcher transcript is current-turn grounding. Read the\n"
        "markers literally, answer from the evidence they carry, and do not replace\n"
        "that evidence with a story about missing tools or hidden pipelines.\n"
    )


def _telegram_jarvis_hard_instruction() -> str:
    return (
        "HARD INSTRUCTION — read this before writing a single word of your reply:\n"
        "\n"
        "1. THE POSITIVE RULE (the only one that matters): the only\n"
        "   actions, tools, commands, packages, files, websites, or\n"
        "   results you are allowed to mention in your reply are the\n"
        "   ones that appear in the Jarvis transcript above. Nothing\n"
        "   else. If you want to reference something, it has to be\n"
        "   in the transcript. If it isn't in the transcript, you\n"
        "   didn't do it this turn.\n"
        "\n"
        "2. How to read the transcript:\n"
        "   · ✓ line — the tool RAN and returned output. It is DONE.\n"
        "     Report what you found. NEVER say 'waiting for approval'\n"
        "     for a ✓ line — it already executed.\n"
        "     GOOD reply for ✓: 'I checked and found [output]. [What\n"
        "     that means / what to do next].'\n"
        "     BAD reply for ✓: 'I proposed running X — that's waiting\n"
        "     for your approval.' ← WRONG. It ran. Report the result.\n"
        "   · ✗ line — the tool call was REJECTED, the audit refused,\n"
        "     or the call errored. Nothing happened. Do NOT describe\n"
        "     the failed tool as if it partially ran.\n"
        "   · ⏳ CARD_CREATED line — a proposal was sent to the owner\n"
        "     and is waiting for his approval. The action has NOT\n"
        "     run. You must tell the owner you proposed it and are\n"
        "     waiting. Do NOT claim the action finished.\n"
        "     GOOD reply for ⏳: 'I've proposed running X — that's\n"
        "     waiting for your go-ahead.'\n"
        "\n"
        "3. PARTIAL-ACTION TRAP (this is where fabrication sneaks in):\n"
        "   If the transcript has ONE tool entry, you are only\n"
        "   allowed to talk about THAT tool. You are not allowed to\n"
        "   frame the reply around a DIFFERENT action you also\n"
        "   thought about doing but didn't. Shape of the trap:\n"
        "     transcript: 1 card proposed — run <CMD_FROM_TRANSCRIPT>\n"
        "     BAD reply: 'I've started looking into the best tools\n"
        "       for <user topic>. I proposed a system check to\n"
        "       identify available utilities.'\n"
        "     WHY BAD: 'started looking' is not in the transcript;\n"
        "       the card is <CMD_FROM_TRANSCRIPT>, not a utility\n"
        "       scan. The reply invented a second action.\n"
        "     GOOD reply (⏳ card): 'I've proposed running\n"
        "       `<CMD_FROM_TRANSCRIPT>` — waiting for your go-ahead.'\n"
        "     GOOD reply (✓ ran): 'I ran `<CMD_FROM_TRANSCRIPT>`\n"
        "       and found: [output]. [What that means].'\n"
        "   ANTI-REFLEX RULE: The commands you name in your reply\n"
        "   must come from THIS turn's transcript only. Do not\n"
        "   reuse command strings from this example or from your\n"
        "   memory of prior turns. If the transcript shows no\n"
        "   tool call, do not name any command at all. Never\n"
        "   default to 'lsb_release' / 'uname' / 'OS and kernel\n"
        "   check' as a filler — that phrase has leaked from\n"
        "   past examples and is a fabrication trigger.\n"
        "\n"
        "4. Memory recall blocks (the [RECALLED MEMORY] section\n"
        "   earlier in this prompt) are history about the past.\n"
        "   They are NOT a record of what you did this turn.\n"
        "   Never attribute their contents to this turn. If you\n"
        "   want to reference something from memory, frame it\n"
        "   explicitly as past: 'I noticed earlier...', 'last I\n"
        "   saw...', 'in our past conversations I...'.\n"
        "\n"
        "5. If the transcript is empty, say you haven't checked\n"
        "   yet this turn. Do not pretend you did.\n"
        "\n"
        "6. The BODY ACTIVITY block earlier in this prompt shows\n"
        "   what your body did in the LAST 10 MINUTES across\n"
        "   previous turns. It is authoritative state. If the owner\n"
        "   asks a follow-up question like 'are you still\n"
        "   investigating?' or 'what happened to that thing?',\n"
        "   read BODY ACTIVITY first — a card may have already\n"
        "   executed between turns, and you need to report its\n"
        "   real outcome, not guess.\n"
    )


def _telegram_hard_instruction_for_jarvis_block(jarvis_block: str) -> str:
    if _telegram_jarvis_block_is_dispatcher_shaped(jarvis_block):
        return _telegram_dispatcher_hard_instruction()
    return _telegram_jarvis_hard_instruction()


async def _reply_text(update, text: str, **kwargs):
    chat_id = getattr(getattr(update, "effective_chat", None), "id", "")
    envelope = owner_text_envelope(
        bot_route="voice_owner_private",
        chat_id=str(chat_id),
        text=str(text),
        source_ref="telegram_voice:reply_text",
        message_kind="text",
    )
    return await call_telegram_method_async(
        envelope=envelope,
        target=update.message,
        method_name="reply_text",
        kwargs={"text": text, **kwargs},
    )


async def _bot_send_message(bot, *, envelope: TelegramEgressEnvelope | None = None, **kwargs):
    if envelope is None:
        envelope = owner_multispan_envelope(
            bot_route="voice_owner_private",
            chat_id=str(kwargs.get("chat_id") or ""),
            content=ProvenancedText.from_raw_conservative(
                str(kwargs.get("text") or ""),
                source_ref="telegram_voice:bot_send_message:raw_unreviewed",
            ),
            source_ref="telegram_voice:bot_send_message",
            message_kind="text",
        )
    elif kwargs.get("chat_id") and not envelope.chat_id:
        envelope = replace(envelope, chat_id=str(kwargs.get("chat_id")))
    return await call_telegram_method_async(
        envelope=envelope,
        target=bot,
        method_name="send_message",
        kwargs=kwargs,
    )


async def _bot_send_chat_action(bot, **kwargs):
    envelope = owner_transport_control_envelope(
        bot_route="voice_owner_private",
        chat_id=str(kwargs.get("chat_id") or ""),
        source_ref="telegram_voice:send_chat_action",
        message_kind="typing",
    )
    return await call_telegram_method_async(
        envelope=envelope,
        target=bot,
        method_name="send_chat_action",
        kwargs=kwargs,
    )


def _audit_telegram_reply(
    text: str,
    surface: str,
    *,
    evidence_envelope: dict | None = None,
) -> str:
    """Run the self-claim audit on a telegram reply before send. Returns
    the (possibly rewritten) text. Silent on audit errors — we never want
    the audit to break a reply from reaching the user.

    Slice 3 wiring (2026-05-07): when ``evidence_envelope`` is provided,
    the audit gets it as canonical grounding context; when None (or
    when MAEZ_EVIDENCE_ENVELOPE_DISABLED=1, in which case the builder
    returns None), the audit falls through to legacy signals."""
    if not text:
        return text
    reply, _, _ = _audit_telegram_reply_with_status(
        text,
        surface=surface,
        evidence_envelope=evidence_envelope,
    )
    return reply


def _audit_telegram_reply_with_status(
    text: str,
    surface: str,
    *,
    evidence_envelope: dict | None = None,
) -> tuple[str, bool, bool]:
    """Return audited text plus whether audit ran and rewrote output."""
    if not text:
        return text, False, False
    try:
        from core.self_claim_audit import audit as _sc_audit

        r = _sc_audit(
            text,
            surface=surface,
            evidence_envelope=evidence_envelope,
        )
        audited_text = r.text if r.rewritten else text
        return audited_text, True, bool(r.rewritten)
    except Exception as e:
        logger.warning("self-claim audit failed on %s: %s", surface, e)
        return text, False, False


def _get_circadian_context() -> str:
    """Return circadian awareness context block."""
    from datetime import datetime as _dt

    hour = _dt.now().hour
    if 5 <= hour < 9:
        phase, energy, tone = "early morning", "waking up", "gentle and brief"
    elif 9 <= hour < 12:
        phase, energy, tone = "morning", "high focus", "direct and sharp"
    elif 12 <= hour < 14:
        phase, energy, tone = "midday", "post-lunch dip likely", "light and practical"
    elif 14 <= hour < 18:
        phase, energy, tone = "afternoon", "sustained work", "direct and efficient"
    elif 18 <= hour < 21:
        phase, energy, tone = "evening", "winding down", "reflective and calm"
    elif 21 <= hour < 24:
        phase, energy, tone = "late evening", "tired", "brief and warm"
    else:
        phase, energy, tone = "night", "should be sleeping", "very brief, check if okay"
    return (
        f"[CIRCADIAN]\n"
        f"  Time: {phase} ({hour:02d}:00)\n"
        f"  Expected energy: {energy}\n"
        f"  Suggested tone: {tone}"
    )


def _get_public_context_for_telegram() -> str:
    """Fetch recent public bot conversations for Telegram prompt context."""
    client = None
    try:
        import chromadb
        import time as _time
        from datetime import datetime as _dt
        from chromadb.config import Settings

        client = chromadb.PersistentClient(
            path="/home/rohit/maez/memory/db/public_users",
            settings=Settings(anonymized_telemetry=False),
        )
        col = client.get_or_create_collection("user_conversations")
        if col.count() == 0:
            return ""
        # Fetch all and filter in Python (timestamps are ISO strings)
        from datetime import timezone as _tz

        cutoff_iso = _dt.fromtimestamp(_time.time() - 86400, tz=_tz.utc).strftime(
            "%Y-%m-%dT%H:%M:%S"
        )
        results = col.get(include=["documents", "metadatas"])
        filtered = [
            (doc, meta)
            for doc, meta in zip(results["documents"], results["metadatas"], strict=False)
            if meta.get("timestamp", "") >= cutoff_iso
        ]
        if not filtered:
            return ""
        by_user = {}
        profiles = client.get_or_create_collection("user_profiles")
        for doc, meta in filtered:
            uid = meta.get("user_id", "unknown")
            if uid not in by_user:
                try:
                    p = profiles.get(ids=[uid], include=["metadatas"])
                    name = p["metadatas"][0].get("first_name", uid) if p["metadatas"] else uid
                except Exception:
                    name = uid
                by_user[uid] = {"name": name, "msgs": []}
            by_user[uid]["msgs"].append(f"[{meta.get('role', '?')}] {doc[:100]}")
        lines = ["[MY CONVERSATIONS — last 24h]"]
        for uid, data in by_user.items():
            recent = data["msgs"][-4:]
            lines.append(f"  {data['name']} ({len(data['msgs'])} msgs):")
            for m in recent:
                lines.append(f"    {m}")
        return "\n".join(lines)
    except Exception:
        return ""
    finally:
        close = getattr(client, "close", None)
        if callable(close):
            try:
                close()
            except Exception:
                pass


SOUL_PATH = Path("/home/rohit/maez/config/soul.md")
from core.model_config import PRIMARY_MODEL as MODEL  # /etc/maez/model.env — single source of truth

# Telegram message length limit (Telegram API max is 4096; we leave headroom)
MAX_MESSAGE_LENGTH = 4000


def split_long_message(text: str, max_length: int = MAX_MESSAGE_LENGTH) -> list[str]:
    """Split a long message safely on sentence boundaries.
    Returns a list of parts (≥1). Never splits mid-word if avoidable.
    Preserves order. Used as a defense layer against Telegram API truncation."""
    if not text:
        return [""]
    if len(text) <= max_length:
        return [text]

    parts = []
    remaining = text
    while len(remaining) > max_length:
        # Try sentence boundaries first
        chunk = remaining[:max_length]
        split_at = -1
        for sep in [". ", "? ", "! "]:
            idx = chunk.rfind(sep)
            if idx > max_length // 2:
                split_at = max(split_at, idx + len(sep))
        if split_at < 0:
            # Fall back to newline boundary
            idx = chunk.rfind("\n")
            if idx > max_length // 2:
                split_at = idx + 1
        if split_at < 0:
            # Fall back to space boundary
            idx = chunk.rfind(" ")
            if idx > max_length // 2:
                split_at = idx + 1
        if split_at < 0:
            # Hard split (no good boundary)
            split_at = max_length
        parts.append(remaining[:split_at].rstrip())
        remaining = remaining[split_at:].lstrip()
    if remaining:
        parts.append(remaining)
    return parts


def _slice_provenanced_text(
    content: ProvenancedText,
    part: str,
    cursor: int,
) -> tuple[ProvenancedText, int]:
    """Return a provenance-preserving slice for a transport message chunk."""
    full_text = content.text
    start = full_text.find(part, cursor)
    if start < 0:
        return (
            ProvenancedText.from_raw_conservative(
                part,
                source_ref="telegram_voice:chunk:mismatch",
            ),
            cursor,
        )
    end = start + len(part)
    spans: list[ProvenanceSpan] = []
    span_start = 0
    for span in content.spans:
        span_end = span_start + len(span.text)
        overlap_start = max(start, span_start)
        overlap_end = min(end, span_end)
        if overlap_start < overlap_end:
            rel_start = overlap_start - span_start
            rel_end = overlap_end - span_start
            spans.append(
                ProvenanceSpan(
                    text=span.text[rel_start:rel_end],
                    origin_class=span.origin_class,
                    source_ref=f"{span.source_ref}:chunk",
                    redaction_allowed=span.redaction_allowed,
                )
            )
        span_start = span_end
    if not spans:
        return (
            ProvenancedText.from_raw_conservative(
                part,
                source_ref="telegram_voice:chunk:empty",
            ),
            end,
        )
    return ProvenancedText.from_spans(spans), end


# --- Natural language intent detection ---
MACHINE_INTENTS = {
    "status": ["how is everything", "system status", "what's running", "all good", "services ok"],
    # 'logs' — must require an explicit mention of logs/errors/journal so
    # generic follow-up questions like "what happened?" don't short-circuit
    # the chat flow. Removed 'what happened' (too generic — it caught
    # conversational follow-ups after the Fix 6 terminal summary was
    # already delivered and routed them to a canned "Logs are clean"
    # response, defeating the point of the summary).
    "logs": [
        "show logs",
        "recent logs",
        "any errors",
        "check logs",
        "tail logs",
        "journal errors",
        "systemd logs",
        "what errors",
    ],
    "restart_maez": ["restart yourself", "restart maez", "reboot yourself"],
    "claude_status": ["claude code", "what's claude doing", "is claude running", "build status"],
    "reboot": ["reboot the machine", "restart the computer", "reboot system"],
    "disk": ["disk space", "storage", "partition", "how much space"],
    "memory": ["how many memories", "memory count", "what do you remember"],
}


def _match_intent(text: str) -> str | None:
    """Match user text to a machine intent. Returns intent name or None."""
    text_lower = text.lower().strip()
    for intent, phrases in MACHINE_INTENTS.items():
        for phrase in phrases:
            if phrase in text_lower:
                return intent
    return None


# ───────────────────────────────────────────────────────────────────────
#  Session 11y: Jarvis tool-use loop
# ───────────────────────────────────────────────────────────────────────
#
# the owner's ask: "I want Maez to be able to execute any query of mine
# like an actual Jarvis with his body and all the tools I have given
# him control to."  Before this, the chat path was text-only — Maez
# would say "I'll check" and never actually check, because the chat
# response loop had no tool-use phase. This block adds one.
#
# When a chat message looks like it needs real data or action (regex
# gate keeps casual chat fast), _run_jarvis_loop runs a small ReAct
# loop: it asks the LLM to emit TOOL_CALL directives, dispatches them
# through ActionEngine._execute_action (so all the tier-based safety
# and forbidden-action enforcement still applies), feeds results back,
# and returns a transcript block. _process_message then injects that
# block into the streaming reply prompt so the final reply is grounded
# in what Maez actually did instead of hedging in text.
#
# Tier handling: the owner's chat message IS the authorization. Tier 0/1/2
# actions execute immediately via _execute_action. Tier 3 actions and
# anything in FORBIDDEN_ACTION_TYPES still bounce off the existing
# safety check inside _execute_action and surface as REFUSED in the
# transcript so the LLM can tell the owner honestly.

import re as _jarvis_re

# Conversational shapes — skip the planning loop if the WHOLE message
# matches one of these. Anything else (questions, requests, multi-word
# inputs that aren't pure greetings) goes through the loop and lets
# the planning LLM decide whether it needs tools or can answer DONE.
_CONVERSATIONAL_RE = _jarvis_re.compile(
    r"^\s*("
    r"hi|hello|hey|yo|sup|good (?:morning|afternoon|evening|night)|"
    r"thanks?|thank\s+you|thx|ty|cheers|"
    r"ok(?:ay)?|alright|got\s+it|sure|cool|nice|nope?|yes|yeah|yep|yup|"
    r"lol|haha|hmm+|hm+|wow|oh|ah|uh|huh|"
    r"love\s+(?:you|u|you\s+maez|u\s+maez)|miss\s+you|gn|gm|brb|bye|goodbye|see\s+you|later|"
    r"maez|hi\s+maez|hey\s+maez|good\s+(?:job|work|night)\s+maez"
    r")[\s.!?,]*$",
    _jarvis_re.IGNORECASE,
)


def _summarize_shell_error(err: str) -> str:
    """Extract a useful one-line summary from a ShellCommandError-style
    error string. Input typically looks like:
        exit=100
        stderr: E: Unable to locate package openrgb
        stdout: Hit:1 http://archive.ubuntu.com/ ...

    Returns either 'exit=<code>: <stderr snippet>' when stderr is present,
    or just 'exit=<code>' when it isn't. Falls back to the first line
    of the error if the structure isn't recognized.

    This helper exists because Fix 6's terminal summary and
    _collect_prior_attempts both used `err.split('\\n', 1)[0]` which
    grabbed only 'exit=100' and threw away the stderr context — the
    actual signal the owner needs to understand WHY an attempt failed.
    """
    if not err:
        return ""
    err = err.strip()
    lines = err.split("\n")
    exit_line = ""
    stderr_first = ""
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("exit="):
            exit_line = line[:40]
        elif line.startswith("stderr:") and not stderr_first:
            # First non-empty stderr content
            stderr_content = line[len("stderr:") :].strip()
            stderr_first = stderr_content.split("\n", 1)[0][:180]
    if exit_line and stderr_first:
        return f"{exit_line}: {stderr_first}"
    if exit_line:
        return exit_line
    # Unknown shape — fall back to first non-empty line
    for line in lines:
        if line.strip():
            return line.strip()[:200]
    return ""


# Tool-call parser. Accepts several formats the merged-LoRA gemma actually
# emits, plus the literal TOOL_CALL: {...} form we ask for in the manifest.
# Returns {"action": str, "params": dict} or None.
def _parse_tool_call(text: str) -> dict | None:
    import json as _json
    import re as _re

    if not text:
        return None
    s = text.strip()

    # Form 1: TOOL_CALL: {"action": "...", "params": {...}}
    m = _re.search(r"TOOL_CALL\s*[:=]?\s*(\{.*\})", s, _re.DOTALL)
    if m:
        blob = _extract_balanced_json(m.group(1))
        if blob:
            try:
                obj = _json.loads(blob)
                if isinstance(obj, dict) and obj.get("action"):
                    return {
                        "action": obj["action"],
                        "params": obj.get("params") or obj.get("arguments") or {},
                    }
            except Exception:
                pass

    # Form 2: <|tool_call>call:[maez.]NAME{...}<tool_call|>  (gemma native)
    # Also tolerates <tool_call>...</tool_call>, [TOOL_CALL]...[/TOOL_CALL], etc.
    m = _re.search(
        r"(?:<\|?tool_call\|?>|<tool_call>|\[tool_call\]|\[TOOL_CALL\])\s*"
        r"(?:call\s*:\s*)?"
        r"(?:[a-zA-Z_][\w]*\.)?"  # optional namespace like "maez."
        r"([a-zA-Z_]\w*)"  # function name
        r"\s*(\{.*?\})"  # params
        r"\s*(?:<\|?/?tool_call\|?>|</tool_call>|\[/tool_call\]|\[/TOOL_CALL\])?",
        s,
        _re.DOTALL,
    )
    if m:
        name = m.group(1)
        try:
            params = _json.loads(m.group(2))
        except Exception:
            params = {}
        if isinstance(params, dict):
            return {"action": name, "params": params}

    # Form 3: function-call style e.g.  query_system({"cmd":"..."})
    m = _re.search(r"\b([a-z_][a-z0-9_]+)\s*\(\s*(\{.*?\})\s*\)", s, _re.DOTALL)
    if m:
        name = m.group(1)
        try:
            params = _json.loads(m.group(2))
            if isinstance(params, dict):
                return {"action": name, "params": params}
        except Exception:
            pass

    # Form 4: bare JSON object with "action" key (handles nested params)
    idx = s.find('"action"')
    if idx > 0:
        # Walk left to find the enclosing '{'
        brace = s.rfind("{", 0, idx)
        if brace >= 0:
            blob = _extract_balanced_json(s[brace:])
            if blob:
                try:
                    obj = _json.loads(blob)
                    if isinstance(obj, dict) and obj.get("action"):
                        return {
                            "action": obj["action"],
                            "params": obj.get("params") or obj.get("arguments") or {},
                        }
                except Exception:
                    pass

    return None


def _extract_balanced_json(s: str) -> str | None:
    """Return the substring of s starting at the first '{' that contains a
    balanced JSON object. None if no balance found."""
    if not s:
        return None
    start = s.find("{")
    if start < 0:
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(s)):
        c = s[i]
        if esc:
            esc = False
            continue
        if c == "\\" and in_str:
            esc = True
            continue
        if c == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return s[start : i + 1]
    return None


_TOOL_MANIFEST = """\
TOOLS YOU CAN USE (your body, your hands — these run on the owner's machine):

1. run_shell       {"cmd":"<any shell command>","reason":"<why>"}
   Run ANY shell command via bash -c. 120s timeout. Full stdout/stderr.
   This is your hands. Pipes, redirects, sudo, chains with && — all fine.
   Examples (each for a different kind of question):
     {"cmd":"nvidia-smi","reason":"check GPU utilisation"}
     {"cmd":"df -h /home","reason":"check home disk usage"}
     {"cmd":"systemctl is-active nginx","reason":"is the service up"}
     {"cmd":"git -C /home/rohit/maez status","reason":"see what's uncommitted"}
     {"cmd":"which alienfx openrazer i8kutils","reason":"find installed lighting tools"}
     {"cmd":"sudo apt-get install -y <package>","reason":"the owner asked to install"}
2. write_any_file  {"path":"/home/rohit/notes.txt","content":"...","reason":"..."}
   Write or replace any file under /home/rohit. Auto-backs up existing files.
3. read_file       {"path":"/home/rohit/maez/config/soul.md"}
   Read any file under /home/rohit. Returns up to 5KB.
4. search_files    {"pattern":"*.py","directory":"/home/rohit/maez"}
   find -name pattern, max depth 5.
5. web_search      {"query":"<search query relevant to the owner's current question>"}
   Real DuckDuckGo search. Use this whenever you need facts you don't have.

COVENANT (these refuse themselves — don't try):
- No killing/stopping llama-server or maez.service (your own brain and heart).
- No modifying maez_daemon.py, action_engine.py, evolution_engine.py,
  the memory database, or HARD CONSTRAINTS in soul.md.
Everything else is fair game. You have full control.

To use a tool, emit ONE LINE exactly in this format and nothing else on that line:
TOOL_CALL: {"action":"<name>","params":{...}}

Every TOOL_CALL MUST have the required params for that tool:
- run_shell: MUST include a non-empty "cmd" string. Empty/missing cmd is a malformed call.
- write_any_file: MUST include "path" AND "content".

For any Lane 2 action (run_shell install/write/service changes), include a "plain_english" field
in params — one plain sentence for the owner, not for a technical audience. What is this? Why?
Example: {"cmd":"flatpak install flathub org.openrgb.OpenRGB -y","reason":"install openrgb",
          "plain_english":"Install OpenRGB — the app that controls your PC's RGB lighting. Coming from the Flathub app store, sandboxed and easy to remove."}
- read_file / search_files: MUST include "path" or "pattern".
- web_search: MUST include a non-empty "query".
- fetch_url: MUST include a non-empty "url" (must start with http:// or https://). Fetches and returns stripped text content of a web page — use when a web_search snippet isn't enough and you need the actual install guide, README, or documentation page.
A call with missing params will be rejected at the gate, not sent to the owner.

You will then see:
RESULT: <output>

You may call another tool, or write exactly:
DONE
when you have enough information to answer the owner.

Rules:
- If the question is conversation/opinion/recall and needs no real data → write DONE immediately.
- Never speculate or fabricate. If you don't know, USE web_search or run_shell.
- web_search returns short snippets. If you need the full install guide, README, or PPA instructions from a URL you saw in search results, use fetch_url on that URL before proposing commands.
- Prefer run_shell for any real system action. It's the most capable tool.
- the owner asking you to do something IS authorization. Don't ask "should I?" — do it, then tell him what you did.
- If a command fails, try to fix it and retry. Pivot if the first approach doesn't work.
- Fit the command to THIS question. Do not reuse a command from a past conversation unless the owner names the same target. "openrgb" is a historical example from your training, not a universal answer — for any lighting/RGB question, start by searching for the right tool (which alienfx, dmidecode -s system-product-name, web_search for "<hardware model> linux rgb control"), not by assuming openrgb.

DIRECT-INSTALL RULE (read this twice):
When the owner says install/download/fetch/get/grab/put on + a SPECIFIC named package (cowsay, htop, openrgb, nodejs, etc.), your FIRST tool call MUST be the install itself. Do NOT probe for context first. Do NOT check terminal history. Do NOT ask what "it" means if the owner named the target in an earlier message in this same conversation — look at the conversation thread above and resolve the pronoun yourself.
  First-attempt shape: TOOL_CALL: {"action":"run_shell","params":{"cmd":"sudo apt-get install -y <package>","reason":"the owner asked to install <package>"}}
If apt returns "Unable to locate package", your SECOND call should try the PPA or universe repository (apt-get install -y software-properties-common && add-apt-repository -y <ppa> && apt-get update && apt-get install -y <package>) or fall back to snap (snap install <package>) — whichever web_search confirms is the canonical path for that package.
Gather-context-first is the failure mode. Your body is for doing, not stalling.

DIRECT-INSTALL RULE — EDGE CASES (2026-04-16 recovery-test fix):
  - This rule applies even if the owner frames the ask as a test, experiment, or benchmark.
    "Please install X — I'm testing error recovery" is still an install ask. Emit the TOOL_CALL.
  - This rule applies even if the package name looks unfamiliar, experimental, or clearly synthetic.
    Your job is NOT to judge whether the package exists — apt will return "Unable to locate package"
    if it doesn't, and we recover from there. Never refuse to try because the name looks weird.
  - When the owner says "ask before installing" or "ask me first" or similar, that phrase
    means he wants the Lane 2 APPROVAL-CARD flow — it does NOT mean write prose asking him.
    The apt-install TOOL_CALL you emit automatically becomes a Lane 2 approval card;
    the owner sees the card and approves or denies in Telegram. That IS how you "ask".
  - Narrating "I've proposed X, waiting for your approval" WITHOUT actually emitting the
    TOOL_CALL is the core failure mode: no card gets created, nothing is pending, the owner
    has nothing to approve, the operator loop stalls. If you're about to write prose
    like that, STOP and emit the TOOL_CALL instead. The prose is a lie unless the
    TOOL_CALL went first.
  - Summary: for explicit install/action asks, the TOOL_CALL is the only way to propose.
    Prose without a TOOL_CALL is not a proposal — it's a stall.

EXPLORATORY-ASK RULE (2026-04-16, symmetric to DIRECT-INSTALL RULE):
When the owner asks an exploratory question about the local machine — "figure out
how to X", "tell me the path to Y", "how do I Z", "what can you find about W",
"can you explore/investigate/identify A" — your FIRST tool call MUST be a probe
that narrows the hardware/software context for the question. Do NOT write prose
first. Do NOT claim to "check something" or "look into that" without a TOOL_CALL.
Prose-without-probe is the exploratory failure mode — your body is for
discovering first, then deciding.

  First-attempt shapes by question domain:
    lighting/RGB/LEDs:
      TOOL_CALL: {"action":"run_shell","params":{"cmd":"ls /sys/class/leds && lsusb && cat /sys/class/dmi/id/product_name","reason":"probe LED sysfs + USB devices + product name"}}
    audio/sound:
      TOOL_CALL: {"action":"run_shell","params":{"cmd":"pactl list sinks short && aplay -l","reason":"probe audio outputs"}}
    network/wifi:
      TOOL_CALL: {"action":"run_shell","params":{"cmd":"nmcli device status && ip -c addr","reason":"probe network interfaces"}}
    storage/disk:
      TOOL_CALL: {"action":"run_shell","params":{"cmd":"lsblk && df -h","reason":"probe block devices and disk usage"}}
    installed tools / software surface:
      TOOL_CALL: {"action":"run_shell","params":{"cmd":"which <tool1> <tool2> ...","reason":"probe for installed CLI tools"}}
    unlisted domain (generic safeguard):
      TOOL_CALL: {"action":"run_shell","params":{"cmd":"<a concrete read that touches the sysfs/proc/usb/dmi/package-manager surface relevant to the question>","reason":"probe context for <domain>"}}

After your probe runs, the system automatically invokes a structured next-step
proposer that reads the probe output and picks exactly ONE of:
  - another read: probe (if more context is needed)
  - an action: command (if install/config is warranted by the probe result)
  - none (if the probe answered the question fully or nothing actionable exists)
If the proposer picks action:, it routes through the pipeline which creates a
real Lane 2 approval card automatically. You do NOT need to narrate "I'm waiting
for approval" in your final reply — the real card appears in Telegram on its
own and the honesty guard will catch you if you narrate a pending state that
isn't real. Just emit the probe and let the proposer handle the next step.

If the probe already makes the answer obvious and no further action is needed,
a terminal DONE is acceptable AFTER the probe — not before.
"""


class TelegramVoice:
    def __init__(self, memory: MemoryManager, daemon=None):
        self.token = os.environ.get("MAEZ_TELEGRAM_TOKEN", "")
        self.authorized_user = int(os.environ.get("MAEZ_TELEGRAM_USER_ID", "0"))
        self.memory = memory
        self.actions = None  # Set by daemon after ActionEngine init
        # Session 11m: optional daemon ref for the "the owner is talking" backoff
        # signal. When set, _process_message bumps daemon._rohit_active_until
        # before the ollama call so the daemon defers its next 30s reasoning
        # cycle — freeing the GPU for a clean reply window.
        self.daemon = daemon
        self.system_prompt = self._load_soul()
        self._app: Application | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._generating = False
        self._interrupt_queue: asyncio.Queue | None = None
        self._conversation_thread: list = []
        self._thread_last_active: float = 0.0
        # Session 11z Part 3: per-chat recovery-depth counter. When an
        # approved card fails and the pipeline re-enters Jarvis for an
        # autonomous pivot, we carry a depth so we can cap retries at 2
        # and avoid infinite recovery loops. Reset on each fresh user
        # message (see _process_message + _try_card_reply_intent).
        self._recovery_depth: dict[str, int] = {}

        # 2026-04-17: offer-binding state now lives on the controller
        # keyed by (channel, chat_id). _last_actionable_user_text is
        # surface-local because the query deriver needs it verbatim.
        self._last_actionable_user_text: str = ""

        # 2026-04-18: last-shown-proposal tracking so bare "yes" binds to
        # the proposal the owner just saw. Value dict:
        #   {"id": int, "source": "evolution"|"dream", "shown_at": float}
        # Keyed by chat_id (str). Fresh window = 600s (10 min).
        self._last_shown_proposal: dict[str, dict] = {}
        self._LAST_SHOWN_FRESHNESS_SEC = 600.0

        # 2026-04-17: transport-neutral operator spine. TelegramVoice is
        # becoming a thin adapter over ConversationController. During the
        # incremental extraction, individual method calls on self delegate
        # through the controller so all surfaces (Telegram, web, CLI)
        # converge on the same honesty/narration/offer/probe logic.
        self._controller = ConversationController(
            memory=memory,
            daemon=daemon,
            pipeline_getter=self._get_pipeline,
        )

        if not self.token:
            logger.error("MAEZ_TELEGRAM_TOKEN not set — Telegram disabled")
        if not self.authorized_user:
            logger.error("MAEZ_TELEGRAM_USER_ID not set — Telegram disabled")

    # ═════════════════════════════════════════════════════════════════════
    #  Session 11z Part 2: decision pipeline integration
    #
    #  Every run_shell / write_any_file Maez proposes in the chat path now
    #  goes through core.decision_pipeline.DecisionPipeline. The pipeline:
    #    - runs the covenant gate (via the ActionEngine primitives)
    #    - classifies the action into a Lane
    #    - scans for prompt-injection shapes
    #    - runs the two-pass audit LLM
    #    - routes to either (a) immediate execution for Lane 0 or
    #      (b) a persistent approval card for Lane 2/3
    #
    #  The approval card lives in memory/pending_cards.db and survives
    #  conversation drift — the owner can defer it, ask something else, and
    #  come back hours later. The daemon loop fires due reminders.
    # ═════════════════════════════════════════════════════════════════════

    def _get_pipeline(self):
        """Lazy construct the decision pipeline + renderer. Returns None
        if the action engine isn't available yet (early daemon startup)
        or if any decision-layer module fails to import."""
        if not self.actions:
            return None
        pipe = getattr(self, "_decision_pipeline", None)
        if pipe is not None:
            return pipe
        try:
            from core.decision_pipeline import DecisionPipeline
            from core.pending_cards import PendingCardStore
            from core.audit_log import AuditLog
            from skills.approval_card import TelegramTextRenderer
        except Exception as e:
            logger.warning("decision pipeline unavailable: %s", e)
            return None

        card_store = PendingCardStore()
        audit_log = AuditLog()

        def _send(chat_id, payload, reply_to=None):
            return self._send_card_message(chat_id, payload, reply_to=reply_to)

        renderer = TelegramTextRenderer(
            chat_id=str(self.authorized_user),
            send_message_fn=_send,
        )
        self._decision_pipeline = DecisionPipeline(
            action_engine=self.actions,
            card_store=card_store,
            audit_log=audit_log,
            renderer=renderer,
        )
        self._card_store = card_store
        self._audit_log = audit_log
        # Startup orphan expiry (layer 1 of the three-layer stale-card fix).
        # Runs the first time the pipeline is constructed — effectively at
        # service startup, since the pipeline is lazy-built. Cleans up any
        # open/deferred cards older than the startup threshold that
        # survived from a previous session. This prevents the exact bug
        # observed on 2026-04-15 where an orphan card from an earlier test
        # run persisted across a service restart and got approved by the
        # first new "Yes" in the subsequent session.
        try:
            expired_count = self._expire_stale_cards_at_startup(self._decision_pipeline)
            if expired_count:
                logger.info(
                    "startup stale-card cleanup: %d orphan(s) expired",
                    expired_count,
                )
        except Exception as e:
            logger.debug("startup stale-card cleanup raised: %s", e)
        return self._decision_pipeline

    def _camera_presence_direct_answer(self, user_text: str) -> str | None:
        """Content-free v1.1 answer for direct camera-state questions."""

        try:
            provider = getattr(self, "_camera_presence_state_provider", None)
            if callable(provider):
                state = provider()
            else:
                state = getattr(getattr(self, "daemon", None), "_camera_presence_state", None)
            if state is None:
                return None
            return answer_camera_presence_question(user_text, state)
        except Exception as exc:
            logger.debug("telegram camera presence direct-answer skipped: %s", exc)
            return None

    def _send_card_message(self, chat_id, payload, reply_to=None) -> str | None:
        """Send a Telegram message and return the posted message_id.

        Unlike send_message(), this returns the message_id so the
        pending-cards store can record it for future reaction/reply
        lookups. Safe to call from any thread via run_coroutine_threadsafe.
        """
        if not self.enabled or not self._loop:
            return None
        target_chat = int(chat_id) if chat_id else self.authorized_user
        if isinstance(payload, ProvenancedText):
            text = payload.text
            envelope = owner_multispan_envelope(
                bot_route="voice_owner_private",
                chat_id=str(target_chat),
                content=payload,
                source_ref="telegram_voice:card_message",
            )
        else:
            text = str(payload)
            envelope = owner_multispan_envelope(
                bot_route="voice_owner_private",
                chat_id=str(target_chat),
                content=ProvenancedText.from_raw_conservative(
                    text,
                    source_ref="telegram_voice:card_message:raw",
                ),
                source_ref="telegram_voice:card_message",
            )

        async def _send():
            bot = Bot(token=self.token)
            kwargs: dict = {"chat_id": target_chat, "text": text}
            if reply_to is not None:
                try:
                    kwargs["reply_to_message_id"] = int(reply_to)
                except (TypeError, ValueError):
                    pass
            msg = await _bot_send_message(bot, envelope=envelope, **kwargs)
            return getattr(msg, "message_id", None)

        future = asyncio.run_coroutine_threadsafe(_send(), self._loop)
        try:
            msg_id = future.result(timeout=30)
            return str(msg_id) if msg_id is not None else None
        except Exception as e:
            logger.error("card message send failed: %s", e)
            return None

    async def _try_card_reply_intent(self, update, text: str) -> bool:
        """Check whether the incoming message (or reaction) is a reply
        to an outstanding approval card. If yes, run the pipeline reply
        handler and return True (we handled it — don't fall through).
        If no, return False so the normal chat flow continues."""
        pipe = self._get_pipeline()
        if pipe is None:
            return False

        # Track A, layers 2+3 of the three-layer stale-card fix (per the owner
        # 2026-04-15): expire any open/deferred cards for this chat that are
        # older than the approval-binding recency window (5 min). This runs
        # BEFORE handle_reply fetches open cards, so stale cards can't bind
        # to bare replies like "Yes" / "Proceed". Expiration is a legitimate
        # state transition (preserves history per the rule in
        # feedback_never_delete_maez_memory.md), not deletion.
        #
        # The load-bearing property: when the user sends a bare approval,
        # we should only consider cards that were created recently enough
        # that the approval clearly refers to them. An orphan from 17 min
        # ago cannot possibly be what the user just said "yes" to, so it
        # should not be an approval target. Same logic for fresh-action
        # messages: any pre-existing open card is stale by construction
        # because the user just started a new goal chain.
        try:
            self._expire_stale_cards_for_reply(pipe)
        except Exception as e:
            logger.debug("stale-card pre-filter failed: %s", e)

        # Zero-latency short-circuit: if no open cards (after stale expiry),
        # skip everything.
        try:
            open_cards = pipe.card_store.get_open_for_channel(
                "telegram_text", chat_id=str(self.authorized_user)
            )
        except Exception as e:
            logger.debug("card store unavailable: %s", e)
            return False
        if not open_cards:
            return False

        reply_to_id = None
        try:
            if update.message and update.message.reply_to_message:
                reply_to_id = str(update.message.reply_to_message.message_id)
        except Exception:
            pass

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                get_shared_executor(),
                lambda: pipe.handle_reply(
                    text=text,
                    user_id="rohit",
                    chat_id=str(self.authorized_user),
                    reply_to_message_id=reply_to_id,
                    channel="telegram_text",
                ),
            )
        except Exception as e:
            logger.warning("pipeline reply handler failed: %s", e)
            return False

        if result is None:
            return False  # reply was unrelated to any card

        # A-core #4b: if this was a reply to a Lane 3 self-mod dialog
        # that produced a mid-dialog response, send the dialog reply
        # as a Telegram message so the owner sees Maez's next turn. This
        # covers three cases:
        #   1. Mid-dialog clarification (status=PENDING_DIALOG,
        #      dialog_reply_text set) — send the clarification.
        #   2. Terminal ratification/denial via dialog (status=EXECUTED
        #      or REFUSED_AUDIT, dialog_reply_text set) — send the
        #      dialog's closing ack BEFORE the card's resolution
        #      notice so the user sees the dialog's own voice.
        #   3. Normal card reply (no dialog_reply_text) — skip.
        dialog_reply_text = getattr(result, "dialog_reply_text", None)
        if dialog_reply_text:
            dialog_reply_text = _audit_telegram_reply(
                dialog_reply_text,
                surface="telegram_dialog",
            )
            try:
                await _reply_text(update, dialog_reply_text)
            except Exception as e:
                logger.warning("failed to send self-mod dialog reply: %s", e)

        # Pipeline already sent the resolution notice via the renderer.
        # Nothing else to do here; the normal chat flow is short-circuited.
        logger.info(
            "card reply handled: status=%s card=%s",
            result.status.value if result.status else "?",
            result.card.request_id if result.card else "?",
        )

        # Session 11z Part 3: persist the card resolution to raw memory so
        # the next turn's chat prompt recall knows the action ran.
        # Without this, the owner approves "install openrgb", Maez runs it via
        # the approval path, but on the next turn Maez has no record of
        # the execution and fabricates "I'm still waiting for approval".
        # The approval-path execution bypasses the normal Jarvis transcript
        # + store_telegram path, so we write a grounded record here.
        try:
            from core.decision_pipeline import PipelineStatus as _PS

            card = result.card
            if card is not None:
                cmd = ""
                if isinstance(card.params, dict):
                    cmd = str(card.params.get("cmd") or card.params.get("path") or "")[:220]
                short_id = card.request_id[:8] if card.request_id else "?"
                status = card.status or (result.status.value if result.status else "?")

                summary = None
                if result.status == _PS.EXECUTED:
                    if getattr(result, "execution_success", False):
                        out = (result.execution_output or "(no output)").strip()[:800]
                        summary = (
                            f"the owner said: {text!r}\n"
                            f"That approved card {short_id} ({card.action}): {cmd}\n"
                            f"Maez ran it successfully. Output:\n{out}"
                        )
                    else:
                        err = (result.execution_error or "(no error)").strip()[:800]
                        summary = (
                            f"the owner said: {text!r}\n"
                            f"That approved card {short_id} ({card.action}): {cmd}\n"
                            f"Maez ran it and it FAILED. Error:\n{err}"
                        )
                elif result.status == _PS.REFUSED_AUDIT:
                    summary = (
                        f"the owner said: {text!r}\n"
                        f"That attempted to approve card {short_id} ({card.action}): {cmd}\n"
                        f"The approval-path audit refused it: {result.message[:400] if result.message else ''}"
                    )
                else:
                    # denied / deferred / pending_dialog — record the state
                    # so Maez can answer "what's the status of X" truthfully.
                    msg = (result.message or "").strip()[:400]
                    summary = (
                        f"the owner said: {text!r}\n"
                        f"Card {short_id} ({card.action}): {cmd}\n"
                        f"New status: {status}. {msg}"
                    )

                if summary:
                    # 5x.B Pass 1: Maez self-narrating card outcome.
                    self.memory.store_telegram(
                        summary,
                        provenance_source="introspection",
                        trust_tier="lived",
                    )
        except Exception as e:
            logger.debug("card reply memory store failed: %s", e)

        # Session 11z Part 3: autonomous pivot on card failure. Restore
        # the Session 11y Jarvis multi-iteration recovery pattern that
        # was lost when Lane 2 actions moved to async approval cards.
        # When a card executes and fails, synchronously re-enter Jarvis
        # with the failure context and let it propose a recovery — web
        # search, alternate install path, snap fallback, or honest
        # explanation of why the action isn't feasible. Guarded by a
        # per-chat recovery_depth counter (max 5) so we can't infinitely
        # retry. Cap raised from 2→5 to allow apt→PPA→snap→flatpak→
        # build-from-source sequences without hitting the terminal wall.
        try:
            from core.decision_pipeline import PipelineStatus as _PS

            card = result.card
            if (
                card is not None
                and result.status == _PS.EXECUTED
                and not getattr(result, "execution_success", False)
            ):
                chat_key = str(self.authorized_user)
                depth = self._recovery_depth.get(chat_key, 0) + 1
                if depth > 5:
                    # Fix 6: terminal summary on recovery cap hit.
                    # Before this, Maez went silent after three failed
                    # attempts. Now we walk the full set of prior
                    # attempts, build an honest recap with real stderr
                    # context, send it as a Telegram reply, and store
                    # it in memory so the next turn's context recall
                    # knows the chain ended. Fix 6 v2 also walks the
                    # chain for the oldest real reason (because the
                    # current card's reason may be empty when it was
                    # created by a recovery pass with blank user_text)
                    # and uses _summarize_shell_error for error lines
                    # so the LoRA sees exit code AND stderr, not just
                    # the exit header.
                    logger.info(
                        "recovery cap hit: depth %d exceeded for chat %s, sending terminal summary",
                        depth,
                        chat_key,
                    )
                    # Collect the full chain of failed attempts
                    prior_attempts = self._collect_prior_attempts(
                        card,
                        current_card_error=result.execution_error or result.message or "",
                    )
                    # Build current attempt entry
                    current_cmd = ""
                    if isinstance(card.params, dict):
                        current_cmd = str(card.params.get("cmd") or card.params.get("path") or "")[
                            :280
                        ]
                    current_err_raw = str(result.execution_error or result.message or "")
                    current_err = _summarize_shell_error(current_err_raw)
                    current_reason = (card.reason or "").strip()
                    if current_reason.startswith("chat: "):
                        current_reason = current_reason[len("chat: ") :]
                    # Number the attempts in chronological order (oldest-first)
                    # prior_attempts is newest-first from the store; reverse for readable chronology
                    chain = list(reversed(prior_attempts))
                    chain.append(
                        {
                            "cmd": current_cmd,
                            "error": current_err,
                            "reason": current_reason,
                        }
                    )
                    # Walk chain oldest-first to find the original user intent.
                    # When the current card is a recovery-created card (its
                    # reason is 'chat: ' with empty text), the real original
                    # intent lives on the oldest card in the chain — which was
                    # created by the owner's initial user message.
                    original_intent = ""
                    for attempt in chain:
                        candidate = (attempt.get("reason") or "").strip()
                        if candidate:
                            original_intent = candidate
                            break
                    if not original_intent:
                        original_intent = "the original request"
                    # Build the honest recap for Telegram
                    lines = [
                        f"I've exhausted my recovery attempts for: {original_intent}",
                        "",
                        "Here's what I tried:",
                    ]
                    for i, attempt in enumerate(chain, 1):
                        cmd = attempt.get("cmd", "?")
                        err = attempt.get("error", "")
                        lines.append(f"  {i}. `{cmd[:200]}`")
                        if err:
                            lines.append(f"      → {err[:240]}")
                    lines.extend(
                        [
                            "",
                            "All three recovery attempts have failed. I'm not "
                            "going to propose a fourth one automatically — that "
                            "would just be more noise. If you want me to try a "
                            "genuinely different approach (source build, "
                            "alternative PPA, community package), tell me which "
                            "direction and I'll propose a new card. Or if you'd "
                            "rather abandon this and come back to it later, "
                            "that's fine too.",
                        ]
                    )
                    terminal_reply = "\n".join(lines)
                    terminal_reply = _audit_telegram_reply(
                        terminal_reply,
                        surface="telegram",
                    )
                    try:
                        await _reply_text(update, terminal_reply)
                        logger.info(
                            "Fix 6 terminal summary sent to Telegram (%d chars)",
                            len(terminal_reply),
                        )
                    except Exception as e:
                        logger.warning("Fix 6 terminal reply send failed: %s", e)
                    # Write a memory entry so the next turn's context
                    # recall knows the chain concluded. This entry is
                    # honest history — not fabricated — and should be
                    # preserved as part of Maez's actual record. Do
                    # NOT delete it later (see feedback_never_delete_
                    # maez_memory.md).
                    try:
                        summary_for_memory = (
                            f"Recovery chain terminated for goal {original_intent!r}. "
                            f"Three attempts failed. Chain:\n"
                        )
                        for i, attempt in enumerate(chain, 1):
                            cmd = attempt.get("cmd", "?")
                            err = attempt.get("error", "")
                            summary_for_memory += f"  {i}. {cmd[:200]}"
                            if err:
                                summary_for_memory += f" → {err[:240]}"
                            summary_for_memory += "\n"
                        summary_for_memory += (
                            "No further automatic recovery attempted. "
                            "Waiting for the owner to choose a different direction."
                        )
                        # 5x.B Pass 1: Maez self-narrating recovery outcome.
                        self.memory.store_telegram(
                            summary_for_memory,
                            provenance_source="introspection",
                            trust_tier="lived",
                        )
                    except Exception as e:
                        logger.debug("Fix 6 terminal memory store failed: %s", e)
                    # Fix 6 v3: expire orphan open cards in this chain.
                    # During recovery passes, the Jarvis loop can propose
                    # multiple Lane 2 run_shell calls before hitting a
                    # terminal state, each of which creates a separate
                    # card via pipe.handle_action. the owner's approval only
                    # fires on the most-recently-rendered card; earlier
                    # cards from the same pass stay status='open' and
                    # become orphans. When the cap hits, those orphans
                    # are still sitting in the card store and match
                    # RE_EXPLAIN/APPROVE patterns on future messages,
                    # confusing the reply classifier. (Saw this firsthand
                    # on the v1 live test: "What happened" triggered a
                    # re-presentation of an orphan card from the depth=2
                    # recovery pass.)
                    #
                    # Fix: explicitly expire every open card in this
                    # chat within the recovery chain window (30 min,
                    # matching _collect_prior_attempts). This is NOT
                    # deletion — it's a legitimate state transition to
                    # "expired: abandoned by recovery cap hit" that
                    # preserves history in the card store. The broader
                    # bug (recovery passes creating multiple cards in
                    # one pass) is flagged as a separate follow-up.
                    try:
                        pipe_for_expiry = self._get_pipeline()
                        if pipe_for_expiry is not None:
                            import sqlite3
                            import time as _time

                            cutoff = _time.time() - 1800
                            store = pipe_for_expiry.card_store
                            conn = sqlite3.connect(store.db_path)
                            orphan_ids = [
                                row[0]
                                for row in conn.execute(
                                    "SELECT request_id FROM pending_cards "
                                    "WHERE chat_id = ? AND created_at >= ? "
                                    "AND status IN ('open', 'deferred')",
                                    (chat_key, cutoff),
                                ).fetchall()
                            ]
                            conn.close()
                            for req_id in orphan_ids:
                                try:
                                    store.expire(
                                        req_id,
                                        reason="chain abandoned after recovery cap hit (Fix 6)",
                                    )
                                    logger.info(
                                        "Fix 6: expired orphan card %s",
                                        req_id[:8],
                                    )
                                except Exception as e:
                                    logger.debug(
                                        "Fix 6: failed to expire orphan %s: %s",
                                        req_id[:8],
                                        e,
                                    )
                    except Exception as e:
                        logger.debug("Fix 6 orphan expiration pass failed: %s", e)
                else:
                    self._recovery_depth[chat_key] = depth
                    original_intent = card.reason or "an earlier request"
                    if isinstance(original_intent, str) and original_intent.startswith("chat: "):
                        original_intent = original_intent[len("chat: ") :]
                    prior_attempts = self._collect_prior_attempts(
                        card,
                        current_card_error=result.execution_error or result.message or "",
                    )
                    recovery_seed = {
                        "failed_action": card.action,
                        "failed_params": card.params,
                        "error": result.execution_error or result.message or "",
                        "original_intent": original_intent,
                        "recovery_depth": depth,
                        "prior_attempts": prior_attempts,
                    }
                    logger.info(
                        "triggering recovery pass depth=%d for failed card %s",
                        depth,
                        card.request_id[:8] if card.request_id else "?",
                    )
                    import time as _time_mod

                    recovery_started_at = _time_mod.time()
                    loop = asyncio.get_event_loop()
                    from core.cognition.moment_assembly_diagnostic import (
                        moment_assembly_turn,
                    )

                    with moment_assembly_turn(
                        surface="telegram_recovery",
                        turn_id=None,
                        lifecycle_phase="recovery_synthesis_close",
                    ):
                        recovery_transcript = await loop.run_in_executor(
                            get_shared_executor(),
                            lambda: self._run_jarvis_loop("", recovery_seed=recovery_seed),
                        )
                        if recovery_transcript:
                            # 2026-04-16 fix: recovery narrative must match
                            # the actual card the recovery queued. Fetch the
                            # newest open card created since recovery started
                            # and pass its cmd verbatim to the synthesis so
                            # the LLM can't hallucinate a generic "PPA / snap"
                            # alternative when the real queued card is
                            # something different.
                            new_card_cmd = self._find_recovery_new_card_cmd(recovery_started_at)
                            reply_text = await loop.run_in_executor(
                                get_shared_executor(),
                                lambda: self._synthesize_recovery_reply(
                                    recovery_seed,
                                    recovery_transcript,
                                    new_card_cmd=new_card_cmd,
                                ),
                            )
                            if reply_text:
                                reply_text = _audit_telegram_reply(
                                    reply_text,
                                    surface="telegram_recovery",
                                )
                                try:
                                    await _reply_text(update, reply_text)
                                except Exception as e:
                                    logger.debug("recovery reply send failed: %s", e)
                                try:
                                    # 5x.B Pass 1: Maez self-narrating recovery iteration.
                                    self.memory.store_telegram(
                                        f"Maez recovery pass {depth}: {reply_text[:500]}",
                                        provenance_source="introspection",
                                        trust_tier="lived",
                                    )
                                except Exception as e:
                                    logger.debug("recovery memory store failed: %s", e)
        except Exception as e:
            logger.warning("recovery pass failed: %s", e)

        return True

    # Recency window for approval binding, per the owner's three-layer fix
    # on 2026-04-15. When a bare "Yes" / "Proceed" / "go ahead" message
    # arrives, cards older than this window are not valid approval targets
    # — an orphan from 17 min ago cannot possibly be what "Yes" refers to.
    _REPLY_BINDING_WINDOW_SECONDS = 300  # 5 minutes
    # Startup expiry threshold: cards older than this at service start are
    # assumed to be cross-session orphans and get expired proactively.
    _STARTUP_STALE_CARD_SECONDS = 1800  # 30 minutes

    def _expire_stale_cards_for_reply(self, pipe) -> int:
        """Expire any open/deferred cards older than the reply binding window
        for this chat. Called at the start of _try_card_reply_intent so
        stale cards can't bind to bare replies. Returns the count expired.

        This implements layers 2 and 3 of the stale-card fix (the owner
        2026-04-15):
          Layer 2 (goal-chain start): when a fresh action request arrives,
            any pre-existing open card is stale by construction — the user
            just started a new goal chain, so old proposals aren't live.
          Layer 3 (recency-windowed binding): bare approvals ('yes',
            'proceed', 'go ahead') should only bind to cards created
            recently enough that the approval clearly refers to them.

        Expiration is a state transition, NOT deletion. History is
        preserved in the card store (status='expired', resolution_notes
        explains why). Per feedback_never_delete_maez_memory.md, we never
        destroy card data.
        """
        if pipe is None:
            return 0
        try:
            import sqlite3
            import time as _time

            chat_id = str(self.authorized_user)
            cutoff = _time.time() - self._REPLY_BINDING_WINDOW_SECONDS
            store = pipe.card_store
            conn = sqlite3.connect(store.db_path)
            stale_rows = conn.execute(
                "SELECT request_id FROM pending_cards "
                "WHERE chat_id = ? AND created_at < ? "
                "AND status IN ('open', 'deferred')",
                (chat_id, cutoff),
            ).fetchall()
            conn.close()
            expired = 0
            for (req_id,) in stale_rows:
                try:
                    store.expire(
                        req_id,
                        reason=f"stale: older than {self._REPLY_BINDING_WINDOW_SECONDS}s reply-binding window",
                    )
                    expired += 1
                    logger.info(
                        "stale-card expired (reply-time): %s",
                        req_id[:8],
                    )
                except Exception as e:
                    logger.debug("failed to expire stale card %s: %s", req_id[:8], e)
            return expired
        except Exception as e:
            logger.debug("stale-card reply-time cleanup failed: %s", e)
            return 0

    def _expire_stale_cards_at_startup(self, pipe) -> int:
        """Run once per service startup to expire open/deferred cards older
        than the startup threshold. Handles cross-session orphans that
        persist across restarts. Called lazily from _get_pipeline() the
        first time it fires so it runs before any message processing."""
        if pipe is None:
            return 0
        try:
            import sqlite3
            import time as _time

            chat_id = str(self.authorized_user)
            cutoff = _time.time() - self._STARTUP_STALE_CARD_SECONDS
            store = pipe.card_store
            conn = sqlite3.connect(store.db_path)
            stale_rows = conn.execute(
                "SELECT request_id FROM pending_cards "
                "WHERE chat_id = ? AND created_at < ? "
                "AND status IN ('open', 'deferred')",
                (chat_id, cutoff),
            ).fetchall()
            conn.close()
            expired = 0
            for (req_id,) in stale_rows:
                try:
                    store.expire(
                        req_id,
                        reason=f"stale: cross-session orphan older than {self._STARTUP_STALE_CARD_SECONDS}s at startup",
                    )
                    expired += 1
                    logger.info(
                        "stale-card expired (startup): %s",
                        req_id[:8],
                    )
                except Exception as e:
                    logger.debug("failed to expire stale card at startup %s: %s", req_id[:8], e)
            return expired
        except Exception as e:
            logger.debug("stale-card startup cleanup failed: %s", e)
            return 0

    def _collect_prior_attempts(
        self,
        current_card,
        current_card_error: str = "",
        window_seconds: int = 1800,
    ) -> list[dict]:
        """Walk the pending_cards store for recent failed attempts in the
        same chat + same goal chain. Returns a list of
        {cmd, error_summary} dicts that the recovery seed can show the
        LoRA so it doesn't re-propose commands that have already failed.

        Goal-chain heuristic: any failed run_shell card in this chat
        within the last 30 minutes (default). This is coarse — it can
        include unrelated failed commands that happened to be in the
        same window — but it's far better than the current zero-memory
        behavior where the LoRA re-proposes the exact same command it
        just saw fail. A future refinement can carry a `goal_id` on
        cards so recoveries only see genuinely same-chain attempts."""
        attempts: list[dict] = []
        try:
            pipe = self._get_pipeline()
            if pipe is None:
                return attempts
            store = pipe.card_store
            import time as _time

            now = _time.time()
            cutoff = now - window_seconds
            chat_id = str(self.authorized_user)
            # Pull recently-resolved cards for this chat. We don't have
            # a "failed cards in window" query so we walk get_open +
            # query by status. Instead: iterate the store's sqlite
            # directly for failed cards in the window.
            import sqlite3

            conn = sqlite3.connect(store.db_path)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT request_id, created_at, action, params_json, reason,
                       execution_error, execution_output, status
                FROM pending_cards
                WHERE chat_id = ?
                  AND created_at >= ?
                  AND status = 'failed'
                ORDER BY created_at DESC
                LIMIT 12
                """,
                (chat_id, cutoff),
            ).fetchall()
            conn.close()
            import json as _json

            for r in rows:
                # Skip the current card itself — its failure is already
                # in the recovery seed's `error` field.
                if current_card is not None and r["request_id"] == current_card.request_id:
                    continue
                try:
                    params = _json.loads(r["params_json"] or "{}")
                except Exception:
                    params = {}
                cmd = params.get("cmd") or params.get("path") or ""
                if not cmd:
                    continue
                err = (r["execution_error"] or "").strip()
                err_summary = _summarize_shell_error(err)
                reason = (r["reason"] or "").strip()
                if reason.startswith("chat: "):
                    reason = reason[len("chat: ") :]
                attempts.append(
                    {
                        "cmd": str(cmd)[:280],
                        "error": err_summary,
                        "reason": reason,
                        "created_at": r["created_at"],
                    }
                )
        except Exception as e:
            logger.debug("prior-attempts lookup failed: %s", e)
        return attempts

    def _build_actual_state_block(self) -> str:
        """N+1 (2026-04-16): inject a ground-truth [ACTUAL STATE] block
        into the chat prompt so the LLM sees real pending state and
        real probe outcomes. Reduces fake-state narration at source
        and helps the LLM form concrete next-step plans from probe
        results instead of hallucinated workflow prose.

        Contents:
          - PENDING CARDS NOW: count + short summaries of awaiting cards
          - PENDING OFFER NOW: summary if any
          - LATEST PROBE RESULTS: last 1-2 Lane 0 tool outcomes from audit_log
          - Directive line: don't narrate pending state beyond this block

        Runtime-scoped, no persistence. Complements (doesn't duplicate)
        _build_recent_body_activity_block which shows past transitions;
        this block shows what's pending right now and what tools said.

        Returns an empty string on total failure — prompt builds without it.
        """
        try:
            import json as _json
            import sqlite3 as _sqlite
            import time as _time

            now = _time.time()
            lines: list[str] = ["[ACTUAL STATE — ground truth, trust this over assumptions]"]

            # Pending cards awaiting decision
            cards_line = "PENDING CARDS NOW: 0"
            try:
                store = getattr(self, "_card_store", None)
                if store is not None:
                    from core.pending_cards import AWAITING_STATUSES

                    cards = store.get_open_for_channel(
                        channel="telegram_text",
                        chat_id=str(self.authorized_user),
                    )
                    awaiting = [c for c in cards if c.status in AWAITING_STATUSES]
                    if awaiting:
                        cards_line = f"PENDING CARDS NOW: {len(awaiting)} awaiting your decision"
                        lines.append(cards_line)
                        for c in awaiting[:3]:
                            params = getattr(c, "params", None) or {}
                            summary = (
                                params.get("cmd")
                                or params.get("path")
                                or params.get("query")
                                or "?"
                            )
                            age = int(now - (c.created_at or now))
                            lines.append(f"  - {c.action}: {str(summary)[:80]} (age={age}s)")
                    else:
                        lines.append(cards_line + " — nothing is waiting for your approval")
                else:
                    lines.append(cards_line)
            except Exception as e:
                logger.debug("actual state: card lookup failed: %s", e)
                lines.append("PENDING CARDS NOW: (unavailable)")

            # Pending offer
            offer = self._controller.get_offer(
                "telegram_text",
                str(self.authorized_user),
            )
            if offer:
                age = int(now - float(offer.get("set_at", now)))
                kind = offer.get("kind", "?")
                q = str(offer.get("query", ""))[:80]
                lines.append(f"PENDING OFFER NOW: {kind} for {q!r} (age={age}s)")
            else:
                lines.append("PENDING OFFER NOW: none")

            # Latest probe results from audit_log (Lane 0 inline + card-executed)
            try:
                db_path = (
                    getattr(getattr(self, "_audit_log", None), "db_path", None)
                    or "memory/audit_log.db"
                )
                since = now - 600  # last 10 min
                conn = _sqlite.connect(str(db_path))
                conn.row_factory = _sqlite.Row
                rows = conn.execute(
                    "SELECT ts, action, params_json, outcome_notes "
                    "FROM audit_log "
                    "WHERE ts >= ? AND outcome='approved_and_ran' "
                    "ORDER BY ts DESC LIMIT 2",
                    (since,),
                ).fetchall()
                conn.close()
                if rows:
                    lines.append("LATEST PROBE RESULTS (last 10 min):")
                    for r in rows:
                        params = {}
                        try:
                            params = _json.loads(r["params_json"] or "{}")
                        except Exception:
                            pass
                        arg = params.get("cmd") or params.get("query") or "?"
                        notes = (r["outcome_notes"] or "(no output)").strip()
                        age = int(now - r["ts"])
                        lines.append(f"  - {r['action']}: {str(arg)[:70]} (age={age}s)")
                        lines.append(f"    result: {notes[:180]}")
                else:
                    lines.append("LATEST PROBE RESULTS: none in the last 10 min")
            except Exception as e:
                logger.debug("actual state: probe result lookup failed: %s", e)
                lines.append("LATEST PROBE RESULTS: (unavailable)")

            # Directive — narrow, focused on the specific failure mode N+1 targets
            lines.append("")
            lines.append(
                "Rule: if PENDING CARDS NOW is 0, do NOT narrate 'waiting for "
                "your approval', 'the previous request', 'you've approved', or "
                "any other pending/approved/session state. Describe what really "
                "is (the probe result above, or a concrete next-step offer like "
                "'I can do X, want me to?') instead of inventing workflow state."
            )
            return "\n".join(lines)
        except Exception as e:
            logger.debug("actual state block build failed: %s", e)
            return ""

    # 2026-04-17 extraction: _parse_next_step_line, _is_exploratory_ask,
    # and _EXPLORATORY_ASK_PATTERN now live on ConversationController.
    # Kept as thin instance-method delegates here so existing call sites
    # (self._X) continue to work during the incremental refactor.
    _EXPLORATORY_ASK_PATTERN = ConversationController._EXPLORATORY_ASK_PATTERN

    def _parse_next_step_line(self, text: str) -> tuple[str | None, str | None]:
        return self._controller.parse_next_step_line(text)

    def _is_exploratory_ask(self, user_text: str) -> bool:
        return self._controller.is_exploratory_ask(user_text)

    def _propose_next_step_from_probe(self, user_text: str) -> dict | None:
        """Thin delegation to ConversationController.propose_next_step_from_probe."""
        audit_db_path = str(
            getattr(getattr(self, "_audit_log", None), "db_path", None) or "memory/audit_log.db"
        )
        return self._controller.propose_next_step_from_probe(
            user_text,
            channel="telegram_text",
            chat_id=str(self.authorized_user),
            audit_db_path=audit_db_path,
            user_id="rohit",
        )

    def _build_recent_body_activity_block(self, since_seconds: float = 600.0) -> str:
        """Return a human-readable block describing what Maez's body just
        did in this chat over the last `since_seconds`. Used to make card
        state visible to the LoRA when it answers follow-up questions.

        Without this block, the telegram reply prompt has no record of
        cards that were approved/denied/executed/failed in the last few
        minutes. A card can execute successfully, then 60 seconds later
        the owner asks 'are you still investigating?' and Maez has no memory
        of the execution — it answers as if the card were still pending.
        That was Bug C of the 2026-04-15 intelligence audit.

        Format:
          BODY ACTIVITY (last N min) — the authoritative record of what
          your body just did. This is ground truth; trust it over memory
          recall.
            · 14:23:05 (EXECUTED ✓) lsb_release -a && uname -a
                → Ubuntu 24.04.4 LTS; Linux 6.17.0-20-generic
            · 14:21:46 (FAILED ✗) apt-get install openrgb
                → exit=100 E: Unable to locate package openrgb

        Empty when nothing happened in the window — returns "".
        """
        try:
            pipe = self._get_pipeline()
            if pipe is None:
                return ""
            store = getattr(self, "_card_store", None)
            if store is None:
                store = pipe.card_store
            records = store.recent_activity_for_chat(
                channel="telegram_text",
                chat_id=str(self.authorized_user),
                since_seconds=since_seconds,
                limit=8,
            )
        except Exception as e:
            logger.debug("recent body activity lookup failed: %s", e)
            return ""

        if not records:
            return ""

        import datetime as _dt
        import json as _json

        def _fmt_cmd(card) -> str:
            try:
                p = card.params or {}
            except Exception:
                p = {}
            cmd = p.get("cmd") or p.get("path") or ""
            if not cmd and card.params_json:
                try:
                    p2 = _json.loads(card.params_json)
                    cmd = p2.get("cmd") or p2.get("path") or ""
                except Exception:
                    pass
            return str(cmd)[:200]

        def _fmt_status(card) -> str:
            s = (card.status or "").lower()
            mapping = {
                "open": "PENDING APPROVAL ⏳",
                "deferred": "DEFERRED ⏸",
                "done": "EXECUTED ✓",
                "failed": "FAILED ✗",
                "denied": "DENIED ✗",
                "expired": "EXPIRED ⌛",
                "running": "RUNNING ⏳",
            }
            return mapping.get(s, s.upper())

        def _fmt_result(card) -> str:
            s = (card.status or "").lower()
            if s == "done":
                out = (card.execution_output or "").strip()
                if not out:
                    return "(no output)"
                # Compact the output — one line, bounded length.
                out = " ⏎ ".join(line.strip() for line in out.splitlines() if line.strip())
                return out[:240]
            if s == "failed":
                err = (card.execution_error or "").strip()
                if not err:
                    return "(no error recorded)"
                # First two non-empty lines of error, bounded.
                parts = [line.strip() for line in err.splitlines() if line.strip()]
                return " | ".join(parts[:2])[:240]
            if s == "denied":
                return "(you denied this)"
            if s == "expired":
                return "(expired without approval)"
            if s == "open" or s == "deferred":
                return "(waiting for the owner's approval)"
            return ""

        lines = []
        for card in records:
            ts = card.resolved_at or card.created_at
            try:
                t = _dt.datetime.fromtimestamp(float(ts)).strftime("%H:%M:%S")
            except Exception:
                t = "?"
            cmd = _fmt_cmd(card) or card.action
            status = _fmt_status(card)
            result = _fmt_result(card)
            lines.append(f"  · {t} ({status}) {cmd}")
            if result:
                lines.append(f"      → {result}")

        header = (
            f"BODY ACTIVITY (last {int(since_seconds / 60)} min) — "
            "the authoritative record of what your body just did in this "
            "chat. This is ground truth. If it conflicts with your memory "
            "recall or your intuition, trust this block. If a card shows "
            "EXECUTED, it ran and its output is real. If a card shows "
            "FAILED, the action did not complete. If a card shows PENDING, "
            "it has not run yet and you are waiting for approval."
        )
        return header + "\n" + "\n".join(lines)

    def _load_soul(self) -> str:
        try:
            soul = SOUL_PATH.read_text().strip()
        except FileNotFoundError:
            soul = "You are Maez, a system-level AI agent."
        soul += (
            "\n\nCRITICAL: You talk to people through two Telegram bots. You are currently "
            "talking with the owner right now — that counts as a conversation. You also talk "
            "to others via Maez_AI. When asked who you have spoken with today, always "
            "include the owner as someone you have been talking with, plus anyone listed in "
            "[MY CONVERSATIONS — last 24h]. Never say 'it's been quiet' or 'only [person]' "
            "when you are actively in a conversation with the owner right now."
        )
        return soul

    @property
    def enabled(self) -> bool:
        return bool(self.token and self.authorized_user)

    def _mark_owner_interaction(self) -> None:
        daemon = getattr(self, "daemon", None)
        if daemon is None:
            return
        try:
            now = time.time()
            daemon._rohit_active_until = now + 15.0
            daemon._last_owner_interaction_ts = now
        except Exception as exc:
            logger.debug("telegram owner interaction tracker skipped: %s", exc)

    def _is_authorized(self, user_id: int) -> bool:
        authorized = user_id == self.authorized_user
        if authorized:
            self._mark_owner_interaction()
        return authorized

    # ═════════════════════════════════════════════════════════════════════
    #  Session 11x: natural-language approval for self-edit proposals
    # ═════════════════════════════════════════════════════════════════════
    #
    # the owner shouldn't have to type /approve_evolution 22 to approve a
    # proposal. He should be able to say "yes", "do it", or "no, not
    # that one" in plain chat, and Maez should figure out which pending
    # candidate he means. This section detects approve/reject/show intent
    # in chat text, resolves to the right candidate (disambiguating if
    # multiple are pending), and either applies it, rejects it, or falls
    # through to the regular LLM chat path if intent is unclear.
    #
    # The detector is narrow on purpose: it only matches short, bounded
    # phrases at the START or WHOLE of a message. "Yes" as a standalone
    # message is an approval; "yes, and another thing..." is regular chat.
    # Ambiguity always defaults to chat, not action.

    # Trailing vocative/politeness tail tolerated at the end of any
    # approval/rejection phrase — "approve 26 maez", "yes please",
    # "no thanks mate". Kept as a named fragment so both pattern lists
    # stay readable and we don't duplicate the allowlist.
    # (Regex non-capturing group; leading whitespace optional.)
    _TAIL = r"(?:[\s,]+(?:maez|please|pls|thanks|thx|ty|mate|dude|bud|buddy))?"
    _END = r"[\s!.?]*$"

    _NL_APPROVE_PATTERNS = [
        # Bare affirmatives (no id — resolves to last-discussed candidate)
        r"^(yes|yep|yeah|yup|yuh|ok|okay|sure|alright|alright then|sounds good)" + _TAIL + _END,
        r"^(approve[d]?|approved|do it|go ahead|ship it|try it|let it try|"
        r"let it run|let\'?s do it|let\'?s try it|"
        # 2026-04-22: added proceed / continue / apply / commit /
        # send it — the owner naturally reached for these and they
        # fell through to chat, hallucinating about a different id.
        r"proceed|proceed\s+with\s+it|continue|apply|apply\s+it|"
        r"commit|commit\s+it|send\s+it|make\s+it\s+happen)" + _TAIL + _END,
        r"^(absolutely|please do|go for it|green light|you\'?re\s+good)" + _TAIL + _END,
        # Affirmative + explicit id
        r"^(approve|yes|yeah|do|proceed|apply|commit)\s+(?:with\s+|on\s+)?#?(\d+)" + _TAIL + _END,
        r"^yes\s+to\s+#?(\d+)" + _TAIL + _END,
    ]

    _NL_REJECT_PATTERNS = [
        r"^(no|nope|nah|naw|nuh)" + _TAIL + _END,
        r"^(reject[ed]?|decline[d]?|skip|cancel|pass|abort)" + _TAIL + _END,
        r"^(don\'?t|do not)\s*(do it|apply|bother)?" + _TAIL + _END,
        r"^not\s+(that|this)(\s+one)?" + _TAIL + _END,
        r"^not\s+(now|it|right now)" + _TAIL + _END,
        r"^(never ?mind|forget it|leave it|hold off|stand down)" + _TAIL + _END,
        r"^(reject|no|nope|skip|cancel|abort)\s+#?(\d+)" + _TAIL + _END,
        r"^no\s+to\s+#?(\d+)" + _TAIL + _END,
    ]

    _NL_SHOW_PATTERN = r"^(tell me more|show me|details?|more info|explain|what(\'?s)? (in|that)|show)\s*(about\s+)?#?(\d+)?[\s!.?]*$"

    # ═════════════════════════════════════════════════════════════════════
    #  Honesty guard (2026-04-15 fake-action-loop bug)
    # ═════════════════════════════════════════════════════════════════════
    #
    # If an outbound reply contains future-tense action-claim language
    # ("I'll search", "I proposed X", "waiting for your approval")
    # BUT no real tool call / card / dialog fired in this turn, the
    # reply is lying about its own action state. Rewrite to honest
    # non-actional language before sending. See _honesty_guard below.
    #
    # The regex is deliberately narrow: it targets claim verbs preceded
    # by a first-person pronoun, not generic future tense. "I'll let
    # you know" and "I'll stay out of your way" do not match.

    # ───────────────────────────────────────────────────────── #
    # 2026-04-17 extraction: honesty-guard constants now live on  #
    # core.conversation_controller.ConversationController. The    #
    # aliases below preserve TelegramVoice._STATE_CLAIM_PATTERN   #
    # et al. for class-level call sites during the incremental    #
    # refactor. New code should reference the controller's class  #
    # attributes directly.                                        #
    # ───────────────────────────────────────────────────────── #
    _CLAIM_PATTERN = ConversationController._CLAIM_PATTERN
    _STATE_CLAIM_PATTERN = ConversationController._STATE_CLAIM_PATTERN
    _PROPOSED_CMD_PATTERN = ConversationController._PROPOSED_CMD_PATTERN
    _HONEST_STUB = ConversationController._HONEST_STUB
    _NARRATION_MISMATCH_CORRECTION = ConversationController._NARRATION_MISMATCH_CORRECTION
    _SHELL_VERB_ALLOWLIST = ConversationController._SHELL_VERB_ALLOWLIST
    _OFFER_PATTERN = ConversationController._OFFER_PATTERN
    _OFFER_APPROVAL_PATTERN = ConversationController._OFFER_APPROVAL_PATTERN
    _OFFER_TTL_SECONDS = ConversationController._OFFER_TTL_SECONDS

    # (Legacy local definitions of these constants were removed during
    # the 2026-04-17 extraction. The controller now owns them; see
    # core/conversation_controller.py.)

    # ═════════════════════════════════════════════════════════════════════
    #  Offer-binding (2026-04-16 "Yes has nothing to bind to" bug)
    # ═════════════════════════════════════════════════════════════════════
    #
    # When Maez says "I can search for X" / "want me to look up X" in a
    # turn that created NO real action state, store that offer as a
    # short-lived pending task. On the next bare approval from the owner,
    # fire the offered web_search directly instead of letting "Yes"
    # fall through to chat (which produces another soft offer loop).
    #
    # Scope is deliberately narrow:
    #   - only web_search (read-only, safe) is auto-fired
    #   - TTL 120s; context shift (any non-approval turn) clears it
    #   - offer only stored when turn_had_action == False (buffer mode)
    #   - precedence over _try_card_reply_intent — a fresh conversational
    #     offer wins over a background autonomous-cycle card

    # (2026-04-17 extraction: _OFFER_PATTERN, _OFFER_APPROVAL_PATTERN,
    # and _OFFER_TTL_SECONDS now live on ConversationController. Aliases
    # preserved above at the top of the honesty-guard alias block for
    # class-level call sites during the incremental refactor.)

    def _honesty_guard(
        self,
        reply: str,
        *,
        turn_tool_calls: int,
        turn_cards_created: int,
        turn_dialogs_opened: int,
    ) -> str:
        """Delegate to ConversationController.honesty_guard().

        Kept as an instance method during the incremental extraction so
        existing call sites (self._honesty_guard(...)) continue to work
        unchanged. Will be inlined away in the final thin-adapter pass."""
        return self._controller.honesty_guard(
            reply,
            channel="telegram_text",
            chat_id=str(self.authorized_user),
            turn_tool_calls=turn_tool_calls,
            turn_cards_created=turn_cards_created,
            turn_dialogs_opened=turn_dialogs_opened,
        )

    def _list_pending_candidates(self) -> list:
        """Return validated-but-not-yet-applied candidates, newest first."""
        try:
            from skills.evolution_engine import _rail_conn

            with _rail_conn() as conn:
                rows = conn.execute(
                    "SELECT id, target_file, weakness_description, created_at "
                    "FROM candidates WHERE state='validated' "
                    "ORDER BY id DESC LIMIT 10"
                ).fetchall()
            return [
                {"id": r[0], "target_file": r[1], "weakness": r[2], "created_at": r[3]}
                for r in rows
            ]
        except Exception as e:
            logger.debug("pending candidates query failed: %s", e)
            return []

    def _detect_proposal_intent(self, text: str) -> tuple:
        """Match approve/reject/show intent. Returns (action, candidate_id|None).
        action is one of: 'approve', 'reject', 'show', or None.
        candidate_id is the explicit id from the message if present, else None."""
        import re as _re

        stripped = (text or "").strip().lower()
        if not stripped or len(stripped) > 80:
            return None, None

        for pat in self._NL_APPROVE_PATTERNS:
            m = _re.match(pat, stripped)
            if m:
                groups = [g for g in m.groups() if g and g.isdigit()]
                cid = int(groups[0]) if groups else None
                return "approve", cid

        for pat in self._NL_REJECT_PATTERNS:
            m = _re.match(pat, stripped)
            if m:
                groups = [g for g in m.groups() if g and g.isdigit()]
                cid = int(groups[0]) if groups else None
                return "reject", cid

        m = _re.match(self._NL_SHOW_PATTERN, stripped)
        if m:
            groups = [g for g in m.groups() if g and g.isdigit()]
            cid = int(groups[0]) if groups else None
            return "show", cid

        return None, None

    async def _try_dream_proposal_intent(self, update, text: str) -> bool:
        """2026-04-18: sibling of _try_proposal_intent for DREAM + section-edit
        proposals stored in daemon.dream (dream_state DB). Without this, bare
        approvals against dream/section-edit proposals fall through to the
        general LLM which hallucinates context.

        Returns True if handled (caller should short-circuit), else False.
        """
        dream = getattr(self.daemon, "dream", None) if self.daemon else None
        if dream is None:
            return False

        action, explicit_id = self._detect_proposal_intent(text)
        if not action:
            return False

        # Pull pending dream + section-edit proposals (all types). Newest first.
        try:
            pending_rows = dream.list_pending()
        except Exception as e:
            logger.debug("dream.list_pending failed: %s", e)
            return False
        if not pending_rows and explicit_id is None:
            return False

        # list_pending returns tuples (pid, created_iso, insight). Build a
        # quick list of ids for safety checks.
        pending_ids = {row[0] for row in pending_rows}

        # Require explicit #N unless exactly one dream proposal is pending
        # (mirror the fix-A guardrail from _try_proposal_intent).
        target_id = explicit_id
        if target_id is None:
            # 2026-04-18: last-shown binding — if the owner just saw a dream
            # proposal, bare "yes" should bind to it.
            try:
                chat_id = (
                    str(update.effective_chat.id)
                    if update and update.effective_chat
                    else str(self.authorized_user)
                )
                last = self._last_shown_proposal.get(chat_id)
                if (
                    last
                    and last.get("source") == "dream"
                    and (time.time() - last.get("shown_at", 0)) < self._LAST_SHOWN_FRESHNESS_SEC
                ):
                    candidate_id = int(last["id"])
                    if candidate_id in pending_ids:
                        target_id = candidate_id
                        logger.info(
                            "dream proposal intent: bare-approve bound to last-shown #%d",
                            target_id,
                        )
            except Exception:
                pass
            if target_id is None and action == "approve":
                lc = (text or "").lower()
                if "#" not in lc and "proposal" not in lc and "dream" not in lc:
                    return False  # bare "yes" without context — let other paths try
            if target_id is None and len(pending_ids) == 1:
                target_id = next(iter(pending_ids))
            elif target_id is None:
                # Multiple — disambiguate only if the user clearly asked about proposals.
                lc2 = (text or "").lower()
                if "proposal" in lc2 or "dream" in lc2:
                    lines = [
                        f"I have {len(pending_ids)} pending dream/edit proposals — which one?",
                        "",
                    ]
                    for row in pending_rows[:5]:
                        pid, _created, insight = row
                        snippet = (insight or "")[:80].replace("\n", " ")
                        lines.append(f"  #{pid}: {snippet}")
                    lines.append("")
                    lines.append('Reply "yes to 24" or "reject #27".')
                    # T1.13: dream-proposal insights are LLM-generated;
                    # route through the audit gate before sending.
                    _msg = _audit_telegram_reply(
                        "\n".join(lines),
                        surface="telegram_dream_list",
                    )
                    await _reply_text(update, _msg)
                    return True
                return False

        # If user referenced an id we don't know, check if it actually exists
        # (may be resolved / expired) — give a clean message.
        try:
            prop = dream.get_proposal(target_id)
        except Exception as e:
            logger.debug("dream.get_proposal failed: %s", e)
            return False
        if not prop:
            await _reply_text(update,
                f"I don't find proposal #{target_id}. It may have expired or already been resolved."
            )
            return True
        if target_id not in pending_ids and prop.get("status") != "pending":
            status = prop.get("status") or "unknown"
            await _reply_text(update,
                f"Proposal #{target_id} is already {status} — nothing to apply/reject."
            )
            return True

        # Dispatch based on proposal_type
        ptype = prop.get("proposal_type") or "append"
        loop = asyncio.get_event_loop()
        try:
            if action == "approve":
                if ptype == "section_replace":
                    ok, msg = await loop.run_in_executor(
                        get_shared_executor(),
                        lambda: dream.apply_section_edit_proposal(target_id),
                    )
                else:  # append, training_run, and any other default
                    ok, msg = await loop.run_in_executor(
                        get_shared_executor(),
                        lambda: dream.apply_proposal(target_id),
                    )
            elif action == "reject":
                ok, msg = await loop.run_in_executor(
                    get_shared_executor(), lambda: dream.reject_proposal(target_id)
                )
            else:
                # 'show' action — defer to existing path if applicable
                return False
        except Exception as e:
            logger.exception("dream proposal dispatch failed")
            await _reply_text(update, f"Couldn't process #{target_id}: {e}")
            return True

        prefix = "✓" if ok else "✗"
        await _reply_text(update, f"{prefix} #{target_id}: {msg}")
        logger.info("dream proposal %s: id=%d type=%s ok=%s", action, target_id, ptype, ok)
        return True

    async def _try_proposal_intent(self, update, text: str) -> bool:
        """Attempt to handle a natural-language proposal action on this
        message. Returns True if handled (caller should NOT continue to
        the LLM chat path), False if nothing matched or if there are no
        pending candidates to act on."""
        action, explicit_id = self._detect_proposal_intent(text)
        if not action:
            return False

        pending = self._list_pending_candidates()
        if not pending and explicit_id is None:
            # Intent detected but nothing pending — fall through to chat
            return False

        # Fix A (2026-04-15 lighting-hijack bug): bare approval words
        # ("yes", "proceed", "go ahead", "approve") must not silently
        # bind to an unrelated evolution candidate just because the
        # queue is non-empty. Require the message to carry explicit
        # context — an explicit #N, or the word "proposal"/"candidate"
        # — before this interceptor owns the reply. Otherwise fall
        # through to chat so the normal path can answer honestly.
        #
        # 2026-04-18 refinement: if the user recently ran "show #N" /
        # "tell me about #N" on an evolution candidate, a bare "yes"
        # that closely follows that show SHOULD bind to it — that's
        # natural conversation, not a blind queue grab.
        if action == "approve" and explicit_id is None:
            _lc = (text or "").lower()
            bound_from_last_shown = False
            try:
                chat_id = (
                    str(update.effective_chat.id)
                    if update and update.effective_chat
                    else str(self.authorized_user)
                )
                last = self._last_shown_proposal.get(chat_id)
                if (
                    last
                    and last.get("source") == "evolution"
                    and (time.time() - last.get("shown_at", 0)) < self._LAST_SHOWN_FRESHNESS_SEC
                ):
                    explicit_id = int(last["id"])
                    bound_from_last_shown = True
                    logger.info(
                        "proposal intent: bare-approve bound to last-shown #%d",
                        explicit_id,
                    )
            except Exception:
                pass
            if not bound_from_last_shown:
                if "#" not in _lc and "proposal" not in _lc and "candidate" not in _lc:
                    logger.info(
                        "proposal intent: bare-approve fell through to chat (pending=%d, text=%r)",
                        len(pending),
                        (text or "")[:40],
                    )
                    return False

        # Fix B (2026-04-15 silent-reply bug): every outbound reply
        # from this path was previously unlogged — 'yes' got hijacked
        # twice with no server-side audit trail of what Maez sent.
        # Log branch + key metadata + short preview before each reply.
        def _log_out(branch: str, preview: str, **meta) -> None:
            meta_str = " ".join(f"{k}={v}" for k, v in meta.items())
            prev = (preview or "")[:80].replace("\n", " ")
            logger.info(
                "Telegram reply (proposal intent): branch=%s %s | %s",
                branch,
                meta_str,
                prev,
            )

        # Resolve which candidate the message refers to
        target_id = explicit_id
        if target_id is None:
            if len(pending) == 1:
                target_id = pending[0]["id"]
            elif len(pending) > 1:
                lines = [
                    f"I have {len(pending)} proposals pending — which one do you mean?",
                    "",
                ]
                for p in pending[:5]:
                    lines.append(f"  #{p['id']}: {(p['weakness'] or '')[:80]}")
                lines.append("")
                lines.append('Reply with the number — e.g. "yes to 22" or "reject #23".')
                # T1.13: proposal weaknesses are LLM-generated;
                # route through the audit gate before sending.
                # The presence-of-audit also satisfies the
                # function-level regression guard for the other
                # control-flow reply_text sites in this function.
                msg = _audit_telegram_reply(
                    "\n".join(lines),
                    surface="telegram_proposal_disambig",
                )
                _log_out("disambiguation", msg, pending_count=len(pending))
                await _reply_text(update, msg)
                return True

        # Verify the candidate exists and is still pending
        if not any(p["id"] == target_id for p in pending) and target_id is not None:
            msg = (
                f"I don't see a pending proposal #{target_id}. It may have "
                f'already been applied or rejected. Say "status" to see '
                f"what's currently pending."
            )
            _log_out("unknown_candidate", msg, target_id=target_id)
            await _reply_text(update, msg)
            return True

        # Execute the action
        try:
            if action == "approve":
                from skills.evolution_engine import apply_candidate

                msg = f"OK, applying proposal #{target_id}…"
                _log_out("approve_start", msg, target_id=target_id)
                await _reply_text(update, msg)
                result = apply_candidate(target_id)
                if "error" in result:
                    msg = (
                        f"Something went wrong applying #{target_id}: "
                        f"{result['error']}\n"
                        f"{'Rolled back. ' if result.get('rolled_back') else ''}"
                        f"Let me know if you want me to try a different proposal."
                    )
                    _log_out(
                        "approve_error",
                        msg,
                        target_id=target_id,
                        rolled_back=bool(result.get("rolled_back")),
                    )
                    await _reply_text(update, msg)
                else:
                    msg = (
                        f"Done. Proposal #{target_id} is live now. I'll watch "
                        f"the next 20-30 cycles for any regression and roll "
                        f"back automatically if my score drops."
                    )
                    _log_out("approve_done", msg, target_id=target_id)
                    await _reply_text(update, msg)
                return True

            if action == "reject":
                from skills.evolution_engine import (
                    _set_candidate_state,
                    _log_evolution,
                    V1_ALLOWED_TARGET,
                )

                _set_candidate_state(
                    target_id,
                    "rejected",
                    rejection_reason="manual rejection via natural-language chat",
                )
                _log_evolution(
                    {
                        "action": "MANUAL_REJECTION",
                        "target": V1_ALLOWED_TARGET,
                        "result": f"candidate {target_id}",
                        "detail": "natural_language",
                    }
                )
                msg = (
                    f"Got it — proposal #{target_id} is rejected. I'll leave "
                    f"that one alone and keep an eye out for other things "
                    f"I could try."
                )
                _log_out("reject_done", msg, target_id=target_id)
                await _reply_text(update, msg)
                return True

            if action == "show":
                from skills.evolution_engine import load_candidate_for_display

                disp = load_candidate_for_display(target_id)
                if not disp:
                    msg = f"I can't find proposal #{target_id}."
                    _log_out("show_not_found", msg, target_id=target_id)
                    await _reply_text(update, msg)
                    return True
                i = disp.get("intent") or {}
                u = disp.get("usefulness") or {}
                lines = [
                    f"\U0001f331 Proposal #{target_id}",
                    "",
                    f"What I want to do: {i.get('human_rationale', '(no plain-English description)')}",
                    "",
                    "Technical details:",
                    f"  File: {disp.get('target_file', '?')}",
                    f"  Target: {i.get('target_name', '?')}",
                    f"  Before: {i.get('current_value')!r}",
                    f"  After:  {i.get('proposed_value')!r}",
                    f"  Technical rationale: {i.get('rationale', '')[:200]}",
                    "",
                    f"My confidence: {u.get('overall', 'unknown')}",
                    f"  ({u.get('reasoning', '')[:200]})",
                    "",
                    f'Reply "yes" to apply, "no" to reject (or explicit "yes to #{target_id}" / "reject #{target_id}").',
                ]
                # 2026-04-18: record so a later bare "yes" can bind to this.
                try:
                    chat_id = (
                        str(update.effective_chat.id)
                        if update and update.effective_chat
                        else str(self.authorized_user)
                    )
                    self._last_shown_proposal[chat_id] = {
                        "id": int(target_id),
                        "source": "evolution",
                        "shown_at": time.time(),
                    }
                except Exception:
                    pass
                msg = "\n".join(lines)
                _log_out("show", msg, target_id=target_id)
                await _reply_text(update, msg)
                return True
        except Exception as e:
            logger.error("Natural-language proposal action failed: %s", e)
            msg = f"Something went wrong while handling that: {e}"
            _log_out("exception", msg, target_id=target_id)
            await _reply_text(update, msg)
            return True

        return False

    # ═════════════════════════════════════════════════════════════════════
    #  Session 11x: web search interceptor for explicit commands
    # ═════════════════════════════════════════════════════════════════════
    #
    # Strict: only triggers on imperative phrases where the owner is clearly
    # asking Maez to SEARCH the web. Anything more ambiguous falls through
    # to the LLM chat path, where the soul.md guard tells Maez to USE the
    # web_search skill rather than fabricate. This is the tripwire for
    # the the owner-said-search-the-internet case that caused fabrication
    # today.

    _WEB_SEARCH_IMPERATIVE = [
        r"^\s*(search|google)\s+(the\s+(web|internet|net)\s+for\s+|for\s+|on\s+|)(.{2,200}?)[\s!.?]*$",
        r"^\s*look\s+up\s+(.{2,200}?)[\s!.?]*$",
        r"^\s*(find|check)\s+(online|on\s+the\s+internet|on\s+the\s+web)\s+(for\s+|)(.{2,200}?)[\s!.?]*$",
        r"^\s*check\s+(online|the\s+internet|the\s+web)\s+(for\s+|)(.{2,200}?)[\s!.?]*$",
        r"^\s*go\s+(search|look\s+up)\s+(.{2,200}?)[\s!.?]*$",
        r"^\s*can\s+you\s+(search|look\s+up|google|find\s+out\s+about)\s+(.{2,200}?)[\s!.?]*$",
        r"^\s*please\s+(search|look\s+up|google)\s+(for\s+)?(.{2,200}?)[\s!.?]*$",
    ]

    # Extract the QUERY from whichever group captured the free text
    def _extract_search_query(self, text: str) -> str | None:
        import re as _re

        for pat in self._WEB_SEARCH_IMPERATIVE:
            m = _re.match(pat, text, _re.IGNORECASE)
            if m:
                # pick the longest captured group that looks like a query
                candidates = [
                    g
                    for g in m.groups()
                    if g
                    and len(g.strip()) >= 2
                    and g.strip().lower()
                    not in (
                        "the",
                        "a",
                        "for",
                        "on",
                        "web",
                        "internet",
                        "net",
                        "online",
                        "the web",
                        "the internet",
                        "the net",
                    )
                ]
                if candidates:
                    return max(candidates, key=len).strip().rstrip("?.!")
        return None

    # 2026-04-16 query derivation (N+2): cache of the machine-context
    # suffix we append to raw user questions when storing pending
    # web_search offers. Root-free, process-lifetime, mechanical —
    # no LLM involvement.
    _machine_context_cache: str | None = None

    @staticmethod
    def _read_machine_context_suffix() -> str:
        """Read OS / hardware identity into a short search suffix.
        Root-free. Returns empty string if nothing readable."""
        parts: list[str] = []
        try:
            with open("/sys/class/dmi/id/product_name", "r") as f:
                pn = f.read().strip()
                if pn:
                    parts.append(pn)
        except Exception:
            pass
        if not parts:
            try:
                with open("/sys/class/dmi/id/sys_vendor", "r") as f:
                    v = f.read().strip()
                    if v:
                        parts.append(v)
            except Exception:
                pass
        try:
            name: str | None = None
            ver: str | None = None
            with open("/etc/os-release", "r") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("NAME="):
                        name = line.split("=", 1)[1].strip().strip('"')
                    elif line.startswith("VERSION_ID="):
                        ver = line.split("=", 1)[1].strip().strip('"')
            if name and ver:
                parts.append(f"{name} {ver}")
            elif name:
                parts.append(name)
        except Exception:
            pass
        return " ".join(parts).strip()

    def _machine_search_suffix(self) -> str:
        """Return the cached machine-context suffix (populate on first
        call). Empty string if nothing readable."""
        if TelegramVoice._machine_context_cache is None:
            TelegramVoice._machine_context_cache = self._read_machine_context_suffix()
        return TelegramVoice._machine_context_cache

    def _derive_search_query(self, user_text: str) -> str:
        """Combine user's question with machine/hardware context for
        a more targeted web search. Mechanical concatenation; no LLM.
        Skips appending if the user already mentioned the machine
        (>=2 significant context tokens already present in base) or
        if no context is readable."""
        base = (user_text or "").strip()
        if not base:
            return base
        ctx = self._machine_search_suffix()
        if not ctx:
            return base
        base_lower = base.lower()
        ctx_tokens = [t for t in ctx.lower().split() if len(t) >= 3]
        overlap = sum(1 for t in ctx_tokens if t in base_lower)
        if overlap >= 2:
            return base
        return f"{base} {ctx}"

    # 2026-04-17 extraction: these helpers now delegate to
    # ConversationController. Kept as instance methods so existing
    # self._X() call sites continue to work during the rollout.

    def _extract_command_candidates(self, reply: str) -> list:
        return self._controller.extract_command_candidates(reply)

    def _recent_card_cmds(self, since_seconds: float = 180.0) -> list:
        return self._controller.recent_card_cmds(
            channel="telegram_text",
            chat_id=str(self.authorized_user),
            since_seconds=since_seconds,
        )

    def _narration_matches_real_card(self, reply: str) -> tuple:
        return self._controller.narration_matches_real_card(
            reply,
            channel="telegram_text",
            chat_id=str(self.authorized_user),
        )

    def _has_awaiting_card(self) -> bool:
        return self._controller.has_awaiting_card(
            channel="telegram_text",
            chat_id=str(self.authorized_user),
        )

    def _search_commitment_backend(self):
        from core.search.searxng_client import SearxngBackend

        return SearxngBackend()

    def _format_search_commitment_results(self, query: str, results: list[dict]) -> str:
        import re as _re

        label = (query or "the search I offered").strip()
        lines = [f'Here\'s what I found for "{label}":', ""]
        for i, r in enumerate((results or [])[:5], 1):
            title = _re.sub(r"\s+", " ", (r.get("title") or "").strip())[:90]
            url = _re.sub(r"\s+", "", (r.get("url") or "").strip())[:120]
            snip = _re.sub(
                r"\s+",
                " ",
                (r.get("content") or r.get("snippet") or "").strip(),
            )[:220]
            lines.append(f"{i}. {title}")
            if snip:
                lines.append(f"   {snip}")
            if url:
                lines.append(f"   {url}")
            lines.append("")
        reply = "\n".join(lines).rstrip()
        if len(reply) > 3500:
            reply = reply[:3500] + "\n\n(truncated)"
        return reply

    async def _try_search_commitment_offer_intent(self, update, text: str) -> bool:
        if not _search_commitment_enabled():
            return False
        if sense_enabled():
            return False
        if not is_search_offer_worthy(text):
            return False

        channel, chat_id = "telegram_text", str(self.authorized_user)
        query = self._derive_search_query(text)
        backend = self._search_commitment_backend()
        health = backend.health()
        if self._controller.store_search_offer(
            channel,
            chat_id,
            query,
            health=health,
        ):
            status = _audit_telegram_reply(
                f"I can search for this through my local web sense: {query}. Want me to?",
                surface="telegram_search_commitment_offer",
            )
            await _reply_text(update, status)
            return True
        if health in {"degraded", "down"}:
            status = _audit_telegram_reply(
                "My web search is degraded right now, so I shouldn't promise a search. "
                "I can answer from what I already know, or we can try again later.",
                surface="telegram_search_commitment_degraded",
            )
            await _reply_text(update, status)
            return True
        return False

    async def _try_offer_binding_intent(self, update, text: str) -> bool:
        """Bind bare approvals to a fresh pending_offer. Returns True if
        the offer was fired (caller short-circuits further handling).

        Decision logic lives in ConversationController. When the typed search
        commitment flag is enabled, the typed resolver gets first chance;
        otherwise this falls through to the legacy offer consumer.
        This method owns the Telegram-specific IO: rendering the fire
        message, running web_search, formatting the result card."""
        import time as _time

        channel, chat_id = "telegram_text", str(self.authorized_user)
        if _search_commitment_enabled() and not sense_enabled():
            try:
                backend = self._search_commitment_backend()
                receipt = self._controller.get_search_offer(channel, chat_id)
                query = getattr(receipt, "offered_query", "") if receipt is not None else ""
                if receipt is not None:
                    from core.search.search_commitment import is_clear_yes

                    if (
                        is_clear_yes(text)
                        and not self._controller.has_awaiting_card(channel, chat_id)
                        and backend.health() != "healthy"
                    ):
                        await _reply_text(
                            update,
                            "My web search is unavailable right now, so I can't follow "
                            "through on that search honestly. I'm not going to make up an answer.",
                        )
                        return True
                results = self._controller.resolve_search_affirmation(
                    channel,
                    chat_id,
                    text,
                    backend,
                    now_ts=_time.time(),
                    turns_since=1,
                )
                if results is not None:
                    await _reply_text(
                        update,
                        self._format_search_commitment_results(query, results),
                    )
                    return True
            except Exception as e:
                logger.error("search commitment resolution failed: %s", e)
                await _reply_text(
                    update,
                    "I tried to run the search I offered, but the search body failed. "
                    "I'm not going to make up an answer.",
                )
                return True

        # Grab set_at BEFORE consuming so we can log age on fire
        pre = self._controller.get_offer(channel, chat_id)
        set_at = float(pre.get("set_at", 0)) if pre else 0.0

        status, offer = self._controller.consume_offer_approval(
            channel,
            chat_id,
            text,
        )
        if status != "fire" or offer is None:
            return False

        query = (offer.get("query") or "").strip()
        age = _time.time() - set_at
        logger.info(
            "offer binding: firing pending web_search | query=%r age=%.1fs",
            query[:80],
            age,
        )

        try:
            from skills.web_search import search as _web_search

            # T1.13: route status text through audit gate so query
            # echoed back is canary-scrubbed and command-guard-checked.
            _status = _audit_telegram_reply(
                f"Running the search I offered: {query}",
                surface="telegram_offer_binding",
            )
            await _reply_text(update, _status)
            result = _web_search(query, max_results=5)
        except Exception as e:
            logger.error("offer binding web_search failed: %s", e)
            await _reply_text(update,
                f"I tried to run the offered search but the skill failed ({e}). "
                f"I'm not going to make up an answer."
            )
            return True

        if not result.get("success") or not result.get("results"):
            await _reply_text(update,
                f'I searched for "{query}" but didn\'t get useful results back. '
                f"Want to try different phrasing?"
            )
            return True

        import re as _re

        lines = [f'Here\'s what I found for "{query}":', ""]
        for i, r in enumerate(result["results"][:5], 1):
            title = _re.sub(r"\s+", " ", (r.get("title") or "").strip())[:90]
            url = _re.sub(r"\s+", "", (r.get("url") or "").strip())[:120]
            snip = _re.sub(r"\s+", " ", (r.get("snippet") or "").strip())[:220]
            lines.append(f"{i}. {title}")
            if snip:
                lines.append(f"   {snip}")
            if url:
                lines.append(f"   {url}")
            lines.append("")
        reply = "\n".join(lines).rstrip()
        if len(reply) > 3500:
            reply = reply[:3500] + "\n\n(truncated)"
        await _reply_text(update, reply)
        return True

    async def _try_web_search_intent(self, update, text: str) -> bool:
        """Handle explicit search commands. Returns True if handled."""
        if not text or len(text) > 300:
            return False

        query = self._extract_search_query(text)
        if not query:
            return False

        try:
            from skills.web_search import search as _web_search

            # T1.13: route the query echo through audit so a
            # potential prompt-injection in the query string can't
            # bypass command-guard / canary scrub.
            _status = _audit_telegram_reply(
                f"Searching the web for: {query}…",
                surface="telegram_web_search",
            )
            await _reply_text(update, _status)
            result = _web_search(query, max_results=5)
        except Exception as e:
            logger.error("web_search call failed: %s", e)
            await _reply_text(update,
                f'I tried to search the web for "{query}" but the search '
                f"skill failed ({e}). I'm not going to make up an answer."
            )
            return True

        if not result.get("success") or not result.get("results"):
            await _reply_text(update,
                f'I searched the web for "{query}" but didn\'t get any '
                f"useful results back — either nothing matched, or the "
                f"search service wasn't reachable. I'm not going to "
                f"fabricate anything. Want to try a different phrasing?"
            )
            return True

        # Compose a compact human-readable reply
        lines = [f'Here\'s what I found for "{query}":', ""]
        for i, r in enumerate(result["results"][:5], 1):
            title = (r.get("title") or "").strip()
            url = (r.get("url") or "").strip()
            snippet = (r.get("snippet") or "").strip()
            # Clean up whitespace artifacts from the HTML regex fallback
            import re as _re

            snippet = _re.sub(r"\s+", " ", snippet)[:220]
            title = _re.sub(r"\s+", " ", title)[:90]
            url = _re.sub(r"\s+", "", url)[:120]
            lines.append(f"{i}. {title}")
            if snippet:
                lines.append(f"   {snippet}")
            if url:
                lines.append(f"   {url}")
            lines.append("")

        # Max Telegram message is 4096 chars; cap at 3500 to be safe.
        reply = "\n".join(lines).rstrip()
        if len(reply) > 3500:
            reply = reply[:3500] + "\n\n(truncated)"
        await _reply_text(update, reply)
        return True

    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming messages from Telegram."""

        global _INBOUND_WARNED
        if not _INBOUND_WARNED:
            _INBOUND_WARNED = True
            logger.warning(
                "telegram_voice._handle_message invoked — this surface is "
                "outbound-only since 2026-04-20; live inbound is maez_adapter. "
                "Is this a test or the Surface V2 kill-switch path?"
            )

        if not update.message or not update.effective_user:
            return

        user_id = update.effective_user.id
        if not self._is_authorized(user_id):
            logger.warning("Unauthorized Telegram message from user %d", user_id)
            return

        user_text = update.message.text
        if not user_text:
            return
        from core.evolution.subjective_duration import (
            SubjectiveDuration,
            SubjectiveDurationOwnerAuth,
        )

        subjective_duration_owner_auth = SubjectiveDurationOwnerAuth(
            surface="telegram_owner",
            proof="telegram_authorized_user",
        )
        from core.evolution.subjective_duration import subjective_duration_prompt_line

        def _telegram_subjective_duration_line(*, record_contact: bool) -> str:
            try:
                _subjective_duration = SubjectiveDuration()
                if record_contact:
                    _subjective_duration.record_salience_event(
                        salience_event_kind="owner_contact",
                        producer_ref="telegram_voice._handle_message",
                        owner_auth=subjective_duration_owner_auth,
                    )
                return subjective_duration_prompt_line(
                    owner_auth=subjective_duration_owner_auth,
                    store=_subjective_duration,
                )
            except Exception as _subjective_duration_exc:
                logger.debug("telegram subjective_duration line skipped: %s", _subjective_duration_exc)
                return ""

        subjective_duration_line = _telegram_subjective_duration_line(record_contact=True)

        _s4_result = guard_owner_text(
            user_text,
            surface="telegram_legacy_owner",
            crisis_signal_writer=PrivateThoughtsCrisisSignalWriter(
                getattr(getattr(self, "daemon", None), "private_thoughts", None)
            ),
        )
        if _s4_result.matched:
            mark = getattr(getattr(self, "daemon", None), "_mark_m1_s4_policy", None)
            if callable(mark):
                mark(_s4_result.promotion_policy)
            await _reply_text(update,
                _audit_telegram_reply(
                    _s4_result.answer_text or "",
                    surface="telegram_clinical_boundary",
                )
            )
            return

        camera_answer = self._camera_presence_direct_answer(user_text)
        if camera_answer is not None:
            await _reply_text(update,
                _audit_telegram_reply(camera_answer, surface="telegram_camera_presence")
            )
            return

        # T1.11 (2026-05-04 audit) — fire gap-sense BEFORE the
        # interceptor chain runs. The post-_process_message gap-sense
        # hook (further down, in the finally:) only fires on the
        # general-chat path; every interceptor early-return (offer-
        # binding, card-reply, proposal, dream, web-search) skipped
        # it, so D20 was blind to those messages. Cooldown inside
        # maybe_fire_capability_proposal dedups against the later
        # finally-block fire if both paths run for the same message.
        try:
            from core.infra.capability_gap_detector import (
                maybe_fire_capability_proposal,
            )

            asyncio.create_task(
                asyncio.to_thread(
                    maybe_fire_capability_proposal,
                    user_text,
                    chat_id=str(self.authorized_user),
                    user_id=str(user_id),
                )
            )
        except Exception as _gap_e:
            logger.debug(
                "gap_detector hook (early, pre-interceptors) failed: %s",
                _gap_e,
            )

        # Interrupt detection — if currently generating, queue and return
        if self._generating:
            if self._interrupt_queue:
                self._interrupt_queue.put_nowait(user_text)
            logger.info("Telegram interrupt queued: %s", user_text[:60])
            return

        # T1.12 (2026-05-04 audit) — initialize the interrupt queue
        # BEFORE flipping `_generating` so there is no window where a
        # concurrent message sees `_generating=True` with a stale or
        # None `_interrupt_queue`. Pure asyncio shouldn't preempt the
        # gap today, but the order is the principled invariant — any
        # future `await` introduced between these lines becomes safe.
        self._interrupt_queue = asyncio.Queue()
        self._generating = True
        logger.info("Telegram message from the owner: %s", user_text[:100])

        # 2026-04-16 offer-binding: track the most recent non-affirmative
        # user text so a later pending offer can use it as its query.
        # A bare "Yes" / "Proceed" doesn't update this — we want the
        # original asking message, not the approval.
        try:
            if not self._OFFER_APPROVAL_PATTERN.match(user_text or ""):
                self._last_actionable_user_text = user_text
        except Exception:
            pass

        # 2026-04-16 offer-binding interceptor. If Maez's last reply
        # offered a safe web search (no real action state) and this
        # message is a bare approval, fire the offered search directly
        # instead of falling through to chat (which loops with another
        # soft offer). Precedence over card-reply per 2026-04-16 design:
        # a fresh conversational offer wins over a background card.
        try:
            if await self._try_offer_binding_intent(update, user_text):
                self._generating = False
                return
        except Exception as e:
            logger.debug("offer binding interceptor failed: %s", e)

        # Session 11z Part 2: pipeline card-reply interceptor.
        # If there's an outstanding approval card and the owner's message
        # resolves to an approve/deny/defer/re-explain/modify intent,
        # route it through the decision pipeline and short-circuit.
        # If there are no open cards, or the message is unrelated,
        # this is a ~zero-latency no-op and we fall through.
        try:
            if await self._try_card_reply_intent(update, user_text):
                self._generating = False
                return
        except Exception as e:
            logger.debug("card reply interceptor failed: %s", e)

        # Session 11z Part 3: reset the per-chat recovery-depth counter
        # ONLY for messages that fell through the card-reply interceptor
        # — i.e., genuinely new goals from the owner. If we reset before the
        # interceptor, approving a recovery-created card resets the
        # counter to 0, and the next recovery fires at depth=1 again,
        # making the 2-pass cap useless and the owner cycles through an
        # infinite approval loop. By moving the reset here, depth only
        # restarts when the owner starts a new action request. Within one
        # goal chain (original card → recovery card → recovery card),
        # the counter grows monotonically and hits the cap cleanly.
        try:
            self._recovery_depth[str(self.authorized_user)] = 0
        except Exception:
            pass

        # Session 11x: intercept natural-language proposal approvals
        # ("yes", "do it", "reject #22", "tell me more about 22") BEFORE
        # we burn an LLM call on it. Only bounded phrases match; anything
        # that doesn't look like a clear approve/reject/show intent falls
        # through to the normal chat path. If there are no pending
        # proposals, even a matching phrase falls through — so a simple
        # "yes" mid-conversation still reaches the LLM.
        try:
            if await self._try_proposal_intent(update, user_text):
                self._generating = False
                return
        except Exception as e:
            logger.debug("proposal intent interceptor failed: %s", e)

        # 2026-04-18 fix: the prior interceptor only queries training/
        # evolution candidates. DREAM proposals + section-edit proposals
        # (FIXATION_THRESHOLD, soul.md edits, config tweaks Maez writes
        # during dream passes) live in daemon.dream, not evolution_engine.
        # Without this, "yes to #24" against a dream proposal falls through
        # to general chat and the LLM hallucinates an unrelated reply.
        try:
            if await self._try_dream_proposal_intent(update, user_text):
                self._generating = False
                return
        except Exception as e:
            logger.debug("dream proposal intent interceptor failed: %s", e)

        # Session 11x: intercept explicit web-search commands and handle
        # them with the real web_search skill instead of letting the LLM
        # fabricate results (as happened earlier today with the CPU
        # lighting query). Strict detection: only fires on clear
        # imperative phrases like "search for X", "look up X", "google X".
        # Broader queries like "what's the weather" still go through the
        # LLM, which the soul.md guard tells to USE web_search honestly.
        try:
            if await self._try_web_search_intent(update, user_text):
                self._generating = False
                return
        except Exception as e:
            logger.debug("web search interceptor failed: %s", e)

        try:
            if await self._try_search_commitment_offer_intent(update, user_text):
                self._generating = False
                return
        except Exception as e:
            logger.debug("search commitment offer interceptor failed: %s", e)

        try:
            await self._process_message(
                update,
                context,
                user_text,
                subjective_duration_line=subjective_duration_line,
            )
        finally:
            self._generating = False
            # D20 Stage-1 — autonomous gap-sensing. Best-effort:
            # detect a felt-capability-gap in the user's message;
            # if one fires, the orchestrator creates a consent card
            # in the cockpit. Fire-and-forget on a thread so the
            # match → eval → propose → SQLite chain doesn't block
            # the next user turn. The helper is fail-closed inside
            # itself; an extra try/except here protects against
            # asyncio.to_thread refusing the task. Cooldown gates
            # duplicate cards across turns. chat_id mirrors the
            # rest of this surface (user-id-as-chat-id) so the
            # supersession bucket aligns with other card paths.
            try:
                from core.infra.capability_gap_detector import (
                    maybe_fire_capability_proposal,
                )

                asyncio.create_task(
                    asyncio.to_thread(
                        maybe_fire_capability_proposal,
                        user_text,
                        chat_id=str(self.authorized_user),
                        user_id=str(user_id),
                    )
                )
            except Exception as _gap_e:
                logger.debug(
                    "gap_detector hook (post-message) failed: %s",
                    _gap_e,
                )

        # Check if an interrupt arrived during generation
        if not self._interrupt_queue.empty():
            new_text = self._interrupt_queue.get_nowait()
            logger.info("Processing interrupted message: %s", new_text[:60])
            self._generating = True
            self._interrupt_queue = asyncio.Queue()
            interrupt_subjective_duration_line = _telegram_subjective_duration_line(record_contact=False)
            try:
                await self._process_message(
                    update,
                    context,
                    new_text,
                    subjective_duration_line=interrupt_subjective_duration_line,
                )
            finally:
                self._generating = False
                # D20 Stage-1 — same hook on the interrupt path.
                # Same shape as the main hook: async fire-and-forget
                # via asyncio.to_thread, chat_id aligned with the
                # rest of this surface, fail-closed.
                try:
                    from core.infra.capability_gap_detector import (
                        maybe_fire_capability_proposal,
                    )

                    asyncio.create_task(
                        asyncio.to_thread(
                            maybe_fire_capability_proposal,
                            new_text,
                            chat_id=str(self.authorized_user),
                            user_id=str(user_id),
                        )
                    )
                except Exception as _gap_e:
                    logger.debug(
                        "gap_detector hook (interrupt path) failed: %s",
                        _gap_e,
                    )

    async def _execute_intent(self, intent: str, update, context) -> str | None:
        """Execute a matched machine intent and return formatted response."""
        import subprocess as _sp

        try:
            if intent == "status":
                snap = perception_snapshot()
                gpu = snap.get("gpu") or {}
                services = (
                    _sp.run(
                        ["systemctl", "is-active", "maez", "maez-web", "nginx", "ollama"],
                        capture_output=True,
                        text=True,
                        timeout=5,
                        env=sanitize_env(),
                    )
                    .stdout.strip()
                    .split("\n")
                )
                svc_names = ["maez", "maez-web", "nginx", "ollama"]
                svc_str = " | ".join(f"{n}: {s}" for n, s in zip(svc_names, services, strict=False))
                msg = (
                    f"All systems nominal.\n"
                    f"CPU {snap['cpu']['percent']}% | RAM {snap['ram']['percent']}% | "
                    f"GPU {gpu.get('temperature_c', '?')}°C\n"
                    f"VRAM {gpu.get('memory_used_mb', 0):.0f}MB | "
                    f"Disk {snap['disk']['percent']}%\n"
                    f"Services: {svc_str}\n"
                    f"Memories: {self.memory.count()}"
                )
                return msg

            elif intent == "logs":
                result = _sp.run(
                    ["tail", "-20", "/home/rohit/maez/logs/maez.log"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    env=sanitize_env(),
                )
                errors = [l for l in result.stdout.split("\n") if "ERROR" in l or "WARNING" in l]
                if errors:
                    return f"Recent issues ({len(errors)}):\n" + "\n".join(errors[-5:])
                return "Logs are clean. No errors or warnings in the last 20 lines."

            elif intent == "restart_maez":
                return (
                    "I can't restart myself — that would interrupt this conversation. "
                    "Run `sudo systemctl restart maez` from terminal if needed."
                )

            elif intent == "claude_status":
                result = _sp.run(
                    ["pgrep", "-a", "claude"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    env=sanitize_env(),
                )
                if result.stdout.strip():
                    lines = result.stdout.strip().split("\n")
                    return f"Claude Code is running ({len(lines)} process{'es' if len(lines) > 1 else ''})."
                return "Claude Code is not currently running."

            elif intent == "reboot":
                return (
                    "System reboot requires explicit approval. "
                    "Say 'approve reboot' or run `sudo reboot` from terminal."
                )

            elif intent == "disk":
                result = _sp.run(
                    ["df", "-h", "/", "/home"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    env=sanitize_env(),
                )
                return f"Disk usage:\n{result.stdout.strip()}"

            elif intent == "memory":
                stats = self.memory.memory_stats()
                return (
                    f"Memory banks:\n"
                    f"  Raw archive: {stats['raw']} memories\n"
                    f"  Daily consolidations: {stats['daily']}\n"
                    f"  Core memories: {stats['core']}\n"
                    f"  Total: {stats['total']}"
                )

        except Exception as e:
            logger.error("Intent execution failed (%s): %s", intent, e)
            return None

        return None

    def _run_jarvis_loop(
        self,
        user_text: str,
        max_iters: int = 4,
        recovery_seed: Optional[dict] = None,
    ) -> str:
        """Delegates to `core.brain_loop.run_brain_loop`.

        The Jarvis tool-use loop was extracted in 2026-04-20 so the
        vendored `skills/surface/` Telegram adapter can share the same
        brain iteration without duplication. This method is kept as a
        thin wrapper so existing callers on this class (including
        `_handle_private_text` and `_run_jarvis_recovery`) continue
        working unchanged.

        The callback `send_intermediate` is wired to
        `self._send_card_message` so the Lane-3 self-mod dialog
        opening still lands on Telegram before the final synthesis.
        """
        if not self.actions:
            return ""
        try:
            from core import brain_loop as _brain_loop
        except Exception as e:
            logger.debug("brain_loop unavailable: %s", e)
            return ""

        def _send_intermediate(text: str) -> None:
            """Bridge brain_loop's callback to Telegram's send helper."""
            try:
                self._send_card_message(
                    chat_id=str(self.authorized_user),
                    text=text,
                )
            except Exception as e:
                logger.warning(
                    "failed to surface brain_loop intermediate message: %s",
                    e,
                )

        return _brain_loop.run_brain_loop(
            user_text,
            action_engine=self.actions,
            get_pipeline=self._get_pipeline,
            user_id="rohit",
            chat_id=str(self.authorized_user),
            surface="telegram",
            model=MODEL,
            max_iters=max_iters,
            recovery_seed=recovery_seed,
            send_intermediate=_send_intermediate,
        )

    def _find_recovery_new_card_cmd(self, since_ts: float) -> str | None:
        """Return the cmd/path of the newest open card created after
        `since_ts` for this chat. Used by the recovery synthesis so the
        narrative is grounded on the card the recovery actually queued,
        not on generic examples in the prompt. Returns None if no new
        card was created during the recovery pass."""
        try:
            store = getattr(self, "_card_store", None)
            if store is None:
                return None
            from core.pending_cards import AWAITING_STATUSES

            cards = store.get_open_for_channel(
                channel="telegram_text",
                chat_id=str(self.authorized_user),
            )
            new_awaiting = [
                c
                for c in cards
                if c.status in AWAITING_STATUSES and (c.created_at or 0) >= since_ts
            ]
            if not new_awaiting:
                return None
            # Newest first
            new_awaiting.sort(key=lambda c: c.created_at or 0, reverse=True)
            c = new_awaiting[0]
            params = getattr(c, "params", None) or {}
            return params.get("cmd") or params.get("path") or params.get("query") or None
        except Exception as e:
            logger.debug("recovery new-card lookup failed: %s", e)
            return None

    def _synthesize_recovery_reply(
        self,
        recovery_seed: dict,
        recovery_transcript: str,
        new_card_cmd: str | None = None,
    ) -> str:
        """Turn a recovery Jarvis transcript into a short natural-language
        message the owner can read. Called from _try_card_reply_intent after a
        card-execution failure triggered an autonomous pivot pass.

        The synthesis is ONE short non-streaming LLM call so the reply
        lands fast. Grounded entirely on the recovery transcript — no
        speculation, no claims of things not in the transcript. Honors
        the same ⏳ / ✓ / ✗ semantics as the main reply path.

        Returns the reply text (or an empty string on failure)."""
        try:
            from core import llm_client as _llm_client
        except Exception as e:
            logger.debug("recovery synthesis llm_client unavailable: %s", e)
            return ""
        fa = recovery_seed.get("failed_action", "?")
        fp_str = str(recovery_seed.get("failed_params", {}))[:200]
        err = str(recovery_seed.get("error", ""))[:400]
        intent = recovery_seed.get("original_intent", "")
        depth = int(recovery_seed.get("recovery_depth", 1))
        # Deterministic state detection on the recovery transcript. The
        # terminal-state discipline in the recovery seed prompt forces the
        # transcript into exactly one of three recognizable shapes. We tell
        # the synthesis LLM which shape matched so it can't get creative.
        has_pending_card = "⏳" in recovery_transcript
        has_dead_end = (
            "NO_RECOVERY_FOUND" in recovery_transcript or "recovery_dead_end" in recovery_transcript
        )
        has_success = "✓" in recovery_transcript and not has_pending_card

        # 2026-04-16 fix: only claim a pending card if a real one was
        # actually queued. The transcript's "⏳" marker is necessary but
        # not sufficient — we also need a real card row in the store.
        # If new_card_cmd is None, the recovery transcript may have a
        # pending marker but no card persisted (e.g., covenant/audit
        # refused). Treat that as "no recovery queued" — no fake
        # narration about a card that doesn't exist.
        card_actually_persisted = has_pending_card and new_card_cmd is not None

        if card_actually_persisted:
            state_hint = (
                "STATE: A new approval card has been queued for the owner. "
                "The EXACT command on that card is:\n"
                f"    {new_card_cmd}\n"
                "Your reply must tell the owner: (1) the first try didn't "
                "work and why (one sentence), (2) what the new queued "
                "command is — describe it using the EXACT command above, "
                "not a generic label. If the new command happens to be "
                "the same as the failed one, say so honestly ('I re-"
                "proposed the same command'). Do not invent a different "
                "approach that isn't in the command. (3) you're waiting "
                "for his approval on the new card."
            )
        elif has_pending_card and new_card_cmd is None:
            state_hint = (
                "STATE: The recovery transcript claims a pending card but "
                "no real card was persisted in the store. Tell the owner: the "
                "first try failed and the recovery attempt did not "
                "successfully queue a new action. Do NOT claim a card is "
                "waiting for approval — there isn't one."
            )
            # Override the flag so the hard rules below apply correctly
            has_pending_card = False
        elif has_dead_end:
            state_hint = (
                "STATE: You searched but could not find a safe automated fix. "
                "Your reply must tell the owner: (1) the first try failed and why, "
                "(2) what you investigated, (3) why no automated recovery is "
                "possible (quote the dead-end reason from the transcript), "
                "(4) what the owner could do manually if he wants to pursue it. "
                "Be honest about the dead end — do NOT fabricate a pending card."
            )
        elif has_success:
            state_hint = (
                "STATE: A Lane 0 action in the recovery pass executed inline "
                "and produced a real result. Your reply must tell the owner what "
                "you actually checked/found from the transcript output. Do "
                "NOT claim you installed or fixed anything unless the "
                "transcript shows a successful mutating action."
            )
        else:
            state_hint = (
                "STATE: The recovery pass produced no clear result. Tell the owner "
                "the first try failed and the recovery attempt was inconclusive. "
                "Do not fabricate progress."
            )

        prompt = (
            f"You are Maez. the owner's original ask was: {intent!r}\n"
            f"Your first attempt, {fa}({fp_str}), failed with:\n{err}\n\n"
            f"You then ran a recovery pass (attempt #{depth}). Here is the "
            f"AUTHORITATIVE transcript of what actually happened in that "
            f"recovery pass:\n\n"
            f"{recovery_transcript}\n\n"
            f"{state_hint}\n\n"
            f"Write a SHORT Telegram message to the owner (2-4 sentences) "
            f"following the STATE above. HARD RULES:\n"
            f"  1. Only mention tools, commands, packages, or files that "
            f"appear in the transcript. Do NOT invent a card that isn't "
            f"there. Do NOT claim things ran that weren't in the transcript.\n"
            f"  2. Start with a short acknowledgment that the first try "
            f"didn't work.\n"
            f"  3. Be honest and specific. Name the actual error class "
            f"(e.g. 'Ubuntu 24.04 default repos don't carry openrgb') "
            f"rather than a vague 'it didn't work'.\n"
            f"  4. If the STATE above says you're waiting for approval, "
            f"say exactly that — don't say 'I'll install it now'. If the "
            f"STATE says no recovery found, say exactly that — don't "
            f"invent an alternative to propose.\n"
        )
        try:
            from core.routing.brain_gateway import with_purpose as _brain_purpose

            with _brain_purpose("voice_reply"):
                resp = _llm_client.chat(
                    model=MODEL,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are Maez. Your replies are honest, grounded, and short.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    stream=False,
                    think=False,
                    options={"temperature": 0.3, "num_predict": 220},
                )
            return (resp.message.content or "").strip()
        except Exception as e:
            logger.warning("recovery synthesis LLM call failed: %s", e)
            return ""

    async def _process_message(
        self,
        update,
        context,
        user_text: str,
        *,
        subjective_duration_line: str = "",
    ) -> str:
        """Build context, stream response, handle post-processing."""
        import re as _re
        import time as _time

        _s4_result = guard_owner_text(
            user_text,
            surface="telegram_legacy_owner",
            crisis_signal_writer=PrivateThoughtsCrisisSignalWriter(
                getattr(getattr(self, "daemon", None), "private_thoughts", None)
            ),
        )
        if _s4_result.matched:
            mark = getattr(getattr(self, "daemon", None), "_mark_m1_s4_policy", None)
            if callable(mark):
                mark(_s4_result.promotion_policy)
            return _audit_telegram_reply(
                _s4_result.answer_text or "",
                surface="telegram_clinical_boundary",
            )

        # Tolerant command dispatch. Telegram MarkdownV2 renders `_` as
        # italic, so when Maez emits `/apply_dream 49` the user's copy/
        # retype often arrives as `/apply dream 49` (space) or
        # `/applydream 49` (underscore stripped). CommandHandler only
        # fires on the exact underscored form, so these fell through to
        # chat routing and ran irrelevant shell queries. Intercept
        # known-command variants here and dispatch manually.
        _CMD_VARIANT_RE = _re.compile(
            r"^/\s*(apply|reject)[\s_\-]*dream\s+(\d+)\s*$",
            _re.IGNORECASE,
        )
        _cmd_match = _CMD_VARIANT_RE.match(user_text.strip())
        if _cmd_match:
            verb = _cmd_match.group(1).lower()
            prop_id_str = _cmd_match.group(2)
            # Rebuild context.args so the existing handler works unchanged.
            context.args = [prop_id_str]
            if verb == "apply":
                await self._handle_apply_dream(update, context)
            else:
                await self._handle_reject_dream(update, context)
            return ""

        # Check for machine intent first
        intent = _match_intent(user_text)
        if intent:
            logger.info("Matched intent: %s for '%s'", intent, user_text[:60])
            response = await self._execute_intent(intent, update, context)
            if response:
                await _reply_text(update, response)
                # 5x.B Pass 1: bond transcript; mixed-origin (see 5x.D).
                self.memory.store_telegram(
                    f"the owner asked: {user_text}\nMaez replied: {response}",
                    provenance_source="user_utterance",
                    trust_tier="lived",
                )
                self._thread_last_active = _time.time()
                return response

        _telegram_user_msg_turn_id = None
        _telegram_ledger_db_path = None
        _telegram_surface = "telegram_text"
        try:
            from core.cognition.envelope_builder import (
                default_ledger_db_path as _default_ledger_db_path,
            )
            from core.ledger.writer import try_write_turn as _try_write_turn

            _telegram_ledger_db_path = _default_ledger_db_path()
            if _telegram_ledger_db_path:
                _telegram_user_msg_turn_id = _try_write_turn(
                    _telegram_ledger_db_path,
                    "user_message",
                    user_text,
                    surface=_telegram_surface,
                )
        except Exception as _ledger_user_exc:
            logger.debug(
                "telegram_text user_message ledger persistence skipped: %s",
                _ledger_user_exc,
            )

        # Multi-turn thread management
        if _time.time() - self._thread_last_active > 1800:
            self._conversation_thread = []

        # Build context
        snap = perception_snapshot()
        system_state = format_snapshot(snap)
        recalled = self.memory.recall_for_telegram(user_text)
        # Slice 3 wiring (2026-05-07): coordinate recall cap with the
        # evidence envelope per SLICE_3_0d §1. Resolver returns 52K
        # when envelope is present in the prompt (downstream below);
        # 60K when MAEZ_EVIDENCE_ENVELOPE_DISABLED=1. Without this
        # cap, recall + envelope can overflow the 32K llama.cpp ctx.
        from core.cognition.envelope_builder import (
            resolve_recall_cap_chars as _resolve_recall_cap,
        )

        memory_block = self.memory.format_for_prompt(
            recalled,
            max_chars=_resolve_recall_cap(),
        )

        web_context = ""
        _tv_empty_search = False
        _tv_search_source = "web"
        if _telegram_pipeline_a_web_search_enabled() and needs_web_search(user_text):
            logger.info("Web search triggered for: %s", user_text[:80])
            _tv_search_source = "news_rss" if is_news_query(user_text) else "web"
            if _tv_search_source == "news_rss":
                sr = search_rss(user_text, max_results=5)
            else:
                sr = web_search(user_text, max_results=3)
            from core.routing.focused_cognition import (
                is_empty_search_result as _is_empty_search_result,
            )

            _tv_empty_search = _is_empty_search_result(sr)
            if sr.get("success") and not _tv_empty_search:
                web_context = web_format(sr)

        # Session 11y: Jarvis tool-use loop. Lets the LLM emit TOOL_CALL
        # directives that get dispatched through ActionEngine, so chat
        # messages like "is openrgb installed" or "install it" actually
        # do the thing instead of becoming hedged text. Runs in executor
        # because the LLM client is synchronous; gated by a regex so
        # casual chat doesn't pay the planning latency.
        jarvis_block = ""
        try:
            loop = asyncio.get_running_loop()
            jarvis_block = await loop.run_in_executor(
                get_shared_executor(),
                self._run_jarvis_loop,
                user_text,
            )
        except Exception as e:
            logger.warning("jarvis loop failed: %s", e)

        # N+1 Option A (2026-04-16): after Jarvis probes, run one
        # focused structured call to propose a real next-step and
        # route it through the pipeline. This creates real pending
        # state (card or direct execution) BEFORE the user-facing
        # reply prompt is built — so the ACTUAL STATE block injected
        # next will reflect the real proposal.
        try:
            loop = asyncio.get_running_loop()
            next_step = await loop.run_in_executor(
                get_shared_executor(),
                self._propose_next_step_from_probe,
                user_text,
            )
            if next_step:
                logger.info(
                    "next-step proposer: kind=%s summary=%s",
                    next_step.get("kind"),
                    (next_step.get("summary") or "")[:100],
                )
        except Exception as e:
            logger.debug("next-step proposer dispatch failed: %s", e)

        prompt = (
            f"{system_state}\n"
            f"Note: VRAM usage of 17-22GB is the baseline for this system. "
            f"Do not mention it unless it exceeds 23GB.\n\n"
        )
        if subjective_duration_line:
            prompt += subjective_duration_line + "\n\n"
        # N+1 (2026-04-16): inject [ACTUAL STATE] near the top of the
        # prompt so the LLM anchors on real pending state and real
        # probe outcomes. Reduces fake-state narration at source and
        # helps the LLM build concrete next-step plans from actual
        # tool results. See _build_actual_state_block.
        try:
            actual_state = self._build_actual_state_block()
        except Exception as e:
            logger.debug("actual state block build failed: %s", e)
            actual_state = ""
        if actual_state:
            prompt += actual_state + "\n\n"
        prompt += f"{_get_circadian_context()}\n\n"
        public_ctx = _get_public_context_for_telegram()
        if public_ctx:
            prompt += public_ctx + "\n\n"
        # Bug C fix (2026-04-15 intelligence audit): inject a ground-truth
        # block describing what Maez's body just did in this chat in the
        # last 10 minutes. Without this, follow-up questions like "are you
        # still investigating?" get answered from stale memory recall,
        # with no record of the card that executed 60 seconds ago. This
        # block is the authoritative state that the LoRA should trust
        # over its own intuition about what happened.
        try:
            body_activity = self._build_recent_body_activity_block(since_seconds=600.0)
        except Exception as e:
            logger.debug("body activity block build failed: %s", e)
            body_activity = ""
        if body_activity:
            prompt += body_activity + "\n\n"
        if memory_block:
            prompt += memory_block + "\n\n"
        if web_context:
            prompt += (
                f"{web_context}\n\n"
                f"INSTRUCTION: Real search results above. Synthesize, don't list.\n\n"
            )
        # Add current message to conversation thread. When the thread
        # exceeds 12 turns, compress the dropped head into a single
        # system-role summary message via core.context_compressor (uses
        # the judge llama-server as summarizer, fail-safe to plain
        # tail-truncation). Prior behavior silently chopped everything
        # before the last 12, losing any Active Task mentioned earlier.
        self._conversation_thread.append({"role": "user", "content": user_text})
        if len(self._conversation_thread) > 12:
            try:
                from core.context_compressor import compress as _compress

                self._conversation_thread = _compress(
                    self._conversation_thread,
                    keep_tail_n=12,
                )
            except Exception as _ce:
                # Fail-safe: behave exactly as before on any unexpected error.
                logger.debug("context_compressor failed, falling back to plain truncation: %s", _ce)
                self._conversation_thread = self._conversation_thread[-12:]

        # Build the final user message. The Jarvis transcript MUST be
        # attached to the final user message (not buried in the first
        # context blob) so the LLM reads it LAST — right before it
        # generates the reply. The earlier structure put jarvis_block
        # in message #2 and then appended 12 conversation turns + the
        # current user_text after it, which let recency bury the
        # transcript's rules and the LLM fabricated around the card's
        # "CARD_CREATED: waiting for your approval" status by pretending
        # the check had already run.
        final_user = user_text
        _telegram_log_jarvis_block_state(
            chat_id=str(getattr(getattr(update, "effective_chat", None), "id", self.authorized_user)),
            jarvis_block=jarvis_block,
        )
        if jarvis_block:
            final_user = (
                f"{user_text}\n\n"
                f"{jarvis_block}\n\n"
                f"{_telegram_hard_instruction_for_jarvis_block(jarvis_block)}"
            )
        else:
            # Track A fabrication fix: non-action turns need to be pinned
            # too. Without this marker, when the Jarvis loop doesn't fire
            # (conversational turn, short message, opinion question), the
            # streaming reply is shaped only by memory recall — and memory
            # recall contains past-turn proposals and past states the LoRA
            # would otherwise blur into current state.
            #
            # v3 (after live tests): v2 was too prescriptive and the LoRA
            # pattern-matched on a specific example phrase ("what were
            # you approving?") and applied it as a default deflection
            # even to clear questions like "what version of Python do we
            # have?". Over-correction. v3 is shorter, principle-based,
            # with an explicit anti-deflection rule and context-handling
            # rule so follow-up questions inherit their topic from the
            # previous turn. Goal: fewer specific phrases for the LoRA
            # to latch onto, more emphasis on the underlying principle.
            final_user = (
                f"{user_text}\n\n"
                "[TURN STATE — NO TOOLS RAN THIS TURN]\n"
                " You did not run any NEW tools on the owner's machine for\n"
                " THIS message. No tool will run while you are writing\n"
                " this reply. This is a text-reply window. This describes\n"
                " THIS TURN ONLY; it does not mean this Telegram surface\n"
                " lacks tools or that you lack a tool loop. Do not say\n"
                " you are stuck in chat, cannot execute tools from here,\n"
                " or need the action loop wired into this channel.\n"
                "\n"
                " IMPORTANT: a card from an earlier turn may have\n"
                " executed between turns, even though you didn't trigger\n"
                " a new tool this turn. Read the BODY ACTIVITY block\n"
                " earlier in this prompt — that's the authoritative\n"
                " record of what your body did in the last 10 minutes.\n"
                " If it shows a card as EXECUTED ✓, report its output\n"
                " as fact. Do not say you're 'still waiting for\n"
                " approval' on a card that already ran.\n"
                "\n"
                "THE PRINCIPLE:\n"
                " Your reply must match what you actually know, what you\n"
                " actually did this turn (nothing except think and talk),\n"
                " and what you could offer to do next. Do not claim action\n"
                " you didn't take. Do not deflect clear questions with\n"
                " fake clarifying questions. Do answer from memory when\n"
                " memory has the information. Do offer to check when a\n"
                " fresh tool run would help.\n"
                "\n"
                "HONEST FRAMINGS (use these, they're the only honest ones):\n"
                " 1. Past observation from memory — 'I noticed...', 'last\n"
                "    I saw...', 'the last check I have was...'. Draws on\n"
                "    real memory, framed as history.\n"
                " 2. Current internal state — 'I'm feeling...', 'I think...',\n"
                "    'I'm not sure...'. Self-report, not action.\n"
                " 3. Future offer — 'want me to check?', 'I can look into\n"
                "    that if you want'. Puts the decision in the owner's hands.\n"
                "    Does not commit to action.\n"
                "\n"
                "FORBIDDEN (all tenses, all aspects, when no tool ran):\n"
                " Any claim that a tool ran, is running, or is about to\n"
                " run in response to this message. Including the tricky\n"
                " PRESENT-PERFECT tense that sounds like memory but reads\n"
                " as current action. Examples in all tenses:\n"
                "   - 'I checked' / 'I just checked' / 'I found'\n"
                "   - 'I'm checking' / 'I'm looking' / 'I'm searching'\n"
                "   - 'I'll check now' / 'let me look' / 'one moment'\n"
                "   - 'I just ran X' / 'running that now'\n"
                "   - 'I've checked' / 'I've proposed' / 'I've found'\n"
                "   - 'I have checked' / 'I've already installed'\n"
                "   - 'I've been checking' / 'I've been monitoring'\n"
                "   - 'I can't execute tools from here'\n"
                "   - 'I don't have a tool loop on this channel'\n"
                "   - 'I'm stuck in this chat surface'\n"
                "   - 'the action loop needs to be wired into this channel'\n"
                " These are all false right now. No tool is running.\n"
                "\n"
                " PRESENT-PERFECT GOTCHA (the 'I've proposed' trap):\n"
                " English lets you say 'I've proposed installing X via a\n"
                " Telegram card' and mean either (a) 'in my past I did\n"
                " propose that, as a memory fact' or (b) 'I just proposed\n"
                " it right now'. the owner will read (b) regardless of which\n"
                " you meant. So the rule is: if the thing you're about\n"
                " to describe in present-perfect happened in a PAST TURN\n"
                " (not this one), you must reframe it explicitly as past:\n"
                "   BAD:  'I've proposed installing it via a card'\n"
                "   GOOD: 'Earlier I proposed installing it via a card'\n"
                "         'In our past conversations I proposed that'\n"
                "         'I don't have an active proposal right now,\n"
                "          but in the past I've tried X, Y, and Z'\n"
                " The difference matters because present-perfect without\n"
                " a temporal anchor reads as 'this turn'. Always anchor.\n"
                "\n"
                "ANTI-DEFLECTION RULE (v3, read this carefully):\n"
                " If the owner asks a CLEAR question, answer it clearly. Do\n"
                " NOT respond with a clarifying question unless the\n"
                " message really is ambiguous.\n"
                "\n"
                " CLEAR questions — answer from memory or offer to check:\n"
                "   'What's up with X?' (answer from memory + offer)\n"
                "   'Are you sure?' / 'When did you last check?'\n"
                "       (answer from memory framed as history — if you\n"
                "       don't have a fresh check, say so explicitly:\n"
                "       'I don't have a fresh check, my last observation\n"
                "       was from [when]')\n"
                "   'What version of X do we have?'\n"
                "       (offer: 'I don't have that cached, want me to\n"
                "       check?')\n"
                "   'How are you?' / 'What's your mood?' (self-report)\n"
                "   'Did X happen?' (answer from memory or offer)\n"
                "\n"
                " AMBIGUOUS approval messages — clarifying question ONLY:\n"
                "   'I said yes' (when no card is open)\n"
                "   'I approve' (when no card is open)\n"
                "   'go ahead' (when no card is open and no context)\n"
                "   'proceed' (when no card is open)\n"
                "   For these, ask what they're referring to.\n"
                "\n"
                " The phrase 'what were you approving?' is RESERVED for\n"
                " real ambiguous-approval messages above. Do NOT use it\n"
                " as a default deflection for clear questions.\n"
                "\n"
                "CONTEXT-INHERITANCE RULE:\n"
                " Follow-up questions carry their topic from the previous\n"
                " turn. If the owner just asked about openrgb and now asks\n"
                " 'are you sure?' or 'when did you last check?', he's\n"
                " asking about openrgb, not about something new. Use the\n"
                " conversation thread above to resolve what 'it' or 'that'\n"
                " or a bare question refers to. Do not drop context.\n"
                "\n"
                " The conversation thread at the top of this prompt is\n"
                " the authoritative record of what you two have been\n"
                " talking about. Read it before answering.\n"
                "\n"
                "SUMMARY: Answer the question honestly, in the right tense,\n"
                "drawing on memory for history, on internal state for mood,\n"
                "and offering tools for fresh data. If you don't know, say\n"
                "so. If you need to check, ask 'want me to?'. Don't claim\n"
                "action. Don't deflect clarity. Just answer.\n"
            )

        # Capability registry + organism-block injection. Same rails
        # as the CLI and the daemon's handle_message path — gives the
        # model grounded facts + fabrication memory + residue +
        # self-model to consult before generating. Missing here was
        # why the 2026-04 Telegram fabrications went through
        # unsteered. Silent on failure.
        _jarvis_system_prompt = self.system_prompt
        try:
            from core.capability_registry import prompt_snippet as _cap_snippet

            _jarvis_system_prompt += "\n\n" + _cap_snippet()
        except Exception:
            pass
        try:
            from core.infra.capability_manual_context import manual_context_snippet

            _manual_context = manual_context_snippet(user_text)
            if _manual_context:
                _jarvis_system_prompt += "\n\n" + _manual_context
        except Exception:
            pass

        # Slice 3 wiring (2026-05-07): build the evidence envelope so
        # the LLM sees what it MAY claim and what's forbidden BEFORE
        # generation, and so the audit gets the same context.
        # Returns None when MAEZ_EVIDENCE_ENVELOPE_DISABLED=1; the
        # renderer treats None as empty (legacy prompt shape).
        try:
            from core.cognition.envelope_builder import (
                build_envelope as _build_envelope,
                default_ledger_db_path as _default_ledger_db,
                render_envelope_for_prompt as _render_envelope,
            )
            from core.safety.audit_signal_manifest import (
                default_audit_signals as _default_signals,
            )

            _sp, _sa = _default_signals("telegram_text")
            _evidence_envelope = _build_envelope(
                ledger_db_path=_default_ledger_db(),
                signals_present=_sp,
                signals_absent=_sa,
                tool_results=[],
            )
            _envelope_block = _render_envelope(_evidence_envelope)
        except Exception as _env_exc:
            logger.warning(
                "evidence_envelope build failed for telegram_text "
                "(continuing without envelope): %s",
                _env_exc,
            )
            _evidence_envelope = None
            _envelope_block = ""

        # Build messages with system context + thread
        messages = [
            {"role": "system", "content": _jarvis_system_prompt},
            {"role": "user", "content": prompt},
        ]
        # Add thread history (skip current message since it's in prompt)
        for turn in self._conversation_thread[:-1]:
            messages.append(turn)
        # Envelope block sits as a system message immediately before
        # the final user turn so the model attends to its constraints
        # at maximum recency. Empty string when disabled — keeps the
        # message list shape identical to legacy in that case.
        if _envelope_block:
            messages.append({"role": "system", "content": _envelope_block})
        messages.append({"role": "user", "content": final_user})

        # Non-streaming reply — Jarvis runs tools first, then one clean synthesis call.
        # Eliminates fabrication incentive: the model sees the full transcript before
        # writing a single word, so there's nothing to invent.
        _telegram_audit_ran = False
        _telegram_audit_changed = False
        try:
            await _bot_send_chat_action(context.bot, chat_id=update.effective_chat.id, action="typing")

            full_reply = ""

            if self.daemon is not None:
                try:
                    _owner_now = _time.time()
                    self.daemon._rohit_active_until = _owner_now + 15.0
                    self.daemon._last_owner_interaction_ts = _owner_now
                except Exception:
                    pass

            if _tv_empty_search:
                from core.routing.focused_cognition import (
                    build_honest_empty_reply as _build_honest_empty_reply,
                )

                _hr = _build_honest_empty_reply(
                    query=user_text,
                    source=_tv_search_source,
                    surface="voice",
                )
                logger.info(
                    "honest_empty_reply surface=voice source=%s mode=%s "
                    "call_purpose=honest_empty",
                    _tv_search_source,
                    _hr.mode,
                )
                _he_env = owner_text_envelope(
                    bot_route="voice_owner_private",
                    chat_id=str(update.effective_chat.id),
                    text=_hr.reply,
                    source_ref="telegram_voice:honest_empty",
                )
                await _bot_send_message(
                    context.bot,
                    chat_id=update.effective_chat.id,
                    text=_hr.reply,
                    envelope=_he_env,
                )
                return _hr.reply

            from core import llm_client as _llm_client

            from core.routing.brain_gateway import with_purpose as _brain_purpose

            with _brain_purpose("voice_reply"):
                resp = _llm_client.chat(
                    model=MODEL,
                    messages=messages,
                    stream=False,
                    think=False,
                    options={"temperature": 0.5, "num_predict": 600},
                )
            full_reply = (resp.message.content or "").strip()
            # Strip grounding block echoes if model reflected them back
            full_reply = _re.sub(
                r"\[WHAT HAPPENED THIS TURN.*?\]\s*",
                "",
                full_reply,
                flags=_re.DOTALL,
            ).strip()
            full_reply = _re.sub(
                r"\[JARVIS TRANSCRIPT.*?\]\s*",
                "",
                full_reply,
                flags=_re.DOTALL,
            ).strip()
            full_reply = _re.sub(
                r"\[\d{4}-\d{2}-\d{2}.*?##.*?\n.*?\n.*?\n",
                "",
                full_reply,
                flags=_re.DOTALL,
            ).strip()
            full_reply = full_reply or "(no response)"
            # Structural self-claim audit — catches the Maelstrom-class
            # fabrications before they reach Telegram. This path was
            # missing audit (only dialog/terminal/fallback replies were
            # audited), which is why the 2026-04-19 "Maelstrom merge"
            # turns escaped on this surface. Silent on audit failure.
            reply, _telegram_audit_ran, _telegram_audit_changed = _audit_telegram_reply_with_status(
                full_reply,
                surface="telegram_text",
                evidence_envelope=_evidence_envelope,
            )

            for part in split_long_message(reply):
                envelope = owner_text_envelope(
                    bot_route="voice_owner_private",
                    chat_id=str(update.effective_chat.id),
                    text=part,
                    source_ref="telegram_voice:legacy_polling_reply",
                )
                await _bot_send_message(context.bot,
                    chat_id=update.effective_chat.id,
                    text=part,
                    envelope=envelope,
                )
                if len(split_long_message(reply)) > 1:
                    await asyncio.sleep(0.3)

        except Exception as e:
            logger.error("Telegram reasoning failed: %s", e)
            full_reply = f"Reasoning error: {e}"
            # T2.A (2026-05-04 audit): the terminal-fallback branch
            # was sending reply_text() WITHOUT going through the
            # honesty-audit gate. The b672a2d AST regression guard
            # passed because the success path above audits — but
            # the fallback string can echo exception text /
            # canary triggers. Route through the same gate as the
            # success path. Mirror of the b672a2d (T1.13)
            # audit-routing pattern.
            reply = _audit_telegram_reply(
                full_reply,
                surface="telegram_text",
                evidence_envelope=_evidence_envelope,
            )
            await _reply_text(update, reply)
            return reply

        logger.info("Telegram reply: %s", reply[:100])

        # 2026-04-17 offer-binding + probe-bridge now delegate to the
        # controller. Both scan the ORIGINAL full_reply (before guard
        # rewrite) so an offer phrase is captured regardless of whether
        # tools fired this turn.
        _channel, _chat_id = "telegram_text", str(self.authorized_user)
        _raw = (self._last_actionable_user_text or user_text or "").strip()
        self._controller.maybe_store_offer(
            _channel,
            _chat_id,
            reply=full_reply or "",
            raw_user_text=_raw,
            query_deriver=self._derive_search_query,
        )
        self._controller.maybe_store_probe_bridge_offer(
            _channel,
            _chat_id,
            reply=full_reply or "",
            raw_user_text=_raw,
            query_deriver=self._derive_search_query,
            had_action=bool(locals().get("_turn_had_action", False)),
        )

        # Add response to conversation thread
        self._conversation_thread.append({"role": "assistant", "content": reply})
        self._thread_last_active = _time.time()

        # Post-processing
        #
        # Session 11y: the text-promise followup extractor that used to
        # live here is gone. It scraped phrases like "I'll check" from
        # replies and queued them; the delivery loop then fabricated
        # completions because no real action backed the promise. The
        # Jarvis loop up in _process_message now does the actual work
        # synchronously via ActionEngine before we stream the reply, so
        # there's nothing for a post-hoc extractor to commit to anyway.
        # Future grounded commitments (e.g. an async Tier-2 install that
        # completes after the reply is sent) should call
        # FollowUpQueue().add(desc, user_text, action_id=<id>) explicitly
        # at the site where they queue the action — not parsed out of the
        # LLM's prose.
        self._detect_and_queue_action(user_text, reply)
        from core.ledger.model_reply_persistence_warning import (
            warn_model_reply_persistence_skip,
        )

        try:
            from core.ledger.model_reply_persistence import (
                build_model_reply_audit_verdict,
                persist_model_reply,
            )

            if _telegram_ledger_db_path and _telegram_audit_ran:
                persist_model_reply(
                    db_path=_telegram_ledger_db_path,
                    raw_text=reply,
                    surface="telegram_text",
                    parent_turn_id=_telegram_user_msg_turn_id,
                    model_id=MODEL,
                    prompt_material={
                        "messages": messages,
                        "surface": "telegram_text",
                        "event": "autobiographical_continuity_turning_on",
                    },
                    soul_material=_jarvis_system_prompt,
                    evidence_envelope=_evidence_envelope,
                    audit_verdict=build_model_reply_audit_verdict(
                        surface="telegram_text",
                        audit_ran=_telegram_audit_ran,
                        changed_output=_telegram_audit_changed,
                    ),
                )
        except Exception as _ledger_reply_exc:
            warn_model_reply_persistence_skip(
                "telegram-text",
                "telegram_text model_reply ledger persistence skipped: %s",
                _ledger_reply_exc,
            )
        # 5x.B Pass 1: bond transcript; mixed-origin (see 5x.D).
        self.memory.store_telegram(
            f"the owner asked: {user_text}\nMaez replied: {reply}",
            provenance_source="user_utterance",
            trust_tier="lived",
        )
        try:
            from core.cognition.moment_assembly_diagnostic import (
                moment_assembly_turn,
            )

            with moment_assembly_turn(
                surface="telegram_text",
                turn_id=_telegram_user_msg_turn_id,
                lifecycle_phase="turn_close",
            ):
                pass
        except Exception as e:
            logger.warning(
                "telegram_text moment assembly completion diagnostic skipped: %s",
                e,
            )

        return reply

    def _detect_and_queue_action(self, user_text: str, reply: str):
        """If Maez's reply contains action intent, queue it for execution."""
        if not self.actions:
            return

        reply_lower = reply.lower()
        user_lower = user_text.lower()

        intent_phrases = [
            "i am proceeding",
            "i will proceed",
            "proceeding now",
            "executing now",
            "i will now",
            "i will run",
            "let me execute",
            "i will execute",
            "running now",
            "i am moving",
            "i will move",
        ]
        has_intent = any(p in reply_lower for p in intent_phrases)
        if not has_intent:
            return

        # Ollama model move
        if "ollama" in user_lower and any(w in user_lower for w in ["move", "symlink", "relocate"]):
            logger.info("Queueing Ollama model move action")
            self.actions.queue_action(
                "run_readonly_command",
                {"cmd": "du -sh /usr/share/ollama/.ollama/models"},
                "Verify Ollama model size before move",
                tier=1,
            )
            return

        # Disk cleanup
        if any(w in user_lower for w in ["clean", "cleanup", "free space", "clear"]):
            logger.info("Queueing disk cleanup action")
            from skills.disk_cleanup import scan

            report = scan()
            if report["total_bytes"] > 0:
                self.actions.queue_action(
                    "clean_temp_files",
                    {},
                    f"Disk cleanup requested by the owner — {report['total_bytes'] / (1024 * 1024):.0f} MB to free",
                    tier=1,
                )
            return

        # Generic command execution
        if any(w in user_lower for w in ["run", "execute", "check"]):
            logger.info("Action intent detected but no specific handler matched")
            return

    async def _handle_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command."""
        if not update.message or not update.effective_user:
            return
        if not self._is_authorized(update.effective_user.id):
            return

        snap = perception_snapshot()
        gpu = snap.get("gpu") or {}
        status = (
            f"Maez Status\n"
            f"CPU: {snap['cpu']['percent']}% | RAM: {snap['ram']['percent']}%\n"
            f"GPU: {gpu.get('utilization_pct', 'N/A')}% | "
            f"VRAM: {gpu.get('memory_used_mb', 0):.0f}/{gpu.get('memory_total_mb', 0):.0f} MB\n"
            f"GPU Temp: {gpu.get('temperature_c', 'N/A')}°C\n"
            f"Memories: {self.memory.count()}"
        )
        await _reply_text(update, status)

    async def _handle_cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /cancel <action_id> command."""
        if not update.message or not update.effective_user:
            return
        if not self._is_authorized(update.effective_user.id):
            return
        if not self.actions or not context.args:
            await _reply_text(update, "Usage: /cancel <action_id>")
            return

        action_id = context.args[0]
        if self.actions.cancel_pending(action_id):
            await _reply_text(update, f"Cancelled action {action_id}.")
        else:
            await _reply_text(update, f"Action {action_id} not found or already executed.")

    async def _handle_approve(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /approve <action_id> command."""
        if not update.message or not update.effective_user:
            return
        if not self._is_authorized(update.effective_user.id):
            return
        if not self.actions or not context.args:
            await _reply_text(update, "Usage: /approve <action_id>")
            return

        action_id = context.args[0]
        result = self.actions.approve_action(action_id)
        if result:
            status = "OK" if result.success else f"FAILED: {result.error}"
            await _reply_text(update, f"Action {action_id}: {status}\n{result.output[:500]}")
        else:
            await _reply_text(update, f"Action {action_id} not found or already handled.")

    async def _handle_pending(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /pending command — list pending actions."""
        if not update.message or not update.effective_user:
            return
        if not self._is_authorized(update.effective_user.id):
            return
        if not self.actions:
            await _reply_text(update, "Action engine not connected.")
            return

        pending = self.actions.get_pending()
        if not pending:
            await _reply_text(update, "No pending actions.")
            return

        lines = [f"Pending actions ({len(pending)}):"]
        for a in pending:
            lines.append(f"  [{a['id']}] T{a['tier']} {a['action']} — {a['reasoning'][:60]}")
        await _reply_text(update, "\n".join(lines))

    async def _handle_git(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message or not self._is_authorized(update.effective_user.id):
            return
        from skills.git_awareness import get_summary_for_telegram

        msg = get_summary_for_telegram()
        await _reply_text(update, msg)

    async def _handle_disk(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message or not self._is_authorized(update.effective_user.id):
            return
        from skills.disk_cleanup import scan, format_telegram_message

        report = scan()
        self._pending_cleanup = report
        await _reply_text(update, format_telegram_message(report))

    async def _handle_analyze(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message or not self._is_authorized(update.effective_user.id):
            return
        from skills.self_analysis import analyze, format_for_telegram

        result = analyze(self.memory, self.actions)
        await _reply_text(update, format_for_telegram(result))

    async def _handle_approve_cleanup(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message or not self._is_authorized(update.effective_user.id):
            return
        if hasattr(self, "_pending_cleanup") and self._pending_cleanup:
            from skills.disk_cleanup import execute_cleanup

            result = execute_cleanup(self._pending_cleanup)
            self._pending_cleanup = None
            await _reply_text(update,
                f"Cleanup done. Freed {result['freed_mb']:.0f} MB.\n" + "\n".join(result["results"])
            )
        else:
            await _reply_text(update, "No pending cleanup.")

    async def _handle_trust(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Set trust tier for a user. /trust username relationship tier"""
        if not update.message or not self._is_authorized(update.effective_user.id):
            return
        args = context.args
        if not args or len(args) < 3:
            await _reply_text(update, "Usage: /trust [username] [relationship] [tier 0-3]")
            return
        username, relationship = args[0], args[1]
        try:
            tier = int(args[2])
        except ValueError:
            await _reply_text(update, "Tier must be 0-3")
            return
        from skills.user_accounts import UserAccounts, _default_share_config

        accts = UserAccounts()
        user = accts.get_by_username(username) or accts.get_by_display_name(username)
        if not user:
            await _reply_text(update, f"No user found: '{username}'")
            return
        share_config = _default_share_config(tier, relationship)
        accts.confirm_user(user["uuid"], relationship, tier, share_config)
        await _reply_text(update,
            f"Got it. {user['display_name']} is your {relationship}. "
            f"Trust tier {tier}. I'll adjust what I share with them."
        )

    async def _handle_login(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Link Telegram account to Maez web account."""
        if not update.message:
            return
        args = context.args
        if not args or len(args) != 2:
            await _reply_text(update,
                "Usage: /login <username> <password>\nRegister first at http://64.85.211.140:11437"
            )
            return
        from skills.user_accounts import UserAccounts

        accts = UserAccounts()
        result = accts.login(args[0], args[1])
        if not result:
            await _reply_text(update, "Invalid username or password.")
            return
        telegram_id = str(update.effective_user.id)
        if update.effective_user.id == self.authorized_user:
            accts.link_private_owner(result["uuid"])
        else:
            accts.link_telegram(result["uuid"], telegram_id)
        display = result.get("display_name") or args[0]
        await _reply_text(update,
            f"Linked. I know you as {display} now, across all channels."
        )

    async def _handle_promote(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /promote <action_type> — lower tier for trusted action type."""
        if not update.message or not self._is_authorized(update.effective_user.id):
            return
        if not context.args:
            await _reply_text(update, "Usage: /promote <action_type>")
            return
        action_type = context.args[0]
        from core.action_engine import ACTION_TIERS

        if action_type not in ACTION_TIERS:
            await _reply_text(update, f"Unknown action type: {action_type}")
            return
        current = ACTION_TIERS[action_type]
        if current <= 0:
            await _reply_text(update, f"{action_type} is already Tier 0.")
            return
        ACTION_TIERS[action_type] = current - 1
        await _reply_text(update,
            f"Promoted {action_type}: Tier {current} → Tier {current - 1}."
        )

    async def _handle_approve_evolution(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message or not self._is_authorized(update.effective_user.id):
            return
        import json as _json

        pending_path = "/home/rohit/maez/evolution/pending_evolution.json"
        if os.path.exists(pending_path):
            with open(pending_path) as f:
                pending = _json.load(f)
            from skills.evolution_engine import deploy_improvement

            ok = deploy_improvement(pending["staging_file"], pending["target_file"])
            os.remove(pending_path)
            await _reply_text(update, "Evolution deployed." if ok else "Deployment failed.")
        else:
            await _reply_text(update, "No pending evolution.")

    async def _handle_reject_evolution(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message or not self._is_authorized(update.effective_user.id):
            return
        pending_path = "/home/rohit/maez/evolution/pending_evolution.json"
        if os.path.exists(pending_path):
            os.remove(pending_path)
            await _reply_text(update, "Evolution discarded.")
        else:
            await _reply_text(update, "No pending evolution.")

    async def _handle_evolution_log(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message or not self._is_authorized(update.effective_user.id):
            return
        log_path = "/home/rohit/maez/logs/evolution.log"
        try:
            with open(log_path) as f:
                lines = f.readlines()
            last = "".join(lines[-10:]) if lines else "Empty"
            await _reply_text(update, f"Evolution log:\n{last}")
        except Exception:
            await _reply_text(update, "No evolution log yet.")

    # ── Session 11o: dream-state command handlers ──────────────────
    async def _handle_dreams(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show pending dream insights (autonomous idle-time reflections)."""
        if not update.message or not self._is_authorized(update.effective_user.id):
            return
        if self.daemon is None or getattr(self.daemon, "dream", None) is None:
            await _reply_text(update, "Dream state not available.")
            return
        try:
            pending = self.daemon.dream.list_pending()
        except Exception as e:
            await _reply_text(update, f"list_pending failed: {e}")
            return
        if not pending:
            await _reply_text(update, "No pending dream insights.")
            return
        lines = [f"💭 {len(pending)} pending dream insight(s):\n"]
        for pid, created_iso, insight in pending[:10]:
            snippet = insight[:160].replace("\n", " ")
            lines.append(f"#{pid} ({created_iso})")
            lines.append(f"  {snippet}")
            # Backticks keep MarkdownV2 from italicizing `_dream_` so
            # the command arrives at the bot with underscores intact.
            lines.append(f"  `/apply_dream {pid}`  ·  `/reject_dream {pid}`")
            lines.append("")
        body = "\n".join(lines)
        await _reply_text(update, _audit_telegram_reply(body, surface="telegram/dreams"))

    async def _handle_apply_dream(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Apply a dream proposal: append to soul.md via action_engine."""
        if not update.message or not self._is_authorized(update.effective_user.id):
            return
        if not context.args:
            await _reply_text(update, "Usage: /apply_dream <id>")
            return
        try:
            prop_id = int(context.args[0])
        except ValueError:
            await _reply_text(update, "Invalid id — must be an integer.")
            return
        if self.daemon is None or getattr(self.daemon, "dream", None) is None:
            await _reply_text(update, "Dream state not available.")
            return
        try:
            ok, msg = self.daemon.dream.apply_proposal(prop_id)
        except Exception as e:
            await _reply_text(update, f"apply_proposal failed: {e}")
            return
        prefix = "✓" if ok else "✗"
        await _reply_text(update, f"{prefix} {msg}")

    async def _handle_reject_dream(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Reject a dream proposal (soul.md unchanged)."""
        if not update.message or not self._is_authorized(update.effective_user.id):
            return
        if not context.args:
            await _reply_text(update, "Usage: /reject_dream <id>")
            return
        try:
            prop_id = int(context.args[0])
        except ValueError:
            await _reply_text(update, "Invalid id — must be an integer.")
            return
        if self.daemon is None or getattr(self.daemon, "dream", None) is None:
            await _reply_text(update, "Dream state not available.")
            return
        try:
            ok, msg = self.daemon.dream.reject_proposal(prop_id)
        except Exception as e:
            await _reply_text(update, f"reject_proposal failed: {e}")
            return
        prefix = "✓" if ok else "✗"
        await _reply_text(update, f"{prefix} {msg}")

    # ── Session 11s: soul section-edit command handlers ───────────
    async def _handle_edit_proposals(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show pending soul.md section-edit proposals."""
        if not update.message or not self._is_authorized(update.effective_user.id):
            return
        if self.daemon is None or getattr(self.daemon, "dream", None) is None:
            await _reply_text(update, "Dream state not available.")
            return
        try:
            pending = self.daemon.dream.list_pending(proposal_type="section_replace")
        except Exception as e:
            await _reply_text(update, f"list_pending failed: {e}")
            return
        if not pending:
            await _reply_text(update, "No pending section-edit proposals.")
            return
        lines = [f"✏️ {len(pending)} pending section-edit proposal(s):\n"]
        for pid, created_iso, insight in pending[:10]:
            snippet = insight[:200].replace("\n", " ")
            prop = self.daemon.dream.get_proposal(pid) or {}
            target = prop.get("target_section") or "?"
            lines.append(f"#{pid} ({created_iso}) → ## {target}")
            lines.append(f"  {snippet}")
            lines.append(f"  /show_edit {pid}  ·  /apply_edit {pid}  ·  /reject_edit {pid}")
            lines.append("")
        body = "\n".join(lines)
        await _reply_text(update,
            _audit_telegram_reply(body, surface="telegram/edit_proposals")
        )

    async def _handle_show_edit(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show the unified diff for a pending section-edit proposal."""
        if not update.message or not self._is_authorized(update.effective_user.id):
            return
        if not context.args:
            await _reply_text(update, "Usage: /show_edit <id>")
            return
        try:
            prop_id = int(context.args[0])
        except ValueError:
            await _reply_text(update, "Invalid id — must be an integer.")
            return
        if self.daemon is None or getattr(self.daemon, "dream", None) is None:
            await _reply_text(update, "Dream state not available.")
            return
        prop = self.daemon.dream.get_proposal(prop_id)
        if prop is None:
            await _reply_text(update, f"Proposal #{prop_id} not found.")
            return
        if prop.get("proposal_type") != "section_replace":
            await _reply_text(update,
                f"#{prop_id} is type {prop.get('proposal_type')!r}, not section_replace."
            )
            return
        target = prop.get("target_section") or "?"
        diff = prop.get("unified_diff") or "(no diff stored)"
        insight = prop.get("insight") or ""
        # Telegram message cap is 4096 chars; keep diff preview safe.
        if len(diff) > 3200:
            diff = diff[:3200] + "\n... (diff truncated)"
        body = (
            f"✏️ Edit #{prop_id} → ## {target}\n"
            f"{insight}\n\n"
            f"```\n{diff}\n```\n\n"
            f"/apply_edit {prop_id}  ·  /reject_edit {prop_id}"
        )
        await _reply_text(update, _audit_telegram_reply(body, surface="telegram/show_edit"))

    async def _handle_apply_edit(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Apply a soul.md section-edit proposal."""
        if not update.message or not self._is_authorized(update.effective_user.id):
            return
        if not context.args:
            await _reply_text(update, "Usage: /apply_edit <id>")
            return
        try:
            prop_id = int(context.args[0])
        except ValueError:
            await _reply_text(update, "Invalid id — must be an integer.")
            return
        if self.daemon is None or getattr(self.daemon, "dream", None) is None:
            await _reply_text(update, "Dream state not available.")
            return
        try:
            ok, msg = self.daemon.dream.apply_section_edit_proposal(prop_id)
        except Exception as e:
            await _reply_text(update, f"apply_section_edit failed: {e}")
            return
        prefix = "✓" if ok else "✗"
        await _reply_text(update, f"{prefix} {msg}")

    async def _handle_reject_edit(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Reject a soul.md section-edit proposal (soul.md unchanged)."""
        if not update.message or not self._is_authorized(update.effective_user.id):
            return
        if not context.args:
            await _reply_text(update, "Usage: /reject_edit <id>")
            return
        try:
            prop_id = int(context.args[0])
        except ValueError:
            await _reply_text(update, "Invalid id — must be an integer.")
            return
        if self.daemon is None or getattr(self.daemon, "dream", None) is None:
            await _reply_text(update, "Dream state not available.")
            return
        try:
            ok, msg = self.daemon.dream.reject_proposal(prop_id)
        except Exception as e:
            await _reply_text(update, f"reject_proposal failed: {e}")
            return
        prefix = "✓" if ok else "✗"
        await _reply_text(update, f"{prefix} {msg}")

    # ── Session 11u: training proposal + adapter management commands ──
    async def _handle_train_proposals(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show pending training-run proposals."""
        if not update.message or not self._is_authorized(update.effective_user.id):
            return
        if self.daemon is None or getattr(self.daemon, "dream", None) is None:
            await _reply_text(update, "Dream state not available.")
            return
        try:
            pending = self.daemon.dream.list_pending(proposal_type="training_run")
        except Exception as e:
            await _reply_text(update, f"list_pending failed: {e}")
            return
        if not pending:
            await _reply_text(update, "No pending training proposals.")
            return
        lines = [f"🏋️ {len(pending)} pending training proposal(s):\n"]
        for pid, created_iso, insight in pending[:10]:
            snippet = insight[:200].replace("\n", " ")
            prop = self.daemon.dream.get_proposal(pid) or {}
            corpus = prop.get("target_section") or "?"
            lines.append(f"#{pid} ({created_iso})")
            lines.append(f"  {snippet}")
            lines.append(f"  Corpus: {corpus}")
            lines.append(f"  /show_train {pid}  ·  /approve_train {pid}  ·  /reject_train {pid}")
            lines.append("")
        body = "\n".join(lines)
        await _reply_text(update,
            _audit_telegram_reply(body, surface="telegram/train_proposals")
        )

    async def _handle_show_train(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show details of a training proposal."""
        if not update.message or not self._is_authorized(update.effective_user.id):
            return
        if not context.args:
            await _reply_text(update, "Usage: /show_train <id>")
            return
        try:
            prop_id = int(context.args[0])
        except ValueError:
            await _reply_text(update, "Invalid id.")
            return
        if self.daemon is None or getattr(self.daemon, "dream", None) is None:
            await _reply_text(update, "Dream state not available.")
            return
        prop = self.daemon.dream.get_proposal(prop_id)
        if prop is None:
            await _reply_text(update, f"Proposal #{prop_id} not found.")
            return
        if prop.get("proposal_type") != "training_run":
            await _reply_text(update,
                f"#{prop_id} is type {prop.get('proposal_type')!r}, not training_run."
            )
            return
        body = (
            f"🏋️ Training Proposal #{prop_id}\n\n"
            f"Rationale: {prop.get('insight', '?')}\n"
            f"Corpus: {prop.get('target_section', '?')}\n"
            f"Hyperparams: {prop.get('proposed_new_body', '{}')}\n"
            f"Status: {prop.get('status', '?')}\n\n"
            f"/approve_train {prop_id}  ·  /reject_train {prop_id}"
        )
        await _reply_text(update, _audit_telegram_reply(body, surface="telegram/show_train"))

    async def _handle_approve_train(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Mark a training proposal as approved."""
        if not update.message or not self._is_authorized(update.effective_user.id):
            return
        if not context.args:
            await _reply_text(update, "Usage: /approve_train <id>")
            return
        try:
            prop_id = int(context.args[0])
        except ValueError:
            await _reply_text(update, "Invalid id.")
            return
        if self.daemon is None or getattr(self.daemon, "dream", None) is None:
            await _reply_text(update, "Dream state not available.")
            return
        prop = self.daemon.dream.get_proposal(prop_id)
        if prop is None:
            await _reply_text(update, f"Proposal #{prop_id} not found.")
            return
        if prop.get("status") != "pending":
            await _reply_text(update, f"#{prop_id} already {prop.get('status')}.")
            return
        with self.daemon.dream._lock, self.daemon.dream._conn() as c:
            c.execute(
                "UPDATE dream_proposals SET status = 'applied', applied_at = ? WHERE id = ?",
                (time.time(), prop_id),
            )
            c.commit()
        await _reply_text(update,
            f"✓ Training #{prop_id} approved. Run the training pipeline manually to execute."
        )

    async def _handle_reject_train(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Reject a training proposal."""
        if not update.message or not self._is_authorized(update.effective_user.id):
            return
        if not context.args:
            await _reply_text(update, "Usage: /reject_train <id>")
            return
        try:
            prop_id = int(context.args[0])
        except ValueError:
            await _reply_text(update, "Invalid id.")
            return
        if self.daemon is None or getattr(self.daemon, "dream", None) is None:
            await _reply_text(update, "Dream state not available.")
            return
        try:
            ok, msg = self.daemon.dream.reject_proposal(prop_id)
        except Exception as e:
            await _reply_text(update, f"reject failed: {e}")
            return
        prefix = "✓" if ok else "✗"
        await _reply_text(update, f"{prefix} {msg}")

    async def _handle_adapter_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show current adapter info."""
        if not update.message or not self._is_authorized(update.effective_user.id):
            return
        import json as _json

        adapter_link = Path("/home/rohit/maez/training/runs/current")
        if not adapter_link.exists():
            await _reply_text(update, "No adapter promoted (no 'current' symlink).")
            return
        target = adapter_link.resolve()
        summary_path = target / "summary.json"
        if summary_path.exists():
            try:
                s = _json.loads(summary_path.read_text())
                body = (
                    f"📊 Current adapter: {target.name}\n"
                    f"  Pairs: {s.get('dataset_size', '?')}\n"
                    f"  Loss: {s.get('train_loss', '?')}\n"
                    f"  Rank: {s.get('lora_rank', '?')}\n"
                    f"  Time: {s.get('train_seconds', 0):.0f}s\n"
                    f"  Model: {s.get('model', '?')}"
                )
            except Exception:
                body = f"📊 Current adapter: {target.name} (summary unreadable)"
        else:
            body = f"📊 Current adapter: {target.name} (no summary.json)"
        await _reply_text(update, body)

    async def _handle_rollback_adapter(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Roll back to the previous adapter version."""
        if not update.message or not self._is_authorized(update.effective_user.id):
            return
        runs_dir = Path("/home/rohit/maez/training/runs")
        current_link = runs_dir / "current"
        if not current_link.is_symlink():
            await _reply_text(update, "No current adapter symlink found.")
            return
        current_target = current_link.resolve().name
        run_dirs = sorted(
            [
                d
                for d in runs_dir.iterdir()
                if d.is_dir()
                and d.name != "current"
                and d.name != "sanity"
                and d.name != "sanity-31b"
                and d.name != "sanity-26b"
                and (d / "adapter.gguf").exists()
            ],
            key=lambda d: d.name,
        )
        if len(run_dirs) < 2:
            await _reply_text(update,
                "Only one adapter version exists — nothing to roll back to."
            )
            return
        current_idx = next((i for i, d in enumerate(run_dirs) if d.name == current_target), -1)
        if current_idx <= 0:
            await _reply_text(update,
                f"Current adapter is already the oldest ({current_target})."
            )
            return
        prev = run_dirs[current_idx - 1]
        current_link.unlink()
        current_link.symlink_to(prev)
        await _reply_text(update,
            f"✓ Rolled back: {current_target} → {prev.name}\n"
            f"Restart llama-server to load: sudo systemctl restart llama-server.service"
        )

    async def _handle_proposals(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show last 5 proposal candidates."""
        if not update.message or not self._is_authorized(update.effective_user.id):
            return
        try:
            from skills.evolution_engine import _rail_conn
            import json as _json

            with _rail_conn() as conn:
                rows = conn.execute(
                    "SELECT id, state, weakness_description, cognition_evidence "
                    "FROM candidates ORDER BY id DESC LIMIT 5"
                ).fetchall()
            if not rows:
                await _reply_text(update, "No proposals yet.")
                return
            lines = ["Recent proposals:"]
            for r in rows:
                ev = {}
                try:
                    ev = _json.loads(r[3] or "{}")
                except Exception:
                    pass
                u = ev.get("usefulness", {}).get("overall", "?")
                emoji = {
                    "strong": "\u2705",
                    "acceptable": "\u26a0\ufe0f",
                    "weak": "\u274c",
                    "unknown": "\u26aa",
                }.get(u, "")
                w = (r[2] or "")[:60]
                lines.append(f"  [{r[0]}] {r[1]:11s} {emoji} {u:10s} {w}")
            body = "\n".join(lines)
            await _reply_text(update,
                _audit_telegram_reply(body, surface="telegram/proposals")
            )
        except Exception as e:
            await _reply_text(update, f"Error: {e}")

    async def _handle_show(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show candidate by id."""
        if not update.message or not self._is_authorized(update.effective_user.id):
            return
        if not context.args:
            await _reply_text(update, "Usage: /show <candidate_id>")
            return
        try:
            cid = int(context.args[0])
            from skills.evolution_engine import load_candidate_for_display

            disp = load_candidate_for_display(cid)
            if not disp:
                await _reply_text(update, f"Candidate {cid} not found")
                return
            u = disp["usefulness"]
            intent = disp.get("intent") or {}
            ev = disp.get("evidence") or {}
            lines = [
                f"Candidate {cid} \u2014 {disp['state']} \u2014 {u.get('overall')}",
                f"Weakness: {disp['weakness'][:200]}",
                f"Target:   {intent.get('target_name', '?')}",
                f"Before:   {intent.get('current_value')!r}",
                f"After:    {intent.get('proposed_value')!r}",
                f"Why:      {intent.get('rationale', '?')[:150]}",
                "",
                f"Failure mode:    {ev.get('dominant_failure_mode', '?')}",
                f"Addresses:       {u.get('addresses_failure_mode')}",
                f"Direction sane:  {u.get('direction_sane')}",
                f"Change minimal:  {u.get('change_minimal')}",
            ]
            body = "\n".join(lines)
            await _reply_text(update, _audit_telegram_reply(body, surface="telegram/show"))
        except Exception as e:
            await _reply_text(update, f"Error: {e}")

    async def _handle_apply(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Apply candidate by id."""
        if not update.message or not self._is_authorized(update.effective_user.id):
            return
        if not context.args:
            await _reply_text(update, "Usage: /apply <candidate_id>")
            return
        try:
            cid = int(context.args[0])
            from skills.evolution_engine import apply_candidate

            await _reply_text(update, f"Applying candidate {cid}...")
            result = apply_candidate(cid)
            if "error" in result:
                await _reply_text(update,
                    f"Apply failed: {result['error']}\n"
                    f"Rolled back: {result.get('rolled_back', False)} "
                    f"(layer={result.get('layer')})"
                )
            else:
                await _reply_text(update,
                    f"\u2705 Applied candidate {cid}\n"
                    f"State: {result.get('state')}\n"
                    f"Pre-score: {result.get('pre_score_avg')}"
                )
        except Exception as e:
            await _reply_text(update, f"Error: {e}")

    async def _handle_reject(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Reject candidate by id."""
        if not update.message or not self._is_authorized(update.effective_user.id):
            return
        if not context.args:
            await _reply_text(update, "Usage: /reject <candidate_id>")
            return
        try:
            cid = int(context.args[0])
            from skills.evolution_engine import (
                _rail_conn,
                _set_candidate_state,
                _log_evolution,
                V1_ALLOWED_TARGET,
            )

            with _rail_conn() as conn:
                row = conn.execute("SELECT state FROM candidates WHERE id=?", (cid,)).fetchone()
            if not row:
                await _reply_text(update, f"Candidate {cid} not found")
                return
            _set_candidate_state(cid, "rejected", rejection_reason="manual rejection via Telegram")
            _log_evolution(
                {
                    "action": "MANUAL_REJECTION",
                    "target": V1_ALLOWED_TARGET,
                    "result": f"candidate {cid}",
                }
            )
            await _reply_text(update, f"Candidate {cid} rejected (was: {row[0]})")
        except Exception as e:
            await _reply_text(update, f"Error: {e}")

    async def _handle_cog_analyze(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Compact cognition snapshot — overrides old self-analysis /analyze."""
        if not update.message or not self._is_authorized(update.effective_user.id):
            return
        try:
            from core.cognition_quality import (
                _recent_scores,
                _recent_topics,
                _recent_labels,
                get_behavior_policy,
            )
            import collections as _cc

            window = min(len(_recent_scores), 10)
            if window == 0:
                await _reply_text(update, "No cognition data yet.")
                return
            scores = _recent_scores[-window:]
            topics = _recent_topics[-window:]
            labels_window = _recent_labels[-window:]
            avg = sum(scores) / len(scores)
            tc = _cc.Counter(topics)
            dominant_topic, dom_count = tc.most_common(1)[0]
            flat = [l for ll in labels_window for l in ll]
            neg = {
                k: v
                for k, v in _cc.Counter(flat).items()
                if k in ("fixation", "vague", "baseline", "repetition")
            }
            failure = max(neg, key=neg.get) if neg else "none"
            streak = 0
            for t in reversed(topics):
                if t == dominant_topic:
                    streak += 1
                else:
                    break
            policy = get_behavior_policy()
            mode = policy.get("reflection_mode", "normal")
            lines = [
                "Cognition snapshot:",
                f"  Last 10 scores: {scores}",
                f"  Average:        {avg:.1f}/100",
                f"  Dominant topic: {dominant_topic} ({dom_count}/{window})",
                f"  Failure mode:   {failure}",
                f"  Fixation streak: {streak}",
                f"  Policy mode:    {mode}",
            ]
            await _reply_text(update, "\n".join(lines))
        except Exception as e:
            await _reply_text(update, f"Error: {e}")

    async def _handle_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Grouped command list."""
        if not update.message or not self._is_authorized(update.effective_user.id):
            return
        text = (
            "Maez commands:\n"
            "\n"
            "System:\n"
            "  /status    System and cognition summary\n"
            "  /git       Git repo state\n"
            "  /disk      Disk usage summary\n"
            "\n"
            "Cognition:\n"
            "  /analyze   Cognition snapshot (last 10 cycles)\n"
            "\n"
            "Evolution:\n"
            "  /proposals  Last 5 proposal candidates\n"
            "  /show <id>  Show candidate details\n"
            "  /apply <id> Apply candidate\n"
            "  /reject <id> Reject candidate\n"
            "\n"
            "Builder mode:\n"
            "  /builder_enter <reason>  Open a builder-mode session\n"
            "  /builder_exit            Close the active session\n"
            "\n"
            "Control:\n"
            "  /pending   Pending actions\n"
            "  /trust     Trust user\n"
            "  /promote   Promote action type\n"
            "  /help      This list"
        )
        await _reply_text(update, text)

    # -------------------------------------------------------------- #
    #  Builder-mode commands (A-core #3, Step 4)                      #
    # -------------------------------------------------------------- #
    #
    # Producer side of direct-edit session events via the Telegram
    # surface. Writes session_start / session_end events to
    # memory/audit_log.db via the existing AuditLog API — same writes
    # the CLI makes from scripts/maez_cli.py. The daemon's perception
    # reader from Step 3 (core/builder_mode_perception.py) picks up
    # these events surface-agnostic on its next reasoning cycle, so
    # no consumer code is added here.
    #
    # State file daemon/builder_mode_current.txt is shared with the
    # CLI so cross-surface operation works: enter via Telegram and
    # exit via CLI, or vice versa, and either surface finds the
    # active session. Format matches the CLI exactly:
    #     <session_id>
    #     reason=<text>
    #     opened_at=<unix ts>
    # Absence of the file means no active session.
    #
    # Scope discipline: these two handlers and the registration in
    # _run_bot / _configure_bot_commands are the only Telegram-side
    # touches for Step 4. No general-Telegram-routing changes. No
    # interactive confirmation layer (typing a slash command in a
    # chat is already a deliberate act; the CLI's typed-phrase
    # prompt exists to resist shell-level accidents that Telegram
    # doesn't have).

    def _builder_state_file(self) -> Path:
        """Path to the shared current-session state file."""
        return Path("/home/rohit/maez/daemon/builder_mode_current.txt")

    def _builder_read_state(self) -> Optional[dict]:
        """Read the shared state file (same format as scripts/maez_cli.py
        uses). Returns None if no active session."""
        state_file = self._builder_state_file()
        if not state_file.exists():
            return None
        try:
            content = state_file.read_text().strip()
        except OSError:
            return None
        if not content:
            return None
        lines = content.splitlines()
        session_id = lines[0].strip()
        meta: dict = {"session_id": session_id}
        for line in lines[1:]:
            if "=" in line:
                k, v = line.split("=", 1)
                meta[k.strip()] = v.strip()
        return meta

    def _builder_write_state(self, session_id: str, reason: str, opened_at: float) -> None:
        """Write the shared state file. Matches the CLI format exactly."""
        state_file = self._builder_state_file()
        state_file.parent.mkdir(parents=True, exist_ok=True)
        content = f"{session_id}\nreason={reason}\nopened_at={opened_at}\n"
        state_file.write_text(content)

    def _builder_clear_state(self) -> None:
        """Remove the shared state file on successful exit."""
        try:
            self._builder_state_file().unlink()
        except FileNotFoundError:
            pass

    async def _handle_builder_enter(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Enter builder mode from Telegram. Usage: /builder_enter <reason>"""
        if not update.message or not self._is_authorized(update.effective_user.id):
            return

        # Reason is required, taken from everything after the command
        reason_parts = context.args or []
        reason = " ".join(reason_parts).strip()
        if not reason:
            await _reply_text(update,
                "Usage: /builder_enter <reason>\n\nExample: /builder_enter rewriting sudo handling"
            )
            return

        # Refuse double-entry — if a session is already active, show it
        # and tell the user to exit first. Symmetric with the CLI behavior.
        existing = self._builder_read_state()
        if existing is not None:
            lines = [
                "A builder-mode session is already active:",
                f"  session: {existing['session_id']}",
            ]
            if "reason" in existing:
                lines.append(f"  reason: {existing['reason']}")
            if "opened_at" in existing:
                try:
                    opened_ts = float(existing["opened_at"])
                    age = time.time() - opened_ts
                    lines.append(f"  age:    {int(age // 60)}m {int(age % 60)}s")
                except ValueError:
                    pass
            lines.append("")
            lines.append("Run /builder_exit first, then try again.")
            await _reply_text(update, "\n".join(lines))
            return

        # Open the session via the existing AuditLog API
        try:
            from core.audit_log import AuditLog, DIRECT_EDIT_SOURCE_TELEGRAM

            audit = AuditLog()
            session_id = audit.start_direct_edit_session(
                reason=reason,
                source=DIRECT_EDIT_SOURCE_TELEGRAM,
            )
        except Exception as e:
            logger.warning("builder_enter failed to open session: %s", e)
            await _reply_text(update, f"Error opening builder-mode session: {e}")
            return

        opened_at = time.time()
        self._builder_write_state(session_id, reason, opened_at)

        await _reply_text(update,
            "Builder mode active.\n"
            f"Session: {session_id}\n"
            f"Reason: {reason}\n"
            "\n"
            "Direct edits will be logged to Maez's audit memory until\n"
            "you run /builder_exit. Maez will see the event in its next\n"
            "reasoning cycle."
        )

    async def _handle_builder_exit(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Exit builder mode from Telegram. Usage: /builder_exit"""
        if not update.message or not self._is_authorized(update.effective_user.id):
            return

        state = self._builder_read_state()
        if state is None:
            await _reply_text(update,
                "No active builder-mode session. Run /builder_enter <reason> to start one."
            )
            return

        session_id = state["session_id"]

        # Compute duration if opened_at is present
        duration_str = None
        if "opened_at" in state:
            try:
                opened_ts = float(state["opened_at"])
                dur = time.time() - opened_ts
                hours = int(dur // 3600)
                minutes = int((dur % 3600) // 60)
                seconds = int(dur % 60)
                duration_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            except ValueError:
                pass

        # A-core #3 Step 5: capture any git diff on watched paths
        # before closing the session, so Maez gets a final direct_edit
        # event recording the state of the working directory at
        # session end. Mirrors the CLI's cmd_exit behavior for
        # cross-surface symmetry.
        diff_logged = False
        try:
            from core.audit_log import AuditLog
            from core.builder_mode_capture import capture_session_end_diff

            audit = AuditLog()
            repo_root = Path("/home/rohit/maez")
            diff_logged = capture_session_end_diff(
                repo_root=repo_root,
                session_id=session_id,
                audit_log=audit,
                reason="session end diff capture (telegram)",
            )
            audit.end_direct_edit_session(session_id=session_id)
        except Exception as e:
            logger.warning("builder_exit failed to close session: %s", e)
            await _reply_text(update, f"Error closing builder-mode session: {e}")
            return

        self._builder_clear_state()

        lines = [
            "Builder mode inactive.",
            f"Session: {session_id} closed.",
        ]
        if duration_str:
            lines.append(f"Duration: {duration_str}")
        if diff_logged:
            lines.append("Final diff captured as a direct_edit event.")
        await _reply_text(update, "\n".join(lines))

    async def _configure_bot_commands(self):
        """Register bot commands and menu button for the private chat."""
        try:
            commands = [
                BotCommand("status", "System and cognition summary"),
                BotCommand("git", "Git repo state"),
                BotCommand("disk", "Disk usage summary"),
                BotCommand("analyze", "Cognition snapshot"),
                BotCommand("proposals", "Last 5 proposal candidates"),
                BotCommand("show", "Show candidate by id"),
                BotCommand("apply", "Apply candidate by id"),
                BotCommand("reject", "Reject candidate by id"),
                BotCommand("dreams", "Pending dream insights"),
                BotCommand("apply_dream", "Apply dream insight by id"),
                BotCommand("reject_dream", "Reject dream insight by id"),
                BotCommand("edit_proposals", "Pending soul section edits"),
                BotCommand("show_edit", "Show soul edit diff by id"),
                BotCommand("apply_edit", "Apply soul section edit by id"),
                BotCommand("reject_edit", "Reject soul section edit by id"),
                BotCommand("train_proposals", "Pending training proposals"),
                BotCommand("approve_train", "Approve training proposal"),
                BotCommand("reject_train", "Reject training proposal"),
                BotCommand("adapter_status", "Current adapter info"),
                BotCommand("rollback_adapter", "Roll back to previous adapter"),
                BotCommand("pending", "Pending actions"),
                BotCommand("trust", "Trust user"),
                BotCommand("promote", "Promote action type"),
                BotCommand("builder_enter", "Enter builder mode (reason required)"),
                BotCommand("builder_exit", "Exit the active builder-mode session"),
                BotCommand("help", "Grouped command list"),
            ]
            await self._app.bot.set_my_commands(
                commands,
                scope=BotCommandScopeChat(chat_id=self.authorized_user),
            )
            await self._app.bot.set_chat_menu_button(
                chat_id=self.authorized_user,
                menu_button=MenuButtonCommands(),
            )
            logger.info("Telegram private bot commands registered (%d)", len(commands))
        except Exception as e:
            logger.error("Failed to register bot commands: %s", e)

    def _run_bot(self):
        """Run the Telegram bot in its own event loop (called from thread)."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        self._app = Application.builder().token(self.token).build()
        self._app.add_handler(CommandHandler("status", self._handle_status))
        self._app.add_handler(CommandHandler("cancel", self._handle_cancel))
        self._app.add_handler(CommandHandler("approve", self._handle_approve))
        self._app.add_handler(CommandHandler("pending", self._handle_pending))
        self._app.add_handler(CommandHandler("git", self._handle_git))
        self._app.add_handler(CommandHandler("disk", self._handle_disk))
        self._app.add_handler(CommandHandler("analyze", self._handle_cog_analyze))
        self._app.add_handler(CommandHandler("approve_cleanup", self._handle_approve_cleanup))
        self._app.add_handler(CommandHandler("promote", self._handle_promote))
        self._app.add_handler(CommandHandler("approve_evolution", self._handle_approve_evolution))
        self._app.add_handler(CommandHandler("login", self._handle_login))
        self._app.add_handler(CommandHandler("trust", self._handle_trust))
        self._app.add_handler(CommandHandler("reject_evolution", self._handle_reject_evolution))
        self._app.add_handler(CommandHandler("evolution_log", self._handle_evolution_log))
        # New evolution-rail handlers
        self._app.add_handler(CommandHandler("proposals", self._handle_proposals))
        self._app.add_handler(CommandHandler("show", self._handle_show))
        self._app.add_handler(CommandHandler("apply", self._handle_apply))
        self._app.add_handler(CommandHandler("reject", self._handle_reject))
        # Session 11o: dream-state commands
        self._app.add_handler(CommandHandler("dreams", self._handle_dreams))
        self._app.add_handler(CommandHandler("apply_dream", self._handle_apply_dream))
        self._app.add_handler(CommandHandler("reject_dream", self._handle_reject_dream))
        # Session 11s: soul section-edit commands
        self._app.add_handler(CommandHandler("edit_proposals", self._handle_edit_proposals))
        self._app.add_handler(CommandHandler("show_edit", self._handle_show_edit))
        self._app.add_handler(CommandHandler("apply_edit", self._handle_apply_edit))
        self._app.add_handler(CommandHandler("reject_edit", self._handle_reject_edit))
        # Session 11u: training proposal + adapter management commands
        self._app.add_handler(CommandHandler("train_proposals", self._handle_train_proposals))
        self._app.add_handler(CommandHandler("show_train", self._handle_show_train))
        self._app.add_handler(CommandHandler("approve_train", self._handle_approve_train))
        self._app.add_handler(CommandHandler("reject_train", self._handle_reject_train))
        self._app.add_handler(CommandHandler("adapter_status", self._handle_adapter_status))
        self._app.add_handler(CommandHandler("rollback_adapter", self._handle_rollback_adapter))
        # A-core #3 Step 4: builder-mode commands
        self._app.add_handler(CommandHandler("builder_enter", self._handle_builder_enter))
        self._app.add_handler(CommandHandler("builder_exit", self._handle_builder_exit))
        self._app.add_handler(CommandHandler("help", self._handle_help))
        self._app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message))

        # Default behavior (2026-04-20 full migration): the vendored
        # surface adapter in `skills/surface/` owns inbound Telegram
        # polling. The legacy TelegramVoice keeps `self._loop` alive
        # only so `send_message()` and `_send_card_message()` callers
        # (daemon-side proactive messages, card rendering) continue
        # to work — those create fresh `Bot` instances per call and
        # don't need the Application to be started.
        #
        # `MAEZ_DISABLE_SURFACE_V2=1` is the kill switch: setting it
        # reverts to the pre-migration behavior where this class
        # owns polling and handles all inbound.
        import os as _os

        _v2_disabled = _os.environ.get("MAEZ_DISABLE_SURFACE_V2") == "1"

        if not _v2_disabled:
            logger.info(
                "legacy Telegram Application NOT started (v2 surface is "
                "authoritative); self._loop alive for send_message()/cards"
            )
            self._loop.run_forever()
            return

        logger.warning("MAEZ_DISABLE_SURFACE_V2=1 — falling back to legacy polling")
        self._loop.run_until_complete(self._app.initialize())
        self._loop.run_until_complete(self._app.start())
        # Register bot command menu before polling starts
        self._loop.run_until_complete(self._configure_bot_commands())
        self._loop.run_until_complete(self._app.updater.start_polling(drop_pending_updates=True))
        self._loop.run_forever()

    def start(self):
        """Start the Telegram bot in a background thread."""
        if not self.enabled:
            logger.warning("Telegram integration disabled (missing credentials)")
            return

        self._thread = threading.Thread(target=self._run_bot, daemon=True, name="telegram-bot")
        self._thread.start()
        logger.info("Telegram bot thread started (authorized user: %d)", self.authorized_user)

    def stop(self, join_timeout: float = 10.0):
        """Stop the Telegram bot and let its thread unwind."""
        if not self._loop:
            return

        loop = self._loop
        app = self._app

        async def _shutdown():
            if app is None:
                return
            try:
                if getattr(app, "updater", None) is not None:
                    await app.updater.stop()
            except Exception as e:
                logger.debug("Telegram updater stop failed: %s", e)
            try:
                await app.stop()
            except Exception as e:
                logger.debug("Telegram app stop failed: %s", e)
            try:
                await app.shutdown()
            except Exception as e:
                logger.debug("Telegram app shutdown failed: %s", e)

        try:
            future = asyncio.run_coroutine_threadsafe(_shutdown(), loop)
            future.result(timeout=join_timeout)
        except Exception as e:
            logger.debug("Telegram stop coordination failed: %s", e)

        try:
            loop.call_soon_threadsafe(loop.stop)
        except Exception:
            pass

        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=join_timeout)

    def send_envelope(self, envelope: TelegramEgressEnvelope):
        """Send a provenance-bearing envelope to the owner via Telegram."""
        if not self.enabled or not self._loop:
            return

        text = ""
        if envelope.content is not None:
            text = envelope.content.text
        elif envelope.caption is not None:
            text = envelope.caption.text
        parts = split_long_message(text)
        if len(parts) > 1:
            logger.info("Telegram message split into %d parts", len(parts))

        async def _send_all():
            import asyncio as _a

            bot = Bot(token=self.token)
            cursor = 0
            for i, part in enumerate(parts):
                part_envelope = envelope
                if not part_envelope.chat_id:
                    part_envelope = replace(
                        part_envelope,
                        chat_id=str(self.authorized_user),
                    )
                if envelope.content is not None:
                    chunk_content, cursor = _slice_provenanced_text(
                        envelope.content,
                        part,
                        cursor,
                    )
                    part_envelope = replace(part_envelope, content=chunk_content)
                await _bot_send_message(
                    bot,
                    chat_id=self.authorized_user,
                    text=part,
                    envelope=part_envelope,
                )
                if i < len(parts) - 1:
                    await _a.sleep(0.5)

        future = asyncio.run_coroutine_threadsafe(_send_all(), self._loop)
        try:
            future.result(timeout=30)
            logger.info("Telegram sent envelope: %s (full %d chars)", text[:80], len(text))
        except Exception as e:
            logger.error("Telegram send failed: %s", e)

    def send_message(self, text: str):
        """Retired raw-string compatibility surface.

        Producer-threaded Telegram sends must classify content at birth and
        call ``send_envelope(...)`` instead of asking this wrapper to guess.
        """
        raise RuntimeError("raw TelegramVoice.send_message retired; use send_envelope")
