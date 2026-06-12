from __future__ import annotations

from typing import Any, Literal

from data_oop.exceptions import TBoxAlreadyExistsError, TBoxConflictError
from data_oop.schema.models import (
    ConnectorDef,
    ConnectorKind,
    SourceBinding,
    SourceLink,
)
from data_oop.falkor._repo_base import _RepositoryBase


class _ConnectorMixin(_RepositoryBase):
    # ------------------------------------------------------------------
    # Connector
    # ------------------------------------------------------------------
    def define_connector(
        self,
        name: str,
        *,
        kind: ConnectorKind = "postgres",
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
        view_rows = self._query(
            "MATCH (v:ViewDef)-[:USES_CONNECTOR]->(k:ConnectorDef {name: $name}) RETURN count(v)",
            {"name": name},
        )
        has_binding = bool(binding_rows and int(binding_rows[0][0]) > 0)
        has_view = bool(view_rows and int(view_rows[0][0]) > 0)
        if (has_binding or has_view) and not detach:
            raise TBoxConflictError(
                f"ConnectorDef is in use (source bindings or views): {name}"
            )
        # Edges must go before the node delete regardless of detach, else FalkorDB
        # refuses to delete a node that still has relationships. View nodes are
        # removed outright (a view without its connector cannot resolve).
        self._query(
            "MATCH (:ClassDef)-[e:HAS_CONNECTOR]->(k:ConnectorDef {name: $name}) DELETE e",
            {"name": name},
        )
        self._query(
            "MATCH (v:ViewDef)-[:USES_CONNECTOR]->(k:ConnectorDef {name: $name}) DETACH DELETE v",
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

