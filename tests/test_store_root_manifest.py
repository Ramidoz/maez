# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Store-root manifest — shadow-DB prevention.

Every Tier-A persistence producer must derive its default store path from
the canonical resolver (core.infra.paths) rather than a bare-relative string
that silently resolves against the process CWD. A bare-relative default such
as ``"memory/audit_log.db"`` opens a *different* file depending on where the
daemon happened to be launched from — a shadow DB. This manifest pins each
producer's default to an absolute path rooted under ``paths.home()``.

The test does PATH MATH ONLY. It never connects sqlite, never writes the
filesystem, and (critically) never auto-creates the birth-gated ledger DB or
the human-gated S7 store. Importing the producers must remain a pure no-op.
"""

from __future__ import annotations

import importlib
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from core.infra import paths


def _resolved_defaults() -> dict[str, Path]:
    """Return each Tier-A producer's resolved default store path.

    Re-imports the producer modules fresh so module-load helpers re-run
    against the currently active environment (so MAEZ_HOME redirection is
    observed).
    """
    import core.governance.s7_webauthn_bootstrap as s7
    import core.cognition.moment_assembly_diagnostic as mad
    import core.ledger.init as ledger_init

    importlib.reload(s7)
    importlib.reload(mad)
    importlib.reload(ledger_init)

    return {
        # (a) conversation_controller — default is None (lazy), resolves via
        #     the shared helper at connect time.
        "conversation_controller.audit_db_path": Path(paths.audit_log_db()),
        # (b) telegram_voice — bare fallback now routes through the helper.
        "telegram_voice.audit_db_fallback": Path(paths.audit_log_db()),
        # (c) ledger/init — birth-gated; only the PATH default changed.
        "ledger.init._DEFAULT_PATH": Path(ledger_init._DEFAULT_PATH),
        # (d) s7_webauthn_bootstrap — human-gated; only the PATH default changed.
        "s7_webauthn.DEFAULT_STORE_ROOT": Path(s7.DEFAULT_STORE_ROOT),
        # (e) moment_assembly_diagnostic.
        "moment_assembly.DEFAULT_LOG_PATH": Path(mad.DEFAULT_LOG_PATH),
    }


class StoreRootManifestTests(unittest.TestCase):
    def test_all_tier_a_defaults_absolute_under_home(self):
        for name, p in _resolved_defaults().items():
            with self.subTest(producer=name):
                self.assertTrue(
                    p.is_absolute(),
                    f"{name} default is not absolute: {p!r}",
                )
                self.assertTrue(
                    str(p).startswith(str(paths.home())),
                    f"{name} default {p!r} not under home {paths.home()!r}",
                )

    def test_conversation_controller_default_is_lazy_none(self):
        # The bare string default is gone; the signature default must be None
        # so the path is resolved lazily (against the resolver, not CWD).
        import inspect
        from core.brain.conversation_controller import ConversationController

        sig = inspect.signature(
            ConversationController.propose_next_step_from_probe
        )
        self.assertIsNone(
            sig.parameters["audit_db_path"].default,
            "audit_db_path default must be None (lazy), not a bare string",
        )

    def test_maez_home_redirects_every_producer(self):
        tmp = Path(self._make_tmp())
        with patch.dict(os.environ, {"MAEZ_HOME": str(tmp)}, clear=False):
            for name, p in _resolved_defaults().items():
                with self.subTest(producer=name):
                    self.assertTrue(
                        str(p).startswith(str(tmp)),
                        f"{name} default {p!r} did not redirect under "
                        f"MAEZ_HOME={tmp!r}",
                    )
        # Reload back to ambient env so later tests see canonical defaults.
        _resolved_defaults()

    def test_no_filesystem_state_created(self):
        # Path math must not have created the birth-gated ledger / S7 store.
        tmp = Path(self._make_tmp())
        with patch.dict(os.environ, {"MAEZ_HOME": str(tmp)}, clear=False):
            _resolved_defaults()
            self.assertFalse(
                (tmp / "memory" / "ledger.db").exists(),
                "ledger DB must NOT be created by path resolution (birth-gated)",
            )
            self.assertFalse(
                (tmp / "memory" / "s7_1_webauthn").exists(),
                "S7 store must NOT be created by path resolution (human-gated)",
            )
        _resolved_defaults()

    def _make_tmp(self) -> str:
        import tempfile

        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        return d.name


if __name__ == "__main__":
    unittest.main()
