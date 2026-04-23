# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""
capability_registry.py — single source of truth for what Maez actually
has on this system.

Built after the 2026-04-19/20 Maelstrom and self-evolution fabrications
demonstrated that Maez cannot reliably answer "what do you have?"
questions from training weights alone. The fix is not to teach the model
more — the fix is to give it a registry to consult and rewrite
self-description through it.

Three public surfaces:

    describe()         → structured dict, machine-readable.
    prompt_snippet()   → compact string, injected into system prompt so
                         the model sees grounded facts before generating
                         a self-describing reply.
    grounded_vocab()   → frozenset of token stems, consumed by the
                         self_claim_audit detector to widen the
                         grounding surface.

Policy:
  - Everything here is observable from this box at import time.
  - If a fact changes (service restarted, feature re-enabled), the
    registry is regenerated per-call (fast) so replies reflect reality
    instead of startup snapshots.
  - If enumeration fails (permissions, missing tools), the affected
    section is marked `unavailable` rather than fabricated. Audit
    consumers must treat unavailable sections as "don't assert
    anything" rather than "no facts".
"""
from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from typing import Any

try:
    from core import paths as _paths
    _MAEZ_HOME = _paths.home()
except Exception:
    _MAEZ_HOME = Path("/home/rohit/maez")

# ── static schedules (from daemon source constants) ────────────────────

_STATIC_SCHEDULES = {
    "reasoning_cycle_seconds": 30,
    "daily_consolidation_hour_local": 3,
    "nightly_journal_hour_local": 23,
    "curiosity_checkin_hour_local": 21,
    "dreams_trigger": "AFK threshold (event-triggered, not scheduled)",
}

# Features that are code-present but operationally disabled. Explicit
# list — not introspected — so re-enables require a deliberate edit.
_DISABLED_FEATURES = {
    "llama-server-vision": (
        "paused 2026-04 by user; vision inputs unavailable until explicit "
        "re-enable."
    ),
}

# Top-level authored-code dirs. Mirrors self_claim_audit's list so both
# agree on what counts as a "real module".
_CODE_DIRS = ("core", "daemon", "skills", "cli", "ui", "memory",
              "evolution", "training", "web", "tests")

_SKIP_SUBDIR_NAMES = frozenset({
    "__pycache__", ".git", ".venv", "node_modules", "db",
    "chroma-archive", "chroma_archive",
})


# ── introspection helpers ──────────────────────────────────────────────

def _list_modules() -> list[str]:
    """Top-level authored-code dirs present on disk."""
    out: list[str] = []
    for sub in _CODE_DIRS:
        if (_MAEZ_HOME / sub).exists():
            out.append(sub)
    return sorted(out)


def _list_services() -> dict[str, str]:
    """systemd unit states for maez* and llama* units. Returns
    {unit_name: state} where state is 'active' | 'inactive' | 'failed'
    | 'unknown'. If systemctl is unavailable, returns {'unavailable': reason}."""
    try:
        out = subprocess.check_output(
            ["systemctl", "list-units", "--all", "--no-pager", "--no-legend",
             "--type=service", "maez*", "llama*"],
            timeout=2.0, stderr=subprocess.DEVNULL,
        ).decode("utf-8", errors="replace")
    except (subprocess.TimeoutExpired, FileNotFoundError,
            subprocess.CalledProcessError):
        return {"_unavailable": "systemctl not reachable"}
    result: dict[str, str] = {}
    for line in out.splitlines():
        toks = line.strip().split(None, 3)
        if len(toks) < 4:
            continue
        unit = toks[0]
        if unit.endswith(".service"):
            name = unit[:-len(".service")]
            state = toks[2]  # active | inactive | failed
            result[name] = state
    return result


def _memory_counts() -> dict[str, int]:
    """Return real row counts for the chroma memory tiers.

    Queries each tier's chroma.sqlite3 directly (counts the
    `embeddings` table). Returns 0 for any tier whose db is missing
    or unreadable — callers should treat 0 as "unavailable", not
    "empty", for the `raw` tier especially (a functioning Maez
    always has thousands of raw memories).

    Added 2026-04-20 after a Telegram turn where the LLM fabricated
    "I have 12,842 memories" instead of the real ~23,660. Grounding
    this in the prompt snippet removes the guessing surface.
    """
    import sqlite3
    counts: dict[str, int] = {}
    for kind in ("raw", "daily", "core"):
        p = _MAEZ_HOME / "memory" / "db" / kind / "chroma.sqlite3"
        if not p.exists():
            counts[kind] = 0
            continue
        try:
            db = sqlite3.connect(str(p), timeout=1.5)
            row = db.execute("SELECT COUNT(*) FROM embeddings").fetchone()
            counts[kind] = int(row[0]) if row else 0
            db.close()
        except Exception:
            counts[kind] = 0
    counts["total"] = counts["raw"] + counts["daily"] + counts["core"]
    return counts


def _recent_activity() -> dict[str, str]:
    """Recent modification times for key state files. Useful for
    anchoring claims like 'when did the evolution cycle last run?'
    to real mtimes instead of fabricated timestamps."""
    targets = {
        "evolution_track_db": "memory/evolution_track.db",
        "dream_proposals_db": "memory/dream_proposals.db",
        "wonderings_db": "memory/wonderings.db",
        "audit_log_db": "memory/audit_log.db",
        "pending_cards_db": "memory/pending_cards.db",
        "identity_ledger_db": "memory/identity_ledger.db",
        "cognition_log": "logs/cognition.log",
        "progress_md": "PROGRESS.md",
        "maez_notes_md": "logs/maez_notes.md",
    }
    out: dict[str, str] = {}
    for key, rel in targets.items():
        p = _MAEZ_HOME / rel
        if not p.exists():
            out[key] = "missing"
            continue
        try:
            m = p.stat().st_mtime
            out[key] = time.strftime("%Y-%m-%d %H:%M", time.localtime(m))
        except OSError:
            out[key] = "stat_error"
    return out


# ── public API ─────────────────────────────────────────────────────────

def describe() -> dict[str, Any]:
    """Return a structured snapshot of what Maez has on this system.
    Regenerated each call — reflects current state, not import-time."""
    return {
        "modules": _list_modules(),
        "services": _list_services(),
        "schedules": dict(_STATIC_SCHEDULES),
        "disabled_features": dict(_DISABLED_FEATURES),
        "recent_activity": _recent_activity(),
        "memory_counts": _memory_counts(),
        "home": str(_MAEZ_HOME),
    }


def prompt_snippet() -> str:
    """Compact, prompt-suitable rendering of the registry. Kept short
    (<800 chars) so it doesn't bloat every turn's context. The closing
    instruction is the load-bearing part — tells the model what to do
    when a claim isn't grounded here."""
    d = describe()
    services_active = sorted([
        k for k, v in d["services"].items() if v == "active"
        and not k.startswith("_")
    ])
    services_inactive = sorted([
        k for k, v in d["services"].items() if v != "active"
        and not k.startswith("_")
    ])
    modules = ", ".join(d["modules"])
    disabled = ", ".join(
        f"{k} ({v.split(';')[0]})" for k, v in d["disabled_features"].items()
    ) or "(none)"
    ev = d["recent_activity"].get("evolution_track_db", "?")
    dr = d["recent_activity"].get("dream_proposals_db", "?")
    cog = d["recent_activity"].get("cognition_log", "?")

    mc = d.get("memory_counts") or {}
    mem_line = (
        f"Memory: {mc.get('raw', 0):,} raw, {mc.get('daily', 0):,} "
        f"daily, {mc.get('core', 0):,} core "
        f"(total {mc.get('total', 0):,}). "
        "Use THIS number if asked 'how many memories do you have'. "
        "Do NOT guess or round."
        if mc else ""
    )

    base = (
        "# CAPABILITIES (source of truth for self-description)\n"
        f"Modules on disk: {modules}.\n"
        f"Services active: {', '.join(services_active) or '(none)'}.\n"
        f"Services inactive/stopped: {', '.join(services_inactive) or '(none)'}.\n"
        f"Disabled features: {disabled}.\n"
        "Schedules: 30-second reasoning cycle; daily consolidation at "
        "03:00 local; nightly journal at 23:00 local; curiosity check-in "
        "at 21:00 local; dreams are event-triggered (AFK), not scheduled.\n"
        f"Last evolution db write: {ev}. Last dream db write: {dr}. "
        f"Last cognition log write: {cog}.\n"
        + (f"{mem_line}\n" if mem_line else "")
        + "INSTRUCTION: If the user asks about a module, feature, schedule, "
        "or service NOT listed above, respond with honest uncertainty "
        "(\"I don't have that recorded\" / \"I can't verify that\"). "
        "Do NOT invent names, paths, version numbers, or postcondition "
        "details (memory counts, percentages, 'I ran X and it did Y') "
        "that aren't grounded in this list or in a real tool output "
        "from this turn.\n"
    )

    # Append immune-memory block if there's anything to report. Kept
    # separate from the capabilities block because the two blocks have
    # different cadence and different provenance (one is live system
    # state, the other is a record of past mistakes).
    try:
        from core import fabrication_memory as _fab_mem
        fab_snip = _fab_mem.prompt_snippet(days=7, limit=6)
    except Exception:
        fab_snip = ""

    # Append inner-residue block if current level is above threshold.
    # Different provenance again — live transient state shaped by
    # unresolved moments from recent turns. See core/inner_residue.py.
    try:
        from core import inner_residue as _residue
        res_snip = _residue.prompt_snippet()
    except Exception:
        res_snip = ""

    # Append self-model block — Maez's own picture of "how I've been
    # lately" built from cognition.log + wonderings + fabrication memory
    # + residue. Factual, not generative. See core/self_model.py.
    try:
        from core import self_model as _selfmod
        self_snip = _selfmod.prompt_snippet()
    except Exception:
        self_snip = ""

    blocks = [base]
    if fab_snip:
        blocks.append(fab_snip)
    if res_snip:
        blocks.append(res_snip)
    if self_snip:
        blocks.append(self_snip)
    return "\n".join(blocks) + "\n"


def grounded_vocab() -> frozenset[str]:
    """Token-level grounding for the audit detector. Includes module
    dir names, active/inactive service names, and schedule anchor words.
    Does NOT include architecture abstractions — those stay in audit's
    static set (so the registry doesn't have to carry English vocabulary)."""
    d = describe()
    tokens: set[str] = set()
    tokens.update(d["modules"])
    for unit in d["services"]:
        if unit.startswith("_"):
            continue
        tokens.add(unit)
        # also add the bare prefix ("maez-web" → "maez", "web")
        for part in unit.replace(".", "-").split("-"):
            if part:
                tokens.add(part.lower())
    # Note: disabled features intentionally NOT added as grounded —
    # Maez should NOT claim to have them.
    return frozenset(t.lower() for t in tokens if t)
