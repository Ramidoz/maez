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
