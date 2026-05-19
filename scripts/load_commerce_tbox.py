from __future__ import annotations

import argparse

from tbox import TBoxValidator, build_commerce_tbox, connect_and_load_tbox_to_falkor


def main() -> None:
    parser = argparse.ArgumentParser(description="Load commerce TBox into FalkorDB")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=6380)
    parser.add_argument("--graph", default="commerce_tbox")
    parser.add_argument("--username", default=None)
    parser.add_argument("--password", default=None)
    parser.add_argument("--clear", action="store_true", help="Delete graph before loading")
    args = parser.parse_args()

    repo = build_commerce_tbox()
    TBoxValidator(repo).validate_tbox().raise_if_invalid()

    result = connect_and_load_tbox_to_falkor(
        repo,
        graph_name=args.graph,
        host=args.host,
        port=args.port,
        username=args.username,
        password=args.password,
        clear=args.clear,
    )

    print(
        f"Loaded graph={result.graph_name} "
        f"nodes={result.nodes} edges={result.edges} "
        f"classes={result.classes} interfaces={result.interfaces} "
        f"properties={result.properties} relationships={result.relationships} "
        f"constraints={result.constraints}"
    )


if __name__ == "__main__":
    main()
