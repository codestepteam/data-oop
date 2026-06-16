import pytest
from falkordb import FalkorDB

from data_oop import (
    ConnectorDef,
    FalkorTBoxRepository,
    InMemoryTBoxRepository,
    SourceBinding,
    SourceLink,
    TBoxConflictError,
    TBoxNotFoundError,
)
from data_oop.exceptions import TBoxError
from data_oop.rdb.connectors import _bigquery_client_from_credentials_env


@pytest.fixture(scope="module")
def falkor_graph():
    db = FalkorDB(host="localhost", port=6380)
    graph = db.select_graph("connector_test_temp")
    try:
        graph.delete()
    except Exception:
        pass
    yield graph
    try:
        graph.delete()
    except Exception:
        pass


@pytest.fixture(params=["memory", "falkor"])
def repo(request, falkor_graph):
    if request.param == "memory":
        return InMemoryTBoxRepository()
    return FalkorTBoxRepository(falkor_graph)


def _seed(repo):
    repo.create_class("ProductRevenue")
    repo.define_connector("prod_pg", kind="postgres", dsn_ref="PROD_DB_DSN")


def test_define_and_get_connector(repo) -> None:
    repo.define_connector("prod_pg", kind="postgres", dsn_ref="PROD_DB_DSN", description="prod")
    got = repo.get_connector("prod_pg")
    assert got == ConnectorDef(
        name="prod_pg", kind="postgres", dsn_ref="PROD_DB_DSN", description="prod"
    )
    assert repo.get_connector("missing") is None
    assert repo.list_connectors() == [got]


def test_connector_dsn_ref_holds_env_name_not_secret(repo) -> None:
    # Only the env var NAME is persisted — nothing secret.
    repo.define_connector("prod_pg", dsn_ref="PROD_DB_DSN")
    assert repo.get_connector("prod_pg").dsn_ref == "PROD_DB_DSN"


def test_bigquery_credentials_env_path_uses_service_account_file(tmp_path) -> None:
    calls = {}

    class FakeClient:
        @classmethod
        def from_service_account_json(cls, path, project=None):
            calls["path"] = path
            calls["project"] = project
            return "client"

    class FakeBigQuery:
        Client = FakeClient

    credentials_path = tmp_path / "service-account.json"
    credentials_path.write_text("{}", encoding="utf-8")

    assert (
        _bigquery_client_from_credentials_env(
            FakeBigQuery, str(credentials_path), project="my-project"
        )
        == "client"
    )
    assert calls == {"path": str(credentials_path), "project": "my-project"}


def test_bigquery_credentials_env_json_string_uses_inline_info(monkeypatch) -> None:
    import json
    import sys
    import types

    calls = {}

    class FakeCredentials:
        @classmethod
        def from_service_account_info(cls, info):
            calls["info"] = info
            return "credentials"

    service_account_module = types.ModuleType("google.oauth2.service_account")
    service_account_module.Credentials = FakeCredentials
    oauth2_module = types.ModuleType("google.oauth2")
    oauth2_module.service_account = service_account_module
    google_module = types.ModuleType("google")
    google_module.oauth2 = oauth2_module
    monkeypatch.setitem(sys.modules, "google", google_module)
    monkeypatch.setitem(sys.modules, "google.oauth2", oauth2_module)
    monkeypatch.setitem(sys.modules, "google.oauth2.service_account", service_account_module)

    class FakeClient:
        def __init__(self, project=None, credentials=None):
            calls["client"] = {"project": project, "credentials": credentials}

    class FakeBigQuery:
        Client = FakeClient

    raw_credentials = json.dumps(
        {"type": "service_account", "project_id": "json-project", "client_email": "x@y"}
    )

    client = _bigquery_client_from_credentials_env(FakeBigQuery, raw_credentials, project=None)

    assert isinstance(client, FakeClient)
    assert calls["info"]["project_id"] == "json-project"
    assert calls["client"] == {"project": "json-project", "credentials": "credentials"}


def test_bigquery_credentials_env_quoted_json_string(monkeypatch) -> None:
    import json
    import sys
    import types

    calls = {}

    class FakeCredentials:
        @classmethod
        def from_service_account_info(cls, info):
            calls["info"] = info
            return "credentials"

    service_account_module = types.ModuleType("google.oauth2.service_account")
    service_account_module.Credentials = FakeCredentials
    oauth2_module = types.ModuleType("google.oauth2")
    oauth2_module.service_account = service_account_module
    google_module = types.ModuleType("google")
    google_module.oauth2 = oauth2_module
    monkeypatch.setitem(sys.modules, "google", google_module)
    monkeypatch.setitem(sys.modules, "google.oauth2", oauth2_module)
    monkeypatch.setitem(sys.modules, "google.oauth2.service_account", service_account_module)

    class FakeClient:
        def __init__(self, project=None, credentials=None):
            calls["client"] = {"project": project, "credentials": credentials}

    class FakeBigQuery:
        Client = FakeClient

    # Wrapped in double quotes
    raw_credentials_double = '"' + json.dumps(
        {"type": "service_account", "project_id": "quoted-project-double", "client_email": "x@y"}
    ) + '"'

    client = _bigquery_client_from_credentials_env(FakeBigQuery, raw_credentials_double, project=None)
    assert isinstance(client, FakeClient)
    assert calls["info"]["project_id"] == "quoted-project-double"

    # Wrapped in single quotes
    raw_credentials_single = "'" + json.dumps(
        {"type": "service_account", "project_id": "quoted-project-single", "client_email": "x@y"}
    ) + "'"

    client = _bigquery_client_from_credentials_env(FakeBigQuery, raw_credentials_single, project=None)
    assert isinstance(client, FakeClient)
    assert calls["info"]["project_id"] == "quoted-project-single"


def test_bigquery_credentials_env_missing_json_file_raises() -> None:
    with pytest.raises(TBoxError, match="does not exist"):
        _bigquery_client_from_credentials_env(object(), "missing-service-account.json", None)


def test_attach_and_get_source_binding(repo) -> None:
    _seed(repo)
    binding = repo.attach_source_binding_to_class(
        class_name="ProductRevenue",
        connector_name="prod_pg",
        sql="SELECT p.id AS product_id, SUM(oi.amount) AS revenue FROM order_items oi "
        "JOIN products p ON p.id = oi.product_id GROUP BY p.id",
        key_columns=("product_id",),
        column_map={"revenue": "revenue"},
        refresh_interval_hours=24,
    )
    expected = SourceBinding(
        class_name="ProductRevenue",
        connector_name="prod_pg",
        sql=binding.sql,
        key_columns=("product_id",),
        column_map={"revenue": "revenue"},
        materialization="materialized",
        refresh_interval_hours=24,
    )
    assert binding == expected
    assert repo.get_source_binding("ProductRevenue") == expected
    assert repo.list_source_bindings() == [expected]


def test_key_columns_round_trip_as_tuple(repo) -> None:
    _seed(repo)
    repo.attach_source_binding_to_class(
        class_name="ProductRevenue",
        connector_name="prod_pg",
        sql="SELECT 1",
        key_columns=("a", "b"),
    )
    fetched = repo.get_source_binding("ProductRevenue")
    assert isinstance(fetched.key_columns, tuple)
    assert fetched.key_columns == ("a", "b")


def test_empty_key_columns_rejected(repo) -> None:
    _seed(repo)
    with pytest.raises(TBoxConflictError):
        repo.attach_source_binding_to_class(
            class_name="ProductRevenue",
            connector_name="prod_pg",
            sql="SELECT 1",
            key_columns=(),
        )


def test_attach_requires_existing_class_and_connector(repo) -> None:
    repo.define_connector("prod_pg", dsn_ref="X")
    with pytest.raises(TBoxNotFoundError):
        repo.attach_source_binding_to_class(
            class_name="Nope", connector_name="prod_pg", sql="SELECT 1", key_columns=("id",)
        )
    repo.create_class("ProductRevenue")
    with pytest.raises(TBoxNotFoundError):
        repo.attach_source_binding_to_class(
            class_name="ProductRevenue", connector_name="nope", sql="SELECT 1", key_columns=("id",)
        )


def test_rebinding_replaces_previous_connector(repo) -> None:
    _seed(repo)
    repo.define_connector("other_db", kind="mysql", dsn_ref="OTHER_DSN")
    repo.attach_source_binding_to_class(
        class_name="ProductRevenue", connector_name="prod_pg", sql="SELECT 1", key_columns=("id",)
    )
    repo.attach_source_binding_to_class(
        class_name="ProductRevenue", connector_name="other_db", sql="SELECT 2", key_columns=("id",)
    )
    binding = repo.get_source_binding("ProductRevenue")
    assert binding.connector_name == "other_db"
    assert binding.sql == "SELECT 2"
    assert len(repo.list_source_bindings()) == 1


def test_delete_connector_blocked_while_bound(repo) -> None:
    _seed(repo)
    repo.attach_source_binding_to_class(
        class_name="ProductRevenue", connector_name="prod_pg", sql="SELECT 1", key_columns=("id",)
    )
    with pytest.raises(TBoxConflictError):
        repo.delete_connector("prod_pg")
    # detach drops the bindings then removes the connector
    repo.delete_connector("prod_pg", detach=True)
    assert repo.get_connector("prod_pg") is None
    assert repo.get_source_binding("ProductRevenue") is None


def test_source_binding_links_round_trip(repo) -> None:
    _seed(repo)
    repo.attach_source_binding_to_class(
        class_name="ProductRevenue",
        connector_name="prod_pg",
        sql="SELECT 1",
        key_columns=("product_id",),
        links=(
            SourceLink(relationship_name="OF_PRODUCT", to_class="Product", local_key="product_id"),
        ),
    )
    binding = repo.get_source_binding("ProductRevenue")
    assert len(binding.links) == 1
    link = binding.links[0]
    assert link.relationship_name == "OF_PRODUCT"
    assert link.to_class == "Product"
    assert link.local_key == "product_id"
    assert link.target_property == "product_id"  # defaulted from local_key
    assert link.direction == "out"


def test_detach_source_binding(repo) -> None:
    _seed(repo)
    repo.attach_source_binding_to_class(
        class_name="ProductRevenue", connector_name="prod_pg", sql="SELECT 1", key_columns=("id",)
    )
    repo.detach_source_binding_from_class("ProductRevenue")
    assert repo.get_source_binding("ProductRevenue") is None
    # connector is now free to delete
    repo.delete_connector("prod_pg")
    assert repo.get_connector("prod_pg") is None


def test_delete_class_drops_its_binding(repo) -> None:
    _seed(repo)
    repo.attach_source_binding_to_class(
        class_name="ProductRevenue", connector_name="prod_pg", sql="SELECT 1", key_columns=("id",)
    )
    repo.delete_class("ProductRevenue", detach=True)
    assert repo.list_source_bindings() == []
    # binding gone -> connector deletable without detach
    repo.delete_connector("prod_pg")
