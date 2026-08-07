---
name: Feature Task
about: SRS 기반의 구체적인 개발 태스크 명세
title: "[Feature] WS-FE-02: 워크스페이스 생성 모달 및 OS 폴더 선택기 연동"
labels: 'feature, frontend, priority:high'
assignees: ''
---

## :dart: Summary
- 기능명: [WS-FE-02] 워크스페이스 생성 UI
- 목적: 사용자가 OS 네이티브 디렉토리 선택기로 2개 이상의 로컬 폴더를 선택하여 워크스페이스를 생성할 수 있는 UI를 제공한다.

## :link: References (Spec & Context)
> :bulb: AI Agent & Dev Note: 작업 시작 전 아래 문서를 반드시 먼저 Read/Evaluate 할 것.
- SRS 문서: `docs/SRS_v1.1_after_grill_OPUS.md` §4.1.1 → **REQ-FUNC-001** (Workspace Creation)
- API 명세: API-001
- 제약: CON-04 (MAX_PATH), ASM-03 (폴더 권한)

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] 신규 생성 버튼 클릭 시 생성 모달(또는 다이얼로그) 표시
- [ ] OS 네이티브 디렉토리 선택기 호출 및 선택된 경로 목록 상태 관리
- [ ] `POST /api/v1/workspace` API 연동 및 성공/실패 Toast 피드백

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: 다중 폴더 선택 및 생성
- Given: 사용자가 OS 디렉토리 선택기로 폴더 A, B를 선택함
- When: [생성] 버튼을 클릭함
- Then: `POST /api/v1/workspace`가 호출되고 성공 시 히스토리 패널에 새 항목이 추가된다.

Scenario 2: 유효하지 않은 경로 에러 처리
- Given: 선택된 폴더 중 하나가 삭제되어 더 이상 존재하지 않음
- When: 생성 API를 호출함
- Then: 404 에러 Toast가 표시되고 UI 상태가 원복된다.

## :gear: Technical & Non-Functional Constraints
- 플랫폼: CON-01 Windows 전용 네이티브 폴더 선택기 연동
- 무결성: 최소 2개 폴더 선택 Validation (REQ-FUNC-001)

## :checkered_flag: Definition of Done (DoD)
- [ ] 2개 이상 폴더 미선택 시 클라이언트 Validation 동작
- [ ] 생성 성공/실패 Toast 피드백 구현

## :construction: Dependencies & Blockers
- Depends on: WS-FE-01, MOCK-001
- Blocks: WS-FE-03
