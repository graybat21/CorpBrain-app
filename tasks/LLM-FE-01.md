---
name: Feature Task
about: SRS 기반의 구체적인 개발 태스크 명세
title: "[Feature] LLM-FE-01: LLM 설정 화면 및 Health Check 상태 표시 UI"
labels: 'feature, frontend, priority:medium'
assignees: ''
---

## :dart: Summary
- 기능명: [LLM-FE-01] LLM 엔진 설정 UI
- 목적: 프론트엔드 환경 설정 페이지에서 Option A/B 엔진 선택 콤보박스를 제공하고 현재 연결 상태(Health)를 시각적 아이콘으로 렌더링한다.

## :link: References (Spec & Context)
- API 명세: API-003, LLM-QRY-01

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] 설정 모달/페이지 내에 Option A/B 선택 UI(콤보박스/라디오 버튼) 마크업
- [ ] 서버에 주기적으로 `GET /api/llm/health` 폴링(Polling)을 수행하여 상태(true/false) 조회
- [ ] 상태에 따라 초록색(✅) 및 붉은색(❌) 신호등 아이콘 컴포넌트 렌더링

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: 상태 변경 UI 갱신
- Given: Option A(클라우드)를 선택해둔 상태
- When: 네트워크를 의도적으로 끊음
- Then: Health Check 폴링이 실패하고, 연결 상태 아이콘이 실시간으로 '연결 끊김(❌)'으로 갱신된다.

## :construction: Dependencies & Blockers
- Depends on: APP-UI-01, API-003
