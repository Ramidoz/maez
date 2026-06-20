import os, unittest
os.environ.setdefault("MAEZ_IPHONE_INGEST_TOKEN", "dummy-test")
os.environ.setdefault("MAEZ_SECRETS_DISABLE_NEW_LOADER", "1")
from daemon.maez_daemon import _prior_vetoes_reflex
from core.routing.observation.priors import RoutingPrior

class VetoSeamTest(unittest.TestCase):
    def test_high_confidence_bad_prior_vetoes(self):
        p = RoutingPrior("SIGNALS", "web_search", n=8, success_rate=0.1, confidence=1.0)
        self.assertTrue(_prior_vetoes_reflex(p, min_conf=0.6, max_success=0.4))
    def test_low_confidence_does_not_veto(self):
        p = RoutingPrior("SIGNALS", "web_search", n=2, success_rate=0.0, confidence=0.0)
        self.assertFalse(_prior_vetoes_reflex(p, min_conf=0.6, max_success=0.4))
    def test_good_prior_does_not_veto(self):
        p = RoutingPrior("NEWS", "web_search", n=8, success_rate=0.9, confidence=1.0)
        self.assertFalse(_prior_vetoes_reflex(p, min_conf=0.6, max_success=0.4))
    def test_none_prior_does_not_veto(self):
        self.assertFalse(_prior_vetoes_reflex(None, min_conf=0.6, max_success=0.4))
