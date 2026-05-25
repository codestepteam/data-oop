from __future__ import annotations

import os
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from falkordb import FalkorDB

from data_oop.falkor_repository import FalkorTBoxRepository
from data_oop.workflows import save_workflow, run_workflow
from data_oop.falkor_validation import run_latest_falkor_abox_validation


app = FastAPI(title="Data OOP TBox & Workflow API")

# Enable CORS for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# DB helper
def get_graph():
    host = os.getenv("FALKOR_HOST", "macmini")
    port = int(os.getenv("FALKOR_PORT", 6380))
    graph_name = os.getenv("FALKOR_GRAPH", "data_oop")
    db = FalkorDB(host=host, port=port)
    return db.select_graph(graph_name)


# Models
class ClassCreate(BaseModel):
    name: str
    label: Optional[str] = None
    description: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class PropertyCreate(BaseModel):
    name: str
    datatype: str = "string"
    description: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class PropertyAttach(BaseModel):
    class_name: str
    property_name: str
    required: bool = False
    unique: bool = False
    nullable: bool = True
    default: Optional[Any] = None


class RelationshipCreate(BaseModel):
    id: str
    name: str
    from_class: str
    to_class: str
    min_count: int = 0
    max_count: Optional[int] = None
    required: bool = False
    description: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class WorkflowStep(BaseModel):
    step_id: str
    action: str  # "create_node" or "create_relationship"
    class_name: Optional[str] = None
    properties: Optional[Dict[str, Any]] = None
    uuid: Optional[str] = None
    from_class: Optional[str] = None
    from_uuid: Optional[str] = None
    relationship_name: Optional[str] = None
    to_class: Optional[str] = None
    to_uuid: Optional[str] = None


class WorkflowCreate(BaseModel):
    name: str
    steps: List[dict]
    parameters: Optional[List[dict]] = None
    description: Optional[str] = None


class WorkflowRun(BaseModel):
    parameters: Dict[str, Any]


# Endpoints
@app.get("/api/tbox")
def get_tbox():
    try:
        graph = get_graph()
        repo = FalkorTBoxRepository(graph)
        
        classes = [c for c in repo.list_classes() if c.name != "WorkflowDefinition"]
        interfaces = repo.list_interfaces()
        properties = [p for p in repo.list_properties() if p.name not in ("steps_json", "parameters_json")]
        relationships = repo.list_relationships()
        constraints = repo.list_constraints()
        
        # Build enriched classes with effective properties
        enriched_classes = []
        for cls in classes:
            eff_props = repo.get_properties_of_class(cls.name)
            props_list = []
            for ep in eff_props:
                props_list.append({
                    "name": ep.property.name,
                    "datatype": ep.property.datatype,
                    "description": ep.property.description,
                    "required": ep.binding.required,
                    "unique": ep.binding.unique,
                    "nullable": ep.binding.nullable,
                    "default": ep.binding.default,
                    "source_kind": ep.source_kind,
                    "source_id": ep.source_id,
                })
            
            # Fetch implementing interfaces
            impl_ifaces = [i.name for i in repo.get_interfaces_of_class(cls.name)]
            
            enriched_classes.append({
                "name": cls.name,
                "label": cls.label,
                "description": cls.description,
                "metadata": cls.metadata,
                "properties": props_list,
                "interfaces": impl_ifaces,
            })
            
        return {
            "classes": enriched_classes,
            "interfaces": [
                {
                    "name": i.name,
                    "description": i.description,
                    "metadata": i.metadata,
                    "properties": [
                        {
                            "name": ep.property.name,
                            "datatype": ep.property.datatype,
                            "description": ep.property.description,
                            "required": ep.binding.required,
                            "unique": ep.binding.unique,
                            "nullable": ep.binding.nullable,
                            "default": ep.binding.default,
                        }
                        for ep in repo.get_properties_of_interface(i.name)
                    ]
                }
                for i in interfaces
            ],
            "properties": [
                {
                    "name": p.name,
                    "datatype": p.datatype,
                    "description": p.description,
                    "metadata": p.metadata,
                }
                for p in properties
            ],
            "relationships": [
                {
                    "id": r.id,
                    "name": r.name,
                    "from_class": r.from_class,
                    "to_class": r.to_class,
                    "min_count": r.min_count,
                    "max_count": r.max_count,
                    "required": r.required,
                    "description": r.description,
                    "metadata": r.metadata,
                }
                for r in relationships
            ],
            "constraints": [
                {
                    "id": c.id,
                    "kind": c.kind,
                    "target_kind": c.target_kind,
                    "target_id": c.target_id,
                    "property_names": list(c.property_names),
                    "expression": c.expression,
                    "severity": c.severity,
                    "description": c.description,
                    "metadata": c.metadata,
                }
                for c in constraints
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/tbox/class")
def create_class(data: ClassCreate):
    try:
        graph = get_graph()
        repo = FalkorTBoxRepository(graph)
        repo.create_class(
            data.name,
            label=data.label,
            description=data.description,
            metadata=data.metadata,
            merge=True
        )
        return {"status": "success", "message": f"Class {data.name} created/updated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/tbox/property")
def create_property(data: PropertyCreate):
    try:
        graph = get_graph()
        repo = FalkorTBoxRepository(graph)
        repo.create_property(
            data.name,
            datatype=data.datatype,
            description=data.description,
            metadata=data.metadata,
            merge=True
        )
        return {"status": "success", "message": f"Property {data.name} created/updated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/tbox/property/attach")
def attach_property(data: PropertyAttach):
    try:
        graph = get_graph()
        repo = FalkorTBoxRepository(graph)
        repo.attach_property_to_class(
            class_name=data.class_name,
            property_name=data.property_name,
            required=data.required,
            unique=data.unique,
            nullable=data.nullable,
            default=data.default,
        )
        return {"status": "success", "message": f"Property {data.property_name} attached to Class {data.class_name}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/tbox/relationship")
def create_relationship(data: RelationshipCreate):
    try:
        graph = get_graph()
        repo = FalkorTBoxRepository(graph)
        repo.define_relationship(
            id=data.id,
            name=data.name,
            from_class=data.from_class,
            to_class=data.to_class,
            min_count=data.min_count,
            max_count=data.max_count,
            required=data.required,
            description=data.description,
            metadata=data.metadata,
            merge=True,
        )
        return {"status": "success", "message": f"Relationship {data.name} ({data.id}) defined"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/workflows")
def list_workflows():
    try:
        graph = get_graph()
        # Query ABox WorkflowDefinition nodes
        res = graph.query(
            "MATCH (w:WorkflowDefinition) RETURN w.name, w.steps_json, w.description, w.uuid, w.parameters_json"
        )
        workflows = []
        for row in getattr(res, "result_set", []) or []:
            import json
            try:
                steps = json.loads(row[1]) if row[1] else []
            except Exception:
                steps = []
            try:
                parameters = json.loads(row[4]) if len(row) > 4 and row[4] else []
            except Exception:
                parameters = []
            workflows.append({
                "name": row[0],
                "steps": steps,
                "parameters": parameters,
                "description": row[2],
                "uuid": row[3]
            })
        return workflows
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/workflows")
def create_workflow(data: WorkflowCreate):
    try:
        graph = get_graph()
        res = save_workflow(
            graph=graph,
            name=data.name,
            steps=data.steps,
            parameters=data.parameters,
            description=data.description
        )
        return {"status": "success", "uuid": res.uuid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/workflows/{name}/run")
def execute_workflow(name: str, data: WorkflowRun):
    try:
        graph = get_graph()
        results = run_workflow(
            graph=graph,
            name=name,
            parameters=data.parameters,
        )
        return {"status": "success", "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/validation")
def run_validation():
    try:
        graph = get_graph()
        res = run_latest_falkor_abox_validation(graph=graph)
        return {
            "run_id": res.run_id,
            "status": res.status,
            "checked_instance_count": res.checked_instance_count,
            "error_count": res.error_count,
            "warning_count": res.warning_count,
            "issue_count": res.issue_count,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/validation/latest")
def get_latest_validation():
    try:
        graph = get_graph()
        # Find latest ValidationRun
        run_res = graph.query(
            "MATCH (r:ValidationRun) RETURN r.id, r.status, r.startedAt, r.checkedInstanceCount, r.errorCount, r.warningCount"
        )
        run_rows = getattr(run_res, "result_set", []) or []
        if not run_rows:
            return {"run": None, "issues": []}
        
        run_row = run_rows[0]
        run_id = run_row[0]
        run_info = {
            "id": run_id,
            "status": run_row[1],
            "started_at": run_row[2],
            "checked_instance_count": run_row[3],
            "error_count": run_row[4],
            "warning_count": run_row[5],
        }
        
        # Get issues
        issues_res = graph.query(
            """
            MATCH (r:ValidationRun {id: $run_id})-[:HAS_ISSUE]->(i:ValidationIssue)
            RETURN i.id, i.code, i.severity, i.className, i.instanceUuid, i.propertyName, i.relationshipName, i.message
            """,
            {"run_id": run_id}
        )
        issues = []
        for row in getattr(issues_res, "result_set", []) or []:
            issues.append({
                "id": row[0],
                "code": row[1],
                "severity": row[2],
                "className": row[3],
                "instanceUuid": row[4],
                "propertyName": row[5],
                "relationshipName": row[6],
                "message": row[7],
            })
            
        return {"run": run_info, "issues": issues}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/abox/nodes")
def get_abox_nodes():
    try:
        graph = get_graph()
        # Count nodes by labels (excluding TBox and Validation nodes)
        res = graph.query(
            """
            MATCH (n)
            WHERE NOT n:TBox AND NOT n:ValidationRun AND NOT n:ValidationIssue
            RETURN labels(n), count(n)
            """
        )
        counts = []
        for row in getattr(res, "result_set", []) or []:
            labels = row[0]
            # labels is usually a list
            label = labels[0] if labels else "Unknown"
            counts.append({
                "label": label,
                "count": row[1]
            })
            
        # Get some preview nodes
        nodes_res = graph.query(
            """
            MATCH (n)
            WHERE NOT n:TBox AND NOT n:ValidationRun AND NOT n:ValidationIssue
            RETURN labels(n), n.uuid, properties(n)
            LIMIT 100
            """
        )
        nodes = []
        for row in getattr(nodes_res, "result_set", []) or []:
            labels = row[0]
            label = labels[0] if labels else "Unknown"
            # properties(n) returns a map
            props = row[2] if len(row) > 2 else {}
            nodes.append({
                "label": label,
                "uuid": row[1],
                "properties": props
            })
            
        return {
            "counts": counts,
            "nodes": nodes
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/abox/nodes/{class_name}")
def list_abox_nodes_by_class(class_name: str):
    import re
    if not re.match(r"^[a-zA-Z0-9_]+$", class_name):
        raise HTTPException(status_code=400, detail="Invalid class name")
        
    try:
        graph = get_graph()
        res = graph.query(
            f"MATCH (n:{class_name}) RETURN n.uuid, properties(n) LIMIT 500"
        )
        nodes = []
        for row in getattr(res, "result_set", []) or []:
            uuid = row[0]
            props = row[1] if len(row) > 1 else {}
            display_name = props.get("name") or props.get("title") or props.get("label") or props.get("channel_code") or uuid
            nodes.append({
                "uuid": uuid,
                "display_name": display_name,
                "properties": props
            })
        return nodes
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
