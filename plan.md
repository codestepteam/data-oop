# 동적 TBox 설계 정리

## 1. 현재 설계 범위

현재 단계에서는 **ABox는 다루지 않는다.**

즉, 실제 인스턴스인 다음과 같은 데이터는 아직 생성하지 않는다.

```text
(:DBConnection {id: ...})
(:Database {id: ...})
(:Table {id: ...})
(:Channel {id: ...})
```

현재 목표는 **나중에 이런 인스턴스를 만들 수 있도록 타입/속성/관계/제약을 동적으로 정의하는 TBox 라이브러리**를 설계하는 것이다.

---

## 2. 핵심 TBox 구성요소

필수 구성요소는 다음 4개다.

```text
ClassDef
InterfaceDef
PropertyDef
ConstraintDef
```

그리고 관계 정의는 별도 `RelationshipDef` 노드로 두지 않고, **ClassDef와 ClassDef를 직접 연결하는 TBox 관계의 프로퍼티**로 표현한다.

각 의미는 다음과 같다.

| 구성요소               | 의미                                                      |
| ---------------------- | --------------------------------------------------------- |
| `ClassDef`             | 실제 인스턴스가 될 수 있는 타입 정의                      |
| `InterfaceDef`         | Class가 구현할 수 있는 기능/계약 정의                     |
| `PropertyDef`          | Class 또는 Interface가 가질 수 있는 속성 정의             |
| `ConstraintDef`        | Class, Interface, Property, Relationship에 대한 제약 정의 |
| `DEFINES_RELATIONSHIP` | ClassDef와 ClassDef 사이의 관계 정의                      |

---

## 3. Class와 Interface

`ClassDef`는 구체 타입이다.

예:

```text
DBConnection
Database
Dataset
Table
Column
Channel
QueryMethod
```

`InterfaceDef`는 기능 또는 계약이다.

예:

```text
NamedResource
Connectable
QueryableSource
HasColumns
Runnable
```

관계는 다음처럼 표현한다.

```text
ClassDef -[:IMPLEMENTS]-> InterfaceDef
```

예:

```text
Table      IMPLEMENTS NamedResource
Table      IMPLEMENTS QueryableSource
Table      IMPLEMENTS HasColumns
Database   IMPLEMENTS NamedResource
Channel    IMPLEMENTS Runnable
DBConnection IMPLEMENTS Connectable
```

의미:

```text
Table은 이름을 가진 리소스다.
Table은 조회 가능한 소스다.
Table은 컬럼을 가질 수 있다.
```

---

## 4. PropertyDef

`PropertyDef`는 속성 정의다.

예:

```text
id
name
schema
description
datatype
host
port
```

속성은 Class에 직접 붙일 수도 있고 Interface에 붙일 수도 있다.

```text
ClassDef -[:HAS_PROPERTY]-> PropertyDef
InterfaceDef -[:HAS_PROPERTY]-> PropertyDef
```

예:

```text
NamedResource HAS_PROPERTY name
Table         HAS_PROPERTY schema
Column        HAS_PROPERTY datatype
DBConnection  HAS_PROPERTY host
DBConnection  HAS_PROPERTY port
```

`Table`이 `NamedResource`를 구현하면, `NamedResource`의 `name` 속성도 `Table`의 effective property가 된다.

```text
Table 직접 property:
- schema

Table이 구현한 Interface property:
- name

Table effective properties:
- schema
- name
```

---

## 5. Relationship 설계

관계 정의는 별도 노드로 만들지 않는다. **ClassDef와 ClassDef를 직접 연결하고, 그 링크의 프로퍼티에 관계 정의를 둔다.**

```text
(:ClassDef)-[:DEFINES_RELATIONSHIP { ... }]->(:ClassDef)
```

예:

```text
(:ClassDef {name: "Database"})
  -[:DEFINES_RELATIONSHIP {
    id: "uuid",
    name: "HAS_TABLE",
    minCount: 0,
    maxCount: null,
    required: false
  }]->
(:ClassDef {name: "Table"})
```

의미:

```text
Database 인스턴스는 HAS_TABLE 관계로 Table 인스턴스를 가리킬 수 있다.
```

관계 방향은 그래프 링크 방향으로 표현한다.

```text
from ClassDef -> to ClassDef
```

따라서 `in/out`, `from_classes`, `to_classes` 같은 별도 필드는 두지 않는다.

---

## 6. Relationship 값 객체

Python에서는 관계 정의를 다루기 위한 값 객체만 둔다. 그래프에는 독립 노드로 저장하지 않는다.

```python
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
```

`id`는 UUID/ULID 같은 무의미한 식별자로 둔다. 관계의 의미는 `name`, `from_class`, `to_class`가 표현한다.

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
is_relationship_allowed(
    from_class="Database",
    relationship_name="HAS_TABLE",
    to_class="Table",
)
```

검사 방식:

```cypher
MATCH (:ClassDef {name: $from_class})
      -[r:DEFINES_RELATIONSHIP]->
      (:ClassDef {name: $to_class})
WHERE r.name = $relationship_name
RETURN count(r) > 0 AS allowed
```

---

## 9. 전체 구조 예시

```text
ClassDef(Table)
 ├─ IMPLEMENTS NamedResource
 ├─ IMPLEMENTS QueryableSource
 ├─ IMPLEMENTS HasColumns
 └─ HAS_PROPERTY schema
```

Class 간 관계 정의는 Class 내부 목록이 아니라 Class 간 링크로 표현한다.

```text
Database   - DEFINES_RELATIONSHIP {name: HAS_TABLE}  -> Table
Dataset    - DEFINES_RELATIONSHIP {name: HAS_TABLE}  -> Table
Table      - DEFINES_RELATIONSHIP {name: HAS_COLUMN} -> Column
QueryMethod - DEFINES_RELATIONSHIP {name: READS_FROM} -> Table
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
    required: bool = False
    unique: bool = False
    description: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


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
    def create_property(self, name: str, *, datatype: str = "unknown", required: bool = False, unique: bool = False, description: str | None = None, metadata: dict[str, Any] | None = None, merge: bool = True) -> PropertyDef: ...
    def get_property(self, name: str) -> PropertyDef | None: ...
    def update_property(self, name: str, *, datatype: str | None = None, required: bool | None = None, unique: bool | None = None, description: str | None = None, metadata: dict[str, Any] | None = None) -> PropertyDef: ...
    def delete_property(self, name: str, *, detach: bool = False) -> None: ...
    def list_properties(self, *, owner_class: str | None = None, owner_interface: str | None = None) -> list[PropertyDef]: ...

    # Property attachment
    def attach_property_to_class(self, *, class_name: str, property_name: str, required: bool | None = None, unique: bool | None = None) -> None: ...
    def attach_property_to_interface(self, *, interface_name: str, property_name: str, required: bool | None = None, unique: bool | None = None) -> None: ...
    def detach_property_from_class(self, *, class_name: str, property_name: str) -> None: ...
    def detach_property_from_interface(self, *, interface_name: str, property_name: str) -> None: ...
    def get_properties_of_class(self, class_name: str, *, include_interfaces: bool = True) -> list[PropertyDef]: ...
    def get_properties_of_interface(self, interface_name: str) -> list[PropertyDef]: ...

    # Relationship
    def define_relationship(self, *, id: str, name: str, from_class: str, to_class: str, min_count: int = 0, max_count: int | None = None, required: bool = False, description: str | None = None, metadata: dict[str, Any] | None = None, merge: bool = True) -> RelationshipDef: ...
    def get_relationship(self, id: str) -> RelationshipDef | None: ...
    def update_relationship(self, id: str, *, name: str | None = None, from_class: str | None = None, to_class: str | None = None, min_count: int | None = None, max_count: int | None = None, required: bool | None = None, description: str | None = None, metadata: dict[str, Any] | None = None) -> RelationshipDef: ...
    def delete_relationship(self, id: str) -> None: ...
    def list_relationships(self, *, from_class: str | None = None, to_class: str | None = None, name: str | None = None) -> list[RelationshipDef]: ...
    def is_relationship_allowed(self, *, from_class: str, relationship_name: str, to_class: str) -> bool: ...

    # Constraint
    def create_constraint(self, *, id: str, kind: str, target_kind: Literal["class", "interface", "property", "relationship"], target_id: str, property_names: tuple[str, ...] = (), expression: str | None = None, severity: Literal["info", "warning", "error"] = "error", description: str | None = None, metadata: dict[str, Any] | None = None, merge: bool = True) -> ConstraintDef: ...
    def get_constraint(self, id: str) -> ConstraintDef | None: ...
    def update_constraint(self, id: str, *, kind: str | None = None, target_kind: Literal["class", "interface", "property", "relationship"] | None = None, target_id: str | None = None, property_names: tuple[str, ...] | None = None, expression: str | None = None, severity: Literal["info", "warning", "error"] | None = None, description: str | None = None, metadata: dict[str, Any] | None = None) -> ConstraintDef: ...
    def delete_constraint(self, id: str) -> None: ...
    def list_constraints(self, *, target_kind: str | None = None, target_id: str | None = None, kind: str | None = None) -> list[ConstraintDef]: ...
```

---

## 12. 최종 결론

현재 설계에서는 다음을 제거한다.

```text
ABox
Builder
RelationshipRule
RelationshipDef 노드
QueryPatternDef
DialectDef
```

남는 핵심은 다음이다.

```text
ClassDef
InterfaceDef
PropertyDef
RelationshipDef 값 객체
ConstraintDef
TBoxRepository
TBoxValidator
```

관계 정의는 다음 방식으로 처리한다.

```text
ClassDef -[:DEFINES_RELATIONSHIP {id, name, minCount, maxCount, required}]-> ClassDef
```

`id`는 UUID/ULID처럼 의미 없는 값으로 둔다. 관계 의미는 `from_class`, `name`, `to_class`가 표현한다.
