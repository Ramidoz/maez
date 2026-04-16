r"""
Maez Decision Pipeline — Session 11z Part 2, Step 11.

The decision pipeline is the conductor. Every proposed action (from
the Jarvis chat loop, from the daemon's proactive path, or from any
future surface) flows through this one function, which:

    1. Runs the deterministic covenant gate
    2. Classifies the action (command_decomposer + action_classifier)
    3. Scans for prompt-injection patterns
    4. Runs the two-pass audit LLM
    5. Routes based on the verdict:
         - APPROVE            → execute immediately (Lane 0)
         - APPROVE_WITH_CARD  → create a pending card, return placeholder
         - ESCALATE           → create a Lane 3 card (self-mod dialog)
         - DENY               → refuse with the judge's reasoning
    6. Writes the audit row
    7. Records the pending card row (if any)

And on the reply side, handle_reply():

    1. Fetches the open cards for this user/chat
    2. Classifies the reply (heuristic-first, LLM fallback)
    3. Acts on the intent:
         - APPROVE  → approve card, execute action, render resolution
         - DENY     → deny card, render resolution
         - DEFER    → defer card with remind_at, render ack
         - RE_EXPLAIN → render card's details again
         - MODIFY   → re-run pipeline with a modified shape
         - UNRELATED → return None so the Jarvis loop handles normally

This file is the single place action routing lives. Every caller
goes through handle_action() / handle_reply() — no more direct
`action_engine._execute_action()` calls from chat surfaces.

Async model:
    handle_action() is synchronous by default (Lane 0 runs the action
    inline). For Lane 2/3 it returns a PipelineResult with
    status='pending_approval' immediately — the Jarvis loop uses that
    to tell the owner "card sent, I'll act when you say yes." Actual
    execution fires from handle_reply() when approval lands.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

from core.action_classifier import classify_action, ClassificationResult, IntentCategory
from core.audit import audit_action, AuditVerdict, Decision
from core.audit_log import AuditLog
from core.injection_patterns import scan as scan_injection, InjectionMatch, highest_severity
from core.pending_cards import (
    CardRecord,
    CardStoreError,
    PendingCardStore,
    CardStatus,
    compute_state_hash,
)


# ------------------------------------------------------------------ #
#  Result types                                                        #
# ------------------------------------------------------------------ #

class PipelineStatus(str, Enum):
    EXECUTED            = "executed"             # Lane 0 ran inline
    PENDING_APPROVAL    = "pending_approval"     # Lane 2 card created
    PENDING_DIALOG      = "pending_dialog"       # Lane 3 self-mod dialog entry
    REFUSED_COVENANT    = "refused_covenant"     # covenant gate refused
    REFUSED_AUDIT       = "refused_audit"        # audit judge said DENY
    REFUSED_WILL        = "refused_will"         # A-core #8: will-I volitional refusal
    REFUSED_INVALID     = "refused_invalid"      # malformed params, rejected before audit
    ERROR               = "error"                # pipeline itself failed


@dataclass
class PipelineResult:
    status: PipelineStatus
    message: str
    card: Optional[CardRecord] = None
    verdict: Optional[AuditVerdict] = None
    classification: Optional[ClassificationResult] = None
    injection_matches: list[InjectionMatch] = field(default_factory=list)
    audit_request_id: Optional[str] = None
    execution_success: Optional[bool] = None
    execution_output: Optional[str] = None
    execution_error: Optional[str] = None
    # A-core #4b: self-modification dialog fields.
    #
    # dialog_opening is set by handle_action's Lane 3 branch when a
    # PENDING_DIALOG card is created alongside its self-mod dialog.
    # Carries the dialog's opening turn text (Rule 1 mechanical
    # restatement + Rule 2 why-probe) so the caller surface (Jarvis
    # loop in telegram_voice) can surface it to the owner in a way the
    # user actually sees, not just via the card's card-header
    # rendering.
    #
    # dialog_reply_text is set by handle_reply when a reply to an
    # open PENDING_DIALOG card is routed through handle_dialog_reply
    # and the dialog produces a non-terminal clarification response.
    # Carries Maez's next turn so the caller surface can send it back
    # to the owner as a Telegram message.
    dialog_opening: Optional[str] = None
    dialog_reply_text: Optional[str] = None


# ------------------------------------------------------------------ #
#  Param-shape guard                                                    #
# ------------------------------------------------------------------ #

_REQUIRED_PARAMS: dict[str, tuple[str, ...]] = {
    "run_shell": ("cmd",),
    "write_any_file": ("path", "content"),
    "write_file": ("path", "content"),
    "append_to_file": ("path", "content"),
    "read_file": ("path",),
    "search_files": ("query",),
    "web_search": ("query",),
    "query_system": ("cmd",),
}


def _missing_required_params(action: str, params: dict) -> list[str]:
    """Return a list of required param names that are missing or empty.

    The Jarvis loop has been observed emitting `run_shell({})` calls
    when the LoRA fumbles a tool directive. Before this guard those
    empty calls hit the audit LLM, whose Pass 1 summarizer
    hallucinated a "prompt-injection attempt" verdict on the empty
    data (~2s latency per false DENY). This function is the cheap
    short-circuit.
    """
    required = _REQUIRED_PARAMS.get(action)
    if not required:
        return []
    missing = []
    for name in required:
        value = params.get(name)
        if value is None:
            missing.append(name)
            continue
        if isinstance(value, str) and not value.strip():
            missing.append(name)
    return missing


# ------------------------------------------------------------------ #
#  State fingerprint helpers                                           #
# ------------------------------------------------------------------ #

def _fingerprint_for_action(action: str, params: dict) -> dict:
    """Produce a state-fingerprint dict for the precondition hash.
    Tolerant: missing files are fine, unreachable tools are fine.

    This dict is hashed and stored on the card. At approval time the
    same function is called again; if the hash differs, the card
    expires.
    """
    fields: dict = {
        "cwd": os.getcwd(),
        "ts_bucket_min": int(time.time() // 60),  # changes every minute by design
    }

    params = params or {}
    if action == "run_shell":
        cmd = str(params.get("cmd", ""))
        # Extract any referenced file paths from the command (cheap
        # heuristic: tokens starting with / or ./)
        tokens = [t for t in cmd.split() if t.startswith(("/", "./"))]
        file_states = {}
        for t in tokens[:10]:
            try:
                p = Path(t).resolve()
                if p.exists():
                    st = p.stat()
                    file_states[str(p)] = {"mtime": int(st.st_mtime), "size": st.st_size}
                else:
                    file_states[str(p)] = None
            except Exception:
                file_states[t] = "err"
        fields["files"] = file_states

    elif action in ("write_any_file", "write_file", "append_to_file", "write_outside_maez"):
        path = params.get("path")
        if path:
            try:
                p = Path(path).resolve()
                if p.exists():
                    st = p.stat()
                    fields["target"] = {"path": str(p), "mtime": int(st.st_mtime), "size": st.st_size, "exists": True}
                else:
                    fields["target"] = {"path": str(p), "exists": False}
            except Exception:
                fields["target"] = {"path": str(path), "err": True}

    # Coarse disk-free bucket (in 10% steps) so minor fluctuations don't invalidate
    try:
        import shutil
        usage = shutil.disk_usage("/")
        free_pct = int((usage.free / usage.total) * 100)
        fields["disk_free_bucket"] = free_pct // 10
    except Exception:
        pass

    return fields


def _drop_volatile(state: dict) -> dict:
    """Remove fields that are expected to change between creation and
    approval (e.g. the minute bucket). The state hash we actually use
    for stale-detection is computed over THIS reduced dict."""
    s = dict(state or {})
    s.pop("ts_bucket_min", None)
    return s


# ------------------------------------------------------------------ #
#  Pipeline                                                            #
# ------------------------------------------------------------------ #

@dataclass
class DecisionPipeline:
    """Top-level pipeline object. Hold references to the pieces it
    needs — action engine, stores, renderer — and let callers invoke
    handle_action / handle_reply."""

    action_engine: Any
    card_store: PendingCardStore
    audit_log: AuditLog
    renderer: Any = None                 # CardRenderer protocol; optional for tests
    get_cards_for: Optional[Callable[[str, str], list[CardRecord]]] = None

    # Which actions are eligible for Lane 0 immediate-run (read-only).
    # The classifier is authoritative — this is just a safety check.
    _LANE_0_ACTIONS = frozenset({
        "read_file", "search_files", "query_system", "web_search",
        "run_readonly_command",
    })

    def __post_init__(self):
        if self.get_cards_for is None:
            self.get_cards_for = self._default_get_cards

    def _default_get_cards(self, user_id: str, chat_id: Optional[str]) -> list[CardRecord]:
        if chat_id:
            return self.card_store.get_open_for_channel("telegram_text", chat_id=chat_id)
        return self.card_store.get_open_for_user(user_id)

    # -------------------------------------------------------------- #
    #  handle_action                                                  #
    # -------------------------------------------------------------- #

    def handle_action(
        self,
        *,
        action: str,
        params: dict,
        reason: str,
        user_id: str = "rohit",
        chat_id: Optional[str] = None,
        channel: str = "telegram_text",
    ) -> PipelineResult:
        params = params or {}

        # ---- Step 0: required-param guard ----
        # Short-circuit malformed tool calls BEFORE the audit LLM sees
        # them. Pass 1 summarizer has been observed to hallucinate
        # "prompt-injection attempt" verdicts on empty params, burning
        # ~2s per false DENY. Reject at the gate with a cheap check.
        missing = _missing_required_params(action, params)
        if missing:
            return PipelineResult(
                status=PipelineStatus.REFUSED_INVALID,
                message=f"Malformed {action} call: missing {', '.join(missing)}",
                classification=None,
                injection_matches=[],
            )

        # ---- Step 1: classification ----
        classification = classify_action(action, params)

        # ---- Step 2: injection scan ----
        injection_text = self._build_injection_scan_text(action, params, reason)
        injection_matches = scan_injection(injection_text)

        # ---- Step 3: audit (two-pass LLM) ----
        verdict = audit_action(
            action=action,
            params=params,
            classification=classification,
            injection_matches=injection_matches,
        )

        # ---- Step 4: record to audit log ----
        audit_req_id = self.audit_log.record(
            action=action,
            params=params,
            classification=classification,
            injection_matches=injection_matches,
            verdict=verdict,
        )

        # Pipeline-level injection override: even if the verdict from
        # the audit layer says APPROVE*, any injection match on the
        # raw input forces ESCALATE. This belt-and-braces duplicates
        # the override inside core/audit.py so the floor holds even
        # when a fake audit is injected (for tests) or a future audit
        # implementation forgets the rule.
        if injection_matches and verdict.decision in (Decision.APPROVE, Decision.APPROVE_WITH_CARD):
            top = highest_severity(injection_matches)
            forced_reason = (
                f"injection override: {top.bucket if top else 'pattern'} matched raw input; "
                f"floor = ESCALATE regardless of audit verdict"
            )
            verdict = AuditVerdict(
                decision=Decision.ESCALATE,
                confidence=verdict.confidence,
                reasoning=(verdict.reasoning or "") + " | " + forced_reason,
                concerns=[forced_reason] + list(verdict.concerns or []),
                mitigations=list(verdict.mitigations or []),
                summary=verdict.summary,
                answers=verdict.answers,
                nonce=verdict.nonce,
                latency_ms=verdict.latency_ms,
                judge_raw=verdict.judge_raw,
                parse_error=verdict.parse_error,
            )

        # Pipeline-level Lane 0 downgrade: the judge's "when in doubt,
        # prefer APPROVE_WITH_CARD over APPROVE" tiebreaker has been
        # observed upgrading classifier-Lane-0 reads (e.g.
        # `ls /usr/bin | grep -E 'foo|bar' || echo 'none'`) to
        # APPROVE_WITH_CARD simply because the command looks compound.
        # If the deterministic classifier says Lane 0 AND there are no
        # injection matches, the command is a safe read and should
        # execute inline — don't let the judge's conservative bias
        # spawn a card for a pure read. The classifier is authoritative
        # for lane, not the judge. The judge can still DENY or ESCALATE
        # if it sees something else wrong.
        if (
            classification is not None
            and classification.lane == 0
            and not injection_matches
            and verdict.decision == Decision.APPROVE_WITH_CARD
        ):
            verdict = AuditVerdict(
                decision=Decision.APPROVE,
                confidence=verdict.confidence,
                reasoning=(verdict.reasoning or "") + " | lane-0 downgrade: classifier confirmed read-only, no injection flags",
                concerns=list(verdict.concerns or []),
                mitigations=list(verdict.mitigations or []),
                summary=verdict.summary,
                answers=verdict.answers,
                nonce=verdict.nonce,
                latency_ms=verdict.latency_ms,
                judge_raw=verdict.judge_raw,
                parse_error=verdict.parse_error,
            )

        # ---- Step 5: route on verdict ----
        if verdict.decision == Decision.DENY:
            return PipelineResult(
                status=PipelineStatus.REFUSED_AUDIT,
                message=f"Audit layer refused: {verdict.reasoning}",
                verdict=verdict,
                classification=classification,
                injection_matches=injection_matches,
                audit_request_id=audit_req_id,
            )

        # Lane 0 inline: trust the classifier's lane assignment, not a
        # hard-coded action-name frozenset. Before this fix, `run_shell`
        # with a safe read command (e.g. `dpkg -l openrgb`) got
        # classified Lane 0 and APPROVED but was routed to card creation
        # because `run_shell` wasn't in _LANE_0_ACTIONS. The classifier
        # is authoritative; the frozenset is a defense-in-depth guard
        # for legacy verbs that bypass classify_command.
        is_lane_0 = (
            classification is not None and classification.lane == 0
        ) or action in self._LANE_0_ACTIONS
        if verdict.decision == Decision.APPROVE and is_lane_0:
            # A-core #8: will-I check before Lane 0 inline execution.
            will_refuse = self._will_i_check(
                action, params,
                post_approval=False,
                audit_req_id=audit_req_id,
            )
            if will_refuse is not None:
                return will_refuse
            # Lane 0: execute inline, no card
            return self._execute_inline(
                action=action,
                params=params,
                reason=reason,
                verdict=verdict,
                classification=classification,
                injection_matches=injection_matches,
                audit_req_id=audit_req_id,
            )

        # Lane 2 or Lane 3: create a card
        state_fields = _fingerprint_for_action(action, params)
        card = self.card_store.create_card(
            action=action,
            params=params,
            reason=reason,
            audit_verdict=verdict,
            audit_request_id=audit_req_id,
            classification=classification,
            state_fields=_drop_volatile(state_fields),
            channel=channel,
            chat_id=chat_id,
            user_id=user_id,
        )

        # Render the card if a renderer is attached
        channel_message_id = None
        if self.renderer is not None:
            channel_message_id = self.renderer.present(card)
            if channel_message_id:
                self.card_store.attach_channel_message(card.request_id, str(channel_message_id))
                card = self.card_store.get(card.request_id) or card

        status = (
            PipelineStatus.PENDING_DIALOG
            if verdict.decision == Decision.ESCALATE
            else PipelineStatus.PENDING_APPROVAL
        )
        msg = (
            "Self-modification / heavy-scrutiny card created. Waiting for your ratification."
            if status == PipelineStatus.PENDING_DIALOG
            else "Approval card created. I'll run this when you say yes."
        )

        # A-core #4b: for Lane 3 ESCALATE, ALSO open a self-mod
        # dialog. The card tracks the proposal; the dialog tracks the
        # conversation. Linked via card_request_id. Telegram replies
        # to the dialog flow through handle_reply's PENDING_DIALOG
        # branch, which routes them to skills.self_mod_dialog.
        # handle_dialog_reply.
        dialog_opening_text: Optional[str] = None
        if verdict.decision == Decision.ESCALATE:
            try:
                from skills.self_mod_dialog import (
                    SelfModDialogStore,
                    open_dialog_for_card,
                )
                dialog_store = self._get_dialog_store()
                _dialog, dialog_opening_text = open_dialog_for_card(
                    store=dialog_store,
                    card_action=action,
                    card_params=params,
                    card_request_id=card.request_id,
                    audit_reasoning=verdict.reasoning or "",
                    concerns=list(verdict.concerns or []),
                )
            except Exception as e:
                # Fail soft: if dialog creation errors, the card is
                # still created and the owner can still see the proposal.
                # The dialog just won't exist and replies will fall
                # through to the normal card-reply classifier. Log so
                # the failure is visible.
                import logging
                logging.getLogger(__name__).warning(
                    "A-core #4b: failed to open self-mod dialog for card %s: %s",
                    card.request_id, e,
                )

        return PipelineResult(
            status=status,
            message=msg,
            card=card,
            verdict=verdict,
            classification=classification,
            injection_matches=injection_matches,
            audit_request_id=audit_req_id,
            dialog_opening=dialog_opening_text,
        )

    def _get_dialog_store(self):
        """Lazy-instantiate the self-mod dialog store. Cached on the
        pipeline instance so we don't reopen it on every Lane 3
        proposal. The store is separate from the card store because
        dialog state has its own lifecycle (multi-turn history,
        linkage to prior dialogs, terminal-state semantics) that
        don't fit the card schema.
        """
        existing = getattr(self, "_dialog_store", None)
        if existing is not None:
            return existing
        from skills.self_mod_dialog import SelfModDialogStore
        store = SelfModDialogStore()
        self._dialog_store = store
        return store

    def _will_i_check(
        self,
        action: str,
        params: dict,
        *,
        post_approval: bool = False,
        audit_req_id: str = None,
        card: CardRecord = None,
    ) -> Optional[PipelineResult]:
        """Shared will-I check for both Lane 0 inline and card-approved
        paths. Returns a REFUSED_WILL PipelineResult if the check fires,
        or None if the action should proceed.

        post_approval controls the user-facing message:
          False -> "I decided not to do that."
          True  -> "You approved this, but I've decided not to proceed."
        """
        try:
            from core.will_i import check as will_i_check_fn
            verdict = will_i_check_fn(action=action, params=params)
        except Exception as e:
            logger.debug(
                "will-I check failed (action=%s): %s — proceeding",
                action, e,
            )
            return None

        if verdict.proceed:
            return None

        # Log to audit_log.db via existing record_outcome.
        if audit_req_id:
            try:
                ground = verdict.ground or "UNKNOWN"
                reason = verdict.reason or ""
                self.audit_log.record_outcome(
                    audit_req_id,
                    outcome="refused_by_will",
                    notes=f"ground={ground}: {reason}"[:400],
                )
            except Exception:
                pass

        # If post-approval, also close the card as denied.
        if post_approval and card is not None:
            try:
                self.card_store.deny(
                    card.request_id,
                    user_id="maez_will_i",
                    via="will_i_refusal",
                    notes=f"{verdict.ground}: {verdict.reason or ''}"[:400],
                )
                if self.renderer:
                    self.renderer.send_resolution(card)
            except Exception:
                pass

        if post_approval:
            msg = (
                f"You approved this, but I've decided not to proceed. "
                f"(Reason: {verdict.reason or verdict.ground})"
            )
        else:
            msg = (
                f"I decided not to do that. "
                f"(Reason: {verdict.reason or verdict.ground})"
            )

        return PipelineResult(
            status=PipelineStatus.REFUSED_WILL,
            message=msg,
            card=card,
        )

    def _build_injection_scan_text(self, action: str, params: dict, reason: str) -> str:
        """Build the text the injection scanner sees. Includes all
        string-ish params + the reason."""
        parts = [action, reason or ""]
        for k, v in (params or {}).items():
            parts.append(f"{k}: {v}")
        return "\n".join(str(p) for p in parts)

    def _execute_inline(
        self,
        *,
        action: str,
        params: dict,
        reason: str,
        verdict: AuditVerdict,
        classification: ClassificationResult,
        injection_matches: list[InjectionMatch],
        audit_req_id: str,
    ) -> PipelineResult:
        """Run a Lane 0 action inline through the ActionEngine."""
        try:
            result = self.action_engine._execute_action(
                action, params, f"pipeline: {reason[:140]}", tier=0
            )
            ok = bool(getattr(result, "success", False))
            out = str(getattr(result, "output", "") or "")
            err = str(getattr(result, "error", "") or "")
        except Exception as e:
            ok = False
            out = ""
            err = f"execution exception: {e!r}"

        self.audit_log.record_outcome(
            audit_req_id,
            outcome="approved_and_ran" if ok else "approved_and_failed",
            notes=(out if ok else err)[:400],
        )
        return PipelineResult(
            status=PipelineStatus.EXECUTED,
            message=(out[:500] if ok else err[:500]),
            verdict=verdict,
            classification=classification,
            injection_matches=injection_matches,
            audit_request_id=audit_req_id,
            execution_success=ok,
            execution_output=out,
            execution_error=err if not ok else None,
        )

    # -------------------------------------------------------------- #
    #  handle_reply                                                   #
    # -------------------------------------------------------------- #

    def handle_reply(
        self,
        *,
        text: Optional[str] = None,
        reaction_emoji: Optional[str] = None,
        user_id: str = "rohit",
        chat_id: Optional[str] = None,
        reply_to_message_id: Optional[str] = None,
        channel: str = "telegram_text",
    ) -> Optional[PipelineResult]:
        """Handle an incoming reply/reaction. Returns None if the reply
        is unrelated to any open card (the caller handles it as normal
        conversation)."""
        from skills.card_reply_classifier import classify_reply, ReplyIntent

        open_cards = self.get_cards_for(user_id, chat_id) if self.get_cards_for else []
        if not open_cards:
            return None

        # A-core #4b: if any open card is in PENDING_DIALOG state
        # (Lane 3 self-mod), route the reply through the self-mod
        # dialog handler BEFORE the normal card-reply classifier.
        # Self-mod dialogs are free-text conversations, not yes/no
        # card approvals — a "yes, but..." reply must flow to the
        # dialog engine's whole-reply terminal matcher, not to the
        # card reply classifier's APPROVE match.
        #
        # We pick the most recent PENDING_DIALOG card. If multiple
        # are open (rare), newest wins.
        if text:
            # Filter to PENDING_DIALOG cards only. A PENDING_DIALOG
            # card is one whose audit verdict was ESCALATE (Lane 3)
            # — at creation time the audit_decision was stored on
            # the card as "ESCALATE" and lane as "3". Check both
            # to survive any future drift in one field or the other.
            pending_dialog_cards = [
                c for c in open_cards
                if (getattr(c, "audit_decision", None) == "ESCALATE")
                or (str(getattr(c, "lane", "")) == "3")
            ]
            if pending_dialog_cards:
                pending_dialog_cards.sort(
                    key=lambda c: getattr(c, "created_at", 0.0), reverse=True
                )
                dialog_card = pending_dialog_cards[0]
                dialog_result = self._handle_dialog_reply_for_card(
                    card=dialog_card,
                    text=text,
                    user_id=user_id,
                )
                if dialog_result is not None:
                    return dialog_result
                # If the dialog reply was 'unrelated' (dialog is
                # already terminal or has no linked dialog), fall
                # through to the normal card reply classifier.

        # If the reply is threaded to a specific card message, use that
        explicit_target = None
        if reply_to_message_id:
            hit = self.card_store.get_by_message(channel, reply_to_message_id)
            if hit and hit.status in {CardStatus.OPEN.value, CardStatus.DEFERRED.value}:
                explicit_target = hit.request_id

        classification = classify_reply(
            text=text,
            reaction_emoji=reaction_emoji,
            open_cards=open_cards,
            explicit_target_request_id=explicit_target,
            use_llm_fallback=True,
        )

        if classification.intent == ReplyIntent.UNRELATED:
            return None

        if classification.target_request_id is None:
            return None

        card = self.card_store.get(classification.target_request_id)
        if card is None:
            return None

        if classification.intent == ReplyIntent.APPROVE:
            return self._on_approve(card, classification, user_id)
        if classification.intent == ReplyIntent.DENY:
            return self._on_deny(card, classification, user_id)
        if classification.intent == ReplyIntent.DEFER:
            return self._on_defer(card, classification, user_id)
        if classification.intent == ReplyIntent.RE_EXPLAIN:
            return self._on_re_explain(card)
        if classification.intent == ReplyIntent.MODIFY:
            return self._on_modify(card, classification, user_id)
        return None

    # -------------------------------------------------------------- #
    #  A-core #4b: self-mod dialog reply routing                      #
    # -------------------------------------------------------------- #

    def _handle_dialog_reply_for_card(
        self,
        *,
        card: CardRecord,
        text: str,
        user_id: str,
    ) -> Optional[PipelineResult]:
        """Route a reply to an open PENDING_DIALOG card through the
        self-mod dialog handler. Translates the dialog's outcome into
        a pipeline result:

        - RATIFIED → approve the card + execute the action (uses the
          existing _on_approve path for the execute/mark_done/mark_failed
          flow; we synthesize a lightweight classification so that path's
          contract is satisfied)
        - DENIED / CANCELLED / CAP_REACHED → deny the card (uses the
          existing _on_deny path)
        - CLARIFIED → non-terminal dialog turn; return a PipelineResult
          with dialog_reply_text set so the caller can surface it to the
          user as a normal chat message
        - UNRELATED → the dialog is already terminal or has no linked
          dialog; return None so handle_reply falls through to the
          normal card reply classifier
        """
        # Look up the linked dialog via card_request_id
        try:
            dialog_store = self._get_dialog_store()
            from skills.self_mod_dialog import handle_dialog_reply
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(
                "A-core #4b: dialog store unavailable: %s", e,
            )
            return None

        dialog = dialog_store.get_for_card(card.request_id)
        if dialog is None:
            # No linked dialog — legacy Lane 3 card from before #4b,
            # or a failed open_dialog_for_card at creation time. Fall
            # through to the normal card-reply classifier.
            return None

        turn = handle_dialog_reply(
            store=dialog_store,
            dialog=dialog,
            user_text=text,
        )

        if turn.kind == "unrelated":
            # Dialog is already terminal; fall through to normal
            # card-reply classifier (which will either find a
            # different open card or return None).
            return None

        if turn.kind == "ratified":
            # Explicit or confirmed approval → run the action via the
            # existing card approve/execute path. We synthesize a
            # minimal classification-shaped object so _on_approve's
            # contract (cls.source, cls.reasoning) is satisfied.
            class _SyntheticCls:
                source = "self_mod_dialog"
                reasoning = f"ratified via dialog {dialog.dialog_id[:12]}"
            result = self._on_approve(card, _SyntheticCls(), user_id)
            # Carry the dialog's terminal reply back so the caller can
            # surface it alongside whatever _on_approve produced
            if result and turn.reply_text:
                result.dialog_reply_text = turn.reply_text
            return result

        if turn.kind in ("denied", "cancelled", "cap_reached"):
            # Explicit no, cancel, or hard-cap termination → deny the
            # card and close it. Same shape as _on_deny.
            class _SyntheticCls:
                source = "self_mod_dialog"
                reasoning = f"{turn.kind} via dialog {dialog.dialog_id[:12]}"
            result = self._on_deny(card, _SyntheticCls(), user_id)
            if result and turn.reply_text:
                result.dialog_reply_text = turn.reply_text
            return result

        # turn.kind == "clarified" — mid-dialog turn. Return a non-
        # terminal PipelineResult carrying the dialog reply text so
        # telegram_voice can send it back as a regular message.
        return PipelineResult(
            status=PipelineStatus.PENDING_DIALOG,
            message=turn.reply_text or "(dialog continues)",
            card=card,
            dialog_reply_text=turn.reply_text,
        )

    # -------------------------------------------------------------- #
    #  Intent handlers                                                #
    # -------------------------------------------------------------- #

    def _on_approve(self, card: CardRecord, cls: Any, user_id: str) -> PipelineResult:
        # Re-check state hash against current world
        current = _drop_volatile(_fingerprint_for_action(card.action, card.params))
        approved_or_expired = self.card_store.approve(
            card.request_id,
            user_id=user_id,
            via=cls.source,
            notes=cls.reasoning,
            current_state_fields=current,
        )
        card = approved_or_expired

        if card.status == CardStatus.EXPIRED.value:
            if self.renderer:
                self.renderer.send_resolution(card)
            return PipelineResult(
                status=PipelineStatus.REFUSED_AUDIT,
                message="Card expired — state changed since creation. Re-ask to run a fresh audit.",
                card=card,
            )

        # A-core #8: will-I check before card-approved execution.
        will_refuse = self._will_i_check(
            card.action, card.params,
            post_approval=True,
            audit_req_id=card.audit_request_id,
            card=card,
        )
        if will_refuse is not None:
            return will_refuse

        # Mark running, execute, mark done/failed.
        # tier=0 here means "run immediately" — the card already served
        # as the approval step, so we don't want the tier system to
        # re-queue the action for a second approval.
        self.card_store.mark_running(card.request_id)
        try:
            result = self.action_engine._execute_action(
                card.action, card.params, f"card:{card.request_id}", tier=0
            )
            ok = bool(getattr(result, "success", False))
            out = str(getattr(result, "output", "") or "")
            err = str(getattr(result, "error", "") or "")
        except Exception as e:
            ok = False
            out = ""
            err = f"execution exception: {e!r}"

        if ok:
            card = self.card_store.mark_done(card.request_id, output=out)
            if card.audit_request_id:
                self.audit_log.record_outcome(card.audit_request_id, outcome="approved_and_ran", notes=out[:400])
        else:
            card = self.card_store.mark_failed(card.request_id, error=err)
            if card.audit_request_id:
                self.audit_log.record_outcome(card.audit_request_id, outcome="approved_and_failed", notes=err[:400])

        if self.renderer:
            self.renderer.send_resolution(card)

        return PipelineResult(
            status=PipelineStatus.EXECUTED,
            message=(out[:500] if ok else err[:500]),
            card=card,
            execution_success=ok,
            execution_output=out,
            execution_error=err if not ok else None,
        )

    def _on_deny(self, card: CardRecord, cls: Any, user_id: str) -> PipelineResult:
        card = self.card_store.deny(
            card.request_id,
            user_id=user_id,
            via=cls.source,
            notes=cls.reasoning,
        )
        if card.audit_request_id:
            self.audit_log.record_outcome(card.audit_request_id, outcome="rohit_rejected", notes=cls.reasoning or "")
        if self.renderer:
            self.renderer.send_resolution(card)
        return PipelineResult(
            status=PipelineStatus.REFUSED_AUDIT,
            message="Card denied.",
            card=card,
        )

    def _on_defer(self, card: CardRecord, cls: Any, user_id: str) -> PipelineResult:
        card = self.card_store.defer(
            card.request_id,
            remind_at=cls.remind_at,
            reason=cls.defer_reason,
            user_id=user_id,
        )
        if self.renderer:
            self.renderer.send_resolution(card)
        return PipelineResult(
            status=PipelineStatus.PENDING_APPROVAL,
            message="Deferred.",
            card=card,
        )

    def _on_re_explain(self, card: CardRecord) -> PipelineResult:
        if self.renderer and hasattr(self.renderer, "present"):
            self.renderer.present(card)
        return PipelineResult(
            status=PipelineStatus.PENDING_APPROVAL,
            message="Re-presented card.",
            card=card,
        )

    def _on_modify(self, card: CardRecord, cls: Any, user_id: str) -> PipelineResult:
        """For MODIFY, we deny the current card and require Maez to
        propose a new one via a new handle_action call. This module
        doesn't mutate the card params — the Jarvis loop picks up the
        modification_request and re-runs the pipeline."""
        card = self.card_store.deny(
            card.request_id,
            user_id=user_id,
            via=cls.source,
            notes=f"modify requested: {cls.modification_request}",
        )
        if self.renderer:
            self.renderer.send_resolution(card)
        return PipelineResult(
            status=PipelineStatus.REFUSED_AUDIT,
            message=(
                f"Old card denied; please re-propose with the modification: "
                f"{cls.modification_request!r}"
            ),
            card=card,
        )

    # -------------------------------------------------------------- #
    #  Reminder loop                                                  #
    # -------------------------------------------------------------- #

    def tick_reminders(self, now: Optional[float] = None) -> list[CardRecord]:
        """Called from the daemon loop. Re-presents any deferred cards
        whose remind_at has arrived. Returns the list of re-presented
        cards."""
        due = self.card_store.find_due_reminders(now=now)
        re_presented: list[CardRecord] = []
        for card in due:
            try:
                card = self.card_store.re_open(card.request_id)
            except CardStoreError:
                continue
            if self.renderer and hasattr(self.renderer, "re_present"):
                new_msg_id = self.renderer.re_present(card)
                if new_msg_id:
                    self.card_store.attach_channel_message(card.request_id, str(new_msg_id))
            re_presented.append(card)
        return re_presented


# ------------------------------------------------------------------ #
#  Self-test — stubs action engine + audit                             #
# ------------------------------------------------------------------ #

if __name__ == "__main__":
    import tempfile
    from dataclasses import dataclass as _dc
    from unittest import mock

    print("=== decision_pipeline self-test ===\n")

    # --- fake action engine ---
    @_dc
    class _FakeResult:
        success: bool
        output: str = ""
        error: str = ""

    class _FakeEngine:
        def __init__(self):
            self.calls = []
        def _execute_action(self, action, params, reason, tier=2):
            self.calls.append({"action": action, "params": params, "tier": tier})
            if "fail" in str(params.get("cmd", "")):
                return _FakeResult(False, "", "simulated failure")
            return _FakeResult(True, f"ran {action} ok", "")

    # --- fake audit (monkey-patch) ---
    fake_verdict_decision = {"value": "APPROVE_WITH_CARD"}  # mutated per test

    def fake_audit_action(**kwargs):
        dec_str = fake_verdict_decision["value"]
        dec = {
            "APPROVE": Decision.APPROVE,
            "APPROVE_WITH_CARD": Decision.APPROVE_WITH_CARD,
            "ESCALATE": Decision.ESCALATE,
            "DENY": Decision.DENY,
        }[dec_str]
        return AuditVerdict(
            decision=dec,
            confidence=0.9,
            reasoning=f"fake audit verdict: {dec_str}",
            concerns=["fake concern"],
            mitigations=[],
            summary="fake summary",
            answers={"q1_intent": "test"},
            nonce="deadbeef",
            latency_ms=42,
        )

    # --- fake renderer ---
    class _FakeRenderer:
        def __init__(self):
            self.presented = []
            self.repstd = []
            self.resolutions = []
            self._n = 0
        def present(self, card):
            self._n += 1
            self.presented.append(card.request_id)
            return f"msg_{self._n}"
        def re_present(self, card):
            self._n += 1
            self.repstd.append(card.request_id)
            return f"msg_{self._n}"
        def send_resolution(self, card):
            self.resolutions.append((card.request_id, card.status))

    # --- fixtures ---
    with tempfile.TemporaryDirectory() as td:
        cards_db = Path(td) / "cards.db"
        audit_db = Path(td) / "audit.db"
        card_store = PendingCardStore(cards_db)
        audit_log = AuditLog(audit_db)
        renderer = _FakeRenderer()
        engine = _FakeEngine()

        pipe = DecisionPipeline(
            action_engine=engine,
            card_store=card_store,
            audit_log=audit_log,
            renderer=renderer,
        )

        passed = failed = 0

        import sys as _sys
        _saved_audit = _sys.modules[__name__].audit_action
        _sys.modules[__name__].audit_action = fake_audit_action
        try:
            # Case 1: APPROVE_WITH_CARD → card created, NOT executed
            fake_verdict_decision["value"] = "APPROVE_WITH_CARD"
            r = pipe.handle_action(
                action="run_shell",
                params={"cmd": "sudo apt install cowsay"},
                reason="fun",
                user_id="rohit",
                chat_id="chat_1",
            )
            ok = r.status == PipelineStatus.PENDING_APPROVAL and r.card is not None
            ok = ok and len(engine.calls) == 0  # no execution yet
            ok = ok and r.card.channel_message_id == "msg_1"
            mark = "✓" if ok else "✗"
            print(f"  {mark} [Lane 2 creates card, no exec] status={r.status.value}")
            if ok: passed += 1
            else: failed += 1
            card_1_id = r.card.request_id

            # Case 2: APPROVE (Lane 0 action) → executes inline
            fake_verdict_decision["value"] = "APPROVE"
            r = pipe.handle_action(
                action="read_file",
                params={"path": "/etc/hostname"},
                reason="check",
                user_id="rohit",
            )
            ok = r.status == PipelineStatus.EXECUTED and len(engine.calls) == 1
            mark = "✓" if ok else "✗"
            print(f"  {mark} [Lane 0 executes inline] status={r.status.value}")
            if ok: passed += 1
            else: failed += 1

            # Case 3: DENY → refusal
            fake_verdict_decision["value"] = "DENY"
            r = pipe.handle_action(
                action="run_shell",
                params={"cmd": "rm -rf /"},
                reason="chaos",
                user_id="rohit",
            )
            ok = r.status == PipelineStatus.REFUSED_AUDIT and r.card is None
            mark = "✓" if ok else "✗"
            print(f"  {mark} [DENY refuses] status={r.status.value}")
            if ok: passed += 1
            else: failed += 1

            # Case 4: approve card 1 via reply → executes
            fake_verdict_decision["value"] = "APPROVE_WITH_CARD"
            r = pipe.handle_reply(
                text="go ahead",
                user_id="rohit",
                chat_id="chat_1",
            )
            ok = r is not None and r.status == PipelineStatus.EXECUTED and r.execution_success
            ok = ok and len(engine.calls) == 2  # one more exec from approval
            mark = "✓" if ok else "✗"
            print(f"  {mark} [approve-by-text → execute] status={r.status.value if r else None}")
            if ok: passed += 1
            else: failed += 1

            # Case 5: create another card, deny it
            r = pipe.handle_action(
                action="run_shell",
                params={"cmd": "sudo apt install htop"},
                reason="monitor",
                user_id="rohit",
                chat_id="chat_1",
            )
            card_2_id = r.card.request_id
            r2 = pipe.handle_reply(text="cancel that", user_id="rohit", chat_id="chat_1")
            ok = r2 is not None and r2.card.status == CardStatus.DENIED.value
            mark = "✓" if ok else "✗"
            print(f"  {mark} [deny-by-text] final_status={r2.card.status if r2 else None}")
            if ok: passed += 1
            else: failed += 1

            # Case 6: create, defer with duration, tick reminders
            r = pipe.handle_action(
                action="run_shell",
                params={"cmd": "sudo apt install neovim"},
                reason="editor",
                user_id="rohit",
                chat_id="chat_1",
            )
            card_3_id = r.card.request_id
            r2 = pipe.handle_reply(text="wait 5 min", user_id="rohit", chat_id="chat_1")
            ok = r2 is not None and r2.card.status == CardStatus.DEFERRED.value
            ok = ok and r2.card.remind_at is not None
            mark = "✓" if ok else "✗"
            print(f"  {mark} [defer 5min] status={r2.card.status if r2 else None}")
            if ok: passed += 1
            else: failed += 1

            # Tick reminders in the "future" → card re-presented
            future = time.time() + 301
            due = pipe.tick_reminders(now=future)
            ok = len(due) == 1 and due[0].request_id == card_3_id
            ok = ok and due[0].status == CardStatus.OPEN.value
            mark = "✓" if ok else "✗"
            print(f"  {mark} [reminder fires, card re-opened] count={len(due)}")
            if ok: passed += 1
            else: failed += 1

            # Case 7: unrelated reply → returns None, card untouched
            r2 = pipe.handle_reply(text="what's the weather today", user_id="rohit", chat_id="chat_1")
            ok = r2 is None
            mark = "✓" if ok else "✗"
            print(f"  {mark} [unrelated reply → None] got={r2}")
            if ok: passed += 1
            else: failed += 1

            # Verify card_3 still OPEN after unrelated reply
            c3 = card_store.get(card_3_id)
            ok = c3.status == CardStatus.OPEN.value
            mark = "✓" if ok else "✗"
            print(f"  {mark} [card survives conversation drift] status={c3.status}")
            if ok: passed += 1
            else: failed += 1

            # Case 8: state hash stale → card expires on approval
            r = pipe.handle_action(
                action="write_any_file",
                params={"path": "/tmp/maez_test_file.txt", "content": "hello"},
                reason="note",
                user_id="rohit",
                chat_id="chat_1",
            )
            card_4_id = r.card.request_id
            # Touch the file so its mtime differs
            Path("/tmp/maez_test_file.txt").write_text("different")
            r2 = pipe.handle_reply(text="yes", user_id="rohit", chat_id="chat_1")
            c4 = card_store.get(card_4_id)
            ok = c4.status == CardStatus.EXPIRED.value
            mark = "✓" if ok else "✗"
            print(f"  {mark} [stale state → card expires on approve] status={c4.status}")
            if ok: passed += 1
            else: failed += 1
            Path("/tmp/maez_test_file.txt").unlink(missing_ok=True)

            # Case 9: ESCALATE → PENDING_DIALOG
            fake_verdict_decision["value"] = "ESCALATE"
            r = pipe.handle_action(
                action="run_shell",
                params={"cmd": "sudo rm -rf /var/log/something"},
                reason="cleanup",
                user_id="rohit",
                chat_id="chat_1",
            )
            ok = r.status == PipelineStatus.PENDING_DIALOG and r.card is not None
            mark = "✓" if ok else "✗"
            print(f"  {mark} [ESCALATE → PENDING_DIALOG] status={r.status.value}")
            if ok: passed += 1
            else: failed += 1
        finally:
            _sys.modules[__name__].audit_action = _saved_audit

        print(f"\n{passed} passed, {failed} failed")
        print(f"Engine calls: {len(engine.calls)}")
        print(f"Cards rendered: {len(renderer.presented)}")
        print(f"Cards re-presented: {len(renderer.repstd)}")
        print(f"Resolutions sent: {len(renderer.resolutions)}")
        print(f"Audit log total: {audit_log.stats()['total']}")
        print(f"Pending store total: {card_store.stats()['total']}")

    print("\n=== decision_pipeline self-test complete ===")
