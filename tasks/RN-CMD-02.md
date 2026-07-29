---
name: Feature Task
about: SRS 기반의 구체적인 개발 태스크 명세
title: "[Feature] RN-CMD-02: 승인된 Diff 기반 OS 레벨 물리 파일 Rename 및 내역 확정"
labels: 'feature, backend, priority:high, os'
assignees: ''
---

## :dart: Summary
- 기능명: [RN-CMD-02] 파일명 변경 실행 (Apply Command)
- 목적: 사용자가 제안을 승인하면 실제로 OS 레벨에서 파일 이름을 변경하고(Rename), DB 기록을 확정(Applied)한다.

## :link: References (Spec & Context)
- SRS 문서: `REQ-FUNC-018`

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] OS `os.rename()` 또는 `shutil.move()` API를 호출하여 물리 파일명 변경
- [ ] 이름 변경 중 권한 부족이나 파일 열림 에러(Lock) 발생 시 해당 항목 Skip 및 Rollback 플래그 처리
- [ ] 모두 성공 혹은 일부 성공 상태를 `Rename_History` 테이블에 업데이트(`status='applied'`)

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: 정상적인 파일 이름 일괄 변경
- Given: 승인된 Diff 리스트가 존재하며 파일 잠금이 없음
- When: Apply 명령을 호출함
- Then: OS 폴더에서 실제 파일 이름이 변경되고 DB 상태가 적용됨(Applied)으로 바뀐다.

## :gear: Technical & Non-Functional Constraints
- 트랜잭션/OS 에러 방어: 중간에 OS 에러가 나더라도 앱이 크래시되지 않도록 `try-catch` 필수

## :construction: Dependencies & Blockers
- Depends on: RN-QRY-01
- Blocks: RN-CMD-03
