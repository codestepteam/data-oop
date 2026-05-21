import pytest

from tbox import (
    InMemoryTBoxRepository,
    Property,
    RelationshipSpec,
    TBoxBuilder,
    load_tbox_from_specs,
    tbox_class,
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


def test_tbox_declarative_dsl_loads_correctly() -> None:
    @tbox_class(description="A department within the organization")
    class Department:
        name = Property(required=True, unique=True)
        code = Property(required=True, unique=True)

    @tbox_class(description="A projects handled by department")
    class Project:
        title = Property(required=True)
        budget = Property(datatype="integer", required=False)

    repo = InMemoryTBoxRepository()
    
    # Load into repository using specs
    load_tbox_from_specs(
        repo,
        classes=[Department, Project],
        relationships=[
            RelationshipSpec(
                id="rel_dept_runs_project",
                name="RUNS",
                from_class=Department,
                to_class=Project,
                required=True,
            )
        ],
    )

    # Verify class metadata
    dept_class = repo.get_class("Department")
    assert dept_class is not None
    assert dept_class.description == "A department within the organization"

    # Verify properties
    effective_props = {
        item.property.name: item for item in repo.get_properties_of_class("Department")
    }
    assert "name" in effective_props
    assert effective_props["name"].binding.required is True
    assert "code" in effective_props
    assert effective_props["code"].binding.unique is True

    # Verify project budget datatype
    project_props = {
        item.property.name: item for item in repo.get_properties_of_class("Project")
    }
    assert project_props["budget"].property.datatype == "integer"

    # Verify relationships
    assert repo.is_relationship_allowed(
        from_class="Department", relationship_name="RUNS", to_class="Project"
    )
    rel = repo.get_relationship("rel_dept_runs_project")
    assert rel is not None
    assert rel.required is True


def test_tbox_declarative_dsl_raises_on_undecorated_class() -> None:
    class InvalidClass:
        name = Property()

    repo = InMemoryTBoxRepository()

    with pytest.raises(ValueError, match="is not decorated with @tbox_class"):
        load_tbox_from_specs(repo, classes=[InvalidClass])
