import os
from pathlib import Path
import stat
import subprocess
import tempfile
import textwrap
import unittest

SETUP_SCRIPT = Path(__file__).resolve().parents[1] / "devices" / "jetson_presence" / "setup_models.sh"


class SetupModelsDepsTests(unittest.TestCase):
    def test_deps_pins_numpy_below_two_for_apt_opencv_compatibility(self):
        setup = SETUP_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("cuda-python", setup)
        self.assertIn("onnxruntime", setup)
        self.assertIn("'numpy<2'", setup)
        self.assertNotIn(" pycuda ", setup)
        self.assertNotIn(" numpy\n", setup)

    def test_deps_fails_loudly_when_system_python_has_no_pip(self):
        with tempfile.TemporaryDirectory() as td:
            fake_python = Path(td) / "python3"
            fake_python.write_text(
                textwrap.dedent(
                    """\
                    #!/usr/bin/env bash
                    if [ "$1" = "-m" ] && [ "$2" = "pip" ] && [ "$3" = "--version" ]; then
                      echo "/usr/bin/python3: No module named pip" >&2
                      exit 1
                    fi
                    echo "unexpected fake python invocation: $*" >&2
                    exit 99
                    """
                ),
                encoding="utf-8",
            )
            fake_python.chmod(fake_python.stat().st_mode | stat.S_IXUSR)

            result = subprocess.run(
                [str(SETUP_SCRIPT), "deps"],
                env={**os.environ, "PYTHON": str(fake_python)},
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertNotEqual(result.returncode, 0)
        output = result.stdout + result.stderr
        self.assertIn("sudo apt install python3-pip", output)
        self.assertIn("python3 -m pip --version", output)


if __name__ == "__main__":
    unittest.main()
