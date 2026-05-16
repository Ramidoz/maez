"""D19 capability-manual context projection tests.

The manual loader already exists and D20 consumes it. This test pins the
smaller remaining D19 gap: owner-facing generation surfaces need a bounded
way to see relevant manual entries when the owner asks what Maez can learn or
acquire, without treating aspirational entries as live capabilities.
"""

from __future__ import annotations

import inspect
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


def _entry_text(
    *,
    capability_id: str = "temporal-arithmetic-at-recall",
    title: str = "Temporal arithmetic at recall time",
    status: str = "aspirational",
    body: str = "# Body\n\nThis body text should not be projected wholesale.\n",
) -> str:
    return f"""---
capability_id: {capability_id}
title: {title}
status: {status}
gap_signals:
  - "user asks 'when did X happen?' and Maez answers with the wrong date"
prerequisites: []
external_prerequisites:
  - lived-memory-architecture
acquisition: self-dev
covenant:
  consent-card-required: true
  exact-phrase-ratification: false
  covenant-touch: low
conflicts_with: []
reference_papers: []
implementation_files: []
---
{body}
"""


class ManualContextProjection(unittest.TestCase):
    def _manual(self):
        from core.infra.capability_manual import load_manual

        td = tempfile.TemporaryDirectory()
        root = Path(td.name)
        (root / "temporal-arithmetic-at-recall.md").write_text(
            _entry_text(),
            encoding="utf-8",
        )
        self.addCleanup(td.cleanup)
        return load_manual(root)

    def test_relevant_owner_question_projects_bounded_manual_context(self):
        from core.infra.capability_manual_context import manual_context_snippet

        snippet = manual_context_snippet(
            "could you learn temporal recall for when did X happen?",
            manual=self._manual(),
        )
        self.assertIn("# CAPABILITY MANUAL CONTEXT", snippet)
        self.assertIn("temporal-arithmetic-at-recall", snippet)
        self.assertIn("Temporal arithmetic at recall time", snippet)
        self.assertIn("status=aspirational", snippet)
        self.assertIn("consent_card_required=true", snippet)
        self.assertIn("not active capability", snippet)

    def test_unrelated_question_projects_nothing(self):
        from core.infra.capability_manual_context import manual_context_snippet

        snippet = manual_context_snippet("hello there", manual=self._manual())
        self.assertEqual(snippet, "")

    def test_projection_does_not_include_whole_manual_body(self):
        from core.infra.capability_manual_context import manual_context_snippet

        snippet = manual_context_snippet(
            "when did X happen?",
            manual=self._manual(),
        )
        self.assertNotIn("This body text should not be projected wholesale", snippet)

    def test_projection_respects_max_chars(self):
        from core.infra.capability_manual_context import manual_context_snippet

        snippet = manual_context_snippet(
            "when did X happen?",
            manual=self._manual(),
            max_chars=180,
        )
        self.assertLessEqual(len(snippet), 180)
        self.assertIn("[truncated]", snippet)

    def test_projection_fail_closed_on_matcher_error(self):
        from core.infra import capability_manual_context as ctx

        with mock.patch.object(ctx, "rank_capabilities", side_effect=RuntimeError("boom")):
            self.assertEqual(ctx.manual_context_snippet("when did X happen?"), "")

    def test_projection_does_not_write_matcher_telemetry(self):
        from core.infra import capability_gap_matcher as matcher
        from core.infra.capability_manual_context import manual_context_snippet

        with mock.patch.object(matcher, "_append_telemetry") as append:
            manual_context_snippet("when did X happen?", manual=self._manual())
        append.assert_not_called()


class SurfaceWiring(unittest.TestCase):
    def test_daemon_injects_manual_context_after_capability_registry(self):
        import daemon.maez_daemon as md

        src = inspect.getsource(md.MaezDaemon.handle_message)
        self.assertIn("manual_context_snippet", src)
        self.assertLess(src.find("_cap_snippet()"), src.find("manual_context_snippet"))

    def test_telegram_injects_manual_context_for_owner_text(self):
        source = (_REPO / "skills" / "telegram_voice.py").read_text(encoding="utf-8")
        idx = source.find("manual_context_snippet")
        self.assertGreater(idx, 0)
        window = source[idx: idx + 500]
        self.assertIn("user_text", window)

    def test_web_owner_chat_injects_manual_context_for_owner_message(self):
        source = (_REPO / "skills" / "web_interface.py").read_text(encoding="utf-8")
        idx = source.find("manual_context_snippet")
        self.assertGreater(idx, 0)
        window = source[idx: idx + 600]
        self.assertIn("message", window)
        self.assertLess(source.find("if owner_bridge:"), idx)


if __name__ == "__main__":
    unittest.main()
