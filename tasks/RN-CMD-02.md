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
- **확정 사항: `DEC-08`** — Rename은 `File_Meta.current_path`·`file_name` 갱신으로 끝나며 위키 본문·딥링크를 수정하지 않는다
- **확정 사항: `DEC-04`** — 202 + `task_id` 비동기 실행, 진행률은 `Async_Task` 폴링

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] OS `os.rename()` API를 호출하여 물리 파일명 변경
- [ ] 성공한 파일마다 **`File_Meta`의 `current_path`·`file_name`만 UPDATE**한다. `original_path`는 절대 변경하지 않으며(최초 스캔 시점 불변), **`Wiki_Content`·`deeplink_mappings`·벡터 메타데이터는 손대지 않는다** (`DEC-08`)
- [ ] `Rename_History.old_paths`/`new_paths`에 `{file_id, path}` 형태로 기록해 Undo가 대상 행을 특정할 수 있게 한다
- [ ] 이름 변경 중 권한 부족이나 파일 열림 에러(Lock) 발생 시 해당 항목 Skip 및 Rollback 플래그 처리 → 부분 실패는 **HTTP 207 + `data.failed[]`** (`DEC-03`)
- [ ] 모두 성공 혹은 일부 성공 상태를 `Rename_History` 테이블에 업데이트(`status='applied'`)

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: 정상적인 파일 이름 일괄 변경
- Given: 승인된 Diff 리스트가 존재하며 파일 잠금이 없음
- When: Apply 명령을 호출함
- Then: OS 폴더에서 실제 파일 이름이 변경되고 DB 상태가 적용됨(Applied)으로 바뀐다.

Scenario 2: Rename이 딥링크를 파괴하지 않음 (DEC-08)
- Given: 대상 파일을 참조하는 `[[file_id:UUID]]` 앵커가 위키에 존재함
- When: Rename Apply가 성공적으로 완료됨
- Then: `Wiki_Content.markdown_content`는 **바이트 단위로 변경되지 않으며**, 위키 조회 시 딥링크가 새 경로로 정상 열린다 (`is_broken: false`).

## :gear: Technical & Non-Functional Constraints
- 트랜잭션/OS 에러 방어: 중간에 OS 에러가 나더라도 앱이 크래시되지 않도록 `try-catch` 필수
- **디스크 변경과 DB 갱신의 순서**: `os.rename()` 성공 → 즉시 해당 파일의 `current_path` 커밋. 여러 파일을 하나의 긴 트랜잭션으로 묶지 않는다 (`DEC-05` — 중단 시 디스크와 DB가 어긋난 채 남는다)
- Rename 실행 중 Watcher가 자기 자신의 이동 이벤트를 중복 처리하지 않도록 억제(suppress)한다

## :construction: Dependencies & Blockers
- Depends on: RN-QRY-01
- Blocks: RN-CMD-03
