from __future__ import annotations

from typing import Any

from data_oop.exceptions import TBoxAlreadyExistsError, TBoxConflictError
from data_oop.schema.models import (
    ClassDef,
)
from data_oop.falkor._repo_base import _RepositoryBase


class _ClassMixin(_RepositoryBase):
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

        # 4. Check subclass hierarchy edges (either direction)
        rows = self._query(
            "MATCH (c:ClassDef {name: $name})-[:SUBCLASS_OF]-() RETURN count(c)",
            {"name": name},
        )
        if rows and int(rows[0][0]) > 0:
            has_ref = True

        if has_ref and not detach:
            raise TBoxConflictError(f"ClassDef has references: {name}")

        # Detach/Delete IMPLEMENTS and HAS_PROPERTY relations, delete relationship nodes as well if detaching
        if detach:
            self._query("MATCH (c:ClassDef {name: $name})-[r:IMPLEMENTS]->() DELETE r", {"name": name})
            self._query("MATCH (c:ClassDef {name: $name})-[r:HAS_PROPERTY]->() DELETE r", {"name": name})
            self._query("MATCH (c:ClassDef {name: $name})-[r:SUBCLASS_OF]-() DELETE r", {"name": name})
            
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

    # ------------------------------------------------------------------
    # Subclass hierarchy (SUBCLASS_OF)
    # ------------------------------------------------------------------
    def set_subclass_of(self, *, class_name: str, parent_name: str) -> None:
        """Declare ``class_name`` a subclass of ``parent_name`` (rdfs:subClassOf).

        A class may have multiple parents. Instances of the subclass carry every
        ancestor label in the ABox, and the subclass inherits ancestor property
        bindings, interface bindings, and class-targeted constraints. Raises
        ``TBoxConflictError`` on self-subclassing or a hierarchy cycle.
        """
        self._require_class(class_name)
        self._require_class(parent_name)
        if class_name == parent_name:
            raise TBoxConflictError(f"Class cannot subclass itself: {class_name}")
        ancestors = {c.name for c in self.get_superclasses(parent_name)}
        if class_name in ancestors:
            raise TBoxConflictError(
                f"Subclass cycle: {parent_name} already inherits from {class_name}"
            )
        self._query(
            """
            MATCH (c:TBox:ClassDef {name: $class_name})
            MATCH (p:TBox:ClassDef {name: $parent_name})
            MERGE (c)-[:SUBCLASS_OF]->(p)
            """,
            {"class_name": class_name, "parent_name": parent_name},
        )

    def remove_subclass_of(self, *, class_name: str, parent_name: str) -> None:
        self._require_class(class_name)
        self._require_class(parent_name)
        self._query(
            """
            MATCH (:TBox:ClassDef {name: $class_name})-[r:SUBCLASS_OF]->(:TBox:ClassDef {name: $parent_name})
            DELETE r
            """,
            {"class_name": class_name, "parent_name": parent_name},
        )

    def get_superclasses(self, class_name: str, *, transitive: bool = True) -> list[ClassDef]:
        self._require_class(class_name)
        depth = "1.." if transitive else "1..1"
        rows = self._query(
            f"""
            MATCH (:TBox:ClassDef {{name: $name}})-[:SUBCLASS_OF*{depth}]->(p:TBox:ClassDef)
            RETURN DISTINCT p.name, p.label, p.description, p.metadata
            """,
            {"name": class_name},
        )
        classes = [
            ClassDef(name=row[0], label=row[1], description=row[2], metadata=self._parse_json(row[3]))
            for row in rows
        ]
        return sorted(classes, key=lambda value: value.name)

    def get_subclasses(self, class_name: str, *, transitive: bool = True) -> list[ClassDef]:
        self._require_class(class_name)
        depth = "1.." if transitive else "1..1"
        rows = self._query(
            f"""
            MATCH (c:TBox:ClassDef)-[:SUBCLASS_OF*{depth}]->(:TBox:ClassDef {{name: $name}})
            RETURN DISTINCT c.name, c.label, c.description, c.metadata
            """,
            {"name": class_name},
        )
        classes = [
            ClassDef(name=row[0], label=row[1], description=row[2], metadata=self._parse_json(row[3]))
            for row in rows
        ]
        return sorted(classes, key=lambda value: value.name)

    def is_subclass_of(self, *, class_name: str, parent_name: str) -> bool:
        return any(c.name == parent_name for c in self.get_superclasses(class_name))

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

