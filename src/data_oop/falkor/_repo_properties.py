from __future__ import annotations

from typing import Any

from data_oop.exceptions import TBoxAlreadyExistsError, TBoxConflictError
from data_oop.schema.models import (
    EffectivePropertyDef,
    OwnerKind,
    PropertyBinding,
    PropertyDef,
)
from data_oop.schema.effective import merge_effective_properties
from data_oop.falkor._repo_base import _RepositoryBase


class _PropertyMixin(_RepositoryBase):
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

        # The class itself comes first, then its SUBCLASS_OF ancestors, so the
        # merge's first-non-null default and direct-binding source attribution
        # favor the class's own bindings over inherited ones. Each owner
        # contributes its interface bindings and its direct bindings.
        lineage = [c.name for c in self.get_superclasses(class_name)]
        for owner_name in (class_name, *lineage):
            if include_interfaces:
                iface_rows = self._query(
                    "MATCH (c:ClassDef {name: $name})-[:IMPLEMENTS]->(i:InterfaceDef) RETURN i.name",
                    {"name": owner_name}
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

            direct_bindings = self._get_bindings("class", owner_name)
            for binding in direct_bindings:
                sources.append(
                    EffectivePropertyDef(
                        property=self._require_property(binding.property_name),
                        binding=binding,
                        source_kind="class",
                        source_id=owner_name
                    )
                )

        # Collapse own + inherited sources with the shared precedence rules.
        return merge_effective_properties("class", class_name, sources)

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

