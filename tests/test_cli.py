from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest

from data_oop.cli import main
from data_oop.schema.models import (
    ClassDef,
    ConnectorDef,
    ConstraintDef,
    EffectivePropertyDef,
    InterfaceDef,
    PropertyBinding,
    PropertyDef,
    RelationshipDef,
    SourceBinding,
    SourceLink,
    TriggerDef,
    ViewDef,
    ViewParam,
)


@pytest.fixture(autouse=True)
def mock_load_dotenv(request):
    if request.node.name == "test_cli_load_dotenv":
        yield
    else:
        with patch("data_oop.cli.load_dotenv", return_value=None):
            yield


@patch("data_oop.cli.connect_and_run_latest_falkor_abox_validation")
def test_cli_validate_command(mock_validation) -> None:
    # Mock return value for validation
    mock_result = MagicMock()
    mock_result.run_id = "test_run_id"
    mock_result.status = "passed"
    mock_result.checked_instance_count = 10
    mock_result.issue_count = 0
    mock_result.error_count = 0
    mock_result.warning_count = 0
    mock_validation.return_value = mock_result

    test_args = ["data-oop", "validate", "--run-id", "custom_id"]
    with patch.object(sys, "argv", test_args):
        main()

    mock_validation.assert_called_once_with(
        graph_name="data_oop",
        host="localhost",
        port=6380,
        username=None,
        password=None,
        run_id="custom_id",
    )


@patch("data_oop.cli.connect_and_clear_abox_nodes")
def test_cli_clear_abox_command(mock_clear) -> None:
    test_args = ["data-oop", "clear-abox", "--yes"]
    with patch.object(sys, "argv", test_args):
        main()

    mock_clear.assert_called_once_with(
        graph_name="data_oop",
        host="localhost",
        port=6380,
        username=None,
        password=None,
    )


@patch("data_oop.cli.FalkorTBoxRepository")
@patch("data_oop.cli.get_db_connection")
def test_cli_tbox_create_class(mock_get_db, mock_repo_class) -> None:
    mock_repo = MagicMock()
    mock_repo_class.return_value = mock_repo
    mock_get_db.return_value = (None, None)

    test_args = [
        "data-oop",
        "tbox-create-class",
        "--class-name", "User",
        "--label", "UserLabel",
        "--description", "desc",
        "--metadata", '{"key": "value"}'
    ]
    with patch.object(sys, "argv", test_args):
        main()

    mock_repo.create_class.assert_called_once_with(
        name="User",
        label="UserLabel",
        description="desc",
        metadata={"key": "value"}
    )


@patch("data_oop.cli.FalkorTBoxRepository")
@patch("data_oop.cli.get_db_connection")
def test_cli_tbox_create_property(mock_get_db, mock_repo_class) -> None:
    mock_repo = MagicMock()
    mock_repo_class.return_value = mock_repo
    mock_get_db.return_value = (None, None)

    test_args = [
        "data-oop",
        "tbox-create-property",
        "--name", "age",
        "--datatype", "integer",
        "--description", "User age",
        "--metadata", '{"min": 0}'
    ]
    with patch.object(sys, "argv", test_args):
        main()

    mock_repo.create_property.assert_called_once_with(
        name="age",
        datatype="integer",
        description="User age",
        metadata={"min": 0}
    )


@patch("data_oop.cli.FalkorTBoxRepository")
@patch("data_oop.cli.get_db_connection")
def test_cli_tbox_attach_property(mock_get_db, mock_repo_class) -> None:
    mock_repo = MagicMock()
    mock_repo_class.return_value = mock_repo
    mock_get_db.return_value = (None, None)

    test_args = [
        "data-oop",
        "tbox-attach-property",
        "--class-name", "User",
        "--property", "age",
        "--required",
        "--unique",
        "--default", "18",
        "--metadata", '{"ui": "slider"}'
    ]
    with patch.object(sys, "argv", test_args):
        main()

    mock_repo.attach_property_to_class.assert_called_once_with(
        class_name="User",
        property_name="age",
        required=True,
        unique=True,
        nullable=True,
        default=18,
        metadata={"ui": "slider"}
    )


@patch("data_oop.cli.FalkorTBoxRepository")
@patch("data_oop.cli.get_db_connection")
def test_cli_tbox_attach_property_not_nullable(mock_get_db, mock_repo_class) -> None:
    mock_repo = MagicMock()
    mock_repo_class.return_value = mock_repo
    mock_get_db.return_value = (None, None)

    test_args = [
        "data-oop",
        "tbox-attach-property",
        "--class-name", "User",
        "--property", "age",
        "--nullable", "false"
    ]
    with patch.object(sys, "argv", test_args):
        main()

    mock_repo.attach_property_to_class.assert_called_once_with(
        class_name="User",
        property_name="age",
        required=False,
        unique=False,
        nullable=False,
        default=None,
        metadata={}
    )


@patch("data_oop.cli.FalkorTBoxRepository")
@patch("data_oop.cli.get_db_connection")
def test_cli_tbox_define_relationship(mock_get_db, mock_repo_class) -> None:
    mock_repo = MagicMock()
    mock_repo_class.return_value = mock_repo
    mock_get_db.return_value = (None, None)

    test_args = [
        "data-oop",
        "tbox-define-relationship",
        "--id", "rel_user_groups",
        "--name", "MEMBER_OF",
        "--from-class", "User",
        "--to-class", "Group",
        "--required",
        "--min-count", "1",
        "--max-count", "5",
        "--description", "User membership",
        "--metadata", '{"active": true}'
    ]
    with patch.object(sys, "argv", test_args):
        main()

    mock_repo.define_relationship.assert_called_once_with(
        id="rel_user_groups",
        name="MEMBER_OF",
        from_class="User",
        to_class="Group",
        min_count=1,
        max_count=5,
        required=True,
        description="User membership",
        metadata={"active": True}
    )


@patch("data_oop.cli.connect_and_upsert_abox_node")
def test_cli_abox_upsert_node(mock_upsert) -> None:
    user_uuid = "550e8400-e29b-41d4-a716-446655440000"
    mock_result = MagicMock()
    mock_result.class_name = "User"
    mock_result.uuid = user_uuid
    mock_upsert.return_value = mock_result

    test_args = [
        "data-oop",
        "abox-upsert-node",
        "--class-name", "User",
        "--uuid", user_uuid,
        "--properties", '{"name": "Alice", "age": 30}'
    ]
    with patch.object(sys, "argv", test_args):
        main()

    mock_upsert.assert_called_once_with(
        graph_name="data_oop",
        host="localhost",
        port=6380,
        username=None,
        password=None,
        class_name="User",
        uuid=user_uuid,
        properties={"name": "Alice", "age": 30}
    )


@patch("data_oop.cli.connect_and_upsert_abox_node")
def test_cli_abox_upsert_node_generates_uuid_when_omitted(mock_upsert) -> None:
    mock_result = MagicMock()
    mock_result.class_name = "User"
    mock_result.uuid = "generated"
    mock_upsert.return_value = mock_result

    test_args = [
        "data-oop",
        "abox-upsert-node",
        "--class-name", "User",
        "--properties", '{"name": "Alice"}'
    ]
    with patch.object(sys, "argv", test_args):
        main()

    generated_uuid = mock_upsert.call_args.kwargs["uuid"]
    UUID(generated_uuid)
    assert mock_upsert.call_args.kwargs["properties"] == {"name": "Alice"}


@patch("data_oop.cli.connect_and_upsert_abox_node")
def test_cli_abox_upsert_node_rejects_invalid_uuid(mock_upsert, capsys) -> None:
    test_args = [
        "data-oop",
        "abox-upsert-node",
        "--class-name", "User",
        "--uuid", "user-1",
    ]
    with patch.object(sys, "argv", test_args), pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 1
    assert "Error: --uuid must be a valid UUID: user-1" in capsys.readouterr().err
    mock_upsert.assert_not_called()


@patch("data_oop.cli.upsert_abox_relationship")
@patch("data_oop.cli.get_db_connection")
def test_cli_abox_upsert_relationship(mock_get_db, mock_upsert_rel) -> None:
    mock_get_db.return_value = (None, "mock_graph")

    test_args = [
        "data-oop",
        "abox-upsert-relationship",
        "--from-class", "User",
        "--from-uuid", "user-1",
        "--name", "MEMBER_OF",
        "--to-class", "Group",
        "--to-uuid", "group-1",
        "--properties", '{"since": "2026-01-01"}'
    ]
    with patch.object(sys, "argv", test_args):
        main()

    mock_upsert_rel.assert_called_once_with(
        graph="mock_graph",
        from_class="User",
        from_uuid="user-1",
        relationship_name="MEMBER_OF",
        to_class="Group",
        to_uuid="group-1",
        properties={"since": "2026-01-01"}
    )


@patch("data_oop.cli.connect_and_delete_abox_element")
def test_cli_abox_delete(mock_delete) -> None:
    mock_delete.return_value = (1, 0)  # mock node deletion

    test_args = [
        "data-oop",
        "abox-delete",
        "--uuid", "my-uuid"
    ]
    with patch.object(sys, "argv", test_args):
        main()

    mock_delete.assert_called_once_with(
        graph_name="data_oop",
        host="localhost",
        port=6380,
        username=None,
        password=None,
        uuid="my-uuid"
    )


@patch("data_oop.cli.FalkorTBoxRepository")
@patch("data_oop.cli.get_db_connection")
def test_cli_tbox_delete_class(mock_get_db, mock_repo_class) -> None:
    mock_repo = MagicMock()
    mock_repo_class.return_value = mock_repo
    mock_get_db.return_value = (None, None)

    test_args = [
        "data-oop",
        "tbox-delete-class",
        "--class-name", "User",
        "--detach"
    ]
    with patch.object(sys, "argv", test_args):
        main()

    mock_repo.delete_class.assert_called_once_with(
        name="User",
        detach=True
    )


@patch("data_oop.cli.FalkorTBoxRepository")
@patch("data_oop.cli.get_db_connection")
def test_cli_tbox_delete_property(mock_get_db, mock_repo_class) -> None:
    mock_repo = MagicMock()
    mock_repo_class.return_value = mock_repo
    mock_get_db.return_value = (None, None)

    test_args = [
        "data-oop",
        "tbox-delete-property",
        "--name", "age",
        "--detach"
    ]
    with patch.object(sys, "argv", test_args):
        main()

    mock_repo.delete_property.assert_called_once_with(
        name="age",
        detach=True
    )


@patch("data_oop.cli.FalkorTBoxRepository")
@patch("data_oop.cli.get_db_connection")
def test_cli_tbox_detach_property(mock_get_db, mock_repo_class) -> None:
    mock_repo = MagicMock()
    mock_repo_class.return_value = mock_repo
    mock_get_db.return_value = (None, None)

    test_args = [
        "data-oop",
        "tbox-detach-property",
        "--class-name", "User",
        "--property", "age"
    ]
    with patch.object(sys, "argv", test_args):
        main()

    mock_repo.detach_property_from_class.assert_called_once_with(
        class_name="User",
        property_name="age"
    )


@patch("data_oop.cli.FalkorTBoxRepository")
@patch("data_oop.cli.get_db_connection")
def test_cli_tbox_delete_relationship(mock_get_db, mock_repo_class) -> None:
    mock_repo = MagicMock()
    mock_repo_class.return_value = mock_repo
    mock_get_db.return_value = (None, None)

    test_args = [
        "data-oop",
        "tbox-delete-relationship",
        "--id", "rel_user_groups"
    ]
    with patch.object(sys, "argv", test_args):
        main()

    mock_repo.delete_relationship.assert_called_once_with(
        id="rel_user_groups"
    )


def test_cli_load_dotenv(tmp_path) -> None:
    from data_oop.cli import load_dotenv
    import os

    # Create a temporary .env file
    dotenv_file = tmp_path / ".env"
    dotenv_file.write_text(
        "# This is a comment\n"
        "FALKOR_HOST=my-custom-host\n"
        "FALKOR_PORT=9999\n"
        "FALKOR_PASSWORD='my-secret-pass'\n"
    )

    cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        os.environ.pop("FALKOR_HOST", None)
        os.environ.pop("FALKOR_PORT", None)
        os.environ.pop("FALKOR_PASSWORD", None)

        load_dotenv()

        assert os.environ.get("FALKOR_HOST") == "my-custom-host"
        assert os.environ.get("FALKOR_PORT") == "9999"
        assert os.environ.get("FALKOR_PASSWORD") == "my-secret-pass"
    finally:
        os.chdir(cwd)
        os.environ.pop("FALKOR_HOST", None)
        os.environ.pop("FALKOR_PORT", None)
        os.environ.pop("FALKOR_PASSWORD", None)


@patch("data_oop.cli.dump_graph_to_file")
def test_cli_db_dump(mock_dump) -> None:
    test_args = [
        "data-oop",
        "db-dump",
        "--file", "test_out.dump"
    ]
    with patch.object(sys, "argv", test_args):
        main()

    mock_dump.assert_called_once_with(
        filepath="test_out.dump",
        graph_name="data_oop",
        host="localhost",
        port=6380,
        username=None,
        password=None
    )


@patch("data_oop.cli.restore_graph_from_file")
def test_cli_db_restore(mock_restore) -> None:
    test_args = [
        "data-oop",
        "db-restore",
        "--file", "test_in.dump"
    ]
    with patch.object(sys, "argv", test_args):
        main()

    mock_restore.assert_called_once_with(
        filepath="test_in.dump",
        graph_name="data_oop",
        host="localhost",
        port=6380,
        username=None,
        password=None
    )


@patch("data_oop.cli.FalkorTBoxRepository")
@patch("data_oop.cli.get_db_connection")
def test_cli_inspect_lists_full_tbox_content(mock_get_db, mock_repo_class, capsys) -> None:
    graph = MagicMock()
    graph.name = "data_oop"
    workflow_result = MagicMock()
    workflow_result.result_set = [
        ["wf-1", "score_workflow", "Score customers", '[{"step_id":"fetch"}]', "[]"]
    ]
    graph.query.return_value = workflow_result
    mock_get_db.return_value = (None, graph)

    repo = MagicMock()
    mock_repo_class.return_value = repo
    prop = PropertyDef(name="customer_id", datatype="string", description="Customer id")
    binding = PropertyBinding(
        owner_kind="class",
        owner_id="Customer",
        property_name="customer_id",
        required=True,
        unique=True,
        nullable=False,
    )
    repo.list_classes.return_value = [ClassDef(name="Customer", label="Customer", description="Customer class")]
    repo.get_interfaces_of_class.return_value = [InterfaceDef(name="Auditable")]
    repo.get_properties_of_class.return_value = [
        EffectivePropertyDef(property=prop, binding=binding, source_kind="class", source_id="Customer")
    ]
    repo.list_interfaces.return_value = [InterfaceDef(name="Auditable", description="Audit fields")]
    repo.get_properties_of_interface.return_value = []
    repo.list_properties.return_value = [prop]
    repo.list_relationships.return_value = [
        RelationshipDef(
            id="rel_customer_order",
            name="PLACED",
            from_class="Customer",
            to_class="Order",
            description="Customer order",
        )
    ]
    repo.get_properties_of_relationship.return_value = []
    repo.list_constraints.return_value = [
        ConstraintDef(id="customer_unique", kind="unique", target_kind="class", target_id="Customer")
    ]
    repo.list_connectors.return_value = [
        ConnectorDef(name="warehouse", kind="postgres", dsn_ref="WAREHOUSE_DSN")
    ]
    repo.list_source_bindings.return_value = [
        SourceBinding(
            class_name="Customer",
            connector_name="warehouse",
            sql="SELECT customer_id FROM customers",
            key_columns=("customer_id",),
            column_map={"customer_id": "customer_id"},
            links=(
                SourceLink(
                    relationship_name="PLACED",
                    to_class="Order",
                    local_key="customer_id",
                    target_property="customer_id",
                ),
            ),
        )
    ]
    repo.list_views.return_value = [
        ViewDef(
            name="revenue_last_30d",
            class_name="Customer",
            connector_name="warehouse",
            sql="SELECT sum(amount) AS revenue FROM orders WHERE customer_id = :cid",
            params=(ViewParam(name="cid", required=True),),
            ttl_seconds=3600,
            description="Recent revenue",
        )
    ]
    repo.list_triggers.return_value = [
        TriggerDef(
            name="score_on_update",
            class_name="Customer",
            event="update",
            workflow_name="score_workflow",
            parameter_map={"customer_id": "{uuid}"},
        )
    ]

    with patch.object(sys, "argv", ["data-oop", "inspect"]):
        main()

    out = capsys.readouterr().out
    assert "[Properties] (1)" in out
    assert "[Connectors] (1)" in out
    assert "[Source Bindings] (1)" in out
    assert "SELECT customer_id FROM customers" in out
    assert "[Views] (1)" in out
    assert "revenue_last_30d" in out
    assert "params: cid*" in out
    assert "steps_json" in out
    assert 'parameter_map: {"customer_id": "{uuid}"}' in out
