
from data_oop import (
    InMemoryTBoxRepository,
    TBoxBuilder,
)


def test_tbox_builder_chains_correctly() -> None:
    repo = InMemoryTBoxRepository()
    builder = TBoxBuilder(repo)

    builder.class_("Team", description="A team") \
        .property("name", required=True, unique=True) \
        .property("description", required=False) \
        .end() \
        .class_("Event", description="An event") \
        .property("name", required=True, unique=True) \
        .property("start_date", required=True) \
        .end() \
        .relationship("rel_team_organized_event", "ORGANIZED", "Team", "Event")

    # Verify ClassDef
    team_class = repo.get_class("Team")
    assert team_class is not None
    assert team_class.description == "A team"

    # Verify Properties on Class
    effective_props = {
        item.property.name: item for item in repo.get_properties_of_class("Team")
    }
    assert "name" in effective_props
    assert effective_props["name"].binding.required is True
    assert effective_props["name"].binding.unique is True
    assert "description" in effective_props
    assert effective_props["description"].binding.required is False

    # Verify Relationships
    assert repo.is_relationship_allowed(
        from_class="Team", relationship_name="ORGANIZED", to_class="Event"
    )


def test_tbox_builder_relationship_without_id() -> None:
    repo = InMemoryTBoxRepository()
    builder = TBoxBuilder(repo)

    builder.class_("Team") \
        .end() \
        .class_("Event") \
        .end() \
        .relationship("ORGANIZED", "Team", "Event")

    # Verify relationship was created with auto-generated id
    assert repo.is_relationship_allowed(
        from_class="Team", relationship_name="ORGANIZED", to_class="Event"
    )
    # The default generated id format is rel_from_name_to
    rel = repo.get_relationship("rel_team_organized_event")
    assert rel is not None
    assert rel.name == "ORGANIZED"
