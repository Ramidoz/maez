# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Maez per-turn trace emission — structured JSONL traces.

Slice 1 of the trace harness work (`docs/HANDOFF-2026-04-28.md`):
this package writes one JSONL line per owner-bridge /message turn so a
deterministic trace harness, semantic judge, or cockpit replay tool can
later consume them without scraping mixed log lines.

Naming note: this package is `core.turn_traces`, NOT
`core.observability`. `core.observability` already exists as a Phase 3
shim that delegates to `core.cognition.observability` (Langfuse-style
cognitive spans). Different concern — that module instruments LLM
calls; this one emits an end-to-end record per /message turn. Names
disambiguated to keep both alive.

Field names lean OpenTelemetry-friendly so an export adapter can map
to OTel GenAI spans when the spec stabilizes; nothing here depends on
a tracing SDK today.
"""
from core.turn_traces.trace_schema import (
    AuditInfo,
    Trace,
    ToolCall,
    new_trace_id,
)
from core.turn_traces.trace_writer import TraceWriter, default_writer

__all__ = [
    "AuditInfo",
    "Trace",
    "ToolCall",
    "TraceWriter",
    "default_writer",
    "new_trace_id",
]
