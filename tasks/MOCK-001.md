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
- [ ] **MSW(Mock Service Worker)** 로 Mock 구성 — 별도 Mock 서버 프로세스를 띄우지 않는다. 이유: 실제 런타임은 랜덤 포트 + Bearer 토큰(`DEC-02`)이므로 고정 URL Mock 서버는 실 환경과 계약이 어긋난다. MSW는 `window.__CORPBRAIN__` 주입 여부와 무관하게 fetch를 가로챈다.
- [ ] Mock 응답은 **API-001의 OpenAPI 스키마에서 파생**시켜 계약 드리프트 방지
- [ ] 프론트엔드 연동 가이드 문서 작성 (`window.__CORPBRAIN__ = { baseUrl, token }` 부재 시 개발 모드 fallback 규약 포함)

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: Mock Workspace 목록 조회
- Given: 개발 모드에서 MSW 핸들러가 등록되어 있음
- When: 프론트엔드에서 `/api/v1/workspace` 로 GET 요청을 보냄
- Then: 200 OK와 함께 미리 정의된 3개의 Workspace 더미 객체 리스트(ID, 경로 등 포함)를 반환한다.

> 주의: 엔드포인트는 SRS §6.1 기준 `/api/v1/workspace` (단수)다. `/workspaces` 복수형을 쓰지 않는다.

## :gear: Technical & Non-Functional Constraints
- 환경 분리: 개발 환경(`NODE_ENV=development` 등)에서만 Mock 서버가 동작해야 하며 빌드 시 프로덕션 환경에서는 제외되어야 함.

## :checkered_flag: Definition of Done (DoD)
- [ ] 프론트엔드에서 Mock API 호출 시 정상 응답을 받는가?

## :construction: Dependencies & Blockers
- Depends on: API-001, API-002
- Blocks: WS-FE-01, WS-FE-02, WS-FE-03
