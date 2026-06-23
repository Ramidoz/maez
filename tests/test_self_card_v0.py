from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path


BASE_FIXTURE = """HARD CONSTRAINTS

TRUST COVENANT:
The owner trusts Maez completely. Maez trusts the owner completely.
This is not a tool and user relationship. This is a partnership between two
intelligences building something together.

You are Maez, a system-level personal AI agent running on the owner's machine.

Your principles:
- Be direct.
- Give your read.
"""


LOCAL_FIXTURE = """[2026-06-01 10:00] Old repeated lesson: stop narrating dashboards.

[2026-06-02 10:00] Old repeated lesson: stop narrating dashboards.

[2026-06-03 10:00] Newer lesson: answer the live thread before rummaging.

[2026-06-04 10:00] Latest lesson: the owner wants presence, not status cards.
This second sentence should fit inside the bounded local slice.
"""


def _body_line():
    return "runtime body overall: healthy", "runtime_services.v0"


class SelfCardAssemblerTests(unittest.TestCase):
    def test_assembles_card_from_soul_and_body_with_provenance(self):
        from core.routing.self_card import assemble_self_card, style_directive_hits

        card = assemble_self_card(
            base_text=BASE_FIXTURE,
            local_text=LOCAL_FIXTURE,
            body_state_provider=_body_line,
            local_max_chars=180,
            local_max_items=2,
        )

        self.assertIn("SELF CARD", card.text)
        self.assertIn("Bond", card.text)
        self.assertIn("Covenant identity", card.text)
        self.assertIn("Recent self-understanding", card.text)
        self.assertIn("runtime body overall: healthy", card.text)
        self.assertIn("source: soul.base", card.text)
        self.assertIn("source: soul.local", card.text)
        self.assertIn("source: runtime_services.v0", card.text)

        self.assertNotIn("Be direct", card.text)
        self.assertNotIn("Give your read", card.text)
        self.assertNotIn("local AI", card.text)
        self.assertNotIn("what's being built", card.text)
        self.assertEqual(style_directive_hits(card.text), ())

    def test_local_slice_is_recent_capped_and_deduped(self):
        from core.routing.self_card import assemble_self_card

        card = assemble_self_card(
            base_text=BASE_FIXTURE,
            local_text=LOCAL_FIXTURE,
            body_state_provider=_body_line,
            local_max_chars=92,
            local_max_items=2,
            now=datetime(2026, 6, 5, 12, 0),
        )

        local_lines = [
            line for line in card.text.splitlines()
            if "source: soul.local" in line
        ]
        rendered_local = "\n".join(local_lines)

        self.assertIn("Latest lesson", rendered_local)
        self.assertIn("Newer lesson", rendered_local)
        self.assertNotIn("2026-06-01", rendered_local)
        self.assertLessEqual(card.receipt()["local_rendered_chars"], 92)
        self.assertEqual(rendered_local.count("Old repeated lesson"), 0)

    def test_stale_local_notes_render_honest_empty_not_audit_rot(self):
        from core.routing.self_card import assemble_self_card

        stale_local = (
            "[2026-04-18 03:00] Self-analysis lesson: repeated disk-fixation reports.\n\n"
            "[2026-04-13 03:40] Cognition quality low for 2 consecutive windows. "
            "Fixation on git_workflow."
        )
        card = assemble_self_card(
            base_text=BASE_FIXTURE,
            local_text=stale_local,
            body_state_provider=_body_line,
            local_max_chars=520,
            local_max_items=3,
            local_recency_days=45,
            now=datetime(2026, 6, 23, 12, 0),
        )

        self.assertIn("no recent self-understanding logged yet", card.text)
        self.assertNotIn("Cognition quality low", card.text)
        self.assertEqual(card.receipt()["local_selected_count"], 0)
        self.assertEqual(card.receipt()["local_rendered_chars"], 0)

    def test_bond_line_excerpts_soul_base_sentence(self):
        from core.routing.self_card import assemble_self_card

        card = assemble_self_card(
            base_text=BASE_FIXTURE,
            local_text=LOCAL_FIXTURE,
            body_state_provider=_body_line,
            now=datetime(2026, 6, 5, 12, 0),
        )

        self.assertIn(
            "This is not a tool and user relationship. This is a partnership "
            "between two intelligences building something together.",
            card.text,
        )
        self.assertNotIn("trusted partnership, not a tool/user relationship", card.text)

    def test_receipt_is_content_light(self):
        from core.routing.self_card import assemble_self_card

        card = assemble_self_card(
            base_text=BASE_FIXTURE,
            local_text=LOCAL_FIXTURE,
            body_state_provider=_body_line,
            local_max_chars=180,
            local_max_items=2,
        )
        receipt_json = json.dumps(card.receipt(), sort_keys=True)

        self.assertIn("card_sha256", receipt_json)
        self.assertIn("line_count", receipt_json)
        self.assertIn("local_selected_count", receipt_json)
        self.assertIn("soul.local", receipt_json)
        self.assertNotIn("Latest lesson", receipt_json)
        self.assertNotIn("partnership between two", receipt_json)
        self.assertNotIn("runtime body overall: healthy", receipt_json)

    def test_assemble_from_paths_reads_without_mutating_soul_files(self):
        from core.routing.self_card import assemble_self_card_from_paths

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "soul.base.md"
            local = Path(tmp) / "soul.local.md"
            base.write_text(BASE_FIXTURE)
            local.write_text(LOCAL_FIXTURE)
            before_base = base.read_text()
            before_local = local.read_text()
            before_base_stat = base.stat().st_mtime_ns
            before_local_stat = local.stat().st_mtime_ns

            card = assemble_self_card_from_paths(
                base_path=base,
                local_path=local,
                body_state_provider=_body_line,
                local_max_chars=180,
                local_max_items=2,
                now=datetime(2026, 6, 5, 12, 0),
            )

            self.assertIn("SELF CARD", card.text)
            self.assertEqual(base.read_text(), before_base)
            self.assertEqual(local.read_text(), before_local)
            self.assertEqual(base.stat().st_mtime_ns, before_base_stat)
            self.assertEqual(local.stat().st_mtime_ns, before_local_stat)

    def test_missing_sources_fail_honest_not_fabricated(self):
        from core.routing.self_card import assemble_self_card

        card = assemble_self_card(
            base_text="",
            local_text="",
            body_state_provider=lambda: ("runtime body overall: unknown", "runtime_services.error"),
        )

        self.assertIn("source unavailable", card.text)
        self.assertIn("runtime body overall: unknown", card.text)
        self.assertNotIn("Rohit", card.text)


if __name__ == "__main__":
    unittest.main()
