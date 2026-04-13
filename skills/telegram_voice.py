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
        self._detect_and_queue_action(user_text, reply)
        from skills.followup_queue import FollowUpQueue
        followup_task = FollowUpQueue.extract_task(reply)
        if followup_task:
            FollowUpQueue().add(followup_task, user_text)
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
