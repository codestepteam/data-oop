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

