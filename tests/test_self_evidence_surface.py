import os
import unittest
from unittest import mock


class SurfaceTests(unittest.TestCase):
    def test_flag_off_surface_is_inert(self):
        from scripts import self_evidence as cli

        with (
            mock.patch.dict(os.environ, {"MAEZ_SELF_EVIDENCE": "0"}, clear=False),
            mock.patch(
                "core.learning.self_evidence.self_evidence_digest",
                side_effect=AssertionError("digest should not run"),
            ),
        ):
            out = cli.render(argv=["show"])

        self.assertIn("disabled", out.lower())

    def test_flag_on_renders_digest_without_first_person(self):
        from scripts import self_evidence as cli

        digest = {
            "kind": "self_evidence_integrity_ledger",
            "sources": {
                "fabrication_events": {
                    "status": "ok",
                    "retained_rows": 2,
                    "coverage": "90d_best_effort",
                }
            },
            "merged_events": {"distinct_integrity_events": 2},
        }
        with (
            mock.patch.dict(os.environ, {"MAEZ_SELF_EVIDENCE": "1"}, clear=False),
            mock.patch(
                "core.learning.self_evidence.self_evidence_digest",
                return_value=digest,
            ),
        ):
            out = cli.render(argv=["show"]).lower()

        for text in (" i ", "i have", "i've", "myself", "my record"):
            self.assertNotIn(text, out)
        self.assertIn("fabrication_events", out)
        self.assertIn("retained_rows", out)
