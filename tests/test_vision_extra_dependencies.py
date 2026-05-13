import tomllib
import unittest
from pathlib import Path


class VisionExtraDependenciesTests(unittest.TestCase):
    def test_vision_extra_declares_presence_detector_runtime_dependency(self):
        data = tomllib.loads(Path("pyproject.toml").read_text())
        vision_deps = data["project"]["optional-dependencies"]["vision"]
        normalized = {dep.split(">=", 1)[0] for dep in vision_deps}

        self.assertIn("opencv-python", normalized)
        self.assertIn("mediapipe", normalized)


if __name__ == "__main__":
    unittest.main()
