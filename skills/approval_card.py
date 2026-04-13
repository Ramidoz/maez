r"""
Maez Approval Card — Session 11z Part 2, Step 9c.

Transport-agnostic approval card object + renderer(s). Today the only
renderer is TelegramTextRenderer, which posts the card as a Telegram
message and watches the chat for reactions / text replies to resolve
it. A future VoiceRenderer (desk mic + speaker or Telegram voice
message) will slot in at the same interface without changing the
card core, the pending store, or the reply classifier.

The card itself is just a CardRecord from core.pending_cards. The
renderer handles presentation; the reply classifier handles intent;
the pending store handles state. Every layer stays ignorant of the
others' internals so we can swap pieces out independently.

This module provides:

    format_card_text(card) -> str
        Pure function that formats a CardRecord as Telegram-flavored
        Markdown. Unit-testable. No I/O.

    TelegramTextRenderer(send_fn, edit_fn=None, react_fn=None)
        Constructed with plain callables so it never imports a specific
        Telegram library. Tests inject fakes; production wires up
        skills.telegram_voice helpers.

    format_resolution_text(card) -> str
        Formats the outcome notice after a card has been approved/
        denied/executed. Sent as a reply-to-message to keep the thread
        tidy.

    format_reminder_text(card) -> str
        Formats the "you asked me to check back about this" reminder
        when a deferred card's remind_at fires.
"""

from __future__ import annotations

import json
import textwrap
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional, Protocol

from core.pending_cards import CardRecord, CardStatus


# ------------------------------------------------------------------ #
#  Pure formatters                                                     #
# ------------------------------------------------------------------ #

# Emoji header by audit decision
_DECISION_HEADER = {
    "APPROVE":            "🟢 Ready to run — your call",
    "APPROVE_WITH_CARD":  "🟡 Action pending your approval",
    "ESCALATE":           "🔴 Heavy scrutiny — needs your attention",
    "DENY":               "⛔ Blocked by audit",
}

_MAX_CMD_DISPLAY   = 600
_MAX_REASONING     = 400
_MAX_CONCERN       = 150
_MAX_CONCERN_ITEMS = 4


def _truncate(s: str, limit: int) -> str:
    if s is None:
        return ""
    s = str(s)
    return s if len(s) <= limit else s[: limit - 1] + "…"


def _render_cmd_line(card: CardRecord) -> str:
    """Extract a displayable command string from the card's params."""
    params = card.params or {}
    # run_shell shape
    if "cmd" in params:
        return _truncate(str(params["cmd"]), _MAX_CMD_DISPLAY)
    # write_any_file shape
    if "path" in params:
        content = params.get("content", "")
        content_preview = _truncate(str(content), 200).replace("\n", "\\n")
        return f"write {params['path']}: {content_preview}"
    # Fallback: best-effort JSON
    return _truncate(json.dumps(params, default=str), _MAX_CMD_DISPLAY)


def _format_concerns(card: CardRecord) -> str:
    concerns = card.audit_concerns or []
    if not concerns:
        return ""
    shown = concerns[:_MAX_CONCERN_ITEMS]
    lines = [f"• {_truncate(str(c), _MAX_CONCERN)}" for c in shown]
    if len(concerns) > _MAX_CONCERN_ITEMS:
        lines.append(f"• (+{len(concerns) - _MAX_CONCERN_ITEMS} more)")
    return "\n".join(lines)


def _format_mitigations(card: CardRecord) -> str:
    mit = card.audit_mitigations or []
    if not mit:
        return ""
    shown = mit[:_MAX_CONCERN_ITEMS]
    return "\n".join(f"• {_truncate(str(m), _MAX_CONCERN)}" for m in shown)


def format_card_text(card: CardRecord) -> str:
    """Format a pending card as Telegram-flavored Markdown.

    Intentionally plain text with a small amount of formatting —
    Telegram's Markdown is fragile around backticks and special
    characters, so we keep it simple and readable.
    """
    header = _DECISION_HEADER.get(card.audit_decision or "APPROVE_WITH_CARD", "🟡 Action pending your approval")

    cmd = _render_cmd_line(card)
    reasoning = _truncate(card.audit_reasoning or "(no reasoning from audit)", _MAX_REASONING)
    concerns = _format_concerns(card)
    mitigations = _format_mitigations(card)

    lines = [
        header,
        "",
        "*What I want to run:*",
        "```",
        cmd,
        "```",
    ]
    if card.reason:
        lines += ["", f"*Why:* {_truncate(card.reason, 200)}"]
    lines += ["", "*Audit says:*", reasoning]
    if concerns:
        lines += ["", "*Concerns:*", concerns]
    if mitigations:
        lines += ["", "*Mitigations:*", mitigations]
    lines += [
        "",
        "_React 👍 to approve, 👎 to deny, 🤔 for more detail,_",
        "_or reply in your own words — \"wait an hour\", \"change it to X\"._",
    ]
    return "\n".join(lines)


def format_reminder_text(card: CardRecord) -> str:
    """Formatted re-presentation when a deferred card's reminder fires."""
    cmd = _render_cmd_line(card)
    ago = int(time.time() - card.created_at)
    hrs = ago // 3600
    mins = (ago % 3600) // 60
    if hrs > 0:
        ago_str = f"{hrs}h {mins}m ago"
    else:
        ago_str = f"{mins}m ago"

    reason = f" — you said: \"{_truncate(card.defer_reason or '', 80)}\"" if card.defer_reason else ""
    header = f"⏰ Checking back on an earlier request ({ago_str}){reason}"

    return (
        f"{header}\n\n"
        f"*What I still want to run:*\n"
        f"```\n{cmd}\n```\n\n"
        f"Still want me to do it? Same options — 👍 👎 🤔, or reply."
    )


def format_resolution_text(card: CardRecord) -> str:
    """Formatted outcome notice after a card resolves. Sent as a reply
    to the original card message so it threads cleanly."""
    if card.status == CardStatus.DONE.value:
        out = _truncate(card.execution_output or "", 400)
        return f"✅ Done.\n```\n{out}\n```" if out else "✅ Done."
    if card.status == CardStatus.FAILED.value:
        err = _truncate(card.execution_error or "(no error)", 400)
        return f"⚠️ Failed.\n```\n{err}\n```"
    if card.status == CardStatus.DENIED.value:
        note = f" ({card.resolution_notes})" if card.resolution_notes else ""
        return f"🛑 Not running this{note}."
    if card.status == CardStatus.EXPIRED.value:
        note = card.resolution_notes or "state changed since the card was created"
        return (
            f"⏹️ Card expired — {note}.\n"
            f"If you still want this, ask again and I'll re-run the audit against the current state."
        )
    if card.status == CardStatus.APPROVED.value:
        return "✅ Approved. Running now."
    if card.status == CardStatus.RUNNING.value:
        return "⏳ Running…"
    if card.status == CardStatus.DEFERRED.value:
        if card.remind_at:
            in_s = int(card.remind_at - time.time())
            if in_s >= 3600:
                when = f"in {in_s // 3600}h {(in_s % 3600) // 60}m"
            elif in_s >= 60:
                when = f"in {in_s // 60}m"
            else:
                when = "shortly"
            return f"⏸️ Deferred — I'll check back {when}."
        return "⏸️ Deferred — I'll hold it until you bring it up."
    return f"(status: {card.status})"


# ------------------------------------------------------------------ #
#  Renderer protocol                                                   #
# ------------------------------------------------------------------ #

class CardRenderer(Protocol):
    """Transport-agnostic interface every renderer must satisfy."""

    def present(self, card: CardRecord) -> Optional[str]:
        """Post the card to its channel. Return a channel_message_id
        string that the pending-cards store can later use to look up
        the card when a reply/reaction arrives."""
        ...

    def re_present(self, card: CardRecord) -> Optional[str]:
        """Re-post a deferred card after its reminder fires. May return
        a new channel_message_id if the renderer posts a fresh message."""
        ...

    def send_resolution(self, card: CardRecord) -> None:
        """Post the outcome notice, threaded to the original card if the
        channel supports threading."""
        ...


# ------------------------------------------------------------------ #
#  Telegram text renderer                                              #
# ------------------------------------------------------------------ #

@dataclass
class TelegramTextRenderer:
    """Renders cards to a Telegram chat as text messages.

    Constructed with plain callables so this module never imports the
    Telegram library directly. Production wires these up to
    skills/telegram_voice.py; tests inject fakes.

    send_message_fn signature:
        (chat_id: str, text: str, reply_to: Optional[str] = None) -> str
        returns the posted message_id (as string)
    """

    chat_id: str
    send_message_fn: Callable[..., str]
    edit_message_fn: Optional[Callable[..., None]] = None

    def present(self, card: CardRecord) -> Optional[str]:
        text = format_card_text(card)
        try:
            msg_id = self.send_message_fn(self.chat_id, text)
            return str(msg_id) if msg_id is not None else None
        except Exception as e:
            return None

    def re_present(self, card: CardRecord) -> Optional[str]:
        text = format_reminder_text(card)
        try:
            reply_to = card.channel_message_id
            msg_id = self.send_message_fn(self.chat_id, text, reply_to=reply_to)
            return str(msg_id) if msg_id is not None else None
        except Exception:
            return None

    def send_resolution(self, card: CardRecord) -> None:
        text = format_resolution_text(card)
        try:
            reply_to = card.channel_message_id
            self.send_message_fn(self.chat_id, text, reply_to=reply_to)
        except Exception:
            pass


# ------------------------------------------------------------------ #
#  Self-test                                                           #
# ------------------------------------------------------------------ #

if __name__ == "__main__":
    print("=== approval_card self-test ===\n")

    # Build a CardRecord by hand (no sqlite dependency in this test)
    now = time.time()
    card = CardRecord(
        request_id="test_abc",
        created_at=now - 600,
        updated_at=now,
        status="open",
        action="run_shell",
        params={"cmd": "sudo apt install cowsay", "reason": "fun"},
        reason="fun",
        audit_decision="APPROVE_WITH_CARD",
        audit_confidence=0.88,
        audit_reasoning="Standard apt install from a trusted Debian repo. Reversible via apt remove. No covenant paths touched.",
        audit_concerns=["modifies system packages", "requires sudo"],
        audit_mitigations=["apt remove cowsay will undo it"],
        audit_summary="installs cowsay via apt",
        audit_answers={},
        intent_category="SYSTEM_MODIFICATION",
        lane="lane_2",
        state_hash="deadbeef",
        channel="telegram_text",
        chat_id="chat_1",
        user_id="rohit",
    )

    # Format card
    text = format_card_text(card)
    print("-- card text --")
    print(text)
    print()
    assert "sudo apt install cowsay" in text
    assert "modifies system packages" in text
    assert "🟡" in text
    assert "👍" in text and "👎" in text
    print("  ✓ card text contains cmd, concerns, decision emoji, reactions hint")

    # Format reminder
    card.defer_reason = "wait an hour"
    reminder = format_reminder_text(card)
    print("-- reminder text --")
    print(reminder)
    print()
    assert "Checking back" in reminder
    assert "wait an hour" in reminder
    assert "sudo apt install cowsay" in reminder
    print("  ✓ reminder text contains defer reason + cmd")

    # Resolution: done
    card.status = "done"
    card.execution_output = "Reading package lists...\nE: cowsay already installed"
    res = format_resolution_text(card)
    print("-- resolution (done) --")
    print(res)
    print()
    assert "✅ Done" in res
    assert "already installed" in res
    print("  ✓ done resolution")

    # Resolution: failed
    card.status = "failed"
    card.execution_error = "apt: lock file in use"
    res = format_resolution_text(card)
    assert "⚠️ Failed" in res
    print(f"  ✓ failed resolution")

    # Resolution: denied
    card.status = "denied"
    card.resolution_notes = "changed my mind"
    res = format_resolution_text(card)
    assert "🛑 Not running" in res
    assert "changed my mind" in res
    print(f"  ✓ denied resolution")

    # Resolution: expired
    card.status = "expired"
    card.resolution_notes = "state hash changed"
    res = format_resolution_text(card)
    assert "expired" in res
    assert "re-run the audit" in res
    print(f"  ✓ expired resolution")

    # Resolution: deferred with future reminder
    card.status = "deferred"
    card.remind_at = time.time() + 3700
    res = format_resolution_text(card)
    assert "Deferred" in res
    assert ("1h" in res or "61m" in res)
    print(f"  ✓ deferred resolution with reminder")

    # --- Renderer ---
    sent = []

    def fake_send(chat_id, text, reply_to=None):
        msg_id = f"msg_{len(sent)+1}"
        sent.append({"chat_id": chat_id, "text": text, "reply_to": reply_to, "id": msg_id})
        return msg_id

    renderer = TelegramTextRenderer(chat_id="chat_1", send_message_fn=fake_send)

    # Reset card to open to test present
    card.status = "open"
    card.remind_at = None
    msg_id = renderer.present(card)
    assert msg_id == "msg_1"
    assert "sudo apt install cowsay" in sent[-1]["text"]
    assert sent[-1]["reply_to"] is None
    print(f"  ✓ renderer.present → msg_id={msg_id}")

    # Record the channel message id as the store would
    card.channel_message_id = msg_id

    # Defer + re-present
    card.status = "deferred"
    card.defer_reason = "busy right now"
    card.remind_at = time.time() - 10  # due
    msg_id2 = renderer.re_present(card)
    assert msg_id2 == "msg_2"
    assert sent[-1]["reply_to"] == "msg_1"  # threaded to original
    assert "Checking back" in sent[-1]["text"]
    print(f"  ✓ renderer.re_present threads to original msg")

    # Resolution notice
    card.status = "done"
    card.execution_output = "installed successfully"
    renderer.send_resolution(card)
    assert sent[-1]["reply_to"] == "msg_1"
    assert "✅" in sent[-1]["text"]
    print(f"  ✓ renderer.send_resolution threads to original msg")

    print(f"\n{len(sent)} Telegram messages sent during test")
    print("=== approval_card self-test complete ===")
