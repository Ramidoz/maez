from __future__ import annotations

import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PRODUCTION_ROOTS = ("skills", "daemon", "core")
APPROVED_DIRECT_SEND_FILES = {
    "core/egress/telegram_egress.py",
}
APPROVED_LEGACY_FACTORY_FILES = {
    "core/egress/telegram_egress.py",
}
RAW_SYNC_SEND_SCAN_ROOTS = (
    "daemon/maez_daemon.py",
    "core/actions/action_engine.py",
    "core/evolution/dream_state.py",
)
TELEGRAM_ADAPTER_MEDIA_FALLBACK_METHODS = {
    "send_image",
    "send_animation",
    "send_voice",
    "send_video",
    "send_document",
    "send_image_file",
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


def _literal_string(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _is_getattr_call(node: ast.AST, attr_name: str) -> bool:
    if not isinstance(node, ast.Call):
        return False
    if _receiver_name(node.func) != "getattr":
        return False
    if len(node.args) < 2:
        return False
    return _literal_string(node.args[1]) == attr_name


def _sync_telegram_aliases(tree: ast.AST) -> set[str]:
    aliases: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        value = node.value
        if value is None:
            continue
        receiver = _receiver_name(value)
        if receiver.endswith(".telegram") or _is_getattr_call(value, "telegram"):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name):
                    aliases.add(target.id)
    return aliases


def _is_sync_telegram_object(node: ast.AST, aliases: set[str]) -> bool:
    receiver = _receiver_name(node)
    if isinstance(node, ast.Name) and node.id in aliases:
        return True
    if receiver.endswith(".telegram"):
        return True
    if _is_getattr_call(node, "telegram"):
        return True
    return False


def _is_raw_sync_send_message_call(call: ast.Call, aliases: set[str] | None = None) -> bool:
    aliases = aliases or set()
    func = call.func
    if isinstance(func, ast.Attribute) and func.attr == "send_message":
        return _is_sync_telegram_object(func.value, aliases)
    if _is_getattr_call(func, "send_message"):
        return bool(func.args) and _is_sync_telegram_object(func.args[0], aliases)
    return False


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


def _find_legacy_text_envelope_calls() -> list[str]:
    hits: list[str] = []
    for root_name in PRODUCTION_ROOTS:
        for path in (ROOT / root_name).rglob("*.py"):
            rel = path.relative_to(ROOT).as_posix()
            if rel in APPROVED_LEGACY_FACTORY_FILES or _is_test_path(path):
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and _receiver_name(node.func) == "legacy_text_envelope":
                    hits.append(f"{rel}:{node.lineno}:legacy_text_envelope")
    return sorted(hits)


def _find_legacy_shadow_kwarg_paths() -> list[str]:
    hits = _find_legacy_text_envelope_calls()
    for root_name in PRODUCTION_ROOTS:
        for path in (ROOT / root_name).rglob("*.py"):
            rel = path.relative_to(ROOT).as_posix()
            if rel in APPROVED_LEGACY_FACTORY_FILES or _is_test_path(path):
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.keyword):
                    continue
                if node.arg not in {"allow_shadow_send", "allow_legacy_shadow_send"}:
                    continue
                if isinstance(node.value, ast.Constant) and node.value.value is True:
                    hits.append(f"{rel}:{node.lineno}:{node.arg}=True")
    return sorted(set(hits))


def _find_raw_sync_send_message_calls() -> list[str]:
    hits: list[str] = []
    for rel in RAW_SYNC_SEND_SCAN_ROOTS:
        path = ROOT / rel
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        aliases = _sync_telegram_aliases(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and _is_raw_sync_send_message_call(node, aliases):
                hits.append(f"{rel}:{node.lineno}:{_receiver_name(node.func)}")
    return sorted(hits)


def _find_telegram_adapter_super_media_fallbacks() -> list[str]:
    path = ROOT / "skills/surface/telegram_adapter.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    hits: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr not in TELEGRAM_ADAPTER_MEDIA_FALLBACK_METHODS:
            continue
        if _receiver_name(node.func.value) == "super":
            hits.append(f"skills/surface/telegram_adapter.py:{node.lineno}:super().{node.func.attr}")
    return sorted(hits)


class TelegramBypassInventoryTests(unittest.TestCase):
    def test_no_production_legacy_text_envelope_outside_chokepoint(self):
        self.assertEqual(_find_legacy_text_envelope_calls(), [])

    def test_no_production_legacy_shadow_send_paths(self):
        self.assertEqual(_find_legacy_shadow_kwarg_paths(), [])

    def test_no_raw_sync_send_message_calls_in_production_producers(self):
        self.assertEqual(_find_raw_sync_send_message_calls(), [])

    def test_sync_send_inventory_catches_direct_alias_and_getattr_patterns(self):
        tree = ast.parse(
            """
def f(self):
    self.telegram.send_message("direct")
    tg = self.telegram
    tg.send_message("alias")
    getattr(self.telegram, "send_message")("getattr-method")
    getattr(self, "telegram").send_message("getattr-object")
"""
        )
        aliases = _sync_telegram_aliases(tree)
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
        detected = [
            _receiver_name(call.func)
            for call in calls
            if _is_raw_sync_send_message_call(call, aliases)
        ]

        self.assertEqual(
            detected,
            [
                "self.telegram.send_message",
                "tg.send_message",
                "getattr",
                "getattr.send_message",
            ],
        )

    def test_telegram_adapter_media_paths_do_not_fallback_to_base_raw_sends(self):
        self.assertEqual(_find_telegram_adapter_super_media_fallbacks(), [])

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

    def test_allowlist_marks_telegram_and_action_fetch_shadow_states(self):
        text = ROOT.joinpath(
            "docs/slices/privacy-egress-gate/network_migration_allowlist.yaml"
        ).read_text(encoding="utf-8")

        self.assertIn("surface: telegram", text)
        self.assertIn("status: producer_threaded_shadow", text)
        action_entry = text.split("surface: action_engine_external_fetch", 1)[1]
        self.assertIn("status: substrate_shadow", action_entry)


if __name__ == "__main__":
    unittest.main()
