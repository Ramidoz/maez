"""Deterministic resolution rails for conversational consent."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable, Mapping
from uuid import uuid4

from core.consent.bindings import BindingRegistry
from core.consent.spine import ConsentIntent, OwnerUtterance
from core.pending_cards import AWAITING_STATUSES, CardStoreError, PendingCardStore


ApproveChannel = Callable[[str, Mapping[str, object]], Mapping[str, object]]
Clock = Callable[[], datetime]

_DEFAULT_APPROVE_CHANNEL = object()


@dataclass(frozen=True)
class ConsentResolutionPaths:
    receipt_log: Path

    @classmethod
    def defaults(cls) -> "ConsentResolutionPaths":
        from core.infra import paths

        return cls(receipt_log=paths.logs_dir() / "consent_receipts.jsonl")


@dataclass(frozen=True)
class ConsentResolutionRequest:
    utterance: OwnerUtterance
    intent: ConsentIntent | None
    binding_id: str
    card_id: str
    decision: str
    echo_status: str = "ok"
    identity_verified: bool = True


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _append_receipt(path: Path, receipt: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(dict(receipt), sort_keys=True, separators=(",", ":")))
        f.write("\n")


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


def _default_approve_channel(request_id: str, payload: Mapping[str, object]) -> Mapping[str, object]:
    body = json.dumps(dict(payload)).encode("utf-8")
    req = urllib.request.Request(
        f"http://127.0.0.1:11435/internal/approve_card/{request_id}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(raw) if raw else {}
            except Exception:
                parsed = {"raw": raw}
            if not isinstance(parsed, dict):
                parsed = {"value": parsed}
            parsed["http_status"] = int(resp.status)
            return parsed
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw) if raw else {}
        except Exception:
            parsed = {"raw": raw}
        if not isinstance(parsed, dict):
            parsed = {"value": parsed}
        parsed["http_status"] = int(exc.code)
        return parsed
    except Exception as exc:
        return {"ok": False, "http_status": 503, "error": str(exc)}


def _reason_from_upstream(upstream: Mapping[str, object]) -> str:
    values = {
        str(upstream.get("error") or ""),
        str(upstream.get("reason") or ""),
        str(upstream.get("message") or ""),
        str(upstream.get("status") or ""),
    }
    if "s7_authorization_required" in values:
        return "s7_ceremony_required"
    return "upstream_refused"


def _base_receipt(
    request: ConsentResolutionRequest,
    *,
    at: datetime,
    receipt_id: str,
) -> dict[str, object]:
    return {
        "receipt_id": receipt_id,
        "action": "conversational_consent_resolution",
        "binding_id": request.binding_id,
        "card_id": request.card_id,
        "request_id": request.card_id,
        "decision": request.decision,
        "surface_kind": request.utterance.surface_kind,
        "surface_identity": request.utterance.surface_identity,
        "at": at.isoformat(),
    }


def _emit(
    request: ConsentResolutionRequest,
    *,
    paths: ConsentResolutionPaths,
    at: datetime,
    receipt_id: str,
    ok: bool,
    outcome: str,
    reason: str | None = None,
    upstream: Mapping[str, object] | None = None,
    final_card_status: str | None = None,
    channel: str | None = None,
) -> dict[str, object]:
    receipt = _base_receipt(request, at=at, receipt_id=receipt_id)
    receipt.update(
        {
            "ok": ok,
            "outcome": outcome,
            "status": outcome,
            "final_card_status": final_card_status,
        }
    )
    if reason:
        receipt["reason"] = reason
    if upstream is not None:
        receipt["upstream"] = dict(upstream)
    if channel:
        receipt["channel"] = channel
    _append_receipt(paths.receipt_log, receipt)
    return receipt


def resolve_consent_decision(
    request: ConsentResolutionRequest,
    *,
    card_store: PendingCardStore,
    binding_registry: BindingRegistry,
    paths: ConsentResolutionPaths | None = None,
    flag_enabled: bool,
    approve_channel: ApproveChannel | None | object = _DEFAULT_APPROVE_CHANNEL,
    now: Clock = _now_utc,
) -> dict[str, object]:
    paths = paths or ConsentResolutionPaths.defaults()
    at = now()
    if at.tzinfo is None:
        at = at.replace(tzinfo=UTC)
    receipt_id = f"consent-{uuid4().hex}"

    def refused(reason: str, *, final_card_status: str | None = None) -> dict[str, object]:
        return _emit(
            request,
            paths=paths,
            at=at,
            receipt_id=receipt_id,
            ok=False,
            outcome="refused",
            reason=reason,
            final_card_status=final_card_status,
        )

    if not flag_enabled:
        return refused("consent_flag_off")

    binding = binding_registry.get(request.binding_id)
    if binding is None or binding.status != "active":
        return refused("surface_not_bound")
    if (
        binding.surface_kind != request.utterance.surface_kind
        or binding.surface_identity != request.utterance.surface_identity
    ):
        return refused("surface_not_bound")

    if not request.identity_verified:
        return refused("surface_identity_unverifiable")

    card = card_store.get(request.card_id)
    if card is None:
        return refused("card_not_found")
    if card.status not in AWAITING_STATUSES:
        return refused("card_not_awaiting", final_card_status=card.status)

    if request.echo_status == "expired":
        return refused("echo_expired", final_card_status=card.status)
    if request.echo_status == "ambiguous":
        return refused("echo_ambiguous", final_card_status=card.status)
    if not request.utterance.fresh:
        return refused("utterance_not_fresh", final_card_status=card.status)
    if request.intent is None or request.intent.kind not in {"approve", "deny"}:
        return refused("intent_unavailable", final_card_status=card.status)

    if request.decision == "approve":
        if approve_channel is None:
            return refused("approval_channel_unavailable", final_card_status=card.status)
        channel = "existing_approval_channel"
        actual_channel = (
            _default_approve_channel
            if approve_channel is _DEFAULT_APPROVE_CHANNEL
            else approve_channel
        )
        upstream = dict(actual_channel(request.card_id, {"via": "conversational_consent"}))
    elif request.decision == "deny":
        channel = "existing_pending_cards"
        try:
            resolved = card_store.deny(
                request.card_id,
                user_id=binding.surface_identity,
                via="conversational_consent",
                notes="denied by conversational consent",
            )
            upstream = {
                "ok": True,
                "http_status": 200,
                "status": resolved.status,
            }
        except CardStoreError as exc:
            upstream = {
                "ok": False,
                "http_status": 409,
                "status": "conflict",
                "error": str(exc),
            }
    else:
        return refused("intent_unavailable", final_card_status=card.status)

    final_card = card_store.get(request.card_id)
    final_card_status = final_card.status if final_card is not None else None
    http_status = _http_status(upstream)
    http_ok = http_status is not None and 200 <= http_status < 300
    upstream_ok = upstream.get("ok") is True
    resolved = final_card_status is not None and final_card_status not in AWAITING_STATUSES

    if http_ok and upstream_ok and resolved:
        return _emit(
            request,
            paths=paths,
            at=at,
            receipt_id=receipt_id,
            ok=True,
            outcome="resolved",
            upstream=upstream,
            final_card_status=final_card_status,
            channel=channel,
        )

    if http_ok and upstream_ok and not resolved:
        return _emit(
            request,
            paths=paths,
            at=at,
            receipt_id=receipt_id,
            ok=False,
            outcome="unconfirmed",
            reason="upstream_unconfirmed",
            upstream=upstream,
            final_card_status=final_card_status,
            channel=channel,
        )

    return _emit(
        request,
        paths=paths,
        at=at,
        receipt_id=receipt_id,
        ok=False,
        outcome="refused",
        reason=_reason_from_upstream(upstream),
        upstream=upstream,
        final_card_status=final_card_status,
        channel=channel,
    )
