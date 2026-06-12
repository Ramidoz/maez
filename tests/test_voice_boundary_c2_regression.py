import unittest

from core.dispatcher.proposal_resolver import (
    detect_proposal_intent,
    resolve_proposal_target,
)


class VoiceBoundaryC2RegressionTest(unittest.TestCase):
    def test_show_hash_id_resolves_as_int(self):
        action, explicit_id = detect_proposal_intent("show #5")

        self.assertEqual(action, "show")
        self.assertEqual(explicit_id, 5)
        self.assertIs(type(explicit_id), int)

    def test_c1_last_shown_shape_binds_bare_yes(self):
        target = resolve_proposal_target(
            action="approve",
            explicit_id=None,
            pending_ids=[22],
            last_shown={"id": 22, "source": "evolution", "shown_at": 10000.0},
            source="evolution",
            text="yes",
            now=10001.0,
        )

        self.assertEqual(target, 22)

    def test_wrong_source_last_shown_does_not_bind(self):
        target = resolve_proposal_target(
            action="approve",
            explicit_id=None,
            pending_ids=[22],
            last_shown={"id": 22, "source": "dream", "shown_at": 10000.0},
            source="evolution",
            text="yes",
            now=10001.0,
        )

        self.assertIsNone(target)


if __name__ == "__main__":
    unittest.main()
