import pytest
from falkordb import FalkorDB

from data_oop import (
    FalkorTBoxRepository,
    MetricDef,
    TBoxConflictError,
    TBoxNotFoundError,
    register_executor,
    resolve_metric,
    run_workflow,
    save_workflow,
    upsert_abox_node,
)

# A controllable in-test executor: it records every (sql, params) it receives and
# returns the rows the test set in _ROWS. Recording lets us assert that node values
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
    r.create_class("Customer")
    r.define_connector("fake_db", kind="fake_resolve", dsn_ref="")
    return r


def _define_revenue(repo, **overrides):
    kwargs = dict(
        name="revenue_last_30d",
        class_name="Customer",
        connector_name="fake_db",
        sql="SELECT sum(amount) AS value FROM orders WHERE customer_id = :cid",
        param_map={"cid": "{customer_id}"},
        result_kind="scalar",
    )
    kwargs.update(overrides)
    return repo.define_metric(MetricDef(**kwargs))


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------
def test_define_and_get_metric_roundtrip(repo):
    _define_revenue(repo, ttl_seconds=3600, description="30d revenue")
    got = repo.get_metric("revenue_last_30d")
    assert got is not None
    assert got.class_name == "Customer"
    assert got.connector_name == "fake_db"
    assert got.param_map == {"cid": "{customer_id}"}
    assert got.result_kind == "scalar"
    assert got.value_column == "value"
    assert got.ttl_seconds == 3600
    assert got.description == "30d revenue"


def test_list_metrics_and_filter_by_class(repo):
    repo.create_class("Product")
    _define_revenue(repo)
    repo.define_metric(MetricDef(name="stock", class_name="Product", connector_name="fake_db", sql="SELECT 1 AS value"))

    assert {m.name for m in repo.list_metrics()} == {"revenue_last_30d", "stock"}
    assert [m.name for m in repo.list_metrics(class_name="Customer")] == ["revenue_last_30d"]


def test_define_metric_unknown_class_or_connector_raises(repo):
    with pytest.raises(TBoxNotFoundError):
        repo.define_metric(MetricDef(name="x", class_name="Nope", connector_name="fake_db", sql="SELECT 1"))
    with pytest.raises(TBoxNotFoundError):
        repo.define_metric(MetricDef(name="x", class_name="Customer", connector_name="nope", sql="SELECT 1"))


def test_delete_metric(repo, graph):
    _define_revenue(repo)
    repo.delete_metric("revenue_last_30d")
    assert repo.get_metric("revenue_last_30d") is None
    with pytest.raises(TBoxNotFoundError):
        repo.delete_metric("revenue_last_30d")


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------
def test_resolve_scalar_returns_value_column(repo, graph):
    global _ROWS
    _define_revenue(repo)
    _ROWS = [{"value": 340000}]
    out = resolve_metric(repo=repo, graph=graph, metric_name="revenue_last_30d",
                         node={"customer_id": "123"})
    assert out == 340000


def test_resolve_row_and_rows(repo, graph):
    global _ROWS
    repo.define_metric(MetricDef(name="m_row", class_name="Customer", connector_name="fake_db",
                                 sql="SELECT a, b", result_kind="row"))
    repo.define_metric(MetricDef(name="m_rows", class_name="Customer", connector_name="fake_db",
                                 sql="SELECT a", result_kind="rows"))
    _ROWS = [{"a": 1, "b": 2}, {"a": 3, "b": 4}]
    assert resolve_metric(repo=repo, graph=graph, metric_name="m_row") == {"a": 1, "b": 2}
    assert resolve_metric(repo=repo, graph=graph, metric_name="m_rows") == [{"a": 1, "b": 2}, {"a": 3, "b": 4}]


def test_scalar_empty_result_is_none(repo, graph):
    _define_revenue(repo)
    out = resolve_metric(repo=repo, graph=graph, metric_name="revenue_last_30d", node={"customer_id": "x"})
    assert out is None


def test_param_map_interpolated_against_node_and_bound_not_formatted(repo, graph):
    global _ROWS
    _define_revenue(repo)
    _ROWS = [{"value": 1}]
    resolve_metric(repo=repo, graph=graph, metric_name="revenue_last_30d",
                   node={"customer_id": "abc'; DROP TABLE orders;--"})
    # The node value flows through bind params, and the SQL text is untouched — so a
    # malicious value can never become SQL.
    assert _CALLS[-1]["params"] == {"cid": "abc'; DROP TABLE orders;--"}
    assert ":cid" in _CALLS[-1]["sql"]
    assert "DROP TABLE" not in _CALLS[-1]["sql"]


def test_explicit_params_override_param_map(repo, graph):
    global _ROWS
    _define_revenue(repo)
    _ROWS = [{"value": 1}]
    resolve_metric(repo=repo, graph=graph, metric_name="revenue_last_30d",
                   node={"customer_id": "123"}, params={"cid": "999"})
    assert _CALLS[-1]["params"] == {"cid": "999"}


def test_resolve_unknown_metric_raises(repo, graph):
    with pytest.raises(TBoxNotFoundError):
        resolve_metric(repo=repo, graph=graph, metric_name="ghost")


# ---------------------------------------------------------------------------
# TTL cache
# ---------------------------------------------------------------------------
def test_ttl_cache_serves_fresh_and_refetches_when_stale(repo, graph):
    global _ROWS
    _define_revenue(repo, ttl_seconds=3600)
    upsert_abox_node(graph=graph, class_name="Customer", uuid="c1", properties={"customer_id": "123"})

    def node():
        rows = graph.query("MATCH (n:Customer {uuid:$u}) RETURN properties(n)", {"u": "c1"}).result_set
        return dict(rows[0][0])

    _ROWS = [{"value": 100}]
    v1 = resolve_metric(repo=repo, graph=graph, metric_name="revenue_last_30d",
                        node=node(), now="2026-06-02T00:00:00+00:00")
    assert v1 == 100
    assert len(_CALLS) == 1

    # Within TTL: served from the node's cache, the executor is NOT called again even
    # though the underlying rows changed.
    _ROWS = [{"value": 999}]
    v2 = resolve_metric(repo=repo, graph=graph, metric_name="revenue_last_30d",
                        node=node(), now="2026-06-02T00:30:00+00:00")
    assert v2 == 100
    assert len(_CALLS) == 1

    # Past TTL: refetch, get the new value, write the cache again.
    v3 = resolve_metric(repo=repo, graph=graph, metric_name="revenue_last_30d",
                        node=node(), now="2026-06-02T02:00:00+00:00")
    assert v3 == 999
    assert len(_CALLS) == 2


def test_no_cache_flag_bypasses_cache(repo, graph):
    global _ROWS
    _define_revenue(repo, ttl_seconds=3600)
    upsert_abox_node(graph=graph, class_name="Customer", uuid="c1", properties={"customer_id": "123"})
    node = {"uuid": "c1", "customer_id": "123"}

    _ROWS = [{"value": 100}]
    resolve_metric(repo=repo, graph=graph, metric_name="revenue_last_30d", node=node, now="2026-06-02T00:00:00+00:00")
    resolve_metric(repo=repo, graph=graph, metric_name="revenue_last_30d", node=node,
                   use_cache=False, now="2026-06-02T00:10:00+00:00")
    assert len(_CALLS) == 2


# ---------------------------------------------------------------------------
# fetch_metric workflow action (end-to-end)
# ---------------------------------------------------------------------------
def test_fetch_metric_workflow_links_node_to_segment(repo, graph):
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
            {"step_id": "rev", "action": "fetch_metric", "metric_name": "revenue_last_30d",
             "parameters": {"cid": "{customer_id}"}},
            {"step_id": "seg", "action": "create_relationship", "if_present": "rev.value",
             "from_class": "Customer", "from_uuid": "{customer_uuid}",
             "relationship_name": "IN_SEGMENT", "to_class": "Segment", "to_uuid": "seg-high"},
        ],
    )

    _ROWS = [{"value": 500000}]
    run_workflow(graph=graph, name="classify_customer",
                 parameters={"customer_uuid": "c1", "customer_id": "123"})

    # The metric value (live) was used to gate the link; only the derived edge is stored.
    assert _CALLS[-1]["params"] == {"cid": "123"}
    edges = graph.query(
        "MATCH (c:Customer)-[:IN_SEGMENT]->(s:Segment) RETURN c.uuid, s.uuid"
    ).result_set
    assert edges == [["c1", "seg-high"]]


def test_fetch_metric_missing_metric_name_rejected(repo, graph):
    with pytest.raises(ValueError, match="metric_name"):
        save_workflow(
            graph=graph,
            name="bad",
            parameters=[],
            steps=[{"step_id": "x", "action": "fetch_metric"}],
        )


# ---------------------------------------------------------------------------
# Connector deletion guards against orphaning metrics
# ---------------------------------------------------------------------------
def test_delete_connector_blocked_while_metric_uses_it(repo):
    _define_revenue(repo)
    with pytest.raises(TBoxConflictError):
        repo.delete_connector("fake_db")


def test_delete_connector_detach_removes_metric(repo):
    _define_revenue(repo)
    repo.delete_connector("fake_db", detach=True)
    assert repo.get_metric("revenue_last_30d") is None
    assert repo.get_connector("fake_db") is None
