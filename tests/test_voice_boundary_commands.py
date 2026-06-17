import asyncio
import inspect
import os
import types
import unittest

from core.dispatcher.proposal_commands import parse_show_id


class ParseShowIdTest(unittest.TestCase):
    def test_extracts_show_id_variants(self):
        self.assertEqual(parse_show_id("/show 22"), 22)
        self.assertEqual(parse_show_id("/show #22"), 22)
        self.assertEqual(parse_show_id("/show@maezbot 22"), 22)

    def test_returns_none_without_id(self):
        self.assertIsNone(parse_show_id("/show"))
        self.assertIsNone(parse_show_id("/proposals"))
        self.assertIsNone(parse_show_id("show #22"))


class FakeMaezHandler:
    """Stand in for the live MaezMessageHandler instance C1 reaches."""

    def __init__(self, evo, dream):
        self._evo = evo
        self._dream = dream
        self._last_shown_proposal = {}
        self.show_calls = []

    def _surface_parity_pending_evolution_candidates(self):
        return self._evo

    def _surface_parity_pending_dream_rows(self):
        return self._dream

    def _surface_parity_disambiguation(self, *, pending, dream_rows):
        return f"LISTING evo={len(pending)} dream={len(dream_rows)}"

    async def _try_surface_parity_proposal_intent(self, *, text, chat_id):
        self.show_calls.append((text, chat_id))
        self._last_shown_proposal[chat_id] = {
            "id": 22,
            "source": "evolution",
            "shown_at": 1000.0,
        }
        return f"DETAIL for {text}"


class HandleCommandInterceptTest(unittest.TestCase):
    def test_handle_command_checks_proposals_before_generic_dispatch(self):
        from skills.surface.telegram_adapter import TelegramAdapter

        source = inspect.getsource(TelegramAdapter._handle_command)
        proposal_idx = source.find("_try_command_proposal_surface")
        unwired_idx = source.find("_try_handle_unwired_command_event")
        generic_idx = source.find("await self.handle_message(event)")

        self.assertGreaterEqual(proposal_idx, 0)
        self.assertGreaterEqual(unwired_idx, 0)
        self.assertGreaterEqual(generic_idx, 0)
        self.assertLess(proposal_idx, generic_idx)
        self.assertLess(unwired_idx, generic_idx)

    def setUp(self):
        self._saved_voice = os.environ.get("MAEZ_VOICE_BOUNDARY_ENABLED")
        self._saved_parity = os.environ.get("MAEZ_SURFACE_PARITY_ENABLED")
        os.environ["MAEZ_VOICE_BOUNDARY_ENABLED"] = "1"
        os.environ["MAEZ_SURFACE_PARITY_ENABLED"] = "1"

    def tearDown(self):
        for key, val in (
            ("MAEZ_VOICE_BOUNDARY_ENABLED", self._saved_voice),
            ("MAEZ_SURFACE_PARITY_ENABLED", self._saved_parity),
        ):
            if val is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = val

    def _adapter(self, evo, dream):
        from skills.surface.platform_base import PlatformConfig
        from skills.surface.telegram_adapter import TelegramAdapter

        adapter = TelegramAdapter(
            PlatformConfig(enabled=True, token="x", reply_to_mode="off", extra={})
        )
        adapter._message_handler = FakeMaezHandler(evo, dream)
        sent = []

        async def _fake_send(event, text, **_kwargs):
            sent.append(text)
            return True

        adapter._send_command_reply = _fake_send

        async def _fail_brain(_event):
            raise AssertionError("slash command must NOT call the brain")

        adapter.handle_message = _fail_brain
        return adapter, sent

    def _event(self, text):
        return types.SimpleNamespace(
            text=text,
            source=types.SimpleNamespace(chat_id="c1"),
            message_id=1,
            raw=None,
        )

    def test_proposals_reuses_disambiguation_no_brain(self):
        adapter, sent = self._adapter(
            [{"id": 22, "weakness": "w", "target_file": "x"}],
            [],
        )

        handled = asyncio.run(
            adapter._try_command_proposal_surface(self._event("/proposals"))
        )

        self.assertTrue(handled)
        self.assertIn("LISTING evo=1 dream=0", sent[0])

    def test_proposals_empty_is_honest(self):
        adapter, sent = self._adapter([], [])

        handled = asyncio.run(
            adapter._try_command_proposal_surface(self._event("/proposals"))
        )

        self.assertTrue(handled)
        self.assertIn("no pending proposals", sent[0].lower())

    def test_show_delegates_with_correct_chatid_and_binds(self):
        adapter, sent = self._adapter(
            [{"id": 22, "weakness": "w", "target_file": "x"}],
            [],
        )

        handled = asyncio.run(
            adapter._try_command_proposal_surface(self._event("/show 22"))
        )

        self.assertTrue(handled)
        self.assertEqual(adapter._message_handler.show_calls, [("show #22", "c1")])
        self.assertEqual(
            adapter._message_handler._last_shown_proposal["c1"]["id"],
            22,
        )
        self.assertIn("DETAIL", sent[0])

    def test_show_no_id_usage(self):
        adapter, sent = self._adapter([], [])

        handled = asyncio.run(
            adapter._try_command_proposal_surface(self._event("/show"))
        )

        self.assertTrue(handled)
        self.assertIn("/show <id>", sent[0])

    def test_unrelated_slash_not_handled(self):
        adapter, _sent = self._adapter([], [])

        handled = asyncio.run(
            adapter._try_command_proposal_surface(self._event("/weather"))
        )

        self.assertFalse(handled)

    def test_flag_off_not_handled(self):
        os.environ.pop("MAEZ_VOICE_BOUNDARY_ENABLED", None)
        adapter, _sent = self._adapter(
            [{"id": 22, "weakness": "w", "target_file": "x"}],
            [],
        )

        handled = asyncio.run(
            adapter._try_command_proposal_surface(self._event("/proposals"))
        )

        self.assertFalse(handled)

    def test_unwired_slash_command_is_deterministic_not_brain(self):
        adapter, sent = self._adapter([], [])

        handled = asyncio.run(
            adapter._try_handle_unwired_command_event(self._event("/pending"))
        )

        self.assertTrue(handled)
        self.assertIn("not wired", sent[0].lower())
        self.assertIn("/pending", sent[0])

    def test_unknown_slash_command_is_deterministic_not_brain(self):
        adapter, sent = self._adapter([], [])

        handled = asyncio.run(
            adapter._try_handle_unwired_command_event(self._event("/flarble"))
        )

        self.assertTrue(handled)
        self.assertIn("not wired", sent[0].lower())
        self.assertIn("/flarble", sent[0])

    def test_plain_text_is_not_captured_by_unwired_command_guard(self):
        adapter, _sent = self._adapter([], [])

        handled = asyncio.run(
            adapter._try_handle_unwired_command_event(self._event("show #22"))
        )

        self.assertFalse(handled)


if __name__ == "__main__":
    unittest.main()
