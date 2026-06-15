"""Dispatcher throat receipt — test that `_render_prompt_block` emits the shared
`web_containment_applied` receipt (path=dispatcher) after wrapping fresh summaries.

Methodology: patch `core.routing.web_containment.emit_receipt` to capture the dict
that would be logged; verify shape, balanced=True, correct digest, correct path.
"""
import os
import types
import unittest
from unittest import mock


# ---------------------------------------------------------------------------
# Fixtures (mirrored from test_rail2_containment.py / test_livewc_dispatcher.py)
# ---------------------------------------------------------------------------

def _fresh_spec():
    from core.dispatcher.spec import CompositionHint, ProvenanceFraming
    return types.SimpleNamespace(
        composition_hint=CompositionHint.FRESH_ONLY,
        provenance_framing=ProvenanceFraming.FRESH_ONLY,
    )


def _substrate_only_spec():
    from core.dispatcher.spec import CompositionHint, ProvenanceFraming
    return types.SimpleNamespace(
        composition_hint=CompositionHint.SUBSTRATE_ONLY,
        provenance_framing=ProvenanceFraming.SUBSTRATE_ONLY_NO_FRESH_VALIDATION,
    )


def _fresh_summary(text: str, *, digest: str = "webdig"):
    from core.dispatcher.provenance_renderer import SourceRole, SourceSummary
    from core.dispatcher.spec import ExternalSource
    return SourceSummary(
        source=ExternalSource("WEB_SEARCH"),
        role=SourceRole.FRESH_EVIDENCE,
        text=text,
        content_digest=digest,
    )


def _memory_summary(text: str):
    from core.dispatcher.provenance_renderer import SourceRole, SourceSummary
    from core.dispatcher.spec import SubstrateSource
    return SourceSummary(
        source=SubstrateSource("REDDIT_SOURCE"),
        role=SourceRole.SUBSTRATE_CONTEXT,
        text=text,
        content_digest="memdig",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class DispatcherReceiptTest(unittest.TestCase):

    def test_inline_flag_on_emits_balanced_dispatcher_receipt(self):
        """AskShape.CONVERSATIONAL, flag ON, one FRESH + one memory summary.
        Receipt must have path=dispatcher, balanced=True, segments/open/close==1,
        and digest comes from the FRESH summary's content_digest, not the memory one."""
        from core.dispatcher.provenance_renderer import AskShape, _render_prompt_block

        captured = []
        with mock.patch("core.routing.web_containment.emit_receipt", side_effect=captured.append), \
             mock.patch.dict(os.environ, {"MAEZ_FETCH_CONTAINMENT_ENABLED": "1"}):
            _render_prompt_block(
                _fresh_spec(),
                ask_shape=AskShape.CONVERSATIONAL,
                source_summaries=[
                    _memory_summary("substrate mem"),
                    _fresh_summary("fetched page", digest="webdig"),
                ],
            )

        self.assertEqual(len(captured), 1, "Expected exactly one receipt emitted")
        r = captured[0]
        self.assertEqual(r["path"], "dispatcher")
        self.assertTrue(r["balanced"], "Receipt must be balanced=True")
        self.assertEqual(r["rendered_web_segments"], 1)
        self.assertEqual(r["open_markers"], 1)
        self.assertEqual(r["close_markers"], 1)
        self.assertIn("webdig", r["digest"])
        self.assertNotIn("memdig", r["digest"])

    def test_report_flag_on_emits_balanced_dispatcher_receipt(self):
        """AskShape.REPORT, flag ON, one FRESH + one memory summary.
        Receipt must have path=dispatcher and balanced=True."""
        from core.dispatcher.provenance_renderer import AskShape, _render_prompt_block

        captured = []
        with mock.patch("core.routing.web_containment.emit_receipt", side_effect=captured.append), \
             mock.patch.dict(os.environ, {"MAEZ_FETCH_CONTAINMENT_ENABLED": "1"}):
            _render_prompt_block(
                _fresh_spec(),
                ask_shape=AskShape.REPORT,
                source_summaries=[
                    _memory_summary("substrate mem"),
                    _fresh_summary("fetched report page", digest="webdig"),
                ],
            )

        self.assertEqual(len(captured), 1, "Expected exactly one receipt emitted")
        r = captured[0]
        self.assertEqual(r["path"], "dispatcher")
        self.assertTrue(r["balanced"])
        self.assertEqual(r["rendered_web_segments"], 1)
        self.assertEqual(r["open_markers"], 1)
        self.assertEqual(r["close_markers"], 1)
        self.assertIn("webdig", r["digest"])

    def test_two_fresh_summaries_segments_2(self):
        """Two FRESH summaries (digests d1, d2) → receipt has segments==2, open==close==2,
        and digest contains both d1 and d2."""
        from core.dispatcher.provenance_renderer import AskShape, _render_prompt_block

        captured = []
        with mock.patch("core.routing.web_containment.emit_receipt", side_effect=captured.append), \
             mock.patch.dict(os.environ, {"MAEZ_FETCH_CONTAINMENT_ENABLED": "1"}):
            _render_prompt_block(
                _fresh_spec(),
                ask_shape=AskShape.CONVERSATIONAL,
                source_summaries=[
                    _fresh_summary("first fetched page", digest="d1"),
                    _fresh_summary("second fetched page", digest="d2"),
                ],
            )

        self.assertEqual(len(captured), 1, "Expected exactly one receipt emitted")
        r = captured[0]
        self.assertEqual(r["rendered_web_segments"], 2)
        self.assertEqual(r["open_markers"], 2)
        self.assertEqual(r["close_markers"], 2)
        self.assertTrue(r["balanced"])
        self.assertIn("d1", r["digest"])
        self.assertIn("d2", r["digest"])

    def test_flag_off_no_receipt_and_byte_identical(self):
        """Flag OFF: emit_receipt must NOT be called, and the rendered block must
        contain no <<EXT: markers (byte-identical bare rendering)."""
        from core.dispatcher.provenance_renderer import AskShape, _render_prompt_block

        captured = []
        env = {k: v for k, v in os.environ.items() if k != "MAEZ_FETCH_CONTAINMENT_ENABLED"}
        with mock.patch("core.routing.web_containment.emit_receipt", side_effect=captured.append), \
             mock.patch.dict(os.environ, env, clear=True):
            block, _ = _render_prompt_block(
                _fresh_spec(),
                ask_shape=AskShape.CONVERSATIONAL,
                source_summaries=[
                    _fresh_summary("hi", digest="webdig"),
                ],
            )

        self.assertEqual(len(captured), 0, "emit_receipt must NOT be called when flag is off")
        self.assertNotIn("<<EXT:", block, "Flag-off block must not contain <<EXT: markers")
        self.assertEqual(block, "[fresh evidence] hi")


    def test_flag_on_zero_fresh_no_receipt(self):
        """Flag ON but only a substrate/memory summary (no FRESH role) → NO receipt.

        A non-fetch turn must never log a false path=dispatcher witness.
        _emit_dispatcher_receipt guards on `_fresh_digests`; with zero fresh
        summaries that list stays empty and emit_receipt must not be called."""
        from core.dispatcher.provenance_renderer import AskShape, _render_prompt_block

        captured = []
        with mock.patch.dict(os.environ, {"MAEZ_FETCH_CONTAINMENT_ENABLED": "1"}), \
             mock.patch("core.routing.web_containment.emit_receipt", lambda r: captured.append(r)):
            block, _ = _render_prompt_block(
                _substrate_only_spec(),
                ask_shape=AskShape.CONVERSATIONAL,
                source_summaries=[
                    _memory_summary("substrate mem"),
                ],
            )

        self.assertEqual(len(captured), 0, "no fresh content -> no dispatcher receipt")
        self.assertNotIn("<<EXT:", block)


if __name__ == "__main__":
    unittest.main()
