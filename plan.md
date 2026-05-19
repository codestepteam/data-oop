# 동적 TBox 라이브러리 설계 계획

## 1. 현재 설계 범위

현재 단계에서는 **ABox는 다루지 않는다.**

즉, 실제 인스턴스인 다음과 같은 데이터는 아직 생성하지 않는다.

```text
(:DBConnection {id: ...})
(:Database {id: ...})
(:Table {id: ...})
(:Channel {id: ...})
```

현재 목표는 **나중에 이런 인스턴스를 만들 수 있도록 타입/속성/관계/제약을 동적으로 정의하는 TBox 라이브러리**를 설계하고 구현하는 것이다.

---

## 2. 핵심 설계 결정

이번 설계의 핵심 결정은 다음과 같다.

1. `PropertyDef`는 **속성 자체의 공통 정의**만 가진다.
2. `required`, `unique`, `nullable`, `default` 같은 적용 제약은 `HAS_PROPERTY` edge에 둔다.
3. `RelationshipDef`는 독립 노드로 둔다.
4. `RelationshipDef`도 `PropertyDef`를 가질 수 있다.
5. Relationship의 cardinality 제약인 `minCount`, `maxCount`, `required`는 `RelationshipDef -[:FROM_CLASS]-> ClassDef` edge에 둔다.
6. 복잡한 제약은 `ConstraintDef`로 표현한다.
7. 저장소 API는 `TBoxRepository`, 검증은 `TBoxValidator`가 담당한다.

---

## 3. 핵심 TBox 구성요소

```text
ClassDef
InterfaceDef
PropertyDef
RelationshipDef
ConstraintDef
```

| 구성요소          | 의미                                                        |
| ----------------- | ----------------------------------------------------------- |
| `ClassDef`        | 실제 인스턴스가 될 수 있는 타입 정의                        |
| `InterfaceDef`    | Class가 구현할 수 있는 기능/계약 정의                       |
| `PropertyDef`     | Class, Interface, Relationship이 사용할 수 있는 속성 정의   |
| `RelationshipDef` | ClassDef 간 허용 관계 정의                                  |
| `ConstraintDef`   | 기본 edge 제약으로 표현하기 어려운 복합 제약 정의           |

---

## 4. 전체 그래프 모델

### 4.1 Class / Interface

```text
(:ClassDef)-[:IMPLEMENTS]->(:InterfaceDef)
```

예:

```text
Table        IMPLEMENTS NamedResource
Table        IMPLEMENTS QueryableSource
Table        IMPLEMENTS HasColumns
Database     IMPLEMENTS NamedResource
Channel      IMPLEMENTS Runnable
DBConnection IMPLEMENTS Connectable
```

---

### 4.2 Property 정의와 적용

`PropertyDef` 노드는 속성 자체만 정의한다.

```text
(:PropertyDef {name, datatype, description, metadata})
```

속성이 Class, Interface, Relationship에 적용될 때의 제약은 `HAS_PROPERTY` edge에 둔다.

```text
(:ClassDef)-[:HAS_PROPERTY {required, unique, nullable, default}]->(:PropertyDef)
(:InterfaceDef)-[:HAS_PROPERTY {required, unique, nullable, default}]->(:PropertyDef)
(:RelationshipDef)-[:HAS_PROPERTY {required, unique, nullable, default}]->(:PropertyDef)
```

예:

```text
(:PropertyDef {name: "name", datatype: "string"})
(:PropertyDef {name: "schema", datatype: "string"})
(:PropertyDef {name: "datatype", datatype: "string"})
```

```text
(:InterfaceDef {name: "NamedResource"})
  -[:HAS_PROPERTY {required: true, unique: false}]->
(:PropertyDef {name: "name"})

(:ClassDef {name: "Table"})
  -[:HAS_PROPERTY {required: true, unique: true}]->
(:PropertyDef {name: "schema"})

(:ClassDef {name: "Column"})
  -[:HAS_PROPERTY {required: true, unique: false}]->
(:PropertyDef {name: "name"})
```

핵심은 `name`이라는 속성 정의는 하나지만, `Table.name`, `Column.name`, `Database.name`에서의 제약은 각각 다를 수 있다는 점이다.

---

## 5. PropertyDef 설계

### 5.1 PropertyDef는 공통 정의만 가진다

```python
@dataclass(frozen=True)
class PropertyDef:
    name: str
    datatype: str = "unknown"
    description: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
```

`PropertyDef`에는 `required`, `unique`를 두지 않는다.

이유:

```text
PropertyDef(name="name", unique=True)
```

라고 하면 다음 의미가 모호해진다.

```text
1. 모든 Class의 name이 전역 unique인가?
2. 각 Class 안에서만 name이 unique인가?
3. 특정 Class에 붙을 때만 unique인가?
```

따라서 `unique`, `required`는 속성 자체가 아니라 **속성이 어떤 owner에 붙었는지**에 대한 제약으로 본다.

---

### 5.2 PropertyBinding

Python에서는 edge property를 다루기 위한 값 객체를 둔다.

```python
@dataclass(frozen=True)
class PropertyBinding:
    owner_kind: Literal["class", "interface", "relationship"]
    owner_id: str
    property_name: str
    required: bool = False
    unique: bool = False
    nullable: bool = True
    default: Any | None = None
    description: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
```

그래프에는 별도 `PropertyBinding` 노드를 만들지 않는다.

실제 저장은 다음 edge에 한다.

```text
(owner)-[:HAS_PROPERTY {required, unique, nullable, default, metadata}]->(:PropertyDef)
```

---

### 5.3 Effective Property

Class의 최종 속성은 다음을 합친 결과다.

```text
1. ClassDef가 직접 가진 Property
2. ClassDef가 구현한 InterfaceDef의 Property
```

예:

```text
Table 직접 property:
- schema

Table이 구현한 Interface property:
- name

Table effective properties:
- schema
- name
```

반환 모델은 단순 `PropertyDef`보다 `EffectivePropertyDef`가 낫다.

```python
@dataclass(frozen=True)
class EffectivePropertyDef:
    property: PropertyDef
    binding: PropertyBinding
    source_kind: Literal["class", "interface", "relationship"]
    source_id: str
```

---

## 6. RelationshipDef 설계

### 6.1 RelationshipDef는 노드로 둔다

관계에도 속성 정의가 필요할 수 있으므로 `RelationshipDef`는 독립 노드로 둔다.

예:

```text
READS_FROM.query
READS_FROM.mode
AUTHORED.role
HAS_COLUMN.ordinal
```

edge에는 다시 edge를 붙일 수 없기 때문에, 관계가 속성을 가지려면 `RelationshipDef`는 노드여야 한다.

---

### 6.2 RelationshipDef 그래프 구조

`RelationshipDef`는 source class와 target class를 모두 명시적으로 edge로 가진다.

```text
(:RelationshipDef {id, name, description, metadata})
  -[:FROM_CLASS {minCount, maxCount, required}]->
(:ClassDef)

(:RelationshipDef)
  -[:TO_CLASS]->
(:ClassDef)
```

예:

```text
(:RelationshipDef {
    id: "550e8400-e29b-41d4-a716-446655440001",
    name: "HAS_TABLE"
  })
  -[:FROM_CLASS {
    minCount: 0,
    maxCount: null,
    required: false
  }]->
(:ClassDef {name: "Database"})

(:RelationshipDef {id: "550e8400-e29b-41d4-a716-446655440001"})
  -[:TO_CLASS]->
(:ClassDef {name: "Table"})
```

의미:

```text
Database 인스턴스는 HAS_TABLE 관계로 Table 인스턴스를 가리킬 수 있다.
```

방향은 다음과 같이 해석한다.

```text
RelationshipDef -[:FROM_CLASS]-> source ClassDef
RelationshipDef -[:TO_CLASS]-> target ClassDef
```

따라서 `RelationshipDef` 노드에는 `from_class`, `to_class`를 중복 저장하지 않는다.
Python 값 객체로 반환할 때만 인접 노드를 읽어서 채운다.

---

### 6.3 RelationshipDef도 PropertyDef를 가진다

```text
(:RelationshipDef)-[:HAS_PROPERTY {required, unique, nullable, default}]->(:PropertyDef)
```

예:

```text
(:RelationshipDef {name: "READS_FROM"})
  -[:HAS_PROPERTY {required: false}]->
(:PropertyDef {name: "query", datatype: "string"})

(:RelationshipDef {name: "HAS_COLUMN"})
  -[:HAS_PROPERTY {required: true, unique: false}]->
(:PropertyDef {name: "ordinal", datatype: "integer"})
```

의미:

```text
READS_FROM 관계 인스턴스는 query 속성을 가질 수 있다.
HAS_COLUMN 관계 인스턴스는 ordinal 속성을 가져야 한다.
```

---

### 6.4 RelationshipDef의 식별 기준

`RelationshipDef.id`는 UUID/ULID 같은 무의미한 식별자다.

관계의 의미는 다음 semantic key가 표현한다.

```text
(from_class, relationship_name, to_class)
```

예:

```text
(Database, HAS_TABLE, Table)
(Dataset, HAS_TABLE, Table)
(Table, HAS_COLUMN, Column)
```

같은 semantic key가 중복 생성되면 안 된다.

---

## 7. Relationship 예시

```python
repo.define_relationship(
    id="550e8400-e29b-41d4-a716-446655440001",
    name="HAS_TABLE",
    from_class="Database",
    to_class="Table",
)

repo.define_relationship(
    id="550e8400-e29b-41d4-a716-446655440002",
    name="HAS_TABLE",
    from_class="Dataset",
    to_class="Table",
)

repo.define_relationship(
    id="550e8400-e29b-41d4-a716-446655440003",
    name="HAS_COLUMN",
    from_class="Table",
    to_class="Column",
    min_count=1,
)
```

허용되는 관계:

```text
Database - HAS_TABLE  -> Table
Dataset  - HAS_TABLE  -> Table
Table    - HAS_COLUMN -> Column
```

---

## 8. Relationship 허용 여부 검사

```python
repo.is_relationship_allowed(
    from_class="Database",
    relationship_name="HAS_TABLE",
    to_class="Table",
)
```

검사 Cypher:

```cypher
MATCH (r:RelationshipDef {name: $relationship_name})
      -[:FROM_CLASS]->
      (:ClassDef {name: $from_class})
MATCH (r)
      -[:TO_CLASS]->
      (:ClassDef {name: $to_class})
RETURN count(r) > 0 AS allowed
```

---

## 9. ConstraintDef 설계

기본 제약은 edge에 둔다.

```text
HAS_PROPERTY.required
HAS_PROPERTY.unique
HAS_PROPERTY.nullable
FROM_CLASS.minCount
FROM_CLASS.maxCount
FROM_CLASS.required
```

`ConstraintDef`는 다음처럼 edge property만으로 표현하기 어려운 복합 제약을 위해 둔다.

예:

```text
- name은 정규식 ^[a-zA-Z][a-zA-Z0-9_]*$ 를 만족해야 한다
- port는 1 이상 65535 이하여야 한다
- host와 port는 함께 있어야 한다
- Table의 (schema, name)은 복합 unique여야 한다
- HAS_COLUMN.ordinal은 Table 안에서 unique여야 한다
```

저장 구조:

```text
(:ConstraintDef {id, kind, expression, severity, description, metadata})
  -[:CONSTRAINS]->
(:ClassDef | :InterfaceDef | :PropertyDef | :RelationshipDef)
```

단, 특정 property 조합을 대상으로 하는 경우 `ConstraintDef.propertyNames`에 이름 목록을 둔다.

```text
(:ConstraintDef {
  id: "...",
  kind: "composite_unique",
  propertyNames: ["schema", "name"]
})-[:CONSTRAINS]->(:ClassDef {name: "Table"})
```

---

## 10. Python 데이터 모델 최종안

```python
from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass(frozen=True)
class ClassDef:
    name: str
    label: str | None = None
    description: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class InterfaceDef:
    name: str
    description: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PropertyDef:
    name: str
    datatype: str = "unknown"
    description: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PropertyBinding:
    owner_kind: Literal["class", "interface", "relationship"]
    owner_id: str
    property_name: str
    required: bool = False
    unique: bool = False
    nullable: bool = True
    default: Any | None = None
    description: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EffectivePropertyDef:
    property: PropertyDef
    binding: PropertyBinding
    source_kind: Literal["class", "interface", "relationship"]
    source_id: str


@dataclass(frozen=True)
class RelationshipDef:
    id: str
    name: str
    from_class: str
    to_class: str
    min_count: int = 0
    max_count: int | None = None
    required: bool = False
    description: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ConstraintDef:
    id: str
    kind: str
    target_kind: Literal["class", "interface", "property", "relationship"]
    target_id: str
    property_names: tuple[str, ...] = ()
    expression: str | None = None
    severity: Literal["info", "warning", "error"] = "error"
    description: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
```

주의:

```text
RelationshipDef.min_count / max_count / required는 Python 값 객체에는 포함하지만,
그래프 저장 시에는 RelationshipDef -[:FROM_CLASS]-> ClassDef edge property로 저장한다.
```

---

## 11. Repository API 최종안

Builder는 두지 않는다.

동적 추가/수정은 `TBoxRepository`에서 직접 처리한다.

```python
class TBoxRepository:
    # Class
    def create_class(self, name: str, *, label: str | None = None, description: str | None = None, metadata: dict[str, Any] | None = None, merge: bool = True) -> ClassDef: ...
    def get_class(self, name: str) -> ClassDef | None: ...
    def update_class(self, name: str, *, label: str | None = None, description: str | None = None, metadata: dict[str, Any] | None = None) -> ClassDef: ...
    def delete_class(self, name: str, *, detach: bool = False) -> None: ...
    def list_classes(self, *, implements: str | None = None, has_property: str | None = None) -> list[ClassDef]: ...

    # Interface
    def create_interface(self, name: str, *, description: str | None = None, metadata: dict[str, Any] | None = None, merge: bool = True) -> InterfaceDef: ...
    def get_interface(self, name: str) -> InterfaceDef | None: ...
    def update_interface(self, name: str, *, description: str | None = None, metadata: dict[str, Any] | None = None) -> InterfaceDef: ...
    def delete_interface(self, name: str, *, detach: bool = False) -> None: ...
    def list_interfaces(self, *, implemented_by: str | None = None, has_property: str | None = None) -> list[InterfaceDef]: ...

    # Implements
    def implement_interface(self, *, class_name: str, interface_name: str) -> None: ...
    def remove_interface(self, *, class_name: str, interface_name: str) -> None: ...
    def class_implements(self, *, class_name: str, interface_name: str) -> bool: ...
    def get_interfaces_of_class(self, class_name: str) -> list[InterfaceDef]: ...
    def get_classes_of_interface(self, interface_name: str) -> list[ClassDef]: ...

    # Property
    def create_property(self, name: str, *, datatype: str = "unknown", description: str | None = None, metadata: dict[str, Any] | None = None, merge: bool = True) -> PropertyDef: ...
    def get_property(self, name: str) -> PropertyDef | None: ...
    def update_property(self, name: str, *, datatype: str | None = None, description: str | None = None, metadata: dict[str, Any] | None = None) -> PropertyDef: ...
    def delete_property(self, name: str, *, detach: bool = False) -> None: ...
    def list_properties(self, *, owner_class: str | None = None, owner_interface: str | None = None, owner_relationship: str | None = None) -> list[PropertyDef]: ...

    # Property attachment
    def attach_property_to_class(self, *, class_name: str, property_name: str, required: bool = False, unique: bool = False, nullable: bool = True, default: Any | None = None, metadata: dict[str, Any] | None = None) -> PropertyBinding: ...
    def attach_property_to_interface(self, *, interface_name: str, property_name: str, required: bool = False, unique: bool = False, nullable: bool = True, default: Any | None = None, metadata: dict[str, Any] | None = None) -> PropertyBinding: ...
    def attach_property_to_relationship(self, *, relationship_id: str, property_name: str, required: bool = False, unique: bool = False, nullable: bool = True, default: Any | None = None, metadata: dict[str, Any] | None = None) -> PropertyBinding: ...

    def detach_property_from_class(self, *, class_name: str, property_name: str) -> None: ...
    def detach_property_from_interface(self, *, interface_name: str, property_name: str) -> None: ...
    def detach_property_from_relationship(self, *, relationship_id: str, property_name: str) -> None: ...

    def get_properties_of_class(self, class_name: str, *, include_interfaces: bool = True) -> list[EffectivePropertyDef]: ...
    def get_properties_of_interface(self, interface_name: str) -> list[EffectivePropertyDef]: ...
    def get_properties_of_relationship(self, relationship_id: str) -> list[EffectivePropertyDef]: ...

    # Relationship
    def define_relationship(self, *, id: str, name: str, from_class: str, to_class: str, min_count: int = 0, max_count: int | None = None, required: bool = False, description: str | None = None, metadata: dict[str, Any] | None = None, merge: bool = True) -> RelationshipDef: ...
    def get_relationship(self, id: str) -> RelationshipDef | None: ...
    def update_relationship(self, id: str, *, name: str | None = None, min_count: int | None = None, max_count: int | None = None, required: bool | None = None, description: str | None = None, metadata: dict[str, Any] | None = None) -> RelationshipDef: ...
    def move_relationship(self, id: str, *, from_class: str, to_class: str) -> RelationshipDef: ...
    def delete_relationship(self, id: str, *, detach: bool = False) -> None: ...
    def list_relationships(self, *, from_class: str | None = None, to_class: str | None = None, name: str | None = None) -> list[RelationshipDef]: ...
    def is_relationship_allowed(self, *, from_class: str, relationship_name: str, to_class: str) -> bool: ...

    # Constraint
    def create_constraint(self, *, id: str, kind: str, target_kind: Literal["class", "interface", "property", "relationship"], target_id: str, property_names: tuple[str, ...] = (), expression: str | None = None, severity: Literal["info", "warning", "error"] = "error", description: str | None = None, metadata: dict[str, Any] | None = None, merge: bool = True) -> ConstraintDef: ...
    def get_constraint(self, id: str) -> ConstraintDef | None: ...
    def update_constraint(self, id: str, *, kind: str | None = None, target_kind: Literal["class", "interface", "property", "relationship"] | None = None, target_id: str | None = None, property_names: tuple[str, ...] | None = None, expression: str | None = None, severity: Literal["info", "warning", "error"] | None = None, description: str | None = None, metadata: dict[str, Any] | None = None) -> ConstraintDef: ...
    def delete_constraint(self, id: str) -> None: ...
    def list_constraints(self, *, target_kind: str | None = None, target_id: str | None = None, kind: str | None = None) -> list[ConstraintDef]: ...
```

주의:

```text
update_relationship()은 from_class, to_class를 직접 바꾸지 않는다.
endpoint 변경은 move_relationship()에서 명시적으로 처리한다.
```

---

## 12. Validation 설계

### 12.1 Validation 목적

`TBoxValidator`는 TBox 정의 자체가 일관적인지 확인한다.

현재 단계에서는 ABox 인스턴스를 만들지 않으므로, 실제 데이터 검증이 아니라 **스키마/온톨로지 정의 검증**만 한다.

---

### 12.2 Validation 데이터 모델

```python
@dataclass(frozen=True)
class ValidationIssue:
    code: str
    severity: Literal["info", "warning", "error"]
    message: str
    target_kind: Literal["class", "interface", "property", "relationship", "constraint", "edge"]
    target_id: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ValidationReport:
    issues: tuple[ValidationIssue, ...] = ()

    @property
    def valid(self) -> bool: ...
    def errors(self) -> list[ValidationIssue]: ...
    def warnings(self) -> list[ValidationIssue]: ...
    def raise_if_invalid(self) -> None: ...
```

---

### 12.3 TBoxValidator API

```python
class TBoxValidator:
    def __init__(self, repo: TBoxRepository) -> None: ...

    def validate_tbox(self) -> ValidationReport: ...
    def validate_class(self, class_name: str) -> ValidationReport: ...
    def validate_interface(self, interface_name: str) -> ValidationReport: ...
    def validate_relationship(self, relationship_id: str) -> ValidationReport: ...
    def validate_constraint(self, constraint_id: str) -> ValidationReport: ...

    def get_effective_class_schema(self, class_name: str) -> EffectiveClassSchema: ...
    def get_effective_relationship_schema(self, relationship_id: str) -> EffectiveRelationshipSchema: ...
```

---

### 12.4 Effective Schema 모델

```python
@dataclass(frozen=True)
class EffectiveClassSchema:
    class_def: ClassDef
    interfaces: tuple[InterfaceDef, ...]
    properties: tuple[EffectivePropertyDef, ...]
    outgoing_relationships: tuple[RelationshipDef, ...]
    incoming_relationships: tuple[RelationshipDef, ...]
    constraints: tuple[ConstraintDef, ...]


@dataclass(frozen=True)
class EffectiveRelationshipSchema:
    relationship_def: RelationshipDef
    properties: tuple[EffectivePropertyDef, ...]
    constraints: tuple[ConstraintDef, ...]
```

---

### 12.5 기본 검증 항목

#### 식별자 검증

```text
- ClassDef.name 중복 없음
- InterfaceDef.name 중복 없음
- PropertyDef.name 중복 없음
- RelationshipDef.id 중복 없음
- ConstraintDef.id 중복 없음
- 이름 규칙 위반 없음: ^[A-Za-z][A-Za-z0-9_]*$
```

#### Property 검증

```text
- PropertyDef.datatype이 등록된 타입인지 확인
- HAS_PROPERTY edge의 required/unique/nullable/default 값이 올바른 타입인지 확인
- default 값이 PropertyDef.datatype과 호환되는지 확인
- 같은 owner에 같은 property가 중복 연결되지 않았는지 확인
```

#### Interface / Class 검증

```text
- Class가 구현한 Interface가 실제 존재하는지 확인
- effective property 계산 중 충돌이 없는지 확인
- 여러 Interface에서 같은 Property를 가져올 때 binding 제약이 병합 가능한지 확인
- Class 직접 Property와 Interface Property가 충돌하지 않는지 확인
```

기본 병합 규칙:

```text
required: 하나라도 true면 true
unique: 하나라도 true면 true
nullable: 하나라도 false면 false
default: 여러 source가 서로 다른 default를 제공하면 warning/error
```

#### Relationship 검증

```text
- RelationshipDef가 정확히 하나의 source Class로 FROM_CLASS 연결되는지 확인
- RelationshipDef가 정확히 하나의 target Class로 TO_CLASS 연결되는지 확인
- (from_class, relationship_name, to_class) semantic key 중복 없음
- FROM_CLASS.minCount >= 0
- FROM_CLASS.maxCount is None 또는 FROM_CLASS.maxCount >= FROM_CLASS.minCount
- FROM_CLASS.required=True이면 FROM_CLASS.minCount >= 1 이어야 함
- RelationshipDef의 HAS_PROPERTY edge가 유효한 PropertyDef를 가리키는지 확인
```

#### Constraint 검증

```text
- ConstraintDef target이 존재하는지 확인
- target_kind와 실제 target node label이 일치하는지 확인
- property_names가 target의 effective property에 존재하는지 확인
- severity 값이 info/warning/error 중 하나인지 확인
- kind별 필수 필드가 존재하는지 확인
```

---

## 13. 저장소 초기화와 Index / Constraint

FalkorDB에는 가능한 범위에서 unique/mandatory constraint와 index를 만든다.

필수 후보:

```text
ClassDef.name unique
InterfaceDef.name unique
PropertyDef.name unique
RelationshipDef.id unique
ConstraintDef.id unique
```

조회 최적화 후보:

```text
RelationshipDef.name index
ConstraintDef.kind index
HAS_PROPERTY edge property index: required, unique
FROM_CLASS edge property index: minCount, maxCount, required
```

단, DB constraint만으로 표현하기 어려운 것은 repository/validator 레벨에서 보장한다.

대표 예:

```text
(from_class, relationship_name, to_class) semantic key unique
RelationshipDef가 정확히 하나의 source/target을 갖는지
Interface property 병합 충돌 여부
```

---

## 14. 구현 우선순위

### Phase 1. Core model

```text
- dataclass 모델 정의
- TBoxRepository interface 정의
- FalkorDB repository skeleton 작성
- ClassDef / InterfaceDef / PropertyDef CRUD
```

### Phase 2. Property binding

```text
- HAS_PROPERTY edge 생성/삭제/조회
- Class/Interface effective property 계산
- PropertyBinding / EffectivePropertyDef 구현
```

### Phase 3. RelationshipDef node

```text
- RelationshipDef 노드 생성
- RelationshipDef -[:FROM_CLASS {minCount, maxCount, required}]-> ClassDef 저장
- RelationshipDef -[:TO_CLASS]-> ClassDef 저장
- RelationshipDef -[:HAS_PROPERTY]-> PropertyDef 지원
- is_relationship_allowed 구현
```

### Phase 4. ConstraintDef

```text
- ConstraintDef CRUD
- ConstraintDef -[:CONSTRAINS]-> target 저장
- property_names 기반 복합 제약 표현
```

### Phase 5. Validation

```text
- ValidationIssue / ValidationReport 구현
- TBoxValidator 구현
- validate_tbox / validate_class / validate_relationship 구현
- effective schema API 구현
```

---

## 15. 최종 결론

최종 구조는 다음과 같다.

```text
ClassDef
InterfaceDef
PropertyDef
RelationshipDef
ConstraintDef
PropertyBinding 값 객체
EffectivePropertyDef 값 객체
TBoxRepository
TBoxValidator
```

핵심 그래프 패턴:

```text
(:ClassDef)-[:IMPLEMENTS]->(:InterfaceDef)

(:ClassDef)-[:HAS_PROPERTY {required, unique, nullable, default}]->(:PropertyDef)
(:InterfaceDef)-[:HAS_PROPERTY {required, unique, nullable, default}]->(:PropertyDef)
(:RelationshipDef)-[:HAS_PROPERTY {required, unique, nullable, default}]->(:PropertyDef)

(:RelationshipDef)-[:FROM_CLASS {minCount, maxCount, required}]->(:ClassDef)
(:RelationshipDef)-[:TO_CLASS]->(:ClassDef)

(:ConstraintDef)-[:CONSTRAINS]->(:ClassDef | :InterfaceDef | :PropertyDef | :RelationshipDef)
```

이 설계에서는 `PropertyDef`와 `RelationshipDef` 자체는 공통 정의만 가진다.
실제 적용 제약은 edge에 둔다.

따라서 다음이 가능하다.

```text
같은 PropertyDef(name)를 Table에서는 unique로 사용하고,
Column에서는 unique 없이 사용할 수 있다.

같은 RelationshipDef 구조에서 관계 자체에도 PropertyDef를 붙일 수 있다.

Class/Interface/Relationship 모두 동일한 방식으로 property를 가진다.
```
