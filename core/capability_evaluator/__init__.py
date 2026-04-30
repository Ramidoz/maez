# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Phase 3 shim — re-exports core.infra.capability_evaluator.

Directory package (not a flat .py shim) so
``python -m core.capability_evaluator '<query>'`` works through the
sibling ``__main__.py``.
"""
from core.infra.capability_evaluator import (
    CapabilityEvaluation,
    EvaluationReason,
    evaluate_match,
    evaluate_matches,
)

__all__ = [
    "CapabilityEvaluation",
    "EvaluationReason",
    "evaluate_match",
    "evaluate_matches",
]
