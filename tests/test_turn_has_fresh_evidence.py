import os, unittest
os.environ.setdefault("MAEZ_IPHONE_INGEST_TOKEN", "dummy-test")
os.environ.setdefault("MAEZ_SECRETS_DISABLE_NEW_LOADER", "1")
from types import SimpleNamespace
from core.routing.focused_cognition import turn_has_fresh_evidence

def _ws(*source_types):
    return SimpleNamespace(items=[SimpleNamespace(source_type=s) for s in source_types])

class TurnHasFreshEvidenceTest(unittest.TestCase):
    def test_web_context_is_fresh(self):
        self.assertTrue(turn_has_fresh_evidence(_ws("web_context")))
    def test_fresh_evidence_is_fresh(self):
        self.assertTrue(turn_has_fresh_evidence(_ws("fresh_evidence")))
    def test_recall_only_is_not_fresh(self):
        self.assertFalse(turn_has_fresh_evidence(_ws("memory_evidence", "memory_context")))
    def test_mixed_recall_and_web_is_fresh(self):
        self.assertTrue(turn_has_fresh_evidence(_ws("memory_context", "web_context")))
    def test_empty_is_not_fresh(self):
        self.assertFalse(turn_has_fresh_evidence(_ws()))
    def test_none_working_set_is_not_fresh(self):
        self.assertFalse(turn_has_fresh_evidence(None))
