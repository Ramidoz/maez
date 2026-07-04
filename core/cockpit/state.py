"""Aggregate Cockpit V2 read model.

This module composes process truth and source health for the cockpit. It does
not mutate runtime state and all filesystem paths are injectable for tests.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

from core.cockpit.readers import CockpitSourcePaths, source_health


@dataclass(frozen=True)
class RuntimePaths:
    memory_dir: Path
    logs_dir: Path
    config_dir: Path

    @classmethod
    def defaults(cls) -> "RuntimePaths":
        from core.infra import paths

        return cls(
            memory_dir=paths.memory_dir(),
            logs_dir=paths.logs_dir(),
            config_dir=paths.config_dir(),
        )


CommandRunner = Callable[[Sequence[str]], str]


def _default_command_runner(cmd: Sequence[str]) -> str:
    return subprocess.check_output(
        list(cmd),
        text=True,
        stderr=subprocess.DEVNULL,
        timeout=1.5,
    )


def _main_pid(service: str, command_runner: CommandRunner) -> int:
    try:
        raw = command_runner(
            ["systemctl", "show", "-p", "MainPID", "--value", service]
        )
    except Exception:
        return 0
    try:
        return int(str(raw).strip() or "0")
    except ValueError:
        return 0


def _process_env_flags(pid: int, proc_root: Path) -> tuple[str, dict[str, str]]:
    if pid <= 0:
        return "not_running", {}
    try:
        raw = (proc_root / str(pid) / "environ").read_bytes()
    except Exception:
        return "unavailable", {}
    flags: dict[str, str] = {}
    for part in raw.split(b"\0"):
        if not part or b"=" not in part:
            continue
        key_b, value_b = part.split(b"=", 1)
        key = key_b.decode("utf-8", errors="replace")
        if not key.startswith("MAEZ_"):
            continue
        flags[key] = value_b.decode("utf-8", errors="replace")
    return "ok", dict(sorted(flags.items()))


def _process_truth(
    *,
    service: str,
    command_runner: CommandRunner,
    proc_root: Path,
) -> dict:
    pid = _main_pid(service, command_runner)
    env_status, env_flags = _process_env_flags(pid, proc_root)
    return {
        "service": service,
        "pid": pid,
        "status": "active" if pid > 0 else "unavailable",
        "env_status": env_status,
        "env_flags": env_flags,
    }


def _rooms() -> list[dict]:
    return [
        {
            "id": "senses",
            "label": "Senses",
            "organs": [
                {"id": "body_legibility", "label": "Body Legibility"},
                {"id": "ambient_weather", "label": "Ambient Weather"},
            ],
        },
        {
            "id": "memory",
            "label": "Memory",
            "organs": [
                {"id": "narrative_spine", "label": "Narrative Spine"},
                {"id": "metabolic_memory", "label": "Metabolic Memory"},
                {"id": "interaction_preferences", "label": "Interaction Preferences"},
            ],
        },
        {
            "id": "self_knowledge",
            "label": "Self-Knowledge",
            "organs": [
                {"id": "a1_scar_tissue", "label": "A1 Scar Tissue"},
                {"id": "a2_continuity_fingerprint", "label": "A2 Continuity"},
                {"id": "a6_self_evidence", "label": "A6 Self-Evidence"},
                {"id": "a7_interiority", "label": "A7 Interiority"},
            ],
        },
        {
            "id": "honesty",
            "label": "Honesty",
            "organs": [
                {"id": "claim_receipt_rail", "label": "Claim-Receipt Rail"},
                {"id": "receipts", "label": "Receipts"},
            ],
        },
        {
            "id": "voice",
            "label": "Voice",
            "organs": [
                {"id": "self_card", "label": "Self Card"},
                {"id": "why_this_reply", "label": "Why This Reply"},
            ],
        },
        {
            "id": "learning",
            "label": "Learning",
            "organs": [
                {"id": "routing_priors", "label": "Routing Priors"},
                {"id": "dreams", "label": "Dreams"},
            ],
        },
        {
            "id": "life_switch",
            "label": "Life Switch",
            "organs": [
                {"id": "s7_ceremony", "label": "S7 Ceremony"},
                {"id": "birth_gate", "label": "Birth Gate"},
            ],
        },
    ]


def build_state(
    *,
    runtime: RuntimePaths | None = None,
    command_runner: CommandRunner | None = None,
    proc_root: Path | str = Path("/proc"),
) -> dict:
    runtime_paths = runtime or RuntimePaths.defaults()
    runner = command_runner or _default_command_runner
    source_paths = CockpitSourcePaths(
        memory_dir=runtime_paths.memory_dir,
        logs_dir=runtime_paths.logs_dir,
    )
    proc = Path(proc_root)
    return {
        "kind": "cockpit_v2_state",
        "processes": {
            "daemon": _process_truth(
                service="maez.service",
                command_runner=runner,
                proc_root=proc,
            ),
            "web": _process_truth(
                service="maez-web.service",
                command_runner=runner,
                proc_root=proc,
            ),
        },
        "rooms": _rooms(),
        "sources": source_health(source_paths),
    }
