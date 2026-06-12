from __future__ import annotations

import unittest
from pathlib import Path

_SRC = Path("skills/telegram_voice.py").read_text()


class LoudnessGuardTests(unittest.TestCase):
    def test_module_docstring_names_outbound_only_and_the_map(self):
        head = _SRC[:1400]
        self.assertIn("OUTBOUND-ONLY", head)
        self.assertIn("2026-04-20", head)
        self.assertIn("maez_adapter.py", head)
        self.assertIn("SURFACE_PARITY_MAP_2026-06-12", head)

    def test_handle_message_has_once_per_process_warning(self):
        self.assertIn("_INBOUND_WARNED", _SRC)
        self.assertIn("outbound-only", _SRC.lower())
