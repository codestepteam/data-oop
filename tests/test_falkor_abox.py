from __future__ import annotations

from typing import Any

import pytest

from data_oop import upsert_abox_node, upsert_abox_relationship, clear_abox_nodes, delete_abox_element


class FakeResult:
    def __init__(self, rows: list[list[Any]] | None = None) -> None:
        self.result_set = rows or []


class FakeGraph:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object] | None]] = []

    def query(
        self,
        q: str,
        params: dict[str, object] | None = None,
        timeout: int | None = None,
    ) -> FakeResult:
        self.calls.append((q, params))
        compact = " ".join(q.split())
        if "MATCH (c:TBox:ClassDef" in compact:
            return FakeResult([[1]])
        if "MATCH (r:TBox:RelationshipDef" in compact:
            return FakeResult([[1]])
        if "RETURN count(n)" in compact:
            return FakeResult([[3]])
        return FakeResult([["ok"]])


def test_upsert_abox_node_uses_domain_label_and_uuid_without_abox_label() -> None:
    graph = FakeGraph()

    # fire_triggers=False keeps this a focused unit test of the MERGE query shape;
    # trigger dispatch has its own coverage in test_triggers.py.
    result = upsert_abox_node(
        graph=graph,
        class_name="SalesChannel",
        uuid="channel-naver-smartstore",
        properties={
            "channel_code": "NAVER_SMARTSTORE",
            "name": "Naver Smartstore",
        },
        fire_triggers=False,
    )

    assert result.uuid == "channel-naver-smartstore"
    query = graph.calls[-1][0]
    params = graph.calls[-1][1]
    assert "MERGE (n:SalesChannel {uuid: $uuid})" in query
    assert ":ABox" not in query
    assert params is not None
    assert params["uuid"] == "channel-naver-smartstore"
    assert "NAVER_SMARTSTORE" in params.values()


def test_upsert_abox_node_rejects_unsafe_class_name() -> None:
    graph = FakeGraph()

    with pytest.raises(ValueError):
        upsert_abox_node(
            graph=graph,
            class_name="Bad Label",
            uuid="bad",
            properties={},
        )


def test_upsert_abox_relationship_checks_tbox_relationship_and_uses_uuid() -> None:
    graph = FakeGraph()

    result = upsert_abox_relationship(
        graph=graph,
        from_class="Product",
        from_uuid="product-1",
        relationship_name="LISTED_ON",
        to_class="SalesChannel",
        to_uuid="channel-naver-smartstore",
    )

    assert result.relationship_name == "LISTED_ON"
    query = graph.calls[-1][0]
    params = graph.calls[-1][1]
    assert "MATCH (from_node:Product {uuid: $from_uuid})" in query
    assert "MATCH (to_node:SalesChannel {uuid: $to_uuid})" in query
    assert "MERGE (from_node)-[r:LISTED_ON]->(to_node)" in query
    assert params is not None
    assert params["from_uuid"] == "product-1"
    assert params["to_uuid"] == "channel-naver-smartstore"


def test_clear_abox_nodes_deletes_non_tbox_nodes() -> None:
    graph = FakeGraph()

    deleted_count = clear_abox_nodes(graph=graph)

    assert deleted_count == 3
    assert len(graph.calls) == 2
    
    # First call: count non-TBox nodes
    count_query = graph.calls[0][0]
    assert "RETURN count(n)" in count_query
    assert "NOT n:TBox" in count_query
    
    # Second call: delete non-TBox nodes
    delete_query = graph.calls[1][0]
    assert "DETACH DELETE n" in delete_query
    assert "NOT n:TBox" in delete_query


def test_delete_abox_element_relationship() -> None:
    class RelFakeGraph(FakeGraph):
        def query(self, q: str, params: dict[str, object] | None = None, timeout: int | None = None) -> FakeResult:
            self.calls.append((q, params))
            compact = " ".join(q.split())
            if "RETURN count(r)" in compact:
                return FakeResult([[1]])
            if "RETURN count(n)" in compact:
                return FakeResult([[0]])
            return FakeResult([["ok"]])

    graph = RelFakeGraph()
    nodes, rels = delete_abox_element(graph=graph, uuid="rel-uuid")
    assert nodes == 0
    assert rels == 1
    assert any("DELETE r" in q for q, _ in graph.calls)


def test_delete_abox_element_node() -> None:
    class NodeFakeGraph(FakeGraph):
        def query(self, q: str, params: dict[str, object] | None = None, timeout: int | None = None) -> FakeResult:
            self.calls.append((q, params))
            compact = " ".join(q.split())
            if "RETURN count(r)" in compact:
                return FakeResult([[0]])
            if "RETURN count(n)" in compact:
                return FakeResult([[1]])
            return FakeResult([["ok"]])

    graph = NodeFakeGraph()
    nodes, rels = delete_abox_element(graph=graph, uuid="node-uuid")
    assert nodes == 1
    assert rels == 0
    assert any("DETACH DELETE n" in q for q, _ in graph.calls)
