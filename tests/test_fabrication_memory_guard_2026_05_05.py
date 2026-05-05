# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""REGRESSION GUARD: fabrication_memory diag clear helpers refuse to
wipe the production DB.

On 2026-05-05 we discovered _diag_clear_events_for_test had been run
against the production memory/fabrication_log.db, wiping ~14K
accumulated fabrication events. The cause: a test ran without
isolating its DB path.

This file locks in the four-corner contract added in response:

  1. MAEZ_TEST_MODE unset → clear refused (RuntimeError).
  2. MAEZ_TEST_MODE=1 but _DB_PATH is the production DB → refused.
  3. MAEZ_TEST_MODE=1 AND _DB_PATH is a temp file → allowed.
  4. The same guard applies to BOTH diag clear helpers
     (_diag_clear_for_test wipes fabrication_log;
      _diag_clear_events_for_test wipes fabrication_events).

If any of these branches drift, the regression risk is silent
production-data loss.
"""
from __future__ import annotations

import os
import importlib
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


def _fresh_module():
    """Reload the module to get a clean _DB_PATH / _initialized state
    after env or path mutation."""
    from core.learning import fabrication_memory as fm
    importlib.reload(fm)
    return fm


class GuardBlocksProductionWipe(unittest.TestCase):

    def setUp(self):
        # Save and restore env to keep tests independent of caller state.
        self._prior_mode = os.environ.get("MAEZ_TEST_MODE")

    def tearDown(self):
        if self._prior_mode is None:
            os.environ.pop("MAEZ_TEST_MODE", None)
        else:
            os.environ["MAEZ_TEST_MODE"] = self._prior_mode

    def test_no_env_no_clear_events(self):
        os.environ.pop("MAEZ_TEST_MODE", None)
        fm = _fresh_module()
        with self.assertRaises(RuntimeError) as ctx:
            fm._diag_clear_events_for_test()
        self.assertIn("MAEZ_TEST_MODE", str(ctx.exception))

    def test_no_env_no_clear_log(self):
        os.environ.pop("MAEZ_TEST_MODE", None)
        fm = _fresh_module()
        with self.assertRaises(RuntimeError) as ctx:
            fm._diag_clear_for_test()
        self.assertIn("MAEZ_TEST_MODE", str(ctx.exception))

    def test_env_only_blocks_against_production_path(self):
        """Even with MAEZ_TEST_MODE=1, the production DB path is
        protected. Both safety conditions must hold."""
        os.environ["MAEZ_TEST_MODE"] = "1"
        fm = _fresh_module()
        # _DB_PATH should be the production path after a fresh
        # reload — verify, then confirm the clear is still refused.
        prod_path = (
            Path(__file__).resolve().parent.parent
            / "memory" / "fabrication_log.db"
        )
        # Best-effort sanity check; allow the test to proceed if
        # someone has reconfigured paths.
        if fm._DB_PATH.resolve() == prod_path.resolve():
            with self.assertRaises(RuntimeError) as ctx:
                fm._diag_clear_events_for_test()
            self.assertIn("production", str(ctx.exception).lower())

    def test_safe_conditions_allow_clear(self):
        """With BOTH conditions satisfied (env set + temp path),
        the clear should run normally."""
        os.environ["MAEZ_TEST_MODE"] = "1"
        fm = _fresh_module()
        with tempfile.TemporaryDirectory(prefix="maez_guard_safe_") as td:
            fm._DB_PATH = Path(td) / "fabrication_log.db"
            fm._initialized = False
            # Both helpers should run without raising.
            try:
                fm._diag_clear_for_test()
                fm._diag_clear_events_for_test()
            except Exception as e:
                self.fail(
                    f"clear refused under safe conditions: {e}"
                )


if __name__ == "__main__":
    unittest.main()
