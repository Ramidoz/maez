# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Runtime ground-truth provider tests.

The provider is best-effort and read-only: every probe returns a fact
with source/provenance, and failures become ok=False facts instead of
exceptions. These tests mock external calls so they do not depend on
the local machine's systemd/GPU/model state.
"""
from __future__ import annotations

import io
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


class CurrentModelProbe(unittest.TestCase):
    def test_current_model_reads_first_model_id(self):
        from core.turn_traces import ground_truth as gt

        payload = json.dumps({"data": [{"id": "qwen36-27b"}]}).encode()

        class _Resp(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

        with mock.patch("urllib.request.urlopen", return_value=_Resp(payload)):
            fact = gt.current_model(url="http://example.test/v1/models")

        self.assertTrue(fact.ok)
        self.assertEqual(fact.value, "qwen36-27b")
        self.assertEqual(fact.source, "http://example.test/v1/models")

    def test_current_model_failure_is_fact_not_exception(self):
        from core.turn_traces import ground_truth as gt

        with mock.patch("urllib.request.urlopen", side_effect=OSError("no server")):
            fact = gt.current_model(url="http://example.test/v1/models")

        self.assertFalse(fact.ok)
        self.assertEqual(fact.value, "")
        self.assertIn("no server", fact.detail)


class ServiceAndHardwareProbes(unittest.TestCase):
    def test_service_active_maps_active_stdout_to_true(self):
        from core.turn_traces import ground_truth as gt

        with mock.patch.object(gt, "_run", return_value=(0, "active", "")):
            fact = gt.service_active("maez.service")

        self.assertTrue(fact.ok)
        self.assertTrue(fact.value)
        self.assertIn("systemctl is-active maez.service", fact.source)

    def test_service_inactive_is_known_false(self):
        from core.turn_traces import ground_truth as gt

        with mock.patch.object(gt, "_run", return_value=(3, "inactive", "")):
            fact = gt.service_active("llama-judge.service")

        self.assertTrue(fact.ok)
        self.assertFalse(fact.value)
        self.assertEqual(fact.detail, "inactive")

    def test_vram_snapshot_parses_nvidia_smi_csv(self):
        from core.turn_traces import ground_truth as gt

        with mock.patch.object(gt, "_run", return_value=(0, "21100, 24576, 55", "")):
            fact = gt.vram_snapshot()

        self.assertTrue(fact.ok)
        self.assertEqual(fact.value["memory_used_mb"], 21100)
        self.assertEqual(fact.value["memory_total_mb"], 24576)
        self.assertEqual(fact.value["temperature_c"], 55)

    def test_feature_flags_are_sourced_from_environment(self):
        from core.turn_traces import ground_truth as gt

        with mock.patch.dict("os.environ", {"MAEZ_WEB_TOOL_LOOP": "1"}, clear=True):
            fact = gt.feature_flags(["MAEZ_WEB_TOOL_LOOP", "MAEZ_SCREEN_PERCEPTION"])

        self.assertTrue(fact.ok)
        self.assertEqual(fact.value["MAEZ_WEB_TOOL_LOOP"], "1")
        self.assertEqual(fact.value["MAEZ_SCREEN_PERCEPTION"], "")


if __name__ == "__main__":
    unittest.main()
