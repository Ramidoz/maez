from __future__ import annotations


class BondIsolationViolation(PermissionError):
    """Base class for bond-scope boundary violations."""


class CrossBondAccessError(BondIsolationViolation):
    """Raised when a request crosses from one bond scope into another."""


class SubjectBoundaryRefused(BondIsolationViolation):
    """Raised when a curiosity request targets a refused subject class."""


class SubjectKindRefused(BondIsolationViolation):
    """Raised when curiosity creation lacks an allowed subject kind."""
