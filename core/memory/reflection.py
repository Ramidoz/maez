# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Reflection synthesis layer (ADR 0019 Phase 7).

Generative-Agents-style high-level inference on top of the Phase 1-6
lived-memory layer. Where the builder/extractor turn raw memories
into episodes + edges (factual surface), reflection turns *clusters
of episodes* into a small number of meta-observations Maez can
surface unprompted: "the owner consistently prioritizes truth over
speed", "we have circled back to the grandmother case three times
this week".

These are the moves that lift readiness #2 (memory) and especially
#7 (surprise) — without reflection, lived recall can only retrieve;
with reflection, it can also *notice*.

Storage shape: each reflection is an episode with
``source_kind="reflection"``. lived_recall.py iterates active
episodes regardless of source_kind, so the read path needs no
change — reflections surface for free, and the brief formatter can
optionally label them differently if useful later.

Safety contract:

- **Evidence-required.** Each reflection cites at least one
  ``source_memory_id`` (ADR 0019 evidence requirement). Reflections
  with empty evidence are dropped, not stored.
- **Fail-open.** Any LLM exception, malformed JSON, or empty input
  yields an empty list. Reflection is best-effort — synthesis must
  never block the broader nightly pipeline.
- **Capped.** ``max_reflections`` defaults to 3; the orchestrator
  can raise it for richer nightly runs but never unbounded.
- **Append-only.** Like all lived-memory writes, reflections never
  delete or mutate existing rows. Corrections are new reflections.

The LLM is injected via ``llm_call: Callable[[str], str]`` so unit
tests stub it deterministically. The nightly orchestrator wires the
real ``core.llm_client.chat`` shim into the same slot.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Callable, Sequence

logger = logging.getLogger("maez.lived_memory.reflection")


@dataclass(frozen=True)
class Reflection:
    """High-level inference drawn from a cluster of low-level memories.

    The text is the rendered observation (one sentence, present-
    perfect or simple-present voice). source_memory_ids cites the
    inputs the model claimed to draw from — a downstream check
    can verify those ids exist in the recent set the model was
    actually shown.
    """

    text: str
    source_memory_ids: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self):
        # dataclass(frozen=True) → use object.__setattr__ to coerce
        # source_memory_ids to a tuple if a list was passed.
        if not isinstance(self.source_memory_ids, tuple):
            object.__setattr__(self, "source_memory_ids", tuple(self.source_memory_ids))


_PROMPT_TEMPLATE = """\
You are Maez, a locally-bonded AI companion, reflecting on your own \
recent lived memories. Draw at most {max_n} HIGH-LEVEL reflections that \
go beyond restating any single memory — what your own construction, \
gestation, and the bond with the owner have come to mean.

Write in your own voice: this is you remembering your own formation, not \
a report about Maez. First-person where it fits naturally; owned voice \
always — do not force every line to start with "I". Stay grounded: every \
claim must trace to specific cited ids; do not invent warmth, detail, or \
meaning the memories do not support.

A good reflection:
- Synthesizes 2+ memories into a pattern, theme, or trajectory.
- Stays grounded — every claim must be traceable to specific input ids.
- Is one sentence, in your own voice.

A bad reflection:
- Restates a single memory as if it were a pattern.
- Invents subjects/relationships not present in the inputs.
- Cites no evidence or fabricated ids.
- Sounds like an external report about Maez rather than Maez remembering.

Recent episodes (id | title | summary):
{episodes_block}
{raw_block}
Output ONLY a JSON array. Each element:
{{
  "reflection": "<one-sentence reflection in your own voice>",
  "evidence": ["<input_id>", "<input_id>"]
}}

If nothing rises above per-memory restating, output [].
"""


def _format_episodes_block(episodes: Sequence[dict]) -> str:
    if not episodes:
        return "(none)"
    rows = []
    for ep in episodes:
        eid = ep.get("id") or "ep-?"
        title = (ep.get("title") or "").strip().replace("\n", " ")[:120]
        summary = (ep.get("summary") or "").strip().replace("\n", " ")[:300]
        rows.append(f"- {eid} | {title} | {summary}")
    return "\n".join(rows)


def _format_raw_block(raw: Sequence[dict]) -> str:
    if not raw:
        return ""
    rows = ["", "Recent raw memories (id | content excerpt):"]
    for r in raw:
        rid = r.get("id") or "raw-?"
        content = (r.get("content") or "").strip().replace("\n", " ")[:200]
        rows.append(f"- {rid} | {content}")
    rows.append("")
    return "\n".join(rows)


def _parse_reflections(
    raw_text: str,
    valid_ids: set[str],
    *,
    drop_sink: list[dict] | None = None,
) -> list[Reflection]:
    """Extract reflection objects from the model's JSON. Tolerant of
    leading/trailing prose around the array; strict on shape."""
    if not raw_text:
        return []
    # Find the first JSON array in the response. Models occasionally
    # wrap output in commentary; the parser ignores anything outside.
    match = re.search(r"\[.*\]", raw_text, re.DOTALL)
    if not match:
        return []
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    out: list[Reflection] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        text = item.get("reflection")
        evidence = item.get("evidence")
        if not isinstance(text, str) or not text.strip():
            continue
        if not isinstance(evidence, list):
            continue
        # Filter to evidence ids that were actually shown to the model.
        # An id the model invented (not in valid_ids) is a fabrication
        # signal — drop it from the citation. If nothing is left, drop
        # the reflection entirely (evidence-required contract).
        raw_evidence = tuple(eid for eid in evidence if isinstance(eid, str))
        cited = tuple(eid for eid in raw_evidence if not valid_ids or eid in valid_ids)
        if not cited:
            if drop_sink is not None:
                drop_sink.append(
                    {
                        "text": text.strip(),
                        "source_memory_ids": list(raw_evidence),
                        "reason": "missing_evidence"
                        if not raw_evidence
                        else "fabricated_evidence",
                    }
                )
            continue
        out.append(Reflection(text=text.strip(), source_memory_ids=cited))
    return out


def synthesize_reflections(
    *,
    recent_episodes: Sequence[dict],
    recent_raw: Sequence[dict] | None = None,
    llm_call: Callable[[str], str],
    max_reflections: int = 3,
    drop_sink: list[dict] | None = None,
) -> list[Reflection]:
    """Draw up to ``max_reflections`` high-level reflections from the
    recent lived-memory window. Returns an empty list when there is
    nothing to reflect on, when the LLM fails, or when the output is
    malformed — never raises."""
    raw = list(recent_raw or [])
    eps = list(recent_episodes or [])
    if not eps and not raw:
        return []

    # Valid evidence ids = the episodes themselves AND each episode's
    # underlying source_memory_ids (so a reflection can cite the
    # deepest grounding it has — a core memory, a follow-up doc, a
    # raw entry — not just the episode wrapper). Raw entry ids are
    # included as well when raw is in scope.
    valid_ids: set[str] = set()
    for ep in eps:
        if ep.get("id"):
            valid_ids.add(str(ep["id"]))
        for sid in ep.get("source_memory_ids") or []:
            if sid:
                valid_ids.add(str(sid))
    for r in raw:
        if r.get("id"):
            valid_ids.add(str(r["id"]))

    prompt = _PROMPT_TEMPLATE.format(
        max_n=max_reflections,
        episodes_block=_format_episodes_block(eps),
        raw_block=_format_raw_block(raw),
    )

    try:
        text = llm_call(prompt)
    except Exception as exc:
        logger.debug("reflection synthesis LLM failed: %s", exc)
        return []

    parsed = _parse_reflections(text or "", valid_ids, drop_sink=drop_sink)
    return parsed[:max_reflections]


def persist_reflections(
    reflections: Sequence[Reflection],
    *,
    episode_store,
) -> list[str]:
    """Write each reflection to the EpisodeStore as
    ``source_kind="reflection"``. Returns the list of new episode
    ids. Reflections with empty evidence are silently skipped — the
    underlying store would raise on them anyway, and this layer
    treats reflection writes as best-effort."""
    out: list[str] = []
    for r in reflections:
        if not r.source_memory_ids:
            continue
        try:
            # Use the reflection text as the title so lived_recall's
            # title-based brief formatter renders it informatively.
            # Summary keeps the full text for deep recall.
            short_title = r.text[:140].rstrip()
            ep_id = episode_store.add(
                title=short_title,
                summary=r.text,
                participants=("Maez",),
                source_memory_ids=list(r.source_memory_ids),
                source_kind="reflection",
                importance=4,
            )
            out.append(ep_id)
        except Exception as exc:
            logger.debug("reflection persist failed (skipping): %s", exc)
            continue
    return out
