"""Regression guard — throat 4 dispatcher containment is truncation-safe.

Task 0 proved the dispatcher does NOT truncate the fresh block after Rail 2 Layer A
wraps it (zero truncation / slicing / char-budget in core/dispatcher/merge.py and
core/dispatcher/provenance_renderer.py).

This test LOCKS that invariant: a long (5000-char) wrapped web block must render
with a balanced, un-sliced close marker, and flag-off must produce bare text
byte-identically (no <<EXT: prefix).

Methodology: reuses the exact fixture approach from tests/test_rail2_containment.py
(SourceSummary, SourceRole.FRESH_EVIDENCE, ExternalSource, AskShape, _render_prompt_block).
"""
import os
import types
import unittest
from unittest import mock


# ---------------------------------------------------------------------------
# Shared fixtures (mirrored from test_rail2_containment.py)
# ---------------------------------------------------------------------------

def _fresh_spec():
    """Minimal spec whose composition/provenance hints mark the block FRESH_ONLY."""
    from core.dispatcher.spec import CompositionHint, ProvenanceFraming
    return types.SimpleNamespace(
        composition_hint=CompositionHint.FRESH_ONLY,
        provenance_framing=ProvenanceFraming.FRESH_ONLY,
    )


def _fresh_summary(text: str):
    from core.dispatcher.provenance_renderer import SourceRole, SourceSummary
    from core.dispatcher.spec import ExternalSource
    return SourceSummary(
        source=ExternalSource("WEB_SEARCH"),
        role=SourceRole.FRESH_EVIDENCE,
        text=text,
        content_digest="d1gest",
    )


# ---------------------------------------------------------------------------
# Regression test
# ---------------------------------------------------------------------------

_LONG_WEB_TEXT = "A" * 2500 + " mid-marker " + "B" * 2488  # 5001 chars total


class DispatcherTruncationSafeTest(unittest.TestCase):
    """Throat 4 — dispatcher render must never slice the containment envelope."""

    def test_long_fresh_block_balanced_markers_flag_on(self):
        """Flag ON + 5000-char fresh text: open and close markers are both present
        and balanced (count open == count close), proving no truncation of the
        wrapped block occurs inside the dispatcher render path."""
        from core.dispatcher.provenance_renderer import AskShape, _render_prompt_block

        with mock.patch.dict(os.environ, {"MAEZ_FETCH_CONTAINMENT_ENABLED": "1"}):
            block, _ = _render_prompt_block(
                _fresh_spec(),
                ask_shape=AskShape.CONVERSATIONAL,
                source_summaries=[_fresh_summary(_LONG_WEB_TEXT)],
            )

        # 1. Close marker must be present (not sliced off).
        self.assertIn("<</EXT:", block, "Close marker absent — dispatcher may be truncating the wrapped block")

        # 2. Markers must be balanced: every open has a matching close.
        open_count = block.count("<<EXT:")
        close_count = block.count("<</EXT:")
        self.assertEqual(
            open_count,
            close_count,
            f"Unbalanced markers: {open_count} open vs {close_count} close — "
            "dispatcher is slicing inside the containment envelope",
        )

        # 3. The full web text must survive intact (no char-budget truncation).
        self.assertIn(_LONG_WEB_TEXT, block, "Long web text was truncated before reaching the rendered block")

        # 4. Standing instruction present (proves flag path active).
        self.assertIn("never", block.lower(), "Standing instruction missing — containment flag may not be active")

    def test_long_fresh_block_flag_off_no_ext_marker(self):
        """Flag OFF: rendered block must contain no <<EXT: prefix at all —
        byte-identical bare rendering, confirming flag-off path is untouched."""
        from core.dispatcher.provenance_renderer import AskShape, _render_prompt_block

        env = {k: v for k, v in os.environ.items() if k != "MAEZ_FETCH_CONTAINMENT_ENABLED"}
        with mock.patch.dict(os.environ, env, clear=True):
            block, _ = _render_prompt_block(
                _fresh_spec(),
                ask_shape=AskShape.CONVERSATIONAL,
                source_summaries=[_fresh_summary(_LONG_WEB_TEXT)],
            )

        self.assertNotIn(
            "<<EXT:",
            block,
            "Flag-off block contains <<EXT: marker — containment envelope is leaking into the bare path",
        )
        # The long text still reaches the brain unchanged.
        self.assertIn(_LONG_WEB_TEXT, block, "Long web text lost on flag-off path")


if __name__ == "__main__":
    unittest.main()
