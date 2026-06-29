import unittest
from pathlib import Path
from unittest import mock


REPO = Path(__file__).resolve().parent.parent


class SharedIdentityReplyTests(unittest.TestCase):
    def test_identity_question_matches_prefaced_owner_turn(self):
        from core.routing.identity_reply import is_identity_question

        self.assertTrue(
            is_identity_question("Yeah comfortable. Let's talk about you. Who are you?")
        )
        self.assertTrue(is_identity_question("tell me about yourself"))
        self.assertFalse(is_identity_question("who are you hiring?"))

    def test_identity_reply_is_body_truth_aware_and_not_prompt_text(self):
        from core.infra import body_capabilities as bc
        from core.routing.identity_reply import render_identity_reply

        fake_snap = {
            "env": {
                "DISPLAY": ":1",
                "XAUTHORITY": "/run/user/1000/gdm/Xauthority",
                "DBUS_SESSION_BUS_ADDRESS": None,
                "WAYLAND_DISPLAY": None,
            },
            "services": {"brain_8080": True},
            "desktop_session_reachable": False,
        }
        with mock.patch.object(bc, "body_capabilities", return_value=fake_snap):
            reply = render_identity_reply(display="Rohit", linked_user=True)

        self.assertIn("I'm Maez", reply)
        self.assertIn("memory", reply.lower())
        lowered = reply.lower()
        self.assertNotIn("trust covenant", lowered)
        self.assertNotIn("hard constraints", lowered)
        self.assertNotIn("system-prompt", lowered)
        self.assertNotIn("system prompt", lowered)
        self.assertNotIn("desktop", lowered)
        self.assertNotIn("vision", lowered)
        self.assertNotIn("world", lowered)

    def test_web_and_daemon_use_shared_identity_organ(self):
        web_src = (REPO / "skills" / "web_interface.py").read_text()
        daemon_src = (REPO / "daemon" / "maez_daemon.py").read_text()

        self.assertNotIn("def _render_identity_reply", web_src)
        self.assertIn("core.routing.identity_reply", web_src)
        self.assertIn("core.routing.identity_reply", daemon_src)
        self.assertIn("is_identity_question", daemon_src)
        self.assertIn("render_identity_reply", daemon_src)


if __name__ == "__main__":
    unittest.main()
