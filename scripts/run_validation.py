from __future__ import annotations

import argparse

from tbox import connect_and_run_latest_falkor_abox_validation


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run latest-only ABox validation against current FalkorDB TBox"
    )
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=6380)
    parser.add_argument("--graph", default="commerce_tbox")
    parser.add_argument("--username", default=None)
    parser.add_argument("--password", default=None)
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args()

    result = connect_and_run_latest_falkor_abox_validation(
        graph_name=args.graph,
        host=args.host,
        port=args.port,
        username=args.username,
        password=args.password,
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
