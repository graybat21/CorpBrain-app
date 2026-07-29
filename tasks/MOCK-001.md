---
name: Feature Task
about: SRS 기반의 구체적인 개발 태스크 명세
title: "[Feature] MOCK-001: 프론트엔드 UI 독립 개발용 Workspace 및 대시보드 Mock 서버 세팅"
labels: 'feature, mock, priority:medium'
assignees: ''
---

## :dart: Summary
- 기능명: [MOCK-001] Workspace / 대시보드 Mock API 제공
- 목적: 백엔드 비즈니스 로직 완성 전, 프론트엔드가 UI(사이드바, 대시보드 화면) 개발을 병행할 수 있도록 정적 더미 데이터를 반환하는 Mock 서버를 세팅한다.

## :link: References (Spec & Context)
- API 명세: API-001, API-002

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] Mock 데이터(JSON) 더미 팩토리 생성 (워크스페이스 리스트, 스캔 결과 등)
- [ ] HTTP Mock 서버(MSW, json-server, 또는 Python FastAPI 정적 엔드포인트) 구성
- [ ] 프론트엔드 연동 가이드 문서 작성

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: Mock Workspace 목록 조회
- Given: Mock 서버가 실행 중임
- When: 프론트엔드에서 `/api/v1/workspaces` 로 GET 요청을 보냄
- Then: 200 OK와 함께 미리 정의된 3개의 Workspace 더미 객체 리스트(ID, 경로 등 포함)를 반환한다.

## :gear: Technical & Non-Functional Constraints
- 환경 분리: 개발 환경(`NODE_ENV=development` 등)에서만 Mock 서버가 동작해야 하며 빌드 시 프로덕션 환경에서는 제외되어야 함.

## :checkered_flag: Definition of Done (DoD)
- [ ] 프론트엔드에서 Mock API 호출 시 정상 응답을 받는가?

## :construction: Dependencies & Blockers
- Depends on: API-001, API-002
- Blocks: WS-FE-01, WS-FE-02, WS-FE-03
