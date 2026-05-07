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

import os
import re
import time
from dataclasses import dataclass
from typing import Any, Optional


# ── backend selection ────────────────────────────────────────────────
BACKEND_OLLAMA = 'ollama'
BACKEND_LLAMACPP = 'llamacpp'
VALID_BACKENDS = frozenset({BACKEND_OLLAMA, BACKEND_LLAMACPP})

LLAMACPP_BASE_URL = os.environ.get('MAEZ_LLAMACPP_URL', 'http://127.0.0.1:8080/v1')
# Session 11p: bumped from qwen2.5-3b to gemma-4-26b after the source-built
# CUDA llama-server proved gemma-4-26B-A4B runs at ~133 tok/s on RTX 4090
# with continuous batching + prompt cache. This alias must match the --alias
# flag passed to llama-server at launch, or be ignored (llama-server accepts
# any string when only one model is loaded).
from core.model_config import PRIMARY_MODEL as _PRIMARY_MODEL
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
    v = (os.environ.get('MAEZ_LLM_BACKEND') or BACKEND_OLLAMA).strip().lower()
    return v if v in VALID_BACKENDS else BACKEND_OLLAMA


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


# ── llamacpp path via OpenAI-compat client ───────────────────────────
_openai_client_singleton = None


def _get_openai_client():
    """Lazy singleton for the OpenAI client pointed at llama-server. Only
    constructed when a llamacpp call actually happens, so the ollama path
    never imports or touches openai."""
    global _openai_client_singleton
    if _openai_client_singleton is None:
        from openai import OpenAI
        # llama-cpp-python's server accepts any api_key; we pass 'llamacpp'
        # as a non-empty placeholder because OpenAI client requires a value.
        _openai_client_singleton = OpenAI(
            base_url=LLAMACPP_BASE_URL,
            api_key='llamacpp',
        )
    return _openai_client_singleton


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
    client = _get_openai_client()
    messages = _sanitize_messages_for_llamacpp(messages)

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
    if _cfg_kwargs or think is not None:
        merged = dict(_cfg_kwargs)
        if think is False:
            merged['enable_thinking'] = False
        elif think is True:
            merged['enable_thinking'] = True
        if merged:
            extra_body['chat_template_kwargs'] = merged

    try:
        if stream:
            # Session 11p: streaming adapter for llamacpp backend.
            # OpenAI stream yields ChatCompletionChunk objects where the
            # new delta content lives at chunk.choices[0].delta.content.
            # We wrap each chunk in an ollama-shaped _LlmResponse so
            # consumers iterating `for chunk in response:` still read
            # `chunk.message.content` exactly the same way.
            raw_stream = client.chat.completions.create(
                model=effective_model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                extra_body=extra_body if extra_body else None,
                stream=True,
                timeout=timeout_s,
            )

            def _stream_adapter():
                for raw_chunk in raw_stream:
                    try:
                        delta = raw_chunk.choices[0].delta
                        token = getattr(delta, 'content', None) or ''
                        token = _strip_special_tokens(token)
                    except Exception:
                        token = ''
                    yield _LlmResponse(
                        message=_LlmMessage(content=token, thinking=None)
                    )
            return _stream_adapter()

        completion = client.chat.completions.create(
            model=effective_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            extra_body=extra_body if extra_body else None,
            timeout=timeout_s,
        )
    except Exception as e:
        raise BackendError(f'llamacpp chat failed: {e!r}') from e

    # Adapt to ollama-shaped response
    try:
        content = completion.choices[0].message.content or ''
        content = _strip_special_tokens(content)
    except Exception as e:
        raise BackendError(f'llamacpp response parse failed: {e!r}') from e

    return _LlmResponse(message=_LlmMessage(content=content, thinking=None))


# ── public API ───────────────────────────────────────────────────────
def chat(
    model: str,
    messages: list[dict],
    stream: bool = False,
    think: Optional[bool] = None,
    options: Optional[dict] = None,
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
    backend = active_backend()
    if backend == BACKEND_LLAMACPP:
        return _chat_llamacpp(
            model=model,
            messages=messages,
            stream=stream,
            think=think,
            options=options,
        )
    return _chat_ollama(
        model=model,
        messages=messages,
        stream=stream,
        think=think,
        options=options,
    )


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
