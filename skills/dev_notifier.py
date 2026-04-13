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

# Session 11x: plain-English usefulness labels shown to the owner, instead of
# raw rubric words. the owner doesn't care whether the proposal is 2/3 or 3/3
# on some internal rubric — he wants to know whether Maez is confident or
# cautious about the change it wants to make.
_HUMAN_USEFULNESS_LABEL = {
    'strong':     "\u2705 I'm confident this helps",
    'acceptable': "\u26a0\ufe0f I think this helps, but I'm less sure",
    'weak':       "\u274c not confident, probably skip this",
    'unknown':    "\u26aa I don't have enough evidence to be sure",
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
                       usefulness, rationale, human_rationale=None):
    """Compact self-edit proposal card in plain English.

    Session 11x rewrite: uses the generator's `human_rationale` (first-person
    Maez voice, no jargon) as the primary message, shows the exact before /
    after value change as a footnote rather than the headline, and replaces
    the slash-command hint with a plain-language "reply yes / no / tell me
    more" prompt. If human_rationale is missing the caller should have
    filled it in via _enrich_intent's template fallback — but we still
    guard here and fall back to the technical rationale as last resort.
    """
    label = _HUMAN_USEFULNESS_LABEL.get(usefulness, _USEFULNESS_BADGE.get(usefulness, usefulness or '?'))

    # Pick the primary message. Prefer human_rationale; fall back to
    # the technical rationale; then to the weakness text itself.
    message = (human_rationale or '').strip()
    if not message:
        message = (rationale or '').strip()
    if not message:
        message = _truncate(weakness or 'A change I want to make.', 200)

    # Compact "what exactly is changing" footnote — the raw before/after.
    # Kept short and visually de-emphasized. This is the only place in
    # the card where the owner sees the internal variable name, and it's
    # labeled as "the technical bit" so he knows he can ignore it.
    try:
        before_repr = repr(before)
        after_repr = repr(after)
    except Exception:
        before_repr = str(before)
        after_repr = str(after)
    change_line = f"(the technical bit: {target} {before_repr} \u2192 {after_repr})"

    lines = [
        "\U0001f331 Maez wants to adjust itself",
        "",
        message,
        "",
        label,
        "",
        change_line,
        "",
        f"Reply \"yes\" to let me try it, \"no\" to skip, or \"tell me more about #{candidate_id}\" for the full details.",
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
