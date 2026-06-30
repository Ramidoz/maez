# Frames AND crops are RAM-only. This matches B0's hardened guard
# (tests/test_jetson_edge_no_frame_write.py) token-for-token, extended to crops.
import os
import unittest

_B1A = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "devices", "jetson_presence", "jetson_presence", "b1a"))

_FORBIDDEN_WRITE = (
    "imwrite", "VideoWriter", "imencode", "write_bytes", ".tofile(", ".save(",
    "'wb'", '"wb"', "'w+b'", '"w+b"', "'wb+'", '"wb+"',
    "'r+'", '"r+"', "'r+b'", '"r+b"', "'rb+'", '"rb+"',
    "'ab'", '"ab"', "'a+b'", '"a+b"', "'ab+'", '"ab+"',
)


class NoCropWriteStructuralTests(unittest.TestCase):
    def test_b1a_writes_no_frames_or_crops(self):
        offenders = []
        for name in os.listdir(_B1A):
            if not name.endswith(".py"):
                continue
            src = open(os.path.join(_B1A, name), encoding="utf-8").read()
            for tok in _FORBIDDEN_WRITE:
                if tok in src:
                    offenders.append(f"{name}: {tok}")
        self.assertEqual(offenders, [], f"frames/crops are RAM-only; found: {offenders}")


if __name__ == "__main__":
    unittest.main()
