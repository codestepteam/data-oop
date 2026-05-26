from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any

from falkordb import FalkorDB

from data_oop import (
    InMemoryTBoxRepository,
    FalkorTBoxRepository,
    connect_and_clear_abox_nodes,
    connect_and_load_tbox_to_falkor,
    connect_and_run_latest_falkor_abox_validation,
    run_workflow,
)


def load_tbox_repository_from_file(filepath: str) -> Any:
    """Dynamically load python file and extract a TBoxRepository or TBoxBuilder."""
    path = Path(filepath).resolve()
    if not path.exists():
        print(f"Error: Schema file not found: {path}", file=sys.stderr)
        sys.exit(1)

    module_name = path.stem
    spec = importlib.util.spec_from_file_location(module_name, str(path))
    if spec is None or spec.loader is None:
        print(f"Error: Cannot load module from path: {path}", file=sys.stderr)
        sys.exit(1)

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as e:
        print(f"Error while executing schema file: {e}", file=sys.stderr)
        sys.exit(1)

    from data_oop import TBoxBuilder, TBoxRepository

    # 1. Search for a function named build_tbox or build_schema
    for func_name in ("build_tbox", "build_schema"):
        if hasattr(module, func_name):
            func = getattr(module, func_name)
            if callable(func):
                result = func()
                if isinstance(result, TBoxRepository):
                    return result
                elif isinstance(result, TBoxBuilder):
                    return result.build()

    # 2. Search for a global TBoxRepository instance
    for name in dir(module):
        obj = getattr(module, name)
        # Avoid checking module types themselves or classes, just check instances
        if not isinstance(obj, type) and isinstance(obj, TBoxRepository):
            return obj

    # 3. Search for a global TBoxBuilder instance
    for name in dir(module):
        obj = getattr(module, name)
        if not isinstance(obj, type) and isinstance(obj, TBoxBuilder):
            return obj.build()

    print(
        "Error: Could not find any TBoxRepository, TBoxBuilder, or build_tbox()/build_schema() function in the schema file.",
        file=sys.stderr,
    )
    sys.exit(1)


def get_db_connection(args: argparse.Namespace) -> tuple[FalkorDB, Any]:
    """Helper to connect to FalkorDB based on CLI arguments and Env variables."""
    host = os.environ.get("FALKOR_HOST", args.host)
    port = int(os.environ.get("FALKOR_PORT", str(args.port)))
    graph_name = os.environ.get("FALKOR_GRAPH", args.graph)
    username = os.environ.get("FALKOR_USERNAME", args.username)
    password = os.environ.get("FALKOR_PASSWORD", args.password)

    db = FalkorDB(host=host, port=port, username=username, password=password)
    graph = db.select_graph(graph_name)
    return db, graph


def cmd_validate(args: argparse.Namespace) -> None:
    """Run ABox validation."""
    host = os.environ.get("FALKOR_HOST", args.host)
    port = int(os.environ.get("FALKOR_PORT", str(args.port)))
    graph_name = os.environ.get("FALKOR_GRAPH", args.graph)
    username = os.environ.get("FALKOR_USERNAME", args.username)
    password = os.environ.get("FALKOR_PASSWORD", args.password)

    print(f"Running ABox validation against graph '{graph_name}'...")
    result = connect_and_run_latest_falkor_abox_validation(
        graph_name=graph_name,
        host=host,
        port=port,
        username=username,
        password=password,
        run_id=args.run_id,
    )
    print(f"Validation finished. Run ID: {result.run_id}")
    print(f"Status: {result.status}")
    print(f"Checked Nodes: {result.checked_instance_count}")
    print(f"Issues Found: {result.issue_count} (Errors: {result.error_count}, Warnings: {result.warning_count})")
    
    if result.error_count > 0:
        print("\nVerification failed: errors present in ABox nodes.")
        sys.exit(1)
    else:
        print("\nVerification successful.")


def cmd_clear_abox(args: argparse.Namespace) -> None:
    """Clear ABox nodes."""
    host = os.environ.get("FALKOR_HOST", args.host)
    port = int(os.environ.get("FALKOR_PORT", str(args.port)))
    graph_name = os.environ.get("FALKOR_GRAPH", args.graph)
    username = os.environ.get("FALKOR_USERNAME", args.username)
    password = os.environ.get("FALKOR_PASSWORD", args.password)

    confirm = args.yes or input(f"Are you sure you want to clear ABox nodes in '{graph_name}'? [y/N]: ").lower().strip() == 'y'
    if not confirm:
        print("Cancelled.")
        return

    print(f"Clearing ABox nodes in graph '{graph_name}'...")
    connect_and_clear_abox_nodes(
        graph_name=graph_name,
        host=host,
        port=port,
        username=username,
        password=password,
    )
    print("ABox nodes cleared successfully.")


def cmd_load_tbox(args: argparse.Namespace) -> None:
    """Load TBox schema definitions from a python file."""
    repo = load_tbox_repository_from_file(args.file)

    host = os.environ.get("FALKOR_HOST", args.host)
    port = int(os.environ.get("FALKOR_PORT", str(args.port)))
    graph_name = os.environ.get("FALKOR_GRAPH", args.graph)
    username = os.environ.get("FALKOR_USERNAME", args.username)
    password = os.environ.get("FALKOR_PASSWORD", args.password)

    print(f"Loading TBox into graph '{graph_name}' (clear={args.clear})...")
    result = connect_and_load_tbox_to_falkor(
        repo,
        graph_name=graph_name,
        host=host,
        port=port,
        username=username,
        password=password,
        clear=args.clear,
    )
    print("TBox schema loaded successfully.")
    print(f"Created nodes: {result.nodes} (Classes: {result.classes}, Interfaces: {result.interfaces}, Relationships: {result.relationships})")
    print(f"Created edges: {result.edges}")


def cmd_run_workflow(args: argparse.Namespace) -> None:
    """Run a workflow stored in FalkorDB."""
    _, graph = get_db_connection(args)

    # Parse parameters
    params = {}
    if args.params:
        try:
            params = json.loads(args.params)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON string for params: {e}", file=sys.stderr)
            sys.exit(1)
    elif args.params_file:
        path = Path(args.params_file).resolve()
        if not path.exists():
            print(f"Error: Params file not found: {path}", file=sys.stderr)
            sys.exit(1)
        try:
            with open(path, "r", encoding="utf-8") as f:
                params = json.load(f)
        except Exception as e:
            print(f"Error reading params file: {e}", file=sys.stderr)
            sys.exit(1)

    print(f"Running workflow '{args.name}' with params: {params}...")
    try:
        results = run_workflow(graph=graph, name=args.name, parameters=params)
        print("Workflow executed successfully!")
        print(json.dumps(results, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"Error running workflow: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_inspect(args: argparse.Namespace) -> None:
    """Inspect and list TBox definition elements from FalkorDB."""
    _, graph = get_db_connection(args)
    repo = FalkorTBoxRepository(graph)

    print(f"=== Inspecting TBox Graph: {args.graph} ===")
    
    classes = repo.list_classes()
    print(f"\n[Classes] ({len(classes)})")
    for cls in classes:
        print(f"  - {cls.name} (label: {cls.label or 'None'}) - {cls.description or ''}")
        props = repo.get_properties_of_class(cls.name)
        if props:
            print("    Properties:")
            for p in props:
                req_str = "required" if p.binding.required else "optional"
                uniq_str = ", unique" if p.binding.unique else ""
                print(f"      * {p.property.name} ({p.property.datatype}, {req_str}{uniq_str}) - {p.property.description or ''}")

    interfaces = repo.list_interfaces()
    if interfaces:
        print(f"\n[Interfaces] ({len(interfaces)})")
        for iface in interfaces:
            print(f"  - {iface.name} - {iface.description or ''}")

    relationships = repo.list_relationships()
    print(f"\n[Relationships] ({len(relationships)})")
    for rel in relationships:
        req_str = "required" if rel.required else "optional"
        min_max = f"cardinality: {rel.min_count}..{rel.max_count or 'N'}"
        print(f"  - {rel.id}: ({rel.from_class}) -[:{rel.name}]-> ({rel.to_class}) [{req_str}, {min_max}] - {rel.description or ''}")

    # Inspect workflows
    try:
        res = graph.query("MATCH (w:WorkflowDefinition) RETURN w.uuid, w.name, w.description")
        rows = getattr(res, "result_set", []) or []
        print(f"\n[Workflow Definitions] ({len(rows)})")
        for row in rows:
            print(f"  - Name: {row[1]} (uuid: {row[0]}) - {row[2] or ''}")
    except Exception:
        pass


def main() -> None:
    parser = argparse.ArgumentParser(
        description="CLI utility for data-oop FalkorDB TBox and ABox schema operations."
    )
    
    # Global database options
    parser.add_argument("--host", default="localhost", help="FalkorDB host (default: localhost / env: FALKOR_HOST)")
    parser.add_argument("--port", type=int, default=6380, help="FalkorDB port (default: 6380 / env: FALKOR_PORT)")
    parser.add_argument("--graph", default="data_oop", help="FalkorDB graph name (default: data_oop / env: FALKOR_GRAPH)")
    parser.add_argument("--username", default=None, help="FalkorDB username (env: FALKOR_USERNAME)")
    parser.add_argument("--password", default=None, help="FalkorDB password (env: FALKOR_PASSWORD)")

    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # validate
    parser_validate = subparsers.add_parser("validate", help="Run ABox node validation against TBox schema")
    parser_validate.add_argument("--run-id", default=None, help="Optional custom run ID for this validation")
    parser_validate.set_defaults(func=cmd_validate)

    # clear-abox
    parser_clear = subparsers.add_parser("clear-abox", help="Clear all ABox domain nodes from FalkorDB")
    parser_clear.add_argument("-y", "--yes", action="store_true", help="Confirm clearing without interactive prompt")
    parser_clear.set_defaults(func=cmd_clear_abox)

    # load-tbox
    parser_load = subparsers.add_parser("load-tbox", help="Load TBox schema definitions from a python file")
    parser_load.add_argument("-f", "--file", required=True, help="Path to Python schema file containing tbox definitions")
    parser_load.add_argument("--clear", action="store_true", help="Delete entire graph before loading")
    parser_load.set_defaults(func=cmd_load_tbox)

    # run-workflow
    parser_workflow = subparsers.add_parser("run-workflow", help="Run a workflow definition stored in FalkorDB")
    parser_workflow.add_argument("-n", "--name", required=True, help="Name of the workflow definition to run")
    group = parser_workflow.add_mutually_exclusive_group()
    group.add_argument("-p", "--params", help="JSON string of parameter bindings")
    group.add_argument("-f", "--params-file", help="Path to a JSON file containing parameter bindings")
    parser_workflow.set_defaults(func=cmd_run_workflow)

    # inspect
    parser_inspect = subparsers.add_parser("inspect", help="List all defined Classes, Properties, Relationships and Workflows")
    parser_inspect.set_defaults(func=cmd_inspect)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()
