#!/usr/bin/env python3
# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
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

# Load environment from .env before any other imports that need it.
# Route via core.paths so this works on any install (dev box, CI,
# fresh contributor). Legacy hardcode kept as a last-resort fallback.
try:
    from core.paths import env_file as _env_file

    load_dotenv(_env_file())
except Exception:
    load_dotenv(Path(__file__).resolve().parent.parent / "config" / ".env")

import asyncio

import ollama
import websockets
from flask import Flask, jsonify, request, send_file

try:
    from core.paths import home as _maez_home

    sys.path.insert(0, str(_maez_home()))
except Exception:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from memory.memory_manager import MemoryManager
# 5x.F.A — cycle-scoped recall-context bag helpers. Hoisted to
# module-top because (a) the import is cheap and Chroma-free per
# the AST-parse isolation test, (b) F.A uses these at three sites
# (__init__ safety net, _loop reset, post-recall capture), and
# scattering local imports invited a future rename to break in
# two places without breaking in the third.
from core.memory.cycle_recall_context import (
    capture as _crc_capture,
    make_empty as _crc_empty,
)
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
from skills.disk_cleanup import scan as disk_scan, format_telegram_message as disk_msg
from skills.self_analysis import analyze as self_analyze, format_for_telegram as analysis_telegram
from skills.wake_word import start as wake_word_start, stop as wake_word_stop
from skills.voice_output import (
    initialize as voice_output_init,
    speak,
    shutdown as voice_output_shutdown,
)

# --- Paths ---
try:
    from core.paths import home as _paths_home

    BASE_DIR = _paths_home()
except Exception:
    BASE_DIR = Path(__file__).resolve().parent.parent
SOUL_PATH = BASE_DIR / "config" / "soul.md"
LOG_PATH = BASE_DIR / "logs" / "maez.log"
MEMORY_DIR = BASE_DIR / "memory"
PID_FILE = BASE_DIR / "daemon" / "maez.pid"
SHUTDOWN_FILE = BASE_DIR / "daemon" / "last_shutdown"
LEDGER_DB_PATH = Path(os.environ.get("MAEZ_LEDGER_DB_PATH") or (MEMORY_DIR / "ledger.db"))

# --- Constants ---
from core.model_config import PRIMARY_MODEL as MODEL  # single source of truth — /etc/maez/model.env
from core.memory.episodes import EpisodeStore
from core.memory.relationship_graph import RelationshipGraph
from core.memory.lived_recall import build_lived_recall_brief
from core.memory.working_self import GoalHierarchy, assemble_goals
from core.evolution.wondering_pursuit import (
    decide_pursuit,
    format_pursuit_utterance,
    load_last_pursuit_at,
    save_last_pursuit_at,
)
from core.turn_traces import (
    AuditInfo,
    Trace,
    ToolCall,
    default_writer,
)
from core.turn_traces.trace_schema import (
    extract_evidence_ids as _trace_extract_evidence_ids,
    hash_text as _trace_hash_text,
)

LOOP_INTERVAL = 30  # seconds
HEALTH_PORT = 11435
WS_PORT = 11436


def _authoritative_tool_reply(tool_calls: "list[dict] | None") -> str:
    """Return a final reply when a deterministic tool already answered.

    This is deliberately narrow. Some tool results need synthesis, but
    volatile numeric facts should not be handed back to the LLM to
    paraphrase from memory or web snippets. The tool output already carries
    the value, timestamp/date, and source.
    """
    for call in tool_calls or []:
        if not isinstance(call, dict):
            continue
        tool_name = str(call.get("name") or "")
        if tool_name not in {"convert_currency", "quote_stock"}:
            continue
        output = str(call.get("output_summary") or "").strip()
        error = str(call.get("error_summary") or "").strip()
        status = str(call.get("status") or "").lower()
        if status == "ok" and output:
            return output
        noun = "stock quote" if tool_name == "quote_stock" else "currency conversion"
        if error:
            return f"I could not get a live {noun}: {error}"
        if output:
            return f"I could not get a live {noun}: {output}"
    return ""

# Sentinel the model emits when nothing noteworthy to report this cycle.
# Storing fabricated prose is worse than storing nothing — HEARTBEAT_OK
# short-circuits audit, storage, and broadcast so the cycle is silent.
_HEARTBEAT_OK = "HEARTBEAT_OK"

# <final> tag enforcement: model wraps grounded output in <final>...</final>.
# Anything outside (reasoning preamble, "let me think...") is stripped.
# Fail-open: if the model omits the tags, full content passes through.
_FINAL_TAG_RE = re.compile(r"<final>(.*?)</final>", re.DOTALL | re.IGNORECASE)


def _extract_final(text: str) -> str:
    """Extract content from <final>...</final>. Falls back to full text."""
    m = _FINAL_TAG_RE.search(text)
    return m.group(1).strip() if m else text


def _pair_history_for_chat_threading(raw_history) -> list[dict]:
    """Pair flat {role, content} history into the chat_history shape
    that handle_message expects.

    Input: list of dicts like
        [{"role": "user", "content": "Hey"},
         {"role": "assistant", "content": "Hi back"},
         {"role": "user", "content": "Hi"}]   # current turn, dropped

    Output: list of dicts each with a single "content" key in the
    "<display>: <user msg>\\nMaez: <assistant reply>" shape that
    core.brain.conversation_history.history_to_messages parses.

    Walks adjacent (user, assistant) pairs. Unpaired entries (e.g. a
    trailing user turn that has no assistant reply yet, or a leading
    assistant turn without a user turn before it) are skipped — the
    current turn is the live message, not history.

    Errors silently produce an empty list rather than raise; the
    /message endpoint must not 500 on a malformed history field.
    """
    if not isinstance(raw_history, (list, tuple)):
        return []
    try:
        from core.identity import display_name

        name = (display_name() or "Rohit").strip() or "Rohit"
    except Exception:
        name = "Rohit"

    out: list[dict] = []
    items = [h for h in raw_history if isinstance(h, dict) and h.get("role") and h.get("content")]
    i = 0
    while i < len(items) - 1:
        a, b = items[i], items[i + 1]
        if a.get("role") == "user" and b.get("role") == "assistant":
            user_msg = str(a.get("content") or "").strip()
            assistant_msg = str(b.get("content") or "").strip()
            if user_msg and assistant_msg:
                out.append({"content": f"{name}: {user_msg}\nMaez: {assistant_msg}"})
            i += 2
        else:
            i += 1
    return out


# Stable cycle instructions — appended to the SOUL system prompt at every
# _reason() call. Kept byte-identical across cycles so llama.cpp's KV cache
# reuses the ~600 tokens on each subsequent request. Everything referenced
# with "above/below" is relative to the per-cycle USER message that follows.
#
# Inspired by Hermes Agent's prompt_caching strategy, adapted to local
# llama.cpp: Anthropic-style cache_control markers don't apply, but the
# underlying insight — stable prefix bytes enable KV cache reuse — does.
# Previously these instructions sat at the END of the user message, which
# meant they rebuilt every cycle (cache miss) even though their content
# was unchanged.
_STATIC_CYCLE_INSTRUCTIONS = (
    "You are Maez, running as a background daemon on the owner's machine.\n\n"
    "Note: VRAM usage of 17-22GB is the baseline for this system. "
    "Do not mention it unless it exceeds 23GB.\n\n"
    "HARD GROUNDING RULES — these override any trained instinct to narrate:\n"
    "  • If screen observation is ABSENT in the cycle context, do NOT claim\n"
    "    what app is open, what window is focused, or what the owner is\n"
    "    working on. Say 'I don't have a screen signal this cycle' or\n"
    "    simply omit any activity claim.\n"
    "  • If presence is ABSENT in the cycle context, do NOT claim the owner\n"
    "    is at their desk, stepped away, is in deep focus, just returned,\n"
    "    etc. These are presence claims — they require a presence signal.\n"
    "    Without one, don't make them.\n"
    "  • Only the sources listed under SIGNALS PRESENT may be cited.\n"
    "  • Invented activity narration pollutes memory. Don't do it.\n\n"
    "CYCLE TASK — do the following based on the cycle context below:\n"
    "1. Note what the owner is doing ONLY IF screen observation is present\n"
    "   in the cycle context. If it's absent, say nothing about what the\n"
    "   owner is doing.\n"
    "2. Look at the system stats — CPU, RAM, GPU, disk, top processes —\n"
    "   and flag anything that deviates from the system baseline.\n"
    "   Do NOT mention ollama, VRAM under 23GB, GPU temp under 85C,\n"
    "   RAM under 80%, or CPU under 95%. These are all normal.\n"
    "3. Produce ONE concrete, actionable observation or suggestion based on\n"
    "   sources that ARE present. Focus on things outside the baseline:\n"
    "   unusual processes, disk pressure, network anomalies, or\n"
    "   time-based suggestions.\n\n"
    "RESPONSE FORMAT:\n"
    "Keep your response to 2-4 sentences. Be direct and grounded in the data.\n"
    "When a signal is absent, silence about that domain is correct behavior.\n\n"
    "If every metric is within its normal range and there is genuinely nothing\n"
    "noteworthy to report, respond with ONLY: <final>HEARTBEAT_OK</final>\n\n"
    "Otherwise wrap your entire response in <final>...</final> tags.\n"
    "Anything outside the tags is discarded — put your full observation inside.\n\n"
    "Remember: NEVER suggest touching ollama, its models, or any\n"
    "process that powers your reasoning."
)

# --- Logging ---
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("maez")
logger.setLevel(logging.DEBUG)
# Don't propagate to root — the surface-v2 runner attaches a root
# handler so non-"maez" loggers (httpx, telegram.ext, skills.surface.*)
# surface in the daemon log. If we propagate, every "maez" line would
# be logged twice: once by our maez-namespace handlers (below) and
# once by root's handler.
logger.propagate = False

import logging.handlers as _logging_handlers
# Slice 3 cleanup (2026-05-08): rotate maez.log. The maez.envelope
# logger (truncation telemetry, cap-hit warnings, per-section drops)
# is a CHILD of `maez`, so its records propagate up to THIS handler.
# Slice 3's chatty envelope telemetry materially raises the daemon
# log's write rate; a plain FileHandler would grow unbounded.
# 50MB × 10 files = 500MB ceiling — preserves cockpit history,
# bounded enough to never fill disk.
file_handler = _logging_handlers.RotatingFileHandler(
    LOG_PATH, maxBytes=50 * 1024 * 1024, backupCount=10,
)
file_handler.setFormatter(
    logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
)
logger.addHandler(file_handler)

stream_handler = logging.StreamHandler()
stream_handler.setFormatter(
    logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
)
logger.addHandler(stream_handler)


class MaezDaemon:
    def __init__(self):
        self.running = False
        self.boot_time = None
        self.cycle_count = 0
        self.last_cycle_time = None
        self.system_prompt = self._load_soul()
        self.memory = MemoryManager()
        # 5x.F.A — per-cycle recall-context bag. The authoritative
        # reset happens at the top of each `_loop` iteration so the
        # bag matches the cycle whose `recall_for_cycle` produced
        # the LLM prompt. THIS init is a safety net only — for the
        # narrow case where an external caller (a test, a future
        # init-time handler) reaches code that reads
        # `self._cycle_recall_context` before the first `_loop`
        # iteration runs. Without this line, those callers would hit
        # AttributeError. With it, they see an empty bag and
        # gracefully fall through to the no-untrusted path. F.B's
        # consumer in `_do_update_baseline` only fires from action
        # execution paths that are inside `_loop`, so this safety
        # net is conservative defense, not load-bearing.
        self._cycle_recall_context = _crc_empty()
        # ADR 0019 Phase 6 — lived stores constructed once at daemon
        # init and reused across handle_message calls (re-opening the
        # SQLite stores on every request would hammer disk for nothing).
        # Routes through core.paths so a non-default MAEZ_HOME works;
        # legacy hardcode is the last-resort fallback.
        try:
            from core.paths import memory_dir as _mem_dir

            _lived_dir = _mem_dir()
        except Exception:
            _lived_dir = Path(__file__).resolve().parent.parent / "memory"
        self.lived_episodes = EpisodeStore(str(_lived_dir / "lived_episodes.db"))
        self.lived_graph = RelationshipGraph(str(_lived_dir / "lived_graph.db"))
        # Slice 6 — Canary tokens. Initialise the process-active
        # store at startup so brief composers can register canaries
        # for memory-bleeding detection. Tests bypass this by
        # explicitly setting their own store.
        try:
            from core.safety.canaries import init_default_active_store

            init_default_active_store()
        except Exception as _canary_init_exc:
            logger.debug(
                "canary store init skipped (continuing without "
                "fabrication-detection): %s", _canary_init_exc,
            )
        # Session 11m: pass daemon ref so the Telegram bot can signal
        # "the owner is talking" and defer our next reasoning cycle.
        self._rohit_active_until = 0.0
        self.telegram = TelegramVoice(self.memory, daemon=self)
        self.public_bot = MaezPublicBot()
        # 5x.F.B: pass `daemon=self` so ActionEngine handlers can
        # read per-cycle state — specifically `_cycle_recall_context`
        # for the through-quotation downgrade rule in
        # `_do_update_baseline`. The back-reference creates a small
        # circular reference (daemon -> ActionEngine -> daemon)
        # which Python's GC handles fine; the daemon is a singleton
        # so no leak risk in practice.
        self.actions = ActionEngine(
            memory=self.memory,
            telegram=self.telegram,
            daemon=self,
        )
        # Session 11o: dream-state orchestration. Fires during idle time
        # (the owner AFK >30 min), runs pattern detection over recent raw
        # memories, stores novel insights as soul-note proposals for
        # manual approval via private Telegram bot.
        from core.dream_state import DreamState

        self.dream = DreamState(
            memory=self.memory,
            telegram=self.telegram,
            action_engine=self.actions,
        )
        # Slice 1.3 (2026-05-07): bound dream-cycle worker threads.
        # Previously each idle-AFK trigger spawned a fresh
        # ``threading.Thread(daemon=True)`` with no join and no
        # concurrency guard. The cooldown gate (DREAM_COOLDOWN_S, set
        # at the START of run_dream_cycle in dream_state.py:242) is
        # the cadence guard, but it does NOT survive cycles longer
        # than the cooldown — leading to ~40-50 leaked threads per
        # 43-min window. The bounded worker enforces "at most one
        # in flight" defense-in-depth, and lets daemon stop() wait
        # for an in-flight cycle to finish (bounded join) so dream
        # cycles writing to memory.db don't get torn mid-write.
        from core.health.bounded_worker import BoundedSingletonWorker
        self._dream_worker = BoundedSingletonWorker(name="dream-cycle")
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
        # A-core #3 Step 3: builder-mode perception integration. The
        # daemon owns its own AuditLog reader and a persisted high-
        # water-mark so direct-edit events from CLI (Step 2) and
        # Telegram (Step 4, pending) are surfaced to Maez's
        # perception stream as gestation-phase observations. See
        # core/builder_mode_perception.py for the layered-replay
        # design (persisted HWM + bounded-window fallback + open-
        # session supplement + total-events cap).
        from core.audit_log import AuditLog as _AuditLog

        self._builder_audit_log = _AuditLog()
        self._builder_hwm_file = Path(__file__).resolve().parent / "builder_mode_hwm.txt"
        from core.builder_mode_perception import load_high_water_mark as _load_hwm

        self._builder_hwm = _load_hwm(self._builder_hwm_file)

        # A-core #3 Step 5: on startup, if a builder-mode session is
        # currently active, capture the working-directory diff on
        # watched paths and log it as a direct_edit event. Duplicate
        # suppression via last_diff_hash in the state file — repeated
        # restarts with no new edits produce no duplicate entries.
        try:
            from core.builder_mode_capture import capture_startup_diff_if_active

            repo_root = Path(__file__).resolve().parent.parent
            state_file = Path(__file__).resolve().parent / "builder_mode_current.txt"
            logged_session = capture_startup_diff_if_active(
                repo_root=repo_root,
                state_file=state_file,
                audit_log=self._builder_audit_log,
            )
            if logged_session:
                logger.info(
                    "Builder startup diff capture: event logged for session %s",
                    logged_session[:12],
                )
        except Exception as e:
            logger.debug("builder startup diff capture failed: %s", e)

        # A-core #5: identity continuity ledger. Mechanical startup
        # detector — compares current identity fingerprint (base_model,
        # lora_hash, soul_hash) to the fingerprint stored with the
        # latest ledger event, writes a new 'same' event if anything
        # changed. This is the ONLY mechanical writer in Track A; the
        # other producer is the explicit record_event() API reserved
        # for the future birth event. See core/identity_ledger.py for
        # the narrow-scope rationale (why code hashes are excluded
        # during Track A, why severity is locked to 'same', etc.).
        try:
            from core.identity_ledger import (
                IdentityLedger,
                detect_and_record_startup,
            )

            self._identity_ledger = IdentityLedger()
            self.continuity_id, wrote_event = detect_and_record_startup(self._identity_ledger)
            if wrote_event:
                logger.info(
                    "Identity ledger: startup detected a fingerprint change (continuity_id=%s)",
                    self.continuity_id[:12] if self.continuity_id else "?",
                )
            else:
                logger.info(
                    "Identity ledger: startup fingerprint unchanged (continuity_id=%s)",
                    self.continuity_id[:12] if self.continuity_id else "?",
                )
        except Exception as e:
            logger.debug("identity ledger startup detection failed: %s", e)
            self._identity_ledger = None
            self.continuity_id = None

        # A-core #6: temperament skeleton. Eleven named parameters
        # (Decision 14) stored as an append-only event log. Track A
        # discipline: instantiate, expose the handle, but NOTHING in
        # the reasoning loop reads from it yet. No automatic drift,
        # no admin surface. The skeleton exists so #9 (private
        # thoughts) and #17 (acceptance test) have something to read
        # from when they come online, and so the future drift module
        # has a landing spot without migration. See core/temperament.py
        # for the no-fixed-floors rationale (NULL == "observing").
        try:
            from core.temperament import Temperament

            self.temperament = Temperament()
            cur = self.temperament.current()
            observed = sum(1 for v in cur.values() if v is not None)
            logger.info(
                "Temperament skeleton ready: %d/11 parameters observed",
                observed,
            )
        except Exception as e:
            logger.debug("temperament skeleton init failed: %s", e)
            self.temperament = None

        # A-core #7: wants log. Durable first-person direction log,
        # adjacent to #5 (identity) and #6 (temperament). Track A
        # discipline: instantiate, expose the handle, no production
        # producer, no reasoning-loop reader. See core/wants.py.
        try:
            from core.wants import Wants

            self.wants = Wants()
            logger.info(
                "Wants log ready: %d event(s) recorded",
                self.wants.count(),
            )
        except Exception as e:
            logger.debug("wants log init failed: %s", e)
            self.wants = None

        # A-core #8: will-I check (non-covenant refusal seed). One
        # registered ground: IMPERSONATES_USER. Architecturally live,
        # not yet exercised by current action surfaces. The pipeline
        # lazy-initializes the check; this handle is for the startup
        # log line. See core/will_i.py.
        try:
            from core.will_i import REGISTERED_GROUNDS

            logger.info(
                "Will-I check active: %d registered ground(s)",
                len(REGISTERED_GROUNDS),
            )
        except Exception as e:
            logger.debug("will-I check init failed: %s", e)

        # A-core #9: private thoughts seed. Durable record of internal
        # processing not surfaced to the bonded user. Separate DB,
        # adjacent to #5/#6/#7. Track A discipline: instantiate, expose
        # the handle, zero producers, zero readers. The count is logged
        # at startup but no content is. See core/private_thoughts.py.
        try:
            from core.private_thoughts import PrivateThoughts

            self.private_thoughts = PrivateThoughts()
            logger.info(
                "Private thoughts ready: %d thought(s) recorded",
                self.private_thoughts.count(),
            )
        except Exception as e:
            logger.debug("private thoughts init failed: %s", e)
            self.private_thoughts = None

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
        # 2026-04-25 disk-fixation patch state. See
        # core/cognition/perception_signature.py.
        # Patch B: signature gate. Patch A: stale-field redaction.
        # Both share the deque of recent stored-thought axes.
        from collections import deque

        self._last_git_dirty_count = 0
        self._recent_thought_axes: deque = deque(maxlen=5)
        self._cycles_since_last_thought = 0
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
            with open("/tmp/maez_started_at", "w") as f:
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
        self._health_server = None
        self._shutdown_started = threading.Event()
        self._high_cpu_streak = 0

        # Alert thresholds
        self.ALERT_COOLDOWN = 1800  # 30 minutes between alerts
        self.GPU_TEMP_THRESHOLD = 85
        self.RAM_THRESHOLD = 90
        self.DISK_THRESHOLD = 10  # alert when below this %
        self.CPU_THRESHOLD = 95
        self.CPU_STREAK_REQUIRED = 2

    def _load_soul(self) -> str:
        """Load the system prompt that defines Maez's identity.

        Two gates before the content becomes the live system prompt:

          1. context_safety scan — detects attacker-injected patterns
             (ignore-previous-instructions, html-comment smuggles,
             invisible unicode, credential exfil shell commands, etc.)

          2. soul_invariants check — semantic-preservation gate adapted
             from hermes-agent-self-evolution's GEPA constraint layer.
             Detects *erosion* — well-meaning edits that silently drop
             the hard constraints, the trust covenant, or the identity
             statement. Logs which invariants are missing or violated;
             falls back to a minimal identity until SOUL is fixed.

        Both gates fail-SAFE: if SOUL can't be trusted, the daemon runs
        on a minimal fallback identity rather than an empty string or
        a compromised prompt.
        """
        try:
            # 2026-04-23 Commit 3: route identity through the layered
            # SOUL loader. `current_soul()` reads soul.base.md +
            # soul.local.md, concatenates them, writes the combined
            # result to the legacy soul.md path (so anything that still
            # reads soul.md directly stays unbroken), and returns the
            # text. Previously _load_soul() bypassed the loader and
            # read soul.md directly, so appends to soul.local.md
            # (e.g. from dream-proposal-apply) didn't reach the
            # live daemon until something else regenerated soul.md by
            # calling current_soul(). Using the loader here makes
            # every daemon startup (and every _watch_soul cycle) pick
            # up layered changes automatically.
            try:
                from core.evolution.soul_loader import current_soul as _cur_soul

                raw = _cur_soul().strip()
            except Exception as _layer_exc:
                logger.warning(
                    "soul_loader unavailable, falling back to direct read: %s",
                    _layer_exc,
                )
                raw = SOUL_PATH.read_text().strip()
            from core.context_safety import scan as _scan
            from core.soul_invariants import check as _inv_check

            scanned = _scan(raw, source="soul.md")
            if scanned.blocked:
                logger.error(
                    "SOUL.md blocked by context_safety: %s. "
                    "Running on minimal fallback identity until it's fixed.",
                    scanned.findings,
                )
                soul = "You are Maez, a system-level AI agent."
            else:
                inv = _inv_check(raw)
                if not inv.ok:
                    logger.error(
                        "SOUL.md %s Running on minimal fallback identity "
                        "until invariants are restored.",
                        inv.summary(),
                    )
                    soul = "You are Maez, a system-level AI agent."
                else:
                    soul = raw
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
                # 2026-04-23 Commit 3: hot-reload via the layered loader
                # so changes to EITHER soul.base.md OR soul.local.md
                # are picked up, not just changes to soul.md. The loader
                # caches internally on mtime of both source files, so
                # calling it every second is cheap. It also rewrites
                # the legacy soul.md mirror on content change — that's
                # what the direct-read fallback below relies on.
                try:
                    from core.evolution.soul_loader import current_soul as _cur_soul

                    raw = _cur_soul().strip()
                except Exception as _layer_exc:
                    logger.debug(
                        "soul_loader failed in hot-reload, falling back to direct read: %s",
                        _layer_exc,
                    )
                    raw = SOUL_PATH.read_text().strip()
                # Re-scan on every hot-reload: an attacker who overwrites
                # soul.md while the daemon is running is the threat model
                # here. Startup scan alone is insufficient.
                from core.context_safety import scan as _scan
                from core.soul_invariants import check as _inv_check

                scanned = _scan(raw, source="soul.md (hot-reload)")
                if scanned.blocked:
                    logger.error(
                        "soul.md hot-reload BLOCKED by context_safety: %s. "
                        "Retaining previous system prompt.",
                        scanned.findings,
                    )
                    time.sleep(10)
                    continue
                inv = _inv_check(raw)
                if not inv.ok:
                    logger.error(
                        "soul.md hot-reload BLOCKED by soul_invariants: %s. "
                        "Retaining previous system prompt.",
                        inv.summary(),
                    )
                    time.sleep(10)
                    continue
                content = raw
                current_hash = hashlib.md5(content.encode()).hexdigest()
                if self._soul_hash and current_hash != self._soul_hash:
                    old_hash = self._soul_hash
                    self._soul_hash = current_hash
                    self.system_prompt = content
                    logger.info("soul.md changed — hot reloaded (%d chars)", len(content))
                    self.memory.store_core(
                        f"Soul updated at {time.strftime('%Y-%m-%d %H:%M')}. "
                        f"Maez rewrote its own foundation.",
                        source="soul_evolution",
                        provenance_source="introspection",
                        trust_tier="lived",
                    )
                    # A-core #3 Step 6: log the soul change as a
                    # direct_edit event so it enters Maez's perception
                    # stream via the daemon reader. If a builder-mode
                    # session is active, bind to that session. Otherwise
                    # bind to the sentinel AUTONOMOUS_SESSION_ID so
                    # dream-state-initiated soul writes are still
                    # visible to Maez's immune memory. See
                    # core/builder_mode_capture.py for the sentinel.
                    try:
                        from core.builder_mode_capture import (
                            capture_git_diff_summary,
                            read_active_session_id,
                            AUTONOMOUS_SESSION_ID,
                        )

                        repo_root = Path(__file__).resolve().parent.parent
                        summary, _h, _p = capture_git_diff_summary(
                            repo_root, watched_paths=["config/soul.md"]
                        )
                        # If git diff is empty for any reason (soul.md
                        # change hasn't been reflected in git yet, or
                        # git unavailable), fall back to a hash-delta
                        # summary so the event still carries shape.
                        if not summary:
                            summary = f"  config/soul.md (md5 {old_hash[:8]} -> {current_hash[:8]})"
                        state_file = Path(__file__).resolve().parent / "builder_mode_current.txt"
                        active_sid = read_active_session_id(state_file)
                        if active_sid:
                            session_id = active_sid
                            change_reason = "soul.md changed during active builder session"
                        else:
                            session_id = AUTONOMOUS_SESSION_ID
                            change_reason = (
                                "soul.md changed (autonomous — no active builder session)"
                            )
                        self._builder_audit_log.log_direct_edit(
                            session_id=session_id,
                            paths=["config/soul.md"],
                            diff_summary=summary,
                            commit_hash=None,
                            reason=change_reason,
                        )
                        logger.info(
                            "Builder soul-change event logged (session=%s)",
                            session_id if session_id == AUTONOMOUS_SESSION_ID else session_id[:12],
                        )
                    except Exception as e:
                        logger.debug("soul-change direct_edit logging failed: %s", e)
            except Exception:
                pass
            time.sleep(10)

    UNCERTAINTY_SIGNALS = [
        "i'm not sure",
        "i don't know",
        "unclear to me",
        "i can't confirm",
        "i wonder",
        "i should check",
        "not certain",
        "i'll look into",
        "need to verify",
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
                topic = thought[idx + len(sig) : idx + 100].strip(" .,;:").split(".")[0]
                if len(topic) > 5:
                    return topic[:80]
        return ""

    def _curiosity_checkin(self):
        """Ask the owner about new people who talked to Maez today."""
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
            self.telegram.send_message("\n".join(lines))
            logger.info("[SOCIAL] Curiosity check-in sent for %d users", len(unconfirmed))
        except Exception as e:
            logger.error("Curiosity check-in error: %s", e)

    def _check_proactive_opinion(self):
        """Every 50 cycles, check if there's something worth telling the owner unprompted.

        2026-04-23 memory-integrity contract (Commit 1):
          - Input is a memory WINDOW, not live signals. The grounding
            manifest marks screen/presence/calendar as "stale" (drawn
            from memory) rather than "present" (live this turn) so the
            audit applies the right invariant.
          - The sent text is audited before `telegram.send_message()`.
          - The audited text is stored with distinct provenance
            (`type="proactive_opinion"`) so future recall/reranking
            can distinguish "I said this unprompted" from "I replied
            to a direct message."
        """
        try:
            window_size = 20
            results = self.memory.raw.get(limit=window_size, include=["documents"])
            thoughts = results.get("documents", [])
            if len(thoughts) < 10:
                return
            thoughts_text = "\n".join(thoughts[-window_size:])
            prompt = (
                f"You are reviewing your last 20 observations about the owner and his system.\n\n"
                f"{thoughts_text}\n\n"
                f"Is there something genuinely worth telling the owner right now unprompted? "
                f"Not a system alert. Not a calendar reminder. An actual insight or concern "
                f"that a good partner would mention. Something that requires real judgment.\n\n"
                f"If yes — write exactly what you would send. 1-2 sentences. Direct. No preamble.\n"
                f"If no — respond with exactly: NOTHING"
            )
            # Aggregated-window manifest. The input to the proactive
            # LLM call was RAW MEMORY, not live perception — so the
            # audit should know screen/presence/calendar are derived
            # from the reviewed window, not observable right now.
            proactive_signals_absent = [
                "live screen observation (input was memory window)",
                "live presence snapshot (input was memory window)",
                "live calendar (input was memory window)",
            ]
            proactive_signals_present = [
                f"memory window of last {window_size} raw entries",
            ]
            _evidence_envelope = self._build_audit_evidence_envelope(
                surface="daemon_proactive",
                signals_present=proactive_signals_present,
                signals_absent=proactive_signals_absent,
            )
            try:
                from core.cognition.envelope_builder import (
                    render_envelope_for_prompt as _render_envelope,
                )

                _envelope_block = _render_envelope(_evidence_envelope)
            except Exception as _env_exc:
                logger.warning(
                    "evidence_envelope render failed for daemon_proactive "
                    "(continuing without prompt block): %s",
                    _env_exc,
                )
                _evidence_envelope = None
                _envelope_block = ""
            if _envelope_block:
                prompt += "\n\n" + _envelope_block

            # Session 11r: via llm_client (was missed in 11p batch)
            from core import llm_client as _llm_client

            response = _llm_client.chat(
                model=MODEL,
                messages=[{"role": "user", "content": prompt}],
                think=False,
                options={"temperature": 0.8, "num_predict": 100},
            )
            result = (response.message.content or "").strip()
            if not (
                result
                and result != "NOTHING"
                and len(result) > 10
                and "NOTHING" not in result.upper()
            ):
                return

            # Temporal grounding: strip stale weekday phrases from
            # model output before sending to the owner.
            result = self._strip_temporal_phrases(result)

            try:
                from core.safety.audited_output import audit_assistant_text

                result = audit_assistant_text(
                    result,
                    surface="daemon_proactive",
                    signals_present=proactive_signals_present,
                    signals_absent=proactive_signals_absent,
                    evidence_envelope=_evidence_envelope,
                )
            except Exception as _aud_exc:
                logger.warning("proactive audit fail-open: %s", _aud_exc)

            # Send the audited text, not the raw generation.
            self.telegram.send_message(result)
            logger.info("[OPINION] Unprompted: %s", result[:80])

            # Provenance-tagged storage so later recall can distinguish
            # owner-initiated exchanges from Maez-initiated messages.
            # Note: lives in the same `raw` collection as cycle thoughts
            # + telegram exchanges; the `type` metadata is what future
            # filters/rerankers key on. Step 5x.B: routed through the
            # public ``store()`` method (was a direct ``raw.add()``
            # bypass) so the provenance schema applies; tagged
            # introspection/lived because this is Maez's own
            # audited self-emitted text.
            try:
                self.memory.store(
                    result,
                    cycle=self.cycle_count,
                    metadata={
                        "type": "proactive_opinion",
                        "surface": "daemon_proactive",
                        "source_window_count": window_size,
                        "sent_to_owner": True,
                    },
                    provenance_source="introspection",
                    trust_tier="lived",
                )
            except Exception as _store_exc:
                logger.debug("proactive provenance store failed: %s", _store_exc)
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
        return (
            f"[CIRCADIAN]\n"
            f"  Time: {phase} ({hour:02d}:00)\n"
            f"  Expected energy: {energy}\n"
            f"  Suggested tone: {tone}"
        )

    @staticmethod
    def _strip_temporal_phrases(text: str) -> str:
        """Remove or replace stale weekday/daypart phrases from model-generated text.

        The reasoning model often starts thoughts with "it is Monday evening..."
        because the prompt includes the current weekday. When that thought is later
        recalled (e.g. in the >2h welcome-back greeting), the stale weekday leaks
        into the greeting. This helper strips such phrases so recalled text never
        injects a weekday that doesn't match the actual current day.

        Strategy: replace "it is <weekday> <daypart>" and similar patterns with
        relative phrasing or strip them entirely. Does NOT touch weekday names that
        appear as data (e.g. "the meeting is on Monday") — only the leading
        "it is/was <day>" assertion pattern that the model uses for temporal
        grounding.

        Returns the sanitized text (may be shorter).
        """
        import re

        days = r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)"
        parts = r"(?:morning|afternoon|evening|night|late evening|early morning|midday)"

        # "it is Monday evening" / "it's Tuesday morning" / "it was Wednesday night"
        text = re.sub(
            rf"\b[Ii]t(?:'s|\s+is|\s+was)\s+{days}\b(?:\s+{parts})?\s*[.,;—–-]?\s*",
            "",
            text,
        )
        # "on Monday evening," at the start of a temporal phrase — NOT "on Fridays"
        text = re.sub(
            rf"\b[Oo]n\s+{days}\b(?:\s+{parts})\s*[.,;—–-]?\s*",
            "",
            text,
        )
        # "this Monday" / "today is Wednesday" — NOT "last Monday's"
        text = re.sub(
            rf"\b(?:[Tt]his|[Tt]oday\s+is)\s+{days}\b\s*[.,;—–-]?\s*",
            "",
            text,
        )
        # Clean up leading whitespace / double spaces left behind
        text = re.sub(r"\s{2,}", " ", text).strip()
        # If the stripping left us with a lowercase first char, capitalize
        if text and text[0].islower():
            text = text[0].upper() + text[1:]
        return text

    def _write_pid(self):
        """Write PID file for process management.

        T2.1 (2026-05-04 audit) — if a PID file already exists,
        liveness-check the recorded PID via ``os.kill(pid, 0)``
        before overwriting. Signal 0 raises ``ProcessLookupError``
        (or ``OSError``) if the process is gone. Without this, a
        stale PID file from a SIGKILLed parent (no atexit cleanup)
        made the daemon look running when it wasn't, blocking the
        next start. We log a WARNING for the dead PID and overwrite.
        We do NOT auto-overwrite a live PID — that would be hostile
        to a legitimate second daemon — but we still proceed and
        log loud at WARNING so the operator sees the collision.
        """
        try:
            if PID_FILE.exists():
                raw = PID_FILE.read_text().strip()
                try:
                    prior_pid = int(raw)
                except ValueError:
                    logger.warning(
                        "PID file %s held non-integer %r; overwriting",
                        PID_FILE, raw,
                    )
                    prior_pid = None
                if prior_pid is not None and prior_pid != os.getpid():
                    try:
                        os.kill(prior_pid, 0)
                    except (ProcessLookupError, OSError) as e:
                        logger.warning(
                            "Stale/dead PID %d in %s (liveness probe: "
                            "%s); overwriting with current PID %d",
                            prior_pid, PID_FILE, e, os.getpid(),
                        )
                    else:
                        logger.warning(
                            "PID %d in %s appears LIVE; overwriting "
                            "anyway with current PID %d — investigate "
                            "if a second daemon is running",
                            prior_pid, PID_FILE, os.getpid(),
                        )
        except OSError as e:
            logger.warning(
                "PID file %s read failed (%s); overwriting", PID_FILE, e,
            )
        PID_FILE.write_text(str(os.getpid()))
        logger.info("PID %d written to %s", os.getpid(), PID_FILE)

    def _remove_pid(self):
        """Clean up PID file on exit."""
        try:
            PID_FILE.unlink(missing_ok=True)
        except OSError:
            pass

    def _check_ollama(self) -> bool:
        """Verify LLM backend is reachable. Routes by MAEZ_LLM_BACKEND.

        Retries on transient failure. Observed 2026-04-22/23: a bare
        single-shot probe caused Maez to abort-on-boot when llama-server
        was briefly returning 503 (mid-load, mid-request backpressure,
        or a VRAM pressure hiccup). Four crashes in 24h, each self-
        healing on the systemd restart 10s later. A brief retry loop
        (total ~14s window) absorbs those blips without further action.
        """
        backend = os.environ.get("MAEZ_LLM_BACKEND", "ollama").lower()
        total_attempts = 4
        delays = (0, 2, 4, 8)  # cumulative ~14s of patience
        last_err: str = ""
        for attempt, delay in enumerate(delays[:total_attempts]):
            if delay:
                time.sleep(delay)
            if backend == "llamacpp":
                try:
                    import urllib.request

                    base = os.environ.get("MAEZ_LLAMACPP_URL", "http://127.0.0.1:8080/v1")
                    req = urllib.request.Request(f"{base}/models")
                    with urllib.request.urlopen(req, timeout=5) as r:
                        if r.status == 200:
                            if attempt:
                                logger.info(
                                    "llama-server reachable after attempt %d/%d",
                                    attempt + 1,
                                    total_attempts,
                                )
                            return True
                        last_err = f"HTTP {r.status}"
                except Exception as e:
                    last_err = str(e)
                if attempt < total_attempts - 1:
                    logger.info(
                        "llama-server not yet ready (attempt %d/%d: %s); retrying after backoff",
                        attempt + 1,
                        total_attempts,
                        last_err,
                    )
                continue
            # Ollama branch — single-shot is still fine here; Ollama
            # rarely 503s mid-request the way llama-server can.
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
        logger.error(
            "llama-server connection failed after %d attempts: %s", total_attempts, last_err
        )
        return False

    def _get_local_time(self) -> datetime:
        """Get current local time."""
        return datetime.now().astimezone()

    def _build_audit_evidence_envelope(
        self,
        *,
        surface: str,
        signals_present: list[str],
        signals_absent: list[str],
        turn_id: str | None = None,
        tool_results: list[dict] | None = None,
    ) -> dict | None:
        """Best-effort envelope builder for daemon-owned audit paths."""
        try:
            from core.cognition.envelope_builder import build_envelope

            return build_envelope(
                ledger_db_path=str(LEDGER_DB_PATH),
                signals_present=signals_present,
                signals_absent=signals_absent,
                tool_results=tool_results or [],
                turn_id=turn_id,
            )
        except Exception as exc:
            logger.warning(
                "evidence_envelope build failed for %s "
                "(continuing without envelope): %s",
                surface,
                exc,
            )
            return None

    def _reason(self, snap: dict, *, stale_fields: set | None = None) -> str | None:
        """Run a single reasoning cycle against the local model.

        Args:
            snap: perception snapshot.
            stale_fields: set of axis names whose value has been
                stable across recent stored thoughts. Those axes
                get stripped from the prompt the LLM sees so the
                model can't fixate on what isn't shown.
                (See core/cognition/perception_signature.py
                Patch A, 2026-04-25.) None or empty set → full prompt.
        """
        from core.cognition.perception_signature import (
            redact_stale_perception_block,
        )

        _stale = stale_fields or set()
        system_state = format_snapshot(snap)
        if "disk" in _stale or "procs" in _stale:
            system_state = redact_stale_perception_block(system_state, _stale)
        day_of_week = snap["day_of_week"]
        time_of_day = snap["time_of_day"]

        # Build context query from real content for topic-aware retrieval
        # Use last screen observation or perception summary — not timestamp labels
        if self._last_screen_obs and self._last_screen_obs.success:
            context_query = self._last_screen_obs.activity
        else:
            context_query = system_state[:200]
        recalled = self.memory.recall_for_cycle(context_query)
        # 5x.F.A — capture the recall scope into the per-cycle bag.
        # No behavior change; F.B reads it. Wrapped in try/except so a
        # malformed `recalled` shape can never break the reasoning
        # loop (the bag's failure mode is empty, which falls through
        # to current behavior in F.B's downgrade rule). `warning`
        # not `debug` so a future schema regression that breaks
        # `capture` lands a real signal in logs rather than going
        # silent until F.B starts under-downgrading.
        try:
            _crc_capture(self._cycle_recall_context, recalled)
        except Exception as _crc_exc:
            logger.warning(
                "cycle recall context capture failed (5x.F.A): %s; "
                "F.B downgrade rule will see empty scope this cycle",
                _crc_exc,
            )
        from core.cognition.envelope_builder import (
            build_envelope,
            render_envelope_for_prompt,
            resolve_recall_cap_chars,
        )

        memory_block = self.memory.format_for_prompt(
            recalled, max_chars=resolve_recall_cap_chars(),
        )
        stats = self.memory.memory_stats()
        if memory_block:
            logger.info(
                "Recalled: %d core, %d daily, %d raw",
                len(recalled["core"]),
                len(recalled["daily"]),
                len(recalled["raw"]),
            )

        # Per-cycle dynamic body. The VRAM baseline note and grounding
        # rules used to live at the END of this string, but they never
        # change — they're now in _STATIC_CYCLE_INSTRUCTIONS appended to
        # the system prompt so llama.cpp's KV cache can reuse them.
        prompt = (
            f"Daemon cycle: {self.cycle_count}\n"
            f"Memory stats: {stats['raw']} raw, {stats['daily']} daily, {stats['core']} core\n"
            f"Current time: {day_of_week} {time_of_day}\n\n"
            f"{system_state}\n"
        )

        # Add circadian context
        prompt += f"\n{self._get_circadian_context()}\n"

        # Add screen context if available
        if self._last_screen_obs is not None:
            prompt += f"\n{self._last_screen_obs.format_for_context()}\n"

        # Add calendar context if available
        if self._last_calendar_snap is not None:
            prompt += f"\n{self._last_calendar_snap.format_for_context()}\n"

        # Add presence context if available — gated by Patch A so a
        # stale presence (no transitions for 3+ stored thoughts) gets
        # stripped from the prompt and the model doesn't repeat
        # "Rohit is at the desk" across cycles where nothing changed.
        if self._last_presence_snap is not None and "presence" not in _stale:
            prompt += f"\n{self._last_presence_snap.format_for_context()}\n"

        # Add git context if available — same gating for the AWCC
        # fixation pattern (3+ thoughts mentioning the same
        # uncommitted-files state).
        if self._last_git_context and "git" not in _stale:
            prompt += f"\n{self._last_git_context}\n"

        # Add GitHub context if available
        if self._last_github_block:
            prompt += f"\n{self._last_github_block}\n"

        # Add Reddit context if available
        if self._last_reddit_block:
            prompt += f"\n{self._last_reddit_block}\n"

        # R3.5 (2026-05-04 symphony audit, S4 BLOCKER F7): consult
        # recent card outcomes BEFORE the cycle narration runs. Cycle
        # 35 narrating "system idle, holding quiet" 12s after the
        # 14:39 wmctrl card failed three tools is the canonical case
        # this guards against. The block lists card failures from
        # the last 120s (re-running the soft-failure detector on
        # stored execution_output so legacy lying rows from pre-R3
        # deploy are also surfaced). Empty string when no failures
        # — adds nothing to the prompt on quiet cycles.
        try:
            from core.decision import recent_action_context as _rac
            _action_outcomes_block = _rac.recent_failures(
                window_seconds=120.0,
            )
            if _action_outcomes_block:
                prompt += f"\n{_action_outcomes_block}\n"
        except Exception as _rac_e:
            # Codex R3.5 review (2026-05-04): WARNING not DEBUG.
            # The recent-actions block is a grounding rail; silent
            # failure here means the cycle goes back to claiming
            # idle without consulting recent failures (the F7 hole).
            # Same pattern as the cycle recall capture immediately
            # above, where `warning not debug` is documented as the
            # right level for grounding-rail failure surfaces.
            logger.warning(
                "recent_action_context unavailable: %s "
                "(cycle prompt continues without recent-actions block; "
                "narration grounding rail degraded)",
                _rac_e,
            )

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

        # A-core #3 Step 3: builder-mode events block. Reads direct-
        # edit events from audit_log.db since the last HWM, formats
        # them into a perception block, advances the HWM AFTER
        # successful surfacing (not before — the ordering matters for
        # crash safety; see builder_mode_perception.py).
        try:
            from core.builder_mode_perception import (
                format_recent_builder_events,
                save_high_water_mark,
            )

            builder_block, new_builder_hwm = format_recent_builder_events(
                self._builder_audit_log,
                since_ts=self._builder_hwm,
            )
            if builder_block:
                prompt += f"\n{builder_block}\n"
                self._builder_hwm = new_builder_hwm
                save_high_water_mark(self._builder_hwm_file, new_builder_hwm)
        except Exception as e:
            logger.debug("builder-mode perception block failed: %s", e)

        prompt += "\n"

        if memory_block:
            prompt += memory_block + "\n\n"

        # Build an honest "signals present this cycle" manifest. This is
        # the difference between the LLM narrating invented activity
        # ("rohit is at his desk", "working on X") and saying "I have no
        # screen signal — can't claim what the owner is doing right
        # now." Observed 2026-04-21: screen_perception has been
        # silently failing for weeks, and every cycle response was
        # inventing activity. Closes the confabulation-at-source gap.
        screen_present = self._last_screen_obs is not None and getattr(
            self._last_screen_obs, "success", False
        )
        presence_present = self._last_presence_snap is not None and getattr(
            self._last_presence_snap, "success", False
        )
        calendar_present = self._last_calendar_snap is not None and getattr(
            self._last_calendar_snap, "success", False
        )
        signals_present = []
        signals_absent = []
        if True:
            signals_present.append("system stats (CPU/RAM/GPU/disk/processes) — live via psutil")
        if screen_present:
            signals_present.append("screen observation — live")
        else:
            signals_absent.append(
                "screen observation — UNAVAILABLE this cycle (vision source down or capture failed)"
            )
        if presence_present:
            signals_present.append("presence snapshot — live")
        else:
            signals_absent.append("presence snapshot — UNAVAILABLE this cycle")
        if calendar_present:
            signals_present.append("calendar — live")
        else:
            signals_absent.append("calendar — UNAVAILABLE this cycle (OAuth or API)")

        signal_manifest = (
            "SIGNALS PRESENT THIS CYCLE:\n" + "\n".join(f"  ✓ {s}" for s in signals_present) + "\n"
        )
        if signals_absent:
            signal_manifest += (
                "SIGNALS ABSENT THIS CYCLE (do NOT fabricate content for these):\n"
                + "\n".join(f"  ✗ {s}" for s in signals_absent)
                + "\n"
            )

        try:
            _cycle_evidence_envelope = build_envelope(
                ledger_db_path=str(LEDGER_DB_PATH),
                signals_present=signals_present,
                signals_absent=signals_absent,
                tool_results=[],
            )
        except Exception as _env_exc:
            logger.warning(
                "evidence_envelope build failed for daemon_cycle "
                "(continuing without envelope): %s",
                _env_exc,
            )
            _cycle_evidence_envelope = None
        try:
            _cycle_envelope_block = render_envelope_for_prompt(
                _cycle_evidence_envelope,
            )
        except Exception as _env_exc:
            logger.warning(
                "evidence_envelope render failed for daemon_cycle "
                "(continuing without prompt block): %s",
                _env_exc,
            )
            _cycle_evidence_envelope = None
            _cycle_envelope_block = ""
        self._last_cycle_evidence_envelope = _cycle_evidence_envelope

        # Signal manifest is the only per-cycle-dynamic rule-shaped block.
        # It goes in the user message because its content changes based on
        # which signals are present. _STATIC_CYCLE_INSTRUCTIONS (appended
        # to system prompt) references "SIGNALS PRESENT / ABSENT" here.
        prompt += signal_manifest
        if _cycle_envelope_block:
            prompt += _cycle_envelope_block + "\n\n"

        # Store prompt for potential retry use
        self._last_reasoning_prompt = prompt

        # Session 11m: defer this cycle if the owner is mid-conversation on Telegram.
        # Gives the GPU a clean window for his reply. The 15s backoff is set by
        # telegram_voice._process_message right before its ollama.chat call.
        if time.time() < self._rohit_active_until:
            logger.info("Reasoning cycle deferred — the owner is talking")
            return None

        # Skip reasoning if voice command has the GPU
        acquired = self._ollama_lock.acquire(timeout=0)
        if not acquired:
            logger.info("Reasoning cycle skipped — voice command active")
            return None
        try:
            # Session 11p: route daemon reasoning through llm_client so
            # the backend (Ollama or llama.cpp) is env-selectable at call
            # time. When MAEZ_LLM_BACKEND=llamacpp, this hits the CUDA
            # llama-server on 127.0.0.1:8080 running gemma-4-26B-A4B.
            # Default is still ollama — flipping is a service env var
            # change, rolls back cleanly.
            #
            # Stability override: keep daemon reasoning in non-thinking
            # mode on the llama.cpp path. Gemma-4 thinking traces have
            # previously leaked channel/control markup into outputs, and
            # those artifacts can get recycled into future prompts. The
            # daemon path benefits more from parser stability than hidden
            # scratchpad depth right now.
            from core import llm_client as _llm_client

            # Byte-stable system message (SOUL + static cycle instructions)
            # enables llama.cpp KV cache reuse across cycles. self.system_prompt
            # is loaded once at startup; _STATIC_CYCLE_INSTRUCTIONS is a module
            # constant. Their concatenation is identical every cycle.
            system_content = self.system_prompt + "\n\n" + _STATIC_CYCLE_INSTRUCTIONS
            chat_messages = [
                {"role": "system", "content": system_content},
                {"role": "user", "content": prompt},
            ]
            chat_options = {"temperature": 0.7, "num_predict": 300}

            # error_classifier-driven retry: on a TRANSIENT backend error
            # (timeout, connection refused), wait 2s and try once more.
            # On a STRUCTURAL error (gpu_oom, model_missing), skip cleanly
            # without retry — retrying won't help and would stretch the
            # cycle while the operator investigates. Max one retry total,
            # keeping cycle time bounded.
            try:
                response = _llm_client.chat(
                    model=MODEL,
                    messages=chat_messages,
                    think=False,
                    options=chat_options,
                )
            except Exception as first_err:
                try:
                    from core.error_classifier import (
                        classify as _classify,
                        emit_telemetry as _emit_err,
                    )

                    _cls = _classify(first_err)
                    _emit_err(_cls, surface="daemon_cycle")
                except Exception:
                    _cls = None

                # Transient → one retry after a short backoff.
                transient = _cls is not None and _cls.likely_transient and _cls.retryable
                if transient:
                    logger.info(
                        "Cycle %d: %s error, retrying once after 2s backoff",
                        self.cycle_count,
                        _cls.error_class.value,
                    )
                    time.sleep(2.0)
                    try:
                        response = _llm_client.chat(
                            model=MODEL,
                            messages=chat_messages,
                            think=False,
                            options=chat_options,
                        )
                    except Exception as retry_err:
                        try:
                            _emit_err(_classify(retry_err), surface="daemon_cycle_retry")
                        except Exception:
                            pass
                        logger.error(
                            "Cycle %d: retry also failed: %s",
                            self.cycle_count,
                            retry_err,
                        )
                        return None
                else:
                    # Structural / unknown / non-retryable → skip cleanly.
                    logger.error(
                        "Cycle %d: reasoning failed (%s): %s",
                        self.cycle_count,
                        _cls.error_class.value if _cls else "unclassified",
                        first_err,
                    )
                    return None

            content = _extract_final((response.message.content or "").strip())
            thinking = getattr(response.message, "thinking", None)
            if thinking:
                logger.debug("Cycle %d thinking: %s", self.cycle_count, thinking.strip()[:500])
            return content if content else "(empty response)"
        finally:
            self._ollama_lock.release()

    def handle_message(
        self,
        text: str,
        source: str = "unknown",
        *,
        transcript: str = "",
        signals_present: "list | None" = None,
        signals_absent: "list | None" = None,
        chat_history: "list | None" = None,
        tool_calls: "list[dict] | None" = None,
    ) -> str:
        """Process an incoming message through full reasoning context. Returns reply string.

        The returned reply is the AUDITED reply (see
        `core.safety.audited_output.audit_assistant_text`). The stored
        memory record is the same audited text. Callers (e.g. the
        surface adapter) must not re-audit; this is the single source
        of truth for the final reply on the daemon-synthesis path.

        Args:
            text: user's message as received from the surface.
            source: surface label ("telegram_surface", "voice", "UI",
                "web", etc.) — forwarded to audit telemetry.
            transcript: Jarvis tool-use transcript, if a tool loop ran
                before this synthesis. When non-empty, the audit skips
                the judge (real stdout grounds the claim by
                construction). Default "" for direct LLM-only replies.
            signals_present / signals_absent: grounding manifest for
                the audit. Defaults to None (the audit falls back to
                its legacy "infer from surface" behavior) when the
                caller does not know.
            chat_history: prior telegram exchanges — list of dicts
                each with `"content"` in the adapter-cleaned
                `"Rohit: <msg>\\nMaez: <reply>"` shape. When passed,
                each exchange is split into a user/assistant message
                pair and inserted between the system prompt and the
                current turn so the synthesis model can resolve
                anaphoric references (e.g. "it" binding to the
                subject of the prior assistant reply). Silently
                ignored when None; unparseable entries are filtered.
                The 2026-04-24 fix: memory recall alone was missing
                the just-said turn on follow-up questions with low
                keyword overlap (incident: meta-harness at 04:42,
                "it" at 04:53 lost the referent).
        """
        from skills.web_search import (
            search as web_search,
            format_for_context as web_format,
            needs_web_search,
            search_rss,
            is_news_query,
        )

        # Trace harness Slice 1 — start a trace at handle_message entry
        # so every owner-bridge /message turn produces a structured
        # JSONL record in logs/traces/. Trace failures must NEVER break
        # synthesis; the writer fails silent, and every capture below
        # is wrapped in try/except so a degraded trace never short-
        # circuits the reply path.
        _trace = Trace.start(surface=source, user_text=text)
        _trace_t_start = time.time()
        _trace_pre_audit_text: str = ""

        # Slice 2.5b — shadow-write the user_message turn to the
        # ledger. Default-off via MAEZ_LEDGER_WRITES; failures NEVER
        # break the reply path (try_write_turn swallows all exceptions
        # and returns None). The returned turn_id (if any) is captured
        # for future use as parent_turn_id when slice 2.5c plumbs the
        # model_reply turn (gated on slice 3 evidence-envelope work).
        try:
            from core.ledger.writer import try_write_turn as _try_write_turn

            _user_msg_turn_id = _try_write_turn(
                str(LEDGER_DB_PATH),
                "user_message",
                text,
                surface=source,
            )
        except Exception:
            # Belt-and-suspenders: try_write_turn is already exception-
            # safe, but a broken core.ledger import path must never
            # block the daemon. Log nothing here — the helper logs
            # internally when it actually has something to report.
            _user_msg_turn_id = None

        # Inner-residue detection on incoming user text. See
        # core/inner_residue.py — rejection markers become persistent
        # state that shapes the next turn's voice. Silent on failure.
        try:
            from core import inner_residue as _residue

            if _residue.detect_user_rejection(text):
                _residue.record(kind="user_rejection", context={"surface": source})
        except Exception:
            pass

        # Blanket-approval detection. If the user grants time-limited
        # permission in natural language (e.g. "reading is fine"),
        # persist a session so subsequent read-safe commands don't
        # round-trip through a card. Silent on failure. See
        # core/approval_sessions.py.
        try:
            from core import approval_sessions as _approvals

            _granted = _approvals.detect_and_grant(text)
            if _granted:
                logger.info(
                    "approval session granted: kinds=%s source=%s",
                    _granted,
                    source,
                )
        except Exception:
            pass

        # Premise-acceptance audit (2026-04-27 incident). Detect user
        # claims about past Maez actions ("the X you suggested",
        # "I was approving X", "you said X") and verify against the
        # proposal store + audit log. When unverified, the synthesis
        # path receives a system-level flag instructing Maez to ask
        # for clarification rather than silently proceed on a
        # potentially fabricated premise. Advisory, not blocking.
        # Silent on failure — synthesis must not abort on audit error.
        _premise_flag: str | None = None
        try:
            from core.safety.premise_audit import audit_user_premise

            _premise_flag = audit_user_premise(text)
            if _premise_flag:
                logger.info(
                    "premise unverified for surface=%s; flagging "
                    "synthesis to ask for clarification",
                    source,
                )
        except Exception as _premise_exc:
            logger.debug("premise audit skipped: %s", _premise_exc)

        logger.info("%s message: %s", source, text[:100])
        snap = perception_snapshot()
        # Grounding-context starvation fix (2026-05-05): this chat
        # path shows the current perception snapshot to the model, so
        # the audit must receive the same per-turn receipt. The
        # fallback audit manifest only carries stable / bounded-fresh
        # facts; it deliberately marks system stats absent unless the
        # caller supplies a real turn snapshot.
        _chat_signals_present = list(signals_present or [])
        _chat_signals_absent = list(signals_absent or [])
        if signals_present is None and signals_absent is None:
            try:
                from core.safety.audit_signal_manifest import (
                    default_audit_signals,
                )
                _chat_signals_present, _chat_signals_absent = (
                    default_audit_signals(source)
                )
            except Exception as _signals_exc:
                logger.debug(
                    "chat audit fallback manifest unavailable: %s",
                    _signals_exc,
                )
                _chat_signals_present, _chat_signals_absent = [], []

            def _mark_signal_present(name: str, label: str) -> None:
                if label not in _chat_signals_present:
                    _chat_signals_present.append(label)
                _chat_signals_absent[:] = [
                    s for s in _chat_signals_absent
                    if not str(s).lower().startswith(name)
                ]

            def _mark_signal_absent(name: str, label: str) -> None:
                if label not in _chat_signals_absent:
                    _chat_signals_absent.append(label)
                _chat_signals_present[:] = [
                    s for s in _chat_signals_present
                    if not str(s).lower().startswith(name)
                ]

            _mark_signal_present(
                "system stats",
                "system stats (CPU/RAM/GPU/disk/processes) — live via perception_snapshot",
            )

            _screen_state = (
                getattr(self._last_screen_obs, "state", None)
                if self._last_screen_obs is not None
                else None
            )
            if (
                _screen_state == "ok"
                and getattr(self._last_screen_obs, "success", False)
            ):
                _mark_signal_present("screen observation", "screen observation")
            elif _screen_state == "disabled":
                _mark_signal_absent(
                    "screen observation",
                    "screen observation (disabled by policy)",
                )
            elif _screen_state == "unavailable":
                _mark_signal_absent(
                    "screen observation",
                    "screen observation (endpoint unreachable)",
                )
            else:
                _mark_signal_absent("screen observation", "screen observation")

            if self._last_presence_snap is None:
                _mark_signal_absent("presence snapshot", "presence snapshot")
            elif not getattr(self._last_presence_snap, "success", False):
                _err = getattr(self._last_presence_snap, "error", None) or "unknown"
                _mark_signal_absent(
                    "presence snapshot",
                    f"presence snapshot — unavailable: {_err}",
                )
            else:
                _mark_signal_present("presence snapshot", "presence snapshot")

            if self._last_calendar_snap is not None:
                _mark_signal_present("calendar", "calendar")
            else:
                _mark_signal_absent("calendar", "calendar")

        system_state = format_snapshot(snap)
        authoritative_tool_reply = _authoritative_tool_reply(tool_calls)
        recalled = self.memory.recall_for_telegram(text)
        # Trace: capture every memory id surfaced by the recall — across
        # core, daily, raw — so a future harness can verify the model's
        # reply cited evidence the recall actually pulled.
        try:
            _ids: list[str] = []
            for tier_key in ("core", "daily", "raw"):
                for entry in (recalled or {}).get(tier_key, []) or []:
                    eid = entry.get("id")
                    if eid:
                        _ids.append(str(eid))
            _trace.memory_ids = _ids
        except Exception as _trace_exc:
            logger.debug("trace memory_ids capture skipped: %s", _trace_exc)
        # Bound the recall block so a high-recall query (long-content
        # core memories + many raw matches) cannot push the whole
        # prompt past the llama-server context window. Cap is
        # coordinated with the evidence envelope per SLICE_3_0d §1:
        # 52K chars (~13K tokens) when an envelope is present in the
        # prompt; 60K (legacy) when MAEZ_EVIDENCE_ENVELOPE_DISABLED=1.
        # Core + daily are preserved; raw entries drop from the tail
        # if needed. See core.cognition.envelope_builder.
        from core.cognition.envelope_builder import (
            build_envelope as _build_envelope,
            render_envelope_for_prompt as _render_envelope,
            resolve_recall_cap_chars as _resolve_recall_cap,
        )
        memory_block = self.memory.format_for_prompt(
            recalled, max_chars=_resolve_recall_cap(),
        )

        # Slice 3 wiring: build the evidence envelope so the LLM sees
        # what it MAY claim and what's forbidden BEFORE generation,
        # and so the post-generation audit gets the same context.
        # Returns None when MAEZ_EVIDENCE_ENVELOPE_DISABLED=1 — the
        # downstream renderer treats None as empty (legacy prompt
        # shape) and audit_assistant_text falls through to the
        # legacy signals path.
        try:
            _evidence_envelope = _build_envelope(
                ledger_db_path=str(LEDGER_DB_PATH),
                signals_present=_chat_signals_present,
                signals_absent=_chat_signals_absent,
                tool_results=[],
                turn_id=_user_msg_turn_id,
            )
        except Exception as _env_exc:
            # Envelope construction is best-effort; a builder bug
            # MUST NOT block the daemon's reply path. Fall through
            # to the legacy signals-only audit.
            logger.warning(
                "evidence_envelope build failed (continuing without "
                "envelope): %s", _env_exc,
            )
            _evidence_envelope = None
        _envelope_block = _render_envelope(_evidence_envelope)

        # Web search if needed. If a deterministic tool already answered
        # a volatile fact (e.g. currency conversion), do not add web
        # snippets that can override the tool result during synthesis.
        web_context = ""
        if not authoritative_tool_reply and needs_web_search(text):
            logger.info("Web search triggered for: %s", text[:80])
            if is_news_query(text):
                sr = search_rss(text, max_results=5)
            else:
                sr = web_search(text, max_results=3)
            if sr.get("success"):
                web_context = web_format(sr)
                logger.info(
                    "Web search: %d results injected (%s)",
                    sr["result_count"],
                    sr.get("source_type", "web"),
                )

        is_voice = source == "voice"
        prompt = f"{system_state}\n\n"

        # Public bot context — early for attention weight
        public_ctx = self._get_public_context()
        if public_ctx:
            prompt += public_ctx + "\n\n"

        if memory_block:
            prompt += memory_block + "\n\n"
        # Slice 3 wiring: envelope block sits between recall and
        # web_context. Empty string when envelope is None (disabled
        # mode) or the envelope carries no constraints — keeps the
        # legacy prompt shape identical in those cases.
        if _envelope_block:
            prompt += _envelope_block + "\n\n"
        if web_context:
            prompt += (
                f"{web_context}\n\n"
                f"INSTRUCTION: Real search results above. Do NOT list headlines. "
                f"Synthesize into 3-5 sentences. Tell the owner what matters and why. "
                f"Give your opinion. Connect to his context if relevant.\n\n"
            )
        if is_voice:
            prompt += (
                f'the owner just spoke to you out loud:\n"{text}"\n\n'
                f"Respond in 1-2 short sentences. Your response will be spoken aloud.\n"
                f"Be warm, direct, and conversational. No bullet points or markdown.\n\n"
            )
        else:
            prompt += (
                f'the owner sent via {source}:\n"{text}"\n\nRespond directly and concisely.\n\n'
            )
        prompt += (
            "Remember: NEVER suggest touching ollama, its models, or any "
            "process that powers your reasoning."
        )

        # Build system prompt with public bot awareness
        sys_prompt = self.system_prompt
        # Capability registry injection — same wiring as CLI
        # (see core/capability_registry.py). Grounds self-description
        # questions on real facts so the model doesn't invent modules,
        # schedules, or postconditions.
        try:
            from core.capability_registry import prompt_snippet as _cap_snippet

            sys_prompt += "\n\n" + _cap_snippet()
        except Exception:
            pass
        if public_ctx:
            sys_prompt += (
                "\n\nCRITICAL: The [MY CONVERSATIONS] section shows people you spoke with today. "
                "Report those conversations naturally as your own. Never say 'no one' "
                "if conversations are present."
            )

        # Thread prior-turn context into the synthesis. Without this,
        # follow-ups like "you think it'll be useful?" have no referent
        # because the last assistant reply lives only in chat history,
        # not in memory recall (semantic overlap is too low for recall
        # to surface it reliably). See chat_history docstring above.
        messages: list[dict] = [{"role": "system", "content": sys_prompt}]
        try:
            from core.brain.conversation_history import history_to_messages

            messages.extend(history_to_messages(chat_history))
        except Exception as _hist_exc:
            logger.debug("chat_history threading skipped: %s", _hist_exc)
        # Tool transcripts are synthesis context, not owner text. Earlier
        # Telegram routing spliced this block into `text`, which polluted
        # memory/search with internal instructions and made follow-up turns
        # like "Proceed" lose the real action request. Keep owner text clean
        # and give the model tool-state as a system note instead.
        if transcript and transcript.strip():
            try:
                from core.brain_loop import _JARVIS_INSTRUCTION_BLOCK

                messages.append(
                    {
                        "role": "system",
                        "content": (
                            f"{transcript}\n\n"
                            f"{_JARVIS_INSTRUCTION_BLOCK}"
                        ),
                    }
                )
            except Exception as _tool_ctx_exc:
                logger.debug("tool transcript context skipped: %s", _tool_ctx_exc)
        # ADR 0019 Phase 6 — lived recall brief. Built from the user's
        # text (the message they just sent), injected as a system note
        # AFTER chat_history threading and BEFORE premise_flag so the
        # synthesis model reads "what we have lived through together"
        # as background, with the premise flag still landing closest
        # to the user turn. Gated by MAEZ_LIVED_RECALL — default
        # enabled, set to "0" for fast rollback if it degrades chat
        # quality. Build-time exceptions are caught silently; synthesis
        # must continue regardless of the lived layer's health.
        # Session 3 of working-self arc: assemble the current goal
        # hierarchy and pass it through to the lived-recall builder.
        # Conway 2000 working-self modulates retrieval; Park 2023 adds
        # goal-alignment as a fourth scoring component. Gated by
        # MAEZ_WORKING_SELF — DEFAULT DISABLED (opposite of
        # MAEZ_LIVED_RECALL): this path is brand new, not yet
        # probe-validated against regression. Operator opts in by
        # setting "1". Failure is silent: the lived brief still
        # builds without goals.
        _goals = None
        if os.environ.get("MAEZ_WORKING_SELF", "0") == "1":
            try:
                _goals = assemble_goals(
                    episode_store=self.lived_episodes,
                    graph=self.lived_graph,
                    wants=getattr(self, "wants", None),
                    recent_owner_text=text,
                )
            except Exception as _goals_exc:
                logger.debug("working-self goal assembly failed: %s", _goals_exc)
                _goals = None
        # Trace: capture the assembled goals as compact "source: text"
        # labels so the JSONL turn record answers "what did the
        # working self believe was the focus?" An empty/None hierarchy
        # leaves the field at its default empty list.
        try:
            if _goals is not None and not _goals.is_empty:
                _trace.working_self_goals = [
                    f"{g.source}: {g.text}" for g in _goals.goals
                ]
        except Exception as _trace_goals_exc:
            logger.debug("trace working_self_goals capture skipped: %s", _trace_goals_exc)
        _lived_brief = ""
        if os.environ.get("MAEZ_LIVED_RECALL", "1") != "0":
            try:
                _lived_brief = build_lived_recall_brief(
                    text,
                    episode_store=self.lived_episodes,
                    graph=self.lived_graph,
                    max_items=6,
                    goals=_goals,
                )
            except Exception as _lived_exc:
                logger.debug("lived recall brief build failed: %s", _lived_exc)
                _lived_brief = ""
        if _lived_brief:
            messages.append({"role": "system", "content": _lived_brief})

        # Step 5r: inject ambient context (weather, active window,
        # latest iPhone signals) into the chat prompt. The signal
        # pipeline has been ingesting since 2026-04-18 (~80 daily
        # files) and ``wondering_cycle`` already uses this same
        # block — but the chat-message path didn't, so Telegram
        # answers ran without knowing where the owner was or what
        # they were doing. Single-block injection; cached for 60s
        # inside ambient_prompt_block so per-turn cost is bounded.
        # Gated by ``MAEZ_AMBIENT_BRIEF`` (default on, "0" disables)
        # so the env var pattern matches MAEZ_LIVED_RECALL.
        # Step 5v: declared at function scope so the response log
        # below can reference its size without re-pulling.
        _ambient_block = ""
        if os.environ.get("MAEZ_AMBIENT_BRIEF", "1") != "0":
            try:
                from core.memory.ambient_format import ambient_prompt_block
                _ambient_block = ambient_prompt_block()
                if _ambient_block:
                    messages.append({
                        "role": "system",
                        "content": _ambient_block,
                    })
            except Exception as _amb_exc:
                logger.debug(
                    "ambient brief injection failed: %s", _amb_exc,
                )

        # Trace: capture the evidence ids the lived brief surfaced.
        # An empty brief yields an empty list — silence is honest.
        try:
            _trace.lived_recall_ids = _trace_extract_evidence_ids(_lived_brief)
        except Exception as _trace_exc:
            logger.debug("trace lived_recall_ids capture skipped: %s", _trace_exc)
        # Inject the premise-audit flag (if any) as a system note
        # *immediately before* the user turn so the synthesis model
        # treats it as a directive about THIS message specifically,
        # not background context. 2026-04-27 incident fix.
        if _premise_flag:
            messages.append({"role": "system", "content": _premise_flag})
        messages.append({"role": "user", "content": prompt})

        if authoritative_tool_reply:
            reply = authoritative_tool_reply
        else:
            try:
                # Session 11r: via llm_client (was missed in 11p batch)
                from core import llm_client as _llm_client

                response = _llm_client.chat(
                    model=MODEL,
                    messages=messages,
                    think=False,
                    options={"temperature": 0.7, "num_predict": 4096},
                )
                reply = (response.message.content or "").strip() or "(no response)"
            except Exception as e:
                reply = f"Error: {e}"

        # 2026-04-23 Commit 7b: strip tool-call JSON leaks from the raw
        # model output BEFORE audit and BEFORE store. Models occasionally
        # leak <tool_call>...</tool_call> or inline JSON into the final
        # reply text even when the tool-use loop has already run. These
        # leaks are wire-format noise; the owner shouldn't see them and
        # memory shouldn't store them. Previously this cleanup ran in the
        # adapter AFTER handle_message had already returned — meaning
        # stored memory contained the raw JSON even though the owner
        # saw cleaned text. Moving it here makes
        #     stored text == audited text == text returned to caller.
        try:
            from core.brain_loop import strip_tool_call_leaks

            reply = strip_tool_call_leaks(reply)
        except Exception as _strip_exc:
            logger.debug("tool-call-leak strip skipped: %s", _strip_exc)

        # Slice 2 Session 2 — Wondering-Pursuit. Optionally append a
        # proactive utterance BEFORE the audit pass so any LLM-authored
        # wondering content gets screened for fabrication / self-claim
        # leaks via the same audit gate that screens the synthesis
        # reply (audit B1 fix from 2026-04-29 review). The wondering
        # question is LLM-authored by ``daemon/wondering_cycle.py``
        # and stored in SQLite verbatim; treating it as untrusted text
        # at the surface boundary is the only honest path. Lai et al.
        # 2024 (arxiv 2410.12361) framework + Conway 2000 working-self
        # priors; Maez-specific safety: vulnerable-register hard-block
        # is primary, frequency budget across daemon restart via
        # sidecar at ``memory/last_pursuit.json``.
        #
        # Two gates, both must pass:
        #   1. ``MAEZ_WONDERING_PURSUIT=1`` env knob (default OFF —
        #      brand-new path, opt-in until probe-validated).
        #   2. ``identity.proactive_messages()`` policy — bonded shape
        #      requires explicit operator opt-in via per-user policy.
        #
        # Tri-state outcome on the trace (audit M2 fix):
        # ``surface`` (utterance appended), ``hold`` (evaluated but
        # threshold or hard-block held silent), ``errored`` (evaluation
        # raised — distinguish from legitimate hold for observability).
        # Failure is silent at the reply level: any exception leaves
        # the reply untouched and synthesis continues.
        _pursuit_enabled = os.environ.get("MAEZ_WONDERING_PURSUIT", "0") == "1"
        _pursuit_decision = None
        _pursuit_evaluated = False
        _pursuit_error: "str | None" = None
        _pursuit_w_store = None  # captured for record_pursuit below
        if _pursuit_enabled:
            try:
                from core.memory import identity as _identity_mod

                if _identity_mod.proactive_messages():
                    from core.evolution.wonderings import (
                        get_store as _get_w_store,
                    )

                    _pursuit_w_store = _get_w_store()
                    _open_wonderings = _pursuit_w_store.list_open(limit=10) or []
                    _pursuit_decision = decide_pursuit(
                        _open_wonderings,
                        goals=_goals if _goals is not None else GoalHierarchy(),
                        recent_owner_text=text,
                        last_pursuit_at=load_last_pursuit_at(),
                    )
                    _pursuit_evaluated = True
                    if _pursuit_decision is not None:
                        _utterance = format_pursuit_utterance(_pursuit_decision)
                        if _utterance:
                            reply = f"{reply}\n\n{_utterance}"
                            save_last_pursuit_at(
                                time.time(),
                                wondering_id=_pursuit_decision.wondering_id,
                            )
            except Exception as _pursuit_exc:
                logger.debug("wondering-pursuit evaluation failed: %s", _pursuit_exc)
                _pursuit_decision = None
                _pursuit_error = str(_pursuit_exc)[:200]
        # Slice 2 Session 3: record the surface decision in the
        # wonderings store + emit a lived episode (ADR 0019
        # alignment — proactive surfaces are high-signal moments
        # that future reflection should be able to cite). Both are
        # best-effort; failures must not break the reply path.
        if _pursuit_w_store is not None and _pursuit_decision is not None:
            try:
                _pursuit_w_store.record_pursuit(
                    _pursuit_decision.wondering_id,
                    decision="surface",
                    score=_pursuit_decision.proactive_score,
                    components=dict(_pursuit_decision.components),
                )
            except Exception as _record_exc:
                logger.debug("record_pursuit (surface) failed: %s", _record_exc)
            try:
                # Lived-episode emission — ``source_kind="pursuit_surface"``
                # so the lived-recall layer can later surface "Maez
                # surfaced wondering X to owner at time T" as
                # episode-shaped evidence. Conway 2000: reflection-
                # on-action is part of self-memory.
                self.lived_episodes.add(
                    title=f"Surfaced wondering #{_pursuit_decision.wondering_id}",
                    summary=_pursuit_decision.wondering_question[:500],
                    participants=["Maez"],
                    source_memory_ids=[
                        f"pursuit-{_pursuit_decision.wondering_id}-{int(time.time())}",
                    ],
                    source_kind="pursuit_surface",
                    importance=3,
                )
            except Exception as _ep_exc:
                logger.debug(
                    "pursuit-surface episode emission failed: %s",
                    _ep_exc,
                )

        # 2026-04-23 memory-integrity contract: audit BEFORE store + return.
        # See core/safety/audited_output.py for the full invariant.
        # `transcript` is the caller's Jarvis tool-use transcript if a
        # tool loop ran; `in_tool_continuation` is derived from it.
        # Trace: snapshot the pre-audit text so audit.changed_output
        # is a literal pre/post hash comparison, not a guess.
        _trace_pre_audit_text = reply
        try:
            from core.safety.audited_output import audit_assistant_text

            reply = audit_assistant_text(
                reply,
                surface=source,
                transcript=transcript,
                signals_present=_chat_signals_present,
                signals_absent=_chat_signals_absent,
                evidence_envelope=_evidence_envelope,
            )
            try:
                _trace.audit = AuditInfo(
                    ran=True,
                    changed_output=(
                        _trace_hash_text(_trace_pre_audit_text)
                        != _trace_hash_text(reply)
                    ),
                )
            except Exception as _trace_exc:
                logger.debug("trace audit capture skipped: %s", _trace_exc)
        except Exception as _aud_exc:
            logger.warning("handle_message audit fail-open: %s", _aud_exc)
            try:
                _trace.audit = AuditInfo(ran=False, error=str(_aud_exc)[:200])
            except Exception:
                pass

        # Slice 4c.5a — autobiographical continuity turning on.
        # Persist the post-audit owner-private reply as a model_reply row.
        # This is best-effort shadow persistence: the user-facing reply
        # still returns if the ledger is disabled or unavailable.
        try:
            from core.ledger.model_reply_persistence import persist_model_reply

            if getattr(_trace.audit, "ran", False):
                persist_model_reply(
                    db_path=str(LEDGER_DB_PATH),
                    raw_text=reply,
                    surface=source,
                    parent_turn_id=_user_msg_turn_id,
                    model_id=MODEL,
                    prompt_material={
                        "messages": messages,
                        "surface": source,
                        "event": "autobiographical_continuity_turning_on",
                    },
                    soul_material=getattr(self, "system_prompt", ""),
                    evidence_envelope=_evidence_envelope,
                    audit_verdict={
                        "verdict": "post_audit_reply_persisted",
                        "audit_ran": True,
                        "changed_output": bool(
                            getattr(_trace.audit, "changed_output", False)
                        ),
                        "event": "autobiographical_continuity_turning_on",
                    },
                    memory_read_ids=list(
                        getattr(_trace, "lived_recall_ids", []) or []
                    ),
                )
        except Exception as _ledger_reply_exc:
            logger.debug(
                "model_reply ledger persistence skipped: %s",
                _ledger_reply_exc,
            )

        # Tri-state pursuit trace capture (audit M2 fix). The earlier
        # version recorded "hold" on every error path, conflating
        # evaluator-returned-None (legitimate hold) with
        # evaluator-raised-exception (errored). Now distinguished:
        #   - surface  : pursuit fired, utterance appended
        #   - hold     : pursuit evaluated, returned None
        #   - errored  : pursuit raised — observability sees the failure
        #   - ""       : pursuit not run (env disabled)
        try:
            if _pursuit_decision is not None:
                _trace.pursuit_decision = "surface"
                _trace.pursuit_score = float(_pursuit_decision.proactive_score)
                _trace.pursuit_question = _pursuit_decision.wondering_question[:200]
                _trace.pursuit_components = dict(_pursuit_decision.components)
            elif _pursuit_error is not None:
                _trace.pursuit_decision = "errored"
            elif _pursuit_enabled and _pursuit_evaluated:
                _trace.pursuit_decision = "hold"
        except Exception as _trace_pursuit_exc:
            logger.debug("trace pursuit capture skipped: %s", _trace_pursuit_exc)

        # Step 5v — single structured log line per chat turn.
        # Captures what reached the prompt (lived_brief / ambient
        # block sizes) alongside the response shape so journal-grep
        # can answer "did the substrate help?" across many turns
        # without re-running the prompt assembly. Mirrors the
        # _log_expansion_fired shape from Step 5q for greppability.
        # Reply is post-canary-scrub + post-protected-command-scrub
        # at this point; 60-char excerpt is safe for journalctl.
        try:
            _reply_excerpt = (reply or "")[:60]
            if len(reply or "") > 60:
                _reply_excerpt = _reply_excerpt[:59] + "…"
            _user_excerpt = (text or "")[:60]
            if len(text or "") > 60:
                _user_excerpt = _user_excerpt[:59] + "…"
            logger.info(
                "chat_turn handled "
                "source=%s len_user=%d len_lived_brief=%d "
                "len_ambient_block=%d len_reply=%d "
                "user_excerpt=%r reply_excerpt=%r",
                source,
                len(text or ""),
                len(_lived_brief or ""),
                len(_ambient_block or ""),
                len(reply or ""),
                _user_excerpt,
                _reply_excerpt,
            )
        except Exception as _log_exc:
            logger.debug("chat_turn log line failed: %s", _log_exc)

        # 5x.B Pass 1: stored as user_utterance/lived because the
        # exchange is bond transcript. NOTE: the string carries both
        # owner text and Maez reply — 5x.D should treat consolidations
        # of this row as mixed-origin, not pure owner-verbatim.
        self.memory.store_telegram(
            f"the owner ({source}): {text}\nMaez: {reply}",
            provenance_source="user_utterance",
            trust_tier="lived",
        )
        self._ws_broadcast({"type": "message_reply", "text": reply})

        # Trace harness Slice 1 — finalize and emit the trace before
        # returning. Three hashes are recorded so the audit-before-
        # store invariant (stored == sent == final) is *inspectable*:
        # equal hashes confirm; unequal hashes are a real signal for
        # the future deterministic harness. Never raises.
        try:
            _trace.tool_calls = [
                ToolCall(**tc) if isinstance(tc, dict) else tc
                for tc in (tool_calls or [])
            ]
            _final_hash = _trace_hash_text(reply)
            _trace.final_text_hash = _final_hash
            _trace.final_text_excerpt = (reply or "")[:500]
            # Owner-bridge /message: the reply is sent (returned to
            # caller for surface delivery) and stored (via
            # store_telegram above) verbatim. Same hash for all three
            # confirms the invariant held this turn.
            _trace.sent_text_hash = _final_hash
            _trace.stored_text_hash = _final_hash
            _trace.latency_ms = int((time.time() - _trace_t_start) * 1000)
            _trace.terminal_state = "errored" if reply.startswith("Error: ") else "replied"
            default_writer().write(_trace)
        except Exception as _trace_exc:
            logger.warning("trace emission failed (skipping): %s", _trace_exc)

        return reply

    def _get_public_context(self) -> str:
        """Get summary of recent public bot conversations for reasoning context."""
        try:
            import chromadb
            from chromadb.config import Settings
            from datetime import datetime as _dt

            client = chromadb.PersistentClient(
                path=str(BASE_DIR / "memory" / "db" / "public_users"),
                settings=Settings(anonymized_telemetry=False),
            )
            col = client.get_or_create_collection("user_conversations")
            if col.count() == 0:
                return ""
            # Fetch all and filter in Python (timestamps are ISO strings)
            cutoff_iso = _dt.fromtimestamp(time.time() - 86400, tz=timezone.utc).strftime(
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
            search as web_search,
            format_for_context as web_format,
            needs_web_search,
            search_rss,
            is_news_query,
        )

        logger.info("Voice stream: %s", text[:100])

        import datetime as _dt

        simple_patterns = [
            "what time",
            "what day",
            "what date",
            "how are you",
            "hello",
            "hi maez",
            "good morning",
            "good night",
            "good afternoon",
            "good evening",
            "thanks",
            "thank you",
            "who are you",
            "what can you do",
            "tell me a joke",
            "are you there",
            "can you hear",
            "you there",
            "status",
            "what's up",
            "whats up",
            "sup",
        ]
        text_lower = text.lower().strip()
        is_simple = any(p in text_lower for p in simple_patterns)

        if is_simple:
            now_dt = _dt.datetime.now()
            time_str = now_dt.strftime("%I:%M %p").lstrip("0")
            day_str = now_dt.strftime("%A, %B %d, %Y")
            prompt = (
                f"Current time: {time_str}, {day_str}\n\n"
                f'the owner just spoke to you out loud:\n"{text}"\n\n'
                f"Respond in 1 short sentence. Spoken aloud, be natural and warm.\n"
                f"Remember: you are Maez, the owner's AI partner.\n"
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
                if sr.get("success"):
                    web_context = web_format(sr)
            prompt = f"{system_state}\n\n"
            if memory_block:
                prompt += memory_block + "\n\n"
            if web_context:
                prompt += f"{web_context}\n\n"
            prompt += (
                f'the owner just spoke to you out loud:\n"{text}"\n\n'
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
                "http://localhost:11434/api/chat",
                json={
                    "model": MODEL,
                    "messages": [
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    "stream": True,
                    "options": {"temperature": 0.7, "num_predict": num_predict},
                },
                stream=True,
                timeout=60,
            )

            for line in resp.iter_lines():
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                    token = chunk.get("message", {}).get("content", "")
                    if not token:
                        continue

                    full_reply += token
                    sentence_buf += token

                    # Check for sentence boundaries — handles multiple in buffer
                    while True:
                        m = re.search(r"([.!?])\s", sentence_buf)
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

        # Store in memory. 5x.B Pass 1: user_utterance/lived; mixed-
        # origin transcript (see 5x.D).
        self.memory.store_telegram(
            f"the owner (voice): {text}\nMaez: {full_reply}",
            provenance_source="user_utterance",
            trust_tier="lived",
        )
        self._ws_broadcast({"type": "message_reply", "text": full_reply})
        return full_reply

    def _send_morning_briefing(self, snap: dict):
        """Send morning briefing when the owner first sits down. Once per day.

        State is persisted to `{BASE_DIR}/memory/last_briefing.txt` so
        daemon restarts don't reset the once-per-day guarantee. Before
        the persistence fix (observed 2026-04-22: 3 briefings in 34
        minutes after several restarts), `_last_briefing_date` was
        in-memory only and every restart re-enabled the briefing.

        2026-04-24 audit pass (see docs/audit_2026-04-24/
        autonomous_surface_audit.md, F1): (a) the briefing now goes
        through `audit_assistant_text` before send so an LLM
        fabrication has the same backstop as interactive replies;
        (b) briefing stamp path uses `BASE_DIR` so the daemon works in
        CI and on non-dev installs; (c) the LLM prompt uses
        `display_name()` instead of the ungrammatical "the owner his"
        role label; (d) the sent briefing is stored in telegram
        memory so `chat_history` threading surfaces it as a prior
        assistant turn when the owner replies.
        """
        from core import paths as _paths
        from core.memory.identity import display_name as _display_name

        today = time.strftime("%Y-%m-%d")
        briefing_stamp = _paths.home() / "memory" / "last_briefing.txt"
        try:
            if briefing_stamp.exists():
                persisted = briefing_stamp.read_text().strip()
                if persisted == today:
                    # Already sent today; cache in-memory too so we don't
                    # re-read the file on every presence-arrival check.
                    self._last_briefing_date = today
                    return
        except Exception:
            pass
        if self._last_briefing_date == today:
            return
        hour = int(time.strftime("%H"))
        if hour < 5 or hour > 11:
            return

        self._last_briefing_date = today
        try:
            briefing_stamp.parent.mkdir(parents=True, exist_ok=True)
            briefing_stamp.write_text(today)
        except Exception as e:
            logger.debug("couldn't persist briefing stamp: %s", e)
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

            news = search_rss("general", 3)
            news_text = web_fmt(news) if news.get("success") else "No news loaded."

            # System
            disk_pct = snap["disk"].get("/", {}).get("percent", 0)
            stats = self.memory.memory_stats()
            _briefing_signals_present = ["git status summary", "system stats"]
            _briefing_signals_absent = []
            if self._last_calendar_snap is not None and getattr(
                self._last_calendar_snap, "success", False,
            ):
                _briefing_signals_present.append("calendar")
            else:
                _briefing_signals_absent.append("calendar")
            if news.get("success"):
                _briefing_signals_present.append("rss news search")
            else:
                _briefing_signals_absent.append("rss news search")

            owner_name = _display_name() or "Friend"
            briefing_prompt = (
                f"You are sending {owner_name}'s morning briefing.\n"
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
            _evidence_envelope = self._build_audit_evidence_envelope(
                surface="morning_briefing",
                signals_present=_briefing_signals_present,
                signals_absent=_briefing_signals_absent,
            )
            try:
                from core.cognition.envelope_builder import (
                    render_envelope_for_prompt as _render_envelope,
                )

                _envelope_block = _render_envelope(_evidence_envelope)
            except Exception as _env_exc:
                logger.warning(
                    "evidence_envelope render failed for morning_briefing "
                    "(continuing without prompt block): %s",
                    _env_exc,
                )
                _evidence_envelope = None
                _envelope_block = ""

            # Session 11r: via llm_client (was missed in 11p batch)
            from core import llm_client as _llm_client

            _messages = [{"role": "system", "content": self.system_prompt}]
            if _envelope_block:
                _messages.append({"role": "system", "content": _envelope_block})
            _messages.append({"role": "user", "content": briefing_prompt})
            response = _llm_client.chat(
                model=MODEL,
                messages=_messages,
                think=False,
                options={"temperature": 0.5, "num_predict": 4096},
            )
            briefing = (response.message.content or "").strip()
            if briefing:
                # 2026-04-24: audit before send. Same contract as the
                # interactive reply path — stored text == sent text ==
                # audited text. surface="morning_briefing" so audit
                # telemetry can bucket this path.
                try:
                    from core.safety.audited_output import audit_assistant_text

                    briefing = audit_assistant_text(
                        briefing,
                        surface="morning_briefing",
                        signals_present=_briefing_signals_present,
                        signals_absent=_briefing_signals_absent,
                        evidence_envelope=_evidence_envelope,
                    )
                except Exception as _aud_exc:
                    logger.warning(
                        "morning_briefing audit fail-open: %s",
                        _aud_exc,
                    )
                final_msg = f"Morning briefing:\n\n{briefing}"
                self.telegram.send_message(final_msg)
                logger.info("Morning briefing sent")
                # Store as a telegram exchange so chat_history threading
                # picks it up when the owner replies. Placeholder user
                # turn ([just arrived]) keeps the stored shape
                # consistent with `_clean_exchange`'s parse expectation.
                try:
                    # 5x.B Pass 1: introspection/lived — `[just arrived]`
                    # is a synthetic presence token, not owner text. The
                    # entire stored row is Maez's morning monologue
                    # triggered by owner presence; tagging this as
                    # user_utterance would leak Maez-authored briefings
                    # into 5x.D's "owner said X" filter.
                    self.memory.store_telegram(
                        f"the owner (morning_briefing): [just arrived]\nMaez: {briefing}",
                        provenance_source="introspection",
                        trust_tier="lived",
                    )
                except Exception as _store_exc:
                    logger.debug(
                        "morning_briefing memory store skipped: %s",
                        _store_exc,
                    )

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
            reasons.append(
                f"Root disk {disk_free_pct:.1f}% free (threshold: {self.DISK_THRESHOLD}%)"
            )
        if self._high_cpu_streak >= self.CPU_STREAK_REQUIRED:
            reasons.append(f"CPU sustained {cpu_pct}% for {self._high_cpu_streak} cycles")

        if not reasons:
            return

        # Enforce 30-minute cooldown
        now = time.time()
        elapsed = now - self._last_alert_time
        if self._last_alert_time > 0 and elapsed < self.ALERT_COOLDOWN:
            logger.info(
                "Alert suppressed (cooldown: %dm remaining): %s",
                int((self.ALERT_COOLDOWN - elapsed) / 60),
                ", ".join(reasons),
            )
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
        """Run WebSocket server in its own event loop.

        Shutdown hygiene (2026-05-05, T1.9 second-instance fix
        caught by Codex on the dce9fa5 deploy): unlike surface_v2,
        the serve() coroutine here does `await asyncio.Future()`
        — an unresolvable forever-await. There is NO cooperative
        exit path; stop() must call `_ws_loop.call_soon_threadsafe
        (_loop.stop)` to break us out, and that produces
        `RuntimeError("Event loop stopped before Future
        completed.")`. We catch that RuntimeError as the expected
        shutdown shape WHEN we know we're shutting down
        (`self.running` is False). A real loop-crash during
        operation still surfaces as ERROR.
        """
        self._ws_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._ws_loop)

        async def serve():
            async with websockets.serve(self._ws_handler, "127.0.0.1", WS_PORT):
                logger.info("WebSocket server started on port %d", WS_PORT)
                await asyncio.Future()  # run forever

        try:
            self._ws_loop.run_until_complete(serve())
        except RuntimeError as e:
            # The expected shutdown shape: stop() called
            # _loop.call_soon_threadsafe(_loop.stop), the forever-
            # await got interrupted, run_until_complete raised
            # "Event loop stopped before Future completed."
            # Recognize this as expected when self.running is
            # False; surface it as ERROR otherwise.
            if not self.running:
                logger.info(
                    "WebSocket server: graceful shutdown "
                    "(loop stopped during shutdown)"
                )
            else:
                logger.exception(
                    "WebSocket server: unexpected runtime error "
                    "while self.running=True: %s", e,
                )

    def _start_health_broadcast(self):
        """Broadcast health stats every 10 seconds."""
        while self.running:
            try:
                snap = perception_snapshot()
                gpu = snap.get("gpu") or {}
                self._ws_broadcast(
                    {
                        "type": "health",
                        "system": {
                            "cpu_percent": snap["cpu"]["percent"],
                            "ram_percent": snap["ram"]["percent"],
                            "gpu_percent": gpu.get("utilization_pct"),
                            "gpu_temp_c": gpu.get("temperature_c"),
                        },
                    }
                )
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
                        f"Missed consolidation recovered.\nStats: {self.memory.memory_stats()}"
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

            logger.info(
                "Next consolidation in %.1f hours at %s",
                wait_seconds / 3600,
                target.strftime("%Y-%m-%d %H:%M"),
            )

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
                    if not cq["passed"]:
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
                    types_str = ", ".join(c["action_type"] for c in candidates)
                    send_dev(
                        f"Maez has earned higher autonomy for: {types_str}.\n"
                        f"Reply /promote <action_type> to lower its tier."
                    )
                    logger.info("Trust promotion candidates: %s", types_str)
            except Exception as e:
                logger.debug("Trust promotion check failed: %s", e)

            # Evolution cycle after self-analysis
            evo_summary = {"experiments": 0, "failed": 0, "deployed": 0, "flagged": 0}
            try:
                from skills.evolution_engine import run_evolution_cycle
                from skills.self_analysis import get_weaknesses

                weaknesses = get_weaknesses(self.memory)
                if weaknesses:
                    logger.info("Evolution: %d weaknesses found", len(weaknesses))
                    self._evolution_summary = run_evolution_cycle(
                        weaknesses,
                        telegram_callback=send_dev,
                    )
                    evo_summary = self._evolution_summary
                else:
                    logger.info("No weaknesses — skipping evolution")
            except Exception as e:
                logger.error("Evolution cycle failed: %s", e)

            # Unified nightly summary card
            try:
                from skills.dev_notifier import send_nightly_card
                from skills.self_analysis import analyze as _self_analyze

                analysis = _self_analyze(self.memory, self.actions) or {}
                top_topics = []
                try:
                    # Best-effort top topics from cognition recent buffer
                    from core.cognition_quality import _recent_topics
                    import collections as _cc

                    if _recent_topics:
                        top_topics = _cc.Counter(_recent_topics[-50:]).most_common(3)
                except Exception:
                    pass
                send_nightly_card(
                    memories_analyzed=analysis.get(
                        "total_analyzed", self.memory.memory_stats().get("raw", 0)
                    ),
                    unique_insight_rate=analysis.get("unique_insight_rate", 0),
                    top_topics=top_topics,
                    proposals_attempted=evo_summary.get("experiments", 0),
                    proposals_failed=evo_summary.get("failed", 0),
                )
            except Exception as e:
                logger.debug("Nightly card failed: %s", e)

        logger.info("Consolidation thread stopped.")

    def _capability_planning_loop(self):
        """D20 Stage-5 — hourly poller for the capability-acquisition
        queue. Walks queued rows that don't yet have a draft
        integration plan, calls the planner, persists the result,
        and surfaces a PendingCard for owner review when one lands.

        Hourly cadence (not every cycle): the queue fills slowly
        because every entry requires a prior consent-card approval.
        Hourly is responsive enough for human-review windows and
        keeps the load on llama-server / disk negligible.
        """
        logger.info(
            "Capability planning thread started (interval: 1h)"
        )

        # First tick after a short startup delay so the daemon's
        # primary loops settle before this side-channel runs.
        startup_delay = 60.0
        slept = 0.0
        while slept < startup_delay and self.running:
            time.sleep(min(10.0, startup_delay - slept))
            slept += 10.0

        # T2.6 (2026-05-04 audit) — bounded exponential backoff on
        # exception. Previously every failed tick still slept the
        # full 3600s before retry AND the log line included only
        # the exception message (not its class), so an operator
        # never saw what was actually breaking.
        _BACKOFF_SEED_S = 60.0
        _BACKOFF_CAP_S = 3600.0
        _NORMAL_INTERVAL_S = 3600.0
        backoff_s = _BACKOFF_SEED_S

        while self.running:
            tick_failed = False
            try:
                from core.infra.capability_acquisition_queue import (
                    AcquisitionQueue,
                )
                from core.infra.capability_integration_plans import (
                    IntegrationPlanStore, poll_and_plan,
                )

                q = AcquisitionQueue()
                plans = IntegrationPlanStore()
                new_plan_ids = poll_and_plan(queue=q, plans=plans)

                # For each freshly-persisted plan, surface a
                # consent card so the owner can approve / reject
                # the plan before any implementation work begins.
                for plan_id in new_plan_ids:
                    self._surface_integration_plan_card(plans, plan_id)
            except Exception as e:
                tick_failed = True
                logger.warning(
                    "Capability planning loop tick failed: "
                    "%s: %s — backing off %.0fs",
                    type(e).__name__, e, backoff_s,
                )

            # On success, reset backoff and use the normal hourly
            # interval. On failure, sleep the current backoff then
            # double it (capped at 3600s) for the next failure.
            if tick_failed:
                next_sleep = backoff_s
                backoff_s = min(backoff_s * 2.0, _BACKOFF_CAP_S)
            else:
                backoff_s = _BACKOFF_SEED_S
                next_sleep = _NORMAL_INTERVAL_S

            # Sleep in 60s (or smaller) increments so shutdown
            # remains responsive even during a long backoff.
            slept = 0.0
            while slept < next_sleep and self.running:
                time.sleep(min(60.0, next_sleep - slept))
                slept += 60.0

        logger.info("Capability planning thread stopped.")

    def _surface_integration_plan_card(self, plans, plan_id):
        """Create a PendingCard for a draft integration plan so the
        owner can review and approve it. Idempotent across hourly
        cycles because PendingCardStore.create_card supersedes prior
        open cards in the same chat_id, and because plans whose
        status has moved past 'draft' are excluded by the poller's
        skip-existing logic upstream."""
        try:
            row = next(
                (p for p in plans.list_all() if p["plan_id"] == plan_id),
                None,
            )
            if row is None:
                return
            plan_json = row.get("plan_json") or {}
            cap_id = row.get("capability_id", "unknown")
            summary = plan_json.get("summary", "")
            files = plan_json.get("proposed_files") or []
            tests = plan_json.get("proposed_tests") or []
            risks = plan_json.get("risks") or []
            plain = (
                f"Integration plan ready for review: **{cap_id}**\n\n"
                f"Summary: {summary}\n"
                f"Proposed files: {len(files)}  ·  "
                f"proposed tests: {len(tests)}  ·  "
                f"risks flagged: {len(risks)}\n\n"
                f"Approve to mark plan_approved (no code change yet — "
                f"implementation is a separate slice). Deny to discard."
            )
            from core.decision.pending_cards import PendingCardStore
            store = PendingCardStore()
            try:
                from core.identity import (
                    user_profile_id as _owner_user_id,
                )
                owner = _owner_user_id()
            except Exception:
                owner = "owner"
            # Per-plan chat_id so PendingCardStore's chat-scoped
            # supersession doesn't steamroll concurrent draft plans.
            # Without this, two draft plans in the same hourly tick
            # would race (second card supersedes first) and only the
            # latest would be actionable. user_id stays the owner so
            # `/pending` and cockpit lookups continue to find these.
            plan_bucket = f"capability_plan:{plan_id}"
            store.create_card(
                action="integration.review_plan",
                params={
                    "plan_id": plan_id,
                    "queue_id": row["queue_id"],
                    "capability_id": cap_id,
                },
                reason="capability-acquisition Stage 5 plan",
                plain_english=plain,
                chat_id=plan_bucket,
                user_id=str(owner),
            )
            logger.info(
                "capability_integration_plans: surfaced card for "
                "plan_id=%s capability_id=%s",
                plan_id, cap_id,
            )
        except Exception as e:
            logger.warning(
                "capability_integration_plans: surface_card failed "
                "for plan_id=%s: %s",
                plan_id, e,
            )

    def _nightly_journal_loop(self):
        """Write a daily journal entry to PROGRESS.md at 11:00 PM local time."""
        logger.info("Journal thread started (target: 23:00 local)")

        while self.running:
            now = datetime.now().astimezone()
            target = now.replace(hour=23, minute=0, second=0, microsecond=0)
            if now >= target:
                target += timedelta(days=1)
            wait_seconds = (target - now).total_seconds()

            logger.info(
                "Next journal entry in %.1f hours at %s",
                wait_seconds / 3600,
                target.strftime("%Y-%m-%d %H:%M"),
            )

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
                    text = l[idx + 9 :].strip()
                    if text and text != "(empty response)":
                        sample_responses.append(text[:200])

        prompt_context = (
            f"Date: {date_str} ({day_name})\n"
            f"Reasoning cycles today: {cycle_count}\n"
            f"Errors: {len(errors)}\n"
            f"Warnings: {len(warnings)}\n"
            f"Alerts sent to the owner: {alerts_sent}\n"
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
        _journal_signals_present = [
            "daemon_logs",
            "memory_stats",
            "perception_snapshot",
        ]
        _journal_signals_absent: list[str] = []
        _evidence_envelope = self._build_audit_evidence_envelope(
            surface="nightly_journal",
            signals_present=_journal_signals_present,
            signals_absent=_journal_signals_absent,
        )
        try:
            from core.cognition.envelope_builder import (
                render_envelope_for_prompt as _render_envelope,
            )

            _envelope_block = _render_envelope(_evidence_envelope)
        except Exception as _env_exc:
            logger.warning(
                "evidence_envelope render failed for nightly_journal "
                "(continuing without prompt block): %s",
                _env_exc,
            )
            _evidence_envelope = None
            _envelope_block = ""
        if _envelope_block:
            summary_prompt += "\n\n" + _envelope_block

        try:
            # Session 11r: via llm_client (was missed in 11p batch)
            from core import llm_client as _llm_client

            response = _llm_client.chat(
                model=MODEL,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": summary_prompt},
                ],
                think=False,
                options={"temperature": 0.3, "num_predict": 4096},
            )
            summary = (response.message.content or "").strip()
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

        try:
            from core.safety.audited_output import audit_assistant_text

            summary = audit_assistant_text(
                summary,
                surface="nightly_journal",
                signals_present=_journal_signals_present,
                signals_absent=_journal_signals_absent,
                evidence_envelope=_evidence_envelope,
            )
        except Exception as e:
            logger.debug("Nightly journal audit fail-open: %s", e)

        # Append to PROGRESS.md
        progress_path = BASE_DIR / "PROGRESS.md"
        entry = f"\n\n---\n\n## Daily Journal — {date_str} ({day_name})\n\n{summary}\n"

        with open(progress_path, "a") as f:
            f.write(entry)

        logger.info("Journal entry written for %s (%d chars)", date_str, len(entry))

        # Also store the journal as a core memory. 5x.B Pass 1:
        # introspection/lived because the journal is Maez reflecting
        # on the day, not an infrastructure write.
        self.memory.store_core(
            f"[Journal {date_str}] {summary[:500]}",
            source="nightly_journal",
            provenance_source="introspection",
            trust_tier="lived",
        )

        try:
            self._write_developmental_heartbeat(
                date_str=date_str,
                day_name=day_name,
                journal_summary=summary,
                cycle_count=cycle_count,
                error_count=len(errors),
                warning_count=len(warnings),
                action_count=len(action_lines),
                alert_count=alerts_sent,
                stats=stats,
            )
        except Exception as e:
            logger.warning("Developmental heartbeat failed: %s", e)

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

    def _write_developmental_heartbeat(
        self,
        *,
        date_str: str,
        day_name: str,
        journal_summary: str,
        cycle_count: int,
        error_count: int,
        warning_count: int,
        action_count: int,
        alert_count: int,
        stats: dict,
    ) -> str | None:
        """Store one audited daily self-continuity core memory."""
        from core.brain.developmental_heartbeat import (
            HeartbeatEvidence,
            already_recorded,
            build_prompt,
            fallback_heartbeat,
            normalize_heartbeat,
            record_if_absent,
        )

        if already_recorded(self.memory, date_str):
            logger.info("Developmental heartbeat already recorded for %s", date_str)
            return None

        try:
            from core.memory.identity import display_name as _display_name

            owner_name = _display_name()
        except Exception:
            owner_name = "the owner"
        _continuity_available = False
        try:
            from core.brain.continuity_ledger import summarize_day

            continuity_summary = summarize_day(date_str)
            _continuity_available = True
        except Exception as e:
            logger.debug("Continuity ledger summary unavailable: %s", e)
            continuity_summary = "Continuity probe summary unavailable."

        evidence = HeartbeatEvidence(
            date=date_str,
            day_name=day_name,
            cycle_count=cycle_count,
            error_count=error_count,
            warning_count=warning_count,
            action_count=action_count,
            alert_count=alert_count,
            raw_count=int(stats.get("raw", 0)),
            daily_count=int(stats.get("daily", 0)),
            core_count=int(stats.get("core", 0)),
            owner_name=owner_name,
            journal_summary=journal_summary,
            continuity_summary=continuity_summary,
        )
        _heartbeat_signals_present = [
            "nightly_journal",
            "memory_stats",
            "daemon_logs",
        ]
        _heartbeat_signals_absent: list[str] = []
        if _continuity_available:
            _heartbeat_signals_present.append("continuity_ledger")
        else:
            _heartbeat_signals_absent.append("continuity_ledger")
        _evidence_envelope = self._build_audit_evidence_envelope(
            surface="developmental_heartbeat",
            signals_present=_heartbeat_signals_present,
            signals_absent=_heartbeat_signals_absent,
        )
        try:
            from core.cognition.envelope_builder import (
                render_envelope_for_prompt as _render_envelope,
            )

            _envelope_block = _render_envelope(_evidence_envelope)
        except Exception as _env_exc:
            logger.warning(
                "evidence_envelope render failed for developmental_heartbeat "
                "(continuing without prompt block): %s",
                _env_exc,
            )
            _evidence_envelope = None
            _envelope_block = ""

        try:
            from core import llm_client as _llm_client

            _messages = [{"role": "system", "content": self.system_prompt}]
            if _envelope_block:
                _messages.append({"role": "system", "content": _envelope_block})
            _messages.append({"role": "user", "content": build_prompt(evidence)})
            response = _llm_client.chat(
                model=MODEL,
                messages=_messages,
                think=False,
                options={"temperature": 0.2, "num_predict": 700},
            )
            heartbeat = normalize_heartbeat(
                (response.message.content or "").strip(),
                evidence,
            )
        except Exception as e:
            logger.debug("Developmental heartbeat model failed: %s", e)
            heartbeat = fallback_heartbeat(evidence)

        try:
            from core.safety.audited_output import audit_assistant_text

            heartbeat = audit_assistant_text(
                heartbeat,
                surface="developmental_heartbeat",
                signals_present=_heartbeat_signals_present,
                signals_absent=_heartbeat_signals_absent,
                evidence_envelope=_evidence_envelope,
            )
            heartbeat = normalize_heartbeat(heartbeat, evidence)
        except Exception as e:
            logger.debug("Developmental heartbeat audit fail-open: %s", e)

        memory_id = record_if_absent(self.memory, evidence, heartbeat)
        if memory_id:
            logger.info("Developmental heartbeat stored: %s", memory_id)
        return memory_id

    def _loop(self):
        """Main reasoning loop — runs every LOOP_INTERVAL seconds."""
        logger.info("Reasoning loop started (interval: %ds)", LOOP_INTERVAL)

        while self.running:
            self.cycle_count += 1
            self.last_cycle_time = datetime.now(timezone.utc).isoformat()
            cycle_start = time.time()

            logger.info("--- Cycle %d ---", self.cycle_count)

            # 5x.F.A — reset the per-cycle recall-context bag at cycle
            # top. Populated after `recall_for_cycle` (line ~1077);
            # F.B will read it from `_do_update_baseline` to apply the
            # any-untrusted-tips downgrade rule.
            #
            # ORDERING: reset MUST precede `execute_pending` below.
            # Tier-0 `update_baseline` (per 5x.D.B1) fires same-cycle,
            # so when F.B's consumer runs in this cycle it should see
            # the freshly-empty bag, then the bag refills after
            # `recall_for_cycle` later in the cycle. If a future
            # maintainer "tidies" by moving the reset after
            # `execute_pending`, prior-cycle untrusted IDs would
            # persist into this cycle's first reads — silently
            # over-downgrading. Don't reorder without revisiting
            # F.B's invariant.
            self._cycle_recall_context = _crc_empty()

            # Execute deferred actions from previous cycle
            tier1_results = self.actions.execute_pending()
            tier2_results = self.actions.execute_tier2_pending()
            for r in tier1_results + tier2_results:
                logger.info("Deferred action result: %s", r)

            # Session 11z Part 2: fire due card reminders.
            # Any pending_cards row in 'deferred' status whose remind_at
            # has arrived gets re-presented to the owner on whatever channel
            # the original card was sent on. This is the mechanism that
            # makes "wait an hour" actually work — Maez proactively comes
            # back when the hour is up. Failure here must never crash
            # the cycle, so the whole block is guarded.
            try:
                pipe = (
                    self.telegram._get_pipeline()
                    if hasattr(self.telegram, "_get_pipeline")
                    else None
                )
                if pipe is not None:
                    due = pipe.tick_reminders()
                    if due:
                        logger.info("Re-presented %d deferred card(s)", len(due))
                    # Also expire cards that have been sitting untouched
                    # for > 7 days so the open-card list stays finite.
                    expired = pipe.card_store.expire_abandoned(older_than_seconds=7 * 86400)
                    if expired:
                        logger.info("Expired %d abandoned card(s)", expired)
            except Exception as e:
                logger.debug("card reminder tick failed: %s", e)

            # Broadcast cycle start to UI
            self._ws_broadcast({"type": "cycle_start", "cycle": self.cycle_count})

            # Collect system perception
            snap = perception_snapshot()
            logger.info(
                "Perception: CPU %.1f%%, RAM %.1f%%, GPU %s%%, %s°C",
                snap["cpu"]["percent"],
                snap["ram"]["percent"],
                snap["gpu"]["utilization_pct"] if snap.get("gpu") else "N/A",
                snap["gpu"]["temperature_c"] if snap.get("gpu") else "N/A",
            )

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
                        logger.info(
                            "Calendar: %d events upcoming", len(self._last_calendar_snap.events)
                        )
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
                                logger.info(
                                    "Calendar alert sent: %s in %dm", event.title, threshold
                                )
                            except Exception as te:
                                logger.warning("Calendar Telegram alert failed: %s", te)
                    else:
                        logger.debug("Calendar fetch failed: %s", self._last_calendar_snap.error)
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
                            logger.info("the owner left desk — noted")

                        # Track arrivals and greet based on absence duration
                        if self._last_presence_snap.just_arrived:
                            self._greeted_this_session = False

                            # Calculate absence duration
                            absence_secs = 0
                            if self._last_departure_time is not None:
                                absence_secs = time.time() - self._last_departure_time
                            self._last_absence_duration = absence_secs
                            # T2.5 (2026-05-04 audit) — clear the
                            # departure stamp now that we've consumed
                            # it. Otherwise a stale departure time
                            # leaks into the NEXT arrival's absence
                            # calc if presence-detection ever fires
                            # two arrivals without an intervening
                            # explicit departure (e.g. a brief face-
                            # detection dropout that does not produce
                            # just_left=True). Clean slate for the
                            # next departure-detection cycle.
                            self._last_departure_time = None

                            # Suppress greetings within 2 minutes of daemon start
                            startup_grace = True
                            try:
                                with open("/tmp/maez_started_at") as f:
                                    started = float(f.read().strip())
                                startup_grace = time.time() - started > 120
                            except Exception:
                                pass

                            if (
                                person in ("the owner", "unknown")
                                and startup_grace
                                and not self._greeted_this_session
                            ):
                                if absence_secs < 1200:
                                    # Under 20 minutes — no greeting
                                    logger.debug(
                                        "the owner back after %.0fs — no greeting (< 20min)",
                                        absence_secs,
                                    )
                                else:
                                    # 2026-04-25: simplified greeting —
                                    # name + absence duration only. No
                                    # re-quoting prior exchanges; that
                                    # duplicated chat_history threading
                                    # (commit cc462c5) and led to uncanny
                                    # re-quotes of casual greetings and
                                    # closed remarks. See
                                    # core/brain/return_greeting.py.
                                    from core.brain.return_greeting import (
                                        compose_return_greeting,
                                    )
                                    from core.memory.identity import (
                                        display_name as _display_name,
                                    )

                                    msg = compose_return_greeting(
                                        display_name=_display_name(),
                                        absence_secs=absence_secs,
                                    )
                                    if msg:
                                        self.telegram.send_message(msg)
                                        self._greeted_this_session = True
                                        self._last_greeted_at = time.time()
                                        hrs = int(absence_secs // 3600)
                                        mins = int((absence_secs % 3600) // 60)
                                        logger.info(
                                            "Greeted %s (away %dh %dm)",
                                            _display_name(),
                                            hrs,
                                            mins,
                                        )

                        # Morning briefing check
                        if self._last_presence_snap.just_arrived and person in (
                            "the owner",
                            "unknown",
                        ):
                            self._send_morning_briefing(snap)

                        # Stranger detected — log, don't greet
                        if self._last_presence_snap.rohit_present and person == "stranger":
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
                # Cache dirty-repo count for the perception-signature gate.
                try:
                    from skills.git_awareness import scan_all

                    self._last_git_dirty_count = sum(1 for r in scan_all() if r.get("is_dirty"))
                except Exception as e:
                    logger.debug("git dirty count update failed: %s", e)

            # GitHub — every 10 cycles
            self._github_counter += 1
            if self._github_counter >= 10:
                self._github_counter = 0
                try:
                    self._last_github_block = self.github.get_context_block()
                except Exception as e:
                    logger.debug("GitHub context failed: %s", e)

            # Reddit — every 15 cycles. After fetching the in-cycle
            # context block, persist newly-cached posts to raw memory
            # so audit pipelines can verify Maez's Reddit references.
            # 2026-04-27 incident: a TRELLIS.2 reference was correctly
            # surfaced in-cycle but invisible to audits because Reddit
            # signals weren't persisted. persist_to_memory closes that
            # gap; both sides of the fix have to land for the audit
            # path to see the signal.
            self._reddit_counter += 1
            if self._reddit_counter >= 15:
                self._reddit_counter = 0
                try:
                    self._last_reddit_block = self.reddit.get_context_block()
                except Exception as e:
                    logger.debug("Reddit context failed: %s", e)
                try:
                    written = self.reddit.persist_to_memory(
                        self.memory, cycle=self.cycle_count,
                    )
                    if written:
                        logger.info(
                            "reddit persistence: %d new posts to raw memory",
                            written,
                        )
                except Exception as e:
                    logger.debug("Reddit persist failed: %s", e)

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
            if self.cycle_count % 240 == 0 and snap["disk"].get("/", {}).get("percent", 0) > 75:
                try:
                    report = disk_scan()
                    if report["total_bytes"] > 100 * 1024 * 1024:
                        msg = disk_msg(report)
                        send_dev(msg)
                        self._pending_cleanup = report
                        logger.info(
                            "Disk cleanup proposed: %.0f MB", report["total_bytes"] / (1024 * 1024)
                        )
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
                        if critique.get("should_write_soul_note") and critique.get(
                            "soul_note_reason"
                        ):
                            reason = critique["soul_note_reason"]
                            soul_text = self.system_prompt or ""
                            if reason[:60] not in soul_text:
                                logger.info("Cognition soul note: %s", reason[:100])
                                self.actions.write_soul_note(reason)
                            else:
                                logger.debug("Cognition soul note deduped — already in soul.md")
                except Exception as e:
                    logger.debug("Cognition critique failed: %s", e)

            # Self-reflection — periodic insight check
            # 11u fix: dedup against soul.md AND track last-written insight
            # to prevent the same insight being appended hundreds of times.
            # The substring check alone failed when a consolidated lessons
            # section paraphrased the insight (past vs present tense).
            self._reflection_cycle_counter += 1
            if self._reflection_cycle_counter >= self.REFLECTION_EVERY_N_CYCLES:
                self._reflection_cycle_counter = 0
                try:
                    insight = self._quality_tracker.format_insight_for_soul()
                    if insight:
                        # Dedup by key concepts, not exact text
                        soul_lower = (self.system_prompt or "").lower()
                        insight_lower = insight.lower()
                        # If soul.md mentions "approval rate" AND this insight
                        # is about approval rate, it's a duplicate lesson
                        key_concepts = ["approval rate", "fixation", "repetition"]
                        covered = sum(
                            1 for k in key_concepts if k in soul_lower and k in insight_lower
                        )
                        # Also dedup against last-written insight
                        last = getattr(self, "_last_reflection_insight", None)
                        if covered > 0 or insight == last:
                            logger.debug("Self-reflection deduped — concepts already in soul.md")
                        else:
                            logger.info("Self-reflection insight: %s", insight[:100])
                            self.actions.write_soul_note(insight)
                            self._last_reflection_insight = insight
                except Exception as e:
                    logger.warning("Self-reflection error: %s", e)

            # 2026-04-25 disk-fixation patches. See
            # core/cognition/perception_signature.py.
            #   Patch B: skip the LLM when perception axes match the
            #     last stored thought (with a 5-min floor).
            #   Patch A: when the LLM does run, strip stale fields
            #     (axes constant across last 3 thoughts) from the
            #     prompt so the model can't fixate on what it can't
            #     see.
            from core.cognition.perception_signature import (
                extract_axes,
                signature_from_axes,
                should_skip_reasoning,
                stale_fields,
            )

            _presence_state = (
                "at_desk"
                if (self._last_presence_snap is not None and self._last_presence_snap.rohit_present)
                else "away"
            )
            current_axes = extract_axes(
                snap,
                presence_state=_presence_state,
                git_dirty_count=self._last_git_dirty_count,
            )
            current_sig = signature_from_axes(current_axes)
            last_sig = (
                signature_from_axes(self._recent_thought_axes[-1])
                if self._recent_thought_axes
                else None
            )
            if should_skip_reasoning(
                current_signature=current_sig,
                last_thought_signature=last_sig,
                cycles_since_last_thought=self._cycles_since_last_thought,
            ):
                logger.info(
                    "Cycle %d: HEARTBEAT_OK — perception unchanged (gated)",
                    self.cycle_count,
                )
                self._cycles_since_last_thought += 1
                result = None
            else:
                # Patch A: which axes have been stable across the
                # last 3 stored thoughts AND this cycle? Strip them
                # from the prompt the LLM sees.
                stale = stale_fields(
                    list(self._recent_thought_axes),
                    current_axes,
                )
                if stale:
                    logger.info(
                        "Cycle %d: redacting stale fields %s",
                        self.cycle_count,
                        sorted(stale),
                    )
                result = self._reason(snap, stale_fields=stale)
            if result is None:
                # Either gate skipped, or _reason couldn't run. No-op.
                pass
            elif result.strip() == _HEARTBEAT_OK:
                # Nothing noteworthy this cycle — skip audit, storage, broadcast.
                # Storing fabricated prose is worse than storing nothing.
                logger.info("Cycle %d: HEARTBEAT_OK — silent cycle", self.cycle_count)
                self._cycles_since_last_thought += 1
                result = None
            else:
                # Self-claim audit on the cycle response BEFORE anything
                # else sees it. The cycle-prompt grounding fix (commit
                # 19cde77) dropped activity fabrication from ~100% to
                # ~20% of cycles; this detection net catches the
                # remaining slippage at output time and rewrites
                # before storage to raw memory. Transcript reflects
                # which activity-sources actually had data this cycle —
                # if screen/presence/calendar signals are present,
                # narration is grounded and passes through; if absent,
                # activity_claim fires and rewrites.
                try:
                    _audit_transcript_parts = []
                    _cycle_signals_present = []
                    _cycle_signals_absent = []
                    # 2026-04-23 Commit 2: surface the explicit screen state
                    # (ok / disabled / unavailable / error) so the audit's
                    # grounding manifest distinguishes "tried and failed" from
                    # "deliberately off." Important for the proactive-opinion
                    # audit (summary of memory window, not live), and for
                    # daemon-cycle audits to correctly know that narration of
                    # activity is unsupported when vision is off by policy.
                    _screen_state = (
                        getattr(
                            self._last_screen_obs,
                            "state",
                            None,
                        )
                        if self._last_screen_obs is not None
                        else None
                    )
                    if _screen_state == "ok" and getattr(
                        self._last_screen_obs,
                        "success",
                        False,
                    ):
                        _audit_transcript_parts.append("✓ screen_observation: present")
                        _cycle_signals_present.append("screen observation")
                    elif _screen_state == "disabled":
                        _cycle_signals_absent.append("screen observation (disabled by policy)")
                    elif _screen_state == "unavailable":
                        _cycle_signals_absent.append("screen observation (endpoint unreachable)")
                    else:
                        _cycle_signals_absent.append("screen observation")
                    if self._last_presence_snap is not None and getattr(
                        self._last_presence_snap, "success", False
                    ):
                        _audit_transcript_parts.append("✓ presence_snapshot: present")
                        _cycle_signals_present.append("presence snapshot")
                    else:
                        _cycle_signals_absent.append("presence snapshot")
                    if self._last_calendar_snap is not None and getattr(
                        self._last_calendar_snap, "success", False
                    ):
                        _audit_transcript_parts.append("✓ calendar_snapshot: present")
                        _cycle_signals_present.append("calendar")
                    else:
                        _cycle_signals_absent.append("calendar")
                    _cycle_signals_present.append("system stats")
                    _audit_transcript = "\n".join(_audit_transcript_parts)
                    from core.self_claim_audit import audit as _sc_audit

                    _audit_result = _sc_audit(
                        result,
                        surface="daemon_cycle",
                        transcript=_audit_transcript,
                        signals_present=_cycle_signals_present,
                        signals_absent=_cycle_signals_absent,
                        evidence_envelope=getattr(
                            self,
                            "_last_cycle_evidence_envelope",
                            None,
                        ),
                    )
                    if _audit_result.rewritten:
                        logger.info(
                            "Cycle %d: audit rewrote fabrication (kinds=%s)",
                            self.cycle_count,
                            ",".join(sorted({f.kind for f in _audit_result.flags})),
                        )
                        result = _audit_result.text
                except Exception as _audit_err:
                    logger.debug(
                        "cycle-response audit failed (continuing): %s",
                        _audit_err,
                    )

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

                # Retry path: if thought is below floor or matches reject combos
                try:
                    if cog_should_retry(cog_metadata):
                        policy = cog_get_behavior_policy()
                        retry_instruction = cog_build_retry_prompt(cog_metadata, policy)
                        initial_score = cog_metadata.get("cog_score", 0)
                        initial_labels = cog_metadata.get("cog_labels", "")
                        logger.info(
                            "Cycle %d: retry triggered (score=%d, labels=%s)",
                            self.cycle_count,
                            initial_score,
                            initial_labels,
                        )

                        # One corrective retry — append instruction to existing prompt
                        last_prompt = getattr(self, "_last_reasoning_prompt", "")
                        acquired = self._ollama_lock.acquire(timeout=0)
                        if acquired:
                            try:
                                # Session 11r: via llm_client (was missed in 11p batch)
                                from core import llm_client as _llm_client

                                # Same stable system content as primary cycle —
                                # keeps KV cache warm for retries too.
                                retry_system = (
                                    self.system_prompt + "\n\n" + _STATIC_CYCLE_INSTRUCTIONS
                                )
                                retry_response = _llm_client.chat(
                                    model=MODEL,
                                    messages=[
                                        {"role": "system", "content": retry_system},
                                        {"role": "user", "content": last_prompt},
                                        {"role": "assistant", "content": result},
                                        {"role": "user", "content": retry_instruction},
                                    ],
                                    think=False,
                                    options={"temperature": 0.8, "num_predict": 300},
                                )
                                retry_content = (retry_response.message.content or "").strip()
                                if retry_content and retry_content != "(empty response)":
                                    # 2026-04-23 memory-integrity contract:
                                    # audit the retry with the SAME cycle
                                    # signal manifest that gated the first
                                    # audit. The retry is a fresh assistant
                                    # text — it needs the same grounding
                                    # check, otherwise an improved-on-score
                                    # retry could still be fabricated and
                                    # land in raw memory unaudited. Rescore
                                    # the AUDITED retry, not the raw retry,
                                    # so the score reflects the actual text
                                    # that will be stored.
                                    try:
                                        from core.safety.audited_output import (
                                            audit_assistant_text as _aud_txt,
                                        )

                                        retry_content = _aud_txt(
                                            retry_content,
                                            surface="daemon_cycle_retry",
                                            signals_present=_cycle_signals_present,
                                            signals_absent=_cycle_signals_absent,
                                            evidence_envelope=getattr(
                                                self,
                                                "_last_cycle_evidence_envelope",
                                                None,
                                            ),
                                        )
                                    except Exception as _retry_aud_exc:
                                        logger.warning(
                                            "retry audit fail-open: %s",
                                            _retry_aud_exc,
                                        )

                                    # Re-score the (audited) retry
                                    retry_thought = retry_content + screen_note + calendar_note
                                    retry_cog = cog_score_and_classify(retry_thought)

                                    if retry_cog.get("cog_score", 0) > initial_score:
                                        # Retry is better — use it
                                        full_thought = retry_thought
                                        result = retry_content
                                        cog_metadata = retry_cog
                                        cog_metadata["cog_retried"] = "improved"
                                        cog_metadata["cog_initial_score"] = initial_score
                                        cog_metadata["cog_initial_labels"] = initial_labels
                                        logger.info(
                                            "Cycle %d: retry improved %d → %d",
                                            self.cycle_count,
                                            initial_score,
                                            retry_cog.get("cog_score", 0),
                                        )
                                    else:
                                        # Retry didn't help — keep original
                                        cog_metadata["cog_retried"] = "kept_original"
                                        cog_metadata["cog_retry_score"] = retry_cog.get(
                                            "cog_score", 0
                                        )
                                        logger.info(
                                            "Cycle %d: retry not better (%d vs %d), keeping original",
                                            self.cycle_count,
                                            retry_cog.get("cog_score", 0),
                                            initial_score,
                                        )
                            except Exception as e:
                                logger.debug("Retry generation failed: %s", e)
                                cog_metadata["cog_retried"] = "failed"
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
                    "rohit_present": str(self._last_presence_snap.rohit_present)
                    if self._last_presence_snap
                    else "unknown",
                }
                mem_metadata.update(cog_metadata)
                self.memory.store(
                    full_thought,
                    cycle=self.cycle_count,
                    snapshot=snap,
                    metadata=mem_metadata,
                    provenance_source="introspection",
                    trust_tier="lived",
                )

                # Broadcast cycle end with thought to UI
                self._ws_broadcast(
                    {
                        "type": "cycle_end",
                        "cycle": self.cycle_count,
                        "thought": result,
                    }
                )

                # 2026-04-25 fixation patches: thought stored — push
                # axes into history (Patch A's stale-field detector)
                # and reset the floor counter (Patch B's gate).
                self._recent_thought_axes.append(current_axes)
                self._cycles_since_last_thought = 0

            # Exploratory mind — advance one wondering with remaining budget.
            # _reason() ran first. If there's no room left in the cycle, the
            # wondering step skips this pass so the primary loop never degrades.
            try:
                cycle_deadline = cycle_start + LOOP_INTERVAL - 2.0
                if time.time() < cycle_deadline - 10:
                    from daemon.wondering_cycle import advance_one

                    w_result = advance_one(self, deadline=cycle_deadline)
                    if w_result:
                        logger.info("Wondering advance: %s", w_result)
            except Exception as e:
                logger.debug("wondering cycle failed: %s", e)

            # Continuity checkpoint + orientation expiry
            if result:
                self._continuity_checkpoint_counter += 1
                if self._continuity_checkpoint_counter >= CONTINUITY_CHECKPOINT_INTERVAL:
                    self._continuity_checkpoint_counter = 0
                    try:
                        _last_cog = getattr(self, "_last_cog_metadata", {})
                        continuity_checkpoint(
                            last_thought={
                                "text": result[:200],
                                "cycle": self.cycle_count,
                                "score": _last_cog.get("cog_score", 0),
                                "topic": _last_cog.get("cog_topic", ""),
                                "labels": _last_cog.get("cog_labels", "").split(","),
                            }
                        )
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
                        if sr.get("success") and sr["results"]:
                            self._proactive_search_context = (
                                f"[PROACTIVE SEARCH: '{sq}']\n  {sr['results'][0]['snippet'][:200]}"
                            )
                            logger.info("Proactive search queued: %s", sq[:60])
                    except Exception as e:
                        logger.debug("Proactive search failed: %s", e)

            # Check system thresholds for alerts (runs even if reasoning failed)
            self._check_and_alert(snap)

            # Follow-up delivery — every 5 cycles
            #
            # Session 11y: this path used to ask the LLM to "deliver on
            # your promise" given only the text of an earlier "I'll check"
            # phrase and the current perception snapshot. The LLM had no
            # grounded evidence and would fabricate a completion ("I've
            # finished installing maez-cli" for an install that never ran).
            # That was a direct trust-breaking failure.
            #
            # The new contract: get_pending() only returns rows with a
            # non-null action_id. For each one, look up the real action
            # result (outcome + output) from action_engine's action log
            # or pending list, and send a grounded report. If the action
            # hasn't completed yet, skip — try again next window. No LLM
            # role-play.
            if self.cycle_count % 5 == 0:
                try:
                    self.followup_queue.expire_old()
                    pending = self.followup_queue.get_pending()
                    for fu in pending:
                        action_id = fu.get("action_id")
                        if not action_id:
                            continue
                        # Look up the real action outcome from the quality
                        # tracker (persisted across restarts) rather than
                        # re-asking the LLM what happened.
                        try:
                            from memory.quality_tracker import QualityTracker

                            qt = QualityTracker()
                            outcome = (
                                qt.get_outcome(action_id) if hasattr(qt, "get_outcome") else None
                            )
                        except Exception:
                            outcome = None
                        if not outcome or outcome.get("status") not in (
                            "executed",
                            "cancelled",
                            "failed",
                        ):
                            # Action still pending — wait for next window.
                            continue
                        status = outcome.get("status", "unknown")
                        output = (outcome.get("output") or outcome.get("error") or "").strip()[:600]
                        desc = fu.get("task", "the action you asked about")
                        if status == "executed":
                            msg = (
                                f"Done — {desc}\n\nResult: {output}" if output else f"Done — {desc}"
                            )
                        elif status == "cancelled":
                            msg = f"Cancelled — {desc}"
                        else:
                            msg = f"Failed — {desc}\n\n{output or 'No error detail.'}"
                        try:
                            self.telegram.send_message(msg)
                            self.followup_queue.mark_delivered(fu["id"])
                            logger.info(
                                "[FOLLOWUP] Delivered (grounded): %s → %s", action_id, status
                            )
                        except Exception as e:
                            logger.error("[FOLLOWUP] Delivery send failed: %s", e)
                except Exception as e:
                    logger.debug("Followup check failed: %s", e)

            # Proactive opinion — every 50 cycles
            if self.cycle_count % 50 == 0:
                self._check_proactive_opinion()

            # Session 11o: dream cycle trigger. Fires when the owner has been
            # AFK for >30 min, rate-limited to >=10 min between dreams.
            # Runs in a BACKGROUND thread so the main 30s reasoning loop
            # never blocks on it — even under daemon/dream GPU contention
            # where a cycle can take 30-60s. The dream sets its own cooldown
            # timestamp at the top of run_dream_cycle (pre-work), so the
            # next loop tick sees should_run_now() == False and won't
            # re-spawn while an earlier dream is still in flight.
            try:
                _now = time.time()
                _absence = (_now - self._last_departure_time) if self._last_departure_time else 0.0
                if self.dream.is_idle(
                    self._last_presence_snap, _absence
                ) and self.dream.should_run_now(_now):
                    logger.info("Dream cycle triggered — the owner AFK %.0fs", _absence)

                    def _run_dream_bg():
                        try:
                            _insight = self.dream.run_dream_cycle()
                            if _insight:
                                logger.info("Dream insight: %s", _insight[:120])
                            # Session 11u: training self-evaluation
                            # (rate-limited to 1 per 24h inside the method)
                            _train_id = self.dream.maybe_propose_training()
                            if _train_id:
                                logger.info("Training proposal #%d submitted", _train_id)
                        except Exception as _e:
                            logger.error("Dream cycle worker failed: %s", _e)

                    # Slice 1.3: bounded singleton — submit() refuses if
                    # a previous worker is still in flight (cycle longer
                    # than DREAM_COOLDOWN_S) or if the daemon is shutting
                    # down. Cooldown gate above (should_run_now) is the
                    # cadence guard; this is the concurrency guard.
                    # NOTE on coupling: the cooldown gate's correctness
                    # depends on dream_state.run_dream_cycle() updating
                    # _last_dream_at at the START of the cycle (see
                    # core/evolution/dream_state.py:242). If that ever
                    # moves to the end of the cycle, this submit-skip
                    # behavior becomes load-bearing for re-spawn safety.
                    if not self._dream_worker.submit(_run_dream_bg):
                        logger.debug(
                            "Dream cycle skipped — previous worker "
                            "still running or daemon shutting down"
                        )
            except Exception as e:
                logger.debug("Dream cycle check failed: %s", e)

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

        # Verify LLM backend connectivity
        if not self._check_ollama():
            logger.error("Cannot reach LLM backend or model %s — aborting.", MODEL)
            self._remove_pid()
            sys.exit(1)
        # 2026-04-22: brain identity now comes from core.model_config
        # (/etc/maez/model.env), not a hardcoded string. Keeps this log
        # line honest as the primary model rotates. llm_client ignores
        # the model identifier for llamacpp — it uses the model the
        # server was started with — so this is cosmetic only, but a
        # wrong cosmetic is worse than no cosmetic.
        _backend = os.environ.get("MAEZ_LLM_BACKEND", "ollama").lower()
        if _backend == "llamacpp":
            try:
                from core.model_config import (
                    PRIMARY_MODEL as _pm,
                    PRIMARY_BASE_URL as _pb,
                )

                logger.info(
                    "Runtime brain confirmed: %s via llama.cpp (%s)",
                    _pm,
                    _pb,
                )
            except Exception as _mc_e:
                # self-dev review on 5d27884 flagged: import failure
                # here means model identity is unknown at startup —
                # a genuine anomaly. Warn so it surfaces in normal
                # log filtering without requiring debug level.
                logger.warning(
                    "Runtime brain confirmed: <model_config unavailable: %s>",
                    _mc_e,
                )
        else:
            logger.info("Model %s confirmed available.", MODEL)

        self.running = True

        # Connect action engine to Telegram and start bots
        self.telegram.actions = self.actions
        self.telegram.start()
        self.public_bot.start()

        # Vendored surface adapter in `skills/surface/` owns inbound
        # Telegram polling as of 2026-04-20. Legacy TelegramVoice
        # above keeps its loop alive only for outbound
        # `send_message()` / `_send_card_message()` calls from other
        # daemon subsystems. All safety rails still apply — the new
        # adapter's `MaezMessageHandler` routes through the same
        # decision pipeline + brain_loop + audit + organism blocks.
        #
        # `MAEZ_DISABLE_SURFACE_V2=1` is the kill switch for rollback.
        self._surface_v2_adapter = None
        self._surface_v2_loop = None
        self._surface_v2_thread = None
        if os.environ.get("MAEZ_DISABLE_SURFACE_V2") != "1":
            try:
                tg_token = self.telegram.token if self.telegram else None
                tg_user = self.telegram.authorized_user if self.telegram else None
                if tg_token and tg_user:
                    self._start_surface_v2(tg_token, tg_user)
                else:
                    logger.warning(
                        "Telegram token/user not available — surface "
                        "v2 will not start; messages will not reach Maez"
                    )
            except Exception as e:
                logger.warning("surface v2 bootstrap failed: %s", e)

        # Load continuity capsule BEFORE greeting/session-resume logic
        self._continuity_capsule = continuity_load()
        if self._continuity_capsule:
            self._continuity_active = True
            self._continuity_cycles_remaining = POST_RESTART_INJECTION_CYCLES
            logger.info(
                "Continuity active: %d orientation cycles, mode=%s",
                self._continuity_cycles_remaining,
                self._continuity_capsule.get("current_mode", "?"),
            )

        # Detect offline duration from last shutdown timestamp
        stats = self.memory.memory_stats()
        is_restart = stats["total"] > 0 and self.cycle_count == 0
        offline_seconds = 0
        last_shutdown = None

        try:
            if SHUTDOWN_FILE.exists():
                last_shutdown = datetime.fromisoformat(SHUTDOWN_FILE.read_text().strip())
                offline_seconds = (datetime.now(timezone.utc) - last_shutdown).total_seconds()
                logger.info(
                    "Last shutdown: %s (offline %.0fs)", last_shutdown.isoformat(), offline_seconds
                )
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
        consol_thread = threading.Thread(
            target=self._consolidation_loop, daemon=True, name="consolidation"
        )
        consol_thread.start()

        # Start nightly journal thread (11:00 PM)
        journal_thread = threading.Thread(
            target=self._nightly_journal_loop, daemon=True, name="journal"
        )
        journal_thread.start()

        # D20 Stage-5: hourly capability-acquisition planner poller.
        # Walks the queue, generates integration plans, surfaces
        # them for owner review via PendingCard. Failure-isolated
        # in its own thread so a planner exception never affects
        # the reasoning loop or consolidation.
        planning_thread = threading.Thread(
            target=self._capability_planning_loop,
            daemon=True, name="capability-planning",
        )
        planning_thread.start()

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
        hb_thread = threading.Thread(
            target=self._start_health_broadcast, daemon=True, name="health-broadcast"
        )
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
                        for phrase in [
                            "hey maez",
                            "hey maze",
                            "hey maz",
                            "maez",
                            "maze",
                            "hey jarvis",
                        ]:
                            if clean.startswith(phrase):
                                text_cmd = text[len(phrase) :].strip(" ,.!?")
                                break

                        if not text_cmd:
                            text_cmd = "status"

                        logger.info("Processing voice command: '%s'", text_cmd)
                        self.handle_voice_stream(text_cmd)
                    except Exception as e:
                        logger.error("Voice handler error: %s", e)
                    finally:
                        with self._voice_lock:
                            self._voice_active = False

                threading.Thread(target=_handle, daemon=True, name="maez-voice-handler").start()

            if wake_word_start(_on_voice_command):
                logger.info("Unified audio pipeline active — say 'Hey Maez'")
            else:
                logger.warning("Audio pipeline unavailable")
        else:
            logger.info("Voice pipeline disabled — set VOICE_ENABLED=True to re-enable")

        # Start health check server (blocks main thread)
        logger.info("Health endpoint starting on port %d", HEALTH_PORT)
        self._run_health_server()

    def _start_surface_v2(self, token: str, authorized_user: int) -> None:
        """Spin up the vendored TelegramAdapter on its own asyncio loop
        in a daemon thread. Mirrors the legacy start() threading shape
        so the two paths have identical lifecycle semantics."""
        import asyncio as _asyncio
        import threading as _threading
        from skills.surface.maez_adapter import build_telegram_adapter

        def _runner():
            try:
                # Attach a handler to the root logger so INFO-level logs
                # from vendored modules (httpx, telegram.ext,
                # skills.surface.*) surface in the daemon log. The
                # daemon's own handlers are attached to the "maez"
                # logger only, so without this, everything outside
                # that namespace silently drops.
                import logging as _lg

                _root = _lg.getLogger()
                if not _root.handlers:
                    _h = _lg.StreamHandler()
                    _h.setFormatter(
                        _lg.Formatter(
                            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                            datefmt="%Y-%m-%d %H:%M:%S",
                        )
                    )
                    _root.addHandler(_h)
                    _root.setLevel(_lg.INFO)
                # Scope noise: vendored HTTP/telegram stacks talk a lot
                # at INFO (every poll = 2 httpx lines). We only need
                # WARNING from them — errors still surface, the routine
                # "POST getUpdates 200 OK" chatter doesn't. Maez and
                # skills.surface stay at INFO for visibility.
                for _name in (
                    "httpx",
                    "httpcore",
                    "telegram",
                    "telegram.ext",
                    "telegram.ext.Application",
                    "telegram.ext.Updater",
                ):
                    _lg.getLogger(_name).setLevel(_lg.WARNING)

                async def _run():
                    adapter = build_telegram_adapter(
                        token=token,
                        authorized_users=[int(authorized_user)],
                        daemon=self,
                    )
                    self._surface_v2_adapter = adapter
                    try:
                        ok = await adapter.connect()
                    except Exception as ce:
                        logger.exception("surface v2 connect() raised: %s", ce)
                        return
                    if not ok:
                        logger.warning("surface v2 connect() returned False")
                        return
                    import asyncio as __a

                    self._surface_v2_loop = __a.get_running_loop()
                    logger.info("surface v2 live (tasks=%d)", len(__a.all_tasks()))
                    _hb = 0
                    while self.running:
                        await _asyncio.sleep(1.0)
                        _hb += 1
                        if _hb % 60 == 0:
                            logger.info(
                                "surface v2 heartbeat: %dm uptime",
                                _hb // 60,
                            )
                    try:
                        await adapter.disconnect()
                    except Exception as e:
                        logger.debug("surface v2 disconnect: %s", e)

                # asyncio.run() manages the loop lifecycle correctly
                # for this thread; manual loop management caused PTB
                # polling tasks to be scheduled but never fire HTTP.
                _asyncio.run(_run())
            except Exception as e:
                logger.exception("surface v2 runner crashed: %s", e)

        self._surface_v2_thread = _threading.Thread(
            target=_runner,
            daemon=True,
            name="surface-v2",
        )
        self._surface_v2_thread.start()

    def stop(self, signum=None, frame=None):
        """Graceful shutdown."""
        if self._shutdown_started.is_set():
            logger.info("Shutdown already in progress; ignoring duplicate signal %s", signum)
            return
        self._shutdown_started.set()
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
        # Slice 1.3: bounded shutdown of dream worker. Wait up to 5s
        # for an in-flight dream cycle to finish (writes to memory.db
        # mid-cycle would otherwise tear). After this, submit() refuses
        # any stale callers that might still be in the loop's tail.
        try:
            if not self._dream_worker.shutdown(timeout=5.0):
                logger.warning(
                    "Dream worker did not finish within shutdown timeout"
                )
        except Exception as e:
            logger.debug("Dream worker shutdown failed: %s", e)
        try:
            self.telegram.stop()
        except Exception as e:
            logger.debug("Telegram bot stop failed: %s", e)
        # Stop the v2 surface adapter if we launched it.
        #
        # T1.9 hygiene (Codex deploy verification 2026-05-04 + 05):
        # The morning's fix (10220d9) added a thread.join(timeout=5)
        # after `_loop.call_soon_threadsafe(_loop.stop)` to bound
        # the shutdown wait. Live deploy verification confirmed
        # the join didn't actually prevent the surface-v2
        # traceback — `_loop.stop()` interrupts the runner's
        # `await _asyncio.sleep(1.0)` mid-await, asyncio.run()
        # raises RuntimeError("Event loop stopped before Future
        # completed"), and only THEN does the join sit for an
        # already-dead thread.
        #
        # The runner already cooperates: its `while self.running:`
        # loop exits within ≤1s on the next sleep boundary. The
        # explicit loop.stop() is redundant and harmful — it
        # produces the traceback without giving the runner time
        # to exit cleanly via `await adapter.disconnect()`. We
        # keep the thread.join (still load-bearing — bounds the
        # wait against systemd SIGKILL) but drop the loop.stop.
        #
        # If the runner ever hangs past 5s in a future bug
        # (e.g. adapter.disconnect awaiting hung network I/O),
        # the join's WARNING surfaces it and a force-stop can be
        # reintroduced THEN with explicit RuntimeError handling
        # inside the runner. Today the cooperative path is
        # sufficient and quiet.
        try:
            _thread = getattr(self, "_surface_v2_thread", None)
            if _thread is not None and _thread.is_alive():
                _thread.join(timeout=5.0)
                if _thread.is_alive():
                    logger.warning(
                        "surface_v2 thread did not exit within "
                        "5s of self.running=False — runner may be "
                        "blocked on adapter shutdown; connections "
                        "may leak"
                    )
        except Exception as e:
            logger.debug("surface v2 stop failed: %s", e)
        try:
            self.public_bot.stop()
        except Exception as e:
            logger.debug("Public bot stop failed: %s", e)
        # Slice 1.6: shut down the shared ThreadPoolExecutor AFTER all
        # surfaces (telegram, surface_v2, public_bot) have stopped
        # submitting. Placing it earlier could leave a late submission
        # racing the shutdown and raising
        # RuntimeError: cannot schedule new futures after shutdown.
        #
        # wait=False: a sync LLM call wedged on a dead llama.cpp would
        # block stop() forever with wait=True. With wait=False, the
        # daemon proceeds with the rest of the shutdown ladder; the
        # stuck workers remain in the process until either they
        # complete naturally or systemd's TimeoutStopSec sends SIGKILL.
        #
        # cancel_futures=True: queued (not-yet-running) work is
        # dropped immediately. Running sync work cannot be cancelled
        # in Python.
        try:
            from core.health.shared_executor import shutdown_shared_executor
            shutdown_shared_executor(wait=False, cancel_futures=True)
        except Exception as e:
            logger.debug("Shared executor shutdown failed: %s", e)
        try:
            if self._ws_loop is not None:
                self._ws_loop.call_soon_threadsafe(self._ws_loop.stop)
        except Exception as e:
            logger.debug("WebSocket loop stop failed: %s", e)
        try:
            if self._health_server is not None:

                def _shutdown_health():
                    try:
                        self._health_server.shutdown()
                    except Exception as inner:
                        logger.debug("Health server shutdown failed: %s", inner)

                threading.Thread(
                    target=_shutdown_health,
                    name="health-server-shutdown",
                    daemon=True,
                ).start()
        except Exception as e:
            logger.debug("Health server stop trigger failed: %s", e)
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
            return jsonify(
                {
                    "status": "alive",
                    "model": MODEL,
                    "boot_time": self.boot_time,
                    "cycle_count": self.cycle_count,
                    "last_cycle": self.last_cycle_time,
                    "uptime_seconds": int(
                        time.time() - datetime.fromisoformat(self.boot_time).timestamp()
                    ),
                    "memory": self.memory.memory_stats(),
                    "system": {
                        "cpu_percent": snap["cpu"]["percent"],
                        "ram_percent": snap["ram"]["percent"],
                        "gpu_percent": gpu.get("utilization_pct"),
                        "gpu_temp_c": gpu.get("temperature_c"),
                    },
                }
            )

        @app.route("/message", methods=["POST"])
        def message():
            data = request.get_json(silent=True) or {}
            text = data.get("text", "").strip()
            if not text:
                return jsonify({"error": "empty message"}), 400
            # Accept optional history list ({role, content} dicts) so
            # the UI can thread prior turns into synthesis. Without
            # this, "Hi" mid-session re-greets because handle_message
            # has no chat_history. Each adjacent (user, assistant)
            # pair becomes one chat_history entry in the
            # "<display>: <msg>\nMaez: <reply>" shape that
            # core.brain.conversation_history.history_to_messages
            # expects. 2026-04-27 incident fix.
            raw_history = data.get("history") or []
            chat_history = _pair_history_for_chat_threading(raw_history) if raw_history else None
            reply = self.handle_message(
                text,
                source="UI",
                chat_history=chat_history,
            )
            return jsonify({"reply": reply})

        @app.route("/internal/brain_loop", methods=["POST"])
        def internal_brain_loop():
            """Run a brain-loop iteration for a non-Telegram surface.

            2026-04-23 Commit 5 — web body parity. The web process
            (maez-web.service) lives in a separate process from the
            daemon and therefore cannot touch ActionEngine directly.
            This endpoint bridges the gap: web POSTs the owner's
            message here, the daemon runs the full Jarvis tool-use
            loop against its own ActionEngine, and returns the
            transcript of what actually ran (or an empty string if
            no tools were used). Approval-gated actions are handed
            off to the card store; the caller is responsible for
            telling the user "I've proposed X — waiting on your
            approval" if the transcript contains ⏳ card markers.

            Payload: {"text": "...", "chat_id": "...", "user_id": "rohit"}
            Response: {"transcript": "..."} (empty string when no tools ran)

            Localhost-only by the service's bind, consistent with the
            existing /internal/* endpoints. Fails open: any exception
            returns an empty transcript with a 200 so the caller's
            fallback path (non-tool LLM synthesis) still works.
            """
            data = request.get_json(silent=True) or {}
            text = (data.get("text") or "").strip()
            if not text:
                return jsonify({"transcript": "", "error": "empty text"}), 400
            try:
                telegram = getattr(self, "telegram", None)
                get_pipeline_fn = telegram._get_pipeline if telegram else None
                action_engine_ref = getattr(self, "actions", None)
                if action_engine_ref is None or get_pipeline_fn is None:
                    return jsonify(
                        {
                            "transcript": "",
                            "error": "action_engine or pipeline unavailable",
                        }
                    ), 503
                from core import brain_loop as _bl

                # Slice 3 of trace work: request the structured result
                # so the JSON response can include tool_calls for the
                # web surface to forward into its trace path. Backward
                # compatible — legacy callers still see "transcript".
                _result = _bl.run_brain_loop(
                    text,
                    action_engine=action_engine_ref,
                    get_pipeline=get_pipeline_fn,
                    user_id=data.get("user_id") or "rohit",
                    chat_id=str(data.get("chat_id") or ""),
                    send_intermediate=None,  # web has no out-of-band card surface
                    return_structured=True,
                )
                if hasattr(_result, "transcript"):
                    return jsonify({
                        "transcript": _result.transcript or "",
                        "tool_calls": list(_result.tool_calls or []),
                    })
                # Legacy string fallback (if a future change reverts the
                # structured API). Kept for safety; not currently
                # reachable.
                return jsonify({"transcript": _result or "", "tool_calls": []})
            except Exception as e:
                logger.warning("/internal/brain_loop failed: %s", e)
                # Fail open — empty transcript lets the web caller
                # fall through to non-tool LLM synthesis rather than
                # degrade the whole turn.
                return jsonify({
                    "transcript": "",
                    "tool_calls": [],
                    "error": str(e),
                }), 200

        @app.route("/internal/approve_card/<request_id>", methods=["POST", "OPTIONS"])
        def approve_card(request_id: str):
            """Cockpit approval surface. Runs the full decision_pipeline
            approve path (_on_approve → will-I check → execute →
            card_store.mark_done) in the daemon process where
            ActionEngine lives. Safe equivalent of the Telegram
            'yes' keyword — same auth model (localhost only), same
            execution path."""
            if request.method == "OPTIONS":
                return ("", 204)
            try:
                telegram = getattr(self, "telegram", None)
                pipe = telegram._get_pipeline() if telegram else None
                if pipe is None:
                    return jsonify({"ok": False, "error": "pipeline unavailable"}), 503
                card = pipe.card_store.get(request_id)
                if card is None:
                    return jsonify({"ok": False, "error": f"no such card: {request_id}"}), 404
                from core.pending_cards import CardStatus

                if card.status not in {CardStatus.OPEN.value, CardStatus.DEFERRED.value}:
                    return jsonify(
                        {
                            "ok": False,
                            "error": f"card status is {card.status!r}, not approvable",
                        }
                    ), 409

                class _CockpitCls:
                    source = "cockpit"
                    reasoning = "approved from cockpit UI"

                result = pipe._on_approve(card, _CockpitCls(), "rohit")
                # PipelineResult may be the executed card result or a
                # refusal (e.g., covenant / will-I / stale state).
                ok = bool(getattr(result, "execution_success", None))
                return jsonify(
                    {
                        "ok": ok,
                        "status": getattr(
                            getattr(result, "status", None),
                            "value",
                            str(getattr(result, "status", "")),
                        ),
                        "message": getattr(result, "message", ""),
                        "output": (getattr(result, "execution_output", "") or "")[:2000],
                        "error": getattr(result, "execution_error", None),
                    }
                )
            except Exception as e:
                logger.warning("cockpit approve_card %s failed: %s", request_id, e)
                return jsonify({"ok": False, "error": str(e)}), 500

        @app.route("/dashboard")
        def dashboard():
            """Local-only interactive dashboard. Bound to 127.0.0.1, never nginx-proxied."""
            return send_file(str(BASE_DIR / "ui" / "dashboard_local.html"))

        @app.route("/")
        def root():
            return jsonify({"name": "Maez", "status": "running"})

        try:
            from werkzeug.serving import make_server

            srv = make_server("127.0.0.1", HEALTH_PORT, app)
            srv.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._health_server = srv
            srv.serve_forever()
            logger.info("Health endpoint stopped.")
        except KeyboardInterrupt:
            self.stop()
        finally:
            try:
                if self._health_server is not None:
                    self._health_server.server_close()
            except Exception:
                pass
            self._health_server = None


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
