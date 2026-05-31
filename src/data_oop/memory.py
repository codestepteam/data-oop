from __future__ import annotations

from typing import Any, Literal

from .exceptions import TBoxAlreadyExistsError, TBoxConflictError, TBoxNotFoundError
from .models import (
    ClassDef,
    ConnectorDef,
    ConstraintDef,
    EffectivePropertyDef,
    InterfaceDef,
    OwnerKind,
    PropertyBinding,
    PropertyDef,
    RelationshipDef,
    SourceBinding,
    SourceLink,
    TargetKind,
)


def _normalize_links(links: tuple[SourceLink, ...]) -> tuple[SourceLink, ...]:
    """Default each link's target_property to its local_key when left blank."""
    return tuple(
        link if link.target_property else SourceLink(
            relationship_name=link.relationship_name,
            to_class=link.to_class,
            local_key=link.local_key,
            target_property=link.local_key,
            direction=link.direction,
        )
        for link in links
    )


class InMemoryTBoxRepository:
    """In-memory TBox repository implementing the plan.md API.

    The repository mirrors the planned graph model with dictionaries and edge sets:
    IMPLEMENTS, HAS_PROPERTY, FROM_CLASS, TO_CLASS, and CONSTRAINS.
    """

    def __init__(self) -> None:
        self._classes: dict[str, ClassDef] = {}
        self._interfaces: dict[str, InterfaceDef] = {}
        self._properties: dict[str, PropertyDef] = {}
        self._relationships: dict[str, RelationshipDef] = {}
        self._constraints: dict[str, ConstraintDef] = {}
        self._implements: set[tuple[str, str]] = set()
        self._property_bindings: dict[tuple[OwnerKind, str, str], PropertyBinding] = {}
        self._connectors: dict[str, ConnectorDef] = {}
        self._source_bindings: dict[str, SourceBinding] = {}

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _merge_metadata(
        existing: dict[str, Any], incoming: dict[str, Any] | None
    ) -> dict[str, Any]:
        merged = dict(existing)
        if incoming:
            merged.update(incoming)
        return merged

    def _require_class(self, name: str) -> ClassDef:
        if name not in self._classes:
            raise TBoxNotFoundError(f"ClassDef not found: {name}")
        return self._classes[name]

    def _require_interface(self, name: str) -> InterfaceDef:
        if name not in self._interfaces:
            raise TBoxNotFoundError(f"InterfaceDef not found: {name}")
        return self._interfaces[name]

    def _require_property(self, name: str) -> PropertyDef:
        if name not in self._properties:
            raise TBoxNotFoundError(f"PropertyDef not found: {name}")
        return self._properties[name]

    def _require_relationship(self, id: str) -> RelationshipDef:
        if id not in self._relationships:
            raise TBoxNotFoundError(f"RelationshipDef not found: {id}")
        return self._relationships[id]

    def _require_constraint(self, id: str) -> ConstraintDef:
        if id not in self._constraints:
            raise TBoxNotFoundError(f"ConstraintDef not found: {id}")
        return self._constraints[id]

    def _require_connector(self, name: str) -> ConnectorDef:
        if name not in self._connectors:
            raise TBoxNotFoundError(f"ConnectorDef not found: {name}")
        return self._connectors[name]

    def _require_target(self, target_kind: TargetKind, target_id: str) -> None:
        if target_kind == "class":
            self._require_class(target_id)
        elif target_kind == "interface":
            self._require_interface(target_id)
        elif target_kind == "property":
            self._require_property(target_id)
        elif target_kind == "relationship":
            self._require_relationship(target_id)
        else:
            raise TBoxConflictError(f"Unsupported target kind: {target_kind}")

    def _require_owner(self, owner_kind: OwnerKind, owner_id: str) -> None:
        self._require_target(owner_kind, owner_id)

    def _relationship_semantic_key(
        self, relationship: RelationshipDef
    ) -> tuple[str, str, str]:
        return (relationship.from_class, relationship.name, relationship.to_class)

    def _find_relationship_by_semantic_key(
        self, *, from_class: str, name: str, to_class: str, exclude_id: str | None = None
    ) -> RelationshipDef | None:
        for relationship in self._relationships.values():
            if exclude_id is not None and relationship.id == exclude_id:
                continue
            if (
                relationship.from_class == from_class
                and relationship.name == name
                and relationship.to_class == to_class
            ):
                return relationship
        return None

    def _assert_no_semantic_relationship_duplicate(
        self, *, id: str, name: str, from_class: str, to_class: str
    ) -> None:
        existing = self._find_relationship_by_semantic_key(
            from_class=from_class,
            name=name,
            to_class=to_class,
            exclude_id=id,
        )
        if existing is not None:
            raise TBoxConflictError(
                "Relationship semantic key already exists: "
                f"({from_class}, {name}, {to_class}) as {existing.id}"
            )

    def _bindings_for_owner(
        self, owner_kind: OwnerKind, owner_id: str
    ) -> list[PropertyBinding]:
        return [
            binding
            for (kind, oid, _), binding in self._property_bindings.items()
            if kind == owner_kind and oid == owner_id
        ]

    def _constraints_for_target(
        self, target_kind: str, target_id: str
    ) -> list[ConstraintDef]:
        return [
            constraint
            for constraint in self._constraints.values()
            if constraint.target_kind == target_kind and constraint.target_id == target_id
        ]

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
        if name in self._classes:
            if not merge:
                raise TBoxAlreadyExistsError(f"ClassDef already exists: {name}")
            existing = self._classes[name]
            updated = ClassDef(
                name=name,
                label=label if label is not None else existing.label,
                description=(
                    description if description is not None else existing.description
                ),
                metadata=self._merge_metadata(existing.metadata, metadata),
            )
            self._classes[name] = updated
            return updated

        class_def = ClassDef(
            name=name,
            label=label,
            description=description,
            metadata=dict(metadata or {}),
        )
        self._classes[name] = class_def
        return class_def

    def get_class(self, name: str) -> ClassDef | None:
        return self._classes.get(name)

    def update_class(
        self,
        name: str,
        *,
        label: str | None = None,
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ClassDef:
        existing = self._require_class(name)
        updated = ClassDef(
            name=name,
            label=label if label is not None else existing.label,
            description=description if description is not None else existing.description,
            metadata=self._merge_metadata(existing.metadata, metadata),
        )
        self._classes[name] = updated
        return updated

    def delete_class(self, name: str, *, detach: bool = False) -> None:
        self._require_class(name)
        references = []
        references.extend(edge for edge in self._implements if edge[0] == name)
        references.extend(self._bindings_for_owner("class", name))
        references.extend(self._constraints_for_target("class", name))
        references.extend(
            relationship
            for relationship in self._relationships.values()
            if relationship.from_class == name or relationship.to_class == name
        )
        if references and not detach:
            raise TBoxConflictError(f"ClassDef has references: {name}")

        self._implements = {edge for edge in self._implements if edge[0] != name}
        self._property_bindings = {
            key: value
            for key, value in self._property_bindings.items()
            if not (key[0] == "class" and key[1] == name)
        }
        self._constraints = {
            key: value
            for key, value in self._constraints.items()
            if not (value.target_kind == "class" and value.target_id == name)
        }
        for relationship_id in [
            relationship.id
            for relationship in self._relationships.values()
            if relationship.from_class == name or relationship.to_class == name
        ]:
            self.delete_relationship(relationship_id, detach=True)
        self._source_bindings.pop(name, None)
        del self._classes[name]

    def list_classes(
        self, *, implements: str | None = None, has_property: str | None = None
    ) -> list[ClassDef]:
        classes = list(self._classes.values())
        if implements is not None:
            classes = [
                class_def
                for class_def in classes
                if (class_def.name, implements) in self._implements
            ]
        if has_property is not None:
            classes = [
                class_def
                for class_def in classes
                if ("class", class_def.name, has_property) in self._property_bindings
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
        if name in self._interfaces:
            if not merge:
                raise TBoxAlreadyExistsError(f"InterfaceDef already exists: {name}")
            existing = self._interfaces[name]
            updated = InterfaceDef(
                name=name,
                description=description if description is not None else existing.description,
                metadata=self._merge_metadata(existing.metadata, metadata),
            )
            self._interfaces[name] = updated
            return updated

        interface_def = InterfaceDef(
            name=name, description=description, metadata=dict(metadata or {})
        )
        self._interfaces[name] = interface_def
        return interface_def

    def get_interface(self, name: str) -> InterfaceDef | None:
        return self._interfaces.get(name)

    def update_interface(
        self,
        name: str,
        *,
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> InterfaceDef:
        existing = self._require_interface(name)
        updated = InterfaceDef(
            name=name,
            description=description if description is not None else existing.description,
            metadata=self._merge_metadata(existing.metadata, metadata),
        )
        self._interfaces[name] = updated
        return updated

    def delete_interface(self, name: str, *, detach: bool = False) -> None:
        self._require_interface(name)
        references = []
        references.extend(edge for edge in self._implements if edge[1] == name)
        references.extend(self._bindings_for_owner("interface", name))
        references.extend(self._constraints_for_target("interface", name))
        if references and not detach:
            raise TBoxConflictError(f"InterfaceDef has references: {name}")

        self._implements = {edge for edge in self._implements if edge[1] != name}
        self._property_bindings = {
            key: value
            for key, value in self._property_bindings.items()
            if not (key[0] == "interface" and key[1] == name)
        }
        self._constraints = {
            key: value
            for key, value in self._constraints.items()
            if not (value.target_kind == "interface" and value.target_id == name)
        }
        del self._interfaces[name]

    def list_interfaces(
        self,
        *,
        implemented_by: str | None = None,
        has_property: str | None = None,
    ) -> list[InterfaceDef]:
        interfaces = list(self._interfaces.values())
        if implemented_by is not None:
            interfaces = [
                interface_def
                for interface_def in interfaces
                if (implemented_by, interface_def.name) in self._implements
            ]
        if has_property is not None:
            interfaces = [
                interface_def
                for interface_def in interfaces
                if ("interface", interface_def.name, has_property)
                in self._property_bindings
            ]
        return sorted(interfaces, key=lambda value: value.name)

    # ------------------------------------------------------------------
    # Implements
    # ------------------------------------------------------------------
    def implement_interface(self, *, class_name: str, interface_name: str) -> None:
        self._require_class(class_name)
        self._require_interface(interface_name)
        self._implements.add((class_name, interface_name))

    def remove_interface(self, *, class_name: str, interface_name: str) -> None:
        self._require_class(class_name)
        self._require_interface(interface_name)
        self._implements.discard((class_name, interface_name))

    def class_implements(self, *, class_name: str, interface_name: str) -> bool:
        self._require_class(class_name)
        self._require_interface(interface_name)
        return (class_name, interface_name) in self._implements

    def get_interfaces_of_class(self, class_name: str) -> list[InterfaceDef]:
        self._require_class(class_name)
        return sorted(
            [
                self._interfaces[interface_name]
                for cls, interface_name in self._implements
                if cls == class_name
            ],
            key=lambda value: value.name,
        )

    def get_classes_of_interface(self, interface_name: str) -> list[ClassDef]:
        self._require_interface(interface_name)
        return sorted(
            [
                self._classes[class_name]
                for class_name, iface in self._implements
                if iface == interface_name
            ],
            key=lambda value: value.name,
        )

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
        if name in self._properties:
            if not merge:
                raise TBoxAlreadyExistsError(f"PropertyDef already exists: {name}")
            existing = self._properties[name]
            updated = PropertyDef(
                name=name,
                datatype=(
                    datatype
                    if datatype != "unknown" or existing.datatype == "unknown"
                    else existing.datatype
                ),
                description=description if description is not None else existing.description,
                metadata=self._merge_metadata(existing.metadata, metadata),
            )
            self._properties[name] = updated
            return updated

        property_def = PropertyDef(
            name=name,
            datatype=datatype,
            description=description,
            metadata=dict(metadata or {}),
        )
        self._properties[name] = property_def
        return property_def

    def get_property(self, name: str) -> PropertyDef | None:
        return self._properties.get(name)

    def update_property(
        self,
        name: str,
        *,
        datatype: str | None = None,
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> PropertyDef:
        existing = self._require_property(name)
        updated = PropertyDef(
            name=name,
            datatype=datatype if datatype is not None else existing.datatype,
            description=description if description is not None else existing.description,
            metadata=self._merge_metadata(existing.metadata, metadata),
        )
        self._properties[name] = updated
        return updated

    def delete_property(self, name: str, *, detach: bool = False) -> None:
        self._require_property(name)
        references = []
        references.extend(
            binding
            for (_, _, property_name), binding in self._property_bindings.items()
            if property_name == name
        )
        references.extend(self._constraints_for_target("property", name))
        if references and not detach:
            raise TBoxConflictError(f"PropertyDef has references: {name}")

        self._property_bindings = {
            key: value
            for key, value in self._property_bindings.items()
            if key[2] != name
        }
        self._constraints = {
            key: value
            for key, value in self._constraints.items()
            if not (value.target_kind == "property" and value.target_id == name)
        }
        del self._properties[name]

    def list_properties(
        self,
        *,
        owner_class: str | None = None,
        owner_interface: str | None = None,
        owner_relationship: str | None = None,
    ) -> list[PropertyDef]:
        owner_filters: list[tuple[OwnerKind, str]] = []
        if owner_class is not None:
            self._require_class(owner_class)
            owner_filters.append(("class", owner_class))
        if owner_interface is not None:
            self._require_interface(owner_interface)
            owner_filters.append(("interface", owner_interface))
        if owner_relationship is not None:
            self._require_relationship(owner_relationship)
            owner_filters.append(("relationship", owner_relationship))

        if not owner_filters:
            return sorted(self._properties.values(), key=lambda value: value.name)

        property_names = {
            property_name
            for (kind, owner_id, property_name) in self._property_bindings
            if (kind, owner_id) in owner_filters
        }
        return [self._properties[name] for name in sorted(property_names)]

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
        binding = PropertyBinding(
            owner_kind=owner_kind,
            owner_id=owner_id,
            property_name=property_name,
            required=required,
            unique=unique,
            nullable=nullable,
            default=default,
            metadata=dict(metadata or {}),
        )
        self._property_bindings[(owner_kind, owner_id, property_name)] = binding
        return binding

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
        self._property_bindings.pop(("class", class_name, property_name), None)

    def detach_property_from_interface(
        self, *, interface_name: str, property_name: str
    ) -> None:
        self._require_interface(interface_name)
        self._property_bindings.pop(("interface", interface_name, property_name), None)

    def detach_property_from_relationship(
        self, *, relationship_id: str, property_name: str
    ) -> None:
        self._require_relationship(relationship_id)
        self._property_bindings.pop(("relationship", relationship_id, property_name), None)

    def _effective_property_from_binding(
        self,
        binding: PropertyBinding,
        *,
        source_kind: OwnerKind,
        source_id: str,
    ) -> EffectivePropertyDef:
        return EffectivePropertyDef(
            property=self._properties[binding.property_name],
            binding=binding,
            source_kind=source_kind,
            source_id=source_id,
        )

    def _property_sources_of_class(
        self, class_name: str, *, include_interfaces: bool = True
    ) -> list[EffectivePropertyDef]:
        self._require_class(class_name)
        sources: list[EffectivePropertyDef] = []
        if include_interfaces:
            for interface_def in self.get_interfaces_of_class(class_name):
                for binding in sorted(
                    self._bindings_for_owner("interface", interface_def.name),
                    key=lambda value: value.property_name,
                ):
                    sources.append(
                        self._effective_property_from_binding(
                            binding,
                            source_kind="interface",
                            source_id=interface_def.name,
                        )
                    )

        for binding in sorted(
            self._bindings_for_owner("class", class_name),
            key=lambda value: value.property_name,
        ):
            sources.append(
                self._effective_property_from_binding(
                    binding, source_kind="class", source_id=class_name
                )
            )
        return sources

    @staticmethod
    def _merge_effective_property_sources(
        owner_kind: OwnerKind,
        owner_id: str,
        sources: list[EffectivePropertyDef],
    ) -> list[EffectivePropertyDef]:
        grouped: dict[str, list[EffectivePropertyDef]] = {}
        for source in sources:
            grouped.setdefault(source.property.name, []).append(source)

        merged: list[EffectivePropertyDef] = []
        for property_name in sorted(grouped):
            values = grouped[property_name]
            if len(values) == 1:
                merged.append(values[0])
                continue

            defaults = [value.binding.default for value in values if value.binding.default is not None]
            default = defaults[0] if defaults else None
            metadata: dict[str, Any] = {}
            for value in values:
                metadata.update(value.binding.metadata)

            binding = PropertyBinding(
                owner_kind=owner_kind,
                owner_id=owner_id,
                property_name=property_name,
                required=any(value.binding.required for value in values),
                unique=any(value.binding.unique for value in values),
                nullable=all(value.binding.nullable for value in values),
                default=default,
                metadata=metadata,
            )
            direct_source = next(
                (value for value in values if value.source_kind == owner_kind), None
            )
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

    def get_properties_of_class(
        self, class_name: str, *, include_interfaces: bool = True
    ) -> list[EffectivePropertyDef]:
        sources = self._property_sources_of_class(
            class_name, include_interfaces=include_interfaces
        )
        return self._merge_effective_property_sources("class", class_name, sources)

    def get_properties_of_interface(self, interface_name: str) -> list[EffectivePropertyDef]:
        self._require_interface(interface_name)
        return [
            self._effective_property_from_binding(
                binding, source_kind="interface", source_id=interface_name
            )
            for binding in sorted(
                self._bindings_for_owner("interface", interface_name),
                key=lambda value: value.property_name,
            )
        ]

    def get_properties_of_relationship(
        self, relationship_id: str
    ) -> list[EffectivePropertyDef]:
        self._require_relationship(relationship_id)
        return [
            self._effective_property_from_binding(
                binding, source_kind="relationship", source_id=relationship_id
            )
            for binding in sorted(
                self._bindings_for_owner("relationship", relationship_id),
                key=lambda value: value.property_name,
            )
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
        self._assert_no_semantic_relationship_duplicate(
            id=id, name=name, from_class=from_class, to_class=to_class
        )

        if id in self._relationships:
            if not merge:
                raise TBoxAlreadyExistsError(f"RelationshipDef already exists: {id}")
            existing = self._relationships[id]
            updated = RelationshipDef(
                id=id,
                name=name,
                from_class=from_class,
                to_class=to_class,
                min_count=min_count,
                max_count=max_count,
                required=required,
                description=description if description is not None else existing.description,
                metadata=self._merge_metadata(existing.metadata, metadata),
            )
            self._relationships[id] = updated
            return updated

        relationship = RelationshipDef(
            id=id,
            name=name,
            from_class=from_class,
            to_class=to_class,
            min_count=min_count,
            max_count=max_count,
            required=required,
            description=description,
            metadata=dict(metadata or {}),
        )
        self._relationships[id] = relationship
        return relationship

    def get_relationship(self, id: str) -> RelationshipDef | None:
        return self._relationships.get(id)

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
        self._assert_no_semantic_relationship_duplicate(
            id=id,
            name=new_name,
            from_class=existing.from_class,
            to_class=existing.to_class,
        )
        updated = RelationshipDef(
            id=id,
            name=new_name,
            from_class=existing.from_class,
            to_class=existing.to_class,
            min_count=min_count if min_count is not None else existing.min_count,
            max_count=max_count if max_count is not None else existing.max_count,
            required=required if required is not None else existing.required,
            description=description if description is not None else existing.description,
            metadata=self._merge_metadata(existing.metadata, metadata),
        )
        self._relationships[id] = updated
        return updated

    def move_relationship(
        self, id: str, *, from_class: str, to_class: str
    ) -> RelationshipDef:
        existing = self._require_relationship(id)
        self._require_class(from_class)
        self._require_class(to_class)
        self._assert_no_semantic_relationship_duplicate(
            id=id, name=existing.name, from_class=from_class, to_class=to_class
        )
        updated = RelationshipDef(
            id=id,
            name=existing.name,
            from_class=from_class,
            to_class=to_class,
            min_count=existing.min_count,
            max_count=existing.max_count,
            required=existing.required,
            description=existing.description,
            metadata=dict(existing.metadata),
        )
        self._relationships[id] = updated
        return updated

    def delete_relationship(self, id: str, *, detach: bool = False) -> None:
        self._require_relationship(id)
        references = []
        references.extend(self._bindings_for_owner("relationship", id))
        references.extend(self._constraints_for_target("relationship", id))
        if references and not detach:
            raise TBoxConflictError(f"RelationshipDef has references: {id}")

        self._property_bindings = {
            key: value
            for key, value in self._property_bindings.items()
            if not (key[0] == "relationship" and key[1] == id)
        }
        self._constraints = {
            key: value
            for key, value in self._constraints.items()
            if not (value.target_kind == "relationship" and value.target_id == id)
        }
        del self._relationships[id]

    def list_relationships(
        self,
        *,
        from_class: str | None = None,
        to_class: str | None = None,
        name: str | None = None,
    ) -> list[RelationshipDef]:
        relationships = list(self._relationships.values())
        if from_class is not None:
            relationships = [
                relationship
                for relationship in relationships
                if relationship.from_class == from_class
            ]
        if to_class is not None:
            relationships = [
                relationship
                for relationship in relationships
                if relationship.to_class == to_class
            ]
        if name is not None:
            relationships = [
                relationship for relationship in relationships if relationship.name == name
            ]
        return sorted(relationships, key=lambda value: value.id)

    def is_relationship_allowed(
        self, *, from_class: str, relationship_name: str, to_class: str
    ) -> bool:
        return (
            self._find_relationship_by_semantic_key(
                from_class=from_class, name=relationship_name, to_class=to_class
            )
            is not None
        )

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
        self._require_target(target_kind, target_id)
        if id in self._constraints:
            if not merge:
                raise TBoxAlreadyExistsError(f"ConstraintDef already exists: {id}")
            existing = self._constraints[id]
            updated = ConstraintDef(
                id=id,
                kind=kind,
                target_kind=target_kind,
                target_id=target_id,
                property_names=property_names,
                expression=expression if expression is not None else existing.expression,
                severity=severity,
                description=description if description is not None else existing.description,
                metadata=self._merge_metadata(existing.metadata, metadata),
            )
            self._constraints[id] = updated
            return updated

        constraint = ConstraintDef(
            id=id,
            kind=kind,
            target_kind=target_kind,
            target_id=target_id,
            property_names=property_names,
            expression=expression,
            severity=severity,
            description=description,
            metadata=dict(metadata or {}),
        )
        self._constraints[id] = constraint
        return constraint

    def get_constraint(self, id: str) -> ConstraintDef | None:
        return self._constraints.get(id)

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
        new_target_kind = target_kind if target_kind is not None else existing.target_kind
        new_target_id = target_id if target_id is not None else existing.target_id
        self._require_target(new_target_kind, new_target_id)
        updated = ConstraintDef(
            id=id,
            kind=kind if kind is not None else existing.kind,
            target_kind=new_target_kind,
            target_id=new_target_id,
            property_names=(
                property_names if property_names is not None else existing.property_names
            ),
            expression=expression if expression is not None else existing.expression,
            severity=severity if severity is not None else existing.severity,
            description=description if description is not None else existing.description,
            metadata=self._merge_metadata(existing.metadata, metadata),
        )
        self._constraints[id] = updated
        return updated

    def delete_constraint(self, id: str) -> None:
        self._require_constraint(id)
        del self._constraints[id]

    def list_constraints(
        self,
        *,
        target_kind: str | None = None,
        target_id: str | None = None,
        kind: str | None = None,
    ) -> list[ConstraintDef]:
        constraints = list(self._constraints.values())
        if target_kind is not None:
            constraints = [
                constraint
                for constraint in constraints
                if constraint.target_kind == target_kind
            ]
        if target_id is not None:
            constraints = [
                constraint for constraint in constraints if constraint.target_id == target_id
            ]
        if kind is not None:
            constraints = [constraint for constraint in constraints if constraint.kind == kind]
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
        if name in self._connectors:
            if not merge:
                raise TBoxAlreadyExistsError(f"ConnectorDef already exists: {name}")
            existing = self._connectors[name]
            updated = ConnectorDef(
                name=name,
                kind=kind,
                dsn_ref=dsn_ref if dsn_ref else existing.dsn_ref,
                description=description if description is not None else existing.description,
                metadata=self._merge_metadata(existing.metadata, metadata),
            )
            self._connectors[name] = updated
            return updated

        connector = ConnectorDef(
            name=name,
            kind=kind,
            dsn_ref=dsn_ref,
            description=description,
            metadata=dict(metadata or {}),
        )
        self._connectors[name] = connector
        return connector

    def get_connector(self, name: str) -> ConnectorDef | None:
        return self._connectors.get(name)

    def list_connectors(self) -> list[ConnectorDef]:
        return sorted(self._connectors.values(), key=lambda value: value.name)

    def delete_connector(self, name: str, *, detach: bool = False) -> None:
        self._require_connector(name)
        bound = [
            binding
            for binding in self._source_bindings.values()
            if binding.connector_name == name
        ]
        if bound and not detach:
            raise TBoxConflictError(f"ConnectorDef has source bindings: {name}")
        if detach:
            self._source_bindings = {
                class_name: binding
                for class_name, binding in self._source_bindings.items()
                if binding.connector_name != name
            }
        del self._connectors[name]

    # ------------------------------------------------------------------
    # Source binding
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
        binding = SourceBinding(
            class_name=class_name,
            connector_name=connector_name,
            sql=sql,
            key_columns=tuple(key_columns),
            column_map=dict(column_map or {}),
            materialization=materialization,
            refresh_interval_hours=refresh_interval_hours,
            links=_normalize_links(tuple(links)),
        )
        self._source_bindings[class_name] = binding
        return binding

    def get_source_binding(self, class_name: str) -> SourceBinding | None:
        return self._source_bindings.get(class_name)

    def detach_source_binding_from_class(self, class_name: str) -> None:
        self._require_class(class_name)
        self._source_bindings.pop(class_name, None)

    def list_source_bindings(self) -> list[SourceBinding]:
        return sorted(self._source_bindings.values(), key=lambda value: value.class_name)
