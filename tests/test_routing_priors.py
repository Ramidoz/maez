import os, tempfile, unittest
os.environ.setdefault("MAEZ_IPHONE_INGEST_TOKEN", "dummy-test")
os.environ.setdefault("MAEZ_SECRETS_DISABLE_NEW_LOADER", "1")
from core.routing.observation import RoutingObservationStore
from core.routing.observation.priors import learn_priors, RoutingPrior

class PriorsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.store = RoutingObservationStore(db_path=self.tmp.name)

    def _obs(self, q):
        return self.store.record_legacy_web_search_observation(
            user_text="t", surface="cockpit", chat_id=None, chosen_tool="web_search",
            execution_status="success", evidence_block_count=2, outcome_quality=q,
            request_class_id="SIGNALS", request_class_score=0.7, request_class_version="v0")

    def test_cold_start_low_confidence(self):
        self._obs("unusable")
        priors = learn_priors(self.store, min_observations=3)
        p = priors.get(("SIGNALS", "web_search"))
        self.assertTrue(p is None or p.confidence == 0.0)

    def test_learns_bad_prior_after_enough_unusable(self):
        for _ in range(5): self._obs("unusable")
        priors = learn_priors(self.store, min_observations=3)
        p = priors[("SIGNALS", "web_search")]
        self.assertIsInstance(p, RoutingPrior)
        self.assertLess(p.success_rate, 0.5)
        self.assertGreater(p.confidence, 0.0)
        self.assertEqual(p.n, 5)

    def test_good_outcomes_high_prior(self):
        for _ in range(5): self._obs("structured_evidence")
        p = learn_priors(self.store, min_observations=3)[("SIGNALS", "web_search")]
        self.assertGreater(p.success_rate, 0.5)

    def test_rows_without_class_are_excluded(self):
        # a row with NULL request_class_id must NOT appear in priors (forward-only)
        self.store.record_legacy_web_search_observation(
            user_text="x", surface="cockpit", chat_id=None, chosen_tool="web_search",
            execution_status="success", evidence_block_count=2, outcome_quality="unusable")
        self.assertEqual(learn_priors(self.store), {})
