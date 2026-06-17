import inspect
import os
import subprocess
import sys
import threading
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo


_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


CHICAGO = ZoneInfo("America/Chicago")
LOS_ANGELES = ZoneInfo("America/Los_Angeles")
UTC = ZoneInfo("UTC")


def _web_interface_for_tests():
    with (
        patch.dict(os.environ, {"MAEZ_IPHONE_INGEST_TOKEN": "test-token"}, clear=False),
        patch("core.infra.secrets.load_ordinary_config_for_process"),
        patch("core.infra.secrets.load_secrets_for_process"),
    ):
        import skills.web_interface as web_interface

    return web_interface


class TemporalSpineHelperTests(unittest.TestCase):
    def setUp(self):
        from core.time import temporal_spine

        temporal_spine._reset_diagnostics_for_tests()

    def tearDown(self):
        os.environ.pop("MAEZ_OWNER_TIMEZONE", None)

    def test_env_timezone_wins_and_reports_env_source(self):
        from core.time import temporal_spine

        with patch.dict(os.environ, {"MAEZ_OWNER_TIMEZONE": "America/Los_Angeles"}):
            self.assertEqual(temporal_spine.owner_timezone().key, "America/Los_Angeles")
            snap = temporal_spine.diagnostics_snapshot()

        self.assertEqual(snap.timezone_source, "env")
        self.assertEqual(snap.timezone_name, "America/Los_Angeles")

    def test_identity_timezone_used_when_env_empty(self):
        from core.time import temporal_spine

        with (
            patch.dict(os.environ, {}, clear=False),
            patch("core.memory.identity.timezone", return_value="America/Chicago"),
        ):
            os.environ.pop("MAEZ_OWNER_TIMEZONE", None)
            self.assertEqual(temporal_spine.owner_timezone().key, "America/Chicago")
            snap = temporal_spine.diagnostics_snapshot()

        self.assertEqual(snap.timezone_source, "identity")
        self.assertEqual(snap.timezone_name, "America/Chicago")

    def test_invalid_identity_timezone_falls_back_without_exposing_raw_value(self):
        from core.time import temporal_spine

        with (
            patch.dict(os.environ, {}, clear=False),
            patch("core.memory.identity.timezone", return_value="Definitely/Not_A_Real_Zone"),
        ):
            os.environ.pop("MAEZ_OWNER_TIMEZONE", None)
            zone = temporal_spine.owner_timezone()
            snap = temporal_spine.diagnostics_snapshot()

        self.assertEqual(zone.key, "UTC")
        self.assertEqual(snap.timezone_source, "invalid_fallback_utc")
        self.assertEqual(snap.timezone_name, "UTC")
        self.assertNotIn("Definitely", repr(snap))

    def test_missing_identity_timezone_falls_back_to_utc(self):
        from core.time import temporal_spine

        with (
            patch.dict(os.environ, {}, clear=False),
            patch("core.memory.identity.timezone", return_value=""),
        ):
            os.environ.pop("MAEZ_OWNER_TIMEZONE", None)
            zone = temporal_spine.owner_timezone()
            snap = temporal_spine.diagnostics_snapshot()

        self.assertEqual(zone.key, "UTC")
        self.assertEqual(snap.timezone_source, "fallback_utc")
        self.assertEqual(snap.timezone_name, "UTC")

    def test_timezone_source_resolves_before_reporting(self):
        from core.time import temporal_spine

        with patch.dict(os.environ, {"MAEZ_OWNER_TIMEZONE": "America/Los_Angeles"}):
            self.assertEqual(temporal_spine.timezone_source(), "env")

    def test_temporal_spine_health_resolves_timezone_before_reporting(self):
        from core.time import temporal_spine

        with (
            patch.dict(os.environ, {}, clear=False),
            patch("core.memory.identity.timezone", return_value="America/Chicago"),
        ):
            os.environ.pop("MAEZ_OWNER_TIMEZONE", None)
            health = temporal_spine.temporal_spine_health()

        self.assertEqual(health["timezone_source"], "identity")
        self.assertEqual(health["timezone_name"], "America/Chicago")

    def test_identity_timezone_exception_maps_to_invalid_fallback_utc(self):
        from core.time import temporal_spine

        with (
            patch.dict(os.environ, {}, clear=False),
            patch("core.memory.identity.timezone", side_effect=RuntimeError("identity down")),
        ):
            os.environ.pop("MAEZ_OWNER_TIMEZONE", None)
            self.assertEqual(temporal_spine.owner_timezone().key, "UTC")
            snap = temporal_spine.diagnostics_snapshot()

        self.assertEqual(snap.timezone_source, "invalid_fallback_utc")
        self.assertEqual(snap.timezone_name, "UTC")

    def test_canonical_utc_iso_normalizes_z_and_local_offsets(self):
        from core.time.temporal_spine import canonical_utc_iso

        self.assertEqual(
            canonical_utc_iso("2026-05-15T12:00:00Z", field_name="event_at"),
            "2026-05-15T12:00:00+00:00",
        )
        self.assertEqual(
            canonical_utc_iso("2026-05-15T07:00:00-05:00", field_name="event_at"),
            "2026-05-15T12:00:00+00:00",
        )

    def test_s2_temporal_envelope_field_names_are_accepted(self):
        from core.time.temporal_spine import canonical_utc

        for field_name in (
            "received_at",
            "expires_at",
            "deletion_observed_at",
            "change_observed_at",
        ):
            self.assertEqual(
                canonical_utc("2026-05-15T12:00:00Z", field_name=field_name),
                datetime(2026, 5, 15, 12, 0, tzinfo=timezone.utc),
            )

    def test_closed_vocabulary_members_are_exported_without_rename(self):
        import typing
        from core.time import temporal_spine

        self.assertEqual(
            set(typing.get_args(temporal_spine.TemporalInstantFieldName)),
            {
                "event_at",
                "ingested_at",
                "observed_at",
                "received_at",
                "expires_at",
                "deletion_observed_at",
                "change_observed_at",
                "valid_from",
                "valid_to",
            },
        )
        self.assertEqual(
            set(typing.get_args(temporal_spine.TemporalDerivedFieldName)),
            {"owner_local_date"},
        )
        self.assertEqual(
            set(typing.get_args(temporal_spine.TemporalAnchorKind)),
            {"earlier_today", "this_morning", "yesterday", "last_week"},
        )
        self.assertEqual(
            set(typing.get_args(temporal_spine.HelperUnavailableReason)),
            {"temporal_helper_exception"},
        )

    def test_naive_inputs_are_assumed_utc_and_counted(self):
        from core.time import temporal_spine

        naive_dt = datetime(2026, 5, 15, 12, 0)
        self.assertEqual(
            temporal_spine.canonical_utc(naive_dt, field_name="event_at"),
            datetime(2026, 5, 15, 12, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(
            temporal_spine.canonical_utc("2026-05-15T13:00:00", field_name="event_at"),
            datetime(2026, 5, 15, 13, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(
            temporal_spine.diagnostics_snapshot().naive_timestamp_assumed_utc_count,
            2,
        )

    def test_malformed_and_bare_date_inputs_are_rejected_and_counted(self):
        from core.time import temporal_spine

        for value in ("not-a-date", "2026-05-15"):
            with self.assertRaises(ValueError):
                temporal_spine.canonical_utc(value, field_name="event_at")

        self.assertEqual(
            temporal_spine.diagnostics_snapshot().malformed_timestamp_rejected_count,
            2,
        )

    def test_reset_diagnostics_clears_all_counters_and_timezone_state(self):
        from core.time import temporal_spine

        with patch.dict(os.environ, {"MAEZ_OWNER_TIMEZONE": "America/Los_Angeles"}):
            temporal_spine.owner_timezone()
        with self.assertRaises(ValueError):
            temporal_spine.canonical_utc("bad", field_name="event_at")
        with self.assertRaises(ValueError):
            temporal_spine.canonical_utc("bad", field_name="bad_field")  # type: ignore[arg-type]
        temporal_spine.canonical_utc("2026-05-15T12:00:00", field_name="event_at")
        with self.assertRaises(ValueError):
            temporal_spine.temporal_window("next_week", datetime(2026, 5, 15, tzinfo=UTC))  # type: ignore[arg-type]
        temporal_spine.record_helper_unavailable("temporal_helper_exception")

        temporal_spine._reset_diagnostics_for_tests()
        snap = temporal_spine.diagnostics_snapshot()

        self.assertEqual(snap.timezone_source, "fallback_utc")
        self.assertEqual(snap.timezone_name, "UTC")
        self.assertEqual(snap.invalid_field_name_rejected_count, 0)
        self.assertEqual(snap.malformed_timestamp_rejected_count, 0)
        self.assertEqual(snap.naive_timestamp_assumed_utc_count, 0)
        self.assertEqual(snap.unsupported_anchor_rejected_count, 0)
        self.assertEqual(snap.helper_unavailable_count, 0)

    def test_counter_isolation_after_reset(self):
        from core.time import temporal_spine

        with self.assertRaises(ValueError):
            temporal_spine.canonical_utc("bad", field_name="event_at")
        temporal_spine._reset_diagnostics_for_tests()
        temporal_spine.canonical_utc("2026-05-15T13:00:00", field_name="event_at")
        snap = temporal_spine.diagnostics_snapshot()

        self.assertEqual(snap.malformed_timestamp_rejected_count, 0)
        self.assertEqual(snap.naive_timestamp_assumed_utc_count, 1)

    def test_invalid_field_name_wins_before_timestamp_parsing(self):
        from core.time import temporal_spine

        with self.assertRaises(ValueError):
            temporal_spine.canonical_utc("not-a-date", field_name="bad_field")  # type: ignore[arg-type]

        snap = temporal_spine.diagnostics_snapshot()
        self.assertEqual(snap.invalid_field_name_rejected_count, 1)
        self.assertEqual(snap.malformed_timestamp_rejected_count, 0)

    def test_ambiguous_fall_back_time_preserves_fold(self):
        from core.time.temporal_spine import canonical_utc

        fold0 = datetime(2026, 11, 1, 1, 30, tzinfo=CHICAGO, fold=0)
        fold1 = datetime(2026, 11, 1, 1, 30, tzinfo=CHICAGO, fold=1)

        self.assertNotEqual(
            canonical_utc(fold0, field_name="event_at"),
            canonical_utc(fold1, field_name="event_at"),
        )

    def test_nonexistent_owner_local_reference_time_is_rejected(self):
        from core.time import temporal_spine

        with patch.dict(os.environ, {"MAEZ_OWNER_TIMEZONE": "America/Chicago"}):
            with self.assertRaises(ValueError):
                temporal_spine.temporal_window(
                    "earlier_today",
                    datetime(2026, 3, 8, 2, 30, tzinfo=CHICAGO),
                )

        self.assertEqual(
            temporal_spine.diagnostics_snapshot().malformed_timestamp_rejected_count,
            1,
        )

    def test_owner_local_date_uses_owner_timezone_not_utc(self):
        from core.time import temporal_spine

        with patch.dict(os.environ, {"MAEZ_OWNER_TIMEZONE": "America/Los_Angeles"}):
            self.assertEqual(
                temporal_spine.owner_local_date("2026-05-15T06:30:00+00:00").isoformat(),
                "2026-05-14",
            )

    def test_owner_local_date_is_not_persisted_by_s3_runtime_paths(self):
        production_paths = [
            _REPO / "core" / "memory" / "episodes.py",
            _REPO / "core" / "memory" / "temporal_anchor_recall.py",
            _REPO / "daemon" / "maez_daemon.py",
            _REPO / "scripts" / "observe_sidecar.py",
            _REPO / "skills" / "web_interface.py",
        ]
        for path in production_paths:
            self.assertNotIn("owner_local_date", path.read_text(), str(path))

    def test_temporal_windows_match_owner_local_boundaries_and_utc_surfaces(self):
        from core.time import temporal_spine

        with patch.dict(os.environ, {"MAEZ_OWNER_TIMEZONE": "America/Chicago"}):
            ref = datetime(2026, 5, 13, 22, 30, tzinfo=CHICAGO)
            earlier = temporal_spine.temporal_window("earlier_today", ref)
            morning = temporal_spine.temporal_window("this_morning", ref)
            yesterday = temporal_spine.temporal_window(
                "yesterday", datetime(2026, 3, 9, 9, 0, tzinfo=CHICAGO)
            )
            last_week = temporal_spine.temporal_window("last_week", ref)

        self.assertEqual(earlier.start, datetime(2026, 5, 13, 0, 0, tzinfo=CHICAGO))
        self.assertEqual(earlier.end, ref)
        self.assertEqual(morning.end, datetime(2026, 5, 13, 12, 0, tzinfo=CHICAGO))
        self.assertEqual(yesterday.start, datetime(2026, 3, 8, 0, 0, tzinfo=CHICAGO))
        self.assertEqual(yesterday.end, datetime(2026, 3, 9, 0, 0, tzinfo=CHICAGO))
        self.assertEqual(last_week.start, datetime(2026, 5, 4, 0, 0, tzinfo=CHICAGO))
        self.assertEqual(last_week.end, datetime(2026, 5, 11, 0, 0, tzinfo=CHICAGO))
        self.assertEqual(last_week.start_utc.tzinfo, timezone.utc)
        self.assertEqual(last_week.end_utc.tzinfo, timezone.utc)

    def test_temporal_window_naive_reference_is_owner_local_not_utc(self):
        from core.time import temporal_spine

        with patch.dict(os.environ, {"MAEZ_OWNER_TIMEZONE": "America/Los_Angeles"}):
            window = temporal_spine.temporal_window(
                "earlier_today",
                datetime(2026, 5, 15, 1, 0),
            )

        self.assertEqual(window.start, datetime(2026, 5, 15, 0, 0, tzinfo=LOS_ANGELES))
        self.assertEqual(window.end, datetime(2026, 5, 15, 1, 0, tzinfo=LOS_ANGELES))

    def test_temporal_window_rejects_generated_nonexistent_midnight(self):
        from core.time import temporal_spine

        with patch.dict(os.environ, {"MAEZ_OWNER_TIMEZONE": "America/Havana"}):
            with self.assertRaises(ValueError):
                temporal_spine.temporal_window(
                    "earlier_today",
                    datetime(2026, 3, 8, 10, 0, tzinfo=ZoneInfo("America/Havana")),
                )

    def test_half_open_contains_uses_canonical_utc_instants(self):
        from core.time.temporal_spine import half_open_contains

        start = datetime(2026, 5, 15, 12, 0, tzinfo=timezone.utc)
        end = datetime(2026, 5, 15, 13, 0, tzinfo=timezone.utc)

        self.assertTrue(half_open_contains("2026-05-15T07:30:00-05:00", start=start, end=end))
        self.assertFalse(half_open_contains("2026-05-15T13:00:00+00:00", start=start, end=end))
        self.assertTrue(half_open_contains("2026-05-15T12:00:00+00:00", start=start, end=end))

    def test_half_open_contains_rejects_non_utc_bounds(self):
        from core.time.temporal_spine import half_open_contains

        with self.assertRaises(ValueError):
            half_open_contains(
                "2026-05-15T12:30:00+00:00",
                start=datetime(2026, 5, 15, 7, 0, tzinfo=CHICAGO),
                end=datetime(2026, 5, 15, 8, 0, tzinfo=CHICAGO),
            )

    def test_unsupported_anchor_counts_only_symbolic_api_boundary(self):
        from core.time import temporal_spine

        with self.assertRaises(ValueError):
            temporal_spine.temporal_window("next_week", datetime(2026, 5, 15, tzinfo=UTC))  # type: ignore[arg-type]

        self.assertEqual(
            temporal_spine.diagnostics_snapshot().unsupported_anchor_rejected_count,
            1,
        )

    def test_record_helper_unavailable_and_diagnostics_are_thread_safe(self):
        from core.time import temporal_spine

        def worker() -> None:
            for _ in range(50):
                temporal_spine.record_helper_unavailable("temporal_helper_exception")

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(temporal_spine.diagnostics_snapshot().helper_unavailable_count, 200)

    def test_reset_diagnostics_is_test_guarded(self):
        from core.time import temporal_spine

        source = inspect.getsource(temporal_spine._reset_diagnostics_for_tests)
        self.assertIn("_called_from_tests", source)
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "from core.time import temporal_spine; temporal_spine._reset_diagnostics_for_tests()",
            ],
            cwd=str(_REPO),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("RuntimeError", result.stderr)

    def test_module_import_graph_avoids_deferred_stores(self):
        import core.time.temporal_spine as temporal_spine

        source = inspect.getsource(temporal_spine)
        for forbidden in (
            "m1_lived_episode_promotion",
            "private_thoughts",
            "entity_index",
            "calendar_store",
            "calendar_v1",
        ):
            self.assertNotIn(f"import {forbidden}", source)
            self.assertNotIn(f"from core.memory.{forbidden}", source)
            self.assertNotIn(f"from core.information_limb.{forbidden}", source)


class TemporalSpineHealthAndSidecarTests(unittest.TestCase):
    def test_health_includes_temporal_spine_aggregate(self):
        from core.time.temporal_spine import temporal_spine_health

        health = temporal_spine_health()

        self.assertEqual(
            set(health),
            {
                "timezone_source",
                "timezone_name",
                "invalid_field_name_rejected_count",
                "malformed_timestamp_rejected_count",
                "naive_timestamp_assumed_utc_count",
                "unsupported_anchor_rejected_count",
                "helper_unavailable_count",
            },
        )

    def test_public_maez_state_strips_temporal_spine(self):
        web_interface = _web_interface_for_tests()

        with patch.object(
            web_interface,
            "_daemon_health",
            return_value={
                "status": "alive",
                "temporal_spine": {"timezone_name": "America/Chicago"},
            },
        ):
            response = web_interface.app.test_client().get("/api/maez-state")

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("temporal_spine", response.get_json()["daemon"])

    def test_debug_services_strips_temporal_spine(self):
        web_interface = _web_interface_for_tests()
        client = web_interface.app.test_client()
        client.set_cookie("maez_token", "tok")

        with (
            patch.object(
                web_interface,
                "_daemon_health",
                return_value={
                    "status": "alive",
                    "temporal_spine": {"timezone_name": "America/Chicago"},
                },
            ),
            patch.object(web_interface, "_service_state_cached", return_value={"active": "active"}),
            patch.object(
                web_interface.accounts,
                "get_by_token",
                return_value={"uuid": "owner", "display_name": "Rohit"},
            ),
            patch.object(
                web_interface.accounts,
                "get_user_record",
                return_value={"private_owner_bridge": True},
            ),
        ):
            response = client.get("/api/debug/services")

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("temporal_spine", response.get_json()["daemon"])

    def test_sidecar_projects_temporal_spine_allowlist_and_red_gates(self):
        from scripts.observe_sidecar import project_health, red_gates

        health = {
            "temporal_spine": {
                "timezone_source": "invalid_fallback_utc",
                "timezone_name": "UTC",
                "invalid_field_name_rejected_count": 3,
                "malformed_timestamp_rejected_count": 1,
                "naive_timestamp_assumed_utc_count": 2,
                "unsupported_anchor_rejected_count": 4,
                "helper_unavailable_count": 5,
                "raw_timestamp": "2026-05-15T12:00:00Z",
                "exception_text": "Definitely/Not_A_Real_Zone",
            },
            "camera_presence": {"mode": "disabled", "enabled": False},
            "lived_episodes": {"m1": {"enabled": True}},
            "credentials": {"required_present": True},
        }

        sample = project_health(health, service={"active": "active", "nrestarts": 0})

        self.assertEqual(sample["temporal_spine"]["timezone_source"], "invalid_fallback_utc")
        self.assertNotIn("raw_timestamp", sample["temporal_spine"])
        self.assertNotIn("exception_text", sample["temporal_spine"])
        self.assertEqual(
            red_gates(sample),
            [
                "temporal_spine_invalid_timezone_fallback",
                "temporal_spine_malformed_timestamp_rejected",
            ],
        )

    def test_sidecar_red_gates_missing_temporal_spine(self):
        from scripts.observe_sidecar import project_health, red_gates

        sample = project_health(
            {
                "camera_presence": {"mode": "disabled", "enabled": False},
                "lived_episodes": {"m1": {"enabled": True}},
                "credentials": {"required_present": True},
            },
            service={"active": "active", "nrestarts": 0},
        )

        self.assertEqual(red_gates(sample), ["temporal_spine_unavailable"])

    def test_sidecar_missing_temporal_spine_does_not_also_counter_reset(self):
        from scripts.observe_sidecar import project_health, red_gates

        previous = {
            "service": {"active": "active", "nrestarts": 0, "main_pid": 123},
            "temporal_spine_present": True,
            "temporal_spine": {
                "malformed_timestamp_rejected_count": 5,
                "invalid_field_name_rejected_count": 0,
                "naive_timestamp_assumed_utc_count": 0,
                "unsupported_anchor_rejected_count": 0,
                "helper_unavailable_count": 0,
            },
        }
        sample = project_health(
            {
                "camera_presence": {"mode": "disabled", "enabled": False},
                "lived_episodes": {"m1": {"enabled": True}},
                "credentials": {"required_present": True},
            },
            service={"active": "active", "nrestarts": 0, "main_pid": 123},
        )

        self.assertEqual(
            red_gates(sample, previous_sample=previous), ["temporal_spine_unavailable"]
        )

    def test_sidecar_does_not_gate_watch_only_temporal_counters(self):
        from scripts.observe_sidecar import red_gates

        sample = {
            "service": {"active": "active", "nrestarts": 0, "main_pid": 123},
            "temporal_spine_present": True,
            "temporal_spine": {
                "timezone_source": "identity",
                "timezone_name": "America/Chicago",
                "invalid_field_name_rejected_count": 1,
                "malformed_timestamp_rejected_count": 0,
                "naive_timestamp_assumed_utc_count": 2,
                "unsupported_anchor_rejected_count": 3,
                "helper_unavailable_count": 4,
            },
            "camera_presence": {"enabled": False, "mode": "disabled", "last_error_class": ""},
            "m1": {"enabled": True, "staleness_status": "ok"},
            "credentials": {"required_present": True},
        }

        self.assertEqual(red_gates(sample), [])

    def test_sidecar_red_gates_counter_reset_only_with_same_pid(self):
        from scripts.observe_sidecar import red_gates

        previous = {
            "service": {"active": "active", "nrestarts": 0, "main_pid": 123},
            "temporal_spine_present": True,
            "temporal_spine": {
                "malformed_timestamp_rejected_count": 5,
                "invalid_field_name_rejected_count": 0,
                "naive_timestamp_assumed_utc_count": 0,
                "unsupported_anchor_rejected_count": 0,
                "helper_unavailable_count": 0,
            },
            "camera_presence": {"enabled": False, "mode": "disabled", "last_error_class": ""},
            "m1": {"enabled": True, "staleness_status": "ok"},
            "credentials": {"required_present": True},
        }
        current = {
            **previous,
            "temporal_spine": {
                **previous["temporal_spine"],
                "malformed_timestamp_rejected_count": 0,
            },
        }
        different_pid = {
            **current,
            "service": {"active": "active", "nrestarts": 0, "main_pid": 456},
        }

        self.assertIn("temporal_spine_counter_reset", red_gates(current, previous_sample=previous))
        self.assertNotIn(
            "temporal_spine_counter_reset",
            red_gates(different_pid, previous_sample=previous),
        )

    def test_s3_spec_preserves_future_calendar_guard_and_store_inventory(self):
        spec = (_REPO / "docs" / "slices" / "temporal-spine" / "spec.md").read_text()

        self.assertIn("calendar_voice_guard", spec)
        self.assertIn("Store Status Inventory", spec)
        self.assertIn("| canonical |", spec)
        self.assertIn("| wrapped |", spec)
        self.assertIn("| deferred |", spec)


if __name__ == "__main__":
    unittest.main()
