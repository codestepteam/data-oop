from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import ValidationReport


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
