from __future__ import annotations

from typing import Any, Literal

from data_oop.exceptions import TBoxAlreadyExistsError
from data_oop.schema.models import (
    ConstraintDef,
)
from data_oop.falkor._repo_base import _RepositoryBase


class _ConstraintMixin(_RepositoryBase):
    # ------------------------------------------------------------------
    # Constraint
    # ------------------------------------------------------------------
    def create_constraint(
        self,
        *,
        id: str,
        kind: str,
        target_kind: Literal["class", "interface", "property", "relationship"],
        target_id: str,
        property_names: tuple[str, ...] = (),
        expression: str | None = None,
        severity: Literal["info", "warning", "error"] = "error",
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
        merge: bool = True,
    ) -> ConstraintDef:
        # Check target
        if target_kind == "class":
            self._require_class(target_id)
        elif target_kind == "interface":
            self._require_interface(target_id)
        elif target_kind == "property":
            self._require_property(target_id)
        elif target_kind == "relationship":
            self._require_relationship(target_id)

        existing = self.get_constraint(id)
        if existing:
            if not merge:
                raise TBoxAlreadyExistsError(f"ConstraintDef already exists: {id}")
            return self.update_constraint(
                id,
                kind=kind,
                target_kind=target_kind,
                target_id=target_id,
                property_names=property_names,
                expression=expression,
                severity=severity,
                description=description,
                metadata=metadata
            )

        uuid = self._stable_uuid("ConstraintDef", id)
        meta_str = self._json(metadata or {})
        
        self._query(
            """
            CREATE (c:TBox:ConstraintDef {
                id: $id,
                uuid: $uuid,
                kind: $kind,
                targetKind: $target_kind,
                targetId: $target_id,
                propertyNames: $property_names,
                expression: $expression,
                severity: $severity,
                description: $description,
                metadata: $metadata
            })
            """,
            {
                "id": id,
                "uuid": uuid,
                "kind": kind,
                "target_kind": target_kind,
                "target_id": target_id,
                "property_names": list(property_names),
                "expression": expression,
                "severity": severity,
                "description": description,
                "metadata": meta_str
            }
        )

        # Create CONSTRAINS relationship
        target_label = "ClassDef" if target_kind == "class" else ("InterfaceDef" if target_kind == "interface" else ("PropertyDef" if target_kind == "property" else "RelationshipDef"))
        target_key = "name" if target_kind in ("class", "interface", "property") else "id"
        self._query(
            f"""
            MATCH (c:ConstraintDef {{id: $id}})
            MATCH (target:{target_label} {{{target_key}: $target_id}})
            MERGE (c)-[:CONSTRAINS]->(target)
            """,
            {"id": id, "target_id": target_id}
        )

        return ConstraintDef(
            id=id,
            kind=kind,
            target_kind=target_kind,
            target_id=target_id,
            property_names=property_names,
            expression=expression,
            severity=severity,
            description=description,
            metadata=metadata or {}
        )

    def get_constraint(self, id: str) -> ConstraintDef | None:
        rows = self._query(
            "MATCH (c:TBox:ConstraintDef {id: $id}) RETURN c.id, c.kind, c.targetKind, c.targetId, c.propertyNames, c.expression, c.severity, c.description, c.metadata",
            {"id": id}
        )
        if not rows:
            return None
        row = rows[0]
        return ConstraintDef(
            id=row[0],
            kind=row[1],
            target_kind=row[2],
            target_id=row[3],
            property_names=tuple(row[4] or []),
            expression=row[5],
            severity=row[6],
            description=row[7],
            metadata=self._parse_json(row[8])
        )

    def update_constraint(
        self,
        id: str,
        *,
        kind: str | None = None,
        target_kind: Literal["class", "interface", "property", "relationship"] | None = None,
        target_id: str | None = None,
        property_names: tuple[str, ...] | None = None,
        expression: str | None = None,
        severity: Literal["info", "warning", "error"] | None = None,
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ConstraintDef:
        existing = self._require_constraint(id)
        
        new_kind = kind if kind is not None else existing.kind
        new_target_kind = target_kind if target_kind is not None else existing.target_kind
        new_target_id = target_id if target_id is not None else existing.target_id
        new_property_names = property_names if property_names is not None else existing.property_names
        new_expression = expression if expression is not None else existing.expression
        new_severity = severity if severity is not None else existing.severity
        new_description = description if description is not None else existing.description

        if target_kind is not None or target_id is not None:
            if new_target_kind == "class":
                self._require_class(new_target_id)
            elif new_target_kind == "interface":
                self._require_interface(new_target_id)
            elif new_target_kind == "property":
                self._require_property(new_target_id)
            elif new_target_kind == "relationship":
                self._require_relationship(new_target_id)

        merged_metadata = dict(existing.metadata)
        if metadata:
            merged_metadata.update(metadata)
        meta_str = self._json(merged_metadata)

        self._query(
            """
            MATCH (c:TBox:ConstraintDef {id: $id})
            SET c.kind = $kind,
                c.targetKind = $target_kind,
                c.targetId = $target_id,
                c.propertyNames = $property_names,
                c.expression = $expression,
                c.severity = $severity,
                c.description = $description,
                c.metadata = $metadata
            """,
            {
                "id": id,
                "kind": new_kind,
                "target_kind": new_target_kind,
                "target_id": new_target_id,
                "property_names": list(new_property_names),
                "expression": new_expression,
                "severity": new_severity,
                "description": new_description,
                "metadata": meta_str
            }
        )

        if target_kind is not None or target_id is not None:
            # Recreate CONSTRAINS relationship
            self._query("MATCH (c:ConstraintDef {id: $id})-[edge:CONSTRAINS]->() DELETE edge", {"id": id})
            target_label = "ClassDef" if new_target_kind == "class" else ("InterfaceDef" if new_target_kind == "interface" else ("PropertyDef" if new_target_kind == "property" else "RelationshipDef"))
            target_key = "name" if new_target_kind in ("class", "interface", "property") else "id"
            self._query(
                f"""
                MATCH (c:ConstraintDef {{id: $id}})
                MATCH (target:{target_label} {{{target_key}: $target_id}})
                MERGE (c)-[:CONSTRAINS]->(target)
                """,
                {"id": id, "target_id": new_target_id}
            )

        return ConstraintDef(
            id=id,
            kind=new_kind,
            target_kind=new_target_kind,
            target_id=new_target_id,
            property_names=new_property_names,
            expression=new_expression,
            severity=new_severity,
            description=new_description,
            metadata=merged_metadata
        )

    def delete_constraint(self, id: str) -> None:
        self._require_constraint(id)
        self._query("MATCH (c:ConstraintDef {id: $id})-[edge:CONSTRAINS]->() DELETE edge", {"id": id})
        self._query("MATCH (c:TBox:ConstraintDef {id: $id}) DELETE c", {"id": id})

    def list_constraints(
        self,
        *,
        target_kind: str | None = None,
        target_id: str | None = None,
        kind: str | None = None,
    ) -> list[ConstraintDef]:
        query_parts = ["MATCH (c:TBox:ConstraintDef)"]
        conditions = []
        params = {}
        
        if target_kind is not None:
            conditions.append("c.targetKind = $target_kind")
            params["target_kind"] = target_kind
        if target_id is not None:
            conditions.append("c.targetId = $target_id")
            params["target_id"] = target_id
        if kind is not None:
            conditions.append("c.kind = $kind")
            params["kind"] = kind
            
        if conditions:
            query_parts.append("WHERE " + " AND ".join(conditions))
            
        query_parts.append("RETURN c.id, c.kind, c.targetKind, c.targetId, c.propertyNames, c.expression, c.severity, c.description, c.metadata")
        
        rows = self._query(" ".join(query_parts), params)
        constraints = [
            ConstraintDef(
                id=row[0],
                kind=row[1],
                target_kind=row[2],
                target_id=row[3],
                property_names=tuple(row[4] or []),
                expression=row[5],
                severity=row[6],
                description=row[7],
                metadata=self._parse_json(row[8])
            )
            for row in rows
        ]
        return sorted(constraints, key=lambda value: value.id)

