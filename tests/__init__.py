# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Maez test suite — includes the sandboxed ActionEngine harness."""

import os
import tempfile
from pathlib import Path


_routing_observation_dir = tempfile.mkdtemp(prefix="maez_test_routing_observation_")
os.environ.setdefault(
    "MAEZ_ROUTING_OBSERVATION_DB_PATH",
    str(Path(_routing_observation_dir) / "routing_observation.db"),
)

# Test-hermeticity: keep the test suite out of Maez's real diary. The daemon
# attaches a RotatingFileHandler to logs/maez.log at import; this env var makes
# it skip that handler so test runs cannot pollute the production log. Live
# daemon never sets this, so its logging is unchanged.
os.environ.setdefault("MAEZ_DISABLE_FILE_LOG", "1")
