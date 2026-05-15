import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


class ObservationSidecarTests(unittest.TestCase):
    def test_project_health_keeps_only_content_free_fields(self):
        from scripts.observe_sidecar import project_health

        health = {
            "cycle_count": 12,
            "cycle_stalled": False,
            "stage": "cycle_sleep",
            "camera_presence": {
                "mode": "observe",
                "enabled": True,
                "sensor_state": "available",
                "presence_state": "present",
                "last_error_class": "",
                "source_id": "aurora_camera_presence",
                "source_instance_id": "aurora_camera_presence.primary",
            },
            "calendar": {
                "mode": "disabled",
                "connector_state": "disabled",
                "raw_title": "Coffee with Sarah re: her divorce",
            },
            "lived_episodes": {
                "m1": {
                    "enabled": True,
                    "staleness_status": "ok",
                    "newest_age_hours": 1.5,
                }
            },
            "credentials": {"source": "secrets-local-env", "required_present": True},
            "raw_prompt": "do not write this",
        }

        sample = project_health(health, service={"active": "active", "nrestarts": 0})

        self.assertEqual(sample["heartbeat"]["cycle_count"], 12)
        self.assertEqual(sample["camera_presence"]["presence_state"], "present")
        self.assertEqual(sample["calendar"]["mode"], "disabled")
        self.assertNotIn("raw_title", sample["calendar"])
        self.assertNotIn("source_id", sample["camera_presence"])
        self.assertNotIn("source_instance_id", sample["camera_presence"])
        self.assertNotIn("raw_prompt", sample)

    def test_project_health_includes_process_telemetry_without_content(self):
        from scripts.observe_sidecar import project_health

        sample = project_health(
            {"camera_presence": {"mode": "disabled", "enabled": False}},
            service={
                "active": "active",
                "nrestarts": 0,
                "main_pid": 123,
                "memory_current_bytes": 456_789,
                "tasks_current": 37,
                "presence_native_thread_count": 2,
            },
        )

        self.assertEqual(sample["service"]["main_pid"], 123)
        self.assertEqual(sample["service"]["memory_current_bytes"], 456_789)
        self.assertEqual(sample["service"]["tasks_current"], 37)
        self.assertEqual(sample["service"]["presence_native_thread_count"], 2)
        self.assertNotIn("thread_names", sample["service"])
        self.assertNotIn("cmdline", sample["service"])

    def test_red_gates_report_only_gate_names(self):
        from scripts.observe_sidecar import red_gates

        sample = {
            "service": {"active": "active", "nrestarts": 0},
            "heartbeat": {"cycle_stalled": True},
            "camera_presence": {
                "enabled": True,
                "last_error_class": "detector_timeout",
                "sensor_state": "unavailable",
            },
            "calendar": {"mode": "disabled"},
            "m1": {"enabled": True, "staleness_status": "alarm"},
            "credentials": {"required_present": False},
        }

        self.assertEqual(
            red_gates(sample),
            [
                "heartbeat_stalled",
                "camera_detector_timeout",
                "m1_staleness_alarm",
                "credentials_missing_required",
            ],
        )

    def test_expired_camera_timebox_is_not_a_red_gate(self):
        from scripts.observe_sidecar import red_gates

        sample = {
            "service": {"active": "active", "nrestarts": 0},
            "heartbeat": {"cycle_stalled": False},
            "camera_presence": {
                "enabled": False,
                "mode": "expired_disabled",
                "last_error_class": "timebox_expired",
                "sensor_state": "disabled",
                "presence_state": "unknown",
            },
            "calendar": {"mode": "disabled"},
            "m1": {"enabled": True, "staleness_status": "ok"},
            "credentials": {"required_present": True},
        }

        self.assertEqual(red_gates(sample), [])

    def test_stranded_presence_threads_are_red_only_when_camera_disabled(self):
        from scripts.observe_sidecar import red_gates

        disabled = {
            "service": {"active": "active", "nrestarts": 0, "presence_native_thread_count": 1},
            "heartbeat": {"cycle_stalled": False},
            "camera_presence": {"enabled": False, "mode": "disabled", "last_error_class": ""},
            "m1": {"enabled": True, "staleness_status": "ok"},
            "credentials": {"required_present": True},
        }
        enabled = {
            **disabled,
            "camera_presence": {"enabled": True, "mode": "observe", "last_error_class": ""},
        }

        self.assertIn("camera_presence_threads_stranded", red_gates(disabled))
        self.assertNotIn("camera_presence_threads_stranded", red_gates(enabled))

    def test_presence_native_thread_count_reads_proc_comm_without_names(self):
        from scripts.observe_sidecar import presence_native_thread_count

        with TemporaryDirectory() as td:
            root = Path(td)
            task_dir = root / "123" / "task"
            for tid, name in {
                "1": "python",
                "2": "presence-observe",
                "3": "mediapipe-worker",
                "4": "opencv-camera",
            }.items():
                thread_dir = task_dir / tid
                thread_dir.mkdir(parents=True)
                (thread_dir / "comm").write_text(name, encoding="utf-8")

            self.assertEqual(presence_native_thread_count(123, proc_root=root), 3)


if __name__ == "__main__":
    unittest.main()
