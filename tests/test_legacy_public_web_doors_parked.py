import os
import re
import subprocess
import sys
import textwrap
import unittest
from unittest import mock

os.environ.setdefault("MAEZ_IPHONE_INGEST_TOKEN", "dummy-test-token")
os.environ.setdefault("MAEZ_SECRETS_DISABLE_NEW_LOADER", "1")
# Keep the ambient module import hermetic even on machines where the
# feature flag is enabled in owner-local config.
os.environ["MAEZ_LIVE_FAST_LANE_ENABLED"] = "0"

import skills.web_interface as wi


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(wi.__file__), ".."))


class LegacyDoorParkingTests(unittest.TestCase):
    def setUp(self):
        self.client = wi.app.test_client()

    def assert_parked_json(self, response):
        self.assertEqual(response.status_code, 410)
        payload = response.get_json()
        self.assertIsInstance(payload, dict)
        self.assertEqual(payload.get("error"), "legacy_surface_parked")
        self.assertIn("/cockpit", payload.get("message", ""))

    def assert_parked_page(self, response):
        self.assertIn(response.status_code, (302, 410))
        if response.status_code == 302:
            self.assertEqual(response.headers["Location"].rstrip("/"), "/cockpit")
        else:
            self.assert_parked_json(response)

    def test_auth_and_chat_doors_are_parked(self):
        self.assert_parked_page(self.client.get("/login"))
        self.assert_parked_json(self.client.post("/login", json={"username": "r", "password": "x"}))
        self.assert_parked_json(self.client.post("/register", json={"username": "r", "password": "xxxx"}))
        self.assert_parked_json(
            self.client.post("/link-telegram", json={"web_token": "t", "telegram_id": "1"})
        )
        self.assert_parked_json(self.client.post("/chat", json={"web_token": "t", "message": "hello"}))

    def test_read_doors_are_parked_without_state_leak(self):
        for path in (
            "/history",
            "/status",
            "/api/maez-state",
            "/api/session-timeline",
            "/api/analytics-summary",
        ):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assert_parked_json(response)
                body = response.get_data(as_text=True).lower()
                self.assertNotIn("memory_count", body)
                self.assertNotIn("sessions", body)
                self.assertNotIn("soul", body)
                self.assertNotIn("daemon", body)

    def test_journal_and_old_local_pages_are_parked(self):
        for path in ("/journal", "/planner", "/analytics"):
            with self.subTest(path=path):
                self.assert_parked_page(self.client.get(path))

    def test_old_write_apis_are_parked(self):
        self.assert_parked_json(self.client.post("/api/analytics", json={"event": "pageview", "path": "/"}))
        self.assert_parked_json(self.client.get("/api/planner-board"))
        self.assert_parked_json(self.client.post("/api/planner-board", json={"items": []}))

    def test_parking_wins_before_untrusted_origin_write_guard(self):
        headers = {"Origin": "https://example.invalid"}
        self.assert_parked_json(
            self.client.post("/chat", json={"web_token": "t", "message": "hello"}, headers=headers)
        )
        self.assert_parked_json(self.client.post("/api/planner-board", json={"items": []}, headers=headers))

    def test_debug_read_doors_are_parked(self):
        for path in ("/debug", "/debug/flow", "/debug/flow/static", "/debug/card-default"):
            with self.subTest(path=path):
                self.assert_parked_page(self.client.get(path))
        for path in (
            "/api/debug/services",
            "/api/debug/wonderings",
            "/api/debug/canary-leaks",
            "/api/debug/trace-labels",
            "/api/debug/memory-view",
            "/api/debug/pursuit-decisions",
            "/api/debug/wondering-events",
            "/api/debug/cycle-timeline",
            "/api/debug/cards",
            "/api/debug/recent-shells",
            "/api/debug/fabrication-feed",
            "/api/debug/stats",
        ):
            with self.subTest(path=path):
                self.assert_parked_json(self.client.get(path))

    def test_progress_board_remains_public_projection_only(self):
        with mock.patch.object(
            wi,
            "_load_planner_board",
            return_value={
                "updated_at": "2026-06-28T00:00:00Z",
                "items": [
                    {
                        "id": "public-1",
                        "title": "public title",
                        "status": "planned",
                        "summary": "public summary",
                        "details": "public details",
                        "tags": ["public"],
                        "updated_at": "2026-06-28T00:00:00Z",
                        "visibility": "public",
                    },
                    {
                        "id": "private-1",
                        "title": "SECRET PRIVATE TITLE",
                        "status": "planned",
                        "summary": "SECRET PRIVATE SUMMARY",
                        "details": "SECRET PRIVATE DETAILS",
                        "tags": ["private"],
                        "updated_at": "2026-06-28T00:00:00Z",
                        "visibility": "private",
                    },
                ],
            },
        ):
            response = self.client.get("/api/progress-board")
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("public title", body)
        self.assertNotIn("SECRET PRIVATE", body)

    def test_iphone_ingest_is_token_auth_local_integration_not_account_app(self):
        missing = self.client.post("/api/iphone/ingest", json={"kind": "battery"})
        self.assertIn(missing.status_code, (401, 403))
        with mock.patch("skills.iphone_ingest.ingest", return_value=({"ok": True}, 200)) as ingest:
            response = self.client.post(
                "/api/iphone/ingest",
                json={"kind": "battery"},
                headers={"X-Maez-Token": "dummy-test-token"},
            )
        self.assertEqual(response.status_code, 200)
        ingest.assert_called_once()
        payload, token = ingest.call_args.args
        self.assertEqual(token, "dummy-test-token")
        self.assertNotIn("web_token", payload)

    def test_fast_reply_absent_when_feature_flag_off(self):
        code = textwrap.dedent(
            """
            import os
            os.environ["MAEZ_SECRETS_DISABLE_NEW_LOADER"] = "1"
            os.environ["MAEZ_IPHONE_INGEST_TOKEN"] = "dummy-test-token"
            os.environ["MAEZ_LIVE_FAST_LANE_ENABLED"] = "0"
            import skills.web_interface as wi
            print(any(rule.rule == "/v1/fast-reply" for rule in wi.app.url_map.iter_rules()))
            """
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertEqual(result.stdout.strip(), "False")

    def test_fast_reply_parked_when_feature_flag_on(self):
        code = textwrap.dedent(
            """
            import os
            os.environ["MAEZ_SECRETS_DISABLE_NEW_LOADER"] = "1"
            os.environ["MAEZ_IPHONE_INGEST_TOKEN"] = "dummy-test-token"
            os.environ["MAEZ_LIVE_FAST_LANE_ENABLED"] = "1"
            import skills.web_interface as wi
            c = wi.app.test_client()
            r = c.post("/v1/fast-reply", json={"web_token": "t", "message": "hello"})
            print(r.status_code)
            print(r.get_data(as_text=True))
            """
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertIn("410", result.stdout.splitlines()[0])
        self.assertIn("legacy_surface_parked", result.stdout)


class OwnerSurfaceTests(unittest.TestCase):
    def setUp(self):
        self.client = wi.app.test_client()

    def test_cockpit_pages_still_serve(self):
        self.assertEqual(self.client.get("/cockpit").status_code, 200)
        self.assertEqual(self.client.get("/cockpit/s7-webauthn-proof").status_code, 200)

    def test_api_v1_state_routes_require_owner_or_loopback_gate(self):
        checks = (
            ("GET", "/api/v1/daemon/state", None),
            ("GET", "/api/v1/s7/webauthn/status", None),
            ("GET", "/api/v1/cards", None),
            ("POST", "/api/v1/cards/request-1/deny", {}),
            ("POST", "/api/v1/cards/request-1/approve", {}),
            ("GET", "/api/v1/services", None),
            ("GET", "/api/v1/gpu", None),
            ("GET", "/api/v1/signals", None),
            ("GET", "/api/v1/soul", None),
            ("GET", "/api/v1/memory", None),
            ("GET", "/api/v1/lived-memory", None),
            ("GET", "/api/v1/lived-memory/episodes", None),
            ("GET", "/api/v1/lived-memory/graph", None),
            ("GET", "/api/v1/lived-memory/echoes", None),
            ("GET", "/api/v1/lived-memory/predictions", None),
            ("GET", "/api/v1/lived-memory/brief?query=hello", None),
            ("GET", "/api/v1/turn/latest", None),
            ("GET", "/api/v1/now", None),
            ("GET", "/api/v1/rail/timeline", None),
            ("GET", "/api/v1/dreams", None),
            ("GET", "/api/v1/quality", None),
            ("GET", "/api/v1/workshop/sessions", None),
            ("POST", "/api/v1/workshop/sessions", {"title": "probe"}),
            ("GET", "/api/v1/workshop/session/session-1", None),
            ("POST", "/api/v1/workshop/session/session-1/turn", {"message": "hi"}),
            ("POST", "/api/v1/workshop/session/session-1/model", {"model": "probe"}),
            ("POST", "/api/v1/workshop/session/session-1/apply", {"reviewed": True}),
            ("DELETE", "/api/v1/workshop/session/session-1", None),
            ("POST", "/api/v1/self_dev/concern/1/resolve", {}),
            ("GET", "/api/v1/self_dev", None),
            ("GET", "/api/v1/identity", None),
            ("GET", "/api/v1/router", None),
            ("GET", "/api/v1/logs/maez", None),
            ("POST", "/api/v1/dreams/1/approve", {}),
            ("GET", "/api/v1/chat/sessions", None),
        )
        with mock.patch.object(wi, "_owner_private_auth_ok", return_value=False):
            for method, path, json_body in checks:
                with self.subTest(method=method, path=path):
                    response = self.client.open(path, method=method, json=json_body)
                    self.assertEqual(response.status_code, 401)
                    self.assertEqual(response.get_json().get("error"), "owner_auth_required")

    def test_s7_status_still_uses_existing_proxy_shape(self):
        import os

        with mock.patch.object(wi, "_owner_private_auth_ok", return_value=True), \
                mock.patch.dict(os.environ, {"S7_INTERNAL_CHANNEL_TOKEN": "doors-test-token"}, clear=False):
            with mock.patch("urllib.request.urlopen") as urlopen:
                response = mock.Mock()
                response.status = 200
                response.headers = {"Content-Type": "application/json"}
                response.read.return_value = b'{"ok": true, "enrolled": false}'
                response.__enter__ = mock.Mock(return_value=response)
                response.__exit__ = mock.Mock(return_value=None)
                urlopen.return_value = response
                result = self.client.get("/api/v1/s7/webauthn/status")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.get_json()["enrolled"], False)


class KeptCosmeticPageLinkTests(unittest.TestCase):
    def test_kept_cosmetic_pages_do_not_link_to_parked_doors(self):
        pages = (
            "ui/index.html",
            "ui/progress_public.html",
            "ui/privacy.html",
        )
        parked_patterns = (
            r'(href|action|fetch)\s*\(?[\'"]/(login|chat|history|journal|planner|analytics)[\'"/?]',
            r'fetch\([\'"]/(status|api/maez-state|api/session-timeline|api/analytics-summary|api/planner-board)[\'"?]',
            r'window\.location(\.href)?\s*=\s*[\'"]/(login|chat|history|journal|planner|analytics)[\'"/?]',
        )
        for page in pages:
            with self.subTest(page=page):
                with open(os.path.join(REPO_ROOT, page), encoding="utf-8") as fh:
                    html = fh.read()
                for pattern in parked_patterns:
                    self.assertIsNone(
                        re.search(pattern, html),
                        f"{page} still points at parked route via {pattern}",
                    )

    def test_kept_cosmetic_pages_do_not_load_scripts_that_call_parked_doors(self):
        pages = (
            "ui/index.html",
            "ui/progress_public.html",
            "ui/privacy.html",
        )
        parked_api_patterns = (
            r"[\"']/(api/analytics|api/planner-board|api/analytics-summary)[\"']",
            r"fetch\([\"']/(status|api/maez-state|api/session-timeline)[\"']",
            r"sendBeacon\([A-Z_]*PATH",
        )
        for page in pages:
            with self.subTest(page=page):
                with open(os.path.join(REPO_ROOT, page), encoding="utf-8") as fh:
                    html = fh.read()
                script_srcs = re.findall(r"<script[^>]+src=[\"']([^\"']+)[\"']", html)
                for src in script_srcs:
                    if not src.startswith("/") or src.startswith("//"):
                        continue
                    script_path = os.path.join(REPO_ROOT, "ui", os.path.basename(src.split("?", 1)[0]))
                    with open(script_path, encoding="utf-8") as script_fh:
                        script = script_fh.read()
                    for pattern in parked_api_patterns:
                        self.assertIsNone(
                            re.search(pattern, script),
                            f"{page} loads {src}, which still calls a parked route via {pattern}",
                        )

    def test_landing_page_does_not_fabricate_retired_live_status(self):
        with open(os.path.join(REPO_ROOT, "ui/index.html"), encoding="utf-8") as fh:
            html = fh.read()
        self.assertNotIn('id="lastThoughtTime"', html)
        self.assertNotIn('id="lastThoughtPreview"', html)
        self.assertNotIn("watching, remembering", html)
        self.assertNotIn("a few", html)
        self.assertNotIn("growing", html)

    def test_kept_pages_do_not_advertise_parked_guest_or_account_surfaces(self):
        stale_copy = {
            "ui/index.html": (
                "Talk briefly with the first Maez as a guest",
                "Sign in as a guest",
            ),
            "ui/privacy.html": (
                "Anonymous pageviews &amp; button clicks",
                "What the site analytics collects",
                "Your conversation with Maez (so it can remember you)",
                "Stored per-account",
                "If you create an account",
                "Analytics still sees the anonymous pageview",
                "The public Telegram bot and the web channel are separate doorways",
            ),
        }
        for page, snippets in stale_copy.items():
            with self.subTest(page=page):
                with open(os.path.join(REPO_ROOT, page), encoding="utf-8") as fh:
                    html = fh.read()
                for snippet in snippets:
                    self.assertNotIn(snippet, html)


if __name__ == "__main__":
    unittest.main()
