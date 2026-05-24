from __future__ import annotations

import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PRODUCTION_ROOTS = ("skills", "daemon", "core")
APPROVED_DIRECT_SEND_FILES = {
    "core/egress/telegram_egress.py",
}

TELEGRAM_METHODS = {
    "send_message",
    "reply_text",
    "send_voice",
    "send_audio",
    "send_photo",
    "send_document",
    "send_video",
    "send_animation",
    "edit_message_text",
    "send_chat_action",
    "send_message_draft",
    "answer",
    "set_message_reaction",
}


def _is_test_path(path: Path) -> bool:
    rel = path.relative_to(ROOT).as_posix()
    return rel.startswith("tests/")


def _receiver_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_receiver_name(node.value)}.{node.attr}".strip(".")
    if isinstance(node, ast.Call):
        return _receiver_name(node.func)
    return type(node).__name__


def _telegram_aliases(tree: ast.AST) -> set[str]:
    aliases: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        value = node.value
        if not isinstance(value, ast.Call):
            continue
        if _receiver_name(value.func).endswith("Bot"):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name):
                    aliases.add(target.id)
    return aliases


def _is_telegram_send_call(call: ast.Call, telegram_aliases: set[str] | None = None) -> bool:
    func = call.func
    telegram_aliases = telegram_aliases or set()
    if not isinstance(func, ast.Attribute):
        return False
    method = func.attr
    if method not in TELEGRAM_METHODS:
        return False
    receiver = _receiver_name(func.value)
    if method == "answer":
        return receiver.endswith("query") or receiver.endswith("callback_query")
    if method == "reply_text":
        return receiver.endswith("message") or ".message" in receiver
    if method in {"send_message", "send_voice", "send_audio", "send_photo", "send_document", "send_video", "send_animation", "send_chat_action", "send_message_draft", "set_message_reaction"}:
        if receiver in {"self", "super", "self.telegram"}:
            return False
        return (
            receiver in {"bot", "self._bot", "context.bot"}
            or receiver in telegram_aliases
            or receiver.endswith(".bot")
            or receiver.endswith("Bot")
            or "bot" in receiver.lower()
        )
    if method == "edit_message_text":
        return (
            receiver in {"bot", "self._bot", "query"}
            or receiver in telegram_aliases
            or receiver.endswith(".bot")
            or receiver.endswith("query")
        )
    return False


def _find_direct_telegram_calls() -> list[str]:
    hits: list[str] = []
    for root_name in PRODUCTION_ROOTS:
        for path in (ROOT / root_name).rglob("*.py"):
            rel = path.relative_to(ROOT).as_posix()
            if rel in APPROVED_DIRECT_SEND_FILES or _is_test_path(path):
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            aliases = _telegram_aliases(tree)
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and _is_telegram_send_call(node, aliases):
                    func = node.func
                    assert isinstance(func, ast.Attribute)
                    receiver = _receiver_name(func.value)
                    hits.append(f"{rel}:{node.lineno}:{receiver}.{func.attr}")
    return sorted(hits)


class TelegramBypassInventoryTests(unittest.TestCase):
    def test_no_direct_telegram_send_calls_outside_chokepoint(self):
        hits = _find_direct_telegram_calls()

        self.assertEqual(hits, [])

    def test_inventory_catches_text_and_no_arg_callback_answers(self):
        tree = ast.parse(
            """
async def f(query):
    await query.answer(text="Picker expired")
    await query.answer()
"""
        )
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]

        self.assertEqual([_is_telegram_send_call(call) for call in calls], [True, True])

    def test_inventory_catches_aliased_bot_method_receivers(self):
        tree = ast.parse(
            """
async def f(telegram_bot, owner_bot):
    await telegram_bot.send_message(text="x")
    await owner_bot.send_photo(photo="x")
"""
        )
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]

        self.assertEqual([_is_telegram_send_call(call) for call in calls], [True, True])

    def test_inventory_catches_bot_constructor_alias_without_bot_name(self):
        tree = ast.parse(
            """
async def f(Bot):
    client = Bot(token="x")
    await client.send_message(text="x")
"""
        )
        aliases = _telegram_aliases(tree)
        calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "send_message"
        ]

        self.assertEqual(aliases, {"client"})
        self.assertEqual([_is_telegram_send_call(call, aliases) for call in calls], [True])

    def test_inventory_does_not_classify_screen_perception_false_positive(self):
        hits = [
            hit
            for hit in _find_direct_telegram_calls()
            if hit.startswith("skills/screen_perception.py:")
        ]

        self.assertEqual(hits, [])

    def test_telegram_adapter_send_image_has_no_direct_url_download_fallback(self):
        source = ROOT.joinpath("skills/surface/telegram_adapter.py").read_text(
            encoding="utf-8"
        )
        tree = ast.parse(source)
        send_image = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "send_image"
        )
        offenders: list[str] = []
        for node in ast.walk(send_image):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in {"httpx", "requests"}:
                        offenders.append(f"import {alias.name}")
            if isinstance(node, ast.ImportFrom) and node.module in {"httpx", "requests"}:
                offenders.append(f"from {node.module} import")
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                receiver = _receiver_name(node.func.value)
                if receiver.endswith("client") and node.func.attr.lower() == "get":
                    offenders.append(f"{receiver}.get")

        self.assertEqual(offenders, [])

    def test_telegram_draft_presence_does_not_call_getattr_send_draft_directly(self):
        source = ROOT.joinpath("skills/surface/telegram_adapter.py").read_text(
            encoding="utf-8"
        )

        self.assertNotIn("send_draft(**kwargs)", source)

    def test_allowlist_marks_telegram_chokepoint_without_migrating_action_fetch(self):
        text = ROOT.joinpath(
            "docs/slices/privacy-egress-gate/network_migration_allowlist.yaml"
        ).read_text(encoding="utf-8")

        self.assertIn("surface: telegram", text)
        self.assertIn("status: chokepoint_shadow", text)
        action_entry = text.split("surface: action_engine_external_fetch", 1)[1]
        self.assertIn("status: unmigrated", action_entry)


if __name__ == "__main__":
    unittest.main()
