# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Slice 3.0d cap + telemetry contract tests for BoundedEnvelopeBuilder.

Locks the ratified docs/slices/legacy/3-0d-token-budget.md as executable
contract:

  §1   3K-token total cap → 12K-char enforcement (chars_per_token=4)
  §2   Per-section caps (tool_results 8x200, claimable 15x100,
       forbidden 8x80, self_history 5x200, signals 12x30 each)
  §3   Truncation order: tool_result body → claimable → self_history,
       preserving forbidden + signals
  §3a  Minimal-envelope fallback when steps 1-5 still over cap
  §4   maez.envelope WARNING log per truncation event with full
       required field set
  §6   Class-level MAX_* constants; envelope_chars_final stamped
  §7   MAEZ_EVIDENCE_ENVELOPE_BUDGET_TOKENS override and
       MAEZ_EVIDENCE_ENVELOPE_DISABLED bypass
"""
from __future__ import annotations

import logging
import os
import unittest
from unittest.mock import patch

os.environ["MAEZ_TEST_MODE"] = "1"

from core.cognition import envelope_builder as eb  # noqa: E402
from core.ledger import envelope_schema  # noqa: E402


class _LogCapture(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record):
        self.records.append(record)


def _build(**kwargs):
    """Construct a builder, drive it once, return (envelope, logs)."""
    cap = _LogCapture()
    cap.setLevel(logging.DEBUG)
    log = logging.getLogger("maez.envelope")
    log.addHandler(cap)
    log.setLevel(logging.DEBUG)
    try:
        builder = eb.BoundedEnvelopeBuilder()
        env = builder.build(**kwargs)
    finally:
        log.removeHandler(cap)
    return env, cap.records


class ClassConstantsTests(unittest.TestCase):
    """§6: Class-level MAX_* constants must be defined and match §2."""

    def test_max_constants_match_memo(self):
        cls = eb.BoundedEnvelopeBuilder
        self.assertEqual(cls.MAX_TOOL_RESULTS, 8)
        self.assertEqual(cls.MAX_TOOL_RESULT_SUMMARY_CHARS, 200)
        self.assertEqual(cls.MAX_CLAIMABLE, 15)
        self.assertEqual(cls.MAX_CLAIMABLE_ENTRY_CHARS, 100)
        self.assertEqual(cls.MAX_FORBIDDEN, 8)
        self.assertEqual(cls.MAX_FORBIDDEN_ENTRY_CHARS, 80)
        self.assertEqual(cls.MAX_SELF_HISTORY, 5)
        self.assertEqual(cls.MAX_SELF_HISTORY_SUMMARY_CHARS, 200)
        self.assertEqual(cls.MAX_SIGNALS, 12)
        self.assertEqual(cls.MAX_SIGNAL_ENTRY_CHARS, 30)

    def test_fallback_constants_match_memo(self):
        cls = eb.BoundedEnvelopeBuilder
        self.assertEqual(cls.MAX_FALLBACK_TOOLS, 8)
        self.assertEqual(cls.MAX_FALLBACK_FORBIDDEN, 8)
        self.assertEqual(cls.MAX_FALLBACK_SIGNALS_CHARS, 480)

    def test_chars_per_token_is_four(self):
        # §7 conversion rule: 4 chars/token, default 3000 tokens.
        self.assertEqual(eb.BoundedEnvelopeBuilder.CHARS_PER_TOKEN, 4)
        self.assertEqual(eb.BoundedEnvelopeBuilder.DEFAULT_TOKEN_CAP, 3000)


class EnvelopeFinalCharsStampedTests(unittest.TestCase):
    def test_envelope_chars_final_present(self):
        env, _ = _build(
            ledger_db_path=None,
            signals_present=["a"], signals_absent=[],
            tool_results=[],
        )
        self.assertIn("envelope_chars_final", env)
        self.assertIsInstance(env["envelope_chars_final"], int)
        self.assertGreater(env["envelope_chars_final"], 0)


class PerSectionCapsTests(unittest.TestCase):
    def test_tool_results_capped_at_max_entries(self):
        many = [{"name": f"t{i}", "status": "ok",
                 "summary": f"output {i}"} for i in range(20)]
        env, logs = _build(
            ledger_db_path=None,
            signals_present=[], signals_absent=[],
            tool_results=many,
        )
        self.assertEqual(len(env["tool_results"]),
                         eb.BoundedEnvelopeBuilder.MAX_TOOL_RESULTS)
        self.assertTrue(any(
            r.levelno == logging.WARNING and "tool_results" in r.getMessage()
            for r in logs
        ))

    def test_tool_result_summary_truncated_per_entry(self):
        long_summary = "x" * 800
        env, _ = _build(
            ledger_db_path=None,
            signals_present=[], signals_absent=[],
            tool_results=[{"name": "fetch", "status": "ok",
                           "summary": long_summary}],
        )
        s = env["tool_results"][0]["summary"]
        self.assertLessEqual(
            len(s),
            eb.BoundedEnvelopeBuilder.MAX_TOOL_RESULT_SUMMARY_CHARS,
        )
        # Status and name preserved per §5.
        self.assertEqual(env["tool_results"][0]["name"], "fetch")
        self.assertEqual(env["tool_results"][0]["status"], "ok")

    def test_claimable_drops_oldest_first(self):
        many = [{"text": f"c{i}"} for i in range(20)]
        env, _ = _build(
            ledger_db_path=None,
            signals_present=[], signals_absent=[],
            tool_results=[], claimable=many,
        )
        self.assertEqual(len(env["claimable"]),
                         eb.BoundedEnvelopeBuilder.MAX_CLAIMABLE)
        # §3.2 — keep most recent. With "oldest first" in input list,
        # newest are at the END; survivors must include the tail.
        kept_texts = {c["text"] for c in env["claimable"]}
        self.assertIn("c19", kept_texts)
        self.assertNotIn("c0", kept_texts)

    def test_forbidden_capped_at_max(self):
        many = [{"topic": f"f{i}", "reason": "x"} for i in range(15)]
        env, _ = _build(
            ledger_db_path=None,
            signals_present=[], signals_absent=[],
            tool_results=[], forbidden=many,
        )
        self.assertEqual(len(env["forbidden"]),
                         eb.BoundedEnvelopeBuilder.MAX_FORBIDDEN)

    def test_signals_capped_at_12_each(self):
        many = [f"sig_{i}" for i in range(20)]
        env, _ = _build(
            ledger_db_path=None,
            signals_present=many, signals_absent=many,
            tool_results=[],
        )
        self.assertLessEqual(
            len(env["signals_present"]),
            eb.BoundedEnvelopeBuilder.MAX_SIGNALS,
        )
        self.assertLessEqual(
            len(env["signals_absent"]),
            eb.BoundedEnvelopeBuilder.MAX_SIGNALS,
        )

    def test_signal_entry_truncated_at_30_chars(self):
        env, _ = _build(
            ledger_db_path=None,
            signals_present=["x" * 100], signals_absent=[],
            tool_results=[],
        )
        self.assertLessEqual(
            len(env["signals_present"][0]),
            eb.BoundedEnvelopeBuilder.MAX_SIGNAL_ENTRY_CHARS,
        )


class TotalCapTruncationOrderTests(unittest.TestCase):
    """§3 truncation order: bulk first (tool_result bodies, claimable,
    self_history) before signal (forbidden, signals)."""

    def test_tool_result_bodies_truncated_first(self):
        # Setup so that step-1 (zero tool_result bodies) is sufficient
        # to bring the envelope under cap — verifies forbidden+signals
        # are preserved untouched at §3.4-5.
        env, logs = _build(
            ledger_db_path=None,
            # Unique strings — repeats would dedup to a single entry.
            signals_present=["sigA", "sigB", "sigC"],
            signals_absent=["absA", "absB", "absC"],
            tool_results=[
                {"name": f"t{i}", "status": "ok", "summary": "x" * 200}
                for i in range(5)
            ],
            forbidden=[{"topic": f"f{i}", "reason": "z"}
                       for i in range(3)],
            char_cap=600,
        )
        # Forbidden + signals MUST be preserved per §3.4-5.
        self.assertEqual(len(env["forbidden"]), 3)
        self.assertEqual(len(env["signals_present"]), 3)
        self.assertEqual(len(env["signals_absent"]), 3)
        # tool_result summaries fully stripped at step 1.
        total_summary_chars = sum(
            len(t.get("summary", "")) for t in env["tool_results"]
        )
        self.assertEqual(total_summary_chars, 0)
        # tool_results entries themselves preserved (name+status).
        self.assertEqual(len(env["tool_results"]), 5)


class MinimalFallbackTests(unittest.TestCase):
    """§3a: when steps 1-5 still leave the envelope over cap, a minimal
    envelope is emitted with _truncated=true and floor caps."""

    def test_minimal_fallback_triggered_under_extreme_pressure(self):
        # Use UNIQUE signals (dedup would collapse repeats), and load
        # forbidden + signals up to per-section caps. With those
        # caps in place, normal §3 truncation drops bulk only — but
        # forbidden+signals remain. With a tight char_cap below
        # forbidden+signals weight, minimal fallback must fire.
        env, logs = _build(
            ledger_db_path=None,
            signals_present=[f"sp_{i}" for i in range(20)],
            signals_absent=[f"sa_{i}" for i in range(20)],
            tool_results=[],
            forbidden=[
                {"topic": f"forbidden_topic_{i}",
                 "reason": "very long forbidden reason text " * 2}
                for i in range(20)
            ],
            char_cap=400,
        )
        self.assertIs(env.get("_truncated"), True)
        self.assertIn("_truncation_reason", env)
        self.assertLessEqual(
            len(env["forbidden"]),
            eb.BoundedEnvelopeBuilder.MAX_FALLBACK_FORBIDDEN,
        )
        # signals_present + signals_absent total chars under floor cap.
        sigs_chars = (
            sum(len(s) for s in env.get("signals_present", []))
            + sum(len(s) for s in env.get("signals_absent", []))
        )
        self.assertLessEqual(
            sigs_chars,
            eb.BoundedEnvelopeBuilder.MAX_FALLBACK_SIGNALS_CHARS,
        )
        # Telemetry must mark this with truncation_kind=minimal_fallback.
        self.assertTrue(
            any(getattr(r, "truncation_kind", None) == "minimal_fallback"
                for r in logs),
            "expected truncation_kind=minimal_fallback in maez.envelope logs",
        )


class TelemetryFieldsTests(unittest.TestCase):
    """§4: every truncation log must carry the full required field
    set."""

    REQUIRED = {
        "section", "truncation_kind", "dropped_entries", "dropped_chars",
        "envelope_chars_before", "envelope_chars_after",
        "envelope_tokens_estimated_before", "envelope_tokens_estimated_after",
        "char_cap", "token_cap", "cap_hit",
    }

    def test_per_section_cap_log_carries_all_fields(self):
        env, logs = _build(
            ledger_db_path=None,
            signals_present=[], signals_absent=[],
            tool_results=[
                {"name": f"t{i}", "status": "ok", "summary": "x"}
                for i in range(20)
            ],
            turn_id="turn-test-001",
        )
        warnings = [r for r in logs if r.levelno >= logging.WARNING]
        self.assertGreater(len(warnings), 0)
        rec = warnings[0]
        for field in self.REQUIRED:
            self.assertTrue(
                hasattr(rec, field),
                f"telemetry record missing field {field!r}",
            )
        self.assertEqual(rec.turn_id, "turn-test-001")


class PerSectionTelemetryEnvelopeSizesTests(unittest.TestCase):
    """Reviewer-flagged: per-section truncation logs must carry REAL
    envelope_chars_before/after, not -1 sentinels. The before value
    is the envelope size if THIS section were uncapped (other sections
    at their capped size); the after value is the actual envelope size
    after the section cap. Difference must equal the bytes saved."""

    def test_per_section_log_has_real_envelope_sizes(self):
        env, logs = _build(
            ledger_db_path=None,
            signals_present=[], signals_absent=[],
            tool_results=[
                {"name": f"t{i}", "status": "ok",
                 "summary": "x" * 500}
                for i in range(20)
            ],
            turn_id="turn-real-001",
        )
        per_section = [
            r for r in logs
            if getattr(r, "truncation_kind", None) == "per_section_cap"
            and getattr(r, "section", None) == "tool_results"
        ]
        self.assertEqual(len(per_section), 1)
        rec = per_section[0]
        # Real values, not sentinels.
        self.assertGreater(rec.envelope_chars_before, 0)
        self.assertGreater(rec.envelope_chars_after, 0)
        # Capping reduced size.
        self.assertGreater(
            rec.envelope_chars_before, rec.envelope_chars_after,
        )
        # Token estimates derived from chars / 4.
        self.assertEqual(
            rec.envelope_tokens_estimated_before,
            rec.envelope_chars_before // 4,
        )
        self.assertEqual(
            rec.envelope_tokens_estimated_after,
            rec.envelope_chars_after // 4,
        )


class EnvVarTests(unittest.TestCase):
    def test_disabled_env_var_returns_none(self):
        # §7: "skip envelope construction entirely." None is the
        # contract — callers MUST then fall through to the legacy
        # signals_present/signals_absent path. Returning a degenerate
        # empty envelope would, under full-takeover semantics in
        # judge(), erase the caller's legacy signals — the opposite
        # of what an emergency bypass should do.
        with patch.dict(os.environ,
                        {"MAEZ_EVIDENCE_ENVELOPE_DISABLED": "1"}):
            env, _ = _build(
                ledger_db_path=None,
                signals_present=["x"], signals_absent=[],
                tool_results=[{"name": "y", "status": "ok",
                               "summary": "z"}],
            )
        self.assertIsNone(env)

    def test_token_budget_override(self):
        with patch.dict(
            os.environ,
            {"MAEZ_EVIDENCE_ENVELOPE_BUDGET_TOKENS": "100"},
        ):
            # 100 tokens × 4 = 400 chars. Lots of forbidden entries
            # overflow → minimal fallback.
            env, _ = _build(
                ledger_db_path=None,
                signals_present=[], signals_absent=[],
                tool_results=[],
                forbidden=[{"topic": f"f{i}", "reason": "rr"}
                           for i in range(50)],
            )
        # With a 400-char cap, the envelope must come in at-or-near it.
        self.assertLessEqual(env["envelope_chars_final"], 800)


class ExtremeCapHandlingTests(unittest.TestCase):
    """Edge cases on cap arithmetic. Reviewer-flagged: char_cap=0
    must not bypass the unrenderable path; dropped_chars must never
    go negative."""

    def test_zero_char_cap_emits_unrenderable_shape(self):
        env, logs = _build(
            ledger_db_path=None,
            signals_present=["x"], signals_absent=[],
            tool_results=[{"name": "t", "status": "ok",
                           "summary": "anything"}],
            char_cap=0,
        )
        # Unrenderable: every section empty, _truncated marker set.
        self.assertIs(env.get("_truncated"), True)
        self.assertEqual(env["tool_results"], [])
        self.assertEqual(env["forbidden"], [])
        self.assertEqual(env["signals_present"], [])
        self.assertEqual(env["signals_absent"], [])

    def test_dropped_chars_non_negative_in_telemetry(self):
        # Force minimal-fallback path; verify no telemetry record
        # carries a negative dropped_chars.
        env, logs = _build(
            ledger_db_path=None,
            signals_present=[f"sp_{i}" for i in range(20)],
            signals_absent=[],
            tool_results=[],
            forbidden=[
                {"topic": f"forbidden_topic_{i}",
                 "reason": "very long forbidden reason text " * 2}
                for i in range(20)
            ],
            char_cap=0,
        )
        # Only check truncation telemetry records (skip the ad-hoc
        # ERROR/WARN diagnostic lines that don't carry extra fields).
        truncation_records = [
            r for r in logs
            if getattr(r, "truncation_kind", None) is not None
        ]
        self.assertGreater(len(truncation_records), 0)
        for r in truncation_records:
            for field in ("dropped_chars",
                          "envelope_chars_before", "envelope_chars_after"):
                v = getattr(r, field)
                self.assertGreaterEqual(
                    v, 0,
                    f"telemetry field {field!r} negative ({v}) — "
                    "must be ≥ 0 (memo §4: real envelope sizes)",
                )


class EnvelopeCharsFinalIncludesStampTests(unittest.TestCase):
    """Reviewer-flagged: `envelope_chars_final` must equal the actual
    delivered JSON size, INCLUDING the stamp itself, per memo §6."""

    def test_chars_final_matches_serialized_size(self):
        env, _ = _build(
            ledger_db_path=None,
            signals_present=["sigA", "sigB"], signals_absent=["absA"],
            tool_results=[{"name": "ls", "status": "ok",
                           "summary": "three items"}],
            forbidden=[{"topic": "secret"}],
        )
        import json as _json
        actual = len(_json.dumps(env, sort_keys=True, ensure_ascii=False))
        self.assertEqual(
            env["envelope_chars_final"], actual,
            "envelope_chars_final must match full serialized size, "
            "including the stamp field itself",
        )


class ToolResultsShapeTests(unittest.TestCase):
    """§5 tool_results shape: name, status, tool_call_id, summary."""

    def test_memo_shape_passes_through(self):
        env, _ = _build(
            ledger_db_path=None,
            signals_present=[], signals_absent=[],
            tool_results=[{
                "name": "web_search",
                "status": "ok",
                "tool_call_id": "call-abc-123",
                "summary": "found 3 results",
            }],
        )
        tr = env["tool_results"][0]
        self.assertEqual(tr["name"], "web_search")
        self.assertEqual(tr["status"], "ok")
        self.assertEqual(tr["tool_call_id"], "call-abc-123")
        self.assertEqual(tr["summary"], "found 3 results")


class SchemaValidityTests(unittest.TestCase):
    def test_normal_envelope_schema_valid(self):
        env, _ = _build(
            ledger_db_path=None,
            signals_present=["a"], signals_absent=["b"],
            tool_results=[{"name": "t", "status": "ok", "summary": "s"}],
            claimable=[{"text": "c"}],
            forbidden=[{"topic": "f"}],
        )
        envelope_schema.validate_envelope(env)

    def test_minimal_fallback_envelope_schema_valid(self):
        env, _ = _build(
            ledger_db_path=None,
            signals_present=["x"] * 50, signals_absent=[],
            tool_results=[],
            forbidden=[{"topic": f"f{i}", "reason": "x"}
                       for i in range(200)],
            char_cap=400,
        )
        envelope_schema.validate_envelope(env)


class RecallCapResolverTests(unittest.TestCase):
    """SLICE_3_0d §1: recall cap reduces from 60K → 52K when an
    envelope will be present in the prompt. ``resolve_recall_cap_chars``
    is the single decision point so the daemon's recall builder and
    any future caller agree on the same number."""

    def test_default_is_52000(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("MAEZ_EVIDENCE_ENVELOPE_DISABLED", None)
            os.environ.pop("MAEZ_RECALL_CAP_WITH_ENVELOPE_CHARS", None)
            self.assertEqual(eb.resolve_recall_cap_chars(), 52_000)

    def test_disabled_mode_returns_60000_legacy(self):
        with patch.dict(os.environ,
                        {"MAEZ_EVIDENCE_ENVELOPE_DISABLED": "1"}):
            self.assertEqual(eb.resolve_recall_cap_chars(), 60_000)

    def test_env_override_honored(self):
        with patch.dict(
            os.environ,
            {"MAEZ_RECALL_CAP_WITH_ENVELOPE_CHARS": "12345"},
        ):
            os.environ.pop("MAEZ_EVIDENCE_ENVELOPE_DISABLED", None)
            self.assertEqual(eb.resolve_recall_cap_chars(), 12_345)

    def test_invalid_env_falls_back_to_default(self):
        with patch.dict(
            os.environ,
            {"MAEZ_RECALL_CAP_WITH_ENVELOPE_CHARS": "not-a-number"},
        ):
            os.environ.pop("MAEZ_EVIDENCE_ENVELOPE_DISABLED", None)
            self.assertEqual(eb.resolve_recall_cap_chars(), 52_000)


class ToolResultsCompressionRuleTests(unittest.TestCase):
    """SLICE_3_0d §5 compression rule: summary may be a string, dict,
    or list. Each gets a different compression treatment.

      - string: head-truncate to 200 chars + "…"
      - dict:   keep all keys, truncate each value past ~80 chars
      - list:   keep N=3 items, append "(+M more dropped)"
    """

    def test_dict_summary_keys_preserved_values_truncated(self):
        long_val = "y" * 200
        env, _ = _build(
            ledger_db_path=None,
            signals_present=[], signals_absent=[],
            tool_results=[{
                "name": "calendar",
                "status": "ok",
                "summary": {
                    "next": "Meeting at 3pm with Alice " + "x" * 200,
                    "after": long_val,
                    "free_until": "5pm",
                },
            }],
        )
        s = env["tool_results"][0]["summary"]
        # Keys all preserved.
        self.assertEqual(set(s.keys()), {"next", "after", "free_until"})
        # Each value bounded.
        for v in s.values():
            self.assertLessEqual(len(v), 80)
        # Short value pass-through unchanged.
        self.assertEqual(s["free_until"], "5pm")

    def test_list_summary_keeps_three_items_with_dropped_marker(self):
        env, _ = _build(
            ledger_db_path=None,
            signals_present=[], signals_absent=[],
            tool_results=[{
                "name": "web_search",
                "status": "ok",
                "summary": [
                    "result 1", "result 2", "result 3",
                    "result 4", "result 5", "result 6",
                    "result 7",
                ],
            }],
        )
        s = env["tool_results"][0]["summary"]
        self.assertIsInstance(s, list)
        # 3 items kept + 1 dropped marker.
        self.assertEqual(len(s), 4)
        self.assertEqual(s[:3], ["result 1", "result 2", "result 3"])
        self.assertIn("4", s[3])
        self.assertIn("more dropped", s[3])

    def test_list_summary_under_threshold_no_marker(self):
        env, _ = _build(
            ledger_db_path=None,
            signals_present=[], signals_absent=[],
            tool_results=[{
                "name": "web_search",
                "status": "ok",
                "summary": ["only one"],
            }],
        )
        s = env["tool_results"][0]["summary"]
        self.assertEqual(s, ["only one"])

    def test_string_summary_unchanged_for_short(self):
        env, _ = _build(
            ledger_db_path=None,
            signals_present=[], signals_absent=[],
            tool_results=[{"name": "n", "status": "ok",
                           "summary": "small text"}],
        )
        self.assertEqual(env["tool_results"][0]["summary"], "small text")


class SchemaMetadataTests(unittest.TestCase):
    """Per docs/ledger/envelope-schema.md §3.1, the envelope carries
    schema_version, built_at, and (when supplied) turn_id at the top
    level. Reviewer-flagged: the minimal fallback memo §3a explicitly
    requires schema_version on the truncated shape."""

    def test_normal_envelope_has_metadata(self):
        env, _ = _build(
            ledger_db_path=None,
            signals_present=[], signals_absent=[],
            tool_results=[],
            turn_id="turn-meta-001",
        )
        self.assertEqual(env["schema_version"], 1)
        self.assertIsInstance(env["built_at"], float)
        self.assertEqual(env["turn_id"], "turn-meta-001")

    def test_envelope_without_turn_id_omits_field(self):
        env, _ = _build(
            ledger_db_path=None,
            signals_present=[], signals_absent=[],
            tool_results=[],
        )
        # turn_id is optional; omit cleanly when not provided.
        self.assertNotIn("turn_id", env)
        self.assertIn("schema_version", env)
        self.assertIn("built_at", env)

    def test_minimal_fallback_envelope_has_schema_version(self):
        env, _ = _build(
            ledger_db_path=None,
            signals_present=[f"sp_{i}" for i in range(20)],
            signals_absent=[f"sa_{i}" for i in range(20)],
            tool_results=[],
            forbidden=[
                {"topic": f"forbidden_topic_{i}",
                 "reason": "very long forbidden reason text " * 2}
                for i in range(20)
            ],
            char_cap=400,
        )
        self.assertIs(env.get("_truncated"), True)
        self.assertEqual(env["schema_version"], 1)


if __name__ == "__main__":
    unittest.main()
