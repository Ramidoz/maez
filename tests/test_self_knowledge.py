# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Self-knowledge tests (Step 0 of the Decision-19/20 capability-
acquisition pipeline arc).

Maez has to know its own VRAM, context window, and loaded model
to evaluate capability candidates against its own constraints.
The pipeline's self-evaluator depends on this — without it,
"don't propose a 1T-parameter model into 24GB VRAM" can't fire.

All tests stub subprocess and urllib so they're hermetic — no
real GPU or llama-server required.
"""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


# ── nvidia-smi parsing ──────────────────────────────────────────────


class TestNvidiaSmiParsing(unittest.TestCase):
    def test_parses_total_and_available_from_query(self):
        from core.self_knowledge import _parse_nvidia_smi_query

        # Real nvidia-smi --query-gpu=name,memory.total,memory.free
        # output (CSV with units stripped).
        sample = "NVIDIA GeForce RTX 4090, 24564 MiB, 18432 MiB\n"
        parsed = _parse_nvidia_smi_query(sample)
        self.assertEqual(parsed["name"], "NVIDIA GeForce RTX 4090")
        self.assertEqual(parsed["total_mb"], 24564)
        self.assertEqual(parsed["available_mb"], 18432)

    def test_handles_units_with_no_space(self):
        from core.self_knowledge import _parse_nvidia_smi_query

        sample = "Tesla T4, 16384MiB, 14000MiB\n"
        parsed = _parse_nvidia_smi_query(sample)
        self.assertEqual(parsed["total_mb"], 16384)
        self.assertEqual(parsed["available_mb"], 14000)

    def test_returns_none_on_garbage(self):
        from core.self_knowledge import _parse_nvidia_smi_query

        self.assertIsNone(_parse_nvidia_smi_query(""))
        self.assertIsNone(_parse_nvidia_smi_query("not csv at all"))


# ── vram functions ─────────────────────────────────────────────────


class TestVramFunctions(unittest.TestCase):
    def test_vram_total_mb_via_mocked_subprocess(self):
        from core import self_knowledge

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "GeForce RTX 4090, 24564 MiB, 18432 MiB\n"
        with patch("subprocess.run", return_value=mock_result):
            self.assertEqual(self_knowledge.vram_total_mb(), 24564)

    def test_vram_available_mb_via_mocked_subprocess(self):
        from core import self_knowledge

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "GeForce RTX 4090, 24564 MiB, 18432 MiB\n"
        with patch("subprocess.run", return_value=mock_result):
            self.assertEqual(self_knowledge.vram_available_mb(), 18432)

    def test_vram_returns_none_when_nvidia_smi_missing(self):
        from core import self_knowledge

        with patch(
            "subprocess.run",
            side_effect=FileNotFoundError("no nvidia-smi"),
        ):
            self.assertIsNone(self_knowledge.vram_total_mb())
            self.assertIsNone(self_knowledge.vram_available_mb())

    def test_vram_returns_none_on_subprocess_error(self):
        from core import self_knowledge

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "no devices found"
        with patch("subprocess.run", return_value=mock_result):
            self.assertIsNone(self_knowledge.vram_total_mb())

    def test_vram_returns_none_on_timeout(self):
        from core import self_knowledge

        with patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="nvidia-smi", timeout=2),
        ):
            self.assertIsNone(self_knowledge.vram_total_mb())

    def test_gpu_name(self):
        from core import self_knowledge

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "GeForce RTX 4090, 24564 MiB, 18432 MiB\n"
        with patch("subprocess.run", return_value=mock_result):
            self.assertEqual(
                self_knowledge.gpu_name(), "GeForce RTX 4090",
            )


# ── llama-server self-knowledge ────────────────────────────────────


class TestLlamaServerSelfKnowledge(unittest.TestCase):
    def test_loaded_model_name_via_mocked_v1_models(self):
        from core import self_knowledge

        payload = {
            "models": [{"name": "qwen36-27b"}],
            "data": [{"id": "qwen36-27b"}],
        }
        with patch.object(
            self_knowledge, "_fetch_models_payload",
            return_value=payload,
        ):
            self.assertEqual(
                self_knowledge.loaded_model_name(), "qwen36-27b",
            )

    def test_current_context_window_from_meta(self):
        from core import self_knowledge

        payload = {
            "data": [{"id": "qwen36-27b", "meta": {"n_ctx_train": 262144}}],
        }
        with patch.object(
            self_knowledge, "_fetch_models_payload",
            return_value=payload,
        ):
            self.assertEqual(
                self_knowledge.current_context_window(), 262144,
            )

    def test_loaded_model_name_returns_none_when_server_unreachable(self):
        from core import self_knowledge

        with patch.object(
            self_knowledge, "_fetch_models_payload",
            return_value=None,
        ):
            self.assertIsNone(self_knowledge.loaded_model_name())

    def test_current_context_window_returns_none_on_missing_field(self):
        from core import self_knowledge

        # OpenAI-canonical shape with no meta block.
        payload = {"data": [{"id": "anonymous"}]}
        with patch.object(
            self_knowledge, "_fetch_models_payload",
            return_value=payload,
        ):
            self.assertIsNone(self_knowledge.current_context_window())

    def test_prefers_data_id_over_models_name(self):
        """OpenAI canonical (data[].id) wins. llama-server's legacy
        models[].name is the fallback."""
        from core import self_knowledge

        payload = {
            "data": [{"id": "openai-canonical"}],
            "models": [{"name": "legacy-name"}],
        }
        with patch.object(
            self_knowledge, "_fetch_models_payload",
            return_value=payload,
        ):
            self.assertEqual(
                self_knowledge.loaded_model_name(), "openai-canonical",
            )


# ── headroom helpers ───────────────────────────────────────────────


class TestHeadroom(unittest.TestCase):
    def test_can_load_model_with_size_below_available(self):
        from core import self_knowledge

        with patch.object(
            self_knowledge, "vram_available_mb", return_value=18432,
        ):
            self.assertTrue(self_knowledge.can_fit_in_vram_mb(16000))

    def test_cannot_load_model_with_size_above_available(self):
        from core import self_knowledge

        with patch.object(
            self_knowledge, "vram_available_mb", return_value=18432,
        ):
            self.assertFalse(self_knowledge.can_fit_in_vram_mb(20000))

    def test_can_fit_returns_false_when_vram_unknown(self):
        """Decision: if Maez can't read VRAM, don't claim it can
        fit anything. False is the safe answer; a candidate that
        won't fit is better deferred than accidentally proposed."""
        from core import self_knowledge

        with patch.object(
            self_knowledge, "vram_available_mb", return_value=None,
        ):
            self.assertFalse(self_knowledge.can_fit_in_vram_mb(1000))


# ── summarize ──────────────────────────────────────────────────────


class TestSummarize(unittest.TestCase):
    """summarize() shares a single nvidia-smi call and a single
    /v1/models fetch — direct composition of the public functions
    would multiply both (audit perf fix). Tests patch at the
    underlying probe functions accordingly."""

    def test_summary_shape(self):
        from core import self_knowledge

        nv = {
            "name": "RTX 4090",
            "total_mb": 24564,
            "available_mb": 18432,
        }
        payload = {
            "data": [{
                "id": "qwen36-27b",
                "meta": {"n_ctx_train": 262144},
            }],
        }
        with patch.object(
            self_knowledge, "_run_nvidia_smi", return_value=nv,
        ), patch.object(
            self_knowledge, "_fetch_models_payload", return_value=payload,
        ):
            s = self_knowledge.summarize()
        for key in (
            "vram_total_mb", "vram_available_mb", "gpu_name",
            "loaded_model_name", "current_context_window",
        ):
            self.assertIn(key, s)
        self.assertEqual(s["vram_total_mb"], 24564)
        self.assertEqual(s["loaded_model_name"], "qwen36-27b")
        self.assertEqual(s["current_context_window"], 262144)

    def test_summary_handles_missing_pieces(self):
        """When VRAM probe fails, summarize still returns a dict
        with None values rather than raising."""
        from core import self_knowledge

        with patch.object(
            self_knowledge, "_run_nvidia_smi", return_value=None,
        ), patch.object(
            self_knowledge, "_fetch_models_payload", return_value=None,
        ):
            s = self_knowledge.summarize()
        self.assertIsNone(s["vram_total_mb"])
        self.assertIsNone(s["loaded_model_name"])

    def test_summary_calls_each_probe_once(self):
        """Audit perf fix: summarize must NOT make three subprocess
        calls just because three pieces of nvidia-smi data are
        surfaced. Single call, fields plucked from the result."""
        from core import self_knowledge

        with patch.object(
            self_knowledge, "_run_nvidia_smi",
            return_value={
                "name": "x", "total_mb": 100, "available_mb": 50,
            },
        ) as mock_nv, patch.object(
            self_knowledge, "_fetch_models_payload",
            return_value={"data": [{"id": "m"}]},
        ) as mock_pl:
            self_knowledge.summarize()
        self.assertEqual(mock_nv.call_count, 1)
        self.assertEqual(mock_pl.call_count, 1)


class TestAuditFixPins(unittest.TestCase):
    """Pins for the inline audit fixes so they can't silently
    revert: comma-in-number robustness, multi-GPU first-only
    contract, empty data list, non-positive n_ctx_train, non-dict
    payload, model_config URL resolution."""

    def test_subprocess_called_with_c_locale_env(self):
        """Audit fix #1: nvidia-smi is invoked with LC_ALL=C / LANG=C
        so locale-driven thousands-separator (e.g. '24,564 MiB')
        cannot break CSV parsing. This is the load-bearing
        protection; the in-field comma strip is just a backstop."""
        from core import self_knowledge

        captured = {}

        def fake_run(*a, **kw):
            captured["env"] = kw.get("env")
            from unittest.mock import MagicMock
            r = MagicMock()
            r.returncode = 0
            r.stdout = "X, 1 MiB, 1 MiB\n"
            return r

        with patch("subprocess.run", side_effect=fake_run):
            self_knowledge.vram_total_mb()
        self.assertIsNotNone(captured["env"])
        self.assertEqual(captured["env"].get("LC_ALL"), "C")
        self.assertEqual(captured["env"].get("LANG"), "C")

    # Note: an "in-field comma strip" backstop test was considered
    # and dropped because the real protection against locale-leak
    # comma is LC_ALL=C at the subprocess boundary (test above);
    # CSV-split has already happened by the time _parse_nvidia_smi_query
    # sees the string, so a strip can't recover. The strip in
    # _mb() is harmless defensive code.

    def test_multi_gpu_first_only_documented_contract(self):
        from core.self_knowledge import _parse_nvidia_smi_query

        sample = (
            "GPU 0, 24564 MiB, 18432 MiB\n"
            "GPU 1, 16384 MiB, 14000 MiB\n"
        )
        parsed = _parse_nvidia_smi_query(sample)
        # Documented contract: first GPU only. Pin so a refactor
        # to multi-GPU surfacing has to update this test deliberately.
        self.assertEqual(parsed["name"], "GPU 0")

    def test_loaded_model_name_returns_none_on_empty_data(self):
        from core import self_knowledge

        with patch.object(
            self_knowledge, "_fetch_models_payload",
            return_value={"data": []},
        ):
            self.assertIsNone(self_knowledge.loaded_model_name())

    def test_current_context_window_rejects_zero_and_negative(self):
        from core import self_knowledge

        for bad in (0, -1, "262144"):  # str shape test included
            with patch.object(
                self_knowledge, "_fetch_models_payload",
                return_value={
                    "data": [{"id": "m", "meta": {"n_ctx_train": bad}}],
                },
            ):
                self.assertIsNone(
                    self_knowledge.current_context_window(),
                    f"failed to reject {bad!r}",
                )

    def test_loaded_model_name_handles_non_dict_payload(self):
        from core import self_knowledge

        # Server returns a JSON list instead of object — guard
        # against the edge.
        with patch.object(
            self_knowledge, "_fetch_models_payload",
            return_value=["unexpected", "shape"],
        ):
            self.assertIsNone(self_knowledge.loaded_model_name())

    def test_llama_models_url_resolves_via_model_config(self):
        """URL must be config-driven, not hardcoded. If
        PRIMARY_BASE_URL changes, _llama_models_url() reflects it."""
        from core.infra import self_knowledge as sk

        with patch(
            "core.routing.model_config.PRIMARY_BASE_URL",
            "http://example.test:9999",
        ):
            self.assertEqual(
                sk._llama_models_url(),
                "http://example.test:9999/v1/models",
            )


if __name__ == "__main__":
    unittest.main()
