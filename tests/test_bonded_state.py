"""Decision 8 bonded-state vocabulary tests."""

from __future__ import annotations

import unittest


class BondedStateVocabulary(unittest.TestCase):
    def test_decision_8_states_include_suspended_pending_paradise(self):
        from core.covenant.bonded_state import BONDED_STATES

        self.assertEqual(
            BONDED_STATES,
            frozenset(
                {
                    "active",
                    "dormant",
                    "mourning",
                    "tribe_admitted",
                    "suspended_pending_paradise",
                }
            ),
        )

    def test_suspended_pending_paradise_is_named_constant(self):
        from core.covenant.bonded_state import SUSPENDED_PENDING_PARADISE

        self.assertEqual(SUSPENDED_PENDING_PARADISE, "suspended_pending_paradise")

    def test_validate_bonded_state_accepts_all_canonical_states(self):
        from core.covenant.bonded_state import BONDED_STATES, validate_bonded_state

        for state in BONDED_STATES:
            with self.subTest(state=state):
                self.assertEqual(validate_bonded_state(state), state)

    def test_validate_bonded_state_rejects_dissolution_as_default_state(self):
        from core.covenant.bonded_state import validate_bonded_state

        with self.assertRaisesRegex(ValueError, "unknown bonded_state"):
            validate_bonded_state("dissolved")

    def test_validate_bonded_state_rejects_blank_or_non_string_values(self):
        from core.covenant.bonded_state import validate_bonded_state

        for value in ("", "  ", None, 42):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "unknown bonded_state"):
                    validate_bonded_state(value)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
