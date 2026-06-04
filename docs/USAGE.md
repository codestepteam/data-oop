# Commerce Data OOP Library Usage Guide

이 라이브러리는 FalkorDB를 기반으로 TBox(스키마 정의)와 ABox(실제 데이터 노드/관계)를 객체 지향 및 DSL 방식으로 관리하고 검증할 수 있는 기능을 제공합니다.

---

## 1. TBox 정의 및 로드

TBox(클래스, 속성, 관계)를 정의할 때는 `TBoxBuilder`를 사용하여 체이닝 방식으로 동적 스키마를 구성합니다.

### A. TBox 정의 및 FalkorDB 로드 예시

```python
from data_oop import InMemoryTBoxRepository, TBoxBuilder, connect_and_load_tbox_to_falkor

# 1. 빌더를 이용해 TBox 정의
repo = InMemoryTBoxRepository()
builder = TBoxBuilder(repo)

builder.class_("Department", description="회사 부서 정보") \
    .property("name", datatype="string", required=True, unique=True) \
    .property("code", datatype="string", required=True, unique=True) \
    .end() \
    .class_("Project", description="부서 프로젝트 정보") \
    .property("title", datatype="string", required=True) \
    .property("budget", datatype="integer", required=False) \
    .end() \
    .relationship("rel_dept_runs_project", "RUNS", "Department", "Project")

# 2. FalkorDB에 TBox 스키마 로드 (Macmini의 localhost:6380, commerce_data_oop 그래프 기준)
connect_and_load_tbox_to_falkor(
    repo,
    graph_name="commerce_data_oop",
    host="localhost",
    port=6380,
    clear=True
)
```

---

## 2. ABox 노드 및 관계 조작 (CRUD)

ABox 인스턴스는 최상위 `ABox` 라벨 없이 도메인 클래스 라벨(예: `:Department`)만 사용하며, 식별자로 `uuid` 속성을 반드시 가져야 합니다.

```python
from data_oop import (
    connect_and_upsert_abox_node,
    upsert_abox_relationship,
    connect_and_clear_abox_nodes,
)
from falkordb import FalkorDB

db = FalkorDB(host="localhost", port=6380)
graph = db.select_graph("commerce_data_oop")

# 1. ABox 노드 추가/갱신 (Upsert)
dept_result = connect_and_upsert_abox_node(
    class_name="Department",
    uuid="dept-it-01",
    properties={
        "name": "IT Support",
        "code": "IT01"
    }
)
print(f"Upserted Department: {dept_result.node_id}")

proj_result = connect_and_upsert_abox_node(
    class_name="Project",
    uuid="proj-cloud-migration",
    properties={
        "title": "Cloud Migration",
        "budget": 50000
    }
)

# 2. ABox 관계 연결 (Upsert)
# 로컬 그래프 인스턴스를 직접 사용해 관계 맺기
upsert_abox_relationship(
    graph=graph,
    from_class="Department",
    from_uuid="dept-it-01",
    relationship_name="RUNS",
    to_class="Project",
    to_uuid="proj-cloud-migration"
)

# 3. ABox 노드 전체 초기화 (TBox 및 Validation 정보 보존)
connect_and_clear_abox_nodes()
```

---

## 3. ABox 검증 (Validation)

TBox에 정의된 필수값(`required`), 고유성(`unique`), 관계 조건 등을 위반하는 ABox 인스턴스를 검증하고, 검증 결과를 FalkorDB에 기록합니다.

```python
from data_oop import connect_and_run_latest_falkor_abox_validation

# 검증 수행 및 최신 결과만 FalkorDB에 저장
# 기존 ValidationRun 및 ValidationIssue 노드들을 자동 삭제 후 갱신
validation_result = connect_and_run_latest_falkor_abox_validation()

print(f"Validation Status: {validation_result.status}")
print(f"Checked Instances: {validation_result.checked_instance_count}")
print(f"Errors found: {validation_result.error_count}")
```

### 데이터베이스에 남는 검증 노드 구조

```text
(:ValidationRun)-[:HAS_ISSUE]->(:ValidationIssue)-[:AFFECTS]->(오류가 있는 ABox 노드)
```

---

## 4. 워크플로우 (Workflow) 정의 및 실행

순차적인 그래프 생성/연결 단계를 Workflow로 템플릿화하여 TBox에 정의하고, 매개변수 바인딩을 통해 동적으로 실행합니다.

```python
from data_oop import save_workflow, run_workflow
from falkordb import FalkorDB

db = FalkorDB(host="localhost", port=6380)
graph = db.select_graph("commerce_data_oop")

# 1. 워크플로우 단계 정의 (TBox 저장)
steps = [
    {
        "step_id": "create_new_project",
        "action": "create_node",
        "class_name": "Project",
        "properties": {
            "title": "{project_title}",
            "budget": "{budget}"
        }
    },
    {
        "step_id": "link_dept_to_project",
        "action": "create_relationship",
        "from_class": "Department",
        "from_uuid": "{dept_uuid}",
        "relationship_name": "RUNS",
        "to_class": "Project",
        "to_uuid": "{create_new_project.uuid}"  # 이전 단계에서 생성된 uuid 참조
    }
]

# 워크플로우 정의 저장
save_workflow(
    graph=graph,
    name="new_dept_project_workflow",
    steps=steps,
    description="새 프로젝트를 만들고 특정 부서에 연결하는 워크플로우"
)

# 2. 워크플로우 실행
params = {
    "project_title": "AI Platform Setup",
    "budget": 120000,
    "dept_uuid": "dept-it-01"
}

run_results = run_workflow(
    graph=graph,
    name="new_dept_project_workflow",
    parameters=params
)

created_proj_uuid = run_results["create_new_project"]["uuid"]
print(f"Workflow executed successfully. New project uuid: {created_proj_uuid}")
```

---

# 라이브러리 API

`from data_oop import ...` 공개 심볼로 ABox 쿼리·View·스키마·워크플로우를 전부 다룬다. 외부 프로젝트(MCP 서버 등)는 이 패키지를 SDK로 import해 쓴다.

## 시그니처 확인 — 코드가 진실원

정확한 시그니처/docstring은 문서가 아니라 패키지에서 직접 본다 (문서는 stale 가능):

```python
import data_oop
data_oop.describe_api()              # 전체 공개 API를 그룹별 + 라이브 시그니처로 출력
data_oop.describe_api(verbose=True)  # docstring 전체
help(data_oop)                       # 모듈 개요(그룹 맵 + 사용법)
help(data_oop.abox_query)            # 심볼별 상세
data_oop.__all__                     # raw export 목록
```

`py.typed` 포함 → IDE 자동완성/시그니처 팝업 네이티브 지원.

## 두 가지 호출 형태

- **`connect_and_*`** — 연결 파라미터를 받아 FalkorDB 연결까지 한 번에. 그래프 핸들 없이 호출. 외부 SDK용.
- **그래프 핸들 버전** — 이미 `graph`(FalkorDB `select_graph` 결과)를 들고 있을 때. 여러 호출에서 연결 재사용.

공통 연결 kwargs(keyword-only): `graph_name="data_oop", host="localhost", port=6380, username=None, password=None`.

## 주요 진입점 (전체는 `describe_api()`)

| 영역 | 함수 / 클래스 |
|---|---|
| ABox 읽기 | `abox_query`, `connect_and_abox_query` |
| View 집계 | `resolve_view`, `connect_and_resolve_view` |
| ABox 쓰기 | `upsert_abox_node`, `upsert_abox_relationship`, `delete_abox_element`, `clear_abox_nodes` (+ `connect_and_*`) |
| RDB 동기화 | `materialize_source`; executor: `register_executor` / `get_executor` / `fetch_rows` |
| 워크플로우 / 트리거 | `save_workflow`, `run_workflow`; `analyze_trigger_graph`, `validate_trigger_graph`, `dispatch_triggers` |
| 검증 | `run_latest_falkor_abox_validation`, `store_latest_validation_report` |
| TBox 로드 / 덤프 | `load_tbox_to_falkor`, `dump_graph_to_file`, `restore_graph_from_file` |
| 스키마 CRUD | `FalkorTBoxRepository(graph)` — class/property/interface/relationship/constraint/connector/binding/view/trigger 메서드 |
| 모델 (dataclass) | `ViewDef`, `ViewParam`, `ConnectorDef`, `SourceBinding`, `ClassDef`, ... |
| DSL / 예외 | `TBoxBuilder`, `ClassBuilder`, `WorkflowBuilder`; `TBoxError` 계열 |

## 외부 SDK 최소 예시 (MCP 등)

```python
from data_oop import connect_and_abox_query, connect_and_resolve_view

CONN = dict(host="macmini", port=6380, graph_name="data_oop")

# 1. 골드 고객 노드 조회 (read-only Cypher, 쓰기 DB 레벨 거부)
nodes = connect_and_abox_query(
    "MATCH (c:Customer) WHERE c.tier='gold' RETURN c.uuid, c", limit=50, **CONN)

# 2. tier별 매출 상위 (RDB 라이브 집계, 한 쿼리)
rows = connect_and_resolve_view(
    view_name="top_customers", filters={"tier": "gold", "limit": 10}, **CONN)
```

> View 값은 그래프에 없음(RDB에 있음). `abox_query`로 노드를 좁히고, 집계는 `resolve_view`로 따로 가져와 `key_column`으로 맞춘다.
