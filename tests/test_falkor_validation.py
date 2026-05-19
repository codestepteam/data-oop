from __future__ import annotations

from typing import Any

from tbox import (
    ValidationIssue,
    ValidationReport,
    run_latest_falkor_abox_validation,
    store_latest_validation_report,
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
        if "MATCH (c:ClassDef) RETURN c.name, c.kind" in compact:
            return FakeResult([
                ["Product", "logical_entity"],
                ["SalesChannel", "entity"],
            ])
        if "MATCH (n:Product) RETURN n.id, ID(n)" in compact:
            return FakeResult([])
        if "MATCH (n:SalesChannel) RETURN count(n)" in compact:
            return FakeResult([[1]])
        if "MATCH (c:ClassDef {name: $class_name})-[b:HAS_PROPERTY]->" in compact:
            if params and params.get("class_name") == "SalesChannel":
                return FakeResult([["channel_code", "string", True, True]])
            return FakeResult([])
        if "IMPLEMENTS" in compact and "HAS_PROPERTY" in compact:
            return FakeResult([])
        if "WHERE n.channel_code IS NULL" in compact:
            return FakeResult([["channel_1", 7]])
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
                    "instanceId": "channel_1",
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
    assert issue_params["instance_id"] == "channel_1"
    assert issue_params["property_name"] == "channel_code"
