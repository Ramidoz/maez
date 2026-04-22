# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Tests for core.claude_tier — the thin client that maez modules use
to reach the subscription proxy. Tests are fully offline: the proxy's
HTTP is mocked via urllib.request.urlopen so no network, no subprocess,
no budget DB writes."""
from __future__ import annotations

import io
import json
import unittest
import urllib.error
from unittest import mock


def _make_response(body: dict, status: int = 200):
    """Build a urlopen() response stand-in."""
    raw = json.dumps(body).encode("utf-8")
    resp = mock.MagicMock()
    resp.status = status
    resp.read.return_value = raw
    resp.__enter__ = mock.MagicMock(return_value=resp)
    resp.__exit__ = mock.MagicMock(return_value=False)
    return resp


def _make_http_error(code: int, detail: str):
    """Build an HTTPError stand-in with a JSON detail body."""
    body = json.dumps({"detail": detail}).encode("utf-8")
    err = urllib.error.HTTPError(
        url="x", code=code, msg="err", hdrs=None,
        fp=io.BytesIO(body),
    )
    return err


class HappyPath(unittest.TestCase):
    def test_successful_call_returns_tierreply(self):
        from core import claude_tier
        response = _make_response({
            "id": "x", "model": "claude-sonnet-4-6",
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": "hi there"},
                "finish_reason": "stop",
            }],
            "usage": {"prompt_tokens": 3, "completion_tokens": 5},
        })
        with mock.patch("urllib.request.urlopen", return_value=response):
            r = claude_tier.call(
                prompt="hello", model="sonnet", caller="test",
            )
        self.assertEqual(r.reply, "hi there")
        self.assertEqual(r.model_used, "claude-sonnet-4-6")
        self.assertEqual(r.input_tokens, 3)
        self.assertEqual(r.output_tokens, 5)
        self.assertIsInstance(r.raw, dict)

    def test_is_online_true_on_200(self):
        from core import claude_tier
        response = _make_response({"status": "ok"})
        with mock.patch("urllib.request.urlopen", return_value=response):
            self.assertTrue(claude_tier.is_online())


class FailureModes(unittest.TestCase):
    def test_empty_prompt_raises_badrequest_before_http(self):
        from core import claude_tier
        with self.assertRaises(claude_tier.ClaudeTierBadRequest):
            claude_tier.call(prompt="", caller="test")

    def test_connection_refused_raises_unavailable(self):
        from core import claude_tier
        with mock.patch("urllib.request.urlopen",
                        side_effect=urllib.error.URLError("refused")):
            with self.assertRaises(claude_tier.ClaudeTierUnavailable):
                claude_tier.call(prompt="hi", caller="test")

    def test_400_raises_badrequest(self):
        from core import claude_tier
        with mock.patch(
            "urllib.request.urlopen",
            side_effect=_make_http_error(400, "no messages"),
        ):
            with self.assertRaises(claude_tier.ClaudeTierBadRequest):
                claude_tier.call(prompt="x", caller="test")

    def test_429_raises_capped_with_kind(self):
        from core import claude_tier
        with mock.patch(
            "urllib.request.urlopen",
            side_effect=_make_http_error(
                429, "claude: hourly cap reached (10/10)",
            ),
        ):
            with self.assertRaises(claude_tier.ClaudeTierCapped) as cm:
                claude_tier.call(prompt="x", caller="test")
            self.assertEqual(cm.exception.cap_kind, "hourly")

    def test_429_daily_cap_detected(self):
        from core import claude_tier
        with mock.patch(
            "urllib.request.urlopen",
            side_effect=_make_http_error(
                429, "claude: daily cap reached (30/30)",
            ),
        ):
            with self.assertRaises(claude_tier.ClaudeTierCapped) as cm:
                claude_tier.call(prompt="x", caller="test")
            self.assertEqual(cm.exception.cap_kind, "daily")

    def test_502_raises_adapter_error(self):
        from core import claude_tier
        with mock.patch(
            "urllib.request.urlopen",
            side_effect=_make_http_error(502, "claude timed out"),
        ):
            with self.assertRaises(claude_tier.ClaudeTierAdapterError):
                claude_tier.call(prompt="x", caller="test")

    def test_is_online_false_on_unreachable(self):
        from core import claude_tier
        with mock.patch("urllib.request.urlopen",
                        side_effect=urllib.error.URLError("refused")):
            self.assertFalse(claude_tier.is_online())


class CanAfford(unittest.TestCase):
    def test_returns_true_when_remaining_meets_need(self):
        from core import claude_tier
        response = _make_response({
            "claude": {
                "hourly_remaining": 5, "daily_remaining": 20,
                "hourly_used": 5, "daily_used": 10,
                "hourly_cap": 10, "daily_cap": 30,
            },
        })
        with mock.patch("urllib.request.urlopen", return_value=response):
            self.assertTrue(claude_tier.can_afford("claude", needed_calls=3))
            self.assertFalse(claude_tier.can_afford("claude", needed_calls=6))

    def test_fail_closed_when_proxy_down(self):
        from core import claude_tier
        with mock.patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("refused"),
        ):
            self.assertFalse(claude_tier.can_afford("claude"))

    def test_unknown_adapter_cannot_afford(self):
        from core import claude_tier
        response = _make_response({
            "claude": {"hourly_remaining": 10, "daily_remaining": 20,
                        "hourly_used": 0, "daily_used": 0,
                        "hourly_cap": 10, "daily_cap": 30},
        })
        with mock.patch("urllib.request.urlopen", return_value=response):
            self.assertFalse(claude_tier.can_afford("nonexistent"))


class CallerHeader(unittest.TestCase):
    """The caller label flows into the X-Maez-Caller header. Essential
    for the trajectory log to be sliceable per consumer."""

    def test_caller_header_is_sent(self):
        from core import claude_tier
        response = _make_response({
            "choices": [{
                "message": {"role": "assistant", "content": "ok"},
                "finish_reason": "stop", "index": 0,
            }],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            "model": "sonnet",
        })

        captured = {}

        def _capture(req, timeout):
            captured["caller"] = req.headers.get("X-maez-caller")
            captured["url"] = req.full_url
            captured["method"] = req.get_method()
            return response

        with mock.patch("urllib.request.urlopen", side_effect=_capture):
            claude_tier.call(
                prompt="hi", caller="dream_eval/self_critique",
            )
        self.assertEqual(captured["caller"], "dream_eval/self_critique")
        self.assertEqual(captured["method"], "POST")
        self.assertIn("/v1/chat/completions", captured["url"])


if __name__ == "__main__":
    unittest.main()
