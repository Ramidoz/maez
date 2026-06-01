from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from scripts.brain_bench.inference import make_benchmark_chat_fn


def _fab_working_set_text(ws_items: int) -> str:
    return "\n".join(
        f"[E{index + 1}] fabricated evidence line {index + 1}"
        for index in range(ws_items)
    )


def _ask_for_mode(mode: str) -> str:
    if mode == "short":
        return "Answer in one short sentence."
    if mode == "long":
        return "Answer in full detail."
    return f"Answer in {mode} mode."


def run_sweep(
    *,
    ws_item_counts: Iterable[int],
    output_modes: Iterable[str],
    variant,
    stream_factory=None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for ws_items in ws_item_counts:
        evidence = _fab_working_set_text(ws_items)
        for mode in output_modes:
            chat_fn, sink = make_benchmark_chat_fn(
                variant=variant,
                stream_factory=stream_factory,
            )
            messages = [
                {
                    "role": "system",
                    "content": f"=== EVIDENCE ===\n{evidence}\n{_ask_for_mode(mode)}",
                },
                {"role": "user", "content": "what did we note?"},
            ]
            chat_fn(
                model=variant.model,
                messages=messages,
                think=False,
                options={"num_predict": 4096},
            )
            measurement = sink.last()
            rows.append(
                {
                    "ws_items": ws_items,
                    "input_tokens": len(evidence) // 4,
                    "output_tokens": measurement.output_tokens,
                    "ttft_ms": measurement.ttft_ms,
                    "total_ms": measurement.total_ms,
                    "tok_s": measurement.tokens_per_sec,
                }
            )
    return rows
