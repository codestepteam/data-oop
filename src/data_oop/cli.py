from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from falkordb import FalkorDB

from data_oop import (
    FalkorTBoxRepository,
    connect_and_clear_abox_nodes,
    connect_and_run_latest_falkor_abox_validation,
    run_workflow,
    connect_and_upsert_abox_node,
    upsert_abox_relationship,
    connect_and_delete_abox_element,
)


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


def cmd_tbox_create_class(args: argparse.Namespace) -> None:
    """Create a ClassDef in TBox."""
    _, graph = get_db_connection(args)
    repo = FalkorTBoxRepository(graph)
    
    metadata = {}
    if args.metadata:
        try:
            metadata = json.loads(args.metadata)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON for metadata: {e}", file=sys.stderr)
            sys.exit(1)

    print(f"Creating class '{args.class_name}' in TBox...")
    repo.create_class(
        name=args.class_name,
        label=args.label,
        description=args.description,
        metadata=metadata,
    )
    print("Class created successfully.")


def cmd_tbox_create_property(args: argparse.Namespace) -> None:
    """Create a PropertyDef in TBox."""
    _, graph = get_db_connection(args)
    repo = FalkorTBoxRepository(graph)

    metadata = {}
    if args.metadata:
        try:
            metadata = json.loads(args.metadata)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON for metadata: {e}", file=sys.stderr)
            sys.exit(1)

    print(f"Creating property '{args.name}' ({args.datatype}) in TBox...")
    repo.create_property(
        name=args.name,
        datatype=args.datatype,
        description=args.description,
        metadata=metadata,
    )
    print("Property created successfully.")


def cmd_tbox_attach_property(args: argparse.Namespace) -> None:
    """Attach PropertyDef to ClassDef in TBox."""
    _, graph = get_db_connection(args)
    repo = FalkorTBoxRepository(graph)

    metadata = {}
    if args.metadata:
        try:
            metadata = json.loads(args.metadata)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON for metadata: {e}", file=sys.stderr)
            sys.exit(1)

    default_val = None
    if args.default:
        try:
            default_val = json.loads(args.default)
        except json.JSONDecodeError:
            default_val = args.default

    print(f"Attaching property '{args.property}' to class '{args.class_name}'...")
    repo.attach_property_to_class(
        class_name=args.class_name,
        property_name=args.property,
        required=args.required,
        unique=args.unique,
        nullable=args.nullable,
        default=default_val,
        metadata=metadata,
    )
    print("Property attached successfully.")


def cmd_tbox_define_relationship(args: argparse.Namespace) -> None:
    """Define a RelationshipDef in TBox."""
    _, graph = get_db_connection(args)
    repo = FalkorTBoxRepository(graph)

    metadata = {}
    if args.metadata:
        try:
            metadata = json.loads(args.metadata)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON for metadata: {e}", file=sys.stderr)
            sys.exit(1)

    print(f"Defining relationship '{args.id}' ({args.from_class} -[:{args.name}]-> {args.to_class})...")
    repo.define_relationship(
        id=args.id,
        name=args.name,
        from_class=args.from_class,
        to_class=args.to_class,
        min_count=args.min_count,
        max_count=args.max_count,
        required=args.required,
        description=args.description,
        metadata=metadata,
    )
    print("Relationship defined successfully.")


def cmd_abox_upsert_node(args: argparse.Namespace) -> None:
    """Create or update an ABox node instance."""
    properties = {}
    if args.properties:
        try:
            properties = json.loads(args.properties)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON for properties: {e}", file=sys.stderr)
            sys.exit(1)

    host = os.environ.get("FALKOR_HOST", args.host)
    port = int(os.environ.get("FALKOR_PORT", str(args.port)))
    graph_name = os.environ.get("FALKOR_GRAPH", args.graph)
    username = os.environ.get("FALKOR_USERNAME", args.username)
    password = os.environ.get("FALKOR_PASSWORD", args.password)

    print(f"Upserting ABox node '{args.class_name}' with uuid '{args.uuid}'...")
    result = connect_and_upsert_abox_node(
        graph_name=graph_name,
        host=host,
        port=port,
        username=username,
        password=password,
        class_name=args.class_name,
        uuid=args.uuid,
        properties=properties,
    )
    print(f"ABox node upserted successfully: label={result.class_name}, uuid={result.uuid}")


def cmd_abox_upsert_relationship(args: argparse.Namespace) -> None:
    """Create or update an ABox relationship link."""
    _, graph = get_db_connection(args)
    
    properties = {}
    if args.properties:
        try:
            properties = json.loads(args.properties)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON for properties: {e}", file=sys.stderr)
            sys.exit(1)

    print(f"Upserting ABox relationship ({args.from_class} {{{args.from_uuid}}}) -[:{args.name}]-> ({args.to_class} {{{args.to_uuid}}})...")
    result = upsert_abox_relationship(
        graph=graph,
        from_class=args.from_class,
        from_uuid=args.from_uuid,
        relationship_name=args.name,
        to_class=args.to_class,
        to_uuid=args.to_uuid,
        properties=properties,
    )
    print("ABox relationship upserted successfully.")


def cmd_abox_delete(args: argparse.Namespace) -> None:
    """Delete an ABox node or relationship by uuid."""
    host = os.environ.get("FALKOR_HOST", args.host)
    port = int(os.environ.get("FALKOR_PORT", str(args.port)))
    graph_name = os.environ.get("FALKOR_GRAPH", args.graph)
    username = os.environ.get("FALKOR_USERNAME", args.username)
    password = os.environ.get("FALKOR_PASSWORD", args.password)

    print(f"Deleting ABox element with uuid '{args.uuid}' from graph '{graph_name}'...")
    nodes_deleted, rels_deleted = connect_and_delete_abox_element(
        graph_name=graph_name,
        host=host,
        port=port,
        username=username,
        password=password,
        uuid=args.uuid,
    )
    if nodes_deleted > 0:
        print(f"Successfully deleted ABox node: uuid={args.uuid}")
    elif rels_deleted > 0:
        print(f"Successfully deleted ABox relationship: uuid={args.uuid}")
    else:
        print(f"No node or relationship found with uuid '{args.uuid}'.")


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

    # tbox-create-class
    p_tbox_class = subparsers.add_parser("tbox-create-class", help="Create a ClassDef in TBox")
    p_tbox_class.add_argument("--class-name", required=True, help="Name of the ClassDef")
    p_tbox_class.add_argument("--label", help="Label for the ClassDef")
    p_tbox_class.add_argument("--description", help="Description")
    p_tbox_class.add_argument("--metadata", help="JSON string metadata")
    p_tbox_class.set_defaults(func=cmd_tbox_create_class)

    # tbox-create-property
    p_tbox_prop = subparsers.add_parser("tbox-create-property", help="Create a PropertyDef in TBox")
    p_tbox_prop.add_argument("--name", required=True, help="Name of the PropertyDef")
    p_tbox_prop.add_argument("--datatype", default="string", help="Datatype (default: string)")
    p_tbox_prop.add_argument("--description", help="Description")
    p_tbox_prop.add_argument("--metadata", help="JSON string metadata")
    p_tbox_prop.set_defaults(func=cmd_tbox_create_property)

    # tbox-attach-property
    p_tbox_attach = subparsers.add_parser("tbox-attach-property", help="Attach PropertyDef to ClassDef in TBox")
    p_tbox_attach.add_argument("--class-name", required=True, help="Name of the ClassDef")
    p_tbox_attach.add_argument("--property", required=True, help="Name of the PropertyDef")
    p_tbox_attach.add_argument("--required", action="store_true", help="Set required constraint")
    p_tbox_attach.add_argument("--unique", action="store_true", help="Set unique constraint")
    p_tbox_attach.add_argument("--nullable", type=bool, default=True, help="Set nullable constraint (default: True)")
    p_tbox_attach.add_argument("--default", help="Default value")
    p_tbox_attach.add_argument("--metadata", help="JSON string metadata")
    p_tbox_attach.set_defaults(func=cmd_tbox_attach_property)

    # tbox-define-relationship
    p_tbox_rel = subparsers.add_parser("tbox-define-relationship", help="Define a RelationshipDef in TBox")
    p_tbox_rel.add_argument("--id", required=True, help="Unique ID of the relationship definition")
    p_tbox_rel.add_argument("--name", required=True, help="Name (type) of the relationship (e.g., HAS_MEMBER)")
    p_tbox_rel.add_argument("--from-class", required=True, help="From ClassDef name")
    p_tbox_rel.add_argument("--to-class", required=True, help="To ClassDef name")
    p_tbox_rel.add_argument("--required", action="store_true", help="Set required constraint")
    p_tbox_rel.add_argument("--min-count", type=int, default=0, help="Min count constraint (default: 0)")
    p_tbox_rel.add_argument("--max-count", type=int, help="Max count constraint")
    p_tbox_rel.add_argument("--description", help="Description")
    p_tbox_rel.add_argument("--metadata", help="JSON string metadata")
    p_tbox_rel.set_defaults(func=cmd_tbox_define_relationship)

    # abox-upsert-node
    p_abox_node = subparsers.add_parser("abox-upsert-node", help="Create or update an ABox node instance")
    p_abox_node.add_argument("--class-name", required=True, help="Domain class name")
    p_abox_node.add_argument("--uuid", required=True, help="UUID of the instance")
    p_abox_node.add_argument("--properties", help="JSON string of property values")
    p_abox_node.set_defaults(func=cmd_abox_upsert_node)

    # abox-upsert-relationship
    p_abox_rel = subparsers.add_parser("abox-upsert-relationship", help="Create or update an ABox relationship link")
    p_abox_rel.add_argument("--from-class", required=True, help="From node domain class name")
    p_abox_rel.add_argument("--from-uuid", required=True, help="From node UUID")
    p_abox_rel.add_argument("--name", required=True, help="Relationship type name")
    p_abox_rel.add_argument("--to-class", required=True, help="To node domain class name")
    p_abox_rel.add_argument("--to-uuid", required=True, help="To node UUID")
    p_abox_rel.add_argument("--properties", help="JSON string of relationship property values")
    p_abox_rel.set_defaults(func=cmd_abox_upsert_relationship)

    # abox-delete
    p_abox_del = subparsers.add_parser("abox-delete", help="Delete a single ABox node or relationship by uuid")
    p_abox_del.add_argument("--uuid", required=True, help="UUID of the node or relationship to delete")
    p_abox_del.set_defaults(func=cmd_abox_delete)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()
