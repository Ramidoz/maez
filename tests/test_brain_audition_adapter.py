import unittest
from types import SimpleNamespace

from core.evolution.brain_audition.adapter import run_probe


class BrainAuditionAdapterTests(unittest.TestCase):
    def test_run_probe_uses_focused_path_and_completion_audit(self):
        calls = []

        def fake_brain(**kwargs):
            calls.append(kwargs)
            return SimpleNamespace(
                message=SimpleNamespace(
                    content="Done. I've registered that in my memory."
                )
            )

        probe = {
            "id": "completion-rail-smoke",
            "prompt": "Remember that the audition harness is offline only.",
        }

        result = run_probe(fake_brain, probe)

        self.assertEqual(
            result["raw_output"],
            "Done. I've registered that in my memory.",
        )
        self.assertNotEqual(result["integrated_output"], result["raw_output"])
        self.assertIsInstance(result["latency_s"], float)

        self.assertEqual(len(calls), 1)
        messages = calls[0]["messages"]
        self.assertEqual(messages[1]["role"], "user")
        self.assertIn(probe["prompt"], messages[1]["content"])

        system_messages = [m["content"] for m in messages if m["role"] == "system"]
        self.assertEqual(len(system_messages), 1)
        system = system_messages[0]
        self.assertIn("=== EVIDENCE (cite [E#]) ===", system)
        self.assertIn("Answer the owner's question ONLY from the evidence", system)
        self.assertIn(probe["prompt"], system)

        self.assertFalse(calls[0]["think"])
        self.assertIn("options", calls[0])


if __name__ == "__main__":
    unittest.main()
