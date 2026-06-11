"""Want->Pursuit bridge v0.

The bridge seeds work orders into the existing wondering workshop and raises
advisory satisfied-proposals. It writes nothing to the want ledger.
"""

from __future__ import annotations

import logging
from typing import Any

_LOG = logging.getLogger(__name__)

WANT_SOURCE_PREFIX = "want:"
TERMINAL_PROPOSAL_ACTION = "want_terminal_proposal"


def template_question(want_statement: str) -> str:
    return (
        "What bounded, read-only investigation would advance this want: "
        f"{(want_statement or '').strip()}?"
    )


def source_for(want_id: str) -> str:
    return f"{WANT_SOURCE_PREFIX}{want_id}"


def want_id_from_source(source: str) -> str | None:
    value = str(source or "")
    if not value.startswith(WANT_SOURCE_PREFIX):
        return None
    return value[len(WANT_SOURCE_PREFIX) :]


def want_pursuit_trail(wonderings_store: Any, want_id: str) -> list[dict]:
    return wonderings_store.list_by_source(source_for(want_id))
