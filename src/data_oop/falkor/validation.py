from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from data_oop.falkor.graph import FalkorGraph
from data_oop.schema.models import ValidationIssue, ValidationReport
from data_oop.schema.validator import NAME_RE

# Per-check row cap. When a check returns this many rows the result may be truncated, so a
# warning issue is emitted rather than silently dropping violations beyond the cap.
CHECK_ROW_LIMIT = 1000


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


@dataclass(frozen=True)
class _ConstraintInfo:
    id: str
    kind: str
    target_kind: str
    target_id: str
    property_names: tuple[str, ...]
    expression: str | None
    severity: str


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
                    LIMIT {CHECK_ROW_LIMIT}
                    """,
                )
                if len(rows) >= CHECK_ROW_LIMIT:
                    issues.append(_truncation_issue(class_info.name, f"required:{binding.name}"))
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

            if binding.datatype and binding.datatype != "unknown" and binding.datatype != "any":
                rows = _query_rows(
                    graph,
                    f"""
                    MATCH (n:{label})
                    WHERE n.{prop} IS NOT NULL
                    RETURN n.uuid, ID(n), n.{prop}
                    LIMIT {CHECK_ROW_LIMIT}
                    """
                )
                if len(rows) >= CHECK_ROW_LIMIT:
                    issues.append(_truncation_issue(class_info.name, f"datatype:{binding.name}"))
                for row in rows:
                    instance_uuid = _instance_uuid(row)
                    val = row[2]
                    is_valid = _validate_value_datatype(val, binding.datatype)
                    if not is_valid:
                        issues.append(
                            _issue(
                                code="invalid_property_datatype",
                                severity="error",
                                message=(
                                    f"{class_info.name}.{binding.name} must be of type {binding.datatype} "
                                    f"but got value: {val} (type: {type(val).__name__})"
                                ),
                                class_name=class_info.name,
                                instance_uuid=instance_uuid,
                                property_name=binding.name,
                                metadata={"value": val, "expected_datatype": binding.datatype},
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
                    LIMIT {CHECK_ROW_LIMIT}
                    """,
                    {"min_count": min_count},
                )
                if len(rows) >= CHECK_ROW_LIMIT:
                    issues.append(_truncation_issue(class_info.name, f"min_count:{relationship.name}"))
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
                    LIMIT {CHECK_ROW_LIMIT}
                    """,
                    {"max_count": relationship.max_count},
                )
                if len(rows) >= CHECK_ROW_LIMIT:
                    issues.append(_truncation_issue(class_info.name, f"max_count:{relationship.name}"))
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

        issues.extend(_check_class_constraints(graph, class_info.name, label))

    issues.extend(_check_relationship_constraints(graph))

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
    # SUBCLASS_OF ancestors contribute their direct and interface bindings too.
    rows.extend(
        _query_rows(
            graph,
            """
            MATCH (c:ClassDef {name: $class_name})-[:SUBCLASS_OF*1..]->(:ClassDef)-[b:HAS_PROPERTY]->(p:PropertyDef)
            RETURN p.name, p.datatype, b.required, b.unique
            """,
            {"class_name": class_name},
        )
    )
    rows.extend(
        _query_rows(
            graph,
            """
            MATCH (c:ClassDef {name: $class_name})-[:SUBCLASS_OF*1..]->(:ClassDef)-[:IMPLEMENTS]->(:InterfaceDef)-[b:HAS_PROPERTY]->(p:PropertyDef)
            RETURN p.name, p.datatype, b.required, b.unique
            """,
            {"class_name": class_name},
        )
    )
    # Intentional narrow projection: validation only needs name/datatype/required/unique,
    # so it OR-merges those rather than reusing schema.effective.merge_effective_properties
    # (which builds full EffectivePropertyDef with nullable/default/metadata).
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


# --- ConstraintDef enforcement -------------------------------------------------
#
# Constraints are declared in the TBox (kind: required / unique / composite_unique /
# regex / range / expression) and enforced here against ABox instances. Values are
# fetched and evaluated in Python (like the datatype checks) so enforcement does not
# depend on Cypher regex/expression dialect support. The generic "expression" kind is
# NOT executed — it would mean evaluating arbitrary code — so it is surfaced as an
# info-level "constraint_not_enforced" issue instead of silently passing.

_CONSTRAINT_RETURN = (
    "RETURN con.id, con.kind, con.targetKind, con.targetId, con.propertyNames, "
    "con.expression, con.severity"
)


def _constraint_from_row(row: list[Any]) -> _ConstraintInfo:
    return _ConstraintInfo(
        id=row[0],
        kind=(row[1] or "").lower(),
        target_kind=row[2],
        target_id=row[3],
        property_names=tuple(row[4] or []),
        expression=row[5],
        severity=row[6] or "error",
    )


def _load_constraints_for_class(
    graph: FalkorGraph, class_name: str
) -> list[_ConstraintInfo]:
    """Constraints applying to a class: targeted directly, via an implemented
    interface, or via a property the class (or its interfaces) binds."""
    rows: list[list[Any]] = []
    rows.extend(
        _query_rows(
            graph,
            "MATCH (con:TBox:ConstraintDef {targetKind: 'class', targetId: $class_name}) "
            + _CONSTRAINT_RETURN,
            {"class_name": class_name},
        )
    )
    rows.extend(
        _query_rows(
            graph,
            """
            MATCH (:ClassDef {name: $class_name})-[:IMPLEMENTS]->(i:InterfaceDef)
            MATCH (con:TBox:ConstraintDef {targetKind: 'interface'})
            WHERE con.targetId = i.name
            """
            + _CONSTRAINT_RETURN,
            {"class_name": class_name},
        )
    )
    # SUBCLASS_OF ancestors: their class-targeted and interface-targeted
    # constraints apply to subclass instances as well.
    rows.extend(
        _query_rows(
            graph,
            """
            MATCH (:ClassDef {name: $class_name})-[:SUBCLASS_OF*1..]->(a:ClassDef)
            MATCH (con:TBox:ConstraintDef {targetKind: 'class'})
            WHERE con.targetId = a.name
            """
            + _CONSTRAINT_RETURN,
            {"class_name": class_name},
        )
    )
    rows.extend(
        _query_rows(
            graph,
            """
            MATCH (:ClassDef {name: $class_name})-[:SUBCLASS_OF*1..]->(:ClassDef)-[:IMPLEMENTS]->(i:InterfaceDef)
            MATCH (con:TBox:ConstraintDef {targetKind: 'interface'})
            WHERE con.targetId = i.name
            """
            + _CONSTRAINT_RETURN,
            {"class_name": class_name},
        )
    )
    for pattern in (
        "MATCH (:ClassDef {name: $class_name})-[:HAS_PROPERTY]->(p:PropertyDef)",
        "MATCH (:ClassDef {name: $class_name})-[:IMPLEMENTS]->(:InterfaceDef)"
        "-[:HAS_PROPERTY]->(p:PropertyDef)",
        "MATCH (:ClassDef {name: $class_name})-[:SUBCLASS_OF*1..]->(:ClassDef)"
        "-[:HAS_PROPERTY]->(p:PropertyDef)",
    ):
        rows.extend(
            _query_rows(
                graph,
                f"""
                {pattern}
                MATCH (con:TBox:ConstraintDef {{targetKind: 'property'}})
                WHERE con.targetId = p.name
                """
                + _CONSTRAINT_RETURN,
                {"class_name": class_name},
            )
        )
    constraints: dict[str, _ConstraintInfo] = {}
    for row in rows:
        info = _constraint_from_row(row)
        constraints[info.id] = info
    return sorted(constraints.values(), key=lambda value: value.id)


def _constraint_properties(constraint: _ConstraintInfo) -> tuple[str, ...]:
    if constraint.target_kind == "property":
        return (constraint.target_id,)
    return constraint.property_names


def _check_class_constraints(
    graph: FalkorGraph, class_name: str, label: str
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for constraint in _load_constraints_for_class(graph, class_name):
        props = _constraint_properties(constraint)
        if constraint.kind == "required":
            for prop_name in props:
                prop = _safe_identifier(prop_name, "property")
                rows = _query_rows(
                    graph,
                    f"""
                    MATCH (n:{label})
                    WHERE n.{prop} IS NULL
                    RETURN n.uuid, ID(n)
                    LIMIT {CHECK_ROW_LIMIT}
                    """,
                )
                if len(rows) >= CHECK_ROW_LIMIT:
                    issues.append(
                        _truncation_issue(class_name, f"constraint:{constraint.id}")
                    )
                for row in rows:
                    issues.append(
                        _constraint_issue(
                            constraint,
                            code="constraint_required_violation",
                            message=(
                                f"{class_name}.{prop_name} is required by constraint "
                                f"{constraint.id} but missing"
                            ),
                            class_name=class_name,
                            instance_uuid=_instance_uuid(row),
                            property_name=prop_name,
                        )
                    )
        elif constraint.kind in ("unique", "composite_unique"):
            if not props:
                continue
            safe = [_safe_identifier(p, "property") for p in props]
            not_null = " AND ".join(f"n.{p} IS NOT NULL" for p in safe)
            projection = ", ".join(f"n.{p} AS v{i}" for i, p in enumerate(safe))
            value_cols = ", ".join(f"v{i}" for i in range(len(safe)))
            rows = _query_rows(
                graph,
                f"""
                MATCH (n:{label})
                WHERE {not_null}
                WITH {projection}, count(n) AS cnt
                WHERE cnt > 1
                RETURN {value_cols}, cnt
                LIMIT {CHECK_ROW_LIMIT}
                """,
            )
            for row in rows:
                values = dict(zip(props, row[:-1]))
                issues.append(
                    _constraint_issue(
                        constraint,
                        code="constraint_composite_unique_violation",
                        message=(
                            f"{class_name} values {values} must be unique "
                            f"(constraint {constraint.id}) but appear {row[-1]} times"
                        ),
                        class_name=class_name,
                        metadata={"values": values, "count": row[-1]},
                    )
                )
        elif constraint.kind == "regex":
            predicate = _compile_regex(constraint)
            if predicate is None:
                issues.append(_invalid_expression_issue(constraint, class_name))
                continue
            issues.extend(
                _check_value_constraint(
                    graph,
                    constraint,
                    class_name=class_name,
                    label=label,
                    props=props,
                    predicate=predicate,
                    code="constraint_regex_violation",
                    describe=f"must match regex {constraint.expression!r}",
                )
            )
        elif constraint.kind == "range":
            predicate = _compile_range(constraint)
            if predicate is None:
                issues.append(_invalid_expression_issue(constraint, class_name))
                continue
            issues.extend(
                _check_value_constraint(
                    graph,
                    constraint,
                    class_name=class_name,
                    label=label,
                    props=props,
                    predicate=predicate,
                    code="constraint_range_violation",
                    describe=f"must be in range {constraint.expression!r}",
                )
            )
        else:
            issues.append(
                _issue(
                    code="constraint_not_enforced",
                    severity="info",
                    message=(
                        f"Constraint {constraint.id} (kind={constraint.kind!r}) on "
                        f"{class_name} is not enforced by ABox validation"
                    ),
                    class_name=class_name,
                    metadata={"constraintId": constraint.id, "kind": constraint.kind},
                )
            )
    return issues


def _check_value_constraint(
    graph: FalkorGraph,
    constraint: _ConstraintInfo,
    *,
    class_name: str,
    label: str,
    props: tuple[str, ...],
    predicate: Any,
    code: str,
    describe: str,
) -> list[ValidationIssue]:
    """Fetch non-null values of each property and report rows failing ``predicate``."""
    issues: list[ValidationIssue] = []
    for prop_name in props:
        prop = _safe_identifier(prop_name, "property")
        rows = _query_rows(
            graph,
            f"""
            MATCH (n:{label})
            WHERE n.{prop} IS NOT NULL
            RETURN n.uuid, ID(n), n.{prop}
            LIMIT {CHECK_ROW_LIMIT}
            """,
        )
        if len(rows) >= CHECK_ROW_LIMIT:
            issues.append(_truncation_issue(class_name, f"constraint:{constraint.id}"))
        for row in rows:
            if predicate(row[2]):
                continue
            issues.append(
                _constraint_issue(
                    constraint,
                    code=code,
                    message=(
                        f"{class_name}.{prop_name} {describe} "
                        f"(constraint {constraint.id}) but got: {row[2]!r}"
                    ),
                    class_name=class_name,
                    instance_uuid=_instance_uuid(row),
                    property_name=prop_name,
                    metadata={"value": row[2]},
                )
            )
    return issues


def _check_relationship_constraints(graph: FalkorGraph) -> list[ValidationIssue]:
    """Enforce required/regex/range constraints on relationship (edge) properties."""
    issues: list[ValidationIssue] = []
    rows = _query_rows(
        graph,
        """
        MATCH (con:TBox:ConstraintDef {targetKind: 'relationship'})
        MATCH (r:TBox:RelationshipDef)-[:FROM_CLASS]->(f:ClassDef)
        MATCH (r)-[:TO_CLASS]->(t:ClassDef)
        WHERE con.targetId = r.id
        RETURN con.id, con.kind, con.targetKind, con.targetId, con.propertyNames,
               con.expression, con.severity, r.name, f.name, t.name
        """,
    )
    for row in rows:
        constraint = _constraint_from_row(row[:7])
        rel_name, from_class, to_class = row[7], row[8], row[9]
        rel_type = _safe_identifier(rel_name, "relationship")
        from_label = _safe_identifier(from_class, "class")
        to_label = _safe_identifier(to_class, "class")
        props = constraint.property_names
        if constraint.kind == "regex":
            predicate = _compile_regex(constraint)
        elif constraint.kind == "range":
            predicate = _compile_range(constraint)
        elif constraint.kind == "required":
            predicate = None
        else:
            issues.append(
                _issue(
                    code="constraint_not_enforced",
                    severity="info",
                    message=(
                        f"Constraint {constraint.id} (kind={constraint.kind!r}) on "
                        f"relationship {rel_name} is not enforced by ABox validation"
                    ),
                    relationship_name=rel_name,
                    metadata={"constraintId": constraint.id, "kind": constraint.kind},
                )
            )
            continue
        if constraint.kind in ("regex", "range") and predicate is None:
            issues.append(_invalid_expression_issue(constraint, from_class))
            continue
        for prop_name in props:
            prop = _safe_identifier(prop_name, "property")
            if constraint.kind == "required":
                edge_rows = _query_rows(
                    graph,
                    f"""
                    MATCH (:{from_label})-[r:{rel_type}]->(:{to_label})
                    WHERE r.{prop} IS NULL
                    RETURN r.uuid
                    LIMIT {CHECK_ROW_LIMIT}
                    """,
                )
                for edge_row in edge_rows:
                    issues.append(
                        _constraint_issue(
                            constraint,
                            code="constraint_required_violation",
                            message=(
                                f"{rel_name}.{prop_name} is required by constraint "
                                f"{constraint.id} but missing"
                            ),
                            instance_uuid=str(edge_row[0]) if edge_row[0] else None,
                            relationship_name=rel_name,
                            property_name=prop_name,
                        )
                    )
                continue
            edge_rows = _query_rows(
                graph,
                f"""
                MATCH (:{from_label})-[r:{rel_type}]->(:{to_label})
                WHERE r.{prop} IS NOT NULL
                RETURN r.uuid, r.{prop}
                LIMIT {CHECK_ROW_LIMIT}
                """,
            )
            for edge_row in edge_rows:
                if predicate is None or predicate(edge_row[1]):
                    continue
                code = (
                    "constraint_regex_violation"
                    if constraint.kind == "regex"
                    else "constraint_range_violation"
                )
                issues.append(
                    _constraint_issue(
                        constraint,
                        code=code,
                        message=(
                            f"{rel_name}.{prop_name} violates constraint "
                            f"{constraint.id} ({constraint.expression!r}); "
                            f"got: {edge_row[1]!r}"
                        ),
                        instance_uuid=str(edge_row[0]) if edge_row[0] else None,
                        relationship_name=rel_name,
                        property_name=prop_name,
                        metadata={"value": edge_row[1]},
                    )
                )
    return issues


def _compile_regex(constraint: _ConstraintInfo) -> Any | None:
    if not constraint.expression:
        return None
    try:
        pattern = re.compile(constraint.expression)
    except re.error:
        return None
    return lambda value: isinstance(value, str) and bool(pattern.fullmatch(value))


# Range expression grammar: "a..b" (inclusive, either bound optional) or a single
# comparison: ">=a", "<=a", ">a", "<a". Non-numeric values fail the constraint.
_RANGE_DOTS_RE = re.compile(r"^\s*(-?\d+(?:\.\d+)?)?\s*\.\.\s*(-?\d+(?:\.\d+)?)?\s*$")
_RANGE_CMP_RE = re.compile(r"^\s*(>=|<=|>|<)\s*(-?\d+(?:\.\d+)?)\s*$")


def _compile_range(constraint: _ConstraintInfo) -> Any | None:
    expr = constraint.expression or ""
    match = _RANGE_DOTS_RE.match(expr)
    if match and (match.group(1) is not None or match.group(2) is not None):
        low = float(match.group(1)) if match.group(1) is not None else None
        high = float(match.group(2)) if match.group(2) is not None else None

        def in_bounds(value: Any) -> bool:
            number = _as_number(value)
            if number is None:
                return False
            if low is not None and number < low:
                return False
            if high is not None and number > high:
                return False
            return True

        return in_bounds
    match = _RANGE_CMP_RE.match(expr)
    if match:
        op, bound_text = match.group(1), float(match.group(2))
        ops = {
            ">=": lambda n: n >= bound_text,
            "<=": lambda n: n <= bound_text,
            ">": lambda n: n > bound_text,
            "<": lambda n: n < bound_text,
        }
        compare = ops[op]

        def satisfies(value: Any) -> bool:
            number = _as_number(value)
            return number is not None and compare(number)

        return satisfies
    return None


def _as_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _constraint_issue(
    constraint: _ConstraintInfo,
    *,
    code: str,
    message: str,
    class_name: str | None = None,
    instance_uuid: str | None = None,
    property_name: str | None = None,
    relationship_name: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> ValidationIssue:
    issue_metadata = dict(metadata or {})
    issue_metadata["constraintId"] = constraint.id
    severity = constraint.severity if constraint.severity in ("info", "warning", "error") else "error"
    return _issue(
        code=code,
        severity=severity,
        message=message,
        class_name=class_name,
        instance_uuid=instance_uuid,
        property_name=property_name,
        relationship_name=relationship_name,
        metadata=issue_metadata,
    )


def _invalid_expression_issue(
    constraint: _ConstraintInfo, class_name: str
) -> ValidationIssue:
    return _issue(
        code="constraint_invalid_expression",
        severity="warning",
        message=(
            f"Constraint {constraint.id} has an invalid {constraint.kind} expression: "
            f"{constraint.expression!r}; it was not enforced"
        ),
        class_name=class_name,
        metadata={"constraintId": constraint.id, "expression": constraint.expression},
    )


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


def _truncation_issue(class_name: str, check: str) -> ValidationIssue:
    """Warning emitted when a check hits ``CHECK_ROW_LIMIT`` — violations past the cap are
    not reported, so the run is incomplete for this class/check."""
    return _issue(
        code="check_truncated",
        severity="warning",
        message=(
            f"{class_name}: '{check}' check hit the {CHECK_ROW_LIMIT}-row cap; "
            "violations beyond it are not reported. Narrow the data or raise the cap."
        ),
        class_name=class_name,
    )


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _validate_value_datatype(val: Any, datatype: str) -> bool:
    if val is None:
        return True
        
    dt = datatype.lower()
    
    if dt in ("string", "str"):
        return isinstance(val, str)
        
    elif dt in ("integer", "int"):
        if isinstance(val, (int, float)):
            if isinstance(val, float):
                return val.is_integer()
            return type(val) is int
        if isinstance(val, str):
            try:
                int(val)
                return True
            except ValueError:
                return False
        return False
        
    elif dt in ("float", "number"):
        if isinstance(val, (int, float)) and type(val) is not bool:
            return True
        if isinstance(val, str):
            try:
                float(val)
                return True
            except ValueError:
                return False
        return False
        
    elif dt in ("boolean", "bool"):
        if isinstance(val, bool):
            return True
        if isinstance(val, (int, float)) and val in (0, 1, 0.0, 1.0):
            return True
        if isinstance(val, str) and val.lower() in ("true", "false", "0", "1"):
            return True
        return False
        
    elif dt == "email":
        if not isinstance(val, str):
            return False
        return bool(re.match(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", val))
        
    elif dt == "url":
        if not isinstance(val, str):
            return False
        return val.startswith(("http://", "https://")) and len(val) > 10
        
    elif dt == "phone":
        if not isinstance(val, (str, int)):
            return False
        val_str = str(val)
        cleaned = re.sub(r"[+\-\s\(\)]", "", val_str)
        return cleaned.isdigit() and len(cleaned) >= 7
        
    elif dt == "date":
        if not isinstance(val, str):
            return False
        cleaned_date = val.replace(".", "-")
        try:
            datetime.strptime(cleaned_date, "%Y-%m-%d")
            return True
        except ValueError:
            pass
        try:
            datetime.fromisoformat(val)
            return True
        except ValueError:
            pass
        return False
        
    elif dt == "datetime":
        if not isinstance(val, str):
            return False
        try:
            datetime.fromisoformat(val.replace("Z", "+00:00"))
            return True
        except ValueError:
            pass
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"):
            try:
                datetime.strptime(val, fmt)
                return True
            except ValueError:
                pass
        return False
        
    elif dt == "uuid":
        if not isinstance(val, str):
            return False
        try:
            uuid.UUID(val)
            return True
        except ValueError:
            return False
            
    elif dt in ("json", "object", "array", "list"):
        if isinstance(val, str):
            if val.strip().startswith(("[", "{")):
                try:
                    import json
                    json.loads(val)
                    return True
                except ValueError:
                    return False
            return False
        return isinstance(val, (dict, list))
        
    return True
