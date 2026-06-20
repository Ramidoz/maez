import unittest
from unittest import mock
import daemon.maez_daemon as d
from daemon.maez_daemon import _build_cycle_focused_prompt

# The focused-cognition packet is gated by MAEZ_CYCLE_FOCUSED_ENABLED (default OFF;
# the live autonomous path turns it on). The injection tests exercise that built path,
# so enable the gate exactly as tests/test_cycle_packet.py does.
_FOCUSED_ON = {"MAEZ_CYCLE_FOCUSED_ENABLED": "1"}


class FeedLineBuilder(unittest.TestCase):
    def test_builds_perception_line_from_context(self):
        ctx = {"felt_value": 7.65, "felt_phrase": "a long quiet stretch",
               "felt_compute_version": 1, "seconds_since_last_owner_contact": 3 * 3600 + 12 * 60}
        line = d._format_time_sense_line(ctx)
        self.assertIn("3h 12m", line)
        self.assertIn("a long quiet stretch", line)
        self.assertTrue(line.startswith("Time:"))

    def test_line_is_perception_not_directive(self):
        ctx = {"felt_value": 9.0, "felt_phrase": "a long quiet stretch",
               "felt_compute_version": 1, "seconds_since_last_owner_contact": 36000}
        line = d._format_time_sense_line(ctx).lower()
        for imperative in ("should", "reach out", "you must", "go ", "send", "remind"):
            self.assertNotIn(imperative, line)   # states what IS, never what to DO


class FeedPromptInjection(unittest.TestCase):
    def test_prepends_perception_block_when_line_present(self):
        with mock.patch.dict("os.environ", _FOCUSED_ON):
            dec = _build_cycle_focused_prompt(
                legacy_prompt="LEGACY", candidates=[],
                time_sense_line="Time: ~3h 12m since the last owner contact. Felt: a long quiet stretch.",
            )
        self.assertIn("TIME SENSE", dec.prompt)
        self.assertIn("3h 12m", dec.prompt)
        # perception block sits BEFORE the evidence block
        self.assertLess(dec.prompt.index("TIME SENSE"), dec.prompt.index("CYCLE EVIDENCE"))

    def test_no_block_when_line_empty(self):
        with mock.patch.dict("os.environ", _FOCUSED_ON):
            dec = _build_cycle_focused_prompt(legacy_prompt="LEGACY", candidates=[], time_sense_line="")
        self.assertNotIn("TIME SENSE", dec.prompt)

    def test_cycle_packet_module_has_no_felt_time(self):
        # cycle_packet.py stays PURE — felt-time is wired in the daemon, not the packet builder.
        import inspect, core.cognition.cycle_packet as cp
        src = inspect.getsource(cp).lower()
        for token in ("felt_time", "felt time", "time_sense", "subjective_duration", "time sense"):
            self.assertNotIn(token, src)
