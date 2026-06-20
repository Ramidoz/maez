import os, tempfile, unittest
os.environ.setdefault("MAEZ_IPHONE_INGEST_TOKEN", "dummy-test")
os.environ.setdefault("MAEZ_SECRETS_DISABLE_NEW_LOADER", "1")
from core.routing.observation import RoutingObservationStore

class WriteBackTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.store = RoutingObservationStore(db_path=self.tmp.name)

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
