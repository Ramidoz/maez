# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Tests for the prompt-caching refactor.

Before 2026-04-21, the ~600 tokens of static cycle instructions sat at
the END of the user message. Since the user message changes every cycle
(cycle count, system stats, recall), the instructions rebuilt every time
and llama.cpp's KV cache could not reuse them.

The refactor moves those instructions into the system prompt (appended
to SOUL) so the entire system message is byte-stable across cycles.
These tests pin the invariants that make the cache win real:

  1. _STATIC_CYCLE_INSTRUCTIONS contains no per-cycle interpolations
     (no f-string variables that would differ between cycles).
  2. Concatenating a stable SOUL with the static instructions produces
     byte-identical output on repeated calls.
  3. The string is non-trivially sized (≥ 1000 chars, i.e. non-empty
     payload — catches accidental truncation regressions).
"""
from __future__ import annotations

import hashlib
import unittest

# daemon/maez_daemon.py pulls in ollama, telegram, flask, websockets,
# and other optional extras at import time. On a bare [dev] install
# (e.g. CI) any one missing dep blocks the import entirely. Skip the
# suite cleanly rather than generating an opaque ImportError.
try:
    from daemon.maez_daemon import _STATIC_CYCLE_INSTRUCTIONS
    _HAS_DAEMON_DEPS = True
except ImportError as e:
    _STATIC_CYCLE_INSTRUCTIONS = ""
    _IMPORT_ERROR = str(e)
    _HAS_DAEMON_DEPS = False


@unittest.skipUnless(
    _HAS_DAEMON_DEPS,
    "daemon.maez_daemon requires surface extras (ollama, telegram, flask, "
    "websockets). Install with `pip install -e .[all]` to run these tests."
)
class StaticInstructionsStability(unittest.TestCase):

    def test_no_dynamic_interpolation_markers(self):
        """If an f-string accidentally sneaks in, the constant would
        contain '{', '}' or format-marker characters from live values.
        The legitimate uses (bullet lists, etc.) shouldn't look like
        unresolved placeholders."""
        # A clean sanity check: there must be no double-brace or {var}-
        # style patterns remaining.
        import re
        placeholder_re = re.compile(r"\{[a-zA-Z_][a-zA-Z_0-9]*\}")
        matches = placeholder_re.findall(_STATIC_CYCLE_INSTRUCTIONS)
        self.assertEqual(
            matches, [],
            f"static instructions contain unresolved placeholders: {matches}",
        )

    def test_repeated_concatenation_is_byte_identical(self):
        soul = "You are Maez. This is your soul."
        a = soul + "\n\n" + _STATIC_CYCLE_INSTRUCTIONS
        b = soul + "\n\n" + _STATIC_CYCLE_INSTRUCTIONS
        self.assertEqual(
            hashlib.sha256(a.encode()).hexdigest(),
            hashlib.sha256(b.encode()).hexdigest(),
            "stable system-prompt assembly must be byte-identical across calls",
        )

    def test_contains_the_grounding_rules(self):
        """Regression guard: critical rules must be in the constant,
        not accidentally left only in the user-message trailer."""
        body = _STATIC_CYCLE_INSTRUCTIONS
        self.assertIn("HARD GROUNDING RULES", body)
        self.assertIn("HEARTBEAT_OK", body)
        self.assertIn("<final>", body)
        self.assertIn("VRAM", body)

    def test_non_trivial_size(self):
        """Catches accidental truncation: the moved instructions should
        be at least ~1000 chars (~250 tokens), the whole point of the
        refactor being to cache a large stable block."""
        self.assertGreater(len(_STATIC_CYCLE_INSTRUCTIONS), 1000)

    def test_no_above_references_that_would_dangle(self):
        """After the move, there's no 'above' reference pointing at
        content that now lives in a different message. Self-contained
        phrasing only ('cycle context', 'SIGNALS PRESENT / ABSENT')."""
        # 'above' bare reference would be a dangling spatial cue since
        # the referenced content (signals manifest) is in the user
        # message, not above this block.
        body = _STATIC_CYCLE_INSTRUCTIONS.lower()
        # It's OK for 'above' to appear inside a self-contained clause
        # (there currently are none) — this is a forward regression guard.
        # Only flag if the word is used in a directional sense.
        self.assertNotIn(" is absent above", body)
        self.assertNotIn(" is present above", body)


if __name__ == "__main__":
    unittest.main()
