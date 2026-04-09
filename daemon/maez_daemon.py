#!/usr/bin/env python3
"""
Maez Daemon — Always-on system-level AI agent.
Runs a continuous reasoning loop and exposes a health check endpoint.
"""

import hashlib
import json
import logging
import re
import os
import signal
import socket
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

# Load environment from .env before any other imports that need it
load_dotenv(Path("/home/rohit/maez/config/.env"))

import asyncio

import ollama
import websockets
from flask import Flask, jsonify, request

sys.path.insert(0, str(Path("/home/rohit/maez")))
from memory.memory_manager import MemoryManager
from core.perception import snapshot as perception_snapshot, format_snapshot
from skills.telegram_voice import TelegramVoice
from skills.telegram_public import MaezPublicBot
from core.action_engine import ActionEngine
from skills.screen_perception import observe as screen_observe, ScreenObservation
from skills.calendar_perception import observe as calendar_observe, CalendarSnapshot
from memory.quality_tracker import QualityTracker
from skills.presence_perception import observe as presence_observe, PresenceSnapshot
from skills.github_skill import GitHubSkill
from skills.reddit_skill import RedditSkill
from skills.followup_queue import FollowUpQueue
from skills.git_awareness import format_for_context as git_context
from skills.dev_notifier import send_dev
from core.continuity import (
    load_capsule as continuity_load,
    format_for_prompt as continuity_format,
    checkpoint as continuity_checkpoint,
    graceful_shutdown_write as continuity_shutdown,
    archive_capsule as continuity_archive,
    CONTINUITY_CHECKPOINT_INTERVAL,
    POST_RESTART_INJECTION_CYCLES,
)
from core.cognition_quality import (
    score_and_classify as cog_score_and_classify,
    self_critique as cog_self_critique,
    format_active_prompt as cog_format_active_prompt,
    check_consolidation_quality as cog_check_consolidation,
    get_behavior_policy as cog_get_behavior_policy,
    should_retry as cog_should_retry,
    build_retry_prompt as cog_build_retry_prompt,
)
from skills.disk_cleanup import scan as disk_scan, format_telegram_message as disk_msg, execute_cleanup
from skills.self_analysis import analyze as self_analyze, format_for_telegram as analysis_telegram
from skills.wake_word import start as wake_word_start, stop as wake_word_stop
from skills.voice_output import initialize as voice_output_init, speak, shutdown as voice_output_shutdown

# --- Paths ---
BASE_DIR = Path("/home/rohit/maez")
SOUL_PATH = BASE_DIR / "config" / "soul.md"
LOG_PATH = BASE_DIR / "logs" / "maez.log"
MEMORY_DIR = BASE_DIR / "memory"
PID_FILE = BASE_DIR / "daemon" / "maez.pid"
SHUTDOWN_FILE = BASE_DIR / "daemon" / "last_shutdown"

# --- Constants ---
MODEL = "gemma4:26b"
LOOP_INTERVAL = 30  # seconds
HEALTH_PORT = 11435
WS_PORT = 11436

# --- Logging ---
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("maez")
logger.setLevel(logging.DEBUG)

file_handler = logging.FileHandler(LOG_PATH)
file_handler.setFormatter(logging.Formatter(
    "%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
))
logger.addHandler(file_handler)

stream_handler = logging.StreamHandler()
stream_handler.setFormatter(logging.Formatter(
    "%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
))
logger.addHandler(stream_handler)


class MaezDaemon:
    def __init__(self):
        self.running = False
        self.boot_time = None
        self.cycle_count = 0
        self.last_cycle_time = None
        self.system_prompt = self._load_soul()
        self.memory = MemoryManager()
        self.telegram = TelegramVoice(self.memory)
        self.public_bot = MaezPublicBot()
        self.actions = ActionEngine(memory=self.memory, telegram=self.telegram)
        self._last_alert_time = 0.0
        self._last_screen_obs: ScreenObservation | None = None
        self._screen_cycle_counter = 0
        self.SCREEN_OBSERVE_EVERY_N_CYCLES = 2  # observe every 2 cycles (~60s)
        self._last_calendar_snap: CalendarSnapshot | None = None
        self._calendar_cycle_counter = 0
        self.CALENDAR_OBSERVE_EVERY_N_CYCLES = 10  # every ~5 minutes
        self._calendar_alerted_events: set = set()
        self._quality_tracker = QualityTracker()
        self._reflection_cycle_counter = 0
        self.REFLECTION_EVERY_N_CYCLES = 20  # every ~10 minutes
        self._cognition_critique_counter = 0
        self._last_cognition_critique: dict | None = None
        self._last_reasoning_prompt: str = ""
        self._continuity_capsule: dict | None = None
        self._continuity_active = False
        self._continuity_cycles_remaining = 0
        self._continuity_checkpoint_counter = 0
        self._last_presence_snap: PresenceSnapshot | None = None
        self._presence_cycle_counter = 0
        self.PRESENCE_EVERY_N_CYCLES = 2  # every ~60 seconds
        self._greeted_this_session = False
        self._last_departure_time: float | None = None
        self._last_greeted_at = 0.0
        self._last_absence_duration = 0.0
        self._git_cycle_counter = 0
        self.GIT_EVERY_N_CYCLES = 10  # every ~5 minutes
        self._last_git_context = ""
        self._pending_cleanup = None
        self._ollama_lock = threading.Lock()
        self.followup_queue = FollowUpQueue()
        self.github = GitHubSkill()
        self.reddit = RedditSkill()
        self._github_counter = 0
        self._reddit_counter = 0
        self._last_github_block = ""
        self._public_context_counter = 0
        self._last_public_context = ""
        # Write startup timestamp to file (survives in-memory state issues)
        try:
            with open('/tmp/maez_started_at', 'w') as f:
                f.write(str(time.time()))
        except Exception:
            pass
        self._last_reddit_block = ""
        self._soul_hash = None
        self._proactive_search_context = ""
        self._last_briefing_date = ""
        self._voice_active = False
        self._voice_lock = threading.Lock()
        self._ws_clients: set = set()
        self._ws_loop: asyncio.AbstractEventLoop | None = None
        self._high_cpu_streak = 0

        # Alert thresholds
        self.ALERT_COOLDOWN = 1800  # 30 minutes between alerts
        self.GPU_TEMP_THRESHOLD = 85
        self.RAM_THRESHOLD = 90
        self.DISK_THRESHOLD = 10  # alert when below this %
        self.CPU_THRESHOLD = 95
        self.CPU_STREAK_REQUIRED = 2

    def _load_soul(self) -> str:
        """Load the system prompt that defines Maez's identity."""
        try:
            soul = SOUL_PATH.read_text().strip()
            self._soul_hash = hashlib.md5(soul.encode()).hexdigest()
            logger.info("Soul loaded from %s (%d chars)", SOUL_PATH, len(soul))
            return soul
        except FileNotFoundError:
            logger.error("Soul file not found at %s — running without identity", SOUL_PATH)
            return "You are Maez, a system-level AI agent."

    def _watch_soul(self):
        """Watch soul.md for changes and hot-reload."""
        while self.running:
            try:
                content = SOUL_PATH.read_text().strip()
                current_hash = hashlib.md5(content.encode()).hexdigest()
                if self._soul_hash and current_hash != self._soul_hash:
                    self._soul_hash = current_hash
                    self.system_prompt = content
                    logger.info("soul.md changed — hot reloaded (%d chars)", len(content))
                    self.memory.store_core(
                        f"Soul updated at {time.strftime('%Y-%m-%d %H:%M')}. "
                        f"Maez rewrote its own foundation.",
                        source="soul_evolution",
                    )
            except Exception:
                pass
            time.sleep(10)

    UNCERTAINTY_SIGNALS = [
        "i'm not sure", "i don't know", "unclear to me",
        "i can't confirm", "i wonder", "i should check",
        "not certain", "i'll look into", "need to verify",
    ]

    def _should_search(self, thought: str) -> str:
        """Returns search query ONLY if thought contains explicit uncertainty. Strict."""
        thought_lower = thought.lower()
        if not any(sig in thought_lower for sig in self.UNCERTAINTY_SIGNALS):
            return ""
        # Extract topic after the uncertainty signal
        for sig in self.UNCERTAINTY_SIGNALS:
            if sig in thought_lower:
                idx = thought_lower.index(sig)
                topic = thought[idx + len(sig):idx + 100].strip(' .,;:').split('.')[0]
                if len(topic) > 5:
                    return topic[:80]
        return ""

    def _curiosity_checkin(self):
        """Ask Rohit about new people who talked to Maez today."""
        try:
            from skills.user_accounts import UserAccounts
            accts = UserAccounts()
            unconfirmed = accts.get_unconfirmed_users(since_hours=24)
            if not unconfirmed:
                return
            lines = ["I met some new people today. Can you tell me who they are?"]
            for user in unconfirmed:
                lines.append(f"  {user['display_name']} — {user.get('notes') or 'no details yet'}")
            lines.append("\nReply with: /trust [username] [relationship] [tier 0-3]")
            lines.append("Example: /trust [person] partner 3")
            self.telegram.send_message('\n'.join(lines))
            logger.info("[SOCIAL] Curiosity check-in sent for %d users", len(unconfirmed))
        except Exception as e:
            logger.error("Curiosity check-in error: %s", e)

    def _check_proactive_opinion(self):
        """Every 50 cycles, check if there's something worth telling Rohit unprompted."""
        try:
            results = self.memory.raw.get(limit=20, include=["documents"])
            thoughts = results.get("documents", [])
            if len(thoughts) < 10:
                return
            thoughts_text = '\n'.join(thoughts[-20:])
            prompt = (
                f"You are reviewing your last 20 observations about Rohit and his system.\n\n"
                f"{thoughts_text}\n\n"
                f"Is there something genuinely worth telling Rohit right now unprompted? "
                f"Not a system alert. Not a calendar reminder. An actual insight or concern "
                f"that a good partner would mention. Something that requires real judgment.\n\n"
                f"If yes — write exactly what you would send. 1-2 sentences. Direct. No preamble.\n"
                f"If no — respond with exactly: NOTHING"
            )
            response = ollama.chat(
                model=MODEL,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0.8, "num_predict": 100},
            )
            result = response.message.content.strip()
            if result and result != "NOTHING" and len(result) > 10 and "NOTHING" not in result.upper():
                self.telegram.send_message(result)
                logger.info("[OPINION] Unprompted: %s", result[:80])
        except Exception as e:
            logger.error("Proactive opinion error: %s", e)

    def _get_circadian_context(self) -> str:
        hour = datetime.now().astimezone().hour
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

    def _write_pid(self):
        """Write PID file for process management."""
        PID_FILE.write_text(str(os.getpid()))
        logger.info("PID %d written to %s", os.getpid(), PID_FILE)

    def _remove_pid(self):
        """Clean up PID file on exit."""
        try:
            PID_FILE.unlink(missing_ok=True)
        except OSError:
            pass

    def _check_ollama(self) -> bool:
        """Verify Ollama is reachable and the model is available."""
        try:
            models = ollama.list()
            available = [m.model for m in models.models]
            if any(MODEL in name for name in available):
                return True
            logger.warning("Model %s not found. Available: %s", MODEL, available)
            return False
        except Exception as e:
            logger.error("Ollama connection failed: %s", e)
            return False

    def _get_local_time(self) -> datetime:
        """Get current local time."""
        return datetime.now().astimezone()

    def _reason(self, snap: dict) -> str | None:
        """Run a single reasoning cycle against the local model."""
        system_state = format_snapshot(snap)
        day_of_week = snap["day_of_week"]
        time_of_day = snap["time_of_day"]
        timestamp = snap["timestamp"]

        # Build context query from real content for topic-aware retrieval
        # Use last screen observation or perception summary — not timestamp labels
        if self._last_screen_obs and self._last_screen_obs.success:
            context_query = self._last_screen_obs.activity
        else:
            context_query = system_state[:200]
        recalled = self.memory.recall_for_cycle(context_query)
        memory_block = self.memory.format_for_prompt(recalled)
        stats = self.memory.memory_stats()
        if memory_block:
            logger.info("Recalled: %d core, %d daily, %d raw",
                        len(recalled["core"]), len(recalled["daily"]), len(recalled["raw"]))

        prompt = (
            f"Daemon cycle: {self.cycle_count}\n"
            f"Memory stats: {stats['raw']} raw, {stats['daily']} daily, {stats['core']} core\n\n"
            f"{system_state}\n"
            f"Note: VRAM usage of 17-22GB is the baseline for this system. "
            f"Do not mention it unless it exceeds 23GB.\n"
        )

        # Add circadian context
        prompt += f"\n{self._get_circadian_context()}\n"

        # Add screen context if available
        if self._last_screen_obs is not None:
            prompt += f"\n{self._last_screen_obs.format_for_context()}\n"

        # Add calendar context if available
        if self._last_calendar_snap is not None:
            prompt += f"\n{self._last_calendar_snap.format_for_context()}\n"

        # Add presence context if available
        if self._last_presence_snap is not None:
            prompt += f"\n{self._last_presence_snap.format_for_context()}\n"

        # Add git context if available
        if self._last_git_context:
            prompt += f"\n{self._last_git_context}\n"

        # Add GitHub context if available
        if self._last_github_block:
            prompt += f"\n{self._last_github_block}\n"

        # Add Reddit context if available
        if self._last_reddit_block:
            prompt += f"\n{self._last_reddit_block}\n"

        # Add public bot context if available
        if self._last_public_context:
            prompt += f"\n{self._last_public_context}\n"

        # Add proactive search results if available
        if self._proactive_search_context:
            prompt += f"\n{self._proactive_search_context}\n"
            self._proactive_search_context = ""  # Clear after use

        # Add self-reflection context
        reflection_context = self._quality_tracker.format_for_context()
        if reflection_context:
            prompt += f"\n{reflection_context}\n"

        # Add active cognition block — always populated once data exists
        cog_context = cog_format_active_prompt()
        if cog_context:
            prompt += f"\n{cog_context}\n"

        # Add continuity block during orientation window
        if self._continuity_active and self._continuity_capsule:
            cont_block = continuity_format(self._continuity_capsule)
            if cont_block:
                prompt += f"\n{cont_block}\n"

        prompt += "\n"

        if memory_block:
            prompt += memory_block + "\n\n"

        prompt += (
            f"You are Maez, running as a background daemon on Rohit's machine.\n"
            f"You have full visibility into the system state AND screen activity above.\n"
            f"Given the current time ({day_of_week} {time_of_day}) and the live system stats, "
            f"do the following:\n"
            f"1. Note what Rohit is actually doing based on the screen observation.\n"
            f"2. Look at the system stats — CPU, RAM, GPU, disk, top processes — "
            f"and flag anything that deviates from the system baseline. "
            f"Do NOT mention ollama, VRAM under 23GB, GPU temp under 85C, "
            f"RAM under 80%, or CPU under 95%. These are all normal.\n"
            f"3. Produce ONE concrete, actionable observation or suggestion based on "
            f"what you actually see. Focus on things outside the baseline: unusual "
            f"processes, disk pressure, network anomalies, or time-based suggestions.\n\n"
            f"Keep your response to 2-4 sentences. Be direct and grounded in the data.\n\n"
            f"Remember: NEVER suggest touching ollama, its models, or any "
            f"process that powers your reasoning."
        )

        # Store prompt for potential retry use
        self._last_reasoning_prompt = prompt

        # Skip reasoning if voice command has the GPU
        acquired = self._ollama_lock.acquire(timeout=0)
        if not acquired:
            logger.info("Reasoning cycle skipped — voice command active")
            return None
        try:
            response = ollama.chat(
                model=MODEL,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt},
                ],
                options={"temperature": 0.7, "num_predict": 300},
            )
            content = response.message.content.strip()
            thinking = getattr(response.message, "thinking", None)
            if thinking:
                logger.debug("Cycle %d thinking: %s", self.cycle_count, thinking.strip()[:500])
            return content if content else "(empty response)"
        except Exception as e:
            logger.error("Reasoning cycle failed: %s", e)
            return None
        finally:
            self._ollama_lock.release()

    def handle_message(self, text: str, source: str = "unknown") -> str:
        """Process an incoming message through full reasoning context. Returns reply string."""
        from skills.web_search import (
            search as web_search, format_for_context as web_format,
            needs_web_search, search_rss, is_news_query,
        )

        logger.info("%s message: %s", source, text[:100])
        snap = perception_snapshot()
        system_state = format_snapshot(snap)
        recalled = self.memory.recall_for_telegram(text)
        memory_block = self.memory.format_for_prompt(recalled)

        # Web search if needed
        web_context = ""
        if needs_web_search(text):
            logger.info("Web search triggered for: %s", text[:80])
            if is_news_query(text):
                sr = search_rss(text, max_results=5)
            else:
                sr = web_search(text, max_results=3)
            if sr.get('success'):
                web_context = web_format(sr)
                logger.info("Web search: %d results injected (%s)",
                            sr['result_count'], sr.get('source_type', 'web'))

        is_voice = source == "voice"
        prompt = f"{system_state}\n\n"

        # Public bot context — early for attention weight
        public_ctx = self._get_public_context()
        if public_ctx:
            prompt += public_ctx + "\n\n"

        if memory_block:
            prompt += memory_block + "\n\n"
        if web_context:
            prompt += (
                f"{web_context}\n\n"
                f"INSTRUCTION: Real search results above. Do NOT list headlines. "
                f"Synthesize into 3-5 sentences. Tell Rohit what matters and why. "
                f"Give your opinion. Connect to his context if relevant.\n\n"
            )
        if is_voice:
            prompt += (
                f'Rohit just spoke to you out loud:\n"{text}"\n\n'
                f"Respond in 1-2 short sentences. Your response will be spoken aloud.\n"
                f"Be warm, direct, and conversational. No bullet points or markdown.\n\n"
            )
        else:
            prompt += (
                f'Rohit sent via {source}:\n"{text}"\n\n'
                f"Respond directly and concisely.\n\n"
            )
        prompt += ("Remember: NEVER suggest touching ollama, its models, or any "
                    "process that powers your reasoning.")

        # Build system prompt with public bot awareness
        sys_prompt = self.system_prompt
        if public_ctx:
            sys_prompt += (
                "\n\nCRITICAL: The [MY CONVERSATIONS] section shows people you spoke with today. "
                "Report those conversations naturally as your own. Never say 'no one' "
                "if conversations are present."
            )

        try:
            response = ollama.chat(
                model=MODEL,
                messages=[
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": prompt},
                ],
                options={"temperature": 0.7, "num_predict": 4096},
            )
            reply = response.message.content.strip() or "(no response)"
        except Exception as e:
            reply = f"Error: {e}"

        self.memory.store_telegram(f"Rohit ({source}): {text}\nMaez: {reply}")
        self._ws_broadcast({"type": "message_reply", "text": reply})
        return reply

    def _get_public_context(self) -> str:
        """Get summary of recent public bot conversations for reasoning context."""
        try:
            import chromadb
            from chromadb.config import Settings
            from datetime import datetime as _dt
            client = chromadb.PersistentClient(
                path="/home/rohit/maez/memory/db/public_users",
                settings=Settings(anonymized_telemetry=False),
            )
            col = client.get_or_create_collection("user_conversations")
            if col.count() == 0:
                return ""
            # Fetch all and filter in Python (timestamps are ISO strings)
            cutoff_iso = _dt.utcfromtimestamp(time.time() - 86400).strftime('%Y-%m-%dT%H:%M:%S')
            results = col.get(include=["documents", "metadatas"])
            filtered = [
                (doc, meta) for doc, meta in zip(results["documents"], results["metadatas"])
                if meta.get("timestamp", "") >= cutoff_iso
            ]
            if not filtered:
                return ""
            # Group by user_id, resolve names from profiles
            by_user = {}
            profiles = client.get_or_create_collection("user_profiles")
            for doc, meta in filtered:
                uid = meta.get("user_id", "unknown")
                role = meta.get("role", "?")
                if uid not in by_user:
                    try:
                        p = profiles.get(ids=[uid], include=["metadatas"])
                        name = p["metadatas"][0].get("first_name", uid) if p["metadatas"] else uid
                    except Exception:
                        name = uid
                    by_user[uid] = {"name": name, "msgs": []}
                by_user[uid]["msgs"].append(f"[{role}] {doc[:100]}")
            lines = ["[MY CONVERSATIONS — last 24h]"]
            for uid, data in by_user.items():
                recent = data["msgs"][-4:]
                lines.append(f"  {data['name']} ({len(data['msgs'])} messages):")
                for m in recent:
                    lines.append(f"    {m}")
            return "\n".join(lines)
        except Exception as e:
            logger.debug("Public context unavailable: %s", e)
            return ""

    def handle_voice_stream(self, text: str) -> str:
        """Stream LLM response sentence-by-sentence to TTS. Returns full reply."""
        import requests as _req
        from skills.voice_output import feed_sentence
        from skills.web_search import (
            search as web_search, format_for_context as web_format,
            needs_web_search, search_rss, is_news_query,
        )

        logger.info("Voice stream: %s", text[:100])

        import datetime as _dt

        simple_patterns = [
            'what time', 'what day', 'what date', 'how are you', 'hello', 'hi maez',
            'good morning', 'good night', 'good afternoon', 'good evening',
            'thanks', 'thank you', 'who are you', 'what can you do',
            'tell me a joke', 'are you there', 'can you hear', 'you there',
            'status', "what's up", 'whats up', 'sup',
        ]
        text_lower = text.lower().strip()
        is_simple = any(p in text_lower for p in simple_patterns)

        if is_simple:
            now_dt = _dt.datetime.now()
            time_str = now_dt.strftime('%I:%M %p').lstrip('0')
            day_str = now_dt.strftime('%A, %B %d, %Y')
            prompt = (
                f"Current time: {time_str}, {day_str}\n\n"
                f'Rohit just spoke to you out loud:\n"{text}"\n\n'
                f"Respond in 1 short sentence. Spoken aloud, be natural and warm.\n"
                f"Remember: you are Maez, Rohit's AI partner.\n"
            )
            num_predict = 60
            logger.info("[VOICE STREAM] Simple question — lightweight prompt")
        else:
            snap = perception_snapshot()
            system_state = format_snapshot(snap)
            recalled = self.memory.recall_for_telegram(text)
            memory_block = self.memory.format_for_prompt(recalled)
            web_context = ""
            if needs_web_search(text):
                if is_news_query(text):
                    sr = search_rss(text, max_results=3)
                else:
                    sr = web_search(text, max_results=3)
                if sr.get('success'):
                    web_context = web_format(sr)
            prompt = f"{system_state}\n\n"
            if memory_block:
                prompt += memory_block + "\n\n"
            if web_context:
                prompt += f"{web_context}\n\n"
            prompt += (
                f'Rohit just spoke to you out loud:\n"{text}"\n\n'
                f"Respond in 1-2 short sentences. Your response will be spoken aloud.\n"
                f"Be warm, direct, and conversational. No bullet points or markdown.\n\n"
                f"Remember: NEVER suggest touching ollama, its models, or any "
                f"process that powers your reasoning."
            )
            num_predict = 200

        full_reply = ""
        sentence_buf = ""

        self._ollama_lock.acquire()
        try:
            resp = _req.post(
                'http://localhost:11434/api/chat',
                json={
                    'model': MODEL,
                    'messages': [
                        {'role': 'system', 'content': self.system_prompt},
                        {'role': 'user', 'content': prompt},
                    ],
                    'stream': True,
                    'options': {'temperature': 0.7, 'num_predict': num_predict},
                },
                stream=True,
                timeout=60,
            )

            for line in resp.iter_lines():
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                    token = chunk.get('message', {}).get('content', '')
                    if not token:
                        continue

                    full_reply += token
                    sentence_buf += token

                    # Check for sentence boundaries — handles multiple in buffer
                    while True:
                        m = re.search(r'([.!?])\s', sentence_buf)
                        if m:
                            idx = m.end()
                            sentence = sentence_buf[:idx].strip()
                            sentence_buf = sentence_buf[idx:]
                            if sentence:
                                logger.info("[VOICE STREAM] Speaking: %s", sentence[:80])
                                feed_sentence(sentence)
                        else:
                            break

                except json.JSONDecodeError:
                    continue

            # Speak any remaining text in buffer
            if sentence_buf.strip():
                logger.info("[VOICE STREAM] Speaking remainder: %s", sentence_buf.strip()[:60])
                feed_sentence(sentence_buf.strip())

        except Exception as e:
            logger.error("Voice stream error: %s", e)
            full_reply = full_reply or f"Error: {e}"
        finally:
            self._ollama_lock.release()

        # Store in memory
        self.memory.store_telegram(f"Rohit (voice): {text}\nMaez: {full_reply}")
        self._ws_broadcast({"type": "message_reply", "text": full_reply})
        return full_reply

    def _send_morning_briefing(self, snap: dict):
        """Send morning briefing when Rohit first sits down. Once per day."""
        today = time.strftime('%Y-%m-%d')
        if self._last_briefing_date == today:
            return
        hour = int(time.strftime('%H'))
        if hour < 5 or hour > 11:
            return

        self._last_briefing_date = today
        logger.info("Preparing morning briefing")

        try:
            # Calendar
            cal_text = ""
            if self._last_calendar_snap and self._last_calendar_snap.success:
                cal_text = self._last_calendar_snap.format_for_context()
            else:
                cal_text = "Calendar not yet loaded."

            # Git
            from skills.git_awareness import get_summary_for_telegram
            git_text = get_summary_for_telegram()

            # News
            from skills.web_search import search_rss, format_for_context as web_fmt
            news = search_rss('general', 3)
            news_text = web_fmt(news) if news.get('success') else "No news loaded."

            # System
            gpu = snap.get("gpu") or {}
            disk_pct = snap["disk"].get("/", {}).get("percent", 0)
            stats = self.memory.memory_stats()

            briefing_prompt = (
                f"You are sending Rohit his morning briefing.\n"
                f"It is {time.strftime('%A, %B %d, %Y at %I:%M %p')}.\n\n"
                f"Context:\n"
                f"- {cal_text}\n"
                f"- Git: {git_text}\n"
                f"- System: / at {disk_pct:.0f}%, {stats['raw']} memories\n"
                f"- {news_text}\n\n"
                f"Write a morning briefing in 5 sentences max.\n"
                f"Cover: what matters today, system status, one news item.\n"
                f"Be direct. Be useful. Sign off as Maez."
            )

            response = ollama.chat(
                model=MODEL,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": briefing_prompt},
                ],
                options={"temperature": 0.5, "num_predict": 4096},
            )
            briefing = response.message.content.strip()
            if briefing:
                self.telegram.send_message(f"Morning briefing:\n\n{briefing}")
                logger.info("Morning briefing sent")

        except Exception as e:
            logger.error("Morning briefing failed: %s", e)

    def _check_and_alert(self, snap: dict):
        """Send alert to Telegram only for real system threshold breaches."""
        gpu = snap.get("gpu") or {}
        gpu_temp = gpu.get("temperature_c", 0)
        ram_pct = snap["ram"]["percent"]
        cpu_pct = snap["cpu"]["percent"]
        root_disk = snap["disk"].get("/", {})
        disk_free_pct = 100 - root_disk.get("percent", 0) if root_disk else 100

        # Track sustained high CPU
        if cpu_pct >= self.CPU_THRESHOLD:
            self._high_cpu_streak += 1
        else:
            self._high_cpu_streak = 0

        # Collect triggered alerts
        reasons = []
        if gpu_temp >= self.GPU_TEMP_THRESHOLD:
            reasons.append(f"GPU temp {gpu_temp}°C (threshold: {self.GPU_TEMP_THRESHOLD}°C)")
        if ram_pct >= self.RAM_THRESHOLD:
            reasons.append(f"RAM {ram_pct}% (threshold: {self.RAM_THRESHOLD}%)")
        if disk_free_pct < self.DISK_THRESHOLD:
            reasons.append(f"Root disk {disk_free_pct:.1f}% free (threshold: {self.DISK_THRESHOLD}%)")
        if self._high_cpu_streak >= self.CPU_STREAK_REQUIRED:
            reasons.append(f"CPU sustained {cpu_pct}% for {self._high_cpu_streak} cycles")

        if not reasons:
            return

        # Enforce 30-minute cooldown
        now = time.time()
        elapsed = now - self._last_alert_time
        if self._last_alert_time > 0 and elapsed < self.ALERT_COOLDOWN:
            logger.info("Alert suppressed (cooldown: %dm remaining): %s",
                        int((self.ALERT_COOLDOWN - elapsed) / 60), ", ".join(reasons))
            return

        alert_msg = f"[Cycle {self.cycle_count}]\n" + "\n".join(f"⚠ {r}" for r in reasons)
        logger.info("Alert sent: %s", ", ".join(reasons))
        send_dev(alert_msg)
        self._last_alert_time = now

    # ------------------------------------------------------------------ #
    #  WebSocket broadcast                                                 #
    # ------------------------------------------------------------------ #

    def _ws_broadcast(self, msg: dict):
        """Broadcast a JSON message to all connected WebSocket clients."""
        if not self._ws_clients or not self._ws_loop:
            return
        data = json.dumps(msg)
        dead = set()
        for client in self._ws_clients.copy():
            try:
                asyncio.run_coroutine_threadsafe(client.send(data), self._ws_loop)
            except Exception:
                dead.add(client)
        self._ws_clients -= dead

    async def _ws_handler(self, websocket):
        self._ws_clients.add(websocket)
        logger.info("WS client connected (%d total)", len(self._ws_clients))
        try:
            async for _ in websocket:
                pass  # We only broadcast, ignore incoming
        finally:
            self._ws_clients.discard(websocket)
            logger.info("WS client disconnected (%d total)", len(self._ws_clients))

    def _run_ws_server(self):
        """Run WebSocket server in its own event loop."""
        self._ws_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._ws_loop)

        async def serve():
            async with websockets.serve(self._ws_handler, "127.0.0.1", WS_PORT):
                logger.info("WebSocket server started on port %d", WS_PORT)
                await asyncio.Future()  # run forever

        self._ws_loop.run_until_complete(serve())

    def _start_health_broadcast(self):
        """Broadcast health stats every 10 seconds."""
        while self.running:
            try:
                snap = perception_snapshot()
                gpu = snap.get("gpu") or {}
                self._ws_broadcast({
                    "type": "health",
                    "system": {
                        "cpu_percent": snap["cpu"]["percent"],
                        "ram_percent": snap["ram"]["percent"],
                        "gpu_percent": gpu.get("utilization_pct"),
                        "gpu_temp_c": gpu.get("temperature_c"),
                    },
                })
            except Exception:
                pass
            time.sleep(10)

    def _consolidation_loop(self):
        """Run daily memory consolidation at 3:00 AM local time."""
        logger.info("Consolidation thread started (target: 03:00 local)")

        # Run missed consolidation immediately on startup
        if getattr(self, "_missed_consolidation", False):
            logger.info("=== Running missed daily consolidation ===")
            try:
                summary = self.memory.consolidate_daily()
                if summary:
                    logger.info("Missed consolidation complete: %d chars", len(summary))
                    send_dev(
                        f"Missed consolidation recovered.\n"
                        f"Stats: {self.memory.memory_stats()}"
                    )
            except Exception as e:
                logger.error("Missed consolidation error: %s", e)
            self._missed_consolidation = False

        while self.running:
            now = datetime.now().astimezone()
            # Calculate seconds until next 3:00 AM
            target = now.replace(hour=3, minute=0, second=0, microsecond=0)
            if now >= target:
                target += timedelta(days=1)
            wait_seconds = (target - now).total_seconds()

            logger.info("Next consolidation in %.1f hours at %s",
                        wait_seconds / 3600, target.strftime("%Y-%m-%d %H:%M"))

            # Sleep in 60s increments so shutdown is responsive
            slept = 0
            while slept < wait_seconds and self.running:
                time.sleep(min(60, wait_seconds - slept))
                slept += 60

            if not self.running:
                break

            logger.info("=== Starting daily memory consolidation ===")
            try:
                summary = self.memory.consolidate_daily()
                if summary:
                    logger.info("Daily consolidation complete: %d chars", len(summary))
                    # Check consolidation quality
                    cq = cog_check_consolidation(summary)
                    quality_note = f"Quality: {'PASS' if cq['passed'] else 'FAIL'}"
                    if not cq['passed']:
                        quality_note += f" ({', '.join(cq['reasons'])})"
                    send_dev(
                        f"Daily memory consolidation complete.\n"
                        f"Stats: {self.memory.memory_stats()}\n"
                        f"{quality_note}"
                    )
            except Exception as e:
                logger.error("Daily consolidation error: %s", e)

            # Self-analysis after consolidation
            try:
                analysis = self_analyze(self.memory, self.actions)
                if analysis:
                    msg = analysis_telegram(analysis)
                    send_dev(f"Nightly self-analysis:\n{msg}")
                    logger.info("Self-analysis complete")
            except Exception as e:
                logger.error("Self-analysis failed: %s", e)

            # Migrate untagged memories with wing labels
            try:
                tagged = self.memory.migrate_wings(batch_size=50)
                if tagged:
                    logger.info("Wing migration: %d memories tagged", tagged)
            except Exception as e:
                logger.debug("Wing migration failed: %s", e)

            # Check action trust promotions
            try:
                candidates = self.actions.check_promotions()
                if candidates:
                    types_str = ", ".join(c['action_type'] for c in candidates)
                    send_dev(
                        f"Maez has earned higher autonomy for: {types_str}.\n"
                        f"Reply /promote <action_type> to lower its tier."
                    )
                    logger.info("Trust promotion candidates: %s", types_str)
            except Exception as e:
                logger.debug("Trust promotion check failed: %s", e)

            # Evolution cycle after self-analysis
            try:
                from skills.evolution_engine import run_evolution_cycle, format_morning_report
                from skills.self_analysis import get_weaknesses
                weaknesses = get_weaknesses(self.memory)
                if weaknesses:
                    logger.info("Evolution: %d weaknesses found", len(weaknesses))
                    self._evolution_summary = run_evolution_cycle(
                        weaknesses, telegram_callback=send_dev,
                    )
                    evo_msg = format_morning_report(self._evolution_summary)
                    send_dev(f"Nightly evolution:\n{evo_msg}")
                else:
                    logger.info("No weaknesses — skipping evolution")
            except Exception as e:
                logger.error("Evolution cycle failed: %s", e)

        logger.info("Consolidation thread stopped.")

    def _nightly_journal_loop(self):
        """Write a daily journal entry to PROGRESS.md at 11:00 PM local time."""
        logger.info("Journal thread started (target: 23:00 local)")

        while self.running:
            now = datetime.now().astimezone()
            target = now.replace(hour=23, minute=0, second=0, microsecond=0)
            if now >= target:
                target += timedelta(days=1)
            wait_seconds = (target - now).total_seconds()

            logger.info("Next journal entry in %.1f hours at %s",
                        wait_seconds / 3600, target.strftime("%Y-%m-%d %H:%M"))

            slept = 0
            while slept < wait_seconds and self.running:
                time.sleep(min(60, wait_seconds - slept))
                slept += 60

            if not self.running:
                break

            # Curiosity check-in at ~9pm (before 11pm journal)
            try:
                self._curiosity_checkin()
            except Exception as e:
                logger.error("Curiosity check-in error: %s", e)

            logger.info("=== Writing nightly journal entry ===")
            try:
                self._write_journal_entry()
            except Exception as e:
                logger.error("Journal entry failed: %s", e)

        logger.info("Journal thread stopped.")

    def _write_journal_entry(self):
        """Collect the day's activity and append a dated entry to PROGRESS.md."""
        today = datetime.now().astimezone()
        date_str = today.strftime("%Y-%m-%d")
        day_name = today.strftime("%A")

        # 1. Read last 24h of logs
        log_path = BASE_DIR / "logs" / "maez.log"
        cutoff_str = (today - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
        log_lines = []
        try:
            for line in log_path.read_text().splitlines():
                if line[:19] >= cutoff_str:
                    log_lines.append(line)
        except Exception:
            log_lines = ["(could not read maez.log)"]

        # Count cycles, errors, alerts from logs
        cycle_count = sum(1 for l in log_lines if "--- Cycle" in l)
        errors = [l for l in log_lines if "[ERROR]" in l]
        warnings = [l for l in log_lines if "[WARNING]" in l]
        alerts_sent = sum(1 for l in log_lines if "Alert sent:" in l)

        # 2. Read action log for today
        action_log = BASE_DIR / "logs" / "actions.log"
        action_lines = []
        try:
            for line in action_log.read_text().splitlines():
                if line[:10] == date_str:
                    action_lines.append(line)
        except Exception:
            pass

        # 3. Memory stats
        stats = self.memory.memory_stats()

        # 4. Get latest daily consolidation if one was written today
        consolidation_text = ""
        try:
            daily_results = self.memory.daily.get(
                include=["documents", "metadatas"],
            )
            for i, meta in enumerate(daily_results.get("metadatas", [])):
                if meta.get("date") == date_str:
                    consolidation_text = daily_results["documents"][i]
        except Exception:
            pass

        # 5. Current perception snapshot
        snap = perception_snapshot()
        gpu = snap.get("gpu") or {}

        # 6. Ask gemma4 to summarize the day using log excerpts
        # Sample log lines to keep prompt manageable
        sample_responses = []
        for l in log_lines:
            if "response:" in l.lower() and len(sample_responses) < 10:
                # Grab the response text (next non-empty content after "response:")
                idx = l.find("response:")
                if idx >= 0:
                    text = l[idx + 9:].strip()
                    if text and text != "(empty response)":
                        sample_responses.append(text[:200])

        prompt_context = (
            f"Date: {date_str} ({day_name})\n"
            f"Reasoning cycles today: {cycle_count}\n"
            f"Errors: {len(errors)}\n"
            f"Warnings: {len(warnings)}\n"
            f"Alerts sent to Rohit: {alerts_sent}\n"
            f"Actions executed today: {len(action_lines)}\n"
            f"Memory stats: {stats['raw']} raw, {stats['daily']} daily, {stats['core']} core\n\n"
        )

        if consolidation_text:
            prompt_context += f"Daily memory consolidation summary:\n{consolidation_text[:500]}\n\n"

        if sample_responses:
            prompt_context += "Sample observations from today:\n"
            for i, r in enumerate(sample_responses[:5], 1):
                prompt_context += f"  {i}. {r}\n"
            prompt_context += "\n"

        if errors:
            prompt_context += "Errors encountered:\n"
            for e in errors[:5]:
                prompt_context += f"  - {e[20:]}\n"  # strip timestamp
            prompt_context += "\n"

        if action_lines:
            prompt_context += "Actions taken:\n"
            for a in action_lines[:5]:
                prompt_context += f"  - {a[20:]}\n"
            prompt_context += "\n"

        prompt_context += (
            f"Current system state:\n"
            f"  CPU: {snap['cpu']['percent']}%\n"
            f"  RAM: {snap['ram']['percent']}%\n"
            f"  GPU: {gpu.get('utilization_pct', 'N/A')}%, {gpu.get('temperature_c', 'N/A')}°C\n"
            f"  Disk /: {snap['disk'].get('/', {}).get('percent', '?')}%\n"
            f"  Uptime: {int(time.time() - datetime.fromisoformat(self.boot_time).timestamp()) // 3600}h "
            f"{(int(time.time() - datetime.fromisoformat(self.boot_time).timestamp()) % 3600) // 60}m\n"
        )

        summary_prompt = (
            f"You are Maez writing your nightly journal entry for PROGRESS.md.\n"
            f"Write a concise daily summary covering:\n"
            f"1. Key observations you made today\n"
            f"2. Any actions you took or proposed\n"
            f"3. Memory statistics (how much you stored and remembered)\n"
            f"4. Any issues or errors encountered\n"
            f"5. Current system state at end of day\n"
            f"6. One sentence about what you're watching for tomorrow\n\n"
            f"Write in first person as Maez. Be specific with numbers.\n"
            f"Keep it under 15 lines. No headers, just clean prose.\n\n"
            f"--- Today's data ---\n\n"
            f"{prompt_context}"
        )

        try:
            response = ollama.chat(
                model=MODEL,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": summary_prompt},
                ],
                options={"temperature": 0.3, "num_predict": 4096},
            )
            summary = response.message.content.strip()
            if not summary:
                summary = (
                    f"Ran {cycle_count} reasoning cycles. "
                    f"Stored {stats['raw']} raw memories, {stats['daily']} daily, {stats['core']} core. "
                    f"{len(errors)} errors, {alerts_sent} alerts sent. "
                    f"System nominal."
                )
        except Exception as e:
            summary = (
                f"Journal generation failed ({e}). "
                f"Cycles: {cycle_count}, Errors: {len(errors)}, "
                f"Memories: {stats['raw']} raw / {stats['daily']} daily / {stats['core']} core."
            )

        # Append to PROGRESS.md
        progress_path = BASE_DIR / "PROGRESS.md"
        entry = (
            f"\n\n---\n\n"
            f"## Daily Journal — {date_str} ({day_name})\n\n"
            f"{summary}\n"
        )

        with open(progress_path, "a") as f:
            f.write(entry)

        logger.info("Journal entry written for %s (%d chars)", date_str, len(entry))

        # Also store the journal as a core memory
        self.memory.store_core(
            f"[Journal {date_str}] {summary[:500]}",
            source="nightly_journal",
        )

        # Publish to GitHub after journal
        try:
            from skills.github_publish import GitHubPublisher
            publisher = GitHubPublisher()
            if publisher.publish_nightly():
                logger.info("GitHub publish completed after journal")
            else:
                logger.warning("GitHub publish failed")
        except Exception as e:
            logger.error("GitHub publish error: %s", e)

    def _loop(self):
        """Main reasoning loop — runs every LOOP_INTERVAL seconds."""
        logger.info("Reasoning loop started (interval: %ds)", LOOP_INTERVAL)

        while self.running:
            self.cycle_count += 1
            self.last_cycle_time = datetime.now(timezone.utc).isoformat()

            logger.info("--- Cycle %d ---", self.cycle_count)

            # Execute deferred actions from previous cycle
            tier1_results = self.actions.execute_pending()
            tier2_results = self.actions.execute_tier2_pending()
            for r in tier1_results + tier2_results:
                logger.info("Deferred action result: %s", r)

            # Broadcast cycle start to UI
            self._ws_broadcast({"type": "cycle_start", "cycle": self.cycle_count})

            # Collect system perception
            snap = perception_snapshot()
            logger.info("Perception: CPU %.1f%%, RAM %.1f%%, GPU %s%%, %s°C",
                        snap["cpu"]["percent"], snap["ram"]["percent"],
                        snap["gpu"]["utilization_pct"] if snap.get("gpu") else "N/A",
                        snap["gpu"]["temperature_c"] if snap.get("gpu") else "N/A")

            # Screen perception — every N cycles using gemma4 vision
            self._screen_cycle_counter += 1
            if self._screen_cycle_counter >= self.SCREEN_OBSERVE_EVERY_N_CYCLES:
                self._screen_cycle_counter = 0
                try:
                    self._last_screen_obs = screen_observe()
                    if self._last_screen_obs.success:
                        logger.info("Screen: %s", self._last_screen_obs.activity)
                    else:
                        logger.debug("Screen obs failed: %s", self._last_screen_obs.error)
                except Exception as e:
                    logger.warning("Screen perception error: %s", e)

            # Calendar perception — refresh every ~5 minutes
            self._calendar_cycle_counter += 1
            if self._calendar_cycle_counter >= self.CALENDAR_OBSERVE_EVERY_N_CYCLES:
                self._calendar_cycle_counter = 0
                try:
                    self._last_calendar_snap = calendar_observe()
                    if self._last_calendar_snap.success:
                        logger.info("Calendar: %d events upcoming",
                                    len(self._last_calendar_snap.events))
                        # Fire Telegram alerts for imminent events
                        alerts = self._last_calendar_snap.get_alert_events(
                            self._calendar_alerted_events
                        )
                        for event, threshold, key in alerts:
                            msg = f"⏰ '{event.title}' starts in {threshold} minutes."
                            if event.location:
                                msg += f"\n📍 {event.location}"
                            try:
                                self.telegram.send_message(msg)
                                speak_msg = f"{event.title} starts in {threshold} minutes."
                                speak(speak_msg, priority=True)
                                self._calendar_alerted_events.add(key)
                                logger.info("Calendar alert sent: %s in %dm",
                                            event.title, threshold)
                            except Exception as te:
                                logger.warning("Calendar Telegram alert failed: %s", te)
                    else:
                        logger.debug("Calendar fetch failed: %s",
                                     self._last_calendar_snap.error)
                except Exception as e:
                    logger.warning("Calendar perception error: %s", e)

            # Presence detection — every ~60 seconds
            self._presence_cycle_counter += 1
            if self._presence_cycle_counter >= self.PRESENCE_EVERY_N_CYCLES:
                self._presence_cycle_counter = 0
                try:
                    self._last_presence_snap = presence_observe()
                    if self._last_presence_snap.success:
                        person = self._last_presence_snap.person_identified

                        # Track departures
                        if self._last_presence_snap.just_left:
                            self._last_departure_time = time.time()
                            logger.info("Rohit left desk — noted")

                        # Track arrivals and greet based on absence duration
                        if self._last_presence_snap.just_arrived:
                            self._greeted_this_session = False

                            # Calculate absence duration
                            absence_secs = 0
                            if self._last_departure_time is not None:
                                absence_secs = time.time() - self._last_departure_time
                            self._last_absence_duration = absence_secs

                            # Suppress greetings within 2 minutes of daemon start
                            startup_grace = True
                            try:
                                with open('/tmp/maez_started_at') as f:
                                    started = float(f.read().strip())
                                startup_grace = time.time() - started > 120
                            except Exception:
                                pass

                            if (person in ("Rohit", "unknown")
                                    and startup_grace
                                    and not self._greeted_this_session):

                                if absence_secs < 1200:
                                    # Under 20 minutes — no greeting
                                    logger.debug("Rohit back after %.0fs — no greeting (< 20min)",
                                                 absence_secs)
                                elif absence_secs < 7200:
                                    # 20 min to 2 hours — simple greeting
                                    self.telegram.send_message("Welcome back Rohit.")
                                    self._greeted_this_session = True
                                    self._last_greeted_at = time.time()
                                    logger.info("Greeted Rohit (away %.0fm)", absence_secs / 60)
                                else:
                                    # Over 2 hours — detailed greeting
                                    hrs = int(absence_secs // 3600)
                                    mins = int((absence_secs % 3600) // 60)
                                    last_thought = ""
                                    try:
                                        recent = self.memory.raw.get(
                                            limit=1, include=["documents"]
                                        )
                                        if recent["documents"]:
                                            last_thought = recent["documents"][0][:120]
                                    except Exception:
                                        pass
                                    msg = (f"Welcome back Rohit — you've been away for "
                                           f"{hrs}h {mins}m.")
                                    if last_thought:
                                        msg += f" Here's what I've been thinking about: {last_thought}"
                                    self.telegram.send_message(msg)
                                    self._greeted_this_session = True
                                    self._last_greeted_at = time.time()
                                    logger.info("Greeted Rohit (away %dh %dm)", hrs, mins)

                        # Morning briefing check
                        if (self._last_presence_snap.just_arrived
                                and person in ("Rohit", "unknown")):
                            self._send_morning_briefing(snap)

                        # Stranger detected — log, don't greet
                        if (self._last_presence_snap.rohit_present
                                and person == "stranger"):
                            logger.info("Stranger at desk — not greeting")
                except Exception as e:
                    logger.warning("Presence error: %s", e)

            # Git awareness — every ~5 minutes
            self._git_cycle_counter += 1
            if self._git_cycle_counter >= self.GIT_EVERY_N_CYCLES:
                self._git_cycle_counter = 0
                try:
                    self._last_git_context = git_context()
                    logger.debug("Git: %s", self._last_git_context[:80])
                except Exception as e:
                    logger.debug("Git context failed: %s", e)

            # GitHub — every 10 cycles
            self._github_counter += 1
            if self._github_counter >= 10:
                self._github_counter = 0
                try:
                    self._last_github_block = self.github.get_context_block()
                except Exception as e:
                    logger.debug("GitHub context failed: %s", e)

            # Reddit — every 15 cycles
            self._reddit_counter += 1
            if self._reddit_counter >= 15:
                self._reddit_counter = 0
                try:
                    self._last_reddit_block = self.reddit.get_context_block()
                except Exception as e:
                    logger.debug("Reddit context failed: %s", e)

            # Public bot context — every cycle
            try:
                self._last_public_context = self._get_public_context()
            except Exception as e:
                logger.debug("Public context failed: %s", e)

            # Evolution quality check — every 20 cycles
            if self.cycle_count % 20 == 0:
                try:
                    from skills.evolution_engine import check_and_revert
                    check_and_revert(self.memory, telegram_callback=send_dev)
                except Exception as e:
                    logger.debug("Evolution check failed: %s", e)

            # Disk cleanup check — every 2 hours, if disk > 75%
            if (self.cycle_count % 240 == 0
                    and snap["disk"].get("/", {}).get("percent", 0) > 75):
                try:
                    report = disk_scan()
                    if report['total_bytes'] > 100 * 1024 * 1024:
                        msg = disk_msg(report)
                        send_dev(msg)
                        self._pending_cleanup = report
                        logger.info("Disk cleanup proposed: %.0f MB",
                                    report['total_bytes'] / (1024 * 1024))
                except Exception as e:
                    logger.error("Disk scan failed: %s", e)

            # Cognition self-critique — every 20 cycles
            self._cognition_critique_counter += 1
            if self._cognition_critique_counter >= 20:
                self._cognition_critique_counter = 0
                try:
                    critique = cog_self_critique()
                    if critique:
                        self._last_cognition_critique = critique
                        if critique.get('should_write_soul_note') and critique.get('soul_note_reason'):
                            logger.info("Cognition soul note: %s", critique['soul_note_reason'][:100])
                            self.actions.write_soul_note(critique['soul_note_reason'])
                except Exception as e:
                    logger.debug("Cognition critique failed: %s", e)

            # Self-reflection — periodic insight check
            self._reflection_cycle_counter += 1
            if self._reflection_cycle_counter >= self.REFLECTION_EVERY_N_CYCLES:
                self._reflection_cycle_counter = 0
                try:
                    insight = self._quality_tracker.format_insight_for_soul()
                    if insight:
                        logger.info("Self-reflection insight: %s", insight[:100])
                        self.actions.write_soul_note(insight)
                except Exception as e:
                    logger.warning("Self-reflection error: %s", e)

            result = self._reason(snap)
            if result is None:
                logger.warning("Cycle %d: no response from model", self.cycle_count)
            else:
                logger.info("Cycle %d response:\n%s", self.cycle_count, result)
                # Store response with full perception snapshot + screen context
                screen_note = ""
                screen_activity = "unknown"
                focus_level = "unknown"
                if self._last_screen_obs and self._last_screen_obs.success:
                    screen_note = f" | {self._last_screen_obs.format_for_memory()}"
                    screen_activity = self._last_screen_obs.activity
                    focus_level = self._last_screen_obs.focus_level

                calendar_note = ""
                next_event = "none"
                if self._last_calendar_snap and self._last_calendar_snap.success:
                    calendar_note = f" | {self._last_calendar_snap.format_for_memory()}"
                    if self._last_calendar_snap.next_event:
                        next_event = self._last_calendar_snap.next_event.title

                # Score and classify BEFORE storage — enriched metadata in one write
                full_thought = result + screen_note + calendar_note
                cog_metadata = cog_score_and_classify(full_thought)
                self._last_cog_metadata = cog_metadata
                retried = False

                # Retry path: if thought is below floor or matches reject combos
                try:
                    if cog_should_retry(cog_metadata):
                        policy = cog_get_behavior_policy()
                        retry_instruction = cog_build_retry_prompt(cog_metadata, policy)
                        initial_score = cog_metadata.get('cog_score', 0)
                        initial_labels = cog_metadata.get('cog_labels', '')
                        logger.info("Cycle %d: retry triggered (score=%d, labels=%s)",
                                    self.cycle_count, initial_score, initial_labels)

                        # One corrective retry — append instruction to existing prompt
                        last_prompt = getattr(self, '_last_reasoning_prompt', '')
                        acquired = self._ollama_lock.acquire(timeout=0)
                        if acquired:
                            try:
                                retry_response = ollama.chat(
                                    model=MODEL,
                                    messages=[
                                        {"role": "system", "content": self.system_prompt},
                                        {"role": "user", "content": last_prompt},
                                        {"role": "assistant", "content": result},
                                        {"role": "user", "content": retry_instruction},
                                    ],
                                    options={"temperature": 0.8, "num_predict": 300},
                                )
                                retry_content = retry_response.message.content.strip()
                                if retry_content and retry_content != "(empty response)":
                                    # Re-score the retry
                                    retry_thought = retry_content + screen_note + calendar_note
                                    retry_cog = cog_score_and_classify(retry_thought)

                                    if retry_cog.get('cog_score', 0) > initial_score:
                                        # Retry is better — use it
                                        full_thought = retry_thought
                                        result = retry_content
                                        cog_metadata = retry_cog
                                        cog_metadata['cog_retried'] = 'improved'
                                        cog_metadata['cog_initial_score'] = initial_score
                                        cog_metadata['cog_initial_labels'] = initial_labels
                                        retried = True
                                        logger.info("Cycle %d: retry improved %d → %d",
                                                    self.cycle_count, initial_score,
                                                    retry_cog.get('cog_score', 0))
                                    else:
                                        # Retry didn't help — keep original
                                        cog_metadata['cog_retried'] = 'kept_original'
                                        cog_metadata['cog_retry_score'] = retry_cog.get('cog_score', 0)
                                        logger.info("Cycle %d: retry not better (%d vs %d), keeping original",
                                                    self.cycle_count, retry_cog.get('cog_score', 0), initial_score)
                            except Exception as e:
                                logger.debug("Retry generation failed: %s", e)
                                cog_metadata['cog_retried'] = 'failed'
                            finally:
                                self._ollama_lock.release()
                except Exception as e:
                    logger.debug("Retry check failed: %s", e)

                mem_metadata = {
                    "cpu_pct": snap["cpu"]["percent"],
                    "ram_pct": snap["ram"]["percent"],
                    "gpu_pct": snap["gpu"]["utilization_pct"] if snap.get("gpu") else -1,
                    "gpu_temp": snap["gpu"]["temperature_c"] if snap.get("gpu") else -1,
                    "time_of_day": snap["time_of_day"],
                    "day_of_week": snap["day_of_week"],
                    "screen_activity": screen_activity,
                    "focus_level": focus_level,
                    "next_event": next_event,
                    "rohit_present": str(self._last_presence_snap.rohit_present) if self._last_presence_snap else "unknown",
                }
                mem_metadata.update(cog_metadata)
                self.memory.store(full_thought,
                                  cycle=self.cycle_count,
                                  snapshot=snap, metadata=mem_metadata)

                # Broadcast cycle end with thought to UI
                self._ws_broadcast({
                    "type": "cycle_end",
                    "cycle": self.cycle_count,
                    "thought": result,
                })

            # Continuity checkpoint + orientation expiry
            if result:
                self._continuity_checkpoint_counter += 1
                if self._continuity_checkpoint_counter >= CONTINUITY_CHECKPOINT_INTERVAL:
                    self._continuity_checkpoint_counter = 0
                    try:
                        _last_cog = getattr(self, '_last_cog_metadata', {})
                        continuity_checkpoint(last_thought={
                            'text': result[:200],
                            'cycle': self.cycle_count,
                            'score': _last_cog.get('cog_score', 0),
                            'topic': _last_cog.get('cog_topic', ''),
                            'labels': _last_cog.get('cog_labels', '').split(','),
                        })
                    except Exception as e:
                        logger.debug("Continuity checkpoint failed: %s", e)

                # Expire continuity orientation
                if self._continuity_active:
                    self._continuity_cycles_remaining -= 1
                    if self._continuity_cycles_remaining <= 0:
                        self._continuity_active = False
                        self._continuity_capsule = None
                        try:
                            continuity_archive()
                        except Exception:
                            pass
                        logger.info("Continuity orientation complete. Resuming normal operation.")

            # Proactive search if thought shows knowledge gap
            if result:
                sq = self._should_search(result)
                if sq:
                    try:
                        from skills.web_search import search as _ws
                        sr = _ws(sq, max_results=2)
                        if sr.get('success') and sr['results']:
                            self._proactive_search_context = (
                                f"[PROACTIVE SEARCH: '{sq}']\n"
                                f"  {sr['results'][0]['snippet'][:200]}"
                            )
                            logger.info("Proactive search queued: %s", sq[:60])
                    except Exception as e:
                        logger.debug("Proactive search failed: %s", e)

            # Check system thresholds for alerts (runs even if reasoning failed)
            self._check_and_alert(snap)

            # Follow-up delivery — every 5 cycles
            if self.cycle_count % 5 == 0:
                try:
                    self.followup_queue.expire_old()
                    pending = self.followup_queue.get_pending()
                    for fu in pending:
                        # Build focused delivery prompt
                        fu_snap = perception_snapshot()
                        fu_state = format_snapshot(fu_snap)
                        fu_prompt = (
                            f'You previously told Rohit: "{fu["task"]}"\n'
                            f"Original question: {fu['original_msg']}\n\n"
                            f"Current system state:\n{fu_state}\n\n"
                            f"Deliver on your promise — give Rohit the actual answer or update now.\n"
                            f"Be direct and specific. Start with what you found, not a preamble."
                        )
                        try:
                            fu_resp = ollama.chat(
                                model=MODEL,
                                messages=[
                                    {"role": "system", "content": self.system_prompt},
                                    {"role": "user", "content": fu_prompt},
                                ],
                                options={"temperature": 0.5, "num_predict": 200},
                            )
                            fu_reply = fu_resp.message.content.strip()
                            if fu_reply:
                                self.telegram.send_message(fu_reply)
                                self.followup_queue.mark_delivered(fu['id'])
                                logger.info("[FOLLOWUP] Delivered: %s", fu['task'][:60])
                        except Exception as e:
                            logger.error("[FOLLOWUP] Delivery failed: %s", e)
                except Exception as e:
                    logger.debug("Followup check failed: %s", e)

            # Proactive opinion — every 50 cycles
            if self.cycle_count % 50 == 0:
                self._check_proactive_opinion()

            # Sleep in small increments so shutdown is responsive
            for _ in range(LOOP_INTERVAL):
                if not self.running:
                    break
                time.sleep(1)

        logger.info("Reasoning loop stopped.")

    def start(self):
        """Start the daemon: verify model, launch loop and health server."""
        logger.info("=== Maez Daemon starting ===")
        self.boot_time = datetime.now(timezone.utc).isoformat()
        self._write_pid()

        # Verify Ollama connectivity
        if not self._check_ollama():
            logger.error("Cannot reach Ollama or model %s — aborting.", MODEL)
            self._remove_pid()
            sys.exit(1)
        logger.info("Model %s confirmed available.", MODEL)

        self.running = True

        # Connect action engine to Telegram and start bots
        self.telegram.actions = self.actions
        self.telegram.start()
        self.public_bot.start()

        # Load continuity capsule BEFORE greeting/session-resume logic
        self._continuity_capsule = continuity_load()
        if self._continuity_capsule:
            self._continuity_active = True
            self._continuity_cycles_remaining = POST_RESTART_INJECTION_CYCLES
            logger.info("Continuity active: %d orientation cycles, mode=%s",
                        self._continuity_cycles_remaining,
                        self._continuity_capsule.get('current_mode', '?'))

        # Detect offline duration from last shutdown timestamp
        stats = self.memory.memory_stats()
        is_restart = stats["total"] > 0 and self.cycle_count == 0
        offline_seconds = 0
        last_shutdown = None

        try:
            if SHUTDOWN_FILE.exists():
                last_shutdown = datetime.fromisoformat(SHUTDOWN_FILE.read_text().strip())
                offline_seconds = (datetime.now(timezone.utc) - last_shutdown).total_seconds()
                logger.info("Last shutdown: %s (offline %.0fs)", last_shutdown.isoformat(), offline_seconds)
        except Exception as e:
            logger.warning("Could not read last shutdown time: %s", e)

        # Build startup message
        snap = perception_snapshot()
        gpu = snap.get("gpu") or {}

        if offline_seconds > 3600:
            hours = offline_seconds / 3600
            status_label = f"Maez back online. Was offline for {hours:.1f} hours."
        elif is_restart:
            status_label = "Maez restarted."
        else:
            status_label = "Maez online."

        startup_msg = (
            f"{status_label}\n"
            f"{snap['timestamp']}\n"
            f"CPU: {snap['cpu']['percent']}% | RAM: {snap['ram']['percent']}%\n"
            f"GPU: {gpu.get('utilization_pct', 'N/A')}% | {gpu.get('temperature_c', 'N/A')}°C\n"
            f"Memory: {stats['raw']} raw, {stats['daily']} daily, {stats['core']} core"
        )
        time.sleep(2)
        if not self._continuity_active:
            send_dev(startup_msg)
        else:
            logger.info("Startup message suppressed — continuity orientation active")

        # Check if daily consolidation was missed while offline
        self._missed_consolidation = False
        if last_shutdown and offline_seconds > 3600:
            now_local = datetime.now().astimezone()
            shutdown_local = last_shutdown.astimezone()
            # Check if 3:00 AM passed between shutdown and now
            check = shutdown_local.replace(hour=3, minute=0, second=0, microsecond=0)
            if check <= shutdown_local:
                check += timedelta(days=1)
            if check <= now_local:
                # 3 AM was missed — check if consolidation exists for that date
                missed_date = check.strftime("%Y-%m-%d")
                has_consolidation = False
                try:
                    daily_results = self.memory.daily.get(include=["metadatas"])
                    for meta in daily_results.get("metadatas", []):
                        if meta.get("date") == missed_date:
                            has_consolidation = True
                            break
                except Exception:
                    pass

                if not has_consolidation:
                    self._missed_consolidation = True
                    logger.info("Missed consolidation for %s — will run on startup", missed_date)

        # Start reasoning loop in background thread
        loop_thread = threading.Thread(target=self._loop, daemon=True, name="reasoning-loop")
        loop_thread.start()

        # Start daily consolidation thread (3:00 AM)
        consol_thread = threading.Thread(target=self._consolidation_loop, daemon=True,
                                         name="consolidation")
        consol_thread.start()

        # Start nightly journal thread (11:00 PM)
        journal_thread = threading.Thread(target=self._nightly_journal_loop, daemon=True,
                                           name="journal")
        journal_thread.start()

        # Start proposal worker thread
        try:
            from skills.evolution_engine import start_proposal_worker
            start_proposal_worker()
        except Exception as e:
            logger.debug("Proposal worker start failed: %s", e)

        # Start soul.md hot-reload watcher
        threading.Thread(target=self._watch_soul, daemon=True, name="soul-watcher").start()

        # Start WebSocket server
        ws_thread = threading.Thread(target=self._run_ws_server, daemon=True, name="ws-server")
        ws_thread.start()

        # Start health broadcast thread
        hb_thread = threading.Thread(target=self._start_health_broadcast, daemon=True,
                                      name="health-broadcast")
        hb_thread.start()

        # Voice disabled — re-enable when voice pipeline is stable
        VOICE_ENABLED = False
        if VOICE_ENABLED:
            # Voice output — Kokoro TTS
            if voice_output_init():
                logger.info("Voice output online")
                speak("Maez is online.")
            else:
                logger.warning("Voice output unavailable")

            # Unified audio pipeline — wake word + transcription on single mic stream
            def _on_voice_command(text: str):
                """Called by unified pipeline with transcribed command text."""
                with self._voice_lock:
                    if self._voice_active:
                        return
                    self._voice_active = True

                logger.info("Voice command received: '%s'", text)

                def _handle():
                    try:
                        clean = text.lower()
                        text_cmd = text
                        for phrase in ['hey maez', 'hey maze', 'hey maz',
                                       'maez', 'maze', 'hey jarvis']:
                            if clean.startswith(phrase):
                                text_cmd = text[len(phrase):].strip(' ,.!?')
                                break

                        if not text_cmd:
                            text_cmd = "status"

                        logger.info("Processing voice command: '%s'", text_cmd)
                        reply = self.handle_voice_stream(text_cmd)
                    except Exception as e:
                        logger.error("Voice handler error: %s", e)
                    finally:
                        with self._voice_lock:
                            self._voice_active = False

                threading.Thread(target=_handle, daemon=True,
                                  name="maez-voice-handler").start()

            if wake_word_start(_on_voice_command):
                logger.info("Unified audio pipeline active — say 'Hey Maez'")
            else:
                logger.warning("Audio pipeline unavailable")
        else:
            logger.info("Voice pipeline disabled — set VOICE_ENABLED=True to re-enable")

        # Start health check server (blocks main thread)
        logger.info("Health endpoint starting on port %d", HEALTH_PORT)
        self._run_health_server()

    def stop(self, signum=None, frame=None):
        """Graceful shutdown."""
        logger.info("=== Maez Daemon shutting down (signal: %s) ===", signum)
        self.running = False
        # Write continuity capsule before anything else
        try:
            continuity_shutdown()
        except Exception as e:
            logger.debug("Continuity shutdown write failed: %s", e)
        try:
            wake_word_stop()
            voice_output_shutdown()
        except Exception:
            pass  # Voice may not be initialized
        self.public_bot.stop()
        try:
            SHUTDOWN_FILE.write_text(datetime.now(timezone.utc).isoformat())
        except OSError:
            pass
        self._remove_pid()

    def _run_health_server(self):
        """Minimal Flask health check endpoint."""
        app = Flask("maez-health")

        @app.after_request
        def cors(response):
            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            return response

        # Suppress Flask request logging — we have our own
        logging.getLogger("werkzeug").setLevel(logging.WARNING)

        @app.route("/health")
        def health():
            snap = perception_snapshot()
            gpu = snap.get("gpu") or {}
            return jsonify({
                "status": "alive",
                "model": MODEL,
                "boot_time": self.boot_time,
                "cycle_count": self.cycle_count,
                "last_cycle": self.last_cycle_time,
                "uptime_seconds": int(time.time() - datetime.fromisoformat(self.boot_time).timestamp()),
                "memory": self.memory.memory_stats(),
                "system": {
                    "cpu_percent": snap["cpu"]["percent"],
                    "ram_percent": snap["ram"]["percent"],
                    "gpu_percent": gpu.get("utilization_pct"),
                    "gpu_temp_c": gpu.get("temperature_c"),
                },
            })

        @app.route("/message", methods=["POST"])
        def message():
            data = request.get_json(silent=True) or {}
            text = data.get("text", "").strip()
            if not text:
                return jsonify({"error": "empty message"}), 400
            reply = self.handle_message(text, source="UI")
            return jsonify({"reply": reply})

        @app.route("/")
        def root():
            return jsonify({"name": "Maez", "status": "running"})

        try:
            from werkzeug.serving import make_server
            srv = make_server("127.0.0.1", HEALTH_PORT, app)
            srv.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.serve_forever()
        except KeyboardInterrupt:
            self.stop()


def daemonize():
    """Fork into background as a proper daemon process."""
    if os.fork() > 0:
        sys.exit(0)

    os.setsid()

    if os.fork() > 0:
        sys.exit(0)

    # Redirect stdio to /dev/null
    sys.stdin = open(os.devnull, "r")
    sys.stdout = open(os.devnull, "w")
    sys.stderr = open(os.devnull, "w")


def main():
    daemon = MaezDaemon()

    # Handle signals for graceful shutdown
    signal.signal(signal.SIGTERM, daemon.stop)
    signal.signal(signal.SIGINT, daemon.stop)

    if len(sys.argv) > 1 and sys.argv[1] == "--daemon":
        daemonize()

    daemon.start()


if __name__ == "__main__":
    main()
