# tbox-ontology

FalkorDB 위에 최소 TBox/ABox 온톨로지 모델을 올리는 Python 라이브러리 초안입니다.

## 로컬 FalkorDB

공식 문서 기준 `falkordb/falkordb` 이미지는 서버 `6379`와 Browser `3000`을 제공합니다. 이 프로젝트는 호스트에서 Browser `3009`, FalkorDB `6380`으로 매핑합니다.

```bash
docker compose up -d
# Browser: http://localhost:3009
# FalkorDB: localhost:6380
```

## 설치/실행

```bash
uv sync --extra dev
uv run python examples/basic_usage.py
uv run pytest
```

## 코드 사용 예

```python
from tbox import Class, FalkorOntologyStore, Interface, PropertyDef, RelationshipDef

store = FalkorOntologyStore.connect(graph="tbox_demo", port=6380)
store.clear()

store.define(
    Interface("Named", properties=(PropertyDef("name", "string", required=True),)),
    Class("Person", implements=("Named",), properties=(PropertyDef("email", "string"),)),
    Class("Document", implements=("Named",), properties=(PropertyDef("body", "string"),)),
    RelationshipDef("AUTHORED", "Person", "Document", properties=(PropertyDef("role", "string"),)),
)

store.add_instance("person_alice", "Person", name="Alice", email="alice@example.com")
store.add_instance("doc_tbox", "Document", name="TBox 설계", body="ABox 검증 예제")
store.add_relation("person_alice", "AUTHORED", "doc_tbox", role="author")

report = store.validate()
report.raise_if_invalid()
```

## 핵심 API

- `PropertyDef(name, kind="string", required=False)`
- `Interface(name, properties=...)`
- `Class(name, properties=..., implements=...)`
- `RelationshipDef(name, from_class, to_class, properties=...)`
- `FalkorOntologyStore.connect(...)`
- `store.define(...)`
- `store.add_instance(...)`
- `store.add_relation(...)`
- `store.validate()`
