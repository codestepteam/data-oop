# 온톨로지 모델링을 위한 문제정의 가이드: Good vs. Bad 예시

온톨로지(TBox & ABox)를 설계할 때 가장 흔히 빠지는 함정은 **"모든 세상을 모델링하려는 것(World Modeling Trap)"**입니다. 문제정의가 명확하지 않으면 TBox 스키마는 끊임없이 확장되고, 데이터 적재(ABox)는 불가능해지며, 결국 검증(Validation)조차 수행할 수 없게 됩니다.

이 가이드는 `data-oop` 프레임워크와 FalkorDB 환경에서 성공적인 온톨로지를 구축하기 위해 **좋은 문제정의와 나쁜 문제정의**를 비교하고, TBox/ABox 모델링 관점의 설계 및 검증 예시를 제시합니다.

---

## 0. 온톨로지 설계 및 검증 핵심 원칙 (`data-oop` 기준)

1. **명확한 범위 제약**: 특정 질문(Competency Question)에 답할 수 있는 최소한의 TBox만 정의합니다.
2. **식별자 제약**: ABox의 모든 실제 노드는 공통 `ABox` 라벨을 갖지 않고, 도메인 클래스 라벨(예: `:Customer`)만 사용하며 필수적으로 `uuid` 속성을 가집니다 (`Identifiable` 인터페이스나 `id` 속성은 금지).
3. **자동 검증성 (Validation Feasibility)**: 필수 속성(`required=True`), 유니크 속성(`unique=True`), 관계 카디널리티 조건을 `data-oop` 검증기로 즉시 확인 가능해야 합니다.

---

## 1. 문제정의 Good vs. Bad 비교 (10개 예시)

### 1. 매출 증대 및 채널 최적화
* **나쁜 정의**: "우리 서비스의 매출을 증대한다."
  * **이유**: 단순 매출은 온톨로지 스키마로 매핑할 대상이 너무 방대함. 구매 과정, 마케팅, 제품 가격 등 모든 요소를 다뤄야 하므로 범위 제어가 불가능하고 검증할 수 없음.
* **좋은 정의**: "판매 채널(SalesChannel)별 고객의 구매 전환율을 추적하여 실적이 저조한 채널을 찾아낸다."
  * **이유**: 핵심 엔티티(채널, 고객, 주문)와 관계가 명확함. `data-oop`에서 특정 채널을 경유한 주문 경로 탐색 Cypher 쿼리로 실적 계산이 가능함.
  * **TBox 설계**:
    ```python
    builder = TBoxBuilder()
    builder.class_("SalesChannel", description="판매 채널") \
        .property("name", datatype="string", required=True) \
        .property("type", datatype="string", required=True) \
        .end() \
        .class_("Order", description="주문") \
        .property("amount", datatype="integer", required=True) \
        .property("status", datatype="string", required=True) \
        .end()
    ```
  * **검증 & 쿼리**:
    * 검증: 모든 주문 노드가 `uuid`와 `amount`를 필수적으로 가졌는지 확인.
    * 쿼리: `MATCH (c:Customer)-[:ORDERED]->(o:Order)-[:VIA]->(s:SalesChannel) RETURN s.name, sum(o.amount)`

---

### 2. 공급망 단일 장애점(SPOF) 감지
* **나쁜 정의**: "공급망 파트너 정보와 자재 흐름을 전부 연결하여 그래프로 관리한다."
  * **이유**: 단순 파트너십 매핑은 비즈니스적 목적이 불분명하여 어떤 관계가 중요하고 어떠한 속성이 제약되어야 하는지 알 수 없음. 결국 단순 관계 목록 나열에 그쳐 관리 코스트만 발생.
* **좋은 정의**: "완제품(Product) 조립에 필요한 원자재(Material)의 1차(Tier 1) 및 2차(Tier 2) 공급망 상에서 대체 불가능한 단일 공급업체(Supplier)에 의존하고 있는 부품 경로를 탐색하여 공급망 중단 리스크를 식별한다."
  * **이유**: 그래프 탐색(path traversal)의 기점(`Product`)과 도달점(`Supplier`), 그리고 그 사이의 핵심 경로(`-[:REQUIRES]->`, `-[:SUPPLIED_BY]->`)가 명확히 스키마 수준에서 규정됨.
  * **TBox 설계**:
    ```python
    builder = TBoxBuilder()
    builder.class_("Product", description="완제품") \
        .property("name", datatype="string", required=True) \
        .end() \
        .class_("Material", description="원자재/부품") \
        .property("name", datatype="string", required=True) \
        .end() \
        .class_("Supplier", description="공급업체") \
        .property("country", datatype="string", required=True) \
        .end()
    ```
  * **검증 & 쿼리**:
    * 쿼리: `MATCH (p:Product)-[:REQUIRES*1..2]->(m:Material) WITH p, m MATCH (m)-[:SUPPLIED_BY]->(s:Supplier) WITH p, m, count(s) as supplier_cnt WHERE supplier_cnt = 1 RETURN p.name, m.name` (1차/2차 자재 중 단일 공급업체에 의존하는 부품 검출)

---

### 3. IT 인프라 방치 자원 식별
* **나쁜 정의**: "회사의 모든 서버 및 클라우드 자원의 비용을 절감한다."
  * **이유**: 단순 '비용 절감'은 액션이 모호함. 소스 코드 리팩토링, DB 튜닝 등 온톨로지 외적인 요소가 섞여서 모델 구조를 잡을 수 없음.
* **좋은 정의**: "가상 인스턴스(Instance)와 이를 실행하는 서비스(Service), 그리고 서비스의 소유자(Owner)를 연결하여 30일 이상 트래픽이 없으면서 소유자가 불분명한 방치 자원을 감지한다."
  * **이유**: 인프라 리소스 소유권 체인을 추적하여 미사용 자원을 정확하게 매핑 및 정리할 수 있음.
  * **TBox 설계**:
    ```python
    builder = TBoxBuilder()
    builder.class_("Instance") \
        .property("provider_id", datatype="string", required=True) \
        .property("unused_days", datatype="integer", required=True) \
        .end() \
        .class_("Service") \
        .property("name", datatype="string", required=True) \
        .end()
    ```
  * **검증 & 쿼리**:
    * 쿼리: 소유자 관계가 단절된 경우 탐색 `MATCH (i:Instance) WHERE i.unused_days >= 30 AND NOT (i)-[:RUNS_FOR]->(:Service)-[:OWNED_BY]->(:Owner) RETURN i.uuid`

---

### 4. 마케팅 기여도 분석 (Multi-touch Attribution)
* **나쁜 정의**: "고객 여정(Customer Journey) 데이터를 수집하여 마케팅 효율을 분석한다."
  * **이유**: '고객 여정'이라는 표현은 매우 포괄적이어서 클릭, 장바구니, 결제 외에 CS 통화, 리뷰 작성 등 모호한 행동 노드들을 양산함. 기여도를 평가할 수 있는 타임라인 경로 모델링의 규격이 정의되지 않음.
* **좋은 정의**: "고객(Customer)이 특정 주문(Order)을 생성하기 전 발생한 마케팅 접점(Touchpoint)들의 이벤트 인스턴스를 타임라인(`-[:NEXT]->`)으로 정렬하고, 첫 접점(First Touch)과 마지막 접점(Last Touch)에 기여한 캠페인(Campaign)을 판별한다."
  * **이유**: 이벤트 연결의 방향성과 순서가 명확하며, 타임라인의 기점과 결말을 나타내는 에지 제약 조건(`required`) 및 그래프 관계 탐색 범위를 확정할 수 있음.
  * **TBox 설계**:
    ```python
    builder = TBoxBuilder()
    builder.class_("Touchpoint", description="마케팅 접점") \
        .property("type", datatype="string", required=True) \
        .property("timestamp", datatype="integer", required=True) \
        .end() \
        .class_("Campaign", description="마케팅 캠페인") \
        .property("campaign_name", datatype="string", required=True) \
        .end()
    ```
  * **검증 & 쿼리**:
    * 쿼리: `MATCH (c:Customer)-[:HAD]->(first:Touchpoint) WHERE NOT (()-[:NEXT]->(first)) MATCH (first)-[:NEXT*0..]->(last:Touchpoint)-[:TRIGGERS]->(o:Order) RETURN first, last` (첫 마케팅 터치와 마지막 구매 전환 직전의 터치 추출)

---

### 5. 고객 지원 티켓 병목 분석
* **나쁜 정의**: "고객 문의 응대 데이터를 체계적으로 관리한다."
  * **이유**: 단순 테이블 구조(문의 내용, 일시, 답변 내용)를 그래프 데이터베이스에 그대로 집어넣어, RDB로도 충분히 할 수 있는 단순 조회 성능의 온톨로지로 퇴색됨.
* **좋은 정의**: "고객 지원 문의(Ticket)가 1차 상담사(Agent)로부터 2차 부서(DevTeam, Logistics) 등으로 이관되는 전파 경로(`-[:ESCALATED_TO]->`) 상에서 평균 이관 지연 시간이 48시간을 초과하는 조직(Department) 및 담당자를 식별한다."
  * **이유**: 이관 경로 상에서 부서 노드와 에스컬레이션 관계의 상태(시간 속성)를 추적하여 병목 구간을 구체적인 그래프의 가중치로 도출할 수 있음.
  * **TBox 설계**:
    ```python
    builder = TBoxBuilder()
    builder.class_("Ticket", description="고객 지원 티켓") \
        .property("title", datatype="string", required=True) \
        .end() \
        .class_("EscalationEvent", description="이관 이벤트") \
        .property("duration_hours", datatype="integer", required=True) \
        .end()
    ```
  * **검증 & 쿼리**:
    * 검증: `EscalationEvent` 노드 생성 시 `duration_hours`가 양수인지 검증 룰 적용 가능.
    * 쿼리: `MATCH (t:Ticket)-[:HAS_EVENT]->(e:EscalationEvent)-[:ASSIGNED_TO]->(d:Department) WHERE e.duration_hours > 48 RETURN t.uuid, d.name, e.duration_hours`

---

### 6. 소프트웨어 취약점 영향도 전파 추적
* **나쁜 정의**: "사내 소프트웨어의 전체 보안을 개선한다."
  * **이유**: 방화벽 설정, 암호화 정책, 물리 보안 등을 포함하려고 하면 온톨로지의 초점이 흔들림.
* **좋은 정의**: "프로덕션 컨테이너 이미지(ContainerImage)에 설치된 패키지(Package)와 오픈소스 라이브러리(Library) 간 의존 관계를 매핑하여, 특정 라이브러리의 보안 취약점(CVE)이 어떤 서비스에 영향을 주는지 실시간으로 전파 경로를 추적한다."
  * **이유**: 의존성 그래프(Dependency Graph)라는 명확한 데이터 구조를 사용하여 영향도를 최상위 서비스까지 재귀적으로 탐색 가능함.
  * **TBox 설계**:
    ```python
    builder = TBoxBuilder()
    builder.class_("Library") \
        .property("name", datatype="string", required=True) \
        .property("cve_id", datatype="string", required=False) \
        .end()
    ```
  * **검증 & 쿼리**:
    * 쿼리: `MATCH (l:Library {name: "log4j"})<-[:DEPENDS_ON*]-(p:Package)<-[:CONTAINS]-(i:ContainerImage) RETURN i.uuid`

---

### 7. 인사 이동과 퇴사율 상관관계 분석
* **나쁜 정의**: "직원들의 퇴사율을 줄이고 행복한 일터를 만든다."
  * **이유**: 퇴사 원인은 복합적이어서 온톨로지만으로 전수 추적 불가. '행복'은 계량화하기 힘든 속성임.
* **좋은 정의**: "직원(Employee)의 소속 부서 이동 이력(TransferEvent), 팀의 규모(TeamSize), 그리고 소속 팀장(Manager)의 변경 이력을 매핑하여 퇴사(ResignationEvent)와의 상관관계를 분석한다."
  * **이유**: 부서 이동 빈도와 팀장 변경이라는 팩트 중심의 노드와 관계를 정밀하게 추적 가능.
  * **TBox 설계**:
    ```python
    builder = TBoxBuilder()
    builder.class_("Employee") \
        .property("tenure_months", datatype="integer", required=True) \
        .end() \
        .class_("TransferEvent") \
        .property("effective_date", datatype="string", required=True) \
        .end()
    ```

---

### 8. 경쟁 상품 사양 및 가격 모니터링
* **나쁜 정의**: "경쟁사의 모든 비즈니스 활동을 모니터링한다."
  * **이유**: 경쟁사 채용 현황, 재무제표, 홍보 기사 등을 다 넣으려다 온톨로지가 쓰레기통이 됨.
* **좋은 정의**: "자사 상품(Product)과 사양이 대응되는 경쟁사 상품(CompetitorProduct)을 매핑하고 가격 속성을 비교하여, 동일 스펙 대비 가격 차이가 15% 이상 발생하는 상품군을 탐색한다."
  * **이유**: 비교 가능한 매핑 관계(`[:COMPETES_WITH]`)를 맺고 자사와 경쟁사의 가격 차이라는 구체적 검증 룰 적용 가능.
  * **TBox 설계**:
    ```python
    builder = TBoxBuilder()
    builder.class_("CompetitorProduct") \
        .property("model_name", datatype="string", required=True) \
        .property("price", datatype="integer", required=True) \
        .end()
    ```

---

### 9. 지인 추천 네트워크 및 바이럴 기여도 분석
* **나쁜 정의**: "지인 추천 마케팅의 효과를 측정하고 바이럴 유입을 늘린다."
  * **이유**: '효과 측정'과 '바이럴'은 온톨로지 관점에서 구체적인 노드나 관계로 환원되기 어려움. 모호한 목표로 인해 시스템에 무작위 마케팅 설문 데이터나 소셜 미디어 크롤링 정보 등을 닥치는 대로 밀어 넣어 모델이 망가짐.
* **좋은 정의**: "신규 가입 고객(Customer)의 추천인 관계(`-[:RECOMMENDED_BY]->`)를 연결하여, 네트워크상에서 3단계(3-hop) 이내에 가장 많은 신규 가입을 유도한 핵심 인물(인플루언서)과 그들을 통해 유입된 고객들의 누적 매출 기여도를 산출한다."
  * **이유**: 추천 관계(Referral Graph)라는 명확한 에지와 3-hop이라는 그래프 탐색 반경 제약이 있음. 각 노드(`Customer`)의 매출 속성과 관계만으로 명확한 결과를 도출할 수 있음.
  * **TBox 설계**:
    ```python
    builder = TBoxBuilder()
    builder.class_("Customer", description="고객 정보") \
        .property("name", datatype="string", required=True) \
        .property("total_spend", datatype="integer", required=True) \
        .end()
    ```
  * **검증 & 쿼리**:
    * 검증: 추천 에지(`RECOMMENDED_BY`)가 자기 자신을 가리키는 순환 참조(Self-loop) 위반이 없는지 검증 가능.
    * 쿼리: `MATCH (influencer:Customer)<-[:RECOMMENDED_BY*1..3]-(referred:Customer) WITH influencer, sum(referred.total_spend) as network_revenue RETURN influencer.uuid, network_revenue ORDER BY network_revenue DESC LIMIT 10`

---

### 10. 거래형 커머스 구매 이탈(휴면) 위험 고객 감지
* **나쁜 정의**: "구매율이 떨어진 고객들에게 마케팅 이메일을 발송하여 복귀시킨다."
  * **이유**: '구매율 저하'의 명확한 판단 기준이 없고, '이메일 발송'이라는 단순 액션은 온톨로지 정의와 무관함. 결국 스키마에 이메일 발송 이력, 마케팅 문구 등을 무분별하게 추가하려다 모델 구조가 망가짐.
* **좋은 정의**: "고객(Customer)별 평균 구매 주기 대비 마지막 주문(Order) 이후 경과 일수가 3배를 초과한 상태에서, 최근 7일 동안 장바구니 담기(CartEvent) 행동만 취하고 결제 완료로 전환하지 못한 휴면 위험 고객을 선별한다."
  * **이유**: 개별 구매 주기 속성, 마지막 주문일과의 시간 연산, 그리고 행동 단계 에지(`-[:CARTED]->`, `-[:ORDERED]->`)의 미전환 상태를 Cypher 경로 탐색과 속성 비교를 통해 오차 없이 검출 가능.
  * **TBox 설계**:
    ```python
    builder = TBoxBuilder()
    builder.class_("Customer", description="고객 정보") \
        .property("avg_purchase_interval_days", datatype="integer", required=True) \
        .end() \
        .class_("CartEvent", description="장바구니 담기 이벤트") \
        .property("timestamp", datatype="integer", required=True) \
        .end()
    ```
  * **검증 & 쿼리**:
    * 검증: `Customer`의 `avg_purchase_interval_days`가 양의 정수인지 `data-oop` ABox Validation이 속성 검증.
    * 쿼리: `MATCH (c:Customer)-[:CARTED]->(e:CartEvent) WHERE NOT (c)-[:ORDERED]->(:Order) AND (1716681600 - e.timestamp) > 7 * 24 * 3600 RETURN c.uuid` (현재 시점 기준 7일간 결제 없는 건 탐색)

---

## 2. 요약: 나쁜 정의와 좋은 정의를 구별하는 자가진단 질문

| 질문 항목 | 나쁜 문제정의 (Bad) | 좋은 문제정의 (Good) |
| :--- | :--- | :--- |
| **목표가 구체적인가?** | 매출 증가, 보안 개선, 행복 등 추상적 | 채널별 전환율 추적, SPOF 감지, 방치 자원 식별 등 명확함 |
| **TBox 클래스가 5개 이하로 시작하는가?** | 세상을 다 담으려고 하여 30개가 넘어감 | 핵심 비즈니스 흐름을 나타내는 3~5개 핵심 클래스로 시작 |
| **ABox 검증(Validation) 규칙을 쓸 수 있는가?** | "행복 여부 검증 불가" | "특정 필수 속성 누락 검증", "1:N 관계 위반 검증" 가능 |
| **Cypher 쿼리로 결과 도출이 가능한가?** | "매출이 왜 오르는지 상관관계 쿼리 불가" | "A-B-C 경로 탐색 후 가중치 연산" 가능 |
