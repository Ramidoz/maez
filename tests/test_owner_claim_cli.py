import json, os, tempfile, unittest
from skills.user_accounts import UserAccounts
from scripts import maez_cli

class FakeArgs:
    def __init__(self, **kw):
        self.account = kw.get("account")
        self.rebind = kw.get("rebind", False)
        self.reset = kw.get("reset", False)

class OwnClaimCli(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.db = os.path.join(self.dir, "users.db")
        self.audit = os.path.join(self.dir, "owner_identity_audit.jsonl")
        self.acc = UserAccounts(db_path=self.db)
        self.acc.register("rohit", "pw", display_name="Rohit")
        self.ctx = dict(accounts=self.acc, audit_path=self.audit,
                        is_interactive=lambda: True, uid_ok=lambda: True,
                        confirm=lambda prompt: True)

    def test_claim_sets_owner_and_audits(self):
        rc = maez_cli.cmd_own_claim(FakeArgs(account="rohit"), **self.ctx)
        self.assertEqual(rc, 0)
        self.assertTrue(self.acc.owner_claimed())
        with open(self.audit) as f:
            rows = [json.loads(l) for l in f]
        self.assertEqual(rows[-1]["action"], "claim")

    def test_refuses_without_tty(self):
        self.ctx["is_interactive"] = lambda: False
        rc = maez_cli.cmd_own_claim(FakeArgs(account="rohit"), **self.ctx)
        self.assertNotEqual(rc, 0)
        self.assertFalse(self.acc.owner_claimed())
        self.assertFalse(os.path.exists(self.audit))

    def test_refuses_on_uid_mismatch(self):
        self.ctx["uid_ok"] = lambda: False
        rc = maez_cli.cmd_own_claim(FakeArgs(account="rohit"), **self.ctx)
        self.assertNotEqual(rc, 0)
        self.assertFalse(self.acc.owner_claimed())
        self.assertFalse(os.path.exists(self.audit))

    def test_no_confirm_writes_nothing(self):
        self.ctx["confirm"] = lambda prompt: False
        rc = maez_cli.cmd_own_claim(FakeArgs(account="rohit"), **self.ctx)
        self.assertNotEqual(rc, 0)
        self.assertFalse(self.acc.owner_claimed())
        self.assertFalse(os.path.exists(self.audit))

    def test_idempotent_reclaim(self):
        maez_cli.cmd_own_claim(FakeArgs(account="rohit"), **self.ctx)
        rc = maez_cli.cmd_own_claim(FakeArgs(account="rohit"), **self.ctx)
        self.assertEqual(rc, 0)

    def test_rebind_and_reset(self):
        self.acc.register("alex", "pw")
        maez_cli.cmd_own_claim(FakeArgs(account="rohit"), **self.ctx)
        self.assertEqual(maez_cli.cmd_own_claim(FakeArgs(account="alex", rebind=True), **self.ctx), 0)
        self.assertEqual(self.acc.get_owner()["username"], "alex")
        self.assertEqual(maez_cli.cmd_own_claim(FakeArgs(reset=True), **self.ctx), 0)
        self.assertFalse(self.acc.owner_claimed())

    def test_idempotent_reclaim_writes_no_extra_audit(self):
        maez_cli.cmd_own_claim(FakeArgs(account="rohit"), **self.ctx)
        maez_cli.cmd_own_claim(FakeArgs(account="rohit"), **self.ctx)  # noop
        with open(self.audit) as f:
            rows = [json.loads(l) for l in f]
        self.assertEqual(len([r for r in rows if r["action"] == "claim"]), 1)
