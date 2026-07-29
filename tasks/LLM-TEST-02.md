---
name: Feature Task
about: SRS 기반의 구체적인 개발 태스크 명세
title: "[Feature] LLM-TEST-02: LLM Health Check 단위 테스트"
labels: 'test, backend, priority:medium'
assignees: ''
---

## :dart: Summary
- 기능명: [LLM-TEST-02] Health Check 테스트 스위트
- 목적: 선택된 LLM 엔진(Option A/B)의 연결 상태 확인 로직이 정상/장애 시나리오 모두에서 올바르게 동작하는지 검증한다.

## :link: References (Spec & Context)
> :bulb: AI Agent & Dev Note: 작업 시작 전 아래 문서를 반드시 먼저 Read/Evaluate 할 것.
- SRS 문서: `04_SRS-Drafts/피벗 버전/SRS-draft_v0.6_OPUS.md` §4.1.2 → **REQ-FUNC-011** (LLM Health Check)
- 가용성: `04_SRS-Drafts/피벗 버전/SRS-draft_v0.6_OPUS.md` §4.2 → **REQ-NF-010** (Graceful Degradation)
- 검증 TC: TC-LLM-005

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] Option B: Ollama 데몬 미구동 상태 Mock 테스트 작성
- [ ] Option A: API 키 만료/네트워크 단절 상태 Mock 테스트 작성
- [ ] Health Check timeout(5초) 경계값 테스트

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: Ollama 데몬 미실행 감지
- Given: Option B 설정이나 Ollama 프로세스가 중지됨
- When: Health Check 쿼리를 실행함
- Then: `status: false`와 timeout 사유가 반환된다.

Scenario 2: Cloud API 키 만료 감지
- Given: Option A 설정이나 API 키가 무효함
- When: Health Check 쿼리를 실행함
- Then: `status: false`가 반환되고 기존 위키 조회 기능은 정상 동작한다 (REQ-NF-010).

## :gear: Technical & Non-Functional Constraints
- 네트워크: Health Check timeout 5초
- Mock: 네트워크 단절/데몬 미구동 시뮬레이션 필수

## :checkered_flag: Definition of Done (DoD)
- [ ] TC-LLM-005 시나리오 자동화
- [ ] CI 환경에서 Mock 기반 테스트 통과

## :construction: Dependencies & Blockers
- Depends on: LLM-QRY-01, API-003
- Blocks: None
