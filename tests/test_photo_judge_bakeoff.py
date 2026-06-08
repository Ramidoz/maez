import importlib
import json
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests" / "data" / "judge_eval_photo_contradiction_v1.jsonl"

STRATA = {
    "real_anchor", "numeric_ocr", "entity_title",
    "grounded_control", "uncertainty_control",
}


class CorpusSchema(unittest.TestCase):
    def setUp(self):
        from scripts.photo_judge_bakeoff import load_corpus
        self.rows = load_corpus(str(CORPUS))

    def test_required_fields_and_enums(self):
        for r in self.rows:
            for f in ("id", "stratum", "premise", "reply", "hypothesis",
                      "expected", "must_catch", "source"):
                self.assertIn(f, r, f"{r.get('id')} missing {f}")
            self.assertIn(r["stratum"], STRATA, r["id"])
            self.assertIn(r["expected"], {"grounded", "contradicts"}, r["id"])
            self.assertIsInstance(r["must_catch"], bool, r["id"])

    def test_all_five_strata_present_from_field(self):
        seen = {r["stratum"] for r in self.rows}   # read from FIELD, never inferred
        self.assertEqual(seen, STRATA)

    def test_wwdc_anchor_present_and_must_catch(self):
        anchors = [r for r in self.rows if r["stratum"] == "real_anchor"]
        self.assertTrue(anchors)
        wwdc = [r for r in anchors if "wwdc" in r["id"].lower()]
        self.assertTrue(wwdc, "WWDC2024 anchor case must exist")
        self.assertTrue(wwdc[0]["must_catch"])
        self.assertEqual(wwdc[0]["expected"], "contradicts")

    def test_has_grounded_and_uncertainty_controls(self):
        exp = {r["expected"] for r in self.rows}
        self.assertIn("grounded", exp)  # false-flag guard exists
        self.assertGreaterEqual(
            sum(1 for r in self.rows if r["stratum"] == "uncertainty_control"), 1)


class ThresholdProtocol(unittest.TestCase):
    def test_grid_is_fixed_and_shared(self):
        from scripts.photo_judge_bakeoff_adapters import THRESHOLD_GRID
        self.assertEqual(THRESHOLD_GRID, (0.3, 0.4, 0.5, 0.6, 0.7))

    def test_score_maps_to_label_via_threshold(self):
        from scripts.photo_judge_bakeoff_adapters import score_to_label
        # convention: HIGHER score = more grounded; below threshold = contradicts
        self.assertEqual(score_to_label(0.8, 0.5), "grounded")
        self.assertEqual(score_to_label(0.2, 0.5), "contradicts")
        self.assertEqual(score_to_label(0.5, 0.5), "grounded")  # >= is grounded

    def test_verdict_carries_fields(self):
        from scripts.photo_judge_bakeoff_adapters import Verdict
        v = Verdict(label="contradicts", score=0.1, latency_s=0.02)
        self.assertEqual(v.label, "contradicts")
        self.assertEqual(v.score, 0.1)
        self.assertEqual(v.latency_s, 0.02)


class AdapterBase(unittest.TestCase):
    def test_predict_applies_threshold_and_times(self):
        from scripts.photo_judge_bakeoff_adapters import CandidateAdapter, Verdict

        class FakeScore(CandidateAdapter):
            name = "fake"
            score_based = True
            def _load(self): return object()
            def _raw_predict(self, premise, hypothesis): return 0.2  # low → contradicts

        a = FakeScore(threshold=0.5)
        v = a.predict("p", "h")
        self.assertIsInstance(v, Verdict)
        self.assertEqual(v.label, "contradicts")
        self.assertGreaterEqual(v.latency_s, 0.0)

    def test_unavailable_on_load_failure(self):
        from scripts.photo_judge_bakeoff_adapters import CandidateAdapter

        class Broken(CandidateAdapter):
            name = "broken"
            score_based = True
            def _load(self): raise RuntimeError("no weights")
            def _raw_predict(self, premise, hypothesis): return 0.9

        a = Broken(threshold=0.5)
        v = a.predict("p", "h")
        self.assertEqual(v.label, "unavailable")
        self.assertIn("no weights", a.unavailable_reason)


class ConcreteAdapters(unittest.TestCase):
    def test_all_adapters_registered(self):
        from scripts.photo_judge_bakeoff_adapters import ALL_ADAPTERS
        names = {a.name for a in ALL_ADAPTERS}
        self.assertEqual(names, {
            "hhem", "minicheck", "thinkncheck", "nli", "reranker", "chatjudge"})

    def test_score_based_vs_label_native_flags(self):
        from scripts.photo_judge_bakeoff_adapters import (
            HHEMAdapter, RerankerAdapter, NLIAdapter,
            MiniCheckAdapter, ThinknCheckAdapter, ChatJudgeAdapter)
        self.assertTrue(HHEMAdapter.score_based)
        self.assertTrue(RerankerAdapter.score_based)
        self.assertTrue(NLIAdapter.score_based)
        self.assertFalse(MiniCheckAdapter.score_based)   # label-native 0/1
        self.assertFalse(ThinknCheckAdapter.score_based) # verdict
        self.assertFalse(ChatJudgeAdapter.score_based)   # yes/no

    def test_hhem_low_score_is_contradiction(self):
        from scripts.photo_judge_bakeoff_adapters import HHEMAdapter
        # Patch _load at the CLASS level BEFORE instantiation so __init__'s
        # _load() never imports transformers or touches disk.
        with mock.patch.object(HHEMAdapter, "_load", return_value=object()), \
             mock.patch.object(HHEMAdapter, "_raw_predict", return_value=0.05):
            a = HHEMAdapter(threshold=0.5)
            self.assertEqual(a.predict("p", "h").label, "contradicts")

    def test_minicheck_label_native(self):
        from scripts.photo_judge_bakeoff_adapters import MiniCheckAdapter
        with mock.patch.object(MiniCheckAdapter, "_load", return_value=object()), \
             mock.patch.object(MiniCheckAdapter, "_raw_predict",
                               return_value="contradicts"):
            a = MiniCheckAdapter()
            v = a.predict("p", "h")
            self.assertEqual(v.label, "contradicts")
            self.assertIsNone(v.score)  # no threshold for label-native


class Aggregator(unittest.TestCase):
    def _rows(self):
        return [
            {"id": "c1", "stratum": "numeric_ocr", "expected": "contradicts", "must_catch": True},
            {"id": "c2", "stratum": "entity_title", "expected": "contradicts", "must_catch": False},
            {"id": "g1", "stratum": "grounded_control", "expected": "grounded", "must_catch": False},
        ]

    def test_catch_falseflag_and_must_catch(self):
        from scripts.photo_judge_bakeoff import aggregate_candidate
        rows = self._rows()
        # verdicts: c1 caught, c2 MISSED (graded grounded), g1 correct
        verdicts = {
            "c1": ("contradicts", 0.10),
            "c2": ("grounded", 0.30),
            "g1": ("grounded", 0.40),
        }
        agg = aggregate_candidate("hhem", rows, verdicts,
                                  meta={"threshold": 0.5})
        self.assertAlmostEqual(agg["catch_rate"], 0.5)        # 1 of 2 contradicts caught
        self.assertEqual(agg["false_flag_rate"], 0.0)         # g1 not flagged
        self.assertEqual(agg["missed_must_catch"], [])        # c1 (must_catch) WAS caught
        self.assertEqual(agg["meta"]["threshold"], 0.5)
        ps = agg["per_stratum"]
        self.assertEqual(ps["numeric_ocr"]["contradiction_n"], 1)
        self.assertEqual(ps["numeric_ocr"]["caught"], 1)
        self.assertEqual(ps["numeric_ocr"]["catch_rate"], 1.0)
        self.assertEqual(ps["entity_title"]["caught"], 0)       # c2 missed
        self.assertEqual(ps["grounded_control"]["grounded_n"], 1)
        self.assertEqual(ps["grounded_control"]["false_flags"], 0)
        self.assertEqual(ps["grounded_control"]["false_flag_rate"], 0.0)

    def test_missed_must_catch_is_loud(self):
        from scripts.photo_judge_bakeoff import aggregate_candidate
        rows = self._rows()
        verdicts = {"c1": ("grounded", 0.9), "c2": ("contradicts", 0.1),
                    "g1": ("grounded", 0.4)}  # c1 is must_catch and MISSED
        agg = aggregate_candidate("x", rows, verdicts, meta={})
        self.assertEqual(agg["missed_must_catch"], ["c1"])

    def test_error_grade_missed_not_false_flag_and_counted(self):
        from scripts.photo_judge_bakeoff import aggregate_candidate
        rows = self._rows()  # c1 numeric/contradicts/must, c2 entity/contra, g1 grounded
        verdicts = {"c1": ("error", 0.1),       # contradiction + error → missed
                    "c2": ("contradicts", 0.2),  # caught
                    "g1": ("error", 0.3)}         # grounded + error → NOT a false flag
        agg = aggregate_candidate("x", rows, verdicts, meta={})
        self.assertEqual(agg["error_count"], 2)
        self.assertEqual(agg["catch_rate"], 0.5)        # c2 caught; c1 errored = missed
        self.assertEqual(agg["false_flag_rate"], 0.0)   # g1 error is NOT a false flag
        self.assertIn("c1", agg["missed_must_catch"])   # must_catch + errored = missed
        self.assertEqual(agg["per_stratum"]["grounded_control"]["errors"], 1)

    def test_zero_candidates_report(self):
        from scripts.photo_judge_bakeoff import build_report
        report = build_report([])   # no candidate aggregates
        self.assertIn("RECOMMENDATION: none", report["text"])
        self.assertEqual(report["aggregates"], [])

    def test_unavailable_candidate_in_report(self):
        from scripts.photo_judge_bakeoff import build_report
        agg = {"name": "hhem", "runnable": False,
               "meta": {"unavailable_reason": "no weights"},
               "catch_rate": None, "false_flag_rate": None,
               "missed_must_catch": [], "per_stratum": {}, "latency": {}}
        report = build_report([agg])
        self.assertIn("no weights", report["text"])
        self.assertIn("RECOMMENDATION: none", report["text"])  # 0 runnable


class HardContract(unittest.TestCase):
    """Scopes to the RUNNER FILE ONLY (photo_judge_bakeoff.py). It must NEVER
    inspect photo_judge_bakeoff_fetch.py, whose job IS huggingface_hub/network.
    Tests DANGEROUS BEHAVIOR structurally (imports / env-assignment / file-write),
    not string mentions — the runner docstring legitimately NAMES model.env /
    MAEZ_JUDGE_BASE_URL / the fetch helper while promising not to TOUCH them."""

    def _runner_ast(self):
        import ast
        return ast.parse((ROOT / "scripts" / "photo_judge_bakeoff.py").read_text())

    def test_runner_imports_no_network_or_fetch_or_subprocess(self):
        import ast
        mods = set()
        for n in ast.walk(self._runner_ast()):
            if isinstance(n, ast.Import):
                mods |= {a.name.split(".")[0] for a in n.names}
            elif isinstance(n, ast.ImportFrom) and n.module:
                mods.add(n.module.split(".")[0])
                self.assertNotIn("photo_judge_bakeoff_fetch", n.module,
                                 "runner must not import the fetch helper")
        self.assertNotIn("huggingface_hub", mods)
        self.assertNotIn("subprocess", mods)  # → cannot shell out to systemctl

    def test_runner_never_assigns_live_judge_url(self):
        import ast
        for n in ast.walk(self._runner_ast()):
            if isinstance(n, ast.Assign):
                for t in n.targets:
                    if (isinstance(t, ast.Subscript)
                            and isinstance(t.value, ast.Attribute)
                            and t.value.attr == "environ"):
                        key = getattr(t.slice, "value", None)
                        self.assertNotEqual(
                            key, "MAEZ_JUDGE_BASE_URL",
                            "runner must not mutate the live judge URL")

    def test_runner_writes_no_model_env(self):
        import ast
        for n in ast.walk(self._runner_ast()):
            if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "open":
                consts = [a for a in n.args if isinstance(a, ast.Constant)]
                if (len(consts) >= 2 and isinstance(consts[1].value, str)
                        and "w" in consts[1].value):
                    self.assertNotIn("model.env", str(consts[0].value))


class RunnerMain(unittest.TestCase):
    def test_main_runs_corpus_through_a_fake_adapter_and_writes_report(self):
        import scripts.photo_judge_bakeoff as r
        from scripts.photo_judge_bakeoff_adapters import CandidateAdapter

        class FakeAll(CandidateAdapter):
            name = "fakeall"
            score_based = False
            def _load(self): return object()
            def _raw_predict(self, premise, hypothesis): return "contradicts"

        import tempfile
        outdir = tempfile.mkdtemp()
        rc = r.main(["--label", "t", "--out-dir", outdir,
                     "--corpus", str(CORPUS)],
                    adapters=[FakeAll(threshold=None)])
        self.assertEqual(rc, 0)
        md = list(Path(outdir).glob("*.md"))
        self.assertTrue(md)
        self.assertIn("RECOMMENDATION", md[0].read_text())

    def test_score_based_candidate_expands_across_grid(self):
        # un-riggable: a score-based candidate yields ONE row PER grid threshold.
        import scripts.photo_judge_bakeoff as r
        from scripts.photo_judge_bakeoff_adapters import (
            CandidateAdapter, THRESHOLD_GRID)

        class FakeScore(CandidateAdapter):
            name = "fakescore"
            score_based = True
            def _load(self): return object()
            def _raw_predict(self, premise, hypothesis): return 0.6

        rows = r.load_corpus(str(CORPUS))
        aggs = r.run_candidate(FakeScore(threshold=None), rows)
        self.assertEqual(len(aggs), len(THRESHOLD_GRID))
        self.assertEqual({a["name"] for a in aggs},
                         {f"fakescore@{t}" for t in THRESHOLD_GRID})

    def test_per_case_error_does_not_crash_the_sweep(self):
        # A per-case predict() failure (score None) must NOT abort the otherwise
        # runnable candidate's threshold sweep — it is recorded as an error.
        import scripts.photo_judge_bakeoff as r
        from scripts.photo_judge_bakeoff_adapters import CandidateAdapter

        class FlakyScore(CandidateAdapter):
            name = "flaky"
            score_based = True
            def _load(self): return object()
            def _raw_predict(self, premise, hypothesis):
                if "boom" in hypothesis:
                    raise RuntimeError("model OOM on this case")
                return 0.1  # low → contradicts

        rows = [
            {"id": "ok1", "stratum": "numeric_ocr", "premise": "p", "reply": "x",
             "hypothesis": "fine", "expected": "contradicts", "must_catch": False,
             "source": "t"},
            {"id": "err1", "stratum": "entity_title", "premise": "p", "reply": "x",
             "hypothesis": "boom", "expected": "contradicts", "must_catch": False,
             "source": "t"},
        ]
        aggs = r.run_candidate(FlakyScore(threshold=None), rows)  # must NOT raise
        a0 = aggs[0]
        self.assertTrue(a0["runnable"])          # partial failure ≠ unavailable
        self.assertEqual(a0["error_count"], 1)   # err1 recorded as a per-case error
        self.assertEqual(a0["catch_rate"], 0.5)  # ok1 caught; err1 errored = missed


class FetchHelper(unittest.TestCase):
    def _fake_snapshot(self, repo_id, revision, local_dir, **kw):
        Path(local_dir).mkdir(parents=True, exist_ok=True)
        (Path(local_dir) / "weights.bin").write_bytes(b"abc")
        return local_dir

    def _tmp(self):
        import tempfile
        return tempfile.mkdtemp()

    def test_fetch_pins_and_hashes_smoke_skipped_by_default(self):
        import scripts.photo_judge_bakeoff_fetch as f
        with mock.patch.object(f, "_snapshot_download", self._fake_snapshot):
            rec = f.fetch_one(repo_id="vectara/x", revision="deadbeef",
                              name="hhem", dest_root=self._tmp())
        self.assertEqual(rec["revision"], "deadbeef")     # PINNED
        self.assertEqual(len(rec["sha256"]), 64)          # HASH recorded
        self.assertEqual(rec["smoke"], "skipped")         # honest default

    def test_fetch_runs_smoke_hook_when_given(self):
        import scripts.photo_judge_bakeoff_fetch as f
        def boom(dest):
            raise RuntimeError("bad weights")
        with mock.patch.object(f, "_snapshot_download", self._fake_snapshot):
            ok = f.fetch_one(repo_id="x", revision="r", name="n",
                             dest_root=self._tmp(), smoke_fn=lambda dest: None)
            bad = f.fetch_one(repo_id="x", revision="r", name="n",
                              dest_root=self._tmp(), smoke_fn=boom)
        self.assertEqual(ok["smoke"], "ok")
        self.assertTrue(bad["smoke"].startswith("failed"))   # honest failure

    def test_fetch_refuses_unpinned_revision(self):
        import scripts.photo_judge_bakeoff_fetch as f
        with self.assertRaises(ValueError):
            f.fetch_one(repo_id="x", revision=None, name="n", dest_root="/tmp/x")

    def test_fetch_helper_is_a_separate_file(self):   # moved from Task 5 (fix #3)
        self.assertTrue((ROOT / "scripts" / "photo_judge_bakeoff_fetch.py").exists())

    def test_cli_parses_and_calls_fetch_one(self):
        import scripts.photo_judge_bakeoff_fetch as f
        seen = {}
        def fake_fetch_one(**kw):
            seen.update(kw)
            return {"name": kw["name"], "smoke": "skipped"}
        with mock.patch.object(f, "fetch_one", fake_fetch_one):
            rc = f.main(["--repo-id", "vectara/x", "--revision", "abc",
                         "--name", "hhem", "--dest-root", "/tmp/bk"])
        self.assertEqual(rc, 0)
        self.assertEqual(seen["revision"], "abc")
        self.assertEqual(seen["name"], "hhem")


class ReproFingerprint(unittest.TestCase):
    """Every report row must carry the full fingerprint (model_id / revision /
    adapter_version / sha256 / threshold / device) — reproducibility is the point."""

    def test_revision_in_meta_and_fingerprint_in_report(self):
        import scripts.photo_judge_bakeoff as r
        from scripts.photo_judge_bakeoff_adapters import CandidateAdapter

        class Fake(CandidateAdapter):
            name = "fake"
            score_based = False
            model_id = "vectara/x"
            revision = "abc123"
            def _load(self): return object()
            def _raw_predict(self, p, h): return "contradicts"

        rows = r.load_corpus(str(CORPUS))
        aggs = r.run_candidate(Fake(threshold=None), rows)
        self.assertEqual(aggs[0]["meta"]["revision"], "abc123")   # carried into meta
        rpt = r.build_report(aggs)["text"]
        self.assertIn("vectara/x", rpt)        # model_id printed
        self.assertIn("abc123", rpt)           # revision printed
        self.assertIn("adapter_version", rpt)  # column present

    def test_fetch_writes_manifest_with_revision_and_sha256(self):
        import json as _json
        import scripts.photo_judge_bakeoff_fetch as f

        def fake_snap(repo_id, revision, local_dir, **kw):
            Path(local_dir).mkdir(parents=True, exist_ok=True)
            (Path(local_dir) / "w.bin").write_bytes(b"abc")
            return local_dir

        import tempfile
        root = tempfile.mkdtemp()
        with mock.patch.object(f, "_snapshot_download", fake_snap):
            rec = f.fetch_one(repo_id="vectara/x", revision="deadbeef",
                              name="hhem", dest_root=root)
        man = Path(root) / "hhem" / "bakeoff_manifest.json"
        self.assertTrue(man.exists())          # fetch records a manifest
        m = _json.loads(man.read_text())
        self.assertEqual(m["revision"], "deadbeef")
        self.assertEqual(m["sha256"], rec["sha256"])

    def test_adapter_reads_revision_from_manifest(self):
        import json as _json
        import tempfile
        from scripts.photo_judge_bakeoff_adapters import read_bakeoff_manifest
        d = tempfile.mkdtemp()
        (Path(d) / "bakeoff_manifest.json").write_text(
            _json.dumps({"revision": "rev9", "sha256": "f00"}))
        man = read_bakeoff_manifest(d)
        self.assertEqual(man["revision"], "rev9")
        self.assertEqual(man["sha256"], "f00")
        self.assertIsNone(read_bakeoff_manifest(tempfile.mkdtemp()))  # absent → None


if __name__ == "__main__":
    unittest.main()
