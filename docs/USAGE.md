# Commerce Data OOP Library Usage Guide

이 라이브러리는 FalkorDB를 기반으로 TBox(스키마 정의)와 ABox(실제 데이터 노드/관계)를 객체 지향 및 DSL 방식으로 관리하고 검증할 수 있는 기능을 제공합니다.

---

## 1. TBox 정의 및 로드

TBox(클래스, 속성, 관계)를 정의하는 두 가지 방법(선언형 DSL, 빌더 DSL)을 지원합니다.

### A. 선언형(Declarative) DSL (추천)

데코레이터 `@tbox_class`와 `Property` 클래스를 사용하여 Python 클래스 형태로 스키마를 정의합니다.

```python
from data_oop import (
    InMemoryTBoxRepository,
    Property,
    RelationshipSpec,
    load_tbox_from_specs,
    tbox_class,
    connect_and_load_tbox_to_falkor,
)

# 1. 클래스 및 속성 정의
@tbox_class(description="회사 부서 정보")
class Department:
    name = Property(datatype="string", required=True, unique=True)
    code = Property(datatype="string", required=True, unique=True)

@tbox_class(description="부서 프로젝트 정보")
class Project:
    title = Property(datatype="string", required=True)
    budget = Property(datatype="integer", required=False)

# 2. 인메모리 저장소에 스펙 로드 및 관계 정의
repo = InMemoryTBoxRepository()
load_tbox_from_specs(
    repo,
    classes=[Department, Project],
    relationships=[
        RelationshipSpec(
            id="rel_dept_runs_project",
            name="RUNS",
            from_class=Department,
            to_class=Project,
            required=False,
        )
    ],
)

# 3. FalkorDB에 TBox 스키마 로드 (Macmini의 localhost:6380, commerce_data_oop 그래프 기준)
from falkordb import FalkorDB
db = FalkorDB(host="localhost", port=6380)
graph = db.select_graph("commerce_data_oop")

connect_and_load_tbox_to_falkor(repo)
```

### B. 빌더(Fluent) DSL

체이닝 방식으로 TBox를 동적 생성합니다.

```python
from data_oop import InMemoryTBoxRepository, TBoxBuilder

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
