from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from falkordb import FalkorDB

from data_oop import (
    FalkorTBoxRepository,
    MetricDef,
    SourceLink,
    connect_and_clear_abox_nodes,
    connect_and_run_latest_falkor_abox_validation,
    materialize_source,
    resolve_metric,
    run_workflow,
    connect_and_upsert_abox_node,
    upsert_abox_relationship,
    connect_and_delete_abox_element,
    dump_graph_to_file,
    restore_graph_from_file,
)


def _read_sql_arg(value: str) -> str:
    """Return SQL text. A leading '@' reads from a file (avoids shell-quoting long SQL)."""
    if value.startswith("@"):
        path = Path(value[1:]).resolve()
        if not path.exists():
            print(f"Error: SQL file not found: {path}", file=sys.stderr)
            sys.exit(1)
        return path.read_text(encoding="utf-8")
    return value


def _get_db_env_values(args: argparse.Namespace) -> tuple[str, int, str, str | None, str | None]:
    """Helper to retrieve FalkorDB connection params from environment or args."""
    host = os.environ.get("FALKORDB_HOST", os.environ.get("FALKOR_HOST", args.host))
    port = int(os.environ.get("FALKORDB_PORT", os.environ.get("FALKOR_PORT", str(args.port))))
    graph_name = os.environ.get("FALKORDB_GRAPH", os.environ.get("FALKOR_GRAPH", args.graph))
    username = os.environ.get("FALKORDB_USERNAME", os.environ.get("FALKOR_USERNAME", args.username))
    password = os.environ.get("FALKORDB_PASSWORD", os.environ.get("FALKOR_PASSWORD", args.password))
    return host, port, graph_name, username, password


def get_db_connection(args: argparse.Namespace) -> tuple[FalkorDB, Any]:
    """Helper to connect to FalkorDB based on CLI arguments and Env variables."""
    host, port, graph_name, username, password = _get_db_env_values(args)

    db = FalkorDB(host=host, port=port, username=username, password=password)
    graph = db.select_graph(graph_name)
    return db, graph


def cmd_validate(args: argparse.Namespace) -> None:
    """Run ABox validation."""
    host, port, graph_name, username, password = _get_db_env_values(args)

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
    host, port, graph_name, username, password = _get_db_env_values(args)

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


def _format_json(value: Any) -> str:
    """Stable one-line JSON for inspect detail fields."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _print_metadata(metadata: dict[str, Any], *, indent: str = "    ") -> None:
    if metadata:
        print(f"{indent}metadata: {_format_json(metadata)}")


def _print_effective_properties(props: list[Any], *, indent: str = "    ") -> None:
    if not props:
        return
    print(f"{indent}Properties:")
    for p in props:
        req_str = "required" if p.binding.required else "optional"
        uniq_str = ", unique" if p.binding.unique else ""
        nullable_str = ", nullable" if p.binding.nullable else ", not-null"
        default_str = f", default={p.binding.default!r}" if p.binding.default is not None else ""
        print(
            f"{indent}  * {p.property.name} ({p.property.datatype}, "
            f"{req_str}{uniq_str}{nullable_str}{default_str}) "
            f"from {p.source_kind}:{p.source_id} - {p.property.description or p.binding.description or ''}"
        )
        _print_metadata(p.property.metadata, indent=f"{indent}    ")
        if p.binding.metadata:
            print(f"{indent}    binding metadata: {_format_json(p.binding.metadata)}")


def cmd_inspect(args: argparse.Namespace) -> None:
    """Inspect and list every known TBox definition element from FalkorDB."""
    _, graph = get_db_connection(args)
    repo = FalkorTBoxRepository(graph)

    print(f"=== Inspecting TBox Graph: {graph.name} ===")

    classes = repo.list_classes()
    print(f"\n[Classes] ({len(classes)})")
    for cls in classes:
        print(f"  - {cls.name} (label: {cls.label or 'None'}) - {cls.description or ''}")
        _print_metadata(cls.metadata)
        class_interfaces = repo.get_interfaces_of_class(cls.name)
        if class_interfaces:
            print("    Implements: " + ", ".join(iface.name for iface in class_interfaces))
        _print_effective_properties(repo.get_properties_of_class(cls.name))

    interfaces = repo.list_interfaces()
    print(f"\n[Interfaces] ({len(interfaces)})")
    for iface in interfaces:
        print(f"  - {iface.name} - {iface.description or ''}")
        _print_metadata(iface.metadata)
        _print_effective_properties(repo.get_properties_of_interface(iface.name))

    properties = repo.list_properties()
    print(f"\n[Properties] ({len(properties)})")
    for prop in properties:
        print(f"  - {prop.name} ({prop.datatype}) - {prop.description or ''}")
        _print_metadata(prop.metadata)

    relationships = repo.list_relationships()
    print(f"\n[Relationships] ({len(relationships)})")
    for rel in relationships:
        req_str = "required" if rel.required else "optional"
        min_max = f"cardinality: {rel.min_count}..{rel.max_count or 'N'}"
        print(
            f"  - {rel.id}: ({rel.from_class}) -[:{rel.name}]-> ({rel.to_class}) "
            f"[{req_str}, {min_max}] - {rel.description or ''}"
        )
        _print_metadata(rel.metadata)
        _print_effective_properties(repo.get_properties_of_relationship(rel.id))

    constraints = repo.list_constraints()
    print(f"\n[Constraints] ({len(constraints)})")
    for const in constraints:
        prop_names = ",".join(const.property_names) or "None"
        print(
            f"  - {const.id}: {const.kind} on {const.target_kind} '{const.target_id}' "
            f"[severity={const.severity}, properties={prop_names}] - {const.description or ''}"
        )
        if const.expression:
            print(f"    expression: {const.expression}")
        _print_metadata(const.metadata)

    connectors = repo.list_connectors()
    print(f"\n[Connectors] ({len(connectors)})")
    for connector in connectors:
        print(
            f"  - {connector.name} (kind={connector.kind}, dsn_ref={connector.dsn_ref or 'None'}) "
            f"- {connector.description or ''}"
        )
        _print_metadata(connector.metadata)

    source_bindings = repo.list_source_bindings()
    print(f"\n[Source Bindings] ({len(source_bindings)})")
    for binding in source_bindings:
        keys = ",".join(binding.key_columns) or "None"
        print(
            f"  - {binding.class_name} <- {binding.connector_name} "
            f"[keys={keys}, materialization={binding.materialization}, "
            f"refresh_interval_hours={binding.refresh_interval_hours or 'None'}]"
        )
        if binding.column_map:
            print(f"    column_map: {_format_json(binding.column_map)}")
        if binding.links:
            print(f"    links: {_format_json([asdict(link) for link in binding.links])}")
        print(f"    sql: {binding.sql}")

    metrics = repo.list_metrics()
    print(f"\n[Metrics] ({len(metrics)})")
    for metric in metrics:
        print(
            f"  - {metric.name} on {metric.class_name} <- {metric.connector_name} "
            f"[result_kind={metric.result_kind}, value_column={metric.value_column}, "
            f"ttl_seconds={metric.ttl_seconds or 'live'}] - {metric.description or ''}"
        )
        if metric.param_map:
            print(f"    param_map: {_format_json(metric.param_map)}")
        print(f"    sql: {metric.sql}")

    # Inspect workflows
    try:
        res = graph.query(
            "MATCH (w:WorkflowDefinition) "
            "RETURN w.uuid, w.name, w.description, w.steps_json, w.parameters_json"
        )
        rows = getattr(res, "result_set", []) or []
        print(f"\n[Workflow Definitions] ({len(rows)})")
        for row in rows:
            print(f"  - Name: {row[1]} (uuid: {row[0]}) - {row[2] or ''}")
            if len(row) > 4 and row[4]:
                print(f"    parameters_json: {row[4]}")
            if len(row) > 3 and row[3]:
                print(f"    steps_json: {row[3]}")
    except Exception:
        pass

    # Inspect triggers
    triggers = repo.list_triggers()
    print(f"\n[Triggers] ({len(triggers)})")
    for t in triggers:
        state = "" if t.enabled else " [disabled]"
        cond = f" if {t.condition}" if t.condition else ""
        print(
            f"  - {t.name}: ({t.class_name}) on {t.event}{cond} -> "
            f"workflow '{t.workflow_name}' [order={t.order}]{state} - {t.description or ''}"
        )
        if t.parameter_map:
            print(f"    parameter_map: {_format_json(t.parameter_map)}")


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

    nullable_val = args.nullable == "true"

    print(f"Attaching property '{args.property}' to class '{args.class_name}'...")
    repo.attach_property_to_class(
        class_name=args.class_name,
        property_name=args.property,
        required=args.required,
        unique=args.unique,
        nullable=nullable_val,
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

    node_uuid = args.uuid or str(uuid4())
    try:
        UUID(node_uuid)
    except ValueError:
        print(f"Error: --uuid must be a valid UUID: {node_uuid}", file=sys.stderr)
        sys.exit(1)

    host, port, graph_name, username, password = _get_db_env_values(args)

    print(f"Upserting ABox node '{args.class_name}' with uuid '{node_uuid}'...")
    result = connect_and_upsert_abox_node(
        graph_name=graph_name,
        host=host,
        port=port,
        username=username,
        password=password,
        class_name=args.class_name,
        uuid=node_uuid,
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
    host, port, graph_name, username, password = _get_db_env_values(args)

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


def cmd_tbox_delete_class(args: argparse.Namespace) -> None:
    """Delete a ClassDef in TBox."""
    _, graph = get_db_connection(args)
    repo = FalkorTBoxRepository(graph)
    
    print(f"Deleting class '{args.class_name}' from TBox (detach={args.detach})...")
    repo.delete_class(name=args.class_name, detach=args.detach)
    print("Class deleted successfully.")


def cmd_tbox_delete_property(args: argparse.Namespace) -> None:
    """Delete a PropertyDef in TBox."""
    _, graph = get_db_connection(args)
    repo = FalkorTBoxRepository(graph)

    print(f"Deleting property '{args.name}' from TBox (detach={args.detach})...")
    repo.delete_property(name=args.name, detach=args.detach)
    print("Property deleted successfully.")


def cmd_tbox_detach_property(args: argparse.Namespace) -> None:
    """Detach PropertyDef from ClassDef in TBox."""
    _, graph = get_db_connection(args)
    repo = FalkorTBoxRepository(graph)

    print(f"Detaching property '{args.property}' from class '{args.class_name}'...")
    repo.detach_property_from_class(class_name=args.class_name, property_name=args.property)
    print("Property detached successfully.")


def cmd_tbox_delete_relationship(args: argparse.Namespace) -> None:
    """Delete a RelationshipDef in TBox."""
    _, graph = get_db_connection(args)
    repo = FalkorTBoxRepository(graph)

    print(f"Deleting relationship '{args.id}' from TBox...")
    repo.delete_relationship(id=args.id)
    print("Relationship deleted successfully.")


def cmd_db_dump(args: argparse.Namespace) -> None:
    """Dump FalkorDB graph to a file."""
    host, port, graph_name, username, password = _get_db_env_values(args)

    print(f"Dumping graph '{graph_name}' to '{args.file}'...")
    try:
        dump_graph_to_file(
            filepath=args.file,
            graph_name=graph_name,
            host=host,
            port=port,
            username=username,
            password=password,
        )
        print("Graph dumped successfully.")
    except Exception as e:
        print(f"Error dumping graph: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_db_restore(args: argparse.Namespace) -> None:
    """Restore FalkorDB graph from a file."""
    host, port, graph_name, username, password = _get_db_env_values(args)

    print(f"Restoring graph '{graph_name}' from '{args.file}'...")
    try:
        restore_graph_from_file(
            filepath=args.file,
            graph_name=graph_name,
            host=host,
            port=port,
            username=username,
            password=password,
        )
        print("Graph restored successfully.")
    except Exception as e:
        print(f"Error restoring graph: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_define_connector(args: argparse.Namespace) -> None:
    """Define an external RDB connector (stores only an env-var reference, no secrets)."""
    _, graph = get_db_connection(args)
    repo = FalkorTBoxRepository(graph)

    metadata = {}
    if args.metadata:
        try:
            metadata = json.loads(args.metadata)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON for metadata: {e}", file=sys.stderr)
            sys.exit(1)

    print(f"Defining connector '{args.name}' (kind={args.kind})...")
    repo.define_connector(
        name=args.name,
        kind=args.kind,
        dsn_ref=args.dsn_ref or "",
        description=args.description,
        metadata=metadata,
    )
    print("Connector defined successfully.")


def cmd_list_connectors(args: argparse.Namespace) -> None:
    """List defined connectors and their source bindings."""
    _, graph = get_db_connection(args)
    repo = FalkorTBoxRepository(graph)

    connectors = repo.list_connectors()
    print(f"[Connectors] ({len(connectors)})")
    for c in connectors:
        print(f"  - {c.name} (kind={c.kind}, dsn_ref={c.dsn_ref or 'None'}) - {c.description or ''}")

    bindings = repo.list_source_bindings()
    print(f"\n[Source bindings] ({len(bindings)})")
    for b in bindings:
        print(
            f"  - {b.class_name} <- {b.connector_name} "
            f"[keys={','.join(b.key_columns)}, {b.materialization}]"
        )


def cmd_delete_connector(args: argparse.Namespace) -> None:
    """Delete a connector (blocked while classes are bound unless --detach)."""
    _, graph = get_db_connection(args)
    repo = FalkorTBoxRepository(graph)

    print(f"Deleting connector '{args.name}' (detach={args.detach})...")
    repo.delete_connector(args.name, detach=args.detach)
    print("Connector deleted successfully.")


def cmd_bind_source(args: argparse.Namespace) -> None:
    """Bind a class to an RDB query that produces its aggregate/segment instances."""
    _, graph = get_db_connection(args)
    repo = FalkorTBoxRepository(graph)

    column_map = {}
    if args.column_map:
        try:
            column_map = json.loads(args.column_map)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON for column-map: {e}", file=sys.stderr)
            sys.exit(1)

    key_columns = tuple(c.strip() for c in args.key_columns.split(",") if c.strip())
    if not key_columns:
        print("Error: --key-columns must list at least one column", file=sys.stderr)
        sys.exit(1)

    links: list[SourceLink] = []
    for raw in args.link or []:
        try:
            spec = json.loads(raw)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON for --link: {e}", file=sys.stderr)
            sys.exit(1)
        try:
            links.append(
                SourceLink(
                    relationship_name=spec["rel"],
                    to_class=spec["to"],
                    local_key=spec["key"],
                    target_property=spec.get("target", ""),
                    direction=spec.get("dir", "out"),
                )
            )
        except KeyError as e:
            print(f"Error: --link missing required field {e} (need rel, to, key)", file=sys.stderr)
            sys.exit(1)

    print(f"Binding class '{args.class_name}' to connector '{args.connector}'...")
    repo.attach_source_binding_to_class(
        class_name=args.class_name,
        connector_name=args.connector,
        sql=_read_sql_arg(args.sql),
        key_columns=key_columns,
        column_map=column_map,
        materialization=args.materialization,
        refresh_interval_hours=args.refresh_interval_hours,
        links=tuple(links),
    )
    print("Source binding attached successfully.")


def cmd_sync_source(args: argparse.Namespace) -> None:
    """Run a class's bound RDB query and materialize result rows as ABox nodes."""
    _, graph = get_db_connection(args)
    repo = FalkorTBoxRepository(graph)

    print(f"Syncing source-backed class '{args.class_name}' (prune={not args.no_prune})...")
    try:
        result = materialize_source(
            repo=repo,
            graph=graph,
            class_name=args.class_name,
            prune=not args.no_prune,
        )
    except Exception as e:
        print(f"Error syncing source: {e}", file=sys.stderr)
        sys.exit(1)
    print(
        f"Sync done: fetched={result.rows_fetched}, upserted={result.nodes_upserted}, "
        f"pruned={result.nodes_pruned}, edges={result.edges_upserted}, "
        f"links_missing={result.links_missing}, synced_at={result.synced_at}"
    )


def cmd_define_metric(args: argparse.Namespace) -> None:
    """Attach a named parameterized RDB query to a class (resolved on demand, never copied)."""
    _, graph = get_db_connection(args)
    repo = FalkorTBoxRepository(graph)

    param_map = {}
    if args.param_map:
        try:
            param_map = json.loads(args.param_map)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON for --param-map: {e}", file=sys.stderr)
            sys.exit(1)

    print(f"Defining metric '{args.name}' on class '{args.class_name}'...")
    repo.define_metric(
        MetricDef(
            name=args.name,
            class_name=args.class_name,
            connector_name=args.connector,
            sql=_read_sql_arg(args.sql),
            param_map=param_map,
            result_kind=args.result_kind,
            value_column=args.value_column,
            ttl_seconds=args.ttl_seconds,
            description=args.description,
        )
    )
    print("Metric defined successfully.")


def cmd_list_metrics(args: argparse.Namespace) -> None:
    """List defined metrics (optionally filtered by class)."""
    _, graph = get_db_connection(args)
    repo = FalkorTBoxRepository(graph)

    metrics = repo.list_metrics(class_name=args.class_name)
    print(f"[Metrics] ({len(metrics)})")
    for m in metrics:
        print(
            f"  - {m.name} on {m.class_name} <- {m.connector_name} "
            f"[{m.result_kind}, ttl={m.ttl_seconds or 'live'}] - {m.description or ''}"
        )


def cmd_delete_metric(args: argparse.Namespace) -> None:
    """Delete a metric definition by name."""
    _, graph = get_db_connection(args)
    repo = FalkorTBoxRepository(graph)

    print(f"Deleting metric '{args.name}'...")
    repo.delete_metric(args.name)
    print("Metric deleted successfully.")


def cmd_resolve_metric(args: argparse.Namespace) -> None:
    """Resolve a metric live and print its value. Optionally bind an anchor node."""
    _, graph = get_db_connection(args)
    repo = FalkorTBoxRepository(graph)

    metric = repo.get_metric(args.name)
    if metric is None:
        print(f"Error: MetricDef not found: {args.name}", file=sys.stderr)
        sys.exit(1)

    node = None
    if args.node_uuid:
        from data_oop.falkor_abox import _safe_identifier

        label = _safe_identifier(metric.class_name, "class")
        rows = graph.query(
            f"MATCH (n:{label} {{uuid: $uuid}}) RETURN properties(n)",
            {"uuid": args.node_uuid},
        ).result_set
        if not rows or not rows[0] or not rows[0][0]:
            print(f"Error: node not found: {metric.class_name} {args.node_uuid}", file=sys.stderr)
            sys.exit(1)
        node = dict(rows[0][0])

    params = {}
    for raw in args.param or []:
        if "=" not in raw:
            print(f"Error: --param must be NAME=VALUE, got: {raw}", file=sys.stderr)
            sys.exit(1)
        key, value = raw.split("=", 1)
        params[key.strip()] = value

    try:
        value = resolve_metric(
            repo=repo,
            graph=graph,
            metric_name=args.name,
            node=node,
            params=params or None,
            use_cache=not args.no_cache,
        )
    except Exception as e:
        print(f"Error resolving metric: {e}", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(value, ensure_ascii=False, default=str))


def cmd_add_trigger(args: argparse.Namespace) -> None:
    """Register a class-level trigger: on create/update, run a stored workflow.

    Rejected before saving if it would close a cycle in the trigger graph.
    """
    from data_oop.exceptions import TriggerCycleError

    _, graph = get_db_connection(args)
    repo = FalkorTBoxRepository(graph)

    # --param NAME=TEMPLATE (repeatable). TEMPLATE is interpolated against the node,
    # e.g. --param order_id={uuid} --param amount={total} --param channel=naver
    parameter_map: dict[str, str] = {}
    for raw in args.param or []:
        if "=" not in raw:
            print(f"Error: --param must be NAME=TEMPLATE, got: {raw}", file=sys.stderr)
            sys.exit(1)
        key, value = raw.split("=", 1)
        parameter_map[key.strip()] = value

    print(
        f"Registering trigger '{args.name}' on {args.class_name}/{args.event} "
        f"-> workflow '{args.workflow}'..."
    )
    try:
        repo.attach_trigger_to_class(
            class_name=args.class_name,
            name=args.name,
            event=args.event,
            workflow_name=args.workflow,
            condition=args.condition,
            enabled=not args.disabled,
            order=args.order,
            description=args.description,
            parameter_map=parameter_map,
        )
    except TriggerCycleError as e:
        print(f"Error: {e}", file=sys.stderr)
        for cycle in e.cycles:
            print(f"  cycle: {' -> '.join(cycle)}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error registering trigger: {e}", file=sys.stderr)
        sys.exit(1)
    print("Trigger registered successfully.")


def cmd_list_triggers(args: argparse.Namespace) -> None:
    """List registered triggers."""
    _, graph = get_db_connection(args)
    repo = FalkorTBoxRepository(graph)

    triggers = repo.list_triggers()
    print(f"[Triggers] ({len(triggers)})")
    for t in triggers:
        state = "" if t.enabled else " [disabled]"
        cond = f" if {t.condition}" if t.condition else ""
        print(
            f"  - {t.name}: ({t.class_name}) on {t.event}{cond} -> "
            f"workflow '{t.workflow_name}' [order={t.order}]{state}"
        )
        if t.parameter_map:
            params = ", ".join(f"{k}={v}" for k, v in t.parameter_map.items())
            print(f"      params: {params}")


def cmd_delete_trigger(args: argparse.Namespace) -> None:
    """Delete a trigger by class and name."""
    _, graph = get_db_connection(args)
    repo = FalkorTBoxRepository(graph)

    print(f"Deleting trigger '{args.name}' on {args.class_name}...")
    repo.delete_trigger(args.class_name, args.name)
    print("Trigger deleted successfully.")


def cmd_validate_triggers(args: argparse.Namespace) -> None:
    """Analyse the trigger graph for cycles and divergence without saving."""
    _, graph = get_db_connection(args)
    repo = FalkorTBoxRepository(graph)

    report = repo.analyze_triggers()
    if report.valid:
        print("Trigger graph OK: no cycles.")
    else:
        print(f"Trigger graph INVALID: {len(report.cycles)} cycle(s).")
        for cycle in report.cycles:
            print(f"  cycle: {' -> '.join(cycle)}")
    if report.unbounded:
        print(f"Warning - unbounded fan-out (loop_over): {', '.join(report.unbounded)}")
    if report.unresolved:
        print(f"Warning - dynamic class (unanalyzable): {', '.join(report.unresolved)}")
    if report.missing_workflows:
        print(f"Warning - triggers referencing missing workflows: {', '.join(report.missing_workflows)}")
    if not report.valid:
        sys.exit(1)


def load_dotenv(dotenv_path: str = ".env") -> None:
    """Load variables from a .env file into os.environ if it exists."""
    if not os.path.exists(dotenv_path):
        return
    try:
        with open(dotenv_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip()
                    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                        val = val[1:-1]
                    os.environ[key] = val
    except Exception as e:
        print(f"Warning: Failed to load .env file: {e}", file=sys.stderr)


def main() -> None:
    load_dotenv()
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
    parser_inspect = subparsers.add_parser("inspect", help="List all TBox definitions, metrics, bindings, triggers and workflows")
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
    p_tbox_attach.add_argument("--nullable", choices=["true", "false"], default="true", help="Set nullable constraint (default: true)")
    p_tbox_attach.add_argument("--default", help="Default value")
    p_tbox_attach.add_argument("--metadata", help="JSON string metadata")
    p_tbox_attach.set_defaults(func=cmd_tbox_attach_property)

    # tbox-define-relationship
    p_tbox_rel = subparsers.add_parser("tbox-define-relationship", help="Define a RelationshipDef in TBox")
    p_tbox_rel.add_argument("--id", help="Unique ID of the relationship definition (auto-generated if omitted)")
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
    p_abox_node.add_argument("--uuid", help="UUID of the instance (auto-generated if omitted)")
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

    # tbox-delete-class
    p_tbox_del_cls = subparsers.add_parser("tbox-delete-class", help="Delete a ClassDef in TBox")
    p_tbox_del_cls.add_argument("--class-name", required=True, help="Name of the ClassDef to delete")
    p_tbox_del_cls.add_argument("--detach", action="store_true", help="Detach from interfaces/properties/relationships first")
    p_tbox_del_cls.set_defaults(func=cmd_tbox_delete_class)

    # tbox-delete-property
    p_tbox_del_prop = subparsers.add_parser("tbox-delete-property", help="Delete a PropertyDef in TBox")
    p_tbox_del_prop.add_argument("--name", required=True, help="Name of the PropertyDef to delete")
    p_tbox_del_prop.add_argument("--detach", action="store_true", help="Detach from classes/interfaces/relationships first")
    p_tbox_del_prop.set_defaults(func=cmd_tbox_delete_property)

    # tbox-detach-property
    p_tbox_detach = subparsers.add_parser("tbox-detach-property", help="Detach PropertyDef from ClassDef in TBox")
    p_tbox_detach.add_argument("--class-name", required=True, help="Name of the ClassDef")
    p_tbox_detach.add_argument("--property", required=True, help="Name of the PropertyDef to detach")
    p_tbox_detach.set_defaults(func=cmd_tbox_detach_property)

    # tbox-delete-relationship
    p_tbox_del_rel = subparsers.add_parser("tbox-delete-relationship", help="Delete a RelationshipDef in TBox")
    p_tbox_del_rel.add_argument("--id", required=True, help="ID of the RelationshipDef to delete")
    p_tbox_del_rel.set_defaults(func=cmd_tbox_delete_relationship)

    # define-connector
    p_def_conn = subparsers.add_parser("define-connector", help="Define an external RDB connector (env-var reference only, no secrets)")
    p_def_conn.add_argument("--name", required=True, help="Connector name")
    p_def_conn.add_argument("--kind", choices=["postgres", "mysql", "bigquery"], default="postgres", help="Connector kind (default: postgres)")
    p_def_conn.add_argument("--dsn-ref", help="Name of the env var holding the DSN (postgres/mysql)")
    p_def_conn.add_argument("--description", help="Description")
    p_def_conn.add_argument("--metadata", help="JSON metadata (e.g. bigquery {\"project\":..,\"credentials_ref\":..})")
    p_def_conn.set_defaults(func=cmd_define_connector)

    # list-connectors
    p_list_conn = subparsers.add_parser("list-connectors", help="List connectors and source bindings")
    p_list_conn.set_defaults(func=cmd_list_connectors)

    # delete-connector
    p_del_conn = subparsers.add_parser("delete-connector", help="Delete a connector")
    p_del_conn.add_argument("--name", required=True, help="Connector name")
    p_del_conn.add_argument("--detach", action="store_true", help="Drop source bindings using it first")
    p_del_conn.set_defaults(func=cmd_delete_connector)

    # bind-source
    p_bind = subparsers.add_parser("bind-source", help="Bind a class to an RDB query (aggregates/segments)")
    p_bind.add_argument("--class-name", required=True, help="Source-backed ClassDef name")
    p_bind.add_argument("--connector", required=True, help="Connector name")
    p_bind.add_argument("--sql", required=True, help="SQL text, or @path to read from a file")
    p_bind.add_argument("--key-columns", required=True, help="Comma-separated business key columns")
    p_bind.add_argument("--column-map", help="JSON mapping of sql_column -> class property")
    p_bind.add_argument("--materialization", choices=["materialized", "virtual"], default="materialized", help="Default: materialized")
    p_bind.add_argument("--refresh-interval-hours", type=int, help="Freshness hint (hours)")
    p_bind.add_argument(
        "--link",
        action="append",
        help='Edge to an existing node, repeatable. JSON: {"rel":"OF_PRODUCT","to":"Product","key":"product_id"[,"target":"product_id","dir":"out|in"]}',
    )
    p_bind.set_defaults(func=cmd_bind_source)

    # sync-source
    p_sync = subparsers.add_parser("sync-source", help="Run a class's bound query and materialize result rows as ABox nodes")
    p_sync.add_argument("--class-name", required=True, help="Source-backed ClassDef name")
    p_sync.add_argument("--no-prune", action="store_true", help="Keep previously synced nodes instead of replacing")
    p_sync.set_defaults(func=cmd_sync_source)

    # define-metric
    p_def_metric = subparsers.add_parser("define-metric", help="Attach a named parameterized RDB query to a class (resolved on demand)")
    p_def_metric.add_argument("--name", required=True, help="Metric name (unique)")
    p_def_metric.add_argument("--class-name", required=True, help="ClassDef the metric hangs off")
    p_def_metric.add_argument("--connector", required=True, help="Connector name")
    p_def_metric.add_argument("--sql", required=True, help="SQL with :name placeholders, or @path to read from a file")
    p_def_metric.add_argument("--param-map", help='JSON mapping of :placeholder -> node template, e.g. {"cid":"{customer_id}"}')
    p_def_metric.add_argument("--result-kind", choices=["scalar", "row", "rows"], default="scalar", help="Default: scalar")
    p_def_metric.add_argument("--value-column", default="value", help="Column read for scalar/row (default: value)")
    p_def_metric.add_argument("--ttl-seconds", type=int, help="Per-node cache TTL; omit for always-live")
    p_def_metric.add_argument("--description", help="Description")
    p_def_metric.set_defaults(func=cmd_define_metric)

    # list-metrics
    p_list_metric = subparsers.add_parser("list-metrics", help="List defined metrics")
    p_list_metric.add_argument("--class-name", help="Filter by class")
    p_list_metric.set_defaults(func=cmd_list_metrics)

    # delete-metric
    p_del_metric = subparsers.add_parser("delete-metric", help="Delete a metric definition by name")
    p_del_metric.add_argument("--name", required=True, help="Metric name")
    p_del_metric.set_defaults(func=cmd_delete_metric)

    # resolve-metric
    p_res_metric = subparsers.add_parser("resolve-metric", help="Resolve a metric live and print its value")
    p_res_metric.add_argument("--name", required=True, help="Metric name")
    p_res_metric.add_argument("--node-uuid", help="Anchor node uuid (its properties feed param_map templates)")
    p_res_metric.add_argument("--param", action="append", help="Explicit bind override NAME=VALUE, repeatable")
    p_res_metric.add_argument("--no-cache", action="store_true", help="Ignore the per-node TTL cache")
    p_res_metric.set_defaults(func=cmd_resolve_metric)

    # add-trigger
    p_add_trg = subparsers.add_parser("add-trigger", help="Register a class trigger: on create/update, run a workflow")
    p_add_trg.add_argument("--class-name", required=True, help="ClassDef the trigger fires on")
    p_add_trg.add_argument("--name", required=True, help="Trigger name (unique per class)")
    p_add_trg.add_argument("--event", required=True, choices=["create", "update"], help="Fire on node create or update")
    p_add_trg.add_argument("--workflow", required=True, help="Stored WorkflowDefinition to run")
    p_add_trg.add_argument("--condition", help="Node property path; fires only if non-empty")
    p_add_trg.add_argument("--order", type=int, default=0, help="Execution order among same-event triggers (default: 0)")
    p_add_trg.add_argument("--disabled", action="store_true", help="Register but do not fire")
    p_add_trg.add_argument("--description", help="Description")
    p_add_trg.add_argument(
        "--param",
        action="append",
        help="Workflow parameter binding NAME=TEMPLATE, repeatable. TEMPLATE is interpolated "
        "against the full node, e.g. --param order_id={uuid} --param channel=naver. "
        "Omit to pass the node's properties through flat.",
    )
    p_add_trg.set_defaults(func=cmd_add_trigger)

    # list-triggers
    p_list_trg = subparsers.add_parser("list-triggers", help="List registered triggers")
    p_list_trg.set_defaults(func=cmd_list_triggers)

    # delete-trigger
    p_del_trg = subparsers.add_parser("delete-trigger", help="Delete a trigger by class and name")
    p_del_trg.add_argument("--class-name", required=True, help="ClassDef the trigger is on")
    p_del_trg.add_argument("--name", required=True, help="Trigger name")
    p_del_trg.set_defaults(func=cmd_delete_trigger)

    # validate-triggers
    p_val_trg = subparsers.add_parser("validate-triggers", help="Analyse the trigger graph for cycles/divergence (no save)")
    p_val_trg.set_defaults(func=cmd_validate_triggers)

    # db-dump
    p_db_dump = subparsers.add_parser("db-dump", help="Dump FalkorDB graph data to a file (graph specified by global --graph option)")
    p_db_dump.add_argument("-f", "--file", required=True, help="Path to output dump file")
    p_db_dump.set_defaults(func=cmd_db_dump)

    # db-restore
    p_db_restore = subparsers.add_parser("db-restore", help="Restore FalkorDB graph data from a dump file (graph specified by global --graph option)")
    p_db_restore.add_argument("-f", "--file", required=True, help="Path to input dump file")
    p_db_restore.set_defaults(func=cmd_db_restore)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()
