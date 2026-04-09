"""
dev_notifier.py — Sends operational notifications to Maez Dev bot.
Keeps Maez private bot clean for conversation only.

Outbound only. No inbound handlers.

Provides:
- send_dev(text)              — short raw messages
- send_proposal_card(...)     — compact self-edit proposal card
- send_nightly_card(...)      — compact nightly summary card
- send_service_card(...)      — compact service alert/recovery card
"""
import os
import requests
import logging

logger = logging.getLogger("maez")

_USEFULNESS_BADGE = {
    'strong':     '\u2705 strong',
    'acceptable': '\u26a0\ufe0f acceptable',
    'weak':       '\u274c weak',
    'unknown':    '\u26aa unknown',
}


def send_dev(text: str):
    """Send a message to the Maez Dev Telegram bot."""
    token = os.getenv('MAEZ_DEV_TOKEN')
    user_id = os.getenv('MAEZ_TELEGRAM_USER_ID')
    if not token or not user_id:
        logger.warning("MAEZ_DEV_TOKEN not set — dev notification dropped")
        return
    try:
        requests.post(
            f'https://api.telegram.org/bot{token}/sendMessage',
            json={'chat_id': user_id, 'text': text},
            timeout=10,
        )
    except Exception as e:
        logger.error("Dev notification failed: %s", e)


def _truncate(s: str, n: int) -> str:
    if not s:
        return ''
    s = str(s).strip().replace('\n', ' ')
    return s[:n] + ('\u2026' if len(s) > n else '')


def send_proposal_card(candidate_id, weakness, target, before, after,
                       usefulness, rationale):
    """Compact self-edit proposal card. Max 8 lines."""
    badge = _USEFULNESS_BADGE.get(usefulness, usefulness or '?')
    lines = [
        "\U0001f9e0 Self-edit proposal",
        "",
        f"Weakness: {_truncate(weakness, 100)}",
        f"Target: {target}  {before!r} \u2192 {after!r}",
        f"Why: {_truncate(rationale, 100)}",
        f"Confidence: {badge}",
        "",
        f"/show {candidate_id} \u00b7 /apply {candidate_id} \u00b7 /reject {candidate_id}",
    ]
    send_dev('\n'.join(lines))


def send_nightly_card(memories_analyzed, unique_insight_rate, top_topics,
                      proposals_attempted, proposals_failed, autonomy_promotions=None):
    """Compact nightly summary card. Max 8 lines."""
    topics_str = ', '.join(f"{t} ({n})" for t, n in (top_topics or [])[:3])
    lines = [
        "\U0001f319 Nightly summary",
        "",
        f"Memories: {memories_analyzed} analyzed \u00b7 {unique_insight_rate:.0f}% unique insight rate",
        f"Top topics: {topics_str or 'none'}",
        f"Evolution: {proposals_attempted} attempted \u00b7 {proposals_failed} failed validation",
    ]
    if autonomy_promotions:
        promotions = ', '.join(autonomy_promotions) if isinstance(autonomy_promotions, (list, tuple)) else str(autonomy_promotions)
        lines.append(f"\U0001f53c Autonomy earned: {promotions}")
    send_dev('\n'.join(lines))


def send_service_card(service_name, event, details=None):
    """Compact service alert/recovery card. Max 8 lines."""
    is_recovery = any(k in event.lower() for k in ('back', 'recover', 'online', 'restored'))
    header = "\u2705 Service recovery" if is_recovery else "\u26a0\ufe0f Service alert"
    lines = [header, "", f"{service_name}: {_truncate(event, 100)}"]
    if details:
        lines.append(_truncate(str(details), 200))
    send_dev('\n'.join(lines))
