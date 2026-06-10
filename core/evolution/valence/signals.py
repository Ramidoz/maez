"""Valence v0 input contracts. Synthetic in tests; live readers are v0.1."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AuditSignals:
    rail_fired: bool = False
    fabrication_flagged: bool = False
    correction_needed: bool = False


@dataclass(frozen=True)
class WantSignals:
    resolved: int = 0
    blocked: int = 0
    stale: int = 0
    backlog: int = 0
    backlog_grew: bool = False


@dataclass(frozen=True)
class ContinuitySignals:
    unexpected_gap: bool = False
    memory_loss: bool = False
    capsule_expected: bool = False
    capsule_present: bool = False
