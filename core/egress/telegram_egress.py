from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import secrets
import time
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Literal, Mapping

from core.egress.gate import (
    EgressDecision,
    EgressRequest,
    decide_egress,
    load_or_create_telemetry_key,
)
from core.egress.provenance import ProvenancedText


BotRoute = Literal["owner_private", "voice_owner_private", "public_stranger"]
AudienceClass = Literal["bonded_owner", "public_stranger"]
CONTENT_FREE_MESSAGE_KINDS = frozenset(
    {
        "transport_control",
        "typing",
        "reaction",
        "callback_answer",
        "draft_presence",
    }
)


@dataclass(frozen=True)
class TelegramInteractiveMarkup:
    """Content-aware shape for Telegram inline keyboards and callbacks."""

    labels: tuple[str, ...] = ()
    callback_data_classes: tuple[str, ...] = ()
    button_count: int = 0


@dataclass(frozen=True)
class TelegramEgressEnvelope:
    bot_route: BotRoute
    audience_class: AudienceClass
    chat_id: str
    message_kind: str
    content: ProvenancedText | None
    caption: ProvenancedText | None
    interactive_markup: TelegramInteractiveMarkup | None
    media_ref: str | None
    reply_to: str | None
    source_ref: str
    request_id: str
    metadata: Mapping[str, object] = field(default_factory=dict)
    allow_legacy_shadow_send: bool = False


@dataclass(frozen=True)
class TelegramEgressResult:
    sent: bool
    decision: EgressDecision
    message_id: str | None = None
    reason_codes: tuple[str, ...] = ()
    maez_visible_diagnostic: None = None
    raw_response: Mapping[str, object] = field(default_factory=dict)


def legacy_text_envelope(
    *,
    bot_route: BotRoute,
    audience_class: AudienceClass,
    chat_id: str,
    text: str,
    source_ref: str,
    request_id: str | None = None,
    message_kind: str = "text",
    metadata: Mapping[str, object] | None = None,
    allow_shadow_send: bool = True,
) -> TelegramEgressEnvelope:
    return TelegramEgressEnvelope(
        bot_route=bot_route,
        audience_class=audience_class,
        chat_id=str(chat_id),
        message_kind=message_kind,
        content=ProvenancedText.from_raw_conservative(text, source_ref=source_ref),
        caption=None,
        interactive_markup=None,
        media_ref=None,
        reply_to=None,
        source_ref=source_ref,
        request_id=request_id or _request_id(),
        metadata=metadata or {},
        allow_legacy_shadow_send=allow_shadow_send,
    )


def with_interactive_markup(
    envelope: TelegramEgressEnvelope,
    interactive_markup: TelegramInteractiveMarkup,
) -> TelegramEgressEnvelope:
    return replace(envelope, interactive_markup=interactive_markup)


def owner_text_envelope(
    *,
    bot_route: BotRoute = "owner_private",
    chat_id: str,
    text: str,
    source_ref: str,
    request_id: str | None = None,
    message_kind: str = "text",
    metadata: Mapping[str, object] | None = None,
) -> TelegramEgressEnvelope:
    return TelegramEgressEnvelope(
        bot_route=bot_route,
        audience_class="bonded_owner",
        chat_id=str(chat_id),
        message_kind=message_kind,
        content=ProvenancedText.maez_authored_owner_third_party_transport(
            text,
            source_ref=source_ref,
        ),
        caption=None,
        interactive_markup=None,
        media_ref=None,
        reply_to=None,
        source_ref=source_ref,
        request_id=request_id or _request_id(),
        metadata=metadata or {},
    )


def public_text_envelope(
    *,
    chat_id: str,
    text: str,
    source_ref: str,
    request_id: str | None = None,
    message_kind: str = "text",
    metadata: Mapping[str, object] | None = None,
) -> TelegramEgressEnvelope:
    return TelegramEgressEnvelope(
        bot_route="public_stranger",
        audience_class="public_stranger",
        chat_id=str(chat_id),
        message_kind=message_kind,
        content=ProvenancedText.maez_authored_public_third_party_transport(
            text,
            source_ref=source_ref,
        ),
        caption=None,
        interactive_markup=None,
        media_ref=None,
        reply_to=None,
        source_ref=source_ref,
        request_id=request_id or _request_id(),
        metadata=metadata or {},
    )


def send_telegram(
    *,
    envelope: TelegramEgressEnvelope | object,
    bot: object,
) -> TelegramEgressResult:
    return asyncio.run(send_telegram_async(envelope=envelope, bot=bot))


async def send_telegram_async(
    *,
    envelope: TelegramEgressEnvelope | object,
    bot: object,
) -> TelegramEgressResult:
    if not isinstance(envelope, TelegramEgressEnvelope):
        decision = decide_egress(envelope)
        return TelegramEgressResult(
            sent=False,
            decision=decision,
            reason_codes=decision.reason_codes,
        )

    decision = _decide_envelope(envelope)
    await _write_diagnostic(envelope, decision)
    if decision.decision == "block" and not _legacy_shadow_allowed(envelope, decision):
        return TelegramEgressResult(
            sent=False,
            decision=decision,
            reason_codes=decision.reason_codes,
        )

    if envelope.message_kind in {"transport_control", "typing", "reaction", "callback_answer"}:
        return TelegramEgressResult(
            sent=True,
            decision=decision,
            reason_codes=decision.reason_codes,
        )

    text = decision.sanitized_text()
    if not text:
        text = _content_text(envelope)

    try:
        msg = await bot.send_message(chat_id=int(envelope.chat_id), text=text)
    except TypeError:
        msg = await bot.send_message(chat_id=envelope.chat_id, text=text)
    message_id = getattr(msg, "message_id", None)
    return TelegramEgressResult(
        sent=True,
        decision=decision,
        message_id=str(message_id) if message_id is not None else None,
        reason_codes=decision.reason_codes,
        raw_response={"message_id": message_id} if message_id is not None else {},
    )


async def call_telegram_method_async(
    *,
    envelope: TelegramEgressEnvelope,
    target: object,
    method_name: str,
    kwargs: Mapping[str, Any] | None = None,
) -> Any:
    """Evaluate egress, then call one Telegram library method inside chokepoint.

    Existing producers use many Telegram methods. This helper lets migration
    replace direct library calls without inventing a second transport booth.
    """

    kwargs_dict = dict(kwargs or {})
    envelope = _envelope_with_method_payload(envelope, kwargs_dict)
    decision = _decide_envelope(envelope)
    await _write_diagnostic(envelope, decision)
    if decision.decision == "block" and not _legacy_shadow_allowed(envelope, decision):
        return TelegramEgressResult(
            sent=False,
            decision=decision,
            reason_codes=decision.reason_codes,
        )
    method = getattr(target, method_name)
    return await method(**kwargs_dict)


def _legacy_shadow_allowed(
    envelope: TelegramEgressEnvelope,
    decision: EgressDecision,
) -> bool:
    return (
        envelope.allow_legacy_shadow_send
        and decision.decision == "block"
        and "unclassified" in decision.reason_codes
        and (
            (
                bool(decision.origin_classes)
                and all(origin == "unclassified" for origin in decision.origin_classes)
            )
            or (
                not decision.origin_classes
                and envelope.message_kind in CONTENT_FREE_MESSAGE_KINDS
            )
        )
    )


def _envelope_with_method_payload(
    envelope: TelegramEgressEnvelope,
    kwargs: Mapping[str, Any],
) -> TelegramEgressEnvelope:
    text_value = kwargs.get("text")
    caption_value = kwargs.get("caption")
    if text_value is None and caption_value is None:
        return envelope
    content = envelope.content
    caption = envelope.caption
    if text_value is not None:
        content = _payload_text_with_existing_provenance(
            existing=content,
            text=str(text_value),
            source_ref=envelope.source_ref,
        )
    if caption_value is not None:
        caption = _payload_text_with_existing_provenance(
            existing=caption,
            text=str(caption_value),
            source_ref=f"{envelope.source_ref}:caption",
        )
    return replace(envelope, content=content, caption=caption)


def _payload_text_with_existing_provenance(
    *,
    existing: ProvenancedText | None,
    text: str,
    source_ref: str,
) -> ProvenancedText:
    if existing is not None and existing.spans:
        if existing.text == text:
            return existing
    return ProvenancedText.from_raw_conservative(text, source_ref=source_ref)


def _decide_envelope(envelope: TelegramEgressEnvelope) -> EgressDecision:
    call_class = (
        "owner_third_party_transport_send"
        if envelope.audience_class == "bonded_owner"
        else "public_third_party_transport_send"
    )
    return decide_egress(
        EgressRequest(
            call_class=call_class,
            destination=f"telegram:{envelope.bot_route}:{envelope.audience_class}",
            caller=envelope.source_ref,
            request_id=envelope.request_id,
            segments=_segments(envelope),
        )
    )


def _segments(envelope: TelegramEgressEnvelope):
    segments = []
    if envelope.content is not None:
        segments.extend(envelope.content.to_egress_segments())
    if envelope.caption is not None:
        segments.extend(envelope.caption.to_egress_segments())
    return segments


async def _write_diagnostic(
    envelope: TelegramEgressEnvelope,
    decision: EgressDecision,
) -> None:
    path = _diagnostic_path()
    row = _diagnostic_row(envelope, decision)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    except Exception:
        if decision.decision != "allow":
            raise


def _diagnostic_row(
    envelope: TelegramEgressEnvelope,
    decision: EgressDecision,
) -> dict[str, object]:
    key = load_or_create_telemetry_key()
    content_text = _content_text(envelope)
    content_digest = hmac.new(key, content_text.encode("utf-8"), hashlib.sha256).hexdigest()
    chat_digest = hmac.new(
        key,
        str(envelope.chat_id).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return {
        "schema_version": "telegram-egress-diagnostic-v1",
        "timestamp": time.time(),
        "request_id": envelope.request_id,
        "bot_route": envelope.bot_route,
        "audience_class": envelope.audience_class,
        "chat_id_digest": f"hmac-sha256:{chat_digest}",
        "message_kind": envelope.message_kind,
        "origin_classes": list(decision.origin_classes),
        "decision": decision.decision,
        "reason_codes": list(decision.reason_codes),
        "source_ref": envelope.source_ref,
        "char_count": len(content_text),
        "content_digest": f"hmac-sha256:{content_digest}",
        "interactive_markup": _markup_metadata(envelope.interactive_markup, key),
    }


def _markup_metadata(
    markup: TelegramInteractiveMarkup | None,
    key: bytes,
) -> dict[str, object] | None:
    if markup is None:
        return None
    label_digest = hmac.new(
        key,
        "|".join(markup.labels).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return {
        "button_count": markup.button_count,
        "label_count": len(markup.labels),
        "callback_data_classes": list(markup.callback_data_classes),
        "label_digest": f"hmac-sha256:{label_digest}",
    }


def _content_text(envelope: TelegramEgressEnvelope) -> str:
    parts: list[str] = []
    if envelope.content is not None:
        parts.append(envelope.content.text)
    if envelope.caption is not None:
        parts.append(envelope.caption.text)
    return "".join(parts)


def _diagnostic_path() -> Path:
    override = os.environ.get("MAEZ_TELEGRAM_EGRESS_LOG")
    if override:
        return Path(override)
    try:
        from core.infra import paths as _paths

        return _paths.logs_dir() / "telegram_egress_diagnostics.jsonl"
    except Exception:
        return Path(__file__).resolve().parents[2] / "logs" / "telegram_egress_diagnostics.jsonl"


def _request_id() -> str:
    return f"tg-{int(time.time() * 1000)}-{secrets.token_hex(4)}"
