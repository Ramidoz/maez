import os, tempfile, unittest
os.environ.setdefault("MAEZ_IPHONE_INGEST_TOKEN", "dummy-test")
os.environ.setdefault("MAEZ_SECRETS_DISABLE_NEW_LOADER", "1")
from core.routing.observation import RoutingObservationStore
from core.routing.observation.priors import beta_belief, compare_beliefs, BeliefComparison

class BetaBeliefTest(unittest.TestCase):
    def test_beta_belief_consistent_failures_confident(self):
        mean, p_below = beta_belief(usable=0, n=5)
        self.assertAlmostEqual(p_below, 1 - 0.6**6, places=4)   # 1 - 0.6**6 ~ 0.953
        self.assertLess(mean, 0.2)
    def test_beta_belief_thin_stays_uncertain(self):           # GATE 2
        _, p2 = beta_belief(usable=0, n=2)                     # 1 - 0.6**3 = 0.784 < 0.9
        self.assertLess(p2, 0.9)
    def test_beta_belief_mixed_is_uncertain(self):             # GATE 5
        _, p = beta_belief(usable=2, n=5)                      # Beta(3,4): P(rate<=0.4) < 0.5
        self.assertLess(p, 0.5)

class CompareBeliefsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.store = RoutingObservationStore(db_path=self.tmp.name)
    def tearDown(self):
        self.tmp.close()
        try: os.unlink(self.tmp.name)
        except OSError: pass
    def _rows(self, qualities):
        for q in qualities:
            self.store.record_legacy_web_search_observation(
                user_text="t", surface="cockpit", chat_id=None, chosen_tool="web_search",
                execution_status="success", evidence_block_count=2, outcome_quality=q,
                request_class_id="SIG", request_class_score=0.7, request_class_version="v0")
    def test_consistent_both_veto(self):                       # GATE 4 (5-streak)
        self._rows(["unusable"] * 5)
        c = compare_beliefs(self.store)[("SIG", "web_search")]
        self.assertTrue(c.n8_would_veto); self.assertTrue(c.beta_would_veto)
    def test_thin_both_abstain(self):                          # GATE 2
        self._rows(["unusable"] * 2)
        c = compare_beliefs(self.store)[("SIG", "web_search")]
        self.assertFalse(c.n8_would_veto); self.assertFalse(c.beta_would_veto)
    def test_mixed_n8_overclaims_beta_abstains(self):          # GATE 5 — the keystone
        self._rows(["unusable", "unusable", "unusable", "structured_evidence", "structured_evidence"])
        c = compare_beliefs(self.store)[("SIG", "web_search")]
        self.assertIsInstance(c, BeliefComparison)
        self.assertTrue(c.n8_would_veto)                       # n/8: n=5 conf 0.625, rate 0.4 -> vetoes
        self.assertFalse(c.beta_would_veto)                    # Beta: Beta(3,4) uncertain -> abstains
        self.assertLess(c.beta_p_below, c.n8_confidence)       # Beta less confident than n/8 on mixed
