# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""
maez_adapter.py — bridges the vendored platform adapter layer into
Maez's brain.

The vendored `BasePlatformAdapter` exposes a `MessageHandler` protocol:

    MessageHandler = Callable[[MessageEvent], Awaitable[Optional[str]]]

`MaezMessageHandler` implements that protocol by taking a `MessageEvent`,
running Maez's standard pre-processing (inner-residue, approval-session
detection), dispatching through the daemon's synchronous `handle_message`
in an executor, and post-auditing the reply with the self-claim audit.

That's the full Maez-specific wiring. Everything else — covenant,
decision pipeline, owner-trust, capability registry, organism loops —
is already invoked transitively by `daemon.handle_message` and by the
audit path.

Bootstrap entry point is `build_telegram_adapter(...)`. Caller is
responsible for scheduling `adapter.connect()` on an event loop.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from typing import Any, Optional

from core.health.shared_executor import get_shared_executor
from core.routing.brain_gateway import (
    BrainPurpose,
    copy_current_context_callable,
    with_purpose,
)
from core.conversation_controller import _search_commitment_enabled
from core.cognition.parity_flag import (
    s7_ceremony_bridge_enabled,
    surface_parity_enabled,
)
from core.infra.env_flags import strict_env_flag
from daemon.inbound_core import inbound_core_v2_enabled, run_inbound_turn
from core.search.sense_flag import sense_enabled
from core.search.search_commitment import is_clear_yes, is_search_offer_worthy
from core.safety.clinical_boundary import PrivateThoughtsCrisisSignalWriter, guard_owner_text
from skills.surface.platform_base import MessageEvent, MessageType
from skills.surface.platform_config import PlatformConfig
from skills.surface.telegram_adapter import TelegramAdapter


# 2026-04-23: strip the stored prompt envelope before passing a prior
# exchange to run_brain_loop as chat_history. Stored content shapes:
#
#   (a) daemon telegram  (daemon/maez_daemon.py:1346):
#       the owner (<source>): <USER_MSG>
#       [<TURN STATE/FORBIDDEN/JARVIS TRANSCRIPT/etc. envelope>]
#       Maez: <REPLY>
#
#   (b) web + telegram_voice  (web_interface.py, telegram_voice.py):
#       the owner asked: <USER_MSG>
#       Maez replied: <REPLY>
#
# Passing form (a) raw would flood the planning prompt with stale
# FORBIDDEN and AMBIGUOUS-REFERENT rule text from the previous turn,
# burying the actual Q/A signal. Form (b) has no envelope but the
# `Maez replied:` delimiter doesn't match the daemon-form
# `Maez:` delimiter the parser expected.
#
# 2026-04-24 audit pass (F4): both forms now clean to the same
# shape — `"<display_name>: <USER_MSG>\nMaez: <REPLY>"` — so the
# downstream `core.brain.conversation_history.history_to_messages`
# threads them uniformly. Without this, web + voice follow-ups
# silently lost continuity threading (the failure we just closed
# for telegram in commit cc462c5).
_SOURCE_PREFIX_RE = re.compile(r"^the owner \([^)]+\):\s*")
_ASKED_PREFIX_RE = re.compile(r"^the owner asked:\s*")
_ASSISTANT_MARKER_DAEMON = "\nMaez:"
_ASSISTANT_MARKER_WEB_VOICE = "\nMaez replied:"


def _clean_exchange(doc: str) -> str:
    """Collapse a stored telegram_exchange envelope to a clean Q/A pair.

    Handles two stored forms (see module-level note):
      (a) daemon telegram:      `the owner (<source>): <msg>\\n[envelope]\\nMaez: <reply>`
      (b) web + telegram_voice: `the owner asked: <msg>\\nMaez replied: <reply>`

    Any other shape (operational notes like card-state summaries,
    recovery markers, test fixtures, future formats) passes through
    unchanged so this helper is safe to add without migrating every
    caller. The downstream parser rejects unparseable passthroughs.

    The owner-side prefix used in the cleaned output is resolved from
    `core.memory.identity.display_name()` at call time — not hardcoded
    — so a fresh install with `display_name="Friend"` (or any other
    configured value) produces self-consistent conversation history.
    Falls back to a generic "Owner:" if identity lookup fails so the
    cleaner can never crash a surface turn.
    """
    if not doc:
        return ""
    first_line = doc.split("\n", 1)[0]
    user_msg = None
    reply = None

    # Try daemon form first — the `\nMaez:` marker is more
    # restrictive than `\nMaez replied:`, so match that explicitly.
    if _SOURCE_PREFIX_RE.match(first_line):
        user_msg = _SOURCE_PREFIX_RE.sub("", first_line).strip()
        # The reply is appended after a final "\nMaez:" delimiter
        # (prefer `rfind` so an embedded "Maez:" mention in the
        # envelope can't fool us — the real reply is always the last
        # segment).
        pos = doc.rfind(_ASSISTANT_MARKER_DAEMON)
        if pos == -1:
            pos = doc.find(_ASSISTANT_MARKER_DAEMON)
        if pos < 0:
            return doc
        reply = doc[pos + len(_ASSISTANT_MARKER_DAEMON) :].strip()
    # Then the web/voice form — single-line user, `\nMaez replied:`
    # marker, no envelope between.
    elif _ASKED_PREFIX_RE.match(first_line):
        user_msg = _ASKED_PREFIX_RE.sub("", first_line).strip()
        pos = doc.find(_ASSISTANT_MARKER_WEB_VOICE)
        if pos < 0:
            return doc
        reply = doc[pos + len(_ASSISTANT_MARKER_WEB_VOICE) :].strip()
    else:
        return doc

    if not user_msg and not reply:
        return doc
    try:
        from core.memory.identity import display_name as _display_name

        owner_prefix = _display_name() or "Owner"
    except Exception:
        owner_prefix = "Owner"
    return f"{owner_prefix}: {user_msg}\nMaez: {reply}".strip()


logger = logging.getLogger(__name__)


# Distinct surface label so logs make the routing path obvious during
# parallel operation with the legacy `skills/telegram_voice.py` path.
# When the old path is retired, this can be renamed to simply
# "telegram" or "telegram_text" (the current legacy label).
SURFACE_NAME = "telegram_surface"

# How many prior telegram exchanges to inject into the brain_loop's
# planning context. Kept small on purpose — the planning prompt is
# ~512 tokens and each exchange is capped at 800 chars by
# core.brain_loop, so 3 fits comfortably with headroom for the tool
# manifest. Bump only if the model starts missing context from
# further back; prefer retrieval changes over blind enlargement.
_CHAT_HISTORY_TURNS = 3


class MaezMessageHandler:
    """MessageHandler that plugs Maez's brain into the vendored
    platform adapter.

    Each incoming Telegram message flows through three stages here:
      1. Pre-processing: user-rejection detection (→ inner-residue) and
         blanket-approval detection (→ approval-sessions).
      2. Brain loop: runs `core.brain_loop.run_brain_loop` to let the
         model iterate tool calls through the decision pipeline, then
         calls `daemon.handle_message` for the final text synthesis
         with the jarvis transcript folded in.
      3. Post-processing: self-claim audit rewrites fabrications.

    The brain loop and audit are IDENTICAL to what
    `skills/telegram_voice.py` runs on the legacy path — they both call
    `core.brain_loop.run_brain_loop` so any surface here and any surface
    there produce the same tool-use behavior."""

    def __init__(self, daemon: Any):
        self.daemon = daemon
        self._last_shown_proposal: dict[str, dict[str, Any]] = {}
        self._last_shown_freshness_s = 600.0

    def _search_commitment_controller(self):
        legacy_tg = getattr(self.daemon, "telegram", None)
        return getattr(legacy_tg, "_controller", None)

    def _search_commitment_backend(self):
        from core.search.searxng_client import SearxngBackend

        return SearxngBackend()

    def _format_search_commitment_results(self, query: str, results: list[dict]) -> str:
        label = (query or "the search I offered").strip()
        lines = [f'Here\'s what I found for "{label}":', ""]
        for i, row in enumerate((results or [])[:5], 1):
            title = re.sub(r"\s+", " ", (row.get("title") or "").strip())[:90]
            url = re.sub(r"\s+", "", (row.get("url") or "").strip())[:120]
            content = re.sub(
                r"\s+",
                " ",
                (row.get("content") or row.get("snippet") or "").strip(),
            )[:220]
            lines.append(f"{i}. {title}")
            if content:
                lines.append(f"   {content}")
            if url:
                lines.append(f"   {url}")
            lines.append("")
        reply = "\n".join(lines).rstrip()
        if len(reply) > 3500:
            reply = reply[:3500] + "\n\n(truncated)"
        return reply

    def _audit_surface_reply(self, text: str, *, surface: str) -> str:
        try:
            from core.self_claim_audit import audit as _sc_audit

            result = _sc_audit(text, surface=surface)
            return result.text if result.rewritten else text
        except Exception:
            return text

    def _surface_parity_pending_evolution_candidates(self) -> list[dict]:
        try:
            from skills.evolution_engine import _rail_conn

            with _rail_conn() as conn:
                rows = conn.execute(
                    "SELECT id, target_file, weakness_description, created_at "
                    "FROM candidates WHERE state='validated' "
                    "ORDER BY id DESC LIMIT 10"
                ).fetchall()
            return [
                {
                    "id": row[0],
                    "target_file": row[1],
                    "weakness": row[2],
                    "created_at": row[3],
                }
                for row in rows
            ]
        except Exception:
            logger.debug("surface parity pending evolution query failed", exc_info=True)
            return []

    def _surface_parity_pending_dream_rows(self) -> list[tuple]:
        dream = getattr(self.daemon, "dream", None)
        if dream is None:
            return []
        try:
            return list(dream.list_pending())
        except Exception:
            logger.debug("surface parity pending dream query failed", exc_info=True)
            return []

    def _surface_parity_disambiguation(self, *, pending: list[dict], dream_rows: list[tuple]) -> str:
        lines = [f"I have {len(pending) + len(dream_rows)} proposals pending - which one?", ""]
        for row in pending[:5]:
            lines.append(f"  #{row['id']}: {(row.get('weakness') or '')[:80]}")
        for row in dream_rows[:5]:
            pid, _created, insight = row
            lines.append(f"  #{pid}: {(insight or '')[:80]}")
        lines.append("")
        lines.append('Reply with the number, for example "yes to #22" or "reject #23".')
        return self._audit_surface_reply("\n".join(lines), surface=f"{SURFACE_NAME}_proposal_disambig")

    async def _try_surface_parity_proposal_intent(
        self,
        *,
        text: str,
        chat_id: str,
        pipe: Any = None,
        user_id: str = "rohit",
    ) -> Optional[str]:
        if not surface_parity_enabled():
            return None

        from core.dispatcher.proposal_resolver import (
            detect_proposal_intent,
            resolve_proposal_target,
        )

        action, explicit_id = detect_proposal_intent(text)
        if not action:
            return None

        pending = self._surface_parity_pending_evolution_candidates()
        dream_rows = self._surface_parity_pending_dream_rows()
        evolution_ids = {int(row["id"]) for row in pending}
        dream_ids = {int(row[0]) for row in dream_rows}
        if not pending and not dream_rows and explicit_id is None:
            return None

        last_shown = self._last_shown_proposal.get(chat_id)
        source = None
        target_id: int | None = None

        if explicit_id is not None:
            if explicit_id in evolution_ids:
                source = "evolution"
                target_id = explicit_id
            elif explicit_id in dream_ids:
                source = "dream"
                target_id = explicit_id
            else:
                return f"I don't find proposal #{explicit_id}. It may have expired or already been resolved."
        else:
            target_id = resolve_proposal_target(
                action=action,
                explicit_id=None,
                pending_ids=evolution_ids,
                last_shown=last_shown,
                source="evolution",
                text=text,
                freshness_s=self._last_shown_freshness_s,
            )
            if target_id is not None:
                source = "evolution"
            else:
                target_id = resolve_proposal_target(
                    action=action,
                    explicit_id=None,
                    pending_ids=dream_ids,
                    last_shown=last_shown,
                    source="dream",
                    text=text,
                    freshness_s=self._last_shown_freshness_s,
                )
                if target_id is not None:
                    source = "dream"

        if target_id is None or source is None:
            lowered = (text or "").lower()
            if ("proposal" in lowered or "dream" in lowered) and (len(pending) + len(dream_rows)) > 1:
                return self._surface_parity_disambiguation(pending=pending, dream_rows=dream_rows)
            return None

        loop = asyncio.get_event_loop()
        if source == "dream":
            return await self._surface_parity_handle_dream_proposal(
                action=action,
                target_id=target_id,
                chat_id=chat_id,
                loop=loop,
                pipe=pipe,
                user_id=user_id,
            )
        return await self._surface_parity_handle_evolution_proposal(
            action=action,
            target_id=target_id,
            chat_id=chat_id,
            loop=loop,
        )

    async def _surface_parity_handle_dream_proposal(
        self,
        *,
        action: str,
        target_id: int,
        chat_id: str,
        loop: asyncio.AbstractEventLoop,
        pipe: Any = None,
        user_id: str = "rohit",
    ) -> Optional[str]:
        dream = getattr(self.daemon, "dream", None)
        if dream is None:
            return None
        try:
            prop = dream.get_proposal(target_id)
        except Exception:
            logger.debug("surface parity dream get_proposal failed", exc_info=True)
            return None
        if not prop:
            return f"I don't find proposal #{target_id}. It may have expired or already been resolved."
        status = prop.get("status") or "unknown"
        if status != "pending":
            return f"Proposal #{target_id} is already {status} - nothing to apply/reject."
        try:
            if action == "approve":
                if s7_ceremony_bridge_enabled():
                    def _bridge() -> str:
                        from skills.surface import s7_ceremony_bridge as bridge

                        if not bridge.cockpit_available():
                            return (
                                "The S7 authorization surface isn't running, so I can't "
                                "open the ceremony for this soul-affecting proposal yet. "
                                "Start the cockpit and ask again."
                            )
                        if pipe is None:
                            return (
                                "I can't open the S7 ceremony because the live decision "
                                "pipeline isn't available on this surface."
                            )
                        deps = bridge.LiveBridgeDeps(
                            dream=dream,
                            pipeline=pipe,
                            chat_id=chat_id,
                            user_id=user_id,
                        )
                        seed = bridge.seed_soul_proposal_dialog(
                            prop_id=target_id,
                            deps=deps,
                        )
                        if seed is None:
                            return (
                                f"Proposal #{target_id} has moved on or is no longer pending, "
                                "so I didn't open an S7 ceremony for it."
                            )
                        consult = bridge.consult_then_block_or_pointer(
                            card_request_id=seed.card_request_id,
                            deps=deps,
                        )
                        if consult.blocked or not consult.ceremony_pointer:
                            return (
                                f"Proposal #{target_id} opened an S7 request, but Maez's "
                                "own consultation did not clear it. I blocked the dialog "
                                "instead of asking for your hardware-key proof."
                            )
                        return (
                            f"Proposal #{target_id} needs the S7 ceremony before it can "
                            f"touch my soul. Please complete the S7 ceremony here: "
                            f"{consult.ceremony_pointer}"
                        )

                    return await loop.run_in_executor(get_shared_executor(), _bridge)

                if (prop.get("proposal_type") or "append") == "section_replace":
                    ok, msg = await loop.run_in_executor(
                        get_shared_executor(),
                        lambda: dream.apply_section_edit_proposal(target_id),
                    )
                else:
                    ok, msg = await loop.run_in_executor(
                        get_shared_executor(),
                        lambda: dream.apply_proposal(target_id),
                    )
            elif action == "reject":
                ok, msg = await loop.run_in_executor(
                    get_shared_executor(),
                    lambda: dream.reject_proposal(target_id),
                )
            elif action == "show":
                insight = str(prop.get("insight") or prop.get("summary") or "")[:500]
                self._last_shown_proposal[chat_id] = {
                    "id": int(target_id),
                    "source": "dream",
                    "shown_at": time.time(),
                }
                return self._audit_surface_reply(
                    f"Proposal #{target_id}\n\n{insight}\n\nReply \"yes\" to apply or \"no\" to reject.",
                    surface=f"{SURFACE_NAME}_dream_proposal_show",
                )
            else:
                return None
        except Exception as exc:
            logger.exception("surface parity dream proposal dispatch failed")
            return f"Couldn't process #{target_id}: {exc}"

        prefix = "OK" if ok else "Couldn't"
        return f"{prefix} #{target_id}: {msg}"

    async def _surface_parity_handle_evolution_proposal(
        self,
        *,
        action: str,
        target_id: int,
        chat_id: str,
        loop: asyncio.AbstractEventLoop,
    ) -> Optional[str]:
        try:
            if action == "approve":
                from skills.evolution_engine import apply_candidate

                result = await loop.run_in_executor(
                    get_shared_executor(),
                    lambda: apply_candidate(target_id),
                )
                if "error" in result:
                    return (
                        f"Something went wrong applying #{target_id}: {result['error']}\n"
                        f"{'Rolled back. ' if result.get('rolled_back') else ''}"
                        "Let me know if you want me to try a different proposal."
                    )
                return (
                    f"Done. Proposal #{target_id} is live now. I'll watch the next "
                    "20-30 cycles for any regression and roll back automatically if my score drops."
                )
            if action == "reject":
                from skills.evolution_engine import _log_evolution, _set_candidate_state, V1_ALLOWED_TARGET

                await loop.run_in_executor(
                    get_shared_executor(),
                    lambda: (
                        _set_candidate_state(
                            target_id,
                            "rejected",
                            rejection_reason="manual rejection via Surface V2 natural-language chat",
                        ),
                        _log_evolution(
                            {
                                "action": "MANUAL_REJECTION",
                                "target": V1_ALLOWED_TARGET,
                                "result": f"candidate {target_id}",
                                "detail": "surface_v2_natural_language",
                            }
                        ),
                    ),
                )
                return (
                    f"Got it - proposal #{target_id} is rejected. I'll leave that one alone "
                    "and keep an eye out for other things I could try."
                )
            if action == "show":
                from skills.evolution_engine import load_candidate_for_display

                disp = await loop.run_in_executor(
                    get_shared_executor(),
                    lambda: load_candidate_for_display(target_id),
                )
                if not disp:
                    return f"I can't find proposal #{target_id}."
                intent = disp.get("intent") or {}
                usefulness = disp.get("usefulness") or {}
                self._last_shown_proposal[chat_id] = {
                    "id": int(target_id),
                    "source": "evolution",
                    "shown_at": time.time(),
                }
                lines = [
                    f"Proposal #{target_id}",
                    "",
                    f"What I want to do: {intent.get('human_rationale', '(no plain-English description)')}",
                    "",
                    "Technical details:",
                    f"  File: {disp.get('target_file', '?')}",
                    f"  Target: {intent.get('target_name', '?')}",
                    f"  Before: {intent.get('current_value')!r}",
                    f"  After:  {intent.get('proposed_value')!r}",
                    f"  Technical rationale: {intent.get('rationale', '')[:200]}",
                    "",
                    f"My confidence: {usefulness.get('overall', 'unknown')}",
                    f"  ({usefulness.get('reasoning', '')[:200]})",
                    "",
                    f'Reply "yes" to apply, "no" to reject (or explicit "yes to #{target_id}" / "reject #{target_id}").',
                ]
                return self._audit_surface_reply(
                    "\n".join(lines),
                    surface=f"{SURFACE_NAME}_proposal_show",
                )
        except Exception as exc:
            logger.error("Surface V2 proposal action failed: %s", exc)
            return f"Something went wrong while handling that: {exc}"
        return None

    async def _try_search_commitment_intent(
        self,
        *,
        text: str,
        chat_id: str,
    ) -> Optional[str]:
        if not _search_commitment_enabled():
            return None
        ctrl = self._search_commitment_controller()
        if ctrl is None:
            return None

        channel = "telegram_text"
        backend = self._search_commitment_backend()
        if sense_enabled():
            if not is_search_offer_worthy(text):
                return None
            health = backend.health()
            if health == "healthy":
                return None
            return (
                "My web sense is degraded right now, so I can't check the live web "
                "for this. I can answer from what I already hold if you ask again, "
                "or we can retry the web later."
            )

        receipt = ctrl.get_search_offer(channel, chat_id)
        query = getattr(receipt, "offered_query", "") if receipt is not None else ""
        if receipt is not None and is_clear_yes(text) and backend.health() != "healthy":
            return (
                "My web search is unavailable right now, so I can't follow through "
                "on that search honestly. I'm not going to make up an answer."
            )

        results = ctrl.resolve_search_affirmation(
            channel,
            chat_id,
            text,
            backend,
            turns_since=1,
        )
        if results is not None:
            return self._format_search_commitment_results(query, results)

        if not is_search_offer_worthy(text):
            return None

        health = backend.health()
        query = (text or "").strip()
        if ctrl.store_search_offer(channel, chat_id, query, health=health):
            return f"I can search for this through my local web sense: {query}. Want me to?"
        if health in {"degraded", "down"}:
            return (
                "My web search is degraded right now, so I shouldn't promise a search. "
                "I can answer from what I already know, or we can try again later."
            )
        return None

    def _build_inbound_descriptor(self, event: MessageEvent) -> dict:
        """Assemble the keyword descriptor for daemon.inbound_core.run_inbound_turn.

        Every surface-coupled literal the inline body hardcodes is injected
        here. The transport closures (_send_intermediate / _send_progress_receipt)
        are built capturing the SAME state the inline body captures
        (self._surface_v2_adapter / self._surface_v2_loop / this handler's loop
        / chat_id) so the flag-on path is byte-identical to flag-off.

        Only built when MAEZ_INBOUND_CORE_V2 is ON, so this never runs on the
        default (flag-off) path.
        """
        loop = asyncio.get_event_loop()

        # Surface-decoupling: the adapter now OWNS event-shape resolution so the
        # core stays surface-agnostic. chat_id + resolved_user_id are resolved
        # here exactly as the inline body resolved them (chat_id="" / user_id=
        # "rohit" fallbacks). chat_id is also captured inside the transport
        # closures below, identically to the inline body.
        chat_id = ""
        resolved_user_id = "rohit"
        try:
            src = event.source
            if src and src.chat_id:
                chat_id = str(src.chat_id)
            if src and src.user_id:
                resolved_user_id = str(src.user_id)
        except Exception:
            pass

        # has_local_photo_context computation moves OUT of the core (so the core
        # no longer imports MessageType) and INTO the adapter; the core consumes
        # the resulting bool as ``is_photo_turn``.
        is_photo_turn = bool(
            event.message_type == MessageType.PHOTO
            and event.channel_prompt
            and "Local Maez vision analysis" in str(event.channel_prompt)
        )

        adapter = getattr(self.daemon, "_surface_v2_adapter", None)
        adapter_loop = getattr(self.daemon, "_surface_v2_loop", None)

        def _send_intermediate(msg_text: str) -> None:
            if not adapter or not adapter_loop or not chat_id:
                return
            try:
                from core.egress.provenance import ProvenancedText

                payload = ProvenancedText.maez_authored_owner_third_party_transport(
                    msg_text,
                    source_ref=f"{SURFACE_NAME}:self_mod_dialog_intermediate",
                )
                coro = adapter.send(chat_id, payload)
                fut = asyncio.run_coroutine_threadsafe(coro, adapter_loop)
                fut.result(timeout=20)
            except Exception as e:
                logger.warning(
                    "send_intermediate failed on %s: %s",
                    SURFACE_NAME,
                    e,
                )

        def _send_progress_receipt(
            msg_text: str,
            *,
            on_complete=None,
            should_send=None,
        ) -> None:
            def _complete(result: str) -> None:
                if on_complete is None:
                    return
                try:
                    on_complete(result, time.monotonic())
                except Exception:
                    logger.debug("recall progress receipt completion callback failed")

            if not adapter or not loop or not chat_id:
                _complete("failed")
                return

            async def _send() -> None:
                try:
                    if should_send is not None and not should_send():
                        _complete("failed")
                        return
                    from core.egress.provenance import ProvenancedText
                    from core.routing.recall_receipt import RECEIPT_SEND_TIMEOUT_MS

                    payload = ProvenancedText.maez_authored_owner_third_party_transport(
                        msg_text,
                        source_ref=f"{SURFACE_NAME}:recall_progress_receipt",
                    )
                    result = await asyncio.wait_for(
                        adapter.send(chat_id, payload),
                        timeout=RECEIPT_SEND_TIMEOUT_MS / 1000.0,
                    )
                    _complete("ok" if getattr(result, "success", False) else "failed")
                except asyncio.TimeoutError:
                    _complete("timeout")
                except Exception as e:
                    logger.debug(
                        "recall progress receipt send failed on %s: %s",
                        SURFACE_NAME,
                        type(e).__name__,
                    )
                    _complete("failed")

            try:
                asyncio.run_coroutine_threadsafe(_send(), loop)
            except Exception as e:
                logger.debug(
                    "recall progress receipt scheduling failed on %s: %s",
                    SURFACE_NAME,
                    type(e).__name__,
                )
                _complete("failed")

        def _owner_auth_factory():
            from core.evolution.subjective_duration import SubjectiveDurationOwnerAuth

            return SubjectiveDurationOwnerAuth(
                surface="telegram_owner",
                proof="telegram_authorized_user",
            )

        def _chat_history_provider(limit: int):
            _mem = getattr(self.daemon, "memory", None)
            return _mem.get_telegram_exchanges(limit=limit)

        action_engine = getattr(self.daemon, "actions", None)
        legacy_tg = getattr(self.daemon, "telegram", None)
        get_pipeline = (
            getattr(legacy_tg, "_get_pipeline", None) if legacy_tg is not None else None
        )

        return dict(
            daemon=self.daemon,
            text=event.text or "",
            raw_platform_metadata=getattr(event, "raw_message", None),
            chat_id=chat_id,
            resolved_user_id=resolved_user_id,
            reply_to_message_id=getattr(event, "reply_to_message_id", None),
            context_note=event.channel_prompt,
            photo_analysis=getattr(event, "photo_analysis_text", None),
            is_photo_turn=is_photo_turn,
            owner_surface_label=SURFACE_NAME,
            user_id="rohit",
            channel="telegram_text",
            owner_auth_factory=_owner_auth_factory,
            observe_turn_label="telegram_turn",
            chat_history_turns=_CHAT_HISTORY_TURNS,
            action_engine=action_engine,
            get_pipeline=get_pipeline,
            chat_history_provider=_chat_history_provider,
            try_proposal_intent=self._try_surface_parity_proposal_intent,
            try_search_commitment_intent=self._try_search_commitment_intent,
            search_commitment_controller=self._search_commitment_controller,
            audit_surface_reply=self._audit_surface_reply,
            clean_exchange=_clean_exchange,
            send_intermediate=_send_intermediate,
            send_progress_receipt=_send_progress_receipt,
        )

    async def __call__(self, event: MessageEvent) -> Optional[str]:
        text = (event.text or "").strip()
        if not text:
            return None

        # SLICE 0 strangler seam — flag-gated delegation to the
        # surface-agnostic inbound core. DEFAULT OFF. When ON, the entire
        # inbound pipeline below is run from daemon.inbound_core.run_inbound_turn
        # with every surface-coupled literal injected via the descriptor. When
        # OFF (default), the EXISTING inline body below runs UNTOUCHED — this is
        # the byte-identical path proven by tests/test_inbound_core_equivalence.
        if inbound_core_v2_enabled():
            return await run_inbound_turn(**self._build_inbound_descriptor(event))

        _s4_result = guard_owner_text(
            text,
            surface=SURFACE_NAME,
            crisis_signal_writer=PrivateThoughtsCrisisSignalWriter(
                getattr(self.daemon, "private_thoughts", None)
            ),
        )
        if _s4_result.matched:
            mark = getattr(self.daemon, "_mark_m1_s4_policy", None)
            if callable(mark):
                mark(_s4_result.promotion_policy)
            return _s4_result.answer_text

        # Pre-processing — same signals the daemon's own
        # handle_message path picks up. Safe to run here too because
        # both detections are idempotent for a single turn.
        try:
            from core import inner_residue as _residue

            if _residue.detect_user_rejection(text):
                _residue.record(
                    kind="user_rejection",
                    context={"surface": SURFACE_NAME},
                )
        except Exception:
            pass

        try:
            from core import approval_sessions as _approvals

            _approvals.detect_and_grant(text)
        except Exception:
            pass

        loop = asyncio.get_event_loop()

        # Resolve shared references — pipeline + action engine live on
        # the legacy TelegramVoice instance (it constructs them lazily
        # in `_get_pipeline`). In v2 mode legacy still holds these for
        # shared card rendering during the parallel-run period.
        action_engine = getattr(self.daemon, "actions", None)
        legacy_tg = getattr(self.daemon, "telegram", None)
        get_pipeline = getattr(legacy_tg, "_get_pipeline", None) if legacy_tg is not None else None

        chat_id = ""
        user_id = "rohit"
        try:
            src = event.source
            if src and src.chat_id:
                chat_id = str(src.chat_id)
            if src and src.user_id:
                user_id = str(src.user_id)
        except Exception:
            pass
        reply_to_msg_id = getattr(event, "reply_to_message_id", None)
        pipe = None
        if get_pipeline is not None:
            try:
                pipe = get_pipeline()
            except Exception:
                pipe = None
        has_local_photo_context = bool(
            event.message_type == MessageType.PHOTO
            and event.channel_prompt
            and "Local Maez vision analysis" in str(event.channel_prompt)
        )

        # Surface Parity Restoration v0: D20 capability-gap detection.
        # Placement law: after auth, before every early-return interceptor.
        # The helper creates cards through pending_card_store; this path
        # never sends card messages manually.
        if surface_parity_enabled():
            try:
                from core.infra.capability_gap_detector import maybe_fire_capability_proposal

                def _fire_gap_detector() -> None:
                    try:
                        maybe_fire_capability_proposal(
                            text,
                            pending_card_store=getattr(pipe, "card_store", None) if pipe else None,
                            chat_id=chat_id,
                            user_id=user_id,
                        )
                    except Exception:
                        logger.debug("d20 gap detection skipped", exc_info=True)

                loop.run_in_executor(get_shared_executor(), _fire_gap_detector)
            except Exception:
                logger.debug("d20 gap detection enqueue failed", exc_info=True)

        if strict_env_flag("MAEZ_INTAKE_FACULTY_SHADOW"):
            try:
                from core.cognition.intake_shadow import observe_owner_turn

                observe_owner_turn(
                    text,
                    surface=SURFACE_NAME,
                    chat_id=chat_id,
                    controller=self._search_commitment_controller(),
                    memory=getattr(self.daemon, "memory", None),
                )
            except Exception:
                logger.debug("intake faculty shadow enqueue failed", exc_info=True)

        # Card-reply intent check — if there's an open approval card
        # and this message looks like a yes/no/defer, route through
        # the pipeline's reply handler. The renderer inside the
        # pipeline sends the resolution notice directly, so we return
        # any mid-dialog continuation text (or None if fully handled).
        if pipe is not None:
            try:
                open_cards = pipe.card_store.get_open_for_channel(
                    "telegram_text",
                    chat_id=chat_id,
                )
            except Exception:
                open_cards = []
            if open_cards:
                try:
                    result = await loop.run_in_executor(
                        get_shared_executor(),
                        lambda: pipe.handle_reply(
                            text=text,
                            user_id="rohit",
                            chat_id=chat_id,
                            reply_to_message_id=reply_to_msg_id,
                            channel="telegram_text",
                        ),
                    )
                except Exception as e:
                    logger.warning(
                        "pipe.handle_reply failed on %s: %s",
                        SURFACE_NAME,
                        e,
                    )
                    result = None
                if result is not None:
                    # Pipeline handled it — resolution was sent by
                    # its CardRenderer. Return any mid-dialog
                    # continuation text so the adapter sends it
                    # as the reply to this message.
                    dialog_reply = getattr(
                        result,
                        "dialog_reply_text",
                        None,
                    )
                    if dialog_reply:
                        # Strip tool-call JSON leaks (e.g. the
                        # {"action": "log", ...} block observed
                        # in a 2026-04-20 dialog reply).
                        try:
                            from core.brain_loop import (
                                strip_tool_call_leaks,
                            )

                            dialog_reply = strip_tool_call_leaks(
                                dialog_reply,
                            )
                        except Exception:
                            pass
                        try:
                            from core.self_claim_audit import (
                                audit as _sc_audit,
                            )

                            r = _sc_audit(
                                dialog_reply,
                                surface=f"{SURFACE_NAME}_dialog",
                            )
                            return r.text if r.rewritten else dialog_reply
                        except Exception:
                            return dialog_reply
                    return None

        proposal_reply = await self._try_surface_parity_proposal_intent(
            text=text,
            chat_id=chat_id,
            pipe=pipe,
            user_id=user_id,
        )
        if proposal_reply:
            return proposal_reply

        search_commitment_reply = await self._try_search_commitment_intent(
            text=text,
            chat_id=chat_id,
        )
        if search_commitment_reply:
            return search_commitment_reply

        # Self-mod dialog bridge — brain_loop needs a callable that
        # surfaces the Lane-3 dialog opening as a Telegram message
        # BEFORE the final synthesis reply. The brain loop runs in an
        # executor (sync), so we bridge to the adapter's async send
        # via run_coroutine_threadsafe on this handler's loop.
        adapter = getattr(self.daemon, "_surface_v2_adapter", None)
        adapter_loop = getattr(self.daemon, "_surface_v2_loop", None)

        def _send_intermediate(msg_text: str) -> None:
            if not adapter or not adapter_loop or not chat_id:
                return
            try:
                from core.egress.provenance import ProvenancedText

                payload = ProvenancedText.maez_authored_owner_third_party_transport(
                    msg_text,
                    source_ref=f"{SURFACE_NAME}:self_mod_dialog_intermediate",
                )
                coro = adapter.send(chat_id, payload)
                fut = asyncio.run_coroutine_threadsafe(coro, adapter_loop)
                fut.result(timeout=20)
            except Exception as e:
                logger.warning(
                    "send_intermediate failed on %s: %s",
                    SURFACE_NAME,
                    e,
                )

        def _send_progress_receipt(
            msg_text: str,
            *,
            on_complete=None,
            should_send=None,
        ) -> None:
            def _complete(result: str) -> None:
                if on_complete is None:
                    return
                try:
                    on_complete(result, time.monotonic())
                except Exception:
                    logger.debug("recall progress receipt completion callback failed")

            if not adapter or not loop or not chat_id:
                _complete("failed")
                return

            async def _send() -> None:
                try:
                    if should_send is not None and not should_send():
                        _complete("failed")
                        return
                    from core.egress.provenance import ProvenancedText
                    from core.routing.recall_receipt import RECEIPT_SEND_TIMEOUT_MS

                    payload = ProvenancedText.maez_authored_owner_third_party_transport(
                        msg_text,
                        source_ref=f"{SURFACE_NAME}:recall_progress_receipt",
                    )
                    result = await asyncio.wait_for(
                        adapter.send(chat_id, payload),
                        timeout=RECEIPT_SEND_TIMEOUT_MS / 1000.0,
                    )
                    _complete("ok" if getattr(result, "success", False) else "failed")
                except asyncio.TimeoutError:
                    _complete("timeout")
                except Exception as e:
                    logger.debug(
                        "recall progress receipt send failed on %s: %s",
                        SURFACE_NAME,
                        type(e).__name__,
                    )
                    _complete("failed")

            try:
                asyncio.run_coroutine_threadsafe(_send(), loop)
            except Exception as e:
                logger.debug(
                    "recall progress receipt scheduling failed on %s: %s",
                    SURFACE_NAME,
                    type(e).__name__,
                )
                _complete("failed")

        # Fetch the last few telegram exchanges so the brain-loop's
        # tool-planner has conversational context. Without this, the
        # planner sees only the current user message and drifts on
        # follow-up questions ("what did you find?", "try that again").
        # get_telegram_exchanges already exists and is used by
        # continuity + dream_state; this just extends its reach to the
        # tool-planning path. None-safe — fall open if memory is
        # unreachable.
        chat_history = None
        held_now_history = None
        try:
            _mem = getattr(self.daemon, "memory", None)
            if _mem is not None:
                _raw_exchanges = await loop.run_in_executor(
                    get_shared_executor(),
                    lambda: _mem.get_telegram_exchanges(
                        limit=_CHAT_HISTORY_TURNS,
                    ),
                )
                # Held-now C5: the coalesced, scope-filtered list is a
                # SEPARATE carrier consumed only by working-set anchor
                # construction — the raw list above keeps feeding the
                # planner/legacy/comprehension consumers unchanged.
                try:
                    from core.routing.focused_cognition import (
                        held_now_enabled as _hn_on,
                        held_now_shadow_enabled as _hn_shadow,
                    )

                    if _hn_on() or _hn_shadow():
                        _coalesced = await loop.run_in_executor(
                            get_shared_executor(),
                            lambda: _mem.get_telegram_exchanges_coalesced(
                                limit=_CHAT_HISTORY_TURNS,
                                origin_surface=SURFACE_NAME,
                                chat_id=chat_id or None,
                            ),
                        )
                        held_now_history = [
                            {
                                "content": _clean_exchange(
                                    _row.get("content") or ""
                                ),
                                "metadata": dict(_row.get("metadata") or {}),
                            }
                            for _row in _coalesced or []
                        ]
                except Exception as _hn_exc:
                    logger.warning("held_now history fetch failed: %s", _hn_exc)
                    held_now_history = None
                # 2026-04-23: clean the stored envelope into a tight
                # "Rohit: ... / Maez: ..." pair before it reaches
                # run_brain_loop. Without this, `chat_history` injects
                # hundreds of lines of old FORBIDDEN / TURN STATE /
                # AMBIGUOUS REFERENT rule text into the current prompt
                # and the planner loses the actual conversational
                # signal. Observed symptom: the owner says "What
                # happened?" after an npm install failure and Maez
                # replies "I don't know what you're referring to."
                # The cleaner preserves other keys (metadata, id) so
                # downstream contracts stay intact; only `content` is
                # rewritten, and only when the envelope prefix matches.
                chat_history = []
                for _ex in _raw_exchanges or []:
                    if not _ex:
                        continue
                    _new = dict(_ex)
                    _cleaned = _clean_exchange(_new.get("content", ""))
                    if not _cleaned:
                        continue
                    _new["content"] = _cleaned
                    chat_history.append(_new)
        except Exception as e:
            logger.debug("chat_history fetch failed on %s: %s", SURFACE_NAME, e)
            chat_history = None

        # Observability: wrap the whole turn in a Langfuse trace so
        # every LLM call + tool dispatch lands in the UI. No-op when
        # LANGFUSE_PUBLIC_KEY isn't set (default). See
        # core.observability for the abstraction.
        from core.observability import observe_turn

        with observe_turn(
            "telegram_turn",
            input={"text": text, "chat_id": chat_id},
            metadata={"user_id": "rohit", "surface": SURFACE_NAME},
        ) as turn:
            # Brain-loop stage — runs the tool iteration synchronously
            # with the pipeline for card-or-inline decisions.
            jarvis_transcript = ""
            jarvis_tool_calls: list[dict] = []
            jarvis_recall_items = ()
            brain_failed = False
            try:
                from core import brain_loop as _brain_loop

                if (
                    action_engine is not None
                    and get_pipeline is not None
                    and not has_local_photo_context
                ):
                    # Slice 3 of trace work: ask for the structured
                    # result so we can pass tool_calls into
                    # handle_message and the per-turn trace records the
                    # actual tool trajectory, not just the synthesis
                    # text. Falls back to a string + empty tool_calls
                    # if a future change reverts the structured API.
                    with with_purpose(BrainPurpose.OWNER_REPLY):
                        _result = await loop.run_in_executor(
                            get_shared_executor(),
                            copy_current_context_callable(
                                lambda: _brain_loop.run_brain_loop(
                                    text,
                                    action_engine=action_engine,
                                    get_pipeline=get_pipeline,
                                    user_id="rohit",
                                    chat_id=chat_id,
                                    surface=SURFACE_NAME,
                                    send_intermediate=_send_intermediate,
                                    chat_history=chat_history,
                                    turn=turn,
                                    return_structured=True,
                                )
                            ),
                        )
                    if hasattr(_result, "transcript"):
                        jarvis_transcript = _result.transcript or ""
                        jarvis_tool_calls = list(getattr(_result, "tool_calls", []) or [])
                        jarvis_recall_items = tuple(getattr(_result, "recall_items", ()) or ())
                    else:  # legacy str fallback
                        jarvis_transcript = _result or ""
            except Exception as e:
                logger.warning("brain_loop failed on %s: %s", SURFACE_NAME, e)
                jarvis_transcript = ""
                jarvis_tool_calls = []
                jarvis_recall_items = ()
                # Codex review of b35bc94: the v2 inbound path forwards the
                # downgrade; this flag-off rollback path swallowed it.
                brain_failed = True

            # Synthesis stage — daemon.handle_message does the final text reply
            # and OWNS the pipeline: strip tool-call leaks, self-claim audit,
            # store_telegram, trace. For photo turns it synthesizes over a
            # BOUNDED working set internally (direction b) when photo_analysis
            # (successful local vision) is present — so the photo reply still
            # flows through that same pipeline instead of bypassing it.
            # 2026-04-23 memory-integrity contract (Commit 1): the audit is
            # owned by handle_message; the adapter does NOT double-audit.
            subjective_duration_owner_auth = None
            if surface_parity_enabled():
                try:
                    from core.evolution.subjective_duration import SubjectiveDurationOwnerAuth

                    subjective_duration_owner_auth = SubjectiveDurationOwnerAuth(
                        surface="telegram_owner",
                        proof="telegram_authorized_user",
                    )
                except Exception:
                    logger.debug(
                        "subjective duration auth construction failed",
                        exc_info=True,
                    )
            try:
                with with_purpose(BrainPurpose.OWNER_REPLY):
                    reply = await loop.run_in_executor(
                        get_shared_executor(),
                        copy_current_context_callable(
                            lambda: self.daemon.handle_message(
                                text,
                                SURFACE_NAME,
                                transcript=jarvis_transcript or "",
                                context_note=event.channel_prompt,
                                photo_analysis=getattr(
                                    event, "photo_analysis_text", None
                                ),
                                chat_history=chat_history,
                                chat_id=chat_id,
                                tool_calls=jarvis_tool_calls or None,
                                recall_items=jarvis_recall_items,
                                subjective_duration_owner_auth=subjective_duration_owner_auth,
                                send_intermediate=_send_progress_receipt,
                                brain_failed=brain_failed,
                                held_now_history=held_now_history,
                            )
                        ),
                    )
            except Exception as e:
                logger.warning("daemon dispatch failed on %s: %s", SURFACE_NAME, e)
                turn.update(output=f"(internal error: {e})")
                return f"(internal error: {e})"

            if not isinstance(reply, str) or not reply.strip():
                from skills.web_search import strip_quality_lines

                fallback = strip_quality_lines(jarvis_transcript or "")
                turn.update(output=fallback or "(empty)")
                return fallback or None

            # 2026-04-23 Commit 7b: strip_tool_call_leaks was moved INTO
            # daemon.handle_message (before audit, before store) so the
            # stored / audited / displayed text are all the same string.
            # Adapter no longer re-strips — the reply returned here is
            # already clean wire-format.

            # Record the final reply into the trace before the with
            # block exits and flushes. This is what the Langfuse UI
            # shows as the turn's "output".
            try:
                turn.update(output=reply)
            except Exception:
                pass

        return reply


def build_telegram_adapter(
    token: str,
    authorized_users: list[int],
    daemon: Any,
    *,
    reply_to_mode: str = "first",
    extra: Optional[dict] = None,
) -> TelegramAdapter:
    """Instantiate the vendored TelegramAdapter wired to Maez's brain.

    The caller is responsible for scheduling `adapter.connect()` on
    an event loop. Typical bootstrap:

        adapter = build_telegram_adapter(token, [user_id], daemon)
        asyncio.create_task(adapter.connect())

    Or in a thread with its own loop (matches the current legacy
    pattern in `skills/telegram_voice.py`):

        loop = asyncio.new_event_loop()
        loop.run_until_complete(adapter.connect())
    """
    merged_extra: dict = {"allowed_users": list(authorized_users)}
    if extra:
        merged_extra.update(extra)

    cfg = PlatformConfig(
        enabled=True,
        token=token,
        reply_to_mode=reply_to_mode,
        extra=merged_extra,
    )
    adapter = TelegramAdapter(cfg)
    adapter._maez_daemon = daemon
    handler = MaezMessageHandler(daemon)
    adapter.set_message_handler(handler)
    return adapter
