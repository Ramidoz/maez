# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Slice 2 — the vision truth contract (vision-organ redesign @df797f9).

The EVALUATION CONTRACT every screen sensor/model must meet: transcribe or
abstain, temp 0, field-level provenance, and unstructured specificity fails
closed. Its support is schema-only until Slice 3 checks pixels. Instrument
calibration of a SENSOR (ADR 0029) — never a rule on Maez's voice.
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from typing import get_args
from unittest import mock

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import core.vision_contract.truth_contract as contract  # noqa: E402
from core.vision_contract.truth_contract import (  # noqa: E402
    TRANSCRIBE_PROMPT,
    build_transcribe_request,
    parse_and_validate,
)


class ContractPromptTests(unittest.TestCase):
    def test_prompt_is_sensor_not_maez(self):
        # The eye reports evidence; Maez interprets. No impersonation.
        self.assertNotIn("You are Maez", TRANSCRIBE_PROMPT)
        low = TRANSCRIBE_PROMPT.lower()
        self.assertIn("[unreadable]", low)
        self.assertIn("transcribe", low)
        # Must forbid inference of the high-specificity classes.
        for banned in ("filename", "command", "application"):
            self.assertIn(banned, low)

    def test_request_builder_sets_temperature_zero(self):
        req = build_transcribe_request(image_b64="AAAA", model="m")
        self.assertEqual(req["temperature"], 0)
        self.assertEqual(req["model"], "m")
        content = req["messages"][0]["content"]
        self.assertEqual(content[0]["text"], TRANSCRIBE_PROMPT)


class ValidationTests(unittest.TestCase):
    def test_specificity_claims_are_shared(self):
        from core.vision_contract.truth_contract import find_specificity_claims

        claims = find_specificity_claims(
            "Open Main.PY, then git push; after that run $ pytest"
        )

        self.assertEqual(
            [(claim.kind, claim.value) for claim in claims],
            [
                ("filename", "Main.PY"),
                ("shell_command", "git push"),
                ("shell_prompt", "$ pytest"),
            ],
        )

    def test_verdict_carries_schema_version(self):
        for raw in (
            "REGION: titlebar\nTEXT: Settings\n",
            "NO_TEXT_VISIBLE",
            "",
        ):
            with self.subTest(raw=raw):
                self.assertEqual(
                    getattr(parse_and_validate(raw), "schema_version", None),
                    "vision_truth_contract.v1",
                )

    def test_contract_vocabularies_are_closed(self):
        self.assertTrue(hasattr(contract, "VerdictKind"))
        self.assertEqual(set(get_args(contract.VerdictKind)), {"ok", "empty", "rejected"})
        self.assertEqual(
            set(get_args(contract.FieldProvenance)),
            {"transcribed", "partial", "abstained"},
        )
        self.assertEqual(set(get_args(contract.VerdictSupport)), {"schema_only"})
        self.assertEqual(set(get_args(contract.EmptyReason)), {"no_text_visible"})
        self.assertEqual(
            set(get_args(contract.RejectionReason)),
            {
                "protocol_violation",
                "malformed_schema",
                "contradictory_provenance",
                "unstructured_specificity",
                "field_limit_exceeded",
                "invalid_region",
                "region_too_long",
                "text_too_long",
                "line_limit_exceeded",
                "raw_limit_exceeded",
            },
        )

    def test_text_length_bound(self):
        at_limit = parse_and_validate(f"REGION: editor\nTEXT: {'x' * 2_000}\n")
        over_limit = parse_and_validate(f"REGION: editor\nTEXT: {'x' * 2_001}\n")
        self.assertEqual(at_limit.verdict, "ok")
        self.assertEqual(over_limit.verdict, "rejected")
        self.assertEqual(over_limit.reason, "text_too_long")

    def test_field_count_bound(self):
        def raw_with_fields(count: int) -> str:
            return "".join(f"REGION: field {i}\nTEXT: value {i}\n" for i in range(count))

        at_limit = parse_and_validate(raw_with_fields(32))
        over_limit = parse_and_validate(raw_with_fields(33))
        self.assertEqual(at_limit.verdict, "ok")
        self.assertEqual(over_limit.verdict, "rejected")
        self.assertEqual(over_limit.reason, "field_limit_exceeded")

    def test_region_length_boundary(self):
        at_limit = parse_and_validate(f"REGION: {'r' * 64}\nTEXT: value\n")
        over_limit = parse_and_validate(f"REGION: {'r' * 65}\nTEXT: value\n")
        self.assertEqual(at_limit.verdict, "ok")
        self.assertEqual(over_limit.verdict, "rejected")
        self.assertEqual(over_limit.reason, "region_too_long")

    def test_non_string_output_is_protocol_violation(self):
        for raw in (1, [], {}, b"REGION: editor"):
            with self.subTest(raw=raw):
                try:
                    verdict = parse_and_validate(raw)
                except Exception as exc:  # pragma: no cover - RED witness guard
                    self.fail(f"validator raised instead of rejecting: {exc!r}")
                self.assertEqual(verdict.verdict, "rejected")
                self.assertEqual(verdict.reason, "protocol_violation")

    def test_repeated_coarse_region_labels_are_allowed(self):
        raw = "REGION: titlebar\nTEXT: [UNREADABLE]\nREGION: TITLEBAR\nTEXT: Settings\n"
        verdict = parse_and_validate(raw)
        self.assertEqual(verdict.verdict, "ok")
        self.assertEqual(len(verdict.fields), 2)

    def test_abstention_marker_near_misses_are_rejected(self):
        for body in (
            '"[UNREADABLE]"',
            "[UNREADABLE].",
            "[UNREADABLE ]",
            "UNREADABLE",
        ):
            with self.subTest(body=body):
                verdict = parse_and_validate(f"REGION: editor\nTEXT: {body}\n")
                self.assertEqual(verdict.verdict, "rejected")
                self.assertEqual(verdict.reason, "malformed_schema")

    def test_total_line_bound(self):
        raw = ("\n" * 97) + "REGION: editor\nTEXT: Settings\n"
        verdict = parse_and_validate(raw)
        self.assertEqual(verdict.verdict, "rejected")
        self.assertEqual(verdict.reason, "line_limit_exceeded")

    def test_total_raw_bound(self):
        verdict = parse_and_validate(" " * 70_001)
        self.assertEqual(verdict.verdict, "rejected")
        self.assertEqual(verdict.reason, "raw_limit_exceeded")

    def test_verdict_support_is_schema_only(self):
        for raw in (
            "REGION: titlebar\nTEXT: Settings\n",
            "NO_TEXT_VISIBLE",
            "",
        ):
            with self.subTest(raw=raw):
                self.assertEqual(getattr(parse_and_validate(raw), "support", None), "schema_only")

    def test_schema_valid_output_passes(self):
        raw = (
            "REGION: titlebar\nTEXT: plan.md — Visual Studio Code\n"
            "REGION: terminal\nTEXT: [UNREADABLE]\n"
        )
        v = parse_and_validate(raw)
        self.assertEqual(v.verdict, "ok")
        self.assertEqual(len(v.fields), 2)
        self.assertEqual(v.fields[0].provenance, "transcribed")
        self.assertEqual(v.fields[1].provenance, "abstained")

    def test_partial_evidence_stays_partial(self):
        raw = "REGION: editor\nTEXT: Settings [UNREADABLE]\n"
        v = parse_and_validate(raw)
        self.assertEqual(v.verdict, "ok")
        self.assertEqual(v.fields[0].provenance, "partial")

    def test_non_latin_partial_evidence_stays_partial(self):
        raw = "REGION: editor\nTEXT: 设置 [UNREADABLE]\n"
        v = parse_and_validate(raw)
        self.assertEqual(v.verdict, "ok")
        self.assertEqual(v.fields[0].provenance, "partial")

    def test_unreadable_field_abstains(self):
        raw = "REGION: editor\nTEXT: [UNREADABLE]\n"
        v = parse_and_validate(raw)
        self.assertEqual(v.verdict, "ok")
        self.assertEqual(v.fields[0].provenance, "abstained")

    def test_no_text_visible_is_honest_empty(self):
        v = parse_and_validate("NO_TEXT_VISIBLE")
        self.assertEqual(v.verdict, "empty")
        self.assertEqual(v.reason, "no_text_visible")
        self.assertEqual(v.fields, ())
        self.assertEqual(v.support, "schema_only")

    def test_empty_output_is_protocol_violation(self):
        v = parse_and_validate("")
        self.assertEqual(v.verdict, "rejected")
        self.assertEqual(v.reason, "protocol_violation")
        self.assertEqual(v.fields, ())

    def test_empty_text_field_is_malformed(self):
        v = parse_and_validate("REGION: editor\nTEXT:\n")
        self.assertEqual(v.verdict, "rejected")
        self.assertEqual(v.reason, "malformed_schema")

    def test_specificity_in_region_label_is_rejected(self):
        v = parse_and_validate("REGION: main.py\nTEXT: [UNREADABLE]\n")
        self.assertEqual(v.verdict, "rejected")
        self.assertEqual(v.reason, "unstructured_specificity")

    def test_region_specificity_detection_is_case_insensitive(self):
        v = parse_and_validate("REGION: Git PUSH\nTEXT: [UNREADABLE]\n")
        self.assertEqual(v.verdict, "rejected")
        self.assertEqual(v.reason, "unstructured_specificity")

    def test_invalid_region_label_is_rejected(self):
        v = parse_and_validate("REGION: title/bar\nTEXT: [UNREADABLE]\n")
        self.assertEqual(v.verdict, "rejected")
        self.assertEqual(v.reason, "invalid_region")

    def test_overlong_region_label_is_rejected(self):
        v = parse_and_validate(f"REGION: {'r' * 65}\nTEXT: [UNREADABLE]\n")
        self.assertEqual(v.verdict, "rejected")
        self.assertEqual(v.reason, "region_too_long")

    def test_unstructured_specificity_fails_closed(self):
        # Free prose asserting filenames/commands OUTSIDE the schema is the
        # confabulation signature — rejected wholesale, never salvaged.
        raw = "The owner is editing main.py and running git push origin main."
        v = parse_and_validate(raw)
        self.assertEqual(v.verdict, "rejected")
        self.assertEqual(v.reason, "unstructured_specificity")
        self.assertEqual(v.fields, ())

    def test_malformed_provenance_rejected(self):
        raw = "TEXT: orphan line with no region\n"
        v = parse_and_validate(raw)
        self.assertEqual(v.verdict, "rejected")
        self.assertEqual(v.reason, "malformed_schema")

    def test_contradictory_provenance_rejected(self):
        raw = "NO_TEXT_VISIBLE\nREGION: dock\nTEXT: Firefox\n"
        v = parse_and_validate(raw)
        self.assertEqual(v.verdict, "rejected")
        self.assertEqual(v.reason, "contradictory_provenance")


class ProductionCallerTests(unittest.TestCase):
    def test_schema_only_transcript_is_withheld_independent_of_privacy_state(self):
        from core.vision_contract.truth_contract import Field
        from skills.screen_perception import ScreenObservation

        marker = "SECRET_TRANSCRIPT"
        for support_fields in (
            {"contract_support": "schema_only"},
            {"validation": "schema_only"},
        ):
            with self.subTest(support_fields=support_fields):
                obs = ScreenObservation(
                    activity="unknown",
                    application="unknown",
                    detail=f"editor [transcribed]: {marker}",
                    focus_level="unknown",
                    raw_response=f"REGION: editor\nTEXT: {marker}",
                    timestamp=0.0,
                    success=True,
                    state="ok",
                    transcript_fields=(Field("editor", marker, "transcribed"),),
                    third_party_content_state="not_indicated",
                    **support_fields,
                )

                self.assertNotIn(marker, obs.format_for_context())
                self.assertIn("sensor admission", obs.format_for_context().lower())
                self.assertNotIn(marker, obs.format_for_memory())
                self.assertIn("sensor admission", obs.format_for_memory().lower())

    def test_fast_prompt_refuses_schema_only_screen_transcript(self):
        from core.infra.fast_prompt_builder import _format_screen
        from core.memory.perception_envelope import EnvelopeSource
        from skills.screen_perception import ScreenObservation

        marker = "SECRET_TRANSCRIPT"
        obs = ScreenObservation(
            activity="unknown",
            application="unknown",
            detail=marker,
            focus_level="unknown",
            raw_response=marker,
            timestamp=0.0,
            success=True,
            state="ok",
            contract_support="schema_only",
        )
        source = EnvelopeSource(
            name="screen",
            has_value=True,
            value=obs,
            age_ms=10,
            freshness_state="fresh",
            error=None,
            version=1,
        )

        rendered = _format_screen(source)
        self.assertIsNone(rendered)

    def test_fast_prompt_preserves_non_schema_screen_shape(self):
        from core.infra.fast_prompt_builder import _format_screen
        from core.memory.perception_envelope import EnvelopeSource
        from skills.screen_perception import ScreenObservation

        obs = ScreenObservation(
            activity="coding",
            application="code",
            detail="editing plan.md",
            focus_level="deep_work",
            raw_response="legacy",
            timestamp=0.0,
            success=True,
            state="ok",
        )
        source = EnvelopeSource(
            name="screen",
            has_value=True,
            value=obs,
            age_ms=10,
            freshness_state="fresh",
            error=None,
            version=1,
        )

        self.assertEqual(
            _format_screen(source),
            "  screen        [FRESH 0s ago] "
            "app=code | focus=deep_work | activity=coding | detail=editing plan.md",
        )

    def test_schema_only_screen_is_not_admitted_to_daemon_consumers(self):
        from daemon.maez_daemon import (
            _cycle_salient_perception_state,
            _cycle_signal_availability_key,
            _screen_observation_is_admitted,
        )

        obs = mock.Mock(
            success=True,
            state="ok",
            activity="SECRET_ACTIVITY",
            application="SECRET_APPLICATION",
            focus_level="SECRET_FOCUS",
            contract_support="schema_only",
            validation="schema_only",
        )
        camera = mock.Mock(sensor_state="unavailable")

        self.assertFalse(_screen_observation_is_admitted(obs))
        availability = _cycle_signal_availability_key(
            screen_obs=obs,
            camera_state=camera,
        )
        self.assertEqual(availability, "screen=absent|camera=absent")
        salient = _cycle_salient_perception_state(
            screen_obs=obs,
            signal_availability_key=availability,
        )
        baseline = _cycle_salient_perception_state(
            screen_obs=None,
            signal_availability_key=availability,
        )
        self.assertEqual(salient, baseline)
        self.assertFalse(salient["screen_success"])
        self.assertEqual(salient["screen_activity"], "unknown")
        self.assertEqual(salient["screen_application"], "unknown")
        self.assertEqual(salient["screen_focus_level"], "unknown")

    def test_schema_only_screen_cannot_shape_daemon_cycle_reasoning(self):
        import contextlib
        from types import SimpleNamespace

        from daemon.maez_daemon import MaezDaemon

        marker = "SECRET_SCHEMA_ONLY_TRANSCRIPT"

        class Memory:
            def __init__(self):
                self.queries = []

            def recall_for_cycle(self, query):
                self.queries.append(query)
                return {"core": [], "daily": [], "raw": []}

            def format_for_prompt(self, recalled, max_chars=None):
                return ""

            def memory_stats(self):
                return {"raw": 0, "daily": 0, "core": 0}

        screen = SimpleNamespace(
            state="ok",
            success=True,
            activity=marker,
            application=marker,
            detail=marker,
            focus_level=marker,
            contract_support="schema_only",
            validation="schema_only",
            format_for_context=mock.Mock(return_value=marker),
        )
        daemon = object.__new__(MaezDaemon)
        daemon.cycle_count = 1
        daemon.system_prompt = "SOUL"
        daemon.memory = Memory()
        daemon._cycle_recall_context = {}
        daemon._last_screen_obs = screen
        daemon._last_git_context = ""
        daemon._github_legacy_enabled = False
        daemon._last_github_block = None
        daemon._last_reddit_block = ""
        daemon._last_public_context = ""
        daemon._proactive_search_context = ""
        daemon._continuity_active = False
        daemon._continuity_capsule = None
        daemon._builder_audit_log = None
        daemon._builder_hwm = None
        daemon._builder_hwm_file = None
        daemon._cycle_feed_time_sense_line = lambda: ""
        daemon._s1b_note_residue_event = lambda *_args, **_kwargs: None

        snap = {
            "timestamp": "2026-07-09T00:00:00Z",
            "day_of_week": "Thursday",
            "time_of_day": "afternoon",
            "cpu": {"percent": 1.0, "core_count": 8, "freq_mhz": 3200},
            "ram": {"used_gb": 1.0, "total_gb": 16.0, "percent": 6.0},
            "gpu": None,
            "disk": {},
            "network": {"send_rate_mbps": 0.0, "recv_rate_mbps": 0.0},
            "top_processes_cpu": [],
            "top_processes_mem": [],
        }
        captured = {}

        @contextlib.contextmanager
        def purpose(_name):
            yield

        def build_envelope(**kwargs):
            captured["envelope"] = kwargs
            return None

        def chat(*, model, messages, think, options):
            captured["messages"] = messages
            return SimpleNamespace(message=SimpleNamespace(content="HEARTBEAT_OK"))

        with (
            mock.patch("daemon.maez_daemon._crc_capture", lambda *_args, **_kwargs: None),
            mock.patch("daemon.maez_daemon._cycle_focused_enabled", return_value=False),
            mock.patch(
                "core.cognition.envelope_builder.build_envelope",
                side_effect=build_envelope,
            ),
            mock.patch(
                "core.cognition.envelope_builder.render_envelope_for_prompt",
                return_value="",
            ),
            mock.patch("core.routing.brain_gateway.with_purpose", purpose),
            mock.patch("core.llm_client.chat", side_effect=chat),
        ):
            result = daemon._reason(snap)

        self.assertEqual(result, "HEARTBEAT_OK")
        self.assertNotIn(marker, daemon.memory.queries[0])
        self.assertNotIn(marker, captured["messages"][1]["content"])
        screen.format_for_context.assert_not_called()
        self.assertNotIn("screen observation — live", captured["envelope"]["signals_present"])
        self.assertIn(
            "screen observation — UNAVAILABLE this cycle (vision source down or capture failed)",
            captured["envelope"]["signals_absent"],
        )

    def test_sensor_flag_accepts_only_explicit_truthy_values(self):
        import skills.screen_perception as sp

        for value in ("1", "true", "yes", "on", " True ", "ON"):
            with (
                self.subTest(value=value),
                mock.patch.dict(os.environ, {"MAEZ_SCREEN_PERCEPTION": value}),
            ):
                self.assertTrue(sp._is_enabled())
        for value in ("", "0", "false", "no", "off", "0  # comment", "garbage"):
            with (
                self.subTest(value=value),
                mock.patch.dict(os.environ, {"MAEZ_SCREEN_PERCEPTION": value}),
            ):
                self.assertFalse(sp._is_enabled())

    def test_daemon_screen_flag_accepts_only_explicit_truthy_values(self):
        from daemon.maez_daemon import _screen_perception_enabled

        for value in ("1", "true", "yes", "on", " True ", "ON"):
            with self.subTest(value=value):
                self.assertTrue(
                    _screen_perception_enabled(environ={"MAEZ_SCREEN_PERCEPTION": value})
                )
        for value in ("", "0", "false", "no", "off", "0  # comment", "garbage"):
            with self.subTest(value=value):
                self.assertFalse(
                    _screen_perception_enabled(environ={"MAEZ_SCREEN_PERCEPTION": value})
                )

    def test_observe_rejects_confabulated_prose(self):
        import skills.screen_perception as sp

        class Response:
            status_code = 200
            text = ""

            @staticmethod
            def json():
                return {
                    "choices": [
                        {
                            "message": {
                                "content": (
                                    "The owner is editing main.py and running git push origin main."
                                )
                            }
                        }
                    ]
                }

        with (
            mock.patch.dict(os.environ, {"MAEZ_SCREEN_PERCEPTION": "1"}),
            mock.patch.object(sp, "_is_paused", return_value=False),
            mock.patch.object(sp, "_is_excluded_active_window", return_value=False),
            mock.patch.object(sp, "_vision_endpoint_probe", return_value=True),
            mock.patch.object(sp, "_capture_screenshot", return_value="AAAA"),
            mock.patch.object(sp.requests, "post", return_value=Response()),
        ):
            obs = sp.observe()

        self.assertFalse(obs.success)
        self.assertEqual(obs.state, "rejected")
        self.assertEqual(obs.error, "unstructured_specificity")
        self.assertEqual(getattr(obs, "failure_reason_code", None), "unstructured_specificity")
        self.assertEqual(getattr(obs, "contract_support", None), "schema_only")
        self.assertEqual(
            getattr(obs, "contract_schema_version", None),
            "vision_truth_contract.v1",
        )

    def test_observe_carries_schema_valid_transcript_fields(self):
        import skills.screen_perception as sp

        class Response:
            status_code = 200
            text = ""

            @staticmethod
            def json():
                return {
                    "choices": [
                        {
                            "message": {
                                "content": (
                                    "REGION: titlebar\nTEXT: Settings\n"
                                    "REGION: dock\nTEXT: [UNREADABLE]\n"
                                )
                            }
                        }
                    ]
                }

        with (
            mock.patch.dict(os.environ, {"MAEZ_SCREEN_PERCEPTION": "1"}),
            mock.patch.object(sp, "_is_paused", return_value=False),
            mock.patch.object(sp, "_is_excluded_active_window", return_value=False),
            mock.patch.object(sp, "_vision_endpoint_probe", return_value=True),
            mock.patch.object(sp, "_capture_screenshot", return_value="AAAA"),
            mock.patch.object(sp.requests, "post", return_value=Response()) as post,
        ):
            obs = sp.observe()

        self.assertTrue(obs.success)
        self.assertEqual(obs.state, "ok")
        self.assertEqual(obs.activity, "unknown")
        self.assertEqual(obs.application, "unknown")
        self.assertEqual(obs.focus_level, "unknown")
        self.assertEqual(obs.validation, "schema_only")
        self.assertEqual(getattr(obs, "contract_support", None), "schema_only")
        self.assertEqual(
            getattr(obs, "contract_schema_version", None),
            "vision_truth_contract.v1",
        )
        self.assertTrue(hasattr(obs, "transcript_fields"))
        self.assertEqual(
            tuple((field.region, field.text, field.provenance) for field in obs.transcript_fields),
            (
                ("titlebar", "Settings", "transcribed"),
                ("dock", "[UNREADABLE]", "abstained"),
            ),
        )
        self.assertEqual(
            obs.detail,
            "titlebar [transcribed]: Settings\ndock [abstained]: [UNREADABLE]",
        )
        sent = post.call_args.kwargs["json"]
        self.assertEqual(sent["temperature"], 0)
        self.assertEqual(sent["messages"][0]["content"][0]["text"], TRANSCRIBE_PROMPT)

        self.assertNotIn("Settings", obs.format_for_context())
        self.assertIn("withheld", obs.format_for_context().lower())
        self.assertNotIn("Settings", obs.format_for_memory())
        self.assertIn("withheld", obs.format_for_memory().lower())
        from daemon.maez_daemon import _screen_perception_owner_fact

        with mock.patch.dict(os.environ, {"MAEZ_SCREEN_PERCEPTION": "1"}):
            block, receipt = _screen_perception_owner_fact(obs, now=obs.timestamp)
        self.assertNotIn("Settings", block)
        self.assertIn("no fresh screen glance", block.lower())
        self.assertIsNone(receipt)

    def test_observe_renders_no_text_visible_as_honest_empty(self):
        import skills.screen_perception as sp

        class Response:
            status_code = 200
            text = ""

            @staticmethod
            def json():
                return {"choices": [{"message": {"content": "NO_TEXT_VISIBLE"}}]}

        with (
            mock.patch.dict(os.environ, {"MAEZ_SCREEN_PERCEPTION": "1"}),
            mock.patch.object(sp, "_is_paused", return_value=False),
            mock.patch.object(sp, "_is_excluded_active_window", return_value=False),
            mock.patch.object(sp, "_vision_endpoint_probe", return_value=True),
            mock.patch.object(sp, "_capture_screenshot", return_value="AAAA"),
            mock.patch.object(sp.requests, "post", return_value=Response()),
        ):
            obs = sp.observe()

        self.assertFalse(obs.success)
        self.assertEqual(obs.state, "empty")
        self.assertEqual(getattr(obs, "failure_reason_code", None), "no_text_visible")
        self.assertNotIn("failed", obs.format_for_context().lower())
        self.assertIn("no visible text", obs.format_for_context().lower())

    def test_sensor_not_reenabled(self):
        import skills.screen_perception as sp

        with (
            mock.patch.dict(os.environ, {"MAEZ_SCREEN_PERCEPTION": "0"}),
            mock.patch.object(sp, "_is_paused", return_value=False),
            mock.patch.object(sp, "_is_excluded_active_window") as excluded,
            mock.patch.object(sp, "_vision_endpoint_probe") as probe,
            mock.patch.object(sp, "_capture_screenshot") as capture,
            mock.patch.object(sp.requests, "post") as post,
        ):
            obs = sp.observe()
        self.assertEqual(obs.state, "disabled")
        excluded.assert_not_called()
        probe.assert_not_called()
        capture.assert_not_called()
        post.assert_not_called()


if __name__ == "__main__":
    unittest.main()


class PromptParserAgreementTests(unittest.TestCase):
    """The prompt must not teach a shape its own parser refuses (2026-08-17).

    The first bake-off failed every candidate largely on format, and the
    cause was the prompt showing `REGION: [label]` while _REGION_LABEL_RE
    forbids brackets in a region. Existing prompt tests could not catch that:
    they assert loose substrings, and the request test compares the payload
    against the same constant it was built from, so any prompt regression
    stays green. These pin behaviour instead.
    """

    def test_every_line_of_the_prompts_worked_example_parses(self):
        """Whatever shape the prompt DEMONSTRATES must be admissible."""
        example: list[str] = []
        for line in TRANSCRIBE_PROMPT.splitlines():
            stripped = line.strip()
            if stripped.upper().startswith(("REGION:", "TEXT:")):
                example.append(stripped)
        self.assertGreaterEqual(
            len(example), 2, "the prompt must show a worked REGION/TEXT example"
        )
        verdict = parse_and_validate("\n".join(example))
        self.assertEqual(
            verdict.verdict,
            "ok",
            f"the prompt's own example is rejected as {verdict.reason}",
        )

    def test_prompt_shows_no_bracketed_region_placeholder(self):
        """A model copying a bracketed label is refused invalid_region."""
        for line in TRANSCRIBE_PROMPT.splitlines():
            stripped = line.strip()
            if stripped.upper().startswith("REGION:"):
                label = stripped.split(":", 1)[1].strip()
                self.assertNotIn("[", label, f"bracketed region placeholder: {stripped!r}")
                self.assertEqual(
                    parse_and_validate(f"REGION: {label}\nTEXT: x").verdict,
                    "ok",
                    f"prompt shows an inadmissible region label: {label!r}",
                )

    def test_prompt_forbids_the_three_observed_decorations(self):
        low = TRANSCRIBE_PROMPT.lower()
        self.assertIn("code fence", low)
        self.assertIn("preamble", low)
        self.assertTrue("bold" in low or "italic" in low or "markdown" in low)

    def test_prompt_keeps_the_nothing_visible_exception_consistent(self):
        """A 'must begin with REGION' rule must not contradict NO_TEXT_VISIBLE."""
        low = TRANSCRIBE_PROMPT.lower()
        self.assertIn("NO_TEXT_VISIBLE", TRANSCRIBE_PROMPT)
        if "must begin with region" in low or "must be the r of region" in low:
            self.assertIn(
                "exception",
                low,
                "a begin-with-REGION rule must name the NO_TEXT_VISIBLE exception",
            )
        self.assertEqual(parse_and_validate("NO_TEXT_VISIBLE").verdict, "empty")

    def test_prompt_never_forbids_brackets_the_parser_accepts_in_TEXT(self):
        """Brackets visibly on screen must stay verbatim, not be censored.

        Measured: `TEXT: Settings [menu]` parses ok, so a rule banning all
        brackets would instruct a model to ALTER real screen text.
        """
        self.assertEqual(
            parse_and_validate("REGION: editor\nTEXT: Settings [menu]").verdict, "ok"
        )
        low = TRANSCRIBE_PROMPT.lower()
        for overreach in (
            "only bracketed token allowed anywhere",
            "no brackets anywhere",
        ):
            self.assertNotIn(overreach, low)

    def test_prompt_keeps_verbatim_fidelity_in_words(self):
        self.assertIn("verbatim", TRANSCRIBE_PROMPT.lower())

    def test_request_budget_is_pinned_not_self_referential(self):
        """Pin the literal budget so a silent change fails here.

        Recorded reason: 500 is currently NARROWER than the parser it feeds
        (MAX_FIELDS=32 pairs), and the live caller runs on the ~60s daemon
        cycle against a 45s HTTP timeout while discarding finish_reason --
        so this number must never move without that being noticed.
        """
        req = build_transcribe_request(image_b64="AAAA", model="m")
        self.assertEqual(req["max_tokens"], 500)
        self.assertEqual(req["temperature"], 0)
