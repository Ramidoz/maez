import unittest


class IngestTokenLoadableTests(unittest.TestCase):
    def test_ingest_token_is_classified_secret(self):
        from core.infra.secrets import is_secret_name

        self.assertTrue(is_secret_name("MAEZ_GITHUB_INGEST_TOKEN"))

    def test_ingest_token_allowlisted(self):
        from core.infra.secrets import SECRET_NAMES

        self.assertIn("MAEZ_GITHUB_INGEST_TOKEN", SECRET_NAMES)


if __name__ == "__main__":
    unittest.main()
