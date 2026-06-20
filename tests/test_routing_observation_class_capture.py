import os, tempfile, unittest
os.environ.setdefault("MAEZ_IPHONE_INGEST_TOKEN", "dummy-test")
os.environ.setdefault("MAEZ_SECRETS_DISABLE_NEW_LOADER", "1")
from core.routing.observation import RoutingObservationStore

class ClassCaptureTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.store = RoutingObservationStore(db_path=self.tmp.name)

    def test_class_fields_persist_when_provided(self):
        rid = self.store.record_legacy_web_search_observation(
            user_text="summarize today's signals", surface="cockpit", chat_id=None,
            chosen_tool="web_search", execution_status="success", evidence_block_count=3,
            outcome_quality="structured_evidence",
            request_class_id="B_EXPLICIT_LIVE_FETCH", request_class_score=0.71,
            request_class_version="archetypes-v0")
        row = self.store.get(rid)
        self.assertEqual(row["request_class_id"], "B_EXPLICIT_LIVE_FETCH")
        self.assertEqual(row["request_class_version"], "archetypes-v0")

    def test_class_fields_default_null(self):
        rid = self.store.record_legacy_web_search_observation(
            user_text="x", surface="cockpit", chat_id=None, chosen_tool="web_search",
            execution_status="success", evidence_block_count=0, outcome_quality="empty_but_honest")
        self.assertIsNone(self.store.get(rid)["request_class_id"])
