import os, tempfile, unittest
os.environ.setdefault("MAEZ_IPHONE_INGEST_TOKEN", "dummy-test")
os.environ.setdefault("MAEZ_SECRETS_DISABLE_NEW_LOADER", "1")
from core.routing.veto_ledger import VetoLedger, classify_outcome

class VetoLedgerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.led = VetoLedger(db_path=self.tmp.name)
    def tearDown(self):
        self.tmp.close()
        try: os.unlink(self.tmp.name)
        except OSError: pass

    def _veto(self, t=1000.0):
        return self.led.record_veto(class_id="SIG", tool="web_search",
            prior_n=5, prior_success_rate=0.0, prior_confidence=0.625,
            turn_id="t1", surface="cockpit", now=t)

    def test_classify_outcome_mapping(self):
        self.assertEqual(classify_outcome("structured_evidence"), "likely_wrong")
        self.assertEqual(classify_outcome("unusable"), "likely_right")
        self.assertEqual(classify_outcome("empty_but_honest"), "likely_right")
        self.assertEqual(classify_outcome("tool_error"), "ambiguous")

    def test_record_then_find_open_within_window(self):
        self._veto(1000.0)
        e = self.led.find_open_for_class("SIG", "web_search", now=1100.0)
        self.assertIsNotNone(e); self.assertEqual(e.class_id, "SIG"); self.assertIsNone(e.classification)

    def test_reask_outcome_classifies_likely_wrong(self):
        self._veto(1000.0)
        e = self.led.find_open_for_class("SIG", "web_search", now=1100.0)
        cls = self.led.attach_reask_outcome(e.id, reask_turn_id="t2", reask_outcome_quality="structured_evidence")
        self.assertEqual(cls, "likely_wrong")
        self.assertIsNone(self.led.find_open_for_class("SIG", "web_search", now=1200.0))

    def test_no_reask_past_window_is_uncontested_lazily(self):
        self._veto(1000.0)
        self.assertIsNone(self.led.find_open_for_class("SIG", "web_search", now=1000.0 + 4000))
        rows = self.led.all_events()
        self.assertEqual(rows[0].classification, "uncontested")
