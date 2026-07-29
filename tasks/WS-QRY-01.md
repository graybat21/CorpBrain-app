---
name: Feature Task
about: SRS 기반의 구체적인 개발 태스크 명세
title: "[Feature] WS-QRY-01: 전체 워크스페이스 목록 및 단일 상세 조회 로직"
labels: 'feature, backend, priority:medium'
assignees: ''
---

## :dart: Summary
- 기능명: [WS-QRY-01] 워크스페이스 조회 (Query)
- 목적: 프론트엔드 히스토리 패널 렌더링을 위해 전체 워크스페이스 목록을 불러오고, 특정 워크스페이스의 메타 정보를 단일 조회한다.

## :link: References (Spec & Context)
- SRS 문서: `REQ-FUNC-002`

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] DB에서 최근 생성/수정일 기준 내림차순(DESC)으로 `Workspace_Meta` 목록 SELECT
- [ ] UUID를 기반으로 단일 워크스페이스 정보 SELECT
- [ ] 조회 데이터를 `WorkspaceListRes` DTO 형식으로 매핑하여 반환

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: 빈 워크스페이스 목록 조회
- Given: 생성된 워크스페이스가 없음
- When: 전체 목록 조회를 요청함
- Then: 빈 배열 `[]` 과 함께 200 OK 응답이 반환된다.

## :gear: Technical & Non-Functional Constraints
- 성능: DB Index를 활용하여 리스트 조회 p95 ≤ 30ms 달성

## :checkered_flag: Definition of Done (DoD)
- [ ] 정렬 조건(수정일 최신순) 적용 및 테스트 통과
- [ ] API 반환값이 DTO 명세와 일치하는가?

## :construction: Dependencies & Blockers
- Depends on: WS-CMD-01
