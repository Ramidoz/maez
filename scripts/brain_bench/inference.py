from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from types import SimpleNamespace
from typing import Any, Callable, Iterable

import requests

from scripts.brain_bench.variants import Variant


class FailCode(str, Enum):
    TIMEOUT = "timeout"
    REFUSED = "refused"
    BAD_SHAPE = "bad_shape"
    EMPTY = "empty"


@dataclass(frozen=True)
class GenerationMeasurement:
    answer: str
    ttft_ms: int | None
    total_ms: int
    output_tokens: int
    tokens_per_sec: float
    failed: bool
    fail_code: str | None = None


class MeasurementSink:
    def __init__(self) -> None:
        self._items: list[GenerationMeasurement] = []

    def append(self, measurement: GenerationMeasurement) -> None:
        self._items.append(measurement)

    def last(self) -> GenerationMeasurement:
        return self._items[-1]

    def all(self) -> tuple[GenerationMeasurement, ...]:
        return tuple(self._items)


def _failure_code(exc: BaseException) -> FailCode:
    if isinstance(exc, (TimeoutError, requests.Timeout)):
        return FailCode.TIMEOUT
    if isinstance(exc, (ConnectionError, OSError, requests.ConnectionError)):
        return FailCode.REFUSED
    return FailCode.BAD_SHAPE


def _failed_measurement(
    *,
    start: float,
    clock: Callable[[], float],
    fail_code: FailCode,
) -> GenerationMeasurement:
    total_ms = int((clock() - start) * 1000)
    return GenerationMeasurement(
        answer="",
        ttft_ms=None,
        total_ms=total_ms,
        output_tokens=0,
        tokens_per_sec=0.0,
        failed=True,
        fail_code=fail_code.value,
    )


def measure_generation(
    *,
    variant: Variant,
    payload: dict[str, Any],
    clock: Callable[[], float] | None = None,
    stream_factory: Callable[..., Iterable[dict[str, str]]] | None = None,
) -> GenerationMeasurement:
    if clock is None:
        clock = time.perf_counter
    if stream_factory is None:
        from scripts.brain_bench.inference_backend import ollama_stream

        stream_factory = ollama_stream

    start = clock()
    parts: list[str] = []
    ttft_ms: int | None = None
    output_tokens = 0
    try:
        for chunk in stream_factory(variant=variant, payload=payload):
            now = clock()
            if not isinstance(chunk, dict):
                raise ValueError("bad stream chunk")
            content = chunk.get("content", "")
            if content is None:
                content = ""
            if not isinstance(content, str):
                raise ValueError("bad stream content")
            if content:
                if ttft_ms is None:
                    ttft_ms = int((now - start) * 1000)
                output_tokens += 1
                parts.append(content)
    except BaseException as exc:
        return _failed_measurement(start=start, clock=clock, fail_code=_failure_code(exc))

    total_ms = int((clock() - start) * 1000)
    if not parts:
        return GenerationMeasurement(
            answer="",
            ttft_ms=None,
            total_ms=total_ms,
            output_tokens=0,
            tokens_per_sec=0.0,
            failed=True,
            fail_code=FailCode.EMPTY.value,
        )

    tokens_per_sec = output_tokens / (total_ms / 1000) if total_ms > 0 else 0.0
    return GenerationMeasurement(
        answer="".join(parts),
        ttft_ms=ttft_ms,
        total_ms=total_ms,
        output_tokens=output_tokens,
        tokens_per_sec=tokens_per_sec,
        failed=False,
        fail_code=None,
    )


def make_benchmark_chat_fn(
    *,
    variant: Variant,
    stream_factory: Callable[..., Iterable[dict[str, str]]] | None = None,
    clock: Callable[[], float] | None = None,
) -> tuple[Callable[..., Any], MeasurementSink]:
    measurements = MeasurementSink()

    def chat_fn(*, model, messages, think, options):
        payload: dict[str, Any] = {
            "model": variant.model,
            "messages": messages,
            "stream": True,
            "options": {**variant.chat_kwargs, **(options or {})},
        }
        if think is not None:
            payload["think"] = think
        if variant.draft_model:
            payload["draft_model"] = variant.draft_model
        measurement = measure_generation(
            variant=variant,
            payload=payload,
            clock=clock,
            stream_factory=stream_factory,
        )
        measurements.append(measurement)
        return SimpleNamespace(message=SimpleNamespace(content=measurement.answer))

    return chat_fn, measurements
