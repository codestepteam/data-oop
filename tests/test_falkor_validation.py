from __future__ import annotations

import pytest
import uuid
from typing import Any
from falkordb import FalkorDB

from data_oop import (
    ValidationIssue,
    ValidationReport,
    run_latest_falkor_abox_validation,
    store_latest_validation_report,
    FalkorTBoxRepository,
)


class FakeResult:
    def __init__(self, rows: list[list[Any]] | None = None) -> None:
        self.result_set = rows or []


class FakeGraph:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object] | None]] = []

    def query(
        self,
        q: str,
        params: dict[str, object] | None = None,
        timeout: int | None = None,
    ) -> FakeResult:
        self.calls.append((q, params))
        compact = " ".join(q.split())
        if "MATCH (c:ClassDef) RETURN c.name" in compact:
            return FakeResult([
                ["SalesChannel"],
            ])
        if "MATCH (n:Product) RETURN n.uuid, ID(n)" in compact:
            return FakeResult([])
        if "MATCH (n:SalesChannel) RETURN count(n)" in compact:
            return FakeResult([[1]])
        if "MATCH (c:ClassDef {name: $class_name})-[b:HAS_PROPERTY]->" in compact:
            if params and params.get("class_name") == "SalesChannel":
                return FakeResult([["channel_code", "string", True, True]])
            return FakeResult([])
        if "IMPLEMENTS" in compact and "HAS_PROPERTY" in compact:
            return FakeResult([])
        if "WHERE n.uuid IS NULL" in compact:
            return FakeResult([])
        if "WHERE n.channel_code IS NULL" in compact:
            return FakeResult([["uuid_channel_1", 7]])
        if "WHERE n.channel_code IS NOT NULL" in compact:
            return FakeResult([])
        if "MATCH (r:RelationshipDef)-[f:FROM_CLASS]->" in compact:
            return FakeResult([])
        return FakeResult([])


def test_store_latest_validation_report_deletes_old_runs_and_writes_new_run_and_issues() -> None:
    graph = FakeGraph()
    report = ValidationReport(
        (
            ValidationIssue(
                code="missing_required_property",
                severity="error",
                message="missing channel_code",
                target_kind="class",
                target_id="SalesChannel",
                metadata={
                    "className": "SalesChannel",
                    "instanceUuid": "uuid_channel_1",
                    "propertyName": "channel_code",
                },
            ),
        )
    )

    result = store_latest_validation_report(
        graph=graph,
        report=report,
        run_id="run_test",
        checked_instance_count=3,
    )

    assert result.status == "failed"
    assert result.error_count == 1
    assert result.issue_count == 1
    queries = [call[0] for call in graph.calls]
    assert any("MATCH (n:ValidationIssue) DELETE n" in query for query in queries)
    assert any("MATCH (n:ValidationRun) DELETE n" in query for query in queries)
    assert any("CREATE (:ValidationRun" in query for query in queries)
    assert any("CREATE (issue:ValidationIssue" in query for query in queries)
    assert any("AFFECTS" in query for query in queries)


def test_run_latest_falkor_abox_validation_detects_required_property_and_stores_latest() -> None:
    graph = FakeGraph()

    result = run_latest_falkor_abox_validation(graph=graph, run_id="run_abox")

    assert result.status == "failed"
    assert result.checked_instance_count == 1
    assert result.error_count == 1
    assert result.issue_count == 1
    issue_params = [
        params
        for query, params in graph.calls
        if "CREATE (issue:ValidationIssue" in query
    ][0]
    assert issue_params is not None
    assert issue_params["code"] == "missing_required_property"
    assert issue_params["class_name"] == "SalesChannel"
    assert issue_params["instance_uuid"] == "uuid_channel_1"
    assert issue_params["property_name"] == "channel_code"


@pytest.fixture(scope="module")
def falkor_graph():
    db = FalkorDB(host="localhost", port=6380)
    graph = db.select_graph("tbox_validation_test_temp")
    
    try:
        graph.delete()
    except Exception:
        pass
        
    yield graph
    
    try:
        graph.delete()
    except Exception:
        pass


def test_run_latest_falkor_abox_validation_detects_datatype_violations(falkor_graph) -> None:
    tbox_repo = FalkorTBoxRepository(falkor_graph)
    tbox_repo.create_class("User", label="User", description="A user")
    
    tbox_repo.create_property("email_addr", datatype="email")
    tbox_repo.create_property("birth_date", datatype="date")
    tbox_repo.create_property("website", datatype="url")
    tbox_repo.create_property("phone_num", datatype="phone")
    tbox_repo.create_property("score", datatype="float")
    tbox_repo.create_property("age", datatype="integer")
    tbox_repo.create_property("is_active", datatype="boolean")
    tbox_repo.create_property("user_id", datatype="uuid")

    tbox_repo.attach_property_to_class(class_name="User", property_name="email_addr")
    tbox_repo.attach_property_to_class(class_name="User", property_name="birth_date")
    tbox_repo.attach_property_to_class(class_name="User", property_name="website")
    tbox_repo.attach_property_to_class(class_name="User", property_name="phone_num")
    tbox_repo.attach_property_to_class(class_name="User", property_name="score")
    tbox_repo.attach_property_to_class(class_name="User", property_name="age")
    tbox_repo.attach_property_to_class(class_name="User", property_name="is_active")
    tbox_repo.attach_property_to_class(class_name="User", property_name="user_id")

    # Insert invalid ABox node
    node_uuid = str(uuid.uuid4())
    falkor_graph.query(
        """
        CREATE (:User {
            uuid: $uuid,
            email_addr: "not-an-email",
            birth_date: "not-a-date",
            website: "not-a-url",
            phone_num: "12",
            score: "not-a-float",
            age: 25.5,
            is_active: "not-a-bool",
            user_id: "not-a-uuid"
        })
        """,
        {"uuid": node_uuid}
    )

    result = run_latest_falkor_abox_validation(graph=falkor_graph, run_id="run_datatype_test")

    # We expect 8 errors because all 8 properties have invalid datatypes
    assert result.status == "failed"
    assert result.error_count == 8

    # Verify we can fetch the issues and see they are invalid_property_datatype
    # Let's inspect the created ValidationIssue nodes in FalkorDB
    issues_res = falkor_graph.query(
        "MATCH (r:ValidationRun)-[:HAS_ISSUE]->(i:ValidationIssue) RETURN i.propertyName, i.code ORDER BY i.propertyName"
    ).result_set

    # Match property names and codes
    expected_issues = {
        "email_addr": "invalid_property_datatype",
        "birth_date": "invalid_property_datatype",
        "website": "invalid_property_datatype",
        "phone_num": "invalid_property_datatype",
        "score": "invalid_property_datatype",
        "age": "invalid_property_datatype",
        "is_active": "invalid_property_datatype",
        "user_id": "invalid_property_datatype",
    }

    actual_issues = {row[0]: row[1] for row in issues_res}
    assert actual_issues == expected_issues
