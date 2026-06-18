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
