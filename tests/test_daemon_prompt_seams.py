from __future__ import annotations

import unittest
from pathlib import Path

_DAEMON_SRC = Path("daemon/maez_daemon.py").read_text()


class CombinedBlockSeamTests(unittest.TestCase):
    def test_capability_block_built_outside_ambient_brief_gate(self):
        self.assertIn("capability_prompt_block()", _DAEMON_SRC)
        cap_idx = _DAEMON_SRC.index("capability_prompt_block()")
        gate_idx = _DAEMON_SRC.index("MAEZ_AMBIENT_BRIEF", cap_idx - 4000)
        self.assertLess(cap_idx, gate_idx + 8000)
        self.assertIn("_combined_context_block", _DAEMON_SRC)

    def test_append_condition_is_combined_not_ambient_only(self):
        region = _DAEMON_SRC[_DAEMON_SRC.index("_combined_context_block") :][:1500]
        self.assertIn("if _combined_context_block:", region)


class DrainOrderTests(unittest.TestCase):
    def test_detector_runs_after_retain_before_render(self):
        drain = _DAEMON_SRC[_DAEMON_SRC.index("pop_turn_evidence") :]
        retain = drain.index("retain_receipt")
        observe = drain.index("observe_marked_draft")
        render = drain.index("render_natural(")
        self.assertLess(retain, observe)
        self.assertLess(observe, render)


if __name__ == "__main__":
    unittest.main()
