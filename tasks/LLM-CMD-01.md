---
name: Feature Task
about: SRS 기반의 구체적인 개발 태스크 명세
title: "[Feature] LLM-CMD-01: LLM 엔진 설정(Option A/B) 변경 및 DB 저장"
labels: 'feature, backend, priority:high'
assignees: ''
---

## :dart: Summary
- 기능명: [LLM-CMD-01] 하이브리드 LLM 설정 관리 (Command)
- 목적: 사용자가 클라우드 API(Option A)와 로컬 프라이빗(Option B - Ollama) 중 선호하는 엔진을 선택하면 이 설정을 데이터베이스에 저장한다.

## :link: References (Spec & Context)
> :bulb: AI Agent & Dev Note: 작업 시작 전 아래 문서를 반드시 먼저 Read/Evaluate 할 것.
- SRS 문서: `REQ-FUNC-007`
- DTO 명세: `API-003`

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] Option A/B Enum 정의 및 `Settings_Meta` 테이블에 업데이트하는 로직 구현
- [ ] Option B(Ollama) 선택 시 내부적으로 로컬 데몬 구동 여부 플래그를 활성화하도록 연계

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: 정상적인 엔진 변경 요청
- Given: 현재 Option A 상태인 시스템
- When: 사용자가 Option B로 설정을 변경하는 요청을 보냄
- Then: DB에 설정이 'Option B'로 반영되고 성공 응답(200 OK)이 반환된다.

## :gear: Technical & Non-Functional Constraints
- 무결성: Enum에 존재하지 않는 엔진 값이 들어올 경우 예외 처리 필수

## :checkered_flag: Definition of Done (DoD)
- [ ] 단위 테스트 작성 및 통과
- [ ] Swagger 스펙상 유효한 값만 전송되도록 Validation 적용

## :construction: Dependencies & Blockers
- Depends on: DB-001, API-003
- Blocks: LLM-CMD-02, LLM-CMD-03
