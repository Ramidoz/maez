"""Cockpit V2 flag registry and process/file truth comparison.

This module classifies flag authority for the cockpit. It does not edit env
files and does not expose write endpoints; Task 5 owns writes after owner
review of the tier table.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Literal, Mapping, Sequence

from core.infra.secrets import is_secret_name

Tier = Literal["T0", "T1", "T2", "T3"]

_FLAG_RE = re.compile(r"\bMAEZ_[A-Z0-9_]+\b")
_SOURCE_ORDER = ("code", "env_file", "process_env")
_SKIP_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "memory",
    "logs",
    "node_modules",
}
_TEXT_SUFFIXES = {
    ".cfg",
    ".conf",
    ".env",
    ".html",
    ".js",
    ".jsx",
    ".json",
    ".md",
    ".py",
    ".sh",
    ".service",
    ".template",
    ".txt",
    ".yaml",
    ".yml",
}


@dataclass(frozen=True)
class FlagRegistryEntry:
    name: str
    label: str
    tier: Tier
    description: str
    witness_recipe: str
    revert_line: str
    owner_review_status: str = "pending_owner_review"

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def _entry(
    name: str,
    *,
    label: str,
    tier: Tier,
    description: str,
    witness: str,
    revert: str | None = None,
    owner_review_status: str = "owner_reviewed",
) -> FlagRegistryEntry:
    return FlagRegistryEntry(
        name=name,
        label=label,
        tier=tier,
        description=description,
        witness_recipe=witness,
        revert_line=revert or f"Set {name}=0 or remove it, then restart if daemon-read.",
        owner_review_status=owner_review_status,
    )


def default_registry() -> dict[str, FlagRegistryEntry]:
    """Return the owner-reviewed registry.

    Unknown entries are not writable. T0 and T3 entries remain non-writable by
    tier even after owner review.
    """

    entries = [
        _entry(
            "MAEZ_COCKPIT_V2",
            label="Cockpit operability shell",
            tier="T1",
            description="Serves the V2 operability shell while flag-off remains byte-identical.",
            witness="Set MAEZ_COCKPIT_V2=1, restart maez-web.service, verify /cockpit serves v2 and flag-off reverts.",
        ),
        _entry(
            "MAEZ_BODY_LEGIBILITY",
            label="Body Legibility",
            tier="T1",
            description="Makes existing body/sense affordances visible; no tool routing change.",
            witness="Set MAEZ_BODY_LEGIBILITY=1, restart maez.service, ask a body-capability turn, verify no body denial.",
        ),
        _entry(
            "MAEZ_SELF_EVIDENCE",
            label="A6 Self-Evidence",
            tier="T1",
            description="Read-only integrity receipt digest surface.",
            witness="Set MAEZ_SELF_EVIDENCE=1 and run scripts/self_evidence.py show; verify no first-person or score.",
            revert="Set MAEZ_SELF_EVIDENCE=0 or remove it; no restart required for the script surface.",
        ),
        _entry(
            "MAEZ_CONTINUITY_FINGERPRINT",
            label="A2 Continuity Fingerprint",
            tier="T1",
            description="Inspection-only private probe meter; writes only its own A2 store when run.",
            witness="Set MAEZ_CONTINUITY_FINGERPRINT=1 and run scripts/continuity_fingerprint.py run/show.",
            revert="Set MAEZ_CONTINUITY_FINGERPRINT=0 or remove it; no restart required for the script surface.",
        ),
        _entry(
            "MAEZ_INTERACTION_PREFERENCES_SHADOW",
            label="Interaction Preferences shadow",
            tier="T1",
            description="Detects explicit owner preferences without writing a preference row.",
            witness="Set MAEZ_INTERACTION_PREFERENCES_SHADOW=1, restart maez.service, verify would_capture log and no DB row.",
        ),
        _entry(
            "MAEZ_INTERACTION_PREFERENCES",
            label="Interaction Preferences enforce",
            tier="T2",
            description="Stores and renders explicit owner-authored interaction preferences.",
            witness="Set MAEZ_INTERACTION_PREFERENCES=1, restart maez.service, capture and retract one owner statement.",
        ),
        _entry(
            "MAEZ_SCAR_TISSUE",
            label="A1 Scar Tissue",
            tier="T2",
            description="Writes correction scars and consequence rows from receipt-grade events.",
            witness="Set MAEZ_SCAR_TISSUE=1, restart maez.service, reject one dream with owner words, verify scar receipt.",
        ),
        _entry(
            "MAEZ_METABOLIC_MEMORY",
            label="A3 Metabolic Memory",
            tier="T2",
            description="Changes cycle-thought durability and self-observed memory tiering.",
            witness="Set MAEZ_METABOLIC_MEMORY=1, restart maez.service, verify quiet stretch writes glances to RAM only.",
        ),
        _entry(
            "MAEZ_NARRATIVE_SPINE",
            label="A4 Narrative Spine",
            tier="T2",
            description="Arms deterministic narrative link writes for new episodes.",
            witness="Set MAEZ_NARRATIVE_SPINE=1, restart maez.service, apply owner-gated backfill, verify strings/threads counts.",
        ),
        _entry(
            "MAEZ_NARRATIVE_WEAVE",
            label="A4 Narrative Weave",
            tier="T2",
            description="Runs embedding-instrument story-nearness proposals; no LLM path.",
            witness="Set MAEZ_NARRATIVE_WEAVE=1, restart if daemon-read, verify proposals only and no history link without confirmation.",
        ),
        _entry(
            "MAEZ_NARRATIVE_REFLECTION",
            label="A4 Narrative Reflection",
            tier="T2",
            description="Writes reflection chapters once true threads exist.",
            witness="Set MAEZ_NARRATIVE_REFLECTION=1, restart if daemon-read, verify chapter output cites narrative links.",
        ),
        _entry(
            "MAEZ_NARRATIVE_RECALL",
            label="Narrative recall reader",
            tier="T2",
            description="Allows narrative structure to inform recall.",
            witness="Set MAEZ_NARRATIVE_RECALL=1, restart maez.service, verify recall/presence witness before leaving on.",
        ),
        _entry(
            "MAEZ_NARRATIVE_PRESENCE",
            label="Narrative presence reader",
            tier="T2",
            description="Allows narrative structure to inform presence.",
            witness="Set MAEZ_NARRATIVE_PRESENCE=1, restart maez.service, verify presence witness before leaving on.",
        ),
        _entry(
            "MAEZ_RECALL_CONTEXT_FLOOR_SHADOW",
            label="Recall context floor shadow",
            tier="T1",
            description="Observe-only content-blind recall floor receipts.",
            witness="Set MAEZ_RECALL_CONTEXT_FLOOR_SHADOW=1, restart maez.service, inspect shadow artifact.",
        ),
        _entry(
            "MAEZ_RECALL_CONTEXT_FLOOR_ENABLED",
            label="Recall context floor enforce",
            tier="T2",
            description="Applies content-blind casual-floor recall filtering.",
            witness="Set MAEZ_RECALL_CONTEXT_FLOOR_ENABLED=1, restart maez.service, verify diary quiets and self-asks unchanged.",
        ),
        _entry(
            "MAEZ_CLAIM_RECEIPT_SHADOW",
            label="Claim-receipt rail shadow",
            tier="T1",
            description="Observe-only action-claim mismatch detection.",
            witness="Set MAEZ_CLAIM_RECEIPT_SHADOW=1, restart maez.service, inspect false-positive artifact.",
        ),
        _entry(
            "MAEZ_CLAIM_RECEIPT_ENFORCE",
            label="Claim-receipt rail enforce",
            tier="T2",
            description="One-redo honesty rail for unreceipted this-turn action claims.",
            witness="Set MAEZ_CLAIM_RECEIPT_ENFORCE=1, restart maez.service, verify no fabricated action reaches send.",
        ),
        _entry(
            "MAEZ_TELEGRAM_TOKEN",
            label="Telegram token",
            tier="T0",
            description="Secret/process credential; cockpit may show health, never edit or reveal value.",
            witness="Read-only health check only; values are redacted.",
            revert="Credential changes stay outside cockpit flag writes.",
        ),
        _entry(
            "MAEZ_JETSON_DEVICE_TOKEN",
            label="Jetson device token",
            tier="T0",
            description="Secret/device credential; cockpit may show health, never edit or reveal value.",
            witness="Read-only health check only; values are redacted.",
            revert="Credential changes stay outside cockpit flag writes.",
        ),
        _entry(
            "MAEZ_OWNER_TIMEZONE",
            label="Owner timezone",
            tier="T0",
            description="Configuration fact, not an on/off feature flag.",
            witness="Read-only display only; verify timezone source if surfaced.",
            revert="Configuration fact changes stay outside cockpit flag writes.",
        ),
        _entry(
            "MAEZ_LEDGER_WRITES",
            label="Birth ledger write switch",
            tier="T3",
            description="Birth-gated autobiography switch; reachable only through the birth ceremony.",
            witness="Run the reviewed BIRTH_CEREMONY path; never flip MAEZ_LEDGER_WRITES directly from cockpit.",
            revert="No direct env revert; follow the birth ceremony rollback/runbook.",
        ),
        _entry(
            "S7_LIVE_WEBAUTHN_CEREMONY",
            label="S7 live WebAuthn ceremony gate",
            tier="T3",
            description="Soul-authority ceremony gate; reachable only through the existing S7 ceremony flow.",
            witness="Complete S7_CEREMONY through the existing WebAuthn challenge/assertion route.",
            revert="No direct env revert; follow S7 ceremony rollback/runbook.",
        ),
        FlagRegistryEntry(
            name="S7_CEREMONY",
            label="S7 ceremony",
            tier="T3",
            description="Human-gated self-shaping ceremony; cockpit may launch the existing S7 flow only.",
            witness_recipe="Complete the existing /api/v1/s7 challenge/assertion flow with hardware-key touch.",
            revert_line="No direct env revert; follow S7 ceremony rollback/runbook.",
            owner_review_status="owner_reviewed",
        ),
        FlagRegistryEntry(
            name="BIRTH_CEREMONY",
            label="Birth ceremony",
            tier="T3",
            description="Birth gate ceremony; no direct flag write is allowed.",
            witness_recipe="Run the reviewed birth ceremony after all blockers clear and hardware key is present.",
            revert_line="No direct env revert; follow the birth ceremony runbook.",
            owner_review_status="owner_reviewed",
        ),
    ]
    return {entry.name: entry for entry in entries}


def parse_env_file(path: Path | str) -> dict[str, str]:
    """Parse MAEZ_* assignments from an env file without expanding values."""

    env: dict[str, str] = {}
    p = Path(path)
    if not p.exists():
        return env
    for raw_line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key.startswith("MAEZ_"):
            continue
        env[key] = value.strip().strip("'\"")
    return dict(sorted(env.items()))


def _scan_code_flags(root: Path) -> set[str]:
    found: set[str] = set()
    if not root.exists():
        return found
    for path in root.rglob("*"):
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        if not path.is_file():
            continue
        if path.suffix and path.suffix not in _TEXT_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        found.update(_FLAG_RE.findall(text))
    return found


def discover_observed_flags(
    *,
    code_roots: Sequence[Path | str] = (),
    env_files: Sequence[Path | str] = (),
    process_envs: Sequence[Mapping[str, str]] = (),
) -> list[dict[str, object]]:
    sources_by_name: dict[str, set[str]] = {}
    for root in code_roots:
        for name in _scan_code_flags(Path(root)):
            sources_by_name.setdefault(name, set()).add("code")
    for env_file in env_files:
        for name in parse_env_file(env_file):
            sources_by_name.setdefault(name, set()).add("env_file")
    for env in process_envs:
        for name in env:
            if name.startswith("MAEZ_"):
                sources_by_name.setdefault(name, set()).add("process_env")

    order = {source: idx for idx, source in enumerate(_SOURCE_ORDER)}
    return [
        {
            "name": name,
            "sources": sorted(sources, key=lambda item: order[item]),
        }
        for name, sources in sorted(sources_by_name.items())
    ]


def compare_file_process_flags(
    *,
    file_env: Mapping[str, str],
    process_env: Mapping[str, str],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for name in sorted(set(file_env) | set(process_env)):
        file_present = name in file_env
        process_present = name in process_env
        file_value = file_env.get(name)
        process_value = process_env.get(name)
        if file_present and process_present:
            sync_state = "in_sync" if file_value == process_value else "mismatch"
        elif file_present:
            sync_state = "file_only"
        else:
            sync_state = "process_only"
        display_file_value = _display_value(name, file_value)
        display_process_value = _display_value(name, process_value)
        rows.append(
            {
                "name": name,
                "file_value": display_file_value,
                "process_value": display_process_value,
                "sync_state": sync_state,
                "severity": "ok" if sync_state == "in_sync" else "warning",
            }
        )
    return rows


def compare_file_process_flags_by_process(
    *,
    file_env: Mapping[str, str],
    process_envs: Mapping[str, Mapping[str, str]],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    names = set(file_env)
    for env in process_envs.values():
        names.update(env)
    for name in sorted(names):
        file_present = name in file_env
        file_value = file_env.get(name)
        raw_process_values = {
            process_name: env[name]
            for process_name, env in sorted(process_envs.items())
            if name in env
        }
        display_process_values = {
            process_name: str(_display_value(name, value))
            for process_name, value in raw_process_values.items()
        }
        distinct_raw_values = set(raw_process_values.values())
        if len(distinct_raw_values) == 1:
            only_value = next(iter(distinct_raw_values))
            process_value = _display_value(name, only_value)
        elif distinct_raw_values:
            process_value = "mixed"
        else:
            process_value = None

        if file_present and raw_process_values:
            if len(distinct_raw_values) == 1 and file_value in distinct_raw_values:
                sync_state = "in_sync"
            else:
                sync_state = "mismatch"
        elif file_present:
            sync_state = "file_only"
        else:
            sync_state = "process_only"

        rows.append(
            {
                "name": name,
                "file_value": _display_value(name, file_value),
                "process_value": process_value,
                "process_values": display_process_values,
                "sync_state": sync_state,
                "severity": "ok" if sync_state == "in_sync" else "warning",
            }
        )
    return rows


def display_env_values(env: Mapping[str, str]) -> dict[str, str]:
    return {name: str(_display_value(name, value)) for name, value in sorted(env.items())}


def _display_value(name: str, value: str | None) -> str | None:
    if value is None:
        return None
    if is_secret_name(name):
        return "[redacted]"
    return value


def write_policy_for_flag(
    name: str,
    desired_value: str,
    *,
    registry: Mapping[str, FlagRegistryEntry] | None = None,
) -> dict[str, object]:
    """Return direct-write eligibility without performing any write."""

    del desired_value
    entries = registry if registry is not None else default_registry()
    entry = entries.get(name)
    if entry is None:
        return {
            "name": name,
            "tier": "unclassified",
            "direct_write_allowed": False,
            "direct_write_endpoint": None,
            "reason": "unknown_flag",
        }
    if entry.tier == "T0":
        reason = "read_only"
    elif entry.tier == "T3":
        reason = "ceremony_only"
    elif entry.owner_review_status != "owner_reviewed":
        reason = "pending_owner_review"
    else:
        reason = "ok"
    allowed = reason == "ok"
    return {
        "name": name,
        "tier": entry.tier,
        "direct_write_allowed": allowed,
        "direct_write_endpoint": f"/api/v2/cockpit/flags/{name}" if allowed else None,
        "reason": reason,
        "witness_recipe": entry.witness_recipe,
        "revert_line": entry.revert_line,
    }


def registry_table() -> list[dict[str, str]]:
    return [entry.to_dict() for entry in default_registry().values()]


def unclassified_observed_flags(observed: Iterable[Mapping[str, object]]) -> list[str]:
    registry = default_registry()
    return sorted(
        str(row["name"])
        for row in observed
        if str(row.get("name", "")) not in registry
    )
