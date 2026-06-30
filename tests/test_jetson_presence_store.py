# tests/test_jetson_presence_store.py
import unittest
from core.body.jetson_presence import JetsonPresenceReading
from core.body.jetson_presence_store import JetsonPresenceStore


def _reading(owner_present="present", sensor_state="available"):
    return JetsonPresenceReading(owner_present, "high", sensor_state, "2026-06-29T19:00:00+00:00")


class JetsonPresenceStoreTests(unittest.TestCase):
    def test_empty_store_is_unavailable_unknown(self):
        store = JetsonPresenceStore(stale_after=180)
        self.assertEqual(store.current(now=1000.0), ("unknown", "unavailable"))

    def test_record_then_current_fresh(self):
        store = JetsonPresenceStore(stale_after=180)
        store.record(_reading(), received_at=1000.0)
        self.assertEqual(store.current(now=1010.0), ("present", "available"))

    def test_record_then_current_after_window_is_stale_unknown(self):
        store = JetsonPresenceStore(stale_after=180)
        store.record(_reading(owner_present="present"), received_at=1000.0)
        owner, sensor = store.current(now=1200.0)  # 200s later
        self.assertEqual((owner, sensor), ("unknown", "stale"))  # never "absent"

    def test_received_at_is_recorded(self):
        store = JetsonPresenceStore(stale_after=180)
        store.record(_reading(), received_at=1234.5)
        self.assertEqual(store.last_received_at, 1234.5)


if __name__ == "__main__":
    unittest.main()
