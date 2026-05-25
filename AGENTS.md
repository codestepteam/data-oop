# Project Agent Notes

- 사용자의 지시가 기존 프로젝트 원칙, 모델링 규칙, 데이터 안전성, 라이브 graph 변경/삭제, 보안/credential 처리 측면에서 문제가 될 수 있거나 의도가 불명확하면, 작업을 진행하기 전에 예상 문제를 짚고 사용자에게 다시 확인한다.
- 라이브 TBox는 FalkorDB graph `commerce_tbox`에 있다.
- 커머스 TBox preset 파일은 유지하지 않는다.
- 커머스 TBox 변경은 사용자가 요청한 경우 FalkorDB `commerce_tbox` live graph를 갱신한다.
- 단, live graph 변경은 raw Cypher를 바로 쓰기보다 이 프로젝트의 Python 라이브러리 함수를 통해 수행하는 것을 기본 원칙으로 한다.
- 필요한 라이브러리 함수가 없으면 먼저 `src/tbox`에 함수를 추가/고도화하고, 그 함수를 사용해서 변경한다.
- 반복되는 작업 흐름은 스크립트에 임시로 두지 말고 라이브러리 함수로 추출한다.
- 라이브러리 함수에는 테스트를 추가하고, 실제 FalkorDB 변경 전/후 검증 가능한 형태로 만든다.
- 이 프로젝트의 목적은 라이브 TBox를 운영하면서 동시에 TBox 라이브러리를 계속 고도화하는 것이다.
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
Team
Event
Product
Channel
WorkflowDefinition
```

## 모델링 원칙

- TBox/ABox 구분은 ABox를 묶는 방식이 아니라 TBox를 `:TBox` label로 묶는 방식으로 한다.
- 모든 클래스는 인스턴스화가 가능하며, 필요한 경우 FalkorDB 내에 ABox 노드로 생성한다.
- 모든 node의 기본 식별자는 `uuid`다. 도메인/외부 시스템 식별자는 별도 프로퍼티로 둔다.
- `Team`은 조직 내 부서/팀을 나타내며, `name`(필수, 고유) 속성을 갖는다.
- `Event`는 팀이 주최하는 이벤트/행사이며, 시작일(`start_date`, 필수), 종료일(`end_date`, 옵셔널), 설명(`description`, 필수) 속성을 갖는다.
- `Product`는 팀이 관리하거나 이벤트에서 홍보하는 상품을 나타낸다.
- `Channel`은 이벤트가 진행되는 플랫폼/채널(예: Instagram Shop 등)을 나타낸다.
- `WorkflowDefinition`은 UI에서 빌딩된 스키마-드리븐 저코드/노코드 워크플로우 정의 스펙(`name` 필수/유니크, `steps_json` 필수)을 담는다.
- 관계성:
  - `Team -[:ORGANIZED]-> Event`: 팀이 특정 이벤트를 개최/기획한다.
  - `Event -[:ON_CHANNEL]-> Channel`: 이벤트가 특정 채널을 대상으로 운영된다.
  - `Event -[:INCLUDES]-> Product`: 이벤트에 특정 제품군들이 포함/연동된다.
  - `Team -[:MANAGES]-> Product`: 팀이 해당 제품의 관리 책임을 맡는다.
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

- 모든 ClassDef: 동일 label의 ABox 노드를 검사한다.
- ABox node는 `uuid`가 없으면 error다.
- required/unique property를 검사한다.
- relationship cardinality는 local edge로 검사한다.
