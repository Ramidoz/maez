"""Out-of-band A2 probe sampler.

Runs the private continuity battery through the minimal probe envelope and
writes only to the A2 store.
"""

from __future__ import annotations

from typing import Any

from core.infra.env_flags import strict_env_flag
from core.model_config import PRIMARY_MODEL

from .envelope import build_probe_envelope
from .probes import BATTERY, BATTERY_VERSION
from .store import ContinuityStore


def _enabled() -> bool:
    return strict_env_flag("MAEZ_CONTINUITY_FINGERPRINT")


def _embedder_id(encoder: Any) -> str:
    return f"{getattr(encoder, 'model', 'unknown')}:{getattr(encoder, 'dimension', 'unknown')}"


def _default_encoder():
    from memory.embedder import get_encoder

    return get_encoder()


def _default_chat_fn(**kwargs):
    from core.routing import llm_client
    from core.routing.brain_gateway import BrainPurpose

    return llm_client.chat(
        model=PRIMARY_MODEL,
        messages=kwargs["messages"],
        think=False,
        options=kwargs.get("options"),
        purpose=BrainPurpose.NEUTRAL,
    )


def _response_text(response: Any) -> str:
    if isinstance(response, str):
        return response
    message = getattr(response, "message", None)
    if message is not None and hasattr(message, "content"):
        return str(message.content or "")
    if isinstance(response, dict):
        try:
            return str(response["message"]["content"] or "")
        except Exception:
            return str(response.get("content") or "")
    return str(response or "")


def run_probe_battery(
    *,
    chat_fn=None,
    encoder=None,
    store: ContinuityStore | None = None,
) -> dict[str, Any]:
    """Run one private A2 battery sample if the feature flag is enabled."""

    if not _enabled():
        return {"status": "disabled"}

    chat_fn = chat_fn or _default_chat_fn
    encoder = encoder or _default_encoder()
    store = store or ContinuityStore()
    envelope, snapshot = build_probe_envelope()

    answers: list[dict[str, Any]] = []
    for probe in BATTERY:
        messages = [
            {"role": "system", "content": envelope},
            {"role": "user", "content": probe.text},
        ]
        response = chat_fn(messages=messages)
        answer_text = _response_text(response)
        # Measurement vector is intentionally transient: compute, validate the
        # instrument, then discard. Distances are absent until anchors exist.
        encoder.encode(answer_text)
        answers.append(
            {
                "question_id": probe.id,
                "answer_text": answer_text,
                "dist_short": None,
                "dist_mid": None,
                "dist_long": None,
            }
        )

    run_id = store.record_run(
        snapshot=snapshot,
        embedder_id=_embedder_id(encoder),
        battery_version=BATTERY_VERSION,
        answers=answers,
    )
    return {"status": "recorded", "run_id": run_id, "answers": len(answers)}

