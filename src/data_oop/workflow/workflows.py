from __future__ import annotations

import json
import math
import re
import uuid
from datetime import date, datetime
from typing import Any
from urllib.parse import urlparse

from data_oop.falkor.graph import FalkorGraph
from data_oop.falkor.abox import (
    ABoxNodeResult,
    _safe_identifier,
    upsert_abox_node,
    upsert_abox_relationship,
)
from data_oop.schema.models import WorkflowDef, WorkflowStepDef, WorkflowParameterDef


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE_RE = re.compile(r"^\+?[0-9][0-9\-\s().]{6,}$")
_TRUE_VALUES = {"true", "1", "yes", "y", "on"}
_FALSE_VALUES = {"false", "0", "no", "n", "off"}


def validate_workflow_parameter_values(
    parameter_defs: list[WorkflowParameterDef] | tuple[WorkflowParameterDef, ...],
    values: dict[str, Any],
) -> dict[str, Any]:
    """Validate and normalize runtime workflow parameter values against definitions."""
    normalized: dict[str, Any] = {}
    for param in parameter_defs:
        raw = values.get(param.name)
        missing = raw is None or raw == "" or raw == []
        if missing:
            if param.required:
                raise ValueError(f"Missing required workflow parameter: {param.name}")
            continue
        normalized[param.name] = _validate_parameter_value(param, raw)

    # Preserve extra values for backwards compatibility with older/implicit workflows.
    for name, value in values.items():
        if name not in normalized and name not in {p.name for p in parameter_defs}:
            normalized[name] = value
    return normalized


def _validate_parameter_value(param: WorkflowParameterDef, value: Any) -> Any:
    t = param.type
    if t == "string":
        return str(value)
    if t == "integer":
        return _validate_integer(param.name, value)
    if t == "float":
        return _validate_float(param.name, value)
    if t == "boolean":
        return _validate_boolean(param.name, value)
    if t == "date":
        return _validate_date(param.name, value)
    if t == "datetime":
        return _validate_datetime(param.name, value)
    if t == "email":
        return _validate_email(param.name, value)
    if t == "url":
        return _validate_url(param.name, value)
    if t == "phone":
        return _validate_phone(param.name, value)
    if t == "uuid":
        return _validate_uuid(param.name, value)
    if t == "array":
        return _validate_array(param, value)
    raise ValueError(f"Unsupported workflow parameter type for {param.name}: {t}")


def _validate_integer(name: str, value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError(f"Workflow parameter {name} must be integer")
    if isinstance(value, int):
        return value
    if isinstance(value, str) and re.fullmatch(r"[-+]?\d+", value.strip()):
        return int(value)
    raise ValueError(f"Workflow parameter {name} must be integer")


def _validate_float(name: str, value: Any) -> float:
    if isinstance(value, bool):
        raise ValueError(f"Workflow parameter {name} must be float")
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"Workflow parameter {name} must be float") from None
    if not math.isfinite(parsed):
        raise ValueError(f"Workflow parameter {name} must be finite float")
    return parsed


def _validate_boolean(name: str, value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in _TRUE_VALUES:
            return True
        if lowered in _FALSE_VALUES:
            return False
    raise ValueError(f"Workflow parameter {name} must be boolean")


def _validate_date(name: str, value: Any) -> str:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip()).isoformat()
        except ValueError:
            pass
    raise ValueError(f"Workflow parameter {name} must be ISO date (YYYY-MM-DD)")


def _validate_datetime(name: str, value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, str):
        raw = value.strip()
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).isoformat()
        except ValueError:
            pass
    raise ValueError(f"Workflow parameter {name} must be ISO datetime")


def _validate_email(name: str, value: Any) -> str:
    if isinstance(value, str) and _EMAIL_RE.fullmatch(value.strip()):
        return value.strip()
    raise ValueError(f"Workflow parameter {name} must be email")


def _validate_url(name: str, value: Any) -> str:
    if isinstance(value, str):
        raw = value.strip()
        parsed = urlparse(raw)
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            return raw
    raise ValueError(f"Workflow parameter {name} must be URL")


def _validate_phone(name: str, value: Any) -> str:
    if isinstance(value, str) and _PHONE_RE.fullmatch(value.strip()):
        return value.strip()
    raise ValueError(f"Workflow parameter {name} must be phone")


def _validate_uuid(name: str, value: Any) -> str:
    try:
        return str(uuid.UUID(str(value)))
    except (TypeError, ValueError, AttributeError):
        raise ValueError(f"Workflow parameter {name} must be UUID") from None


def _validate_array(param: WorkflowParameterDef, value: Any) -> list[Any]:
    raw = value
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            raise ValueError(f"Workflow parameter {param.name} must be array") from None
    if not isinstance(raw, list):
        raise ValueError(f"Workflow parameter {param.name} must be array")
    if not param.array_item_type:
        return raw

    item_param = WorkflowParameterDef(name=f"{param.name}[]", type=param.array_item_type)  # type: ignore[arg-type]
    return [_validate_parameter_value(item_param, item) for item in raw]


def _workflow_parameter_defs_from_raw(raw_parameters: list[dict[str, Any]]) -> list[WorkflowParameterDef]:
    return [
        WorkflowParameterDef(
            name=p["name"],
            type=p["type"],
            array_item_type=p.get("array_item_type"),
            array_item_class=p.get("array_item_class"),
            required=p.get("required", True),
            description=p.get("description"),
        )
        for p in raw_parameters
    ]


def validate_workflow(workflow: WorkflowDef) -> None:
    """Validate workflow definition structure, action fields, and variable references."""
    # 1. Check step_ids are unique
    step_ids = set()
    for step in workflow.steps:
        if not step.step_id:
            raise ValueError("Workflow step must have a step_id")
        if step.step_id in step_ids:
            raise ValueError(f"Duplicate step_id found: {step.step_id}")
        step_ids.add(step.step_id)

    # 2. Check actions and required fields
    for step in workflow.steps:
        if step.action not in ("create_node", "create_relationship", "run_workflow", "fetch_view"):
            raise ValueError(f"Unsupported action: {step.action} in step {step.step_id}")

        if step.action == "create_node":
            if not step.class_name:
                raise ValueError(f"Step {step.step_id} (create_node) is missing class_name")
        elif step.action == "create_relationship":
            if not all([step.from_class, step.from_uuid, step.relationship_name, step.to_class, step.to_uuid]):
                raise ValueError(
                    f"Step {step.step_id} (create_relationship) is missing one of: "
                    "from_class, from_uuid, relationship_name, to_class, to_uuid"
                )
        elif step.action == "run_workflow":
            if not step.workflow_name:
                raise ValueError(f"Step {step.step_id} (run_workflow) is missing workflow_name")
        elif step.action == "fetch_view":
            if not step.view_name:
                raise ValueError(f"Step {step.step_id} (fetch_view) is missing view_name")

    # 3. Check variable interpolations
    # Collect all valid parameter names
    param_names = {p.name for p in workflow.parameters}
    
    # Track steps processed so far
    processed_steps = set()
    
    for step in workflow.steps:
        # Collect all string values in step properties/parameters to check for interpolations
        strings_to_check = []
        
        # Helper to collect strings recursively
        def collect_strings(val: Any):
            if isinstance(val, str):
                strings_to_check.append(val)
            elif isinstance(val, dict):
                for v in val.values():
                    collect_strings(v)
            elif isinstance(val, list):
                for v in val:
                    collect_strings(v)

        collect_strings(step.properties)
        collect_strings(step.parameters)
        if step.uuid:
            strings_to_check.append(step.uuid)
        if step.from_uuid:
            strings_to_check.append(step.from_uuid)
        if step.to_uuid:
            strings_to_check.append(step.to_uuid)
            
        if step.if_present:
            strings_to_check.append(f"{{{step.if_present}}}")
        if step.loop_over:
            strings_to_check.append(f"{{{step.loop_over}}}")

        # Search for {variable_name} pattern
        for s in strings_to_check:
            matches = re.findall(r"\{([^}]+)\}", s)
            for path in matches:
                root_key = path.split(".")[0]
                is_valid = (
                    root_key in param_names
                    or root_key in processed_steps
                    or (step.loop_over and root_key == (step.loop_var or "item"))
                )
                if not is_valid:
                    raise ValueError(
                        f"Step {step.step_id} references undefined variable: '{root_key}' in '{s}'"
                    )
                    
        processed_steps.add(step.step_id)


def extract_parameters_from_steps(
    steps: list[dict[str, Any]] | list[WorkflowStepDef] | tuple[WorkflowStepDef, ...]
) -> list[dict[str, Any]]:
    """Inspect workflow steps and extract referenced variables as workflow parameters."""
    raw_steps = []
    for step in steps:
        if isinstance(step, WorkflowStepDef):
            from dataclasses import asdict
            raw_steps.append(asdict(step))
        else:
            raw_steps.append(step)
            
    step_ids = set()
    extracted_names = set()
    
    for step in raw_steps:
        step_id = step.get("step_id")
        loop_over = step.get("loop_over")
        loop_var = step.get("loop_var") or "item"
        
        strings_to_check = []
        
        def collect_strings(val: Any):
            if isinstance(val, str):
                strings_to_check.append(val)
            elif isinstance(val, dict):
                for v in val.values():
                    collect_strings(v)
            elif isinstance(val, list):
                for v in val:
                    collect_strings(v)

        collect_strings(step.get("properties", {}))
        collect_strings(step.get("parameters", {}))
        if step.get("uuid"):
            strings_to_check.append(step["uuid"])
        if step.get("from_uuid"):
            strings_to_check.append(step["from_uuid"])
        if step.get("to_uuid"):
            strings_to_check.append(step["to_uuid"])
        if step.get("if_present"):
            strings_to_check.append(f"{{{step['if_present']}}}")
            
        for s in strings_to_check:
            matches = re.findall(r"\{([^}]+)\}", s)
            for path in matches:
                root_key = path.split(".")[0]
                if root_key not in step_ids and (not loop_over or root_key != loop_var):
                    extracted_names.add(root_key)
                    
        if loop_over:
            clean_loop_over = loop_over.strip("{} ")
            root_key = clean_loop_over.split(".")[0]
            if root_key not in step_ids:
                extracted_names.add(root_key)
                    
        if step_id:
            step_ids.add(step_id)
            
    params = []
    for name in sorted(extracted_names):
        is_array = False
        is_optional = False
        for step in raw_steps:
            if step.get("loop_over") == name or step.get("loop_over") == f"{name}.results":
                is_array = True
            if step.get("if_present") == name:
                is_optional = True
        params.append({
            "name": name,
            "type": "array" if is_array else "string",
            "required": not is_optional,
            "description": f"Auto-extracted parameter {name}"
        })
    return params


def generate_workflow_dsl(workflow: WorkflowDef) -> str:
    """Generate executable Python DSL code for the workflow definition using WorkflowBuilder."""
    code_str = (
        "from data_oop import WorkflowBuilder, save_workflow, run_workflow\n"
        "from falkordb import FalkorDB\n\n"
        "# 1. Connect to FalkorDB\n"
        "db = FalkorDB(host=\"localhost\", port=6380)\n"
        "graph = db.select_graph(\"data_oop\")\n\n"
        "# 2. Define Workflow using Fluent Builder\n"
        f"workflow = (\n    WorkflowBuilder(\"{workflow.name}\""
    )

    if workflow.description:
        desc_escaped = workflow.description.replace('"', '\\"')
        code_str += f", description=\"{desc_escaped}\""
    code_str += ")\n"

    # Add parameters
    for p in workflow.parameters:
        code_str += f"    .parameter(\n        name=\"{p.name}\",\n        type=\"{p.type}\""
        if p.array_item_type:
            code_str += f",\n        array_item_type=\"{p.array_item_type}\""
        if p.array_item_class:
            code_str += f",\n        array_item_class=\"{p.array_item_class}\""
        if not p.required:
            code_str += ",\n        required=False"
        if p.description:
            desc_escaped = p.description.replace('"', '\\"')
            code_str += f",\n        description=\"{desc_escaped}\""
        code_str += "\n    )\n"

    # Add steps
    for step in workflow.steps:
        if step.action == "create_node":
            code_str += (
                "    .create_node(\n"
                f"        step_id=\"{step.step_id}\",\n"
                f"        class_name=\"{step.class_name}\""
            )
            if step.properties:
                code_str += ",\n        properties={\n"
                for k, v in step.properties.items():
                    val_escaped = str(v).replace('"', '\\"')
                    code_str += f"            \"{k}\": \"{val_escaped}\",\n"
                code_str += "        }"
            if step.uuid:
                code_str += f",\n        uuid=\"{step.uuid}\""

        elif step.action == "create_relationship":
            code_str += (
                "    .create_relationship(\n"
                f"        step_id=\"{step.step_id}\",\n"
                f"        relationship_name=\"{step.relationship_name}\",\n"
                f"        from_class=\"{step.from_class}\",\n"
                f"        from_uuid=\"{step.from_uuid}\",\n"
                f"        to_class=\"{step.to_class}\",\n"
                f"        to_uuid=\"{step.to_uuid}\""
            )
            if step.properties:
                code_str += ",\n        properties={\n"
                for k, v in step.properties.items():
                    val_escaped = str(v).replace('"', '\\"')
                    code_str += f"            \"{k}\": \"{val_escaped}\",\n"
                code_str += "        }"

        elif step.action == "run_workflow":
            code_str += (
                "    .run_workflow(\n"
                f"        step_id=\"{step.step_id}\",\n"
                f"        workflow_name=\"{step.workflow_name}\""
            )
            if step.parameters:
                code_str += ",\n        parameters={\n"
                for k, v in step.parameters.items():
                    val_escaped = str(v).replace('"', '\\"')
                    code_str += f"            \"{k}\": \"{val_escaped}\",\n"
                code_str += "        }"

        if step.if_present:
            code_str += f",\n        if_present=\"{step.if_present}\""
        if step.loop_over:
            code_str += f",\n        loop_over=\"{step.loop_over}\""
            if step.loop_var:
                code_str += f",\n        loop_var=\"{step.loop_var}\""
        code_str += "\n    )\n"

    code_str += (
        ")\n\n"
        "# 3. Save Workflow to DB\n"
        "save_workflow(\n"
        "    graph=graph,\n"
        "    name=workflow.name,\n"
        "    steps=workflow.steps,\n"
        "    parameters=workflow.parameters,\n"
        "    description=workflow.description\n"
        ")\n\n"
        "# 4. Execute Workflow\n"
        "results = run_workflow(\n"
        "    graph=graph,\n"
        "    name=workflow.name,\n"
        "    parameters={\n"
    )

    for p in workflow.parameters:
        if p.type == "array":
            code_str += f"        \"{p.name}\": [],  # list of {p.array_item_type or 'items'}\n"
        else:
            code_str += f"        \"{p.name}\": \"YOUR_{p.name.upper()}_VALUE\",\n"

    code_str += (
        "    }\n"
        ")\n"
        "print(\"Execution Results:\", results)\n"
    )
    return code_str


def save_workflow(
    *,
    graph: FalkorGraph,
    name: str,
    steps: list[dict[str, Any]] | list[WorkflowStepDef] | tuple[WorkflowStepDef, ...],
    parameters: list[dict[str, Any]] | list[WorkflowParameterDef] | tuple[WorkflowParameterDef, ...] | None = None,
    description: str | None = None,
) -> ABoxNodeResult:
    """Save the workflow steps as an ABox node in FalkorDB.

    This enables workflows to be fully defined and stored inside FalkorDB as data.
    """
    step_defs = []
    for step in steps:
        if isinstance(step, dict):
            step_defs.append(WorkflowStepDef(
                step_id=step["step_id"],
                action=step["action"],
                class_name=step.get("class_name"),
                properties=step.get("properties") or {},
                uuid=step.get("uuid"),
                from_class=step.get("from_class"),
                from_uuid=step.get("from_uuid"),
                relationship_name=step.get("relationship_name"),
                to_class=step.get("to_class"),
                to_uuid=step.get("to_uuid"),
                if_present=step.get("if_present"),
                loop_over=step.get("loop_over"),
                loop_var=step.get("loop_var"),
                workflow_name=step.get("workflow_name"),
                view_name=step.get("view_name"),
                parameters=step.get("parameters") or {},
            ))
        else:
            step_defs.append(step)

    if parameters is None:
        extracted = extract_parameters_from_steps(step_defs)
        param_defs = [
            WorkflowParameterDef(
                name=p["name"],
                type=p["type"],
                required=p["required"],
                description=p["description"]
            )
            for p in extracted
        ]
    else:
        param_defs = []
        for p in parameters:
            if isinstance(p, dict):
                param_defs.append(WorkflowParameterDef(
                    name=p["name"],
                    type=p["type"],
                    array_item_type=p.get("array_item_type"),
                    array_item_class=p.get("array_item_class"),
                    required=p.get("required", True),
                    description=p.get("description"),
                ))
            else:
                param_defs.append(p)

    workflow = WorkflowDef(
        name=name,
        steps=tuple(step_defs),
        parameters=tuple(param_defs),
        description=description,
    )

    validate_workflow(workflow)

    # 2. Save/Upsert Workflow ABox Node
    workflow_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"workflow:{name}"))
    
    # Serialize steps and parameters as standard lists of dicts
    from dataclasses import asdict
    serialized_steps = [asdict(s) for s in workflow.steps]
    serialized_params = [asdict(p) for p in workflow.parameters]
    
    steps_str = json.dumps(serialized_steps, ensure_ascii=False)
    params_str = json.dumps(serialized_params, ensure_ascii=False)
    
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
    _depth: int = 0,
) -> dict[str, Any]:
    """Retrieve a WorkflowDefinition from FalkorDB by name, and execute its steps dynamically.

    ``_depth`` tracks how deep this run sits in a trigger -> workflow -> trigger
    chain. It is threaded into the node upserts so that triggers those upserts
    fire are bounded by ``MAX_TRIGGER_DEPTH``.

    Variable references in steps (e.g. "{event_name}" or "{create_event.uuid}") are resolved
    in real-time against the parameters and previously executed steps.

    Returns the execution context summarizing generated node UUIDs.
    """
    # 1. Retrieve the workflow definition from ABox
    rows = graph.query(
        "MATCH (w:WorkflowDefinition {name: $name}) RETURN w.steps_json, w.parameters_json",
        {"name": name}
    ).result_set

    if not rows or not rows[0]:
        raise ValueError(f"WorkflowDefinition not found: {name}")

    steps_str = rows[0][0]
    steps: list[dict[str, Any]] = json.loads(steps_str)
    try:
        raw_parameter_defs = json.loads(rows[0][1]) if len(rows[0]) > 1 and rows[0][1] else []
    except Exception:
        raw_parameter_defs = []
    if not raw_parameter_defs:
        raw_parameter_defs = extract_parameters_from_steps(steps)
    parameter_defs = _workflow_parameter_defs_from_raw(raw_parameter_defs)
    normalized_parameters = validate_workflow_parameter_values(parameter_defs, parameters)

    # 2. Setup context for variable interpolation
    # Context contains validated parameters and results of executed steps
    context = dict(normalized_parameters)

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
                    
                    # Execute node creation. Pass the current depth so any
                    # triggers this node fires stay within MAX_TRIGGER_DEPTH.
                    upsert_abox_node(
                        graph=graph,
                        class_name=class_name,
                        uuid=node_uuid,
                        properties=properties,
                        _depth=_depth,
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
                    # Call run_workflow recursively, carrying the depth forward.
                    sub_results = run_workflow(
                        graph=graph,
                        name=sub_wf_name,
                        parameters=sub_params,
                        _depth=_depth,
                    )
                    
                    rollback_stack.append({
                        "type": "sub_workflow",
                        "results": sub_results
                    })

                    return sub_results
                elif action == "fetch_view":
                    # Read-only: resolve a stored view live and hand its rows to later
                    # steps as {step_id: {"value": [...]}}. No graph mutation, so nothing
                    # is pushed onto the rollback stack. The step's interpolated
                    # ``parameters`` (already resolved against the node context above)
                    # become the view's filters.
                    from data_oop.falkor.repository import FalkorTBoxRepository
                    from data_oop.rdb.views import resolve_view

                    view_name = interpolated.get("view_name")
                    if not view_name:
                        raise ValueError(f"Missing view_name for fetch_view step: {step_id}")
                    view_filters = interpolated.get("parameters", {}) or {}
                    value = resolve_view(
                        repo=FalkorTBoxRepository(graph),
                        graph=graph,
                        view_name=view_name,
                        filters=view_filters,
                    )
                    return {"value": value}
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
        rel_name = _safe_identifier(item.get("relationship_name"), "relationship")
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
        rel_name = _safe_identifier(step_res["relationship_name"], "relationship")
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


class WorkflowBuilder:
    """Fluent Builder for creating a WorkflowDef."""

    def __init__(self, name: str, description: str | None = None) -> None:
        self.name = name
        self.description = description
        self.steps: list[WorkflowStepDef] = []
        self.parameters: list[WorkflowParameterDef] = []

    def parameter(
        self,
        name: str,
        type: str,
        array_item_type: str | None = None,
        array_item_class: str | None = None,
        required: bool = True,
        description: str | None = None,
    ) -> WorkflowBuilder:
        self.parameters.append(WorkflowParameterDef(
            name=name,
            type=type,
            array_item_type=array_item_type,
            array_item_class=array_item_class,
            required=required,
            description=description,
        ))
        return self

    def create_node(
        self,
        step_id: str,
        class_name: str,
        properties: dict[str, Any] | None = None,
        uuid: str | None = None,
        if_present: str | None = None,
        loop_over: str | None = None,
        loop_var: str | None = None,
    ) -> WorkflowBuilder:
        self.steps.append(WorkflowStepDef(
            step_id=step_id,
            action="create_node",
            class_name=class_name,
            properties=properties or {},
            uuid=uuid,
            if_present=if_present,
            loop_over=loop_over,
            loop_var=loop_var,
        ))
        return self

    def create_relationship(
        self,
        step_id: str,
        relationship_name: str,
        from_class: str,
        from_uuid: str,
        to_class: str,
        to_uuid: str,
        properties: dict[str, Any] | None = None,
        if_present: str | None = None,
        loop_over: str | None = None,
        loop_var: str | None = None,
    ) -> WorkflowBuilder:
        self.steps.append(WorkflowStepDef(
            step_id=step_id,
            action="create_relationship",
            from_class=from_class,
            from_uuid=from_uuid,
            relationship_name=relationship_name,
            to_class=to_class,
            to_uuid=to_uuid,
            properties=properties or {},
            if_present=if_present,
            loop_over=loop_over,
            loop_var=loop_var,
        ))
        return self

    def run_workflow(
        self,
        step_id: str,
        workflow_name: str,
        parameters: dict[str, Any] | None = None,
        if_present: str | None = None,
        loop_over: str | None = None,
        loop_var: str | None = None,
    ) -> WorkflowBuilder:
        self.steps.append(WorkflowStepDef(
            step_id=step_id,
            action="run_workflow",
            workflow_name=workflow_name,
            parameters=parameters or {},
            if_present=if_present,
            loop_over=loop_over,
            loop_var=loop_var,
        ))
        return self

    def loop_over(self, loop_over: str, loop_var: str = "item") -> WorkflowBuilder:
        """Add loop property to the last added step."""
        if not self.steps:
            raise ValueError("No steps defined to loop over")
        last_step = self.steps[-1]
        from dataclasses import replace
        self.steps[-1] = replace(last_step, loop_over=loop_over, loop_var=loop_var)
        return self

    def build(self) -> WorkflowDef:
        wf = WorkflowDef(
            name=self.name,
            steps=tuple(self.steps),
            parameters=tuple(self.parameters),
            description=self.description,
        )
        validate_workflow(wf)
        return wf
