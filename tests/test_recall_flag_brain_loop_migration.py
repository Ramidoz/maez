import os
import unittest
from unittest import mock


_RECALL_FLAGS = (
    "MAEZ_RECALL_TRIAD_ENABLED",
    "MAEZ_DISPATCHER_ENABLED",
    "MAEZ_FOCUSED_COGNITION_ENABLED",
    "MAEZ_LIVING_RECALL_ENABLED",
)


def _clean_env(**values):
    env = {name: values[name] for name in values}
    return mock.patch.dict(
        os.environ,
        {name: "" for name in _RECALL_FLAGS} | env,
        clear=False,
    )


class BrainLoopMigrationTest(unittest.TestCase):
    def test_bundle_on_enables_dispatcher_and_living(self):
        from core import brain_loop

        with _clean_env(MAEZ_RECALL_TRIAD_ENABLED="1"):
            self.assertTrue(brain_loop._dispatcher_enabled())
            self.assertTrue(brain_loop._living_recall_enabled())

    def test_raw_dispatcher_flag_alone_is_inert(self):
        from core import brain_loop

        with _clean_env(MAEZ_DISPATCHER_ENABLED="1"):
            self.assertFalse(brain_loop._dispatcher_enabled())
            self.assertFalse(brain_loop._living_recall_enabled())

    def test_all_off(self):
        from core import brain_loop

        with _clean_env():
            self.assertFalse(brain_loop._dispatcher_enabled())
            self.assertFalse(brain_loop._living_recall_enabled())


if __name__ == "__main__":
    unittest.main()
