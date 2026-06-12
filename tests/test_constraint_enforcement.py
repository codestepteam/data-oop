from __future__ import annotations

from typing import Any

from data_oop.falkor.validation import (
    _check_class_constraints,
    _check_relationship_constraints,
    _compile_range,
    _ConstraintInfo,
)


class FakeResult:
    def __init__(self, rows: list[list[Any]] | None = None) -> None:
        self.result_set = rows or []


class FakeGraph:
    """Pattern-matching fake: maps a substring of the compacted query to rows."""

    def __init__(self, routes: list[tuple[str, list[list[Any]]]]) -> None:
        self.routes = routes
        self.calls: list[str] = []

    def query(
        self,
        q: str,
        params: dict[str, object] | None = None,
        timeout: int | None = None,
    ) -> FakeResult:
        compact = " ".join(q.split())
        self.calls.append(compact)
        for needle, rows in self.routes:
            if needle in compact:
                return FakeResult(rows)
        return FakeResult([])

    def delete(self) -> None:  # FalkorGraph protocol
        pass


def _constraint_row(
    id: str,
    kind: str,
    target_kind: str,
    target_id: str,
    property_names: list[str],
    expression: str | None,
    severity: str = "error",
) -> list[Any]:
    return [id, kind, target_kind, target_id, property_names, expression, severity]


def test_regex_constraint_reports_mismatch() -> None:
    graph = FakeGraph(
        [
            (
                "targetKind: 'class', targetId: $class_name",
                [_constraint_row("c1", "regex", "class", "Person", ["email"], r"[^@]+@[^@]+")],
            ),
            (
                "WHERE n.email IS NOT NULL RETURN n.uuid, ID(n), n.email",
                [["u1", 1, "valid@example.com"], ["u2", 2, "not-an-email"]],
            ),
        ]
    )
    issues = _check_class_constraints(graph, "Person", "Person")
    assert [i.code for i in issues] == ["constraint_regex_violation"]
    assert issues[0].metadata["instanceUuid"] == "u2"
    assert issues[0].metadata["constraintId"] == "c1"


def test_range_constraint_reports_out_of_bounds() -> None:
    graph = FakeGraph(
        [
            (
                "targetKind: 'class', targetId: $class_name",
                [_constraint_row("c2", "range", "class", "Person", ["age"], "0..150", "warning")],
            ),
            (
                "WHERE n.age IS NOT NULL RETURN n.uuid, ID(n), n.age",
                [["u1", 1, 30], ["u2", 2, 200], ["u3", 3, -1]],
            ),
        ]
    )
    issues = _check_class_constraints(graph, "Person", "Person")
    assert [i.code for i in issues] == [
        "constraint_range_violation",
        "constraint_range_violation",
    ]
    assert {i.metadata["instanceUuid"] for i in issues} == {"u2", "u3"}
    assert all(i.severity == "warning" for i in issues)


def test_composite_unique_constraint_reports_duplicates() -> None:
    graph = FakeGraph(
        [
            (
                "targetKind: 'class', targetId: $class_name",
                [
                    _constraint_row(
                        "c3", "composite_unique", "class", "Person", ["first", "last"], None
                    )
                ],
            ),
            (
                "WITH n.first AS v0, n.last AS v1, count(n) AS cnt",
                [["Kim", "Lee", 2]],
            ),
        ]
    )
    issues = _check_class_constraints(graph, "Person", "Person")
    assert [i.code for i in issues] == ["constraint_composite_unique_violation"]
    assert issues[0].metadata["values"] == {"first": "Kim", "last": "Lee"}
    assert issues[0].metadata["count"] == 2


def test_required_constraint_via_property_target() -> None:
    graph = FakeGraph(
        [
            (
                "MATCH (con:TBox:ConstraintDef {targetKind: 'property'})",
                [_constraint_row("c4", "required", "property", "name", [], None)],
            ),
            (
                "WHERE n.name IS NULL RETURN n.uuid, ID(n)",
                [["u9", 9]],
            ),
        ]
    )
    issues = _check_class_constraints(graph, "Person", "Person")
    # Property-target constraint loads via both the direct and interface HAS_PROPERTY
    # paths but is deduplicated by id, so exactly one violation per instance.
    assert [i.code for i in issues] == ["constraint_required_violation"]
    assert issues[0].metadata["propertyName"] == "name"


def test_unknown_constraint_kind_surfaces_not_enforced_info() -> None:
    graph = FakeGraph(
        [
            (
                "targetKind: 'class', targetId: $class_name",
                [_constraint_row("c5", "expression", "class", "Person", ["age"], "age > 0")],
            ),
        ]
    )
    issues = _check_class_constraints(graph, "Person", "Person")
    assert [i.code for i in issues] == ["constraint_not_enforced"]
    assert issues[0].severity == "info"


def test_invalid_regex_expression_surfaces_warning() -> None:
    graph = FakeGraph(
        [
            (
                "targetKind: 'class', targetId: $class_name",
                [_constraint_row("c6", "regex", "class", "Person", ["email"], "[unclosed")],
            ),
        ]
    )
    issues = _check_class_constraints(graph, "Person", "Person")
    assert [i.code for i in issues] == ["constraint_invalid_expression"]
    assert issues[0].severity == "warning"


def test_relationship_constraint_on_edge_property() -> None:
    graph = FakeGraph(
        [
            (
                "MATCH (con:TBox:ConstraintDef {targetKind: 'relationship'})",
                [
                    _constraint_row(
                        "c7", "range", "relationship", "rel_x", ["ordinal"], ">=0"
                    )
                    + ["HAS_TABLE", "Database", "Table"]
                ],
            ),
            (
                "MATCH (:Database)-[r:HAS_TABLE]->(:Table) WHERE r.ordinal IS NOT NULL",
                [["e1", 3], ["e2", -2]],
            ),
        ]
    )
    issues = _check_relationship_constraints(graph)
    assert [i.code for i in issues] == ["constraint_range_violation"]
    assert issues[0].metadata["instanceUuid"] == "e2"


def test_range_expression_grammar() -> None:
    def compile_expr(expr: str):
        return _compile_range(
            _ConstraintInfo("x", "range", "class", "C", ("p",), expr, "error")
        )

    bounds = compile_expr("0..10")
    assert bounds is not None
    assert bounds(0) and bounds(10) and bounds("5")
    assert not bounds(-1) and not bounds(11) and not bounds("abc") and not bounds(None)

    low_only = compile_expr("5..")
    assert low_only is not None
    assert low_only(5) and low_only(1000) and not low_only(4)

    cmp_expr = compile_expr(">= 3")
    assert cmp_expr is not None
    assert cmp_expr(3) and not cmp_expr(2)

    assert compile_expr("nonsense") is None
    assert compile_expr("..") is None
