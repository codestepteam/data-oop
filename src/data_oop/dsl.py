from __future__ import annotations

from typing import Any

from .memory import InMemoryTBoxRepository
from .repository import TBoxRepository


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
    ) -> ClassBuilder:
        """Create a ClassDef and return a ClassBuilder to chain properties."""
        self.repo.create_class(
            name,
            label=label,
            description=description,
            metadata=metadata,
        )
        return ClassBuilder(self, name)

    def relationship(
        self,
        id: str,
        name: str,
        from_class: str,
        to_class: str,
        *,
        min_count: int = 0,
        max_count: int | None = None,
        required: bool = False,
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TBoxBuilder:
        """Define a RelationshipDef."""
        self.repo.define_relationship(
            id=id,
            name=name,
            from_class=from_class,
            to_class=to_class,
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
