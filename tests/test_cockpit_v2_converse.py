import os
from pathlib import Path
from unittest import mock
import unittest


os.environ.setdefault("MAEZ_IPHONE_INGEST_TOKEN", "dummy-test")
os.environ.setdefault("MAEZ_SECRETS_DISABLE_NEW_LOADER", "1")


def _make_urlopen_response(payload: bytes, *, status: int = 200, content_type: str = "application/json"):
    class _Response:
        def __init__(self):
            self.status = status
            self.headers = {"Content-Type": content_type}

        def read(self):
            return payload

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    return _Response()


def _extract_function(source: str, name: str, *, end_marker: str) -> str:
    start = source.index(f"function {name}")
    end = source.index(end_marker, start)
    return source[start:end]


class CockpitV2ConverseTests(unittest.TestCase):
    def test_message_proxy_still_uses_existing_owner_private_s7_channel(self):
        import skills.web_interface as wi

        wi.app.config["TESTING"] = True
        client = wi.app.test_client()
        captured = {}

        def fake_urlopen(req, timeout=None):
            captured["url"] = req.full_url
            captured["s7"] = req.get_header("X-maez-s7-internal-channel")
            captured["owner"] = req.get_header("X-maez-owner-authenticated")
            captured["body"] = req.data
            return _make_urlopen_response(b'{"reply":"ok"}')

        with mock.patch.object(wi, "_owner_private_auth_ok", return_value=True), \
            mock.patch.object(wi, "_request_has_web_owner_cookie", return_value=True), \
            mock.patch.dict(os.environ, {"S7_INTERNAL_CHANNEL_TOKEN": "tok-123"}, clear=False), \
            mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            response = client.post(
                "/api/v1/cockpit/message",
                json={"text": "hello", "source": "cockpit", "history": []},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(captured["url"], "http://127.0.0.1:11435/message")
        self.assertEqual(captured["s7"], "tok-123")
        self.assertEqual(captured["owner"], "1")
        self.assertIn(b'"source": "cockpit"', captured["body"])
        response.close()

    def test_converse_ui_does_not_create_second_chat_authority(self):
        ui = Path("web/cockpit/v2/terminal-ui.jsx").read_text()
        chatpane = _extract_function(ui, "ChatPane", end_marker="function ThinkingBlock")

        self.assertIn("/api/v1/cockpit/message", chatpane)
        self.assertNotIn("/api/v2/cockpit/message", chatpane)
        self.assertNotIn("127.0.0.1:11435", chatpane)
        self.assertNotIn("fetch('/message", chatpane)

    def test_show_why_uses_latest_turn_and_receipts_without_duplicate_audit_path(self):
        index = Path("web/cockpit/v2/index.html").read_text()
        why = _extract_function(index, "WhyReplyPane", end_marker="function WhyBlock")

        self.assertIn("/api/v1/turn/latest", why)
        self.assertIn("sim.state.cockpitV2?.receiptsRoom", why)
        self.assertIn("receipt context", why)
        self.assertIn("fabrication event receipts", why)
        self.assertIn("corrected_before_send", why)
        self.assertIn("held_with_floor_notice", why)
        self.assertNotIn("self_claim_audit", why)
        self.assertNotIn("audit_assistant_text", why)
        self.assertNotIn("fabrication_log.db", why)

    def test_converse_task_does_not_edit_prompt_or_voice_sources(self):
        index = Path("web/cockpit/v2/index.html").read_text()
        why = _extract_function(index, "WhyReplyPane", end_marker="function WhyBlock")
        ui = Path("web/cockpit/v2/terminal-ui.jsx").read_text()
        chatpane = _extract_function(ui, "ChatPane", end_marker="function ThinkingBlock")
        forbidden = (
            "config/soul",
            "core/voice",
            "voice_card",
            "assemble_self_card",
            "system prompt",
            "system_part",
        )
        for name, text in {"WhyReplyPane": why.lower(), "ChatPane": chatpane.lower()}.items():
            for needle in forbidden:
                self.assertNotIn(needle, text, f"{needle!r} leaked into {name}")


if __name__ == "__main__":
    unittest.main()
