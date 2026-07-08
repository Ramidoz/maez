# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""
core/llm_client.py — Session 11n, staging pivot.

Thin wrapper that dispatches LLM chat calls to either the existing Ollama
backend or a llama-cpp-python OpenAI-compatible server, gated by the
environment variable MAEZ_LLM_BACKEND.

Purpose
=======
Session 11n begins the llama.cpp migration pivot (see the 11n plan). The
wrapper lets us flip a single conversational surface over to llama.cpp's
server mode without touching Ollama-backed paths. When MAEZ_LLM_BACKEND is
unset or set to 'ollama', calls pass through to ollama.chat() unchanged.
When set to 'llamacpp', calls hit the OpenAI-compatible llama-server on
http://127.0.0.1:8080/v1.

Safety contract
===============
- Defaults to Ollama. A missing env var does NOT flip the backend.
- Returns a lightweight response object with the same shape for both
  backends: .message.content (string), .message.thinking (string or None).
  Consumers that only read .message.content work unchanged across backends.
- Never raises on backend-level errors — bubbles them up via a BackendError
  exception the caller can handle the same way it already handles Ollama
  failures.
- No global state. No import-time side effects beyond the module-level
  OpenAI client singleton, which is only created if llama.cpp is requested.

Staging-only
============
- Not imported by daemon/maez_daemon.py (the daemon continues to call
  ollama.chat directly in 11n).
- Only the fast-lane adapter in skills/web_interface.py uses this wrapper
  in 11n. Other conversational surfaces migrate in 11o.
"""

from __future__ import annotations

import json
import os
import re
import socket as _socket
import threading
import time
import urllib.request
from dataclasses import dataclass
from typing import Any, Optional
from urllib.parse import urlparse

from core.model_config import BACKEND_LLAMACPP, BACKEND_OLLAMA

# ── backend selection ────────────────────────────────────────────────
# Legacy export. Runtime call paths use _llamacpp_base_url() so endpoint
# changes are resolved per call.
LLAMACPP_BASE_URL = os.environ.get('MAEZ_LLAMACPP_URL', 'http://127.0.0.1:8080/v1')
# Session 11p: bumped from qwen2.5-3b to gemma-4-26b after the source-built
# CUDA llama-server proved gemma-4-26B-A4B runs at ~133 tok/s on RTX 4090
# with continuous batching + prompt cache. This alias must match the --alias
# flag passed to llama-server at launch, or be ignored (llama-server accepts
# any string when only one model is loaded).
from core.model_config import PRIMARY_BASE_URL as _PRIMARY_BASE_URL
from core.model_config import PRIMARY_MODEL as _PRIMARY_MODEL
PRIMARY_BASE_URL = _PRIMARY_BASE_URL
PRIMARY_MODEL = _PRIMARY_MODEL
# MAEZ_LLAMACPP_MODEL is a legacy override; prefer MAEZ_PRIMARY_MODEL via model_config.
LLAMACPP_MODEL    = os.environ.get('MAEZ_LLAMACPP_MODEL', _PRIMARY_MODEL)

# Gemma-4 / llama.cpp special tokens that should never be forwarded as
# literal user/system content to the OpenAI-compatible chat endpoint.
# If they leak into live prompts, llama-server's jinja chat template can
# misparse them and return 500s like "Failed to parse input at pos ...".
#
# The `<|...|>` middle segment excludes `<` and `>` (not just `|`) so the
# regex can't cross the asymmetric Gemma-native tool-call delimiters
# `<|tool_call>call:NAME{...}<tool_call|>`. Without the `<>` exclusions
# the greedy match would span from the opening `<|` of `<|tool_call>` to
# the closing `|>` of `<tool_call|>` and delete the entire tool-call body
# in between — silently destroying the LoRA's primary trained tool-call
# format. The Jarvis parser has an explicit branch for Gemma-native, and
# the sanitizer must leave it intact for that branch to ever fire.
_SPECIAL_TOKEN_RE = re.compile(
    r"<\|[^|<>]*\|>"
    r"|<start_of_turn>"
    r"|<end_of_turn>"
    r"|<maez_thought>"
    r"|</maez_thought>"
    r"|<bos>"
    r"|<eos>"
)

# Maez's own memory-framing markers. If any recalled content contains these
# (because the LLM once echoed the envelope into its output and the output got
# persisted), the outer <RECALLED>...</RECALLED> wrapper breaks — the model
# sees a stray close tag or a duplicate header and starts reading stale recall
# as live state. Strip them from content before re-wrapping.
_FRAMING_TOKEN_RE = re.compile(
    r"</?RECALLED\b[^>]*>"
    r"|=== (?:END )?PAST OBSERVATIONS[^=]*===",
    re.IGNORECASE,
)


def active_backend() -> str:
    """Return the currently selected backend name, defaulting to 'ollama'.

    Reads MAEZ_LLM_BACKEND at call time (not import time) so a flag flip
    picks up on the next request without requiring a process restart.
    """
    from core.model_config import active_backend as _active_backend

    return _active_backend()


def _props_url_for_base(base_url: str) -> str:
    base = str(base_url or "").rstrip("/")
    if base.endswith("/v1"):
        base = base[:-3].rstrip("/")
    return f"{base}/props"


def _llamacpp_props_url() -> str:
    return _props_url_for_base(_llamacpp_base_url())


def _llamacpp_base_url() -> str:
    from core.model_config import llamacpp_base_url_from_env

    return llamacpp_base_url_from_env()


def _props_model_alias(url: str, *, timeout_s: float) -> str | None:
    with urllib.request.urlopen(url, timeout=timeout_s) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    alias = payload.get("model_alias")
    if alias:
        return str(alias)
    model_path = payload.get("model_path")
    if model_path:
        return str(model_path).rsplit("/", 1)[-1]
    return None


def served_model_alias(*, default: str | None = None, timeout_s: float = 1.0) -> str:
    """Return the actually served model alias for telemetry.

    This is observational only: it does not affect routing. OpenAI-compatible
    llama-server deployments can ignore the requested model label when one
    model is loaded, so telemetry reads `/props` to report the resident alias
    when that endpoint is available.
    """
    fallback = default or LLAMACPP_MODEL
    primary_props_url = _props_url_for_base(PRIMARY_BASE_URL)
    try:
        alias = _props_model_alias(primary_props_url, timeout_s=timeout_s)
        if alias:
            return alias
    except Exception:
        pass

    if active_backend() != BACKEND_LLAMACPP:
        return fallback
    try:
        alias = _props_model_alias(_llamacpp_props_url(), timeout_s=timeout_s)
        if alias:
            return alias
    except Exception:
        return "llamacpp:unknown"
    return "llamacpp:unknown"


class BackendError(Exception):
    """Raised on any underlying backend failure. Callers should handle this
    the same way they already handle ollama exceptions."""


@dataclass
class _LlmMessage:
    content: str
    thinking: Optional[str] = None


@dataclass
class _LlmResponse:
    """Minimal ollama.ChatResponse-shaped object so consumers can call
    resp.message.content without caring which backend produced it."""
    message: _LlmMessage
    server_prompt_ms: Optional[int] = None
    finish_reason: Optional[str] = None
    backend: Optional[str] = None
    thinking_suppressed: Optional[bool] = None


class _LlamaCppStreamParser:
    """Incremental HTTP/1.1 chunked SSE parser for llama-server streaming."""

    def __init__(self):
        self._buf = bytearray()
        self._phase = "status"
        self._chunk_left = 0
        self._sse = bytearray()
        self._yielded = False
        self.cancelled = False
        self.server_prompt_ms: int | None = None

    @property
    def done(self) -> bool:
        return self._phase == "done"

    def feed(self, data: bytes) -> list[str]:
        if data:
            self._buf.extend(data)
        tokens: list[str] = []
        advanced = True
        while advanced and self._phase != "done":
            advanced = False
            if self._phase == "status":
                advanced = self._parse_status()
            elif self._phase == "headers":
                advanced = self._parse_header_line()
            elif self._phase == "size":
                advanced = self._parse_chunk_size()
            elif self._phase == "body":
                advanced = self._parse_chunk_body()
            elif self._phase == "trailer":
                advanced = self._parse_chunk_trailer()
            tokens.extend(self._drain_sse())
        if self.done and not self._yielded and not self.cancelled:
            raise BackendError("llamacpp empty stream")
        return tokens

    def _parse_status(self) -> bool:
        idx = self._buf.find(b"\r\n")
        if idx < 0:
            return False
        line = bytes(self._buf[:idx])
        del self._buf[: idx + 2]
        parts = line.split(b" ", 2)
        code = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
        if code != 200:
            if self.cancelled:
                self._phase = "done"
                return True
            raise BackendError(f"llamacpp non-200: {code}")
        self._phase = "headers"
        return True

    def _parse_header_line(self) -> bool:
        idx = self._buf.find(b"\r\n")
        if idx < 0:
            return False
        if idx == 0:
            del self._buf[:2]
            self._phase = "size"
            return True
        del self._buf[: idx + 2]
        return True

    def _parse_chunk_size(self) -> bool:
        idx = self._buf.find(b"\r\n")
        if idx < 0:
            return False
        size_line = bytes(self._buf[:idx]).split(b";", 1)[0].strip()
        del self._buf[: idx + 2]
        try:
            size = int(size_line, 16)
        except ValueError as exc:
            if self.cancelled:
                self._phase = "done"
                return True
            raise BackendError("llamacpp bad chunk size") from exc
        if size == 0:
            self._phase = "done"
        else:
            self._chunk_left = size
            self._phase = "body"
        return True

    def _parse_chunk_body(self) -> bool:
        if not self._buf:
            return False
        take = min(self._chunk_left, len(self._buf))
        self._sse.extend(self._buf[:take])
        del self._buf[:take]
        self._chunk_left -= take
        if self._chunk_left == 0:
            self._phase = "trailer"
        return True

    def _parse_chunk_trailer(self) -> bool:
        if len(self._buf) < 2:
            return False
        trailer = bytes(self._buf[:2])
        del self._buf[:2]
        if trailer != b"\r\n":
            if self.cancelled:
                self._phase = "done"
                return True
            raise BackendError("llamacpp bad chunk trailer")
        self._phase = "size"
        return True

    def _drain_sse(self) -> list[str]:
        tokens: list[str] = []
        while True:
            idx = self._sse.find(b"\n\n")
            if idx < 0:
                break
            event = bytes(self._sse[:idx])
            del self._sse[: idx + 2]
            for line in event.split(b"\n"):
                line = line.strip()
                if not line.startswith(b"data:"):
                    continue
                payload = line[len(b"data:") :].strip()
                if payload == b"[DONE]":
                    self._phase = "done"
                    continue
                try:
                    data = json.loads(payload)
                    timings = data.get("timings")
                    if isinstance(timings, dict) and timings.get("prompt_ms") is not None:
                        try:
                            self.server_prompt_ms = int(float(timings["prompt_ms"]))
                        except (TypeError, ValueError):
                            pass
                    content = _openai_stream_content(data)
                except Exception as exc:
                    if self.cancelled:
                        return tokens
                    raise BackendError("llamacpp malformed SSE json") from exc
                content = _strip_special_tokens(content or "")
                if content:
                    self._yielded = True
                    tokens.append(content)
        return tokens


def _openai_stream_content(data: dict) -> str:
    choices = data.get("choices") or ()
    if not choices:
        return ""
    first = choices[0] or {}
    delta = first.get("delta") or {}
    message = first.get("message") or {}
    return delta.get("content") or message.get("content") or ""


def _connect_llamacpp_socket(
    base_url: str,
    body: bytes,
    *,
    timeout_s: float = 90,
):
    parsed = urlparse(base_url)
    if parsed.scheme != "http":
        raise BackendError(f"socket transport requires http, got {parsed.scheme!r}")
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 80
    base_path = parsed.path.rstrip("/")
    path = f"{base_path}/chat/completions" if base_path else "/chat/completions"
    try:
        sock = _socket.create_connection((host, port), timeout=timeout_s)
    except OSError as exc:
        raise BackendError(f"llamacpp socket connect failed: {exc!r}") from exc
    request_head = (
        f"POST {path} HTTP/1.1\r\n"
        f"Host: {host}:{port}\r\n"
        "Authorization: Bearer llamacpp\r\n"
        "Content-Type: application/json\r\n"
        f"Content-Length: {len(body)}\r\n"
        "Connection: close\r\n\r\n"
    ).encode("utf-8")
    try:
        sock.sendall(request_head + body)
    except OSError as exc:
        try:
            sock.close()
        except OSError:
            pass
        raise BackendError(f"llamacpp socket send failed: {exc!r}") from exc
    return sock


def _strip_special_tokens(text: str) -> str:
    """Remove template/control tokens that break llama-server parsing."""
    if not text:
        return text
    return _SPECIAL_TOKEN_RE.sub("", text)


def _strip_framing_tokens(text: str) -> str:
    """Remove Maez's own memory-framing envelope markers from content."""
    if not text:
        return text
    return _FRAMING_TOKEN_RE.sub("", text)


class _LlamaCppSocketStream:
    """Ollama-shaped iterator backed by a raw socket cancellation handle."""

    def __init__(self, *, sock):
        self._sock = sock
        self._parser = _LlamaCppStreamParser()
        self._closed = False
        self._close_lock = threading.Lock()

    def close(self):
        self._close(mark_cancelled=True)

    @property
    def server_prompt_ms(self) -> int | None:
        return self._parser.server_prompt_ms

    def _close(self, *, mark_cancelled: bool) -> None:
        with self._close_lock:
            if self._closed:
                return
            self._closed = True
            if mark_cancelled:
                self._parser.cancelled = True
            try:
                self._sock.shutdown(_socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                self._sock.close()
            except OSError:
                pass

    def __iter__(self):
        try:
            while not self._parser.done:
                try:
                    data = self._sock.recv(65536)
                except OSError as exc:
                    if self._closed:
                        return
                    raise BackendError("llamacpp socket read failed") from exc
                if not data:
                    if self._closed or self._parser.cancelled:
                        return
                    raise BackendError("llamacpp stream ended before DONE")
                for token in self._parser.feed(data):
                    yield _LlmResponse(
                        message=_LlmMessage(content=token, thinking=None)
                    )
        finally:
            self._close(mark_cancelled=False)


def sanitize_prompt_text(text: str) -> str:
    """Public helper for text that may be fed back into live prompts."""
    return _strip_framing_tokens(_strip_special_tokens(text))


def _sanitize_messages_for_llamacpp(messages: list[dict]) -> list[dict]:
    """Return a shallow-copied message list safe for llama-server.

    We only sanitize the local llama.cpp path so Ollama behavior remains
    unchanged. This keeps Maez's higher-level prompts intact while
    stripping the literal control tokens that have been observed to crash
    the request parser.
    """
    cleaned: list[dict] = []
    for msg in messages or []:
        if not isinstance(msg, dict):
            cleaned.append(msg)
            continue
        clone = dict(msg)
        content = clone.get("content")
        if isinstance(content, str):
            clone["content"] = _strip_special_tokens(content)
        cleaned.append(clone)
    return cleaned


# ── ollama path (no-op passthrough) ──────────────────────────────────
def _chat_ollama(
    model: str,
    messages: list[dict],
    stream: bool = False,
    think: Optional[bool] = None,
    options: Optional[dict] = None,
) -> Any:
    """Call ollama.chat directly. Returns ollama's native response object
    (same shape _LlmResponse imitates, so consumers don't need to adapt)."""
    import ollama
    kwargs: dict[str, Any] = {
        'model': model,
        'messages': messages,
        'stream': stream,
    }
    if think is not None:
        kwargs['think'] = think
    if options is not None:
        kwargs['options'] = options
    try:
        return ollama.chat(**kwargs)
    except Exception as e:
        raise BackendError(f'ollama chat failed: {e!r}') from e


def _ollama_options(options: Optional[dict]) -> Optional[dict]:
    if options is None:
        return None
    cleaned = dict(options)
    cleaned.pop('chat_template_kwargs', None)
    return cleaned


# ── llamacpp path via OpenAI-compat client ───────────────────────────
_openai_client_singletons: dict[str, Any] = {}


def _normalize_openai_base_url(base_url: str) -> str:
    base = str(base_url or "").rstrip("/")
    if not base:
        base = "http://127.0.0.1:8080"
    if not base.endswith("/v1"):
        base = f"{base}/v1"
    return base


def _get_openai_client_for_base(base_url: str):
    """Lazy singleton for the OpenAI client pointed at llama-server. Only
    constructed when a llamacpp call actually happens, so the ollama path
    never imports or touches openai."""
    normalized = _normalize_openai_base_url(base_url)
    client = _openai_client_singletons.get(normalized)
    if client is None:
        from openai import OpenAI
        # llama-cpp-python's server accepts any api_key; we pass 'llamacpp'
        # as a non-empty placeholder because OpenAI client requires a value.
        client = OpenAI(
            base_url=normalized,
            api_key='llamacpp',
        )
        _openai_client_singletons[normalized] = client
    return client


def _get_openai_client():
    return _get_openai_client_for_base(_llamacpp_base_url())


def _thinking_suppressed(
    *,
    think: Optional[bool],
    options: Optional[dict],
) -> bool:
    try:
        return _chat_template_kwargs(think=think, options=options).get("enable_thinking") is False
    except Exception:
        return think is False


def _chat_openai_compat(
    *,
    base_url: str,
    backend_label: str,
    model: str,
    messages: list[dict],
    stream: bool = False,
    think: Optional[bool] = None,
    options: Optional[dict] = None,
    timeout_s: Optional[float] = None,
) -> _LlmResponse:
    if stream:
        raise BackendError("direct OpenAI-compatible classifier calls must be non-streaming")

    client = _get_openai_client_for_base(base_url)
    messages = _sanitize_messages_for_llamacpp(messages)

    temperature = 0.7
    max_tokens = 512
    if options:
        temperature = float(options.get('temperature', temperature))
        max_tokens = int(options.get('num_predict', max_tokens))

    extra_body: dict = {}
    merged = _chat_template_kwargs(think=think, options=options)
    if merged:
        extra_body['chat_template_kwargs'] = merged

    try:
        completion = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            extra_body=extra_body if extra_body else None,
            timeout=timeout_s,
        )
    except Exception as e:
        raise BackendError(f'{backend_label} chat failed: {e!r}') from e

    try:
        first = completion.choices[0]
        content = first.message.content or ''
        finish_reason = str(getattr(first, 'finish_reason', '') or '')
        content = _strip_special_tokens(content)
    except Exception as e:
        raise BackendError(f'{backend_label} response parse failed: {e!r}') from e

    return _LlmResponse(
        message=_LlmMessage(content=content, thinking=None),
        finish_reason=finish_reason,
        backend=backend_label,
        thinking_suppressed=_thinking_suppressed(think=think, options=options),
    )


def _chat_llamacpp(
    model: str,
    messages: list[dict],
    stream: bool = False,
    think: Optional[bool] = None,
    options: Optional[dict] = None,
    timeout_s: Optional[float] = None,
) -> _LlmResponse:
    """Call llama.cpp's OpenAI-compatible server (source-built with CUDA
    since Session 11p) and adapt the response to the ollama shape that
    consumers expect.

    The `think` kwarg is ollama-style (top-level bool). llama.cpp gemma4
    templates honor an equivalent via `chat_template_kwargs.enable_thinking`
    inside the extra_body, which this function forwards when `think=False`.
    """
    if not stream:
        return _chat_openai_compat(
            base_url=_llamacpp_base_url(),
            backend_label=BACKEND_LLAMACPP,
            model=LLAMACPP_MODEL,
            messages=messages,
            stream=False,
            think=think,
            options=options,
            timeout_s=timeout_s,
        )

    # Map ollama options.temperature/num_predict to OpenAI kwargs.
    temperature = 0.7
    max_tokens = 512
    if options:
        temperature = float(options.get('temperature', temperature))
        # Ollama calls it num_predict; OpenAI calls it max_tokens
        max_tokens = int(options.get('num_predict', max_tokens))

    # The llama-server ignores the 'model' field if only one model is
    # loaded, but OpenAI spec requires it. Use the configured default.
    effective_model = LLAMACPP_MODEL

    # Chat-template kwargs are model-specific quirks (enable_thinking,
    # tool-format toggles, etc.). They live in /etc/maez/model.env as
    # MAEZ_PRIMARY_CHAT_KWARGS JSON, so swapping to any model is a
    # config change, not a code change. When think is not None, we
    # merge in an enable_thinking override; otherwise we pass the
    # configured defaults verbatim. Any model that doesn't understand
    # a given kwarg will simply ignore it.
    from core.model_config import PRIMARY_CHAT_KWARGS as _cfg_kwargs
    extra_body: dict = {}
    if _cfg_kwargs or think is not None or (options and options.get('chat_template_kwargs')):
        merged = _chat_template_kwargs(think=think, options=options)
        if merged:
            extra_body['chat_template_kwargs'] = merged

    try:
        messages = _sanitize_messages_for_llamacpp(messages)
        return iter(_start_llamacpp_stream(
            model=effective_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            extra_body=extra_body,
            timeout_s=timeout_s,
        ))
    except Exception as e:
        raise BackendError(f'llamacpp chat failed: {e!r}') from e


def _start_llamacpp_stream(
    *,
    model: str,
    messages: list[dict],
    temperature: float,
    max_tokens: int,
    extra_body: dict,
    timeout_s: Optional[float] = None,
):
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
    }
    if extra_body:
        payload.update(extra_body)
    body = json.dumps(payload).encode("utf-8")
    sock = _connect_llamacpp_socket(
        _llamacpp_base_url(),
        body,
        timeout_s=timeout_s if timeout_s is not None else 90,
    )
    return _LlamaCppSocketStream(sock=sock)


def start_cancellable_chat(
    model: str,
    messages: list[dict],
    think: Optional[bool] = None,
    options: Optional[dict] = None,
):
    """Start a cancellable streaming call for gateway-owned buffered chat."""
    from core.routing.cancellable_brain_call import CancellableBrainCall

    backend = active_backend()
    if backend == BACKEND_LLAMACPP:
        messages = _sanitize_messages_for_llamacpp(messages)
        temperature = 0.7
        max_tokens = 512
        if options:
            temperature = float(options.get('temperature', temperature))
            max_tokens = int(options.get('num_predict', max_tokens))
        from core.model_config import PRIMARY_CHAT_KWARGS as _cfg_kwargs

        extra_body: dict = {}
        if _cfg_kwargs or think is not None or (options and options.get('chat_template_kwargs')):
            merged = _chat_template_kwargs(think=think, options=options)
            if merged:
                extra_body['chat_template_kwargs'] = merged
        stream = _start_llamacpp_stream(
            model=LLAMACPP_MODEL,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            extra_body=extra_body,
        )
        return CancellableBrainCall(raw_stream=stream)

    return CancellableBrainCall(
        raw_stream=_chat_ollama(
            model=model,
            messages=messages,
            stream=True,
            think=think,
            options=_ollama_options(options),
        )
    )


def _chat_primary_openai(
    model: str,
    messages: list[dict],
    stream: bool = False,
    think: Optional[bool] = None,
    options: Optional[dict] = None,
) -> _LlmResponse:
    if stream:
        raise BackendError("primary direct classifier calls must be non-streaming")
    return _chat_openai_compat(
        base_url=PRIMARY_BASE_URL,
        backend_label="primary_openai",
        model=model or PRIMARY_MODEL,
        messages=messages,
        stream=False,
        think=think,
        options=options,
    )


def chat_direct(
    model: str,
    messages: list[dict],
    think: Optional[bool] = None,
    options: Optional[dict] = None,
    purpose: Any = None,
) -> Any:
    """Direct non-gateway chat for tiny deterministic classifier calls.

    This intentionally uses the configured primary OpenAI-compatible
    endpoint, not the legacy backend selector. The routing-comprehension
    judge needs the same chat-template kwargs behavior proven on
    MAEZ_PRIMARY_BASE_URL.
    """
    del purpose
    return _chat_primary_openai(
        model=model,
        messages=messages,
        stream=False,
        think=think,
        options=options,
    )


# ── public API ───────────────────────────────────────────────────────
def chat(
    model: str,
    messages: list[dict],
    stream: bool = False,
    think: Optional[bool] = None,
    options: Optional[dict] = None,
    purpose: Any = None,
) -> Any:
    """Unified chat entry point. Dispatches to the backend chosen by the
    MAEZ_LLM_BACKEND env var at call time.

    Return value is ollama-shaped regardless of backend:
        resp.message.content     -> str
        resp.message.thinking    -> Optional[str]

    Raises BackendError on backend-level failures. Consumers that currently
    wrap ollama.chat(...) in a try/except can wrap llm_client.chat(...) the
    same way and the exception surface is equivalent.
    """
    if stream:
        backend = active_backend()
        if backend == BACKEND_LLAMACPP:
            return _chat_llamacpp(
                model=model,
                messages=messages,
                stream=True,
                think=think,
                options=options,
            )
        return _chat_ollama(
            model=model,
            messages=messages,
            stream=True,
            think=think,
            options=_ollama_options(options),
        )

    from core.routing import brain_gateway

    call_box: dict[str, Any] = {}

    def _start_gateway_call():
        call = start_cancellable_chat(
            model=model,
            messages=messages,
            think=think,
            options=options,
        )
        call_box["call"] = call
        return call

    reply = brain_gateway.GATEWAY.submit(
        purpose=purpose if purpose is not None else brain_gateway.current_purpose(),
        run_streaming_fn=_start_gateway_call,
    )
    server_prompt_ms = getattr(call_box.get("call"), "server_prompt_ms", None)
    return _LlmResponse(
        message=_LlmMessage(content=reply, thinking=None),
        server_prompt_ms=server_prompt_ms,
    )


def _chat_template_kwargs(
    *,
    think: Optional[bool],
    options: Optional[dict],
) -> dict:
    from core.model_config import PRIMARY_CHAT_KWARGS as _cfg_kwargs

    merged = dict(_cfg_kwargs)
    if options:
        explicit = options.get('chat_template_kwargs')
        if isinstance(explicit, dict):
            merged.update(explicit)
    if think is False:
        merged['enable_thinking'] = False
    elif think is True:
        merged['enable_thinking'] = True
    return merged


# ── prompt-completion entry point (for /api/generate callers) ──────
def generate(
    prompt: str,
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 512,
    timeout_s: float = 120.0,
    think: Optional[bool] = False,
) -> str:
    """Single-prompt completion. Returns the completion text directly.

    Session 11r: added for callers that used Ollama's /api/generate
    endpoint directly with requests.post (e.g., skills/evolution_engine.py's
    proposal generation paths). Those callers historically did:

        resp = requests.post('http://localhost:11434/api/generate',
                             json={'model': M, 'prompt': P, 'stream': False})
        text = resp.json().get('response', '').strip()

    Replace with:

        from core import llm_client
        text = llm_client.generate(prompt=P).strip()

    Internally wraps as a single-user-message chat call. Think mode
    defaults to OFF because generate() is typically used for focused
    prompt-completion work (code gen, classification, summarization)
    where a scratchpad isn't needed.

    Raises BackendError on failure.

    2026-04-23 Commit 6: default model parameter now falls back to
    `core.model_config.PRIMARY_MODEL` when None is passed, instead
    of a hardcoded 'gemma4:26b'. Callers that want a specific model
    still pass model= explicitly.
    """
    if model is None:
        model = _PRIMARY_MODEL
    backend = active_backend()

    if backend == BACKEND_OLLAMA:
        # Use ollama.generate() directly — it's the native shape for
        # this path and preserves exactly what the old raw requests.post
        # callers expected.
        try:
            import ollama
            client = ollama.Client(timeout=timeout_s)
            resp = client.generate(
                model=model,
                prompt=prompt,
                options={'temperature': temperature, 'num_predict': max_tokens},
                stream=False,
            )
            # ollama.generate returns an object with .response OR a dict
            # with 'response' key depending on client version. Try both.
            text = getattr(resp, 'response', None)
            if text is None and isinstance(resp, dict):
                text = resp.get('response', '')
            return text or ''
        except Exception as e:
            raise BackendError(f'ollama generate failed: {e!r}') from e

    # llamacpp path: wrap as a single-user-message chat call
    try:
        chat_resp = _chat_llamacpp(
            model=model,
            messages=[{'role': 'user', 'content': prompt}],
            stream=False,
            think=think,
            options={'temperature': temperature, 'num_predict': max_tokens},
            timeout_s=timeout_s,
        )
        return (chat_resp.message.content or '') if hasattr(chat_resp, 'message') else ''
    except BackendError:
        raise
    except Exception as e:
        raise BackendError(f'llamacpp generate failed: {e!r}') from e


# ── self-test ────────────────────────────────────────────────────────
if __name__ == '__main__':
    # Minimal end-to-end check. Run directly:
    #   python -m core.llm_client
    # Verifies both backends by flipping the env var in-process.
    msgs = [{'role': 'user', 'content': 'Say hi in one short sentence.'}]

    print('backend=ollama path (control)')
    os.environ['MAEZ_LLM_BACKEND'] = 'ollama'
    t0 = time.perf_counter()
    try:
        r = chat(model='gemma4:26b', messages=msgs, think=False,
                 options={'temperature': 0.3, 'num_predict': 32})
        dt = time.perf_counter() - t0
        content = r.message.content if hasattr(r, 'message') else str(r)
        print(f'  {dt:.2f}s  reply: {content[:120]!r}')
    except BackendError as e:
        print(f'  FAILED: {e}')

    print('backend=llamacpp path (test)')
    os.environ['MAEZ_LLM_BACKEND'] = 'llamacpp'
    t0 = time.perf_counter()
    try:
        r = chat(model='ignored', messages=msgs,
                 options={'temperature': 0.3, 'num_predict': 32})
        dt = time.perf_counter() - t0
        content = r.message.content if hasattr(r, 'message') else str(r)
        print(f'  {dt:.2f}s  reply: {content[:120]!r}')
    except BackendError as e:
        print(f'  FAILED: {e}')

    print('sanitizer unit checks')
    raw = 'hello <|channel|> world <end_of_turn> <bos>'
    cleaned = _strip_special_tokens(raw)
    assert '<|channel|>' not in cleaned and '<end_of_turn>' not in cleaned and '<bos>' not in cleaned
    sanitized = _sanitize_messages_for_llamacpp([
        {'role': 'system', 'content': 'safe'},
        {'role': 'user', 'content': raw},
    ])
    assert sanitized[1]['content'] == cleaned
    assert sanitized[0]['content'] == 'safe'

    # Regression: Gemma-native tool-call delimiters must survive the
    # sanitizer intact. The regex must NOT greedy-match across the
    # asymmetric `<|tool_call>...<tool_call|>` envelope and delete the
    # JSON body. Previous regex `<\|[^|]*\|>` had this bug and silently
    # destroyed the LoRA's primary trained tool-call format.
    toolcall = '<|tool_call>call:maez.run_shell{"cmd":"ls"}<tool_call|>'
    assert _strip_special_tokens(toolcall) == toolcall, (
        f'Gemma-native tool call was destroyed by sanitizer: {_strip_special_tokens(toolcall)!r}'
    )
    assert _strip_special_tokens('<|tool_call>') == '<|tool_call>'
    assert _strip_special_tokens('<tool_call|>') == '<tool_call|>'
    # And the chat-template tokens still get stripped
    assert _strip_special_tokens('<|im_start|>') == ''
    assert _strip_special_tokens('<|im_end|>') == ''
    assert _strip_special_tokens('<|end_of_text|>') == ''

    # Framing-token stripping: Maez's recall envelope must never survive
    # inside stored content, or a future recall wraps a tag-within-a-tag.
    assert _strip_framing_tokens('<RECALLED tier="raw" age="2h">x</RECALLED>') == 'x'
    assert _strip_framing_tokens('</RECALLED>leak') == 'leak'
    assert _strip_framing_tokens(
        '=== PAST OBSERVATIONS — NOT CURRENT STATE ===\nbody'
    ).strip() == 'body'
    assert _strip_framing_tokens('=== END PAST OBSERVATIONS ===\nbody').strip() == 'body'
    # Does not eat unrelated angle-bracket content
    assert _strip_framing_tokens('<div>keep</div>') == '<div>keep</div>'
    # sanitize_prompt_text composes both strippers
    assert sanitize_prompt_text(
        '<RECALLED tier="x">hi <|im_end|></RECALLED>'
    ).strip() == 'hi'
    print('  sanitizer OK')
