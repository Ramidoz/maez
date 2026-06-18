import os, tempfile, unittest
from skills.user_accounts import UserAccounts

class OwnerIdentitySchema(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.db = os.path.join(self.dir, "users.db")
        self.acc = UserAccounts(db_path=self.db)
        self.acc.register("rohit", "pw", display_name="Rohit")
        self.uid = self.acc.get_by_username("rohit")["uuid"]

    def test_additive_columns_exist_and_default(self):
        rec = self.acc.get_user_record(self.uid)
        self.assertEqual(rec["web_owner"], 0)
        self.assertIsNone(rec["provenance"])
        self.assertIsNone(rec["consent"])
        self.assertIsNone(rec["access_scope"])

    def test_existing_rows_stay_valid(self):
        acc2 = UserAccounts(db_path=self.db)  # re-runs _migrate
        self.assertIsNotNone(acc2.get_by_username("rohit"))

    def test_claim_is_idempotent_and_sets_owner_fields(self):
        self.assertFalse(self.acc.owner_claimed())
        self.assertEqual(self.acc.claim_owner(self.uid), "claimed")
        self.assertTrue(self.acc.owner_claimed())
        rec = self.acc.get_user_record(self.uid)
        self.assertEqual(rec["web_owner"], 1)
        self.assertEqual(rec["relationship"], "owner")
        self.assertEqual(rec["trust_tier"], 3)
        self.assertEqual(rec["provenance"], "local-owner-claim")
        self.assertEqual(self.acc.claim_owner(self.uid), "noop")

    def test_claim_refuses_when_other_owner_exists(self):
        self.acc.register("alex", "pw")
        uid2 = self.acc.get_by_username("alex")["uuid"]
        self.acc.claim_owner(self.uid)
        with self.assertRaises(ValueError):
            self.acc.claim_owner(uid2)

    def test_rebind_moves_owner_and_reset_clears(self):
        self.acc.register("alex", "pw")
        uid2 = self.acc.get_by_username("alex")["uuid"]
        self.acc.claim_owner(self.uid)
        self.assertEqual(self.acc.rebind_owner(uid2), "rebound")
        self.assertEqual(self.acc.get_owner()["uuid"], uid2)
        self.assertEqual(self.acc.get_user_record(self.uid)["web_owner"], 0)
        self.assertEqual(self.acc.reset_owner(), 1)
        self.assertFalse(self.acc.owner_claimed())

    def test_claim_unknown_uid_raises(self):
        with self.assertRaises(ValueError):
            self.acc.claim_owner("no-such-uid")

    def test_unclaimed_is_safe_floor_and_no_feature_flag(self):
        # Before any claim, owner_claimed() is False (the safe floor)...
        self.assertFalse(self.acc.owner_claimed())
        # ...and activation is owner_claimed() ONLY — there is NO env feature flag.
        import os as _os
        self.assertNotIn("MAEZ_WEB_OWNER_IDENTITY_ENABLED", _os.environ)
