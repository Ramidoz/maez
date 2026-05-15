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
                "voice_guard_rejected_count": 0,
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
                    "identity_fallback_count": 0,
                    "invalid_eligibility_reason_rejected_count": 0,
                }
            },
            "credentials": {"source": "secrets-local-env", "required_present": True},
            "raw_prompt": "do not write this",
        }

        sample = project_health(health, service={"active": "active", "nrestarts": 0})

        self.assertEqual(sample["heartbeat"]["cycle_count"], 12)
        self.assertEqual(sample["camera_presence"]["presence_state"], "present")
        self.assertEqual(sample["camera_presence"]["voice_guard_rejected_count"], 0)
        self.assertEqual(sample["calendar"]["mode"], "disabled")
        self.assertEqual(sample["m1"]["identity_fallback_count"], 0)
        self.assertEqual(sample["m1"]["invalid_eligibility_reason_rejected_count"], 0)
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

    def test_project_health_reads_nested_reasoning_loop_for_heartbeat_gate(self):
        from scripts.observe_sidecar import project_health, red_gates

        sample = project_health({
            "cycle_count": 20,
            "reasoning_loop": {
                "cycle_stalled": True,
                "stage": "observe_camera",
                "stage_age_seconds": 95,
                "cycle_age_seconds": 130,
            },
            "camera_presence": {"mode": "disabled", "enabled": False},
            "lived_episodes": {"m1": {"enabled": True}},
            "credentials": {"required_present": True},
        })

        self.assertEqual(sample["heartbeat"]["cycle_count"], 20)
        self.assertIs(sample["heartbeat"]["cycle_stalled"], True)
        self.assertEqual(sample["heartbeat"]["stage"], "observe_camera")
        self.assertIn("heartbeat_stalled", red_gates(sample))

    def test_project_health_reads_nested_lived_episode_staleness_for_m1_gate(self):
        from scripts.observe_sidecar import project_health, red_gates

        sample = project_health({
            "camera_presence": {"mode": "disabled", "enabled": False},
            "lived_episodes": {
                "m1": {
                    "enabled": True,
                    "identity_fallback_count": 0,
                    "invalid_eligibility_reason_rejected_count": 0,
                    "invalid_promotion_trigger_rejected_count": 0,
                },
                "staleness": {
                    "staleness_status": "alarm",
                    "newest_age_hours": 72.0,
                    "active_count": 12,
                },
            },
            "credentials": {"required_present": True},
        })

        self.assertEqual(sample["m1"]["staleness_status"], "alarm")
        self.assertEqual(sample["m1"]["newest_age_hours"], 72.0)
        self.assertEqual(sample["m1"]["active_count"], 12)
        self.assertIn("m1_staleness_alarm", red_gates(sample))

    def test_red_gates_report_only_gate_names(self):
        from scripts.observe_sidecar import red_gates

        sample = {
            "service": {"active": "active", "nrestarts": 0},
            "heartbeat": {"cycle_stalled": True},
            "camera_presence": {
                "enabled": True,
                "last_error_class": "detector_timeout",
                "sensor_state": "unavailable",
                "voice_guard_rejected_count": 1,
            },
            "calendar": {"mode": "disabled"},
            "m1": {
                "enabled": True,
                "staleness_status": "alarm",
                "identity_fallback_count": 1,
                "invalid_eligibility_reason_rejected_count": 2,
                "invalid_promotion_trigger_rejected_count": 3,
            },
            "credentials": {"required_present": False},
        }

        self.assertEqual(
            red_gates(sample),
            [
                "heartbeat_stalled",
                "camera_detector_timeout",
                "camera_presence_voice_guard_rejected",
                "m1_staleness_alarm",
                "m1_identity_fallback",
                "m1_invalid_eligibility_reason_rejected",
                "m1_invalid_promotion_trigger_rejected",
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
