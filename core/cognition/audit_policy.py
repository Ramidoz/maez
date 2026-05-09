# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Audit trace refusal policy.

Slice 4c.5b keeps projection-influenced rows from becoming audit
evidence. The trace label on ``turns`` is intentionally thin: it is a
refusal token, not a provenance payload. Rich lineage lives in the
diagnostic ``audit_trace_lineage`` table.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Iterable

AUDIT_TRACE_POLICY = "refuse_v1"
TRACE_LABEL_VALUE_SCHEMA = 1
TRACE_METADATA_SHAPE = 1
PROJECTION_INFLUENCED_TRACE_LABEL = "projection_influenced"
LOGGER_NAME = "maez.audit_trace_policy"

_log = logging.getLogger(LOGGER_NAME)

__all__ = [
    "AUDIT_TRACE_POLICY",
    "TRACE_LABEL_VALUE_SCHEMA",
    "TRACE_METADATA_SHAPE",
    "PROJECTION_INFLUENCED_TRACE_LABEL",
    "LOGGER_NAME",
    "GOLDEN_TRACE_PREDICATE_CASES",
    "TraceAuditPolicy",
    "validate_trace_metadata",
]


GOLDEN_TRACE_PREDICATE_CASES = (
    {
        "name": "current_valid",
        "audit_trace_label": PROJECTION_INFLUENCED_TRACE_LABEL,
        "audit_trace_value_schema": TRACE_LABEL_VALUE_SCHEMA,
        "audit_trace_metadata_shape": TRACE_METADATA_SHAPE,
    },
    {
        "name": "null_default",
        "audit_trace_label": None,
        "audit_trace_value_schema": None,
        "audit_trace_metadata_shape": None,
    },
    {
        "name": "wrong_value_schema",
        "audit_trace_label": PROJECTION_INFLUENCED_TRACE_LABEL,
        "audit_trace_value_schema": 2,
        "audit_trace_metadata_shape": TRACE_METADATA_SHAPE,
    },
    {
        "name": "unknown_label",
        "audit_trace_label": "diagnostic_only",
        "audit_trace_value_schema": TRACE_LABEL_VALUE_SCHEMA,
        "audit_trace_metadata_shape": TRACE_METADATA_SHAPE,
    },
)


def validate_trace_metadata(
    *,
    audit_trace_label: str | None,
    audit_trace_value_schema: int | None,
    audit_trace_metadata_shape: int | None,
    audit_trace_lineage: dict | None = None,
) -> None:
    """Validate the current trace-label vocabulary and metadata shape."""
    fields = (
        audit_trace_label,
        audit_trace_value_schema,
        audit_trace_metadata_shape,
    )
    if all(v is None for v in fields):
        if audit_trace_lineage is not None:
            raise ValueError("audit_trace_lineage requires audit_trace label")
        return
    if any(v is None for v in fields):
        raise ValueError("audit_trace metadata must be all set or all NULL")
    if audit_trace_label != PROJECTION_INFLUENCED_TRACE_LABEL:
        raise ValueError(f"unknown audit_trace_label {audit_trace_label!r}")
    if audit_trace_value_schema != TRACE_LABEL_VALUE_SCHEMA:
        raise ValueError(f"audit_trace_value_schema must be {TRACE_LABEL_VALUE_SCHEMA}")
    if audit_trace_metadata_shape != TRACE_METADATA_SHAPE:
        raise ValueError(f"audit_trace_metadata_shape must be {TRACE_METADATA_SHAPE}")
    if audit_trace_lineage is None:
        raise ValueError("audit_trace lineage is required for traced rows")

    required = ("rule_id", "source_ids", "policy_doc_sha256", "applied_at")
    missing = [k for k in required if k not in audit_trace_lineage]
    if missing:
        raise ValueError("audit_trace lineage missing required fields: " + ",".join(missing))
    source_ids = audit_trace_lineage.get("source_ids")
    if not isinstance(source_ids, list) or not source_ids:
        raise ValueError("audit_trace lineage source_ids must be non-empty list")
    if not all(isinstance(s, str) and s for s in source_ids):
        raise ValueError("audit_trace lineage source_ids must be non-empty strings")
    digest = audit_trace_lineage.get("policy_doc_sha256")
    if not isinstance(digest, str) or len(digest) != 64:
        raise ValueError("audit_trace lineage policy_doc_sha256 must be sha256 hex")


@dataclass(frozen=True)
class TraceAuditPolicy:
    """Current audit trace policy.

    ``apply`` is intentionally the one public gate for audit-shaped
    self_history rows. Future policies dispatch from here instead of
    introducing scattered inline conditionals.
    """

    policy_version: str = AUDIT_TRACE_POLICY

    @classmethod
    def current(cls) -> "TraceAuditPolicy":
        return cls()

    def is_trace_labeled(self, row: dict) -> bool:
        return (
            row.get("audit_trace_label") == PROJECTION_INFLUENCED_TRACE_LABEL
            and row.get("audit_trace_value_schema") == TRACE_LABEL_VALUE_SCHEMA
            and row.get("audit_trace_metadata_shape") == TRACE_METADATA_SHAPE
        )

    def apply(
        self,
        rows: Iterable[dict],
        *,
        audit_path: str,
        would_have_consumed_surface: str,
    ) -> list[dict]:
        kept: list[dict] = []
        for row in rows:
            if self.is_trace_labeled(row):
                payload = {
                    "reason": "skipped_trace_labeled",
                    "row_id": row.get("turn_id"),
                    "audit_path": audit_path,
                    "would_have_consumed_surface": would_have_consumed_surface,
                    "policy_version": self.policy_version,
                }
                _log.info("%s", json.dumps(payload, sort_keys=True))
                continue
            kept.append(row)
        return kept
