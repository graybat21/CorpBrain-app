---
name: Feature Task
about: SRS 기반의 구체적인 개발 태스크 명세
title: "[Feature] RN-CMD-03: `Rename_History` 기록 기반 OS 파일명 100% 원복(Undo) 실행"
labels: 'feature, backend, priority:high'
assignees: ''
---

## :dart: Summary
- 기능명: [RN-CMD-03] 실행 취소 (Undo Command)
- 목적: 사용자가 변경된 파일명을 되돌리고 싶을 때, DB 히스토리를 기반으로 100% 원복을 수행한다.

## :link: References (Spec & Context)
- SRS 문서: `REQ-FUNC-019`

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] 최근 변경된 `Rename_History` 항목 조회 (역순)
- [ ] OS `rename` 함수를 호출해 새로운 이름에서 옛 이름으로 되돌리기
- [ ] 해당 History 상태를 `status='reverted'`로 변경

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: Undo를 통한 100% 롤백
- Given: 방금 Rename 기능으로 이름이 변경된 상태임
- When: Undo(원복) 기능을 실행함
- Then: 물리적 파일 이름이 기존과 100% 동일하게 되돌아온다.

## :construction: Dependencies & Blockers
- Depends on: RN-CMD-02
