from __future__ import annotations

import json
from typing import Iterator

import requests

from scripts.brain_bench.variants import BackendFamily, Variant


def stream_variant(*, variant: Variant, payload: dict) -> Iterator[dict[str, str]]:
    if variant.backend_family is BackendFamily.OPENAI_COMPATIBLE:
        yield from openai_compat_stream(variant=variant, payload=payload)
        return
    yield from ollama_stream(variant=variant, payload=payload)


def ollama_stream(*, variant: Variant, payload: dict) -> Iterator[dict[str, str]]:
    session = requests.Session()
    session.trust_env = False
    response = session.post(
        f"{variant.base_url.rstrip('/')}/api/chat",
        json=payload,
        stream=True,
        timeout=120,
    )
    response.raise_for_status()
    for line in response.iter_lines():
        if not line:
            continue
        data = json.loads(line.decode("utf-8") if isinstance(line, bytes) else line)
        content = ((data.get("message") or {}).get("content")) or data.get("response") or ""
        yield {"content": content}


def openai_compat_stream(*, variant: Variant, payload: dict) -> Iterator[dict[str, str]]:
    session = requests.Session()
    session.trust_env = False
    response = session.post(
        f"{variant.base_url.rstrip('/')}/v1/chat/completions",
        json=_openai_payload(variant=variant, payload=payload),
        stream=True,
        timeout=120,
    )
    response.raise_for_status()
    for line in response.iter_lines():
        data = _decode_openai_stream_line(line)
        if data is None:
            continue
        content = _openai_content(data)
        yield {"content": content}


def _openai_payload(*, variant: Variant, payload: dict) -> dict:
    options = dict(payload.get("options") or {})
    body: dict = {
        "model": variant.model,
        "messages": payload.get("messages") or [],
        "stream": True,
        "temperature": float(options.get("temperature", 0.7)),
        "max_tokens": int(options.get("num_predict", options.get("max_tokens", 512))),
    }
    extra_body = dict(options.get("extra_body") or {})
    chat_template_kwargs = dict(
        options.get("chat_template_kwargs")
        or extra_body.get("chat_template_kwargs")
        or {}
    )
    if payload.get("think") is not None:
        chat_template_kwargs["enable_thinking"] = bool(payload["think"])
    if chat_template_kwargs:
        body["chat_template_kwargs"] = chat_template_kwargs
    return body


def _decode_openai_stream_line(line) -> dict | None:
    if not line:
        return None
    text = line.decode("utf-8") if isinstance(line, bytes) else str(line)
    text = text.strip()
    if not text:
        return None
    if text.startswith("data:"):
        text = text.removeprefix("data:").strip()
    if text == "[DONE]":
        return None
    return json.loads(text)


def _openai_content(data: dict) -> str:
    choices = data.get("choices") or ()
    if not choices:
        return ""
    first = choices[0] or {}
    delta = first.get("delta") or {}
    message = first.get("message") or {}
    return delta.get("content") or message.get("content") or ""
