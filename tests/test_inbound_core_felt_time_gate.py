import inspect
import unittest
from daemon import inbound_core


class RunInboundTurnFeltTimeGate(unittest.TestCase):
    def test_signature_has_felt_time_enabled_default_false(self):
        sig = inspect.signature(inbound_core.run_inbound_turn)
        self.assertIn("felt_time_enabled", sig.parameters)
        self.assertEqual(sig.parameters["felt_time_enabled"].default, False)

    def test_gate_source_honors_felt_time_enabled(self):
        src = inspect.getsource(inbound_core.run_inbound_turn)
        self.assertIn("surface_parity_enabled() or felt_time_enabled", src)


if __name__ == "__main__":
    unittest.main()
