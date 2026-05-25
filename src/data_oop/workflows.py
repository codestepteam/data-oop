from __future__ import annotations

import json
import re
import uuid
from typing import Any

from .falkor import FalkorGraph
from .falkor_abox import ABoxNodeResult, upsert_abox_node, upsert_abox_relationship


def save_workflow(
    *,
    graph: FalkorGraph,
    name: str,
    steps: list[dict[str, Any]],
    parameters: list[dict[str, Any]] | None = None,
    description: str | None = None,
) -> ABoxNodeResult:
    """Save the workflow steps as an ABox node in FalkorDB.

    This enables workflows to be fully defined and stored inside FalkorDB as data.
    """
    # 2. Save/Upsert Workflow ABox Node
    workflow_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"workflow:{name}"))
    steps_str = json.dumps(steps, ensure_ascii=False)
    params_str = json.dumps(parameters or [], ensure_ascii=False)
    
    return upsert_abox_node(
        graph=graph,
        class_name="WorkflowDefinition",
        uuid=workflow_uuid,
        properties={
            "name": name,
            "steps_json": steps_str,
            "parameters_json": params_str,
            "description": description,
        },
    )


def run_workflow(
    *,
    graph: FalkorGraph,
    name: str,
    parameters: dict[str, Any],
) -> dict[str, Any]:
    """Retrieve a WorkflowDefinition from FalkorDB by name, and execute its steps dynamically.

    Variable references in steps (e.g. "{event_name}" or "{create_event.uuid}") are resolved
    in real-time against the parameters and previously executed steps.

    Returns the execution context summarizing generated node UUIDs.
    """
    # 1. Retrieve the workflow definition from ABox
    rows = graph.query(
        "MATCH (w:WorkflowDefinition {name: $name}) RETURN w.steps_json",
        {"name": name}
    ).result_set

    if not rows or not rows[0]:
        raise ValueError(f"WorkflowDefinition not found: {name}")

    steps_str = rows[0][0]
    steps: list[dict[str, Any]] = json.loads(steps_str)

    # 2. Setup context for variable interpolation
    # Context contains parameters and results of executed steps
    context = {}
    for k, v in parameters.items():
        if isinstance(v, str) and v.strip().startswith("[") and v.strip().endswith("]"):
            try:
                v = json.loads(v)
            except Exception:
                pass
        context[k] = v

    rollback_stack = []

    try:
        # 3. Execute steps sequentially
        for step in steps:
            step_id = step.get("step_id")
            action = step.get("action")
            if not step_id or not action:
                raise ValueError(f"Invalid step configuration: {step}")

            # 3.1. Condition Check (if_present)
            if_present_var = step.get("if_present")
            if if_present_var:
                val = _resolve_path(if_present_var, context)
                if val is None or val == "" or val == []:
                    # Skip this step since the optional variable is missing or empty
                    continue

            # Helper to execute a single step action with a given interpolated state
            def _exec_single_action(interpolated: dict[str, Any]) -> Any:
                if action == "create_node":
                    class_name = interpolated.get("class_name")
                    properties = interpolated.get("properties", {})
                    node_uuid = interpolated.get("uuid") or str(uuid.uuid4())
                    
                    # Execute node creation
                    upsert_abox_node(
                        graph=graph,
                        class_name=class_name,
                        uuid=node_uuid,
                        properties=properties,
                    )
                    
                    rollback_stack.append({
                        "type": "delete_node",
                        "uuid": node_uuid,
                        "class_name": class_name
                    })
                    
                    return {
                        "uuid": node_uuid,
                        **properties
                    }

                elif action == "create_relationship":
                    from_class = interpolated.get("from_class")
                    from_uuid = interpolated.get("from_uuid")
                    relationship_name = interpolated.get("relationship_name")
                    to_class = interpolated.get("to_class")
                    to_uuid = interpolated_step.get("to_uuid") if (to_uuid := interpolated.get("to_uuid")) is None else to_uuid
                    # Ensure we get interpolated fields correctly
                    to_uuid_val = interpolated.get("to_uuid")
                    properties = interpolated.get("properties", {})

                    if not all([from_class, from_uuid, relationship_name, to_class, to_uuid_val]):
                        raise ValueError(f"Missing required parameters for relationship step: {step_id}")

                    # Execute relationship creation
                    upsert_abox_relationship(
                        graph=graph,
                        from_class=from_class,
                        from_uuid=from_uuid,
                        relationship_name=relationship_name,
                        to_class=to_class,
                        to_uuid=to_uuid_val,
                        properties=properties,
                    )
                    
                    rollback_stack.append({
                        "type": "delete_relationship",
                        "from_uuid": from_uuid,
                        "to_uuid": to_uuid_val,
                        "relationship_name": relationship_name
                    })
                    
                    return {
                        "relationship_name": relationship_name,
                        "from_uuid": from_uuid,
                        "to_uuid": to_uuid_val
                    }
                elif action == "run_workflow":
                    sub_wf_name = interpolated.get("workflow_name")
                    sub_params = interpolated.get("parameters", {})
                    if not sub_wf_name:
                        raise ValueError("Missing workflow_name for run_workflow step")
                    # Call run_workflow recursively
                    sub_results = run_workflow(
                        graph=graph,
                        name=sub_wf_name,
                        parameters=sub_params,
                    )
                    
                    rollback_stack.append({
                        "type": "sub_workflow",
                        "results": sub_results
                    })
                    
                    return sub_results
                else:
                    raise ValueError(f"Unsupported workflow action: {action}")

            # 3.2. Loop Check (loop_over)
            loop_over_var = step.get("loop_over")
            if loop_over_var:
                loop_items = _resolve_path(loop_over_var, context)
                loop_var = step.get("loop_var") or "item"

                # Normalize loop items
                if loop_items is None:
                    loop_items = []
                elif not isinstance(loop_items, list):
                    loop_items = [loop_items]

                step_results = []
                for item in loop_items:
                    # Merge loop item value into temporary context
                    sub_context = {**context, loop_var: item}
                    interpolated_step = _interpolate(step, sub_context)
                    res = _exec_single_action(interpolated_step)
                    step_results.append(res)
                
                # Save results array to context
                context[step_id] = step_results
            else:
                # Normal execution
                interpolated_step = _interpolate(step, context)
                res = _exec_single_action(interpolated_step)
                context[step_id] = res

    except Exception as e:
        # Roll back LIFO
        for rollback_item in reversed(rollback_stack):
            try:
                _execute_rollback_item(graph, rollback_item)
            except Exception as roll_err:
                print(f"Error during rollback: {roll_err}")
        raise e

    # Return only the execution results (exclude input parameters)
    results = {
        key: val for key, val in context.items()
        if key not in parameters
    }
    return results


# ------------------------------------------------------------------
# Internal variable interpolation helpers
# ------------------------------------------------------------------
def _interpolate(val: Any, context: dict[str, Any]) -> Any:
    if isinstance(val, str):
        # Complete substitution (e.g. "{create_event.uuid}")
        match = re.match(r"^\{([^}]+)\}$", val)
        if match:
            path = match.group(1)
            return _resolve_path(path, context)
            
        # Inline string substitution (e.g. "Event: {event_name}")
        def repl(m: re.Match) -> str:
            path = m.group(1)
            res = _resolve_path(path, context)
            return str(res) if res is not None else ""
        return re.sub(r"\{([^}]+)\}", repl, val)
        
    elif isinstance(val, dict):
        return {k: _interpolate(v, context) for k, v in val.items()}
    elif isinstance(val, list):
        return [_interpolate(x, context) for x in val]
    return val


def _resolve_path(path: str, context: dict[str, Any]) -> Any:
    parts = path.split(".")
    curr: Any = context
    for part in parts:
        if isinstance(curr, dict) and part in curr:
            curr = curr[part]
        else:
            return None
    return curr


def _execute_rollback_item(graph: FalkorGraph, item: dict[str, Any]) -> None:
    t = item.get("type")
    if t == "delete_node":
        uuid_val = item.get("uuid")
        graph.query("MATCH (n {uuid: $uuid}) DETACH DELETE n", {"uuid": uuid_val})
        
    elif t == "delete_relationship":
        from_uuid = item.get("from_uuid")
        to_uuid = item.get("to_uuid")
        rel_name = item.get("relationship_name")
        graph.query(
            f"MATCH (a {{uuid: $from_uuid}})-[r:{rel_name}]->(b {{uuid: $to_uuid}}) DELETE r",
            {"from_uuid": from_uuid, "to_uuid": to_uuid}
        )
        
    elif t == "sub_workflow":
        sub_res = item.get("results", {})
        _rollback_workflow_results(graph, sub_res)


def _rollback_workflow_results(graph: FalkorGraph, results: dict[str, Any]) -> None:
    for _, step_res in reversed(list(results.items())):
        if not step_res:
            continue
        
        if isinstance(step_res, list):
            for item in reversed(step_res):
                _rollback_single_step_result(graph, item)
        else:
            _rollback_single_step_result(graph, step_res)


def _rollback_single_step_result(graph: FalkorGraph, step_res: Any) -> None:
    if not isinstance(step_res, dict):
        return
    
    if "relationship_name" in step_res and "from_uuid" in step_res and "to_uuid" in step_res:
        rel_name = step_res["relationship_name"]
        from_uuid = step_res["from_uuid"]
        to_uuid = step_res["to_uuid"]
        graph.query(
            f"MATCH (a {{uuid: $from_uuid}})-[r:{rel_name}]->(b {{uuid: $to_uuid}}) DELETE r",
            {"from_uuid": from_uuid, "to_uuid": to_uuid}
        )
    elif "uuid" in step_res:
        node_uuid = step_res["uuid"]
        graph.query("MATCH (n {uuid: $uuid}) DETACH DELETE n", {"uuid": node_uuid})
    else:
        _rollback_workflow_results(graph, step_res)
