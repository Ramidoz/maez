"""
Maez Telegram Voice — Bidirectional Telegram integration.
Sends proactive observations and receives commands from the owner.
"""

import asyncio
import logging
import os
import threading
import time
from pathlib import Path

import ollama
from telegram import Bot, Update, BotCommand, BotCommandScopeChat, MenuButtonCommands
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import sys
sys.path.insert(0, str(Path("/home/rohit/maez")))
from core.perception import snapshot as perception_snapshot, format_snapshot
from memory.memory_manager import MemoryManager
from skills.web_search import (
    search as web_search, format_for_context as web_format,
    needs_web_search, search_rss, is_news_query,
)

logger = logging.getLogger("maez")


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
    return (f"[CIRCADIAN]\n"
            f"  Time: {phase} ({hour:02d}:00)\n"
            f"  Expected energy: {energy}\n"
            f"  Suggested tone: {tone}")


def _get_public_context_for_telegram() -> str:
    """Fetch recent public bot conversations for Telegram prompt context."""
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
        cutoff_iso = _dt.fromtimestamp(_time.time() - 86400, tz=_tz.utc).strftime('%Y-%m-%dT%H:%M:%S')
        results = col.get(include=["documents", "metadatas"])
        filtered = [
            (doc, meta) for doc, meta in zip(results["documents"], results["metadatas"])
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

SOUL_PATH = Path("/home/rohit/maez/config/soul.md")
MODEL = "gemma4:26b"

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
        for sep in ['. ', '? ', '! ']:
            idx = chunk.rfind(sep)
            if idx > max_length // 2:
                split_at = max(split_at, idx + len(sep))
        if split_at < 0:
            # Fall back to newline boundary
            idx = chunk.rfind('\n')
            if idx > max_length // 2:
                split_at = idx + 1
        if split_at < 0:
            # Fall back to space boundary
            idx = chunk.rfind(' ')
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

# --- Natural language intent detection ---
MACHINE_INTENTS = {
    'status':       ['how is everything', 'system status', "what's running", 'all good', 'services ok'],
    'logs':         ['show logs', 'recent logs', 'any errors', 'what happened', 'check logs'],
    'restart_maez': ['restart yourself', 'restart maez', 'reboot yourself'],
    'claude_status':['claude code', "what's claude doing", 'is claude running', 'build status'],
    'reboot':       ['reboot the machine', 'restart the computer', 'reboot system'],
    'disk':         ['disk space', 'storage', 'partition', 'how much space'],
    'memory':       ['how many memories', 'memory count', 'what do you remember'],
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
    r'^\s*('
    r'hi|hello|hey|yo|sup|good (?:morning|afternoon|evening|night)|'
    r'thanks?|thank\s+you|thx|ty|cheers|'
    r'ok(?:ay)?|alright|got\s+it|sure|cool|nice|nope?|yes|yeah|yep|yup|'
    r'lol|haha|hmm+|hm+|wow|oh|ah|uh|huh|'
    r'love\s+(?:you|u|you\s+maez|u\s+maez)|miss\s+you|gn|gm|brb|bye|goodbye|see\s+you|later|'
    r'maez|hi\s+maez|hey\s+maez|good\s+(?:job|work|night)\s+maez'
    r')[\s.!?,]*$',
    _jarvis_re.IGNORECASE,
)

def _should_run_jarvis_loop(text: str) -> bool:
    """True if the message could plausibly need tools. Inverts the old
    keyword gate — bias toward running the loop, only skip on messages
    that are obviously pure conversation."""
    if not text:
        return False
    t = text.strip()
    if len(t) < 3:
        return False
    if _CONVERSATIONAL_RE.match(t):
        return False
    return True


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
    m = _re.search(r'TOOL_CALL\s*[:=]?\s*(\{.*\})', s, _re.DOTALL)
    if m:
        blob = _extract_balanced_json(m.group(1))
        if blob:
            try:
                obj = _json.loads(blob)
                if isinstance(obj, dict) and obj.get("action"):
                    return {"action": obj["action"],
                            "params": obj.get("params") or obj.get("arguments") or {}}
            except Exception:
                pass

    # Form 2: <|tool_call>call:[maez.]NAME{...}<tool_call|>  (gemma native)
    # Also tolerates <tool_call>...</tool_call>, [TOOL_CALL]...[/TOOL_CALL], etc.
    m = _re.search(
        r'(?:<\|?tool_call\|?>|<tool_call>|\[tool_call\]|\[TOOL_CALL\])\s*'
        r'(?:call\s*:\s*)?'
        r'(?:[a-zA-Z_][\w]*\.)?'         # optional namespace like "maez."
        r'([a-zA-Z_]\w*)'                # function name
        r'\s*(\{.*?\})'                  # params
        r'\s*(?:<\|?/?tool_call\|?>|</tool_call>|\[/tool_call\]|\[/TOOL_CALL\])?',
        s, _re.DOTALL,
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
    m = _re.search(r'\b([a-z_][a-z0-9_]+)\s*\(\s*(\{.*?\})\s*\)', s, _re.DOTALL)
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
        brace = s.rfind('{', 0, idx)
        if brace >= 0:
            blob = _extract_balanced_json(s[brace:])
            if blob:
                try:
                    obj = _json.loads(blob)
                    if isinstance(obj, dict) and obj.get("action"):
                        return {"action": obj["action"],
                                "params": obj.get("params") or obj.get("arguments") or {}}
                except Exception:
                    pass

    return None


def _extract_balanced_json(s: str) -> str | None:
    """Return the substring of s starting at the first '{' that contains a
    balanced JSON object. None if no balance found."""
    if not s:
        return None
    start = s.find('{')
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
        if c == '\\' and in_str:
            esc = True
            continue
        if c == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return s[start:i + 1]
    return None

_TOOL_MANIFEST = """\
TOOLS YOU CAN USE (your body, your hands — these run on the owner's machine):

1. run_shell       {"cmd":"dpkg -l openrgb","reason":"check if installed"}
   Run ANY shell command via bash -c. 120s timeout. Full stdout/stderr.
   This is your hands. Pipes, redirects, sudo, chains with && — all fine.
   Examples:
     {"cmd":"sudo apt-get install -y openrgb","reason":"the owner asked"}
     {"cmd":"sudo add-apt-repository -y ppa:openrgb/stable && sudo apt-get update && sudo apt-get install -y openrgb","reason":"install from PPA"}
     {"cmd":"nvidia-smi","reason":"check GPU"}
     {"cmd":"git status","reason":"see what's uncommitted"}
     {"cmd":"systemctl is-active nginx","reason":"check service"}
2. write_any_file  {"path":"/home/rohit/notes.txt","content":"...","reason":"..."}
   Write or replace any file under /home/rohit. Auto-backs up existing files.
3. read_file       {"path":"/home/rohit/maez/config/soul.md"}
   Read any file under /home/rohit. Returns up to 5KB.
4. search_files    {"pattern":"*.py","directory":"/home/rohit/maez"}
   find -name pattern, max depth 5.
5. web_search      {"query":"openrgb cpu lighting linux"}
   Real DuckDuckGo search. Use this whenever you need facts you don't have.

COVENANT (these refuse themselves — don't try):
- No killing/stopping llama-server or maez.service (your own brain and heart).
- No modifying maez_daemon.py, action_engine.py, evolution_engine.py,
  the memory database, or HARD CONSTRAINTS in soul.md.
Everything else is fair game. You have full control.

To use a tool, emit ONE LINE exactly in this format and nothing else on that line:
TOOL_CALL: {"action":"<name>","params":{...}}

You will then see:
RESULT: <output>

You may call another tool, or write exactly:
DONE
when you have enough information to answer the owner.

Rules:
- If the question is conversation/opinion/recall and needs no real data → write DONE immediately.
- Never speculate or fabricate. If you don't know, USE web_search or run_shell.
- Prefer run_shell for any real system action. It's the most capable tool.
- the owner asking you to do something IS authorization. Don't ask "should I?" — do it, then tell him what you did.
- If a command fails, try to fix it and retry. Pivot if the first approach doesn't work.
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

        def _send(chat_id, text, reply_to=None):
            return self._send_card_message(chat_id, text, reply_to=reply_to)

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
        return self._decision_pipeline

    def _send_card_message(self, chat_id, text: str, reply_to=None) -> str | None:
        """Send a Telegram message and return the posted message_id.

        Unlike send_message(), this returns the message_id so the
        pending-cards store can record it for future reaction/reply
        lookups. Safe to call from any thread via run_coroutine_threadsafe.
        """
        if not self.enabled or not self._loop:
            return None
        target_chat = int(chat_id) if chat_id else self.authorized_user

        async def _send():
            bot = Bot(token=self.token)
            kwargs: dict = {"chat_id": target_chat, "text": text}
            if reply_to is not None:
                try:
                    kwargs["reply_to_message_id"] = int(reply_to)
                except (TypeError, ValueError):
                    pass
            msg = await bot.send_message(**kwargs)
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

        # Zero-latency short-circuit: if no open cards, skip everything.
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
                None,
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

        # Pipeline already sent the resolution notice via the renderer.
        # Nothing else to do here; the normal chat flow is short-circuited.
        logger.info(
            "card reply handled: status=%s card=%s",
            result.status.value if result.status else "?",
            result.card.request_id if result.card else "?",
        )
        return True

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

    def _is_authorized(self, user_id: int) -> bool:
        return user_id == self.authorized_user

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

    _NL_APPROVE_PATTERNS = [
        r'^(yes|yep|yeah|yup|yuh|ok|okay|sure|alright|alright then|sounds good)[\s!.?]*$',
        r'^(approve[d]?|approved|do it|go ahead|ship it|try it|let it try|let it run|let\'?s do it|let\'?s try it)[\s!.?]*$',
        r'^(absolutely|please do|go for it|green light)[\s!.?]*$',
        r'^(approve|yes|yeah|do)\s+#?(\d+)[\s!.?]*$',
        r'^yes\s+to\s+#?(\d+)[\s!.?]*$',
    ]

    _NL_REJECT_PATTERNS = [
        r'^(no|nope|nah|naw|nuh)[\s!.?]*$',
        r'^(reject[ed]?|decline[d]?|skip|cancel|pass)[\s!.?]*$',
        r'^(don\'?t|do not)\s*(do it|apply|bother)?[\s!.?]*$',
        r'^not\s+(that|this)(\s+one)?[\s!.?]*$',
        r'^not\s+(now|it|right now)[\s!.?]*$',
        r'^(never ?mind|forget it|leave it)[\s!.?]*$',
        r'^(reject|no|nope|skip|cancel)\s+#?(\d+)[\s!.?]*$',
        r'^no\s+to\s+#?(\d+)[\s!.?]*$',
    ]

    _NL_SHOW_PATTERN = r'^(tell me more|show me|details?|more info|explain|what(\'?s)? (in|that)|show)\s*(about\s+)?#?(\d+)?[\s!.?]*$'

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
            return [{'id': r[0], 'target_file': r[1], 'weakness': r[2],
                     'created_at': r[3]} for r in rows]
        except Exception as e:
            logger.debug("pending candidates query failed: %s", e)
            return []

    def _detect_proposal_intent(self, text: str) -> tuple:
        """Match approve/reject/show intent. Returns (action, candidate_id|None).
        action is one of: 'approve', 'reject', 'show', or None.
        candidate_id is the explicit id from the message if present, else None."""
        import re as _re
        stripped = (text or '').strip().lower()
        if not stripped or len(stripped) > 80:
            return None, None

        for pat in self._NL_APPROVE_PATTERNS:
            m = _re.match(pat, stripped)
            if m:
                groups = [g for g in m.groups() if g and g.isdigit()]
                cid = int(groups[0]) if groups else None
                return 'approve', cid

        for pat in self._NL_REJECT_PATTERNS:
            m = _re.match(pat, stripped)
            if m:
                groups = [g for g in m.groups() if g and g.isdigit()]
                cid = int(groups[0]) if groups else None
                return 'reject', cid

        m = _re.match(self._NL_SHOW_PATTERN, stripped)
        if m:
            groups = [g for g in m.groups() if g and g.isdigit()]
            cid = int(groups[0]) if groups else None
            return 'show', cid

        return None, None

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

        # Resolve which candidate the message refers to
        target_id = explicit_id
        if target_id is None:
            if len(pending) == 1:
                target_id = pending[0]['id']
            elif len(pending) > 1:
                lines = [
                    f"I have {len(pending)} proposals pending — which one do you mean?",
                    "",
                ]
                for p in pending[:5]:
                    lines.append(f"  #{p['id']}: {(p['weakness'] or '')[:80]}")
                lines.append("")
                lines.append("Reply with the number — e.g. \"yes to 22\" or \"reject #23\".")
                await update.message.reply_text("\n".join(lines))
                return True

        # Verify the candidate exists and is still pending
        if not any(p['id'] == target_id for p in pending) and target_id is not None:
            await update.message.reply_text(
                f"I don't see a pending proposal #{target_id}. It may have "
                f"already been applied or rejected. Say \"status\" to see "
                f"what's currently pending."
            )
            return True

        # Execute the action
        try:
            if action == 'approve':
                from skills.evolution_engine import apply_candidate
                await update.message.reply_text(f"OK, applying proposal #{target_id}…")
                result = apply_candidate(target_id)
                if 'error' in result:
                    await update.message.reply_text(
                        f"Something went wrong applying #{target_id}: "
                        f"{result['error']}\n"
                        f"{'Rolled back. ' if result.get('rolled_back') else ''}"
                        f"Let me know if you want me to try a different proposal."
                    )
                else:
                    await update.message.reply_text(
                        f"Done. Proposal #{target_id} is live now. I'll watch "
                        f"the next 20-30 cycles for any regression and roll "
                        f"back automatically if my score drops."
                    )
                return True

            if action == 'reject':
                from skills.evolution_engine import (
                    _set_candidate_state, _log_evolution, V1_ALLOWED_TARGET,
                )
                _set_candidate_state(
                    target_id, 'rejected',
                    rejection_reason='manual rejection via natural-language chat',
                )
                _log_evolution({
                    'action': 'MANUAL_REJECTION', 'target': V1_ALLOWED_TARGET,
                    'result': f'candidate {target_id}', 'detail': 'natural_language',
                })
                await update.message.reply_text(
                    f"Got it — proposal #{target_id} is rejected. I'll leave "
                    f"that one alone and keep an eye out for other things "
                    f"I could try."
                )
                return True

            if action == 'show':
                from skills.evolution_engine import load_candidate_for_display
                disp = load_candidate_for_display(target_id)
                if not disp:
                    await update.message.reply_text(f"I can't find proposal #{target_id}.")
                    return True
                i = disp.get('intent') or {}
                u = disp.get('usefulness') or {}
                lines = [
                    f"\U0001f331 Proposal #{target_id}",
                    "",
                    f"What I want to do: {i.get('human_rationale', '(no plain-English description)')}",
                    "",
                    f"Technical details:",
                    f"  File: {disp.get('target_file', '?')}",
                    f"  Target: {i.get('target_name', '?')}",
                    f"  Before: {i.get('current_value')!r}",
                    f"  After:  {i.get('proposed_value')!r}",
                    f"  Technical rationale: {i.get('rationale', '')[:200]}",
                    "",
                    f"My confidence: {u.get('overall', 'unknown')}",
                    f"  ({u.get('reasoning', '')[:200]})",
                    "",
                    f"Reply \"yes\" to apply, \"no\" to reject.",
                ]
                await update.message.reply_text("\n".join(lines))
                return True
        except Exception as e:
            logger.error("Natural-language proposal action failed: %s", e)
            await update.message.reply_text(
                f"Something went wrong while handling that: {e}"
            )
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
        r'^\s*(search|google)\s+(the\s+(web|internet|net)\s+for\s+|for\s+|on\s+|)(.{2,200}?)[\s!.?]*$',
        r'^\s*look\s+up\s+(.{2,200}?)[\s!.?]*$',
        r'^\s*(find|check)\s+(online|on\s+the\s+internet|on\s+the\s+web)\s+(for\s+|)(.{2,200}?)[\s!.?]*$',
        r'^\s*check\s+(online|the\s+internet|the\s+web)\s+(for\s+|)(.{2,200}?)[\s!.?]*$',
        r'^\s*go\s+(search|look\s+up)\s+(.{2,200}?)[\s!.?]*$',
        r'^\s*can\s+you\s+(search|look\s+up|google|find\s+out\s+about)\s+(.{2,200}?)[\s!.?]*$',
        r'^\s*please\s+(search|look\s+up|google)\s+(for\s+)?(.{2,200}?)[\s!.?]*$',
    ]

    # Extract the QUERY from whichever group captured the free text
    def _extract_search_query(self, text: str) -> str | None:
        import re as _re
        for pat in self._WEB_SEARCH_IMPERATIVE:
            m = _re.match(pat, text, _re.IGNORECASE)
            if m:
                # pick the longest captured group that looks like a query
                candidates = [g for g in m.groups()
                              if g and len(g.strip()) >= 2 and
                              g.strip().lower() not in (
                                  'the', 'a', 'for', 'on', 'web', 'internet',
                                  'net', 'online', 'the web', 'the internet',
                                  'the net',
                              )]
                if candidates:
                    return max(candidates, key=len).strip().rstrip('?.!')
        return None

    async def _try_web_search_intent(self, update, text: str) -> bool:
        """Handle explicit search commands. Returns True if handled."""
        if not text or len(text) > 300:
            return False

        query = self._extract_search_query(text)
        if not query:
            return False

        try:
            from skills.web_search import search as _web_search
            await update.message.reply_text(f"Searching the web for: {query}…")
            result = _web_search(query, max_results=5)
        except Exception as e:
            logger.error("web_search call failed: %s", e)
            await update.message.reply_text(
                f"I tried to search the web for \"{query}\" but the search "
                f"skill failed ({e}). I'm not going to make up an answer."
            )
            return True

        if not result.get('success') or not result.get('results'):
            await update.message.reply_text(
                f"I searched the web for \"{query}\" but didn't get any "
                f"useful results back — either nothing matched, or the "
                f"search service wasn't reachable. I'm not going to "
                f"fabricate anything. Want to try a different phrasing?"
            )
            return True

        # Compose a compact human-readable reply
        lines = [f"Here's what I found for \"{query}\":", ""]
        for i, r in enumerate(result['results'][:5], 1):
            title = (r.get('title') or '').strip()
            url = (r.get('url') or '').strip()
            snippet = (r.get('snippet') or '').strip()
            # Clean up whitespace artifacts from the HTML regex fallback
            import re as _re
            snippet = _re.sub(r'\s+', ' ', snippet)[:220]
            title = _re.sub(r'\s+', ' ', title)[:90]
            url = _re.sub(r'\s+', '', url)[:120]
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
        await update.message.reply_text(reply)
        return True

    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming messages from Telegram."""
        import re as _re
        import time as _time

        if not update.message or not update.effective_user:
            return

        user_id = update.effective_user.id
        if not self._is_authorized(user_id):
            logger.warning("Unauthorized Telegram message from user %d", user_id)
            return

        user_text = update.message.text
        if not user_text:
            return

        # Interrupt detection — if currently generating, queue and return
        if self._generating:
            if self._interrupt_queue:
                self._interrupt_queue.put_nowait(user_text)
            logger.info("Telegram interrupt queued: %s", user_text[:60])
            return

        self._generating = True
        logger.info("Telegram message from the owner: %s", user_text[:100])

        # Initialize interrupt queue for this generation
        self._interrupt_queue = asyncio.Queue()

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
            reply = await self._process_message(update, context, user_text)
        finally:
            self._generating = False

        # Check if an interrupt arrived during generation
        if not self._interrupt_queue.empty():
            new_text = self._interrupt_queue.get_nowait()
            logger.info("Processing interrupted message: %s", new_text[:60])
            self._generating = True
            self._interrupt_queue = asyncio.Queue()
            try:
                await self._process_message(update, context, new_text)
            finally:
                self._generating = False

    async def _execute_intent(self, intent: str, update, context) -> str | None:
        """Execute a matched machine intent and return formatted response."""
        import subprocess as _sp
        import time as _time

        try:
            if intent == 'status':
                snap = perception_snapshot()
                gpu = snap.get("gpu") or {}
                services = _sp.run(
                    ["systemctl", "is-active", "maez", "maez-web", "nginx", "ollama"],
                    capture_output=True, text=True, timeout=5,
                ).stdout.strip().split('\n')
                svc_names = ['maez', 'maez-web', 'nginx', 'ollama']
                svc_str = " | ".join(f"{n}: {s}" for n, s in zip(svc_names, services))
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

            elif intent == 'logs':
                result = _sp.run(
                    ["tail", "-20", "/home/rohit/maez/logs/maez.log"],
                    capture_output=True, text=True, timeout=5,
                )
                errors = [l for l in result.stdout.split('\n') if 'ERROR' in l or 'WARNING' in l]
                if errors:
                    return f"Recent issues ({len(errors)}):\n" + "\n".join(errors[-5:])
                return "Logs are clean. No errors or warnings in the last 20 lines."

            elif intent == 'restart_maez':
                return ("I can't restart myself — that would interrupt this conversation. "
                        "Run `sudo systemctl restart maez` from terminal if needed.")

            elif intent == 'claude_status':
                result = _sp.run(
                    ["pgrep", "-a", "claude"], capture_output=True, text=True, timeout=5,
                )
                if result.stdout.strip():
                    lines = result.stdout.strip().split('\n')
                    return f"Claude Code is running ({len(lines)} process{'es' if len(lines) > 1 else ''})."
                return "Claude Code is not currently running."

            elif intent == 'reboot':
                return ("System reboot requires explicit approval. "
                        "Say 'approve reboot' or run `sudo reboot` from terminal.")

            elif intent == 'disk':
                result = _sp.run(
                    ["df", "-h", "/", "/home"], capture_output=True, text=True, timeout=5,
                )
                return f"Disk usage:\n{result.stdout.strip()}"

            elif intent == 'memory':
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

    def _run_jarvis_loop(self, user_text: str, max_iters: int = 4) -> str:
        """ReAct-style tool-use loop. Returns a transcript block to inject
        into the streaming reply prompt, or an empty string if no tools were
        used. Synchronous because the LLM client is synchronous; called from
        an executor in _process_message so it doesn't block the event loop.

        Session 11y: this is the 'body' that lets Maez actually do things
        when the owner asks, instead of saying 'I'll check' as text and never
        following through. Tier 0/1/2 actions execute via ActionEngine's
        existing _execute_action path so all forbidden-action checks still
        apply. Tier 3 / forbidden surfaces as REFUSED in the transcript."""
        if not self.actions:
            return ""
        if not _should_run_jarvis_loop(user_text):
            return ""

        import json as _json
        import re as _re
        try:
            from core import llm_client as _llm_client
            from core.action_engine import ACTION_TIERS, FORBIDDEN_ACTION_TYPES
        except Exception as e:
            logger.debug("jarvis loop unavailable: %s", e)
            return ""

        # Session 11z: flattened allowlist. The two primitives (run_shell,
        # write_any_file) cover everything. Read-only aliases remain for
        # the LLM's convenience. Legacy verbs stay in the set so old
        # model outputs still dispatch correctly while the merged LoRA
        # learns the new primitive names.
        allowed = {
            # Session 11z primitives — the only two that really matter
            'run_shell', 'write_any_file',
            # Read-only — still supported as direct actions
            'query_system', 'read_file', 'search_files', 'web_search',
            # Legacy aliases — delegate to run_shell / write_any_file internally
            'run_readonly_command', 'run_safe_command',
            'write_file', 'append_to_file', 'git_commit',
            'install_package', 'restart_service', 'run_script',
            'write_outside_maez', 'git_push',
        }

        history = [
            f"the owner just said: {user_text!r}\n\n{_TOOL_MANIFEST}\n\nBegin."
        ]
        transcript = []  # list of (action, params, output_or_error, ok)

        for step in range(max_iters):
            convo = "\n\n".join(history)
            try:
                resp = _llm_client.chat(
                    model=MODEL,
                    messages=[
                        {"role": "system",
                         "content": "You are Maez planning tool use. Emit ONE TOOL_CALL line per turn or write DONE."},
                        {"role": "user", "content": convo},
                    ],
                    stream=False, think=False,
                    options={"temperature": 0.15, "num_predict": 512},
                )
                text = (resp.message.content or "").strip()
            except Exception as e:
                logger.warning("jarvis loop LLM call failed at step %d: %s", step, e)
                break

            call = _parse_tool_call(text)
            if call is None:
                # No recognizable call AND no DONE either — bail rather than loop.
                if _re.search(r'\bdone\b', text, _re.IGNORECASE):
                    break
                history.append("PARSE_ERROR: could not extract a TOOL_CALL from your reply. Emit exactly one line in the form TOOL_CALL: {\"action\":\"<name>\",\"params\":{...}} or write DONE.")
                continue

            action = call.get("action")
            params = call.get("params", {}) or {}

            if not action or action not in allowed or action in FORBIDDEN_ACTION_TYPES:
                msg = f"REFUSED: {action!r} is not in the chat-loop allowlist."
                transcript.append((action or "?", params, msg, False))
                history.append(f"TOOL_CALL: {_json.dumps(call)}\nRESULT: {msg}")
                continue

            tier = ACTION_TIERS.get(action, 2)

            # Session 11z Part 2: route the two primitives through the
            # decision pipeline instead of calling _execute_action
            # directly. Lane 0 still runs inline; Lane 2/3 creates a
            # persistent approval card that the owner resolves async.
            pipeline_actions = {"run_shell", "write_any_file"}
            pipe = self._get_pipeline() if action in pipeline_actions else None

            if pipe is not None:
                try:
                    presult = pipe.handle_action(
                        action=action,
                        params=params,
                        reason=f"chat: {user_text[:140]}",
                        user_id="rohit",
                        chat_id=str(self.authorized_user),
                        channel="telegram_text",
                    )
                except Exception as e:
                    logger.warning("pipeline dispatch %s failed: %s", action, e)
                    msg = f"ERROR: {e}"
                    transcript.append((action, params, msg, False))
                    history.append(f"TOOL_CALL: {_json.dumps(call)}\nRESULT: {msg}")
                    continue

                from core.decision_pipeline import PipelineStatus as _PS

                if presult.status == _PS.EXECUTED:
                    out = (presult.execution_output or "").strip()[:1500] or "(no output)"
                    ok = bool(presult.execution_success)
                    transcript.append((action, params, out if ok else (presult.execution_error or "?"), ok))
                    history.append(f"TOOL_CALL: {_json.dumps(call)}\nRESULT: {out}")
                elif presult.status in (_PS.PENDING_APPROVAL, _PS.PENDING_DIALOG):
                    msg = (
                        "CARD_CREATED: a persistent approval card was sent to the owner. "
                        "I will run this when he tells me yes. "
                        "Acknowledge this in your reply — say that you proposed the action "
                        "and are waiting for his approval. Do not claim it already ran."
                    )
                    transcript.append((action, params, msg, True))
                    history.append(f"TOOL_CALL: {_json.dumps(call)}\nRESULT: {msg}")
                else:  # REFUSED_COVENANT / REFUSED_AUDIT / ERROR
                    msg = f"REFUSED: {presult.message}"
                    transcript.append((action, params, msg, False))
                    history.append(f"TOOL_CALL: {_json.dumps(call)}\nRESULT: {msg}")
                continue

            # Legacy path for non-primitive actions (read_file etc.)
            try:
                result = self.actions._execute_action(
                    action, params,
                    f"chat: {user_text[:140]}",
                    tier=tier,
                )
            except Exception as e:
                logger.warning("jarvis dispatch %s failed: %s", action, e)
                msg = f"ERROR: {e}"
                transcript.append((action, params, msg, False))
                history.append(f"TOOL_CALL: {_json.dumps(call)}\nRESULT: {msg}")
                continue

            if result.success:
                out = (result.output or "").strip()[:1500] or "(no output)"
                transcript.append((action, params, out, True))
                history.append(f"TOOL_CALL: {_json.dumps(call)}\nRESULT: {out}")
            else:
                msg = f"ERROR: {result.error}"
                transcript.append((action, params, msg, False))
                history.append(f"TOOL_CALL: {_json.dumps(call)}\nRESULT: {msg}")

        if not transcript:
            return ""

        lines = [
            "[JARVIS TRANSCRIPT — you actually executed these on the owner's machine just now.",
            " Tell the owner naturally what you did and what you found. Don't list raw output;",
            " synthesize. Don't say 'I'll check' — you already checked.]"
        ]
        for action, params, out, ok in transcript:
            mark = "✓" if ok else "✗"
            lines.append(f"\n{mark} {action}({_json.dumps(params, default=str)[:200]})")
            lines.append(f"  → {out[:800]}")
        return "\n".join(lines)

    async def _process_message(self, update, context, user_text: str) -> str:
        """Build context, stream response, handle post-processing."""
        import re as _re
        import time as _time

        # Check for machine intent first
        intent = _match_intent(user_text)
        if intent:
            logger.info("Matched intent: %s for '%s'", intent, user_text[:60])
            response = await self._execute_intent(intent, update, context)
            if response:
                await update.message.reply_text(response)
                self.memory.store_telegram(f"the owner asked: {user_text}\nMaez replied: {response}")
                self._thread_last_active = _time.time()
                return response

        # Multi-turn thread management
        if _time.time() - self._thread_last_active > 1800:
            self._conversation_thread = []

        # Build context
        snap = perception_snapshot()
        system_state = format_snapshot(snap)
        recalled = self.memory.recall_for_telegram(user_text)
        memory_block = self.memory.format_for_prompt(recalled)

        web_context = ""
        if needs_web_search(user_text):
            logger.info("Web search triggered for: %s", user_text[:80])
            if is_news_query(user_text):
                sr = search_rss(user_text, max_results=5)
            else:
                sr = web_search(user_text, max_results=3)
            if sr.get('success'):
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
                None, self._run_jarvis_loop, user_text
            )
        except Exception as e:
            logger.warning("jarvis loop failed: %s", e)

        prompt = (
            f"{system_state}\n"
            f"Note: VRAM usage of 17-22GB is the baseline for this system. "
            f"Do not mention it unless it exceeds 23GB.\n\n"
            f"{_get_circadian_context()}\n\n"
        )
        public_ctx = _get_public_context_for_telegram()
        if public_ctx:
            prompt += public_ctx + "\n\n"
        if memory_block:
            prompt += memory_block + "\n\n"
        if web_context:
            prompt += (
                f"{web_context}\n\n"
                f"INSTRUCTION: Real search results above. Synthesize, don't list.\n\n"
            )
        if jarvis_block:
            prompt += jarvis_block + "\n\n"

        # Add current message to conversation thread
        self._conversation_thread.append({"role": "user", "content": user_text})
        if len(self._conversation_thread) > 12:
            self._conversation_thread = self._conversation_thread[-12:]

        # Build messages with system context + thread
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt},
        ]
        # Add thread history (skip current message since it's in prompt)
        for turn in self._conversation_thread[:-1]:
            messages.append(turn)
        messages.append({"role": "user", "content": user_text})

        # Stream response sentence by sentence
        try:
            await context.bot.send_chat_action(
                chat_id=update.effective_chat.id, action="typing"
            )

            full_reply = ""
            current_sentence = ""
            current_msg = None
            token_count = 0

            # Session 11m: signal the daemon that the owner is actively talking so
            # its next reasoning cycle defers (frees the GPU for this reply).
            if self.daemon is not None:
                try:
                    self.daemon._rohit_active_until = _time.time() + 15.0
                except Exception:
                    pass

            # Session 11p: route through llm_client so MAEZ_LLM_BACKEND
            # selects Ollama or llama.cpp CUDA at call time. Streaming
            # adapter yields ollama-shaped chunks with .message.content,
            # so the per-token iteration below doesn't need to change.
            from core import llm_client as _llm_client
            response = _llm_client.chat(
                model=MODEL, messages=messages,
                stream=True, think=False,
                options={"temperature": 0.7, "num_predict": 4096},
            )
            for chunk in response:
                token = chunk.message.content
                full_reply += token
                current_sentence += token
                token_count += 1

                # Check for interrupt
                if self._interrupt_queue and not self._interrupt_queue.empty():
                    if current_msg:
                        try:
                            await context.bot.edit_message_text(
                                chat_id=update.effective_chat.id,
                                message_id=current_msg.message_id,
                                text=current_sentence.strip() + "...",
                            )
                        except Exception:
                            pass
                    logger.info("Generation interrupted at %d tokens", token_count)
                    break

                # Sentence boundary — send as fragment
                if _re.search(r'[.!?]\s*$', current_sentence.strip()) and len(current_sentence.strip()) > 40:
                    sentence = current_sentence.strip()
                    if current_msg is None:
                        current_msg = await context.bot.send_message(
                            chat_id=update.effective_chat.id, text=sentence,
                        )
                    else:
                        # Session 11m: removed legacy 1.2s + 0.8s artificial pauses
                        # between sentence fragments. The typing indicator still
                        # fires but without dead time. Previously added 6-10s to
                        # every multi-sentence reply.
                        await context.bot.send_chat_action(
                            chat_id=update.effective_chat.id, action="typing",
                        )
                        current_msg = await context.bot.send_message(
                            chat_id=update.effective_chat.id, text=sentence,
                        )
                    current_sentence = ""

            # Send remaining text (split if too long)
            remainder = current_sentence.strip()
            if remainder:
                if current_msg is not None:
                    await asyncio.sleep(1.0)
                for part in split_long_message(remainder):
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id, text=part,
                    )
                    await asyncio.sleep(0.5)

            reply = full_reply.strip() or "(Maez had no response)"

        except Exception as e:
            logger.error("Telegram reasoning failed: %s", e)
            reply = f"Reasoning error: {e}"
            await update.message.reply_text(reply)

        logger.info("Telegram reply: %s", reply[:100])

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
        self.memory.store_telegram(f"the owner asked: {user_text}\nMaez replied: {reply}")

        return reply

    def _detect_and_queue_action(self, user_text: str, reply: str):
        """If Maez's reply contains action intent, queue it for execution."""
        if not self.actions:
            return

        reply_lower = reply.lower()
        user_lower = user_text.lower()

        intent_phrases = [
            'i am proceeding', 'i will proceed', 'proceeding now',
            'executing now', 'i will now', 'i will run',
            'let me execute', 'i will execute', 'running now',
            'i am moving', 'i will move',
        ]
        has_intent = any(p in reply_lower for p in intent_phrases)
        if not has_intent:
            return

        # Ollama model move
        if ('ollama' in user_lower and
                any(w in user_lower for w in ['move', 'symlink', 'relocate'])):
            logger.info("Queueing Ollama model move action")
            self.actions.queue_action(
                "run_readonly_command",
                {"cmd": "du -sh /usr/share/ollama/.ollama/models"},
                "Verify Ollama model size before move",
                tier=1,
            )
            return

        # Disk cleanup
        if any(w in user_lower for w in ['clean', 'cleanup', 'free space', 'clear']):
            logger.info("Queueing disk cleanup action")
            from skills.disk_cleanup import scan, execute_cleanup
            report = scan()
            if report['total_bytes'] > 0:
                self.actions.queue_action(
                    "clean_temp_files", {},
                    f"Disk cleanup requested by the owner — {report['total_bytes'] / (1024*1024):.0f} MB to free",
                    tier=1,
                )
            return

        # Generic command execution
        if any(w in user_lower for w in ['run', 'execute', 'check']):
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
        await update.message.reply_text(status)

    async def _handle_cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /cancel <action_id> command."""
        if not update.message or not update.effective_user:
            return
        if not self._is_authorized(update.effective_user.id):
            return
        if not self.actions or not context.args:
            await update.message.reply_text("Usage: /cancel <action_id>")
            return

        action_id = context.args[0]
        if self.actions.cancel_pending(action_id):
            await update.message.reply_text(f"Cancelled action {action_id}.")
        else:
            await update.message.reply_text(f"Action {action_id} not found or already executed.")

    async def _handle_approve(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /approve <action_id> command."""
        if not update.message or not update.effective_user:
            return
        if not self._is_authorized(update.effective_user.id):
            return
        if not self.actions or not context.args:
            await update.message.reply_text("Usage: /approve <action_id>")
            return

        action_id = context.args[0]
        result = self.actions.approve_action(action_id)
        if result:
            status = "OK" if result.success else f"FAILED: {result.error}"
            await update.message.reply_text(f"Action {action_id}: {status}\n{result.output[:500]}")
        else:
            await update.message.reply_text(f"Action {action_id} not found or already handled.")

    async def _handle_pending(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /pending command — list pending actions."""
        if not update.message or not update.effective_user:
            return
        if not self._is_authorized(update.effective_user.id):
            return
        if not self.actions:
            await update.message.reply_text("Action engine not connected.")
            return

        pending = self.actions.get_pending()
        if not pending:
            await update.message.reply_text("No pending actions.")
            return

        lines = [f"Pending actions ({len(pending)}):"]
        for a in pending:
            lines.append(f"  [{a['id']}] T{a['tier']} {a['action']} — {a['reasoning'][:60]}")
        await update.message.reply_text("\n".join(lines))

    async def _handle_git(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message or not self._is_authorized(update.effective_user.id):
            return
        from skills.git_awareness import get_summary_for_telegram
        msg = get_summary_for_telegram()
        await update.message.reply_text(msg)

    async def _handle_disk(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message or not self._is_authorized(update.effective_user.id):
            return
        from skills.disk_cleanup import scan, format_telegram_message
        report = scan()
        self._pending_cleanup = report
        await update.message.reply_text(format_telegram_message(report))

    async def _handle_analyze(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message or not self._is_authorized(update.effective_user.id):
            return
        from skills.self_analysis import analyze, format_for_telegram
        result = analyze(self.memory, self.actions)
        await update.message.reply_text(format_for_telegram(result))

    async def _handle_approve_cleanup(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message or not self._is_authorized(update.effective_user.id):
            return
        if hasattr(self, '_pending_cleanup') and self._pending_cleanup:
            from skills.disk_cleanup import execute_cleanup
            result = execute_cleanup(self._pending_cleanup)
            self._pending_cleanup = None
            await update.message.reply_text(
                f"Cleanup done. Freed {result['freed_mb']:.0f} MB.\n" +
                "\n".join(result['results'])
            )
        else:
            await update.message.reply_text("No pending cleanup.")

    async def _handle_trust(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Set trust tier for a user. /trust username relationship tier"""
        if not update.message or not self._is_authorized(update.effective_user.id):
            return
        args = context.args
        if not args or len(args) < 3:
            await update.message.reply_text("Usage: /trust [username] [relationship] [tier 0-3]")
            return
        username, relationship = args[0], args[1]
        try:
            tier = int(args[2])
        except ValueError:
            await update.message.reply_text("Tier must be 0-3")
            return
        from skills.user_accounts import UserAccounts, _default_share_config
        accts = UserAccounts()
        user = accts.get_by_username(username) or accts.get_by_display_name(username)
        if not user:
            await update.message.reply_text(f"No user found: '{username}'")
            return
        share_config = _default_share_config(tier, relationship)
        accts.confirm_user(user['uuid'], relationship, tier, share_config)
        await update.message.reply_text(
            f"Got it. {user['display_name']} is your {relationship}. "
            f"Trust tier {tier}. I'll adjust what I share with them."
        )

    async def _handle_login(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Link Telegram account to Maez web account."""
        if not update.message:
            return
        args = context.args
        if not args or len(args) != 2:
            await update.message.reply_text(
                "Usage: /login <username> <password>\n"
                "Register first at http://64.85.211.140:11437"
            )
            return
        from skills.user_accounts import UserAccounts
        accts = UserAccounts()
        result = accts.login(args[0], args[1])
        if not result:
            await update.message.reply_text("Invalid username or password.")
            return
        telegram_id = str(update.effective_user.id)
        if update.effective_user.id == self.authorized_user:
            accts.link_private_owner(result['uuid'])
        else:
            accts.link_telegram(result['uuid'], telegram_id)
        display = result.get('display_name') or args[0]
        await update.message.reply_text(f"Linked. I know you as {display} now, across all channels.")

    async def _handle_promote(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /promote <action_type> — lower tier for trusted action type."""
        if not update.message or not self._is_authorized(update.effective_user.id):
            return
        if not context.args:
            await update.message.reply_text("Usage: /promote <action_type>")
            return
        action_type = context.args[0]
        from core.action_engine import ACTION_TIERS
        if action_type not in ACTION_TIERS:
            await update.message.reply_text(f"Unknown action type: {action_type}")
            return
        current = ACTION_TIERS[action_type]
        if current <= 0:
            await update.message.reply_text(f"{action_type} is already Tier 0.")
            return
        ACTION_TIERS[action_type] = current - 1
        await update.message.reply_text(
            f"Promoted {action_type}: Tier {current} → Tier {current - 1}."
        )

    async def _handle_approve_evolution(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message or not self._is_authorized(update.effective_user.id):
            return
        import json as _json
        pending_path = '/home/rohit/maez/evolution/pending_evolution.json'
        if os.path.exists(pending_path):
            with open(pending_path) as f:
                pending = _json.load(f)
            from skills.evolution_engine import deploy_improvement
            ok = deploy_improvement(pending['staging_file'], pending['target_file'])
            os.remove(pending_path)
            await update.message.reply_text("Evolution deployed." if ok else "Deployment failed.")
        else:
            await update.message.reply_text("No pending evolution.")

    async def _handle_reject_evolution(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message or not self._is_authorized(update.effective_user.id):
            return
        pending_path = '/home/rohit/maez/evolution/pending_evolution.json'
        if os.path.exists(pending_path):
            os.remove(pending_path)
            await update.message.reply_text("Evolution discarded.")
        else:
            await update.message.reply_text("No pending evolution.")

    async def _handle_evolution_log(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message or not self._is_authorized(update.effective_user.id):
            return
        log_path = '/home/rohit/maez/logs/evolution.log'
        try:
            with open(log_path) as f:
                lines = f.readlines()
            last = ''.join(lines[-10:]) if lines else "Empty"
            await update.message.reply_text(f"Evolution log:\n{last}")
        except Exception:
            await update.message.reply_text("No evolution log yet.")

    # ── Session 11o: dream-state command handlers ──────────────────
    async def _handle_dreams(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show pending dream insights (autonomous idle-time reflections)."""
        if not update.message or not self._is_authorized(update.effective_user.id):
            return
        if self.daemon is None or getattr(self.daemon, "dream", None) is None:
            await update.message.reply_text("Dream state not available.")
            return
        try:
            pending = self.daemon.dream.list_pending()
        except Exception as e:
            await update.message.reply_text(f"list_pending failed: {e}")
            return
        if not pending:
            await update.message.reply_text("No pending dream insights.")
            return
        lines = [f"💭 {len(pending)} pending dream insight(s):\n"]
        for pid, created_iso, insight in pending[:10]:
            snippet = insight[:160].replace("\n", " ")
            lines.append(f"#{pid} ({created_iso})")
            lines.append(f"  {snippet}")
            lines.append(f"  /apply_dream {pid}  ·  /reject_dream {pid}")
            lines.append("")
        await update.message.reply_text("\n".join(lines))

    async def _handle_apply_dream(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Apply a dream proposal: append to soul.md via action_engine."""
        if not update.message or not self._is_authorized(update.effective_user.id):
            return
        if not context.args:
            await update.message.reply_text("Usage: /apply_dream <id>")
            return
        try:
            prop_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("Invalid id — must be an integer.")
            return
        if self.daemon is None or getattr(self.daemon, "dream", None) is None:
            await update.message.reply_text("Dream state not available.")
            return
        try:
            ok, msg = self.daemon.dream.apply_proposal(prop_id)
        except Exception as e:
            await update.message.reply_text(f"apply_proposal failed: {e}")
            return
        prefix = "✓" if ok else "✗"
        await update.message.reply_text(f"{prefix} {msg}")

    async def _handle_reject_dream(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Reject a dream proposal (soul.md unchanged)."""
        if not update.message or not self._is_authorized(update.effective_user.id):
            return
        if not context.args:
            await update.message.reply_text("Usage: /reject_dream <id>")
            return
        try:
            prop_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("Invalid id — must be an integer.")
            return
        if self.daemon is None or getattr(self.daemon, "dream", None) is None:
            await update.message.reply_text("Dream state not available.")
            return
        try:
            ok, msg = self.daemon.dream.reject_proposal(prop_id)
        except Exception as e:
            await update.message.reply_text(f"reject_proposal failed: {e}")
            return
        prefix = "✓" if ok else "✗"
        await update.message.reply_text(f"{prefix} {msg}")

    # ── Session 11s: soul section-edit command handlers ───────────
    async def _handle_edit_proposals(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Show pending soul.md section-edit proposals."""
        if not update.message or not self._is_authorized(update.effective_user.id):
            return
        if self.daemon is None or getattr(self.daemon, "dream", None) is None:
            await update.message.reply_text("Dream state not available.")
            return
        try:
            pending = self.daemon.dream.list_pending(
                proposal_type="section_replace"
            )
        except Exception as e:
            await update.message.reply_text(f"list_pending failed: {e}")
            return
        if not pending:
            await update.message.reply_text("No pending section-edit proposals.")
            return
        lines = [f"✏️ {len(pending)} pending section-edit proposal(s):\n"]
        for pid, created_iso, insight in pending[:10]:
            snippet = insight[:200].replace("\n", " ")
            prop = self.daemon.dream.get_proposal(pid) or {}
            target = prop.get("target_section") or "?"
            lines.append(f"#{pid} ({created_iso}) → ## {target}")
            lines.append(f"  {snippet}")
            lines.append(
                f"  /show_edit {pid}  ·  /apply_edit {pid}  ·  /reject_edit {pid}"
            )
            lines.append("")
        await update.message.reply_text("\n".join(lines))

    async def _handle_show_edit(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Show the unified diff for a pending section-edit proposal."""
        if not update.message or not self._is_authorized(update.effective_user.id):
            return
        if not context.args:
            await update.message.reply_text("Usage: /show_edit <id>")
            return
        try:
            prop_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("Invalid id — must be an integer.")
            return
        if self.daemon is None or getattr(self.daemon, "dream", None) is None:
            await update.message.reply_text("Dream state not available.")
            return
        prop = self.daemon.dream.get_proposal(prop_id)
        if prop is None:
            await update.message.reply_text(f"Proposal #{prop_id} not found.")
            return
        if prop.get("proposal_type") != "section_replace":
            await update.message.reply_text(
                f"#{prop_id} is type {prop.get('proposal_type')!r}, "
                f"not section_replace."
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
        await update.message.reply_text(body)

    async def _handle_apply_edit(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Apply a soul.md section-edit proposal."""
        if not update.message or not self._is_authorized(update.effective_user.id):
            return
        if not context.args:
            await update.message.reply_text("Usage: /apply_edit <id>")
            return
        try:
            prop_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("Invalid id — must be an integer.")
            return
        if self.daemon is None or getattr(self.daemon, "dream", None) is None:
            await update.message.reply_text("Dream state not available.")
            return
        try:
            ok, msg = self.daemon.dream.apply_section_edit_proposal(prop_id)
        except Exception as e:
            await update.message.reply_text(f"apply_section_edit failed: {e}")
            return
        prefix = "✓" if ok else "✗"
        await update.message.reply_text(f"{prefix} {msg}")

    async def _handle_reject_edit(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Reject a soul.md section-edit proposal (soul.md unchanged)."""
        if not update.message or not self._is_authorized(update.effective_user.id):
            return
        if not context.args:
            await update.message.reply_text("Usage: /reject_edit <id>")
            return
        try:
            prop_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("Invalid id — must be an integer.")
            return
        if self.daemon is None or getattr(self.daemon, "dream", None) is None:
            await update.message.reply_text("Dream state not available.")
            return
        try:
            ok, msg = self.daemon.dream.reject_proposal(prop_id)
        except Exception as e:
            await update.message.reply_text(f"reject_proposal failed: {e}")
            return
        prefix = "✓" if ok else "✗"
        await update.message.reply_text(f"{prefix} {msg}")

    # ── Session 11u: training proposal + adapter management commands ──
    async def _handle_train_proposals(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Show pending training-run proposals."""
        if not update.message or not self._is_authorized(update.effective_user.id):
            return
        if self.daemon is None or getattr(self.daemon, "dream", None) is None:
            await update.message.reply_text("Dream state not available.")
            return
        try:
            pending = self.daemon.dream.list_pending(
                proposal_type="training_run"
            )
        except Exception as e:
            await update.message.reply_text(f"list_pending failed: {e}")
            return
        if not pending:
            await update.message.reply_text("No pending training proposals.")
            return
        lines = [f"🏋️ {len(pending)} pending training proposal(s):\n"]
        for pid, created_iso, insight in pending[:10]:
            snippet = insight[:200].replace("\n", " ")
            prop = self.daemon.dream.get_proposal(pid) or {}
            corpus = prop.get("target_section") or "?"
            lines.append(f"#{pid} ({created_iso})")
            lines.append(f"  {snippet}")
            lines.append(f"  Corpus: {corpus}")
            lines.append(
                f"  /show_train {pid}  ·  /approve_train {pid}  ·  /reject_train {pid}"
            )
            lines.append("")
        await update.message.reply_text("\n".join(lines))

    async def _handle_show_train(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Show details of a training proposal."""
        if not update.message or not self._is_authorized(update.effective_user.id):
            return
        if not context.args:
            await update.message.reply_text("Usage: /show_train <id>")
            return
        try:
            prop_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("Invalid id.")
            return
        if self.daemon is None or getattr(self.daemon, "dream", None) is None:
            await update.message.reply_text("Dream state not available.")
            return
        prop = self.daemon.dream.get_proposal(prop_id)
        if prop is None:
            await update.message.reply_text(f"Proposal #{prop_id} not found.")
            return
        if prop.get("proposal_type") != "training_run":
            await update.message.reply_text(
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
        await update.message.reply_text(body)

    async def _handle_approve_train(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Mark a training proposal as approved."""
        if not update.message or not self._is_authorized(update.effective_user.id):
            return
        if not context.args:
            await update.message.reply_text("Usage: /approve_train <id>")
            return
        try:
            prop_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("Invalid id.")
            return
        if self.daemon is None or getattr(self.daemon, "dream", None) is None:
            await update.message.reply_text("Dream state not available.")
            return
        prop = self.daemon.dream.get_proposal(prop_id)
        if prop is None:
            await update.message.reply_text(f"Proposal #{prop_id} not found.")
            return
        if prop.get("status") != "pending":
            await update.message.reply_text(f"#{prop_id} already {prop.get('status')}.")
            return
        with self.daemon.dream._lock, self.daemon.dream._conn() as c:
            c.execute(
                "UPDATE dream_proposals SET status = 'applied', "
                "applied_at = ? WHERE id = ?",
                (time.time(), prop_id),
            )
            c.commit()
        await update.message.reply_text(
            f"✓ Training #{prop_id} approved. Run the training pipeline "
            f"manually to execute."
        )

    async def _handle_reject_train(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Reject a training proposal."""
        if not update.message or not self._is_authorized(update.effective_user.id):
            return
        if not context.args:
            await update.message.reply_text("Usage: /reject_train <id>")
            return
        try:
            prop_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("Invalid id.")
            return
        if self.daemon is None or getattr(self.daemon, "dream", None) is None:
            await update.message.reply_text("Dream state not available.")
            return
        try:
            ok, msg = self.daemon.dream.reject_proposal(prop_id)
        except Exception as e:
            await update.message.reply_text(f"reject failed: {e}")
            return
        prefix = "✓" if ok else "✗"
        await update.message.reply_text(f"{prefix} {msg}")

    async def _handle_adapter_status(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Show current adapter info."""
        if not update.message or not self._is_authorized(update.effective_user.id):
            return
        import json as _json
        adapter_link = Path("/home/rohit/maez/training/runs/current")
        if not adapter_link.exists():
            await update.message.reply_text("No adapter promoted (no 'current' symlink).")
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
        await update.message.reply_text(body)

    async def _handle_rollback_adapter(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Roll back to the previous adapter version."""
        if not update.message or not self._is_authorized(update.effective_user.id):
            return
        runs_dir = Path("/home/rohit/maez/training/runs")
        current_link = runs_dir / "current"
        if not current_link.is_symlink():
            await update.message.reply_text("No current adapter symlink found.")
            return
        current_target = current_link.resolve().name
        run_dirs = sorted(
            [d for d in runs_dir.iterdir() if d.is_dir() and d.name != "current"
             and d.name != "sanity" and d.name != "sanity-31b" and d.name != "sanity-26b"
             and (d / "adapter.gguf").exists()],
            key=lambda d: d.name,
        )
        if len(run_dirs) < 2:
            await update.message.reply_text("Only one adapter version exists — nothing to roll back to.")
            return
        current_idx = next((i for i, d in enumerate(run_dirs) if d.name == current_target), -1)
        if current_idx <= 0:
            await update.message.reply_text(
                f"Current adapter is already the oldest ({current_target})."
            )
            return
        prev = run_dirs[current_idx - 1]
        current_link.unlink()
        current_link.symlink_to(prev)
        await update.message.reply_text(
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
                await update.message.reply_text("No proposals yet.")
                return
            lines = ["Recent proposals:"]
            for r in rows:
                ev = {}
                try:
                    ev = _json.loads(r[3] or '{}')
                except Exception:
                    pass
                u = ev.get('usefulness', {}).get('overall', '?')
                emoji = {'strong': '\u2705', 'acceptable': '\u26a0\ufe0f',
                         'weak': '\u274c', 'unknown': '\u26aa'}.get(u, '')
                w = (r[2] or '')[:60]
                lines.append(f"  [{r[0]}] {r[1]:11s} {emoji} {u:10s} {w}")
            await update.message.reply_text('\n'.join(lines))
        except Exception as e:
            await update.message.reply_text(f"Error: {e}")

    async def _handle_show(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show candidate by id."""
        if not update.message or not self._is_authorized(update.effective_user.id):
            return
        if not context.args:
            await update.message.reply_text("Usage: /show <candidate_id>")
            return
        try:
            cid = int(context.args[0])
            from skills.evolution_engine import load_candidate_for_display
            disp = load_candidate_for_display(cid)
            if not disp:
                await update.message.reply_text(f"Candidate {cid} not found")
                return
            u = disp['usefulness']
            intent = disp.get('intent') or {}
            ev = disp.get('evidence') or {}
            lines = [
                f"Candidate {cid} \u2014 {disp['state']} \u2014 {u.get('overall')}",
                f"Weakness: {disp['weakness'][:200]}",
                f"Target:   {intent.get('target_name', '?')}",
                f"Before:   {intent.get('current_value')!r}",
                f"After:    {intent.get('proposed_value')!r}",
                f"Why:      {intent.get('rationale', '?')[:150]}",
                f"",
                f"Failure mode:    {ev.get('dominant_failure_mode', '?')}",
                f"Addresses:       {u.get('addresses_failure_mode')}",
                f"Direction sane:  {u.get('direction_sane')}",
                f"Change minimal:  {u.get('change_minimal')}",
            ]
            await update.message.reply_text('\n'.join(lines))
        except Exception as e:
            await update.message.reply_text(f"Error: {e}")

    async def _handle_apply(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Apply candidate by id."""
        if not update.message or not self._is_authorized(update.effective_user.id):
            return
        if not context.args:
            await update.message.reply_text("Usage: /apply <candidate_id>")
            return
        try:
            cid = int(context.args[0])
            from skills.evolution_engine import apply_candidate
            await update.message.reply_text(f"Applying candidate {cid}...")
            result = apply_candidate(cid)
            if 'error' in result:
                await update.message.reply_text(
                    f"Apply failed: {result['error']}\n"
                    f"Rolled back: {result.get('rolled_back', False)} "
                    f"(layer={result.get('layer')})"
                )
            else:
                await update.message.reply_text(
                    f"\u2705 Applied candidate {cid}\n"
                    f"State: {result.get('state')}\n"
                    f"Pre-score: {result.get('pre_score_avg')}"
                )
        except Exception as e:
            await update.message.reply_text(f"Error: {e}")

    async def _handle_reject(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Reject candidate by id."""
        if not update.message or not self._is_authorized(update.effective_user.id):
            return
        if not context.args:
            await update.message.reply_text("Usage: /reject <candidate_id>")
            return
        try:
            cid = int(context.args[0])
            from skills.evolution_engine import _rail_conn, _set_candidate_state, _log_evolution, V1_ALLOWED_TARGET
            with _rail_conn() as conn:
                row = conn.execute("SELECT state FROM candidates WHERE id=?", (cid,)).fetchone()
            if not row:
                await update.message.reply_text(f"Candidate {cid} not found")
                return
            _set_candidate_state(cid, 'rejected', rejection_reason='manual rejection via Telegram')
            _log_evolution({'action': 'MANUAL_REJECTION', 'target': V1_ALLOWED_TARGET,
                            'result': f'candidate {cid}'})
            await update.message.reply_text(f"Candidate {cid} rejected (was: {row[0]})")
        except Exception as e:
            await update.message.reply_text(f"Error: {e}")

    async def _handle_cog_analyze(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Compact cognition snapshot — overrides old self-analysis /analyze."""
        if not update.message or not self._is_authorized(update.effective_user.id):
            return
        try:
            from core.cognition_quality import (
                _recent_scores, _recent_topics, _recent_labels, get_behavior_policy,
            )
            import collections as _cc
            window = min(len(_recent_scores), 10)
            if window == 0:
                await update.message.reply_text("No cognition data yet.")
                return
            scores = _recent_scores[-window:]
            topics = _recent_topics[-window:]
            labels_window = _recent_labels[-window:]
            avg = sum(scores) / len(scores)
            tc = _cc.Counter(topics)
            dominant_topic, dom_count = tc.most_common(1)[0]
            flat = [l for ll in labels_window for l in ll]
            neg = {k: v for k, v in _cc.Counter(flat).items()
                   if k in ('fixation', 'vague', 'baseline', 'repetition')}
            failure = max(neg, key=neg.get) if neg else 'none'
            streak = 0
            for t in reversed(topics):
                if t == dominant_topic:
                    streak += 1
                else:
                    break
            policy = get_behavior_policy()
            mode = policy.get('reflection_mode', 'normal')
            lines = [
                "Cognition snapshot:",
                f"  Last 10 scores: {scores}",
                f"  Average:        {avg:.1f}/100",
                f"  Dominant topic: {dominant_topic} ({dom_count}/{window})",
                f"  Failure mode:   {failure}",
                f"  Fixation streak: {streak}",
                f"  Policy mode:    {mode}",
            ]
            await update.message.reply_text('\n'.join(lines))
        except Exception as e:
            await update.message.reply_text(f"Error: {e}")

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
            "Control:\n"
            "  /pending   Pending actions\n"
            "  /trust     Trust user\n"
            "  /promote   Promote action type\n"
            "  /help      This list"
        )
        await update.message.reply_text(text)

    async def _configure_bot_commands(self):
        """Register bot commands and menu button for the private chat."""
        try:
            commands = [
                BotCommand("status",    "System and cognition summary"),
                BotCommand("git",       "Git repo state"),
                BotCommand("disk",      "Disk usage summary"),
                BotCommand("analyze",   "Cognition snapshot"),
                BotCommand("proposals", "Last 5 proposal candidates"),
                BotCommand("show",      "Show candidate by id"),
                BotCommand("apply",     "Apply candidate by id"),
                BotCommand("reject",    "Reject candidate by id"),
                BotCommand("dreams",       "Pending dream insights"),
                BotCommand("apply_dream",  "Apply dream insight by id"),
                BotCommand("reject_dream", "Reject dream insight by id"),
                BotCommand("edit_proposals", "Pending soul section edits"),
                BotCommand("show_edit",    "Show soul edit diff by id"),
                BotCommand("apply_edit",   "Apply soul section edit by id"),
                BotCommand("reject_edit",  "Reject soul section edit by id"),
                BotCommand("train_proposals", "Pending training proposals"),
                BotCommand("approve_train", "Approve training proposal"),
                BotCommand("reject_train", "Reject training proposal"),
                BotCommand("adapter_status", "Current adapter info"),
                BotCommand("rollback_adapter", "Roll back to previous adapter"),
                BotCommand("pending",   "Pending actions"),
                BotCommand("trust",     "Trust user"),
                BotCommand("promote",   "Promote action type"),
                BotCommand("help",      "Grouped command list"),
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
        self._app.add_handler(CommandHandler("help", self._handle_help))
        self._app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message))

        logger.info("Telegram bot starting polling...")
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

    def send_message(self, text: str):
        """Send a message to the owner via Telegram. Safe to call from any thread.
        Auto-splits messages > 4000 chars on sentence boundaries."""
        if not self.enabled or not self._loop:
            return

        parts = split_long_message(text)
        if len(parts) > 1:
            logger.info("Telegram message split into %d parts", len(parts))

        async def _send_all():
            import asyncio as _a
            bot = Bot(token=self.token)
            for i, part in enumerate(parts):
                await bot.send_message(chat_id=self.authorized_user, text=part)
                if i < len(parts) - 1:
                    await _a.sleep(0.5)

        future = asyncio.run_coroutine_threadsafe(_send_all(), self._loop)
        try:
            future.result(timeout=30)
            logger.info("Telegram sent: %s (full %d chars)", text[:80], len(text))
        except Exception as e:
            logger.error("Telegram send failed: %s", e)
