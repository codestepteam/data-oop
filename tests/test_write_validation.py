from __future__ import annotations

from typing import Any

import pytest

from data_oop import upsert_abox_node, upsert_abox_relationship
from data_oop.exceptions import ABoxValidationError


class FakeResult:
    def __init__(self, rows: list[list[Any]] | None = None) -> None:
        self.result_set = rows or []


class FakeGraph:
    """Routes a substring of the compacted query to canned rows."""

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

    def delete(self) -> None:
        pass


CLASS_EXISTS = ("MATCH (c:TBox:ClassDef", [[1]])
NODE_NOT_EXISTS = ("RETURN count(n)", [[0]])


def _binding_route(rows: list[list[Any]]) -> tuple[str, list[list[Any]]]:
    return ("MATCH (c:ClassDef {name: $class_name})-[b:HAS_PROPERTY]->", rows)


def test_create_missing_required_property_raises() -> None:
    graph = FakeGraph(
        [
            CLASS_EXISTS,
            _binding_route([["name", "string", True, False]]),
            NODE_NOT_EXISTS,
        ]
    )
    with pytest.raises(ABoxValidationError, match="Person.name is required"):
        upsert_abox_node(
            graph=graph,
            class_name="Person",
            uuid="p1",
            properties={},
            fire_triggers=False,
        )


def test_create_with_required_property_passes() -> None:
    graph = FakeGraph(
        [
            CLASS_EXISTS,
            _binding_route([["name", "string", True, False]]),
            NODE_NOT_EXISTS,
        ]
    )
    result = upsert_abox_node(
        graph=graph,
        class_name="Person",
        uuid="p1",
        properties={"name": "Kim"},
        fire_triggers=False,
    )
    assert result.uuid == "p1"


def test_update_partial_props_does_not_require_all() -> None:
    graph = FakeGraph(
        [
            CLASS_EXISTS,
            _binding_route([["name", "string", True, False], ["age", "integer", False, False]]),
            ("MATCH (n:Person {uuid: $uuid}) RETURN count(n)", [[1]]),
        ]
    )
    result = upsert_abox_node(
        graph=graph,
        class_name="Person",
        uuid="p1",
        properties={"age": 30},
        fire_triggers=False,
    )
    assert result.uuid == "p1"


def test_update_setting_required_to_null_raises() -> None:
    graph = FakeGraph(
        [
            CLASS_EXISTS,
            _binding_route([["name", "string", True, False]]),
            ("MATCH (n:Person {uuid: $uuid}) RETURN count(n)", [[1]]),
        ]
    )
    with pytest.raises(ABoxValidationError, match="cannot be set to null"):
        upsert_abox_node(
            graph=graph,
            class_name="Person",
            uuid="p1",
            properties={"name": None},
            fire_triggers=False,
        )


def test_datatype_mismatch_raises() -> None:
    graph = FakeGraph(
        [
            CLASS_EXISTS,
            _binding_route([["age", "integer", False, False]]),
            NODE_NOT_EXISTS,
        ]
    )
    with pytest.raises(ABoxValidationError, match="must be of type integer"):
        upsert_abox_node(
            graph=graph,
            class_name="Person",
            uuid="p1",
            properties={"age": "thirty"},
            fire_triggers=False,
        )


def test_unique_property_conflict_raises() -> None:
    graph = FakeGraph(
        [
            CLASS_EXISTS,
            _binding_route([["email", "string", False, True]]),
            ("MATCH (n:Person {uuid: $uuid}) RETURN count(n)", [[0]]),
            ("WHERE n.email = $value AND n.uuid <> $uuid", [[1]]),
        ]
    )
    with pytest.raises(ABoxValidationError, match="must be unique"):
        upsert_abox_node(
            graph=graph,
            class_name="Person",
            uuid="p1",
            properties={"email": "a@b.com"},
            fire_triggers=False,
        )


def test_error_severity_range_constraint_blocks_write() -> None:
    graph = FakeGraph(
        [
            CLASS_EXISTS,
            NODE_NOT_EXISTS,
            (
                "targetKind: 'class', targetId: $class_name",
                [["c_age", "range", "class", "Person", ["age"], "0..150", "error"]],
            ),
        ]
    )
    with pytest.raises(ABoxValidationError, match="violates range constraint c_age"):
        upsert_abox_node(
            graph=graph,
            class_name="Person",
            uuid="p1",
            properties={"age": 200},
            fire_triggers=False,
        )


def test_warning_severity_constraint_does_not_block_write() -> None:
    graph = FakeGraph(
        [
            CLASS_EXISTS,
            NODE_NOT_EXISTS,
            (
                "targetKind: 'class', targetId: $class_name",
                [["c_age", "range", "class", "Person", ["age"], "0..150", "warning"]],
            ),
        ]
    )
    result = upsert_abox_node(
        graph=graph,
        class_name="Person",
        uuid="p1",
        properties={"age": 200},
        fire_triggers=False,
    )
    assert result.uuid == "p1"


def test_relationship_max_count_exceeded_raises() -> None:
    graph = FakeGraph(
        [
            ("RETURN f.maxCount", [[1]]),
            ("MATCH (r:TBox:RelationshipDef", [[1]]),
            ("WHERE t.uuid <> $to_uuid RETURN count(r)", [[1]]),
        ]
    )
    with pytest.raises(ABoxValidationError, match="allows at most 1"):
        upsert_abox_relationship(
            graph=graph,
            from_class="Person",
            from_uuid="p1",
            relationship_name="WORKS_FOR",
            to_class="Org",
            to_uuid="o2",
        )


def test_relationship_within_max_count_passes() -> None:
    graph = FakeGraph(
        [
            ("RETURN f.maxCount", [[2]]),
            ("MATCH (r:TBox:RelationshipDef", [[1]]),
            ("WHERE t.uuid <> $to_uuid RETURN count(r)", [[1]]),
        ]
    )
    result = upsert_abox_relationship(
        graph=graph,
        from_class="Person",
        from_uuid="p1",
        relationship_name="WORKS_FOR",
        to_class="Org",
        to_uuid="o2",
    )
    assert result.relationship_name == "WORKS_FOR"
