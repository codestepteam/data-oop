from __future__ import annotations

import pytest
from falkordb import FalkorDB

from data_oop import (
    FalkorTBoxRepository,
    TriggerDef,
    analyze_trigger_graph,
    save_workflow,
    upsert_abox_node,
    validate_trigger_graph,
)
from data_oop.exceptions import TBoxNotFoundError, TriggerCycleError
from data_oop.workflow.triggers import MAX_TRIGGER_DEPTH, workflow_emits


# ---------------------------------------------------------------------------
# Pure static-analysis tests (no database)
# ---------------------------------------------------------------------------
def _t(name: str, cls: str, event: str, wf: str) -> TriggerDef:
    return TriggerDef(name=name, class_name=cls, event=event, workflow_name=wf)


def test_workflow_emits_create_and_update_for_create_node() -> None:
    steps = {"wf": [{"step_id": "s", "action": "create_node", "class_name": "B"}]}
    emission = workflow_emits("wf", steps)
    assert emission.events == frozenset({("B", "create"), ("B", "update")})
    assert not emission.has_loop_fanout
    assert not emission.has_dynamic_class


def test_workflow_emits_expands_nested_workflow() -> None:
    steps = {
        "outer": [{"step_id": "s", "action": "run_workflow", "workflow_name": "inner"}],
        "inner": [{"step_id": "s", "action": "create_node", "class_name": "C"}],
    }
    emission = workflow_emits("outer", steps)
    assert ("C", "create") in emission.events


def test_workflow_emits_flags_loop_and_dynamic() -> None:
    steps = {
        "loopy": [{"step_id": "s", "action": "create_node", "class_name": "C", "loop_over": "{xs}"}],
        "dyn": [{"step_id": "s", "action": "create_node", "class_name": "{cls}"}],
    }
    assert workflow_emits("loopy", steps).has_loop_fanout
    assert workflow_emits("dyn", steps).has_dynamic_class


def test_acyclic_graph_is_valid() -> None:
    steps = {"leaf": [{"step_id": "s", "action": "create_relationship", "from_class": "X"}]}
    report = analyze_trigger_graph([_t("tA", "A", "create", "leaf")], steps)
    assert report.valid
    assert report.cycles == []


def test_two_node_cycle_detected() -> None:
    steps = {
        "wfA": [{"step_id": "s", "action": "create_node", "class_name": "B"}],
        "wfB": [{"step_id": "s", "action": "create_node", "class_name": "A"}],
    }
    triggers = [_t("tA", "A", "create", "wfA"), _t("tB", "B", "create", "wfB")]
    report = analyze_trigger_graph(triggers, steps)
    assert not report.valid
    assert len(report.cycles) == 1
    assert set(report.cycles[0]) == {"tA", "tB"}


def test_self_update_loop_detected() -> None:
    # A trigger on (C, update) whose workflow updates a C node is a self-loop:
    # the most common accidental infinite loop.
    steps = {"wfC": [{"step_id": "s", "action": "create_node", "class_name": "C"}]}
    report = analyze_trigger_graph([_t("tC", "C", "update", "wfC")], steps)
    assert report.cycles == [["tC"]]


def test_dynamic_class_is_unresolved_not_a_cycle() -> None:
    steps = {"dyn": [{"step_id": "s", "action": "create_node", "class_name": "{cls}"}]}
    report = analyze_trigger_graph([_t("tD", "A", "create", "dyn")], steps)
    assert report.cycles == []
    assert report.unresolved == ["tD"]


def test_loop_over_marks_unbounded() -> None:
    steps = {"loopy": [{"step_id": "s", "action": "create_node", "class_name": "B", "loop_over": "{xs}"}]}
    report = analyze_trigger_graph([_t("tA", "A", "create", "loopy")], steps)
    assert report.unbounded == ["tA"]


def test_missing_workflow_reported() -> None:
    report = analyze_trigger_graph([_t("tA", "A", "create", "ghost")], {})
    assert report.missing_workflows == ["tA"]


def test_validate_raises_on_cycle() -> None:
    steps = {
        "wfA": [{"step_id": "s", "action": "create_node", "class_name": "B"}],
        "wfB": [{"step_id": "s", "action": "create_node", "class_name": "A"}],
    }
    triggers = [_t("tA", "A", "create", "wfA"), _t("tB", "B", "create", "wfB")]
    with pytest.raises(TriggerCycleError):
        validate_trigger_graph(triggers, steps)


def test_validate_returns_report_when_acyclic() -> None:
    report = validate_trigger_graph([], {})
    assert report.valid


# ---------------------------------------------------------------------------
# Integration tests against a live FalkorDB
# ---------------------------------------------------------------------------
@pytest.fixture()
def graph():
    try:
        db = FalkorDB(host="localhost", port=6380)
        g = db.select_graph("triggers_test_temp")
        g.query("RETURN 1")
    except Exception:  # noqa: BLE001
        pytest.skip("FalkorDB not reachable on localhost:6380")
    try:
        g.delete()
    except Exception:  # noqa: BLE001
        pass
    g = db.select_graph("triggers_test_temp")
    yield g
    try:
        g.delete()
    except Exception:  # noqa: BLE001
        pass


def _seed_classes(repo: FalkorTBoxRepository, *names: str) -> None:
    for name in names:
        repo.create_class(name, merge=True)


def test_create_node_fires_trigger_workflow(graph) -> None:
    repo = FalkorTBoxRepository(graph)
    _seed_classes(repo, "Order", "AuditLog")

    # Workflow the trigger will run: create an AuditLog node referencing the order.
    save_workflow(
        graph=graph,
        name="audit_order",
        steps=[
            {
                "step_id": "log",
                "action": "create_node",
                "class_name": "AuditLog",
                "properties": {"order_uuid": "{uuid}"},
            }
        ],
    )

    repo.attach_trigger_to_class(
        class_name="Order",
        name="on_order_created",
        event="create",
        workflow_name="audit_order",
    )

    upsert_abox_node(graph=graph, class_name="Order", uuid="order-1", properties={"total": 100})

    rows = graph.query("MATCH (a:AuditLog) RETURN a.order_uuid").result_set
    assert rows and rows[0][0] == "order-1"


def test_attach_trigger_rejects_cycle(graph) -> None:
    repo = FalkorTBoxRepository(graph)
    _seed_classes(repo, "A", "B")
    save_workflow(graph=graph, name="wfA", steps=[{"step_id": "s", "action": "create_node", "class_name": "B"}])
    save_workflow(graph=graph, name="wfB", steps=[{"step_id": "s", "action": "create_node", "class_name": "A"}])

    repo.attach_trigger_to_class(class_name="A", name="tA", event="create", workflow_name="wfA")
    with pytest.raises(TriggerCycleError):
        repo.attach_trigger_to_class(class_name="B", name="tB", event="create", workflow_name="wfB")


def test_attach_trigger_requires_existing_workflow(graph) -> None:
    repo = FalkorTBoxRepository(graph)
    _seed_classes(repo, "A")
    with pytest.raises(TBoxNotFoundError):
        repo.attach_trigger_to_class(class_name="A", name="tA", event="create", workflow_name="nope")


def test_disabled_trigger_does_not_fire(graph) -> None:
    repo = FalkorTBoxRepository(graph)
    _seed_classes(repo, "Order", "AuditLog")
    save_workflow(
        graph=graph,
        name="audit_order",
        steps=[{"step_id": "log", "action": "create_node", "class_name": "AuditLog", "properties": {"order_uuid": "{uuid}"}}],
    )
    repo.attach_trigger_to_class(
        class_name="Order", name="on_order_created", event="create", workflow_name="audit_order", enabled=False
    )
    upsert_abox_node(graph=graph, class_name="Order", uuid="order-2", properties={})
    rows = graph.query("MATCH (a:AuditLog) RETURN count(a)").result_set
    assert rows[0][0] == 0


def test_list_and_delete_trigger(graph) -> None:
    repo = FalkorTBoxRepository(graph)
    _seed_classes(repo, "Order", "AuditLog")
    save_workflow(graph=graph, name="wf", steps=[{"step_id": "s", "action": "create_node", "class_name": "AuditLog"}])
    repo.attach_trigger_to_class(class_name="Order", name="t1", event="create", workflow_name="wf")
    assert [t.name for t in repo.list_triggers()] == ["t1"]
    repo.delete_trigger("Order", "t1")
    assert repo.list_triggers() == []


def test_condition_gates_firing(graph) -> None:
    repo = FalkorTBoxRepository(graph)
    _seed_classes(repo, "Order", "AuditLog")
    save_workflow(
        graph=graph,
        name="audit_order",
        steps=[{"step_id": "log", "action": "create_node", "class_name": "AuditLog", "properties": {"order_uuid": "{uuid}"}}],
    )
    repo.attach_trigger_to_class(
        class_name="Order", name="on_paid", event="update", workflow_name="audit_order", condition="paid"
    )
    # paid is empty -> trigger skipped
    upsert_abox_node(graph=graph, class_name="Order", uuid="order-3", properties={"paid": ""})
    assert graph.query("MATCH (a:AuditLog) RETURN count(a)").result_set[0][0] == 0
    # paid set -> trigger fires
    upsert_abox_node(graph=graph, class_name="Order", uuid="order-3", properties={"paid": "yes"})
    assert graph.query("MATCH (a:AuditLog) RETURN count(a)").result_set[0][0] == 1


def test_parameter_map_binds_node_fields_to_workflow_params(graph) -> None:
    repo = FalkorTBoxRepository(graph)
    _seed_classes(repo, "Order", "AuditLog")
    # Workflow params (oid, amt) differ from node property names (uuid, total).
    save_workflow(
        graph=graph,
        name="audit",
        steps=[{
            "step_id": "log",
            "action": "create_node",
            "class_name": "AuditLog",
            "properties": {"order_ref": "{oid}", "amount_seen": "{amt}"},
        }],
    )
    repo.attach_trigger_to_class(
        class_name="Order",
        name="t",
        event="create",
        workflow_name="audit",
        parameter_map={"oid": "{uuid}", "amt": "{total}"},
    )
    upsert_abox_node(graph=graph, class_name="Order", uuid="o1", properties={"total": 500})

    rows = graph.query("MATCH (a:AuditLog) RETURN a.order_ref, a.amount_seen").result_set
    assert rows and rows[0] == ["o1", "500"]
    # parameter_map round-trips through storage.
    assert repo.list_triggers()[0].parameter_map == {"oid": "{uuid}", "amt": "{total}"}


def test_full_node_state_visible_on_partial_update(graph) -> None:
    # An update that writes only one field must still expose the node's other
    # stored properties to the workflow (full-node fetch, not the upsert delta).
    repo = FalkorTBoxRepository(graph)
    _seed_classes(repo, "Order", "AuditLog")
    save_workflow(
        graph=graph,
        name="audit",
        steps=[{"step_id": "log", "action": "create_node", "class_name": "AuditLog", "properties": {"seen_total": "{total}"}}],
    )
    repo.attach_trigger_to_class(
        class_name="Order", name="t", event="update", workflow_name="audit", parameter_map={"total": "{total}"}
    )
    # create writes total; trigger is on update so it does not fire yet
    upsert_abox_node(graph=graph, class_name="Order", uuid="o1", properties={"total": 999})
    assert graph.query("MATCH (a:AuditLog) RETURN count(a)").result_set[0][0] == 0
    # partial update writes only status; workflow must still see total=999 from full node
    upsert_abox_node(graph=graph, class_name="Order", uuid="o1", properties={"status": "x"})
    rows = graph.query("MATCH (a:AuditLog) RETURN a.seen_total").result_set
    assert rows and rows[0][0] == "999"


def test_max_trigger_depth_is_a_positive_int() -> None:
    assert isinstance(MAX_TRIGGER_DEPTH, int) and MAX_TRIGGER_DEPTH > 0
