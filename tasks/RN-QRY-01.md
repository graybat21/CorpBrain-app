---
name: Feature Task
about: SRS 기반의 구체적인 개발 태스크 명세
title: "[Feature] RN-QRY-01: 생성된 파일명 Diff (Old/New) 매핑 리스트 반환"
labels: 'feature, backend, priority:low'
assignees: ''
---

## :dart: Summary
- 기능명: [RN-QRY-01] 파일명 Diff 목록 조회
- 목적: 백엔드에서 생성된 임시 Diff 상태(Before/After) 리스트를 프론트엔드로 전달하여 사용자가 미리볼 수 있게 한다.

## :link: References (Spec & Context)
- SRS 문서: `REQ-FUNC-017`

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] `Rename_History` 테이블에서 `status='pending'`인 특정 워크스페이스 내역 SELECT
- [ ] 원본 파일명, 변경될 파일명이 포함된 DTO 구성 후 반환

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: Pending 리스트 정상 반환
- Given: Rename 추천이 완료되어 임시 저장된 3건의 파일 매핑 내역이 있음
- When: 프론트엔드에서 리스트 조회를 요청함
- Then: 200 OK와 함께 old_name, new_name이 포함된 배열 응답이 반환된다.

## :construction: Dependencies & Blockers
- Depends on: RN-CMD-01
- Blocks: RN-FE-01
