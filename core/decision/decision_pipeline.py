# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
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

import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

from core.action_classifier import classify_action, ClassificationResult
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
#  Audit-trail helpers (T2 cleanup 2026-05-04)                         #
# ------------------------------------------------------------------ #

def _owner_display_name() -> str:
    """Return the canonical owner display_name. Indirection lets tests
    monkeypatch this without reaching into the identity module's
    cache. Falls back to "Friend" if identity is unavailable."""
    try:
        from core.identity import display_name as _dn
        return _dn() or "Friend"
    except Exception:
        return "Friend"


def _owner_rejection_outcome() -> str:
    """Owner-derived audit_log outcome label for owner-rejected cards.

    Replaces the historical hardcoded "rohit_rejected" string so the
    audit trail is correct on any non-Rohit instance. For Rohit's
    instance this still resolves to "rohit_rejected" because the
    canonical owner display_name is "Rohit" — slug = "rohit". Other
    instances get "<slug>_rejected" (e.g. "alice_rejected"). The
    quality_tracker / drift report keys on "rohit_rejected" still
    work for Rohit's instance unchanged.
    """
    name = _owner_display_name()
    slug = "".join(c.lower() if c.isalnum() else "_" for c in name).strip("_")
    if not slug:
        slug = "owner"
    return f"{slug}_rejected"


def _s7_now_text() -> str:
    return datetime.now(timezone.utc).isoformat()


def _s7_one_hour_from_now_text() -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()


def _s7_card_time_text(epoch_seconds: float) -> str:
    return datetime.fromtimestamp(float(epoch_seconds), timezone.utc).isoformat()


def _resolve_audit_request_id(card: Any) -> str:
    """Return a usable audit_request_id for a card, synthesizing a
    deterministic `orphan-card-<request_id>` fallback when the card
    has no audit_request_id. The audit-trail invariant is "every card
    outcome → one audit_log row"; orphans broke that silently before
    this helper existed.
    """
    aid = getattr(card, "audit_request_id", None)
    if aid:
        return str(aid)
    return f"orphan-card-{getattr(card, 'request_id', 'unknown')}"


# ------------------------------------------------------------------ #
#  Result types                                                        #
# ------------------------------------------------------------------ #

class PipelineStatus(str, Enum):
    EXECUTED            = "executed"             # Lane 0 ran inline
    PENDING_APPROVAL    = "pending_approval"     # Lane 2 card created
    PENDING_DIALOG      = "pending_dialog"       # Lane 3 self-mod dialog entry
    BLOCKED             = "blocked"              # S7 or explicit runtime gate blocked
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
        params = dict(params or {})
        plain_english = params.pop("plain_english", None)  # LLM-authored human description, not a command param

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

        # Fabricated-target pre-check — catches systemctl write verbs
        # against unit names that don't exist on this system. Added
        # 2026-04-20 after `maez-llm.service` was fabricated and the
        # card pipeline queued `systemctl start maez-llm.service`
        # with no way to know the unit was invented. See
        # core/owner_trust.cmd_validity_error.
        if action == "run_shell":
            try:
                from core.owner_trust import cmd_validity_error
                _cmd_str = params.get("cmd", "") if isinstance(params, dict) else ""
                _err = cmd_validity_error(_cmd_str)
                if _err:
                    return PipelineResult(
                        status=PipelineStatus.REFUSED_INVALID,
                        message=_err,
                        classification=None,
                        injection_matches=[],
                    )
            except Exception:
                pass

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

        # Approval-session shortcut: if the user has granted a blanket
        # session (e.g. "reading is fine") and this is a read-safe
        # run_shell, promote it to Lane 0 so the user doesn't see the
        # per-command card that they just explicitly waived.
        # See core/approval_sessions.py.
        if (
            not is_lane_0
            and action == "run_shell"
            and verdict.decision == Decision.APPROVE
        ):
            try:
                from core import approval_sessions as _approvals
                cmd = (params or {}).get("cmd", "") if isinstance(params, dict) else ""
                if (_approvals.is_active("read_safe")
                        and _approvals.is_read_safe_cmd(cmd)):
                    is_lane_0 = True
            except Exception:
                pass

        # Owner-trust lane-flip: per `project_bond_styles_dimension.md`,
        # Rohit's Maez is liberal — friend-with-keys, inline-default for
        # non-risky acts. Any destructive / sudo / package-mgmt /
        # network-write / self-mod command is still routed to a card.
        # Covenant / audit / will-I all already ran and don't change;
        # this is purely the UX policy layer. See core/owner_trust.py.
        if (
            not is_lane_0
            and verdict.decision == Decision.APPROVE
        ):
            try:
                from core import owner_trust as _owner_trust
                should_inline, reason = _owner_trust.should_run_inline(
                    user_id, action, params,
                )
                if should_inline:
                    is_lane_0 = True
                    # Log the flip for auditability — the lane decision
                    # was overridden by trust policy, not by the classifier.
                    try:
                        import logging as _logging
                        _logging.getLogger(__name__).info(
                            "owner_trust lane-flip: user=%s action=%s reason=%s",
                            user_id, action, reason,
                        )
                    except Exception:
                        pass
            except Exception:
                pass

        if verdict.decision == Decision.APPROVE and is_lane_0:
            if self._action_requires_s7_authorization(action, params):
                return PipelineResult(
                    status=PipelineStatus.BLOCKED,
                    message="S7 authorization required before guarded inline execution",
                    verdict=verdict,
                    classification=classification,
                    injection_matches=injection_matches,
                    audit_request_id=audit_req_id,
                )
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
            plain_english=plain_english,
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
                    open_dialog_for_card,
                )
                dialog_store = self._get_dialog_store()
                s7_envelope = self._s7_request_envelope_for_card(card)
                from core.governance import operator_user_boundary as s7

                _dialog, dialog_opening_text = open_dialog_for_card(
                    store=dialog_store,
                    card_action=action,
                    card_params=params,
                    card_request_id=card.request_id,
                    audit_reasoning=verdict.reasoning or "",
                    concerns=list(verdict.concerns or []),
                    require_s7_linkage=True,
                    s7_request_envelope_hash=s7.work_request_envelope_hash(s7_envelope),
                )
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(
                    "A-core #4b: failed to open self-mod dialog for card %s: %s",
                    card.request_id, e,
                )
                blocked = self._block_s7_card(
                    card,
                    reason="self-mod dialog linkage failed for guarded work",
                )
                blocked.verdict = verdict
                blocked.classification = classification
                blocked.injection_matches = injection_matches
                blocked.audit_request_id = audit_req_id
                return blocked

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

        # T2.C (2026-05-04): mirror _on_approve's failure-branch
        # consequence_memory recording. The Lane 0 inline path was
        # structurally missing the equivalent learning signal — an
        # inline action approved-then-failed produced no
        # consequence_memory trail, so the planner re-surfaced the
        # same proposal cycle after cycle. Same kind / context /
        # surface shape as _on_approve so quality reports aggregate
        # uniformly across both paths. Silent on failure to keep
        # pipeline resolution robust.
        if not ok:
            try:
                from core import consequence_memory as _cm
                _cmd = params.get("cmd") if isinstance(params, dict) else ""
                _context = (
                    f"action={action} cmd={_cmd!r}"
                    if _cmd else f"action={action}"
                )
                _cm.record_event(
                    kind=_cm.CLASS_TOOL_FAILURE,
                    context=_context[:400],
                    outcome=(err or "")[:400],
                    feedback="",  # open for future enrichment
                    surface="decision_pipeline",
                    tags=[action] + (
                        [_cmd.strip().split()[0]]
                        if _cmd and _cmd.strip().split() else []
                    ),
                    extra={"audit_request_id": audit_req_id, "lane": 0},
                )
            except Exception as _cm_exc:
                logger.warning(
                    "consequence_memory record_event failed on inline "
                    "action %s (approved_and_failed path) — pattern "
                    "won't be available for future planner avoidance: %s",
                    action, _cm_exc,
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
        s7_execution_authorization: Any = None,
    ) -> Optional[PipelineResult]:
        """Handle an incoming reply/reaction. Returns None if the reply
        is unrelated to any open card (the caller handles it as normal
        conversation)."""
        from skills.card_reply_classifier import classify_reply, ReplyIntent

        open_cards = self.get_cards_for(user_id, chat_id) if self.get_cards_for else []
        if not open_cards:
            return None

        # If the reply is threaded to a specific card message, use that
        # explicit target before the newest-card fallback below. A
        # newer dialog must not hijack a reply explicitly aimed at a
        # regular card.
        explicit_target = None
        explicit_target_card = None
        if reply_to_message_id:
            hit = self.card_store.get_by_message(channel, reply_to_message_id)
            if hit and hit.status in {CardStatus.OPEN.value, CardStatus.DEFERRED.value}:
                explicit_target = hit.request_id
                explicit_target_card = hit

        if (text or reaction_emoji) and explicit_target_card is not None:
            if self._is_pending_dialog_card(explicit_target_card):
                return self._handle_pending_dialog_input(
                    card=explicit_target_card,
                    text=text,
                    user_id=user_id,
                    s7_execution_authorization=s7_execution_authorization,
                )

        # A-core #4b: route to self-mod dialog ONLY IF the newest open
        # card is PENDING_DIALOG. If a regular APPROVE card was queued
        # AFTER the dialog opened, "Yes" approves the newer card —
        # matches user expectation ("the thing I just proposed").
        #
        # Previous version always won for PENDING_DIALOG regardless of
        # age, which caused the cap_reached silent-pause episode:
        # a stale dialog ate every "Yes" meant for newer cards.
        if (text or reaction_emoji) and open_cards and explicit_target_card is None:
            sorted_cards = sorted(
                open_cards,
                key=lambda c: getattr(c, "created_at", 0.0),
                reverse=True,
            )
            newest = sorted_cards[0]
            if self._is_pending_dialog_card(newest):
                dialog_result = self._handle_pending_dialog_input(
                    card=newest,
                    text=text,
                    user_id=user_id,
                    s7_execution_authorization=s7_execution_authorization,
                )
                if dialog_result is not None:
                    return dialog_result
                # If 'unrelated' (dialog terminal or no linked dialog),
                # fall through to the normal card reply classifier.

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

        if self._is_pending_dialog_card(card):
            return self._handle_pending_dialog_input(
                card=card,
                text=text,
                user_id=user_id,
                s7_execution_authorization=s7_execution_authorization,
            )

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

    @staticmethod
    def _is_pending_dialog_card(card: CardRecord) -> bool:
        return (
            getattr(card, "audit_decision", None) == "ESCALATE"
            or str(getattr(card, "lane", "")) == "3"
        )

    def _handle_pending_dialog_input(
        self,
        *,
        card: CardRecord,
        text: Optional[str],
        user_id: str,
        s7_execution_authorization: Any = None,
    ) -> Optional[PipelineResult]:
        if not text:
            return self._block_s7_card(
                card,
                reason="self-mod dialog requires text S7 authorization",
            )
        return self._handle_dialog_reply_for_card(
            card=card,
            text=text,
            user_id=user_id,
            s7_execution_authorization=s7_execution_authorization,
        )

    def _s7_request_envelope_for_card(self, card: CardRecord) -> Any:
        from core.governance import operator_user_boundary as s7

        path = str((card.params or {}).get("path") or (card.params or {}).get("file") or "")
        lowered = " ".join((card.action, path)).lower()
        if "soul" in lowered:
            proposed_change_class = "soul_change"
        elif "model_routing" in lowered or "trust_scope" in lowered:
            proposed_change_class = "model_routing_change"
        elif "config" in lowered:
            proposed_change_class = "config_change"
        elif "protection" in lowered:
            proposed_change_class = "protection_change"
        elif card.action == "capability.acquire":
            proposed_change_class = "capability_install_intent"
        elif card.action in {"write_any_file", "write_file", "append_to_file"}:
            proposed_change_class = "code_change"
        else:
            proposed_change_class = "unknown_change"

        derived = s7.derive_work_class(action=card.action, params=card.params)
        predicted_effect_class = (
            "protection_change"
            if proposed_change_class == "protection_change"
            else "behavior_change"
            if derived in s7.GUARDED_WORK_CLASSES
            else "no_behavior_change"
        )
        content_exposure_risk = (
            "bonded_content_ref"
            if any(key in (card.params or {}) for key in ("content", "note", "new_body", "proposed_new_body"))
            else "content_free"
        )
        free_text_ref_hash = (
            s7.canonical_hash({"params": card.params})
            if content_exposure_risk == "bonded_content_ref"
            else None
        )
        created_at = _s7_card_time_text(card.created_at)
        expires_at = _s7_card_time_text(card.created_at + 3600)
        voice_consultation_id = (
            f"s7.1.card.voice.{card.request_id}"
            if derived in s7.VOICE_SEAT_WORK_CLASSES
            else None
        )
        return s7.build_work_request_envelope(
            request_id=card.request_id,
            action=card.action,
            params=card.params,
            claimed_work_class=derived,
            requesting_subsystem="decision_pipeline",
            closed_symptom_code=(
                "self_mod_requested"
                if derived in s7.GUARDED_WORK_CLASSES
                else "verification_needed"
            ),
            proposed_change_class=proposed_change_class,
            why_self_fix_failed_class="needs_human_authority",
            affected_refs=s7.derive_affected_refs(action=card.action, params=card.params),
            content_exposure_risk=content_exposure_risk,
            precondition_hash=s7.canonical_hash({
                "card_state_hash": card.state_hash,
                "state_fields": card.state_fields,
            }),
            created_at=created_at,
            expires_at=expires_at,
            predicted_effect_class=predicted_effect_class,
            rollback_path_class=(
                "manual_review"
                if proposed_change_class == "protection_change"
                else "revert_patch"
                if derived in s7.GUARDED_WORK_CLASSES
                else "no_rollback_needed"
            ),
            maez_voice_consultation_id=voice_consultation_id,
            free_text_ref_hash=free_text_ref_hash,
        )

    def _s7_voice_consultation_for_card(self, card: CardRecord, envelope: Any) -> Any:
        """Produce the reviewed, content-free Maez voice-seat fact for a card.

        The consultation records the pipeline's own card/audit provenance, not
        caller prose. It deliberately carries only hashes and closed states.
        """
        from core.governance import operator_user_boundary as s7

        consultation_id = getattr(envelope, "maez_voice_consultation_id", None)
        if not consultation_id:
            consultation_id = f"s7.1.card.voice.{card.request_id}"
        source_ref_hash = s7.canonical_hash(
            {
                "card_request_id": card.request_id,
                "audit_request_id": getattr(card, "audit_request_id", None),
                "state_hash": getattr(card, "state_hash", None),
                "action": getattr(card, "action", None),
            }
        )
        return s7.MaezVoiceConsultation(
            consultation_id=consultation_id,
            request_id=envelope.request_id,
            request_envelope_hash=s7.work_request_envelope_hash(envelope),
            producer="s7_voice_consultation_turn",
            source_ref_kind="s7_voice_turn",
            source_ref_hash=source_ref_hash,
            maez_voice_consulted=True,
            maez_objection_state="not_determined",
            maez_withdrew_request=False,
            unavailable_reason_code="consultation_path_unavailable",
            created_at=_s7_now_text(),
        )

    def _handle_dialog_reply_for_card(
        self,
        *,
        card: CardRecord,
        text: str,
        user_id: str,
        s7_execution_authorization: Any = None,
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
            from skills.self_mod_dialog import DialogStage, handle_dialog_reply
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(
                "A-core #4b: dialog store unavailable: %s", e,
            )
            return self._block_s7_card(
                card,
                reason="self-mod dialog store unavailable for guarded work",
            )

        dialog = dialog_store.get_for_card(card.request_id)
        if dialog is None:
            return self._block_s7_card(
                card,
                reason="self-mod dialog linkage missing for guarded work",
            )

        authority_context = getattr(s7_execution_authorization, "authority_context", None)
        s7_artifact_id = getattr(s7_execution_authorization, "artifact_id", None)
        s7_now = getattr(s7_execution_authorization, "now", None)
        turn = handle_dialog_reply(
            store=dialog_store,
            dialog=dialog,
            user_text=text,
            authority_context=authority_context,
            s7_artifact_id=s7_artifact_id,
            s7_now=s7_now,
        )

        if turn.kind == "unrelated":
            # Dialog is already terminal; fall through to normal
            # card-reply classifier (which will either find a
            # different open card or return None).
            return None

        if turn.kind == "blocked":
            result = self._block_s7_card(
                card,
                reason="self-mod dialog blocked by missing S7 authorization",
            )
            if result and turn.reply_text:
                result.dialog_reply_text = turn.reply_text
            return result

        if turn.kind == "ratified":
            if not self._s7_card_precondition_fresh(card):
                dialog_store.set_blocked(
                    turn.dialog.dialog_id,
                    reason="stale S7 self-mod precondition",
                )
                result = self._block_s7_card(
                    card,
                    reason="stale S7 self-mod precondition",
                )
                if result and turn.reply_text:
                    result.dialog_reply_text = turn.reply_text
                return result
            # Explicit or confirmed approval → run the action via the
            # existing card approve/execute path. We synthesize a
            # minimal classification-shaped object so _on_approve's
            # contract (cls.source, cls.reasoning) is satisfied.
            # 02-M2: _on_approve historically reads audit_request_id
            # from `card`, not from cls — we propagate it onto cls
            # anyway so any future refactor that reaches for
            # cls.audit_request_id sees the correct value rather
            # than routing the outcome to a different audit row.
            _card_aid = getattr(card, "audit_request_id", None)
            class _SyntheticCls:
                source = "self_mod_dialog"
                reasoning = f"ratified via dialog {dialog.dialog_id[:12]}"
                audit_request_id = _card_aid
            result = self._on_approve(
                card,
                _SyntheticCls(),
                user_id,
                pre_execute_hook=lambda transition: self._consume_s7_execution_authorization(
                    s7_execution_authorization,
                    card=card,
                    dialog=turn.dialog,
                    after_consume_before_commit=transition,
                ),
                s7_artifact_id=getattr(s7_execution_authorization, "artifact_id", None),
                pre_execute_block_reason="missing or invalid S7 execution authorization",
            )
            # Carry the dialog's terminal reply back so the caller can
            # surface it alongside whatever _on_approve produced
            if result and turn.reply_text:
                result.dialog_reply_text = turn.reply_text
            if result and result.status in (
                PipelineStatus.BLOCKED,
                PipelineStatus.REFUSED_AUDIT,
                PipelineStatus.REFUSED_WILL,
            ):
                dialog_store.set_blocked(
                    turn.dialog.dialog_id,
                    reason=result.message or "S7 execution could not start",
                )
            elif result and result.status == PipelineStatus.EXECUTED:
                if result.execution_success is True:
                    dialog_store.set_stage(
                        turn.dialog.dialog_id,
                        DialogStage.EXECUTED.value,
                        execution_output=result.execution_output,
                    )
                elif result.execution_success is False:
                    dialog_store.set_stage(
                        turn.dialog.dialog_id,
                        DialogStage.FAILED.value,
                        execution_error=result.execution_error,
                    )
            return result

        if turn.kind in ("denied", "cancelled", "cap_reached"):
            # Explicit no, cancel, or hard-cap termination → deny the
            # card and close it. Same shape as _on_deny.
            _card_aid = getattr(card, "audit_request_id", None)
            class _SyntheticCls:
                source = "self_mod_dialog"
                reasoning = f"{turn.kind} via dialog {dialog.dialog_id[:12]}"
                audit_request_id = _card_aid
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

    def _consume_s7_execution_authorization(
        self,
        authorization: Any,
        *,
        card: CardRecord,
        dialog: Any,
        after_consume_before_commit: Optional[Callable[[Any], Any]] = None,
    ) -> tuple[Any, Any]:
        try:
            from core.governance import operator_user_boundary as s7

            if not isinstance(authorization, s7.S7ExecutionAuthorization):
                return False, None
            if authorization.rendered.request_id != card.request_id:
                return False, None
            if getattr(dialog, "s7_artifact_id", None) != authorization.artifact_id:
                return False, None
            if (
                getattr(dialog, "s7_request_envelope_hash", None)
                != authorization.rendered.request_envelope_hash
            ):
                return False, None
            execute_params = self._execution_params_for_card(card)
            actual_action_params_hash = s7.canonical_hash(execute_params)
            if authorization.action_params_hash != actual_action_params_hash:
                return False, None
            grant, transitioned_card = authorization.store.consume_for_execution(
                authorization.artifact_id,
                rendered=authorization.rendered,
                action_params_hash=actual_action_params_hash,
                authority_context=authorization.authority_context,
                precondition_hash=authorization.precondition_hash,
                derived_work_class=authorization.derived_work_class,
                derived_aggregation_group=authorization.derived_aggregation_group,
                now=authorization.now,
                covenant_ceremony_evidence=authorization.covenant_ceremony_evidence,
                after_consume_before_commit=after_consume_before_commit,
            )
            if not isinstance(grant, s7.S7ExecutionGrant):
                return False, transitioned_card
            return grant, transitioned_card
        except Exception:
            return False, None

    @staticmethod
    def _execution_params_for_card(card: CardRecord) -> dict:
        execute_params = dict(card.params or {})
        if card.action == "capability.acquire":
            execute_params.setdefault("card_request_id", card.request_id)
            if card.reason is not None:
                execute_params.setdefault("reason", card.reason)
            summary = card.proposed_action_summary or card.plain_english
            if summary is not None:
                execute_params.setdefault("plain_english", summary)
        return execute_params

    def _action_requires_s7_authorization(self, action: str, params: dict | None) -> bool:
        try:
            from core.governance import operator_user_boundary as s7

            work_class = s7.derive_work_class(action=action, params=params or {})
            return work_class in s7.GUARDED_WORK_CLASSES
        except Exception:
            return True

    def _s7_card_precondition_fresh(self, card: CardRecord) -> bool:
        if card.state_hash == "empty":
            return True
        current = _drop_volatile(_fingerprint_for_action(card.action, card.params))
        return compute_state_hash(current) == card.state_hash

    def _card_requires_s7_authorization(self, card: CardRecord) -> bool:
        return self._action_requires_s7_authorization(card.action, card.params)

    def _block_s7_card(self, card: CardRecord, *, reason: str) -> PipelineResult:
        try:
            blocked = self.card_store.block(card.request_id, reason)
        except CardStoreError as e:
            logger.warning(
                "card %s could not enter S7 blocked state (%s)",
                card.request_id,
                e,
            )
            blocked = self.card_store.get(card.request_id) or card
        return PipelineResult(
            status=PipelineStatus.BLOCKED,
            message=reason,
            card=blocked,
        )

    # -------------------------------------------------------------- #
    #  Intent handlers                                                #
    # -------------------------------------------------------------- #

    def _on_approve(
        self,
        card: CardRecord,
        cls: Any,
        user_id: str,
        *,
        pre_execute_hook: Optional[Callable[..., Any]] = None,
        s7_artifact_id: Optional[str] = None,
        pre_execute_block_reason: str = "pre-execution gate blocked",
    ) -> PipelineResult:
        s7_required = self._card_requires_s7_authorization(card)
        if s7_required and pre_execute_hook is None:
            return self._block_s7_card(
                card,
                reason="missing S7 execution authorization for guarded card",
            )
        if s7_required and not s7_artifact_id:
            return self._block_s7_card(
                card,
                reason="missing S7 authorization artifact for guarded card",
            )
        # Re-check state hash against current world
        current = _drop_volatile(_fingerprint_for_action(card.action, card.params))
        if s7_required:
            if card.state_hash != "empty":
                now_hash = compute_state_hash(current)
                if now_hash != card.state_hash:
                    expired = self.card_store.expire(
                        card.request_id,
                        f"state hash changed: was {card.state_hash}, now {now_hash}",
                    )
                    if self.renderer:
                        self.renderer.send_resolution(expired)
                    return PipelineResult(
                        status=PipelineStatus.REFUSED_AUDIT,
                        message="Card expired — state changed since creation. Re-ask to run a fresh audit.",
                        card=expired,
                    )
        else:
            try:
                approved_or_expired = self.card_store.approve(
                    card.request_id,
                    user_id=user_id,
                    via=cls.source,
                    notes=cls.reasoning,
                    current_state_fields=current,
                    s7_authorized=False,
                )
            except CardStoreError as e:
                return self._block_s7_card(card, reason=str(e))
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

        if s7_required:
            assert pre_execute_hook is not None

            def _mark_running_after_s7_verification(grant: Any) -> CardRecord:
                latest = _drop_volatile(_fingerprint_for_action(card.action, card.params))
                return self.card_store.approve_and_mark_running(
                    card.request_id,
                    user_id=user_id,
                    via=cls.source,
                    notes=cls.reasoning,
                    current_state_fields=latest,
                    s7_artifact_id=s7_artifact_id,
                    s7_execution_grant=grant,
                    s7_execution_params=self._execution_params_for_card(card),
                )

            try:
                pre_execute_result = pre_execute_hook(_mark_running_after_s7_verification)
            except Exception:
                pre_execute_result = (False, None)
            if isinstance(pre_execute_result, tuple):
                execution_grant = pre_execute_result[0]
                transitioned_card = pre_execute_result[1] if len(pre_execute_result) > 1 else None
            else:
                execution_grant = None
                transitioned_card = None
            if not isinstance(transitioned_card, CardRecord):
                return self._block_s7_card(card, reason="S7 transition did not return a running card")
            try:
                from core.governance import operator_user_boundary as s7

                pre_execute_ok = s7.execution_grant_authorizes_card_transition(
                    execution_grant,
                    request_id=card.request_id,
                    action=card.action,
                    params=self._execution_params_for_card(card),
                    artifact_id=s7_artifact_id,
                )
            except Exception:
                pre_execute_ok = False
            if not pre_execute_ok:
                failed_card = transitioned_card if isinstance(transitioned_card, CardRecord) else card
                return self._block_s7_card(failed_card, reason=pre_execute_block_reason)
            card = transitioned_card
            if card.status == CardStatus.EXPIRED.value:
                if self.renderer:
                    self.renderer.send_resolution(card)
                return PipelineResult(
                    status=PipelineStatus.REFUSED_AUDIT,
                    message="Card expired — state changed since creation. Re-ask to run a fresh audit.",
                    card=card,
                )
            if not self._s7_card_precondition_fresh(card):
                return self._block_s7_card(
                    card,
                    reason="stale S7 precondition after authorization consume",
                )
        else:
            # Mark running, execute, mark done/failed.
            # tier=0 here means "run immediately" — the card already served
            # as the approval step, so we don't want the tier system to
            # re-queue the action for a second approval.
            #
            # 02-B1: if `mark_running` itself raises CardStoreError the card
            # has already moved to a terminal state between the will-I check
            # above and here (concurrent deny, manual expiry, second
            # approval path). Treat that as "card already resolved" and
            # return the current state rather than crashing with an
            # unhandled CardStoreError up to the caller.
            try:
                card = self.card_store.mark_running(card.request_id)
            except CardStoreError as e:
                logger.warning(
                    "card %s already terminal at mark_running (%s); "
                    "skipping execution", card.request_id, e,
                )
                fresh = self.card_store.get(card.request_id) or card
                return PipelineResult(
                    status=PipelineStatus.REFUSED_AUDIT,
                    message="Card was already resolved before execution could start.",
                    card=fresh,
                )
        # Enrich params for actions whose handlers need the surrounding
        # card metadata (request_id / reason / proposed summary). The
        # default _execute_action contract passes only card.action +
        # card.params, which loses metadata that lives on the card
        # row itself. capability.acquire's handler stores
        # card_request_id, reason, and plain_english into the
        # acquisition queue for the audit trail — without enrichment
        # those queue fields would be NULL on real-card approvals.
        # (Step 4b post-review fix.)
        execute_params = self._execution_params_for_card(card)
        try:
            result = self.action_engine._execute_action(
                card.action, execute_params,
                f"card:{card.request_id}", tier=0,
                s7_execution_grant=execution_grant if s7_required else None,
            )
            ok = bool(getattr(result, "success", False))
            out = str(getattr(result, "output", "") or "")
            err = str(getattr(result, "error", "") or "")
        except Exception as e:
            ok = False
            out = ""
            err = f"execution exception: {e!r}"

        # 02-B1: mark_done / mark_failed can raise CardStoreError if the
        # card was terminally resolved by a racing path (will-I deny,
        # second approver). Log and continue — the outcome is still
        # written to audit_log; the card state just reflects whichever
        # path terminated first.
        if ok:
            try:
                card = self.card_store.mark_done(card.request_id, output=out)
            except CardStoreError as e:
                logger.warning(
                    "card %s already terminal at mark_done (%s); "
                    "outcome recorded to audit only", card.request_id, e,
                )
            self.audit_log.record_outcome(
                _resolve_audit_request_id(card),
                outcome="approved_and_ran",
                notes=out[:400],
            )
        else:
            try:
                card = self.card_store.mark_failed(card.request_id, error=err)
            except CardStoreError as e:
                logger.warning(
                    "card %s already terminal at mark_failed (%s); "
                    "outcome recorded to audit only", card.request_id, e,
                )
            self.audit_log.record_outcome(
                _resolve_audit_request_id(card),
                outcome="approved_and_failed",
                notes=err[:400],
            )

            # 2026-05-02 fix: record to consequence_memory so future
            # planner cycles can retrieve the failure pattern via
            # token-overlap and avoid re-proposing the same command.
            # The equivalent block in `_on_deny` records CARD_REJECTED;
            # this path was structurally missing the equivalent learning
            # signal for approve-then-failed. Without it, an action
            # approved-then-failed (e.g. `apt install <nonexistent-
            # package>`) had NO learnable signal, so Maez's planner
            # re-surfaced the same proposal cycle after cycle. Surfaced
            # by drift-report investigation: 95 historical run_shell
            # failures, dominated by repeated openrgb install attempts
            # that had no consequence_memory trail. Silent on failure
            # to keep card resolution robust.
            try:
                from core import consequence_memory as _cm
                _action = getattr(card, "action", "unknown")
                _params = getattr(card, "params", {}) or {}
                _cmd = _params.get("cmd") if isinstance(_params, dict) else ""
                _context = (
                    f"action={_action} cmd={_cmd!r}"
                    if _cmd else f"action={_action}"
                )
                _cm.record_event(
                    kind=_cm.CLASS_TOOL_FAILURE,
                    context=_context[:400],
                    # 400-char outcome to match audit_log's truncation
                    # (line ~1006 above) — same kind of "what went
                    # wrong" string, same length budget.
                    outcome=(err or "")[:400],
                    feedback="",  # open for future enrichment
                    surface="decision_pipeline",
                    tags=[_action] + (
                        [_cmd.strip().split()[0]]
                        if _cmd and _cmd.strip().split() else []
                    ),
                    extra={"request_id": card.request_id},
                )
            except Exception as _cm_exc:
                logger.warning(
                    "consequence_memory record_event failed on card %s "
                    "(approved_and_failed path) — pattern won't be "
                    "available for future planner avoidance: %s",
                    card.request_id, _cm_exc,
                )

        # If this card was attached to a wondering, fill the deferred probe
        # with real output and return the wondering to active state. Failure
        # here must never break card resolution.
        try:
            wid = (card.params or {}).get("wondering_id") if card.params else None
            if wid:
                from core.wonderings import (
                    get_store as _w_store, validate_learning,
                    LEARNING_SYNTH_BLOCKED,
                )
                # No second LLM synthesis in the pipeline — store the raw
                # outcome as the learning if it can be evidence-tied;
                # otherwise the synthesis-blocked sentinel. The next daemon
                # cycle can propose a follow-up probe.
                rc = 0 if ok else 1
                candidate = (out or err or "").strip().splitlines()
                candidate = candidate[0].strip()[:200] if candidate else ""
                tied = bool(candidate) and validate_learning(
                    candidate, out, err, rc,
                )
                learning = candidate if tied else LEARNING_SYNTH_BLOCKED
                _w_store().unblock_from_card(
                    int(wid), stdout=out, stderr=err, rc=rc,
                    learning=learning, evidence_tied=tied,
                )
        except Exception as _e:
            import logging
            logging.getLogger("maez.wonderings").debug(
                "unblock_from_card on approval failed: %s", _e,
            )

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
        self.audit_log.record_outcome(
            _resolve_audit_request_id(card),
            outcome=_owner_rejection_outcome(),
            notes=cls.reasoning or "",
        )
        # Card rejection is a real residue event — Maez proposed
        # something and the user declined. Functional state, not
        # performance; feeds into the next turn's tone. Silent on
        # failure. See core/inner_residue.py.
        try:
            from core import inner_residue as _residue
            _residue.record(
                kind="card_rejected",
                context={"action": getattr(card, "action", None),
                         "request_id": card.request_id},
            )
        except Exception:
            pass

        # Also record to consequence_memory so future planner calls
        # can retrieve similar past rejections via token-overlap and
        # avoid re-proposing the same pattern. inner_residue is
        # transient (30-min half-life); consequence_memory persists.
        # The two complement rather than duplicate.
        # 02-M1: wrap consequence_memory recording with explicit logging
        # on failure. Previously the outer try/except swallowed every
        # exception silently, so a card rejection that failed to reach
        # consequence_memory would re-surface on the next planner cycle
        # as a proposal Maez never learned was already rejected.
        try:
            from core import consequence_memory as _cm
            _action = getattr(card, "action", "unknown")
            _params = getattr(card, "params", {}) or {}
            _cmd = _params.get("cmd") if isinstance(_params, dict) else ""
            _context = f"action={_action} cmd={_cmd!r}" if _cmd else f"action={_action}"
            _cm.record_event(
                kind=_cm.CLASS_CARD_REJECTED,
                context=_context[:400],
                outcome=cls.reasoning[:300] if cls.reasoning else "denied",
                feedback="",  # open for future enrichment
                surface="decision_pipeline",
                tags=[_action] + ([_cmd.strip().split()[0]]
                                    if _cmd and _cmd.strip().split()
                                    else []),
                extra={"request_id": card.request_id},
            )
        except Exception as _cm_exc:
            logger.warning(
                "consequence_memory record_event failed on card %s: %s — "
                "rejection not persisted; planner may re-propose this action",
                card.request_id, _cm_exc,
            )

        # D20 Stage-5 — when an integration.review_plan card is
        # denied, propagate the denial to the plans store so
        # `list_pending_review` no longer surfaces it. Without
        # this hook the plan would stay at status='draft' forever:
        # the next hourly poll would skip it (existing plan), and
        # the cockpit's pending-review filter would lie.
        if getattr(card, "action", None) == "integration.review_plan":
            try:
                from core.infra.capability_integration_plans import (
                    IntegrationPlanStore,
                )
                plan_id = (
                    (getattr(card, "params", {}) or {}).get("plan_id")
                )
                if plan_id:
                    _store = IntegrationPlanStore()
                    _existing = next(
                        (p for p in _store.list_all()
                         if p["plan_id"] == plan_id),
                        None,
                    )
                    if _existing and _existing["plan_status"] == "draft":
                        _store.upsert(
                            queue_id=_existing["queue_id"],
                            capability_id=_existing["capability_id"],
                            plan_status="plan_rejected",
                            plan_json=_existing["plan_json"],
                        )
            except Exception as _plan_exc:
                logger.debug(
                    "integration_plans deny-propagation failed for "
                    "card %s: %s",
                    card.request_id, _plan_exc,
                )

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
        def _execute_action(
            self,
            action,
            params,
            reason,
            tier=2,
            s7_authorized=False,
            s7_execution_grant=None,
        ):
            del s7_authorized, s7_execution_grant
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
