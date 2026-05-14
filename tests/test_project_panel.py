# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Source-level contract tests for the local project panel."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


class ProjectPanelContractTests(unittest.TestCase):
    def test_daemon_exposes_separate_project_panel_routes(self):
        src = (_REPO / "daemon" / "maez_daemon.py").read_text()

        self.assertIn('@app.route("/project-panel")', src)
        self.assertIn('@app.route("/project-panel/state")', src)
        self.assertIn('@app.route("/project-panel/doc/<path:doc_path>")', src)
        self.assertIn('send_file(str(BASE_DIR / "ui" / "project_panel.html"))', src)
        self.assertIn('BASE_DIR / "docs" / "project-panel" / "state.json"', src)
        self.assertIn('target.relative_to(docs_root)', src)

    def test_project_panel_state_is_minimal_and_readable(self):
        state_path = _REPO / "docs" / "project-panel" / "state.json"

        state = json.loads(state_path.read_text())

        self.assertEqual(state["schema_version"], "1.0")
        self.assertIn("observation_gates", state)
        self.assertIn("open_wounds", state)
        self.assertIn("next_moves", state)
        self.assertIn("do_not_touch_yet", state)
        self.assertIn("links", state)

        gate_ids = {gate["id"] for gate in state["observation_gates"]}
        self.assertIn("m1-lived-episode-promotion", gate_ids)
        self.assertIn("ars-audit-rewrite", gate_ids)
        self.assertIn("trf-temporal-recall", gate_ids)
        self.assertIn("s1b-private-thoughts", gate_ids)

        wound_ids = {wound["id"] for wound in state["open_wounds"]}
        self.assertIn("daemon-cycle-stuck", wound_ids)
        self.assertIn("sigterm-sigkill-shutdown", wound_ids)

    def test_project_panel_page_consumes_health_and_state_without_external_assets(self):
        page = (_REPO / "ui" / "project_panel.html").read_text()

        self.assertIn("<title>Maez · Project Panel</title>", page)
        self.assertIn("fetch('/health'", page)
        self.assertIn("fetch('/project-panel/state'", page)
        self.assertIn("/project-panel/doc/", page)
        self.assertIn("id=\"liveCards\"", page)
        self.assertIn("id=\"observationGates\"", page)
        self.assertIn("id=\"openWounds\"", page)
        self.assertIn("id=\"nextMoves\"", page)
        self.assertNotIn("cdnjs", page)
        self.assertNotIn("fonts.googleapis", page)

    def test_health_exposes_reasoning_loop_heartbeat_fields(self):
        src = (_REPO / "daemon" / "maez_daemon.py").read_text()

        self.assertIn("self._cycle_stage", src)
        self.assertIn("self._mark_cycle_stage(", src)
        self.assertIn("def _cycle_heartbeat_health(self)", src)
        self.assertIn('"reasoning_loop": self._cycle_heartbeat_health()', src)
        self.assertIn('"cycle_age_seconds"', src)
        self.assertIn('"cycle_stalled"', src)
        self.assertIn('"stage"', src)
        self.assertIn('"stage_age_seconds"', src)

    def test_project_panel_displays_reasoning_loop_heartbeat(self):
        page = (_REPO / "ui" / "project_panel.html").read_text()

        self.assertIn("id=\"liveHeartbeat\"", page)
        self.assertIn("h.reasoning_loop", page)
        self.assertIn("cycle_stalled", page)
        self.assertIn("cycle_age_seconds", page)


if __name__ == "__main__":
    unittest.main()
