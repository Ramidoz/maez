import unittest

from core.governance.operator_user_boundary import build_birth_readiness_projection


def _cond(key, state, detail="d"):
    return {
        "key": key,
        "title": key.replace("_", " "),
        "state": state,
        "detail": detail,
        "checked_at": "2026-07-05T00:00:00Z",
    }


class BirthReadinessProjectionTests(unittest.TestCase):
    def test_all_green_overall_green(self):
        p = build_birth_readiness_projection(
            generated_at="2026-07-05T00:00:00Z",
            conditions=[_cond("ledger_init", "green"), _cond("flag_state", "green")],
        )
        self.assertEqual(p["route"], "/operator/birth_readiness")
        self.assertEqual(p["overall"], "green")
        self.assertEqual(len(p["conditions"]), 2)

    def test_any_red_overall_red(self):
        p = build_birth_readiness_projection(
            generated_at="2026-07-05T00:00:00Z",
            conditions=[_cond("ledger_init", "green"), _cond("dream_witness", "red")],
        )
        self.assertEqual(p["overall"], "red")

    def test_invalid_state_refused(self):
        with self.assertRaises(ValueError):
            build_birth_readiness_projection(
                generated_at="2026-07-05T00:00:00Z",
                conditions=[_cond("x", "yellow")],
            )

    def test_content_light_no_free_fields(self):
        with self.assertRaises(ValueError):
            build_birth_readiness_projection(
                generated_at="2026-07-05T00:00:00Z",
                conditions=[{**_cond("x", "green"), "thought_body": "leak"}],
            )


if __name__ == "__main__":
    unittest.main()
