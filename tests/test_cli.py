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
