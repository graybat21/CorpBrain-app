---
name: Feature Task
about: SRS 기반의 구체적인 개발 태스크 명세
title: "[Feature] RN-FE-02: Apply 및 Undo 버튼 동작 및 실패 모달 렌더링"
labels: 'feature, frontend, priority:high'
assignees: ''
---

## :dart: Summary
- 목적: Rename 리스트 상단의 일괄 적용(Apply) 버튼과 원복(Undo) 버튼의 클릭 이벤트 및 API 통신, 결과 수신 후의 상태 처리를 구현한다.

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] [적용하기], [원복하기] 버튼 액션 이벤트 바인딩
- [ ] 버튼 클릭 시 백엔드 Command API 호출 및 진행 중(Loading) 상태 스피너 렌더링
- [ ] 에러 발생(500, 파일 잠김 등) 시 글로벌 에러 팝업 혹은 인라인 Toast 표출 연동

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: 적용 완료 후 상태 업데이트
- Given: Diff 테이블이 렌더링되어 있음
- When: 사용자가 [적용하기] 버튼을 클릭함
- Then: Loading 스피너가 표시된 후 200 OK 수신 시, 성공 알림과 함께 목록이 사라지거나 적용 완료 표시로 갱신된다.

## :construction: Dependencies & Blockers
- Depends on: RN-CMD-02, RN-CMD-03, RN-FE-01
