"""Calendar v1 legacy-disablement contract.

Decision 28 / ADR 0033 makes Calendar an S2-bounded information limb, not
raw prompt context or reminder voice. These tests are source-level where
importing the daemon would start too much machinery.
"""

from __future__ import annotations

import ast
import os
import re
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


def _read(path: str) -> str:
    return (_REPO / path).read_text(encoding="utf-8")


def _method_body(src: str, method_name: str) -> str:
    pattern = re.compile(rf"^    def {re.escape(method_name)}\(", re.MULTILINE)
    match = pattern.search(src)
    if match is None:
        raise AssertionError(f"method not found: {method_name}")
    start = match.start()
    next_method = re.search(r"^    def \w+\(", src[start + 1 :], re.MULTILINE)
    end = start + 1 + next_method.start() if next_method else len(src)
    return src[start:end]


class CalendarModeResolutionTests(unittest.TestCase):
    def test_calendar_mode_defaults_disabled(self):
        from core.information_limb.calendar_v1_config import CalendarMode, resolve_calendar_mode

        self.assertEqual(resolve_calendar_mode({}), CalendarMode.DISABLED)

    def test_v1_mode_is_explicit_and_legacy_requires_dev_gate(self):
        from core.information_limb.calendar_v1_config import CalendarMode, resolve_calendar_mode

        self.assertEqual(
            resolve_calendar_mode({"MAEZ_CALENDAR_MODE": "v1"}),
            CalendarMode.V1,
        )
        self.assertEqual(
            resolve_calendar_mode(
                {
                    "MAEZ_CALENDAR_MODE": "legacy_dev_only",
                    "MAEZ_CALENDAR_ALLOW_LEGACY_TEST_MODE": "1",
                }
            ),
            CalendarMode.LEGACY_DEV_ONLY,
        )
        with self.assertRaises(ValueError):
            resolve_calendar_mode({"MAEZ_CALENDAR_MODE": "legacy_dev_only"})
        with self.assertRaises(ValueError):
            resolve_calendar_mode({"MAEZ_CALENDAR_MODE": "legacy"})


class CalendarLegacyDisablementSourceTests(unittest.TestCase):
    def test_daemon_does_not_import_legacy_calendar_at_module_load(self):
        src = _read("daemon/maez_daemon.py")
        tree = ast.parse(src)

        top_level_imports = [
            node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))
        ]
        imported_modules = []
        for node in top_level_imports:
            if isinstance(node, ast.Import):
                imported_modules.extend(alias.name for alias in node.names)
            else:
                imported_modules.append(node.module or "")

        self.assertNotIn("skills.calendar_perception", imported_modules)

    def test_reason_prompt_never_formats_legacy_calendar_context(self):
        reason_body = _method_body(_read("daemon/maez_daemon.py"), "_reason")

        self.assertNotIn("_last_calendar_snap.format_for_context()", reason_body)
        self.assertNotIn("[CALENDAR]", reason_body)

    def test_daemon_loop_does_not_send_legacy_calendar_alerts(self):
        loop_body = _method_body(_read("daemon/maez_daemon.py"), "_loop")

        self.assertNotIn("get_alert_events", loop_body)
        self.assertNotIn("Calendar alert sent", loop_body)
        self.assertNotIn("starts in {threshold} minutes", loop_body)

    def test_calendar_observe_only_allowed_in_legacy_dev_gate(self):
        src = _read("daemon/maez_daemon.py")
        for match in re.finditer(r"calendar_observe\(", src):
            window = src[max(0, match.start() - 500) : match.start()]
            self.assertIn("_calendar_legacy_enabled", window)

    def test_memory_scoring_never_appends_legacy_calendar_text(self):
        loop_body = _method_body(_read("daemon/maez_daemon.py"), "_loop")

        self.assertNotIn("_last_calendar_snap.format_for_memory()", loop_body)
        self.assertNotIn("calendar_note", loop_body)

    def test_fast_reply_prime_perception_does_not_start_legacy_calendar_worker(self):
        src = _read("scripts/fast_reply_cli.py")

        self.assertNotIn("from skills.calendar_cache_worker import CalendarCacheWorker", src)
        self.assertNotIn("CalendarCacheWorker(cache=cache)", src)

    def test_legacy_calendar_is_not_advertised_as_active_skill(self):
        source_awareness = _read("core/memory/source_awareness.py")
        evolution_engine = _read("skills/evolution_engine.py")

        self.assertNotIn("'skills/calendar_perception.py': ['calendar']", source_awareness)
        self.assertNotIn("'skills/calendar_perception.py',", evolution_engine)
        self.assertNotIn("'calendar': 'skills/calendar_perception.py'", evolution_engine)

    def test_health_includes_content_free_calendar_v1_state(self):
        body = _method_body(_read("daemon/maez_daemon.py"), "_run_health_server")

        self.assertIn('"calendar"', body)
        self.assertIn("self._calendar_health()", body)

    def test_v1_mode_initializes_calendar_store_without_legacy_import(self):
        init_body = _method_body(_read("daemon/maez_daemon.py"), "__init__")

        self.assertIn("CalendarStore(", init_body)
        self.assertIn("self._calendar_mode == CalendarMode.V1", init_body)
        self.assertNotIn("calendar_observe()", init_body)

    def test_iphone_ingest_rejects_legacy_calendar_signals(self):
        from skills.iphone_ingest import ingest

        with patch.dict(os.environ, {"MAEZ_IPHONE_INGEST_TOKEN": "secret"}, clear=False):
            response, status = ingest(
                {
                    "kind": "calendar",
                    "data": {
                        "title": "Therapy with Sarah",
                        "location": "Private clinic",
                    },
                },
                provided_token="secret",
            )

        self.assertEqual(status, 400)
        self.assertIn("unknown kind", response["error"])

    def test_ambient_prompt_block_never_renders_calendar_signal_content(self):
        from core.memory.ambient_format import _format

        rendered = _format(
            {
                "now": "2026-05-15T12:00:00+00:00",
                "signals_latest": {
                    "calendar": {
                        "timestamp": "2026-05-15T11:55:00+00:00",
                        "data": {
                            "title": "Therapy with Sarah",
                            "location": "Private clinic",
                        },
                    }
                },
            }
        )

        self.assertNotIn("calendar:", rendered)
        self.assertNotIn("Therapy with Sarah", rendered)
        self.assertNotIn("Private clinic", rendered)

    def test_legacy_calendar_cache_worker_fails_closed_without_dev_gate(self):
        from core.perception_cache import ERROR, PerceptionCache
        from skills.calendar_cache_worker import CalendarCacheWorker

        calls = []
        cache = PerceptionCache()
        worker = CalendarCacheWorker(
            cache=cache,
            interval_s=0.01,
            observe_timeout_s=0.01,
            observe_fn=lambda: calls.append("called"),
        )

        with (
            patch.dict(os.environ, {}, clear=True),
            self.assertLogs(
                "skills.calendar_cache_worker",
                level="WARNING",
            ),
        ):
            worker.start()

        self.assertEqual(calls, [])
        self.assertIsNone(worker._thread)
        entry = cache.get("calendar")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.freshness_state, ERROR)
        self.assertIn("disabled", entry.error or "")

    def test_legacy_calendar_cache_default_observe_requires_dev_gate(self):
        from skills.calendar_cache_worker import _default_observe

        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "disabled"):
                _default_observe()

    def test_fast_lane_perception_envelope_excludes_legacy_calendar(self):
        from core.perception_cache import PerceptionCache
        from core.perception_envelope import ENVELOPE_SOURCES, build_envelope

        cache = PerceptionCache()
        cache.register("calendar", fresh_ms=1000, stale_ms=2000)
        cache.set_value("calendar", object())

        envelope = build_envelope(cache)

        self.assertNotIn("calendar", ENVELOPE_SOURCES)
        self.assertIsNone(envelope.get("calendar"))

    def test_fast_prompt_builder_never_formats_legacy_calendar_titles(self):
        from types import SimpleNamespace

        from core.infra.fast_prompt_builder import build_fast_prompt
        from core.perception_envelope import EnvelopeSource, PerceptionEnvelope

        envelope = PerceptionEnvelope(
            sources={
                "calendar": EnvelopeSource(
                    name="calendar",
                    has_value=True,
                    value=SimpleNamespace(
                        current_event=SimpleNamespace(title="Therapy with Sarah"),
                        next_event=SimpleNamespace(
                            title="Private clinic follow-up",
                            minutes_until=15,
                        ),
                        events=[object()],
                    ),
                    age_ms=0,
                    freshness_state="fresh",
                    error=None,
                    version=1,
                )
            }
        )

        prompt = build_fast_prompt("hey", envelope)

        self.assertNotIn("Therapy with Sarah", prompt.text)
        self.assertNotIn("Private clinic", prompt.text)
        self.assertNotIn("calendar", prompt.used_perception_sources)

    def test_static_capability_surfaces_do_not_advertise_legacy_calendar_alerts(self):
        for path in ("ui/dashboard_local.html", "ui/dashboard_public.html"):
            src = _read(path)
            self.assertNotIn("Google Calendar, 8h lookahead", src)
            self.assertNotIn("15/5 minute meeting alerts", src)
            self.assertNotIn("Screen + system + calendar workers", src)
            self.assertNotIn(
                "Screen + system + calendar workers feed a shared in-memory cache",
                src,
            )

    def test_runtime_source_awareness_does_not_advertise_legacy_calendar_import(self):
        source_awareness = _read("memory/source_awareness.json")

        self.assertNotIn('"skills.calendar_perception"', source_awareness)
        self.assertNotIn('"tags": [\n        "calendar"\n      ]', source_awareness)


if __name__ == "__main__":
    unittest.main()
