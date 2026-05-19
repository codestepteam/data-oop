# Project Agent Notes

- `README.md`는 유지하지 않는다.
- 라이브 TBox는 FalkorDB graph `commerce_tbox`에 있다.
- 커머스 TBox preset 파일은 유지하지 않는다.
- 커머스 TBox 변경은 사용자가 요청한 경우 FalkorDB `commerce_tbox` live graph를 직접 갱신한다.
- ABox validation은 버전/revision 없이 최신 TBox 기준으로만 실행한다.
- validation 실행 시 기존 `ValidationRun`/`ValidationIssue`는 모두 삭제하고 최신 결과만 남긴다.
- TBox 정의 노드는 공통 label `TBox`로 묶는다. 예: `(:TBox:ClassDef)`, `(:TBox:PropertyDef)`.
- ABox 인스턴스는 공통 `ABox` label로 묶지 않는다. 도메인 class label만 사용한다. 예: `(:SalesChannel)`.
- 모든 실제 graph node는 기본 식별자로 `uuid` property를 가져야 한다.
- `Identifiable` interface와 `id` PropertyDef는 사용하지 않는다.

## FalkorDB 접속

```text
Browser URL: http://macmini:3009
Browser 내부 DB Host: localhost
Browser 내부 DB Port: 6379
Python/loader Host: localhost 또는 macmini
Python/loader Port: 6380
Graph: commerce_tbox
Username: default 또는 공백
Password: 공백
```

## 현재 커머스 ClassDef

```text
Product          kind=logical_entity
ProductVariant   kind=logical_entity
Inventory        kind=entity
SalesChannel     kind=entity
DataSource       kind=entity
Table            kind=entity
QueryDefinition  kind=entity
```

## 모델링 원칙

- TBox/ABox 구분은 ABox를 묶는 방식이 아니라 TBox를 `:TBox` label로 묶는 방식으로 한다.
- `ClassDef.kind`는 `entity`와 `logical_entity` 두 값만 사용한다.
- `entity`: Falkor에 실제 노드/인스턴스를 만들 수 있는 클래스다.
- `logical_entity`: 외부 시스템에 이미 존재하고 Falkor에는 인스턴스를 만들지 않는 클래스다.
- `Product`, `ProductVariant`는 ezAdmin 등에 이미 존재하는 데이터를 논리적으로 연결하는 용도다.
- `Product`는 채널별 상품이며 `Product -[:LISTED_ON]-> SalesChannel`로 채널에 묶인다.
- `Product -[:HAS_VARIANT]-> ProductVariant` 구조로 채널별 상품 하위에 variant가 존재한다.
- `ProductVariant.ezadmin_sku`는 variant별 통합 ezAdmin SKU 프로퍼티다.
- `SalesChannel`은 logical entity가 아니다. 채널별 실제 노드를 만들 수 있는 entity다.
- `SalesChannel`에는 `status`를 두지 않는다.
- `Inventory`도 logical entity가 아니다. 재고 레코드/노드를 만들 수 있는 entity다.
- `Inventory`는 `Inventory -[:FOR_VARIANT]-> ProductVariant`로만 연결한다. `Inventory -[:FOR_CHANNEL]-> SalesChannel`은 사용하지 않는다.
- 모든 node의 기본 식별자는 `uuid`다. 도메인/외부 시스템 식별자는 별도 프로퍼티로 둔다.
- 기간별 매출 같은 데이터는 `QueryDefinition -[:READS_FROM]-> Table`로 조회 방법을 정의한다.
- 실제 credential은 TBox에 직접 저장하지 않고 `connection_ref` 같은 참조만 둔다.

## Validation 운영

```bash
uv run python scripts/run_validation.py --host localhost --port 6380 --graph commerce_tbox
```

남는 validation 노드는 항상 최신 실행 결과 하나다.

```text
(:ValidationRun)-[:HAS_ISSUE]->(:ValidationIssue)
(:ValidationIssue)-[:AFFECTS]->(ABoxInstance)  # instance uuid가 있을 때만 연결
```

검증 기준:

- `entity` ClassDef: 동일 label의 ABox 노드를 검사한다.
- `logical_entity` ClassDef: Falkor에 동일 label의 ABox 노드가 있으면 error다.
- entity ABox node는 `uuid`가 없으면 error다.
- required/unique property를 검사한다.
- relationship cardinality는 from/to 양쪽이 모두 `entity`일 때만 local edge로 검사한다.
- logical entity와의 관계는 외부 key/query resolution 대상으로 보고 local edge cardinality를 강제하지 않는다.
