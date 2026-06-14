# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""
Maez ConversationController — transport-neutral operator spine.

This module owns everything that should behave the same across Telegram,
web /chat, CLI, voice, or any future surface where Maez converses with
its user. Surface-specific adapters (TelegramVoice, web /chat handler,
CliChat) instantiate a ConversationContext per conversation, call
handle_user_message(), and send the resulting ReplyPlan through their
native IO.

Rationale: the Stand concept says there is one Maez per user, speaking
through any surface it has access to. Duplicating the operator spine
across adapters would produce three different Maezes — which violates
the concept. The controller keeps the spine in one place so Maez
behaves the same wherever it is addressed.

The controller is extracted from skills/telegram_voice.py incrementally.
Each extraction is reversible: the class starts empty and gains one
concern per commit, with Telegram continuing to work at every step.
Partial progress is surfaced via has_layer() for surfaces that want to
feature-gate on what's landed.
"""

from __future__ import annotations

import json as _json
import logging
import threading
import time
import re as _re
from dataclasses import dataclass, field
from typing import Any, Optional

from core.infra.env_flags import strict_env_flag

# 2026-04-23 Commit 6: default model for synthesis now tracks the
# current primary brain. Callers can still override via model=.
try:
    from core.model_config import PRIMARY_MODEL as _DEFAULT_MODEL
except Exception:
    _DEFAULT_MODEL = "primary-model"

logger = logging.getLogger("maez")


def _search_commitment_enabled() -> bool:
    return strict_env_flag("MAEZ_SEARCH_COMMITMENT_ENABLED")


# ============================================================ #
#  Transport-neutral conversation context                       #
# ============================================================ #

@dataclass
class ConversationContext:
    """Per-conversation context an adapter passes to the controller.

    Stable across a conversation (channel + chat_id identify it).
    Capability flags tell the controller what the surface can do so
    the controller doesn't ask for features the surface cannot
    deliver — e.g., offering card approvals on a guest web surface
    where the user has no authority to approve Maez actions."""

    channel: str                     # "telegram_text" | "web_chat_owner" | "web_chat_guest" | "cli" | ...
    chat_id: str                     # stable per-conversation identifier
    user_id: str                     # stable per-user identifier
    is_owner: bool = True            # gates Jarvis agentic loop + card approvals
    can_send_cards: bool = True      # surface can render pending-card UI
    can_stream: bool = False         # surface supports partial-message streaming (V2)


# ============================================================ #
#  Reply plan                                                   #
# ============================================================ #

@dataclass
class ReplyPlan:
    """What the controller has decided to send back.

    Adapters iterate `messages` first (primary reply), then send
    `correction` as a follow-up if present. `short_circuit` tells the
    adapter to skip any further adapter-native processing (commands,
    etc.) — used by intent handlers that fully resolved the turn.
    """

    messages: list[str] = field(default_factory=list)
    correction: Optional[str] = None
    short_circuit: bool = False
    tool_calls_made: int = 0
    cards_created: int = 0
    dialogs_opened: int = 0


# ============================================================ #
#  Controller                                                   #
# ============================================================ #

class ConversationController:
    """Transport-neutral operator spine.

    Current scope (extracted layers):
      - honesty         : _CLAIM_PATTERN, _STATE_CLAIM_PATTERN,
                          _PROPOSED_CMD_PATTERN, _HONEST_STUB,
                          _NARRATION_MISMATCH_CORRECTION, honesty_guard()
      - pending_card_view : has_awaiting_card(), recent_card_cmds()
      - narration_check   : extract_command_candidates(),
                            narration_matches_real_card()

    Planned scope (being moved in from skills/telegram_voice.py):
      - honesty guard + narration-card content check
      - pending-card view helpers (has_awaiting_card, recent_card_cmds)
      - offer-binding (bare "yes" → stored web-search offer)
      - proposal-intent / web-search-intent / card-reply-intent routing
      - Jarvis loop orchestration (for is_owner contexts)
      - probe-bridge and next-step proposer
      - recovery synthesis
      - Jarvis prompt fragments (DIRECT-INSTALL, EXPLORATORY-ASK,
        PARTIAL-ACTION TRAP, anti-reflex)

    Ephemeral per-chat state lives in the controller, keyed by
    (channel, chat_id). This means Telegram-chat state and web-chat
    state stay isolated — they do not cross-pollute even though
    Maez is the same being on both.
    """

    # ──────────────────────────────────────────────────────── #
    #  Honesty-guard constants (moved from skills/telegram_voice.py  #
    #  2026-04-17 extraction pass — see feedback_claude_as_parent.md #
    #  and docs/TRACK_A.md for the extraction rationale).            #
    # ──────────────────────────────────────────────────────── #

    # Future-action claim — "I'll search / I've proposed ...". Subject to
    # tool-bypass: legitimate when a tool fired this turn (e.g. a probe
    # tool call just ran and the reply correctly previews next step).
    _CLAIM_PATTERN = _re.compile(
        r"\b("
        r"I[' ]?ll\s+(search|check|look|run|investigate|find|try|set|install|execute|initiate|start)"
        r"|I[' ]?ve\s+(proposed|started|begun|initiated|searched|checked|run|set|executed)"
        r"|I\s+proposed\s+(running|to\s+run|checking)"
        r"|I\s+have\s+the\s+plan\s+ready"
        r"|Shall\s+I\s+(go\s+ahead|proceed|run|search|check|execute)"
        r")",
        _re.IGNORECASE,
    )

    # State-claim — "waiting for your approval / you've approved / pending
    # session / skill_id". These are never legitimate in chat prose because
    # real pending state is surfaced by the card renderer, not narrated.
    _STATE_CLAIM_PATTERN = _re.compile(
        r"(?:"
        r"\b(?:"
        r"waiting\s+for\s+your\s+approval"
        r"|that'?s\s+waiting\s+for\s+(?:your\s+)?(?:approval|go[\s\-]?ahead)"
        r"|you'?ve\s+approved"
        r"|since\s+you'?ve\s+approved"
        r"|you\s+approved\s+(?:the|that|this|it)"
        r"|wait(?:ing)?\s+for\s+(?:that|this|the)\s+session"
        r"|(?:that|this|the)\s+session\s+to\s+(?:finish|complete|end)"
        r"|the\s+previous\s+(?:request|approval|session)"
        r"|pending\s+(?:approval|request|session|investigation)"
        r"|the\s+Telegram\s+card\s+for\s+your\s+approval"
        r"|skill_id\b"
        r"|(?:I[' ]?ve|I\s+have)\s+(?:already|now|just|recently|also)\s+proposed"
        r")"
        r"|\(\s*ref\s*:"
        r")",
        _re.IGNORECASE,
    )

    # Proposal-claim — "I've proposed <command>". Narrow pattern specific
    # to the narration↔card content check. Fires regardless of adverbs
    # because the content check verifies commands themselves.
    _PROPOSED_CMD_PATTERN = _re.compile(
        r"\b("
        r"I[' ]?ve\s+proposed"
        r"|I\s+have\s+proposed"
        r"|I\s+proposed\s+(?:running|to\s+run|a\s+(?:system\s+)?check|a\s+probe|checking)"
        r"|proposed\s+(?:a\s+(?:system\s+)?check|running|checking|via|probing)"
        r"|I\s+(?:queued|am\s+queuing)"
        r"|I[' ]?ve\s+queued"
        r")\b",
        _re.IGNORECASE,
    )

    # Replacement sent when the guard trips and we need to fully rewrite
    # the reply (no real state to refer to). Three short sentences —
    # non-actional, honest, forward-looking without claiming state that
    # doesn't exist.
    _HONEST_STUB = (
        "I haven't actually started that yet. "
        "I don't currently have a pending action for it. "
        "I can do that once I create or run the correct action."
    )

    # Appended (not replacing) when the reply contains real content
    # alongside a fake proposal claim. Preserves the rest of the reply
    # while flagging the fake portion explicitly.
    _NARRATION_MISMATCH_CORRECTION = (
        "\n\n(Correction: I misspoke above — the command(s) I mentioned "
        "as proposed aren't actually queued. Disregard that part; any "
        "real pending card will show up as its own Telegram card.)"
    )

    # Shell verbs that reliably indicate a command in backticks (not a
    # path, vendor ID, product name, etc.). Used to extract command-like
    # candidates from reply text before comparing them against real card
    # cmds. Deliberately narrow — false positives would make the guard
    # fire on innocuous backtick mentions.
    _SHELL_VERB_ALLOWLIST = frozenset({
        "ls", "cat", "head", "tail", "less", "more",
        "cp", "mv", "rm", "rmdir", "mkdir", "touch", "ln",
        "dpkg", "apt", "apt-get", "apt-cache",
        "pip", "pip3", "npm", "snap", "flatpak",
        "lsusb", "lspci", "lscpu", "lsmod", "lshw", "lsblk",
        "lsns", "lsipc", "lslocks", "lsscsi", "hwinfo", "inxi", "xdpyinfo",
        "lsb_release", "uname", "hostname", "whoami", "id", "groups", "date",
        "ps", "top", "htop", "df", "du", "free", "stat", "file",
        "find", "locate", "grep", "egrep", "rg", "ag", "which", "whereis",
        "systemctl", "journalctl", "service",
        "nvidia-smi", "sensors", "dmidecode",
        "ip", "ss", "ping", "dig", "nslookup", "host", "ifconfig",
        "curl", "wget", "nc", "netcat", "ssh", "scp", "rsync",
        "git", "python", "python3", "node", "go", "cargo", "docker",
        "echo", "printf", "sed", "awk", "tr", "sort", "uniq", "cut", "tee",
        "openrgb", "pactl", "pacmd",
    })

    # ──────────────────────────────────────────────────────── #
    #  Offer-binding constants (layer: offer_binding)               #
    #                                                               #
    #  When Maez says "I can search for X" / "want me to look up X" #
    #  in a turn that created no real action state, store the offer #
    #  as a short-lived pending task. On the next bare approval the #
    #  controller fires the offered web_search instead of letting   #
    #  "yes" fall through to chat (which loops the soft-offer).     #
    #  Safety rail: web_search only; other kinds fall through.      #
    # ──────────────────────────────────────────────────────── #

    _OFFER_PATTERN = _re.compile(
        # Match "I can [up to 80 chars of anything except negation] (offer-verb)"
        # The (?!can't|cannot) prevents matching "I cannot check".
        # The .{0,80}? non-greedy middle allows clauses like
        # "I can, however, use the run_shell tool to check".
        r"I\s+can\b(?!(?:'?t|not)\b).{0,80}?\b"
        r"(search|look\s+up|look\s+into|check|investigate|find|web[\s\-]?search)"
        r"|want\s+me\s+to\b.{0,60}?\b(search|look\s+up|check|investigate|find)"
        r"|Shall\s+I\b.{0,60}?\b(search|look\s+up|look\s+into|check|investigate|find)"
        r"|I\s+(?:could|would)\b.{0,60}?\b(search|look\s+up|look\s+into|check|investigate|find)",
        _re.IGNORECASE,
    )

    _OFFER_APPROVAL_PATTERN = _re.compile(
        r"^\s*(?:"
        r"yes|yep|yeah|yup|yuh|ok|okay|sure|sure\s+thing"
        r"|alright|alright\s+then|absolutely|go\s+ahead|proceed"
        r"|do\s+it|please\s+do|sounds\s+good|green\s+light|ship\s+it"
        r"|yeah\s+proceed|yeah\s+go\s+ahead|yes\s+proceed|yes\s+go\s+ahead"
        r"|fine|great|perfect"
        r"|that'?d\s+be\s+great|that\s+would\s+be\s+great|that'?s\s+great"
        r"|that'?d\s+be\s+perfect|that\s+would\s+be\s+perfect|that'?s\s+perfect"
        r"|that'?d\s+work|that\s+works|sounds\s+great|that\s+sounds\s+good"
        r"|love\s+(?:it|that)|go\s+for\s+it|yeah\s+do\s+that|yes\s+do\s+that"
        r"|yeah\s+that|yes\s+that|do\s+that|that'?s\s+good"
        r")[\s!.?]*$",
        _re.IGNORECASE,
    )

    _OFFER_TTL_SECONDS = 120

    # ──────────────────────────────────────────────────────── #
    #  Exploratory-ask detector + next-step parser                  #
    #  (layer: next_step_parse — pure logic, no LLM or dispatch)    #
    # ──────────────────────────────────────────────────────── #

    _EXPLORATORY_ASK_PATTERN = _re.compile(
        r"\b("
        r"figure\s+out"
        r"|how\s+(?:do|can|should|would)\s+(?:i|we|you)"
        r"|tell\s+me\s+(?:the\s+path|about|how|what|where|which)"
        r"|what\s+(?:can|tools|options|are|is)"
        r"|(?:please\s+)?investigate"
        r"|explore\b"
        r"|look\s+into"
        r"|can\s+you\s+(?:control|find|explore|investigate|figure|identify|check)"
        r"|any\s+way\s+to"
        r"|what'?s\s+the\s+(?:path|way|command)"
        r")\b",
        _re.IGNORECASE,
    )

    def __init__(
        self,
        memory: Any,
        pipeline: Any = None,
        daemon: Any = None,
        pipeline_getter: Any = None,
    ):
        self.memory = memory
        self.pipeline = pipeline
        self.daemon = daemon
        # Lazy accessor — called by _card_store() each time so the
        # controller can start before the pipeline is constructed
        # (e.g. during daemon startup when the action engine lands
        # later than the Telegram thread).
        self._pipeline_getter = pipeline_getter

        # T1.3 (2026-05-04 audit) — pipeline_getter failures used to be
        # logged at DEBUG and silently returned None, which made every
        # honesty-guard caller fail-OPEN (steamroll the user's pending-
        # card context). Track failures observably; has_awaiting_card
        # uses these to fail CLOSED inside a short window.
        self._card_store_failures: int = 0
        self._card_store_last_failure_ts: Optional[float] = None

        # Ephemeral per-chat state, keyed by (channel, chat_id).
        #
        # T1.2 (2026-05-04 audit) — these mutable dicts are read /
        # written by sync methods invoked from an async event loop
        # plus a separate Telegram polling thread. RLock guards
        # every access path so concurrent set/pop/get can't corrupt
        # the dict state. Reentrant so methods that call other
        # locked methods (e.g. consume_offer_approval -> clear_offer)
        # don't self-deadlock.
        self._offers_lock = threading.RLock()
        self._offers: dict[tuple[str, str], dict] = {}
        self._search_receipts: dict[tuple[str, str], Any] = {}
        self._last_probes: dict[tuple[str, str], dict] = {}
        self._last_user_text: dict[tuple[str, str], str] = {}

        # Track which extraction layers have been migrated from the
        # Telegram adapter so surfaces can feature-gate during the
        # incremental rollout.
        self._layers: set[str] = set()
        self._register_layer("honesty")
        self._register_layer("pending_card_view")
        self._register_layer("narration_check")
        self._register_layer("offer_binding")
        self._register_layer("next_step_parse")
        self._register_layer("next_step_proposer")

    # -------- layer introspection -------- #

    def has_layer(self, name: str) -> bool:
        """True if the named operator-spine layer has been migrated
        to the controller and is safe for adapters to rely on."""
        return name in self._layers

    def _register_layer(self, name: str) -> None:
        self._layers.add(name)

    # -------- primary entry point -------- #

    async def handle_user_message(
        self,
        ctx: ConversationContext,
        user_text: str,
    ) -> ReplyPlan:
        """Primary entry point. Currently a placeholder during the
        incremental extraction — adapters should continue using their
        existing paths until the corresponding layer is registered.

        Once extraction completes, this method orchestrates:
          1. Intent detection (card-reply, offer-binding, proposal,
             web-search) — any of these may short-circuit.
          2. Main chat turn (Jarvis loop for owner, non-agentic
             constrained chat for guest).
          3. Honesty guard + narration check applied to the final
             reply; correction synthesized if mismatch detected.
        """
        plan = ReplyPlan()
        # Placeholder — extraction in progress.
        return plan

    # ════════════════════════════════════════════════════════ #
    #  Pending-card view (layer: pending_card_view)             #
    # ════════════════════════════════════════════════════════ #

    # T1.3 — within this many seconds of a pipeline_getter failure,
    # honesty-critical callers (has_awaiting_card) fail CLOSED so the
    # user's pending-card context is preserved.
    _CARD_STORE_FAILURE_WINDOW_S = 30.0

    def _card_store(self) -> Any:
        """Return the pending-card store from the pipeline, or None.

        T1.3 (2026-05-04 audit): on pipeline_getter failure we now log
        at WARNING (not DEBUG) and bump a failure counter. The counter
        plus timestamp let has_awaiting_card distinguish 'no pipeline
        configured' (None forever) from 'lookup just failed' (None now,
        try again later) — the latter must fail CLOSED for the honesty
        guard, not silently fail-OPEN as before.
        """
        pipe = self.pipeline
        if pipe is None and self._pipeline_getter is not None:
            try:
                pipe = self._pipeline_getter()
            except Exception as e:
                self._card_store_failures += 1
                self._card_store_last_failure_ts = time.time()
                logger.warning(
                    "controller: pipeline_getter raised: %s "
                    "(failure #%d) — honesty guard will fail closed "
                    "for the next %.0fs",
                    e,
                    self._card_store_failures,
                    self._CARD_STORE_FAILURE_WINDOW_S,
                )
                pipe = None
        if pipe is None:
            return None
        return getattr(pipe, "card_store", None)

    def _card_store_recently_failed(self) -> bool:
        """True if a pipeline_getter failure was recorded within the
        fail-closed window. Honesty-guard-critical callers consult
        this to back off on suspect lookups instead of treating
        them as 'no pending card'."""
        ts = self._card_store_last_failure_ts
        if ts is None:
            return False
        return (time.time() - ts) < self._CARD_STORE_FAILURE_WINDOW_S

    def has_awaiting_card(self, channel: str, chat_id: str) -> bool:
        """True if the given (channel, chat_id) has at least one card in
        status OPEN or DEFERRED. Used by the probe→pending bridge, by
        offer-binding, and by the honesty guard to avoid preempting /
        over-correcting when a real card already exists.

        T1.3 fail-closed semantics: when _card_store() returns None
        because pipeline_getter just raised (within the failure
        window), assume there IS an awaiting card. The honesty guard
        consults this to decide whether to back off; backing off on
        a suspect lookup preserves the user's pending-card context
        instead of steamrolling it."""
        store = self._card_store()
        if store is None:
            if self._card_store_recently_failed():
                return True  # T1.3 fail-CLOSED
            return False
        try:
            from core.pending_cards import AWAITING_STATUSES
            cards = store.get_open_for_channel(channel=channel, chat_id=chat_id)
            return any(getattr(c, "status", None) in AWAITING_STATUSES for c in cards)
        except Exception as e:
            logger.debug("controller: awaiting-card check failed: %s", e)
            return False

    def recent_card_cmds(
        self,
        channel: str,
        chat_id: str,
        since_seconds: float = 180.0,
    ) -> list[str]:
        """Command strings from cards that narration could legitimately
        reference right now: currently awaiting cards OR cards executed/
        created within the last since_seconds. Consumed by the narration-
        card content check."""
        store = self._card_store()
        if store is None:
            return []
        cmds: list[str] = []

        def _cmd_from_record(rec: Any) -> Optional[str]:
            try:
                params = getattr(rec, "params", None)
                if params is None:
                    return None
                if isinstance(params, str):
                    params = _json.loads(params)
                if isinstance(params, dict):
                    return params.get("cmd")
            except Exception:
                return None
            return None

        try:
            for c in store.get_open_for_channel(channel=channel, chat_id=chat_id):
                cmd = _cmd_from_record(c)
                if cmd and cmd not in cmds:
                    cmds.append(cmd)
        except Exception as e:
            logger.debug("controller: open-cards lookup failed: %s", e)

        try:
            records = store.recent_activity_for_chat(
                channel=channel, chat_id=chat_id,
                since_seconds=since_seconds, limit=16,
            )
            for rec in records or []:
                cmd = _cmd_from_record(rec)
                if cmd and cmd not in cmds:
                    cmds.append(cmd)
        except Exception as e:
            logger.debug("controller: recent-activity lookup failed: %s", e)

        return cmds

    # ════════════════════════════════════════════════════════ #
    #  Narration-card content check (layer: narration_check)    #
    # ════════════════════════════════════════════════════════ #

    def extract_command_candidates(self, reply: str) -> list[str]:
        """Extract backticked tokens whose first word is a known argv0
        from _SHELL_VERB_ALLOWLIST. Filters out paths, vendor IDs,
        filenames — anything that's not command-shaped."""
        if not reply:
            return []
        candidates: list[str] = []
        for tok in _re.findall(r'`([^`]+)`', reply):
            tok = tok.strip()
            if not tok:
                continue
            parts = tok.split()
            if not parts:
                continue
            if parts[0] in self._SHELL_VERB_ALLOWLIST:
                candidates.append(tok)
        return candidates

    def narration_matches_real_card(
        self,
        reply: str,
        channel: str,
        chat_id: str,
    ) -> tuple[bool, str, list[str], list[str]]:
        """Verify backticked command candidates in reply correspond to
        at least one real recent card cmd.

        Returns (ok, info, candidates, real_cmds):
          - ok == True when there's nothing to verify (no candidates)
            OR at least one candidate overlaps a real card cmd (as
            substring, either direction, or as one of its segments).
          - ok == False when candidates are present AND none overlap
            any real cmd — the hallucinated-narration case."""
        candidates = self.extract_command_candidates(reply)
        if not candidates:
            return True, "no command candidates", [], []
        real_cmds = self.recent_card_cmds(channel=channel, chat_id=chat_id)
        if not real_cmds:
            return False, "candidates present but no real cards in window", candidates, []
        for cand in candidates:
            for rcmd in real_cmds:
                if cand in rcmd or rcmd in cand:
                    return True, f"matched {cand!r}", candidates, real_cmds
                for seg in _re.split(r'\s*(?:&&|\|\||;|\|)\s*', cand):
                    seg = seg.strip()
                    if seg and (seg in rcmd or rcmd in seg):
                        return True, f"matched segment {seg!r}", candidates, real_cmds
        return False, "no candidate overlaps any real cmd", candidates, real_cmds

    # ════════════════════════════════════════════════════════ #
    #  Honesty guard (layer: honesty)                           #
    # ════════════════════════════════════════════════════════ #

    def honesty_guard(
        self,
        reply: str,
        *,
        channel: str,
        chat_id: str,
        turn_tool_calls: int,
        turn_cards_created: int,
        turn_dialogs_opened: int,
    ) -> str:
        """Apply state-claim and future-action claim checks to a reply.

        Returns the reply, possibly rewritten to _HONEST_STUB, possibly
        with _NARRATION_MISMATCH_CORRECTION appended. Callers in streaming
        mode should use the separate streaming helpers (see honesty_guard_
        post_stream) — this method is for buffered reply flows where the
        full text is available before send.

        State claims (pending/approved/session) always fire — tool calls
        this turn don't legitimize a fake "waiting for your approval"
        narrative. Real pending state is surfaced via the card renderer,
        not chat prose.

        Future-action claims ("I'll search") are bypassed when a tool
        fired this turn, because those claims may match the probing tool
        that actually ran."""
        if not reply:
            return reply

        sm = self._STATE_CLAIM_PATTERN.search(reply)
        if sm:
            if self.has_awaiting_card(channel=channel, chat_id=chat_id):
                logger.info(
                    "honesty guard: state-claim suppressed in buffer "
                    "mode — real pending card exists (matched=%r)",
                    sm.group(0),
                )
            else:
                logger.info(
                    "honesty guard: chat_state_claim_rewritten "
                    "(tool_calls=%d cards=%d dialogs=%d matched=%r) | orig=%s",
                    turn_tool_calls, turn_cards_created, turn_dialogs_opened,
                    sm.group(0),
                    reply[:100].replace("\n", " "),
                )
                return self._HONEST_STUB

        # 2026-04-17 narration↔card content check — fires regardless of
        # whether the state-claim pattern matched above, because the
        # "I have proposed X" shape (no adverb) doesn't match the
        # state-claim pattern but still asserts fake queued commands.
        pm = self._PROPOSED_CMD_PATTERN.search(reply)
        if pm:
            ok, info, cands, real = self.narration_matches_real_card(
                reply, channel=channel, chat_id=chat_id,
            )
            if not ok:
                logger.info(
                    "honesty guard: narration-card mismatch (buffer) "
                    "matched=%r candidates=%r real=%r info=%s",
                    pm.group(0), cands, real, info,
                )
                return reply + self._NARRATION_MISMATCH_CORRECTION

        if turn_tool_calls > 0 or turn_cards_created > 0 or turn_dialogs_opened > 0:
            return reply

        m = self._CLAIM_PATTERN.search(reply)
        if not m:
            return reply
        logger.info(
            "honesty guard: chat_claim_rewritten "
            "(tool_calls=%d cards=%d dialogs=%d matched=%r) | orig=%s",
            turn_tool_calls, turn_cards_created, turn_dialogs_opened,
            m.group(0),
            reply[:100].replace("\n", " "),
        )
        return self._HONEST_STUB

    def honesty_guard_post_stream(
        self,
        full_reply: str,
        *,
        channel: str,
        chat_id: str,
    ) -> tuple[Optional[str], Optional[str]]:
        """Post-stream guard check for surfaces that have already sent
        sentences before the full reply was available (Telegram streaming
        mode). Returns (state_claim_correction, narration_correction) —
        either or both may be None.

        State-claim correction fires when _STATE_CLAIM_PATTERN matched
        AND no real card exists (can't refer to waiting state that isn't
        there). Narration-card correction fires when a proposal claim
        names commands that don't match any real recent card.

        Caller sends each non-None correction as a follow-up message."""
        if not full_reply:
            return None, None

        state_corr: Optional[str] = None
        narration_corr: Optional[str] = None

        sm = self._STATE_CLAIM_PATTERN.search(full_reply)
        if sm and not self.has_awaiting_card(channel=channel, chat_id=chat_id):
            logger.info(
                "honesty guard: chat_state_claim_correction "
                "(streaming, matched=%r) | orig=%s",
                sm.group(0), full_reply[:100].replace("\n", " "),
            )
            state_corr = (
                f"Correction: {self._HONEST_STUB} "
                f"Disregard any earlier mention of pending approval, "
                f"a previous approved request, or an active session — "
                f"no such state actually exists right now."
            )
        elif sm:
            logger.info(
                "honesty guard: state-claim suppressed — real "
                "pending card exists (matched=%r)", sm.group(0),
            )

        pm = self._PROPOSED_CMD_PATTERN.search(full_reply)
        if pm:
            ok, info, cands, real = self.narration_matches_real_card(
                full_reply, channel=channel, chat_id=chat_id,
            )
            if not ok:
                logger.info(
                    "honesty guard: narration-card mismatch (streaming) "
                    "matched=%r candidates=%r real=%r info=%s",
                    pm.group(0), cands, real, info,
                )
                narration_corr = (
                    "⚠ Correction: I misspoke above — the command(s) I "
                    "mentioned as proposed aren't actually queued. "
                    "Disregard that part; any real pending card will "
                    "show up as its own Telegram card."
                )

        return state_corr, narration_corr

    # ════════════════════════════════════════════════════════ #
    #  Offer-binding (layer: offer_binding)                     #
    # ════════════════════════════════════════════════════════ #

    def is_offer_approval(self, text: str) -> bool:
        """Whole-message bare-approval match. Mixed content like
        'yes and also...' does not match — falls through to chat."""
        if not text:
            return False
        return bool(self._OFFER_APPROVAL_PATTERN.match(text))

    def reply_contains_offer(self, reply: str) -> bool:
        """True if reply contains a soft web_search offer phrase."""
        if not reply:
            return False
        return bool(self._OFFER_PATTERN.search(reply))

    def get_offer(self, channel: str, chat_id: str) -> Optional[dict]:
        """Return live offer dict or None. Silently clears on TTL expiry."""
        import time as _time
        with self._offers_lock:
            offer = self._offers.get((channel, chat_id))
            if offer is None:
                return None
            set_at = float(offer.get("set_at", 0))
            if (_time.time() - set_at) > self._OFFER_TTL_SECONDS:
                self._offers.pop((channel, chat_id), None)
                return None
            return offer

    def set_offer(self, channel: str, chat_id: str, offer: dict) -> None:
        """Store a pending offer for (channel, chat_id). Overwrites any
        existing offer — callers are expected to check first if they care."""
        with self._offers_lock:
            self._offers[(channel, chat_id)] = offer

    def clear_offer(
        self,
        channel: str,
        chat_id: str,
        *,
        reason: str = "",
    ) -> Optional[dict]:
        """Remove and return any stored offer. reason goes to debug log."""
        with self._offers_lock:
            offer = self._offers.pop((channel, chat_id), None)
        if offer is not None and reason:
            logger.debug(
                "offer binding: cleared offer for (%s,%s) reason=%s",
                channel, chat_id, reason,
            )
        return offer

    def get_search_offer(self, channel: str, chat_id: str):
        """Return the typed search commitment receipt for tests/diagnostics.

        The commitment slot is separate from the legacy untyped `_offers` slot
        so enabling the new organ cannot accidentally read old regex-captured
        promises.
        """
        with self._offers_lock:
            return self._search_receipts.get((channel, chat_id))

    def store_search_offer(
        self,
        channel: str,
        chat_id: str,
        query: str,
        *,
        health: str,
        now_ts: float | None = None,
        ttl_seconds: float = 300.0,
        ttl_turns: int = 3,
    ) -> bool:
        """Store a typed sovereign-local search offer when the flag is on.

        Capability truth is checked before the offer exists. Degraded/down
        search stores nothing, so there is no executable promise to later bind.
        """
        if not _search_commitment_enabled():
            return False
        query = (query or "").strip()
        if not query or health != "healthy":
            return False
        from core.search.search_commitment import OfferReceipt

        receipt = OfferReceipt(
            action_type="web_search",
            stakes="low_read",
            offered_query=query,
            created_ts=time.time() if now_ts is None else now_ts,
            ttl_seconds=ttl_seconds,
            ttl_turns=ttl_turns,
            requires_confirmation=True,
            confirmation_mode="clear_yes_ok",
            executor="searxng",
            egress_class="sovereign_local_search",
        )
        with self._offers_lock:
            self._search_receipts[(channel, chat_id)] = receipt
        return True

    def resolve_search_affirmation(
        self,
        channel: str,
        chat_id: str,
        text: str,
        backend,
        *,
        now_ts: float | None = None,
        turns_since: int = 1,
    ) -> list[dict] | None:
        """Resolve a bare affirmation against the typed search receipt.

        Returns search results only when the trap-proof conjunction passes.
        Otherwise returns None and never touches the backend search method.
        """
        if not _search_commitment_enabled():
            return None
        from core.search.search_commitment import resolve_affirmation

        key = (channel, chat_id)
        with self._offers_lock:
            receipt = self._search_receipts.get(key)
        if receipt is None:
            return None
        health = backend.health()
        decision = resolve_affirmation(
            receipt,
            text,
            health=health,
            has_awaiting_card=self.has_awaiting_card(channel, chat_id),
            now_ts=time.time() if now_ts is None else now_ts,
            turns_since=turns_since,
        )
        if not decision.execute:
            if decision.reason == "stale_offer":
                with self._offers_lock:
                    self._search_receipts.pop(key, None)
            return None
        results = backend.search(decision.query)
        with self._offers_lock:
            self._search_receipts.pop(key, None)
        return results

    def maybe_store_offer(
        self,
        channel: str,
        chat_id: str,
        *,
        reply: str,
        raw_user_text: str,
        query_deriver,
    ) -> bool:
        """Store a pending web_search offer if reply contains an offer
        phrase AND no awaiting card exists AND query_deriver returns a
        non-empty query. Returns True if stored.

        query_deriver is a callable (str) -> str that derives a search
        query from the raw user text. Provided by the adapter so the
        controller stays surface-agnostic (each surface knows how to
        compose machine-specific context).
        """
        if _search_commitment_enabled():
            return False
        import time as _time
        try:
            if not self.reply_contains_offer(reply):
                return False
            if self.has_awaiting_card(channel=channel, chat_id=chat_id):
                return False
            raw = (raw_user_text or "").strip()
            query = (query_deriver(raw) or "").strip() if query_deriver else raw
            if not query:
                return False
            self.set_offer(channel, chat_id, {
                "kind": "web_search",
                "query": query,
                "raw_query": raw,
                "set_at": _time.time(),
                "offer_preview": (reply or "")[:120].replace("\n", " "),
            })
            logger.info(
                "offer binding: stored pending web_search "
                "(%s,%s) | query=%r raw=%r",
                channel, chat_id, query[:80], raw[:60],
            )
            return True
        except Exception as e:
            logger.debug("offer binding store failed: %s", e)
            return False

    def maybe_store_probe_bridge_offer(
        self,
        channel: str,
        chat_id: str,
        *,
        reply: str,
        raw_user_text: str,
        query_deriver,
        had_action: bool,
    ) -> bool:
        """Probe→pending bridge. Called when:
          - a probe ran this turn (Jarvis fired a Lane-0 action)
          - AND reply narrated fake pending/approved/session state
          - AND no explicit offer was already stored
          - AND no real awaiting card exists
        Converts 'probe → fake narration → Yes does nothing' into
        'probe → real pending offer → Yes runs search'. Returns True
        if an offer was auto-stored."""
        if _search_commitment_enabled():
            return False
        import time as _time
        try:
            if not (had_action and reply):
                return False
            if self.get_offer(channel, chat_id) is not None:
                return False
            if not self._STATE_CLAIM_PATTERN.search(reply):
                return False
            if self.has_awaiting_card(channel=channel, chat_id=chat_id):
                return False
            raw = (raw_user_text or "").strip()
            query = (query_deriver(raw) or "").strip() if query_deriver else raw
            if not query:
                return False
            self.set_offer(channel, chat_id, {
                "kind": "web_search",
                "query": query,
                "raw_query": raw,
                "set_at": _time.time(),
                "offer_preview": (
                    "[auto from probe+state-claim] "
                    + reply[:80].replace("\n", " ")
                ),
            })
            logger.info(
                "offer binding: auto-stored from probe+state-claim "
                "(%s,%s) | query=%r raw=%r",
                channel, chat_id, query[:80], raw[:60],
            )
            return True
        except Exception as e:
            logger.debug("probe->pending bridge failed: %s", e)
            return False

    def consume_offer_approval(
        self,
        channel: str,
        chat_id: str,
        text: str,
    ) -> tuple[str, Optional[dict]]:
        """One-call decision helper for adapter-level offer-binding.

        Returns (status, offer):
          - ("fire", offer): caller should execute offer['query'] and
            clear on completion (offer is already cleared from store).
          - ("defer_to_card", None): real card exists, caller should
            fall through to card-reply handling.
          - ("context_shift", None): live offer existed but text is not
            a bare approval — cleared silently, caller falls through.
          - ("none", None): no live offer (never existed / TTL expired).
          - ("not_web_search", None): offer exists but kind != web_search
            — caller falls through (narrow safety rail)."""
        if _search_commitment_enabled():
            return "none", None
        offer = self.get_offer(channel, chat_id)  # TTL-aware
        if offer is None:
            return "none", None
        if self.has_awaiting_card(channel=channel, chat_id=chat_id):
            logger.info(
                "offer binding: real pending card exists — deferring "
                "to card-reply, clearing stored offer | text=%r",
                (text or "")[:60],
            )
            self.clear_offer(channel, chat_id, reason="awaiting_card")
            return "defer_to_card", None
        if not self.is_offer_approval(text):
            logger.info(
                "offer binding: clearing stale offer on context shift "
                "| text=%r", (text or "")[:60],
            )
            self.clear_offer(channel, chat_id, reason="context_shift")
            return "context_shift", None
        if offer.get("kind") != "web_search":
            return "not_web_search", None
        if not (offer.get("query") or "").strip():
            self.clear_offer(channel, chat_id, reason="empty_query")
            return "none", None
        # Pop and return — caller owns the fire
        with self._offers_lock:
            self._offers.pop((channel, chat_id), None)
        return "fire", offer

    # ════════════════════════════════════════════════════════ #
    #  Next-step parse helpers (layer: next_step_parse)         #
    # ════════════════════════════════════════════════════════ #

    def is_exploratory_ask(self, user_text: str) -> bool:
        """Heuristic: does the user's message look like exploratory
        planning ('figure out how to', 'tell me the path', 'can you
        find/explore') rather than a direct action ask ('install X',
        'run Y')? Triggers the exploratory next-step prompt path."""
        if not user_text or len(user_text) > 600:
            return False
        return bool(self._EXPLORATORY_ASK_PATTERN.search(user_text))

    def parse_next_step_line(
        self, text: str,
    ) -> tuple[Optional[str], Optional[str]]:
        """Parse 'NEXT_STEP: <cmd>' / 'NEXT_STEP: read: <cmd>' /
        'NEXT_STEP: action: <cmd>' / 'NEXT_STEP: none' from LLM output.

        Returns (cmd, label):
          - (None, None) — parse failed or 'none'
          - (cmd, None)  — plain command, no kind label (non-exploratory)
          - (cmd, 'read') / (cmd, 'action') — labeled (exploratory)

        The label is advisory: dispatch routes uniformly through the
        pipeline which lane-classifies. Logging uses the label when
        present for post-hoc audit."""
        if not text:
            return (None, None)
        for raw in text.strip().splitlines():
            line = raw.strip()
            if not line.upper().startswith("NEXT_STEP:"):
                continue
            rest = line[len("NEXT_STEP:"):].strip().strip("`").strip()
            if not rest or rest.lower() == "none":
                return (None, None)
            label: Optional[str] = None
            for pref in ("read:", "action:"):
                if rest.lower().startswith(pref):
                    label = pref.rstrip(":")
                    rest = rest[len(pref):].strip().strip("`").strip()
                    break
            if not rest or rest.lower() == "none":
                return (None, None)
            lower = rest.lower()
            for bad in ("<cmd>", "<command>", "...", "tbd", "placeholder"):
                if bad in lower:
                    return (None, None)
            if len(rest) > 500:
                return (None, None)
            return (rest, label)
        return (None, None)

    # ════════════════════════════════════════════════════════ #
    #  Next-step proposer (layer: next_step_proposer)           #
    # ════════════════════════════════════════════════════════ #

    def _get_pipeline(self) -> Any:
        """Return the action pipeline, or None. Mirrors _card_store() but
        returns the pipeline itself for callers that need handle_action()."""
        pipe = self.pipeline
        if pipe is None and self._pipeline_getter is not None:
            try:
                pipe = self._pipeline_getter()
            except Exception as e:
                logger.debug("controller: pipeline_getter raised: %s", e)
                pipe = None
        return pipe

    def propose_next_step_from_probe(
        self,
        user_text: str,
        *,
        channel: str,
        chat_id: str,
        audit_db_path: str | None = None,
        user_id: str | None = None,
        model: str = _DEFAULT_MODEL,
    ) -> Optional[dict]:
        """After Jarvis probes complete, run ONE focused structured LLM
        call to propose a single concrete next-step action based on the
        real probe result, then route it through the pipeline so
        classification / audit / lane routing apply uniformly.

        Returns:
          {'kind': 'executed'|'card_created'|'dialog_opened'|'refused'
                   |'none'|'skipped', 'summary': str}
          or None on total failure (caller proceeds without it).

        Scope: synchronous (called from executor). Single-shot per turn.
        No Lane-3 escalation — we hand the proposal to the pipeline and
        let it route.
        """
        import sqlite3 as _sqlite
        import time as _time

        # Resolve the audit DB lazily through the canonical resolver so the
        # path is anchored under paths.home() rather than the process CWD
        # (a bare-relative default would open a shadow DB when the daemon is
        # launched from a different directory).
        if audit_db_path is None:
            from core.infra import paths as _paths
            audit_db_path = str(_paths.audit_log_db())

        # Resolve default user_id from identity rather than hardcoding
        # "rohit". On a fresh install the owner's configured user_id
        # drives trust-scope routing.
        if user_id is None:
            try:
                from core.identity import user_profile_id as _owner_user_id
                user_id = _owner_user_id()
            except Exception:
                user_id = "owner"

        try:
            since = _time.time() - 60
            conn = _sqlite.connect(str(audit_db_path))
            conn.row_factory = _sqlite.Row
            rows = conn.execute(
                "SELECT ts, action, params_json, outcome, outcome_notes "
                "FROM audit_log "
                "WHERE ts >= ? AND outcome IN ('approved_and_ran', "
                "'approved_and_failed') "
                "ORDER BY ts DESC LIMIT 4",
                (since,),
            ).fetchall()

            # Also fetch failed commands from the last 10 minutes so the
            # proposer doesn't re-suggest something that already failed this
            # session (e.g. proposing `sudo apt install openrgb` again after
            # it failed twice in the same conversation).
            failed_rows = conn.execute(
                "SELECT params_json, outcome_notes "
                "FROM audit_log "
                "WHERE ts >= ? AND outcome = 'approved_and_failed' "
                "ORDER BY ts DESC LIMIT 8",
                (_time.time() - 600,),
            ).fetchall()
            conn.close()

            already_failed: list[str] = []
            for r in failed_rows:
                try:
                    p = _json.loads(r["params_json"] or "{}")
                    cmd = p.get("cmd") or ""
                    if cmd and cmd not in already_failed:
                        already_failed.append(cmd[:200])
                except Exception:
                    pass

            useful_rows = []
            for r in rows:
                notes = (r["outcome_notes"] or "").strip()
                is_success = r["outcome"] == "approved_and_ran"
                if is_success:
                    useful_rows.append(r)
                elif len(notes) > 30:
                    useful_rows.append(r)
                if len(useful_rows) >= 2:
                    break

            if not useful_rows:
                return {"kind": "skipped", "summary": "no recent useful probe"}

            probe_summaries: list[str] = []
            for r in useful_rows:
                p: dict = {}
                try:
                    p = _json.loads(r["params_json"] or "{}")
                except Exception:
                    pass
                arg = p.get("cmd") or p.get("query") or "?"
                notes = (r["outcome_notes"] or "(no output)").strip()
                status_tag = (
                    "SUCCESS" if r["outcome"] == "approved_and_ran"
                    else "EXIT_NONZERO (stdout may still be useful)"
                )
                probe_summaries.append(
                    f"- {r['action']} [{status_tag}]: {str(arg)[:120]}\n"
                    f"  result: {notes[:400]}"
                )
            probes_text = "\n".join(probe_summaries)

            failed_block = ""
            if already_failed:
                failed_block = (
                    "\nCOMMANDS THAT ALREADY FAILED IN THIS SESSION "
                    "(do NOT re-propose any of these):\n"
                    + "\n".join(f"  - {c}" for c in already_failed)
                    + "\n"
                )

            exploratory = self.is_exploratory_ask(user_text)
            if exploratory:
                system_msg = (
                    "You are translating an EXPLORATORY user question + "
                    "recent probe results into ONE concrete next step "
                    "toward the user's goal.\n\n"
                    "OUTPUT FORMAT — one line, starting with exactly "
                    "'NEXT_STEP:'. One of:\n"
                    "  NEXT_STEP: read: <shell command>\n"
                    "  NEXT_STEP: action: <shell command that changes state>\n"
                    "  NEXT_STEP: none\n\n"
                    "Labels:\n"
                    "  - 'read:' = another probe or query (lsusb, cat "
                    "/sys/..., find, grep on existing file). Use when "
                    "probes so far haven't uncovered the key context "
                    "you need.\n"
                    "  - 'action:' = a state-changing command "
                    "(sudo apt install <pkg>, echo X > /path, "
                    "systemctl enable Y, modprobe Z). Use when you have "
                    "enough evidence to propose a real install/config "
                    "step.\n"
                    "  - 'none' = the probes already answer the user's "
                    "question, or no reasonable step exists.\n\n"
                    "CRITICAL DISCIPLINE:\n"
                    "- Don't keep probing forever. After 1-2 successful "
                    "probes, strongly prefer 'action:' over more "
                    "'read:'. The user asked for a concrete path, not "
                    "an infinite survey.\n"
                    "- 'action:' examples from probe evidence:\n"
                    "    probe found 'Alienware LED controller' via "
                    "lsusb, openrgb not installed → action: "
                    "sudo apt install -y openrgb\n"
                    "    probe found /sys/class/leds/X → action: "
                    "cat /sys/class/leds/X/brightness\n"
                    "    (when the action reads a file that's already "
                    "known to exist, it's still 'action:' if it "
                    "commits to 'here is the path'; label it 'read:' "
                    "only if you're genuinely still searching.)\n"
                    "- EXIT_NONZERO probes may still have useful stdout "
                    "— read the stdout, don't just trust the exit code.\n"
                    "- Don't re-propose the same command a probe "
                    "already ran.\n"
                    "- No placeholders, no ellipsis, no TBD.\n"
                    "- If you emit 'action:', the pipeline will create "
                    "a real approval card — that IS how you ask for "
                    "permission. Do NOT also narrate 'waiting for "
                    "approval' anywhere.\n"
                    "- NO prose, NO explanation. ONLY the NEXT_STEP line."
                )
            else:
                system_msg = (
                    "You are producing a structured next-step proposal. "
                    "Read the user question and the actual probe results, "
                    "then propose exactly ONE concrete safe shell command "
                    "that advances the user's question given what the probe "
                    "found, or 'none'.\n\n"
                    "OUTPUT FORMAT — one line, starting with exactly "
                    "'NEXT_STEP:', nothing before it, nothing after the "
                    "command. One of:\n"
                    "  NEXT_STEP: <single concrete shell command>\n"
                    "  NEXT_STEP: none\n\n"
                    "Rules:\n"
                    "- Command must be real and specific. No placeholders, "
                    "no ellipsis, no 'TBD'.\n"
                    "- A probe marked EXIT_NONZERO may still have useful "
                    "stdout — read the stdout, don't just trust the exit "
                    "status. A pipeline like `lsusb && grep foo` can exit "
                    "nonzero because grep matched nothing, while lsusb's "
                    "stdout still contains the answer. Do NOT propose "
                    "rerunning the same failing command — propose a "
                    "different concrete step that uses what stdout showed.\n"
                    "- Do NOT propose the same command that just failed.\n"
                    "- If the probe result already answers fully, output "
                    "'NEXT_STEP: none'.\n"
                    "- If you do not have enough data, output 'NEXT_STEP: "
                    "none'.\n"
                    "- No prose, no explanation. ONLY the NEXT_STEP line."
                )
            user_msg = (
                f"USER QUESTION: {user_text[:300]}\n\n"
                f"PROBE RESULTS:\n{probes_text}\n"
                f"{failed_block}\n"
                f"What is the single next-step command that advances "
                f"the user's question?"
            )

            from core import llm_client as _llm_client
            from core.routing.brain_gateway import with_purpose as _brain_purpose
            from core.routing.cancellable_brain_call import BrainPreempted

            with _brain_purpose("owner_reply"):
                resp = _llm_client.chat(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_msg},
                        {"role": "user", "content": user_msg},
                    ],
                    stream=False,
                    think=False,
                    options={"temperature": 0.2, "num_predict": 120},
                )
            raw = getattr(getattr(resp, "message", None), "content", None)
            if raw is None:
                raw = str(resp)
            raw = raw.strip()
        except BrainPreempted:
            raise
        except Exception as e:
            logger.debug("next-step proposer LLM call failed: %s", e)
            return None

        cmd, label = self.parse_next_step_line(raw)
        if cmd is None:
            logger.info(
                "next-step proposer: NEXT_STEP: none (or parse miss) "
                "| exploratory=%s raw=%r",
                exploratory, raw[:120].replace("\n", " "),
            )
            return {"kind": "none", "summary": "no concrete next step"}

        logger.info(
            "next-step proposer: dispatching cmd=%r label=%s exploratory=%s",
            cmd[:120], label, exploratory,
        )

        try:
            pipe = self._get_pipeline()
            if pipe is None:
                return {"kind": "none", "summary": "pipeline unavailable"}
            presult = pipe.handle_action(
                action="run_shell",
                params={"cmd": cmd},
                reason=f"next-step from probe: {user_text[:100]}",
                user_id=user_id,
                chat_id=chat_id,
                channel=channel,
            )
            from core.decision_pipeline import PipelineStatus as _PS
            status = getattr(presult, "status", None)
            if status == _PS.EXECUTED:
                out = (presult.execution_output or "").strip()[:300]
                logger.info(
                    "next-step proposer: EXECUTED cmd=%r output=%r",
                    cmd[:80], out[:100],
                )
                return {"kind": "executed", "summary": out}
            if status == _PS.PENDING_APPROVAL:
                card_id = (
                    getattr(presult.card, "request_id", "?")[:8]
                    if presult.card else "?"
                )
                logger.info(
                    "next-step proposer: card_created id=%s cmd=%r",
                    card_id, cmd[:80],
                )
                return {"kind": "card_created", "summary": cmd[:120]}
            if status == _PS.PENDING_DIALOG:
                logger.info(
                    "next-step proposer: dialog_opened cmd=%r", cmd[:80]
                )
                return {"kind": "dialog_opened", "summary": cmd[:120]}
            logger.info(
                "next-step proposer: refused status=%s cmd=%r",
                status, cmd[:80],
            )
            return {"kind": "refused", "summary": f"status={status}"}
        except Exception as e:
            logger.debug("next-step proposer pipeline dispatch failed: %s", e)
            return None


# ============================================================ #
#  Module-level helpers (future home for extracted constants)   #
# ============================================================ #

# The patterns, allowlists, and stubs currently defined on
# TelegramVoice (lines ~1879-2036 of skills/telegram_voice.py) will
# move here as they are extracted. Kept as class-level constants on
# the controller for encapsulation rather than module globals, so the
# test harness can swap them in subclasses without monkey-patching.
