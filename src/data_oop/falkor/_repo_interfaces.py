from __future__ import annotations

from typing import Any

from data_oop.exceptions import TBoxAlreadyExistsError, TBoxConflictError
from data_oop.schema.models import (
    ClassDef,
    InterfaceDef,
)
from data_oop.falkor._repo_base import _RepositoryBase


class _InterfaceMixin(_RepositoryBase):
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

