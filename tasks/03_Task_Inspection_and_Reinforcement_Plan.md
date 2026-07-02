# [계획서] CorpBrain MVP 개발 태스크 품질 검수 및 보강 계획

## 1. 개요 및 검수 기준 (Executive Summary & Inspection Criteria)
총 64개의 마크다운 태스크 파일에 대해 파일 크기, Task Breakdown 구체성, BDD 인수 조건, NFR 제약사항의 충실도를 전수 및 샘플링 점검했습니다. 
현재 모든 파일이 GitHub Issue 템플릿 구조(Summary, BDD, NFR)를 100% 준수하고 있으나, 실제 프로덕션 환경(Production-ready)에서 필수적인 **동시성 제어, 장애 격리, 예외 상황(Edge Case) 처리** 측면에서 구체성이 부족한 파일들을 식별하여 보강 계획을 수립했습니다.

---

## 2. 품질 부족 파일 식별 및 핵심 보강 계획 (Identified Gaps & Reinforcement Plan)

### 1) 외부 시스템 연동 및 Webhook 영역
- **대상 파일**: `EXT-002_Confluence_API.md`, `EXT-003_Stripe_Billing.md`, `ING-003_Jira_Webhooks.md`
- **식별된 결함 및 한계**:
  - Webhook 중복 수신 시의 **멱등성(Idempotency)** 보장 로직 부재.
  - 외부 API(Atlassian, Stripe) 장애 발생 시 내부 트랜잭션 처리 및 **장애 격리(Circuit Breaker/Retry)** 명세 부족.
- **보강 계획**:
  - Webhook 이벤트 ID 기반의 Redis Lock 중복 체크 로직을 Task Breakdown에 추가.
  - 외부 API 호출 실패 시 지수 백오프(Exponential Backoff) 기반의 재시도 큐 적재 및 Fallback 시나리오를 BDD 인수 조건에 보강.

### 2) QA 및 보안 감사 영역
- **대상 파일**: `QA-002_OWASP_Security_Scan.md`, `SEC-006_PII_Masking_Testset.md`
- **식별된 결함 및 한계**:
  - SAST/DAST 스캐닝 툴(Trivy, ZAP 등)의 구체적인 CI/CD 실행 스크립트 및 환경 변수 설정 명세 부재.
  - 보안 스캔 시 필연적으로 발생하는 **오탐(False Positive)** 예외 처리 및 관리 프로세스 누락.
- **보강 계획**:
  - GitHub Actions 워크플로우 상의 구체적 스캔 도구 설정 및 빌드 차단(Build Break) 기준 명시.
  - `.trivyignore` 또는 억제(Suppression) 룰 관리에 대한 NFR 제약사항 추가.

### 3) UI/UX 설계 및 프론트엔드 영역
- **대상 파일**: `DES-002_Masking_Rules.md`, `APP-007_ROI_Dashboard.md`
- **식별된 결함 및 한계**:
  - 데이터가 없을 때의 빈 화면(**Empty State**), API 지연 시의 로딩 스켈레톤(**Skeleton UI**), 에러 발생 시의 **에러 바운더리(Error Boundary)** 등 엣지 케이스 UI 명세 협소.
  - 접근성(A11y) 및 다국어 통화 포맷팅 명세 부족.
- **보강 계획**:
  - 각 컴포넌트별 예외 상태(Loading, Error, Empty) UI 처리 Task Breakdown 추가.
  - 스크린 리더 지원(`aria-*`) 및 `Intl.NumberFormat`을 활용한 통화 표기 제약사항 보강.

### 4) AI 엔진 및 예외 처리 영역
- **대상 파일**: `AIE-002b_Context_Collision_Diff.md`, `INF-002_Gemma_Server_Setup.md`
- **식별된 결함 및 한계**:
  - LLM 추론 실패(Timeout, Out of Memory) 시의 **Fallback 전략** 및 토큰 사용량/비용 모니터링 연동 명세 부족.
- **보강 계획**:
  - 추론 실패 시 룰 기반 병합으로 전환하는 Fallback 파이프라인 Task 추가.
  - APM(Datadog/Prometheus)을 통한 토큰 사용량 및 추론 지연 시간 메트릭 수집 인수 조건 보강.

---

## 3. 판단의 전제 및 기대 효과 (Premises & Expected Impact)

### 1) 판단의 전제
- 단순 파일 크기나 체크리스트 개수를 넘어, 단일 개발자 또는 AI 어시스턴트(Vibe Coding)가 코드를 작성할 때 "예외 상황에서 시스템이 어떻게 동작해야 하는가?"에 대한 모호함을 제거하는 것을 최우선 기준으로 삼았습니다.

### 2) 기대 효과
- 본 보강 계획을 통해 명세서를 업데이트할 경우, 엣지 케이스와 장애 상황에 대한 방어 로직이 설계 단계부터 반영되어 MVP의 안정성과 감사 가능성(Auditability)이 극대화됩니다.
