import os, tempfile, unittest
os.environ.setdefault("MAEZ_IPHONE_INGEST_TOKEN", "dummy-test")
os.environ.setdefault("MAEZ_SECRETS_DISABLE_NEW_LOADER", "1")
from core.routing.observation import RoutingObservationStore

class WriteBackTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.store = RoutingObservationStore(db_path=self.tmp.name)

    def tearDown(self):
        self.tmp.close()
        try:
            os.unlink(self.tmp.name)
        except OSError:
            pass

    def _row(self):
        return self.store.record_legacy_web_search_observation(
            user_text="summarize today's signals", surface="cockpit", chat_id=None,
            chosen_tool="web_search", execution_status="success", evidence_block_count=3,
            outcome_quality="structured_evidence")

    def test_attach_overwrites_outcome_quality_by_id(self):
        rid = self._row()
        self.store.attach_post_turn_quality(rid, outcome_quality="unusable",
                                            post_turn_signal="support_gate_caveated:4")
        row = self.store.get(rid)
        self.assertEqual(row["outcome_quality"], "unusable")
        self.assertEqual(row["post_turn_signal"], "support_gate_caveated:4")

    def test_attach_unknown_id_is_silent_noop(self):
        self.store.attach_post_turn_quality("nope", outcome_quality="unusable", post_turn_signal="x")

    def test_quality_mapping_marks_caveated_unusable(self):
        from daemon.maez_daemon import _routing_quality_from_gate
        q, sig = _routing_quality_from_gate(caveated_unsupported=4, web_quality="adequate", result_count=3)
        self.assertEqual(q, "unusable"); self.assertIn("caveated", sig)

    def test_quality_mapping_thin_nonempty_search_unusable(self):
        from daemon.maez_daemon import _routing_quality_from_gate
        q, sig = _routing_quality_from_gate(caveated_unsupported=0, web_quality="thin", result_count=2)
        self.assertEqual(q, "unusable"); self.assertIn("thin", sig)

    def test_adequate_search_no_caveats_stays_good(self):
        from daemon.maez_daemon import _routing_quality_from_gate
        q, _ = _routing_quality_from_gate(caveated_unsupported=0, web_quality="adequate", result_count=3)
        self.assertIsNone(q)

    def test_empty_search_preserves_empty_but_honest(self):
        from daemon.maez_daemon import _routing_quality_from_gate
        q, _ = _routing_quality_from_gate(caveated_unsupported=0, web_quality="thin", result_count=0)
        self.assertIsNone(q)
