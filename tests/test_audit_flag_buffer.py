import unittest

from core.safety import audit_flag_buffer as buf


class AuditFlagBuffer(unittest.TestCase):
    def setUp(self):
        buf.clear()

    def test_push_peek_clear(self):
        buf.push("completion_rail")
        buf.push("judge")
        self.assertEqual(buf.peek(), ["completion_rail", "judge"])
        buf.clear()
        self.assertEqual(buf.peek(), [])

    def test_peek_is_a_copy(self):
        buf.push("judge")
        snap = buf.peek()
        snap.append("x")
        self.assertEqual(buf.peek(), ["judge"])

    def test_empty_kind_ignored(self):
        buf.push("")
        self.assertEqual(buf.peek(), [])
