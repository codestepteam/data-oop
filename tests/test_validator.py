import pytest

from data_oop import InMemoryTBoxRepository, TBoxValidationError, TBoxValidator


def build_valid_repo() -> InMemoryTBoxRepository:
    repo = InMemoryTBoxRepository()
    repo.create_interface("NamedResource")
    repo.create_class("Database")
    repo.create_class("Table")
    repo.create_property("name", datatype="string")
    repo.create_property("schema", datatype="string")
    repo.create_property("ordinal", datatype="integer")

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
    repo.define_relationship(
        id="rel-has-table",
        name="HAS_TABLE",
        from_class="Database",
        to_class="Table",
    )
    repo.attach_property_to_relationship(
        relationship_id="rel-has-table",
        property_name="ordinal",
    )
    return repo


def test_valid_tbox_report_is_valid_and_effective_schema_is_available() -> None:
    repo = build_valid_repo()
    validator = TBoxValidator(repo)

    report = validator.validate_tbox()
    class_schema = validator.get_effective_class_schema("Table")
    relationship_schema = validator.get_effective_relationship_schema("rel-has-table")

    assert report.valid
    assert [interface.name for interface in class_schema.interfaces] == ["NamedResource"]
    assert {item.property.name for item in class_schema.properties} == {"name", "schema"}
    assert [item.property.name for item in relationship_schema.properties] == ["ordinal"]


def test_report_raise_if_invalid_raises_validation_error() -> None:
    repo = build_valid_repo()
    repo.update_property("ordinal", datatype="xml")

    report = TBoxValidator(repo).validate_tbox()

    assert not report.valid
    assert any(issue.code == "property.unsupported_datatype" for issue in report.errors())
    with pytest.raises(TBoxValidationError):
        report.raise_if_invalid()


def test_required_relationship_must_have_min_count_at_least_one() -> None:
    repo = InMemoryTBoxRepository()
    repo.create_class("Table")
    repo.create_class("Column")
    repo.define_relationship(
        id="rel-has-column",
        name="HAS_COLUMN",
        from_class="Table",
        to_class="Column",
        required=True,
        min_count=0,
    )

    report = TBoxValidator(repo).validate_relationship("rel-has-column")

    assert not report.valid
    assert any(
        issue.code == "relationship.required_without_min_count"
        for issue in report.errors()
    )


def test_default_conflict_between_interface_bindings_is_reported() -> None:
    repo = InMemoryTBoxRepository()
    repo.create_class("Table")
    repo.create_interface("NamedA")
    repo.create_interface("NamedB")
    repo.create_property("name", datatype="string")

    repo.attach_property_to_interface(
        interface_name="NamedA", property_name="name", default="a"
    )
    repo.attach_property_to_interface(
        interface_name="NamedB", property_name="name", default="b"
    )
    repo.implement_interface(class_name="Table", interface_name="NamedA")
    repo.implement_interface(class_name="Table", interface_name="NamedB")

    report = TBoxValidator(repo).validate_class("Table")

    assert not report.valid
    assert any(
        issue.code == "class.property_default_conflict" for issue in report.errors()
    )


def test_constraint_property_names_must_exist_on_effective_target() -> None:
    repo = build_valid_repo()
    repo.create_constraint(
        id="constraint-table-name",
        kind="composite_unique",
        target_kind="class",
        target_id="Table",
        property_names=("missing",),
    )

    report = TBoxValidator(repo).validate_constraint("constraint-table-name")

    assert not report.valid
    assert any(issue.code == "constraint.property_not_found" for issue in report.errors())


def test_name_pattern_is_validated() -> None:
    repo = InMemoryTBoxRepository()
    repo.create_class("1Invalid")

    report = TBoxValidator(repo).validate_tbox()

    assert not report.valid
    assert any(issue.code == "class.invalid_name" for issue in report.errors())
