from __future__ import annotations

from typing import Any, Sequence, Type

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


class Property:
    """Declarative Property specification for class attributes."""

    def __init__(
        self,
        datatype: str = "string",
        *,
        required: bool = False,
        unique: bool = False,
        nullable: bool = True,
        default: Any | None = None,
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        self.datatype = datatype
        self.required = required
        self.unique = unique
        self.nullable = nullable
        self.default = default
        self.description = description
        self.metadata = metadata or {}


def tbox_class(
    *,
    label: str | None = None,
    description: str | None = None,
    metadata: dict[str, Any] | None = None,
):
    """Class decorator to mark a class as a TBox ClassDef."""
    def decorator(cls: Type[Any]) -> Type[Any]:
        cls.__tbox_class__ = True
        cls.__tbox_label__ = label
        cls.__tbox_desc__ = description
        cls.__tbox_metadata__ = metadata or {}
        return cls
    return decorator


class RelationshipSpec:
    """Specification for defining a relationship declaratively."""

    def __init__(
        self,
        id: str,
        name: str,
        from_class: str | Type[Any],
        to_class: str | Type[Any],
        *,
        min_count: int = 0,
        max_count: int | None = None,
        required: bool = False,
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        self.id = id
        self.name = name
        self.from_class = from_class
        self.to_class = to_class
        self.min_count = min_count
        self.max_count = max_count
        self.required = required
        self.description = description
        self.metadata = metadata or {}


def load_tbox_from_specs(
    repo: TBoxRepository,
    classes: Sequence[Type[Any]],
    relationships: Sequence[RelationshipSpec] = (),
) -> TBoxRepository:
    """Load TBox definitions from declarative class definitions and relationship specs."""
    for cls in classes:
        if not getattr(cls, "__tbox_class__", False):
            raise ValueError(f"Class {cls.__name__} is not decorated with @tbox_class")

        class_name = cls.__name__
        label = getattr(cls, "__tbox_label__", None) or class_name
        description = getattr(cls, "__tbox_desc__", None)
        metadata = getattr(cls, "__tbox_metadata__", {})

        repo.create_class(class_name, label=label, description=description, metadata=metadata)

        # Inspect class attributes for Property specs
        for attr_name in dir(cls):
            if attr_name.startswith("_"):
                continue
            attr_val = getattr(cls, attr_name)
            if isinstance(attr_val, Property):
                repo.create_property(
                    attr_name,
                    datatype=attr_val.datatype,
                    description=attr_val.description,
                    metadata=attr_val.metadata,
                )
                repo.attach_property_to_class(
                    class_name=class_name,
                    property_name=attr_name,
                    required=attr_val.required,
                    unique=attr_val.unique,
                    nullable=attr_val.nullable,
                    default=attr_val.default,
                    metadata=attr_val.metadata,
                )

    for rel in relationships:
        from_name = rel.from_class if isinstance(rel.from_class, str) else rel.from_class.__name__
        to_name = rel.to_class if isinstance(rel.to_class, str) else rel.to_class.__name__

        repo.define_relationship(
            id=rel.id,
            name=rel.name,
            from_class=from_name,
            to_class=to_name,
            min_count=rel.min_count,
            max_count=rel.max_count,
            required=rel.required,
            description=rel.description,
            metadata=rel.metadata,
        )

    return repo
