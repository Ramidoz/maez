import unittest
from unittest import mock


class BackupFreshnessDaemonWiringTest(unittest.TestCase):
    def test_coverage_gap_is_a_valid_operator_freshness_class(self):
        from core.governance.operator_user_boundary import validate_operator_freshness_class

        self.assertEqual(validate_operator_freshness_class("coverage_gap"), "coverage_gap")

    def test_operator_health_reads_real_backup_freshness(self):
        from daemon.maez_daemon import MaezDaemon

        daemon = object.__new__(MaezDaemon)

        with mock.patch(
            "core.health.backup_freshness.backup_freshness",
            return_value="fresh",
        ) as freshness:
            health = daemon._operator_health()

        self.assertEqual(health["backup_freshness_class"], "fresh")
        freshness.assert_called_once()

    def test_operator_health_fails_soft_to_unavailable(self):
        from daemon.maez_daemon import MaezDaemon

        daemon = object.__new__(MaezDaemon)

        with mock.patch(
            "core.health.backup_freshness.backup_freshness",
            side_effect=RuntimeError("backup reader unavailable"),
        ):
            health = daemon._operator_health()

        self.assertEqual(health["backup_freshness_class"], "unavailable")


if __name__ == "__main__":
    unittest.main()
