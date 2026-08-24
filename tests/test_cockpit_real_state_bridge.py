"""Tests for the face real-state bridge (coherence-assembly campaign).

Covenant: the cockpit must show REAL substrate state, never fabricated inner
life. These tests pin:
  - the daemon JSON-assembly helper `_build_cockpit_state(daemon)` reads real
    retained attrs and NEVER emits mood/uncertainty (no organ for them);
  - the web proxy is flag-gated (MAEZ_COCKPIT_REAL_STATE strict), flag-off keeps
    the log-scrape shape, flag-on proxies the daemon verbatim with an honest
    unreachable fallback;
  - COCKPIT_DIR resolves repo-relative (env override respected).

Runner:
  /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_cockpit_real_state_bridge -v
"""

import json
import os
import unittest
from types import SimpleNamespace
from unittest import mock


# ── fakes ────────────────────────────────────────────────────────────────


class _FakeDaemon:
    """A stand-in daemon carrying the real retain attrs the helper reads."""

    def __init__(self):
        self.running = True
        self.boot_time = "2026-06-13T00:00:00+00:00"
        self.cycle_count = 42
        self.last_cycle_time = "2026-06-13T00:10:00+00:00"
        self._last_cycle_text = "the substrate is quiet; nothing wants my hands."
        self._last_valence_reading = {
            "sign": "neutral",
            "magnitude": "none",
            "telemetry": "given the substrate signals I can see, this state appears NONE NEUTRAL; no setpoint moved.",
            "reasons": [],
        }
        self._last_cog_metadata = {
            "cog_score": 73,
            "cog_primary": "actionable",
            "cog_labels": "actionable,insightful",
            "cog_topic": "cpu_load",
            "cog_retried": "improved",
        }
        self._last_recall_receipt = SimpleNamespace(
            receipt="on_ok", at_ts=1234567.0, boot_id="2026-06-13T00:00:00+00:00"
        )

    # health helpers the real daemon provides
    def _cycle_heartbeat_health(self):
        return {"state": "alive", "cycles": self.cycle_count}

    def _health_status_from_reasoning_loop(self, reasoning_loop):
        return "ok" if reasoning_loop.get("state") == "alive" else "degraded"

    def _watchdog_health(self):
        return {"state": "clear"}

    def _voice_continuity_health(self):
        return {"state": "continuous"}


def _build_state_under_patches(daemon):
    """Call the helper with the module-level health fns patched to be cheap."""
    from daemon import maez_daemon as md

    with mock.patch.object(md, "temporal_spine_health", return_value={"ok": True}), \
        mock.patch.object(md, "clinical_boundary_health", return_value={"ok": True}):
        return md._build_cockpit_state(daemon)


# ── Part 1/2: helper reads real fields, omits theater ─────────────────────


class TestBuildCockpitState(unittest.TestCase):
    def test_real_fields_present(self):
        state = _build_state_under_patches(_FakeDaemon())
        self.assertEqual(state["cycle_count"], 42)
        self.assertEqual(state["last_thought"],
                         "the substrate is quiet; nothing wants my hands.")
        self.assertEqual(state["status"], "ok")
        self.assertTrue(state["running"])
        self.assertEqual(state["last_cycle"], "2026-06-13T00:10:00+00:00")
        # legacy cognition-score metadata is no longer a live cockpit signal
        self.assertIsNone(state["cognition"])
        # valence retained verbatim from the reading telemetry
        self.assertEqual(state["valence"]["sign"], "neutral")
        # recall receipt fields surfaced
        self.assertEqual(state["recall"]["receipt"], "on_ok")
        # sampled_at present and numeric
        self.assertIsInstance(state["sampled_at"], float)

    def test_no_fabricated_inner_life_keys(self):
        state = _build_state_under_patches(_FakeDaemon())
        self.assertNotIn("mood", state)
        self.assertNotIn("uncertainty", state)

    def test_flags_dict_present(self):
        with mock.patch.dict(os.environ, {"MAEZ_LIVED_RECALL": "1"}, clear=False):
            state = _build_state_under_patches(_FakeDaemon())
        self.assertIsInstance(state["flags"], dict)
        self.assertIn("MAEZ_LIVED_RECALL", state["flags"])

    def test_missing_attrs_yield_null_not_crash(self):
        bare = SimpleNamespace(
            running=False,
            boot_time=None,
            cycle_count=0,
            last_cycle_time=None,
            _cycle_heartbeat_health=lambda: {"state": "boot"},
            _health_status_from_reasoning_loop=lambda rl: "starting",
        )
        # no _last_cycle_text / _last_valence_reading / etc.
        state = _build_state_under_patches(bare)
        self.assertIsNone(state["last_thought"])
        self.assertIsNone(state["valence"])
        self.assertIsNone(state["cognition"])
        self.assertIsNone(state["recall"])
        # serializable
        json.dumps(state)


# ── Part 1: retain attrs default init ─────────────────────────────────────


class TestRetainAttrInit(unittest.TestCase):
    def test_valence_reading_to_telemetry_dict(self):
        """The helper that converts a ValenceReading into the retained dict
        keeps only honest fields (sign/magnitude/telemetry/reasons)."""
        from daemon import maez_daemon as md
        from core.evolution.valence.reading import (
            ValenceReading, Sign, Magnitude, Contribution,
        )
        reading = ValenceReading(
            sign=Sign.POSITIVE,
            magnitude=Magnitude.MILD,
            contributions=(
                Contribution(setpoint="x", sign=Sign.POSITIVE,
                             reason="a want resolved", evidence={}),
            ),
        )
        out = md._valence_reading_to_telemetry(reading)
        self.assertEqual(out["sign"], "positive")
        self.assertEqual(out["magnitude"], "mild")
        self.assertIn("a want resolved", out["reasons"])
        self.assertIn("positive", out["telemetry"].lower())

    def test_none_reading_returns_none(self):
        from daemon import maez_daemon as md
        self.assertIsNone(md._valence_reading_to_telemetry(None))


# ── Part 3: web proxy flag gate ───────────────────────────────────────────


class TestWebProxyFlag(unittest.TestCase):
    def _client(self):
        import skills.web_interface as wi
        wi.app.config["TESTING"] = True
        return wi, wi.app.test_client()

    def test_default_is_the_honest_proxy_not_the_scrape(self):
        """Flipped 2026-08-14 (full-body audit): the fabricating scrape
        was the default while the honest proxy sat behind a flag. Real
        state is now the default; no flag required."""
        wi, client = self._client()
        real_payload = {"status": "ok", "cycle_count": 3}

        class _Resp:
            def __init__(self, data):
                self._data = json.dumps(data).encode()
            def read(self):
                return self._data
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False

        with mock.patch.object(wi, "_owner_private_auth_ok", return_value=True), \
                mock.patch.dict(os.environ, {"S7_INTERNAL_CHANNEL_TOKEN": "test-tok"}, clear=False):
            os.environ.pop("MAEZ_COCKPIT_REAL_STATE", None)
            os.environ.pop("MAEZ_COCKPIT_LEGACY_SCRAPE", None)
            with mock.patch("urllib.request.urlopen", return_value=_Resp(real_payload)):
                resp = client.get("/api/v1/daemon/state")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json(), real_payload)

    def test_legacy_scrape_needs_explicit_flag_and_invents_no_mood(self):
        wi, client = self._client()
        with mock.patch.object(wi, "_owner_private_auth_ok", return_value=True), \
                mock.patch.dict(os.environ, {"MAEZ_COCKPIT_LEGACY_SCRAPE": "1"}, clear=False):
            with mock.patch.object(wi, "_tail_log_lines", return_value=[]):
                resp = client.get("/api/v1/daemon/state")
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        # log-scrape shape carries these keys
        self.assertIn("cycle", body)
        self.assertIn("scratchpad", body)
        self.assertIn("sampledAt", body)
        # De-fabricated: with no real source, mood is unknown, not
        # "attentive".
        self.assertIsNone(body.get("mood"))

    def test_flag_on_proxies_daemon_verbatim(self):
        wi, client = self._client()
        real_payload = {"status": "ok", "cycle_count": 7, "last_thought": "hi"}

        class _Resp:
            def __init__(self, data):
                self._data = json.dumps(data).encode()
            def read(self):
                return self._data
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False

        with mock.patch.object(wi, "_owner_private_auth_ok", return_value=True), \
                mock.patch.dict(os.environ, {"MAEZ_COCKPIT_REAL_STATE": "1", "S7_INTERNAL_CHANNEL_TOKEN": "test-tok"}, clear=False):
            with mock.patch("urllib.request.urlopen", return_value=_Resp(real_payload)):
                resp = client.get("/api/v1/daemon/state")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json(), real_payload)

    def test_flag_on_unreachable_is_honest(self):
        wi, client = self._client()
        with mock.patch.object(wi, "_owner_private_auth_ok", return_value=True), \
                mock.patch.dict(os.environ, {"MAEZ_COCKPIT_REAL_STATE": "1", "S7_INTERNAL_CHANNEL_TOKEN": "test-tok"}, clear=False):
            with mock.patch("urllib.request.urlopen", side_effect=OSError("refused")):
                resp = client.get("/api/v1/daemon/state")
        body = resp.get_json()
        # proxy now carries an honest reason for the unreachable state
        self.assertEqual(body["status"], "unreachable")
        self.assertEqual(body["reason"], "daemon_unreachable")
        # honest fallback NEVER carries scraped/seed data
        self.assertNotIn("mood", body)
        self.assertNotIn("scratchpad", body)

    def test_strict_flag_parser_table(self):
        from core.infra.env_flags import strict_env_flag
        truthy = ["1", "true", "yes", "on", "TRUE", "On", "YES"]
        falsy = ["0", "false", "no", "off", "", "maybe", "2"]
        for v in truthy:
            with mock.patch.dict(os.environ, {"MAEZ_COCKPIT_REAL_STATE": v}, clear=False):
                self.assertTrue(strict_env_flag("MAEZ_COCKPIT_REAL_STATE"), v)
        for v in falsy:
            with mock.patch.dict(os.environ, {"MAEZ_COCKPIT_REAL_STATE": v}, clear=False):
                self.assertFalse(strict_env_flag("MAEZ_COCKPIT_REAL_STATE"), v)


# ── Part 3b: daemon-state endpoint owner gate (always-on) ─────────────────


class DaemonStateEndpointOwnerGate(unittest.TestCase):
    def _client(self):
        import skills.web_interface as wi
        wi.app.config["TESTING"] = True
        return wi, wi.app.test_client()

    def test_non_owner_gets_401(self):
        wi, client = self._client()
        with mock.patch.object(wi, "_owner_private_auth_ok", return_value=False):
            r = client.get("/api/v1/daemon/state")
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.get_json().get("error"), "owner_auth_required")

    def test_owner_flag_on_no_token_is_unreachable_no_scrape(self):
        wi, client = self._client()
        with mock.patch.object(wi, "_owner_private_auth_ok", return_value=True), \
                mock.patch.dict(os.environ, {"MAEZ_COCKPIT_REAL_STATE": "1"}, clear=False):
            os.environ.pop("S7_INTERNAL_CHANNEL_TOKEN", None)
            r = client.get("/api/v1/daemon/state")
        self.assertEqual(r.get_json(), {"status": "unreachable", "reason": "s7_internal_channel_untrusted"})


# ── Part 4: web proxy sends the S7 internal-channel token ─────────────────


class ProxySendsS7Token(unittest.TestCase):
    def test_proxy_sends_managed_token_header(self):
        import skills.web_interface as wi
        captured = {}

        class _Resp:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self): return json.dumps({"status": "ok", "cycle_count": 7}).encode()

        def fake_urlopen(req, timeout=None):
            captured["req"] = req                  # capture the OUTGOING Request object
            return _Resp()

        with mock.patch.dict(os.environ, {"S7_INTERNAL_CHANNEL_TOKEN": "tok-123"}, clear=False), \
             mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            out = wi._daemon_cockpit_state_proxy()
        self.assertEqual(out["cycle_count"], 7)
        # the header was actually SENT (urllib title-cases the key):
        self.assertEqual(captured["req"].get_header("X-maez-s7-internal-channel"), "tok-123")

    def test_proxy_no_token_is_unreachable_with_reason(self):
        import skills.web_interface as wi
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("S7_INTERNAL_CHANNEL_TOKEN", None)
            out = wi._daemon_cockpit_state_proxy()
        self.assertEqual(out, {"status": "unreachable", "reason": "s7_internal_channel_untrusted"})

    def test_proxy_daemon_403_is_untrusted_reason(self):
        import skills.web_interface as wi
        import urllib.error
        def fake_urlopen(req, timeout=None):
            raise urllib.error.HTTPError("u", 403, "forbidden", {}, None)
        with mock.patch.dict(os.environ, {"S7_INTERNAL_CHANNEL_TOKEN": "tok"}, clear=False), \
             mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            out = wi._daemon_cockpit_state_proxy()
        self.assertEqual(out, {"status": "unreachable", "reason": "s7_internal_channel_untrusted"})

    def test_proxy_daemon_down_is_unreachable_reason(self):
        import skills.web_interface as wi
        with mock.patch.dict(os.environ, {"S7_INTERNAL_CHANNEL_TOKEN": "tok"}, clear=False), \
             mock.patch("urllib.request.urlopen", side_effect=OSError("refused")):
            out = wi._daemon_cockpit_state_proxy()
        self.assertEqual(out["status"], "unreachable")
        self.assertEqual(out["reason"], "daemon_unreachable")


# ── Part 5: COCKPIT_DIR hermetic-path fix ─────────────────────────────────


class TestCockpitDir(unittest.TestCase):
    def test_resolves_repo_relative(self):
        import skills.web_interface as wi
        self.assertTrue(
            wi.COCKPIT_DIR.endswith(os.path.join("web", "cockpit")),
            wi.COCKPIT_DIR,
        )
        # under the repo root (parent of skills/)
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(wi.__file__)))
        self.assertTrue(
            os.path.abspath(wi.COCKPIT_DIR).startswith(repo_root),
            f"{wi.COCKPIT_DIR} not under {repo_root}",
        )

    def test_env_override_respected(self):
        import importlib
        with mock.patch.dict(os.environ, {"MAEZ_COCKPIT_DIR": "/tmp/custom/cockpit"}, clear=False):
            import skills.web_interface as wi
            importlib.reload(wi)
            self.assertEqual(wi.COCKPIT_DIR, "/tmp/custom/cockpit")
        # restore default for other tests
        import skills.web_interface as wi2
        importlib.reload(wi2)


# ── Part 6: ledger admission liveness on the real-state surface ──────────
#
# Council ruling 1 (2026-08-24): "a loud unclaimed/aging-entries report
# wired into the same real-state surface as dead_letter_status(). A spool
# nobody drains is a silent-omission machine with excellent durability."


class TestLedgerAdmissionRealState(unittest.TestCase):
    def test_cockpit_state_carries_ledger_admission_health(self):
        state = _build_state_under_patches(_FakeDaemon())
        adm = state["ledger_admission"]
        self.assertIsNotNone(adm, "admission liveness must be surfaced")
        for key in ("dead_letter", "spool", "writes_enabled",
                    "drainer_thread_alive", "attention"):
            self.assertIn(key, adm)
        # Unborn live tree: nothing pending, nothing dead-lettered,
        # writes disabled — no attention.
        self.assertFalse(adm["attention"])

    def test_attention_fires_on_dead_letters(self):
        import tempfile
        from pathlib import Path

        from daemon import maez_daemon as md

        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "ledger.db"
            db.touch()
            # A dead-letter sidecar with one omitted life-event.
            (Path(td) / "ledger.db.deadletter.999.jsonl").write_text(
                json.dumps({"event_id": "x", "ts": 1.0,
                            "category": "failed"}) + "\n"
            )
            with mock.patch.object(md, "LEDGER_DB_PATH", db):
                state = _build_state_under_patches(_FakeDaemon())
        adm = state["ledger_admission"]
        self.assertEqual(adm["dead_letter"]["rows"], 1)
        self.assertTrue(
            adm["attention"],
            "omitted life pending replay must demand attention",
        )

    def test_attention_fires_on_pending_spool_with_no_drainer(self):
        import tempfile
        from pathlib import Path

        from core.ledger import spool as spool_mod
        from daemon import maez_daemon as md

        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "ledger.db"
            db.touch()
            spool_mod.enqueue(
                spool_mod.default_spool_root(str(db)),
                producer="web",
                turn_kind="user_message",
                raw_text="waiting for a drainer that is not running",
                kwargs={"surface": "web_owner",
                        "taint_labels": ["owner_utterance"],
                        "privacy_access": "public"},
            )
            with mock.patch.object(md, "LEDGER_DB_PATH", db):
                state = _build_state_under_patches(_FakeDaemon())
        adm = state["ledger_admission"]
        self.assertEqual(adm["spool"]["pending_total"], 1)
        self.assertTrue(
            adm["attention"],
            "a pending envelope with no live drainer is the "
            "silent-omission machine — it must demand attention",
        )


if __name__ == "__main__":
    unittest.main()
