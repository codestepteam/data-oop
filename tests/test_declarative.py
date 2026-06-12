from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from data_oop import (
    InMemoryTBoxRepository,
    apply_schema,
    load_schema_file,
    parse_schema_spec,
    plan_schema,
)

SCHEMA_YAML = textwrap.dedent(
    """
    interfaces:
      Named:
        description: Has a display name
        properties:
          name: {datatype: string, required: true}

    classes:
      Agent: {}
      Organization: {}
      Person:
        parent: Agent
        implements: [Named]
        properties:
          age: {datatype: integer}

    relationships:
      WORKS_FOR:
        from: Person
        to: Organization
        max_count: 1

    constraints:
      person_age_range:
        kind: range
        target_kind: class
        target_id: Person
        properties: [age]
        expression: "0..150"
    """
)


def _spec():
    import yaml

    return parse_schema_spec(yaml.safe_load(SCHEMA_YAML))


def test_load_schema_file_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "schema.yaml"
    path.write_text(SCHEMA_YAML, encoding="utf-8")
    spec = load_schema_file(path)
    assert {c.name for c in spec.classes} == {"Agent", "Organization", "Person"}
    person = next(c for c in spec.classes if c.name == "Person")
    assert person.parents == ("Agent",)
    assert person.implements == ("Named",)
    rel = spec.relationships[0]
    assert rel.effective_id == "rel_Person_WORKS_FOR_Organization"
    assert rel.max_count == 1


def test_plan_on_empty_repo_is_all_creates() -> None:
    repo = InMemoryTBoxRepository()
    plan = plan_schema(repo, _spec())
    kinds = {a.kind for a in plan.actions}
    assert kinds == {"create"}
    entities = {a.entity for a in plan.actions}
    assert {"property", "interface", "class", "subclass", "implements", "binding",
            "relationship", "constraint"} <= entities


def test_apply_then_plan_is_all_unchanged() -> None:
    repo = InMemoryTBoxRepository()
    result = apply_schema(repo, _spec())
    assert result.applied
    assert repo.get_class("Person") is not None
    assert repo.is_subclass_of(class_name="Person", parent_name="Agent")
    assert repo.class_implements(class_name="Person", interface_name="Named")
    assert repo.get_relationship("rel_Person_WORKS_FOR_Organization") is not None
    assert repo.get_constraint("person_age_range") is not None

    plan = plan_schema(repo, _spec())
    assert plan.changes() == []


def test_apply_is_idempotent() -> None:
    repo = InMemoryTBoxRepository()
    apply_schema(repo, _spec())
    apply_schema(repo, _spec())  # second run must not raise or duplicate
    assert len(repo.list_relationships()) == 1
    assert len([c for c in repo.list_classes()]) == 3


def test_dry_run_writes_nothing() -> None:
    repo = InMemoryTBoxRepository()
    result = apply_schema(repo, _spec(), dry_run=True)
    assert not result.applied
    assert repo.get_class("Person") is None


def test_plan_detects_cardinality_update() -> None:
    repo = InMemoryTBoxRepository()
    apply_schema(repo, _spec())

    import yaml

    raw = yaml.safe_load(SCHEMA_YAML)
    raw["relationships"]["WORKS_FOR"]["max_count"] = 3
    changed = parse_schema_spec(raw)
    plan = plan_schema(repo, changed)
    updates = [a for a in plan.changes() if a.kind == "update"]
    assert len(updates) == 1
    assert updates[0].entity == "relationship"


def test_prune_plans_deletion_of_removed_entities() -> None:
    repo = InMemoryTBoxRepository()
    apply_schema(repo, _spec())
    repo.create_class("Orphan")

    plan = plan_schema(repo, _spec(), prune=True)
    deletes = [a for a in plan.changes() if a.kind == "delete"]
    assert any(a.entity == "class" and a.target == "Orphan" for a in deletes)

    result = apply_schema(repo, _spec(), prune=True)
    assert result.applied
    assert repo.get_class("Orphan") is None


def test_conflicting_property_datatypes_rejected() -> None:
    raw = {
        "classes": {
            "A": {"properties": {"x": {"datatype": "string"}}},
            "B": {"properties": {"x": {"datatype": "integer"}}},
        }
    }
    repo = InMemoryTBoxRepository()
    with pytest.raises(ValueError, match="conflicting datatypes"):
        plan_schema(repo, parse_schema_spec(raw))


def test_unknown_top_level_key_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown top-level"):
        parse_schema_spec({"clases": {}})
