from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

OwnerKind = Literal["class", "interface", "relationship"]
TargetKind = Literal["class", "interface", "property", "relationship"]
Severity = Literal["info", "warning", "error"]
ValidationTargetKind = Literal[
    "class", "interface", "property", "relationship", "constraint", "edge"
]
ConnectorKind = Literal["mysql", "postgres", "bigquery"]
# "virtual" is reserved for a future lazy-federation tier; only "materialized" is wired today.
Materialization = Literal["materialized", "virtual"]


@dataclass(frozen=True)
class ClassDef:
    name: str
    label: str | None = None
    description: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class InterfaceDef:
    name: str
    description: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PropertyDef:
    name: str
    datatype: str = "unknown"
    description: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PropertyBinding:
    owner_kind: OwnerKind
    owner_id: str
    property_name: str
    required: bool = False
    unique: bool = False
    nullable: bool = True
    default: Any | None = None
    description: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EffectivePropertyDef:
    property: PropertyDef
    binding: PropertyBinding
    source_kind: OwnerKind
    source_id: str


@dataclass(frozen=True)
class RelationshipDef:
    id: str
    name: str
    from_class: str
    to_class: str
    min_count: int = 0
    max_count: int | None = None
    required: bool = False
    description: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ConstraintDef:
    id: str
    kind: str
    target_kind: TargetKind
    target_id: str
    property_names: tuple[str, ...] = ()
    expression: str | None = None
    severity: Severity = "error"
    description: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ConnectorDef:
    """A reference to an external relational data source.

    ``dsn_ref`` is the NAME of an environment variable holding the real DSN/credentials
    (e.g. "PROD_DB_DSN") — never the literal connection string. Nothing secret is stored
    in the graph, so dumps and restores carry no credentials.
    """

    name: str
    kind: ConnectorKind = "postgres"
    dsn_ref: str = ""
    description: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


LinkDirection = Literal["out", "in"]


@dataclass(frozen=True)
class SourceLink:
    """Wires a materialized source row to an existing graph node via a relationship.

    For each synced row, the value of ``local_key`` is matched against ``target_property``
    on a ``to_class`` node, then a ``relationship_name`` edge is MERGEd. ``direction="out"``
    means source -[rel]-> target; ``"in"`` means target -[rel]-> source. The relationship
    must already be defined in the TBox.
    """

    relationship_name: str
    to_class: str
    local_key: str
    target_property: str = ""  # defaults to local_key when blank
    direction: LinkDirection = "out"


@dataclass(frozen=True)
class SourceBinding:
    """Binds a TBox class to an RDB query that produces its aggregate/segment instances.

    Each result row of ``sql`` becomes one ABox node of ``class_name``. ``key_columns``
    forms the business identity used to keep re-sync idempotent. ``column_map`` renames
    SQL result columns to class property names (identity mapping when empty). ``links``
    optionally wires each row to existing nodes via relationships.
    """

    class_name: str
    connector_name: str
    sql: str
    key_columns: tuple[str, ...] = ()
    column_map: dict[str, str] = field(default_factory=dict)
    materialization: Materialization = "materialized"
    refresh_interval_hours: int | None = None
    links: tuple[SourceLink, ...] = ()


@dataclass(frozen=True)
class ViewParam:
    """A filter accepted by a :class:`ViewDef`. ``required`` params must be supplied at
    resolve time; the rest are optional."""

    name: str
    required: bool = False


@dataclass(frozen=True)
class ViewDef:
    """A named, parameterized RDB query attached to a TBox class. Resolves to a *table*
    (list of rows) on demand: the data lives in the relational source, the graph stores
    only the query spec — connector, SQL, and the filter params it accepts.

    Unlike a materialized ``SourceBinding`` (which copies rows into ABox nodes), a view
    is resolved on demand and never written to the graph. Crucially, a view runs
    **once** and lets the RDB do any aggregation (``GROUP BY``) in a single query, so
    listing/aggregating across many entities never fans out into N round-trips. A
    single-entity lookup is just the same view filtered down to one key.

    ``sql`` uses neutral ``:name`` placeholders (e.g.
    ``"SELECT customer_id, sum(amount) AS revenue FROM orders WHERE tier = :tier"
    " GROUP BY customer_id"``). Values come from caller-supplied ``filters`` at resolve
    time, bound through the driver — never string-formatted into the SQL — so a filter
    value can never become SQL injection. ``params`` declares the accepted filters; a
    ``required`` one must be supplied. ``key_column`` names the result column that
    correlates rows back to this class's ABox nodes — informational only, since the
    graph and the RDB are separate stores and the caller joins them. ``ttl_seconds``
    enables a Redis result cache keyed by view + filters (``None`` = always live).
    """

    name: str
    class_name: str
    connector_name: str
    sql: str
    params: tuple[ViewParam, ...] = ()
    key_column: str | None = None
    ttl_seconds: int | None = None
    description: str | None = None


@dataclass(frozen=True)
class MaterializeResult:
    """Outcome of materializing a source-backed class from its RDB query."""

    class_name: str
    connector_name: str
    rows_fetched: int
    nodes_upserted: int
    nodes_pruned: int
    synced_at: str
    edges_upserted: int = 0
    links_missing: int = 0


@dataclass(frozen=True)
class EffectiveClassSchema:
    class_def: ClassDef
    interfaces: tuple[InterfaceDef, ...]
    properties: tuple[EffectivePropertyDef, ...]
    outgoing_relationships: tuple[RelationshipDef, ...]
    incoming_relationships: tuple[RelationshipDef, ...]
    constraints: tuple[ConstraintDef, ...]


@dataclass(frozen=True)
class EffectiveRelationshipSchema:
    relationship_def: RelationshipDef
    properties: tuple[EffectivePropertyDef, ...]
    constraints: tuple[ConstraintDef, ...]


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    severity: Severity
    message: str
    target_kind: ValidationTargetKind
    target_id: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ValidationReport:
    issues: tuple[ValidationIssue, ...] = ()

    @property
    def valid(self) -> bool:
        return not self.errors()

    def errors(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "error"]

    def warnings(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "warning"]

    def raise_if_invalid(self) -> None:
        if not self.valid:
            from data_oop.exceptions import TBoxValidationError

            raise TBoxValidationError(self)


WorkflowAction = Literal[
    "create_node",
    "create_relationship",
    "run_workflow",
    "fetch_view",
    "transform",
    "abox_query",
    "http_request",
    "materialize_source",
    "db_operation",
]
WorkflowParameterType = Literal[
    "string", "integer", "float", "boolean", "date", "datetime", "email", "url", "phone", "uuid", "array"
]


@dataclass(frozen=True)
class WorkflowParameterDef:
    name: str
    type: WorkflowParameterType
    array_item_type: str | None = None
    array_item_class: str | None = None
    required: bool = True
    description: str | None = None


@dataclass(frozen=True)
class WorkflowStepDef:
    step_id: str
    action: WorkflowAction
    class_name: str | None = None
    properties: dict[str, Any] = field(default_factory=dict)
    uuid: str | None = None
    from_class: str | None = None
    from_uuid: str | None = None
    relationship_name: str | None = None
    to_class: str | None = None
    to_uuid: str | None = None
    if_present: str | None = None
    loop_over: str | None = None
    loop_var: str | None = None
    workflow_name: str | None = None
    # For action="fetch_view": the ViewDef to resolve. The fetched rows are stored in
    # the step's context entry as {"value": [...]} for later steps to reference. The
    # step's interpolated ``parameters`` become the view's filters.
    view_name: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    # For action="transform": return ``value`` when set, otherwise return the
    # interpolated ``parameters`` map. Useful for shaping rows between steps.
    value: Any | None = None
    # For action="abox_query": read-only Cypher query plus bind params in
    # ``parameters``. Results are stored as {"rows": [...]}.
    cypher: str | None = None
    limit: int | None = None
    timeout_ms: int | None = None
    # For action="http_request": outbound HTTP request. ``parameters`` remains
    # available for template interpolation; query/body/header maps get interpolated.
    method: str | None = None
    url: str | None = None
    headers: dict[str, Any] = field(default_factory=dict)
    query: dict[str, Any] = field(default_factory=dict)
    body: Any | None = None
    # For action="materialize_source": optional execution controls.
    prune: bool = True
    max_rows: int | None = None
    # For action="db_operation": name of a code-registered DB operation.
    operation_name: str | None = None


@dataclass(frozen=True)
class WorkflowDef:
    name: str
    steps: tuple[WorkflowStepDef, ...]
    parameters: tuple[WorkflowParameterDef, ...] = ()
    description: str | None = None
    uuid: str | None = None


# A trigger fires when an ABox node of its class is created or updated.
TriggerEvent = Literal["create", "update"]


@dataclass(frozen=True)
class TriggerDef:
    """A class-level callback: when an ABox node of ``class_name`` is created or
    updated, run the workflow ``workflow_name``.

    The callback itself is data, not code — it references a stored
    ``WorkflowDefinition`` so the whole rule lives in FalkorDB.

    When the trigger fires, the **full current node state** (every stored property,
    including ``uuid``) is read from the graph and used as the interpolation
    context. ``parameter_map`` then explicitly states which workflow parameter gets
    which value: each value is a template interpolated against the node, e.g.
    ``{"order_id": "{uuid}", "amount": "{total}", "channel": "naver"}``. Templates
    without braces are literals. When ``parameter_map`` is empty, the node's
    properties are passed through flat as a convenience default.

    ``condition`` is an optional property path on the node; the trigger fires only
    when it resolves to a non-empty value. ``order`` controls execution order among
    triggers sharing the same class and event.
    """

    name: str
    class_name: str
    event: TriggerEvent
    workflow_name: str
    condition: str | None = None
    enabled: bool = True
    order: int = 0
    description: str | None = None
    parameter_map: dict[str, Any] = field(default_factory=dict)
