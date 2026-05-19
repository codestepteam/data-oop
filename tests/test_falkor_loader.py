from __future__ import annotations

from typing import Any

from tbox import InMemoryTBoxRepository, load_tbox_to_falkor


class FakeGraph:
    def __init__(self) -> None:
        self.queries: list[tuple[str, dict[str, object] | None]] = []
        self.deleted = False

    def query(
        self,
        q: str,
        params: dict[str, object] | None = None,
        timeout: int | None = None,
    ) -> Any:
        self.queries.append((q, params))
        return None

    def delete(self) -> None:
        self.deleted = True


def build_sample_tbox() -> InMemoryTBoxRepository:
    repo = InMemoryTBoxRepository()
    repo.create_class("SalesChannel", kind="entity")
    repo.create_property("name", datatype="string")
    repo.attach_property_to_class(
        class_name="SalesChannel",
        property_name="name",
        required=True,
    )
    repo.create_constraint(
        id="sample.channel_name_required",
        kind="required",
        target_kind="class",
        target_id="SalesChannel",
        property_names=("name",),
    )
    return repo


def test_load_tbox_to_falkor_emits_planned_graph_shape() -> None:
    repo = build_sample_tbox()
    graph = FakeGraph()

    result = load_tbox_to_falkor(repo, graph=graph, graph_name="sample_tbox", clear=True)
    all_queries = "\n".join(query for query, _ in graph.queries)

    assert graph.deleted is True
    assert result.graph_name == "sample_tbox"
    assert result.classes == 1
    assert result.properties == 1
    assert result.constraints == 1
    assert result.nodes == 3
    assert result.edges > 0
    assert "n.uuid = $uuid" in all_queries
    assert "n.kind = $kind" in all_queries
    assert ":TBox:ClassDef" in all_queries
    assert "HAS_PROPERTY" in all_queries
    assert "CONSTRAINS" in all_queries
