# FalkorDB 기반 지식그래프 운영 CLI 베스트 프랙티스 가이드

이 가이드는 `data-oop` CLI 유틸리티를 사용하여 FalkorDB 상에서 TBox(온톨로지 스키마)를 정의하고, ABox(실제 인스턴스 데이터)를 적재하며, 데이터의 무결성을 검증하고 스키마를 점진적으로 업데이트해 나가는 **실전 워크플로우와 베스트 프랙티스**를 다룹니다.

---

## 0. 연결 및 환경 설정

CLI 실행 시 데이터베이스 접속 플래그를 매번 입력하는 대신, 환경 변수를 활용하여 세션을 고정하는 것을 권장합니다.

```bash
# 로컬 개발 환경용 터미널 세션 설정
export FALKOR_HOST="localhost"
export FALKOR_PORT=6380
export FALKOR_GRAPH="commerce_data"

# 설정 작동 여부 확인 (도움말 출력)
data-oop --help
```

---

## [참고] 식별자 (ID/UUID) 관리 규칙

CLI를 사용할 때 노드, 관계, 스키마의 식별자(ID/UUID)는 다음과 같은 규칙을 따릅니다.

1. **ABox 노드 인스턴스 UUID**: 사용자가 노드 생성(`abox-upsert-node`) 시 `--uuid` 옵션으로 직접 고유 식별자를 입력해야 합니다.
2. **ABox 엣지(관계) 인스턴스 UUID**: 사용자가 직접 입력하지 않습니다. 관계 생성(`abox-upsert-relationship`) 시 `출발UUID:관계명:도착UUID` 포맷으로 **내부에서 자동 생성**됩니다.
3. **TBox 관계 정의 ID**: 사용자가 관계 스키마를 정의(`tbox-define-relationship`) 할 때 `--id` 옵션을 명시할 필요가 없습니다. 생략 시 `rel_출발클래스_관계명_도착클래스` 형식으로 **자동 생성**됩니다.

---

## 1단계: TBox 설계 및 반영 (온톨로지 정의)

지식그래프의 뼈대인 클래스(Class), 속성(Property), 제약 조건(Constraints), 관계(Relationship)를 점진적으로 선언합니다.

### 1. 핵심 클래스 선언

도메인의 주요 엔티티 단위를 정의합니다. (예: 부서와 프로젝트)

```bash
data-oop tbox-create-class --class-name Department --description "회사 부서 정보"
data-oop tbox-create-class --class-name Project --description "부서 프로젝트 정보"
```

### 2. 속성 생성 및 제약 조건 바인딩

클래스가 가질 수 있는 속성을 정의하고 제약 조건(필수 여부, 고유값 여부, null 허용 여부)을 바인딩합니다.

```bash
# 속성 원형 생성
data-oop tbox-create-property --name name --datatype string --description "이름"
data-oop tbox-create-property --name code --datatype string --description "고유 코드"
data-oop tbox-create-property --name budget --datatype integer --description "프로젝트 예산"

# Department 클래스에 속성 바인딩 (name과 code는 필수적이고 유니크해야 함)
data-oop tbox-attach-property --class-name Department --property name --required --unique
data-oop tbox-attach-property --class-name Department --property code --required --unique

# Project 클래스에 속성 바인딩 (budget은 null 가능 및 기본값 0 설정)
data-oop tbox-attach-property --class-name Project --property name --required
data-oop tbox-attach-property --class-name Project --property budget --nullable true --default 0
```

### 3. 관계(Relationship) 정의

클래스와 클래스 간의 연결 규칙을 선언합니다.

```bash
# Department가 Project를 'RUNS' 관계로 연결하며, 관계 식별 ID는 자동 생성함
data-oop tbox-define-relationship --name RUNS --from-class Department --to-class Project --required
```

### 4. 스키마 검사

현재 적용된 TBox 메타데이터가 설계와 일치하는지 한눈에 검사합니다.

```bash
data-oop inspect
```

---

## 2단계: ABox 데이터 입력 및 적재 (지식 채우기)

TBox 규격이 완성되면, 이에 부합하는 실제 데이터 노드와 엣지를 생성합니다. **모든 노드와 엣지는 `uuid`를 가집니다.**

### 1. 인스턴스 노드 생성 (Upsert)

속성값은 올바른 데이터 타입 형식의 JSON 문자열로 전달합니다.

```bash
# IT 부서 생성
data-oop abox-upsert-node --class-name Department --uuid dept-it-01 --properties '{"name": "IT Support", "code": "IT01"}'

# 클라우드 마이그레이션 프로젝트 생성 (TBox 기본값에 의해 budget은 0으로 자동 지정됨)
data-oop abox-upsert-node --class-name Project --uuid proj-cloud-01 --properties '{"name": "Cloud Migration"}'
```

### 2. 노드 간 엣지 연결 (Upsert)

노드 생성 후, TBox 관계 규칙(`RUNS`)에 따라 관계선을 연결합니다.

```bash
data-oop abox-upsert-relationship --from-class Department --from-uuid dept-it-01 --name RUNS --to-class Project --to-uuid proj-cloud-01
```

---

## 3단계: 지식그래프 무결성 검증 (ABox Validation)

적재된 데이터가 TBox 스키마가 규정한 필수값, 유니크값, 엣지 카디널리티 제약 사항을 준수하고 있는지 검증을 실행합니다.

```bash
data-oop validate
```

- 검증에 실패하면 오류 원인과Violating Node의 `uuid`를 출력하고 종료 코드 `1`을 반환합니다.
- 이는 배포 파이프라인(CI/CD) 등에서 데이터 정합성 차단기로 사용할 수 있습니다.

---

## 4단계: 스키마 및 데이터 점진적 업데이트

지식그래프 요구사항이 바뀜에 따라 스키마와 인스턴스를 동적으로 관리 및 변경해 나갑니다.

### 1. 데이터 삭제 (Unified Deletion)

인스턴스 노드나 관계선은 모두 `uuid`를 갖습니다. 동일한 하나의 명령어로 노드와 엣지 모두 삭제 가능합니다.

```bash
# 특정 프로젝트 노드 삭제 (연결된 관계선도 자동 분리 삭제됨)
data-oop abox-delete --uuid proj-cloud-01

# 부서와 프로젝트 간의 RUNS 관계선만 조준 삭제 (관계 UUID: 출발UUID:관계명:도착UUID)
data-oop abox-delete --uuid dept-it-01:RUNS:proj-cloud-01
```

### 2. 스키마 해제 및 수정

TBox 스키마를 점진적으로 구조조정(Evolution)할 때 사용합니다.

```bash
# 클래스에서 속성 바인딩만 제거 (속성 정의 자체는 보존)
data-oop tbox-detach-property --class-name Project --property budget

# TBox 클래스 정의를 완전히 삭제 (관련 관계나 속성 바인딩이 있으면 --detach 플래그 동반 필요)
data-oop tbox-delete-class --class-name Project --detach
```

### 3. 전체 데이터 초기화 (ABox Clear)

스키마(TBox) 설계는 유지하되, 적재된 테스트 데이터(ABox)만 깨끗이 밀고 다시 시작하고 싶을 때 실행합니다.

```bash
data-oop clear-abox --yes
```

---

## 5단계: 외부 RDB 연결 및 집계 적재 (Source Binding & Sync)

원천 데이터(주문/고객 한 줄 한 줄)는 기존 RDB에 그대로 두고, **의미 있는 집계·세그먼트**(예: VIP 고객군, 상품별 매출)만 RDB 쿼리로 뽑아 ABox 노드로 적재합니다. 원천 raw 행은 그래프에 들어가지 않습니다.

### 1. 커넥터 정의 (Connector)

접속 정보 자체가 아니라 **DSN을 담은 환경 변수의 이름(`--dsn-ref`)** 만 저장합니다. 비밀번호는 그래프/덤프에 절대 저장되지 않으며, 동기화 실행 시점에 `os.environ`에서 읽힙니다.

```bash
# Postgres / MySQL: dsn-ref 가 가리키는 env 변수에 DSN 전체(비번 포함)를 보관
#   예) export PROD_DB_DSN="postgresql://reader:secret@db.example.com:5432/shop"
data-oop define-connector --name prod_pg --kind postgres --dsn-ref PROD_DB_DSN

# BigQuery: DSN 대신 metadata 에 project 와 credentials_ref(SA JSON 경로를 담은 env 이름) 지정
#   credentials_ref 생략 시 ADC(Application Default Credentials)로 폴백
data-oop define-connector --name warehouse --kind bigquery \
  --metadata '{"project": "my-proj", "credentials_ref": "GCP_SA_JSON"}'
```

> 보안: 운영용 계정은 **읽기 전용**을 권장합니다. `--sql` 본문은 운영자가 신뢰하는 설정으로 그대로 실행됩니다.

### 2. 클래스에 소스 쿼리 바인딩 (Bind Source)

집계 결과 **한 행이 ABox 노드 한 개**가 됩니다. `--key-columns` 는 재동기화 시 멱등성을 보장하는 업무 키이며, 중복/NULL이면 동기화가 즉시 실패합니다. `--sql` 은 `@파일경로` 형식으로 파일에서 읽을 수 있습니다.

```bash
# 상품별 매출: product_id 당 한 노드, rev 컬럼을 revenue 속성으로 매핑
data-oop bind-source --class-name ProductRevenue --connector prod_pg \
  --sql "SELECT p.id AS product_id, SUM(oi.amount) AS rev FROM order_items oi JOIN products p ON p.id = oi.product_id GROUP BY p.id" \
  --key-columns product_id --column-map '{"rev": "revenue"}'

# 긴 SQL은 파일로 분리
data-oop bind-source --class-name VipSegment --connector prod_pg \
  --sql @sql/vip_segment.sql --key-columns segment_name
```

**기존 노드와 관계(엣지) 연결**: `--link` 옵션(반복 가능)으로, 적재되는 각 행을 그래프에 이미 존재하는 노드와 관계로 잇습니다. 행의 `key` 컬럼 값을 대상 클래스의 `target` 속성과 매칭하여 엣지를 MERGE합니다. 관계는 **TBox에 미리 정의**되어 있어야 합니다. 대상 노드를 못 찾으면 해당 링크는 건너뛰고(`links_missing`로 집계), 동기화 자체는 실패하지 않습니다.
```bash
# Inventory 행을 같은 product_id 를 가진 기존 Product 노드에 (Inventory)-[:OF_PRODUCT]->(Product) 로 연결
#   target 생략 시 key 와 같은 이름(product_id)으로 매칭, dir 생략 시 out (source -> target)
data-oop bind-source --class-name Inventory --connector prod_pg \
  --sql "SELECT sku, product_id, qty FROM inventory" --key-columns sku \
  --link '{"rel": "OF_PRODUCT", "to": "Product", "key": "product_id"}'
```

### 3. 동기화 실행 (Sync)

바인딩된 쿼리를 실행해 결과 행을 ABox 노드로 적재합니다. 기본적으로 동일 커넥터에서 이전에 적재한 노드를 먼저 비우고 새로 채웁니다(prune). 각 노드에는 `synced_at`, `source_connector` 가 기록됩니다.

```bash
data-oop sync-source --class-name ProductRevenue
# 출력: fetched=120, upserted=120, pruned=0, synced_at=...

# 기존 노드를 지우지 않고 누적하려면
data-oop sync-source --class-name ProductRevenue --no-prune
```

> 적재된 집계 노드는 평범한 ABox 노드이므로 `validate`/`inspect`/`db-dump` 가 그대로 적용됩니다. 주기적 갱신은 외부 cron 에서 `sync-source` 를 호출하면 됩니다.

### 4. 커넥터/바인딩 조회 및 삭제

```bash
# 커넥터와 소스 바인딩 목록 확인
data-oop list-connectors

# 커넥터 삭제 (바인딩이 걸려 있으면 차단됨 → --detach 로 바인딩까지 정리)
data-oop delete-connector --name prod_pg --detach
```

> 드라이버는 선택 설치입니다: `pip install 'data-oop[postgres]'` / `[mysql]` / `[bigquery]`.

---

## 5-B단계: 온디맨드 메트릭 (Metric) — 값은 RDB에 두고 조회법만 저장

`bind-source`/`sync-source`(5단계)가 **행을 그래프로 복사**하는 반면, 메트릭은 정반대입니다. 매출·주문수 같은 수치 데이터는 RDB에 그대로 두고, 그래프에는 **"어떻게 조회하는지"(커넥터 + SQL + 노드 값 바인딩)만** 저장합니다. 값은 호출 시점에 라이브로 계산되며, 그래프에는 아무것도 쓰지 않습니다(선택적 TTL 캐시 제외).

저장 구조: `(:TBox:ClassDef)-[:HAS_METRIC]->(:TBox:MetricDef)-[:USES_CONNECTOR]->(:TBox:ConnectorDef)`. 한 클래스에 메트릭 여러 개를 매달 수 있습니다.

### 1. 메트릭 정의 (define-metric)

SQL에는 중립 `:name` 플레이스홀더를 쓰고, `--param-map` 으로 각 플레이스홀더를 노드 속성 템플릿(`{customer_id}`)에 연결합니다. 값은 항상 드라이버 바인드 파라미터로 전달되어 SQL 인젝션이 차단됩니다.

```bash
data-oop define-metric --name revenue_last_30d --class-name Customer --connector prod_pg \
  --sql "SELECT sum(amount) AS value FROM orders WHERE customer_id = :cid AND ts > now() - interval '30 day'" \
  --param-map '{"cid":"{customer_id}"}' --result-kind scalar --ttl-seconds 3600 \
  --description "최근 30일 매출"
```

- `--result-kind`: `scalar`(첫 행의 `--value-column`, 기본 `value`) | `row`(첫 행 dict) | `rows`(전체 행)
- `--ttl-seconds`: 생략하면 항상 라이브. 지정하면 노드의 `metricsCache` 속성에 값을 캐시하고 TTL 안에서는 RDB를 건드리지 않습니다.

### 2. 메트릭 해석 (resolve-metric)

```bash
# 앵커 노드의 속성으로 param_map 을 채워 라이브 조회
data-oop resolve-metric --name revenue_last_30d --node-uuid <customer-uuid>
# 출력: 340000

# 노드 없이 바인드 값을 직접 지정 (param_map 보다 우선)
data-oop resolve-metric --name revenue_last_30d --param cid=123 --no-cache
```

### 3. 워크플로우에서 사용 (fetch_metric 액션)

저장된 워크플로우가 메트릭을 읽으려면 `fetch_metric` 스텝을 씁니다(읽기 전용, 그래프 미변경). 결과는 `{step_id: {"value": ...}}` 로 이후 스텝에 전달됩니다. 예: 주문 생성 트리거 → 고객 매출 조회 → 임계값 넘으면 세그먼트 연결.

```python
save_workflow(graph=graph, name="classify_customer",
    parameters=[{"name": "customer_uuid", "type": "string"},
                {"name": "customer_id", "type": "string"}],
    steps=[
        {"step_id": "rev", "action": "fetch_metric", "metric_name": "revenue_last_30d",
         "parameters": {"cid": "{customer_id}"}},
        {"step_id": "seg", "action": "create_relationship", "if_present": "rev.value",
         "from_class": "Customer", "from_uuid": "{customer_uuid}",
         "relationship_name": "IN_SEGMENT", "to_class": "Segment", "to_uuid": "seg-high-value"},
    ])
```

> 메트릭 원본 수치는 RDB에 남고, 그래프에는 분류 결과(엣지)만 저장됩니다. 임계값 비교 연산자는 아직 DSL에 없으므로, SQL의 `HAVING` 으로 조건을 만족하는 행만 반환하게 하거나 `if_present` 로 존재성만 검사하세요.

### 4. 메트릭 조회 및 삭제

```bash
data-oop list-metrics                       # 전체
data-oop list-metrics --class-name Customer # 클래스 필터
data-oop delete-metric --name revenue_last_30d
```

> 메트릭이 참조하는 커넥터는 `delete-connector` 가 차단합니다(`--detach` 로 메트릭까지 정리).

---

## 6단계: 트리거 (클래스 콜백) — 생성/수정 시 워크플로우 실행

특정 클래스의 ABox 노드가 **생성(create)되거나 수정(update)될 때** 자동으로 동작을 실행하고 싶을 때 트리거를 등록합니다. 핵심 원칙은 **콜백이 코드가 아니라 데이터**라는 것입니다. 트리거는 실행할 동작을 직접 담지 않고, 이미 FalkorDB에 저장된 **워크플로우(WorkflowDefinition)의 이름을 참조**합니다. 따라서 규칙 전체(언제·무엇을·어떤 조건에)가 그래프 안에 데이터로 존재하며, `db-dump`/`db-restore`로 그대로 이동합니다.

저장 구조는 `(:TBox:ClassDef)-[:HAS_TRIGGER]->(:TBox:TriggerDef)` 이며, TBox의 일부로 관리됩니다.

### 1. 사전 준비: 실행할 워크플로우 저장

트리거가 가리킬 워크플로우가 **먼저 존재**해야 합니다(없으면 `add-trigger`가 거부합니다). 워크플로우는 API/라이브러리로 저장합니다.

```python
# 예: Order 생성 시 감사 로그 노드를 만드는 워크플로우
from data_oop import save_workflow
save_workflow(
    graph=graph,
    name="audit_order",
    steps=[{
        "step_id": "log",
        "action": "create_node",
        "class_name": "AuditLog",
        "properties": {"order_ref": "{order_id}"},  # 워크플로우 파라미터 order_id 를 참조
    }],
)
```

#### 워크플로우 파라미터는 어떻게 정해지나

트리거가 발화하면, 먼저 **변경된 노드의 전체 현재 상태**(저장된 모든 속성 + `uuid`)를 그래프에서 읽어 보간 컨텍스트로 씁니다. 부분 수정(일부 속성만 upsert)이어도 워크플로우는 노드의 나머지 속성까지 모두 볼 수 있습니다.

그 위에서 워크플로우로 넘어갈 파라미터는 두 방식 중 하나로 결정됩니다.

- **명시적 매핑 (권장)** — `--param 워크플로우파라미터=템플릿` 으로 "어떤 파라미터에 어떤 값"을 직접 지정합니다. 템플릿은 노드에 대해 보간됩니다(`{uuid}`, `{total}`). 중괄호가 없으면 리터럴입니다. 워크플로우 파라미터명과 노드 속성명이 달라도 됩니다.
- **기본값 (매핑 생략)** — `--param` 을 하나도 주지 않으면 노드의 속성이 그대로(평탄하게) 파라미터로 전달됩니다. 워크플로우가 노드 속성명과 같은 이름을 참조할 때 편합니다.

### 2. 트리거 등록 (add-trigger)

```bash
# Order 생성 시 audit_order 실행. --param 으로 워크플로우 파라미터(order_id) <- 노드 속성(uuid) 매핑
#   워크플로우 파라미터명과 노드 속성명이 달라도 명시적으로 연결됨
data-oop add-trigger --class-name Order --name on_order_created \
  --event create --workflow audit_order \
  --param order_id={uuid} --param amount={total} --param channel=naver

# --param 생략 시: 노드 속성이 그대로 파라미터로 전달 (워크플로우가 {uuid} 등 노드 속성명을 직접 참조할 때)
data-oop add-trigger --class-name Order --name on_order_simple \
  --event create --workflow audit_order

# 수정 시 + 조건부 발화: paid 속성이 비어있지 않을 때만 실행
#   --condition 은 노드의 속성 경로이며, 값이 비어있으면(None/""/[]) 스킵됩니다.
data-oop add-trigger --class-name Order --name on_paid \
  --event update --workflow notify_payment --condition paid \
  --param order_id={uuid}

# 같은 이벤트에 여러 트리거가 걸리면 --order 오름차순으로 실행됩니다.
data-oop add-trigger --class-name Order --name first_step \
  --event create --workflow step_a --order 0
data-oop add-trigger --class-name Order --name second_step \
  --event create --workflow step_b --order 1

# 등록만 하고 발화는 끄려면 --disabled
data-oop add-trigger --class-name Order --name draft_only \
  --event create --workflow wf_x --disabled
```

옵션 요약:

| 옵션 | 설명 |
|------|------|
| `--class-name` | 트리거가 걸리는 ClassDef |
| `--name` | 트리거 이름 (클래스 내 유일) |
| `--event` | `create` 또는 `update` |
| `--workflow` | 실행할 WorkflowDefinition 이름 (사전 존재 필수) |
| `--condition` | 노드 속성 경로. 값이 비어있지 않을 때만 발화 (선택) |
| `--order` | 동일 이벤트 내 실행 순서 (기본 0) |
| `--disabled` | 등록하되 발화하지 않음 |
| `--description` | 설명 |
| `--param` | `워크플로우파라미터=템플릿` (반복 가능). 노드에 대해 보간. 생략 시 노드 속성 평탄 전달 |

### 3. 발화 시점

트리거는 ABox 노드의 단일 진입점(`upsert_abox_node`)에서 발화합니다. 즉 `abox-upsert-node`, API를 통한 노드 생성/수정, 그리고 **워크플로우가 만든 노드**까지 모두 대상입니다.

```bash
# 아래 한 줄이 Order 노드를 만들고, on_order_created 트리거가 audit_order 를 실행 → AuditLog 노드 생성
data-oop abox-upsert-node --class-name Order --uuid order-1 --properties '{"total": 100}'
```

> 예외 — 대량 동기화: `sync-source`(5단계)는 수천 행을 적재할 수 있어 **행별로 트리거를 발화하지 않습니다.** 동기화로 들어온 집계 노드에 후처리가 필요하면 동기화 후 별도 워크플로우를 호출하세요.

### 4. 무한 루프 / 발산 방지 — 등록 시 사이클 검사

트리거의 워크플로우가 또 다른 노드를 만들면 그 노드의 트리거가 다시 발화될 수 있습니다. 이 관계는 방향 그래프를 이루며, **사이클은 무한 콜백 루프**가 됩니다. `add-trigger`는 저장 직전에 트리거 그래프를 분석하여 **사이클을 만드는 트리거는 저장 자체를 거부**합니다(종료 코드 `1`).

```bash
# A 생성 -> wfA(B 생성), B 생성 -> wfB(A 생성) 인 경우, 두 번째 등록이 거부됨
data-oop add-trigger --class-name AuditLog --name loopback --event create --workflow make_order
# Error: Trigger cycle detected: loopback -> on_order_created
#   cycle: loopback -> on_order_created
```

저장 전에 현재 트리거 그래프 전체의 건전성을 확인하려면 `validate-triggers`를 사용합니다. 읽기 전용이며 아무것도 저장하지 않습니다.

```bash
data-oop validate-triggers
# Trigger graph OK: no cycles.
#
# 문제가 있으면:
# Trigger graph INVALID: 1 cycle(s).
#   cycle: tA -> tB
# Warning - unbounded fan-out (loop_over): tC        # loop_over 로 행 수만큼 노드 생성 → 정적 상한 불가
# Warning - dynamic class (unanalyzable): tD          # class_name 이 {변수} 라 정적 분석 불가
# Warning - triggers referencing missing workflows: tE
```

정적 분석은 **보수적**입니다. "사이클 없음"은 안전 보증이지만, `--condition`(런타임 데이터 의존)이나 `loop_over`(행 수 의존), 동적 클래스명은 정적으로 묶을 수 없어 경고로만 표시됩니다. 이를 보완하기 위해 런타임에 **트리거 연쇄 깊이 상한(`MAX_TRIGGER_DEPTH`)** 이 백스톱으로 항상 동작하므로, 정적 분석이 놓친 경우라도 무한 재귀로 빠지지 않습니다.

### 5. 트리거 조회 및 삭제

```bash
# 등록된 트리거 목록
data-oop list-triggers
#   - on_order_created: (Order) on create -> workflow 'audit_order' [order=0]

# inspect 출력에도 [Triggers] 섹션으로 함께 표시됨
data-oop inspect

# 트리거 삭제 (클래스 + 이름으로 지정)
data-oop delete-trigger --class-name Order --name on_order_created
```
