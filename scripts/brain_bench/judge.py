from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Callable


@dataclass(frozen=True)
class BlindAnswer:
    probe_id: str
    sample_id: str
    answer: str
    evidence: str


@dataclass(frozen=True)
class JudgeResult:
    quality_winrate: dict[str, float]
    voice_winrate: dict[str, float]
    quality_games: int
    voice_games: int
    invalid_verdicts: int


def _prompt(axis: str, first: BlindAnswer, second: BlindAnswer) -> str:
    return (
        f"Axis: {axis}\n"
        f"Probe: {first.probe_id}\n"
        "Choose A, B, TIE, or INVALID.\n\n"
        f"A answer:\n{first.answer}\n\nA evidence:\n{first.evidence}\n\n"
        f"B answer:\n{second.answer}\n\nB evidence:\n{second.evidence}\n"
    )


def _group_answers(
    answers_by_variant: dict[str, tuple[BlindAnswer, ...]]
) -> dict[tuple[str, str], dict[str, BlindAnswer]]:
    grouped: dict[tuple[str, str], dict[str, BlindAnswer]] = {}
    for label, answers in answers_by_variant.items():
        for answer in answers:
            grouped.setdefault((answer.probe_id, answer.sample_id), {})[label] = answer
    return grouped


def judge_pairwise(
    answers_by_variant: dict[str, tuple[BlindAnswer, ...]],
    *,
    call_judge: Callable[..., str],
    seed: int,
) -> JudgeResult:
    labels = sorted(answers_by_variant)
    wins = {
        "quality": {label: 0 for label in labels},
        "voice": {label: 0 for label in labels},
    }
    denominators = {
        "quality": {label: 0 for label in labels},
        "voice": {label: 0 for label in labels},
    }
    games = {"quality": 0, "voice": 0}
    invalid = 0
    grouped = _group_answers(answers_by_variant)

    for _group_key in sorted(grouped):
        by_label = grouped[_group_key]
        for left_label, right_label in combinations(labels, 2):
            if left_label not in by_label or right_label not in by_label:
                continue
            left = by_label[left_label]
            right = by_label[right_label]
            for axis in ("quality", "voice"):
                for first_label, first, second_label, second in (
                    (left_label, left, right_label, right),
                    (right_label, right, left_label, left),
                ):
                    verdict = str(
                        call_judge(
                            axis=axis,
                            first=first,
                            second=second,
                            prompt=_prompt(axis, first, second),
                        )
                    ).upper()
                    games[axis] += 1
                    denominators[axis][first_label] += 1
                    denominators[axis][second_label] += 1
                    if verdict == "A":
                        wins[axis][first_label] += 1
                    elif verdict == "B":
                        wins[axis][second_label] += 1
                    elif verdict == "INVALID":
                        invalid += 1
                    elif verdict != "TIE":
                        invalid += 1

    quality_winrate = {
        label: (
            wins["quality"][label] / denominators["quality"][label]
            if denominators["quality"][label]
            else 0.0
        )
        for label in labels
    }
    voice_winrate = {
        label: (
            wins["voice"][label] / denominators["voice"][label]
            if denominators["voice"][label]
            else 0.0
        )
        for label in labels
    }
    return JudgeResult(
        quality_winrate=quality_winrate,
        voice_winrate=voice_winrate,
        quality_games=games["quality"],
        voice_games=games["voice"],
        invalid_verdicts=invalid,
    )
