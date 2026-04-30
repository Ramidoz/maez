# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Capability integration planner (Step 5a of the Decision-19/20 arc).

Consumes queued acquisition intents from
``capability_acquisition_queue`` and produces a *reviewable* draft
integration plan. This stage does ONE thing: convert approved intent
into an honest plan an owner / Claude pair can review. It does NOT:

  • fetch code, install packages, or run network calls
  • mutate any repo file
  • mutate the queue (no status transition, no row update)
  • call out to Claude-tier or web (Step 5b)
  • pretend the manual's prose is an executable recipe

Hard contract — honesty over completeness:

  When the manual entry doesn't carry enough specificity to draft
  a concrete plan (no implementation file paths, no named
  identifiers in the "How it's acquired" section), the planner
  emits ``status="needs_field_search"`` and
  ``next_action="field_search_required"``. It refuses to fabricate
  certainty. The next slice (5b) decides whether to enrich via
  field search; first-real-implementation (5c+) consumes drafts
  the owner has reviewed.

Public API:

  plan_next(queue, *, queue_id=None, manual_root=None)
      → CapabilityIntegrationPlan | None

  Returns None iff there is no queued row at all (or the explicit
  id targets a non-existent row in the no-queue case). Validation
  failures raise ``IntegrationPlannerError``.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    from core.infra.capability_acquisition_queue import AcquisitionQueue
    from core.infra.capability_manual import CapabilityEntry


# ── exceptions ─────────────────────────────────────────────────────


class IntegrationPlannerError(ValueError):
    """Raised when a queued row cannot be planned: drift between
    queue state and manual, deprecated entry, path containment
    failure, or unknown queue id. Subclasses ValueError so callers
    that already catch ValueError keep working."""


# ── plan dataclass ─────────────────────────────────────────────────


@dataclass
class CapabilityIntegrationPlan:
    """One draft integration plan. Pure function output — not
    persisted in v1. Step 5b/5c may add a planner-store later;
    intentionally kept out of this slice to mirror Step 4's "no
    persistence in v1" stance."""

    plan_id: str
    queue_id: str
    capability_id: str
    created_at: float
    status: str  # "draft" | "needs_field_search"
    source: str  # "manual"
    manual_source_path: str
    acquisition: str

    summary: str
    proposed_files: list[str]
    proposed_tests: list[str]
    required_consents: list[str]
    risks: list[str]
    non_goals: list[str]
    evidence: dict
    next_action: str  # "review_plan" | "field_search_required"
    needs_field_search: bool = False

    # Populated when the planner extracted enough from the manual
    # body to surface a one-line owner-facing summary; never used
    # to fabricate certainty.
    extracted_identifiers: list[str] = field(default_factory=list)

    # ── rendering ──────────────────────────────────────────────────

    def render_text(self) -> str:
        """Owner-facing rendering. The first line is a load-bearing
        disclaimer: the surface MUST tell the operator this is a
        plan, not an installed capability. CLI prints this verbatim."""
        lines: list[str] = []
        lines.append(
            "This is an integration plan, not an implemented capability."
        )
        lines.append("")
        lines.append(f"plan_id:         {self.plan_id}")
        lines.append(f"queue_id:        {self.queue_id}")
        lines.append(f"capability_id:   {self.capability_id}")
        lines.append(f"status:          {self.status}")
        lines.append(f"source:          {self.source}")
        lines.append(f"acquisition:     {self.acquisition}")
        lines.append(f"manual entry:    {self.manual_source_path}")
        lines.append(f"next action:     {self.next_action}")
        lines.append("")
        lines.append("summary:")
        lines.append(f"  {self.summary or '(no summary extracted)'}")
        lines.append("")
        lines.append("proposed files:")
        if self.proposed_files:
            for f_ in self.proposed_files:
                lines.append(f"  - {f_}")
        else:
            lines.append("  (none extracted from manual entry)")
        lines.append("")
        lines.append("proposed tests:")
        if self.proposed_tests:
            for f_ in self.proposed_tests:
                lines.append(f"  - {f_}")
        else:
            lines.append("  (none extracted)")
        lines.append("")
        lines.append("required consents:")
        for c in self.required_consents:
            lines.append(f"  - {c}")
        lines.append("")
        lines.append("risks:")
        if self.risks:
            for r in self.risks:
                lines.append(f"  - {r}")
        else:
            lines.append("  (none extracted)")
        lines.append("")
        lines.append("non-goals:")
        for ng in self.non_goals:
            lines.append(f"  - {ng}")
        lines.append("")
        lines.append("evidence:")
        for k, v in self.evidence.items():
            lines.append(f"  {k}: {v}")
        return "\n".join(lines)


# ── manual body extraction helpers ────────────────────────────────


_FILE_PATH_RE = re.compile(
    r"`?([a-z0-9_]+(?:/[a-z0-9_]+)+\.py)`?", re.IGNORECASE,
)
_IDENTIFIER_IN_BACKTICKS_RE = re.compile(
    r"`([a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*)?)`",
)


def _extract_section(body: str, header: str) -> str:
    """Grab the body of a markdown ## section by header. Match is
    case-insensitive and tolerant of trailing whitespace. Returns
    the empty string when the section is absent."""
    pattern = re.compile(
        rf"^##\s+{re.escape(header)}\s*$\n(.*?)(?=^##\s+|\Z)",
        re.IGNORECASE | re.MULTILINE | re.DOTALL,
    )
    m = pattern.search(body)
    return m.group(1).strip() if m else ""


def _bulleted_or_numbered_lines(section: str) -> list[str]:
    """Pull bullet/numbered list items out of a section. Strips the
    marker and collapses internal whitespace. Empty list when the
    section has no list items (e.g. pure prose)."""
    out: list[str] = []
    for raw in section.splitlines():
        line = raw.strip()
        m = re.match(r"^(?:[-*]|\d+\.)\s+(.*)$", line)
        if m:
            text = re.sub(r"\s+", " ", m.group(1)).strip()
            if text:
                out.append(text)
    return out


def _extract_files(section: str) -> tuple[list[str], list[str]]:
    """Return (proposed_files, proposed_tests) parsed out of a
    section. Tests are paths starting with ``tests/``; everything
    else lands in proposed_files. Order-preserving and de-duped."""
    seen: set[str] = set()
    files: list[str] = []
    tests: list[str] = []
    for m in _FILE_PATH_RE.finditer(section):
        path = m.group(1)
        if path in seen:
            continue
        seen.add(path)
        if path.startswith("tests/"):
            tests.append(path)
        else:
            files.append(path)
    return files, tests


def _extract_identifiers(section: str) -> list[str]:
    """Backtick-quoted identifiers (function/method names). Filters
    out anything that already came through ``_extract_files`` so the
    file-path matches don't double-count as identifiers."""
    seen: set[str] = set()
    out: list[str] = []
    for m in _IDENTIFIER_IN_BACKTICKS_RE.finditer(section):
        ident = m.group(1)
        if "/" in ident or ident.endswith(".py"):
            continue
        if ident in seen:
            continue
        seen.add(ident)
        out.append(ident)
    return out


def _summary_from_body(body: str) -> str:
    """First substantive paragraph after stripping headings. Mirrors
    the body-excerpt shape from capability_proposal so the planner's
    summary line reads consistently with the proposal card."""
    stripped = re.sub(r"^#{1,6}\s+.*$", "", body, flags=re.MULTILINE)
    paragraphs = [p.strip() for p in stripped.split("\n\n")]
    for para in paragraphs:
        if para and not para.startswith("#"):
            return re.sub(r"\s+", " ", para).strip()
    return ""


# ── core planning ─────────────────────────────────────────────────


def _build_plan(
    *,
    row: dict,
    entry: "CapabilityEntry",
) -> CapabilityIntegrationPlan:
    """Assemble the plan dataclass from a validated (row, entry)
    pair. Determinism axis: same inputs → same plan modulo
    plan_id and created_at."""
    body = entry.body or ""
    how = _extract_section(body, "How it's acquired")
    risks_section = _extract_section(body, "What can go wrong")

    body_files, body_tests = _extract_files(body)
    how_files, how_tests = _extract_files(how)

    # Prefer manual-declared implementation_files (most authoritative);
    # fall back to whatever the body names. how_* gets priority over
    # generic body_* because "How it's acquired" is the section the
    # author wrote with implementation in mind.
    if entry.implementation_files:
        proposed_files = list(entry.implementation_files)
        proposed_tests: list[str] = []
        for f_ in proposed_files[:]:
            if f_.startswith("tests/"):
                proposed_tests.append(f_)
                proposed_files.remove(f_)
    else:
        proposed_files = how_files or body_files
        proposed_tests = how_tests or body_tests

    identifiers = _extract_identifiers(how) or _extract_identifiers(body)
    risks = _bulleted_or_numbered_lines(risks_section)
    if not risks and risks_section:
        # Section exists but isn't a list — fall back to the first
        # paragraph so the owner sees *something* honest from the
        # manual rather than a fabricated risk list.
        first = re.sub(r"\s+", " ", risks_section.split("\n\n")[0]).strip()
        if first:
            risks = [first]

    # Concreteness gate. Without files OR named identifiers, the
    # entry is too vague to draft a real plan; surface that fact
    # rather than fabricating one.
    has_files = bool(proposed_files) or bool(proposed_tests)
    has_identifiers = bool(identifiers)
    needs_field_search = not (has_files or has_identifiers)

    required_consents: list[str] = []
    if entry.covenant.consent_card_required:
        required_consents.append(
            "owner approval via consent card before any file change"
        )
    if entry.covenant.exact_phrase_ratification:
        required_consents.append(
            "exact-phrase ratification at activation time"
        )
    if entry.covenant.covenant_touch in {"medium", "high"}:
        required_consents.append(
            f"covenant-touch={entry.covenant.covenant_touch}: ratification "
            "must document what changes for the owner"
        )

    non_goals = [
        "no code is fetched, installed, or modified by this plan",
        "no queue row is marked completed by this plan",
        "no network or Claude-tier call is made by this plan",
    ]

    summary = _summary_from_body(body)[:600]

    return CapabilityIntegrationPlan(
        plan_id="plan-" + uuid4().hex[:12],
        queue_id=row["id"],
        capability_id=entry.capability_id,
        created_at=time.time(),
        status="needs_field_search" if needs_field_search else "draft",
        source="manual",
        manual_source_path=str(entry.source_path),
        acquisition=entry.acquisition,
        summary=summary,
        proposed_files=proposed_files,
        proposed_tests=proposed_tests,
        required_consents=required_consents,
        risks=risks,
        non_goals=non_goals,
        evidence={
            "queue_id": row["id"],
            "card_request_id": row.get("card_request_id"),
            "proposal_id": row.get("proposal_id"),
            "manual_source_path": str(entry.source_path),
            "manual_status": entry.status,
            "matched_capability_id": entry.capability_id,
        },
        next_action=(
            "field_search_required" if needs_field_search else "review_plan"
        ),
        needs_field_search=needs_field_search,
        extracted_identifiers=identifiers[:10],
    )


# ── revalidation ──────────────────────────────────────────────────


def _is_path_inside(candidate: Path, root: Path) -> bool:
    """True iff ``candidate`` (resolved) is a real file under
    ``root`` (resolved). Mirrors the queue's repo-anchored
    containment check; duplicated here so the planner is
    self-sufficient when a custom manual_root is supplied (tests)."""
    try:
        c = candidate.resolve()
    except (OSError, ValueError):
        return False
    if not c.is_file():
        return False
    try:
        c.relative_to(root.resolve())
        return True
    except (ValueError, OSError):
        return False


def _resolve_manual_root(override: Path | str | None) -> Path:
    if override is not None:
        return Path(override).resolve()
    try:
        from core.infra import paths as _paths
        return (_paths.home() / "docs" / "maez_manual").resolve()
    except Exception:
        # Defensive: refuse the broad ancestor match by returning a
        # non-existent path. Same posture as the queue handler.
        return Path("/dev/null/docs/maez_manual")


def _revalidate(
    row: dict, *, manual_root: Path,
) -> "CapabilityEntry":
    """Apply the full Step 5a revalidation contract. Raises
    ``IntegrationPlannerError`` with a specific message on the first
    failure. Honest error text: tells the owner WHICH check failed."""
    if row["status"] != "queued":
        raise IntegrationPlannerError(
            f"queue row {row['id']!r} has status "
            f"{row['status']!r}; planner only consumes 'queued' rows"
        )
    if row["source"] != "manual":
        raise IntegrationPlannerError(
            f"queue row {row['id']!r} has source {row['source']!r}; "
            "v1 planner only handles 'manual' source"
        )

    manual_path = Path(row["manual_source_path"])
    if not _is_path_inside(manual_path, manual_root):
        raise IntegrationPlannerError(
            f"manual_source_path {str(manual_path)!r} is not under "
            f"{str(manual_root)!r} (or doesn't exist) — refusing to "
            "plan against an unverified manual entry"
        )

    from core.infra.capability_manual import (
        CapabilityManualError, load_capability,
    )
    try:
        entry = load_capability(manual_path)
    except CapabilityManualError as e:
        raise IntegrationPlannerError(
            f"could not load manual entry at {manual_path}: {e}"
        ) from e

    if entry.capability_id != row["capability_id"]:
        raise IntegrationPlannerError(
            f"capability_id drift: queue row says "
            f"{row['capability_id']!r} but manual entry resolves to "
            f"{entry.capability_id!r}"
        )
    if entry.acquisition != row["acquisition"]:
        raise IntegrationPlannerError(
            f"acquisition drift: queue row says "
            f"{row['acquisition']!r} but manual entry says "
            f"{entry.acquisition!r}"
        )
    if entry.status == "deprecated":
        raise IntegrationPlannerError(
            f"manual entry {entry.capability_id!r} is deprecated; "
            "refusing to plan against a deprecated capability"
        )

    return entry


# ── public API ────────────────────────────────────────────────────


def plan_next(
    queue: "AcquisitionQueue",
    *,
    queue_id: str | None = None,
    manual_root: Path | str | None = None,
) -> CapabilityIntegrationPlan | None:
    """Generate an integration plan for one queued acquisition row.

    Selection: ``queue_id`` if supplied; otherwise the oldest row
    whose status is still ``queued``. Returns None when there is no
    queued row to plan and no explicit id was supplied.

    Raises ``IntegrationPlannerError`` on any revalidation failure —
    the planner is the second line of defence after the action
    handler, and refuses silently-broken rows."""
    if queue_id is not None:
        row = queue.get(queue_id)
        if row is None:
            raise IntegrationPlannerError(
                f"no queue row with id {queue_id!r}"
            )
    else:
        open_rows = queue.list_open()
        if not open_rows:
            return None
        # list_open is sorted DESC by created_at; oldest is the last.
        row = open_rows[-1]

    root = _resolve_manual_root(manual_root)
    entry = _revalidate(row, manual_root=root)
    return _build_plan(row=row, entry=entry)


__all__ = [
    "CapabilityIntegrationPlan",
    "IntegrationPlannerError",
    "plan_next",
]
