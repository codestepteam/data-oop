import pytest

from data_oop import InMemoryTBoxRepository, TBoxConflictError


def test_class_metadata_updates() -> None:
    repo = InMemoryTBoxRepository()

    class_def = repo.create_class("Product", metadata={"foo": "bar"})
    updated = repo.update_class("Product", metadata={"baz": "qux"})

    assert class_def.metadata == {"foo": "bar"}
    assert updated.metadata == {"foo": "bar", "baz": "qux"}


def test_property_constraints_are_stored_on_bindings_not_property_def() -> None:
    repo = InMemoryTBoxRepository()
    repo.create_interface("NamedResource")
    prop = repo.create_property("name", datatype="string")
    assert not hasattr(prop, "required")
    assert not hasattr(prop, "unique")

    binding = repo.attach_property_to_interface(
        interface_name="NamedResource",
        property_name="name",
        required=True,
        unique=False,
    )

    assert binding.required is True
    assert binding.unique is False
    assert binding.property_name == "name"


def test_class_effective_properties_merge_interface_and_direct_bindings() -> None:
    repo = InMemoryTBoxRepository()
    repo.create_interface("NamedResource")
    repo.create_class("Table")
    repo.create_property("name", datatype="string")
    repo.create_property("schema", datatype="string")

    repo.attach_property_to_interface(
        interface_name="NamedResource",
        property_name="name",
        required=True,
        nullable=False,
    )
    repo.implement_interface(class_name="Table", interface_name="NamedResource")
    repo.attach_property_to_class(
        class_name="Table",
        property_name="schema",
        required=True,
        unique=True,
    )

    effective = {item.property.name: item for item in repo.get_properties_of_class("Table")}

    assert set(effective) == {"name", "schema"}
    assert effective["name"].binding.required is True
    assert effective["name"].binding.nullable is False
    assert effective["schema"].binding.unique is True


def test_relationship_def_is_node_like_and_can_have_properties() -> None:
    repo = InMemoryTBoxRepository()
    repo.create_class("Database")
    repo.create_class("Table")
    repo.create_property("ordinal", datatype="integer")

    relationship = repo.define_relationship(
        id="rel-has-table",
        name="HAS_TABLE",
        from_class="Database",
        to_class="Table",
        min_count=0,
    )
    binding = repo.attach_property_to_relationship(
        relationship_id=relationship.id,
        property_name="ordinal",
        required=False,
    )

    assert repo.is_relationship_allowed(
        from_class="Database",
        relationship_name="HAS_TABLE",
        to_class="Table",
    )
    assert binding.owner_kind == "relationship"
    assert binding.owner_id == "rel-has-table"
    assert [item.property.name for item in repo.get_properties_of_relationship(relationship.id)] == [
        "ordinal"
    ]


def test_relationship_semantic_key_must_be_unique() -> None:
    repo = InMemoryTBoxRepository()
    repo.create_class("Database")
    repo.create_class("Table")

    repo.define_relationship(
        id="rel-1", name="HAS_TABLE", from_class="Database", to_class="Table"
    )

    with pytest.raises(TBoxConflictError):
        repo.define_relationship(
            id="rel-2", name="HAS_TABLE", from_class="Database", to_class="Table"
        )


def test_move_relationship_updates_from_and_to_classes() -> None:
    repo = InMemoryTBoxRepository()
    repo.create_class("Database")
    repo.create_class("Dataset")
    repo.create_class("Table")

    repo.define_relationship(
        id="rel-1", name="HAS_TABLE", from_class="Database", to_class="Table"
    )
    moved = repo.move_relationship("rel-1", from_class="Dataset", to_class="Table")

    assert moved.from_class == "Dataset"
    assert moved.to_class == "Table"
    assert not repo.is_relationship_allowed(
        from_class="Database", relationship_name="HAS_TABLE", to_class="Table"
    )
    assert repo.is_relationship_allowed(
        from_class="Dataset", relationship_name="HAS_TABLE", to_class="Table"
    )
