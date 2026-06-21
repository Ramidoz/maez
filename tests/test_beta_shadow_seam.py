import os, unittest
os.environ.setdefault("MAEZ_IPHONE_INGEST_TOKEN", "dummy-test")
os.environ.setdefault("MAEZ_SECRETS_DISABLE_NEW_LOADER", "1")

class BetaSeamTest(unittest.TestCase):
    _ALL = ["MAEZ_ROUTING_PRIORS_SHADOW", "MAEZ_ROUTING_PRIORS_ENABLED",
            "MAEZ_ROUTING_BETA_SHADOW", "MAEZ_ROUTING_BETA_ENABLED"]
    def _clear(self):
        for k in self._ALL: os.environ.pop(k, None)
    def test_beta_flags_default_off(self):
        from daemon.maez_daemon import _routing_beta_shadow_enabled, _routing_beta_veto_enabled
        self._clear()
        self.assertFalse(_routing_beta_shadow_enabled()); self.assertFalse(_routing_beta_veto_enabled())
    def test_beta_flags_on(self):
        from daemon.maez_daemon import _routing_beta_shadow_enabled, _routing_beta_veto_enabled
        self._clear(); os.environ["MAEZ_ROUTING_BETA_SHADOW"]="1"; os.environ["MAEZ_ROUTING_BETA_ENABLED"]="1"
        try: self.assertTrue(_routing_beta_shadow_enabled()); self.assertTrue(_routing_beta_veto_enabled())
        finally: self._clear()
    def test_consult_reachable_with_beta_shadow_only(self):   # false-witness fix
        from daemon.maez_daemon import _routing_prior_consult_enabled
        self._clear(); os.environ["MAEZ_ROUTING_BETA_SHADOW"]="1"
        try: self.assertTrue(_routing_prior_consult_enabled())
        finally: self._clear()
    def test_consult_reachable_with_beta_enabled_only(self):
        from daemon.maez_daemon import _routing_prior_consult_enabled
        self._clear(); os.environ["MAEZ_ROUTING_BETA_ENABLED"]="1"
        try: self.assertTrue(_routing_prior_consult_enabled())
        finally: self._clear()
    def test_consult_off_when_all_four_off(self):            # byte-identical / no scipy
        from daemon.maez_daemon import _routing_prior_consult_enabled
        self._clear()
        self.assertFalse(_routing_prior_consult_enabled())
    def test_beta_swap_inside_priors_enabled_authority(self):
        # Beta changes WHICH verdict, never WHETHER the veto fires.
        import pathlib, daemon.maez_daemon as d
        src = pathlib.Path(d.__file__).read_text()
        self.assertIn("_veto_decision = _prior_vetoes_reflex(_prior)", src)
        self.assertIn("_veto_decision = _belief_cmp.beta_would_veto", src)
        self.assertIn("_routing_beta_veto_enabled()", src)
        auth = 'MAEZ_ROUTING_PRIORS_ENABLED") == "1" and _veto_decision'
        self.assertIn(auth, src)
        self.assertLess(src.index("_veto_decision = _belief_cmp.beta_would_veto"), src.index(auth))
