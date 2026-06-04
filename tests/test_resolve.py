import pytest
from falkordb import FalkorDB

from data_oop import (
    FalkorTBoxRepository,
    TBoxConflictError,
    TBoxNotFoundError,
    ViewDef,
    ViewParam,
    register_executor,
    resolve_view,
    run_workflow,
    save_workflow,
    upsert_abox_node,
)

# A controllable in-test executor: it records every (sql, params) it receives and
# returns the rows the test set in _ROWS. Recording lets us assert that filter values
# are passed as *bind parameters* (never formatted into the SQL string).
_ROWS: list[dict] = []
_CALLS: list[dict] = []


def _fake_executor(connector, sql, params=None):
    _CALLS.append({"sql": sql, "params": dict(params or {})})
    return list(_ROWS)


# A unique kind: the executor registry is process-global, so reusing "fake" (as
# test_sync does) would let whichever module imported last win.
register_executor("fake_resolve", _fake_executor)


@pytest.fixture(autouse=True)
def _reset():
    global _ROWS, _CALLS
    _ROWS = []
    _CALLS = []
    yield


@pytest.fixture
def graph():
    db = FalkorDB(host="localhost", port=6380)
    g = db.select_graph("resolve_test_temp")
    conn = g.client.connection

    def _clean():
        try:
            g.delete()
        except Exception:
            pass
        # View results are cached in the same Redis instance, separate from the graph,
        # so they must be cleared between tests too.
        try:
            keys = conn.keys("doop:viewcache:resolve_test_temp:*")
            if keys:
                conn.delete(*keys)
        except Exception:
            pass

    _clean()
    yield g
    _clean()


@pytest.fixture
def repo(graph):
    r = FalkorTBoxRepository(graph)
    r.create_class("Customer")
    r.define_connector("fake_db", kind="fake_resolve", dsn_ref="")
    return r


def _define_revenue(repo, **overrides):
    kwargs = dict(
        name="revenue_last_30d",
        class_name="Customer",
        connector_name="fake_db",
        sql="SELECT sum(amount) AS revenue FROM orders WHERE customer_id = :cid",
        params=(ViewParam(name="cid", required=False),),
    )
    kwargs.update(overrides)
    return repo.define_view(ViewDef(**kwargs))


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------
def test_define_and_get_view_roundtrip(repo):
    _define_revenue(repo, key_column="customer_id", ttl_seconds=3600, description="30d revenue")
    got = repo.get_view("revenue_last_30d")
    assert got is not None
    assert got.class_name == "Customer"
    assert got.connector_name == "fake_db"
    assert got.params == (ViewParam(name="cid", required=False),)
    assert got.key_column == "customer_id"
    assert got.ttl_seconds == 3600
    assert got.description == "30d revenue"


def test_list_views_and_filter_by_class(repo):
    repo.create_class("Product")
    _define_revenue(repo)
    repo.define_view(ViewDef(name="stock", class_name="Product", connector_name="fake_db", sql="SELECT 1 AS qty"))

    assert {v.name for v in repo.list_views()} == {"revenue_last_30d", "stock"}
    assert [v.name for v in repo.list_views(class_name="Customer")] == ["revenue_last_30d"]


def test_define_view_unknown_class_or_connector_raises(repo):
    with pytest.raises(TBoxNotFoundError):
        repo.define_view(ViewDef(name="x", class_name="Nope", connector_name="fake_db", sql="SELECT 1"))
    with pytest.raises(TBoxNotFoundError):
        repo.define_view(ViewDef(name="x", class_name="Customer", connector_name="nope", sql="SELECT 1"))


def test_delete_view(repo):
    _define_revenue(repo)
    repo.delete_view("revenue_last_30d")
    assert repo.get_view("revenue_last_30d") is None
    with pytest.raises(TBoxNotFoundError):
        repo.delete_view("revenue_last_30d")


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------
def test_resolve_returns_rows(repo, graph):
    global _ROWS
    _define_revenue(repo)
    _ROWS = [{"revenue": 340000}]
    out = resolve_view(repo=repo, graph=graph, view_name="revenue_last_30d", filters={"cid": "123"})
    assert out == [{"revenue": 340000}]


def test_resolve_aggregate_rows(repo, graph):
    global _ROWS
    repo.define_view(ViewDef(name="top", class_name="Customer", connector_name="fake_db",
                             sql="SELECT customer_id, sum(amount) AS revenue FROM orders GROUP BY customer_id"))
    _ROWS = [{"customer_id": "a", "revenue": 10}, {"customer_id": "b", "revenue": 20}]
    out = resolve_view(repo=repo, graph=graph, view_name="top")
    assert out == [{"customer_id": "a", "revenue": 10}, {"customer_id": "b", "revenue": 20}]


def test_resolve_empty_result_is_empty_list(repo, graph):
    _define_revenue(repo)
    out = resolve_view(repo=repo, graph=graph, view_name="revenue_last_30d", filters={"cid": "x"})
    assert out == []


def test_filters_bound_not_formatted(repo, graph):
    global _ROWS
    _define_revenue(repo)
    _ROWS = [{"revenue": 1}]
    resolve_view(repo=repo, graph=graph, view_name="revenue_last_30d",
                 filters={"cid": "abc'; DROP TABLE orders;--"})
    # The filter value flows through bind params, and the SQL text is untouched — so a
    # malicious value can never become SQL.
    assert _CALLS[-1]["params"] == {"cid": "abc'; DROP TABLE orders;--"}
    assert ":cid" in _CALLS[-1]["sql"]
    assert "DROP TABLE" not in _CALLS[-1]["sql"]


def test_required_filter_missing_raises(repo, graph):
    _define_revenue(repo, params=(ViewParam(name="cid", required=True),))
    with pytest.raises(ValueError, match="required"):
        resolve_view(repo=repo, graph=graph, view_name="revenue_last_30d")


def test_resolve_unknown_view_raises(repo, graph):
    with pytest.raises(TBoxNotFoundError):
        resolve_view(repo=repo, graph=graph, view_name="ghost")


# ---------------------------------------------------------------------------
# Redis result cache
# ---------------------------------------------------------------------------
def test_ttl_cache_serves_from_redis_and_bypass(repo, graph):
    global _ROWS
    _define_revenue(repo, ttl_seconds=3600)

    _ROWS = [{"revenue": 100}]
    v1 = resolve_view(repo=repo, graph=graph, view_name="revenue_last_30d", filters={"cid": "123"})
    assert v1 == [{"revenue": 100}]
    assert len(_CALLS) == 1

    # Within TTL: served from the Redis cache, the executor is NOT called again even
    # though the underlying rows changed.
    _ROWS = [{"revenue": 999}]
    v2 = resolve_view(repo=repo, graph=graph, view_name="revenue_last_30d", filters={"cid": "123"})
    assert v2 == [{"revenue": 100}]
    assert len(_CALLS) == 1

    # use_cache=False bypasses the cache and refetches the fresh rows.
    v3 = resolve_view(repo=repo, graph=graph, view_name="revenue_last_30d",
                      filters={"cid": "123"}, use_cache=False)
    assert v3 == [{"revenue": 999}]
    assert len(_CALLS) == 2


def test_cache_key_varies_by_filters(repo, graph):
    global _ROWS
    _define_revenue(repo, ttl_seconds=3600)
    _ROWS = [{"revenue": 1}]
    resolve_view(repo=repo, graph=graph, view_name="revenue_last_30d", filters={"cid": "a"})
    # Different filters => different cache key => a fresh fetch, not the cached row.
    resolve_view(repo=repo, graph=graph, view_name="revenue_last_30d", filters={"cid": "b"})
    assert len(_CALLS) == 2


# ---------------------------------------------------------------------------
# fetch_view workflow action (end-to-end)
# ---------------------------------------------------------------------------
def test_fetch_view_workflow_links_node_to_segment(repo, graph):
    global _ROWS
    repo.create_class("Segment")
    repo.define_relationship(name="IN_SEGMENT", from_class="Customer", to_class="Segment")
    _define_revenue(repo)
    upsert_abox_node(graph=graph, class_name="Customer", uuid="c1", properties={"customer_id": "123"})
    upsert_abox_node(graph=graph, class_name="Segment", uuid="seg-high", properties={"name": "high-value"})

    save_workflow(
        graph=graph,
        name="classify_customer",
        parameters=[
            {"name": "customer_uuid", "type": "string"},
            {"name": "customer_id", "type": "string"},
        ],
        steps=[
            {"step_id": "rev", "action": "fetch_view", "view_name": "revenue_last_30d",
             "parameters": {"cid": "{customer_id}"}},
            {"step_id": "seg", "action": "create_relationship", "if_present": "rev.value",
             "from_class": "Customer", "from_uuid": "{customer_uuid}",
             "relationship_name": "IN_SEGMENT", "to_class": "Segment", "to_uuid": "seg-high"},
        ],
    )

    _ROWS = [{"revenue": 500000}]
    run_workflow(graph=graph, name="classify_customer",
                 parameters={"customer_uuid": "c1", "customer_id": "123"})

    # The view rows (live) gated the link; only the derived edge is stored.
    assert _CALLS[-1]["params"] == {"cid": "123"}
    edges = graph.query(
        "MATCH (c:Customer)-[:IN_SEGMENT]->(s:Segment) RETURN c.uuid, s.uuid"
    ).result_set
    assert edges == [["c1", "seg-high"]]


def test_fetch_view_missing_view_name_rejected(repo, graph):
    with pytest.raises(ValueError, match="view_name"):
        save_workflow(
            graph=graph,
            name="bad",
            parameters=[],
            steps=[{"step_id": "x", "action": "fetch_view"}],
        )


# ---------------------------------------------------------------------------
# Connector deletion guards against orphaning views
# ---------------------------------------------------------------------------
def test_delete_connector_blocked_while_view_uses_it(repo):
    _define_revenue(repo)
    with pytest.raises(TBoxConflictError):
        repo.delete_connector("fake_db")


def test_delete_connector_detach_removes_view(repo):
    _define_revenue(repo)
    repo.delete_connector("fake_db", detach=True)
    assert repo.get_view("revenue_last_30d") is None
    assert repo.get_connector("fake_db") is None
