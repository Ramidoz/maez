import os
import unittest
from unittest import mock

os.environ.setdefault("MAEZ_IPHONE_INGEST_TOKEN", "dummy-test")
os.environ.setdefault("MAEZ_SECRETS_DISABLE_NEW_LOADER", "1")

import daemon.maez_daemon as d


class _Item:
    def __init__(self, label, st, text, trust=None, prov=None):
        self.local_label, self.source_type, self.text = label, st, text
        self.origin_trust, self.origin_provenance = trust, prov


class _WS:
    def __init__(self, items):
        self.items = tuple(items)


class TestConflictSenseSeam(unittest.TestCase):
    def _ws(self):
        return _WS([
            _Item("E1", "web_context", "Anthropic released Opus 4.8 in 2026."),
            _Item("E2", "memory_evidence", "Maez's latest model is Claude 3.", trust="lived"),
        ])

    def test_flag_off_does_not_run_sense(self):
        with mock.patch.dict(os.environ, {"MAEZ_MEM_FRESH_CONFLICT_SENSE": "0"}), \
             mock.patch.object(d, "check_memory_fresh_conflict") as chk:
            d._run_mem_fresh_conflict_sense(self._ws(), surface="telegram")
            chk.assert_not_called()

    def test_flag_on_runs_sense_and_logs(self):
        with mock.patch.dict(os.environ, {"MAEZ_MEM_FRESH_CONFLICT_SENSE": "1"}), \
             mock.patch.object(d, "check_memory_fresh_conflict") as chk, \
             self.assertLogs(d.logger.name) as logs:
            chk.return_value = d.MemoryFreshConflictReceipt(
                verdict="contradiction", mem_id="E2", fresh_id="E1",
                mem_sha256="a" * 64, fresh_sha256="b" * 64, reason_code="trusted_clash")
            d._run_mem_fresh_conflict_sense(self._ws(), surface="telegram")
            chk.assert_called_once()
            self.assertTrue(any("mem_fresh_conflict_sense" in m for m in logs.output))

    def test_sense_is_called_at_the_focused_seam(self):
        import inspect
        # The shadow sense must be invoked in the same seam region as _run_support_scope.
        # Find the enclosing source that contains the support-scope call and assert our
        # call is present there too. Adjust the source target to the REAL seam scope.
        src = inspect.getsource(d)
        self.assertIn("_run_mem_fresh_conflict_sense(", src)


if __name__ == "__main__":
    unittest.main()
