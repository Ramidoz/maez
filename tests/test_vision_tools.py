import asyncio
import json
import unittest

from tools import vision_tools


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


class ContractTests(unittest.TestCase):
    def test_result_shape(self):
        out = vision_tools._result(success=True, analysis="a cat on a desk")

        self.assertEqual(set(out), {"success", "analysis", "error"})
        self.assertTrue(out["success"])
        self.assertEqual(out["analysis"], "a cat on a desk")
        self.assertEqual(out["error"], "")

    def test_emit_is_json_string(self):
        s = vision_tools._emit(vision_tools._result(success=False, error="x"))

        d = json.loads(s)
        self.assertFalse(d["success"])
        self.assertEqual(d["analysis"], "")
        self.assertEqual(d["error"], "x")


if __name__ == "__main__":
    unittest.main()
