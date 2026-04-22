# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Adapter: Gemini CLI (Google One AI Premium subscription).

Parallel to the Claude adapter. Wraps `gemini -p` as an async
subprocess, consuming the user's Google One AI Premium quota.

Authentication: `gemini` handles its own Google account auth. Run
`gemini auth login` interactively once; from then on this adapter
can invoke it non-interactively.

If `gemini` is not installed, the adapter still loads but health()
reports bin_available=false and call() raises cleanly. This lets
the proxy run on machines without Gemini installed.

Claims: models starting with `gemini-`.

NOTE: The Gemini CLI's exact flag set may drift. This adapter uses a
minimal set observed as of 2026-04-22. If the CLI changes output
format, update _parse_result and the flags below.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
from typing import Optional

from core.subscription_proxy.adapters.base import Adapter, CallResult

logger = logging.getLogger("maez.subscription_proxy.gemini")

GEMINI_BIN = os.environ.get("MAEZ_GEMINI_BIN", "gemini")
CALL_TIMEOUT_S = float(os.environ.get("MAEZ_GEMINI_TIMEOUT_S", "180"))
DEFAULT_MODEL = os.environ.get(
    "MAEZ_GEMINI_DEFAULT_MODEL", "gemini-2.5-pro",
)


class GeminiCliAdapter(Adapter):
    name = "gemini"

    def handles_model(self, model: str) -> bool:
        if not model:
            return False
        return model.lower().startswith("gemini-")

    def default_model(self) -> str:
        return DEFAULT_MODEL

    def resolve_model(self, requested: str) -> str:
        return requested if requested else DEFAULT_MODEL

    def health(self) -> dict:
        bin_path = shutil.which(GEMINI_BIN)
        return {
            "adapter": self.name,
            "bin": GEMINI_BIN,
            "bin_available": bool(bin_path),
            "bin_resolved": bin_path or "(not found on PATH)",
            "default_model": DEFAULT_MODEL,
            "auth_mode": "Google account via `gemini auth login`",
        }

    async def call(self, *, prompt: str, system_prompt: Optional[str],
                    model: str) -> CallResult:
        if not shutil.which(GEMINI_BIN):
            raise RuntimeError(
                f"gemini CLI not on PATH (looked for {GEMINI_BIN!r}). "
                f"Install from https://github.com/google-gemini/gemini-cli "
                f"and run `gemini auth login`."
            )

        resolved = self.resolve_model(model)
        # -p / --prompt: non-interactive one-shot
        # --model: model id
        # --output-format json: structured output we can parse
        #
        # System prompt — Gemini CLI currently doesn't have a dedicated
        # --system-prompt flag (as of the observed version). Fold it
        # into the user prompt with a clear separator. Upgrade this
        # when/if the CLI adds the flag.
        combined = (
            f"[SYSTEM INSTRUCTION]\n{system_prompt}\n\n[USER]\n{prompt}"
            if system_prompt else prompt
        )
        argv = [
            GEMINI_BIN,
            "-p", combined,
            "--model", resolved,
            "--output-format", "json",
        ]

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
            raise RuntimeError(f"gemini timed out after {CALL_TIMEOUT_S}s")

        if proc.returncode != 0:
            err = (stderr or b"").decode("utf-8", errors="replace")[:800]
            raise RuntimeError(f"gemini exited {proc.returncode}: {err}")

        raw = (stdout or b"").decode("utf-8", errors="replace").strip()

        # Try JSON first; fall back to raw text if the CLI returned plain.
        reply = ""
        meta: dict = {}
        try:
            data = json.loads(raw)
            # Best-effort extraction across observed shapes.
            reply = (
                data.get("response")
                or data.get("text")
                or data.get("result")
                or ""
            )
            if not reply and isinstance(data.get("candidates"), list):
                # Vertex-style shape
                cand = data["candidates"][0] if data["candidates"] else {}
                content = (cand.get("content") or {})
                parts = content.get("parts") or []
                reply = "".join(p.get("text", "") for p in parts
                                  if isinstance(p, dict))
            meta = {"raw_keys": list(data.keys())}
        except json.JSONDecodeError:
            reply = raw

        if not reply:
            raise RuntimeError(
                f"gemini produced empty reply; raw head={raw[:200]!r}"
            )

        return CallResult(
            reply=reply,
            meta=meta,
            model_used=resolved,
        )
