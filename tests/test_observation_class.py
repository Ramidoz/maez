import os, unittest
from unittest import mock
os.environ.setdefault("MAEZ_IPHONE_INGEST_TOKEN", "dummy-test")
os.environ.setdefault("MAEZ_SECRETS_DISABLE_NEW_LOADER", "1")
from core.routing.observation_class import classify_request_class

class ObservationClassTest(unittest.TestCase):
    def test_hash_fallback_is_stable_and_versioned(self):
        a = classify_request_class("summarize today's signals")
        b = classify_request_class("summarize today's signals")
        self.assertEqual(a, b)
        self.assertEqual(a[2], "utterance_hash_v0")
        self.assertEqual(a[1], 1.0)
        self.assertNotEqual(a[0], classify_request_class("totally different")[0])

    def test_layer0_class_used_when_reachable(self):
        with mock.patch("core.routing.observation_class._layer0_class",
                        return_value=("B_EXPLICIT_LIVE_FETCH", 0.71, "archetypes-v0")), \
             mock.patch("core.routing.observation_class._LAYER0_ENABLED", True):
            cid, score, ver = classify_request_class("search the web for X")
            self.assertEqual(cid, "B_EXPLICIT_LIVE_FETCH"); self.assertEqual(ver, "archetypes-v0")

    def test_layer0_failure_falls_back_to_hash(self):
        with mock.patch("core.routing.observation_class._layer0_class", side_effect=RuntimeError("dormant")), \
             mock.patch("core.routing.observation_class._LAYER0_ENABLED", True):
            cid, score, ver = classify_request_class("anything")
            self.assertEqual(ver, "utterance_hash_v0")
