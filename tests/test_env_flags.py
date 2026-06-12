import os
import unittest

from core.infra.env_flags import strict_env_flag


class StrictEnvFlagTest(unittest.TestCase):
    VAR = "MAEZ_TEST_STRICT_FLAG_XYZ"

    def setUp(self):
        self._saved = os.environ.get(self.VAR)
        os.environ.pop(self.VAR, None)

    def tearDown(self):
        if self._saved is None:
            os.environ.pop(self.VAR, None)
        else:
            os.environ[self.VAR] = self._saved

    def test_unset_is_off(self):
        self.assertFalse(strict_env_flag(self.VAR))

    def test_zero_is_off_not_truthy(self):
        # the exact footgun this helper exists to kill
        os.environ[self.VAR] = "0"
        self.assertFalse(strict_env_flag(self.VAR))

    def test_falsey_words_are_off(self):
        for val in ("false", "no", "off", "", "   "):
            os.environ[self.VAR] = val
            self.assertFalse(strict_env_flag(self.VAR), val)

    def test_truthy_words_are_on(self):
        for val in ("1", "true", "yes", "on", "ON", " True ", "YeS"):
            os.environ[self.VAR] = val
            self.assertTrue(strict_env_flag(self.VAR), val)

    def test_arbitrary_string_is_off(self):
        # NOT a presence check — a non-truthy value reads off (unlike bool(env))
        os.environ[self.VAR] = "wayland-0"
        self.assertFalse(strict_env_flag(self.VAR))
