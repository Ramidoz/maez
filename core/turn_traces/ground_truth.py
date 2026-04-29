# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Runtime ground truth for trace-harness checks.

This module is intentionally small and read-only. It gives the trace
harness current facts about Maez's body (model alias, service state,
feature flags, VRAM, git state) with provenance for each fact. The
facts are not "beliefs"; each one records how it was probed so a
harness finding can cite the same evidence covenant Maez's own replies
are expected to obey.

All probes are best-effort. A failed probe returns ``ok=False`` instead
of raising; an unavailable fact must not become a false accusation.
"""
from __future__ import annotations

import json
import os
import subprocess
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class GroundTruthFact:
    name: str
    value: Any
    ok: bool
    source: str
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GroundTruthSnapshot:
    facts: dict[str, GroundTruthFact] = field(default_factory=dict)

    def get(self, name: str) -> GroundTruthFact | None:
        return self.facts.get(name)

    def to_dict(self) -> dict[str, Any]:
        return {name: fact.to_dict() for name, fact in self.facts.items()}


def _run(cmd: list[str], *, timeout: float = 2.0) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(
            cmd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except Exception as exc:
        return 999, "", str(exc)


def current_model(*, url: str = "http://127.0.0.1:8080/v1/models") -> GroundTruthFact:
    """Return the first model id from the local llama.cpp OpenAI-style
    models endpoint."""
    try:
        with urllib.request.urlopen(url, timeout=2.0) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        data = payload.get("data") or []
        model = ""
        if data and isinstance(data[0], dict):
            model = str(data[0].get("id") or "")
        if model:
            return GroundTruthFact(
                name="current_model",
                value=model,
                ok=True,
                source=url,
            )
        return GroundTruthFact(
            name="current_model",
            value="",
            ok=False,
            source=url,
            detail="models endpoint returned no model id",
        )
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        return GroundTruthFact(
            name="current_model",
            value="",
            ok=False,
            source=url,
            detail=str(exc),
        )


def service_active(service: str) -> GroundTruthFact:
    rc, out, err = _run(["systemctl", "is-active", service], timeout=2.0)
    state = out or err or f"exit={rc}"
    return GroundTruthFact(
        name=f"service:{service}",
        value=(state == "active"),
        ok=(rc == 0 or state in {"active", "inactive", "failed", "unknown"}),
        source=f"systemctl is-active {service}",
        detail=state,
    )


def active_services(services: list[str]) -> GroundTruthFact:
    states: dict[str, bool] = {}
    details: list[str] = []
    ok = True
    for service in services:
        fact = service_active(service)
        states[service] = bool(fact.value)
        details.append(f"{service}={fact.detail or fact.value}")
        ok = ok and fact.ok
    return GroundTruthFact(
        name="active_services",
        value=states,
        ok=ok,
        source="systemctl is-active <service>",
        detail=", ".join(details),
    )


def judge_active() -> GroundTruthFact:
    fact = service_active("llama-judge.service")
    return GroundTruthFact(
        name="judge_active",
        value=bool(fact.value),
        ok=fact.ok,
        source=fact.source,
        detail=fact.detail,
    )


def vision_available() -> GroundTruthFact:
    """Vision is available only if the env flag is set and a known vision
    service is active. Today MAEZ_SCREEN_PERCEPTION unset means vision is
    intentionally off."""
    env_value = os.environ.get("MAEZ_SCREEN_PERCEPTION", "")
    # Retired/disabled feature probes: these names are checked so the
    # harness can prove old vision-service claims are false; they are
    # not live dependencies.
    service_names = ["llama-server-vision.service", "maez-screen-perception.service"]
    service_fact = active_services(service_names)
    active_any = any((service_fact.value or {}).values())
    available = env_value.strip().lower() in {"1", "true", "yes", "on"} and active_any
    return GroundTruthFact(
        name="vision_available",
        value=available,
        ok=service_fact.ok,
        source="MAEZ_SCREEN_PERCEPTION + systemctl is-active vision services",
        detail=f"MAEZ_SCREEN_PERCEPTION={env_value!r}; {service_fact.detail}",
    )


def feature_flags(names: list[str] | None = None) -> GroundTruthFact:
    if names is None:
        names = [
            "MAEZ_LIVED_RECALL",
            "MAEZ_WEB_TOOL_LOOP",
            "MAEZ_SCREEN_PERCEPTION",
            "MAEZ_JUDGE_MODEL",
        ]
    values = {name: os.environ.get(name, "") for name in names}
    return GroundTruthFact(
        name="feature_flags",
        value=values,
        ok=True,
        source="process environment",
    )


def vram_snapshot() -> GroundTruthFact:
    rc, out, err = _run(
        [
            "nvidia-smi",
            "--query-gpu=memory.used,memory.total,temperature.gpu",
            "--format=csv,noheader,nounits",
        ],
        timeout=2.0,
    )
    if rc != 0:
        return GroundTruthFact(
            name="vram_snapshot",
            value={},
            ok=False,
            source="nvidia-smi --query-gpu=memory.used,memory.total,temperature.gpu",
            detail=err or out or f"exit={rc}",
        )
    first = (out.splitlines() or [""])[0]
    parts = [p.strip() for p in first.split(",")]
    value: dict[str, int] = {}
    try:
        if len(parts) >= 3:
            value = {
                "memory_used_mb": int(float(parts[0])),
                "memory_total_mb": int(float(parts[1])),
                "temperature_c": int(float(parts[2])),
            }
    except ValueError:
        value = {}
    return GroundTruthFact(
        name="vram_snapshot",
        value=value,
        ok=bool(value),
        source="nvidia-smi --query-gpu=memory.used,memory.total,temperature.gpu",
        detail=out,
    )


def git_clean_state(*, repo_root: str | Path | None = None) -> GroundTruthFact:
    cwd = Path(repo_root) if repo_root is not None else Path.cwd()
    rc, out, err = _run(["git", "status", "--short"], timeout=2.0)
    dirty = [line for line in out.splitlines() if line.strip()]
    return GroundTruthFact(
        name="git_clean",
        value=(rc == 0 and not dirty),
        ok=(rc == 0),
        source=f"git status --short ({cwd})",
        detail=err if rc != 0 else f"{len(dirty)} changed path(s)",
    )


def collect_ground_truth() -> GroundTruthSnapshot:
    facts = [
        current_model(),
        judge_active(),
        vision_available(),
        feature_flags(),
        vram_snapshot(),
        git_clean_state(),
    ]
    return GroundTruthSnapshot({fact.name: fact for fact in facts})
