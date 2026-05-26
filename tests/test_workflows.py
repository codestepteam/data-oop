import pytest
import uuid
from falkordb import FalkorDB

from data_oop import (
    FalkorTBoxRepository,
    connect_and_clear_abox_nodes,
    save_workflow,
    run_workflow,
)


@pytest.fixture(scope="module")
def falkor_graph():
    db = FalkorDB(host="localhost", port=6380)
    graph = db.select_graph("tbox_test_temp")
    
    try:
        graph.delete()
    except Exception:
        pass
        
    yield graph
    
    try:
        graph.delete()
    except Exception:
        pass


def test_save_and_run_workflow_successfully(falkor_graph) -> None:
    # 1. Setup TBox classes for the test
    tbox_repo = FalkorTBoxRepository(falkor_graph)
    tbox_repo.create_class("Team", label="Team", description="A team")
    tbox_repo.create_class("Event", label="Event", description="An event")
    tbox_repo.create_property("name", datatype="string")
    tbox_repo.create_property("start_date", datatype="string")
    tbox_repo.create_property("description", datatype="string")
    
    tbox_repo.attach_property_to_class(class_name="Team", property_name="name", required=True)
    tbox_repo.attach_property_to_class(class_name="Event", property_name="name", required=True)
    tbox_repo.attach_property_to_class(class_name="Event", property_name="start_date", required=True)
    tbox_repo.attach_property_to_class(class_name="Event", property_name="description", required=True)
    
    tbox_repo.define_relationship(
        id="rel_team_organized_event",
        name="ORGANIZED",
        from_class="Team",
        to_class="Event",
    )

    # 2. Setup ABox: Create a Team node
    team_uuid = str(uuid.uuid4())
    tbox_graph = falkor_graph
    tbox_graph.query(
        "CREATE (:Team {uuid: $uuid, name: $name})",
        {"uuid": team_uuid, "name": "Marketing Team"}
    )

    # 3. Define and Save Workflow Steps
    steps = [
        {
            "step_id": "create_event",
            "action": "create_node",
            "class_name": "Event",
            "properties": {
                "name": "{event_name}",
                "start_date": "{start_date}",
                "description": "{description}"
            }
        },
        {
            "step_id": "link_team",
            "action": "create_relationship",
            "from_class": "Team",
            "from_uuid": "{team_uuid}",
            "relationship_name": "ORGANIZED",
            "to_class": "Event",
            "to_uuid": "{create_event.uuid}"
        }
    ]

    # Save
    save_workflow(
        graph=falkor_graph,
        name="organize_event_workflow",
        steps=steps,
        description="Workflow to create an event and link it to a team"
    )

    # Verify WorkflowDefinition exists in ABox
    rows = falkor_graph.query("MATCH (w:WorkflowDefinition {name: 'organize_event_workflow'}) RETURN w.uuid").result_set
    assert len(rows) == 1

    # 4. Run Workflow
    params = {
        "event_name": "Autumn Sale 2026",
        "start_date": "2026-10-01",
        "description": "Big autumn discount sale",
        "team_uuid": team_uuid,
    }
    
    results = run_workflow(
        graph=falkor_graph,
        name="organize_event_workflow",
        parameters=params,
    )

    # Verify run results contains step logs
    assert "create_event" in results
    event_uuid = results["create_event"]["uuid"]
    assert event_uuid is not None
    assert results["create_event"]["name"] == "Autumn Sale 2026"

    # Verify DB state: Event node actually created
    event_rows = falkor_graph.query(
        "MATCH (e:Event {uuid: $uuid}) RETURN e.name, e.start_date, e.description",
        {"uuid": event_uuid}
    ).result_set
    assert len(event_rows) == 1
    assert event_rows[0][0] == "Autumn Sale 2026"
    assert event_rows[0][1] == "2026-10-01"

    # Verify DB state: ORGANIZED relationship created
    rel_rows = falkor_graph.query(
        "MATCH (t:Team {uuid: $team_uuid})-[r:ORGANIZED]->(e:Event {uuid: $event_uuid}) RETURN count(r)",
        {"team_uuid": team_uuid, "event_uuid": event_uuid}
    ).result_set
    assert rel_rows[0][0] == 1


def test_conditional_and_loop_workflow_execution(falkor_graph) -> None:
    # Setup TBox classes
    tbox_repo = FalkorTBoxRepository(falkor_graph)
    if not tbox_repo.get_class("Product"):
        tbox_repo.create_class("Product", label="Product", description="Product class")
        tbox_repo.create_property("name", datatype="string")
        tbox_repo.attach_property_to_class(class_name="Product", property_name="name", required=True)
    if not tbox_repo.get_class("Event"):
        tbox_repo.create_class("Event", label="Event")
        
    tbox_repo.define_relationship(
        id="rel_event_includes_product",
        name="INCLUDES",
        from_class="Event",
        to_class="Product",
    )

    # Clean ABox
    falkor_graph.query("MATCH (n:Product) DETACH DELETE n")

    # Save a workflow with loop and condition
    steps = [
        {
            "step_id": "create_event",
            "action": "create_node",
            "class_name": "Event",
            "properties": {
                "name": "{event_name}"
            }
        },
        {
            "step_id": "create_optional_product",
            "action": "create_node",
            "if_present": "opt_product_name", # Only run if opt_product_name is provided
            "class_name": "Product",
            "properties": {
                "name": "{opt_product_name}"
            }
        },
        {
            "step_id": "link_products",
            "action": "create_relationship",
            "loop_over": "product_uuids", # Loop over input array of UUIDs
            "loop_var": "p_uuid",
            "from_class": "Event",
            "from_uuid": "{create_event.uuid}",
            "relationship_name": "INCLUDES",
            "to_class": "Product",
            "to_uuid": "{p_uuid}"
        }
    ]

    save_workflow(
        graph=falkor_graph,
        name="loop_cond_workflow",
        steps=steps,
        description="Workflow testing loops and conditions"
    )

    # Scenario A: opt_product_name is missing, loop runs with 2 products
    product1_uuid = str(uuid.uuid4())
    product2_uuid = str(uuid.uuid4())
    
    # Create products in DB first
    falkor_graph.query("CREATE (:Product {uuid: $u1, name: 'P1'})", {"u1": product1_uuid})
    falkor_graph.query("CREATE (:Product {uuid: $u2, name: 'P2'})", {"u2": product2_uuid})

    params = {
        "event_name": "Summer Festival",
        "product_uuids": [product1_uuid, product2_uuid],
        # opt_product_name is omitted (missing)
    }

    results = run_workflow(
        graph=falkor_graph,
        name="loop_cond_workflow",
        parameters=params,
    )

    # Verification A
    # create_optional_product step should be skipped (not in results)
    assert "create_optional_product" not in results
    # create_event and link_products should be in results
    assert "create_event" in results
    assert "link_products" in results
    assert len(results["link_products"]) == 2  # looped 2 times

    event_uuid = results["create_event"]["uuid"]
    # Check relationships exist in DB
    rel_count = falkor_graph.query(
        "MATCH (e:Event {uuid: $event_uuid})-[r:INCLUDES]->(p:Product) RETURN count(r)",
        {"event_uuid": event_uuid}
    ).result_set[0][0]
    assert rel_count == 2

    # Scenario B: product_uuids is passed as a stringified JSON array (simulating API payload string inputs)
    params_str = {
        "event_name": "Autumn Festival",
        "product_uuids": f'["{product1_uuid}", "{product2_uuid}"]',
    }

    results_str = run_workflow(
        graph=falkor_graph,
        name="loop_cond_workflow",
        parameters=params_str,
    )

    # Verification B
    assert "link_products" in results_str
    assert len(results_str["link_products"]) == 2
    # The to_uuid should be resolved as raw strings, not containing JSON characters
    assert results_str["link_products"][0]["to_uuid"] == product1_uuid
    assert results_str["link_products"][1]["to_uuid"] == product2_uuid


def test_nested_workflow_execution(falkor_graph) -> None:
    tbox_repo = FalkorTBoxRepository(falkor_graph)
    # Ensure classes and properties exist
    tbox_repo.create_class("Product", label="Product", description="A product")
    tbox_repo.create_class("Event", label="Event", description="An event")
    tbox_repo.create_property("name", datatype="string")
    tbox_repo.create_property("description", datatype="string")
    tbox_repo.attach_property_to_class(class_name="Product", property_name="name", required=True)
    tbox_repo.attach_property_to_class(class_name="Product", property_name="description")
    tbox_repo.attach_property_to_class(class_name="Event", property_name="name", required=True)
    tbox_repo.define_relationship(
        id="rel_event_includes_product",
        name="INCLUDES",
        from_class="Event",
        to_class="Product",
    )

    # 1. Define and Save Sub-Workflow (creates a Product)
    sub_steps = [
        {
            "step_id": "create_prod",
            "action": "create_node",
            "class_name": "Product",
            "properties": {
                "name": "{prod_name}",
                "description": "{prod_desc}"
            }
        }
    ]
    sub_params = [
        { "name": "prod_name", "type": "string", "required": True },
        { "name": "prod_desc", "type": "string" }
    ]
    save_workflow(
        graph=falkor_graph,
        name="create_product_sub_wf",
        steps=sub_steps,
        parameters=sub_params,
        description="Sub workflow to create a product"
    )

    # 2. Define and Save Parent Workflow (creates Event, calls Sub-Workflow, links them)
    parent_steps = [
        {
            "step_id": "create_evt",
            "action": "create_node",
            "class_name": "Event",
            "properties": {
                "name": "{event_name}"
            }
        },
        {
            "step_id": "call_sub",
            "action": "run_workflow",
            "workflow_name": "create_product_sub_wf",
            "parameters": {
                "prod_name": "{product_name}",
                "prod_desc": "{product_desc}"
            }
        },
        {
            "step_id": "link_event_prod",
            "action": "create_relationship",
            "from_class": "Event",
            "from_uuid": "{create_evt.uuid}",
            "relationship_name": "INCLUDES",
            "to_class": "Product",
            "to_uuid": "{call_sub.create_prod.uuid}"
        }
    ]
    parent_params = [
        { "name": "event_name", "type": "string", "required": True },
        { "name": "product_name", "type": "string", "required": True },
        { "name": "product_desc", "type": "string" }
    ]
    save_workflow(
        graph=falkor_graph,
        name="parent_wf",
        steps=parent_steps,
        parameters=parent_params,
        description="Parent workflow with nested workflow execution"
    )

    # 3. Run Parent Workflow
    p_params = {
        "event_name": "Expo 2026",
        "product_name": "Super Widget",
        "product_desc": "State of the art widget"
    }

    results = run_workflow(
        graph=falkor_graph,
        name="parent_wf",
        parameters=p_params,
    )

    # Verification
    assert "create_evt" in results
    assert "call_sub" in results
    assert "create_prod" in results["call_sub"]
    assert "link_event_prod" in results

    event_uuid = results["create_evt"]["uuid"]
    product_uuid = results["call_sub"]["create_prod"]["uuid"]
    
    assert results["link_event_prod"]["from_uuid"] == event_uuid
    assert results["link_event_prod"]["to_uuid"] == product_uuid

    # Query DB to verify relationship exists
    rel_exists = falkor_graph.query(
        "MATCH (e:Event {uuid: $e_uuid})-[r:INCLUDES]->(p:Product {uuid: $p_uuid}) RETURN count(r)",
        {"e_uuid": event_uuid, "p_uuid": product_uuid}
    ).result_set[0][0]
    assert rel_exists == 1


def test_workflow_execution_rollback_on_failure(falkor_graph) -> None:
    tbox_repo = FalkorTBoxRepository(falkor_graph)
    tbox_repo.create_class("Event", label="Event", description="An event")
    tbox_repo.create_property("name", datatype="string")
    tbox_repo.attach_property_to_class(class_name="Event", property_name="name", required=True)

    # 1. Simple rollback: creates event node, then fails on invalid class
    steps = [
        {
            "step_id": "create_evt",
            "action": "create_node",
            "class_name": "Event",
            "properties": {
                "name": "Event To Rollback"
            }
        },
        {
            "step_id": "fail_step",
            "action": "create_node",
            "class_name": "FakeClassDoesNotExist",
            "properties": {}
        }
    ]

    save_workflow(
        graph=falkor_graph,
        name="rollback_simple_wf",
        steps=steps,
        description="Workflow that fails on step 2"
    )

    # Run should raise ValueError
    with pytest.raises(ValueError) as excinfo:
        run_workflow(
            graph=falkor_graph,
            name="rollback_simple_wf",
            parameters={}
        )
    assert "ClassDef not found" in str(excinfo.value)

    # Verify that Event node does not exist in DB
    evt_exists = falkor_graph.query(
        "MATCH (e:Event {name: 'Event To Rollback'}) RETURN count(e)"
    ).result_set[0][0]
    assert evt_exists == 0


def test_nested_workflow_rollback_on_failure(falkor_graph) -> None:
    tbox_repo = FalkorTBoxRepository(falkor_graph)
    tbox_repo.create_class("Product", label="Product", description="A product")
    tbox_repo.create_class("Event", label="Event", description="An event")
    tbox_repo.create_property("name", datatype="string")
    tbox_repo.attach_property_to_class(class_name="Product", property_name="name", required=True)
    tbox_repo.attach_property_to_class(class_name="Event", property_name="name", required=True)

    # 1. Sub-workflow (succeeds)
    sub_steps = [
        {
            "step_id": "create_prod",
            "action": "create_node",
            "class_name": "Product",
            "properties": {
                "name": "Product To Rollback"
            }
        }
    ]
    save_workflow(
        graph=falkor_graph,
        name="sub_wf_succeed",
        steps=sub_steps,
        description="Sub-workflow that succeeds"
    )

    # 2. Parent workflow (creates event, runs sub-workflow, then fails)
    parent_steps = [
        {
            "step_id": "create_evt",
            "action": "create_node",
            "class_name": "Event",
            "properties": {
                "name": "Event To Rollback 2"
            }
        },
        {
            "step_id": "call_sub",
            "action": "run_workflow",
            "workflow_name": "sub_wf_succeed",
            "parameters": {}
        },
        {
            "step_id": "fail_step",
            "action": "create_node",
            "class_name": "FakeClassDoesNotExist",
            "properties": {}
        }
    ]
    save_workflow(
        graph=falkor_graph,
        name="parent_wf_fail",
        steps=parent_steps,
        description="Parent workflow that fails after running sub-workflow"
    )

    # Run parent
    with pytest.raises(ValueError):
        run_workflow(
            graph=falkor_graph,
            name="parent_wf_fail",
            parameters={}
        )

    # Both Event and Product nodes should be rolled back!
    evt_exists = falkor_graph.query(
        "MATCH (e:Event {name: 'Event To Rollback 2'}) RETURN count(e)"
    ).result_set[0][0]
    assert evt_exists == 0

    prod_exists = falkor_graph.query(
        "MATCH (p:Product {name: 'Product To Rollback'}) RETURN count(p)"
    ).result_set[0][0]
    assert prod_exists == 0


def test_workflow_validation_and_dsl_generation() -> None:
    from data_oop.models import WorkflowDef, WorkflowStepDef, WorkflowParameterDef
    from data_oop.workflows import validate_workflow, generate_workflow_dsl, extract_parameters_from_steps
    
    # 1. Valid WorkflowDef
    steps = (
        WorkflowStepDef(
            step_id="create_user",
            action="create_node",
            class_name="User",
            properties={"name": "{user_name}"}
        ),
        WorkflowStepDef(
            step_id="create_profile",
            action="create_node",
            class_name="Profile",
            properties={"bio": "{bio_text}"},
            if_present="bio_text"
        ),
        WorkflowStepDef(
            step_id="link_user_profile",
            action="create_relationship",
            from_class="User",
            from_uuid="{create_user.uuid}",
            relationship_name="HAS_PROFILE",
            to_class="Profile",
            to_uuid="{create_profile.uuid}"
        )
    )
    
    params = (
        WorkflowParameterDef(name="user_name", type="string"),
        WorkflowParameterDef(name="bio_text", type="string", required=False),
    )
    
    wf = WorkflowDef(
        name="test_val_dsl",
        steps=steps,
        parameters=params,
        description="Test validation and DSL"
    )
    
    # Should not raise any ValueError
    validate_workflow(wf)
    
    # DSL Generation
    dsl = generate_workflow_dsl(wf)
    assert "WorkflowBuilder(" in dsl
    assert ".parameter(" in dsl
    assert "create_node(" in dsl
    assert "create_relationship(" in dsl
    assert '"user_name": "YOUR_USER_NAME_VALUE"' in dsl

    # 2. Parameter extraction
    raw_steps = [
        {
            "step_id": "step_1",
            "action": "create_node",
            "class_name": "ClassA",
            "properties": {"val": "{param_1}"}
        },
        {
            "step_id": "step_2",
            "action": "create_relationship",
            "loop_over": "param_array",
            "loop_var": "item",
            "from_class": "ClassA",
            "from_uuid": "{step_1.uuid}",
            "relationship_name": "REL",
            "to_class": "ClassB",
            "to_uuid": "{item}"
        },
        {
            "step_id": "step_3",
            "action": "create_relationship",
            "loop_over": "product_id",
            "loop_var": "product_id",
            "from_class": "Event",
            "from_uuid": "{step_1.uuid}",
            "relationship_name": "INCLUDES",
            "to_class": "Product",
            "to_uuid": "{product_id}",
            "if_present": "product_id"
        }
    ]
    extracted = extract_parameters_from_steps(raw_steps)
    extracted_names = {p["name"] for p in extracted}
    assert extracted_names == {"param_1", "param_array", "product_id"}
    # Verify parameter type detection
    param_types = {p["name"]: p["type"] for p in extracted}
    assert param_types["param_1"] == "string"
    assert param_types["param_array"] == "array"
    assert param_types["product_id"] == "array"
    
    # Verify optional parameter detection via if_present
    param_required = {p["name"]: p["required"] for p in extracted}
    assert param_required["param_1"] is True
    assert param_required["product_id"] is False

    # 3. Invalid workflows
    # Duplicate step_id
    invalid_steps_1 = (
        WorkflowStepDef(step_id="step_a", action="create_node", class_name="ClassA"),
        WorkflowStepDef(step_id="step_a", action="create_node", class_name="ClassA"),
    )
    with pytest.raises(ValueError, match="Duplicate step_id"):
        validate_workflow(WorkflowDef(name="invalid", steps=invalid_steps_1))

    # Undefined variable reference
    invalid_steps_2 = (
        WorkflowStepDef(
            step_id="step_a",
            action="create_node",
            class_name="ClassA",
            properties={"name": "{undefined_param}"}
        ),
    )
    with pytest.raises(ValueError, match="references undefined variable"):
        validate_workflow(WorkflowDef(name="invalid", steps=invalid_steps_2))

    # 4. Test WorkflowBuilder
    from data_oop import WorkflowBuilder
    
    wf_builder = (
        WorkflowBuilder("builder_test", description="Using builder pattern")
        .parameter("param1", type="string")
        .parameter("param2", type="array")
        .create_node(
            step_id="node_1",
            class_name="User",
            properties={"name": "{param1}"}
        )
        .create_relationship(
            step_id="node_2",
            relationship_name="FOLLOWS",
            from_class="User",
            from_uuid="{node_1.uuid}",
            to_class="User",
            to_uuid="{item}"
        )
        .loop_over("param2", loop_var="item")
    )
    
    wf_from_builder = wf_builder.build()
    
    assert wf_from_builder.name == "builder_test"
    assert len(wf_from_builder.parameters) == 2
    assert wf_from_builder.parameters[0].name == "param1"
    assert wf_from_builder.parameters[1].type == "array"
    assert len(wf_from_builder.steps) == 2
    assert wf_from_builder.steps[1].loop_over == "param2"
    assert wf_from_builder.steps[1].loop_var == "item"


def test_workflow_parameter_value_validation() -> None:
    from data_oop.models import WorkflowParameterDef
    from data_oop.workflows import validate_workflow_parameter_values

    valid_uuid = str(uuid.uuid4())
    params = (
        WorkflowParameterDef(name="id", type="uuid"),
        WorkflowParameterDef(name="start_date", type="date"),
        WorkflowParameterDef(name="created_at", type="datetime"),
        WorkflowParameterDef(name="count", type="integer"),
        WorkflowParameterDef(name="score", type="float"),
        WorkflowParameterDef(name="enabled", type="boolean"),
        WorkflowParameterDef(name="email", type="email"),
        WorkflowParameterDef(name="url", type="url"),
        WorkflowParameterDef(name="phone", type="phone"),
        WorkflowParameterDef(name="ids", type="array", array_item_type="uuid"),
        WorkflowParameterDef(name="optional_note", type="string", required=False),
    )

    normalized = validate_workflow_parameter_values(params, {
        "id": valid_uuid.upper(),
        "start_date": "2026-05-26",
        "created_at": "2026-05-26T12:34:56Z",
        "count": "12",
        "score": "3.14",
        "enabled": "true",
        "email": "user@example.com",
        "url": "https://example.com/path",
        "phone": "+1 555 123 4567",
        "ids": f'["{valid_uuid}"]',
    })

    assert normalized["id"] == valid_uuid
    assert normalized["start_date"] == "2026-05-26"
    assert normalized["created_at"] == "2026-05-26T12:34:56+00:00"
    assert normalized["count"] == 12
    assert normalized["score"] == 3.14
    assert normalized["enabled"] is True
    assert normalized["ids"] == [valid_uuid]
    assert "optional_note" not in normalized

    with pytest.raises(ValueError, match="must be UUID"):
        validate_workflow_parameter_values((WorkflowParameterDef(name="id", type="uuid"),), {"id": "bad"})
    with pytest.raises(ValueError, match="ISO date"):
        validate_workflow_parameter_values((WorkflowParameterDef(name="d", type="date"),), {"d": "05/26/2026"})
    with pytest.raises(ValueError, match="Missing required"):
        validate_workflow_parameter_values((WorkflowParameterDef(name="required", type="string"),), {})

    # Float validation edge cases
    assert validate_workflow_parameter_values((WorkflowParameterDef(name="f", type="float"),), {"f": 12})["f"] == 12.0
    with pytest.raises(ValueError, match="must be float"):
        validate_workflow_parameter_values((WorkflowParameterDef(name="f", type="float"),), {"f": True})
    with pytest.raises(ValueError, match="must be float"):
        validate_workflow_parameter_values((WorkflowParameterDef(name="f", type="float"),), {"f": "not-a-number"})

    # Boolean validation edge cases
    assert validate_workflow_parameter_values((WorkflowParameterDef(name="b", type="boolean"),), {"b": "yes"})["b"] is True
    assert validate_workflow_parameter_values((WorkflowParameterDef(name="b", type="boolean"),), {"b": "off"})["b"] is False
    with pytest.raises(ValueError, match="must be boolean"):
        validate_workflow_parameter_values((WorkflowParameterDef(name="b", type="boolean"),), {"b": "maybe"})

    # Integer edge cases
    with pytest.raises(ValueError, match="must be integer"):
        validate_workflow_parameter_values((WorkflowParameterDef(name="i", type="integer"),), {"i": "12.3"})
    with pytest.raises(ValueError, match="must be integer"):
        validate_workflow_parameter_values((WorkflowParameterDef(name="i", type="integer"),), {"i": True})

    # Array edge cases
    with pytest.raises(ValueError, match="must be array"):
        validate_workflow_parameter_values((WorkflowParameterDef(name="a", type="array"),), {"a": "invalid-json{"})
    with pytest.raises(ValueError, match="must be array"):
        validate_workflow_parameter_values((WorkflowParameterDef(name="a", type="array"),), {"a": 123})


def test_circular_and_forward_references_validation() -> None:
    from data_oop.models import WorkflowDef, WorkflowStepDef
    from data_oop.workflows import validate_workflow

    # 1. Forward reference (step_1 references step_2 which is defined later)
    forward_steps = (
        WorkflowStepDef(
            step_id="step_1",
            action="create_node",
            class_name="User",
            properties={"name": "{step_2.uuid}"}
        ),
        WorkflowStepDef(
            step_id="step_2",
            action="create_node",
            class_name="User",
            properties={"name": "Alice"}
        ),
    )
    with pytest.raises(ValueError, match="references undefined variable: 'step_2'"):
        validate_workflow(WorkflowDef(name="forward_ref", steps=forward_steps))

    # 2. Circular reference (step_1 -> step_2 -> step_1)
    circular_steps = (
        WorkflowStepDef(
            step_id="step_1",
            action="create_node",
            class_name="User",
            properties={"name": "{step_2.uuid}"}
        ),
        WorkflowStepDef(
            step_id="step_2",
            action="create_node",
            class_name="User",
            properties={"name": "{step_1.uuid}"}
        ),
    )
    with pytest.raises(ValueError, match="references undefined variable: 'step_2'"):
        validate_workflow(WorkflowDef(name="circular_ref", steps=circular_steps))


def test_rollback_continues_on_individual_rollback_failure(falkor_graph, monkeypatch) -> None:
    from data_oop.workflows import run_workflow, save_workflow
    import data_oop.workflows
    
    rollback_calls = []
    original_rollback = data_oop.workflows._execute_rollback_item
    
    def mock_rollback(graph, item):
        rollback_calls.append(item)
        if item.get("uuid") == "fail_uuid":
            raise Exception("Simulated Rollback Query Failure")
        original_rollback(graph, item)
        
    monkeypatch.setattr(data_oop.workflows, "_execute_rollback_item", mock_rollback)
    
    steps = [
        {
            "step_id": "step_1",
            "action": "create_node",
            "class_name": "Product",
            "uuid": "fail_uuid",
            "properties": {"name": "P1"}
        },
        {
            "step_id": "step_2",
            "action": "create_node",
            "class_name": "Product",
            "uuid": "success_uuid",
            "properties": {"name": "P2"}
        },
        {
            "step_id": "step_3",
            "action": "create_node",
            "class_name": "NonExistentClassSpecFail",
            "properties": {}
        }
    ]
    
    save_workflow(graph=falkor_graph, name="rollback_fail_test", steps=steps)
    
    with pytest.raises(ValueError):
        run_workflow(graph=falkor_graph, name="rollback_fail_test", parameters={})
        
    assert len(rollback_calls) == 2
    uuids_rolled_back = {item.get("uuid") for item in rollback_calls}
    assert uuids_rolled_back == {"success_uuid", "fail_uuid"}

