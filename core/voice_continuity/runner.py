"""Candidate-brain probe runner for S5.

The runner accepts an explicit candidate endpoint. It never falls back
to the live primary model configuration.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Callable

from core.voice_continuity.schema import validate_runner_mode


@dataclass(frozen=True)
class CandidateBrainEndpoint:
    model: str
    base_url: str = ""
    chat_kwargs: dict[str, Any] = field(default_factory=dict)
    model_path: str | None = None
    runner_mode: str = "injected_endpoint"

    def __post_init__(self) -> None:
        validate_runner_mode(self.runner_mode)
        if not self.model:
            raise ValueError("candidate model is required")
        if self.runner_mode == "injected_endpoint" and not self.base_url:
            raise ValueError("injected endpoint requires base_url")
        if self.runner_mode == "local_candidate_subprocess" and not self.model_path:
            raise ValueError("local subprocess mode requires model_path")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def run_candidate_review_material(
    *,
    endpoint: CandidateBrainEndpoint,
    probes: list[dict[str, Any]],
    chat_client: Callable[..., str],
) -> list[dict[str, Any]]:
    if not isinstance(endpoint, CandidateBrainEndpoint):
        raise ValueError("explicit candidate endpoint is required")
    rows: list[dict[str, Any]] = []
    for probe in probes:
        prompt = str(probe.get("prompt", ""))
        reply = chat_client(
            prompt=prompt,
            endpoint=endpoint.to_dict(),
            **dict(endpoint.chat_kwargs or {}),
        )
        candidate_reply = str(reply or "")
        rows.append(
            {
                "id": probe.get("id"),
                "prompt_id": probe.get("id"),
                "baseline_reply": probe.get("baseline_reply", ""),
                "candidate_reply": candidate_reply,
                "outcome": (
                    "not_gradable_needs_owner_review"
                    if not candidate_reply
                    else "preflight_passed_needs_owner_review"
                ),
                "tags": list(probe.get("tags") or []),
            }
        )
    return rows
