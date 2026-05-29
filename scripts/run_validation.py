from __future__ import annotations

import argparse
import os

from data_oop import connect_and_run_latest_falkor_abox_validation
from data_oop.cli import load_dotenv


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(
        description="Run latest-only ABox validation against current FalkorDB TBox"
    )
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=6380)
    parser.add_argument("--graph", default="data_oop")
    parser.add_argument("--username", default=None)
    parser.add_argument("--password", default=None)
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args()

    host = os.environ.get("FALKORDB_HOST", os.environ.get("FALKOR_HOST", args.host))
    port = int(os.environ.get("FALKORDB_PORT", os.environ.get("FALKOR_PORT", str(args.port))))
    graph_name = os.environ.get("FALKORDB_GRAPH", os.environ.get("FALKOR_GRAPH", args.graph))
    username = os.environ.get("FALKORDB_USERNAME", os.environ.get("FALKOR_USERNAME", args.username))
    password = os.environ.get("FALKORDB_PASSWORD", os.environ.get("FALKOR_PASSWORD", args.password))

    result = connect_and_run_latest_falkor_abox_validation(
        graph_name=graph_name,
        host=host,
        port=port,
        username=username,
        password=password,
        run_id=args.run_id,
    )
    print(
        f"ValidationRun id={result.run_id} status={result.status} "
        f"checked={result.checked_instance_count} "
        f"errors={result.error_count} warnings={result.warning_count} "
        f"issues={result.issue_count}"
    )


if __name__ == "__main__":
    main()
