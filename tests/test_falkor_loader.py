from __future__ import annotations

from typing import Any

from tbox import build_commerce_tbox, load_tbox_to_falkor


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


def test_load_tbox_to_falkor_emits_planned_graph_shape() -> None:
    repo = build_commerce_tbox()
    graph = FakeGraph()

    result = load_tbox_to_falkor(repo, graph=graph, graph_name="commerce_tbox", clear=True)
    all_queries = "\n".join(query for query, _ in graph.queries)

    assert graph.deleted is True
    assert result.graph_name == "commerce_tbox"
    assert result.classes == 7
    assert result.relationships == 6
    assert result.nodes == 54
    assert result.edges > 0
    assert "n.uuid = $uuid" in all_queries
    assert "n.kind = $kind" in all_queries
    assert ":TBox:ClassDef" in all_queries
    assert ":TBox:RelationshipDef" in all_queries
    assert "FROM_CLASS" in all_queries
    assert "TO_CLASS" in all_queries
    assert "HAS_PROPERTY" in all_queries
    assert "CONSTRAINS" in all_queries
