from __future__ import annotations

import os
import sys
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from data_oop import TBoxRepository
from data_oop.cli import load_tbox_repository_from_file, main


def test_load_tbox_repository_from_file_with_builder() -> None:
    # Create a temporary python file containing TBoxBuilder definition
    schema_code = """
from data_oop import TBoxBuilder

builder = TBoxBuilder()
builder.class_("User", description="Mock User class") \\
    .property("username", required=True, unique=True) \\
    .property("email", required=False) \\
    .end() \\
    .class_("Group", description="Mock Group class") \\
    .property("name", required=True) \\
    .end() \\
    .relationship("rel_user_member_group", "MEMBER_OF", "User", "Group")
"""

    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write(schema_code)
        temp_path = f.name

    try:
        repo = load_tbox_repository_from_file(temp_path)
        assert isinstance(repo, TBoxRepository)
        
        # Verify classes loaded
        user_class = repo.get_class("User")
        assert user_class is not None
        assert user_class.description == "Mock User class"
        
        group_class = repo.get_class("Group")
        assert group_class is not None
        assert group_class.description == "Mock Group class"
        
        # Verify relationships loaded
        assert repo.is_relationship_allowed(
            from_class="User", relationship_name="MEMBER_OF", to_class="Group"
        )
    finally:
        os.remove(temp_path)


def test_load_tbox_repository_from_file_with_function() -> None:
    # Create a temporary python file with a build_tbox function
    schema_code = """
from data_oop import TBoxBuilder, InMemoryTBoxRepository

def build_tbox():
    repo = InMemoryTBoxRepository()
    builder = TBoxBuilder(repo)
    builder.class_("Department", description="Mock Department")
    return repo
"""

    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write(schema_code)
        temp_path = f.name

    try:
        repo = load_tbox_repository_from_file(temp_path)
        assert isinstance(repo, TBoxRepository)
        
        dept_class = repo.get_class("Department")
        assert dept_class is not None
        assert dept_class.description == "Mock Department"
    finally:
        os.remove(temp_path)


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


@patch("data_oop.cli.connect_and_load_tbox_to_falkor")
def test_cli_load_tbox_command(mock_load) -> None:
    # Create temp schema file
    schema_code = """
from data_oop import TBoxBuilder
builder = TBoxBuilder()
builder.class_("User")
"""
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write(schema_code)
        temp_path = f.name

    # Mock return result
    mock_result = MagicMock()
    mock_result.nodes = 1
    mock_result.classes = 1
    mock_result.interfaces = 0
    mock_result.relationships = 0
    mock_result.edges = 0
    mock_load.return_value = mock_result

    test_args = ["data-oop", "load-tbox", "--file", temp_path, "--clear"]
    try:
        with patch.object(sys, "argv", test_args):
            main()
            
        mock_load.assert_called_once()
        # Verify the clear parameter passed to connect_and_load_tbox_to_falkor
        kwargs = mock_load.call_args[1]
        assert kwargs["clear"] is True
    finally:
        os.remove(temp_path)
