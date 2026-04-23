# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""
core/fast_backend_local.py — staging-only.

Local Gemma backend wrapper used by the fast reply prototype.

Two compatible public surfaces (Session 11d):

  1) Function form (preserved from 11c — used by bench_fast_reply_prototype):
       generate(prompt, max_tokens, temperature, timeout_s) -> BackendResult

  2) Class form (added in 11d — used by fast_backend_router):
       LocalGemmaBackend()
       backend.name           -> 'local-gemma4-26b'
       backend.is_available() -> bool
       backend.generate(prompt, max_tokens, temperature, timeout_s) -> BackendResult

Both forms call the same underlying Ollama path, so behavior is identical.
The class form satisfies the Backend protocol declared in fast_backend_router.

Convention follows existing call sites in the repo (skills/screen_perception.py,
core/continuity.py, skills/telegram_*.py): Ollama at localhost:11434, model
'gemma4:26b', /api/chat endpoint with messages = [{'role':'user', 'content':...}].
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

import requests


# ── backend identity ───────────────────────────────────────────────────
BACKEND_NAME = 'local-gemma4-26b'
OLLAMA_URL   = 'http://localhost:11434/api/chat'
MODEL        = 'gemma4:26b'

# Defaults — tuned for short, fast replies, not deep reasoning.
DEFAULT_MAX_TOKENS  = 256
DEFAULT_TEMPERATURE = 0.4
DEFAULT_TIMEOUT_S   = 30.0

# Empty-reply post-check (Session 11e). gemma4:26b is a thinking model and
# can return success=True with no visible output when num_predict is too
# tight to leave room past internal thinking. Anything below this many
# visible chars triggers the retry path in fast_reply_prototype.
MIN_VISIBLE_CHARS = 12


def is_visible_reply(text: str) -> bool:
    """True if `text` is non-empty after stripping whitespace AND has at
    least MIN_VISIBLE_CHARS visible characters. Used by the empty-reply
    retry mechanism in fast_reply_prototype."""
    if text is None:
        return False
    stripped = text.strip()
    return len(stripped) >= MIN_VISIBLE_CHARS


@dataclass
class BackendResult:
    success: bool
    text: str
    backend_name: str
    model_call_ms: int
    error: Optional[str] = None
    raw_status: Optional[int] = None


def is_available() -> bool:
    """Cheap reachability probe — does the local inference backend answer?

    Session 11p: backend-aware. When MAEZ_LLM_BACKEND=llamacpp, probes the
    llama-server OpenAI-compatible endpoint instead of Ollama. The router
    uses this to decide "is local available?" and used to only know about
    Ollama; with llama.cpp as the new substrate, Ollama may be stopped
    entirely while llama-server is serving requests.

    10-M2: the active-backend decision is resolved once at the top and
    drives the probe target. Previously, an exception importing or
    calling active_backend() silently fell through to Ollama — so a
    llamacpp deployment whose llm_client module briefly failed would
    return "local available" based on a stale Ollama install that the
    caller would then try to use. If the backend is llamacpp we only
    probe llama-server; fallback to Ollama only when the backend is
    explicitly Ollama (or when active_backend is unresolvable, which
    remains the Ollama-default behavior for bootstrap).
    """
    backend: Optional[str] = None
    llamacpp_probe_url: Optional[str] = None
    try:
        from core.llm_client import (
            active_backend as _lc_active_backend,
            BACKEND_LLAMACPP,
            LLAMACPP_BASE_URL,
        )
        backend = _lc_active_backend()
        if backend == BACKEND_LLAMACPP:
            llamacpp_probe_url = LLAMACPP_BASE_URL.rstrip('/') + '/models'
    except Exception:
        # llm_client unavailable — treat as bootstrap / Ollama-default.
        backend = None

    if llamacpp_probe_url is not None:
        try:
            r = requests.get(llamacpp_probe_url, timeout=1.5)
            return r.status_code == 200
        except Exception:
            return False

    # Ollama (explicit or bootstrap default).
    try:
        r = requests.get('http://localhost:11434/api/tags', timeout=1.5)
        return r.status_code == 200
    except Exception:
        return False


def generate(
    prompt: str,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    temperature: float = DEFAULT_TEMPERATURE,
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> BackendResult:
    """Single-shot generation via local Ollama. Never raises.

    Returns a BackendResult with success=False on any failure mode
    (timeout, non-200, network error, parse error). The fast reply
    prototype layers a fallback message on top so the user always
    sees something.

    Session 11n — optional llama.cpp backend branch (staging pivot):
    when the MAEZ_LLM_BACKEND env var is 'llamacpp' (read at call time via
    core.llm_client.active_backend), this function delegates to the
    llama-cpp-python OpenAI-compat server at 127.0.0.1:8080 instead of
    ollama. Ollama path is unchanged and remains the default. This is the
    lowest-risk surface for piloting the llama.cpp substrate — the fast
    lane is flag-gated staging and the rollback is just unsetting the env
    var.
    """
    t0 = time.perf_counter()

    # ── Session 11n: llama.cpp backend branch ────────────────────────
    try:
        from core.llm_client import active_backend as _lc_active_backend
        from core.llm_client import BACKEND_LLAMACPP as _LC_LLAMACPP
        _backend_is_llamacpp = _lc_active_backend() == _LC_LLAMACPP
    except Exception:
        _backend_is_llamacpp = False

    if _backend_is_llamacpp:
        try:
            from core import llm_client as _llm_client
            # llm_client.chat adapts both backends to an ollama-shaped
            # response with .message.content. think=False is honored for
            # ollama and ignored for llamacpp (the small model doesn't
            # have a thinking phase anyway).
            resp_obj = _llm_client.chat(
                model=MODEL,
                messages=[{'role': 'user', 'content': prompt}],
                stream=False,
                think=False,
                options={
                    'temperature': temperature,
                    'num_predict': max_tokens,
                },
            )
            text = getattr(getattr(resp_obj, 'message', None), 'content', '') or ''
            return BackendResult(
                success=True,
                text=text,
                backend_name='local-llamacpp',
                model_call_ms=int((time.perf_counter() - t0) * 1000),
            )
        except Exception as e:
            return BackendResult(
                success=False, text='', backend_name='local-llamacpp',
                model_call_ms=int((time.perf_counter() - t0) * 1000),
                error=f'llamacpp call failed: {e!r}',
            )

    # ── original Ollama path (default, unchanged) ────────────────────
    try:
        resp = requests.post(
            OLLAMA_URL,
            json={
                'model': MODEL,
                'messages': [{'role': 'user', 'content': prompt}],
                'stream': False,
                # Session 11j: gemma4:26b is a thinking model (RENDERER gemma4
                # PARSER gemma4 in the modelfile). Internal reasoning routinely
                # burns 90%+ of wall-clock on invisible tokens — measured: 1480
                # thinking chars → 30 visible chars, 20.8s cold. Disabling think
                # drops the same reply to 0.3s (cold) with equal or better
                # visible output. The fast lane exists for responsive replies;
                # there is no budget for internal reasoning here. The daemon's
                # slow reasoning loop is a separate code path (maez_daemon.py,
                # ollama.chat directly) and keeps its thinking budget intact.
                'think': False,
                'options': {
                    'temperature': temperature,
                    'num_predict': max_tokens,
                },
            },
            timeout=timeout_s,
        )
    except requests.Timeout:
        return BackendResult(
            success=False, text='', backend_name=BACKEND_NAME,
            model_call_ms=int((time.perf_counter() - t0) * 1000),
            error=f'ollama timeout after {timeout_s:.1f}s',
        )
    except Exception as e:
        return BackendResult(
            success=False, text='', backend_name=BACKEND_NAME,
            model_call_ms=int((time.perf_counter() - t0) * 1000),
            error=f'ollama call failed: {e!r}',
        )

    elapsed_ms = int((time.perf_counter() - t0) * 1000)

    if resp.status_code != 200:
        return BackendResult(
            success=False, text='', backend_name=BACKEND_NAME,
            model_call_ms=elapsed_ms, raw_status=resp.status_code,
            error=f'ollama returned {resp.status_code}: {resp.text[:200]}',
        )

    try:
        body = resp.json()
        text = body['message']['content']
    except Exception as e:
        return BackendResult(
            success=False, text='', backend_name=BACKEND_NAME,
            model_call_ms=elapsed_ms, raw_status=resp.status_code,
            error=f'ollama response parse failed: {e!r}',
        )

    return BackendResult(
        success=True,
        text=text.strip(),
        backend_name=BACKEND_NAME,
        model_call_ms=elapsed_ms,
        raw_status=resp.status_code,
    )


# ──────────────────────────────────────────────────────────────────────
#  Class form — satisfies the Backend protocol declared in
#  core/fast_backend_router.py. Wraps the function form 1:1 so any
#  caller can use either interchangeably.
# ──────────────────────────────────────────────────────────────────────
class LocalGemmaBackend:
    """Local Ollama gemma4:26b backend. Stateless, cheap to instantiate."""

    name: str = BACKEND_NAME

    def is_available(self) -> bool:
        return is_available()

    def generate(
        self,
        prompt: str,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
        timeout_s: float = DEFAULT_TIMEOUT_S,
    ) -> BackendResult:
        return generate(
            prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout_s=timeout_s,
        )

    def __repr__(self) -> str:
        return f'LocalGemmaBackend(name={self.name!r})'
