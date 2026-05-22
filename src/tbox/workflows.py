from __future__ import annotations

import json
import re
import uuid
from typing import Any

from .falkor import FalkorGraph
from .falkor_abox import ABoxNodeResult, upsert_abox_node, upsert_abox_relationship
from .falkor_repository import FalkorTBoxRepository


def save_workflow(
    *,
    graph: FalkorGraph,
    name: str,
    steps: list[dict[str, Any]],
    description: str | None = None,
) -> ABoxNodeResult:
    """Register a WorkflowDefinition in the TBox (if missing) and save the workflow steps as an ABox node.

    This enables workflows to be fully defined and stored inside FalkorDB as data.
    """
    # 1. Ensure WorkflowDefinition exists in TBox
    tbox_repo = FalkorTBoxRepository(graph)
    if not tbox_repo.get_class("WorkflowDefinition"):
        # Define TBox metadata for WorkflowDefinition
        tbox_repo.create_class(
            "WorkflowDefinition",
            label="WorkflowDefinition",
            description="A dynamically defined low-code/no-code workflow definition",
        )
        tbox_repo.create_property("name", datatype="string", description="Name of the workflow")
        tbox_repo.create_property("steps_json", datatype="string", description="JSON serialized steps of the workflow")
        tbox_repo.create_property("description", datatype="string", description="Optional description")
        
        tbox_repo.attach_property_to_class(
            class_name="WorkflowDefinition",
            property_name="name",
            required=True,
            unique=True,
        )
        tbox_repo.attach_property_to_class(
            class_name="WorkflowDefinition",
            property_name="steps_json",
            required=True,
        )
        tbox_repo.attach_property_to_class(
            class_name="WorkflowDefinition",
            property_name="description",
            required=False,
        )

    # 2. Save/Upsert Workflow ABox Node
    workflow_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"workflow:{name}"))
    steps_str = json.dumps(steps, ensure_ascii=False)
    
    return upsert_abox_node(
        graph=graph,
        class_name="WorkflowDefinition",
        uuid=workflow_uuid,
        properties={
            "name": name,
            "steps_json": steps_str,
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
    context = dict(parameters)

    # 3. Execute steps sequentially
    for step in steps:
        step_id = step.get("step_id")
        action = step.get("action")
        if not step_id or not action:
            raise ValueError(f"Invalid step configuration: {step}")

        # Interpolate variables in step parameters
        interpolated_step = _interpolate(step, context)

        if action == "create_node":
            class_name = interpolated_step.get("class_name")
            properties = interpolated_step.get("properties", {})
            node_uuid = interpolated_step.get("uuid") or str(uuid.uuid4())
            
            # Execute node creation
            upsert_abox_node(
                graph=graph,
                class_name=class_name,
                uuid=node_uuid,
                properties=properties,
            )
            
            # Save step results to context so subsequent steps can refer to them
            # E.g. { "create_event": { "uuid": "xxx", "name": "yyy" } }
            context[step_id] = {
                "uuid": node_uuid,
                **properties
            }

        elif action == "create_relationship":
            from_class = interpolated_step.get("from_class")
            from_uuid = interpolated_step.get("from_uuid")
            relationship_name = interpolated_step.get("relationship_name")
            to_class = interpolated_step.get("to_class")
            to_uuid = interpolated_step.get("to_uuid")
            properties = interpolated_step.get("properties", {})

            if not all([from_class, from_uuid, relationship_name, to_class, to_uuid]):
                raise ValueError(f"Missing required parameters for relationship step: {step_id}")

            # Execute relationship creation
            upsert_abox_relationship(
                graph=graph,
                from_class=from_class,
                from_uuid=from_uuid,
                relationship_name=relationship_name,
                to_class=to_class,
                to_uuid=to_uuid,
                properties=properties,
            )

        else:
            raise ValueError(f"Unsupported workflow action: {action}")

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
