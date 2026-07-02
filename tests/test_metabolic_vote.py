import time
import unittest

from core.memory.metabolic import CycleEvents, GlanceBuffer, evaluate_durability


class DurabilityVoteTests(unittest.TestCase):
    def test_quiet_cycle_is_ephemeral(self):
        durable, reason = evaluate_durability(CycleEvents())
        self.assertFalse(durable)
        self.assertIsNone(reason)

    def test_each_event_trigger_is_durable(self):
        cases = {
            "alert_sent": "alert",
            "error_event": "error",
            "owner_interaction": "owner_interaction",
            "action_taken": "action",
            "first_of_kind": "novel_event",
            "covenant_event": "covenant",
        }
        for field, expected_reason in cases.items():
            with self.subTest(field=field):
                durable, reason = evaluate_durability(CycleEvents(**{field: True}))
                self.assertTrue(durable)
                self.assertEqual(reason, expected_reason)

    def test_salience_rescue_is_durable(self):
        durable, reason = evaluate_durability(CycleEvents(salience_marked=True))
        self.assertTrue(durable)
        self.assertEqual(reason, "salience_rescue")

    def test_event_reason_wins_over_rescue_when_both(self):
        durable, reason = evaluate_durability(
            CycleEvents(alert_sent=True, salience_marked=True)
        )
        self.assertTrue(durable)
        self.assertEqual(reason, "alert")


class GlanceBufferTests(unittest.TestCase):
    def test_append_and_recent(self):
        buf = GlanceBuffer(maxlen=3, ttl_s=3600)
        for i in range(4):
            buf.append(text=f"t{i}", cycle=i, ts=time.time())
        texts = [g["text"] for g in buf.recent()]
        self.assertEqual(texts, ["t1", "t2", "t3"])

    def test_ttl_prunes(self):
        buf = GlanceBuffer(maxlen=10, ttl_s=1)
        buf.append(text="old", cycle=1, ts=time.time() - 5)
        buf.append(text="new", cycle=2, ts=time.time())
        texts = [g["text"] for g in buf.recent()]
        self.assertEqual(texts, ["new"])

    def test_rescue_window_pop(self):
        buf = GlanceBuffer(maxlen=10, ttl_s=3600)
        buf.append(text="mover", cycle=7, ts=time.time())
        g = buf.take_by_cycle(7)
        self.assertEqual(g["text"], "mover")
        self.assertIsNone(buf.take_by_cycle(7))
