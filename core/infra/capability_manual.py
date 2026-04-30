# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Capability manual loader + validator (Step 1 of the Decision-19/20
capability-acquisition pipeline arc).

Reads the markdown files under ``docs/maez_manual/``, parses YAML
front-matter via PyYAML, returns structured ``CapabilityEntry``
records with the body markdown preserved, and validates against the
schema rules from BAD §19.

This module is the substrate. Step 2 (gap matcher) consumes the
loaded entries; the matcher / evaluator / proposal generator
orchestration is NOT in this module.

Public API:

  load_capability(path)       -> CapabilityEntry          single file
  load_manual(root)           -> ManualLoadResult         whole directory
  validate_capability(entry,
                      repo_root=None,
                      manual_ids=None)
                              -> list[CapabilityValidationIssue]

Exit criteria: real manual loads with zero errors; warnings are
meaningful, not noise.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml

logger = logging.getLogger(__name__)


_VALID_STATUS: frozenset[str] = frozenset({
    "stable", "experimental", "deprecated", "aspirational",
})
_VALID_ACQUISITION: frozenset[str] = frozenset({
    "self-dev", "peer-fetch", "owner-install", "external-service",
})
_VALID_COVENANT_TOUCH: frozenset[str] = frozenset({
    "low", "medium", "high",
})

_REQUIRED_FIELDS: tuple[str, ...] = (
    "capability_id", "title", "status", "gap_signals",
    "prerequisites", "acquisition", "covenant", "conflicts_with",
    "reference_papers", "implementation_files",
)

# Front-matter delimiters: standard `---\n...---\n`. Trailing
# newline after the closing `---` is optional so files without a
# final newline don't mysteriously fail (audit fix).
_FRONT_MATTER_RE = re.compile(
    r"\A---\s*\n(?P<front>.*?)\n---\s*(?:\n(?P<body>.*))?\Z",
    re.DOTALL,
)


# ── exceptions ─────────────────────────────────────────────────────


class CapabilityManualError(Exception):
    """Raised when a manual entry cannot be loaded at all (missing
    front-matter, malformed YAML, missing capability_id). For
    less-fatal issues, use ``CapabilityValidationIssue`` instead."""


# ── dataclasses ────────────────────────────────────────────────────


@dataclass
class CapabilityCovenant:
    """The covenant block of a capability entry. Flat mapping;
    fields are kebab-case in YAML, snake_case in Python."""
    consent_card_required: bool = False
    exact_phrase_ratification: bool = False
    covenant_touch: str = "low"


@dataclass
class CapabilityEntry:
    """One parsed manual entry. The body markdown is preserved
    verbatim — the matcher/evaluator will need it."""
    capability_id: str
    title: str
    status: str
    gap_signals: list[str]
    prerequisites: list[str]
    external_prerequisites: list[str]
    acquisition: str
    covenant: CapabilityCovenant
    conflicts_with: list[str]
    reference_papers: list[str]
    implementation_files: list[str]
    body: str
    source_path: Path
    superseded_by: str | None = None
    raw_front_matter: dict = field(default_factory=dict)


@dataclass
class CapabilityValidationIssue:
    """One validation finding. ``severity='error'`` means CLI exits
    nonzero; ``warning`` means meaningful-but-tolerated."""
    capability_id: str
    code: str
    severity: Literal["error", "warning"]
    message: str


@dataclass
class ManualLoadResult:
    """Result of loading a whole manual directory. Holds every
    successfully-parsed entry plus the validation issues found
    during cross-entry checks (duplicate IDs, dangling refs)."""
    entries: list[CapabilityEntry]
    errors: list[CapabilityValidationIssue]
    warnings: list[CapabilityValidationIssue]

    def find_by_id(self, capability_id: str) -> CapabilityEntry | None:
        """Returns the entry with the given id, or None on miss.
        Pipeline gap-matcher uses this routinely; never raises."""
        for e in self.entries:
            if e.capability_id == capability_id:
                return e
        return None


# ── single-file loader ─────────────────────────────────────────────


def _split_front_matter(text: str) -> tuple[dict, str]:
    """Split a markdown file into ``(front_matter_dict, body)``.
    Raises ``CapabilityManualError`` on missing or malformed
    front-matter."""
    m = _FRONT_MATTER_RE.match(text)
    if not m:
        raise CapabilityManualError(
            "missing or malformed front-matter (expected `---\\n…---\\n` block)"
        )
    raw = m.group("front")
    body = m.group("body") or ""
    try:
        fm = yaml.safe_load(raw) or {}
    except yaml.YAMLError as e:
        raise CapabilityManualError(f"front-matter YAML parse failed: {e}") from e
    if not isinstance(fm, dict):
        raise CapabilityManualError(
            f"front-matter must be a YAML mapping, got {type(fm).__name__}"
        )
    return fm, body


def _build_covenant(raw: Any) -> CapabilityCovenant:
    """Construct a CapabilityCovenant from the front-matter
    ``covenant`` block, accepting only the flat-mapping form. The
    list-of-mappings form was rejected during the 2026-04-30 audit."""
    if not isinstance(raw, dict):
        # Validation will surface this as an error; build a default
        # covenant so the entry can still be inspected.
        return CapabilityCovenant()
    return CapabilityCovenant(
        consent_card_required=raw.get("consent-card-required", False),
        exact_phrase_ratification=raw.get(
            "exact-phrase-ratification", False,
        ),
        covenant_touch=str(raw.get("covenant-touch", "low")),
    )


def load_capability(path: Path | str) -> CapabilityEntry:
    """Read a single manual entry file. Raises
    ``CapabilityManualError`` if the file can't be parsed at all
    (missing front-matter, missing capability_id). Less-fatal issues
    surface through ``validate_capability`` instead."""
    p = Path(path)
    # utf-8-sig strips a BOM if present; vanilla utf-8 reading would
    # leave the BOM as an invisible first character and the
    # front-matter regex would fail (audit fix).
    text = p.read_text(encoding="utf-8-sig")
    fm, body = _split_front_matter(text)

    cid = fm.get("capability_id")
    if not isinstance(cid, str) or not cid:
        raise CapabilityManualError(
            f"{p}: missing or empty capability_id in front-matter"
        )

    def _list(field_name: str) -> list[str]:
        v = fm.get(field_name) or []
        if isinstance(v, list):
            return [str(x) for x in v]
        return []

    return CapabilityEntry(
        capability_id=cid,
        title=str(fm.get("title", "")),
        status=str(fm.get("status", "")),
        gap_signals=_list("gap_signals"),
        prerequisites=_list("prerequisites"),
        external_prerequisites=_list("external_prerequisites"),
        acquisition=str(fm.get("acquisition", "")),
        covenant=_build_covenant(fm.get("covenant")),
        conflicts_with=_list("conflicts_with"),
        reference_papers=_list("reference_papers"),
        implementation_files=_list("implementation_files"),
        body=body,
        source_path=p,
        superseded_by=(
            str(fm["superseded_by"])
            if isinstance(fm.get("superseded_by"), str)
            and fm["superseded_by"]
            else None
        ),
        raw_front_matter=fm,
    )


# ── per-entry validation ───────────────────────────────────────────


def validate_capability(
    entry: CapabilityEntry,
    *,
    repo_root: Path | None = None,
    manual_ids: set[str] | None = None,
) -> list[CapabilityValidationIssue]:
    """Per-entry validation. Cross-entry checks (duplicate IDs,
    superseded_by resolution) live in ``load_manual``.

    ``repo_root`` enables the implementation_files existence check.
    ``manual_ids`` enables the internal-prerequisite presence check.
    Both are optional — single-entry tests pass without them.
    """
    issues: list[CapabilityValidationIssue] = []
    cid = entry.capability_id

    def _err(code: str, msg: str) -> None:
        issues.append(CapabilityValidationIssue(
            capability_id=cid, code=code, severity="error", message=msg,
        ))

    def _warn(code: str, msg: str) -> None:
        issues.append(CapabilityValidationIssue(
            capability_id=cid, code=code, severity="warning", message=msg,
        ))

    # filename stem must match capability_id.
    if entry.source_path.stem != cid:
        _err(
            "filename_mismatch",
            f"file '{entry.source_path.name}' does not match "
            f"capability_id '{cid}'",
        )

    # required-field presence.
    for field_name in _REQUIRED_FIELDS:
        if field_name not in entry.raw_front_matter:
            _err(
                "missing_required_field",
                f"required field '{field_name}' missing from front-matter",
            )

    # status enum.
    if entry.status not in _VALID_STATUS:
        _err(
            "status_invalid",
            f"status '{entry.status}' not in {sorted(_VALID_STATUS)}",
        )

    # acquisition enum.
    if entry.acquisition not in _VALID_ACQUISITION:
        _err(
            "acquisition_invalid",
            f"acquisition '{entry.acquisition}' not in "
            f"{sorted(_VALID_ACQUISITION)}",
        )

    # gap_signals non-empty list of non-empty strings.
    if not entry.gap_signals:
        _err(
            "gap_signals_empty",
            "gap_signals must be a non-empty list",
        )
    else:
        for i, sig in enumerate(entry.gap_signals):
            if not isinstance(sig, str) or not sig.strip():
                _err(
                    "gap_signal_empty_string",
                    f"gap_signals[{i}] is empty or non-string",
                )

    # covenant block — type-check the parsed values.
    cov_raw = entry.raw_front_matter.get("covenant")
    if not isinstance(cov_raw, dict):
        _err(
            "covenant_not_mapping",
            "covenant must be a flat YAML mapping (not a list)",
        )
    else:
        if not isinstance(cov_raw.get("consent-card-required"), bool):
            _err(
                "consent_card_required_not_bool",
                "covenant.consent-card-required must be a boolean",
            )
        if not isinstance(cov_raw.get("exact-phrase-ratification"), bool):
            _err(
                "exact_phrase_ratification_not_bool",
                "covenant.exact-phrase-ratification must be a boolean",
            )
        if entry.covenant.covenant_touch not in _VALID_COVENANT_TOUCH:
            _err(
                "covenant_touch_invalid",
                f"covenant.covenant-touch '{entry.covenant.covenant_touch}' "
                f"not in {sorted(_VALID_COVENANT_TOUCH)}",
            )

    # implementation_files existence (skipped for aspirational status).
    if repo_root is not None and entry.status != "aspirational":
        for rel in entry.implementation_files:
            target = repo_root / rel
            if not target.exists():
                _err(
                    "implementation_file_missing",
                    f"implementation_files entry '{rel}' does not exist "
                    f"under {repo_root}",
                )

    # internal prerequisites — manual-driven check (warning).
    if manual_ids is not None:
        for pre in entry.prerequisites:
            if pre not in manual_ids:
                _warn(
                    "missing_internal_prerequisite",
                    f"prerequisite '{pre}' is not present as a manual entry. "
                    "Move to external_prerequisites if it lives in code.",
                )

    return issues


# ── manual-level loader ────────────────────────────────────────────


def load_manual(
    root: Path | str | None = None,
) -> ManualLoadResult:
    """Load every ``*.md`` entry under ``root``. Default root is
    ``<repo>/docs/maez_manual``. The README is excluded by name.

    Returns a ``ManualLoadResult`` with parsed entries plus all
    validation issues split into errors and warnings.
    """
    if root is None:
        root = Path(__file__).resolve().parent.parent.parent / "docs" / "maez_manual"
    root = Path(root)

    entries: list[CapabilityEntry] = []
    errors: list[CapabilityValidationIssue] = []
    warnings: list[CapabilityValidationIssue] = []

    seen_ids: dict[str, list[Path]] = {}

    for path in sorted(root.glob("*.md")):
        if path.name.lower() == "readme.md":
            continue
        try:
            entry = load_capability(path)
        except CapabilityManualError as e:
            errors.append(CapabilityValidationIssue(
                capability_id=path.stem, code="load_failed",
                severity="error", message=str(e),
            ))
            continue
        entries.append(entry)
        seen_ids.setdefault(entry.capability_id, []).append(path)

    # Cross-entry: duplicate IDs.
    for cid, paths in seen_ids.items():
        if len(paths) > 1:
            errors.append(CapabilityValidationIssue(
                capability_id=cid, code="duplicate_capability_id",
                severity="error",
                message=(
                    f"capability_id '{cid}' appears in multiple files: "
                    + ", ".join(p.name for p in paths)
                ),
            ))

    manual_ids = {e.capability_id for e in entries}

    # Per-entry validation, with cross-entry context.
    repo_root = root.parent.parent  # docs/maez_manual → repo root
    for entry in entries:
        for issue in validate_capability(
            entry, repo_root=repo_root, manual_ids=manual_ids,
        ):
            (errors if issue.severity == "error" else warnings).append(issue)

    # superseded_by must resolve to a real capability_id.
    for entry in entries:
        if entry.superseded_by and entry.superseded_by not in manual_ids:
            errors.append(CapabilityValidationIssue(
                capability_id=entry.capability_id,
                code="superseded_by_unresolved",
                severity="error",
                message=(
                    f"superseded_by '{entry.superseded_by}' does not "
                    "resolve to any capability_id in the manual"
                ),
            ))

    return ManualLoadResult(
        entries=entries, errors=errors, warnings=warnings,
    )


def find_by_id(
    capability_id: str, *, root: Path | str | None = None,
) -> CapabilityEntry | None:
    """Module-level convenience wrapper. Loads the manual and
    returns the entry with ``capability_id``, or None on miss.

    Cheap callers prefer ``load_manual().find_by_id(...)`` to avoid
    repeated load. This wrapper exists for spec parity and one-off
    interactive use."""
    return load_manual(root).find_by_id(capability_id)


__all__ = [
    "CapabilityCovenant",
    "CapabilityEntry",
    "CapabilityManualError",
    "CapabilityValidationIssue",
    "ManualLoadResult",
    "find_by_id",
    "load_capability",
    "load_manual",
    "validate_capability",
]
