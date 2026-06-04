from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from data_oop.schema.models import ValidationReport


class TBoxError(Exception):
    """Base exception for TBox library errors."""


class TBoxNotFoundError(TBoxError):
    """Raised when a requested TBox definition does not exist."""


class TBoxAlreadyExistsError(TBoxError):
    """Raised when a definition already exists and merge=False."""


class TBoxConflictError(TBoxError):
    """Raised when a requested operation would create an inconsistent TBox."""


class TBoxValidationError(TBoxError):
    """Raised by ValidationReport.raise_if_invalid()."""

    def __init__(self, report: ValidationReport) -> None:
        self.report = report
        codes = ", ".join(issue.code for issue in report.errors())
        super().__init__(f"TBox validation failed: {codes}")


class TriggerCycleError(TBoxConflictError):
    """Raised when attaching a trigger would create a cycle in the trigger graph
    (an infinite/divergent callback loop).

    ``cycles`` is a list of cycles, each a list of trigger names forming the loop.
    """

    def __init__(self, cycles: list[list[str]]) -> None:
        self.cycles = cycles
        rendered = "; ".join(" -> ".join(cycle) for cycle in cycles)
        super().__init__(f"Trigger cycle detected: {rendered}")
