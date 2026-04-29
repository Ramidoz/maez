#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Rohit Ananthan

import unittest


class ReadFileToolTolerance(unittest.TestCase):
    def test_read_file_ignores_extra_reason_kwarg(self):
        """The Telegram tool loop often includes a human reason field.

        read_file is read-only and should tolerate that extra field instead
        of failing the whole autonomy turn with TypeError.
        """
        from core.action_engine import ActionEngine

        ae = ActionEngine.__new__(ActionEngine)  # bypass __init__
        result = ActionEngine._do_read_file(
            ae,
            path="/home/rohit/maez/skills/web_interface.py",
            reason="inspect the route definition",
        )
        self.assertIn("web_interface.py", result)
        self.assertIn("import", result)


if __name__ == "__main__":
    unittest.main()
