from __future__ import annotations

from typing import Any, Literal, Protocol, runtime_checkable

from data_oop.schema.models import (
    ClassDef,
    ConnectorDef,
    ConnectorKind,
    ConstraintDef,
    EffectivePropertyDef,
    InterfaceDef,
    PropertyBinding,
    PropertyDef,
    RelationshipDef,
    SourceBinding,
    SourceLink,
    ViewDef,
)


@runtime_checkable
class TBoxRepository(Protocol):
    # Class
    def create_class(
        self,
        name: str,
        *,
        label: str | None = None,
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
        merge: bool = True,
    ) -> ClassDef: ...

    def get_class(self, name: str) -> ClassDef | None: ...

    def update_class(
        self,
        name: str,
        *,
        label: str | None = None,
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ClassDef: ...

    def delete_class(self, name: str, *, detach: bool = False) -> None: ...

    def list_classes(
        self, *, implements: str | None = None, has_property: str | None = None
    ) -> list[ClassDef]: ...

    # Subclass hierarchy (SUBCLASS_OF)
    def set_subclass_of(self, *, class_name: str, parent_name: str) -> None: ...

    def remove_subclass_of(self, *, class_name: str, parent_name: str) -> None: ...

    def get_superclasses(
        self, class_name: str, *, transitive: bool = True
    ) -> list[ClassDef]: ...

    def get_subclasses(
        self, class_name: str, *, transitive: bool = True
    ) -> list[ClassDef]: ...

    def is_subclass_of(self, *, class_name: str, parent_name: str) -> bool: ...

    # Interface
    def create_interface(
        self,
        name: str,
        *,
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
        merge: bool = True,
    ) -> InterfaceDef: ...

    def get_interface(self, name: str) -> InterfaceDef | None: ...

    def update_interface(
        self,
        name: str,
        *,
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> InterfaceDef: ...

    def delete_interface(self, name: str, *, detach: bool = False) -> None: ...

    def list_interfaces(
        self,
        *,
        implemented_by: str | None = None,
        has_property: str | None = None,
    ) -> list[InterfaceDef]: ...

    # Implements
    def implement_interface(self, *, class_name: str, interface_name: str) -> None: ...

    def remove_interface(self, *, class_name: str, interface_name: str) -> None: ...

    def class_implements(self, *, class_name: str, interface_name: str) -> bool: ...

    def get_interfaces_of_class(self, class_name: str) -> list[InterfaceDef]: ...

    def get_classes_of_interface(self, interface_name: str) -> list[ClassDef]: ...

    # Property
    def create_property(
        self,
        name: str,
        *,
        datatype: str = "unknown",
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
        merge: bool = True,
    ) -> PropertyDef: ...

    def get_property(self, name: str) -> PropertyDef | None: ...

    def update_property(
        self,
        name: str,
        *,
        datatype: str | None = None,
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> PropertyDef: ...

    def delete_property(self, name: str, *, detach: bool = False) -> None: ...

    def list_properties(
        self,
        *,
        owner_class: str | None = None,
        owner_interface: str | None = None,
        owner_relationship: str | None = None,
    ) -> list[PropertyDef]: ...

    # Property attachment
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
    ) -> PropertyBinding: ...

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
    ) -> PropertyBinding: ...

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
    ) -> PropertyBinding: ...

    def detach_property_from_class(self, *, class_name: str, property_name: str) -> None: ...

    def detach_property_from_interface(
        self, *, interface_name: str, property_name: str
    ) -> None: ...

    def detach_property_from_relationship(
        self, *, relationship_id: str, property_name: str
    ) -> None: ...

    def get_properties_of_class(
        self, class_name: str, *, include_interfaces: bool = True
    ) -> list[EffectivePropertyDef]: ...

    def get_properties_of_interface(self, interface_name: str) -> list[EffectivePropertyDef]: ...

    def get_properties_of_relationship(
        self, relationship_id: str
    ) -> list[EffectivePropertyDef]: ...

    # Relationship
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
    ) -> RelationshipDef: ...

    def get_relationship(self, id: str) -> RelationshipDef | None: ...

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
    ) -> RelationshipDef: ...

    def move_relationship(self, id: str, *, from_class: str, to_class: str) -> RelationshipDef: ...

    def delete_relationship(self, id: str, *, detach: bool = False) -> None: ...

    def list_relationships(
        self,
        *,
        from_class: str | None = None,
        to_class: str | None = None,
        name: str | None = None,
    ) -> list[RelationshipDef]: ...

    def is_relationship_allowed(
        self, *, from_class: str, relationship_name: str, to_class: str
    ) -> bool: ...

    # Constraint
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
    ) -> ConstraintDef: ...

    def get_constraint(self, id: str) -> ConstraintDef | None: ...

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
    ) -> ConstraintDef: ...

    def delete_constraint(self, id: str) -> None: ...

    def list_constraints(
        self,
        *,
        target_kind: str | None = None,
        target_id: str | None = None,
        kind: str | None = None,
    ) -> list[ConstraintDef]: ...

    # Connector
    def define_connector(
        self,
        name: str,
        *,
        kind: ConnectorKind = "postgres",
        dsn_ref: str = "",
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
        merge: bool = True,
    ) -> ConnectorDef: ...

    def get_connector(self, name: str) -> ConnectorDef | None: ...

    def list_connectors(self) -> list[ConnectorDef]: ...

    def delete_connector(self, name: str, *, detach: bool = False) -> None: ...

    # Source binding (class <- RDB query)
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
    ) -> SourceBinding: ...

    def get_source_binding(self, class_name: str) -> SourceBinding | None: ...

    def detach_source_binding_from_class(self, class_name: str) -> None: ...

    def list_source_bindings(self) -> list[SourceBinding]: ...

    # View (class <- named parameterized RDB query, resolved on demand to a table)
    def define_view(self, view: ViewDef, *, merge: bool = True) -> ViewDef: ...

    def get_view(self, name: str) -> ViewDef | None: ...

    def list_views(self, class_name: str | None = None) -> list[ViewDef]: ...

    def delete_view(self, name: str) -> None: ...
