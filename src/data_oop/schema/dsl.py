from __future__ import annotations

from typing import Any

from data_oop.memory import InMemoryTBoxRepository
from data_oop.schema.repository import TBoxRepository


class ClassBuilder:
    """Builder helper for defining properties on a ClassDef."""

    def __init__(self, builder: TBoxBuilder, class_name: str):
        self.builder = builder
        self.class_name = class_name

    def property(
        self,
        name: str,
        datatype: str = "string",
        *,
        required: bool = False,
        unique: bool = False,
        nullable: bool = True,
        default: Any | None = None,
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ClassBuilder:
        """Create a PropertyDef and attach it to this class."""
        self.builder.repo.create_property(
            name,
            datatype=datatype,
            description=description,
            metadata=metadata,
        )
        self.builder.repo.attach_property_to_class(
            class_name=self.class_name,
            property_name=name,
            required=required,
            unique=unique,
            nullable=nullable,
            default=default,
            metadata=metadata,
        )
        return self

    def end(self) -> TBoxBuilder:
        """Return the parent TBoxBuilder to continue chaining."""
        return self.builder


class TBoxBuilder:
    """Fluent builder for creating a TBox schema repository."""

    def __init__(self, repo: TBoxRepository | None = None):
        self.repo = repo or InMemoryTBoxRepository()

    def class_(
        self,
        name: str,
        *,
        label: str | None = None,
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
        parent: str | None = None,
    ) -> ClassBuilder:
        """Create a ClassDef and return a ClassBuilder to chain properties.

        ``parent`` declares a SUBCLASS_OF edge to an already-defined class; the new
        class inherits the parent's property bindings and constraints, and its ABox
        instances carry the parent's label.
        """
        self.repo.create_class(
            name,
            label=label,
            description=description,
            metadata=metadata,
        )
        if parent is not None:
            self.repo.set_subclass_of(class_name=name, parent_name=parent)
        return ClassBuilder(self, name)

    def relationship(
        self,
        id_or_name: str,
        name_or_from: str | None = None,
        from_or_to: str | None = None,
        to_class: str | None = None,
        *,
        id: str | None = None,
        min_count: int = 0,
        max_count: int | None = None,
        required: bool = False,
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TBoxBuilder:
        """Define a RelationshipDef."""
        if to_class is None:
            # Called as relationship("ORGANIZED", "Team", "Event")
            real_id = id
            real_name = id_or_name
            real_from = name_or_from
            real_to = from_or_to
        else:
            # Called as relationship("rel_id", "ORGANIZED", "Team", "Event")
            real_id = id_or_name
            real_name = name_or_from
            real_from = from_or_to
            real_to = to_class

        self.repo.define_relationship(
            id=real_id,
            name=real_name,
            from_class=real_from,
            to_class=real_to,
            min_count=min_count,
            max_count=max_count,
            required=required,
            description=description,
            metadata=metadata,
        )
        return self

    def build(self) -> TBoxRepository:
        """Return the completed TBoxRepository."""
        return self.repo
