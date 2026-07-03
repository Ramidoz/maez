"""Out-of-band A2 probe sampler.

Runs the private continuity battery through the minimal probe envelope and
writes only to the A2 store.
"""

from __future__ import annotations

from math import sqrt
from typing import Any

from core.infra.env_flags import strict_env_flag
from core.model_config import PRIMARY_MODEL

from .envelope import build_probe_envelope
from .meter import aggregate_drift
from .probes import BATTERY, BATTERY_VERSION
from .store import ContinuityStore


SHORT_ANCHOR_RUNS = 3
MID_ANCHOR_RUNS = 12
LONG_ANCHOR_RUNS = 50


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


def _cosine_distance(left: list[float], right: list[float]) -> float | None:
    dot = sum(float(a) * float(b) for a, b in zip(left, right, strict=False))
    left_norm = sqrt(sum(float(a) * float(a) for a in left))
    right_norm = sqrt(sum(float(b) * float(b) for b in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return None
    return 1.0 - (dot / (left_norm * right_norm))


def _prior_answers_by_question(
    store: ContinuityStore,
    *,
    era: str,
) -> dict[str, list[str]]:
    prior: dict[str, list[str]] = {}
    for run in store.list_runs():
        if run.get("era") != era:
            continue
        for answer in store.answers_for(str(run["run_id"])):
            prior.setdefault(str(answer["question_id"]), []).append(
                str(answer["answer_text"])
            )
    return prior


def _anchor_distance(
    *,
    current_vector: list[float],
    prior_texts: list[str],
    encoder: Any,
    limit: int,
) -> float | None:
    if not prior_texts:
        return None
    distances = [
        _cosine_distance(current_vector, encoder.encode(text))
        for text in prior_texts[-limit:]
    ]
    return aggregate_drift(distances)


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
    embedder_id = _embedder_id(encoder)
    era = f"{BATTERY_VERSION}|{embedder_id}"
    prior_answers = _prior_answers_by_question(store, era=era)
    envelope, snapshot = build_probe_envelope()

    answers: list[dict[str, Any]] = []
    for probe in BATTERY:
        messages = [
            {"role": "system", "content": envelope},
            {"role": "user", "content": probe.text},
        ]
        response = chat_fn(messages=messages)
        answer_text = _response_text(response)
        # Measurement vectors are intentionally transient: compute distances to
        # prior answer text, then discard. Only scalar distances are persisted.
        current_vector = encoder.encode(answer_text)
        prior_texts = prior_answers.get(probe.id, [])
        answers.append(
            {
                "question_id": probe.id,
                "answer_text": answer_text,
                "dist_short": _anchor_distance(
                    current_vector=current_vector,
                    prior_texts=prior_texts,
                    encoder=encoder,
                    limit=SHORT_ANCHOR_RUNS,
                ),
                "dist_mid": _anchor_distance(
                    current_vector=current_vector,
                    prior_texts=prior_texts,
                    encoder=encoder,
                    limit=MID_ANCHOR_RUNS,
                ),
                "dist_long": _anchor_distance(
                    current_vector=current_vector,
                    prior_texts=prior_texts,
                    encoder=encoder,
                    limit=LONG_ANCHOR_RUNS,
                ),
            }
        )

    run_id = store.record_run(
        snapshot=snapshot,
        embedder_id=embedder_id,
        battery_version=BATTERY_VERSION,
        answers=answers,
    )
    return {"status": "recorded", "run_id": run_id, "answers": len(answers)}
