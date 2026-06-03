from __future__ import annotations

import json
from typing import Any, Literal
from uuid import NAMESPACE_URL, uuid5

from .exceptions import TBoxAlreadyExistsError, TBoxConflictError, TBoxNotFoundError
from .falkor import FalkorGraph
from .models import (
    ClassDef,
    ConnectorDef,
    ConstraintDef,
    EffectivePropertyDef,
    InterfaceDef,
    MetricDef,
    OwnerKind,
    PropertyBinding,
    PropertyDef,
    RelationshipDef,
    SourceBinding,
    SourceLink,
    TriggerDef,
    TriggerEvent,
)
from .triggers import TriggerGraphReport, analyze_trigger_graph, validate_trigger_graph


class FalkorTBoxRepository:
    """TBox repository implementation that queries and updates FalkorDB directly in real-time.

    This ensures FalkorDB is the Single Source of Truth (SSOT), and all DSL modifications
    are applied instantly to the live database graph.
    """

    def __init__(self, graph: FalkorGraph):
        self.graph = graph

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _query(self, query: str, params: dict[str, Any] | None = None) -> list[list[Any]]:
        result = self.graph.query(query, params)
        return list(getattr(result, "result_set", []) or [])

    @staticmethod
    def _stable_uuid(kind: str, key: str) -> str:
        return str(uuid5(NAMESPACE_URL, f"tbox:{kind}:{key}"))

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)

    @staticmethod
    def _parse_json(value: Any) -> dict[str, Any]:
        if not value:
            return {}
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return {}
        return dict(value)

    @staticmethod
    def _links_to_json(links: tuple[SourceLink, ...]) -> str:
        return json.dumps(
            [
                {
                    "relationship_name": link.relationship_name,
                    "to_class": link.to_class,
                    "local_key": link.local_key,
                    "target_property": link.target_property or link.local_key,
                    "direction": link.direction,
                }
                for link in links
            ],
            ensure_ascii=False,
            sort_keys=True,
        )

    @staticmethod
    def _parse_links(value: Any) -> tuple[SourceLink, ...]:
        if not value:
            return ()
        data = json.loads(value) if isinstance(value, str) else value
        return tuple(
            SourceLink(
                relationship_name=item["relationship_name"],
                to_class=item["to_class"],
                local_key=item["local_key"],
                target_property=item.get("target_property") or item["local_key"],
                direction=item.get("direction", "out"),
            )
            for item in data
        )

    def _require_class(self, name: str) -> ClassDef:
        cls = self.get_class(name)
        if not cls:
            raise TBoxNotFoundError(f"ClassDef not found: {name}")
        return cls

    def _require_interface(self, name: str) -> InterfaceDef:
        iface = self.get_interface(name)
        if not iface:
            raise TBoxNotFoundError(f"InterfaceDef not found: {name}")
        return iface

    def _require_property(self, name: str) -> PropertyDef:
        prop = self.get_property(name)
        if not prop:
            raise TBoxNotFoundError(f"PropertyDef not found: {name}")
        return prop

    def _require_relationship(self, id: str) -> RelationshipDef:
        rel = self.get_relationship(id)
        if not rel:
            raise TBoxNotFoundError(f"RelationshipDef not found: {id}")
        return rel

    def _require_constraint(self, id: str) -> ConstraintDef:
        const = self.get_constraint(id)
        if not const:
            raise TBoxNotFoundError(f"ConstraintDef not found: {id}")
        return const

    def _require_connector(self, name: str) -> ConnectorDef:
        connector = self.get_connector(name)
        if not connector:
            raise TBoxNotFoundError(f"ConnectorDef not found: {name}")
        return connector

    def _require_metric(self, name: str) -> MetricDef:
        metric = self.get_metric(name)
        if not metric:
            raise TBoxNotFoundError(f"MetricDef not found: {name}")
        return metric

    def _require_owner(self, owner_kind: OwnerKind, owner_id: str) -> None:
        if owner_kind == "class":
            self._require_class(owner_id)
        elif owner_kind == "interface":
            self._require_interface(owner_id)
        elif owner_kind == "relationship":
            self._require_relationship(owner_id)

    # ------------------------------------------------------------------
    # Class
    # ------------------------------------------------------------------
    def create_class(
        self,
        name: str,
        *,
        label: str | None = None,
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
        merge: bool = True,
    ) -> ClassDef:
        existing = self.get_class(name)
        if existing:
            if not merge:
                raise TBoxAlreadyExistsError(f"ClassDef already exists: {name}")
            return self.update_class(name, label=label, description=description, metadata=metadata)

        uuid = self._stable_uuid("ClassDef", name)
        meta_str = self._json(metadata or {})
        self._query(
            """
            CREATE (n:TBox:ClassDef {
                name: $name,
                uuid: $uuid,
                label: $label,
                description: $description,
                metadata: $metadata
            })
            """,
            {"name": name, "uuid": uuid, "label": label, "description": description, "metadata": meta_str}
        )
        return ClassDef(name=name, label=label, description=description, metadata=metadata or {})

    def get_class(self, name: str) -> ClassDef | None:
        rows = self._query(
            "MATCH (n:TBox:ClassDef {name: $name}) RETURN n.name, n.label, n.description, n.metadata",
            {"name": name}
        )
        if not rows:
            return None
        row = rows[0]
        return ClassDef(
            name=row[0],
            label=row[1],
            description=row[2],
            metadata=self._parse_json(row[3])
        )

    def update_class(
        self,
        name: str,
        *,
        label: str | None = None,
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ClassDef:
        existing = self._require_class(name)
        new_label = label if label is not None else existing.label
        new_description = description if description is not None else existing.description
        
        merged_metadata = dict(existing.metadata)
        if metadata:
            merged_metadata.update(metadata)
        meta_str = self._json(merged_metadata)

        self._query(
            """
            MATCH (n:TBox:ClassDef {name: $name})
            SET n.label = $label,
                n.description = $description,
                n.metadata = $metadata
            """,
            {"name": name, "label": new_label, "description": new_description, "metadata": meta_str}
        )
        return ClassDef(name=name, label=new_label, description=new_description, metadata=merged_metadata)

    def delete_class(self, name: str, *, detach: bool = False) -> None:
        self._require_class(name)
        # Check references: IMPLEMENTS, HAS_PROPERTY (as owner), FROM_CLASS/TO_CLASS (in RelationshipDef)
        has_ref = False
        
        # 1. Check implements
        rows = self._query("MATCH (c:ClassDef {name: $name})-[:IMPLEMENTS]->() RETURN count(c)", {"name": name})
        if rows and int(rows[0][0]) > 0:
            has_ref = True

        # 2. Check properties
        rows = self._query("MATCH (c:ClassDef {name: $name})-[:HAS_PROPERTY]->() RETURN count(c)", {"name": name})
        if rows and int(rows[0][0]) > 0:
            has_ref = True

        # 3. Check relationships
        rows = self._query(
            """
            MATCH (r:RelationshipDef)
            WHERE r.from_class = $name OR r.to_class = $name
            RETURN count(r)
            """,
            {"name": name}
        )
        if rows and int(rows[0][0]) > 0:
            has_ref = True

        if has_ref and not detach:
            raise TBoxConflictError(f"ClassDef has references: {name}")

        # Detach/Delete IMPLEMENTS and HAS_PROPERTY relations, delete relationship nodes as well if detaching
        if detach:
            self._query("MATCH (c:ClassDef {name: $name})-[r:IMPLEMENTS]->() DELETE r", {"name": name})
            self._query("MATCH (c:ClassDef {name: $name})-[r:HAS_PROPERTY]->() DELETE r", {"name": name})
            
            # Delete relationships referencing this class
            rel_rows = self._query(
                "MATCH (r:RelationshipDef) WHERE r.from_class = $name OR r.to_class = $name RETURN r.id",
                {"name": name}
            )
            for row in rel_rows:
                self.delete_relationship(row[0], detach=True)

        # Source binding lives on the HAS_CONNECTOR edge owned by this class; drop it
        # unconditionally so the node delete below never trips over a dangling edge.
        self._query(
            "MATCH (c:ClassDef {name: $name})-[r:HAS_CONNECTOR]->() DELETE r",
            {"name": name},
        )

        self._query("MATCH (c:TBox:ClassDef {name: $name}) DELETE c", {"name": name})

    def list_classes(
        self, *, implements: str | None = None, has_property: str | None = None
    ) -> list[ClassDef]:
        if implements is not None:
            query = "MATCH (n:TBox:ClassDef)-[:IMPLEMENTS]->(i:InterfaceDef {name: $implements}) RETURN n.name, n.label, n.description, n.metadata"
            params = {"implements": implements}
        elif has_property is not None:
            query = "MATCH (n:TBox:ClassDef)-[:HAS_PROPERTY]->(p:PropertyDef {name: $has_property}) RETURN n.name, n.label, n.description, n.metadata"
            params = {"has_property": has_property}
        else:
            query = "MATCH (n:TBox:ClassDef) RETURN n.name, n.label, n.description, n.metadata"
            params = {}

        rows = self._query(query, params)
        classes = [
            ClassDef(
                name=row[0],
                label=row[1],
                description=row[2],
                metadata=self._parse_json(row[3])
            )
            for row in rows
        ]
        return sorted(classes, key=lambda value: value.name)

    # ------------------------------------------------------------------
    # Interface
    # ------------------------------------------------------------------
    def create_interface(
        self,
        name: str,
        *,
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
        merge: bool = True,
    ) -> InterfaceDef:
        existing = self.get_interface(name)
        if existing:
            if not merge:
                raise TBoxAlreadyExistsError(f"InterfaceDef already exists: {name}")
            return self.update_interface(name, description=description, metadata=metadata)

        uuid = self._stable_uuid("InterfaceDef", name)
        meta_str = self._json(metadata or {})
        self._query(
            """
            CREATE (n:TBox:InterfaceDef {
                name: $name,
                uuid: $uuid,
                description: $description,
                metadata: $metadata
            })
            """,
            {"name": name, "uuid": uuid, "description": description, "metadata": meta_str}
        )
        return InterfaceDef(name=name, description=description, metadata=metadata or {})

    def get_interface(self, name: str) -> InterfaceDef | None:
        rows = self._query(
            "MATCH (n:TBox:InterfaceDef {name: $name}) RETURN n.name, n.description, n.metadata",
            {"name": name}
        )
        if not rows:
            return None
        row = rows[0]
        return InterfaceDef(
            name=row[0],
            description=row[1],
            metadata=self._parse_json(row[2])
        )

    def update_interface(
        self,
        name: str,
        *,
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> InterfaceDef:
        existing = self._require_interface(name)
        new_description = description if description is not None else existing.description
        
        merged_metadata = dict(existing.metadata)
        if metadata:
            merged_metadata.update(metadata)
        meta_str = self._json(merged_metadata)

        self._query(
            """
            MATCH (n:TBox:InterfaceDef {name: $name})
            SET n.description = $description,
                n.metadata = $metadata
            """,
            {"name": name, "description": new_description, "metadata": meta_str}
        )
        return InterfaceDef(name=name, description=new_description, metadata=merged_metadata)

    def delete_interface(self, name: str, *, detach: bool = False) -> None:
        self._require_interface(name)
        has_ref = False
        
        rows = self._query("MATCH ()-[r:IMPLEMENTS]->(i:InterfaceDef {name: $name}) RETURN count(r)", {"name": name})
        if rows and int(rows[0][0]) > 0:
            has_ref = True
            
        rows = self._query("MATCH (i:InterfaceDef {name: $name})-[:HAS_PROPERTY]->() RETURN count(i)", {"name": name})
        if rows and int(rows[0][0]) > 0:
            has_ref = True

        if has_ref and not detach:
            raise TBoxConflictError(f"InterfaceDef has references: {name}")

        if detach:
            self._query("MATCH ()-[r:IMPLEMENTS]->(i:InterfaceDef {name: $name}) DELETE r", {"name": name})
            self._query("MATCH (i:InterfaceDef {name: $name})-[r:HAS_PROPERTY]->() DELETE r", {"name": name})

        self._query("MATCH (i:TBox:InterfaceDef {name: $name}) DELETE i", {"name": name})

    def list_interfaces(
        self,
        *,
        implemented_by: str | None = None,
        has_property: str | None = None,
    ) -> list[InterfaceDef]:
        if implemented_by is not None:
            query = "MATCH (c:ClassDef {name: $implemented_by})-[:IMPLEMENTS]->(n:TBox:InterfaceDef) RETURN n.name, n.description, n.metadata"
            params = {"implemented_by": implemented_by}
        elif has_property is not None:
            query = "MATCH (n:TBox:InterfaceDef)-[:HAS_PROPERTY]->(p:PropertyDef {name: $has_property}) RETURN n.name, n.description, n.metadata"
            params = {"has_property": has_property}
        else:
            query = "MATCH (n:TBox:InterfaceDef) RETURN n.name, n.description, n.metadata"
            params = {}

        rows = self._query(query, params)
        interfaces = [
            InterfaceDef(
                name=row[0],
                description=row[1],
                metadata=self._parse_json(row[2])
            )
            for row in rows
        ]
        return sorted(interfaces, key=lambda value: value.name)

    # ------------------------------------------------------------------
    # Implements
    # ------------------------------------------------------------------
    def implement_interface(self, *, class_name: str, interface_name: str) -> None:
        self._require_class(class_name)
        self._require_interface(interface_name)
        self._query(
            """
            MATCH (c:ClassDef {name: $class_name})
            MATCH (i:InterfaceDef {name: $interface_name})
            MERGE (c)-[:IMPLEMENTS]->(i)
            """,
            {"class_name": class_name, "interface_name": interface_name}
        )

    def remove_interface(self, *, class_name: str, interface_name: str) -> None:
        self._require_class(class_name)
        self._require_interface(interface_name)
        self._query(
            """
            MATCH (c:ClassDef {name: $class_name})-[r:IMPLEMENTS]->(i:InterfaceDef {name: $interface_name})
            DELETE r
            """,
            {"class_name": class_name, "interface_name": interface_name}
        )

    def class_implements(self, *, class_name: str, interface_name: str) -> bool:
        self._require_class(class_name)
        self._require_interface(interface_name)
        rows = self._query(
            """
            MATCH (c:ClassDef {name: $class_name})-[r:IMPLEMENTS]->(i:InterfaceDef {name: $interface_name})
            RETURN count(r)
            """,
            {"class_name": class_name, "interface_name": interface_name}
        )
        return bool(rows and int(rows[0][0]) > 0)

    def get_interfaces_of_class(self, class_name: str) -> list[InterfaceDef]:
        self._require_class(class_name)
        rows = self._query(
            """
            MATCH (c:ClassDef {name: $class_name})-[:IMPLEMENTS]->(i:InterfaceDef)
            RETURN i.name, i.description, i.metadata
            """,
            {"class_name": class_name}
        )
        interfaces = [
            InterfaceDef(name=row[0], description=row[1], metadata=self._parse_json(row[2]))
            for row in rows
        ]
        return sorted(interfaces, key=lambda value: value.name)

    def get_classes_of_interface(self, interface_name: str) -> list[ClassDef]:
        self._require_interface(interface_name)
        rows = self._query(
            """
            MATCH (c:ClassDef)-[:IMPLEMENTS]->(i:InterfaceDef {name: $interface_name})
            RETURN c.name, c.label, c.description, c.metadata
            """,
            {"interface_name": interface_name}
        )
        classes = [
            ClassDef(name=row[0], label=row[1], description=row[2], metadata=self._parse_json(row[3]))
            for row in rows
        ]
        return sorted(classes, key=lambda value: value.name)

    # ------------------------------------------------------------------
    # Property
    # ------------------------------------------------------------------
    def create_property(
        self,
        name: str,
        *,
        datatype: str = "unknown",
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
        merge: bool = True,
    ) -> PropertyDef:
        existing = self.get_property(name)
        if existing:
            if not merge:
                raise TBoxAlreadyExistsError(f"PropertyDef already exists: {name}")
            new_datatype = datatype if datatype != "unknown" or existing.datatype == "unknown" else existing.datatype
            return self.update_property(name, datatype=new_datatype, description=description, metadata=metadata)

        uuid = self._stable_uuid("PropertyDef", name)
        meta_str = self._json(metadata or {})
        self._query(
            """
            CREATE (n:TBox:PropertyDef {
                name: $name,
                uuid: $uuid,
                datatype: $datatype,
                description: $description,
                metadata: $metadata
            })
            """,
            {"name": name, "uuid": uuid, "datatype": datatype, "description": description, "metadata": meta_str}
        )
        return PropertyDef(name=name, datatype=datatype, description=description, metadata=metadata or {})

    def get_property(self, name: str) -> PropertyDef | None:
        rows = self._query(
            "MATCH (n:TBox:PropertyDef {name: $name}) RETURN n.name, n.datatype, n.description, n.metadata",
            {"name": name}
        )
        if not rows:
            return None
        row = rows[0]
        return PropertyDef(
            name=row[0],
            datatype=row[1],
            description=row[2],
            metadata=self._parse_json(row[3])
        )

    def update_property(
        self,
        name: str,
        *,
        datatype: str | None = None,
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> PropertyDef:
        existing = self._require_property(name)
        new_datatype = datatype if datatype is not None else existing.datatype
        new_description = description if description is not None else existing.description
        
        merged_metadata = dict(existing.metadata)
        if metadata:
            merged_metadata.update(metadata)
        meta_str = self._json(merged_metadata)

        self._query(
            """
            MATCH (n:TBox:PropertyDef {name: $name})
            SET n.datatype = $datatype,
                n.description = $description,
                n.metadata = $metadata
            """,
            {"name": name, "datatype": new_datatype, "description": new_description, "metadata": meta_str}
        )
        return PropertyDef(name=name, datatype=new_datatype, description=new_description, metadata=merged_metadata)

    def delete_property(self, name: str, *, detach: bool = False) -> None:
        self._require_property(name)
        has_ref = False
        
        rows = self._query("MATCH ()-[r:HAS_PROPERTY]->(p:PropertyDef {name: $name}) RETURN count(r)", {"name": name})
        if rows and int(rows[0][0]) > 0:
            has_ref = True

        if has_ref and not detach:
            raise TBoxConflictError(f"PropertyDef has references: {name}")

        if detach:
            self._query("MATCH ()-[r:HAS_PROPERTY]->(p:PropertyDef {name: $name}) DELETE r", {"name": name})

        self._query("MATCH (p:TBox:PropertyDef {name: $name}) DELETE p", {"name": name})

    def list_properties(
        self,
        *,
        owner_class: str | None = None,
        owner_interface: str | None = None,
        owner_relationship: str | None = None,
    ) -> list[PropertyDef]:
        if owner_class is not None:
            self._require_class(owner_class)
            query = "MATCH (c:ClassDef {name: $owner_id})-[:HAS_PROPERTY]->(n:TBox:PropertyDef) RETURN n.name, n.datatype, n.description, n.metadata"
            params = {"owner_id": owner_class}
        elif owner_interface is not None:
            self._require_interface(owner_interface)
            query = "MATCH (i:InterfaceDef {name: $owner_id})-[:HAS_PROPERTY]->(n:TBox:PropertyDef) RETURN n.name, n.datatype, n.description, n.metadata"
            params = {"owner_id": owner_interface}
        elif owner_relationship is not None:
            self._require_relationship(owner_relationship)
            query = "MATCH (r:RelationshipDef {id: $owner_id})-[:HAS_PROPERTY]->(n:TBox:PropertyDef) RETURN n.name, n.datatype, n.description, n.metadata"
            params = {"owner_id": owner_relationship}
        else:
            query = "MATCH (n:TBox:PropertyDef) RETURN n.name, n.datatype, n.description, n.metadata"
            params = {}

        rows = self._query(query, params)
        properties = [
            PropertyDef(
                name=row[0],
                datatype=row[1],
                description=row[2],
                metadata=self._parse_json(row[3])
            )
            for row in rows
        ]
        return sorted(properties, key=lambda value: value.name)

    # ------------------------------------------------------------------
    # Property attachment
    # ------------------------------------------------------------------
    def _attach_property(
        self,
        *,
        owner_kind: OwnerKind,
        owner_id: str,
        property_name: str,
        required: bool = False,
        unique: bool = False,
        nullable: bool = True,
        default: Any | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> PropertyBinding:
        self._require_owner(owner_kind, owner_id)
        self._require_property(property_name)

        meta_str = self._json(metadata or {})
        
        owner_label = "ClassDef" if owner_kind == "class" else ("InterfaceDef" if owner_kind == "interface" else "RelationshipDef")
        owner_key = "name" if owner_kind in ("class", "interface") else "id"

        self._query(
            f"""
            MATCH (owner:{owner_label} {{{owner_key}: $owner_id}})
            MATCH (p:PropertyDef {{name: $property_name}})
            MERGE (owner)-[edge:HAS_PROPERTY]->(p)
            SET edge.required = $required,
                edge.unique = $unique,
                edge.nullable = $nullable,
                edge.defaultValue = $default,
                edge.description = $description,
                edge.metadata = $metadata
            """,
            {
                "owner_id": owner_id,
                "property_name": property_name,
                "required": required,
                "unique": unique,
                "nullable": nullable,
                "default": default,
                "description": description if (description := (metadata or {}).get("description")) else None,
                "metadata": meta_str
            }
        )

        return PropertyBinding(
            owner_kind=owner_kind,
            owner_id=owner_id,
            property_name=property_name,
            required=required,
            unique=unique,
            nullable=nullable,
            default=default,
            metadata=metadata or {},
        )

    def attach_property_to_class(
        self,
        *,
        class_name: str,
        property_name: str,
        required: bool = False,
        unique: bool = False,
        nullable: bool = True,
        default: Any | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> PropertyBinding:
        return self._attach_property(
            owner_kind="class",
            owner_id=class_name,
            property_name=property_name,
            required=required,
            unique=unique,
            nullable=nullable,
            default=default,
            metadata=metadata,
        )

    def attach_property_to_interface(
        self,
        *,
        interface_name: str,
        property_name: str,
        required: bool = False,
        unique: bool = False,
        nullable: bool = True,
        default: Any | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> PropertyBinding:
        return self._attach_property(
            owner_kind="interface",
            owner_id=interface_name,
            property_name=property_name,
            required=required,
            unique=unique,
            nullable=nullable,
            default=default,
            metadata=metadata,
        )

    def attach_property_to_relationship(
        self,
        *,
        relationship_id: str,
        property_name: str,
        required: bool = False,
        unique: bool = False,
        nullable: bool = True,
        default: Any | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> PropertyBinding:
        return self._attach_property(
            owner_kind="relationship",
            owner_id=relationship_id,
            property_name=property_name,
            required=required,
            unique=unique,
            nullable=nullable,
            default=default,
            metadata=metadata,
        )

    def detach_property_from_class(self, *, class_name: str, property_name: str) -> None:
        self._require_class(class_name)
        self._query(
            """
            MATCH (c:ClassDef {name: $class_name})-[r:HAS_PROPERTY]->(p:PropertyDef {name: $property_name})
            DELETE r
            """,
            {"class_name": class_name, "property_name": property_name}
        )

    def detach_property_from_interface(
        self, *, interface_name: str, property_name: str
    ) -> None:
        self._require_interface(interface_name)
        self._query(
            """
            MATCH (i:InterfaceDef {name: $interface_name})-[r:HAS_PROPERTY]->(p:PropertyDef {name: $property_name})
            DELETE r
            """,
            {"interface_name": interface_name, "property_name": property_name}
        )

    def detach_property_from_relationship(
        self, *, relationship_id: str, property_name: str
    ) -> None:
        self._require_relationship(relationship_id)
        self._query(
            """
            MATCH (rel:RelationshipDef {id: $relationship_id})-[r:HAS_PROPERTY]->(p:PropertyDef {name: $property_name})
            DELETE r
            """,
            {"relationship_id": relationship_id, "property_name": property_name}
        )

    def _get_bindings(self, owner_kind: OwnerKind, owner_id: str) -> list[PropertyBinding]:
        owner_label = "ClassDef" if owner_kind == "class" else ("InterfaceDef" if owner_kind == "interface" else "RelationshipDef")
        owner_key = "name" if owner_kind in ("class", "interface") else "id"

        rows = self._query(
            f"""
            MATCH (owner:{owner_label} {{{owner_key}: $owner_id}})-[edge:HAS_PROPERTY]->(p:PropertyDef)
            RETURN p.name, edge.required, edge.unique, edge.nullable, edge.defaultValue, edge.metadata
            """,
            {"owner_id": owner_id}
        )
        return [
            PropertyBinding(
                owner_kind=owner_kind,
                owner_id=owner_id,
                property_name=row[0],
                required=bool(row[1]),
                unique=bool(row[2]),
                nullable=bool(row[3]),
                default=row[4],
                metadata=self._parse_json(row[5])
            )
            for row in rows
        ]

    def get_properties_of_class(
        self, class_name: str, *, include_interfaces: bool = True
    ) -> list[EffectivePropertyDef]:
        self._require_class(class_name)
        sources: list[EffectivePropertyDef] = []
        
        # Interface properties
        if include_interfaces:
            iface_rows = self._query(
                "MATCH (c:ClassDef {name: $name})-[:IMPLEMENTS]->(i:InterfaceDef) RETURN i.name",
                {"name": class_name}
            )
            for row in iface_rows:
                iface_name = row[0]
                bindings = self._get_bindings("interface", iface_name)
                for binding in bindings:
                    sources.append(
                        EffectivePropertyDef(
                            property=self._require_property(binding.property_name),
                            binding=binding,
                            source_kind="interface",
                            source_id=iface_name
                        )
                    )

        # Direct properties
        direct_bindings = self._get_bindings("class", class_name)
        for binding in direct_bindings:
            sources.append(
                EffectivePropertyDef(
                    property=self._require_property(binding.property_name),
                    binding=binding,
                    source_kind="class",
                    source_id=class_name
                )
            )

        # Merge duplicates (interface override logic matching memory.py)
        grouped: dict[str, list[EffectivePropertyDef]] = {}
        for source in sources:
            grouped.setdefault(source.property.name, []).append(source)

        merged: list[EffectivePropertyDef] = []
        for prop_name in sorted(grouped):
            values = grouped[prop_name]
            if len(values) == 1:
                merged.append(values[0])
                continue

            defaults = [val.binding.default for val in values if val.binding.default is not None]
            default = defaults[0] if defaults else None
            metadata: dict[str, Any] = {}
            for val in values:
                metadata.update(val.binding.metadata)

            binding = PropertyBinding(
                owner_kind="class",
                owner_id=class_name,
                property_name=prop_name,
                required=any(val.binding.required for val in values),
                unique=any(val.binding.unique for val in values),
                nullable=all(val.binding.nullable for val in values),
                default=default,
                metadata=metadata,
            )
            direct_source = next((val for val in values if val.source_kind == "class"), None)
            source = direct_source or values[0]
            merged.append(
                EffectivePropertyDef(
                    property=source.property,
                    binding=binding,
                    source_kind=source.source_kind,
                    source_id=source.source_id,
                )
            )
        return merged

    def get_properties_of_interface(self, interface_name: str) -> list[EffectivePropertyDef]:
        self._require_interface(interface_name)
        bindings = self._get_bindings("interface", interface_name)
        return [
            EffectivePropertyDef(
                property=self._require_property(b.property_name),
                binding=b,
                source_kind="interface",
                source_id=interface_name
            )
            for b in sorted(bindings, key=lambda val: val.property_name)
        ]

    def get_properties_of_relationship(
        self, relationship_id: str
    ) -> list[EffectivePropertyDef]:
        self._require_relationship(relationship_id)
        bindings = self._get_bindings("relationship", relationship_id)
        return [
            EffectivePropertyDef(
                property=self._require_property(b.property_name),
                binding=b,
                source_kind="relationship",
                source_id=relationship_id
            )
            for b in sorted(bindings, key=lambda val: val.property_name)
        ]

    # ------------------------------------------------------------------
    # Relationship
    # ------------------------------------------------------------------
    def define_relationship(
        self,
        *,
        id: str | None = None,
        name: str,
        from_class: str,
        to_class: str,
        min_count: int = 0,
        max_count: int | None = None,
        required: bool = False,
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
        merge: bool = True,
    ) -> RelationshipDef:
        if id is None:
            id = f"rel_{from_class.lower()}_{name.lower()}_{to_class.lower()}"

        self._require_class(from_class)
        self._require_class(to_class)

        # Check semantic duplicate (same from, name, to but different ID)
        dup_rows = self._query(
            """
            MATCH (r:TBox:RelationshipDef)
            WHERE r.from_class = $from_class
              AND r.name = $name
              AND r.to_class = $to_class
              AND r.id <> $id
            RETURN r.id
            """,
            {"from_class": from_class, "name": name, "to_class": to_class, "id": id}
        )
        if dup_rows:
            raise TBoxConflictError(
                f"Relationship semantic key already exists: ({from_class}, {name}, {to_class}) as {dup_rows[0][0]}"
            )

        existing = self.get_relationship(id)
        if existing:
            if not merge:
                raise TBoxAlreadyExistsError(f"RelationshipDef already exists: {id}")
            return self.update_relationship(
                id,
                name=name,
                min_count=min_count,
                max_count=max_count,
                required=required,
                description=description,
                metadata=metadata
            )

        uuid = self._stable_uuid("RelationshipDef", id)
        meta_str = self._json(metadata or {})
        
        # In FalkorTBox, we represent RelationshipDef as a node and link it to endpoints
        self._query(
            """
            CREATE (r:TBox:RelationshipDef {
                id: $id,
                uuid: $uuid,
                name: $name,
                from_class: $from_class,
                to_class: $to_class,
                description: $description,
                metadata: $metadata
            })
            """,
            {
                "id": id,
                "uuid": uuid,
                "name": name,
                "from_class": from_class,
                "to_class": to_class,
                "description": description,
                "metadata": meta_str
            }
        )
        
        # Create FROM_CLASS / TO_CLASS link for verification / path traversing
        self._query(
            """
            MATCH (r:RelationshipDef {id: $id})
            MATCH (from:ClassDef {name: $from_class})
            MATCH (to:ClassDef {name: $to_class})
            MERGE (r)-[f:FROM_CLASS]->(from)
            SET f.minCount = $min_count,
                f.maxCount = $max_count,
                f.required = $required
            MERGE (r)-[:TO_CLASS]->(to)
            """,
            {
                "id": id,
                "from_class": from_class,
                "to_class": to_class,
                "min_count": min_count,
                "max_count": max_count,
                "required": required
            }
        )

        return RelationshipDef(
            id=id,
            name=name,
            from_class=from_class,
            to_class=to_class,
            min_count=min_count,
            max_count=max_count,
            required=required,
            description=description,
            metadata=metadata or {}
        )

    def get_relationship(self, id: str) -> RelationshipDef | None:
        rows = self._query(
            """
            MATCH (r:TBox:RelationshipDef {id: $id})
            MATCH (r)-[f:FROM_CLASS]->(from:ClassDef)
            MATCH (r)-[:TO_CLASS]->(to:ClassDef)
            RETURN r.id, r.name, from.name, to.name, f.minCount, f.maxCount, f.required, r.description, r.metadata
            """,
            {"id": id}
        )
        if not rows:
            return None
        row = rows[0]
        return RelationshipDef(
            id=row[0],
            name=row[1],
            from_class=row[2],
            to_class=row[3],
            min_count=int(row[4] or 0),
            max_count=None if row[5] is None else int(row[5]),
            required=bool(row[6]),
            description=row[7],
            metadata=self._parse_json(row[8])
        )

    def update_relationship(
        self,
        id: str,
        *,
        name: str | None = None,
        min_count: int | None = None,
        max_count: int | None = None,
        required: bool | None = None,
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> RelationshipDef:
        existing = self._require_relationship(id)
        new_name = name if name is not None else existing.name

        # Semantic duplication check
        dup_rows = self._query(
            """
            MATCH (r:TBox:RelationshipDef)
            WHERE r.from_class = $from_class
              AND r.name = $name
              AND r.to_class = $to_class
              AND r.id <> $id
            RETURN r.id
            """,
            {"from_class": existing.from_class, "name": new_name, "to_class": existing.to_class, "id": id}
        )
        if dup_rows:
            raise TBoxConflictError(
                f"Relationship semantic key already exists: ({existing.from_class}, {new_name}, {existing.to_class}) as {dup_rows[0][0]}"
            )

        new_min_count = min_count if min_count is not None else existing.min_count
        new_max_count = max_count if max_count is not None else existing.max_count
        new_required = required if required is not None else existing.required
        new_description = description if description is not None else existing.description

        merged_metadata = dict(existing.metadata)
        if metadata:
            merged_metadata.update(metadata)
        meta_str = self._json(merged_metadata)

        self._query(
            """
            MATCH (r:TBox:RelationshipDef {id: $id})
            SET r.name = $name,
                r.description = $description,
                r.metadata = $metadata
            """,
            {"id": id, "name": new_name, "description": new_description, "metadata": meta_str}
        )

        self._query(
            """
            MATCH (r:RelationshipDef {id: $id})-[f:FROM_CLASS]->()
            SET f.minCount = $min_count,
                f.maxCount = $max_count,
                f.required = $required
            """,
            {"id": id, "min_count": new_min_count, "max_count": new_max_count, "required": new_required}
        )

        return RelationshipDef(
            id=id,
            name=new_name,
            from_class=existing.from_class,
            to_class=existing.to_class,
            min_count=new_min_count,
            max_count=new_max_count,
            required=new_required,
            description=new_description,
            metadata=merged_metadata
        )

    def move_relationship(
        self, id: str, *, from_class: str, to_class: str
    ) -> RelationshipDef:
        existing = self._require_relationship(id)
        self._require_class(from_class)
        self._require_class(to_class)

        # Semantic duplication check
        dup_rows = self._query(
            """
            MATCH (r:TBox:RelationshipDef)
            WHERE r.from_class = $from_class
              AND r.name = $name
              AND r.to_class = $to_class
              AND r.id <> $id
            RETURN r.id
            """,
            {"from_class": from_class, "name": existing.name, "to_class": to_class, "id": id}
        )
        if dup_rows:
            raise TBoxConflictError(
                f"Relationship semantic key already exists: ({from_class}, {existing.name}, {to_class}) as {dup_rows[0][0]}"
            )

        self._query(
            """
            MATCH (r:TBox:RelationshipDef {id: $id})
            SET r.from_class = $from_class,
                r.to_class = $to_class
            """,
            {"id": id, "from_class": from_class, "to_class": to_class}
        )

        # Recreate endpoint links
        self._query("MATCH (r:RelationshipDef {id: $id})-[edge:FROM_CLASS]->() DELETE edge", {"id": id})
        self._query("MATCH (r:RelationshipDef {id: $id})-[edge:TO_CLASS]->() DELETE edge", {"id": id})
        
        self._query(
            """
            MATCH (r:RelationshipDef {id: $id})
            MATCH (from:ClassDef {name: $from_class})
            MATCH (to:ClassDef {name: $to_class})
            MERGE (r)-[f:FROM_CLASS]->(from)
            SET f.minCount = $min_count,
                f.maxCount = $max_count,
                f.required = $required
            MERGE (r)-[:TO_CLASS]->(to)
            """,
            {
                "id": id,
                "from_class": from_class,
                "to_class": to_class,
                "min_count": existing.min_count,
                "max_count": existing.max_count,
                "required": existing.required
            }
        )

        return RelationshipDef(
            id=id,
            name=existing.name,
            from_class=from_class,
            to_class=to_class,
            min_count=existing.min_count,
            max_count=existing.max_count,
            required=existing.required,
            description=existing.description,
            metadata=dict(existing.metadata)
        )

    def delete_relationship(self, id: str, *, detach: bool = False) -> None:
        self._require_relationship(id)
        has_ref = False

        rows = self._query("MATCH (r:RelationshipDef {id: $id})-[:HAS_PROPERTY]->() RETURN count(r)", {"id": id})
        if rows and int(rows[0][0]) > 0:
            has_ref = True

        if has_ref and not detach:
            raise TBoxConflictError(f"RelationshipDef has references: {id}")

        if detach:
            self._query("MATCH (r:RelationshipDef {id: $id})-[edge:HAS_PROPERTY]->() DELETE edge", {"id": id})

        # Remove FROM_CLASS / TO_CLASS links
        self._query("MATCH (r:RelationshipDef {id: $id})-[edge:FROM_CLASS]->() DELETE edge", {"id": id})
        self._query("MATCH (r:RelationshipDef {id: $id})-[edge:TO_CLASS]->() DELETE edge", {"id": id})
        self._query("MATCH (r:TBox:RelationshipDef {id: $id}) DELETE r", {"id": id})

    def list_relationships(
        self,
        *,
        from_class: str | None = None,
        to_class: str | None = None,
        name: str | None = None,
    ) -> list[RelationshipDef]:
        query_parts = [
            """
            MATCH (r:TBox:RelationshipDef)
            MATCH (r)-[f:FROM_CLASS]->(from:ClassDef)
            MATCH (r)-[:TO_CLASS]->(to:ClassDef)
            """
        ]
        conditions = []
        params = {}
        
        if from_class is not None:
            conditions.append("from.name = $from_class")
            params["from_class"] = from_class
        if to_class is not None:
            conditions.append("to.name = $to_class")
            params["to_class"] = to_class
        if name is not None:
            conditions.append("r.name = $name")
            params["name"] = name
            
        if conditions:
            query_parts.append("WHERE " + " AND ".join(conditions))
            
        query_parts.append("RETURN r.id, r.name, from.name, to.name, f.minCount, f.maxCount, f.required, r.description, r.metadata")
        
        rows = self._query(" ".join(query_parts), params)
        relationships = [
            RelationshipDef(
                id=row[0],
                name=row[1],
                from_class=row[2],
                to_class=row[3],
                min_count=int(row[4] or 0),
                max_count=None if row[5] is None else int(row[5]),
                required=bool(row[6]),
                description=row[7],
                metadata=self._parse_json(row[8])
            )
            for row in rows
        ]
        return sorted(relationships, key=lambda value: value.id)

    def is_relationship_allowed(
        self, *, from_class: str, relationship_name: str, to_class: str
    ) -> bool:
        rows = self._query(
            """
            MATCH (r:TBox:RelationshipDef)
            MATCH (r)-[:FROM_CLASS]->(from:ClassDef {name: $from_class})
            MATCH (r)-[:TO_CLASS]->(to:ClassDef {name: $to_class})
            WHERE r.name = $relationship_name
            RETURN count(r)
            """,
            {"from_class": from_class, "relationship_name": relationship_name, "to_class": to_class}
        )
        return bool(rows and int(rows[0][0]) > 0)

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

    # ------------------------------------------------------------------
    # Connector
    # ------------------------------------------------------------------
    def define_connector(
        self,
        name: str,
        *,
        kind: Literal["mysql", "postgres"] = "postgres",
        dsn_ref: str = "",
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
        merge: bool = True,
    ) -> ConnectorDef:
        existing = self.get_connector(name)
        if existing:
            if not merge:
                raise TBoxAlreadyExistsError(f"ConnectorDef already exists: {name}")
            new_dsn_ref = dsn_ref if dsn_ref else existing.dsn_ref
            new_description = description if description is not None else existing.description
            merged_metadata = dict(existing.metadata)
            if metadata:
                merged_metadata.update(metadata)
            self._query(
                """
                MATCH (n:TBox:ConnectorDef {name: $name})
                SET n.kind = $kind,
                    n.dsnRef = $dsn_ref,
                    n.description = $description,
                    n.metadata = $metadata
                """,
                {
                    "name": name,
                    "kind": kind,
                    "dsn_ref": new_dsn_ref,
                    "description": new_description,
                    "metadata": self._json(merged_metadata),
                },
            )
            return ConnectorDef(
                name=name,
                kind=kind,
                dsn_ref=new_dsn_ref,
                description=new_description,
                metadata=merged_metadata,
            )

        uuid = self._stable_uuid("ConnectorDef", name)
        self._query(
            """
            CREATE (n:TBox:ConnectorDef {
                name: $name,
                uuid: $uuid,
                kind: $kind,
                dsnRef: $dsn_ref,
                description: $description,
                metadata: $metadata
            })
            """,
            {
                "name": name,
                "uuid": uuid,
                "kind": kind,
                "dsn_ref": dsn_ref,
                "description": description,
                "metadata": self._json(metadata or {}),
            },
        )
        return ConnectorDef(
            name=name,
            kind=kind,
            dsn_ref=dsn_ref,
            description=description,
            metadata=metadata or {},
        )

    def get_connector(self, name: str) -> ConnectorDef | None:
        rows = self._query(
            "MATCH (n:TBox:ConnectorDef {name: $name}) RETURN n.name, n.kind, n.dsnRef, n.description, n.metadata",
            {"name": name},
        )
        if not rows:
            return None
        row = rows[0]
        return ConnectorDef(
            name=row[0],
            kind=row[1],
            dsn_ref=row[2] or "",
            description=row[3],
            metadata=self._parse_json(row[4]),
        )

    def list_connectors(self) -> list[ConnectorDef]:
        rows = self._query(
            "MATCH (n:TBox:ConnectorDef) RETURN n.name, n.kind, n.dsnRef, n.description, n.metadata"
        )
        connectors = [
            ConnectorDef(
                name=row[0],
                kind=row[1],
                dsn_ref=row[2] or "",
                description=row[3],
                metadata=self._parse_json(row[4]),
            )
            for row in rows
        ]
        return sorted(connectors, key=lambda value: value.name)

    def delete_connector(self, name: str, *, detach: bool = False) -> None:
        self._require_connector(name)
        binding_rows = self._query(
            "MATCH (:ClassDef)-[e:HAS_CONNECTOR]->(k:ConnectorDef {name: $name}) RETURN count(e)",
            {"name": name},
        )
        metric_rows = self._query(
            "MATCH (m:MetricDef)-[:USES_CONNECTOR]->(k:ConnectorDef {name: $name}) RETURN count(m)",
            {"name": name},
        )
        has_binding = bool(binding_rows and int(binding_rows[0][0]) > 0)
        has_metric = bool(metric_rows and int(metric_rows[0][0]) > 0)
        if (has_binding or has_metric) and not detach:
            raise TBoxConflictError(
                f"ConnectorDef is in use (source bindings or metrics): {name}"
            )
        # Edges must go before the node delete regardless of detach, else FalkorDB
        # refuses to delete a node that still has relationships. Metric nodes are
        # removed outright (a metric without its connector cannot resolve).
        self._query(
            "MATCH (:ClassDef)-[e:HAS_CONNECTOR]->(k:ConnectorDef {name: $name}) DELETE e",
            {"name": name},
        )
        self._query(
            "MATCH (m:MetricDef)-[:USES_CONNECTOR]->(k:ConnectorDef {name: $name}) DETACH DELETE m",
            {"name": name},
        )
        self._query("MATCH (k:TBox:ConnectorDef {name: $name}) DELETE k", {"name": name})

    # ------------------------------------------------------------------
    # Source binding (class <- RDB query)
    # ------------------------------------------------------------------
    def attach_source_binding_to_class(
        self,
        *,
        class_name: str,
        connector_name: str,
        sql: str,
        key_columns: tuple[str, ...],
        column_map: dict[str, str] | None = None,
        materialization: Literal["materialized", "virtual"] = "materialized",
        refresh_interval_hours: int | None = None,
        links: tuple[SourceLink, ...] = (),
    ) -> SourceBinding:
        self._require_class(class_name)
        self._require_connector(connector_name)
        if not key_columns:
            raise TBoxConflictError(
                f"SourceBinding requires at least one key column: {class_name}"
            )
        normalized_links = self._parse_links(self._links_to_json(tuple(links)))
        # A class carries at most one source binding; clear any prior edge first so a
        # connector change doesn't leave two HAS_CONNECTOR edges behind.
        self._query(
            "MATCH (c:ClassDef {name: $class_name})-[e:HAS_CONNECTOR]->() DELETE e",
            {"class_name": class_name},
        )
        self._query(
            """
            MATCH (c:TBox:ClassDef {name: $class_name})
            MATCH (k:TBox:ConnectorDef {name: $connector_name})
            MERGE (c)-[e:HAS_CONNECTOR]->(k)
            SET e.sql = $sql,
                e.keyColumns = $key_columns,
                e.columnMap = $column_map,
                e.materialization = $materialization,
                e.refreshIntervalHours = $refresh_interval_hours,
                e.links = $links
            """,
            {
                "class_name": class_name,
                "connector_name": connector_name,
                "sql": sql,
                "key_columns": list(key_columns),
                "column_map": self._json(column_map or {}),
                "materialization": materialization,
                "refresh_interval_hours": refresh_interval_hours,
                "links": self._links_to_json(normalized_links),
            },
        )
        return SourceBinding(
            class_name=class_name,
            connector_name=connector_name,
            sql=sql,
            key_columns=tuple(key_columns),
            column_map=dict(column_map or {}),
            materialization=materialization,
            refresh_interval_hours=refresh_interval_hours,
            links=normalized_links,
        )

    def get_source_binding(self, class_name: str) -> SourceBinding | None:
        rows = self._query(
            """
            MATCH (c:TBox:ClassDef {name: $class_name})-[e:HAS_CONNECTOR]->(k:TBox:ConnectorDef)
            RETURN k.name, e.sql, e.keyColumns, e.columnMap, e.materialization, e.refreshIntervalHours, e.links
            """,
            {"class_name": class_name},
        )
        if not rows:
            return None
        row = rows[0]
        return SourceBinding(
            class_name=class_name,
            connector_name=row[0],
            sql=row[1],
            key_columns=tuple(row[2] or []),
            column_map=self._parse_json(row[3]),
            materialization=row[4] or "materialized",
            refresh_interval_hours=row[5],
            links=self._parse_links(row[6]),
        )

    def detach_source_binding_from_class(self, class_name: str) -> None:
        self._require_class(class_name)
        self._query(
            "MATCH (c:ClassDef {name: $class_name})-[e:HAS_CONNECTOR]->() DELETE e",
            {"class_name": class_name},
        )

    def list_source_bindings(self) -> list[SourceBinding]:
        rows = self._query(
            """
            MATCH (c:TBox:ClassDef)-[e:HAS_CONNECTOR]->(k:TBox:ConnectorDef)
            RETURN c.name, k.name, e.sql, e.keyColumns, e.columnMap, e.materialization, e.refreshIntervalHours, e.links
            """
        )
        bindings = [
            SourceBinding(
                class_name=row[0],
                connector_name=row[1],
                sql=row[2],
                key_columns=tuple(row[3] or []),
                column_map=self._parse_json(row[4]),
                materialization=row[5] or "materialized",
                refresh_interval_hours=row[6],
                links=self._parse_links(row[7]),
            )
            for row in rows
        ]
        return sorted(bindings, key=lambda value: value.class_name)

    # ------------------------------------------------------------------
    # Metrics (class <- named parameterized RDB query, resolved on demand)
    # ------------------------------------------------------------------
    def define_metric(self, metric: MetricDef, *, merge: bool = True) -> MetricDef:
        """Attach (or update) a named parameterized query to a class. Stores only the
        query spec — the connector, SQL and param map — never any fetched value."""
        self._require_class(metric.class_name)
        self._require_connector(metric.connector_name)
        if not merge and self.get_metric(metric.name) is not None:
            raise TBoxAlreadyExistsError(f"MetricDef already exists: {metric.name}")
        uuid = self._stable_uuid("MetricDef", metric.name)
        self._query(
            """
            MATCH (c:TBox:ClassDef {name: $class_name})
            MATCH (k:TBox:ConnectorDef {name: $connector_name})
            MERGE (m:TBox:MetricDef {name: $name})
            SET m.uuid = coalesce(m.uuid, $uuid),
                m.className = $class_name,
                m.connectorName = $connector_name,
                m.sql = $sql,
                m.paramMap = $param_map,
                m.resultKind = $result_kind,
                m.valueColumn = $value_column,
                m.ttlSeconds = $ttl_seconds,
                m.description = $description
            MERGE (c)-[:HAS_METRIC]->(m)
            MERGE (m)-[:USES_CONNECTOR]->(k)
            """,
            {
                "name": metric.name,
                "uuid": uuid,
                "class_name": metric.class_name,
                "connector_name": metric.connector_name,
                "sql": metric.sql,
                "param_map": self._json(metric.param_map),
                "result_kind": metric.result_kind,
                "value_column": metric.value_column,
                "ttl_seconds": metric.ttl_seconds,
                "description": metric.description,
            },
        )
        return metric

    @staticmethod
    def _row_to_metric(row: list[Any]) -> MetricDef:
        return MetricDef(
            name=row[0],
            class_name=row[1],
            connector_name=row[2],
            sql=row[3],
            param_map=FalkorTBoxRepository._parse_json(row[4]),
            result_kind=row[5] or "scalar",
            value_column=row[6] or "value",
            ttl_seconds=row[7],
            description=row[8],
        )

    _METRIC_RETURN = (
        "m.name, m.className, m.connectorName, m.sql, m.paramMap, "
        "m.resultKind, m.valueColumn, m.ttlSeconds, m.description"
    )

    def get_metric(self, name: str) -> MetricDef | None:
        rows = self._query(
            f"MATCH (m:TBox:MetricDef {{name: $name}}) RETURN {self._METRIC_RETURN}",
            {"name": name},
        )
        return self._row_to_metric(rows[0]) if rows else None

    def list_metrics(self, class_name: str | None = None) -> list[MetricDef]:
        if class_name is not None:
            rows = self._query(
                f"MATCH (m:TBox:MetricDef {{className: $class_name}}) RETURN {self._METRIC_RETURN}",
                {"class_name": class_name},
            )
        else:
            rows = self._query(f"MATCH (m:TBox:MetricDef) RETURN {self._METRIC_RETURN}")
        metrics = [self._row_to_metric(row) for row in rows]
        return sorted(metrics, key=lambda value: value.name)

    def delete_metric(self, name: str) -> None:
        self._require_metric(name)
        self._query("MATCH (m:TBox:MetricDef {name: $name}) DETACH DELETE m", {"name": name})

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
