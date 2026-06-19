"""Named DB operation registry for workflow steps.

A named DB operation is code-defined and referenced by name from workflow data. This
keeps raw SQL out of stored workflows while still allowing curated database work such as
lookups, status updates, or sync helpers. Operation callables receive the active TBox
repository, graph handle, and interpolated parameters.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from data_oop.exceptions import TBoxError, TBoxNotFoundError

DbOperation = Callable[..., Any]

_DB_OPERATIONS: dict[str, DbOperation] = {}


def register_db_operation(name: str, operation: DbOperation) -> None:
    """Register a named DB operation callable for workflow execution.

    ``operation`` is called as ``operation(repo=..., graph=..., parameters=...)``.
    Use this for curated DB work instead of storing raw SQL in workflow definitions.
    """
    if not name or not isinstance(name, str):
        raise ValueError("DB operation name must be a non-empty string")
    if not callable(operation):
        raise ValueError("DB operation must be callable")
    _DB_OPERATIONS[name] = operation


def list_db_operations() -> list[str]:
    """Return registered named DB operation names in sorted order."""
    return sorted(_DB_OPERATIONS)


def get_db_operation(name: str) -> DbOperation:
    """Return the callable registered for ``name`` or raise if missing."""
    try:
        return _DB_OPERATIONS[name]
    except KeyError as exc:
        raise TBoxNotFoundError(f"DB operation not registered: {name}") from exc


def execute_db_operation(
    *,
    name: str,
    repo: Any,
    graph: Any,
    parameters: dict[str, Any] | None = None,
) -> Any:
    """Execute named DB operation with active repo/graph and bound parameters."""
    operation = get_db_operation(name)
    try:
        return operation(repo=repo, graph=graph, parameters=parameters or {})
    except TypeError as exc:
        raise TBoxError(
            f"DB operation {name!r} must accept keyword args: repo, graph, parameters"
        ) from exc
