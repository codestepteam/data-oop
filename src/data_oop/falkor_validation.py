from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from .falkor import FalkorGraph
from .models import ValidationIssue, ValidationReport
from .validator import NAME_RE


@dataclass(frozen=True)
class FalkorValidationResult:
    run_id: str
    status: str
    checked_instance_count: int
    error_count: int
    warning_count: int
    issue_count: int


@dataclass(frozen=True)
class _ClassInfo:
    name: str


@dataclass(frozen=True)
class _PropertyBindingInfo:
    name: str
    datatype: str
    required: bool
    unique: bool


@dataclass(frozen=True)
class _RelationshipInfo:
    id: str
    name: str
    from_class: str
    to_class: str
    min_count: int
    max_count: int | None
    required: bool


# Validation history is intentionally not versioned.
# Every run deletes previous ValidationRun/ValidationIssue nodes and leaves only
# the latest result so the graph always shows current problems against current TBox.
# TBox definitions are grouped with the :TBox label. ABox nodes are not grouped
# with a common :ABox label; they are identified by their domain class label and
# must carry a uuid property.
def run_latest_falkor_abox_validation(
    *,
    graph: FalkorGraph,
    run_id: str | None = None,
) -> FalkorValidationResult:
    """Validate local ABox nodes against the current TBox and store only latest issues.

    Assumptions:
    - ABox node labels match ClassDef.name.
    - ABox nodes must have a uuid property.
    - All ClassDef nodes define concrete ABox labels which are validated.
    """

    issues: list[ValidationIssue] = []
    checked_instance_count = 0

    classes = _load_classes(graph)

    for class_info in classes:
        label = _safe_identifier(class_info.name, "class")

        checked_instance_count += _count_instances(graph, label)
        for row in _query_rows(
            graph,
            f"MATCH (n:{label}) WHERE n.uuid IS NULL RETURN ID(n) LIMIT 1000",
        ):
            issues.append(
                _issue(
                    code="missing_node_uuid",
                    severity="error",
                    message=f"{class_info.name} node must have uuid",
                    class_name=class_info.name,
                    instance_uuid=f"internal:{row[0]}",
                    property_name="uuid",
                )
            )

        property_bindings = _load_effective_property_bindings(graph, class_info.name)
        for binding in property_bindings:
            prop = _safe_identifier(binding.name, "property")
            if binding.required:
                rows = _query_rows(
                    graph,
                    f"""
                    MATCH (n:{label})
                    WHERE n.{prop} IS NULL
                    RETURN n.uuid, ID(n)
                    LIMIT 1000
                    """,
                )
                for row in rows:
                    instance_uuid = _instance_uuid(row)
                    issues.append(
                        _issue(
                            code="missing_required_property",
                            severity="error",
                            message=(
                                f"{class_info.name}.{binding.name} is required "
                                "but missing"
                            ),
                            class_name=class_info.name,
                            instance_uuid=instance_uuid,
                            property_name=binding.name,
                        )
                    )
            if binding.unique:
                rows = _query_rows(
                    graph,
                    f"""
                    MATCH (n:{label})
                    WHERE n.{prop} IS NOT NULL
                    WITH n.{prop} AS value, count(n) AS cnt
                    WHERE cnt > 1
                    RETURN value, cnt
                    LIMIT 1000
                    """,
                )
                for value, count in rows:
                    issues.append(
                        _issue(
                            code="duplicate_unique_property",
                            severity="error",
                            message=(
                                f"{class_info.name}.{binding.name} must be unique "
                                f"but value appears {count} times"
                            ),
                            class_name=class_info.name,
                            property_name=binding.name,
                            metadata={"value": value, "count": count},
                        )
                    )

        for relationship in _load_outgoing_relationships(graph, class_info.name):
            rel_type = _safe_identifier(relationship.name, "relationship")
            to_label = _safe_identifier(relationship.to_class, "class")
            min_count = max(relationship.min_count, 1 if relationship.required else 0)
            if min_count > 0:
                rows = _query_rows(
                    graph,
                    f"""
                    MATCH (n:{label})
                    OPTIONAL MATCH (n)-[r:{rel_type}]->(m:{to_label})
                    WITH n, count(m) AS cnt
                    WHERE cnt < $min_count
                    RETURN n.uuid, ID(n), cnt
                    LIMIT 1000
                    """,
                    {"min_count": min_count},
                )
                for row in rows:
                    instance_uuid = _instance_uuid(row)
                    issues.append(
                        _issue(
                            code="relationship_min_count_violation",
                            severity="error",
                            message=(
                                f"{class_info.name} requires at least {min_count} "
                                f"{relationship.name} relationship(s) to "
                                f"{relationship.to_class}"
                            ),
                            class_name=class_info.name,
                            instance_uuid=instance_uuid,
                            relationship_name=relationship.name,
                            metadata={"count": row[2], "min_count": min_count},
                        )
                    )
            if relationship.max_count is not None:
                rows = _query_rows(
                    graph,
                    f"""
                    MATCH (n:{label})
                    OPTIONAL MATCH (n)-[r:{rel_type}]->(m:{to_label})
                    WITH n, count(m) AS cnt
                    WHERE cnt > $max_count
                    RETURN n.uuid, ID(n), cnt
                    LIMIT 1000
                    """,
                    {"max_count": relationship.max_count},
                )
                for row in rows:
                    instance_uuid = _instance_uuid(row)
                    issues.append(
                        _issue(
                            code="relationship_max_count_violation",
                            severity="error",
                            message=(
                                f"{class_info.name} allows at most "
                                f"{relationship.max_count} {relationship.name} "
                                f"relationship(s) to {relationship.to_class}"
                            ),
                            class_name=class_info.name,
                            instance_uuid=instance_uuid,
                            relationship_name=relationship.name,
                            metadata={
                                "count": row[2],
                                "max_count": relationship.max_count,
                            },
                        )
                    )

    return store_latest_validation_report(
        graph=graph,
        report=ValidationReport(tuple(issues)),
        run_id=run_id,
        checked_instance_count=checked_instance_count,
    )


def connect_and_run_latest_falkor_abox_validation(
    *,
    graph_name: str = "data_oop",
    host: str = "localhost",
    port: int = 6380,
    username: str | None = None,
    password: str | None = None,
    run_id: str | None = None,
) -> FalkorValidationResult:
    """Connect to FalkorDB, run ABox validation, and persist latest result only."""

    from falkordb import FalkorDB

    db = FalkorDB(host=host, port=port, username=username, password=password)
    graph = db.select_graph(graph_name)
    return run_latest_falkor_abox_validation(graph=graph, run_id=run_id)


def store_latest_validation_report(
    *,
    graph: FalkorGraph,
    report: ValidationReport,
    run_id: str | None = None,
    checked_instance_count: int = 0,
) -> FalkorValidationResult:
    """Replace all previous validation state with the given report."""

    _clear_validation_state(graph)
    now = _now()
    final_run_id = run_id or f"validation_{uuid4().hex}"
    error_count = len(report.errors())
    warning_count = len(report.warnings())
    status = "failed" if error_count else "passed"

    graph.query(
        """
        CREATE (:ValidationRun {
            uuid: $uuid,
            id: $id,
            status: $status,
            startedAt: $started_at,
            finishedAt: $finished_at,
            checkedInstanceCount: $checked_instance_count,
            errorCount: $error_count,
            warningCount: $warning_count
        })
        """,
        {
            "uuid": str(uuid4()),
            "id": final_run_id,
            "status": status,
            "started_at": now,
            "finished_at": now,
            "checked_instance_count": checked_instance_count,
            "error_count": error_count,
            "warning_count": warning_count,
        },
    )

    for index, issue in enumerate(report.issues, start=1):
        _create_validation_issue(graph, final_run_id, issue, index)

    return FalkorValidationResult(
        run_id=final_run_id,
        status=status,
        checked_instance_count=checked_instance_count,
        error_count=error_count,
        warning_count=warning_count,
        issue_count=len(report.issues),
    )


def _clear_validation_state(graph: FalkorGraph) -> None:
    # Delete relationships first to avoid relying on DETACH DELETE support.
    for query in (
        "MATCH (:ValidationRun)-[r]->() DELETE r",
        "MATCH (:ValidationRun)<-[r]-() DELETE r",
        "MATCH (:ValidationIssue)-[r]->() DELETE r",
        "MATCH (:ValidationIssue)<-[r]-() DELETE r",
        "MATCH (n:ValidationIssue) DELETE n",
        "MATCH (n:ValidationRun) DELETE n",
    ):
        graph.query(query)


def _create_validation_issue(
    graph: FalkorGraph,
    run_id: str,
    issue: ValidationIssue,
    index: int,
) -> None:
    issue_id = f"{run_id}_issue_{index}"
    class_name = issue.metadata.get("className")
    instance_uuid = issue.metadata.get("instanceUuid")
    property_name = issue.metadata.get("propertyName")
    relationship_name = issue.metadata.get("relationshipName")
    graph.query(
        """
        MATCH (run:ValidationRun {id: $run_id})
        CREATE (issue:ValidationIssue {
            uuid: $uuid,
            id: $id,
            code: $code,
            severity: $severity,
            className: $class_name,
            instanceUuid: $instance_uuid,
            propertyName: $property_name,
            relationshipName: $relationship_name,
            message: $message,
            targetKind: $target_kind,
            targetId: $target_id,
            createdAt: $created_at
        })
        CREATE (run)-[:HAS_ISSUE]->(issue)
        """,
        {
            "uuid": str(uuid4()),
            "run_id": run_id,
            "id": issue_id,
            "code": issue.code,
            "severity": issue.severity,
            "class_name": class_name,
            "instance_uuid": instance_uuid,
            "property_name": property_name,
            "relationship_name": relationship_name,
            "message": issue.message,
            "target_kind": issue.target_kind,
            "target_id": issue.target_id,
            "created_at": _now(),
        },
    )
    if class_name and instance_uuid and NAME_RE.match(str(class_name)):
        graph.query(
            f"""
            MATCH (issue:ValidationIssue {{id: $issue_id}})
            MATCH (node:{class_name} {{uuid: $instance_uuid}})
            MERGE (issue)-[:AFFECTS]->(node)
            """,
            {"issue_id": issue_id, "instance_uuid": instance_uuid},
        )


def _load_classes(graph: FalkorGraph) -> list[_ClassInfo]:
    rows = _query_rows(
        graph,
        "MATCH (c:ClassDef) RETURN c.name ORDER BY c.name",
    )
    return [_ClassInfo(name=row[0]) for row in rows]


def _load_effective_property_bindings(
    graph: FalkorGraph, class_name: str
) -> list[_PropertyBindingInfo]:
    rows = []
    rows.extend(
        _query_rows(
            graph,
            """
            MATCH (c:ClassDef {name: $class_name})-[b:HAS_PROPERTY]->(p:PropertyDef)
            RETURN p.name, p.datatype, b.required, b.unique
            """,
            {"class_name": class_name},
        )
    )
    rows.extend(
        _query_rows(
            graph,
            """
            MATCH (c:ClassDef {name: $class_name})-[:IMPLEMENTS]->(:InterfaceDef)-[b:HAS_PROPERTY]->(p:PropertyDef)
            RETURN p.name, p.datatype, b.required, b.unique
            """,
            {"class_name": class_name},
        )
    )
    merged: dict[str, _PropertyBindingInfo] = {}
    for name, datatype, required, unique in rows:
        existing = merged.get(name)
        merged[name] = _PropertyBindingInfo(
            name=name,
            datatype=datatype or "unknown",
            required=bool(required) or bool(existing.required if existing else False),
            unique=bool(unique) or bool(existing.unique if existing else False),
        )
    return sorted(merged.values(), key=lambda value: value.name)


def _load_outgoing_relationships(
    graph: FalkorGraph, class_name: str
) -> list[_RelationshipInfo]:
    rows = _query_rows(
        graph,
        """
        MATCH (r:RelationshipDef)-[f:FROM_CLASS]->(from:ClassDef {name: $class_name})
        MATCH (r)-[:TO_CLASS]->(to:ClassDef)
        RETURN r.id, r.name, from.name, to.name, f.minCount, f.maxCount, f.required
        """,
        {"class_name": class_name},
    )
    return [
        _RelationshipInfo(
            id=row[0],
            name=row[1],
            from_class=row[2],
            to_class=row[3],
            min_count=int(row[4] or 0),
            max_count=None if row[5] is None else int(row[5]),
            required=bool(row[6]),
        )
        for row in rows
    ]


def _count_instances(graph: FalkorGraph, label: str) -> int:
    rows = _query_rows(graph, f"MATCH (n:{label}) RETURN count(n)")
    return int(rows[0][0]) if rows else 0


def _query_rows(
    graph: FalkorGraph,
    query: str,
    params: dict[str, object] | None = None,
) -> list[list[Any]]:
    result = graph.query(query, params)
    return list(getattr(result, "result_set", []) or [])


def _safe_identifier(value: str, kind: str) -> str:
    if not NAME_RE.match(value):
        raise ValueError(f"Unsafe {kind} identifier: {value}")
    return value


def _instance_uuid(row: list[Any]) -> str:
    if row and row[0] is not None:
        return str(row[0])
    if len(row) > 1:
        return f"internal:{row[1]}"
    return "unknown"


def _issue(
    *,
    code: str,
    severity: str,
    message: str,
    class_name: str | None = None,
    instance_uuid: str | None = None,
    property_name: str | None = None,
    relationship_name: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> ValidationIssue:
    issue_metadata = dict(metadata or {})
    if class_name is not None:
        issue_metadata["className"] = class_name
    if instance_uuid is not None:
        issue_metadata["instanceUuid"] = instance_uuid
    if property_name is not None:
        issue_metadata["propertyName"] = property_name
    if relationship_name is not None:
        issue_metadata["relationshipName"] = relationship_name
    return ValidationIssue(
        code=code,
        severity=severity,  # type: ignore[arg-type]
        message=message,
        target_kind="class" if class_name else "edge",
        target_id=class_name or relationship_name or property_name or "validation",
        metadata=issue_metadata,
    )


def _now() -> str:
    return datetime.now(UTC).isoformat()
