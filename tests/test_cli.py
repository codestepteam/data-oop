from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

from data_oop.cli import main


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
    mock_result = MagicMock()
    mock_result.class_name = "User"
    mock_result.uuid = "user-1"
    mock_upsert.return_value = mock_result

    test_args = [
        "data-oop",
        "abox-upsert-node",
        "--class-name", "User",
        "--uuid", "user-1",
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
        uuid="user-1",
        properties={"name": "Alice", "age": 30}
    )


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
