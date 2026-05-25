import pytest
from falkordb import FalkorDB

from data_oop import FalkorTBoxRepository, TBoxConflictError, TBoxNotFoundError, TBoxAlreadyExistsError


@pytest.fixture(scope="module")
def falkor_graph():
    # Connect to the local test FalkorDB
    db = FalkorDB(host="localhost", port=6380)
    # Use a separate temp graph name to avoid messing with live commerce_tbox
    graph = db.select_graph("tbox_test_temp")
    
    try:
        graph.delete()
    except Exception:
        pass
        
    yield graph
    
    # Teardown: clean up temp graph
    try:
        graph.delete()
    except Exception:
        pass


def test_falkor_repository_crud_lifecycle(falkor_graph) -> None:
    repo = FalkorTBoxRepository(falkor_graph)

    # 1. Class CRUD
    # Create
    team_class = repo.create_class("Team", label="Team", description="A team", metadata={"key": "val"})
    assert team_class.name == "Team"
    assert team_class.description == "A team"
    assert team_class.metadata == {"key": "val"}

    # Get
    retrieved = repo.get_class("Team")
    assert retrieved is not None
    assert retrieved.name == "Team"
    assert retrieved.description == "A team"
    assert retrieved.metadata == {"key": "val"}

    # Update
    updated = repo.update_class("Team", label="NewTeam", description="Updated description", metadata={"new_key": "new_val"})
    assert updated.label == "NewTeam"
    assert updated.description == "Updated description"
    # Metadata merges
    assert updated.metadata == {"key": "val", "new_key": "new_val"}

    # Duplicate create raises if merge=False
    with pytest.raises(TBoxAlreadyExistsError):
        repo.create_class("Team", merge=False)

    # 2. Property CRUD & Attachment
    # Create Property
    prop = repo.create_property("name", datatype="string", description="Name property")
    assert prop.name == "name"
    assert prop.datatype == "string"

    # Attach to class
    binding = repo.attach_property_to_class(
        class_name="Team",
        property_name="name",
        required=True,
        unique=True,
    )
    assert binding.required is True
    assert binding.unique is True

    # Retrieve attached properties
    effective_props = {
        item.property.name: item for item in repo.get_properties_of_class("Team")
    }
    assert "name" in effective_props
    assert effective_props["name"].binding.required is True
    assert effective_props["name"].binding.unique is True

    # 3. Relationship CRUD
    # Create target class first
    repo.create_class("Event", label="Event", description="An event")

    # Define relationship
    rel = repo.define_relationship(
        id="rel_team_organized_event",
        name="ORGANIZED",
        from_class="Team",
        to_class="Event",
        min_count=1,
        required=True,
    )
    assert rel.id == "rel_team_organized_event"
    assert rel.required is True

    # Check validation
    assert repo.is_relationship_allowed(from_class="Team", relationship_name="ORGANIZED", to_class="Event") is True
    assert repo.is_relationship_allowed(from_class="Event", relationship_name="ORGANIZED", to_class="Team") is False

    # 4. Conflict / NotFound Cases
    assert repo.get_class("NonExistent") is None

    with pytest.raises(TBoxNotFoundError):
        repo.update_class("NonExistent", label="NonExistent")

    with pytest.raises(TBoxConflictError):
        # Semantic duplicate relationship (same from/name/to but diff ID)
        repo.define_relationship(
            id="rel_dup_id",
            name="ORGANIZED",
            from_class="Team",
            to_class="Event",
        )

    # 5. Delete lifecycle (with detach=True)
    # Detach Delete Class
    repo.delete_class("Team", detach=True)
    assert repo.get_class("Team") is None

    # Relationship and property attachments should have been deleted/detached
    assert repo.get_relationship("rel_team_organized_event") is None
