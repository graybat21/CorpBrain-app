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
- **확정 사항: `DEC-08`** — Undo도 `current_path` 되돌리기로 끝난다. 위키·딥링크는 무관

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] 최근 변경된 `Rename_History` 항목 조회 (역순)
- [ ] OS `rename` 함수를 호출해 새로운 이름에서 옛 이름으로 되돌리기 (`old_paths`의 `{file_id, path}` 기준)
- [ ] 원복 성공한 파일마다 **`File_Meta.current_path`·`file_name`을 `old_paths` 값으로 UPDATE.** `original_path`는 건드리지 않으며 위키 본문·`deeplink_mappings`도 수정 대상이 아니다 (`DEC-08`)
- [ ] 이미 원복된 History에 재요청이 오면 `ALREADY_UNDONE`(409)로 응답 (`DEC-03`)
- [ ] 해당 History 상태를 `status='reverted'` + `undone_at` 기록으로 변경

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: Undo를 통한 100% 롤백
- Given: 방금 Rename 기능으로 이름이 변경된 상태임
- When: Undo(원복) 기능을 실행함
- Then: 물리적 파일 이름이 기존과 100% 동일하게 되돌아오고, `File_Meta.current_path`도 동일 값으로 복귀한다.

Scenario 2: Undo 후에도 딥링크 정합 유지 (DEC-08)
- Given: Rename → Undo를 순차 실행함
- When: 해당 파일을 참조하는 위키의 딥링크를 클릭함
- Then: 원복된 경로로 파일이 정상적으로 열린다 (`is_broken: false`, 위키 재생성 불필요).

## :construction: Dependencies & Blockers
- Depends on: RN-CMD-02
