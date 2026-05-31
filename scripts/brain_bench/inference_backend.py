from __future__ import annotations

import json
from typing import Iterator

import requests

from scripts.brain_bench.variants import Variant


def ollama_stream(*, variant: Variant, payload: dict) -> Iterator[dict[str, str]]:
    response = requests.post(
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
