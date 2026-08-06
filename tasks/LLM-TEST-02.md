---
name: Feature Task
about: SRS 기반의 구체적인 개발 태스크 명세
title: "[Feature] LLM-TEST-02: LLM Health Check 및 실패·재시도·부분 실패 정책 단위 테스트"
labels: 'test, backend, priority:medium'
assignees: ''
---

## :dart: Summary
- 기능명: [LLM-TEST-02] Health Check 및 실패 정책 테스트 스위트
- 목적: 선택된 LLM 엔진(Option A/B)의 연결 상태 확인 로직과 **`DEC-16` 실패 정책**(엔진 자동 전환 금지 · 일시적 오류만 재시도 · 파일 단위 부분 실패 207 · 연속 10건 실패 중단)이 정상/장애 시나리오 모두에서 올바르게 동작하는지 검증한다.

## :link: References (Spec & Context)
> :bulb: AI Agent & Dev Note: 작업 시작 전 아래 문서를 반드시 먼저 Read/Evaluate 할 것.
- SRS 문서: `04_SRS-Drafts/피벗 버전/SRS-draft_v0.6_OPUS.md` §4.1.2 → **REQ-FUNC-011** (LLM Health Check)
- 가용성: `04_SRS-Drafts/피벗 버전/SRS-draft_v0.6_OPUS.md` §4.2 → **REQ-NF-010** (Graceful Degradation)
- 검증 TC: TC-LLM-005, **TC-AVAIL-003**
- **확정 사항: `DEC-16`** — 엔진 자동 전환 금지 / 일시적 오류만 3회 지수 백오프 / 파일 단위 부분 실패 후 207 / 연속 10건 실패 시 전체 중단

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] Option B: Ollama 데몬 미구동 상태 Mock 테스트 작성
- [ ] Option A: API 키 만료/네트워크 단절 상태 Mock 테스트 작성
- [ ] Health Check timeout(5초) 경계값 테스트
- [ ] **엔진 자동 전환 부재 검증 (`DEC-16`)**: Option A 호출을 실패시킨 뒤 Ollama가 준비된 환경에서도 **로컬 어댑터가 호출되지 않음**을 Mock 호출 카운트로 단언한다
- [ ] **재시도 대상 구분 테스트 (`DEC-16`)**: `429`·`503`·읽기 타임아웃은 3회까지 재시도되고, `401`·`400`·`EgressBlockedError`·`PII_MASKING_FAILED`는 **1회로 끝남**을 호출 횟수로 검증한다
- [ ] **백오프 간격 테스트**: 재시도 대기가 1s→2s→4s 계열로 증가하는지(가짜 시계 주입) 확인하고, `retry-after` 헤더가 있으면 그 값이 우선되는지 검증한다
- [ ] **부분 실패 207 테스트 (`DEC-16`)**: 100개 중 3개 파일 호출을 실패시켜 작업이 `completed`로 끝나고 응답이 **207 + `ok:true` + `data.failed[]` 3건**임을 단언한다. `failed[]` 항목에 `file_id`·`error.code`만 있고 **원문 청크·프롬프트가 없음**도 함께 단언한다
- [ ] **연속 실패 전체 중단 테스트**: 연속 10건 실패 시 남은 파일을 처리하지 않고 `status='failed'` + `LLM_UNAVAILABLE`로 종료되는지 검증한다
- [ ] **실패 파일 재분석 멱등성 테스트**: 실패 파일의 `File_Meta.parse_status`가 `parsed`가 아니므로 재분석 시 성공 파일은 건너뛰고 실패 파일만 재처리되는지 확인한다
- [ ] **타임아웃 설정 주입 테스트**: `App_Config`의 `llm_timeout_*` 값을 바꾸면 실제 클라이언트 타임아웃이 따라 변하는지 검증한다 (하드코딩 회귀 방지)

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: Ollama 데몬 미실행 감지
- Given: Option B 설정이나 Ollama 프로세스가 중지됨
- When: Health Check 쿼리를 실행함
- Then: `status: false`와 timeout 사유가 반환된다.

Scenario 2: Cloud API 키 만료 감지
- Given: Option A 설정이나 API 키가 무효함
- When: Health Check 쿼리를 실행함
- Then: `status: false`가 반환되고 기존 위키 조회 기능은 정상 동작한다 (REQ-NF-010).

Scenario 3: 부분 실패가 성공으로 위장되지 않음 (DEC-16)
- Given: 100개 파일 심층 분석 중 3개 파일의 LLM 호출이 재시도 3회 후에도 실패함
- When: 작업이 종료되고 결과를 조회함
- Then: 나머지 97개는 위키에 반영되고 응답은 **207 + `ok:true` + `data.failed[]` 3건**이다. **200/`ok:true`로 조용히 넘어가지 않는다.**

Scenario 4: Option A 실패 시 Option B로 자동 전환하지 않음 (DEC-16)
- Given: Option A가 선택되어 있고 Anthropic 호출이 `503`으로 계속 실패하며, 로컬 Ollama는 정상 구동 중임
- When: 심층 분석을 실행함
- Then: 재시도 3회 후 해당 파일이 실패로 기록되고, **로컬 생성 어댑터는 단 한 번도 호출되지 않는다**(사용자가 승인한 보안 결정을 앱이 바꾸지 않는다).

## :gear: Technical & Non-Functional Constraints
- 네트워크: Health Check timeout 5초. 나머지 타임아웃은 `App_Config`의 `llm_timeout_*`에서 주입 (`DEC-16` — 하드코딩 금지)
- Mock: 네트워크 단절/데몬 미구동 시뮬레이션 필수. 백오프 대기는 **가짜 시계**로 주입해 테스트가 실제로 7초를 기다리지 않게 한다
- 실패 정보: `data.failed[]` 단언 시 원문 청크·프롬프트 부재를 함께 검사한다 (`DEC-16`)

## :checkered_flag: Definition of Done (DoD)
- [ ] TC-LLM-005 시나리오 자동화
- [ ] **TC-AVAIL-003**(부분 실패 207 + 엔진 자동 전환 부재) 통과
- [ ] CI 환경에서 Mock 기반 테스트 통과

## :construction: Dependencies & Blockers
- Depends on: LLM-QRY-01, API-003
- Blocks: None
