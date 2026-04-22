# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Adapter: Claude Code CLI (Anthropic Max subscription).

Wraps `claude --print` as an async subprocess. Every call consumes one
message off the user's Claude Max quota, indistinguishable from typing
`claude` in a terminal. Subscription-backed, not API-key-backed.

Authentication: relies on `claude` having been authenticated interactively
(via `claude auth` or on first run). This adapter does NOT perform auth
itself — if the user is not logged in, calls fail loudly.

NOT using --bare: that flag forces Anthropic auth to API-key only and
bypasses OAuth/keychain, routing the call via the paid API instead of
the subscription. Verified 2026-04-22: `claude --bare ...` returns
"Not logged in · Please run /login" even with valid subscription auth.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
from typing import Optional

from core.subscription_proxy.adapters.base import Adapter, CallResult

logger = logging.getLogger("maez.subscription_proxy.claude")

CLAUDE_BIN = os.environ.get(
    "MAEZ_CLAUDE_BIN", "/home/rohit/.local/bin/claude",
)
# 2026-04-22: bumped default from 180 to 300 after multiple timeouts
# on module-review requests (workshop.py @ 750 LoC, cognition_quality.py
# @ 956 LoC). Claude Sonnet's response time on long-form structured
# JSON varies with load — 180s is too aggressive for review-class
# work. Still honors MAEZ_CLAUDE_TIMEOUT_S override.
CALL_TIMEOUT_S = float(os.environ.get("MAEZ_CLAUDE_TIMEOUT_S", "300"))
DEFAULT_MODEL = os.environ.get("MAEZ_CLAUDE_DEFAULT_MODEL", "sonnet")


class ClaudeCliAdapter(Adapter):
    name = "claude"

    # Accept aliases and fully-qualified model ids. Keep this list
    # narrow — adding a model here claims this adapter serves it;
    # ambiguous names should not match.
    _SHORT_ALIASES = {"opus", "sonnet", "haiku"}

    def handles_model(self, model: str) -> bool:
        if not model:
            return True  # claim empty model → routed to default backend
        n = model.lower().strip()
        if n in self._SHORT_ALIASES:
            return True
        if n.startswith("claude-"):
            return True
        return False

    def default_model(self) -> str:
        return DEFAULT_MODEL

    def resolve_model(self, requested: str) -> str:
        """Translate callers' aliases to what `claude --model` expects."""
        if not requested:
            return DEFAULT_MODEL
        n = requested.lower().strip()
        # Short aliases and `claude-*` full names both pass through
        # to the CLI, which resolves them further.
        return n if (n in self._SHORT_ALIASES or n.startswith("claude-")) else DEFAULT_MODEL

    def health(self) -> dict:
        """Cheap check: does the binary exist and look executable? Does
        NOT run `claude auth status` — that would be slower and risks
        counting against interactive-session limits."""
        bin_path = shutil.which(CLAUDE_BIN) or (CLAUDE_BIN
                                                 if os.access(CLAUDE_BIN, os.X_OK)
                                                 else None)
        return {
            "adapter": self.name,
            "bin": CLAUDE_BIN,
            "bin_available": bool(bin_path),
            "default_model": DEFAULT_MODEL,
            "auth_mode": "OAuth subscription (via `claude auth`)",
        }

    async def call(self, *, prompt: str, system_prompt: Optional[str],
                    model: str) -> CallResult:
        """Run one `claude --print` subprocess.

        Flags:
          -p                       one-shot, non-interactive
          --output-format json     parseable structured output
          --tools ""               no tool fan-out (one message per call)
          --no-session-persistence fresh session, no disk clutter
          --model <m>              opus/sonnet/haiku or full model id
          --system-prompt <sys>    forwarded from request
        """
        resolved = self.resolve_model(model)
        argv = [
            CLAUDE_BIN, "-p",
            "--output-format", "json",
            "--tools", "",
            "--no-session-persistence",
            "--model", resolved,
        ]
        if system_prompt:
            argv.extend(["--system-prompt", system_prompt])
        argv.append(prompt)

        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=CALL_TIMEOUT_S,
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise RuntimeError(f"claude timed out after {CALL_TIMEOUT_S}s")

        if proc.returncode != 0:
            err = (stderr or b"").decode("utf-8", errors="replace")[:800]
            raise RuntimeError(f"claude exited {proc.returncode}: {err}")

        raw = (stdout or b"").decode("utf-8", errors="replace")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise RuntimeError(
                f"claude produced unparseable JSON: {e}; head={raw[:200]!r}"
            )

        if data.get("is_error"):
            # Claude Code returns is_error=True for auth failures, etc.
            # Surface the message verbatim so ops can diagnose.
            raise RuntimeError(f"claude error: {data.get('result') or raw[:200]}")

        reply = data.get("result") or data.get("response") or ""
        if not reply and isinstance(data.get("messages"), list):
            for m in reversed(data["messages"]):
                if m.get("role") == "assistant":
                    content = m.get("content")
                    if isinstance(content, str):
                        reply = content
                    elif isinstance(content, list):
                        reply = "".join(
                            (c.get("text") or "") for c in content
                            if isinstance(c, dict) and c.get("type") == "text"
                        )
                    break

        usage = data.get("usage") or {}
        return CallResult(
            reply=reply,
            meta={"raw_keys": list(data.keys()),
                  "usage": usage,
                  "session_id": data.get("session_id")},
            input_toks=usage.get("input_tokens"),
            output_toks=usage.get("output_tokens"),
            model_used=resolved,
        )
