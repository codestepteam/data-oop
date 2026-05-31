import pytest
from falkordb import FalkorDB

from data_oop import (
    FalkorTBoxRepository,
    TBoxNotFoundError,
    materialize_source,
    register_executor,
)

# A controllable in-test executor: each test sets _ROWS, the executor returns them.
_ROWS: list[dict] = []


def _fake_executor(connector, sql):
    return list(_ROWS)


register_executor("fake", _fake_executor)


@pytest.fixture
def graph():
    db = FalkorDB(host="localhost", port=6380)
    g = db.select_graph("sync_test_temp")
    try:
        g.delete()
    except Exception:
        pass
    yield g
    try:
        g.delete()
    except Exception:
        pass


@pytest.fixture
def repo(graph):
    r = FalkorTBoxRepository(graph)
    r.create_class("ProductRevenue")
    r.define_connector("fake_db", kind="fake", dsn_ref="")
    r.attach_source_binding_to_class(
        class_name="ProductRevenue",
        connector_name="fake_db",
        sql="SELECT product_id, rev FROM ... GROUP BY product_id",
        key_columns=("product_id",),
        column_map={"rev": "revenue"},
    )
    return r


def _nodes(graph):
    rows = graph.query(
        "MATCH (n:ProductRevenue) RETURN n.product_id, n.revenue, n.synced_at, n.source_connector "
        "ORDER BY n.product_id"
    ).result_set
    return rows


def test_materialize_creates_one_node_per_row(repo, graph):
    global _ROWS
    _ROWS = [{"product_id": 1, "rev": 100}, {"product_id": 2, "rev": 200}]

    result = materialize_source(repo=repo, graph=graph, class_name="ProductRevenue", now="2026-05-30T00:00:00+00:00")

    assert result.rows_fetched == 2
    assert result.nodes_upserted == 2
    assert result.nodes_pruned == 0
    nodes = _nodes(graph)
    assert nodes == [
        [1, 100, "2026-05-30T00:00:00+00:00", "fake_db"],
        [2, 200, "2026-05-30T00:00:00+00:00", "fake_db"],
    ]


def test_column_map_renames_and_unmapped_columns_kept(repo, graph):
    global _ROWS
    _ROWS = [{"product_id": 7, "rev": 50}]
    materialize_source(repo=repo, graph=graph, class_name="ProductRevenue")
    row = _nodes(graph)[0]
    assert row[0] == 7  # product_id kept (unmapped)
    assert row[1] == 50  # rev -> revenue (mapped)


def test_resync_prunes_previous_nodes(repo, graph):
    global _ROWS
    _ROWS = [{"product_id": 1, "rev": 100}, {"product_id": 2, "rev": 200}]
    materialize_source(repo=repo, graph=graph, class_name="ProductRevenue")

    _ROWS = [{"product_id": 1, "rev": 999}]
    result = materialize_source(repo=repo, graph=graph, class_name="ProductRevenue")

    assert result.nodes_pruned == 2
    assert result.nodes_upserted == 1
    nodes = _nodes(graph)
    assert len(nodes) == 1
    assert nodes[0][0] == 1 and nodes[0][1] == 999


def test_no_prune_keeps_previous_nodes(repo, graph):
    global _ROWS
    _ROWS = [{"product_id": 1, "rev": 100}]
    materialize_source(repo=repo, graph=graph, class_name="ProductRevenue")
    _ROWS = [{"product_id": 2, "rev": 200}]
    result = materialize_source(repo=repo, graph=graph, class_name="ProductRevenue", prune=False)
    assert result.nodes_pruned == 0
    assert len(_nodes(graph)) == 2


def test_duplicate_key_fails_loudly_and_writes_nothing(repo, graph):
    global _ROWS
    _ROWS = [{"product_id": 1, "rev": 100}, {"product_id": 1, "rev": 200}]
    with pytest.raises(ValueError, match="duplicate key"):
        materialize_source(repo=repo, graph=graph, class_name="ProductRevenue")
    assert _nodes(graph) == []


def test_null_key_fails_loudly(repo, graph):
    global _ROWS
    _ROWS = [{"product_id": None, "rev": 100}]
    with pytest.raises(ValueError, match="NULL key"):
        materialize_source(repo=repo, graph=graph, class_name="ProductRevenue")
    assert _nodes(graph) == []


def test_missing_key_column_treated_as_null(repo, graph):
    global _ROWS
    _ROWS = [{"rev": 100}]  # no product_id column at all
    with pytest.raises(ValueError, match="NULL key"):
        materialize_source(repo=repo, graph=graph, class_name="ProductRevenue")


def test_materialize_without_binding_raises(graph):
    r = FalkorTBoxRepository(graph)
    r.create_class("Lonely")
    with pytest.raises(TBoxNotFoundError):
        materialize_source(repo=r, graph=graph, class_name="Lonely")
