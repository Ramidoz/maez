import os, unittest

os.environ.setdefault("MAEZ_IPHONE_INGEST_TOKEN", "dummy-test")
os.environ.setdefault("MAEZ_SECRETS_DISABLE_NEW_LOADER", "1")

from core.routing.recall_outcome import RecallOutcome, OutcomeClass, ReplyPath


def _rec(**kw):
    base = dict(mode="recall_triad", turn_kind="ordinary",
                outcome_class=OutcomeClass.ORDINARY_ANSWERED, denial_kind="na",
                had_confirmed=False, citation_coverage=0.1, receipt_or_na="not_consulted",
                latency_ms=10, focused_elapsed_ms=5, reply_path=ReplyPath.FOCUSED)
    base.update(kw)
    return RecallOutcome(**base)


class TestRecallOutcomeField(unittest.TestCase):
    def test_reply_grounding_defaults_none(self):
        self.assertIsNone(_rec().reply_grounding)

    def test_reply_grounding_set(self):
        self.assertEqual(_rec(reply_grounding=0.75).reply_grounding, 0.75)


class TestLogEmitsReplyGrounding(unittest.TestCase):
    def test_log_line_carries_reply_grounding(self):
        import daemon.maez_daemon as d
        with self.assertLogs(d.logger.name) as logs:
            d._log_recall_outcome(rec=_rec(reply_grounding=0.5))
        self.assertTrue(any("reply_grounding=0.5" in m for m in logs.output))


class TestDaemonThreadsBothPipes(unittest.TestCase):
    def test_daemon_threads_reply_grounding(self):
        import inspect, daemon.maez_daemon as d
        src = inspect.getsource(d)
        self.assertIn("_rk_reply_grounding", src)
        self.assertIn("reply_grounding=_rk_reply_grounding", src)


if __name__ == "__main__":
    unittest.main()
