# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Chat-history → messages[] conversion — 2026-04-24 gap closure.

The incident: on 2026-04-24 04:42 Maez answered an owner question about
`stanford-iris-lab/meta-harness` (grounded via web_search tool, real
repo with 622 stars). At 04:53 the owner asked "You think it'll be
useful for you? How will it make you better in layman's terms" — and
Maez replied "I don't know what 'it' refers to. Our last exchange was
about my general capabilities."

Root cause: `daemon.handle_message` built its synthesis request with
only `[system, user]` in the messages array — no prior-turn context.
Memory recall ran against the new text ("you think it'll be useful")
but had zero semantic overlap with "meta-harness", so recall did not
surface the 04:42 turn. The "AMBIGUOUS REFERENT RULE" prompt fired on
a context that genuinely had no referent. The adapter already pulls
the last 3 exchanges for tool-planning in brain_loop; it wasn't
threading them into synthesis.

This helper parses the adapter-cleaned exchange format
(`"Rohit: <user>\\nMaez: <reply>"`) into a list of alternating
user/assistant messages that can be inserted between the system
prompt and the current turn."""
from __future__ import annotations

from typing import Iterable


_USER_PREFIX = "Rohit:"
_ASSISTANT_MARKER = "\nMaez:"


def _split_exchange(content: str) -> tuple[str, str] | None:
    """Return (user_msg, assistant_reply) for a cleaned exchange, or
    None if the shape doesn't match. Rejects legacy envelope entries
    by requiring both the "Rohit:" prefix and a "\\nMaez:" delimiter.
    Either field empty → reject (no point polluting messages[] with
    empty turns)."""
    if not content:
        return None
    if not content.startswith(_USER_PREFIX):
        return None
    pos = content.find(_ASSISTANT_MARKER)
    if pos <= 0:
        return None
    user_msg = content[len(_USER_PREFIX):pos].strip()
    assistant_msg = content[pos + len(_ASSISTANT_MARKER):].strip()
    if not user_msg or not assistant_msg:
        return None
    return user_msg, assistant_msg


def history_to_messages(
    chat_history: Iterable[dict] | None,
) -> list[dict]:
    """Turn adapter chat-history entries into llm_client messages[]
    pairs. Oldest first, newest last — matches conversational order.

    Each input entry is a dict with a `"content"` field in the shape
    `"Rohit: <user_text>\\nMaez: <reply_text>"` (as produced by
    `skills.surface.maez_adapter._clean_exchange`). Other fields are
    ignored. Entries that don't match the shape (legacy envelope,
    empty, None) are silently skipped rather than flooding the
    synthesis prompt with unparseable noise."""
    if not chat_history:
        return []
    out: list[dict] = []
    for entry in chat_history:
        if not isinstance(entry, dict):
            continue
        pair = _split_exchange(entry.get("content") or "")
        if pair is None:
            continue
        user_msg, assistant_msg = pair
        out.append({"role": "user", "content": user_msg})
        out.append({"role": "assistant", "content": assistant_msg})
    return out
