from __future__ import annotations

import unittest

from core.interaction_preferences.render import render_interaction_preferences
from core.interaction_preferences.store import InteractionPreference


def _pref(
    *,
    owner_statement: str = "stop asking me so many questions",
) -> InteractionPreference:
    return InteractionPreference(
        preference_id="pref-1",
        created_at="2026-07-03T12:00:00Z",
        updated_at="2026-07-03T12:00:00Z",
        status="active",
        preference_class="question_cadence",
        owner_statement=owner_statement,
        source_ref="owner_turn:telegram:abc123:1000",
        surface="telegram",
        statement_sha256="a" * 64,
    )


class InteractionPreferencesRenderTests(unittest.TestCase):
    def test_renderer_uses_verbatim_owner_statement(self):
        rendered = render_interaction_preferences([_pref()])

        self.assertIn('Rohit explicitly said: "stop asking me so many questions"', rendered)
        self.assertNotIn('"stop asking me so many questions."', rendered)

    def test_renderer_scaffold_contains_no_command_language(self):
        rendered = render_interaction_preferences([_pref()])
        scaffold = rendered.replace('"stop asking me so many questions"', "")
        lowered = scaffold.lower()

        for forbidden in ("must", "never", "do not ask", "don't ask", "only ask"):
            self.assertNotIn(forbidden, lowered)

    def test_empty_active_preferences_render_empty(self):
        self.assertEqual(render_interaction_preferences([]), "")


if __name__ == "__main__":
    unittest.main()
