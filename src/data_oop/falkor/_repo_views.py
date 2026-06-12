from __future__ import annotations

import json
from typing import Any

from data_oop.exceptions import TBoxAlreadyExistsError
from data_oop.schema.models import (
    ViewDef,
    ViewParam,
)
from data_oop.falkor._repo_base import _RepositoryBase


class _ViewMixin(_RepositoryBase):
    # ------------------------------------------------------------------
    # Views (class <- named parameterized RDB query, resolved on demand to a table)
    # ------------------------------------------------------------------
    def define_view(self, view: ViewDef, *, merge: bool = True) -> ViewDef:
        """Attach (or update) a named parameterized query to a class. Stores only the
        query spec — the connector, SQL, accepted filter params and cache TTL — never
        any fetched value."""
        self._require_class(view.class_name)
        self._require_connector(view.connector_name)
        if not merge and self.get_view(view.name) is not None:
            raise TBoxAlreadyExistsError(f"ViewDef already exists: {view.name}")
        uuid = self._stable_uuid("ViewDef", view.name)
        self._query(
            """
            MATCH (c:TBox:ClassDef {name: $class_name})
            MATCH (k:TBox:ConnectorDef {name: $connector_name})
            MERGE (v:TBox:ViewDef {name: $name})
            SET v.uuid = coalesce(v.uuid, $uuid),
                v.className = $class_name,
                v.connectorName = $connector_name,
                v.sql = $sql,
                v.params = $params,
                v.keyColumn = $key_column,
                v.ttlSeconds = $ttl_seconds,
                v.description = $description
            MERGE (c)-[:HAS_VIEW]->(v)
            MERGE (v)-[:USES_CONNECTOR]->(k)
            """,
            {
                "name": view.name,
                "uuid": uuid,
                "class_name": view.class_name,
                "connector_name": view.connector_name,
                "sql": view.sql,
                "params": self._json([{"name": p.name, "required": p.required} for p in view.params]),
                "key_column": view.key_column,
                "ttl_seconds": view.ttl_seconds,
                "description": view.description,
            },
        )
        return view

    @staticmethod
    def _row_to_view(row: list[Any]) -> ViewDef:
        raw = row[4]
        if isinstance(raw, str):
            try:
                raw_params = json.loads(raw)
            except json.JSONDecodeError:
                raw_params = []
        elif isinstance(raw, list):
            raw_params = raw
        else:
            raw_params = []
        params = tuple(
            ViewParam(name=p["name"], required=bool(p.get("required", False)))
            for p in raw_params
            if isinstance(p, dict) and p.get("name")
        )
        return ViewDef(
            name=row[0],
            class_name=row[1],
            connector_name=row[2],
            sql=row[3],
            params=params,
            key_column=row[5],
            ttl_seconds=row[6],
            description=row[7],
        )

    _VIEW_RETURN = (
        "v.name, v.className, v.connectorName, v.sql, v.params, "
        "v.keyColumn, v.ttlSeconds, v.description"
    )

    def get_view(self, name: str) -> ViewDef | None:
        rows = self._query(
            f"MATCH (v:TBox:ViewDef {{name: $name}}) RETURN {self._VIEW_RETURN}",
            {"name": name},
        )
        return self._row_to_view(rows[0]) if rows else None

    def list_views(self, class_name: str | None = None) -> list[ViewDef]:
        if class_name is not None:
            rows = self._query(
                f"MATCH (v:TBox:ViewDef {{className: $class_name}}) RETURN {self._VIEW_RETURN}",
                {"class_name": class_name},
            )
        else:
            rows = self._query(f"MATCH (v:TBox:ViewDef) RETURN {self._VIEW_RETURN}")
        views = [self._row_to_view(row) for row in rows]
        return sorted(views, key=lambda value: value.name)

    def delete_view(self, name: str) -> None:
        self._require_view(name)
        self._query("MATCH (v:TBox:ViewDef {name: $name}) DETACH DELETE v", {"name": name})

