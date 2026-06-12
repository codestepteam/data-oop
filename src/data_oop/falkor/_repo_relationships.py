from __future__ import annotations

from typing import Any

from data_oop.exceptions import TBoxAlreadyExistsError, TBoxConflictError
from data_oop.schema.models import (
    RelationshipDef,
)
from data_oop.falkor._repo_base import _RepositoryBase


class _RelationshipMixin(_RepositoryBase):
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

