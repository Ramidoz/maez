"""Guard the recall bundle flag as the only production toggle source."""

import os
import re
import unittest

_RAW_FLAGS = (
    "MAEZ_DISPATCHER_ENABLED",
    "MAEZ_FOCUSED_COGNITION_ENABLED",
    "MAEZ_LIVING_RECALL_ENABLED",
)
_ALLOWED = {
    os.path.join("core", "routing", "recall_stack_config.py"),
}
_ROOTS = ("core", "daemon", "skills")
_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class RecallFlagSingleSourceTest(unittest.TestCase):
    def test_no_raw_flag_reads_outside_resolver(self):
        pattern = re.compile("|".join(re.escape(flag) for flag in _RAW_FLAGS))
        offenders: list[str] = []

        for root in _ROOTS:
            base = os.path.join(_REPO, root)
            for dirpath, _dirs, files in os.walk(base):
                for fname in files:
                    if not fname.endswith(".py"):
                        continue
                    abspath = os.path.join(dirpath, fname)
                    relpath = os.path.relpath(abspath, _REPO)
                    if relpath in _ALLOWED:
                        continue
                    with open(abspath, encoding="utf-8") as fh:
                        if pattern.search(fh.read()):
                            offenders.append(relpath)

        self.assertEqual(
            offenders,
            [],
            "raw recall flag names found outside the resolver: %s" % offenders,
        )


if __name__ == "__main__":
    unittest.main()
