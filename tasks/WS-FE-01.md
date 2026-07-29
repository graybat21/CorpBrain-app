---
name: Feature Task
about: SRS 기반의 구체적인 개발 태스크 명세
title: "[Feature] WS-FE-01: 좌측 히스토리 패널 렌더링 및 워크스페이스 목록 연동"
labels: 'feature, frontend, priority:high'
assignees: ''
---

## :dart: Summary
- 기능명: [WS-FE-01] 좌측 패널 UI
- 목적: 프론트엔드 좌측 사이드바에 과거에 생성한 워크스페이스 목록을 렌더링하고, 앱 재시작 후에도 즉시 접근 가능하도록 한다.

## :link: References (Spec & Context)
> :bulb: AI Agent & Dev Note: 작업 시작 전 아래 문서를 반드시 먼저 Read/Evaluate 할 것.
- SRS 문서: `04_SRS-Drafts/피벗 버전/SRS-draft_v0.6_OPUS.md` §4.1.1 → **REQ-FUNC-001, 002** (Workspace Creation & Persistence)
- UI/UX: `04_SRS-Drafts/피벗 버전/SRS-draft_v0.6_OPUS.md` §3.2 (Client Applications)
- API 명세: API-001, MOCK-001

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] 사이드바(Sidebar) 컴포넌트 마크업 및 스타일링 작성
- [ ] `GET /api/v1/workspace` API (초기엔 Mock API 사용) 연동 및 리스트 상태 관리
- [ ] 로딩 상태(Skeleton UI) 및 Empty State 구현

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: 히스토리 패널 목록 렌더링
- Given: 워크스페이스 3개가 DB에 존재함
- When: 앱을 실행하고 좌측 패널을 로드함
- Then: 3개 워크스페이스가 최근 수정일 내림차순으로 표시된다.

Scenario 2: Empty State 표시
- Given: 생성된 워크스페이스가 없음
- When: 좌측 패널을 렌더링함
- Then: "워크스페이스를 생성하세요" Empty State와 생성 버튼이 노출된다.

## :gear: Technical & Non-Functional Constraints
- 성능/UX: 비동기 API 호출 시 Skeleton UI 필수 (REQ-FUNC-002 영속성 체감)
- 확장성: REQ-NF-013 — 50개 이상 목록 렌더링 시 스크롤 가상화 고려

## :checkered_flag: Definition of Done (DoD)
- [ ] Mock API 정상/Empty 시나리오 렌더링 검증 완료
- [ ] 디자인 시스템(APP-UI-01) Color/Typography 일관 적용

## :construction: Dependencies & Blockers
- Depends on: APP-UI-01, MOCK-001
- Blocks: WS-FE-02
