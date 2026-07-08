"""Cockpit V2 approval queue read model and guarded decisions.

Approvals are a window over the existing pending-card authority. This module
does not create a second approval store: approve routes through the daemon's
existing approval channel, and reject routes through PendingCardStore.deny().
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable, Mapping
from uuid import uuid4

from core.governance.operator_user_boundary import GUARDED_WORK_CLASSES, derive_work_class
from core.infra.ro_sqlite import _ro_connect

Clock = Callable[[], datetime]
ExistingApproveChannel = Callable[[str, Mapping[str, object]], Mapping[str, object]]

_AWAITING_STATUSES = ("open", "deferred")
_EXECUTION_SHAPED_ACTIONS = frozenset({"run_shell"})


@dataclass(frozen=True)
class CockpitApprovalPaths:
    cards_db: Path
    receipt_log: Path

    @classmethod
    def defaults(cls) -> "CockpitApprovalPaths":
        from core.infra import paths

        return cls(
            cards_db=paths.memory_dir() / "pending_cards.db",
            receipt_log=paths.logs_dir() / "cockpit_approval_receipts.jsonl",
        )


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _append_receipt(path: Path, receipt: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
        f.write("\n")


def _loads_dict(raw: object) -> dict[str, object]:
    if not raw:
        return {}
    try:
        parsed = json.loads(str(raw))
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _table_exists(con: sqlite3.Connection, table: str) -> bool:
    row = con.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone()
    return row is not None


def _approval_tier(action: str, params: Mapping[str, object]) -> str:
    try:
        work_class = derive_work_class(action=action, params=dict(params))
    except Exception:
        work_class = "undeterminable_work_class"
    if action in _EXECUTION_SHAPED_ACTIONS or work_class in GUARDED_WORK_CLASSES:
        return "T2"
    return "T1"


def _confirmation_text(request_id: str) -> str:
    return f"APPROVE {request_id}"


def _refusal(
    request_id: str,
    reason: str,
    *,
    extra: Mapping[str, object] | None = None,
) -> dict[str, object]:
    out: dict[str, object] = {
        "ok": False,
        "status": "refused",
        "request_id": request_id,
        "reason": reason,
    }
    if extra:
        out.update(extra)
    return out


def _http_status(upstream: Mapping[str, object]) -> int | None:
    raw = upstream.get("http_status")
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return raw
    try:
        return int(str(raw))
    except Exception:
        return None


def _upstream_reason(upstream: Mapping[str, object], fallback: str) -> str:
    for key in ("error", "reason", "message", "status"):
        raw = upstream.get(key)
        if isinstance(raw, str) and raw:
            return raw
    return fallback


def _approval_outcome(
    upstream: Mapping[str, object],
    final_card_status: str | None,
) -> tuple[str, str | None]:
    http_status = _http_status(upstream)
    http_ok = http_status is not None and 200 <= http_status < 300
    upstream_ok = upstream.get("ok") is True
    resolved = final_card_status is not None and final_card_status not in _AWAITING_STATUSES

    if http_ok and upstream_ok and resolved:
        return "resolved", None
    if not http_ok or not upstream_ok:
        if http_status is not None and 400 <= http_status < 500:
            return "refused", _upstream_reason(upstream, "upstream_refused")
        if str(upstream.get("status") or "") in {"blocked", "refused", "denied"}:
            return "refused", _upstream_reason(upstream, "upstream_refused")
        return "failed", _upstream_reason(upstream, "upstream_failed")
    return "unconfirmed", "upstream_unconfirmed"


def _row_to_card(row: sqlite3.Row) -> dict[str, object]:
    params = _loads_dict(row["params_json"])
    action = str(row["action"] or "")
    tier = _approval_tier(action, params)
    return {
        "request_id": row["request_id"],
        "id": row["request_id"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "status": row["status"],
        "action": action,
        "params": params,
        "reason": row["reason"] or "",
        "plain_english": row["plain_english"] or "",
        "proposed_action_summary": row["proposed_action_summary"] or "",
        "decision_tier": tier,
        "required_confirmation": _confirmation_text(str(row["request_id"])) if tier == "T2" else None,
        "channel": "existing_pending_cards",
    }


def _read_card(paths: CockpitApprovalPaths, request_id: str) -> dict[str, object] | None:
    con = _ro_connect(paths.cards_db)
    if con is None:
        return None
    with closing(con):
        con.execute("PRAGMA query_only=ON")
        if not _table_exists(con, "pending_cards"):
            return None
        row = con.execute(
            "SELECT * FROM pending_cards WHERE request_id = ?",
            (request_id,),
        ).fetchone()
    return _row_to_card(row) if row is not None else None


def build_approvals_room(paths: CockpitApprovalPaths | None = None) -> dict[str, object]:
    """Return pending approvals without creating the pending-card DB."""

    paths = paths or CockpitApprovalPaths.defaults()
    con = _ro_connect(paths.cards_db)
    if con is None:
        return {
            "kind": "cockpit_v2_approvals",
            "status": "no_data",
            "pending_count": 0,
            "pending": [],
            "source": str(paths.cards_db),
        }
    with closing(con):
        con.execute("PRAGMA query_only=ON")
        if not _table_exists(con, "pending_cards"):
            return {
                "kind": "cockpit_v2_approvals",
                "status": "no_data",
                "pending_count": 0,
                "pending": [],
                "source": str(paths.cards_db),
            }
        rows = con.execute(
            """
            SELECT *
            FROM pending_cards
            WHERE status IN (?, ?)
            ORDER BY created_at ASC
            LIMIT 50
            """,
            _AWAITING_STATUSES,
        ).fetchall()

    pending = [_row_to_card(row) for row in rows]
    return {
        "kind": "cockpit_v2_approvals",
        "status": "ok",
        "pending_count": len(pending),
        "pending": pending,
        "source": str(paths.cards_db),
        "authority": "existing_pending_cards",
    }


def apply_approval_decision(
    request_id: str,
    decision: str,
    *,
    paths: CockpitApprovalPaths,
    owner_authenticated: bool,
    confirm_click_token: str | None = None,
    typed_confirmation: str | None = None,
    edited_params: Mapping[str, object] | None = None,
    existing_approve_channel: ExistingApproveChannel | None = None,
    now: Clock = _now_utc,
) -> dict[str, object]:
    """Apply an approval decision through the existing card authority."""

    if not owner_authenticated:
        return _refusal(request_id, "owner_auth_required")
    if decision not in {"approve", "reject"}:
        return _refusal(request_id, "invalid_decision")
    if confirm_click_token != "confirm":
        return _refusal(request_id, "confirm_click_required")

    card = _read_card(paths, request_id)
    if card is None:
        return _refusal(request_id, "card_not_found")
    tier = str(card["decision_tier"])
    if decision == "approve" and tier == "T2" and typed_confirmation != _confirmation_text(request_id):
        return _refusal(
            request_id,
            "typed_confirmation_required",
            extra={"required_confirmation": _confirmation_text(request_id), "tier": tier},
        )

    at = now()
    if at.tzinfo is None:
        at = at.replace(tzinfo=UTC)
    receipt_id = f"cockpit-approval-{uuid4().hex}"

    if decision == "approve":
        if existing_approve_channel is None:
            return _refusal(request_id, "approval_channel_unavailable", extra={"tier": tier})
        upstream = dict(existing_approve_channel(request_id, {"edited_params": edited_params}))
        channel = "existing_approval_channel"
    else:
        from core.pending_cards import CardStoreError, PendingCardStore

        store = PendingCardStore(paths.cards_db)
        try:
            resolved = store.deny(
                request_id,
                user_id="rohit",
                via="cockpit_v2",
                notes="denied from cockpit v2",
            )
            upstream = {"ok": True, "http_status": 200, "status": resolved.status}
        except CardStoreError as e:
            upstream = {
                "ok": False,
                "http_status": 409,
                "status": "conflict",
                "error": str(e),
            }
        channel = "existing_pending_cards"

    final_card = _read_card(paths, request_id)
    final_card_status = str(final_card["status"]) if final_card is not None else None
    outcome, outcome_reason = _approval_outcome(upstream, final_card_status)

    receipt = {
        "receipt_id": receipt_id,
        "action": "approval_decision",
        "request_id": request_id,
        "decision": decision,
        "tier": tier,
        "channel": channel,
        "at": at.isoformat(),
        "confirmation_kind": "typed" if decision == "approve" and tier == "T2" else "click",
        "upstream": upstream,
        "outcome": outcome,
        "final_card_status": final_card_status,
    }
    _append_receipt(paths.receipt_log, receipt)
    result = {
        "ok": outcome == "resolved",
        "status": outcome,
        "outcome": outcome,
        "request_id": request_id,
        "decision": decision,
        "tier": tier,
        "channel": channel,
        "receipt_id": receipt_id,
        "upstream": upstream,
        "final_card_status": final_card_status,
    }
    if outcome_reason:
        result["reason"] = outcome_reason
    return result
