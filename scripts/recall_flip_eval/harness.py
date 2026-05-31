from __future__ import annotations

import re
import time
from dataclasses import dataclass
from types import SimpleNamespace


DETERMINISTIC_CHAT_ID = "offline_citation_echo.v1"


@dataclass(frozen=True)
class ProbeArmResult:
    answer: str
    outcome_class: str
    receipt: str
    focused_elapsed_ms: int
    citation_coverage: float | None
    cited_durable_ids: tuple[str, ...] = ()
    cited_confirmed_memory_context: bool = False
    working_set_source_types: tuple[str, ...] = ()


def deterministic_offline_chat(*, model, messages, think=False, options=None):
    """Offline chat adapter for 2a.

    It never calls a model. It returns a tiny citation-shaped response so
    focused synthesis and groundedness exercise the real citation plumbing.
    """
    system = str((messages or [{}])[0].get("content") or "")
    labels = re.findall(r"\[(E\d+)\]", system)
    label = labels[0] if labels else "E1"
    return SimpleNamespace(
        message=SimpleNamespace(content=f"Offline recall harness cites [{label}].")
    )


def run_probe(text: str, *, flag_on: bool) -> ProbeArmResult:
    if not flag_on:
        return ProbeArmResult(
            answer="",
            outcome_class="declined_unavailable",
            receipt="not_consulted",
            focused_elapsed_ms=0,
            citation_coverage=None,
        )

    from core.brain import brain_loop
    from core.dispatcher.spec import SubstrateSource
    from core.routing import focused_cognition
    from core.routing.recall_outcome import (
        cites_confirmed_memory_context,
        classify_outcome,
    )
    from core.routing.recall_stack_config import RecallMode, RecallStackConfig
    from core.routing.temporal_cue import absolute_recall_cue
    from scripts.recall_flip_eval import sandbox

    sandbox.assert_sandbox()
    date_addressed = absolute_recall_cue(text).is_address
    stack_config = RecallStackConfig(RecallMode.TRIAD, "bundle_enabled")
    adapters = brain_loop._dispatcher_recall_adapters(
        text,
        surface="telegram",
        recall_stack_config=stack_config,
    )
    blocks = tuple(adapters[SubstrateSource.TELEGRAM_TEMPORAL](SubstrateSource.TELEGRAM_TEMPORAL))
    transcript = "\n\n".join(block.text for block in blocks if block.text)
    recall_items = tuple(item for block in blocks for item in (block.items or ()))

    start = time.time()
    working_set = focused_cognition.assemble_working_set(
        transcript=transcript,
        web_context="",
        owner_question=text,
        chat_history=(),
        recall_items=recall_items,
    )
    if working_set is None:
        elapsed = int((time.time() - start) * 1000)
        if not date_addressed:
            return ProbeArmResult(
                answer="",
                outcome_class="ordinary_answered",
                receipt="not_consulted",
                focused_elapsed_ms=elapsed,
                citation_coverage=None,
            )
        return ProbeArmResult(
            answer="",
            outcome_class="declined_absence",
            receipt="consulted",
            focused_elapsed_ms=elapsed,
            citation_coverage=None,
        )

    had_confirmed = any(
        bool((item.temporal_provenance or {}).get("confirmed"))
        for item in working_set.items
    )
    if date_addressed and not had_confirmed:
        elapsed = int((time.time() - start) * 1000)
        return ProbeArmResult(
            answer="",
            outcome_class="declined_absence",
            receipt="consulted",
            focused_elapsed_ms=elapsed,
            citation_coverage=None,
            working_set_source_types=tuple(item.source_type for item in working_set.items),
        )

    result = focused_cognition.focused_synthesize(
        working_set,
        surface="telegram",
        chat_fn=deterministic_offline_chat,
    )
    verdict = focused_cognition.check_groundedness(result, working_set)
    elapsed = int((time.time() - start) * 1000)
    grounded = cites_confirmed_memory_context(result, working_set)
    outcome = classify_outcome(
        mode="recall_triad",
        turn_kind="dated",
        answered=bool(result.reply),
        receipt="consulted",
        denial_kind="none",
        had_confirmed=had_confirmed,
        cited_grounded_context=grounded,
        unmatched_citations=len(verdict.unmatched),
    )
    cited = set(result.cited_ids)
    durable_ids = tuple(
        item.durable_id
        for item in working_set.items
        if item.local_label in cited and item.durable_id
    )
    return ProbeArmResult(
        answer=result.reply,
        outcome_class=outcome.value,
        receipt="consulted",
        focused_elapsed_ms=elapsed,
        citation_coverage=verdict.citation_coverage,
        cited_durable_ids=durable_ids,
        cited_confirmed_memory_context=grounded,
        working_set_source_types=tuple(item.source_type for item in working_set.items),
    )


def main() -> int:
    raise SystemExit("recall flip eval harness main is implemented in Task 5")


if __name__ == "__main__":
    main()
