"""Live Brain Gateway forced-collision probe.

Owner-run diagnostic for the socket-level cancellable transport. It does not
flip recall, touch daemon posture, or persist model output. It creates a fresh
process-local BrainGateway, starts a background llama.cpp call through the real
socket transport, then submits a foreground OWNER_RECALL call through the same
gateway and reports content-free timing/telemetry.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from core.routing import llm_client
from core.routing import brain_gateway
from core.routing.brain_gateway import BrainGateway, BrainPurpose
from core.routing.cancellable_brain_call import BrainPreempted


FILLER = "The history of computing is long and detailed. " * 1800
DEFAULT_SLOT_RELEASE_THRESHOLD_MS = 1500.0


def _messages(content: str) -> list[dict[str, str]]:
    return [{"role": "user", "content": content}]


def _start_chat(content: str, *, max_tokens: int):
    return llm_client.start_cancellable_chat(
        model=llm_client.LLAMACPP_MODEL,
        messages=_messages(content),
        think=False,
        options={"temperature": 0.0, "num_predict": max_tokens},
    )


def _wait_for_inflight_handle(gateway: BrainGateway, timeout_s: float) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        with gateway._condition:  # noqa: SLF001 - diagnostic probe, not library API
            record = gateway._in_flight  # noqa: SLF001
            if record is not None and record.call is not None:
                return True
        time.sleep(0.01)
    return False


def summarize_events(
    events: list[dict[str, Any]],
    *,
    foreground_wall_ms: float,
    threshold_ms: float = DEFAULT_SLOT_RELEASE_THRESHOLD_MS,
) -> dict[str, Any]:
    probes = [e for e in events if e.get("event") == "brain_gateway_preempt_probe"]
    gateway_events = [e for e in events if e.get("event") == "brain_gateway_event"]
    owner_events = [e for e in gateway_events if e.get("purpose") == "owner_recall"]

    owner_wait_ms = None
    if owner_events:
        owner_wait_ms = owner_events[-1].get("wait_ms")

    handle_present = any(p.get("handle_state") == "present" for p in probes)
    background_preempted = any(
        e.get("purpose") == "daemon_cycle_generation" and e.get("preempted")
        for e in gateway_events
    )
    preempt_timeout = any(bool(e.get("preempt_timeout")) for e in gateway_events)
    slot_release_pass = (
        handle_present
        and background_preempted
        and not preempt_timeout
        and isinstance(owner_wait_ms, int | float)
        and owner_wait_ms <= threshold_ms
    )
    return {
        "schema_version": 1,
        "handle_present": handle_present,
        "background_preempted": background_preempted,
        "preempt_timeout": preempt_timeout,
        "owner_wait_ms": owner_wait_ms,
        "foreground_wall_ms": round(foreground_wall_ms, 3),
        "threshold_ms": threshold_ms,
        "slot_release_pass": slot_release_pass,
    }


def run_probe(
    *,
    background_warmup_s: float = 0.25,
    handle_timeout_s: float = 5.0,
    threshold_ms: float = DEFAULT_SLOT_RELEASE_THRESHOLD_MS,
) -> dict[str, Any]:
    os.environ["MAEZ_LLM_BACKEND"] = llm_client.BACKEND_LLAMACPP
    gateway = BrainGateway(preempt_timeout_s=threshold_ms / 1000.0)
    bg_outcome: dict[str, Any] = {}

    def run_background() -> None:
        try:
            reply = gateway.submit(
                purpose=BrainPurpose.DAEMON_CYCLE_GENERATION,
                run_streaming_fn=lambda: _start_chat(FILLER, max_tokens=8),
            )
            bg_outcome["completed"] = True
            bg_outcome["reply_len"] = len(reply or "")
        except BrainPreempted:
            bg_outcome["preempted"] = True
        except Exception as exc:  # noqa: BLE001 - probe reports backend failures
            bg_outcome["error"] = repr(exc)

    worker = threading.Thread(target=run_background, name="probe-background")
    worker.start()
    handle_ready = _wait_for_inflight_handle(gateway, timeout_s=handle_timeout_s)
    if background_warmup_s > 0:
        time.sleep(background_warmup_s)

    t0 = time.monotonic()
    fg_error = None
    foreground_reply_len = 0
    try:
        reply = gateway.submit(
            purpose=BrainPurpose.OWNER_RECALL,
            run_streaming_fn=lambda: _start_chat("Reply with OK.", max_tokens=4),
        )
        foreground_reply_len = len(reply or "")
    except Exception as exc:  # noqa: BLE001 - probe reports backend failures
        fg_error = repr(exc)
    foreground_wall_ms = (time.monotonic() - t0) * 1000.0
    worker.join(timeout=10.0)

    events = [dict(event) for event in gateway.events]
    summary = summarize_events(
        events,
        foreground_wall_ms=foreground_wall_ms,
        threshold_ms=threshold_ms,
    )
    summary.update(
        {
            "handle_ready_before_foreground": handle_ready,
            "background_thread_alive": worker.is_alive(),
            "background_outcome": bg_outcome,
            "foreground_error": fg_error,
            "foreground_reply_len": foreground_reply_len,
            "runtime_paths": {
                "repo_root": str(_REPO_ROOT),
                "brain_gateway": str(Path(brain_gateway.__file__).resolve()),
                "llm_client": str(Path(llm_client.__file__).resolve()),
            },
            "events": events,
        }
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--background-warmup-s", type=float, default=0.25)
    parser.add_argument("--handle-timeout-s", type=float, default=5.0)
    parser.add_argument("--threshold-ms", type=float, default=DEFAULT_SLOT_RELEASE_THRESHOLD_MS)
    args = parser.parse_args()

    result = run_probe(
        background_warmup_s=args.background_warmup_s,
        handle_timeout_s=args.handle_timeout_s,
        threshold_ms=args.threshold_ms,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("slot_release_pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
