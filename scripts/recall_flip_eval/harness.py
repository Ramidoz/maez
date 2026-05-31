from __future__ import annotations

import re
import hashlib
import json
import subprocess
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace


DETERMINISTIC_CHAT_ID = "offline_citation_echo.v1"


@dataclass(frozen=True)
class ProbeArmResult:
    answer: str
    outcome_class: str
    receipt: str
    focused_elapsed_ms: int
    citation_coverage: float | None
    cited_ids: tuple[str, ...] = ()
    cited_durable_ids: tuple[str, ...] = ()
    cited_confirmed_memory_context: bool = False
    working_set_source_types: tuple[str, ...] = ()
    available_label_map: tuple[dict[str, object], ...] = ()
    citation_render_version: str = "v1"


class HarnessAbort(RuntimeError):
    pass


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


def citation_label_map(working_set) -> tuple[dict[str, object], ...]:
    """Content-free map of citation labels available in the assembled working set."""
    return tuple(
        {
            "label": item.local_label,
            "durable_id": item.durable_id,
            "source_type": item.source_type,
            "confirmed": bool((item.temporal_provenance or {}).get("confirmed")),
        }
        for item in getattr(working_set, "items", ())
    )


def current_commit_sha() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


def git_dirty() -> bool:
    return bool(subprocess.check_output(["git", "status", "--porcelain"], text=True).strip())


def assert_run_parity(*, expect_commit: str | None, allow_dirty: bool = False) -> tuple[str, bool]:
    actual = current_commit_sha()
    dirty = git_dirty()
    if expect_commit and expect_commit != actual:
        raise HarnessAbort(f"commit mismatch: expected {expect_commit}, got {actual}")
    if dirty and not allow_dirty:
        raise HarnessAbort("worktree is dirty; refusing to emit canonical proof packet")
    return actual, dirty


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
            available_label_map=citation_label_map(working_set),
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
        cited_ids=tuple(result.cited_ids),
        cited_durable_ids=durable_ids,
        cited_confirmed_memory_context=grounded,
        working_set_source_types=tuple(item.source_type for item in working_set.items),
        available_label_map=citation_label_map(working_set),
        citation_render_version=working_set.citation_render_version,
    )


def run_eval(
    *,
    sandbox_root: str | Path,
    expect_commit: str | None = None,
    probe_ids: tuple[str, ...] | None = None,
    variants_per_probe: int | None = None,
    allow_dirty: bool = False,
    debug_dump_dir: str | Path | None = None,
    teardown_sandbox: bool = False,
):
    from core.model_config import PRIMARY_MODEL
    from scripts.recall_flip_eval import probes, sandbox
    from scripts.recall_flip_eval.proof_packet import (
        ProbeResult,
        ProofPacket,
    )

    sandbox_root = Path(sandbox_root)
    sandbox.patch_memory_manager_base_db(sandbox_root)
    try:
        sandbox.assert_sandbox(sandbox_root)
        actual_commit, dirty = assert_run_parity(
            expect_commit=expect_commit,
            allow_dirty=allow_dirty,
        )
        expected_commit = expect_commit or actual_commit
        run_id = f"eval-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}"
        selected = [
            probe
            for probe in probes.PROBES
            if probe_ids is None or probe.probe_id in set(probe_ids)
        ]
        probe_results: list[ProbeResult] = []
        fixture_manifest: list[dict] = []
        debug_dump_count = 0
        debug_hash = None

        with sandbox.no_egress():
            for probe in selected:
                (
                    probe_result,
                    probe_debug_count,
                    probe_fixture_manifest,
                ) = _run_probe_battery(
                    sandbox_root=sandbox_root,
                    probe=probe,
                    run_id=run_id,
                    variants_per_probe=variants_per_probe,
                    debug_dump_dir=debug_dump_dir,
                )
                probe_results.append(probe_result)
                debug_dump_count += probe_debug_count
                fixture_manifest.extend(probe_fixture_manifest)

        if debug_dump_dir is not None and debug_dump_count:
            debug_hash = _hash_debug_manifest(debug_dump_dir)
        packet = ProofPacket(
            run_id=run_id,
            started_at_utc=datetime.now(timezone.utc).isoformat(),
            expected_commit_sha=expected_commit,
            actual_commit_sha=actual_commit,
            git_dirty=dirty,
            probe_set_hash=_manifest_hash([probe.probe_id for probe in selected]),
            fixture_manifest_hash=_fixture_manifest_hash(fixture_manifest),
            deterministic_chat_id=DETERMINISTIC_CHAT_ID,
            configured_model_id=str(PRIMARY_MODEL),
            debug_dump_count=debug_dump_count,
            debug_dump_manifest_hash=debug_hash,
            results=tuple(probe_results),
        )
        out_dir = sandbox_root / "proof"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "eval_packet.json").write_text(packet.to_json() + "\n")
        return packet
    finally:
        sandbox.restore_memory_patches()
        if teardown_sandbox:
            sandbox.teardown(sandbox_root)


def _run_probe_battery(
    *,
    sandbox_root: Path,
    probe,
    run_id: str,
    variants_per_probe: int | None,
    debug_dump_dir: str | Path | None,
) -> tuple[object, int, tuple[dict, ...]]:
    from scripts.recall_flip_eval import probes, sandbox
    from scripts.recall_flip_eval.proof_packet import ProbeResult, VariantResult

    probe_root = sandbox_root / "probe_sandboxes" / probe.probe_id
    prior_patch_state = sandbox.memory_patch_snapshot()
    debug_dump_count = 0
    try:
        with sandbox.sandbox_env(probe_root):
            sandbox.patch_memory_manager_base_db(probe_root)
            sandbox.assert_sandbox(probe_root)
            expected_fixture_ids, fixture_manifest = _seed_for_probe(probe_root, probe, run_id)
            variants = probe.variants[: variants_per_probe or len(probe.variants)]
            variant_results: list[VariantResult] = []
            passes = 0
            unsafe_failures = 0
            elapsed_values: list[int] = []
            coverage_values: list[float] = []
            last_outcome = "declined_unverified"
            for index, text in enumerate(variants, start=1):
                legacy = run_probe(text, flag_on=False)
                triad = run_probe(text, flag_on=True)
                codes, unsafe = probes.assert_probe_result(
                    probe,
                    triad,
                    expected_fixture_ids=expected_fixture_ids,
                )
                if not unsafe:
                    passes += 1
                unsafe_failures += int(bool(unsafe))
                elapsed_values.append(triad.focused_elapsed_ms)
                if triad.citation_coverage is not None:
                    coverage_values.append(float(triad.citation_coverage))
                last_outcome = triad.outcome_class
                variant_results.append(
                    VariantResult(
                        variant_id=f"{probe.probe_id}_v{index}",
                        legacy_outcome_class=legacy.outcome_class,
                        triad_outcome_class=triad.outcome_class,
                        assertion_codes=tuple(codes),
                        unsafe_failure=bool(unsafe),
                        focused_elapsed_ms=triad.focused_elapsed_ms,
                        citation_coverage=triad.citation_coverage,
                        cited_source_types=triad.working_set_source_types,
                        cited_temporal_confirmed=triad.cited_confirmed_memory_context,
                        cited_durable_id_hashes=tuple(
                            _hash_id(value) for value in triad.cited_durable_ids
                        ),
                    )
                )
                if unsafe and debug_dump_dir is not None:
                    debug_dump_count += 1
                    _write_debug_dump(debug_dump_dir, run_id, probe.probe_id, index, text, triad)
    finally:
        sandbox.restore_memory_patch_snapshot(prior_patch_state)

    return (
        ProbeResult(
            probe_id=probe.probe_id,
            kind=probe.kind,
            hard_gate=probe.hard_gate,
            k_pass=passes,
            k_total=len(variants),
            unsafe_failures=unsafe_failures,
            outcome_class=last_outcome,
            citation_coverage=(
                sum(coverage_values) / len(coverage_values)
                if coverage_values
                else None
            ),
            focused_elapsed_ms=max(elapsed_values or [0]),
            variants=tuple(variant_results),
        ),
        debug_dump_count,
        tuple(fixture_manifest),
    )


_ANSWERABLE_FIXTURE_CONTENT = {
    ("dated_hit", "fixture"): (
        "On April 27, 2026, the dated answer should mention April 27: "
        "router failover stayed stable while the root disk crossed a watch threshold. "
        "Direct answer: router failover stayed stable; root disk crossed a watch threshold."
    ),
    ("both_shaped", "fixture"): (
        "On April 27, 2026, the continuity note says we were tuning the recall gate "
        "with the cedar-card checklist while checking infrastructure health. "
        "Direct answer: tuning the recall gate with the cedar-card checklist."
    ),
    ("type_rule", "fixture"): (
        "On April 27, 2026, the historical backup-log says the silver rollback image "
        "was archived after a router audit. This is historical context and not "
        "current-state evidence. Direct answer: historical backup-log; silver rollback image archived."
    ),
    ("multi_year", "wrong_year"): (
        "On April 27, 2025, the decoy infrastructure note says the green compass was "
        "stored on the west shelf. Direct answer: green compass on the west shelf."
    ),
    ("multi_year", "right_year"): (
        "On April 27, 2026, the current-year infrastructure note says router failover "
        "stayed stable while the root disk crossed a watch threshold. Direct answer: "
        "router failover stayed stable; root disk crossed a watch threshold."
    ),
}


def _seed_for_probe(root: Path, probe, run_id: str) -> tuple[tuple[str, ...], tuple[dict, ...]]:
    if probe.probe_id in {"dated_hit", "both_shaped", "type_rule"}:
        fixture_id, manifest = _seed_fixture(
            probe.probe_id,
            "fixture",
            date_value=date(2026, 4, 27),
            content=_ANSWERABLE_FIXTURE_CONTENT[(probe.probe_id, "fixture")],
            tier="core",
            run_id=run_id,
        )
        return (
            (fixture_id,),
            (manifest,),
        )
    if probe.probe_id == "multi_year":
        _wrong_id, wrong_manifest = _seed_fixture(
            probe.probe_id,
            "wrong_year",
            date_value=date(2025, 4, 27),
            content=_ANSWERABLE_FIXTURE_CONTENT[("multi_year", "wrong_year")],
            tier="core",
            run_id=run_id,
        )
        right, right_manifest = _seed_fixture(
            probe.probe_id,
            "right_year",
            date_value=date(2026, 4, 27),
            content=_ANSWERABLE_FIXTURE_CONTENT[("multi_year", "right_year")],
            tier="core",
            run_id=run_id,
        )
        return (right,), (wrong_manifest, right_manifest)
    return (), ()


def _seed_fixture(
    probe_id: str,
    variant_id: str,
    *,
    date_value: date,
    content: str,
    tier: str,
    run_id: str,
) -> tuple[str, dict]:
    from scripts.recall_flip_eval import sandbox

    fixture_id = sandbox.seed_dated_memory(
        probe_id,
        variant_id,
        date=date_value,
        content=content,
        tier=tier,
        run_id=run_id,
    )
    return fixture_id, {
        "probe_id": probe_id,
        "variant_id": variant_id,
        "date": date_value.isoformat(),
        "tier": tier,
        "content_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "durable_id": fixture_id,
    }


def _hash_id(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _manifest_hash(values) -> str:
    blob = json.dumps(tuple(values), sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def _fixture_manifest_hash(entries) -> str:
    canonical = tuple(sorted(entries, key=lambda item: json.dumps(item, sort_keys=True)))
    return _manifest_hash(canonical)


def _write_debug_dump(debug_dump_dir, run_id, probe_id, index, text, triad) -> None:
    path = Path(debug_dump_dir) / run_id / probe_id
    path.mkdir(parents=True, exist_ok=True)
    (path / f"variant-{index}.json").write_text(
        json.dumps(
            {
                "probe_id": probe_id,
                "variant_index": index,
                "query_text": text,
                "answer_text": triad.answer,
                "outcome_class": triad.outcome_class,
            },
            indent=2,
            sort_keys=True,
        )
    )


def _hash_debug_manifest(debug_dump_dir) -> str:
    entries = sorted(str(path.relative_to(debug_dump_dir)) for path in Path(debug_dump_dir).rglob("*") if path.is_file())
    return _manifest_hash(entries)


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--sandbox-root", required=True)
    parser.add_argument("--expect-commit")
    parser.add_argument("--allow-dirty", action="store_true")
    parser.add_argument("--debug-dump-dir")
    parser.add_argument("--teardown-sandbox", action="store_true")
    args = parser.parse_args(argv)
    run_eval(
        sandbox_root=args.sandbox_root,
        expect_commit=args.expect_commit,
        allow_dirty=args.allow_dirty,
        debug_dump_dir=args.debug_dump_dir,
        teardown_sandbox=args.teardown_sandbox,
    )
    return 0


if __name__ == "__main__":
    main()
