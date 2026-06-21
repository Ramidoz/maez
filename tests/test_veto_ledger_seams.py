import os, unittest
os.environ.setdefault("MAEZ_IPHONE_INGEST_TOKEN", "dummy-test")
os.environ.setdefault("MAEZ_SECRETS_DISABLE_NEW_LOADER", "1")

class SeamHelperTest(unittest.TestCase):
    def test_ledger_disabled_by_default(self):
        from daemon.maez_daemon import _veto_ledger_enabled
        os.environ.pop("MAEZ_VETO_LEDGER", None)
        self.assertFalse(_veto_ledger_enabled())
    def test_ledger_enabled_flag(self):
        from daemon.maez_daemon import _veto_ledger_enabled
        os.environ["MAEZ_VETO_LEDGER"] = "1"
        try: self.assertTrue(_veto_ledger_enabled())
        finally: os.environ.pop("MAEZ_VETO_LEDGER", None)
    def test_ledger_get_opens_notebook_when_none(self):
        # first-veto failure class: no sibling import, override found nothing -> record path must STILL open the notebook
        import tempfile
        from daemon.maez_daemon import _veto_ledger_get
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        os.environ["MAEZ_VETO_LEDGER_DB_PATH"] = tmp.name
        try:
            led = _veto_ledger_get(None)
            self.assertIsNotNone(led)
            rid = led.record_veto(class_id="SIG", tool="web_search", prior_n=5,
                prior_success_rate=0.0, prior_confidence=0.625, turn_id="t1", surface="cockpit", now=1000.0)
            self.assertIsNotNone(rid)
            self.assertIs(_veto_ledger_get(led), led)
        finally:
            os.environ.pop("MAEZ_VETO_LEDGER_DB_PATH", None)
            tmp.close()
            try: os.unlink(tmp.name)
            except OSError: pass
