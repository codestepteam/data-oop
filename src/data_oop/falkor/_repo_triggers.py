from __future__ import annotations

import json
from typing import Any

from data_oop.exceptions import TBoxConflictError, TBoxNotFoundError
from data_oop.schema.models import (
    TriggerDef,
    TriggerEvent,
)
from data_oop.workflow.triggers import TriggerGraphReport, analyze_trigger_graph, validate_trigger_graph
from data_oop.falkor._repo_base import _RepositoryBase


class _TriggerMixin(_RepositoryBase):
    # ------------------------------------------------------------------
    # Triggers (class-level callbacks: on create/update -> run workflow)
    # ------------------------------------------------------------------
    def _load_workflow_steps(self) -> dict[str, list[dict[str, Any]]]:
        """Load every stored workflow's steps, for trigger-graph analysis."""
        rows = self._query("MATCH (w:WorkflowDefinition) RETURN w.name, w.steps_json")
        out: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            try:
                out[row[0]] = json.loads(row[1]) if row[1] else []
            except (TypeError, json.JSONDecodeError):
                out[row[0]] = []
        return out

    def _trigger_from_row(self, class_name: str, row: list[Any]) -> TriggerDef:
        # row: name, event, workflowName, condition, enabled, orderIndex, description, paramMap
        return TriggerDef(
            name=row[0],
            class_name=class_name,
            event=row[1],
            workflow_name=row[2],
            condition=row[3] or None,
            enabled=True if row[4] is None else bool(row[4]),
            order=int(row[5]) if row[5] is not None else 0,
            description=row[6],
            parameter_map=self._parse_json(row[7]) if len(row) > 7 else {},
        )

    def analyze_triggers(self, extra: TriggerDef | None = None) -> TriggerGraphReport:
        """Analyse the current trigger graph (optionally with one prospective
        trigger added) for cycles and divergence, without mutating anything."""
        triggers = self.list_triggers()
        if extra is not None:
            triggers = [
                t for t in triggers if not (t.class_name == extra.class_name and t.name == extra.name)
            ]
            triggers.append(extra)
        return analyze_trigger_graph(triggers, self._load_workflow_steps())

    def attach_trigger_to_class(
        self,
        *,
        class_name: str,
        name: str,
        event: TriggerEvent,
        workflow_name: str,
        condition: str | None = None,
        enabled: bool = True,
        order: int = 0,
        description: str | None = None,
        parameter_map: dict[str, Any] | None = None,
    ) -> TriggerDef:
        """Register (or replace) a trigger on a class. Rejects the trigger if it
        would introduce a cycle in the trigger graph."""
        self._require_class(class_name)
        if event not in ("create", "update"):
            raise TBoxConflictError(f"Unsupported trigger event: {event}")
        rows = self._query(
            "MATCH (w:WorkflowDefinition {name: $name}) RETURN count(w)",
            {"name": workflow_name},
        )
        if not rows or int(rows[0][0]) == 0:
            raise TBoxNotFoundError(f"WorkflowDefinition not found: {workflow_name}")

        prospective = TriggerDef(
            name=name,
            class_name=class_name,
            event=event,
            workflow_name=workflow_name,
            condition=condition,
            enabled=enabled,
            order=order,
            description=description,
            parameter_map=dict(parameter_map or {}),
        )
        existing = [
            t for t in self.list_triggers() if not (t.class_name == class_name and t.name == name)
        ]
        # Raises TriggerCycleError if this trigger closes a loop.
        validate_trigger_graph(existing + [prospective], self._load_workflow_steps())

        uuid = self._stable_uuid("TriggerDef", f"{class_name}:{name}")
        # Replace any prior trigger node with the same identity (edge first).
        self._query(
            "MATCH (:TBox:ClassDef)-[e:HAS_TRIGGER]->(t:TBox:TriggerDef {uuid: $uuid}) DELETE e",
            {"uuid": uuid},
        )
        self._query("MATCH (t:TBox:TriggerDef {uuid: $uuid}) DELETE t", {"uuid": uuid})
        self._query(
            """
            MATCH (c:TBox:ClassDef {name: $class_name})
            CREATE (c)-[:HAS_TRIGGER]->(t:TBox:TriggerDef {
                uuid: $uuid,
                name: $name,
                event: $event,
                workflowName: $workflow_name,
                condition: $condition,
                enabled: $enabled,
                orderIndex: $order,
                description: $description,
                paramMap: $param_map
            })
            """,
            {
                "class_name": class_name,
                "uuid": uuid,
                "name": name,
                "event": event,
                "workflow_name": workflow_name,
                "condition": condition,
                "enabled": enabled,
                "order": order,
                "description": description,
                "param_map": self._json(dict(parameter_map or {})),
            },
        )
        return prospective

    def get_triggers_for_class(
        self, class_name: str, *, event: str | None = None
    ) -> list[TriggerDef]:
        """Return triggers on a class. When ``event`` is given, returns only the
        enabled triggers for that event (the runtime dispatch path), ordered by
        ``order`` then ``name``; otherwise returns all triggers on the class."""
        params: dict[str, Any] = {"class_name": class_name}
        where = ""
        if event is not None:
            where = "WHERE t.event = $event "
            params["event"] = event
        rows = self._query(
            f"""
            MATCH (c:TBox:ClassDef {{name: $class_name}})-[:HAS_TRIGGER]->(t:TBox:TriggerDef)
            {where}RETURN t.name, t.event, t.workflowName, t.condition, t.enabled, t.orderIndex, t.description, t.paramMap
            """,
            params,
        )
        triggers = [self._trigger_from_row(class_name, row) for row in rows]
        if event is not None:
            triggers = [t for t in triggers if t.enabled]
        triggers.sort(key=lambda t: (t.order, t.name))
        return triggers

    def list_triggers(self) -> list[TriggerDef]:
        rows = self._query(
            """
            MATCH (c:TBox:ClassDef)-[:HAS_TRIGGER]->(t:TBox:TriggerDef)
            RETURN c.name, t.name, t.event, t.workflowName, t.condition, t.enabled, t.orderIndex, t.description, t.paramMap
            """
        )
        triggers = [self._trigger_from_row(row[0], row[1:]) for row in rows]
        return sorted(triggers, key=lambda t: (t.class_name, t.order, t.name))

    def delete_trigger(self, class_name: str, name: str) -> None:
        uuid = self._stable_uuid("TriggerDef", f"{class_name}:{name}")
        self._query(
            "MATCH (:TBox:ClassDef)-[e:HAS_TRIGGER]->(t:TBox:TriggerDef {uuid: $uuid}) DELETE e",
            {"uuid": uuid},
        )
        self._query("MATCH (t:TBox:TriggerDef {uuid: $uuid}) DELETE t", {"uuid": uuid})
