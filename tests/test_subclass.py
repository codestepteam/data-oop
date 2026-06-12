from __future__ import annotations

import pytest
from falkordb import FalkorDB

from data_oop import (
    FalkorTBoxRepository,
    InMemoryTBoxRepository,
    TBoxBuilder,
    TBoxConflictError,
    apply_subclass_labels,
    upsert_abox_node,
    upsert_abox_relationship,
)


# ---------------------------------------------------------------------------
# In-memory repository
# ---------------------------------------------------------------------------


def test_memory_subclass_hierarchy_and_cycle_detection() -> None:
    repo = InMemoryTBoxRepository()
    repo.create_class("Agent")
    repo.create_class("Person")
    repo.create_class("Employee")

    repo.set_subclass_of(class_name="Person", parent_name="Agent")
    repo.set_subclass_of(class_name="Employee", parent_name="Person")

    assert [c.name for c in repo.get_superclasses("Employee")] == ["Agent", "Person"]
    assert [c.name for c in repo.get_superclasses("Employee", transitive=False)] == ["Person"]
    assert [c.name for c in repo.get_subclasses("Agent")] == ["Employee", "Person"]
    assert repo.is_subclass_of(class_name="Employee", parent_name="Agent")
    assert not repo.is_subclass_of(class_name="Agent", parent_name="Employee")

    with pytest.raises(TBoxConflictError):
        repo.set_subclass_of(class_name="Agent", parent_name="Employee")
    with pytest.raises(TBoxConflictError):
        repo.set_subclass_of(class_name="Agent", parent_name="Agent")


def test_memory_subclass_inherits_property_bindings() -> None:
    builder = TBoxBuilder()
    builder.class_("Agent").property("name", required=True).end()
    builder.class_("Person", parent="Agent").property("age", datatype="integer").end()
    repo = builder.build()

    props = {p.property.name: p for p in repo.get_properties_of_class("Person")}
    assert set(props) == {"name", "age"}
    assert props["name"].binding.required
    assert props["name"].source_id == "Agent"


def test_memory_own_binding_overrides_parent_default() -> None:
    repo = InMemoryTBoxRepository()
    repo.create_class("Agent")
    repo.create_class("Person")
    repo.create_property("tier")
    repo.attach_property_to_class(class_name="Agent", property_name="tier", default="base")
    repo.attach_property_to_class(class_name="Person", property_name="tier", default="member")
    repo.set_subclass_of(class_name="Person", parent_name="Agent")

    props = {p.property.name: p for p in repo.get_properties_of_class("Person")}
    assert props["tier"].binding.default == "member"


def test_memory_delete_class_blocks_on_subclass_edge() -> None:
    repo = InMemoryTBoxRepository()
    repo.create_class("Agent")
    repo.create_class("Person")
    repo.set_subclass_of(class_name="Person", parent_name="Agent")

    with pytest.raises(TBoxConflictError):
        repo.delete_class("Agent")
    repo.delete_class("Agent", detach=True)
    assert repo.get_superclasses("Person") == []


# ---------------------------------------------------------------------------
# FalkorDB repository + ABox (integration; needs FalkorDB on localhost:6380)
# ---------------------------------------------------------------------------


@pytest.fixture
def graph():
    db = FalkorDB(host="localhost", port=6380)
    g = db.select_graph("subclass_test_temp")
    try:
        g.delete()
    except Exception:
        pass
    yield g
    try:
        g.delete()
    except Exception:
        pass


def _setup_hierarchy(graph) -> FalkorTBoxRepository:
    repo = FalkorTBoxRepository(graph)
    repo.create_class("Agent")
    repo.create_class("Organization")
    repo.create_class("Person")
    repo.set_subclass_of(class_name="Person", parent_name="Agent")
    repo.create_property("name", datatype="string")
    repo.attach_property_to_class(class_name="Agent", property_name="name", required=True)
    repo.define_relationship(
        id="rel_agent_works_for_org",
        name="WORKS_FOR",
        from_class="Agent",
        to_class="Organization",
        max_count=1,
    )
    return repo


def test_falkor_subclass_roundtrip_and_cycle(graph) -> None:
    repo = _setup_hierarchy(graph)
    assert [c.name for c in repo.get_superclasses("Person")] == ["Agent"]
    assert [c.name for c in repo.get_subclasses("Agent")] == ["Person"]
    with pytest.raises(TBoxConflictError):
        repo.set_subclass_of(class_name="Agent", parent_name="Person")

    props = {p.property.name: p for p in repo.get_properties_of_class("Person")}
    assert "name" in props and props["name"].binding.required


def test_abox_instance_carries_ancestor_labels(graph) -> None:
    _setup_hierarchy(graph)
    upsert_abox_node(
        graph=graph,
        class_name="Person",
        uuid="p1",
        properties={"name": "Kim"},
        fire_triggers=False,
    )
    rows = graph.query("MATCH (n:Agent {uuid: 'p1'}) RETURN count(n)").result_set
    assert rows[0][0] == 1  # polymorphic query over the parent label matches


def test_relationship_defined_on_ancestor_usable_from_subclass(graph) -> None:
    _setup_hierarchy(graph)
    upsert_abox_node(
        graph=graph, class_name="Person", uuid="p1",
        properties={"name": "Kim"}, fire_triggers=False,
    )
    upsert_abox_node(
        graph=graph, class_name="Organization", uuid="o1",
        properties={}, fire_triggers=False,
    )
    result = upsert_abox_relationship(
        graph=graph,
        from_class="Person",
        from_uuid="p1",
        relationship_name="WORKS_FOR",
        to_class="Organization",
        to_uuid="o1",
    )
    assert result.relationship_name == "WORKS_FOR"

    # max_count=1 inherited from the ancestor definition blocks a second edge.
    upsert_abox_node(
        graph=graph, class_name="Organization", uuid="o2",
        properties={}, fire_triggers=False,
    )
    from data_oop import ABoxValidationError

    with pytest.raises(ABoxValidationError):
        upsert_abox_relationship(
            graph=graph,
            from_class="Person",
            from_uuid="p1",
            relationship_name="WORKS_FOR",
            to_class="Organization",
            to_uuid="o2",
        )


def test_apply_subclass_labels_backfills_existing_instances(graph) -> None:
    repo = FalkorTBoxRepository(graph)
    repo.create_class("Agent")
    repo.create_class("Person")
    upsert_abox_node(
        graph=graph, class_name="Person", uuid="p1",
        properties={}, fire_triggers=False,
    )
    # Hierarchy declared AFTER the instance was written.
    repo.set_subclass_of(class_name="Person", parent_name="Agent")
    rows = graph.query("MATCH (n:Agent {uuid: 'p1'}) RETURN count(n)").result_set
    assert rows[0][0] == 0

    updated = apply_subclass_labels(graph=graph, class_name="Person")
    assert updated == 1
    rows = graph.query("MATCH (n:Agent {uuid: 'p1'}) RETURN count(n)").result_set
    assert rows[0][0] == 1
