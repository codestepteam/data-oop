# Project Agent Notes

- 사용자의 지시가 기존 프로젝트 원칙, 모델링 규칙, 데이터 안전성, 라이브 graph 변경/삭제, 보안/credential 처리 측면에서 문제가 될 수 있거나 의도가 불명확하면, 작업을 진행하기 전에 예상 문제를 짚고 사용자에게 다시 확인한다.
- 라이브 TBox는 FalkorDB graph `commerce_data_oop`에 있다.
- 커머스 TBox preset 파일은 유지하지 않는다.
- 커머스 TBox 변경은 사용자가 요청한 경우 FalkorDB `commerce_data_oop` live graph를 갱신한다.
- 단, live graph 변경은 raw Cypher를 바로 쓰기보다 이 프로젝트의 Python 라이브러리 함수를 통해 수행하는 것을 기본 원칙으로 한다.
- 필요한 라이브러리 함수가 없으면 먼저 `src/data_oop`에 함수를 추가/고도화하고, 그 함수를 사용해서 변경한다.
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
Graph: commerce_data_oop
Username: default 또는 공백
Password: 공백
```

## 모델링 및 라이브러리 운영 원칙

- TBox/ABox 구분은 ABox를 묶는 방식이 아니라 TBox를 `:TBox` label로 묶는 방식으로 한다.
- TBox 정의 노드는 공통 label `TBox`로 묶는다. 예: `(:TBox:ClassDef)`, `(:TBox:PropertyDef)`.
- ABox 인스턴스는 공통 `ABox` label로 묶지 않는다. 도메인 class label만 사용한다.
- 모든 실제 graph node는 기본 식별자로 `uuid` property를 가져야 하며, validator는 이를 기본 제약 조건으로 검증한다.
- `Identifiable` interface와 `id` PropertyDef는 사용하지 않는다.
- 실제 credential은 TBox에 직접 저장하지 않고 `connection_ref` 같은 참조만 둔다.

## Validation 운영

```bash
uv run python scripts/run_validation.py --host localhost --port 6380 --graph commerce_data_oop
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
