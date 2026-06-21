import os, unittest
from types import SimpleNamespace
from unittest import mock
os.environ.setdefault("MAEZ_IPHONE_INGEST_TOKEN", "dummy-test")
os.environ.setdefault("MAEZ_SECRETS_DISABLE_NEW_LOADER", "1")
import daemon.maez_daemon as d

def _ws(*types):
    return SimpleNamespace(items=[SimpleNamespace(source_type=t) for t in types])

class SupportScopeBehaviorTest(unittest.TestCase):
    def test_recall_only_never_invokes_minicheck_reply_unchanged(self):
        with mock.patch("core.cognition.grounding_shadow.observe_focused_support_gate") as g, \
             mock.patch("core.cognition.grounding_shadow.observe_focused_support") as s, \
             self.assertLogs(d.logger.name, level="INFO") as logs:
            reply, receipt = d._run_support_scope(
                "good morning, the rig is humming", _ws("memory_context", "memory_evidence"),
                {"E1": "x"}, surface="telegram_surface", boot_id=None, shadow_id="sid", ts=0)
        g.assert_not_called(); s.assert_not_called()
        self.assertEqual(reply, "good morning, the rig is humming")
        self.assertIsNone(receipt)
        self.assertTrue(any("support_gate_scope" in m and "skipped_recall_only" in m for m in logs.output))

    def test_fresh_web_convenes_the_gate(self):
        os.environ["MAEZ_SUPPORT_GATE_ENABLED"] = "1"
        try:
            with mock.patch("core.cognition.grounding_shadow.observe_focused_support_gate",
                            return_value=("gated reply", {"caveated_unsupported": 0})) as g, \
                 self.assertLogs(d.logger.name, level="INFO") as logs:
                reply, receipt = d._run_support_scope(
                    "Anthropic shipped X [E1]", _ws("web_context"), {"E1": "x"},
                    surface="cockpit", boot_id=None, shadow_id="sid", ts=0)
            g.assert_called_once()
            self.assertEqual(reply, "gated reply")
            self.assertTrue(any("support_gate_scope" in m and "path=gated" in m for m in logs.output))
        finally:
            os.environ.pop("MAEZ_SUPPORT_GATE_ENABLED", None)
