from __future__ import annotations

import os
import unittest

from core.intake_bus import world_observation_lane as lane


class _FakeMemory:
    def __init__(self, existing=None):
        self.stored = []
        self._existing = existing

    def body_row_id_by_source_ref(self, source_ref, *, egress_origin_class):
        return self._existing

    def store(self, **kwargs):
        kwargs.setdefault("source_ref", kwargs.get("metadata", {}).get("source_ref"))
        self.stored.append(kwargs)
        return "body-1"


class _Spec:
    def __init__(self, sources):
        self.external_sources = sources


class _Turn:
    def __init__(
        self,
        sources=("WEB_SEARCH",),
        summaries=("WEB_SEARCH",),
        outcome="ALL_SUCCEEDED",
    ):
        self.effective_spec = _Spec(list(sources))
        self.source_summaries = [type("S", (), {"source": s})() for s in summaries]
        self.fresh_attempt_outcome = outcome


def _evidence():
    # FreshBlock.text shape: format_for_context output.
    return [
        "[WEB SEARCH] Releases - llama.cpp - https://github.com/x/releases - "
        "b9601 released today"
    ]


class ConditionTests(unittest.TestCase):
    def test_all_legs_hold(self):
        self.assertTrue(lane.evaluate_write_condition(_Turn()))

    def test_leg_no_web_search_in_spec(self):
        self.assertFalse(lane.evaluate_write_condition(_Turn(sources=("LIVE_REDDIT",))))

    def test_leg_no_summary(self):
        self.assertFalse(lane.evaluate_write_condition(_Turn(summaries=("LIVE_REDDIT",))))

    def test_leg_failed_outcome(self):
        self.assertFalse(lane.evaluate_write_condition(_Turn(outcome="ALL_FAILED")))

    def test_malformed_turn_is_false_not_raise(self):
        self.assertFalse(lane.evaluate_write_condition(object()))


class WriteTests(unittest.TestCase):
    def setUp(self):
        os.environ["MAEZ_SEARCH_AS_SENSE_ENABLED"] = "1"
        self.addCleanup(lambda: os.environ.pop("MAEZ_SEARCH_AS_SENSE_ENABLED", None))

    def test_writes_one_observation(self):
        mem = _FakeMemory()
        out = lane.write_world_observation(
            mem,
            query="latest llama.cpp release",
            evidence_texts=_evidence(),
            diagnostic_id="fan-123",
        )
        self.assertEqual(out, "admitted")
        self.assertEqual(len(mem.stored), 1)
        rec = mem.stored[0]
        provenance = rec["provenance_source"]
        self.assertEqual(str(getattr(provenance, "value", provenance)), "external_web")
        self.assertIn("latest llama.cpp release", rec["content"])
        self.assertIn("github.com", rec["content"])

    def test_flag_off_never_writes(self):
        os.environ.pop("MAEZ_SEARCH_AS_SENSE_ENABLED", None)
        mem = _FakeMemory()
        out = lane.write_world_observation(
            mem,
            query="q",
            evidence_texts=_evidence(),
            diagnostic_id="fan-1",
        )
        self.assertEqual(out, "disabled")
        self.assertEqual(mem.stored, [])

    def test_idempotent_on_diagnostic_id(self):
        mem = _FakeMemory(existing="already-there")
        out = lane.write_world_observation(
            mem,
            query="q",
            evidence_texts=_evidence(),
            diagnostic_id="fan-123",
        )
        self.assertEqual(out, "already_admitted")
        self.assertEqual(mem.stored, [])

    def test_provenance_purity_no_owner_text_beyond_query(self):
        mem = _FakeMemory()
        lane.write_world_observation(
            mem,
            query="latest llama.cpp release",
            evidence_texts=_evidence(),
            diagnostic_id="fan-9",
        )
        content = mem.stored[0]["content"]
        self.assertIn("web evidence entered the synthesis context", content)
        self.assertNotIn("Maez used", content)

    def test_memory_failure_never_raises(self):
        class _Boom(_FakeMemory):
            def store(self, **kwargs):
                raise RuntimeError("db locked")

        out = lane.write_world_observation(
            _Boom(),
            query="q",
            evidence_texts=_evidence(),
            diagnostic_id="fan-1",
        )
        self.assertEqual(out, "error_dropped")

    def test_real_bus_validation_accepts_the_origin_class(self):
        from core.egress.gate import KNOWN_ORIGINS

        self.assertIn(lane.WORLD_OBSERVATION_EGRESS, KNOWN_ORIGINS)
        self.assertNotIn("sovereign_local_search", KNOWN_ORIGINS)
        mem = _FakeMemory()
        out = lane.write_world_observation(
            mem,
            query="real validation",
            evidence_texts=_evidence(),
            diagnostic_id="fan-real",
        )
        self.assertEqual(out, "admitted")

    def test_source_url_extraction_from_evidence_text(self):
        urls = lane.extract_source_urls(_evidence())
        self.assertEqual(urls, ["https://github.com/x/releases"])


class PageObservationTests(unittest.TestCase):
    def setUp(self):
        for key in ("MAEZ_SEARCH_AS_SENSE_ENABLED", "MAEZ_PAGE_READ_ENABLED"):
            os.environ.pop(key, None)
            self.addCleanup(lambda key=key: os.environ.pop(key, None))

    def test_page_observation_writes_with_only_page_flag(self):
        os.environ["MAEZ_PAGE_READ_ENABLED"] = "1"
        mem = _FakeMemory()
        out = lane.write_page_observation(
            mem,
            url="https://github.com/x/releases",
            title="Releases",
            excerpt="b9601 released June 11",
            diagnostic_id="diag-p1",
        )

        self.assertEqual(out, "admitted")
        rec = mem.stored[0]
        self.assertIn("https://github.com/x/releases", rec["content"])
        self.assertIn("Releases", rec["content"])

    def test_page_observation_disabled_when_neither_flag(self):
        mem = _FakeMemory()
        out = lane.write_page_observation(
            mem,
            url="https://a",
            title="t",
            excerpt="x",
            diagnostic_id="d1",
        )

        self.assertEqual(out, "disabled")
        self.assertEqual(mem.stored, [])

    def test_web_search_write_still_works_with_only_search_flag(self):
        os.environ["MAEZ_SEARCH_AS_SENSE_ENABLED"] = "1"
        mem = _FakeMemory()
        out = lane.write_world_observation(
            mem,
            query="q",
            evidence_texts=_evidence(),
            diagnostic_id="d2",
        )

        self.assertEqual(out, "admitted")

    def test_page_source_ref_and_reclass_metadata(self):
        os.environ["MAEZ_PAGE_READ_ENABLED"] = "1"
        mem = _FakeMemory()
        lane.write_page_observation(
            mem,
            url="https://a.example/p",
            title="T",
            excerpt="x",
            diagnostic_id="diag-9",
        )

        rec = mem.stored[0]
        self.assertTrue(rec["source_ref"].startswith("page_read:diag-9:"))
        metadata = rec["metadata"]
        self.assertEqual(metadata["owner_supplied_url"], "true")
        self.assertEqual(metadata["preflight_allowed"], "true")
        self.assertEqual(metadata["text_content_type"], "true")

    def test_page_observation_idempotent(self):
        os.environ["MAEZ_PAGE_READ_ENABLED"] = "1"
        mem = _FakeMemory(existing="row-1")
        out = lane.write_page_observation(
            mem,
            url="https://a",
            title="t",
            excerpt="x",
            diagnostic_id="diag-9",
        )

        self.assertEqual(out, "already_admitted")

    def test_condition_source_aware(self):
        self.assertTrue(
            lane.evaluate_write_condition(
                _Turn(sources=("FETCH_URL",), summaries=("FETCH_URL",)),
                source_value="FETCH_URL",
            )
        )
        self.assertFalse(lane.evaluate_write_condition(_Turn(), source_value="FETCH_URL"))
        self.assertTrue(lane.evaluate_write_condition(_Turn()))


class ProgressEmitTests(unittest.TestCase):
    def test_emits_only_when_web_search_selected(self):
        from core.brain.brain_loop import _emit_search_progress

        calls = []
        _emit_search_progress(calls.append, ["WEB_SEARCH"], stage="start", count=None)
        _emit_search_progress(calls.append, ["WEB_SEARCH"], stage="results", count=5)
        _emit_search_progress(calls.append, ["LIVE_REDDIT"], stage="start", count=None)
        _emit_search_progress(None, ["WEB_SEARCH"], stage="start", count=None)
        self.assertEqual(calls, ["searching the web...", "reading 5 results..."])

    def test_pipeline_passthrough_gated_on_flag(self):
        import inspect

        from core.brain import brain_loop

        src = inspect.getsource(brain_loop.run_brain_loop)
        self.assertIn(
            "send_intermediate if sense_enabled() or page_read_enabled() else None",
            src,
        )
        sig = inspect.signature(brain_loop._run_dispatcher_pipeline)
        self.assertIn("send_intermediate", sig.parameters)


if __name__ == "__main__":
    unittest.main()
