# CorpBrain MVP Task Breakdown List (v4 — P1~P5 원칙 적용)

본 문서는 `SRS-draft_v0.5.md`를 기반으로 식별된 개발 태스크 리스트입니다.

> **설계 원칙**
> - **P1 데이터·계약 우선 (SSOT)**: DB 스키마, API DTO, Mock 데이터를 최우선 도출
> - **P2 CQRS 분리**: 상태 변경(Write/Command)과 조회(Read/Query)를 별개 태스크로 격리
> - **P3 AC → 테스트 코드**: 인수 조건(AC)을 자동화된 테스트 태스크로 변환
> - **P4 닫힌 문맥 (Closed Context)**: 태스크 1건 = 단일 목적
> - **P5 UI/백엔드 분리**: 프론트엔드 UI 조립과 백엔드 로직을 별도 태스크로 추출

> **v4 변경 이력**: P1~P5 원칙 검증 후 Data Contract(SSOT) 3건, CQRS Read API 2건, 테스트 자동화 4건, AI Engine 분리 1건, Push 알림 백엔드 1건, 프론트엔드 목록 화면 1건 — 총 13개 태스크 추가. AIE-002를 AIE-002a/002b로 분리.

---

## 0. Data Contract — SSOT (P1)

| Task ID | Epic | Feature (기능명) | 관련 SRS 섹션 | 선행 태스크 | 복잡도 |
|---|---|---|---|---|---|
| **SSOT-001** | Data Contract | API Contract/DTO 스키마 정의 (OpenAPI Spec) | 6.1 API Endpoint 전체 | None | M |
| **SSOT-002** | Data Contract | 개발용 Mock 데이터 Seed/Fixture 생성 | 6.2 전체 | INF-009 | L |
| **SSOT-003** | Data Contract | Webhook 인바운드 Payload 정규화 스키마 정의 (Slack/Jira) | 6.1 #1~2, 3.1 | None | M |

---

## 1. UI/UX Design (DES)

| Task ID | Epic | Feature (기능명) | 관련 SRS 섹션 | 선행 태스크 | 복잡도 |
|---|---|---|---|---|---|
| **DES-001** | UI/UX Design | Trust-Anchor (딥링크) UI/UX 설계 | 4.1.3 F3 | None | M |
| **DES-002** | UI/UX Design | 마스킹 규칙 관리 UI/UX 설계 | 4.1.4 F4 | None | L |
| **DES-003** | UI/UX Design | HITL 승인 대시보드 UI/UX 설계 | 4.1.5 F5 | None | H |
| **DES-004** | UI/UX Design | ROI 리포트 및 관리자 콘솔 UI/UX 설계 | 4.1.6 F6, 3.2 | None | M |

---

## 2. Infrastructure (INF)

| Task ID | Epic | Feature (기능명) | 관련 SRS 섹션 | 선행 태스크 | 복잡도 |
|---|---|---|---|---|---|
| **INF-001** | Infrastructure | PostgreSQL DB 및 Redis Queue 인프라 구축 | 1.5.1 C-TEC-001, 002 | None | M |
| **INF-002** | Infrastructure | Private Cloud 기반 Gemma LLM 서버 구축 | 1.5.2 C-TEC-004 | None | H |
| **INF-003** | Infrastructure | CI/CD 파이프라인 및 마스킹 Build Break 구성 | REQ-FUNC-019, REQ-NF-012 | INF-001 | M |
| **INF-004** | Infrastructure | 모니터링 시스템(Datadog APM, Grafana, Prometheus) 구축 | 4.2.4 REQ-NF-018 | INF-001 | M |
| **INF-005** | Infrastructure | DB 백업(WAL) 주기 설정 및 RTO/RPO 복구 파이프라인 구성 | 4.2.2 REQ-NF-011 | INF-001 | M |
| **INF-006** | Infrastructure | 데이터 유실 대조 및 Deadlock 탐지 자동화 크론 스크립트 | 4.2.2 REQ-NF-007, 009 | INF-001 | M |
| **INF-007** | Infrastructure | UptimeRobot 헬스체크 및 PagerDuty Critical 알림 연동 | 4.2.2 REQ-NF-008, 4.2.3 REQ-NF-017 | INF-004 | M |
| **INF-008** | Infrastructure | 네트워크 TLS 1.3 적용 및 인프라 비용 예산 Alert 구성 | 4.2.3 REQ-NF-014, 4.2.5 REQ-NF-022 | INF-004 | M |
| **INF-009** | Infrastructure | DB 스키마 마이그레이션 (5개 엔터티, 인덱스, 제약조건) | 6.2 전체 (WORKSPACE~SEMANTIC_DRAFT) | INF-001 | M |

---

## 3. Data Ingestion (ING)

| Task ID | Epic | Feature (기능명) | 관련 SRS 섹션 | 선행 태스크 | 복잡도 |
|---|---|---|---|---|---|
| **ING-001** | Data Ingestion | Webhook Handler 및 Redis 비동기 적재 로직 구현 | 4.1.1 REQ-FUNC-003 | INF-001, SSOT-003 | M |
| **ING-002** | Data Ingestion | Slack Events API 연동 모듈 | 4.1.1 REQ-FUNC-001 | ING-001, SSOT-003 | M |
| **ING-003** | Data Ingestion | Jira Webhooks 연동 모듈 | 4.1.1 REQ-FUNC-002 | ING-001, SSOT-003 | M |
| **ING-004** | Data Ingestion | 외부 API Rate Limit 지수 백오프(Exponential Backoff) 구현 | 4.1.1 REQ-FUNC-004, 005 | ING-001 | M |
| **ING-005** | Data Ingestion | Webhook Signature 검증 로직 (Slack Signing Secret / Jira Secret) | 6.1 인증 컬럼, 6.5 validateSignature() | ING-001 | L |
| **ING-006** | Data Ingestion | Data Parser 모듈 (Adapter Pattern 기반 외부 파서 래퍼) | 3.0 Component, 6.5 Class, REQ-NF-026 | ING-001 | M |

---

## 4. Privacy & Security (SEC)

| Task ID | Epic | Feature (기능명) | 관련 SRS 섹션 | 선행 태스크 | 복잡도 |
|---|---|---|---|---|---|
| **SEC-001** | Privacy & Security | 정규식 기반 PII 사전 마스킹 엔진 구현 | 4.1.4 REQ-FUNC-014 | INF-001 | M |
| **SEC-002** | Privacy & Security | NER 모델 기반 기밀 정보 이중 마스킹 연동 | 4.1.4 REQ-FUNC-015 | SEC-001, INF-002 | H |
| **SEC-003** | Privacy & Security | 고객사 커스텀 MASKING_RULE 동적 적용 로직 | 4.1.4 REQ-FUNC-016, 017 | SEC-001 | M |
| **SEC-004** | Privacy & Security | 연동 OAuth Token AES-256 암호화 모듈 구현 | 4.2.3 REQ-NF-013 | None | M |
| **SEC-005** | Privacy & Security | 전역 API 호출 Audit Log(감사 로그) 미들웨어 구현 | 4.2.3 REQ-NF-016 | AUTH-001 | M |
| **SEC-006** | Privacy & Security | PII 마스킹 회귀 테스트셋 200건 설계 및 작성 | REQ-FUNC-019, REQ-NF-012 | SEC-001 | M |

---

## 5. Auth (AUTH)

| Task ID | Epic | Feature (기능명) | 관련 SRS 섹션 | 선행 태스크 | 복잡도 |
|---|---|---|---|---|---|
| **AUTH-001** | Auth | JWT 기반 인증/인가 모듈 구현 (Bearer Token 발급/검증) | 6.1 인증 컬럼 전체 (JWT) | INF-001 | M |
| **AUTH-002** | Auth | RBAC(Role-Based Access Control) 미들웨어 (Admin/Manager/User) | REQ-FUNC-025, 6.1 (Admin, Manager+ 권한) | AUTH-001 | M |

---

## 6. AI Engine (AIE)

| Task ID | Epic | Feature (기능명) | 관련 SRS 섹션 | 선행 태스크 | 복잡도 |
|---|---|---|---|---|---|
| **AIE-001** | AI Engine | 수집 데이터 시간순 정렬 및 전처리 모듈 | 4.1.2 REQ-FUNC-006 | ING-002, ING-003, ING-006 | L |
| **AIE-002a** | AI Engine | 시맨틱 임베딩 기반 문맥 병합(Merge) 로직 | 4.1.2 REQ-FUNC-007 | AIE-001, INF-002 | H |
| **AIE-002b** | AI Engine | 문맥 충돌(Context Collision) 감지 및 Diff 생성 로직 | 4.1.2 REQ-FUNC-008 | AIE-002a | H |
| **AIE-003** | AI Engine | 요약 문장별 원본 딥링크(Trust-Anchor) 강제 매핑 로직 | 4.1.3 REQ-FUNC-010 | AIE-002b | H |
| **AIE-004** | AI Engine | 수정 이력 기반 RL(강화학습) 피드백 루프 데이터 파이프라인 | 4.1.5 REQ-FUNC-022, REQ-NF-005 | INF-001 | H |

---

## 7. API Core (API) — Command / Write (P2)

| Task ID | Epic | Feature (기능명) | 관련 SRS 섹션 | 선행 태스크 | 복잡도 |
|---|---|---|---|---|---|
| **API-W001** | API Core (Write) | `POST /api/v1/drafts/generate` — 초안 생성 Command | 4.1.2 REQ-FUNC-009, REQ-NF-002 | SSOT-001, AIE-003, SEC-002 | H |
| **API-W002** | API Core (Write) | `POST /api/v1/masking-rules` — 마스킹 규칙 등록 Command | 4.1.4 REQ-FUNC-018 | SSOT-001, INF-009 | L |
| **API-W003** | API Core (Write) | `PATCH /api/v1/drafts/{draft_id}/review` — 승인/수정/반려 Command | 4.1.5 REQ-FUNC-020~023, REQ-NF-004 | SSOT-001, API-R001 | M |

---

## 8. API Core (API) — Query / Read (P2)

| Task ID | Epic | Feature (기능명) | 관련 SRS 섹션 | 선행 태스크 | 복잡도 |
|---|---|---|---|---|---|
| **API-R001** | API Core (Read) | `GET /api/v1/drafts/{draft_id}` — 초안 상세 조회 Query | 4.1.3 REQ-FUNC-010~012 | SSOT-001, INF-009 | M |
| **API-R002** | API Core (Read) | `GET /api/v1/drafts` — 초안 목록 조회 Query | 대시보드 목록 렌더링 필수 | SSOT-001, INF-009 | M |
| **API-R003** | API Core (Read) | `GET /api/v1/masking-rules` — 마스킹 규칙 목록 조회 Query | APP-004 관리 화면 필수 | SSOT-001, INF-009 | L |
| **API-R004** | API Core (Read) | `GET /api/v1/reports/roi` — ROI 리포트 조회 Query | 4.1.6 REQ-FUNC-024, 025 | SSOT-001, AUTH-002 | M |
| **API-R005** | API Core (Read) | `GET /api/v1/health` — 시스템 헬스체크 Query | 6.1, REQ-NF-008 | None | L |

---

## 9. API Core (API) — Cross-cutting Middleware

| Task ID | Epic | Feature (기능명) | 관련 SRS 섹션 | 선행 태스크 | 복잡도 |
|---|---|---|---|---|---|
| **API-M001** | API Middleware | 내부 API Rate Limiting 미들웨어 (엔드포인트별 req/min 제어) | 6.1 Rate Limit 컬럼 전체 | AUTH-001 | M |
| **API-M002** | API Middleware | 초안 생성 완료 Push 알림 백엔드 (WebSocket/SSE 서버) | 3.4.1 "DG→UI: 초안 생성 완료 알림" | INF-001 | M |

---

## 10. External System (EXT)

| Task ID | Epic | Feature (기능명) | 관련 SRS 섹션 | 선행 태스크 | 복잡도 |
|---|---|---|---|---|---|
| **EXT-001** | External System | Notion API 위키 발행 연동 | 3.1, REQ-FUNC-021 | API-W003 | M |
| **EXT-002** | External System | Confluence API 위키 발행 연동 | 3.1, REQ-FUNC-021 | API-W003 | M |
| **EXT-003** | External System | Stripe Billing API 연동 (유료 플랜 구독 추적) | 3.1, REQ-NF-029 | None | M |

---

## 11. Frontend App (APP) — P5: UI 조립 전용

| Task ID | Epic | Feature (기능명) | 관련 SRS 섹션 | 선행 태스크 | 복잡도 |
|---|---|---|---|---|---|
| **APP-001** | Frontend App | HITL 초안 리뷰 및 편집 에디터 UI | 4.1.5 REQ-FUNC-020, 023 | DES-003, API-R001 | H |
| **APP-002** | Frontend App | 딥링크 앵커 호버(툴팁/팝오버) 및 네비게이션 UI | 4.1.3 REQ-FUNC-011, 012 | DES-001, APP-001 | M |
| **APP-003** | Frontend App | 삭제 링크 경고 배지 및 수집 지연 토스트 알림 UI | 4.1.3 REQ-FUNC-013, 4.1.1 REQ-FUNC-005 | APP-002 | L |
| **APP-004** | Frontend App | 커스텀 마스킹 규칙 등록 및 관리 화면 UI | 4.1.4 REQ-FUNC-018 | DES-002, API-W002, API-R003 | M |
| **APP-005** | Frontend App | ROI 대시보드 리포트 화면 UI | 4.1.6 REQ-FUNC-024 | DES-004, API-R004 | M |
| **APP-006** | Frontend App | 시스템 연동(Slack/Jira/Notion) 설정 관리 화면 UI | 3.2 | None | M |
| **APP-007** | Frontend App | GA4 및 Mixpanel 이벤트 트래킹 연동 | 4.2.8 REQ-NF-027, 030, 031 | None | M |
| **APP-008** | Frontend App | 초안 생성 완료 실시간 알림(Push Notification) UI | 3.4.1 "DG→UI" | API-M002, APP-001 | M |
| **APP-009** | Frontend App | 초안 목록 조회 화면 UI | 대시보드 메인 | DES-003, API-R002 | M |

---

## 12. Test Automation (TEST) — P3: AC → 테스트 코드

| Task ID | Epic | Feature (기능명) | 관련 SRS 섹션 | 선행 태스크 | 복잡도 |
|---|---|---|---|---|---|
| **TEST-001** | Test Automation | 수집 파이프라인 Integration Test (TC-001~004) | §5.4 TC-001~004 | ING-002, ING-003, ING-004 | M |
| **TEST-002** | Test Automation | AI 엔진 Unit/Integration Test (TC-005~007) | §5.4 TC-005~007 | AIE-002b, AIE-003 | M |
| **TEST-003** | Test Automation | 프론트엔드 E2E Test (TC-008, 009, 014) | §5.4 TC-008, 009, 014 | APP-001, APP-002, APP-003 | H |
| **TEST-004** | Test Automation | 보안 감사 자동화 Test (TC-019: TLS/AES/OAuth scope) | §5.4 TC-019 | SEC-004, INF-008 | M |

---

## 13. QA & Ops (QA)

| Task ID | Epic | Feature (기능명) | 관련 SRS 섹션 | 선행 태스크 | 복잡도 |
|---|---|---|---|---|---|
| **QA-001** | QA & Ops | 환각률 프록시 모니터링 Alert 로직 (수정 빈도 1.5배 급증 시 Warning) | 4.2.4 REQ-NF-019 | INF-004, API-W003 | M |
| **QA-002** | QA & Ops | 외부 API Rate Limit 소진율 80% Alert 로직 | 4.2.4 REQ-NF-020 | INF-004, ING-004 | L |
| **QA-003** | QA & Ops | 부하 테스트(k6/Locust) 시나리오 스크립트 작성 및 실행 | 4.2.6 REQ-NF-023, 024 | API-W001, API-W003 | M |

---

## Summary

| Epic | 태스크 수 | 적용 원칙 |
|---|---|---|
| Data Contract (SSOT) | 3 | P1 |
| UI/UX Design | 4 | — |
| Infrastructure | 9 | — |
| Data Ingestion | 6 | — |
| Privacy & Security | 6 | — |
| Auth | 2 | — |
| AI Engine | 5 | P4 (AIE-002 분리) |
| API Core — Write (Command) | 3 | P2 |
| API Core — Read (Query) | 5 | P2 |
| API Core — Middleware | 2 | P4, P5 |
| External System | 3 | — |
| Frontend App | 9 | P5 |
| Test Automation | 4 | P3 |
| QA & Ops | 3 | — |
| **합계** | **64** | |

---

## P1~P5 Traceability

| 원칙 | 관련 태스크 | 적용 내용 |
|---|---|---|
| **P1** SSOT | SSOT-001~003 | API DTO 스키마, Mock 데이터, Webhook Payload 계약을 최우선 도출. 모든 API/ING 태스크가 SSOT-001, SSOT-003을 선행 참조 |
| **P2** CQRS | API-W001~W003 / API-R001~R005 | Write(Command)와 Read(Query)를 별개 섹션·별개 태스크로 완전 분리 |
| **P3** AC→테스트 | TEST-001~004, SEC-006, QA-003 | SRS §5.4 TC-001~020을 4개 테스트 그룹 + PII 테스트셋 + 부하 테스트로 자동화 태스크 전환 |
| **P4** 닫힌 문맥 | AIE-002a/002b, API-M002 | AIE-002를 병합/충돌감지로 분리, Push 알림 백엔드를 프론트엔드(APP-008)와 분리 |
| **P5** UI/백엔드 분리 | APP-001~009 vs API-W/R/M | 모든 APP 태스크는 UI 조립만 담당, 백엔드 로직은 API/AIE/SEC 태스크에 격리 |
