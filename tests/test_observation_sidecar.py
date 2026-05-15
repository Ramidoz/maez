import unittest


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
        self.assertNotIn("source_id", sample["camera_presence"])
        self.assertNotIn("source_instance_id", sample["camera_presence"])
        self.assertNotIn("raw_title", sample["calendar"])
        self.assertNotIn("raw_prompt", sample)

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


if __name__ == "__main__":
    unittest.main()
