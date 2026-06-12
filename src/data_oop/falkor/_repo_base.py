from __future__ import annotations

import json
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from data_oop.exceptions import TBoxNotFoundError
from data_oop.falkor.graph import FalkorGraph
from data_oop.schema.models import (
    ClassDef,
    ConnectorDef,
    ConstraintDef,
    InterfaceDef,
    OwnerKind,
    PropertyDef,
    RelationshipDef,
    SourceLink,
    ViewDef,
)


class _RepositoryBase:
    """Shared FalkorDB query, serialization, and existence-check helpers."""

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

    def _require_view(self, name: str) -> ViewDef:
        view = self.get_view(name)
        if not view:
            raise TBoxNotFoundError(f"ViewDef not found: {name}")
        return view

    def _require_owner(self, owner_kind: OwnerKind, owner_id: str) -> None:
        if owner_kind == "class":
            self._require_class(owner_id)
        elif owner_kind == "interface":
            self._require_interface(owner_id)
        elif owner_kind == "relationship":
            self._require_relationship(owner_id)

