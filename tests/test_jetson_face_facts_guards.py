import ast
import pathlib
import tempfile
import unittest

_REPO = pathlib.Path(__file__).resolve().parents[1]
_EDGE = _REPO / "devices" / "jetson_presence" / "jetson_presence"
_CONTRACT = _REPO / "core" / "body" / "jetson_face_facts.py"
_WEB = _REPO / "skills" / "web_interface.py"

_ABSENCE_TOKENS = (
    "owner_absent",
    "room_empty",
    "no_one_here",
    "nobody_present",
    "room_occupancy",
)
_WRITE_TOKENS = (
    "imwrite",
    "VideoWriter",
    "imencode",
    "write_bytes",
    ".tofile(",
    ".save(",
    "np.save",
    "'wb'",
    '"wb"',
    "'w+b'",
    '"w+b"',
    "'wb+'",
    '"wb+"',
    "'ab'",
    '"ab"',
    "'a+b'",
    '"a+b"',
)
_WEB_FNS = ("_jetson_write_face_facts_receipt", "api_jetson_face_facts_intake")
_EDGE_FILES = ("face_facts.py", "run.py", "config.py")


def _extract_functions(path, names):
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    out = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names:
            segment = ast.get_source_segment(src, node)
            if segment is not None:
                out[node.name] = segment
    return out


def _existing_edge_files():
    return [(_EDGE / name) for name in _EDGE_FILES if (_EDGE / name).exists()]


class NoAbsenceVerdictTests(unittest.TestCase):
    def _all_face_facts_sources(self):
        srcs = {"contract": _CONTRACT.read_text(encoding="utf-8")}
        for path in _existing_edge_files():
            srcs[path.name] = path.read_text(encoding="utf-8")
        for fn, body in _extract_functions(_WEB, _WEB_FNS).items():
            srcs[f"web:{fn}"] = body
        return srcs

    def test_no_absence_verdict_token_in_any_face_facts_source(self):
        offenders = []
        for where, src in self._all_face_facts_sources().items():
            for token in _ABSENCE_TOKENS:
                if token in src:
                    offenders.append(f"{where}: {token}")
        self.assertEqual(offenders, [])

    def test_probe_absence_token_trips_via_extractor(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "web.py"
            path.write_text(
                "def api_jetson_face_facts_intake():\n"
                "    logger.info('owner_absent=%s', 1)\n",
                encoding="utf-8",
            )
            body = _extract_functions(path, ("api_jetson_face_facts_intake",))[
                "api_jetson_face_facts_intake"
            ]
            self.assertTrue(any(token in body for token in _ABSENCE_TOKENS))


class NoEdgeDurableStoreTests(unittest.TestCase):
    def test_edge_face_facts_code_writes_nothing_durable(self):
        offenders = []
        for path in _existing_edge_files():
            src = path.read_text(encoding="utf-8")
            for token in _WRITE_TOKENS:
                if token in src:
                    offenders.append(f"{path.name}: {token}")
        self.assertEqual(offenders, [])

    def test_probe_write_trips(self):
        planted = "np.save('embedding.npy', vec)\n"
        self.assertTrue(any(token in planted for token in _WRITE_TOKENS))


class NoConsumerTests(unittest.TestCase):
    _BANNED = ("fresh_moment_receipts", "heartbeat", "promote", "_STORE", ".record(")

    def test_face_facts_web_fns_call_no_consumer_or_store(self):
        functions = _extract_functions(_WEB, _WEB_FNS)
        self.assertEqual(set(functions), set(_WEB_FNS), "both face-facts web fns must be isolable")
        offenders = []
        for fn, body in functions.items():
            for banned in self._BANNED:
                if banned in body:
                    offenders.append(f"{fn}: {banned}")
        self.assertEqual(offenders, [])

    def test_probe_consumer_call_trips_via_same_extractor(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "web.py"
            path.write_text(
                "def api_jetson_face_facts_intake():\n"
                "    _JETSON_FACE_FACTS_STORE.record(reading)\n",
                encoding="utf-8",
            )
            body = _extract_functions(path, ("api_jetson_face_facts_intake",))[
                "api_jetson_face_facts_intake"
            ]
            self.assertTrue(any(banned in body for banned in NoConsumerTests._BANNED))


if __name__ == "__main__":
    unittest.main()
