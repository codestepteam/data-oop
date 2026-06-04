"""data_oop — dynamic TBox/ABox ontology over FalkorDB + an external RDB tier.

Public API (import from ``data_oop``), grouped by area:

- **ABox read** — ``abox_query`` (read-only Cypher → rows), ``connect_and_abox_query``.
- **On-demand views** — ``resolve_view`` (live RDB table, Redis-cached), ``connect_and_resolve_view``.
- **ABox write** — ``upsert_abox_node`` / ``upsert_abox_relationship`` / ``delete_abox_element`` / ``clear_abox_nodes`` (+ ``connect_and_*``).
- **RDB sync** — ``materialize_source`` (+ ``connect_and_*``); executor registry ``register_executor`` / ``get_executor`` / ``fetch_rows``.
- **Workflow / triggers** — ``save_workflow`` / ``run_workflow``; ``analyze_trigger_graph`` / ``validate_trigger_graph`` / ``dispatch_triggers``.
- **Validation** — ``run_latest_falkor_abox_validation`` (+ ``connect_and_*``), ``store_latest_validation_report``.
- **TBox load / dump** — ``load_tbox_to_falkor`` (+ ``connect_and_*``), ``dump_graph_to_file`` / ``restore_graph_from_file``.
- **Schema** — ``FalkorTBoxRepository`` (live CRUD), ``TBoxRepository`` (protocol), ``InMemoryTBoxRepository``; ``TBoxBuilder`` DSL.
- **Models** — ``ViewDef`` / ``ConnectorDef`` / ``ClassDef`` / ... dataclasses.

Functions with a ``connect_and_`` prefix open the FalkorDB connection themselves
(``host/port/graph_name/username/password`` kwargs) — use them when you do not already
hold a graph handle (e.g. an external MCP server). The plain forms take a ``graph``.

Discovery from the import side:
- ``data_oop.describe_api()`` — print every public symbol grouped, with live signatures.
- ``help(data_oop.abox_query)`` / ``inspect.signature(...)`` — per-symbol detail.
- ``data_oop.__all__`` — the full export list.
- ``py.typed`` ships, so IDEs give autocomplete + inline signatures natively.

See ``docs/USAGE.md`` for worked examples.
"""

from data_oop.exceptions import (
    TBoxAlreadyExistsError,
    TBoxConflictError,
    TBoxError,
    TBoxNotFoundError,
    TBoxValidationError,
)
from data_oop.falkor.graph import (
    FalkorLoadResult,
    connect_and_load_tbox_to_falkor,
    load_tbox_to_falkor,
    dump_graph_to_file,
    restore_graph_from_file,
)
from data_oop.falkor.repository import FalkorTBoxRepository
from data_oop.falkor.abox import (
    ABoxNodeResult,
    ABoxRelationshipResult,
    connect_and_upsert_abox_node,
    upsert_abox_node,
    upsert_abox_relationship,
    clear_abox_nodes,
    connect_and_clear_abox_nodes,
    delete_abox_element,
    connect_and_delete_abox_element,
)
from data_oop.falkor.validation import (
    FalkorValidationResult,
    connect_and_run_latest_falkor_abox_validation,
    run_latest_falkor_abox_validation,
    store_latest_validation_report,
)
from data_oop.rdb.connectors import fetch_rows, get_executor, register_executor
from data_oop.rdb.sync import (
    connect_and_materialize_source,
    materialize_source,
)
from data_oop.rdb.views import resolve_view, connect_and_resolve_view
from data_oop.falkor.query import abox_query, connect_and_abox_query
from data_oop.workflow.workflows import save_workflow, run_workflow, WorkflowBuilder
from data_oop.workflow.triggers import (
    MAX_TRIGGER_DEPTH,
    TriggerGraphReport,
    analyze_trigger_graph,
    dispatch_triggers,
    validate_trigger_graph,
)
from data_oop.schema.dsl import (
    ClassBuilder,
    TBoxBuilder,
)
from data_oop.memory import InMemoryTBoxRepository
from data_oop.schema.models import (
    ClassDef,
    ConnectorDef,
    ConstraintDef,
    EffectiveClassSchema,
    EffectivePropertyDef,
    EffectiveRelationshipSchema,
    InterfaceDef,
    MaterializeResult,
    PropertyBinding,
    PropertyDef,
    RelationshipDef,
    SourceBinding,
    SourceLink,
    TriggerDef,
    ValidationIssue,
    ValidationReport,
    ViewDef,
    ViewParam,
)
from data_oop.schema.repository import TBoxRepository
from data_oop.schema.validator import SUPPORTED_DATATYPES, TBoxValidator


# Display order + label for each source module; anything else falls under "기타".
_API_GROUPS = (
    ("falkor.query", "ABox read — Cypher query"),
    ("rdb.views", "On-demand views (live RDB table)"),
    ("falkor.abox", "ABox write — nodes & relationships"),
    ("rdb.sync", "RDB source sync (materialized)"),
    ("rdb.connectors", "RDB executor registry"),
    ("workflow.workflows", "Workflows"),
    ("workflow.triggers", "Triggers"),
    ("falkor.validation", "Validation"),
    ("falkor.graph", "TBox load / DB dump"),
    ("falkor.repository", "Schema repository (FalkorDB, live)"),
    ("schema.repository", "Schema repository (protocol)"),
    ("memory", "Schema repository (in-memory)"),
    ("schema.dsl", "DSL builders"),
    ("schema.validator", "TBox validator"),
    ("schema.models", "Data models (dataclasses)"),
    ("exceptions", "Exceptions"),
)


def describe_api(*, verbose: bool = False) -> None:
    """Print the public API grouped by area, with live signatures.

    For each exported symbol: a function prints its call signature, a dataclass its
    fields, a class/constant just its name — followed by the first docstring line
    (``verbose=True`` prints the whole docstring). Generated by introspection, so it
    never drifts from the code. ``data_oop.__all__`` is the raw export list; this is the
    human-readable map.
    """
    import dataclasses
    import inspect
    from collections import defaultdict

    label = dict(_API_GROUPS)
    order = {mod: i for i, (mod, _) in enumerate(_API_GROUPS)}

    buckets: dict[str, list[tuple[str, object]]] = defaultdict(list)
    for name in __all__:
        if name == "describe_api":
            continue
        obj = globals()[name]
        mod = getattr(obj, "__module__", "") or ""
        mod = mod[len("data_oop."):] if mod.startswith("data_oop.") else "기타"
        buckets[mod].append((name, obj))

    def _signature(obj: object) -> str:
        if dataclasses.is_dataclass(obj):
            return "(" + ", ".join(f.name for f in dataclasses.fields(obj)) + ")"
        if inspect.isfunction(obj):
            try:
                return str(inspect.signature(obj))
            except (TypeError, ValueError):
                return "(...)"
        return ""

    for mod in sorted(buckets, key=lambda m: order.get(m, len(order))):
        print(f"\n## {label.get(mod, '기타')}  [{mod}]")
        for name, obj in sorted(buckets[mod]):
            doc = inspect.getdoc(obj) or ""
            # A dataclass with no real docstring yields an auto "Name(field: type, ...)"
            # — redundant with the fields line, so drop it.
            if dataclasses.is_dataclass(obj) and doc.startswith(f"{name}("):
                doc = ""
            print(f"  {name}{_signature(obj)}")
            if doc:
                if verbose:
                    for ln in doc.splitlines():
                        print(f"      {ln}")
                else:
                    print(f"      — {doc.splitlines()[0]}")


__all__ = [
    "ClassDef",
    "ConnectorDef",
    "SourceBinding",
    "SourceLink",
    "MaterializeResult",
    "ViewDef",
    "ViewParam",
    "materialize_source",
    "connect_and_materialize_source",
    "resolve_view",
    "connect_and_resolve_view",
    "abox_query",
    "connect_and_abox_query",
    "register_executor",
    "get_executor",
    "fetch_rows",
    "ConstraintDef",
    "EffectiveClassSchema",
    "EffectivePropertyDef",
    "EffectiveRelationshipSchema",
    "ABoxNodeResult",
    "ABoxRelationshipResult",
    "FalkorLoadResult",
    "FalkorValidationResult",
    "InMemoryTBoxRepository",
    "InterfaceDef",
    "PropertyBinding",
    "PropertyDef",
    "RelationshipDef",
    "SUPPORTED_DATATYPES",
    "TBoxAlreadyExistsError",
    "TBoxConflictError",
    "TBoxError",
    "TBoxNotFoundError",
    "TBoxRepository",
    "FalkorTBoxRepository",
    "TBoxValidationError",
    "TBoxValidator",
    "ValidationIssue",
    "ValidationReport",
    "TBoxBuilder",
    "ClassBuilder",
    "connect_and_load_tbox_to_falkor",
    "connect_and_upsert_abox_node",
    "connect_and_run_latest_falkor_abox_validation",
    "load_tbox_to_falkor",
    "run_latest_falkor_abox_validation",
    "store_latest_validation_report",
    "upsert_abox_node",
    "upsert_abox_relationship",
    "clear_abox_nodes",
    "connect_and_clear_abox_nodes",
    "delete_abox_element",
    "connect_and_delete_abox_element",
    "save_workflow",
    "run_workflow",
    "WorkflowBuilder",
    "TriggerDef",
    "TriggerGraphReport",
    "MAX_TRIGGER_DEPTH",
    "analyze_trigger_graph",
    "validate_trigger_graph",
    "dispatch_triggers",
    "dump_graph_to_file",
    "restore_graph_from_file",
    "describe_api",
]
