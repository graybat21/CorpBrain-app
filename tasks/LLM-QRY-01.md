---
name: Feature Task
about: SRS 기반의 구체적인 개발 태스크 명세
title: "[Feature] LLM-QRY-01: 선택된 엔진(Cloud/Ollama) 연결 상태 확인 (Health Check) 반환"
labels: 'feature, backend, priority:medium'
assignees: ''
---

## :dart: Summary
- 기능명: [LLM-QRY-01] LLM 엔진 Health Check
- 목적: 현재 선택된 엔진(Cloud API 또는 Local Ollama)과 정상적으로 통신이 가능한지 핑(Ping)을 날려 상태를 반환한다.

## :link: References (Spec & Context)
- SRS 문서: `REQ-FUNC-011`

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] Option A인 경우: 외부 네트워크 연결 체크 또는 Cloud API Ping 테스트
- [ ] Option B인 경우: 로컬 호스트(`http://127.0.0.1:11434`)의 Ollama 서버 Ping 동작 확인
- [ ] 상태에 따라 `true/false` DTO 리턴

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: Ollama 데몬 미실행 시 체크
- Given: 설정이 Option B(Ollama)로 지정되어 있으나 백그라운드 프로세스가 내려가 있음
- When: Health Check 쿼리를 실행함
- Then: 연결 시간 초과(Timeout) 등을 감지하여 `status: false` 응답을 반환한다.

## :construction: Dependencies & Blockers
- Depends on: API-003
