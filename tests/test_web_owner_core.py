from __future__ import annotations

import json
import os
import sys
import unittest
from unittest import mock


def _make_urlopen_response(body: bytes, status: int = 200):
    cm = mock.MagicMock()
    response = mock.MagicMock()
    response.read.return_value = body
    response.status = status
    response.headers = {"Content-Type": "application/json"}
    cm.__enter__.return_value = response
    cm.__exit__.return_value = False
    return cm


class WebOwnerCoreProxyTests(unittest.TestCase):
    def _web_interface(self):
        sys.modules.pop("skills.web_interface", None)
        with (
            mock.patch.dict(
                os.environ,
                {"MAEZ_IPHONE_INGEST_TOKEN": "test-token"},
                clear=False,
            ),
            mock.patch("core.infra.secrets.load_ordinary_config_for_process"),
            mock.patch("core.infra.secrets.load_secrets_for_process"),
        ):
            from skills import web_interface as wi

        return wi

    def test_proxy_posts_owner_surface_to_daemon_message(self):
        wi = self._web_interface()

        captured = {}

        def fake_urlopen(req, timeout=None):
            captured["url"] = req.full_url
            captured["data"] = json.loads(req.data.decode("utf-8"))
            captured["method"] = req.get_method()
            captured["timeout"] = timeout
            return _make_urlopen_response(json.dumps({"reply": "from daemon"}).encode())

        with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            reply = wi._proxy_web_owner_message_to_daemon(
                message="hello from maez.live",
                history=[{"role": "user", "content": "prior"}],
            )

        self.assertEqual(reply, {"reply": "from daemon"})
        self.assertEqual(captured["url"], "http://127.0.0.1:11435/message")
        self.assertEqual(captured["method"], "POST")
        self.assertEqual(captured["data"]["text"], "hello from maez.live")
        self.assertEqual(captured["data"]["surface"], "web_owner")
        self.assertEqual(captured["data"]["history"], [{"role": "user", "content": "prior"}])
        self.assertGreaterEqual(captured["timeout"], 60.0)

    def test_web_owner_core_flag_is_strict(self):
        wi = self._web_interface()

        for off in ("0", "false", "no", "off", "", "garbage"):
            with self.subTest(off=off), mock.patch.dict(
                "os.environ", {"MAEZ_WEB_OWNER_CORE": off}
            ):
                self.assertFalse(wi.web_owner_core_enabled())
        with mock.patch.dict("os.environ", {}, clear=False):
            import os

            os.environ.pop("MAEZ_WEB_OWNER_CORE", None)
            self.assertFalse(wi.web_owner_core_enabled())
        for on in ("1", "true", "yes", "on", "ON"):
            with self.subTest(on=on), mock.patch.dict(
                "os.environ", {"MAEZ_WEB_OWNER_CORE": on}
            ):
                self.assertTrue(wi.web_owner_core_enabled())

    def test_owner_chat_flag_on_returns_daemon_reply(self):
        wi = self._web_interface()
        client = wi.app.test_client()

        with (
            mock.patch.dict("os.environ", {"MAEZ_WEB_OWNER_CORE": "1"}),
            mock.patch.object(wi.accounts, "get_by_token", return_value={"uuid": "owner", "display_name": "Rohit"}),
            mock.patch.object(
                wi.accounts,
                "get_user_record",
                return_value={"private_owner_bridge": True},
            ),
            mock.patch(
                "core.evolution.subjective_duration.SubjectiveDuration.record_salience_event"
            ),
            mock.patch.object(
                wi,
                "_proxy_web_owner_message_to_daemon",
                return_value={"reply": "daemon-body reply"},
            ) as proxy,
        ):
            response = client.post(
                "/chat",
                json={
                    "web_token": "tok",
                    "message": "hello from the owner web bridge",
                    "history": [{"role": "user", "content": "prior"}],
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["reply"], "daemon-body reply")
        proxy.assert_called_once_with(
            message="hello from the owner web bridge",
            history=[{"role": "user", "content": "prior"}],
        )


class DaemonWebOwnerDescriptorTests(unittest.TestCase):
    def test_web_owner_descriptor_uses_owner_surface_not_cockpit(self):
        from daemon.maez_daemon import _build_web_owner_inbound_descriptor

        daemon = mock.Mock()
        descriptor = _build_web_owner_inbound_descriptor(
            daemon,
            text="hello",
            chat_history=[{"content": "Rohit: hi\nMaez: hello"}],
        )

        self.assertEqual(descriptor["owner_surface_label"], "web_owner")
        self.assertEqual(descriptor["chat_id"], "web_owner")
        self.assertEqual(descriptor["channel"], "web_owner_bridge")
        self.assertEqual(descriptor["observe_turn_label"], "web_owner_turn")
        self.assertIsNone(descriptor["get_pipeline"])
        self.assertIsNone(descriptor["action_engine"])

    def test_web_owner_surface_disabled_does_not_fall_through_to_cockpit(self):
        from daemon.maez_daemon import _select_message_inbound_descriptor

        with mock.patch.dict(
            os.environ,
            {"MAEZ_COCKPIT_CORE": "1", "MAEZ_WEB_OWNER_CORE": "0"},
        ):
            descriptor, error = _select_message_inbound_descriptor(
                mock.Mock(),
                text="hello from maez.live",
                chat_history=None,
                surface_hint="web_owner",
            )

        self.assertIsNone(descriptor)
        self.assertEqual(error, "web_owner_core_disabled")

    def test_message_descriptor_selector_routes_each_enabled_surface(self):
        from daemon.maez_daemon import _select_message_inbound_descriptor

        with mock.patch.dict(
            os.environ,
            {"MAEZ_COCKPIT_CORE": "1", "MAEZ_WEB_OWNER_CORE": "1"},
        ):
            web_descriptor, web_error = _select_message_inbound_descriptor(
                mock.Mock(),
                text="hello from maez.live",
                chat_history=None,
                surface_hint="web_owner",
            )
            cockpit_descriptor, cockpit_error = _select_message_inbound_descriptor(
                mock.Mock(),
                text="hello from cockpit",
                chat_history=None,
                surface_hint="cockpit",
            )

        self.assertIsNone(web_error)
        self.assertEqual(web_descriptor["owner_surface_label"], "web_owner")
        self.assertIsNone(cockpit_error)
        self.assertEqual(cockpit_descriptor["owner_surface_label"], "cockpit")
