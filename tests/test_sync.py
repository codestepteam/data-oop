import pytest
from falkordb import FalkorDB

from data_oop import (
    FalkorTBoxRepository,
    SourceLink,
    TBoxNotFoundError,
    materialize_source,
    register_executor,
    upsert_abox_node,
)

# A controllable in-test executor: each test sets _ROWS, the executor returns them.
_ROWS: list[dict] = []


def _fake_executor(connector, sql, params=None):
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


def _setup_inventory_with_link(graph):
    """Product nodes exist; Inventory is source-backed and links to Product by product_id."""
    repo = FalkorTBoxRepository(graph)
    repo.create_class("Product")
    repo.create_class("Inventory")
    repo.define_relationship(name="OF_PRODUCT", from_class="Inventory", to_class="Product")
    repo.define_connector("fake_db", kind="fake", dsn_ref="")
    upsert_abox_node(graph=graph, class_name="Product", uuid="p1", properties={"product_id": 1})
    upsert_abox_node(graph=graph, class_name="Product", uuid="p2", properties={"product_id": 2})
    repo.attach_source_binding_to_class(
        class_name="Inventory",
        connector_name="fake_db",
        sql="SELECT sku, product_id, qty FROM inventory",
        key_columns=("sku",),
        links=(
            SourceLink(relationship_name="OF_PRODUCT", to_class="Product", local_key="product_id"),
        ),
    )
    return repo


def test_sync_links_rows_to_existing_nodes(graph):
    global _ROWS
    repo = _setup_inventory_with_link(graph)
    _ROWS = [
        {"sku": "A", "product_id": 1, "qty": 10},
        {"sku": "B", "product_id": 2, "qty": 5},
    ]

    result = materialize_source(repo=repo, graph=graph, class_name="Inventory")

    assert result.nodes_upserted == 2
    assert result.edges_upserted == 2
    assert result.links_missing == 0
    edges = graph.query(
        "MATCH (i:Inventory)-[:OF_PRODUCT]->(p:Product) RETURN i.sku, p.product_id ORDER BY i.sku"
    ).result_set
    assert edges == [["A", 1], ["B", 2]]


def test_sync_link_missing_target_counted_not_fatal(graph):
    global _ROWS
    repo = _setup_inventory_with_link(graph)
    _ROWS = [
        {"sku": "A", "product_id": 1, "qty": 10},
        {"sku": "B", "product_id": 99, "qty": 5},  # no Product 99
    ]

    result = materialize_source(repo=repo, graph=graph, class_name="Inventory")

    assert result.nodes_upserted == 2  # both nodes created
    assert result.edges_upserted == 1  # only product 1 linked
    assert result.links_missing == 1


def test_resync_rebuilds_links(graph):
    global _ROWS
    repo = _setup_inventory_with_link(graph)
    _ROWS = [{"sku": "A", "product_id": 1, "qty": 10}]
    materialize_source(repo=repo, graph=graph, class_name="Inventory")
    # re-sync (prune wipes old Inventory nodes + their edges, then rebuilds)
    _ROWS = [{"sku": "A", "product_id": 2, "qty": 7}]
    result = materialize_source(repo=repo, graph=graph, class_name="Inventory")
    assert result.nodes_pruned == 1
    assert result.edges_upserted == 1
    edges = graph.query(
        "MATCH (i:Inventory)-[:OF_PRODUCT]->(p:Product) RETURN i.sku, p.product_id"
    ).result_set
    assert edges == [["A", 2]]


def test_node_uuid_is_deterministic_for_key_columns() -> None:
    from data_oop.rdb.sync import _node_uuid
    from data_oop.schema.models import SourceBinding

    binding = SourceBinding(
        class_name="CustomerSegment",
        connector_name="warehouse",
        sql="SELECT ...",
        key_columns=("tier", "region"),
    )
    row = {"tier": "gold", "region": "kr", "revenue": 100}
    again = {"tier": "gold", "region": "kr", "revenue": 999}
    other = {"tier": "silver", "region": "kr", "revenue": 100}

    assert _node_uuid(binding, "warehouse", row) == _node_uuid(binding, "warehouse", again)
    assert _node_uuid(binding, "warehouse", row) != _node_uuid(binding, "warehouse", other)
    assert _node_uuid(binding, "other_conn", row) != _node_uuid(binding, "warehouse", row)


def test_node_uuid_without_key_columns_is_random() -> None:
    from data_oop.rdb.sync import _node_uuid
    from data_oop.schema.models import SourceBinding

    binding = SourceBinding(class_name="X", connector_name="c", sql="SELECT 1")
    row = {"a": 1}
    assert _node_uuid(binding, "c", row) != _node_uuid(binding, "c", row)
