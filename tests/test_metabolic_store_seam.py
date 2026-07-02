import unittest
from unittest import mock

from core.memory.metabolic import CycleEvents


class StoreSeamTests(unittest.TestCase):
    def _daemon_stub(self):
        daemon = mock.Mock()
        daemon._glance_buffer = mock.Mock()
        daemon.memory = mock.Mock()
        daemon.cycle_count = 42
        return daemon

    def test_flag_off_stores_exactly_as_today(self):
        from daemon.maez_daemon import MaezDaemon

        daemon = self._daemon_stub()
        with mock.patch.dict("os.environ", {"MAEZ_METABOLIC_MEMORY": "0"}):
            outcome = MaezDaemon._metabolic_store_cycle_thought(
                daemon,
                "thought",
                {"time_of_day": "x"},
                {"m": 1},
                CycleEvents(),
            )
        self.assertEqual(outcome, "durable")
        daemon.memory.store.assert_called_once()
        kwargs = daemon.memory.store.call_args.kwargs
        self.assertEqual(kwargs["cycle"], 42)
        self.assertEqual(kwargs["snapshot"], {"time_of_day": "x"})
        self.assertEqual(kwargs["metadata"], {"m": 1})
        self.assertEqual(kwargs["provenance_source"], "introspection")
        self.assertEqual(kwargs["trust_tier"], "lived")
        self.assertNotIn("metabolic_durable_reason", kwargs.get("metadata", {}))
        daemon._glance_buffer.append.assert_not_called()

    def test_flag_on_quiet_goes_to_buffer(self):
        from daemon.maez_daemon import MaezDaemon

        daemon = self._daemon_stub()
        with mock.patch.dict("os.environ", {"MAEZ_METABOLIC_MEMORY": "1"}):
            outcome = MaezDaemon._metabolic_store_cycle_thought(
                daemon,
                "quiet glance",
                {},
                {},
                CycleEvents(),
            )
        self.assertEqual(outcome, "ephemeral")
        daemon.memory.store.assert_not_called()
        daemon._glance_buffer.append.assert_called_once()
        kwargs = daemon._glance_buffer.append.call_args.kwargs
        self.assertEqual(kwargs["text"], "quiet glance")
        self.assertEqual(kwargs["cycle"], 42)

    def test_flag_on_triggered_is_durable_with_reason_and_tier(self):
        from daemon.maez_daemon import MaezDaemon

        daemon = self._daemon_stub()
        with mock.patch.dict("os.environ", {"MAEZ_METABOLIC_MEMORY": "1"}):
            outcome = MaezDaemon._metabolic_store_cycle_thought(
                daemon,
                "owner spoke",
                {},
                {},
                CycleEvents(owner_interaction=True),
            )
        self.assertEqual(outcome, "durable")
        daemon.memory.store.assert_called_once()
        kwargs = daemon.memory.store.call_args.kwargs
        self.assertEqual(
            kwargs["metadata"]["metabolic_durable_reason"],
            "owner_interaction",
        )
        self.assertNotEqual(kwargs.get("trust_tier"), "lived")
        self.assertIn(kwargs.get("trust_tier"), (None, "self_observed"))
        daemon._glance_buffer.append.assert_not_called()

    def test_daemon_init_creates_glance_buffer(self):
        from core.memory.metabolic import GlanceBuffer
        from daemon.maez_daemon import MaezDaemon

        with mock.patch("daemon.maez_daemon.MemoryManager"):
            daemon = MaezDaemon()
        self.assertIsInstance(daemon._glance_buffer, GlanceBuffer)
